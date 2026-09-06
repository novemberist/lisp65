#!/usr/bin/env python3
"""Freeze Card 2 r3 at its incomplete Acceptance placement prover."""

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

import block_26_f011_map_abort_repair_product_card as CARD  # noqa: E402
import c2_v160_r1_stored_world_conversions as ACCEPT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = ARCH / "block-2.6-card2-f011-product-r3-acceptance-red.json"
REPORT = ROOT / "docs/planning/2.6-card2-f011-product-r3-acceptance-red.md"
FORMAT = "lisp65-block-2.6-card2-f011-product-r3-acceptance-red-v1"
STATUS = "FROZEN: CARD 2 R3 PRODUCT GREEN; ACCEPTANCE PLACEMENT PROVER INCOMPLETE"


class RedError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RedError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def placement_facts() -> dict[str, Any]:
    CARD.R2.PRODUCT.select_f011_cold_world()
    registries = CARD.R2.PRODUCT.active_card_freight_registries()
    f011_registry = [row for row in registries
                     if row["registry"] == "block-26-f011-cold-read"]
    require(len(f011_registry) == 1, "active F011 freight registry absent")
    registry = f011_registry[0]
    registered = {name for row in registries for name in row["allocated"]}
    layout = ACCEPT.LAYOUT.layout_from_elf(CARD.ELF, packed_prg=CARD.PRG,
        allowed_flat_packed_sections=registered)
    by_name = {row["name"]: row for row in layout["allocatable_sections"]}
    owner = by_name[".lisp65_c2_mapped_f011_cold"]
    far = by_name[".lisp65_c2_mapped_far_service"]
    owner_offset = owner["lma"] - owner["vma"]
    far_offset = far["lma"] - far["vma"]
    checks = {
        "owner-positive-and-within-capacity": (
            0 < owner["bytes"] <= registry["registration"]["capacity_bytes"]),
        "owner-ends-at-far-vma": owner["vma"] + owner["bytes"] == far["vma"],
        "owner-ends-at-far-lma": owner["lma"] + owner["bytes"] == far["lma"],
        "shared-map-offset": owner_offset == far_offset,
        "page-encodable-map-offset": owner_offset & 0xff == 0,
    }
    require(all(checks.values()), "r3 does not satisfy derived-before-far relation")
    error = ""
    try:
        ACCEPT._freight_proof_rows(layout, registries)
    except ACCEPT.ConversionError as exception:
        error = str(exception)
    require(error == ("mapped additive freight violates arena contract: "
                      ".lisp65_c2_mapped_f011_cold"),
            f"Acceptance red changed identity: {error}")
    source = (ROOT / "tools/host-lisp/c2_v160_r1_stored_world_conversions.py"
              ).read_text(encoding="utf-8")
    require('"derived-before-far-service/shared-map-offset"' not in source,
            "Acceptance already recognizes the F011 placement form")
    return {"registry": registry, "owner": owner, "far_service": far,
        "owner_map_offset": owner_offset, "far_map_offset": far_offset,
        "checks": checks, "Acceptance_error": error,
        "prover_population": ["candidate-predecessor-end",
            "mapped-arena-contract", "composed-raw-owner/preheap-gap"],
        "missing_prover": "derived-before-far-service/shared-map-offset"}


def derive() -> dict[str, Any]:
    CARD.patch_card(); CARD.R2.CARD.configure()
    final = CARD.final_gate()
    require(final["nesting"]["violations"] == []
            and final["mapped_error_return"][
                "abort_paths_from_derived_mapped_population"] == []
            and final["bounded_owners"]["all_floors_green"] is True,
            "r3 final product gate is not green")
    difference = CARD.attribution()
    require(difference["unexplained_members"] == 0,
            "r2-to-r3 attribution retains a remainder")
    scope = load(CARD.WPLTO / "owner-scope-result.json")
    require(scope["status"] == "PASS", "r3 Scope is not green")
    return {"format": FORMAT, "recorded_on": "2026-09-03", "status": STATUS,
        "authority": CARD.authority(),
        "artifact_boundary": {"ELF": bind(CARD.ELF), "PRG": bind(CARD.PRG),
            "LTO_object": bind(Path(str(CARD.PRG) + ".lto.o")),
            "link_map": bind(Path(str(CARD.PRG) + ".map")),
            "disposition": "FROZEN-PRODUCT-GREEN-ACCEPTANCE-UNQUALIFIED"},
        "product_facts": {"final_gate_status": final["status"],
            "bounded_owners": final["bounded_owners"],
            "composed_bank2": final["composed_bank2"],
            "nested_MAP_violations": final["nesting"]["violations"],
            "mapped_abort_paths": final["mapped_error_return"][
                "abort_paths_from_derived_mapped_population"],
            "direct_abort_mutation": final["mapped_error_return"][
                "mutation_paths"]},
        "difference": difference, "difference_receipt": bind(CARD.DIFFERENCE),
        "scope": bind(CARD.WPLTO / "owner-scope-result.json"),
        "attribution": {"classification": "Acceptance-prover-population-defect",
            "product_defect_established": False,
            "placement": placement_facts(),
            "mechanism": ("build graph registers a derived-before-far-service "
                "placement gate; Acceptance has no prover for that gate and "
                "falls through to an older mapped-arena-contract assertion"),
            "unexplained_members": 0},
        "qualification": {"scope_runs": 1, "scope_status": "PASS",
            "acceptance_runs": 1, "acceptance_status": "RED-CHECKER-WORLD",
            "DWX_prefilter_runs": 0, "device_contacts": 0},
        "attempt_accounting": {"card_total": {"WPLTO_runs": 3,
                "product_link_attempts": 3, "completed_product_links": 2},
            "last_round": {"WPLTO_runs": 1, "product_links": 1},
            "additional_link_authority": 0},
        "decision_required": {
            "recommended": ("add the missing semantic Acceptance prover with "
                "adjacency/shared-offset mutations, then read-only resume over r3"),
            "alternative": "apply the bound Card-2 cold-reader descope",
            "no_new_WPLTO_or_link_in_either_attribution_step": True}}


