#!/usr/bin/env python3
"""Bind the authorized Resident-Island seed's first-red capacity result."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "build/c2.2/substitution/product-link-29-direct-entry-encoding"
PROBE = ROOT / "build/c2.2/substitution/hot-refill-resident-capacity-probe"
BASE_MAP = BASE / "resident-island-seed.prg.map"
PROBE_MAP = PROBE / "hot-refill-capacity-seed.prg.map"
PROBE_LTO = PROBE / "hot-refill-capacity-seed.prg.lto.o"
PROBE_STDERR = PROBE / "hot-refill-capacity-seed.prg.link.stderr.txt"
PROBE_STDOUT = PROBE / "hot-refill-capacity-seed.prg.link.stdout.txt"
PROFILE = PROBE / "resolved-profile.txt"
LINK29 = BASE / "lisp65-c2-substitution-linked.prg"
LINK29_ARCHIVE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/artifacts/"
    "c2-link29-direct-entry-encoding-pass-20260720/root/"
    "lisp65-c2-substitution-linked.prg")
CONTRACT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-hot-refill-resident-entry-contract-probe-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-hot-refill-resident-entry-capacity-first-red-receipt.json")


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


def section(text: str, name: str) -> dict[str, int]:
    match = re.search(
        r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+"
        + re.escape(name) + r"\s*$", text, re.MULTILINE)
    require(match is not None, f"section {name} absent")
    return {"address": int(match.group(1), 16),
            "load_address": int(match.group(2), 16),
            "bytes": int(match.group(3), 16)}


def symbol(text: str, name: str) -> dict[str, int]:
    match = re.search(
        r"^\s*([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+"
        + re.escape(name) + r"\s*$", text, re.MULTILINE)
    require(match is not None, f"symbol {name} absent")
    return {"address": int(match.group(1), 16),
            "bytes": int(match.group(2), 16)}


def build() -> dict[str, Any]:
    for path in (BASE_MAP, PROBE_MAP, PROBE_LTO, PROBE_STDERR,
                 PROBE_STDOUT, PROFILE, LINK29, LINK29_ARCHIVE,
                 CONTRACT_RECEIPT):
        require(path.is_file(), f"required evidence absent: {path}")
    require(sha(LINK29) == sha(LINK29_ARCHIVE)
            == "01c6b8ff25072349e353973c0e66f239eb89efc30de4ac742bd19ef54a9bdb0c",
            "Link 29 identity changed")
    require(not (PROBE / "hot-refill-capacity-seed.prg").exists()
            and not (PROBE / "hot-refill-capacity-seed.prg.elf").exists(),
            "failed seed unexpectedly emitted an executable")
    base = BASE_MAP.read_text(encoding="utf-8", errors="replace")
    probe = PROBE_MAP.read_text(encoding="utf-8", errors="replace")
    diagnostics = PROBE_STDERR.read_text(encoding="utf-8")
    require("C2 profile rodata is not adjacent to session state" in diagnostics
            and "session_emitter_state virtual address range overlaps" in diagnostics,
            "expected first-red linker diagnostics absent")

    b_text = section(base, ".text"); p_text = section(probe, ".text")
    b_bss = section(base, ".bss"); p_bss = section(probe, ".bss")
    b_c2 = section(base, ".lisp65_c2_kernal_window.c2_resident")
    p_c2 = section(probe, ".lisp65_c2_kernal_window.c2_resident")
    b_state = section(base, ".lisp65_c2_kernal_window.session_emitter_state")
    p_state = section(probe, ".lisp65_c2_kernal_window.session_emitter_state")
    profile = section(probe, ".lisp65_c2_kernal_window.profile_rodata")
    b_island = section(base, ".lisp65_resident_island")
    p_island = section(probe, ".lisp65_resident_island")
    b_annex = section(base, ".lisp65_resident_island_annex")
    p_annex = section(probe, ".lisp65_resident_island_annex")
    b_phase = section(base, ".lisp65_rt_c2d_13")
    p_phase = section(probe, ".lisp65_rt_c2d_13")
    b_fixed = section(base, ".lisp65_c2_fixed_bank0")
    p_fixed = section(probe, ".lisp65_c2_fixed_bank0")
    b_fixed_code = section(base, ".lisp65_c2_fixed_bank0_code")
    p_fixed_code = section(probe, ".lisp65_c2_fixed_bank0_code")
    b_zp = section(base, ".lisp65_c2_fixed_zp")
    p_zp = section(probe, ".lisp65_c2_fixed_zp")

    b_child = symbol(base, "c2_stream_product_child_value")
    p_child = symbol(probe, "c2_stream_product_child_value")
    b_records = symbol(base, "c2_entry_records")
    p_records = symbol(probe, "c2_entry_records")
    b_length = symbol(base, "c2_product_entry_length")
    p_length = symbol(probe, "c2_product_entry_length")
    b_read = symbol(base, "c2_product_entry_read")
    p_read = symbol(probe, "c2_product_entry_read")
    materializer = symbol(probe, "c2_stream_product_materialize_entry")

    text_limit = 0xB481
    b_text_room = text_limit - (b_text["address"] + b_text["bytes"])
    p_text_room = text_limit - (p_text["address"] + p_text["bytes"])
    fixed_base = 0xC080
    b_bss_room = fixed_base - (b_bss["address"] + b_bss["bytes"])
    p_bss_room = fixed_base - (p_bss["address"] + p_bss["bytes"])
    overlap = p_state["address"] + p_state["bytes"] - profile["address"]
    island_room = 2048 - p_island["bytes"] - p_annex["bytes"]
    require((b_text_room, p_text_room, b_bss_room, p_bss_room)
            == (176, 263, 19, 19), "Bank-0 arithmetic drift")
    require(p_c2["bytes"] - b_c2["bytes"] == 171
            and p_state["address"] - b_state["address"] == 171
            and overlap == 171, "E000 first-red arithmetic drift")
    require((p_child["bytes"] - b_child["bytes"],
             p_records["bytes"] - b_records["bytes"],
             p_length["bytes"] - b_length["bytes"]) == (73, 123, -25),
            "E000 symbol attribution drift")
    require(73 + 123 - 25 == 171, "E000 attribution does not close")
    require(p_island["bytes"] - b_island["bytes"] == 789
            and materializer["bytes"] == 789 and island_room == 604,
            "Resident-Island arithmetic drift")
    require((b_phase["bytes"], p_phase["bytes"]) == (1776, 121),
            "phase-13 arithmetic drift")
    require(b_fixed == p_fixed and b_fixed_code == p_fixed_code and b_zp == p_zp,
            "fixed Bank-0 or ZP drift")

    for path in (PROBE_LTO, PROBE_MAP, PROBE_STDERR, PROBE_STDOUT, PROFILE):
        os.chmod(path, 0o444)
    return {
        "format": "lisp65-c2-hot-refill-resident-entry-capacity-first-red-v1",
        "recorded_on": "2026-07-20",
        "status": "stopped-first-red-no-product-link",
        "scope": {"authorized_resident_island_seed_attempts": 1,
                  "seed_attempts_consumed": 1, "seed_executables_emitted": 0,
                  "product_links": 0, "hardware_execution": "none",
                  "promotion": "blocked"},
        "identity": {
            "link29_product": bind(LINK29),
            "link29_archived_product": bind(LINK29_ARCHIVE),
            "semantic_and_stage_contract_receipt": bind(CONTRACT_RECEIPT),
            "baseline_map": bind(BASE_MAP), "failed_probe_map": bind(PROBE_MAP),
            "failed_probe_lto_object": bind(PROBE_LTO),
            "linker_diagnostics": bind(PROBE_STDERR),
            "linker_stdout": bind(PROBE_STDOUT),
            "resolved_probe_profile": bind(PROFILE),
        },
        "first_red": {
            "currency": "owned-e000-positional-layout",
            "session_emitter_state": {
                "link29_start": f"0x{b_state['address']:04x}",
                "probe_start": f"0x{p_state['address']:04x}",
                "bytes": p_state["bytes"],
                "probe_end_exclusive": f"0x{p_state['address'] + p_state['bytes']:04x}"},
            "fixed_profile_rodata_start": f"0x{profile['address']:04x}",
            "overlap_bytes": overlap,
            "c2_resident_growth_bytes": p_c2["bytes"] - b_c2["bytes"],
            "exact_symbol_attribution": {
                "lean_child_resolver_delta_bytes": p_child["bytes"] - b_child["bytes"],
                "entry_records_delta_bytes": p_records["bytes"] - b_records["bytes"],
                "entry_length_credit_bytes": b_length["bytes"] - p_length["bytes"],
                "sum_bytes": 171},
        },
        "capacity_observed_before_stop": {
            "bank0_text": {"link29_headroom_bytes": b_text_room,
                           "probe_headroom_bytes": p_text_room,
                           "credit_bytes": p_text_room - b_text_room,
                           "entry_read_delta_bytes": p_read["bytes"] - b_read["bytes"]},
            "bank0_bss": {"link29_bytes": b_bss["bytes"],
                          "probe_bytes": p_bss["bytes"],
                          "link29_headroom_bytes": b_bss_room,
                          "probe_headroom_bytes": p_bss_room},
            "bank0_fixed_block": {"bytes": p_fixed["bytes"],
                                  "code_bytes": p_fixed_code["bytes"],
                                  "delta_bytes": 0},
            "zero_page_fixed": {"bytes": p_zp["bytes"], "delta_bytes": 0},
            "resident_island": {"link29_base_bytes": b_island["bytes"],
                                "probe_base_bytes": p_island["bytes"],
                                "materializer_bytes": materializer["bytes"],
                                "annex_bytes": p_annex["bytes"],
                                "headroom_bytes": island_room},
            "phase13_overlay": {"link29_bytes": b_phase["bytes"],
                                "probe_bytes": p_phase["bytes"],
                                "credit_bytes": b_phase["bytes"] - p_phase["bytes"],
                                "headroom_bytes": 1792 - p_phase["bytes"]},
            "owned_e000": {"link29_c2_resident_bytes": b_c2["bytes"],
                           "probe_c2_resident_bytes": p_c2["bytes"],
                           "positional_overlap_bytes": overlap,
                           "status": "failed"},
            "runtime_overlay_bank": "not-packed-first-red-preceded-pack-gate",
            "bank5_mutable_plane": "unchanged-input-not-relinked",
            "attic_immutable_shelf": "unchanged-input-not-relinked",
            "installer_slice": "outside-C2-closure-unmodified",
        },
        "gates": {
            "source_single_materializer": "passed-before-seed",
            "stage_content_mutations": "4/4-rejected-before-publication",
            "hot_semantics": "588/588-entries-1931/1931-values",
            "hot_transport_failures": "2/2-fail-closed",
            "capacity_and_placement": "failed-first",
            "handoff": "not-reached", "pre_ownership": "not-reached",
            "data_reference": "not-reached", "fixed_facade": "not-reached",
            "kernal_freedom": "not-reached"},
        "diagnosis": {
            "successful_shape": (
                "The shared materializer consumes 789 Resident-Island bytes with 604 "
                "bytes remaining; phase 13 shrinks by 1655 bytes and Bank-0 text gains "
                "87 bytes."),
            "failed_shape": (
                "The implementation changed the established E000 record seam and child "
                "resolver. Their +73/+123 bytes, partly offset by a 25-byte entry-length "
                "credit, shift the fixed-size session state by exactly 171 bytes into "
                "profile rodata. The closed E000 window cannot absorb that drift."),
            "architectural_implication": (
                "A successor would have to preserve the Link-29 E000 implementations "
                "byte-for-byte in placement terms and house the shared entry materializer "
                "entirely in the Island. This attempt does not prove that successor fits."),
        },
        "claim_limit": (
            "Exact first-red attribution from the one authorized product-shaped seed. "
            "No executable seed, product link, complete structure-gate run, hardware, "
            "latency, promotion, acceptance or performance claim."),
        "next_action": (
            "The one-time attempt is exhausted. Return the measured 171-byte positional "
            "failure for review; do not retry, reclaim, relax a cap or alter Link 29 "
            "without a new explicit layout authorization."),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        data = canonical(build())
        if args.action == "write":
            if RECEIPT.exists(): os.chmod(RECEIPT, 0o644)
            RECEIPT.write_bytes(data); os.chmod(RECEIPT, 0o444); verb = "WROTE"
        elif args.action == "check":
            require(RECEIPT.read_bytes() == data, "first-red receipt drift")
            verb = "PASS"
        else:
            verb = "SELFTEST PASS"
        print("c2-hot-refill-resident-first-red: " + verb
              + " e000-overlap=171 island-headroom=604 phase13=121/1792"
              + " product-links=0")
        return 0
    except (OSError, ValueError, KeyError, FirstRedError) as error:
        print(f"c2-hot-refill-resident-first-red: FAIL: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
