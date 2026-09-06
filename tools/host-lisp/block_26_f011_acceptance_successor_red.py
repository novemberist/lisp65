#!/usr/bin/env python3
"""Freeze Card 2 r3 at the next v5 fixed-successor checker pin."""

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

import block_26_f011_map_abort_repair_product_card as CARD  # noqa: E402
import c2_v160_r1_stored_world_conversions as ACCEPT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
AUTHORIZATION = "f06a2647"
PLAN_HEADER = (
    "## Reviewer disposition — card 2 r3 Acceptance prover; resume authorized — 2026-09-03"
)
CONVERSION = ARCH / "block-2.6-card2-f011-r3-acceptance-placement-conversion.json"
FIRST_RED = ARCH / "block-2.6-card2-f011-product-r3-acceptance-red.json"
RECEIPT = ARCH / "block-2.6-card2-f011-product-r3-acceptance-successor-red.json"
REPORT = ROOT / "docs/planning/2.6-card2-f011-product-r3-acceptance-successor-red.md"
FORMAT = "lisp65-block-2.6-card2-f011-r3-acceptance-successor-red-v1"
STATUS = "FROZEN: F011 PLACEMENT PROVER GREEN; V5 ANNEX VMA PIN RED"


class SuccessorRedError(RuntimeError):
    pass


class ProjectionCaptured(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SuccessorRedError(message)


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


def authority() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(PLAN_HEADER) == 1, "r3 resume authority drift")
    payload = (PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]).split(
        "\n## ", 1)[0].rstrip().encode() + b"\n"
    return {"commit": AUTHORIZATION, "path": relative,
        "section": PLAN_HEADER, "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest()}


def capture_fixed_projection() -> dict[str, Any]:
    """Capture the exact comparison inputs at the real Acceptance seam."""
    captured: dict[str, Any] = {}
    original = ACCEPT.V5_GOLDEN.compare_layout

    def intercept(layout: dict[str, Any], golden: dict[str, Any] | None = None
                  ) -> dict[str, Any]:
        authority_value = (ACCEPT.V5_GOLDEN.load(ACCEPT.V5_GOLDEN.GOLDEN)
                           if golden is None else golden)
        fixed = ACCEPT.V5_GOLDEN.fixed_projection(layout, authority_value)
        expected = {"section_invariants": authority_value["section_invariants"],
                    "fixed_boundary_symbols":
                        authority_value["fixed_boundary_symbols"]}
        actual_sections = {row["name"]: row
                           for row in fixed["section_invariants"]}
        expected_sections = {row["name"]: row
                             for row in expected["section_invariants"]}
        section_differences = [{"name": name,
            "candidate": actual_sections.get(name),
            "sealed_v5": expected_sections.get(name)}
            for name in sorted(set(actual_sections) | set(expected_sections))
            if actual_sections.get(name) != expected_sections.get(name)]
        boundary_differences = [{"name": name,
            "candidate": fixed["fixed_boundary_symbols"].get(name),
            "sealed_v5": expected["fixed_boundary_symbols"].get(name)}
            for name in sorted(set(fixed["fixed_boundary_symbols"]) |
                               set(expected["fixed_boundary_symbols"]))
            if fixed["fixed_boundary_symbols"].get(name) !=
               expected["fixed_boundary_symbols"].get(name)]
        captured.update({"section_differences": section_differences,
                         "boundary_differences": boundary_differences})
        raise ProjectionCaptured("fixed projection captured")

    ACCEPT.V5_GOLDEN.compare_layout = intercept
    try:
        CARD.patch_card()
        CARD.R2.CARD.child("_accept")
    except ProjectionCaptured:
        pass
    finally:
        ACCEPT.V5_GOLDEN.compare_layout = original
    require(captured, "real Acceptance seam did not reach v5 fixed projection")
    return captured


def successor_facts(projection: dict[str, Any]) -> dict[str, Any]:
    truth = CARD.R2.CARD.ElfTruth.read(CARD.ELF,
        llvm_readobj=CARD.READOBJ)
    island = truth.section(".lisp65_resident_island")
    annex = truth.section(".lisp65_resident_island_annex")
    differences = projection["section_differences"]
    require(len(differences) == 1 and differences[0]["name"] ==
            ".lisp65_resident_island_annex",
            "annex successor projection is not unique")
    candidate = differences[0]["candidate"]
    alignment = candidate["alignment"]
    require(candidate["vma"] == annex.address,
            "captured annex projection differs from final ELF")
    derived_annex = (island.address + island.bytes + alignment - 1) & ~(
        alignment - 1)
    return {"island": {"vma": island.address, "bytes": island.bytes,
                       "end_exclusive": island.address + island.bytes},
        "annex": {"vma": annex.address, "bytes": annex.bytes,
                  "alignment": alignment,
                  "end_exclusive": annex.address + annex.bytes},
        "derived_annex_vma": derived_annex,
        "adjacent_after_alignment": annex.address == derived_annex,
        "resident_island_floor_margin_bytes": 0x2000 -
            (annex.address + annex.bytes)}


def derive() -> dict[str, Any]:
    projection = capture_fixed_projection()
    facts = successor_facts(projection)
    require(projection["boundary_differences"] == []
            and len(projection["section_differences"]) == 1
            and projection["section_differences"][0]["name"] ==
                ".lisp65_resident_island_annex"
            and projection["section_differences"][0]["candidate"]["vma"] ==
                facts["annex"]["vma"] == facts["derived_annex_vma"]
            and facts["adjacent_after_alignment"]
            and facts["resident_island_floor_margin_bytes"] == 28,
            "r3 successor red is not the one derived annex-VMA pin")
    return {"format": FORMAT, "recorded_on": "2026-09-03",
        "status": STATUS, "authority": authority(),
        "frozen_pair": {"ELF": bind(CARD.ELF), "PRG": bind(CARD.PRG),
            "LTO_object": bind(Path(str(CARD.PRG) + ".lto.o")),
            "link_map": bind(Path(str(CARD.PRG) + ".map"))},
        "preceding_checker_conversion": bind(CONVERSION),
        "preceding_acceptance_red": bind(FIRST_RED),
        "observed_error":
            "candidate dependent-address invariants differ from v5 Golden",
        "exact_fixed_projection_difference": projection,
        "candidate_successor_facts": facts,
        "attribution": {
            "classification": "sealed-v5-dependent-address-pin",
            "consumer": "phase9 freight-boundary Golden fixed projection",
            "mechanism": ("the candidate-derived resident-island end moved, "
                "and its aligned annex successor followed; Acceptance normalizes "
                "the end but still compares the annex VMA to sealed v5"),
            "product_defect_established": False,
            "first_conversion_effective": True,
            "unexplained_members": 0},
        "qualification": {"scope_status": "PASS",
            "acceptance_status": "RED-CHECKER-WORLD",
            "packed_prefilter_runs": 0, "device_contacts": 0},
        "attempt_accounting": {"additional_WPLTO_runs": 0,
            "additional_product_links": 0, "read_only_acceptance_attempts": 1,
            "media_builds": 0, "device_contacts": 0},
        "requested_disposition": ("prove the annex VMA as the aligned successor "
            "of the final resident-island extent, add a broken-adjacency mutation, "
            "normalize only the sealed comparison view, then resume read-only")}


def report(value: dict[str, Any]) -> str:
    diff = value["exact_fixed_projection_difference"]["section_differences"][0]
    facts = value["candidate_successor_facts"]
    return f"""# Block 2.6 Card 2 — r3 Acceptance successor red

Status: **{value['status']}**

The authorized semantic F011 placement prover is effective: Acceptance passed
that seam and stopped one layer later at the v5 fixed projection. The exact
projection diff has one member and no boundary remainder:
`.lisp65_resident_island_annex` VMA `{diff['sealed_v5']['vma']:#x}` →
`{diff['candidate']['vma']:#x}`.

The final ELF explains the successor mechanically. The resident island ends at
`{facts['island']['end_exclusive']:#x}`; applying the annex's
{facts['annex']['alignment']}-byte alignment derives `{facts['derived_annex_vma']:#x}`
exactly. Island plus annex retains {facts['resident_island_floor_margin_bytes']}
bytes before `$2000`, already above the final-product floor. Acceptance had
normalized the candidate-derived island end but still pinned its immediate
aligned successor to the sealed v5 address.

This is a second checker-world stop, not a product red. The r3 ELF/PRG/LTO/map
identities remain frozen; this attempt used zero WPLTOs, links, media builds or
device contacts. Proposed disposition is the established candidate-successor
conversion with a broken-adjacency mutation, followed by another read-only
resume. No such conversion is performed by this report.
"""


def validate(value: dict[str, Any]) -> None:
    differences = value["exact_fixed_projection_difference"]
    facts = successor_facts(differences)
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["frozen_pair"]["ELF"] == bind(CARD.ELF)
            and value["frozen_pair"]["PRG"] == bind(CARD.PRG)
            and value["preceding_checker_conversion"] == bind(CONVERSION)
            and differences["boundary_differences"] == []
            and len(differences["section_differences"]) == 1
            and differences["section_differences"][0]["name"] ==
                ".lisp65_resident_island_annex"
            and value["candidate_successor_facts"] == facts
            and facts["adjacent_after_alignment"]
            and value["attribution"]["product_defect_established"] is False
            and value["attribution"]["unexplained_members"] == 0
            and value["attempt_accounting"]["additional_WPLTO_runs"] == 0
            and value["attempt_accounting"]["additional_product_links"] == 0,
            "Card-2 r3 Acceptance successor-red drift")


