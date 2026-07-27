#!/usr/bin/env python3
"""Artifact-only completion of the export-symbol-domain WPLTO gates."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_export_symbol_domain_wplto as PROBE  # noqa: E402
import c2_lite_v6_roots_fronts_coresident_wplto_replay as BASE  # noqa: E402


OUT = PROBE.OUT
FULL = OUT / "full-product-wplto"
TARGET = FULL / "c2-lite-v6-full-seed.prg"
ELF = Path(str(TARGET) + ".elf")
FIRST_RED = PROBE.RECEIPT
FIRST_RED_SHA = (
    "a16e726eed8933f42495e53162bb6f2095a8ebf5fa57a7a188d8d0da364f170a")
RECEIPT = PROBE.EVIDENCE / (
    "c2.2-c2-lite-v6-export-symbol-domain-wplto-"
    "artifact-replay-receipt.json")
GATE_OUT = OUT / "artifact-replay-gates"


def configure_base() -> None:
    BASE.OUT = OUT
    BASE.FULL = FULL
    BASE.TARGET = TARGET
    BASE.ELF = ELF
    BASE.GATE_OUT = GATE_OUT


def replay_real_plan() -> dict[str, Any]:
    binary = OUT / "export-symbol-domain-host"
    stdout = OUT / "export-symbol-domain-host.stdout.txt"
    stderr = OUT / "export-symbol-domain-host.stderr.txt"
    PROBE.require(
        "PASS rows=353 foreign-domains-rejected=5" in
            stdout.read_text(encoding="utf-8")
        and not stderr.read_text(encoding="utf-8"),
        "bound 353-row host matrix result is red")
    return {
        "status": "passed-bound-real-plan-binary-replay",
        "accepted_real_rows": 353,
        "negative_cases": 5,
        "rejected_domains": ["heap-pointer", "NIL", "Fixnum", "BCODE",
                             "odd-damaged-SYMI"],
        "compiler_runs": 0, "binary_reexecution": 0,
        "fixture": PROBE.bind(PROBE.FIXTURE),
        "real_plan": PROBE.bind(PROBE.REAL_PLAN),
        "binary": PROBE.bind(binary),
        "original_stdout": PROBE.bind(stdout),
        "original_stderr": PROBE.bind(stderr),
    }


def build() -> dict[str, Any]:
    PROBE.require(not RECEIPT.exists(), "artifact replay already exists")
    PROBE.require(FIRST_RED.is_file() and PROBE.sha(FIRST_RED) == FIRST_RED_SHA,
                  "WPLTO path-model First Red drift")
    PROBE.require(TARGET.is_file() and ELF.is_file(),
                  "frozen WPLTO product/ELF absent")
    configure_base()
    # Recreate only the Python-side profile that interprets the frozen ELF.
    BASE.STAGE.apply_profile(BASE.STAGE.BASE.configure)
    BASE.PROBE.configure_roots_fronts()
    wplto = BASE.reconstruct_wplto()
    gates = BASE.replay_gates(wplto)
    product = {
        "status": "passed-export-symbol-domain-product-shaped-WPLTO-replay",
        "whole_program_lto": wplto,
        "capacity": {"walls": wplto["walls"], "e000_floor_bytes": 115,
                     "session_aggregate":
                         wplto["successor_bank3_pack"]["session"]},
        "fresh_gates": gates,
        "artifacts": {
            "measurement_product": PROBE.bind(TARGET),
            "measurement_elf": PROBE.bind(ELF),
            "measurement_map": PROBE.bind(Path(str(TARGET) + ".map")),
        },
    }
    aggregate = PROBE.RF.product_gate(product)
    source = PROBE.source_domain_gate()
    generated = PROBE.source_domain_gate(
        FULL / "generated-product-sources/c2_product_runtime.c")
    plan = replay_real_plan()
    coresident = PROBE.CORESIDENT.source_contract_gate()
    island = PROBE.ISLAND.audit(
        ELF,
        FULL / "runtime-overlays-boot-c2-lite.bin",
        FULL / "runtime-overlays-boot-c2-lite.json",
        FULL / "generated-product-sources/vm_runtime_overlay.c",
        GATE_OUT / "final-island-identity-gate.json")
    PROBE.require(island["mutation_cases"] == 11,
                  "final-Island identity gate replay incomplete")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    value = {
        "format": "lisp65-c2-lite-v6-export-symbol-domain-artifact-replay-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-export-symbol-domain-WPLTO-artifact-only-replay",
        "scope": {"whole_program_lto_probes": 0,
                  "replayed_prior_wplto_artifacts": 1,
                  "compiler_runs": 0, "product_links": 0,
                  "hardware_runs": 0, "promotable": False},
        "authority": {
            "class_c": PROBE.authority(),
            "path_model_first_red": PROBE.bind(FIRST_RED),
            "driver": PROBE.bind(Path(__file__)),
            "frozen_artifacts": first["evidence"],
        },
        "harness_correction": {
            "class": "Class A output-path model only",
            "old_missing_path": str(OUT / "c2-product-kernal-window.bin"),
            "actual_product_directory": str(FULL),
            "source_elf": PROBE.bind(ELF),
            "compiler_or_linker_runs": 0,
        },
        "source_domain_gate": source,
        "real_353_row_plan_gate": plan,
        "co_resident_contract_gate": coresident,
        "product_shaped_wplto": product,
        "aggregate_recovery": aggregate,
        "generated_source_domain_gate": generated,
        "final_island_identity_gate": island,
        "line1_first_red_budget": "1/3 consumed; 2 remain",
        "latency_measurement_attempts": "0/2 consumed",
        "claim_limit": "Artifact-only completion of the one authorized "
                       "WPLTO. No new compiler/linker run, product link, "
                       "hardware, latency, promotion or acceptance claim.",
        "rollback_line": {**PROBE.bind(PROBE.LINK42), "status": "untouched"},
        "next_gate": "Separate Class-C authorization for the successor product link",
    }
    report = OUT / "export-symbol-domain-artifact-replay-report.json"
    PROBE.write_json(report, value)
    value["replay_report"] = PROBE.bind(report)
    PROBE.write_json(RECEIPT, value)
    PROBE.protect()
    os.chmod(report, 0o444)
    os.chmod(RECEIPT, 0o444)
    return value


def main() -> int:
    try:
        value = build()
    except Exception as error:
        print("c2-lite-v6-export-symbol-domain-replay: FIRST RED " + str(error))
        return 2
    walls = value["product_shaped_wplto"]["capacity"]["walls"]
    aggregate = value["aggregate_recovery"]
    print("c2-lite-v6-export-symbol-domain-replay: PASS "
          "rows=353 negatives=5 "
          f"publish={aggregate['slice']['bytes']}B "
          f"session={aggregate['session_family_bytes']}B "
          f"headroom={aggregate['session_family_headroom_bytes']}B "
          f"text={walls['bank0_text_headroom_bytes']}B "
          f"e000={walls['e000_headroom_bytes']}B "
          "compiler=0 link=0 hardware=0 budget=1/3 latency=0/2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
