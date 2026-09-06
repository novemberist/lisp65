#!/usr/bin/env python3
"""Seal the r3 annex conversion's projection-vs-geometry fixture red."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import block_26_f011_map_abort_repair_product_card as CARD  # noqa: E402
import c2_v160_r1_stored_world_conversions as ACCEPT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PREDECESSOR = ARCH / "block-2.6-card2-f011-r3-acceptance-successor-conversion.json"
RECEIPT = ARCH / "block-2.6-card2-f011-r3-acceptance-normalization-red.json"
REPORT = ROOT / "docs/planning/2.6-card2-f011-r3-acceptance-normalization-red.md"
FORMAT = "lisp65-block-2.6-card2-f011-r3-acceptance-normalization-red-v1"
STATUS = "FROZEN: ANNEX PROOF GREEN; WHOLE-LAYOUT NORMALIZATION RED"


class NormalizationRedError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise NormalizationRedError(message)


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


def derive() -> dict[str, Any]:
    previous = load(PREDECESSOR)
    truth = ElfTruth.read(CARD.ELF, llvm_readobj=CARD.READOBJ)
    island = truth.section(".lisp65_resident_island")
    annex = truth.section(".lisp65_resident_island_annex")
    sealed_annex = previous["authority"]["frozen_successor_red"]
    red = load(ROOT / sealed_annex["path"])
    v5_vma = red["exact_fixed_projection_difference"][
        "section_differences"][0]["sealed_v5"]["vma"]
    overlap = max(0, island.address + island.bytes - v5_vma)
    require(previous["acceptance_seam"]["sealed_comparison_projection"] == {
                "section_differences": [], "boundary_differences": []}
            and annex.address == previous["acceptance_seam"][
                "candidate_successors"]["resident_island"]["derived_annex_vma"]
            and overlap == 21,
            "normalization red arithmetic drift")
    return {"format": FORMAT, "recorded_on": "2026-09-03",
        "status": STATUS, "predecessor_conversion": bind(PREDECESSOR),
        "frozen_pair": {"ELF": bind(CARD.ELF), "PRG": bind(CARD.PRG)},
        "observed_error":
            "owned VMA ranges overlap: .lisp65_resident_island_annex",
        "geometry": {"live_island": {"start": island.address,
            "end_exclusive": island.address + island.bytes},
            "live_annex_vma": annex.address,
            "sealed_v5_annex_vma": v5_vma,
            "whole-layout_normalization_overlap_bytes": overlap},
        "attribution": {
            "classification": "checker-conversion-fixture-defect",
            "mechanism": ("the conversion replaced annex VMA in the layout "
                "consumed by downstream capacity/load geometry, rather than "
                "only in the sealed fixed-projection comparison"),
            "fixture_blind_spot": ("the conversion probe intercepted at "
                "compare_layout entry and never executed its downstream "
                "capacity/load checks"),
            "product_defect_established": False,
            "unexplained_members": 0},
        "attempt_accounting": {"additional_WPLTO_runs": 0,
            "additional_product_links": 0, "read_only_acceptance_attempts": 1,
            "media_builds": 0, "device_contacts": 0},
        "correction": ("normalize annex only in fixed_projection; retain the "
            "unaltered candidate layout for every geometry consumer")}


def report(value: dict[str, Any]) -> str:
    geometry = value["geometry"]
    return f"""# Block 2.6 Card 2 — r3 annex normalization red

Status: **{value['status']}**

The Annex successor proof itself is green. The second read-only Resume exposed
a defect in its conversion fixture: replacing the live annex VMA with sealed
v5's `{geometry['sealed_v5_annex_vma']:#x}` in the whole layout overlaps the
live Island extent by **{geometry['whole-layout_normalization_overlap_bytes']} bytes**.
The actual derived annex remains correctly placed at
`{geometry['live_annex_vma']:#x}`.

The conversion probe had intercepted `compare_layout` at entry, so it proved
the fixed projection empty without exercising downstream capacity/load
geometry. The correction is projection-only normalization: compare the annex
as a reviewed derived successor for the fixed-v5 equality, while every later
consumer sees the untouched candidate layout.

No product artifact changed. This read-only attempt used zero WPLTOs, links,
media builds or device contacts; no product defect is established.
"""


def validate(value: dict[str, Any]) -> None:
    current = derive()
    require(value == current and value["status"] == STATUS
            and value["geometry"]["whole-layout_normalization_overlap_bytes"] == 21
            and value["attribution"]["product_defect_established"] is False
            and value["attempt_accounting"]["additional_WPLTO_runs"] == 0
            and value["attempt_accounting"]["additional_product_links"] == 0,
            "annex normalization-red drift")


def write() -> None:
    require(not RECEIPT.exists() and not REPORT.exists(),
            "annex normalization red is one-shot")
    value = derive(); RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    validate(value)
    print("Block 2.6 Card 2: ANNEX NORMALIZATION RED checker-fixture=true")


def check() -> None:
    value = load(RECEIPT); validate(value)
    require(REPORT.read_text(encoding="utf-8") == report(value),
            "annex normalization-red report drift")
    print("Block 2.6 Card 2: ANNEX NORMALIZATION RED CHECK product-defect=false")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "overlap-hidden": lambda row: row["geometry"].update(
            whole_layout_normalization_overlap_bytes=0),
        "fixture-blind-spot-hidden": lambda row: row["attribution"].update(
            fixture_blind_spot=""),
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
        except (NormalizationRedError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "normalization-red mutation survived")
    print(f"Block 2.6 Card 2: NORMALIZATION RED SELFTEST mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    {"write": write, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (NormalizationRedError, RuntimeError, KeyError, ValueError,
            OSError) as error:
        print(f"Block 2.6 Card 2 normalization red: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
