#!/usr/bin/env python3
"""Build Link 63 with record-owned completion retry length."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_completion_retry_length_elf_gate as LENGTH_ELF  # noqa: E402
import c2_link60_two_region_e000_s1_successor_link as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
ELF_GATE_NAME = "c2-completion-retry-length-elf-gate.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise BASE.Link60Error(f"Link-63 artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write_read_only(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(path, 0o444)


def validate_completion(value: dict[str, Any]) -> bool:
    return bool(
        value["status"]
        == "passed-canonical-retry-length-WPLTO-all-walls-and-gates-green"
        and value["class_A_historical_pin_correction"][
            "compiler_or_linker_replay"] is False
        and value["class_A_historical_pin_correction"][
            "product_bytes_changed"] == 0
        and value["class_A_historical_pin_correction"][
            "current_contract_pin"] == "0xb972"
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
            "mutation_count"] == 4
        and value["completion_retry_length"]["source_mutations"] == 22
        and value["execution_accounting"]["replay_compiler_runs"] == 0
        and value["execution_accounting"]["replay_linker_runs"] == 0
    )


def configure() -> None:
    BASE.LINK_NUMBER = 63
    BASE.OUT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-63-canonical-completion-length")
    BASE.PRODUCT = BASE.OUT / "lisp65-c2-substitution-linked.prg"
    BASE.ELF = Path(str(BASE.PRODUCT) + ".elf")
    BASE.MAP = Path(str(BASE.PRODUCT) + ".map")
    BASE.C2D = (
        BASE.OUT
        / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
    BASE.INTERNAL = EVIDENCE / "c2.2-product-link63-internal.json"
    BASE.BASE_RECEIPT = EVIDENCE / "c2.2-product-link63-base.json"
    BASE.RAW_RECEIPT = EVIDENCE / "c2.2-product-link63-raw.json"
    BASE.REPLAY_OUT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-63-canonical-completion-length-read-only-qualification")
    BASE.REPLAY_RECEIPT = EVIDENCE / (
        "c2.2-product-link63-canonical-completion-length-"
        "read-only-qualification.json")
    BASE.BASE_RESULT = EVIDENCE / "c2.2-product-link63-base-result.json"
    BASE.FORMAT_RECEIPT = EVIDENCE / (
        "c2.2-product-link63-canonical-completion-length-"
        "format-and-stage-gate.json")
    BASE.COMPLETION_SOURCE_RECEIPT = ROOT / (
        "build/c2.2/two-region-session-store/"
        "product-link63-canonical-completion-length-"
        "write-completion-source-gate.json")
    BASE.EMITTER_RECEIPT = EVIDENCE / (
        "c2.2-product-link63-canonical-completion-length-"
        "emitter-union-gate.json")
    BASE.ISLAND_RECEIPT = EVIDENCE / (
        "c2.2-product-link63-canonical-completion-length-"
        "preinstall-source-host-gate.json")
    BASE.QUALIFICATION_RECEIPT = EVIDENCE / (
        "c2.2-product-link63-canonical-completion-length-"
        "fresh-qualification.json")
    BASE.RECEIPT = EVIDENCE / (
        "c2.2-product-link63-canonical-completion-length-"
        "structural-receipt.json")

    BASE.ARTIFACT_COMPLETION = EVIDENCE / (
        "c2.2-link63-canonical-completion-length-"
        "artifact-replay-receipt.json")
    BASE.ARTIFACT_COMPLETION_SHA = (
        "2c11423b7543e97bca616263d7a20da7c26a9f25e9ad849ed4f6692d28c00a38")
    BASE.WPLTO_PROFILE = ROOT / (
        "build/c2.2/substitution/"
        "link63-canonical-completion-length-wplto/resolved-profile.txt")
    BASE.WPLTO_PROFILE_SHA = (
        "53a7aca6011ce5379f611286c726554be900122a5438f9bb7a1d969d22f8a1f3")

    BASE.FAILED_PREDECESSOR_PRODUCT = ROOT / (
        "build/c2.2/substitution/product-link-62-post-shelf-region1/"
        "lisp65-c2-substitution-linked.prg")
    BASE.FAILED_PREDECESSOR_PRODUCT_SHA = (
        "85fc3cad0eded7fd6a9079194a25b59415d86f2eb99ccec7d684ac756a831b3f")
    BASE.FAILED_PREDECESSOR_RECEIPT = EVIDENCE / (
        "c2.2-link62-slot39-threshold-length-liveness-replay-receipt.json")


def main() -> int:
    configure()
    gate_path = BASE.OUT / ELF_GATE_NAME
    original_validate = BASE.validate_artifact_completion
    original_final_main = BASE.FINAL.main

    def qualified_final_main() -> int:
        result = original_final_main()
        BASE.require(result == 0, "Link-63 fresh product closure stopped")
        gate = LENGTH_ELF.audit_elf(BASE.ELF)
        BASE.require(
            gate["status"]
            == "passed-linked-record-owned-retry-length-and-scratch-clobber-pin"
            and gate["mutation_count"] == 4
            and gate["linked_dataflow"]["reload_count"] == 2
            and gate["linked_dataflow"]["retry_edge_count"] == 2,
            "Link-63 completion retry-length linked gate red",
        )
        write_read_only(
            gate_path,
            {
                "format":
                    "lisp65-c2-completion-retry-length-ELF-gate-v1",
                "recorded_on": "2026-07-24",
                "status": gate["status"],
                "authority": {
                    "contract": bind(LENGTH_ELF.CONTRACT),
                    "ELF": bind(BASE.ELF),
                    "gate": bind(Path(LENGTH_ELF.__file__)),
                },
                "result": gate,
            },
        )
        return result

    try:
        BASE.validate_artifact_completion = validate_completion
        BASE.FINAL.main = qualified_final_main
        result = BASE.main()
    finally:
        BASE.validate_artifact_completion = original_validate
        BASE.FINAL.main = original_final_main

    BASE.require(result == 0 and gate_path.is_file(),
                 "Link-63 product qualification stopped")
    os.chmod(BASE.RECEIPT, 0o644)
    receipt = json.loads(BASE.RECEIPT.read_text(encoding="utf-8"))
    receipt["format"] = (
        "lisp65-c2-lite-v6-link63-canonical-completion-length-v1")
    receipt["status"] = (
        "passed-link63-canonical-completion-length-product-identity-"
        "hardware-not-run")
    receipt["authority"]["link63_driver"] = bind(Path(__file__))
    receipt["authority"]["retry_length_contract"] = bind(
        LENGTH_ELF.CONTRACT)
    receipt["fresh_gate_program"]["completion_retry_length_ELF"] = bind(
        gate_path)
    receipt["completion_retry_length"] = {
        "authority": "verified record byte 27",
        "reload_policy":
            "reload before every attempt and after every nested Bank-5 read",
        "linked_reload_count": 2,
        "linked_retry_edges": 2,
        "linked_mutations_rejected": 4,
        "source_mutations_rejected": 22,
        "capacity_delta":
            "measured by the sole WPLTO and this fresh product link",
    }
    receipt["next_gate"] = (
        "prepare nonpromotable Cutpoint-3 episode-latch and Cutpoint-4 "
        "write-completion carriers from this exact Link-63 identity; "
        "request device start before hardware")
    receipt["claim_limit"] = (
        "Structurally complete Link 63 only. Hardware Cutpoints 3/4, C1, "
        "the full matrix, promotion and R4/R5/R6/G5/G6 remain unclaimed.")
    write_read_only(BASE.RECEIPT, receipt)
    print(
        "c2-link63-completion-length: COMPLETE "
        f"product={sha(BASE.PRODUCT)} reloads=2 mutations=4 "
        "hardware=not-run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BASE.Link60Error, BASE.FINAL.FinalMapError, RuntimeError, OSError,
        ValueError, KeyError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-link63-completion-length: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
