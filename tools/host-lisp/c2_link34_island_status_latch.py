#!/usr/bin/env python3
"""Build and bind the authorized non-promotable Link-34 status-latch probe."""

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
import c2_crc_asm_leaf_successor_link as L34  # noqa: E402
import c2_link33_bss_triage_product_link as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PROBE_OUT = ROOT / "build/c2.2/substitution/link34-island-status-latch-wplto"
PROBE_RECEIPT = EVIDENCE / (
    "c2.2-link34-island-status-latch-wplto-probe-receipt.json")
LINK_OUT = ROOT / "build/c2.2/substitution/link34-island-status-latch-diagnostic"
LINK_RECEIPT = EVIDENCE / (
    "c2.2-link34-island-status-latch-diagnostic-link-receipt.json")
HARDWARE_OUT = ROOT / "build/c2.2/link34-island-status-latch-hardware"
HARDWARE_RESULT = HARDWARE_OUT / "hardware-result.json"
SOURCE = ROOT / "src/vm_runtime_overlay.c"
LINK34_RECEIPT = EVIDENCE / (
    "c2.2-product-link34-crc-asm-leaf-structural-receipt.json")
LINK34_PRODUCT = ROOT / (
    "build/c2.2/substitution/product-link-34-crc-asm-leaf/"
    "lisp65-c2-substitution-linked.prg")
LINK34_ELF = Path(str(LINK34_PRODUCT) + ".elf")
FIRST_RED = EVIDENCE / (
    "c2.2-product-link34-runtime-island-hardware-first-red-diagnosis.json")
EXONERATION = EVIDENCE / (
    "c2.2-product-link34-crc-leaf-hardware-exoneration-receipt.json")
LEAF_RESULT = ROOT / (
    "build/c2.2/link34-crc-leaf-hardware-probe/hardware-result.json")
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
DEFINE = "LISP65_C2_ISLAND_DIAGNOSTIC_LATCH"
FEATURES = (*BASE.FEATURES, DEFINE)
LINK34_PRODUCT_SHA = (
    "bef7708baa12b8e23094c2150a53f5bee529be25b9b9e11d0d68a3191ee6a485")
LINK34_RECEIPT_SHA = (
    "b4610ac561b576f85bdbb7491bcb0bec79974edeef1a4c691657adf313d67509")
FIRST_RED_SHA = (
    "803c5b1e5d474e7a02f8ac1afe435f444d9169b7e2aeaa5f301ce0a7c91d68fe")
EXONERATION_SHA = (
    "9aa04a67689366e415fb1dd4a81e0796397cf0713db0326154cd2e426e806bff")
LEAF_RESULT_SHA = (
    "95e1467afecf5a7766195e663628b75c96c03849248938841cbbee01cb883232")


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"status-latch artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


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


def prerequisites() -> dict[str, Any]:
    expected = {
        LINK34_RECEIPT: LINK34_RECEIPT_SHA,
        LINK34_PRODUCT: LINK34_PRODUCT_SHA,
        FIRST_RED: FIRST_RED_SHA,
        EXONERATION: EXONERATION_SHA,
        LEAF_RESULT: LEAF_RESULT_SHA,
    }
    for path, digest in expected.items():
        require(path.is_file() and sha(path) == digest,
                f"status-latch prerequisite drift: {path}")
    baseline = json.loads(LINK34_RECEIPT.read_text(encoding="utf-8"))
    exoneration = json.loads(EXONERATION.read_text(encoding="utf-8"))
    leaf = json.loads(LEAF_RESULT.read_text(encoding="utf-8"))
    require(baseline.get("status") ==
            "passed-new-product-identity-hardware-not-run"
            and baseline["product_identity"]["product"]["sha256"] ==
            LINK34_PRODUCT_SHA,
            "Link-34 structural rollback line is not green")
    require(exoneration.get("status") ==
            "leaf-exonerated-next-stage-requires-separate-authorization"
            and leaf.get("status") ==
            "passed-receipt-less-exact-linked-leaf-on-hardware",
            "exact linked CRC leaf is not exonerated")
    source = SOURCE.read_text(encoding="utf-8")
    required = (
        "#ifdef LISP65_C2_ISLAND_DIAGNOSTIC_LATCH",
        "((volatile uint8_t *)&rtov_call_context)[0] = verifier_index;",
        "((volatile uint8_t *)&rtov_call_context)[1] = (uint8_t)status;",
        "((volatile uint8_t *)&rtov_call_result)[0] =",
        "(uint8_t)rtov_loaded_len;",
        "((volatile uint8_t *)&rtov_call_result)[1] =",
        "(uint8_t)(rtov_loaded_len >> 8);",
    )
    for token in required:
        require(token in source, f"diagnostic latch source token absent: {token}")
    require(source.count("LISP65_C2_ISLAND_DIAGNOSTIC_LATCH") == 1,
            "diagnostic define escaped its one guarded source site")
    return {
        "link34_structural_baseline": bind(LINK34_RECEIPT),
        "link34_rollback_product": {**bind(LINK34_PRODUCT),
                                    "status": "untouched"},
        "link34_first_red": bind(FIRST_RED),
        "exact_crc_leaf_exoneration": bind(EXONERATION),
        "exact_crc_leaf_hardware_result": bind(LEAF_RESULT),
        "diagnostic_latch_source": bind(SOURCE),
    }


