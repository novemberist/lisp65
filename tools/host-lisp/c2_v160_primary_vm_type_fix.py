#!/usr/bin/env python3
"""Prove the v1.6 Comfort empty-input-phase fix and its fixture contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import evidence_era as ERA  # noqa: E402


PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
SOURCE = ROOT / "lib/stdlib-read-line.lisp"
SUITE_PATH = ROOT / "tests/bytecode/libs/p0-repl-comfort.json"
ATTRIBUTION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-primary-vm-type-attribution-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-primary-vm-type-fix-receipt.json"
)
AUTHORITY = "43951e04"
FORMAT = "lisp65-c2.3-v1.6-primary-vm-type-fix-v1"
CASE = "comfort-cursor-down-empty-boundary"
FIXED = "(code (if (numberp event) event (if event (cadr event) 0)))"
UNFIXED = "(code (if (numberp event) event (cadr event)))"


class FixError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FixError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def boundary_case(suite: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in suite.get("cases", []) if row.get("name") == CASE]
    require(len(rows) == 1, "empty-boundary fixture absent or duplicated")
    return rows[0]


def fixture_gate(suite: dict[str, Any]) -> dict[str, Any]:
    case = boundary_case(suite)
    events = case.get("key_events")
    require(
        isinstance(events, list)
        and len(events) == 3
        and events[0] == 17
        and events[1] == {"empty_polls": 1}
        and events[2] == 13
        and case.get("expect_key_events_remaining") == 0,
        "claim fixture must contain Cursor-Down, an empty boundary, then Return",
    )
    return {"case": CASE, "physical_sequence": events,
            "preload_only_rejected": True}


def run_boundary(*, mutant: bool) -> dict[str, Any]:
    suite = STD._read_suite(str(SUITE_PATH))
    suite["cases"] = [boundary_case(suite)]
    original_read = STD._read_source
    original_run = B.P0VM.run
    failures: list[dict[str, Any]] = []

    def read_source(path: str) -> str:
        source = original_read(path)
        if mutant and str(path).endswith("lib/stdlib-read-line.lisp"):
            require(source.count(FIXED) == 1, "fixed loop shape drift")
            source = source.replace(FIXED, UNFIXED, 1)
        return source

    def observed_run(vm: B.P0VM, *args: Any, **kwargs: Any) -> Any:
        try:
            return original_run(vm, *args, **kwargs)
        except Exception as error:
            failures.append({"type": type(error).__name__,
                "status": getattr(error, "status", None),
                "message": str(error), "steps": vm.steps})
            raise

    STD._read_source = read_source
    B.P0VM.run = observed_run
    try:
        result = STD.check_suite("v1.6-primary-vm-type-boundary", suite)
    except B.VMError as error:
        require(mutant, f"fixed boundary raised {error}")
        require(len(failures) == 1
                and failures[0]["status"] == "TypeError"
                and failures[0]["steps"] > 0,
                "unfixed semantic failure signature drift")
        return {"status": "RED: UNFIXED LOOP PASSES NIL TO FIXNUM COMPARISON",
                **failures[0]}
    finally:
        STD._read_source = original_read
        B.P0VM.run = original_run
    require(not mutant and result["cases"] == 1,
            "unfixed mutation failed to reproduce")
    observation = result["observations"][0]
    require(observation["result"] == "nil"
            and observation["io_witness"]["key_events_remaining"] == 0,
            "fixed empty-boundary execution drift")
    return {"status": "PASS: EMPTY PHASE WAITS AND CONTINUES",
            "steps": result["steps"], "result": observation["result"],
            "key_events_remaining": 0}


def derive() -> dict[str, Any]:
    attribution = load(ATTRIBUTION)
    require(
        attribution["status"] ==
            "ATTRIBUTED: PRIMARY VM_TYPE; HOLDER READ SPECIFIED NOT EXECUTED"
        and attribution["track_1"]["delivered_artifact_gap_case"]["steps"] == 4196
        and attribution["track_1"]["preloaded_return_control"]["steps"] == 4642,
        "primary-fault attribution drift",
    )
    source = SOURCE.read_text(encoding="utf-8")
    require(source.count(FIXED) == 1 and UNFIXED not in source,
            "empty-phase fix source shape drift")
    suite = STD._read_suite(str(SUITE_PATH))
    fixture = fixture_gate(suite)
    mutant_suite = json.loads(json.dumps(suite))
    boundary_case(mutant_suite)["key_events"] = [17, 13]
    try:
        fixture_gate(mutant_suite)
    except FixError:
        pass
    else:
        raise FixError("preload-only fixture mutation survived")
    unfixed = run_boundary(mutant=True)
    fixed = run_boundary(mutant=False)
    return {
        "format": FORMAT,
        "status": "PASS: PRIMARY VM_TYPE EMPTY-PHASE FIX",
        "authority": ERA.era_bind(AUTHORITY, PLAN.relative_to(ROOT).as_posix()),
        "inputs": {"attribution": bind(ATTRIBUTION), "source": bind(SOURCE),
                   "suite": bind(SUITE_PATH)},
        "regression": {"historical_delivered_steps": 4196,
            "preloaded_control_steps": 4642, "unfixed_mutation": unfixed,
            "fixed_boundary": fixed,
            "candidate_step_counts_derived": True,
            "stored_step_equality_absent": True},
        "fixture_contract": fixture,
        "claim_limit": (
            "Host proof of the primary empty-phase fix only. Final-world walls "
            "belong to the one authorized product card. The Track-2 holder read "
            "was not executed and device acceptance remains closed."
        ),
        "execution": {"WPLTO_runs": 0, "product_links": 0,
                      "media_builds": 0, "device_contacts": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "write"))
    action = parser.parse_args().action
    value = derive()
    if action == "write":
        RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    else:
        require(load(RECEIPT) == value, "primary VM_TYPE fix receipt drift")
    print("v1.6 primary VM_TYPE fix: PASS historical=4196 "
          f"candidate={value['regression']['unfixed_mutation']['steps']}/"
          f"{value['regression']['fixed_boundary']['steps']} boundary=required")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 primary VM_TYPE fix: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
