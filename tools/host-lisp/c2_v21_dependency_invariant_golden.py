#!/usr/bin/env python3
"""Build and review the dependent-address successor to the VMA golden.

The v3 authority stored every allocatable section VMA.  The v2.1 card proved
that two reopening sections have no numeric-address consumer: their starts are
defined solely as the ends of predecessor sections.  This successor keeps
fixed VMAs only for the reviewed dependent-address set and validates the two
derived VMAs by their named predecessor-end relations.
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
import c2_v20_vma_invariant_golden as V3  # noqa: E402
import c2_v21_reopen_gap_dependency_attribution as ATTR  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
GOLDEN = ROOT / (
    "tests/bytecode/dialect-v2/golden-layout/"
    "c2-full-map-dependent-vma-invariants-v4.json")
RECEIPT = ARCH / (
    "c2.3-v2.1-dependent-vma-invariant-golden-review-receipt.json")
FINAL_RED = ARCH / "c2.3-v2.1-postlink-schema-replacement-card-final-red.json"
REFERENCE_ELF = ROOT / (
    "build/c2.3/v2.0-source-oracle-replacement3-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
CANDIDATE_ELF = ROOT / (
    "build/c2.3/v2.1-postlink-schema-replacement-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "30129087"
RECORDED_ON = "2026-08-14"
FORMAT = "lisp65-c2-full-map-dependent-vma-invariants-v4"
GOLDEN_SHA256 = "28190ae2e5c3f02b229a3cea257ef3ca5b98f76ac19b35ef77f1f48dc318f1f3"

GAP0 = ".lisp65_c2_kernal_window.reopen_gap0"
GAP1 = ".lisp65_c2_kernal_window.reopen_gap1"
GAP2 = ".lisp65_c2_kernal_window.reopen_gap2"
RESIDENT = ".lisp65_c2_kernal_window.c2_resident"
PROFILE = ".lisp65_c2_kernal_window.profile_rodata"
DERIVED = {GAP0: RESIDENT, GAP1: PROFILE}
DERIVED_NAMES = tuple(sorted(DERIVED))
DERIVATION_KEYS = {
    "alignment", "flags", "name", "relation", "section_type"}
TOP_KEYS = {
    "capacity_arenas", "derived_fields", "fixed_boundary_symbols", "format",
    "invariant_policy", "section_invariants", "section_vma_derivations"}


class DependencyGoldenError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise DependencyGoldenError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


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
    relative = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{relative}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": relative,
            "bytes": len(raw), "sha256": sha_bytes(raw)}


def authorization() -> dict[str, Any]:
    authority = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in (
            "golden reclassification authorized",
            "`reopen_gap0` and `reopen_gap1` reclassify as",
            "invariants are addresses with dependents",
            "mutations both ways",
            "exactly one card"):
        require(token in text, f"Golden reclassification authorization absent: {token}")
    return authority


def dependency_authority(*, verify: bool) -> dict[str, Any]:
    value = load(ATTR.RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    if verify:
        ATTR.validate(value)
    require(
        value.get("status") == ATTR.STATUS
        and value.get("attribution", {}).get("outcome") == "NOT-DEPENDED-UPON"
        and value.get("attribution", {}).get(
            "fixed_address_dependency_found") is False
        and value.get("sibling_classification", {}).get(GAP0, {}).get(
            "recommended_golden_class") == "derived-vma"
        and value.get("sibling_classification", {}).get(GAP1, {}).get(
            "recommended_golden_class") == "derived-vma"
        and value.get("sibling_classification", {}).get(GAP2, {}).get(
            "recommended_golden_class") == "unchanged-fixed-vma"
        and isinstance(rejected, list) and len(rejected) == 10,
        "reopen-gap dependency authority drift")
    return bind(ATTR.RECEIPT)


def source_artifact() -> dict[str, Any]:
    V3.golden_bytes()
    value = deepcopy(load(V3.GOLDEN))
    V3.audit_artifact(value)
    rows = {row["name"]: row for row in value["section_invariants"]}
    require(set(DERIVED) <= set(rows) and rows[GAP2]["vma"] == 0xFF90,
            "v3 reopening rows do not support authorized partition")

    derivations: list[dict[str, Any]] = []
    for name, predecessor in sorted(DERIVED.items()):
        row = rows.pop(name)
        derivations.append({
            "alignment": row["alignment"], "flags": row["flags"],
            "name": name, "section_type": row["section_type"],
            "relation": {"kind": "predecessor-end",
                         "predecessor": predecessor},
        })
    value["section_invariants"] = [rows[name] for name in sorted(rows)]
    value["section_vma_derivations"] = derivations
    value["format"] = FORMAT
    value["invariant_policy"] = {
        "criterion": "addresses-with-dependents-only",
        "dependent_fixed_vmas": len(rows),
        "dependent_free_derived_vmas": len(derivations),
        "dependency_authority": dependency_authority(verify=False),
    }
    value["derived_fields"]["section_vmas"] = {
        "frozen_in_golden": False,
        "sections": list(DERIVED_NAMES),
        "source": "candidate-elf-section-table",
        "validation": "named-predecessor-end-relations",
    }
    value["derived_fields"]["section_order"]["vma_geometry"] = {
        "frozen_in_golden": False,
        "operation": "sort-by-vma-then-identity-at-validation-time",
        "source": "fixed-golden-vmas-plus-validated-derived-vmas",
    }
    return value


def audit_artifact(value: dict[str, Any]) -> None:
    require(set(value) == TOP_KEYS,
            "dependent-VMA Golden top-level shape drift")
    require(value["format"] == FORMAT, "dependent-VMA Golden format drift")

    fixed = value["section_invariants"]
    require(isinstance(fixed, list) and len(fixed) == 101,
            "dependent fixed-VMA closure drift")
    fixed_names: list[str] = []
    for row in fixed:
        require(isinstance(row, dict) and set(row) == V2.SECTION_KEYS,
                "fixed section invariant contains freight or loses VMA truth")
        require(isinstance(row["name"], str) and row["name"]
                and isinstance(row["vma"], int) and row["vma"] >= 0
                and isinstance(row["alignment"], int) and row["alignment"] > 0
                and isinstance(row["section_type"], str)
                and row["section_type"]
                and isinstance(row["flags"], list)
                and row["flags"] == sorted(set(row["flags"])),
                "invalid fixed section invariant")
        fixed_names.append(row["name"])
    require(fixed_names == sorted(set(fixed_names)),
            "fixed section invariants are duplicated or non-canonical")
    v3 = load(V3.GOLDEN)
    expected_fixed = [row for row in v3["section_invariants"]
                      if row["name"] not in DERIVED]
    require(fixed == expected_fixed,
            "inherited dependent fixed-VMA authority drift")
    require(GAP0 not in fixed_names and GAP1 not in fixed_names,
            "dependent-free reopening VMA was promoted to invariant")
    gap2 = [row for row in fixed if row["name"] == GAP2]
    require(len(gap2) == 1 and gap2[0]["vma"] == 0xFF90,
            "dependent gap2 anchor was demoted or moved")

    derived = value["section_vma_derivations"]
    require(isinstance(derived, list) and len(derived) == 2,
            "derived reopening closure drift")
    derived_names: list[str] = []
    v3_rows = {row["name"]: row for row in v3["section_invariants"]}
    for row in derived:
        require(isinstance(row, dict) and set(row) == DERIVATION_KEYS,
                "derived VMA contains a frozen address or loses metadata")
        name = row["name"]
        require(name in DERIVED and row["relation"] == {
            "kind": "predecessor-end", "predecessor": DERIVED[name]},
            f"derived predecessor relation drift: {name}")
        expected = {key: v3_rows[name][key]
                    for key in ("alignment", "flags", "name", "section_type")}
        require({key: row[key] for key in expected} == expected,
                f"derived section metadata drift: {name}")
        derived_names.append(name)
    require(tuple(derived_names) == DERIVED_NAMES,
            "derived reopening identities are non-canonical")

    policy = value["invariant_policy"]
    require(policy == {
        "criterion": "addresses-with-dependents-only",
        "dependent_fixed_vmas": 101,
        "dependent_free_derived_vmas": 2,
        "dependency_authority": dependency_authority(verify=False),
    }, "dependent-address policy or authority drift")

    boundaries = value["fixed_boundary_symbols"]
    require(isinstance(boundaries, dict)
            and boundaries == v3["fixed_boundary_symbols"]
            and tuple(sorted(boundaries)) == V2.FIXED_BOUNDARIES
            and V2.DERIVED_BOUNDARY not in boundaries
            and all(isinstance(item, int) and item >= 0
                    for item in boundaries.values()),
            "fixed boundary closure drift")

    fields = value["derived_fields"]
    require(isinstance(fields, dict) and set(fields) == {
        "boundary_symbols", "section_bytes", "section_lmas",
        "section_order", "section_vmas"},
        "derived field closure drift")
    require(fields["section_bytes"] == {
        "source": "candidate-elf-section-table",
        "validation": "fixed-capacity-arenas",
        "frozen_in_golden": False,
    }, "section-size derivation drift")
    require(fields["section_lmas"] == {
        "source": "candidate-elf-program-headers",
        "validation": "candidate-local-complete-and-non-overlapping",
        "frozen_in_golden": False,
    }, "section-LMA derivation drift")
    require(fields["section_vmas"] == {
        "frozen_in_golden": False,
        "sections": list(DERIVED_NAMES),
        "source": "candidate-elf-section-table",
        "validation": "named-predecessor-end-relations",
    }, "derived-VMA field rule drift")
    require(fields["section_order"] == {
        "vma_geometry": {
            "source": "fixed-golden-vmas-plus-validated-derived-vmas",
            "operation": "sort-by-vma-then-identity-at-validation-time",
            "frozen_in_golden": False,
        },
        "lma_sequence": {
            "source": "candidate-elf-program-headers",
            "operation": "sort-by-lma-then-identity-at-validation-time",
            "frozen_in_golden": False,
        },
    }, "VMA/LMA order derivation partition drift")
    require(fields["boundary_symbols"] == {
        V2.DERIVED_BOUNDARY: {
            "operation": "section-vma-plus-bytes",
            "section": ".lisp65_workbench_overlay",
            "frozen_in_golden": False,
        },
    }, "derived overlay-end rule drift")

    arenas = value["capacity_arenas"]
    require(isinstance(arenas, list) and len(arenas) == 11,
            "capacity arena closure drift")
    require(arenas == v3["capacity_arenas"],
            "inherited capacity arena authority drift")
    owned: list[str] = []
    arena_ids: list[str] = []
    for arena in arenas:
        require(isinstance(arena, dict) and set(arena) == {
            "end_exclusive", "id", "members", "policy", "space", "start"},
            "capacity arena shape drift")
        require(isinstance(arena["start"], int)
                and isinstance(arena["end_exclusive"], int)
                and arena["start"] < arena["end_exclusive"]
                and arena["policy"] in {
                    "fixed-vma-ordered-no-overlap",
                    "fixed-vma-ordered-zero-alias-only",
                    "independent-alternate-overlay"}
                and isinstance(arena["members"], list) and arena["members"],
                f"invalid capacity arena: {arena.get('id')}")
        arena_ids.append(arena["id"])
        owned.extend(arena["members"])
    require(arena_ids == list(dict.fromkeys(arena_ids)),
            "duplicate capacity arena identity")
    require(sorted(owned) == sorted(fixed_names + derived_names),
            "capacity arenas do not own fixed plus derived section closure")


def golden_bytes() -> bytes:
    raw = GOLDEN.read_bytes()
    require(sha_bytes(raw) == GOLDEN_SHA256,
            "dependent-VMA Golden SHA-256 binding drift")
    value = load(GOLDEN)
    audit_artifact(value)
    require(canonical(value) == raw,
            "dependent-VMA Golden is not canonical JSON")
    return raw


def all_names(golden: dict[str, Any]) -> set[str]:
    return ({row["name"] for row in golden["section_invariants"]}
            | {row["name"] for row in golden["section_vma_derivations"]})


def fixed_projection(layout: dict[str, Any], golden: dict[str, Any]
                     ) -> dict[str, Any]:
    by_name = {row["name"]: row for row in layout["allocatable_sections"]}
    return {
        "section_invariants": [
            {key: by_name[row["name"]][key] for key in sorted(V2.SECTION_KEYS)}
            for row in golden["section_invariants"]],
        "fixed_boundary_symbols": {
            name: layout["boundary_symbols"][name]
            for name in V2.FIXED_BOUNDARIES},
    }


def expected_fixed_projection(golden: dict[str, Any]) -> dict[str, Any]:
    return {"section_invariants": golden["section_invariants"],
            "fixed_boundary_symbols": golden["fixed_boundary_symbols"]}


def validate_section_closure(layout: dict[str, Any],
                             golden: dict[str, Any]) -> None:
    names = [row["name"] for row in layout["allocatable_sections"]]
    require(len(names) == len(set(names)), "candidate section identity duplicated")
    require(set(names) == all_names(golden),
            "candidate fixed-plus-derived section closure drift")


def validate_derived_vmas(layout: dict[str, Any], golden: dict[str, Any]
                          ) -> dict[str, Any]:
    by_name = {row["name"]: row for row in layout["allocatable_sections"]}
    result: dict[str, Any] = {}
    for rule in golden["section_vma_derivations"]:
        name = rule["name"]
        predecessor = rule["relation"]["predecessor"]
        row = by_name[name]
        parent = by_name[predecessor]
        metadata = {key: row[key]
                    for key in ("alignment", "flags", "name", "section_type")}
        expected = {key: rule[key] for key in metadata}
        require(metadata == expected,
                f"candidate derived-section metadata drift: {name}")
        expected_vma = parent["vma"] + parent["bytes"]
        require(row["vma"] == expected_vma,
                f"candidate derived VMA violates predecessor end: {name}")
        result[name] = {"vma": row["vma"], "predecessor": predecessor,
                        "predecessor_end": expected_vma}
    return result


def candidate_file_rows(layout: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted([
        row for row in layout["allocatable_sections"]
        if row["lma"] is not None and row["bytes"] > 0
        and row["section_type"] != "SHT_NOBITS"],
        key=lambda row: (row["lma"], row["name"]))


def validate_loads(layout: dict[str, Any], golden: dict[str, Any]) -> None:
    expected = [row for row in layout["allocatable_sections"]
                if row["bytes"] > 0 and row["section_type"] != "SHT_NOBITS"]
    require(all(row["lma"] is not None for row in expected),
            "candidate file-backed section lacks a derived LMA")
    rows = candidate_file_rows(layout)
    require({row["name"] for row in rows} <= all_names(golden),
            "candidate load sequence contains an uncontracted section")
    previous_end = 0
    for row in rows:
        require(row["lma"] >= previous_end,
                f"candidate-derived load ranges overlap: {row['name']}")
        previous_end = row["lma"] + row["bytes"]


def compare_layout(layout: dict[str, Any], golden: dict[str, Any] | None = None
                   ) -> dict[str, Any]:
    authority = load(GOLDEN) if golden is None else golden
    audit_artifact(authority)
    validate_section_closure(layout, authority)
    fixed = fixed_projection(layout, authority)
    require(fixed == expected_fixed_projection(authority),
            "candidate dependent-address invariants differ from Golden")
    derived = validate_derived_vmas(layout, authority)
    by_name = {row["name"]: row for row in layout["allocatable_sections"]}
    overlay = by_name[".lisp65_workbench_overlay"]
    require(layout["boundary_symbols"][V2.DERIVED_BOUNDARY]
            == overlay["vma"] + overlay["bytes"],
            "derived overlay_end disagrees with candidate section extent")
    V2.validate_capacities(layout, authority)
    validate_loads(layout, authority)

    freight = {
        "section_bytes": {row["name"]: row["bytes"]
                          for row in layout["allocatable_sections"]},
        "section_lmas": {row["name"]: row["lma"]
                         for row in layout["allocatable_sections"]},
        "boundary_symbols": {V2.DERIVED_BOUNDARY:
            layout["boundary_symbols"][V2.DERIVED_BOUNDARY]},
    }
    vma_order = [row["name"] for row in sorted(
        layout["allocatable_sections"],
        key=lambda row: (row["vma"], row["name"]))]
    lma_order = [row["name"] for row in candidate_file_rows(layout)]
    return {
        "comparison": "dependent-address-invariants-plus-derived-vmas-exact",
        "fixed_projection_sha256": sha_bytes(canonical(fixed)),
        "derived_vmas": derived,
        "derived_vma_projection_sha256": sha_bytes(canonical(derived)),
        "derived_freight_sha256": sha_bytes(canonical(freight)),
        "derived_vma_order_sha256": sha_bytes(canonical(vma_order)),
        "candidate_lma_order_sha256": sha_bytes(canonical(lma_order)),
        "allocatable_sections": len(layout["allocatable_sections"]),
        "dependent_fixed_vmas": len(authority["section_invariants"]),
        "dependent_free_derived_vmas": len(
            authority["section_vma_derivations"]),
        "fixed_boundary_symbols": len(V2.FIXED_BOUNDARIES),
        "capacity_arenas": len(authority["capacity_arenas"]),
        "capacity_measurements": V2.capacity_measurements(layout, authority),
    }


def compare_elf(path: Path) -> dict[str, Any]:
    golden_bytes()
    return compare_layout(LEGACY.layout_from_elf(path))


def reject(label: str, action: Callable[[], None],
           result: dict[str, str]) -> None:
    try:
        action()
    except (DependencyGoldenError, V2.InvariantGoldenError, KeyError,
            TypeError) as error:
        result[label] = str(error)
    else:
        raise DependencyGoldenError(
            f"dependent-VMA mutation survived: {label}")


def _demote_anchor(value: dict[str, Any]) -> None:
    row = next(row for row in value["section_invariants"]
               if row["name"] == GAP2)
    value["section_invariants"].remove(row)
    value["section_vma_derivations"].append({
        "alignment": row["alignment"], "flags": row["flags"],
        "name": GAP2, "section_type": row["section_type"],
        "relation": {"kind": "predecessor-end", "predecessor": GAP1},
    })
    value["section_vma_derivations"].sort(key=lambda item: item["name"])


def _promote_dependent_free(value: dict[str, Any]) -> None:
    row = next(row for row in value["section_vma_derivations"]
               if row["name"] == GAP0)
    value["section_vma_derivations"].remove(row)
    predecessor = next(item for item in load(V3.GOLDEN)["section_invariants"]
                       if item["name"] == GAP0)
    value["section_invariants"].append(predecessor)
    value["section_invariants"].sort(key=lambda item: item["name"])


def artifact_mutations() -> dict[str, str]:
    golden_bytes()
    base = load(GOLDEN)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "dependent-anchor-demoted": _demote_anchor,
        "dependent-free-address-promoted": _promote_dependent_free,
        "derived-vma-frozen": lambda x: x["section_vma_derivations"][0].update(
            vma=0xFCB0),
        "derived-predecessor-changed": lambda x: x[
            "section_vma_derivations"][0]["relation"].update(
                predecessor=PROFILE),
        "derived-relation-dimmed": lambda x: x[
            "section_vma_derivations"][0]["relation"].update(kind="adjacent"),
        "dependency-authority-changed": lambda x: x["invariant_policy"][
            "dependency_authority"].update(sha256="0" * 64),
        "criterion-dimmed": lambda x: x["invariant_policy"].update(
            criterion="all-vmas"),
        "derived-order-source-reverted": lambda x: x["derived_fields"][
            "section_order"]["vma_geometry"].update(
                source="golden-section-invariant-vmas"),
        "capacity-wall-moved": lambda x: x["capacity_arenas"][0].update(
            end_exclusive=0x2018),
        "fixed-boundary-moved": lambda x: x["fixed_boundary_symbols"].update(
            __heap_start=0xC355),
    }
    result: dict[str, str] = {}
    for label, mutate in cases.items():
        candidate = deepcopy(base)
        mutate(candidate)
        reject(label, lambda candidate=candidate: audit_artifact(candidate),
               result)
    return result


def _row(layout: dict[str, Any], name: str) -> dict[str, Any]:
    return next(row for row in layout["allocatable_sections"]
                if row["name"] == name)


def candidate_mutations() -> dict[str, str]:
    base = load(GOLDEN)
    layout = LEGACY.layout_from_elf(CANDIDATE_ELF)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "gap0-breaks-predecessor-end": lambda x: _row(x, GAP0).update(
            vma=_row(x, GAP0)["vma"] + 1),
        "gap1-breaks-predecessor-end": lambda x: _row(x, GAP1).update(
            vma=_row(x, GAP1)["vma"] + 1),
        "gap0-predecessor-size-unfollowed": lambda x: _row(
            x, RESIDENT).update(bytes=_row(x, RESIDENT)["bytes"] + 1),
        "gap2-anchor-moved": lambda x: _row(x, GAP2).update(vma=0xFF91),
        "other-fixed-vma-moved": lambda x: _row(x, ".text").update(
            vma=_row(x, ".text")["vma"] + 1),
        "derived-section-absent": lambda x: x["allocatable_sections"].remove(
            _row(x, GAP1)),
        "uncontracted-section-added": lambda x: x[
            "allocatable_sections"].append({
                "alignment": 1, "bytes": 1, "flags": ["SHF_ALLOC"],
                "lma": 0x70000, "name": ".uncontracted", "section_type":
                "SHT_PROGBITS", "vma": 0x7000}),
    }
    result: dict[str, str] = {}
    for label, mutate in cases.items():
        candidate = deepcopy(layout)
        mutate(candidate)
        reject(label, lambda candidate=candidate: compare_layout(candidate, base),
               result)
    return result


def world_probe() -> dict[str, Any]:
    reference = compare_elf(REFERENCE_ELF)
    candidate = compare_elf(CANDIDATE_ELF)
    require(reference["fixed_projection_sha256"]
            == candidate["fixed_projection_sha256"],
            "reference/candidate fixed dependent-address truth differs")
    require(reference["derived_vmas"][GAP0]["vma"] == 0xFCB0
            and candidate["derived_vmas"][GAP0]["vma"] == 0xFCAF
            and reference["derived_vmas"][GAP1]["vma"]
                == candidate["derived_vmas"][GAP1]["vma"] == 0xFE88
            and reference["derived_vma_projection_sha256"]
                != candidate["derived_vma_projection_sha256"],
            "world probe did not isolate the authorized derived VMA")
    return {
        "reference_v2_0": reference,
        "candidate_v2_1": candidate,
        "shared_fixed_projection": True,
        "different_valid_derived_projection": True,
        "lesson": (
            "Both worlds satisfy one dependent-address authority. The "
            "changed gap0 value is accepted only because the independent "
            "dependency attribution classifies its predecessor-end relation; "
            "world agreement is not the classifier."),
    }


def build_receipt() -> dict[str, Any]:
    dependency = dependency_authority(verify=True)
    owner = authorization()
    artifact_cases = artifact_mutations()
    candidate_cases = candidate_mutations()
    worlds = world_probe()
    artifact = load(GOLDEN)
    audit_artifact(artifact)
    final_red = load(FINAL_RED)
    require(final_red.get("status") ==
            "FINAL RED: post-link schema replacement returns to owner",
            "schema replacement Final Red authority drift")
    return {
        "format": "lisp65-c2.3-v2.1-dependent-vma-golden-review-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: awaiting one-time dependent-VMA Golden review",
        "claim": (
            "Host-only review package for 101 dependent fixed VMAs and two "
            "candidate-derived predecessor-end VMAs. No WPLTO, card, "
            "Completion, media, device or release claim."),
        "dependent_vma_golden": {
            **bind(GOLDEN),
            "dependent_fixed_vmas": len(artifact["section_invariants"]),
            "dependent_free_derived_vmas": len(
                artifact["section_vma_derivations"]),
            "fixed_boundary_symbols": len(V2.FIXED_BOUNDARIES),
            "capacity_arenas": len(artifact["capacity_arenas"]),
            "stored_gap0_vma": False,
            "stored_gap1_vma": False,
            "stored_gap2_vma": "0xff90",
        },
        "permanent_policy": {
            "criterion": "invariants-are-addresses-with-dependents",
            "derived": "addresses-that-merely-arise",
            "gap0_validation": "end-of-c2_resident",
            "gap1_validation": "end-of-profile_rodata",
            "gap2_validation": "fixed-0xff90",
        },
        "world_probe": worlds,
        "mutations_rejected": {
            "golden": artifact_cases,
            "candidate": candidate_cases,
        },
        "execution_witness": {
            "world_layout_extractions": 2,
            "dependent_address_comparisons": 2,
            "golden_mutations": len(artifact_cases),
            "candidate_mutations": len(candidate_cases),
            "fresh_wplto": 0, "cards_consumed": 0,
            "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0,
        },
        "authority": {
            "owner_reclassification": owner,
            "dependency_attribution": dependency,
            "predecessor_vma_golden": bind(V3.GOLDEN),
            "predecessor_vma_golden_review": bind(V3.RECEIPT),
            "postlink_schema_card_final_red": bind(FINAL_RED),
            "reference_v2_0_elf": bind(REFERENCE_ELF),
            "candidate_v2_1_elf": bind(CANDIDATE_ELF),
            "invariant_gate": bind(DRIVER),
        },
        "review_question": (
            "Accept the dependent-address SHA-bound Golden once. Only a "
            "later reviewer acceptance may unlock exactly one replacement "
            "card under the unchanged producer and qualification authorities."),
        "card_lock": {
            "review_accepted": False,
            "card_authorized_by_this_receipt": False,
            "wplto_allowed": False,
        },
    }


def emit() -> None:
    require(not GOLDEN.exists(), "dependent-VMA Golden already exists")
    value = source_artifact()
    audit_artifact(value)
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_bytes(canonical(value))
    print("2.1 dependent-VMA Golden: EMIT PASS "
          f"fixed={len(value['section_invariants'])} "
          f"derived={len(value['section_vma_derivations'])} sha256={sha(GOLDEN)}")


def review(*, write: bool) -> None:
    value = build_receipt()
    if write:
        require(not RECEIPT.exists(), "dependent-VMA review receipt exists")
        RECEIPT.write_bytes(canonical(value))
    print("2.1 dependent-VMA Golden: REVIEW PASS fixed=101 derived=2 "
          "mutations=10+7 wplto=0 cards=0 review=owner")


def selftest() -> None:
    require(canonical(source_artifact()) == golden_bytes(),
            "dependent-VMA Golden is not reproducible from v3 plus authority")
    dependency_authority(verify=True)
    artifact_cases = artifact_mutations()
    candidate_cases = candidate_mutations()
    worlds = world_probe()
    require(len(artifact_cases) == 10 and len(candidate_cases) == 7
            and worlds["shared_fixed_projection"] is True,
            "dependent-VMA mutation/world closure drift")
    print("2.1 dependent-VMA Golden: SELFTEST PASS fixed=101 derived=2 "
          "mutations=10+7 card=locked")


def check() -> None:
    require(RECEIPT.is_file(), "dependent-VMA review receipt absent")
    require(RECEIPT.read_bytes() == canonical(build_receipt()),
            "dependent-VMA review receipt drift")
    print(f"2.1 dependent-VMA Golden: CHECK PASS golden={GOLDEN_SHA256} "
          "review=pending card=locked")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "emit", "selftest", "review", "write-review", "check", "compare"))
    parser.add_argument("--elf", type=Path)
    args = parser.parse_args()
    if args.action == "emit":
        emit()
    elif args.action == "selftest":
        selftest()
    elif args.action in ("review", "write-review"):
        review(write=args.action == "write-review")
    elif args.action == "check":
        check()
    else:
        require(args.elf is not None, "compare requires --elf")
        result = compare_elf(args.elf)
        print("2.1 dependent-VMA Golden: COMPARE PASS "
              f"sections={result['allocatable_sections']} "
              f"fixed={result['dependent_fixed_vmas']} "
              f"derived={result['dependent_free_derived_vmas']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DependencyGoldenError, V2.InvariantGoldenError,
            OSError, ValueError, KeyError, TypeError,
            subprocess.CalledProcessError) as error:
        print(f"2.1 dependent-VMA Golden: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
