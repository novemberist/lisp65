#!/usr/bin/env python3
"""Build Link 64 with the non-LTO stateless completion-length leaf."""

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
ELF_GATE_NAME = "c2-stateless-completion-length-elf-gate.json"
ABI_GATE_NAME = "c2-asm-leaf-abi-dataflow-gate-link64.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise BASE.Link60Error(f"Link-64 artifact absent: {path}")
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
    return bool(
        value["status"]
        == "passed-non-LTO-stateless-completion-length-all-walls-and-gates"
        and value["class_A_gate_correction"][
            "compiler_or_linker_replay"] is False
        and value["class_A_gate_correction"]["product_bytes_changed"] == 0
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
        and value["completion_retry_length"]["ELF_gate"][
            "mutation_count"] == 9
        and value["completion_retry_length"]["source_mutations"] == 24
        and value["execution_accounting"]["replay_compiler_runs"] == 0
        and value["execution_accounting"]["replay_linker_runs"] == 0)


def configure() -> None:
    BASE.LINK_NUMBER = 64
    BASE.OUT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-64-nonlto-stateless-completion-length")
    BASE.PRODUCT = BASE.OUT / "lisp65-c2-substitution-linked.prg"
    BASE.ELF = Path(str(BASE.PRODUCT) + ".elf")
    BASE.MAP = Path(str(BASE.PRODUCT) + ".map")
    BASE.C2D = (
        BASE.OUT
        / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
    BASE.INTERNAL = EVIDENCE / "c2.2-product-link64-internal.json"
    BASE.BASE_RECEIPT = EVIDENCE / "c2.2-product-link64-base.json"
    BASE.RAW_RECEIPT = EVIDENCE / "c2.2-product-link64-raw.json"
    BASE.REPLAY_OUT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-64-nonlto-stateless-completion-length-"
        "read-only-qualification")
    BASE.REPLAY_RECEIPT = EVIDENCE / (
        "c2.2-product-link64-nonlto-stateless-completion-length-"
        "read-only-qualification.json")
    BASE.BASE_RESULT = EVIDENCE / "c2.2-product-link64-base-result.json"
    BASE.FORMAT_RECEIPT = EVIDENCE / (
        "c2.2-product-link64-nonlto-stateless-completion-length-"
        "format-and-stage-gate.json")
    BASE.COMPLETION_SOURCE_RECEIPT = ROOT / (
        "build/c2.2/two-region-session-store/"
        "product-link64-nonlto-stateless-completion-length-"
        "write-completion-source-gate.json")
    BASE.EMITTER_RECEIPT = EVIDENCE / (
        "c2.2-product-link64-nonlto-stateless-completion-length-"
        "emitter-union-gate.json")
    BASE.ISLAND_RECEIPT = EVIDENCE / (
        "c2.2-product-link64-nonlto-stateless-completion-length-"
        "preinstall-source-host-gate.json")
    BASE.QUALIFICATION_RECEIPT = EVIDENCE / (
        "c2.2-product-link64-nonlto-stateless-completion-length-"
        "fresh-qualification.json")
    BASE.RECEIPT = EVIDENCE / (
        "c2.2-product-link64-nonlto-stateless-completion-length-"
        "structural-receipt.json")

    BASE.ARTIFACT_COMPLETION = EVIDENCE / (
        "c2.2-link64-nonlto-stateless-completion-length-"
        "artifact-replay-receipt.json")
    BASE.ARTIFACT_COMPLETION_SHA = (
        "bd06f4ab048b47c5ea67342fb1e3601443b9008274b8dad30a15c38a72c31dfd")
    BASE.WPLTO_PROFILE = ROOT / (
        "build/c2.2/substitution/"
        "link64-nonlto-stateless-completion-length-wplto/"
        "resolved-profile.txt")
    BASE.WPLTO_PROFILE_SHA = (
        "b21c72cf7c17db913890ac87c4b18975e8a7f0ec36803bcf5f7cfbb64afeb141")

    BASE.FAILED_PREDECESSOR_PRODUCT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-63-canonical-completion-length/"
        "lisp65-c2-substitution-linked.prg")
    BASE.FAILED_PREDECESSOR_PRODUCT_SHA = (
        "46f93f1bd890761af55fd1170349e841d3f8c906edff2f59ef12a96f40362fe6")
    BASE.FAILED_PREDECESSOR_RECEIPT = EVIDENCE / (
        "c2.2-product-link63-canonical-completion-length-"
        "structural-receipt.json")


