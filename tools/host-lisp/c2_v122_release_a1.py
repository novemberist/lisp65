#!/usr/bin/env python3
"""Qualify the v1.2.2 Link-78 pre-chain hygiene gate."""

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


PLAN = ROOT / "docs/planning/v1.2.2-release-plan.md"
EQUIVALENCE = ROOT / "build/equivalence/equivalence-completion.json"
LINK78 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link78-dirmiss-renderer-structural-receipt.json")
HARDWARE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link78-d1-d2-bundled-hardware-receipt.json")
G2 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.2-g2-symbol-value-cost-preparation-receipt.json")
INDEX = ROOT / "config/document-index.json"
REGISTER = ROOT / "config/promotion-register.json"
ASSETS = ROOT / "config/evidence-archive-assets.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.2-a1-prechain-hygiene-receipt.json")
LOG_ROOT = ROOT / "build/c2.2/v1.2.2/a1"


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
    require(result.returncode == 0, f"{name} failed:\n{result.stdout[-5000:]}")
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


def validate_link78() -> tuple[dict[str, Any], dict[str, Any]]:
    structural = load(LINK78)
    hardware = load(HARDWARE)
    require(
        structural.get("status")
        == "passed-Link78-D1-renderer-hardware-not-run"
        and structural.get("gates", {}).get("all_green") is True
        and structural.get("link_number") == 78,
        "Link-78 structural authority drift",
    )
    d1 = structural.get("D1", {}).get("host_and_object_gate", {})
    require(
        d1.get("status")
        == "passed-full-name-and-target-pointer-consumption"
        and d1.get("rendered_exactly")
        == "undefined function: intern-renderer-missing"
        and d1.get("host_cases_executed") == 20
        and len(d1.get("target_mutations_rejected", [])) == 5,
        "Link-78 DIRMISS structural witness drift",
    )
    rows = {
        row.get("id"): row for row in hardware.get("passed_rows", [])
        if isinstance(row, dict)
    }
    require(
        hardware.get("status")
        == "D2-returned-to-Class-C-without-investigation"
        and rows.get("dirmiss-full-name", {}).get("outcome")
        == "*** undefined function: intern-renderer-missing"
        and rows.get("post-dirmiss-repl", {}).get("outcome") == "9"
        and hardware.get("stop", {}).get("id") == "define-point"
        and hardware.get("stop", {}).get("diagnostic_actions_after_stop") == 0,
        "Link-78 bounded hardware history drift",
    )
    return structural, hardware


def validate_g2() -> dict[str, Any]:
    value = load(G2)
    require(
        value.get("status")
        == "passed-host-qualified-two-row-measurement-awaiting-bundled-session"
        and value.get("execution_witnesses", {}).get(
            "bound_carrier_cases") == 2
        and value.get("execution_witnesses", {}).get(
            "negative_mutations") == 12
        and value.get("product_delta", {}).get("bytes") == 0
        and value.get("product_delta", {}).get("links") == 0
        and value.get("measurement", {}).get(
            "dominance_threshold_frames") == 44.5,
        "G2 preparation authority drift",
    )
    return value


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
    structural, hardware = validate_link78()
    g2 = validate_g2()
    consistency = HOUSEKEEPING.evidence_consistency()
    if RECEIPT.is_file():
        consistency["tracked_json_receipts_excluding_this_receipt"] -= 1
    documents = load(INDEX).get("documents")
    promotions = load(REGISTER).get("promotions")
    assets = load(ASSETS)
    require(
        isinstance(documents, list) and len(documents) > 0
        and isinstance(promotions, list) and len(promotions) == 41
        and assets.get("archive_count") == 44
        and consistency["invalid_json_receipts"] == 0
        and consistency[
            "promotion_archives_bound_in_asset_inventory"] == 41,
        "document/promotion/evidence inventory drift",
    )
    if outputs:
        require(
            "executed=447" in outputs["equivalence"]
            and re.search(
                rf"document-index: PASS documents={len(documents)}\b",
                outputs["document_index"])
            and "promotion-register: PASS promotions=41" in
                outputs["promotion_register"],
            "fresh gate output lacks its expected positive witness",
        )

    tracked_changes = git_lines("diff", "--name-only")
    untracked = [
        path for path in git_lines(
            "ls-files", "--others", "--exclude-standard")
        if path != RECEIPT.relative_to(ROOT).as_posix()
    ]
    require(
        not tracked_changes and not untracked,
        "A1 must run from an isolated clean Link-78 source closure",
    )
    head = git_lines("rev-parse", "HEAD")
    require(len(head) == 1 and re.fullmatch(r"[0-9a-f]{40}", head[0]),
            "HEAD identity drift")

    return {
        "format": "lisp65-v1.2.2-a1-prechain-hygiene-v1",
        "version": 1,
        "recorded_on": "2026-07-29",
        "status": "passed-prechain-hygiene",
        "candidate": {
            "name": "Link 78",
            "source_head_at_gate": head[0],
            "tracked_modified_paths": 0,
            "untracked_paths_excluding_receipt": 0,
            "r4_state": "blocked-until-A2-and-fresh-candidate-reproduction",
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
        "receipt_tree": {"status": "passed", **consistency},
        "promotion_register": {
            "status": "passed",
            "records": len(promotions),
            "archives": assets["archive_count"],
            "register": bind(REGISTER),
            "asset_inventory": bind(ASSETS),
        },
        "link78": {
            "structural": bind(LINK78),
            "hardware_history": bind(HARDWARE),
            "structural_status": structural["status"],
            "hardware_D1_rows": 2,
            "hardware_D2_stop":
                "recorded-history-not-v1.2.2-acceptance",
        },
        "g2_measurement": {
            "status": "prepared-independent-non-acceptance-rows",
            "carrier_cases":
                g2["execution_witnesses"]["bound_carrier_cases"],
            "negative_mutations_rejected":
                g2["execution_witnesses"]["negative_mutations"],
            "product_delta_bytes": 0,
            "receipt": bind(G2),
        },
        "authority": {
            "release_plan": bind(PLAN),
            "verifier": bind(Path(__file__)),
        },
        "claim_limit": (
            "A1 host/pre-chain hygiene only. Link-78 hardware is feature "
            "history, not fresh v1.2.2 acceptance. This receipt creates no "
            "R4/R5/R6/G5/G6 result, promotion, release, tag or public push."
        ),
    }


def write_receipt() -> None:
    value = collect(run_gates=True)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-v1.2.2-a1: PASS "
        f"lanes={value['equivalence']['lanes_executed']} "
        f"cases={value['equivalence']['cases_executed']} "
        f"documents={value['document_index']['tracked_documents']} "
        f"promotions={value['promotion_register']['records']} "
        "Link78=isolated R4=blocked")


def verify_receipt() -> None:
    recorded = load(RECEIPT)
    expected = collect(run_gates=False)
    require(recorded == expected, "A1 receipt or authority drift")
    print("c2-v1.2.2-a1: VERIFY PASS")


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
        print(f"c2-v1.2.2-a1: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
