#!/usr/bin/env python3
"""Build and evaluate Class-B cycle 1: hold before the E2f wipe."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link35_completion_double_crc_diagnostic as D  # noqa: E402
import c2_dma_completion_first_status_successor_link as L35  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / "src/vm_runtime_overlay.c"
DEFINE = "LISP65_C2_ISLAND_DIAGNOSTIC_HOLD_BEFORE_WIPE"
FEATURES = (*L35.FEATURES, DEFINE)
LINK35_REPLAY = D.LINK35_REPLAY
LINK35_DIR = D.LINK35_DIR
LINK35_PRODUCT = D.LINK35_PRODUCT
LINK35_ELF = D.LINK35_ELF
LINK35_PRODUCT_SHA = D.LINK35_PRODUCT_SHA
OUT = ROOT / (
    "build/c2.2/substitution/link35-hold-before-wipe-diagnostic-cycle1")
RECEIPT = EVIDENCE / (
    "c2.2-link35-hold-before-wipe-diagnostic-cycle1-link-receipt.json")
HW_RECEIPT = EVIDENCE / (
    "c2.2-link35-hold-before-wipe-diagnostic-cycle1-hardware-receipt.json")
TARGET = 0xC356
TARGET_BYTES = 1156
SOURCE_OFFSET = 0x200
EXPECTED_CRC = 0xE856


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def hold_region(source: str) -> str:
    start = "#ifdef " + DEFINE
    require(source.count(start) == 1, "diagnostic hold branch is not unique")
    tail = source.split(start, 1)[1]
    require("#elif defined(LISP65_C2_ISLAND_DIAGNOSTIC_CRC_LATCH_DOUBLE)" in tail,
            "diagnostic hold branch has no bounded end")
    return tail.split(
        "#elif defined(LISP65_C2_ISLAND_DIAGNOSTIC_CRC_LATCH_DOUBLE)", 1)[0]


def source_gate(source: str, mutations: bool = False) -> dict[str, Any]:
    region = hold_region(source)
    required = (
        "rtov_crc_mem((const uint8_t *)RTOV_TARGET, file_len) != crc",
        "rtov_fault = VM_RUNTIME_OVERLAY_ERR_CRC;",
        'for (;;) __asm__ volatile("" ::: "memory");',
    )
    for token in required:
        require(token in region, f"hold-before-wipe source token absent: {token}")
    require("rtov_wipe" not in region, "diagnostic hold branch performs a wipe")
    require("return VM_RUNTIME_OVERLAY" not in region,
            "diagnostic mismatch edge returns instead of holding")
    matrix: dict[str, str] = {}
    if mutations:
        candidates = {
            "hold-removed": source.replace(required[2], "return;", 1),
            "wipe-inserted": source.replace(
                required[1], required[1] + "\n        rtov_wipe();", 1),
            "specific-status-removed": source.replace(
                required[1], "rtov_fault = VM_RUNTIME_OVERLAY_ERR_ENTRY;", 1),
        }
        for name, candidate in candidates.items():
            try:
                source_gate(candidate, mutations=False)
            except GateError:
                matrix[name] = "rejected"
            else:
                raise GateError(f"hold-before-wipe source mutation accepted: {name}")
    return {
        "status": "passed-hold-before-wipe-source-gate",
        "mismatch_status": "VM_RUNTIME_OVERLAY_ERR_CRC",
        "wipe_before_hold": False,
        "verifier_entry_before_hold": False,
        "mutations": matrix,
    }


def instructions(body: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for line in body.splitlines():
        match = re.match(
            r"^\s*([0-9a-f]+):\s+([a-z][a-z0-9]*)\s*(.*)$", line)
        if match:
            result.append({"address": int(match.group(1), 16),
                           "mnemonic": match.group(2),
                           "operand": match.group(3).strip(),
                           "text": line.strip()})
    return result


def hold_elf_gate(elf: Path) -> dict[str, Any]:
    current = D.symbols(elf)
    baseline = D.symbols(LINK35_ELF)
    for name in ("rtov_call_context", "rtov_call_result",
                 "rtov_loaded_len", "rtov_fault"):
        require(name in current and name in baseline,
                f"diagnostic state absent: {name}")
        require(current[name] == baseline[name],
                f"hold diagnostic allocated or moved state: {name}")
    body = D.function_disassembly(
        elf, "vm_runtime_overlay_exec_family", current)
    rows = instructions(body)
    fault = int(current["rtov_fault"]["address"])
    holds: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if row["mnemonic"] != "sta" or not re.search(
                rf"\${fault:x}\b", row["operand"]):
            continue
        following = rows[index + 1:index + 4]
        for candidate in following:
            if candidate["mnemonic"] not in ("bra", "jmp"):
                continue
            target_match = re.search(r"\$([0-9a-f]+)", candidate["operand"])
            if target_match and int(target_match.group(1), 16) == candidate["address"]:
                holds.append({"fault_store": row, "self_branch": candidate})
    require(len(holds) == 1,
            f"expected one linked CRC-status hold edge, found {len(holds)}")
    hold = holds[0]
    prefix = [row for row in rows if row["address"] < hold["fault_store"]["address"]]
    require(any(row["mnemonic"] == "lda" and re.search(
                    r"#\$(?:0?f)\b", row["operand"])
                for row in prefix[-5:]),
            "hold edge does not load ERR_CRC before latching rtov_fault")
    require(any("rtov_crc_mem" in row["operand"] for row in prefix),
            "hold edge is not downstream of a payload CRC")
    return {
        "status": "passed-linked-hold-before-wipe-edge",
        "rtov_fault_address": f"0x{fault:04x}",
        "fault_store": hold["fault_store"]["text"],
        "self_branch": hold["self_branch"]["text"],
        "new_state_bytes": 0,
        "state_symbols_identical_to_link35": True,
    }


def capacity_gate(capacity: dict[str, Any]) -> dict[str, Any]:
    baseline = json.loads(
        LINK35_REPLAY.read_text(encoding="utf-8"))["capacity"]
    flat = (
        "bank0_text_headroom_bytes",
        "ordinary_bank0_bss_headroom_bytes",
        "fixed_hot_block_headroom_bytes",
        "resident_island_headroom_bytes",
    )
    deltas: dict[str, int] = {}
    for field in flat:
        delta = int(capacity[field]) - int(baseline[field])
        require(delta >= 0, f"Class-B diagnostic consumes bound wall: {field}")
        deltas[field] = delta
    require(capacity["e000"]["actual_headroom_bytes"] == 115
            and capacity["e000"]["delta_bytes"] == 0,
            "Class-B diagnostic moves the final E000 floor")
    for family in ("boot", "session"):
        field = family + "_headroom_bytes"
        delta = (int(capacity["runtime_overlay_bank"][field]) -
                 int(baseline["runtime_overlay_bank"][field]))
        require(delta >= 0,
                f"Class-B diagnostic consumes {family} runtime-bank headroom")
        deltas["runtime_overlay_bank_" + field] = delta
    minimum_delta = (int(capacity["runtime_slices"]["minimum_headroom_bytes"])
                     - int(baseline["runtime_slices"]["minimum_headroom_bytes"]))
    require(minimum_delta >= 0,
            "Class-B diagnostic consumes the minimum slice headroom")
    deltas["runtime_slice_minimum_headroom_bytes"] = minimum_delta
    deltas["e000_headroom_bytes"] = 0
    return {
        "status": "passed-class-b-no-bound-capacity-debit",
        "headroom_delta_vs_link35_bytes": deltas,
        "footprint_effect": "zero-or-credit-on-every-bound-wall",
    }


def prerequisites() -> dict[str, Any]:
    expected = {
        D.LINK35_REPLAY: D.LINK35_REPLAY_SHA,
        D.LINK35_FIRST_RED: D.LINK35_FIRST_RED_SHA,
        LINK35_PRODUCT: LINK35_PRODUCT_SHA,
    }
    for path, digest in expected.items():
        require(path.is_file() and D.sha(path) == digest,
                f"Link-35 diagnostic prerequisite drift: {path}")
    replay = json.loads(D.LINK35_REPLAY.read_text(encoding="utf-8"))
    first_red = json.loads(D.LINK35_FIRST_RED.read_text(encoding="utf-8"))
    require(replay.get("status") ==
            "passed-artifact-only-link35-preinstall-dataflow-replay",
            "Link-35 pure replay is not green")
    require(first_red.get("status") ==
            "FIRST RED: chained completion marker observed but "
            "catalog-verifier payload CRC failed",
            "Link-35 hardware First Red is not authoritative")
    return {
        "link35_pure_replay": D.bind(D.LINK35_REPLAY),
        "link35_hardware_first_red": D.bind(D.LINK35_FIRST_RED),
        "link35_rollback_product": {**D.bind(LINK35_PRODUCT),
                                    "status": "untouched"},
        "diagnostic_source": D.bind(SOURCE),
        "completion_leaf": D.bind(ROOT / "src/rtov_dma_completion.s"),
        "hold_source_gate": source_gate(
            SOURCE.read_text(encoding="utf-8"), mutations=True),
    }


def full_build(out: Path) -> dict[str, Any]:
    D.BASE.configure()
    authority = prerequisites()
    fresh = D.BASE.PRE.check(out / "fresh-v5-prelink-gates")
    require(fresh["status"] == "passed-prelink-product-link-not-run"
            and fresh["b2_model"]["cases"] == 18,
            "fresh nested-append/B2 prelink gates failed")
    D.BASE.P.single_link(
        out, probe_definitions=FEATURES,
        direct_entry_receipt=D.BASE.DIRECT.RECEIPT,
        direct_entry_check_tool="c2_hot_refill_direct_entry_contract.py",
        extra_contract_lines=(
            "mode=class-b-link35-hold-before-wipe-cycle1",
            "promotable=no",
            "diagnostic_define=" + DEFINE,
            "feature_defines=" + ",".join(FEATURES),
            "link35_rollback_sha256=" + LINK35_PRODUCT_SHA,
            "diagnostic_question=E2f-hold-before-wipe",
            "delegation_class=B",
            "delegated_cycle=1-of-3",
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
    capacity, sections = D.BASE.capacity(elf, out)
    walls = capacity_gate(capacity)
    completion = D.LEAF.elf_gate(elf)
    hold = hold_elf_gate(elf)
    closure = D.BASE.LINK33_BASE.final_overlay_closure(elf)
    preinstall = D.BASE.ISLAND.static_elf_gate(elf)
    hot = D.BASE.HOT.direct_path_gate(elf)
    status_rule = L35.first_status_source_gate(
        SOURCE.read_text(encoding="utf-8"))
    require(D.sha(product) != LINK35_PRODUCT_SHA,
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
        "hold_before_wipe": hold["status"],
        "first_status_source": status_rule["status"],
        "class_b_capacity": walls["status"],
    }
    require(all("pass" in value for value in gates.values()),
            f"diagnostic fresh gate set red: {gates}")
    return {
        "recorded_on": "2026-07-21",
        "delegation": {"class": "B", "cycle": 1, "cycle_cap": 3,
                       "question": "E2f / hold before wipe"},
        "promotable": False,
        "authority": authority,
        "product_identity": {
            "product": D.bind(product), "elf": D.bind(elf),
            "resolved_profile": D.bind(out / "resolved-profile.txt"),
        },
        "fresh_gates": gates,
        "hold_before_wipe": hold,
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
            "whole_program_lto_diagnostic_links": 1,
            "hardware_runs": 0,
            "promotable_product_candidates": 0,
        },
        "link35_rollback": {**D.bind(LINK35_PRODUCT), "status": "untouched"},
    }


def protect(out: Path, receipt: Path) -> None:
    if out.exists():
        D.BASE.protect(out)
    os.chmod(receipt, 0o444)


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Class-B cycle-1 diagnostic link already consumed")
    try:
        result = full_build(OUT)
        result.update({
            "format": "lisp65-c2-link35-hold-before-wipe-class-b-link-v1",
            "status": "passed-nonpromotable-hold-before-wipe-cycle1-hardware-not-run",
            "claim_limit": (
                "One non-promotable Class-B diagnostic identity. It makes no "
                "product, promotion, acceptance, completion-contract or "
                "hardware claim."),
            "next_gate": "one announced Class-B diagnostic hardware run",
        })
        report = OUT / "hold-before-wipe-diagnostic-link.json"
        D.write_json(report, result)
        value = {**result, "report": D.bind(report)}
        D.write_json(RECEIPT, value)
        protect(OUT, RECEIPT)
        return value
    except Exception as error:
        value = {
            "format": "lisp65-c2-link35-hold-before-wipe-class-b-first-red-v1",
            "recorded_on": "2026-07-21",
            "status": "FIRST RED: Class-B hold-before-wipe cycle 1 stopped",
            "promotable": False,
            "diagnostic": {"type": type(error).__name__, "message": str(error)},
            "execution_accounting": {
                "whole_program_lto_diagnostic_links": int(
                    (OUT / "lisp65-c2-substitution-linked.prg").is_file()),
                "hardware_runs": 0,
                "promotable_product_candidates": 0,
            },
            "evidence": D.evidence_tree(OUT) if OUT.exists() else {},
            "link35_rollback": {**D.bind(LINK35_PRODUCT), "status": "untouched"},
            "next_gate": "stop; escalate if a bound wall or product question was touched",
        }
        D.write_json(RECEIPT, value)
        protect(OUT, RECEIPT)
        return value


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "Class-B cycle-1 diagnostic receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") ==
            "passed-nonpromotable-hold-before-wipe-cycle1-hardware-not-run",
            "Class-B cycle-1 diagnostic link is not green")
    for row in value["product_identity"].values():
        require(D.bind(ROOT / row["path"]) == row,
                f"diagnostic identity drift: {row['path']}")
    require(D.sha(LINK35_PRODUCT) == LINK35_PRODUCT_SHA,
            "Link-35 rollback identity drift")
    return value


def crc16(data: bytes) -> int:
    value = 0xffff
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = (((value << 1) ^ 0x1021) & 0xffff
                     if value & 0x8000 else (value << 1) & 0xffff)
    return value


def classify(captures: list[bytes], expected: bytes) -> str:
    if all(value == expected for value in captures):
        return "destination-converged-after-first-failed-crc-before-capture"
    if any(left != right for left, right in zip(captures, captures[1:])):
        return "destination-still-evolving-while-held"
    return "destination-stably-wrong-while-held"


def classify_selftest() -> dict[str, str]:
    good = b"abc"
    cases = {
        "converged": ([good, good, good],
                      "destination-converged-after-first-failed-crc-before-capture"),
        "evolving": ([b"aaa", b"aab", good],
                     "destination-still-evolving-while-held"),
        "stable-wrong": ([b"aaa", b"aaa", b"aaa"],
                         "destination-stably-wrong-while-held"),
    }
    for name, (values, expected) in cases.items():
        require(classify(values, good) == expected,
                f"hardware classifier drift: {name}")
    return {name: "passed" for name in cases}


def evaluate_hardware(directory: Path) -> dict[str, Any]:
    check()
    require(not HW_RECEIPT.exists(), "cycle-1 hardware receipt already exists")
    deployment = json.loads(
        (directory / "deployment.json").read_text(encoding="utf-8"))
    boot_row = next(row for row in deployment["preloads"]
                    if int(row["address"], 16) == 0x08200000)
    boot_path = ROOT / boot_row["path"]
    boot = boot_path.read_bytes()
    require(D.sha(boot_path) == boot_row["sha256"],
            "deployed Boot-family binding drift")
    expected = boot[SOURCE_OFFSET:SOURCE_OFFSET + TARGET_BYTES]
    require(len(expected) == TARGET_BYTES and crc16(expected) == EXPECTED_CRC,
            "expected catalog-verifier slice drift")
    target_paths = [directory / f"held-target-capture-{index}.bin"
                    for index in range(1, 4)]
    captures = [path.read_bytes() for path in target_paths]
    require(all(len(value) == TARGET_BYTES for value in captures),
            "held target capture length drift")
    boot_live = directory / "held-boot-family.bin"
    require(boot_live.read_bytes() == boot,
            "Boot-family source changed during diagnostic run")
    low = (directory / "held-low-0000-1fff.bin").read_bytes()
    require(len(low) == 0x2000 and low[0x7c] == 15,
            "hardware did not stop on the latched ERR_CRC edge")
    job = (directory / "held-job-and-marker-b960-bfe0.bin").read_bytes()
    require(len(job) == 0x680 and job[0xbfd1 - 0xb960] == 0xa5,
            "completion marker was not observed in the held state")
    outcome = classify(captures, expected)
    values = [{
        **D.bind(path),
        "crc16": f"0x{crc16(data):04x}",
        "matches_expected": data == expected,
        "nonmatching_bytes": sum(a != b for a, b in zip(data, expected)),
    } for path, data in zip(target_paths, captures)]
    if outcome == "destination-converged-after-first-failed-crc-before-capture":
        answer = (
            "The target converged to the exact catalog-verifier payload after "
            "the product had already observed marker 0xa5 and failed its first "
            "CRC, while execution was held before wipe. The marker is therefore "
            "an early publication witness, not a completion boundary.")
        product_decision = "completion contract/fix required (Class C)"
    elif outcome == "destination-still-evolving-while-held":
        answer = (
            "The target continued changing while held before wipe, directly "
            "confirming post-marker transfer visibility.")
        product_decision = "completion contract/fix required (Class C)"
    else:
        answer = (
            "The held destination remained stably wrong; E2f is not explained "
            "by delayed convergence alone and Class-B cycle 2 is required.")
        product_decision = "no product conclusion; Class-B cycle 2 remains available"
    value = {
        "format": "lisp65-c2-link35-hold-before-wipe-class-b-hardware-v1",
        "recorded_on": "2026-07-21",
        "status": "answered-E2f-hold-before-wipe" if "completion" in product_decision
                  else "Class-B cycle 1 inconclusive",
        "promotable": False,
        "delegation": {"class": "B", "cycle": 1, "cycle_cap": 3},
        "authorization": D.bind(RECEIPT),
        "deployment": D.bind(directory / "deployment.json"),
        "product_identity": D.bind(
            OUT / "lisp65-c2-substitution-linked.prg"),
        "observations": {
            "rtov_fault": 15,
            "completion_marker": "0xa5",
            "expected_crc16": f"0x{EXPECTED_CRC:04x}",
            "target_captures": values,
            "source_post_stop": {**D.bind(boot_live),
                                 "matches_deployed": True},
            "classification": outcome,
        },
        "answer": answer,
        "next_gate": product_decision,
        "claim_limit": (
            "One non-promotable receipt-less Class-B hardware diagnostic. "
            "It is not promotion, acceptance, latency or product evidence."),
        "classifier_mutations": classify_selftest(),
        "execution_accounting": {
            "diagnostic_links": 1,
            "hardware_runs": 1,
            "read_only_post_stop_captures": 5,
            "remaining_autonomous_cycles": 2,
        },
        "link35_rollback": {**D.bind(LINK35_PRODUCT), "status": "untouched"},
    }
    D.write_json(HW_RECEIPT, value)
    D.BASE.protect(directory)
    os.chmod(HW_RECEIPT, 0o444)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "selftest", "build", "check", "evaluate-hardware"))
    parser.add_argument("--hardware-dir", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            D.BASE.configure()
            prerequisites()
            classify_selftest()
            print("c2-link35-hold-before-wipe: SELFTEST PASS mutations=6")
            return 0
        if args.action == "build":
            value = build()
        elif args.action == "check":
            value = check()
        else:
            require(args.hardware_dir is not None,
                    "--hardware-dir is required for evaluation")
            value = evaluate_hardware(args.hardware_dir.resolve())
        print("c2-link35-hold-before-wipe: " + value["status"])
        return 3 if str(value["status"]).startswith("FIRST RED") else 0
    except Exception as error:
        print("c2-link35-hold-before-wipe: FAIL " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
