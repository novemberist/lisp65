#!/usr/bin/env python3
"""Attribute the execution-boundary seam First Red from frozen bytes."""

from __future__ import annotations

import argparse
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
from elf_truth import ElfTruth  # noqa: E402


PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
ELF = ROOT / (
    "build/c2.3/v1.6-execution-boundary-backstop-uint8-irq-return-"
    "replacement-card/wplto/lisp65-c2-substitution-linked.prg.elf")
CAPTURE = ROOT / "build/c2.3/v1.6-execution-boundary-first-red/capture.json"
CAPTURE_DRIVER = ROOT / (
    "tools/host-lisp/c2_v160_execution_boundary_first_red_capture.py")
OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-execution-boundary-first-red-attribution.json")
FORMAT = "lisp65-c2.3-v1.6-execution-boundary-first-red-attribution-v1"

EXPECTED = {
    "plan": "18e59f014957833b0e981a3003f66bb52669e96d7432d4adc31397d4705197d1",
    "ELF": "c8b74690e682370f14c68bc837cd9642b702df024e71c82753b0b21d678fd10d",
    "capture": "334e67a7a4ecd746c381fc38751607c916d35b100390ddba5abdbe20c14c94d4",
    "capture_driver": "7ddbde9ba649bd315d5febe9b4027f4839ffa1172235c4ee8dd87e13aaedf79d",
}
PLAN_SEAL = "63bac8b1e3d9af87bb378ed70ab8d94498284fe5"


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
    try:
        display = path.relative_to(ROOT).as_posix()
    except ValueError:
        display = str(path)
    return {"path": display, "bytes": len(raw), "sha256": sha(raw)}


def bind_sealed_plan() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{PLAN_SEAL}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    require(sha(raw) == EXPECTED["plan"], "sealed attribution plan drift")
    # Preserve the sealed receipt's original projection while changing only
    # the source from which the historical bytes are read.
    return {"path": name, "bytes": len(raw), "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def row(capture: dict[str, Any], name: str) -> bytes:
    matches = [item for item in capture["reads"] if item["name"] == name]
    require(len(matches) == 1, f"capture row identity drift: {name}")
    raw = bytes.fromhex(matches[0]["observed_hex"])
    require(len(raw) == int(matches[0]["bytes"]), f"capture row length drift: {name}")
    return raw


def u16(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset:offset + 2], "little")


