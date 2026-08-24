#!/usr/bin/env python3
"""Run the single-exit replacement for the v1.6 queue-owner capacity Red."""

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
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-queue-single-owner-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-queue-single-owner-replacement-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-queue-single-owner-replacement-process"
RECEIPT = ARCH / "c2.3-v1.6-queue-single-owner-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-queue-single-owner-replacement-card-final-red.json"
PREDECESSOR = ARCH / "c2.3-v1.6-queue-single-owner-card-final-red.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "b6632c09"
FORMAT = "lisp65-c2-v160-queue-single-owner-replacement-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 QUEUE SINGLE-EXIT REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 QUEUE SINGLE-OWNER FINAL WORLD GREEN"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("collapse the duplicated call", "single-exit shape",
                  "string literal must remain a single instance",
                  "measured in emitted bytes"):
        BASE.CARD.require(token in text, f"single-exit authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    red = BASE.CARD.BASE.load(PREDECESSOR)
    BASE.CARD.require(red["status"] ==
            "FINAL RED: V1.6 ACTIVE-FRAME LIVENESS STOPS"
        and red["attempt_accounting"]["cards_consumed"] == 1
        and red["attempt_accounting"]["WPLTO_runs"] == 1
        and "ordinary text displaced the mapped far facade" in
            red["error"]["message"],
        "single-exit predecessor capacity Red drift")
    owner = BASE.OWNER.derive(); BASE.OWNER.validate(owner)
    return {"capacity_Final_Red": red, "source_single_owner": owner,
            "required_recovery_bytes": 7}


def configure_module() -> None:
    BASE.CARD.configure_for_paths(BUILD, PREFLIGHT,
                                  tag="queue-single-owner-replacement")


def check_receipt() -> dict[str, Any]:
    value = BASE.CARD.BASE.load(RECEIPT)
    elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    emitted_free = facade.address - (text.address + text.bytes)
    owner = value["queue_single_owner"]
    BASE.CARD.require(value["status"] == FINAL_STATUS
        and value["attempt_accounting"] == {"cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1,
            "media_builds": 0, "device_contacts": 0}
        and emitted_free >= 0
        and owner["queue_poll_calls"] == owner["dominated_calls"]
        and value["source_single_owner"]["status"] ==
            "PASS: ARMED CAPTURE IS SOLE HARDWARE QUEUE OWNER",
        "single-exit replacement final receipt drift")
    value.setdefault("single_exit_capacity", {
        "text_start": f"0x{text.address:04X}", "text_bytes": text.bytes,
        "text_end_exclusive": f"0x{text.address + text.bytes:04X}",
        "facade_start": f"0x{facade.address:04X}",
        "free_bytes": emitted_free, "required_recovery_bytes": 7})
    return value


def install() -> None:
    BASE.BUILD = BUILD; BASE.PREFLIGHT = PREFLIGHT; BASE.PROCESS = PROCESS
    BASE.RECEIPT = RECEIPT; BASE.FINAL_RED = FINAL_RED
    BASE.PREDECESSOR = PREDECESSOR; BASE.DRIVER = DRIVER
    BASE.AUTHORIZATION = AUTHORIZATION; BASE.FORMAT = FORMAT
    BASE.PREFLIGHT_STATUS = PREFLIGHT_STATUS; BASE.FINAL_STATUS = FINAL_STATUS
    BASE.authority = authority; BASE.predecessor = predecessor
    BASE.configure_module = configure_module; BASE.check_receipt = check_receipt


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "check" and FINAL_RED.is_file() and not RECEIPT.exists():
        value = BASE.CARD.BASE.load(FINAL_RED)
        BASE.CARD.require(value["format"] == FORMAT + "-final-red"
            and value["status"] ==
                "FINAL RED: V1.6 QUEUE SINGLE-EXIT CAPACITY STOPS"
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["attempt_accounting"]["product_link_attempts"] == 1
            and value["attempt_accounting"]["media_builds"] == 0
            and value["attempt_accounting"]["device_contacts"] == 0
            and "ordinary text displaced the mapped far facade" in
                value["error"]["message"],
            "single-exit replacement Final Red drift")
        print("v1.6 queue single-exit: FINAL RED sealed; card consumed 1/1")
        return 0
    result = BASE.main()
    if action == "card" and RECEIPT.is_file():
        value = check_receipt()
        value["single_exit_authority"] = authority()
        value["single_exit_predecessor"] = BASE.CARD.BASE.bind(PREDECESSOR)
        # check_receipt derives this before persistence; persist only its facts.
        elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
        truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
        text = truth.section(".text"); facade = truth.section(
            ".lisp65_c2_mapped_far_facade")
        value["single_exit_capacity"] = {
            "text_start": f"0x{text.address:04X}", "text_bytes": text.bytes,
            "text_end_exclusive": f"0x{text.address + text.bytes:04X}",
            "facade_start": f"0x{facade.address:04X}",
            "free_bytes": facade.address - (text.address + text.bytes),
            "required_recovery_bytes": 7}
        RECEIPT.write_bytes(BASE.CARD.canonical(value)); check_receipt()
    return result


if __name__ == "__main__":
    install()
    try: raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: BASE.CARD.record_red(error)
            except Exception as receipt_error:
                print(f"single-exit Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 queue single-exit: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
