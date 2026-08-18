#!/usr/bin/env python3
"""Raw-first final capture and result binder for the bundled contact."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402
import c2_v16_corrected_view_contact as VIEW  # noqa: E402
import c2_v150_stager_liveness_successor as LIVENESS  # noqa: E402
import c2_v20_map_cpu_transport_probe as PROBE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.3/v2.0-loading-libraries-progress-map/contact"
CAPTURE = OUT / "raw-capture.json"
RESULT = OUT / "result.json"
RECEIPT = ARCH / "c2.3-v2.0-loading-libraries-progress-map-device-receipt.json"
DEVICE = os.environ.get("DEVICE", "/dev/ttyUSB1")
FORMAT = "lisp65-c2.3-v2.0-loading-libraries-progress-map-device-v1"
FRAME_HZ = 51.966
SAMPLE_FRAMES = 2048
EXPECTED_READS = 346_298
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


class ContactError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ContactError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical(value)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def preflight() -> dict[str, Any]:
    probe = PROBE.check()
    session = load(PROBE.SESSION)
    require(session["authorization"] == {
        "contact_authorized": True, "class": "B",
        "owner_keyboard_required": False, "D1_D5_open": False},
        "contact authorization drift")
    require(session["active_interval"] == {
        "begins": "FTP exits after same-world readback and product mount",
        "quiet_seconds": 180, "host_monitor_entries": 0,
        "host_CPU_stops": 0, "screenshots": 0, "FTP_accesses": 0,
        "owner_keyboard_lines": 0,
        "sampler": "owned target raster IRQ only"},
        "active quiet interval drift")
    return {"probe_receipt": bind(PROBE.RECEIPT),
            "session": bind(PROBE.SESSION),
            "product_D81": bind(PROBE.PROBE_D81),
            "library_D81": bind(PROBE.RING.LIBRARY_D81),
            "mutations": probe["mutations"]["total"]}


def append_raw(path: Path, label: str, command: str, raw: bytes) -> None:
    row = canonical({"label": label, "command": command, "raw_hex": raw.hex()})
    with path.open("ab") as handle:
        handle.write(row)
        handle.flush()
        os.fsync(handle.fileno())


def monitor_row(fd: int, address: int, raw_log: Path) -> bytes:
    command = f"m{address:08x}"
    raw = VIEW.command(fd, command.encode(), 0.05)
    append_raw(raw_log, f"physical-0x{address:08x}", command, raw)
    match = re.search(fr":{address:08X}:([0-9A-Fa-f]{{32}})".encode(), raw)
    require(match is not None,
            f"physical memory row absent at 0x{address:08x}: {raw!r}")
    return bytes.fromhex(match.group(1).decode())


def read_range(fd: int, address: int, count: int, raw_log: Path) -> bytes:
    result = bytearray()
    cursor = address
    end = address + count
    while cursor < end:
        remaining = end - cursor
        start = cursor if remaining >= 16 else max(address, end - 16)
        row = monitor_row(fd, start, raw_log)
        at = cursor - start
        take = min(remaining, 16 - at)
        require(take > 0, "physical range reader made no progress")
        result.extend(row[at:at + take])
        cursor += take
    require(len(result) == count, "physical range length drift")
    return bytes(result)


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
        append_raw(raw_log, "sole-final-stop", "t1", stop_raw)
        register_raw = VIEW.command(fd, b"r", 0.05)
        append_raw(raw_log, "register-tuple", "r", register_raw)
        registers = VIEW.parse_registers(register_raw)
        state = read_range(fd, 0x0000B582, 66, raw_log)
        frames = read_range(fd, 0x0000FF83, 2, raw_log)
    finally:
        os.close(fd)
    (OUT / "progress-state.bin").write_bytes(state)
    (OUT / "frame-counter.bin").write_bytes(frames)
    value = {
        "format": FORMAT + "-raw",
        "captured_on": "2026-08-14", "authority": authority,
        "device": DEVICE, "discipline": {
            "active_observations": 0, "target_sampler_only": True,
            "stops": 1, "resumes": 0, "runs_after_mount": 0,
            "tuple_before_data": True, "raw_persisted_before_interpretation": True,
            "same_stopped_session": True, "CPU_left_stopped": True,
            "D1_D5_executed": False},
        "tuple": registers, "state_hex": state.hex(),
        "frame_counter_hex": frames.hex(), "raw_log": bind(raw_log),
        "claim_limit": "Raw-first stopped-state capture only; the result binder owns every transport and progress claim.",
    }
    write_json(CAPTURE, value)
    return value


def u32(raw: bytes) -> int:
    return int.from_bytes(raw, "little")


def classify(value: dict[str, Any]) -> dict[str, Any]:
    state = bytes.fromhex(value["state_hex"])
    frames = bytes.fromhex(value["frame_counter_hex"])
    require(len(state) == 66 and len(frames) == 2,
            "captured range extent drift")
    final_frame = int.from_bytes(frames, "little")
    bank5, attic = state[64], state[65]
    probe_values = {0xA5: "PASS", 0xE1: "MISMATCH", 0xD7: "NOT-RUN"}
    probe = {"bank5_status": f"0x{bank5:02x}",
             "attic_status": f"0x{attic:02x}",
             "bank5": probe_values.get(bank5, "INVALID"),
             "attic": probe_values.get(attic, "INVALID")}
    if bank5 == attic == 0xA5:
        probe["decision"] = "MAP-CPU-BANK5-AND-ATTIC-TARGET-GREEN"
    elif bank5 in (0xA5, 0xE1) and attic in (0xA5, 0xE1):
        probe["decision"] = "MAP-CPU-TRANSPORT-REFUTED-IN-ONE-OR-MORE-DOMAINS"
    else:
        probe["decision"] = "INSTRUMENT-OR-SETUP-RED"

    slots = []
    for index in range(4):
        raw = state[12 + index * 13:12 + (index + 1) * 13]
        require(len(raw) == 13, "ring slot extent drift")
        if raw[12] != 0xA5:
            continue
        frame_hi = raw[11]
        age_hi = ((final_frame >> 8) - frame_hi) & 0xFF
        slots.append({"index": index, "counter": u32(raw[0:4]),
                      "phase": raw[4], "image": raw[5],
                      "entry_or_publication": int.from_bytes(raw[6:8], "little"),
                      "descriptor_ordinal": int.from_bytes(raw[8:10], "little"),
                      "transport": raw[10], "frame_high": frame_hi,
                      "age_high": age_hi, "commit": "0xa5"})
    require(len(slots) == 4, f"progress ring did not commit four slots: {len(slots)}")
    slots.sort(key=lambda row: row["age_high"])
    require(all(slots[i + 1]["age_high"] - slots[i]["age_high"] == 8
                for i in range(3)), "ring samples are not consecutive 2048-frame epochs")
    intervals = []
    for newer, older in zip(slots, slots[1:]):
        delta = (newer["counter"] - older["counter"]) & 0xFFFFFFFF
        intervals.append({"newer_slot": newer["index"],
                          "older_slot": older["index"],
                          "counter_delta": delta,
                          "seconds": SAMPLE_FRAMES / FRAME_HZ,
                          "reads_per_second": delta / (SAMPLE_FRAMES / FRAME_HZ)})
    growing = any(row["counter_delta"] > 0 for row in intervals)
    newest = slots[0]
    ring = {"final_frame": final_frame, "slots_newest_first": slots,
            "intervals_newest_first": intervals,
            "newest_counter": newest["counter"],
            "expected_reads": EXPECTED_READS,
            "completed": newest["counter"] == EXPECTED_READS,
            "decision": "LIVE" if growing else "FIXED",
            "newest_phase": f"0x{newest['phase']:02x}",
            "newest_image": newest["image"],
            "newest_entry_or_publication": newest["entry_or_publication"],
            "newest_descriptor_ordinal": newest["descriptor_ordinal"],
            "newest_transport": {
                "value": newest["transport"],
                "meaning": {0: "C2D / Bank 5", 1: "Shelf / Attic"}
                           .get(newest["transport"], "unknown")},
            "fixed_observation_seconds": 0.0 if growing else
                3 * SAMPLE_FRAMES / FRAME_HZ}
    positive = [row["reads_per_second"] for row in intervals
                if row["counter_delta"] > 0]
    if positive:
        rate = sum(positive) / len(positive)
        ring["observed_reads_per_second"] = rate
        ring["projected_seconds_for_346298_reads"] = EXPECTED_READS / rate
    if ring["completed"]:
        ring["completion_bracket"] = "between the first complete committed slot and its preceding 2048-frame slot"
    return {"probe": probe, "progress_ring": ring}


def packed_stager_liveness() -> dict[str, Any]:
    elf = PROBE.PROBE_STAGER.with_suffix(PROBE.PROBE_STAGER.suffix + ".elf")
    try:
        value = LIVENESS.delivered_liveness_gate(elf)
    except Exception as error:
        require("lacks the unique liveness-prefix entry" in str(error),
                f"unexpected packed-stager liveness failure: {error}")
        return {"result": "ABSENT-IN-ACTUAL-PACKED-ELF",
                "actual_ELF": bind(elf), "error": str(error),
                "owner_observation": "STAGING MEDIA was not visible; BUILDING HEAP and LOADING LIBRARIES were visible; no prompt followed"}
    raise ContactError(f"packed stager unexpectedly carries STAGING MEDIA: {value}")


def stopped_code_identity(tuple_value: dict[str, Any]) -> dict[str, Any]:
    pc = int(tuple_value["PC"], 0)
    truth = ElfTruth.read(PROBE.PROBE_ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    section = truth.section(".text")
    symbol = truth.symbol("crc32_update")
    require(section.address <= pc < section.address + section.bytes
            and symbol.value <= pc < symbol.value + symbol.bytes,
            "stopped PC is outside delivered crc32_update identity")
    return {"PC": f"0x{pc:04x}", "section": section.name,
            "symbol": symbol.name, "symbol_start": f"0x{symbol.value:04x}",
            "symbol_offset": pc - symbol.value,
            "interpretation": "single final PC sample inside phase-03 CRC computation; not by itself a loop proof"}


def audit(value: dict[str, Any]) -> None:
    require(value["discipline"] == {
        "active_observations": 0, "target_sampler_only": True,
        "stops": 1, "resumes": 0, "same_stopped_session": True,
        "CPU_left_stopped": True, "D1_D5_executed": False},
        "device discipline drift")
    require(value["probe"]["decision"] in {
        "MAP-CPU-BANK5-AND-ATTIC-TARGET-GREEN",
        "MAP-CPU-TRANSPORT-REFUTED-IN-ONE-OR-MORE-DOMAINS",
        "INSTRUMENT-OR-SETUP-RED"}, "probe decision drift")
    require(value["progress_ring"]["decision"] in {"LIVE", "FIXED"}
            and len(value["progress_ring"]["slots_newest_first"]) == 4,
            "progress decision drift")
    require(value["packed_stager_liveness"]["result"]
            == "ABSENT-IN-ACTUAL-PACKED-ELF"
            and value["stopped_code_identity"]["symbol"] == "crc32_update",
            "screen/code identity drift")
    if value["progress_ring"]["decision"] == "FIXED":
        rows = value["progress_ring"]["slots_newest_first"]
        require(all(row["counter"] == 18 and row["phase"] == 3
                    and row["image"] == 96
                    and row["entry_or_publication"] == 0
                    and row["descriptor_ordinal"] == 0
                    and row["transport"] == 1 for row in rows)
                and value["progress_ring"]["fixed_observation_seconds"]
                    > 118.2,
                "fixed phase-03/image-96/Shelf tuple drift")


def mutation_gate(base: dict[str, Any]) -> dict[str, Any]:
    cases = {
        "allow-active-observation": (["discipline", "active_observations"], 1),
        "lose-target-sampler": (["discipline", "target_sampler_only"], False),
        "add-stop": (["discipline", "stops"], 2),
        "add-resume": (["discipline", "resumes"], 1),
        "split-session": (["discipline", "same_stopped_session"], False),
        "resume-CPU": (["discipline", "CPU_left_stopped"], False),
        "open-D1-D5": (["discipline", "D1_D5_executed"], True),
        "invent-probe-result": (["probe", "decision"], "UNKNOWN"),
        "invent-ring-result": (["progress_ring", "decision"], "UNKNOWN"),
        "drop-slot": (["progress_ring", "slots_newest_first"],
                      base["progress_ring"]["slots_newest_first"][:3]),
        "mislabel-image-as-ordinal":
            (["progress_ring", "slots_newest_first", 0, "image"], 0),
        "mislabel-transport-as-error":
            (["progress_ring", "slots_newest_first", 0, "transport"], 0),
        "invent-staging-sign":
            (["packed_stager_liveness", "result"], "PRESENT"),
        "misbind-final-PC":
            (["stopped_code_identity", "symbol"], "c2_stream_phase_03"),
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
        except ContactError as error:
            rejected[name] = str(error)
        else:
            raise ContactError(f"device-result mutation survived: {name}")
    return {"count": len(rejected), "rejected": rejected}


def record() -> dict[str, Any]:
    capture_value = load(CAPTURE)
    result = classify(capture_value)
    value = {
        "format": FORMAT, "recorded_on": "2026-08-14",
        "status": "TARGET-RESULT-BOUND",
        "inputs": {"probe": bind(PROBE.RECEIPT), "session": bind(PROBE.SESSION),
                   "raw_capture": bind(CAPTURE),
                   "product_readback": bind(OUT / "product-readback.d81"),
                   "library_readback": bind(OUT / "library-readback.d81")},
        "discipline": {"active_observations": 0, "target_sampler_only": True,
                       "stops": 1, "resumes": 0,
                       "same_stopped_session": True,
                       "CPU_left_stopped": True, "D1_D5_executed": False},
        "tuple": capture_value["tuple"], **result,
        "packed_stager_liveness": packed_stager_liveness(),
        "stopped_code_identity": stopped_code_identity(capture_value["tuple"]),
        "claim_limit": "The MAP claim is limited to 256 repeated four-byte CPU reads at each tested Bank-5 and Attic source base. The ring decides life versus fixed state and measures its observed interval rate; it does not by itself promote a transport or diagnose every remaining reader.",
    }
    value["mutations"] = mutation_gate(value)
    audit(value)
    write_json(RESULT, value)
    write_json(RECEIPT, value)
    return value


def check() -> dict[str, Any]:
    value = load(RECEIPT)
    audit(value)
    require(value == load(RESULT), "device result/receipt identity drift")
    require(value["inputs"]["probe"] == bind(PROBE.RECEIPT)
            and value["inputs"]["session"] == bind(PROBE.SESSION)
            and value["inputs"]["raw_capture"] == bind(CAPTURE),
            "device result input drift")
    require(value["mutations"] == mutation_gate(
        {key: deepcopy(item) for key, item in value.items() if key != "mutations"}),
        "device result mutation drift")
    return value


def selftest() -> dict[str, Any]:
    state = bytearray(66)
    state[64] = state[65] = 0xA5
    final_high = 40
    for index, frame_high in enumerate((8, 16, 24, 32)):
        at = 12 + index * 13
        state[at:at + 4] = (index * 10_000).to_bytes(4, "little")
        state[at + 4:at + 11] = bytes((2, index, 0, 1, 0, 0xA5, 0))
        state[at + 11] = frame_high
        state[at + 12] = 0xA5
    value = classify({"state_hex": state.hex(),
                      "frame_counter_hex": (final_high << 8).to_bytes(2, "little").hex()})
    require(value["probe"]["decision"] == "MAP-CPU-BANK5-AND-ATTIC-TARGET-GREEN"
            and value["progress_ring"]["decision"] == "LIVE"
            and len(value["progress_ring"]["intervals_newest_first"]) == 3,
            "contact selftest oracle drift")
    return value


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
    except (ContactError, OSError, KeyError, ValueError) as error:
        print(f"c2-v20-loading-libraries-progress-map-contact: FAIL: {error}",
              file=sys.stderr)
        raise SystemExit(1)
