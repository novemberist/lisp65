#!/usr/bin/env python3
"""Authorized successor plus pure replay of its report-builder First Red."""

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_coresident_diet_probe as PROBE  # noqa: E402


PROBE.OUT = ROOT / "build/c2-lite/v6-coresident-diet-successor-wplto-probe"
PROBE.RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-coresident-diet-successor-wplto-probe-receipt.json")
HARNESS_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-coresident-diet-successor-harness-first-red.json")


def replay_existing_wplto() -> tuple[dict, Path, Path]:
    """Reconstruct the report from the already linked and packed artifacts."""
    PROBE.BASE.configure()
    PROBE.configure_coresident_diet()
    product = PROBE.BASE.P
    product.E000_FINAL_FLOOR_BYTES = 115
    features = (*PROBE.BASE.FEATURES,
                "LISP65_C2_PHASE11_SPLIT",
                "LISP65_C2_LITE_COLD_EVICTION",
                "LISP65_C2_LITE_V6_SEMANTIC_SPLITS",
                "LISP65_C2_LITE_V6_CORESIDENT_DIET",
                "LISP65_C2_LITE_CHIP_RAM")
    full = PROBE.OUT / "full-product-wplto"
    target = full / "c2-lite-v6-full-seed.prg"
    elf = Path(str(target) + ".elf")
    boot_image = full / "runtime-overlays-boot-c2-lite.bin"
    boot_manifest = full / "runtime-overlays-boot-c2-lite.json"
    session_image = full / "runtime-overlays-session-c2-lite.bin"
    session_manifest = full / "runtime-overlays-session-c2-lite.json"
    resolved = full / "resolved-profile.txt"
    for path in (target, elf, boot_image, boot_manifest,
                 session_image, session_manifest, resolved):
        PROBE.require(path.is_file(), f"pure-replay artifact absent: {path}")

    sections = product.section_table(elf)
    text = sections[".text"]
    bss = sections[".bss"]
    walls = {
        "bank0_text_headroom_bytes":
            product.HANDOFF_BASE - text["address"] - text["bytes"],
        "ordinary_bank0_bss_headroom_bytes":
            product.FIXED_BANK0_BASE - bss["address"] - bss["bytes"],
        "fixed_hot_block_headroom_bytes": product.fixed_bank0_headroom_bytes(),
        "resident_island_headroom_bytes": 2048 - sum(
            sections.get(name, {}).get("bytes", 0) for name in
            (".lisp65_resident_island", ".lisp65_resident_island_annex")),
        "e000_headroom_bytes": product.KERNAL_WINDOW_BYTES - sum(
            sections[name]["bytes"] for name in product.KERNAL_SECTIONS),
    }
    PROBE.require(all(walls[key] >= 0 for key in walls
                      if key != "e000_headroom_bytes")
                  and walls["e000_headroom_bytes"] >= 115,
                  "pure-replay product wall red: " + str(walls))
    slice_sections = {spec.split(":")[2] for spec in
                      product.BOOT_SLICE_SPECS + product.SESSION_SLICE_SPECS}
    slice_sizes = {name: sections.get(name, {}).get("bytes", 0)
                   for name in slice_sections}
    over = {name: size for name, size in slice_sizes.items()
            if size <= 0 or size > PROBE.CAP}
    PROBE.require(not over, "pure-replay slice wall red: " + str(over))
    boot = json.loads(boot_manifest.read_text(encoding="utf-8"))
    session = json.loads(session_manifest.read_text(encoding="utf-8"))
    PROBE.require(boot["storage"]["size"] == boot_image.stat().st_size
                  <= PROBE.BANK_BYTES
                  and session["storage"]["size"]
                  == session_image.stat().st_size <= PROBE.BANK_BYTES,
                  "pure-replay Bank-3 manifest binding red")

    generated = full / "generated-product-sources"
    generated_hot = (generated / "c2_hot_literal.c").read_text(encoding="utf-8")
    generated_runtime = (generated / "c2_product_runtime.c").read_text(
        encoding="utf-8")
    generated_rtov = (generated / "vm_runtime_overlay.c").read_text(
        encoding="utf-8")
    hot_entry = PROBE.V6.c_function_definition(
        generated_runtime, "c2_product_entry_read")
    rtov_read = PROBE.V6.c_function_definition(generated_rtov, "rtov_read")
    PROBE.require("c2_stream_shelf_read" not in generated_hot
                  and "c2_stream_shelf_read" not in hot_entry
                  and "c2_dma_copy" not in hot_entry
                  and "rtov_dma_submit_wait" not in rtov_read
                  and "c2_facade_vm_code_load(2u" in hot_entry
                  and "c2_facade_vm_code_load(3u" in rtov_read,
                  "pure-replay hot no-Attic closure red")
    retired = {
        "runtime_crc_convergence_define":
            "LISP65_RTOV_CRC_CONVERGENCE" not in features,
        "dma_completion_fence_define":
            "LISP65_RTOV_DMA_COMPLETION_FENCE" not in features,
        "hot_c2i_reads": 0,
        "hot_attic_reads": 0,
        "bank2_loader_callsites": hot_entry.count(
            "c2_facade_vm_code_load(2u"),
        "bank3_loader_callsites": rtov_read.count(
            "c2_facade_vm_code_load(3u"),
    }
    result = {
        "status": "passed-one-full-nonpromotable-product-shaped-wplto",
        "report_mode": "pure-replay-after-Path-length-harness-fix",
        "product_links": 0, "promotable": False, "hardware_runs": 0,
        "target": PROBE.bind(target), "elf": PROBE.bind(elf),
        "map": PROBE.bind(Path(str(target) + ".map")),
        "resolved_profile": PROBE.bind(resolved),
        "walls": walls,
        "runtime_slices": {
            "count": len(slice_sizes), "cap_bytes": PROBE.CAP,
            "largest_bytes": max(slice_sizes.values()),
            "minimum_headroom_bytes": PROBE.CAP - max(slice_sizes.values()),
        },
        "successor_bank3_pack": {
            "boot": {**PROBE.bind(boot_image),
                     "bytes": boot_image.stat().st_size,
                     "headroom_bytes": PROBE.BANK_BYTES
                         - boot_image.stat().st_size},
            "session": {**PROBE.bind(session_image),
                        "bytes": session_image.stat().st_size,
                        "headroom_bytes": PROBE.BANK_BYTES
                            - session_image.stat().st_size},
        },
        "hot_no_runtime_attic_gate": {"status": "passed", **retired},
        "generated_source_count": len(list(generated.glob("*.c"))),
        "claim_limit": (
            "Pure report replay over one already completed nonpromotable WPLTO; "
            "zero compiler runs, links and hardware in the replay."),
    }
    return result, target, elf


