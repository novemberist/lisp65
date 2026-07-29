#!/usr/bin/env python3
"""Prove the terminal source-less-IRQ fail-closed blackbox.

The source half is usable before the sole WPLTO.  With --elf, the gate also
compares the linked IRQ handler to Link 78 and permits exactly the two-byte
operand change of its already-terminal absolute JMP.
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
SOURCE = ROOT / "src/c2_kernal_window.s"
CONTRACT = ROOT / "config/c2-fail-closed-blackbox-contract.json"
KERNAL_CONTRACT = ROOT / "config/c2-kernal-unmap-contract.json"
PREDECESSOR = (
    ROOT / "build/post-release/link78-dirmiss-renderer/final/"
    "lisp65-c2-substitution-linked.prg.elf"
)
LLVM = ROOT / "tools/llvm-mos/bin"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str]) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0, result.stdout[-5000:])
    return result.stdout


def span(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin)
    return source[begin:finish]


def source_gate(source: str) -> dict[str, Any]:
    constants = """\
\t.equ C2K_FAIL_CODE,        C2K_EVENT_CODE
\t.equ C2K_FAIL_LATCH,       C2K_EVENT_READY
\t.equ C2K_FAIL_AUTOIEC,     C2K_BREAK_PENDING
\t.equ C2K_FAIL_AUDIODMA,    C2K_BREAK_HELD
\t.equ C2K_FAIL_D01A,        $ff8c
\t.equ C2K_FAIL_PC_LO,       $ff8d
\t.equ C2K_FAIL_PC_HI,       $ff8e
\t.equ C2K_FAIL_ETHERNET,    $ff8f
"""
    require(constants in source, "terminal state aliases drift")
    irq = span(
        source, "c2_kernal_irq_handler:",
        "\t.section .text.c2_kernal_fail_closed_blackbox",
    )
    terminal = """\
\tlda C2K_SOURCELESS_IRQS
\tbeq .Lfirst_source_less
\t; Cross-section control flow is always an absolute jump.  A long
\t; conditional relocation is not an identity-safe facade.
\tjmp c2_kernal_sourceless_fail_blackbox
.Lfirst_source_less:
\tinc C2K_SOURCELESS_IRQS
\tbra .Lirq_return
"""
    require(terminal in irq, "second source-less terminal edge drift")
    require(
        irq.count("c2_kernal_sourceless_fail_blackbox") == 1,
        "blackbox must have exactly one IRQ edge",
    )
    require("C2K_FAIL_" not in irq,
            "a returning IRQ path writes terminal blackbox state")
    require(
        "\tsta C2K_UNOWNED_VIC\n" in irq
        and irq.index("\tsta C2K_UNOWNED_VIC\n") < irq.index(terminal),
        "D019 classification is not captured before the terminal edge",
    )

    body = span(
        source, "c2_kernal_sourceless_fail_blackbox:",
        ".Lc2_kernal_sourceless_fail_blackbox_end:",
    )
    expected_prefix = """\
