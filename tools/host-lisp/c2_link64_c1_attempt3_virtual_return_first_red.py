#!/usr/bin/env python3
"""Bind the Link-64 C1 attempt-3 virtual-RETURN First Red."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / (
    "build/c2.2/c1-freezer-hardware-link64-"
    "cutpoints3-4-attempt3-NONPROMOTABLE")
DEPLOYMENT = OUT / "deployment.json"
PROBE = OUT / "autorun-probe.txt"
PROBE_PNG = OUT / "autorun-probe.png"
SCREEN = OUT / "boot-screen.txt"
SCREEN_PNG = OUT / "boot-screen.png"
HARNESS = ROOT / "scripts/c2-c1-freezer-hw.sh"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link64-C1-attempt3-virtual-return-first-red.json")
PRODUCT_SHA = (
    "13c82707ae1797885ff2ddeb7bff62198bf897a9163ed63b7531df8212d49b2c")


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, object]:
    require(path.is_file(), f"attempt-3 artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def main() -> int:
    require(not RECEIPT.exists(), "attempt-3 First Red is one-shot")
    deployment = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    probe = PROBE.read_text(encoding="utf-8")
    screen = SCREEN.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    require(
        deployment["product"]["sha256"] == PRODUCT_SHA,
        "attempt-3 product authority drift")
    require(
        "run:" in probe and "lisp65>" not in probe
        and "run:" in screen and "lisp65>" not in screen,
        "attempt-3 screen evidence drift")
    require(PROBE.read_bytes() == SCREEN.read_bytes(),
            "attempt-3 pre/post text screens differ")
    require(PROBE_PNG.read_bytes() == SCREEN_PNG.read_bytes(),
            "attempt-3 pre/post pixel screens differ")
    require(
        'run_m65 -t "~M"' in harness
        and "Completed pending m65 autorun RETURN." in harness,
        "attempt-3 explicit virtual-RETURN path absent")
    require(not (OUT / "cutpoint-3").exists(),
            "attempt-3 unexpectedly armed cutpoint 3")
    require(not (OUT / "cutpoint-4").exists(),
            "attempt-3 unexpectedly armed cutpoint 4")
    value = {
        "format":
            "lisp65-c2.2-link64-C1-attempt3-virtual-return-first-red-v1",
        "recorded_on": "2026-07-25",
        "status":
            "FIRST RED: explicit virtual RETURN did not submit m65 autorun",
        "classification": "hardware-loader-harness-only",
        "product_entered": False,
        "product_semantics_finding": "none",
        "authority": {
            "deployment": bind(DEPLOYMENT),
            "product_sha256": PRODUCT_SHA,
            "autorun_probe": bind(PROBE),
            "autorun_probe_image": bind(PROBE_PNG),
            "post_return_screen": bind(SCREEN),
            "post_return_screen_image": bind(SCREEN_PNG),
            "attempted_harness": bind(HARNESS),
            "receipt_driver": bind(Path(__file__)),
        },
        "observed": {
            "BASIC_ready": True,
            "pending_command": "run:",
            "virtual_return_command_completed": True,
            "post_return_wait_seconds": 25,
            "pre_post_text_byteidentical": True,
            "pre_post_pixels_byteidentical": True,
            "REPL_visible": False,
            "cutpoint_armed": False,
            "Freezer_roundtrips": 0,
        },
        "disposition": {
            "attempt2_hypothesis":
                "the generated autorun command needed exactly one virtual "
                "RETURN",
            "result": "disproved",
            "product_bytes_changed": 0,
            "compiler_or_linker_runs": 0,
            "additional_hardware_actions_after_first_red": 0,
        },
        "execution_accounting": {
            "hardware_runs": 1,
            "cutpoint_3_results_consumed": 0,
            "cutpoint_4_results_consumed": 0,
            "Freezer_results_consumed": 0,
            "automatic_hardware_retries": 0,
        },
        "next_gate":
            "separate authorization for a loader-transport correction; "
            "C1 cutpoints remain unstarted",
        "claim_limit":
            "Harness First Red only. C1 and the matrix remain OPEN.",
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-link64-c1-attempt3-virtual-return-first-red: BOUND "
        "product-entered=0 freezer=0 product-delta=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
