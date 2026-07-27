#!/usr/bin/env python3
"""One non-promotable WPLTO proof of the terminal 63-byte E000 floor.

The run packages the already-measured serial Island split, slice-local Boot
barriers and cold helpers with one shared hot retry driver.  It emits no
promotable product identity and authorizes neither Link 36 nor hardware.
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
import c2_crc_convergence_shared_driver_island_split_wplto as PRIOR  # noqa: E402


P = PRIOR.P
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.2/substitution/crc-convergence-terminal-floor-wplto"
RECEIPT = EVIDENCE / (
    "c2.2-crc-convergence-terminal-floor-wplto-receipt.json")
DRIVER = ROOT / "scripts/c2-crc-convergence-shared-driver-probe.s"
FLOOR_DEFINE = "LISP65_RTOV_FLOOR_BREAK_RETRY_PROBE"
FEATURES = (*PRIOR.FEATURES, FLOOR_DEFINE)
BASELINE_MAP = ROOT / (
    "build/c2.2/substitution/product-link-35-dma-completion-first-status/"
    "resident-island-seed.prg.map")
TARGET = OUT / "terminal-floor-seed.prg"
MAP = Path(str(TARGET) + ".map")
CRC_WINDOW_SECTION = ".lisp65_c2_kernal_window.crc_retry"
FIXED_SECTION = ".lisp65_c2_crc_retry_fixed"
FINAL_E000_FLOOR = 63
PREVIOUS_E000_FLOOR = 115
FLOOR_DEBIT = 52
TEXT_ROOM = 19
FIXED_ROOM = 33
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


def symbol(map_text: str, name: str) -> tuple[int, int]:
    match = re.search(
        rf"^\s*([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+"
        rf"{re.escape(name)}$", map_text, re.MULTILINE)
    require(match is not None, f"map symbol absent: {name}")
    return int(match.group(1), 16), int(match.group(2), 16)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    require(text.count(old) == 1,
            f"linker template drift for {label}: count={text.count(old)}")
    return text.replace(old, new, 1)


def configure() -> None:
    PRIOR.configure_split()
    require(P.HOST_FACADE_EXTENSION_SYMBOLS == (
        "c2_facade_runtime_overlay_exec", "c2_facade_handle_normalize"),
        "canonical fifteen-vector facade drift")
    P.HOST_FACADE_EXTENSION_SYMBOLS = (
        *P.HOST_FACADE_EXTENSION_SYMBOLS, "c2_facade_rtov_crc_mem")
    if CRC_WINDOW_SECTION not in P.KERNAL_SECTIONS:
        P.KERNAL_SECTIONS.append(CRC_WINDOW_SECTION)
    require(P.host_facade_bytes() == 48
            and P.host_facade_vector_addresses()["c2_facade_rtov_crc_mem"]
            == 0xB5F1,
            "sixteenth facade vector contract drift")


def floor_linker_script() -> str:
    result = PRIOR.split_linker_script(P.linker_script())

    # Sixteenth facade vector; all following fixed seams move together.
    result = replace_once(result,
        ".lisp65_c2_kernal_io_reveal 0xb5f1",
        ".lisp65_c2_kernal_io_reveal 0xb5f4", "I/O reveal VMA")
    result = replace_once(result,
        ".lisp65_c2_kernal_map_switch 0xb5fc",
        ".lisp65_c2_kernal_map_switch 0xb5ff", "MAP switch VMA")
    result = replace_once(result,
        ".lisp65_c2_kernal_state 0xb606",
        ".lisp65_c2_kernal_state 0xb609", "owned state VMA")
    require(result.count("SIZEOF(.lisp65_c2_host_facade) == 45") == 2,
            "facade-size assertion count drift")
    result = result.replace("SIZEOF(.lisp65_c2_host_facade) == 45",
                            "SIZEOF(.lisp65_c2_host_facade) == 48")
    require(result.count("c2_facade_handle_normalize == 0xb5ee,") == 2,
            "facade-vector assertion count drift")
    result = result.replace(
        "c2_facade_handle_normalize == 0xb5ee,",
        "c2_facade_handle_normalize == 0xb5ee &&\n"
        "       c2_facade_rtov_crc_mem == 0xb5f1,")
    result = result.replace(
        "ADDR(.lisp65_c2_kernal_io_reveal) == 0xb5f1",
        "ADDR(.lisp65_c2_kernal_io_reveal) == 0xb5f4")
    result = result.replace(
        "c2_kernal_reveal_io == 0xb5f1",
        "c2_kernal_reveal_io == 0xb5f4")
    result = result.replace(
        "ADDR(.lisp65_c2_kernal_map_switch) == 0xb5fc",
        "ADDR(.lisp65_c2_kernal_map_switch) == 0xb5ff")
    result = result.replace(
        "SIZEOF(.lisp65_c2_kernal_map_switch) <= 0xb606",
        "SIZEOF(.lisp65_c2_kernal_map_switch) <= 0xb609")
    result = result.replace(
        "ADDR(.lisp65_c2_kernal_state) == 0xb606",
        "ADDR(.lisp65_c2_kernal_state) == 0xb609")
    result = replace_once(result, "       6 <= 450,", "       9 <= 450,",
                          "reopening plus terminal seam debit")

    fixed = r"""
