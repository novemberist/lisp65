#!/usr/bin/env python3
"""Build the one owner-authorized Link 60 product identity."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_two_region_e000_s1_final_wplto as FINAL  # noqa: E402
import c2_lite_v6_link50_persistent_header_successor_link as LINK50  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK_NUMBER = 60
OUT = ROOT / (
    "build/c2.2/substitution/product-link-60-two-region-e000-s1")
PRODUCT = OUT / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
C2D = OUT / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin"
INTERNAL = EVIDENCE / "c2.2-product-link60-internal.json"
BASE_RECEIPT = EVIDENCE / "c2.2-product-link60-base.json"
RAW_RECEIPT = EVIDENCE / "c2.2-product-link60-raw.json"
REPLAY_OUT = ROOT / (
    "build/c2.2/substitution/product-link-60-read-only-qualification")
REPLAY_RECEIPT = EVIDENCE / (
    "c2.2-product-link60-read-only-qualification.json")
BASE_RESULT = EVIDENCE / "c2.2-product-link60-base-result.json"
FORMAT_RECEIPT = EVIDENCE / (
    "c2.2-product-link60-format-and-stage-gate.json")
COMPLETION_SOURCE_RECEIPT = ROOT / (
    "build/c2.2/two-region-session-store/"
    "link60-write-completion-source-gate.json")
EMITTER_RECEIPT = EVIDENCE / (
    "c2.2-product-link60-emitter-union-gate.json")
ISLAND_RECEIPT = EVIDENCE / (
    "c2.2-product-link60-preinstall-source-host-gate.json")
QUALIFICATION_RECEIPT = EVIDENCE / (
    "c2.2-product-link60-fresh-qualification.json")
RECEIPT = EVIDENCE / (
    "c2.2-product-link60-two-region-e000-s1-structural-receipt.json")
ARTIFACT_COMPLETION = EVIDENCE / (
    "c2.2-two-region-e000-s1-link60-artifact-completion2-receipt.json")
ARTIFACT_COMPLETION_SHA = (
    "1749bea8b6f0f18896de8a7eaa6ca8c2142ecec426513b3c73eb2242eff255e6")
WPLTO_PROFILE = ROOT / (
    "build/c2.2/substitution/"
    "two-region-session-store-e000-s1-final-wplto4/resolved-profile.txt")
WPLTO_PROFILE_SHA = (
    "69ccc94c681eb2e1be5c51906e5d5d472cbdbc8c53abb9e283e4d0e4f862c314")
BASELINE = ROOT / (
    "build/c2.2/substitution/product-link-59-c1-freezer-irq-episode/"
    "lisp65-c2-substitution-linked.prg")
BASELINE_SHA = (
    "b46ab695a803f993e206f48f87e6ce310de1e6e56ca897bf07900502697000e6")
BASELINE_RECEIPT = EVIDENCE / (
    "c2.2-product-link59-c1-freezer-irq-episode-structural-receipt.json")
KERNAL_CONTRACT = ROOT / "config/c2-kernal-unmap-contract.json"
REGION_CONTRACT = ROOT / "config/c2-two-region-session-store-contract.json"
FAILED_PREDECESSOR_PRODUCT: Path | None = None
FAILED_PREDECESSOR_PRODUCT_SHA: str | None = None
FAILED_PREDECESSOR_RECEIPT: Path | None = None


class Link60Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise Link60Error(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"Link-60 artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write_receipt(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(path, 0o444)


def feature_preflight() -> dict[str, Any]:
    rows = [
        line.split("=", 1)[1]
        for line in WPLTO_PROFILE.read_text(encoding="utf-8").splitlines()
        if line.startswith("feature_defines=")
    ]
    require(len(rows) == 1, "Link-60 WPLTO has no unique feature row")
    expected = tuple(rows[0].split(","))
    actual = FINAL.BASE.transformed_features(
        FINAL.BASE.FUSION.PROFILE.resolved_features())
    journal_feature = FINAL.BASE.FUSION.FUSION.FEATURE
    require(
        journal_feature not in actual,
        "Link-60 journal/prepare profile feature is duplicated",
    )
    actual = (*actual, journal_feature)
    require(
        actual == expected
        and "LISP65_RUNTIME_OVERLAY_FORMAT_V4" in actual
        and "LISP65_RUNTIME_OVERLAY_FORMAT_V3" not in actual
        and "LISP65_C2_TWO_REGION_SESSION_STORE" in actual,
        "Link-60 driver feature profile differs from WPLTO authority",
    )
    return {
        "status": "passed-same-canonical-feature-profile",
        "feature_count": len(actual),
        "profile_sha256": sha(WPLTO_PROFILE),
        "format": "L65R-v4-only",
    }


def configure_current_pin_adapters() -> None:
    """Move the active inherited Link-50 adapter to Link-60 authority.

    Link-50 itself remains historical.  The current driver must override both
    the adapter's public pin and the Link-49 layer it configures before the
    generic product closure starts.
    """
    LINK50.VERIFIER_BASE = 0xB972
    LINK50.BASE.VERIFIER_BASE = 0xB972
    require(
        LINK50.VERIFIER_BASE == LINK50.BASE.VERIFIER_BASE == 0xB972,
        "Link-60 inherited publish-last adapter pin drift",
    )


def canonical_profile_rows(path: Path) -> tuple[str, ...]:
    rows: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256=build/") and (
                "/generated-product-sources/" in line):
            _prefix, rest = line.split(
                "/generated-product-sources/", 1)
            line = "input_sha256=<generated-product-sources>/" + rest
        rows.append(line)
    return tuple(rows)


def validate_artifact_completion(completion: dict[str, Any]) -> bool:
    """Validate the qualified WPLTO authority consumed by this link driver.

    Successor wrappers may replace this predicate when a later, independently
    bound WPLTO replay adds gates while retaining the same measured geometry.
    The Link-60 default remains exact and unchanged.
    """
    return bool(
        completion["status"]
        == "passed-owner-repinned-artifact-completion-all-gates-green"
        and completion["owner_repin"]["current_address"] == "0xb972"
        and completion["publish_last"]["total_domain"][
            "declared_domain_bytes"] == 42
        and completion["walls"] == {
            "bank0_text_headroom_bytes": 134,
            "ordinary_bank0_bss_headroom_bytes": 161,
            "fixed_hot_block_headroom_bytes": 2,
            "resident_island_headroom_bytes": 443,
            "e000_headroom_bytes": 151,
        }
        and completion["runtime_families"][
            "session_main_headroom_bytes"] == 610
        and completion["execution_accounting"][
            "completion_compiler_runs"] == 0
        and completion["execution_accounting"][
            "completion_linker_runs"] == 0
    )


def configure_paths() -> None:
    FINAL.OUT = OUT
    FINAL.INTERNAL = INTERNAL
    FINAL.BASE_RECEIPT = BASE_RECEIPT
    FINAL.RAW_RECEIPT = RAW_RECEIPT
    FINAL.REPLAY_OUT = REPLAY_OUT
    FINAL.REPLAY_RECEIPT = REPLAY_RECEIPT
    FINAL.BASE_RESULT = BASE_RESULT
    FINAL.FORMAT_RECEIPT = FORMAT_RECEIPT
    FINAL.COMPLETION_SOURCE_RECEIPT = COMPLETION_SOURCE_RECEIPT
    FINAL.EMITTER_RECEIPT = EMITTER_RECEIPT
    FINAL.ISLAND_RECEIPT = ISLAND_RECEIPT
    FINAL.RECEIPT = QUALIFICATION_RECEIPT
    FINAL.PRODUCT = PRODUCT
    FINAL.ELF = ELF
    FINAL.MAP = MAP
    FINAL.C2D = C2D
    FINAL.RUNNER_PATH = Path(__file__)


def main() -> int:
    one_shot = (
        OUT, INTERNAL, BASE_RECEIPT, RAW_RECEIPT, REPLAY_OUT,
        REPLAY_RECEIPT, BASE_RESULT, FORMAT_RECEIPT,
        COMPLETION_SOURCE_RECEIPT, EMITTER_RECEIPT, ISLAND_RECEIPT,
        QUALIFICATION_RECEIPT, RECEIPT,
    )
    require(
        not any(path.exists() for path in one_shot),
        "Link 60 is one-shot",
    )
    require(
        ARTIFACT_COMPLETION.is_file()
        and sha(ARTIFACT_COMPLETION) == ARTIFACT_COMPLETION_SHA
        and WPLTO_PROFILE.is_file()
        and sha(WPLTO_PROFILE) == WPLTO_PROFILE_SHA
        and BASELINE.is_file()
        and sha(BASELINE) == BASELINE_SHA
        and BASELINE_RECEIPT.is_file()
        and KERNAL_CONTRACT.is_file()
        and REGION_CONTRACT.is_file(),
        "Link-60 authority SHA or rollback identity drift",
    )
    if FAILED_PREDECESSOR_PRODUCT is not None:
        require(
            FAILED_PREDECESSOR_PRODUCT_SHA is not None
            and FAILED_PREDECESSOR_RECEIPT is not None
            and FAILED_PREDECESSOR_PRODUCT.is_file()
            and sha(FAILED_PREDECESSOR_PRODUCT)
                == FAILED_PREDECESSOR_PRODUCT_SHA
            and FAILED_PREDECESSOR_RECEIPT.is_file(),
            f"Link-{LINK_NUMBER} failed-predecessor authority drift",
        )
    completion = json.loads(ARTIFACT_COMPLETION.read_text(encoding="utf-8"))
    baseline_receipt = json.loads(
        BASELINE_RECEIPT.read_text(encoding="utf-8"))
    require(
        validate_artifact_completion(completion)
        and baseline_receipt["status"]
        == "passed-link59-C1-IRQ-episode-product-identity-hardware-not-run"
        and baseline_receipt["product_identity"]["product"]["sha256"]
        == BASELINE_SHA,
        "Link-60 completed WPLTO or rollback authority is incomplete",
    )
    profile = feature_preflight()
    configure_current_pin_adapters()
    configure_paths()
    result = FINAL.main()
    require(result == 0, "Link-60 fresh product closure stopped")

    qualified = json.loads(
        QUALIFICATION_RECEIPT.read_text(encoding="utf-8"))
    base = json.loads(BASE_RESULT.read_text(encoding="utf-8"))
    raw = json.loads(RAW_RECEIPT.read_text(encoding="utf-8"))
    format_gate = json.loads(FORMAT_RECEIPT.read_text(encoding="utf-8"))
    product_link = json.loads(
        (OUT / "product-substitution-link.json").read_text(encoding="utf-8"))
    session = json.loads(
        (OUT / "runtime-overlays-session-final.json").read_text(
            encoding="utf-8"))
    boot = json.loads(
        (OUT / "runtime-overlays-boot-final.json").read_text(
            encoding="utf-8"))
    verifier = json.loads(
        (OUT / "runtime-verifier-publish-last.json").read_text(
            encoding="utf-8"))
    publish = json.loads(
        (OUT / "total-publish-last-domain.json").read_text(
            encoding="utf-8"))
    resolved_sha = sha(OUT / "resolved-profile.txt")
    profile_equal = (
        canonical_profile_rows(OUT / "resolved-profile.txt")
        == canonical_profile_rows(WPLTO_PROFILE))
    walls = raw["walls"]
    capacity = raw["capacity"]
    overflow = session["overflow_storage"]
    fixed = json.loads(
        (OUT / "fixed-block-rtov-fail-final.json").read_text(
            encoding="utf-8"))

    require(
        qualified["status"] == "passed-final-map-all-walls-and-gates-green"
        and qualified["execution_accounting"][
            "whole_program_LTO_closure_links"] == 1
        and base["status"].startswith("passed")
        and format_gate["status"].startswith("passed")
        and format_gate["stage_source_authority"]["status"].startswith(
            "passed")
        and product_link["status"] == "passed"
        and product_link["product_closure_link_count"] == 1
        and profile_equal
        and sha(PRODUCT) != BASELINE_SHA
        and walls == {
            "bank0_text_headroom_bytes": 134,
            "ordinary_bank0_bss_headroom_bytes": 161,
            "fixed_hot_block_headroom_bytes": 2,
            "resident_island_headroom_bytes": 443,
            "e000_headroom_bytes": 151,
        }
        and int(capacity["session_family_bytes"]) == 64926
        and int(capacity["session_family_headroom_bytes"]) == 610
        and int(session["storage"]["size"]) == 64926
        and int(overflow["used"]) == 1956
        and int(overflow["capacity"]) == 2032
        and verifier["address"] == 0xB972
        and verifier["expected_address"] == 0xB972
        and verifier["bytes"] == 40
        and publish["status"] == "passed"
        and publish["declared_domain_bytes"] == 42
        and fixed["fixed_code"]["end_exclusive"] == 0xC25D
        and fixed["hot_bss"]["address"] == 0xC25D,
        "Link-60 final product qualification red",
    )
    require(
        sha(BASELINE) == BASELINE_SHA,
        "Link-59 rollback line changed during Link 60",
    )

    receipt = {
        "format":
            f"lisp65-c2-lite-v6-link{LINK_NUMBER}-two-region-E000-S1-v1",
        "recorded_on": "2026-07-24",
        "link_number": LINK_NUMBER,
        "status":
            f"passed-link{LINK_NUMBER}-two-region-E000-S1-product-identity-"
            "hardware-not-run",
        "promotable": False,
        "authority": {
            "qualified_WPLTO_artifact_completion": bind(
                ARTIFACT_COMPLETION),
            "canonical_WPLTO_profile": bind(WPLTO_PROFILE),
            "link59_rollback_product": {
                **bind(BASELINE), "status": "untouched"},
            "link59_rollback_receipt": bind(BASELINE_RECEIPT),
            "kernal_contract": bind(KERNAL_CONTRACT),
            "two_region_contract": bind(REGION_CONTRACT),
            "driver": bind(Path(__file__)),
            **({
                "failed_predecessor_product": bind(
                    FAILED_PREDECESSOR_PRODUCT),
                "failed_predecessor_receipt": bind(
                    FAILED_PREDECESSOR_RECEIPT),
            } if FAILED_PREDECESSOR_PRODUCT is not None
                and FAILED_PREDECESSOR_RECEIPT is not None else {}),
        },
        "preflight": profile,
        "canonical_profile_binding": {
            "WPLTO_sha256": WPLTO_PROFILE_SHA,
            "link_sha256": resolved_sha,
            "path_normalized_rows_byteidentical": profile_equal,
            "rule":
                "Generated-source paths differ by output root; feature, "
                "input hashes and every non-path field are identical.",
        },
        "fresh_gate_program": {
            "qualification": bind(QUALIFICATION_RECEIPT),
            "base": bind(BASE_RESULT),
            "format_and_stage": bind(FORMAT_RECEIPT),
            "write_completion_source": bind(COMPLETION_SOURCE_RECEIPT),
            "emitter_union": bind(EMITTER_RECEIPT),
            "preinstall_source_host": bind(ISLAND_RECEIPT),
            "read_only_qualification": bind(REPLAY_RECEIPT),
            "product_substitution": bind(
                OUT / "product-substitution-link.json"),
            "verifier_publish_last": bind(
                OUT / "runtime-verifier-publish-last.json"),
            "total_publish_last": bind(
                OUT / "total-publish-last-domain.json"),
            "fixed_block": bind(OUT / "fixed-block-rtov-fail-final.json"),
            "all_fresh_green": True,
            "inherited_green": 0,
        },
        "walls": walls,
        "runtime_families": {
            "boot_main_bytes": boot["storage"]["size"],
            "session_main_bytes": session["storage"]["size"],
            "session_main_headroom_bytes": 610,
            "session_overflow_used_bytes": overflow["used"],
            "session_overflow_capacity_bytes": overflow["capacity"],
            "session_overflow_headroom_bytes":
                int(overflow["capacity"]) - int(overflow["used"]),
        },
        "publish_last": {
            "verifier_table_address": "0xb972",
            "verifier_and_family_stage_bytes": 40,
            "kernal_CRC_addresses": ["0xb4cc", "0xb4d0"],
            "total_declared_bytes": 42,
            "status": "passed",
        },
        "product_identity": {
            "product": bind(PRODUCT),
            "elf": bind(ELF),
            "map": bind(MAP),
            "runtime_boot": bind(
                OUT / "runtime-overlays-boot-final.bin"),
            "runtime_session": bind(
                OUT / "runtime-overlays-session-final.bin"),
            "runtime_session_region1": bind(
                OUT / "runtime-overlays-session-final-region1.bin"),
            "predecessor_sha256": BASELINE_SHA,
            "new_identity": True,
        },
        "C1_Freezer_cutpoints": {
            "cutpoint_3":
                f"repeat-with-episode-latch-on-exact-Link{LINK_NUMBER}-"
                "identity",
            "cutpoint_4":
                "repeat-with-four-write-completion-barriers-on-exact-"
                f"Link{LINK_NUMBER}-identity",
            "matrix_C1": "OPEN-until-both-hardware-results-green",
        },
        "execution_accounting": {
            "product_closure_links": 1,
            "automatic_retries": 0,
            "hardware_runs": 0,
        },
        "counters": {
            "line1_product_first_reds": "2/3",
            "completed_latency_measurements": "2/2-passed",
        },
        "next_gate":
            "prepare nonpromotable Cutpoint-3 episode-latch and Cutpoint-4 "
            f"write-completion carriers from this exact Link-{LINK_NUMBER} "
            "identity; "
            "request device start before hardware",
        "claim_limit":
            f"Structurally complete Link {LINK_NUMBER} only. C1, the full "
            "matrix, "
            "promotion and R4/R5/R6/G5/G6 remain unclaimed.",
    }
    write_receipt(RECEIPT, receipt)
    print(
        f"c2-link{LINK_NUMBER}-two-region-E000-S1: COMPLETE "
        f"product={sha(PRODUCT)} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"bss={walls['ordinary_bank0_bss_headroom_bytes']} "
        f"fixed={walls['fixed_hot_block_headroom_bytes']} "
        f"island={walls['resident_island_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        "session=64926+1956 verifier=B972 hardware=not-run"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        Link60Error, FINAL.FinalMapError, RuntimeError, OSError, ValueError,
        KeyError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-link60-two-region-E000-S1: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
