#!/usr/bin/env python3
"""Prove handwritten 45GS02 code obeys both directions of the Z contract.

The 65CE02/45GS02 opcode named STZ stores the Z register.  It is compatible
with the 65C02 "store zero" spelling only while Z is actually zero.  This gate
derives its inventory from every handwritten ``.s``/``.S`` source under
``src`` and ``scripts``; a new STZ therefore enters the proof automatically.

llvm-mos also requires Z=0 at every C boundary.  Consequently every regular
handwritten entry must return or tail-call with Z=0 on every path.  Interrupt
entries are the sole different class: they must return or chain with the
arbitrary interrupted Z value preserved.  The path proof follows local JSR
subroutines, checks every external call/tail edge, and is mutation-pinned at
every return edge.
"""

from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOTS = (ROOT / "src", ROOT / "scripts")
INLINE_POLICIES = {
    ROOT / "src/c2_kernal_runtime.c": {
        "site": "stz $d702",
        "proof": "owned C world begins with SEI / LDZ #0 before c2k_copy",
        "required": (
            '__asm__ volatile("sei\\n\\tldz #0"',
            "c2k_copy(C2_KERNAL_WINDOW_STAGE_PHYSICAL,",
        ),
    },
    ROOT / "scripts/c2-lite-chipram-proof-main.c": {
        "site": "stz $d702",
        "proof": "non-product main calls install_owned_window before DMA tests",
        "required": (
            '__asm__ volatile("sei\\n\\tldz #0"',
            "install_owned_window();",
        ),
    },
}
ZERO = "zero"
NONZERO = "nonzero"
UNKNOWN = "unknown"
PRESERVED = "entry-Z-preserved"


def _interrupt_entry(name: str) -> bool:
    """Interrupt shims return to a machine frame, not to compiled C."""
    lowered = name.lower()
    return "irq" in lowered or "nmi" in lowered


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def _binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def source_paths() -> list[Path]:
    paths: set[Path] = set()
    for directory in SOURCE_ROOTS:
        for suffix in ("*.s", "*.S"):
            paths.update(directory.rglob(suffix))
    return sorted(paths)


def inline_source_paths() -> list[Path]:
    paths: set[Path] = set()
    for directory in SOURCE_ROOTS:
        paths.update(directory.rglob("*.c"))
    return sorted(paths)


def _code(line: str) -> str:
    return line.split(";", 1)[0].strip()


def _join(before: str | None, after: str) -> str:
    if before is None:
        return after
    return before if before == after else UNKNOWN


def _immediate_zero(operand: str) -> bool:
    value = operand.strip().lower()
    if not value.startswith("#"):
        return False
    token = value[1:].strip()
    try:
        if token.startswith("$"):
            return int(token[1:], 16) == 0
        return int(token, 0) == 0
    except ValueError:
        return False


def _immediate_nonzero(operand: str) -> bool:
    value = operand.strip().lower()
    if not value.startswith("#"):
        return False
    token = value[1:].strip()
    try:
        if token.startswith("$"):
            return int(token[1:], 16) != 0
        return int(token, 0) != 0
    except ValueError:
        return False


def _transfer(
        state: str, opcode: str, operand: str, *,
        interrupt_entry: bool = False) -> str:
    if opcode == "ldz":
        if _immediate_zero(operand):
            return ZERO
        if _immediate_nonzero(operand):
            return NONZERO
        return UNKNOWN
    if opcode in {"inz", "dez"}:
        if state == ZERO:
            return NONZERO
        return UNKNOWN
    if opcode == "plz":
        return PRESERVED if interrupt_entry else UNKNOWN
    if opcode == "taz":
        return UNKNOWN
    # Every regular handwritten call edge is an llvm-mos ABI boundary.  Its
    # callee must return Z=0 and is independently covered by the ABI gate.
    if opcode == "jsr":
        return ZERO
    return state


