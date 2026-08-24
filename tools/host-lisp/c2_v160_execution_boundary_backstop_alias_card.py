#!/usr/bin/env python3
"""Authorized zero-byte-alias replacement for the v1.6 backstop card."""

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
ATTRIBUTION = ARCH / "c2.3-v1.6-execution-boundary-bss-margin-attribution.json"
RED = ARCH / "c2.3-v1.6-execution-boundary-backstop-projection-replacement-card-final-red.json"
AUTHORIZATION = "c9188125"
ORIGINAL_PREDECESSOR = CARD.predecessor


def authority():
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").replace("`", "").split())
    for token in ("exactly one replacement card", "c cells stay private",
                  "global asm aliases point at the same bytes",
                  ".bss back at 1,585", "five-byte margin intact",
                  "alias with its own allocation falls"):
        CARD.require(token in text, f"zero-byte alias authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor():
    value = ORIGINAL_PREDECESSOR()
    attribution = CARD.load(ATTRIBUTION); red = CARD.load(RED)
    CARD.require(attribution["status"] ==
        "ATTRIBUTED: GLOBAL VISIBILITY SPENDS ONE PROTECTED BSS MARGIN BYTE"
        and attribution["replacement_price_candidate"]["expected_BSS_delta"] == 0
        and red["attempt_accounting"]["WPLTO_runs"] == 1,
        "zero-byte alias predecessor drift")
    return {**value, "BSS_margin_attribution": CARD.bind(ATTRIBUTION),
            "protected_margin_Final_Red": CARD.bind(RED)}


def install() -> None:
    CARD.BUILD = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-alias-card"
    CARD.PREFLIGHT = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-alias-preflight"
    CARD.PROCESS = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-alias-process"
    CARD.INHERITED_PROCESS = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-alias-inherited-process"
    CARD.RECEIPT = ARCH / "c2.3-v1.6-execution-boundary-backstop-alias-card-receipt.json"
    CARD.FINAL_RED = ARCH / "c2.3-v1.6-execution-boundary-backstop-alias-card-final-red.json"
    CARD.DRIVER = Path(__file__).resolve()
    CARD.AUTHORIZATION = AUTHORIZATION
    CARD.FORMAT = "lisp65-c2-v160-execution-boundary-backstop-alias-card-v1"
    CARD.PREFLIGHT_STATUS = "PASS: V1.6 EXECUTION BOUNDARY ZERO-BYTE ALIAS ARMED 0/1"
    CARD.FINAL_STATUS = "PASS: V1.6 EXECUTION BOUNDARY ZERO-BYTE ALIAS FINAL WORLD GREEN"
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
