#!/usr/bin/env python3
"""Class-A replay after qualifying the E000 capacity inventory by ELF VMA.

Replay 1 correctly completed the relocation gate but its reporting helper
summed the process-default KERNAL section list.  The product profile registers
the three reopening sections and profile data dynamically, so that helper
under-counted 416 bytes and reported a false 672-byte margin.  This replay
uses every SHF_ALLOC section whose VMA lies in $E000..$FFFF; the independent
product-link report must agree on the resulting 256-byte margin.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link44_dirmiss_e000_eviction_artifact_replay as R1  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


REPLAY1 = R1.RECEIPT
REPLAY1_SHA = (
    "37a28a633297f23769f20199f5e83db60b5b0a68c3524cca24cb66f1db329205")
DIAGNOSIS = R1.PROBE.EVIDENCE / (
    "c2.2-link44-dirmiss-detail-e000-eviction-"
    "capacity-inventory-harness-diagnosis.json")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link44-dirmiss-detail-e000-eviction-artifact-replay2")
RECEIPT = R1.PROBE.EVIDENCE / (
    "c2.2-link44-dirmiss-detail-e000-eviction-"
    "artifact-replay2-receipt.json")


def e000_capacity(truth: ElfTruth) -> dict[str, Any]:
    allocated = sorted(
        (section for section in truth.sections
         if "SHF_ALLOC" in section.flags and section.bytes > 0
         and 0xE000 <= section.address
         and section.address + section.bytes <= 0x10000),
        key=lambda section: (section.address, section.name))
    live = sum(section.bytes for section in allocated)
    margin = 0x2000 - live
    R1.require(margin == 256 and margin >= 115,
               f"VMA-complete E000 inventory drift: live={live} margin={margin}")
    product_report = json.loads(
        (R1.OUT / "product-substitution-link.json").read_text())
    R1.require(product_report["actual_e000_future_margin_bytes"] == margin,
               "independent product-link E000 margin disagrees with ELF VMA inventory")
    return {
        "status": "passed-all-SHF_ALLOC-window-sections-and-independent-link-report",
        "gross_bytes": 0x2000,
        "live_bytes": live,
        "headroom_bytes": margin,
        "floor_bytes": 115,
        "floor_clearance_bytes": margin - 115,
        "sections": [
            {"name": section.name, "address": f"0x{section.address:04x}",
             "bytes": section.bytes, "flags": list(section.flags)}
            for section in allocated],
    }


def capacity_gate(truth: ElfTruth) -> dict[str, Any]:
    P = R1.DETAIL.LINK44.P
    sections = P.section_table(R1.ELF)
    text, bss = sections[".text"], sections[".bss"]
    window = e000_capacity(truth)
    walls = {
        "bank0_text_headroom_bytes":
            P.HANDOFF_BASE - text["address"] - text["bytes"],
        "ordinary_bank0_bss_headroom_bytes":
            P.FIXED_BANK0_BASE - bss["address"] - bss["bytes"],
        "fixed_hot_block_headroom_bytes": P.fixed_bank0_headroom_bytes(),
        "resident_island_headroom_bytes": 2048 - sum(
            sections.get(name, {}).get("bytes", 0) for name in
            (".lisp65_resident_island", ".lisp65_resident_island_annex")),
        "e000_headroom_bytes": window["headroom_bytes"],
    }
    R1.require(walls["bank0_text_headroom_bytes"] >= 32
               and walls["e000_headroom_bytes"] >= 115
               and all(value >= 0 for value in walls.values()),
               f"qualified frozen evacuation walls red: {walls}")
    first = json.loads(R1.PROBE.FIRST_RED.read_text())
    relief = first["first_red"]["probe"]["text_bytes"] - text["bytes"]
    R1.require(relief >= 86, f"qualified evacuation relief red: {relief}")
    session = json.loads(
        (R1.OUT / "runtime-overlays-session-final.json").read_text())
    R1.require(session["storage"]["size"] == 65438,
               "qualified Session aggregate drift")
    return {
        "status": "passed-qualified-WPLTO-all-walls-and-aggregate",
        "walls": walls,
        "window_inventory": window,
        "measured_bank0_relief_from_first_red_bytes": relief,
        "required_relief_bytes": 86,
        "standing_text_reserve_bytes": walls["bank0_text_headroom_bytes"],
        "session_family_bytes": session["storage"]["size"],
        "session_family_headroom_bytes": 65536 - session["storage"]["size"],
    }


def build() -> dict[str, Any]:
    R1.require(not OUT.exists() and not RECEIPT.exists()
               and not DIAGNOSIS.exists(),
               "qualified E000 artifact replay is one-shot")
    R1.require(REPLAY1.is_file() and R1.sha(REPLAY1) == REPLAY1_SHA,
               "Replay-1 capacity-reporting First Red drift")
    first = json.loads(REPLAY1.read_text())
    R1.require(first["status"].startswith("passed-")
               and first["capacity"]["walls"]["e000_headroom_bytes"] == 672,
               "Replay-1 is not the dynamically incomplete inventory witness")
    diagnosis = {
        "format": "lisp65-c2-lite-v6-e000-capacity-inventory-harness-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-class-a-VMA-complete-window-inventory-correction",
        "replay1": R1.bind(REPLAY1),
        "cause": (
            "The replay imported the process-default KERNAL_SECTIONS list. "
            "The product profile had dynamically registered reopen_gap0/1/2 "
            "and profile_rodata; omitting them under-counted 416 live bytes."),
        "correction": (
            "Count every SHF_ALLOC ELF section wholly resident at "
            "$E000..$FFFF and require equality with the independent product-link report."),
        "scope": {"product_bytes_changed": 0, "capacity_effect_bytes": 0,
                  "compiler_runs": 0, "linker_runs": 0,
                  "product_links": 0, "hardware_runs": 0},
    }
    R1.write(DIAGNOSIS, diagnosis)
    os.chmod(DIAGNOSIS, 0o444)
    OUT.mkdir(parents=True)
    truth = ElfTruth.read(
        R1.ELF,
        llvm_readobj=R1.DETAIL.LINK44.P.TOOLCHAIN / "llvm-readobj")
    source = R1.DETAIL.source_gate(
        R1.DETAIL.VM.read_text(), R1.DETAIL.VM_H.read_text(),
        R1.DETAIL.EVAL.read_text(), R1.DETAIL.COMPILE.read_text(),
        R1.DETAIL.INTERRUPT.read_text(),
        R1.DETAIL.ERROR_OVERLAY.read_text(), mutations=True)
    candidate_source = R1.PROBE.contract_gate(
        (ROOT / "src/vm.c").read_text(), mutations=True)
    value = {
        "format": "lisp65-c2-lite-v6-link44-dirmiss-e000-artifact-replay2-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-complete-dirmiss-detail-E000-evacuation-WPLTO-artifact-replay",
        "promotable": False,
        "scope": {"replayed_prior_wplto_artifacts": 1,
                  "compiler_runs": 0, "linker_runs": 0,
                  "product_links": 0, "hardware_runs": 0},
        "authority": {
            "replay1_reporting_witness": R1.bind(REPLAY1),
            "capacity_inventory_diagnosis": R1.bind(DIAGNOSIS),
            "relocation_model_first_red": R1.bind(R1.FIRST_RED),
            "evacuation_contract": R1.bind(R1.PROBE.CONTRACT),
            "driver": R1.bind(Path(__file__)),
        },
        "detail_source_contract": source,
        "evacuation_source_contract": candidate_source,
        "candidate_selection": R1.PROBE.premove_candidate_gate(),
        "linked_detail": R1.detail_gate(truth),
        "linked_eviction": R1.PROBE.linked_eviction_gate(R1.ELF),
        "capacity": capacity_gate(truth),
        "fresh_gate_replay": R1.existing_gate_reachability(),
        "frozen_identity": {"product": R1.bind(R1.PRODUCT),
                            "elf": R1.bind(R1.ELF),
                            "map": R1.bind(R1.MAP)},
        "rollback_line": {**R1.bind(R1.DETAIL.BASE_PRODUCT),
                          "status": "untouched"},
        "counters": {"class_b": "3/3 exhausted",
                     "line1_product_first_reds": "2/3",
                     "completed_latency_measurements": "0/2"},
        "claim_limit": (
            "Artifact-only completion of the authorized WPLTO; no compiler, "
            "linker, hardware, latency, promotion or product-candidate claim."),
        "next_gate": "the already authorized one successor product link",
    }
    report = OUT / "artifact-replay2-report.json"
    R1.write(report, value)
    value["replay_report"] = R1.bind(report)
    R1.write(RECEIPT, value)
    os.chmod(report, 0o444)
    os.chmod(RECEIPT, 0o444)
    return value


def main() -> int:
    try:
        value = build()
        walls = value["capacity"]["walls"]
        print("c2-lite-v6-link44-dirmiss-e000-artifact-replay2: PASS "
              f"text={walls['bank0_text_headroom_bytes']} "
              f"e000={walls['e000_headroom_bytes']} floor=115 "
              "compiler=0 link=0 hardware=0")
        return 0
    except Exception as error:
        print("c2-lite-v6-link44-dirmiss-e000-artifact-replay2: FIRST RED "
              + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