def symbols(path: Path) -> dict[str, dict[str, int | str]]:
    result: dict[str, dict[str, int | str]] = {}
    text = run([str(TOOLCHAIN / "llvm-nm"), "--defined-only",
                "--print-size", "--numeric-sort", str(path)])
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 4:
            result[fields[-1]] = {"address": int(fields[0], 16),
                                  "bytes": int(fields[1], 16),
                                  "type": fields[2]}
    return result


def latch_model(verifier_index: int, status: int,
                loaded_len: int) -> dict[str, Any]:
    require(verifier_index in (0, 1), "invalid diagnostic verifier index")
    require(1 <= status <= 21, "invalid diagnostic inner status")
    require(0 <= loaded_len <= 1792, "invalid diagnostic loaded length")
    return {
        "verifier": "catalog" if verifier_index == 0 else "record",
        "inner_status": status,
        "loaded_len": loaded_len,
        "failure_class": (
            "tuple-payload-crc-before-verifier"
            if loaded_len else "verifier-returned-status"),
    }


def selftest() -> dict[str, str]:
    require(latch_model(0, 15, 1156)["failure_class"] ==
            "tuple-payload-crc-before-verifier",
            "catalog tuple-CRC model drift")
    require(latch_model(1, 7, 0) == {
                "verifier": "record", "inner_status": 7,
                "loaded_len": 0, "failure_class": "verifier-returned-status"},
            "record semantic model drift")
    mutations = {
        "invalid-verifier-index": (2, 15, 0),
        "success-is-not-a-failure-status": (0, 0, 0),
        "length-over-slice-cap": (1, 15, 1793),
    }
    rejected: dict[str, str] = {}
    for name, args in mutations.items():
        try:
            latch_model(*args)
        except GateError:
            rejected[name] = "rejected"
        else:
            raise GateError(f"diagnostic latch mutation accepted: {name}")
    return rejected


def function_disassembly(elf: Path, name: str,
                         symbol_table: dict[str, dict[str, int | str]]) -> str:
    row = symbol_table[name]
    begin = int(row["address"])
    end = begin + int(row["bytes"])
    disassembly = run([str(TOOLCHAIN / "llvm-objdump"), "-d",
                       "--no-show-raw-insn", "--symbolize-operands", str(elf)])
    lines: list[str] = []
    for line in disassembly.splitlines():
        match = re.match(r"^\s*([0-9a-f]+):", line)
        if match and begin <= int(match.group(1), 16) < end:
            lines.append(line)
    require(lines, f"no disassembly for diagnostic latch owner {name}")
    return "\n".join(lines)


