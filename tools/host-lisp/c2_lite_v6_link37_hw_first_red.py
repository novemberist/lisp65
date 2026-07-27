#!/usr/bin/env python3
"""Bind the Link-37 C2-lite line-1 hardware First Red."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
HW = ROOT / "build/c2.2/hardware-presmoke-link37-c2-lite-v6"
LINK = ROOT / (
    "build/c2.2/substitution/product-link-37-c2-lite-v6-artifact-resume2")
AUTH = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link37-c2-lite-v6-artifact-resume2-structural-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link37-c2-lite-v6-hardware-first-red-diagnosis.json")
DEPLOY = HW / "deployment.json"
SCREEN = HW / "line1/screen.txt"
RTOV = LINK / "generated-product-sources/vm_runtime_overlay.c"
PRODUCT_RUNTIME = LINK / "generated-product-sources/c2_product_runtime.c"
ADDENDUM = ROOT / "docs/planning/c2-lite-execution-contract-addendum.md"
MEMO = ROOT / "docs/planning/c2-lite-rebuild-memo.md"


class DiagnosisError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DiagnosisError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, object]:
    require(path.is_file(), f"evidence absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def function(source: str, name: str) -> str:
    match = re.search(r"\b" + re.escape(name) + r"\s*\([^;]*?\)\s*\{", source)
    require(match is not None, f"function absent: {name}")
    brace = source.index("{", match.start())
    depth = 0
    for index in range(brace, len(source)):
        depth += source[index] == "{"
        depth -= source[index] == "}"
        if depth == 0:
            return source[match.start():index + 1]
    raise DiagnosisError(f"unterminated function: {name}")


def protect(path: Path) -> None:
    for item in sorted(path.rglob("*"), reverse=True):
        if item.is_file():
            os.chmod(item, 0o444)
        elif item.is_dir():
            os.chmod(item, 0o555)
    os.chmod(path, 0o555)


def build() -> dict[str, object]:
    require(not RECEIPT.exists(), "Link-37 hardware First Red already recorded")
    deployment = json.loads(DEPLOY.read_text(encoding="utf-8"))
    authorization = json.loads(AUTH.read_text(encoding="utf-8"))
    require(deployment["status"] == "ready-receipt-less"
            and deployment["product"]["sha256"]
                == "fffa5fdf518763001c840e416c1f448ac7f32a80e0e4f28330a5fab50a15157a"
            and authorization["status"]
                == "passed-new-c2-lite-product-identity-hardware-not-run",
            "Link-37 deployment/authorization identity drift")
    screen = SCREEN.read_text(encoding="utf-8", errors="replace")
    require("E2f runtime island invalid; redeploy" in screen,
            "line-1 screen does not contain the observed First Red")
    readbacks = []
    for row in deployment["preloads"]:
        source = ROOT / row["path"]
        readback = HW / ("readback-" + source.name)
        require(readback.is_file() and readback.read_bytes() == source.read_bytes(),
                f"deployment readback drift: {source.name}")
        readbacks.append(bind(readback))

    rtov = RTOV.read_text(encoding="utf-8")
    runtime = PRODUCT_RUNTIME.read_text(encoding="utf-8")
    read = function(rtov, "rtov_read")
    select = function(rtov, "vm_runtime_overlay_select_family")
    prepare = function(runtime, "c2_product_prepare_boot")
    findings = {
        "hot_overlay_reader_uses_chip_bank3":
            "c2_facade_vm_code_load(3u" in read,
        "boot_preparation_selects_family":
            "c2_facade_select_family" in prepare,
        "family_selection_publishes_without_stage":
            "rtov_family = family" in select
            and "rtov_family_generation = generation" in select
            and "c2_dma_copy" not in select
            and "vm_code_load" not in select,
        "no_product_bank3_stage_symbol":
            "stage_bank3" not in rtov and "stage_bank3" not in runtime,
        "historic_deployment_loaded_boot_family_only_to_attic":
            any(row["address"] == "0x08200000"
                and row["path"].endswith("runtime-overlays-boot-final.bin")
                for row in deployment["preloads"])
            and not any(row["address"] == "0x00030000"
                        for row in deployment["preloads"]),
    }
    require(all(findings.values()), f"root-cause closure drift: {findings}")
    addendum = ADDENDUM.read_text(encoding="utf-8")
    memo = MEMO.read_text(encoding="utf-8")
    require("Bank 3 is staged by family" in addendum
            and "complete packed family is destination-verified" in addendum
            and "Boot to banner/REPL, including static Chip-plane staging"
                in memo,
            "C2-lite staging contract citation drift")
    value = {
        "format": "lisp65-c2-lite-v6-link37-hardware-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "first-red-receipt-less-hardware-presmoke-stopped-at-line-1",
        "promotable": False,
        "candidate": authorization["product_identity"],
        "hardware": {
            "runs": 1,
            "completed_latency_attempts": 0,
            "two_attempt_rule_slots_consumed": 0,
            "line_reached": 1,
            "visible_result": "E2f runtime island invalid; redeploy",
            "deployment_readbacks": len(readbacks),
            "all_preloads_byte_identical": True,
        },
        "evidence": {
            "deployment": bind(DEPLOY),
            "screen_text": bind(SCREEN),
            "screen_png": bind(HW / "line1/screen.png"),
            "authorization": bind(AUTH),
            "readbacks": readbacks,
            "runtime_overlay_source": bind(RTOV),
            "product_runtime_source": bind(PRODUCT_RUNTIME),
        },
        "diagnosis": {
            "class": "product-semantics-and-stage-before-publish",
            "findings": findings,
            "cause": (
                "The C2-lite runtime reader consumes the active family from "
                "Chip Bank 3, but the product's Boot-family transition only "
                "wipes and publishes family/generation. It never stages and "
                "destination-verifies the Boot family in Bank 3. The old "
                "hardware deployment correctly exposes the missing product "
                "operation by supplying only the cold Attic source."),
            "forbidden_harness_workaround": (
                "Preloading Bank 3 externally would bypass the contract's "
                "product-side initial staging row and cannot turn this run green."),
            "structural_proof_gap": (
                "The prior stage-before-publish gate proved the model and "
                "publication source order but did not require a linked "
                "Boot-family Attic-to-Bank-3 transfer before publication."),
        },
        "contract": {
            "bank3_rule": (
                "Bank 3 is staged by family; the complete packed family is "
                "destination-verified before family/generation publishes."),
            "presmoke_line_1": (
                "Boot to banner/REPL, including static Chip-plane staging."),
        },
        "claims_not_run": [
            "boot-to-REPL pass", "cold first-call latency",
            "warm second-call latency", "bytecode/native refill timing",
            "GC block reads and frame cost", "Freezer identity",
            "nested eval", "RUN/STOP rollback", "generation invalidation",
            "promotion", "acceptance"],
        "rollback_line": {
            "link35_product_sha256":
                "54c731559fdb72d5d1cb8478b9da7e78a422741e4e5267d64b07fe4c6f763a65",
            "status": "untouched"},
        "next_gate": (
            "Class-C review of product-side Boot/Session Bank-3 staging and "
            "its linked stage-before-publish gate; no hardware retry."),
    }
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    protect(HW)
    return value


if __name__ == "__main__":
    result = build()
    print("c2-lite-v6-link37-hw-first-red: " + result["status"])
