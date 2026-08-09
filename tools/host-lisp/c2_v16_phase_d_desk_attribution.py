#!/usr/bin/env python3
"""Desk attribution for the two Phase-D First Reds.

This tool deliberately answers only what the bound Link-88/82 artifacts and
the stopped/setup receipts can answer.  In particular, an m65 ``-t`` process
return is not a key-arrival witness, and a cumulative GC counter is not a GC
delta.  The loader lane proves the diagnostic startup bytes, not the behavior
of an unobserved product entry.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402

READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
LINK88_ELF = ROOT / (
    "build/c2.3/v1.3.0-candidate-product-link88-r1/final/"
    "lisp65-c2-substitution-linked.prg.elf")
PHASE_C = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-c-diagnostic-preparation-receipt.json")
PHASE_D = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-d-device-first-red-receipt.json")
HISTORICAL_EDITOR = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-stall-hang-triggered-device-receipt.json")
CONTROL_PRG = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/control-link82.prg"
DIAGNOSTIC_PRG = ROOT / (
    "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-link82.prg")
CONTROL_ELF = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/control-link82.elf"
DIAGNOSTIC_ELF = ROOT / (
    "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-link82.elf")
LINK80_RUNNER = ROOT / "scripts/c2-v123-link80-require-discriminator-hw.sh"
LINK82_RUNNER = ROOT / "scripts/c2-v125-require-prior-append-hw.sh"
OWNER_PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
EDITOR_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-editor-d1-desk-attribution-receipt.json")
LOADER_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-loader-desk-attribution-receipt.json")


class FirstRed(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FirstRed(message)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def write(path: Path, value: dict[str, Any]) -> None:
    path.write_bytes(canonical(value))


def symbol_bytes(truth: ElfTruth, name: str) -> tuple[int, bytes]:
    symbol = truth.symbol(name)
    require(symbol.bytes > 0, f"unsized symbol: {name}")
    section = truth.section(symbol.section)
    data = truth.section_bytes(symbol.section)
    offset = symbol.value - section.address
    require(0 <= offset <= len(data) - symbol.bytes,
            f"symbol outside section: {name}")
    return symbol.value, data[offset:offset + symbol.bytes]


def prg_diff_ranges(before: bytes, after: bytes) -> list[dict[str, Any]]:
    require(len(before) == len(after), "PRG length drift")
    require(before[:2] == after[:2], "PRG load address drift")
    load_address = int.from_bytes(before[:2], "little")
    differing = [i for i, pair in enumerate(zip(before, after))
                 if pair[0] != pair[1]]
    ranges: list[list[int]] = []
    for index in differing:
        if not ranges or index != ranges[-1][-1] + 1:
            ranges.append([index])
        else:
            ranges[-1].append(index)
    return [{
        "file_offset": f"0x{row[0]:04x}",
        "start": f"0x{load_address + row[0] - 2:04x}",
        "bytes": len(row),
        "before": before[row[0]:row[-1] + 1].hex(),
        "after": after[row[0]:row[-1] + 1].hex(),
    } for row in ranges]


def validate_editor_observation(
    observation: dict[str, Any], *, poll_start: int, poll_bytes: bytes,
) -> None:
    stopped = observation["one_stop_packet"]
    pc = int(stopped["PC"], 16)
    require(observation["postcondition"]["fill"] == 56,
            "D1 fill witness drift")
    require(observation["postcondition"]["expected_fill"] == 64,
            "D1 expected fill drift")
    require(stopped["queue_state"] == 0 and stopped["queue_code"] == 0,
            "D1 queue is not empty")
    require(poll_start <= pc < poll_start + len(poll_bytes),
            "D1 PC is not inside event poll")
    offset = pc - poll_start
    require(offset == 0x35 and poll_bytes[0x33:0x38] == bytes.fromhex("a900a30060"),
            "D1 PC is not the no-event return path")


def editor_value() -> dict[str, Any]:
    phase_d = load(PHASE_D)
    historical = load(HISTORICAL_EDITOR)
    truth = ElfTruth.read(
        LINK88_ELF, llvm_readobj=READOBJ, include_section_data=True)
    poll_start, poll = symbol_bytes(truth, "c2_kernal_event_poll")
    input_start, input_body = symbol_bytes(truth, "lisp_input_event")
    vm_start, vm_body = symbol_bytes(truth, "vm_run_inner")
    gc = truth.symbol("gc_collect")
    gc_runs = truth.symbol("gc_runs")
    observation = phase_d["D1_editor_quiet_typing"]
    validate_editor_observation(
        observation, poll_start=poll_start, poll_bytes=poll)
    require(bytes.fromhex("2000e0") in input_body,
            "blocking input no longer calls event poll")
    require(bytes.fromhex("2000e0") in vm_body,
            "VM periodic poll no longer calls event poll")
    old = historical["offline_review"]["observed"]
    require(old["stable_fill"] == 13 and old["expected_fill"] == 34,
            "historical partial-fill witness drift")
    require(old["queue_state"] == 0 and old["queue_code"] == 0,
            "historical queue witness drift")
    require(old["PC"] == "0xe000",
            "historical event-poll witness drift")
    require(historical["offline_review"]["classification"] ==
            "FIRST-RED-option1-setup-partial-normal-input",
            "historical classification drift")
    require(gc_runs.value == 0xB9F0, "Link-88 gc_runs address drift")
    return {
        "format": "lisp65-c2.3-v1.6-editor-D1-desk-attribution-v1",
        "recorded_on": date.today().isoformat(),
        "status": "D1-PC-attributed-product-stall-not-proven",
        "authorities": {
            "owner_commission": bind(OWNER_PLAN),
            "phase_D": bind(PHASE_D),
            "link88_ELF": bind(LINK88_ELF),
            "historical_same-signature_receipt": bind(HISTORICAL_EDITOR),
            "tool": bind(Path(__file__).resolve()),
        },
        "linked_truth": {
            "PC": "0xe035",
            "symbol": "c2_kernal_event_poll",
            "symbol_start": f"0x{poll_start:04x}",
            "symbol_bytes": len(poll),
            "offset": 0x35,
            "instruction": "LDZ #$00",
            "path": "LDA #$00; LDZ #$00; RTS — ordinary no-event return",
            "possible_callers_not_distinguished_without_stack": [
                {"symbol": "lisp_input_event", "start": f"0x{input_start:04x}"},
                {"symbol": "vm_run_inner", "start": f"0x{vm_start:04x}"},
            ],
            "gc_collect": {
                "start": f"0x{gc.value:04x}", "bytes": gc.bytes,
                "PC_inside": False,
            },
            "gc_runs": {"address": f"0x{gc_runs.value:04x}", "value": 9},
        },
        "evidence_reading": {
            "proven": [
                "56 of 64 virtual-key submissions persisted in measure3",
                "the hardware queue was empty at the one stop",
                "the sampled CPU was returning 'no event' from the product event poll",
                "zero monitor traffic occurred during the 64-key interval",
            ],
            "not_proven": [
                "arrival of each of the 64 submitted keys at $D60A/$D619",
                "a GC transition during the measured interval (no pre-key gc_runs value exists)",
                "a CPU hang or spin inside the collector",
                "which of the two linked event-poll callers owned the sampled frame (stack bytes were not captured)",
            ],
            "gc_note": "gc_runs=9 is cumulative; treating it as a delta would invent a collection witness.",
        },
        "precedent": {
            "partial_fill": "13/34",
            "queue": "empty",
            "PC": "c2_kernal_event_poll+0",
            "gc_delta": 1,
            "bound_reading": "setup/input-delivery failure, not a product GC stall",
        },
        "attribution": {
            "named_site": "c2_kernal_event_poll no-event return at $E033..$E037",
            "mechanism_claim": "unacknowledged virtual-key delivery remains the first unresolved boundary",
            "owner_claim_correction": "The quiet row refutes monitor-crossing as a necessary cause, but it does not convert m65 submission into hardware arrival. The stopped state is idle, not stuck.",
            "register_disposition": "Do not close as a product-stall witness; retain the known issue, but record D1 as transport-unproven partial delivery.",
        },
        "claim_limit": "Artifact/stopped-state attribution only. No device, product byte, fix, GC mechanism or per-key arrival claim.",
    }


def validate_loader_diff(
    ranges: list[dict[str, Any]], expected: list[dict[str, Any]],
    start_address: int,
) -> None:
    observed = [(row["start"], row["bytes"]) for row in ranges]
    bound = [(row["start"], row["bytes"]) for row in expected]
    require(observed == bound, "diagnostic PRG delta drift")
    require(all(int(row["start"], 16) > start_address for row in ranges),
            "diagnostic delta entered startup prefix")


def loader_value() -> dict[str, Any]:
    phase_c = load(PHASE_C)
    phase_d = load(PHASE_D)
    before = CONTROL_PRG.read_bytes()
    after = DIAGNOSTIC_PRG.read_bytes()
    ranges = prg_diff_ranges(before, after)
    control = ElfTruth.read(
        CONTROL_ELF, llvm_readobj=READOBJ, include_section_data=True)
    diagnostic = ElfTruth.read(
        DIAGNOSTIC_ELF, llvm_readobj=READOBJ, include_section_data=True)
    control_start = control.symbol("_start").value
    diagnostic_start = diagnostic.symbol("_start").value
    require(control_start == diagnostic_start == 0x2023,
            "Link-82 entry address drift")
    require(before[:25] == after[:25], "BASIC SYS stub drift")
    require(b"8227" in before[:25], "BASIC SYS target absent")
    require(int(b"8227") == control_start, "BASIC SYS target/ELF entry mismatch")
    validate_loader_diff(
        ranges, phase_c["exact_PRG_byte_differences"], control_start)
    first_delta_offset = int(ranges[0]["file_offset"], 16)
    require(before[:first_delta_offset] == after[:first_delta_offset],
            "diagnostic startup prefix drift")
    require(phase_d["D2_contact_1"]["measured_forms_started"] == 0,
            "contact 1 entered a measured form")
    require(phase_d["D2_contact_2_setup_reserve"]["measured_forms_started"] == 0,
            "contact 2 entered a measured form")
    for runner in (LINK80_RUNNER, LINK82_RUNNER):
        text = runner.read_text(encoding="utf-8")
        require("run:[[:space:]]*$" in text and "run_m65 -t '~M'" in text,
                f"historical RUN-intermediate handling drift: {runner.name}")
    return {
        "format": "lisp65-c2.3-v1.6-defstruct-D2-loader-desk-attribution-v1",
        "recorded_on": date.today().isoformat(),
        "status": "setup-launch-boundary-attributed-product-loader-not-entered",
        "authorities": {
            "owner_commission": bind(OWNER_PLAN),
            "phase_C": bind(PHASE_C),
            "phase_D": bind(PHASE_D),
            "control_ELF": bind(CONTROL_ELF),
            "diagnostic_ELF": bind(DIAGNOSTIC_ELF),
            "control_PRG": bind(CONTROL_PRG),
            "diagnostic_PRG": bind(DIAGNOSTIC_PRG),
            "historical_Link80_runner": bind(LINK80_RUNNER),
            "historical_Link82_runner": bind(LINK82_RUNNER),
            "tool": bind(Path(__file__).resolve()),
        },
        "artifact_truth": {
            "BASIC_load_address": "0x2001",
            "BASIC_SYS_decimal": 8227,
            "ELF_entry": "0x2023",
            "control_and_diagnostic_startup_byteidentical": True,
            "diagnostic_PRG_delta_bytes": sum(row["bytes"] for row in ranges),
            "diagnostic_PRG_delta_ranges": ranges,
            "earliest_delta": ranges[0]["start"],
            "startup_prefix_end_exclusive": ranges[0]["start"],
        },
        "contact_truth": {
            "contact_1": {
                "medium_and_seven_preloads": "byteidentical",
                "screen": "BASIC run: intermediate; command not submitted",
                "measured_forms": 0,
                "mechanism": "missing virtual RETURN in loader launch choreography",
            },
            "contact_2": {
                "medium_and_seven_preloads": "byteidentical",
                "screen": "plain BASIC READY; neither run: nor lisp65>",
                "measured_forms": 0,
                "mechanism_limit": "No PC or entry witness was captured, so non-entry and immediate return cannot be distinguished.",
            },
        },
        "attribution": {
            "named_boundary": "m65 BASIC injection/launch before the Link-82 $2023 entry witness",
            "diagnostic_identity_exoneration": "Every byte through startup and up to the first witness hook at $47C5 is identical to the bound Link-82 control.",
            "product_loader_claim": "not reached on contact 1 and unproved on contact 2",
            "next_method_if_owner_reopens": "Replace screen inference with an entry-PC witness or a byteidentical AUTOBOOT diagnostic medium; do not spend another contact on virtual RUN choreography.",
        },
        "claim_limit": "Host/ELF/setup attribution only. No require/defstruct execution, R/A/I/G row, product-loader defect, device retry or fix is claimed.",
    }


def build() -> tuple[dict[str, Any], dict[str, Any]]:
    return editor_value(), loader_value()


def selftest() -> None:
    phase_d = load(PHASE_D)
    truth = ElfTruth.read(
        LINK88_ELF, llvm_readobj=READOBJ, include_section_data=True)
    poll_start, poll = symbol_bytes(truth, "c2_kernal_event_poll")
    base = phase_d["D1_editor_quiet_typing"]
    mutations = 0
    for name, mutate in (
        ("wrong-fill", lambda row: row["postcondition"].__setitem__("fill", 64)),
        ("wrong-expected", lambda row: row["postcondition"].__setitem__("expected_fill", 56)),
        ("queued-key", lambda row: row["one_stop_packet"].__setitem__("queue_state", 0x80)),
        ("outside-poll", lambda row: row["one_stop_packet"].__setitem__("PC", "0x38f7")),
    ):
        row = deepcopy(base)
        mutate(row)
        try:
            validate_editor_observation(row, poll_start=poll_start, poll_bytes=poll)
        except FirstRed:
            mutations += 1
        else:
            raise FirstRed(f"selftest mutation survived: {name}")
    before = CONTROL_PRG.read_bytes()
    after = DIAGNOSTIC_PRG.read_bytes()
    expected = load(PHASE_C)["exact_PRG_byte_differences"]
    ranges = prg_diff_ranges(before, after)
    for name, mutated in (
        ("drop-range", ranges[:-1]),
        ("startup-delta", [{**ranges[0], "start": "0x2023"}] + ranges[1:]),
    ):
        try:
            validate_loader_diff(mutated, expected, 0x2023)
        except FirstRed:
            mutations += 1
        else:
            raise FirstRed(f"selftest mutation survived: {name}")
    require(mutations == 6, "selftest execution count drift")
    print("c2-v16-phase-d-desk-attribution: SELFTEST PASS mutations=6")


def run() -> None:
    editor, loader = build()
    write(EDITOR_RECEIPT, editor)
    write(LOADER_RECEIPT, loader)
    print("c2-v16-phase-d-desk-attribution: PASS "
          "D1=idle-event-poll-transport-unproven "
          "D2=pre-entry-launch-boundary")


def check() -> None:
    editor, loader = build()
    require(EDITOR_RECEIPT.exists() and EDITOR_RECEIPT.read_bytes() == canonical(editor),
            "editor attribution receipt drift")
    require(LOADER_RECEIPT.exists() and LOADER_RECEIPT.read_bytes() == canonical(loader),
            "loader attribution receipt drift")
    print("c2-v16-phase-d-desk-attribution: PASS "
          "D1=idle-event-poll-transport-unproven "
          "D2=pre-entry-launch-boundary")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    try:
        if action == "run":
            run()
        elif action == "check":
            check()
        elif action == "selftest":
            selftest()
        else:
            print(f"usage: {Path(sys.argv[0]).name} <run|check|selftest>", file=sys.stderr)
            return 2
    except (FirstRed, KeyError, ValueError, OSError) as error:
        print(f"c2-v16-phase-d-desk-attribution: FIRST RED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