def latch_elf_gate(elf: Path) -> dict[str, Any]:
    current = symbols(elf)
    baseline = symbols(LINK34_ELF)
    state_names = ("rtov_call_context", "rtov_call_result",
                   "rtov_loaded_len", "rtov_fault")
    state: dict[str, Any] = {}
    for name in state_names:
        require(name in current and name in baseline,
                f"diagnostic state symbol absent: {name}")
        require(current[name] == baseline[name],
                f"diagnostic latch allocated or moved state: {name}")
        state[name] = current[name]
    require(current["rtov_call_context"]["bytes"] == 2
            and current["rtov_call_result"]["bytes"] == 2,
            "diagnostic tuple is not the existing four-byte storage")
    body = function_disassembly(elf, "vm_runtime_overlay_exec_family", current)
    addresses = {
        int(current["rtov_call_context"]["address"]),
        int(current["rtov_call_context"]["address"]) + 1,
        int(current["rtov_call_result"]["address"]),
        int(current["rtov_call_result"]["address"]) + 1,
    }
    missing = [address for address in sorted(addresses)
               if not re.search(rf"\b(?:sta|stx|sty|stz)\s+\${address:x}\b", body)]
    require(not missing,
            f"diagnostic latch stores absent from final WPLTO function: {missing}")
    return {
        "status": "passed-four-existing-bytes-no-new-state",
        "owner": "vm_runtime_overlay_exec_family",
        "state_symbols": state,
        "store_addresses": [f"0x{address:02x}" for address in sorted(addresses)],
        "saved_before_rtov_fail": True,
        "outer_E2f_mapping_unchanged": True,
        "fail_closed_wipe_unchanged": True,
        "negative_matrix": selftest(),
    }


def evidence_tree(out: Path) -> dict[str, dict[str, Any]]:
    return {path.relative_to(out).as_posix(): bind(path)
            for path in sorted(out.rglob("*")) if path.is_file()}


def protect(out: Path, receipt: Path) -> None:
    BASE.protect(out)
    os.chmod(receipt, 0o444)


