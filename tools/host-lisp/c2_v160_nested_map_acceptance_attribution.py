#!/usr/bin/env python3
"""Attribute the post-swap Acceptance freight-authority red read-only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v160_r1_stored_world_conversions as ACCEPT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RED = ARCH / "c2.3-v1.6-nested-map-swap-replacement-card-final-red.json"
ELF = (ROOT / "build/c2.3/v1.6-nested-map-swap-replacement-card/wplto/"
       "lisp65-c2-substitution-linked.prg.elf")
RECEIPT = ARCH / "c2.3-v1.6-nested-map-swap-acceptance-attribution.json"
STATUS = "ATTRIBUTED: ACCEPTANCE OMITTED WITNESS CARD-FREIGHT AUTHORITY"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def compute() -> dict[str, Any]:
    red = ACCEPT.load(RED)
    require(red["status"] ==
                "FINAL RED: V1.6 NESTED MAP SWAP REPLACEMENT STOPS"
            and "neither Golden nor card-freight authority" in
                red["error"]["message"], "Acceptance Final Red drift")
    layout = ACCEPT.LAYOUT.layout_from_elf(ELF)
    golden = ACCEPT.load(ACCEPT.V5_GOLDEN.GOLDEN)
    golden_names = ACCEPT.V4_GOLDEN.all_names(golden)
    candidate_names = {row["name"] for row in layout["allocatable_sections"]}
    capture = PRODUCT.input_capture_inventory_registration((
        PRODUCT.INPUT_CAPTURE_FEATURE, PRODUCT.INPUT_HYBRID_FEATURE))
    witness = PRODUCT.refill_witness_inventory_registration((
        PRODUCT.REFILL_WITNESS_FEATURE,))
    capture_names = set(capture["allocated"])
    witness_names = set(witness["allocated"])
    current_registered = capture_names
    complete_registered = capture_names | witness_names
    current_unowned = candidate_names - golden_names - current_registered
    complete_unowned = candidate_names - golden_names - complete_registered
    require(current_unowned == {".lisp65_c2_mapped_diagnostic"}
            and complete_unowned == set()
            and candidate_names == golden_names | complete_registered,
            "Acceptance authority attribution did not close exactly")
    return {"format": "lisp65-c2-v160-nested-map-acceptance-attribution-v1",
        "status": STATUS,
        "inputs": {"Final_Red": bind(RED), "frozen_candidate_ELF": bind(ELF),
            "accepted_v5_Golden": bind(ACCEPT.V5_GOLDEN.GOLDEN)},
        "worlds": {"candidate_section_count": len(candidate_names),
            "golden_section_count": len(golden_names),
            "acceptance_registered_sections": sorted(current_registered),
            "acceptance_unowned_sections": sorted(current_unowned),
            "complete_card_freight_sections": sorted(complete_registered),
            "complete_unowned_sections": sorted(complete_unowned)},
        "registries": {"input_capture": capture, "refill_witness": witness},
        "decision": {"product_fault": False, "MAP_swap_fault": False,
            "Golden_change_required": False,
            "class": "additive card-freight authority projection omission",
            "mechanism": ("Acceptance unions v5 only with the input-capture "
                          "registry; the active refill-witness registry owns "
                          "the sole remaining candidate section but is never "
                          "projected into that union"),
            "minimal_successor": ("derive additive freight from the union of "
                "all active build-configuration registries, prove each row's "
                "own placement gate, then run read-only Acceptance over the "
                "frozen linked pair; no WPLTO, relink or product card")},
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0},
        "authorization_boundary": ("Attribution only. Self-disposition budget "
            "is exhausted; no successor or Acceptance resume is authorized.")}


def check(value: dict[str, Any]) -> None:
    require(value["status"] == STATUS
            and value["worlds"]["acceptance_unowned_sections"] ==
                [".lisp65_c2_mapped_diagnostic"]
            and value["worlds"]["complete_unowned_sections"] == []
            and value["decision"]["Golden_change_required"] is False
            and value["attempt_accounting"] == {"cards_consumed": 0,
                "WPLTO_runs": 0, "product_links": 0,
                "media_builds": 0, "device_contacts": 0},
            "nested-MAP Acceptance attribution drift")


def main(argv: list[str]) -> int:
    require(len(argv) == 2 and argv[1] in ("write", "check"),
            "usage: write|check")
    if argv[1] == "write":
        require(not RECEIPT.exists(), "attribution receipt is one-shot")
        value = compute(); check(value)
        RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    else:
        value = ACCEPT.load(RECEIPT); check(value)
        require(bind(RED) == value["inputs"]["Final_Red"]
                and bind(ELF) == value["inputs"]["frozen_candidate_ELF"],
                "attribution evidence identity drift")
    print("v1.6 nested MAP Acceptance attribution: PASS "
          "unowned=.lisp65_c2_mapped_diagnostic")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (AttributionError, OSError, KeyError, ValueError) as error:
        print(f"v1.6 nested MAP Acceptance attribution: RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
