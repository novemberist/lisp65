#!/usr/bin/env python3
"""2026-09-24 successor: account for overlay catalog directory growth.

Import the era-bound predecessor unchanged. Its text and JSON receipt are
still emitted unchanged; a separately named dated receipt contains the
corrected projection. The exit status follows the corrected projection.

Reserve the directory for the entire requested batch before placing payloads:
all records, including overflow-region records, live in region 0. The catalog
uses 32-byte headers/records and 256-byte alignment; payload alignment remains
family-specific. A failed batch is not an admitted partial repack. Region 1/2
payloads do not shift, but their new records can exhaust region 0.

This successor fixes directory accounting only. The predecessor's conservative
unique-count admission policy is retained and labeled as inherited policy,
not as a built runtime union limit. Region 2 remains a private store; a size
projection does not authorize a new owner there. No product tools are run.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import sys
from typing import Any

import slice_capacity_preflight as PRE
import runtime_overlay_bank as BANK

PREDECESSOR_SHA256 = "ef17fe73483e26a209d70738799a0088833c72468ac5ae39979b1c4ddfbe0759"
DEFAULT_OUT = PRE.ROOT / "build/slice-capacity-preflight-20260924"
RECEIPT_NAME = "slice-capacity-preflight-20260924.json"


def check_predecessor() -> None:
    if PRE.sha256_file(Path(PRE.__file__)) != PREDECESSOR_SHA256:
        raise PRE.PreflightError("era-bound predecessor SHA-256 drift")


def directory_step(count: int, additions: int) -> int:
    if count < 0 or additions < 0:
        raise PRE.PreflightError("negative catalog record count")
    old_payload = PRE.align_up(BANK.HEADER_SIZE + count * BANK.ENTRY_SIZE,
                               BANK.CATALOG_ALIGNMENT)
    new_payload = PRE.align_up(
        BANK.HEADER_SIZE + (count + additions) * BANK.ENTRY_SIZE,
        BANK.CATALOG_ALIGNMENT)
    return new_payload - old_payload


def project(world: dict[str, Any], family: str, region: int,
            slices: list[tuple[str, int]]) -> dict[str, Any]:
    # The predecessor validates family/region and retains its slot/size policy.
    legacy = PRE.place_slices(world, family, region, slices)
    if any(not name or size <= 0 for name, size in slices):
        raise PRE.PreflightError("new slices need names and positive byte counts")
    report = world["families"][family]
    count = report["slice_count"]
    alignment = report["payload_alignment"]
    if alignment not in BANK.ACCEPTED_PAYLOAD_ALIGNMENTS:
        raise PRE.PreflightError("unsupported payload alignment")
    old_payload = PRE.align_up(BANK.HEADER_SIZE + count * BANK.ENTRY_SIZE,
                               BANK.CATALOG_ALIGNMENT)
    manifest = world["manifests"][family]
    catalog = manifest["catalog"]
    for key, expected in (("header_size", BANK.HEADER_SIZE),
                          ("entry_size", BANK.ENTRY_SIZE),
                          ("directory_offset", BANK.HEADER_SIZE),
                          ("payload_offset", old_payload)):
        if key in catalog and catalog[key] != expected:
            raise PRE.PreflightError(f"catalog {key} disagrees with packer geometry")
    shift = directory_step(count, len(slices))
    # Directory-only catalogs still occupy bytes even with no main payload.
    current_end = max(report["region0"]["used"], old_payload)
    shifted_end = current_end + shift
    directory_fits = shifted_end <= report["region0"]["capacity"]
    adjusted = deepcopy(world)
    if region == 0:
        adjusted["families"][family]["region0"]["used"] = shifted_end
        adjusted["families"][family]["region0"]["free"] = (
            report["region0"]["capacity"] - shifted_end)
    placements = PRE.place_slices(adjusted, family, region, slices)
    if not directory_fits:
        for row in placements:
            row["fits"] = False
            row["slot"] = None
    return {
        "format": "lisp65-slice-capacity-preflight-20260924-v1",
        "predecessor_sha256": PREDECESSOR_SHA256,
        "predecessor": PRE.build_receipt(world, legacy),
        "reservation_policy": "entire requested batch; no partial repack admitted",
        "slot_policy": "predecessor unique-count policy retained; not a runtime union cap",
        "directory": {
            "family": family,
            "records_before": count,
            "records_after": count + len(slices),
            "payload_offset_before": old_payload,
            "payload_offset_after": old_payload + shift,
            "growth_bytes": shift,
            "region0_end_before": current_end,
            "region0_end_after_shift": shifted_end,
            "region0_free_after_shift": report["region0"]["capacity"] - shifted_end,
            "fits_region0": directory_fits,
        },
        "placements": placements,
        "all_fit": directory_fits and all(row["fits"] for row in placements),
    }


def place_slices(world: dict[str, Any], family: str, region: int,
                 slices: list[tuple[str, int]]) -> list[dict[str, Any]]:
    """Predecessor-shaped placement API, with directory reservation first."""
    return project(world, family, region, slices)["placements"]


def _world(count: int = 55, end: int = 64185, unique: int = 63,
           alignment: int = 32) -> dict[str, Any]:
    manifest = {
        "policy": {"payload_alignment": alignment, "max_slice_bytes": 1792,
                   "max_slices": 64},
        "catalog": {"slice_count": count},
        "slices": [{"region_id": 0, "source_address": 0x30000,
                    "file_size": end}],
        "overflow_storage": {"capacity": 2032, "used": 1892},
        "external_storage": {"bytes": 750, "owner": {"payload": {"capacity": 1622}}},
    }
    return {
        "medium": "synthetic", "sha256": {},
        "families": {f: PRE.family_report(manifest) for f in PRE.FAMILIES},
        "slice_count_unique": unique, "unique_catalog_slots_free": 64 - unique,
        "manifests": {f: deepcopy(manifest) for f in PRE.FAMILIES},
    }


def _regression_checks() -> None:
    world = _world()
    untouched = deepcopy(world)
    old = PRE.place_slices(world, "session", 0, [("too-big", 1089)])[0]
    assert old["fits"] and old["aligned_start"] == 64192
    exact = project(world, "session", 0, [("exact", 1088)])
    row = exact["placements"][0]
    assert row["aligned_start"] == 64448, "directory step omitted or wrong"
    assert row["end"] == 65536 and row["remaining_bytes"] == 0 and exact["all_fit"]
    over = project(world, "session", 0, [("over", 1089)])
    assert not over["all_fit"] and not over["placements"][0]["fits_region"]
    assert over["placements"][0]["end"] == 65537
    assert exact["directory"]["growth_bytes"] == 256
    assert world == untouched, "projection mutated predecessor world"
    assert PRE.place_slices(world, "session", 0, [("too-big", 1089)])[0] == old

    # No boundary, the next boundary, and multiple-page growth.
    assert directory_step(54, 1) == 0
    assert directory_step(55, 0) == 0
    assert directory_step(55, 1) == 256
    assert directory_step(56, 7) == 0
    assert directory_step(63, 1) == 256
    assert directory_step(55, 9) == 512
    unchanged = _world(54, 62001, 54)
    assert place_slices(unchanged, "session", 0, [("small", 17)]) == \
        PRE.place_slices(unchanged, "session", 0, [("small", 17)])
    # Reserve for the final count, not independently per requested slice.
    batch = project(_world(54, 62001, 54), "session", 0, [("a", 31), ("b", 33)])
    assert batch["directory"]["records_after"] == 56
    assert [p["aligned_start"] for p in batch["placements"]] == [62272, 62304]
    assert batch["all_fit"]
    assert project(_world(63, 62001, 63), "session", 0, [("last", 1)])["directory"]["growth_bytes"] == 256
    boot = project(_world(alignment=256), "boot", 0, [("b", 1024)])
    assert boot["placements"][0]["aligned_start"] == 64512 and boot["all_fit"]
    for region, start in ((1, 1920), (2, 768)):
        good = project(world, "session", region, [("external", 8)])
        assert good["placements"][0]["aligned_start"] == start and good["all_fit"]
        blocked = project(_world(end=65400), "session", region, [("external", 8)])
        assert not blocked["all_fit"] and not blocked["directory"]["fits_region0"]
    assert not project(_world(unique=64), "session", 0, [("no-slot", 1)])["all_fit"]
    assert not project(_world(end=60000), "session", 0, [("oversize", 1793)])["all_fit"]
    empty = project(world, "session", 0, [])
    assert empty["directory"]["growth_bytes"] == 0 and empty["all_fit"]


def _packer_checks() -> None:
    # Independent oracle: pack synthetic bytes with the real format packer.
    # This is host-only memory packing; no compiler, linker, or product execution.
    def pack(lengths: list[int]) -> Any:
        slices = []
        for i, length in enumerate(lengths):
            name = f"test-{i}"
            spec = BANK.SliceSpec(i, name, f".lisp65_rt_test_{i}", f"s{i}",
                                  f"e{i}", f"entry{i}",
                                  BANK.FLAG_RUNTIME | BANK.FLAG_REUSABLE, 1, 0,
                                  f"entry{i}")
            slices.append(BANK.ExtractedSlice(spec, 0xC200, 0xC200 + length,
                                               0xC200, bytes([i]) * length))
        return BANK.build_region_images(
            slices, profile_build_id=1, expected_vma=0xC200,
            max_slice_bytes=1792, format_version=4, payload_alignment=32)
    lengths = [1152] * 54 + [185]
    before, _, parsed = pack(lengths)
    assert len(before) == 64185 and parsed.payload_offset == 1792
    after, _, parsed = pack(lengths + [1088])
    row = place_slices(_world(), "session", 0, [("exact", 1088)])[0]
    assert len(after) == row["end"] == 65536
    assert parsed.payload_offset == 2048
    assert parsed.slices[-1].file_offset == row["aligned_start"] == 64448
    try:
        pack(lengths + [1089])
    except BANK.OverlayBankError as error:
        assert error.code == "bank-overflow", error
    else:
        raise AssertionError("packer admitted one-byte overflow")


def selftest() -> None:
    check_predecessor()
    PRE.selftest()
    _regression_checks()
    _packer_checks()
    # Prove the positive tests reject omitted/incorrect directory accounting.
    global directory_step
    original = directory_step
    mutants = {
        "omitted-step": lambda count, additions: 0,
        "per-record-no-page-rounding": lambda count, additions: additions * 32,
        "double-step": lambda count, additions: 2 * original(count, additions),
    }
    for name, mutant in mutants.items():
        directory_step = mutant
        try:
            try:
                _regression_checks()
            except AssertionError:
                print(f"mutation {name}: rejected")
            else:
                raise AssertionError(f"mutation survived: {name}")
        finally:
            directory_step = original
    print("slice_capacity_preflight_20260924: selftest OK")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--medium", type=Path, default=PRE.DEFAULT_MEDIUM)
    parser.add_argument("--slice", dest="slices", action="append", default=[],
                        metavar="NAME:BYTES")
    parser.add_argument("--family", choices=PRE.FAMILIES, default="session")
    parser.add_argument("--region", type=int, choices=(0, 1, 2), default=0)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    try:
        check_predecessor()
        if args.selftest:
            selftest()
            return 0
        world = PRE.load_world(args.medium)
        slices = [PRE.parse_slice_arg(s) for s in args.slices]
        receipt = project(world, args.family, args.region, slices)
        # Keep the predecessor's stdout and receipt bytes exactly as produced.
        legacy_args = ["--medium", str(args.medium), "--family", args.family,
                       "--region", str(args.region), "--out", str(args.out)]
        for raw in args.slices:
            legacy_args.extend(["--slice", raw])
        PRE.main(legacy_args)
        (args.out / RECEIPT_NAME).write_text(
            PRE.json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        directory = receipt["directory"]
        print(f"20260924 directory: {directory['records_before']} -> "
              f"{directory['records_after']} records; +{directory['growth_bytes']} bytes")
        for row in receipt["placements"]:
            print(f"20260924 slice {row['name']}: start={row['aligned_start']} "
                  f"end={row['end']} fits={row['fits']}")
        return 0 if receipt["all_fit"] else 1
    except PRE.PreflightError as error:
        print(f"slice_capacity_preflight_20260924: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
