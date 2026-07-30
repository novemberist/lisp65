#!/usr/bin/env python3
"""Qualify v1.2.4 pre-chain hygiene under the mandatory source-gate rule."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / "c2.2-v1.2.4-a1-prechain-hygiene-receipt.json"
LOG_ROOT = ROOT / "build/c2.2/v1.2.4/a1"
CHECK_SOURCE_LOG = LOG_ROOT / "check-source.log"
EQUIVALENCE_LOG = LOG_ROOT / "equivalence.log"
EQUIVALENCE = ROOT / "build/equivalence/equivalence-completion.json"
DOCUMENT_INDEX = ROOT / "config/document-index.json"
PROMOTION_REGISTER = ROOT / "config/promotion-register.json"
ASSET_INVENTORY = ROOT / "config/evidence-archive-assets.json"
LINK81 = EVIDENCE / "c2.2-v1.2.4-phase-e-link81-receipt.json"
PHASE_M = EVIDENCE / "c2.2-v1.2.4-phase-m-hardware-receipt.json"


class A1Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise A1Error(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing file: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(command: list[str], output: Path) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result.stdout, encoding="utf-8")
    require(result.returncode == 0, f"{' '.join(command)} failed")
    require("FIRST RED" not in result.stdout, "First Red present in green lane")
    return result.stdout


def clean_tree() -> None:
    output = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True)
    allowed = f"?? {RECEIPT.relative_to(ROOT)}"
    rows = [row for row in output.splitlines() if row and row != allowed]
    require(not rows, f"A1 requires a clean tracked tree: {rows[:8]}")


def authorities() -> tuple[dict[str, Any], dict[str, Any]]:
    link = load(LINK81)
    phase_m = load(PHASE_M)
    require(
        link.get("status") == "passed-bound-Link81-and-check-source"
        and link.get("qualifying_candidate", {}).get("link") == 81,
        "Link-81 authority drift")
    require(
        phase_m.get("status")
        == "passed-one-bundled-session-with-M1-harness-correction"
        and phase_m.get("M3_fx", {}).get("status")
        == "passed-target-multiply-divide-rounding-smoke"
        and phase_m.get("M4_time", {}).get("status")
        == "passed-50Hz-calibration",
        "Phase-M feature-history authority drift")
    return link, phase_m


def build(run_lanes: bool) -> dict[str, Any]:
    authorities()
    if run_lanes:
        clean_tree()
        check_source = run(["make", "-k", "check-source"], CHECK_SOURCE_LOG)
        equivalence = run(
            ["make", "--no-print-directory",
             "equivalence-completion-canary-check"],
            EQUIVALENCE_LOG)
        for witness in (
            "c2-bound-artifact-source-parity: PASS",
            "c2-random-base-gate: PASS",
            "c2-v124-fx-gate: PASS",
            "c2-v124-time-gate: PASS",
            "c2-repl-banner-version: PASS subtitle='WORKBENCH 1.2.4'",
            "document-index: PASS",
            "r6-g6-seal: REGISTERED SET PASS count=4",
        ):
            require(witness in check_source,
                    f"check-source witness missing: {witness}")
        require(
            "equivalence-completion-canary: PASS lanes=11 executed=447"
            in equivalence,
            "equivalence completion witness absent")
    eq = load(EQUIVALENCE)
    index = load(DOCUMENT_INDEX)
    register = load(PROMOTION_REGISTER)
    inventory = load(ASSET_INVENTORY)
    require(
        eq.get("status") == "passed-complete-chain"
        and eq.get("lane_count") == 11
        and eq.get("executed_case_count") == 447
        and all(row.get("executed_cases") == row.get("expected_cases")
                for row in eq.get("lanes", [])),
        "equivalence execution receipt drift")
    require(
        isinstance(index.get("documents"), list)
        and isinstance(register.get("promotions"), list),
        "document/promotion registry drift")
    return {
        "format": "lisp65-v1.2.4-a1-prechain-hygiene-v1",
        "version": 1,
        "recorded_on": date.today().isoformat(),
        "status": "passed-prechain-hygiene-check-source-no-exceptions",
        "candidate": {
            "name": "Link 81",
            "source_head_at_gate": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT,
                text=True).strip(),
            "r4_state": "blocked-until-delta-and-fresh-reproduction",
        },
        "check_source": {
            "status": "passed",
            "exception_list": [],
            "binding": bind(CHECK_SOURCE_LOG),
            "required_by_release_rule": True,
        },
        "equivalence": {
            "status": "passed",
            "lanes_executed": 11,
            "cases_executed": 447,
            "all_lanes_positive_and_exact": True,
            "receipt": bind(EQUIVALENCE),
            "log": bind(EQUIVALENCE_LOG),
        },
        "document_index": {
            "status": "passed",
            "tracked_documents": len(index["documents"]),
            "binding": bind(DOCUMENT_INDEX),
        },
        "receipt_tree": {
            "promotion_records": len(register["promotions"]),
            "asset_inventory_archives": len(inventory.get("archives", [])),
            "status": "passed",
        },
        "link81": bind(LINK81),
        "phase_m_feature_history": {
            "receipt": bind(PHASE_M),
            "fx": "passed-target-multiply-divide-rounding-smoke",
            "time_hz": 51.96615805290813,
            "classification": "feature-history-not-v1.2.4-acceptance",
        },
        "authority": {"verifier": bind(Path(__file__).resolve())},
        "claim_limit": (
            "A1 host/pre-chain hygiene only. Phase-M observations are feature "
            "history, not fresh v1.2.4 G5/G6 acceptance. No promotion, tag, "
            "release or public push is created.")
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "verify"))
    args = parser.parse_args()
    try:
        if args.action == "write":
            value = build(run_lanes=True)
            RECEIPT.write_text(
                json.dumps(value, indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
            print(
                "c2-v1.2.4-a1: PASS check-source=green exceptions=0 "
                "lanes=11 executed=447")
        else:
            require(RECEIPT.is_file(), "A1 receipt missing")
            require(load(RECEIPT) == build(run_lanes=False),
                    "A1 receipt or authority drift")
            print(
                "c2-v1.2.4-a1: VERIFY PASS check-source=green "
                "exceptions=0 lanes=11 executed=447")
        return 0
    except (A1Error, OSError, KeyError, ValueError) as error:
        print(f"c2-v1.2.4-a1: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
