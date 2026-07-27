#!/usr/bin/env python3
"""Build the one authorized Link-35 completion/double-CRC diagnostic."""

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
import c2_dma_completion_first_status_successor_link as L35  # noqa: E402
import c2_link33_bss_triage_product_link as BASE  # noqa: E402
import c2_link34_dma_completion_leaf_presmoke as LEAF  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / "src/vm_runtime_overlay.c"
DEFINE = "LISP65_C2_ISLAND_DIAGNOSTIC_CRC_LATCH_DOUBLE"
FEATURES = (*L35.FEATURES, DEFINE)
LINK35_REPLAY = EVIDENCE / (
    "c2.2-product-link35-dma-completion-first-status-pure-replay-receipt.json")
LINK35_REPLAY_SHA = (
    "10bc82583a9b6f80c805a6770769792047e838e93e07d92a4735b673bd2fd13d")
LINK35_FIRST_RED = EVIDENCE / (
    "c2.2-product-link35-dma-completion-hardware-first-red-diagnosis.json")
LINK35_FIRST_RED_SHA = (
    "1313edd19d466f290ac6af61f83840884bc385cb7f7b5dfc88928280f1b74c06")
LINK35_DIR = ROOT / (
    "build/c2.2/substitution/product-link-35-dma-completion-first-status")
LINK35_PRODUCT = LINK35_DIR / "lisp65-c2-substitution-linked.prg"
LINK35_ELF = Path(str(LINK35_PRODUCT) + ".elf")
LINK35_PRODUCT_SHA = (
    "54c731559fdb72d5d1cb8478b9da7e78a422741e4e5267d64b07fe4c6f763a65")
PROBE_OUT = ROOT / (
    "build/c2.2/substitution/link35-completion-double-crc-wplto")
PROBE_RECEIPT = EVIDENCE / (
    "c2.2-link35-completion-double-crc-wplto-probe-receipt.json")
LINK_OUT = ROOT / (
    "build/c2.2/substitution/link35-completion-double-crc-diagnostic")
LINK_RECEIPT = EVIDENCE / (
    "c2.2-link35-completion-double-crc-diagnostic-link-receipt.json")
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"diagnostic artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: dict[str, Any]) -> None:
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


def symbols(path: Path) -> dict[str, dict[str, int | str]]:
    result: dict[str, dict[str, int | str]] = {}
    output = run([str(TOOLCHAIN / "llvm-nm"), "--defined-only",
                  "--print-size", "--numeric-sort", str(path)])
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 4:
            result[fields[-1]] = {
                "address": int(fields[0], 16),
                "bytes": int(fields[1], 16),
                "type": fields[2],
            }
    return result


def function_disassembly(
    elf: Path, name: str, table: dict[str, dict[str, int | str]],
) -> str:
    row = table[name]
    begin = int(row["address"])
    end = begin + int(row["bytes"])
    output = run([str(TOOLCHAIN / "llvm-objdump"), "-d",
                  "--no-show-raw-insn", "--symbolize-operands", str(elf)])
    lines: list[str] = []
    for line in output.splitlines():
        match = re.match(r"^\s*([0-9a-f]+):", line)
        if match and begin <= int(match.group(1), 16) < end:
            lines.append(line)
    require(lines, f"no disassembly for {name}")
    return "\n".join(lines)


def classify(first: int, second: int, expected: int) -> str:
    require(first != expected, "first CRC unexpectedly matches")
    if second == expected:
        return "second-read-converged"
    if second == first:
        return "stable-wrong-cpu-view"
    return "evolving-post-marker-cpu-view"


def model_selftest() -> dict[str, str]:
    cases = {
        "second-converges": (0x1111, 0xe856, "second-read-converged"),
        "stable-wrong": (0x1111, 0x1111, "stable-wrong-cpu-view"),
        "evolving": (0x1111, 0x2222, "evolving-post-marker-cpu-view"),
    }
    for name, (first, second, expected) in cases.items():
        require(classify(first, second, 0xe856) == expected,
                f"double-CRC model drift: {name}")
    try:
        classify(0xe856, 0xe856, 0xe856)
    except GateError:
        matching = "rejected"
    else:
        raise GateError("matching first CRC mutation accepted")
    return {**{name: "passed" for name in cases},
            "matching-first": matching}


