#!/usr/bin/env python3
"""Loud source-closure rebind for the Link-108 D1 evidence/successor."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_reopen_gap_attribution_rebind_liveness_replay_media_20260815 as OLD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PREVIOUS = ARCH / (
    "c2.3-v2.1-reopen-gap-attribution-liveness-replay-media-rebind-"
    "20260815-receipt.json")
RECEIPT = ARCH / (
    "c2.3-v2.1-reopen-gap-attribution-d1-successor-rebind-"
    "20260815-receipt.json")
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
GATES = ROOT / "mk/gates.mk"
D1 = ROOT / "tools/host-lisp/c2_v21_product_liveness_d1.py"
FIRST_RED = ROOT / "tools/host-lisp/c2_v21_product_liveness_d1_first_red.py"
SUCCESSOR = ROOT / "tools/host-lisp/c2_v21_product_liveness_phase1_successor.py"
RUNNER = ROOT / "scripts/c2-v21-product-liveness-phase1-successor-hw.sh"
FORMAT = "lisp65-c2.3-v2.1-reopen-gap-d1-successor-rebind-v1"


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def derive() -> dict[str, Any]:
    previous = load(PREVIOUS)
    OLD.audit(previous)
    current = OLD.current_attribution()
    projection = OLD.PREV.PREV.OLD.semantic_projection(current)
    require(projection == previous.get("semantic_projection"),
            "reopen-gap result changed during D1-successor rebind")
    old_count = previous["source_scan"]["current_tracked_files"]
    new_count = current["dependency_inventory"]["active_pin_scan"][
        "tracked_text_files"]
    require(new_count > old_count, "D1-successor source closure did not grow")
    value = {"format": FORMAT, "recorded_on": "2026-08-15",
        "status": "PASS: LOUD D1-SUCCESSOR SOURCE-CLOSURE REBIND",
        "authority": {"previous_rebind": bind(PREVIOUS)},
        "inputs": {"D1_checker": bind(D1), "First_Red": bind(FIRST_RED),
            "successor": bind(SUCCESSOR), "successor_runner": bind(RUNNER),
            "gates": bind(GATES), "plan": bind(PLAN)},
        "source_scan": {"previous_tracked_files": old_count,
            "current_tracked_files": new_count},
        "semantic_projection": projection,
        "result": {"semantic_conclusion": "byteidentical",
            "gap0": "derived", "gap1": "derived", "gap2": "fixed",
            "historical_receipts_changed": False, "device_contacts": 0,
            "D1_successor_authorized": False},
        "claim_limit": (
            "Loud source-closure rebind only. It records the crossed D1 and "
            "host-green successor but grants no device-contact authority.")}
    value["mutations"] = mutations(value)
    audit(value)
    return value


def audit(value: dict[str, Any]) -> None:
    require(value.get("status") ==
            "PASS: LOUD D1-SUCCESSOR SOURCE-CLOSURE REBIND"
            and value.get("result") == {"semantic_conclusion": "byteidentical",
                "gap0": "derived", "gap1": "derived", "gap2": "fixed",
                "historical_receipts_changed": False, "device_contacts": 0,
                "D1_successor_authorized": False}
            and value["source_scan"]["current_tracked_files"] >
                value["source_scan"]["previous_tracked_files"]
            and len(value.get("inputs", {})) == 6,
            "D1-successor source-closure rebind drift")


def mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-history": lambda x: x["result"].update(
            historical_receipts_changed=True),
        "change-gap0": lambda x: x["result"].update(gap0="fixed"),
        "drop-successor": lambda x: x["inputs"].pop("successor"),
        "invent-contact-authority": lambda x: x["result"].update(
            D1_successor_authorized=True),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(base); mutate(trial)
        try:
            audit(trial)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "D1-successor rebind mutation survived")
    return rejected


def record() -> dict[str, Any]:
    require(not RECEIPT.exists(), "D1-successor rebind receipt exists")
    value = derive(); RECEIPT.write_bytes(canonical(value)); return value


def check() -> dict[str, Any]:
    value = load(RECEIPT); audit(value)
    require(value == derive(), "D1-successor source-closure rebind stale")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    if action == "record":
        value = record()
    elif action == "check":
        value = check()
    else:
        value = derive(); audit(value)
    print("D1-successor source rebind: PASS "
          f"{value['source_scan']['previous_tracked_files']}->"
          f"{value['source_scan']['current_tracked_files']} mutations=4")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RebindError, OLD.RebindError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"D1-SUCCESSOR SOURCE REBIND: {error}", file=sys.stderr)
        raise SystemExit(1)
