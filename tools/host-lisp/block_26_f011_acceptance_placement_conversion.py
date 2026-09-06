#!/usr/bin/env python3
"""Install and seal Card 2's semantic F011 Acceptance placement prover."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import block_26_f011_map_abort_repair_acceptance_red as RED  # noqa: E402
import block_26_f011_map_abort_repair_product_card as CARD  # noqa: E402
import c2_v160_r1_stored_world_conversions as ACCEPT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
AUTHORIZATION = "f06a2647"
PLAN_HEADER = (
    "## Reviewer disposition — card 2 r3 Acceptance prover; resume authorized — 2026-09-03"
)
RECEIPT = ARCH / "block-2.6-card2-f011-r3-acceptance-placement-conversion.json"
REPORT = ROOT / "docs/planning/2.6-card2-f011-r3-acceptance-placement-conversion.md"
FORMAT = "lisp65-block-2.6-card2-f011-r3-acceptance-placement-conversion-v1"
STATUS = "PASS: R3 F011 ACCEPTANCE PLACEMENT PROVER CONVERTED"


class ConversionCardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ConversionCardError(message)


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
    require(text.count(PLAN_HEADER) == 1, "Acceptance conversion authority drift")
    payload = (PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]).split(
        "\n## ", 1)[0].rstrip().encode() + b"\n"
    folded = " ".join(payload.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("read-only resume", "no wplto", "no link",
                  "exact vma/lma adjacency", "broken offset"):
        require(token in folded, f"Acceptance authority token absent: {token}")
    return {"commit": AUTHORIZATION, "path": relative,
        "section": PLAN_HEADER, "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "frozen_red": bind(RED.RECEIPT)}


def final_elf_proof() -> dict[str, Any]:
    CARD.patch_card(); CARD.R2.CARD.configure()
    CARD.R2.PRODUCT.select_f011_cold_world()
    registries, registered = ACCEPT._active_freight_union()
    layout = ACCEPT.LAYOUT.layout_from_elf(CARD.ELF, packed_prg=CARD.PRG,
        allowed_flat_packed_sections=registered)
    rows = ACCEPT._freight_proof_rows(layout, registries)
    ACCEPT._validate_freight_rows(rows, registered)
    matches = [row for row in rows
               if row["name"] == ".lisp65_c2_mapped_f011_cold"]
    require(len(matches) == 1, "F011 placement proof is not unique")
    proof = matches[0]

    by_name = {row["name"]: row for row in layout["allocatable_sections"]}
    owner = by_name[".lisp65_c2_mapped_f011_cold"]
    far = by_name[".lisp65_c2_mapped_far_service"]
    facts = {
        "owner_ends_at_far_service_VMA":
            owner["vma"] + owner["bytes"] == far["vma"],
        "owner_ends_at_far_service_LMA":
            owner["lma"] + owner["bytes"] == far["lma"],
        "shared_mapping_offset":
            owner["lma"] - owner["vma"] == far["lma"] - far["vma"],
        "page_congruent_mapping_offset":
            (owner["lma"] - owner["vma"]) & 0xff == 0,
    }
    require(all(facts.values()), "final ELF fails converted placement relation")

    # The proof may contain page-size arithmetic, section identities and
    # derived comparisons, but never a candidate address literal.
    source = inspect.getsource(ACCEPT._derived_before_far_service_proof)
    tree = ast.parse(source)
    address_literals = sorted({node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, int)
        and node.value > 0x100})
    require(address_literals == [], "converted prover pins a candidate address")
    return {"frozen_pair": {"ELF": bind(CARD.ELF), "PRG": bind(CARD.PRG)},
        "membership_authority": proof["membership_authority"],
        "placement_proof": proof["placement_proof"],
        "derived_final_ELF_facts": facts,
        "candidate_address_literals": address_literals,
        "sealed_red_era_remains_frozen": True}


def derive() -> dict[str, Any]:
    proof = final_elf_proof()
    return {"format": FORMAT, "recorded_on": "2026-09-03",
        "status": STATUS, "authority": authority(), "proof": proof,
        "era_conversion": {
            "sealed_red_checked_in_its_own_evidence_era": True,
            "living_acceptance_uses_successor_prover": True,
            "anti_mixing_rule": "a sealed checker red is never regenerated with successor source",
        },
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "next": "commit conversion, then read-only Acceptance resume over frozen r3"}


def report(value: dict[str, Any]) -> str:
    proof = value["proof"]["placement_proof"]
    return f"""# Block 2.6 Card 2 — r3 Acceptance placement conversion

Status: **{value['status']}**

Acceptance now recognizes the F011 owner's semantic placement directly from
the final ELF: the section ends exactly at the far service in both VMA and
LMA, and both sections share one page-congruent mapping offset. No candidate
address is a checker constant.

The sharp mutations `{proof['mutations_rejected'][0]}` and
`{proof['mutations_rejected'][1]}` both fall. The historical red remains sealed
in its pre-conversion evidence era; its check binds the frozen pair and claims
without requiring the living checker to reproduce its old defect.

This conversion used zero WPLTOs, links, media builds or device contacts. The
next operation is the separately authorized read-only Acceptance resume over
the unchanged r3 pair.
"""


def validate(value: dict[str, Any]) -> None:
    current = derive()
    proof = value["proof"]["placement_proof"]
    require(value == current and value["status"] == STATUS
            and proof["gate"] ==
                "derived-before-far-service/shared-map-offset"
            and proof["mutations_rejected"] == [
                "broken-vma-lma-adjacency", "broken-shared-map-offset"]
            and value["proof"]["candidate_address_literals"] == []
            and value["attempt_accounting"]["WPLTO_runs"] == 0
            and value["attempt_accounting"]["product_links"] == 0,
            "F011 Acceptance placement conversion drift")


def write() -> None:
    require(not RECEIPT.exists() and not REPORT.exists(),
            "F011 Acceptance placement conversion is one-shot")
    value = derive(); RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    validate(value)
    print("Block 2.6 Card 2: ACCEPTANCE PLACEMENT CONVERSION PASS mutations=2")


def check() -> None:
    value = load(RECEIPT); validate(value)
    require(REPORT.read_text(encoding="utf-8") == report(value),
            "F011 Acceptance placement conversion report drift")
    print("Block 2.6 Card 2: ACCEPTANCE PLACEMENT CONVERSION CHECK PASS")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "adjacency-mutation-lost": lambda row: row["proof"][
            "placement_proof"]["mutations_rejected"].remove(
                "broken-vma-lma-adjacency"),
        "offset-mutation-lost": lambda row: row["proof"][
            "placement_proof"]["mutations_rejected"].remove(
                "broken-shared-map-offset"),
        "address-pin-added": lambda row: row["proof"].update(
            candidate_address_literals=[0x763b]),
        "product-work-hidden": lambda row: row["attempt_accounting"].update(
            product_links=1),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (ConversionCardError, ACCEPT.ConversionError, RuntimeError,
                KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "Acceptance conversion mutation survived")
    print(f"Block 2.6 Card 2: ACCEPTANCE CONVERSION SELFTEST mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    {"write": write, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ConversionCardError, ACCEPT.ConversionError, RuntimeError,
            KeyError, ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Block 2.6 Card 2 Acceptance conversion: FAIL {error}",
              file=sys.stderr)
        raise SystemExit(1)
