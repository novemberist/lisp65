#!/usr/bin/env python3
"""Bind Link 34's receipt-less runtime-Island hardware First Red."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_crc_asm_leaf_gate as ASM  # noqa: E402
import c2_crc_codegen_gate as CODEGEN  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


PRODUCT_DIR = ROOT / "build/c2.2/substitution/product-link-34-crc-asm-leaf"
HW_DIR = ROOT / "build/c2.2/hardware-presmoke-link34-crc-asm-leaf"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
STRUCTURAL = EVIDENCE / "c2.2-product-link34-crc-asm-leaf-structural-receipt.json"
OUTPUT = EVIDENCE / "c2.2-product-link34-runtime-island-hardware-first-red-diagnosis.json"
PRODUCT = PRODUCT_DIR / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
BOOT = PRODUCT_DIR / "runtime-overlays-boot-final.bin"
MANIFEST = PRODUCT_DIR / "runtime-overlays-boot-final.json"
DEPLOYMENT = HW_DIR / "deployment.json"
LOW_CAPTURE = HW_DIR / "first-red-low-0000-1fff.bin"
FIXED_CAPTURE = HW_DIR / "first-red-fixed-state-bf80-c07f.bin"
BOOT_CAPTURE = HW_DIR / "first-red-boot-family.bin"
MAP = Path(str(PRODUCT) + ".map")

EXPECTED = {
    STRUCTURAL: "b4610ac561b576f85bdbb7491bcb0bec79974edeef1a4c691657adf313d67509",
    PRODUCT: "bef7708baa12b8e23094c2150a53f5bee529be25b9b9e11d0d68a3191ee6a485",
    ELF: "cfbd1f7420c5b0a5bbf80408e7ec39c2b6237d35d3e930a1eb2b219ebb9dadf4",
    BOOT: "cb9f47b8f1c8a924aee4852ee8ba544f1d316211cbd8b2855ee3cf49f778ef19",
    LOW_CAPTURE: "46def544a895cf4cc5d044a43dde04bb15f15ab3b79b0678c1844cb55ec04c61",
    FIXED_CAPTURE: "8e21943864dc4ba12132d5664e4f4c504ec2c4a554d5aee27aa859f7bb00e071",
    BOOT_CAPTURE: "cb9f47b8f1c8a924aee4852ee8ba544f1d316211cbd8b2855ee3cf49f778ef19",
}


class DiagnosisError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DiagnosisError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"evidence absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def linked_leaf_rows() -> tuple[list[dict[str, Any]], dict[str, int], dict[str, Any]]:
    truth = ElfTruth.read(
        ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    leaf = truth.symbol(CODEGEN.CRC)
    rc = {name: truth.symbol(name).value for name in
          ("__rc2", "__rc3", "__rc4", "__rc5", "__rc6", "__rc7")}
    completed = subprocess.run(
        [str(ROOT / "tools/llvm-mos/bin/llvm-objdump"), "-d",
         "--no-show-raw-insn", str(ELF)], check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    rows = [row for row in CODEGEN.disassembly_rows(completed.stdout)
            if row["section"] == leaf.section
            and leaf.value <= int(row["address"]) < leaf.value + leaf.bytes]
    return rows, rc, {
        "address": leaf.value,
        "bytes": leaf.bytes,
        "section": leaf.section,
        "symbol_type": leaf.symbol_type,
    }


def exact_payload_parity() -> dict[str, Any]:
    rows, rc, leaf = linked_leaf_rows()
    boot = BOOT.read_bytes()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cases: list[tuple[str, bytes, int]] = []
    header = bytearray(boot[:32])
    expected = int.from_bytes(header[26:28], "little")
    header[26:28] = b"\0\0"
    cases.append(("catalog-header", bytes(header), expected))
    for slot in (0, 1, 8, 9):
        row = manifest["slices"][slot]
        begin = int(row["file_offset"])
        end = begin + int(row["file_size"])
        cases.append((str(row["name"]), boot[begin:end], int(row["crc16"])))
    results: dict[str, Any] = {}
    for name, payload, expected_crc in cases:
        reference = ASM.crc_reference(payload)
        executed = ASM.execute(rows, rc=rc, data=payload)
        require(reference == expected_crc == executed["crc"],
                f"exact operational CRC parity failed for {name}")
        results[name] = {
            "bytes": len(payload),
            "manifest_crc16": expected_crc,
            "portable_reference_crc16": reference,
            "final_elf_interpreter_crc16": executed["crc"],
            "executed_instructions": executed["steps"],
            "status": "passed-host-only-exact-operational-payload",
        }
    return {"leaf": leaf, "abi_zero_page": rc, "cases": results}


def run() -> dict[str, Any]:
    require(not OUTPUT.exists(), "Link-34 hardware First-Red diagnosis already exists")
    for path, expected in EXPECTED.items():
        require(sha(path) == expected, f"bound evidence drift: {path}")
    require(BOOT_CAPTURE.read_bytes() == BOOT.read_bytes(),
            "post-failure Boot-family capture differs from deployed bytes")
    structural = json.loads(STRUCTURAL.read_text(encoding="utf-8"))
    require(structural.get("status") ==
            "passed-new-product-identity-hardware-not-run",
            "Link-34 structural receipt is not the accepted prerequisite")
    deployment = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    require(deployment["product"]["sha256"] == EXPECTED[PRODUCT]
            and deployment["status"] == "ready-receipt-less",
            "hardware deployment does not bind Link 34")
    low = LOW_CAPTURE.read_bytes()
    require(len(low) == 8192 and not any(low[0x1800:0x2000]),
            "failed Island was not completely wiped")
    state = {
        "rtov_call_context": int.from_bytes(low[0x6e:0x70], "little"),
        "rtov_call_result_or_install_target": int.from_bytes(
            low[0x70:0x72], "little"),
        "rtov_family": low[0x77],
        "rtov_island_state": low[0x78],
        "rtov_loaded_len": int.from_bytes(low[0x79:0x7b], "little"),
        "rtov_busy": low[0x7b],
        "rtov_fault": low[0x7c],
    }
    require(state == {
        "rtov_call_context": 0,
        "rtov_call_result_or_install_target": 0,
        "rtov_family": 1,
        "rtov_island_state": 3,
        "rtov_loaded_len": 0,
        "rtov_busy": 0,
        "rtov_fault": 20,
    }, f"unexpected captured First-Red state: {state}")
    parity = exact_payload_parity()
    value = {
        "format": "lisp65-c2-product-link34-runtime-island-hardware-first-red-diagnosis-v1",
        "status": "first-red-receipt-less-hardware-presmoke-stopped-before-repl",
        "recorded_on": "2026-07-21",
        "scope": {
            "candidate_product_sha256": EXPECTED[PRODUCT],
            "new_product_links_after_first_red": 0,
            "hardware_retries_after_first_red": 0,
            "product_source_changes_after_first_red": 0,
            "presmoke_rows": {
                "boot_to_repl": "first-red-E2f-no-repl",
                "definition_first_call": "not-run",
                "warm_second_call": "not-run",
                "gc_blockread": "not-run",
                "freezer_e000_identity": "not-run",
                "nested_eval": "not-run",
            },
        },
        "evidence": {
            "structural_receipt": bind(STRUCTURAL),
            "deployment": bind(DEPLOYMENT),
            "product": bind(PRODUCT),
            "elf": bind(ELF),
            "boot_manifest": bind(MANIFEST),
            "deployed_boot_family": bind(BOOT),
            "target_leaf": bind(ROOT / "src/rtov_crc_mem.s"),
            "runtime_source": bind(ROOT / "src/vm_runtime_overlay.c"),
            "hardware_captures": [
                bind(LOW_CAPTURE), bind(FIXED_CAPTURE), bind(BOOT_CAPTURE)
            ],
        },
        "hardware_observation": {
            "user_visible": "red border; E2f runtime island invalid; redeploy",
            "captured_runtime_state": state,
            "decoded": {
                "family": "boot",
                "island_state": "failed",
                "latched_fault": "VM_RUNTIME_OVERLAY_ERR_ISLAND (generic outer mapping)",
                "window_payload_after_fail": "wiped; loaded length reset to zero",
                "island_0x1800_0x1fff": "all zero; fail-closed cleanup passed",
                "boot_family_after_fail": "byte-identical to deployed Link-34 family",
            },
        },
        "localization": {
            "installer_executed": False,
            "basis": (
                "The record verifier is the sole writer of RTOV_INSTALL_CONTEXT "
                "and the installer is the sole writer of RTOV_INSTALL_TARGET. "
                "Neither generic failure cleanup nor the outer E2f mapping clears "
                "those globals. Both remain zero, so successful record publication "
                "and installer entry were not reached."),
            "bounded_region": [
                "catalog-verifier payload CRC or catalog validation",
                "record-verifier payload CRC or record validation before frame publication",
            ],
            "not_reached": [
                "verifier-frame seal consumption",
                "DATA_ONLY carrier read/copy",
                "resident-Island target CRC",
                "C2 product boot",
            ],
        },
        "host_exact_operational_payload_check": parity,
        "claim_hygiene": {
            "established": (
                "The deployed bytes and Boot-family preload were exact, cleanup was "
                "fail-closed, and the final-ELF leaf interpreter matches every actual "
                "early-boot payload CRC used before Island publication."),
            "not_established": (
                "The exact target-side rejection point and root cause remain unknown. "
                "Host instruction interpretation is not 45GS02 hardware execution."),
        },
        "bounded_next_probe": {
            "authorization": "not granted by this diagnosis",
            "kind": "exact-Link-34-leaf hardware conformance probe; no product link",
            "method": (
                "Load the immutable Link-34 product bytes without entering the product, "
                "call the exact linked leaf at 0x222d from a disposable diagnostic stub, "
                "and compare A/X against the pinned CRC for the canonical vector and the "
                "five exact early-boot inputs."),
            "cases": [
                "123456789 -> 0x29b1",
                "catalog header with CRC field zeroed, 32 bytes -> 0xf0de",
                "catalog-verifier, 1156 bytes -> 0x291d",
                "record-verifier, 1411 bytes -> 0x3d7c",
                "resident-island-installer, 1287 bytes -> 0xbf4b",
                "resident-island-image, 1781 bytes -> 0x8009",
            ],
            "decision_rule": {
                "any_crc_mismatch": (
                    "Target execution/ABI of the hand-written leaf is the First Red; "
                    "return with the exact failing length and value before source work."),
                "all_crc_match": (
                    "The leaf is exonerated on metal; authorize a diagnostic-only stage "
                    "latch that preserves the inner verifier status before E2f maps it."),
            },
        },
        "claim_limit": (
            "Read-only binding and diagnosis of one receipt-less Link-34 hardware "
            "First Red. It is not hardware acceptance, performance evidence, promotion, "
            "authorization for a retry, source fix or successor product link."),
        "next_gate": (
            "Review/authorize the bounded exact-byte hardware CRC conformance probe; "
            "no presmoke retry and no product change."),
    }
    OUTPUT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    OUTPUT.chmod(0o444)
    return value


if __name__ == "__main__":
    try:
        result = run()
        print("c2-link34-island-first-red: " + result["status"])
    except (DiagnosisError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print("c2-link34-island-first-red: FAIL: " + str(error), file=sys.stderr)
        raise SystemExit(1)
