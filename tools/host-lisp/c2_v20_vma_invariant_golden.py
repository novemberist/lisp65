#!/usr/bin/env python3
"""Review the VMA-only successor to the 2.0 invariant golden.

The first invariant golden correctly separated section sizes and numeric LMAs
from owned geometry, but retained an LMA-sorted ``load_order``.  The low-
resident delivery repair proved that this order was another source-world
snapshot: fixing four LMAs changed the order while every VMA remained exact.

This successor stores no order.  Geometric order is recomputed from the fixed
VMA inventory at validation time.  File-load order is recomputed independently
from each candidate's LMAs and is required only to be complete and
non-overlapping.  No card edge is exposed by this module; its receipt is the
one-time review package ordered by the owner disposition.
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
import c2_product_substitution_link as LINK  # noqa: E402
import c2_stack_overlay_ownership as OWN  # noqa: E402
import c2_v20_invariant_golden as V2  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
GOLDEN = ROOT / (
    "tests/bytecode/dialect-v2/golden-layout/"
    "c2-full-map-owned-vma-invariants-v3.json")
RECEIPT = EVIDENCE / "c2.3-v2.0-vma-invariant-golden-review-receipt.json"
REBIND = EVIDENCE / (
    "c2.3-v2.0-vma-invariant-golden-review-rebind-2026-08-16.json")
LMA_FINAL_RED = EVIDENCE / (
    "c2.3-v2.0-low-resident-lma-repair-card-final-red.json")
BROKEN_WORLD_ELF = V2.CURRENT_ELF
REPAIRED_WORLD_ELF = ROOT / (
    "build/c2.3/v2.0-low-resident-lma-repair-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
REPAIRED_WORLD_ELF_SHA256 = (
    "10ab42e4c19ae4e6b20b93c1b9598ff576aabfc7bb357865da199e593d61d4f8")
DISPOSITION_COMMIT = "30a5568706f92e7a61475b1f28745cf2d52d2de5"
DISPOSITION_PATH = "docs/planning/2.0-ownership-recharter-work-plan.md"
FORMAT = "lisp65-c2-full-map-vma-invariant-golden-v3"
GOLDEN_SHA256 = "3b7d35e34f1199b03e58eeb9be3da7e45aaeb87b67a652c32751761df1398dfa"
RECORDED_ON = "2026-08-12"

TOP_KEYS = {
    "capacity_arenas", "derived_fields", "fixed_boundary_symbols", "format",
    "section_invariants"}
RESET_SECTIONS = (
    ".lisp65_c2_kernal_handoff",
    ".lisp65_c2_host_facade",
    ".lisp65_c2_kernal_io_reveal",
    ".lisp65_c2_kernal_map_switch",
)


class VmaInvariantGoldenError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise VmaInvariantGoldenError(message)


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


def source_artifact() -> dict[str, Any]:
    """Derive v3 only from the already reviewed v2 fixed facts."""
    value = deepcopy(load(V2.GOLDEN))
    V2.audit_artifact(value)
    value.pop("load_order")
    value["format"] = FORMAT
    value["derived_fields"]["section_lmas"] = {
        "source": "candidate-elf-program-headers",
        "validation": "candidate-local-complete-and-non-overlapping",
        "frozen_in_golden": False,
    }
    value["derived_fields"]["section_order"] = {
        "vma_geometry": {
            "source": "golden-section-invariant-vmas",
            "operation": "sort-by-vma-then-identity-at-validation-time",
            "frozen_in_golden": False,
        },
        "lma_sequence": {
            "source": "candidate-elf-program-headers",
            "operation": "sort-by-lma-then-identity-at-validation-time",
            "frozen_in_golden": False,
        },
    }
    return value


def audit_artifact(value: dict[str, Any]) -> None:
    require(set(value) == TOP_KEYS,
            "VMA invariant golden top-level shape drift or stored order field")
    require(value["format"] == FORMAT, "VMA invariant golden format drift")
    require("load_order" not in value,
            "LMA-dependent load_order was promoted to a golden invariant")
    rows = value["section_invariants"]
    require(isinstance(rows, list) and rows,
            "VMA invariant golden has no section inventory")
    names: list[str] = []
    for row in rows:
        require(isinstance(row, dict) and set(row) == V2.SECTION_KEYS,
                "section invariant contains freight or loses geometry")
        require(isinstance(row["name"], str) and row["name"],
                "section invariant has no identity")
        require(isinstance(row["vma"], int) and row["vma"] >= 0,
                f"invalid invariant VMA: {row['name']}")
        require(isinstance(row["alignment"], int) and row["alignment"] > 0,
                f"invalid invariant alignment: {row['name']}")
        require(isinstance(row["section_type"], str)
                and row["section_type"],
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
            and tuple(sorted(boundaries)) == V2.FIXED_BOUNDARIES,
            "fixed boundary closure drift")
    require(V2.DERIVED_BOUNDARY not in boundaries,
            "freight-derived overlay_end was promoted to an invariant")
    require(all(isinstance(item, int) and item >= 0
                for item in boundaries.values()),
            "invalid fixed boundary value")

    derived = value["derived_fields"]
    require(isinstance(derived, dict) and set(derived) == {
        "boundary_symbols", "section_bytes", "section_lmas", "section_order"},
        "derived field closure drift")
    require(derived["section_bytes"] == {
        "source": "candidate-elf-section-table",
        "validation": "fixed-capacity-arenas",
        "frozen_in_golden": False,
    }, "section-size derivation drift")
    require(derived["section_lmas"] == {
        "source": "candidate-elf-program-headers",
        "validation": "candidate-local-complete-and-non-overlapping",
        "frozen_in_golden": False,
    }, "section-LMA derivation drift")
    require(derived["section_order"] == {
        "vma_geometry": {
            "source": "golden-section-invariant-vmas",
            "operation": "sort-by-vma-then-identity-at-validation-time",
            "frozen_in_golden": False,
        },
        "lma_sequence": {
            "source": "candidate-elf-program-headers",
            "operation": "sort-by-lma-then-identity-at-validation-time",
            "frozen_in_golden": False,
        },
    }, "VMA/LMA order derivation partition drift")
    require(derived["boundary_symbols"] == {
        V2.DERIVED_BOUNDARY: {
            "operation": "section-vma-plus-bytes",
            "section": ".lisp65_workbench_overlay",
            "frozen_in_golden": False,
        },
    }, "derived overlay-end rule drift")

    arenas = value["capacity_arenas"]
    require(isinstance(arenas, list) and len(arenas) == 11,
            "capacity arena closure drift")
    owned: list[str] = []
    arena_ids: list[str] = []
    for arena in arenas:
        require(isinstance(arena, dict) and set(arena) == {
            "end_exclusive", "id", "members", "policy", "space", "start"},
            "capacity arena shape drift")
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
            "duplicate capacity arena identity")
    require(sorted(owned) == names,
            "capacity arenas do not own the complete section inventory")


def golden_bytes() -> bytes:
    raw = GOLDEN.read_bytes()
    require(sha_bytes(raw) == GOLDEN_SHA256,
            "VMA invariant golden SHA-256 binding drift")
    value = load(GOLDEN)
    audit_artifact(value)
    require(canonical(value) == raw,
            "VMA invariant golden is not canonical JSON")
    return raw


def invariant_projection(layout: dict[str, Any]) -> dict[str, Any]:
    return V2.invariant_projection(layout)


def expected_projection(golden: dict[str, Any]) -> dict[str, Any]:
    return {
        "section_invariants": golden["section_invariants"],
        "fixed_boundary_symbols": golden["fixed_boundary_symbols"],
    }


def vma_order_from_rows(rows: list[dict[str, Any]]) -> list[str]:
    return [row["name"] for row in sorted(
        rows, key=lambda row: (row["vma"], row["name"]))]


def candidate_file_rows(layout: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        row for row in layout["allocatable_sections"]
        if row["lma"] is not None and row["bytes"] > 0
        and row["section_type"] != "SHT_NOBITS"]
    return sorted(rows, key=lambda row: (row["lma"], row["name"]))


def validate_vma_order(layout: dict[str, Any], golden: dict[str, Any]) -> None:
    expected = vma_order_from_rows(golden["section_invariants"])
    observed = vma_order_from_rows(layout["allocatable_sections"])
    require(observed == expected,
            "candidate-derived VMA order violates invariant VMA geometry")


def validate_loads(layout: dict[str, Any], golden: dict[str, Any]) -> None:
    expected_rows = [
        row for row in layout["allocatable_sections"]
        if row["bytes"] > 0 and row["section_type"] != "SHT_NOBITS"]
    require(all(row["lma"] is not None for row in expected_rows),
            "candidate file-backed section lacks a derived LMA")
    rows = candidate_file_rows(layout)
    invariant_names = {row["name"] for row in golden["section_invariants"]}
    require({row["name"] for row in rows} <= invariant_names,
            "candidate load sequence contains a non-invariant section")
    previous_end = 0
    for row in rows:
        require(row["lma"] >= previous_end,
                f"candidate-derived load ranges overlap: {row['name']}")
        previous_end = row["lma"] + row["bytes"]


def validate_derived(layout: dict[str, Any], golden: dict[str, Any]) -> None:
    by_name = {row["name"]: row for row in layout["allocatable_sections"]}
    overlay = by_name[".lisp65_workbench_overlay"]
    observed = layout["boundary_symbols"][V2.DERIVED_BOUNDARY]
    require(observed == overlay["vma"] + overlay["bytes"],
            "derived overlay_end disagrees with candidate section extent")
    V2.validate_capacities(layout, golden)
    validate_loads(layout, golden)


def compare_layout(layout: dict[str, Any], golden: dict[str, Any] | None = None
                   ) -> dict[str, Any]:
    authority = load(GOLDEN) if golden is None else golden
    audit_artifact(authority)
    validate_vma_order(layout, authority)
    require(invariant_projection(layout) == expected_projection(authority),
            "candidate invariant geometry differs from reviewed VMA golden")
    validate_derived(layout, authority)
    projection = invariant_projection(layout)
    derived = {
        "section_bytes": {
            row["name"]: row["bytes"]
            for row in layout["allocatable_sections"]},
        "section_lmas": {
            row["name"]: row["lma"]
            for row in layout["allocatable_sections"]},
        "boundary_symbols": {
            V2.DERIVED_BOUNDARY:
                layout["boundary_symbols"][V2.DERIVED_BOUNDARY]},
    }
    vma_order = vma_order_from_rows(layout["allocatable_sections"])
    lma_order = [row["name"] for row in candidate_file_rows(layout)]
    return {
        "comparison": "VMA-invariants-exact-candidate-freight-validated",
        "invariant_projection_sha256": sha_bytes(canonical(projection)),
        "derived_freight_sha256": sha_bytes(canonical(derived)),
        "derived_vma_order_sha256": sha_bytes(canonical(vma_order)),
        "candidate_lma_order_sha256": sha_bytes(canonical(lma_order)),
        "allocatable_sections": len(layout["allocatable_sections"]),
        "fixed_boundary_symbols": len(V2.FIXED_BOUNDARIES),
        "capacity_arenas": len(authority["capacity_arenas"]),
        "derived_vma_order_entries": len(vma_order),
        "candidate_lma_order_entries": len(lma_order),
        "capacity_measurements": V2.capacity_measurements(layout, authority),
    }


def compare_elf(path: Path) -> dict[str, Any]:
    golden_bytes()
    return compare_layout(LEGACY.layout_from_elf(path))


def reject(label: str, action: Callable[[], None], result: dict[str, str]) -> None:
    try:
        action()
    except (VmaInvariantGoldenError, V2.InvariantGoldenError,
            OWN.OwnershipError, KeyError,
            TypeError) as error:
        result[label] = str(error)
    else:
        raise VmaInvariantGoldenError(
            f"VMA-invariant mutation survived: {label}")


def _swap_distinct_vmas(layout: dict[str, Any]) -> None:
    rows = sorted(layout["allocatable_sections"],
                  key=lambda row: (row["vma"], row["name"]))
    for first, second in zip(rows, rows[1:]):
        if first["vma"] != second["vma"]:
            first["vma"], second["vma"] = second["vma"], first["vma"]
            return
    raise VmaInvariantGoldenError("no distinct VMAs available to mutate")


def _overlap_candidate_loads(layout: dict[str, Any]) -> None:
    rows = candidate_file_rows(layout)
    require(len(rows) >= 2, "candidate has fewer than two file-backed rows")
    rows[1]["lma"] = rows[0]["lma"]


def mutation_selftest() -> dict[str, str]:
    golden_bytes()
    base = load(GOLDEN)
    repaired = LEGACY.layout_from_elf(REPAIRED_WORLD_ELF)
    result: dict[str, str] = {}
    artifact_cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "LMA-load-order-stored": lambda x:
            x.update(load_order=[".basic_header"]),
        "VMA-order-snapshot-stored": lambda x:
            x.update(vma_order=[".basic_header"]),
        "invariant-VMA-demoted": lambda x:
            x["section_invariants"][0].pop("vma"),
        "snapshot-size-promoted": lambda x:
            x["section_invariants"][0].update(bytes=1),
        "snapshot-LMA-promoted": lambda x:
            x["section_invariants"][0].update(lma=0x2001),
        "LMA-sequence-frozen": lambda x:
            x["derived_fields"]["section_order"]["lma_sequence"].update(
                frozen_in_golden=True),
        "VMA-order-source-dimmed": lambda x:
            x["derived_fields"]["section_order"]["vma_geometry"].update(
                source="candidate-LMAs"),
        "capacity-wall-moved": lambda x:
            x["capacity_arenas"][0].update(end_exclusive=0x1FFF),
        "fixed-boundary-moved": lambda x:
            x["fixed_boundary_symbols"].update(__heap_start=0xC355),
        "format-changed": lambda x: x.update(format="old"),
    }
    for label, mutate in artifact_cases.items():
        candidate = deepcopy(base)
        mutate(candidate)
        reject(label, lambda candidate=candidate: (
            audit_artifact(candidate),
            require(canonical(candidate) == golden_bytes(),
                    "mutated fixed authority differs from SHA-bound golden")),
            result)

    candidate_cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "candidate-derived-VMA-order-crossed": _swap_distinct_vmas,
        "candidate-load-ranges-overlap": _overlap_candidate_loads,
        "candidate-file-section-loses-LMA": lambda x:
            next(row for row in x["allocatable_sections"]
                 if row["name"] == ".rodata").update(lma=None),
        "candidate-derived-overlay-end-lies": lambda x:
            x["boundary_symbols"].update({
                V2.DERIVED_BOUNDARY:
                    x["boundary_symbols"][V2.DERIVED_BOUNDARY] + 1}),
        "candidate-runtime-capacity-overflow": lambda x:
            next(row for row in x["allocatable_sections"]
                 if row["name"] == ".lisp65_rt_c2d_00").update(bytes=1793),
    }
    for label, mutate in candidate_cases.items():
        candidate = deepcopy(repaired)
        mutate(candidate)
        reject(label, lambda candidate=candidate: compare_layout(candidate, base),
               result)
    return result


def two_world_probe() -> dict[str, Any]:
    """Prove one VMA truth accepts both faulty and repaired LMA worlds."""
    source = LEGACY.layout_from_elf(LEGACY.FINAL_ELF)
    broken = LEGACY.layout_from_elf(BROKEN_WORLD_ELF)
    repaired = LEGACY.layout_from_elf(REPAIRED_WORLD_ELF)
    source_result = compare_layout(source)
    broken_result = compare_layout(broken)
    repaired_result = compare_layout(repaired)
    require(source_result["invariant_projection_sha256"]
            == broken_result["invariant_projection_sha256"]
            == repaired_result["invariant_projection_sha256"],
            "source/broken/repaired worlds differ in VMA geometry")
    require(broken_result["candidate_lma_order_sha256"]
            != repaired_result["candidate_lma_order_sha256"],
            "LMA delivery repair did not change candidate-derived ordering")
    broken_rows = {row["name"]: row for row in broken["allocatable_sections"]}
    repaired_rows = {
        row["name"]: row for row in repaired["allocatable_sections"]}
    for name in RESET_SECTIONS:
        require(broken_rows[name]["vma"] == repaired_rows[name]["vma"],
                f"LMA repair moved invariant VMA: {name}")
        require(broken_rows[name]["lma"] != repaired_rows[name]["lma"],
                f"LMA repair did not move candidate freight: {name}")
        require(repaired_rows[name]["lma"] == repaired_rows[name]["vma"],
                f"low-resident delivery was not restored: {name}")
    return {
        "source_world": source_result,
        "shared_defect_world": broken_result,
        "repaired_candidate_world": repaired_result,
        "reset_sections": list(RESET_SECTIONS),
        "lesson": (
            "A world pair can share a defect and therefore cannot classify "
            "an alleged invariant.  Stored fields are admitted only when "
            "derivable from VMAs; LMA-downstream facts remain candidate-local."),
    }


def closer_crc_proof() -> dict[str, Any]:
    locations = LINK._kernal_crc_binding_locations(REPAIRED_WORLD_ELF)
    mutations = LINK._kernal_crc_call_binding_model_selftest()
    require(locations["high_address"] == LINK.KERNAL_CRC_BINDING_HIGH_ADDRESS
            and locations["low_address"]
            == LINK.KERNAL_CRC_BINDING_LOW_ADDRESS,
            "closer CRC operand binding address drift")
    require(len(mutations) == 4,
            "closer CRC call-binding mutation closure drift")
    return {
        "binding": locations,
        "callee_authority": "encoded-JSR-target plus ELF symbol value",
        "objdump_display_label_authoritative": False,
        "mutations": mutations,
    }


def build_receipt() -> dict[str, Any]:
    require(sha(REPAIRED_WORLD_ELF) == REPAIRED_WORLD_ELF_SHA256,
            "repaired candidate ELF binding drift")
    mutations = mutation_selftest()
    worlds = two_world_probe()
    closer = closer_crc_proof()
    owner = git_binding(DISPOSITION_COMMIT, DISPOSITION_PATH)
    raw = subprocess.run(
        ["git", "show", f"{DISPOSITION_COMMIT}:{DISPOSITION_PATH}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    require(b"load_order` leaves the stored golden" in raw
            and b"exactly one card" in raw,
            "owner VMA-golden disposition is not bound")
    artifact = load(GOLDEN)
    return {
        "format": "lisp65-c2.3-v20-vma-invariant-golden-review-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: awaiting one-time reviewer VMA-golden review",
        "claim": (
            "Host-only review package for a VMA-only fixed authority, "
            "candidate-derived LMA validation, and the narrow closer CRC "
            "operand-locator repair; no WPLTO, card, completion, media, "
            "device, release or parity claim."),
        "vma_invariant_golden": {
            **bind(GOLDEN),
            "section_invariants": len(artifact["section_invariants"]),
            "fixed_boundary_symbols": len(V2.FIXED_BOUNDARIES),
            "capacity_arenas": len(artifact["capacity_arenas"]),
            "stored_order_fields": 0,
            "stored_section_size_fields": 0,
            "stored_section_lma_fields": 0,
        },
        "order_partition": {
            "geometry": "derived from invariant VMAs at validation time",
            "freight": "derived from each candidate's LMAs at validation time",
            "fixed_load_order": False,
        },
        "world_probe": worlds,
        "closer_crc_repair": closer,
        "mutations_rejected": mutations,
        "execution_witness": {
            "world_layout_extractions": 3,
            "VMA_invariant_comparisons": 3,
            "candidate_LMA_validations": 3,
            "golden_mutations": 10,
            "candidate_mutations": 5,
            "closer_mutations": 4,
            "fresh_wplto": 0,
            "cards_consumed": 0,
            "completion_runs": 0,
            "device_contacts": 0,
        },
        "authority": {
            "owner_disposition": owner,
            "predecessor_invariant_golden": bind(V2.GOLDEN),
            "predecessor_golden_review": bind(V2.RECEIPT),
            "LMA_repair_final_red": bind(LMA_FINAL_RED),
            "source_world_elf": bind(LEGACY.FINAL_ELF),
            "shared_defect_world_elf": bind(BROKEN_WORLD_ELF),
            "repaired_candidate_world_elf": bind(REPAIRED_WORLD_ELF),
            "invariant_gate": bind(Path(__file__).resolve()),
            "closer_gate": bind(ROOT / "tools/host-lisp/c2_product_substitution_link.py"),
        },
        "review_question": (
            "Accept the VMA-only SHA-bound golden once.  Only a later "
            "reviewer acceptance may unlock the exactly-one-card edge."),
        "card_lock": {
            "review_accepted": False,
            "card_authorized_by_this_receipt": False,
            "wplto_allowed": False,
        },
    }


def emit() -> None:
    require(not GOLDEN.exists(), "VMA invariant golden already exists")
    value = source_artifact()
    audit_artifact(value)
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_bytes(canonical(value))
    print("2.0 VMA invariant golden: EMIT PASS "
          f"sections={len(value['section_invariants'])} "
          f"stored-order=0 sha256={sha(GOLDEN)}")


def review(write: bool) -> None:
    value = build_receipt()
    if write:
        RECEIPT.write_bytes(canonical(value))
    print("2.0 VMA invariant golden: REVIEW PASS "
          f"mutations={len(value['mutations_rejected'])}+4-closer "
          "wplto=0 cards=0 review=reviewer")


def selftest() -> None:
    require(canonical(source_artifact()) == golden_bytes(),
            "VMA-only golden is not reproducible from predecessor authority")
    mutations = mutation_selftest()
    worlds = two_world_probe()
    closer_crc_proof()
    require(worlds["repaired_candidate_world"]["capacity_arenas"] == 11,
            "repaired candidate capacity closure drift")
    print("2.0 VMA invariant golden: SELFTEST PASS "
          f"mutations={len(mutations)} stored-order=0 worlds=3 card=locked")


def check() -> None:
    require(RECEIPT.is_file(), "VMA-golden review receipt absent")
    expected = build_receipt()
    actual_raw = RECEIPT.read_bytes()
    expected_raw = canonical(expected)
    if actual_raw != expected_raw:
        rebind = load(REBIND)
        require(
            rebind.get("status") ==
                "PASS: loud linker-producer authority rebind"
            and rebind.get("authority", {}).get(
                "historical_review_receipt", {}).get("sha256")
                == sha_bytes(actual_raw)
            and rebind.get("authority", {}).get(
                "live_reconstructed_review", {}).get("sha256")
                == sha_bytes(expected_raw)
            and rebind.get("change", {}).get("fields")
                == ["authority.closer_gate", "authority.invariant_gate"]
            and rebind.get("authority", {}).get(
                "authorized_linker_producer") == expected[
                    "authority"]["closer_gate"]
            and rebind.get("semantic_preservation", {}).get(
                "all_other_fields_equal") is True,
            "VMA-golden review receipt drift")
    print("2.0 VMA invariant golden: CHECK PASS "
          f"golden={GOLDEN_SHA256} card=locked")


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
        print("2.0 VMA invariant golden: COMPARE PASS "
              f"sections={result['allocatable_sections']} "
              f"VMA-order={result['derived_vma_order_entries']} "
              f"LMA-order={result['candidate_lma_order_entries']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (VmaInvariantGoldenError, V2.InvariantGoldenError,
            OWN.OwnershipError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"2.0 VMA invariant golden: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
