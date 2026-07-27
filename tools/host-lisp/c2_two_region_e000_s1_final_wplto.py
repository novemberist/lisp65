#!/usr/bin/env python3
"""The one final WPLTO map for E000-S1 and stage-amortized L65R-v4."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_preinstall_island_guard as ISLAND  # noqa: E402
import c2_e000_s1_tuple_lifetime_gate as TUPLE  # noqa: E402
import c2_two_region_session_store_wplto as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "two-region-session-store-e000-s1-final-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-two-region-e000-s1-final-wplto-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-two-region-e000-s1-final-wplto-base.json")
RAW_RECEIPT = EVIDENCE / (
    "c2.2-two-region-e000-s1-final-wplto-raw.json")
REPLAY_OUT = ROOT / (
    "build/c2.2/substitution/"
    "two-region-session-store-e000-s1-final-qualification")
REPLAY_RECEIPT = EVIDENCE / (
    "c2.2-two-region-e000-s1-final-qualification.json")
BASE_RESULT = EVIDENCE / (
    "c2.2-two-region-e000-s1-final-wplto-base-result.json")
FORMAT_RECEIPT = EVIDENCE / (
    "c2.2-two-region-e000-s1-final-format-and-stage-gate.json")
COMPLETION_SOURCE_RECEIPT = ROOT / (
    "build/c2.2/two-region-session-store/"
    "e000-s1-final-write-completion-source-gate.json")
EMITTER_RECEIPT = EVIDENCE / (
    "c2.2-two-region-e000-s1-final-emitter-union-gate.json")
ISLAND_RECEIPT = EVIDENCE / (
    "c2.2-two-region-e000-s1-final-preinstall-source-host-gate.json")
TUPLE_FEATURE_RECEIPT = EVIDENCE / (
    "c2.2-e000-s1-tuple-feature-lifetime-gate.json")
RECEIPT = EVIDENCE / (
    "c2.2-two-region-e000-s1-final-wplto-receipt.json")
PRODUCT = OUT / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
C2D = OUT / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin"
DRIVER_PATH = Path(__file__)
RUNNER_PATH = DRIVER_PATH


class FinalMapError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FinalMapError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write_receipt(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(path, 0o444)


def source_and_host_gate() -> dict[str, Any]:
    source = ISLAND.source_gate()
    host = ISLAND.host_gate()
    value = {
        "format": "lisp65-c2-e000-s1-preinstall-source-host-gate-v1",
        "recorded_on": "2026-07-24",
        "status": "passed-E000-S1-source-mutations-and-host-lifecycle",
        "source": source,
        "host": host,
        "authority": {
            "runtime": bind(ISLAND.RUNTIME),
            "header": bind(ISLAND.HEADER),
            "fixture": bind(ISLAND.FIXTURE),
            "gate": bind(Path(ISLAND.__file__)),
        },
        "execution_accounting": {
            "whole_program_LTO_closure_links": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
    }
    write_receipt(ISLAND_RECEIPT, value)
    return value


def tuple_feature_lifetime_gate() -> dict[str, Any]:
    """Rebuild the tuple-lifetime proof from this checkout's live sources."""
    value = TUPLE.build()
    write_receipt(TUPLE_FEATURE_RECEIPT, value)
    return value


def configure_base_paths() -> None:
    BASE.OUT = OUT
    BASE.INTERNAL = INTERNAL
    BASE.BASE_RECEIPT = BASE_RECEIPT
    BASE.RAW_RECEIPT = RAW_RECEIPT
    BASE.REPLAY_OUT = REPLAY_OUT
    BASE.REPLAY_RECEIPT = REPLAY_RECEIPT
    BASE.RECEIPT = BASE_RESULT
    BASE.SOURCE_RECEIPT = COMPLETION_SOURCE_RECEIPT
    BASE.FORMAT_RECEIPT = FORMAT_RECEIPT
    BASE.PRODUCT_PATH = PRODUCT
    BASE.ELF = ELF
    BASE.MAP = MAP
    BASE.C2D = C2D
    BASE.EMITTER_UNION.RECEIPT = EMITTER_RECEIPT


