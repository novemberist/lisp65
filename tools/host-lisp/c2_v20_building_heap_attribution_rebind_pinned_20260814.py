#!/usr/bin/env python3
"""Loudly rebind BUILDING-HEAP sources after the pinned-constant sweep."""

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
RECEIPT = B.LATEST_REBIND
PREVIOUS = B.REBIND
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "d615bcf4"
RECORDED_ON = "2026-08-14"
FORMAT = "lisp65-c2.3-v20-building-heap-attribution-rebind-v2"
STATUS = "PASS: second loud semantic-preserving current-source rebind"
RECORDED_PROJECTION_SHA256 = (
    "f2e1dfe19955ea07307276fb835f86d7d8f93df14de40750c5f2a1ef9deac37b")
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
    require("stale building-heap source rebind" in text
            and "loud, dated rebind" in text,
            "second BUILDING-HEAP rebind authorization absent")
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
        result: list[str] = []
        for key in sorted(set(old) | set(new)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in old or key not in new:
                result.append(child)
            else:
                result.extend(changed_paths(old[key], new[key], child))
        return result
    return [] if old == new else [prefix]


def base_values() -> tuple[dict[str, Any], dict[str, Any]]:
    historical = load(B.RECEIPT)
    rejected = historical.pop("mutations_rejected", None)
    B.validate(historical, verify=False)
    require(rejected == B.mutations(historical),
            "historical BUILDING-HEAP mutation set drift")
    current = B.derive(); B.validate(current, verify=False)
    changed = tuple(changed_paths(historical, current))
    require(changed == ALLOWED_LEAVES,
            f"second BUILDING-HEAP rebind exceeds authorized fields: {changed}")
    old_semantic = deepcopy(historical); new_semantic = deepcopy(current)
    for path in ALLOWED:
        without_path(old_semantic, path); without_path(new_semantic, path)
    require(old_semantic == new_semantic,
            "second BUILDING-HEAP semantic projection changed")
    return historical, current


def previous_rebind() -> dict[str, Any]:
    value = load(PREVIOUS)
    require(value.get("format") ==
                "lisp65-c2.3-v20-building-heap-attribution-rebind-v1"
            and value.get("status") ==
                "PASS: loud semantic-preserving current-source rebind"
            and value["change"]["semantic_claims_changed"] is False
            and value["change"]["historical_receipt_rewritten"] is False,
            "first BUILDING-HEAP rebind ancestry drift")
    return value


def derive() -> dict[str, Any]:
    historical, current = base_values(); previous_rebind()
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "authority": {"authorization": authorization(),
            "historical_receipt": bind(B.RECEIPT),
            "previous_rebind": bind(PREVIOUS),
            "historical_driver": historical["authority"]["driver"],
            "current_driver": current["authority"]["driver"],
            "current_projection": bind_raw(B.RECEIPT, B.canonical(current)),
            "rebind_driver": bind(DRIVER)},
        "change": {"allowed_paths": list(ALLOWED),
            "actual_changed_paths": changed_paths(historical, current),
            "semantic_claims_changed": False,
            "historical_receipt_rewritten": False,
            "previous_rebind_rewritten": False},
        "claim_continuity": {"status": current["status"],
            "capture_row_specified": current["disposition"]["capture_row_specified"],
            "recontact_authorized": current["disposition"]["recontact_authorized"],
            "D2_D5_open": current["disposition"]["D2_D5_open"]},
        "claim_limit": (
            "Second authority/source rebind only. Historical evidence, the "
            "first rebind and every BUILDING-HEAP claim remain unchanged."),
    }


def validate(value: dict[str, Any]) -> None:
    # This dated receipt witnesses its own source world.  Reconstructing it
    # from the living BUILDING-HEAP source would make later authorized product
    # work a predicate over historical evidence.
    require(
        value.get("format") == FORMAT
        and value.get("recorded_on") == RECORDED_ON
        and value.get("status") == STATUS
        and value["change"]["allowed_paths"] == list(ALLOWED)
        and value["change"]["actual_changed_paths"] == list(ALLOWED_LEAVES)
        and value["change"]["semantic_claims_changed"] is False
        and value["change"]["historical_receipt_rewritten"] is False
        and value["change"]["previous_rebind_rewritten"] is False
        and value["claim_continuity"]["capture_row_specified"] is True
        and value["claim_continuity"]["recontact_authorized"] is False
        and value["claim_continuity"]["D2_D5_open"] is False
        and value["authority"]["current_projection"]["sha256"]
            == RECORDED_PROJECTION_SHA256,
        "second BUILDING-HEAP dated rebind drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-history": lambda x: x["change"].update(
            historical_receipt_rewritten=True),
        "rewrite-first-rebind": lambda x: x["change"].update(
            previous_rebind_rewritten=True),
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
    require(rejected == list(cases), "second BUILDING-HEAP mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "second BUILDING-HEAP rebind exists")
    require(hashlib.sha256(B.RECEIPT.read_bytes()).hexdigest() ==
                B.HISTORICAL_RECEIPT_SHA256,
            "historical BUILDING-HEAP receipt was rewritten")
    value = derive()
    require(value == derive(), "second BUILDING-HEAP live record drift")
    validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("BUILDING-HEAP second dated rebind: PASS fields=3 mutations=7")


def check() -> None:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value)
    require(rejected == mutations(value), "second rebind mutation drift")
    print("BUILDING-HEAP second dated rebind: CHECK PASS ancestry=2")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check"),
            "usage: rebind_pinned_20260814.py record|check")
    {"record": record, "check": check}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RebindError, B.AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"BUILDING-HEAP second dated rebind: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
