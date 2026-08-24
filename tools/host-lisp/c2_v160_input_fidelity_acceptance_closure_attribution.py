#!/usr/bin/env python3
"""Attribute the frozen input-fidelity Acceptance section-closure Red."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_golden_layout_inversion as LAYOUT  # noqa: E402
import c2_v21_dependency_invariant_golden as V4  # noqa: E402
import c2_v21_phase9_freight_boundary_golden as V5  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
ELF = ROOT / (
    "build/c2.3/v1.6-input-fidelity-membership-real-consumer-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
FINAL_RED = ARCH / (
    "c2.3-v1.6-input-fidelity-membership-real-consumer-card-final-red.json")
RECEIPT = ARCH / (
    "c2.3-v1.6-input-fidelity-acceptance-closure-attribution.json")
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-c2-v160-input-fidelity-acceptance-closure-attribution-v1"
STATUS = "ATTRIBUTED: ACCEPTED V5 REJECTS TWO AUTHORIZED ADDITIVE SECTIONS"
CAPTURE = {
    ".lisp65_c2_kernal_window.input_capture_main": {
        "bytes": 34, "vma": 0xFD08, "predecessor":
            ".lisp65_c2_kernal_window.reopen_gap0",
        "entry": "c2_kernal_input_capture"},
    ".lisp65_c2_kernal_window.input_capture_helper": {
        "bytes": 25, "vma": 0xFEE1, "predecessor":
            ".lisp65_c2_kernal_window.reopen_gap1",
        "entry": "c2_kernal_input_capture_commit"},
}


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


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


def run() -> dict[str, Any]:
    evidence_before = {"ELF": bind(ELF), "Final_Red": bind(FINAL_RED),
                       "accepted_v5_golden": bind(V5.GOLDEN),
                       "accepted_v5_review": bind(V5.RECEIPT)}
    require(evidence_before["ELF"]["sha256"] ==
                "4b2dfa0e7a33968863ec73f2162894ee1f644bd7ccbe6d9e745def7f376fb711",
            "frozen candidate ELF identity drift")
    red = load(FINAL_RED)
    require(red["error"]["message"].endswith(
                "candidate fixed-plus-derived section closure drift\n")
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_link_attempts"] == 1,
            "Acceptance Final Red mechanism/accounting drift")

    V5.golden_bytes()
    golden = load(V5.GOLDEN)
    layout = LAYOUT.layout_from_elf(ELF)
    candidate_names = {row["name"] for row in layout["allocatable_sections"]}
    golden_names = V4.all_names(golden)
    candidate_only = sorted(candidate_names - golden_names)
    golden_only = sorted(golden_names - candidate_names)
    require(candidate_only == sorted(CAPTURE) and golden_only == [],
            "section-closure delta is not exactly the two capture sections")

    rows = {row["name"]: row for row in layout["allocatable_sections"]}
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    capture_rows: dict[str, Any] = {}
    for name, expected in sorted(CAPTURE.items()):
        row = rows[name]
        predecessor = rows[expected["predecessor"]]
        entry = truth.symbol(expected["entry"])
        require(row["bytes"] == expected["bytes"]
                and row["vma"] == expected["vma"]
                and row["vma"] == predecessor["vma"] + predecessor["bytes"]
                and entry.section == name and entry.value == row["vma"]
                and entry.bytes == row["bytes"],
                f"capture section placement/entry drift: {name}")
        capture_rows[name] = {
            "candidate": row,
            "placement_rule": "predecessor-vma-plus-bytes",
            "predecessor": {"name": expected["predecessor"],
                "vma": predecessor["vma"], "bytes": predecessor["bytes"],
                "end_exclusive": predecessor["vma"] + predecessor["bytes"]},
            "entry_symbol": {"name": expected["entry"],
                "value": entry.value, "bytes": entry.bytes,
                "section": entry.section},
        }

    # The accepted authority is otherwise an exact fit for this candidate.
    # Removing only the two authorized additive sections must make the real
    # v5 consumer pass, proving that no fixed VMA, derived VMA, boundary or
    # capacity invariant is implicated by this Red.
    base_projection = deepcopy(layout)
    base_projection["allocatable_sections"] = [
        row for row in layout["allocatable_sections"]
        if row["name"] not in CAPTURE]
    comparison = V5.compare_layout(base_projection, golden)
    require(comparison["comparison"] ==
                "dependent-address-plus-freight-boundaries-exact"
            and comparison["allocatable_sections"] == 103
            and comparison["dependent_fixed_vmas"] == 101
            and comparison["dependent_free_derived_vmas"] == 2,
            "v5 base projection does not pass after exact additive removal")

    evidence_after = {"ELF": bind(ELF), "Final_Red": bind(FINAL_RED),
                      "accepted_v5_golden": bind(V5.GOLDEN),
                      "accepted_v5_review": bind(V5.RECEIPT)}
    require(evidence_before == evidence_after,
            "frozen Acceptance evidence changed during attribution")
    return {
        "format": FORMAT, "recorded_on": "2026-08-19", "status": STATUS,
        "claim_limit": (
            "Host-only read of the frozen Final Red, linked ELF and accepted "
            "v5 authority. No configuration, qualification, WPLTO, link, "
            "card, media or device action."),
        "frozen_evidence_before": evidence_before,
        "frozen_evidence_after": evidence_after,
        "actual_acceptance_authority": {
            "module": "c2_v21_phase9_freight_boundary_golden",
            "golden": evidence_before["accepted_v5_golden"],
            "review": evidence_before["accepted_v5_review"],
            "stored_section_closure": len(golden_names),
        },
        "closure_comparison": {
            "candidate_allocatable_sections": len(candidate_names),
            "accepted_v5_sections": len(golden_names),
            "candidate_only": candidate_only, "golden_only": golden_only,
            "capture_sections": capture_rows,
        },
        "v5_without_authorized_additive_freight": comparison,
        "classification": {
            "class": "accepted-v5-exact-closure-versus-authorized-additive-freight",
            "stale_golden_identity": False,
            "product_or_placement_failure": False,
            "non_capture_invariant_drift": False,
            "mechanism": (
                "The real Acceptance consumer correctly reads accepted v5. "
                "Its exact 103-section closure predates the two authorized, "
                "nonempty capture sections and therefore rejects the 105-"
                "section candidate before its otherwise-green invariants."),
        },
        "decision_boundary": {
            "hard_stop": "acceptance-authority-policy",
            "review_required": True,
            "successors_authorized": 0,
            "legal_reviews": [
                "review a Golden successor that owns the two new sections",
                "review an additive candidate-freight projection in Acceptance while v5 remains the base geometry authority",
            ],
            "forbidden": "silently weaken exact closure or regenerate Golden",
        },
        "attempt_accounting": {"attribution_runs": 1, "WPLTO_runs": 0,
            "product_links": 0, "cards_consumed": 0, "media_builds": 0,
            "device_contacts": 0},
        "driver": bind(DRIVER),
    }


def main() -> int:
    value = run()
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 input fidelity Acceptance closure: ATTRIBUTED "
          "candidate=105 v5=103 additive=2 successor=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
