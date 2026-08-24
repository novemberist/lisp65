#!/usr/bin/env python3
"""Bind the selector-bypass blank-screen control cycle without guessing its ingress."""

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
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))
from elf_truth import ElfTruth  # noqa: E402


ELF = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-domain-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
PRG = ELF.with_suffix("")
FIRST = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-domain-media/"
    "device-blank-first-red-20260824/capture.json")
FOLLOWUP = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-domain-media/"
    "device-blank-followup-20260824/capture.json")
FIRST_DRIVER = ROOT / (
    "tools/host-lisp/c2_v160_selector_bypass_blank_first_red_capture.py")
FOLLOWUP_DRIVER = ROOT / (
    "tools/host-lisp/c2_v160_selector_bypass_blank_followup_capture.py")
OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-selector-bypass-blank-cycle-attribution.json")
FORMAT = "lisp65-c2.3-v1.6-selector-bypass-blank-cycle-attribution-v1"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

EXPECTED = {
    "ELF": "bbb1547779ea2c9366fa5a29633aa07061a3607fa753043071df1780cc5ea3e4",
    "PRG": "3954884bc2e942f5da2f592be7b61a93613b5913c596db219bb3acc04bd1c19f",
    "first": "29a197788244c46ad457b0e743769da9bda2b82dc923d42f36038dfdb7fb979f",
    "followup": "8691c6105e4edbf9bbaa2c312760e3f50d680c185b3ff460c0f128533bab5525",
    "first_driver": "fd907b4d3ad1dac55761e2296f5f992d57dc0244bf1be41fac0bacc0527e167d",
    "followup_driver": "7c86bccf31f202ff0dc75a51f986a09d5d088fc15ed9f8591fc63c07f3bcc31c",
}

TABLE_BASES = (
    0xB634, 0xB6B8, 0xFD4C, 0xFDD6, 0xFDEC, 0xFDF4, 0xFD2C,
    0xB6E6, 0xB6F2, 0xB71C, 0xB624, 0xB708, 0xB62C,
)


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
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def rows(value: dict[str, Any]) -> dict[str, bytes]:
    return {item["name"]: bytes.fromhex(item["observed_hex"])
            for item in value["reads"]}


def u16(raw: bytes, offset: int = 0) -> int:
    return int.from_bytes(raw[offset:offset + 2], "little")


def section_u16(truth: ElfTruth, address: int) -> tuple[str, int]:
    matches: list[tuple[str, int]] = []
    for section in truth.sections_at_vma(address):
        if "SHF_ALLOC" not in section.flags or not section.bytes:
            continue
        raw = truth.section_bytes(section.name)
        offset = address - section.address
        if 0 <= offset <= len(raw) - 2:
            matches.append((section.name, u16(raw, offset)))
    require(len(matches) == 1, f"table-head section identity drift at ${address:04x}")
    return matches[0]


