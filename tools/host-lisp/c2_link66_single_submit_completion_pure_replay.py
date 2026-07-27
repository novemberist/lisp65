#!/usr/bin/env python3
"""Pure full-gate replay of immutable First-Red Link 66."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_completion_retry_length_elf_gate as LENGTH  # noqa: E402
import c2_link60_boot_inventory_pure_replay as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"


def configure() -> None:
    BASE.LINK_NUMBER = 66
    BASE.SOURCE = ROOT / (
        "build/c2.2/substitution/"
        "product-link-66-single-submit-completion")
    BASE.PRODUCT = BASE.SOURCE / "lisp65-c2-substitution-linked.prg"
    BASE.ELF = Path(str(BASE.PRODUCT) + ".elf")
    BASE.PROFILE = BASE.SOURCE / "resolved-profile.txt"
    BASE.SOURCE_RECEIPT = EVIDENCE / "c2.2-product-link66-internal.json"
    BASE.OUT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-66-single-submit-completion-pure-replay")
    BASE.RECEIPT = EVIDENCE / (
        "c2.2-product-link66-single-submit-completion-"
        "structural-receipt.json")
    BASE.EXPECTED_PRODUCT_SHA = (
        "482b0b28171515c79ee2c8fd3ad78cea37716887ba06acddac0067db8171f6b4")
    BASE.EXPECTED_SOURCE_STATUS = (
        "FIRST RED: C2-lite real-ABI Link 50 stopped")
    BASE.EXPECTED_SOURCE_DIAGNOSTIC = {
        "message": "final consolidation aggregate/profile gate red",
        "type": "GateError",
    }
    BASE.REQUIRE_SOURCE_PRODUCT_BINDING = False
    BASE.FAILED_PREDECESSOR_PRODUCT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-64-nonlto-stateless-completion-length/"
        "lisp65-c2-substitution-linked.prg")
    BASE.FAILED_PREDECESSOR_RECEIPT = EVIDENCE / (
        "c2.2-product-link64-nonlto-stateless-completion-length-"
        "structural-receipt.json")


def main() -> int:
    configure()
    linked = LENGTH.audit_elf(BASE.ELF)
    abi = ABI.audit_elf(BASE.ELF, require_bank3_chain=True)
    single = linked["linked_dataflow"]["poll"]["single_submit"]
    BASE.require(
        linked["status"]
            == "passed-linked-stateless-mode-derived-completion-length"
        and linked["mutation_count"] == 10
        and linked["phase_mutation_count"] == 6
        and linked["linked_dataflow"][
            "rematerialization_call_count"] == 3
        and len(linked["linked_dataflow"]["structured_call_edges"]) == 4
        and single == {
            "reader_call_count": 1,
            "retry_target_is_after_reader": True,
            "retry_target_is_after_poison": True,
        }
        and abi["status"] == "passed-all-assembler-leaf-abi-contracts"
        and "c2_completion_mode_length"
            in abi["ELF_derived_C_called_inventory"]["C_called_functions"],
        "Link-66 single-submit or leaf ABI gate red")
    result = BASE.main()
    BASE.require(result == 0, "Link-66 pure full-gate replay stopped")

    length_path = BASE.OUT / "c2-single-submit-completion-elf-gate.json"
    length_value = {
        "format": "lisp65-c2-single-submit-completion-ELF-gate-v1",
        "recorded_on": "2026-07-26",
        "status": linked["status"],
        "authority": {
            "contract": BASE.bind(LENGTH.CONTRACT),
            "ELF": BASE.bind(BASE.ELF),
            "gate": BASE.bind(Path(LENGTH.__file__)),
        },
        "result": linked,
    }
    BASE.write_json(length_path, length_value)
    os.chmod(length_path, 0o444)

    abi_path = BASE.OUT / "c2-asm-leaf-abi-dataflow-gate-link66.json"
    BASE.write_json(
        abi_path,
        {
            "format": "lisp65-c2-link66-complete-assembler-ABI-gate-v1",
            "recorded_on": "2026-07-26",
            "status": abi["status"],
            "authority": {
                "ELF": BASE.bind(BASE.ELF),
                "gate": BASE.bind(Path(ABI.__file__)),
            },
            "result": abi,
        })
    os.chmod(abi_path, 0o444)

    os.chmod(BASE.RECEIPT, 0o644)
    receipt = json.loads(BASE.RECEIPT.read_text(encoding="utf-8"))
    receipt["format"] = (
        "lisp65-c2-lite-v6-link66-single-submit-completion-v1")
    receipt["status"] = (
        "passed-link66-single-submit-completion-product-identity-"
        "hardware-not-run")
    receipt["authority"]["link66_replay_driver"] = BASE.bind(Path(__file__))
    receipt["authority"]["write_completion_contract"] = BASE.bind(
        LENGTH.CONTRACT)
    receipt["gates"]["single_submit_completion_ELF"] = linked["status"]
    receipt["gates"]["complete_assembler_leaf_ABI"] = abi["status"]
    receipt["gates"]["all_green"] = True
    receipt["completion_observation"] = {
        "linked_shape":
            "one poison pass; one target read; local comparison retries only",
        "reader_submit_count": 1,
        "retry_edges": linked["linked_dataflow"]["poll"]["retry_edges"],
        "retry_target_after_reader": True,
        "retry_target_after_poison": True,
        "per_attempt_length_rematerializations": 3,
        "linked_mutations_rejected": 10,
        "phase_mutations_rejected": 6,
        "source_mutations_rejected": 25,
        "product_bytes_changed_by_replay": 0,
    }
    receipt["next_gate"] = (
        "prepare nonpromotable Cutpoint-3 episode-latch and Cutpoint-4 "
        "write-completion carriers from this exact Link-66 identity; "
        "request device start before hardware")
    receipt["claim_limit"] = (
        "Structurally complete Link 66 only. Hardware Cutpoints 3/4, C1, "
        "the full matrix, promotion and R4/R5/R6/G5/G6 remain unclaimed.")
    BASE.write_json(BASE.RECEIPT, receipt)
    os.chmod(BASE.RECEIPT, 0o444)
    print(
        "c2-link66-single-submit-completion-replay: COMPLETE "
        f"product={BASE.sha(BASE.PRODUCT)} reader_submits=1 "
        "mutations=25+10+6 compiler=0 linker=0 product-delta=0 hardware=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BASE.ReplayError, RuntimeError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-link66-single-submit-completion-replay: FIRST RED: "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
