#!/usr/bin/env python3
"""Link and qualify the v1.6 single-owner hardware queue correction."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_active_frame_liveness_card as CARD  # noqa: E402
import c2_v160_queue_single_owner_gate as OWNER  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-queue-single-owner-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-queue-single-owner-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-queue-single-owner-process"
RECEIPT = ARCH / "c2.3-v1.6-queue-single-owner-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-queue-single-owner-card-final-red.json"
PREDECESSOR = ARCH / "c2.3-v1.6-bound-origin-measurement-result-receipt.json"
ATTRIBUTION = ARCH / "c2.3-v1.6-second-queue-consumer-attribution.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "dcf27b87"
FORMAT = "lisp65-c2-v160-queue-single-owner-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 QUEUE SINGLE-OWNER CARD ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 QUEUE SINGLE-OWNER FINAL WORLD GREEN"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("prove the race", "one owner per resource",
                  "must not read or acknowledge the queue", "run/stop"):
        CARD.require(token in text, f"single-owner authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    result = CARD.BASE.load(PREDECESSOR)
    attribution = CARD.BASE.load(ATTRIBUTION)
    owner = OWNER.derive(); OWNER.validate(owner)
    CARD.require(result["status"] ==
            "PASS: V1.6 INPUT LOSS LOCATED BEFORE RAW QUEUE WITNESS"
        and result["decision"]["arithmetic"] ==
            "physical 11 > raw 8 = seen 8 = stored 8 = taken 8"
        and attribution["status"] ==
            "PASS: SECOND PRODUCT QUEUE CONSUMER PROVES LOSS RACE"
        and owner["status"] ==
            "PASS: ARMED CAPTURE IS SOLE HARDWARE QUEUE OWNER",
        "single-owner predecessor chain drift")
    return {"measurement": result, "attribution": attribution,
            "source_gate": owner}


def configure_module() -> None:
    CARD.configure_for_paths(BUILD, PREFLIGHT, tag="queue-single-owner")


def _validate_queue_call_rows(rows: list[dict[str, Any]], *,
                              blanket: bool = False) -> None:
    expected = {"vm_run_inner", "lisp_input_event"}
    CARD.require({str(row["owner"]) for row in rows} == expected,
                 f"linked queue consumer identity drift: {rows}")
    for row in rows:
        needs_domination = blanket or row["owner"] == "vm_run_inner"
        if needs_domination:
            CARD.require(row["armed_state_before"] and row["matrix_before"],
                         f"evaluator queue edge lacks capture domination: {row}")


def linked_owner_model_selftest() -> dict[str, str]:
    rows = [
        {"owner": "vm_run_inner", "armed_state_before": True,
         "matrix_before": True},
        {"owner": "lisp_input_event", "armed_state_before": False,
         "matrix_before": False},
    ]
    _validate_queue_call_rows(rows)
    blanket_rejected = False
    try: _validate_queue_call_rows(rows, blanket=True)
    except Exception: blanket_rejected = True
    CARD.require(blanket_rejected,
                 "blanket queue-domination mutation survived")
    mutant = [dict(row) for row in rows]
    mutant[0]["armed_state_before"] = False
    evaluator_rejected = False
    try: _validate_queue_call_rows(mutant)
    except Exception: evaluator_rejected = True
    CARD.require(evaluator_rejected,
                 "unguarded evaluator-edge mutation survived")
    return {"blanket_requirement": "rejected",
            "unguarded_evaluator_edge": "rejected"}


def linked_owner_gate(elf: Path) -> dict[str, Any]:
    text = subprocess.run([str(OBJDUMP), "-d", str(elf)], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.lower()
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
    functions = [row for row in truth.symbols
                 if row.symbol_type == "Function" and row.bytes > 0]
    call = "jsr\t$e000 <c2_kernal_event_poll>"
    calls = [index for index in range(len(text)) if text.startswith(call, index)]
    CARD.require(calls, "final ELF lost legacy closed-capture consumer")
    rows: list[dict[str, Any]] = []
    for index in calls:
        line_start = text.rfind("\n", 0, index) + 1
        address_match = re.match(r"\s*([0-9a-f]+):", text[line_start:index])
        CARD.require(address_match is not None,
                     "linked queue call address is undecodable")
        address = int(address_match.group(1), 16)
        owners = [row for row in functions
                  if row.value <= address < row.value + row.bytes]
        CARD.require(owners, f"linked queue call has no function owner: {address:x}")
        owner = min(owners, key=lambda row: row.bytes)
        function_label = f"{owner.value:08x} <{owner.name}>:"
        function_start = text.rfind(function_label, 0, index)
        CARD.require(function_start >= 0,
                     f"linked queue owner disassembly absent: {owner.name}")
        prefix = text[function_start:index]
        rows.append({"owner": owner.name, "call_address": f"0x{address:04x}",
                     "armed_state_before": "$ff8d" in prefix,
                     "matrix_before": "$ff8a" in prefix})
    _validate_queue_call_rows(rows)
    evaluator = [row for row in rows if row["owner"] == "vm_run_inner"]
    public = [row for row in rows if row["owner"] == "lisp_input_event"]
    CARD.require(len(evaluator) == 1 and len(public) == 1,
                 "linked queue consumer role cardinality drift")
    return {"queue_poll_calls": len(calls),
            "dominated_calls": len(evaluator),
            "armed_state": "0xFF8D", "matrix_pending": "0xFF8A",
            "consumers": rows,
            "mutations": linked_owner_model_selftest(),
            "rule": "only evaluator drain requires capture domination; public key-event remains legitimate"}


def check_receipt() -> dict[str, Any]:
    value = CARD.BASE.load(RECEIPT)
    linked = value["queue_single_owner"]
    roles_green = (linked.get("consumers") is not None
        and [row["owner"] for row in linked["consumers"]] ==
            ["vm_run_inner", "lisp_input_event"]
        and linked["dominated_calls"] == 1)
    CARD.require(value["status"] == FINAL_STATUS
        and value["attempt_accounting"] == {"cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1,
            "media_builds": 0, "device_contacts": 0}
        and (roles_green or linked["queue_poll_calls"] ==
            linked["dominated_calls"])
        and value["source_single_owner"]["status"] ==
            "PASS: ARMED CAPTURE IS SOLE HARDWARE QUEUE OWNER",
        "queue single-owner final receipt drift")
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
    if action == "check" and FINAL_RED.is_file() and not RECEIPT.exists():
        red = CARD.BASE.load(FINAL_RED)
        CARD.require(red["status"] ==
                "FINAL RED: V1.6 ACTIVE-FRAME LIVENESS STOPS"
            and red["attempt_accounting"]["cards_consumed"] == 1
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_link_attempts"] == 1
            and "ordinary text displaced the mapped far facade" in
                red["error"]["message"],
            "queue single-owner Final Red drift")
        print("v1.6 queue single-owner: CHECK FINAL RED capacity=ordinary-text")
        return 0
    result = CARD.main()
    if action == "card" and RECEIPT.is_file():
        value = CARD.BASE.load(RECEIPT)
        value["queue_single_owner_authority"] = authority()
        value["queue_single_owner_predecessor"] = CARD.BASE.bind(PREDECESSOR)
        value["queue_race_attribution"] = CARD.BASE.bind(ATTRIBUTION)
        value["source_single_owner"] = OWNER.derive()
        value["queue_single_owner"] = linked_owner_gate(CARD.PRODUCT_ELF)
        RECEIPT.write_bytes(CARD.canonical(value))
        check_receipt()
    return result


if __name__ == "__main__":
    install()
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: CARD.record_red(error)
            except Exception as receipt_error:
                print(f"single-owner Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 queue single-owner: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
