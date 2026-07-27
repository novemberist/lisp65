#!/usr/bin/env python3
"""Validate the owner-commissioned C2 KERNAL-unmap contract."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-kernal-unmap-contract.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2-kernal-unmap-contract-receipt.json"
)


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_receipt() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(receipt.get("format") ==
            "lisp65-c2-kernal-unmap-contract-receipt-v1",
            "receipt format drift")
    require(receipt.get("status") ==
            "passed-contract-bounded-probe-authorized-link-not-authorized",
            "receipt status drift")
    for name, row in receipt["bindings"].items():
        path = ROOT / row["path"]
        require(path.is_file() and not path.is_symlink(),
                f"receipt binding is not a regular file: {name}")
        require(path.stat().st_size == row["bytes"],
                f"receipt byte count drift: {name}")
        require(sha256(path) == row["sha256"],
                f"receipt SHA drift: {name}")
    result = receipt["gate_result"]
    require(result == {
        "command": "make c2-kernal-unmap-contract-check",
        "offline_receipt_command":
            "make c2-kernal-unmap-contract-receipt-check",
        "status": "passed",
        "gross_bytes": 8192,
        "deficit_bytes": 3639,
        "replacement_categories": 7,
        "continuity_invariants": 2,
        "negative_cases": 25,
        "mutations_rejected": 13,
        "product_bytes": 0,
    }, "receipt gate-result drift")
    workspace = receipt["workspace_boundary"]
    require(workspace["product_source_files_changed_by_this_contract_block"] == [],
            "receipt claims product-source changes")
    require(workspace["product_artifacts_emitted_by_this_contract_block"] == 0,
            "receipt claims product artifacts")


def validate(value: dict) -> None:
    require(value.get("format") == "lisp65-c2-kernal-unmap-contract-v1",
            "format drift")
    require(value.get("version") == 1, "version drift")
    require(value.get("status") ==
            "link36-first-red-automatic-c2-lite-selected",
            "status drift")

    authority = value["authority"]
    reference = authority["hardware_reference"]
    reference_path = ROOT / reference["path"]
    require(sha256(reference_path) == reference["sha256"],
            "pinned hardware-reference SHA drift")
    require(reference["printed_to_pdf_pages"] == {
        "map_and_kernal": [[9, 23], [10, 24], [11, 25]],
        "vic_raster_irq": [[50, 64], [51, 65]],
        "typed_event_queue": [[102, 116], [103, 117], [104, 118]],
    }, "printed/PDF page binding drift")

    facts = value["hardware_facts"]
    require(facts["cpu_window"] == "0xe000..0xffff", "window drift")
    require(facts["gross_bytes"] == 8192, "gross size drift")
    require(facts["typed_event"] == {
        "queue_and_event_modifiers": "0xd60a",
        "petscii_and_dequeue": "0xd619",
        "rule": "capture code and event-time modifiers from one queue head, then dequeue exactly once",
    }, "typed-event register contract drift")
    require(facts["frame_irq_candidate"]["raster_compare"] == "0xd012"
            and facts["frame_irq_candidate"]["irq_flag_ack"] == "0xd019"
            and facts["frame_irq_candidate"]["irq_mask"] == "0xd01a",
            "raster-IRQ candidate drift")

    capacity = value["capacity_model"]
    categories = capacity["replacement_categories"]
    require(capacity["gross_window_bytes"] == 8192, "gross model drift")
    require(capacity["fixed_resident_deficit_bytes"] == 3639,
            "fixed deficit drift")
    require(len(categories) == 7 and len(set(categories)) == 7,
            "replacement-category census drift")
    require(set(categories) == {
        "typed_queue_driver", "irq_handler", "nmi_and_freezer_return",
        "frame_source", "map_switch_and_guards",
        "post_startup_output_seam", "alignment_and_vectors",
    }, "replacement-category identity drift")
    probe_values = capacity["probe_values"]
    require(probe_values == {
        "replacement_resident_bytes": 490,
        "future_margin_bytes": 4063,
        "actual_live_window_bytes": 7806,
        "actual_future_margin_bytes": 386,
    }, "historical Link-28 capacity evidence drift")
    require(capacity["equation"] ==
            "future_margin_bytes = 8192 - 3639 - replacement_resident_bytes",
            "net equation drift")

    terminal = value["formal_reopening_2026_07_21"]["final_floor_rule"]
    require(terminal["bytes"] == 63 and terminal["previous_bytes"] == 115
            and terminal["authorized_debit_bytes"] == 52,
            "terminal floor arithmetic drift")
    require(terminal["retry_window_section"] ==
            ".lisp65_c2_kernal_window.crc_retry"
            and terminal["retry_window_vma"] == "0xff44"
            and terminal["retry_window_bytes"] == 52,
            "terminal retry tenant drift")
    require(terminal["facade_vector_count"] == 16
            and terminal["crc_leaf_facade_vector"] == {
                "symbol": "c2_facade_rtov_crc_mem",
                "address": "0xb5f1", "bytes": 3},
            "terminal retry facade drift")
    require("automatically selects C2-lite" in
            terminal["future_resident_growth"],
            "terminal floor self-trigger drift")
    terminal_receipt = ROOT / terminal["wplto_receipt"]
    require(terminal_receipt.is_file() and
            sha256(terminal_receipt) == terminal["wplto_receipt_sha256"],
            "terminal-floor WPLTO receipt binding drift")
    terminal_result = json.loads(terminal_receipt.read_text(encoding="utf-8"))
    require(terminal_result["status"] ==
            "passed-terminal-floor-package-wplto"
            and terminal_result["measurement"]["walls"]
            ["e000_headroom_bytes"] == 63
            and terminal_result["execution_accounting"]
            ["promotable_product_links"] == 0
            and terminal_result["execution_accounting"]["hardware_runs"] == 0,
            "terminal-floor WPLTO receipt claim drift")
    link36 = value["formal_reopening_2026_07_21"][
        "link36_first_red_2026_07_21"]
    link36_receipt = ROOT / link36["receipt"]
    require(link36_receipt.is_file()
            and sha256(link36_receipt) == link36["receipt_sha256"],
            "Link-36 First-Red receipt binding drift")
    link36_result = json.loads(link36_receipt.read_text(encoding="utf-8"))
    require(link36["resident_overlap_bytes"] == 8
            and link36["product_closure_links"] == 0
            and link36["hardware_runs"] == 0
            and link36_result["status"] ==
            "FIRST RED: terminal-floor Link 36 stopped"
            and link36_result["terminal_floor_disposition"]
            ["selected_successor"] == "C2-lite",
            "Link-36 automatic C2-lite disposition drift")

    machine = value["state_machine"]
    require(machine["ordered_states"] == [
        "firmware-owned", "replacement-armed", "handoff-closed",
        "product-owned",
    ], "ownership state order drift")
    require(machine["freezer_states"] ==
            ["freezer-suspended", "freezer-return"],
            "Freezer state drift")
    rules = machine["transition_rules"]
    for phrase in ("retain the KERNAL", "verified before unmap",
                   "masked only", "before any product instruction",
                   "firmware-owned boot world"):
        require(any(phrase in rule for rule in rules),
                f"missing transition obligation: {phrase}")

    continuity = value["continuity_invariants"]
    require(continuity["run_stop_abort"]["minimum_authoritative_sources"] == 1,
            "RUN/STOP continuity floor drift")
    require("before STKEY 0x91 is retired" in
            continuity["run_stop_abort"]["handoff_rule"],
            "abort handoff ordering drift")
    require(continuity["frame_source"]["minimum_authoritative_sources"] == 1,
            "frame continuity floor drift")
    require("advancing before" in continuity["frame_source"]["handoff_rule"],
            "frame handoff ordering drift")
    require("before the vector is published" in
            continuity["publication_rule"], "vector publication order drift")

    keymap = value["input_and_keymap"]
    require(keymap["event_shape"] == "(key code modifiers)",
            "event shape drift")
    require(keymap["queue_empty_is_not_code_zero"] is True,
            "code-zero collision restored")
    require(keymap["blocking_and_polling_share_one_capture"] is True,
            "input views diverged")
    require(keymap["single_source"] ==
            "config/v11-l-lite-keymap.json evolves through tools/host-lisp/v11_l_lite_keymap.py",
            "generated keymap source drift")
    require(keymap["modifier_binding_authority"] ==
            "config/v11-l-lite-keymap.json#modifier_bindings",
            "modifier binding authority drift")
    require(keymap["end_to_end_gate"] ==
            "tools/host-lisp/c2_l_full_keymap_end_to_end_gate.py"
            and "queue tuple through product normalization" in
            keymap["end_to_end_rule"],
            "keymap end-to-end gate contract drift")
    require(keymap["required_l_full_bindings"] == [
        {"physical": "Control-Space", "command": "set-mark"},
        {"physical": "Meta-x", "command": "execute-command"},
    ], "L-full binding freight drift")
    require(len(keymap["generated_consumers"]) == 6,
            "generated-consumer census drift")

    freedom = value["kernal_freedom_link_gate"]
    require(freedom["owned_section"] == ".lisp65_c2_kernal_window",
            "owned section drift")
    require(freedom["owned_vector_section"] == ".lisp65_c2_vectors",
            "owned vector section drift")
    require(freedom["forbidden_service_targets"] == ["0xffd2", "0xffe4"],
            "KERNAL service target census drift")
    require(freedom["forbidden_state_addresses"] == ["0x0091"],
            "retired state census drift")
    require(len(freedom["rules"]) == 5, "freedom-rule census drift")

    freezer = value["freezer_fidelity"]
    require(freezer["classification"] == "hardware-only",
            "Freezer fidelity drift")
    require("no Freezer safety PASS" in freezer["xemu_claim"],
            "Xemu claim widened")
    require(len(freezer["prechain_smoke"]) == 6,
            "prechain smoke census drift")

    probe = value["bounded_probe"]
    require(probe["artifact_class"] == "isolated non-product proof target",
            "probe artifact class drift")
    require(probe["product_artifacts_emitted"] == 0,
            "contract falsely claims product artifacts")
    require(len(probe["required_outputs"]) == 7,
            "probe-output census drift")
    require("exactly one real substitution link" in probe["next_if_green"],
            "post-probe review boundary drift")
    require("first-red" in probe["next_if_red"],
            "first-red discipline drift")

    negatives = value["required_negative_cases"]
    require(len(negatives) == 28 and len(set(negatives)) == 28,
            "negative-case census drift")
    required_phrases = (
        "unmap before", "retire STKEY", "lose an abort",
        "firmware frame", "vector before", "Freezer return",
        "CHROUT", "GETIN", "STKEY read", "different queue heads",
        "dequeued more than once", "queue empty", "RUN/STOP routed",
        "keymap, test list", "modifier documented", "capacity category",
        "gross 8192", "zero or negative margin", "platform reset", "Xemu",
    )
    for phrase in required_phrases:
        require(any(phrase in item for item in negatives),
                f"missing negative class: {phrase}")


def mutation_tests(value: dict) -> int:
    mutations: list[dict] = []

    def add(path: tuple[str, ...], replacement: object) -> None:
        candidate = copy.deepcopy(value)
        target = candidate
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = replacement
        mutations.append(candidate)

    add(("hardware_facts", "gross_bytes"), 4096)
    add(("hardware_facts", "typed_event", "petscii_and_dequeue"), "0xd610")
    add(("capacity_model", "fixed_resident_deficit_bytes"), 3049)
    add(("capacity_model", "probe_values", "future_margin_bytes"), 4553)
    add(("formal_reopening_2026_07_21", "final_floor_rule", "bytes"), 62)
    add(("formal_reopening_2026_07_21", "link36_first_red_2026_07_21",
         "resident_overlap_bytes"), 7)
    add(("state_machine", "ordered_states"),
        ["firmware-owned", "product-owned"])
    add(("continuity_invariants", "run_stop_abort",
         "minimum_authoritative_sources"), 0)
    add(("continuity_invariants", "frame_source",
         "minimum_authoritative_sources"), 0)
    add(("input_and_keymap", "queue_empty_is_not_code_zero"), False)
    add(("input_and_keymap", "required_l_full_bindings"), [])
    add(("input_and_keymap", "modifier_binding_authority"),
        "config/c2-l-full-keymap-probe.json")
    add(("kernal_freedom_link_gate", "forbidden_service_targets"), ["0xffd2"])
    add(("freezer_fidelity", "classification"), "emulator-valid")
    add(("bounded_probe", "product_artifacts_emitted"), 1)
    bad = copy.deepcopy(value)
    bad["required_negative_cases"].pop()
    mutations.append(bad)

    rejected = 0
    for candidate in mutations:
        try:
            validate(candidate)
        except GateError:
            rejected += 1
    require(rejected == len(mutations),
            "a KERNAL-unmap contract mutation passed")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-receipt", action="store_true")
    args = parser.parse_args()
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    validate(value)
    rejected = mutation_tests(value)
    if args.verify_receipt:
        verify_receipt()
    print("c2-kernal-unmap-contract: PASS "
          "gross=8192 deficit=3639 replacement-categories=7 "
          "continuity-invariants=2 negative-cases=28 "
          f"mutations-rejected={rejected} product-bytes=0"
          + (" receipt=bound" if args.verify_receipt else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
