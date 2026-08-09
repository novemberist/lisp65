#!/usr/bin/env python3
"""Prepare and run the owner-authorized mapping-aware v1.6 boot ladder.

The contact is deliberately limited to the launch boundary.  It waits through
the bound quiet floor, samples the running machine three times with stop/resume
spacing, proves the instruction owner in CPU view, and reads every state byte
from physical Bank-0 RAM only after capturing the mapping row at the same stop.
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
import c2_v16_romc_repaired_d2_appointment as APPT  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


OWNER_COMMIT = "f072b72d"
PLAN = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
MAPPING_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mapping-aware-data-boot-gc-receipt.json")
REPAIR_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-bootstrap-romc-repair-receipt.json")
DEPLOY = ROOT / "build/c2.3/v1.6-defstruct-bootstrap-romc-repair/deployment.json"
ELF = ROOT / (
    "build/c2.3/v1.6-defstruct-bootstrap-romc-repair/artifacts/"
    "diagnostic-link82-romc-safe.elf")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OUT = ROOT / (
    "build/c2.3/v1.6-defstruct-closing-session/"
    "d2-mapping-aware-full-ladder-appointment")
SENTINEL = OUT / "durable-witness-reset.bin"
PREP_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mapping-aware-full-ladder-preparation-receipt.json")
DEVICE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mapping-aware-full-ladder-device-receipt.json")
RUNNER = ROOT / "scripts/c2-v16-defstruct-full-ladder-hw.sh"
DRIVER = Path(__file__).resolve()

WITNESS = 0xB5C3
RESET = 0xD7
STAMP = 0x44
ALLOC_HIGH = 0x0039
GC_FROZEN = 0x003B
FREELIST = 0x003D
GC_RUNS = 0xB9F0
GC_CONTEXT = 0x0016
GC_CONTEXT_BYTES = 10
HEAP_CELLS = 48
EXT_CELLS = 1024
SAMPLES = 3
SPACING_SECONDS = 5.0
QUIET_SECONDS = 27.653
CODE_BYTES = 16


class LadderError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise LadderError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
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


def materialize() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SENTINEL.write_bytes(bytes([RESET]))


def mapping_snapshot(registers: dict[str, Any]) -> dict[str, Any]:
    maph = int(registers["MAPH"], 16)
    mapl = int(registers["MAPL"], 16)
    tail = registers["tail"]
    # This is the mapping state closed by the accepted desk receipt.  A new
    # state is not guessed through: it is a view-protocol First Red.
    require(maph == 0x8000 and mapl == 0x0000,
            f"mapping outside closed translation: MAPH={maph:04x} MAPL={mapl:04x}")
    require("lhc" in tail.casefold() and "c" in tail.casefold(),
            "ROM/CPU-port fields absent from stopped mapping row")
    return {
        "MAPH": f"0x{maph:04x}", "MAPL": f"0x{mapl:04x}",
        "raw_tail": tail, "map_selected_8k_blocks": ["0xe000-0xffff"],
        "bank0_data_translation": "logical low16 -> physical 0x0000xxxx",
    }


def read_physical(fd: int, logical: int, size: int) -> tuple[bytes, list[dict[str, Any]]]:
    require(0 <= logical <= 0xFFFF and logical + size <= 0x10000,
            "physical Bank-0 read crosses low16")
    result = bytearray()
    rows: list[dict[str, Any]] = []
    while len(result) < size:
        address = logical + len(result)
        count = min(16, size - len(result))
        raw = VIEW.command(fd, f"m{address:08x}".encode())
        value = VIEW.parse_memory(raw, address, count)
        result.extend(value)
        rows.append({
            "command": f"m{address:08x}",
            "logical_address": f"0x{address:04x}",
            "physical_RAM_address": f"0x{address:08x}",
            "view": "physical-bank0-RAM-underlay",
            "raw_hex": raw.hex(),
        })
    return bytes(result), rows


def screen_capture(name: str) -> dict[str, Any]:
    m65 = ROOT / "tools/m65tools/m65"
    device = os.environ.get("DEVICE", "/dev/ttyUSB1")
    png = OUT / f"{name}.png"
    ansi = OUT / f"{name}.ansi.txt"
    text_path = OUT / f"{name}.txt"
    result = subprocess.run(
        [str(m65), "-l", device, f"--screenshot={png}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0,
            f"screen capture failed: {result.stderr.decode(errors='replace')}")
    ansi.write_bytes(result.stdout)
    text = re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "",
                  result.stdout.decode(errors="replace"))
    text_path.write_text(text, encoding="utf-8")
    return {"png": bind(png), "ansi": bind(ansi), "text": bind(text_path),
            "visible_prompt": "lisp65>" in text.casefold()}


def ext_occupancy(alloc_high: int) -> int:
    if alloc_high < HEAP_CELLS:
        return 0
    return min(EXT_CELLS, alloc_high - HEAP_CELLS + 1)


def sample(fd: int, index: int) -> dict[str, Any]:
    registers = VIEW.read_registers(fd)
    mapping = mapping_snapshot(registers)
    pc = int(registers["PC"], 16)
    code, code_read = APPT.read_cpu_block(fd, pc, min(CODE_BYTES, 0x10000 - pc))
    owner = APPT.code_owner(pc, code)
    require(owner["unique"], "stopped PC has no unique active code owner")
    values: dict[str, tuple[int, bytes, list[dict[str, Any]]]] = {}
    for name, address, size in (
        ("boot_witness", WITNESS, 1), ("gc_runs", GC_RUNS, 2),
        ("freelist", FREELIST, 2), ("alloc_high", ALLOC_HIGH, 2),
        ("gc_frozen", GC_FROZEN, 2),
        ("gc_context", GC_CONTEXT, GC_CONTEXT_BYTES),
    ):
        raw, evidence = read_physical(fd, address, size)
        values[name] = (address, raw, evidence)
    high = int.from_bytes(values["alloc_high"][1], "little")
    return {
        "sample": index,
        "captured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "registers": registers, "mapping": mapping, "PC": registers["PC"],
        "code_owner": owner, "code_read": code_read,
        "boot_witness": f"0x{values['boot_witness'][1][0]:02x}",
        "gc_runs": int.from_bytes(values["gc_runs"][1], "little"),
        "freelist_head": f"0x{int.from_bytes(values['freelist'][1], 'little'):04x}",
        "alloc_high": high, "gc_frozen": int.from_bytes(
            values["gc_frozen"][1], "little"),
        "EXT_occupancy": ext_occupancy(high),
        "GC_context": values["gc_context"][1].hex(),
        "physical_data_reads": {name: evidence for name, (_, _, evidence)
                                in values.items()},
    }


def in_collection(pc: int, facts: dict[str, Any]) -> bool:
    return any(int(row["start"], 16) <= pc < int(row["end_exclusive"], 16)
               for row in facts["collection_intervals"])


def classify(samples: list[dict[str, Any]], prompt: bool,
             facts: dict[str, Any]) -> str:
    if prompt:
        return "BOOT-PROGRESSED-TO-VISIBLE-PROMPT"
    stamps = [int(row["boot_witness"], 16) for row in samples]
    if any(value != STAMP for value in stamps):
        return "BOOT-ENTRY-IDENTITY-FIRST-RED"
    if not all(row["code_owner"]["selected_owner"] in {
            "ROMC-repaired-diagnostic-PRG", "diagnostic-E000-window"}
            for row in samples):
        return "CODE-OWNER-FIRST-RED"
    pcs = [int(row["PC"], 16) for row in samples]
    state = [(
        row["PC"], row["gc_runs"], row["freelist_head"],
        row["alloc_high"], row["gc_frozen"], row["EXT_occupancy"],
        row["GC_context"], row["registers"]["X"], row["registers"]["Y"],
    ) for row in samples]
    # The owner row requires two equal, temporally separated collection
    # samples.  Three are taken so the equality is witnessed rather than
    # inferred from a single repeated stop.
    if all(in_collection(pc, facts) for pc in pcs) and len(set(state)) < len(state):
        return "STALLED-IN-SINGLE-COLLECTION"
    if len(set(state)) > 1:
        return "TEMPORAL-PROGRESS-WITHOUT-VISIBLE-PROMPT"
    return "FIRST-RED-OUTSIDE-PREBOUND-ROWS"


def facts() -> dict[str, Any]:
    owner, plan = git_blob(OWNER_COMMIT, PLAN)
    text = plan.decode("utf-8")
    require("Full-ladder contact authorized" in text
            and "Two identical spaced samples inside the collection" in text
            and "Progress to a visible prompt" in text,
            "owner full-ladder authority absent")
    mapping = load(MAPPING_RECEIPT)
    require(mapping["status"] ==
            "HOST-GREEN; DATA-VIEW-CLOSED; PRE-PROMPT-GC-EXCLUDED",
            "mapping/boot-GC authority drift")
    census = mapping["facts"]["static_boot_GC"]["allocation_census"]
    require(census["total_before_first_prompt"] == 341
            and census["EXT_first_capacity"] == EXT_CELLS
            and census["remaining_cells"] == 683,
            "341/1024/683 boot census drift")
    repair = load(REPAIR_RECEIPT)
    require(repair["status"] ==
            "HOST-GREEN DIAGNOSTIC-ONLY ROMC BOOTSTRAP REPAIR",
            "ROMC repair authority drift")
    deployment = load(DEPLOY)
    require(deployment["promotable"] is False,
            "diagnostic identity became promotable")
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    symbols = {name: truth.symbol(name) for name in (
        "gc_collect", "c2_product_gc_mark_roots", "freelist", "gc_runs",
        "alloc_high", "gc_frozen")}
    require((symbols["freelist"].value, symbols["gc_runs"].value,
             symbols["alloc_high"].value, symbols["gc_frozen"].value) ==
            (FREELIST, GC_RUNS, ALLOC_HIGH, GC_FROZEN),
            "ladder state-symbol identity drift")
    return {
        "owner": bind_blob(f"git:{owner}:{PLAN}", plan),
        "identity": {"deployment": bind(DEPLOY), "ELF": bind(ELF),
                     "promotable": False, "product_bytes_changed": 0},
        "view_protocol": {
            "mapping_captured_before_every_data_read": True,
            "closed_mapping": {"MAPH": "0x8000", "MAPL": "0x0000"},
            "code": "CPU-view bytes then unique active-owner binding",
            "data": "captured mapping then physical Bank-0 translation",
        },
        "boot_census": {"allocated": 341, "capacity": 1024, "free": 683},
        "state_addresses": {
            "witness": "0xb5c3", "gc_runs": "0xb9f0",
            "freelist": "0x003d", "alloc_high": "0x0039",
            "gc_frozen": "0x003b", "GC_context": "0x0016..0x001f",
        },
        "collection_intervals": [
            {"name": name, "start": f"0x{symbols[name].value:04x}",
             "end_exclusive": f"0x{symbols[name].value + symbols[name].bytes:04x}"}
            for name in ("gc_collect", "c2_product_gc_mark_roots")
        ],
        "appointment": {
            "cold_reset": True, "physical_RUN": True,
            "quiet_floor_seconds": QUIET_SECONDS, "samples": SAMPLES,
            "spacing_seconds": SPACING_SECONDS, "measured_forms_before_prompt": 0,
            "CPU_left_stopped": True,
        },
        "decision_rows": {
            "stable_collection": "STALLED-IN-SINGLE-COLLECTION",
            "visible_prompt": "BOOT-PROGRESSED-TO-VISIBLE-PROMPT",
            "unstamped_post_entry": "BOOT-ENTRY-IDENTITY-FIRST-RED",
            "changing_without_prompt": "TEMPORAL-PROGRESS-WITHOUT-VISIBLE-PROMPT",
        },
    }


def audit(value: dict[str, Any]) -> None:
    view = value["view_protocol"]
    appt = value["appointment"]
    rows = value["decision_rows"]
    require(view["mapping_captured_before_every_data_read"]
            and "physical Bank-0" in view["data"]
            and "unique active-owner" in view["code"],
            "mapping/code view protocol drift")
    require(appt == {
        "cold_reset": True, "physical_RUN": True,
        "quiet_floor_seconds": QUIET_SECONDS, "samples": 3,
        "spacing_seconds": 5.0, "measured_forms_before_prompt": 0,
        "CPU_left_stopped": True,
    }, "appointment boundary drift")
    require(rows["stable_collection"] == "STALLED-IN-SINGLE-COLLECTION"
            and rows["visible_prompt"] == "BOOT-PROGRESSED-TO-VISIBLE-PROMPT"
            and rows["unstamped_post_entry"] ==
                "BOOT-ENTRY-IDENTITY-FIRST-RED",
            "decision-row drift")
    require(value["boot_census"] == {"allocated": 341, "capacity": 1024,
                                      "free": 683}, "boot census drift")


def selftest() -> dict[str, Any]:
    base = facts()
    cases: dict[str, tuple[list[Any], Any]] = {
        "drop-mapping-capture": (["view_protocol", "mapping_captured_before_every_data_read"], False),
        "raw-ROM-data": (["view_protocol", "data"], "CPU view is data truth"),
        "physical-code-owner": (["view_protocol", "code"], "physical underlay"),
        "virtual-RUN": (["appointment", "physical_RUN"], False),
        "short-quiet": (["appointment", "quiet_floor_seconds"], 1.0),
        "one-sample": (["appointment", "samples"], 1),
        "zero-spacing": (["appointment", "spacing_seconds"], 0.0),
        "run-form-early": (["appointment", "measured_forms_before_prompt"], 1),
        "resume-final": (["appointment", "CPU_left_stopped"], False),
        "change-boot-count": (["boot_census", "allocated"], 340),
        "change-capacity": (["boot_census", "capacity"], 4096),
        "widen-stable-row": (["decision_rows", "stable_collection"], "GC-BUG"),
        "widen-prompt-row": (["decision_rows", "visible_prompt"], "R"),
        "claim-identity-as-product": (["decision_rows", "unstamped_post_entry"], "PRODUCT-HANG"),
    }
    rejected: dict[str, str] = {}
    for name, (path, replacement) in cases.items():
        trial = deepcopy(base)
        cursor: Any = trial
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except LadderError as error:
            rejected[name] = str(error)
        else:
            raise LadderError(f"mutation survived: {name}")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "rejected": rejected}


def expected_preparation() -> dict[str, Any]:
    value = facts()
    audit(value)
    return {
        "format": "lisp65-c2.3-v1.6-mapping-aware-full-ladder-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "HOST-GREEN; ONE FULL-LADDER CONTACT AUTHORIZED",
        "authorities": {
            "owner": value.pop("owner"), "mapping_boot_GC": bind(MAPPING_RECEIPT),
            "ROMC_repair": bind(REPAIR_RECEIPT), "driver": bind(DRIVER),
            "runner": bind(RUNNER),
        },
        "facts": value, "mutations_rejected": selftest()["rejected"],
        "claim_limit": (
            "One physical launch ladder under the mapping-aware protocol. No "
            "pre-prompt form, product fix, Link or R/A/I/G result is claimed; "
            "the CPU remains stopped after the final ladder sample."),
    }


def capture(device: str) -> dict[str, Any]:
    require(load(PREP_RECEIPT) == expected_preparation(),
            "full-ladder preparation receipt drift")
    require((OUT / "stage.ready").is_file(), "full-ladder stage handoff absent")
    require(not DEVICE_RECEIPT.exists() and not (OUT / "capture.consumed").exists(),
            "full-ladder contact is one-shot")
    (OUT / "capture.consumed").touch()
    started = time.monotonic()
    time.sleep(QUIET_SECONDS)
    elapsed = time.monotonic() - started
    require(elapsed >= QUIET_SECONDS, "quiet floor shortened")
    first_screen = screen_capture("boot-ladder-first-observation")
    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    samples: list[dict[str, Any]] = []
    try:
        SERIAL.configure_serial(fd)
        for index in range(SAMPLES):
            SERIAL.monitor_sync(fd, f"#c2v16fullladder{index}\r".encode())
            VIEW.command(fd, b"t1", 0.05)
            samples.append(sample(fd, index + 1))
            if index + 1 < SAMPLES:
                VIEW.command(fd, b"t0", 0.03)
                time.sleep(SPACING_SECONDS)
        # Final state deliberately remains stopped.
    finally:
        os.close(fd)
    prepared = load(PREP_RECEIPT)
    status = classify(samples, first_screen["visible_prompt"], prepared["facts"])
    receipt = {
        "format": "lisp65-c2.3-v1.6-mapping-aware-full-ladder-device-v1",
        "recorded_on": date.today().isoformat(), "status": status,
        "device": device,
        "authorities": {"preparation": bind(PREP_RECEIPT),
                        "driver": bind(DRIVER), "runner": bind(RUNNER)},
        "quiet": {"required_seconds": QUIET_SECONDS,
                  "observed_seconds": elapsed, "early_monitor_accesses": 0},
        "first_observation": first_screen, "samples": samples,
        "result": {"classification": status, "CPU_left_stopped": True,
                   "measured_forms_run": 0, "R_A_I_G": None},
        "claim_limit": prepared["claim_limit"],
    }
    write_json(DEVICE_RECEIPT, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "check", "selftest", "capture"))
    parser.add_argument("--device", default=os.environ.get("DEVICE", "/dev/ttyUSB1"))
    args = parser.parse_args()
    materialize()
    if args.action == "prepare":
        value = expected_preparation()
        write_json(PREP_RECEIPT, value)
    elif args.action == "check":
        value = expected_preparation()
        require(load(PREP_RECEIPT) == value, "full-ladder preparation receipt drift")
        value = {"status": "PASS", "mutations": len(value["mutations_rejected"]),
                 "device_receipt_present": DEVICE_RECEIPT.exists()}
    elif args.action == "selftest":
        value = selftest()
    else:
        value = capture(args.device)
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (LadderError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"c2-v16-full-ladder: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
