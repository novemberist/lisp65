#!/usr/bin/env python3
"""Complete the phase-02b WPLTO gates from its frozen linked artifacts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import c2_lite_v6_bank2_target_stage_phase02b_wplto as PROBE
import c2_lite_v6_roots_fronts_coresident_wplto_replay as BASE


B = PROBE.B
ROOT = B.ROOT
OUT = PROBE.OUT
FULL = OUT / "full-product-wplto"
TARGET = FULL / "c2-lite-v6-full-seed.prg"
ELF = Path(str(TARGET) + ".elf")
FIRST_RED = PROBE.RECEIPT
FIRST_RED_SHA = (
    "b4e5ccb034ed185a1ab86f3d0b470173e08b4cb47c727a7d6dcaf103e451dfb8")
RECEIPT = B.EVIDENCE / (
    "c2.2-c2-lite-v6-bank2-target-stage-phase02b-"
    "artifact-replay-receipt.json")
GATE_OUT = OUT / "artifact-replay-gates"
HOST_SEMANTICS = ROOT / (
    "build/c2-lite/v6-coresident-diet-successor-wplto-probe/"
    "shared-semantics-gate.json")
SUBSTITUTION = ROOT / "build/c2.2/substitution/substitution-artifacts.json"


def configure_base() -> None:
    BASE.OUT = OUT
    BASE.FULL = FULL
    BASE.TARGET = TARGET
    BASE.ELF = ELF
    BASE.GATE_OUT = GATE_OUT
    BASE.STAGE.apply_profile(BASE.STAGE.BASE.configure)
    BASE.PROBE.configure_roots_fronts()
    B.configure_bank2_stage()


def fixture_product() -> dict[str, Any]:
    host = json.loads(HOST_SEMANTICS.read_text(encoding="utf-8"))
    substitution = json.loads(SUBSTITUTION.read_text(encoding="utf-8"))
    artifacts = dict(host["host_v6"]["artifacts"])
    artifacts["shelf"] = substitution["artifacts"]["shelf"]
    B.require(artifacts["c2d"]["bytes"] == 33840
              and artifacts["code"]["bytes"] == B.STATIC_BYTES
              and artifacts["shelf"]["bytes"] == 70897,
              "Bank-2 fixture authority geometry drift")
    return {"host_c2d_v6": {"artifacts": artifacts}}


def build() -> dict[str, Any]:
    B.require(not RECEIPT.exists(), "phase-02b artifact replay already exists")
    B.require(FIRST_RED.is_file() and B.sha(FIRST_RED) == FIRST_RED_SHA,
              "phase-02b WPLTO path-model First Red drift")
    B.require(TARGET.is_file() and ELF.is_file(),
              "frozen phase-02b WPLTO artifacts absent")
    configure_base()
    wplto = BASE.reconstruct_wplto()
    gates = BASE.replay_gates(wplto)
    product = {
        "status": "passed-bank2-phase02b-product-shaped-WPLTO-replay",
        "whole_program_lto": wplto,
        "capacity": {
            "walls": wplto["walls"], "e000_floor_bytes": 115,
            "session_aggregate": wplto["successor_bank3_pack"]["session"],
        },
        "fresh_gates": gates,
        "artifacts": {
            "measurement_product": B.bind(TARGET),
            "measurement_elf": B.bind(ELF),
            "measurement_map": B.bind(Path(str(TARGET) + ".map")),
        },
    }
    aggregate = B.RF.product_gate(product)
    target = B.elf_gate(product)
    workbench = B.target_fixture(fixture_product())
    source = PROBE.source_gate(test_mutations=False)
    mutation_files = sorted((OUT / "mutations").glob("*.c"))
    B.require(len(mutation_files) == 10,
              "bound source mutation inventory is incomplete")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    value = {
        "format": "lisp65-c2-lite-v6-bank2-phase02b-artifact-replay-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-complete-bank2-target-stage-phase02b-WPLTO",
        "scope": {
            "whole_program_lto_probes": 0,
            "replayed_prior_wplto_artifacts": 1,
            "compiler_runs": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "promotable": False,
        },
        "authority": {
            "class_c": PROBE.authority(),
            "path_model_first_red": B.bind(FIRST_RED),
            "driver": B.bind(Path(__file__)),
            "frozen_artifacts": first["evidence"],
            "host_semantics": B.bind(HOST_SEMANTICS),
            "substitution_artifacts": B.bind(SUBSTITUTION),
        },
        "harness_correction": {
            "class": "Class A output-path model only",
            "old_missing_path": str(OUT / "c2-product-kernal-window.bin"),
            "actual_product_directory": str(FULL),
            "source_elf": B.bind(ELF),
            "compiler_or_linker_runs": 0,
        },
        "source_contract": source,
        "bound_source_mutations": {
            "status": "passed-before-the-frozen-WPLTO",
            "count": len(mutation_files),
            "artifacts": [B.bind(path) for path in mutation_files],
        },
        "product_shaped_wplto": product,
        "aggregate_recovery": aggregate,
        "target_dataflow_gate": target,
        "workbench_scratch_negative_fixture": workbench,
        "product_first_red_budget": "2/3 consumed; 1 remains",
        "latency_measurement_attempts": "0/2 consumed",
        "claim_limit": "Artifact-only completion of the one authorized "
                       "phase-02b WPLTO. No compiler, linker, product link, "
                       "hardware, latency, promotion or acceptance claim.",
        "rollback_line": {**B.bind(B.LINK43), "status": "untouched"},
        "next_gate": "The already authorized successor product link",
    }
    report = OUT / "bank2-phase02b-artifact-replay-report.json"
    B.write_json(report, value)
    value["replay_report"] = B.bind(report)
    B.write_json(RECEIPT, value)
    B.protect()
    os.chmod(report, 0o444)
    os.chmod(RECEIPT, 0o444)
    return value


def main() -> int:
    try:
        value = build()
    except Exception as error:
        print("c2-lite-v6-bank2-phase02b-replay: FIRST RED " + str(error))
        return 2
    phase = value["target_dataflow_gate"]["phase"]
    walls = value["product_shaped_wplto"]["capacity"]["walls"]
    fixture = value["workbench_scratch_negative_fixture"]
    print("c2-lite-v6-bank2-phase02b-replay: PASS "
          f"phase03b={phase['bytes']}B "
          f"text={walls['bank0_text_headroom_bytes']}B "
          f"e000={walls['e000_headroom_bytes']}B "
          f"workbench-passing={fixture['workbench_scratch_passing_records']} "
          "compiler=0 link=0 hardware=0 budget=2/3 latency=0/2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
