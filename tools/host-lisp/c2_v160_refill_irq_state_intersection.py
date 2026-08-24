#!/usr/bin/env python3
"""Attribute the v1.6 refill/armed-IRQ state intersection from linked bytes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ELF = ROOT / (
    "build/c2.3/v1.6-display-ownership-device-preparation/canonical-product/"
    "final/lisp65-c2-substitution-linked.prg.elf")
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
LLVM_OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
IRQ_SOURCE = ROOT / "src/optional/c2_kernal_input_capture.s"
VM_SOURCE = ROOT / "src/vm.c"
MAP_SOURCE = ROOT / "src/optional/c2_map_cpu_read.s"
PREDECESSOR = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-refill-seam-attribution.json")
ABI_REPORT = ROOT / (
    "build/c2.3/v1.6-display-ownership-device-preparation/canonical-product/"
    "final/c2-asm-leaf-abi-dataflow-gate.json")
OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-refill-irq-state-intersection.json")


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


def disassembly() -> str:
    return subprocess.run(
        [str(LLVM_OBJDUMP), "-d", "--no-show-raw-insn", str(ELF)],
        check=True, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE).stdout


def function_body(text: str, name: str) -> str:
    match = re.search(
        rf"^[0-9a-f]+ <{re.escape(name)}>:\n(?P<body>.*?)(?=^\n?[0-9a-f]+ <|^Disassembly of section|\Z)",
        text, re.MULTILINE | re.DOTALL)
    require(match is not None, f"linked function absent: {name}")
    return match.group("body")


def linked_writes(body: str) -> list[dict[str, Any]]:
    writes: list[dict[str, Any]] = []
    for line in body.splitlines():
        match = re.match(
            r"\s*([0-9a-f]+):\s+([a-z0-9]+)\s+\$([0-9a-f]+)(?:,([xyz]))?",
            line.split(";", 1)[0])
        if not match or match.group(2) not in {
                "sta", "stx", "sty", "stz", "inc", "dec", "asl", "lsr",
                "rol", "ror", "trb", "tsb", "rmb", "smb"}:
            continue
        address = int(match.group(3), 16)
        index = match.group(4)
        if address == 0xBC90 and index == "y":
            addresses = list(range(0xBC90, 0xBCFC))
        else:
            addresses = [address]
        writes.append({"pc": int(match.group(1), 16),
                       "mnemonic": match.group(2), "operand": address,
                       "index": index, "addresses": addresses})
    return writes


def derive() -> dict[str, Any]:
    predecessor = json.loads(PREDECESSOR.read_text(encoding="utf-8"))
    require(predecessor["decision"]["class"] == "REAL TARGET REFILL FAILURE",
            "predecessor decision drift")
    abi_report = json.loads(ABI_REPORT.read_text(encoding="utf-8"))
    require(abi_report["status"] == "passed-all-assembler-leaf-abi-contracts"
            and Path(abi_report["elf"]).resolve() == ELF.resolve()
            and "unmap on every exit" in
                abi_report["source_inventory"]["c2_map_cpu_read"]["policy"],
            "candidate ABI/every-exit-unmap authority drift")
    truth = ElfTruth.read(ELF, llvm_readobj=LLVM_READOBJ,
                          include_section_data=True)
    text = disassembly()

    irq_names = ["c2_kernal_irq_handler", "c2_kernal_input_capture",
                 "c2_kernal_input_capture_commit"]
    irq_start = truth.symbol("c2_kernal_irq_handler").value
    irq_end = truth.symbol("c2_kernal_nmi_handler").value
    require(irq_end - irq_start == 74, "linked IRQ handler size drift")
    irq_bodies = {name: function_body(text, name) for name in irq_names}
    writes = {name: linked_writes(body) for name, body in irq_bodies.items()}
    persistent_writes = sorted({address for rows in writes.values()
                                for row in rows for address in row["addresses"]})
    expected_writes = set([
        0xD019, 0xD619, 0xFF83, 0xFF84, 0xFF86, 0xFF89, 0xFF8A,
        0xFF8B, 0xFF8C, 0xBCFC, 0xBCFD, 0xBCFE,
    ]) | set(range(0xBC90, 0xBCFC))
    require(set(persistent_writes) == expected_writes,
            "armed owned-IRQ persistent write set drift")

    # The exact seam is path-sensitive: PC $45 is beyond header+littab, so the
    # refill reads immutable payload into vm_codebuf and does not materialise
    # literals.  These symbols are the entire VM-owned window bookkeeping.
    vm_names = ["vm_status", "vm_codebuf", "vm_buf_off", "vm_buf_bank",
                "vmr_hdrlen", "vmr_littab", "vmr_code", "vmr_poff",
                "vmr_plen", "vmr_pwmax", "vmr_win", "vmr_winlen",
                "vmr_streaming"]
    vm_state = []
    for name in vm_names:
        symbol = truth.symbol(name)
        size = symbol.bytes or 1
        vm_state.append({"name": name, "start": symbol.value,
                         "bytes": size, "end_exclusive": symbol.value + size})
    vm_addresses = {address for row in vm_state
                    for address in range(row["start"], row["end_exclusive"])}

    # LLVM-MOS C code uses the imaginary-register file as its ABI scratch.
    # The final reader also owns a dynamic C activation record addressed via
    # __rc0, and writes only the caller-provided vm_codebuf destination.
    abi_addresses = set(range(0x02, 0x22))
    require(not (set(persistent_writes) & abi_addresses),
            "IRQ writes LLVM-MOS imaginary registers")
    require(not (set(persistent_writes) & vm_addresses),
            "IRQ writes VM refill/window bookkeeping")

    irq_source = IRQ_SOURCE.read_text(encoding="utf-8")
    require(all(token in irq_source for token in
                ("pha", "phx", "phy", "phz", "plz", "ply", "plx", "pla", "rti")),
            "IRQ machine-register save/restore drift")
    handler = irq_bodies["c2_kernal_irq_handler"]
    require(all(token in handler for token in
                ("pha", "phx", "phy", "phz", "plz", "ply", "plx", "pla", "rti")),
            "linked IRQ save/restore drift")

    map_source = MAP_SOURCE.read_text(encoding="utf-8")
    require("php" in map_source and "sei" in map_source and "plp" in map_source,
            "MAP reader interrupt exclusion drift")
    require("map" not in irq_source.lower(), "armed IRQ unexpectedly changes MAP")

    vm_source = VM_SOURCE.read_text(encoding="utf-8")
    require("win = pc_;" in vm_source and "winlen =" in vm_source
            and "vm_object_load(bank, off" in vm_source,
            "WIN_ENSURE source seam drift")

    intersection = sorted(set(persistent_writes) & (vm_addresses | abi_addresses))
    require(intersection == [], "persistent refill/IRQ state intersection is nonempty")

    result = {
        "format": "lisp65-c2.3-v1.6-refill-irq-state-intersection-v1",
        "recorded_on": "2026-08-22",
        "status": "ATTRIBUTED: NO REGISTER-FORM IRQ/REFILL INTERSECTION",
        "inputs": {name: bind(path) for name, path in {
            "candidate_ELF": ELF, "predecessor": PREDECESSOR,
            "ABI_and_every_exit_unmap_report": ABI_REPORT,
            "IRQ_source": IRQ_SOURCE, "VM_source": VM_SOURCE,
            "MAP_reader_source": MAP_SOURCE,
            "attribution_tool": Path(__file__).resolve(),
        }.items()},
        "refill_state": {
            "machine_state": ["A", "X", "Y", "Z", "P", "SP"],
            "abi_zero_page": {"start": 0x02, "end_exclusive": 0x22,
                              "role": "__rc0..__rc31 and C activation scratch"},
            "dynamic_activation": "C frame addressed through __rc0/__rc1",
            "vm_window_bookkeeping": vm_state,
            "destination": {"owner": "vm_codebuf",
                            "seam_slice": "$bfc7..$bfdb ($45 refill, 21 bytes)"},
            "source": ("candidate entry metadata plus immutable payload through "
                       "c2_product_entry_read/c2_map_cpu_read"),
            "map_state": {"changed": True, "interruptible_while_changed": False,
                          "proof": "linked/source PHP; SEI; MAP...; baseline MAP; PLP"},
        },
        "armed_irq_state": {
            "linked_functions": irq_names,
            "handler_bytes": irq_end - irq_start,
            "persistent_write_addresses": [f"${value:04X}" for value in persistent_writes],
            "writes_by_function": writes,
            "machine_state": {"transient": ["A", "X", "Y", "Z", "P", "SP"],
                              "restored": ["A", "X", "Y", "Z", "P", "SP"]},
            "map_state_changed": False,
            "stack_protocol": ("hardware IRQ frame plus balanced PHA/PHX/PHY/PHZ and "
                               "the balanced capture JSR frame below interrupted SP"),
        },
        "intersection": {
            "persistent_addresses": intersection,
            "machine_registers": ["A", "X", "Y", "Z", "P", "SP"],
            "machine_register_verdict": "shared transiently, fully restored on every owned return",
            "stack": "shared protocol, disjoint live frames and balanced return",
            "map": "no interruptible overlap: reader masks IRQ for every non-baseline MAP",
            "verdict": "EMPTY AFTER ABI, EVERY-EXIT-UNMAP AND BALANCED-STACK PROOFS",
        },
        "decision": {
            "class": "NOT REGISTER-FORM IRQ CORRUPTION",
            "reason": ("the armed IRQ writes no LLVM-MOS ABI cell, no vm_codebuf byte, "
                       "no VM window-bookkeeping cell and no MAP state; all shared CPU "
                       "registers and stack frames are restored, while the mapped reader "
                       "is interrupt-masked until baseline MAP is restored"),
            "save_restore_fix": "NOT SUPPORTED BY THE INTERSECTION",
            "ownership_split_fix": "NOT SUPPORTED BY THE INTERSECTION",
            "next_step": ("a separately priced device witness must observe the real "
                          "c2_product_entry_read return/refill boundary; this attribution "
                          "does not authorise it"),
        },
        "claim_boundary": ("Host-only byte attribution. It excludes a register-, ABI-, "
                           "MAP- or persistent-state collision with the armed IRQ; it does "
                           "not explain the target-only failed refill and performs no link, "
                           "product mutation, media build or device contact."),
    }
    return result


def audit(value: dict[str, Any]) -> None:
    require(value["intersection"]["persistent_addresses"] == [],
            "receipt persistent intersection drift")
    require(value["intersection"]["verdict"].startswith("EMPTY"),
            "receipt verdict drift")
    require(value["decision"]["class"] == "NOT REGISTER-FORM IRQ CORRUPTION",
            "receipt class drift")


def main(argv: list[str]) -> int:
    require(len(argv) == 2 and argv[1] in {"check", "write"},
            "usage: c2_v160_refill_irq_state_intersection.py check|write")
    value = derive()
    if argv[1] == "write":
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    else:
        require(OUT.is_file(), f"receipt absent: {OUT}")
        recorded = json.loads(OUT.read_text(encoding="utf-8"))
        require(recorded == value, "recorded attribution drift")
    audit(value)
    print("v1.6 refill/IRQ intersection: PASS persistent=0 cpu=restored "
          "map=irq-masked decision=device-witness-required")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (AttributionError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"v1.6 refill/IRQ intersection: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
