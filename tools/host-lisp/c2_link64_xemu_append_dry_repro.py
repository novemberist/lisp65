#!/usr/bin/env python3
"""Non-authoritative Xemu dry reproduction of Link 64's Slot-39 failure.

This tool consumes the already-bound diagnostic deployment.  It does not
compile, link, patch, or change product bytes.  Xemu is deliberately only a
triage witness: the receipt may localize a phase error, but it is never metal
or acceptance evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / os.environ.get(
    "C2_XEMU_DEPLOYMENT",
    "build/c2.2/c1-freezer-hardware-link64-cutpoints3-4-attempt4-"
    "NONPROMOTABLE/deployment.json")
OUT = ROOT / os.environ.get(
    "C2_XEMU_OUT",
    "build/c2.2/link64-append-xemu-dry-repro-NONAUTHORITATIVE")
RECEIPT = OUT / "receipt.json"
XEMU = Path(os.environ.get(
    "XMEGA65", os.path.expanduser("~/.local/bin/xmega65")))
SAFE_RUN = ROOT / "scripts/xmega65-safe-run.sh"
SOCKET = Path(f"/tmp/lisp65-link64-xemu-{os.getpid()}.sock")
TIMEOUT = os.environ.get("XMEGA65_TIMEOUT", "240")
BOOT_WAIT_SECONDS = int(os.environ.get("C2_XEMU_BOOT_WAIT_SECONDS", "30"))
MEDIA = (
    ROOT / os.environ["C2_XEMU_D81"]
    if os.environ.get("C2_XEMU_D81") else None)
FORM = os.environ.get(
    "C2_XEMU_FORM", "(defun %c1e () (quote t))")
LABEL = os.environ.get("C2_XEMU_LABEL", "Link-64")
RECEIPT_FORMAT = os.environ.get(
    "C2_XEMU_RECEIPT_FORMAT",
    "lisp65-c2-link64-xemu-append-dry-repro-v1")
PHASE_SCRATCH = 0xC0C6
PHASE_SCRATCH_BYTES = 304
C2J = 0x5C640
C2J_BYTES = 64
RECORD_OFFSET = 182


class ReproError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReproError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


class Monitor:
    MATRIX = {
        "a": 10, "b": 28, "c": 20, "d": 18, "e": 14, "f": 21,
        "g": 26, "h": 29, "i": 33, "j": 34, "k": 37, "l": 42,
        "m": 36, "n": 39, "o": 38, "p": 41, "q": 62, "r": 17,
        "s": 13, "t": 22, "u": 30, "v": 31, "w": 9, "x": 23,
        "y": 25, "z": 12,
        "0": 35, "1": 56, "2": 59, "3": 8, "4": 11, "5": 16,
        "6": 19, "7": 24, "8": 27, "9": 32,
        " ": 60, "\r": 1, "+": 40, "-": 43, "*": 49, "/": 55,
        "=": 53, ".": 44, ",": 47, ":": 45, ";": 50,
    }
    SHIFTED = {
        "(": "8", ")": "9", "<": ",", ">": ".", '"': "2", "!": "1",
        "%": "5",
    }

    def __init__(self, path: Path):
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.connect(path.as_posix())
        self.socket.settimeout(3)

    def command(self, value: str, wait: float = 0.03) -> str:
        self.socket.sendall(value.encode() + b"\r")
        time.sleep(wait)
        result = bytearray()
        try:
            while True:
                chunk = self.socket.recv(65536)
                if not chunk:
                    break
                result.extend(chunk)
                if result.rstrip().endswith(b"."):
                    break
        except socket.timeout:
            pass
        return result.decode(errors="replace")

    def poke(self, address: int, value: bytes, chunk_bytes: int = 64) -> None:
        for offset in range(0, len(value), chunk_bytes):
            part = value[offset:offset + chunk_bytes]
            command = "s%x %s" % (
                address + offset, " ".join(f"{byte:02x}" for byte in part))
            self.socket.sendall(command.encode() + b"\r")
            response = bytearray()
            deadline = time.time() + 5
            while b"." not in response and time.time() < deadline:
                try:
                    response.extend(self.socket.recv(65536))
                except socket.timeout:
                    continue
            require(b"." in response,
                    f"Xemu monitor did not acknowledge write at "
                    f"0x{address + offset:08x}")

    def read(self, address: int, length: int) -> bytes:
        result = bytearray()
        cursor = address
        while len(result) < length:
            response = self.command(f"m{cursor:x}")
            matched = False
            for row in re.finditer(
                    r":([0-9A-Fa-f]{8}):([0-9A-Fa-f]+)", response):
                row_address = int(row.group(1), 16)
                data = bytes.fromhex(row.group(2))
                if row_address <= cursor < row_address + len(data):
                    result.extend(data[cursor - row_address:])
                    cursor = row_address + len(data)
                    matched = True
            require(matched,
                    f"Xemu monitor dump unreadable at 0x{cursor:08x}")
        return bytes(result[:length])

    def type_line(self, value: str) -> None:
        for original in value + "\r":
            character = (
                original if original in self.SHIFTED else original.lower())
            shifted = character in self.SHIFTED
            key = self.SHIFTED[character] if shifted else character
            require(key in self.MATRIX,
                    f"no Xemu matrix binding for {original!r}")
            if shifted:
                self.command("sffd3616 0f")
            self.command(f"sffd3615 {self.MATRIX[key]:02x}")
            self.command("sffd3615 7f")
            if shifted:
                self.command("sffd3616 7f")
        time.sleep(0.5)


def screen_text(monitor: Monitor) -> str:
    raw = monitor.read(0x0800, 2000)

    def decode(byte: int) -> str:
        byte &= 0x7f
        if 1 <= byte <= 26:
            return chr(ord("a") + byte - 1)
        if byte == 0:
            return "@"
        if 32 <= byte <= 63:
            return chr(byte)
        return " "

    return "".join(map(decode, raw))


def crc16(data: bytes) -> int:
    crc = 0xffff
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xffff \
                if crc & 0x8000 else (crc << 1) & 0xffff
    return crc


def start_xemu() -> subprocess.Popen[bytes]:
    if SOCKET.exists():
        SOCKET.unlink()
    command = [
        SAFE_RUN.as_posix(), SOCKET.as_posix(), TIMEOUT, XEMU.as_posix(),
        "-headless", "-testing", "-sleepless", "-besure", "-fastboot",
        "-uartmon", SOCKET.as_posix(),
    ]
    if MEDIA is not None:
        command.extend(["-8", MEDIA.as_posix()])
    return subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)


def stop_xemu(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass


def parse_address(value: str) -> int:
    return int(value, 16)


def main() -> int:
    deployment = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    product_path = ROOT / deployment["product"]["path"]
    product = product_path.read_bytes()
    require((product[0] | product[1] << 8) == 0x2001,
            f"{LABEL} PRG is not based at $2001")
    payload = product[2:]
    basic = re.search(rb"\x9e\s*(\d+)", payload)
    require(basic is not None, f"{LABEL} BASIC SYS address absent")
    sys_address = basic.group(1).decode()
    for item in deployment["preloads"]:
        path = ROOT / item["path"]
        require(path.stat().st_size == item["bytes"]
                and sha256(path) == item["sha256"],
                f"deployment preload drift: {path}")
    require(sha256(product_path) == deployment["product"]["sha256"],
            f"{LABEL} product drift")
    if MEDIA is not None:
        require(MEDIA.is_file(), f"{LABEL} D81 absent: {MEDIA}")

    OUT.mkdir(parents=True, exist_ok=True)
    process = start_xemu()
    try:
        for _ in range(80):
            if SOCKET.exists():
                break
            time.sleep(0.25)
        require(SOCKET.exists(), "Xemu monitor socket did not appear")
        time.sleep(2)
        monitor = Monitor(SOCKET)
        for _ in range(50):
            if "ready" in screen_text(monitor):
                break
            monitor.type_line("")
            time.sleep(0.5)
        else:
            raise ReproError("Xemu did not reach BASIC READY")

        for item in deployment["preloads"]:
            path = ROOT / item["path"]
            address = parse_address(item["address"])
            value = path.read_bytes()
            print(
                f"xemu preload {path.name}: {len(value)} bytes "
                f"at 0x{address:08x}", flush=True)
            monitor.poke(address, value)
            require(monitor.read(address, min(16, len(value))) ==
                    value[:min(16, len(value))],
                    f"Xemu preload readback failed: {path}")
        monitor.poke(0x2001, payload)
        print(f"xemu product: {len(payload)} bytes at 0x00002001",
              flush=True)
        require(monitor.read(0x2001, 16) == payload[:16],
                "Xemu product upload readback failed")
        monitor.type_line(f"SYS {sys_address}")
        # A full Screen-RAM dump is intentionally not used as a poll: uartmon
        # serves it as many small transactions, so observation would dominate
        # the safe-run deadline.  One snapshot after the measured boot window
        # is both cheaper and less intrusive.
        time.sleep(BOOT_WAIT_SECONDS)
        boot_screen = screen_text(monitor)
        (OUT / "boot-screen.txt").write_text(
            boot_screen, encoding="utf-8")
        require("lisp65>" in boot_screen,
                f"{LABEL} did not reach its REPL in Xemu; "
                f"screen tail={boot_screen.rstrip()[-240:]!r}")

        form = FORM
        monitor.type_line(form)
        time.sleep(8)
        final_screen = screen_text(monitor)
        phase = monitor.read(PHASE_SCRATCH, PHASE_SCRATCH_BYTES)
        c2j = monitor.read(C2J, C2J_BYTES)
        (OUT / "phase-scratch.bin").write_bytes(phase)
        (OUT / "c2j.bin").write_bytes(c2j)
        (OUT / "screen.txt").write_text(final_screen, encoding="utf-8")
        record = phase[RECORD_OFFSET:RECORD_OFFSET + 32]
        value = {
            "format": RECEIPT_FORMAT,
            "recorded_on": "2026-07-25",
            "status": (
                "NONAUTHORITATIVE-XEMU-REPRODUCED"
                if "bad bytecode" in final_screen
                else "NONAUTHORITATIVE-XEMU-NOT-REPRODUCED"),
            "claim_limit": (
                "Xemu-only triage. Not hardware, product-link, promotion, "
                "matrix, latency, or acceptance evidence."),
            "authority": {
                "deployment": bind(DEPLOYMENT),
                "product": bind(product_path),
                "driver": bind(Path(__file__)),
                **({"media": bind(MEDIA)} if MEDIA is not None else {}),
            },
            "execution": {
                "compiler_runs": 0,
                "linker_runs": 0,
                "product_bytes_changed": 0,
                "hardware_runs": 0,
                "xemu_runs": 1,
                "form": form,
                "basic_SYS": sys_address,
            },
            "observed": {
                "bad_bytecode_visible": "bad bytecode" in final_screen,
                "slot_stamp": phase[0x12e],
                "completion": {
                    "mode": f"0x{record[24]:02x}",
                    "producer_seal": f"0x{record[25] | record[26] << 8:04x}",
                    "retired_record_27": f"0x{record[27]:02x}",
                    "journal_result": record[31],
                },
                "C2J": {
                    "hex": c2j.hex(),
                    "crc16": f"0x{crc16(c2j):04x}",
                    "magic": c2j[:4].decode(errors="replace"),
                },
                "screen_tail": final_screen.rstrip()[-600:],
            },
            "captures": {
                "phase_scratch": bind(OUT / "phase-scratch.bin"),
                "C2J": bind(OUT / "c2j.bin"),
                "screen": bind(OUT / "screen.txt"),
            },
        }
        RECEIPT.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0
    finally:
        stop_xemu(process)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            ReproError) as error:
        OUT.mkdir(parents=True, exist_ok=True)
        value = {
            "format": RECEIPT_FORMAT,
            "recorded_on": "2026-07-25",
            "status": "FIRST-RED-NONAUTHORITATIVE-XEMU-SILENT",
            "claim_limit": (
                f"Xemu did not reach the {LABEL} REPL. This is tool/emulator "
                "evidence only and supports no product, hardware, matrix, "
                "latency, promotion, acceptance, or release inference."),
            "authority": {
                "deployment": bind(DEPLOYMENT),
                "driver": bind(Path(__file__)),
            },
            "execution": {
                "compiler_runs": 0,
                "linker_runs": 0,
                "product_bytes_changed": 0,
                "hardware_runs": 0,
                "xemu_runs": 1,
            },
            "first_red": str(error),
        }
        RECEIPT.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print(f"{LABEL}-xemu-dry-repro: FIRST RED: {error}")
        raise SystemExit(2)
