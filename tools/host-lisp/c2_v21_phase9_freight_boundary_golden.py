#!/usr/bin/env python3
"""Build, review and consume the freight-boundary successor Golden.

The v4 Golden correctly stores dependent section VMAs, but still freezes two
end symbols that merely follow the mapped-far service freight.  This v5
authority derives those ends from the candidate section extent and keeps the
independent mapped-bank2 arena capacity fixed.
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
import c2_v20_invariant_golden as V2  # noqa: E402
import c2_v21_dependency_invariant_golden as V4  # noqa: E402
import c2_v21_phase9_service_end_dependency_attribution as ATTR  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
GOLDEN = ROOT / (
    "tests/bytecode/dialect-v2/golden-layout/"
    "c2-full-map-freight-boundary-invariants-v5.json")
RECEIPT = ARCH / (
    "c2.3-v2.1-phase9-freight-boundary-golden-review-receipt.json")
FINAL_RED = ATTR.FINAL_RED
REFERENCE_ELF = ATTR.REFERENCE_ELF
CANDIDATE_ELF = ATTR.CANDIDATE_ELF
DRIVER = Path(__file__).resolve()

AUTHORIZATION = "b1dd0379"
RECORDED_ON = "2026-08-16"
FORMAT = "lisp65-c2-full-map-freight-boundary-invariants-v5"
GOLDEN_SHA256 = "7d7ff4578fdd5f019e0d6b6e16d4d142015149e8149655c45393d6fb36289c95"

SECTION = ATTR.SECTION
END = ATTR.END
LOAD_END = ATTR.LOAD_END
FREIGHT_BOUNDARIES = (END, LOAD_END, V2.DERIVED_BOUNDARY)


class FreightGoldenError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FreightGoldenError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha_bytes(raw)}


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": sha_bytes(raw)}


def authorization() -> dict[str, Any]:
    authority = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode()
    text = " ".join(raw.lower().split())
    for token in ("dependency check, then reclassify",
                  "both end symbols reclassify as",
                  "validated against the invariant **arena capacity**",
                  "one-time golden review",
                  "artifact-only replay"):
        require(token in text, f"freight-Golden authority absent: {token}")
    return authority


def dependency_authority(*, verify: bool) -> dict[str, Any]:
    value = load(ATTR.RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    value.get("authority", {}).pop("pre_rebind", None)
    if verify:
        ATTR.validate(value)
        require(rejected == ATTR.mutations(value),
                "service-end attribution mutation receipt drift")
    require(value.get("status") == ATTR.STATUS
            and value["attribution"]["fixed_address_dependency_found"] is False
            and value["capacity_invariant"] == {
                "arena_start": 30898, "arena_end_exclusive": 32397,
                "capacity_bytes": 1499, "candidate_demand_bytes": 1086,
                "candidate_headroom_bytes": 413, "status": "PASS"},
            "service-end dependency authority drift")
    return bind(ATTR.RECEIPT)


def source_artifact() -> dict[str, Any]:
    V4.golden_bytes()
    value = deepcopy(load(V4.GOLDEN))
    old_boundaries = value["fixed_boundary_symbols"]
    require(old_boundaries[END] == 0x7C1C
            and old_boundaries[LOAD_END] == 0x2BC1C,
            "v4 service-end predecessor authority drift")
    del old_boundaries[END]
    del old_boundaries[LOAD_END]
    value["format"] = FORMAT
    value["invariant_policy"] = {
        "criterion": "addresses-with-dependents-only",
        "dependent_fixed_vmas": 101,
        "dependent_free_derived_vmas": 2,
        "fixed_boundary_symbols": 25,
        "freight_derived_boundary_symbols": 3,
        "dependency_authority": dependency_authority(verify=False),
    }
    value["derived_fields"]["boundary_symbols"] = {
        END: {"operation": "section-vma-plus-bytes", "section": SECTION,
              "frozen_in_golden": False},
        LOAD_END: {"operation": "section-lma-plus-bytes", "section": SECTION,
                   "frozen_in_golden": False},
        V2.DERIVED_BOUNDARY: {
            "operation": "section-vma-plus-bytes",
            "section": ".lisp65_workbench_overlay",
            "frozen_in_golden": False},
    }
    return value


def audit_artifact(value: dict[str, Any]) -> None:
    expected = source_artifact()
    stored_dependency = value.get("invariant_policy", {}).get(
        "dependency_authority")
    require(isinstance(stored_dependency, dict)
            and stored_dependency.get("path") ==
                ATTR.RECEIPT.relative_to(ROOT).as_posix(),
            "freight-boundary Golden loses reviewed dependency provenance")
    # Receipt hashes are review provenance, not geometry.  A loud successor
    # rebinds the current receipt in the review record without rewriting the
    # SHA-bound Golden artifact.
    expected["invariant_policy"]["dependency_authority"] = stored_dependency
    require(value == expected, "freight-boundary Golden artifact drift")
    require(len(value["section_invariants"]) == 101
            and len(value["section_vma_derivations"]) == 2
            and len(value["fixed_boundary_symbols"]) == 25
            and set(value["derived_fields"]["boundary_symbols"])
                == set(FREIGHT_BOUNDARIES),
            "freight-boundary authority cardinality drift")
    arena = [row for row in value["capacity_arenas"]
             if row["id"] == "mapped-bank2-far-service"]
    require(arena == [{"end_exclusive": 32397,
                       "id": "mapped-bank2-far-service",
                       "members": [SECTION],
                       "policy": "fixed-vma-ordered-no-overlap",
                       "space": "mapped-bank2", "start": 30898}],
            "mapped-far capacity invariant drift")


def golden_bytes() -> bytes:
    raw = GOLDEN.read_bytes()
    require(GOLDEN_SHA256 != "TO_BE_BOUND"
            and sha_bytes(raw) == GOLDEN_SHA256,
            "freight-boundary Golden SHA-256 binding drift")
    value = load(GOLDEN); audit_artifact(value)
    require(canonical(value) == raw,
            "freight-boundary Golden is not canonical JSON")
    return raw


def fixed_projection(layout: dict[str, Any], golden: dict[str, Any]
                     ) -> dict[str, Any]:
    by_name = {row["name"]: row for row in layout["allocatable_sections"]}
    return {
        "section_invariants": [
            {key: by_name[row["name"]][key] for key in sorted(V2.SECTION_KEYS)}
            for row in golden["section_invariants"]],
        "fixed_boundary_symbols": {
            name: layout["boundary_symbols"][name]
            for name in sorted(golden["fixed_boundary_symbols"])}
    }


def validate_derived_boundaries(
        layout: dict[str, Any], golden: dict[str, Any]) -> dict[str, Any]:
    rows = {row["name"]: row for row in layout["allocatable_sections"]}
    result: dict[str, Any] = {}
    for name, rule in golden["derived_fields"]["boundary_symbols"].items():
        row = rows[rule["section"]]
        if rule["operation"] == "section-vma-plus-bytes":
            expected = row["vma"] + row["bytes"]
        elif rule["operation"] == "section-lma-plus-bytes":
            require(row["lma"] is not None,
                    f"derived boundary section lacks LMA: {name}")
            expected = row["lma"] + row["bytes"]
        else:
            raise FreightGoldenError(f"unknown derived boundary operation: {name}")
        require(layout["boundary_symbols"][name] == expected,
                f"candidate derived boundary disagrees with extent: {name}")
        result[name] = {"value": expected, "section": rule["section"],
                        "operation": rule["operation"]}
    return result


def compare_layout(layout: dict[str, Any], golden: dict[str, Any] | None = None
                   ) -> dict[str, Any]:
    authority = load(GOLDEN) if golden is None else golden
    audit_artifact(authority)
    V4.validate_section_closure(layout, authority)
    fixed = fixed_projection(layout, authority)
    expected = {"section_invariants": authority["section_invariants"],
                "fixed_boundary_symbols": authority["fixed_boundary_symbols"]}
    require(fixed == expected,
            "candidate dependent-address invariants differ from v5 Golden")
    derived_vmas = V4.validate_derived_vmas(layout, authority)
    derived_boundaries = validate_derived_boundaries(layout, authority)
    V2.validate_capacities(layout, authority)
    V4.validate_loads(layout, authority)
    measurements = V2.capacity_measurements(layout, authority)
    service = [row for row in measurements
               if row["id"] == "mapped-bank2-far-service"]
    require(len(service) == 1
            and service[0]["end_exclusive"] - service[0]["start"] == 1499,
            "mapped-far capacity measurement drift")
    freight = {"section_bytes": {row["name"]: row["bytes"]
                                  for row in layout["allocatable_sections"]},
               "section_lmas": {row["name"]: row["lma"]
                                 for row in layout["allocatable_sections"]},
               "boundary_symbols": derived_boundaries}
    return {
        "comparison": "dependent-address-plus-freight-boundaries-exact",
        "fixed_projection_sha256": sha_bytes(canonical(fixed)),
        "derived_vmas": derived_vmas,
        "derived_boundaries": derived_boundaries,
        "derived_freight_sha256": sha_bytes(canonical(freight)),
        "allocatable_sections": len(layout["allocatable_sections"]),
        "dependent_fixed_vmas": 101,
        "dependent_free_derived_vmas": 2,
        "fixed_boundary_symbols": 25,
        "freight_derived_boundary_symbols": 3,
        "capacity_arenas": 11,
        "capacity_measurements": measurements,
        "mapped_far_service_capacity": service[0],
    }


def compare_elf(path: Path) -> dict[str, Any]:
    golden_bytes()
    return compare_layout(LEGACY.layout_from_elf(path))


def reject(label: str, action: Callable[[], None], result: dict[str, str]) -> None:
    try:
        action()
    except (FreightGoldenError, V2.InvariantGoldenError, KeyError, TypeError) as error:
        result[label] = str(error)
    else:
        raise FreightGoldenError(f"freight-boundary mutation survived: {label}")


def artifact_mutations() -> dict[str, str]:
    base = load(GOLDEN)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "cpu-end-repromoted": lambda x: x["fixed_boundary_symbols"].update(
            {END: 0x7C1C}),
        "load-end-repromoted": lambda x: x["fixed_boundary_symbols"].update(
            {LOAD_END: 0x2BC1C}),
        "cpu-end-derivation-dimmed": lambda x: x["derived_fields"][
            "boundary_symbols"][END].update(operation="candidate-value"),
        "load-end-derivation-dimmed": lambda x: x["derived_fields"][
            "boundary_symbols"][LOAD_END].update(operation="candidate-value"),
        "dependency-authority-path-lost": lambda x: x["invariant_policy"][
            "dependency_authority"].update(path="wrong-receipt.json"),
        "capacity-wall-moved": lambda x: next(row for row in x[
            "capacity_arenas"] if row["id"] == "mapped-bank2-far-service").update(
                end_exclusive=0x7CF0),
        "dependent-start-demoted": lambda x: x["section_invariants"].remove(
            next(row for row in x["section_invariants"] if row["name"] == SECTION)),
    }
    result: dict[str, str] = {}
    for name, mutate in cases.items():
        trial = deepcopy(base); mutate(trial)
        reject(name, lambda trial=trial: audit_artifact(trial), result)
    return result


def _row(layout: dict[str, Any], name: str) -> dict[str, Any]:
    return next(row for row in layout["allocatable_sections"]
                if row["name"] == name)


def candidate_mutations() -> dict[str, str]:
    base = load(GOLDEN)
    layout = LEGACY.layout_from_elf(CANDIDATE_ELF)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "cpu-end-does-not-follow-freight": lambda x: x["boundary_symbols"].update(
            {END: x["boundary_symbols"][END] - 1}),
        "load-end-does-not-follow-freight": lambda x: x[
            "boundary_symbols"].update({LOAD_END: x["boundary_symbols"][LOAD_END] - 1}),
        "service-exceeds-capacity": lambda x: _row(x, SECTION).update(bytes=1500),
        "service-start-anchor-moved": lambda x: _row(x, SECTION).update(vma=0x78B3),
        "service-load-start-moved": lambda x: _row(x, SECTION).update(lma=0x2B8B3),
    }
    result: dict[str, str] = {}
    for name, mutate in cases.items():
        trial = deepcopy(layout); mutate(trial)
        reject(name, lambda trial=trial: compare_layout(trial, base), result)
    return result


def world_probe() -> dict[str, Any]:
    reference = compare_elf(REFERENCE_ELF)
    candidate = compare_elf(CANDIDATE_ELF)
    require(reference["fixed_projection_sha256"]
            == candidate["fixed_projection_sha256"]
            and reference["derived_boundaries"][END]["value"] == 0x7C1C
            and candidate["derived_boundaries"][END]["value"] == 0x7CF0
            and reference["derived_boundaries"][LOAD_END]["value"] == 0x2BC1C
            and candidate["derived_boundaries"][LOAD_END]["value"] == 0x2BCF0,
            "two-world freight-boundary probe drift")
    return {"reference_874_bytes": reference, "candidate_1086_bytes": candidate,
            "shared_fixed_projection": True,
            "different_valid_freight_boundaries": True,
            "authorized_delta_bytes": 212}


def build_receipt() -> dict[str, Any]:
    dependency = dependency_authority(verify=True)
    worlds = world_probe()
    golden_cases = artifact_mutations()
    candidate_cases = candidate_mutations()
    return {
        "format": "lisp65-c2.3-v2.1-phase9-freight-boundary-golden-review-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: freight-boundary Golden reviewed and accepted",
        "claim": (
            "One-time host review of v5: 101 fixed VMAs, 25 fixed boundaries, "
            "three freight-derived boundaries and 11 fixed capacity arenas."),
        "golden": {**bind(GOLDEN), "dependent_fixed_vmas": 101,
                   "dependent_free_derived_vmas": 2,
                   "fixed_boundary_symbols": 25,
                   "freight_derived_boundary_symbols": 3,
                   "capacity_arenas": 11},
        "world_probe": worlds,
        "permanent_policy": {
            "fixed": "addresses with independent dependents",
            "freight_derived": "end values that follow candidate extents",
            "capacity": "mapped-far service must fit 1499-byte arena"},
        "mutations_rejected": {"golden": golden_cases,
                               "candidate": candidate_cases},
        "execution_witness": {"world_layout_extractions": 2,
            "golden_mutations": len(golden_cases),
            "candidate_mutations": len(candidate_cases),
            "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "authority": {"owner": authorization(),
            "dependency_attribution": dependency,
            "predecessor_golden": bind(V4.GOLDEN),
            "predecessor_review": bind(V4.RECEIPT),
            "Final_Red": bind(FINAL_RED), "reference_ELF": bind(REFERENCE_ELF),
            "candidate_ELF": bind(CANDIDATE_ELF), "driver": bind(DRIVER)},
        "review": {"review_accepted": True,
                   "artifact_only_replay_authorized": True,
                   "new_card_authorized": False},
    }


def emit() -> None:
    require(not GOLDEN.exists(), "freight-boundary Golden already exists")
    value = source_artifact()
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_bytes(canonical(value))
    print(f"2.1 freight-boundary Golden: EMIT PASS sha256={sha_bytes(GOLDEN.read_bytes())}")


def review(*, write: bool) -> None:
    golden_bytes()
    value = build_receipt()
    if write:
        require(not RECEIPT.exists(), "freight-boundary review receipt exists")
        RECEIPT.write_bytes(canonical(value))
    print("2.1 freight-boundary Golden: REVIEW PASS fixed=101/25 derived=2/3")


def selftest() -> None:
    raw = golden_bytes(); persisted = load(GOLDEN)
    expected = source_artifact()
    expected["invariant_policy"]["dependency_authority"] = persisted[
        "invariant_policy"]["dependency_authority"]
    require(canonical(expected) == raw,
            "freight-boundary Golden semantic body is not reproducible")
    require(len(artifact_mutations()) == 7 and len(candidate_mutations()) == 5,
            "freight-boundary mutation closure drift")
    world_probe()
    print("2.1 freight-boundary Golden: SELFTEST PASS mutations=7+5")


def check() -> None:
    require(RECEIPT.is_file(), "freight-boundary review receipt absent")
    require(RECEIPT.read_bytes() == canonical(build_receipt()),
            "freight-boundary review receipt drift")
    print(f"2.1 freight-boundary Golden: CHECK PASS golden={GOLDEN_SHA256}")


def rebind() -> None:
    old = load(RECEIPT)
    expected = build_receipt()
    comparison = deepcopy(expected)
    comparison["authority"]["dependency_attribution"] = old[
        "authority"]["dependency_attribution"]
    comparison["authority"]["driver"] = old["authority"]["driver"]
    comparison["mutations_rejected"]["golden"] = old[
        "mutations_rejected"]["golden"]
    require(old == comparison,
            "freight-boundary rebind moved more than desk authorities")
    RECEIPT.write_bytes(canonical(expected))
    print("2.1 freight-boundary Golden: REBIND PASS product-change=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "emit", "review", "record-review", "rebind", "selftest", "check",
        "compare"))
    parser.add_argument("--elf", type=Path)
    args = parser.parse_args()
    if args.action == "emit": emit()
    elif args.action == "review": review(write=False)
    elif args.action == "record-review": review(write=True)
    elif args.action == "rebind": rebind()
    elif args.action == "selftest": selftest()
    elif args.action == "check": check()
    else:
        require(args.elf is not None, "compare requires --elf")
        result = compare_elf(args.elf)
        print("2.1 freight-boundary Golden: COMPARE PASS "
              f"fixed={result['dependent_fixed_vmas']}/"
              f"{result['fixed_boundary_symbols']} derived="
              f"{result['dependent_free_derived_vmas']}/"
              f"{result['freight_derived_boundary_symbols']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