def full_gate_build(
    out: Path, *, mode: str,
    features: tuple[str, ...] = FEATURES,
    diagnostic_define: str = DEFINE,
    diagnostic_gate=latch_elf_gate,
    capacity_gate=None,
) -> dict[str, Any]:
    BASE.configure()
    authority = prerequisites()
    fresh = BASE.PRE.check(out / "fresh-v5-prelink-gates")
    require(fresh["status"] == "passed-prelink-product-link-not-run"
            and fresh["b2_model"]["cases"] == 18,
            "fresh nested-append/B2 prelink gates failed")
    BASE.P.single_link(
        out, probe_definitions=features,
        direct_entry_receipt=BASE.DIRECT.RECEIPT,
        direct_entry_check_tool="c2_hot_refill_direct_entry_contract.py",
        extra_contract_lines=(
            "mode=link34-island-status-latch-" + mode,
            "promotable=no",
            "hardware_acceptance_claim=forbidden",
            "diagnostic_define=" + diagnostic_define,
            "feature_defines=" + ",".join(features),
            "product_profile_object="
            + BASE.PROFILE.PROFILE.relative_to(ROOT).as_posix(),
            "product_profile_object_sha256=" + BASE.PROFILE.sha256(),
            "link34_rollback_sha256=" + LINK34_PRODUCT_SHA,
            "append_abi=v5-high-edge-transient-c2j",
            "append_slice_count=" + str(len(BASE.P.C2_APPEND_SLICES)),
            "fixed_facade_vector_count=15",
            "final_e000_floor_bytes=115",
            "green_inheritance=none",
        ))
    product = out / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    structure = json.loads(
        (out / "product-substitution-link.json").read_text(encoding="utf-8"))
    total = json.loads(
        (out / "total-publish-last-domain.json").read_text(encoding="utf-8"))
    required = (
        "identity_gate", "capacity_gate", "one_truth_gate",
        "kernal_freedom_gate", "fixed_host_facade_gate",
        "pre_ownership_gate", "handoff_z_abi_gate",
    )
    require(structure.get("status") == "passed"
            and structure.get("product_closure_link_count") == 1
            and all(structure.get(name) == "passed" for name in required),
            "diagnostic WPLTO closure is not fully green")
    require(total.get("status") == "passed"
            and total.get("declared_domain_bytes") == 34,
            "diagnostic 34-byte publish-last binding drift")
    capacity, sections = BASE.capacity(elf, out)
    closure = BASE.LINK33_BASE.final_overlay_closure(elf)
    preinstall = BASE.ISLAND.static_elf_gate(elf)
    hot = BASE.HOT.direct_path_gate(elf)
    latch = diagnostic_gate(elf)
    baseline = json.loads(LINK34_RECEIPT.read_text(encoding="utf-8"))["capacity"]
    if capacity_gate is None:
        require(capacity["ordinary_bank0_bss_headroom_bytes"] ==
                baseline["ordinary_bank0_bss_headroom_bytes"],
                "diagnostic latch consumed ordinary BSS")
        require(capacity["fixed_hot_block_headroom_bytes"] ==
                baseline["fixed_hot_block_headroom_bytes"]
                and capacity["resident_island_headroom_bytes"] ==
                baseline["resident_island_headroom_bytes"]
                and capacity["e000"]["actual_headroom_bytes"] == 115,
                "diagnostic latch moved a non-text resident wall")
    else:
        capacity_gate(capacity, baseline)
    crc_codegen = json.loads(
        (out / "c2-crc-codegen-gate.json").read_text(encoding="utf-8"))
    crc_leaf = json.loads(
        (out / "c2-crc-asm-leaf-gate.json").read_text(encoding="utf-8"))
    f011 = json.loads(
        (out / "c2-f011-mount-window-gate.json").read_text(encoding="utf-8"))
    fresh_gates = {
        **{name: structure[name] for name in required},
        "direct_entry_encoding": structure["direct_entry_encoding_gate"],
        "runtime_family_identity": structure["identity_components"]
            ["all_runtime_family_records_and_payloads"],
        "total_publish_last": structure["identity_components"]
            ["total_publish_last_domain_gate"],
        "crc_codegen": crc_codegen["status"],
        "crc_assembler_leaf": crc_leaf["status"],
        "f011_mount_window": f011["status"],
        "overlay_closure": closure["status"],
        "preinstallation_island": preinstall["status"],
        "hot_refill": hot["status"],
        "diagnostic_latch": latch["status"],
    }
    require(all("pass" in status for status in fresh_gates.values()),
            f"diagnostic fresh gate set red: {fresh_gates}")
    return {
        "recorded_on": "2026-07-21",
        "mode": mode,
        "promotable": False,
        "authority": authority,
        "product_identity": {"product": bind(product), "elf": bind(elf),
                             "resolved_profile": bind(out / "resolved-profile.txt")},
        "link34_rollback": {**bind(LINK34_PRODUCT), "status": "untouched"},
        "fresh_gates": fresh_gates,
        "diagnostic_latch": latch,
        "capacity": capacity,
        "capacity_delta_vs_link34": {
            "bank0_text_headroom_bytes": (
                capacity["bank0_text_headroom_bytes"] -
                baseline["bank0_text_headroom_bytes"]),
            "ordinary_bank0_bss_headroom_bytes": (
                capacity["ordinary_bank0_bss_headroom_bytes"] -
                baseline["ordinary_bank0_bss_headroom_bytes"]),
            "fixed_hot_block_headroom_bytes": (
                capacity["fixed_hot_block_headroom_bytes"] -
                baseline["fixed_hot_block_headroom_bytes"]),
            "resident_island_headroom_bytes": (
                capacity["resident_island_headroom_bytes"] -
                baseline["resident_island_headroom_bytes"]),
            "e000_headroom_bytes": (
                capacity["e000"]["actual_headroom_bytes"] -
                baseline["e000"]["actual_headroom_bytes"]),
        },
        "section_count": len(sections),
        "post_link_identity": {
            "declared_mutable_product_bytes": total["declared_domain_bytes"],
            "actual_changed_bytes": total["actual_changed_bytes"],
            "status": total["status"],
        },
        "execution_accounting": {
            "whole_program_lto_closure_links": 1,
            "hardware_runs": 0,
            "promotable_product_candidates": 0,
        },
    }


def bind_first_red(out: Path, receipt: Path, mode: str,
                   error: BaseException) -> dict[str, Any]:
    value = {
        "format": "lisp65-c2-link34-island-status-latch-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: " + mode + " stopped",
        "promotable": False,
        "diagnostic": {"type": type(error).__name__, "message": str(error)},
        "execution_accounting": {
            "hardware_runs": 0,
            "promotable_product_candidates": 0,
        },
        "evidence": evidence_tree(out) if out.is_dir() else {},
        "link34_rollback": {**bind(LINK34_PRODUCT), "status": "untouched"},
        "next_gate": "stop; no hardware run",
    }
    write(receipt, value)
    protect(out, receipt)
    return value


