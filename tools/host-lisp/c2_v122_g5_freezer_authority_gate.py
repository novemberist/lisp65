#!/usr/bin/env python3
"""Bind the complete volatile E000 authority used by Freezer checks."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-c1-freezer-cutpoint-contract.json"
WINDOW = ROOT / "src/c2_kernal_window.s"
CLOSE = ROOT / "tools/host-lisp/c2_lite_g5_hardware_close.py"
EXPECTED = {0xFF83, 0xFF84, 0xFF86, 0xFF89}


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def accepted(differences: set[int], allowed: set[int] = EXPECTED) -> bool:
    return differences <= allowed


def main() -> int:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    identity = contract["hardware_protocol"]["freeze_identity"]
    window = WINDOW.read_text(encoding="utf-8")

    spec = importlib.util.spec_from_file_location("g5_close", CLOSE)
    require(spec is not None and spec.loader is not None, "cannot load G5 closer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    require(
        module.E000_VOLATILE_ADDRESSES == EXPECTED,
        "G5 closer volatile E000 authority drift",
    )
    require(
        all(f"FF{address & 0xff:02X}" in identity for address in EXPECTED),
        "Freezer contract omits a volatile E000 address",
    )
    require(
        ".equ C2K_UNOWNED_VIC,     $ff89" in window
        and "sta C2K_UNOWNED_VIC" in window
        and window.index("sta C2K_UNOWNED_VIC")
        > window.index(".Lsource_less:"),
        "FF89 is not bound to the source-less D019 witness",
    )

    mutations = {
        "actual-ff89-rejected-by-old-list": not accepted(
            {0xFF83, 0xFF84, 0xFF89}, EXPECTED - {0xFF89}
        ),
        "uncontracted-ff85-rejected": not accepted({0xFF85}),
        "uncontracted-ff8a-rejected": not accepted({0xFF8A}),
        "complete-authority-accepted": accepted(EXPECTED),
    }
    require(all(mutations.values()), "Freezer authority mutation escaped")
    print(
        "c2-v1.2.2-g5-freezer-authority: PASS "
        f"volatile={len(EXPECTED)} mutations={sum(mutations.values())}/{len(mutations)}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"c2-v1.2.2-g5-freezer-authority: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
