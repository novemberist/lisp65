#!/usr/bin/env python3
"""Owned-IRQ-tail facade replacement for the uint8 backstop card."""

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
import c2_v160_execution_boundary_backstop_uint8_abi_replacement_card as ABI  # noqa: E402

ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
RED = ARCH / "c2.3-v1.6-execution-boundary-backstop-uint8-abi-replacement-card-final-red.json"
ATTRIBUTION = ARCH / "c2.3-v1.6-execution-boundary-irq-tail-facade-attribution.json"
AUTHORIZATION = "3fba877f"


def authority():
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").replace("`", "").split())
    for token in ("fixed facade lacked irq-tail ownership",
                  "exactly one second replacement is self-disposed",
                  "derives the tail address from the final linked symbol",
                  "exact irq-handler owner section",
                  "foreign low target", "missing owned tail edge"):
        CARD.require(token in text, f"IRQ-tail facade self-disposition absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor():
    value = ABI.predecessor()
    red = CARD.load(RED); attribution = CARD.load(ATTRIBUTION)
    CARD.require(red["status"] ==
        "FINAL RED: V1.6 EXECUTION BOUNDARY CARD STOPS"
        and red["attempt_accounting"]["WPLTO_runs"] == 1
        and attribution["status"] ==
        "ATTRIBUTED: FIXED FACADE LACKED IRQ TAIL OWNER CLASS"
        and attribution["finding"]["foreign_low_edges"] == 0,
        "IRQ-tail facade predecessor drift")
    return {**value, "uint8_ABI_card_Final_Red": CARD.bind(RED),
            "IRQ_tail_facade_attribution": CARD.bind(ATTRIBUTION)}


def install() -> None:
    CARD.BUILD = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-uint8-abi-facade-replacement-card"
    CARD.PREFLIGHT = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-uint8-abi-facade-replacement-preflight"
    CARD.PROCESS = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-uint8-abi-facade-replacement-process"
    CARD.INHERITED_PROCESS = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-uint8-abi-facade-replacement-inherited-process"
    CARD.RECEIPT = ARCH / "c2.3-v1.6-execution-boundary-backstop-uint8-abi-facade-replacement-card-receipt.json"
    CARD.FINAL_RED = ARCH / "c2.3-v1.6-execution-boundary-backstop-uint8-abi-facade-replacement-card-final-red.json"
    CARD.DRIVER = Path(__file__).resolve()
    CARD.AUTHORIZATION = AUTHORIZATION
    CARD.FORMAT = "lisp65-c2-v160-execution-boundary-backstop-uint8-abi-facade-replacement-card-v1"
    CARD.PREFLIGHT_STATUS = "PASS: V1.6 EXECUTION BOUNDARY UINT8 ABI FACADE ARMED 0/1"
    CARD.FINAL_STATUS = "PASS: V1.6 EXECUTION BOUNDARY UINT8 ABI FACADE FINAL WORLD GREEN"
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