def report(value: dict[str, Any]) -> str:
    place = value["attribution"]["placement"]
    owner, far = place["owner"], place["far_service"]
    return f"""# Block 2.6 Card 2 — r3 Acceptance red

Status: **{value['status']}**

The final product gate is green: every constrained owner clears its floor,
the composed Bank-2 map is disjoint, no mapped tenant reaches a language abort
or MAP enter/leave, and the direct-abort mutation reproduces the two forbidden
MAP terminals. The r2→r3 difference has zero unexplained members and Scope is
green.

Acceptance stops on a missing prover, not a failed product relation. The
{owner['bytes']}-byte F011 owner ends exactly at the far service in both views:
VMA `{owner['vma']:#x} + {owner['bytes']} = {far['vma']:#x}` and LMA
`{owner['lma']:#x} + {owner['bytes']} = {far['lma']:#x}`. Both use the same
page-encodable `{place['owner_map_offset']:#x}` mapping offset. The build graph
names this relation `{place['missing_prover']}`, while Acceptance recognizes
only its three older placement families and falls into an assertion that
requires the unrelated `mapped-arena-contract` mnemonic.

The pair is frozen after exactly the authorized last WPLTO/link; no further
link exists. Recommended disposition is a semantic Acceptance conversion
(derive exact VMA/LMA adjacency and shared offset, with broken-adjacency and
offset-divergence mutations), followed by a strictly read-only Acceptance
resume. The alternative is the already bound cold-reader descope.
"""


def validate(value: dict[str, Any]) -> None:
    # This receipt belongs to the sealed pre-conversion checker era.  Once the
    # missing semantic prover exists, replaying ``derive`` against living
    # checker source would rewrite history by requiring the old defect to
    # remain reproducible.  Bind the frozen evidence and its internal claims
    # instead.
    require(value["status"] == STATUS
            and value["artifact_boundary"]["ELF"] == bind(CARD.ELF)
            and value["artifact_boundary"]["PRG"] == bind(CARD.PRG)
            and value["difference_receipt"] == bind(CARD.DIFFERENCE)
            and value["scope"] == bind(CARD.WPLTO / "owner-scope-result.json")
            and value["attribution"]["product_defect_established"] is False
            and all(value["attribution"]["placement"]["checks"].values())
            and value["attribution"]["placement"]["missing_prover"] ==
                "derived-before-far-service/shared-map-offset"
            and value["product_facts"]["nested_MAP_violations"] == []
            and value["difference"]["unexplained_members"] == 0
            and value["qualification"]["DWX_prefilter_runs"] == 0
            and value["attempt_accounting"]["additional_link_authority"] == 0,
            "Card-2 r3 Acceptance red drift")


def write() -> None:
    require(not RECEIPT.exists() and not REPORT.exists(),
            "Card-2 r3 Acceptance red is one-shot")
    # Replace the failed driver's predecessor-wide intermediate with the
    # authorized r2-to-r3 attribution before binding it.
    CARD.patch_card(); CARD.R2.CARD.configure()
    CARD.DIFFERENCE.write_bytes(canonical(CARD.attribution()))
    value = derive()
    RECEIPT.write_bytes(canonical(value)); REPORT.write_text(
        report(value), encoding="utf-8")
    validate(value)
    print("Block 2.6 Card 2 r3: FROZEN Acceptance-prover-red product-green")


def check() -> None:
    value = load(RECEIPT); validate(value)
    require(REPORT.is_file() and REPORT.read_text(encoding="utf-8") == report(value),
            "Card-2 r3 Acceptance-red report drift")
    print("Block 2.6 Card 2 r3: ACCEPTANCE RED CHECK product-defect=false")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "product-defect-hidden": lambda row: row["attribution"].update(
            {"product_defect_established": True}),
        "adjacency-hidden": lambda row: row["attribution"]["placement"][
            "checks"].update({"owner-ends-at-far-vma": False}),
        "nesting-hidden": lambda row: row["product_facts"].update(
            {"nested_MAP_violations": [{"path": ["mapped", "enter"]}]}),
        "new-link-hidden": lambda row: row["attempt_accounting"].update(
            {"additional_link_authority": 1}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (RedError, CARD.CardError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "Card-2 Acceptance-red mutation survived")
    print(f"Block 2.6 Card 2 r3: ACCEPTANCE RED SELFTEST mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    {"write": write, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RedError, CARD.CardError, RuntimeError, KeyError, ValueError,
            OSError) as error:
        print(f"Block 2.6 Card 2 r3 Acceptance red: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
