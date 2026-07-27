#!/usr/bin/env python3
"""Pure qualification replay of the frozen capacity-recovery WPLTO ELF."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link50_badopcode_retirement_artifact_replay as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / ("build/c2.2/substitution/"
                 "link50-badopcode-retirement-capacity-recovery-wplto")
PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
FIRST_RED = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-capacity-recovery-"
    "wplto-internal-structural.json")
FIRST_RED_RECEIPT = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-capacity-recovery-wplto-base.json")
ORIGINAL_CAPACITY_RED = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-wplto-capacity-first-red.json")
OUT = ROOT / ("build/c2.2/substitution/"
              "link50-badopcode-retirement-capacity-recovery-replay")
REPLAY_RECEIPT = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-capacity-recovery-"
    "artifact-replay-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-capacity-recovery-wplto-receipt.json")


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"capacity-recovery replay input absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def main() -> int:
    require(sha(FIRST_RED) ==
                "fe4258e02c63292ddac21b12342ecb290b9157133ee51e8c0dd8284c1eac9514"
            and sha(FIRST_RED_RECEIPT) ==
                "16b08fcffed362b95a50c368f095a53fa24cd3d5452f1b06031bd26a79253c63"
            and sha(ORIGINAL_CAPACITY_RED) ==
                "d5bd969497711a06776f0bf21ad766f95bca8df5d7985d4d3281272a8bfe31b2",
            "capacity-recovery authority drift")
    require(not OUT.exists() and not REPLAY_RECEIPT.exists()
            and not RECEIPT.exists(), "capacity-recovery replay is one-shot")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(first["diagnostic"] == {
                "type": "LinkError",
                "message": "fresh Link-47 L65E shape red: {'bytes': 1143, 'cap_bytes': 1320, 'headroom_bytes': 177}"},
            "current replay is not bound to the exact stale L65E checker Red")

    old = {
        "source": BASE.SOURCE, "product": BASE.PRODUCT,
        "elf": BASE.ELF, "map": BASE.MAP,
        "first": BASE.FIRST_RED, "first_receipt": BASE.FIRST_RED_RECEIPT,
        "out": BASE.OUT, "receipt": BASE.RECEIPT,
        "require": BASE.require,
    }

    def current_require(value: bool, message: str) -> None:
        # The imported replay pins the predecessor hashes.  This wrapper pins
        # the current pair above and relaxes only that stale literal check.
        if message in {"retirement WPLTO First-Red authority drift",
                       "artifact replay is not bound to the shape-checker Red"}:
            return
        old["require"](value, message)

    try:
        BASE.SOURCE = SOURCE
        BASE.PRODUCT = PRODUCT
        BASE.ELF = ELF
        BASE.MAP = MAP
        BASE.FIRST_RED = FIRST_RED
        BASE.FIRST_RED_RECEIPT = FIRST_RED_RECEIPT
        BASE.OUT = OUT
        BASE.RECEIPT = REPLAY_RECEIPT
        BASE.require = current_require
        value = BASE.build()
    finally:
        BASE.SOURCE = old["source"]
        BASE.PRODUCT = old["product"]
        BASE.ELF = old["elf"]
        BASE.MAP = old["map"]
        BASE.FIRST_RED = old["first"]
        BASE.FIRST_RED_RECEIPT = old["first_receipt"]
        BASE.OUT = old["out"]
        BASE.RECEIPT = old["receipt"]
        BASE.require = old["require"]

    walls = value["fresh_read_only_replay"]["walls"]
    capacity = value["fresh_read_only_replay"]["capacity"]
    recovered = walls["bank0_text_headroom_bytes"] - 26
    require(recovered >= 6 and walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and capacity["session_family_bytes"] <= 65536,
            "capacity-recovery replay remains red")
    final = {
        "format": "lisp65-c2-badopcode-retirement-capacity-recovery-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-WPLTO-and-pure-qualification-replay",
        "promotable": False,
        "authority": {
            "six_byte_capacity_first_red": bind(ORIGINAL_CAPACITY_RED),
            "checker_first_red": bind(FIRST_RED),
            "checker_first_red_receipt": bind(FIRST_RED_RECEIPT),
            "contract": bind(BASE.CONTRACT),
            "wplto_driver": bind(ROOT / "tools/host-lisp/"
                "c2_lite_v6_link50_badopcode_retirement_capacity_recovery_wplto.py"),
            "replay_driver": bind(Path(__file__)),
        },
        "named_recovery": {
            "object": "c2_product_install",
            "fossil": "non-authoritative VM result kept live across two non-OK completion edges",
            "before_text_headroom_bytes": 26,
            "after_text_headroom_bytes": walls["bank0_text_headroom_bytes"],
            "measured_recovery_bytes": recovered,
            "required_recovery_bytes": 6,
            "preserved": ["inner non-OK vm_status byte-identical",
                          "DIRMISS SYMI detail", "DIRMISS BCODE detail"],
            "error_result": "canonical NIL; never consumed as success",
        },
        "walls": walls,
        "capacity": capacity,
        "frozen_identity": value["frozen_identity"],
        "qualification_replay": bind(REPLAY_RECEIPT),
        "execution_accounting": {
            "whole_program_lto_closure_links": 1,
            "pure_replay_compiler_runs": 0,
            "pure_replay_linker_runs": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0},
        "next_gate": "one separately authorized successor product link",
    }
    write(RECEIPT, final)
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-badopcode-retirement-capacity-recovery-replay: PASS "
          f"recovered={recovered} text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"session={capacity['session_family_bytes']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-badopcode-retirement-capacity-recovery-replay: "
              f"FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
