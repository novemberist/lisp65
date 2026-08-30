#!/usr/bin/env python3
"""Bind/check the v1.9 Block-A forced-collection follow-up contact."""

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
PLAN = ROOT / "docs/planning/v1.9.0-pre-plan.md"
PLAN_HEADER = (
    "## Reviewer ruling — Block A forced-collection row, redesigned — 2026-08-28")
REPORT = ROOT / "docs/planning/v1.9.0-block-a-forced-collection-followup.md"
SESSION = ROOT / "config/c2-v190-block-a-forced-collection-followup-session.json"
RECEIPT = ARCH / (
    "c2.3-v1.9-block-a-forced-collection-followup-session-receipt.json")
MEDIA_RECEIPT = ARCH / (
    "c2.3-v1.9-blocks-ab-display-r7-acceptance-media-receipt.json")
DEVICE_RESULT = ARCH / (
    "c2.3-v1.9-blocks-ab-display-r7-device-result-receipt.json")
CARD = ARCH / (
    "c2.3-v1.9-native-prompt-editor-display-repair-r7-receipt.json")
INPUT_CONTRACT = ROOT / "config/c2-v160-input-service-hybrid-contract.json"
ELF = ROOT / (
    "build/c2.3/v1.9-native-prompt-editor-display-repair-r7/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
MEDIA = ROOT / (
    "build/c2.3/v1.9-blocks-ab-display-r7-acceptance-media/shared-system/"
    "lisp65-product.d81")

FORMAT = "lisp65-c2-v190-block-a-forced-collection-followup-session-v1"
STATUS = "READY: OWNER BLOCK-A FORCED-COLLECTION FOLLOW-UP"
PATTERN = "01234567012345670123456701234567"
PASSES = 6
FINAL_TEXT = "abcdefg"
CONTROLLER = (
    "(progn (setq s (read-line)) (print (string-length s)) (wait 16383))")
NURSERY_CELLS = 192
CELLS_PER_PRINTABLE = 1
PRINTABLE_INSERTIONS = PASSES * len(PATTERN) + len(FINAL_TEXT)
DELETE_EVENTS = PASSES * len(PATTERN)
RETURN_EVENTS = 1
PHYSICAL_EVENTS = PRINTABLE_INSERTIONS + DELETE_EVENTS + RETURN_EVENTS
COUNTER_MODULUS = 256
EXPECTED_COUNTER = PHYSICAL_EVENTS % COUNTER_MODULUS


class FollowupError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FollowupError(message)


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


def counter_addresses() -> dict[str, str]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    names = {
        "raw": "C2K_INPUT_EVENTS_RAW",
        "seen": "C2K_INPUT_EVENTS_SEEN",
        "stored": "C2K_INPUT_EVENTS_STORED",
        "taken": "C2K_INPUT_EVENTS_TAKEN",
    }
    return {key: f"0x{truth.symbol(symbol).value:04X}"
            for key, symbol in names.items()}


def facts() -> dict[str, Any]:
    card = load(CARD)
    contract = load(INPUT_CONTRACT)
    media = load(MEDIA_RECEIPT)
    result = load(DEVICE_RESULT)
    product = card["final_product"]
    client = product["v1_8_native_line_editor_client"]["client"]
    response = product["hybrid"]["responsiveness"]
    manifest = load(ROOT / client["manifest"]["path"])
    functions = set(manifest["functions"])
    addresses = counter_addresses()
    require(
        contract["responsiveness"]["nursery_cells"] == NURSERY_CELLS
        and response["heap_cells_per_character"] == CELLS_PER_PRINTABLE
        and client["entry_closed_then_zeroed_then_armed"] is True
        and client["normal_return_disarms"] is True
        and {"read-line", "string-length", "print", "wait"} <= functions,
        "r7 allocation/lifecycle/controller authority drift")
    require(
        media["media"]["product"]["sha256"] == bind(MEDIA)["sha256"]
        == "9bc5d45db0c0280ce8f067856dee98ed1cc14aec256398c5e93eb1b56bb06412"
        and result["decision"]["Block_B_hardware"] == "PASS"
        and result["decision"]["Block_A_forced_collection_device_subclaim"]
            == "NOT-CLAIMED"
        and addresses == {"raw": "0xBCFC", "seen": "0xBCFD",
                           "stored": "0xBCFE", "taken": "0xBCFF"},
        "media/predecessor/counter authority drift")
    require(len(CONTROLLER) == 67 and len(PATTERN) == 32
            and PRINTABLE_INSERTIONS == 199
            and PRINTABLE_INSERTIONS * CELLS_PER_PRINTABLE > NURSERY_CELLS
            and PHYSICAL_EVENTS == 392 and EXPECTED_COUNTER == 136,
            "follow-up arithmetic drift")
    return {"card": card, "contract": contract, "media": media,
            "result": result, "client": client, "response": response,
            "addresses": addresses}


def derive_session() -> dict[str, Any]:
    current = facts()
    per_pass = {
        "text": PATTERN,
        "printable_insertions": len(PATTERN),
        "delete_backward_events": len(PATTERN),
        "visible_groups": [PATTERN[index:index + 8]
                           for index in range(0, len(PATTERN), 8)],
    }
    return {
        "format": FORMAT, "recorded_on": "2026-08-30", "status": STATUS,
        "claim_scope": {
            "accepts": ["v1.9-Block-A-lossless-input-across-device-collection"],
            "already_closed": ["v1.9-Block-B-native-prompt-editor"],
            "excludes": ["Comfort", "Matcher/Blink", "Block-C", "Block-D",
                         "$22-closure", "Ship", "publication"],
            "green_consequence": (
                "Block A hardware-accepted; v1.5 fast-typing Known Issue pensioned"),
        },
        "artifact_world": {
            "product_medium": {**bind(MEDIA), "remote_name": "V19R7P.D81"},
            "ELF": bind(ELF), "r7_card": bind(CARD),
            "media_receipt": bind(MEDIA_RECEIPT),
            "predecessor_device_result": bind(DEVICE_RESULT),
            "optional_libraries": [], "product_changes": 0,
        },
        "collection_derivation": {
            "historical_four_cell_assumption_rejected": True,
            "delivered_r7_heap_cells_per_printable": CELLS_PER_PRINTABLE,
            "nursery_cells": NURSERY_CELLS,
            "required_printable_insertions_independent_of_incoming_phase": 193,
            "bound_printable_insertions": PRINTABLE_INSERTIONS,
            "proof": "199 * 1 > 192; at least one collection while read-line capture is armed",
            "single_origin_required": True,
        },
        "controller": {
            "form": CONTROLLER, "form_characters_before_counter_origin": len(CONTROLLER),
            "purpose": (
                "nested read-line owns the measured origin; print gives the numeric oracle; "
                "wait keeps counters stable before the next prompt can re-zero them"),
            "wait_frames": 16383, "expected_numeric_oracle": len(FINAL_TEXT),
        },
        "stimulus": {
            "passes": PASSES, "per_pass": per_pass,
            "pace": {"passes_1_to_2": "ordinary", "passes_3_to_6": "fast"},
            "delete_discipline": (
                "exactly four sets of eight individual Delete/Backspace presses; "
                "no hold/repeat; row must be blank after the 32nd"),
            "final_text": FINAL_TEXT, "maximum_simultaneous_test_text": len(PATTERN),
            "return_events": RETURN_EVENTS,
        },
        "counter_witness": {
            "addresses": current["addresses"], "order": ["raw", "seen", "stored", "taken"],
            "origin": "atomic zero at nested read-line entry while capture tail is closed",
            "width_bits": 8, "modulus": COUNTER_MODULUS,
            "event_arithmetic": {
                "printable_insertions": PRINTABLE_INSERTIONS,
                "delete_backward": DELETE_EVENTS, "return": RETURN_EVENTS,
                "physical_events": PHYSICAL_EVENTS, "wraps": PHYSICAL_EVENTS // 256,
                "expected_each_modulo_256": EXPECTED_COUNTER,
            },
            "green": "raw=seen=stored=taken=136 and visible numeric oracle=7",
        },
        "choreography": {
            "fresh_BASIC_first": True, "product_medium_only": True,
            "owner_keyboard_only_after_boot": True,
            "post_boot_automated_access_before_final_stop": 0,
            "stops": 1, "resumes_after_stop": 0,
        },
        "steps": [
            {"id": "A-FC-1", "action": (
                "cold boot V19R7P.D81 alone and wait for the live lisp65> prompt"),
             "expect": "normal r7 native prompt; no optional library"},
            {"id": "A-FC-2", "action": f"enter exactly {CONTROLLER} and press Return",
             "expect": "a fresh blank nested read-line row appears"},
            {"id": "A-FC-3", "action": (
                f"six times type exactly {PATTERN}; verify its four 8-character "
                "groups; after each pass press Delete/Backspace exactly 32 times "
                "as four counted groups of eight until the row is blank"),
             "expect": (
                "passes 1-2 ordinary and 3-6 fast; every token is exact and the "
                "row becomes blank exactly on deletion 32")},
            {"id": "A-FC-4", "action": f"type {FINAL_TEXT} and press Return",
             "expect": "7 is printed and no new prompt appears while wait is active"},
            {"id": "A-FC-5", "action": (
                "leave the keyboard untouched; Codex stops the CPU once and reads "
                "$BCFC..$BCFF read-only"),
             "expect": "four bytes are 88 88 88 88 (hex), i.e. 136 each; no resume"},
        ],
        "decision_table": {
            "oracle-7-and-136=136=136=136": (
                "Block A hardware-accepted; v1.5 fast-typing Known Issue pensioned"),
            "visible-token-or-delete-count-mismatch": "device input-loss red",
            "raw<136": "physical/core before queue-present observation",
            "raw>seen": "IRQ queue read or filtering",
            "seen>stored": "ring admission/write",
            "stored>taken": "consumer/take",
            "equal-but-not-136": "session choreography/count invalid; no product verdict",
        },
        "claim_limit": (
            "Typing inside one delivered read-line capture lifetime only; type-ahead "
            "during evaluation is not claimed."),
    }


def verify_session(value: dict[str, Any]) -> None:
    require(value == derive_session(), "Block-A follow-up session drift")
    derivation = value["collection_derivation"]
    counters = value["counter_witness"]["event_arithmetic"]
    require(
        derivation["delivered_r7_heap_cells_per_printable"] == 1
        and derivation["bound_printable_insertions"] > derivation["nursery_cells"]
        and value["stimulus"]["maximum_simultaneous_test_text"] == 32
        and counters["physical_events"] == 392
        and counters["expected_each_modulo_256"] == 136
        and value["choreography"]["resumes_after_stop"] == 0,
        "Block-A follow-up wall drift")


def derive_receipt() -> dict[str, Any]:
    verify_session(load(SESSION))
    return {
        "format": "lisp65-c2-v190-block-a-forced-collection-followup-binding-v1",
        "recorded_on": "2026-08-30",
        "status": "PASS: BLOCK-A FORCED-COLLECTION FOLLOW-UP BOUND",
        "authority": {"review_ruling": section_bind(PLAN, PLAN_HEADER),
                      "report": bind(REPORT)},
        "session": bind(SESSION),
        "correction": {
            "rejected": "six times ten under historical four-cells-per-key assumption",
            "reason": "r7 final-world consumer allocates one heap cell per printable",
            "replacement": "six 32-character type/delete passes plus seven final characters",
            "single_counter_origin": True,
        },
        "arithmetic": {
            "nursery": 192, "cells_per_printable": 1,
            "printable_insertions": 199, "forced_collection": True,
            "physical_events": 392, "counter_width": 8,
            "expected_counter_modulo": 136,
        },
        "contact": {"media_builds": 0, "WPLTO": 0, "links": 0,
                    "device_contacts_authorized": 1,
                    "final_reads": [{"start": "0xBCFC", "bytes": 4}],
                    "resumes_after_final_read": 0},
        "next": "owner says ready; deploy same r7 medium and execute only A-FC-1..5",
    }


def verify_receipt(value: dict[str, Any]) -> None:
    require(value == derive_receipt(), "Block-A follow-up receipt drift")


def selftest() -> None:
    base = derive_session()
    cases = {
        "restore-historical-four-cell-world": lambda x: x[
            "collection_derivation"].update(delivered_r7_heap_cells_per_printable=4),
        "six-ten-character-passes": lambda x: x[
            "collection_derivation"].update(bound_printable_insertions=67),
        "omit-single-origin": lambda x: x[
            "collection_derivation"].update(single_origin_required=False),
        "hide-counter-wrap": lambda x: x["counter_witness"][
            "event_arithmetic"].update(wraps=0),
        "wrong-counter-remainder": lambda x: x["counter_witness"][
            "event_arithmetic"].update(expected_each_modulo_256=392),
        "resume-after-final-read": lambda x: x["choreography"].update(
            resumes_after_stop=1),
        "load-optional-library": lambda x: x["artifact_world"].update(
            optional_libraries=["v16core"]),
        "drop-numeric-oracle": lambda x: x["controller"].update(
            expected_numeric_oracle=None),
    }
    rejected = []
    for name, mutate in cases.items():
        value = copy.deepcopy(base)
        mutate(value)
        try:
            verify_session(value)
        except FollowupError:
            rejected.append(name)
    require(rejected == list(cases), "Block-A follow-up mutation survived")
    print(f"v1.9 Block-A collection follow-up: SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "write":
        require(not SESSION.exists() and not RECEIPT.exists(),
                "Block-A follow-up binding already exists")
        SESSION.write_bytes(canonical(derive_session()))
        verify_session(load(SESSION))
        RECEIPT.write_bytes(canonical(derive_receipt()))
        verify_receipt(load(RECEIPT))
        print("v1.9 Block-A collection follow-up: WRITE PASS contact=ready")
    elif action == "check":
        verify_session(load(SESSION))
        verify_receipt(load(RECEIPT))
        print("v1.9 Block-A collection follow-up: CHECK PASS contact=ready")
    elif action == "selftest":
        selftest()
    else:
        raise FollowupError("usage: write|check|selftest")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.9 Block-A collection follow-up: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