def write() -> None:
    require(not RECEIPT.exists() and not REPORT.exists(),
            "Card-2 r3 Acceptance successor red is one-shot")
    value = derive(); RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    validate(value)
    print("Block 2.6 Card 2 r3: ACCEPTANCE SUCCESSOR RED annex=derived")


def check() -> None:
    value = load(RECEIPT); validate(value)
    require(REPORT.read_text(encoding="utf-8") == report(value),
            "Card-2 r3 Acceptance successor-red report drift")
    print("Block 2.6 Card 2 r3: SUCCESSOR RED CHECK product-defect=false")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "extra-projection-member-hidden": lambda row: row[
            "exact_fixed_projection_difference"]["boundary_differences"].append(
                {"name": "mutation", "candidate": 1, "sealed_v5": 0}),
        "derived-adjacency-hidden": lambda row: row[
            "candidate_successor_facts"].update(adjacent_after_alignment=False),
        "product-red-hidden": lambda row: row["attribution"].update(
            product_defect_established=True),
        "link-hidden": lambda row: row["attempt_accounting"].update(
            additional_product_links=1),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (SuccessorRedError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "Acceptance successor-red mutation survived")
    print(f"Block 2.6 Card 2 r3: SUCCESSOR RED SELFTEST mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    {"write": write, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SuccessorRedError, RuntimeError, KeyError, ValueError, OSError,
            subprocess.CalledProcessError) as error:
        print(f"Block 2.6 Card 2 Acceptance successor red: FAIL {error}",
              file=sys.stderr)
        raise SystemExit(1)
