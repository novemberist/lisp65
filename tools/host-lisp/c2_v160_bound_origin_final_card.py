#!/usr/bin/env python3
"""Link and qualify the authorized bound-origin input-instrument world."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_active_frame_liveness_card as CARD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-bound-origin-final-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-bound-origin-final-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-bound-origin-final-process"
RECEIPT = ARCH / "c2.3-v1.6-bound-origin-final-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-bound-origin-final-card-final-red.json"
PREDECESSOR = ARCH / (
    "c2.3-v1.6-active-frame-liveness-acceptance-resume-receipt.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "80baec42"
FORMAT = "lisp65-c2-v160-bound-origin-final-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 BOUND-ORIGIN FINAL CARD ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 BOUND-ORIGIN FINAL WORLD GREEN"


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("final product link and fresh same-world media",
                  "atomic zero at comfort entry", "raw", "seen", "stored",
                  "taken", "under 256 events"):
        CARD.require(token in text,
                     f"bound-origin final-card authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    value = CARD.BASE.load(PREDECESSOR)
    CARD.require(value["status"] ==
            "PASS: V1.6 ACTIVE-FRAME LIVENESS CLOSED READ-ONLY"
        and value["liveness_contract_closed"] is True
        and value["execution_witness"]["WPLTO_runs"] == 0
        and value["execution_witness"]["product_links"] == 0,
        "bound-origin predecessor liveness closure drift")
    counters = CARD.COUNTERS.derive()
    CARD.COUNTERS.validate(counters)
    CARD.require(counters["origin"]["phase"] == "Comfort activation"
        and counters["linked_shape"]["usable_events"] == 107
        and counters["linked_shape"]["E000_surplus_over_floor_bytes"] == 3,
        "bound-origin instrument source world drift")
    return {"liveness_closure": value, "bound_origin_instrument": counters}


def configure_module() -> None:
    CARD.configure_for_paths(BUILD, PREFLIGHT, tag="bound-origin-final")


def check_receipt() -> dict[str, Any]:
    value = CARD.BASE.load(RECEIPT)
    gate = value["active_frame_final_gate"]
    counters = gate["input_counters"]
    CARD.require(value["status"] == FINAL_STATUS
        and value["attempt_accounting"] == {"cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1,
            "media_builds": 0, "device_contacts": 0}
        and gate["population"]["population_count"] == 1
        and gate["enforcement"]["section"] == CARD.ACTIVE.SERVICE
        and gate["far_service"]["free_bytes"] == 37
        and counters["ring_usable_events"] == 107
        and counters["reserve_events"] == 13
        and list(counters["counter_addresses"]) == [
            "C2K_INPUT_EVENTS_RAW", "C2K_INPUT_EVENTS_SEEN",
            "C2K_INPUT_EVENTS_STORED", "C2K_INPUT_EVENTS_TAKEN"]
        and counters["loss_wall"]["dropped"] == 0,
        "bound-origin final receipt drift")
    CARD.BASE.PREV.PREV.PREV.validate_final_claims(value)
    return value


def install() -> None:
    CARD.BUILD = BUILD
    CARD.PREFLIGHT = PREFLIGHT
    CARD.PROCESS = PROCESS
    CARD.NORMAL_BUILD = PROCESS / "normal-build"
    CARD.NORMAL_PREFLIGHT = PROCESS / "normal-preflight"
    CARD.MUTANT_BUILD = PROCESS / "mutant-build"
    CARD.MUTANT_PREFLIGHT = PROCESS / "mutant-preflight"
    CARD.PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    CARD.RECEIPT = RECEIPT
    CARD.FINAL_RED = FINAL_RED
    CARD.PREDECESSOR = PREDECESSOR
    CARD.DRIVER = DRIVER
    CARD.AUTHORIZATION = AUTHORIZATION
    CARD.FORMAT = FORMAT
    CARD.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    CARD.FINAL_STATUS = FINAL_STATUS
    CARD.authority = authority
    CARD.predecessor = predecessor
    CARD.configure_module = configure_module
    CARD.check_receipt = check_receipt
    CARD.install()


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    result = CARD.main()
    if action == "card" and RECEIPT.is_file():
        value = CARD.BASE.load(RECEIPT)
        value["bound_origin_authority"] = authority()
        value["bound_origin_predecessor"] = CARD.BASE.bind(PREDECESSOR)
        RECEIPT.write_bytes(CARD.canonical(value))
        check_receipt()
    return result


if __name__ == "__main__":
    install()
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                CARD.record_red(error)
            except Exception as receipt_error:
                print("bound-origin final-card Final Red receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"v1.6 bound-origin final card: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
