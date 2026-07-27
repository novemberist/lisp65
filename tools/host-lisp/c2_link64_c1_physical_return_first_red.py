#!/usr/bin/env python3
"""Bind the Link-64 C1 physical-RETURN First Red."""

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
VIRTUAL_SCREEN = OUT / "boot-screen.txt"
PHYSICAL_SCREEN = OUT / "physical-return-screen.txt"
PHYSICAL_PNG = OUT / "physical-return-screen.png"
VIRTUAL_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link64-C1-attempt3-virtual-return-first-red.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link64-C1-physical-return-first-red.json")
PRODUCT_SHA = (
    "13c82707ae1797885ff2ddeb7bff62198bf897a9163ed63b7531df8212d49b2c")


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, object]:
    require(path.is_file(), f"physical-RETURN artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def main() -> int:
    require(not RECEIPT.exists(), "physical-RETURN First Red is one-shot")
    deployment = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    physical = PHYSICAL_SCREEN.read_text(encoding="utf-8")
    require(
        deployment["product"]["sha256"] == PRODUCT_SHA,
        "physical-RETURN product authority drift")
    require(
        PROBE.read_bytes() == VIRTUAL_SCREEN.read_bytes()
        == PHYSICAL_SCREEN.read_bytes(),
        "physical-RETURN screen is not byteidentical to both prior captures")
    require(
        "run:" in physical and "lisp65>" not in physical,
        "physical-RETURN screen evidence drift")
    require(not (OUT / "cutpoint-3").exists(),
            "physical-RETURN run unexpectedly armed cutpoint 3")
    require(not (OUT / "cutpoint-4").exists(),
            "physical-RETURN run unexpectedly armed cutpoint 4")
    value = {
        "format":
            "lisp65-c2.2-link64-C1-physical-return-first-red-v1",
        "recorded_on": "2026-07-25",
        "status":
            "FIRST RED: physical RETURN did not advance the visible run:",
        "classification": "hardware-loader-harness-only",
        "product_entered": False,
        "product_semantics_finding": "none",
        "authority": {
            "deployment": bind(DEPLOYMENT),
            "product_sha256": PRODUCT_SHA,
            "pre_return_probe": bind(PROBE),
            "post_virtual_return_screen": bind(VIRTUAL_SCREEN),
            "post_physical_return_screen": bind(PHYSICAL_SCREEN),
            "post_physical_return_image": bind(PHYSICAL_PNG),
            "virtual_return_first_red": bind(VIRTUAL_RECEIPT),
            "receipt_driver": bind(Path(__file__)),
        },
        "operator_attestation": {
            "action": "one physical RETURN",
            "reported_result": "es bleibt bei run:",
        },
        "observed": {
            "BASIC_ready": True,
            "visible_state": "run:",
            "all_three_text_captures_byteidentical": True,
            "REPL_visible": False,
            "cutpoint_armed": False,
            "Freezer_roundtrips": 0,
        },
        "disposition": {
            "virtual_keyboard_only_hypothesis": "disproved",
            "inference":
                "the displayed run: is not progressing as an ordinary "
                "BASIC input line under either virtual or physical RETURN",
            "product_bytes_changed": 0,
            "compiler_or_linker_runs": 0,
            "additional_hardware_actions_after_capture": 0,
        },
        "execution_accounting": {
            "physical_return_actions": 1,
            "cutpoint_3_results_consumed": 0,
            "cutpoint_4_results_consumed": 0,
            "Freezer_results_consumed": 0,
        },
        "next_gate":
            "separately authorized cold reset/redeployment with a corrected "
            "startup transport; do not continue from this loader state",
        "claim_limit":
            "Loader-harness First Red only. C1 and the matrix remain OPEN.",
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-link64-c1-physical-return-first-red: BOUND "
        "product-entered=0 freezer=0 product-delta=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
