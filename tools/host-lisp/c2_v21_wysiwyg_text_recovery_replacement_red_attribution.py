#!/usr/bin/env python3
"""Attribute the consumed Link-116 WYSIWYG replacement-card Final Red."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RED = ARCH / (
    "c2.3-v2.1-wysiwyg-text-recovery-replacement-card-final-red.json")
PRICING = ARCH / "c2.3-v2.1-wysiwyg-text-recovery-pricing-receipt.json"
LINK115 = ARCH / "c2.3-v2.1-wysiwyg-input-card-red-attribution-receipt.json"
PLACEMENT = ARCH / (
    "c2.3-v2.1-terminal-screen-map-authority-rebind-receipt.json")
WYSIWYG = ARCH / "c2.3-v2.1-wysiwyg-input-receipt.json"
OLD_CARD = ROOT / "tools/host-lisp/c2_v21_wysiwyg_input_card.py"
BUILD = ROOT / "build/c2.3/v2.1-wysiwyg-text-recovery-replacement-card/wplto"
ELF = BUILD / "lisp65-c2-substitution-linked.prg.elf"
MAP = BUILD / "lisp65-c2-substitution-linked.prg.map"
PROFILE = BUILD / "resolved-profile.txt"
PRODUCER = ROOT / (
    "build/c2.3/v2.1-wysiwyg-text-recovery-replacement-card/producer-result.json")
RECEIPT = ARCH / (
    "c2.3-v2.1-wysiwyg-text-recovery-replacement-card-red-attribution-receipt.json")
DRIVER = Path(__file__).resolve()
REPL = ROOT / "src/repl.c"
LLVM = ROOT / "tools/llvm-mos/bin"
FORMAT = "lisp65-c2.3-v2.1-wysiwyg-text-recovery-replacement-red-attribution-v1"
STATUS = "FINAL-RED-ATTRIBUTED: CAPACITY GREEN; PRIOR-WORLD PLACEMENT PIN"
RECORDED_ON = "2026-08-17"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


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


def symbol_bytes(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    raw = truth.section_bytes(symbol.section)
    at = symbol.value - section.address
    require(0 <= at and at + symbol.bytes <= len(raw),
            f"symbol outside section: {name}")
    return raw[at:at + symbol.bytes]


def derive() -> dict[str, Any]:
    red, pricing, link115 = load(RED), load(PRICING), load(LINK115)
    placement, producer = load(PLACEMENT), load(PRODUCER)
    require(red["status"] == "FINAL RED: Link-116 replacement returns to owner"
            and red["retry_authorized"] is False
            and red["owner_disposition_required"] is True
            and red["attempt_accounting"] == {"cards_authorized": 1,
                "cards_consumed": 1, "WPLTO_runs": 1,
                "product_link_attempts": 1, "completion_runs": 0,
                "media_builds": 0, "device_contacts": 0}
            and "candidate-derived placement contract does not match linked ELF"
                in red["error"]["message"],
            "Link-116 Final Red/card accounting drift")
    require(pricing["status"] ==
                "PRICED: 42-BYTE SEMANTIC MICRO-RECOVERY WINS"
            and link115["capacity"]["ordinary_text_deficit_bytes"] == 13
            and placement["status"] ==
                "PASS: MAP authority loudly rebound across screen-only byte"
            and producer["status"] == "PASS",
            "pricing/linked-producer authority drift")

    truth = ElfTruth.read(ELF, llvm_readobj=LLVM / "llvm-readobj",
                          include_section_data=True)
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    reader = truth.symbol("c2_map_cpu_read")
    repl = truth.symbol("repl")
    raw = symbol_bytes(truth, "repl")
    abort = truth.symbol("lisp_abort_code").value
    expected = placement["semantic_equivalence"]["placement_price"]
    actual_end = text.address + text.bytes
    actual_reserve = facade.address - actual_end
    failed_end = link115["capacity"]["candidate_seed_map"][
        "ordinary_text_end_exclusive"]
    recovery = failed_end - actual_end
    require(reader.value == 0x2277 and reader.bytes == 189
            and expected["expected_linked_bytes"] == reader.bytes
            and expected["expected_reserve_bytes"] == 1
            and actual_end == 0xB3A5 and actual_reserve == 11
            and failed_end == 0xB3BD and recovery == 24
            and recovery >= link115["capacity"]
                ["minimum_recovery_before_any_replacement_card_bytes"]
            and facade.address == 0xB3B0 and facade.bytes == 98
            and repl.value == 0xAA48 and repl.bytes == 696,
            "linked capacity/placement attribution drift")

    source_sha = hashlib.sha256(REPL.read_bytes()).hexdigest()
    profile = PROFILE.read_text(encoding="utf-8")
    visible = bytes((0xA9, 0x05, 0x20, abort & 0xFF, abort >> 8))
    a0_dataflow = bytes.fromhex("a220c0a0d0034c96ac")
    classifier = bytes.fromhex("2960d0034cc1aa")
    require(visible in raw and a0_dataflow in raw and classifier in raw
            and f"input_sha256=src/repl.c:{source_sha}" in profile,
            "linked WYSIWYG machine semantics/source consumption drift")

    old_gate = OLD_CARD.read_text(encoding="utf-8")
    historical_shape_matches = any(
        raw[index:index + 2] == b"\xC9\xA0"
        and b"\xA9\x20" in raw[index + 2:index + 18]
        for index in range(max(0, len(raw) - 1)))
    require('raw[index:index + 2] == b"\\xC9\\xA0"' in old_gate
            and 'b"\\xA9\\x20" in raw[index + 2:index + 18]' in old_gate
            and historical_shape_matches is False
            and b"\xC0\xA0" in raw and b"\xA2\x20" in raw,
            "latent machine-shape pin attribution drift")

    value = {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "classification": {
            "kind": "POST-LINK VERIFIER IDENTITY PIN",
            "stage": "producer successor placement gate before Scope/Acceptance",
            "WPLTO_green": True, "product_link_green": True,
            "lower_producer_green": True, "Scope_run": False,
            "Acceptance_run": False, "product_capacity_stop": False,
        },
        "capacity_result": {
            "Link115_failed_end_exclusive": "0xb3bd",
            "Link116_end_exclusive": "0xb3a5",
            "facade_start": "0xb3b0", "facade_bytes": facade.bytes,
            "final_recovery_bytes": recovery,
            "required_recovery_bytes": 13,
            "final_headroom_bytes": actual_reserve,
            "repl_bytes": repl.bytes,
            "mapped_far_facade_moved": False,
            "contracted_margins_used_as_freight": False,
            "result": "CAPACITY WALL CLEARED BY 11 BYTES",
        },
        "first_stopper": {
            "consumer": "c2_v21_candidate_derived_local_return.linked_gate",
            "reader_identity": {"expected_bytes": 189, "actual_bytes": 189,
                                "match": True},
            "prior_world_expectation": {"text_end_exclusive": "0xb3af",
                                        "ordinary_reserve_bytes": 1},
            "candidate_reality": {"text_end_exclusive": "0xb3a5",
                                  "ordinary_reserve_bytes": 11},
            "difference": {"text_shrank_bytes": 10,
                           "reserve_grew_bytes": 10},
            "mechanism": (
                "The consumer inherits the terminal-screen candidate's measured "
                "text end/reserve as a contract. The authorized WYSIWYG micro "
                "reduction legitimately changes both while leaving reader and "
                "fixed facade identities exact."),
        },
        "linked_WYSIWYG": {
            "consumed_source_sha256": source_sha,
            "repl_machine_bytes": repl.bytes,
            "visible_reader_error": True,
            "a0_to_space": {"compare": "CPY #$A0", "value": "LDX #$20",
                            "store": "STX __rc20 then echo/store"},
            "control_classifier": "AND #$60 then visible abort",
            "host_regressions": bind(WYSIWYG),
        },
        "latent_post_stopper": {
            "kind": "MACHINE-INSTRUCTION-SHAPE PIN",
            "reached": False,
            "consumer": "c2_v21_wysiwyg_input_card.linked_wysiwyg",
            "historical_shape": ["CMP #$A0", "LDA #$20"],
            "candidate_shape": ["CPY #$A0", "LDX #$20"],
            "semantic_result": "same A0-to-space dataflow",
            "why_recorded": (
                "An artifact-only continuation would otherwise encounter a "
                "second verifier pin after correcting the first stopper."),
        },
        "card_disposition": {
            "cards_authorized": 1, "cards_consumed": 1,
            "retry_authorized": False, "owner_disposition_required": True,
            "Completion_allowed": False, "media_allowed": False,
            "device_allowed": False,
            "narrowest_evidenced_direction": (
                "Derive text end/reserve from the linked candidate while keeping "
                "reader and facade contracts fixed; make the WYSIWYG linked gate "
                "validate semantic dataflow rather than opcodes. Only an owner-"
                "authorized artifact-only Scope/Acceptance continuation may test "
                "the frozen linked SHAs; no relink is implied."),
        },
        "authority": {
            "Final_Red": bind(RED), "pricing": bind(PRICING),
            "Link115_attribution": bind(LINK115),
            "prior_placement_contract": bind(PLACEMENT),
            "linked_ELF": bind(ELF), "linked_map": bind(MAP),
            "resolved_profile": bind(PROFILE), "producer_result": bind(PRODUCER),
            "old_machine_gate": bind(OLD_CARD), "repl": bind(REPL),
            "checker": bind(DRIVER),
        },
        "claim_limit": (
            "Read-only Final-Red attribution. The linked capacity and machine "
            "semantics are bound; Scope, Acceptance, Completion, media and device "
            "claims remain absent."),
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT and value["status"] == STATUS,
            "attribution identity drift")
    classification = value["classification"]
    capacity = value["capacity_result"]
    stopper = value["first_stopper"]
    latent = value["latent_post_stopper"]
    disposition = value["card_disposition"]
    require(classification["kind"] == "POST-LINK VERIFIER IDENTITY PIN"
            and classification["WPLTO_green"] is True
            and classification["product_link_green"] is True
            and classification["lower_producer_green"] is True
            and classification["Scope_run"] is False
            and classification["Acceptance_run"] is False
            and classification["product_capacity_stop"] is False,
            "Final-Red classification drift")
    require(capacity["final_recovery_bytes"] == 24
            and capacity["required_recovery_bytes"] == 13
            and capacity["final_headroom_bytes"] == 11
            and capacity["facade_bytes"] == 98
            and capacity["mapped_far_facade_moved"] is False
            and capacity["contracted_margins_used_as_freight"] is False,
            "linked capacity result drift")
    require(stopper["reader_identity"]["match"] is True
            and stopper["difference"] == {"text_shrank_bytes": 10,
                                           "reserve_grew_bytes": 10},
            "first-stopper identity drift")
    require(value["linked_WYSIWYG"]["visible_reader_error"] is True
            and value["linked_WYSIWYG"]["a0_to_space"]["compare"] == "CPY #$A0"
            and latent["kind"] == "MACHINE-INSTRUCTION-SHAPE PIN"
            and latent["reached"] is False
            and latent["semantic_result"] == "same A0-to-space dataflow",
            "linked/latent WYSIWYG attribution drift")
    require(disposition["cards_authorized"] == 1
            and disposition["cards_consumed"] == 1
            and disposition["retry_authorized"] is False
            and disposition["owner_disposition_required"] is True
            and disposition["Completion_allowed"] is False
            and disposition["media_allowed"] is False
            and disposition["device_allowed"] is False,
            "owner/card boundary drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "call-capacity-red": lambda x: x["classification"].update(
            product_capacity_stop=True),
        "erase-WPLTO": lambda x: x["classification"].update(WPLTO_green=False),
        "claim-Scope": lambda x: x["classification"].update(Scope_run=True),
        "recover-twelve": lambda x: x["capacity_result"].update(
            final_recovery_bytes=12),
        "invent-headroom": lambda x: x["capacity_result"].update(
            final_headroom_bytes=29),
        "move-facade": lambda x: x["capacity_result"].update(
            mapped_far_facade_moved=True),
        "spend-margin": lambda x: x["capacity_result"].update(
            contracted_margins_used_as_freight=True),
        "reader-mismatch": lambda x: x["first_stopper"][
            "reader_identity"].update(match=False),
        "erase-difference": lambda x: x["first_stopper"].update(
            difference={"text_shrank_bytes": 0, "reserve_grew_bytes": 0}),
        "weaken-visible-error": lambda x: x["linked_WYSIWYG"].update(
            visible_reader_error=False),
        "claim-latent-reached": lambda x: x["latent_post_stopper"].update(
            reached=True),
        "claim-opcode-semantics": lambda x: x["latent_post_stopper"].update(
            semantic_result="different"),
        "authorize-retry": lambda x: x["card_disposition"].update(
            retry_authorized=True),
        "open-media": lambda x: x["card_disposition"].update(
            media_allowed=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "replacement attribution mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    value = derive()
    value["mutations_rejected"] = mutations(value)
    if action == "record":
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        require(load(RECEIPT) == value, "replacement attribution receipt stale")
    else:
        require(len(value["mutations_rejected"]) == 14,
                "mutation count drift")
    print("WYSIWYG replacement attribution: PASS "
          f"action={action} recovery=24 headroom=11 mutations=14")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"WYSIWYG replacement attribution: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
