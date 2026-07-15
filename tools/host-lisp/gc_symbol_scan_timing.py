#!/usr/bin/env python3
"""Measure and gate linear scaling of the GC interned-symbol root scan."""

import argparse
import json
import math
import statistics
import subprocess
from pathlib import Path


def regression(points):
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    xbar = statistics.mean(xs)
    ybar = statistics.mean(ys)
    sxx = sum((x - xbar) ** 2 for x in xs)
    slope = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys)) / sxx
    intercept = ybar - slope * xbar
    residual = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    total = sum((y - ybar) ** 2 for y in ys)
    r2 = 1.0 if total == 0 else 1.0 - residual / total
    return slope, intercept, r2


def run(args):
    args.binary.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            args.cc, "-std=c99", "-O2", "-Wall", "-DLISP65_GC_SCAN_PROBE",
            f"-DMAX_SYM={args.max_symbols}", f"-DNAMEPOOL={args.namepool}",
            "-DHEAP_CELLS=48", "-DGC_ROOTS=16", "-Isrc",
            "scripts/gc-symbol-scan-timing-main.c", "src/mem.c", "src/symbol.c",
            "src/interrupt.c", "-o", str(args.binary),
        ],
        check=True,
    )
    samples = []
    medians = []
    for symbols in args.symbols:
        values = []
        for _ in range(args.repeats):
            cp = subprocess.run(
                [str(args.binary), str(symbols), str(args.rounds), str(args.warmup)],
                check=True, text=True, stdout=subprocess.PIPE,
            )
            value = json.loads(cp.stdout)
            expected_visits = symbols * args.rounds
            if value["scan_visits"] != expected_visits:
                raise SystemExit(
                    f"gc-symbol-scan-timing: FAIL symbols={symbols} "
                    f"visits={value['scan_visits']} expected={expected_visits}"
                )
            value["ns_per_gc"] = value["elapsed_ns"] / args.rounds
            values.append(value)
            samples.append(value)
        medians.append((symbols, statistics.median(v["ns_per_gc"] for v in values)))

    slope, intercept, r2 = regression(medians)
    if not math.isfinite(slope) or slope <= 0 or r2 < args.min_r2:
        raise SystemExit(
            f"gc-symbol-scan-timing: FAIL slope={slope:.3f}ns/symbol "
            f"r2={r2:.6f} min_r2={args.min_r2:.6f}"
        )
    delta_symbols = args.max_symbols - args.baseline_symbols
    report = {
        "schema": "lisp65-gc-symbol-scan-timing-v1",
        "status": "pass",
        "scope": "host-monotonic-timing-plus-exact-visit-counter;not-target-cycle-accurate",
        "build": {
            "max_symbols": args.max_symbols,
            "namepool": args.namepool,
            "rounds": args.rounds,
            "warmup": args.warmup,
            "repeats": args.repeats,
        },
        "medians_ns_per_gc": [
            {"symbols": symbols, "ns_per_gc": value} for symbols, value in medians
        ],
        "linear_fit": {
            "slope_ns_per_symbol_per_gc": slope,
            "intercept_ns_per_gc": intercept,
            "r_squared": r2,
            "minimum_r_squared": args.min_r2,
        },
        "cap_delta": {
            "baseline_symbols": args.baseline_symbols,
            "candidate_symbols": args.max_symbols,
            "delta_symbols": delta_symbols,
            "fitted_delta_ns_per_full_scan": slope * delta_symbols,
        },
        "samples": samples,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(
        "gc-symbol-scan-timing: PASS points=%d slope=%.3fns/symbol "
        "r2=%.6f cap_delta=%d fitted_delta=%.1fns report=%s"
        % (len(medians), slope, r2, delta_symbols, slope * delta_symbols, args.out)
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cc", default="cc")
    ap.add_argument("--binary", type=Path, default=Path("build/gc-symbol-scan-timing"))
    ap.add_argument("--out", type=Path, default=Path("build/reports/workbench/gc-symbol-scan-timing.json"))
    ap.add_argument("--max-symbols", type=int, default=752)
    ap.add_argument("--baseline-symbols", type=int, default=720)
    ap.add_argument("--namepool", type=int, default=10208)
    ap.add_argument("--symbols", type=int, nargs="+", default=[256, 448, 624, 720, 752])
    ap.add_argument("--rounds", type=int, default=12000)
    ap.add_argument("--warmup", type=int, default=100)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--min-r2", type=float, default=0.97)
    args = ap.parse_args()
    run(args)


if __name__ == "__main__":
    main()
