#!/usr/bin/env python3
"""Prepare and capture the owner-authorized mem_init before/after contact.

The target writes both snapshots.  This driver waits through the bound launch
floor, enters the monitor once, captures the mapping row, and reads all data
from physical RAM.  It deliberately does not run require/defstruct or assign
an R/A/I/G outcome.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402
import c2_v16_corrected_view_contact as VIEW  # noqa: E402
import c2_v16_full_ladder_contact as LADDER  # noqa: E402
import c2_v16_mem_init_before_after as BUILD  # noqa: E402
import c2_v16_romc_repaired_d2_appointment as APPT  # noqa: E402


OUT = ROOT / (
    "build/c2.3/v1.6-defstruct-closing-session/"
    "d2-mem-init-before-after-repeat-contact")
PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mem-init-before-after-repeat-preparation-receipt.json")
DEVICE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mem-init-before-after-repeat-device-receipt.json")
FIRST_OUT = ROOT / (
    "build/c2.3/v1.6-defstruct-closing-session/"
    "d2-mem-init-before-after-contact")
FIRST_DEVICE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mem-init-before-after-device-receipt.json")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mem-init-before-after-capture-first-red.json")
RESULT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mem-init-before-after-staging-first-red-receipt.json")
RESET_DOMAIN_AUTHORITY = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link85-full-reset-domain-host-receipt.json")
DAY_ROLLOVER_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mem-init-repeat-day-rollover-first-red.json")
RUNNER = ROOT / "scripts/c2-v16-defstruct-mem-init-before-after-hw.sh"
DRIVER = Path(__file__).resolve()

WITNESS = 0xB582
WITNESS_BYTES = 10
BEFORE_TAG = 0xA1
AFTER_TAG = 0xA6
BEFORE_RESET = 0xD1
AFTER_RESET = 0xD2
BOOT_WITNESS = 0xB5C3
BOOT_STAMP = 0x44
FREELIST = 0x003D
ALLOC_HIGH = 0x0039
GC_FROZEN = 0x003B
GC_RUNS = 0xB9F0
RECORD = 0xC03F
RECORD_BYTES = 65
PHASE = 0xC0C6
PHASE_BYTES = 304
FIRST_ERROR_OFFSET = 302
PHASE_OWNER = 0x0089
C2J = 0x05C640
C2J_BYTES = 64
QUIET_SECONDS = 27.653
HEAP_CELLS = 48
EXT_CELLS = 1024
ORIGINAL_CONTACT_COMMIT = "7864ee13"
RESULT_CLOSE_COMMIT = "ce46e229"
REPEAT_OWNER_COMMIT = "049e0b08"
PLAN = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
PREPARATION_RECORDED_ON = "2026-08-05"
HISTORICAL_RESULT_RECORDED_ON = "2026-08-05"


class ContactError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ContactError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    try:
        label = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        label = str(path.resolve())
    return {"path": label, "bytes": len(raw), "sha256": digest(raw)}


def bind_blob(label: str, raw: bytes) -> dict[str, Any]:
    return {"path": label, "bytes": len(raw), "sha256": digest(raw)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def git_blob(commit: str, path: str) -> tuple[str, bytes]:
    result = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0, "consumed contact commit absent")
    full = result.stdout.decode().strip()
    result = subprocess.run(
        ["git", "show", f"{full}:{path}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0, f"consumed authority absent: {path}")
    return full, result.stdout


def ext_occupancy(alloc_high: int) -> int:
    if alloc_high < HEAP_CELLS:
        return 0
    return min(EXT_CELLS, alloc_high - HEAP_CELLS + 1)


def prg_slice(raw: bytes, address: int, size: int) -> bytes | None:
    if len(raw) < 2:
        return None
    at = 2 + address - int.from_bytes(raw[:2], "little")
    if at < 2 or at + size > len(raw):
        return None
    return raw[at:at + size]


def code_owner(logical: int, observed: bytes) -> dict[str, Any]:
    deployment = load(BUILD.DEPLOY)
    candidates: dict[str, bytes] = {}
    overlay = BUILD.BOOT_RAW.read_bytes()
    if (BUILD.OVERLAY_START <= logical
            and logical + len(observed) <= BUILD.OVERLAY_START + len(overlay)):
        at = logical - BUILD.OVERLAY_START
        candidates["mem-init-before-after-workbench-overlay"] = overlay[
            at:at + len(observed)]
    else:
        prg = (ROOT / deployment["diagnostic"]["prg"]["path"]).read_bytes()
        resident = prg_slice(prg, logical, len(observed))
        if resident is not None:
            candidates["mem-init-before-after-diagnostic-PRG"] = resident
    if 0xE000 <= logical and logical + len(observed) <= 0x10000:
        window = (ROOT / deployment["diagnostic"]["window"]["path"]).read_bytes()
        candidates["diagnostic-E000-window"] = window[
            logical - 0xE000:logical - 0xE000 + len(observed)]
    rom = APPT.rom_path().read_bytes()[0x10000:]
    if logical + len(observed) <= len(rom):
        candidates["MEGA65-ROM"] = rom[logical:logical + len(observed)]
    matches = [name for name, raw in candidates.items() if raw == observed]
    return {"logical_address": f"0x{logical:04x}",
            "observed": observed.hex(),
            "candidate_bytes": {name: raw.hex()
                                for name, raw in sorted(candidates.items())},
            "matches": matches,
            "selected_owner": matches[0] if len(matches) == 1 else "unresolved",
            "unique": len(matches) == 1,
            "symbol_interpretation_allowed": len(matches) == 1}


def decode_snapshot(raw: bytes) -> dict[str, Any]:
    require(len(raw) == WITNESS_BYTES, "snapshot length drift")
    before_head = int.from_bytes(raw[1:3], "little")
    before_high = int.from_bytes(raw[3:5], "little")
    after_head = int.from_bytes(raw[6:8], "little")
    after_high = int.from_bytes(raw[8:10], "little")
    return {
        "raw_hex": raw.hex(),
        "before": {"tag": f"0x{raw[0]:02x}",
                   "reached": raw[0] == BEFORE_TAG,
                   "freelist_head": f"0x{before_head:04x}",
                   "alloc_high": before_high,
                   "EXT_occupancy": ext_occupancy(before_high)},
        "after": {"tag": f"0x{raw[5]:02x}",
                  "reached": raw[5] == AFTER_TAG,
                  "freelist_head": f"0x{after_head:04x}",
                  "alloc_high": after_high,
                  "EXT_occupancy": ext_occupancy(after_high)},
    }


def classify(snapshot: dict[str, Any], current_head: int) -> str:
    before, after = snapshot["before"], snapshot["after"]
    if (before["reached"] and after["reached"]
            and int(after["freelist_head"], 16) != 0 and current_head == 0):
        return "LATER-TARGET-STATE-DESTRUCTION"
    if (before["reached"] and int(before["freelist_head"], 16) == 0
            and after["reached"] and int(after["freelist_head"], 16) == 0):
        return "MEM-INIT-DID-NOT-BUILD-FREELIST"
    if before["reached"] and not after["reached"]:
        return "MEM-INIT-IN-FLIGHT-OR-STALLED-NO-OVERCLAIM"
    if (after["reached"] and int(after["freelist_head"], 16) != 0
            and current_head != 0):
        return "INIT-BUILT-NO-FAILURE-REPRODUCED"
    return "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM"


def read_absolute(fd: int, address: int, size: int,
                  view: str) -> tuple[bytes, list[dict[str, Any]]]:
    value = bytearray()
    rows: list[dict[str, Any]] = []
    while len(value) < size:
        at = address + len(value)
        count = min(16, size - len(value))
        raw = VIEW.command(fd, f"m{at:08x}".encode())
        part = VIEW.parse_memory(raw, at, count)
        value.extend(part)
        rows.append({"command": f"m{at:08x}", "address": f"0x{at:08x}",
                     "view": view, "raw_hex": raw.hex()})
    return bytes(value), rows


def mapping_snapshot(registers: dict[str, Any]) -> dict[str, Any]:
    maph = int(registers["MAPH"], 16)
    mapl = int(registers["MAPL"], 16)
    tail = registers["tail"]
    require(maph == 0x8000 and mapl == 0x0000,
            f"mapping outside closed translation: MAPH={maph:04x} MAPL={mapl:04x}")
    # parse_registers() intentionally returns the mapping flag *values*, not
    # the preceding RECA8LHC column labels.  The first contact incorrectly
    # required those labels in this value-only tail.  Preserve the raw values
    # as evidence and make no unparsed per-flag claim.
    require(isinstance(tail, str) and tail.strip(), "mapping flag values absent")
    return {"MAPH": f"0x{maph:04x}", "MAPL": f"0x{mapl:04x}",
            "raw_flag_values": tail,
            "bank0_data_translation": "logical low16 -> physical 0x0000xxxx"}


def runner_contract(source: str) -> None:
    require('RESET_DOMAIN_BYTES=50816' in source,
            "complete reset-domain size assertion absent")
    require('c2d-v6-reset-domain' in source
            and 'partial reset-domain staging rejected' in source,
            "partial-staging rejection absent")
    require('assert raw[33840:] == b"\\0" * (50816 - 33840)' in source,
            "identity-prefix/null-suffix assertion absent")
    require('pre-run-c2j.bin' in source
            and 'assert c2j == b"\\0" * 64' in source,
            "C2J CLEAR assertion absent")
    launch = source.rfind('run_m65 -r')
    clear = source.rfind('assert c2j == b"\\0" * 64')
    require(launch >= 0 and clear >= 0 and clear < launch,
            "C2J CLEAR is not proven before RUN")


def stopped_read(fd: int) -> dict[str, Any]:
    registers = VIEW.read_registers(fd)
    mapping = mapping_snapshot(registers)
    pc = int(registers["PC"], 16)
    code, code_reads = APPT.read_cpu_block(fd, pc, min(16, 0x10000 - pc))
    owner = code_owner(pc, code)
    require(owner["unique"], "stopped PC has no unique CPU-view owner")
    values: dict[str, tuple[bytes, list[dict[str, Any]]]] = {}
    for name, address, size in (
        ("mem_init_witness", WITNESS, WITNESS_BYTES),
        ("boot_witness", BOOT_WITNESS, 1),
        ("freelist", FREELIST, 2), ("alloc_high", ALLOC_HIGH, 2),
        ("gc_frozen", GC_FROZEN, 2), ("gc_runs", GC_RUNS, 2),
        ("diagnostic_record", RECORD, RECORD_BYTES),
        ("phase_scratch", PHASE, PHASE_BYTES),
        ("phase_owner", PHASE_OWNER, 1),
    ):
        values[name] = LADDER.read_physical(fd, address, size)
    values["C2J"] = read_absolute(fd, C2J, C2J_BYTES, "physical-Bank5-C2J")
    return {"registers": registers, "mapping": mapping, "PC": registers["PC"],
            "code_owner": owner, "code_reads": code_reads, "values": values}


def result_receipt(read: dict[str, Any], quiet: dict[str, Any],
                   recovery: dict[str, Any] | None = None) -> dict[str, Any]:
    values = read["values"]
    snapshot = decode_snapshot(values["mem_init_witness"][0])
    current_head = int.from_bytes(values["freelist"][0], "little")
    current_high = int.from_bytes(values["alloc_high"][0], "little")
    status = classify(snapshot, current_head)
    phase = values["phase_scratch"][0]
    receipt = {
        "format": "lisp65-c2.3-v1.6-mem-init-before-after-device-v1",
        "recorded_on": date.today().isoformat(), "status": status,
        "authorities": {"preparation": bind(PREP), "driver": bind(DRIVER),
                        "runner": bind(RUNNER)},
        "quiet": quiet,
        "stop": {key: read[key] for key in (
            "registers", "mapping", "PC", "code_owner", "code_reads")},
        "snapshots": snapshot,
        "current": {"freelist_head": f"0x{current_head:04x}",
                    "alloc_high": current_high,
                    "EXT_occupancy": ext_occupancy(current_high),
                    "gc_frozen": int.from_bytes(values["gc_frozen"][0], "little"),
                    "gc_runs_RAM_underlay": int.from_bytes(
                        values["gc_runs"][0], "little"),
                    "boot_witness": f"0x{values['boot_witness'][0][0]:02x}",
                    "phase_owner": f"0x{values['phase_owner'][0][0]:02x}",
                    "first_error_hex": phase[
                        FIRST_ERROR_OFFSET:FIRST_ERROR_OFFSET + 2].hex(),
                    "C2J_nonzero_bytes": sum(
                        byte != 0 for byte in values["C2J"][0])},
        "raw": {name: {"hex": raw.hex(), "reads": reads}
                for name, (raw, reads) in values.items()},
        "result": {"classification": status, "CPU_left_stopped": True,
                   "measured_forms": 0, "R_A_I_G": None},
        "claim_limit": load(PREP)["claim_limit"],
    }
    if recovery is not None:
        receipt["same_contact_recovery"] = recovery
        receipt["authorities"]["capture_first_red"] = bind(FIRST_RED)
    return receipt


def facts() -> dict[str, Any]:
    owner_full, owner_plan = git_blob(REPEAT_OWNER_COMMIT, PLAN)
    require(b"Repeat contact authorized behind staging green" in owner_plan
            and b"C2J CLEAR before RUN" in owner_plan
            and b"existing reset-domain gate binds this runner" in owner_plan,
            "repeat owner authorization drift")
    build_receipt = load(BUILD.RECEIPT)
    require(build_receipt == BUILD.expected(), "before/after build receipt drift")
    deploy = load(BUILD.DEPLOY)
    require(deploy["status"] == "HOST-GREEN-NON-PROMOTABLE-MEM-INIT-WITNESS"
            and deploy["promotable"] is False, "diagnostic scope drift")
    reset = deploy["mem_init_witness"]["reset_domain"]
    require(reset["bytes"] == 50816 and reset["prefix_bytes"] == 33840
            and reset["suffix_nonzero_bytes"] == 0
            and reset["C2J_nonzero_bytes"] == 0,
            "identity-matched full reset-domain drift")
    runner = RUNNER.read_text(encoding="utf-8")
    runner_contract(runner)
    require('run_m65 -F' in runner and 'run_m65 -r' in runner
            and runner.index('run_m65 -F') < runner.index('run_m65 -r'),
            "cold reset/staging order absent")
    require('type RUN and press RETURN physically' in runner
            and 'exec python3 "$PY" capture' in runner
            and 'keyboard' not in runner.casefold(),
            "physical owner handoff drift")
    require('mem-init-witness-reset-readback.bin' in runner
            and 'cmp "$RESET"' in runner
            and 'cmp "$path"' in runner,
            "staging/readback closure drift")
    standing = load(RESET_DOMAIN_AUTHORITY)
    require(standing["class_closer"]["target"] ==
                "c2-reset-domain-completeness-check"
            and "prefix-only-restage" in standing["class_closer"]["cases"]
            and "omitted-C2J-zeroing" in standing["class_closer"]["cases"],
            "standing reset-domain class closer drift")
    rollover = load(DAY_ROLLOVER_FIRST_RED)
    require(rollover["status"] ==
                "TOOL-FIRST-RED; DATE ROLLOVER; ZERO DEVICE ACTIONS"
            and rollover["facts"]["device_actions"] == 0,
            "day-rollover First Red authority drift")
    return {
        "appointment": {"cold_reset": True, "physical_RUN": True,
                        "quiet_floor_seconds": QUIET_SECONDS,
                        "monitor_entries_after_RUN": 1,
                        "stops": 1, "measured_forms": 0,
                        "CPU_left_stopped": True},
        "read_protocol": {
            "mapping_captured_before_data": True,
            "low_RAM": "physical Bank-0 RAM after same-stop mapping capture",
            "C2J": "physical Bank-5 address 0x0005c640",
            "code": "CPU-view bytes with unique active-owner binding",
        },
        "read_set": {"mem_init_witness": ["0xb582", 10],
                     "boot_witness": ["0xb5c3", 1],
                     "freelist": ["0x003d", 2],
                     "alloc_high": ["0x0039", 2],
                     "gc_frozen": ["0x003b", 2],
                     "gc_runs": ["0xb9f0", 2],
                     "diagnostic_record": ["0xc03f", 65],
                     "phase_scratch": ["0xc0c6", 304],
                     "phase_owner": ["0x0089", 1],
                     "C2J": ["0x0005c640", 64]},
        "staging": {"reset_domain_bytes": 50816, "identity_prefix_bytes": 33840,
                    "suffix_nonzero_bytes": 0, "C2J_nonzero_bytes": 0,
                    "complete_target_readback": True,
                    "C2J_CLEAR_asserted_before_RUN": True,
                    "partial_staging_rejected": True},
        "receipt_timebase": {
            "preparation_recorded_on": PREPARATION_RECORDED_ON,
            "historical_result_recorded_on": HISTORICAL_RESULT_RECORDED_ON,
            "runtime_capture_uses_actual_date": True,
            "date_today_not_used_by_stable_receipt_checks": True,
        },
        "decision_table": BUILD.expected()["facts"]["decision_table"],
        "scope": {"product_bytes": 0, "product_links": 0,
                  "diagnostic_promotable": False, "R_A_I_G": None,
                  "contact_authorized": True, "contact_consumed": False,
                  "owner_authority": f"git:{owner_full}"},
    }


def audit(value: dict[str, Any]) -> None:
    appointment = value["appointment"]
    require(appointment == {"cold_reset": True, "physical_RUN": True,
                             "quiet_floor_seconds": QUIET_SECONDS,
                             "monitor_entries_after_RUN": 1, "stops": 1,
                             "measured_forms": 0, "CPU_left_stopped": True},
            "appointment drift")
    protocol = value["read_protocol"]
    require(protocol["mapping_captured_before_data"]
            and "physical Bank-0" in protocol["low_RAM"]
            and "physical Bank-5" in protocol["C2J"]
            and "unique active-owner" in protocol["code"],
            "read protocol drift")
    require(value["read_set"] == {
        "mem_init_witness": ["0xb582", 10], "boot_witness": ["0xb5c3", 1],
        "freelist": ["0x003d", 2], "alloc_high": ["0x0039", 2],
        "gc_frozen": ["0x003b", 2], "gc_runs": ["0xb9f0", 2],
        "diagnostic_record": ["0xc03f", 65],
        "phase_scratch": ["0xc0c6", 304], "phase_owner": ["0x0089", 1],
        "C2J": ["0x0005c640", 64]}, "read set drift")
    require(value["staging"] == {
        "reset_domain_bytes": 50816, "identity_prefix_bytes": 33840,
        "suffix_nonzero_bytes": 0, "C2J_nonzero_bytes": 0,
        "complete_target_readback": True,
        "C2J_CLEAR_asserted_before_RUN": True,
        "partial_staging_rejected": True}, "staging closure drift")
    require(value["receipt_timebase"] == {
        "preparation_recorded_on": "2026-08-05",
        "historical_result_recorded_on": "2026-08-05",
        "runtime_capture_uses_actual_date": True,
        "date_today_not_used_by_stable_receipt_checks": True},
        "stable receipt timebase drift")
    require(value["decision_table"] == BUILD.expected()["facts"]["decision_table"],
            "decision table drift")
    scope = value["scope"]
    require(scope["product_bytes"] == 0 and scope["product_links"] == 0
            and not scope["diagnostic_promotable"] and scope["R_A_I_G"] is None
            and scope["contact_authorized"] and not scope["contact_consumed"]
            and scope["owner_authority"].startswith("git:"), "scope drift")


def selftest() -> dict[str, Any]:
    base = facts()
    mutations: list[tuple[list[Any], Any]] = [
        (["appointment", "cold_reset"], False),
        (["appointment", "physical_RUN"], False),
        (["appointment", "quiet_floor_seconds"], 1.0),
        (["appointment", "monitor_entries_after_RUN"], 2),
        (["appointment", "stops"], 2),
        (["appointment", "measured_forms"], 1),
        (["appointment", "CPU_left_stopped"], False),
        (["read_protocol", "mapping_captured_before_data"], False),
        (["read_protocol", "low_RAM"], "raw CPU view"),
        (["read_protocol", "C2J"], "Bank-0 alias"),
        (["read_protocol", "code"], "physical underlay"),
        (["read_set", "mem_init_witness", 1], 9),
        (["read_set", "freelist", 0], "0x0040"),
        (["staging", "reset_domain_bytes"], 33840),
        (["staging", "complete_target_readback"], False),
        (["staging", "C2J_CLEAR_asserted_before_RUN"], False),
        (["staging", "partial_staging_rejected"], False),
        (["receipt_timebase", "date_today_not_used_by_stable_receipt_checks"], False),
        (["decision_table", "before_reached_after_absent"],
         "MEM-INIT-DID-NOT-BUILD-FREELIST"),
        (["scope", "R_A_I_G"], "R"),
        (["scope", "contact_consumed"], True),
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
        except ContactError as error:
            rejected[f"mutation-{index:02d}"] = str(error)
        else:
            raise ContactError(f"mutation survived: {path}")
    mutated_runner = RUNNER.read_text(encoding="utf-8").replace(
        "RESET_DOMAIN_BYTES=50816", "RESET_DOMAIN_BYTES=33840", 1)
    try:
        runner_contract(mutated_runner)
    except ContactError as error:
        rejected["mutation-22-partial-staging-runner"] = str(error)
    else:
        raise ContactError("partial-staging runner mutation survived")
    rows = {
        "later-destruction": ("a100000000a6000c0000", 0,
                              "LATER-TARGET-STATE-DESTRUCTION"),
        "mem-init-empty": ("a100000000a600000000", 0,
                           "MEM-INIT-DID-NOT-BUILD-FREELIST"),
        "missing-after": ("a100000000d2cccccccc", 0,
                          "MEM-INIT-IN-FLIGHT-OR-STALLED-NO-OVERCLAIM"),
        "built-live": ("a100000000a6000c0000", 0x0C00,
                       "INIT-BUILT-NO-FAILURE-REPRODUCED"),
        "unclassified": ("d1ccccccccd2cccccccc", 0,
                         "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM"),
    }
    witnessed: dict[str, str] = {}
    for name, (raw_hex, current, expected_status) in rows.items():
        actual = classify(decode_snapshot(bytes.fromhex(raw_hex)), current)
        require(actual == expected_status,
                f"decision execution witness failed: {name}: {actual}")
        witnessed[name] = actual
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "rejected": rejected, "decision_execution_witnesses": witnessed}


def expected() -> dict[str, Any]:
    value = facts()
    audit(value)
    return {
        "format": "lisp65-c2.3-v1.6-mem-init-before-after-repeat-preparation-v1",
        "recorded_on": PREPARATION_RECORDED_ON,
        "status": "HOST-GREEN; FULL RESET DOMAIN; REPEAT CONTACT READY",
        "authorities": {"build_preparation": bind(BUILD.RECEIPT),
                        "deployment": bind(BUILD.DEPLOY),
                        "driver": bind(DRIVER), "runner": bind(RUNNER),
                        "standing_reset_domain_gate": bind(RESET_DOMAIN_AUTHORITY),
                        "day_rollover_first_red": bind(DAY_ROLLOVER_FIRST_RED),
                        "owner_authorization": bind_blob(
                            f"git:{git_blob(REPEAT_OWNER_COMMIT, PLAN)[0]}:{PLAN}",
                            git_blob(REPEAT_OWNER_COMMIT, PLAN)[1])},
        "facts": value, "mutations_rejected": selftest()["rejected"],
        "decision_execution_witnesses": selftest()["decision_execution_witnesses"],
        "claim_limit": (
            "One repeat diagnostic-only physical RUN after complete reset-domain "
            "readback and a pre-RUN C2J CLEAR assertion, followed by one post-quiet stop. The target "
            "writes the before/after snapshots; all data are read through the "
            "captured mapping. No measured form, product change, link or R/A/I/G "
            "result is claimed."),
    }


def capture(device: str) -> dict[str, Any]:
    require(load(PREP) == expected(), "contact preparation receipt drift")
    require((OUT / "stage.ready").is_file(), "stage handoff absent")
    require(not DEVICE.exists() and not (OUT / "capture.consumed").exists(),
            "contact is one-shot")
    (OUT / "capture.consumed").touch()
    started = time.monotonic()
    time.sleep(QUIET_SECONDS)
    elapsed = time.monotonic() - started
    require(elapsed >= QUIET_SECONDS, "quiet floor shortened")

    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c2v16meminitba\r")
        VIEW.command(fd, b"t1", 0.05)
        read = stopped_read(fd)
        # Deliberately no t0: final CPU state remains stopped.
    finally:
        os.close(fd)
    receipt = result_receipt(read, {"required_seconds": QUIET_SECONDS,
        "observed_seconds": elapsed, "early_monitor_accesses": 0})
    receipt["device"] = device
    write_json(DEVICE, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return receipt


def recover(device: str) -> dict[str, Any]:
    require((FIRST_OUT / "capture.consumed").is_file(), "consumed contact absent")
    require(not FIRST_DEVICE.exists(), "device receipt already exists")
    full, original_driver = git_blob(
        ORIGINAL_CONTACT_COMMIT,
        "tools/host-lisp/c2_v16_mem_init_before_after_contact.py")
    _, original_prep = git_blob(
        ORIGINAL_CONTACT_COMMIT,
        "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
        "c2.3-v1.6-defstruct-mem-init-before-after-contact-preparation-receipt.json")
    require(b'"lhc" in tail.casefold()' not in original_driver,
            "unexpected local helper ownership")
    _, inherited = git_blob(
        ORIGINAL_CONTACT_COMMIT, "tools/host-lisp/c2_v16_full_ladder_contact.py")
    require(b'"lhc" in tail.casefold()' in inherited,
            "first-red parser predicate absent from consumed authority")
    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        registers = VIEW.read_registers(fd)
        first_red = {
            "format": "lisp65-c2.3-v1.6-mem-init-before-after-capture-first-red-v1",
            "recorded_on": date.today().isoformat(),
            "status": "TOOL-FIRST-RED; CPU ALREADY STOPPED; NO PRODUCT CLAIM",
            "authorities": {
                "consumed_driver": bind_blob(
                    f"git:{full}:tools/host-lisp/"
                    "c2_v16_mem_init_before_after_contact.py", original_driver),
                "consumed_preparation": bind_blob(
                    f"git:{full}:tests/bytecode/dialect-v2/"
                    "evidence/architecture-blocks/c2.3-v1.6-defstruct-mem-init-"
                    "before-after-contact-preparation-receipt.json", original_prep),
            },
            "cause": ("The inherited mapping helper required the RECA8LHC column "
                      "labels inside parse_registers()' value-only tail. The live "
                      "row carried valid MAPH/MAPL and raw flag values, so the "
                      "contact stopped once and then rejected its own parser."),
            "stopped_registers_after_first_red": registers,
            "contact": {"additional_RUN": 0, "additional_monitor_entries": 0,
                        "additional_stops": 0, "CPU_already_stopped": True},
            "claim_limit": "Tool parser First Red only; no device-state classification.",
        }
        write_json(FIRST_RED, first_red)
        read = stopped_read(fd)
        # No monitor_sync, t1 or t0 occurs in recovery: this completes the
        # read set of the already stopped, already consumed contact.
    finally:
        os.close(fd)
    receipt = result_receipt(read, {
        "required_seconds": QUIET_SECONDS,
        "original_source_order_enforced_before_the_consumed_stop": True,
        "exact_elapsed_lost_to_tool_first_red": True,
        "early_monitor_accesses": 0,
    }, {"same_stopped_state": True, "additional_RUN": 0,
        "additional_monitor_entries": 0, "additional_stops": 0})
    receipt["device"] = device
    write_json(FIRST_DEVICE, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return receipt


def result_facts() -> dict[str, Any]:
    device = load(FIRST_DEVICE)
    first_red = load(FIRST_RED)
    require(device["status"] == "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM"
            and first_red["status"] ==
                "TOOL-FIRST-RED; CPU ALREADY STOPPED; NO PRODUCT CLAIM",
            "consumed result status drift")
    require(device["snapshots"]["raw_hex"] == "d1ccccccccd2cccccccc"
            and not device["snapshots"]["before"]["reached"]
            and not device["snapshots"]["after"]["reached"],
            "untouched snapshot evidence drift")
    require(device["current"]["boot_witness"] == "0x44"
            and device["current"]["C2J_nonzero_bytes"] == 64
            and device["raw"]["C2J"]["hex"] == "10" * 64,
            "boot/C2J stopped evidence drift")
    truth = BUILD.ElfTruth.read(BUILD.DIAG_ELF, llvm_readobj=BUILD.READOBJ)
    symbol = truth.symbol("lisp65_v16_defstruct_first_error_capture")
    require(symbol.value == 0xB434 and device["stop"]["PC"] == "0xb434",
            "stopped first-error entry identity drift")

    full, runner = git_blob(
        ORIGINAL_CONTACT_COMMIT,
        "scripts/c2-v16-defstruct-mem-init-before-after-hw.sh")
    _, deployment_raw = git_blob(
        ORIGINAL_CONTACT_COMMIT,
        "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
        "c2.3-v1.6-defstruct-mem-init-before-after-preparation-receipt.json")
    build_prep = json.loads(deployment_raw)
    require(build_prep["facts"]["scope"]["hardware_contacts"] == 0,
            "consumed preparation scope drift")
    source = runner.decode("utf-8")
    require("jq -c '.diagnostic.preloads[]'" in source
            and "50816" not in source and "0x0005c640" not in source,
            "consumed staging omission no longer reproduced")
    deployment = load(BUILD.BASE_DEPLOY)
    c2d = [row for row in deployment["diagnostic"]["preloads"]
           if row["role"] == "c2d-v6-code-plane"]
    require(len(c2d) == 1 and c2d[0]["bytes"] == 33840,
            "consumed prefix-only deployment drift")
    reset = load(RESET_DOMAIN_AUTHORITY)
    require(reset["mechanism"]["reset_domain_bytes"] == 50816
            and reset["mechanism"]["c2j_zero_bytes"] == 64
            and reset["class_closer"]["mutations_rejected"] == 6
            and "prefix-only-restage" in reset["class_closer"]["cases"],
            "standing full reset-domain authority drift")
    return {
        "contact": {"physical_RUNs": 1, "stops": 1,
                    "same_stop_recovery_reads": True,
                    "additional_RUNs_or_stops": 0},
        "tool_first_red": {"cause": "value-only mapping tail rejected for missing labels",
                           "mapping_was": {"MAPH": "0x8000", "MAPL": "0x0000"},
                           "product_claim": None},
        "staging_first_red": {
            "boot_entry_reached": True,
            "before_tag_reached": False, "after_tag_reached": False,
            "C2J": "64 copies of 0x10", "staged_C2D_bytes": 33840,
            "required_reset_domain_bytes": 50816,
            "runner_wrote_or_asserted_C2J_CLEAR": False,
            "classification": "PREFIX-ONLY-STAGING-LEFT-NONCLEAR-C2J; MEM_INIT QUESTION UNREACHED",
        },
        "stopped_state": {"PC": "0xb434",
                          "symbol": "lisp65_v16_defstruct_first_error_capture",
                          "boot_witness": "0x44", "first_error_payload": "0000",
                          "claim": "entry snapshot only; no failing guard edge inferred"},
        "disposition": {"mem_init_binary_answer": None, "R_A_I_G": None,
                        "product_fault": None, "recontact_authorized": False,
                        "required_before_recontact": (
                            "stage and independently read back the complete 50,816-byte "
                            "identity-matched reset domain; assert C2J CLEAR before RUN")},
        "consumed_authority": f"git:{full}",
    }


def audit_result(value: dict[str, Any]) -> None:
    require(value["contact"] == {"physical_RUNs": 1, "stops": 1,
                                  "same_stop_recovery_reads": True,
                                  "additional_RUNs_or_stops": 0},
            "contact accounting drift")
    require(value["tool_first_red"]["mapping_was"] ==
            {"MAPH": "0x8000", "MAPL": "0x0000"}
            and value["tool_first_red"]["product_claim"] is None,
            "tool first-red claim drift")
    stage = value["staging_first_red"]
    require(stage == {"boot_entry_reached": True,
                       "before_tag_reached": False, "after_tag_reached": False,
                       "C2J": "64 copies of 0x10", "staged_C2D_bytes": 33840,
                       "required_reset_domain_bytes": 50816,
                       "runner_wrote_or_asserted_C2J_CLEAR": False,
                       "classification": (
                           "PREFIX-ONLY-STAGING-LEFT-NONCLEAR-C2J; "
                           "MEM_INIT QUESTION UNREACHED")},
            "staging first-red drift")
    require(value["stopped_state"]["PC"] == "0xb434"
            and value["stopped_state"]["first_error_payload"] == "0000"
            and "no failing guard edge" in value["stopped_state"]["claim"],
            "stopped-state claim drift")
    disposition = value["disposition"]
    require(disposition["mem_init_binary_answer"] is None
            and disposition["R_A_I_G"] is None
            and disposition["product_fault"] is None
            and disposition["recontact_authorized"] is False
            and "50,816-byte" in disposition["required_before_recontact"]
            and "C2J CLEAR" in disposition["required_before_recontact"],
            "result disposition drift")


def result_selftest() -> dict[str, Any]:
    base = result_facts()
    mutations: list[tuple[list[Any], Any]] = [
        (["contact", "additional_RUNs_or_stops"], 1),
        (["tool_first_red", "product_claim"], "mapping fault"),
        (["staging_first_red", "boot_entry_reached"], False),
        (["staging_first_red", "before_tag_reached"], True),
        (["staging_first_red", "C2J"], "CLEAR"),
        (["staging_first_red", "staged_C2D_bytes"], 50816),
        (["stopped_state", "first_error_payload"], "0300"),
        (["disposition", "mem_init_binary_answer"], "later destruction"),
        (["disposition", "R_A_I_G"], "R"),
        (["disposition", "product_fault"], "mem_init"),
        (["disposition", "recontact_authorized"], True),
    ]
    rejected: dict[str, str] = {}
    for index, (path, replacement) in enumerate(mutations, 1):
        trial = deepcopy(base)
        cursor: Any = trial
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = replacement
        try:
            audit_result(trial)
        except ContactError as error:
            rejected[f"mutation-{index:02d}"] = str(error)
        else:
            raise ContactError(f"result mutation survived: {path}")
    return {"status": "RESULT SELFTEST PASS", "mutations": len(rejected),
            "rejected": rejected}


def expected_result() -> dict[str, Any]:
    value = result_facts()
    audit_result(value)
    driver_path = DRIVER.relative_to(ROOT).as_posix()
    driver_commit, driver_raw = git_blob(RESULT_CLOSE_COMMIT, driver_path)
    return {
        "format": "lisp65-c2.3-v1.6-mem-init-before-after-staging-first-red-v1",
        "recorded_on": HISTORICAL_RESULT_RECORDED_ON,
        "status": "SETUP-FIRST-RED; MEM_INIT BINARY QUESTION UNMEASURED",
        "authorities": {"device": bind(FIRST_DEVICE),
                        "capture_first_red": bind(FIRST_RED),
                        "full_reset_domain": bind(RESET_DOMAIN_AUTHORITY),
                        "driver": bind_blob(
                            f"git:{driver_commit}:{driver_path}", driver_raw)},
        "facts": value, "mutations_rejected": result_selftest()["rejected"],
        "claim_limit": (
            "The consumed contact proves one parser First Red and a prefix-only "
            "staging precondition failure with non-CLEAR C2J. It does not answer "
            "the mem_init before/after question, name a product fault, classify "
            "R/A/I/G or authorize another contact."),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=(
        "prepare", "check", "selftest", "capture", "recover", "close",
        "result-selftest", "result-check"))
    parser.add_argument("--device", default=os.environ.get("DEVICE", "/dev/ttyUSB1"))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.action == "prepare":
        value = expected()
        write_json(PREP, value)
    elif args.action == "check":
        value = expected()
        require(load(PREP) == value, "contact preparation receipt drift")
        value = {"status": "PASS", "mutations": len(value["mutations_rejected"]),
                 "device_receipt_present": DEVICE.exists()}
    elif args.action == "selftest":
        value = selftest()
    elif args.action == "capture":
        value = capture(args.device)
    elif args.action == "recover":
        value = recover(args.device)
    elif args.action == "close":
        value = expected_result()
        write_json(RESULT, value)
    elif args.action == "result-selftest":
        value = result_selftest()
    else:
        value = expected_result()
        require(load(RESULT) == value, "staging first-red result receipt drift")
        value = {"status": "RESULT PASS",
                 "mutations": len(value["mutations_rejected"])}
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContactError, BUILD.WitnessError, OSError, ValueError, TypeError,
            KeyError, json.JSONDecodeError) as error:
        print(f"c2-v16-mem-init-before-after: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
