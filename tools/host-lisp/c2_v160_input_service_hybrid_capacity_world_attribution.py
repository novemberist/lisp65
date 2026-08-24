#!/usr/bin/env python3
"""Attribute the hybrid symbol price against the actual Comfort predecessor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0_stdlib as P  # noqa: E402
import c2_v160_comfort_repl as COMFORT  # noqa: E402

SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json"
COMFORT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-comfort-repl-host-first-receipt.json"
)
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-input-service-hybrid-precard-first-red.json"
)
REPORT = ROOT / "docs/planning/v1.6.0-input-service-hybrid-capacity-world-attribution.md"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-input-service-hybrid-capacity-world-attribution-receipt.json"
)
CANDIDATE = "%require-c2d-header-layout-p"
EXPECTED_RECLAIMS = [
    "%take", "%case-fold-list", "%fasl-len", "%subseq-list", "%append2",
]


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def identity(path: Path) -> dict[str, Any]:
    import hashlib
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def compile_world(*, extra_reclaim: bool) -> dict[str, Any]:
    suite = P._read_suite(str(SUITE))
    standing = list(suite.get("private_inline_functions", []))
    require(COMFORT.RECLAIMS == EXPECTED_RECLAIMS
            and "%rl-put" not in standing + COMFORT.RECLAIMS,
            "actual Comfort reclaim inventory drift")
    suite["private_inline_functions"] = standing + list(COMFORT.RECLAIMS)
    if extra_reclaim:
        suite["private_inline_functions"].append(CANDIDATE)
    suite["min_private_inline_functions"] = len(
        suite["private_inline_functions"])
    result = P.check_suite(
        "v1.6-hybrid-capacity-world-attribution", suite)
    code = result["code_by_name"]
    require(result["cases"] == 248 and "%rl-put" in code,
            "actual emitted predecessor does not contain materialized %rl-put")
    require((CANDIDATE not in code) is extra_reclaim,
            "replacement candidate emission state drift")
    return {
        "cases": result["cases"],
        "functions_after": result["functions"],
        "private_inline_functions": suite["private_inline_functions"],
        "rl_put_entry_present": True,
        "candidate_entry_present": CANDIDATE in code,
    }


def derive() -> dict[str, Any]:
    receipt = load(COMFORT_RECEIPT)
    red = load(FIRST_RED)
    accepted = receipt["symbol_budget"]["bias_adjusted_free"]
    minimum = {"symbol_slots": 32, "namepool_bytes": 384}
    baseline = compile_world(extra_reclaim=False)
    selected = compile_world(extra_reclaim=True)
    with_candidate = {
        "symbol_slots": accepted["symbol_slots"] + 1,
        "namepool_bytes": accepted["namepool_bytes"] + len(CANDIDATE) + 1,
    }
    require(accepted == {"symbol_slots": 32, "namepool_bytes": 572}
            and baseline["functions_after"] == 388
            and selected["functions_after"] == 387
            and with_candidate == {"symbol_slots": 33, "namepool_bytes": 601}
            and red["capacity_first_red"]["restored_private_entries"] ==
                ["%rl-put"],
            "capacity-world arithmetic evidence drift")
    return {
        "format": "lisp65-c2-v160-input-service-hybrid-capacity-world-attribution-v1",
        "recorded_on": "2026-08-19",
        "status": "ATTRIBUTED: ACCEPTED COMFORT WORLD ALREADY MATERIALIZES RL-PUT",
        "classification": {
            "class": "stored-predecessor-pricing-consumed-as-live-capacity",
            "mechanism": (
                "the historical three-helper pricing gate named %rl-put; the "
                "accepted Comfort successor replaced that plan with five other reclaims"
            ),
            "card_invoked": False,
        },
        "actual_predecessor": baseline,
        "proven_optional_reclaim": selected,
        "capacity": {
            "without_optional_reclaim": accepted,
            "without_optional_reclaim_margin": {
                "symbol_slots": accepted["symbol_slots"] - minimum["symbol_slots"],
                "namepool_bytes": accepted["namepool_bytes"] - minimum["namepool_bytes"],
            },
            "with_optional_reclaim": with_candidate,
            "with_optional_reclaim_margin": {
                "symbol_slots": with_candidate["symbol_slots"] - minimum["symbol_slots"],
                "namepool_bytes": with_candidate["namepool_bytes"] - minimum["namepool_bytes"],
            },
            "release_minimum": minimum,
        },
        "decision": {
            "successors_authorized": 0,
            "review_required": True,
            "branches": [
                "hybrid at accepted 32/572 floor without an additional reclaim",
                "hybrid plus proved additional reclaim at 33/601",
            ],
        },
        "attempt_accounting": {
            "cards_consumed": 0, "WPLTO_runs": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0,
        },
    }


def selftest() -> None:
    value = derive()
    require(value["actual_predecessor"]["rl_put_entry_present"] is True
            and value["proven_optional_reclaim"]["candidate_entry_present"] is False
            and value["capacity"]["with_optional_reclaim_margin"] == {
                "symbol_slots": 1, "namepool_bytes": 217},
            "capacity-world attribution selftest drift")
    print("v1.6 hybrid capacity-world attribution: SELFTEST PASS worlds=2")


def receipt_gate(value: dict[str, Any]) -> None:
    receipt = load(RECEIPT)
    for key in ("format", "status", "classification", "actual_predecessor",
                "proven_optional_reclaim", "capacity", "decision",
                "attempt_accounting"):
        require(receipt.get(key) == value.get(key),
                f"capacity-world receipt drift: {key}")
    require(receipt.get("inputs") == {
        "checker": identity(Path(__file__)),
        "report": identity(REPORT),
        "accepted_comfort_receipt": identity(COMFORT_RECEIPT),
        "precard_first_red": identity(FIRST_RED),
    }, "capacity-world receipt input closure drift")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "selftest"))
    args = parser.parse_args()
    value = derive()
    if args.action == "selftest":
        selftest()
    else:
        receipt_gate(value)
        print("v1.6 hybrid capacity-world attribution: CHECK PASS "
              f"baseline={value['capacity']['without_optional_reclaim']['symbol_slots']}/"
              f"{value['capacity']['without_optional_reclaim']['namepool_bytes']} "
              f"candidate={value['capacity']['with_optional_reclaim']['symbol_slots']}/"
              f"{value['capacity']['with_optional_reclaim']['namepool_bytes']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 hybrid capacity-world attribution: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