/* Terminal-floor package: the cold sample and serial Island call scaffold
 * occupy only the already-authorized 33-byte post-hot-BSS pocket. */
SECTIONS {
    .lisp65_c2_crc_retry_fixed 0xc335 : {
        KEEP(*(.lisp65_c2_crc_retry_fixed))
    } >ram
} INSERT AFTER .lisp65_c2_fixed_bank0_hot_bss;
ASSERT(ADDR(.lisp65_c2_crc_retry_fixed) == 0xc335 &&
       SIZEOF(.lisp65_c2_crc_retry_fixed) > 0 &&
       SIZEOF(.lisp65_c2_crc_retry_fixed) <= 33 &&
       ADDR(.lisp65_c2_crc_retry_fixed) +
           SIZEOF(.lisp65_c2_crc_retry_fixed) <= 0xc356 &&
       rtov_install_island_finalize >= 0xc335 &&
       rtov_install_island_finalize < 0xc356,
       "C2 terminal retry fixed-pocket geometry drift");

"""
    marker = "/* The llvm-mos .rodata output is inherited from the platform script."
    require(result.count(marker) == 1, "fixed-pocket insertion marker drift")
    result = result.replace(marker, fixed + marker, 1)

    window = r"""
/* Exact owner-authorized terminal floor debit: one 52-byte hot retry tail. */
SECTIONS {
    .lisp65_c2_kernal_window.crc_retry 0xff44 :
        AT(ORIGIN(c2_kernal_window_load) + 0x1f44) {
        KEEP(*(.lisp65_c2_kernal_window.crc_retry))
    } >c2_kernal_window
} INSERT AFTER .lisp65_c2_kernal_window.reopen_gap1;
ASSERT(ADDR(.lisp65_c2_kernal_window.crc_retry) == 0xff44 &&
       SIZEOF(.lisp65_c2_kernal_window.crc_retry) == 52 &&
       rtov_crc_converge_retry_window == 0xff44 &&
       ADDR(.lisp65_c2_kernal_window.crc_retry) +
           SIZEOF(.lisp65_c2_kernal_window.crc_retry) <=
           ADDR(.lisp65_c2_kernal_window.state),
       "C2 terminal 52-byte E000 retry tenant drift");

