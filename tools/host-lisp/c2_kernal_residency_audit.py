#!/usr/bin/env python3
"""Verify the read-only C2 KERNAL-residency audit against product bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-kernal-residency-audit.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2-kernal-residency-audit-receipt.json"
)
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
NM = ROOT / "tools/llvm-mos/bin/llvm-nm"


class AuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def binding(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"regular file required: {path}")
    data = path.read_bytes()
    return {"path": rel(path), "bytes": len(data), "sha256": sha(data)}


def command(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True, encoding="utf-8")


def validate_vector_counts(
    calls: dict[str, list[str]], expected: dict[str, dict[str, Any]]
) -> None:
    require(set(calls) == set(expected),
            f"unexpected KERNAL vector set: actual={sorted(calls)} expected={sorted(expected)}")
    for address, row in expected.items():
        require(len(calls[address]) == row["count"],
                f"KERNAL vector count drift at ${address}: {len(calls[address])}")


def collect() -> dict[str, Any]:
    contract = load(CONTRACT)
    require(contract.get("status") == "read-only-audit", "audit contract status drift")
    reference = ROOT / contract["reference"]["path"]
    require(binding(reference)["sha256"] == contract["reference"]["sha256"],
            "chipset reference SHA drift")
    pdf_text = command("pdftotext", "-layout", str(reference), "-")
    for phrase in (
        "The MAP register overrides all other banking mechanisms.",
        "which of the eight 8KB regions of the 16-bit address space $0000 – $FFFF",
        "8MB ATTIC RAM",
        "ROME Map C65 ROM $E000",
        "KEYQUEUE 1 = Typing event queue is non-empty.",
        "PETSCIIKEY Top of typing event queue as PETSCII.",
    ):
        require(phrase in pdf_text, f"reference fact missing: {phrase}")

    elf = ROOT / contract["product_elf"]
    disassembly = command(str(OBJDUMP), "-d", str(elf)).lower()
    symbols = command(str(NM), "-n", str(elf)).lower()
    calls: dict[str, list[str]] = {}
    for line in disassembly.splitlines():
        match = re.search(r"\b(?:jsr|jmp)\s+\$([0-9a-f]{4})\b", line)
        if match and 0xFF80 <= int(match.group(1), 16) <= 0xFFFF:
            calls.setdefault(match.group(1), []).append(line.strip())
    expected = contract["expected_active_vectors"]
    validate_vector_counts(calls, expected)
    require("00003352 t lisp_poll" in symbols, "lisp_poll symbol address drift")
    poll = command(str(OBJDUMP), "-d", "--disassemble-symbols=lisp_poll", str(elf)).lower()
    require(re.search(r"\b(?:lda|ldx|ldy)\s+\$91\b", poll) is not None,
            "lisp_poll no longer reads STKEY $91")

    passive = []
    for row in contract["expected_passive_dependencies"]:
        source = ROOT / row["source"]
        text = source.read_text(encoding="utf-8")
        require(row["needle"] in text, f"passive dependency drift: {row['source']}")
        passive.append({**row, "binding": binding(source)})

    repl = (ROOT / "src/repl.c").read_text(encoding="utf-8")
    io = (ROOT / "src/io.c").read_text(encoding="utf-8")
    interrupt = (ROOT / "src/interrupt.c").read_text(encoding="utf-8")
    workbench = (ROOT / "config/workbench.mk").read_text(encoding="utf-8")
    require("-DLISP65_SCREEN_DRIVER" in workbench, "native screen driver absent")
    require("#ifdef LISP65_SCREEN_DRIVER" in repl and "scr_init()" in repl,
            "REPL screen-driver path absent")
    require("#elif defined(__C64__) || defined(__CBM__)" in io,
            "CBM KERNAL file branch boundary drift")
    require("0x91 == 0x7F" in interrupt, "STKEY contract comment drift")
    require(not re.search(r"\b(0314|0318|fffa|fffe)\b", disassembly),
            "current product unexpectedly owns an IRQ/NMI vector")

    return {
        "format": "lisp65-c2-kernal-residency-audit-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-19",
        "status": "passed-read-only-input-to-c2.1-layout-decision",
        "claim_limit": (
            "This receipt inventories the current Workbench ELF and binds official "
            "memory/keyboard reference facts. It does not authorize KERNAL unmapping, "
            "claim an IRQ replacement, or change product bytes."
        ),
        "bindings": {
            "verifier": binding(ROOT / "tools/host-lisp/c2_kernal_residency_audit.py"),
            "contract": binding(CONTRACT),
            "reference": binding(reference),
            "product_elf": binding(elf),
            "workbench_profile": binding(ROOT / "config/workbench.mk"),
            "repl": binding(ROOT / "src/repl.c"),
            "vm": binding(ROOT / "src/vm.c"),
            "interrupt": binding(ROOT / "src/interrupt.c"),
            "io": binding(ROOT / "src/io.c"),
        },
        "active_kernal_vectors": {
            address: {
                "name": expected[address]["name"],
                "count": len(lines),
                "owner": expected[address]["owner"],
                "disassembly": lines,
            }
            for address, lines in sorted(calls.items())
        },
        "passive_dependencies": passive,
        "owned_without_kernal": {
            "screen_after_startup": True,
            "mega65_disk_io": True,
            "latency_probe_reads_direct_hardware_register": "$D7FA",
        },
        "not_owned_today": {
            "keyboard_event_source": "KERNAL GETIN",
            "run_stop_state": "KERNAL IRQ-maintained STKEY $91",
            "irq_handler": "platform KERNAL",
            "nmi_handler": "platform KERNAL/Freezer contract",
        },
        "exact_relief": {
            "cpu_window": "0xe000..0xffff",
            "bytes": 8192,
            "currency": "16-bit CPU address space",
            "bank0_bytes": 0,
            "ext_bytes": 0,
            "attic_bytes": 0,
        },
        "required_before_unmap": [
            "typed $D60A/$D619 event-queue driver replaces every GETIN path",
            "RUN/STOP abort is re-sourced from the typed event or matrix path",
            "owned IRQ and NMI vectors remain reachable while ROM is unmapped",
            "frame/timing source is shown independent of KERNAL service",
            "Freezer return restores or re-establishes the C2 map fail-closed",
            "cold boot and platform reset retain their existing firmware path",
            "one real-link capacity receipt proves the unmap funds the intended C2 slice",
        ],
        "decision": (
            "KERNAL unmapping is a viable C2.1 address-space candidate, not a current "
            "implementation authorization. The natural cut is typed-event input plus "
            "owned interrupt state plus post-boot unmap in one separately reviewed block."
        ),
    }


def write() -> dict[str, Any]:
    result = collect()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def check() -> dict[str, Any]:
    result = collect()
    require(RECEIPT.is_file(), "KERNAL audit receipt missing")
    recorded = load(RECEIPT)
    require(recorded == result, "KERNAL audit receipt drift; regenerate with --write")
    return result


def selftest() -> None:
    baseline = collect()
    contract = load(CONTRACT)
    bad = json.loads(json.dumps(contract))
    bad["expected_active_vectors"]["ffe4"]["count"] += 1
    calls = {
        address: row["disassembly"]
        for address, row in baseline["active_kernal_vectors"].items()
    }
    rejected = False
    try:
        validate_vector_counts(calls, bad["expected_active_vectors"])
    except AuditError:
        rejected = True
    require(rejected and baseline["exact_relief"]["bytes"] == 8192,
            "mutated vector count was not rejected")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        print("c2-kernal-residency-audit: SELFTEST PASS mutations=1")
        return 0
    result = write() if args.write else check()
    vectors = result["active_kernal_vectors"]
    print(
        "c2-kernal-residency-audit: PASS "
        f"CHROUT={vectors['ffd2']['count']} GETIN={vectors['ffe4']['count']} "
        "passive=STKEY-$91 relief=8192-address-bytes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
