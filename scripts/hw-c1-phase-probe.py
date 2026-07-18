#!/usr/bin/env python3
"""Run and bind one C1 compiler phase measurement on a physical MEGA65.

Each diagnostic product records one begin/end sample of the 50 Hz frame byte at
$D7FA.  Pairwise builds are intentional: a monolithic trace does not fit the
real overlay slices and would measure a product that cannot pass its own link
gates.  Five successful samples can be assembled into one phase-table receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
TRACE_ADDRESS = 0x17F0
TRACE_SIZE = 2
FRAME_HZ = 50
PRODUCT_BASE = Path("build/products/workbench/c1-phase-probe")
SHELF = Path("build/bytecode/dialect-v2/shelf/library-shelf.bin")
DEFAULT_FORM = "(+ 20 22)"
DEFAULT_EXPECT = "42"
BASELINE_SECONDS = 6.0
MAX_RATIO = 1.15

PHASES: dict[int, str] = {
    1: "attic-shelf-transfer",
    2: "l65m-preflight-and-commit",
    3: "compile",
    4: "retire",
    5: "result-install",
    6: "l65m-preflight-only",
    7: "l65m-commit-only",
    8: "l65m-commit-verify",
    9: "l65m-commit-apply",
    10: "c1-expression-with-lease",
    11: "c1-expression-with-lease-and-trusted-plan",
}
TABLE_PROBES = tuple(range(1, 10))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--probe", type=int, choices=sorted(PHASES))
    action.add_argument("--assemble", action="store_true")
    action.add_argument("--selftest", action="store_true")
    parser.add_argument("--no-deploy", action="store_true",
                        help="read a probe already running on the machine")
    parser.add_argument("--external-only", action="store_true",
                        help="record end-to-end REPL elapsed time without an in-product trace")
    parser.add_argument("--sample-label", default="",
                        help="suffix for repeated samples such as cold or warm")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--device", default=os.environ.get("DEVICE", "/dev/ttyUSB1"))
    parser.add_argument("--tools", default=os.environ.get("TOOLS", "tools/m65tools"))
    parser.add_argument("--ip", default=os.environ.get("MEGA65_IP", ""))
    parser.add_argument("--out-dir", default="build/hw/v11-c1-phase")
    parser.add_argument("--form", default=DEFAULT_FORM)
    parser.add_argument("--expect", default=DEFAULT_EXPECT)
    parser.add_argument("--boot-wait", type=float, default=3.0)
    parser.add_argument("--expect-poll", type=int, default=30)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"expected a JSON object: {path}")
    return value


def artifacts(probe: int) -> dict[str, Path]:
    directory = ROOT / f"{PRODUCT_BASE}-{probe}"
    result = {
        "directory": directory,
        "resident_prg": directory / "lisp65-workbench-resident.prg",
        "preload": directory / "stdlib-with-overlay.ext.bin",
        "runtime_overlays": directory / "lisp65-mvp-workbench.overlays.bin",
        "runtime_manifest": directory / "runtime-overlays-manifest.json",
        "stage_manifest": directory / "stage-manifest.json",
        "footprint_audit": directory / "footprint-audit.json",
        "shelf": ROOT / SHELF,
    }
    missing = [str(path) for name, path in result.items()
               if name != "directory" and not path.is_file()]
    if missing:
        raise SystemExit("missing phase-probe artifacts:\n  " + "\n  ".join(missing))
    return result


def validate_build(probe: int, paths: dict[str, Path]) -> dict[str, Any]:
    footprint = load_json(paths["footprint_audit"])
    if footprint.get("status") != "pass":
        raise SystemExit(f"probe {probe}: footprint audit is not PASS")
    if not all(footprint.get("checks", {}).values()):
        raise SystemExit(f"probe {probe}: one or more footprint checks are false")

    runtime = load_json(paths["runtime_manifest"])
    slices = runtime.get("slices")
    if not isinstance(slices, list):
        raise SystemExit(f"probe {probe}: runtime manifest has no slice list")
    target_names = {
        1: ["attic-library-shelf"],
        2: ["l65m-phase-00", "l65m-phase-06"],
        3: ["c1-compiler-lifetime"],
        4: ["c1-compiler-lifetime"],
        5: ["lcc-install-00", "lcc-install-02"],
        6: ["l65m-phase-00", "l65m-phase-20"],
        7: ["l65m-commit-00", "l65m-commit-06"],
        8: ["l65m-commit-00"],
        9: ["l65m-commit-00", "l65m-commit-06"],
        10: ["c1-compiler-lifetime"],
        11: ["c1-compiler-lifetime", "attic-library-shelf"],
    }[probe]
    by_name = {str(item.get("name")): item for item in slices}
    missing = [name for name in target_names if name not in by_name]
    if missing:
        raise SystemExit(f"probe {probe}: target runtime slices missing: {missing}")
    over = [by_name[name] for name in target_names
            if int(by_name[name].get("memory_size", 0)) > 1792]
    if over:
        raise SystemExit(f"probe {probe}: instrumented slice exceeds 1792 bytes: {over}")
    return {
        "footprint": {
            "status": footprint["status"],
            "boot_stack_gap": footprint["boot_stack_gap"],
            "post_boot_reserve": footprint["post_boot_reserve"],
            "runtime_stack_gap": footprint["runtime_stack_gap"],
        },
        "instrumented_slices": [
            {
                "name": name,
                "memory_size": int(by_name[name]["memory_size"]),
                "headroom_to_1792": 1792 - int(by_name[name]["memory_size"]),
            }
            for name in target_names
        ],
    }


def run(command: list[str], *, dry_run: bool = False) -> None:
    if dry_run:
        print("DRY-RUN:", " ".join(command))
        return
    subprocess.run(command, cwd=ROOT, check=True)


def deploy(args: argparse.Namespace, paths: dict[str, Path]) -> None:
    command = [
        "sh", "scripts/run-on-mega65.sh", "--tools", args.tools,
        "--preload-bin", "0x08000000", str(paths["runtime_overlays"]),
        "--preload-bin", "0x050000", str(paths["preload"]),
        "--preload-bin", "0x08100000", str(paths["shelf"]),
        "--run", str(paths["resident_prg"]),
    ]
    if args.ip:
        command[4:4] = ["--ip", args.ip]
    run(command, dry_run=args.dry_run)
    if args.dry_run:
        print(f"DRY-RUN: sleep {args.boot_wait}")
    else:
        time.sleep(args.boot_wait)


def exercise(args: argparse.Namespace, probe: int, out_dir: Path) -> float:
    suffix = f"-{args.sample_label}" if args.sample_label else ""
    command = [
        "sh", "scripts/hw-jtag-repl.sh",
        "--tools", args.tools,
        "--device", args.device,
        "--out-dir", str(out_dir),
        "--prefix", f"c1-phase-{probe}{suffix}",
        "--form", args.form,
        "--expect", args.expect,
        "--expect-poll", str(args.expect_poll),
        "--verified-input",
    ]
    if args.dry_run:
        command.append("--dry-run")
    start = time.monotonic()
    run(command, dry_run=False)
    return time.monotonic() - start


def read_trace(args: argparse.Namespace, probe: int, out_dir: Path) -> tuple[Path, bytes]:
    dump = out_dir / f"c1-phase-{probe}-trace.bin"
    spec = f"0x{TRACE_ADDRESS:04x}:0x{TRACE_ADDRESS + TRACE_SIZE:04x}={dump}"
    command = [str(ROOT / args.tools / "m65"), "-l", args.device,
               "--memsave", spec]
    if args.dry_run:
        print("DRY-RUN:", " ".join(command))
        return dump, bytes(TRACE_SIZE)
    subprocess.run(command, cwd=ROOT, check=True)
    raw = dump.read_bytes()
    if len(raw) != TRACE_SIZE:
        raise SystemExit(f"probe {probe}: expected {TRACE_SIZE} trace bytes, got {len(raw)}")
    return dump, raw


def sample_receipt(args: argparse.Namespace, probe: int) -> dict[str, Any]:
    paths = artifacts(probe)
    build_evidence = validate_build(probe, paths)
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.no_deploy:
        deploy(args, paths)
    elapsed = exercise(args, probe, out_dir)
    dump: Path | None = None
    begin = end = delta = 0
    if not args.external_only:
        dump, raw = read_trace(args, probe, out_dir)
        begin, end = raw
        delta = (end - begin) & 0xFF

    bound_artifacts = {}
    for name in ("resident_prg", "preload", "runtime_overlays", "shelf"):
        path = paths[name]
        bound_artifacts[name] = {
            "path": str(path.relative_to(ROOT)),
            "sha256": sha256(path),
            "size": path.stat().st_size,
        }

    receipt: dict[str, Any] = {
        "schema": "lisp65-v11-c1-phase-sample-v1",
        "status": "dry-run" if args.dry_run else "pass",
        "claim": ("diagnostic external end-to-end comparison; includes JTAG harness overhead; "
                  "not product or G5 evidence" if args.external_only else
                  "diagnostic phase measurement; not product or G5 evidence"),
        "probe_id": probe,
        "phase": PHASES[probe],
        "input": {"form": args.form, "expected_result": args.expect},
        "trace": None if args.external_only else {
            "address": TRACE_ADDRESS,
            "clock_register": 0xD7FA,
            "clock_hz": FRAME_HZ,
            "begin": begin,
            "end": end,
            "delta_frames_modulo_256": delta,
            "nominal_milliseconds": delta * 1000 // FRAME_HZ,
            "resolution_milliseconds": 1000 // FRAME_HZ,
            "wrap_limit_milliseconds": 256 * 1000 // FRAME_HZ,
            "interpretation": "valid as elapsed frames only while this phase is below one 256-frame wrap",
            "raw": str(dump.relative_to(ROOT)),
        },
        "sample_label": args.sample_label or None,
        "external_repl_elapsed_seconds": round(elapsed, 3),
        "build_gates": build_evidence,
        "artifacts": bound_artifacts,
    }
    suffix = f"-{args.sample_label}" if args.sample_label else ""
    receipt_path = out_dir / f"c1-phase-{probe}{suffix}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    if not args.external_only:
        print(f"phase {probe} ({PHASES[probe]}): {delta} frames ~= {delta / FRAME_HZ:.3f}s")
    print(f"external REPL path: {elapsed:.3f}s")
    print(f"wrote {receipt_path}")
    return receipt


def assemble(args: argparse.Namespace) -> int:
    out_dir = ROOT / args.out_dir
    samples: list[dict[str, Any]] = []
    for probe in TABLE_PROBES:
        path = out_dir / f"c1-phase-{probe}.json"
        if not path.is_file():
            raise SystemExit(f"missing phase sample: {path}")
        sample = load_json(path)
        if sample.get("status") != "pass":
            raise SystemExit(f"phase sample is not PASS: {path}")
        if sample.get("probe_id") != probe or sample.get("phase") != PHASES[probe]:
            raise SystemExit(f"phase identity mismatch: {path}")
        samples.append(sample)

    total_frames = sum(int(item["trace"]["delta_frames_modulo_256"])
                       for item in samples)
    receipt = {
        "schema": "lisp65-v11-c1-phase-table-v1",
        "status": "pass",
        "claim": "five independently linked diagnostic measurements; phase values are not an additive end-to-end benchmark",
        "measurement_model": {
            "clock": "$D7FA 50 Hz frame byte",
            "pairwise_builds": True,
            "reason": "a monolithic trace cannot pass the real overlay footprint gates",
            "modulo_limit": "each phase must remain below 256 frames (5.120 seconds)",
            "sum_is_diagnostic_only": True,
        },
        "owner_performance_bar": {
            "v1_0_1_load_lib_baseline_seconds": BASELINE_SECONDS,
            "maximum_ratio": MAX_RATIO,
            "maximum_load_lib_seconds": round(BASELINE_SECONDS * MAX_RATIO, 3),
            "single_form_repl": "no-perceptible-regression",
        },
        "phase_sum_diagnostic": {
            "frames": total_frames,
            "nominal_seconds": round(total_frames / FRAME_HZ, 3),
        },
        "phases": [
            {
                "probe_id": item["probe_id"],
                "phase": item["phase"],
                "delta_frames_modulo_256": item["trace"]["delta_frames_modulo_256"],
                "nominal_milliseconds": item["trace"]["nominal_milliseconds"],
                "external_repl_elapsed_seconds": item["external_repl_elapsed_seconds"],
                "sample_receipt_sha256": sha256(out_dir / f"c1-phase-{item['probe_id']}.json"),
            }
            for item in samples
        ],
    }
    path = out_dir / "c1-phase-table.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("C1 phase table:")
    for item in receipt["phases"]:
        print(f"  {item['phase']}: {item['delta_frames_modulo_256']} frames "
              f"(~{item['nominal_milliseconds'] / 1000:.3f}s)")
    print(f"  diagnostic sum: {total_frames} frames (~{total_frames / FRAME_HZ:.3f}s)")
    print(f"wrote {path}")
    return 0


def selftest() -> int:
    assert set(PHASES) == set(range(1, 12))
    assert ((3 - 250) & 0xFF) == 9
    assert abs(BASELINE_SECONDS * MAX_RATIO - 6.9) < 0.000001
    for probe in PHASES:
        paths = artifacts(probe)
        evidence = validate_build(probe, paths)
        assert evidence["footprint"]["status"] == "pass"
        assert all(item["headroom_to_1792"] >= 0
                   for item in evidence["instrumented_slices"])
    print(f"hw-c1-phase-probe: PASS ({len(PHASES)} pairwise builds pass real footprint gates)")
    return 0


def main() -> int:
    args = parse_args()
    if args.selftest:
        return selftest()
    if args.assemble:
        return assemble(args)
    assert args.probe is not None
    sample_receipt(args, args.probe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
