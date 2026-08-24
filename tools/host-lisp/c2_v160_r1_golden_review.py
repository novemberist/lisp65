#!/usr/bin/env python3
"""Build the host-only R1 two-world Golden review package.

The review is deliberately allowed to conclude that no successor artifact is
needed.  It compares the accepted v5 authority against one pre-R1 world and
the frozen R1 world, and separately identifies the authority consumed by the
acceptance path that produced the twelfth Final Red.
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

import c2_golden_layout_inversion as LAYOUT  # noqa: E402
import c2_v21_dependency_invariant_golden as V4  # noqa: E402
import c2_v21_phase9_freight_boundary_golden as V5  # noqa: E402
import c2_v160_r1_stored_world_conversions as CONVERSIONS  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
STUDY = ARCH / "c2.3-v1.6-e000-relocation-study-receipt.json"
FINAL_RED = ARCH / (
    "c2.3-v1.6-r1-scope-projection-replacement-final-red.json")
REFERENCE_ELF = ROOT / (
    "build/c2.3/v2.1-wysiwyg-text-recovery-replacement-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
CANDIDATE_ELF = ROOT / (
    "build/c2.3/v1.6-r1-scope-projection-replacement/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
RECEIPT = ARCH / "c2.3-v1.6-r1-golden-review-receipt.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "1b5c3234"
FORMAT = "lisp65-c2-v160-r1-golden-review-v1"
STATUS = "PASS: R1 TWO-WORLD GOLDEN REVIEW AWAITS OWNER"


class ReviewError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReviewError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    full = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("successor golden review", "two-worlds evidence",
                  "every differing invariant", "byte-identical",
                  "never silently regenerated", "owner's veto point"):
        require(token in text, f"R1 Golden-review authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def fixed_bytes(layout: dict[str, Any], golden: dict[str, Any]) -> bytes:
    return canonical(V5.fixed_projection(layout, golden))


def layout_differences(reference: dict[str, Any], candidate: dict[str, Any]
                       ) -> dict[str, Any]:
    old = {row["name"]: row for row in reference["allocatable_sections"]}
    new = {row["name"]: row for row in candidate["allocatable_sections"]}
    require(set(old) == set(new), "R1 changed allocatable-section membership")
    sections: list[dict[str, Any]] = []
    for name in sorted(old):
        changes = {key: {"reference": old[name].get(key),
                         "candidate": new[name].get(key)}
                   for key in sorted(set(old[name]) | set(new[name]))
                   if old[name].get(key) != new[name].get(key)}
        if changes:
            sections.append({"name": name, "changes": changes})
    boundaries = []
    names = set(reference["boundary_symbols"]) | set(
        candidate["boundary_symbols"])
    for name in sorted(names):
        before = reference["boundary_symbols"].get(name)
        after = candidate["boundary_symbols"].get(name)
        if before != after:
            boundaries.append({"name": name, "reference": before,
                               "candidate": after, "delta": after - before})
    return {"section_rows": sections, "boundary_symbols": boundaries}


def legacy_consumer() -> dict[str, Any]:
    before = CONVERSIONS.ORACLE.BASE.INV.__name__
    CONVERSIONS.DEPENDENT.configure()
    after = CONVERSIONS.ORACLE.BASE.INV.__name__
    require(after == V4.__name__ and after != V5.__name__,
            "twelfth acceptance does not resolve to reviewed v4")
    source = Path(CONVERSIONS.__file__).read_text(encoding="utf-8")
    require("ORACLE.BASE.INV.compare_elf(paths[\"elf\"])" in source,
            "acceptance consumer callsite drift")
    try:
        V4.compare_elf(CANDIDATE_ELF)
    except V4.DependencyGoldenError as error:
        rejection = str(error)
    else:
        raise ReviewError("v4 unexpectedly accepts the R1 candidate")
    require(rejection == "candidate dependent-address invariants differ from Golden",
            "v4 rejection does not match the twelfth Final Red")
    return {"callsite": (
        "c2_v160_r1_stored_world_conversions.acceptance_child -> "
        "ORACLE.BASE.INV.compare_elf"),
        "namespace_before_dependent_configuration": before,
        "namespace_consumed_after_configuration": after,
        "current_accepted_authority": V5.__name__,
        "reproduced_rejection": rejection,
        "classification": "accepted-v5-authority-not-delivered-to-consumer"}


def reject(label: str, action: Callable[[], None], out: dict[str, str]) -> None:
    try:
        action()
    except (ReviewError, V5.FreightGoldenError,
            V4.DependencyGoldenError) as error:
        out[label] = str(error)
    else:
        raise ReviewError(f"R1 Golden-review mutation survived: {label}")


def build_receipt() -> dict[str, Any]:
    authority = authorization()
    golden = load(V5.GOLDEN)
    V5.golden_bytes()
    review = load(V5.RECEIPT)
    require(review["review"]["review_accepted"] is True,
            "v5 Golden lacks accepted review authority")
    red = load(FINAL_RED)
    require(red["status"] ==
                "FINAL RED: R1 SCOPE PROJECTION REPLACEMENT RETURNS TO OWNER"
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_link_attempts"] == 1,
            "twelfth R1 Final Red authority drift")

    reference_layout = LAYOUT.layout_from_elf(REFERENCE_ELF)
    candidate_layout = LAYOUT.layout_from_elf(CANDIDATE_ELF)
    reference = V5.compare_layout(reference_layout, golden)
    candidate = V5.compare_layout(candidate_layout, golden)
    reference_fixed = fixed_bytes(reference_layout, golden)
    candidate_fixed = fixed_bytes(candidate_layout, golden)
    require(reference_fixed == candidate_fixed
            and reference["fixed_projection_sha256"] ==
                candidate["fixed_projection_sha256"],
            "R1 changed a v5 dependent-address invariant")

    differences = layout_differences(reference_layout, candidate_layout)
    section_rows = {row["name"]: row["changes"]
                    for row in differences["section_rows"]}
    boundaries = {row["name"]: row for row in differences["boundary_symbols"]}
    service = ".lisp65_c2_mapped_far_service"
    gap1 = ".lisp65_c2_kernal_window.reopen_gap1"
    require(section_rows[service]["bytes"] == {
                "reference": 1248, "candidate": 1382}
            and section_rows[gap1]["bytes"] == {
                "reference": 223, "candidate": 89}
            and boundaries[V5.END]["delta"] == 134
            and boundaries[V5.LOAD_END]["delta"] == 134,
            "R1 freight movement is not the authorized 134-byte relocation")
    invariant_differences: list[dict[str, Any]] = []

    consumer = legacy_consumer()
    mutations: dict[str, str] = {}
    moved = deepcopy(candidate_layout)
    next(row for row in moved["allocatable_sections"]
         if row["name"] == ".text")["vma"] += 1
    reject("move-dependent-vma", lambda: V5.compare_layout(moved, golden),
           mutations)
    wrong_boundary = deepcopy(candidate_layout)
    fixed_name = next(iter(golden["fixed_boundary_symbols"]))
    wrong_boundary["boundary_symbols"][fixed_name] += 1
    reject("move-fixed-boundary",
           lambda: V5.compare_layout(wrong_boundary, golden), mutations)
    reject("emit-successor-with-zero-invariant-delta",
           lambda: require(bool(invariant_differences),
                           "successor Golden requires an invariant delta"),
           mutations)
    reject("retain-v4-at-live-acceptance",
           lambda: require(consumer["namespace_consumed_after_configuration"]
                           == V5.__name__,
                           "live acceptance consumes an older Golden"),
           mutations)

    return {
        "format": FORMAT, "recorded_on": "2026-08-19", "status": STATUS,
        "claim": (
            "Host-only two-world review. The accepted v5 Golden already "
            "accepts the R1 world; no successor Golden is emitted and no "
            "acceptance replay is authorized."),
        "two_world_evidence": {
            "reference": {"artifact": bind(REFERENCE_ELF),
                "comparison": reference},
            "R1_candidate": {"artifact": bind(CANDIDATE_ELF),
                "comparison": candidate},
            "fixed_projection_byte_identical": True,
            "fixed_projection_bytes": len(reference_fixed),
            "fixed_projection_sha256": hashlib.sha256(
                reference_fixed).hexdigest(),
            "differing_invariants": invariant_differences,
            "freight_differences_not_stored_as_invariants": differences,
            "authorized_relocation_witness": {
                "source": gap1, "destination": service,
                "bytes": 134, "service_end_delta": 134,
                "service_load_end_delta": 134}},
        "decision": {
            "classification": "NO-SUCCESSOR-GOLDEN-REQUIRED",
            "reason": (
                "v5 already derives the changed freight ends and retains an "
                "identical 101-VMA/25-boundary fixed projection"),
            "golden_v6_emitted": False,
            "actual_stopper": consumer},
        "mutations_rejected": mutations,
        "execution_witness": {"layout_extractions": 2, "WPLTO_runs": 0,
            "product_links": 0, "acceptance_runs": 0, "cards_consumed": 0,
            "media_builds": 0, "device_contacts": 0},
        "authority": {"commission": authority, "R1_Final_Red": bind(FINAL_RED),
            "relocation_study": bind(STUDY), "accepted_v5_Golden": bind(V5.GOLDEN),
            "accepted_v5_review": bind(V5.RECEIPT), "driver": bind(DRIVER)},
        "review_question": (
            "Accept the no-successor finding and authorize a read-only "
            "acceptance-consumer rebind from reviewed v4 to already accepted "
            "v5 over the frozen R1 artifacts."),
        "review": {"review_accepted": False,
            "acceptance_consumer_rebind_authorized": False,
            "acceptance_replay_authorized": False,
            "new_card_authorized": False}}


def review(*, write: bool) -> None:
    value = build_receipt()
    if write:
        require(not RECEIPT.exists(), "R1 Golden-review receipt exists")
        RECEIPT.write_bytes(canonical(value))
    print("v1.6 R1 Golden review: PASS fixed=101/25 delta=0 "
          "successor=none stopper=v4-consumer")


def check() -> None:
    require(RECEIPT.is_file(), "R1 Golden-review receipt absent")
    require(RECEIPT.read_bytes() == canonical(build_receipt()),
            "R1 Golden-review receipt drift")
    print("v1.6 R1 Golden review: CHECK PASS review=pending replay=locked")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("review", "record-review", "check"))
    args = parser.parse_args()
    review(write=args.action == "record-review") if args.action != "check" \
        else check()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 R1 Golden review: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
