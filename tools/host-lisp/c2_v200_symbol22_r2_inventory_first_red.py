#!/usr/bin/env python3
"""Persist the r2 split-latch inventory First Red without resuming the link."""

from __future__ import annotations

import argparse
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
import c2_v200_symbol22_first_fault_product_card as CARD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ARCH / "c2.3-v2.0-symbol22-first-fault-product-card-r2-first-red.json"
REPORT = ROOT / "docs/planning/v2.0.0-symbol22-first-fault-r2-inventory-first-red.md"
SEED_DIR = ROOT / "build/c2.3/v2.0-symbol22-first-fault-product-card-r2/wplto"
SEED = SEED_DIR / "resident-island-seed.prg"
SEED_ELF = Path(str(SEED) + ".elf")
STATE_RELA = ".rela" + CARD.STATE_SECTION
CODE_RELA = ".rela" + CARD.SECTION
STATUS = "FIRST RED: ZERO-RELOCATION STATE SECTION WAS REQUIRED AS RELA FREIGHT"


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


def derive() -> dict[str, Any]:
    CARD.patch_paths()
    # Reconstruct the exact full-map/profile world consumed by the seed link;
    # the clean-stack prefix alone intentionally has a smaller inventory.
    CARD.BASE.configure_full_candidate()
    required = (SEED, SEED_ELF, Path(str(SEED) + ".map"),
                Path(str(SEED) + ".lto.o"), SEED_DIR / "resolved-profile.txt")
    require(all(path.is_file() for path in required)
            and CARD.INVOCATION.is_file()
            and not CARD.ELF.exists() and not CARD.PRG.exists()
            and not CARD.RECEIPT.exists() and not CARD.DIFFERENCE.exists(),
            "r2 inventory First-Red lifecycle drift")
    truth = ElfTruth.read(SEED_ELF, llvm_readobj=CARD.READOBJ)
    actual = [str(row["name"])
              for row in CARD.PRODUCT._readobj_sections(SEED_ELF)]
    expectation = CARD.PRODUCT.final_section_inventory_expectation()
    expected = list(expectation["names"])
    missing = [name for name in expected if name not in actual]
    additional = [name for name in actual if name not in expected]
    code_relocations = [row for row in truth.relocations
                        if row.source_section == CARD.SECTION]
    state_relocations = [row for row in truth.relocations
                         if row.source_section == CARD.STATE_SECTION]
    registration = expectation["symbol22_latch_registration"]
    require(missing == [STATE_RELA] and not additional
            and CARD.SECTION in actual and CARD.STATE_SECTION in actual
            and CODE_RELA in actual and STATE_RELA not in actual
            and len(code_relocations) > 0 and not state_relocations
            and registration["relocations"] == [CODE_RELA, STATE_RELA],
            "inventory failure is not the zero-relocation state family")
    value = {
        "format": "lisp65-c2.3-v200-symbol22-r2-inventory-first-red-v1",
        "recorded_on": "2026-08-31", "status": STATUS,
        "authority": {"product_card": CARD.authority(),
            "preflight": bind(CARD.PREFLIGHT_RECEIPT),
            "invocation": bind(CARD.INVOCATION)},
        "frozen_seed": {path.name: bind(path) for path in required},
        "observed": {"expected_section_count": len(expected),
            "actual_section_count": len(actual), "missing": missing,
            "additional": additional,
            "allocated_sections_present": [CARD.SECTION, CARD.STATE_SECTION],
            "relocation_sections_present": [CODE_RELA],
            "code_relocation_records": len(code_relocations),
            "state_relocation_records": len(state_relocations)},
        "attribution": {
            "product_defect_established": False,
            "family": "registry projected one RELA section per allocated section",
            "mechanism": ("the packed-zero state has no symbolic operands, so the "
                "assembler emits zero relocation records and LLVM correctly emits "
                "no .rela state section"),
            "preflight_blind_spot": ("the micro-object proved 48/5 bytes but did "
                "not compare its emitted relocation membership with the registry"),
            "candidate_bytes_linked": True,
            "product_closure_link_executed": False},
        "successor_contract": {
            "relocation_membership": ("derive from emitted relocation source-section "
                "membership, not one mechanically fabricated RELA name per allocation"),
            "preflight": ("micro-object relocation membership equals the materialized "
                "registry before WPLTO"),
            "sharp_mutations": [
                "an emitted relocation section omitted from the registry falls",
                "an unregistered relocation section in the final ELF falls",
                "a fabricated empty RELA requirement falls pre-WPLTO"],
            "resume_basis": "immutable resident-island seed",
            "review_required_before_resume": True},
        "accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 0, "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "candidate_disposition": "FROZEN-PRE-CLOSURE-PRODUCT-EVIDENCE",
        "next": ("review the registry conversion; if authorized, replay inventory "
                 "read-only over this seed and spend the still-unconsumed product link")}
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    require(value["status"] == STATUS
            and value["observed"]["missing"] == [STATE_RELA]
            and not value["observed"]["additional"]
            and value["observed"]["state_relocation_records"] == 0
            and value["observed"]["code_relocation_records"] > 0
            and value["attribution"]["product_defect_established"] is False
            and value["attribution"]["product_closure_link_executed"] is False
            and value["accounting"] == {"product_cards": 1, "WPLTO_runs": 1,
                "product_links": 0, "scope_runs": 0, "acceptance_runs": 0,
                "media_builds": 0, "device_contacts": 0}
            and value["successor_contract"]["review_required_before_resume"] is True,
            "r2 inventory First-Red receipt drift")