def main() -> int:
    configure()
    length_gate_path = BASE.OUT / ELF_GATE_NAME
    abi_gate_path = BASE.OUT / ABI_GATE_NAME
    original_validate = BASE.validate_artifact_completion
    original_final_main = BASE.FINAL.main

    def qualified_final_main() -> int:
        result = original_final_main()
        BASE.require(result == 0, "Link-64 fresh product closure stopped")
        length = LENGTH.audit_elf(BASE.ELF)
        abi = ABI.audit_elf(
            BASE.ELF, out=abi_gate_path, require_bank3_chain=True)
        BASE.require(
            length["status"]
                == "passed-linked-stateless-mode-derived-completion-length"
            and length["mutation_count"] == 9
            and length["linked_dataflow"][
                "rematerialization_call_count"] == 3
            and len(length["linked_dataflow"][
                "structured_call_edges"]) == 4
            and abi["status"]
                == "passed-all-assembler-leaf-abi-contracts"
            and "c2_completion_mode_length"
                in abi["ELF_derived_C_called_inventory"][
                    "C_called_functions"],
            "Link-64 stateless length or complete leaf ABI gate red")
        write_read_only(
            length_gate_path,
            {
                "format":
                    "lisp65-c2-stateless-completion-length-ELF-gate-v1",
                "recorded_on": "2026-07-25",
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
        "Link-64 product qualification stopped")
    os.chmod(BASE.RECEIPT, 0o644)
    receipt = json.loads(BASE.RECEIPT.read_text(encoding="utf-8"))
    receipt["format"] = (
        "lisp65-c2-lite-v6-link64-nonlto-stateless-completion-length-v1")
    receipt["status"] = (
        "passed-link64-nonlto-stateless-completion-length-product-"
        "identity-hardware-not-run")
    receipt["authority"]["link64_driver"] = bind(Path(__file__))
    receipt["authority"]["completion_length_contract"] = bind(
        LENGTH.CONTRACT)
    receipt["fresh_gate_program"]["stateless_completion_length_ELF"] = bind(
        length_gate_path)
    receipt["fresh_gate_program"]["complete_assembler_leaf_ABI"] = bind(
        abi_gate_path)
    receipt["completion_retry_length"] = {
        "authority":
            "completion mode rematerialized by a named 27-byte non-LTO leaf",
        "linked_leaf": {
            "symbol": "c2_completion_mode_length",
            "section": ".lisp65_rt_c2append_header",
            "bytes": 27,
            "direct_poll_edges": 4,
        },
        "per_attempt_rematerializations": 3,
        "linked_mutations_rejected": 9,
        "source_mutations_rejected": 24,
        "retired_record_27_references": 0,
        "capacity_delta":
            "measured by the sole WPLTO and this fresh product link",
    }
    receipt["next_gate"] = (
        "prepare nonpromotable Cutpoint-3 episode-latch and Cutpoint-4 "
        "write-completion carriers from this exact Link-64 identity; "
        "request device start before hardware")
    receipt["claim_limit"] = (
        "Structurally complete Link 64 only. Hardware Cutpoints 3/4, C1, "
        "the full matrix, promotion and R4/R5/R6/G5/G6 remain unclaimed.")
    write_read_only(BASE.RECEIPT, receipt)
    print(
        "c2-link64-nonlto-completion: COMPLETE "
        f"product={sha(BASE.PRODUCT)} rematerializations=3 "
        "mutations=9 hardware=not-run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BASE.Link60Error, BASE.FINAL.FinalMapError, RuntimeError, OSError,
        ValueError, KeyError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-link64-nonlto-completion: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
