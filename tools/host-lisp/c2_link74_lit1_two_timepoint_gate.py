#!/usr/bin/env python3
"""Prequalify Link 74's target-only LIT(1) two-timepoint discriminator."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


CONFIG = ROOT / "config/c2.2-link74-lit1-two-timepoint-discriminator.json"
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    require(isinstance(data, dict), f"expected object: {path}")
    return data


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact(root: Path, row: dict[str, Any]) -> Path:
    path = root / str(row["path"])
    require(path.is_file(), f"artifact absent: {path}")
    require(path.stat().st_size == int(row["bytes"]),
            f"artifact size drift: {path}")
    require(sha256(path) == row["sha256"], f"artifact SHA drift: {path}")
    return path


def model_gate(config: dict[str, Any]) -> None:
    require(config["status"] == "prequalified-spec-no-hardware",
            "hardware result must not be preclaimed")
    require(config["promotable"] is False, "diagnostic must be nonpromotable")
    capture = config["capture"]
    require(capture["code_header"] == {"start": 0xBFA0, "bytes": 11},
            "code-header capture drift")
    require(capture["literal_1"]["low"] == 0xBFA9
            and capture["literal_1"]["high"] == 0xBFAA,
            "LIT(1) address drift")
    require(capture["owner"]["bank"] == 0xBFD8
            and capture["owner"]["ordinal_low"] == 0xB9B2
            and capture["owner"]["ordinal_high"] == 0xB9B3,
            "owner witness drift")
    runtime = capture["runtime_context"]
    require(runtime["start"] == 0xC084 and runtime["bytes"] == 46,
            "runtime context drift")
    require(runtime["entries_offset_low"] == 0xC098
            and runtime["entries_offset_high"] == 0xC099
            and runtime["resolutions_offset_low"] == 0xC09A
            and runtime["resolutions_offset_high"] == 0xC09B,
            "runtime offset witness drift")
    expected = config["expected_word"]
    require(expected["source"] == "live-c2d-resolution-plane",
            "expected word is not independently sourced")
    require(expected["host_numeric_ordinal_is_authority"] is False,
            "host numeric symbol ordinal must not bind target truth")
    derivation = "\n".join(expected["derivation"])
    for fragment in (
            "ordinal * 10", "entry_row[6:8]", "resolution_base + 1",
            "SYMI", "%is"):
        require(fragment in derivation,
                f"live expected-word derivation incomplete: {fragment}")
    points = config["checkpoints"]
    require([row["id"] for row in points] == [
        "initial-before-prim68-takeover",
        "reload-before-literal-consumption",
    ], "both ordered checkpoints are mandatory")
    require(points[0]["pc"] == 0x1E8F
            and points[0]["patch"]["before_hex"] == "a93380"
            and points[0]["patch"]["after_hex"] == "4c8f1e",
            "initial checkpoint drift")
    require(points[1]["pc"] == 0x543B
            and points[1]["patch"]["before_hex"] == "a2a7a0"
            and points[1]["patch"]["after_hex"] == "4c3b54",
            "reload checkpoint drift")
    decision = config["decision"]
    require("differs" in decision["transport_or_materialization_fault"]
            and "byteidentical" in
            decision["transport_correct_consumption_fault"],
            "binary adjudication drift")
    procedure = "\n".join(config["hardware_procedure"])
    for fragment in (
            "nonpromotable", "three times", "Restore bytes a9 33 80",
            "without rebooting", "Discard"):
        require(fragment in procedure, f"procedure omitted: {fragment}")


def main() -> int:
    config = load(CONFIG)
    model_gate(config)
    artifacts = {
        name: artifact(ROOT, row)
        for name, row in config["authority"].items()
    }

    truth = ElfTruth.read(
        artifacts["product_elf"], llvm_readobj=LLVM_READOBJ)
    for name, row in config["linked_symbols"].items():
        symbol = truth.symbol(name)
        require(symbol.value == int(row["address"])
                and symbol.bytes == int(row["bytes"]),
                f"linked symbol drift: {name}")

    boot_catalog = load(artifacts["boot_catalog"])
    slices = boot_catalog["slices"]
    island = [row for row in slices
              if row["name"] == "resident-island-image"]
    require(len(island) == 1, "resident island catalog identity is not unique")
    island = island[0]
    first = config["checkpoints"][0]["patch"]
    first_pc = config["checkpoints"][0]["pc"]
    require(island["id"] == first["slice_id"]
            and island["vma"] == first["slice_vma"]
            and island["file_offset"] == first["slice_file_offset"]
            and first["relative_offset"] == first_pc - island["vma"]
            and first["artifact_offset"]
            == island["file_offset"] + first["relative_offset"],
            "resident-island patch provenance drift")
    boot = artifacts["boot_bin"].read_bytes()
    at = first["artifact_offset"]
    require(boot[at:at + 3].hex() == first["before_hex"],
            "initial checkpoint bytes drift")

    prg = artifacts["product_prg"].read_bytes()
    second = config["checkpoints"][1]["patch"]
    second_pc = config["checkpoints"][1]["pc"]
    load_address = int.from_bytes(prg[:2], "little")
    require(load_address == second["load_address"], "PRG load address drift")
    require(second["artifact_offset"]
            == 2 + second_pc - load_address,
            "reload patch PRG provenance drift")
    at = second["artifact_offset"]
    require(prg[at:at + 3].hex() == second["before_hex"],
            "reload checkpoint bytes drift")

    mutations: list[tuple[str, Any]] = [
        ("wrong-LIT1-address",
         lambda c: c["capture"]["literal_1"].update({"low": 0xBFA7})),
        ("missing-initial-checkpoint",
         lambda c: c["checkpoints"].pop(0)),
        ("missing-reload-checkpoint",
         lambda c: c["checkpoints"].pop()),
        ("host-ordinal-as-authority",
         lambda c: c["expected_word"].update(
             {"host_numeric_ordinal_is_authority": True})),
        ("expected-from-materialized-buffer",
         lambda c: c["expected_word"].update({"source": "vm-codebuf"})),
        ("decision-without-independent-equality",
         lambda c: c["decision"].update(
             {"transport_correct_consumption_fault": "accept"})),
    ]
    rejected = 0
    for label, mutate in mutations:
        candidate = deepcopy(config)
        mutate(candidate)
        try:
            model_gate(candidate)
        except (GateError, KeyError, IndexError):
            rejected += 1
        else:
            raise GateError(f"negative mutation accepted: {label}")
    require(rejected == len(mutations), "mutation accounting drift")
    print(
        "c2-link74-lit1-two-timepoint-gate: PASS "
        f"mutations={rejected}/{len(mutations)} "
        "cells=$bfa9/$bfaa checkpoints=$1e8f,$543b")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, KeyError, OSError, ValueError) as error:
        print("c2-link74-lit1-two-timepoint-gate: FIRST RED: " + str(error))
        raise SystemExit(1)
