#!/usr/bin/env python3
"""Bind the C2-lite Bank-3 line-1 harness First Red and its host-only fix."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BAD = ROOT / "build/c2.2/hardware-presmoke-c2-lite-bank3-replay5"
FIXED = ROOT / "build/c2.2/hardware-presmoke-c2-lite-bank3-replay6-two-record"
AUTH = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-bank3-stage-artifact-completion-replay5-structural-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-bank3-presmoke-harness-first-red-receipt.json")


class DiagnosisError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise DiagnosisError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"evidence absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def descriptor(data: bytes, offset: int = 0) -> dict[str, Any]:
    require(offset + 18 <= len(data), "truncated L65O descriptor")
    magic, version, header, build, vma, entry, length, crc = struct.unpack_from(
        "<4sBBIHHHH", data, offset)
    require(magic == b"L65O" and version == 1 and header == 18,
            "invalid L65O descriptor envelope")
    require(offset + header + length <= len(data), "truncated L65O payload")
    return {"magic": magic.decode("ascii"), "version": version,
            "header_bytes": header, "build_id": f"0x{build:08x}",
            "vma": f"0x{vma:04x}", "entry": f"0x{entry:04x}",
            "payload_bytes": length, "payload_crc16": f"0x{crc:04x}",
            "record_offset": offset}


def protect(path: Path) -> None:
    for item in sorted(path.rglob("*"), reverse=True):
        if item.is_file():
            os.chmod(item, 0o444)
        elif item.is_dir():
            os.chmod(item, 0o555)
    os.chmod(path, 0o555)


def build() -> dict[str, Any]:
    require(not RECEIPT.exists(), "Bank-3 harness First Red already recorded")
    bad = json.loads((BAD / "deployment.json").read_text(encoding="utf-8"))
    fixed = json.loads((FIXED / "deployment.json").read_text(encoding="utf-8"))
    auth = json.loads(AUTH.read_text(encoding="utf-8"))
    product_sha = "62f556dfcdeec59783cc2adec16afc3ccb5f618a24b17898c1162f81c1c1b954"
    require(auth["status"]
            == "passed-complete-c2-lite-bank3-candidate-hardware-not-run"
            and bad["product"]["sha256"] == fixed["product"]["sha256"]
            == product_sha,
            "candidate/deployment identity drift")
    readbacks = []
    for row in bad["preloads"]:
        source = ROOT / row["path"]
        readback = BAD / ("readback-" + source.name)
        require(readback.read_bytes() == source.read_bytes(),
                f"deployment readback drift: {source.name}")
        readbacks.append(bind(readback))

    old_stage = (BAD / "boot-overlay.stage.bin").read_bytes()
    old_record = descriptor(old_stage)
    require(len(old_stage) == 1749
            and old_record["entry"] == "0xc860"
            and old_record["payload_bytes"] == 1731
            and "boot_chain" not in bad,
            "old one-record deployment diagnosis drift")
    chain = fixed["boot_chain"]
    fixed_stage = (FIXED / "boot-overlay.stage.bin").read_bytes()
    first = descriptor(fixed_stage, chain["first_record"]["record_offset"])
    second = descriptor(fixed_stage, chain["second_record"]["record_offset"])
    require(len(fixed_stage) == chain["total_bytes"] == 3285
            and chain["padding_bytes"] == 24
            and first["entry"] == "0xc368"
            and first["payload_bytes"] == 1494
            and second["entry"] == "0xc860"
            and second["payload_bytes"] == 1731
            and fixed["new_product_links"] == 0,
            "corrected fixed-chain deployment is not exact")

    low = (BAD / "line1-first-red/low-0000-0200.bin").read_bytes()
    require(low[0x79] == 0 and low[0x8c] == 0,
            "failed run unexpectedly published family/READY")
    value = {
        "format": "lisp65-c2-lite-v6-bank3-presmoke-harness-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "first-red-line1-old-one-record-deployment-harness",
        "promotable": False,
        "candidate": auth["product_identity"],
        "hardware": {
            "runs": 1, "line_reached": 1,
            "completed_latency_measurements": 0,
            "two_attempt_rule_slots_consumed": 0,
            "operator_observation": (
                "red frame; BASIC remains at READY/RUN and never enters Lisp"),
            "all_six_preloads_byte_identical": True,
            "published_family": 0, "c2_ready": 0,
        },
        "diagnosis": {
            "class": "hardware-presmoke-deployment-harness-version-drift",
            "old_emitted_record": old_record,
            "product_expected_first_record": {
                "entry": "0xc368", "payload_bytes": 1494,
                "role": "bank3-boot-stager"},
            "cause": (
                "The pre-smoke harness still emitted the historical one-record "
                "Workbench package. The current product loader requires the "
                "fixed two-record chain: Bank-3 Boot stager first, aligned "
                "Workbench successor second. It therefore rejected the first "
                "descriptor before any Bank-3 family or READY publication."),
            "product_semantics_implicated": False,
        },
        "class_a_harness_correction": {
            "status": "passed-prepare-and-verify-hardware-not-run",
            "fixed_deployment": bind(FIXED / "deployment.json"),
            "fixed_stage": bind(FIXED / "boot-overlay.stage.bin"),
            "first_record": first, "second_record": second,
            "padding_bytes": chain["padding_bytes"],
            "total_bytes": chain["total_bytes"],
            "compiler_runs": 0, "linker_runs": 0,
            "product_byte_changes": 0, "hardware_runs": 0,
        },
        "evidence": {
            "authorization": bind(AUTH),
            "failed_deployment": bind(BAD / "deployment.json"),
            "failed_stage": bind(BAD / "boot-overlay.stage.bin"),
            "screen": bind(BAD / "line1-first-red/screen.png"),
            "low_memory": bind(BAD / "line1-first-red/low-0000-0200.bin"),
            "bank0": bind(BAD / "line1-first-red/bank0-b000-c100.bin"),
            "bank2": bind(BAD / "line1-first-red/bank2-code-plane.bin"),
            "bank3": bind(BAD / "line1-first-red/bank3-boot-family.bin"),
            "deployment_readbacks": readbacks,
        },
        "claims_not_run": [
            "C2-lite product Boot with the corrected two-record deployment",
            "cold and warm latency", "Chip refill timing", "GC block reads",
            "Freezer identity", "nested eval", "RUN/STOP rollback",
            "generation invalidation", "promotion", "acceptance"],
        "next_gate": (
            "Review authorization for one hardware line-1 replay using the "
            "already prepared and SHA-bound two-record deployment; no latency "
            "slot has been consumed."),
    }
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    protect(BAD)
    protect(FIXED)
    return value


if __name__ == "__main__":
    result = build()
    print("c2-lite-v6-bank3-presmoke-harness-first-red: " + result["status"])
