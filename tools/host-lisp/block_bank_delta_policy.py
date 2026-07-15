#!/usr/bin/env python3
"""Validate the prospective bank-delta field used by block receipts."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "config/block-bank-delta-policy.json"
SHA = re.compile(r"[0-9a-f]{64}")


class BankDeltaError(RuntimeError):
    pass


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise BankDeltaError(f"{label} schema drift")
    return value


def _repo_path(value: Any, label: str) -> Path:
    if not isinstance(value, str):
        raise BankDeltaError(f"{label} must be a repository path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or ".." in path.parts:
        raise BankDeltaError(f"{label} is not canonical")
    return ROOT / value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _binding(value: Any, label: str) -> Path:
    item = _exact(value, {"path", "sha256"}, label)
    path = _repo_path(item["path"], f"{label}.path")
    if not SHA.fullmatch(item["sha256"]) or not path.is_file() or path.is_symlink() or _sha(path) != item["sha256"]:
        raise BankDeltaError(f"{label} binding drift")
    return path


def validate_authorization(
    value: Any, *, expected_debit: int, prospective: bool,
    expected_baseline_sha: str | None = None,
    expected_candidate_sha: str | None = None,
) -> None:
    path = _binding(value, "bank_delta.authorization")
    authorization = json.loads(path.read_text(encoding="utf-8"))
    _exact(
        authorization,
        {"format", "id", "status", "authorized_on", "timing", "scope", "baseline", "candidate", "authorized_debit_bytes", "attribution", "evidence", "decision"},
        "debit authorization",
    )
    if (
        authorization["format"] != "lisp65-bank-debit-authorization-v1"
        or authorization["status"] != "authorized"
        or authorization["authorized_debit_bytes"] != expected_debit
        or (prospective and authorization["timing"] != "pre-authorized")
    ):
        raise BankDeltaError("debit authorization does not cover this delta")
    if prospective:
        baseline = authorization["baseline"]
        candidate = authorization["candidate"]
        if (
            not isinstance(baseline, dict)
            or not isinstance(candidate, dict)
            or baseline.get("product_sha256") != expected_baseline_sha
            or candidate.get("product_sha256") != expected_candidate_sha
        ):
            raise BankDeltaError("debit authorization product identity drift")


def validate_bank_delta(value: Any, *, prospective: bool = True) -> None:
    item = _exact(
        value,
        {"baseline_product_sha256", "candidate_product_sha256", "baseline_banked_headroom_bytes", "candidate_banked_headroom_bytes", "delta_bytes", "authorization"},
        "bank_delta",
    )
    if not SHA.fullmatch(item["baseline_product_sha256"]) or not SHA.fullmatch(item["candidate_product_sha256"]):
        raise BankDeltaError("bank_delta product identities must be SHA-256 values")
    for key in ("baseline_banked_headroom_bytes", "candidate_banked_headroom_bytes", "delta_bytes"):
        if type(item[key]) is not int:
            raise BankDeltaError(f"bank_delta.{key} must be an integer")
    delta = item["candidate_banked_headroom_bytes"] - item["baseline_banked_headroom_bytes"]
    if delta != item["delta_bytes"]:
        raise BankDeltaError("bank_delta arithmetic drift")
    if delta < 0:
        validate_authorization(
            item["authorization"], expected_debit=-delta, prospective=prospective,
            expected_baseline_sha=item["baseline_product_sha256"],
            expected_candidate_sha=item["candidate_product_sha256"],
        )
    elif item["authorization"] is not None:
        raise BankDeltaError("zero/credit bank delta must not carry an authorization")


def validate_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _exact(value, {"format", "version", "status", "effective_on", "scope", "receipt_field", "rules", "historical_receipt_exceptions", "one_time_retroactive_resolution"}, "policy")
    if (
        value["format"] != "lisp65-block-bank-delta-policy-v1"
        or value["version"] != 1
        or value["status"] != "active"
        or value["scope"] != "all-future-architecture-block-and-family-promotion-receipts"
        or value["receipt_field"] != "bank_delta"
    ):
        raise BankDeltaError("policy identity drift")
    rules = _exact(value["rules"], {"arithmetic", "zero_or_credit", "debit", "unauthorized_drift", "sealed_history"}, "policy.rules")
    if rules["unauthorized_drift"] != "fail" or rules["sealed_history"] != "never-amend":
        raise BankDeltaError("policy fail-closed/immutability drift")
    exceptions = value["historical_receipt_exceptions"]
    if not isinstance(exceptions, list) or [item.get("id") for item in exceptions] != sorted(item.get("id") for item in exceptions):
        raise BankDeltaError("historical exception order drift")
    for index, exception in enumerate(exceptions):
        item = _exact(exception, {"id", "path", "sha256"}, f"exception[{index}]")
        _binding({"path": item["path"], "sha256": item["sha256"]}, f"exception[{index}]")
    retro = _exact(value["one_time_retroactive_resolution"], {"id", "authorization", "precedent"}, "retroactive resolution")
    auth_path = _repo_path(retro["authorization"], "retroactive authorization")
    validate_authorization({"path": retro["authorization"], "sha256": _sha(auth_path)}, expected_debit=120, prospective=False)
    authorization = json.loads(auth_path.read_text(encoding="utf-8"))
    baseline = _exact(authorization["baseline"], {"commit", "post_boot_reserve_bytes", "banked_headroom_bytes"}, "retroactive baseline")
    candidate = _exact(authorization["candidate"], {"commit", "post_boot_reserve_bytes", "banked_headroom_bytes"}, "retroactive candidate")
    attribution = _exact(authorization["attribution"], {"resident_text_bytes", "resident_rodata_bytes", "boot_overlay_bytes", "classification"}, "retroactive attribution")
    decision = _exact(authorization["decision"], {"accepted_bank_bytes", "reclaim_required", "precedent"}, "retroactive decision")
    if (
        retro["precedent"] != "none"
        or authorization["timing"] != "retroactive-one-time-procedural-repair"
        or candidate["banked_headroom_bytes"] != 435
        or candidate["banked_headroom_bytes"] - baseline["banked_headroom_bytes"] != -120
        or attribution["resident_text_bytes"] + attribution["resident_rodata_bytes"] != 120
        or decision != {
            "accepted_bank_bytes": 435,
            "reclaim_required": False,
            "precedent": "none-future-debits-require-prior-authorization",
        }
    ):
        raise BankDeltaError("retroactive authorization became precedent")
    return value


def selftest() -> None:
    validate_policy()
    sample = {
        "baseline_product_sha256": "1" * 64,
        "candidate_product_sha256": "2" * 64,
        "baseline_banked_headroom_bytes": 435,
        "candidate_banked_headroom_bytes": 435,
        "delta_bytes": 0,
        "authorization": None,
    }
    validate_bank_delta(sample)
    mutations = []
    for name, mutate in (
        ("arithmetic", lambda x: x.update(delta_bytes=1)),
        ("unauthorized-debit", lambda x: x.update(candidate_banked_headroom_bytes=434, delta_bytes=-1)),
        ("authorization-on-zero", lambda x: x.update(authorization={})),
        ("bad-product-sha", lambda x: x.update(candidate_product_sha256="bad")),
    ):
        changed = deepcopy(sample); mutate(changed)
        try:
            validate_bank_delta(changed)
        except BankDeltaError:
            continue
        mutations.append(name)
    if mutations:
        raise BankDeltaError(f"selftest accepted mutations: {mutations}")
    print("block-bank-delta-policy: SELFTEST PASS mutations=4")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "selftest"))
    args = parser.parse_args()
    try:
        selftest() if args.command == "selftest" else validate_policy()
        if args.command == "check":
            print("block-bank-delta-policy: PASS historical=2 prospective=mandatory")
        return 0
    except (BankDeltaError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"block-bank-delta-policy: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