def _parse(path: Path, text: str) -> dict[str, Any]:
    typed = set(re.findall(
        r"^\s*\.type\s+([^,\s]+)\s*,\s*[@%]function\s*$",
        text, re.MULTILINE))
    instructions: list[dict[str, Any]] = []
    labels: dict[str, int] = {}
    pending_labels: list[str] = []
    for line_number, raw in enumerate(text.splitlines(), 1):
        code = _code(raw)
        if not code:
            continue
        label_match = re.match(r"^([A-Za-z_.$][\w.$]*):(?:\s*(.*))?$", code)
        if label_match:
            pending_labels.append(label_match.group(1))
            code = (label_match.group(2) or "").strip()
            if not code:
                continue
        if code.startswith("."):
            continue
        tokens = code.split(None, 1)
        opcode = tokens[0].lower()
        operand = tokens[1].strip() if len(tokens) == 2 else ""
        index = len(instructions)
        for label in pending_labels:
            require(label not in labels, f"duplicate label {label} in {path}")
            labels[label] = index
        pending_labels.clear()
        instructions.append({
            "opcode": opcode,
            "operand": operand,
            "line": line_number,
            "text": raw.strip(),
        })
    for label in pending_labels:
        labels[label] = len(instructions)
    entries = {
        label: labels[label] for label in typed if label in labels
    }
    return {
        "instructions": instructions,
        "labels": labels,
        "entries": entries,
    }


def _successors(index: int, instructions: list[dict[str, Any]],
                labels: dict[str, int]) -> list[int]:
    row = instructions[index]
    opcode = row["opcode"]
    operand = row["operand"].split(",", 1)[0].strip()
    fallthrough = index + 1
    if opcode in {"rts", "rti", "brk"}:
        return []
    if opcode in {"bra", "jmp"}:
        return [labels[operand]] if operand in labels else []
    conditional = (
        opcode.startswith("b")
        and opcode not in {"bit", "brk", "bra"}
    )
    result: list[int] = []
    if fallthrough < len(instructions):
        result.append(fallthrough)
    if conditional and operand in labels:
        result.append(labels[operand])
    return result


def _target(operand: str) -> str:
    return operand.split(",", 1)[0].strip()


