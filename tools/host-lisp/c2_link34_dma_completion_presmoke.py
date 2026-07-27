#!/usr/bin/env python3
"""Build the one non-promotable DMA-completion hardware pre-smoke identity."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link33_bss_triage_product_link as BASE  # noqa: E402
import c2_link34_island_status_latch as STATUS  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / "src/vm_runtime_overlay.c"
CONTRACT = ROOT / "config/c2-runtime-overlay-dma-completion-contract.json"
CONTRACT_DOC = ROOT / "docs/planning/c2.2-runtime-overlay-dma-completion-contract.md"
NEGATIVE = EVIDENCE / (
    "c2.2-product-link34-catalog-verifier-edma-completion-hardware-first-red-"
    "diagnosis.json")
OUT = ROOT / "build/c2.2/substitution/link34-dma-completion-presmoke"
RECEIPT = EVIDENCE / (
    "c2.2-link34-dma-completion-wplto-presmoke-receipt.json")
HARDWARE_OUT = ROOT / "build/c2.2/link34-dma-completion-hardware-presmoke"
HARDWARE_RESULT = HARDWARE_OUT / "hardware-result.json"
DEFINE = "LISP65_RTOV_DMA_COMPLETION_FENCE"
FEATURES = (*BASE.FEATURES, DEFINE)


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"DMA-completion artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def run(command: list[str]) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            check=False)
    if result.returncode:
        raise GateError(
            f"command failed ({result.returncode}): {' '.join(command)}: "
            f"{(result.stderr or result.stdout).strip()}")
    require(not result.stderr.strip(),
            f"unexpected tool diagnostic: {result.stderr.strip()}")
    return result.stdout


def source_gate(text: str) -> dict[str, Any]:
    required_once = (
        "#define RTOV_EDMA_JOB_BYTES 40u",
        "#define RTOV_EDMA_DONE      0xa5u",
        "static volatile uint8_t rtov_edma_complete;",
        "0x04, 0x00, 0x00, 0x00, 0x00,",
        "0x03, 0x01, 0x00, RTOV_EDMA_DONE, 0x00, 0x00,",
        "rtov_edma_job[34] = (uint8_t)target;",
        "rtov_edma_job[35] = (uint8_t)(target >> 8);",
        "rtov_edma_complete = 0;",
        "__asm__ volatile(\"php\\n\\tsei\" ::: \"memory\");",
        "while (rtov_edma_complete != RTOV_EDMA_DONE) { }",
        "__asm__ volatile(\"\" ::: \"memory\");",
        "__asm__ volatile(\"plp\" ::: \"memory\");",
    )
    for token in required_once:
        require(text.count(token) == 1,
                f"DMA-completion source invariant absent/duplicated: {token}")
    require(text.count('"sta $d705\\n\\t"') == 1,
            "target runtime-overlay has other or missing DMA trigger")

    seams = {
        "island-source-crc-chunk":
            "frame->read(file_off, frame->buffer, chunk);",
        "island-carrier-record":
            "frame->read((uint16_t)(LISP65_RUNTIME_OVERLAY_HEADER_SIZE +",
        "island-carrier-payload":
            "frame->read(file_off, RTOV_INSTALL_TARGET, file_len);",
        "catalog-directory-crc-chunk":
            "context->read(relative, context->buffer, chunk);",
        "catalog-header":
            "context->read(0, record, sizeof context->buffer);",
        "record-entry":
            "context->read((uint16_t)(LISP65_RUNTIME_OVERLAY_HEADER_SIZE +",
        "verifier-payload":
            "rtov_read(file_off, (uint8_t *)RTOV_TARGET, file_len);",
        "application-payload":
            "rtov_read(verify.file_off, (uint8_t *)RTOV_TARGET, rtov_loaded_len);",
        "function-pointer-binding": "verify.read = rtov_read;",
    }
    for name, token in seams.items():
        require(text.count(token) == 1,
                f"rtov_read seam inventory drift: {name}")
    return {
        "status": "passed-one-target-transport-nine-consumer-seams",
        "consumer_seams": list(seams),
        "target_trigger_count": 1,
    }


def mutation_matrix(source: str) -> dict[str, str]:
    replacements = {
        "missing-chain": (
            "0x04, 0x00, 0x00, 0x00, 0x00,",
            "0x00, 0x00, 0x00, 0x00, 0x00,"),
        "missing-fill": (
            "0x03, 0x01, 0x00, RTOV_EDMA_DONE, 0x00, 0x00,",
            "0x00, 0x01, 0x00, RTOV_EDMA_DONE, 0x00, 0x00,"),
        "wrong-marker-value": ("#define RTOV_EDMA_DONE      0xa5u",
                               "#define RTOV_EDMA_DONE      0xa4u"),
        "wrong-marker-address": ("rtov_edma_job[34] = (uint8_t)target;",
                                 "rtov_edma_job[33] = (uint8_t)target;"),
        "missing-poll": ("while (rtov_edma_complete != RTOV_EDMA_DONE) { }",
                         "while (0) { }"),
        "missing-memory-barrier": (
            "__asm__ volatile(\"\" ::: \"memory\");",
            "__asm__ volatile(\"nop\");"),
    }
    rejected: dict[str, str] = {}
    for name, (old, new) in replacements.items():
        require(source.count(old) == 1,
                f"mutation anchor drift before test: {name}")
        try:
            source_gate(source.replace(old, new, 1))
        except GateError:
            rejected[name] = "rejected"
        else:
            raise GateError(f"DMA-completion mutation accepted: {name}")
    try:
        source_gate(source + '\n__asm__("sta $d705\\n\\t");\n')
    except GateError:
        rejected["second-direct-trigger"] = "rejected"
    else:
        raise GateError("second direct DMA trigger accepted")
    return rejected


def elf_gate(elf: Path) -> dict[str, Any]:
    table = STATUS.symbols(elf)
    for name in ("rtov_edma_job", "rtov_edma_complete", "rtov_read"):
        require(name in table, f"DMA-completion linked symbol absent: {name}")
    require(table["rtov_edma_job"]["bytes"] == 40,
            "linked DMA list is not the two-job 40-byte chain")
    require(table["rtov_edma_complete"]["bytes"] == 1,
            "linked DMA completion marker is not one byte")
    marker = int(table["rtov_edma_complete"]["address"])
    require(0 <= marker < 0x10000,
            "DMA completion marker is outside CPU-visible Bank 0")
    body = STATUS.function_disassembly(elf, "rtov_read", table).lower()
    for opcode in ("php", "sei", "plp"):
        require(re.search(rf"\b{opcode}\b", body) is not None,
                f"linked rtov_read lacks {opcode}")
    require("$d705" in body and re.search(r"\bbne\b", body),
            "linked rtov_read lacks trigger or completion-poll loop")
    require(f"${marker:x}" in body,
            "linked rtov_read does not reference the registered marker")
    return {
        "status": "passed-linked-two-job-chain-and-poll",
        "job": table["rtov_edma_job"],
        "marker": table["rtov_edma_complete"],
        "critical_region_opcodes": ["php", "sei", "poll-bne", "plp"],
    }


def capacity_gate(capacity: dict[str, Any], baseline: dict[str, Any]) -> None:
    require(capacity["bank0_text_headroom_bytes"] >= 0,
            "DMA completion overflows Bank-0 text")
    require(capacity["ordinary_bank0_bss_headroom_bytes"] >= 0,
            "DMA completion overflows ordinary Bank-0 BSS")
    require(capacity["fixed_hot_block_headroom_bytes"] >= 0,
            "DMA completion overflows the fixed Bank-0 block")
    require(capacity["resident_island_headroom_bytes"] ==
            baseline["resident_island_headroom_bytes"],
            "DMA completion moved the closed resident Island")
    require(capacity["e000"]["actual_headroom_bytes"] == 115,
            "DMA completion moved the final E000 floor")


def prerequisites() -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    negative = json.loads(NEGATIVE.read_text(encoding="utf-8"))
    require(contract.get("status") ==
            "owner-commissioned-contract-then-isolated-hardware-presmoke",
            "DMA completion contract is not commissioned")
    require(negative.get("status") ==
            "FIRST RED: first verifier EDMA payload changes across immediate "
            "sequential CPU CRCs" and negative.get("promotable") is False,
            "bound no-completion hardware negative is absent")
    source = SOURCE.read_text(encoding="utf-8")
    source_result = source_gate(source)
    mutations = mutation_matrix(source)
    return {
        "contract": bind(CONTRACT),
        "contract_document": bind(CONTRACT_DOC),
        "negative_hardware_first_red": bind(NEGATIVE),
        "source": bind(SOURCE),
        "source_gate": source_result,
        "mutations": mutations,
    }


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "DMA-completion pre-smoke identity is one-shot and already exists")
    authority = prerequisites()
    try:
        result = STATUS.full_gate_build(
            OUT, mode="dma-completion-presmoke", features=FEATURES,
            diagnostic_define=DEFINE, diagnostic_gate=elf_gate,
            capacity_gate=capacity_gate)
        result.update({
            "format": "lisp65-c2-link34-dma-completion-wplto-presmoke-v1",
            "status": "passed-nonpromotable-dma-completion-presmoke-hardware-not-run",
            "promotable": False,
            "contract_authority": authority,
            "hardware_negative": {
                "status": "passed-by-bound-prior-first-red",
                "expected_crc16": "0xb47f",
                "observed_crc16": ["0x8e92", "0xe092"],
            },
            "claim_limit": (
                "One fully gated, permanently non-promotable WPLTO identity. "
                "It may run only the isolated positive completion pre-smoke; "
                "it is not the combined product fix or acceptance evidence."),
            "next_gate": (
                "one isolated hardware pre-smoke; first CPU CRC and Island "
                "publication must pass before the combined product link"),
        })
        report = OUT / "dma-completion-wplto-presmoke.json"
        write(report, result)
        receipt = {**result, "report": bind(report),
                   "evidence_file_count": len(STATUS.evidence_tree(OUT))}
        write(RECEIPT, receipt)
        STATUS.protect(OUT, RECEIPT)
        return receipt
    except Exception as error:
        value = {
            "format": "lisp65-c2-link34-dma-completion-wplto-first-red-v1",
            "recorded_on": "2026-07-21",
            "status": "FIRST RED: DMA-completion WPLTO pre-smoke stopped",
            "promotable": False,
            "diagnostic": {"type": type(error).__name__, "message": str(error)},
            "authority": authority,
            "link34_rollback": {**bind(STATUS.LINK34_PRODUCT),
                                "status": "untouched"},
            "next_gate": "stop; no hardware run and no product link",
        }
        write(RECEIPT, value)
        if OUT.exists():
            STATUS.protect(OUT, RECEIPT)
        else:
            os.chmod(RECEIPT, 0o444)
        return value


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "DMA-completion pre-smoke receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") ==
            "passed-nonpromotable-dma-completion-presmoke-hardware-not-run",
            "DMA-completion pre-smoke identity is not green/hardware-not-run")
    for row in value["product_identity"].values():
        require(bind(ROOT / row["path"]) == row,
                f"DMA-completion bound identity drift: {row['path']}")
    return value


def evaluate_hardware() -> dict[str, Any]:
    link = check()
    deployment = HARDWARE_OUT / "deployment.json"
    low_path = HARDWARE_OUT / "presmoke-low-0000-1fff.bin"
    require(deployment.is_file() and low_path.is_file()
            and low_path.stat().st_size == 0x2000,
            "DMA-completion hardware captures are incomplete")
    elf = ROOT / link["product_identity"]["elf"]["path"]
    table = STATUS.symbols(elf)
    low = low_path.read_bytes()

    def byte(name: str) -> int:
        address = int(table[name]["address"])
        require(0 <= address < len(low),
                f"DMA-completion symbol outside capture: {name}")
        return low[address]

    observed = {
        "completion_marker": byte("rtov_edma_complete"),
        "runtime_fault": byte("rtov_fault"),
        "runtime_busy": byte("rtov_busy"),
        "island_state": byte("rtov_island_state"),
    }
    require(observed == {
                "completion_marker": 0xa5,
                "runtime_fault": 0,
                "runtime_busy": 0,
                "island_state": 2,
            }, f"DMA-completion positive pre-smoke failed: {observed}")
    result = {
        "format": "lisp65-c2-link34-dma-completion-hardware-presmoke-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-receipt-less-positive-completion-prefilter",
        "promotable": False,
        "observed": observed,
        "proof": {
            "negative_without_boundary": ["0x8e92", "0xe092"],
            "positive_first_consumer": (
                "catalog-verifier CRC passed, Island published READY and no "
                "runtime fault latched"),
            "completion_marker": "0xa5 from the chained one-byte FILL",
        },
        "deployment": bind(deployment),
        "low_capture": bind(low_path),
        "diagnostic_identity": bind(RECEIPT),
        "execution_accounting": {
            "positive_hardware_runs": 1,
            "product_links": 0,
            "product_presmoke_runs": 0,
        },
        "claim_limit": (
            "Receipt-less hardware prefilter of the completion boundary only. "
            "It is not a product candidate, acceptance, promotion or latency claim."),
        "next_gate": "combined completion plus first-status-wins product link",
    }
    write(HARDWARE_RESULT, result)
    for path in HARDWARE_OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "selftest", "build", "check", "evaluate-hardware"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            result = prerequisites()
            print("c2-link34-dma-completion-presmoke: SELFTEST PASS mutations="
                  + str(len(result["mutations"])))
            return 0
        if args.action == "build":
            result = build()
        elif args.action == "check":
            result = check()
        else:
            result = evaluate_hardware()
        print("c2-link34-dma-completion-presmoke: " + result["status"])
        return 3 if result["status"].startswith("FIRST RED") else 0
    except (GateError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print("c2-link34-dma-completion-presmoke: FAIL: " + str(error),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
