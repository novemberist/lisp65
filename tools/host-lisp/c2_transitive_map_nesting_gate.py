#!/usr/bin/env python3
"""Derive and reject nested MAP lifetimes from a final linked ELF.

Mapped bodies are not named by a hand-maintained list.  They are derived from
the emitted wrapper shape (enter -> body -> leave); every sized function in a
body owner's section then joins the population.  Existing linked ownership
gates separately reject direct entry into those sections without a wrapper.
"""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth, Symbol  # noqa: E402


READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
ENTER = "c2_mapped_far_enter"
LEAVE = "c2_mapped_far_leave"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def _functions(truth: ElfTruth) -> list[Symbol]:
    return [row for row in truth.symbols
            if row.symbol_type == "Function" and row.bytes > 0]


def _canonical(rows: Iterable[Symbol]) -> Symbol | None:
    values = list(rows)
    return max(values, key=lambda row: (row.bytes, row.name)) if values else None


def linked_graph(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ,
                          include_section_data=True)
    functions = _functions(truth)
    starts: dict[tuple[str, int], list[Symbol]] = defaultdict(list)
    by_identity: dict[tuple[str, int], list[Symbol]] = defaultdict(list)
    for symbol in functions:
        starts[(symbol.section, symbol.value)].append(symbol)
        by_identity[(symbol.section, symbol.value)].append(symbol)

    def owner(section: str, address: int) -> Symbol | None:
        exact = _canonical(starts.get((section, address), ()))
        if exact is not None:
            return exact
        containing = [symbol for symbol in functions
                      if symbol.section == section
                      and symbol.value <= address < symbol.value + symbol.bytes]
        return min(containing, key=lambda row: (row.bytes, row.name)) \
            if containing else None

    edges: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    transfers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for relocation in truth.relocations:
        pc = relocation.offset - 1
        source = owner(relocation.source_section, pc)
        section = truth.section(relocation.source_section)
        at = pc - section.address
        data = truth.section_bytes(relocation.source_section)
        if source is None or not 0 <= at < len(data) \
                or data[at] not in (0x20, 0x4C):
            continue
        identity = truth.relocation_target_identity(relocation)
        resolved = identity.get("resolved_value")
        target_section = identity.get("section")
        target_symbol = truth.symbols[relocation.target_symbol_index]
        if target_symbol.symbol_type == "Function" and relocation.addend == 0:
            destination = target_symbol
        else:
            matches = by_identity.get((target_section, resolved), ()) \
                if isinstance(target_section, str) and isinstance(resolved, int) \
                else ()
            destination = _canonical(matches)
        if destination is None or (destination.section, destination.value) == \
                (source.section, source.value):
            continue
        opcode = "jsr" if data[at] == 0x20 else "jmp"
        edges[source.name].add(destination.name)
        incoming[destination.name].append({
            "owner": source.name,
            "owner_section": source.section,
            "address": pc,
            "edge": opcode,
            "target_section": destination.section,
            "target_identity": [destination.section, destination.value],
        })
        transfers[source.name].append({"address": pc, "edge": opcode,
                                       "target": destination.name,
                                       "target_section": destination.section,
                                       "target_identity": [destination.section,
                                                           destination.value]})

    enter = truth.symbol(ENTER)
    leave = truth.symbol(LEAVE)
    wrappers: list[dict[str, Any]] = []
    mapped_sections: set[str] = set()
    mapped_roots: set[str] = set()
    for name, body in transfers.items():
        ordered = sorted(body, key=lambda row: int(row["address"]))
        enters = [int(row["address"]) for row in ordered
                  if row["edge"] == "jsr" and row["target"] == enter.name]
        leaves = [int(row["address"]) for row in ordered
                  if row["target"] == leave.name]
        if not enters or not leaves:
            continue
        first, last = min(enters), max(leaves)
        roots: list[str] = []
        for row in ordered:
            if not first < int(row["address"]) < last:
                continue
            symbol = truth.symbol(str(row["target"]))
            if symbol.name not in (ENTER, LEAVE):
                roots.append(symbol.name)
                mapped_sections.add(symbol.section)
                mapped_roots.add(symbol.name)
        require(bool(roots), f"MAP wrapper has no body: {name}")
        wrappers.append({"wrapper": name, "body_roots": sorted(set(roots))})

    require(bool(wrappers), "final ELF has no derived MAP wrappers")
    tenants = sorted({symbol.name for symbol in functions
                      if symbol.section in mapped_sections})
    return {
        "truth": truth,
        "edges": edges,
        "incoming": incoming,
        "wrappers": sorted(wrappers, key=lambda row: row["wrapper"]),
        "mapped_sections": sorted(mapped_sections),
        "mapped_roots": sorted(mapped_roots),
        "tenants": tenants,
    }


def paths_to_map(graph: dict[str, Any], roots: Iterable[str], *,
                 injected_edges: dict[str, set[str]] | None = None
                 ) -> list[dict[str, Any]]:
    edges = {name: set(targets)
             for name, targets in graph["edges"].items()}
    for name, targets in (injected_edges or {}).items():
        edges.setdefault(name, set()).update(targets)
    results: list[dict[str, Any]] = []
    for root in sorted(set(roots)):
        pending = deque([root])
        parent: dict[str, str | None] = {root: None}
        while pending:
            current = pending.popleft()
            if current in (ENTER, LEAVE):
                path: list[str] = []
                node: str | None = current
                while node is not None:
                    path.append(node)
                    node = parent[node]
                results.append({"mapped_body": root,
                                "terminal": current,
                                "path": list(reversed(path))})
                continue
            for target in sorted(edges.get(current, ())):
                if target not in parent:
                    parent[target] = current
                    pending.append(target)
    return results


def analyze(elf: Path) -> dict[str, Any]:
    graph = linked_graph(elf)
    violations = paths_to_map(graph, graph["tenants"])
    return {
        "wrappers": graph["wrappers"],
        "mapped_sections": graph["mapped_sections"],
        "mapped_roots": graph["mapped_roots"],
        "tenant_count": len(graph["tenants"]),
        "tenants": graph["tenants"],
        "violations": violations,
    }


def check(elf: Path) -> dict[str, Any]:
    result = analyze(elf)
    require(result["violations"] == [],
            f"nested MAP lifetime reachable: {result['violations']}")
    result["status"] = "PASS: NO MAPPED BODY REACHES MAP ENTER/LEAVE"
    return result


def selftest(elf: Path) -> list[str]:
    graph = linked_graph(elf)
    clean = [name for name in graph["tenants"]
             if not paths_to_map(graph, [name])]
    require(bool(clean), "MAP mutation lacks a clean tenant")
    mutant = paths_to_map(
        graph, [clean[0]], injected_edges={clean[0]: {ENTER}})
    require(bool(mutant) and mutant[0]["terminal"] == ENTER,
            "nested MAP mutation survived")
    return ["reachable-nested-enter"]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: c2_transitive_map_nesting_gate.py ELF", file=sys.stderr)
        return 2
    try:
        elf = Path(argv[1]).resolve()
        result = check(elf)
        mutations = selftest(elf)
    except (GateError, OSError, subprocess.CalledProcessError) as error:
        print(f"transitive MAP nesting gate: FAIL: {error}", file=sys.stderr)
        return 1
    print("transitive MAP nesting gate: PASS "
          f"tenants={result['tenant_count']} mutations={len(mutations)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
