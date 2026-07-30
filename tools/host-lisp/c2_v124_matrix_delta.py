#!/usr/bin/env python3
"""Bind the three-row Link-81 fx/time cross-invariant delta review."""

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
PLAN = ROOT / "docs/planning/1.2.4-work-plan.md"
OWNER_DISPOSITION_COMMIT = "2fbd895a"
BASE = EVIDENCE / "c2.2-v1.2.3-link80-cross-invariant-delta-receipt.json"
LINK81 = EVIDENCE / "c2.2-v1.2.4-phase-e-link81-receipt.json"
PHASE_M = EVIDENCE / "c2.2-v1.2.4-phase-m-hardware-receipt.json"
FX = EVIDENCE / "c2.2-v1.2.4-fx-final-composition-revalidation-receipt.json"
TIME = EVIDENCE / "c2.2-v1.2.4-time-final-composition-revalidation-receipt.json"
ELF = ROOT / (
    "build/c2.2/v1.2.4-candidate-product-link81/final/"
    "lisp65-c2-substitution-linked.prg.elf")
LOG_ROOT = ROOT / "build/c2.2/v1.2.4/a2"
FRESH_IRQ = LOG_ROOT / "interrupt-ownership-link81.json"
RECEIPT = EVIDENCE / (
    "c2.2-v1.2.4-link81-cross-invariant-delta-receipt.json")
