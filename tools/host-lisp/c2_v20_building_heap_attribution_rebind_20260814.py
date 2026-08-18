#!/usr/bin/env python3
"""Loudly rebind BUILDING-HEAP attribution to authorized current sources."""

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

import c2_v20_building_heap_attribution as B  # noqa: E402


PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
RECEIPT = B.REBIND
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "421468b1"
RECORDED_ON = "2026-08-14"
FORMAT = "lisp65-c2.3-v20-building-heap-attribution-rebind-v1"
STATUS = "PASS: loud semantic-preserving current-source rebind"
RECORDED_RECEIPT_SHA256 = (
    "ff45e53215d8092fc5e2c9d39d5994dbb0b7dfb4413ae9d7e7a8da314f8b89a7")
ALLOWED = (
    "authority.driver",
    "authority.owner_commission",
    "phase_binding.source_bindings.runtime",
)
ALLOWED_LEAVES = tuple(
    f"{root}.{field}" for root in ALLOWED for field in ("bytes", "sha256"))


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


def bind_raw(path: Path, raw: bytes) -> dict[str, Any]:
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
    require("historical building-heap receipt binding current sources gets its loud"
            in text and "explicitly authorized here, never silent" in text,
            "BUILDING-HEAP rebind authorization absent")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def without_path(value: dict[str, Any], path: str) -> None:
    parts = path.split(".")
    cursor: Any = value
    for part in parts[:-1]:
        cursor = cursor[part]
    del cursor[parts[-1]]


def changed_paths(old: Any, new: Any, prefix: str = "") -> list[str]:
    if isinstance(old, dict) and isinstance(new, dict):
        paths: list[str] = []
        for key in sorted(set(old) | set(new)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in old or key not in new:
                paths.append(child)
            else:
                paths.extend(changed_paths(old[key], new[key], child))
        return paths
    return [] if old == new else [prefix]


def base_values() -> tuple[dict[str, Any], dict[str, Any]]:
    historical = load(B.RECEIPT)
    rejected = historical.pop("mutations_rejected", None)
    B.validate(historical, verify=False)
    require(rejected == B.mutations(historical),
            "historical BUILDING-HEAP mutation set drift")
    current = B.derive()
    B.validate(current, verify=False)
    require(tuple(changed_paths(historical, current)) == ALLOWED_LEAVES,
            f"BUILDING-HEAP rebind exceeds authorized fields: "
            f"{changed_paths(historical, current)}")
    old_semantic = deepcopy(historical)
    new_semantic = deepcopy(current)
    for path in ALLOWED:
        without_path(old_semantic, path)
        without_path(new_semantic, path)
    require(old_semantic == new_semantic,
            "BUILDING-HEAP semantic projection changed")
    return historical, current


def derive() -> dict[str, Any]:
    historical, current = base_values()
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "authority": {"authorization": authorization(),
            "historical_receipt": bind(B.RECEIPT),
            "historical_driver": historical["authority"]["driver"],
            "current_driver": current["authority"]["driver"],
            "current_projection": bind_raw(B.RECEIPT, B.canonical(current)),
            "rebind_driver": bind(DRIVER)},
        "change": {"allowed_paths": list(ALLOWED),
            "actual_changed_paths": changed_paths(historical, current),
            "semantic_claims_changed": False,
            "historical_receipt_rewritten": False},
        "claim_continuity": {"status": current["status"],
            "capture_row_specified": current["disposition"][
                "capture_row_specified"],
            "recontact_authorized": current["disposition"][
                "recontact_authorized"],
            "D2_D5_open": current["disposition"]["D2_D5_open"]},
        "claim_limit": (
            "Authority/source rebind only. Historical evidence and every "
            "BUILDING-HEAP claim remain unchanged; no product, media or device action."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value == derive(), "BUILDING-HEAP dated rebind drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-history": lambda x: x["change"].update(
            historical_receipt_rewritten=True),
        "hide-semantic-change": lambda x: x["change"].update(
            semantic_claims_changed=True),
        "widen-paths": lambda x: x["change"]["allowed_paths"].append(
            "host_model.result"),
        "authorize-contact": lambda x: x["claim_continuity"].update(
            recontact_authorized=True),
        "open-D2-D5": lambda x: x["claim_continuity"].update(D2_D5_open=True),
        "detach-current-projection": lambda x: x["authority"][
            "current_projection"].update(sha256="0" * 64),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "BUILDING-HEAP rebind mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "BUILDING-HEAP dated rebind exists")
    require(hashlib.sha256(B.RECEIPT.read_bytes()).hexdigest()
                == B.HISTORICAL_RECEIPT_SHA256,
            "historical BUILDING-HEAP receipt was rewritten")
    value = derive(); validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("BUILDING-HEAP dated rebind: PASS fields=3 mutations=6")


def check() -> None:
    raw = RECEIPT.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == RECORDED_RECEIPT_SHA256,
            "historical BUILDING-HEAP rebind receipt changed")
    value = json.loads(raw)
    require(
        value.get("format") == FORMAT
        and value.get("status") == STATUS
        and value["change"]["allowed_paths"] == list(ALLOWED)
        and value["change"]["actual_changed_paths"] == list(ALLOWED_LEAVES)
        and value["change"]["semantic_claims_changed"] is False
        and value["change"]["historical_receipt_rewritten"] is False
        and value["claim_continuity"]["recontact_authorized"] is False
        and value["claim_continuity"]["D2_D5_open"] is False
        and value.get("mutations_rejected") == [
            "rewrite-history", "hide-semantic-change", "widen-paths",
            "authorize-contact", "open-D2-D5", "detach-current-projection"],
        "historical BUILDING-HEAP rebind claim drift")
    require(hashlib.sha256(B.RECEIPT.read_bytes()).hexdigest()
                == B.HISTORICAL_RECEIPT_SHA256,
            "historical BUILDING-HEAP receipt changed after rebind")
    print("BUILDING-HEAP dated rebind: PASS historical=immutable successor=required")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check"),
            "usage: c2_v20_building_heap_attribution_rebind_20260814.py record|check")
    {"record": record, "check": check}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RebindError, B.AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"BUILDING-HEAP dated rebind: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