def prerequisites() -> dict[str, Any]:
    expected = {
        LINK35_REPLAY: LINK35_REPLAY_SHA,
        LINK35_FIRST_RED: LINK35_FIRST_RED_SHA,
        LINK35_PRODUCT: LINK35_PRODUCT_SHA,
    }
    for path, digest in expected.items():
        require(path.is_file() and sha(path) == digest,
                f"Link-35 diagnostic prerequisite drift: {path}")
    replay = json.loads(LINK35_REPLAY.read_text(encoding="utf-8"))
    first_red = json.loads(LINK35_FIRST_RED.read_text(encoding="utf-8"))
    require(replay.get("status") ==
            "passed-artifact-only-link35-preinstall-dataflow-replay",
            "Link-35 pure replay is not green")
    require(first_red.get("status") ==
            "FIRST RED: chained completion marker observed but "
            "catalog-verifier payload CRC failed",
            "Link-35 hardware First Red is not authoritative")
    source = SOURCE.read_text(encoding="utf-8")
    required = (
        "#ifdef LISP65_C2_ISLAND_DIAGNOSTIC_CRC_LATCH_DOUBLE",
        "((volatile uint8_t *)&rtov_call_context)[0] =",
        "((volatile uint8_t *)&rtov_call_context)[1] =",
        "((volatile uint8_t *)&rtov_call_result)[0] =",
        "((volatile uint8_t *)&rtov_call_result)[1] =",
    )
    for token in required:
        require(token in source, f"double-CRC source token absent: {token}")
    require(source.count(
        "observed_crc = rtov_crc_mem((const uint8_t *)RTOV_TARGET, "
        "file_len);") >= 3,
        "double-CRC branch lacks its two observations")
    return {
        "link35_pure_replay": bind(LINK35_REPLAY),
        "link35_hardware_first_red": bind(LINK35_FIRST_RED),
        "link35_rollback_product": {**bind(LINK35_PRODUCT),
                                    "status": "untouched"},
        "diagnostic_source": bind(SOURCE),
        "completion_leaf": bind(ROOT / "src/rtov_dma_completion.s"),
    }


def latch_gate(elf: Path) -> dict[str, Any]:
    current = symbols(elf)
    baseline = symbols(LINK35_ELF)
    names = ("rtov_call_context", "rtov_call_result",
             "rtov_loaded_len", "rtov_fault")
    state: dict[str, Any] = {}
    for name in names:
        require(name in current and name in baseline,
                f"diagnostic state absent: {name}")
        require(current[name] == baseline[name],
                f"diagnostic allocated or moved state: {name}")
        state[name] = current[name]
    require(current["rtov_call_context"]["bytes"] == 2
            and current["rtov_call_result"]["bytes"] == 2,
            "diagnostic does not reuse the existing four bytes")
    body = function_disassembly(
        elf, "vm_runtime_overlay_exec_family", current)
    addresses = [
        int(current["rtov_call_context"]["address"]),
        int(current["rtov_call_context"]["address"]) + 1,
        int(current["rtov_call_result"]["address"]),
        int(current["rtov_call_result"]["address"]) + 1,
    ]
    missing = [address for address in addresses if not re.search(
        rf"\b(?:sta|stx|sty|stz)\s+\${address:x}\b", body)]
    require(not missing, f"double-CRC latch stores absent: {missing}")
    require(body.count("rtov_crc_mem") >= 2,
            "double-CRC observations absent after WPLTO")
    return {
        "status": "passed-existing-four-byte-double-crc-latch",
        "state_symbols": state,
        "store_addresses": [f"0x{address:02x}" for address in addresses],
        "new_state_bytes": 0,
        "decision_uses_first_crc": True,
        "second_crc_is_observation_only": True,
        "fail_closed_wipe_unchanged": True,
        "negative_matrix": model_selftest(),
    }


