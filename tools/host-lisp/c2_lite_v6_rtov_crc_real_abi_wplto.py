#!/usr/bin/env python3
"""Measure the Link-38 rtov_crc_mem real-ABI correction with one WPLTO."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_crc_asm_leaf_gate as CRC  # noqa: E402
import c2_lite_v6_bank3_staging_wplto_probe as STAGE  # noqa: E402
import c2_lite_v6_boot_crc_abi_wplto as PAYLOAD  # noqa: E402
import c2_product_hw_presmoke as HW  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


P = STAGE.P
OUT = ROOT / "build/c2-lite/v6-link38-rtov-crc-real-abi-wplto"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.2-c2-lite-v6-link38-rtov-crc-real-abi-wplto-receipt.json")
HARDWARE = EVIDENCE / (
    "c2.2-link38-c2-lite-hold-before-fail-hardware-receipt.json")
HARDWARE_SHA = (
    "69cee2766fc1fc3744fd3c19680479578ca6cbf6f36db0d2c37b2410025e0ca8")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-product-link38-c2-lite-v6-boot-crc-abi-artifact-replay-receipt.json")
BASE_RECEIPT_SHA = (
    "3cad09e6a609f7b7e860896bf30ba707a17acb68975b9d56d9ba1c08117f1cfc")
BASE = ROOT / (
    "build/c2.2/substitution/"
    "product-link-38-c2-lite-v6-boot-crc-abi-replay/"
    "lisp65-c2-substitution-linked.prg")
BASE_SHA = (
    "61f406b57eeb2e258e941be432e8f6cea797c0623f421f09cc56e91f6f1419a2")
EXPECTED_CALLERS = {
    "vm_runtime_overlay_exec_family": 2,
    "rtov_run_batch": 1,
    "vm_runtime_overlay_catalog_verifier": 1,
    "vm_resident_island_install": 2,
    "vm_runtime_overlay_record_verifier": 1,
}
EXPECTED_BASE_WALLS = {
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


def protect() -> None:
    if OUT.exists():
        for path in OUT.rglob("*"):
            if path.is_file():
                os.chmod(path, 0o444)
    if RECEIPT.is_file():
        os.chmod(RECEIPT, 0o444)


def section_sizes(elf: Path) -> dict[str, int]:
    return {name: row["bytes"] for name, row in P.section_table(elf).items()}


def authority() -> dict[str, Any]:
    expected = {
        HARDWARE: HARDWARE_SHA,
        BASE_RECEIPT: BASE_RECEIPT_SHA,
        BASE: BASE_SHA,
    }
    for path, digest in expected.items():
        require(path.is_file() and sha(path) == digest,
                f"rtov CRC ABI authority drift: {path}")
    hardware = json.loads(HARDWARE.read_text(encoding="utf-8"))
    require(hardware["status"] == "answered-link38-bank3-island-edge"
            and hardware["observations"]["classification"]
                == "transport-exact-crc-leaf-abi-reversed"
            and hardware["execution_accounting"]["hardware_runs"] == 1
            and hardware["execution_accounting"]["latency_attempts_consumed"]
                == "0/2",
            "hardware ABI diagnosis is not authoritative")
    return {
        "hardware_hold_before_fail": bind(HARDWARE),
        "link38_structural_baseline": bind(BASE_RECEIPT),
        "link38_product_baseline": bind(BASE),
        "driver": bind(Path(__file__)),
    }


def workbench_crc_gate(target: Path, elf: Path) -> dict[str, Any]:
    data = PAYLOAD.payload(target, elf)
    expected = CRC.crc_reference(data)
    truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    descriptor = HW.boot_overlay_descriptor(
        build_id=int(sha(target.parent / "resolved-profile.txt")[:8], 16),
        start=truth.symbol("__lisp65_workbench_overlay_start").value,
        entry=truth.symbol("vm_workbench_boot_overlay_entry").value,
        payload=data)
    require(struct.unpack_from("<H", descriptor, 16)[0] == expected,
            "Workbench descriptor CRC drift")
    vectors = dict(CRC.VECTORS)
    CRC.VECTORS["actual-workbench-overlay"] = data
    try:
        report = CRC.audit_elf(
            elf, out=OUT / "c2-crc-asm-leaf-real-abi-parity.json")
    finally:
        CRC.VECTORS.clear()
        CRC.VECTORS.update(vectors)
    require(len(report["vectors"]) == 6
            and report["vectors"]["actual-workbench-overlay"]["bytes"] == 1731
            and report["vectors"]["actual-workbench-overlay"]["crc16"]
                == expected,
            "six-vector CRC parity suite drift")
    return {
        "status": "passed-six-final-elf-parity-vectors",
        "cases": len(report["vectors"]),
        "actual_workbench_bytes": len(data),
        "actual_workbench_crc16": f"0x{expected:04x}",
        "actual_workbench_sha256": hashlib.sha256(data).hexdigest(),
        "descriptor_sha256": hashlib.sha256(descriptor).hexdigest(),
        "vectors": report["vectors"],
    }


def first_red(error: BaseException) -> dict[str, Any]:
    value = {
        "format": "lisp65-c2-lite-v6-rtov-crc-real-abi-wplto-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: rtov CRC real-ABI WPLTO stopped",
        "failure": {"type": type(error).__name__, "message": str(error)},
        "scope": {"whole_program_lto_probes": int(OUT.exists()),
                  "product_links": 0, "hardware_runs": 0,
                  "promotable": False},
        "evidence": [bind(path) for path in sorted(OUT.rglob("*"))
                     if path.is_file()],
        "rollback_line": {**bind(BASE), "status": "untouched"},
        "next_gate": "Class-C review; no product link or hardware",
    }
    write_json(RECEIPT, value)
    protect()
    return value


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "rtov CRC real-ABI WPLTO is one-shot")
    auth = authority()
    OUT.mkdir(parents=True)
    abi_mutations = ABI.selftest()
    crc_mutations = CRC.selftest()
    stage_states = STAGE.state_machine_gate()
    stage_source = STAGE.source_contract_gate()

    old_out = STAGE.OUT
    STAGE.OUT = OUT
    try:
        wplto, target, elf = STAGE.run_wplto(STAGE.feature_set())
        product = STAGE.product_gate(wplto, target, elf)
    finally:
        STAGE.OUT = old_out

    abi = ABI.audit_elf(
        elf, out=OUT / "c2-asm-leaf-real-abi-callers.json",
        require_bank3_chain=True)
    callers = abi["rtov_crc_mem_callers"]
    counts: dict[str, int] = {}
    for row in callers["callers"]:
        counts[row["owner"]] = counts.get(row["owner"], 0) + 1
    require(callers["callsite_count"] == 7
            and counts == EXPECTED_CALLERS,
            f"complete rtov_crc_mem caller inventory drift: {counts}")
    parity = workbench_crc_gate(target, elf)

    baseline_elf = Path(str(BASE) + ".elf")
    before = section_sizes(baseline_elf)
    after = section_sizes(elf)
    require(set(before) == set(after), "WPLTO section inventory drift")
    deltas = {name: after[name] - before[name] for name in sorted(before)}
    unexpected = {name: value for name, value in deltas.items()
                  if value != 0 and not (name == ".text" and value == 8)}
    require(not unexpected and deltas[".text"] == 8,
            f"real-ABI correction changed unexpected sections: {unexpected}")
    old_truth = ElfTruth.read(
        baseline_elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    new_truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    old_leaf = old_truth.symbol("rtov_crc_mem")
    new_leaf = new_truth.symbol("rtov_crc_mem")
    require(old_leaf.bytes == 66 and new_leaf.bytes == 74,
            f"CRC Leaf size truth drift: {old_leaf.bytes}->{new_leaf.bytes}")
    expected_walls = {**EXPECTED_BASE_WALLS,
                      "bank0_text_headroom_bytes": 3}
    require(product["walls"] == expected_walls,
            f"WPLTO wall drift: {product['walls']}")

    report = {
        "format": "lisp65-c2-lite-v6-rtov-crc-real-abi-wplto-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-rtov-crc-real-abi-wplto",
        "scope": {"whole_program_lto_probes": 1, "product_links": 0,
                  "hardware_runs": 0, "promotable": False},
        "authority": auth,
        "correction": {
            "callee": "rtov_crc_mem(const uint8_t *p, uint16_t length)",
            "pointer_binding": "__rc2/__rc3",
            "length_binding": "A/X",
            "result_binding": "A/X",
            "source": bind(ROOT / "src/rtov_crc_mem.s"),
            "hardware_exonerated_transport": True,
        },
        "assembler_leaf_abi_gate": abi,
        "complete_caller_inventory": {
            "callsite_count": callers["callsite_count"],
            "owners": counts,
            "product_assembler_callers": 0,
            "all_edges": callers["callers"],
        },
        "negative_mutations": {
            "assembler_abi": abi_mutations,
            "crc_oracle_and_codegen": crc_mutations,
            "total": len(abi_mutations) + len(crc_mutations),
        },
        "six_vector_crc_parity": parity,
        "capacity": {
            "section_deltas": deltas,
            "leaf": {"before_bytes": old_leaf.bytes,
                     "after_bytes": new_leaf.bytes,
                     "delta_bytes": new_leaf.bytes - old_leaf.bytes},
            "walls_before": EXPECTED_BASE_WALLS,
            "walls_after": product["walls"],
            "product_byte_claim": (
                "No product link was made. The product-shaped WPLTO measures "
                "one +8-byte .text/Leaf delta and zero in every other "
                "section."),
        },
        "bank3_stage_gates": {
            "state_machine": stage_states,
            "source_contract": stage_source,
            "product_gate": product,
        },
        "artifacts": {
            "measurement_prg": bind(target),
            "measurement_elf": bind(elf),
            "measurement_map": bind(Path(str(target) + ".map")),
            "abi_gate": bind(OUT / "c2-asm-leaf-real-abi-callers.json"),
            "crc_parity_gate": bind(
                OUT / "c2-crc-asm-leaf-real-abi-parity.json"),
        },
        "rollback_line": {**bind(BASE), "status": "untouched"},
        "claim_limit": (
            "One nonpromotable product-shaped WPLTO. It proves the corrected "
            "real ABI, complete caller inventory, mutation matrix, six-vector "
            "CRC parity and measured capacity. It is not a product link, "
            "hardware acceptance, latency or promotion claim."),
        "next_gate": "Separate Class-C approval before a successor product link",
    }
    write_json(OUT / "rtov-crc-real-abi-wplto-report.json", report)
    report["probe_report"] = bind(
        OUT / "rtov-crc-real-abi-wplto-report.json")
    write_json(RECEIPT, report)
    protect()
    return report


def main() -> int:
    try:
        value = build()
    except Exception as error:
        if OUT.exists() and not RECEIPT.exists():
            first_red(error)
        print("c2-lite-v6-rtov-crc-real-abi-wplto: FIRST RED " + str(error))
        return 2
    print("c2-lite-v6-rtov-crc-real-abi-wplto: PASS "
          f"callers={value['complete_caller_inventory']['callsite_count']} "
          f"vectors={value['six_vector_crc_parity']['cases']} "
          f"leaf=+{value['capacity']['leaf']['delta_bytes']}B "
          f"text-headroom={value['capacity']['walls_after']['bank0_text_headroom_bytes']}B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
