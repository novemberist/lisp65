#!/usr/bin/env python3
"""Split the 2.0 layout golden into invariants and derived freight facts.

The reviewed v1 artifact deliberately captured a complete linked-layout
snapshot.  The 2.0 card proved that this mixed two different kinds of truth:
owned geometry and the freight shape of the source world.  This gate retains
only freight-independent facts in the SHA-bound artifact.  Section sizes,
numeric LMAs and the workbench-overlay end are extracted from each candidate
and checked against fixed walls, fixed load order and independent ELF symbols;
they are never copied into the golden.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_golden_layout_inversion as LEGACY  # noqa: E402
import c2_stack_overlay_ownership as OWN  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
GOLDEN = ROOT / (
    "tests/bytecode/dialect-v2/golden-layout/"
    "c2-full-map-owned-invariants-v2.json")
RECEIPT = EVIDENCE / "c2.3-v2.0-invariant-golden-review-receipt.json"
FINAL_RED = EVIDENCE / "c2.3-v2.0-ownership-recharter-card-final-red.json"
CURRENT_ELF = ROOT / (
    "build/c2.3/v2.0-ownership-recharter-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
CURRENT_ELF_SHA256 = (
    "1b8f75fce3bfcc619ec67d59bb196db5ea196e29f16a8c30b905b1a4f20b4e9b")
FULL_MAP_CONTRACT = ROOT / "config/c2-full-map-ownership-contract.json"
CANDIDATE_CONTRACT = ROOT / (
    "build/c2.3/v2.0-ownership-recharter-inputs/"
    "c2-lite-execution-contract.json")
CANDIDATE_PREFLIGHT = ROOT / (
    "build/c2.3/v2.0-ownership-recharter-preflight/preflight.json")
DISPOSITION_COMMIT = "99002732f32794552a7e5b3c3359388fdda28486"
DISPOSITION_PATH = "docs/planning/2.0-ownership-recharter-work-plan.md"
GOLDEN_SHA256 = "ed12b83b4913923eb4ed3a1977008d70edc7f1c8d4f1da9a13f007a69d390e0d"
FORMAT = "lisp65-c2-full-map-invariant-golden-v2"
RECORDED_ON = "2026-08-12"

DERIVED_BOUNDARY = "__lisp65_workbench_overlay_end"
FIXED_BOUNDARIES = tuple(
    name for name in LEGACY.BOUNDARY_SYMBOLS if name != DERIVED_BOUNDARY)

SECTION_KEYS = {
    "alignment", "flags", "name", "section_type", "vma"}
TOP_KEYS = {
    "capacity_arenas", "derived_fields", "fixed_boundary_symbols", "format",
    "load_order", "section_invariants"}


class InvariantGoldenError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise InvariantGoldenError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular authority absent: {path}")
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def git_binding(commit: str, path: str) -> dict[str, Any]:
    raw = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {
        "git_commit": commit,
        "path": path,
        "bytes": len(raw),
        "sha256": sha_bytes(raw),
    }


def section_names(prefix: str, rows: list[dict[str, Any]]) -> list[str]:
    return sorted(row["name"] for row in rows if row["name"].startswith(prefix))


def source_artifact() -> dict[str, Any]:
    """Project the accepted snapshot into freight-independent truth."""
    legacy = load(LEGACY.GOLDEN)
    LEGACY.audit_artifact(legacy)
    rows = legacy["allocatable_sections"]
    names = {row["name"] for row in rows}

    def members(*items: str) -> list[str]:
        result = list(items)
        require(set(result) <= names, f"unknown capacity member: {result}")
        return result

    runtime = section_names(".lisp65_rt_", rows)
    require(len(runtime) == 61, "runtime-overlay section closure drift")

    arenas = [
        {
            "id": "basic-header", "space": "default-cpu",
            "start": 0x2001, "end_exclusive": 0x2017,
            "policy": "fixed-vma-ordered-no-overlap",
            "members": members(".basic_header"),
        },
        {
            "id": "ordinary-zero-page", "space": "zero-page",
            "start": 0x22, "end_exclusive": 0x90,
            "policy": "fixed-vma-ordered-no-overlap",
            "members": members(
                ".zp.data", ".zp.bss", ".zp",
                ".lisp65_c2_convergence_zp", ".lisp65_c2_fixed_zp"),
        },
        {
            "id": "ordinary-text", "space": "default-cpu",
            "start": 0x2023, "end_exclusive": 0xB3B0,
            "policy": "fixed-vma-ordered-no-overlap",
            "members": members(".text"),
        },
        {
            "id": "mapped-bank2-far-service", "space": "mapped-bank2",
            "start": 0x78B2, "end_exclusive": 0x7E8D,
            "policy": "fixed-vma-ordered-no-overlap",
            "members": members(".lisp65_c2_mapped_far_service"),
        },
        {
            "id": "low-resident-and-ordinary-chain", "space": "default-cpu",
            "start": 0xB3B0, "end_exclusive": 0xC000,
            "policy": "fixed-vma-ordered-no-overlap",
            "members": members(
                ".lisp65_c2_mapped_far_facade",
                ".lisp65_c2_kernal_handoff", ".lisp65_c2_host_facade",
                ".lisp65_c2_kernal_io_reveal",
                ".lisp65_c2_kernal_map_switch", ".lisp65_c2_kernal_state",
                ".rodata", ".lisp65_runtime_overlay_verifier_bindings",
                ".data", ".bss"),
        },
        {
            "id": "owned-bank0-state", "space": "default-cpu",
            "start": 0xC000, "end_exclusive": 0xC354,
            "policy": "fixed-vma-ordered-no-overlap",
            "members": members(
                ".lisp65_c2_convergence_state", ".lisp65_c2_static_stack",
                ".lisp65_c2_fixed_bank0", ".lisp65_c2_fixed_bank0_code",
                ".lisp65_c2_fixed_bank0_hot_bss", ".noinit"),
        },
        {
            "id": "workbench-boot-overlay", "space": "boot-overlay",
            "start": 0xC356, "end_exclusive": 0xCE00,
            "policy": "independent-alternate-overlay",
            "members": members(".lisp65_workbench_overlay"),
        },
        {
            "id": "runtime-overlay-slices", "space": "runtime-overlay",
            "start": 0xC356, "end_exclusive": 0xCA56,
            "policy": "independent-alternate-overlay",
            "members": members(".lisp65_boot_bank3_stage", *runtime),
        },
        {
            "id": "resident-island", "space": "low-memory-island",
            "start": 0x1800, "end_exclusive": 0x2000,
            "policy": "fixed-vma-ordered-no-overlap",
            "members": members(
                ".lisp65_resident_island", ".lisp65_resident_island_annex"),
        },
        {
            "id": "kernal-window", "space": "e000-cpu-window",
            "start": 0xE000, "end_exclusive": 0x10000,
            "policy": "fixed-vma-ordered-zero-alias-only",
            "members": members(*sorted(
                name for name in names
                if name.startswith(".lisp65_c2_kernal_window."))),
        },
    ]
    covered = [name for arena in arenas for name in arena["members"]]
    require(len(covered) == len(set(covered)),
            "a section has more than one capacity owner")
    require(set(covered) | {".lisp65_c2_vectors"} == names,
            "capacity arena section closure drift")
    # The vector is a fixed six-byte terminal table; its VMA and the $10000
    # arena wall make a separate row clearer than special-casing wraparound.
    arenas.append({
        "id": "kernal-vectors", "space": "e000-cpu-window",
        "start": 0xFFFA, "end_exclusive": 0x10000,
        "policy": "fixed-vma-ordered-no-overlap",
        "members": [".lisp65_c2_vectors"],
    })

    file_backed = [
        row for row in rows
        if row["lma"] is not None and row["bytes"] > 0
        and row["section_type"] != "SHT_NOBITS"]
    file_backed.sort(key=lambda row: (row["lma"], row["name"]))

    return {
        "format": FORMAT,
        "section_invariants": [
            {key: row[key] for key in sorted(SECTION_KEYS)} for row in rows],
        "fixed_boundary_symbols": {
            name: legacy["boundary_symbols"][name]
            for name in FIXED_BOUNDARIES},
        "capacity_arenas": arenas,
        "load_order": [row["name"] for row in file_backed],
        "derived_fields": {
            "section_bytes": {
                "source": "candidate-elf-section-table",
                "validation": "fixed-capacity-arenas",
                "frozen_in_golden": False,
            },
            "section_lmas": {
                "source": "candidate-elf-program-headers",
                "validation": "fixed-load-order-and-non-overlap",
                "frozen_in_golden": False,
            },
            "boundary_symbols": {
                DERIVED_BOUNDARY: {
                    "operation": "section-vma-plus-bytes",
                    "section": ".lisp65_workbench_overlay",
                    "frozen_in_golden": False,
                },
            },
        },
    }


def audit_artifact(value: dict[str, Any]) -> None:
    require(set(value) == TOP_KEYS, "invariant golden top-level shape drift")
    require(value["format"] == FORMAT, "invariant golden format drift")

    rows = value["section_invariants"]
    require(isinstance(rows, list) and rows,
            "invariant golden has no section inventory")
    names: list[str] = []
    for row in rows:
        require(isinstance(row, dict) and set(row) == SECTION_KEYS,
                "section invariant contains a snapshot field or loses an invariant")
        require(isinstance(row["name"], str) and row["name"],
                "section invariant has no identity")
        require(isinstance(row["vma"], int) and row["vma"] >= 0,
                f"invalid invariant VMA: {row['name']}")
        require(isinstance(row["alignment"], int) and row["alignment"] > 0,
                f"invalid invariant alignment: {row['name']}")
        require(isinstance(row["section_type"], str) and row["section_type"],
                f"invalid invariant section type: {row['name']}")
        require(isinstance(row["flags"], list)
                and row["flags"] == sorted(set(row["flags"]))
                and all(isinstance(flag, str) for flag in row["flags"]),
                f"invalid invariant flags: {row['name']}")
        names.append(row["name"])
    require(names == sorted(set(names)),
            "section invariant identities are duplicated or non-canonical")

    boundaries = value["fixed_boundary_symbols"]
    require(isinstance(boundaries, dict)
            and tuple(sorted(boundaries)) == FIXED_BOUNDARIES,
            "fixed/derived boundary partition drift")
    require(DERIVED_BOUNDARY not in boundaries,
            "freight-derived overlay_end was promoted to a fixed invariant")
    require(all(isinstance(item, int) and item >= 0
                for item in boundaries.values()),
            "invalid fixed boundary value")

    derived = value["derived_fields"]
    require(isinstance(derived, dict) and set(derived) == {
        "boundary_symbols", "section_bytes", "section_lmas"},
        "derived field closure drift")
    require(derived["section_bytes"] == {
        "source": "candidate-elf-section-table",
        "validation": "fixed-capacity-arenas",
        "frozen_in_golden": False,
    }, "section-size derivation drift")
    require(derived["section_lmas"] == {
        "source": "candidate-elf-program-headers",
        "validation": "fixed-load-order-and-non-overlap",
        "frozen_in_golden": False,
    }, "section-LMA derivation drift")
    require(derived["boundary_symbols"] == {
        DERIVED_BOUNDARY: {
            "operation": "section-vma-plus-bytes",
            "section": ".lisp65_workbench_overlay",
            "frozen_in_golden": False,
        },
    }, "derived overlay-end rule drift")

    arenas = value["capacity_arenas"]
    require(isinstance(arenas, list) and len(arenas) == 11,
            "capacity-arena closure drift")
    arena_ids: list[str] = []
    owned: list[str] = []
    for arena in arenas:
        require(isinstance(arena, dict) and set(arena) == {
            "end_exclusive", "id", "members", "policy", "space", "start"},
            "capacity-arena shape drift")
        require(isinstance(arena["id"], str) and arena["id"],
                "capacity arena has no identity")
        require(isinstance(arena["start"], int)
                and isinstance(arena["end_exclusive"], int)
                and arena["start"] < arena["end_exclusive"],
                f"invalid capacity wall: {arena['id']}")
        require(arena["policy"] in {
            "fixed-vma-ordered-no-overlap",
            "fixed-vma-ordered-zero-alias-only",
            "independent-alternate-overlay"},
            f"unknown capacity policy: {arena['id']}")
        require(isinstance(arena["members"], list) and arena["members"],
                f"empty capacity arena: {arena['id']}")
        arena_ids.append(arena["id"])
        owned.extend(arena["members"])
    require(arena_ids == list(dict.fromkeys(arena_ids)),
            "duplicate capacity-arena identity")
    require(sorted(owned) == names,
            "capacity arenas do not own the complete section inventory")

    order = value["load_order"]
    require(isinstance(order, list) and order
            and order == list(dict.fromkeys(order))
            and set(order) <= set(names), "invalid invariant load order")


def golden_bytes() -> bytes:
    raw = GOLDEN.read_bytes()
    require(sha_bytes(raw) == GOLDEN_SHA256,
            "invariant golden SHA-256 binding drift")
    value = load(GOLDEN)
    audit_artifact(value)
    require(canonical(value) == raw,
            "invariant golden is not canonical JSON")
    return raw


def invariant_projection(layout: dict[str, Any]) -> dict[str, Any]:
    rows = layout["allocatable_sections"]
    return {
        "section_invariants": [
            {key: row[key] for key in sorted(SECTION_KEYS)} for row in rows],
        "fixed_boundary_symbols": {
            name: layout["boundary_symbols"][name]
            for name in FIXED_BOUNDARIES},
    }


def expected_projection(golden: dict[str, Any]) -> dict[str, Any]:
    return {
        "section_invariants": golden["section_invariants"],
        "fixed_boundary_symbols": golden["fixed_boundary_symbols"],
    }


def validate_capacities(layout: dict[str, Any], golden: dict[str, Any]) -> None:
    by_name = {row["name"]: row for row in layout["allocatable_sections"]}
    for arena in golden["capacity_arenas"]:
        rows = [by_name[name] for name in arena["members"]]
        for row in rows:
            require(arena["start"] <= row["vma"] < arena["end_exclusive"],
                    f"section start escaped capacity arena: {row['name']}")
            require(row["vma"] + row["bytes"] <= arena["end_exclusive"],
                    f"section end escaped capacity arena: {row['name']}")
        if arena["policy"] == "independent-alternate-overlay":
            continue
        rows.sort(key=lambda row: (row["vma"], row["name"]))
        previous_end = arena["start"]
        previous_vma: int | None = None
        for row in rows:
            if previous_vma == row["vma"]:
                require(row["bytes"] == 0 or previous_end == row["vma"],
                        f"nonzero VMA alias in owned arena: {row['name']}")
            else:
                require(row["vma"] >= previous_end,
                        f"owned VMA ranges overlap: {row['name']}")
            previous_end = max(previous_end, row["vma"] + row["bytes"])
            previous_vma = row["vma"]


def validate_loads(layout: dict[str, Any], golden: dict[str, Any]) -> None:
    rows = [
        row for row in layout["allocatable_sections"]
        if row["lma"] is not None and row["bytes"] > 0
        and row["section_type"] != "SHT_NOBITS"]
    rows.sort(key=lambda row: (row["lma"], row["name"]))
    require([row["name"] for row in rows] == golden["load_order"],
            "candidate load order differs from invariant golden")
    previous_end = 0
    for row in rows:
        require(row["lma"] >= previous_end,
                f"candidate load ranges overlap: {row['name']}")
        previous_end = row["lma"] + row["bytes"]


def validate_derived(layout: dict[str, Any], golden: dict[str, Any]) -> None:
    by_name = {row["name"]: row for row in layout["allocatable_sections"]}
    overlay = by_name[".lisp65_workbench_overlay"]
    observed = layout["boundary_symbols"][DERIVED_BOUNDARY]
    require(observed == overlay["vma"] + overlay["bytes"],
            "derived overlay_end disagrees with candidate section extent")
    validate_capacities(layout, golden)
    validate_loads(layout, golden)


def capacity_measurements(layout: dict[str, Any], golden: dict[str, Any]
                          ) -> list[dict[str, Any]]:
    """Price candidate freight against every fixed invariant wall."""
    by_name = {row["name"]: row for row in layout["allocatable_sections"]}
    result: list[dict[str, Any]] = []
    for arena in golden["capacity_arenas"]:
        maximum_end = max(
            by_name[name]["vma"] + by_name[name]["bytes"]
            for name in arena["members"])
        result.append({
            "id": arena["id"],
            "start": arena["start"],
            "end_exclusive": arena["end_exclusive"],
            "candidate_max_end_exclusive": maximum_end,
            "candidate_headroom_bytes": arena["end_exclusive"] - maximum_end,
        })
    return result


def compare_layout(layout: dict[str, Any], golden: dict[str, Any] | None = None
                   ) -> dict[str, Any]:
    authority = load(GOLDEN) if golden is None else golden
    audit_artifact(authority)
    require(invariant_projection(layout) == expected_projection(authority),
            "candidate invariant geometry differs from reviewed golden")
    validate_derived(layout, authority)
    derived = {
        "section_bytes": {
            row["name"]: row["bytes"]
            for row in layout["allocatable_sections"]},
        "section_lmas": {
            row["name"]: row["lma"]
            for row in layout["allocatable_sections"]},
        "boundary_symbols": {
            DERIVED_BOUNDARY: layout["boundary_symbols"][DERIVED_BOUNDARY]},
    }
    projection = invariant_projection(layout)
    return {
        "comparison": "invariants-exact-derived-freight-validated",
        "invariant_projection_sha256": sha_bytes(canonical(projection)),
        "derived_freight_sha256": sha_bytes(canonical(derived)),
        "allocatable_sections": len(layout["allocatable_sections"]),
        "fixed_boundary_symbols": len(FIXED_BOUNDARIES),
        "derived_boundary_symbols": 1,
        "capacity_arenas": len(authority["capacity_arenas"]),
        "capacity_measurements": capacity_measurements(layout, authority),
        "load_order_entries": len(authority["load_order"]),
    }


def compare_elf(path: Path) -> dict[str, Any]:
    golden_bytes()
    return compare_layout(LEGACY.layout_from_elf(path))


def reject(label: str, action: Callable[[], None], result: dict[str, str]) -> None:
    try:
        action()
    except (InvariantGoldenError, OWN.OwnershipError, KeyError, TypeError) as error:
        result[label] = str(error)
    else:
        raise InvariantGoldenError(f"invariant-golden mutation survived: {label}")


def mutation_selftest() -> dict[str, str]:
    golden_bytes()
    base = load(GOLDEN)
    historical = LEGACY.layout_from_elf(LEGACY.FINAL_ELF)
    current = LEGACY.layout_from_elf(CURRENT_ELF)
    result: dict[str, str] = {}

    artifact_cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "invariant-demoted-to-derived": lambda x:
            x["section_invariants"][0].pop("vma"),
        "snapshot-size-promoted-to-invariant": lambda x:
            x["section_invariants"][0].update(bytes=22),
        "snapshot-lma-promoted-to-invariant": lambda x:
            x["section_invariants"][0].update(lma=8193),
        "snapshot-overlay-end-promoted-to-invariant": lambda x:
            x["fixed_boundary_symbols"].update(
                {DERIVED_BOUNDARY: 0xCA1C}),
        "derived-overlay-rule-dimmed": lambda x:
            x["derived_fields"]["boundary_symbols"][DERIVED_BOUNDARY].update(
                operation="candidate-value"),
        "section-inventory-deleted": lambda x:
            x["section_invariants"].pop(),
        "fixed-boundary-moved": lambda x:
            x["fixed_boundary_symbols"].update(__heap_start=0xC355),
        "load-order-swapped": lambda x:
            x["load_order"].__setitem__(slice(0, 2), x["load_order"][1::-1]),
        "capacity-wall-shrunk": lambda x:
            next(a for a in x["capacity_arenas"]
                 if a["id"] == "workbench-boot-overlay").update(
                     end_exclusive=0xCA00),
        "format-changed": lambda x: x.update(format="old"),
    }
    for label, mutate in artifact_cases.items():
        candidate = deepcopy(base)
        mutate(candidate)
        reject(label, lambda candidate=candidate: (
            audit_artifact(candidate),
            require(canonical(candidate) == golden_bytes(),
                    "mutated fixed authority differs from SHA-bound golden"),
            compare_layout(current, candidate)), result)

    candidate_cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "candidate-vma-moved": lambda x:
            x["allocatable_sections"][0].update(
                vma=x["allocatable_sections"][0]["vma"] + 1),
        "candidate-fixed-boundary-moved": lambda x:
            x["boundary_symbols"].update(__heap_start=0xC355),
        "candidate-derived-overlay-end-lies": lambda x:
            x["boundary_symbols"].update(
                {DERIVED_BOUNDARY: x["boundary_symbols"][DERIVED_BOUNDARY] + 1}),
        "candidate-runtime-capacity-overflow": lambda x:
            next(row for row in x["allocatable_sections"]
                 if row["name"] == ".lisp65_rt_c2d_00").update(bytes=1793),
        "candidate-load-order-crossed": lambda x:
            next(row for row in x["allocatable_sections"]
                 if row["name"] == ".lisp65_rt_c2d_00b").update(lma=0x10000),
    }
    for label, mutate in candidate_cases.items():
        candidate = deepcopy(current)
        mutate(candidate)
        reject(label, lambda candidate=candidate: compare_layout(candidate, base),
               result)

    # Both source-world and freight-shifted v1.5 layouts must pass the same
    # invariant authority.  This is the positive half of the split.
    compare_layout(historical, base)
    compare_layout(current, base)
    return result


def freight_delta() -> dict[str, Any]:
    old = LEGACY.layout_from_elf(LEGACY.FINAL_ELF)
    new = LEGACY.layout_from_elf(CURRENT_ELF)
    old_rows = {row["name"]: row for row in old["allocatable_sections"]}
    new_rows = {row["name"]: row for row in new["allocatable_sections"]}
    size_names = sorted(
        name for name in old_rows
        if old_rows[name]["bytes"] != new_rows[name]["bytes"])
    lma_names = sorted(
        name for name in old_rows
        if old_rows[name]["lma"] != new_rows[name]["lma"])
    boundary_names = sorted(
        name for name in old["boundary_symbols"]
        if old["boundary_symbols"][name] != new["boundary_symbols"][name])
    require(len(size_names) == 9 and len(lma_names) == 64
            and boundary_names == [DERIVED_BOUNDARY],
            "2.0 source/candidate freight-delta family drift")
    require(invariant_projection(old) == invariant_projection(new),
            "2.0 candidate differs in an invariant field")
    return {
        "section_size_deltas": len(size_names),
        "section_size_names": size_names,
        "section_lma_deltas": len(lma_names),
        "derived_boundary_deltas": boundary_names,
        "fixed_vma_deltas": 0,
        "fixed_boundary_deltas": 0,
    }


def build_receipt() -> dict[str, Any]:
    require(sha(CURRENT_ELF) == CURRENT_ELF_SHA256,
            "2.0 candidate ELF binding drift")
    historical = compare_elf(LEGACY.FINAL_ELF)
    current = compare_elf(CURRENT_ELF)
    require(historical["invariant_projection_sha256"]
            == current["invariant_projection_sha256"],
            "source and v1.5 candidate invariant projections differ")
    require(historical["derived_freight_sha256"]
            != current["derived_freight_sha256"],
            "source and v1.5 freight projections unexpectedly match")
    mutations = mutation_selftest()
    disposition = git_binding(DISPOSITION_COMMIT, DISPOSITION_PATH)
    raw = subprocess.run(
        ["git", "show", f"{DISPOSITION_COMMIT}:{DISPOSITION_PATH}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    require(b"golden splits into its two natures" in raw
            and b"exactly one card" in raw,
            "owner invariant-golden disposition is not bound")
    return {
        "format": "lisp65-c2.3-v20-invariant-golden-review-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: awaiting one-time reviewer invariant-golden review",
        "claim": (
            "Host-only split of the reviewed layout snapshot into one "
            "SHA-bound freight-independent geometry authority and "
            "candidate-derived validated freight facts; no WPLTO, card, "
            "product, device, v1.5, release or parity claim."),
        "invariant_golden": {
            **bind(GOLDEN),
            "section_invariants": len(load(GOLDEN)["section_invariants"]),
            "fixed_boundary_symbols": len(FIXED_BOUNDARIES),
            "capacity_arenas": len(load(GOLDEN)["capacity_arenas"]),
            "load_order_entries": len(load(GOLDEN)["load_order"]),
            "frozen_section_size_fields": 0,
            "frozen_section_lma_fields": 0,
            "frozen_overlay_end_fields": 0,
        },
        "two_natures": {
            "fixed": [
                "section identity/VMA/alignment/type/flags",
                "27 freight-independent boundary symbols",
                "11 capacity arenas",
                "89-entry load ordering invariant",
            ],
            "candidate_derived": [
                "all section sizes",
                "all numeric section LMAs",
                DERIVED_BOUNDARY,
            ],
            "source_world": historical,
            "v1.5_plus_convergence_world": current,
            "observed_freight_delta": freight_delta(),
        },
        "mutations_rejected": mutations,
        "execution_witness": {
            "elf_layout_extractions": 6,
            "invariant_comparisons": 2,
            "derived_freight_validations": 2,
            "mutations": len(mutations),
            "product_compiles": 0,
            "fresh_wplto": 0,
            "cards_consumed": 0,
            "device_contacts": 0,
        },
        "authority": {
            "owner_disposition": disposition,
            "legacy_snapshot_golden": bind(LEGACY.GOLDEN),
            "legacy_golden_review": bind(LEGACY.RECEIPT),
            "terminal_2.0_first_red": bind(FINAL_RED),
            "full_map_ownership_contract": bind(FULL_MAP_CONTRACT),
            "candidate_execution_contract": bind(CANDIDATE_CONTRACT),
            "candidate_preflight": bind(CANDIDATE_PREFLIGHT),
            "source_world_elf": bind(LEGACY.FINAL_ELF),
            "v1.5_plus_convergence_elf": bind(CURRENT_ELF),
            "gate": bind(Path(__file__).resolve()),
        },
        "review_question": (
            "Accept the SHA-bound invariant golden once.  Only a later "
            "reviewer acceptance may unlock the exactly-one-card edge."),
        "card_lock": {
            "review_accepted": False,
            "card_authorized_by_this_receipt": False,
            "wplto_allowed": False,
        },
    }


def emit() -> None:
    require(not GOLDEN.exists(), "invariant golden already exists")
    value = source_artifact()
    audit_artifact(value)
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_bytes(canonical(value))
    print("2.0 invariant golden: EMIT PASS "
          f"sections={len(value['section_invariants'])} "
          f"boundaries={len(value['fixed_boundary_symbols'])}+1-derived "
          f"arenas={len(value['capacity_arenas'])} "
          f"sha256={sha(GOLDEN)}")


def review(write: bool) -> None:
    value = build_receipt()
    if write:
        RECEIPT.write_bytes(canonical(value))
    print("2.0 invariant golden: REVIEW PASS "
          f"sections={value['invariant_golden']['section_invariants']} "
          f"freight=9-size/64-lma/1-boundary "
          f"mutations={value['execution_witness']['mutations']} "
          "wplto=0 cards=0 device=0 review=reviewer")


def check() -> None:
    require(RECEIPT.is_file(), "invariant-golden review receipt absent")
    expected = build_receipt()
    require(canonical(load(RECEIPT)) == canonical(expected),
            "invariant-golden review receipt drift")
    print("2.0 invariant golden: CHECK PASS "
          f"golden={GOLDEN_SHA256} mutations={len(expected['mutations_rejected'])} "
          "card=locked")


def selftest() -> None:
    source = source_artifact()
    audit_artifact(source)
    require(canonical(source) == golden_bytes(),
            "emitted invariant golden is not reproducible from source authority")
    mutations = mutation_selftest()
    delta = freight_delta()
    print("2.0 invariant golden: SELFTEST PASS "
          f"mutations={len(mutations)} fixed-vma-delta={delta['fixed_vma_deltas']} "
          f"freight={delta['section_size_deltas']}/"
          f"{delta['section_lma_deltas']}/1 card=locked")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", choices=("emit", "selftest", "review", "write-review",
                         "check", "compare"))
    parser.add_argument("--elf", type=Path)
    args = parser.parse_args()
    if args.mode == "emit":
        emit()
    elif args.mode == "selftest":
        selftest()
    elif args.mode in ("review", "write-review"):
        review(args.mode == "write-review")
    elif args.mode == "check":
        check()
    else:
        require(args.elf is not None, "compare mode requires --elf")
        result = compare_elf(args.elf)
        print("2.0 invariant golden: COMPARE PASS "
              f"sections={result['allocatable_sections']} "
              f"fixed-boundaries={result['fixed_boundary_symbols']} "
              f"derived-boundaries={result['derived_boundary_symbols']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InvariantGoldenError, OWN.OwnershipError, OSError, ValueError,
            KeyError, subprocess.CalledProcessError) as error:
        print(f"2.0 invariant golden: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
