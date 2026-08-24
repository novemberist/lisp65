#!/usr/bin/env python3
"""Run the one authorized queue-owner cold-relocation product card."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path: sys.path.insert(0, str(HOST))

import c2_v160_queue_single_owner_card as BASE  # noqa: E402
import c2_v160_queue_owner_cold_relocation as RELOCATION  # noqa: E402

ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-queue-owner-cold-relocation-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-queue-owner-cold-relocation-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-queue-owner-cold-relocation-process"
RECEIPT = ARCH / "c2.3-v1.6-queue-owner-cold-relocation-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-queue-owner-cold-relocation-card-final-red.json"
PREDECESSOR = ARCH / "c2.3-v1.6-queue-single-owner-replacement-card-final-red.json"
PRICING = ARCH / "c2.3-v1.6-queue-owner-cold-relocation-pricing.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "45396b35"
FORMAT = "lisp65-c2-v160-queue-owner-cold-relocation-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 QUEUE-OWNER COLD RELOCATION ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 QUEUE-OWNER COLD RELOCATION FINAL WORLD GREEN"


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("exactly one relocation card", "22-byte body",
                  "9-byte stub", "placement born-derived",
                  "single-owner queue guard included", "exceptionless"):
        BASE.CARD.require(token in text, f"cold-relocation authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    red = BASE.CARD.BASE.load(PREDECESSOR)
    price = BASE.CARD.BASE.load(PRICING)
    source = RELOCATION.source_gate()
    BASE.CARD.require(red["status"] ==
            "FINAL RED: V1.6 QUEUE SINGLE-EXIT CAPACITY STOPS"
        and red["attempt_accounting"]["cards_consumed"] == 1
        and price["status"] ==
            "PASS: COLD RELOCATION RECOVERS QUEUE-OWNER TEXT CAPACITY"
        and price["route_2"]["ordinary_net_reclaim_bytes"] == 13
        and source["status"] == RELOCATION.STATUS,
        "cold-relocation predecessor chain drift")
    return {"single_exit_Final_Red": red, "pricing": price,
            "relocation_source_gate": source}


def configure_module() -> None:
    BASE.CARD.configure_for_paths(BUILD, PREFLIGHT,
                                  tag="queue-owner-cold-relocation")


def check_receipt() -> dict[str, Any]:
    value = BASE.CARD.BASE.load(RECEIPT)
    BASE.CARD.require(value["status"] == FINAL_STATUS
        and value["attempt_accounting"] == {"cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1,
            "media_builds": 0, "device_contacts": 0},
        "cold-relocation final receipt drift")
    if "queue_single_owner" in value:
        linked_owner = value["queue_single_owner"]
        BASE.CARD.require(linked_owner["queue_poll_calls"] == 2
                and linked_owner["dominated_calls"] == 1
                and [row["owner"] for row in linked_owner["consumers"]] ==
                    ["vm_run_inner", "lisp_input_event"],
                "persisted single-owner linked proof drift")
    if "cold_relocation" in value:
        linked = value["cold_relocation"]
        BASE.CARD.require(linked["status"] == RELOCATION.STATUS
            and linked["ordinary"]["free_bytes"] >= 6
            and linked["far"]["free_bytes"] >= 15
            and linked["facade_bytes"] == 98
            and len(linked["linked_callers"]) == 2,
            "persisted cold-relocation linked proof drift")
    return value


def install() -> None:
    BASE.CARD.BUILD = BUILD; BASE.CARD.PREFLIGHT = PREFLIGHT
    BASE.CARD.PROCESS = PROCESS
    BASE.CARD.NORMAL_BUILD = PROCESS / "normal-build"
    BASE.CARD.NORMAL_PREFLIGHT = PROCESS / "normal-preflight"
    BASE.CARD.MUTANT_BUILD = PROCESS / "mutant-build"
    BASE.CARD.MUTANT_PREFLIGHT = PROCESS / "mutant-preflight"
    BASE.CARD.PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    BASE.CARD.RECEIPT = RECEIPT; BASE.CARD.FINAL_RED = FINAL_RED
    BASE.CARD.PREDECESSOR = PREDECESSOR; BASE.CARD.DRIVER = DRIVER
    BASE.CARD.AUTHORIZATION = AUTHORIZATION; BASE.CARD.FORMAT = FORMAT
    BASE.CARD.PREFLIGHT_STATUS = PREFLIGHT_STATUS; BASE.CARD.FINAL_STATUS = FINAL_STATUS
    BASE.CARD.authority = authority; BASE.CARD.predecessor = predecessor
    BASE.CARD.configure_module = configure_module; BASE.CARD.check_receipt = check_receipt
    BASE.CARD.install()


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "check" and FINAL_RED.is_file() and not RECEIPT.exists():
        red = BASE.CARD.BASE.load(FINAL_RED)
        BASE.CARD.require(red["status"] ==
                "FINAL RED: V1.6 QUEUE-OWNER LINKED GUARD STOPS"
            and red["attempt_accounting"]["cards_consumed"] == 1
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_link_attempts"] == 1
            and red["attempt_accounting"]["media_builds"] == 0
            and red["attempt_accounting"]["device_contacts"] == 0
            and red["error"]["message"] ==
                "final ELF queue call lacks armed-state/matrix domination",
            "cold-relocation Final Red drift")
        print("v1.6 queue-owner cold relocation: FINAL RED sealed; card consumed 1/1")
        return 0
    result = BASE.CARD.main()
    if action == "card" and RECEIPT.is_file():
        value = BASE.CARD.BASE.load(RECEIPT)
        value["cold_relocation_authority"] = authority()
        value["cold_relocation_pricing"] = BASE.CARD.BASE.bind(PRICING)
        value["source_single_owner"] = BASE.OWNER.derive()
        value["queue_single_owner"] = BASE.linked_owner_gate(BASE.CARD.PRODUCT_ELF)
        value["cold_relocation"] = RELOCATION.linked_gate(BASE.CARD.PRODUCT_ELF)
        RECEIPT.write_bytes(BASE.CARD.canonical(value)); check_receipt()
    return result


if __name__ == "__main__":
    install()
    try: raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: BASE.CARD.record_red(error)
            except Exception as receipt_error:
                print(f"cold-relocation Final Red receipt failure: {receipt_error}", file=sys.stderr)
        print(f"v1.6 queue-owner cold relocation: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