def derive() -> dict[str, Any]:
    inputs = {
        "ELF": bind(ELF), "PRG": bind(PRG), "first": bind(FIRST),
        "followup": bind(FOLLOWUP), "first_driver": bind(FIRST_DRIVER),
        "followup_driver": bind(FOLLOWUP_DRIVER),
    }
    require({name: inputs[name]["sha256"] for name in EXPECTED} == EXPECTED,
            "blank-cycle attribution identity drift")

    first = load(FIRST); followup = load(FOLLOWUP)
    expected_tuple = {
        "A": "0xff", "B": "0x00", "MAPH": "0x8000", "MAPL": "0x0000",
        "PC": "0x2020", "SP": "0x011e", "X": "0x00", "Y": "0xbf",
        "Z": "0x00",
        "suffix": "228408  00     21 ..E....C ...P 15 -  00 - .....lh.",
    }
    require(first["tuple"] == followup["tuple"] == expected_tuple,
            "conserved stopped tuple drift")
    require(first["discipline"] == {
        "CPU_left_stopped": True, "D2_D5_executed": False,
        "raw_first": True, "resets": 0, "resumes": 0, "runs": 0,
        "stops": 1, "tuple_before_memory": True,
    }, "first capture discipline drift")
    require(followup["discipline"] == {
        "CPU_left_stopped": True, "additional_stops": 0, "input": 0,
        "resets": 0, "resumes": 0, "runs": 0,
    }, "follow-up discipline drift")

    first_rows = rows(first); followup_rows = rows(followup)
    zp_stack = first_rows["bank0-zp-stack"]
    require(len(zp_stack) == 0x200, "ZP/stack row extent drift")
    require(zp_stack[0x100:] == bytes.fromhex("80222042") * 64,
            "hardware stack is not the complete two-JSR cycle witness")
    require(first_rows["refill-trace-origin"] == bytes(5)
            and first_rows["refill-trace-slots"] == bytes(68),
            "refill witness unexpectedly armed")
    require(followup_rows == {
        "screen-indirect-target": bytes.fromhex("2020"),
        "native-loop-back-edge": bytes.fromhex("4c4180"),
    }, "five-byte follow-up discriminator drift")

    prg = PRG.read_bytes(); load_address = u16(prg); image = prg[2:]
    def image_at(address: int, count: int) -> bytes:
        offset = address - load_address
        require(0 <= offset <= len(image) - count,
                f"PRG address outside image: ${address:04x}")
        return image[offset:offset + count]

    require(image_at(0x2020, 3) == bytes.fromhex("204080"),
            "$2020 cycle edge differs from packed PRG")
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    text = truth.section(".text"); text_raw = truth.section_bytes(".text")
    code_at = lambda address, count: text_raw[
        address - text.address:address - text.address + count]
    require(code_at(0x803F, 5) == bytes.fromhex("80228408a0")
            and code_at(0x808C, 3) == bytes.fromhex("4c4180"),
            "native loop bytes drift")
    require(truth.symbol("vm_native_call").value == 0x7D3B
            and truth.symbol("vm_native_call").bytes == 0x41C
            and truth.symbol("__call_indir").value == 0x2612,
            "native control identity drift")
    require(code_at(0x2612, 3) == bytes.fromhex("6c1400"),
            "dynamic native trampoline bytes drift")

    disassembly = subprocess.run(
        [str(OBJDUMP), "-d", str(ELF)], check=True,
        stdout=subprocess.PIPE, text=True).stdout
    starts = {int(match.group(1), 16) for match in
              re.finditer(r"^\s*([0-9a-f]+):\s", disassembly, re.MULTILINE)}
    require(0x803F in starts and 0x8041 in starts and 0x8040 not in starts,
            "$8040 instruction-boundary classification drift")
    direct_8040 = [line.strip() for line in disassembly.splitlines()
                   if re.search(r"\b(?:jmp|jsr)\s+\$8040\b", line)]
    require(direct_8040 == [], "$8040 became a linked direct target")
    require(re.search(r"^\s*808c: 4c 41 80\s+jmp\s+\$8041\b",
                      disassembly, re.MULTILINE) is not None,
            "valid $8041 loop edge absent")

    table_heads = []
    for address in TABLE_BASES:
        section, target = section_u16(truth, address)
        table_heads.append({"base": f"0x{address:04x}", "x": 0,
                            "section": section, "ELF_target": f"0x{target:04x}"})
    require(all(row["ELF_target"] != "0x8040" for row in table_heads),
            "an ELF jump-table head already targets $8040")

    runtime = {
        "saved___rc18___rc19": u16(zp_stack, 0x14),
        "lisp_toplevel_active": zp_stack[0x54],
        "vm_status": zp_stack[0x5F],
        "rtov_busy": zp_stack[0x78],
        "rtov_loaded_len": u16(zp_stack, 0x79),
        "c2_phase_owner": zp_stack[0x89],
        "c2_ready": zp_stack[0x8C],
    }
    require(runtime == {
        "saved___rc18___rc19": 0xC356, "lisp_toplevel_active": 1,
        "vm_status": 0, "rtov_busy": 0, "rtov_loaded_len": 0,
        "c2_phase_owner": 0, "c2_ready": 1,
    }, "blank-cycle runtime decode drift")

    return {
        "format": FORMAT,
        "status": "ATTRIBUTED: DETERMINISTIC TWO-JSR CYCLE; FIRST INGRESS STILL OPEN",
        "recorded_on": "2026-08-24",
        "authority": {
            "first_read": "owner authorized one raw-first stopped-state capture",
            "followup_read": ("owner authorized exactly five additional bytes from the "
                              "same stopped CPU; no state transition"),
        },
        "inputs": inputs,
        "contact_accounting": {
            "stops": 1, "followup_stops": 0, "resumes": 0, "runs": 0,
            "resets": 0, "input_events": 0, "CPU_left_stopped": True,
        },
        "observed_cycle": {
            "edge_1": {
                "address": "0x2020", "bytes": "20 40 80",
                "instruction": "JSR $8040", "pushed_return": "0x2022",
            },
            "edge_2": {
                "address": "0x8040", "bytes": "22 84 08",
                "instruction": "JSR ($0884)", "pointer_bytes": "20 20",
                "target": "0x2020", "pushed_return": "0x8042",
            },
            "stack_page": {
                "bytes": 256, "pattern": "80 22 20 42", "repetitions": 64,
                "meaning": ("both JSR return pairs alternate across the complete hardware "
                            "stack page; the original pre-cycle frames have been overwritten"),
            },
            "classification": "real infinite control cycle, not a wait or render-only blank",
        },
        "five_byte_discriminator": {
            "screen_pointer_0884": "0x2020",
            "live_loop_back_808c": "4c 41 80 / JMP $8041",
            "decision": ("the $808c operand is byte-correct; loop-back corruption is "
                         "mechanically refuted"),
        },
        "linked_world": {
            "owner": "vm_native_call",
            "valid_boundaries_around_ingress": ["0x803f", "0x8041"],
            "observed_ingress": "0x8040",
            "observed_ingress_is_instruction_boundary": False,
            "direct_JMP_or_JSR_targets_to_8040": direct_8040,
            "valid_loop_target": "0x8041",
            "x_zero_indirect_table_heads": table_heads,
        },
        "excluded_sources": {
            "808c_loop_operand_corruption": "refuted by live bytes 4c4180",
            "linked_direct_transfer": "no final-ELF JMP/JSR targets $8040",
            "__call_indir_immediate_source": {
                "trampoline": "JMP ($0014)",
                "live_pointer": "0xc356",
                "why_excluded": ("the two-cycle body changes neither $14 nor $15; an immediate "
                                 "__call_indir ingress would therefore still expose $8040"),
            },
            "refill_seam": "trace origin and both trace slots are all zero",
        },
        "runtime_state": {
            **{name: (f"0x{value:04x}" if value > 0xFF else value)
               for name, value in runtime.items()},
            "MAP": "baseline 0x8000/0x0000",
        },
        "open_mechanism": {
            "first_ingress_classes": [
                "a live jump-table head that differs from its final-ELF value",
                "a corrupted RTS/RTI continuation",
                "a live-mutated direct transfer outside the five-byte read",
            ],
            "why_original_state_cannot_name_the_predecessor": (
                "the infinite cycle overwrote all 256 hardware-stack bytes before the stop"),
            "next_minimal_live_discriminator_if_state_is_still_available": {
                "reads": [{"address": f"0x{address:04x}", "bytes": 2,
                           "expected": row["ELF_target"]}
                          for address, row in zip(TABLE_BASES, table_heads)],
                "total_bytes": 26,
                "meaning": ("with preserved X=0, any $8040 head names the corrupt computed "
                            "transfer; all thirteen heads matching ElfTruth exclude the entire "
                            "static table-dispatch class"),
            },
            "if_state_was_powered_off": (
                "reproduce deterministically and capture the same thirteen X=0 table heads; "
                "if all match, price a pre-wrap RTS/RTI/direct-transfer edge witness"),
        },
        "claim_limit": (
            "This receipt proves the terminal cycle and excludes three source classes. It "
            "does not identify the first transfer into $8040 and authorizes no fix, build, "
            "medium, resume or additional device read."),
    }


