#!/usr/bin/env python3
"""Bind the v1.2.2 Link-78 L65E cross-invariant delta review."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v122_dirmiss_renderer_wplto as D1  # noqa: E402


PLAN = ROOT / "docs/planning/v1.2.2-release-plan.md"
MATRIX = ROOT / "docs/planning/c2.2-cross-invariant-matrix.md"
BASELINE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-cross-invariant-full-matrix-link57-review-receipt.json")
TERMINAL = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-cross-invariant-C1-terminal-disposition-link66-receipt.json")
LINK78 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link78-dirmiss-renderer-structural-receipt.json")
HARDWARE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link78-d1-d2-bundled-hardware-receipt.json")
WPLTO = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.2-dirmiss-renderer-wplto-receipt.json")
ATTRIBUTION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.1-dirmiss-renderer-attribution-receipt.json")
E5 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-matrix-e5-cold-front-terminal-noreturn-detail-seam-"
    "fixture-receipt.json")
SOURCE = ROOT / "src/l65e_bcode_ordinal.s"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.2-link78-cross-invariant-delta-receipt.json")

ORDER = (
    "A1", "A2", "A3", "A4",
    "B1", "B2", "B3", "B4", "B5",
    "C1", "C2", "C3", "C4", "C5",
    "D1", "D2", "D3",
    "E1", "E2", "E3", "E4", "E5",
    "F1", "F2", "F3",
)
REDERIVED = frozenset(("E5",))
TERMINAL_STATUS = {
    "A1": "PROVEN", "A2": "PROVEN", "A3": "EXCLUDED",
    "A4": "EXCLUDED", "B1": "PROVEN", "B2": "PROVEN",
    "B3": "PROVEN", "B4": "PROVEN", "B5": "PROVEN",
    "C1": "DOCUMENTED-C2.3-DEFERRED", "C2": "PROVEN",
    "C3": "PROVEN", "C4": "PROVEN", "C5": "EXCLUDED",
    "D1": "PROVEN", "D2": "PROVEN", "D3": "PROVEN",
    "E1": "EXCLUDED", "E2": "EXCLUDED",
    "E3": "DOCUMENTED-C2.3-DEFERRED",
    "E4": "DOCUMENTED-C2.3-DEFERRED", "E5": "PROVEN",
    "F1": "PROVEN", "F2": "PROVEN", "F3": "PROVEN",
}


class DeltaError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DeltaError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing file: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def validate_authorities() -> dict[str, Any]:
    baseline = load(BASELINE)
    terminal = load(TERMINAL)
    link78 = load(LINK78)
    hardware = load(HARDWARE)
    wplto = load(WPLTO)
    attribution = load(ATTRIBUTION)
    e5 = load(E5)
    require(
        tuple(row.get("id") for row in baseline.get("rows", [])) == ORDER,
        "canonical 25-row matrix inventory drift")
    require(
        terminal.get("gate_transition", {}).get("matrix_gate") == "FALLS"
        and terminal.get("other_open_rows", {}).get(
            "explicit_C2_3_deferrals") == ["C1", "E3", "E4"],
        "terminal C2.2 matrix disposition drift")
    require(
        link78.get("status") == "passed-Link78-D1-renderer-hardware-not-run"
        and link78.get("gates", {}).get("all_green") is True
        and wplto.get("status")
        == "passed-D1-full-name-renderer-one-product-shaped-WPLTO",
        "Link-78 D1 structural authority drift")
    rows = {row.get("id"): row for row in hardware.get("passed_rows", [])}
    require(
        rows.get("dirmiss-full-name", {}).get("outcome")
        == "*** undefined function: intern-renderer-missing"
        and rows.get("post-dirmiss-repl", {}).get("outcome") == "9",
        "Link-78 D1 hardware history drift")
    require(
        attribution.get("status")
        == "passed-renderer-pointer-abi-overwrite-attributed"
        and e5.get("status")
        == "passed-product-shaped-host-awaiting-real-eval-hardware"
        and e5.get("row") == "E5"
        and e5.get("renderer", {}).get("status")
        == "passed-host-and-MOS-renderer",
        "L65E attribution/E5 terminal authority drift")
    return {
        "baseline": baseline,
        "terminal": terminal,
        "link78": link78,
        "hardware": hardware,
        "wplto": wplto,
        "attribution": attribution,
        "e5": e5,
    }


def fresh_d1() -> dict[str, Any]:
    attribution = load(ATTRIBUTION)
    require(
        attribution.get("status")
        == "passed-renderer-pointer-abi-overwrite-attributed"
        and attribution.get("disposition", {}).get("convicted_fix")
        == "delete sta __rc2 / stx __rc3 after jsr symname"
        and attribution.get("evidence", {}).get("symname_return_abi")
        == "__rc2/__rc3",
        "DIRMISS attribution authority drift",
    )
    source = SOURCE.read_text(encoding="ascii")
    D1.L65E.renderer_source_contract(source)
    mutations = D1.L65E.renderer_source_mutations(source)
    output = D1.run(
        [sys.executable, str(D1.SMOKE)],
        "v1.2.2 matrix fresh DIRMISS fixture",
    )
    marker = (
        "error-overlay smoke: ok "
        "(cases=20 full-symbol=intern-renderer-missing "
        "target-mutations=5 "
    )
    value = {
        "status": "passed-full-name-and-target-pointer-consumption",
        "rendered_exactly":
            "undefined function: intern-renderer-missing",
        "host_cases_executed": 20,
        "target_mutations_rejected": mutations,
        "output": output.strip().splitlines(),
    }
    require(
        value.get("status")
        == "passed-full-name-and-target-pointer-consumption"
        and value.get("rendered_exactly")
        == "undefined function: intern-renderer-missing"
        and value.get("host_cases_executed") == 20
        and len(value.get("target_mutations_rejected", [])) == 5,
        "fresh DIRMISS gate lacks exact execution/mutation witness")
    require(
        marker in output
        and
        ".Lemit_depth:" in source and ".Lemit_symbol:" in source
        and source.index(".Lemit_depth:") < source.index(".Lemit_symbol:")
        and "jsr\tsymname" in source,
        "L65E depth/symbol branch inventory drift")
    return value


def build_receipt(run_fresh: bool) -> dict[str, Any]:
    authorities = validate_authorities()
    d1 = fresh_d1() if run_fresh else {
        "status": "passed-full-name-and-target-pointer-consumption",
        "rendered_exactly": "undefined function: intern-renderer-missing",
        "host_cases_executed": 20,
        "target_mutations_rejected": [
            "restore-incidental-A-store",
            "restore-incidental-X-store",
            "nonzero-Z-before-name-read",
            "wrong-name-pointer-byte",
            "symname-call-removed",
        ],
    }
    baseline_rows = {row["id"]: row for row in authorities["baseline"]["rows"]}
    rows: list[dict[str, Any]] = []
    for row_id in ORDER:
        baseline = baseline_rows[row_id]
        if row_id == "E5":
            rows.append({
                "id": row_id,
                "crossing": baseline["crossing"],
                "review": "re-derived-against-Link78-L65E-delta",
                "status": "PROVEN",
                "baseline_Link57_status": baseline["status"],
                "terminal_C2_2_status": "PROVEN",
                "delta_surface":
                    "L65E consumer pointer fix x bounded-depth error",
                "finding": (
                    "The Link-78 change is confined to the symbol-detail "
                    "branch after jsr symname. The depth-five code-63/fixnum-5 "
                    "branch remains separate and the fresh 20-case renderer "
                    "suite executes it while all five pointer-consumption "
                    "mutations are rejected."),
                "proof_boundary": (
                    "Fresh host/object proof plus Link-78 exact DIRMISS "
                    "hardware history. This re-derives E5's renderer crossing; "
                    "it does not present the other 24 rows as fresh proof."),
                "fresh_facts": {
                    "renderer_cases": d1["host_cases_executed"],
                    "pointer_mutations_rejected":
                        len(d1["target_mutations_rejected"]),
                    "exact_symbol_output": d1["rendered_exactly"],
                    "depth_and_symbol_branches": "distinct",
                },
                "authorities": [
                    "E5_terminal", "D1_fresh", "Link78", "hardware_history",
                ],
            })
        else:
            row = {
                "id": row_id,
                "crossing": baseline["crossing"],
                "review": "not-rederived-Link78-L65E-delta-disjoint",
                "status": TERMINAL_STATUS[row_id],
                "baseline_Link57_status": baseline["status"],
                "terminal_C2_2_status": TERMINAL_STATUS[row_id],
                "reason": (
                    "The Link-78 delta removes two incidental register-to-"
                    "pointer stores only in the cold L65E symbol-detail "
                    "consumer. No source, state, control, storage, ownership "
                    "or publication edge from that delta reaches this row. "
                    "Its terminal C2.2 disposition is retained and explicitly "
                    "not presented as fresh Link-78 proof."),
                "authorities": ["baseline", "terminal"],
            }
            if row_id in ("C1", "E3", "E4"):
                row["deferred_scope"] = "C2.3-explicit-unchanged"
            rows.append(row)

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    require(
        counts == {
            "PROVEN": 17,
            "EXCLUDED": 5,
            "DOCUMENTED-C2.3-DEFERRED": 3,
        }
        and sum(row["review"].startswith("re-derived") for row in rows) == 1
        and sum(row["review"].startswith("not-rederived")
                for row in rows) == 24,
        "delta review coverage/disposition drift")

    return {
        "format": "lisp65-v1.2.2-link78-cross-invariant-delta-v1",
        "version": 1,
        "recorded_on": "2026-07-29",
        "status": "passed-Link78-L65E-delta-review-no-new-open-row",
        "candidate": "Link 78",
        "method": {
            "baseline_rows": 25,
            "rederived_rows": ["E5"],
            "rederived_count": 1,
            "explicit_not_rederived_count": 24,
            "no_silent_inheritance": True,
            "rule": (
                "Only the L65E/error-rendering crossing reachable from the "
                "Link-78 delta is re-derived. Every other row retains an "
                "explicit not-rederived marker and its terminal disposition."),
        },
        "summary": {
            "PROVEN": counts["PROVEN"],
            "EXCLUDED": counts["EXCLUDED"],
            "DOCUMENTED_C2_3_DEFERRED":
                counts["DOCUMENTED-C2.3-DEFERRED"],
            "new_OPEN_rows": 0,
            "matrix_gate": "remains-fallen-for-C2.2",
            "acceptance_chain": "A2-green-A3-requires-fresh-chain",
        },
        "fresh_execution_witness": {
            "renderer_cases": d1["host_cases_executed"],
            "pointer_mutations_rejected":
                len(d1["target_mutations_rejected"]),
            "rendered_exactly": d1["rendered_exactly"],
        },
        "rows": rows,
        "bindings": {
            "plan": bind(PLAN),
            "matrix": bind(MATRIX),
            "baseline": bind(BASELINE),
            "terminal": bind(TERMINAL),
            "link78": bind(LINK78),
            "hardware_history": bind(HARDWARE),
            "wplto": bind(WPLTO),
            "attribution": bind(ATTRIBUTION),
            "E5_terminal": bind(E5),
            "source": bind(SOURCE),
            "verifier": bind(Path(__file__).resolve()),
        },
        "claim_limit": (
            "A Link-78 L65E delta review only. It is not a fresh full-matrix "
            "derivation, R4/R5/R6/G5/G6 result, promotion, release, tag or "
            "public push. C1/E3/E4 remain explicit C2.3 deferrals."),
    }


def write_receipt() -> None:
    value = build_receipt(run_fresh=True)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-v1.2.2-matrix-delta: PASS rows=25 rederived=1 "
        "explicit-not-rederived=24 new-open=0 deferred-C2.3=3")


def verify_receipt() -> None:
    require(RECEIPT.is_file(), "delta receipt absent")
    require(load(RECEIPT) == build_receipt(run_fresh=False),
            "delta receipt or authority drift")
    print(
        "c2-v1.2.2-matrix-delta: VERIFY PASS "
        "rows=25 rederived=1 explicit-not-rederived=24")


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
    except (DeltaError, D1.DirmissProbeError, OSError, KeyError, TypeError,
            ValueError, json.JSONDecodeError) as error:
        print(f"c2-v1.2.2-matrix-delta: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
