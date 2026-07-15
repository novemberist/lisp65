#!/usr/bin/env python3
"""Validate the five-dimensional capacity delta required by future receipts."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "config" / "block-capacity-delta-policy.json"
SHA = re.compile(r"[0-9a-f]{64}")
DIMENSIONS = ("bank", "ext", "symbols", "namepool", "directory")


class CapacityDeltaError(RuntimeError):
    pass


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise CapacityDeltaError(f"{label} schema drift")
    return value


def _repo_path(value: Any, label: str) -> Path:
    if not isinstance(value, str):
        raise CapacityDeltaError(f"{label} must be a repository path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or pure.as_posix() != value or ".." in pure.parts:
        raise CapacityDeltaError(f"{label} is not canonical")
    return ROOT / pure


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _binding(value: Any, label: str) -> Path:
    item = _exact(value, {"path", "sha256"}, label)
    path = _repo_path(item["path"], f"{label}.path")
    if (
        not SHA.fullmatch(str(item["sha256"])) or path.is_symlink()
        or not path.is_file() or _sha(path) != item["sha256"]
    ):
        raise CapacityDeltaError(f"{label} binding drift")
    return path


def validate_authorization(value: Any, dimension: str, debit: int, candidate: int) -> None:
    path = _binding(value, f"capacity_delta.{dimension}.authorization")
    authorization = json.loads(path.read_text(encoding="utf-8"))
    _exact(
        authorization,
        {
            "format", "id", "status", "authorized_on", "timing", "scope",
            "authorized_debits", "required_floors", "attribution", "decision",
        },
        "capacity authorization",
    )
    if (
        authorization["format"] != "lisp65-capacity-debit-authorization-v1"
        or authorization["status"] != "authorized"
        or authorization["timing"] != "pre-authorized"
        or authorization["scope"] != "r3-cold-start-product-block"
    ):
        raise CapacityDeltaError("capacity authorization identity/timing drift")
    debits = authorization["authorized_debits"]
    floors = authorization["required_floors"]
    attribution = authorization["attribution"]
    if isinstance(attribution, dict):
        _binding(attribution, "capacity authorization attribution")
    elif not isinstance(attribution, str) or not attribution:
        raise CapacityDeltaError("capacity authorization attribution is empty")
    if not isinstance(authorization["decision"], str) or not authorization["decision"]:
        raise CapacityDeltaError("capacity authorization decision is empty")
    if (
        not isinstance(debits, dict) or set(debits) - set(DIMENSIONS)
        or not isinstance(floors, dict) or set(floors) != set(DIMENSIONS)
        or type(debits.get(dimension)) is not int or debit > debits[dimension]
        or type(floors[dimension]) is not int or candidate < floors[dimension]
    ):
        raise CapacityDeltaError(f"capacity authorization does not cover {dimension}")


def validate_capacity_delta(value: Any) -> None:
    item = _exact(
        value,
        {"baseline_identity_sha256", "candidate_identity_sha256", "dimensions"},
        "capacity_delta",
    )
    if not SHA.fullmatch(str(item["baseline_identity_sha256"])) or not SHA.fullmatch(
        str(item["candidate_identity_sha256"])
    ):
        raise CapacityDeltaError("capacity_delta identity drift")
    dimensions = _exact(item["dimensions"], set(DIMENSIONS), "capacity_delta.dimensions")
    for name in DIMENSIONS:
        dimension = _exact(
            dimensions[name], {"baseline", "candidate", "delta", "authorization"},
            f"capacity_delta.{name}",
        )
        values = (dimension["baseline"], dimension["candidate"], dimension["delta"])
        if any(type(number) is not int for number in values):
            raise CapacityDeltaError(f"capacity_delta.{name} values must be integers")
        delta = dimension["candidate"] - dimension["baseline"]
        if delta != dimension["delta"]:
            raise CapacityDeltaError(f"capacity_delta.{name} arithmetic drift")
        if delta < 0:
            validate_authorization(
                dimension["authorization"], name, -delta, dimension["candidate"],
            )
        elif dimension["authorization"] is not None:
            raise CapacityDeltaError(
                f"capacity_delta.{name} zero/credit must not carry authorization"
            )


def validate_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _exact(
        value,
        {
            "format", "version", "status", "effective_on", "scope",
            "receipt_field", "dimensions", "rules", "legacy_bank_policy",
        },
        "capacity policy",
    )
    if (
        value["format"] != "lisp65-block-capacity-delta-policy-v1"
        or value["version"] != 1 or value["status"] != "active"
        or value["scope"]
        != "all-future-architecture-block-family-and-release-promotion-receipts"
        or value["receipt_field"] != "capacity_delta"
    ):
        raise CapacityDeltaError("capacity policy identity drift")
    dimensions = _exact(value["dimensions"], set(DIMENSIONS), "policy.dimensions")
    for name in DIMENSIONS:
        if dimensions[name] not in (
            {"unit": "bytes", "direction": "larger-is-better"},
            {"unit": "entries", "direction": "larger-is-better"},
        ):
            raise CapacityDeltaError(f"capacity policy dimension drift: {name}")
    rules = _exact(
        value["rules"],
        {"arithmetic", "zero_or_credit", "debit", "unauthorized_drift", "sealed_history"},
        "policy.rules",
    )
    if rules["unauthorized_drift"] != "fail" or rules["sealed_history"] != "never-amend":
        raise CapacityDeltaError("capacity policy fail-closed/immutability drift")
    _binding(value["legacy_bank_policy"], "legacy_bank_policy")
    return value


def sample() -> dict[str, Any]:
    return {
        "baseline_identity_sha256": "1" * 64,
        "candidate_identity_sha256": "2" * 64,
        "dimensions": {
            name: {"baseline": 100, "candidate": 100, "delta": 0, "authorization": None}
            for name in DIMENSIONS
        },
    }


def selftest() -> None:
    validate_policy()
    validate_capacity_delta(sample())
    survivors: list[str] = []
    for name, mutate in (
        ("missing-dimension", lambda x: x["dimensions"].pop("ext")),
        ("arithmetic", lambda x: x["dimensions"]["bank"].update(delta=1)),
        (
            "unauthorized-debit",
            lambda x: x["dimensions"]["symbols"].update(candidate=99, delta=-1),
        ),
        (
            "authorization-on-credit",
            lambda x: x["dimensions"]["ext"].update(candidate=101, delta=1, authorization={}),
        ),
    ):
        changed = deepcopy(sample())
        mutate(changed)
        try:
            validate_capacity_delta(changed)
        except CapacityDeltaError:
            continue
        survivors.append(name)
    if survivors:
        raise CapacityDeltaError(f"selftest accepted mutations: {survivors}")
    print("block-capacity-delta-policy: SELFTEST PASS mutations=4 dimensions=5")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "selftest"))
    args = parser.parse_args()
    try:
        selftest() if args.command == "selftest" else validate_policy()
        if args.command == "check":
            print("block-capacity-delta-policy: PASS dimensions=5 prospective=mandatory")
        return 0
    except (CapacityDeltaError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"block-capacity-delta-policy: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
