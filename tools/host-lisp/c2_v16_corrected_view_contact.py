#!/usr/bin/env python3
"""Prepare and capture the corrected-view v1.6 launch contact.

Every stopped-state value is read through the MEGA65 monitor's CPU-view
address space (``$0777xxxx``).  Each sample retains MAPH/MAPL and binds the
instruction owner by comparing CPU-visible bytes with independently bound
product and ROM images before any address is interpreted.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402


OWNER_COMMIT = "1adb9153"
PLAN = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
DEPLOY = ROOT / "build/c2.3/v1.6-defstruct-phase-c/deployment.json"
BASE_PRG = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-link82.prg"
WINDOW = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-window.bin"
OLD_PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-durable-progress-preparation-receipt.json")
ATTRIBUTION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-identity-view-desk-attribution-receipt.json")
ROM_CONTRACT = ROOT / "config/r3-g3-g6-contract.json"
CORE = ROOT / "build/upstream-verification/mega65-core"
CORE_CPU = CORE / "src/vhdl/gs4510.vhdl"
CORE_MONITOR = CORE / "src/monitor/monitor.a65"
COLD_BOOT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link47-zero-literal-entry-hardware-first-red.json")
OUT = ROOT / (
    "build/c2.3/v1.6-defstruct-closing-session/"
    "d2-corrected-view-quiet-appointment")
PATCHED_PRG = OUT / "diagnostic-link82-corrected-view-b5c3.prg"
SENTINEL = OUT / "durable-witness-reset.bin"
UNDERLAY_READBACK = OUT / "witness-underlay-before-run.bin"
PRELAUNCH = OUT / "prelaunch-cpu-view.json"
PREP_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-corrected-view-quiet-preparation-receipt.json")
DEVICE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-corrected-view-quiet-device-receipt.json")
DRIVER = Path(__file__).resolve()
RUNNER = ROOT / "scripts/c2-v16-defstruct-corrected-view-hw.sh"

CORE_COMMIT = "a9158930665763c592d004c895d52eff4a9eefc3"
ROM_SHA = "af3c447f791a2fdc48cb21e1bd3fab015e32641228d9d30d21259b9e878c6fa0"
CPU_VIEW_BASE = 0x07770000
ENTRY_ROUTINE = 0xC03F
BASE_ROUTINE = bytes.fromhex("a2448e30d08e7ac060")
PATCHED_ROUTINE = bytes.fromhex("a2448e30d08ec3b560")
WITNESS = 0xB5C3
RESET = 0xD7
STAMP = 0x44
FREELIST = 0x003D
GC_RUNS = 0xB9F0
GC_CONTEXT = 0x0016
GC_CONTEXT_BYTES = 10
E000_PROBE = 0xE1B8
E000_PROBE_BYTES = 16
CODE_PROBE_BYTES = 16
SAMPLES = 3
SPACING_SECONDS = 5.0
FIRST_OBSERVATION_QUIET_SECONDS = 27.653
RECONTACT_AUTHORIZED = True


class CorrectedViewError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CorrectedViewError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


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


def write_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def run(args: list[str], *, cwd: Path = ROOT) -> bytes:
    process = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    require(process.returncode == 0,
            f"command failed ({' '.join(args)}): "
            f"{process.stderr.decode(errors='replace')}")
    return process.stdout


def git_blob(commit: str, path: str) -> tuple[str, bytes]:
    resolved = run(["git", "rev-parse", f"{commit}^{{commit}}"])
    full = resolved.decode().strip()
    return full, run(["git", "show", f"{full}:{path}"])


def prg_offset(raw: bytes, address: int) -> int:
    require(len(raw) >= 2, "PRG has no load address")
    offset = 2 + address - int.from_bytes(raw[:2], "little")
    require(2 <= offset < len(raw), f"PRG address absent: 0x{address:04x}")
    return offset


def prg_slice(raw: bytes, address: int, size: int) -> bytes | None:
    if len(raw) < 2:
        return None
    offset = 2 + address - int.from_bytes(raw[:2], "little")
    if offset < 2 or offset + size > len(raw):
        return None
    return raw[offset:offset + size]


def derived_prg() -> bytes:
    base = BASE_PRG.read_bytes()
    before = prg_slice(base, ENTRY_ROUTINE, len(BASE_ROUTINE))
    require(before == BASE_ROUTINE, "base diagnostic entry routine drift")
    value = bytearray(base)
    at = prg_offset(base, ENTRY_ROUTINE)
    value[at:at + len(PATCHED_ROUTINE)] = PATCHED_ROUTINE
    changes = [(index, old, new) for index, (old, new) in
               enumerate(zip(base, value)) if old != new]
    require([(int.from_bytes(base[:2], "little") + index - 2, old, new)
             for index, old, new in changes] ==
            [(0xC045, 0x7A, 0xC3), (0xC046, 0xC0, 0xB5)],
            "corrected-view identity diff drift")
    return bytes(value)


def materialize() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PATCHED_PRG.write_bytes(derived_prg())
    SENTINEL.write_bytes(bytes([RESET]))


def rom_path() -> Path:
    contract = load(ROM_CONTRACT)
    candidates: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str) and value.endswith("MEGA65.ROM"):
            candidates.append(value)

    walk(contract)
    require(len(set(candidates)) == 1, "exactly one MEGA65.ROM authority required")
    return Path(candidates[0]).expanduser()


def cpu_view_address(logical: int) -> int:
    require(0 <= logical <= 0xFFFF, f"logical CPU address out of range: {logical}")
    value = CPU_VIEW_BASE | logical
    require((value >> 16) == 0x0777, "CPU-view magic was not applied")
    return value


def source_candidates(logical: int, size: int) -> dict[str, bytes]:
    require(0 <= logical <= 0xFFFF and 0 < size <= 16,
            "code-owner source request out of range")
    result: dict[str, bytes] = {}
    prg = PATCHED_PRG.read_bytes()
    in_prg = prg_slice(prg, logical, size)
    if in_prg is not None:
        result["diagnostic-PRG"] = in_prg
    window = WINDOW.read_bytes()
    if 0xE000 <= logical and logical + size <= 0x10000:
        result["diagnostic-E000-window"] = window[
            logical - 0xE000:logical - 0xE000 + size]
    rom = rom_path().read_bytes()[0x10000:]
    if logical + size <= len(rom):
        result["MEGA65-ROM"] = rom[logical:logical + size]
    return result


def code_owner(logical: int, observed: bytes) -> dict[str, Any]:
    candidates = source_candidates(logical, len(observed))
    matches = [name for name, value in candidates.items() if value == observed]
    owner = matches[0] if len(matches) == 1 else "unresolved"
    return {
        "logical_address": f"0x{logical:04x}",
        "observed": observed.hex(),
        "candidate_bytes": {name: value.hex()
                            for name, value in sorted(candidates.items())},
        "matches": matches,
        "selected_owner": owner,
        "unique": len(matches) == 1,
        "symbol_interpretation_allowed": len(matches) == 1,
    }


REGISTER_RE = re.compile(
    rb"(?:^|\n)([0-9A-Fa-f]{4})"
    rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
    rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
    rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{4})"
    rb"\s+([0-9A-Fa-f]{4})\s+([0-9A-Fa-f]{4})([^\r\n]*)")


def parse_registers(raw: bytes) -> dict[str, Any]:
    match = REGISTER_RE.search(raw)
    require(match is not None, f"full monitor register row absent: {raw!r}")
    names = ("PC", "A", "X", "Y", "Z", "B", "SP", "MAPH", "MAPL")
    widths = (4, 2, 2, 2, 2, 2, 4, 4, 4)
    result = {name: f"0x{int(match.group(index), 16):0{width}x}"
              for index, (name, width) in enumerate(zip(names, widths), 1)}
    row = match.group(0).lstrip(b"\n")
    result["tail"] = match.group(10).decode("ascii", errors="replace").strip()
    result["row"] = row.decode("ascii", errors="replace")
    result["raw_hex"] = raw.hex()
    return result


def command(fd: int, value: bytes, wait: float = 0.04) -> bytes:
    SERIAL.slow_write(fd, value + b"\r")
    time.sleep(wait)
    return SERIAL.serial_read(fd, 0.4)


def read_registers(fd: int) -> dict[str, Any]:
    return parse_registers(command(fd, b"r", 0.05))


def parse_memory(raw: bytes, address: int, size: int) -> bytes:
    match = re.search(fr":{address:08X}:([0-9A-Fa-f]{{32}})".encode(), raw)
    require(match is not None,
            f"monitor CPU-view row absent at 0x{address:08x}: {raw!r}")
    return bytes.fromhex(match.group(1).decode())[:size]


def read_cpu(fd: int, logical: int, size: int) -> tuple[bytes, dict[str, Any]]:
    address = cpu_view_address(logical)
    raw = command(fd, f"m{address:08x}".encode())
    value = parse_memory(raw, address, size)
    return value, {"command": f"m{address:08x}", "logical": f"0x{logical:04x}",
                   "view": "CPU-resolved-0x0777xxxx", "raw_hex": raw.hex()}


def register_fixture() -> bytes:
    return (b"r\r\nPC   A  X  Y  Z  B  SP   MAPH MAPL LAST-OP In    P  "
            b"P-FLAGS   RGP uS IO ws h RECA8LHC\r\n"
            b"E1C2 C0 07 00 00 00 010B 8000 0000 A606    00      A5 "
            b"N.E..I.C ...P 15 -  00 - ..c..lhc\r\n.")


def memory_fixture(address: int, data: bytes) -> bytes:
    return f"m{address:08x}\r\n:{address:08X}:".encode() + data.ljust(
        16, b"\x00").hex().upper().encode() + b"\r\n."


def capture_schedule(source: str) -> dict[str, Any]:
    boundary = "\ndef capture(device: str) -> dict[str, Any]:\n"
    require(boundary in source and "\ndef prepare()" in source,
            "capture schedule boundary absent")
    body = source.split(boundary, 1)[1].split(
        "\ndef prepare()", 1)[0]
    markers = [
        "require(RECONTACT_AUTHORIZED,",
        "quiet_started = time.monotonic()",
        "time.sleep(FIRST_OBSERVATION_QUIET_SECONDS)",
        "fd = os.open(device,",
        "SERIAL.monitor_sync(fd,",
        'command(fd, b"t1", 0.05)',
    ]
    require(all(body.count(marker) == 1 for marker in markers),
            "capture schedule marker multiplicity drift")
    positions = [body.index(marker) for marker in markers]
    require(positions == sorted(positions),
            "monitor entry precedes the bound quiet interval")
    return {
        "ordered_steps": [
            "owner-authorization", "quiet-start", "27.653-second-sleep",
            "serial-open", "monitor-sync", "t1"],
        "first_device_access_after_sleep": True,
    }


def exact_facts() -> dict[str, Any]:
    owner_commit, plan_blob = git_blob(OWNER_COMMIT, PLAN)
    text = plan_blob.decode("utf-8")
    require("Recontact authorized — 2026-08-05" in text
            and "The owner\nauthorizes the repeat contact" in text
            and "recontact_authorized` flips by this decision" in text,
            "corrected-view choreography authority absent")
    attribution = load(ATTRIBUTION)
    require(attribution["status"] ==
            "ATTRIBUTED WRONG E000 OWNER PLUS PHYSICAL-RAM VIEW"
            and len(attribution["mutations_rejected"]) == 14,
            "identity/view attribution authority drift")
    old = load(OLD_PREP)
    require(old["facts"]["identity"]["durable_PRG"]["sha256"] ==
            digest(derived_prg())
            and old["facts"]["witness"] == {
                "address": "0xb5c3", "bytes": 1, "entry_stamp": "0x44",
                "owner_collision_mutations": 30,
                "prelaunch_CPU_readback_required": True,
                "prelaunch_reset": "0xd7",
                "reset_file": old["facts"]["witness"]["reset_file"],
            }, "durable identity authority drift")
    deployment = load(DEPLOY)
    require(deployment["promotable"] is False and
            deployment["diagnostic"]["prg"]["sha256"] ==
            digest(BASE_PRG.read_bytes()), "deployment identity drift")
    rom = rom_path()
    require(digest(rom.read_bytes()) == ROM_SHA, "MEGA65 ROM authority drift")
    core_head = run(["git", "rev-parse", "HEAD"], cwd=CORE).decode().strip()
    require(core_head == CORE_COMMIT, "mega65-core authority drift")
    cold_boot = load(COLD_BOOT_RECEIPT)
    require(cold_boot["hardware_result"]["line1"]["boot_upper_bound"] ==
            ("27.653 seconds from the loader's RUN timestamp to the completed "
             "JTAG screenshot; the prompt may have appeared earlier"),
            "cold-boot observation bound drift")
    cpu_source = CORE_CPU.read_text(encoding="utf-8")
    monitor_source = CORE_MONITOR.read_text(encoding="utf-8")
    require('monitor_mem_address_drive(27 downto 16) = x"777"' in cpu_source
            and "M777xxxx in serial monitor reads memory from CPU's perspective"
            in cpu_source, "CPU-view monitor contract drift")
    require("MAPH MAPL" in monitor_source and "RECA8LHC" in monitor_source,
            "full monitor register format drift")
    parsed = parse_registers(register_fixture())
    require(parsed["PC"] == "0xe1c2" and parsed["X"] == "0x07"
            and parsed["MAPH"] == "0x8000" and parsed["MAPL"] == "0x0000"
            and "lhc" in parsed["tail"], "register parser self-oracle drift")
    address = cpu_view_address(WITNESS)
    require(parse_memory(memory_fixture(address, b"\xd7"), address, 1) == b"\xd7",
            "CPU-view memory parser self-oracle drift")
    product_probe = source_candidates(E000_PROBE, E000_PROBE_BYTES)[
        "diagnostic-E000-window"]
    rom_probe = source_candidates(E000_PROBE, E000_PROBE_BYTES)["MEGA65-ROM"]
    require(code_owner(E000_PROBE, product_probe)["selected_owner"] ==
            "diagnostic-E000-window"
            and code_owner(E000_PROBE, rom_probe)["selected_owner"] ==
            "MEGA65-ROM" and product_probe != rom_probe,
            "independent code-owner oracle drift")
    reads = [WITNESS, FREELIST, GC_RUNS, GC_CONTEXT, E000_PROBE]
    require(all((cpu_view_address(value) >> 16) == 0x0777 for value in reads),
            "not every fixed read uses CPU-view resolution")
    schedule = capture_schedule(DRIVER.read_text(encoding="utf-8"))
    return {
        "owner_authority": bind_blob(f"git:{owner_commit}:{PLAN}", plan_blob),
        "identity": {
            "diagnostic_PRG": bind(PATCHED_PRG), "base_PRG": bind(BASE_PRG),
            "diagnostic_window": bind(WINDOW), "promotable": False,
            "product_bytes_changed": 0, "diagnostic_bytes_changed": 2,
            "entry_stamp": {"address": "0xb5c3", "reset": "0xd7",
                            "entered": "0x44"},
        },
        "view_contract": {
            "logical_to_monitor": "0x07770000 | logical_16_bit_address",
            "fixed_logical_reads": [f"0x{value:04x}" for value in reads],
            "all_fixed_monitor_reads": [
                f"m{cpu_view_address(value):08x}" for value in reads],
            "register_fields_retained": [
                "PC", "A", "X", "Y", "Z", "B", "SP", "MAPH", "MAPL",
                "raw-row-tail-including-ROM-flags"],
            "mapping_bound_per_sample": True,
            "code_owner_before_symbol_interpretation": True,
            "ambiguous_owner_is_red": True,
            "prelaunch_CPU_value_is_context_only": True,
            "physical_underlay_reset_readback_required": True,
        },
        "code_owner_oracle": {
            "sources": ["diagnostic-PRG", "diagnostic-E000-window",
                        "MEGA65-ROM"],
            "comparison": "exact CPU-view bytes at the stopped PC",
            "fixed_E000_probe": "0xe1b8..0xe1c7",
            "kernal_BASIC_idle_discriminators": [
                "unique MEGA65-ROM match at stopped PC",
                "unique MEGA65-ROM match for the fixed E000 probe",
                "PC in bound KERNAL descending-X loop 0xe1be..0xe1c7",
                "entry sentinel remains 0xd7"],
        },
        "appointment": {
            "physical_RUN": True, "samples": SAMPLES,
            "spacing_seconds": SPACING_SECONDS,
            "first_observation_quiet_seconds":
                FIRST_OBSERVATION_QUIET_SECONDS,
            "minimum_sample_offsets_seconds": [
                FIRST_OBSERVATION_QUIET_SECONDS,
                FIRST_OBSERVATION_QUIET_SECONDS + SPACING_SECONDS,
                FIRST_OBSERVATION_QUIET_SECONDS + 2 * SPACING_SECONDS],
            "capture_invocation_follows_owner_launch": True,
            "monitor_entry_before_quiet_floor": "FIRST-RED",
            "recontact_authorized": RECONTACT_AUTHORIZED,
            "implementation": schedule,
            "measured_forms": 0, "R_A_I_G_claimed": False,
            "leave_CPU_stopped_after_final_sample": True,
        },
        "decision_table": {
            "reset_stamp_plus_kernal_idle":
                "KERNAL-BASIC-IDLE-LAUNCH-NOT-HANDED-OVER",
            "reset_stamp_other": "BOOT-ENTRY-IDENTITY-FIRST-RED",
            "entered_plus_changing_state": "TEMPORALLY-OBSERVED-PROGRESS",
            "entered_plus_stable_product_GC": "STALLED-IN-SINGLE-COLLECTION",
            "entered_plus_GC_generation_growth": "ALLOCATION-GC-REENTRY-LOOP",
            "entered_plus_other_stable_product_PC": "POST-ENTRY-HANG-SITE",
            "ambiguous_view_or_owner": "VIEW-OR-OWNER-FIRST-RED",
        },
    }


def audit(facts: dict[str, Any]) -> None:
    view = facts["view_contract"]
    owner = facts["code_owner_oracle"]
    appointment = facts["appointment"]
    table = facts["decision_table"]
    require(view["logical_to_monitor"] ==
            "0x07770000 | logical_16_bit_address"
            and all(value.startswith("m0777")
                    for value in view["all_fixed_monitor_reads"])
            and view["mapping_bound_per_sample"]
            and view["code_owner_before_symbol_interpretation"]
            and view["ambiguous_owner_is_red"]
            and view["prelaunch_CPU_value_is_context_only"]
            and view["physical_underlay_reset_readback_required"]
            and "MAPH" in view["register_fields_retained"]
            and "MAPL" in view["register_fields_retained"],
            "corrected CPU-view contract drift")
    require(owner["comparison"] == "exact CPU-view bytes at the stopped PC"
            and len(owner["kernal_BASIC_idle_discriminators"]) == 4,
            "code-owner/idle oracle drift")
    require(appointment["physical_RUN"]
            and appointment["samples"] == 3
            and appointment["spacing_seconds"] == 5.0
            and appointment["first_observation_quiet_seconds"] >=
                FIRST_OBSERVATION_QUIET_SECONDS
            and appointment["minimum_sample_offsets_seconds"] ==
                [27.653, 32.653, 37.653]
            and appointment["capture_invocation_follows_owner_launch"]
            and appointment["monitor_entry_before_quiet_floor"] == "FIRST-RED"
            and appointment["recontact_authorized"]
            and appointment["implementation"] == {
                "ordered_steps": [
                    "owner-authorization", "quiet-start",
                    "27.653-second-sleep", "serial-open", "monitor-sync",
                    "t1"],
                "first_device_access_after_sleep": True,
            }
            and appointment["measured_forms"] == 0
            and not appointment["R_A_I_G_claimed"]
            and appointment["leave_CPU_stopped_after_final_sample"],
            "appointment boundary drift")
    require(len(table) == 7 and table["ambiguous_view_or_owner"] ==
            "VIEW-OR-OWNER-FIRST-RED",
            "decision table closure drift")


def selftest() -> dict[str, Any]:
    base = exact_facts()
    audit(base)
    cases: dict[str, tuple[list[str], Any]] = {
        "physical-view-read":
            (["view_contract", "all_fixed_monitor_reads", 0], "m0000b5c3"),
        "discard-MAPH":
            (["view_contract", "register_fields_retained"], ["PC", "MAPL"]),
        "discard-MAPL":
            (["view_contract", "register_fields_retained"], ["PC", "MAPH"]),
        "mapping-not-bound":
            (["view_contract", "mapping_bound_per_sample"], False),
        "symbolize-before-owner":
            (["view_contract", "code_owner_before_symbol_interpretation"], False),
        "accept-ambiguous-owner":
            (["view_contract", "ambiguous_owner_is_red"], False),
        "treat-prelaunch-CPU-value-as-underlay":
            (["view_contract", "prelaunch_CPU_value_is_context_only"], False),
        "skip-physical-underlay-readback":
            (["view_contract", "physical_underlay_reset_readback_required"],
             False),
        "metadata-owner-oracle":
            (["code_owner_oracle", "comparison"], "MAP metadata only"),
        "drop-idle-discriminator":
            (["code_owner_oracle", "kernal_BASIC_idle_discriminators"], []),
        "virtual-RUN": (["appointment", "physical_RUN"], False),
        "measured-form": (["appointment", "measured_forms"], 1),
        "claim-R-A-I-G": (["appointment", "R_A_I_G_claimed"], True),
        "resume-final":
            (["appointment", "leave_CPU_stopped_after_final_sample"], False),
        "drop-sample": (["appointment", "samples"], 2),
        "change-spacing": (["appointment", "spacing_seconds"], 0.0),
        "early-t1":
            (["appointment", "first_observation_quiet_seconds"], 0.0),
        "revoke-recontact":
            (["appointment", "recontact_authorized"], False),
        "drop-decision-row":
            (["decision_table", "ambiguous_view_or_owner"], "continue"),
    }
    rejected: dict[str, str] = {}
    for name, (path, replacement) in cases.items():
        trial = deepcopy(base)
        cursor: Any = trial
        for component in path[:-1]:
            cursor = cursor[component]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except CorrectedViewError as error:
            rejected[name] = str(error)
        else:
            raise CorrectedViewError(f"verification mutation survived: {name}")
    source = DRIVER.read_text(encoding="utf-8")
    sleep_line = "    time.sleep(FIRST_OBSERVATION_QUIET_SECONDS)\n"
    t1_line = '            command(fd, b"t1", 0.05)\n'
    require(source.count(sleep_line) == 1 and source.count(t1_line) == 1,
            "schedule mutation fixture drift")
    early = source.replace(sleep_line, "", 1).replace(
        t1_line, t1_line + sleep_line, 1)
    try:
        capture_schedule(early)
    except CorrectedViewError as error:
        rejected["early-t1-source-order"] = str(error)
    else:
        raise CorrectedViewError(
            "verification mutation survived: early-t1-source-order")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "rejected": rejected}


def expected_preparation() -> dict[str, Any]:
    facts = exact_facts()
    audit(facts)
    rejected = selftest()["rejected"]
    return {
        "format": "lisp65-c2.3-v1.6-D2-corrected-view-quiet-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "HOST-GREEN; ONE QUIET RECONTACT AUTHORIZED",
        "authorities": {
            "owner": facts.pop("owner_authority"),
            "identity_view_attribution": bind(ATTRIBUTION),
            "prior_durable_preparation": bind(OLD_PREP),
            "deployment": bind(DEPLOY), "ROM_contract": bind(ROM_CONTRACT),
            "MEGA65_ROM": bind(rom_path()), "core_CPU_view": bind(CORE_CPU),
            "core_monitor_format": bind(CORE_MONITOR), "driver": bind(DRIVER),
            "hardware_runner": bind(RUNNER),
            "cold_boot_upper_bound": bind(COLD_BOOT_RECEIPT),
        },
        "facts": facts, "mutations_rejected": rejected,
        "execution_witnesses": [
            "all fixed state reads carry the 0x0777 CPU-view prefix",
            "MAPH and MAPL are parsed and retained in every register sample",
            "raw monitor tails retain the ROM-enable fields",
            "stopped-PC bytes are compared independently with product and ROM",
            "an ambiguous code owner is fail-closed",
            "the fixed E000 probe distinguishes product window from KERNAL ROM",
            "no Lisp form or R/A/I/G measurement runs in this contact",
            "the first t1 waits at least 27.653 seconds after capture starts",
            "the CPU remains stopped after the final sample",
        ],
        "claim_limit": (
            "Owner-authorized corrected-view physical recontact with the "
            "27.653-second quiet floor and three CPU-view samples. It "
            "authorizes no Lisp form, R/A/I/G row, product fix, Link or "
            "release."),
    }


def sample(fd: int, index: int) -> dict[str, Any]:
    registers = read_registers(fd)
    pc = int(registers["PC"], 16)
    witness, witness_raw = read_cpu(fd, WITNESS, 1)
    freelist, freelist_raw = read_cpu(fd, FREELIST, 2)
    gc_runs, runs_raw = read_cpu(fd, GC_RUNS, 2)
    context, context_raw = read_cpu(fd, GC_CONTEXT, GC_CONTEXT_BYTES)
    e000, e000_raw = read_cpu(fd, E000_PROBE, E000_PROBE_BYTES)
    pc_bytes, pc_raw = read_cpu(fd, pc, CODE_PROBE_BYTES)
    pc_owner = code_owner(pc, pc_bytes)
    e000_owner = code_owner(E000_PROBE, e000)
    idle = {
        "entry_reset": witness[0] == RESET,
        "entry_stamped": witness[0] == STAMP,
        "PC_owner_is_MEGA65_ROM":
            pc_owner["selected_owner"] == "MEGA65-ROM",
        "E000_owner_is_MEGA65_ROM":
            e000_owner["selected_owner"] == "MEGA65-ROM",
        "PC_in_bound_KERNAL_descending_X_loop": 0xE1BE <= pc <= 0xE1C7,
    }
    return {
        "sample": index, "captured_at_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "registers": registers, "PC": registers["PC"],
        "mapping": {"MAPH": registers["MAPH"], "MAPL": registers["MAPL"],
                    "raw_tail": registers["tail"]},
        "code_owner": pc_owner, "E000_owner": e000_owner,
        "durable_witness": f"0x{witness[0]:02x}",
        "freelist_head": f"0x{int.from_bytes(freelist, 'little'):04x}",
        "gc_runs": int.from_bytes(gc_runs, "little"),
        "GC_context": context.hex(), "KERNAL_BASIC_idle": idle,
        "raw": {"witness": witness_raw, "freelist": freelist_raw,
                "gc_runs": runs_raw, "GC_context": context_raw,
                "E000_owner": e000_raw, "PC_owner": pc_raw},
    }


def owners_proved(samples: list[dict[str, Any]]) -> bool:
    return all(row["code_owner"]["unique"] and row["E000_owner"]["unique"]
               and row["mapping"]["MAPH"].startswith("0x")
               and row["mapping"]["MAPL"].startswith("0x") for row in samples)


def product_owned(row: dict[str, Any]) -> bool:
    return row["code_owner"]["selected_owner"] in {
        "diagnostic-PRG", "diagnostic-E000-window"}


def classify(samples: list[dict[str, Any]]) -> str:
    if not owners_proved(samples):
        return "VIEW-OR-OWNER-FIRST-RED"
    stamps = [int(row["durable_witness"], 16) for row in samples]
    if any(value != STAMP for value in stamps):
        if (all(value == RESET for value in stamps)
                and all(row["KERNAL_BASIC_idle"]["PC_owner_is_MEGA65_ROM"]
                        and row["KERNAL_BASIC_idle"]["E000_owner_is_MEGA65_ROM"]
                        for row in samples)):
            return "KERNAL-BASIC-IDLE-LAUNCH-NOT-HANDED-OVER"
        return "BOOT-ENTRY-IDENTITY-FIRST-RED"
    if not all(product_owned(row) for row in samples):
        return "POST-ENTRY-CODE-OWNER-DIVERGENCE"
    pcs = [row["PC"] for row in samples]
    runs = [row["gc_runs"] for row in samples]
    heads = [row["freelist_head"] for row in samples]
    contexts = [row["GC_context"] for row in samples]
    if all(left <= right for left, right in zip(runs, runs[1:])) \
            and any(left < right for left, right in zip(runs, runs[1:])) \
            and all(value == "0x0000" for value in heads):
        return "ALLOCATION-GC-REENTRY-LOOP"
    if len(set(pcs)) == len(set(runs)) == len(set(heads)) == 1 \
            and len(set(contexts)) == 1:
        return "POST-ENTRY-HANG-SITE"
    if (len(set(pcs)) > 1 or len(set(runs)) > 1 or len(set(heads)) > 1
            or len(set(contexts)) > 1):
        return "TEMPORALLY-OBSERVED-PROGRESS"
    return "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM"


def prelaunch(device: str) -> dict[str, Any]:
    require(PREP_RECEIPT.is_file()
            and load(PREP_RECEIPT) == expected_preparation(),
            "corrected-view preparation receipt drift")
    require(not PRELAUNCH.exists(), "corrected-view prelaunch is one-shot")
    require(UNDERLAY_READBACK.is_file()
            and UNDERLAY_READBACK.read_bytes() == bytes([RESET]),
            "physical underlay sentinel readback absent or drifted")
    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c2v16correctedpre\r")
        command(fd, b"t1", 0.05)
        registers = read_registers(fd)
        witness, raw = read_cpu(fd, WITNESS, 1)
        value = {
            "status": "PRELAUNCH CPU-VIEW PASS", "device": device,
            "registers": registers,
            "physical_underlay_witness": "0xd7",
            "physical_underlay_readback": bind(UNDERLAY_READBACK),
            "CPU_view_at_BASIC_prelaunch": f"0x{witness[0]:02x}",
            "CPU_view_prelaunch_semantics": (
                "context only; BASIC mapping need not expose the RAM underlay"),
            "raw_CPU_view": raw, "CPU_resumed": True,
        }
        write_json(PRELAUNCH, value)
        command(fd, b"t0", 0.03)
        return value
    finally:
        os.close(fd)


def capture(device: str) -> dict[str, Any]:
    require(RECONTACT_AUTHORIZED,
            "corrected-view recontact awaits explicit owner authorization")
    expected = expected_preparation()
    require(PREP_RECEIPT.is_file() and load(PREP_RECEIPT) == expected,
            "corrected-view preparation receipt drift")
    pre = load(PRELAUNCH)
    require(pre["status"] == "PRELAUNCH CPU-VIEW PASS"
            and pre["physical_underlay_witness"] == "0xd7"
            and pre["CPU_view_prelaunch_semantics"].startswith("context only")
            and pre["CPU_resumed"] is True,
            "prelaunch CPU-view proof absent")
    require(not DEVICE_RECEIPT.exists(), "corrected-view contact is one-shot")
    quiet_started = time.monotonic()
    time.sleep(FIRST_OBSERVATION_QUIET_SECONDS)
    quiet_elapsed = time.monotonic() - quiet_started
    require(quiet_elapsed >= FIRST_OBSERVATION_QUIET_SECONDS,
            "first monitor entry preceded the bound quiet interval")
    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    samples: list[dict[str, Any]] = []
    try:
        SERIAL.configure_serial(fd)
        for index in range(SAMPLES):
            SERIAL.monitor_sync(fd, f"#c2v16corrected{index}\r".encode())
            command(fd, b"t1", 0.05)
            samples.append(sample(fd, index + 1))
            if index + 1 < SAMPLES:
                command(fd, b"t0", 0.03)
                time.sleep(SPACING_SECONDS)
        # Deliberately stopped after the final sample.
    finally:
        os.close(fd)
    status = classify(samples)
    receipt = {
        "format": "lisp65-c2.3-v1.6-D2-corrected-view-quiet-device-v1",
        "recorded_on": date.today().isoformat(), "status": status,
        "device": device,
        "authorities": {"preparation": bind(PREP_RECEIPT),
                        "prelaunch": bind(PRELAUNCH), "driver": bind(DRIVER)},
        "samples": samples,
        "result": {"classification": status, "CPU_left_stopped": True,
                   "first_observation_quiet_seconds": quiet_elapsed,
                   "quiet_floor_seconds": FIRST_OBSERVATION_QUIET_SECONDS,
                   "measured_forms_run": 0, "R_A_I_G_claimed": False,
                   "all_state_reads_CPU_view": True,
                   "MAPH_MAPL_bound_per_sample": True,
                   "code_owner_bound_before_interpretation": True},
        "claim_limit": expected["claim_limit"],
    }
    write_json(DEVICE_RECEIPT, receipt)
    print(json.dumps(receipt, sort_keys=True))
    return receipt


def prepare() -> dict[str, Any]:
    materialize()
    value = expected_preparation()
    write_json(PREP_RECEIPT, value)
    return value


def check() -> dict[str, Any]:
    materialize()
    expected = expected_preparation()
    require(PREP_RECEIPT.is_file() and load(PREP_RECEIPT) == expected,
            "corrected-view preparation receipt drift")
    return {"status": "PASS", "samples": SAMPLES,
            "CPU_view_prefix": "0x0777", "mutations": 20,
            "first_observation_quiet_seconds":
                FIRST_OBSERVATION_QUIET_SECONDS,
            "recontact_authorized": RECONTACT_AUTHORIZED,
            "prelaunch_present": PRELAUNCH.exists(),
            "device_result_present": DEVICE_RECEIPT.exists()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=(
        "prepare", "check", "selftest", "prelaunch", "capture"))
    parser.add_argument("--device", default=SERIAL.DEVICE)
    args = parser.parse_args()
    if args.action == "prepare":
        value = prepare()
    elif args.action == "check":
        value = check()
    elif args.action == "selftest":
        materialize()
        value = selftest()
    elif args.action == "prelaunch":
        value = prelaunch(args.device)
    else:
        capture(args.device)
        return 0
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CorrectedViewError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-v1.6-corrected-view: FIRST RED: " + str(error))
        raise SystemExit(2)
