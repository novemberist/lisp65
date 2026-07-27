#!/usr/bin/env python3
"""Measure the owner-approved C2-lite boot-CRC ABI correction.

This performs one nonpromotable product-shaped WPLTO, runs the shared
assembler-leaf ABI gate and executes the linked CRC leaf over the actual
Workbench payload.  It never creates or completes a product link.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import struct
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_crc_asm_leaf_gate as CRC  # noqa: E402
import c2_lite_v6_bank3_staging_wplto_probe as STAGE  # noqa: E402
import c2_product_hw_presmoke as HW  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


P = STAGE.P
OUT = ROOT / "build/c2-lite/v6-bank3-boot-crc-abi-wplto-replay2"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-bank3-boot-crc-abi-wplto-replay2-receipt.json")
HARNESS_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-bank3-boot-crc-abi-wplto-receipt.json")
CRC_PIN_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-bank3-boot-crc-abi-wplto-replay-receipt.json")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link37-c2-lite-v6-two-record-hardware-first-red-diagnosis.json")
BASELINE = ROOT / (
    "build/c2.2/substitution/"
    "c2-lite-v6-bank3-stage-artifact-candidate-replay5/"
    "lisp65-c2-substitution-linked.prg")
EXPECTED_WALLS = {
    "bank0_text_headroom_bytes": 11,
    "ordinary_bank0_bss_headroom_bytes": 86,
    "fixed_hot_block_headroom_bytes": 33,
    "resident_island_headroom_bytes": 170,
    "e000_headroom_bytes": 501,
}


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def payload(_prg: Path, elf: Path) -> bytes:
    truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    section = truth.section(".lisp65_workbench_overlay")
    # Overlay VMAs are not part of the PRG's linear load image.  Extract from
    # a disposable ELF copy: this llvm-objcopy version may normalise its input
    # even for --dump-section, so protected evidence is never the operand.
    with tempfile.TemporaryDirectory(prefix="c2-boot-crc-abi-") as raw:
        work = Path(raw) / "input.elf"
        output = Path(raw) / "workbench.bin"
        shutil.copy2(elf, work)
        subprocess.run([
            str(P.TOOLCHAIN / "llvm-objcopy"), "--dump-section",
            f".lisp65_workbench_overlay={output}", str(work)], check=True)
        result = output.read_bytes()
    require(
        len(result) == section.bytes and section.bytes > 0,
        "Workbench payload extraction drift",
    )
    return result


def section_sizes(elf: Path) -> dict[str, int]:
    return {name: row["bytes"] for name, row in P.section_table(elf).items()}


def protect() -> None:
    if OUT.exists():
        for path in OUT.rglob("*"):
            if path.is_file():
                os.chmod(path, 0o444)
    if RECEIPT.is_file():
        os.chmod(RECEIPT, 0o444)


def first_red(error: BaseException) -> dict[str, Any]:
    value = {
        "format": "lisp65-c2-lite-boot-crc-abi-wplto-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: boot CRC ABI WPLTO stopped",
        "failure": {"type": type(error).__name__, "message": str(error)},
        "scope": {"whole_program_lto_probes": int(OUT.exists()),
                  "product_links": 0, "hardware_runs": 0,
                  "promotable": False},
        "evidence": [bind(path) for path in sorted(OUT.rglob("*"))
                     if path.is_file()],
        "rollback_line": {"candidate": bind(BASELINE),
                          "status": "untouched"},
        "next_gate": "Class-C review; no product link or hardware",
    }
    write_json(RECEIPT, value)
    protect()
    return value


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "boot CRC ABI WPLTO is one-shot")
    require(FIRST_RED.is_file() and HARNESS_FIRST_RED.is_file()
            and CRC_PIN_FIRST_RED.is_file()
            and BASELINE.is_file()
            and Path(str(BASELINE) + ".elf").is_file(),
            "ABI first red or baseline absent")
    OUT.mkdir(parents=True)

    mutations = ABI.selftest()
    features = STAGE.feature_set()
    states = STAGE.state_machine_gate()
    source = STAGE.source_contract_gate()
    original_out = STAGE.OUT
    STAGE.OUT = OUT
    try:
        wplto, target, elf = STAGE.run_wplto(features)
        product = STAGE.product_gate(wplto, target, elf)
    finally:
        STAGE.OUT = original_out

    abi = ABI.audit_elf(
        elf, out=OUT / "c2-asm-leaf-abi-dataflow-gate.json",
        require_bank3_chain=True)
    actual_workbench = payload(target, elf)
    actual_crc = CRC.crc_reference(actual_workbench)
    truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    start = truth.symbol("__lisp65_workbench_overlay_start").value
    entry = truth.symbol("vm_workbench_boot_overlay_entry").value
    contract = target.parent / "resolved-profile.txt"
    build_id = int(sha(contract)[:8], 16)
    descriptor = HW.boot_overlay_descriptor(
        build_id=build_id, start=start, entry=entry,
        payload=actual_workbench)
    descriptor_crc = struct.unpack_from("<H", descriptor, 16)[0]
    require(descriptor_crc == actual_crc
            and descriptor[:4] == HW.DESCRIPTOR_MAGIC
            and len(descriptor) == HW.DESCRIPTOR_BYTES,
            "actual Workbench descriptor CRC drift")
    prior_vectors = dict(CRC.VECTORS)
    CRC.VECTORS["actual-workbench-overlay"] = actual_workbench
    try:
        crc = CRC.audit_elf(
            elf, out=OUT / "c2-crc-asm-leaf-workbench-gate.json")
    finally:
        CRC.VECTORS.clear()
        CRC.VECTORS.update(prior_vectors)
    witness = crc["vectors"]["actual-workbench-overlay"]
    require(
        witness["bytes"] == len(actual_workbench)
        and witness["crc16"] == actual_crc,
        "linked CRC leaf did not reproduce the Workbench descriptor CRC",
    )

    baseline_elf = Path(str(BASELINE) + ".elf")
    before = section_sizes(baseline_elf)
    after = section_sizes(elf)
    require(set(before) == set(after), "WPLTO section inventory drift")
    deltas = {name: after[name] - before[name] for name in sorted(before)}
    require(all(value == 0 for value in deltas.values()),
            "ABI operand correction changed section capacity")
    old_truth = ElfTruth.read(
        baseline_elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    new_truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    leaf_sizes = {}
    for name in ("rtov_crc_mem", "vm_boot_overlay_chain_commit",
                 "vm_bank3_boot_stage_entry"):
        old = old_truth.symbol(name)
        new = new_truth.symbol(name)
        require(old.bytes == new.bytes,
                f"assembler leaf size drift: {name}")
        leaf_sizes[name] = {"before": old.bytes, "after": new.bytes,
                            "delta": new.bytes - old.bytes}
    require(product["walls"] == EXPECTED_WALLS,
            f"WPLTO wall drift: {product['walls']}")

    report = {
        "format": "lisp65-c2-lite-boot-crc-abi-wplto-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-zero-byte-boot-crc-abi-wplto",
        "scope": {"whole_program_lto_probes": 1, "product_links": 0,
                  "hardware_runs": 0, "promotable": False},
        "authority": {"hardware_first_red": bind(FIRST_RED),
                      "harness_first_red": bind(HARNESS_FIRST_RED),
                      "crc_pin_first_red": bind(CRC_PIN_FIRST_RED),
                      "baseline": bind(BASELINE),
                      "driver": bind(Path(__file__))},
        "correction": {
            "callee": "ov_crc16(const uint8_t *p, uint16_t n)",
            "pointer_binding": "__rc2/__rc3",
            "length_binding": "A/X",
            "source": bind(ROOT / "src/c2_boot_chain_commit.s")},
        "assembler_leaf_abi_gate": abi,
        "negative_mutations": mutations,
        "workbench_crc_end_to_end": {
            "bytes": len(actual_workbench), "crc16": actual_crc,
            "descriptor_crc16": descriptor_crc,
            "descriptor_sha256": hashlib.sha256(descriptor).hexdigest(),
            "payload_sha256": hashlib.sha256(actual_workbench).hexdigest(),
            "linked_crc_leaf_executed_instructions":
                witness["executed_instructions"],
            "status": "passed-linked-leaf-equals-descriptor-crc"},
        "capacity": {
            "section_deltas": deltas,
            "leaf_size_deltas": leaf_sizes,
            "product_byte_delta_claim": (
                "No product link was made; every WPLTO section and every "
                "affected leaf has exact size delta 0."),
            "walls": product["walls"]},
        "bank3_stage_gates": {
            "state_machine": states, "source_contract": source,
            "product_gate": product},
        "artifacts": {"measurement_prg": bind(target),
                      "measurement_elf": bind(elf),
                      "measurement_map": bind(Path(str(target) + ".map")),
                      "abi_gate": bind(
                          OUT / "c2-asm-leaf-abi-dataflow-gate.json"),
                      "crc_gate": bind(
                          OUT / "c2-crc-asm-leaf-workbench-gate.json")},
        "rollback_line": {"candidate": bind(BASELINE),
                          "status": "untouched"},
        "claim_limit": (
            "One nonpromotable product-shaped WPLTO.  It proves the ABI "
            "correction, mutation gates, actual Workbench CRC parity and "
            "zero size delta; it is not a product link, hardware acceptance "
            "or promotion claim."),
        "next_gate": "Separate Class-C approval before a successor product link",
    }
    write_json(OUT / "boot-crc-abi-wplto-report.json", report)
    report["probe_report"] = bind(OUT / "boot-crc-abi-wplto-report.json")
    write_json(RECEIPT, report)
    protect()
    return report


def main() -> int:
    try:
        result = build()
    except Exception as error:
        if OUT.exists() and not RECEIPT.exists():
            first_red(error)
        print("c2-lite-boot-crc-abi-wplto: FIRST RED " + str(error))
        return 2
    print("c2-lite-boot-crc-abi-wplto: PASS "
          f"workbench={result['workbench_crc_end_to_end']['bytes']} "
          f"crc={result['workbench_crc_end_to_end']['crc16']:04x} "
          "size-delta=0 product-link=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
