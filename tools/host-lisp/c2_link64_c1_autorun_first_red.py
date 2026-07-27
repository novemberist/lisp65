#!/usr/bin/env python3
"""Bind the Link-64 attempt-2 pending autorun First Red."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / (
    "build/c2.2/c1-freezer-hardware-link64-"
    "cutpoints3-4-attempt2-NONPROMOTABLE")
DEPLOYMENT = OUT / "deployment.json"
SCREEN = OUT / "boot-screen.txt"
SCREEN_PNG = OUT / "boot-screen.png"
LATE_SCREEN = OUT / "boot-late-screen.txt"
HARNESS = ROOT / "scripts/c2-c1-freezer-hw.sh"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link64-C1-attempt2-pending-autorun-first-red.json")
PRODUCT_SHA = (
    "13c82707ae1797885ff2ddeb7bff62198bf897a9163ed63b7531df8212d49b2c")


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, object]:
    require(path.is_file(), f"autorun First-Red artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def main() -> int:
    require(not RECEIPT.exists(), "autorun First Red is one-shot")
    deployment = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    screen = SCREEN.read_text(encoding="utf-8")
    late = LATE_SCREEN.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    require(
        deployment["product"]["sha256"] == PRODUCT_SHA
        and "run:" in screen and "lisp65>" not in screen
        and "run:" in late and "lisp65>" not in late
        and 'run_m65 -t "~M"' in harness
        and "generated BASIC `run:`" in harness,
        "pending-autorun First-Red evidence drift")
    value = {
        "format": "lisp65-c2.2-link64-C1-pending-autorun-first-red-v1",
        "recorded_on": "2026-07-25",
        "status": "FIRST RED: m65 autorun command lacked final RETURN",
        "classification": "hardware-loader-harness-only",
        "product_entered": False,
        "product_semantics_finding": "none",
        "authority": {
            "deployment": bind(DEPLOYMENT),
            "product_sha256": PRODUCT_SHA,
            "boot_screen": bind(SCREEN),
            "late_screen": bind(LATE_SCREEN),
            "screen_image": bind(SCREEN_PNG),
            "corrected_harness": bind(HARNESS),
            "receipt_driver": bind(Path(__file__)),
        },
        "observed": {
            "BASIC_ready": True,
            "pending_command": "run:",
            "stable_late_capture": True,
            "REPL_visible": False,
            "cutpoint_armed": False,
            "Freezer_roundtrips": 0,
        },
        "correction": {
            "predicate":
                "standalone run: present and lisp65> absent",
            "action": "inject exactly one explicit RETURN",
            "action_on_running_product": "none",
            "product_bytes_changed": 0,
            "compiler_or_linker_runs": 0,
        },
        "execution_accounting": {
            "hardware_runs": 1,
            "cutpoint_3_results_consumed": 0,
            "cutpoint_4_results_consumed": 0,
            "automatic_hardware_retries": 0,
        },
        "next_gate":
            "separately authorized attempt 3 with quote-safe form and "
            "predicate-guarded autorun RETURN",
        "claim_limit":
            "Loader-harness First Red only. C1 and the matrix remain OPEN.",
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-link64-c1-autorun-first-red: BOUND "
        "product-entered=0 freezer=0 product-delta=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
