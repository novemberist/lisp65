#!/usr/bin/env python3
"""Authorized uint8_t successor for the v1.6 execution-boundary backstop."""

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

ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
ATTRIBUTION = ARCH / "c2.3-v1.6-execution-boundary-alias-lto-attribution.json"
RED = ARCH / "c2.3-v1.6-execution-boundary-backstop-alias-card-final-red.json"
AUTHORIZATION = "5c41adf2"
ORIGINAL_PREDECESSOR = CARD.predecessor


def authority():
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").replace("`", "").split())
    for token in ("exactly one successor card", "explicitly as uint8_t",
                  "every c consumer is proven", "one-byte emission",
                  ".bss back at 1,585", "five-byte validation margin restored",
                  "widened re-emission falls"):
        CARD.require(token in text, f"uint8 successor authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor():
    value = ORIGINAL_PREDECESSOR()
    attribution = CARD.load(ATTRIBUTION); red = CARD.load(RED)
    CARD.require(attribution["status"] ==
        "ATTRIBUTED: EXTERNAL ASM USE RESTORES C INT WIDTH TO TWO BYTES"
        and attribution["remaining_byte"]["symbol"] == "lisp_toplevel_active"
        and attribution["decision"]["successor_authorized"] is False
        and red["attempt_accounting"]["WPLTO_runs"] == 1,
        "uint8 successor predecessor drift")
    return {**value, "alias_LTO_attribution": CARD.bind(ATTRIBUTION),
            "alias_card_Final_Red": CARD.bind(RED)}


def install() -> None:
    CARD.BUILD = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-uint8-card"
    CARD.PREFLIGHT = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-uint8-preflight"
    CARD.PROCESS = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-uint8-process"
    CARD.INHERITED_PROCESS = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-uint8-inherited-process"
    CARD.RECEIPT = ARCH / "c2.3-v1.6-execution-boundary-backstop-uint8-card-receipt.json"
    CARD.FINAL_RED = ARCH / "c2.3-v1.6-execution-boundary-backstop-uint8-card-final-red.json"
    CARD.DRIVER = Path(__file__).resolve()
    CARD.AUTHORIZATION = AUTHORIZATION
    CARD.FORMAT = "lisp65-c2-v160-execution-boundary-backstop-uint8-card-v1"
    CARD.PREFLIGHT_STATUS = "PASS: V1.6 EXECUTION BOUNDARY UINT8 ARMED 0/1"
    CARD.FINAL_STATUS = "PASS: V1.6 EXECUTION BOUNDARY UINT8 FINAL WORLD GREEN"
    CARD.authority = authority
    CARD.predecessor = predecessor
    CARD.install()


def main() -> int:
    install(); action = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        return CARD.main()
    except Exception as error:
        if action == "card": CARD.record_red(error)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