def _entry_exit_proof(
        path: Path, name: str, start: int,
        instructions: list[dict[str, Any]],
        labels: dict[str, int]) -> dict[str, Any]:
    """Explore one assembly entry, including local JSR/RTS call frames."""
    is_interrupt = _interrupt_entry(name)
    initial = PRESERVED if is_interrupt else ZERO
    queue: deque[tuple[int, tuple[int, ...], str]] = deque(
        [(start, (), initial)])
    states: dict[tuple[int, tuple[int, ...]], str] = {}
    exits: dict[tuple[int, str, str], dict[str, Any]] = {}
    external_calls: dict[tuple[int, str], dict[str, Any]] = {}
    max_call_depth = 0

    def enqueue(index: int, stack: tuple[int, ...], state: str) -> None:
        require(
            len(stack) <= 16,
            f"local ASM call depth exceeds 16 in {path}:{name}")
        key = (index, stack)
        merged = _join(states.get(key), state)
        if states.get(key) != merged:
            states[key] = merged
            queue.append((index, stack, merged))

    while queue:
        index, stack, state = queue.popleft()
        if index >= len(instructions):
            raise GateError(
                f"ASM entry falls out of source at {path}:{name}")
        row = instructions[index]
        opcode = row["opcode"]
        operand = row["operand"]
        target = _target(operand)
        fallthrough = index + 1
        max_call_depth = max(max_call_depth, len(stack))

        if opcode == "jsr":
            if target in labels:
                require(
                    fallthrough < len(instructions),
                    f"local JSR has no successor at {path}:{row['line']}")
                enqueue(labels[target], stack + (fallthrough,), state)
            else:
                require(
                    state == ZERO,
                    f"ASM->external call lacks Z=0 at "
                    f"{path}:{row['line']} ({name} -> {target}; Z={state})")
                external_calls[(row["line"], target)] = {
                    "line": row["line"],
                    "kind": "jsr",
                    "target": target,
                    "abstract_Z_at_edge": state,
                }
                if fallthrough < len(instructions):
                    enqueue(fallthrough, stack, ZERO)
            continue

        if opcode == "rts":
            if stack:
                enqueue(stack[-1], stack[:-1], state)
                continue
            require(
                not is_interrupt and state == ZERO,
                f"ASM return violates Z discipline at "
                f"{path}:{row['line']} ({name}; Z={state})")
            exits[(row["line"], "rts", "")] = {
                "line": row["line"],
                "kind": "rts",
                "target": None,
                "abstract_Z_at_edge": state,
            }
            continue

        if opcode == "rti":
            require(
                is_interrupt and not stack and state == PRESERVED,
                f"interrupt return does not preserve entry Z at "
                f"{path}:{row['line']} ({name}; Z={state})")
            exits[(row["line"], "rti", "")] = {
                "line": row["line"],
                "kind": "rti",
                "target": None,
                "abstract_Z_at_edge": state,
            }
            continue

        if opcode == "brk":
            continue

        if opcode == "jmp":
            if target in labels:
                enqueue(labels[target], stack, state)
                continue
            if target == "c2_kernal_fail_closed":
                exits[(row["line"], "nonreturning-jmp", target)] = {
                    "line": row["line"],
                    "kind": "nonreturning-jmp",
                    "target": target,
                    "abstract_Z_at_edge": state,
                }
                continue
            expected = PRESERVED if is_interrupt else ZERO
            require(
                state == expected,
                f"ASM tail edge violates Z discipline at "
                f"{path}:{row['line']} ({name} -> {target}; "
                f"Z={state}, expected={expected})")
            if stack and not is_interrupt:
                # A local helper can tail-call an external ABI function; its
                # RTS consumes the original local JSR return address.
                enqueue(stack[-1], stack[:-1], ZERO)
            else:
                exits[(row["line"], "tail-jmp", target)] = {
                    "line": row["line"],
                    "kind": "tail-jmp",
                    "target": target,
                    "abstract_Z_at_edge": state,
                }
            continue

        after = _transfer(
            state, opcode, operand, interrupt_entry=is_interrupt)
        if opcode == "bra":
            require(
                target in labels,
                f"unresolved BRA target at {path}:{row['line']}: {target}")
            enqueue(labels[target], stack, after)
            continue
        conditional = (
            opcode.startswith("b")
            and opcode not in {"bit", "brk", "bra"}
        )
        if conditional:
            if fallthrough < len(instructions):
                enqueue(fallthrough, stack, after)
            if target in labels:
                enqueue(labels[target], stack, after)
            continue
        if fallthrough < len(instructions):
            enqueue(fallthrough, stack, after)

    if not exits:
        return {
            "status": "passed-nonreturning-entry",
            "entry_Z": initial,
            "exit_count": 0,
            "exits": [],
            "external_call_count": len(external_calls),
            "external_calls": sorted(
                external_calls.values(),
                key=lambda row: (row["line"], row["target"])),
            "max_local_call_depth": max_call_depth,
        }
    returning = [
        row for row in exits.values()
        if row["kind"] != "nonreturning-jmp"
    ]
    status = (
        "passed-interrupt-entry-Z-preserved"
        if is_interrupt
        else ("passed-nonreturning-entry"
              if not returning
              else "passed-all-return-and-tail-paths-Z-zero")
    )
    return {
        "status": status,
        "entry_Z": initial,
        "exit_count": len(exits),
        "exits": sorted(
            exits.values(),
            key=lambda row: (row["line"], row["kind"],
                             str(row["target"]))),
        "external_call_count": len(external_calls),
        "external_calls": sorted(
            external_calls.values(),
            key=lambda row: (row["line"], row["target"])),
        "max_local_call_depth": max_call_depth,
    }


def audit_text(path: Path, text: str) -> dict[str, Any]:
    parsed = _parse(path, text)
    instructions = parsed["instructions"]
    labels = parsed["labels"]
    entries = parsed["entries"]
    stz_indexes = [
        index for index, row in enumerate(instructions)
        if row["opcode"] == "stz"
    ]
    require(
        entries or not stz_indexes,
        f"STZ source has no typed function entry: {path}")

    states: dict[int, str] = {}
    queue: deque[int] = deque()
    for name, index in entries.items():
        if index >= len(instructions):
            continue
        entry_state = PRESERVED if _interrupt_entry(name) else ZERO
        merged = _join(states.get(index), entry_state)
        if states.get(index) != merged:
            states[index] = merged
            queue.append(index)
    while queue:
        index = queue.popleft()
        row = instructions[index]
        after = _transfer(
            states[index], row["opcode"], row["operand"])
        for successor in _successors(index, instructions, labels):
            merged = _join(states.get(successor), after)
            if states.get(successor) != merged:
                states[successor] = merged
                queue.append(successor)

    sites: list[dict[str, Any]] = []
    for index in stz_indexes:
        row = instructions[index]
        state = states.get(index)
        require(
            state is not None,
            f"unreachable/unowned STZ at {path}:{row['line']}")
        require(
            state == ZERO,
            f"STZ lacks Z=0 dominance at {path}:{row['line']} "
            f"(abstract Z={state})")
        sites.append({
            "line": row["line"],
            "operand": row["operand"],
            "abstract_Z_at_store": state,
        })
    exit_proofs = {
        name: _entry_exit_proof(
            path, name, index, instructions, labels)
        for name, index in sorted(entries.items())
        if index < len(instructions)
    }
    return {
        "sites": sites,
        "entries": len(entries),
        "entry_exit_proofs": exit_proofs,
        "exit_count": sum(
            row["exit_count"] for row in exit_proofs.values()),
    }


