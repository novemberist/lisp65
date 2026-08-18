#!/usr/bin/env python3
"""Preserve the historical First Red after its authorized source successor."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_phase1_rescue_result as OLD  # noqa: E402
import c2_v21_terminal_screen_map_authority_rebind as MAP_REBIND  # noqa: E402


RESULT = OLD.RESULT_RECEIPT
EXPECTED_RESULT_SHA256 = "854ca98130fbcc520f7714861fd4b46ece2b7616b76c75d021eee0f1981b4bc8"
EXPECTED_OLD_SOURCE_SHA256 = "0880d62000e9f21d7b6e0ccd279b47f8f0b85b57d264e939bac7dfb6cde19af5"


class SuccessorError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value: raise SuccessorError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == EXPECTED_RESULT_SHA256,
            "historical phase-1 result bytes changed")
    value = json.loads(raw)
    require(isinstance(value, dict), "historical phase-1 result is not an object")
    return value


def check() -> None:
    result = load(RESULT)
    OLD.audit(result)
    require(result.get("mutations") == OLD.mutations(result)
        and result.get("authority", {}).get("reader_source", {}).get("sha256") ==
            EXPECTED_OLD_SOURCE_SHA256
        and result.get("classification", {}).get("name") ==
            "CPU-reader MAP mask borrow contamination/self-occlusion"
        and result.get("mechanism", {}).get("captured_tuple", {}).get("MAPL") ==
            "0xffc0"
        and result.get("mechanism", {}).get("required_tuple", {}).get("MAPL") ==
            "0x4fc0",
        "historical phase-1 semantic authority drift")
    MAP_REBIND.check()
    fixed = MAP_REBIND.load(MAP_REBIND.RECEIPT)
    model = fixed["semantic_equivalence"]["model"]
    require(model["positive"]["MAPL"] == "0x4fc0"
        and [row["MAPL"] for row in model["negative_self_covering"]] ==
            ["0xffc0", "0x2fc0"],
        "authorized phase-1 source successor drift")
    print("phase-1 rescue successor: CHECK PASS historical=ffc0 current=4fc0")


if __name__ == "__main__":
    try:
        require(len(sys.argv) == 2 and sys.argv[1] in ("check", "selftest"),
                "usage: c2_v21_phase1_rescue_result_successor.py check|selftest")
        check()
    except Exception as error:
        print(f"PHASE-1 RESCUE SUCCESSOR: {error}", file=sys.stderr)
        raise SystemExit(1)
