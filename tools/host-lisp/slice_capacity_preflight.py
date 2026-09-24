#!/usr/bin/env python3
"""Preflight: state per-family payload capacity for a runtime-overlay world.

Standing rule (docs/reference/parked-items-register.md, "Preflight gap:
slice cards must state payload capacity"): a card that adds a slice must
state, before it links, the free bytes per region after alignment and the
catalog-slot remainder. The boot-time name-index card's fourth Seed found
the Session overflow bank full because an earlier preflight only checked
catalog slots (64 of 64), never the region-0 payload byte budget.

This tool reads the Session and Boot runtime-overlay manifests of an
accepted world (``runtime-overlays-{session,boot}-final.json``) plus that
world's ``resolved-profile.txt`` (which carries the product's
``slice_count_unique`` -- see ``c2_product_substitution_link.py``'s
``UNIQUE_SLICE_COUNT`` / ``assert_unique_public_specs()``, which dedups the
two family-local verifier names shared by both catalogs and nothing else),
and reports:

- per family: catalog payload alignment, slice count, catalog slots free
  against the per-family ``max_slices`` cap;
- one shared "unique catalog slots free" figure against the 64-slot hard
  cap (``LISP65_RUNTIME_OVERLAY_HARD_MAX_SLICES`` /
  ``runtime_overlay_bank.MAX_SLICES``), derived from ``slice_count_unique``;
- per family, per region (0: the resident bank, sized against the fixed
  64 KiB bank; 1: the Bank-5 overflow window; 2: the external/attic
  overflow store) the occupied end and free bytes;
- for ``--slice NAME:BYTES`` (repeatable), the placement of new slices in
  intake order into one family's region 0, rounding each start up to that
  family's payload alignment, and whether the requested slices fit.

Region-0 usage is derived the same way the accepted evidence states it
(``docs/planning/boot-name-index-final-report.md``, "Session region 0 used
(of 65,536)"): each region-0 slice's ``source_address`` is bank-relative
(``source_address % BANK_SIZE``), and the region's "used" bound is the
highest ``offset + file_size`` over its slices. A placed slice's start is
its family's alignment applied to the running end, exactly as the boot
name index card's two tail slices (10a/10b, 1,671 / 1,755 bytes) rounded
onto the Session-bank capacity world's free 5,362 bytes to leave 1,893.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MEDIUM = ROOT / "build/boot-name-index-seed-medium-r3/materialized"
DEFAULT_OUT = ROOT / "build/slice-capacity-preflight-r1"

FAMILIES = ("session", "boot")
HARD_MAX_SLICES = 64
BANK_SIZE = 0x10000  # region 0: one full resident bank, per runtime_overlay_bank.BANK_SIZE


class PreflightError(RuntimeError):
    """The manifests, the resolved profile, or a requested slice are unusable."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PreflightError(f"missing manifest: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_resolved_profile(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise PreflightError(f"missing resolved profile: {path}")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        # Several keys (e.g. storage_owner_manifest_sha256) repeat later in
        # the file with the same value; the first occurrence is authoritative
        # for the keys this tool reads.
        values.setdefault(key, value)
    return values


def align_up(value: int, alignment: int) -> int:
    if alignment <= 0:
        raise PreflightError(f"non-positive alignment: {alignment}")
    return ((value + alignment - 1) // alignment) * alignment


def region0_used(manifest: dict[str, Any]) -> int:
    used = 0
    for slice_ in manifest.get("slices", []):
        if slice_.get("region_id") != 0:
            continue
        offset = slice_["source_address"] % BANK_SIZE
        end = offset + slice_["file_size"]
        used = max(used, end)
    return used


def region1_state(manifest: dict[str, Any]) -> dict[str, int] | None:
    overflow = manifest.get("overflow_storage")
    if not overflow:
        return None
    capacity = overflow["capacity"]
    used = overflow["used"]
    return {"capacity": capacity, "used": used, "free": capacity - used}


def region2_state(manifest: dict[str, Any]) -> dict[str, int] | None:
    external = manifest.get("external_storage")
    if not external:
        return None
    payload = external["owner"]["payload"]
    capacity = payload["capacity"]
    used = external["bytes"]
    return {"capacity": capacity, "used": used, "free": capacity - used}


def family_report(manifest: dict[str, Any]) -> dict[str, Any]:
    policy = manifest["policy"]
    catalog = manifest["catalog"]
    max_slices = policy.get("max_slices", HARD_MAX_SLICES)
    slice_count = catalog["slice_count"]
    used0 = region0_used(manifest)
    return {
        "payload_alignment": policy["payload_alignment"],
        "max_slice_bytes": policy["max_slice_bytes"],
        "max_slices": max_slices,
        "slice_count": slice_count,
        "catalog_slots_free": max_slices - slice_count,
        "region0": {"used": used0, "capacity": BANK_SIZE, "free": BANK_SIZE - used0},
        "region1": region1_state(manifest),
        "region2": region2_state(manifest),
    }


def load_world(medium: Path) -> dict[str, Any]:
    manifests = {}
    shas = {}
    for family in FAMILIES:
        path = medium / f"runtime-overlays-{family}-final.json"
        manifests[family] = load_json(path)
        shas[f"{family}_manifest"] = sha256_file(path)
    profile_path = medium / "resolved-profile.txt"
    profile = load_resolved_profile(profile_path)
    shas["resolved_profile"] = sha256_file(profile_path)
    if "slice_count_unique" not in profile:
        raise PreflightError(f"resolved profile lacks slice_count_unique: {profile_path}")
    slice_count_unique = int(profile["slice_count_unique"])
    reports = {family: family_report(manifests[family]) for family in FAMILIES}
    for family in FAMILIES:
        key = f"{family}_family_slice_count"
        if key in profile and int(profile[key]) != reports[family]["slice_count"]:
            raise PreflightError(
                f"resolved profile {key}={profile[key]} disagrees with manifest "
                f"slice_count={reports[family]['slice_count']}")
    return {
        "medium": str(medium),
        "sha256": shas,
        "families": reports,
        "slice_count_unique": slice_count_unique,
        "unique_catalog_slots_free": HARD_MAX_SLICES - slice_count_unique,
        "manifests": manifests,
    }


def parse_slice_arg(raw: str) -> tuple[str, int]:
    if ":" not in raw:
        raise PreflightError(f"--slice must be NAME:BYTES, got {raw!r}")
    name, _, bytes_text = raw.rpartition(":")
    if not name:
        raise PreflightError(f"--slice must be NAME:BYTES, got {raw!r}")
    try:
        num_bytes = int(bytes_text)
    except ValueError as exc:
        raise PreflightError(f"--slice byte count is not an integer: {raw!r}") from exc
    if num_bytes <= 0:
        raise PreflightError(f"--slice byte count must be positive: {raw!r}")
    return name, num_bytes


def place_slices(world: dict[str, Any], family: str, region: int,
                  slices: list[tuple[str, int]]) -> list[dict[str, Any]]:
    if family not in FAMILIES:
        raise PreflightError(f"unknown family: {family}")
    report = world["families"][family]
    if region == 0:
        capacity = report["region0"]["capacity"]
        current_end = report["region0"]["used"]
    elif region in (1, 2):
        region_state = report[f"region{region}"]
        if region_state is None:
            raise PreflightError(f"family {family!r} has no region {region}")
        capacity = region_state["capacity"]
        current_end = region_state["used"]
    else:
        raise PreflightError(f"unknown region: {region}")

    alignment = report["payload_alignment"]
    max_slice_bytes = report["max_slice_bytes"]
    slot_count = report["slice_count"]
    unique_count = world["slice_count_unique"]

    placements = []
    for name, num_bytes in slices:
        slot_available = unique_count + 1 <= HARD_MAX_SLICES
        oversize = num_bytes > max_slice_bytes
        aligned_start = align_up(current_end, alignment)
        end = aligned_start + num_bytes
        fits_region = end <= capacity
        fits = slot_available and fits_region and not oversize
        if fits:
            remaining = capacity - end
            slot = slot_count
            current_end = end
            slot_count += 1
            unique_count += 1
        else:
            remaining = capacity - current_end
            slot = None
        placements.append({
            "name": name,
            "requested_bytes": num_bytes,
            "family": family,
            "region": region,
            "alignment": alignment,
            "aligned_start": aligned_start,
            "end": end,
            "fits": fits,
            "fits_region": fits_region,
            "slot_available": slot_available,
            "oversize": oversize,
            "remaining_bytes": remaining,
            "slot": slot,
        })
    return placements


def format_report(world: dict[str, Any], placements: list[dict[str, Any]]) -> str:
    lines = [f"medium: {world['medium']}"]
    for family in FAMILIES:
        report = world["families"][family]
        lines.append(
            f"{family}: alignment={report['payload_alignment']} "
            f"slices={report['slice_count']} "
            f"catalog_slots_free={report['catalog_slots_free']}/{report['max_slices']} "
            f"region0 end={report['region0']['used']} free={report['region0']['free']}")
        for region in (1, 2):
            state = report[f"region{region}"]
            if state is None:
                lines.append(f"  region{region}: absent")
            else:
                lines.append(
                    f"  region{region}: end={state['used']} "
                    f"free={state['free']} capacity={state['capacity']}")
    lines.append(
        f"unique catalog slots free: {world['unique_catalog_slots_free']}/{HARD_MAX_SLICES} "
        f"(slice_count_unique={world['slice_count_unique']})")
    for placement in placements:
        verdict = "fits" if placement["fits"] else "DOES NOT FIT"
        lines.append(
            f"slice {placement['name']}: {placement['requested_bytes']}B -> "
            f"{placement['family']}/region{placement['region']} "
            f"start={placement['aligned_start']} end={placement['end']} "
            f"{verdict} remaining={placement['remaining_bytes']} slot={placement['slot']}")
    return "\n".join(lines)


def build_receipt(world: dict[str, Any], placements: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "format": "lisp65-slice-capacity-preflight-v1",
        "medium": world["medium"],
        "sha256": world["sha256"],
        "families": {
            family: {k: v for k, v in report.items()}
            for family, report in world["families"].items()
        },
        "slice_count_unique": world["slice_count_unique"],
        "unique_catalog_slots_free": world["unique_catalog_slots_free"],
        "hard_max_slices": HARD_MAX_SLICES,
        "placements": placements,
        "all_fit": all(p["fits"] for p in placements),
    }


# --------------------------------------------------------------------------
# Selftest: synthetic manifests, no dependency on any build/ world.
# --------------------------------------------------------------------------

def _write_manifest(directory: Path, family: str, alignment: int,
                     slice_count: int, region0_end: int,
                     region1: dict[str, int] | None = None,
                     region2: dict[str, int] | None = None) -> None:
    slices = []
    if region0_end:
        slices.append({
            "region_id": 0,
            "source_address": 3 * BANK_SIZE,  # bank 3, offset 0
            "file_size": region0_end,
            "name": f"{family}-fill",
        })
    manifest: dict[str, Any] = {
        "lifetime_family": family,
        "policy": {
            "payload_alignment": alignment,
            "max_slice_bytes": 1792,
            "max_slices": 64,
        },
        "catalog": {"slice_count": slice_count},
        "slices": slices,
    }
    if region1 is not None:
        manifest["overflow_storage"] = {
            "capacity": region1["capacity"], "used": region1["used"]}
    if region2 is not None:
        manifest["external_storage"] = {
            "bytes": region2["used"],
            "owner": {"payload": {"capacity": region2["capacity"]}},
        }
    path = directory / f"runtime-overlays-{family}-final.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")


def _write_profile(directory: Path, slice_count_unique: int,
                    session_count: int, boot_count: int) -> None:
    text = (
        f"slice_count_unique={slice_count_unique}\n"
        f"boot_family_slice_count={boot_count}\n"
        f"session_family_slice_count={session_count}\n"
    )
    (directory / "resolved-profile.txt").write_text(text, encoding="utf-8")


def _make_world(tmp: Path, *, session_alignment: int, session_end: int,
                 session_count: int, slice_count_unique: int) -> dict[str, Any]:
    _write_manifest(tmp, "session", session_alignment, session_count, session_end)
    _write_manifest(tmp, "boot", 256, 12, 4000)
    _write_profile(tmp, slice_count_unique, session_count, 12)
    return load_world(tmp)


def selftest() -> None:
    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)

        # Case: exact fit. Region 0 has exactly enough room after alignment.
        world = _make_world(tmp, session_alignment=32, session_end=BANK_SIZE - 32,
                             session_count=10, slice_count_unique=20)
        placements = place_slices(world, "session", 0, [("exact", 32)])
        assert placements[0]["fits"], placements
        assert placements[0]["remaining_bytes"] == 0, placements

        # Case: one byte too many overflows region 0 by exactly one byte.
        placements = place_slices(world, "session", 0, [("over", 33)])
        assert not placements[0]["fits"], placements
        assert not placements[0]["fits_region"], placements
        assert placements[0]["slot"] is None, placements

        # Case: no catalog slot free (unique count already at the hard cap).
        world_full = _make_world(tmp, session_alignment=32, session_end=100,
                                  session_count=10, slice_count_unique=64)
        placements = place_slices(world_full, "session", 0, [("no-slot", 8)])
        assert not placements[0]["fits"], placements
        assert not placements[0]["slot_available"], placements
        assert placements[0]["fits_region"], placements  # region has room; slot is the blocker

        # Case: alignment 256 (boot) rounds a small slice up further than 32 (session).
        world_align = _make_world(tmp, session_alignment=32, session_end=100,
                                   session_count=10, slice_count_unique=20)
        session_placement = place_slices(world_align, "session", 0, [("tiny", 8)])[0]
        boot_placement = place_slices(world_align, "boot", 0, [("tiny", 8)])[0]
        assert session_placement["aligned_start"] == align_up(100, 32) == 128
        assert boot_placement["aligned_start"] == align_up(4000, 256) == 4096
        assert session_placement["aligned_start"] != boot_placement["aligned_start"]

        # region1/region2 presence and free-byte arithmetic.
        _write_manifest(tmp, "session", 32, 10, 100,
                         region1={"capacity": 2032, "used": 1892},
                         region2={"capacity": 1622, "used": 750})
        world_regions = load_world(tmp)
        assert world_regions["families"]["session"]["region1"]["free"] == 140
        assert world_regions["families"]["session"]["region2"]["free"] == 872

    print("slice_capacity_preflight: selftest OK")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--medium", type=Path, default=DEFAULT_MEDIUM,
                         help="directory holding the accepted world's manifests "
                              "and resolved-profile.txt")
    parser.add_argument("--slice", dest="slices", action="append", default=[],
                         metavar="NAME:BYTES",
                         help="a new slice to place, in intake order (repeatable)")
    parser.add_argument("--family", choices=FAMILIES, default="session",
                         help="family whose catalog/region receives --slice entries")
    parser.add_argument("--region", type=int, default=0, choices=(0, 1, 2),
                         help="region that receives --slice entries")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                         help="directory to write the receipt JSON into")
    parser.add_argument("--selftest", action="store_true",
                         help="run the synthetic-manifest selftest and exit")
    args = parser.parse_args(argv)

    if args.selftest:
        selftest()
        return 0

    try:
        world = load_world(args.medium)
        slices = [parse_slice_arg(raw) for raw in args.slices]
        placements = place_slices(world, args.family, args.region, slices)
    except PreflightError as exc:
        print(f"slice_capacity_preflight: {exc}", file=sys.stderr)
        return 1

    print(format_report(world, placements))

    args.out.mkdir(parents=True, exist_ok=True)
    receipt = build_receipt(world, placements)
    (args.out / "slice-capacity-preflight.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if placements and not all(p["fits"] for p in placements):
        return 1
    if slices and not placements:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
