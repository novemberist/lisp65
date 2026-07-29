#!/usr/bin/env python3
"""Qualify the v1.2.1 Link-77 pre-chain hygiene gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import post_12_housekeeping as HOUSEKEEPING  # noqa: E402


PLAN = ROOT / "docs/planning/v1.2.1-release-plan.md"
EQUIVALENCE = ROOT / "build/equivalence/equivalence-completion.json"
LINK77 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link77-random-while-structural-receipt.json")
HARDWARE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link77-gc-discriminator-bundled-hardware-receipt.json")
INDEX = ROOT / "config/document-index.json"
REGISTER = ROOT / "config/promotion-register.json"
ASSETS = ROOT / "config/evidence-archive-assets.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.1-a1-prechain-hygiene-receipt.json")
LOG_ROOT = ROOT / "build/c2.2/v1.2.1/a1"


class A1Error(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise A1Error(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    path = path.resolve()
    require(path.is_file() and not path.is_symlink(), f"missing file: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing JSON: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise A1Error(f"cannot load {path}: {error}") from error
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(command: list[str], name: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    (LOG_ROOT / f"{name}.log").write_text(result.stdout, encoding="utf-8")
    require(result.returncode == 0, f"{name} failed:\n{result.stdout[-4000:]}")
    return result.stdout


def git_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False)
    require(result.returncode == 0, result.stderr.strip() or "git failed")
    return [line for line in result.stdout.splitlines() if line]


def validate_equivalence() -> dict[str, Any]:
    value = load(EQUIVALENCE)
    lanes = value.get("lanes")
    require(
        value.get("format") == "lisp65-equivalence-completion-v2"
        and value.get("status") == "passed-complete-chain"
        and value.get("lane_count") == 11
        and value.get("executed_case_count") == 447
        and isinstance(lanes, list) and len(lanes) == 11,
        "equivalence completion receipt drift",
    )
    require(
        all(
            type(row.get("executed_cases")) is int
            and row["executed_cases"] > 0
            and row["executed_cases"] == row.get("expected_cases")
            for row in lanes
        ),
        "equivalence lane lacks an exact positive execution witness",
    )
    return value


def validate_link77() -> tuple[dict[str, Any], dict[str, Any]]:
    structural = load(LINK77)
    hardware = load(HARDWARE)
    require(
        structural.get("status") == "passed-Link77-random-while-hardware-not-run"
        and hardware.get("status")
        == "completed-GC-random-RUNSTOP-IRQ-DIRMISS-bundle",
        "Link-77 receipt status drift",
    )
    rows = hardware.get("product_rows")
    require(
        isinstance(rows, list) and len(rows) == 7
        and not hardware.get("row_local_first_reds")
        and all(row.get("status") == "passed" for row in rows),
        "Link-77 hardware row closure drift",
    )
    require(
        hardware.get("GC", {}).get("status") == "completed-oom-not-reproduced"
        and hardware.get("DIRMISS", {}).get("answer", {}).get(
            "outcome")
        == "renderer-consumption-attributed-symname-and-read-seam-exonerated",
        "Link-77 bounded diagnostic disposition drift",
    )
    return structural, hardware


def collect(run_gates: bool) -> dict[str, Any]:
    outputs: dict[str, str] = {}
    if run_gates:
        outputs["equivalence"] = run(
            ["make", "equivalence-check"], "equivalence")
        outputs["document_index"] = run(
            ["make", "document-index-check"], "document-index")
        outputs["promotion_register"] = run(
            ["make", "promotion-register-check"], "promotion-register")

    equivalence = validate_equivalence()
    structural, hardware = validate_link77()
    consistency = HOUSEKEEPING.evidence_consistency()
    if RECEIPT.is_file():
        consistency["tracked_json_receipts_excluding_this_receipt"] -= 1
    index = load(INDEX)
    documents = index.get("documents")
    require(isinstance(documents, list) and len(documents) == 203,
            "document index count drift")
    promotions = load(REGISTER).get("promotions")
    assets = load(ASSETS)
    require(
        isinstance(promotions, list) and len(promotions) == 40
        and assets.get("archive_count") == 43
        and consistency["invalid_json_receipts"] == 0
        and consistency[
            "promotion_archives_bound_in_asset_inventory"] == 40,
        "promotion/evidence inventory drift",
    )
    if outputs:
        require(
            "executed=447" in outputs["equivalence"]
            and re.search(r"document-index: PASS documents=203\b",
                          outputs["document_index"])
            and "promotion-register: PASS promotions=40" in
                outputs["promotion_register"],
            "fresh gate output lacks its expected positive witness",
        )

    tracked_changes = git_lines("diff", "--name-only")
    untracked = [
        path for path in git_lines(
            "ls-files", "--others", "--exclude-standard")
        if path != RECEIPT.relative_to(ROOT).as_posix()
    ]
    head = git_lines("rev-parse", "HEAD")
    require(len(head) == 1 and re.fullmatch(r"[0-9a-f]{40}", head[0]),
            "HEAD identity drift")

    return {
        "format": "lisp65-v1.2.1-a1-prechain-hygiene-v1",
        "version": 1,
        "recorded_on": "2026-07-29",
        "status": "passed-prechain-hygiene",
        "candidate": {
            "name": "Link 77",
            "source_head_before_candidate_commit": head[0],
            "candidate_commit": "pending-before-R4",
            "tracked_modified_paths": len(tracked_changes),
            "untracked_paths": len(untracked),
            "r4_state": "blocked-until-commit-and-fresh-clone-reproduction",
        },
        "equivalence": {
            "status": "passed",
            "lanes_executed": equivalence["lane_count"],
            "cases_executed": equivalence["executed_case_count"],
            "all_lanes_positive_and_exact": True,
            "receipt": bind(EQUIVALENCE),
        },
        "document_index": {
            "status": "passed",
            "tracked_documents": len(documents),
            "binding": bind(INDEX),
        },
        "receipt_tree": {
            "status": "passed",
            **consistency,
        },
        "promotion_register": {
            "status": "passed",
            "records": len(promotions),
            "archives": assets["archive_count"],
            "register": bind(REGISTER),
            "asset_inventory": bind(ASSETS),
        },
        "link77": {
            "structural": bind(LINK77),
            "hardware": bind(HARDWARE),
            "hardware_product_rows": len(hardware["product_rows"]),
            "hardware_row_local_first_reds": 0,
            "gc_disposition": "intermittent-observation-not-reproduced-no-fix",
            "dirmiss_disposition": "renderer-consumer-attributed-host-only-open",
        },
        "authority": {
            "release_plan": bind(PLAN),
            "verifier": bind(Path(__file__)),
            "structural_status": structural["status"],
        },
        "claim_limit": (
            "A1 host/pre-chain hygiene only. This receipt does not create a "
            "candidate commit, Fresh-Clone receipt, R4 seal, hardware "
            "acceptance, promotion, release, tag or public push."
        ),
    }


def write_receipt() -> None:
    value = collect(run_gates=True)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-v1.2.1-a1: PASS "
        f"lanes={value['equivalence']['lanes_executed']} "
        f"cases={value['equivalence']['cases_executed']} "
        f"documents={value['document_index']['tracked_documents']} "
        f"receipts={value['receipt_tree']['tracked_json_receipts_excluding_this_receipt']} "
        f"promotions={value['promotion_register']['records']} "
        "R4=blocked-pending-candidate-commit")


def verify_receipt() -> None:
    recorded = load(RECEIPT)
    expected = collect(run_gates=False)
    require(recorded == expected, "A1 receipt or authority drift")
    print("c2-v1.2.1-a1: VERIFY PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "verify"))
    args = parser.parse_args()
    try:
        if args.action == "write":
            write_receipt()
        else:
            verify_receipt()
        return 0
    except (A1Error, HOUSEKEEPING.HousekeepingError, KeyError, TypeError,
            ValueError) as error:
        print(f"c2-v1.2.1-a1: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
