#!/usr/bin/env python3
"""Prepare and capture the owner-authorized G4-corrected v1.6 full run.

The released Link-82 product remains untouched.  This closure stages the
non-promotable diagnostic whose G4 expectation was recomputed from its own
8-KiB KERNAL window, proves the complete reset domain, and separates the
owner's three physical actions from the one post-defstruct stop.
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
import c2_v16_corrected_view_contact as VIEW  # noqa: E402
import c2_v16_full_ladder_contact as PHYSICAL  # noqa: E402
import c2_v16_mem_init_before_after_contact as MEM  # noqa: E402
import c2_v16_romc_repaired_d2_appointment as APPT  # noqa: E402


OWNER_COMMIT = "86f3af8a"
PLAN = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
DEPLOY = ROOT / "build/c2.3/v1.6-defstruct-ownership-crc-bound/deployment.json"
GUARD_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-ownership-guard-attribution-receipt.json")
PHASE_B = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-b-guard-partition-receipt.json")
OUT = ROOT / (
    "build/c2.3/v1.6-defstruct-closing-session/"
    "d2-ownership-crc-full-run")
PREP_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-ownership-crc-full-run-preparation-receipt.json")
DEVICE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-ownership-crc-full-run-device-receipt.json")
RUNNER = ROOT / "scripts/c2-v16-defstruct-ownership-crc-full-run-hw.sh"
DRIVER = Path(__file__).resolve()

RECORD = 0xC03F
RECORD_BYTES = 65
BOOT_WITNESS = 0xB5C3
BOOT_STAMP = 0x44
MEM_WITNESS = 0xB582
MEM_WITNESS_BYTES = 10
LADDER = 0xB58C
LADDER_BYTES = 6
FREELIST = 0x003D
ALLOC_HIGH = 0x0039
GC_FROZEN = 0x003B
PHASE = 0xC0C6
PHASE_BYTES = 304
FIRST_ERROR_OFFSET = 302
PHASE_OWNER = 0x0089
MEM_OOM = 0x008F
GC_RUNS = 0xB9F0
C2D = 0x00050000
C2D_BYTES = 50816
C2J = 0x0005C640
C2J_BYTES = 64
BANK2 = 0x00020000
BANK2_BYTES = 65536
QUIET_SECONDS = 180.0
STABLE_READS = 3
STABLE_SPACING = 2.0
CODE_PROBE = 16


class FullRunError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FullRunError(message)


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


def run(args: list[str]) -> bytes:
    result = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    require(result.returncode == 0,
            f"command failed ({' '.join(args)}): "
            f"{result.stderr.decode(errors='replace')}")
    return result.stdout


def git_blob(commit: str, path: str) -> tuple[str, bytes]:
    full = run(["git", "rev-parse", f"{commit}^{{commit}}"]).decode().strip()
    return full, run(["git", "show", f"{full}:{path}"])


def prg_slice(raw: bytes, address: int, size: int) -> bytes | None:
    if len(raw) < 2:
        return None
    offset = 2 + address - int.from_bytes(raw[:2], "little")
    if offset < 2 or offset + size > len(raw):
        return None
    return raw[offset:offset + size]


def source_candidates(logical: int, size: int) -> dict[str, bytes]:
    deployment = load(DEPLOY)
    result: dict[str, bytes] = {}
    prg = (ROOT / deployment["diagnostic"]["prg"]["path"]).read_bytes()
    resident = prg_slice(prg, logical, size)
    if resident is not None:
        result["ownership-CRC-bound-diagnostic-PRG"] = resident
    window = (ROOT / deployment["diagnostic"]["window"]["path"]).read_bytes()
    if 0xE000 <= logical and logical + size <= 0x10000:
        result["diagnostic-E000-window"] = window[
            logical - 0xE000:logical - 0xE000 + size]
    rom = APPT.rom_path().read_bytes()[0x10000:]
    if logical + size <= len(rom):
        result["MEGA65-ROM"] = rom[logical:logical + size]
    return result


def code_owner(logical: int, observed: bytes) -> dict[str, Any]:
    candidates = source_candidates(logical, len(observed))
    matches = [name for name, value in candidates.items() if value == observed]
    return {
        "logical_address": f"0x{logical:04x}", "observed": observed.hex(),
        "candidate_bytes": {name: value.hex()
                            for name, value in sorted(candidates.items())},
        "matches": matches,
        "selected_owner": matches[0] if len(matches) == 1 else "unresolved",
        "unique": len(matches) == 1,
        "symbol_interpretation_allowed": len(matches) == 1,
    }


def read_cpu_block(fd: int, logical: int, size: int) -> tuple[bytes, list[dict[str, Any]]]:
    require(0 <= logical <= 0xFFFF and logical + size <= 0x10000,
            "CPU-view read crosses logical address space")
    value = bytearray()
    rows: list[dict[str, Any]] = []
    while len(value) < size:
        count = min(16, size - len(value))
        part, evidence = VIEW.read_cpu(fd, logical + len(value), count)
        value.extend(part); rows.append(evidence)
    return bytes(value), rows


def read_physical(fd: int, logical: int, size: int) -> tuple[bytes, list[dict[str, Any]]]:
    return PHYSICAL.read_physical(fd, logical, size)


def runner_contract(source: str) -> dict[str, Any]:
    require("dry-run|stage|verify-boot|arm|capture" in source,
            "full-run action surface drift")
    require("RESET_DOMAIN_BYTES=50816" in source
            and "partial reset-domain staging rejected" in source
            and "pre-run-c2j.bin" in source
            and 'assert c2j == b"\\0" * 64' in source,
            "complete reset-domain/C2J closure absent")
    require("ftp_medium" in source and "FTP_STALL_LIMIT" in source
            and 'cmp "$medium" "$OUT/readback.d81"' in source,
            "guarded library-medium readback absent")
    stage = source.split('if [ "$ACTION" = stage ]; then', 1)[1].split(
        'if [ "$ACTION" = verify-boot ]; then', 1)[0]
    require("run_m65 -t" not in stage and "monitor_sync" not in stage,
            "prelaunch monitor access leaked into stage")
    require("type RUN and press RETURN physically" in stage,
            "physical RUN handoff absent")
    verify = source.split('if [ "$ACTION" = verify-boot ]; then', 1)[1].split(
        'if [ "$ACTION" = arm ]; then', 1)[0]
    require("27.653" in verify and "lisp65>" in verify
            and "type (require 'defstruct) physically" in verify,
            "boot quiet/prompt/require handoff drift")
    arm = source.split('if [ "$ACTION" = arm ]; then', 1)[1].split(
        'exec python3 "$PY" capture', 1)[0]
    require("require-result" in arm and "lisp65>" in arm
            and 'assert "t" in lines' in arm
            and '"$RESET@$record_hex"' in arm and '"$ARM@$record_hex"' in arm
            and "type (defstruct point x y) physically" in arm,
            "require verification or post-require record arm absent")
    capture = DRIVER.read_text(encoding="utf-8").split(
        "def capture(device: str)", 1)[1].split("\ndef main", 1)[0]
    order = [capture.index(marker) for marker in (
        "quiet_started = time.monotonic()", "time.sleep(QUIET_SECONDS)",
        "first_observation = screen_capture()", "os.open(device",
        "SERIAL.monitor_sync", 'VIEW.command(fd, b"t1"')]
    require(order == sorted(order), "device access precedes 180-second quiet floor")
    return {
        "actions": ["stage", "verify-boot", "arm", "capture"],
        "owner_input": ["RUN", "(require 'defstruct)",
                        "(defstruct point x y)"],
        "virtual_key_events": 0, "prelaunch_monitor_accesses": 0,
        "boot_quiet_floor_seconds": 27.653,
        "defstruct_quiet_seconds": QUIET_SECONDS,
        "stops_during_measured_form": 1,
        "record_arm": "canonical reset plus A1 only after visible require=t",
    }


def expected_facts() -> dict[str, Any]:
    owner, plan = git_blob(OWNER_COMMIT, PLAN)
    text = plan.decode("utf-8")
    require("Bundled full-run appointment authorized" in text
            and "Full staging ritual" in text
            and "recontact_authorized` flips" in text,
            "owner full-run authorization absent")
    deployment = load(DEPLOY)
    guard = load(GUARD_RECEIPT)
    require(deployment["status"] ==
            "HOST-GREEN-NON-PROMOTABLE-OWNERSHIP-CRC-BOUND"
            and deployment["promotable"] is False,
            "G4-corrected deployment drift")
    require(deployment["ownership_guard_binding"]["computed_crc16"] == "0xD24C"
            and deployment["ownership_guard_binding"]["final_PRG_operand_bytes"] ==
                "d24c", "diagnostic G4 expectation drift")
    require(guard["status"] ==
            "PRODUCT-GUARD-CORRECT-DIAGNOSTIC-IDENTITY-REPAIRED"
            and guard["verification"]["mutations"] == 22,
            "G4 attribution authority drift")
    for role in ("prg", "elf", "window"):
        row = deployment["diagnostic"][role]
        require(bind(ROOT / row["path"])["sha256"] == row["sha256"],
                f"diagnostic {role} binding drift")
    reset_rows = [row for row in deployment["diagnostic"]["preloads"]
                  if row["role"] == "c2d-v6-reset-domain"]
    require(len(reset_rows) == 1 and reset_rows[0]["bytes"] == C2D_BYTES,
            "one complete reset-domain preload required")
    reset_raw = (ROOT / reset_rows[0]["path"]).read_bytes()
    require(len(reset_raw) == C2D_BYTES and reset_raw[33840:] ==
            b"\0" * (C2D_BYTES - 33840) and reset_raw[-64:] == b"\0" * 64,
            "reset-domain null suffix/C2J drift")
    record_reset = ROOT / deployment["record"]["reset"]["path"]
    record_arm = ROOT / deployment["record"]["arm"]["path"]
    require(len(record_reset.read_bytes()) == RECORD_BYTES
            and record_arm.read_bytes() == b"\xa1", "record authorities drift")
    mem_reset = ROOT / deployment["mem_init_witness"]["reset"]["path"]
    require(mem_reset.read_bytes() == bytes.fromhex("d1ccccccccd2cccccccc"),
            "mem_init witness reset drift")
    return {
        "owner_authority": bind_blob(f"git:{owner}:{PLAN}", plan),
        "authorities": {"deployment": bind(DEPLOY), "G4": bind(GUARD_RECEIPT),
                        "phase_B": bind(PHASE_B), "driver": bind(DRIVER),
                        "runner": bind(RUNNER)},
        "identity": {"promotable": False, "product_bytes_changed": 0,
                     "expected_G4_crc16": "0xD24C",
                     "diagnostic_PRG": bind(ROOT / deployment["diagnostic"]["prg"]["path"]),
                     "diagnostic_ELF": bind(ROOT / deployment["diagnostic"]["elf"]["path"]),
                     "diagnostic_window": bind(ROOT / deployment["diagnostic"]["window"]["path"])},
        "reset_domain": {"bytes": C2D_BYTES, "prefix_bytes": 33840,
                         "null_suffix_bytes": C2D_BYTES - 33840,
                         "C2J_CLEAR_before_RUN": True},
        "mem_init_witness": {"address": "0xb582", "bytes": 10,
                             "before_tag": "0xa1", "after_tag": "0xa6",
                             "read_post_session": True},
        "choreography": runner_contract(RUNNER.read_text(encoding="utf-8")),
        "read_protocol": {
            "code": "CPU-view bytes plus unique active-owner binding",
            "data": "capture MAPH/MAPL then physical Bank-0 RAM underlay",
            "far_planes": ["C2J", "C2D-reset-domain", "Bank-2-source"],
            "record_stable_reads": STABLE_READS,
            "CPU_left_stopped": True,
        },
        "classification": {"mem_init_binary": True,
                           "R_A_I_G_rows": ["R", "A", "I", "G"],
                           "R_A_I_G_pending_independent_oracle_decode": True,
                           "claim_widening_allowed": False},
    }


def audit(value: dict[str, Any]) -> None:
    identity = value["identity"]; choreography = value["choreography"]
    protocol = value["read_protocol"]; classification = value["classification"]
    require(not identity["promotable"] and identity["product_bytes_changed"] == 0
            and identity["expected_G4_crc16"] == "0xD24C",
            "diagnostic identity boundary drift")
    require(value["reset_domain"] == {"bytes": 50816, "prefix_bytes": 33840,
            "null_suffix_bytes": 16976, "C2J_CLEAR_before_RUN": True},
            "reset-domain contract drift")
    require(choreography["virtual_key_events"] == 0
            and choreography["prelaunch_monitor_accesses"] == 0
            and choreography["boot_quiet_floor_seconds"] == 27.653
            and choreography["defstruct_quiet_seconds"] == 180.0
            and choreography["stops_during_measured_form"] == 1,
            "physical/quiet/one-stop choreography drift")
    require(protocol["record_stable_reads"] == 3
            and protocol["CPU_left_stopped"]
            and classification == {"mem_init_binary": True,
                "R_A_I_G_rows": ["R", "A", "I", "G"],
                "R_A_I_G_pending_independent_oracle_decode": True,
                "claim_widening_allowed": False},
            "read/classification boundary drift")


def selftest() -> dict[str, str]:
    base = expected_facts(); audit(base)
    cases: dict[str, tuple[list[str], Any]] = {
        "promote-diagnostic": (["identity", "promotable"], True),
        "use-control-crc": (["identity", "expected_G4_crc16"], "0x39AA"),
        "change-product": (["identity", "product_bytes_changed"], 2),
        "prefix-only-stage": (["reset_domain", "bytes"], 33840),
        "dirty-c2j": (["reset_domain", "C2J_CLEAR_before_RUN"], False),
        "virtual-input": (["choreography", "virtual_key_events"], 1),
        "prelaunch-monitor": (["choreography", "prelaunch_monitor_accesses"], 1),
        "short-boot-floor": (["choreography", "boot_quiet_floor_seconds"], 0),
        "short-defstruct-floor": (["choreography", "defstruct_quiet_seconds"], 179),
        "second-stop": (["choreography", "stops_during_measured_form"], 2),
        "unstable-record": (["read_protocol", "record_stable_reads"], 1),
        "resume-after-read": (["read_protocol", "CPU_left_stopped"], False),
        "drop-mem-answer": (["classification", "mem_init_binary"], False),
        "preclaim-row": (["classification", "R_A_I_G_pending_independent_oracle_decode"], False),
        "widen-row": (["classification", "claim_widening_allowed"], True),
    }
    rejected: dict[str, str] = {}
    for name, (path, replacement) in cases.items():
        trial = deepcopy(base); cursor: Any = trial
        for part in path[:-1]:
            cursor = cursor[part]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except FullRunError as error:
            rejected[name] = str(error)
    require(set(rejected) == set(cases), "full-run mutation escaped")
    return rejected


def prepare() -> dict[str, Any]:
    facts = expected_facts(); rejected = selftest()
    receipt = {
        "format": "lisp65-c2.3-v1.6-ownership-crc-full-run-preparation-v1",
        "recorded_on": "2026-08-06",
        "status": "HOST-GREEN; OWNER-AUTHORIZED FULL RUN READY",
        "facts": facts, "mutations_rejected": rejected,
        "execution_witnesses": 10,
        "claim_limit": (
            "Preparation for one G4-corrected, non-promotable bundled run. No "
            "device result, mem_init answer or R/A/I/G row is claimed here."),
    }
    write_json(PREP_RECEIPT, receipt); return receipt


def check() -> dict[str, Any]:
    expected = {"format": "lisp65-c2.3-v1.6-ownership-crc-full-run-preparation-v1",
                "recorded_on": "2026-08-06",
                "status": "HOST-GREEN; OWNER-AUTHORIZED FULL RUN READY",
                "facts": expected_facts(), "mutations_rejected": selftest(),
                "execution_witnesses": 10,
                "claim_limit": (
                    "Preparation for one G4-corrected, non-promotable bundled run. No "
                    "device result, mem_init answer or R/A/I/G row is claimed here.")}
    require(load(PREP_RECEIPT) == expected, "full-run preparation receipt drift")
    return {"status": "PASS", "mutations": len(expected["mutations_rejected"]),
            "device_receipt_present": DEVICE_RECEIPT.exists()}


def screen_capture() -> dict[str, Any]:
    m65 = ROOT / "tools/m65tools/m65"
    device = os.environ.get("DEVICE", "/dev/ttyUSB1")
    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / "defstruct-first-observation.png"
    ansi = OUT / "defstruct-first-observation.ansi.txt"
    text_path = OUT / "defstruct-first-observation.txt"
    result = subprocess.run([str(m65), "-l", device, f"--screenshot={png}"],
                            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0,
            f"first observation failed: {result.stderr.decode(errors='replace')}")
    ansi.write_bytes(result.stdout)
    text = re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "",
                  result.stdout.decode(errors="replace"))
    text_path.write_text(text, encoding="utf-8")
    return {"png": bind(png), "ansi": bind(ansi), "text": bind(text_path)}


def physical_read(start: int, size: int, path: Path) -> dict[str, Any]:
    m65 = ROOT / "tools/m65tools/m65"
    device = os.environ.get("DEVICE", "/dev/ttyUSB1")
    end = start + size
    result = subprocess.run([str(m65), "-l", device, "-H", "--memsave",
        f"0x{start:08x}:0x{end:08x}={path}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0 and path.is_file() and path.stat().st_size == size,
            f"far-plane read failed at 0x{start:08x}")
    row = bind(path); row.update({"physical_address": f"0x{start:08x}",
        "semantics": "far-backing-plane-oracle-not-PC-symbol-view"})
    return row


def capture(device: str) -> dict[str, Any]:
    check()
    require((OUT / "stage.ready").is_file() and (OUT / "boot.ready").is_file()
            and (OUT / "arm.ready").is_file(), "full-run handoff incomplete")
    require(not DEVICE_RECEIPT.exists() and not (OUT / "capture.consumed").exists(),
            "full-run capture is one-shot")
    (OUT / "capture.consumed").touch()
    quiet_started = time.monotonic()
    time.sleep(QUIET_SECONDS)
    quiet_elapsed = time.monotonic() - quiet_started
    require(quiet_elapsed >= QUIET_SECONDS, "180-second quiet floor shortened")
    first_observation = screen_capture()

    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c2v16ownershipcrcfullrun\r")
        VIEW.command(fd, b"t1", 0.05)
        registers = VIEW.read_registers(fd)
        pc = int(registers["PC"], 16)
        code, code_reads = read_cpu_block(fd, pc, min(CODE_PROBE, 0x10000 - pc))
        owner = code_owner(pc, code)
        require(owner["unique"], "stopped PC has no unique CPU-view owner")
        stable_records: list[dict[str, Any]] = []
        for index in range(STABLE_READS):
            record, record_reads = read_physical(fd, RECORD, RECORD_BYTES)
            stable_records.append({"index": index + 1, "hex": record.hex(),
                                   "physical_reads": record_reads})
            if index + 1 < STABLE_READS:
                time.sleep(STABLE_SPACING)
        require(len({row["hex"] for row in stable_records}) == 1,
                "diagnostic record changed while CPU stopped")
        values: dict[str, tuple[bytes, list[dict[str, Any]]]] = {}
        for name, address, size in (
            ("mem_init_witness", MEM_WITNESS, MEM_WITNESS_BYTES),
            ("micro_ladder", LADDER, LADDER_BYTES),
            ("boot_witness", BOOT_WITNESS, 1),
            ("freelist", FREELIST, 2), ("alloc_high", ALLOC_HIGH, 2),
            ("gc_frozen", GC_FROZEN, 2), ("gc_runs", GC_RUNS, 2),
            ("phase_scratch", PHASE, PHASE_BYTES),
            ("phase_owner", PHASE_OWNER, 1), ("mem_oom", MEM_OOM, 1),
        ):
            values[name] = read_physical(fd, address, size)
        require(values["boot_witness"][0] == bytes([BOOT_STAMP]),
                f"boot witness is not 0x44: {values['boot_witness'][0].hex()}")
    finally:
        os.close(fd)

    OUT.mkdir(parents=True, exist_ok=True)
    raw_files: dict[str, Any] = {}
    for name, (raw, reads) in values.items():
        path = OUT / f"post-{name.replace('_', '-')}.bin"
        path.write_bytes(raw); row = bind(path)
        row.update({"view": "physical-bank0-RAM-underlay", "reads": reads})
        raw_files[name] = row
    record = bytes.fromhex(stable_records[0]["hex"])
    record_path = OUT / "post-diagnostic-record.bin"; record_path.write_bytes(record)
    snapshot = MEM.decode_snapshot(values["mem_init_witness"][0])
    current_head = int.from_bytes(values["freelist"][0], "little")
    mem_result = MEM.classify(snapshot, current_head)
    phase = values["phase_scratch"][0]
    backing = {
        "C2J": physical_read(C2J, C2J_BYTES, OUT / "post-c2j.bin"),
        "C2D": physical_read(C2D, C2D_BYTES, OUT / "post-c2d-reset-domain.bin"),
        "Bank-2": physical_read(BANK2, BANK2_BYTES, OUT / "post-bank2-source.bin"),
    }
    receipt = {
        "format": "lisp65-c2.3-v1.6-ownership-crc-full-run-device-v1",
        "recorded_on": date.today().isoformat(),
        "status": "STOPPED-STATE-CAPTURED; R/A/I/G ORACLE DECODE PENDING",
        "device": device,
        "authorities": {"preparation": bind(PREP_RECEIPT), "driver": bind(DRIVER),
                        "runner": bind(RUNNER), "deployment": bind(DEPLOY)},
        "quiet": {"required_seconds": QUIET_SECONDS,
                  "observed_seconds": quiet_elapsed,
                  "monitor_accesses_during_window": 0},
        "first_observation": first_observation,
        "stop": {"registers": registers, "PC": registers["PC"],
                 "code_owner": owner, "code_reads": code_reads,
                 "mapping": {"MAPH": registers["MAPH"],
                             "MAPL": registers["MAPL"],
                             "raw_tail": registers["tail"]}},
        "stable_record_reads": stable_records,
        "diagnostic_record": bind(record_path),
        "decoded_record": APPT.decode_record(record),
        "mem_init": {"snapshot": snapshot, "current_freelist_head":
                     f"0x{current_head:04x}", "classification": mem_result},
        "current": {"alloc_high": int.from_bytes(values["alloc_high"][0], "little"),
                    "gc_frozen": int.from_bytes(values["gc_frozen"][0], "little"),
                    "gc_runs_RAM_underlay": int.from_bytes(values["gc_runs"][0], "little"),
                    "phase_owner": f"0x{values['phase_owner'][0][0]:02x}",
                    "mem_oom": f"0x{values['mem_oom'][0][0]:02x}",
                    "first_error_hex": phase[
                        FIRST_ERROR_OFFSET:FIRST_ERROR_OFFSET + 2].hex(),
                    "C2J_nonzero_bytes": sum(byte != 0 for byte in
                                               (OUT / "post-c2j.bin").read_bytes())},
        "physical_bank0_captures": raw_files,
        "backing_plane_oracles": backing,
        "result": {"boot_witness": "0x44", "mem_init": mem_result,
                   "record_stable_reads": STABLE_READS,
                   "R_A_I_G": None, "classification_widened": False,
                   "CPU_left_stopped": True},
        "claim_limit": (
            "One owner-authorized G4-corrected full run and its complete stopped "
            "read set. The mem_init binary row is reported; R/A/I/G remains unset "
            "until independent source-byte oracle decode. No row is widened."),
    }
    write_json(DEVICE_RECEIPT, receipt); return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "check", "selftest", "capture"))
    parser.add_argument("--device", default=os.environ.get("DEVICE", "/dev/ttyUSB1"))
    args = parser.parse_args()
    if args.action == "prepare": value = prepare()
    elif args.action == "check": value = check()
    elif args.action == "selftest": value = {"status": "PASS", "rejected": selftest()}
    else: value = capture(args.device)
    print(json.dumps(value, indent=2, sort_keys=True)); return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FullRunError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"c2-v16-ownership-crc-full-run: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
