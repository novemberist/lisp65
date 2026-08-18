#!/usr/bin/env python3
"""Loudly rebind the historical D1/E25 receipt to current runtime source."""

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

import c2_v20_map_tuple_d1_e25 as E25  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
RECEIPT = ARCH / "c2.3-v2.0-map-tuple-d1-e25-rebind-2026-08-14.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "b3f6adc2"
ALLOWED = ("authority.runtime.bytes", "authority.runtime.sha256")


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
    require("map-tuple fixture red" in text and "full closure" in text,
            "D1/E25 closure rebind authority absent")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def changed_paths(old: Any, new: Any, prefix: str = "") -> list[str]:
    if isinstance(old, dict) and isinstance(new, dict):
        result: list[str] = []
        for key in sorted(set(old) | set(new)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in old or key not in new:
                result.append(child)
            else:
                result.extend(changed_paths(old[key], new[key], child))
        return result
    return [] if old == new else [prefix]


def remove_path(value: dict[str, Any], path: str) -> None:
    parts = path.split("."); cursor: Any = value
    for part in parts[:-1]:
        cursor = cursor[part]
    del cursor[parts[-1]]


def derive() -> dict[str, Any]:
    historical = load(E25.RECEIPT)
    E25.verify(historical)
    current = E25.derive(); E25.verify(current)
    changed = tuple(changed_paths(historical, current))
    require(changed == ALLOWED,
            f"D1/E25 rebind exceeds runtime source authority: {changed}")
    old_semantic = deepcopy(historical); new_semantic = deepcopy(current)
    for path in ALLOWED:
        remove_path(old_semantic, path); remove_path(new_semantic, path)
    require(old_semantic == new_semantic,
            "D1/E25 semantic projection changed")
    return {
        "format": "lisp65-c2.3-v20-map-tuple-d1-e25-rebind-v1",
        "recorded_on": "2026-08-14",
        "status": "PASS: loud semantic-preserving D1/E25 runtime-source rebind",
        "authority": {"authorization": authorization(),
            "historical_receipt": bind(E25.RECEIPT),
            "historical_runtime": historical["authority"]["runtime"],
            "current_runtime": current["authority"]["runtime"],
            "current_projection_sha256": hashlib.sha256(
                E25.canonical(current) if hasattr(E25, "canonical") else
                (json.dumps(current, indent=2, sort_keys=True) + "\n").encode()
            ).hexdigest(),
            "rebind_driver": bind(DRIVER)},
        "change": {"allowed_paths": list(ALLOWED),
            "actual_changed_paths": list(changed),
            "semantic_claims_changed": False,
            "historical_receipt_rewritten": False},
        "claim_continuity": {"status": current["status"],
            "remaining_split": current["classification"]["remaining_split"],
            "capture_status": current["capture"]["status"]},
        "claim_limit": (
            "Source-authority rebind only. Historical E25 evidence and every "
            "semantic claim remain unchanged; no device action is authorized."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(value.get("status") ==
                "PASS: loud semantic-preserving D1/E25 runtime-source rebind"
            and value["change"]["allowed_paths"] == list(ALLOWED)
            and value["change"]["semantic_claims_changed"] is False
            and value["change"]["historical_receipt_rewritten"] is False,
            "D1/E25 rebind receipt red")
    if verify:
        require(value == derive(), "D1/E25 rebind drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-history": lambda x: x["change"].update(
            historical_receipt_rewritten=True),
        "change-claims": lambda x: x["change"].update(
            semantic_claims_changed=True),
        "widen-fields": lambda x: x["change"]["allowed_paths"].append(
            "classification.remaining_split"),
        "collapse-split": lambda x: x["claim_continuity"].update(
            remaining_split=["c2_decode_from"]),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=True)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "D1/E25 rebind mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "D1/E25 rebind receipt exists")
    value = derive(); validate(value, verify=True)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("D1/E25 dated rebind: PASS fields=2 mutations=4")


def check() -> None:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value), "D1/E25 rebind mutation set drift")
    print("D1/E25 dated rebind: CHECK PASS historical=unchanged")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check"),
            "usage: c2_v20_map_tuple_d1_e25_rebind_20260814.py record|check")
    {"record": record, "check": check}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RebindError, E25.EvidenceError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"D1/E25 dated rebind: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
