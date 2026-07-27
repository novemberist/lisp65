#!/usr/bin/env python3
"""Emit and evaluate the receipt-less C2 hot-refill hardware pre-smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-hot-refill-hardware-presmoke.json"
DEPLOYMENT = ROOT / "build/c2.2/hardware-presmoke-link30-hot-refill/deployment.json"
ALLOWED_PRODUCTS = {
    "build/c2.2/substitution/product-link-30-hot-refill":
        "1eba43ca05b2d7996071ca2445d3501f8caa9aad999ca1a1c6de818f302d1d18",
    "build/c2.2/substitution/product-link-31-transaction-auth":
        "bfa76fe560979ae59cedd2128300c3761de56f45039f3be24f5ed228cdda23e2",
    "build/c2.2/substitution/product-link-32-preinstall-island-guard":
        "189548ea52b9af748217a0da94b7dc1d5daa5f17d190f5817f2fb4af486a676a",
    "build/c2.2/substitution/product-link-33-handoff-reanchor-final":
        "5f44b65a1a67530a9c3c8b687d7be597422978ae749f56101f42bdcebaf50044",
    "build/c2.2/substitution/product-link-44-c2-lite-v6-bank2-target-stage-replay":
        "db3112e6503ca96d572cccb7a399c91eb06028faeaa05e595454fb9502b7f926",
    "build/c2.2/substitution/product-link-56-selector-tail-z":
        "723579250e692112d4208ae56c0eede15f422858b3f99cc9cd2af1639599d93d",
    "build/c2.2/substitution/product-link-57-keymap-nullary-fast-path2":
        "7d568ceb7edab95a237ff3079fcf689768373a9ea48a5a43f355f6275ddc5df8",
}
PAIR = re.compile(r"\(\s*t\s+(\d+)\s+(\d+)\s*\)", re.IGNORECASE)
BOOT = re.compile(r"\(\s*(\d+)\s+(\d+)\s+(\d+)\s*\)")


class PreSmokeError(RuntimeError):
    pass


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PreSmokeError(f"JSON root is not an object: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contract() -> dict:
    value = load(CONTRACT)
    if (value.get("format") != "lisp65-c2-hot-refill-hardware-presmoke-contract-v1"
            or value.get("clock", {}).get("interval_frame_milliseconds") != 20
            or value.get("diagnostic_limits", {}).get(
                "definition_first_call_max_frames") != 16
            or value.get("diagnostic_limits", {}).get(
                "warm_second_call_max_frames") != 10
            or value.get("diagnostic_limits", {}).get(
                "boot_to_repl_max_frames") != 1500):
        raise PreSmokeError("hot-refill pre-smoke contract drift")
    if value.get("policy", {}).get("automatic_order") != [
            "boot_counter", "definition_setup", "definition_first_call",
            "warm_second_call"] or value.get("policy", {}).get("order") != [
            "boot_counter", "definition_setup", "definition_first_call",
            "warm_second_call", "gc_blockread_and_frame_line",
            "freezer_roundtrip", "post_freezer_resume"]:
        raise PreSmokeError("hot-refill pre-smoke order drift")
    for name, form in value.get("forms", {}).items():
        if not isinstance(form, str) or not form or len(form) > 144:
            raise PreSmokeError(f"unsafe or missing pre-smoke form: {name}")
    return value


def deployment(path: Path) -> dict:
    value = load(path)
    candidate = value.get("source_candidate", {})
    candidate_dir = candidate.get("directory")
    successor = candidate.get("successor_report")
    successor_bound = (
        isinstance(successor, dict)
        and isinstance(successor.get("path"), str)
        and isinstance(successor.get("sha256"), str)
    ) or isinstance(candidate.get(
        "hot_refill_successor_report_sha256"), str) or isinstance(
            candidate.get("structural_report_sha256"), str)
    if (value.get("status") != "ready-receipt-less"
            or value.get("new_product_links") != 0
            or candidate_dir not in ALLOWED_PRODUCTS
            or value.get("product", {}).get("sha256")
                != ALLOWED_PRODUCTS[candidate_dir]
            or not successor_bound):
        raise PreSmokeError("deployment is not a bound latency candidate")
    return value


def latest(pattern: re.Pattern[str], path: Path, label: str) -> tuple[int, ...]:
    found = pattern.findall(path.read_text(encoding="utf-8", errors="replace"))
    if not found:
        raise PreSmokeError(f"no {label} result in {path}")
    row = found[-1]
    if isinstance(row, str):
        row = (row,)
    return tuple(int(item) for item in row)


def evaluate(boot_path: Path, cold_path: Path, warm_path: Path,
             deployment_path: Path) -> dict:
    spec = contract()
    deploy = deployment(deployment_path)
    high_a, low, high_b = latest(BOOT, boot_path, "boot-counter")
    if high_a != high_b:
        raise PreSmokeError(
            f"boot counter crossed a high-byte boundary: {high_a}/{low}/{high_b}")
    boot_frames = high_a * 256 + low
    cold_start, cold_end = latest(PAIR, cold_path, "definition-first-call")
    warm_start, warm_end = latest(PAIR, warm_path, "warm-second-call")
    cold_frames = (cold_end - cold_start) & 0xFF
    warm_frames = (warm_end - warm_start) & 0xFF
    limits = spec["diagnostic_limits"]
    failures = []
    if boot_frames > limits["boot_to_repl_max_frames"]:
        failures.append("boot-to-repl")
    if cold_frames > limits["definition_first_call_max_frames"]:
        failures.append("definition-first-call")
    if warm_frames > limits["warm_second_call_max_frames"]:
        failures.append("warm-second-call")
    result = {
        "format": "lisp65-c2-hot-refill-hardware-presmoke-result-v1",
        "status": "pass-receipt-less" if not failures else "first-red-receipt-less",
        "claim_limit": spec["policy"]["claim_limit"],
        "product_sha256": deploy["product"]["sha256"],
        "deployment": {
            "path": str(deployment_path.resolve().relative_to(ROOT)),
            "sha256": sha(deployment_path),
        },
        "contract": {
            "path": str(CONTRACT.relative_to(ROOT)),
            "sha256": sha(CONTRACT),
        },
        "measurement": {
            "boot_to_repl": {
                "frames": boot_frames,
                "nominal_milliseconds": boot_frames * 20,
                "limit_frames": limits["boot_to_repl_max_frames"],
                "method": "$ff84/$ff83/$ff84 stable read immediately after visible REPL; includes operator/harness delay and is a regression watch, not an acceptance timing",
            },
            "definition_first_call": {
                "result": "t",
                "start": cold_start,
                "end": cold_end,
                "frames": cold_frames,
                "nominal_milliseconds": cold_frames * 20,
                "limit_frames": limits["definition_first_call_max_frames"],
                "limit_class": limits["definition_first_call_target"],
            },
            "warm_second_call": {
                "result": "t",
                "start": warm_start,
                "end": warm_end,
                "frames": warm_frames,
                "nominal_milliseconds": warm_frames * 20,
                "limit_frames": limits["warm_second_call_max_frames"],
            },
        },
        "first_red": failures,
        "value_string": (
            f"product={deploy['product']['sha256']} "
            f"boot={boot_frames}f/{boot_frames * 20}ms<=1500f-regression-watch "
            f"definition-first={cold_frames}f/{cold_frames * 20}ms<=16f "
            f"warm-second={warm_frames}f/{warm_frames * 20}ms<=10f "
            "hardware=receipt-less-presmoke acceptance=not-claimed"
        ),
    }
    return result


def emit(out: Path) -> None:
    spec = contract()
    out.mkdir(parents=True, exist_ok=True)
    for name in spec["policy"]["automatic_order"]:
        (out / f"{name}.forms").write_text(
            spec["forms"][name] + "\n", encoding="ascii")
    print(f"c2-hot-refill-hw-presmoke: EMIT PASS out={out}")


def selftest() -> None:
    contract()
    with tempfile.TemporaryDirectory(prefix="c2-hot-refill-hw-") as raw:
        root = Path(raw)
        boot = root / "boot.txt"
        cold = root / "cold.txt"
        warm = root / "warm.txt"
        boot.write_text("screen (1 200 1)\n", encoding="ascii")
        cold.write_text("screen (t 250 10)\n", encoding="ascii")
        warm.write_text("screen (t 20 30)\n", encoding="ascii")
        # Exercise transcript arithmetic without requiring a real deployment.
        high_a, low, high_b = latest(BOOT, boot, "boot-counter")
        cold_a, cold_b = latest(PAIR, cold, "definition-first-call")
        warm_a, warm_b = latest(PAIR, warm, "warm-second-call")
        if (high_a, low, high_b) != (1, 200, 1):
            raise PreSmokeError("boot transcript parser selftest failed")
        if ((cold_b - cold_a) & 0xff) != 16 or ((warm_b - warm_a) & 0xff) != 10:
            raise PreSmokeError("interval transcript parser selftest failed")
        warm.write_text("screen (t 20 31)\n", encoding="ascii")
        warm_a, warm_b = latest(PAIR, warm, "warm-second-call")
        if ((warm_b - warm_a) & 0xff) <= 10:
            raise PreSmokeError("over-limit mutation selftest failed")
    print("c2-hot-refill-hw-presmoke: SELFTEST PASS mutations=1")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("emit", "evaluate", "selftest"))
    parser.add_argument("--out", type=Path, default=Path(
        "build/c2.2/hardware-presmoke-link30-hot-refill/latency"))
    parser.add_argument("--deployment", type=Path, default=DEPLOYMENT)
    parser.add_argument("--boot", type=Path)
    parser.add_argument("--cold", type=Path)
    parser.add_argument("--warm", type=Path)
    args = parser.parse_args()
    try:
        if args.mode == "emit":
            emit(args.out)
        elif args.mode == "selftest":
            selftest()
        else:
            if not args.boot or not args.cold or not args.warm:
                raise PreSmokeError("evaluate requires --boot, --cold and --warm")
            value = evaluate(args.boot, args.cold, args.warm, args.deployment)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(
                json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="ascii")
            print(value["value_string"])
            if value["first_red"]:
                raise PreSmokeError(
                    "diagnostic limit exceeded: " + ", ".join(value["first_red"]))
    except (OSError, UnicodeError, json.JSONDecodeError, PreSmokeError) as exc:
        print(f"c2-hot-refill-hw-presmoke: FAIL {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
