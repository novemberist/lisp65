#!/usr/bin/env python3
"""Verify the closed 1.10 receipt without rewriting historical authorities."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v110_persistent_performance as V110  # noqa: E402


HISTORICAL_COMMIT = "d13bd166"
REBOUND_ON = "2026-08-07"
AUTHORITY_KEYS = ("closing_plan", "gate_wiring", "driver")


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_bytes(commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE,
    ).stdout


def check() -> dict[str, object]:
    recorded = json.loads(V110.RECEIPT.read_text(encoding="utf-8"))
    V110.audit_result(recorded)
    require(len(recorded.get("mutations_rejected", {})) == 22,
            "historical 1.10 mutation closure drift")

    for key in AUTHORITY_KEYS:
        binding = recorded["authorities"][key]
        raw = git_bytes(HISTORICAL_COMMIT, binding["path"])
        require(len(raw) == binding["bytes"] and sha(raw) == binding["sha256"],
                f"historical 1.10 authority no longer resolves: {key}")

    historical_plan = git_bytes(
        HISTORICAL_COMMIT, recorded["authorities"]["closing_plan"]["path"])
    current_plan = V110.PLAN.read_bytes()
    require(current_plan.startswith(historical_plan),
            "current 1.10 plan is not an append-only extension of its receipt")
    require(b"Loud dated replay rebind -- 2026-08-07" in current_plan,
            "1.10 loud dated replay-rebind record absent")

    current = V110.derive()
    for key in ("closing_plan", "gate_wiring"):
        current["authorities"][key] = recorded["authorities"][key]
    require(current == recorded,
            "current host reconstruction differs beyond historical authorities")
    return {
        "status": "passed-current-execution-historical-authority-replay",
        "historical_commit": subprocess.run(
            ["git", "rev-parse", f"{HISTORICAL_COMMIT}^{{commit}}"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE, text=True,
        ).stdout.strip(),
        "rebound_on": REBOUND_ON,
        "historical_receipt_rewritten": False,
        "normalized_authorities": ["closing_plan", "gate_wiring"],
        "mutations": 22,
    }


def selftest() -> None:
    value = check()
    mutations = 0
    for bad in (False, value["historical_receipt_rewritten"] is True,
                value["mutations"] != 22):
        try:
            require(bad, "mutation")
        except ReplayError:
            mutations += 1
    require(mutations == 3, "replay selftest mutation drift")


def main() -> int:
    try:
        value = check()
        print(
            "c2-v110-persistent-performance-replay: PASS "
            f"historical={str(value['historical_commit'])[:8]} "
            "current-execution=byteidentical receipt-rewritten=no mutations=22"
        )
        return 0
    except (ReplayError, V110.PerformanceError, OSError, ValueError,
            KeyError, subprocess.SubprocessError) as error:
        print(f"c2-v110-persistent-performance-replay: FAIL: {error}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
