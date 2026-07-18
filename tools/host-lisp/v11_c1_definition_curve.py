#!/usr/bin/env python3
"""Measure consecutive C1 definition/call cycles and read session counters.

This is a diagnostic orchestrator, not a product or G5 verifier.  It assumes a
fresh, already-running Workbench whose first definition/call transcript was
captured by the canonical overlay-stack harness.  It reads counters only while
the REPL is idle, then submits additional unique definitions one at a time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
TIMED = re.compile(r"\(\s*t\s+(\d+)\s+(\d+)\s*\)", re.IGNORECASE)
COUNTERS = (
    "nsym",
    "npool",
    "dir_n",
    "ext_code_init",
    "ext_code_hw",
    "gc_runs",
)


class CurveError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def timed_result(path: Path) -> tuple[str, int, int, int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    found = TIMED.findall(text)
    if not found:
        raise CurveError(f"no measured (t start end) result in {path}")
    start, end = (int(value) for value in found[-1])
    return f"(t {start} {end})", start, end, (end - start) & 0xFF


def parse_counter_report(path: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, raw = line.partition("=")
        if separator and key in COUNTERS:
            values[key] = int(raw, 0)
    missing = sorted(set(COUNTERS) - set(values))
    if missing:
        raise CurveError(f"counter report lacks {', '.join(missing)}: {path}")
    return values


def read_counters(args: argparse.Namespace, index: int) -> tuple[dict[str, int], Path]:
    prefix = f"{args.prefix}-cycle-{index:02d}-counters"
    command = [
        sys.executable,
        "scripts/hw-jtag-counters.py",
        "--elf", str(args.elf),
        "--device", args.device,
        "--tools", str(args.tools),
        "--nm", str(args.nm),
        "--out-dir", str(args.out_dir),
        "--prefix", prefix,
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    report = args.out_dir / f"{prefix}.txt"
    return parse_counter_report(report), report


def run_cycle(args: argparse.Namespace, index: int) -> Path:
    name = f"%c1q{index:02d}"
    form = (
        f"(progn(eval(quote(defun {name}()(quote t))))"
        f"(let((a(peek 215 250)))(let((r(eval(quote({name}))))"
        f")(list r a(peek 215 250)))))"
    )
    if len(form) > 144:
        raise CurveError(f"cycle form exceeds verified-input budget: {len(form)}")
    prefix = f"{args.prefix}-cycle-{index:02d}"
    command = [
        "sh", "scripts/hw-jtag-repl.sh",
        "--form", form,
        "--tools", str(args.tools),
        "--device", args.device,
        "--out-dir", str(args.out_dir),
        "--prefix", prefix,
        "--wait", str(args.wait),
        "--form-wait", "0",
        "--timeout", str(args.timeout),
        "--input-retry-wait", "0.2",
        "--verified-input",
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    return args.out_dir / f"{prefix}.txt"


def correlation(xs: list[int], ys: list[int]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    xmean = sum(xs) / len(xs)
    ymean = sum(ys) / len(ys)
    numerator = sum((x - xmean) * (y - ymean) for x, y in zip(xs, ys))
    xsum = sum((x - xmean) ** 2 for x in xs)
    ysum = sum((y - ymean) ** 2 for y in ys)
    if xsum == 0 or ysum == 0:
        return None
    return numerator / math.sqrt(xsum * ysum)


def slope(xs: list[int], ys: list[int]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    xmean = sum(xs) / len(xs)
    ymean = sum(ys) / len(ys)
    denominator = sum((x - xmean) ** 2 for x in xs)
    if denominator == 0:
        return None
    return sum((x - xmean) * (y - ymean) for x, y in zip(xs, ys)) / denominator


def sample(path: Path, index: int, counters: dict[str, int],
           counter_report: Path) -> dict[str, Any]:
    result, start, end, frames = timed_result(path)
    return {
        "cycle": index,
        "result": result,
        "start_frame": start,
        "end_frame": end,
        "elapsed_frames": frames,
        "nominal_milliseconds": frames * 20,
        "transcript": relative(path),
        "transcript_sha256": sha256(path),
        "counters": counters,
        "counter_report": relative(counter_report),
        "counter_report_sha256": sha256(counter_report),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--first-transcript", type=Path, required=True)
    parser.add_argument("--cycles", type=int, default=12)
    parser.add_argument("--device", default="/dev/ttyUSB1")
    parser.add_argument("--tools", type=Path, default=Path("tools/m65tools"))
    parser.add_argument("--nm", type=Path, default=Path("tools/llvm-mos/bin/llvm-nm"))
    parser.add_argument("--out-dir", type=Path, default=Path("build/hw"))
    parser.add_argument("--prefix", default="v11-c1-definition-curve")
    parser.add_argument("--wait", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.cycles < 2 or args.cycles > 32:
        parser.error("--cycles must be in 2..32")
    return args


def main() -> int:
    args = parse_args()
    try:
        for path in (args.elf, args.manifest, args.first_transcript):
            if not path.is_file():
                raise CurveError(f"missing input: {path}")
        args.out_dir.mkdir(parents=True, exist_ok=True)
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        samples: list[dict[str, Any]] = []

        counters, report = read_counters(args, 1)
        samples.append(sample(args.first_transcript, 1, counters, report))
        for index in range(2, args.cycles + 1):
            transcript = run_cycle(args, index)
            counters, report = read_counters(args, index)
            samples.append(sample(transcript, index, counters, report))

        indices = [entry["cycle"] for entry in samples]
        frames = [entry["elapsed_frames"] for entry in samples]
        analysis: dict[str, Any] = {
            "minimum_frames": min(frames),
            "maximum_frames": max(frames),
            "mean_frames": sum(frames) / len(frames),
            "least_squares_frames_per_cycle": slope(indices, frames),
            "correlation": {},
        }
        for counter in COUNTERS:
            values = [entry["counters"][counter] for entry in samples]
            analysis["correlation"][counter] = {
                "first": values[0],
                "last": values[-1],
                "delta": values[-1] - values[0],
                "pearson_r_with_frames": correlation(values, frames),
            }

        value = {
            "format": "lisp65-v11-c1-definition-call-session-curve-v1",
            "version": 1,
            "status": "diagnostic-measurement-only",
            "claim": "Read-only hardware curve; not a performance PASS, G5 receipt or promotion authorization.",
            "product_artifact_set_sha256": manifest.get("product_artifact_set_sha256"),
            "manifest": relative(args.manifest),
            "manifest_sha256": sha256(args.manifest),
            "elf": relative(args.elf),
            "elf_sha256": sha256(args.elf),
            "measurement": {
                "clock": "$D7FA",
                "frame_milliseconds": 20,
                "cycles": args.cycles,
                "counter_method": "ELF-resolved JTAG memsave while REPL idle after each cycle",
                "instrumentation_limit": "Counter reads occur between cycles and may affect phase alignment; timed intervals are entirely on-device and exclude the reads.",
            },
            "samples": samples,
            "analysis": analysis,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("v11-c1-definition-curve: MEASURED " + ",".join(str(item) for item in frames))
        print(f"wrote {args.out}")
    except (CurveError, OSError, UnicodeError, json.JSONDecodeError,
            subprocess.CalledProcessError) as exc:
        print(f"v11-c1-definition-curve: FAIL {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