def capacity_gate(capacity: dict[str, Any]) -> dict[str, Any]:
    baseline = json.loads(LINK35_REPLAY.read_text(encoding="utf-8"))["capacity"]
    exact = (
        "ordinary_bank0_bss_headroom_bytes",
        "fixed_hot_block_headroom_bytes",
        "resident_island_headroom_bytes",
    )
    for field in exact:
        require(capacity[field] == baseline[field],
                f"double-CRC diagnostic moved closed wall: {field}")
    require(capacity["e000"]["actual_headroom_bytes"] == 115
            and capacity["e000"]["delta_bytes"] == 0,
            "double-CRC diagnostic moved the final E000 floor")
    require(capacity["bank0_text_headroom_bytes"] >= 0,
            "double-CRC diagnostic overflows Bank-0 text")
    return {
        "status": "passed-link35-closed-wall-capacity",
        "delta_vs_link35": {
            "bank0_text_headroom_bytes": (
                capacity["bank0_text_headroom_bytes"] -
                baseline["bank0_text_headroom_bytes"]),
            "ordinary_bank0_bss_headroom_bytes": 0,
            "fixed_hot_block_headroom_bytes": 0,
            "resident_island_headroom_bytes": 0,
            "e000_headroom_bytes": 0,
        },
    }


