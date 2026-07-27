#!/usr/bin/env python3
"""Bind the first-red result of the direct hot-refill capacity probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "build/c2.2/substitution/product-link-29-direct-entry-encoding"
ATTEMPT = ROOT / "build/c2.2/substitution/hot-refill-capacity-probe"
CONTRACT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-hot-refill-single-source-contract-probe-receipt.json")
OUTPUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-hot-refill-capacity-placement-first-red-receipt.json")


class FirstRedError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FirstRedError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def map_rows(path: Path) -> tuple[dict[str, dict[str, int]],
                                  dict[str, dict[str, int]]]:
    sections: dict[str, dict[str, int]] = {}
    symbols: dict[str, dict[str, int]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(
            r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+"
            r"([^\s].*)$", line)
        if not match:
            continue
        address, load, size = (int(match.group(i), 16) for i in range(1, 4))
        name = match.group(4).strip()
        row = {"address": address, "load_address": load, "bytes": size,
               "end_exclusive": address + size}
        if name.startswith(".") and ":(" not in name and " " not in name:
            sections.setdefault(name, row)
        elif re.fullmatch(r"[A-Za-z_.$][A-Za-z0-9_.$]*", name):
            symbols.setdefault(name, row)
    return sections, symbols


def section_delta(name: str, before: dict[str, dict[str, int]],
                  after: dict[str, dict[str, int]]) -> dict[str, Any]:
    old, new = before[name], after[name]
    return {"section": name, "link29": old, "probe": new,
            "delta_bytes": new["bytes"] - old["bytes"],
            "delta_address": new["address"] - old["address"]}


def build() -> dict[str, Any]:
    baseline_map = BASE / "resident-island-seed.prg.map"
    attempt_map = ATTEMPT / "hot-refill-capacity-seed.prg.map"
    lto = ATTEMPT / "hot-refill-capacity-seed.prg.lto.o"
    stderr = ATTEMPT / "hot-refill-capacity-seed.prg.link.stderr.txt"
    require(all(path.is_file() for path in (baseline_map, attempt_map, lto,
                                             stderr, CONTRACT)),
            "first-red evidence is incomplete")
    before, before_symbols = map_rows(baseline_map)
    after, after_symbols = map_rows(attempt_map)
    required_sections = (
        ".text", ".bss", ".lisp65_resident_island",
        ".lisp65_resident_island_annex", ".lisp65_rt_c2d_13",
        ".lisp65_c2_kernal_window.c2_resident",
        ".lisp65_c2_kernal_window.profile_rodata",
        ".lisp65_c2_kernal_window.session_emitter_state")
    require(all(name in before and name in after for name in required_sections),
            "required map section absent")
    errors = stderr.read_text(encoding="utf-8", errors="replace")
    for phrase in ("ordinary Bank-0 state overlaps fixed C2 state",
                   "section .text virtual address range overlaps",
                   "c2_resident virtual address range overlaps",
                   "session_emitter_state' will not fit"):
        require(phrase in errors, f"expected linker first red absent: {phrase}")

    text_before, text_after = before[".text"], after[".text"]
    bss_before, bss_after = before[".bss"], after[".bss"]
    island_before = before[".lisp65_resident_island"]
    island_after = after[".lisp65_resident_island"]
    annex = after[".lisp65_resident_island_annex"]
    resident_before = before[".lisp65_c2_kernal_window.c2_resident"]
    resident_after = after[".lisp65_c2_kernal_window.c2_resident"]
    profile = after[".lisp65_c2_kernal_window.profile_rodata"]
    phase_before, phase_after = (before[".lisp65_rt_c2d_13"],
                                 after[".lisp65_rt_c2d_13"])
    require(text_after["bytes"] - text_before["bytes"] == 320,
            "Bank-0 text delta drift")
    require(bss_after["bytes"] == bss_before["bytes"] == 1827,
            "BSS-size attribution drift")
    require(island_after["bytes"] - island_before["bytes"] == 846,
            "island materializer attribution drift")
    require(resident_after["bytes"] - resident_before["bytes"] == 878,
            "owned-window resolver attribution drift")
    require(phase_after["bytes"] - phase_before["bytes"] == -425,
            "phase-13 credit attribution drift")
    direct_before = before_symbols["c2_product_entry_read"]["bytes"]
    direct_after = after_symbols["c2_product_entry_read"]["bytes"]
    require(direct_after - direct_before == 328,
            "direct-entry function attribution drift")

    return {
        "format": "lisp65-c2-hot-refill-capacity-placement-first-red-v1",
        "recorded_on": "2026-07-20",
        "status": "first-red-before-structural-gates-no-product-link",
        "scope": {"semantic_contract_probe": "passed",
                  "resident_island_seed_link_attempts": 1,
                  "resident_island_seed_links_completed": 0,
                  "product_closure_links": 0,
                  "hardware_execution": "none", "promotion": "blocked"},
        "identity": {"semantic_contract_receipt": bind(CONTRACT),
                     "baseline_map": bind(baseline_map),
                     "failed_probe_map": bind(attempt_map),
                     "failed_probe_lto_object": bind(lto),
                     "linker_diagnostics": bind(stderr),
                     "resolved_probe_profile": bind(ATTEMPT / "resolved-profile.txt")},
        "first_red": {
            "bank0_text": {"link29_headroom_bytes": 0xB481 - text_before["end_exclusive"],
                           "probe_headroom_bytes": 0xB481 - text_after["end_exclusive"],
                           "section_growth_bytes": text_after["bytes"] - text_before["bytes"],
                           "direct_entry_read_growth_bytes": direct_after - direct_before},
            "bank0_bss": {"link29_bytes": bss_before["bytes"],
                          "probe_bytes": bss_after["bytes"],
                          "size_delta_bytes": 0,
                          "start_shift_bytes": bss_after["address"] - bss_before["address"],
                          "link29_headroom_bytes": 0xC080 - bss_before["end_exclusive"],
                          "probe_headroom_bytes": 0xC080 - bss_after["end_exclusive"],
                          "interpretation": "BSS did not grow; prior Bank-0 layout growth shifted it into the fixed-state boundary."},
            "owned_e000_c2_resident": {
                "link29_bytes": resident_before["bytes"],
                "probe_bytes": resident_after["bytes"],
                "growth_bytes": resident_after["bytes"] - resident_before["bytes"],
                "link29_gap_to_fixed_profile_rodata_bytes": (
                    profile["address"] - resident_before["end_exclusive"]),
                "probe_overlap_with_fixed_profile_rodata_bytes": (
                    resident_after["end_exclusive"] - profile["address"]),
                "resolver_attribution": {
                    "link29_child_value_bytes": before_symbols[
                        "c2_stream_product_child_value"]["bytes"],
                    "probe_child_status_bytes": after_symbols[
                        "c2_stream_product_child_status"]["bytes"],
                    "probe_child_value_wrapper_bytes": after_symbols[
                        "c2_stream_product_child_value"]["bytes"]}},
            "resident_island": {"link29_base_bytes": island_before["bytes"],
                                "probe_base_bytes": island_after["bytes"],
                                "materializer_growth_bytes": island_after["bytes"]
                                    - island_before["bytes"],
                                "annex_bytes": annex["bytes"],
                                "probe_headroom_bytes": 2048
                                    - island_after["bytes"] - annex["bytes"]},
            "phase13": {"link29_bytes": phase_before["bytes"],
                        "probe_bytes": phase_after["bytes"],
                        "credit_bytes": phase_before["bytes"] - phase_after["bytes"],
                        "probe_headroom_bytes": 1792 - phase_after["bytes"]}},
        "section_attribution": [section_delta(name, before, after) for name in (
            ".text", ".bss", ".lisp65_resident_island",
            ".lisp65_rt_c2d_13", ".lisp65_c2_kernal_window.c2_resident")],
        "gates": {"semantic_588_entries_1931_values": "passed-before-link",
                  "capacity_and_placement": "failed-first",
                  "handoff": "not-reached", "pre_ownership": "not-reached",
                  "data_reference": "not-reached", "fixed_facade": "not-reached",
                  "kernal_freedom": "not-reached"},
        "diagnosis": {
            "not_a_bss_allocation": (
                "The ordinary BSS byte count is identical. Bank-0 text/layout growth moved "
                "the unchanged BSS start by 160 bytes and exhausted its 19-byte corridor."),
            "overvalidation_cost": (
                "The failed probe strengthened every hot direct kind into a fresh semantic "
                "revalidation. That replaced the proven 532-byte child resolver with a "
                "1,316-byte status resolver plus a 94-byte wrapper, spending 878 E000 bytes. "
                "C2 already validates those immutable descriptors at stage/decode; the hot "
                "contract only needs the approved descriptor read, resolution lookup and "
                "kind-3/7 canonical-root indirection."),
            "call_shape_cost": (
                "Passing metadata geometry through the VM refill grew c2_product_entry_read "
                "by 328 bytes. The existing c2_entry_records seam already owns directory, "
                "image, generation, metadata-header and entry lookup."),
        },
        "recommended_bounded_followup": {
            "id": "resident-entry-materializer-over-existing-record-seam",
            "shape": (
                "Restore the proven lean child resolver; expose one resident-island entry-level "
                "materializer that reuses c2_entry_records and accepts ordinal/hot-buffer only. "
                "Phase 13 and VM refill both call that function. Direct-kind semantics remain "
                "stage/decode-owned; the hot seam retains descriptor IO and canonical-root checks."),
            "why_it_targets_all_three_reds": [
                "removes the 878-byte E000 overvalidation growth",
                "removes metadata geometry and 24-byte header handling from Bank-0 VM refill",
                "spends the measured 1,393-byte pre-probe island headroom instead of closed Bank 0/E000"],
            "hard_gates": [
                "same 588-entry/1,931-value semantic and mutation matrix",
                "Bank-0 text and BSS headrooms nonnegative with full deltas",
                "E000 owned residents no larger than the fixed profile boundary",
                "resident island including annex <= 2,048 bytes",
                "phase 13 <= 1,792 bytes and both callsites reach exactly one materializer",
                "one new capacity/placement probe; any red returns for review before a product link"],
        },
        "rejected_shortcuts": [
            "raise any Bank-0, E000, island or phase cap",
            "cache a second persistent literal-value representation",
            "remove stage/decode validation or canonical-root checks",
            "bundle the separate 27-overlay-call transaction redesign into this repair"],
        "claim_limit": (
            "Exact first-red attribution from one failed product-shaped seed link. No product "
            "closure, structural-gate, hardware, latency, promotion or acceptance claim."),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check"))
    args = parser.parse_args()
    try:
        data = canonical(build())
        if args.action == "write":
            if OUTPUT.exists(): os.chmod(OUTPUT, 0o644)
            OUTPUT.write_bytes(data); os.chmod(OUTPUT, 0o444)
        else:
            require(OUTPUT.read_bytes() == data, "first-red receipt drift")
        value = json.loads(data)
        red = value["first_red"]
        print(f"c2-hot-refill-capacity-first-red: {args.action.upper()} "
              f"text={red['bank0_text']['probe_headroom_bytes']} "
              f"bss={red['bank0_bss']['probe_headroom_bytes']} "
              f"e000-overlap={red['owned_e000_c2_resident']['probe_overlap_with_fixed_profile_rodata_bytes']} "
              "product-links=0")
        return 0
    except (OSError, ValueError, KeyError, FirstRedError) as error:
        print(f"c2-hot-refill-capacity-first-red: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
