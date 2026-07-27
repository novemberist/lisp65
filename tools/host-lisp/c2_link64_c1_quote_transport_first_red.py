#!/usr/bin/env python3
"""Bind the Link-64 Cutpoint-3 virtual-key quote transport First Red."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / (
    "build/c2.2/c1-freezer-hardware-link64-"
    "cutpoints3-4-NONPROMOTABLE")
DEPLOYMENT = OUT / "deployment.json"
CONTROL = OUT / "cutpoint-3/hold-before-control.bin"
SCREEN = OUT / "cutpoint-3/first-red-screen.txt"
SCREEN_PNG = OUT / "cutpoint-3/first-red-screen.png"
HARNESS = ROOT / "scripts/c2-c1-freezer-hw.sh"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link64-C1-cutpoint3-virtual-key-quote-first-red.json")
PRODUCT_SHA = (
    "13c82707ae1797885ff2ddeb7bff62198bf897a9163ed63b7531df8212d49b2c")


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, object]:
    require(path.is_file(), f"First-Red artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def main() -> int:
    require(not RECEIPT.exists(), "quote-transport First Red is one-shot")
    deployment = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    cutpoint = next(
        row for row in deployment["cutpoints"] if int(row["id"]) == 3)
    screen = SCREEN.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    require(
        deployment["product"]["sha256"] == PRODUCT_SHA
        and cutpoint["form"] == "(defun %c1e () 't)"
        and CONTROL.read_bytes() == b"\x03\x00"
        and "(defun %c1e () t)" in screen
        and "*** vm: bad bytecode" in screen
        and "(quote t)" not in screen
        and "sed \"s/'t/(quote t)/g\"" in harness,
        "quote-transport First-Red evidence drift")
    value = {
        "format": "lisp65-c2.2-link64-C1-quote-transport-first-red-v1",
        "recorded_on": "2026-07-25",
        "status":
            "FIRST RED: virtual-key transport dropped Lisp apostrophe",
        "classification": "hardware-harness-only",
        "product_semantics_finding": "none",
        "authority": {
            "deployment": bind(DEPLOYMENT),
            "product_sha256": PRODUCT_SHA,
            "control_capture": bind(CONTROL),
            "screen_text": bind(SCREEN),
            "screen_image": bind(SCREEN_PNG),
            "corrected_harness": bind(HARNESS),
            "receipt_driver": bind(Path(__file__)),
        },
        "observed": {
            "contract_form": "(defun %c1e () 't)",
            "screen_form": "(defun %c1e () t)",
            "screen_status": "*** vm: bad bytecode",
            "control_bytes": ["0x03", "0x00"],
            "cutpoint_reached": False,
            "Freezer_roundtrips": 0,
        },
        "correction": {
            "transport_form": "(defun %c1e () (quote t))",
            "semantic_delta": 0,
            "product_bytes_changed": 0,
            "compiler_or_linker_runs": 0,
            "rule":
                "The m65 apostrophe path is not an input authority; quoted "
                "t uses the semantically identical long form.",
        },
        "execution_accounting": {
            "hardware_runs": 1,
            "cutpoint_3_results_consumed": 0,
            "cutpoint_4_results_consumed": 0,
            "automatic_hardware_retries": 0,
        },
        "next_gate":
            "separately authorized hardware attempt with the corrected "
            "transport form; Cutpoints 3 and 4 remain OPEN",
        "claim_limit":
            "Harness First Red only. No C1, matrix, promotion or acceptance "
            "claim.",
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-link64-c1-quote-transport-first-red: BOUND "
        "control=03/00 freezer=0 product-delta=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
