#!/usr/bin/env python3
"""Build the one non-LTO DMA-completion hardware pre-smoke identity."""

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
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / "src/vm_runtime_overlay.c"
LEAF = ROOT / "src/rtov_dma_completion.s"
CONTRACT = ROOT / "config/c2-runtime-overlay-dma-completion-contract.json"
CONTRACT_DOC = ROOT / "docs/planning/c2.2-runtime-overlay-dma-completion-contract.md"
NEGATIVE = EVIDENCE / (
    "c2.2-product-link34-catalog-verifier-edma-completion-hardware-first-red-"
    "diagnosis.json")
OLD_WPLTO_RED = EVIDENCE / (
    "c2.2-link34-dma-completion-wplto-presmoke-receipt.json")
OLD_WPLTO_DIAGNOSIS = EVIDENCE / (
    "c2.2-link34-dma-completion-wplto-capacity-first-red-diagnosis.json")
OUT = ROOT / "build/c2.2/substitution/link34-dma-completion-leaf-presmoke"
RECEIPT = EVIDENCE / (
    "c2.2-link34-dma-completion-nonlto-leaf-wplto-presmoke-receipt.json")
DIAGNOSIS = EVIDENCE / (
    "c2.2-link34-dma-completion-nonlto-leaf-gate-first-red-diagnosis.json")
REPLAY_RECEIPT = EVIDENCE / (
    "c2.2-link34-dma-completion-nonlto-leaf-pure-replay-receipt.json")