def audit_inline(
        texts: dict[Path, str] | None = None) -> dict[str, Any]:
    supplied = texts or {
        path: path.read_text(encoding="utf-8")
        for path in inline_source_paths()
    }
    discovered: dict[Path, list[str]] = {}
    pattern = re.compile(r"stz\s+\$[0-9a-f]+", re.IGNORECASE)
    for path, text in supplied.items():
        matches = [match.group(0).strip().lower()
                   for match in pattern.finditer(text)]
        if matches:
            discovered[path] = matches
    require(
        set(discovered) == set(INLINE_POLICIES),
        "inline-assembler STZ inventory differs from proof policies: "
        + ", ".join(path.relative_to(ROOT).as_posix()
                    for path in sorted(set(discovered) ^ set(INLINE_POLICIES))))
    rows: dict[str, Any] = {}
    for path, policy in INLINE_POLICIES.items():
        text = supplied[path]
        site = str(policy["site"]).lower()
        require(
            discovered[path] == [site],
            f"inline STZ site drift: {path}")
        require(
            all(token in text for token in policy["required"]),
            f"inline STZ Z=0 ownership proof drift: {path}")
        require(
            "inz\\n\\tstz" not in text.lower()
            and "ldz #1\\n\\tstz" not in text.lower(),
            f"inline STZ has nonzero Z immediately before store: {path}")
        rows[path.relative_to(ROOT).as_posix()] = {
            "sites": [{"operand": site[4:],
                       "abstract_Z_at_store": ZERO}],
            "proof": policy["proof"],
        }
    return {
        "files": rows,
        "site_count": sum(len(row["sites"]) for row in rows.values()),
    }


def audit(
        texts: dict[Path, str] | None = None,
        inline_texts: dict[Path, str] | None = None,
        linked_inventory: dict[str, Any] | None = None) -> dict[str, Any]:
    supplied = texts or {
        path: path.read_text(encoding="utf-8") for path in source_paths()
    }
    files: dict[str, Any] = {}
    site_count = 0
    entry_count = 0
    exit_count = 0
    for path in sorted(supplied):
        result = audit_text(path, supplied[path])
        if result["sites"] or result["entries"]:
            relative = path.relative_to(ROOT).as_posix()
            for name, proof in result["entry_exit_proofs"].items():
                if linked_inventory is not None:
                    proof["c2_lite_reachability"] = linked_inventory.get(
                        name, {
                            "status": "not-linked-by-c2-lite-profile",
                            "source": relative,
                        })["status"]
            files[relative] = result
            site_count += len(result["sites"])
            entry_count += result["entries"]
            exit_count += result["exit_count"]
    inline = audit_inline(inline_texts)
    total_sites = site_count + inline["site_count"]
    require(total_sites > 0, "no handwritten STZ sites discovered")
    value = {
        "status": (
            "passed-all-handwritten-STZ-sites-and-Z-boundaries"),
        "instruction_semantics": "45GS02 STZ stores the Z register",
        "boundary_contract": (
            "regular ASM returns and ASM-to-external edges carry Z=0; "
            "interrupt returns/chains preserve the interrupted entry Z"),
        "source_roots": [
            path.relative_to(ROOT).as_posix() for path in SOURCE_ROOTS
        ],
        "files": files,
        "assembly_entry_count": entry_count,
        "assembly_exit_count": exit_count,
        "assembly_site_count": site_count,
        "inline_assembly": inline,
        "site_count": total_sites,
        "authority": {
            "gate": _binding(Path(__file__)),
            "assembly_sources": [
                _binding(path) for path in sorted(supplied)
            ],
            "inline_policies": [
                _binding(path) for path in sorted(INLINE_POLICIES)
            ],
        },
    }
    if linked_inventory is not None:
        batch = linked_inventory.get("vm_l65m_batch_repeat")
        require(
            isinstance(batch, dict)
            and batch.get("status") == "not-linked-by-c2-lite-profile",
            "vm_l65m_batch_repeat unexpectedly entered the C2-lite closure")
        value["c2_lite_reachability"] = {
            "vm_l65m_batch_repeat": {
                "status": batch["status"],
                "source": batch["source"],
                "independent_final_ELF_evidence": True,
            },
        }
    return value


