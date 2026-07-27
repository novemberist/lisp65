#!/usr/bin/env python3
"""Product-shaped WPLTO probe for the pre-authorized Link-39 E000 eviction.

The sole moved object is the post-ownership, call-free vm_arity_accepts leaf.
It joins the existing C2-resident E000 output section.  The probe requires a
real Bank-0 text margin of at least 32 bytes, preserves the 115-byte E000
floor, and reruns ownership, facade, KERNAL-freedom, staging, real-ABI and
six-vector CRC gates.  It never makes a product link or runs hardware.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_lite_v6_bank3_staging_wplto_probe as STAGE  # noqa: E402
import c2_lite_v6_boot_crc_abi_successor_link as LINK_GATES  # noqa: E402
import c2_lite_v6_first_product_link as LINK  # noqa: E402
import c2_lite_v6_rtov_crc_real_abi_wplto as ABI_PROBE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


P = STAGE.P
FEATURE = "LISP65_C2_LITE_VM_ARITY_E000"
OUT = ROOT / "build/c2-lite/v6-link39-real-abi-e000-evacuation-wplto"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.2-c2-lite-v6-link39-real-abi-e000-evacuation-wplto-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.2-product-link39-c2-lite-v6-real-abi-replay-structural-receipt.json")
FIRST_RED_SHA = (
    "25a780ef732ed9105999a2775cadf28413d5e3dc55d63691492578e827741cb1")
QUALIFICATION = EVIDENCE / (
    "c2.2-c2-lite-v6-link38-rtov-crc-real-abi-wplto-"
    "pure-replay-receipt.json")
QUALIFICATION_SHA = (
    "0bef9debcd85ea704cfa37dd4c58b834f025a134b06fd30e67ccb951ba524757")
CURRENT_DIRECT = EVIDENCE / (
    "c2.2-c2-lite-v6-real-abi-direct-entry-contract-receipt.json")
CURRENT_DIRECT_SHA = (
    "f50fe4721727b9fa5ab3d10457b3f067154d3c926f4159cbc271522881b8a0f9")
REAL_ABI_TREE = ROOT / "build/c2-lite/v6-link38-rtov-crc-real-abi-wplto"
REAL_ABI_ELF = REAL_ABI_TREE / "full-product-wplto/c2-lite-v6-full-seed.prg.elf"
REAL_ABI_ELF_SHA = (
    "bdad614e38b2ff5d29de21eb3b5b5965f61cfc172263095b10dc07f11a5dcbdc")
TEXT_MARGIN_TARGET = 32
E000_FLOOR = 115
CAP = 1792
BANK_BYTES = 65536


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"evacuation artifact absent: {path}")
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


def authority() -> dict[str, Any]:
    expected = {
        FIRST_RED: FIRST_RED_SHA,
        QUALIFICATION: QUALIFICATION_SHA,
        CURRENT_DIRECT: CURRENT_DIRECT_SHA,
        REAL_ABI_ELF: REAL_ABI_ELF_SHA,
    }
    for path, digest in expected.items():
        require(path.is_file() and sha(path) == digest,
                f"evacuation authority drift: {path}")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    stderr_row = first.get("evidence", {}).get(
        "resident-island-seed.prg.link.stderr.txt", {})
    stderr_path = ROOT / (
        "build/c2.2/substitution/"
        "product-link-39-c2-lite-v6-real-abi-replay/"
        "resident-island-seed.prg.link.stderr.txt")
    stderr = stderr_path.read_text(encoding="utf-8")
    require(first["status"] == "FIRST RED: C2-lite real-ABI Link 39 stopped"
            and first["execution_accounting"]["product_closure_links"] == 0
            and first["diagnostic"]["message"] ==
                "link command failed before orphan-wrapper acceptance: exit=1"
            and stderr_row.get("sha256") == sha(stderr_path)
            and "section .text" in stderr
            and ".text range is [0x2023, 0xB4A9]" in stderr
            and ".lisp65_c2_kernal_handoff range is [0xB4A3, 0xB5C3]"
                in stderr,
            "Link-39 resident-capacity First Red is not authoritative")
    return {
        "link39_capacity_first_red": bind(FIRST_RED),
        "link39_capacity_linker_diagnostic": bind(stderr_path),
        "class_c_real_abi_qualification": bind(QUALIFICATION),
        "current_v6_direct_entry": bind(CURRENT_DIRECT),
        "qualified_real_abi_elf": bind(REAL_ABI_ELF),
        "source": bind(ROOT / "src/vm.c"),
        "driver": bind(Path(__file__)),
    }


def first_red(error: BaseException) -> dict[str, Any]:
    value = {
        "format": "lisp65-c2-lite-v6-real-abi-e000-evacuation-first-red-v1",
        "recorded_on": "2026-07-22",
        "status": "FIRST RED: Link-39 E000 evacuation WPLTO stopped",
        "failure": {"type": type(error).__name__, "message": str(error)},
        "scope": {"whole_program_lto_probes": int(OUT.exists()),
                  "product_links": 0, "hardware_runs": 0,
                  "promotable": False},
        "evidence": [bind(path) for path in sorted(OUT.rglob("*"))
                     if path.is_file()],
        "rollback_line": {**bind(ABI_PROBE.BASE), "status": "untouched"},
        "next_gate": "Return to Class-C review; no product link or hardware",
    }
    write_json(RECEIPT, value)
    protect()
    return value


def relocation_gate(target: Path, elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    moved = truth.symbol("vm_arity_accepts")
    require(moved.section == ".lisp65_c2_kernal_window.c2_resident"
            and moved.bytes > 0,
            f"vm_arity_accepts did not enter the owned slab: {moved}")
    disassembly = P.run([
        str(P.TOOLCHAIN / "llvm-objdump"), "-dr",
        "--disassemble-symbols=vm_arity_accepts", str(elf)], capture=True)
    require(not re.search(r"\b(?:jsr|jmp)\s+\$", disassembly.lower()),
            "evacuated leaf gained an outbound control-flow edge")
    source = (ROOT / "src/vm.c").read_text(encoding="utf-8")
    require(source.count("LISP65_C2_LITE_VM_ARITY_E000") == 1
            and source.count(
                'section(".lisp65_c2_kernal_window.c2_resident")') >= 1,
            "purpose-bound evacuation source seam drift")
    return {
        "status": "passed-purpose-bound-post-ownership-call-free-leaf",
        "symbol": "vm_arity_accepts",
        "section": moved.section,
        "address": f"0x{moved.value:04x}",
        "bytes": moved.bytes,
        "temperature": "hot-success-path-VM-arity-check",
        "lifetime": "post-ownership-only",
        "outbound_calls_or_jumps": 0,
        "new_section": False,
        "new_vector": False,
        "new_state_bytes": 0,
    }


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "E000 evacuation WPLTO is one-shot")
    auth = authority()
    OUT.mkdir(parents=True)
    features = (*STAGE.feature_set(), FEATURE)
    old_out = STAGE.OUT
    STAGE.OUT = OUT
    try:
        wplto, target, elf = STAGE.run_wplto(features)
        stage = STAGE.product_gate(wplto, target, elf)
    finally:
        STAGE.OUT = old_out

    relocation = relocation_gate(target, elf)
    abi = ABI.audit_elf(
        elf, out=OUT / "c2-asm-leaf-real-abi-callers.json",
        require_bank3_chain=True)
    old_abi_out = ABI_PROBE.OUT
    try:
        ABI_PROBE.OUT = OUT
        parity = ABI_PROBE.workbench_crc_gate(target, elf)
    finally:
        ABI_PROBE.OUT = old_abi_out

    sections = P.section_table(elf)
    walls = {
        "bank0_text_headroom_bytes":
            P.HANDOFF_BASE - sections[".text"]["address"]
            - sections[".text"]["bytes"],
        "ordinary_bank0_bss_headroom_bytes":
            P.FIXED_BANK0_BASE - sections[".bss"]["address"]
            - sections[".bss"]["bytes"],
        "fixed_hot_block_headroom_bytes": P.fixed_bank0_headroom_bytes(),
        "resident_island_headroom_bytes": 2048 - sum(
            sections.get(name, {}).get("bytes", 0) for name in
            (".lisp65_resident_island", ".lisp65_resident_island_annex")),
        "e000_headroom_bytes": P.KERNAL_WINDOW_BYTES - sum(
            sections[name]["bytes"] for name in P.KERNAL_SECTIONS),
    }
    require(walls["bank0_text_headroom_bytes"] >= TEXT_MARGIN_TARGET
            and walls["e000_headroom_bytes"] >= E000_FLOOR
            and all(value >= 0 for value in walls.values()),
            f"evacuation did not restore the contracted margins: {walls}")

    before = ABI_PROBE.section_sizes(REAL_ABI_ELF)
    after = ABI_PROBE.section_sizes(elf)
    require(set(before) == set(after),
            "evacuation changed the final section-name inventory")
    deltas = {name: after[name] - before[name] for name in sorted(before)}
    allocated_deltas = {
        name: value for name, value in deltas.items()
        if value and name in P.KERNAL_SECTIONS + [".text"]}
    require(allocated_deltas.get(".text", 0) < 0
            and allocated_deltas.get(
                ".lisp65_c2_kernal_window.c2_resident", 0) > 0,
            f"evacuation attribution red: {allocated_deltas}")

    facade = P.fixed_facade_gate(OUT, target, "link39-e000-evacuation-wplto")
    handoff = P.handoff_z_abi_gate(
        OUT, target, "link39-e000-evacuation-wplto")
    pre = P.pre_ownership_gate(
        OUT, target, "link39-e000-evacuation-wplto")
    profile = P.profile_data_reference_gate(
        OUT, target, "link39-e000-evacuation-wplto", pre)
    inventory = P.final_section_inventory_gate(OUT, target)
    kernal = P.kernal_freedom_gate(OUT, target)
    no_attic = LINK.no_runtime_attic_gate(
        elf, target.parent / "generated-product-sources")
    overlay = LINK.BASE.LINK33_BASE.final_overlay_closure(elf)
    preinstall = LINK.BASE.ISLAND.static_elf_gate(elf)
    require(kernal["status"] == facade["status"] == handoff["status"]
            == pre["status"] == profile["status"] == inventory["status"]
            == "passed"
            and no_attic["status"].startswith("passed")
            and overlay["status"] == "passed-final-elf-overlay-closure"
            and preinstall["status"] ==
                "passed-static-preinstallation-Island-gate",
            "one or more fresh evacuation structure gates are red")

    session = target.parent / "runtime-overlays-session-c2-lite.bin"
    require(session.stat().st_size <= BANK_BYTES,
            "evacuation changed the session aggregate beyond one bank")
    report = {
        "format": "lisp65-c2-lite-v6-real-abi-e000-evacuation-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-purpose-bound-e000-evacuation-wplto",
        "scope": {"whole_program_lto_probes": 1, "product_links": 0,
                  "hardware_runs": 0, "promotable": False},
        "authority": auth,
        "feature": FEATURE,
        "relocation": relocation,
        "capacity": {
            "section_deltas_against_qualified_real_abi_wplto": deltas,
            "allocated_attribution": allocated_deltas,
            "walls": walls,
            "text_margin_target_bytes": TEXT_MARGIN_TARGET,
            "e000_floor_bytes": E000_FLOOR,
            "session_aggregate": {**bind(session),
                                  "headroom_bytes":
                                      BANK_BYTES - session.stat().st_size},
        },
        "fresh_gates": {
            "bank3_stage": stage,
            "real_abi": abi,
            "six_vector_crc": parity,
            "fixed_facade": facade,
            "handoff": handoff,
            "pre_ownership": pre,
            "profile_data": profile,
            "section_inventory": inventory,
            "kernal_freedom": kernal,
            "no_runtime_attic": no_attic,
            "overlay_closure": overlay,
            "preinstallation_island": preinstall,
        },
        "artifacts": {
            "measurement_product": bind(target),
            "measurement_elf": bind(elf),
            "measurement_map": bind(Path(str(target) + ".map")),
            "caller_gate": bind(OUT / "c2-asm-leaf-real-abi-callers.json"),
            "crc_parity": bind(
                OUT / "c2-crc-asm-leaf-real-abi-parity.json"),
        },
        "rollback_line": {**bind(ABI_PROBE.BASE), "status": "untouched"},
        "claim_limit": (
            "One product-shaped WPLTO capacity and placement probe. No "
            "product link, hardware, boot, latency, promotion or acceptance."),
        "next_gate": "Owner-preauthorized successor product-link replay",
    }
    write_json(OUT / "e000-evacuation-wplto-report.json", report)
    report["probe_report"] = bind(
        OUT / "e000-evacuation-wplto-report.json")
    write_json(RECEIPT, report)
    protect()
    return report


def main() -> int:
    try:
        value = build()
    except Exception as error:
        if OUT.exists() and not RECEIPT.exists():
            first_red(error)
        print("c2-lite-v6-real-abi-e000-evacuation-wplto: FIRST RED "
              + str(error))
        return 2
    walls = value["capacity"]["walls"]
    print("c2-lite-v6-real-abi-e000-evacuation-wplto: PASS "
          f"text-headroom={walls['bank0_text_headroom_bytes']}B "
          f"e000-headroom={walls['e000_headroom_bytes']}B "
          f"moved={value['relocation']['bytes']}B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
