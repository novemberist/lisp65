#!/usr/bin/env python3
"""One corrected WPLTO truth run for the shared retry driver and Island split.

This is a non-promotable capacity/placement probe.  It deliberately stops
after the product-shaped seed link: no final product identity is created and
no hardware artifact is eligible for deployment.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_l65r_v3_crc_convergence_wplto as PRIOR  # noqa: E402


P = PRIOR.BASE.P
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "crc-convergence-shared-driver-island-split-wplto")
RECEIPT = EVIDENCE / (
    "c2.2-crc-convergence-shared-driver-island-split-wplto-receipt.json")
SHARED_DEFINE = "LISP65_RTOV_SHARED_RESIDENT_RETRY_PROBE"
SPLIT_DEFINE = "LISP65_RTOV_ISLAND_SPLIT_PROBE"
FEATURES = (*PRIOR.FEATURES, SHARED_DEFINE, SPLIT_DEFINE,
            "LISP65_RUNTIME_ISLAND_FINALIZE_SLOT=9")
DRIVER = ROOT / "scripts/c2-crc-convergence-shared-driver-probe.s"
DRIVER_OBJECT = ROOT / (
    "build/c2.2/substitution/crc-convergence-shared-driver-design/"
    "shared-driver.o")
DRIVER_DISASSEMBLY = ROOT / (
    "build/c2.2/substitution/crc-convergence-shared-driver-design/"
    "shared-driver.disassembly.txt")
BASELINE_MAP = ROOT / (
    "build/c2.2/substitution/product-link-35-dma-completion-first-status/"
    "resident-island-seed.prg.map")
MAP = OUT / "resident-island-seed.prg.map"
TEXT_RESERVE = 19
FIXED_POCKET = 33
SLICE_CAP = 1792


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"probe artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def section(map_text: str, name: str) -> tuple[int, int]:
    match = re.search(
        rf"^\s*([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+"
        rf"{re.escape(name)}$", map_text, re.MULTILINE)
    require(match is not None, f"map section absent: {name}")
    return int(match.group(1), 16), int(match.group(2), 16)


def optional_section(map_text: str, name: str) -> tuple[int, int] | None:
    match = re.search(
        rf"^\s*([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+"
        rf"{re.escape(name)}$", map_text, re.MULTILINE)
    if not match:
        return None
    return int(match.group(1), 16), int(match.group(2), 16)


def symbol_size(map_text: str, name: str) -> int:
    match = re.search(
        rf"^\s*[0-9a-f]+\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+"
        rf"{re.escape(name)}$", map_text, re.MULTILINE)
    require(match is not None, f"map symbol absent: {name}")
    return int(match.group(1), 16)


def protect() -> None:
    if OUT.exists():
        PRIOR.BASE.protect(OUT)
    if RECEIPT.exists():
        os.chmod(RECEIPT, 0o444)


def configure_split() -> None:
    """Extend the canonical profile with one serial boot-only finalizer."""
    PRIOR.BASE.configure()
    require(P.BOOT_ISLAND_SLOT == 8 and P.BOOT_ISLAND_CARRIER_SLOT == 9,
            "canonical Island slot geometry drift")
    require(len(P.BOOT_SLICE_SPECS) == 9 and len(P.BOOT_DATA_SPECS) == 1,
            "canonical boot family geometry drift")
    finalizer = (
        "9:resident-island-finalizer:.lisp65_rt_island_01:"
        "__lisp65_rt_island_01_start:__lisp65_rt_island_01_end:"
        "__lisp65_rt_island_01_entry:boot:1:0:"
        "vm_resident_island_finalize")
    carrier = (
        "10:resident-island-image:.lisp65_resident_island:"
        "__lisp65_resident_island_start:__lisp65_resident_island_end:"
        "boot+data:0x1800:0")
    P.BOOT_SLICE_SPECS = [*P.BOOT_SLICE_SPECS, finalizer]
    P.BOOT_ISLAND_CARRIER_SLOT = 10
    P.BOOT_DATA_SPECS = [carrier]
    P.UNIQUE_SLICE_COUNT += 1
    P.assert_unique_public_specs()


def split_linker_script(original: str) -> str:
    phase0 = (
        "        .lisp65_rt_island_00 { KEEP(*(.lisp65_rt_island_00)) "
        "KEEP(*(.lisp65_rt_island_00_data)) }")
    phase1 = (
        "        .lisp65_rt_island_01 { KEEP(*(.lisp65_rt_island_01)) "
        "KEEP(*(.lisp65_rt_island_01_data)) }")
    require(original.count(phase0) == 1,
            "Island phase-00 linker placement template drift")
    result = original.replace(phase0, phase0 + "\n" + phase1, 1)

    symbol0 = (
        "__lisp65_rt_island_00_start = ADDR(.lisp65_rt_island_00); "
        "__lisp65_rt_island_00_end = ADDR(.lisp65_rt_island_00) + "
        "SIZEOF(.lisp65_rt_island_00);")
    symbol1 = (
        "__lisp65_rt_island_01_start = ADDR(.lisp65_rt_island_01); "
        "__lisp65_rt_island_01_end = ADDR(.lisp65_rt_island_01) + "
        "SIZEOF(.lisp65_rt_island_01);")
    require(result.count(symbol0) == 1,
            "Island phase-00 linker symbol template drift")
    result = result.replace(symbol0, symbol0 + "\n" + symbol1, 1)

    entry0 = "__lisp65_rt_island_00_entry = vm_resident_island_install;"
    entry1 = "__lisp65_rt_island_01_entry = vm_resident_island_finalize;"
    require(result.count(entry0) == 1,
            "Island phase-00 linker entry template drift")
    result = result.replace(entry0, entry0 + "\n" + entry1, 1)

    assertion0 = (
        "ASSERT(SIZEOF(.lisp65_rt_island_00) <= 1792,\n"
        "       \"resident-island installer exceeds the product Slot-37 budget\");")
    assertion1 = (
        "ASSERT(SIZEOF(.lisp65_rt_island_01) > 0 && "
        "SIZEOF(.lisp65_rt_island_01) <= 1792 &&\n"
        "       __lisp65_rt_island_01_end <= "
        "__lisp65_workbench_boot_slice_limit,\n"
        "       \"resident-island finalizer exceeds the product slice budget\");")
    require(result.count(assertion0) == 1,
            "Island phase-00 linker assertion template drift")
    return result.replace(assertion0, assertion0 + "\n" + assertion1, 1)


def prepare_seed() -> Path:
    manifest_path = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    artifacts = json.loads(manifest_path.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True)
    P.write_v2_profile_report(OUT, artifacts)
    write(OUT / "c2-substitution.ld", split_linker_script(P.linker_script()))
    contract_lines = [
        "profile=" + P.PROFILE,
        "c2_artifacts_sha256=" + sha(manifest_path),
        "linker_sha256=" + sha(OUT / "c2-substitution.ld"),
        "slice_count_unique=" + str(P.UNIQUE_SLICE_COUNT),
        "boot_family_slice_count="
        + str(len(P.BOOT_SLICE_SPECS) + len(P.BOOT_DATA_SPECS)),
        "session_family_slice_count=" + str(len(P.SESSION_SLICE_SPECS)),
        "mode=shared-resident-retry-plus-serial-island-split-wplto",
        "promotable=no", "hardware_execution=prohibited",
        "product_link=prohibited", "final_e000_floor_bytes=115",
        "legal_resident_homes_bytes=52",
        "feature_defines=" + ",".join(FEATURES),
    ]
    for source in P.source_list(FEATURES):
        path = Path(source)
        contract_lines.append(
            f"input_sha256={path.relative_to(ROOT)}:{sha(path)}")
    contract = OUT / "resolved-profile.txt"
    write(contract, "\n".join(contract_lines) + "\n")

    standard = OUT / "runtime-overlay.prepare-standard.h"
    prepared = OUT / "runtime-overlay.prepare.h"
    island_prepared = OUT / "resident-island.prepare.h"
    stage = OUT / "stage-config.h"
    errors = OUT / "error-text-table.h"
    kernal = OUT / "c2-kernal-window.generated.h"
    P.write(kernal, P.kernal_header_values(P.KERNAL_CRC_BINDING_SENTINEL,
                                           "0" * 64))
    P.tool("runtime_overlay_bank.py", "prepare", "--abi-contract",
           str(contract), "--header", str(standard), "--profile", P.PROFILE,
           "--format-version", "3")
    P.render_prepared_family_header(standard, prepared)
    P.tool("resident_island.py", "prepare", "--abi-contract", str(contract),
           "--header", str(island_prepared))
    build_id = int(hashlib.sha256(contract.read_bytes()).hexdigest()[:8], 16)
    P.tool("error_text_table.py", "prepare", "--spec",
           str(ROOT / "config/error-texts.json"), "--profile", "workbench",
           "--build-id", hex(build_id), "--header", str(errors), "--binary",
           str(OUT / "error-text-table.bin"))
    write(stage, "\n".join([
        "#ifndef LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_BOOT_OVERLAY_STAGE_BANK 0x05u",
        "#define LISP65_BOOT_OVERLAY_STAGE_OFF 0x8500u",
        f"#define LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x{build_id:08x}UL",
        "#endif", "",
    ]))
    return P.compile_link(
        OUT, "resident-island-seed.prg",
        [stage, prepared, island_prepared, errors], artifacts,
        probe_definitions=FEATURES, final_inventory=False)


def source_gate() -> dict[str, Any]:
    source = (ROOT / "src/vm_runtime_overlay.c").read_text(encoding="utf-8")
    assembly = DRIVER.read_text(encoding="utf-8")
    require(source.count("rtov_crc_converge_shared_probe(expected)") == 1,
            "shared driver is not consumed through one source wrapper")
    require(source.count("vm_resident_island_finalize(void *opaque)") == 1,
            "serial Island phase-01 entry absent or duplicated")
    require("rtov_batch_entry = file_off;" in source
            and "LISP65_RUNTIME_ISLAND_FINALIZE_SLOT, 0, &result" in source,
            "Island split does not use the existing tuple plus resident driver")
    require("jsr\trtov_crc_mem" in assembly
            and "cpx\t#COMPLETION_TIMEOUT_FRAMES" in assembly
            and "lda\t#COMPLETION_TIMEOUT_STATUS" in assembly,
            "shared driver contract opcodes drift")
    return {
        "status": "passed-one-shared-driver-serial-two-phase-island",
        "shared_driver_callsites_in_c_source":
            source.count("rtov_crc_converge(" ) - 1,
        "transition_state": "existing rtov_batch_entry/file_off",
        "new_resident_transition_bytes": 0,
        "overlay_calls_overlay": False,
        "driver_source": bind(DRIVER),
        "driver_reference_object": bind(DRIVER_OBJECT),
        "driver_reference_disassembly": bind(DRIVER_DISASSEMBLY),
    }


def measured(error: BaseException | None) -> dict[str, Any]:
    require(MAP.is_file(), "WPLTO stopped before emitting its authoritative map")
    current = MAP.read_text(encoding="utf-8")
    baseline = BASELINE_MAP.read_text(encoding="utf-8")
    text_addr, text_bytes = section(current, ".text")
    base_addr, base_bytes = section(baseline, ".text")
    require(text_addr == base_addr, "probe moved the Bank-0 text base")
    delta = text_bytes - base_bytes
    aggregate = TEXT_RESERVE + FIXED_POCKET
    phase0 = section(current, ".lisp65_rt_island_00")[1]
    phase1 = section(current, ".lisp65_rt_island_01")[1]
    shared = symbol_size(current, "rtov_crc_converge_shared_probe")
    bss_addr, bss_bytes = section(current, ".bss")
    e000_used = sum(section(current, name)[1] for name in P.KERNAL_SECTIONS)
    slice_names = {
        spec.split(":")[2]
        for spec in P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS
    }
    slice_sizes = {name: section(current, name)[1] for name in slice_names}
    walls = {
        "bank0_text_headroom_bytes": P.HANDOFF_BASE - text_addr - text_bytes,
        "ordinary_bss_headroom_bytes": P.FIXED_BANK0_BASE - bss_addr - bss_bytes,
        "fixed_hot_block_headroom_bytes": P.fixed_bank0_headroom_bytes(),
        "e000_headroom_bytes": P.KERNAL_WINDOW_BYTES - e000_used,
        "runtime_slice_min_headroom_bytes":
            SLICE_CAP - max(slice_sizes.values()),
    }
    fits = delta <= aggregate and all(value >= 0 for value in walls.values())
    require(phase0 <= SLICE_CAP and phase1 <= SLICE_CAP,
            f"serial Island split is over cap: phase0={phase0} phase1={phase1}")
    require(walls["e000_headroom_bytes"] == 115,
            "shared-driver probe changed the final E000 floor")
    return {
        "status": (
            "passed-corrected-minimal-form-fits-legal-resident-homes"
            if fits else
            "FIRST RED: corrected minimal form exceeds legal resident homes"),
        "criterion3_reached": not fits,
        "diagnostic": None if error is None else {
            "type": type(error).__name__, "message": str(error)},
        "shared_driver": {
            "wplto_symbol_bytes": shared,
            "reference_non_lto_object_bytes": 72,
            "instances": 1,
            "target": "0xc356", "length": "rtov_loaded_len",
            "variable_parameter": "expected_crc16-only",
        },
        "island_split": {
            "phase00_bytes": phase0, "phase01_bytes": phase1,
            "slice_ceiling_bytes": SLICE_CAP,
            "phase00_headroom_bytes": SLICE_CAP - phase0,
            "phase01_headroom_bytes": SLICE_CAP - phase1,
            "serial_driver": True, "overlay_calls_overlay": False,
            "transition_state_bytes": 0,
        },
        "whole_program_truth": {
            "baseline_link35_text_bytes": base_bytes,
            "corrected_probe_text_bytes": text_bytes,
            "resident_delta_vs_link35_bytes": delta,
            "legal_text_reserve_bytes": TEXT_RESERVE,
            "legal_fixed_pocket_bytes": FIXED_POCKET,
            "aggregate_legal_homes_bytes": aggregate,
            "headroom_after_both_legal_homes_bytes": aggregate - delta,
            "walls": walls,
            "map": bind(MAP),
        },
    }


def main() -> int:
    require(not OUT.exists() and not RECEIPT.exists(),
            "corrected shared-driver WPLTO attempt already consumed")
    require(BASELINE_MAP.is_file() and DRIVER_OBJECT.is_file()
            and DRIVER_DISASSEMBLY.is_file(),
            "bound baseline/shared-driver design evidence absent")

    original_source_list = P.source_list
    original_linker_script = P.linker_script

    def source_list(extra_definitions: tuple[str, ...] = ()) -> list[str]:
        result = original_source_list(extra_definitions)
        if SHARED_DEFINE in extra_definitions:
            result.append(str(DRIVER))
        return result

    error: BaseException | None = None
    seed: Path | None = None
    try:
        configure_split()
        P.source_list = source_list
        seed = prepare_seed()
    except BaseException as caught:
        error = caught
    finally:
        P.source_list = original_source_list
        P.linker_script = original_linker_script

    result = measured(error)
    value = {
        "format": (
            "lisp65-c2-crc-convergence-shared-driver-island-split-wplto-v1"),
        "recorded_on": "2026-07-21",
        "status": result["status"],
        "promotable": False,
        "claim_limit": (
            "Exactly one product-shaped WPLTO seed capacity/placement run. "
            "No product candidate, product link or hardware execution."),
        "source_gate": source_gate(),
        "measurement": result,
        "seed_elf_emitted": seed is not None,
        "walls_not_relaxed": [
            "runtime-slice-1792", "final-e000-floor-115",
            "handoff-anchor-b4a3", "bank0-fixed-block-c080",
        ],
        "execution_accounting": {
            "whole_program_lto_seed_runs": 1,
            "product_links": 0,
            "promotable_product_candidates": 0,
            "hardware_runs": 0,
        },
        "next_gate": (
            "If the corrected minimal form fits, Class-C review may authorize "
            "Link 36. If it does not, the commissioned principle decision is "
            "C2-lite versus an explicit floor break."),
    }
    write(RECEIPT, json.dumps(value, indent=2, sort_keys=True) + "\n")
    protect()
    print(value["status"])
    print(json.dumps(result["whole_program_truth"], indent=2))
    return 0 if not result["criterion3_reached"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
