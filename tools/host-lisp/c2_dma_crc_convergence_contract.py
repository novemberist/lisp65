#!/usr/bin/env python3
"""Prove the C2 runtime-overlay CRC-convergence contract and seam inventory."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/c2-runtime-overlay-dma-completion-contract.json"
DOCUMENT = ROOT / "docs/planning/c2.2-runtime-overlay-dma-completion-contract.md"
SOURCE = ROOT / "src/vm_runtime_overlay.c"
UPSTREAM = ROOT / "docs/upstream-findings.md"
HARDWARE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link35-hold-before-wipe-cycle2-hardware-receipt.json")
HARDWARE_SHA = "e8ac3f794d8d8030d15c84b9885c134833faad096420580e99a734d55d291fb6"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-runtime-overlay-crc-convergence-contract-probe-receipt.json")

EXPECTED_CRC = 0xE856
TIMEOUT_FRAMES = 64
FRAME_HZ = 50
TIMEOUT_STATUS = "VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT"

SEAM_TOKENS = {
    "catalog-header": "context->read(0, record, sizeof context->buffer);",
    "catalog-directory-chunks":
        "context->read(relative, context->buffer, chunk);",
    "requested-record-entry":
        "context->read((uint16_t)(LISP65_RUNTIME_OVERLAY_HEADER_SIZE +",
    "catalog-verifier-payload":
        "rtov_read(file_off, (uint8_t *)RTOV_TARGET, file_len);",
    "record-verifier-payload":
        "rtov_read(file_off, (uint8_t *)RTOV_TARGET, file_len);",
    "application-payload":
        "rtov_read(verify.file_off, (uint8_t *)RTOV_TARGET, rtov_loaded_len);",
    "island-carrier-record":
        "frame->read((uint16_t)(LISP65_RUNTIME_OVERLAY_HEADER_SIZE +",
    "island-source-crc-chunks":
        "frame->read(file_off, frame->buffer, chunk);",
    "island-carrier-destination":
        "frame->read(file_off, RTOV_INSTALL_TARGET, file_len);",
}


class ContractError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"contract input absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def convergence(samples: list[tuple[int, int]], start: int,
                expected: int = EXPECTED_CRC,
                limit: int = TIMEOUT_FRAMES) -> dict[str, Any]:
    require(samples, "convergence sequence is empty")
    for frame, observed in samples:
        elapsed = (frame - start) & 0xffff
        if observed == expected:
            return {"status": "complete", "elapsed_frames": elapsed,
                    "crc16": f"0x{observed:04x}"}
        if elapsed >= limit:
            return {"status": "completion-timeout",
                    "error": TIMEOUT_STATUS,
                    "elapsed_frames": elapsed,
                    "crc16": f"0x{observed:04x}"}
    return {"status": "pending",
            "elapsed_frames": (samples[-1][0] - start) & 0xffff}


def model_cases() -> dict[str, Any]:
    cases = {
        "immediate-match": convergence([(100, EXPECTED_CRC)], 100),
        "observed-match-at-35-frames": convergence(
            [(100, 0xE8D8), (135, EXPECTED_CRC)], 100),
        "mismatch-at-63-then-match-at-64": convergence(
            [(163, 0x1111), (164, EXPECTED_CRC)], 100),
        "mismatch-at-64-timeout": convergence([(164, 0x1111)], 100),
        "uint16-frame-wrap": convergence(
            [(0xfffe, 0x1111), (0x001e, EXPECTED_CRC)], 0xfffe),
        "marker-with-wrong-content": convergence([(101, 0xA500)], 100),
    }
    require(cases["immediate-match"]["status"] == "complete"
            and cases["immediate-match"]["elapsed_frames"] == 0,
            "immediate convergence model drift")
    require(cases["observed-match-at-35-frames"]["status"] == "complete"
            and cases["observed-match-at-35-frames"]["elapsed_frames"] == 35,
            "observed convergence model drift")
    require(cases["mismatch-at-63-then-match-at-64"]["status"] == "complete"
            and cases["mismatch-at-63-then-match-at-64"]["elapsed_frames"] == 64,
            "CRC-before-timeout edge order drift")
    require(cases["mismatch-at-64-timeout"]["status"] == "completion-timeout"
            and cases["mismatch-at-64-timeout"]["error"] == TIMEOUT_STATUS,
            "specific timeout model drift")
    require(cases["uint16-frame-wrap"]["status"] == "complete"
            and cases["uint16-frame-wrap"]["elapsed_frames"] == 32,
            "modulo frame model drift")
    require(cases["marker-with-wrong-content"]["status"] == "pending",
            "marker was incorrectly accepted as content completion")
    return cases


def validate_contract(config: dict[str, Any]) -> dict[str, Any]:
    require(config.get("format") ==
            "lisp65-c2-runtime-overlay-dma-completion-contract-v2",
            "completion contract version drift")
    require(config.get("status") ==
            "owner-approved-crc-convergence-contract-probe-product-not-implemented",
            "completion contract status drift")
    protocol = config["completion_protocol"]
    require(protocol["kind"] == "frame-bounded-authoritative-crc-convergence"
            and protocol["transport_return_meaning"] == "destination-untrusted"
            and protocol["marker_meaning"] ==
                "job-acceptance-and-ordering-witness-only",
            "content-over-signal rule drift")
    require(protocol["frame_source"] == "c2_kernal_frame_count"
            and protocol["frame_hz"] == FRAME_HZ
            and protocol["timeout_frames"] == TIMEOUT_FRAMES
            and protocol["timeout_status"] == TIMEOUT_STATUS,
            "frame-bound timeout contract drift")
    require(protocol["observed_upper_bound_ms"] == 691
            and protocol["observed_quantized_frames"] == 35
            and protocol["margin_frames_after_quantized_observation"] == 29
            and protocol["margin_ms_after_raw_observation"] == 589,
            "timeout derivation drift")
    seams = config["covered_seams"]
    require(len(seams) == 9 and {row["id"] for row in seams} == set(SEAM_TOKENS),
            "nine-seam contract inventory drift")
    dispositions = {row["id"]: row["disposition"] for row in seams}
    require("remove-standalone-read" in dispositions["requested-record-entry"]
            and "remove-standalone-read" in dispositions["island-carrier-record"],
            "record seam was exempted rather than eliminated")
    require(config["record_read_rule"][
                "standalone_record_reads_after_directory_authentication"] ==
            "forbidden"
            and config["record_read_rule"]["second_record_buffer"] == "forbidden",
            "record capture single-source rule drift")
    require(config["contract_model"]["product_source_status"] ==
            "inventory-only-not-implemented",
            "contract probe overclaims a product implementation")
    core = config["documented_semantics"]["tested_device_core_identity"]
    require(core["status"] == "missing-mandatory-before-upstream-submission"
            and set(core["next_reproduction_fields"]) == {
                "core-id", "core-version", "bitstream-build-or-release",
                "device-model"},
            "mandatory L10 core-identity gate drift")
    return {"status": "passed-crc-convergence-contract",
            "seam_count": len(seams), "timeout_frames": TIMEOUT_FRAMES,
            "timeout_status": TIMEOUT_STATUS}


def source_inventory(source: str) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for seam, token in SEAM_TOKENS.items():
        count = source.count(token)
        if seam in ("catalog-verifier-payload", "record-verifier-payload"):
            require(count == 1,
                    "the shared verifier-payload seam is not unique")
        else:
            require(count == 1, f"source seam inventory drift: {seam}={count}")
        counts[seam] = count
    require(source.count("static void rtov_read(") == 2,
            "rtov_read declaration/definition inventory drift")
    require(source.count("verify.read = rtov_read;") == 1,
            "rtov_read function-pointer binding drift")
    return {
        "status": "passed-current-nine-seam-source-inventory",
        "seams": counts,
        "function_pointer_binding": 1,
        "standalone_record_reads_pending_removal": [
            "requested-record-entry", "island-carrier-record"],
        "product_implementation": "not-present",
    }


def mutation_matrix(config: dict[str, Any]) -> dict[str, str]:
    mutations: dict[str, dict[str, Any]] = {}
    value = copy.deepcopy(config)
    value["completion_protocol"]["timeout_frames"] = 63
    mutations["timeout-63"] = value
    value = copy.deepcopy(config)
    value["completion_protocol"]["frame_source"] = "delay-loop"
    mutations["foreign-frame-source"] = value
    value = copy.deepcopy(config)
    value["completion_protocol"]["timeout_status"] = "VM_RUNTIME_OVERLAY_ERR_ISLAND"
    mutations["generic-timeout-status"] = value
    value = copy.deepcopy(config)
    value["completion_protocol"]["marker_meaning"] = "completion-boundary"
    mutations["marker-as-completion"] = value
    value = copy.deepcopy(config)
    value["covered_seams"] = value["covered_seams"][:-1]
    mutations["missing-seam"] = value
    value = copy.deepcopy(config)
    value["record_read_rule"][
        "standalone_record_reads_after_directory_authentication"] = "allowed"
    mutations["standalone-record-read"] = value
    value = copy.deepcopy(config)
    value["documented_semantics"]["tested_device_core_identity"]["status"] = "optional"
    mutations["optional-core-identity"] = value
    rejected: dict[str, str] = {}
    for name, candidate in mutations.items():
        try:
            validate_contract(candidate)
        except ContractError:
            rejected[name] = "rejected"
        else:
            raise ContractError(f"contract mutation accepted: {name}")
    return rejected


def documentation_gate(document: str, upstream: str) -> dict[str, Any]:
    required_document = (
        "LISP65_RTOV_COMPLETION_TIMEOUT_FRAMES = 64",
        "VM_RUNTIME_OVERLAY_ERR_COMPLETION_TIMEOUT",
        "The content check precedes the timeout check.",
        "The current source has nine `rtov_read -> consumer` seams.",
        "no second record buffer",
        "core identity was not captured",
    )
    for token in required_document:
        require(token in document, f"contract prose token absent: {token}")
    required_upstream = (
        "### L10 — Enhanced-DMA returns before an Attic-sourced target is stable",
        "| 1 ms | `$e8d8` | 1,133 |",
        "| 691 ms | `$e856` | 0 |",
        "core ID",
        "version/build and device model",
    )
    for token in required_upstream:
        require(token in upstream, f"L10 measurement token absent: {token}")
    return {"status": "passed-contract-and-L10-documentation-gate",
            "contract_tokens": len(required_document),
            "upstream_tokens": len(required_upstream)}


def build() -> dict[str, Any]:
    require(not RECEIPT.exists(), "CRC-convergence contract receipt already exists")
    require(sha(HARDWARE) == HARDWARE_SHA,
            "Class-B cycle-2 hardware authority drift")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    hardware = json.loads(HARDWARE.read_text(encoding="utf-8"))
    require(hardware.get("status") == "answered-E2f-completion-convergence",
            "Class-B cycle-2 did not answer E2f")
    contract = validate_contract(config)
    inventory = source_inventory(SOURCE.read_text(encoding="utf-8"))
    model = model_cases()
    mutations = mutation_matrix(config)
    docs = documentation_gate(DOCUMENT.read_text(encoding="utf-8"),
                              UPSTREAM.read_text(encoding="utf-8"))
    value = {
        "format": "lisp65-c2-runtime-overlay-crc-convergence-contract-probe-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-crc-convergence-contract-product-not-implemented",
        "authority": {
            "config": bind(CONFIG), "contract": bind(DOCUMENT),
            "class_b_cycle2_hardware": bind(HARDWARE),
            "upstream_register": bind(UPSTREAM),
        },
        "contract_gate": contract,
        "model_cases": model,
        "source_inventory": inventory,
        "documentation_gate": docs,
        "negative_matrix": mutations,
        "timeout_derivation": {
            "observed_upper_bound_ms": 691,
            "observed_quantized_frames": 35,
            "bound_frames": 64,
            "bound_nominal_ms": 1280,
            "margin_frames": 29,
            "margin_ms_over_raw_observation": 589,
        },
        "capacity": "not-run; no estimate is an authorization",
        "claim_limit": (
            "Contract, model and source inventory only: zero product bytes, "
            "zero compiler/product links and zero hardware runs."),
        "execution_accounting": {
            "product_bytes": 0, "compiler_runs": 0,
            "product_links": 0, "hardware_runs": 0,
            "host_model_cases": len(model),
            "contract_mutations_rejected": len(mutations),
        },
        "next_gate": (
            "Class-C Whole-Program capacity/placement probe for the common "
            "convergence driver, record capture and specific timeout path; "
            "no product link is authorized by this receipt."),
    }
    write_json(RECEIPT, value)
    os.chmod(RECEIPT, 0o444)
    return value


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "CRC-convergence contract receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") ==
            "passed-crc-convergence-contract-product-not-implemented",
            "CRC-convergence contract receipt is not green")
    for row in value["authority"].values():
        require(bind(ROOT / row["path"]) == row,
                f"contract authority drift: {row['path']}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "selftest"))
    args = parser.parse_args()
    try:
        if args.action == "build":
            value = build()
        elif args.action == "check":
            value = check()
        else:
            config = json.loads(CONFIG.read_text(encoding="utf-8"))
            validate_contract(config)
            model_cases()
            mutation_matrix(config)
            source_inventory(SOURCE.read_text(encoding="utf-8"))
            documentation_gate(DOCUMENT.read_text(encoding="utf-8"),
                               UPSTREAM.read_text(encoding="utf-8"))
            value = {"status": "SELFTEST PASS"}
        print("c2-dma-crc-convergence: " + value["status"])
        return 0
    except Exception as error:
        print("c2-dma-crc-convergence: FAIL " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
