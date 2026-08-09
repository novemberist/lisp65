#!/usr/bin/env python3
"""Capture the one owner-authorized pre-installer micro-ladder contact."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402
import c2_v16_corrected_view_contact as VIEW  # noqa: E402
import c2_v16_full_ladder_contact as PHYSICAL  # noqa: E402
import c2_v16_romc_repaired_d2_appointment as CPUVIEW  # noqa: E402
import c2_v16_preinstaller_micro_ladder as BUILD  # noqa: E402


OUT = ROOT / (
    "build/c2.3/v1.6-defstruct-closing-session/"
    "d2-preinstaller-micro-ladder-contact")
STAGE = OUT / "stage.json"
DEVICE = OUT / "device-receipt.json"
PREP = BUILD.RECEIPT
DRIVER = Path(__file__).resolve()
RUNNER = ROOT / "scripts/c2-v16-defstruct-preinstaller-micro-ladder-hw.sh"
QUIET_SECONDS = 27.653
STATE = 0xB58C
STATE_BYTES = 6
BOOT_WITNESS = 0xB5C3
STATUS = 0x74
HEALTH = 0x8C
RECORD = 0xC03F
RECORD_BYTES = 65
PHASE = 0xC0C6
PHASE_BYTES = 304
PHASE_OWNER = 0x89
C2J = 0x05C640
C2J_BYTES = 64


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
        label = path.resolve().as_posix()
    return {"path": label, "bytes": len(raw), "sha256": digest(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_build_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def prg_slice(raw: bytes, logical: int, size: int) -> bytes | None:
    if len(raw) < 2:
        return None
    at = 2 + logical - int.from_bytes(raw[:2], "little")
    if at < 2 or at + size > len(raw):
        return None
    return raw[at:at + size]


def code_owner(logical: int, observed: bytes) -> dict[str, Any]:
    deployment = load(BUILD.DEPLOY)
    candidates: dict[str, bytes] = {}
    prg = (ROOT / deployment["diagnostic"]["prg"]["path"]).read_bytes()
    resident = prg_slice(prg, logical, len(observed))
    if resident is not None:
        candidates["micro-ladder-diagnostic-PRG"] = resident
    if 0xE000 <= logical and logical + len(observed) <= 0x10000:
        window = (ROOT / deployment["diagnostic"]["window"]["path"]).read_bytes()
        candidates["diagnostic-E000-window"] = window[
            logical - 0xE000:logical - 0xE000 + len(observed)]
        rom = VIEW.rom_path().read_bytes()[0x10000:]
        candidates["configured-MEGA65-ROM"] = rom[logical:logical + len(observed)]
    matches = [name for name, raw in candidates.items() if raw == observed]
    return {"logical_address": f"0x{logical:04x}", "observed": observed.hex(),
            "candidate_bytes": {name: raw.hex()
                                for name, raw in sorted(candidates.items())},
            "matches": matches,
            "selected_owner": matches[0] if len(matches) == 1 else "unresolved",
            "unique": len(matches) == 1,
            "symbol_interpretation_allowed": len(matches) == 1}


def read_absolute(fd: int, address: int, size: int,
                  label: str) -> tuple[bytes, list[dict[str, Any]]]:
    result = bytearray(); rows: list[dict[str, Any]] = []
    while len(result) < size:
        at = address + len(result); count = min(16, size - len(result))
        raw = VIEW.command(fd, f"m{at:08x}".encode())
        part = VIEW.parse_memory(raw, at, count); result.extend(part)
        rows.append({"command": f"m{at:08x}", "address": f"0x{at:08x}",
                     "view": label, "raw_hex": raw.hex()})
    return bytes(result), rows


def classify(state: bytes, status: bytes) -> str:
    require(len(state) == 6 and len(status) == 2, "classification input drift")
    if state[0] == 0xD0:
        return "LOCAL-CRT-INIT-BOUNDARY"
    if state[1] == 0xD1:
        return "CHROUT-NONRETURN-OR-MAP-NOT-RESTORED"
    if state[2] == 0xD2:
        return "MAIN-PREFIX-BOUNDARY"
    if state[3] == 0xD3:
        return "OWNERSHIP-IN-FLIGHT-BOUNDARY"
    if state[3] != 0xE3:
        return "LADDER-TAG-FIRST-RED"
    if state[4] == 0:
        return "OWNERSHIP-FAIL-CLOSED-EXIT"
    if state[5] == 0xD5:
        return "POST-OWNERSHIP-PRE-INSTALLER"
    if state[5] != 0xE4:
        return "LADDER-INSTALLER-TAG-FIRST-RED"
    if status[1] == 0:
        return "INSTALLER-PROLOGUE-BEFORE-ARM"
    return "HAND-OFF-TO-EXISTING-STATUS-TABLE"


def runner_contract(source: str) -> None:
    markers = ["RESET_DOMAIN_BYTES=50816", "c2d-v6-reset-domain",
               "complete reset-domain readback", "pre-run-c2j.bin",
               "C2J CLEAR before RUN", "type RUN and press RETURN physically"]
    require(all(marker in source for marker in markers), "runner closure absent")
    require(source.index("run_m65 -F") < source.index("run_m65 -r")
            < source.index("type RUN and press RETURN physically"),
            "cold-reset/owner handoff order drift")


def preparation() -> dict[str, Any]:
    require(load(PREP) == BUILD.expected(), "build preparation drift")
    runner_contract(RUNNER.read_text(encoding="utf-8"))
    return {"format": "lisp65-c2.3-v1.6-preinstaller-micro-ladder-contact-v1",
            "status": "CONTACT READY", "quiet_floor_seconds": QUIET_SECONDS,
            "read_order": ["tuple", "CPU-view code identity",
                           "physically translated data"],
            "read_set": {"state": ["0xb58c", 6], "boot_witness": ["0xb5c3", 1],
                         "status": ["0x0074", 2], "health": ["0x008c", 4],
                         "record": ["0xc03f", 65], "phase": ["0xc0c6", 304],
                         "phase_owner": ["0x0089", 1], "C2J": ["0x0005c640", 64]},
            "contact": {"cold_reset": True, "physical_RUN": True,
                        "stops": 1, "CPU_left_stopped": True,
                        "complete_reset_domain": True,
                        "C2J_CLEAR_before_RUN": True},
            "authorities": {"build_preparation": bind(PREP),
                            "driver": bind(DRIVER), "runner": bind(RUNNER)},
            "claim_limit": "One owner-authorized non-promotable diagnostic contact. No product bytes, mem_init answer, R/A/I/G row, fix, Link or release."}


def audit(value: dict[str, Any]) -> None:
    require(value["status"] == "CONTACT READY"
            and value["quiet_floor_seconds"] == 27.653
            and value["read_order"] == ["tuple", "CPU-view code identity",
                                         "physically translated data"],
            "contact protocol drift")
    require(value["contact"] == {"cold_reset": True, "physical_RUN": True,
                                  "stops": 1, "CPU_left_stopped": True,
                                  "complete_reset_domain": True,
                                  "C2J_CLEAR_before_RUN": True},
            "contact accounting drift")
    require(value["read_set"]["state"] == ["0xb58c", 6]
            and value["read_set"]["C2J"] == ["0x0005c640", 64]
            and len(value["read_set"]) == 8, "read-set drift")


def selftest() -> dict[str, Any]:
    prep = preparation(); audit(prep)
    table = {
        "d0d1d2d3d4d5": "LOCAL-CRT-INIT-BOUNDARY",
        "0ed1d2d3d4d5": "CHROUT-NONRETURN-OR-MAP-NOT-RESTORED",
        "0ee1d2d3d4d5": "MAIN-PREFIX-BOUNDARY",
        "0ee1e2d3d4d5": "OWNERSHIP-IN-FLIGHT-BOUNDARY",
        "0ee1e2e300d5": "OWNERSHIP-FAIL-CLOSED-EXIT",
        "0ee1e2e301d5": "POST-OWNERSHIP-PRE-INSTALLER",
        "0ee1e2e301e4": "INSTALLER-PROLOGUE-BEFORE-ARM",
    }
    for raw, expected in table.items():
        require(classify(bytes.fromhex(raw), b"\x00\x00") == expected,
                f"decision-table drift: {raw}")
    require(classify(bytes.fromhex("0ee1e2e301e4"), b"\x00\x01") ==
            "HAND-OFF-TO-EXISTING-STATUS-TABLE", "handoff row drift")
    mutations = [
        (["quiet_floor_seconds"], 0), (["read_order", 0], "data"),
        (["contact", "cold_reset"], False), (["contact", "physical_RUN"], False),
        (["contact", "stops"], 2), (["contact", "CPU_left_stopped"], False),
        (["contact", "complete_reset_domain"], False),
        (["contact", "C2J_CLEAR_before_RUN"], False),
        (["read_set", "state", 1], 5), (["read_set", "C2J", 1], 63),
    ]
    rejected: dict[str, str] = {}
    for index, (path, replacement) in enumerate(mutations, 1):
        trial = deepcopy(prep); cursor: Any = trial
        for key in path[:-1]: cursor = cursor[key]
        cursor[path[-1]] = replacement
        try: audit(trial)
        except ContactError as error: rejected[f"mutation-{index:02d}"] = str(error)
        else: raise ContactError(f"contact mutation survived: {path}")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "decision_rows": 8, "rejected": rejected}


def capture(device: str) -> dict[str, Any]:
    prep = preparation(); audit(prep)
    require(STAGE.is_file() and load(STAGE)["status"] == "STAGE READY",
            "verified stage absent")
    require(not DEVICE.exists(), "micro-ladder contact is one-shot")
    quiet_started = time.monotonic(); time.sleep(QUIET_SECONDS)
    quiet_elapsed = time.monotonic() - quiet_started
    require(quiet_elapsed >= QUIET_SECONDS, "quiet floor violated")
    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c2v16preinstallerladder\r")
        VIEW.command(fd, b"t1", 0.05)
        # Tuple first.  No data read precedes this complete register row.
        registers = VIEW.read_registers(fd)
        pc = int(registers["PC"], 16)
        code, code_reads = CPUVIEW.read_cpu_block(fd, pc,
                                                  min(16, 0x10000 - pc))
        owner = code_owner(pc, code)
        values: dict[str, tuple[bytes, list[dict[str, Any]]]] = {}
        for name, address, size in (
            ("state", STATE, STATE_BYTES), ("boot_witness", BOOT_WITNESS, 1),
            ("status", STATUS, 2), ("health", HEALTH, 4),
            ("record", RECORD, RECORD_BYTES), ("phase", PHASE, PHASE_BYTES),
            ("phase_owner", PHASE_OWNER, 1),
        ):
            values[name] = PHYSICAL.read_physical(fd, address, size)
        values["C2J"] = read_absolute(fd, C2J, C2J_BYTES,
                                       "physical-Bank5-C2J")
    finally:
        os.close(fd)
    result = classify(values["state"][0], values["status"][0])
    phase = values["phase"][0]
    receipt = {
        "format": "lisp65-c2.3-v1.6-preinstaller-micro-ladder-device-v1",
        "recorded_on": date.today().isoformat(), "status": result,
        "authorities": {"preparation": bind(PREP), "driver": bind(DRIVER),
                        "runner": bind(RUNNER), "stage": bind(STAGE)},
        "quiet": {"floor_seconds": QUIET_SECONDS,
                  "observed_seconds": quiet_elapsed},
        "tuple_first": {"confirmed_before_data_reads": True,
                        "registers": registers},
        "code_identity": {"CPU_view": True, "owner": owner,
                          "reads": code_reads},
        "ladder": {"raw_hex": values["state"][0].hex(),
                   "classification": result,
                   "decision_table": BUILD.expected()["facts"]["decision_table"]},
        "state": {"boot_witness": f"0x{values['boot_witness'][0][0]:02x}",
                  "status_hex": values["status"][0].hex(),
                  "health_hex": values["health"][0].hex(),
                  "phase_owner": f"0x{values['phase_owner'][0][0]:02x}",
                  "first_error_hex": phase[302:304].hex(),
                  "C2J_nonzero_bytes": sum(byte != 0
                                            for byte in values["C2J"][0])},
        "raw": {name: {"hex": raw.hex(), "reads": reads}
                for name, (raw, reads) in values.items()},
        "result": {"classification": result, "physical_RUNs": 1, "stops": 1,
                   "CPU_left_stopped": True, "measured_forms": 0,
                   "mem_init_answer": None, "R_A_I_G": None,
                   "product_fault": None},
        "claim_limit": prep["claim_limit"],
    }
    write_build_json(DEVICE, receipt)
    print(json.dumps(receipt, sort_keys=True)); return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "selftest", "capture"))
    parser.add_argument("--device", default=SERIAL.DEVICE)
    args = parser.parse_args()
    if args.action == "capture": capture(args.device); return 0
    value = selftest() if args.action == "selftest" else preparation()
    if args.action == "check": audit(value); value = {
        "status": "PASS", "decision_rows": 8,
        "mutations": len(selftest()["rejected"]),
        "device_result_present": DEVICE.exists()}
    print(json.dumps(value, indent=2, sort_keys=True)); return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except (ContactError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"PREINSTALLER MICRO-LADDER CONTACT FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
