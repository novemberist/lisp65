#!/usr/bin/env python3
"""Build the released recovery-writer sanitation successor."""

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

from elf_truth import ElfTruth  # noqa: E402
import c2_v160_execution_boundary_backstop_card as CARD  # noqa: E402
import c2_v160_execution_boundary_backstop_uint8_irq_return_replacement_card as LIVE  # noqa: E402

ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
FOLLOWUP = ARCH / "c2.3-v1.6-execution-boundary-followup-result.json"
SCOPE = ARCH / "c2.3-v1.6-execution-boundary-scope-resume.json"
PREDECESSOR_ELF = ROOT / (
    "build/c2.3/v1.6-execution-boundary-backstop-uint8-irq-return-"
    "replacement-card/wplto/lisp65-c2-substitution-linked.prg.elf")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "66ff6c73"
FORMAT = "lisp65-c2-v160-execution-boundary-recovery-sanitization-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 RECOVERY SANITIZATION ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 RECOVERY WRITER OBEYS LIVENESS CONTRACT"


def authority() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").replace("`", "").split())
    for token in ("recovery sanitizes before longjmp completes",
                  "the rescuer is a carrier writer too",
                  "all backstop prices and walls re-prove", "exceptionless"):
        CARD.require(token in text, f"recovery-sanitization authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    result = CARD.load(FOLLOWUP)
    scope = CARD.load(SCOPE)
    CARD.require(result["status"] ==
        "PROVEN: BACKSTOP RECOVERY SELF-REARMS STALE CSR; CURRENT HISTORY AMBIGUOUS"
        and result["static_product_finding"]["class"] ==
            "recovery restores the carrier it is meant to contain"
        and "no in-generation saved CSR pair" in
            result["static_product_finding"]["required_contract"]
        and scope["status"] == "PASS: V1.6 EXECUTION BOUNDARY SCOPE CLOSED READ-ONLY",
        "recovery-sanitization predecessor drift")
    return {**LIVE.predecessor(), "followup_result": CARD.bind(FOLLOWUP),
            "accepted_execution_boundary_scope": CARD.bind(SCOPE),
            "predecessor_ELF": CARD.bind(PREDECESSOR_ELF)}


def pricing() -> dict[str, Any]:
    truth = ElfTruth.read(PREDECESSOR_ELF, llvm_readobj=CARD.GATE.READOBJ,
                          include_section_data=True)
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    service = truth.section(".lisp65_c2_mapped_far_service")
    landing = truth.symbol("retired_window_resume")
    retirement = truth.symbol("c2_rtov_retire_continuations")
    ordinary_before = facade.address - (text.address + text.bytes)
    far_before = 1499 - service.bytes
    CARD.require(ordinary_before == 30 and far_before == 15
                 and landing.bytes == 29 and retirement.bytes == 80,
                 "recovery-sanitization price base drift")
    source = CARD.GATE.source_gate()
    ordinary_delta = (source["landing_bytes"] - landing.bytes
                      + source["recovery_sanitization"]["entry_bytes"])
    far_delta = (source["recovery_sanitization"]["retirement_bytes"]
                 + source["recovery_sanitization"]["shared_saved_CSR_bytes"]
                 - retirement.bytes)
    CARD.require(ordinary_delta == 12 and far_delta == 4
                 and ordinary_before - ordinary_delta == 18
                 and far_before - far_delta == 11,
                 "recovery-sanitization price does not fit standing walls")
    return {"status": "PRICED: RECOVERY SANITIZATION FITS STANDING WALLS",
        "authority": "predecessor final ELF plus emitted successor objects",
        "ordinary_text": {"free_before": ordinary_before,
            "delta_bytes": ordinary_delta, "forecast_free_floor": 18},
        "mapped_far_service": {"free_before": far_before,
            "delta_bytes": far_delta, "forecast_free_floor": 11,
            "capacity_bytes": 1499},
        "implementation": {"landing_bytes": source["landing_bytes"],
            **source["recovery_sanitization"]},
        "E000_delta_bytes": 0, "BSS_delta_bytes": 0}


def install() -> None:
    CARD.BUILD = ROOT / "build/c2.3/v1.6-execution-boundary-recovery-sanitization-card"
    CARD.PREFLIGHT = ROOT / "build/c2.3/v1.6-execution-boundary-recovery-sanitization-preflight"
    CARD.PROCESS = ROOT / "build/c2.3/v1.6-execution-boundary-recovery-sanitization-process"
    CARD.INHERITED_PROCESS = ROOT / "build/c2.3/v1.6-execution-boundary-recovery-sanitization-inherited-process"
    CARD.RECEIPT = ARCH / "c2.3-v1.6-execution-boundary-recovery-sanitization-card-receipt.json"
    CARD.FINAL_RED = ARCH / "c2.3-v1.6-execution-boundary-recovery-sanitization-card-final-red.json"
    CARD.DRIVER = DRIVER
    CARD.AUTHORIZATION = AUTHORIZATION
    CARD.FORMAT = FORMAT
    CARD.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    CARD.FINAL_STATUS = FINAL_STATUS
    CARD.EXPECTED_LANDING_BYTES = 32
    CARD.authority = authority
    CARD.predecessor = predecessor
    CARD.install()


def preflight() -> None:
    install()
    price = pricing()
    CARD.preflight()
    path = CARD.PREFLIGHT / "preflight.json"
    value = CARD.load(path)
    value["recovery_sanitization_pricing"] = price
    path.write_bytes(CARD.canonical(value))
    print("v1.6 recovery sanitization: PREFLIGHT PASS price=18/11 card=0/1")


def check_receipt() -> dict[str, Any]:
    value = CARD.check_receipt()
    recovery = value["execution_boundary_backstop"]["recovery_sanitization"]
    CARD.require(value["status"] == FINAL_STATUS
                 and recovery["dominates_longjmp"] is True
                 and recovery["recovery_reaches_frame_walker"] is False
                 and recovery["shared_saved_CSR_walker"]["pairs"] == 7,
                 "recovery-sanitization card receipt drift")
    return value


def card() -> None:
    install()
    pre = CARD.load(CARD.PREFLIGHT / "preflight.json")
    CARD.require(pre["status"] == PREFLIGHT_STATUS
                 and pre["recovery_sanitization_pricing"]["status"].startswith("PRICED:"),
                 "recovery-sanitization persisted preflight drift")
    CARD.card()
    check_receipt()
    print("v1.6 recovery sanitization: CARD PASS rescuer-writer=sanitized")


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight": preflight(); return 0
    if action == "card": card(); return 0
    if action == "check":
        check_receipt(); print("v1.6 recovery sanitization: CHECK PASS"); return 0
    return CARD.PREV.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: CARD.record_red(error)
            except Exception as receipt_error:
                print(f"recovery-sanitization Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 recovery sanitization: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
