#!/usr/bin/env python3
"""Loud reopen-gap source-closure rebind for the liveness card driver."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_reopen_gap_attribution_rebind_product_liveness_20260815 as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
PREVIOUS = ARCH / (
    "c2.3-v2.1-reopen-gap-attribution-product-liveness-rebind-"
    "20260815-receipt.json")
RECEIPT = ARCH / (
    "c2.3-v2.1-reopen-gap-attribution-liveness-card-rebind-"
    "20260815-receipt.json")
CARD = ROOT / "tools/host-lisp/c2_v21_product_loading_liveness_card.py"
GATES = ROOT / "mk/gates.mk"
READER = ROOT / "src/optional/c2_map_cpu_read.s"

AUTHORIZATION = "395a91aa"
FORMAT = "lisp65-c2.3-v2.1-reopen-gap-liveness-card-rebind-v1"


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


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in ("product card authorized", "one product card",
                  "liveness ordinal", "wrapper/schema preflight"):
        require(token in text, f"liveness-card rebind authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def current_attribution() -> dict[str, Any]:
    return PREV.current_attribution()


def derive() -> dict[str, Any]:
    previous = load(PREVIOUS)
    current = current_attribution()
    projection = PREV.OLD.semantic_projection(current)
    require(projection == previous.get("semantic_projection"),
            "reopen-gap result changed during liveness-card rebind")
    old_count = previous.get("source_scan", {}).get("current_tracked_files")
    new_count = current["dependency_inventory"]["active_pin_scan"][
        "tracked_text_files"]
    require(isinstance(old_count, int) and new_count > old_count,
            "liveness-card source closure did not grow additively")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-15",
        "status": "PASS: LOUD LIVENESS-CARD SOURCE-CLOSURE REBIND",
        "authority": {"owner": authority(), "previous_rebind": bind(PREVIOUS)},
        "inputs": {"card_driver": bind(CARD), "gates": bind(GATES),
                   "product_reader": bind(READER)},
        "source_scan": {"previous_tracked_files": old_count,
                        "current_tracked_files": new_count},
        "semantic_projection": projection,
        "result": {"semantic_conclusion": "byteidentical",
                   "gap0": "derived", "gap1": "derived", "gap2": "fixed",
                   "historical_receipts_changed": False, "device_contacts": 0},
        "claim_limit": (
            "Loud source-closure rebind only; it spends no product card and "
            "adds no Completion, medium, device or release authority.")}
    value["mutations"] = mutations(value)
    audit(value)
    return value


def audit(value: dict[str, Any]) -> None:
    require(
        value.get("status") == "PASS: LOUD LIVENESS-CARD SOURCE-CLOSURE REBIND"
        and value.get("result") == {"semantic_conclusion": "byteidentical",
            "gap0": "derived", "gap1": "derived", "gap2": "fixed",
            "historical_receipts_changed": False, "device_contacts": 0}
        and value.get("source_scan", {}).get("current_tracked_files", 0) >
            value.get("source_scan", {}).get("previous_tracked_files", 0)
        and len(value.get("inputs", {})) == 3
        and value.get("claim_limit", "").startswith("Loud source-closure"),
        "liveness-card source-closure rebind drift")


def mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-history": lambda x: x["result"].update(
            historical_receipts_changed=True),
        "change-gap0": lambda x: x["result"].update(gap0="fixed"),
        "drop-card-driver": lambda x: x["inputs"].pop("card_driver"),
        "claim-device": lambda x: x["result"].update(device_contacts=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(base)
        mutate(trial)
        try:
            audit(trial)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "liveness-card rebind mutation survived")
    return rejected


def record() -> dict[str, Any]:
    require(not RECEIPT.exists(), "liveness-card rebind receipt exists")
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    return value


def check() -> dict[str, Any]:
    value = load(RECEIPT)
    audit(value)
    require(value == derive(), "liveness-card source-closure rebind stale")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("record", "check", "selftest"))
    args = parser.parse_args()
    value = record() if args.action == "record" else (
        check() if args.action == "check" else derive())
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RebindError, PREV.RebindError, PREV.OLD.RebindError,
            PREV.OLD.ATTR.AttributionError, OSError, KeyError, ValueError,
            subprocess.CalledProcessError) as error:
        print(f"LIVENESS-CARD SOURCE REBIND: {error}", file=sys.stderr)
        raise SystemExit(1)
