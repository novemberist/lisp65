#!/usr/bin/env python3
"""Attribute the selector-bypass Red with section/MAP-domain identities."""

from __future__ import annotations

from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth, Symbol  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
ELF = ROOT / ("build/c2.3/v1.6-boot-refill-selector-bypass-adapter-card/"
              "wplto/lisp65-c2-substitution-linked.prg.elf")
FINAL_RED = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-adapter-card-final-red.json")
PARTIAL = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-adapter-card-receipt.json")
NESTED_RECEIPT = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-dual-capacity-card-receipt.json")
ABI = ROOT / ("build/c2.3/"
    "nested-map-swap-v1.6-boot-refill-selector-bypass-adapter-preflight-qualification/"
    "c2-asm-leaf-abi.json")
OUT = ARCH / "c2.3-v1.6-map-domain-alias-attribution.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORITY = "e356f513"
SEALED_SOURCE_COMMIT = "07877cb1"
FORMAT = "lisp65-c2-v160-map-domain-alias-attribution-v1"
STATUS = "ATTRIBUTED: BOTH VM-NATIVE JUMPS ARE BASELINE; GRAPH MISCLASSIFIED"
SITES = (0x7E03, 0x7E15)
TARGET = 0x7E8D
BASELINE = ".text"
MAPPED = (".lisp65_c2_mapped_far_service",
          ".lisp65_c2_mapped_diagnostic")


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORITY}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").replace("`", "").split())
    for token in ("mapping state that holds on every path",
                  "address, mapping-domain", "real product finding",
                  "inventories which existing gates are address-only"):
        require(token in text, f"domain-attribution authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORITY, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def functions(truth: ElfTruth) -> list[Symbol]:
    return [row for row in truth.symbols
            if row.symbol_type == "Function" and row.bytes > 0]


def owner(rows: list[Symbol], section: str, address: int) -> Symbol | None:
    found = [row for row in rows if row.section == section
             and row.value <= address < row.value + row.bytes]
    return min(found, key=lambda row: (row.bytes, row.name)) if found else None


def target_owner(truth: ElfTruth, rows: list[Symbol], relocation: Any) \
        -> Symbol | None:
    identity = truth.relocation_target_identity(relocation)
    section = identity.get("section")
    address = identity.get("resolved_value")
    if not isinstance(section, str) or not isinstance(address, int):
        return None
    return owner(rows, section, address)


def domain_graph(truth: ElfTruth) -> dict[str, Any]:
    rows = functions(truth)
    edges: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for relocation in truth.relocations:
        section = truth.section(relocation.source_section)
        raw = truth.section_bytes(section.name)
        pc = relocation.offset - 1
        offset = pc - section.address
        if not 0 <= offset < len(raw) or raw[offset] not in (0x20, 0x4C):
            continue
        source = owner(rows, section.name, pc)
        target = target_owner(truth, rows, relocation)
        if source is None or target is None:
            continue
        source_id = f"{source.section}::{source.name}"
        target_id = f"{target.section}::{target.name}"
        if source_id == target_id:
            continue
        identity = truth.relocation_target_identity(relocation)
        edge = {"source_identity": source_id, "source_section": source.section,
                "owner": source.name, "address": pc,
                "opcode": "JSR" if raw[offset] == 0x20 else "JMP",
                "target_identity": target_id, "target_section": target.section,
                "target": target.name,
                "resolved_address": identity["resolved_value"]}
        edges[source_id].add(target_id)
        incoming[target_id].append(edge)
    return {"edges": edges, "incoming": incoming}


def shortest_path(edges: dict[str, set[str]], start: str, target: str) \
        -> list[str] | None:
    pending = deque([start]); parent: dict[str, str | None] = {start: None}
    while pending:
        current = pending.popleft()
        if current == target:
            path: list[str] = []
            while current is not None:
                path.append(current); current = parent[current]
            return list(reversed(path))
        for successor in sorted(edges.get(current, ())):
            if successor not in parent:
                parent[successor] = current; pending.append(successor)
    return None


def site_rows(truth: ElfTruth) -> list[dict[str, Any]]:
    rows = functions(truth)
    result: list[dict[str, Any]] = []
    for site in SITES:
        matches = []
        for relocation in truth.relocations:
            if relocation.offset - 1 != site:
                continue
            identity = truth.relocation_target_identity(relocation)
            matches.append({"relocation_section": relocation.relocation_section,
                "source_section": relocation.source_section,
                "opcode_address": site, "operand_relocation": relocation.offset,
                "target_symbol": relocation.target, "target_addend": relocation.addend,
                "target_identity": {key: identity.get(key) for key in
                    ("section", "symbol", "symbol_type", "resolved_value")}})
        require(len(matches) == 1, f"site relocation multiplicity: {site:#x}")
        visible = []
        for section in truth.sections:
            if "SHF_EXECINSTR" not in section.flags \
                    or not section.address <= site < section.address + section.bytes:
                continue
            raw = truth.section_bytes(section.name)
            at = site - section.address
            citizen = owner(rows, section.name, site)
            visible.append({"mapping_domain": (
                    "baseline" if section.name == BASELINE else "mapped-low-block3"),
                "section": section.name, "owner": citizen.name if citizen else None,
                "bytes_at_site": raw[at:at + 3].hex(),
                "is_JMP_to_7E8D": raw[at:at + 3] == bytes.fromhex("4c8d7e")})
        require(matches[0]["source_section"] == BASELINE
                and matches[0]["target_identity"] == {
                    "section": BASELINE, "symbol": BASELINE,
                    "symbol_type": "Section", "resolved_value": TARGET}
                and len(visible) == 2
                and [row["is_JMP_to_7E8D"] for row in visible] == [True, False],
                f"site domain evidence drift: {site:#x}")
        result.append({**matches[0], "visible_bytes_by_domain": visible,
            "verdict": "instruction and target are baseline-domain"})
    return result


def source_inventory() -> list[dict[str, Any]]:
    specs = [
        ("tools/host-lisp/c2_transitive_map_nesting_gate.py",
         "shared graph root", "direct-address-only-affected",
         ("by_value: dict[int", "matches = by_value.get(resolved")),
        ("tools/host-lisp/c2_v160_nested_map_swap.py",
         "current final gate", "downstream-affected-current-red",
         ("NEST.linked_graph(elf)", 'graph["incoming"].get(disk_body.name')),
        ("tools/host-lisp/c2_v160_nested_map_repricing.py",
         "nested-MAP price model", "downstream-address-only",
         ("NEST.linked_graph(ELF)", "NEST.paths_to_map")),
        ("tools/host-lisp/c2_v160_execution_boundary_backstop.py",
         "execution-boundary final gate", "downstream-address-only",
         ("MAP_GATE.check(elf)",)),
        ("tools/host-lisp/c2_v160_execution_boundary_repricing.py",
         "execution-boundary price model", "downstream-address-only",
         ("MAP_GATE.check(ELF)",)),
        ("tools/host-lisp/c2_v160_abort_driver_relocation.py",
         "R1 final call graph", "independent-address-only-affected",
         ("targets = [row.name for row in rows if row.value == address]",)),
        ("tools/host-lisp/c2_v160_active_frame_liveness.py",
         "active-frame final gate", "independent-address-only-affected",
         ('identity["resolved_value"] == target',
          'row.value == identity["resolved_value"]')),
        ("tools/host-lisp/c2_v160_retired_window_release_classification.py",
         "retired-window classification graph", "latent-global-address-only",
         ("by_value: dict[int", "len(by_value.get(value, ())) != 1")),
        ("tools/host-lisp/c2_v160_boot_refill_selector_bypass.py",
         "absolute-transfer scanner", "latent-address-only-target-outside-map",
         ("def absolute_transfers", "raw.find(needle, start)")),
    ]
    result = []
    for name, consumer, classification, tokens in specs:
        raw = subprocess.run(["git", "show", f"{SEALED_SOURCE_COMMIT}:{name}"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
        text = raw.decode("utf-8")
        require(all(token in text for token in tokens),
                f"address-only inventory evidence drift: {name}")
        result.append({"path": name, "source_commit": SEALED_SOURCE_COMMIT,
            "source_sha256": sha(raw), "consumer": consumer,
            "classification": classification, "evidence_tokens": list(tokens),
            "required_identity": "(section/mapping-domain, address)"})
    return result


def derive() -> dict[str, Any]:
    red = load(FINAL_RED); partial = load(PARTIAL)
    nested = load(NESTED_RECEIPT)["nested_MAP_swap"]["mapped_population"]
    abi = load(ABI)
    require(red["status"] ==
                "FINAL RED: V1.6 SELECTOR BYPASS ADAPTER REPLACEMENT STOPS"
            and red["error"]["message"] ==
                "mapped disk body has a direct or missing foreign caller"
            and partial["status"] ==
                "PASS: V1.6 SELECTOR BYPASS ADAPTER FINAL WORLD GREEN"
            and nested["violations"] == [] and nested["tenant_count"] == 7
            and abi["status"] == "passed-all-assembler-leaf-abi-contracts"
            and abi["contractual_mapped_far_exit_preservation"]["model"][
                "inner_exits"] == 8,
            "domain attribution predecessor/standing-gate drift")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    baseline = truth.section(BASELINE)
    service = truth.section(MAPPED[0]); diagnostic = truth.section(MAPPED[1])
    require((baseline.address, baseline.bytes) == (0x2023, 37755)
            and (service.address, service.bytes) == (0x78B2, 1488)
            and (diagnostic.address, diagnostic.bytes) == (0x7E8D, 324)
            and truth.symbol("__lisp65_c2_mapped_far_service_load_start").value
                == 0x2B8B2
            and truth.symbol("__lisp65_c2_mapped_diagnostic_load_start").value
                == 0x2BE8D,
            "overlapping linked-domain geometry drift")

    graph = domain_graph(truth)
    target_id = ".text::vm_native_call"
    incoming = sorted(graph["incoming"][target_id], key=lambda row: row["address"])
    require([(row["source_identity"], row["address"]) for row in incoming] == [
        (".text::vm_callprim", 0x725E),
        (".text::eval_vm_native_apply_checked", 0x8D50)],
        "baseline caller population drift")
    mapped_tenants = sorted(
        f"{row.section}::{row.name}" for row in functions(truth)
        if row.section in MAPPED)
    mapped_paths = [{"root": root, "path": path}
                    for root in mapped_tenants
                    if (path := shortest_path(graph["edges"], root, target_id))]
    require(len(mapped_tenants) == 7 and mapped_paths == [],
            "non-baseline path reaches vm_native_call")

    sites = site_rows(truth)
    legacy = []
    for row in truth.relocations:
        if row.offset - 1 not in SITES:
            continue
        identity = truth.relocation_target_identity(row)
        legacy.append({"site": row.offset - 1,
            "legacy_key": identity["resolved_value"],
            "legacy_selected_symbol": "disk_chain_to_scratch_far",
            "domain_key": [identity["section"], identity["resolved_value"]],
            "domain_selected_owner": "vm_native_call"})

    return {"format": FORMAT, "recorded_on": "2026-08-24", "status": STATUS,
        "authority": authority(), "inputs": {"Final_Red": bind(FINAL_RED),
            "partial_receipt": bind(PARTIAL), "candidate_ELF": bind(ELF),
            "nested_MAP_gate": bind(NESTED_RECEIPT), "ABI_exit_gate": bind(ABI)},
        "overlapping_domains": {
            "baseline": {"section": BASELINE, "VMA": [baseline.address,
                baseline.address + baseline.bytes]},
            "mapped_low_block3": {"sections": list(MAPPED),
                "physical_window": [0x2A000, 0x2C000],
                "service_VMA": [service.address, service.address + service.bytes],
                "diagnostic_VMA": [diagnostic.address,
                                   diagnostic.address + diagnostic.bytes]},
            "ambiguous_numeric_target": TARGET},
        "site_evidence": sites,
        "path_evidence": {"domain_graph_edges": sum(
                len(rows) for rows in graph["edges"].values()),
            "vm_native_call_incoming": incoming,
            "mapped_tenant_count": len(mapped_tenants),
            "mapped_tenants": mapped_tenants,
            "mapped_paths_to_vm_native_call": mapped_paths,
            "every_exit_unmap": {"nested_violations": nested["violations"],
                "contractual_service_inner_exits": 8,
                "ABI_status": abi["status"]},
            "verdict": "baseline mapping dominates both executable jump sites"},
        "legacy_vs_domain_identity": legacy,
        "gate_inventory": source_inventory(),
        "decision": {"branch": "gate-misclassification",
            "product_finding": False,
            "successor_rule": "key every MAP-range edge by (section/domain,address)",
            "card_may_resume_self_dispositionally": True},
        "accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}}


def check(value: dict[str, Any]) -> None:
    require(value["status"] == STATUS
            and len(value["site_evidence"]) == 2
            and all(row["verdict"] ==
                    "instruction and target are baseline-domain"
                    for row in value["site_evidence"])
            and value["path_evidence"]["mapped_paths_to_vm_native_call"] == []
            and value["decision"] == {"branch": "gate-misclassification",
                "product_finding": False,
                "successor_rule":
                    "key every MAP-range edge by (section/domain,address)",
                "card_may_resume_self_dispositionally": True}
            and len(value["gate_inventory"]) == 9,
            "domain attribution receipt drift")


def main() -> int:
    value = derive(); check(value)
    OUT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print("v1.6 MAP-domain alias attribution: PASS verdict=gate-misclassification "
          "sites=2 mapped-paths=0 inventory=9")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, subprocess.CalledProcessError,
            json.JSONDecodeError, KeyError) as error:
        print(f"v1.6 MAP-domain alias attribution: FAIL: {error}", file=sys.stderr)
        raise SystemExit(2)
