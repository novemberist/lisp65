#!/usr/bin/env python3
"""Verify every owner-bound C1 REPL latency path from device transcripts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / "config/v11-c1-architecture-decision.json"
LIMITATION_DISPOSITION = "documented-limitation-not-performance-pass"
LIMITATION_OWNER_RESULT = (
    "documented-limitation-session-band-owner-approved-2026-07-17-cure-C2-1.2"
)
PAIR = re.compile(r"\(\s*42\s+(\d+)\s*\)")
TIMED_RESULT = re.compile(r"\(\s*42\s+(\d+)\s+(\d+)\s*\)")
DEFINITION_CALL = re.compile(r"\(\s*t\s+(\d+)\s+(\d+)\s*\)", re.IGNORECASE)
FRAME_MS = 20
# The direct seam is an internal reference, not a tighter user-visible claim.
# Bind it to the same owner-accepted 260 ms ceiling as the warm REPL path;
# repeated hardware observations span 10..13 frames because collection and
# GC alignment are part of the real product path.
DIRECT_MAX_FRAMES = 13
WARM_MAX_FRAMES = 13
DELTA_MAX_FRAMES = 3


class LatencyError(RuntimeError):
    pass


def load_decision(path: Path = DECISION) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    reopening = value.get("reopening", {})
    performance = reopening.get("performance_gate", {})
    required = {
        "load_lib_max_ratio_to_v1_0_1": 1.15,
        "single_form_repl_latency": "no-perceptible-regression",
        "optimization_after_phase_measurement": True,
        "measurement_method": "in-product-frame-counter-separated-from-transport-and-harness-time",
        "load_lib_seconds": 6.0,
        "load_lib_limit_seconds": 6.9,
        "warm_nested_entry_milliseconds": 260,
        "direct_resident_equivalent_milliseconds": 200,
        "definition_call_cycle_required": True,
        "definition_call_observed_frames": 95,
        "definition_call_observed_milliseconds": 1900,
        "definition_call_hardware_baseline_frames": [95, 96, 96],
        "definition_call_session_curve_frames": [
            95, 97, 95, 97, 96, 95, 96, 96, 98, 95, 98, 96,
        ],
        "definition_call_session_curve_classification": (
            "jitter-without-demonstrated-growth-or-plateau"
        ),
        "definition_call_quantization_tolerance_frames": 1,
        "definition_call_quantization_policy": (
            "historical-95-to-96-correction-closed-not-iterated"
        ),
        "definition_call_session_band_policy": (
            "owner-corrected-2026-07-17-from-twelve-cycle-curve; "
            "values-above-98-stop; no-iterative-widening"
        ),
        "definition_call_longer_observation_frames": 110,
        "definition_call_longer_observation_disposition": "visible-unexplained",
    }
    for key, expected in required.items():
        if performance.get(key) != expected:
            raise LatencyError(f"C1 owner performance contract drift: {key}")
    definition_call_max = performance.get("definition_call_max_frames")
    owner_result = performance.get("owner_result")
    if definition_call_max is None:
        if owner_result != "promotion-suspended-definition-call-cycle-owner-decision-pending":
            raise LatencyError("C1 pending definition-call decision drift")
    elif (
        not isinstance(definition_call_max, int)
        or definition_call_max < 1
        or performance.get("definition_call_disposition") != LIMITATION_DISPOSITION
        or owner_result != LIMITATION_OWNER_RESULT
    ):
        raise LatencyError("C1 definition-call ceiling is not owner-bound")
    exception = reopening.get("latency_exception", {})
    exception_path = ROOT / str(exception.get("contract", ""))
    if (
        not exception_path.is_file()
        or hashlib.sha256(exception_path.read_bytes()).hexdigest()
        != exception.get("contract_sha256")
    ):
        raise LatencyError("C1 latency-exception binding drift")
    exception_contract = json.loads(exception_path.read_text(encoding="utf-8"))
    if (
        exception_contract.get("status") != "owner-approved-dated-exception"
        or exception_contract.get("performance_bar_result") != "not-passed"
        or exception_contract.get("stability_gate", {}).get(
            "maximum_first_call_after_definition_frames"
        ) != definition_call_max
        or exception_contract.get("cure", {}).get("id")
        != "C2-direct-Attic-execution"
        or exception_contract.get("cure", {}).get("release") != "1.2"
        or exception_contract.get("renewal", {}).get("automatic") is not False
    ):
        raise LatencyError("C1 latency-exception contract drift")
    return performance


def frames(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="replace")
    found = PAIR.findall(text)
    if found:
        return int(found[-1])
    timed = TIMED_RESULT.findall(text)
    if timed:
        start, end = (int(value) for value in timed[-1])
        return (end - start) & 0xFF
    raise LatencyError(
        f"no measured (42 frames) or (42 start end) result in {path}"
    )


def definition_call_frames(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="replace")
    found = DEFINITION_CALL.findall(text)
    if not found:
        raise LatencyError(f"no measured (t start end) result in {path}")
    start, end = (int(value) for value in found[-1])
    return (end - start) & 0xFF


def evaluate(direct: int, warm: int, definition_call: int,
             definition_call_max: int | None, definition_call_disposition: str) -> str:
    delta = warm - direct
    if direct > DIRECT_MAX_FRAMES:
        raise LatencyError(
            f"direct path {direct} frames exceeds {DIRECT_MAX_FRAMES}"
        )
    if warm > WARM_MAX_FRAMES:
        raise LatencyError(f"warm path {warm} frames exceeds {WARM_MAX_FRAMES}")
    if delta > DELTA_MAX_FRAMES:
        raise LatencyError(f"warm delta {delta} frames exceeds {DELTA_MAX_FRAMES}")
    if definition_call_max is None:
        raise LatencyError(
            "definition-call cycle owner decision required: "
            f"observed={definition_call}frames/{definition_call * FRAME_MS}ms"
        )
    if definition_call_disposition != LIMITATION_DISPOSITION:
        raise LatencyError("definition-call result lacks the dated limitation disposition")
    if definition_call > definition_call_max:
        raise LatencyError(
            f"definition-call cycle {definition_call} frames exceeds "
            f"{definition_call_max}"
        )
    return (
        "c1-repl-latency: LIMITATION-STABLE "
        f"warm={warm}frames/{warm * FRAME_MS}ms "
        f"max={WARM_MAX_FRAMES}frames/{WARM_MAX_FRAMES * FRAME_MS}ms "
        f"direct={direct}frames/{direct * FRAME_MS}ms "
        f"direct-max={DIRECT_MAX_FRAMES}frames/{DIRECT_MAX_FRAMES * FRAME_MS}ms "
        f"delta={delta}frames/{delta * FRAME_MS}ms "
        f"delta-max={DELTA_MAX_FRAMES}frames/{DELTA_MAX_FRAMES * FRAME_MS}ms "
        f"definition-call={definition_call}frames/{definition_call * FRAME_MS}ms "
        f"definition-call-max={definition_call_max}frames/"
        f"{definition_call_max * FRAME_MS}ms "
        "performance-bar=not-passed "
        "exception=owner-dated-2026-07-16 "
        "session-band=owner-corrected-2026-07-17:95..98frames "
        "longer-observation=visible-unexplained "
        "cure=C2/1.2"
    )


def verify(direct_path: Path, warm_path: Path, definition_call_path: Path) -> str:
    performance = load_decision()
    direct = frames(direct_path)
    warm = frames(warm_path)
    definition_call = definition_call_frames(definition_call_path)
    return evaluate(
        direct,
        warm,
        definition_call,
        performance.get("definition_call_max_frames"),
        performance.get("definition_call_disposition", ""),
    )


def selftest() -> None:
    load_decision()
    with tempfile.TemporaryDirectory(prefix="lisp65-c1-latency-") as raw:
        root = Path(raw)
        direct = root / "direct.txt"
        warm = root / "warm.txt"
        definition_call = root / "definition-call.txt"
        direct.write_text("screen\n (42 13)\n", encoding="utf-8")
        warm.write_text("screen\n (42 13)\n", encoding="utf-8")
        definition_call.write_text("screen\n (t 237 79)\n", encoding="utf-8")
        if "LIMITATION-STABLE" not in evaluate(
            frames(direct), frames(warm), definition_call_frames(definition_call),
            98, LIMITATION_DISPOSITION,
        ):
            raise LatencyError("accepted boundary did not pass")
        direct.write_text("screen\n (42 14)\n", encoding="utf-8")
        try:
            evaluate(
                frames(direct), frames(warm), 98, 98, LIMITATION_DISPOSITION
            )
        except LatencyError:
            pass
        else:
            raise LatencyError("direct overrun was accepted")
        direct.write_text("screen\n (42 13)\n", encoding="utf-8")
        warm.write_text("screen\n (42 14)\n", encoding="utf-8")
        try:
            evaluate(
                frames(direct), frames(warm), 98, 98, LIMITATION_DISPOSITION
            )
        except LatencyError:
            pass
        else:
            raise LatencyError("warm overrun was accepted")
        direct.write_text("screen\n (42 8)\n", encoding="utf-8")
        warm.write_text("screen\n (42 12)\n", encoding="utf-8")
        try:
            evaluate(
                frames(direct), frames(warm), 98, 98, LIMITATION_DISPOSITION
            )
        except LatencyError:
            pass
        else:
            raise LatencyError("delta overrun was accepted")
        try:
            evaluate(13, 13, 99, 98, LIMITATION_DISPOSITION)
        except LatencyError:
            pass
        else:
            raise LatencyError("definition-call overrun was accepted")
        try:
            evaluate(13, 13, 98, 98, "passed")
        except LatencyError:
            pass
        else:
            raise LatencyError("performance PASS relabeling was accepted")
    print("v11-c1-repl-latency: SELFTEST PASS mutations=5")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--direct", type=Path)
    parser.add_argument("--warm", type=Path)
    parser.add_argument("--definition-call", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        if args.selftest:
            selftest()
        else:
            if not args.direct or not args.warm or not args.definition_call or not args.out:
                raise LatencyError(
                    "--direct, --warm, --definition-call and --out are required"
                )
            line = verify(args.direct, args.warm, args.definition_call)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(line + "\n", encoding="utf-8")
            print(line)
    except (OSError, UnicodeError, json.JSONDecodeError, LatencyError) as exc:
        print(f"v11-c1-repl-latency: FAIL {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
