#!/usr/bin/env python3
"""One product-shaped WPLTO probe for the Link-33 CRC codegen correction."""

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
import c2_crc_codegen_gate as CRC  # noqa: E402
import c2_historical_gate_inheritance as INHERITANCE  # noqa: E402
import c2_l65r_v2_boot_family_probe as BOOT  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402
import f011_mount_window as F011  # noqa: E402


OUT = ROOT / "build/c2.2/substitution/link33-crc-codegen-correction-wplto"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-crc-codegen-correction-wplto-probe-receipt.json")
LINK33_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link33-handoff-reanchor-structural-receipt.json")
LINK33_RECEIPT_SHA = (
    "212339a2c53c1d11aebe0833108d0036cc95d7dd9b465346c842071cf7131840")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link33-crc-loop-hardware-first-red-diagnosis.json")
FIRST_RED_SHA = (
    "7b644e0aaa8ffcbf48c2aaaec444f5dfa232ac27871f53813793d72c03d89e06")
INHERITANCE_RECEIPT = INHERITANCE.RECEIPT
INHERITANCE_RECEIPT_SHA = (
    "55a342d3cc9c7e1e2bbc52f6c9cae61a0928cdc9be52a0001b47659b2fb8b7bf")
LINK33_PRODUCT = ROOT / (
    "build/c2.2/substitution/product-link-33-handoff-reanchor-final/"
    "lisp65-c2-substitution-linked.prg")
LINK33_PRODUCT_SHA = (
    "5f44b65a1a67530a9c3c8b687d7be597422978ae749f56101f42bdcebaf50044")
OLD_WALLS = {
    "bank0_text_headroom_bytes": 32,
    "ordinary_bank0_bss_headroom_bytes": 195,
    "fixed_hot_block_headroom_bytes": 33,
    "resident_island_headroom_bytes": 7,
    "e000_headroom_bytes": 115,
}


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"probe prerequisite absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def prerequisites() -> dict[str, Any]:
    require(sha(LINK33_RECEIPT) == LINK33_RECEIPT_SHA,
            "Link-33 structural receipt drift")
    current = json.loads(LINK33_RECEIPT.read_text(encoding="utf-8"))
    require(current.get("status") ==
            "passed-new-product-identity-hardware-not-run"
            and current.get("capacity", {}).get(
                "bank0_text_headroom_bytes") == 32,
            "Link-33 structural baseline is not applicable")
    require(sha(FIRST_RED) == FIRST_RED_SHA,
            "CRC-loop hardware First Red drift")
    diagnosis = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(diagnosis.get("status") ==
            "first-red-receipt-less-hardware-presmoke-stopped-at-boot"
            and diagnosis["evidence"]["product"]["sha256"] ==
            LINK33_PRODUCT_SHA
            and diagnosis["next_decision"][
                "automatic_fix_or_link_authorized"] is False,
            "CRC-loop diagnosis does not bind the expected First Red")
    require(sha(LINK33_PRODUCT) == LINK33_PRODUCT_SHA,
            "Link-33 product rollback identity drift")
    require(sha(INHERITANCE_RECEIPT) == INHERITANCE_RECEIPT_SHA,
            "historical gate-inheritance receipt drift")
    inherited = INHERITANCE.check(write_receipt=False)
    require(inherited["unresolved_entries"] == 0
            and inherited["migrated_into_every_c2_product_link"] == [
                "f011-mount-window", "runtime-crc-codegen"],
            "historical gate inheritance is not closed")
    return {
        "link33_structural_baseline": bind(LINK33_RECEIPT),
        "link33_crc_hardware_first_red": bind(FIRST_RED),
        "historical_gate_inheritance": bind(INHERITANCE_RECEIPT),
        "rollback_product": {**bind(LINK33_PRODUCT), "status": "untouched"},
        "source_fix": bind(ROOT / "src/vm_runtime_overlay.c"),
        "crc_codegen_gate": bind(ROOT / "tools/host-lisp/c2_crc_codegen_gate.py"),
    }


