#!/usr/bin/env python3
"""Convert the r3 annex successor pin and inventory qualification resolvers."""

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

import block_26_f011_acceptance_successor_red as RED  # noqa: E402
import block_26_f011_map_abort_repair_product_card as CARD  # noqa: E402
import c2_v160_r1_stored_world_conversions as ACCEPT  # noqa: E402
import evidence_era as ERA


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
AUTHORIZATION = "9d790352"
PLAN_HEADER = (
    "## Reviewer disposition — card 2 r3 annex successor; resume authorized — 2026-09-03"
)
RECEIPT = ARCH / "block-2.6-card2-f011-r3-acceptance-successor-conversion.json"
REPORT = ROOT / "docs/planning/2.6-card2-f011-r3-acceptance-successor-conversion.md"
FORMAT = "lisp65-block-2.6-card2-f011-r3-acceptance-successor-conversion-v1"
INVENTORY_SEAL = 'c02a20fa'
STATUS = "PASS: R3 ANNEX SUCCESSOR AND QUALIFICATION POPULATION CONVERTED"


class SuccessorConversionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SuccessorConversionError(message)


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
    require(text.count(PLAN_HEADER) == 1, "annex conversion authority drift")
    payload = (PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]).split(
        "\n## ", 1)[0].rstrip().encode() + b"\n"
    folded = " ".join(payload.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("aligned successor", "adjacency mutation",
                  "read-only", "no wplto", "call graph"):
        require(token in folded, f"annex authority token absent: {token}")
    return {"commit": AUTHORIZATION, "path": relative,
        "section": PLAN_HEADER, "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "frozen_successor_red": bind(RED.RECEIPT)}


def converted_acceptance_seam() -> dict[str, Any]:
    """Reach the real v5 comparison while recording predecessor proofs."""
    captured: dict[str, Any] = {}
    original_successor = ACCEPT.candidate_fixed_successors
    original_mutations = ACCEPT.candidate_fixed_successor_mutations

    def successor(layout: dict[str, Any], authority_value: dict[str, Any]
                  ) -> dict[str, Any]:
        value = original_successor(layout, authority_value)
        captured["candidate_successors"] = value
        return value

    def mutations(layout: dict[str, Any], authority_value: dict[str, Any]
                  ) -> list[str]:
        value = original_mutations(layout, authority_value)
        captured["mutations_rejected"] = value
        return value

    ACCEPT.candidate_fixed_successors = successor
    ACCEPT.candidate_fixed_successor_mutations = mutations
    try:
        projection = RED.capture_fixed_projection()
    finally:
        ACCEPT.candidate_fixed_successors = original_successor
        ACCEPT.candidate_fixed_successor_mutations = original_mutations
    require(projection == {"section_differences": [],
                           "boundary_differences": []},
            "converted sealed-v5 comparison retains a fixed projection pin")
    proof = captured.get("candidate_successors", {})
    rejected = captured.get("mutations_rejected", [])
    require(proof.get("resident_island", {}).get("annex_vma") ==
                proof.get("resident_island", {}).get("derived_annex_vma")
            and proof.get("resident_island", {}).get(
                "combined_margin_bytes") == 28
            and rejected[-1:] == ["resident-annex-adjacency-diverges"],
            "annex successor proof or sharp mutation absent")
    return {"sealed_comparison_projection": projection,
        "candidate_successors": proof, "mutations_rejected": rejected}


def derive() -> dict[str, Any]:
    seam = converted_acceptance_seam()
    population = ACCEPT.qualification_resolver_population()
    population_mutations = ACCEPT.qualification_resolver_population_mutations()
    return {"format": FORMAT, "recorded_on": "2026-09-03",
        "status": STATUS, "authority": authority(),
        "frozen_pair": {"ELF": bind(CARD.ELF), "PRG": bind(CARD.PRG)},
        "acceptance_seam": seam,
        "qualification_resolver_inventory": population,
        "qualification_population_mutations_rejected": population_mutations,
        "era_policy": {
            "sealed_v5_modified": False,
            "candidate_proof_precedes_normalization": True,
            "normalization_scope": [
                ".lisp65_resident_island_annex.vma"],
            "successor_red_remains_sealed": True},
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "next": "commit conversion, then resume Acceptance read-only over r3"}


def report(value: dict[str, Any]) -> str:
    island = value["acceptance_seam"]["candidate_successors"]["resident_island"]
    inventory = value["qualification_resolver_inventory"]
    return f"""# Block 2.6 Card 2 — r3 annex-successor conversion

Status: **{value['status']}**

The final-ELF candidate proof derives the annex at `{island['annex_vma']:#x}`
from the resident-island end plus its emitted {island['annex_alignment']}-byte
alignment. The proof runs before normalization and the broken-adjacency
mutation falls. Only the sealed-v5 comparison view is normalized; its fixed
section and boundary difference sets are now both empty. The sealed Golden is
unchanged.

The pre-resume inventory now derives **{inventory['resolver_count_derived']}**
candidate-world resolvers transitively from `acceptance_golden_gate`. Omitting
a reachable resolver, adding an uninventoried resolver, or removing the root
all fall. This extends the historical 7+6 prelink inventory into the
qualification chain without adding another hand-maintained member list.

The conversion used zero WPLTOs, links, media builds or device contacts. The
next operation is the authorized read-only Acceptance resume over the same r3
pair.
"""


def validate(value: dict[str, Any]) -> None:
    seam = value["acceptance_seam"]
    island = seam["candidate_successors"]["resident_island"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["frozen_pair"] == {
                "ELF": bind(CARD.ELF), "PRG": bind(CARD.PRG)}
            and seam["sealed_comparison_projection"] == {
                "section_differences": [], "boundary_differences": []}
            and island["annex_vma"] == island["derived_annex_vma"]
            and island["combined_margin_bytes"] == 28
            and seam["mutations_rejected"][-1] ==
                "resident-annex-adjacency-diverges"
            and ACCEPT.validate_qualification_resolver_population(
                value["qualification_resolver_inventory"],
                ERA.era_blob(INVENTORY_SEAL,
                    ACCEPT.DRIVER.relative_to(ROOT).as_posix()).decode()) ==
                value["qualification_resolver_inventory"]
            and value["qualification_population_mutations_rejected"] == [
                "reachable-qualification-resolver-omitted",
                "new-qualification-resolver-uninventoried",
                "qualification-root-removed"]
            and value["attempt_accounting"]["WPLTO_runs"] == 0
            and value["attempt_accounting"]["product_links"] == 0,
            "annex successor conversion drift")


def write() -> None:
    require(not RECEIPT.exists() and not REPORT.exists(),
            "annex successor conversion is one-shot")
    value = derive(); RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    validate(value)
    print("Block 2.6 Card 2: ANNEX SUCCESSOR CONVERSION PASS")


def check() -> None:
    value = load(RECEIPT); validate(value)
    # Historical membership belongs to the recorded source generation. The
    # current population is independently derived and mutation-checked, never
    # trimmed to fit the old eight-member receipt.
    live = ACCEPT.qualification_resolver_population()
    ACCEPT.validate_qualification_resolver_population(live)
    ACCEPT.qualification_resolver_population_mutations()
    require(REPORT.read_text(encoding="utf-8") == report(value),
            "annex successor conversion report drift")
    print("Block 2.6 Card 2: ANNEX SUCCESSOR CONVERSION CHECK PASS")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "adjacency-mutation-lost": lambda row: row["acceptance_seam"][
            "mutations_rejected"].remove("resident-annex-adjacency-diverges"),
        "sealed-comparison-remainder": lambda row: row["acceptance_seam"][
            "sealed_comparison_projection"]["section_differences"].append({}),
        "qualification-resolver-omitted": lambda row: row[
            "qualification_resolver_inventory"]["resolvers"].pop(),
        "live-population-in-sealed-receipt": lambda row: row.update(
            qualification_resolver_inventory=ACCEPT.qualification_resolver_population()),
        "link-hidden": lambda row: row["attempt_accounting"].update(
            product_links=1),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (SuccessorConversionError, ACCEPT.ConversionError, RuntimeError,
                KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "annex conversion mutation survived")
    print(f"Block 2.6 Card 2: ANNEX CONVERSION SELFTEST mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    {"write": write, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SuccessorConversionError, ACCEPT.ConversionError, RuntimeError,
            KeyError, ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Block 2.6 Card 2 annex conversion: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