def derive() -> dict[str, Any]:
    inputs = {"plan": bind_sealed_plan(), "ELF": bind(ELF), "capture": bind(CAPTURE),
              "capture_driver": bind(CAPTURE_DRIVER)}
    require({name: inputs[name]["sha256"] for name in EXPECTED} == EXPECTED,
            "execution-boundary First-Red attribution identity drift")

    capture = load(CAPTURE)
    require(capture["tuple"] == {
        "A": "0x02", "B": "0x00", "MAPH": "0x8000", "MAPL": "0x0000",
        "PC": "0xe096", "SP": "0x01c9", "X": "0xc9", "Y": "0xaf",
        "Z": "0x00",
        "suffix": "4C96E0  00     24 ..E..I.. ...P 15 -  00 - .....lh.",
    }, "stopped tuple drift")
    require(capture["discipline"] == {
        "CPU_left_stopped": True, "D2_D5_executed": False,
        "raw_first": True, "resets": 0, "resumes": 0, "runs": 0,
        "stops": 1, "tuple_before_memory": True,
    }, "read-only stopped-state discipline drift")

    zp_stack = row(capture, "bank0-zp-stack")
    vm = row(capture, "vm-and-boot-status")
    boot = row(capture, "c2-boot-runtime")
    trace_origin = row(capture, "refill-trace-origin")
    trace_slots = row(capture, "refill-trace-slots")
    require(len(zp_stack) == 0x200 and len(vm) == 0x20 and len(boot) == 0x32,
            "authorized state extent drift")
    require(trace_origin == bytes(5) and trace_slots == bytes(68),
            "refill witness unexpectedly armed")

    truth = ElfTruth.read(
        ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    require(truth.symbol("c2_kernal_fail_closed").value == 0xE08B
            and truth.symbol("retired_window_brk_classifier").value == 0x222D
            and truth.symbol("retired_window_resume").value == 0x2269,
            "execution-boundary identity drift")
    require(truth.symbol("lisp_toplevel").value == 0xBD49
            and truth.symbol("lisp_toplevel").bytes == 19,
            "current toplevel continuation identity drift")

    # The IRQ entry pushed A/X/Y/Z after the hardware frame.  With SP=$01c9,
    # the classifier's TSX therefore observes P at $01ce and return PC at
    # $01cf/$01d0, exactly as its emitted indexed loads specify.
    sp = 0xC9
    stack = 0x100
    saved = {
        "Z": zp_stack[stack + sp + 1], "Y": zp_stack[stack + sp + 2],
        "X": zp_stack[stack + sp + 3], "A": zp_stack[stack + sp + 4],
        "P": zp_stack[stack + sp + 5],
        "continuation": u16(zp_stack, stack + sp + 6),
    }
    require(saved == {"Z": 0x00, "Y": 0xBF, "X": 0x00, "A": 0xFF,
                      "P": 0xB1, "continuation": 0x0607},
            "IRQ frame decode drift")
    require(saved["P"] & 0x10, "interrupt was not a software BRK")
    brk_address = saved["continuation"] - 2
    require(brk_address == 0x0605, "software BRK address drift")

    executable_owners = [section.name for section in truth.sections_at_vma(brk_address)
                         if "SHF_EXECINSTR" in section.flags]
    symbol_owners = [symbol.name for symbol in truth.symbols
                     if symbol.bytes and symbol.value <= brk_address
                     < symbol.value + symbol.bytes]
    require(executable_owners == [] and symbol_owners == [],
            "$0605 unexpectedly belongs to linked product code")

    # Candidate-symbol decoding over the authorized rows.  These are facts at
    # the stop, not a reconstructed causal chain.
    states = {
        "lisp_toplevel_active": zp_stack[0x52],
        "vm_status": zp_stack[0x5D],
        "rtov_call_context": u16(zp_stack, 0x74),
        "rtov_busy": zp_stack[0x78],
        "rtov_loaded_len": u16(zp_stack, 0x79),
        "pending_code": zp_stack[0x36],
        "saved___rc18___rc19": u16(zp_stack, 0x14),
        "rtov_call_result": u16(vm, 0x11),
        "rtov_fault": vm[0x17], "rtov_family": vm[0x18],
        "rtov_family_generation": u16(vm, 0x19),
    }
    require(states == {
        "lisp_toplevel_active": 1, "vm_status": 0,
        "rtov_call_context": 0x9E36, "rtov_busy": 0,
        "rtov_loaded_len": 0, "pending_code": 0,
        "saved___rc18___rc19": 0xC356, "rtov_call_result": 0x1800,
        "rtov_fault": 0, "rtov_family": 2,
        "rtov_family_generation": 1,
    }, "stopped runtime state drift")
    require(truth.symbol("eval").value <= states["rtov_call_context"]
            < truth.symbol("eval").value + truth.symbol("eval").bytes,
            "call-context owner drift")

    # Bind the exact classifier semantics from final bytes.  It accepts only
    # continuations in [$c358,$ca93); $0607 necessarily takes fail-closed.
    classifier = truth.section_bytes(".text")
    text = truth.section(".text")
    start = truth.symbol("retired_window_brk_classifier").value - text.address
    classifier = classifier[start:start + 60]
    require(classifier.hex() == (
        "babd05012910f031a5780579057ad029a552f025bd060138e958a8bd0701e9c3"
        "9017c9079006d011c03bb00da9699d0601a9229d07014c68e04c8be0"),
        "classifier final bytes drift")

    return {
        "format": FORMAT,
        "status": "ATTRIBUTED: PRE-SEAM SOFTWARE BRK OUTSIDE RETIRED WINDOW; CAUSE OPEN",
        "recorded_on": "2026-08-23", "inputs": inputs,
        "contact": {"kind": "one authorized raw-first stopped-state read",
                    "stops": 1, "resumes": 0, "runs": 0, "resets": 0,
                    "bytes_read": 667, "CPU_left_stopped": True},
        "refill_witness": {
            "origin": "5/5 zero", "slots": "68/68 zero",
            "armed": False,
            "decision": ("failure precedes Comfort/refill witness activation; "
                         "this contact cannot qualify or condemn the repaired seam"),
        },
        "interrupt_frame": {
            "handler_SP": "0x01c9",
            "saved_registers": {name: f"0x{value:02x}" for name, value in
                                saved.items() if name != "continuation"},
            "saved_continuation": "0x0607", "BRK_address": "0x0605",
            "software_BRK": True,
        },
        "linked_world": {
            "BRK_address_executable_sections": executable_owners,
            "BRK_address_symbols": symbol_owners,
            "classification": ("$0605 is dynamic low RAM, not a linked instruction "
                               "boundary or product-code owner"),
            "classifier_accepts": "stacked continuations $c358 through $ca92",
            "observed_continuation": "0x0607",
            "classifier_result": "correct fail-closed rejection",
        },
        "runtime_state": {**{name: (f"0x{value:04x}" if value > 0xff else value)
                              for name, value in states.items()},
                          "rtov_call_context_owner": "eval"},
        "decisions": {
            "known_missing_facade_signature_observed": False,
            "nested_MAP_membership": "not established; MAP is baseline at the stop",
            "refill_witness_involved": False,
            "execution_boundary_false_accept": False,
            "new_fact": ("control reached non-executable low RAM and executed a software BRK; "
                         "the boundary rejected it exactly as designed"),
            "stale_holder_fact": ("__rc18/__rc19 still equals $c356, the historical retired-"
                                  "window entry, but the current BRK is at $0605"),
        },
        "open_mechanism": {
            "question": ("Did an earlier accepted retired-window BRK recover through the live "
                         "$c356 continuation and later transfer to $0605, or is $0605 an "
                         "independent corrupt return/indirect target?"),
            "why_current_capture_cannot_decide": ("it excludes the current lisp_toplevel "
                "jmp_buf, vm_codebuf, low RAM around $0605 and the source-less episode byte"),
            "minimal_discriminator_read": [
                {"name": "current-lisp-toplevel-jmp-buf", "address": "derived from ELF: 0xbd49",
                 "bytes": 19},
                {"name": "vm-codebuf-and-bookkeeping", "address": "derived from ELF: 0xbfa4",
                 "bytes": 75},
                {"name": "low-ram-brk-neighborhood", "address": "0x00000600", "bytes": 16},
                {"name": "IRQ-episode-state", "address": "0x0000ff83", "bytes": 11},
            ],
        },
        "claim_limit": ("Host-only attribution over the authorized frozen capture. It names no "
                        "causal carrier and authorizes no fix, build, medium, resume or further "
                        "device read."),
    }


def selftest() -> None:
    value = derive()
    mutations = [
        ("interrupt_frame", "BRK_address", "0xc356"),
        ("refill_witness", "armed", True),
        ("linked_world", "classifier_result", "accepted"),
    ]
    for first, second, replacement in mutations:
        clone = json.loads(json.dumps(value))
        clone[first][second] = replacement
        accepted = (clone["interrupt_frame"]["BRK_address"] == "0x0605"
                    and clone["refill_witness"]["armed"] is False
                    and clone["linked_world"]["classifier_result"]
                    == "correct fail-closed rejection")
        require(not accepted, "execution-boundary attribution mutation accepted")
    print(f"v1.6 execution-boundary First-Red attribution: SELFTEST PASS "
          f"mutations={len(mutations)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    if action == "selftest":
        selftest(); return 0
    value = derive()
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if action == "write":
        OUT.write_text(encoded, encoding="utf-8")
    else:
        require(OUT.is_file() and OUT.read_text(encoding="utf-8") == encoded,
                "execution-boundary First-Red attribution receipt drift")
    print("v1.6 execution-boundary First-Red attribution: PASS "
          "BRK=$0605 pre-seam cause=open")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError) as error:
        print(f"v1.6 execution-boundary First-Red attribution: FAIL: {error}",
              file=sys.stderr)
        raise SystemExit(1)
