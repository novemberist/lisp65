#!/usr/bin/env python3
"""Capture and bind the autonomous Link-107 CPU-transport ring contact."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402
import c2_v16_corrected_view_contact as VIEW  # noqa: E402
import c2_v20_loading_libraries_progress_map_contact as OLD  # noqa: E402
import c2_v20_loading_libraries_progress_ring as RING  # noqa: E402
import c2_v21_loading_libraries_progress_rebind as REBIND  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.3/v2.1-loading-libraries-progress/contact"
CAPTURE = OUT / "raw-capture.json"
RESULT = OUT / "result.json"
RECEIPT = ARCH / "c2.3-v2.1-loading-libraries-progress-device-receipt.json"
DEVICE = os.environ.get("DEVICE", "/dev/ttyUSB1")
FORMAT = "lisp65-c2.3-v2.1-loading-libraries-progress-device-v1"
FRAME_HZ = 51.966
SAMPLE_FRAMES = 2048
EXPECTED_READS = 346_298


class ContactError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ContactError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(canonical(value))
    temporary.replace(path)


def preflight() -> dict[str, Any]:
    ring = REBIND.check()
    session = load(REBIND.SESSION)
    require(
        ring["contact"] == {"authorized": True, "class": "B",
            "owner_keyboard_required": False, "quiet_seconds": 180,
            "active_observations": 0, "final_stops": 1,
            "CPU_left_stopped": True, "D1_D5_open": False}
        and session["authorization"] == {"contact_authorized": True,
            "class": "B", "owner_keyboard_required": False,
            "D1_D5_open": False}
        and session["active_interval"]["quiet_seconds"] == 180,
        "Link-107 progress contact authorization drift")
    return {"ring_receipt": bind(REBIND.RECEIPT),
            "session": bind(REBIND.SESSION),
            "product_D81": bind(REBIND.DIAG_D81),
            "library_D81": bind(REBIND.LIBRARY_D81)}


def capture() -> dict[str, Any]:
    authority = preflight()
    require(Path(DEVICE).is_char_device(), f"serial device absent: {DEVICE}")
    OUT.mkdir(parents=True, exist_ok=True)
    raw_log = OUT / "monitor-raw.ndjson"
    raw_log.write_bytes(b"")
    fd = os.open(DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        stop_raw = VIEW.command(fd, b"t1", 0.08)
        OLD.append_raw(raw_log, "sole-final-stop", "t1", stop_raw)
        register_raw = VIEW.command(fd, b"r", 0.05)
        OLD.append_raw(raw_log, "register-tuple", "r", register_raw)
        registers = VIEW.parse_registers(register_raw)
        state = OLD.read_range(fd, 0x0000B582, 66, raw_log)
        frames = OLD.read_range(fd, 0x0000FF83, 2, raw_log)
    finally:
        os.close(fd)
    (OUT / "progress-state.bin").write_bytes(state)
    (OUT / "frame-counter.bin").write_bytes(frames)
    value = {
        "format": FORMAT + "-raw", "captured_on": "2026-08-15",
        "authority": authority, "device": DEVICE,
        "discipline": {"active_observations": 0,
            "target_sampler_only": True, "stops": 1, "resumes": 0,
            "runs_after_mount": 0, "tuple_before_data": True,
            "raw_persisted_before_interpretation": True,
            "same_stopped_session": True, "CPU_left_stopped": True,
            "D1_D5_executed": False},
        "tuple": registers, "state_hex": state.hex(),
        "frame_counter_hex": frames.hex(), "raw_log": bind(raw_log),
        "claim_limit": (
            "Raw-first stopped-state capture only; classification is owned "
            "by the result binder."),
    }
    write_json(CAPTURE, value)
    return value


def classify(capture_value: dict[str, Any]) -> dict[str, Any]:
    state = bytes.fromhex(capture_value["state_hex"])
    frames = bytes.fromhex(capture_value["frame_counter_hex"])
    require(len(state) == 66 and len(frames) == 2,
            "Link-107 captured range extent drift")
    require(state[11] == RING.ARM_VALUE and state[64:66] == b"\xd7\xd7",
            "Link-107 ring state/reset tail drift")
    final_frame = int.from_bytes(frames, "little")
    slots = RING.accepted_slots(state[12:64], frames[1])
    require(len(slots) == 4, f"Link-107 committed ring slots: {len(slots)}")
    intervals: list[dict[str, Any]] = []
    for newer, older in zip(slots, slots[1:]):
        delta = (newer["counter"] - older["counter"]) & 0xFFFFFFFF
        seconds = SAMPLE_FRAMES / FRAME_HZ
        intervals.append({"newer_offset": newer["offset"],
            "older_offset": older["offset"], "counter_delta": delta,
            "seconds": seconds, "reads_per_second": delta / seconds})
    newest = slots[0]
    completed = newest["counter"] >= EXPECTED_READS
    growing = any(row["counter_delta"] > 0 for row in intervals)
    decision = "COMPLETE" if completed else "LIVE" if growing else "FIXED"
    ring = {"final_frame": final_frame, "slots_newest_first": slots,
        "intervals_newest_first": intervals,
        "newest_counter": newest["counter"],
        "expected_reads": EXPECTED_READS, "completed": completed,
        "decision": decision, "newest_phase": f"0x{newest['phase']:02x}",
        "newest_image": newest["image"],
        "newest_entry_or_publication": newest["entry_or_publication"],
        "newest_descriptor_ordinal": newest["descriptor_ordinal"],
        "newest_transport": {"value": newest["transport"],
            "meaning": {0: "C2D / Bank 5", 1: "Shelf / Attic"}.get(
                newest["transport"], "unknown")},
        "fixed_observation_seconds": 0.0 if growing else
            3 * SAMPLE_FRAMES / FRAME_HZ}
    positive = [row["reads_per_second"] for row in intervals
                if row["counter_delta"] > 0]
    if positive:
        rate = sum(positive) / len(positive)
        ring["observed_reads_per_second"] = rate
        ring["projected_seconds_for_346298_reads"] = EXPECTED_READS / rate
        ring["projected_minutes_for_346298_reads"] = EXPECTED_READS / rate / 60
    return ring


def stopped_identity(tuple_value: dict[str, Any]) -> dict[str, Any]:
    pc = int(tuple_value["PC"], 0)
    truth = ElfTruth.read(REBIND.DIAG_ELF, llvm_readobj=REBIND.READOBJ,
                          include_section_data=True)
    sections = [row for row in truth.sections
                if row.address <= pc < row.address + row.bytes]
    section = sections[0].name if sections else None
    symbols = [row for row in truth.symbols
               if row.value <= pc < row.value + max(row.bytes, 1)]
    symbols.sort(key=lambda row: (row.bytes or 0x10000, -row.value))
    symbol = symbols[0] if symbols else None
    return {"PC": f"0x{pc:04x}", "section": section,
            "symbol": symbol.name if symbol else None,
            "symbol_offset": pc - symbol.value if symbol else None,
            "interpretation": "single closing PC sample; not a loop proof"}


def result() -> dict[str, Any]:
    captured = load(CAPTURE)
    ring = classify(captured)
    value = {
        "format": FORMAT, "recorded_on": "2026-08-15",
        "status": "TARGET-RESULT-BOUND",
        "inputs": {"ring": bind(REBIND.RECEIPT),
            "session": bind(REBIND.SESSION), "raw_capture": bind(CAPTURE),
            "product_readback": bind(OUT / "product-readback.d81"),
            "library_readback": bind(OUT / "library-readback.d81")},
        "discipline": {"active_observations": 0,
            "target_sampler_only": True, "stops": 1, "resumes": 0,
            "same_stopped_session": True, "CPU_left_stopped": True,
            "D1_D5_executed": False},
        "tuple": captured["tuple"], "progress_ring": ring,
        "stopped_code_identity": stopped_identity(captured["tuple"]),
        "comparison": {"old_DMA_world": {"counter": 18,
                "observation_seconds": 118.23346033945272},
            "CPU_world": {"counter": ring["newest_counter"],
                "decision": ring["decision"]}},
        "claim_limit": (
            "The ring measures successful logical reads over three consecutive "
            "2048-frame intervals. A closing PC is contextual only; the CPU "
            "remains stopped and D1-D5 remain closed."),
    }
    value["mutations"] = mutation_gate(value)
    audit(value)
    return value


def audit(value: dict[str, Any]) -> None:
    require(
        value.get("discipline") == {"active_observations": 0,
            "target_sampler_only": True, "stops": 1, "resumes": 0,
            "same_stopped_session": True, "CPU_left_stopped": True,
            "D1_D5_executed": False}
        and value.get("progress_ring", {}).get("decision")
            in {"LIVE", "FIXED", "COMPLETE"}
        and len(value.get("progress_ring", {}).get(
            "slots_newest_first", [])) == 4
        and value.get("comparison", {}).get("old_DMA_world", {}).get(
            "counter") == 18,
        "Link-107 progress result drift")


def mutation_gate(base: dict[str, Any]) -> dict[str, Any]:
    cases = {
        "allow-active-observation": ("discipline", "active_observations", 1),
        "add-stop": ("discipline", "stops", 2),
        "add-resume": ("discipline", "resumes", 1),
        "open-D1-D5": ("discipline", "D1_D5_executed", True),
        "invent-decision": ("progress_ring", "decision", "UNKNOWN"),
        "drop-slot": ("progress_ring", "slots_newest_first", []),
        "rewrite-baseline": ("comparison", "old_DMA_world", {"counter": 19}),
    }
    rejected: dict[str, str] = {}
    for name, (section, key, replacement) in cases.items():
        trial = deepcopy(base)
        trial[section][key] = replacement
        try:
            audit(trial)
        except ContactError as error:
            rejected[name] = str(error)
    require(len(rejected) == len(cases), "Link-107 contact mutation survived")
    return {"count": len(rejected), "rejected": rejected}


def record() -> dict[str, Any]:
    require(not RECEIPT.exists(), "Link-107 progress result receipt exists")
    value = result()
    write_json(RESULT, value)
    write_json(RECEIPT, value)
    return value


def check() -> dict[str, Any]:
    value = load(RECEIPT)
    audit(value)
    require(value == load(RESULT), "Link-107 result/receipt identity drift")
    require(value["inputs"]["ring"] == bind(REBIND.RECEIPT)
            and value["inputs"]["session"] == bind(REBIND.SESSION)
            and value["inputs"]["raw_capture"] == bind(CAPTURE),
            "Link-107 result input drift")
    return value


def selftest() -> dict[str, Any]:
    state = bytearray(66)
    state[11] = RING.ARM_VALUE
    state[64:66] = b"\xd7\xd7"
    for index, frame_high in enumerate((8, 16, 24, 32)):
        at = 12 + index * 13
        state[at:at + 13] = RING.slot(
            (index + 1) * 10000, 3, 96, 0, 0, 1, frame_high)
    ring = classify({"state_hex": state.hex(),
                     "frame_counter_hex": (40 << 8).to_bytes(2, "little").hex()})
    require(ring["decision"] == "LIVE"
            and len(ring["intervals_newest_first"]) == 3,
            "Link-107 contact selftest oracle drift")
    return ring


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preflight", "capture", "record",
                                           "check", "selftest"))
    args = parser.parse_args()
    if args.action == "preflight":
        value = preflight()
    elif args.action == "capture":
        value = capture()
    elif args.action == "record":
        value = record()
    elif args.action == "check":
        value = check()
    else:
        value = selftest()
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContactError, REBIND.RebindError, OSError, KeyError,
            ValueError) as error:
        print(f"LINK 107 PROGRESS CONTACT: {error}", file=sys.stderr)
        raise SystemExit(1)
