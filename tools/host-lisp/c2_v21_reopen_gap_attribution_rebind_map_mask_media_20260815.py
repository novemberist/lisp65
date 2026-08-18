#!/usr/bin/env python3
"""Loud source-closure rebind for Link-109 Completion/media."""

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

import c2_v21_reopen_gap_attribution_rebind_map_mask_fix_20260815 as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PREVIOUS = PREV.RECEIPT
RECEIPT = ARCH / (
    "c2.3-v2.1-reopen-gap-attribution-map-mask-media-rebind-"
    "20260815-receipt.json")
MEDIA = ROOT / "tools/host-lisp/c2_v21_map_mask_fix_media.py"
CARD_RECEIPT = ARCH / "c2.3-v2.1-map-mask-fix-card-receipt.json"
DEPENDENCY_SUCCESSOR = ROOT / (
    "tools/host-lisp/c2_v21_dependency_invariant_successor_check.py")
GATES = ROOT / "mk/gates.mk"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
AUTHORIZATION = "e63e6240"


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value: raise RebindError(message)


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
    full = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    require("green proceeds to completion, media" in text,
            "Link-109 media authority absent")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def derive() -> dict[str, Any]:
    previous = load(PREVIOUS); PREV.audit(previous)
    current = PREV.PREV.PREV.OLD.current_attribution()
    projection = PREV.PREV.PREV.OLD.PREV.PREV.OLD.semantic_projection(current)
    require(projection == previous["semantic_projection"],
            "reopen-gap result changed during Link-109 media rebind")
    old_count = previous["source_scan"]["current_tracked_files"]
    new_count = current["dependency_inventory"]["active_pin_scan"][
        "tracked_text_files"]
    require(new_count > old_count, "Link-109 media source closure did not grow")
    value = {"format": "lisp65-c2.3-v2.1-reopen-gap-map-mask-media-rebind-v1",
        "recorded_on": "2026-08-15",
        "status": "PASS: LOUD LINK109-MEDIA SOURCE-CLOSURE REBIND",
        "authority": {"owner": authority(), "previous_rebind": bind(PREVIOUS)},
        "inputs": {"media": bind(MEDIA), "green_card": bind(CARD_RECEIPT),
            "dependency_successor": bind(DEPENDENCY_SUCCESSOR),
            "gates": bind(GATES), "plan": bind(PLAN)},
        "source_scan": {"previous_tracked_files": old_count,
                        "current_tracked_files": new_count},
        "semantic_projection": projection,
        "result": {"semantic_conclusion": "byteidentical",
            "gap0": "derived", "gap1": "derived", "gap2": "fixed",
            "historical_receipts_changed": False,
            "product_artifacts_changed": False,
            "bound_green_cards": 1, "cards_by_rebind": 0,
            "device_contacts_by_rebind": 0},
        "claim_limit": "Source-closure rebind only; no Completion/media/device action."}
    value["mutations"] = mutations(value); audit(value); return value


def audit(value: dict[str, Any]) -> None:
    require(value.get("status") ==
            "PASS: LOUD LINK109-MEDIA SOURCE-CLOSURE REBIND"
        and value.get("result") == {"semantic_conclusion": "byteidentical",
            "gap0": "derived", "gap1": "derived", "gap2": "fixed",
            "historical_receipts_changed": False,
            "product_artifacts_changed": False, "bound_green_cards": 1,
            "cards_by_rebind": 0, "device_contacts_by_rebind": 0}
        and value["source_scan"]["current_tracked_files"] >
            value["source_scan"]["previous_tracked_files"]
        and len(value.get("inputs", {})) == 5,
        "Link-109 media rebind drift")


def mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-history": lambda x: x["result"].update(
            historical_receipts_changed=True),
        "change-gap1": lambda x: x["result"].update(gap1="fixed"),
        "drop-media": lambda x: x["inputs"].pop("media"),
        "invent-artifact": lambda x: x["result"].update(
            product_artifacts_changed=True),
        "spend-card": lambda x: x["result"].update(cards_by_rebind=1),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(base); mutate(trial)
        try: audit(trial)
        except RebindError: rejected.append(name)
    require(rejected == list(cases), "Link-109 media rebind mutation survived")
    return rejected


def record() -> dict[str, Any]:
    require(not RECEIPT.exists(), "Link-109 media rebind receipt exists")
    value = derive(); RECEIPT.write_bytes(canonical(value)); return value


def check() -> dict[str, Any]:
    value = load(RECEIPT); audit(value)
    require(value == derive(), "Link-109 media source-closure rebind stale")
    return value


def main() -> int:
    action = argparse.ArgumentParser()
    action.add_argument("action", choices=("record", "check", "selftest"))
    selected = action.parse_args().action
    value = record() if selected == "record" else (
        check() if selected == "check" else derive())
    print("Link-109 media source rebind: PASS "
          f"{value['source_scan']['previous_tracked_files']}->"
          f"{value['source_scan']['current_tracked_files']} mutations=5")
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        print(f"LINK109 MEDIA SOURCE REBIND: {error}", file=sys.stderr)
        raise SystemExit(1)
