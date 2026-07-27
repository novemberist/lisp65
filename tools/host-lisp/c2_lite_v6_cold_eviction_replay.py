#!/usr/bin/env python3
"""Pure gate replay for the cold-eviction WPLTO after the rtov parser fix."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link33_bss_triage_product_link as BASE  # noqa: E402
import c2_lite_v6_cold_eviction_probe as COLD  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402


SOURCE_OUT = ROOT / "build/c2-lite/v6-cold-eviction-wplto-probe"
OUT = ROOT / "build/c2-lite/v6-cold-eviction-wplto-pure-replay"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-cold-eviction-wplto-probe-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-cold-eviction-wplto-pure-replay-receipt.json")
TARGET = SOURCE_OUT / "full-product-wplto/c2-lite-v6-full-seed.prg"
ELF = Path(str(TARGET) + ".elf")
MAP = Path(str(TARGET) + ".map")


class ReplayError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError(message)


def bind(path: Path) -> dict[str, Any]:
    return COLD.bind(path)


def configure() -> None:
    BASE.configure()
    COLD.configure_cold_eviction()
    PRODUCT.E000_FINAL_FLOOR_BYTES = COLD.E000_FLOOR


def reconstruct_wplto_truth() -> dict[str, Any]:
    sections = PRODUCT.section_table(ELF)
    text = sections[".text"]
    bss = sections[".bss"]
    walls = {
        "bank0_text_headroom_bytes":
            PRODUCT.HANDOFF_BASE - text["address"] - text["bytes"],
        "ordinary_bank0_bss_headroom_bytes":
            PRODUCT.FIXED_BANK0_BASE - bss["address"] - bss["bytes"],
        "fixed_hot_block_headroom_bytes": PRODUCT.fixed_bank0_headroom_bytes(),
        "resident_island_headroom_bytes": 2048 - sum(
            sections.get(name, {}).get("bytes", 0) for name in
            (".lisp65_resident_island", ".lisp65_resident_island_annex")),
        "e000_headroom_bytes": PRODUCT.KERNAL_WINDOW_BYTES - sum(
            sections[name]["bytes"] for name in PRODUCT.KERNAL_SECTIONS),
    }
    require(all(value >= 0 for value in walls.values())
            and walls["e000_headroom_bytes"] >= COLD.E000_FLOOR,
            "replayed WPLTO wall red: " + str(walls))
    slice_sections = {spec.split(":")[2] for spec in
                      PRODUCT.BOOT_SLICE_SPECS + PRODUCT.SESSION_SLICE_SPECS}
    slice_sizes = {name: sections.get(name, {}).get("bytes", 0)
                   for name in slice_sections}
    over = {name: size for name, size in slice_sizes.items()
            if size <= 0 or size > COLD.CAP}
    require(not over, "replayed runtime slice wall red: " + str(over))

    generated = TARGET.parent / "generated-product-sources"
    generated_hot = (generated / "c2_hot_literal.c").read_text(encoding="utf-8")
    generated_runtime = (generated / "c2_product_runtime.c").read_text(
        encoding="utf-8")
    generated_rtov = (generated / "vm_runtime_overlay.c").read_text(
        encoding="utf-8")
    hot_entry = V6.c_function_definition(
        generated_runtime, "c2_product_entry_read")
    rtov_read = V6.c_function_definition(generated_rtov, "rtov_read")
    hot_checks = {
        "materializer_has_no_shelf_read":
            "c2_stream_shelf_read" not in generated_hot,
        "entry_read_has_no_shelf_read":
            "c2_stream_shelf_read" not in hot_entry,
        "entry_read_has_no_attic_dma": "c2_dma_copy" not in hot_entry,
        "native_read_has_no_completion_retry":
            "rtov_dma_submit_wait" not in rtov_read,
        "bytecode_reads_bank2": "c2_facade_vm_code_load(2u" in hot_entry,
        "native_slices_read_bank3": "c2_facade_vm_code_load(3u" in rtov_read,
    }
    require(all(hot_checks.values()),
            "corrected hot no-Attic gate red: "
            + str([name for name, ok in hot_checks.items() if not ok]))

    boot_image = TARGET.parent / "runtime-overlays-boot-c2-lite.bin"
    session_image = TARGET.parent / "runtime-overlays-session-c2-lite.bin"
    require(boot_image.stat().st_size <= V6.BANK_BYTES
            and session_image.stat().st_size <= V6.BANK_BYTES,
            "replayed Bank-3 family union red")
    return {
        "status": "passed-pure-artifact-replay",
        "walls": walls,
        "runtime_slices": {
            "count": len(slice_sizes),
            "cap_bytes": COLD.CAP,
            "largest_bytes": max(slice_sizes.values()),
            "minimum_headroom_bytes": COLD.CAP - max(slice_sizes.values()),
            "all_fit": True,
        },
        "successor_bank3_pack": {
            "boot": {**bind(boot_image),
                     "headroom_bytes": V6.BANK_BYTES - boot_image.stat().st_size},
            "session": {**bind(session_image),
                        "headroom_bytes": V6.BANK_BYTES
                        - session_image.stat().st_size},
        },
        "hot_no_runtime_attic_gate": {
            "status": "passed-after-definition-aware-parser-fix",
            "checks": hot_checks,
        },
        "compiler_runs": 0,
        "linker_runs": 0,
        "hardware_runs": 0,
    }


def protect() -> None:
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    if RECEIPT.is_file():
        os.chmod(RECEIPT, 0o444)


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "cold-eviction pure replay is one-shot and already exists")
    require(FIRST_RED.is_file() and TARGET.is_file() and ELF.is_file()
            and MAP.is_file(), "bound WPLTO First-Red artifact set is incomplete")
    for path in (TARGET, ELF, MAP, Path(str(TARGET) + ".lto.o")):
        require(path.stat().st_mode & 0o222 == 0,
                f"replay input is not physically read-only: {path}")
    first_red = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(first_red["failure"] == "hot no-Attic source closure is red",
            "unexpected replay predecessor")
    OUT.mkdir(parents=True)
    configure()
    wplto = reconstruct_wplto_truth()
    # closure_gate consumes the canonical final-family filename.  The probe
    # pack is already immutable; expose a byte-for-byte replay alias instead
    # of repacking or relinking it.
    shutil.copyfile(
        TARGET.parent / "runtime-overlays-session-c2-lite.bin",
        OUT / "runtime-overlays-final.bin")
    shutil.copyfile(
        TARGET.parent / "runtime-overlays-boot-c2-lite.bin",
        OUT / "runtime-overlays-boot-final.bin")
    shutil.copyfile(
        TARGET.parent / "runtime-overlays-session-c2-lite.bin",
        OUT / "runtime-overlays-session-final.bin")
    gates = COLD.structural_gates(TARGET, ELF, report_out=OUT)
    eviction = COLD.eviction_and_anchor_gate(wplto, ELF)
    value = {
        "format": "lisp65-c2-lite-v6-cold-eviction-wplto-pure-replay-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-pure-replay-no-compiler-no-link-no-hardware",
        "scope": {"class": "A", "compiler_runs": 0, "linker_runs": 0,
                  "product_links": 0, "hardware_runs": 0,
                  "product_bytes_changed": 0},
        "first_red": bind(FIRST_RED),
        "immutable_inputs": {
            "measurement_prg": bind(TARGET),
            "measurement_elf": bind(ELF),
            "measurement_map": bind(MAP),
            "saved_lto_object": bind(Path(str(TARGET) + ".lto.o")),
        },
        "harness_correction": {
            "class": "A",
            "cause": (
                "the old gate selected the first rtov_read occurrence, a "
                "forward declaration, instead of the function definition"),
            "fix": (
                "shared brace-aware definition extraction skips prototypes "
                "and forward declarations"),
            "product_delta_bytes": 0,
            "gate_before": "false red",
            "gate_after": "passed",
        },
        "additional_class_a_correction": {
            "cause": (
                "the section-inventory expectation derived the append ABI "
                "from the configured profile but retained Link-28's unsplit "
                "decoder ABI"),
            "fix": (
                "derive both decoder and append section-name sets from their "
                "configured canonical slice lists"),
            "first_replay_result": (
                "correctly rejected 11 versus 11a/11b expectation drift"),
            "product_delta_bytes": 0,
        },
        "replay_alias_correction": {
            "cause": (
                "the generic one-truth gate expects the canonical final-family "
                "filename, while the C2-lite probe pack is suffixed c2-lite"),
            "fix": (
                "byte-identical replay-only aliases of both immutable family "
                "packs; no pack, compiler or linker rerun"),
            "product_delta_bytes": 0,
        },
        "whole_program_lto_replay": wplto,
        "cold_eviction": eviction,
        "fresh_structural_gates": gates,
        "claim_limit": (
            "Read-only replay of one previously emitted, nonpromotable WPLTO "
            "artifact set. No product link, hardware, performance, promotion "
            "or acceptance claim."),
        "rollback_line": {"product": "Link 35", "status": "untouched"},
        "next_gate": "Class-C review before the first C2-lite product link",
    }
    COLD.write_json(OUT / "pure-replay-report.json", value)
    value["replay_report"] = bind(OUT / "pure-replay-report.json")
    COLD.write_json(RECEIPT, value)
    protect()
    return value


def main() -> int:
    try:
        value = build()
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            RuntimeError) as error:
        print("c2-lite-v6-cold-eviction-replay: FIRST RED " + str(error))
        return 2
    walls = value["whole_program_lto_replay"]["walls"]
    anchor = value["cold_eviction"]["anchor_resolution"]
    print("c2-lite-v6-cold-eviction-replay: PASS "
          f"e000={walls['e000_headroom_bytes']} "
          f"anchor-overlap={anchor['after_overlap_bytes']} "
          "compiler=0 linker=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
