#!/usr/bin/env python3
"""Capture the one authorised phase-02a convergence site row.

The device is already stopped.  The authorised repeat issues no additional
stop, captures and verifies the complete tuple before memory, reads only the
six config-bound static ranges, persists them before interpretation, derives
one discriminator byte pair from the retained descriptors, and leaves the
CPU stopped.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys
import termios
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build/c2.3/v2.0-map-tuple-d1/phase02a-site-row"
CAPTURE = OUT / "capture.json"
STATIC_CHECKPOINT = OUT / "static-checkpoint.json"
DEVICE = os.environ.get("DEVICE", "/dev/ttyUSB1")

PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
ROW = ROOT / "config/c2-v20-phase02a-convergence-site-row.json"
PREDECESSOR = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-phase02a-read-attribution-receipt.json")
ELF = ROOT / (
    "build/c2.3/v2.0-map-tuple-fix-replacement-card/final/"
    "lisp65-c2-substitution-linked.prg.elf")
PRODUCT_READBACK = ROOT / "build/c2.3/v2.0-map-tuple-d1/product-readback.d81"
LIBRARY_READBACK = ROOT / "build/c2.3/v2.0-map-tuple-d1/library-readback.d81"
OLD_CAPTURE = ROOT / "build/c2.3/v2.0-map-tuple-d1/e25-stopped-state/capture.json"

AUTHORIZATION_COMMIT = "97c4ae61"
AUTHORIZATION_BYTES = 51579
AUTHORIZATION_SHA256 = (
    "caeea2a2f8f969e6bed4d1fc50885e393dc61c1ea2b000c811b8b07ef8467f1f")
ROW_SHA256 = (
    "1699c0e8522dca71f45a1b9abcf7181cc6c0ab3cdaa18a89989a1fcd2e67d9ab")
PREDECESSOR_SHA256 = (
    "f44c65177baf7b5c6431c43b02299111ec5ddd168dbd6dac3d3ed54e529ebb60")
ELF_SHA256 = (
    "a481eff4acd32f04dde6660090aa2761a2f4a4b6307945cbcb2cda0f70435673")
PRODUCT_SHA256 = (
    "43da1ce57ced3088a56349c84d3b0c32bbc25f1aae34928b808fe31af8462a95")
LIBRARY_SHA256 = (
    "15e4405929be0686d12c8079509fbd9e12f9314041218ed773fd57b895692060")

EXPECTED_TUPLE = {
    "PC": "0xe096", "A": "0x02", "X": "0x64", "Y": "0x01",
    "Z": "0x00", "B": "0x00", "SP": "0x01e4",
    "MAPH": "0x8000", "MAPL": "0x0000",
    "suffix": "4C96E0  00     04 .....I.. ...P 15 -  00 - ..c..lhc",
}

RANGES = (
    ("compiler-static-stack-and-pseudo-registers", 0x0002, 30),
    ("convergence-done-markers", 0x0087, 2),
    ("D700-primary-descriptor", 0xB9D3, 12),
    ("D700-source-probe-descriptors", 0xC000, 24),
    ("D705-source-probe-descriptors-and-value", 0xC019, 41),
    ("D705-primary-descriptor", 0xC0B2, 20),
)

REGISTER_RE = re.compile(
    rb"(?:^|\n)([0-9A-Fa-f]{4})"
    rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
    rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
    rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{4})"
    rb"\s+([0-9A-Fa-f]{4})\s+([0-9A-Fa-f]{4})([^\r\n]*)")


class CaptureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CaptureError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def regular(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    return path.read_bytes()


def bind(path: Path) -> dict[str, Any]:
    raw = regular(path)
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def git_authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION_COMMIT}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION_COMMIT}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    require(len(raw) == AUTHORIZATION_BYTES and sha(raw) == AUTHORIZATION_SHA256,
            "site-row authorization blob identity drift")
    require(b"Site-row repeat authorized" in raw
            and b"one read-only repeat" in raw
            and b"without a further `t1`" in raw
            and b"No resume" in raw,
            "site-row repeat authorization language absent")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def preflight() -> dict[str, Any]:
    authority = git_authorization()
    bindings = {
        "site_row": bind(ROW),
        "desk_attribution": bind(PREDECESSOR),
        "candidate_ELF": bind(ELF),
        "product_D81_readback": bind(PRODUCT_READBACK),
        "library_D81_readback": bind(LIBRARY_READBACK),
        "predecessor_capture": bind(OLD_CAPTURE),
    }
    expected = {
        "site_row": ROW_SHA256,
        "desk_attribution": PREDECESSOR_SHA256,
        "candidate_ELF": ELF_SHA256,
        "product_D81_readback": PRODUCT_SHA256,
        "library_D81_readback": LIBRARY_SHA256,
        "predecessor_capture":
            "320cc81c2dff3cbc0fb3655107202be32ba6f7dd7b7d34a624e32e50a23567ef",
    }
    require({name: item["sha256"] for name, item in bindings.items()} == expected,
            "phase-02a site-row input identity drift")
    row = json.loads(regular(ROW))
    actual_ranges = tuple(
        (item["name"], int(item["address"], 0), item["bytes"])
        for item in row["physical_bank0_ranges"])
    require(actual_ranges == RANGES, "authorized static range drift")
    require(row["precondition"] == {
        "device_state":
            "the D1 E25 state captured under 7478ce73 remains stopped and unchanged",
        "tuple_and_media_identity_first": True,
        "runs": 0, "resumes": 0, "resets": 0, "D2_D5_executed": False,
    }, "site-row precondition drift")
    require(not CAPTURE.exists(), "phase-02a site capture is one-shot")
    require(not STATIC_CHECKPOINT.exists(),
            "phase-02a static checkpoint already exists")
    return {"authorization": authority, **bindings}


def serial_read(fd: int, seconds: float) -> bytes:
    result = bytearray()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        ready, _, _ = select.select(
            [fd], [], [], min(0.02, max(0.0, deadline - time.monotonic())))
        if ready:
            try:
                result.extend(os.read(fd, 8192))
            except BlockingIOError:
                pass
    return bytes(result)


def slow_write(fd: int, value: bytes) -> None:
    for byte in value:
        while True:
            try:
                if os.write(fd, bytes((byte,))):
                    break
            except BlockingIOError:
                time.sleep(0.001)


def configure_serial(fd: int) -> None:
    fcntl.fcntl(fd, fcntl.F_SETFL,
                fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)
    attrs = termios.tcgetattr(fd)
    attrs[0] = attrs[1] = attrs[3] = 0
    attrs[2] = (
        attrs[2]
        & ~(termios.PARENB | termios.CSTOPB | termios.CSIZE | termios.CRTSCTS)
    ) | termios.CS8 | termios.CLOCAL | termios.CREAD
    attrs[4] = attrs[5] = termios.B2000000
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    termios.tcflush(fd, termios.TCIOFLUSH)


def command(fd: int, value: bytes, wait: float = 0.05) -> bytes:
    slow_write(fd, value + b"\r")
    time.sleep(wait)
    return serial_read(fd, 0.5)


def parse_registers(raw: bytes) -> dict[str, str]:
    match = REGISTER_RE.search(raw)
    require(match is not None, f"full monitor register row absent: {raw!r}")
    names = ("PC", "A", "X", "Y", "Z", "B", "SP", "MAPH", "MAPL")
    widths = (4, 2, 2, 2, 2, 2, 4, 4, 4)
    result = {name: f"0x{int(match.group(index), 16):0{width}x}"
              for index, (name, width) in enumerate(zip(names, widths), 1)}
    result["suffix"] = match.group(10).decode("ascii", errors="replace").strip()
    return result


def monitor_row(fd: int, address: int) -> tuple[bytes, bytes]:
    raw = command(fd, f"m{address:08x}".encode())
    match = re.search(fr":{address:08X}:([0-9A-Fa-f]{{32}})".encode(), raw)
    require(match is not None,
            f"physical memory row absent at 0x{address:08x}: {raw!r}")
    return bytes.fromhex(match.group(1).decode()), raw


def read_range(fd: int, address: int, count: int) -> tuple[bytes, list[dict[str, Any]]]:
    end = address + count
    cursor = address
    result = bytearray()
    commands: list[dict[str, Any]] = []
    while cursor < end:
        remaining = end - cursor
        start = cursor if remaining >= 16 else max(address, end - 16)
        row, raw = monitor_row(fd, start)
        take_at = cursor - start
        take = min(remaining, 16 - take_at)
        require(take > 0, "physical range reader made no progress")
        result.extend(row[take_at:take_at + take])
        commands.append({"command": f"m{start:08x}",
                         "returned_address": f"0x{start:08x}",
                         "returned_hex": row.hex(),
                         "consumed_offset": take_at,
                         "consumed_bytes": take,
                         "raw_hex": raw.hex()})
        cursor += take
    require(len(result) == count, "physical range length drift")
    return bytes(result), commands


def edma_job(raw: bytes) -> dict[str, int]:
    require(len(raw) == 20, "Enhanced-DMA descriptor length drift")
    source = (raw[11] | (raw[12] << 8) | ((raw[13] & 0x0f) << 16)
              | (raw[2] << 20))
    target = (raw[14] | (raw[15] << 8) | ((raw[16] & 0x0f) << 16)
              | (raw[4] << 20))
    return {"command": raw[8], "length": raw[9] | (raw[10] << 8),
            "source": source, "target": target}


def d700_job(raw: bytes) -> dict[str, int]:
    require(len(raw) == 12, "ordinary-DMA descriptor length drift")
    return {"command": raw[0], "length": raw[1] | (raw[2] << 8),
            "source": (raw[5] << 16) | raw[3] | (raw[4] << 8),
            "target": (raw[8] << 16) | raw[6] | (raw[7] << 8)}


def choose_dynamic(static: dict[str, bytes]) -> dict[str, Any]:
    pseudo = static["compiler-static-stack-and-pseudo-registers"]
    markers = static["convergence-done-markers"]
    d700_primary = d700_job(static["D700-primary-descriptor"])
    d700_probe_raw = static["D700-source-probe-descriptors"]
    d700_probe = d700_job(d700_probe_raw[:12])
    d700_marker = d700_job(d700_probe_raw[12:])
    d705_probe_raw = static["D705-source-probe-descriptors-and-value"]
    d705_probe = edma_job(d705_probe_raw[:20])
    d705_marker = edma_job(d705_probe_raw[20:40])
    d705_primary = edma_job(static["D705-primary-descriptor"])
    stack = pseudo[0] | (pseudo[1] << 8)
    geometry = {
        "caller_static_stack": stack,
        "outer_Shelf_target": (stack - 32) & 0xffff,
        "D700_C2D_target": (stack - 104) & 0xffff,
        "inner_Shelf_target": (stack - 136) & 0xffff,
    }

    site = "unresolved"
    family = "unresolved"
    probe_timeout = False
    d700_probe_current = 0x00050030 <= d700_probe["source"] < 0x00050050
    d700_primary_current = d700_primary["source"] == 0x00050030
    d705_probe_current = 0x08100020 <= d705_probe["source"] < 0x08100040
    d705_primary_current = d705_primary["source"] == 0x08100020
    if markers[1] != 0xA5 and d705_probe_current:
        family = "D705"
        site = "probe-timeout-before-primary"
        probe_timeout = True
    elif markers[0] != 0xA5 and d700_probe_current:
        family = "D700"
        site = "D700-C2D-image-row"
        probe_timeout = True
    elif not d700_probe_current and d705_probe_current:
        family = "D705"
        site = "D705-phase02a-outer-Shelf"
    elif d700_probe_current and not d705_primary_current:
        family = "D700"
        site = "D700-C2D-image-row"
    elif d700_probe_current and d705_primary_current \
            and not d700_primary_current:
        family = "D705"
        site = "D705-image-reader-Shelf-cross-read"
    elif d700_probe_current and d700_primary_current \
            and d705_primary_current:
        relative = ((d705_primary["target"] - d700_primary["target"]
                     + 0x8000) & 0xffff) - 0x8000
        if relative == 72:
            family = "D700"
            site = "D700-C2D-image-row"
        elif relative == -32:
            family = "D705"
            site = "D705-image-reader-Shelf-cross-read"
    require(family != "unresolved", "retained descriptors name no authorized family")

    probe = d700_probe if family == "D700" else d705_probe
    primary = d700_primary if family == "D700" else d705_primary
    if probe_timeout:
        source_address = probe["source"]
        target_address = probe["target"]
        target_role = "source-probe-value"
    else:
        require(primary["length"] > 0
                and primary["source"] <= probe["source"]
                < primary["source"] + primary["length"],
                "probe source escapes retained primary descriptor")
        source_address = probe["source"]
        target_address = primary["target"] + source_address - primary["source"]
        target_role = "primary-first-difference"
    require(target_address < 0x10000,
            "dynamic target is not physical Bank-0 RAM")
    return {
        "selected_family": family, "selected_site": site,
        "probe_timeout": probe_timeout, "target_role": target_role,
        "source_address": source_address, "target_address": target_address,
        "geometry": geometry,
        "execution_discriminators": {
            "D700_probe_current": d700_probe_current,
            "D700_primary_current": d700_primary_current,
            "D705_probe_current": d705_probe_current,
            "D705_primary_current": d705_primary_current,
        },
        "D700": {"done": markers[0], "probe": d700_probe,
                  "marker": d700_marker, "primary": d700_primary},
        "D705": {"done": markers[1], "probe": d705_probe,
                  "marker": d705_marker, "primary": d705_primary,
                  "retained_probe_value": d705_probe_raw[40]},
    }


def capture() -> dict[str, Any]:
    authority = preflight()
    require(Path(DEVICE).is_char_device(), f"serial device absent: {DEVICE}")
    fd = os.open(DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        configure_serial(fd)
        stop_raw = b""
        registers_raw = command(fd, b"r", 0.05)
        registers = parse_registers(registers_raw)
        require(registers == EXPECTED_TUPLE,
                f"preserved tuple mismatch; no memory read: {registers!r}")
        reads = []
        static: dict[str, bytes] = {}
        for name, address, count in RANGES:
            observed, commands = read_range(fd, address, count)
            static[name] = observed
            reads.append({"name": name, "physical_address": f"0x{address:08x}",
                          "bytes": count, "observed_hex": observed.hex(),
                          "monitor_rows": commands})
        # Raw evidence is authoritative and must survive every interpretation
        # failure.  Persist it before the descriptor selector runs.
        checkpoint = {
            "format": "lisp65-c2.3-v20-phase02a-static-checkpoint-v1",
            "authority": authority, "device": DEVICE, "tuple": registers,
            "stop_raw_hex": stop_raw.hex(),
            "register_raw_hex": registers_raw.hex(), "reads": reads,
            "discipline": {"stops": 0, "resumes": 0, "runs": 0,
                           "resets": 0, "tuple_before_memory": True,
                           "CPU_left_stopped": True, "D2_D5_executed": False},
        }
        OUT.mkdir(parents=True, exist_ok=True)
        STATIC_CHECKPOINT.write_text(
            json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        dynamic = choose_dynamic(static)
        dynamic_reads = []
        for role, address in (("first-difference-target",
                               dynamic["target_address"]),
                              ("immutable-source", dynamic["source_address"])):
            observed, commands = read_range(fd, address, 1)
            dynamic_reads.append({
                "name": role, "physical_address": f"0x{address:08x}",
                "bytes": 1, "observed_hex": observed.hex(),
                "monitor_rows": commands})
    finally:
        os.close(fd)
    value = {
        "format": "lisp65-c2.3-v20-phase02a-site-capture-v1",
        "captured_on": "2026-08-13", "authority": authority,
        "discipline": {"stops": 0, "resumes": 0, "runs": 0, "resets": 0,
                       "tuple_before_memory": True, "static_before_dynamic": True,
                       "CPU_left_stopped": True, "D2_D5_executed": False},
        "device": DEVICE, "tuple": registers,
        "stop_raw_hex": stop_raw.hex(),
        "register_raw_hex": registers_raw.hex(),
        "reads": reads, "dynamic_selection": dynamic,
        "dynamic_reads": dynamic_reads,
        "claim_limit": (
            "Raw authorized read-only site row only; classification belongs "
            "to a separately gated result binder. No fix or device action."),
    }
    CAPTURE.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    return value


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"preflight", "capture"},
            "usage: c2_v20_phase02a_site_capture.py preflight|capture")
    if sys.argv[1] == "preflight":
        print(json.dumps({"status": "PREFLIGHT PASS", "device": DEVICE,
                          "authority": preflight()}, indent=2, sort_keys=True))
        return 0
    value = capture()
    print(json.dumps({"status": "CAPTURE PASS", "tuple": value["tuple"],
                      "dynamic_selection": value["dynamic_selection"],
                      "dynamic_reads": value["dynamic_reads"]},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CaptureError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"c2-v20-phase02a-site-capture: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
