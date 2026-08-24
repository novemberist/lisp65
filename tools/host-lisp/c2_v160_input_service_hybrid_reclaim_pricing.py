#!/usr/bin/env python3
"""Price one replacement private-inline entry for the v1.6 input hybrid."""

from __future__ import annotations

import argparse
import copy
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
import bytecode_p0_stdlib as P  # noqa: E402
import c2_v160_comfort_repl as COMFORT  # noqa: E402
import evidence_era as ERA  # noqa: E402

CONTRACT = ROOT / "config/c2-v160-input-service-hybrid-reclaim-pricing-contract.json"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
REPORT = ROOT / "docs/planning/v1.6.0-input-service-hybrid-reclaim-pricing-report.md"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-input-service-hybrid-reclaim-pricing-receipt.json"
)
FORMAT = "lisp65-c2-v160-input-service-hybrid-reclaim-pricing-v1"


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def instruction_bytes(operand: str) -> int:
    if operand == "none":
        return 1
    if operand in ("s8", "idx", "rel8", "u8"):
        return 2
    return 3


def emitted_calls(heap: Any, code_by_name: dict[str, Any],
                  configured: set[str]) -> dict[str, list[dict[str, Any]]]:
    calls: dict[str, list[dict[str, Any]]] = {}
    for caller, code in code_by_name.items():
        if caller not in configured:
            continue
        pc = 0
        while pc < len(code.payload):
            spec = B.OPCODES[code.payload[pc]]
            if spec.mnemonic in ("CALL", "TAILCALL"):
                index = code.payload[pc + 1]
                target = heap.cell(code.littab[index]).name
                calls.setdefault(target, []).append({
                    "caller": caller, "opcode": spec.mnemonic, "offset": pc,
                })
            pc += instruction_bytes(spec.operand)
    return calls


def configured_suite(contract: dict[str, Any], *, reclaim: bool) -> dict[str, Any]:
    suite = P._read_suite(str(ROOT / contract["suite"]["path"]))
    existing = list(suite.get("private_inline_functions", []))
    additions = list(COMFORT.RECLAIMS)
    if reclaim:
        additions.append(contract["candidate"]["name"])
    require(not (set(existing) & set(additions)),
            "replacement reclaim was already hidden in the baseline")
    suite["private_inline_functions"] = existing + additions
    suite["min_private_inline_functions"] = len(suite["private_inline_functions"])
    return suite


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    require(contract.get("format") == FORMAT
            and contract.get("status") == "review-released-host-only-pricing"
            and contract.get("authority_commit") == "120758b7",
            "reclaim pricing authority drift")
    candidate = contract["candidate"]
    require(candidate == {
        "name": "%require-c2d-header-layout-p",
        "source": "lib/stdlib-require.lisp",
        "only_caller": "%require-c2d-state",
        "recursive": False,
        "name_bytes_including_nul": 29,
    }, "replacement reclaim identity drift")
    source = (ROOT / candidate["source"]).read_text(encoding="utf-8")
    require(source.count(f"(defun {candidate['name']} ") == 1,
            "replacement reclaim source owner drift")
    capacity = contract["capacity"]
    before = capacity["accepted_device_free_before_hybrid"]
    returned = capacity["returned_rl_put_cost"]
    minimum = capacity["release_minimum"]
    after_return = {key: before[key] - returned[key] for key in before}
    selected = {
        "symbol_slots": after_return["symbol_slots"] + 1,
        "namepool_bytes": (after_return["namepool_bytes"]
                           + candidate["name_bytes_including_nul"]),
    }
    margin = {key: selected[key] - minimum[key] for key in selected}
    require(before == {"symbol_slots": 32, "namepool_bytes": 572}
            and returned == {"symbol_slots": 1, "namepool_bytes": 8}
            and after_return == {"symbol_slots": 31, "namepool_bytes": 564}
            and selected == {"symbol_slots": 32, "namepool_bytes": 593}
            and minimum == {"symbol_slots": 32, "namepool_bytes": 384}
            and margin == {"symbol_slots": 0, "namepool_bytes": 209},
            "bias-adjusted replacement arithmetic drift")
    require(contract["walls"] == {
        "product_cards": 0, "WPLTO_runs": 0, "product_links": 0,
        "media_builds": 0, "device_contacts": 0,
        "owner_fork_untouched": ["one-name-convergence", "MAX_SYM"],
    }, "pricing wall drift")
    return {"after_return": after_return, "selected": selected,
            "minimum": minimum, "margin": margin}