def replay_build() -> dict:
    PROBE.require(PROBE.OUT.is_dir() and not PROBE.RECEIPT.exists(),
                  "successor pure replay state is not unique")
    full = PROBE.OUT / "full-product-wplto"
    target = full / "c2-lite-v6-full-seed.prg"
    elf = Path(str(target) + ".elf")
    harness = {
        "format": "lisp65-c2-lite-v6-coresident-successor-harness-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: report builder used len(PosixPath)",
        "failure": "TypeError after both Bank-3 families were linked and packed",
        "correction": "Use Path.stat().st_size; replay existing SHA-bound artifacts",
        "scope": {"product_bytes_changed": 0, "capacity_effect_bytes": 0,
                  "replay_compiler_runs": 0, "replay_links": 0,
                  "replay_hardware_runs": 0},
        "artifacts": {"measurement_prg": PROBE.bind(target),
                      "measurement_elf": PROBE.bind(elf),
                      "boot_pack": PROBE.bind(
                          full / "runtime-overlays-boot-c2-lite.bin"),
                      "session_pack": PROBE.bind(
                          full / "runtime-overlays-session-c2-lite.bin")},
    }
    if not HARNESS_FIRST_RED.exists():
        PROBE.write_json(HARNESS_FIRST_RED, harness)
    HARNESS_FIRST_RED.chmod(0o444)

    attribution = json.loads((PROBE.OUT /
        "payload-attribution-and-pack-model.json").read_text(encoding="utf-8"))
    source = json.loads((PROBE.OUT /
        "source-contract-gate.json").read_text(encoding="utf-8"))
    cutpoints = json.loads((PROBE.OUT /
        "cutpoint-gates.json").read_text(encoding="utf-8"))
    semantics = json.loads((PROBE.OUT /
        "shared-semantics-gate.json").read_text(encoding="utf-8"))
    wplto, target, elf = replay_existing_wplto()
    structural = PROBE.COLD.structural_gates(target, elf)
    capacity = PROBE.capacity_gate(wplto, elf)
    semantic = PROBE.semantic_product_gate(wplto, target, elf)
    root = PROBE.ROOT_GATE.collect()
    PROBE.require(root["status"] == "pass", "root-surrogate replay red")
    value = {
        "format": "lisp65-c2-lite-v6-coresident-diet-successor-replay-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-co-resident-aggregate-diet-pure-report-replay",
        "scope": {"whole_program_lto_probes": 1,
                  "pure_replay_compiler_runs": 0, "pure_replay_links": 0,
                  "product_links": 0, "hardware_runs": 0,
                  "promotable": False},
        "authority": {"contract": PROBE.bind(PROBE.CONTRACT),
                      "addendum": PROBE.bind(PROBE.ADDENDUM),
                      "placement_first_red": PROBE.bind(
                          PROBE.PLACEMENT_FIRST_RED),
                      "harness_first_red": PROBE.bind(HARNESS_FIRST_RED)},
        "class_a_harness_correction": harness,
        "payload_attribution": attribution,
        "source_contract": source,
        "cutpoint_fixtures": cutpoints,
        "shared_semantics": semantics,
        "whole_program_lto": wplto,
        "co_resident_capacity": capacity,
        "product_semantics": semantic,
        "permanent_root_surrogate_gate": root,
        "fresh_structural_gates": structural,
        "artifacts": {"measurement_prg": PROBE.bind(target),
                      "measurement_elf": PROBE.bind(elf),
                      "measurement_map": PROBE.bind(
                          Path(str(target) + ".map"))},
        "claim_limit": (
            "One nonpromotable product-shaped WPLTO plus a pure report replay. "
            "No product link, hardware, performance, promotion or acceptance."),
        "rollback_line": {"product": "Link 35", "status": "untouched"},
        "next_gate": "Class-C review before the first C2-lite product link",
    }
    PROBE.write_json(PROBE.OUT / "coresident-diet-successor-replay.json", value)
    value["probe_report"] = PROBE.bind(
        PROBE.OUT / "coresident-diet-successor-replay.json")
    PROBE.write_json(PROBE.RECEIPT, value)
    PROBE.protect()
    return value


def main() -> int:
    try:
        value = replay_build()
    except Exception as error:
        if not PROBE.RECEIPT.exists():
            PROBE.record_first_red(error)
        print("c2-lite-v6-coresident-diet-successor-replay: FIRST RED "
              + str(error))
        return 2
    capacity = value["co_resident_capacity"]
    print("c2-lite-v6-coresident-diet-successor-replay: PASS "
          f"session={capacity['session_family_bytes']} "
          f"headroom={capacity['session_family_headroom_bytes']} "
          f"largest={value['whole_program_lto']['runtime_slices']['largest_bytes']} "
          "replay-links=0 product-link=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
