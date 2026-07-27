#!/usr/bin/env python3
"""Probe the approved C2-lite phase-11 cut and explain the E000 First Red."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_full_emission as F  # noqa: E402
import c2_gc_root_single_source as G  # noqa: E402
import c2_link33_bss_triage_product_link as BASE  # noqa: E402
import c2_lite_root_surrogate as R  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402
import c2_stream_decoder_v2 as HOST_V2  # noqa: E402


OUT = ROOT / "build/c2-lite/v6-phase11-split-e000-analysis"
HARNESS_RED_ENTRY = ROOT / (
    "build/c2-lite/v6-phase11-split-e000-analysis-"
    "harness-first-red-entry-census/c2-phase11-split-host")
HARNESS_RED_CORPUS = ROOT / (
    "build/c2-lite/v6-phase11-split-e000-analysis-"
    "harness-first-red-moving-v2-corpus/c2-phase11-split-host")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-phase11-split-e000-analysis-receipt.json")
BASELINE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-product-shaped-probe-receipt.json")
BASELINE_MAP = ROOT / (
    "build/c2-lite/product-shaped-v6-probe/full-product-wplto/"
    "c2-lite-v6-full-seed.prg.map")
CAP = 1792


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def command(argv: list[str], *, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True,
                            timeout=timeout, check=False)
    if result.returncode:
        raise ProbeError(
            f"{Path(argv[0]).name} returned {result.returncode}: "
            f"{(result.stderr or result.stdout).strip()}")
    return result


def split_host_semantics() -> dict[str, Any]:
    """Run all 168 real pairs through the two transported halves."""
    host = OUT / "c2-phase11-split-host"
    sources: list[Path] = []
    old = ROOT / "scripts/c2-stream-v2-phase-11.c"
    for source in HOST_V2.SOURCES:
        if source == old:
            sources.extend((ROOT / "scripts/c2-stream-v2-phase-11a.c",
                            ROOT / "scripts/c2-stream-v2-phase-11b.c"))
        else:
            sources.append(source)
    result = command([
        "cc", "-std=c99", "-Os", "-Wall", "-Wextra", "-Werror",
        "-DC2_STREAM_PHASE11_SPLIT_TEST=1",
        "-I", str(ROOT / "scripts"), "-I", str(ROOT / "src"),
        *map(str, sources), str(ROOT / "scripts/c2-stream-v2-host-main.c"),
        "-o", str(host),
    ])
    require(not result.stdout and not result.stderr, "split host compiler diagnostics")
    # Bind the split to the immutable six-image/168-pair corpus that originally
    # proved this decoder.  The live v6 composition has since gained entries
    # and is proven by the separate v6 product-shaped gate; rebuilding the old
    # C2D-v2 receipt from that moving source would mix two contract generations.
    shelf_path = ROOT / "build/c2.1/streaming-decoder-v2/shelf.bin"
    c2d_path = ROOT / "build/c2.1/streaming-decoder-v2/c2d-v2.bin"
    require(sha(shelf_path)
            == "df3050a092b27593124246d91c33c8db3994deb2e01f93a050353f3372e8287c"
            and sha(c2d_path)
            == "a8495be33895530abbc1e039d254d728386eb45563fabd5b4487f0f27550f82f",
            "immutable phase-11 parity corpus drift")
    run = command([str(host), str(shelf_path), str(c2d_path)])
    expected = (
        "c2-stream-v2: PASS shelf=69754 c2d=11048 images=6 entries=583 "
        "descriptors=2249 roots=284 gc=284 materialized=583 max-literals=23 "
        "context=44"
    )
    require(run.stdout.strip() == expected and not run.stderr,
            "split host semantics drift: " + run.stdout.strip())
    (OUT / "phase11-split-host.stdout.txt").write_text(run.stdout, encoding="utf-8")
    return {
        "status": "passed-real-six-image-v2-parity",
        "images": 6, "entries": 583, "descriptors": 2249,
        "pairs": 168, "roots": 284, "gc_checkpoints": 284,
        "immutable_inputs": {"shelf": bind(shelf_path), "c2d": bind(c2d_path)},
        "result": bind(OUT / "phase11-split-host.stdout.txt"),
        "binary": bind(host),
    }


def cutpoint_gate() -> dict[str, Any]:
    binary = OUT / "c2-phase11-cutpoint"
    result = command([
        "cc", "-std=c99", "-Os", "-Wall", "-Wextra", "-Werror",
        "-I", str(ROOT / "scripts"), "-I", str(ROOT / "src"),
        str(ROOT / "scripts/c2-stream-v2-phase-11a.c"),
        str(ROOT / "scripts/c2-stream-v2-phase-11b.c"),
        str(ROOT / "scripts/c2-phase11-cutpoint-main.c"), "-o", str(binary),
    ])
    require(not result.stdout and not result.stderr, "cutpoint compiler diagnostics")
    run = command([str(binary)])
    expected = "c2-phase11-cutpoint: PASS negatives=4 added-handoff-bytes=0"
    require(run.stdout.strip() == expected and not run.stderr,
            "phase-11 cutpoint gate drift")
    (OUT / "phase11-cutpoint.stdout.txt").write_text(run.stdout, encoding="utf-8")
    return {
        "status": "passed",
        "marker": "context.reserved=0x11",
        "added_handoff_bytes": 0,
        "cross_boundary_pointers": 0,
        "negative_fixtures": [
            "skip-11a", "replay-11a", "wrong-marker", "preexisting-error",
        ],
        "result": bind(OUT / "phase11-cutpoint.stdout.txt"),
        "binary": bind(binary),
    }


def configure_phase11_split() -> None:
    old_source = ROOT / "scripts/c2-stream-v2-phase-11.c"
    index = P.C2_PHASE_SOURCES.index(old_source)
    P.C2_PHASE_SOURCES[index:index + 1] = [
        ROOT / "scripts/c2-stream-v2-phase-11a.c",
        ROOT / "scripts/c2-stream-v2-phase-11b.c",
    ]
    decoder: list[tuple[str, str]] = []
    for name, entry in P.C2_DECODER_SLICES:
        if name == "11":
            decoder.extend((("11a", "c2_stream_phase_11a"),
                            ("11b", "c2_stream_phase_11b")))
        else:
            decoder.append((name, entry))
    P.C2_DECODER_SLICES = decoder
    P.BOOT_DECODER_SLICES = decoder[:6]
    P.SESSION_DECODER_SLICES = decoder[6:]
    P.SESSION_EMITTER_SLOT_BASE = 2 + len(P.SESSION_DECODER_SLICES)
    P.SESSION_APPEND_SLOT_BASE = (
        P.SESSION_EMITTER_SLOT_BASE + len(P.C2_EMITTER_SLICES))
    P.configure_append_slices(list(P.C2_APPEND_SLICES))
    require(len(P.C2_DECODER_SLICES) == 18
            and len(P.SESSION_DECODER_SLICES) == 12
            and len(P.SESSION_SLICE_SPECS) == 47
            and P.SESSION_EMITTER_SLOT_BASE == 14
            and P.SESSION_APPEND_SLOT_BASE == 22
            and P.SESSION_SERVICE_SLOT_BASE == 43
            and P.UNIQUE_SLICE_COUNT == 54,
            "phase-11 split runtime-family ABI drift")


def split_wplto() -> tuple[Path, Path, Path, str]:
    """Run one nonpromotable WPLTO; E000 is expected to remain red."""
    original_configure = BASE.configure
    original_features = BASE.FEATURES

    def configure() -> None:
        original_configure()
        configure_phase11_split()

    BASE.configure = configure
    BASE.FEATURES = (*original_features, "LISP65_C2_PHASE11_SPLIT")
    V6.OUT = OUT
    try:
        try:
            V6.full_product_wplto()
        except (RuntimeError, subprocess.CalledProcessError, V6.ProbeError) as error:
            failure = str(error)
        else:
            failure = "unexpected-complete-WPLTO-success"
    finally:
        BASE.configure = original_configure
        BASE.FEATURES = original_features
    full = OUT / "full-product-wplto"
    stem = full / "c2-lite-v6-full-seed.prg"
    map_path = Path(str(stem) + ".map")
    stderr = Path(str(stem) + ".link.stderr.txt")
    lto = Path(str(stem) + ".lto.o")
    require(map_path.is_file() and stderr.is_file() and lto.is_file(),
            "split WPLTO evidence incomplete")
    diagnostic = stderr.read_text(encoding="utf-8")
    require("phase 11a exceeds" not in diagnostic
            and "phase 11b exceeds" not in diagnostic
            and "final E000 floor below 115 bytes" in diagnostic,
            "split WPLTO stopped outside the authorized E000 question")
    require(not stem.is_file() and not Path(str(stem) + ".elf").is_file(),
            "failed nonproduct WPLTO emitted a final product artifact")
    return map_path, stderr, lto, failure


SECTION_RE = re.compile(
    r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+(\.[^\s]+)$")
SYMBOL_RE = re.compile(
    r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+([A-Za-z_][A-Za-z0-9_.$]*)$")


def map_sections(path: Path) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = SECTION_RE.match(line)
        if match:
            result[match.group(4)] = {
                "address": int(match.group(1), 16),
                "load_address": int(match.group(2), 16),
                "bytes": int(match.group(3), 16),
            }
    return result


def resident_symbols(path: Path) -> dict[str, dict[str, int]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines)
                 if SECTION_RE.match(line)
                 and SECTION_RE.match(line).group(4)
                 == ".lisp65_c2_kernal_window.c2_resident")
    rows: dict[str, dict[str, int]] = {}
    for line in lines[start + 1:]:
        section = SECTION_RE.match(line)
        if section:
            break
        match = SYMBOL_RE.match(line)
        if match and int(match.group(3), 16):
            rows[match.group(4)] = {
                "address": int(match.group(1), 16),
                "bytes": int(match.group(3), 16),
            }
    require(rows, "C2 resident symbol inventory absent")
    return rows


KERNAL_SECTIONS = (
    ".lisp65_c2_kernal_window.typed_queue_driver",
    ".lisp65_c2_kernal_window.frame_source",
    ".lisp65_c2_kernal_window.irq_handler",
    ".lisp65_c2_kernal_window.nmi_and_freezer_return",
    ".lisp65_c2_kernal_window.map_switch_and_guards",
    ".lisp65_c2_kernal_window.post_startup_output_seam",
    ".lisp65_c2_kernal_window.event_poll",
    ".lisp65_c2_kernal_window.c2_resident",
    ".lisp65_c2_kernal_window.session_emitter_state",
    ".lisp65_c2_kernal_window.profile_rodata",
    ".lisp65_c2_kernal_window.state", ".lisp65_c2_vectors",
    ".lisp65_c2_kernal_window.reopen_gap0",
    ".lisp65_c2_kernal_window.reopen_gap1",
    ".lisp65_c2_kernal_window.reopen_gap2",
)


TEMPERATURE = {
    "c2_append_begin": "cold-session-append-driver",
    "c2_overlay_call": "retained-transport-seam",
    "c2_overlay_call_range": "cold-session-append-driver",
    "c2_decode_from": "cold-boot-and-append-driver",
    "c2_stream_shelf_read": "cold-source-read-seam",
    "c2_dma_copy": "retained-DMA-seam",
    "c2_stream_c2d_read": "hot-shared-C2D-seam",
    "c2_stream_c2d_write": "cold-publication-seam",
    "c2_stream_product_image_read": "cold-decoder-helper",
    "c2_stream_product_string_record_any": "cold-decoder-helper",
    "c2_stream_product_string_record": "cold-decoder-helper",
    "c2_stream_product_canonical_name": "cold-decoder-helper",
    "c2_stream_product_child_value": "cold-phase11-helper",
    "c2_stream_name_value": "cold-decoder-helper",
    "c2_stream_gc_checkpoint": "cold-decode-GC-boundary",
    "c2_product_entry_record": "hot-v6-lookup",
    "c2_entry_records": "cold-append-publication-legacy-view",
    "c2_source_read": "cold-stage-and-name-source-read",
    "c2_product_entry_length": "hot-v6-entry-length-wrapper",
    "c2_product_gc_mark_roots": "hot-GC-root-scan",
    "c2_header_counts": "cold-session-emitter",
    "c2_session_emit_reset": "cold-session-emitter",
    "c2_session_emit_add": "cold-session-emitter",
    "c2_session_emit_finalize": "cold-session-emitter",
    "vm_logical_relative_target": "hot-VM-branch-helper",
}


def e000_attribution(map_path: Path) -> dict[str, Any]:
    sections = map_sections(map_path)
    symbols = resident_symbols(map_path)
    require(all(name in sections for name in KERNAL_SECTIONS),
            "E000 section inventory incomplete")
    inventory = []
    for name, row in symbols.items():
        inventory.append({"object": name, **row,
                          "temperature": TEMPERATURE.get(name, "unclassified-red")})
    require(all(row["temperature"] != "unclassified-red" for row in inventory),
            "E000 function lacks temperature attribution")

    old = {
        "c2_product_entry_length": 176,
        "c2_entry_records": 615,
        "c2_stream_product_child_value": 536,
        "c2_source_read": 123,
    }
    redesign = [
        {"object": "c2_stream_product_child_value",
         "memo_alt_bytes": old["c2_stream_product_child_value"],
         "current_alt_bytes": symbols["c2_stream_product_child_value"]["bytes"],
         "current_new_bytes": 0,
         "temperature": TEMPERATURE["c2_stream_product_child_value"],
         "disposition": "still resident; candidate for the split decoder family"},
        {"object": "c2_entry_records",
         "memo_alt_bytes": old["c2_entry_records"],
         "current_alt_bytes": symbols["c2_entry_records"]["bytes"],
         "current_new_bytes": 0,
         "temperature": TEMPERATURE["c2_entry_records"],
         "disposition": "still resident; only sliced publish-name/cell consumers remain"},
        {"object": "c2_source_read",
         "memo_alt_bytes": old["c2_source_read"],
         "current_alt_bytes": symbols["c2_source_read"]["bytes"],
         "current_new_bytes": 0,
         "temperature": TEMPERATURE["c2_source_read"],
         "disposition": "still resident; no C2-lite hot-refill consumer remains"},
        {"object": "c2_product_entry_length",
         "memo_alt_bytes": old["c2_product_entry_length"],
         "current_alt_bytes": 0,
         "current_new_bytes": symbols["c2_product_entry_length"]["bytes"],
         "temperature": TEMPERATURE["c2_product_entry_length"],
         "disposition": "old C2I walk retired; retain the v6 C2D wrapper"},
        {"object": "c2_product_entry_record",
         "memo_alt_bytes": 0, "current_alt_bytes": 0,
         "current_new_bytes": symbols["c2_product_entry_record"]["bytes"],
         "temperature": TEMPERATURE["c2_product_entry_record"],
         "disposition": "new single v6 execution-record lookup; hot and retained"},
    ]
    memo = sum(old.values())
    remaining = sum(row["current_alt_bytes"] for row in redesign)
    new = sum(row["current_new_bytes"] for row in redesign)
    require((memo, remaining, new, remaining + new - memo)
            == (1450, 1218, 546, 314),
            "memo/current E000 redesign equation drift")

    resident = sections[".lisp65_c2_kernal_window.c2_resident"]
    state = sections[".lisp65_c2_kernal_window.session_emitter_state"]
    end = resident["address"] + resident["bytes"]
    overhang_rows = []
    for name, row in symbols.items():
        row_end = row["address"] + row["bytes"]
        overlap = max(0, row_end - max(row["address"], state["address"]))
        if overlap:
            overhang_rows.append({"object": name, "overlap_bytes": overlap,
                                  "address": row["address"], "end": row_end})
    require(end - state["address"] == 169
            and sum(row["overlap_bytes"] for row in overhang_rows) == 169,
            "169-byte anchor-overhang attribution drift")
    e000 = sum(sections[name]["bytes"] for name in KERNAL_SECTIONS)
    require(e000 == 8391 and e000 + 115 - 8192 == 314,
            "baseline E000 wall arithmetic drift")
    return {
        "source": bind(map_path),
        "three_column_redesign_surface": redesign,
        "equation": {
            "memo_gross_alt_surface_bytes": memo,
            "remaining_alt_bytes": remaining,
            "new_v6_bytes": new,
            "current_surface_bytes": remaining + new,
            "net_over_memo_bytes": remaining + new - memo,
            "deficit_to_115_floor_bytes": 314,
            "identity": "1218 + 546 - 1450 = 314",
        },
        "anchor_overhang": {
            "resident_end_exclusive": end,
            "session_state_base": state["address"],
            "bytes": end - state["address"],
            "occupants": overhang_rows,
            "interpretation": "positional symptom of the oversized resident section, not a separate tenant debit",
        },
        "complete_c2_resident_inventory": inventory,
        "temperature_result": {
            "cold_alt_bytes": remaining,
            "hot_new_bytes": new,
            "cold_alt_exceeds_floor_deficit_by_bytes": remaining - 314,
            "floor_bytes": 115,
            "floor_status": "fixed-not-discussed",
        },
    }


def split_e000_delta(map_path: Path) -> dict[str, Any]:
    """Attribute every E000 change caused by the authorized phase split."""
    before_sections = map_sections(BASELINE_MAP)
    after_sections = map_sections(map_path)
    before_symbols = resident_symbols(BASELINE_MAP)
    after_symbols = resident_symbols(map_path)
    section_deltas = {
        name: after_sections[name]["bytes"] - before_sections[name]["bytes"]
        for name in KERNAL_SECTIONS
    }
    nonzero_sections = {name: value for name, value in section_deltas.items()
                        if value}
    symbol_deltas = []
    for name in sorted(set(before_symbols) | set(after_symbols)):
        before = before_symbols.get(name, {}).get("bytes", 0)
        after = after_symbols.get(name, {}).get("bytes", 0)
        if before != after:
            symbol_deltas.append({"object": name, "before_bytes": before,
                                  "after_bytes": after, "delta_bytes": after - before,
                                  "temperature": TEMPERATURE.get(name, "unclassified-red")})
    require(nonzero_sections == {
                ".lisp65_c2_kernal_window.c2_resident": 19,
            }
            and symbol_deltas == [{
                "object": "c2_decode_from", "before_bytes": 456,
                "after_bytes": 475, "delta_bytes": 19,
                "temperature": "cold-boot-and-append-driver",
            }], "phase-11 split E000 delta lacks exact attribution")

    resident = after_sections[".lisp65_c2_kernal_window.c2_resident"]
    state = after_sections[".lisp65_c2_kernal_window.session_emitter_state"]
    resident_end = resident["address"] + resident["bytes"]
    occupants = []
    for name, row in after_symbols.items():
        row_end = row["address"] + row["bytes"]
        overlap = max(0, row_end - max(row["address"], state["address"]))
        if overlap:
            occupants.append({"object": name, "address": row["address"],
                              "end": row_end, "overlap_bytes": overlap})
    require(resident_end - state["address"] == 188
            and sum(row["overlap_bytes"] for row in occupants) == 188,
            "post-split anchor-overhang attribution drift")
    return {
        "sections": section_deltas,
        "nonzero_sections": nonzero_sections,
        "symbols": symbol_deltas,
        "e000_delta_bytes": sum(section_deltas.values()),
        "deficit_equation": "314 baseline + 19 split-driver = 333",
        "anchor_overhang": {
            "baseline_bytes": 169,
            "post_split_bytes": resident_end - state["address"],
            "split_driver_positional_delta_bytes": 19,
            "occupants": occupants,
            "interpretation": (
                "The authorized split grows only the cold decode driver. Its 19-byte "
                "positional effect adds to, but does not create a separate tenant debit."
            ),
        },
    }


def run_probe() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "phase11/E000 probe is one-shot and already exists")
    baseline = json.loads(BASELINE_RECEIPT.read_text(encoding="utf-8"))
    require(baseline["status"]
            == "FIRST RED: full product-shaped WPLTO capacity/layout",
            "baseline C2-lite First Red absent")
    OUT.mkdir(parents=True)
    roots = R.collect()
    host = split_host_semantics()
    cutpoint = cutpoint_gate()
    old_attribution = e000_attribution(BASELINE_MAP)
    new_map, stderr, lto, failure = split_wplto()
    sections = map_sections(new_map)
    require(sections[".lisp65_rt_c2d_11a"]["bytes"] <= CAP
            and sections[".lisp65_rt_c2d_11b"]["bytes"] <= CAP,
            "phase-11 semantic halves exceed the immutable cap")
    new_e000 = sum(sections[name]["bytes"] for name in KERNAL_SECTIONS)
    new_floor_deficit = new_e000 + 115 - 8192
    split_delta = split_e000_delta(new_map)
    require(new_floor_deficit == 333
            and old_attribution["equation"]["deficit_to_115_floor_bytes"]
            + split_delta["e000_delta_bytes"] == new_floor_deficit,
            "post-split E000 deficit is not completely attributed")
    report = {
        "format": "lisp65-c2-lite-v6-phase11-split-e000-analysis-v1",
        "recorded_on": "2026-07-21",
        "status": "phase11-split-green-e000-attribution-complete-product-link-not-run",
        "scope": {
            "product_source_change": "phase11-semantic-split-only",
            "nonpromotable_product_shaped_wplto_attempts": 1,
            "product_links": 0, "hardware_runs": 0, "promotion": "not-authorized",
        },
        "authority": {"baseline_first_red": bind(BASELINE_RECEIPT),
                      "root_surrogate_contract": bind(V6.CONTRACT)},
        "root_surrogate_permanent_gate": roots,
        "phase11_split": {
            "semantic_boundary": {
                "11a": "validate every immutable pair descriptor and backward-only child ordinal",
                "11b": "resolve children, allocate pair, publish sole root, run GC checkpoint",
                "handoff": "existing context.reserved marker 0x11 only",
                "added_handoff_bytes": 0, "cross_boundary_pointers": 0,
            },
            "host_semantics": host, "cutpoint_gate": cutpoint,
            "wplto_bytes": {
                "11a": sections[".lisp65_rt_c2d_11a"]["bytes"],
                "11b": sections[".lisp65_rt_c2d_11b"]["bytes"],
            },
            "wplto_headroom_bytes": {
                "11a": CAP - sections[".lisp65_rt_c2d_11a"]["bytes"],
                "11b": CAP - sections[".lisp65_rt_c2d_11b"]["bytes"],
            },
            "cap_bytes": CAP, "cap_changed": False,
        },
        "e000_baseline_attribution": old_attribution,
        "split_wplto": {
            "status": "expected-E000-red-after-authorized-phase-split",
            "map": bind(new_map), "stderr": bind(stderr), "lto_object": bind(lto),
            "driver_failure": failure,
            "e000_use_bytes": new_e000,
            "required_floor_bytes": 115,
            "deficit_to_floor_bytes": new_floor_deficit,
            "delta_from_baseline": split_delta,
            "phase11_cap_error_present": False,
            "final_product_artifact": "absent",
        },
        "decision_result": {
            "phase11": "closed-green",
            "e000": (
                "known-red: 1218 cold-alt + 546 hot-new - 1450 memo + "
                "19 phase-split-driver = 333"
            ),
            "sufficient_cold_surface_exists": True,
            "implementation_not_authorized": True,
        },
        "rollback_line": {"product": "Link 35", "status": "untouched"},
        "claim_limit": (
            "The semantic split and objectwise residency diagnosis are proven by one "
            "nonpromotable WPLTO. No E000 evacuation, product link, hardware, latency, "
            "promotion or acceptance claim exists."
        ),
        "next_gate": (
            "Class-C review of the cold-alt evacuation design; the 115-byte floor is fixed."
        ),
    }
    report_path = OUT / "c2-lite-v6-phase11-e000-analysis.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    report["report"] = bind(report_path)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(RECEIPT, 0o444)
    return report


def replay_attribution() -> dict[str, Any]:
    """Pure replay: enrich the receipt from its existing SHA-bound maps."""
    value = check()
    new_map = ROOT / value["split_wplto"]["map"]["path"]
    split_delta = split_e000_delta(new_map)
    baseline_deficit = value["e000_baseline_attribution"]["equation"][
        "deficit_to_115_floor_bytes"]
    actual_deficit = value["split_wplto"]["deficit_to_floor_bytes"]
    require(baseline_deficit + split_delta["e000_delta_bytes"] == actual_deficit,
            "pure replay cannot close the E000 delta")
    value["split_wplto"]["delta_from_baseline"] = split_delta
    value["decision_result"]["e000"] = (
        "known-red: 1218 cold-alt + 546 hot-new - 1450 memo + "
        "19 phase-split-driver = 333"
    )
    implementation_paths = (
        ROOT / "scripts/c2-stream-v2-decoder.c",
        ROOT / "scripts/c2-stream-v2-decoder.h",
        ROOT / "scripts/c2-stream-v2-phase-11a.c",
        ROOT / "scripts/c2-stream-v2-phase-11b.c",
        ROOT / "scripts/c2-stream-v2-host-main.c",
        ROOT / "scripts/c2-phase11-cutpoint-main.c",
        ROOT / "src/c2_product_runtime.c",
        ROOT / "src/c2_product_runtime.h",
        Path(__file__).resolve(),
    )
    value["implementation_bindings"] = [bind(path) for path in implementation_paths]
    for artifact in (HARNESS_RED_ENTRY, HARNESS_RED_CORPUS):
        require(artifact.is_file(), "autonomous harness First Red artifact absent")
        os.chmod(artifact, 0o444)
    value["autonomous_harness_corrections"] = [
        {
            "first_red": "historical c2_full_emission entry census versus live v6 composition",
            "correction": "do not rebuild a historical C2D-v2 receipt from a moving v6 manifest",
            "artifact": bind(HARNESS_RED_ENTRY),
            "product_bytes": 0, "wplto_runs": 0, "product_links": 0,
        },
        {
            "first_red": "live v6 composition is not the immutable C2D-v2 decoder parity corpus",
            "correction": (
                "bind phase-11 parity to the original SHA-pinned 583-entry/168-pair corpus; "
                "the separate v6 gate owns the live 588-entry composition"
            ),
            "artifact": bind(HARNESS_RED_CORPUS),
            "product_bytes": 0, "wplto_runs": 0, "product_links": 0,
        },
    ]
    value.pop("report", None)
    report_path = OUT / "c2-lite-v6-phase11-e000-analysis.json"
    os.chmod(report_path, 0o644)
    report_path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    value["report"] = bind(report_path)
    os.chmod(RECEIPT, 0o644)
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(report_path, 0o444)
    os.chmod(RECEIPT, 0o444)
    return value


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "phase11/E000 receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status")
            == "phase11-split-green-e000-attribution-complete-product-link-not-run",
            "phase11/E000 receipt status drift")
    for row in (value["report"], value["authority"]["baseline_first_red"],
                value["authority"]["root_surrogate_contract"],
                value["split_wplto"]["map"], value["split_wplto"]["stderr"],
                value["split_wplto"]["lto_object"]):
        path = ROOT / row["path"]
        require(path.is_file() and path.stat().st_size == row["bytes"]
                and sha(path) == row["sha256"], "bound artifact drift: " + str(path))
    for row in (value.get("implementation_bindings", [])
                + [item["artifact"] for item in
                   value.get("autonomous_harness_corrections", [])]):
        path = ROOT / row["path"]
        require(path.is_file() and path.stat().st_size == row["bytes"]
                and sha(path) == row["sha256"], "bound source/harness drift: " + str(path))
    require(value["phase11_split"]["cap_changed"] is False
            and max(value["phase11_split"]["wplto_bytes"].values()) <= CAP
            and value["e000_baseline_attribution"]["equation"]["identity"]
            == "1218 + 546 - 1450 = 314"
            and value["e000_baseline_attribution"]["anchor_overhang"]["bytes"] == 169,
            "bound phase11/E000 arithmetic drift")
    if "delta_from_baseline" in value["split_wplto"]:
        delta = value["split_wplto"]["delta_from_baseline"]
        require(delta["e000_delta_bytes"] == 19
                and delta["anchor_overhang"]["post_split_bytes"] == 188
                and value["split_wplto"]["deficit_to_floor_bytes"] == 333,
                "bound post-split E000 attribution drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "replay", "check"))
    args = parser.parse_args()
    value = (run_probe() if args.action == "run" else
             replay_attribution() if args.action == "replay" else check())
    print("c2-lite-v6-phase11-e000: " + value["status"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.CalledProcessError, ProbeError, R.SurrogateError,
            F.FullError, G.SingleSourceError) as error:
        print("c2-lite-v6-phase11-e000: FAIL: " + str(error), file=sys.stderr)
        raise SystemExit(2)
