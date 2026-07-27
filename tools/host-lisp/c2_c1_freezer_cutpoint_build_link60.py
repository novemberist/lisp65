#!/usr/bin/env python3
"""Build the one Link-60-shaped, non-promotable C1 overlay donor.

This is a diagnostic WPLTO closure, not a product link.  It consumes the
complete Link-60 profile and adds exactly the cold cutpoint fixture define.
Its resident image is never deployed; only four overlay payloads are eligible
for the later artifact-only rebind into the immutable Link-60 family.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_c1_freezer_cutpoint_gate as C1  # noqa: E402
import c2_link60_two_region_e000_s1_successor_link as LINK60  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402
import c2_two_region_e000_s1_final_wplto as FINAL  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link60-c1-freezer-cutpoints-WPLTO-donor-NONPROMOTABLE")
INTERNAL = EVIDENCE / (
    "c2.2-link60-c1-freezer-cutpoints-donor-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link60-c1-freezer-cutpoints-donor-base.json")
RAW_RECEIPT = EVIDENCE / (
    "c2.2-link60-c1-freezer-cutpoints-donor-raw.json")
REPLAY_OUT = ROOT / (
    "build/c2.2/substitution/"
    "link60-c1-freezer-cutpoints-donor-qualification")
REPLAY_RECEIPT = EVIDENCE / (
    "c2.2-link60-c1-freezer-cutpoints-donor-qualification.json")
BASE_RESULT = EVIDENCE / (
    "c2.2-link60-c1-freezer-cutpoints-donor-base-result.json")
FORMAT_RECEIPT = EVIDENCE / (
    "c2.2-link60-c1-freezer-cutpoints-donor-format-stage.json")
COMPLETION_SOURCE_RECEIPT = ROOT / (
    "build/c2.2/c1-freezer-cutpoints-link60/"
    "write-completion-source-gate.json")
EMITTER_RECEIPT = EVIDENCE / (
    "c2.2-link60-c1-freezer-cutpoints-donor-emitter-union.json")
ISLAND_RECEIPT = EVIDENCE / (
    "c2.2-link60-c1-freezer-cutpoints-donor-preinstall-source-host.json")
FINAL_RECEIPT = EVIDENCE / (
    "c2.2-link60-c1-freezer-cutpoints-donor-final-map.json")
RECEIPT = EVIDENCE / (
    "c2.2-link60-c1-freezer-cutpoints-donor-"
    "nonpromotable-structural-receipt.json")
PRODUCT = OUT / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
C2D = OUT / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin"
FEATURE = "LISP65_C2_C1_FREEZER_CUTPOINT_FIXTURE"
PRODUCT_SHA = (
    "7fc3bb84acf6039ea34ff863ba4f6d39458400a7848ae7077a8085ccd9cf2416")
DEPLOYMENT_PRODUCT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-60-two-region-e000-s1-completion/"
    "lisp65-c2-substitution-linked.prg")
DEPLOYMENT_RECEIPT = LINK60.RECEIPT
DEPLOYMENT_STATUS = (
    "passed-link60-two-region-E000-S1-product-identity-hardware-not-run")
AFFECTED = {
    30: ".lisp65_rt_c2append_journal_prepare",
    39: ".lisp65_rt_c2append_header",
    40: ".lisp65_rt_c2append_publish_clear",
    41: ".lisp65_rt_c2append_rollback_unpublish",
}


class BuildError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise BuildError(message)


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"Link-60 C1 donor artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": LINK60.sha(path),
    }


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
    FINAL.RECEIPT = FINAL_RECEIPT
    FINAL.PRODUCT = PRODUCT
    FINAL.ELF = ELF
    FINAL.MAP = MAP
    FINAL.C2D = C2D
    FINAL.RUNNER_PATH = Path(__file__)


def finalize_existing() -> int:
    """Qualify the completed donor after its expected historical-gate red."""
    required = (
        PRODUCT, ELF, MAP, OUT / "resolved-profile.txt",
        OUT / "runtime-overlays-session-final.json",
        OUT / "runtime-overlays-session-final.bin",
        OUT / "runtime-overlays-session-final-region1.bin",
        INTERNAL, RAW_RECEIPT, BASE_RESULT, FINAL_RECEIPT,
    )
    require(
        OUT.is_dir() and not RECEIPT.exists()
        and all(path.is_file() for path in required),
        "Link-60 C1 donor completion inputs are incomplete")
    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    raw = json.loads(RAW_RECEIPT.read_text(encoding="utf-8"))
    base = json.loads(BASE_RESULT.read_text(encoding="utf-8"))
    final = json.loads(FINAL_RECEIPT.read_text(encoding="utf-8"))
    require(
        internal["status"] == "FIRST RED: C2-lite real-ABI Link 50 stopped"
        and internal["diagnostic"] == {
            "message": "final consolidation aggregate/profile gate red",
            "type": "GateError",
        }
        and internal["execution_accounting"]["product_closure_links"] == 1
        and raw["status"]
        == "FIRST RED: historical checker stopped current-product L-full keymap WPLTO"
        and base["status"]
        == "FIRST RED: product-shaped two-region package did not close"
        and final["status"]
        == "FIRST RED: final E000-S1 map or qualification did not close",
        "Link-60 donor did not stop at the expected historical size checker")

    source_gate = C1.gate()
    source_path = OUT / "c1-freezer-cutpoint-source-gate.json"
    os.chmod(OUT, 0o755)
    source_path.write_text(
        json.dumps(source_gate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    manifest_path = OUT / "runtime-overlays-session-final.json"
    main_path = OUT / "runtime-overlays-session-final.bin"
    overflow_path = OUT / "runtime-overlays-session-final-region1.bin"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = {int(row["id"]): row for row in manifest["slices"]}
    resolved = (OUT / "resolved-profile.txt").read_text(encoding="utf-8")
    require(
        "nonpromotable_diagnostic=C1-Freezer-open-transaction" in resolved
        and "diagnostic_command_address=0x17e0" in resolved
        and "diagnostic_reached_address=0x17e1" in resolved
        and set(rows) == set(range(51))
        and int(manifest["catalog"]["version"]) == 4
        and main_path.stat().st_size == 64926
        and overflow_path.stat().st_size == 1956
        and LINK60.sha(overflow_path)
        == "38e5771ab7f6840d487715d473a63b8e3ea268a23c6993928be7535152ad7b6b"
        and all(rows[slot]["section"] == section
                and int(rows[slot]["region_id"]) == 0
                and int(rows[slot]["file_size"]) <= 1792
                for slot, section in AFFECTED.items()),
        "Link-60 diagnostic donor geometry is not carrier-eligible")

    product = DEPLOYMENT_PRODUCT
    contract = ROOT / "config/c2-c1-freezer-cutpoint-contract.json"
    receipt = {
        "format": "lisp65-c2.2-link60-C1-Freezer-WPLTO-donor-v1",
        "recorded_on": "2026-07-24",
        "status":
            "passed-nonpromotable-Link60-C1-overlay-donor-hardware-not-run",
        "promotable": False,
        "authority": {
            "immutable_link60_product": bind(product),
            "link60_receipt": bind(DEPLOYMENT_RECEIPT),
            "cutpoint_contract": bind(contract),
            "cutpoint_source_gate": bind(source_path),
            "historical_checker_first_red": bind(INTERNAL),
            "driver": bind(Path(__file__)),
        },
        "diagnostic_identity": {
            "product": bind(PRODUCT),
            "elf": bind(ELF),
            "map": bind(MAP),
            "session_main": bind(main_path),
            "session_region1": bind(overflow_path),
            "feature": FEATURE,
            "deployment_role": "overlay-donor-only",
            "resident_image_deployed": False,
            "product_bytes_changed": 0,
        },
        "carrier_eligibility": {
            "dense_records": len(rows),
            "format_version": 4,
            "main_bytes": main_path.stat().st_size,
            "region1_bytes": overflow_path.stat().st_size,
            "region1_byteidentical_link60": True,
            "affected_region0_slots": {
                str(slot): {
                    "section": rows[slot]["section"],
                    "bytes": rows[slot]["file_size"],
                    "pack_headroom_bytes":
                        1792 - int(rows[slot]["file_size"]),
                }
                for slot in sorted(AFFECTED)
            },
        },
        "historical_checker_disposition": {
            "classification": "class-A-model-only",
            "reason": (
                "The inherited consolidation gate pins product payload sizes; "
                "a cutpoint donor intentionally changes four cold payloads. "
                "Both region extents and every hard slice cap remain green."),
            "compiler_or_linker_rerun": False,
        },
        "execution_accounting": {
            "diagnostic_WPLTO_closure_links": 1,
            "automatic_retries": 0,
            "artifact_completion_compiler_runs": 0,
            "artifact_completion_linker_runs": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0,
            "latency_attempts_consumed": 0,
        },
        "claim_limit": (
            "Overlay donor only. The diagnostic resident image is forbidden "
            "from deployment and carries no product, matrix, acceptance or "
            "release claim."),
        "next_gate": (
            "artifact-only structured relocation rebind to immutable Link 60, "
            "v4 region rebuild and exact main-stage binding"),
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    for path in (source_path, RECEIPT):
        os.chmod(path, 0o444)
    os.chmod(OUT, 0o555)
    print(
        "c2-c1-freezer-cutpoint-build-link60: ARTIFACT PASS "
        f"donor={LINK60.sha(PRODUCT)} main={main_path.stat().st_size} "
        f"region1={overflow_path.stat().st_size} hardware=not-run")
    return 0


def main() -> int:
    one_shot = (
        OUT, INTERNAL, BASE_RECEIPT, RAW_RECEIPT, REPLAY_OUT,
        REPLAY_RECEIPT, BASE_RESULT, FORMAT_RECEIPT,
        COMPLETION_SOURCE_RECEIPT, EMITTER_RECEIPT, ISLAND_RECEIPT,
        FINAL_RECEIPT, RECEIPT,
    )
    if OUT.exists() or any(path.exists() for path in one_shot[1:]):
        return finalize_existing()
    product = DEPLOYMENT_PRODUCT
    link_receipt = DEPLOYMENT_RECEIPT
    contract = ROOT / "config/c2-c1-freezer-cutpoint-contract.json"
    require(
        product.is_file() and LINK60.sha(product) == PRODUCT_SHA
        and link_receipt.is_file() and contract.is_file(),
        "immutable Link-60 donor authority drift")
    authority = json.loads(link_receipt.read_text(encoding="utf-8"))
    authority_product = (
        authority["product_identity"]["product"]
        if "product_identity" in authority
        else authority["authority"]["product"])
    source_gate = C1.gate()
    require(
        authority["status"] == DEPLOYMENT_STATUS
        and authority_product["sha256"] == PRODUCT_SHA
        and source_gate["source"]["product_bytes"] == 0
        and len(source_gate["mutations_rejected"]) == 10,
        "Link-60 C1 source or product authority is incomplete")

    configure_paths()
    original_single_link = P.single_link

    def diagnostic_single_link(
            out: Path, *, probe_definitions: tuple[str, ...] = (),
            direct_entry_receipt: Path = P.DIRECT_ENTRY_CONTRACT_RECEIPT,
            direct_entry_check_tool: str = "c2_direct_entry_contract.py",
            extra_contract_lines: tuple[str, ...] = ()) -> None:
        require(FEATURE not in probe_definitions,
                "C1 diagnostic feature duplicated")
        original_single_link(
            out,
            probe_definitions=(*probe_definitions, FEATURE),
            direct_entry_receipt=direct_entry_receipt,
            direct_entry_check_tool=direct_entry_check_tool,
            extra_contract_lines=(
                *extra_contract_lines,
                "nonpromotable_diagnostic=C1-Freezer-open-transaction",
                "diagnostic_command_address=0x17e0",
                "diagnostic_reached_address=0x17e1",
                "resident_deployment_authority_sha256=" + PRODUCT_SHA,
            ),
        )

    try:
        LINK60.configure_current_pin_adapters()
        P.single_link = diagnostic_single_link
        result = FINAL.main()
    finally:
        P.single_link = original_single_link

    require(
        result == 0 and PRODUCT.is_file() and ELF.is_file() and MAP.is_file(),
        "Link-60 C1 diagnostic WPLTO did not complete")
    final = json.loads(FINAL_RECEIPT.read_text(encoding="utf-8"))
    manifest_path = OUT / "runtime-overlays-session-final.json"
    main_path = OUT / "runtime-overlays-session-final.bin"
    overflow_path = OUT / "runtime-overlays-session-final-region1.bin"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = {int(row["id"]): row for row in manifest["slices"]}
    require(
        final["status"] == "passed-final-map-all-walls-and-gates-green"
        and set(rows) == set(range(51))
        and all(rows[slot]["section"] == section
                and int(rows[slot]["region_id"]) == 0
                for slot, section in AFFECTED.items())
        and all(int(rows[slot]["file_size"]) <= 1792 for slot in AFFECTED)
        and main_path.stat().st_size <= 65536
        and overflow_path.stat().st_size <= 2032,
        "Link-60 diagnostic donor geometry is not carrier-eligible")

    return finalize_existing()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BuildError, C1.GateError, RuntimeError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-c1-freezer-cutpoint-build-link60: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