def attribution(probe_map: Path) -> dict[str, Any]:
    probe_elf = Path(str(probe_map).removesuffix(".map") + ".elf")
    old_elf = Path(str(LINK33_PRODUCT) + ".elf")

    def symbol(path: Path) -> dict[str, int | str]:
        truth = CRC.ElfTruth.read(
            path, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
        row = truth.symbol(CRC.CRC)
        return {"address": row.value, "bytes": row.bytes,
                "section": row.section}

    return {
        "kind": "whole-program-linked-function-attribution",
        "baseline": {"elf": bind(old_elf), "rtov_crc_mem": symbol(old_elf)},
        "probe": {"elf": bind(probe_elf), "rtov_crc_mem": symbol(probe_elf)},
    }


def run_once() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "CRC correction WPLTO probe is one-shot and already consumed")
    authority = prerequisites()
    BOOT.BASE.configure()
    require(P.HANDOFF_BASE == 0xB4A3
            and P.E000_FINAL_FLOOR_BYTES == 115
            and P.fixed_bank0_headroom_bytes() == 33,
            "canonical Link-33 geometry drift before WPLTO probe")
    source = (ROOT / "src/vm_runtime_overlay.c").read_text(encoding="utf-8")
    require(source.count('__asm__ volatile("dec %0"') == 2
            and "while (length--)" not in source,
            "target-stable byte-decrement source shape is absent")
    CRC.selftest()
    F011.selftest()

    original = {
        "OUT": BOOT.OUT,
        "RECEIPT": BOOT.RECEIPT,
        "prerequisites": BOOT.prerequisites,
        "attribution": BOOT.attribution,
        "protect": BOOT.BASE.protect,
    }
    BOOT.OUT, BOOT.RECEIPT = OUT, RECEIPT
    BOOT.prerequisites = prerequisites
    BOOT.attribution = attribution
    BOOT.BASE.protect = lambda _path: None
    try:
        base = BOOT.run_once()
    finally:
        BOOT.OUT, BOOT.RECEIPT = original["OUT"], original["RECEIPT"]
        BOOT.prerequisites = original["prerequisites"]
        BOOT.attribution = original["attribution"]
        BOOT.BASE.protect = original["protect"]

    os.chmod(RECEIPT, 0o644)
    if str(base.get("status", "")).startswith("FIRST RED"):
        base.update({
            "format": "lisp65-c2-crc-codegen-correction-wplto-first-red-v1",
            "status": "FIRST RED: CRC correction WPLTO probe stopped",
            "authority": authority,
            "next_gate": "review; no product link or hardware retry",
        })
        RECEIPT.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        original["protect"](OUT)
        os.chmod(RECEIPT, 0o444)
        return base

    target = ROOT / base["artifacts"]["probe_prg"]["path"]
    elf = Path(str(target) + ".elf")
    try:
        crc_gate = CRC.audit_elf(
            elf, out=OUT / "c2-crc-codegen-correction-gate.json")
        f011 = F011.audit(F011.disassemble(
            ROOT / "tools/llvm-mos/bin/llvm-objdump", elf))
        (OUT / "c2-f011-mount-window-gate.json").write_text(
            json.dumps(f011, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        walls = base["resident_walls"]
        require(all(int(value) >= 0 for value in walls.values()),
                f"CRC correction resident wall red: {walls}")
        require(walls["e000_headroom_bytes"] == 115,
                "closed E000 floor changed during CRC correction")
        require(all(value == "passed" for value in
                    base["fresh_structural_gates"].values()),
                "one or more inherited structural gates are not fresh green")
        wall_deltas = {
            name: int(walls[name]) - old
            for name, old in OLD_WALLS.items()
        }
        value = {
            **base,
            "format": "lisp65-c2-crc-codegen-correction-wplto-probe-v1",
            "status": "passed-crc-codegen-correction-wplto-no-product-link",
            "authority": authority,
            "target_stable_crc": crc_gate,
            "migrated_f011_window": f011,
            "capacity_delta_vs_link33": wall_deltas,
            "standing_text_noise_reserve": {
                "before_bytes": 32,
                "after_bytes": walls["bank0_text_headroom_bytes"],
                "consumed_bytes": 32 - walls["bank0_text_headroom_bytes"],
                "status": "measured-not-borrowed",
            },
            "gate_mutations": {
                "crc_codegen": CRC.selftest(),
                "f011": "existing-trigger-mutation-rejected",
            },
            "scope": {
                **base["scope"],
                "authorized_wplto_probes": 1,
                "actual_wplto_probes": 1,
                "product_closure_links": 0,
                "product_candidates": 0,
                "hardware_runs": 0,
            },
            "claim_limit": (
                "One product-shaped WPLTO capacity, placement and gate probe. "
                "No successor product identity, hardware execution, latency, "
                "promotion or acceptance claim."),
            "next_gate": (
                "Return for separate authorization of one successor product "
                "link; hardware remains blocked."),
        }
    except (CRC.GateError, F011.AuditError, ProbeError, KeyError,
            RuntimeError, ValueError) as error:
        value = {
            **base,
            "format": "lisp65-c2-crc-codegen-correction-wplto-first-red-v1",
            "status": "FIRST RED: CRC correction successor gate stopped",
            "authority": authority,
            "diagnostic": {"type": type(error).__name__,
                           "message": str(error)},
            "next_gate": "review; no product link or hardware retry",
        }
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    original["protect"](OUT)
    os.chmod(RECEIPT, 0o444)
    return value


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "CRC correction WPLTO receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") ==
            "passed-crc-codegen-correction-wplto-no-product-link",
            "CRC correction WPLTO receipt is not green")
    require(sha(LINK33_PRODUCT) == LINK33_PRODUCT_SHA,
            "Link-33 rollback product changed after WPLTO probe")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        cases = CRC.selftest()
        INHERITANCE.selftest()
        F011.selftest()
        print("c2-crc-correction-wplto: SELFTEST PASS mutations="
              + str(len(cases) + 5))
        return 0
    value = run_once() if args.action == "run" else check()
    print("c2-crc-correction-wplto: " + value["status"])
    return 3 if str(value["status"]).startswith("FIRST RED") else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProbeError, BOOT.GateError, BOOT.BASE.ProbeError,
            BOOT.ISLAND.GateError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-crc-correction-wplto: FAIL: " + str(error), file=sys.stderr)
        raise SystemExit(2)
