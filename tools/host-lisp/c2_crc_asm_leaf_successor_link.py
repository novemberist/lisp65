#!/usr/bin/env python3
"""Build the one authorized Link-34 successor with the MOS CRC leaf."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_historical_gate_inheritance as INHERITANCE  # noqa: E402
import c2_link33_bss_triage_product_link as BASE  # noqa: E402


OUT = ROOT / "build/c2.2/substitution/product-link-34-crc-asm-leaf"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link34-crc-asm-leaf-structural-receipt.json")
REPLAY = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-crc-asm-leaf-wplto-pure-replay-receipt.json")
REPLAY_SHA = "591d1e9cb436da2101f4dd77e76f14e82f1df7d95c44f30fbf81bc92e3614433"
DIAGNOSIS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-crc-asm-leaf-wplto-harness-first-red-diagnosis.json")
DIAGNOSIS_SHA = "9f5f0c51b042cc6b05d801f1f7509000578e753fda514584e75912e8d71cc5b7"
LINK33_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link33-handoff-reanchor-structural-receipt.json")
LINK33_RECEIPT_SHA = (
    "212339a2c53c1d11aebe0833108d0036cc95d7dd9b465346c842071cf7131840")
LINK33 = ROOT / (
    "build/c2.2/substitution/product-link-33-handoff-reanchor-final/"
    "lisp65-c2-substitution-linked.prg")
LINK33_SHA = "5f44b65a1a67530a9c3c8b687d7be597422978ae749f56101f42bdcebaf50044"
CRC_LEAF = ROOT / "src/rtov_crc_mem.s"
CRC_LEAF_SHA = "6282f6f0f88b81f57f4c4cc85f396ae3d25e5262ba23e650761c48778601b826"
PRODUCT_DRIVER = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
PRODUCT_DRIVER_SHA = (
    "cfb3c3dfb6dcec33e1c22c6eef8bb685ac56f3361231e9ae4fbb79b6d1026835")
INHERITANCE_RECEIPT = INHERITANCE.RECEIPT
INHERITANCE_SHA = (
    "b5748c1ef4c81e014dc288f7eabcd56b3ab6af08d8c4896c554f869d483feb6b")


class LinkError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LinkError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"Link-34 prerequisite absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def prerequisites() -> dict[str, Any]:
    exact = {
        REPLAY: REPLAY_SHA,
        DIAGNOSIS: DIAGNOSIS_SHA,
        LINK33_RECEIPT: LINK33_RECEIPT_SHA,
        LINK33: LINK33_SHA,
        CRC_LEAF: CRC_LEAF_SHA,
        PRODUCT_DRIVER: PRODUCT_DRIVER_SHA,
        INHERITANCE_RECEIPT: INHERITANCE_SHA,
    }
    for path, expected in exact.items():
        require(path.is_file() and sha(path) == expected,
                f"Link-34 bound prerequisite drift: {path}")
    replay = json.loads(REPLAY.read_text(encoding="utf-8"))
    require(replay.get("status") ==
            "passed-crc-asm-leaf-wplto-pure-replay-no-product-link"
            and replay["scope"]["compiler_invocations"] == 0
            and replay["scope"]["linker_invocations"] == 0
            and replay["replay"]["resident_walls"] == {
                "bank0_text_headroom_bytes": 55,
                "ordinary_bank0_bss_headroom_bytes": 195,
                "fixed_hot_block_headroom_bytes": 33,
                "resident_island_headroom_bytes": 7,
                "e000_headroom_bytes": 115,
            }, "CRC assembler-leaf pure replay is not complete green")
    old = json.loads(LINK33_RECEIPT.read_text(encoding="utf-8"))
    require(old.get("status") == "passed-new-product-identity-hardware-not-run"
            and old["product_identity"]["product"]["sha256"] == LINK33_SHA,
            "Link-33 rollback receipt is not green")
    inherited = INHERITANCE.check(write_receipt=False)
    require(inherited["unresolved_entries"] == 0
            and inherited["migrated_into_every_c2_product_link"] == [
                "f011-mount-window", "runtime-crc-codegen"],
            "historical gate inheritance is not closed")
    return {
        "crc_asm_leaf_pure_replay": bind(REPLAY),
        "crc_asm_leaf_first_red_diagnosis": bind(DIAGNOSIS),
        "crc_asm_leaf_source": bind(CRC_LEAF),
        "central_product_driver": bind(PRODUCT_DRIVER),
        "historical_gate_inheritance": bind(INHERITANCE_RECEIPT),
        "link33_rollback": {
            "structural_receipt": bind(LINK33_RECEIPT),
            "product": bind(LINK33),
            "status": "untouched-until-link34-fully-green",
        },
        "product_profile": BASE.PROFILE.receipt_identity(),
    }


def evidence_tree(out: Path) -> dict[str, dict[str, Any]]:
    return {path.relative_to(out).as_posix(): {
                "bytes": path.stat().st_size,
                "sha256": sha(path),
            } for path in sorted(out.rglob("*")) if path.is_file()}


def protect(out: Path) -> None:
    for path in out.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    for path in sorted((p for p in out.rglob("*") if p.is_dir()),
                       key=lambda p: len(p.parts), reverse=True):
        os.chmod(path, 0o555)
    os.chmod(out, 0o555)


def bind_first_red(error: Exception, prereq: dict[str, Any]) -> dict[str, Any]:
    value = {
        "format": "lisp65-c2-product-link34-crc-asm-leaf-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: fresh Link 34 failed",
        "diagnostic": {"type": type(error).__name__, "message": str(error)},
        "link_number": 34,
        "execution_accounting": {
            "product_closure_links": int(
                (OUT / "lisp65-c2-substitution-linked.prg").is_file()),
            "hardware_runs": 0,
        },
        "prerequisites": prereq,
        "evidence": evidence_tree(OUT) if OUT.is_dir() else {},
        "rollback_line": {"link33_sha256": LINK33_SHA, "status": "untouched"},
        "next_gate": "return to review; no retry or hardware presmoke",
    }
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    if OUT.is_dir():
        protect(OUT)
    return value


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "fresh Link 34 is one-shot and already has output")
    BASE.configure()
    prereq = prerequisites()
    try:
        fresh = BASE.PRE.check(OUT / "fresh-v5-prelink-gates")
        require(fresh["status"] == "passed-prelink-product-link-not-run"
                and fresh["b2_model"]["cases"] == 18,
                "FIRST RED: fresh nested-append/B2 prelink gates failed")
        BASE.P.single_link(
            OUT, probe_definitions=BASE.FEATURES,
            direct_entry_receipt=BASE.DIRECT.RECEIPT,
            direct_entry_check_tool="c2_hot_refill_direct_entry_contract.py",
            extra_contract_lines=(
                "mode=link34-crc-asm-leaf-successor",
                "feature_defines=" + ",".join(BASE.FEATURES),
                "product_profile_object="
                + BASE.PROFILE.PROFILE.relative_to(ROOT).as_posix(),
                "product_profile_object_sha256=" + BASE.PROFILE.sha256(),
                "crc_asm_leaf_sha256=" + CRC_LEAF_SHA,
                "crc_asm_leaf_replay_sha256=" + REPLAY_SHA,
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
                "FIRST RED: generic Link-34 closure is not fully green")
        require(structure.get("crc_codegen_gate") ==
                "passed-target-stable-bytewise-crc-loop"
                and structure.get("identity_components", {}).get(
                    "crc_assembler_leaf") ==
                "passed-linked-assembler-leaf-crc-equivalence",
                "FIRST RED: Link-34 CRC leaf gates are not fresh green")
        require(total.get("status") == "passed"
                and total.get("declared_domain_bytes") == 34,
                "FIRST RED: Link-34 34-byte publish-last domain drift")
        capacity, sections = BASE.capacity(elf, OUT)
        closure = BASE.LINK33_BASE.final_overlay_closure(elf)
        preinstall = BASE.ISLAND.static_elf_gate(elf)
        hot = BASE.HOT.direct_path_gate(elf)
        require(preinstall.get("status") ==
                "passed-static-preinstallation-Island-gate",
                "FIRST RED: Link-34 preinstallation-Island gate red")
        require(capacity["e000"]["equations"] == [
                    "531 - 416 = 115", "416 + 6 = 422"],
                "FIRST RED: Link-34 E000 transition not explicitly proved")
        require(sha(product) != LINK33_SHA,
                "FIRST RED: Link-34 did not create a new product identity")
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
        }
        require(all("pass" in status for status in fresh_gates.values()),
                f"FIRST RED: Link-34 fresh gate set red: {fresh_gates}")
        value = {
            "format": "lisp65-c2-product-link34-crc-asm-leaf-structural-v1",
            "recorded_on": "2026-07-21",
            "status": "passed-new-product-identity-hardware-not-run",
            "link_number": 34,
            "inheritance": "none; every structural and capacity gate ran freshly",
            "execution_accounting": {
                "fresh_nonproduct_target_compiles": 2,
                "resident_island_seed_links": 1,
                "product_closure_links": 1,
                "hardware_runs": 0,
            },
            "prerequisites": prereq,
            "product_identity": {
                "product": bind(product), "elf": bind(elf),
                "resolved_profile": bind(OUT / "resolved-profile.txt"),
                "predecessor_link33_sha256": LINK33_SHA,
                "new_identity": True,
            },
            "fresh_gates": fresh_gates,
            "crc_leaf": {
                "source": bind(CRC_LEAF),
                "codegen": crc_codegen,
                "equivalence": crc_leaf,
            },
            "post_link_identity": {
                "declared_mutable_product_bytes": total["declared_domain_bytes"],
                "actual_changed_bytes": total["actual_changed_bytes"],
                "status": total["status"],
            },
            "nested_append_v5": {
                "append_slice_count": len(BASE.P.C2_APPEND_SLICES),
                "session_slice_count": len(BASE.P.SESSION_SLICE_SPECS),
                "b2_run_stop_cases": fresh["b2_model"]["cases"],
                "final_overlay_closure": closure,
            },
            "preinstallation_Island": preinstall,
            "hot_refill": hot,
            "capacity": capacity,
            "section_count": len(sections),
            "rollback_line": {
                "link33_product_sha256": LINK33_SHA,
                "status": "untouched-and-still-readable",
            },
            "claim_limit": (
                "Fresh Link-34 product identity and complete structural and "
                "capacity closure only. Hardware, latency, nested-eval smoke, "
                "GC read cost, Freezer identity, promotion and acceptance "
                "remain not-run."),
            "next_gate": "authorized hardware presmoke from line 1",
        }
        report = OUT / "link34-crc-asm-leaf-structural.json"
        report.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
        receipt = {**value, "structural_report": bind(report),
                   "evidence_file_count": len(evidence_tree(OUT))}
        RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        os.chmod(RECEIPT, 0o444)
        protect(OUT)
        return receipt
    except (LinkError, BASE.LinkError, BASE.PRE.GateError,
            BASE.ISLAND.GateError, RuntimeError, OSError, ValueError,
            KeyError, json.JSONDecodeError) as error:
        return bind_first_red(error, prereq)


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "Link-34 receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") in {
        "passed-new-product-identity-hardware-not-run",
        "FIRST RED: fresh Link 34 failed"}, "Link-34 receipt status unknown")
    require(sha(LINK33) == LINK33_SHA, "Link-33 rollback identity drift")
    if value["status"].startswith("passed"):
        for name in ("product", "elf", "resolved_profile"):
            row = value["product_identity"][name]
            require(sha(ROOT / row["path"]) == row["sha256"],
                    f"Link-34 product identity drift: {name}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        BASE.configure()
        bound = prerequisites()
        require(BASE.P.HANDOFF_BASE == 0xB4A3
                and BASE.P.E000_FINAL_FLOOR_BYTES == 115,
                "Link-34 geometry selftest drift")
        print("c2-crc-asm-leaf-successor-link: SELFTEST PASS prereq="
              + str(len(bound)))
        return 0
    value = build() if args.action == "run" else check()
    print("c2-crc-asm-leaf-successor-link: " + value["status"])
    return 3 if value["status"].startswith("FIRST RED") else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (LinkError, BASE.LinkError, BASE.PRE.GateError,
            BASE.ISLAND.GateError, OSError, ValueError, KeyError,
            RuntimeError, json.JSONDecodeError) as error:
        print("c2-crc-asm-leaf-successor-link: FAIL " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
