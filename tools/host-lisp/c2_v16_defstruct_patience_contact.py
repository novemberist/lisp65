#!/usr/bin/env python3
"""Capture the commissioned post-floor defstruct patience stopped state.

The owner made the sole physical screen observation only after the priced
780-second floor and reported the form still active.  The CPU was stopped once
before this program is entered.  This reader never stops or resumes it; it
only confirms the stopped tuple and reads the already-bound v1.6 data set.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
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
import c2_v16_full_ladder_contact as PHYSICAL  # noqa: E402
import c2_v16_mem_init_before_after_contact as MEM  # noqa: E402
import c2_v16_pre_rollback_shadow_contact as SHADOW  # noqa: E402
import c2_v16_romc_repaired_d2_appointment as APPT  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SESSION = ROOT / "config/c2-v16-defstruct-patience-session.json"
PRICING = EVIDENCE / "c2.3-v1.6-defstruct-duration-pricing-receipt.json"
OUT = ROOT / "build/c2.3/v1.6-defstruct-closing-session/d2-defstruct-patience"
RECEIPT = EVIDENCE / "c2.3-v1.6-defstruct-patience-contact-device-receipt.json"

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
STABLE_READS = 3
STABLE_SPACING = 2.0
CODE_PROBE = 16


class PatienceContactError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PatienceContactError(message)


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


def load(path: Path) -> dict[str, Any]:
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


def physical_read_external(device: str, start: int, size: int,
                           path: Path) -> dict[str, Any]:
    tool = ROOT / "tools/m65tools/m65"
    result = subprocess.run([
        str(tool), "-l", device, "-H", "--memsave",
        f"0x{start:08x}:0x{start + size:08x}={path}",
    ], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0 and path.is_file() and path.stat().st_size == size,
            f"far-plane read failed at 0x{start:08x}")
    row = bind(path)
    row.update({"physical_address": f"0x{start:08x}",
                "semantics": "far-backing-plane-oracle-not-PC-symbol-view"})
    return row


def capture(device: str, timer_start_epoch: int,
            expected_pc: int, expected_maph: int, expected_mapl: int) -> dict[str, Any]:
    session = load(SESSION)
    floor = session["quiet_contract"]["minimum_seconds_after_defstruct_submission"]
    require(floor == 780, "patience floor drift")
    now = int(time.time())
    require(now - timer_start_epoch >= floor, "capture precedes patience floor")
    require(not RECEIPT.exists(), "patience device receipt already exists")
    OUT.mkdir(parents=True, exist_ok=True)

    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c2v16patienceread\r")
        registers = VIEW.read_registers(fd)
        require((int(registers["PC"], 16), int(registers["MAPH"], 16),
                 int(registers["MAPL"], 16)) ==
                (expected_pc, expected_maph, expected_mapl),
                "stopped register tuple changed before read set")
        pc = int(registers["PC"], 16)
        code, code_reads = SHADOW.read_cpu_block(
            fd, pc, min(CODE_PROBE, 0x10000 - pc))
        owner = SHADOW.code_owner(pc, code)
        require(owner["unique"], "stopped PC has no unique CPU-view owner")

        stable_records: list[dict[str, Any]] = []
        for index in range(STABLE_READS):
            record, reads = SHADOW.read_physical(fd, RECORD, RECORD_BYTES)
            stable_records.append({"index": index + 1, "hex": record.hex(),
                                   "physical_reads": reads})
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
            values[name] = SHADOW.read_physical(fd, address, size)
        require(values["boot_witness"][0] == bytes([BOOT_STAMP]),
                "boot witness is not 0x44")
    finally:
        os.close(fd)

    raw_files: dict[str, Any] = {}
    for name, (raw, reads) in values.items():
        path = OUT / f"post-{name.replace('_', '-')}.bin"
        path.write_bytes(raw)
        row = bind(path)
        row.update({"view": "physical-bank0-RAM-underlay", "reads": reads})
        raw_files[name] = row

    record = bytes.fromhex(stable_records[0]["hex"])
    record_path = OUT / "post-diagnostic-record.bin"
    record_path.write_bytes(record)
    shadow = SHADOW.decode_shadow(record[SHADOW.SHADOW_OFFSET])
    snapshot = MEM.decode_snapshot(values["mem_init_witness"][0])
    current_head = int.from_bytes(values["freelist"][0], "little")
    mem_result = MEM.classify(snapshot, current_head)
    phase = values["phase_scratch"][0]
    backing = {
        "C2J": physical_read_external(device, C2J, C2J_BYTES,
                                       OUT / "post-c2j.bin"),
        "C2D": physical_read_external(device, C2D, C2D_BYTES,
                                       OUT / "post-c2d-reset-domain.bin"),
        "Bank-2": physical_read_external(device, BANK2, BANK2_BYTES,
                                          OUT / "post-bank2-source.bin"),
    }
    stopped_epoch = int(time.time())
    receipt = {
        "format": "lisp65-c2.3-v1.6-defstruct-patience-contact-device-v1",
        "recorded_on": datetime.now(timezone.utc).date().isoformat(),
        "status": "PATIENCE FLOOR EXPIRED WITH ACTIVE FORM; ONE STOPPED READ SET CAPTURED",
        "device": device,
        "authorities": {"session": bind(SESSION), "pricing": bind(PRICING),
                        "driver": bind(Path(__file__).resolve())},
        "quiet": {"required_seconds": floor,
                  "conservative_timer_start_epoch": timer_start_epoch,
                  "stopped_epoch": stopped_epoch,
                  "elapsed_lower_bound_seconds": stopped_epoch - timer_start_epoch,
                  "monitor_accesses_before_floor": 0, "screenshots_before_floor": 0,
                  "virtual_input_after_submit": 0, "screen_polls_before_floor": 0},
        "first_observation": {"kind": "owner-physical-screen-only",
                              "at_or_after_floor": True,
                              "reported": "defstruct form still active; no result or prompt"},
        "stop": {"count": 1, "already_stopped_before_reader": True,
                 "registers": registers, "PC": registers["PC"],
                 "code_owner": owner, "code_reads": code_reads,
                 "mapping": {"MAPH": registers["MAPH"],
                             "MAPL": registers["MAPL"],
                             "raw_tail": registers["tail"]}},
        "stable_record_reads": stable_records,
        "diagnostic_record": bind(record_path),
        "decoded_record": APPT.decode_record(record),
        "pre_rollback_shadow": shadow,
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
        "result": {"completion_postcondition": False,
                   "control_make_point_run": False,
                   "R_A_I_G": None, "classification_widened": False,
                   "CPU_left_stopped": True},
        "claim_limit": (
            "The priced 780-second no-observation floor expired with the form "
            "still visibly active. This proves non-completion by the operational "
            "floor, not an infinite hang. One stop and the existing full read set "
            "only; no resume, retry, or make-point control occurred."),
    }
    write_json(RECEIPT, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", choices=("capture",))
    parser.add_argument("--device", default="/dev/ttyUSB1")
    parser.add_argument("--timer-start-epoch", type=int, required=True)
    parser.add_argument("--expected-pc", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--expected-maph", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--expected-mapl", type=lambda value: int(value, 0), required=True)
    args = parser.parse_args()
    value = capture(args.device, args.timer_start_epoch, args.expected_pc,
                    args.expected_maph, args.expected_mapl)
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PatienceContactError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-v16-defstruct-patience-contact: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(1)
