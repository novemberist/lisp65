#!/usr/bin/env python3
"""Attribute the pre-materialization separate-target continuation Red."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_root_padding_separate_target_continuation as C  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RED = C.FINAL_RED
RECEIPT = ARCH / (
    "c2.3-v2.1-root-padding-separate-target-red-attribution.json")
FORMAT = "lisp65-c2.3-v2.1-separate-target-red-attribution-v1"
STATUS = "ATTRIBUTED FINAL RED: REFERENCE-RELATIVIZATION-API-DOMAIN"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


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


def final_paths() -> list[str]:
    return [path.relative_to(ROOT).as_posix() for path in C.family(C.FINAL)
            if path.exists()]


def validate(value: dict[str, Any]) -> None:
    mechanism = value["mechanism"]
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and mechanism["failed_operation"] == "create-first-input-reference"
        and mechanism["materialization_started"] is False
        and mechanism["final_link_started"] is False
        and mechanism["source_evidence_mode"] == "0555"
        and mechanism["source_evidence_unchanged"] is True
        and mechanism["final_artifacts_present"] == []
        and value["classification"]["product_red"] is False
        and value["classification"]["seed_red"] is False
        and value["classification"]["pre_materialization_harness_red"] is True
        and value["disposition"]["retry_authorized"] is False
        and value["disposition"]["owner_required"] is True,
        "separate-target Red attribution drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-materialization": lambda x: x["mechanism"].update(
            materialization_started=True),
        "claim-link": lambda x: x["mechanism"].update(final_link_started=True),
        "blame-product": lambda x: x["classification"].update(product_red=True),
        "blame-seed": lambda x: x["classification"].update(seed_red=True),
        "hide-immutability": lambda x: x["mechanism"].update(
            source_evidence_unchanged=False),
        "authorize-retry": lambda x: x["disposition"].update(
            retry_authorized=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "separate-target attribution mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    red = load(RED)
    source = C.immutable_tree()
    source_text = Path(__file__).with_name(
        "c2_v21_root_padding_separate_target_continuation.py").read_text(
            encoding="utf-8")
    require(
        red.get("status") ==
            "FINAL RED: SEPARATE-TARGET CONTINUATION RETURNS TO OWNER"
        and red.get("retry_authorized") is False
        and red.get("owner_disposition_required") is True
        and red["error"]["type"] == "ValueError"
        and "is not in the subpath of" in red["error"]["message"]
        and "source.relative_to(path.parent)" in source_text
        and source["mode"] == "0555"
        and not (C.WPLTO / "resident-island.h").exists()
        and final_paths() == [],
        "separate-target failure signature drift")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-17", "status": STATUS,
        "authority": {"Final_Red": bind(RED), "driver": bind(Path(__file__))},
        "mechanism": {
            "class": "REFERENCE-RELATIVIZATION-API-DOMAIN",
            "failed_operation": "create-first-input-reference",
            "source_expression": "source.relative_to(path.parent)",
            "why": (
                "Path.relative_to() requires containment; source and target are "
                "siblings. A relative symlink requires os.path.relpath()."),
            "target_directory_created_by_single_owner": True,
            "materialization_started": False, "final_link_started": False,
            "source_evidence_mode": source["mode"],
            "source_evidence_unchanged":
                source == red["source_evidence"],
            "resident_island_header_present": False,
            "final_artifacts_present": final_paths(),
        },
        "classification": {"product_red": False, "seed_red": False,
            "materializer_red": False, "pre_materialization_harness_red": True},
        "execution_accounting": red["execution_accounting"],
        "disposition": {"retry_authorized": False, "owner_required": True,
            "narrow_repair": (
                "Construct the input reference with os.path.relpath(source, "
                "start=target.parent), mutation-test sibling paths, then decide "
                "whether one replacement bounded run is authorized.")},
        "claim_limit": (
            "Read-only attribution. No input reference, materialization, link, "
            "Completion, medium or device action is authorized."),
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check"))
    action = parser.parse_args().action
    value = derive()
    if action == "record":
        require(not RECEIPT.exists(), "separate-target attribution receipt exists")
        RECEIPT.write_bytes(canonical(value))
    else:
        require(RECEIPT.read_bytes() == canonical(value),
                "separate-target attribution receipt stale")
    print("separate-target Red attribution: PASS pre-materialize link=0 mutations=6")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"separate-target Red attribution: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