def main() -> int:
    one_shot = (
        OUT, INTERNAL, BASE_RECEIPT, RAW_RECEIPT, REPLAY_OUT,
        REPLAY_RECEIPT, BASE_RESULT, FORMAT_RECEIPT,
        COMPLETION_SOURCE_RECEIPT, EMITTER_RECEIPT, ISLAND_RECEIPT,
        TUPLE_FEATURE_RECEIPT, RECEIPT,
    )
    require(not any(path.exists() for path in one_shot),
            "final E000-S1 WPLTO is one-shot")

    source_host = source_and_host_gate()
    tuple_feature = tuple_feature_lifetime_gate()
    configure_base_paths()
    result = BASE.main()

    base_value = json.loads(BASE_RESULT.read_text(encoding="utf-8"))
    internal_value = (
        json.loads(INTERNAL.read_text(encoding="utf-8"))
        if INTERNAL.is_file() else {})
    raw = (json.loads(RAW_RECEIPT.read_text(encoding="utf-8"))
           if RAW_RECEIPT.is_file() else {})
    walls = raw.get("walls")
    capacity = raw.get("capacity")
    format_value = json.loads(FORMAT_RECEIPT.read_text(encoding="utf-8"))
    static_island: dict[str, Any] | None = None
    static_error: str | None = None
    if ELF.is_file():
        try:
            static_island = ISLAND.static_elf_gate(ELF)
        except Exception as error:
            static_error = f"{type(error).__name__}: {error}"

    session = (
        json.loads((OUT / "runtime-overlays-session-unbound.json")
                   .read_text(encoding="utf-8"))
        if (OUT / "runtime-overlays-session-unbound.json").is_file()
        else None)
    region1_rows = (
        [row for row in session["slices"] if row.get("region_id") == 1]
        if session else [])
    overflow = session.get("overflow_storage") if session else None
    expected_region1 = {
        "c2-append-rollback-wipe-plane",
        "c2-append-rollback-wipe-chip",
        "c2-append-rollback-wipe-attic",
    }
    regions_green = bool(
        session and overflow
        and int(session["storage"]["size"]) <= 65536
        and 0 < int(overflow["used"]) <= 2032
        and {str(row["name"]) for row in region1_rows} == expected_region1
        and all(int(row["file_size"]) <= 1792
                for row in session["slices"]))
    walls_green = bool(
        walls
        and int(walls["e000_headroom_bytes"]) >= 54
        and int(walls["bank0_text_headroom_bytes"]) >= 32
        and int(walls["ordinary_bank0_bss_headroom_bytes"]) >= 0
        and int(walls["fixed_hot_block_headroom_bytes"]) >= 0
        and int(walls["resident_island_headroom_bytes"]) >= 0)
    capacity_green = bool(
        capacity and int(capacity["session_family_bytes"]) <= 65536)
    gates_green = bool(
        result == 0
        and base_value["status"].startswith("passed")
        and format_value["status"].startswith("passed")
        and format_value["stage_source_authority"]["status"].startswith(
            "passed")
        and static_island is not None
        and static_error is None
        and static_island["E000_S1"]["status"].startswith("passed")
        and source_host["status"].startswith("passed")
        and tuple_feature["status"].startswith("passed"))
    green = walls_green and capacity_green and regions_green and gates_green

    value = {
        "format": "lisp65-c2-two-region-E000-S1-final-WPLTO-v1",
        "recorded_on": "2026-07-24",
        "status": (
            "passed-final-map-all-walls-and-gates-green"
            if green else
            "FIRST RED: final E000-S1 map or qualification did not close"),
        "promotable": False,
        "authority": {
            "contract": bind(
                ROOT / "config/c2-two-region-session-store-contract.json"),
            "driver": bind(DRIVER_PATH),
            "runner": bind(RUNNER_PATH),
            "tuple_feature_lifetime_gate": bind(TUPLE_FEATURE_RECEIPT),
            "base_result": bind(BASE_RESULT),
            "format_and_stage_gate": bind(FORMAT_RECEIPT),
            "preinstall_source_host_gate": bind(ISLAND_RECEIPT),
            "completion_source_gate": bind(COMPLETION_SOURCE_RECEIPT),
            "emitter_union_gate": bind(EMITTER_RECEIPT),
            "ELF": bind(ELF) if ELF.is_file() else None,
            "map": bind(MAP) if MAP.is_file() else None,
        },
        "decisions": {
            "E000_S1": {
                "retired_symbols": [
                    "rtov_run_batch",
                    "vm_runtime_overlay_exec_batch_island",
                ],
                "replacement":
                    "complete authenticated single-record path per repeat",
                "deliberate_cost": "cold batch operations are slower",
            },
            "record_verifier": {
                "private_region_source_reconstruction": "absent",
                "composite_authority":
                    "emitter bounds + record CRC + final manifest binding + "
                    "target family CRC before VERIFIED",
            },
        },
        "walls": walls,
        "wall_requirements": {
            "E000_floor_bytes": 54,
            "bank0_text_noise_headroom_bytes": 32,
            "ordinary_bank0_bss_headroom_bytes": 0,
            "fixed_hot_block_headroom_bytes": 0,
            "resident_island_headroom_bytes": 0,
        },
        "regions": {
            "status": "passed" if regions_green else "red",
            "main_bytes": (
                session["storage"]["size"] if session else None),
            "main_headroom_bytes": (
                65536 - int(session["storage"]["size"]) if session else None),
            "overflow_used_bytes": (
                overflow["used"] if overflow else None),
            "overflow_headroom_bytes": (
                2032 - int(overflow["used"]) if overflow else None),
            "overflow_slices": [
                {
                    "name": row["name"],
                    "bytes": row["file_size"],
                    "source_address": row["source_address"],
                }
                for row in region1_rows
            ],
        },
        "gates": {
            "base_WPLTO": base_value.get("status"),
            "format_and_stage": format_value.get("status"),
            "stage_source_authority":
                format_value.get("stage_source_authority"),
            "preinstall_static": static_island,
            "preinstall_static_exception": static_error,
            "all_fresh_green": gates_green,
        },
        "execution_accounting": {
            "final_map_driver_attempts": 1,
            "whole_program_LTO_closure_links":
                internal_value.get("execution_accounting", {}).get(
                    "product_closure_links", 0),
            "automatic_retries": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
        "next_gate": (
            "Link 60 with a new product identity and all gates fresh"
            if green else
            "First-Red review; no product link or hardware"),
        "claim_limit": (
            "Exactly one product-shaped WPLTO map. No product identity, "
            "hardware, C1 closure, matrix fall or acceptance-chain claim."),
    }
    write_receipt(RECEIPT, value)
    print(
        "c2-two-region-e000-s1-final-wplto: "
        + ("PASS" if green else "FIRST RED")
        + f" text={walls.get('bank0_text_headroom_bytes') if walls else None}"
        + f" e000={walls.get('e000_headroom_bytes') if walls else None}"
        + f" main={value['regions']['main_bytes']}"
        + f" overflow={value['regions']['overflow_used_bytes']}")
    return 0 if green else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FinalMapError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-two-region-e000-s1-final-wplto: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