def prove(contract: dict[str, Any]) -> dict[str, Any]:
    baseline = configured_suite(contract, reclaim=False)
    (heap, _names, code, _flags, _resident_flags, _bundle, _directory,
     _cases, _entries, _inliner) = P._compile_suite(baseline)
    candidate = contract["candidate"]
    graph = emitted_calls(heap, code, set(baseline["functions"]))
    sites = graph.get(candidate["name"], [])
    require(sites == [{"caller": candidate["only_caller"],
                       "opcode": "CALL", "offset": 10}],
            f"candidate is not a single non-recursive emitted call: {sites}")

    selected = configured_suite(contract, reclaim=True)
    result = P.check_suite("v1.6-input-hybrid-reclaim-real-suite", selected)
    code = result["code_by_name"]
    require(result["cases"] == contract["suite"]["required_cases"] == 248
            and candidate["name"] not in code
            and candidate["only_caller"] in code,
            "real complete-suite inline proof red")
    return {
        "emitted_call_sites": sites,
        "cases": result["cases"],
        "functions_after": result["functions"],
        "private_inline_functions_after": len(selected["private_inline_functions"]),
        "entry_absent": True,
        "caller_preserved": candidate["only_caller"],
        "caller_code_bytes": len(code[candidate["only_caller"]].payload),
        "code_bytes": result["code_bytes"],
        "directory_bytes": result["directory_bytes"],
    }


def derive() -> dict[str, Any]:
    contract = load(CONTRACT)
    arithmetic = validate_contract(contract)
    authority = ERA.era_bind(contract["authority_commit"],
                             PLAN.relative_to(ROOT).as_posix())
    authority_text = ERA.era_blob(
        contract["authority_commit"], PLAN.relative_to(ROOT).as_posix()
    ).decode("utf-8")
    for token in ("one reclaim pricing round", "real emitted call graph",
                  "owner fork"):
        require(token in authority_text, f"pricing authority token absent: {token}")
    proof = prove(contract)
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-19",
        "status": "PASS: ONE REPLACEMENT PRIVATE ENTRY PRICED AND PROVED",
        "authority": authority,
        "contract": bind(CONTRACT),
        "candidate": contract["candidate"],
        "emitted_graph_and_real_suite": proof,
        "bias_adjusted_capacity": arithmetic,
        "walls": contract["walls"],
        "claim_limit": "host pricing only; implementation card remains closed",
        "next": "review may reopen the unconsumed hybrid implementation card",
    }


def receipt_gate(value: dict[str, Any]) -> None:
    receipt = load(RECEIPT)
    for key in ("format", "status", "candidate",
                "emitted_graph_and_real_suite", "bias_adjusted_capacity",
                "walls", "claim_limit", "next"):
        require(receipt.get(key) == value.get(key),
                f"reclaim pricing receipt drift: {key}")
    candidate_source = ROOT / value["candidate"]["source"]
    expected_inputs = {
        "contract": bind(CONTRACT),
        "candidate_source": bind(candidate_source),
        "suite": bind(ROOT / load(CONTRACT)["suite"]["path"]),
        "checker": bind(Path(__file__)),
        "report": bind(REPORT),
    }
    require(receipt.get("inputs") == expected_inputs,
            "reclaim pricing receipt input closure drift")


def selftest() -> None:
    contract = load(CONTRACT)
    mutations = 0
    for path, value in (
        (("candidate", "only_caller"), "%require-world"),
        (("capacity", "accepted_device_free_before_hybrid", "symbol_slots"), 31),
        (("capacity", "returned_rl_put_cost", "namepool_bytes"), 7),
    ):
        changed = copy.deepcopy(contract)
        cursor: Any = changed
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        try:
            validate_contract(changed)
        except PricingError:
            mutations += 1
        else:
            raise PricingError(f"pricing mutation survived: {path}")
    require(mutations == 3, "pricing mutation count drift")
    print("v1.6 input hybrid reclaim pricing: SELFTEST PASS mutations=3")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        selftest()
    else:
        value = derive()
        receipt_gate(value)
        cap = value["bias_adjusted_capacity"]
        print("v1.6 input hybrid reclaim pricing: CHECK PASS "
              f"cases={value['emitted_graph_and_real_suite']['cases']} "
              f"device={cap['selected']['symbol_slots']}/"
              f"{cap['selected']['namepool_bytes']} "
              f"margin={cap['margin']['symbol_slots']}/"
              f"{cap['margin']['namepool_bytes']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 input hybrid reclaim pricing: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