def selftest() -> None:
    value = derive()
    mutations = [
        ("five_byte_discriminator", "live_loop_back_808c", "4c 40 80"),
        ("linked_world", "observed_ingress_is_instruction_boundary", True),
        ("excluded_sources", "refill_seam", "armed"),
    ]
    for first, second, replacement in mutations:
        clone = json.loads(json.dumps(value)); clone[first][second] = replacement
        accepted = (
            clone["five_byte_discriminator"]["live_loop_back_808c"]
            == "4c 41 80 / JMP $8041"
            and clone["linked_world"]["observed_ingress_is_instruction_boundary"] is False
            and clone["excluded_sources"]["refill_seam"]
            == "trace origin and both trace slots are all zero")
        require(not accepted, "blank-cycle attribution mutation accepted")
    print(f"v1.6 selector blank-cycle attribution: SELFTEST PASS "
          f"mutations={len(mutations)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    if action == "selftest":
        selftest(); return 0
    value = derive(); encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if action == "write":
        OUT.write_text(encoded, encoding="utf-8")
    else:
        require(OUT.is_file() and OUT.read_text(encoding="utf-8") == encoded,
                "selector blank-cycle attribution receipt drift")
    print("v1.6 selector blank-cycle attribution: PASS cycle=2020<->8040 "
          "ingress=open")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"selector-blank-cycle-attribution: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
