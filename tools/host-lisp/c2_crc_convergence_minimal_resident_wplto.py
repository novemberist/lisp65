#!/usr/bin/env python3
"""One non-promotable WPLTO truth run for the minimal resident retry split."""

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


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.2/substitution/crc-convergence-minimal-resident-wplto"
RECEIPT = EVIDENCE / (
    "c2.2-crc-convergence-minimal-resident-wplto-first-red-receipt.json")
PROBE_DEFINE = "LISP65_RTOV_MINIMAL_RESIDENT_RETRY_PROBE"
PROBE_ASM = ROOT / "scripts/c2-crc-convergence-minimal-resident-probe.s"
BASELINE_MAP = ROOT / (
    "build/c2.2/substitution/product-link-35-dma-completion-first-status/"
    "resident-island-seed.prg.map")
TEMPERATURE_MAP = ROOT / (
    "build/c2.2/substitution/l65r-v3-crc-convergence-temperature-wplto/"
    "resident-island-seed.prg.map")
MAP = OUT / "resident-island-seed.prg.map"
TEXT_RESERVE = 19
FIXED_POCKET = 33


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing evidence: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def section(map_text: str, name: str) -> tuple[int, int]:
    match = re.search(
        rf"^\s*([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+{re.escape(name)}$",
        map_text, re.MULTILINE)
    require(match is not None, f"map section absent: {name}")
    return int(match.group(1), 16), int(match.group(2), 16)


def symbol_size(map_text: str, name: str) -> int:
    match = re.search(
        rf"^\s*[0-9a-f]+\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+{re.escape(name)}$",
        map_text, re.MULTILINE)
    require(match is not None, f"map symbol absent: {name}")
    return int(match.group(1), 16)


def protect() -> None:
    if OUT.exists():
        PRIOR.BASE.protect(OUT)
    if RECEIPT.exists():
        os.chmod(RECEIPT, 0o444)


