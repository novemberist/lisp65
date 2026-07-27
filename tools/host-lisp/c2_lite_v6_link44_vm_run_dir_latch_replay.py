#!/usr/bin/env python3
"""Class-A pure replay of the one-site latch after gate qualification."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link44_vm_run_dir_latch as D  # noqa: E402


OUT = D.PROBE_OUT
RECEIPT = D.PROBE_REPLAY_RECEIPT
INTERNAL_SHA = (
    "473c22934cb19317284a61cf8e253c816232ffe66b0ec88a754d382edf6271e6")
FIRST_RED_SHA = (
    "56d0b1caece635d364225b4991a4cba9c67493c551ec5c3a862c41b15a55d461")
PRODUCT = OUT / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
PRODUCT_SHA = (
    "d0acc0b7b9490d5de59d4c43ac00d01cec24536327cf8c628c77b574c5a16b6b")
ELF_SHA = (
    "879f74d00f12be6df4148c3a04f03f80a4f01a3c3460627c570fc49312655ee0")
MAP_SHA = (
    "b73d7e3dda1bd72231725ee33c20a4c4271abb170e020923f113176bdb2d4bd6")
STRUCTURE = OUT / "product-substitution-link.json"
STRUCTURE_SHA = (
    "7725aef81cd62349411d45b2fe582b5dbcdae07ddc0e0dd9f9b205d6c8d6f06d")


def walls_and_capacity() -> tuple[dict[str, int], dict[str, Any]]:
    sections = D.LINK44.P.section_table(ELF)
    baseline = D.LINK44.P.section_table(D.BASE_ELF)
    text, bss = sections[".text"], sections[".bss"]
    fixed_names = (
        ".lisp65_c2_fixed_bank0", ".lisp65_c2_fixed_bank0_code",
        ".lisp65_c2_fixed_bank0_hot_bss")
    D.require(all(sections[name] == baseline[name] for name in fixed_names),
              "one-site replay changed fixed-block geometry")
    e000_used = sum(row["bytes"] for row in sections.values()
                    if 0xe000 <= row["address"] < 0x10000 and row["bytes"])
    walls = {
        "bank0_text_headroom_bytes":
            D.LINK44.P.HANDOFF_BASE - text["address"] - text["bytes"],
        "ordinary_bank0_bss_headroom_bytes":
            D.LINK44.P.FIXED_BANK0_BASE - bss["address"] - bss["bytes"],
        "fixed_hot_block_headroom_bytes": 33,
        "resident_island_headroom_bytes": 2048 - sum(
            sections.get(name, {}).get("bytes", 0) for name in
            (".lisp65_resident_island",
             ".lisp65_resident_island_annex")),
        "e000_headroom_bytes": D.LINK44.P.KERNAL_WINDOW_BYTES - e000_used,
    }
    session_bin = OUT / "runtime-overlays-session-final.bin"
    session_json = json.loads(
        (OUT / "runtime-overlays-session-final.json").read_text(
            encoding="utf-8"))
    capacity = {
        "status": "passed",
        "session_family_bytes": session_bin.stat().st_size,
        "session_family_headroom_bytes": 65536 - session_bin.stat().st_size,
        "session_catalog_records_after": len(session_json["slices"]),
    }
    return walls, capacity


def main() -> int:
    D.require(not RECEIPT.exists(), "one-site pure replay is one-shot")
    for path, digest in {
            D.PROBE_INTERNAL: INTERNAL_SHA,
            D.PROBE_RECEIPT: FIRST_RED_SHA,
            PRODUCT: PRODUCT_SHA, ELF: ELF_SHA, MAP: MAP_SHA,
            STRUCTURE: STRUCTURE_SHA}.items():
        D.require(path.is_file() and D.sha(path) == digest,
                  f"one-site replay artifact drift: {path}")
    first = json.loads(D.PROBE_INTERNAL.read_text(encoding="utf-8"))
    D.require(first["status"] == "FIRST RED: C2-lite real-ABI Link 44 stopped"
              and first["diagnostic"]["message"] ==
                "one-site cut changed an uninstrumented VM/renderer function",
              "one-site replay First Red is not the qualified gate-model stop")
    base = json.loads(STRUCTURE.read_text(encoding="utf-8"))
    required = (
        "identity_gate", "capacity_gate", "one_truth_gate",
        "kernal_freedom_gate", "fixed_host_facade_gate",
        "pre_ownership_gate", "handoff_z_abi_gate",
    )
    D.require(base["status"] == "passed"
              and base["product_closure_link_count"] == 1
              and all(base[name] == "passed" for name in required),
              "linked product-substitution base gates are not green")

    linked = D.linked_gate(ELF)
    walls, family = walls_and_capacity()
    capacity = D.capacity_gate({"fresh_replacement_gates": {
        "walls": walls, "capacity": family}})
    shaped = {"artifacts": {"measurement_elf": D.bind(ELF)}}
    target = D.LINK44.B.elf_gate(shaped)
    fixture = D.LINK44.B.target_fixture(D.LINK44.REPLAY.fixture_product())
    D.require(target["phase"]["bytes"] <= D.LINK44.B.CAP
              and fixture["workbench_scratch_passing_records"] == 0
              and not fixture["ready_if_workbench_scratch_remains"],
              "Bank-2 linked-dataflow replay red")
    value = {
        "format": "lisp65-c2-lite-v6-vm-run-dir-latch-pure-replay-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-vm-run-dir-latch-WPLTO-pure-replay-no-hardware",
        "promotable": False,
        "class_a_gate_correction": {
            "old_model": "unrelated LTO function sizes must remain byteidentical",
            "corrected_model": "only vm_run_dir may reference either latch cell; "
                               "other function sizes are provenance",
            "compiler_runs": 0,
            "linker_runs": 0,
            "product_bytes_changed": 0,
        },
        "source_gate": D.source_gate(
            D.VM.read_text(encoding="utf-8"),
            D.VM_H.read_text(encoding="utf-8"),
            D.EVAL.read_text(encoding="utf-8"), mutations=True),
        "linked_latch": linked,
        "capacity": capacity,
        "bank2_target_dataflow": target,
        "bank2_workbench_scratch_negative": fixture,
        "base_gate_status": {name: base[name] for name in required},
        "identity": {"product": D.bind(PRODUCT), "elf": D.bind(ELF),
                     "map": D.bind(MAP), "diagnostic_only": True},
        "first_red": D.bind(D.PROBE_INTERNAL),
        "link44_rollback": {**D.bind(D.BASE_PRODUCT), "status": "untouched"},
        "execution_accounting": {
            "replayed_existing_ELFs": 1,
            "compiler_runs": 0, "linker_runs": 0, "hardware_runs": 0,
            "class_b_cycles_consumed": 0,
        },
        "next_gate": "one nonpromotable Class-B diagnostic link",
    }
    D.write(RECEIPT, value)
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-vm-run-dir-latch-replay: PASS "
          f"text={walls['bank0_text_headroom_bytes']}B "
          f"bss={walls['ordinary_bank0_bss_headroom_bytes']}B "
          "compiler=0 linker=0 hardware=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (D.GateError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-vm-run-dir-latch-replay: FAIL: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
