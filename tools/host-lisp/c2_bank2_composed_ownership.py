#!/usr/bin/env python3
"""Derive and prove composed physical Bank-2 ownership from final artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from elf_truth import ElfTruth


BANK2_START = 0x20000
BANK2_END = 0x30000
MAPPED = (
    (".lisp65_c2_mapped_far_service",
     "__lisp65_c2_mapped_far_service"),
    (".lisp65_c2_mapped_product_cold",
     "__lisp65_c2_mapped_product_cold"),
)


class OwnershipError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise OwnershipError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _gaps(rows: list[dict[str, Any]]) -> list[dict[str, int]]:
    cursor = BANK2_START
    result: list[dict[str, int]] = []
    for row in sorted(rows, key=lambda item: int(item["start"])):
        start = int(row["start"])
        end = int(row["end_exclusive"])
        if cursor < start:
            result.append({"start": cursor, "end_exclusive": start,
                           "bytes": start - cursor})
        cursor = max(cursor, end)
    if cursor < BANK2_END:
        result.append({"start": cursor, "end_exclusive": BANK2_END,
                       "bytes": BANK2_END - cursor})
    return result


def derive(*, elf: Path, plane: Path, readobj: Path,
           static_images: list[dict[str, Any]] | None = None,
           expected_vmas: dict[str, int] | None = None,
           placement_policy: str = "bank2-top-derived") -> dict[str, Any]:
    """Return the complete, final-image-derived Bank-2 ownership map."""
    raw_plane = plane.read_bytes()
    static_end = BANK2_START + len(raw_plane)
    require(BANK2_START < static_end <= BANK2_END,
            "static Bank-2 plane escaped its owning bank")
    truth = ElfTruth.read(elf, llvm_readobj=readobj, include_section_data=True)

    images: list[dict[str, Any]] = []
    if static_images is None:
        images.append({"owner": "bank2-static-code-plane",
                       "start": BANK2_START, "end_exclusive": static_end,
                       "bytes": len(raw_plane), "sha256": sha(raw_plane),
                       "authority": "candidate-static-plane"})
    else:
        cursor = BANK2_START
        for source in static_images:
            count = int(source["bytes"])
            images.append({"owner": str(source["name"]), "start": cursor,
                           "end_exclusive": cursor + count, "bytes": count,
                           "authority": source.get("authority", "manifest")})
            cursor += count
        require(cursor == static_end,
                "static image owners do not cover the candidate plane")

    mapped: list[dict[str, Any]] = []
    for section_name, prefix in MAPPED:
        section = truth.section(section_name)
        body = truth.section_bytes(section_name)
        start = truth.symbol(prefix + "_load_start").value
        end = truth.symbol(prefix + "_load_end").value
        require(end - start == section.bytes == len(body) > 0,
                f"mapped load extent differs from section: {section_name}")
        if expected_vmas is not None:
            require(section.address == expected_vmas[section_name],
                    f"mapped tenant VMA moved: {section_name}")
        mapped.append({"owner": section_name, "start": start,
                       "end_exclusive": end, "bytes": len(body),
                       "VMA": section.address, "sha256": sha(body),
                       "authority": "final-ELF LOADADDR symbols"})

    reserved: list[dict[str, Any]] = []
    far, cold = mapped
    if placement_policy == "map-page-top-derived":
        offsets = {int(row["start"]) - int(row["VMA"]) for row in mapped}
        require(len(offsets) == 1, "mapped tenants do not share one MAP offset")
        shared_offset = offsets.pop()
        require(shared_offset >= 0 and shared_offset & 0xff == 0,
                "mapped tenant offset is not page-encodable")
        require(int(far["end_exclusive"]) <= int(cold["start"])
                and int(cold["end_exclusive"]) <= BANK2_END,
                "page-congruent mapped tenants overlap or escape Bank-2")
        reserved = [{
            "owner": "mapped-tenant-congruence-gap",
            "start": int(far["end_exclusive"]),
            "end_exclusive": int(cold["start"]),
            "bytes": int(cold["start"]) - int(far["end_exclusive"]),
            "authority": "final-ELF VMA gap under shared MAP offset",
        }, {
            "owner": "mapped-tenant-bank-end-reserve",
            "start": int(cold["end_exclusive"]),
            "end_exclusive": BANK2_END,
            "bytes": BANK2_END - int(cold["end_exclusive"]),
            "authority": "maximal page-aligned offset and Bank-2 end",
        }]
        require(all(row["bytes"] > 0 for row in reserved),
                "named MAP placement reserve vanished")
    elif placement_policy not in ("bank2-top-derived", "fixed-contract"):
        raise OwnershipError(f"unknown placement policy: {placement_policy}")

    owners = [*images, *mapped, *reserved]
    ordered = sorted(owners, key=lambda item: (int(item["start"]),
                                               int(item["end_exclusive"])))
    overlaps: list[dict[str, Any]] = []
    for index, left in enumerate(ordered):
        require(BANK2_START <= int(left["start"])
                < int(left["end_exclusive"]) <= BANK2_END,
                f"Bank-2 owner escaped bank: {left['owner']}")
        for right in ordered[index + 1:]:
            start = max(int(left["start"]), int(right["start"]))
            end = min(int(left["end_exclusive"]), int(right["end_exclusive"]))
            if start < end:
                overlaps.append({"left": left["owner"],
                                 "right": right["owner"], "start": start,
                                 "end_exclusive": end, "bytes": end - start})
    require(not overlaps, "composed Bank-2 owners overlap")
    if placement_policy == "bank2-top-derived":
        require(int(cold["end_exclusive"]) == BANK2_END
                and int(far["end_exclusive"]) == int(cold["start"]),
                "mapped tenants are not tightly packed from the Bank-2 end")

    gaps = _gaps(owners)
    require(gaps, "composed Bank-2 map has no free interval")
    largest = max(gaps, key=lambda row: row["bytes"])
    return {
        "status": "PASS: COMPOSED BANK2 OWNERS ARE DISJOINT",
        "bank": {"start": BANK2_START, "end_exclusive": BANK2_END,
                 "bytes": BANK2_END - BANK2_START},
        "static_plane": {"start": BANK2_START,
                         "end_exclusive": static_end,
                         "bytes": len(raw_plane), "sha256": sha(raw_plane)},
        "owners": owners, "mapped_tenants": mapped,
        "reserved_owners": reserved,
        "overlaps": overlaps, "free_intervals": gaps,
        "aggregate_free_bytes": sum(row["bytes"] for row in gaps),
        "largest_contiguous_hole": largest,
        "anchor": ({"kind": "map-page-top-derived",
                    "shared_offset": shared_offset,
                    "offset_mod_0x100": shared_offset & 0xff,
                    "congruence_gap_is_owned": True,
                    "bank_end_reserve_is_owned": True}
                   if placement_policy == "map-page-top-derived" else
                   ({"kind": "fixed-contract",
                     "mapped_load_addresses": {
                         str(row["owner"]): int(row["start"])
                         for row in mapped},
                     "authority": "final-ELF LOADADDR symbols",
                     "disjointness_is_derived": True}
                    if placement_policy == "fixed-contract" else
                   {"kind": "bank2-top-derived",
                    "product_cold_end_equals_bank_end": True,
                    "far_service_end_equals_product_cold_start": True})),
        "capacity_rule": ("placement capacity is the largest contiguous hole; "
                          "aggregate free bytes are informational only"),
        "copy_source_authority": "final-ELF LOADADDR symbols",
        "mutations": {
            "static_plane_overlaps_far_service": "rejected",
            "mapped_tenant_missing_from_owner_union": "rejected",
            **({"non-page-congruent-offset": "rejected",
                "tenant-offset-divergence": "rejected",
                "unnamed-congruence-gap": "rejected",
                "unnamed-bank-end-reserve": "rejected"}
               if placement_policy == "map-page-top-derived" else
               ({"fixed_contract_overlap": "rejected",
                 "fixed_contract_owner_missing": "rejected"}
               if placement_policy == "fixed-contract" else
               {"product_cold_not_anchored_to_bank_end": "rejected",
                "far_service_not_adjacent_to_product_cold": "rejected"})),
        },
    }
