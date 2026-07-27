#!/usr/bin/env python3
"""Artifact-only completion of the final-Island WPLTO gate set."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_final_island_identity_gate as IDENTITY  # noqa: E402
import c2_lite_v6_final_island_identity_wplto as PROBE  # noqa: E402
import c2_lite_v6_roots_fronts_coresident_wplto_replay as REPLAY  # noqa: E402


OUT = ROOT / "build/c2-lite/v6-final-island-identity-wplto-replay2"
FULL = OUT / "full-product-wplto"
TARGET = FULL / "c2-lite-v6-full-seed.prg"
ELF = Path(str(TARGET) + ".elf")
FIRST_RED = PROBE.EVIDENCE / (
    "c2.2-c2-lite-v6-final-island-identity-wplto-replay2-receipt.json")
FIRST_RED_SHA = (
    "1297a532d2bb0dd46f91f0401a4ea68cceefa9dcb6cd6c9c5d17e02acf179f7c")
RECEIPT = PROBE.EVIDENCE / (
    "c2.2-c2-lite-v6-final-island-identity-wplto-"
    "artifact-replay-receipt.json")
GATE_OUT = OUT / "artifact-replay-gates"


def bind(path: Path) -> dict[str, Any]:
    return PROBE.bind(path)


def configure_replay_module() -> None:
    REPLAY.OUT = OUT
    REPLAY.FULL = FULL
    REPLAY.TARGET = TARGET
    REPLAY.ELF = ELF
    REPLAY.GATE_OUT = GATE_OUT


def build() -> dict[str, Any]:
    PROBE.require(not RECEIPT.exists(), "artifact replay already exists")
    PROBE.require(FIRST_RED.is_file() and PROBE.sha(FIRST_RED) ==
                  FIRST_RED_SHA, "WPLTO gate-path First Red drift")
    PROBE.require(TARGET.is_file() and ELF.is_file(),
                  "frozen WPLTO artifacts absent")
    configure_replay_module()
    # Restore only the Python-side profile needed to interpret the frozen ELF.
    REPLAY.STAGE.apply_profile(REPLAY.STAGE.BASE.configure)
    PROBE.RF.configure_roots_fronts()
    wplto = REPLAY.reconstruct_wplto()
    gates = REPLAY.replay_gates(wplto)
    product = {
        "status": "passed-final-island-product-shaped-WPLTO-replay",
        "whole_program_lto": wplto,
        "capacity": {"walls": wplto["walls"], "e000_floor_bytes": 115,
                     "session_aggregate":
                         wplto["successor_bank3_pack"]["session"]},
        "fresh_gates": gates,
        "artifacts": {"measurement_product": bind(TARGET),
                      "measurement_elf": bind(ELF),
                      "measurement_map": bind(Path(str(TARGET) + ".map"))},
    }
    aggregate = PROBE.RF.product_gate(product)
    identity = IDENTITY.audit(
        ELF, FULL / "runtime-overlays-boot-c2-lite.bin",
        FULL / "runtime-overlays-boot-c2-lite.json",
        FULL / "generated-product-sources/vm_runtime_overlay.c",
        GATE_OUT / "final-island-identity-gate.json")
    PROBE.require(identity["mutation_cases"] == 11,
                  "final-Island mutation matrix incomplete")
    host_stdout = OUT / "final-carrier-runtime-host.stdout.txt"
    PROBE.require(
        "PASS publish-last+14 fail-closed cases" in
            host_stdout.read_text(encoding="utf-8"),
        "bound active runtime host matrix is not green")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    value = {
        "format": "lisp65-c2-lite-v6-final-island-artifact-replay-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-final-island-carrier-single-runtime-identity-"
                  "WPLTO-artifact-replay",
        "scope": {"whole_program_lto_probes": 0,
                  "replayed_prior_wplto_artifacts": 1,
                  "compiler_runs": 0, "product_links": 0,
                  "hardware_runs": 0, "promotable": False},
        "authority": {"gate_path_first_red": bind(FIRST_RED),
                      "driver": bind(Path(__file__)),
                      "frozen_artifacts": first["evidence"]},
        "harness_correction": {
            "class": "Class A output-path model only",
            "old_missing_path": str(OUT / "c2-product-kernal-window.bin"),
            "actual_product_directory": str(FULL),
            "source": bind(ELF),
            "compiler_or_linker_runs": 0,
        },
        "source_contract": IDENTITY.source_gate(
            FULL / "generated-product-sources/vm_runtime_overlay.c"),
        "active_runtime_host_matrix": {
            "status": "passed-active-v3-installer-accepts-non-seed-identity",
            "carrier_bytes": 5, "seed_length_compile_constant": 4,
            "seed_identity_used_at_runtime": False,
            "publish_last_fail_closed_cases": 14,
            "family_slot_cartesian_cases": 8,
            "binary": bind(OUT / "final-carrier-runtime-host"),
            "fixture": bind(OUT / "final-carrier-runtime-host.c"),
            "stdout": bind(host_stdout),
            "stderr": bind(OUT / "final-carrier-runtime-host.stderr.txt"),
        },
        "product_shaped_wplto": product,
        "aggregate_recovery": aggregate,
        "final_island_identity_gate": identity,
        "rollback_line": {**bind(PROBE.LINK41), "status": "untouched"},
        "latency_attempts_consumed": "0/2",
        "next_gate": "Authorized successor product link",
    }
    report = OUT / "final-island-identity-artifact-replay-report.json"
    PROBE.write_json(report, value)
    value["replay_report"] = bind(report)
    PROBE.write_json(RECEIPT, value)
    for path in GATE_OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(report, 0o444)
    os.chmod(RECEIPT, 0o444)
    return value


def main() -> int:
    try:
        value = build()
    except Exception as error:
        print("c2-final-island-artifact-replay: FIRST RED " + str(error))
        return 2
    walls = value["product_shaped_wplto"]["capacity"]["walls"]
    ident = value["final_island_identity_gate"]["identity"]
    print("c2-final-island-artifact-replay: PASS "
          f"carrier={ident['section_bytes']}B "
          f"crc=0x{ident['section_crc16']:04x} mutations=11/11 "
          f"text={walls['bank0_text_headroom_bytes']}B "
          f"e000={walls['e000_headroom_bytes']}B "
          "compiler=0 link=0 hardware=0 latency=0/2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
