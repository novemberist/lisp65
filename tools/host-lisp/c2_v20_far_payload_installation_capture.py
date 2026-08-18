#!/usr/bin/env python3
"""Capture the one authorised physical far-LMA installation row.

The machine is already stopped.  This driver first binds the authorising git
blob and every host/media identity, then reads the complete register tuple.
Only an exact tuple match permits five physical-memory monitor reads: two rows
straddling the former staging end and one row at each of the far service's
head, middle, and tail.  It never issues stop, run, reset, or resume commands.
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
import tempfile
import termios
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build/c2.3/v2.0-far-payload-d1-hw/far-lma-installation"
CAPTURE = OUT / "capture.json"
DEVICE = os.environ.get("DEVICE", "/dev/ttyUSB1")

PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
AUTHORIZATION_COMMIT = "5960d2c7"
AUTHORIZATION_SHA256 = (
    "75029f751bd268e0ae206d0599df2499d68299d685c24f59d4d84b2a2791086e")
AUTHORIZATION_BYTES = 40396

PRIOR_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-far-payload-device-receipt.json")
PRIOR_RECEIPT_SHA256 = (
    "0303351b6b420b5fcbe59500aca040c4ee419706b16606ef87e094033bbc87ba")
PRODUCT_READBACK = ROOT / "build/c2.3/v2.0-far-payload-d1-hw/product-readback.d81"
PRODUCT_D81_SHA256 = (
    "d2ab92b14140caab5f3ca87b51fa8e4ab65183b387d6fe76ee4ae1588fcd1130")
DELIVERED = ROOT / (
    "build/c2.3/v2.0-far-payload-delivery/product-inputs/"
    "bank2-static-code.bin")
DELIVERED_SHA256 = (
    "94479944eb6f8ece405be2902a424961b72e1936534ecd6acb0e8a2287a9c4ec")
ELF = ROOT / (
    "build/c2.3/v2.0-crc-carveout-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
ELF_SHA256 = (
    "34fb0a1173d66c2779ec7778ab0ab208bda7fd9a407989e2bb31660e71af4080")
SERVICE_SHA256 = (
    "2e948761a4c7f012687a6ad4519ae10d52ee87e14a10f8025837078f0c69c096")
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"
SERVICE_SECTION = ".lisp65_c2_mapped_far_service"

DESTINATION = 0x00020000
OLD_END_EXCLUSIVE = 0x0002B3DB
SERVICE_START = 0x0002B8B2
SERVICE_END_EXCLUSIVE = 0x0002BC1C
SERVICE_BYTES = SERVICE_END_EXCLUSIVE - SERVICE_START

EXPECTED_STABLE_TUPLE = {
    "A": "0x02", "X": "0x00", "Y": "0xb4",
    "Z": "0x00", "B": "0x00", "SP": "0x01c9", "MAPH": "0x8000",
    "MAPL": "0x2480",
}
# The monitor exposes the CPU pipeline PC: during ``JMP $E096`` it may report
# the opcode, either operand byte, or the post-operand PC before the branch
# target is committed.
FAIL_LOOP_PC = {"0xe096", "0xe097", "0xe098", "0xe099"}

# The two old-tail rows straddle the former exclusive end.  The service rows
# sample its first 16 bytes, a 16-byte row containing the exact midpoint, and
# its final 16 bytes.
PROBES = (
    ("old-extent-tail", OLD_END_EXCLUSIVE - 16, 16),
    ("old-extent-after", OLD_END_EXCLUSIVE, 16),
    ("far-service-head", SERVICE_START, 16),
    ("far-service-middle", SERVICE_START + 0x1AE, 16),
    ("far-service-tail", SERVICE_END_EXCLUSIVE - 16, 16),
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


def bind_git_blob(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    require(len(raw) == AUTHORIZATION_BYTES and sha(raw) == AUTHORIZATION_SHA256,
            "authorization blob identity drift")
    require(b"Installation read authorized" in raw,
            "installation-read authorization absent")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def bind_prior_result() -> dict[str, Any]:
    """Bind the exact predecessor receipt present when the row was authorised."""
    name = PRIOR_RECEIPT.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION_COMMIT}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    require(len(raw) == 7410 and sha(raw) == PRIOR_RECEIPT_SHA256,
            "authorised predecessor result identity drift")
    return {"path": name, "bytes": len(raw), "sha256": sha(raw)}


def expected_rows() -> tuple[dict[str, bytes], dict[str, Any]]:
    authorization = bind_git_blob(AUTHORIZATION_COMMIT, PLAN)
    prior = bind_prior_result()
    product = bind(PRODUCT_READBACK)
    delivered_binding = bind(DELIVERED)
    elf = bind(ELF)
    require(prior["sha256"] == PRIOR_RECEIPT_SHA256,
            "prior stopped-state authority drift")
    require(product["sha256"] == PRODUCT_D81_SHA256,
            "product D81 readback identity drift")
    require(delivered_binding["sha256"] == DELIVERED_SHA256,
            "delivered Bank-2 identity drift")
    require(elf["sha256"] == ELF_SHA256, "frozen candidate ELF identity drift")
    delivered = regular(DELIVERED)
    require(len(delivered) == SERVICE_END_EXCLUSIVE - DESTINATION,
            "delivered Bank-2 extent drift")
    with tempfile.TemporaryDirectory(prefix="c2-v20-far-lma-") as temp:
        service_path = Path(temp) / "service.bin"
        output_elf = Path(temp) / "output.elf"
        subprocess.run(
            [str(OBJCOPY), "--dump-section",
             f"{SERVICE_SECTION}={service_path}", str(ELF), str(output_elf)],
            cwd=ROOT, check=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        service = regular(service_path)
    require(len(service) == SERVICE_BYTES and sha(service) == SERVICE_SHA256,
            "ELF far-service section identity drift")
    require(delivered[SERVICE_START - DESTINATION:
                      SERVICE_END_EXCLUSIVE - DESTINATION] == service,
            "delivered far-service bytes differ from frozen ELF")
    rows: dict[str, bytes] = {}
    for name, address, count in PROBES:
        if SERVICE_START <= address < SERVICE_END_EXCLUSIVE:
            offset = address - SERVICE_START
            rows[name] = service[offset:offset + count]
        else:
            offset = address - DESTINATION
            rows[name] = delivered[offset:offset + count]
        require(len(rows[name]) == count, f"expected probe truncated: {name}")
    return rows, {
        "authorization": authorization, "prior_result": prior,
        "product_D81_readback": product, "delivered_Bank2": delivered_binding,
        "frozen_candidate_ELF": elf,
        "far_service": {"section": SERVICE_SECTION, "bytes": len(service),
                        "sha256": sha(service)},
    }


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
    fcntl.fcntl(
        fd, fcntl.F_SETFL,
        fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)
    attrs = termios.tcgetattr(fd)
    attrs[0] = attrs[1] = attrs[3] = 0
    attrs[2] = (
        attrs[2]
        & ~(termios.PARENB | termios.CSTOPB | termios.CSIZE
            | termios.CRTSCTS)
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
    return {name: f"0x{int(match.group(index), 16):0{width}x}"
            for index, (name, width) in enumerate(zip(names, widths), 1)}


def read_row(fd: int, address: int, count: int) -> tuple[bytes, bytes]:
    require(count <= 16, "monitor row cannot exceed 16 bytes")
    raw = command(fd, f"m{address:08x}".encode())
    match = re.search(fr":{address:08X}:([0-9A-Fa-f]{{32}})".encode(), raw)
    require(match is not None,
            f"physical memory row absent at 0x{address:08x}: {raw!r}")
    return bytes.fromhex(match.group(1).decode())[:count], raw


def capture() -> dict[str, Any]:
    require(not CAPTURE.exists(), "installation capture is one-shot")
    expected, authority = expected_rows()
    require(Path(DEVICE).is_char_device(), f"serial device absent: {DEVICE}")
    fd = os.open(DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        configure_serial(fd)
        registers_raw = command(fd, b"r")
        registers = parse_registers(registers_raw)
        stable = {name: registers[name] for name in EXPECTED_STABLE_TUPLE}
        require(stable == EXPECTED_STABLE_TUPLE
                and registers["PC"] in FAIL_LOOP_PC,
                f"preserved tuple mismatch; no memory read: {registers}")
        reads = []
        for name, address, count in PROBES:
            observed, raw = read_row(fd, address, count)
            reads.append({
                "name": name, "physical_address": f"0x{address:08x}",
                "bytes": count, "command": f"m{address:08x}",
                "observed_hex": observed.hex(),
                "expected_hex": expected[name].hex(),
                "byteidentical": observed == expected[name],
                "raw_hex": raw.hex(),
            })
    finally:
        os.close(fd)
    by_name = {row["name"]: row for row in reads}
    service = [by_name[name] for name in (
        "far-service-head", "far-service-middle", "far-service-tail")]
    if all(row["byteidentical"] for row in service):
        outcome = "PRESENT"
    elif all(not row["byteidentical"] for row in service):
        outcome = "ABSENT"
    else:
        outcome = "PARTIAL-OR-AMBIGUOUS"
    return {
        "format": "lisp65-c2.3-v20-far-lma-installation-capture-v1",
        "captured_on": "2026-08-13", "authority": authority,
        "discipline": {"register_tuple_first": True, "stops": 0,
                       "resumes": 0, "runs": 0, "resets": 0,
                       "CPU_left_stopped": True},
        "tuple_contract": {
            "stable_fields": EXPECTED_STABLE_TUPLE,
            "PC_instruction_identity": "JMP $E096",
            "accepted_PC_bytes": sorted(FAIL_LOOP_PC),
            "pre_read_first_reds": [
                {"observed_PC": "0xe098", "memory_reads": 0,
                 "cause": "historical single-byte PC pin inside one instruction"},
                {"observed_PC": "0xe099", "memory_reads": 0,
                 "cause": "post-operand pipeline PC omitted from instruction identity"},
            ],
        },
        "tuple": registers, "register_raw_hex": registers_raw.hex(),
        "reads": reads, "decision": {
            "service_probe_rows": 3,
            "service_probe_matches": sum(row["byteidentical"] for row in service),
            "outcome": outcome,
        },
        "claim_limit": (
            "One preserved-state read-only row.  PRESENT proves the sampled "
            "far-service LMA bytes are installed; ABSENT proves none of the "
            "three ELF-bound service probes match.  No service-entry, product-"
            "fault, fix, D2-D5, resume, or release-readiness claim."),
    }


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"preflight", "capture"},
            "usage: c2_v20_far_payload_installation_capture.py preflight|capture")
    if sys.argv[1] == "preflight":
        rows, authority = expected_rows()
        print(json.dumps({"status": "PREFLIGHT PASS", "device": DEVICE,
                          "authority": authority,
                          "expected": {name: raw.hex()
                                       for name, raw in rows.items()}},
                         indent=2, sort_keys=True))
        return 0
    value = capture()
    OUT.mkdir(parents=True, exist_ok=True)
    CAPTURE.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    for row in value["reads"]:
        (OUT / f"{row['name']}.bin").write_bytes(
            bytes.fromhex(row["observed_hex"]))
    (OUT / "registers.raw").write_bytes(bytes.fromhex(value["register_raw_hex"]))
    print(json.dumps({"status": "CAPTURE PASS", "tuple": value["tuple"],
                      "decision": value["decision"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CaptureError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"far-LMA installation capture: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