def full_build(out: Path, stage: str) -> dict[str, Any]:
    BASE.configure()
    authority = prerequisites()
    fresh = BASE.PRE.check(out / "fresh-v5-prelink-gates")
    require(fresh["status"] == "passed-prelink-product-link-not-run"
            and fresh["b2_model"]["cases"] == 18,
            "fresh nested-append/B2 prelink gates failed")
    BASE.P.single_link(
        out, probe_definitions=FEATURES,
        direct_entry_receipt=BASE.DIRECT.RECEIPT,
        direct_entry_check_tool="c2_hot_refill_direct_entry_contract.py",
        extra_contract_lines=(
            "mode=link35-completion-double-crc-" + stage,
            "promotable=no",
            "diagnostic_define=" + DEFINE,
            "feature_defines=" + ",".join(FEATURES),
            "link35_rollback_sha256=" + LINK35_PRODUCT_SHA,
            "completion_marker_diagnosis=post-marker-double-crc",
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
            "diagnostic product closure is not fully green")
    require(total.get("status") == "passed"
            and total.get("declared_domain_bytes") == 34,
            "diagnostic publish-last binding drift")
    capacity, sections = BASE.capacity(elf, out)
    walls = capacity_gate(capacity)
    completion = LEAF.elf_gate(elf)
    latch = latch_gate(elf)
    closure = BASE.LINK33_BASE.final_overlay_closure(elf)
    preinstall = BASE.ISLAND.static_elf_gate(elf)
    hot = BASE.HOT.direct_path_gate(elf)
    status_rule = L35.first_status_source_gate(
        SOURCE.read_text(encoding="utf-8"))
    require(sha(product) != LINK35_PRODUCT_SHA,
            "diagnostic did not create a distinct identity")
    gates = {
        **{name: structure[name] for name in required},
        "direct_entry_encoding": structure["direct_entry_encoding_gate"],
        "runtime_family_identity": structure["identity_components"]
            ["all_runtime_family_records_and_payloads"],
        "total_publish_last": structure["identity_components"]
            ["total_publish_last_domain_gate"],
        "overlay_closure": closure["status"],
        "preinstallation_island": preinstall["status"],
        "hot_refill": hot["status"],
        "dma_completion_leaf": completion["status"],
        "double_crc_latch": latch["status"],
        "first_status_source": status_rule["status"],
        "diagnostic_capacity": walls["status"],
    }
    require(all("pass" in value for value in gates.values()),
            f"diagnostic fresh gate set red: {gates}")
    return {
        "recorded_on": "2026-07-21",
        "stage": stage,
        "promotable": False,
        "authority": authority,
        "product_identity": {
            "product": bind(product), "elf": bind(elf),
            "resolved_profile": bind(out / "resolved-profile.txt"),
        },
        "fresh_gates": gates,
        "double_crc_latch": latch,
        "dma_completion_leaf": completion,
        "capacity": capacity,
        "capacity_gate": walls,
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
        "link35_rollback": {**bind(LINK35_PRODUCT), "status": "untouched"},
    }


def evidence_tree(out: Path) -> dict[str, dict[str, Any]]:
    return {path.relative_to(out).as_posix(): {
                "bytes": path.stat().st_size, "sha256": sha(path)}
            for path in sorted(out.rglob("*")) if path.is_file()}


def protect(out: Path, receipt: Path) -> None:
    if out.exists():
        BASE.protect(out)
    os.chmod(receipt, 0o444)


def first_red(out: Path, receipt: Path, stage: str,
              error: BaseException) -> dict[str, Any]:
    value = {
        "format": "lisp65-c2-link35-completion-double-crc-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: completion/double-CRC " + stage + " stopped",
        "promotable": False,
        "diagnostic": {"type": type(error).__name__, "message": str(error)},
        "execution_accounting": {
            "whole_program_lto_closure_links": int(
                (out / "lisp65-c2-substitution-linked.prg").is_file()),
            "hardware_runs": 0,
            "promotable_product_candidates": 0,
        },
        "evidence": evidence_tree(out) if out.exists() else {},
        "link35_rollback": {**bind(LINK35_PRODUCT), "status": "untouched"},
        "next_gate": "stop; no diagnostic link or hardware run",
    }
    write_json(receipt, value)
    protect(out, receipt)
    return value


def build_stage(stage: str) -> dict[str, Any]:
    if stage == "probe":
        out, receipt = PROBE_OUT, PROBE_RECEIPT
        require(not out.exists() and not receipt.exists(),
                "double-CRC WPLTO probe already consumed")
    else:
        out, receipt = LINK_OUT, LINK_RECEIPT
        require(PROBE_RECEIPT.is_file(), "double-CRC WPLTO receipt absent")
        probe = json.loads(PROBE_RECEIPT.read_text(encoding="utf-8"))
        require(probe.get("status") ==
                "passed-link35-completion-double-crc-wplto-hardware-not-run",
                "double-CRC WPLTO probe is not green")
        require(not out.exists() and not receipt.exists(),
                "double-CRC diagnostic link already consumed")
    try:
        result = full_build(out, stage)
        result.update({
            "format": ("lisp65-c2-link35-completion-double-crc-wplto-v1"
                       if stage == "probe" else
                       "lisp65-c2-link35-completion-double-crc-diagnostic-v1"),
            "status": (
                "passed-link35-completion-double-crc-wplto-hardware-not-run"
                if stage == "probe" else
                "passed-nonpromotable-link35-completion-double-crc-link-"
                "hardware-not-run"),
            "claim_limit": (
                "Product-shaped capacity/placement probe only; no diagnostic "
                "product or hardware claim."
                if stage == "probe" else
                "One permanently non-promotable diagnostic identity for the "
                "single authorized double-CRC hardware run."),
            "next_gate": (
                "one non-promotable diagnostic link"
                if stage == "probe" else
                "one diagnostic hardware run; stop after capture"),
        })
        report = out / ("double-crc-wplto.json" if stage == "probe"
                        else "double-crc-diagnostic-link.json")
        write_json(report, result)
        value = {**result, "report": bind(report)}
        write_json(receipt, value)
        protect(out, receipt)
        return value
    except Exception as error:
        return first_red(out, receipt, stage, error)


def check(receipt: Path, expected: str) -> dict[str, Any]:
    require(receipt.is_file(), f"diagnostic receipt absent: {receipt}")
    value = json.loads(receipt.read_text(encoding="utf-8"))
    require(value.get("status") == expected,
            f"diagnostic receipt is not green: {receipt}")
    for row in value["product_identity"].values():
        require(bind(ROOT / row["path"]) == row,
                f"diagnostic identity drift: {row['path']}")
    require(sha(LINK35_PRODUCT) == LINK35_PRODUCT_SHA,
            "Link-35 rollback identity drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "selftest", "probe", "check-probe", "link", "check-link"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            BASE.configure(); prerequisites(); matrix = model_selftest()
            print("c2-link35-completion-double-crc: SELFTEST PASS mutations="
                  + str(len(matrix)))
            return 0
        if args.action == "probe":
            value = build_stage("probe")
        elif args.action == "link":
            value = build_stage("diagnostic-link")
        elif args.action == "check-probe":
            value = check(
                PROBE_RECEIPT,
                "passed-link35-completion-double-crc-wplto-hardware-not-run")
        else:
            value = check(
                LINK_RECEIPT,
                "passed-nonpromotable-link35-completion-double-crc-link-"
                "hardware-not-run")
        print("c2-link35-completion-double-crc: " + value["status"])
        return 3 if value["status"].startswith("FIRST RED") else 0
    except Exception as error:
        print("c2-link35-completion-double-crc: FAIL " + str(error),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