c2_kernal_sourceless_fail_blackbox:
\t; Terminal, call-free capture prefix.  IRQ entry has already made the
\t; interrupted frame stable on page one; do not mask, branch or transport
\t; anything until every witness is resident in the existing state window.
\tlda #$b2
\tsta C2K_FAIL_CODE
\tlda C2K_SOURCELESS_IRQS
\tsta C2K_FAIL_LATCH
\tlda $d01a
\tsta C2K_FAIL_D01A
\ttsx
\tlda $0106,x
\tsta C2K_FAIL_PC_LO
\tlda $0107,x
\tsta C2K_FAIL_PC_HI
\tlda $d6e1
\tsta C2K_FAIL_ETHERNET
\tlda $d697
\tsta C2K_FAIL_AUTOIEC
\tlda $d713
\tsta C2K_FAIL_AUDIODMA
"""
    require(body.startswith(expected_prefix), "capture prefix drift")
    prefix = body[:body.index("\tsei\n")]
    instructions = [
        line.strip() for line in prefix.splitlines()
        if line.startswith("\t") and not line.startswith("\t;")
    ]
    require(
        instructions == [
            "lda #$b2", "sta C2K_FAIL_CODE",
            "lda C2K_SOURCELESS_IRQS", "sta C2K_FAIL_LATCH",
            "lda $d01a", "sta C2K_FAIL_D01A", "tsx",
            "lda $0106,x", "sta C2K_FAIL_PC_LO",
            "lda $0107,x", "sta C2K_FAIL_PC_HI",
            "lda $d6e1", "sta C2K_FAIL_ETHERNET",
            "lda $d697", "sta C2K_FAIL_AUTOIEC",
            "lda $d713", "sta C2K_FAIL_AUDIODMA",
        ],
        "capture prefix is not the exact straight-line witness sequence",
    )
    require(
        not re.search(r"\b(jsr|jmp|bra|brl|b(?:cc|cs|eq|mi|ne|pl|vc|vs))\b",
                      "\n".join(instructions))
        and "$d700" not in prefix and "$d705" not in prefix
        and "c2_dma" not in prefix.lower(),
        "capture prefix calls, branches, checks or transports",
    )
    display = """\
\tsei
\t; F2 = fail-closed on the second source-less IRQ of one raster episode.
\t; This is deliberately only a two-cell display over the existing seam.
\tldx #$00
\tlda #$46
\tjsr c2_kernal_output_cell
\tinx
\tlda #$32
\tjsr c2_kernal_output_cell
\tjmp c2_kernal_fail_closed
"""
    require(display in body, "F2 output or terminal handoff drift")
    require(
        "$0800" not in body and body.count("jsr c2_kernal_output_cell") == 2,
        "blackbox bypasses or misuses the output seam",
    )
    generic = span(
        source, "c2_kernal_fail_closed:",
        "\t.section .lisp65_c2_kernal_window.post_startup_output_seam",
    )
    require(
        generic == """\
c2_kernal_fail_closed:
\tsei
\tlda #$00
\tsta $d01a
\tlda #$02
\tsta $d020
.Lfailed:
\tjmp .Lfailed