def selftest() -> None:
    value = json.loads(OUT.read_text(encoding="utf-8")); validate(value)
    cases = {
        "hide-missing-rela": lambda x: x["observed"].update(missing=[]),
        "invent-state-relocation": lambda x: x["observed"].update(
            state_relocation_records=1),
        "claim-product-defect": lambda x: x["attribution"].update(
            product_defect_established=True),
        "claim-link-consumed": lambda x: x["accounting"].update(product_links=1),
        "resume-without-review": lambda x: x["successor_contract"].update(
            review_required_before_resume=False),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except RedError:
            rejected.append(name)
    require(rejected == list(cases), "r2 inventory mutation survived")
    print(f"v2.0 symbol22 r2 inventory red: SELFTEST PASS mutations={len(rejected)}")


def write_report(value: dict[str, Any]) -> None:
    observed = value["observed"]
    REPORT.write_text(f"""# v2.0 Phase 0 — r2 inventory First Red

Status: **{value['status']}**

The authorized WPLTO produced and froze the resident-island seed.  Both split
allocated owners are present: the 48-byte helper and the 5-byte packed-zero
state.  The helper carries **{observed['code_relocation_records']}** relocation
records and therefore has `{CODE_RELA}`.  State carries **zero** relocation
records and LLVM therefore correctly emits no `{STATE_RELA}`.

The product bytes are not exonerated or qualified, but this stop is not an
established product defect.  The registry fabricated one relocation-section
name per allocated section, rather than projecting actual emitted relocation
membership.  Its only missing name is `{STATE_RELA}`; there are no additional
sections.

Budget is precise: one product card and one WPLTO are consumed; the product
closure link, Scope, Acceptance, media and device counts remain zero.  The
seed is frozen.  A successor may derive relocation membership from emitted
source-section records, add the micro-object equality check before WPLTO, and
then replay inventory over this immutable seed.  Spending the still-unconsumed
product link requires review authorization.
""", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    if action == "record":
        value = derive(); OUT.write_bytes(canonical(value)); write_report(value)
        print("v2.0 symbol22 r2 inventory red: RECORDED WPLTO=1 link=0/1")
    elif action == "check":
        value = json.loads(OUT.read_text(encoding="utf-8")); validate(value)
        require(REPORT.is_file(), "r2 inventory First-Red report absent")
        print("v2.0 symbol22 r2 inventory red: CHECK PASS WPLTO=1 link=0/1")
    else:
        selftest()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RedError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"v2.0 symbol22 r2 inventory red: FAIL: {error}", file=sys.stderr)
        raise SystemExit(2)