def build_stage(stage: str) -> dict[str, Any]:
    if stage == "probe":
        out, receipt = PROBE_OUT, PROBE_RECEIPT
        require(not out.exists() and not receipt.exists(),
                "status-latch WPLTO probe is one-shot and already consumed")
    else:
        out, receipt = LINK_OUT, LINK_RECEIPT
        require(PROBE_RECEIPT.is_file(), "green status-latch probe absent")
        probe = json.loads(PROBE_RECEIPT.read_text(encoding="utf-8"))
        require(probe.get("status") ==
                "passed-status-latch-wplto-no-diagnostic-link"
                and not probe.get("promotable", True),
                "status-latch capacity probe is not green/non-promotable")
        require(not out.exists() and not receipt.exists(),
                "status-latch diagnostic link is one-shot and already consumed")
    try:
        result = full_gate_build(out, mode=stage)
        result.update({
            "format": "lisp65-c2-link34-island-status-latch-"
                      + ("wplto-probe-v1" if stage == "probe"
                         else "diagnostic-link-v1"),
            "status": ("passed-status-latch-wplto-no-diagnostic-link"
                       if stage == "probe" else
                       "passed-nonpromotable-diagnostic-link-hardware-not-run"),
            "claim_limit": (
                "One product-shaped WPLTO capacity/placement and full-gate probe. "
                "It is not a product candidate, hardware evidence or promotion."
                if stage == "probe" else
                "One fully gated but permanently non-promotable diagnostic link. "
                "It may be used only for the authorized inner-status hardware run; "
                "it cannot satisfy product acceptance or promotion."),
            "next_gate": (
                "owner-authorized non-promotable diagnostic link"
                if stage == "probe" else
                "one owner-authorized diagnostic hardware run; stop after capture"),
        })
        report = out / ("status-latch-wplto-probe.json" if stage == "probe"
                        else "diagnostic-island-latch-link.json")
        write(report, result)
        receipt_value = {**result, "report": bind(report),
                         "evidence_file_count": len(evidence_tree(out))}
        write(receipt, receipt_value)
        protect(out, receipt)
        return receipt_value
    except (GateError, BASE.LinkError, BASE.PRE.GateError,
            BASE.ISLAND.GateError, RuntimeError, OSError, ValueError,
            KeyError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        return bind_first_red(out, receipt, stage, error)


STATUS_NAMES = {
    0: "OK", 1: "ERR_ARGUMENT", 2: "ERR_LATCHED", 3: "ERR_BUSY",
    4: "ERR_MAGIC", 5: "ERR_VERSION", 6: "ERR_HEADER",
    7: "ERR_PROFILE", 8: "ERR_DIRECTORY", 9: "ERR_SLOT",
    10: "ERR_VMA", 11: "ERR_ENTRY", 12: "ERR_LENGTH", 13: "ERR_ABI",
    14: "ERR_STACK", 15: "ERR_CRC", 16: "ERR_WIPE", 17: "ERR_ABORTED",
    18: "ERR_BATCH_LIMIT", 19: "ERR_ISLAND_NOT_READY",
    20: "ERR_ISLAND", 21: "ERR_FAMILY",
}


def evaluate_hardware() -> dict[str, Any]:
    require(LINK_RECEIPT.is_file(), "diagnostic-link receipt absent")
    link = json.loads(LINK_RECEIPT.read_text(encoding="utf-8"))
    require(link.get("status") ==
            "passed-nonpromotable-diagnostic-link-hardware-not-run",
            "diagnostic link is not green and hardware-not-run")
    deployment = HARDWARE_OUT / "deployment.json"
    low_path = HARDWARE_OUT / "diagnostic-low-0000-1fff.bin"
    boot_path = HARDWARE_OUT / "diagnostic-boot-family.bin"
    require(deployment.is_file() and low_path.is_file()
            and low_path.stat().st_size == 0x2000 and boot_path.is_file(),
            "diagnostic hardware captures are incomplete")
    dep = json.loads(deployment.read_text(encoding="utf-8"))
    boot_binding = next(row for row in dep["preloads"]
                        if row["address"] == "0x08200000")
    require(sha(boot_path) == boot_binding["sha256"]
            and boot_path.stat().st_size == boot_binding["bytes"],
            "diagnostic Boot-family readback drift")
    elf = ROOT / link["product_identity"]["elf"]["path"]
    table = symbols(elf)
    low = low_path.read_bytes()

    def byte(name: str, offset: int = 0) -> int:
        address = int(table[name]["address"]) + offset
        require(0 <= address < len(low), f"diagnostic symbol outside capture: {name}")
        return low[address]

    verifier_index = byte("rtov_call_context")
    inner_status = byte("rtov_call_context", 1)
    loaded_len = byte("rtov_call_result") | (byte("rtov_call_result", 1) << 8)
    outer_fault = byte("rtov_fault")
    island_state = byte("rtov_island_state")
    busy = byte("rtov_busy")
    require(inner_status in STATUS_NAMES and inner_status != 0,
            "diagnostic latch did not capture an inner failure status")
    decoded = latch_model(verifier_index, inner_status, loaded_len)
    require(outer_fault == 20 and island_state == 3 and busy == 0,
            "diagnostic run did not terminate at the expected fail-closed E2f state")
    result = {
        "format": "lisp65-c2-link34-island-status-latch-hardware-result-v1",
        "recorded_on": "2026-07-21",
        "status": "diagnostic-inner-status-captured-stop-before-fix",
        "promotable": False,
        "diagnostic_link": bind(LINK_RECEIPT),
        "deployment": bind(deployment),
        "captures": {"low": bind(low_path), "boot_family": bind(boot_path)},
        "latched": {
            "verifier_index": verifier_index,
            "verifier": decoded["verifier"],
            "inner_status": inner_status,
            "inner_status_name": STATUS_NAMES[inner_status],
            "loaded_len_before_wipe": loaded_len,
            "failure_class": decoded["failure_class"],
            "outer_fault": outer_fault,
            "outer_fault_name": STATUS_NAMES[outer_fault],
            "island_state": island_state,
            "busy": busy,
        },
        "execution_accounting": {
            "diagnostic_hardware_runs": 1,
            "product_presmoke_retries": 0,
            "promotable_product_links": 0,
        },
        "claim_limit": (
            "One non-promotable diagnostic hardware run. It localizes the "
            "inner verifier failure but is not product acceptance, promotion, "
            "latency evidence or authorization for a fix/successor link."),
        "next_gate": (
            "stop and return the exact inner status for review; no automatic fix"),
    }
    write(HARDWARE_RESULT, result)
    for path in HARDWARE_OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    return result


def check(receipt: Path, expected: str) -> dict[str, Any]:
    require(receipt.is_file(), f"status-latch receipt absent: {receipt}")
    value = json.loads(receipt.read_text(encoding="utf-8"))
    require(value.get("status") == expected, f"status-latch receipt not green: {receipt}")
    for row in value["product_identity"].values():
        require(bind(ROOT / row["path"]) == row,
                f"status-latch bound identity drift: {row['path']}")
    require(sha(LINK34_PRODUCT) == LINK34_PRODUCT_SHA,
            "Link-34 rollback product drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "selftest", "probe", "check-probe", "link", "check-link",
        "evaluate-hardware"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            BASE.configure(); prerequisites(); mutations = selftest()
            print("c2-link34-island-status-latch: SELFTEST PASS mutations="
                  + str(len(mutations)))
            return 0
        if args.action == "probe":
            value = build_stage("probe")
        elif args.action == "link":
            value = build_stage("diagnostic-link")
        elif args.action == "check-probe":
            value = check(PROBE_RECEIPT,
                          "passed-status-latch-wplto-no-diagnostic-link")
        elif args.action == "check-link":
            value = check(LINK_RECEIPT,
                          "passed-nonpromotable-diagnostic-link-hardware-not-run")
        else:
            value = evaluate_hardware()
        print("c2-link34-island-status-latch: " + value["status"])
        return 3 if value["status"].startswith("FIRST RED") else 0
    except (GateError, BASE.LinkError, BASE.PRE.GateError,
            BASE.ISLAND.GateError, RuntimeError, OSError, ValueError,
            KeyError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        print("c2-link34-island-status-latch: FAIL: " + str(error),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
