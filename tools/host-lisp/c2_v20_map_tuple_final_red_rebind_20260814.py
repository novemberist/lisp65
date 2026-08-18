#!/usr/bin/env python3
"""Loudly rebind the historical MAP-tuple Final Red to its current driver."""

from __future__ import annotations

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

import c2_v20_map_tuple_fix_card as M  # noqa: E402


PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
RECEIPT = M.FINAL_RED_REBIND
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "6772b41e"
RECORDED_ON = "2026-08-14"


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


def authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    require("historical map-tuple receipt drift gets its authorized loud"
            in text and "dated rebind" in text,
            "MAP-tuple rebind authorization absent")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def historical() -> dict[str, Any]:
    require(hashlib.sha256(M.FINAL_RED.read_bytes()).hexdigest()
                == M.HISTORICAL_FINAL_RED_SHA256,
            "historical MAP-tuple Final Red was rewritten")
    value = load(M.FINAL_RED)
    require(value.get("status")
                == "FINAL RED: corrected-tuple card returns to owner"
            and value.get("retry_authorized") is False
            and value["root_cause"]["class"]
                == "GLOBAL-ASM-INVENTORY-DUPLICATE-SUCCESSOR",
            "historical MAP-tuple claim drift")
    return value


def derive() -> dict[str, Any]:
    old = historical()
    return {
        "format": "lisp65-c2.3-v20-map-tuple-final-red-rebind-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: loud semantic-preserving MAP-tuple receipt rebind",
        "authority": {"authorization": authorization(),
            "historical_final_red": bind(M.FINAL_RED),
            "historical_driver": old["post_red_closure"]["driver"],
            "current_driver": bind(M.DRIVER),
            "rebind_driver": bind(DRIVER)},
        "change": {"allowed_paths": ["post_red_closure.driver"],
            "semantic_claims_changed": False,
            "historical_receipt_rewritten": False},
        "claim_continuity": {"root_cause": old["root_cause"]["class"],
            "retry_authorized": old["retry_authorized"],
            "owner_disposition_required": old["owner_disposition_required"]},
        "claim_limit": (
            "Authority/source rebind only. Historical MAP-tuple evidence and "
            "all claims remain unchanged; no card, media or device action."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value == derive(), "MAP-tuple dated rebind drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-history": lambda x: x["change"].update(
            historical_receipt_rewritten=True),
        "hide-semantic-change": lambda x: x["change"].update(
            semantic_claims_changed=True),
        "widen-rebind": lambda x: x["change"]["allowed_paths"].append(
            "root_cause.class"),
        "authorize-retry": lambda x: x["claim_continuity"].update(
            retry_authorized=True),
        "detach-current-driver": lambda x: x["authority"][
            "current_driver"].update(sha256="0" * 64),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "MAP-tuple rebind mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "MAP-tuple dated rebind exists")
    value = derive(); validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("MAP-tuple dated rebind: PASS fields=1 mutations=5")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value)
    require(rejected == mutations(value), "MAP-tuple rebind mutation set drift")
    print("MAP-tuple dated rebind: PASS historical=unchanged live=bound")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check"),
            "usage: c2_v20_map_tuple_final_red_rebind_20260814.py record|check")
    {"record": record, "check": check}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RebindError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"MAP-tuple dated rebind: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
