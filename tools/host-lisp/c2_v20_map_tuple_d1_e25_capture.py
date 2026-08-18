#!/usr/bin/env python3
"""Run the one authorised stopped-state E25 discriminator row.

Preflight is host-only.  Capture performs exactly one ``t1``, never resumes,
binds the complete monitor tuple, and only then reads the four physical
Bank-0 ranges named by the committed row contract.
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
OUT = ROOT / "build/c2.3/v2.0-map-tuple-d1/e25-stopped-state"
CAPTURE = OUT / "capture.json"
DEVICE = os.environ.get("DEVICE", "/dev/ttyUSB1")

PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
ROW = ROOT / "config/c2-v20-map-tuple-d1-e25-capture-row.json"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-map-tuple-d1-e25-first-red-receipt.json")
ELF = ROOT / (
    "build/c2.3/v2.0-map-tuple-fix-replacement-card/final/"
    "lisp65-c2-substitution-linked.prg.elf")
PRODUCT_READBACK = ROOT / "build/c2.3/v2.0-map-tuple-d1/product-readback.d81"
LIBRARY_READBACK = ROOT / "build/c2.3/v2.0-map-tuple-d1/library-readback.d81"
SCREEN = ROOT / "build/c2.3/v2.0-map-tuple-d1/product-boot.png"

AUTHORIZATION_COMMIT = "7478ce73"
AUTHORIZATION_BYTES = 46061
AUTHORIZATION_SHA256 = (
    "815e03b7b001bca54d80ef394a572fae6972f23130c950306cc40fca9a67ba65")
ROW_SHA256 = (
    "59d1ecc001bbca3f8c2720a2fabf7e075dc9985285e1fa921a7de607f68bc777")
FIRST_RED_SHA256 = (
    "bf96614c9c56c601bdff5b6c1798baffae2a2b580513bce55a76ec5ad147c0cf")
ELF_SHA256 = (
    "a481eff4acd32f04dde6660090aa2761a2f4a4b6307945cbcb2cda0f70435673")
PRODUCT_SHA256 = (
    "43da1ce57ced3088a56349c84d3b0c32bbc25f1aae34928b808fe31af8462a95")
LIBRARY_SHA256 = (
    "15e4405929be0686d12c8079509fbd9e12f9314041218ed773fd57b895692060")
SCREEN_SHA256 = (
    "27225182cc1222b075900be7dbb69099ddb20d89e0c13d839bbc683889d09a7a")

RANGES = (
    ("boot-publication-zp", 0x002E, 9),
    ("roots-ready-oom-zp", 0x008A, 6),
    ("pending-error-pointer", 0xBFEF, 2),
    ("c2-boot-runtime", 0xC080, 50),
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
            "authorization blob identity drift")
    require(b"E25 stopped-state read authorized" in raw
            and all(token in raw for token in (
                b"one stop", b"no resume", b"no reset")),
            "stopped-state authorization language absent")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def preflight() -> dict[str, Any]:
    authority = git_authorization()
    bindings = {
        "capture_contract": bind(ROW),
        "first_red": bind(FIRST_RED),
        "candidate_ELF": bind(ELF),
        "product_D81_readback": bind(PRODUCT_READBACK),
        "library_D81_readback": bind(LIBRARY_READBACK),
        "screen": bind(SCREEN),
    }
    expected = {
        "capture_contract": ROW_SHA256,
        "first_red": FIRST_RED_SHA256,
        "candidate_ELF": ELF_SHA256,
        "product_D81_readback": PRODUCT_SHA256,
        "library_D81_readback": LIBRARY_SHA256,
        "screen": SCREEN_SHA256,
    }
    require({name: row["sha256"] for name, row in bindings.items()} == expected,
            "E25 input identity drift")
    row = json.loads(regular(ROW))
    require(row["status"] == "host-specified-owner-authorization-pending",
            "committed row must remain non-self-authorizing")
    actual_ranges = tuple(
        (item["name"], int(item["address"], 0), item["bytes"])
        for item in row["physical_bank0_ranges"])
    require(actual_ranges == RANGES, "authorized physical range drift")
    require(row["observation"]["stop_count"] == 1
            and row["observation"]["resume_count"] == 0,
            "authorized stop/resume count drift")
    require(not CAPTURE.exists(), "E25 stopped-state capture is one-shot")
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


def capture() -> dict[str, Any]:
    authority = preflight()
    require(Path(DEVICE).is_char_device(), f"serial device absent: {DEVICE}")
    fd = os.open(DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        configure_serial(fd)
        stop_raw = command(fd, b"t1", 0.08)
        registers_raw = command(fd, b"r", 0.05)
        registers = parse_registers(registers_raw)
        reads = []
        for name, address, count in RANGES:
            observed, commands = read_range(fd, address, count)
            reads.append({"name": name, "physical_address": f"0x{address:08x}",
                          "bytes": count, "observed_hex": observed.hex(),
                          "monitor_rows": commands})
    finally:
        os.close(fd)
    value = {
        "format": "lisp65-c2.3-v20-map-tuple-d1-e25-capture-v1",
        "captured_on": "2026-08-13",
        "authority": authority,
        "discipline": {"stops": 1, "resumes": 0, "runs": 0, "resets": 0,
                       "tuple_before_memory": True, "CPU_left_stopped": True,
                       "D2_D5_executed": False},
        "device": DEVICE,
        "tuple": registers,
        "stop_raw_hex": stop_raw.hex(),
        "register_raw_hex": registers_raw.hex(),
        "reads": reads,
        "claim_limit": "Raw authorized row only; classification belongs to the separately gated result binder.",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    CAPTURE.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    return value


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"preflight", "capture"},
            "usage: c2_v20_map_tuple_d1_e25_capture.py preflight|capture")
    if sys.argv[1] == "preflight":
        print(json.dumps({"status": "PREFLIGHT PASS", "device": DEVICE,
                          "authority": preflight()}, indent=2, sort_keys=True))
        return 0
    value = capture()
    print(json.dumps({"status": "CAPTURE PASS", "tuple": value["tuple"],
                      "reads": [{"name": row["name"],
                                 "observed_hex": row["observed_hex"]}
                                for row in value["reads"]]},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CaptureError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"c2-v20-map-tuple-d1-e25-capture: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
