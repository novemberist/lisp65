#!/usr/bin/env python3
"""Bind the v1.2.1 DIRMISS renderer pointer-ABI attribution.

The hardware hold already proved that ``sym_name_scratch`` is intact after
``symname`` returns.  This gate joins that observation to the linked MOS ABI:
``symname`` returns its pointer in ``__rc2/__rc3``, while the L65E consumer
immediately overwrites those cells with incidental A/X values.

This is attribution only.  The convicted two-store deletion is deliberately
parked for v1.2.2 because the v1.2.1 acceptance chain is already sealed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ELF = ROOT / (
    "build/c2.2/v1.2.1-acceptance/r6/ship/proof/product/"
    "lisp65-c2-lite-product.elf")
SOURCE = ROOT / "src/l65e_bcode_ordinal.s"
SYMBOL_SOURCE = ROOT / "src/symbol.c"
HARDWARE = ROOT / (
    "build/post-promotion/link77-random-while/"
    "gc-discriminator-bundled-session/"
    "dirmiss-post-symname-receipt.json")
PLAN = ROOT / "docs/planning/v1.2.1-release-plan.md"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.1-dirmiss-renderer-attribution-receipt.json")
NM = ROOT / "tools/llvm-mos/bin/llvm-nm"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"

FORMAT = "lisp65-v1.2.1-dirmiss-renderer-attribution-v1"
EXPECTED_SCRATCH = 0xC1F6
EXPECTED_SYMNAME = 0x92F9
EXPECTED_EDGE = 0xC46F
EXPECTED_RETURN = 0xC472


class AttributionError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AttributionError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing file: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def command(args: list[str]) -> str:
    result = subprocess.run(
        args, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, f"command failed: {' '.join(args)}\n"
            f"{result.stdout[-4000:]}")
    return result.stdout


def symbol_address(nm_text: str, name: str) -> int:
    pattern = re.compile(
        rf"^([0-9a-fA-F]+)\s+\S\s+{re.escape(name)}$", re.MULTILINE)
    match = pattern.search(nm_text)
    require(match is not None, f"ELF symbol missing: {name}")
    return int(match.group(1), 16)


def function_chunk(disassembly: str, name: str) -> str:
    match = re.search(
        rf"^[0-9a-fA-F]+\s+<{re.escape(name)}>:\n"
        rf"(?P<body>.*?)(?=^\n?[0-9a-fA-F]+\s+<|\Z)",
        disassembly, re.MULTILINE | re.DOTALL)
    require(match is not None, f"disassembly function missing: {name}")
    return match.group(0)


def instruction_address(chunk: str, text: str) -> int:
    match = re.search(
        rf"^\s*([0-9a-fA-F]+):\s+{text}\s*$", chunk, re.MULTILINE)
    require(match is not None, f"instruction missing: {text}")
    return int(match.group(1), 16)


def analyze(
        *, source_text: str, symname_chunk: str, renderer_chunk: str,
        hardware: dict[str, Any], scratch_address: int,
) -> dict[str, Any]:
    require(
        hardware.get("status")
        == "renderer-consumption-attributed-symname-and-read-seam-exonerated",
        "hardware post-symname status drift")
    require(
        hardware.get("answer", {}).get("scratch_correct_after_symname") is True,
        "hardware did not exonerate symname/read seam")
    captures = hardware.get("captures")
    require(
        isinstance(captures, list) and len(captures) == 3
        and all(capture.get("matches_expected") is True
                for capture in captures),
        "three matching post-symname captures required")

    registers = hardware.get("registers", {})
    captured_a = int(registers.get("A", ""), 0)
    captured_x = int(registers.get("X", ""), 0)
    captured_pc = int(registers.get("PC", ""), 0)
    incidental_pointer = captured_a | (captured_x << 8)
    require(captured_pc == EXPECTED_RETURN, "hardware hold PC drift")
    require(
        incidental_pointer != scratch_address,
        "captured A/X accidentally equals the correct pointer")

    require(
        re.search(
            r"jsr\s+symname\s*\n\s*sta\s+__rc2\s*\n\s*stx\s+__rc3",
            source_text) is not None,
        "source no longer contains the convicted pointer overwrite")
    require(
        re.search(
            r"938d:\s+.*ldx\s+#\$f6.*\n"
            r"\s*938f:\s+.*stx\s+\$4.*\n"
            r"\s*9391:\s+.*ldx\s+#\$c1.*\n"
            r"\s*9393:\s+.*stx\s+\$5",
            symname_chunk) is not None,
        "linked symname no longer returns $C1F6 in __rc2/__rc3")
    require(
        re.search(
            r"c46f:\s+.*jsr\s+\$92f9\s+<symname>\n"
            r"\s*c472:\s+.*sta\s+\$4.*<__rc2>\n"
            r"\s*c474:\s+.*stx\s+\$5.*<__rc3>",
            renderer_chunk) is not None,
        "linked renderer overwrite edge drift")

    return {
        "scratch_correct_after_symname": True,
        "correct_pointer": f"0x{scratch_address:04x}",
        "captured_registers": {
            "A": f"0x{captured_a:02x}",
            "X": f"0x{captured_x:02x}",
            "PC": f"0x{captured_pc:04x}",
        },
        "incidental_pointer_written_by_renderer": (
            f"0x{incidental_pointer:04x}"),
        "symname_return_abi": "__rc2/__rc3",
        "convicted_edge": {
            "call": f"0x{EXPECTED_EDGE:04x}",
            "return": f"0x{EXPECTED_RETURN:04x}",
            "stores": ["sta __rc2", "stx __rc3"],
        },
        "mechanism": (
            "symname returns the correct $C1F6 pointer in __rc2/__rc3; "
            "the L65E consumer overwrites it with incidental A/X=$8FD1 "
            "before reading the name"),
    }


def mutation_checks(
        source_text: str, symname_chunk: str, renderer_chunk: str,
        hardware: dict[str, Any], scratch_address: int,
) -> dict[str, Any]:
    mutations: list[tuple[str, dict[str, Any]]] = [
        ("source-overwrite-deleted", {
            "source_text": source_text.replace(
                "\tsta\t__rc2\n\tstx\t__rc3\n", "", 1)}),
        ("linked-return-low-byte-drift", {
            "symname_chunk": re.sub(
                r"(938d:.*ldx\s+#)\$f6", r"\1$f7",
                symname_chunk, count=1)}),
        ("linked-renderer-store-drift", {
            "renderer_chunk": re.sub(
                r"(c472:.*sta\s+)\$4", r"\1$6",
                renderer_chunk, count=1)}),
        ("post-symname-scratch-not-proven", {
            "hardware": {
                **hardware,
                "answer": {
                    **hardware.get("answer", {}),
                    "scratch_correct_after_symname": False,
                },
            }}),
        ("captured-registers-alias-correct-pointer", {
            "hardware": {
                **hardware,
                "registers": {
                    **hardware.get("registers", {}),
                    "A": "0xf6",
                    "X": "0xc1",
                },
            }}),
    ]
    rejected: list[str] = []
    base = {
        "source_text": source_text,
        "symname_chunk": symname_chunk,
        "renderer_chunk": renderer_chunk,
        "hardware": hardware,
        "scratch_address": scratch_address,
    }
    for name, overrides in mutations:
        try:
            analyze(**{**base, **overrides})
        except AttributionError:
            rejected.append(name)
    require(
        len(rejected) == len(mutations),
        "attribution mutation escaped: "
        + ", ".join(name for name, _ in mutations if name not in rejected))
    return {
        "attempted": len(mutations),
        "rejected": len(rejected),
        "names": rejected,
    }


def expected_receipt() -> dict[str, Any]:
    hardware = json.loads(HARDWARE.read_text(encoding="utf-8"))
    require(isinstance(hardware, dict), "hardware receipt must be an object")
    source_text = SOURCE.read_text(encoding="utf-8")
    nm_text = command([str(NM), "-n", str(ELF)])
    disassembly = command(
        [str(OBJDUMP), "-d", "--no-show-raw-insn", str(ELF)])

    scratch_address = symbol_address(nm_text, "sym_name_scratch")
    symname_address = symbol_address(nm_text, "symname")
    renderer_address = symbol_address(
        nm_text, "lisp65_error_overlay_entry")
    require(scratch_address == EXPECTED_SCRATCH, "scratch address drift")
    require(symname_address == EXPECTED_SYMNAME, "symname address drift")
    require(renderer_address == 0xC356, "renderer entry address drift")

    symname_chunk = function_chunk(disassembly, "symname")
    renderer_chunk = function_chunk(
        disassembly, "lisp65_error_overlay_entry")
    evidence = analyze(
        source_text=source_text,
        symname_chunk=symname_chunk,
        renderer_chunk=renderer_chunk,
        hardware=hardware,
        scratch_address=scratch_address)
    mutations = mutation_checks(
        source_text, symname_chunk, renderer_chunk, hardware, scratch_address)

    return {
        "format": FORMAT,
        "status": "passed-renderer-pointer-abi-overwrite-attributed",
        "scope": "host-static-attribution-no-product-change",
        "candidate": "v1.2.1-acceptance-sealed-not-promoted",
        "inputs": {
            "elf": bind(ELF),
            "renderer_source": bind(SOURCE),
            "symbol_source": bind(SYMBOL_SOURCE),
            "hardware_post_symname": bind(HARDWARE),
            "release_plan": bind(PLAN),
        },
        "linked_symbols": {
            "sym_name_scratch": f"0x{scratch_address:04x}",
            "symname": f"0x{symname_address:04x}",
            "lisp65_error_overlay_entry": f"0x{renderer_address:04x}",
        },
        "evidence": evidence,
        "mutations": mutations,
        "disposition": {
            "convicted_fix": (
                "delete sta __rc2 / stx __rc3 after jsr symname"),
            "v1.2.1": (
                "known issue; no product delta after acceptance seal"),
            "next_eligible_release": "v1.2.2",
            "hardware_or_dma_followup_required": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true",
        help="verify the tracked receipt instead of rewriting it")
    args = parser.parse_args()
    try:
        expected = expected_receipt()
        encoded = json.dumps(
            expected, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
        if args.check:
            require(RECEIPT.is_file(), f"missing receipt: {RECEIPT}")
            require(
                RECEIPT.read_text(encoding="utf-8") == encoded,
                "tracked DIRMISS attribution receipt drift")
            print(
                "c2-v1.2.1-dirmiss-attribution: VERIFY PASS "
                "mechanism=renderer-pointer-abi-overwrite mutations=5/5")
            return 0
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(encoded, encoding="utf-8")
        print(
            "c2-v1.2.1-dirmiss-attribution: PASS "
            "correct=$c1f6 overwritten=$8fd1 mutations=5/5 "
            "disposition=v1.2.2")
        return 0
    except (AttributionError, OSError, UnicodeError, json.JSONDecodeError,
            ValueError) as error:
        print(
            f"c2-v1.2.1-dirmiss-attribution: FIRST RED: {error}",
            file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
