#!/usr/bin/env python3
"""Capture the one authorized Link-108 phase-1 rescue row, raw first."""

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
OUT = ROOT / "build/c2.3/v2.1-product-liveness-phase1-rescue"
CAPTURE = OUT / "capture.json"
PARTIAL = OUT / "capture.partial.json"
DEVICE = os.environ.get("DEVICE", "/dev/ttyUSB1")
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.1-product-liveness-phase1-successor-preparation-receipt.json")
ELF = ROOT / (
    "build/c2.3/v2.1-product-loading-liveness-card/final/"
    "lisp65-c2-substitution-linked.prg.elf")
RUNNER = ROOT / "scripts/c2-v21-product-liveness-phase1-successor-hw.sh"
CONTACT = ROOT / "build/c2.3/v2.1-product-liveness-phase1-successor"
PRODUCT = CONTACT / "product-readback.d81"
LIBRARY = CONTACT / "library-readback.d81"
AUTHORIZATION_COMMIT = "896aac7d"
AUTHORIZATION_BYTES = 83725
AUTHORIZATION_SHA256 = "cd186510c73a466ae37a4d520e529abbed9608627405fc5ba717d65b215c0d96"
EXPECTED = {
    "preparation": "836daa094c4b8b5d34c215c623287040e091fc785ebe543c3c3613cc883e7376",
    "candidate_ELF": "aef1625af9fbdb335dadeb7f97c72b27c5af8dcd4207c9e4db0d280f3dfab9dc",
    "runner": "a78cfb911466c8a1b7d56b47845503aa23a3bb471a16648cccb38be5d0f9e2b3",
    "product_readback": "74e275ce696765796bafd4844ef67539a75fc0a46ea87b81412ff8bd7e7fc2b1",
    "library_readback": "15e4405929be0686d12c8079509fbd9e12f9314041218ed773fd57b895692060",
}
RANGES = (
    ("bank0-zp-stack", 0x00000000, 0x0200),
    ("pending-error-and-overlay-status", 0x0000BFEF, 9),
    ("c2-boot-runtime", 0x0000C080, 50),
    ("shelf-header-and-max-catalog", 0x08100000, 0x0820),
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


def authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION_COMMIT}:{name}"],
                         cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    full = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION_COMMIT}^{{commit}}"],
                          cwd=ROOT, check=True, text=True,
                          stdout=subprocess.PIPE).stdout.strip()
    require(len(raw) == AUTHORIZATION_BYTES and sha(raw) == AUTHORIZATION_SHA256,
            "phase-1 rescue authorization identity drift")
    for token in (b"rescue read authorized", b"one stop", b"no resume",
                  b"$08100000", b"CPU stays stopped"):
        require(token in raw, f"authorization token absent: {token!r}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def preflight() -> dict[str, Any]:
    bindings = {"preparation": bind(PREP), "candidate_ELF": bind(ELF),
                "runner": bind(RUNNER), "product_readback": bind(PRODUCT),
                "library_readback": bind(LIBRARY)}
    require({k: v["sha256"] for k, v in bindings.items()} == EXPECTED,
            "phase-1 rescue input identity drift")
    require((CONTACT / "contact.consumed").is_file()
            and (CONTACT / "owner-observation-awaiting").is_file(),
            "preserved owner-observed contact markers absent")
    config = json.loads((ROOT / "config/c2-v150-v21-product-liveness-far-device-session.json").read_text())
    require(PRODUCT.read_bytes() == (ROOT / config["identity"]["product_medium"]).read_bytes()
            and LIBRARY.read_bytes() == (ROOT / config["identity"]["library_medium"]).read_bytes(),
            "phase-1 media readback/source mismatch")
    require(not CAPTURE.exists() and not PARTIAL.exists(),
            "phase-1 rescue capture is one-shot")
    source = Path(__file__).read_text(encoding="utf-8")
    capture_source = source.split("\ndef capture() ->", 1)[1].split(
        "\ndef main() ->", 1)[0]
    require(capture_source.count('command(fd, b"t1"') == 1
            and 'command(fd, b"t0"' not in capture_source
            and 'command(fd, b"g"' not in capture_source,
            "capture stop/no-resume source discipline drift")
    return {"authorization": authorization(), **bindings}


def serial_read(fd: int, seconds: float) -> bytes:
    result = bytearray(); deadline = time.monotonic() + seconds
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
    attrs[2] = ((attrs[2]
        & ~(termios.PARENB | termios.CSTOPB | termios.CSIZE | termios.CRTSCTS))
        | termios.CS8 | termios.CLOCAL | termios.CREAD)
    attrs[4] = attrs[5] = termios.B2000000
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    termios.tcflush(fd, termios.TCIOFLUSH)


def command(fd: int, value: bytes, wait: float = 0.04) -> bytes:
    slow_write(fd, value + b"\r"); time.sleep(wait)
    return serial_read(fd, 0.28)


def parse_registers(raw: bytes) -> dict[str, str]:
    match = REGISTER_RE.search(raw)
    require(match is not None, f"full monitor register row absent: {raw!r}")
    names = ("PC", "A", "X", "Y", "Z", "B", "SP", "MAPH", "MAPL")
    widths = (4, 2, 2, 2, 2, 2, 4, 4, 4)
    value = {name: f"0x{int(match.group(i), 16):0{width}x}"
             for i, (name, width) in enumerate(zip(names, widths), 1)}
    value["suffix"] = match.group(10).decode("ascii", errors="replace").strip()
    return value


def monitor_row(fd: int, address: int) -> tuple[bytes, bytes]:
    raw = command(fd, f"m{address:08x}".encode())
    match = re.search(fr":{address:08X}:([0-9A-Fa-f]{{32}})".encode(), raw)
    require(match is not None, f"physical row absent at 0x{address:08x}: {raw!r}")
    return bytes.fromhex(match.group(1).decode()), raw


def persist(value: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PARTIAL.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")


def read_range(fd: int, name: str, address: int, count: int,
               value: dict[str, Any]) -> dict[str, Any]:
    end = address + count; cursor = address; observed = bytearray(); rows = []
    while cursor < end:
        remaining = end - cursor
        start = cursor if remaining >= 16 else max(address, end - 16)
        row, raw = monitor_row(fd, start)
        take_at = cursor - start; take = min(remaining, 16 - take_at)
        require(take > 0, "physical reader made no progress")
        observed.extend(row[take_at:take_at + take])
        rows.append({"command": f"m{start:08x}", "returned_hex": row.hex(),
                     "consumed_offset": take_at, "consumed_bytes": take,
                     "raw_hex": raw.hex()})
        cursor += take
        value["active_range"] = {"name": name, "address": f"0x{address:08x}",
            "requested_bytes": count, "persisted_bytes": len(observed),
            "observed_hex": observed.hex(), "monitor_rows": rows}
        persist(value)
    return {"name": name, "physical_address": f"0x{address:08x}",
            "bytes": count, "observed_hex": observed.hex(),
            "monitor_rows": rows}


def capture() -> dict[str, Any]:
    authority = preflight()
    require(Path(DEVICE).is_char_device(), f"serial device absent: {DEVICE}")
    value: dict[str, Any] = {"format": "lisp65-c2.3-v2.1-phase1-rescue-raw-v1",
        "captured_on": "2026-08-15", "authority": authority,
        "discipline": {"stops": 1, "resumes": 0, "runs": 0, "resets": 0,
            "tuple_before_memory": True, "raw_first": True,
            "CPU_left_stopped": True, "D2_D5_executed": False},
        "device": DEVICE, "reads": []}
    fd = os.open(DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        configure_serial(fd)
        value["stop_raw_hex"] = command(fd, b"t1", 0.08).hex()
        registers_raw = command(fd, b"r", 0.05)
        value["register_raw_hex"] = registers_raw.hex()
        value["tuple"] = parse_registers(registers_raw)
        persist(value)
        for name, address, count in RANGES:
            row = read_range(fd, name, address, count, value)
            value["reads"].append(row); value.pop("active_range", None); persist(value)
    finally:
        os.close(fd)
    value["claim_limit"] = (
        "Raw authorized row only. Phase/error classification belongs to the "
        "separate result binder; CPU remains stopped.")
    CAPTURE.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    PARTIAL.unlink()
    return value


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"preflight", "capture"},
            "usage: c2_v21_phase1_rescue_capture.py preflight|capture")
    if sys.argv[1] == "preflight":
        value = preflight(); print(json.dumps({"status": "PREFLIGHT PASS",
            "device": DEVICE, "authority": value}, indent=2, sort_keys=True))
        return 0
    value = capture()
    print(json.dumps({"status": "CAPTURE PASS", "tuple": value["tuple"],
        "reads": [{"name": r["name"], "bytes": r["bytes"],
                   "sha256": sha(bytes.fromhex(r["observed_hex"]))}
                  for r in value["reads"]]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CaptureError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"c2-v21-phase1-rescue: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
