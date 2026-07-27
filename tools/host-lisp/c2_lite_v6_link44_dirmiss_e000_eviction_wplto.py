#!/usr/bin/env python3
"""One product-shaped WPLTO probe for the approved Link-44 E000 eviction.

The permanent VM_DIRMISS status-plus-detail seam is unchanged.  This probe
moves exactly one existing hot, post-ownership, call-free helper
(`vm_byte_args`) into the existing C2-resident KERNAL-window section.  It
requires at least 32 bytes of real Bank-0 text headroom and preserves the
restored 115-byte E000 floor.  It never creates a promotable product or runs
hardware.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link44_dirmiss_detail_wplto as DETAIL  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CONTRACT = ROOT / "config/c2-vm-dirmiss-detail-e000-evacuation-contract.json"
FIRST_RED = EVIDENCE / (
    "c2.2-link44-dirmiss-detail-wplto-capacity-first-red-diagnosis.json")
FIRST_RED_SHA = (
    "dc32d556624bdb0b12dc051352ac1f57296138f17272b1477f469d4792089f2b")
PREMOVE_LTO = ROOT / (
    "build/c2.2/substitution/link44-dirmiss-detail-wplto/"
    "resident-island-seed.prg.lto.o")
PREMOVE_LTO_SHA = (
    "20b5487a3fa3d79ff5af8aa47f7d62dd5e24159606785bd53e6a88049021ad3f")
OUT = ROOT / (
    "build/c2.2/substitution/link44-dirmiss-detail-e000-eviction-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-link44-dirmiss-detail-e000-eviction-wplto-internal-structural.json")
ENGINE_RECEIPT = EVIDENCE / (
    "c2.2-link44-dirmiss-detail-e000-eviction-wplto-engine-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link44-dirmiss-detail-e000-eviction-wplto-receipt.json")
TEXT_HEADROOM_MIN = 32
E000_FLOOR = 115


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"evacuation evidence absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def run(command: list[str]) -> str:
    return DETAIL.LINK44.P.run(command, capture=True)


def contract_gate(source: str, *, mutations: bool = False) -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract["schema"] ==
            "lisp65.c2.vm-dirmiss-detail-e000-evacuation.v1",
            "E000 evacuation contract schema drift")
    seam = ("#define VM_BYTE_ARGS_FN __attribute__((noinline, \\\n+    section(\".lisp65_c2_kernal_window.c2_resident\")))")
    seam = ("#define VM_BYTE_ARGS_FN __attribute__((noinline, "
            + chr(92) + "\n    section(\".lisp65_c2_kernal_window."
            "c2_resident\")))")
    required = (
        "defined(LISP65_C2_LITE_CHIP_RAM)",
        "#define VM_BYTE_ARGS_FN __attribute__((noinline, \\\n+    section(\".lisp65_c2_kernal_window.c2_resident\")))",
        "static VM_BYTE_ARGS_FN uint8_t",
        "vm_byte_args(obj *a, uint8_t n, uint8_t expected)",
        "#undef VM_BYTE_ARGS_FN",
    )
    require(all(source.count(token) == 1 for token in required
                if not token.startswith("#define VM_BYTE_ARGS_FN"))
            and source.count(
                "#define VM_BYTE_ARGS_FN __attribute__((noinline, \\") == 1,
            "purpose-bound vm_byte_args E000 source seam drift")
    require(source.count(seam) == 1,
            "vm_byte_args destination seam is not unique")
    require(source.count(
        'section(".lisp65_c2_kernal_window.c2_resident")))') >= 2,
        "existing C2-resident destination section drift")
    require(source.count("vm_byte_args(") == 2,
            "vm_byte_args definition/callsite cardinality drift")
    body = source.split("vm_byte_args(obj *a, uint8_t n, uint8_t expected)",
                        1)[1].split("#undef VM_BYTE_ARGS_FN", 1)[0]
    require("vm_status = VM_ARITY" in body
            and "vm_status = VM_TYPEERROR" in body
            and not any(token in body for token in
                        ("lisp_poll(", "vm_run(", "c2_facade_", "cons(")),
            "vm_byte_args is no longer the approved call-free status leaf")

    rejected: dict[str, str] = {}
    if mutations:
        candidates = {
            "bank0-residency-regression": source.replace(
                seam, seam.replace(
                    ".lisp65_c2_kernal_window.c2_resident", ".text"), 1),
            "chip-ram-lifetime-guard-removed": source.replace(
                "defined(LISP65_C2_LITE_CHIP_RAM)", "1", 1),
            "second-callsite": source.replace(
                "if (!vm_byte_args(a, n,", "if (!vm_byte_args(a, n,", 1)
                + "\n/* vm_byte_args(a, n, 0); forbidden second callsite */\n",
            "outbound-poll-edge": source.replace(
                "expected) {\n    uint8_t i;",
                "expected) {\n    uint8_t i; lisp_poll();", 1),
            "outbound-facade-edge": source.replace(
                "expected) {\n    uint8_t i;",
                "expected) {\n    uint8_t i; c2_facade_gc_mark(NIL);", 1),
            "status-contract-removed": source.replace(
                "vm_status = VM_TYPEERROR; return 0;\n        }\n    }\n"
                "    return 1;\n}\n#undef VM_BYTE_ARGS_FN",
                "/* status omitted */ return 0;\n        }\n    }\n"
                "    return 1;\n}\n#undef VM_BYTE_ARGS_FN", 1),
        }
        for name, mutation in candidates.items():
            try:
                contract_gate(mutation, mutations=False)
            except (GateError, KeyError, json.JSONDecodeError):
                rejected[name] = "rejected"
            else:
                raise GateError(f"E000 evacuation mutation accepted: {name}")
    return {
        "status": "passed-purpose-bound-hot-leaf-source-contract",
        "symbol": "vm_byte_args",
        "destination_section": ".lisp65_c2_kernal_window.c2_resident",
        "temperature": "hot-CALLPRIM-byte-domain-validation",
        "lifetime": "post-ownership-only",
        "new_vector": False,
        "new_section": False,
        "new_state_bytes": 0,
        "mutations_rejected": rejected,
    }


def premove_candidate_gate() -> dict[str, Any]:
    require(PREMOVE_LTO.is_file() and sha(PREMOVE_LTO) == PREMOVE_LTO_SHA,
            "pre-move WPLTO truth drift")
    truth = ElfTruth.read(
        PREMOVE_LTO, llvm_readobj=DETAIL.LINK44.P.TOOLCHAIN / "llvm-readobj")
    candidates = {
        "vm_byte_args": (97, "hot", "selected"),
        "vm_upval_nth": (93, "hot", "cell_type/cell_b calls"),
        "sidx": (126, "hot", "ext_a call and heap data"),
        "sym_function": (108, "hot", "sidx and DMA-facade calls"),
        "sym_value": (108, "hot", "sidx and DMA-facade calls"),
        "lisp_input_event": (128, "hot", "abort/event-poll calls"),
        "crc32_update": (104, "boot-cold", "wrong temperature"),
    }
    rows: list[dict[str, Any]] = []
    for name, (expected, temperature, disposition) in candidates.items():
        symbol = truth.symbol(name)
        require(symbol.bytes == expected,
                f"candidate size drift before move: {name}")
        outgoing = [row for row in truth.relocations
                    if row.source_section == symbol.section]
        external_code = sorted({row.target for row in outgoing
                                if (row.target.startswith(".text.")
                                    or truth.symbols[row.target_symbol_index]
                                    .symbol_type == "Function")
                                and row.target not in
                                (symbol.section, symbol.name)})
        if name == "vm_byte_args":
            require(not external_code,
                    f"selected leaf has outbound code edges: {external_code}")
        rows.append({
            "symbol": name, "bytes": symbol.bytes,
            "temperature": temperature,
            "external_code_targets": external_code,
            "disposition": disposition,
        })
    return {
        "status": "passed-temperature-and-edge-profile-selection",
        "authority": bind(PREMOVE_LTO),
        "minimum_relief_bytes": 86,
        "selected": "vm_byte_args",
        "candidates": rows,
    }


def linked_eviction_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(
        elf, llvm_readobj=DETAIL.LINK44.P.TOOLCHAIN / "llvm-readobj")
    moved = truth.symbol("vm_byte_args")
    require(moved.section == ".lisp65_c2_kernal_window.c2_resident"
            and moved.bytes >= 86,
            f"vm_byte_args did not become the sized window tenant: {moved}")
    disassembly = run([
        str(DETAIL.LINK44.P.TOOLCHAIN / "llvm-objdump"), "-dr",
        "--disassemble-symbols=vm_byte_args", str(elf)])
    transfers = [int(value, 16) for value in re.findall(
        r"\b(?:jsr|jmp)\s+\$([0-9a-fA-F]+)", disassembly)]
    outbound = [value for value in transfers
                if not moved.value <= value < moved.value + moved.bytes]
    require(not outbound and "<vm_status>" in disassembly,
            f"moved leaf gained an outbound edge or lost status binding: "
            f"{[hex(value) for value in outbound]}")
    return {
        "status": "passed-sized-post-ownership-call-free-window-tenant",
        "symbol": moved.name,
        "section": moved.section,
        "address": f"0x{moved.value:04x}",
        "bytes": moved.bytes,
        "control_transfers": len(transfers),
        "outbound_control_transfers": 0,
        "fixed_data_edge": "vm_status",
        "new_vector": False,
    }


def probe() -> dict[str, Any]:
    require(not any(path.exists() for path in
                    (OUT, INTERNAL, ENGINE_RECEIPT, RECEIPT)),
            "E000 evacuation WPLTO is one-shot and already consumed")
    require(FIRST_RED.is_file() and sha(FIRST_RED) == FIRST_RED_SHA,
            "status-plus-detail capacity First Red drift")
    source_result = contract_gate(
        (ROOT / "src/vm.c").read_text(encoding="utf-8"), mutations=True)
    candidates = premove_candidate_gate()

    old_paths = (DETAIL.OUT, DETAIL.INTERNAL, DETAIL.RECEIPT)
    old_linked = DETAIL.linked_gate
    old_capacity = DETAIL.capacity_gate

    def combined_linked(elf: Path) -> dict[str, Any]:
        value = old_linked(elf)
        value["e000_eviction"] = linked_eviction_gate(elf)
        return value

    def qualified_capacity(structure: dict[str, Any]) -> dict[str, Any]:
        value = old_capacity(structure)
        walls = value["probe_walls"]
        require(walls["bank0_text_headroom_bytes"] >= TEXT_HEADROOM_MIN,
                f"standing Bank-0 text reserve not restored: {walls}")
        require(walls["e000_headroom_bytes"] >= E000_FLOOR,
                f"restored E000 floor crossed: {walls}")
        first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
        failed_bytes = first["first_red"]["probe"]["text_bytes"]
        baseline_bytes = first["first_red"]["baseline"]["text_bytes"]
        after_bytes = baseline_bytes + (
            first["first_red"]["baseline"]["text_headroom_bytes"]
            - walls["bank0_text_headroom_bytes"])
        value.update({
            "minimum_required_relief_bytes": 86,
            "measured_relief_from_first_red_bytes": failed_bytes - after_bytes,
            "standing_text_reserve_required_bytes": TEXT_HEADROOM_MIN,
            "e000_floor_required_bytes": E000_FLOOR,
        })
        require(value["measured_relief_from_first_red_bytes"] >= 86,
                f"evacuation relief below contract: {value}")
        return value

    try:
        DETAIL.OUT = OUT
        DETAIL.INTERNAL = INTERNAL
        DETAIL.RECEIPT = ENGINE_RECEIPT
        DETAIL.linked_gate = combined_linked
        DETAIL.capacity_gate = qualified_capacity
        result = DETAIL.run_probe()
    finally:
        DETAIL.OUT, DETAIL.INTERNAL, DETAIL.RECEIPT = old_paths
        DETAIL.linked_gate = old_linked
        DETAIL.capacity_gate = old_capacity

    require(not result["status"].startswith("FIRST RED"),
            "product-shaped E000 evacuation WPLTO stopped First Red")
    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    structure_path = ROOT / internal["structural_report"]["path"]
    structure = json.loads(structure_path.read_text(encoding="utf-8"))
    gates = structure["fresh_replacement_gates"]
    eviction = gates["vm_dirmiss_detail"]["e000_eviction"]
    capacity = qualified_capacity(structure)
    required_fresh = (
        "handoff_z_abi", "pre_ownership", "profile_data_references",
        "fixed_facade", "kernal_freedom", "section_inventory",
    )
    for name in required_fresh:
        require(name in gates, f"fresh replacement gate absent: {name}")
    value = {
        "format": "lisp65-c2-lite-v6-link44-dirmiss-e000-eviction-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-one-hot-leaf-E000-evacuation-product-shaped-WPLTO",
        "promotable": False,
        "claim_limit": "Placement, WPLTO capacity, mutations and fresh structural gates only; hardware not run.",
        "authority": {
            "capacity_first_red": bind(FIRST_RED),
            "evacuation_contract": bind(CONTRACT),
            "driver": bind(Path(__file__)),
        },
        "source_contract": source_result,
        "candidate_selection": candidates,
        "linked_eviction": eviction,
        "capacity": capacity,
        "fresh_gate_names": sorted(gates),
        "product_shaped_identity": result["product_shaped_identity"],
        "engine_receipt": bind(ENGINE_RECEIPT),
        "internal_structural_receipt": bind(INTERNAL),
        "structural_report": bind(structure_path),
        "link44_rollback": {**bind(DETAIL.BASE_PRODUCT),
                            "status": "untouched"},
        "execution_accounting": {
            "whole_program_lto_closure_links": 1,
            "promotable_product_links": 0,
            "hardware_runs": 0,
            "retries": 0,
        },
        "counters": {
            "class_b": "3/3 exhausted",
            "line1_product_first_reds": "2/3",
            "completed_latency_measurements": "0/2",
        },
        "next_gate": "one authorized promotable successor link",
    }
    write(RECEIPT, value)
    for path in (INTERNAL, ENGINE_RECEIPT, RECEIPT):
        os.chmod(path, 0o444)
    return value


def selftest() -> dict[str, Any]:
    source = contract_gate((ROOT / "src/vm.c").read_text(encoding="utf-8"),
                           mutations=True)
    require(len(source["mutations_rejected"]) == 6,
            "E000 evacuation source mutation count drift")
    candidates = premove_candidate_gate()
    return {"status": "passed-source-and-candidate-selection-selftest",
            "source": source, "candidates": candidates}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("selftest", "probe"))
    args = parser.parse_args()
    try:
        value = selftest() if args.stage == "selftest" else probe()
        print("c2-lite-v6-link44-dirmiss-e000-eviction: " + value["status"])
        return 0
    except (GateError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link44-dirmiss-e000-eviction: FAIL: " + str(error),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
