#!/usr/bin/env python3
"""Build the one combined DMA-completion/first-status successor product."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link33_bss_triage_product_link as BASE  # noqa: E402
import c2_link34_dma_completion_leaf_presmoke as LEAF  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.2/substitution/product-link-35-dma-completion-first-status"
RECEIPT = EVIDENCE / (
    "c2.2-product-link35-dma-completion-first-status-structural-receipt.json")
DIAGNOSIS = EVIDENCE / (
    "c2.2-product-link35-preinstall-wipe-gate-first-red-diagnosis.json")
REPLAY_RECEIPT = EVIDENCE / (
    "c2.2-product-link35-dma-completion-first-status-pure-replay-receipt.json")
REPLAY = EVIDENCE / (
    "c2.2-link34-dma-completion-nonlto-leaf-pure-replay-receipt.json")
REPLAY_SHA = "96e02dbdff6b0313597ab1cbd1fd73a5544fbbb1859f9c01d49f016e3ec6f25a"
CONTRACT = ROOT / "config/c2-runtime-overlay-dma-completion-contract.json"
CONTRACT_DOC = ROOT / "docs/planning/c2.2-runtime-overlay-dma-completion-contract.md"
SOURCE = ROOT / "src/vm_runtime_overlay.c"
HOST_MAIN = ROOT / "scripts/c2-l65r-v2-product-main.c"
LINK34_RECEIPT = LEAF.STATUS.LINK34_RECEIPT
LINK34_PRODUCT = LEAF.STATUS.LINK34_PRODUCT
LINK34_SHA = LEAF.STATUS.LINK34_PRODUCT_SHA
FEATURES = (*BASE.FEATURES, LEAF.DEFINE)


class LinkError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LinkError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"successor-link artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def evidence_tree(out: Path) -> dict[str, dict[str, Any]]:
    return {path.relative_to(out).as_posix(): {
                "bytes": path.stat().st_size, "sha256": sha(path)}
            for path in sorted(out.rglob("*")) if path.is_file()}


def protect(out: Path) -> None:
    BASE.protect(out)


def first_status_source_gate(source: str) -> dict[str, Any]:
    exact = (
        "if (transport == VM_RUNTIME_OVERLAY_OK)\n"
        "            return rtov_fail(VM_RUNTIME_OVERLAY_ERR_ISLAND);",
        "rtov_busy = 0;\n        return transport;",
        "the outer\n         * Island lifecycle adds FAILED state and destination cleanup",
    )
    for token in exact:
        require(source.count(token) == 1,
                f"first-status source invariant absent/duplicated: {token}")
    require("rtov_fault = VM_RUNTIME_OVERLAY_ERR_ISLAND;" not in source,
            "outer Island lifecycle still overwrites the inner status")
    mutated = source.replace(
        "rtov_busy = 0;\n        return transport;",
        "rtov_fault = VM_RUNTIME_OVERLAY_ERR_ISLAND;\n"
        "        rtov_busy = 0;\n"
        "        return VM_RUNTIME_OVERLAY_ERR_ISLAND;", 1)
    try:
        first_status_source_gate(mutated)
    except LinkError:
        mutation = "rejected"
    else:
        raise LinkError("generic outer-status overwrite mutation accepted")
    return {
        "status": "passed-first-innermost-transport-status-wins",
        "generic_result_mapping": "retained only when transport itself succeeded",
        "outer_overwrite_mutation": mutation,
    }


def host_command(source: Path, binary: Path) -> list[str]:
    return [
        "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined",
        "-DLISP65_VM", "-DLISP65_RUNTIME_OVERLAY_HOST_TEST",
        "-DLISP65_RUNTIME_OVERLAY_CATALOG_VERSION=2",
        "-DLISP65_RUNTIME_OVERLAY_FORMAT_V2",
        "-DLISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_STORAGE_BASE=0x08200000UL",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_OFF=0x0500u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_SIZE=8u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_ENTRY_OFFSET=0u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_CRC16=0x37e8u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_OFF=0x0600u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_SIZE=8u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_ENTRY_OFFSET=0u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_CRC16=0x5afbu",
        "-DLISP65_RUNTIME_ISLAND_INSTALL_SLOT=8",
        "-DLISP65_RUNTIME_ISLAND_CARRIER_SLOT=9",
        "-I" + str(ROOT / "src"), str(HOST_MAIN), str(source),
        "-o", str(binary),
    ]


def first_status_host_gate(out: Path) -> dict[str, Any]:
    gate = out / "first-status-host-gate"
    gate.mkdir(parents=True, exist_ok=False)
    source_text = SOURCE.read_text(encoding="utf-8")
    source_result = first_status_source_gate(source_text)
    binary = gate / "first-status-positive"
    subprocess.run(host_command(SOURCE, binary), cwd=ROOT, check=True)
    env = {**os.environ, "ASAN_OPTIONS": "detect_leaks=1",
           "UBSAN_OPTIONS": "halt_on_error=1"}
    positive = subprocess.run([str(binary)], cwd=ROOT, env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=False)
    require(positive.returncode == 0
            and "PASS publish-last+12 fail-closed cases" in positive.stdout,
            "first-status positive host matrix failed: " + positive.stderr)
    (gate / "positive.stdout.txt").write_text(positive.stdout, encoding="utf-8")

    old = (
        "rtov_busy = 0;\n"
        "        return transport;")
    replacement = (
        "rtov_fault = VM_RUNTIME_OVERLAY_ERR_ISLAND;\n"
        "        rtov_busy = 0;\n"
        "        return VM_RUNTIME_OVERLAY_ERR_ISLAND;")
    require(source_text.count(old) == 1,
            "first-status negative source anchor drift")
    mutated_source = gate / "vm_runtime_overlay.generic-outer-negative.c"
    mutated_source.write_text(source_text.replace(old, replacement, 1),
                              encoding="utf-8")
    negative_binary = gate / "first-status-generic-outer-negative"
    subprocess.run(host_command(mutated_source, negative_binary),
                   cwd=ROOT, check=True)
    negative = subprocess.run(
        [str(negative_binary)], cwd=ROOT, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(negative.returncode != 0
            and "FAIL v1 rejected with inner VERSION status" in negative.stderr,
            "generic outer-status mutation did not reproduce the semantic red")
    (gate / "negative.stderr.txt").write_text(
        negative.stderr, encoding="utf-8")
    return {
        "status": "passed-positive-and-generic-overwrite-negative",
        "source_gate": source_result,
        "asan": "passed", "ubsan": "passed",
        "positive_cases": 12,
        "specific_status_fixture": "ERR_VERSION survives outer Island cleanup",
        "negative_mutation": "generic ERR_ISLAND overwrite reproduced red",
        "positive_binary": bind(binary),
        "positive_stdout": bind(gate / "positive.stdout.txt"),
        "negative_binary": bind(negative_binary),
        "negative_stderr": bind(gate / "negative.stderr.txt"),
        "mutated_source": bind(mutated_source),
    }


def prerequisites() -> dict[str, Any]:
    expected = {REPLAY: REPLAY_SHA, LINK34_PRODUCT: LINK34_SHA}
    for path, digest in expected.items():
        require(path.is_file() and sha(path) == digest,
                f"combined successor prerequisite drift: {path}")
    replay = json.loads(REPLAY.read_text(encoding="utf-8"))
    require(replay.get("status") ==
            "passed-artifact-only-structured-relocation-leaf-replay"
            and replay["execution_accounting"] == {
                "artifact_only_replays": 1, "compiler_runs": 0,
                "hardware_runs": 0, "linker_runs": 0},
            "DMA completion leaf pure replay is not complete green")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract["error_status"]["rule"] ==
            "first innermost status wins",
            "first-status contract drift")
    return {
        "completion_leaf_pure_replay": bind(REPLAY),
        "completion_contract": bind(CONTRACT),
        "completion_contract_document": bind(CONTRACT_DOC),
        "completion_leaf_source": bind(LEAF.LEAF),
        "elf_truth_layer": bind(ROOT / "tools/host-lisp/elf_truth.py"),
        "link34_rollback": {
            "structural_receipt": bind(LINK34_RECEIPT),
            "product": bind(LINK34_PRODUCT),
            "status": "untouched-until-successor-fully-green",
        },
    }


def bind_first_red(error: BaseException, prereq: dict[str, Any]) -> dict[str, Any]:
    value = {
        "format": "lisp65-c2-product-link35-completion-status-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: combined DMA-completion/status successor stopped",
        "promotable": False,
        "diagnostic": {"type": type(error).__name__, "message": str(error)},
        "execution_accounting": {
            "product_closure_links": int(
                (OUT / "lisp65-c2-substitution-linked.prg").is_file()),
            "hardware_runs": 0,
        },
        "prerequisites": prereq,
        "evidence": evidence_tree(OUT) if OUT.is_dir() else {},
        "rollback_line": {"link34_sha256": LINK34_SHA, "status": "untouched"},
        "next_gate": "return to review; no retry and no hardware presmoke",
    }
    write_json(RECEIPT, value)
    os.chmod(RECEIPT, 0o444)
    if OUT.is_dir():
        protect(OUT)
    return value


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "combined successor link is one-shot and already has output")
    BASE.configure()
    prereq = prerequisites()
    try:
        host = first_status_host_gate(OUT)
        leaf_source = LEAF.prerequisites()
        fresh = BASE.PRE.check(OUT / "fresh-v5-prelink-gates")
        require(fresh["status"] == "passed-prelink-product-link-not-run"
                and fresh["b2_model"]["cases"] == 18,
                "fresh nested-append/B2 prelink gates failed")
        BASE.P.single_link(
            OUT, probe_definitions=FEATURES,
            direct_entry_receipt=BASE.DIRECT.RECEIPT,
            direct_entry_check_tool="c2_hot_refill_direct_entry_contract.py",
            extra_contract_lines=(
                "mode=link35-dma-completion-first-status-successor",
                "feature_defines=" + ",".join(FEATURES),
                "dma_completion_leaf_replay_sha256=" + REPLAY_SHA,
                "error_status_rule=first-innermost-status-wins",
                "append_abi=v5-high-edge-transient-c2j",
                "append_slice_count=" + str(len(BASE.P.C2_APPEND_SLICES)),
                "fixed_facade_vector_count=15",
                "final_e000_floor_bytes=115",
                "green_inheritance=none",
            ))
        product = OUT / "lisp65-c2-substitution-linked.prg"
        elf = Path(str(product) + ".elf")
        structure = json.loads(
            (OUT / "product-substitution-link.json").read_text(encoding="utf-8"))
        total = json.loads(
            (OUT / "total-publish-last-domain.json").read_text(encoding="utf-8"))
        required = (
            "identity_gate", "capacity_gate", "one_truth_gate",
            "kernal_freedom_gate", "fixed_host_facade_gate",
            "pre_ownership_gate", "handoff_z_abi_gate",
        )
        require(structure.get("status") == "passed"
                and structure.get("product_closure_link_count") == 1
                and all(structure.get(name) == "passed" for name in required),
                "combined successor product closure is not fully green")
        require(total.get("status") == "passed"
                and total.get("declared_domain_bytes") == 34,
                "combined successor publish-last domain drift")
        capacity, sections = BASE.capacity(elf, OUT)
        baseline = json.loads(
            LINK34_RECEIPT.read_text(encoding="utf-8"))["capacity"]
        LEAF.capacity_gate(capacity, baseline)
        completion = LEAF.elf_gate(elf)
        closure = BASE.LINK33_BASE.final_overlay_closure(elf)
        preinstall = BASE.ISLAND.static_elf_gate(elf)
        hot = BASE.HOT.direct_path_gate(elf)
        require(sha(product) != LINK34_SHA,
                "combined successor did not create a new product identity")
        crc_codegen = json.loads(
            (OUT / "c2-crc-codegen-gate.json").read_text(encoding="utf-8"))
        crc_leaf = json.loads(
            (OUT / "c2-crc-asm-leaf-gate.json").read_text(encoding="utf-8"))
        f011 = json.loads(
            (OUT / "c2-f011-mount-window-gate.json").read_text(encoding="utf-8"))
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
            "dma_completion_leaf": completion["status"],
            "first_status_host": host["status"],
        }
        require(all("pass" in status for status in fresh_gates.values()),
                f"combined successor fresh gate set red: {fresh_gates}")
        value = {
            "format": "lisp65-c2-product-link35-completion-status-structural-v1",
            "recorded_on": "2026-07-21",
            "status": "passed-new-product-identity-hardware-not-run",
            "promotable": False,
            "link_number": 35,
            "inheritance": "none; every structural and capacity gate ran freshly",
            "execution_accounting": {
                "host_semantic_compiles": 2,
                "resident_island_seed_links": 1,
                "product_closure_links": 1,
                "hardware_runs": 0,
            },
            "prerequisites": prereq,
            "product_identity": {
                "product": bind(product), "elf": bind(elf),
                "resolved_profile": bind(OUT / "resolved-profile.txt"),
                "predecessor_link34_sha256": LINK34_SHA,
                "new_identity": True,
            },
            "fresh_gates": fresh_gates,
            "dma_completion": {
                "source_and_mutations": leaf_source,
                "linked_leaf": completion,
                "hard_e000_delta_bytes": 0,
            },
            "first_status_wins": host,
            "post_link_identity": {
                "declared_mutable_product_bytes": total["declared_domain_bytes"],
                "actual_changed_bytes": total["actual_changed_bytes"],
                "status": total["status"],
            },
            "nested_append_v5": {
                "b2_run_stop_cases": fresh["b2_model"]["cases"],
                "final_overlay_closure": closure,
            },
            "preinstallation_Island": preinstall,
            "hot_refill": hot,
            "capacity": capacity,
            "section_count": len(sections),
            "rollback_line": {
                "link34_product_sha256": LINK34_SHA,
                "status": "untouched-and-still-readable",
            },
            "claim_limit": (
                "Fresh combined product identity and structural/capacity closure "
                "only. Hardware, latency, nested eval, GC cost, Freezer identity, "
                "promotion and acceptance remain not-run."),
            "next_gate": "hardware presmoke from line 1",
        }
        report = OUT / "link35-dma-completion-first-status-structural.json"
        write_json(report, value)
        receipt = {**value, "structural_report": bind(report),
                   "evidence_file_count": len(evidence_tree(OUT))}
        write_json(RECEIPT, receipt)
        os.chmod(RECEIPT, 0o444)
        protect(OUT)
        return receipt
    except Exception as error:
        return bind_first_red(error, prereq)


def check() -> dict[str, Any]:
    receipt = REPLAY_RECEIPT if REPLAY_RECEIPT.is_file() else RECEIPT
    require(receipt.is_file(), "combined successor receipt absent")
    value = json.loads(receipt.read_text(encoding="utf-8"))
    require(value.get("status") in {
        "passed-new-product-identity-hardware-not-run",
        "passed-artifact-only-link35-preinstall-dataflow-replay",
        "FIRST RED: combined DMA-completion/status successor stopped"},
        "combined successor receipt status unknown")
    require(sha(LINK34_PRODUCT) == LINK34_SHA, "Link-34 rollback drift")
    if value["status"].startswith("passed"):
        for name in ("product", "elf", "resolved_profile"):
            row = value["product_identity"][name]
            require(bind(ROOT / row["path"]) == row,
                    f"combined successor identity drift: {name}")
    return value


def replay() -> dict[str, Any]:
    require(not REPLAY_RECEIPT.exists(),
            "Link-35 preinstall pure replay is one-shot and already consumed")
    BASE.configure()
    expected = {
        RECEIPT: "cd4b2e78751c06bc2ea55e56449018f448f34353cd05fd61a3dc7cf452e69d42",
        DIAGNOSIS: "b37ba5507fbad1dc66de43ca8c59c85994423a475f0f2229bfbc345712d55a7f",
        OUT / "lisp65-c2-substitution-linked.prg":
            "54c731559fdb72d5d1cb8478b9da7e78a422741e4e5267d64b07fe4c6f763a65",
        OUT / "lisp65-c2-substitution-linked.prg.elf":
            "b7cd1aac14c569fdb3e9f3e08a072a5909b34f0fbcf4f2f10ac6e435d5781d0f",
        OUT / "product-substitution-link.json":
            "e80913375d89e1fcca6714bdbd7f5a0592f882b68895cbe8262f442547337990",
    }
    for path, digest in expected.items():
        require(path.is_file() and sha(path) == digest,
                f"Link-35 pure-replay authority drift: {path}")
    first_red = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(first_red.get("status") ==
            "FIRST RED: combined DMA-completion/status successor stopped"
            and first_red["execution_accounting"] == {
                "hardware_runs": 0, "product_closure_links": 1},
            "Link-35 First Red accounting drift")
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    structure = json.loads(
        (OUT / "product-substitution-link.json").read_text(encoding="utf-8"))
    total = json.loads(
        (OUT / "total-publish-last-domain.json").read_text(encoding="utf-8"))
    required = (
        "identity_gate", "capacity_gate", "one_truth_gate",
        "kernal_freedom_gate", "fixed_host_facade_gate",
        "pre_ownership_gate", "handoff_z_abi_gate",
    )
    require(structure.get("status") == "passed"
            and all(structure.get(name) == "passed" for name in required),
            "bound Link-35 structural report is not green")
    require(total.get("status") == "passed"
            and total.get("declared_domain_bytes") == 34,
            "bound Link-35 publish-last report drift")
    capacity, sections = BASE.capacity(elf, OUT)
    baseline = json.loads(
        LINK34_RECEIPT.read_text(encoding="utf-8"))["capacity"]
    LEAF.capacity_gate(capacity, baseline)
    completion = LEAF.elf_gate(elf)
    closure = BASE.LINK33_BASE.final_overlay_closure(elf)
    preinstall = BASE.ISLAND.static_elf_gate(elf)
    hot = BASE.HOT.direct_path_gate(elf)
    require(preinstall.get("status") ==
            "passed-static-preinstallation-Island-gate",
            "corrected preinstall dataflow gate is not green")
    host_rows = first_red["evidence"]
    for name in (
            "first-status-host-gate/first-status-positive",
            "first-status-host-gate/first-status-generic-outer-negative",
            "first-status-host-gate/positive.stdout.txt",
            "first-status-host-gate/negative.stderr.txt"):
        row = host_rows[name]
        path = OUT / name
        require(path.is_file() and sha(path) == row["sha256"],
                f"bound first-status host evidence drift: {name}")
    fresh_gates = {
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
        "first_status_host": "passed-positive-and-generic-overwrite-negative",
    }
    require(all("pass" in status for status in fresh_gates.values()),
            f"Link-35 pure-replay gate set red: {fresh_gates}")
    result = {
        "format": "lisp65-c2-product-link35-dataflow-pure-replay-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-artifact-only-link35-preinstall-dataflow-replay",
        "promotable": False,
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0, "hardware_runs": 0,
            "artifact_only_replays": 1,
        },
        "authority": {
            "first_red_receipt": bind(RECEIPT),
            "first_red_diagnosis": bind(DIAGNOSIS),
            "preinstall_gate": bind(
                ROOT / "tools/host-lisp/c2_preinstall_island_guard.py"),
            "immutable_inputs": [bind(path) for path in expected],
        },
        "product_identity": {
            "product": bind(product), "elf": bind(elf),
            "resolved_profile": bind(OUT / "resolved-profile.txt"),
            "new_identity_vs_link34": True,
        },
        "fresh_artifact_only_gates": fresh_gates,
        "preinstallation_Island": preinstall,
        "dma_completion": completion,
        "first_status_wins": {
            "status": "passed-positive-and-generic-overwrite-negative",
            "specific_status_fixture": "ERR_VERSION survives outer cleanup",
            "positive_cases": 12,
            "asan": "passed", "ubsan": "passed",
            "generic_overwrite_mutation": "reproduced red",
        },
        "post_link_identity": {
            "declared_mutable_product_bytes": total["declared_domain_bytes"],
            "actual_changed_bytes": total["actual_changed_bytes"],
            "status": total["status"],
        },
        "capacity": capacity,
        "section_count": len(sections),
        "hard_capacity_contract": {
            "e000_floor_bytes": 115, "e000_delta_bytes": 0,
        },
        "rollback_line": {**bind(LINK34_PRODUCT), "status": "untouched"},
        "claim_limit": (
            "Artifact-only replay of the corrected preinstall register-dataflow "
            "gate. No compiler, linker, hardware, promotion or acceptance claim."),
        "next_gate": "hardware presmoke from line 1",
    }
    write_json(REPLAY_RECEIPT, result)
    os.chmod(REPLAY_RECEIPT, 0o444)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "run", "replay", "check"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            BASE.configure()
            bound = prerequisites()
            source = first_status_source_gate(
                SOURCE.read_text(encoding="utf-8"))
            leaf = LEAF.prerequisites()
            print("c2-completion-first-status-successor: SELFTEST PASS "
                  f"prereq={len(bound)} mutations="
                  f"{1 + len(leaf['mutation_matrix'])} status={source['status']}")
            return 0
        if args.action == "run":
            value = build()
        elif args.action == "replay":
            value = replay()
        else:
            value = check()
        print("c2-completion-first-status-successor: " + value["status"])
        return 3 if value["status"].startswith("FIRST RED") else 0
    except Exception as error:
        print("c2-completion-first-status-successor: FAIL " + str(error),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
