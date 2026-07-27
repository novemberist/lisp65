#!/usr/bin/env python3
"""Bind the second C1 harness First Red: omitted zero-C2J preload."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / (
    "build/c2.2/c1-freezer-hardware-link58-attempt2-NONPROMOTABLE")
DEPLOYMENT = OUT / "deployment.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-c1-freezer-zero-journal-hardware-first-red.json")
PRODUCT_SHA = (
    "4bab8371aa54060bef4ab9493e12dd6afd230baeb83a11f07daccdaa05000e6f")
C2J_OFFSET = 0xC640
C2J_BYTES = 64


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def main() -> int:
    require(not RECEIPT.exists(), "zero-C2J First-Red receipt is one-shot")
    paths = {
        "deployment": DEPLOYMENT,
        "bank0": OUT / "boot-bank0.bin",
        "bank2": OUT / "boot-bank2.bin",
        "bank3": OUT / "boot-bank3.bin",
        "bank5": OUT / "boot-bank5.bin",
        "zero_C2J": OUT / "zero-c2j.bin",
    }
    for name, path in paths.items():
        require(path.is_file(), f"missing {name}: {path}")
    deployment = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    low = paths["bank0"].read_bytes()
    bank5 = paths["bank5"].read_bytes()
    journal = bank5[C2J_OFFSET:C2J_OFFSET + C2J_BYTES]
    require(
        len(low) == 65536
        and len(bank5) == 50816
        and deployment["product"]["sha256"] == PRODUCT_SHA
        and low[0x008C] == 1
        and low[0x0077] == 0
        and low[0x0079] == 2
        and journal == bytes([0x10]) * C2J_BYTES
        and paths["zero_C2J"].read_bytes() == bytes(C2J_BYTES)
        and all(
            row["address"] != "0x0005c640"
            for row in deployment["preloads"]),
        "attempt-2 evidence is not the omitted zero-C2J preload First Red")
    receipt = {
        "format": "lisp65-c2.2-C1-Freezer-zero-C2J-first-red-v1",
        "status": "first-red-harness-omitted-zero-C2J-preload",
        "promotable": False,
        "product": deployment["product"],
        "hardware": {
            "boots": 1,
            "ready": 1,
            "rtov_fault": 0,
            "rtov_family": 2,
            "C1_cutpoints_reached": 0,
            "latency_attempts_consumed": 0,
        },
        "captures": {
            name: bind(path) for name, path in paths.items()
            if name != "zero_C2J"
        },
        "first_red": {
            "C2J_address": "0x0005c640",
            "C2J_bytes": C2J_BYTES,
            "observed": "0x10 repeated 64 times",
            "cause": (
                "The harness created a 64-byte zero-C2J artifact but omitted "
                "it from the deployment preload list, so reset-stable device "
                "memory survived into the otherwise successful Link-58 boot."),
            "product_semantics": (
                "not reached: the fixture requires a known-zero baseline; "
                "post-boot clearing is forbidden because it would falsify "
                "that precondition"),
        },
        "class_A_correction": {
            "add_preload": {
                "artifact": bind(paths["zero_C2J"]),
                "address": "0x0005c640",
            },
            "compiler_runs": 0,
            "linker_runs": 0,
            "product_bytes_changed": 0,
            "resident_bytes_changed": 0,
        },
        "claim_limit": (
            "Harness First Red only. No C1, product, promotion, "
            "acceptance-chain or release claim."),
        "next_gate": (
            "fresh immutable deployment identity with the zero-C2J preload, "
            "then separate authorization for a qualified hardware run"),
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-c1-freezer-zero-journal-replay: PASS "
        "ready=1 family=Session C2J=10x64 cause=omitted-preload "
        "compiler=0 linker=0 hardware=not-run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(
            "c2-c1-freezer-zero-journal-replay: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
