#!/usr/bin/env python3
"""Gate the non-promotable C1 open-transaction Freezer carrier."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT / "src/c2_c1_freezer_fixture.h"
RUNTIME = ROOT / "src/c2_product_runtime.c"
CONTRACT = ROOT / "config/c2-c1-freezer-cutpoint-contract.json"
PROFILE = ROOT / "config/c2-lite-v6-roots-fronts-product-profile.json"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def function_body(source: str, name: str) -> str:
    begin = source.find(name + "(")
    require(begin >= 0, f"C1 function absent: {name}")
    brace = source.find("{", begin)
    require(brace >= 0, f"C1 function body absent: {name}")
    depth = 0
    for end in range(brace, len(source)):
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
            if depth == 0:
                return source[begin:end + 1]
    raise GateError(f"unterminated C1 function: {name}")


def source_model(header: str, runtime: str,
                 profile: dict[str, Any]) -> dict[str, Any]:
    memory_driven_hold = (
        '"sta $17e1\\n\\t" \\\n'
        '        "1:\\n\\t" \\\n'
        '        "lda $17e0\\n\\t" \\\n'
        '        "cmp #" #id "\\n\\t" \\\n'
        '        "beq 1b\\n\\t"')
    memory_driven_state_hold = (
        '#define C2_C1_FREEZER_HOLD_STATE_PROVEN(id) do { \\\n'
        '    __asm__ volatile( \\\n'
        '        "1:\\n\\t" \\\n'
        '        "lda $17e0\\n\\t" \\\n'
        '        "cmp #" #id "\\n\\t" \\\n'
        '        "beq 1b\\n\\t"')
    for token in (
            "#define LISP65_C2_C1_FREEZER_COMMAND_ADDRESS 0x17e0u",
            "#define LISP65_C2_C1_FREEZER_REACHED_ADDRESS 0x17e1u",
            "#ifdef LISP65_C2_C1_FREEZER_CUTPOINT_FIXTURE",
            '"lda $17e0\\n\\t"',
            '"sta $17e1\\n\\t"',
            "#define C2_C1_FREEZER_ABORT_REQUESTED()"):
        require(token in header, f"C1 carrier token drift: {token}")
    require(memory_driven_hold in header,
            "ordinary C1 hold does not reload command memory per iteration")
    require(memory_driven_state_hold in header,
            "state-proven C1 hold does not reload command memory per iteration")
    require('"cmp $17e0\\n\\t"' not in header,
            "C1 hold carries its comparison operand in a CPU register")
    require(
        "No CPU register\n * is assumed to survive an IRQ or Freezer "
        "roundtrip." in header,
        "C1 memory-driven hold invariant is not documented")
    require(header.count("C2_C1_FREEZER_HOLD(id)") == 2,
            "C1 hold macro does not have exact diagnostic/no-op forms")
    require(header.count("C2_C1_FREEZER_HOLD_STATE_PROVEN(id)") == 2,
            "C1 state-proven hold lacks exact diagnostic/no-op forms")
    require(
        "LISP65_C2_C1_FREEZER_CUTPOINT_FIXTURE"
        not in json.dumps(profile, sort_keys=True),
        "C1 diagnostic feature leaked into the product profile")

    header_phase = function_body(runtime, "c2_append_header_phase")
    exports = function_body(runtime, "c2_append_publish_exports_phase")
    unpublish = function_body(runtime, "c2_append_rollback_unpublish_phase")
    bodies = {
        1: header_phase,
        2: header_phase,
        3: exports,
    }
    for cutpoint, body in bodies.items():
        require(body.count(f"C2_C1_FREEZER_HOLD({cutpoint});") == 1,
                f"C1 cutpoint {cutpoint} absent or duplicated")
    require(runtime.count("C2_C1_FREEZER_HOLD(") == 3
            and runtime.count("C2_C1_FREEZER_HOLD_STATE_PROVEN(4)") == 1,
            "C1 carrier gained an uncontracted hold")

    require(
        header_phase.index(
            "if (mode == C2_COMPLETION_ACTIVE_MARK)")
        < header_phase.index(
            "|| !c2_completion_poll(w, mode, 0))")
        < header_phase.index(
            "C2AW_JOURNAL_RESULT(w) = C2J_RESULT_ACTIVE;")
        < header_phase.index("C2_C1_FREEZER_HOLD(1);")
        < header_phase.index("return C2_STREAM_OK;"),
        "journal-written hold moved outside the converged ACTIVE bookend")
    require(
        header_phase.index(
            "if (mode != C2_COMPLETION_PUBLISH_MARK")
        < header_phase.index(
            "|| !w->append.finished)")
        < header_phase.index("C2_C1_FREEZER_HOLD(2);")
        < header_phase.index("for (i = 0; i < sizeof w->new_header;"),
        "staged-before-header hold moved across header construction")
    require(
        exports.index("if (!w || !w->committed || C2AW_PLAN_MARK(w))")
        < exports.index("C2_C1_FREEZER_HOLD(3);")
        < exports.index("count = c2_u16(w->meta + 22);"),
        "header-before-exports hold moved across export consumption")
    require(
        exports.index("set_sym_function(symbol, published);")
        < exports.index("C2_C1_FREEZER_ABORT_REQUESTED()")
        < exports.rindex("return C2_STREAM_OK;"),
        "abort injection no longer follows completed export publication")
    require(
        unpublish.index(
            "if (!c2_stream_c2d_write(\n"
            "            0u, w->old_header, sizeof w->old_header))")
        < unpublish.index("C2_C1_FREEZER_HOLD_STATE_PROVEN(4);")
        < unpublish.rindex("return C2_STREAM_OK;"),
        "abort-unpublish hold moved before old-header republication")

    return {
        "status": "passed-four-cold-overlay-holds-and-post-export-abort",
        "feature": "LISP65_C2_C1_FREEZER_CUTPOINT_FIXTURE",
        "addresses": {"command": "0x17e0", "reached": "0x17e1"},
        "cutpoints": {
            "1": "journal-written",
            "2": "staged-before-header",
            "3": "header-before-exports",
            "4": "abort-unpublish",
        },
        "product_profile_contains_feature": False,
        "hold_carrier": (
            "command memory is reloaded on every loop iteration; "
            "no register survives the Freezer boundary by assumption"),
        "resident_cells": 0,
        "product_bytes": 0,
    }


def mutations(header: str, runtime: str,
              profile: dict[str, Any]) -> dict[str, str]:
    trials: dict[str, tuple[str, str, dict[str, Any]]] = {
        "wrong-command-address": (
            header.replace("$17e0", "$17df"), runtime, profile),
        "wrong-reached-address": (
            header.replace("$17e1", "$17e2"), runtime, profile),
        "ordinary-hold-carries-id-in-register": (
            header.replace(
                '        "lda $17e0\\n\\t" \\\n'
                '        "cmp #" #id "\\n\\t" \\\n'
                '        "beq 1b\\n\\t"',
                '        "cmp $17e0\\n\\t" \\\n'
                '        "beq 1b\\n\\t"',
                1),
            runtime, profile),
        "state-hold-carries-id-in-register": (
            header.replace(
                '        "1:\\n\\t" \\\n'
                '        "lda $17e0\\n\\t" \\\n'
                '        "cmp #" #id "\\n\\t" \\\n'
                '        "beq 1b\\n\\t"',
                '        "lda $17e0\\n\\t" \\\n'
                '        "cmp #" #id "\\n\\t" \\\n'
                '        "bne 2f\\n\\t" \\\n'
                '        "1:\\n\\t" \\\n'
                '        "cmp $17e0\\n\\t" \\\n'
                '        "beq 1b\\n\\t" \\\n'
                '        "2:\\n\\t"',
                1),
            runtime, profile),
        "cutpoint-1-missing": (
            header, runtime.replace("C2_C1_FREEZER_HOLD(1);", "", 1),
            profile),
        "cutpoint-2-wrong-id": (
            header, runtime.replace(
                "C2_C1_FREEZER_HOLD(2);",
                "C2_C1_FREEZER_HOLD(3);", 1), profile),
        "cutpoint-3-missing": (
            header, runtime.replace("C2_C1_FREEZER_HOLD(3);", "", 1),
            profile),
        "cutpoint-4-before-header-restore": (
            header, runtime.replace(
                "if (!c2_stream_c2d_write(\n"
                "            0u, w->old_header, sizeof w->old_header))\n"
                "        return C2_STREAM_ERR_IO;\n    "
                "C2_C1_FREEZER_HOLD_STATE_PROVEN(4);",
                "C2_C1_FREEZER_HOLD_STATE_PROVEN(4);\n    "
                "if (!c2_stream_c2d_write(\n"
                "            0u, w->old_header, sizeof w->old_header))\n"
                "        return C2_STREAM_ERR_IO;", 1), profile),
        "abort-injection-missing": (
            header, runtime.replace(
                "if (C2_C1_FREEZER_ABORT_REQUESTED()) "
                "return C2_STREAM_ERR_STATE;", "", 1), profile),
    }
    feature_profile = deepcopy(profile)
    feature_profile["diagnostic_feature"] = (
        "LISP65_C2_C1_FREEZER_CUTPOINT_FIXTURE")
    trials["feature-leaked-into-product-profile"] = (
        header, runtime, feature_profile)
    rejected: dict[str, str] = {}
    for label, (trial_header, trial_runtime, trial_profile) in trials.items():
        try:
            source_model(trial_header, trial_runtime, trial_profile)
        except (GateError, ValueError):
            rejected[label] = "rejected"
        else:
            raise GateError(f"C1 mutation survived: {label}")
    return rejected


def gate() -> dict[str, Any]:
    header = HEADER.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    require(
        contract["format"] ==
            "lisp65-c2.2-c1-freezer-cutpoint-contract-v2"
        and contract["matrix_row"] == "C1"
        and contract["product_authority"]["sha256"] ==
            "4bab8371aa54060bef4ab9493e12dd6afd230baeb83a11f07daccdaa05000e6f"
        and contract["link60_successor_authority"]["sha256"] ==
            "7fc3bb84acf6039ea34ff863ba4f6d39458400a7848ae7077a8085ccd9cf2416"
        and len(contract["cutpoints"]) == 4,
        "C1 fixture contract authority drift")
    return {
        "format": "lisp65-c2.2-c1-freezer-cutpoint-source-gate-v2",
        "source": source_model(header, runtime, profile),
        "mutations_rejected": mutations(header, runtime, profile),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = gate()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
    print(
        "c2-c1-freezer-cutpoint-gate: PASS "
        f"cutpoints=4 mutations={len(result['mutations_rejected'])} "
        "product-bytes=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-c1-freezer-cutpoint-gate: FIRST RED: " + str(error))
        raise SystemExit(2)
