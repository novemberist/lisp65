#!/usr/bin/env python3
"""Capture the pre-registered ROMC-safe D2 launch-failure branch.

The owner observed no prompt and no monitor after several minutes.  The
appointment contract says that branch ends at launch: no measured form, one
stop, bound captures, CPU left stopped.  This tool is intentionally separate
from the successful-launch D2 capture so it cannot accidentally arm or run the
R/A/I/G measurement.
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
import c2_v16_romc_repaired_d2_appointment as APPT  # noqa: E402


OWNER_COMMIT = "7de4cc6f"
PLAN = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
OUT = APPT.OUT
PREPARATION = APPT.PREP_RECEIPT
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-romc-repaired-launch-failure-device-receipt.json")
PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-romc-repaired-launch-failure-capture-preparation.json")
DRIVER = Path(__file__).resolve()


class CaptureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CaptureError(message)


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
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write(path: Path, value: dict[str, Any]) -> None:
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


def expected() -> dict[str, Any]:
    commit, plan = git_blob(OWNER_COMMIT, PLAN)
    text = plan.decode("utf-8")
    require("If the launch fails again, the appointment ends there honestly" in text
            and "no improvisation, CPU stopped, captures bound" in text,
            "launch-failure capture authorization absent")
    prep = load(PREPARATION)
    require(prep["status"] == "HOST-GREEN; BUNDLED PHYSICAL APPOINTMENT PREPARED"
            and prep["facts"]["identity"]["entry_hook"]["address"] == "0x2031",
            "bundled preparation authority drift")
    require((OUT / "stage.ready").is_file()
            and not (OUT / "arm.ready").exists(),
            "launch-failure branch requires staged but unarmed identity")
    payload = OUT / "diagnostic-prg-payload.bin"
    deployment = load(APPT.DEPLOY)
    product = ROOT / deployment["diagnostic"]["prg"]["path"]
    require(payload.read_bytes() == product.read_bytes()[2:],
            "staged resident payload is not the ROMC-repaired identity")
    preload_rows = []
    for row in deployment["diagnostic"]["preloads"]:
        path = OUT / f"preload-{row['role']}.bin"
        require(path.read_bytes() == (ROOT / row["path"]).read_bytes(),
                f"staged preload drift: {row['role']}")
        preload_rows.append(bind(path))
    return {
        "owner_authority": {
            "path": f"git:{commit}:{PLAN}", "bytes": len(plan),
            "sha256": digest(plan)},
        "preparation": bind(PREPARATION),
        "driver": bind(DRIVER),
        "staging": {"resident_payload": bind(payload),
                    "preloads": preload_rows,
                    "fresh_BASIC": bind(OUT / "fresh-basic.txt"),
                    "launch_ready": bind(OUT / "launch-ready.txt")},
        "branch": {
            "visible_prompt": False, "measured_forms": 0,
            "record_armed": False, "R_A_I_G_claim": False,
            "first_action": "screenshot-before-one-stop",
            "one_stop": True, "CPU_view": True,
            "MAPH_MAPL_retained": True,
            "code_owner_before_symbol_interpretation": True,
            "CPU_left_stopped": True, "reset_or_resume": False,
        },
    }


def audit(value: dict[str, Any]) -> None:
    branch = value["branch"]
    require(branch == {
        "visible_prompt": False, "measured_forms": 0,
        "record_armed": False, "R_A_I_G_claim": False,
        "first_action": "screenshot-before-one-stop",
        "one_stop": True, "CPU_view": True,
        "MAPH_MAPL_retained": True,
        "code_owner_before_symbol_interpretation": True,
        "CPU_left_stopped": True, "reset_or_resume": False,
    }, "launch-failure claim/capture boundary drift")


def selftest() -> dict[str, str]:
    base = expected()
    audit(base)
    cases: dict[str, tuple[str, Any]] = {
        "run-form": ("measured_forms", 1),
        "arm-record": ("record_armed", True),
        "claim-row": ("R_A_I_G_claim", True),
        "skip-screen": ("first_action", "t1"),
        "second-stop": ("one_stop", False),
        "physical-view": ("CPU_view", False),
        "drop-mapping": ("MAPH_MAPL_retained", False),
        "symbolize-first": ("code_owner_before_symbol_interpretation", False),
        "resume": ("CPU_left_stopped", False),
        "reset": ("reset_or_resume", True),
    }
    rejected: dict[str, str] = {}
    for name, (key, replacement) in cases.items():
        trial = deepcopy(base)
        trial["branch"][key] = replacement
        try:
            audit(trial)
        except CaptureError as error:
            rejected[name] = str(error)
    require(set(rejected) == set(cases), "launch-failure mutations escaped")
    return rejected


def prepare() -> dict[str, Any]:
    facts = expected()
    rejected = selftest()
    receipt = {
        "format": "lisp65-c2.3-v1.6-romc-launch-failure-capture-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "HOST-GREEN LAUNCH-FAILURE CAPTURE PREPARED",
        "facts": facts, "mutations_rejected": rejected,
        "claim_limit": (
            "Read-only closure of the pre-registered failed-launch branch: "
            "screen, one stop, CPU-view state and code owner. No form, reset, "
            "resume, product claim or R/A/I/G result."),
    }
    write(PREP, receipt)
    return receipt


def screen(device: str) -> dict[str, Any]:
    png = OUT / "launch-failure-first-observation.png"
    ansi = OUT / "launch-failure-first-observation.ansi.txt"
    m65 = ROOT / "tools/m65tools/m65"
    result = subprocess.run([str(m65), "-l", device, f"--screenshot={png}"],
                            cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    require(result.returncode == 0,
            f"launch-failure screenshot failed: {result.stderr.decode(errors='replace')}")
    ansi.write_bytes(result.stdout)
    return {"png": bind(png), "ansi": bind(ansi)}


def capture(device: str) -> dict[str, Any]:
    require(load(PREP)["facts"] == expected(), "capture preparation drift")
    require(not RECEIPT.exists(), "launch-failure capture is one-shot")
    first = screen(device)
    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c2v16romclaunchfail\r")
        VIEW.command(fd, b"t1", 0.05)
        registers = VIEW.read_registers(fd)
        pc = int(registers["PC"], 16)
        pc_bytes, pc_read = APPT.read_cpu_block(
            fd, pc, min(APPT.CODE_PROBE, 0x10000 - pc))
        owner = APPT.code_owner(pc, pc_bytes)
        require(owner["unique"], "launch-failure PC owner is ambiguous")
        witness, witness_read = APPT.read_cpu_block(fd, APPT.BOOT_WITNESS, 1)
        record, record_read = APPT.read_cpu_block(fd, APPT.RECORD, APPT.RECORD_BYTES)
        phase, phase_read = APPT.read_cpu_block(fd, APPT.PHASE, APPT.PHASE_BYTES)
        phase_owner, owner_read = APPT.read_cpu_block(fd, APPT.PHASE_OWNER, 1)
        gc_runs, gc_read = APPT.read_cpu_block(fd, APPT.GC_RUNS, 2)
    finally:
        os.close(fd)
    captures: dict[str, Any] = {}
    for name, address, raw in (
        ("boot-witness", APPT.BOOT_WITNESS, witness),
        ("record", APPT.RECORD, record),
        ("phase-scratch", APPT.PHASE, phase),
        ("first-error", APPT.PHASE + APPT.FIRST_ERROR_OFFSET,
         phase[APPT.FIRST_ERROR_OFFSET:APPT.FIRST_ERROR_OFFSET + 2]),
        ("phase-owner", APPT.PHASE_OWNER, phase_owner),
        ("gc-runs", APPT.GC_RUNS, gc_runs),
    ):
        path = OUT / f"launch-failure-{name}.bin"
        path.write_bytes(raw)
        row = bind(path)
        row.update({"logical_address": f"0x{address:04x}",
                    "view": "CPU-resolved-0x0777xxxx"})
        captures[name] = row
    receipt = {
        "format": "lisp65-c2.3-v1.6-romc-repaired-launch-failure-device-v1",
        "recorded_on": date.today().isoformat(),
        "status": "LAUNCH FAILED BEFORE VISIBLE PROMPT; STOPPED CAPTURE BOUND",
        "authorities": {"preparation": bind(PREP), "driver": bind(DRIVER)},
        "first_observation": first,
        "registers": registers,
        "mapping": {"MAPH": registers["MAPH"], "MAPL": registers["MAPL"],
                    "raw_tail": registers["tail"]},
        "PC": registers["PC"], "code_owner": owner,
        "PC_read": pc_read, "CPU_view_captures": captures,
        "CPU_view_raw": {"witness": witness_read, "record": record_read,
                         "phase": phase_read, "phase_owner": owner_read,
                         "gc_runs": gc_read},
        "summary": {
            "boot_witness": f"0x{witness[0]:02x}",
            "record_armed": record[0] == 0xA1,
            "first_error_hex": phase[APPT.FIRST_ERROR_OFFSET:
                                     APPT.FIRST_ERROR_OFFSET + 2].hex(),
            "phase_owner": phase_owner[0],
            "gc_runs": int.from_bytes(gc_runs, "little"),
            "measured_forms": 0, "R_A_I_G": None,
            "CPU_left_stopped": True,
        },
        "claim_limit": (
            "The ROMC-repaired diagnostic did not expose a visible prompt in "
            "the owner-observed launch window. This read-only packet names only "
            "the stopped launch boundary; no product or R/A/I/G claim."),
    }
    write(RECEIPT, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "check", "selftest", "capture"))
    parser.add_argument("--device", default=os.environ.get("DEVICE", "/dev/ttyUSB1"))
    args = parser.parse_args()
    if args.action == "prepare":
        value = prepare()
    elif args.action == "check":
        require(load(PREP)["facts"] == expected(), "preparation drift")
        value = {"status": "PASS", "device_receipt_present": RECEIPT.exists()}
    elif args.action == "selftest":
        value = {"status": "PASS", "mutations_rejected": selftest()}
    else:
        value = capture(args.device)
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CaptureError as error:
        print(f"c2-v16-romc-launch-failure-capture: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