def _insert_before_line(text: str, line_number: int, instruction: str) -> str:
    lines = text.splitlines()
    lines.insert(line_number - 1, instruction)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def selftest() -> dict[str, Any]:
    texts = {
        path: path.read_text(encoding="utf-8") for path in source_paths()
    }
    inline_texts = {
        path: path.read_text(encoding="utf-8")
        for path in inline_source_paths()
    }
    baseline = audit(texts, inline_texts)
    rejected: list[str] = []
    return_edges: set[tuple[str, int, str]] = set()
    for relative, row in baseline["files"].items():
        for proof in row["entry_exit_proofs"].values():
            for edge in proof["exits"]:
                if edge["kind"] in {"rts", "rti", "tail-jmp"}:
                    return_edges.add(
                        (relative, int(edge["line"]), str(edge["kind"])))
    for relative, line, kind in sorted(return_edges):
        path = ROOT / relative
        mutated = dict(texts)
        mutated[path] = _insert_before_line(
            texts[path], line, "\tinz")
        label = f"{relative}:{line}:{kind}:inz-before-exit"
        try:
            audit(mutated, inline_texts)
        except GateError:
            rejected.append(label)
        else:
            raise GateError(
                f"ASM Z-exit mutation survived: {label}")
    for relative, row in baseline["files"].items():
        path = ROOT / relative
        for site in row["sites"]:
            for opcode in ("\tinz", "\tldz #1"):
                mutated = dict(texts)
                mutated[path] = _insert_before_line(
                    texts[path], site["line"], opcode)
                label = (
                    f"{relative}:{site['line']}:"
                    f"{opcode.strip().replace(' ', '-')}")
                try:
                    audit(mutated)
                except GateError:
                    rejected.append(label)
                else:
                    raise GateError(
                        f"STZ Z-dominance mutation survived: {label}")
    for path, policy in INLINE_POLICIES.items():
        for opcode in ("inz", "ldz #1"):
            mutated_inline = dict(inline_texts)
            mutated_inline[path] = inline_texts[path].replace(
                str(policy["site"]),
                opcode + "\\n\\t" + str(policy["site"]), 1)
            label = (
                f"{path.relative_to(ROOT).as_posix()}:inline:"
                f"{opcode.replace(' ', '-')}")
            try:
                audit(texts, mutated_inline)
            except GateError:
                rejected.append(label)
            else:
                raise GateError(
                    f"inline STZ Z-dominance mutation survived: {label}")
    stz_mutations = baseline["site_count"] * 2
    expected = stz_mutations + len(return_edges)
    require(
        len(rejected) == expected,
        f"Z-discipline mutation count drift: {len(rejected)} != {expected}")
    return {
        "status": "passed-STZ-dominance-and-Z-exit-mutations",
        "baseline_sites": baseline["site_count"],
        "baseline_entries": baseline["assembly_entry_count"],
        "baseline_exits": baseline["assembly_exit_count"],
        "exit_mutations": len(return_edges),
        "stz_mutations": stz_mutations,
        "rejected": len(rejected),
        "mutations": rejected,
        "authority": baseline["authority"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        value = selftest() if args.selftest else audit()
        if args.receipt:
            path = (
                args.receipt if args.receipt.is_absolute()
                else ROOT / args.receipt
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(value, indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0
    except (GateError, OSError, ValueError) as error:
        print(f"c2-stz-z-dominance-gate: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