def main() -> int:
    require(not OUT.exists() and not RECEIPT.exists(),
            "minimal-resident WPLTO probe already consumed")
    require(BASELINE_MAP.is_file() and TEMPERATURE_MAP.is_file(),
            "bound Link-35/temperature WPLTO maps are absent")

    original_source_list = PRIOR.BASE.P.source_list

    def source_list(extra_definitions: tuple[str, ...] = ()) -> list[str]:
        result = original_source_list(extra_definitions)
        if PROBE_DEFINE in extra_definitions:
            result.append(str(PROBE_ASM))
        return result

    PRIOR.OUT = OUT
    PRIOR.RECEIPT = OUT / "must-not-pass.json"
    PRIOR.FIRST_RED = OUT / "delegated-first-red.json"
    PRIOR.FEATURES = (*PRIOR.FEATURES, PROBE_DEFINE)
    PRIOR.BASE.P.source_list = source_list

    error: BaseException | None = None
    try:
        PRIOR.full_probe()
    except BaseException as caught:  # the bound walls are expected to stop it
        error = caught
    finally:
        PRIOR.BASE.P.source_list = original_source_list

    require(error is not None,
            "minimal-resident probe unexpectedly passed all product walls")
    require(MAP.is_file(), "WPLTO stopped before emitting its authoritative map")

    current = MAP.read_text(encoding="utf-8")
    baseline = BASELINE_MAP.read_text(encoding="utf-8")
    temperature = TEMPERATURE_MAP.read_text(encoding="utf-8")
    text_base, text_base_bytes = section(baseline, ".text")
    text_probe, text_probe_bytes = section(current, ".text")
    _, text_temperature_bytes = section(temperature, ".text")
    _, island_bytes = section(current, ".lisp65_rt_island_00")
    _, catalog_bytes = section(current, ".lisp65_rt_rtov_catalog")
    _, record_bytes = section(current, ".lisp65_rt_rtov_record")
    start_bytes = symbol_size(current, "rtov_crc_retry_start_probe")
    retry_bytes = symbol_size(current, "rtov_crc_retry_after_miss_probe")
    cold_crc_bytes = symbol_size(current, "rtov_crc_byte")
    require(start_bytes == 12 and retry_bytes == 65,
            "minimal non-LTO retry floor drift")
    require(text_base == text_probe,
            "probe changed the Bank-0 text base rather than measuring growth")

    delta = text_probe_bytes - text_base_bytes
    aggregate_budget = TEXT_RESERVE + FIXED_POCKET
    shortage = delta - aggregate_budget
    require(delta > aggregate_budget,
            "minimal resident delta unexpectedly fits the two legal homes")

    disassembly = OUT / "minimal-resident.disassembly.txt"
    object_path = OUT / "minimal-resident.o"
    # Preserve the separately assembled exact lower-bound object beside the
    # WPLTO map; the product-shaped link compiled the same source again.
    object_path.write_bytes((ROOT / (
        "build/c2.2/substitution/crc-convergence-minimal-resident-design/"
        "minimal-resident.o")).read_bytes())
    disassembly.write_bytes((ROOT / (
        "build/c2.2/substitution/crc-convergence-minimal-resident-design/"
        "minimal-resident.disassembly.txt")).read_bytes())

    value = {
        "format": "lisp65-c2-crc-convergence-minimal-resident-wplto-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: minimal resident CRC retry exceeds the final legal homes",
        "promotable": False,
        "claim_limit": (
            "One product-shaped Whole-Program-LTO capacity/placement run; "
            "no product candidate and no hardware execution."),
        "diagnostic": {"type": type(error).__name__, "message": str(error)},
        "temperature_decomposition": {
            "boot_consumers": {
                "catalog_slice_bytes": catalog_bytes,
                "record_slice_bytes": record_bytes,
                "island_slice_bytes": island_bytes,
                "island_slice_ceiling_bytes": 1792,
                "cold_crc_helper_moved_from_resident_bytes": cold_crc_bytes,
            },
            "runtime_success_path": (
                "one pre-CRC 16-bit frame sample mandated by the approved "
                "contract, then the existing rtov_crc_mem and comparison"),
            "runtime_miss_path": (
                "one consumer only; fixed target C356, existing loaded length, "
                "u16 modulo-frame retry, CRC-before-timeout, specific status"),
        },
        "exact_non_lto_floor": {
            "start_sample_bytes": start_bytes,
            "retry_after_miss_bytes": retry_bytes,
            "combined_bytes": start_bytes + retry_bytes,
            "call_site_glue_excluded": True,
            "boot_context_excluded": True,
            "wplto_can_shrink_these_sections": False,
            "object": bind(object_path),
            "disassembly": bind(disassembly),
            "source": bind(PROBE_ASM),
        },
        "whole_program_truth": {
            "baseline_link35_text_bytes": text_base_bytes,
            "prior_temperature_text_bytes": text_temperature_bytes,
            "minimal_probe_text_bytes": text_probe_bytes,
            "delta_vs_link35_bytes": delta,
            "legal_text_reserve_bytes": TEXT_RESERVE,
            "legal_fixed_pocket_bytes": FIXED_POCKET,
            "aggregate_legal_homes_bytes": aggregate_budget,
            "shortage_after_both_legal_homes_bytes": shortage,
            "map": bind(MAP),
        },
        "contract_guard": {
            "frame_width_bits": 16,
            "timeout_frames": 64,
            "crc_checked_before_timeout": True,
            "specific_timeout_status": 22,
            "late_start_after_first_miss": "rejected-contract-drift",
            "eight_bit_frame_shortcut": "rejected-contract-drift",
        },
        "walls_not_relaxed": [
            "runtime-slice-1792", "final-e000-floor-115",
            "handoff-anchor-b4a3", "bank0-fixed-block-c080",
        ],
        "first_red_conclusion": (
            "The focused minimal form still exceeds the combined 19-byte "
            "text reserve and 33-byte fixed pocket. Per the commissioned "
            "threshold, no further placement or slice attempt is eligible; "
            "Reissleinen criterion 3 is reached."),
        "execution_accounting": {
            "whole_program_lto_seed_runs": 1,
            "product_links": 0,
            "promotable_product_candidates": 0,
            "hardware_runs": 0,
        },
        "next_gate": (
            "Class-C principle decision: C2-lite or explicit floor break; "
            "no automatic continuation."),
    }
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    protect()
    print(value["status"])
    print(json.dumps(value["whole_program_truth"], indent=2))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
