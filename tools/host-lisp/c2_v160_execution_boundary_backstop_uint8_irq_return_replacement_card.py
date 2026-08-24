#!/usr/bin/env python3
"""Final owned IRQ-return continuation replacement for the uint8 card."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_execution_boundary_backstop_card as CARD  # noqa: E402
import c2_v160_execution_boundary_backstop_uint8_abi_facade_replacement_card as FACADE  # noqa: E402

ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
RED = ARCH / "c2.3-v1.6-execution-boundary-backstop-uint8-abi-facade-replacement-card-final-red.json"
ATTRIBUTION = ARCH / "c2.3-v1.6-execution-boundary-irq-return-tail-attribution.json"
AUTHORIZATION = "596e170f"


def authority():
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").replace("`", "").split())
    for token in ("third and final known-family self-disposition",
                  "retired_window_brk_classifier -> c2_kernal_irq_return",
                  "only as jmp", "foreign source", "foreign target",
                  "any further red of any class returns"):
        CARD.require(token in text, f"IRQ-return self-disposition absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor():
    value = FACADE.predecessor()
    red = CARD.load(RED); attribution = CARD.load(ATTRIBUTION)
    CARD.require(red["status"] ==
        "FINAL RED: V1.6 EXECUTION BOUNDARY CARD STOPS"
        and red["attempt_accounting"]["WPLTO_runs"] == 1
        and attribution["status"] ==
        "ATTRIBUTED: IRQ CONTINUATION REJOINS INTERNAL HANDLER RETURN"
        and attribution["finding"]["other_violations_in_configured_final_world"] == 0,
        "IRQ-return predecessor drift")
    return {**value, "uint8_ABI_facade_card_Final_Red": CARD.bind(RED),
            "IRQ_return_tail_attribution": CARD.bind(ATTRIBUTION)}


def install() -> None:
    CARD.BUILD = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-uint8-irq-return-replacement-card"
    CARD.PREFLIGHT = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-uint8-irq-return-replacement-preflight"
    CARD.PROCESS = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-uint8-irq-return-replacement-process"
    CARD.INHERITED_PROCESS = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-uint8-irq-return-replacement-inherited-process"
    CARD.RECEIPT = ARCH / "c2.3-v1.6-execution-boundary-backstop-uint8-irq-return-replacement-card-receipt.json"
    CARD.FINAL_RED = ARCH / "c2.3-v1.6-execution-boundary-backstop-uint8-irq-return-replacement-card-final-red.json"
    CARD.DRIVER = Path(__file__).resolve()
    CARD.AUTHORIZATION = AUTHORIZATION
    CARD.FORMAT = "lisp65-c2-v160-execution-boundary-backstop-uint8-irq-return-replacement-card-v1"
    CARD.PREFLIGHT_STATUS = "PASS: V1.6 EXECUTION BOUNDARY UINT8 IRQ RETURN ARMED 0/1"
    CARD.FINAL_STATUS = "PASS: V1.6 EXECUTION BOUNDARY UINT8 IRQ RETURN FINAL WORLD GREEN"
    CARD.authority = authority
    CARD.predecessor = predecessor
    CARD.install()


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        return CARD.main()
    except Exception as error:
        if action == "card":
            CARD.record_red(error)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