HARDWARE_OUT = ROOT / "build/c2.2/link34-dma-completion-leaf-hardware-presmoke"
HARDWARE_RESULT = HARDWARE_OUT / "hardware-result.json"
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
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
    require(path.is_file(), f"DMA-completion leaf artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def source_gate(c_source: str, leaf_source: str) -> dict[str, Any]:
    c_once = (
        "#define RTOV_EDMA_JOB_BYTES 40u",
        "#define RTOV_EDMA_DONE      0xa5u",
        "volatile uint8_t rtov_edma_complete;",
        "void rtov_dma_submit_wait(void);",
        "0x04, 0x00, 0x00, 0x00, 0x00,",
        "0x03, 0x01, 0x00, RTOV_EDMA_DONE, 0x00, 0x00,",
        "rtov_edma_job[34] = (uint8_t)target;",
        "rtov_edma_job[35] = (uint8_t)(target >> 8);",
        "rtov_dma_submit_wait();",
    )
    for token in c_once:
        require(c_source.count(token) == 1,
                f"DMA-completion C invariant absent/duplicated: {token}")
    require(c_source.count('"sta $d705\\n\\t"') == 1,
            "legacy direct trigger must survive only behind the disabled branch")

    leaf_once = (
        '.section\t.text.rtov_dma_submit_wait,"ax",@progbits',
        ".globl\trtov_dma_submit_wait",
        ".type\trtov_dma_submit_wait,@function",
        "\tphp", "\tsei",
        "\tsta\trtov_edma_complete",
        "\tsta\t$d703", "\tsta\t$d702", "\tsta\t$d704",
        "\tsta\t$d701", "\tsta\t$d705",
        "\tlda\trtov_edma_complete", "\tcmp\t#$a5",
        "\tbne\t.Lrtov_dma_wait", "\tplp", "\trts",
        ".size\trtov_dma_submit_wait, ",
    )
    for token in leaf_once:
        require(leaf_source.count(token) == 1,
                f"DMA-completion leaf invariant absent/duplicated: {token}")

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
        require(c_source.count(token) == 1,
                f"rtov_read seam inventory drift: {name}")
    return {
        "status": "passed-one-nonlto-leaf-nine-consumer-seams",
        "consumer_seams": list(seams),
        "leaf_section": ".text.rtov_dma_submit_wait",
        "compiler_barrier": "external non-LTO call boundary",
        "hardware_barrier": "ordered marker poll inside leaf",
    }


def mutation_matrix(c_source: str, leaf_source: str) -> dict[str, str]:
    cases = {
        "barrier-call-removed": ("c", "rtov_dma_submit_wait();", "(void)0;"),
        "chain-removed": ("c", "0x04, 0x00, 0x00, 0x00, 0x00,",
                          "0x00, 0x00, 0x00, 0x00, 0x00,"),
        "fill-removed": ("c",
                         "0x03, 0x01, 0x00, RTOV_EDMA_DONE, 0x00, 0x00,",
                         "0x00, 0x01, 0x00, RTOV_EDMA_DONE, 0x00, 0x00,"),
        "marker-address-wrong": ("c", "rtov_edma_job[34] = (uint8_t)target;",
                                  "rtov_edma_job[33] = (uint8_t)target;"),
        "interrupt-mask-removed": ("leaf", "\tsei", "\tnop"),
        "marker-reset-removed": ("leaf", "\tsta\trtov_edma_complete",
                                  "\tsta\t$d706"),
        "poll-value-wrong": ("leaf", "\tcmp\t#$a5", "\tcmp\t#$a4"),
        "poll-branch-removed": ("leaf", "\tbne\t.Lrtov_dma_wait", "\tnop"),
        "interrupt-restore-removed": ("leaf", "\tplp", "\tnop"),
    }
    rejected: dict[str, str] = {}
    for name, (which, old, new) in cases.items():
        source = c_source if which == "c" else leaf_source
        require(source.count(old) == 1, f"mutation anchor drift: {name}")
        mutated_c = c_source.replace(old, new, 1) if which == "c" else c_source
        mutated_leaf = (leaf_source.replace(old, new, 1)
                        if which == "leaf" else leaf_source)
        try:
            source_gate(mutated_c, mutated_leaf)
        except GateError:
            rejected[name] = "rejected"
        else:
            raise GateError(f"DMA-completion leaf mutation accepted: {name}")
    return rejected


def elf_gate(elf: Path) -> dict[str, Any]:
    table = STATUS.symbols(elf)
    for name in ("rtov_edma_job", "rtov_edma_complete",
                 "rtov_dma_submit_wait", "rtov_read"):
        require(name in table, f"DMA-completion linked symbol absent: {name}")
    require(table["rtov_edma_job"]["bytes"] == 40,
            "linked DMA list is not the two-job 40-byte chain")
    require(table["rtov_edma_complete"]["bytes"] == 1,
            "linked DMA completion marker is not one byte")
    require(table["rtov_dma_submit_wait"]["bytes"] == 39,
            "non-LTO DMA leaf size drift")

    truth = ElfTruth.read(
        elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
    leaf_symbol = truth.symbol("rtov_dma_submit_wait")
    require(leaf_symbol.symbol_type == "Function" and leaf_symbol.bytes == 39
            and leaf_symbol.section not in ("Absolute", "Undefined"),
            "DMA leaf is not a named, sized, section-owned STT_FUNC")

    marker = int(table["rtov_edma_complete"]["address"])
    job = int(table["rtov_edma_job"]["address"])
    split_job = truth.resolve_split_address_binding(
        owner="rtov_dma_submit_wait", target="rtov_edma_job")
    require(split_job["resolved_value"] == job,
            "structured HI/LO binding does not resolve to the DMA job")
    leaf_begin = leaf_symbol.value
    leaf_end = leaf_begin + leaf_symbol.bytes
    marker_relocations = [row for row in truth.relocations
                          if row.source_section_index == leaf_symbol.section_index
                          and leaf_begin <= row.offset < leaf_end
                          and row.target == "rtov_edma_complete"
                          and row.addend == 0
                          and row.relocation_type == "R_MOS_ADDR16"]
    require(len(marker_relocations) == 2,
            "DMA leaf must have exactly two structured marker relocations")
    leaf_body = STATUS.function_disassembly(
        elf, "rtov_dma_submit_wait", table).lower()
    for opcode in ("php", "sei", "plp", "rts"):
        require(re.search(rf"\b{opcode}\b", leaf_body) is not None,
                f"linked DMA leaf lacks {opcode}")
    require("$d703" in leaf_body and "$d702" in leaf_body
            and "$d704" in leaf_body and "$d701" in leaf_body
            and "$d705" in leaf_body and re.search(r"\bbne\b", leaf_body),
            "linked DMA leaf lacks its exact trigger/poll sequence")
    caller = STATUS.function_disassembly(elf, "rtov_read", table).lower()
    caller_symbol = truth.symbol("rtov_read")
    caller_relocations = [row for row in truth.relocations
                          if row.source_section_index == caller_symbol.section_index
                          and caller_symbol.value <= row.offset <
                          caller_symbol.value + caller_symbol.bytes
                          and row.target == "rtov_dma_submit_wait"
                          and row.addend == 0
                          and row.relocation_type == "R_MOS_ADDR16"]
    require(len(caller_relocations) == 1,
            "rtov_read does not have exactly one structured leaf call binding")
    require("$d705" not in caller and not re.search(r"\bphp\b|\bplp\b", caller),
            "DMA trigger/poll ownership leaked back into LTO C code")
    return {
        "status": "passed-named-sized-nonlto-leaf-exact-critical-region",
        "leaf": table["rtov_dma_submit_wait"],
        "leaf_section": leaf_symbol.section,
        "job_split_binding": split_job,
        "marker_relocations": [
            {"offset": row.offset, "type": row.relocation_type}
            for row in marker_relocations],
        "caller_relocation": {
            "offset": caller_relocations[0].offset,
            "type": caller_relocations[0].relocation_type,
        },
        "job": table["rtov_edma_job"],
        "marker": table["rtov_edma_complete"],
        "critical_region_opcodes": [
            "php", "sei", "marker-reset", "two-job-trigger",
            "marker-cmp-bne", "plp", "rts"],
    }


def capacity_gate(capacity: dict[str, Any], baseline: dict[str, Any]) -> None:
    require(capacity["bank0_text_headroom_bytes"] >= 0,
            "DMA completion leaf overflows Bank-0 text")
    require(capacity["ordinary_bank0_bss_headroom_bytes"] >= 0,
            "DMA completion leaf overflows ordinary Bank-0 BSS")
    require(capacity["fixed_hot_block_headroom_bytes"] >= 0,
            "DMA completion leaf overflows the fixed Bank-0 block")
    require(capacity["resident_island_headroom_bytes"] ==
            baseline["resident_island_headroom_bytes"],
            "DMA completion leaf moved the closed resident Island")
    require(capacity["e000"]["actual_headroom_bytes"] ==
            baseline["e000"]["actual_headroom_bytes"] == 115,
            "DMA completion leaf violated the hard E000 delta-zero floor")


def prerequisites() -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    negative = json.loads(NEGATIVE.read_text(encoding="utf-8"))
    old_red = json.loads(OLD_WPLTO_RED.read_text(encoding="utf-8"))
    require(contract.get("status") ==
            "owner-commissioned-contract-then-isolated-hardware-presmoke",
            "DMA completion contract is not commissioned")
    require(negative.get("status") ==
            "FIRST RED: first verifier EDMA payload changes across immediate "
            "sequential CPU CRCs" and negative.get("promotable") is False,
            "bound no-completion hardware negative is absent")
    require(str(old_red.get("status", "")).startswith("FIRST RED")
            and old_red.get("promotable") is False,
            "superseded C/WPLTO floor First Red is absent")
    c_source = SOURCE.read_text(encoding="utf-8")
    leaf_source = LEAF.read_text(encoding="utf-8")
    source = source_gate(c_source, leaf_source)
    mutations = mutation_matrix(c_source, leaf_source)
    return {
        "contract": bind(CONTRACT),
        "contract_document": bind(CONTRACT_DOC),
        "negative_hardware_first_red": bind(NEGATIVE),
        "superseded_c_wplto_first_red": bind(OLD_WPLTO_RED),
        "superseded_c_wplto_diagnosis": bind(OLD_WPLTO_DIAGNOSIS),
        "c_source": bind(SOURCE),
        "nonlto_leaf_source": bind(LEAF),
        "source_gate": source,
        "mutation_matrix": mutations,
    }


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "DMA-completion leaf WPLTO identity is one-shot and already exists")
    authority = prerequisites()
    try:
        result = STATUS.full_gate_build(
            OUT, mode="dma-completion-nonlto-leaf-presmoke",
            features=FEATURES, diagnostic_define=DEFINE,
            diagnostic_gate=elf_gate, capacity_gate=capacity_gate)
        require(result["capacity_delta_vs_link34"]["e000_headroom_bytes"] == 0,
                "recorded E000 delta is not exactly zero")
        result.update({
            "format": "lisp65-c2-link34-dma-completion-nonlto-leaf-wplto-v1",
            "status": (
                "passed-nonpromotable-dma-completion-leaf-hardware-not-run"),
            "promotable": False,
            "contract_authority": authority,
            "hard_capacity_contract": {
                "e000_floor_bytes": 115,
                "e000_delta_bytes": 0,
                "retry_on_lto_layout_noise": "forbidden",
            },
            "hardware_negative": {
                "status": "passed-by-bound-prior-barrier-absent-first-red",
                "expected_crc16": "0xb47f",
                "observed_crc16": ["0x8e92", "0xe092"],
            },
            "claim_limit": (
                "One fully gated, permanently non-promotable WPLTO identity. "
                "It may run only the isolated positive completion pre-smoke; "
                "it is not the combined status fix or product acceptance."),
            "next_gate": (
                "one isolated hardware pre-smoke; first consumer and Island "
                "publication must pass before the combined product link"),
        })
        report = OUT / "dma-completion-nonlto-leaf-wplto.json"
        write(report, result)
        receipt = {**result, "report": bind(report),
                   "evidence_file_count": len(STATUS.evidence_tree(OUT))}
        write(RECEIPT, receipt)
        STATUS.protect(OUT, RECEIPT)
        return receipt
    except Exception as error:
        value = {
            "format": "lisp65-c2-link34-dma-completion-leaf-first-red-v1",
            "recorded_on": "2026-07-21",
            "status": "FIRST RED: DMA-completion non-LTO leaf WPLTO stopped",
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
    require(RECEIPT.is_file(), "DMA-completion leaf receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") ==
            "passed-nonpromotable-dma-completion-leaf-hardware-not-run",
            "DMA-completion leaf identity is not green/hardware-not-run")
    for row in value["product_identity"].values():
        require(bind(ROOT / row["path"]) == row,
                f"DMA-completion leaf bound identity drift: {row['path']}")
    return value


def replay() -> dict[str, Any]:
    require(not REPLAY_RECEIPT.exists(),
            "DMA-completion leaf pure replay is one-shot and already consumed")
    BASE.configure()
    expected = {
        RECEIPT: "8c608cf5a3530231fcb577154ab0868a09f1d51bf1b68b7d9b9048ef024be9f9",
        DIAGNOSIS: "d5b01c8c319fd394d103ac3b244e870ee2db2347ab3f338f5090e318932e6e2f",
        OUT / "lisp65-c2-substitution-linked.prg":
            "3df3cf3d457cbbbf691e6f60834300dc64f6214f65a9a32de82556b0f98b36c4",
        OUT / "lisp65-c2-substitution-linked.prg.elf":
            "75000fa0de4de803e2e6585cbdc69abac88ab9534828c1558fec6631cea76937",
        OUT / "product-substitution-link.json":
            "9607f79951d3bd0e7d4d40a49b26c2c076be374eb9c70f7878e10be76dc3d9e2",
    }
    for path, digest in expected.items():
        require(path.is_file() and sha(path) == digest,
                f"pure-replay authority drift: {path}")
    authority = prerequisites()
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    structure = json.loads(
        (OUT / "product-substitution-link.json").read_text(encoding="utf-8"))
    required = (
        "identity_gate", "capacity_gate", "one_truth_gate",
        "kernal_freedom_gate", "fixed_host_facade_gate",
        "pre_ownership_gate", "handoff_z_abi_gate",
    )
    require(structure.get("status") == "passed"
            and all(structure.get(name) == "passed" for name in required),
            "bound product structural report is not green")
    capacity, sections = BASE.capacity(elf, OUT)
    baseline = json.loads(
        STATUS.LINK34_RECEIPT.read_text(encoding="utf-8"))["capacity"]
    capacity_gate(capacity, baseline)
    closure = BASE.LINK33_BASE.final_overlay_closure(elf)
    preinstall = BASE.ISLAND.static_elf_gate(elf)
    hot = BASE.HOT.direct_path_gate(elf)
    leaf = elf_gate(elf)
    truth_selftest = __import__("elf_truth").selftest()
    result = {
        "format": "lisp65-c2-link34-dma-completion-leaf-pure-replay-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-artifact-only-structured-relocation-leaf-replay",
        "promotable": False,
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0, "hardware_runs": 0,
            "artifact_only_replays": 1,
        },
        "authority": {
            **authority,
            "first_red_receipt": bind(RECEIPT),
            "first_red_diagnosis": bind(DIAGNOSIS),
            "elf_truth_layer": bind(ROOT / "tools/host-lisp/elf_truth.py"),
            "immutable_inputs": [bind(path) for path in expected],
        },
        "product_identity": {"product": bind(product), "elf": bind(elf)},
        "gate_correction": {
            "status": "passed-structured-hi-lo-relocation-truth",
            "elf_truth_selftest": truth_selftest,
            "leaf": leaf,
        },
        "fresh_artifact_only_gates": {
            **{name: structure[name] for name in required},
            "overlay_closure": closure["status"],
            "preinstallation_island": preinstall["status"],
            "hot_refill": hot["status"],
            "dma_completion_leaf": leaf["status"],
        },
        "capacity": capacity,
        "section_count": len(sections),
        "hard_capacity_contract": {
            "e000_floor_bytes": 115,
            "e000_delta_bytes": 0,
        },
        "link34_rollback": {**bind(STATUS.LINK34_PRODUCT),
                            "status": "untouched"},
        "claim_limit": (
            "Artifact-only correction and replay of one post-link verifier. "
            "No compiler, linker, hardware, product acceptance or promotion claim."),
        "next_gate": "combined completion plus first-status-wins successor link",
    }
    write(REPLAY_RECEIPT, result)
    os.chmod(REPLAY_RECEIPT, 0o444)
    return result


