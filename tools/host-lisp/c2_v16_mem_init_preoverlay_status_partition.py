#!/usr/bin/env python3
"""Prepare the read-only pre-overlay status partition for the retained stop."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402
import c2_v16_mem_init_before_after as W  # noqa: E402
import c2_v16_mem_init_before_after_contact as C  # noqa: E402


RECORDED_ON = "2026-08-06"
WRITE_VIEW = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mem-init-witness-write-view-desk-attribution-receipt.json")
RESULT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mem-init-repeat-mapping-result.json")
SOURCE = ROOT / "build/c2.3/v1.6-defstruct-phase-c/source/src/vm_boot_overlay.c"
HEADER = ROOT / "build/c2.3/v1.6-defstruct-phase-c/source/src/vm_boot_overlay.h"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mem-init-preoverlay-status-partition-preparation.json")
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


class PartitionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PartitionError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def exact() -> dict[str, Any]:
    write_view, result, device = load(WRITE_VIEW), load(RESULT), load(C.DEVICE)
    require(write_view["facts"]["disposition"]["classification"] ==
                "PRE-MEM-INIT-WITNESS-NOT-COMMITTED"
            and not write_view["facts"]["disposition"]["new_contact_authorized"],
            "write-view disposition drift")
    require(result["facts"]["stop_boundary"] == {
        "B_block_selected": True, "MAPH": "0xb300", "MAPL": "0xe300",
        "PC": "0xe160", "code_owner": "unresolved",
        "mapped_B_MB_claim": None, "underlay_runtime_values_promoted": False},
        "retained-stop boundary drift")
    registers = device["stop"]["registers"]
    require({key: registers[key] for key in
             ("PC", "B", "SP", "MAPH", "MAPL")} == {
                 "PC": "0xe160", "B": "0x00", "SP": "0x01ee",
                 "MAPH": "0xb300", "MAPL": "0xe300"},
            "retained register tuple drift")

    truth = ElfTruth.read(W.DIAG_ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    symbols = {name: truth.symbol(name) for name in (
        "vm_boot_overlay_status", "ov_started", "c2_ready", "mem_oom")}
    require({name: (row.value, row.bytes) for name, row in symbols.items()} == {
        "vm_boot_overlay_status": (0x74, 1), "ov_started": (0x75, 1),
        "c2_ready": (0x8C, 1), "mem_oom": (0x8F, 1)},
        "resident status symbol drift")

    header = HEADER.read_text(encoding="utf-8")
    ordered = ["VM_BOOT_OVERLAY_OK", "VM_BOOT_OVERLAY_ERR_MAGIC",
               "VM_BOOT_OVERLAY_ERR_VERSION", "VM_BOOT_OVERLAY_ERR_HEADER",
               "VM_BOOT_OVERLAY_ERR_PROFILE", "VM_BOOT_OVERLAY_ERR_VMA",
               "VM_BOOT_OVERLAY_ERR_ENTRY", "VM_BOOT_OVERLAY_ERR_LENGTH",
               "VM_BOOT_OVERLAY_ERR_CRC", "VM_BOOT_OVERLAY_ERR_ENTRY_RUN",
               "VM_BOOT_OVERLAY_ERR_WIPE", "VM_BOOT_OVERLAY_ERR_REENTRY"]
    positions = [header.index(name) for name in ordered]
    require(positions == sorted(positions), "boot status enum order drift")
    source = SOURCE.read_text(encoding="utf-8")
    require("ov_started = 1;\n    vm_boot_overlay_status = "
            "VM_BOOT_OVERLAY_ERR_LENGTH;" in source
            and "vm_boot_overlay_status = VM_BOOT_OVERLAY_ERR_ENTRY_RUN;"
                in source
            and "FIRST_CALL();" in source
            and source.index("VM_BOOT_OVERLAY_ERR_ENTRY_RUN") <
                source.index("FIRST_CALL();") < source.index(
                    "VM_BOOT_OVERLAY_ERR_WIPE"),
            "boot progress status ordering drift")

    # MAPL=$E300 selects low blocks 1,2,3 but not block 0; with B=0 the
    # physical Zero-Page status bytes are the executing CPU's data cells.
    mapl = int(registers["MAPL"], 16)
    zp_selected = bool(((mapl >> 12) & 0xF) & 1)
    require(not zp_selected and registers["B"] == "0x00",
            "retained stop cannot expose physical Zero Page")

    return {
        "retained_stop": {
            "PC": "0xe160", "MAPH": "0xb300", "MAPL": "0xe300",
            "B": "0x00", "SP": "0x01ee", "CPU_already_stopped": True,
            "same_stop_required": True,
        },
        "read_plan": {
            "first": "re-read full register row and require exact retained tuple",
            "status_pair": {"physical_address": "0x00000074", "bytes": 2,
                            "fields": ["vm_boot_overlay_status", "ov_started"]},
            "health_row": {"physical_address": "0x0000008c", "bytes": 4,
                           "fields": ["c2_ready", "reserved-8d", "reserved-8e",
                                      "mem_oom"]},
            "visibility": "MAPL block-0 unselected and B=0",
            "additional_RUNs": 0, "additional_monitor_entries": 0,
            "additional_stops": 0, "CPU_resume": False,
        },
        "decision_table": {
            "started=0": "PRE-INSTALLER-BOUNDARY",
            "started=1,status=1..8": "INSTALLER-OR-STAGER-PRE-ENTRY-BOUNDARY",
            "started=1,status=9": "ENTRY-RUN-BOUNDARY-BEFORE-CAPTURE-COMMIT",
            "started=1,status=0-or-10": "IDENTITY-OR-STATUS-CONTRADICTION-FIRST-RED",
            "status=11": "REENTRY-FAIL-CLOSED",
            "other": "UNCLASSIFIED-FIRST-RED",
        },
        "authorization": {
            "same_stop_read_authorized": False,
            "new_launch_authorized": False,
            "new_stop_authorized": False,
            "measured_form_authorized": False,
            "owner_decision_required": True,
        },
        "claim_limit": {
            "mem_init_answer": None, "R_A_I_G": None,
            "product_fault": None, "product_bytes": 0, "device_actions": 0,
        },
    }


def audit(value: dict[str, Any]) -> None:
    require(value["retained_stop"] == {
        "PC": "0xe160", "MAPH": "0xb300", "MAPL": "0xe300",
        "B": "0x00", "SP": "0x01ee", "CPU_already_stopped": True,
        "same_stop_required": True}, "retained-stop claim drift")
    read_plan = value["read_plan"]
    require(read_plan["status_pair"] == {
        "physical_address": "0x00000074", "bytes": 2,
        "fields": ["vm_boot_overlay_status", "ov_started"]}
        and read_plan["health_row"] == {
            "physical_address": "0x0000008c", "bytes": 4,
            "fields": ["c2_ready", "reserved-8d", "reserved-8e", "mem_oom"]}
        and read_plan["visibility"] == "MAPL block-0 unselected and B=0"
        and (read_plan["additional_RUNs"],
             read_plan["additional_monitor_entries"],
             read_plan["additional_stops"]) == (0, 0, 0)
        and not read_plan["CPU_resume"], "salvage read plan drift")
    require(value["decision_table"] == {
        "started=0": "PRE-INSTALLER-BOUNDARY",
        "started=1,status=1..8": "INSTALLER-OR-STAGER-PRE-ENTRY-BOUNDARY",
        "started=1,status=9": "ENTRY-RUN-BOUNDARY-BEFORE-CAPTURE-COMMIT",
        "started=1,status=0-or-10": "IDENTITY-OR-STATUS-CONTRADICTION-FIRST-RED",
        "status=11": "REENTRY-FAIL-CLOSED", "other": "UNCLASSIFIED-FIRST-RED"},
        "status decision table drift")
    require(value["authorization"] == {
        "same_stop_read_authorized": False, "new_launch_authorized": False,
        "new_stop_authorized": False, "measured_form_authorized": False,
        "owner_decision_required": True}, "salvage authorization overclaim")
    require(value["claim_limit"] == {
        "mem_init_answer": None, "R_A_I_G": None, "product_fault": None,
        "product_bytes": 0, "device_actions": 0}, "claim-limit drift")


def selftest() -> dict[str, Any]:
    base = exact()
    mutations = [
        (["retained_stop", "PC"], "0xe161"),
        (["retained_stop", "same_stop_required"], False),
        (["read_plan", "status_pair", "physical_address"], "0x0000b582"),
        (["read_plan", "visibility"], "guessed mapped view"),
        (["read_plan", "additional_monitor_entries"], 1),
        (["read_plan", "CPU_resume"], True),
        (["decision_table", "started=1,status=0-or-10"], "SUCCESS"),
        (["authorization", "same_stop_read_authorized"], True),
        (["authorization", "new_launch_authorized"], True),
        (["authorization", "owner_decision_required"], False),
        (["claim_limit", "mem_init_answer"], "never-established"),
        (["claim_limit", "R_A_I_G"], "G"),
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
        except PartitionError as error:
            rejected[f"mutation-{index:02d}"] = str(error)
        else:
            raise PartitionError(f"status-partition mutation survived: {path}")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "rejected": rejected}


def expected() -> dict[str, Any]:
    value = exact()
    audit(value)
    return {
        "format": "lisp65-c2.3-v1.6-mem-init-preoverlay-status-partition-v1",
        "recorded_on": RECORDED_ON,
        "status": "HOST-GREEN; OWNER DECISION REQUIRED FOR SAME-STOP READ",
        "authorities": {
            "write_view": C.bind(WRITE_VIEW), "mapping_result": C.bind(RESULT),
            "device": C.bind(C.DEVICE), "diagnostic_ELF": C.bind(W.DIAG_ELF),
            "boot_source": C.bind(SOURCE), "boot_header": C.bind(HEADER),
            "driver": C.bind(DRIVER),
        },
        "facts": value, "mutations_rejected": selftest()["rejected"],
        "claim_limit": (
            "Desk-only partition for the retained stopped state. No read, RUN, "
            "monitor entry, stop, resume, measured form, mem_init result, R/A/I/G "
            "row or product fault is authorized or claimed."),
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
                "pre-overlay status-partition receipt drift; run write deliberately")
        value = {"status": "PASS", "mutations": len(selftest()["rejected"])}
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PartitionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"MEM_INIT PREOVERLAY STATUS PARTITION FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(1)
