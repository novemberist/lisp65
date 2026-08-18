#!/usr/bin/env python3
"""Reconcile the Link-106 CPU-transport wording with its real source domains.

The historical target observation tested one concrete instruction family:
flat ``LDA [$zp],Z``.  It proved Bank-0 high RAM and disproved Bank 4 for
that family; it did not prove a MAP-based Attic/Bank-5 transport.  This desk
gate binds that scope to the exact Shelf and C2D sources consumed while
LOADING LIBRARIES.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = ARCH / "c2.3-v2.0-cpu-transport-reconciliation-receipt.json"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
PRICING = ARCH / "c2.3-v2.0-loading-libraries-duration-pricing-receipt.json"
CONTRACT = ROOT / "config/c2-f018b-content-safe-read-contract.json"
DEEPDIVE = ROOT / "docs/archive/pre-1.0/reference/mega65-hardware-deepdive-2026-07-10.md"
SMOKE = ROOT / "scripts/hw-access-smoke-main.c"
HWOPS = ROOT / "scripts/hw-mega65-hwops.h"
HEADER = ROOT / "src/c2_product_runtime.h"
RUNTIME = ROOT / ("build/c2.3/v2.0-phase02b-header-consumption-replacement-card/"
                  "wplto/generated-product-sources/c2_product_runtime.c")
SHELF = ROOT / ("build/c2.3/v2.0-phase02b-header-consumption-replacement-card/"
                "static-plane/narrow-static/product/product-shelf-v4-direct.bin")
C2D = ROOT / ("build/c2.3/v2.0-phase02b-header-consumption-replacement-card/"
              "static-plane/narrow-static/v6-semantics/initial.c2d-v6.bin")

AUTHORIZATION = "db20fc5b"
FORMAT = "lisp65-c2.3-v2.0-cpu-transport-reconciliation-v1"
RECORDED_ON = "2026-08-14"


class ReconciliationError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReconciliationError(message)


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


def git_authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    require("reconcile the cpu-transport evidence" in text
            and "build the specified progress ring" in text
            and "d1–d5 stay closed" in text,
            "CPU/ring commission authority drift")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def macro(text: str, name: str) -> int:
    found = re.search(rf"^#define\s+{re.escape(name)}\s+(0x[0-9A-Fa-f]+|[0-9]+)(?:U?L?)",
                      text, re.MULTILINE)
    require(found is not None, f"macro absent: {name}")
    return int(found.group(1), 0)


def build_receipt() -> dict[str, Any]:
    pricing = load(PRICING)
    contract = load(CONTRACT)
    totals = pricing["workload"]["standard_convergence_aggregate"]
    require(totals == {
        "c2d_bytes": 62528, "c2d_calls": 8147,
        "c2d_write_bytes": 16550, "c2d_write_calls": 4773,
        "converged_calls": 346298, "payload_bytes": 1180781,
        "shelf_bytes": 1118253, "shelf_calls": 338151},
        "Link-106 workload identity drift")
    require(len(SHELF.read_bytes()) == 93681 and len(C2D.read_bytes()) == 33840,
            "Link-106 source extent drift")

    header = HEADER.read_text(encoding="utf-8")
    shelf_base = macro(header, "LISP65_C2_SHELF_PHYSICAL")
    session_base = macro(header, "LISP65_C2_SESSION_PHYSICAL")
    c2d_base = macro(header, "LISP65_C2D_BASE")
    c2d_bank = macro(header, "LISP65_C2D_BANK")
    c2d_region = macro(header, "LISP65_C2D_REGION_BYTES")
    require(shelf_base == 0x08100000 and session_base == 0x08400000
            and c2d_bank == 5 and c2d_base == 0 and c2d_region == 50816,
            "target source-domain contract drift")

    runtime = RUNTIME.read_text(encoding="utf-8")
    require("c2_physical_read_converged(base + offset" in runtime
            and "LISP65_C2D_BANK, (uint16_t)(LISP65_C2D_BASE + offset)" in runtime,
            "delivered runtime no longer consumes the bound source domains")
    smoke = SMOKE.read_text(encoding="utf-8")
    hwops = HWOPS.read_text(encoding="utf-8")
    deep = DEEPDIVE.read_text(encoding="utf-8")
    require("hw_flat_read8(0x0000fffau)" in smoke
            and "hw_flat_write8(0x0004c800ul, 0x7b)" in smoke
            and '.byte $ea,$b2,mos16lo(hw_flat_ptr)' in hwops
            and "nur Bank-0-High-RAM" in deep
            and "F018-DMA der einzige" in deep,
            "historical flat-CPU evidence scope drift")
    require(contract["pricing"]["cpu_28bit"]["verdict"]
            == "rejected-for-bank4-bank5-and-attic",
            "accepted Link-106 transport decision drift")

    shelf_end = shelf_base + len(SHELF.read_bytes())
    c2d_live_end = c2d_bank * 0x10000 + len(C2D.read_bytes())
    c2d_region_end = c2d_bank * 0x10000 + c2d_region
    require(shelf_end == 0x08116DF1 and c2d_live_end == 0x00058430
            and c2d_region_end == 0x0005C680,
            "source-domain endpoint arithmetic drift")

    fact = {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "DESK-GREEN; NO-CPU-TRANSPORT-FOR-LINK106; RING-STILL-REQUIRED",
        "authority": git_authority(),
        "inputs": {name: bind(path) for name, path in {
            "pricing": PRICING, "selection_contract": CONTRACT,
            "historical_reading": DEEPDIVE, "target_smoke": SMOKE,
            "flat_opcode_implementation": HWOPS, "runtime_header": HEADER,
            "delivered_runtime": RUNTIME, "shelf": SHELF, "c2d": C2D}.items()},
        "historical_exclusion": {
            "transport_family": "45GS02 flat LDA [$zp],Z (EA B2 zp)",
            "positive_domain": "physical Bank-0 high RAM; observed at 0x0000FFFA",
            "negative_domain": "physical Bank-4; observed at 0x0004C800",
            "bank5_target_test_present": False,
            "attic_target_test_present": False,
            "MAP_based_transport_test_present": False,
            "meaning": "Bank 4 falsifies this flat-opcode family as a bank-agnostic release transport; Bank 5 and Attic remain unproved, not separately measured failures",
        },
        "library_load_sources": {
            "shelf": {"physical_start": "0x08100000",
                      "physical_end_exclusive": "0x08116DF1", "bytes": 93681,
                      "domain": "Attic", "logical_calls": 338151},
            "initial_c2d": {"physical_start": "0x00050000",
                           "physical_end_exclusive": "0x00058430", "bytes": 33840,
                           "owned_region_end_exclusive": "0x0005C680",
                           "domain": "Bank-5", "logical_calls": 8147},
            "session_successor": {"physical_start": "0x08400000",
                                  "maximum_bytes": 1048576,
                                  "domain": "Attic; post-READY append source"},
            "total_logical_reads": 346298,
            "reads_in_proven_CPU_domain": 0,
            "reads_outside_proven_CPU_domain": 346298,
        },
        "reconciliation": {
            "contradiction": False,
            "Link106_release_fix": "verified convergence remains required for 100% of LOADING LIBRARIES reads",
            "flat_opcode_successor": "rejected; the exact tested Bank-4 failure still applies",
            "mapped_or_other_synchronous_CPU_successor": "still promising but new: it needs separate target proof for both Bank-5 and Attic before it can replace DMA",
            "F018B_root_removal_available_now": False,
            "architecture_decision_after_contact": "retain convergence for measured DMA domains; separately price/prove MAP-based or restaged CPU visibility",
        },
        "accounting": {"product_bytes_changed": 0, "media_bytes_changed": 0,
                       "device_contacts": 0, "contact_authorized": False,
                       "D1_D5_open": False},
        "claim_limit": "Desk-only scope reconciliation. It does not claim that MAP cannot expose Bank-5 or Attic; it proves only that no such target proof exists and that none of the 346,298 Link-106 library reads lies in the positively proven flat-CPU Bank-0 domain.",
    }
    audit(fact)
    return fact


def audit(value: dict[str, Any]) -> None:
    require(value["status"]
            == "DESK-GREEN; NO-CPU-TRANSPORT-FOR-LINK106; RING-STILL-REQUIRED",
            "reconciliation status drift")
    old = value["historical_exclusion"]
    require(old["transport_family"] == "45GS02 flat LDA [$zp],Z (EA B2 zp)"
            and old["positive_domain"].startswith("physical Bank-0")
            and old["negative_domain"].startswith("physical Bank-4")
            and old["bank5_target_test_present"] is False
            and old["attic_target_test_present"] is False
            and old["MAP_based_transport_test_present"] is False,
            "historical evidence was broadened or weakened")
    sources = value["library_load_sources"]
    require(sources["shelf"]["physical_start"] == "0x08100000"
            and sources["shelf"]["physical_end_exclusive"] == "0x08116DF1"
            and sources["shelf"]["logical_calls"] == 338151
            and sources["initial_c2d"]["physical_start"] == "0x00050000"
            and sources["initial_c2d"]["physical_end_exclusive"] == "0x00058430"
            and sources["initial_c2d"]["logical_calls"] == 8147
            and sources["reads_in_proven_CPU_domain"] == 0
            and sources["reads_outside_proven_CPU_domain"] == 346298,
            "library source coverage drift")
    decision = value["reconciliation"]
    require(decision["contradiction"] is False
            and decision["F018B_root_removal_available_now"] is False
            and decision["mapped_or_other_synchronous_CPU_successor"].startswith(
                "still promising but new"), "CPU-successor claim broadened")
    require(value["accounting"] == {
        "product_bytes_changed": 0, "media_bytes_changed": 0,
        "device_contacts": 0, "contact_authorized": False,
        "D1_D5_open": False}, "desk-only accounting drift")


def selftest(base: dict[str, Any]) -> dict[str, Any]:
    cases = {
        "broaden-flat-positive-to-bank5": (["historical_exclusion", "positive_domain"], "Bank-0 and Bank-5"),
        "claim-bank5-target-test": (["historical_exclusion", "bank5_target_test_present"], True),
        "claim-attic-target-test": (["historical_exclusion", "attic_target_test_present"], True),
        "claim-MAP-target-test": (["historical_exclusion", "MAP_based_transport_test_present"], True),
        "move-shelf-to-bank0": (["library_load_sources", "shelf", "physical_start"], "0x00010000"),
        "truncate-shelf-domain": (["library_load_sources", "shelf", "physical_end_exclusive"], "0x08100001"),
        "move-c2d-to-bank0": (["library_load_sources", "initial_c2d", "physical_start"], "0x00000000"),
        "truncate-c2d-domain": (["library_load_sources", "initial_c2d", "physical_end_exclusive"], "0x00050001"),
        "admit-one-proven-read": (["library_load_sources", "reads_in_proven_CPU_domain"], 1),
        "drop-one-unproved-read": (["library_load_sources", "reads_outside_proven_CPU_domain"], 346297),
        "invent-root-removal": (["reconciliation", "F018B_root_removal_available_now"], True),
        "erase-new-proof-requirement": (["reconciliation", "mapped_or_other_synchronous_CPU_successor"], "selected"),
        "authorize-contact": (["accounting", "contact_authorized"], True),
        "open-D1-D5": (["accounting", "D1_D5_open"], True),
    }
    rejected: dict[str, str] = {}
    for name, (path, replacement) in cases.items():
        trial = deepcopy(base); cursor: Any = trial
        for key in path[:-1]: cursor = cursor[key]
        cursor[path[-1]] = replacement
        try: audit(trial)
        except ReconciliationError as error: rejected[name] = str(error)
        else: raise ReconciliationError(f"mutation survived: {name}")
    require(len(rejected) == 14, "CPU reconciliation mutation count drift")
    return {"count": len(rejected), "rejected": rejected}


def main() -> int:
    try:
        value = build_receipt()
        value["mutations"] = selftest(value)
        encoded = canonical(value)
        if len(sys.argv) == 2 and sys.argv[1] == "--check":
            require(RECEIPT.is_file() and RECEIPT.read_bytes() == encoded,
                    "persisted CPU reconciliation receipt drift")
        elif len(sys.argv) == 1:
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_bytes(encoded)
        else:
            raise ReconciliationError("usage: c2_v20_cpu_transport_reconciliation.py [--check]")
        print("C2 V2.0 CPU TRANSPORT RECONCILIATION PASS "
              "proven-cpu-reads=0/346298 mutations=14 contact=no")
        return 0
    except (OSError, KeyError, ValueError, ReconciliationError,
            subprocess.CalledProcessError) as error:
        print(f"C2 V2.0 CPU TRANSPORT RECONCILIATION FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
