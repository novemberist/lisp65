#!/usr/bin/env python3
"""Run and bind the Link-107 ring on the repaired diagnostic medium."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402
import c2_media_builder_closure_enumeration as ENUM  # noqa: E402
import c2_v16_corrected_view_contact as VIEW  # noqa: E402
import c2_v20_loading_libraries_progress_map_contact as RAW  # noqa: E402
import c2_v20_loading_libraries_progress_ring as RING  # noqa: E402
import c2_v21_loading_libraries_progress_contact as OLD  # noqa: E402
import c2_v21_loading_libraries_progress_media_repair as REPAIR  # noqa: E402
import c2_v21_loading_libraries_progress_rebind as REBIND  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
SESSION = ROOT / "config/c2-v21-loading-libraries-progress-media-recontact.json"
RUNNER = ROOT / "scripts/c2-v21-loading-libraries-progress-media-recontact.sh"
ENUM_RECEIPT = ARCH / "c2.3-media-builder-closure-enumeration-receipt.json"
OUT = ROOT / "build/c2.3/v2.1-loading-libraries-progress-media-recontact/contact"
CAPTURE = OUT / "raw-capture.json"
RESULT = OUT / "result.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-loading-libraries-progress-media-recontact-receipt.json")
AUTHORIZATION = "2a327257"
FORMAT = "lisp65-c2.3-v2.1-loading-progress-media-recontact-v1"
DEVICE = os.environ.get("DEVICE", "/dev/ttyUSB1")
FRAME_HZ = 51.966
SAMPLE_FRAMES = 2048
EXPECTED_READS = 346_298


class RecontactError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RecontactError(message)


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


def authority() -> dict[str, Any]:
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in ("ring contact authorized on the repaired medium",
                  "one ring contact on the repaired diagnostic medium",
                  "one closing stop", "complete readback"):
        require(token in text, f"repaired ring authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def session_contract() -> dict[str, Any]:
    value = load(SESSION)
    require(
        value.get("accepted_by") == AUTHORIZATION
        and value.get("status") ==
            "owner-authorized-autonomous-ring-contact-on-repaired-medium"
        and value.get("inputs", {}).get("product_medium") ==
            REPAIR.PRODUCT_D81.relative_to(ROOT).as_posix()
        and value.get("inputs", {}).get("library_medium") ==
            REBIND.LIBRARY_D81.relative_to(ROOT).as_posix()
        and value.get("active_interval") == {
            "begins": (
                "FTP exits after byteidentical readback and repaired "
                "product mount"),
            "quiet_seconds": 180, "host_monitor_entries": 0,
            "host_CPU_stops": 0, "screenshots": 0, "FTP_accesses": 0,
            "owner_keyboard_lines": 0,
            "sampler": "owned target raster IRQ only"}
        and value.get("authorization") == {
            "contact_authorized": True, "class": "B",
            "owner_keyboard_required": False, "D1_D5_open": False},
        "repaired Link-107 session drift")
    return value


def preflight() -> dict[str, Any]:
    repair = REPAIR.check()
    enumeration = ENUM.check()
    session_contract()
    require(
        repair.get("status") ==
            "HOST-GREEN; REPAIRED-DIAGNOSTIC-MEDIA-CLOSED"
        and repair.get("packed_artifact_gate_registry", {}).get(
            "complete") is True
        and repair.get("media", {}).get("product_D81") ==
            bind(REPAIR.PRODUCT_D81)
        and enumeration.get("builders", {}).get("total") == 64
        and "tools/host-lisp/"
            "c2_v21_loading_libraries_progress_media_repair.py" in
            enumeration.get("builders", {}).get("current_gate_closed", []),
        "repaired medium or structural closure is not green")
    return {"authorization": authority(), "repair": bind(REPAIR.RECEIPT),
            "enumeration": bind(ENUM_RECEIPT), "ring": bind(REBIND.RECEIPT),
            "session": bind(SESSION), "runner": bind(RUNNER),
            "product_D81": bind(REPAIR.PRODUCT_D81),
            "library_D81": bind(REBIND.LIBRARY_D81)}


def capture() -> dict[str, Any]:
    bound = preflight()
    require(Path(DEVICE).is_char_device(), f"serial device absent: {DEVICE}")
    OUT.mkdir(parents=True, exist_ok=True)
    raw_log = OUT / "monitor-raw.ndjson"
    raw_log.write_bytes(b"")
    fd = os.open(DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        stop_raw = VIEW.command(fd, b"t1", 0.08)
        RAW.append_raw(raw_log, "sole-final-stop", "t1", stop_raw)
        register_raw = VIEW.command(fd, b"r", 0.05)
        RAW.append_raw(raw_log, "register-tuple", "r", register_raw)
        registers = VIEW.parse_registers(register_raw)
        state = RAW.read_range(fd, 0x0000B582, 66, raw_log)
        frames = RAW.read_range(fd, 0x0000FF83, 2, raw_log)
    finally:
        os.close(fd)
    (OUT / "progress-state.bin").write_bytes(state)
    (OUT / "frame-counter.bin").write_bytes(frames)
    value = {
        "format": FORMAT + "-raw", "captured_on": "2026-08-15",
        "authority": bound, "device": DEVICE,
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


def classify(captured: dict[str, Any]) -> dict[str, Any]:
    state = bytes.fromhex(captured["state_hex"])
    frames = bytes.fromhex(captured["frame_counter_hex"])
    require(len(state) == 66 and len(frames) == 2,
            "repaired contact range extent drift")
    final_frame = int.from_bytes(frames, "little")
    if state[11] != RING.ARM_VALUE:
        return {"decision": "INSTRUMENT-RED", "reason": "ring-not-armed",
                "arm": f"0x{state[11]:02x}", "final_frame": final_frame,
                "committed_slots": 0}
    slots = RING.accepted_slots(state[12:64], frames[1])
    if len(slots) != 4:
        return {"decision": "INSTRUMENT-RED",
                "reason": "four-consecutive-committed-slots-absent",
                "arm": f"0x{state[11]:02x}", "final_frame": final_frame,
                "committed_slots": len(slots)}
    intervals = []
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
    result = {"decision": decision, "final_frame": final_frame,
        "slots_newest_first": slots, "intervals_newest_first": intervals,
        "newest_counter": newest["counter"], "expected_reads": EXPECTED_READS,
        "completed": completed, "newest_phase": f"0x{newest['phase']:02x}",
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
        result["observed_reads_per_second"] = rate
        result["projected_seconds_for_346298_reads"] = EXPECTED_READS / rate
        result["projected_minutes_for_346298_reads"] = (
            EXPECTED_READS / rate / 60)
    return result


def stopped_identity(tuple_value: dict[str, Any], decision: str
                     ) -> dict[str, Any]:
    pc = int(tuple_value["PC"], 0)
    if decision == "INSTRUMENT-RED":
        stager_elf = Path(str(REPAIR.STAGER) + ".elf")
        truth = ElfTruth.read(stager_elf, llvm_readobj=REBIND.READOBJ,
                              include_section_data=True)
        symbol = truth.symbol("show_disk_error")
        require(symbol.value <= pc < symbol.value + symbol.bytes,
                "instrument-red PC is not repaired stager disk-error hold")
        return {"PC": f"0x{pc:04x}", "owner": "repaired-diagnostic-stager",
                "section": symbol.section, "symbol": symbol.name,
                "symbol_offset": pc - symbol.value,
                "interpretation": "stager fail hold; no product-rate claim"}
    truth = ElfTruth.read(REBIND.DIAG_ELF, llvm_readobj=REBIND.READOBJ,
                          include_section_data=True)
    sections = [row for row in truth.sections
                if row.address <= pc < row.address + row.bytes]
    symbols = [row for row in truth.symbols
               if row.value <= pc < row.value + max(row.bytes, 1)]
    symbols.sort(key=lambda row: (row.bytes or 0x10000, -row.value))
    symbol = symbols[0] if symbols else None
    return {"PC": f"0x{pc:04x}", "owner": "diagnostic-product",
            "section": sections[0].name if sections else None,
            "symbol": symbol.name if symbol else None,
            "symbol_offset": pc - symbol.value if symbol else None,
            "interpretation": "single closing PC sample; not a loop proof"}


def derive() -> dict[str, Any]:
    captured = load(CAPTURE)
    ring = classify(captured)
    require((OUT / "product-readback.d81").read_bytes() ==
            REPAIR.PRODUCT_D81.read_bytes()
            and (OUT / "library-readback.d81").read_bytes() ==
                REBIND.LIBRARY_D81.read_bytes(),
            "repaired contact uploaded-media readback drift")
    status = ("INSTRUMENT-MEDIA-RED; CPU-RATE-UNMEASURED"
              if ring["decision"] == "INSTRUMENT-RED"
              else "TARGET-RESULT-BOUND")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-15",
        "status": status,
        "inputs": {"authorization": authority(),
            "repair": bind(REPAIR.RECEIPT),
            # This contact ran under the enumeration persisted in its raw
            # capture.  Later diagnostic builders may legitimately extend
            # the live inventory; they must not rewrite historical contact
            # authority after the device event.
            "enumeration": captured["authority"]["enumeration"],
            "ring": bind(REBIND.RECEIPT), "session": bind(SESSION),
            "raw_capture": bind(CAPTURE),
            "product_readback": bind(OUT / "product-readback.d81"),
            "library_readback": bind(OUT / "library-readback.d81")},
        "discipline": {"active_observations": 0,
            "target_sampler_only": True, "stops": 1, "resumes": 0,
            "same_stopped_session": True, "CPU_left_stopped": True,
            "D1_D5_executed": False},
        "tuple": captured["tuple"], "progress_ring": ring,
        "stopped_code_identity": stopped_identity(
            captured["tuple"], ring["decision"]),
        "comparison": {"old_DMA_world": {"counter": 18,
                "observation_seconds": 118.23346033945272},
            "repaired_CPU_world": {"counter": ring.get("newest_counter"),
                "decision": ring["decision"]}},
        "claim_limit": (
            "The ring measures successful logical reads over three "
            "consecutive 2048-frame intervals when four slots commit. A "
            "closing PC is contextual only; CPU remains stopped and D1-D5 "
            "remain closed."),
    }
    value["mutations"] = mutations(value)
    audit(value)
    return value


def audit(value: dict[str, Any]) -> None:
    decision = value.get("progress_ring", {}).get("decision")
    slots = value.get("progress_ring", {}).get("slots_newest_first", [])
    expected_status = ("INSTRUMENT-MEDIA-RED; CPU-RATE-UNMEASURED"
                       if decision == "INSTRUMENT-RED"
                       else "TARGET-RESULT-BOUND")
    require(
        value.get("status") == expected_status
        and value.get("discipline") == {"active_observations": 0,
            "target_sampler_only": True, "stops": 1, "resumes": 0,
            "same_stopped_session": True, "CPU_left_stopped": True,
            "D1_D5_executed": False}
        and decision in {"LIVE", "FIXED", "COMPLETE", "INSTRUMENT-RED"}
        and ((decision == "INSTRUMENT-RED"
              and value.get("progress_ring", {}).get("reason")
                  in {"ring-not-armed",
                      "four-consecutive-committed-slots-absent"}
              and value.get("progress_ring", {}).get(
                  "committed_slots", 4) < 4
              and value.get("stopped_code_identity", {}).get("owner") ==
                  "repaired-diagnostic-stager")
             or (decision != "INSTRUMENT-RED" and len(slots) == 4
                 and value.get("stopped_code_identity", {}).get("owner") ==
                    "diagnostic-product"))
        and value.get("comparison", {}).get("old_DMA_world", {}).get(
            "counter") == 18,
        "repaired Link-107 contact result drift")


def mutations(base: dict[str, Any]) -> dict[str, Any]:
    cases = {
        "allow-active-observation": ("discipline", "active_observations", 1),
        "add-stop": ("discipline", "stops", 2),
        "add-resume": ("discipline", "resumes", 1),
        "open-D1-D5": ("discipline", "D1_D5_executed", True),
        "invent-decision": ("progress_ring", "decision", "UNKNOWN"),
        "rewrite-baseline": ("comparison", "old_DMA_world", {"counter": 19}),
    }
    if base["progress_ring"]["decision"] == "INSTRUMENT-RED":
        cases["invent-four-slots"] = (
            "progress_ring", "committed_slots", 4)
    else:
        cases["drop-slots"] = ("progress_ring", "slots_newest_first", [])
    rejected = []
    for name, (section, key, replacement) in cases.items():
        trial = deepcopy(base)
        trial[section][key] = replacement
        try:
            audit(trial)
        except RecontactError:
            rejected.append(name)
    require(len(rejected) == len(cases), "repaired contact mutation survived")
    return {"count": len(rejected), "rejected": sorted(rejected)}


def record() -> dict[str, Any]:
    require(not RECEIPT.exists(), "repaired contact receipt already exists")
    value = derive()
    write_json(RESULT, value)
    write_json(RECEIPT, value)
    return value


def check() -> dict[str, Any]:
    value = load(RECEIPT)
    audit(value)
    require(value == derive() and value == load(RESULT),
            "repaired contact reconstruction drift")
    return value


def selftest() -> dict[str, Any]:
    state = bytearray(66)
    state[11] = RING.ARM_VALUE
    for index, frame_high in enumerate((8, 16, 24, 32)):
        at = 12 + index * 13
        state[at:at + 13] = RING.slot(
            (index + 1) * 10000, 3, 96, 0, 0, 1, frame_high)
    ring = classify({"state_hex": state.hex(),
                     "frame_counter_hex":
                         (40 << 8).to_bytes(2, "little").hex()})
    require(ring["decision"] == "LIVE"
            and len(ring["intervals_newest_first"]) == 3,
            "repaired contact selftest drift")
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
    except (RecontactError, ENUM.EnumerationError, REPAIR.RepairError,
            REBIND.RebindError, OSError, KeyError, ValueError,
            subprocess.CalledProcessError) as error:
        print(f"REPAIRED LINK-107 RING CONTACT: {error}", file=sys.stderr)
        raise SystemExit(1)
