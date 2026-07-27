#!/usr/bin/env python3
"""One pure replay with the authorized post-BSS-triage 33-byte wall pin."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_handoff_reanchor_wplto_symbol_replay as BASE  # noqa: E402


OUT = ROOT / (
    "build/c2.2/substitution/"
    "link33-handoff-reanchor-wplto-wall-pin-replay")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-handoff-reanchor-wplto-wall-pin-pure-replay-receipt.json")
PREVIOUS_RECEIPT = BASE.RECEIPT
PREVIOUS_RECEIPT_SHA256 = (
    "c06df28dd7126cb4203665b5f3026278f9d55d1f8dc58addaa4b8fdbbf544f0f")
DIAGNOSIS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-handoff-reanchor-wplto-symbol-replay-wall-pin-diagnosis.json")
DIAGNOSIS_SHA256 = (
    "960fde9558d6fc9c1fbb4d6afdcff8eefa6a5688f98c6fb82309f65463a8dd65")


class ReplayError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"wall-pin replay input absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
        "mode": oct(path.stat().st_mode & 0o777),
    }


def authorization_gate() -> dict[str, Any]:
    require(sha(PREVIOUS_RECEIPT) == PREVIOUS_RECEIPT_SHA256,
            "wall-pin predecessor First Red drift")
    require(sha(DIAGNOSIS) == DIAGNOSIS_SHA256,
            "wall-pin diagnosis drift")
    predecessor = json.loads(PREVIOUS_RECEIPT.read_text(encoding="utf-8"))
    require(predecessor.get("status") ==
            "FIRST RED: symbol pure replay stopped",
            "wall-pin successor does not bind the reviewed First Red")
    contract = json.loads(BASE.TRUTH_CONTRACT.read_text(encoding="utf-8"))
    authorization = contract.get(
        "fixed_hot_block_wall_pin_replay_authorization_2026_07_21", {})
    require(authorization.get("status") ==
            "owner-authorized-pin-273-to-33-and-one-pure-replay"
            and authorization.get("bound_elf_sha256") ==
            BASE.ORIGINAL.ELF_SHA256
            and authorization.get("new_pin_bytes") == 33,
            "33-byte wall-pin replay authorization drift")
    return {
        "status": "passed-bound-33-byte-wall-pin-authorization",
        "previous_first_red": bind(PREVIOUS_RECEIPT),
        "diagnosis": bind(DIAGNOSIS),
        "elf_truth_contract": bind(BASE.TRUTH_CONTRACT),
        "canonical_wplto_driver": bind(Path(BASE.W.__file__).resolve()),
        "old_pin_bytes": 273,
        "new_pin_bytes": 33,
    }


def configure_base() -> None:
    BASE.OUT = OUT
    BASE.RECEIPT = RECEIPT
    BASE.FIXED_HOT_BLOCK_HEADROOM_PIN_BYTES = 33
    BASE.REPLAY_FORMAT = (
        "lisp65-c2-handoff-reanchor-wplto-wall-pin-pure-replay-v1")
    BASE.REPLAY_STATUS = "passed-wall-pin-pure-replay-no-link33"
    BASE.FIRST_RED_FORMAT = (
        "lisp65-c2-handoff-reanchor-wplto-wall-pin-pure-replay-first-red-v1")
    BASE.FIRST_RED_STATUS = "FIRST RED: wall-pin pure replay stopped"
    BASE.authorization_gate = authorization_gate


def run() -> dict[str, Any]:
    configure_base()
    return BASE.replay_once()


def check() -> dict[str, Any]:
    configure_base()
    value = BASE.check()
    require(value.get("status") == "passed-wall-pin-pure-replay-no-link33",
            "wall-pin replay receipt is not green")
    require(value["resident_walls"]["fixed_hot_block_headroom_bytes"] == 33,
            "wall-pin replay did not bind 33 bytes")
    return value


def selftest() -> dict[str, Any]:
    configure_base()
    result = BASE.selftest()
    require(BASE.FIXED_HOT_BLOCK_HEADROOM_PIN_BYTES == 33,
            "wall-pin selftest did not select 33 bytes")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "run", "check"))
    args = parser.parse_args()
    result = (selftest() if args.action == "selftest" else
              run() if args.action == "run" else check())
    print("c2-handoff-reanchor-wplto-wall-replay: " + result["status"])
    return 3 if str(result["status"]).startswith("FIRST RED") else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, BASE.ReplayError, BASE.ORIGINAL.ReplayError,
            BASE.PREVIOUS.ReplayError, BASE.ISLAND.GateError,
            BASE.W.ProbeError, BASE.BOOT.GateError, BASE.ELF.ElfTruthError,
            RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-handoff-reanchor-wplto-wall-replay: FAIL {error}",
              file=sys.stderr)
        raise SystemExit(2)
