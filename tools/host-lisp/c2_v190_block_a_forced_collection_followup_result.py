#!/usr/bin/env python3
"""Bind/check the v1.9 Block-A forced-collection follow-up First Red."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BINDING = ARCH / (
    "c2.3-v1.9-block-a-forced-collection-followup-session-receipt.json")
CAPTURE = ARCH / (
    "c2.3-v1.9-block-a-forced-collection-followup-device-capture.json")
RESULT = ARCH / (
    "c2.3-v1.9-block-a-forced-collection-followup-first-red-receipt.json")
R7_RECEIPT = ARCH / (
    "c2.3-v1.9-native-prompt-editor-display-repair-r7-receipt.json")
SESSION = ROOT / "config/c2-v190-block-a-forced-collection-followup-session.json"
REPORT = ROOT / (
    "docs/planning/v1.9.0-block-a-forced-collection-followup-first-red.md")
PLAN = ROOT / "docs/planning/v1.9.0-pre-plan.md"
PLAN_HEADER = "## Block A forced-collection follow-up First Red — 2026-08-30"
R7_SOURCE = ROOT / (
    "build/c2.3/v1.9-native-prompt-editor-display-repair-r7-preflight/"
    "sources/stdlib-read-line.lisp")
R7_ELF = ROOT / (
    "build/c2.3/v1.9-native-prompt-editor-display-repair-r7/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
VM = ROOT / "src/vm.c"
INTERRUPT = ROOT / "src/interrupt.c"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
STATUS = "FIRST RED: FINAL R7 READ-LINE ARMS CAPTURE BUT CONSUMES PUBLIC QUEUE"


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def section_bind(path: Path, header: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    require(text.count(header) == 1, f"section drift: {header}")
    section = header + text.split(header, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    raw = section.encode()
    return {"path": path.relative_to(ROOT).as_posix(), "section": header,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def source_chain() -> dict[str, Any]:
    source = R7_SOURCE.read_text(encoding="utf-8")
    vm = VM.read_text(encoding="utf-8")
    interrupt = INTERRUPT.read_text(encoding="utf-8")
    state = "(state (list head head head 0 0 0 columns row))"
    route = """(if (nthcdr 8 state)
                    (%rl-render nil 0 0 0 0 -1)
                    (key-event 1))"""
    require(source.count(state) == 1 and source.count(route) == 1,
            "final r7 client state/route drift")
    require("(poke 255 141 0)" in source
            and "(dotimes (counter 4 nil)" in source
            and source.count("(poke 255 141 255)") == 2,
            "final r7 arm/origin/disarm drift")
    require("if (mode == 2 || mode == 3)" in vm
            and "c2_kernal_input_take((uint8_t)mode)" in vm
            and "(void)lisp_input_event(1u, 0u, &event);" in vm
            and "uint8_t lisp_input_event(uint8_t blocking" in interrupt
            and "c2_kernal_event_poll(event)" in interrupt,
            "final native key-event route drift")
    return {
        "delivered_state_cells": 8,
        "ring_selector": "(nthcdr 8 state)",
        "ring_selector_value": "NIL",
        "selected_route": "public blocking key-event 1",
        "public_native_sink": "lisp_input_event -> c2_kernal_event_poll",
        "private_ring_route": "key-event mode 2 -> c2_kernal_input_take",
        "private_ring_route_selected": False,
        "capture_armed": True,
        "sources": {"editor": bind(R7_SOURCE), "vm": bind(VM),
                    "interrupt": bind(INTERRUPT)},
    }


def derive() -> dict[str, Any]:
    binding = load(BINDING)
    session = load(SESSION)
    capture = load(CAPTURE)
    r7 = load(R7_RECEIPT)
    truth = ElfTruth.read(R7_ELF, llvm_readobj=READOBJ)
    addresses = {name: truth.symbol(name).value for name in (
        "C2K_INPUT_EVENTS_RAW", "C2K_INPUT_EVENTS_SEEN",
        "C2K_INPUT_EVENTS_STORED", "C2K_INPUT_EVENTS_TAKEN")}
    decoded = capture["capture"]["decoded"]
    expected = session["counter_witness"]["event_arithmetic"][
        "expected_each_modulo_256"]
    lifecycle = r7["final_product"]["v1_8_native_line_editor_client"][
        "client"]
    require(binding["status"] ==
            "PASS: BLOCK-A FORCED-COLLECTION FOLLOW-UP BOUND"
            and capture["format"] ==
                "lisp65-c2-v190-block-a-forced-collection-followup-device-capture-v2"
            and session["controller"]["expected_numeric_oracle"] == 7
            and session["collection_derivation"]["bound_printable_insertions"]
                == 199
            and session["collection_derivation"]["nursery_cells"] == 192
            and capture["owner_observation"]["numeric_oracle_visible"] == 7
            and capture["owner_observation"]["state_observed_after_monitor_exit"] == {
                "evaluation_output": "(7 nil)", "live_prompt_returned": True,
                "active_cursor_visible": True,
                "interpretation": ("the bounded wait completed and "
                    "evaluation returned normally")}
            and capture["choreography"] == {"stop_requests": 1, "reads": 1,
                "explicit_resume_commands": 0,
                "CPU_left_stopped_after_monitor_exit": False,
                "post_monitor_execution_observed": True,
                "keyboard_events_after_oracle": 0}
            and decoded == {"raw": 2, "seen": 2,
                            "stored": 2, "taken": 0}
            and lifecycle["entry_closed_then_zeroed_then_armed"] is True
            and lifecycle["normal_return_disarms"] is True,
            "follow-up authority/device observation drift")
    require(addresses == {"C2K_INPUT_EVENTS_RAW": 0xBCFC,
            "C2K_INPUT_EVENTS_SEEN": 0xBCFD,
            "C2K_INPUT_EVENTS_STORED": 0xBCFE,
            "C2K_INPUT_EVENTS_TAKEN": 0xBCFF},
            "counter address drift")
    chain = source_chain()
    return {
        "format": "lisp65-c2-v190-block-a-forced-collection-followup-first-red-v2",
        "recorded_on": "2026-08-30", "status": STATUS,
        "authority": {"binding": bind(BINDING), "session": bind(SESSION),
            "r7_card": bind(R7_RECEIPT), "report": bind(REPORT),
            "plan_result_section": section_bind(PLAN, PLAN_HEADER)},
        "device": {"capture": bind(CAPTURE), "numeric_oracle": 7,
            "counter_addresses": {name: f"0x{value:04X}"
                for name, value in addresses.items()},
            "expected": {"raw": expected, "seen": expected,
                         "stored": expected, "taken": expected},
            "observed": decoded,
            "explicit_resume_commands": 0,
            "CPU_left_stopped_after_monitor_exit": False,
            "post_monitor_completion": {
                "evaluation_output": "(7 nil)",
                "live_prompt_returned": True,
                "active_cursor_visible": True}},
        "collection": {"printable_insertions": 199,
            "nursery_cells": 192, "heap_cells_per_printable": 1,
            "forced_during_armed_read_line": True,
            "numeric_oracle_passed": True},
        "mechanism": {
            "classification": "FINAL-CLIENT-CONSUMER-ABSENT",
            "chain": chain,
            "device_signature": "raw=seen=stored=2; taken=0",
            "interpretation": ("the armed IRQ stored two queue events while "
                "the delivered editor took none from the ring"),
            "gate_blind_spot": ("armed lifecycle was proved on the final "
                "wrapper; consumer selection was measured in a different "
                "state shape"),
            "rule": "a delivered client proves both arm and actual final-world consumption",
        },
        "decision": {"Block_B_hardware": "PASS",
            "Block_A_hardware": "FIRST-RED-NOT-ACCEPTED",
            "v1_5_fast_typing_known_issue": "REMAINS-OPEN",
            "fix_authorized": False, "new_link_authorized": False,
            "new_media_authorized": False,
            "new_device_contact_authorized": False},
        "claim_limit": {"proves": ["owner completed bounded stimulus",
                "numeric result is 7", "at least one collection occurred",
                "two ring events were stored and none were taken",
                "delivered r7 client selects public queue input"],
            "does_not_prove": ["general device input losslessness",
                "platform-level loss", "Block A acceptance"]},
        "next": "review disposition on one final-client consumption repair; no action implied",
    }


def verify(value: dict[str, Any]) -> None:
    require(value == derive(), "Block-A follow-up First Red drift")
    require(value["device"]["observed"]["stored"] == 2
            and value["device"]["observed"]["taken"] == 0
            and value["mechanism"]["chain"]["private_ring_route_selected"]
                is False
            and value["decision"]["Block_A_hardware"] ==
                "FIRST-RED-NOT-ACCEPTED"
            and value["decision"]["fix_authorized"] is False,
            "Block-A First Red overclaim")


def selftest() -> None:
    base = derive()
    cases = {
        "invent-equal-counters": lambda x: x["device"]["observed"].update(taken=2),
        "invent-expected-counters": lambda x: x["device"]["observed"].update(
            raw=136, seen=136, stored=136, taken=136),
        "invent-ring-selection": lambda x: x["mechanism"]["chain"].update(
            private_ring_route_selected=True),
        "accept-Block-A": lambda x: x["decision"].update(Block_A_hardware="PASS"),
        "retire-known-issue": lambda x: x["decision"].update(
            v1_5_fast_typing_known_issue="PENSIONED"),
        "authorize-fix": lambda x: x["decision"].update(fix_authorized=True),
        "invent-explicit-resume": lambda x: x["device"].update(
            explicit_resume_commands=1),
        "invent-left-stopped": lambda x: x["device"].update(
            CPU_left_stopped_after_monitor_exit=True),
        "erase-collection": lambda x: x["collection"].update(
            forced_during_armed_read_line=False),
    }
    rejected = []
    for name, mutate in cases.items():
        value = copy.deepcopy(base)
        mutate(value)
        try:
            verify(value)
        except ResultError:
            rejected.append(name)
    require(rejected == list(cases), "Block-A First Red mutation survived")
    print(f"v1.9 Block-A follow-up First Red: SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "emit":
        sys.stdout.buffer.write(canonical(derive()))
    elif action == "check":
        verify(load(RESULT))
        print("v1.9 Block-A follow-up First Red: CHECK PASS consumer=absent")
    elif action == "selftest":
        selftest()
    else:
        raise ResultError("usage: emit|check|selftest")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.9 Block-A follow-up First Red: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
