#!/usr/bin/env python3
"""Fail-closed inventory for the Workbench resident Bank-0 island."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ELF = (
    ROOT
    / "build"
    / "products"
    / "workbench"
    / "overlay-stack-guard"
    / "lisp65-workbench-overlay-linked.prg.elf"
)
DEFAULT_POLICY = ROOT / "config" / "bank0-island-workbench.json"
DEFAULT_JSON = ROOT / "build" / "reports" / "workbench" / "bank0-island.json"
DEFAULT_TEXT = ROOT / "build" / "reports" / "workbench" / "bank0-island.txt"
DEFAULT_NM = ROOT / "tools" / "llvm-mos" / "bin" / "llvm-nm"
DEFAULT_SIZE = ROOT / "tools" / "llvm-mos" / "bin" / "llvm-size"

POLICY_SCHEMA = "lisp65-bank0-island-policy-v1"
REPORT_SCHEMA = "lisp65-bank0-island-report-v2"
PINNED_SCREEN = {
    "base": 0x0800,
    "columns": 80,
    "rows": 50,
    "bytes_per_cell": 1,
    "end_exclusive": 0x17A0,
    "seam": False,
}
PINNED_ISLAND = {"start": 0x1800, "end_exclusive": 0x2000}
PINNED_IMMUTABLE_BYTES = 1108
PINNED_ANNEX = {
    "section": ".lisp65_resident_island_annex",
    "start_symbol": "__lisp65_resident_island_annex_start",
    "end_symbol": "__lisp65_resident_island_annex_end",
    "bytes": 260,
    "alignment": 2,
}
PINNED_ANNEX_SYMBOLS = (
    ("lisp65_rootstack_canary_before", 0, 2),
    ("gc_rootstack", 2, 256),
    ("lisp65_rootstack_canary_after", 258, 2),
)
PINNED_MIN_RESERVE = 672
SCREEN_SEAM_NOTE = (
    "SEAM mode is outside this contract and requires explicit screen relocation "
    "before the resident island may be used."
)
_NM_RE = re.compile(r"^\s*([0-9]+)\s+([0-9]+)\s+(\S)\s+(.+?)\s*$")
_LTO_SUFFIX_RE = re.compile(r"\.\d+$")


def _parse_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not an integer")
    if isinstance(value, int):
        return value
    return int(str(value), 0)


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_tool(path: Path, arguments: list[str]) -> str:
    return subprocess.check_output(
        [str(path), *arguments], text=True, stderr=subprocess.STDOUT
    )


def _parse_size_output(text: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        fields = raw.split()
        if len(fields) < 3 or not fields[0].startswith("."):
            continue
        try:
            size = int(fields[1], 10)
            address = int(fields[2], 10)
        except ValueError:
            continue
        name = fields[0]
        if name in seen:
            raise ValueError("duplicate ELF section: %s" % name)
        seen.add(name)
        sections.append({"name": name, "address": address, "size": size})
    if not sections:
        raise ValueError("llvm-size output contains no sections")
    return sorted(sections, key=lambda item: (item["address"], item["name"]))


def _parse_nm_output(text: str) -> list[dict[str, Any]]:
    symbols = []
    for raw in text.splitlines():
        match = _NM_RE.match(raw)
        if not match:
            continue
        address, size, symbol_type, name = match.groups()
        symbols.append(
            {
                "name": name,
                "canonical_name": _LTO_SUFFIX_RE.sub("", name),
                "type": symbol_type,
                "address": int(address, 10),
                "size": int(size, 10),
            }
        )
    symbols.sort(key=lambda item: (item["address"], item["size"], item["name"]))
    return symbols


def _validate_policy(policy: dict[str, Any]) -> None:
    expected_root = {
        "schema",
        "profile",
        "allowed_coordinator_classes",
        "screen_contract",
        "island",
        "allowed_symbols",
    }
    if set(policy) != expected_root:
        raise ValueError("policy has missing or unknown root fields")
    if policy.get("schema") != POLICY_SCHEMA:
        raise ValueError("unsupported policy schema: %r" % policy.get("schema"))
    if not isinstance(policy.get("profile"), str) or not policy["profile"]:
        raise ValueError("policy profile must be a non-empty string")
    classes = policy.get("allowed_coordinator_classes")
    if classes != ["l65m-coordinator", "batch-coordinator"]:
        raise ValueError(
            "allowed_coordinator_classes must pin only L65M and batch coordinators"
        )

    screen = policy.get("screen_contract")
    if not isinstance(screen, dict) or set(screen) != set(PINNED_SCREEN):
        raise ValueError("screen_contract fields do not match the pinned schema")
    for field in ("base", "columns", "rows", "bytes_per_cell", "end_exclusive"):
        _parse_int(screen[field])
    if not isinstance(screen["seam"], bool):
        raise ValueError("screen_contract seam must be boolean")

    island = policy.get("island")
    island_fields = {
        "section",
        "start",
        "end_exclusive",
        "boundary_symbols",
        "allowed_symbol_types",
        "max_unattributed_bytes",
    }
    if not isinstance(island, dict) or set(island) != island_fields:
        raise ValueError("island fields do not match the pinned schema")
    if not isinstance(island["section"], str) or not island["section"].startswith("."):
        raise ValueError("island section must be a non-empty ELF section name")
    _parse_int(island["start"])
    _parse_int(island["end_exclusive"])
    if _parse_int(island["max_unattributed_bytes"]) < 0:
        raise ValueError("max_unattributed_bytes must not be negative")
    boundaries = island["boundary_symbols"]
    if not isinstance(boundaries, dict) or set(boundaries) != {"start", "end"}:
        raise ValueError("boundary_symbols must define start and end")
    if not all(isinstance(value, str) and value for value in boundaries.values()):
        raise ValueError("boundary symbol names must be non-empty strings")
    types = island["allowed_symbol_types"]
    if (
        not isinstance(types, list)
        or not types
        or not all(isinstance(value, str) and len(value) == 1 for value in types)
        or len(types) != len(set(types))
    ):
        raise ValueError("allowed_symbol_types must be a unique non-empty type list")

    allowed = policy.get("allowed_symbols")
    if not isinstance(allowed, list):
        raise ValueError("allowed_symbols must be a list")
    names: set[str] = set()
    for item in allowed:
        if not isinstance(item, dict) or set(item) != {
            "name",
            "expected_allocations",
            "kind",
            "coordinator_class",
        }:
            raise ValueError(
                "allowed symbol entries must define name, count, kind, and coordinator class"
            )
        name = item["name"]
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("allowed symbol name is empty or duplicated: %r" % name)
        names.add(name)
        if _parse_int(item["expected_allocations"]) != 1:
            raise ValueError("allowed symbol %s must expect exactly one allocation" % name)
        if item["kind"] != "cold-coordinator":
            raise ValueError("allowed symbol %s is not a cold coordinator" % name)
        if item["coordinator_class"] not in classes:
            raise ValueError(
                "allowed symbol %s is outside the L65M/batch coordinator classes" % name
            )


def _violation(code: str, message: str, **details: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"code": code, "message": message}
    if details:
        item["details"] = details
    return item


def _contract_violations(policy: dict[str, Any]) -> list[dict[str, Any]]:
    violations = []
    screen = policy["screen_contract"]
    for field, expected in PINNED_SCREEN.items():
        actual = screen[field] if field == "seam" else _parse_int(screen[field])
        if actual != expected:
            violations.append(
                _violation(
                    "screen-contract-drift",
                    "non-SEAM screen contract moved from its pinned value",
                    field=field,
                    expected=expected,
                    actual=actual,
                )
            )
    derived_end = (
        _parse_int(screen["base"])
        + _parse_int(screen["columns"])
        * _parse_int(screen["rows"])
        * _parse_int(screen["bytes_per_cell"])
    )
    if derived_end != _parse_int(screen["end_exclusive"]):
        violations.append(
            _violation(
                "screen-contract-inconsistent",
                "screen geometry does not produce its declared end address",
                derived_end=derived_end,
                declared_end=_parse_int(screen["end_exclusive"]),
            )
        )
    if screen["seam"]:
        violations.append(
            _violation(
                "screen-seam-unsupported",
                SCREEN_SEAM_NOTE,
            )
        )

    island = policy["island"]
    for field, expected in PINNED_ISLAND.items():
        actual = _parse_int(island[field])
        if actual != expected:
            violations.append(
                _violation(
                    "island-boundary-drift",
                    "resident island boundary moved from its pinned address",
                    field=field,
                    expected=expected,
                    actual=actual,
                )
            )
    if _parse_int(screen["end_exclusive"]) > _parse_int(island["start"]):
        violations.append(
            _violation(
                "screen-island-overlap",
                "screen contract overlaps the resident island",
            )
        )
    return violations


def _physical_inventory(
    symbols: list[dict[str, Any]], start: int, end: int, section: dict[str, Any] | None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    physical: dict[tuple[int, int], dict[str, Any]] = {}
    boundary_crossers = []
    section_start = section["address"] if section else start
    section_end = section_start + section["size"] if section else start
    for symbol in symbols:
        if symbol["size"] <= 0:
            continue
        symbol_end = symbol["address"] + symbol["size"]
        overlaps_range = symbol["address"] < end and symbol_end > start
        in_section = (
            section is not None
            and section["size"] > 0
            and section_start <= symbol["address"]
            and symbol_end <= section_end
        )
        if not overlaps_range and not in_section:
            continue
        if symbol["address"] < start or symbol_end > end:
            boundary_crossers.append(symbol)
        key = (symbol["address"], symbol["size"])
        allocation = physical.setdefault(
            key,
            {
                "id": "0x%04x:%d" % key,
                "address": symbol["address"],
                "size": symbol["size"],
                "aliases": [],
            },
        )
        allocation["aliases"].append(
            {
                "name": symbol["name"],
                "canonical_name": symbol["canonical_name"],
                "type": symbol["type"],
            }
        )
    allocations = list(physical.values())
    for item in allocations:
        item["aliases"].sort(key=lambda alias: (alias["canonical_name"], alias["name"]))
    allocations.sort(key=lambda item: (item["address"], item["size"]))
    boundary_crossers.sort(key=lambda item: (item["address"], item["name"]))
    return allocations, boundary_crossers


def _build_report(
    sections: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    policy: dict[str, Any],
    inputs: dict[str, Any],
    require_annex: bool = False,
) -> dict[str, Any]:
    _validate_policy(policy)
    violations = _contract_violations(policy)
    island_policy = policy["island"]
    section_name = island_policy["section"]
    section_matches = [item for item in sections if item["name"] == section_name]
    section = section_matches[0] if len(section_matches) == 1 else None
    if not section_matches:
        violations.append(
            _violation("missing-section", "resident island ELF section is absent", section=section_name)
        )
    elif len(section_matches) != 1:
        violations.append(
            _violation("duplicate-section", "resident island ELF section is ambiguous", section=section_name)
        )

    start = _parse_int(island_policy["start"])
    end = _parse_int(island_policy["end_exclusive"])
    if section is not None:
        if section["address"] != start:
            violations.append(
                _violation(
                    "section-address-drift",
                    "resident island section does not start at its pinned address",
                    expected=start,
                    actual=section["address"],
                )
            )
        if section["address"] + section["size"] > end:
            violations.append(
                _violation(
                    "section-overflow",
                    "resident island section exceeds its pinned capacity",
                    section_end=section["address"] + section["size"],
                    capacity_end=end,
                )
            )
        if require_annex and section["size"] != PINNED_IMMUTABLE_BYTES:
            violations.append(
                _violation(
                    "immutable-size-drift",
                    "immutable resident-island payload changed from its frozen size",
                    expected=PINNED_IMMUTABLE_BYTES,
                    actual=section["size"],
                )
            )

    annex_matches = [
        item for item in sections if item["name"] == PINNED_ANNEX["section"]
    ]
    annex = annex_matches[0] if len(annex_matches) == 1 else None
    if len(annex_matches) > 1:
        violations.append(
            _violation(
                "duplicate-annex-section",
                "rootstack annex ELF section is ambiguous",
                section=PINNED_ANNEX["section"],
            )
        )
    elif annex is None and require_annex:
        violations.append(
            _violation(
                "missing-annex-section",
                "required rootstack annex ELF section is absent",
                section=PINNED_ANNEX["section"],
            )
        )

    immutable_end = section["address"] + section["size"] if section else start
    expected_annex_start = (
        immutable_end + PINNED_ANNEX["alignment"] - 1
    ) & ~(PINNED_ANNEX["alignment"] - 1)
    if annex is not None:
        if annex["address"] != expected_annex_start:
            violations.append(
                _violation(
                    "annex-address-drift",
                    "rootstack annex is not adjacent to the aligned immutable island",
                    expected=expected_annex_start,
                    actual=annex["address"],
                )
            )
        if annex["size"] != PINNED_ANNEX["bytes"]:
            violations.append(
                _violation(
                    "annex-size-drift",
                    "rootstack annex changed from its pinned 2+256+2-byte layout",
                    expected=PINNED_ANNEX["bytes"],
                    actual=annex["size"],
                )
            )
        if annex["address"] + annex["size"] > end:
            violations.append(
                _violation(
                    "annex-overflow",
                    "rootstack annex exceeds the pinned resident-island capacity",
                    annex_end=annex["address"] + annex["size"],
                    capacity_end=end,
                )
            )

    for other in sections:
        if other["name"] in (section_name, PINNED_ANNEX["section"]) or not other["size"]:
            continue
        other_end = other["address"] + other["size"]
        if other["address"] < end and other_end > start:
            violations.append(
                _violation(
                    "foreign-section-overlap",
                    "another ELF section overlaps the pinned resident island",
                    section=other["name"],
                    address=other["address"],
                    size=other["size"],
                )
            )

    symbol_by_name: dict[str, list[dict[str, Any]]] = {}
    for symbol in symbols:
        symbol_by_name.setdefault(symbol["name"], []).append(symbol)
    boundaries = island_policy["boundary_symbols"]
    for boundary, name in boundaries.items():
        matches = symbol_by_name.get(name, [])
        if len(matches) != 1:
            violations.append(
                _violation(
                    "boundary-symbol-missing" if not matches else "boundary-symbol-duplicate",
                    "resident island boundary symbol is absent or ambiguous",
                    boundary=boundary,
                    symbol=name,
                    matches=len(matches),
                )
            )
            continue
        expected = start if boundary == "start" else (
            section["address"] + section["size"] if section is not None else None
        )
        if expected is not None and matches[0]["address"] != expected:
            violations.append(
                _violation(
                    "boundary-symbol-drift",
                    "resident island boundary symbol has the wrong address",
                    boundary=boundary,
                    symbol=name,
                    expected=expected,
                    actual=matches[0]["address"],
                )
            )

    immutable_inventory_end = immutable_end if section is not None else start
    allocations, boundary_crossers = _physical_inventory(
        symbols, start, immutable_inventory_end, section
    )
    for symbol in boundary_crossers:
        violations.append(
            _violation(
                "symbol-boundary-crossing",
                "symbol crosses a pinned resident island boundary",
                symbol=symbol["name"],
                address=symbol["address"],
                size=symbol["size"],
            )
        )

    allowed = {item["name"]: item for item in policy["allowed_symbols"]}
    matches_by_name = {name: [] for name in allowed}
    allowed_types = set(island_policy["allowed_symbol_types"])
    for allocation in allocations:
        allocation["allowed"] = True
        allocation["policy_names"] = []
        for alias in allocation["aliases"]:
            canonical = alias["canonical_name"]
            if canonical in allowed:
                matches_by_name[canonical].append(allocation["id"])
                allocation["policy_names"].append(canonical)
            else:
                allocation["allowed"] = False
                violations.append(
                    _violation(
                        "extra-island-symbol",
                        "resident island contains an undeclared symbol",
                        allocation=allocation["id"],
                        symbol=canonical,
                    )
                )
            if alias["type"] not in allowed_types:
                allocation["allowed"] = False
                violations.append(
                    _violation(
                        "symbol-type-forbidden",
                        "resident island symbol is not executable coordinator code",
                        allocation=allocation["id"],
                        symbol=alias["name"],
                        symbol_type=alias["type"],
                    )
                )
        allocation["policy_names"] = sorted(set(allocation["policy_names"]))

    for name, spec in allowed.items():
        matches = sorted(set(matches_by_name[name]))
        expected = _parse_int(spec["expected_allocations"])
        if len(matches) != expected:
            violations.append(
                _violation(
                    "stale-allowlist-entry",
                    "declared cold coordinator has an unexpected allocation count",
                    symbol=name,
                    expected=expected,
                    actual=len(matches),
                )
            )

    if require_annex and len(allowed) != 8:
        violations.append(
            _violation(
                "immutable-coordinator-count-drift",
                "frozen immutable island must contain exactly eight coordinators",
                expected=8,
                actual=len(allowed),
            )
        )

    annex_allocations: list[dict[str, Any]] = []
    if annex is not None:
        annex_end = annex["address"] + annex["size"]
        annex_allocations, annex_crossers = _physical_inventory(
            symbols, annex["address"], annex_end, annex
        )
        for symbol in annex_crossers:
            violations.append(
                _violation(
                    "annex-symbol-boundary-crossing",
                    "symbol crosses a pinned rootstack-annex boundary",
                    symbol=symbol["name"],
                    address=symbol["address"],
                    size=symbol["size"],
                )
            )
        annex_by_canonical: dict[str, list[dict[str, Any]]] = {}
        for allocation in annex_allocations:
            for alias in allocation["aliases"]:
                annex_by_canonical.setdefault(alias["canonical_name"], []).append(allocation)
                if alias["canonical_name"] not in {
                    item[0] for item in PINNED_ANNEX_SYMBOLS
                }:
                    violations.append(
                        _violation(
                            "extra-annex-symbol",
                            "rootstack annex contains undeclared mutable data",
                            symbol=alias["canonical_name"],
                        )
                    )
                if alias["type"] not in {"b", "B"}:
                    violations.append(
                        _violation(
                            "annex-symbol-type-forbidden",
                            "rootstack annex may contain only NOLOAD data",
                            symbol=alias["name"],
                            symbol_type=alias["type"],
                        )
                    )
        for name, offset, size in PINNED_ANNEX_SYMBOLS:
            matches = annex_by_canonical.get(name, [])
            if len(matches) != 1:
                violations.append(
                    _violation(
                        "annex-symbol-count-drift",
                        "pinned rootstack-annex symbol is absent or ambiguous",
                        symbol=name,
                        expected=1,
                        actual=len(matches),
                    )
                )
                continue
            allocation = matches[0]
            expected_address = annex["address"] + offset
            if allocation["address"] != expected_address or allocation["size"] != size:
                violations.append(
                    _violation(
                        "annex-symbol-layout-drift",
                        "pinned rootstack-annex symbol moved or changed size",
                        symbol=name,
                        expected_address=expected_address,
                        actual_address=allocation["address"],
                        expected_size=size,
                        actual_size=allocation["size"],
                    )
                )
        annex_symbol_bytes = sum(item["size"] for item in annex_allocations)
        if annex_symbol_bytes != annex["size"]:
            violations.append(
                _violation(
                    "annex-symbol-coverage-drift",
                    "rootstack annex is not exactly covered by its three pinned objects",
                    section_bytes=annex["size"],
                    symbol_bytes=annex_symbol_bytes,
                )
            )

        for boundary, expected in (
            (PINNED_ANNEX["start_symbol"], annex["address"]),
            (PINNED_ANNEX["end_symbol"], annex_end),
        ):
            matches = symbol_by_name.get(boundary, [])
            if len(matches) != 1 or matches[0]["address"] != expected:
                violations.append(
                    _violation(
                        "annex-boundary-symbol-drift",
                        "rootstack annex boundary symbol is absent, ambiguous, or misplaced",
                        symbol=boundary,
                        expected=expected,
                        actual=[item["address"] for item in matches],
                    )
                )

        for left, right in zip(annex_allocations, annex_allocations[1:]):
            if left["address"] + left["size"] > right["address"]:
                violations.append(
                    _violation(
                        "annex-allocation-overlap",
                        "distinct rootstack-annex allocations overlap",
                        left=left["id"],
                        right=right["id"],
                    )
                )

    for left, right in zip(allocations, allocations[1:]):
        if left["address"] + left["size"] > right["address"]:
            violations.append(
                _violation(
                    "allocation-overlap",
                    "distinct island allocations overlap",
                    left=left["id"],
                    right=right["id"],
                )
            )

    attributed_ids = {
        (item["address"], item["size"])
        for item in (*allocations, *annex_allocations)
    }
    for symbol in symbols:
        if (
            symbol["size"] > 0
            and symbol["address"] < end
            and symbol["address"] + symbol["size"] > start
            and (symbol["address"], symbol["size"]) not in attributed_ids
        ):
            violations.append(
                _violation(
                    "unclassified-island-allocation",
                    "resident-island capacity contains data outside the two declared classes",
                    symbol=symbol["canonical_name"],
                    address=symbol["address"],
                    size=symbol["size"],
                )
            )

    section_bytes = section["size"] if section else 0
    symbol_bytes = sum(item["size"] for item in allocations)
    unattributed = section_bytes - symbol_bytes
    if unattributed < 0:
        violations.append(
            _violation(
                "symbol-coverage-overflow",
                "symbolized island bytes exceed the ELF section",
                section_bytes=section_bytes,
                symbol_bytes=symbol_bytes,
            )
        )
    elif unattributed > _parse_int(island_policy["max_unattributed_bytes"]):
        violations.append(
            _violation(
                "unattributed-bytes",
                "resident island contains too many bytes without symbols",
                actual=unattributed,
                maximum=_parse_int(island_policy["max_unattributed_bytes"]),
            )
        )

    annex_bytes = annex["size"] if annex else 0
    total_bytes = section_bytes + annex_bytes
    reserve_bytes = end - start - total_bytes
    if require_annex and reserve_bytes < PINNED_MIN_RESERVE:
        violations.append(
            _violation(
                "island-reserve-below-floor",
                "resident island plus rootstack annex consumed its pinned reserve",
                minimum=PINNED_MIN_RESERVE,
                actual=reserve_bytes,
            )
        )

    return {
        "schema": REPORT_SCHEMA,
        "status": "ok" if not violations else "violations",
        "profile": policy["profile"],
        "allowed_coordinator_classes": policy["allowed_coordinator_classes"],
        "inputs": inputs,
        "screen_contract": {
            **PINNED_SCREEN,
            "non_seam_max_address": PINNED_SCREEN["end_exclusive"] - 1,
            "seam_note": SCREEN_SEAM_NOTE,
        },
        "island_contract": {
            "section": section_name,
            "start": start,
            "end_exclusive": end,
            "capacity_bytes": end - start,
            "immutable_bytes": section_bytes,
            "annex_bytes": annex_bytes,
            "total_bytes": total_bytes,
            "reserve_bytes": reserve_bytes,
            "minimum_reserve_bytes": PINNED_MIN_RESERVE,
        },
        "annex_contract": {
            **PINNED_ANNEX,
            "required": require_annex,
            "present": annex is not None,
            "expected_symbols": [item[0] for item in PINNED_ANNEX_SYMBOLS],
        },
        "section": section,
        "annex_section": annex,
        "coverage": {
            "section_bytes": section_bytes,
            "symbolized_physical_bytes": symbol_bytes,
            "unattributed_bytes": unattributed,
            "physical_allocations": len(allocations),
            "declared_symbols": len(allowed),
        },
        "declared_coordinators": sorted(
            (
                {
                    "name": item["name"],
                    "coordinator_class": item["coordinator_class"],
                }
                for item in policy["allowed_symbols"]
            ),
            key=lambda item: item["name"],
        ),
        "allocations": allocations,
        "annex_allocations": annex_allocations,
        "violations": sorted(
            violations,
            key=lambda item: (
                item["code"],
                item["message"],
                json.dumps(item.get("details", {}), sort_keys=True),
            ),
        ),
    }


def _render_text(report: dict[str, Any]) -> str:
    screen = report["screen_contract"]
    island = report["island_contract"]
    lines = [
        "# lisp65 Bank-0 resident-island inventory",
        "schema=%s" % report["schema"],
        "status=%s" % report["status"],
        "profile=%s" % report["profile"],
        "allowed_coordinator_classes=%s"
        % ",".join(report["allowed_coordinator_classes"]),
        "screen_base=0x%04x" % screen["base"],
        "screen_geometry=%dx%dx%d" % (
            screen["columns"],
            screen["rows"],
            screen["bytes_per_cell"],
        ),
        "screen_seam=%s" % str(screen["seam"]).lower(),
        "screen_non_seam_max=0x%04x" % screen["non_seam_max_address"],
        "screen_seam_note=%s" % screen["seam_note"],
        "island_section=%s" % island["section"],
        "island_range=0x%04x..0x%04x" % (island["start"], island["end_exclusive"] - 1),
        "island_capacity_bytes=%d" % island["capacity_bytes"],
        "immutable_bytes=%d" % island["immutable_bytes"],
        "annex_bytes=%d" % island["annex_bytes"],
        "total_bytes=%d" % island["total_bytes"],
        "reserve_bytes=%d" % island["reserve_bytes"],
        "minimum_reserve_bytes=%d" % island["minimum_reserve_bytes"],
        "annex_section=%s" % report["annex_contract"]["section"],
        "annex_required=%s" % str(report["annex_contract"]["required"]).lower(),
        "annex_present=%s" % str(report["annex_contract"]["present"]).lower(),
        "symbolized_physical_bytes=%d" % report["coverage"]["symbolized_physical_bytes"],
        "unattributed_bytes=%d" % report["coverage"]["unattributed_bytes"],
        "",
        "Declared coordinators:",
        "class name",
    ]
    for declaration in report["declared_coordinators"]:
        lines.append(
            "%s %s"
            % (declaration["coordinator_class"], declaration["name"])
        )
    lines.extend([
        "",
        "Island allocations:",
        "address size allowed aliases",
    ])
    for allocation in report["allocations"]:
        aliases = ",".join(alias["name"] for alias in allocation["aliases"])
        lines.append(
            "0x%04x %4d %-7s %s"
            % (allocation["address"], allocation["size"], str(allocation["allowed"]).lower(), aliases)
        )
    lines.extend([
        "",
        "Rootstack annex allocations:",
        "address size aliases",
    ])
    for allocation in report["annex_allocations"]:
        aliases = ",".join(alias["name"] for alias in allocation["aliases"])
        lines.append("0x%04x %4d %s" % (allocation["address"], allocation["size"], aliases))
    lines.extend(["", "Violations:"])
    if not report["violations"]:
        lines.append("- none")
    else:
        for item in report["violations"]:
            details = json.dumps(item.get("details", {}), sort_keys=True, separators=(",", ":"))
            lines.append("- %s: %s %s" % (item["code"], item["message"], details))
    return "\n".join(lines) + "\n"


def _selftest_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "profile": "selftest",
        "allowed_coordinator_classes": ["l65m-coordinator", "batch-coordinator"],
        "screen_contract": dict(PINNED_SCREEN),
        "island": {
            "section": ".lisp65_resident_island",
            "start": PINNED_ISLAND["start"],
            "end_exclusive": PINNED_ISLAND["end_exclusive"],
            "boundary_symbols": {"start": "__island_start", "end": "__island_end"},
            "allowed_symbol_types": ["t", "T"],
            "max_unattributed_bytes": 0,
        },
        "allowed_symbols": [
            {
                "name": "cold_a",
                "expected_allocations": 1,
                "kind": "cold-coordinator",
                "coordinator_class": "l65m-coordinator",
            },
            {
                "name": "cold_b",
                "expected_allocations": 1,
                "kind": "cold-coordinator",
                "coordinator_class": "batch-coordinator",
            },
        ],
    }


def _codes(report: dict[str, Any]) -> set[str]:
    return {item["code"] for item in report["violations"]}


def _selftest() -> int:
    size_text = "fixture:\nsection size addr\n.lisp65_resident_island 96 6144\nTotal 96\n"
    nm_text = (
        "6144 0 A __island_start\n"
        "6144 32 t cold_a\n"
        "6176 64 T cold_b\n"
        "6240 0 A __island_end\n"
    )
    sections = _parse_size_output(size_text)
    symbols = _parse_nm_output(nm_text)
    policy = _selftest_policy()
    base = _build_report(sections, symbols, policy, {})
    assert base["status"] == "ok", base["violations"]
    assert base["coverage"]["physical_allocations"] == 2
    assert [item["name"] for item in base["declared_coordinators"]] == [
        "cold_a",
        "cold_b",
    ]
    assert base["allowed_coordinator_classes"] == [
        "l65m-coordinator",
        "batch-coordinator",
    ]
    assert base["screen_contract"]["non_seam_max_address"] == 0x179F
    assert base["annex_contract"]["present"] is False

    annex_start = 6240
    annex_sections = _parse_size_output(
        size_text
        + ".lisp65_resident_island_annex 260 %d\n" % annex_start
    )
    annex_symbols = _parse_nm_output(
        nm_text
        + "%d 0 A __lisp65_resident_island_annex_start\n" % annex_start
        + "%d 2 B lisp65_rootstack_canary_before\n" % annex_start
        + "%d 256 B gc_rootstack\n" % (annex_start + 2)
        + "%d 2 B lisp65_rootstack_canary_after\n" % (annex_start + 258)
        + "%d 0 A __lisp65_resident_island_annex_end\n" % (annex_start + 260)
    )
    annex_report = _build_report(
        annex_sections, annex_symbols, policy, {}, require_annex=True
    )
    # The production-only immutable-size pin is exercised separately below.
    assert _codes(annex_report) == {
        "immutable-size-drift", "immutable-coordinator-count-drift"
    }, annex_report["violations"]
    assert annex_report["island_contract"]["annex_bytes"] == 260

    missing_annex = _build_report(sections, symbols, policy, {}, require_annex=True)
    assert {"immutable-size-drift", "missing-annex-section"}.issubset(
        _codes(missing_annex)
    )

    bad_annex_symbols = _parse_nm_output(
        (nm_text
         + "%d 0 A __lisp65_resident_island_annex_start\n" % annex_start
         + "%d 2 B lisp65_rootstack_canary_before\n" % annex_start
         + "%d 254 B gc_rootstack\n" % (annex_start + 2)
         + "%d 2 B lisp65_rootstack_canary_after\n" % (annex_start + 258)
         + "%d 2 B forbidden_annex_data\n" % (annex_start + 256)
         + "%d 0 A __lisp65_resident_island_annex_end\n" % (annex_start + 260))
    )
    bad_annex_codes = _codes(
        _build_report(
            annex_sections, bad_annex_symbols, policy, {}, require_annex=True
        )
    )
    assert "extra-annex-symbol" in bad_annex_codes
    assert "annex-symbol-layout-drift" in bad_annex_codes

    extra_symbols = _parse_nm_output(nm_text.replace("6176 64 T cold_b", "6176 32 T cold_b\n6208 32 t extra"))
    assert "extra-island-symbol" in _codes(_build_report(sections, extra_symbols, policy, {}))

    stale = json.loads(json.dumps(policy))
    stale["allowed_symbols"][1]["name"] = "removed"
    stale_codes = _codes(_build_report(sections, symbols, stale, {}))
    assert "stale-allowlist-entry" in stale_codes and "extra-island-symbol" in stale_codes

    missing_section = _build_report([], symbols, policy, {})
    assert "missing-section" in _codes(missing_section)

    missing_boundary = _parse_nm_output(nm_text.replace("6240 0 A __island_end\n", ""))
    assert "boundary-symbol-missing" in _codes(_build_report(sections, missing_boundary, policy, {}))

    shifted_sections = _parse_size_output(
        "fixture:\nsection size addr\n.lisp65_resident_island 96 6145\nTotal 96\n"
    )
    assert "section-address-drift" in _codes(_build_report(shifted_sections, symbols, policy, {}))

    seam = json.loads(json.dumps(policy))
    seam["screen_contract"]["seam"] = True
    seam_codes = _codes(_build_report(sections, symbols, seam, {}))
    assert "screen-contract-drift" in seam_codes and "screen-seam-unsupported" in seam_codes

    boundary_drift = json.loads(json.dumps(policy))
    boundary_drift["island"]["start"] = 0x1801
    assert "island-boundary-drift" in _codes(
        _build_report(sections, symbols, boundary_drift, {})
    )

    forbidden_class = json.loads(json.dumps(policy))
    forbidden_class["allowed_symbols"][0]["coordinator_class"] = "commit-coordinator"
    try:
        _build_report(sections, symbols, forbidden_class, {})
    except ValueError as error:
        assert "outside the L65M/batch coordinator classes" in str(error)
    else:
        raise AssertionError("commit coordinator class was accepted")

    with tempfile.TemporaryDirectory(prefix="lisp65-bank0-island-") as temp:
        path = Path(temp) / "report.json"
        path.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        assert json.loads(path.read_text(encoding="utf-8"))["schema"] == REPORT_SCHEMA
    print("bank0-island-inventory selftest: PASS mutations=11")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--elf", type=Path, default=DEFAULT_ELF)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--nm", type=Path, default=DEFAULT_NM)
    parser.add_argument("--size", type=Path, default=DEFAULT_SIZE)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--text-out", type=Path, default=DEFAULT_TEXT)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--require-annex", action="store_true",
        help="require and pin the Workbench 260-byte mutable rootstack annex",
    )
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()

    try:
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        _validate_policy(policy)
        sections = _parse_size_output(_run_tool(args.size, ["-A", "-d", str(args.elf)]))
        symbols = _parse_nm_output(
            _run_tool(
                args.nm,
                ["--defined-only", "--print-size", "--size-sort", "--radix=d", str(args.elf)],
            )
        )
        inputs = {
            "elf": {"path": _display_path(args.elf), "sha256": _sha256(args.elf)},
            "policy": {"path": _display_path(args.policy), "sha256": _sha256(args.policy)},
            "nm": {"path": _display_path(args.nm), "sha256": _sha256(args.nm)},
            "size": {"path": _display_path(args.size), "sha256": _sha256(args.size)},
        }
        report = _build_report(
            sections, symbols, policy, inputs, require_annex=args.require_annex
        )
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print("bank0-island-inventory: ERROR: %s" % error, file=sys.stderr)
        return 2

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.text_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.text_out.write_text(_render_text(report), encoding="utf-8")
    print(
        "bank0-island-inventory: %s section=%s immutable=%d annex=%d reserve=%d allocations=%d json=%s text=%s"
        % (
            report["status"].upper(),
            report["island_contract"]["section"],
            report["island_contract"]["immutable_bytes"],
            report["island_contract"]["annex_bytes"],
            report["island_contract"]["reserve_bytes"],
            report["coverage"]["physical_allocations"],
            args.json_out,
            args.text_out,
        )
    )
    return 1 if args.check and report["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
