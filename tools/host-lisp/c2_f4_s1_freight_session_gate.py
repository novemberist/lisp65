#!/usr/bin/env python3
"""Prepare and permanently gate the one-session F1/F2 S1 hardware plan."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import bytecode_p0_compiler as C  # noqa: E402
import c2_bitops_gate as F2  # noqa: E402
import c2_top_level_published_value_call_gate as F1  # noqa: E402


CONTRACT = ROOT / "config/c2.2-s1-freight-session.json"
NOTE = ROOT / "docs/planning/c2.2-f4-s1-freight-session.md"
PUBLIC = ROOT / "lib/dialect-v2/eval-runtime.lisp"
F3_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-f3-state-error-first-red-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-f4-s1-freight-session-preparation-receipt.json")
ROW_IDS = (
    "boot-watch",
    "f1-define-fixed",
    "f1-nary-cold",
    "f1-nary-warm",
    "nullary-define-regression",
    "nullary-cold-regression",
    "nullary-warm-regression",
    "f2-bitops-positive",
    "f2-bitops-type-negative",
    "post-error-repl",
    "idle-freezer-roundtrip",
    "post-freezer-repl",
)


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def validate(contract: dict[str, Any]) -> dict[str, Any]:
    rows = contract["rows"]
    by_id = {row["id"]: row for row in rows}
    require(
        contract["format"] == "lisp65-c2.2-s1-freight-session-contract-v1"
        and contract["status"]
            == "link67-bound-attempt2-owner-authorized-hardware-not-run"
        and contract["session_policy"]["hardware_attempts_so_far"] == 1
        and contract["session_policy"]["accepted_product_rows_so_far"] == 0
        and contract["session_policy"]["attempt_2_authorized"] is True
        and contract["candidate"]["link"] == 67
        and contract["candidate"]["product_sha256"]
            == "1b6fb1a524a71a63489848531b30e1d399b871ed5b863c93be7232f3362e44f3"
        and contract["candidate"]["elf_sha256"]
            == "25e563ba41283fb1ce21624a84f618b2337f889510dee19261509dc29e465f32"
        and tuple(row["id"] for row in rows) == ROW_IDS
        and len(by_id) == len(rows)
        and contract["clock"]["frame_register"] == "$d7fa"
        and contract["session_policy"]["hardware_sessions"] == 1
        and contract["session_policy"]["no_inherited_green"] is True,
        "S1 identity/order/session policy drift",
    )
    require(
        by_id["f1-nary-cold"]["limit_frames"] == 16
        and by_id["f1-nary-warm"]["limit_frames"] == 10
        and by_id["nullary-cold-regression"]["limit_frames"] == 16
        and by_id["nullary-warm-regression"]["limit_frames"] == 10
        and by_id["boot-watch"]["limit_frames"] == 1500
        and by_id["f1-nary-cold"]["expected_result"] == "(7 . 8)"
        and by_id["f1-nary-warm"]["expected_result"] == "(7 . 8)"
        and by_id["f2-bitops-positive"]["expected_result"]
            == "(42 -43 -44 -42 16382)"
        and by_id["f2-bitops-type-negative"]["expected_status"]
            == "type error"
        and by_id["post-error-repl"]["expected_result"] == "3"
        and by_id["idle-freezer-roundtrip"]["operator_action"].endswith("F3")
        and by_id["post-freezer-repl"]["expected_result"] == "9",
        "S1 limits/results/Freezer procedure drift",
    )
    parsed = []
    for row in rows:
        form = row.get("form")
        if form is not None:
            C.parse_one(form)
            parsed.append(row["id"])
        require(row.get("first_red") is True,
                f"S1 row is not First Red: {row['id']}")
    require(len(parsed) == 11, "S1 executable form count drift")

    public = PUBLIC.read_text(encoding="utf-8")
    for forbidden in (
        "(defun gc ()", "(defun room ()", "(defun error (message)",
        "(%buffer-read 4 nil)", "(%buffer-read 5 nil)",
        "(%buffer-read 6 message)",
    ):
        require(forbidden not in public,
                f"parked F3 surface leaked into S1: {forbidden}")
    f3 = load(F3_FIRST_RED)
    require(
        contract["f3_disposition"]["status"] == "parked-not-in-S1-product"
        and f3["status"] == "parked-at-hard-cold-slice-cap-before-product-link"
        and f3["capacity_attribution"]["section_bytes"] == 2552
        and f3["capacity_attribution"]["hard_cap_bytes"] == 1792,
        "S1 F3 parked disposition drift",
    )
    return {
        "status": "passed-one-session-row-contract-and-F3-exclusion",
        "row_count": len(rows),
        "parsed_form_count": len(parsed),
        "first_red_rows": len(rows),
        "claim_rows": [
            row["id"] for row in rows if row["class"] == "claim"],
        "regression_rows": [
            row["id"] for row in rows if row["class"] == "regression"],
        "F3": "parked-not-loaded",
    }


def mutation_tests(contract: dict[str, Any]) -> int:
    rejected = 0

    def reject(change: Any) -> None:
        nonlocal rejected
        candidate = copy.deepcopy(contract)
        change(candidate)
        try:
            validate(candidate)
        except (GateError, C.CompileError):
            rejected += 1
        else:
            raise GateError("S1 mutation survived")

    reject(lambda c: c["rows"][2].update(limit_frames=17))
    reject(lambda c: c["rows"][3].update(limit_frames=11))
    reject(lambda c: c["rows"][7].update(
        expected_result="(42 -43 -43 -42 16382)"))
    reject(lambda c: c["rows"][10].update(operator_action="return with F"))
    reject(lambda c: c["rows"][9].update(expected_result="4"))
    reject(lambda c: c["rows"][0].update(first_red=False))
    reject(lambda c: c["session_policy"].update(hardware_sessions=2))
    reject(lambda c: c["session_policy"].update(no_inherited_green=False))
    reject(lambda c: c["f3_disposition"].update(status="loaded"))
    reject(lambda c: c["rows"].__setitem__(2, c["rows"][3]))
    return rejected


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def main() -> int:
    try:
        contract = load(CONTRACT)
        source = validate(contract)
        source["mutations_rejected"] = mutation_tests(contract)
        f1_bundle = F1.bundle()
        f1 = F1.validate_source(f1_bundle)
        f1["mutations_rejected"] = F1.mutation_tests(f1_bundle)
        f1_execution = F1.executable_fixtures()
        f2_bundle = F2.bundle()
        f2 = F2.validate(f2_bundle)
        f2["mutations_rejected"] = F2.mutation_tests(f2_bundle)
        f2_execution = F2.executable_fixtures()
        receipt = {
            "format": "lisp65-c2.2-f4-s1-preparation-receipt-v1",
            "recorded_on": "2026-07-27",
            "status":
                "passed-S1-attempt2-authorized-Link67-bound-hardware-not-run",
            "promotable": False,
            "hardware_runs": 0,
            "product_links": 0,
            "session_gate": source,
            "F1": {
                "source": f1,
                "execution": f1_execution,
            },
            "F2": {
                "source": f2,
                "execution": f2_execution,
            },
            "F3": {
                "status": "parked-not-in-S1",
                "first_red": bind(F3_FIRST_RED),
            },
            "next_binding": (
                "Product and ELF remain bound to Link 67. Attempt 1 is a "
                "harness First Red with zero accepted product rows. "
                "Attempt 2 is explicitly authorized for autonomous execution."
            ),
            "authority": {
                "contract": bind(CONTRACT),
                "note": bind(NOTE),
                "F1_contract": bind(F1.CONTRACT),
                "F2_contract": bind(F2.CONTRACT),
                "gate": bind(Path(__file__)),
            },
            "claim_limit": (
                "Host preparation and executable semantic fixtures only. "
                "No product link, hardware timing, hardware result, "
                "acceptance or promotion is claimed."
            ),
        }
        atomic_json(RECEIPT, receipt)
        print(
            "c2-f4-s1-freight-session-gate: PASS "
            f"rows={source['row_count']} "
            f"mutations={source['mutations_rejected']} "
            f"F1={f1_execution['fixture_count']} "
            f"F2={f2_execution['positive_count']}/"
            f"{f2_execution['negative_count']} hardware=not-run"
        )
    except (OSError, ValueError, KeyError, GateError, C.CompileError,
            F1.GateError, F2.GateError) as exc:
        print(f"c2-f4-s1-freight-session-gate: FAIL: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