def evaluate_hardware() -> dict[str, Any]:
    require(REPLAY_RECEIPT.is_file(), "green leaf replay receipt absent")
    link = json.loads(REPLAY_RECEIPT.read_text(encoding="utf-8"))
    require(link.get("status") ==
            "passed-artifact-only-structured-relocation-leaf-replay",
            "DMA-completion leaf replay is not green")
    deployment = HARDWARE_OUT / "deployment.json"
    low_path = HARDWARE_OUT / "presmoke-low-0000-1fff.bin"
    require(deployment.is_file() and low_path.is_file()
            and low_path.stat().st_size == 0x2000,
            "DMA-completion leaf hardware captures are incomplete")
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
            }, f"DMA-completion leaf positive pre-smoke failed: {observed}")
    result = {
        "format": "lisp65-c2-link34-dma-completion-leaf-hardware-presmoke-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-receipt-less-positive-nonlto-completion-prefilter",
        "promotable": False,
        "observed": observed,
        "proof": {
            "negative_without_barrier": ["0x8e92", "0xe092"],
            "positive_first_consumer": (
                "catalog-verifier CRC passed, Island published READY and no "
                "runtime fault latched"),
            "completion_marker": "0xa5 from the chained one-byte FILL",
        },
        "deployment": bind(deployment),
        "low_capture": bind(low_path),
        "diagnostic_identity": bind(REPLAY_RECEIPT),
        "execution_accounting": {
            "positive_hardware_runs": 1,
            "product_links": 0,
            "product_presmoke_runs": 0,
        },
        "claim_limit": (
            "Receipt-less hardware prefilter of the completion leaf only. It "
            "is not a product candidate, acceptance, promotion or latency claim."),
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
        "selftest", "build", "check", "replay", "evaluate-hardware"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            result = prerequisites()
            print("c2-link34-dma-completion-leaf: SELFTEST PASS mutations="
                  + str(len(result["mutation_matrix"])))
            return 0
        if args.action == "build":
            result = build()
        elif args.action == "check":
            result = check()
        elif args.action == "replay":
            result = replay()
        else:
            result = evaluate_hardware()
        print("c2-link34-dma-completion-leaf: " + result["status"])
        return 3 if result["status"].startswith("FIRST RED") else 0
    except (GateError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print("c2-link34-dma-completion-leaf: FAIL: " + str(error),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
