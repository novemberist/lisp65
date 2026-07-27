#!/usr/bin/env python3
"""One fresh WPLTO proving the six-byte BADOPCODE-retirement recovery.

This consumes the owner-authorized confirming map after the first retirement
WPLTO stopped with 26 bytes of Bank-0 text headroom.  It creates no promotable
product link and performs no hardware action.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link50_badopcode_retirement_wplto as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
FIRST_RED = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-wplto-capacity-first-red.json")
OUT = ROOT / ("build/c2.2/substitution/"
              "link50-badopcode-retirement-capacity-recovery-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-capacity-recovery-"
    "wplto-internal-structural.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-capacity-recovery-wplto-base.json")
RECEIPT = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-capacity-recovery-wplto-receipt.json")


class RecoveryError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RecoveryError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"capacity-recovery evidence absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def main() -> int:
    require(sha(FIRST_RED) ==
            "d5bd969497711a06776f0bf21ad766f95bca8df5d7985d4d3281272a8bfe31b2",
            "26-byte capacity First Red authority drift")
    require(not OUT.exists() and not INTERNAL.exists()
            and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
            "capacity-recovery WPLTO is one-shot")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    measurement = first["fresh_read_only_measurement"]
    require(measurement["walls"]["bank0_text_headroom_bytes"] == 26
            and measurement["required"]
                ["bank0_text_noise_reserve_bytes"] == 32,
            "capacity First Red is not the authorized six-byte shortfall")

    old = (BASE.OUT, BASE.INTERNAL, BASE.RECEIPT)
    try:
        BASE.OUT = OUT
        BASE.INTERNAL = INTERNAL
        BASE.RECEIPT = BASE_RECEIPT
        result = BASE.main()
    finally:
        BASE.OUT, BASE.INTERNAL, BASE.RECEIPT = old
    if result != 0:
        return result

    base = json.loads(BASE_RECEIPT.read_text(encoding="utf-8"))
    walls = base["capacity"]["walls"]
    recovered = walls["bank0_text_headroom_bytes"] - 26
    require(recovered >= 6
            and walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54,
            "named error-result fossil did not recover the required six bytes")
    value = {
        "format": "lisp65-c2-badopcode-retirement-capacity-recovery-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-named-fossil-recovery-and-all-WPLTO-walls",
        "promotable": False,
        "authority": {"six_byte_first_red": bind(FIRST_RED),
                      "contract": bind(BASE.CONTRACT),
                      "driver": bind(Path(__file__))},
        "named_recovery": {
            "object": "c2_product_install",
            "fossil": "non-authoritative VM result kept live across two non-OK completion edges",
            "removed_behavior": "return arbitrary VM result while vm_status is non-OK",
            "preserved_behavior": "the inner non-OK vm_status remains byte-identical and vm_check_status consumes it immediately",
            "before_text_headroom_bytes": 26,
            "after_text_headroom_bytes": walls["bank0_text_headroom_bytes"],
            "measured_recovery_bytes": recovered,
            "required_recovery_bytes": 6},
        "fresh_wplto": base,
        "identity": {"product": base["product_shaped_identity"],
                     "elf": base["product_shaped_elf"]},
        "walls": walls,
        "capacity": base["capacity"],
        "execution_accounting": {
            "whole_program_lto_closure_links": 1,
            "promotable_product_links": 0,
            "hardware_runs": 0},
        "next_gate": "one separately authorized successor product link",
    }
    write(RECEIPT, value)
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-badopcode-retirement-capacity-recovery-wplto: PASS "
          f"recovered={recovered} text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RecoveryError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-badopcode-retirement-capacity-recovery-wplto: "
              f"FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
