#!/usr/bin/env python3
"""Recover the consumed repeat contact from its already stopped state.

The original capture stopped once, retained MAPH/MAPL, then rejected a mapping
outside its single closed $8000/$0000 row before reading any data.  This helper
does not enter the monitor or stop/resume the CPU.  It reads the deliberately
fixed physical Bank-0 witness underlay and lets only committed non-zero tags
select a mem_init decision row.  Code identity remains a CPU-view observation.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v16_mem_init_before_after_contact as C  # noqa: E402


CAPTURE_COMMIT = "50817fd2"
RECOVERY_COMMIT = "f32431ad"
CORE_COMMIT = "a9158930665763c592d004c895d52eff4a9eefc3"
CORE = ROOT / "build/upstream-verification/mega65-core/src/vhdl/gs4510.vhdl"
PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mem-init-repeat-mapping-recovery-preparation.json")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mem-init-repeat-mapping-first-red.json")
RESULT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mem-init-repeat-mapping-result.json")
DRIVER = Path(__file__).resolve()
EXPECTED_MAPH = 0xB300
EXPECTED_MAPL = 0xE300


def check_consumed_preparation() -> None:
    """Keep the exact preparation that authorized the consumed recovery."""
    prep_path = PREP.relative_to(ROOT).as_posix()
    _full, consumed = C.git_blob(RECOVERY_COMMIT, prep_path)
    C.require(PREP.read_bytes() == consumed,
              "consumed mapping recovery preparation drift")


def map_selected(logical: int, map_register: int) -> bool:
    return bool(((map_register >> 12) & 0xF) &
                (1 << ((logical >> 13) & 0x3)))


def facts() -> dict[str, Any]:
    core = CORE.read_text(encoding="utf-8")
    for token in ("if reg_map_high(blocknum)='1'",
                  "if reg_map_low(blocknum)='1'",
                  "temp_address(27 downto 20) := reg_mb_high",
                  "temp_address(27 downto 20) := reg_mb_low"):
        C.require(token in core, f"primary MAP token absent: {token}")
    selections = {
        "zero_page": map_selected(0x003D, EXPECTED_MAPL),
        "B000_witness": map_selected(C.WITNESS, EXPECTED_MAPH),
        "C000_record": map_selected(C.RECORD, EXPECTED_MAPH),
    }
    C.require(selections == {"zero_page": False, "B000_witness": True,
                              "C000_record": False},
              f"captured mapping selection drift: {selections}")
    return {
        "consumed_contact": {"physical_RUNs": 1, "stops": 1,
                             "capture_consumed": True,
                             "device_receipt_present": False},
        "first_red": {"MAPH": "0xb300", "MAPL": "0xe300",
                      "failure_before_data_reads": True,
                      "mem_init_answer": None, "R_A_I_G": None},
        "mapping": {"primary_core_commit": CORE_COMMIT,
                    "selected": selections,
                    "mapped_B_block_MB_not_exposed_by_monitor_row": True},
        "recovery": {
            "additional_RUNs": 0, "additional_monitor_entries": 0,
            "additional_stops": 0, "CPU_already_stopped": True,
            "code": "CPU-resolved view with owner binding",
            "data": "fixed physical Bank-0 underlay plus physical Bank-5 C2J",
            "tag_rule": "only A1/A6 committed tags select a binary row",
            "missing_tags": "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM",
            "CPU_left_stopped": True,
        },
        "scope": {"product_bytes": 0, "links": 0, "measured_forms": 0,
                  "new_contact": False, "R_A_I_G": None},
    }


def audit(value: dict[str, Any]) -> None:
    C.require(value["consumed_contact"] == {
        "physical_RUNs": 1, "stops": 1, "capture_consumed": True,
        "device_receipt_present": False}, "contact accounting drift")
    C.require(value["first_red"] == {
        "MAPH": "0xb300", "MAPL": "0xe300",
        "failure_before_data_reads": True, "mem_init_answer": None,
        "R_A_I_G": None}, "mapping First Red claim drift")
    C.require(value["mapping"]["selected"] == {
        "zero_page": False, "B000_witness": True, "C000_record": False}
        and value["mapping"]["mapped_B_block_MB_not_exposed_by_monitor_row"],
        "mapping selection/MB boundary drift")
    C.require(value["recovery"] == {
        "additional_RUNs": 0, "additional_monitor_entries": 0,
        "additional_stops": 0, "CPU_already_stopped": True,
        "code": "CPU-resolved view with owner binding",
        "data": "fixed physical Bank-0 underlay plus physical Bank-5 C2J",
        "tag_rule": "only A1/A6 committed tags select a binary row",
        "missing_tags": "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM",
        "CPU_left_stopped": True}, "same-stop recovery drift")
    C.require(value["scope"] == {"product_bytes": 0, "links": 0,
                                  "measured_forms": 0, "new_contact": False,
                                  "R_A_I_G": None}, "scope drift")


def selftest() -> dict[str, Any]:
    base = facts()
    cases = [
        (["consumed_contact", "physical_RUNs"], 2),
        (["first_red", "failure_before_data_reads"], False),
        (["first_red", "mem_init_answer"], "mem-init-empty"),
        (["mapping", "selected", "B000_witness"], False),
        (["mapping", "mapped_B_block_MB_not_exposed_by_monitor_row"], False),
        (["recovery", "additional_monitor_entries"], 1),
        (["recovery", "tag_rule"], "interpret reset bytes"),
        (["scope", "new_contact"], True),
        (["scope", "R_A_I_G"], "R"),
    ]
    rejected: dict[str, str] = {}
    for index, (path, replacement) in enumerate(cases, 1):
        trial = deepcopy(base)
        cursor: Any = trial
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except C.ContactError as error:
            rejected[f"mutation-{index:02d}"] = str(error)
        else:
            raise C.ContactError(f"mapping recovery mutation survived: {path}")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "rejected": rejected}


def expected() -> dict[str, Any]:
    value = facts()
    audit(value)
    capture_full, capture_driver = C.git_blob(
        CAPTURE_COMMIT,
        "tools/host-lisp/c2_v16_mem_init_before_after_contact.py")
    return {
        "format": "lisp65-c2.3-v1.6-mem-init-repeat-mapping-recovery-preparation-v1",
        "recorded_on": "2026-08-06",
        "status": "HOST-GREEN; SAME-STOP MAPPING RECOVERY READY",
        "authorities": {
            "consumed_preparation": C.bind(C.PREP),
            "consumed_capture_driver": C.bind_blob(
                f"git:{capture_full}:tools/host-lisp/"
                "c2_v16_mem_init_before_after_contact.py", capture_driver),
            "primary_core": C.bind(CORE), "driver": C.bind(DRIVER),
        },
        "facts": value, "mutations_rejected": selftest()["rejected"],
        "claim_limit": (
            "Desk closure and read-only completion of the already stopped contact. "
            "No new RUN, monitor entry, stop, measured form, product claim or "
            "R/A/I/G claim is authorized."),
    }


def mapping(registers: dict[str, Any]) -> dict[str, Any]:
    maph = int(registers["MAPH"], 16)
    mapl = int(registers["MAPL"], 16)
    C.require((maph, mapl) == (EXPECTED_MAPH, EXPECTED_MAPL),
              f"stopped mapping moved: {maph:04x}/{mapl:04x}")
    return {"MAPH": "0xb300", "MAPL": "0xe300",
            "raw_flag_values": registers["tail"],
            "selected": facts()["mapping"]["selected"],
            "data_authority": "fixed physical underlay; not current mapped B view",
            "mapped_B_block_MB_claim": None}


def stopped_read(fd: int) -> dict[str, Any]:
    registers = C.VIEW.read_registers(fd)
    view = mapping(registers)
    pc = int(registers["PC"], 16)
    code, code_reads = C.APPT.read_cpu_block(fd, pc, min(16, 0x10000 - pc))
    owner = C.code_owner(pc, code)
    values: dict[str, tuple[bytes, list[dict[str, Any]]]] = {}
    for name, address, size in (
        ("mem_init_witness", C.WITNESS, C.WITNESS_BYTES),
        ("boot_witness", C.BOOT_WITNESS, 1),
        ("freelist", C.FREELIST, 2), ("alloc_high", C.ALLOC_HIGH, 2),
        ("gc_frozen", C.GC_FROZEN, 2), ("gc_runs", C.GC_RUNS, 2),
        ("diagnostic_record", C.RECORD, C.RECORD_BYTES),
        ("phase_scratch", C.PHASE, C.PHASE_BYTES),
        ("phase_owner", C.PHASE_OWNER, 1),
    ):
        values[name] = C.LADDER.read_physical(fd, address, size)
    values["C2J"] = C.read_absolute(fd, C.C2J, C.C2J_BYTES,
                                     "physical-Bank5-C2J")
    return {"registers": registers, "mapping": view, "PC": registers["PC"],
            "code_owner": owner, "code_reads": code_reads, "values": values}


def recover(device: str) -> dict[str, Any]:
    C.require(C.load(PREP) == expected(), "mapping recovery preparation drift")
    C.require((C.OUT / "capture.consumed").is_file(), "consumed stop absent")
    C.require(not C.DEVICE.exists(), "repeat device receipt already exists")
    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        C.SERIAL.configure_serial(fd)
        read = stopped_read(fd)
    finally:
        os.close(fd)
    first_red = {
        "format": "lisp65-c2.3-v1.6-mem-init-repeat-mapping-first-red-v1",
        "recorded_on": date.today().isoformat(),
        "status": "TOOL-FIRST-RED; STOP CONSUMED; NO DATA READ; NO MEM_INIT CLAIM",
        "authorities": {"recovery_preparation": C.bind(PREP)},
        "stopped_mapping": read["mapping"],
        "contact": {"physical_RUNs": 1, "stops": 1,
                    "additional_RUNs": 0, "additional_monitor_entries": 0,
                    "additional_stops": 0},
        "cause": ("The capture accepted only MAPH=$8000/MAPL=$0000 and rejected "
                  "the retained $B300/$E300 row before its first data read."),
        "claim_limit": "Tool mapping First Red only; no mem_init or R/A/I/G claim.",
    }
    C.write_json(FIRST_RED, first_red)
    receipt = C.result_receipt(read, {
        "required_seconds": C.QUIET_SECONDS,
        "original_capture_completed_quiet_floor_before_stop": True,
        "exact_elapsed_preserved_by_consumed_capture": True,
        "early_monitor_accesses": 0,
    }, {"same_stopped_state": True, "additional_RUN": 0,
        "additional_monitor_entries": 0, "additional_stops": 0,
        "mapping_recovery": True})
    receipt["format"] = "lisp65-c2.3-v1.6-mem-init-before-after-repeat-device-v1"
    receipt["device"] = device
    receipt["authorities"]["mapping_recovery_preparation"] = C.bind(PREP)
    receipt["authorities"]["mapping_first_red"] = C.bind(FIRST_RED)
    receipt["authorities"]["mapping_recovery_driver"] = C.bind(DRIVER)
    C.write_json(C.DEVICE, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return receipt


def result_facts() -> dict[str, Any]:
    device = C.load(C.DEVICE)
    first_red = C.load(FIRST_RED)
    C.require(device["status"] == "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM"
              and device["snapshots"]["raw_hex"] == "d1ccccccccd2cccccccc",
              "repeat decision evidence drift")
    C.require(device["current"]["boot_witness"] == "0x44"
              and device["current"]["C2J_nonzero_bytes"] == 0,
              "boot/C2J closure drift")
    C.require(device["stop"]["mapping"]["MAPH"] == "0xb300"
              and device["stop"]["mapping"]["MAPL"] == "0xe300"
              and not device["stop"]["code_owner"]["unique"],
              "stopped mapping/owner boundary drift")
    recovery = device["same_contact_recovery"]
    C.require(recovery == {"same_stopped_state": True, "additional_RUN": 0,
                            "additional_monitor_entries": 0,
                            "additional_stops": 0, "mapping_recovery": True},
              "same-stop accounting drift")
    C.require(first_red["contact"] == {"physical_RUNs": 1, "stops": 1,
                                        "additional_RUNs": 0,
                                        "additional_monitor_entries": 0,
                                        "additional_stops": 0},
              "mapping First Red accounting drift")
    return {
        "contact": {"physical_RUNs": 1, "stops": 1,
                    "same_stop_recovery": True,
                    "additional_RUNs_monitor_entries_or_stops": 0},
        "preconditions": {"reset_domain_bytes": 50816,
                          "full_target_readback": True,
                          "C2J_CLEAR_before_RUN": True,
                          "C2J_CLEAR_at_stop": True,
                          "boot_entry_witness": "0x44"},
        "mem_init_witness": {"raw": "d1ccccccccd2cccccccc",
                             "before_reached": False,
                             "after_reached": False,
                             "binary_answer": None},
        "stop_boundary": {"MAPH": "0xb300", "MAPL": "0xe300",
                          "PC": "0xe160", "code_owner": "unresolved",
                          "B_block_selected": True,
                          "mapped_B_MB_claim": None,
                          "underlay_runtime_values_promoted": False},
        "disposition": {"classification":
                            "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM",
                        "R_A_I_G": None, "product_fault": None,
                        "new_contact_authorized": False,
                        "next_required": (
                            "desk-bind the write-time mapping/visibility of the "
                            "$B582 witness hooks before any further device action")},
    }


def audit_result(value: dict[str, Any]) -> None:
    C.require(value["contact"] == {"physical_RUNs": 1, "stops": 1,
                                    "same_stop_recovery": True,
                                    "additional_RUNs_monitor_entries_or_stops": 0},
              "result contact accounting drift")
    C.require(value["preconditions"] == {"reset_domain_bytes": 50816,
                                          "full_target_readback": True,
                                          "C2J_CLEAR_before_RUN": True,
                                          "C2J_CLEAR_at_stop": True,
                                          "boot_entry_witness": "0x44"},
              "result precondition drift")
    C.require(value["mem_init_witness"] == {
        "raw": "d1ccccccccd2cccccccc", "before_reached": False,
        "after_reached": False, "binary_answer": None},
        "mem_init result overclaim")
    C.require(value["stop_boundary"] == {
        "MAPH": "0xb300", "MAPL": "0xe300", "PC": "0xe160",
        "code_owner": "unresolved", "B_block_selected": True,
        "mapped_B_MB_claim": None, "underlay_runtime_values_promoted": False},
        "stop-boundary claim drift")
    disposition = value["disposition"]
    C.require(disposition["classification"] ==
                "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM"
              and disposition["R_A_I_G"] is None
              and disposition["product_fault"] is None
              and not disposition["new_contact_authorized"]
              and "write-time mapping" in disposition["next_required"],
              "result disposition drift")


def result_selftest() -> dict[str, Any]:
    base = result_facts()
    cases = [
        (["contact", "physical_RUNs"], 2),
        (["preconditions", "C2J_CLEAR_before_RUN"], False),
        (["preconditions", "boot_entry_witness"], "0xd7"),
        (["mem_init_witness", "before_reached"], True),
        (["mem_init_witness", "binary_answer"], "never established"),
        (["stop_boundary", "code_owner"], "product"),
        (["stop_boundary", "mapped_B_MB_claim"], "0x00"),
        (["stop_boundary", "underlay_runtime_values_promoted"], True),
        (["disposition", "R_A_I_G"], "R"),
        (["disposition", "product_fault"], "mem_init"),
        (["disposition", "new_contact_authorized"], True),
    ]
    rejected: dict[str, str] = {}
    for index, (path, replacement) in enumerate(cases, 1):
        trial = deepcopy(base)
        cursor: Any = trial
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = replacement
        try:
            audit_result(trial)
        except C.ContactError as error:
            rejected[f"mutation-{index:02d}"] = str(error)
        else:
            raise C.ContactError(f"mapping result mutation survived: {path}")
    return {"status": "RESULT SELFTEST PASS", "mutations": len(rejected),
            "rejected": rejected}


def expected_result() -> dict[str, Any]:
    value = result_facts()
    audit_result(value)
    recovery_full, recovery_driver = C.git_blob(
        RECOVERY_COMMIT,
        "tools/host-lisp/c2_v16_mem_init_repeat_mapping_recovery.py")
    return {
        "format": "lisp65-c2.3-v1.6-mem-init-repeat-mapping-result-v1",
        "recorded_on": "2026-08-06",
        "status": "CONTACT CLOSED UNCLASSIFIED; WRITE-TIME MAPPING DESK BINDING REQUIRED",
        "authorities": {"device": C.bind(C.DEVICE),
                        "mapping_first_red": C.bind(FIRST_RED),
                        "recovery_preparation": C.bind(PREP),
                        "recovery_driver": C.bind_blob(
                            f"git:{recovery_full}:tools/host-lisp/"
                            "c2_v16_mem_init_repeat_mapping_recovery.py",
                            recovery_driver)},
        "facts": value, "mutations_rejected": result_selftest()["rejected"],
        "claim_limit": (
            "The repeat proves complete reset-domain/C2J preconditions and one "
            "unclassified stopped contact. Untouched physical tags do not answer "
            "mem_init while their write-time mapping is unbound. No product fault, "
            "R/A/I/G result or new contact is claimed."),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=(
        "prepare", "check", "selftest", "recover", "close",
        "result-selftest", "result-check"))
    parser.add_argument("--device", default=os.environ.get("DEVICE", "/dev/ttyUSB1"))
    args = parser.parse_args()
    if args.action == "prepare":
        value = expected()
        C.write_json(PREP, value)
    elif args.action == "check":
        check_consumed_preparation()
        value = {"status": "PASS", "mutations": len(selftest()["rejected"])}
    elif args.action == "selftest":
        value = selftest()
    elif args.action == "recover":
        value = recover(args.device)
    elif args.action == "close":
        value = expected_result()
        C.write_json(RESULT, value)
    elif args.action == "result-selftest":
        value = result_selftest()
    else:
        value = expected_result()
        C.require(C.load(RESULT) == value, "mapping result receipt drift")
        value = {"status": "RESULT PASS",
                 "mutations": len(result_selftest()["rejected"])}
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (C.ContactError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"c2-v16-mem-init-mapping-recovery: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