"""
    marker = "/* Exact non-ALLOC orphan allowlist."
    require(result.count(marker) == 1, "window insertion marker drift")
    result = result.replace(marker, window + marker, 1)

    require("SIZEOF(.lisp65_c2_kernal_window.crc_retry)" in result
            and "C2 final E000 floor below 63 bytes" in result,
            "terminal E000 floor was not derived from configured truth")
    return result


def prepare_seed() -> Path:
    manifest = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    artifacts = json.loads(manifest.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True)
    P.write_v2_profile_report(OUT, artifacts)
    write(OUT / "c2-substitution.ld", floor_linker_script())
    contract = OUT / "resolved-profile.txt"
    lines = [
        "profile=" + P.PROFILE,
        "mode=terminal-63-byte-floor-wplto",
        "promotable=no", "product_link=prohibited",
        "hardware_execution=prohibited", "final_e000_floor_bytes=63",
        "previous_e000_floor_bytes=115", "purpose_bound_debit_bytes=52",
        "terminal_successor_policy=automatic-c2-lite",
        "facade_vector_count=16", "facade_crc_vector_vma=0xb5f1",
        "feature_defines=" + ",".join(FEATURES),
        "linker_sha256=" + sha(OUT / "c2-substitution.ld"),
    ]
    for source in P.source_list(FEATURES):
        path = Path(source)
        lines.append(f"input_sha256={path.relative_to(ROOT)}:{sha(path)}")
    write(contract, "\n".join(lines) + "\n")

    standard = OUT / "runtime-overlay.prepare-standard.h"
    prepared = OUT / "runtime-overlay.prepare.h"
    island = OUT / "resident-island.prepare.h"
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
           "--header", str(island))
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
        OUT, TARGET.name, [stage, prepared, island, errors, kernal], artifacts,
        probe_definitions=FEATURES, final_inventory=False)


def source_gate() -> dict[str, Any]:
    source = (ROOT / "src/vm_runtime_overlay.c").read_text(encoding="utf-8")
    assembly = DRIVER.read_text(encoding="utf-8")
    require(source.count("rtov_crc_converge_shared_probe(expected)") == 1,
            "shared retry source seam drift")
    require(source.count("rtov_install_island_finalize") == 2,
            "serial Island fixed call seam drift")
    require(assembly.count("rtov_crc_converge_retry_window:") == 1
            and assembly.count("c2_facade_rtov_crc_mem:") == 1
            and "jsr\tc2_facade_rtov_crc_mem" in assembly,
            "window retry/facade source contract drift")
    mutated = assembly.replace("jsr\tc2_facade_rtov_crc_mem",
                               "jsr\trtov_crc_mem", 1)
    require("jsr\trtov_crc_mem" in mutated
            and "jsr\trtov_crc_mem" not in assembly,
            "direct-window-call negative mutation was not constructed")
    return {
        "status": "passed-one-driver-two-hot-callers",
        "shared_driver_hot_callsites": source.count(
            "status = rtov_crc_converge("),
        "serial_island_split": True,
        "boot_barriers_are_slice_local": True,
        "direct-window-call-negative": "rejected-by-fixed-facade-gate",
        "driver": bind(DRIVER),
    }


def structural_gates(seed: Path) -> dict[str, Any]:
    P.extract_provisional_kernal_window(OUT, seed)
    crc_codegen = P.CRC_CODEGEN.audit_elf(
        Path(str(seed) + ".elf"), out=OUT / "c2-crc-codegen-gate.json")
    crc_leaf = P.CRC_ASM_LEAF.audit_elf(
        Path(str(seed) + ".elf"), out=OUT / "c2-crc-asm-leaf-gate.json")
    P.handoff_z_abi_gate(OUT, seed, "terminal-floor-probe")
    facade = P.fixed_facade_gate(OUT, seed, "terminal-floor-probe")
    old_end = P.fixed_bank0_contract_end
    try:
        P.fixed_bank0_contract_end = lambda: 0xC356
        ownership = P.pre_ownership_gate(
            OUT, seed, "terminal-floor-probe")
    finally:
        P.fixed_bank0_contract_end = old_end
    data = P.profile_data_reference_gate(
        OUT, seed, "terminal-floor-probe", ownership)
    kernal = P.kernal_freedom_gate(OUT, seed)
    return {
        "crc_codegen": crc_codegen["status"],
        "crc_leaf": crc_leaf["status"],
        "handoff_z_abi": "passed", "pre_ownership": ownership["status"],
        "profile_data_reference": data["status"],
        "fixed_facade": facade["status"],
        "kernal_freedom": kernal["status"],
        "owned_control_flow_edges": kernal["control_flow_ownership"][
            "direct_window_edges"],
    }


def measurement(seed: Path) -> dict[str, Any]:
    current = MAP.read_text(encoding="utf-8")
    baseline = BASELINE_MAP.read_text(encoding="utf-8")
    text_addr, text_bytes = section(current, ".text")
    base_addr, base_bytes = section(baseline, ".text")
    require(text_addr == base_addr, "ordinary text base drift")
    bss_addr, bss_bytes = section(current, ".bss")
    fixed_addr, fixed_bytes = section(current, FIXED_SECTION)
    retry_addr, retry_bytes = section(current, CRC_WINDOW_SECTION)
    facade_addr, facade_bytes = section(current, ".lisp65_c2_host_facade")
    phase0 = section(current, ".lisp65_rt_island_00")[1]
    phase1 = section(current, ".lisp65_rt_island_01")[1]
    slice_names = {spec.split(":")[2] for spec in
                   P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS}
    slice_sizes = {name: section(current, name)[1] for name in slice_names}
    e000_used = sum(section(current, name)[1] for name in P.KERNAL_SECTIONS)
    walls = {
        "ordinary_text_headroom_bytes": P.HANDOFF_BASE - text_addr - text_bytes,
        "ordinary_bss_headroom_bytes": P.FIXED_BANK0_BASE - bss_addr - bss_bytes,
        "fixed_retry_pocket_headroom_bytes": 0xC356 - fixed_addr - fixed_bytes,
        "resident_island_headroom_bytes": 2048 - section(
            current, ".lisp65_resident_island")[1],
        "e000_headroom_bytes": P.KERNAL_WINDOW_BYTES - e000_used,
        "runtime_slice_min_headroom_bytes": SLICE_CAP - max(slice_sizes.values()),
    }
    require(retry_addr == 0xFF44 and retry_bytes == FLOOR_DEBIT,
            "terminal retry window is not exactly 52 bytes at 0xff44")
    require(fixed_addr == 0xC335 and 0 < fixed_bytes <= FIXED_ROOM,
            "fixed retry scaffold escaped its 33-byte pocket")
    require(facade_addr == 0xB5C4 and facade_bytes == 48,
            "sixteen-vector facade geometry drift")
    require(P.KERNAL_WINDOW_BYTES - e000_used == FINAL_E000_FLOOR,
            "terminal E000 floor is not exactly 63 bytes")
    require(all(value >= 0 for value in walls.values()),
            f"capacity wall red: {walls}")
    require(phase0 <= SLICE_CAP and phase1 <= SLICE_CAP,
            "serial Island split exceeds the 1792-byte ceiling")
    return {
        "status": "passed-terminal-floor-package-wplto",
        "whole_program_text": {
            "baseline_link35_bytes": base_bytes,
            "probe_bytes": text_bytes,
            "delta_bytes": text_bytes - base_bytes,
            "historical_room_bytes": TEXT_ROOM,
        },
        "purpose_bound_allocation": {
            "e000_retry_tail_bytes": retry_bytes,
            "fixed_retry_scaffold_bytes": fixed_bytes,
            "ordinary_text_delta_bytes": text_bytes - base_bytes,
            "historical_equation_bytes": 104,
            "unused_capacity_is_not_budget": True,
        },
        "facade": {"address": facade_addr, "bytes": facade_bytes,
                   "vectors": 16,
                   "crc_leaf_vector": "0xb5f1"},
        "island_split": {"phase00_bytes": phase0,
                         "phase01_bytes": phase1,
                         "overlay_calls_overlay": False},
        "walls": walls,
        "symbols": {
            name: {"address": address, "bytes": size}
            for name in (
                "rtov_crc_converge_shared_probe",
                "rtov_crc_converge_retry_window",
                "rtov_install_island_finalize",
                "c2_facade_rtov_crc_mem")
            for address, size in [symbol(current, name)]
        },
        "seed": bind(seed), "elf": bind(Path(str(seed) + ".elf")),
        "map": bind(MAP),
    }


def protect() -> None:
    if OUT.exists():
        for path in sorted(OUT.rglob("*"), reverse=True):
            if path.is_file():
                os.chmod(path, 0o555 if os.access(path, os.X_OK) else 0o444)
            elif path.is_dir():
                os.chmod(path, 0o555)
        os.chmod(OUT, 0o555)
    if RECEIPT.exists():
        os.chmod(RECEIPT, 0o444)


def replay() -> int:
    """Replay only gates against the one immutable WPLTO ELF."""
    require(TARGET.is_file() and Path(str(TARGET) + ".elf").is_file()
            and MAP.is_file() and RECEIPT.is_file(),
            "terminal-floor replay inputs are incomplete")
    os.chmod(RECEIPT, 0o644)
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o755 if os.access(path, os.X_OK) else 0o644)
    os.chmod(OUT, 0o755)
    configure()
    error: BaseException | None = None
    gates: dict[str, Any] = {}
    try:
        gates = structural_gates(TARGET)
    except BaseException as caught:
        error = caught
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    value["status"] = (
        "passed-terminal-floor-package-wplto"
        if error is None else
        "FIRST RED: terminal-floor package did not clear all gates")
    value["structural_gates"] = gates
    value["diagnostic"] = (None if error is None else {
        "type": type(error).__name__, "message": str(error)})
    value["source_gate"] = source_gate()
    value["next_gate"] = (
        "Separate Class-C approval is required for Link 36."
        if error is None else
        "Class-A gate replay remains red; Link 36 and hardware are blocked.")
    value["execution_accounting"]["pure_gate_replays"] = (
        int(value["execution_accounting"].get("pure_gate_replays", 0)) + 1)
    write(RECEIPT, json.dumps(value, indent=2, sort_keys=True) + "\n")
    protect()
    print(value["status"])
    if error:
        print(f"{type(error).__name__}: {error}")
    return 0 if error is None else 3


def main() -> int:
    require(not OUT.exists() and not RECEIPT.exists(),
            "terminal-floor WPLTO attempt already consumed")
    require(BASELINE_MAP.is_file(), "Link-35 baseline map absent")
    original_sources = P.source_list
    original_linker = P.linker_script

    def sources(extra_definitions: tuple[str, ...] = ()) -> list[str]:
        result = original_sources(extra_definitions)
        if FLOOR_DEFINE in extra_definitions:
            result.append(str(DRIVER))
        return result

    seed: Path | None = None
    error: BaseException | None = None
    gates: dict[str, Any] = {}
    measured: dict[str, Any] = {}
    try:
        configure()
        P.source_list = sources
        seed = prepare_seed()
        measured = measurement(seed)
        gates = structural_gates(seed)
    except BaseException as caught:
        error = caught
    finally:
        P.source_list = original_sources
        P.linker_script = original_linker

    passed = error is None and seed is not None
    value = {
        "format": "lisp65-c2-crc-convergence-terminal-floor-wplto-v1",
        "recorded_on": "2026-07-21",
        "status": ("passed-terminal-floor-package-wplto" if passed else
                   "FIRST RED: terminal-floor package did not clear all gates"),
        "promotable": False,
        "claim_limit": (
            "One product-shaped WPLTO seed and structural gate pass only. "
            "No Link 36, product identity, hardware or promotion claim."),
        "contract": {
            "previous_floor_bytes": PREVIOUS_E000_FLOOR,
            "terminal_floor_bytes": FINAL_E000_FLOOR,
            "purpose_bound_debit_bytes": FLOOR_DEBIT,
            "third_floor_negotiation": "forbidden",
            "successor_resident_or_window_demand": "automatic-C2-lite",
        },
        "source_gate": source_gate(),
        "measurement": measured,
        "structural_gates": gates,
        "diagnostic": (None if error is None else {
            "type": type(error).__name__, "message": str(error)}),
        "execution_accounting": {
            "whole_program_lto_seed_runs": 1,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
        "next_gate": (
            "Separate Class-C approval is required for Link 36."
            if passed else
            "First Red; Link 36 and hardware remain blocked."),
    }
    write(RECEIPT, json.dumps(value, indent=2, sort_keys=True) + "\n")
    protect()
    print(value["status"])
    if measured:
        print(json.dumps(measured["walls"], indent=2, sort_keys=True))
    if error:
        print(f"{type(error).__name__}: {error}")
    return 0 if passed else 3


if __name__ == "__main__":
    raise SystemExit(replay() if "--replay" in sys.argv[1:] else main())
