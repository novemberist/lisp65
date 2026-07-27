#!/usr/bin/env python3
"""Build Link 66 with single-submit completion observation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_completion_retry_length_elf_gate as LENGTH  # noqa: E402
import c2_link60_two_region_e000_s1_successor_link as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
ELF_GATE_NAME = "c2-single-submit-completion-elf-gate.json"
ABI_GATE_NAME = "c2-asm-leaf-abi-dataflow-gate-link66.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise BASE.Link60Error(f"Link-66 artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write_read_only(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(path, 0o444)


def validate_completion(value: dict[str, Any]) -> bool:
    linked = value["completion"]["linked_gate"]
    single = linked["linked_dataflow"]["poll"]["single_submit"]
    return bool(
        value["status"]
        == "passed-single-submit-local-observation-all-walls-and-gates"
        and value["class_A_gate_correction"][
            "compiler_or_linker_replay"] is False
        and value["class_A_gate_correction"]["product_bytes_changed"] == 0
        and value["class_A_gate_correction"]["current_contract_pin"]
            == "0xb972"
        and value["publish_last"]["total_domain"][
            "declared_domain_bytes"] == 42
        and value["walls"] == {
            "bank0_text_headroom_bytes": 134,
            "ordinary_bank0_bss_headroom_bytes": 161,
            "fixed_hot_block_headroom_bytes": 2,
            "resident_island_headroom_bytes": 443,
            "e000_headroom_bytes": 151,
        }
        and value["runtime_families"][
            "session_main_headroom_bytes"] == 610
        and value["completion"]["source_mutations"] == 25
        and linked["mutation_count"] == 10
        and linked["phase_mutation_count"] == 6
        and single == {
            "reader_call_count": 1,
            "retry_target_is_after_reader": True,
            "retry_target_is_after_poison": True,
        }
        and value["execution_accounting"]["replay_compiler_runs"] == 0
        and value["execution_accounting"]["replay_linker_runs"] == 0)


def configure() -> None:
    BASE.LINK_NUMBER = 66
    BASE.OUT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-66-single-submit-completion")
    BASE.PRODUCT = BASE.OUT / "lisp65-c2-substitution-linked.prg"
    BASE.ELF = Path(str(BASE.PRODUCT) + ".elf")
    BASE.MAP = Path(str(BASE.PRODUCT) + ".map")
    BASE.C2D = (
        BASE.OUT
        / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
    BASE.INTERNAL = EVIDENCE / "c2.2-product-link66-internal.json"
    BASE.BASE_RECEIPT = EVIDENCE / "c2.2-product-link66-base.json"
    BASE.RAW_RECEIPT = EVIDENCE / "c2.2-product-link66-raw.json"
    BASE.REPLAY_OUT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-66-single-submit-completion-read-only-qualification")
    BASE.REPLAY_RECEIPT = EVIDENCE / (
        "c2.2-product-link66-single-submit-completion-"
        "read-only-qualification.json")
    BASE.BASE_RESULT = EVIDENCE / "c2.2-product-link66-base-result.json"
    BASE.FORMAT_RECEIPT = EVIDENCE / (
        "c2.2-product-link66-single-submit-completion-"
        "format-and-stage-gate.json")
    BASE.COMPLETION_SOURCE_RECEIPT = ROOT / (
        "build/c2.2/two-region-session-store/"
        "product-link66-single-submit-completion-"
        "write-completion-source-gate.json")
    BASE.EMITTER_RECEIPT = EVIDENCE / (
        "c2.2-product-link66-single-submit-completion-"
        "emitter-union-gate.json")
    BASE.ISLAND_RECEIPT = EVIDENCE / (
        "c2.2-product-link66-single-submit-completion-"
        "preinstall-source-host-gate.json")
    BASE.QUALIFICATION_RECEIPT = EVIDENCE / (
        "c2.2-product-link66-single-submit-completion-"
        "fresh-qualification.json")
    BASE.RECEIPT = EVIDENCE / (
        "c2.2-product-link66-single-submit-completion-"
        "structural-receipt.json")

    BASE.ARTIFACT_COMPLETION = EVIDENCE / (
        "c2.2-link65-single-submit-completion-"
        "artifact-replay2-receipt.json")
    BASE.ARTIFACT_COMPLETION_SHA = (
        "1321264e98605fa892dd064ea7e0b012175b37e871584efafd83cc70b072d358")
    BASE.WPLTO_PROFILE = ROOT / (
        "build/c2.2/substitution/"
        "link65-single-submit-completion-wplto/resolved-profile.txt")
    BASE.WPLTO_PROFILE_SHA = (
        "d8363476ec433794ad64fa064ec206c4451b347250ea1ff54e03088bee4e4113")

    BASE.FAILED_PREDECESSOR_PRODUCT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-64-nonlto-stateless-completion-length/"
        "lisp65-c2-substitution-linked.prg")
    BASE.FAILED_PREDECESSOR_PRODUCT_SHA = (
        "13c82707ae1797885ff2ddeb7bff62198bf897a9163ed63b7531df8212d49b2c")
    BASE.FAILED_PREDECESSOR_RECEIPT = EVIDENCE / (
        "c2.2-product-link64-nonlto-stateless-completion-length-"
        "structural-receipt.json")


def main() -> int:
    configure()
    length_gate_path = BASE.OUT / ELF_GATE_NAME
    abi_gate_path = BASE.OUT / ABI_GATE_NAME
    original_validate = BASE.validate_artifact_completion
    original_final_main = BASE.FINAL.main

    def qualified_final_main() -> int:
        result = original_final_main()
        BASE.require(result == 0, "Link-66 fresh product closure stopped")
        length = LENGTH.audit_elf(BASE.ELF)
        abi = ABI.audit_elf(
            BASE.ELF, out=abi_gate_path, require_bank3_chain=True)
        single = length["linked_dataflow"]["poll"]["single_submit"]
        BASE.require(
            length["status"]
                == "passed-linked-stateless-mode-derived-completion-length"
            and length["mutation_count"] == 10
            and length["phase_mutation_count"] == 6
            and length["linked_dataflow"][
                "rematerialization_call_count"] == 3
            and len(length["linked_dataflow"][
                "structured_call_edges"]) == 4
            and single == {
                "reader_call_count": 1,
                "retry_target_is_after_reader": True,
                "retry_target_is_after_poison": True,
            }
            and abi["status"]
                == "passed-all-assembler-leaf-abi-contracts"
            and "c2_completion_mode_length"
                in abi["ELF_derived_C_called_inventory"][
                    "C_called_functions"],
            "Link-66 single-submit or complete leaf ABI gate red")
        write_read_only(
            length_gate_path,
            {
                "format":
                    "lisp65-c2-single-submit-completion-ELF-gate-v1",
                "recorded_on": "2026-07-26",
                "status": length["status"],
                "authority": {
                    "contract": bind(LENGTH.CONTRACT),
                    "ELF": bind(BASE.ELF),
                    "gate": bind(Path(LENGTH.__file__)),
                },
                "result": length,
            })
        return result

    try:
        BASE.validate_artifact_completion = validate_completion
        BASE.FINAL.main = qualified_final_main
        result = BASE.main()
    finally:
        BASE.validate_artifact_completion = original_validate
        BASE.FINAL.main = original_final_main

    BASE.require(
        result == 0 and length_gate_path.is_file() and abi_gate_path.is_file(),
        "Link-66 product qualification stopped")
    os.chmod(BASE.RECEIPT, 0o644)
    receipt = json.loads(BASE.RECEIPT.read_text(encoding="utf-8"))
    length = json.loads(
        length_gate_path.read_text(encoding="utf-8"))["result"]
    receipt["format"] = (
        "lisp65-c2-lite-v6-link66-single-submit-completion-v1")
    receipt["status"] = (
        "passed-link66-single-submit-completion-product-identity-"
        "hardware-not-run")
    receipt["authority"]["link66_driver"] = bind(Path(__file__))
    receipt["authority"]["write_completion_contract"] = bind(
        LENGTH.CONTRACT)
    receipt["fresh_gate_program"]["single_submit_completion_ELF"] = bind(
        length_gate_path)
    receipt["fresh_gate_program"]["complete_assembler_leaf_ABI"] = bind(
        abi_gate_path)
    receipt["completion_observation"] = {
        "linked_shape":
            "one poison pass; one target read; local comparison retries only",
        "reader_submit_count": 1,
        "retry_edges": length["linked_dataflow"]["poll"]["retry_edges"],
        "retry_target_after_reader": True,
        "retry_target_after_poison": True,
        "per_attempt_length_rematerializations": 3,
        "linked_mutations_rejected": 10,
        "phase_mutations_rejected": 6,
        "source_mutations_rejected": 25,
        "capacity_delta":
            "measured by the sole WPLTO and this fresh product link",
    }
    receipt["next_gate"] = (
        "prepare nonpromotable Cutpoint-3 episode-latch and Cutpoint-4 "
        "write-completion carriers from this exact Link-66 identity; "
        "request device start before hardware")
    receipt["claim_limit"] = (
        "Structurally complete Link 66 only. Hardware Cutpoints 3/4, C1, "
        "the full matrix, promotion and R4/R5/R6/G5/G6 remain unclaimed.")
    write_read_only(BASE.RECEIPT, receipt)
    print(
        "c2-link66-single-submit-completion: COMPLETE "
        f"product={sha(BASE.PRODUCT)} reader_submits=1 "
        "mutations=25+10+6 hardware=not-run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BASE.Link60Error, BASE.FINAL.FinalMapError, RuntimeError, OSError,
        ValueError, KeyError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-link66-single-submit-completion: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
