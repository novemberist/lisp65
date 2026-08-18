#!/usr/bin/env python3
"""Loud source-closure rebind after Link-108 replay and media closure."""

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

import c2_v21_reopen_gap_attribution_rebind_liveness_card_20260815 as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
PREVIOUS = ARCH / (
    "c2.3-v2.1-reopen-gap-attribution-liveness-card-rebind-"
    "20260815-receipt.json")
RECEIPT = ARCH / (
    "c2.3-v2.1-reopen-gap-attribution-liveness-replay-media-rebind-"
    "20260815-receipt.json")
CHECKER = ROOT / "tools/host-lisp/c2_v21_candidate_derived_local_return.py"
REPLAY = ROOT / "tools/host-lisp/c2_v21_product_liveness_artifact_replay.py"
MEDIA = ROOT / "tools/host-lisp/c2_v21_product_liveness_media.py"
GATES = ROOT / "mk/gates.mk"

AUTHORIZATION = "19b76794"
FORMAT = "lisp65-c2.3-v2.1-reopen-gap-liveness-replay-media-rebind-v1"


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
    for token in ("checker rebind and artifact-only replay approved",
                  "no wplto", "new checkers are born candidate-derived",
                  "green proceeds to completion, media and d1"):
        require(token in text, f"replay/media rebind authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def current_attribution() -> dict[str, Any]:
    return PREV.current_attribution()


def derive() -> dict[str, Any]:
    previous = load(PREVIOUS)
    current = current_attribution()
    projection = PREV.PREV.OLD.semantic_projection(current)
    require(projection == previous.get("semantic_projection"),
            "reopen-gap result changed during replay/media rebind")
    old_count = previous["source_scan"]["current_tracked_files"]
    new_count = current["dependency_inventory"]["active_pin_scan"][
        "tracked_text_files"]
    require(new_count > old_count,
            "replay/media source closure did not grow additively")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-15",
        "status": "PASS: LOUD LIVENESS-REPLAY-MEDIA SOURCE-CLOSURE REBIND",
        "authority": {"owner": authority(), "previous_rebind": bind(PREVIOUS)},
        "inputs": {"candidate_checker": bind(CHECKER),
            "artifact_replay": bind(REPLAY), "media_driver": bind(MEDIA),
            "gates": bind(GATES)},
        "source_scan": {"previous_tracked_files": old_count,
                        "current_tracked_files": new_count},
        "semantic_projection": projection,
        "result": {"semantic_conclusion": "byteidentical",
            "gap0": "derived", "gap1": "derived", "gap2": "fixed",
            "historical_receipts_changed": False, "device_contacts": 0},
        "claim_limit": (
            "Loud source-closure rebind only; artifact replay and media are "
            "already complete, while D1 and D2-D5 remain untouched."),
    }
    value["mutations"] = mutations(value)
    audit(value)
    return value


def audit(value: dict[str, Any]) -> None:
    require(
        value.get("status") ==
            "PASS: LOUD LIVENESS-REPLAY-MEDIA SOURCE-CLOSURE REBIND"
        and value.get("result") == {"semantic_conclusion": "byteidentical",
            "gap0": "derived", "gap1": "derived", "gap2": "fixed",
            "historical_receipts_changed": False, "device_contacts": 0}
        and value["source_scan"]["current_tracked_files"] >
            value["source_scan"]["previous_tracked_files"]
        and len(value.get("inputs", {})) == 4,
        "replay/media source-closure rebind drift")


def mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-history": lambda x: x["result"].update(
            historical_receipts_changed=True),
        "change-gap1": lambda x: x["result"].update(gap1="fixed"),
        "drop-birth-checker": lambda x: x["inputs"].pop("candidate_checker"),
        "claim-device": lambda x: x["result"].update(device_contacts=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(base); mutate(trial)
        try:
            audit(trial)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "replay/media rebind mutation survived")
    return rejected


def record() -> dict[str, Any]:
    require(not RECEIPT.exists(), "replay/media rebind receipt exists")
    value = derive(); RECEIPT.write_bytes(canonical(value)); return value


def check() -> dict[str, Any]:
    value = load(RECEIPT); audit(value)
    require(value == derive(), "replay/media source-closure rebind stale")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    value = record() if action == "record" else (
        check() if action == "check" else derive())
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"LIVENESS-REPLAY-MEDIA SOURCE REBIND: {error}", file=sys.stderr)
        raise SystemExit(1)