""",
        "generic fail-closed body changed",
    )
    require(
        "\t.section .lisp65_c2_kernal_window.state,\"a\",@progbits\n"
        "\t.space 16, 0\n" in source,
        "window state grew or changed representation",
    )
    return {
        "status": "passed-source-terminal-only-blackbox",
        "reason_code": "0xb2",
        "visible_code": "F2",
        "witnesses": 8,
        "existing_D019_witness": "C2K_UNOWNED_VIC at 0xff89",
        "state_bytes": 16,
        "state_growth_bytes": 0,
        "capture_prefix_instructions": len(instructions),
        "calls_before_SEI": 0,
        "DMA_before_SEI": 0,
        "display_seam_calls": 2,
    }


def contract_gate() -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    kernal = json.loads(KERNAL_CONTRACT.read_text(encoding="utf-8"))
    bound = kernal["interrupt_and_output"]["fail_closed_blackbox"]
    require(
        contract["status"] == "owner-commissioned-terminal-blackbox"
        and contract["capture"]["state_geometry"]["bytes"] == 16
        and contract["capture"]["state_geometry"]["growth_bytes"] == 0
        and contract["residency"]["e000_floor_bytes"] == 54
        and contract["residency"]["bank0_text_noise_floor_bytes"] == 32
        and contract["hard_budget"] == {
            "wplto_probes": 1,
            "product_links": 1,
            "hardware_runs": 1,
            "hardware_rows": [
                "(require (quote defstruct))",
                "(defstruct point x y)",
                "(make-point 3 4)",
            ],
            "terminal_rule": (
                "After the one run, attribute from the blackbox or park "
                "defstruct permanently for this era. No instrument revision "
                "or further diagnostic round."
            ),
        }
        and bound["contract"] == str(CONTRACT.relative_to(ROOT))
        and bound["gate"]
            == "tools/host-lisp/c2_fail_closed_blackbox_gate.py",
        "blackbox contract or hard budget drift",
    )
    return {
        "status": "passed-contract-and-hard-budget",
        "wplto_probes": 1,
        "product_links": 1,
        "hardware_runs": 1,
        "e000_floor_bytes": 54,
    }


def mutation_gate(source: str) -> dict[str, Any]:
    mutations = {
        "terminal-edge-bypasses-blackbox": source.replace(
            "\tjmp c2_kernal_sourceless_fail_blackbox\n",
            "\tjmp c2_kernal_fail_closed\n", 1),
        "capture-owned-path": source.replace(
            "\tsta $d019\n", "\tsta $d019\n\tsta C2K_FAIL_CODE\n", 1),
        "capture-first-source-less-path": source.replace(
            ".Lfirst_source_less:\n\tinc C2K_SOURCELESS_IRQS",
            ".Lfirst_source_less:\n\tsta C2K_FAIL_CODE\n"
            "\tinc C2K_SOURCELESS_IRQS", 1),
        "reason-missing": source.replace(
            "\tlda #$b2\n\tsta C2K_FAIL_CODE\n", "", 1),
        "latch-missing": source.replace(
            "\tlda C2K_SOURCELESS_IRQS\n\tsta C2K_FAIL_LATCH\n", "", 1),
        "d01a-wrong": source.replace(
            "\tlda $d01a\n\tsta C2K_FAIL_D01A\n",
            "\tlda $d019\n\tsta C2K_FAIL_D01A\n", 1),
        "pc-low-offset-wrong": source.replace("$0106,x", "$0105,x", 1),
        "pc-high-offset-wrong": source.replace("$0107,x", "$0108,x", 1),
        "ethernet-missing": source.replace(
            "\tlda $d6e1\n\tsta C2K_FAIL_ETHERNET\n", "", 1),
        "autoiec-missing": source.replace(
            "\tlda $d697\n\tsta C2K_FAIL_AUTOIEC\n", "", 1),
        "audiodma-missing": source.replace(
            "\tlda $d713\n\tsta C2K_FAIL_AUDIODMA\n", "", 1),
        "sei-before-last-witness": source.replace(
            "\tlda $d713\n", "\tsei\n\tlda $d713\n", 1),
        "call-in-capture-prefix": source.replace(
            "\tlda $d01a\n", "\tjsr c2_kernal_output_cell\n\tlda $d01a\n", 1),
        "branch-in-capture-prefix": source.replace(
            "\ttsx\n", "\tbra .Lfailed\n\ttsx\n", 1),
        "dma-in-capture-prefix": source.replace(
            "\tlda $d6e1\n", "\tsta $d700\n\tlda $d6e1\n", 1),
        "direct-screen-store": source.replace(
            "\tjsr c2_kernal_output_cell\n\tinx\n",
            "\tsta $0800\n\tinx\n", 1),
        "one-display-cell": source.replace(
            "\tinx\n\tlda #$32\n\tjsr c2_kernal_output_cell\n", "", 1),
        "state-grows": source.replace("\t.space 16, 0", "\t.space 17, 0", 1),
        "generic-fail-changed": source.replace(
            "\tlda #$02\n\tsta $d020\n", "\tlda #$03\n\tsta $d020\n", 1),
    }
    rejected: list[str] = []
    for name, mutated in mutations.items():
        require(mutated != source, f"mutation did not apply: {name}")
        try:
            source_gate(mutated)
        except (GateError, ValueError):
            rejected.append(name)
    require(
        len(rejected) == len(mutations),
        "blackbox mutations survived: "
        + ", ".join(name for name in mutations if name not in rejected),
    )
    return {
        "status": "passed-all-mutants-rejected",
        "rejected": len(rejected),
        "total": len(mutations),
        "names": rejected,
    }


def symbols(elf: Path) -> dict[str, tuple[int, int]]:
    output = run([str(LLVM / "llvm-nm"), "-S", str(elf)])
    found: dict[str, tuple[int, int]] = {}
    for line in output.splitlines():
        match = re.match(
            r"^([0-9a-f]+)\s+([0-9a-f]+)\s+[TtRr]\s+(\S+)$", line)
        if match:
            found[match.group(3)] = (
                int(match.group(1), 16), int(match.group(2), 16))
    return found


def section_table(elf: Path) -> dict[str, tuple[int, int]]:
    output = run([str(LLVM / "llvm-readelf"), "-S", "--wide", str(elf)])
    found: dict[str, tuple[int, int]] = {}
    for line in output.splitlines():
        match = re.match(
            r"^\s*\[\s*\d+\]\s+(\S+)\s+\S+\s+"
            r"([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)\s", line)
        if match:
            found[match.group(1)] = (
                int(match.group(2), 16), int(match.group(3), 16))
    return found


def image_bytes(elf: Path) -> dict[int, int]:
    output = run([str(LLVM / "llvm-objdump"), "-d", str(elf)])
    memory: dict[int, int] = {}
    for line in output.splitlines():
        match = re.match(
            r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}(?:\s+|$))+)", line)
        if not match:
            continue
        address = int(match.group(1), 16)
        for offset, byte in enumerate(match.group(2).split()):
            memory[address + offset] = int(byte, 16)
    return memory


def take(memory: dict[int, int], address: int, size: int) -> bytes:
    try:
        return bytes(memory[address + offset] for offset in range(size))
    except KeyError as exc:
        raise GateError(
            f"linked bytes absent at 0x{int(exc.args[0]):04x}") from exc


def linked_gate(elf: Path, predecessor: Path) -> dict[str, Any]:
    require(elf.is_file() and predecessor.is_file(), "linked ELF absent")
    current_symbols = symbols(elf)
    old_symbols = symbols(predecessor)
    current_sections = section_table(elf)
    old_sections = section_table(predecessor)
    current_memory = image_bytes(elf)
    old_memory = image_bytes(predecessor)
    required = (
        "c2_kernal_irq_handler", "c2_kernal_nmi_handler",
        "c2_kernal_sourceless_fail_blackbox",
        "c2_kernal_fail_closed", "c2_kernal_output_cell",
    )
    require(all(name in current_symbols for name in required),
            "linked blackbox symbols incomplete")
    irq_section = ".lisp65_c2_kernal_window.irq_handler"
    fail_section = ".lisp65_c2_kernal_window.map_switch_and_guards"
    output_section = ".lisp65_c2_kernal_window.post_startup_output_seam"
    state_section = ".lisp65_c2_kernal_window.state"
    require(
        current_sections[irq_section][1] == old_sections[irq_section][1] == 74
        and current_sections[fail_section][1]
            == old_sections[fail_section][1] == 14
        and current_sections[output_section][1]
            == old_sections[output_section][1] == 4
        and current_sections[state_section] == (0xFF80, 16)
        and old_sections[state_section] == (0xFF80, 16),
        "window geometry changed",
    )
    irq_address = current_sections[irq_section][0]
    old_irq_address = old_sections[irq_section][0]
    require(irq_address == old_irq_address, "IRQ entry moved")
    current_irq = bytearray(take(current_memory, irq_address, 74))
    old_irq = bytearray(take(old_memory, old_irq_address, 74))
    old_jump = old_irq.find(bytes((0x4C, 0x8B, 0xE0)))
    require(old_jump >= 0 and old_jump == old_irq.rfind(
        bytes((0x4C, 0x8B, 0xE0))), "predecessor terminal JMP ambiguous")
    target = current_symbols["c2_kernal_sourceless_fail_blackbox"][0]
    require(target < 0xE000, "blackbox did not land in ordinary resident text")
    expected = old_irq[:]
    expected[old_jump + 1] = target & 0xFF
    expected[old_jump + 2] = target >> 8
    require(
        current_irq == expected,
        "a nonterminal IRQ byte changed or terminal JMP is not the blackbox",
    )
    fail_address = current_sections[fail_section][0]
    old_fail_address = old_sections[fail_section][0]
    require(
        fail_address == old_fail_address
        and take(current_memory, fail_address, 14)
            == take(old_memory, old_fail_address, 14),
        "generic fail-closed linked body changed",
    )
    output_address = current_symbols["c2_kernal_output_cell"][0]
    require(
        take(current_memory, output_address, 4)
            == take(old_memory, old_symbols["c2_kernal_output_cell"][0], 4)
            == bytes((0x9D, 0x00, 0x08, 0x60)),
        "output seam changed",
    )
    blackbox_size = current_symbols[
        "c2_kernal_sourceless_fail_blackbox"][1]
    require(0 < blackbox_size <= 96, "blackbox size missing or unbounded")
    blackbox = take(current_memory, target, blackbox_size)
    sei_at = blackbox.find(bytes((0x78,)))
    require(sei_at > 0, "blackbox has no post-capture SEI")
    prefix = blackbox[:sei_at]
    require(
        bytes((0x20,)) not in prefix
        and bytes((0x4C,)) not in prefix
        and bytes((0x8D, 0x00, 0x08)) not in prefix
        and bytes((0x8D, 0x00, 0xD7)) not in prefix
        and bytes((0x8D, 0x05, 0xD7)) not in prefix,
        "linked capture prefix calls, jumps, displays or starts DMA",
    )
    for encoded in (
        bytes((0xAD, 0x1A, 0xD0)),
        bytes((0xBD, 0x06, 0x01)),
        bytes((0xBD, 0x07, 0x01)),
        bytes((0xAD, 0xE1, 0xD6)),
        bytes((0xAD, 0x97, 0xD6)),
        bytes((0xAD, 0x13, 0xD7)),
    ):
        require(encoded in prefix, f"linked capture read absent: {encoded.hex()}")
    output_jsr = bytes((0x20, output_address & 0xFF, output_address >> 8))
    generic_address = current_symbols["c2_kernal_fail_closed"][0]
    terminal_jmp = bytes((
        0x4C, generic_address & 0xFF, generic_address >> 8))
    require(
        blackbox.count(output_jsr) == 2
        and blackbox.endswith(terminal_jmp),
        "linked F2 display or generic terminal handoff drift",
    )
    return {
        "status": "passed-linked-terminal-only-blackbox",
        "blackbox_address": f"0x{target:04x}",
        "blackbox_bytes": blackbox_size,
        "blackbox_section": ".text",
        "irq_address": f"0x{irq_address:04x}",
        "irq_bytes": 74,
        "IRQ_delta_indices": [old_jump + 1, old_jump + 2],
        "IRQ_nonterminal_delta_bytes": 0,
        "generic_fail_closed_bytes": 14,
        "generic_fail_closed_delta_bytes": 0,
        "output_seam_bytes": 4,
        "window_state_bytes": 16,
        "window_state_growth_bytes": 0,
        "calls_before_SEI": 0,
        "display_seam_calls": 2,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--predecessor", type=Path, default=PREDECESSOR)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    source = SOURCE.read_text(encoding="ascii")
    result: dict[str, Any] = {
        "format": "lisp65-c2-fail-closed-blackbox-gate-v1",
        "status": "passed",
        "source": {
            "path": str(SOURCE.relative_to(ROOT)),
            "sha256": sha256(SOURCE),
            **source_gate(source),
        },
        "contract": contract_gate(),
        "mutations": mutation_gate(source),
        "linked": None,
    }
    if args.elf:
        elf = args.elf if args.elf.is_absolute() else ROOT / args.elf
        predecessor = (
            args.predecessor if args.predecessor.is_absolute()
            else ROOT / args.predecessor
        )
        result["linked"] = linked_gate(elf, predecessor)
        result["linked_ELF"] = {
            "path": str(elf.relative_to(ROOT)),
            "sha256": sha256(elf),
        }
        result["predecessor_ELF"] = {
            "path": str(predecessor.relative_to(ROOT)),
            "sha256": sha256(predecessor),
        }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.receipt:
        path = args.receipt if args.receipt.is_absolute() else ROOT / args.receipt
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"c2-fail-closed-blackbox-gate: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
