#!/usr/bin/env python3
"""Gate the passive Slot-39 witness used by the bundled C1 appointment."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT / "src/c2_c1_freezer_fixture.h"
RUNTIME = ROOT / "src/c2_product_runtime.c"
PROFILE = ROOT / "config/c2-l-full-product-profile.json"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def function_body(source: str, name: str) -> str:
    anchor = source.index(name)
    begin = source.index("{", anchor)
    depth = 0
    for end in range(begin, len(source)):
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
            if depth == 0:
                return source[anchor:end + 1]
    raise GateError(f"unterminated function: {name}")


def source_interval(source: str, begin_token: str, end_token: str) -> str:
    begin = source.index(begin_token)
    end = source.index(end_token, begin)
    return source[begin:end]


def source_model(header: str, runtime: str,
                 profile: dict[str, Any]) -> dict[str, Any]:
    # The host/MOS conditional contains two textual closing braces for the
    # single do/while body.  A brace walker therefore cannot model this
    # preprocessor interval; bind the poll to its next declaration instead.
    poll = source_interval(
        runtime,
        "static uint8_t c2_completion_poll",
        "#ifdef LISP65_C2_LITE_V6_PUBLISH_CLEAR_CORESIDENT")
    c2j = function_body(runtime, "c2_completion_c2j_matches")
    addresses = {
        "stage": "0x17e2u",
        "mode": "0x17e3u",
        "reader": "0x17e4u",
        "attempts": "0x17e5u",
        "observed_crc": "0x17e6u",
        "expected_crc": "0x17e8u",
        "frame_start": "0x17eau",
        "frame_end": "0x17ecu",
    }
    for label, address in addresses.items():
        token = (
            "#define LISP65_C2_C1_COMPLETION_"
            + label.upper()
            + "_ADDRESS "
            + address)
        require(token in header, f"bundled witness address drift: {label}")
    require(
        header.count("C2_C1_COMPLETION_WITNESS8(address, value)") == 2
        and header.count("C2_C1_COMPLETION_WITNESS16(address, value)") == 2
        and header.count("C2_C1_COMPLETION_WITNESS_INC(address)") == 2,
        "bundled witness lacks exact diagnostic/no-op forms")
    require(
        "LISP65_C2_C1_FREEZER_CUTPOINT_FIXTURE"
        not in json.dumps(profile, sort_keys=True),
        "bundled witness leaked into the product profile")
    require(
        poll.index("LISP65_C2_C1_COMPLETION_STAGE_ADDRESS, 5u")
        < poll.index("if (!w || !c2_completion_mode_length(mode))")
        < poll.index("reader_ok = c2_stream_c2d_read(")
        < poll.index("reader_ok ? 6u : 0xe6u")
        < poll.index("if (!reader_ok) return 0u;")
        < poll.index("do {")
        < poll.index("C2_CHIP_WRITE_COMPLETION_TIMEOUT_FRAMES")
        < poll.rindex("LISP65_C2_C1_COMPLETION_STAGE_ADDRESS, 8u"),
        "bundled completion witness no longer brackets the real poll")
    require(
        c2j.index("observed_crc = rtov_crc_mem(")
        < c2j.index("LISP65_C2_C1_COMPLETION_OBSERVED_CRC_ADDRESS")
        < c2j.index("LISP65_C2_C1_COMPLETION_EXPECTED_CRC_ADDRESS")
        < c2j.index("observed_crc == C2AW_C2J_SEAL(w)"),
        "bundled C2J witness no longer records computed and expected CRC")
    require(
        poll.count("c2_stream_c2d_read(") == 1
        and poll.count("reader_ok = c2_stream_c2d_read(") == 1,
        "bundled witness duplicated the product reader")
    return {
        "status": "passed-passive-slot39-witness-and-product-noop",
        "addresses": addresses,
        "reader_submits": 1,
        "product_profile_contains_fixture": False,
        "resident_cells": 0,
        "product_bytes": 0,
    }


def mutations(header: str, runtime: str,
              profile: dict[str, Any]) -> dict[str, str]:
    trials: dict[str, tuple[str, str, dict[str, Any]]] = {
        "wrong-stage-address": (
            header.replace("0x17e2u", "0x17efu", 1), runtime, profile),
        "wrong-reader-address": (
            header.replace("0x17e4u", "0x17efu", 1), runtime, profile),
        "wrong-observed-crc-address": (
            header.replace("0x17e6u", "0x17efu", 1), runtime, profile),
        "missing-reader-result-stage": (
            header,
            runtime.replace(
                "C2_C1_COMPLETION_WITNESS8(\n"
                "        LISP65_C2_C1_COMPLETION_STAGE_ADDRESS,\n"
                "        reader_ok ? 6u : 0xe6u);",
                "", 1),
            profile),
        "missing-entry-stage": (
            header,
            runtime.replace(
                "C2_C1_COMPLETION_WITNESS8(\n"
                "        LISP65_C2_C1_COMPLETION_STAGE_ADDRESS, 5u);",
                "", 1),
            profile),
        "missing-timeout-stage": (
            header,
            runtime.replace(
                "C2_C1_COMPLETION_WITNESS8(\n"
                "        LISP65_C2_C1_COMPLETION_STAGE_ADDRESS, 8u);",
                "", 1),
            profile),
        "duplicate-reader": (
            header,
            runtime.replace(
                "reader_ok = c2_stream_c2d_read(",
                "reader_ok = c2_stream_c2d_read(\n"
                "        0u, observed, attempt_length);\n"
                "    reader_ok = c2_stream_c2d_read(",
                1),
            profile),
    }
    leaked = deepcopy(profile)
    leaked["diagnostic_feature"] = (
        "LISP65_C2_C1_FREEZER_CUTPOINT_FIXTURE")
    trials["feature-leaked-into-product-profile"] = (
        header, runtime, leaked)
    rejected: dict[str, str] = {}
    for label, (trial_header, trial_runtime, trial_profile) in trials.items():
        try:
            source_model(trial_header, trial_runtime, trial_profile)
        except (GateError, ValueError):
            rejected[label] = "rejected"
        else:
            raise GateError(f"bundled-session mutation survived: {label}")
    return rejected


def gate() -> dict[str, Any]:
    header = HEADER.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    return {
        **source_model(header, runtime, profile),
        "mutations_rejected": mutations(header, runtime, profile),
    }


def main() -> int:
    result = gate()
    print(
        "c2-c1-bundled-session-gate: PASS "
        f"mutations={len(result['mutations_rejected'])} "
        "product-bytes=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            GateError) as error:
        print("c2-c1-bundled-session-gate: FIRST RED: " + str(error))
        raise SystemExit(2)
