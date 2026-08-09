#!/usr/bin/env python3
"""Bind the write-time CPU view of the v1.6 mem_init witness hooks.

The repeat contact read the deliberately physical Bank-0 witness underlay, but
stopped with the logical B block mapped.  This desk gate answers the separate
question that matters for the two target stores: which MAP state owns $B582 at
the time the boot-overlay hooks can execute?  It does not authorize or perform
another device action.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402
import c2_v16_mem_init_before_after as W  # noqa: E402
import c2_v16_mem_init_before_after_contact as C  # noqa: E402


RECORDED_ON = "2026-08-06"
RESULT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mem-init-repeat-mapping-result.json")
DEVICE = C.DEVICE
PREPARATION = W.RECEIPT
OWNERSHIP = W.OWNERSHIP_RECEIPT
CORE = ROOT / "build/upstream-verification/mega65-core/src/vhdl/gs4510.vhdl"
MAP_SOURCE = ROOT / "build/c2.3/v1.6-defstruct-phase-c/source/src/c2_kernal_map.s"
WINDOW_SOURCE = ROOT / (
    "build/c2.3/v1.6-defstruct-phase-c/source/src/c2_kernal_window.s")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mem-init-witness-write-view-desk-attribution-receipt.json")
DRIVER = Path(__file__).resolve()
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


class ViewError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ViewError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def section_slice(truth: ElfTruth, section_name: str,
                  address: int, count: int) -> bytes:
    section = truth.section(section_name)
    offset = address - section.address
    require(0 <= offset and offset + count <= section.bytes,
            f"section range absent: {section_name} ${address:04x}+{count}")
    return truth.section_bytes(section_name)[offset:offset + count]


def disassembly() -> str:
    completed = subprocess.run(
        [str(OBJDUMP), "-d", str(W.DIAG_ELF)], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    return completed.stdout


def exact() -> dict[str, Any]:
    result, device, prep, ownership = (
        load(RESULT), load(DEVICE), load(PREPARATION), load(OWNERSHIP))
    require(result["facts"]["disposition"] == {
        "R_A_I_G": None,
        "classification": "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM",
        "new_contact_authorized": False,
        "next_required": (
            "desk-bind the write-time mapping/visibility of the $B582 witness "
            "hooks before any further device action"),
        "product_fault": None,
    }, "mapping-result commission drift")
    require(device["snapshots"]["raw_hex"] == "d1ccccccccd2cccccccc"
            and device["raw"]["mem_init_witness"]["reads"][0]["view"] ==
                "physical-bank0-RAM-underlay",
            "physical witness observation drift")
    require(prep["facts"]["placement"]["witness"] == ["0xb582", "0xb58c"]
            and prep["facts"]["routes"]["before"] == {
                "entry": "0xc048", "hook": "0xc85a", "tag": "0xa1",
                "tail": "0xc3fd"}
            and prep["facts"]["routes"]["after"] == {
                "entry": "0xc04e", "hook": "0xc4c5", "tag": "0xa6",
                "tail": "0x2dff"},
            "hook authority drift")
    require(ownership["facts"]["durable_witness"]["containing_gap"] == {
        "start": "0xb582", "end_exclusive": "0xb5c4", "bytes": 66},
        "owner-free witness interval drift")

    truth = ElfTruth.read(W.DIAG_ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    symbols = {name: truth.symbol(name) for name in (
        "main", "c2_kernal_take_ownership", "c2_kernal_map_window",
        "vm_install_staged_boot_overlay", "vm_boot_overlay_chain_commit",
        "vm_workbench_boot_overlay_entry")}
    require({name: (row.value, row.section) for name, row in symbols.items()} == {
        "main": (0xA4AF, ".text"),
        "c2_kernal_take_ownership": (0xB4A3, ".lisp65_c2_kernal_handoff"),
        "c2_kernal_map_window": (0xB5FF, ".lisp65_c2_kernal_map_switch"),
        "vm_install_staged_boot_overlay": (0xA714, ".text"),
        "vm_boot_overlay_chain_commit": (0x2277, ".text"),
        "vm_workbench_boot_overlay_entry":
            (0xC85A, ".lisp65_workbench_overlay"),
    }, "linked route symbol drift")

    # Success from the ownership call falls directly into the overlay installer.
    main_edge = section_slice(truth, ".text", 0xA4E0, 9)
    require(main_edge == bytes.fromhex("20a3b4aaf0272014a7"),
            "ownership-before-overlay call edge drift")
    map_body = truth.section_bytes(".lisp65_c2_kernal_map_switch")
    require(map_body == bytes.fromhex("6baaa8a3805ceaa30060"),
            "MAP tuple body drift")
    ownership_map_call = section_slice(
        truth, ".lisp65_c2_kernal_handoff", 0xB4ED, 3)
    require(ownership_map_call == bytes.fromhex("20ffb5"),
            "ownership MAP call drift")
    overlay_entry = truth.section_bytes(".lisp65_workbench_overlay")[
        0xC85A - truth.section(".lisp65_workbench_overlay").address:
        0xC85D - truth.section(".lisp65_workbench_overlay").address]
    require(overlay_entry == bytes.fromhex("4c48c0"),
            "before-hook route drift")
    chain = section_slice(truth, ".text", symbols[
        "vm_boot_overlay_chain_commit"].value,
        symbols["vm_boot_overlay_chain_commit"].bytes)
    require(chain.count(bytes.fromhex("205ac8")) == 1,
            "boot-chain overlay-entry call drift")
    wrapper = section_slice(truth, ".lisp65_v16_defstruct_diagnostic_state",
                            0xC048, 51)
    require(wrapper == W.wrapper()
            and bytes.fromhex("9d82b5") in wrapper
            and bytes.fromhex("9d83b5") in wrapper,
            "witness wrapper/store drift")

    listing = disassembly()
    map_sites = []
    for line in listing.splitlines():
        match = re.match(r"\s*([0-9a-f]+):.*\bmap\s*$", line)
        if match:
            map_sites.append(int(match.group(1), 16))
    require(map_sites == [0xB604], f"executable MAP-site inventory drift: {map_sites}")
    irq = truth.section_bytes(".lisp65_c2_kernal_window.irq_handler")
    nmi = truth.section_bytes(".lisp65_c2_kernal_window.nmi_and_freezer_return")
    require(b"\x5c" not in irq and b"\x5c" not in nmi,
            "asynchronous handler can change MAP")

    core = CORE.read_text(encoding="utf-8")
    for token in ("reg_map_high <= std_logic_vector(reg_z(7 downto 4))",
                  "reg_map_low <= std_logic_vector(reg_x(7 downto 4))",
                  "if reg_map_high(blocknum)='1'",
                  "temp_address(27 downto 20) := reg_mb_high"):
        require(token in core, f"primary MAP semantic absent: {token}")
    map_source = MAP_SOURCE.read_text(encoding="utf-8")
    require("MAP operand tuple (0,0,0,$80)" in map_source
            and "Own only block 7 ($e000-$ffff)" in map_source,
            "MAP source contract drift")
    window_instructions = [line.split(";", 1)[0].strip().lower()
                           for line in WINDOW_SOURCE.read_text(
                               encoding="utf-8").splitlines()]
    require("map" not in window_instructions,
            "IRQ/window source unexpectedly changes MAP")

    maph, mapl = 0x8000, 0x0000
    b_block = (W.WITNESS >> 13) & 3
    b_selected = bool(((maph >> 12) & 0xF) & (1 << b_block))
    require(b_block == 1 and not b_selected,
            "witness is selected by the established MAP tuple")

    return {
        "linked_route": {
            "ownership_call": "0xa4e0", "overlay_install_call": "0xa4e6",
            "sole_executable_MAP": "0xb604",
            "overlay_entry": "0xc85a", "before_capture": "0xc048",
            "after_capture": "0xc04e",
            "ownership_precedes_overlay": True,
        },
        "write_time_view": {
            "MAPH": "0x8000", "MAPL": "0x0000",
            "selected_blocks": ["0xe000-0xffff"],
            "witness": ["0xb582", "0xb58c"],
            "witness_block_selected": False,
            "mapped_MB_relevant": False,
            "store_destination": "physical-bank0-RAM-underlay",
            "IRQ_and_NMI_change_MAP": False,
        },
        "observation": {
            "physical_read": "d1ccccccccd2cccccccc",
            "before_commit_seen": False, "after_commit_seen": False,
            "mapped_elsewhere_explanation_rejected": True,
        },
        "disposition": {
            "classification": "PRE-MEM-INIT-WITNESS-NOT-COMMITTED",
            "binary_mem_init_answer": None, "R_A_I_G": None,
            "product_fault": None, "new_contact_authorized": False,
            "next_required": (
                "desk-design a mapping-independent progress partition between "
                "the proven _start witness and the uncommitted C85A capture"),
        },
        "scope": {"device_actions": 0, "product_bytes": 0,
                  "links": 0, "measured_forms": 0},
    }


def audit(value: dict[str, Any]) -> None:
    require(value["linked_route"] == {
        "ownership_call": "0xa4e0", "overlay_install_call": "0xa4e6",
        "sole_executable_MAP": "0xb604", "overlay_entry": "0xc85a",
        "before_capture": "0xc048", "after_capture": "0xc04e",
        "ownership_precedes_overlay": True}, "linked route claim drift")
    require(value["write_time_view"] == {
        "MAPH": "0x8000", "MAPL": "0x0000",
        "selected_blocks": ["0xe000-0xffff"],
        "witness": ["0xb582", "0xb58c"],
        "witness_block_selected": False, "mapped_MB_relevant": False,
        "store_destination": "physical-bank0-RAM-underlay",
        "IRQ_and_NMI_change_MAP": False}, "write-time view claim drift")
    require(value["observation"] == {
        "physical_read": "d1ccccccccd2cccccccc",
        "before_commit_seen": False, "after_commit_seen": False,
        "mapped_elsewhere_explanation_rejected": True},
        "witness observation claim drift")
    disposition = value["disposition"]
    require(disposition["classification"] ==
                "PRE-MEM-INIT-WITNESS-NOT-COMMITTED"
            and disposition["binary_mem_init_answer"] is None
            and disposition["R_A_I_G"] is None
            and disposition["product_fault"] is None
            and not disposition["new_contact_authorized"]
            and "mapping-independent progress partition" in
                disposition["next_required"],
            "desk disposition drift")
    require(value["scope"] == {"device_actions": 0, "product_bytes": 0,
                                "links": 0, "measured_forms": 0},
            "desk scope drift")


def selftest() -> dict[str, Any]:
    base = exact()
    mutations = [
        (["linked_route", "ownership_precedes_overlay"], False),
        (["linked_route", "sole_executable_MAP"], "0xc048"),
        (["write_time_view", "MAPH"], "0xb300"),
        (["write_time_view", "witness_block_selected"], True),
        (["write_time_view", "mapped_MB_relevant"], True),
        (["write_time_view", "store_destination"], "mapped-unknown"),
        (["write_time_view", "IRQ_and_NMI_change_MAP"], True),
        (["observation", "before_commit_seen"], True),
        (["observation", "mapped_elsewhere_explanation_rejected"], False),
        (["disposition", "binary_mem_init_answer"], "never-established"),
        (["disposition", "R_A_I_G"], "R"),
        (["disposition", "new_contact_authorized"], True),
    ]
    rejected: dict[str, str] = {}
    for index, (path, replacement) in enumerate(mutations, 1):
        trial = deepcopy(base)
        cursor: Any = trial
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except ViewError as error:
            rejected[f"mutation-{index:02d}"] = str(error)
        else:
            raise ViewError(f"write-view mutation survived: {path}")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "rejected": rejected}


def expected() -> dict[str, Any]:
    value = exact()
    audit(value)
    return {
        "format": "lisp65-c2.3-v1.6-mem-init-witness-write-view-desk-v1",
        "recorded_on": RECORDED_ON,
        "status": "DESK ATTRIBUTION PASS; WITNESS VIEW VALID; PRE-HOOK UNCOMMITTED",
        "authorities": {
            "mapping_result": C.bind(RESULT), "device": C.bind(DEVICE),
            "witness_preparation": C.bind(PREPARATION),
            "ownership": C.bind(OWNERSHIP), "diagnostic_ELF": C.bind(W.DIAG_ELF),
            "primary_core": C.bind(CORE), "MAP_source": C.bind(MAP_SOURCE),
            "window_source": C.bind(WINDOW_SOURCE), "driver": C.bind(DRIVER),
        },
        "facts": value, "mutations_rejected": selftest()["rejected"],
        "claim_limit": (
            "Desk-only write-time view attribution. The physical witness was not "
            "redirected by MAP, so neither tagged capture committed. This does not "
            "answer the mem_init binary question, classify R/A/I/G, name a product "
            "fault, or authorize another contact."),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "write":
        RECEIPT.write_bytes(canonical(expected()))
        value = {"status": "WROTE", "path": str(RECEIPT.relative_to(ROOT))}
    elif args.action == "selftest":
        value = selftest()
    else:
        value = expected()
        require(RECEIPT.read_bytes() == canonical(value),
                "write-view desk receipt drift; run write deliberately")
        value = {"status": "PASS", "mutations": len(selftest()["rejected"])}
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ViewError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"MEM_INIT WITNESS WRITE VIEW FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
