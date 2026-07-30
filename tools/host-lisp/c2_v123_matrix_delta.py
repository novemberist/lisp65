#!/usr/bin/env python3
"""Bind the v1.2.3 Link-80 cross-invariant delta review.

The nine reachable rows are the already-reviewed while/require/IRQ closure.
This verifier replays their source gates against Link 80 and replaces the
hardware facts with Link-80 observations.  The other sixteen rows retain an
explicit not-re-derived marker.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/1.2.3-work-plan.md"
OWNER_DISPOSITION_COMMIT = "9e7be834"
BASE = EVIDENCE / "c2.2-v1.2.1-link77-cross-invariant-delta-receipt.json"
PHASE_B = EVIDENCE / "c2.2-v1.2.3-phase-b-link80-receipt.json"
HARDWARE = EVIDENCE / "c2.2-v1.2.3-link80-bundled-hardware-receipt.json"
REQUIRE_RETRY = EVIDENCE / (
    "c2.2-v1.2.3-link80-require-device-discriminator-retry-hardware-"
    "receipt.json")
FASTPATH = EVIDENCE / "c2.2-require-idempotence-fastpath-receipt.json"
WHILE = EVIDENCE / "c2.2-v2-while-four-view-receipt.json"
ELF = ROOT / (
    "build/c2.2/v1.2.3-candidate-product-link80/final/"
    "lisp65-c2-substitution-linked.prg.elf")
LOG_ROOT = ROOT / "build/c2.2/v1.2.3/a2"
FRESH_IRQ = LOG_ROOT / "interrupt-ownership-link80.json"
RECEIPT = EVIDENCE / (
    "c2.2-v1.2.3-link80-cross-invariant-delta-receipt.json")

REDERIVED = frozenset(
    ("A3", "A4", "B1", "B2", "C5", "D1", "D2", "D3", "E1"))


class DeltaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise DeltaError(message)


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
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeltaError(f"cannot read {path}: {error}") from error
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    (LOG_ROOT / f"{label}.log").write_text(result.stdout, encoding="utf-8")
    require(result.returncode == 0, f"{label} failed:\n{result.stdout[-5000:]}")
    return result.stdout


def bind_owner_plan() -> dict[str, Any]:
    result = subprocess.run(
        ["git", "show", f"{OWNER_DISPOSITION_COMMIT}:{PLAN.relative_to(ROOT)}"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(result.returncode == 0, "owner-disposition plan blob unavailable")
    return {
        "path": PLAN.relative_to(ROOT).as_posix(),
        "commit": OWNER_DISPOSITION_COMMIT,
        "bytes": len(result.stdout),
        "sha256": hashlib.sha256(result.stdout).hexdigest(),
    }


def fresh_gates() -> dict[str, Any]:
    irq = run([
        sys.executable,
        "tools/host-lisp/c2_interrupt_ownership_gate.py",
        "--elf", ELF.relative_to(ROOT).as_posix(),
        "--receipt", FRESH_IRQ.relative_to(ROOT).as_posix(),
        "--selftest",
    ], "interrupt-ownership")
    while_output = run([
        sys.executable, "tools/host-lisp/c2_while_gate.py", "--source-only",
    ], "while-source")
    require(
        "PASS masks=3 mutations=16/16 elf=yes" in irq,
        "Link-80 interrupt-ownership witness absent")
    require(
        "SOURCE PASS mutations=14 new-opcodes=0 resident-state=0"
        in while_output,
        "while execution-source witness absent")
    return {
        "interrupt_ownership": bind(FRESH_IRQ),
        "interrupt_mutations": 16,
        "while_mutations": 14,
    }


def authorities() -> dict[str, Any]:
    base = load(BASE)
    phase_b = load(PHASE_B)
    hardware = load(HARDWARE)
    retry = load(REQUIRE_RETRY)
    fastpath = load(FASTPATH)
    while_receipt = load(WHILE)
    require(
        base.get("status") == "passed-Link77-delta-review-no-new-open-row"
        and base.get("method", {}).get("rederived_rows") == sorted(REDERIVED)
        and len(base.get("rows", [])) == 25,
        "reviewed nine-row delta authority drift")
    require(
        phase_b.get("status")
        == "passed-B3-bound-successor-product-link-and-check-source"
        and phase_b.get("qualifying_candidate", {}).get("link") == 80,
        "Link-80 structural authority drift")
    product_rows = {
        row.get("id"): row for row in hardware.get("product_rows", [])
        if isinstance(row, dict)
    }
    require(
        product_rows.get("while-smoke", {}).get("result") == "6"
        and product_rows.get("while-run-stop", {}).get("result")
        == "*** stopped (run/stop)"
        and product_rows.get("post-run-stop-repl", {}).get("result") == "3"
        and product_rows.get("irq-mask-low", {}).get("result") == "(0 0)"
        and product_rows.get("irq-mask-high", {}).get("result") == "0",
        "Link-80 while/RUN-STOP/IRQ history drift")
    require(
        retry.get("status") == "anomaly-not-reproduced"
        and retry.get("attempt_1", {}).get("result") == "t"
        and retry.get("attempt_2", {}).get("result") == "t"
        and retry.get("bindings", {}).get("attempt_1", {}).get(
            "place_row", {}).get("sha256")
        == retry.get("bindings", {}).get("attempt_2", {}).get(
            "place_row", {}).get("sha256"),
        "Link-80 require repeat authority drift")
    require(
        fastpath.get("status") == "passed-parser-free-idempotence-fastpath"
        and len(fastpath.get("fallback_mutations", {})) == 5,
        "require-fastpath host authority drift")
    require(
        while_receipt.get("status")
        == "passed-four-view-while-successor-link-authorized-not-run"
        and len(while_receipt.get("mutations_rejected", {})) == 14,
        "while four-view authority drift")
    return {
        "base": base,
        "phase_b": phase_b,
        "hardware": hardware,
        "retry": retry,
        "fastpath": fastpath,
        "while": while_receipt,
        "product_rows": product_rows,
    }


def build(run_fresh: bool) -> dict[str, Any]:
    auth = authorities()
    fresh = fresh_gates() if run_fresh else {
        "interrupt_ownership": bind(FRESH_IRQ),
        "interrupt_mutations": 16,
        "while_mutations": 14,
    }
    rows = deepcopy(auth["base"]["rows"])
    for row in rows:
        row_id = row["id"]
        if row_id in REDERIVED:
            row["review"] = "re-derived-against-Link80-v1.2.3-delta"
            row["authorities"] = sorted(set(
                row.get("authorities", [])
                + ["link80", "link80_hardware", "fresh_irq"]))
            if row_id == "B2":
                row["fresh_facts"].update({
                    "hardware_result": "*** stopped (run/stop)",
                    "post_abort_repl_result": "3",
                })
            elif row_id == "D1":
                row["fresh_facts"].update({
                    "hardware_readback": "(0 0 0)",
                    "masked_families": 3,
                })
            elif row_id == "D3":
                row["fresh_facts"].update({
                    "ordinary_link80_run_stop": "passed",
                    "post_abort_repl_result": "3",
                })
            elif row_id == "E1":
                row["fresh_facts"].update({
                    "hardware_repeat_results": ["t", "t"],
                    "hardware_repeat_row_byteidentical": True,
                    "hardware_LA_markers_17_20_read": False,
                })
                row["proof_boundary"] = (
                    "All five generation/identity mismatches take the slow "
                    "path in the host mutation suite. On hardware a cold-start "
                    "repeat returned t with a byte-identical published row; "
                    "the LA phase markers were not read and are not claimed.")
        else:
            row["review"] = "not-rederived-Link80-v1.2.3-delta-disjoint"
            row["reason"] = (
                "No Link-80 v1.2.3 source, state, control, storage, ownership "
                "or publication edge reaches this crossing. Its reviewed "
                "terminal C2.2 disposition is retained and is explicitly not "
                "presented as fresh Link-80 proof.")
    require(
        sum(row["review"].startswith("re-derived") for row in rows) == 9
        and sum(row["review"].startswith("not-rederived") for row in rows)
        == 16,
        "delta coverage drift")
    return {
        "format": "lisp65-v1.2.3-link80-cross-invariant-delta-v1",
        "version": 1,
        "recorded_on": date.today().isoformat(),
        "status": "passed-Link80-v1.2.3-delta-review-no-new-open-row",
        "candidate": "Link 80",
        "method": {
            "baseline_rows": 25,
            "rederived_rows": sorted(REDERIVED),
            "rederived_count": 9,
            "explicit_not_rederived_count": 16,
            "no_silent_inheritance": True,
        },
        "summary": deepcopy(auth["base"]["summary"]),
        "fresh_execution_witness": {
            "interrupt_ownership_mutations": fresh["interrupt_mutations"],
            "while_source_mutations": fresh["while_mutations"],
        },
        "hardware_claim_boundary": {
            "link80_feature_history": True,
            "fresh_v1.2.3_G5_G6_still_required": True,
            "require_results": ["t", "t"],
            "require_row_byteidentical": True,
            "LA_markers_17_20_read": False,
        },
        "rows": rows,
        "bindings": {
            "owner_disposition_plan": bind_owner_plan(),
            "reviewed_nine_row_delta": bind(BASE),
            "link80": bind(PHASE_B),
            "link80_hardware": bind(HARDWARE),
            "require_retry": bind(REQUIRE_RETRY),
            "fastpath": bind(FASTPATH),
            "while": bind(WHILE),
            "link80_elf": bind(ELF),
            "fresh_irq": fresh["interrupt_ownership"],
            "verifier": bind(Path(__file__).resolve()),
        },
        "claim_limit": (
            "A Link-80 v1.2.3 delta review only. Link-80 hardware is feature "
            "history, not fresh G5/G6 acceptance. C1/E3/E4 remain explicit "
            "C2.3 deferrals; no promotion, tag, release or public push.")
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "verify"))
    args = parser.parse_args()
    try:
        if args.action == "write":
            value = build(run_fresh=True)
            RECEIPT.write_text(
                json.dumps(value, indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
            print(
                "c2-v1.2.3-matrix-delta: PASS rows=25 rederived=9 "
                "explicit-not-rederived=16 new-open=0")
        else:
            require(RECEIPT.is_file(), "delta receipt missing")
            require(load(RECEIPT) == build(run_fresh=False),
                    "delta receipt or authority drift")
            print(
                "c2-v1.2.3-matrix-delta: VERIFY PASS rows=25 "
                "rederived=9 explicit-not-rederived=16")
        return 0
    except (DeltaError, OSError, KeyError, ValueError) as error:
        print(f"c2-v1.2.3-matrix-delta: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
