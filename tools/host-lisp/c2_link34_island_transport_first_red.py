#!/usr/bin/env python3
"""Bind the Link-34 diagnostic latch's catalog-verifier transport First Red."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
HW = ROOT / "build/c2.2/link34-island-status-latch-hardware"
LINK = ROOT / "build/c2.2/substitution/link34-island-status-latch-diagnostic"
RESULT = HW / "hardware-result.json"
DEPLOYMENT = HW / "deployment.json"
LOW = HW / "diagnostic-low-0000-1fff.bin"
BOOT = HW / "diagnostic-boot-family.bin"
POST = HW / "post-stop-binding-and-edma.bin"
WINDOW = HW / "post-stop-runtime-window.bin"
BINDING = LINK / "runtime-overlay-verifier-bindings.bin"
MANIFEST = LINK / "runtime-overlays-boot-final.json"
LINK_RECEIPT = EVIDENCE / (
    "c2.2-link34-island-status-latch-diagnostic-link-receipt.json")
OUTPUT = EVIDENCE / (
    "c2.2-product-link34-catalog-verifier-transport-hardware-first-red-diagnosis.json")

EXPECTED = {
    RESULT: "150d152eaa8f8764d0ce2e1f2c52b6fe66034ec36fe9759669ebdd10006b8b82",
    DEPLOYMENT: "f996db93f6802e1f345c21b627ac6a286b58fc75a065f77839aa0ccf338d2708",
    LOW: "d263366f9c917de78d25714f674bbcfc7903c48ff196b779b90e5578f60d5412",
    BOOT: "25a95c48fc947becdf687e1484f2d46936ac5aefc74ab4eccaf018c6f2223ed8",
    POST: "616c76317f810382ea9dc9924491fbf68f63060e40b9206e29eb08dfd6dc51c9",
    WINDOW: "6bed6ecd7fb8a2ef5778c39309a072b28fd839f212be56b3537c590866129ce7",
    BINDING: "7445c0d182712106ca00f50892116fa23d1d73e60cc1c17da73acfb640b51fc4",
    LINK_RECEIPT: "586dc0d1e86e3c55f65ed7f2cbb827f09eabb31b42a0dd9d7592a3c25073e643",
}


class DiagnosisError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DiagnosisError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"diagnosis artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def diagnose() -> dict[str, Any]:
    require(not OUTPUT.exists(), "catalog-verifier transport diagnosis already exists")
    for path, digest in EXPECTED.items():
        require(path.is_file() and sha(path) == digest,
                f"catalog-verifier diagnosis input drift: {path}")
    hardware = json.loads(RESULT.read_text(encoding="utf-8"))
    deployment = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    latched = hardware["latched"]
    require(latched == {
        "busy": 0,
        "failure_class": "tuple-payload-crc-before-verifier",
        "inner_status": 15,
        "inner_status_name": "ERR_CRC",
        "island_state": 3,
        "loaded_len_before_wipe": 1156,
        "outer_fault": 20,
        "outer_fault_name": "ERR_ISLAND",
        "verifier": "catalog",
        "verifier_index": 0,
    }, "diagnostic latch result is not the exact catalog tuple-CRC First Red")
    row = manifest["slices"][0]
    require(row["name"] == "catalog-verifier"
            and row["file_offset"] == 0x200
            and row["file_size"] == 0x484
            and row["crc16"] == 0xCE8C,
            "diagnostic catalog-verifier manifest geometry drift")
    boot_binding = next(item for item in deployment["preloads"]
                        if item["address"] == "0x08200000")
    require(bind(BOOT)["sha256"] == boot_binding["sha256"]
            and bind(BOOT)["bytes"] == boot_binding["bytes"],
            "post-stop Boot-family bytes differ from deployment")
    binding = BINDING.read_bytes()
    post = POST.read_bytes()
    require(post[0x14:0x34] == binding,
            "live verifier binding table differs from post-link bytes")
    expected_job = bytes([
        0x0B, 0x80, 0x82, 0x81, 0x00, 0x85, 0x01, 0x00,
        0x00, 0x84, 0x04, 0x00, 0x02, 0x00, 0x56, 0xC3,
        0x00, 0x00, 0x00, 0x00,
    ])
    require(post[0x36:0x4A] == expected_job,
            "post-stop Enhanced-DMA descriptor differs from catalog transfer")
    require(not any(WINDOW.read_bytes()),
            "fail-closed runtime window was not completely wiped")
    value = {
        "format": "lisp65-c2-link34-catalog-verifier-transport-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: catalog-verifier tuple payload CRC before verifier entry",
        "promotable": False,
        "hardware_observation": latched,
        "transport_binding": {
            "source_physical": "0x08200200",
            "source_base": "0x08200000",
            "source_relative": "0x0200",
            "destination_cpu": "0xc356",
            "bytes": 1156,
            "expected_crc16": "0xce8c",
            "verifier_binding_table_live_byte_identical": True,
            "enhanced_dma_descriptor_live": expected_job.hex(),
            "enhanced_dma_descriptor_matches_manifest": True,
            "source_boot_family_post_stop_byte_identical": True,
            "destination_after_cleanup": "1156 zero bytes",
        },
        "localization": {
            "ruled_out": [
                "hand-written CRC leaf semantics on the canonical and five exact Link-34 inputs",
                "Boot-family deployment corruption",
                "verifier tuple offset/length/expected-CRC binding drift",
                "Enhanced-DMA descriptor address/count construction",
                "catalog-verifier semantic rejection",
                "record-verifier and resident-Island installer entry",
            ],
            "remaining_boundary": (
                "the actual bytes/CPU view produced at 0xc356 by the first "
                "Enhanced-DMA transfer, including completion ordering"),
            "not_yet_known": (
                "the observed pre-wipe CRC and pre-wipe destination bytes"),
        },
        "error_path_followup": {
            "finding": (
                "vm_runtime_overlay_install_island overwrites the first, specific "
                "transport status ERR_CRC with generic ERR_ISLAND/E2f"),
            "permanent_rule": (
                "the first innermost status wins; outer layers may add context "
                "but must never replace it"),
            "implementation": "not authorized and not attempted",
        },
        "bounded_next_probe": {
            "authorization": "not granted by this diagnosis",
            "kind": "diagnostic-only observed-CRC latch at the tuple-CRC comparison",
            "state_budget": "reuse the same four diagnostic bytes; no new state",
            "purpose": (
                "preserve the actual CRC computed over 0xc356 before wipe; compare "
                "against expected 0xce8c, all-zero 0xba75 and all-ff 0x5aee"),
            "limits": [
                "capacity/placement first",
                "non-promotable identity only",
                "at most one separately authorized hardware run",
                "no product fix or successor product link",
            ],
        },
        "execution_accounting": {
            "diagnostic_hardware_runs": 1,
            "product_presmoke_retries": 0,
            "promotable_product_links": 0,
            "post_stop_read_only_captures": 2,
        },
        "evidence": {
            "diagnostic_link": bind(LINK_RECEIPT),
            "hardware_result": bind(RESULT),
            "deployment": bind(DEPLOYMENT),
            "low_capture": bind(LOW),
            "boot_family_capture": bind(BOOT),
            "live_binding_and_dma_capture": bind(POST),
            "wiped_runtime_window_capture": bind(WINDOW),
            "verifier_binding_table": bind(BINDING),
            "boot_manifest": bind(MANIFEST),
        },
        "claim_limit": (
            "One owner-authorized non-promotable diagnostic hardware run plus "
            "read-only post-stop captures. It localizes the First Red but is not "
            "a fix, product hardware acceptance, promotion, latency evidence or "
            "authorization for another run."),
        "next_gate": "return exact transport First Red for review; no automatic fix",
    }
    OUTPUT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    OUTPUT.chmod(0o444)
    return value


def main() -> int:
    try:
        value = diagnose()
        print("c2-link34-island-transport-first-red: " + value["status"])
        return 0
    except (DiagnosisError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-link34-island-transport-first-red: FAIL: " + str(error),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