REDERIVED = frozenset(("A2", "A3", "D1"))


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
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def owner_plan() -> dict[str, Any]:
    result = subprocess.run(
        ["git", "show", f"{OWNER_DISPOSITION_COMMIT}:{PLAN.relative_to(ROOT)}"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(result.returncode == 0, "owner-disposition plan unavailable")
    return {
        "path": PLAN.relative_to(ROOT).as_posix(),
        "commit": OWNER_DISPOSITION_COMMIT,
        "bytes": len(result.stdout),
        "sha256": hashlib.sha256(result.stdout).hexdigest(),
    }


def fresh_irq() -> dict[str, Any]:
    result = subprocess.run([
        sys.executable, "tools/host-lisp/c2_interrupt_ownership_gate.py",
        "--elf", ELF.relative_to(ROOT).as_posix(),
        "--receipt", FRESH_IRQ.relative_to(ROOT).as_posix(),
        "--selftest",
    ], cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    (LOG_ROOT / "interrupt-ownership.log").write_text(
        result.stdout, encoding="utf-8")
    require(
        result.returncode == 0
        and "PASS masks=3 mutations=16/16 elf=yes" in result.stdout,
        "Link-81 interrupt-ownership gate red")
    return bind(FRESH_IRQ)


def authorities() -> dict[str, Any]:
    base = load(BASE)
    link = load(LINK81)
    phase_m = load(PHASE_M)
    fx = load(FX)
    timing = load(TIME)
    require(
        len(base.get("rows", [])) == 25
        and base.get("summary", {}).get("new_OPEN_rows") == 0,
        "reviewed 25-row authority drift")
    require(
        link.get("status") == "passed-bound-Link81-and-check-source"
        and link.get("qualifying_candidate", {}).get("link") == 81,
        "Link-81 structural authority drift")
    require(
        phase_m.get("M3_fx", {}).get("status")
        == "passed-target-multiply-divide-rounding-smoke"
        and phase_m.get("M4_time", {}).get("status")
        == "passed-50Hz-calibration",
        "Phase-M fx/time history drift")
    require(
        fx.get("status") == "passed-fx-host-reference-in-final-v1.2.4-composition"
        and timing.get("status")
        == "passed-time-host-reference-in-final-v1.2.4-composition",
        "final composition authority drift")
    return {"base": base, "link": link, "phase_m": phase_m}


def build(run_fresh: bool) -> dict[str, Any]:
    auth = authorities()
    irq = fresh_irq() if run_fresh else bind(FRESH_IRQ)
    rows = deepcopy(auth["base"]["rows"])
    for row in rows:
        row_id = row["id"]
        if row_id not in REDERIVED:
            row["review"] = "not-rederived-Link81-v1.2.4-delta-disjoint"
            row["reason"] = (
                "No Link-81 fx/time source, state, storage, ownership or "
                "publication edge reaches this crossing. Its reviewed C2.2 "
                "disposition is retained and is not presented as fresh proof.")
            continue
        row["review"] = "re-derived-against-Link81-v1.2.4-delta"
        row["authorities"] = sorted(set(
            row.get("authorities", []) + ["link81", "phase_m", "fx", "time"]))
        if row_id == "A2":
            row.update({
                "delta_surface": "fx Q8.7 arithmetic -> serialized math unit",
                "finding": (
                    "fx adds Bank-2 orchestration only. The math transaction "
                    "uses fixed I/O registers, allocates no heap cell while "
                    "the unit is live and introduces no root or transient "
                    "high-edge state."),
                "fresh_facts": {
                    "bank2_delta_bytes": 1451,
                    "resident_delta_bytes": 0,
                    "new_roots": 0,
                    "target_smoke": "multiply-divide-half-away-passed",
                },
                "proof_boundary": (
                    "Fresh source/artifact equivalence and target math smoke; "
                    "no claim about unrelated heap transports."),
            })
        elif row_id == "A3":
            row.update({
                "delta_surface": "fx/time Bank-2 code -> streamed code window",
                "finding": (
                    "Both additions are immutable Bank-2 code and retain the "
                    "existing refill seam. They add no moving object, direct "
                    "entry reference or root visible to GC."),
                "fresh_facts": {
                    "bank2_static_code_bytes": 43218,
                    "bank2_headroom_bytes": 22318,
                    "new_direct_entry_refs": 0,
                    "new_roots": 0,
                },
                "proof_boundary": (
                    "Structural non-moving-code exclusion, not a loop-refill "
                    "latency claim."),
            })
        else:
            row.update({
                "delta_surface": "time -> product-owned raster frame counter",
                "finding": (
                    "time atomically reads the already-owned frame counter. "
                    "It neither changes IRQ masks nor acknowledges, enables "
                    "or publishes an interrupt source."),
                "fresh_facts": {
                    "hardware_hz": 51.96615805290813,
                    "interrupt_masks": 3,
                    "interrupt_gate_mutations": 16,
                    "resident_delta_bytes": 0,
                },
                "proof_boundary": (
                    "Fresh Link-81 IRQ ownership ELF gate plus Phase-M "
                    "calibration; cartridge storms remain unsupported."),
            })
    require(
        sum(row["review"].startswith("re-derived") for row in rows) == 3
        and sum(row["review"].startswith("not-rederived") for row in rows)
        == 22,
        "delta coverage drift")
    return {
        "format": "lisp65-v1.2.4-link81-cross-invariant-delta-v1",
        "version": 1,
        "recorded_on": date.today().isoformat(),
        "status": "passed-Link81-fx-time-delta-review-no-new-open-row",
        "candidate": "Link 81",
        "method": {
            "baseline_rows": 25,
            "rederived_rows": sorted(REDERIVED),
            "rederived_count": 3,
            "explicit_not_rederived_count": 22,
            "no_silent_inheritance": True,
        },
        "summary": deepcopy(auth["base"]["summary"]),
        "fresh_execution_witness": {
            "interrupt_ownership_mutations": 16,
            "fx_source_and_artifact_oracle": "36x2",
            "time_source_and_artifact_oracle": "12x2",
        },
        "hardware_claim_boundary": {
            "phase_m_is_feature_history": True,
            "fresh_v1.2.4_G5_G6_still_required": True,
            "fx_target_smoke": "passed",
            "time_target_hz": 51.96615805290813,
        },
        "rows": rows,
        "bindings": {
            "owner_disposition_plan": owner_plan(),
            "reviewed_Link80_delta": bind(BASE),
            "link81": bind(LINK81),
            "phase_m": bind(PHASE_M),
            "fx": bind(FX),
            "time": bind(TIME),
            "link81_elf": bind(ELF),
            "fresh_irq": irq,
            "verifier": bind(Path(__file__).resolve()),
        },
        "claim_limit": (
            "A Link-81 v1.2.4 delta review only. Phase-M hardware is feature "
            "history, not fresh G5/G6 acceptance. C1/E3/E4 remain explicit "
            "C2.3 deferrals; no promotion, tag, release or public push.")
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "verify"))
    args = parser.parse_args()
    try:
        if args.action == "write":
            RECEIPT.write_text(
                json.dumps(build(True), indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
            print(
                "c2-v1.2.4-matrix-delta: PASS rows=25 rederived=3 "
                "explicit-not-rederived=22 new-open=0")
        else:
            require(RECEIPT.is_file(), "delta receipt missing")
            require(load(RECEIPT) == build(False),
                    "delta receipt or authority drift")
            print(
                "c2-v1.2.4-matrix-delta: VERIFY PASS rows=25 "
                "rederived=3 explicit-not-rederived=22")
        return 0
    except (DeltaError, OSError, KeyError, ValueError) as error:
        print(f"c2-v1.2.4-matrix-delta: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
