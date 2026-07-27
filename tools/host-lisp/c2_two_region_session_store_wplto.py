#!/usr/bin/env python3
"""One product-shaped WPLTO for strict L65R-v4 and the Session overflow."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_cpu_chip_write_completion_gate as COMPLETION  # noqa: E402
import c2_cpu_chip_write_completion_wplto as DRIVER  # noqa: E402
import c2_emitter_work_state_union_gate as EMITTER_UNION  # noqa: E402
import c2_l65r_v4_two_region_gate as FORMAT  # noqa: E402
import c2_lite_v6_link55_append_suffix_fusion_wplto as FUSION  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "two-region-session-store-source-plan-union-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-two-region-session-store-source-plan-union-wplto-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-two-region-session-store-source-plan-union-wplto-base.json")
RAW_RECEIPT = EVIDENCE / (
    "c2.2-two-region-session-store-source-plan-union-wplto-raw.json")
REPLAY_OUT = ROOT / (
    "build/c2.2/substitution/"
    "two-region-session-store-source-plan-union-qualification")
REPLAY_RECEIPT = EVIDENCE / (
    "c2.2-two-region-session-store-source-plan-union-qualification.json")
RECEIPT = EVIDENCE / (
    "c2.2-two-region-session-store-source-plan-union-wplto-receipt.json")
SOURCE_RECEIPT = ROOT / (
    "build/c2.2/two-region-session-store/"
    "write-completion-source-plan-union-gate.json")
FORMAT_RECEIPT = EVIDENCE / (
    "c2.2-l65r-v4-two-region-contract-receipt.json")
PRODUCT_PATH = OUT / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT_PATH) + ".elf")
MAP = Path(str(PRODUCT_PATH) + ".map")
C2D = OUT / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin"
REGION1_NAMES = {
    "rollback_wipe_plane",
    "rollback_wipe_chip",
    "rollback_wipe_attic",
}


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def configure_two_region() -> None:
    """Run the complete predecessor ABI, then add exactly the v4 delta."""
    names = [name for name, _entry in PRODUCT.C2_APPEND_SLICES]
    require(
        names.count("rollback_unpublish") == 1
        and names.count("rollback_finalize") == 1,
        "rollback split anchors absent")
    at = names.index("rollback_unpublish") + 1
    require(
        names[at] == "rollback_finalize",
        "rollback split anchors are not adjacent")
    rows = list(PRODUCT.C2_APPEND_SLICES)
    rows[at:at] = [
        ("rollback_wipe_plane", "c2_append_rollback_wipe_plane_phase"),
        ("rollback_wipe_chip", "c2_append_rollback_wipe_chip_phase"),
        ("rollback_wipe_attic", "c2_append_rollback_wipe_attic_phase"),
    ]
    PRODUCT.configure_append_slices(rows)
    PRODUCT.configure_runtime_overlay_v4(REGION1_NAMES)
    PRODUCT.configure_link60_final_geometry()
    names = [name for name, _entry in PRODUCT.C2_APPEND_SLICES]
    require(
        names[names.index("rollback_unpublish"):
              names.index("rollback_finalize") + 1]
        == [
            "rollback_unpublish", "rollback_wipe_plane",
            "rollback_wipe_chip", "rollback_wipe_attic",
            "rollback_finalize",
        ],
        "semantic rollback split order drift")


def transformed_features(
        predecessor: tuple[str, ...]) -> tuple[str, ...]:
    require(
        predecessor.count("LISP65_RUNTIME_OVERLAY_FORMAT_V3") == 1
        and "LISP65_RUNTIME_OVERLAY_FORMAT_V4" not in predecessor
        and "LISP65_C2_TWO_REGION_SESSION_STORE" not in predecessor,
        "predecessor format feature is not strict v3")
    values = tuple(
        "LISP65_RUNTIME_OVERLAY_FORMAT_V4"
        if item == "LISP65_RUNTIME_OVERLAY_FORMAT_V3" else item
        for item in predecessor)
    return (*values, "LISP65_C2_TWO_REGION_SESSION_STORE")


def run_source_gates() -> tuple[
        dict[str, Any], dict[str, Any], dict[str, Any]]:
    completion = COMPLETION.build()
    SOURCE_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_RECEIPT.write_text(
        json.dumps(completion, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    old_argv = sys.argv
    try:
        sys.argv = [
            str(FORMAT.__file__), "--receipt", str(FORMAT_RECEIPT)]
        require(FORMAT.main() == 0, "strict v4 format gate failed")
    finally:
        sys.argv = old_argv
    format_value = json.loads(FORMAT_RECEIPT.read_text(encoding="utf-8"))
    emitter_union = EMITTER_UNION.run()
    EMITTER_UNION.RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    EMITTER_UNION.RECEIPT.write_text(
        json.dumps(emitter_union, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return completion, format_value, emitter_union


def run_wplto() -> tuple[int, str | None]:
    old_paths = {
        "OUT": DRIVER.OUT,
        "INTERNAL": DRIVER.INTERNAL,
        "BASE_RECEIPT": DRIVER.BASE_RECEIPT,
        "RAW_RECEIPT": DRIVER.RAW_RECEIPT,
        "REPLAY_OUT": DRIVER.REPLAY_OUT,
        "REPLAY_RECEIPT": DRIVER.REPLAY_RECEIPT,
        "RECEIPT": DRIVER.RECEIPT,
        "PRODUCT": DRIVER.PRODUCT,
        "ELF": DRIVER.ELF,
        "MAP": DRIVER.MAP,
        "C2D": DRIVER.C2D,
    }
    old_configure = FUSION.FUSION.configure
    old_features = FUSION.PROFILE.resolved_features

    def configure() -> None:
        old_configure()
        configure_two_region()

    def features() -> tuple[str, ...]:
        return transformed_features(old_features())

    try:
        DRIVER.OUT = OUT
        DRIVER.INTERNAL = INTERNAL
        DRIVER.BASE_RECEIPT = BASE_RECEIPT
        DRIVER.RAW_RECEIPT = RAW_RECEIPT
        DRIVER.REPLAY_OUT = REPLAY_OUT
        DRIVER.REPLAY_RECEIPT = REPLAY_RECEIPT
        DRIVER.RECEIPT = RECEIPT
        DRIVER.PRODUCT = PRODUCT_PATH
        DRIVER.ELF = ELF
        DRIVER.MAP = MAP
        DRIVER.C2D = C2D
        FUSION.FUSION.configure = configure
        FUSION.PROFILE.resolved_features = features
        return DRIVER.run_wplto()
    finally:
        FUSION.FUSION.configure = old_configure
        FUSION.PROFILE.resolved_features = old_features
        for name, value in old_paths.items():
            setattr(DRIVER, name, value)


def main() -> int:
    require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RAW_RECEIPT.exists()
        and not REPLAY_OUT.exists() and not REPLAY_RECEIPT.exists()
        and not RECEIPT.exists(),
        "two-region WPLTO is one-shot")
    completion, format_value, emitter_union = run_source_gates()
    result, error = run_wplto()
    session_path = OUT / "runtime-overlays-session-unbound.json"
    session = (
        json.loads(session_path.read_text(encoding="utf-8"))
        if session_path.is_file() else None)
    slices = {row["name"]: row for row in session["slices"]} if session else {}
    overflow = session.get("overflow_storage") if session else None
    main_size = session["storage"]["size"] if session else None
    overflow_used = overflow["used"] if overflow else None
    region_rows = (
        [row for row in session["slices"] if row.get("region_id") == 1]
        if session else [])
    slice_cap_green = bool(session) and all(
        row["file_size"] <= 1792 for row in session["slices"])
    region_green = (
        bool(overflow)
        and 0 < overflow_used <= 2032
        and {row["name"].removeprefix("c2-append-")
             .replace("-", "_") for row in region_rows}
        == REGION1_NAMES)
    main_green = isinstance(main_size, int) and main_size <= 65536
    value = {
        "format": "lisp65-c2-two-region-session-store-l65r-v4-WPLTO-v1",
        "recorded_on": "2026-07-24",
        "status": (
            "passed-product-shaped-WPLTO-two-region-capacity"
            if result == 0 and slice_cap_green and region_green and main_green
            else "FIRST RED: product-shaped two-region package did not close"),
        "promotable": False,
        "authority": {
            "contract": bind(
                ROOT / "config/c2-two-region-session-store-contract.json"),
            "format_gate": bind(FORMAT_RECEIPT),
            "completion_source_gate": bind(SOURCE_RECEIPT),
            "emitter_union_gate": bind(EMITTER_UNION.RECEIPT),
            "driver": bind(Path(__file__)),
        },
        "format_gate": {
            "status": format_value["status"],
            "mutations": format_value["mutations"],
        },
        "completion_gate": {
            "status": completion["status"],
            "mutations": completion["mutation_count"],
        },
        "emitter_union_gate": {
            "status": emitter_union["status"],
            "geometry": emitter_union["geometry"],
            "mutations": emitter_union["mutations"],
        },
        "WPLTO": {
            "return_code": result,
            "exception": error,
            "product_completed": PRODUCT_PATH.is_file() and ELF.is_file(),
            "raw_receipt": (
                bind(RAW_RECEIPT) if RAW_RECEIPT.is_file() else None),
        },
        "session_regions": {
            "main_bytes": main_size,
            "main_headroom_bytes": (
                65536 - main_size if isinstance(main_size, int) else None),
            "overflow_used_bytes": overflow_used,
            "overflow_capacity_bytes": (
                overflow["capacity"] if overflow else None),
            "overflow_headroom_bytes": (
                overflow["capacity"] - overflow_used if overflow else None),
            "overflow_slices": [
                {
                    "id": row["id"], "name": row["name"],
                    "bytes": row["file_size"], "file_offset": row["file_offset"],
                }
                for row in region_rows
            ],
            "c2d_append_scratch_floor_bytes": 14544,
            "worst_case_dynamic_entry_delta_rows": -25,
        },
        "rollback_slices": {
            name: {
                "bytes": slices.get("c2-append-" + name.replace("_", "-"), {})
                    .get("file_size"),
                "region_id": slices.get(
                    "c2-append-" + name.replace("_", "-"), {})
                    .get("region_id"),
            }
            for name in (
                "rollback_unpublish", "rollback_wipe_plane",
                "rollback_wipe_chip", "rollback_wipe_attic",
                "rollback_finalize")
        },
        "gates": {
            "all_slices_under_1792": slice_cap_green,
            "main_region_at_most_u16": main_green,
            "overflow_region_at_most_2032": region_green,
        },
        "execution_accounting": {
            "whole_program_LTO_closure_links": 1,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "Capacity/placement WPLTO only. No product link, C1 closure, "
            "matrix-gate fall or acceptance-chain claim."),
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-two-region-session-store-wplto: "
        + ("PASS" if value["status"].startswith("passed") else "FIRST RED")
        + f" main={main_size} overflow={overflow_used}")
    return 0 if value["status"].startswith("passed") else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProbeError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-two-region-session-store-wplto: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
