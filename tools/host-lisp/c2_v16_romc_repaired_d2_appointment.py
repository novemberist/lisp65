#!/usr/bin/env python3
"""Prepare and capture the owner-authorized ROMC-repaired v1.6 D2 run.

This is deliberately a new, one-shot choreography.  It does not rewrite any
historical runner.  Staging and record arming are separate from capture so the
owner can prove the physical RUN, prompt and require result without a monitor
crossing.  Capture waits the full quiet floor before its first device access,
then stops once and reads live low memory through the monitor CPU view.
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


OWNER_COMMIT = "7de4cc6f"
PLAN = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
DEPLOY = ROOT / "build/c2.3/v1.6-defstruct-bootstrap-romc-repair/deployment.json"
REPAIR_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-bootstrap-romc-repair-receipt.json")
PHASE_B = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-b-guard-partition-receipt.json")
PHASE_C = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-c-diagnostic-preparation-receipt.json")
OUT = ROOT / (
    "build/c2.3/v1.6-defstruct-closing-session/"
    "d2-romc-repaired-bundled-appointment")
PREP_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-romc-repaired-bundled-preparation-receipt.json")
DEVICE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-romc-repaired-bundled-device-receipt.json")
RUNNER = ROOT / "scripts/c2-v16-defstruct-romc-repaired-d2-hw.sh"
DRIVER = Path(__file__).resolve()

RECORD = 0xC03F
RECORD_BYTES = 65
BOOT_WITNESS = 0xB5C3
BOOT_RESET = 0xD7
BOOT_STAMP = 0x44
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


class AppointmentError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AppointmentError(message)


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
    result = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE,
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
    at = 2 + address - int.from_bytes(raw[:2], "little")
    if at < 2 or at + size > len(raw):
        return None
    return raw[at:at + size]


def rom_path() -> Path:
    return VIEW.rom_path()


def source_candidates(logical: int, size: int) -> dict[str, bytes]:
    deployment = load(DEPLOY)
    result: dict[str, bytes] = {}
    prg = (ROOT / deployment["diagnostic"]["prg"]["path"]).read_bytes()
    resident = prg_slice(prg, logical, size)
    if resident is not None:
        result["ROMC-repaired-diagnostic-PRG"] = resident
    window = (ROOT / deployment["diagnostic"]["window"]["path"]).read_bytes()
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
    return {
        "logical_address": f"0x{logical:04x}",
        "observed": observed.hex(),
        "candidate_bytes": {name: value.hex()
                            for name, value in sorted(candidates.items())},
        "matches": matches,
        "selected_owner": matches[0] if len(matches) == 1 else "unresolved",
        "unique": len(matches) == 1,
        "symbol_interpretation_allowed": len(matches) == 1,
    }


def read_cpu_block(fd: int, logical: int, size: int) -> tuple[bytes, list[dict[str, Any]]]:
    require(0 <= logical <= 0xFFFF and logical + size <= 0x10000,
            "CPU-view block crosses logical address space")
    value = bytearray()
    rows: list[dict[str, Any]] = []
    while len(value) < size:
        count = min(16, size - len(value))
        part, evidence = VIEW.read_cpu(fd, logical + len(value), count)
        value.extend(part)
        rows.append(evidence)
    return bytes(value), rows


def record_fields() -> list[dict[str, Any]]:
    phase_b = load(PHASE_B)
    fields = phase_b["facts"]["record"]["fields"]
    require(len(fields) == 29 and phase_b["facts"]["record"]["bytes"] == 65,
            "Phase-B record contract drift")
    return fields


def decode_record(raw: bytes) -> dict[str, Any]:
    require(len(raw) == RECORD_BYTES, "record size drift")
    result: dict[str, Any] = {}
    for field in record_fields():
        if field["kind"] == "stage-tag":
            tag = raw[field["offset"]]
            result[field["name"]] = {
                "tag": f"0x{tag:02x}",
                "state": "reached" if tag == field["reached_tag"]
                else "initial" if tag == field["initial_sentinel"] else "invalid",
            }
        else:
            tag = raw[field["tag_offset"]]
            payload = raw[field["value_offset"]:
                          field["value_offset"] + field["value_bytes"]]
            result[field["name"]] = {
                "tag": f"0x{tag:02x}",
                "state": "reached" if tag == field["reached_tag"]
                else "initial" if tag == field["initial_sentinel"] else "invalid",
                "value_hex": payload.hex(),
                "value_le": int.from_bytes(payload, "little"),
            }
    return result


def runner_contract(source: str) -> dict[str, Any]:
    require("stage|arm|capture" in source, "appointment action surface drift")
    stage = source.split('if [ "$ACTION" = stage ]; then', 1)[1].split(
        'if [ "$ACTION" = arm ]; then', 1)[0]
    arm = source.split('if [ "$ACTION" = arm ]; then', 1)[1].split(
        'exec python3 "$PY" capture', 1)[0]
    require('run_m65 -H "$PRODUCT"' in stage and 'run_m65 -r' in stage,
            "verified physical staging path absent")
    last_resume = stage.rindex('run_m65 -r')
    require("screen launch-ready" in stage[last_resume:]
            and "lisp65>" in stage[last_resume:],
            "pre-owner launch-ready assertion absent")
    require("run_m65 -t" not in stage and "monitor_sync" not in stage,
            "virtual input/serial monitor leaked into physical staging")
    require('"$RESET@$record_hex"' in arm and '"$ARM@$record_hex"' in arm
            and "\n  readback " not in arm,
            "record handoff must reset+arm without reading the boot witness")
    capture_source = DRIVER.read_text(encoding="utf-8")
    body = capture_source.split("def capture(device: str)", 1)[1].split(
        "\ndef expected_facts", 1)[0]
    order = [body.index(marker) for marker in (
        "quiet_started = time.monotonic()",
        "time.sleep(QUIET_SECONDS)",
        "capture_screen()",
        "os.open(device",
        "SERIAL.monitor_sync",
        'VIEW.command(fd, b"t1"')]
    require(order == sorted(order), "first device access precedes quiet floor")
    return {
        "actions": ["stage", "arm", "capture"],
        "owner_input": ["RUN", "(require 'defstruct)",
                        "(defstruct point x y)"],
        "virtual_key_events": 0,
        "record_handoff": "canonical-reset-plus-A1-with-no-mid-session-read",
        "quiet_seconds": QUIET_SECONDS,
        "first_device_access_after_quiet_floor": True,
        "one_stop": True,
    }


def expected_facts() -> dict[str, Any]:
    owner_commit, plan = git_blob(OWNER_COMMIT, PLAN)
    text = plan.decode("utf-8")
    require("Bundled launch + D2 appointment authorized" in text
            and "visible `lisp65>` prompt" in text
            and "180-second quiet window" in text,
            "owner appointment authorization absent")
    deployment = load(DEPLOY)
    repair = load(REPAIR_RECEIPT)
    require(deployment["status"] ==
            "HOST-GREEN-NON-PROMOTABLE-ROMC-SAFE-DIAGNOSTIC"
            and deployment["promotable"] is False,
            "ROMC-safe diagnostic identity drift")
    require(repair["status"] == "HOST-GREEN DIAGNOSTIC-ONLY ROMC BOOTSTRAP REPAIR"
            and len(repair["mutations_rejected"]) == 27,
            "ROMC repair authority drift")
    for role in ("prg", "elf", "window"):
        row = deployment["diagnostic"][role]
        require(bind(ROOT / row["path"])["sha256"] == row["sha256"],
                f"diagnostic {role} binding drift")
    for row in deployment["diagnostic"]["preloads"]:
        require(bind(ROOT / row["path"])["sha256"] == row["sha256"],
                f"preload drift: {row['role']}")
    reset = (ROOT / deployment["record"]["reset"]["path"]).read_bytes()
    arm = (ROOT / deployment["record"]["arm"]["path"]).read_bytes()
    require(len(reset) == 65 and arm == b"\xa1" and reset[0] == 0x51,
            "record reset/arm authority drift")
    return {
        "owner_authority": bind_blob(f"git:{owner_commit}:{PLAN}", plan),
        "authorities": {
            "deployment": bind(DEPLOY), "repair": bind(REPAIR_RECEIPT),
            "phase_B": bind(PHASE_B), "phase_C": bind(PHASE_C),
            "driver": bind(DRIVER), "runner": bind(RUNNER),
        },
        "identity": {
            "promotable": False, "product_bytes_changed": 0,
            "diagnostic_PRG": bind(ROOT / deployment["diagnostic"]["prg"]["path"]),
            "diagnostic_ELF": bind(ROOT / deployment["diagnostic"]["elf"]["path"]),
            "diagnostic_window": bind(ROOT / deployment["diagnostic"]["window"]["path"]),
            "ROMC_clear": {"address": "0x202c", "bytes": "a2448e30d0"},
            "entry_hook": {"address": "0x2031", "routine": "0xc03f",
                           "post_state": "0x2035", "stamp": "0xb5c3=0x44"},
        },
        "record": {"address": "0xc03f", "bytes": 65, "fields": 29,
                   "reset": bind(ROOT / deployment["record"]["reset"]["path"]),
                   "arm": bind(ROOT / deployment["record"]["arm"]["path"])},
        "choreography": runner_contract(RUNNER.read_text(encoding="utf-8")),
        "read_set": {
            "CPU_view": ["PC/code-owner", "record-x3", "phase-scratch",
                         "phase-owner", "mem-oom", "gc-runs"],
            "backing_plane_oracles": ["C2J", "C2D-reset-domain", "Bank-2-source"],
            "backing_plane_note": (
                "far backing planes have no 16-bit CPU-view alias; their physical "
                "bytes are source/state oracles, never used to symbolize the stopped PC"),
            "code_owner_before_symbol_interpretation": True,
            "MAPH_MAPL_retained": True,
            "CPU_left_stopped": True,
        },
        "classification": {"rows": ["R", "A", "I", "G"],
                           "precedence": ["R", "A", "G", "I"],
                           "widening_allowed": False},
    }


def audit(value: dict[str, Any]) -> None:
    identity = value["identity"]
    choreography = value["choreography"]
    read_set = value["read_set"]
    require(not identity["promotable"] and identity["product_bytes_changed"] == 0
            and identity["ROMC_clear"]["address"] == "0x202c"
            and identity["entry_hook"]["address"] == "0x2031",
            "identity boundary drift")
    require(choreography["virtual_key_events"] == 0
            and choreography["record_handoff"] ==
                "canonical-reset-plus-A1-with-no-mid-session-read"
            and choreography["quiet_seconds"] == 180.0
            and choreography["first_device_access_after_quiet_floor"]
            and choreography["one_stop"], "quiet choreography drift")
    require(read_set["code_owner_before_symbol_interpretation"]
            and read_set["MAPH_MAPL_retained"]
            and read_set["CPU_left_stopped"]
            and value["classification"] == {
                "rows": ["R", "A", "I", "G"],
                "precedence": ["R", "A", "G", "I"],
                "widening_allowed": False}, "read/classification boundary drift")


def selftest() -> dict[str, str]:
    base = expected_facts()
    audit(base)
    cases: dict[str, tuple[list[str], Any]] = {
        "promote-diagnostic": (["identity", "promotable"], True),
        "move-hook-before-ROMC": (["identity", "entry_hook", "address"], "0x2028"),
        "virtual-input": (["choreography", "virtual_key_events"], 1),
        "read-boot-witness-mid-session":
            (["choreography", "record_handoff"], "reset-arm-readback"),
        "shorten-quiet-window": (["choreography", "quiet_seconds"], 179.9),
        "early-device-access":
            (["choreography", "first_device_access_after_quiet_floor"], False),
        "second-stop": (["choreography", "one_stop"], False),
        "symbolize-before-owner":
            (["read_set", "code_owner_before_symbol_interpretation"], False),
        "discard-MAPH-MAPL": (["read_set", "MAPH_MAPL_retained"], False),
        "resume-after-capture": (["read_set", "CPU_left_stopped"], False),
        "widen-row": (["classification", "widening_allowed"], True),
    }
    rejected: dict[str, str] = {}
    for name, (path, replacement) in cases.items():
        trial = deepcopy(base)
        cursor: Any = trial
        for part in path[:-1]:
            cursor = cursor[part]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except AppointmentError as error:
            rejected[name] = str(error)
    require(set(rejected) == set(cases), "appointment mutations escaped")
    return rejected


def prepare() -> dict[str, Any]:
    facts = expected_facts()
    rejected = selftest()
    receipt = {
        "format": "lisp65-c2.3-v1.6-defstruct-romc-repaired-bundled-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "HOST-GREEN; BUNDLED PHYSICAL APPOINTMENT PREPARED",
        "facts": facts, "mutations_rejected": rejected,
        "execution_witnesses": [
            "ROMC is cleared from low RAM before the entry hook",
            "the owner supplies RUN and both Lisp forms physically",
            "the boot witness is not read before the post-session set",
            "canonical record reset plus A1 arm occurs only after visible require=t",
            "the first device access follows the full 180-second quiet floor",
            "all live low-RAM reads use 0x0777 CPU view and retain MAPH/MAPL",
            "stopped-PC bytes obtain a unique owner before symbol interpretation",
            "far C2J/C2D/Bank-2 bytes are labelled backing-plane oracles",
            "the CPU remains stopped after the one post-event stop",
        ],
        "claim_limit": (
            "Non-promotable ROMC-repaired diagnostic appointment preparation. "
            "No product byte, measured form, device result or R/A/I/G row is claimed."),
    }
    write_json(PREP_RECEIPT, receipt)
    return receipt


def check() -> dict[str, Any]:
    facts = expected_facts()
    audit(facts)
    require(PREP_RECEIPT.is_file(), "preparation receipt absent")
    receipt = load(PREP_RECEIPT)
    require(receipt["facts"] == facts, "preparation receipt drift")
    return {"status": "PASS", "mutations": len(receipt["mutations_rejected"]),
            "device_receipt_present": DEVICE_RECEIPT.exists()}


def capture_screen() -> dict[str, Any]:
    m65 = ROOT / "tools/m65tools/m65"
    device = os.environ.get("DEVICE", "/dev/ttyUSB1")
    png = OUT / "d2-first-observation.png"
    ansi = OUT / "d2-first-observation.ansi.txt"
    command = [str(m65), "-l", device, f"--screenshot={png}"]
    process = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    require(process.returncode == 0,
            f"first observation failed: {process.stderr.decode(errors='replace')}")
    ansi.write_bytes(process.stdout)
    return {"png": bind(png), "ansi": bind(ansi)}


def physical_read(start: int, size: int, path: Path) -> dict[str, Any]:
    m65 = ROOT / "tools/m65tools/m65"
    device = os.environ.get("DEVICE", "/dev/ttyUSB1")
    end = start + size
    command = [str(m65), "-l", device, "-H", "--memsave",
               f"0x{start:08x}:0x{end:08x}={path}"]
    process = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    require(process.returncode == 0 and path.is_file() and path.stat().st_size == size,
            f"backing-plane read failed at 0x{start:08x}: "
            f"{process.stderr.decode(errors='replace')}")
    row = bind(path)
    row.update({"physical_address": f"0x{start:08x}",
                "semantics": "far-backing-plane-oracle-not-PC-symbol-view"})
    return row


def capture(device: str) -> dict[str, Any]:
    require(load(PREP_RECEIPT)["facts"] == expected_facts(),
            "preparation authority drift")
    require((OUT / "stage.ready").is_file() and (OUT / "arm.ready").is_file(),
            "stage/record-arm handoff absent")
    require(not DEVICE_RECEIPT.exists() and not (OUT / "capture.consumed").exists(),
            "bundled appointment capture is one-shot")
    (OUT / "capture.consumed").touch()
    quiet_started = time.monotonic()
    time.sleep(QUIET_SECONDS)
    quiet_elapsed = time.monotonic() - quiet_started
    require(quiet_elapsed >= QUIET_SECONDS, "quiet floor shortened")
    first_observation = capture_screen()

    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    snapshots: list[dict[str, Any]] = []
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c2v16romcsafed2\r")
        VIEW.command(fd, b"t1", 0.05)
        for index in range(STABLE_READS):
            registers = VIEW.read_registers(fd)
            pc = int(registers["PC"], 16)
            pc_size = min(CODE_PROBE, 0x10000 - pc)
            pc_bytes, pc_raw = read_cpu_block(fd, pc, pc_size)
            owner = code_owner(pc, pc_bytes)
            require(owner["unique"], "stopped PC has no unique bound code owner")
            record, record_raw = read_cpu_block(fd, RECORD, RECORD_BYTES)
            snapshots.append({
                "index": index + 1,
                "captured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "registers": registers,
                "mapping": {"MAPH": registers["MAPH"], "MAPL": registers["MAPL"],
                            "raw_tail": registers["tail"]},
                "PC": registers["PC"], "code_owner": owner,
                "PC_read": pc_raw, "record_hex": record.hex(),
                "record_read": record_raw,
            })
            if index + 1 < STABLE_READS:
                time.sleep(STABLE_SPACING)
        require(len({row["record_hex"] for row in snapshots}) == 1,
                "65-byte diagnostic record is not stable while stopped")
        record = bytes.fromhex(snapshots[0]["record_hex"])
        phase, phase_raw = read_cpu_block(fd, PHASE, PHASE_BYTES)
        phase_owner, phase_owner_raw = read_cpu_block(fd, PHASE_OWNER, 1)
        mem_oom, mem_oom_raw = read_cpu_block(fd, MEM_OOM, 1)
        gc_runs, gc_runs_raw = read_cpu_block(fd, GC_RUNS, 2)
        boot, boot_raw = read_cpu_block(fd, BOOT_WITNESS, 1)
        require(boot == bytes([BOOT_STAMP]),
                f"post-session boot witness is not 0x44: {boot.hex()}")
    finally:
        os.close(fd)

    OUT.mkdir(parents=True, exist_ok=True)
    blobs = {
        "record": (RECORD, record), "phase-scratch": (PHASE, phase),
        "first-error": (PHASE + FIRST_ERROR_OFFSET,
                        phase[FIRST_ERROR_OFFSET:FIRST_ERROR_OFFSET + 2]),
        "phase-owner": (PHASE_OWNER, phase_owner), "mem-oom": (MEM_OOM, mem_oom),
        "gc-runs": (GC_RUNS, gc_runs), "boot-witness": (BOOT_WITNESS, boot),
    }
    cpu_captures: dict[str, Any] = {}
    for name, (address, raw) in blobs.items():
        path = OUT / f"post-{name}.bin"
        path.write_bytes(raw)
        row = bind(path)
        row.update({"logical_address": f"0x{address:04x}",
                    "view": "CPU-resolved-0x0777xxxx"})
        cpu_captures[name] = row

    # These far planes have no 16-bit CPU-view alias.  They are read only after
    # the single stop and are retained as source/state oracles, never as the
    # stopped instruction owner.
    backing = {
        "C2J": physical_read(C2J, C2J_BYTES, OUT / "post-c2j.bin"),
        "C2D": physical_read(C2D, C2D_BYTES, OUT / "post-c2d-reset-domain.bin"),
        "Bank-2": physical_read(BANK2, BANK2_BYTES, OUT / "post-bank2-source.bin"),
    }
    decoded = decode_record(record)
    receipt = {
        "format": "lisp65-c2.3-v1.6-defstruct-romc-repaired-bundled-device-v1",
        "recorded_on": date.today().isoformat(),
        "status": "STOPPED-STATE-CAPTURED; R/A/I/G CLASSIFICATION PENDING ORACLE DECODE",
        "device": device,
        "authorities": {"preparation": bind(PREP_RECEIPT), "driver": bind(DRIVER),
                        "runner": bind(RUNNER), "deployment": bind(DEPLOY)},
        "quiet": {"required_seconds": QUIET_SECONDS,
                  "observed_seconds": quiet_elapsed,
                  "device_accesses_during_window": 0},
        "first_observation": first_observation,
        "snapshots": snapshots,
        "CPU_view_captures": cpu_captures,
        "CPU_view_raw": {"phase": phase_raw, "phase_owner": phase_owner_raw,
                         "mem_oom": mem_oom_raw, "gc_runs": gc_runs_raw,
                         "boot": boot_raw},
        "backing_plane_oracles": backing,
        "decoded_record": decoded,
        "result": {"boot_witness": "0x44", "record_stable_reads": 3,
                   "CPU_left_stopped": True, "R_A_I_G": None,
                   "classification_widened": False},
        "claim_limit": (
            "One owner-authorized quiet measured form and its stable stopped-state "
            "read set. Classification remains unset until the last-fill source "
            "oracle is decoded; no row is widened and the CPU remains stopped."),
    }
    write_json(DEVICE_RECEIPT, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "check", "selftest", "capture"))
    parser.add_argument("--device", default=os.environ.get("DEVICE", "/dev/ttyUSB1"))
    args = parser.parse_args()
    if args.action == "prepare":
        value = prepare()
    elif args.action == "check":
        value = check()
    elif args.action == "selftest":
        value = {"status": "PASS", "mutations_rejected": selftest()}
    else:
        value = capture(args.device)
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AppointmentError as error:
        print(f"c2-v16-romc-repaired-d2-appointment: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
