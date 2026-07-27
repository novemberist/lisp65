#!/usr/bin/env python3
"""Bind the C2-lite cold-stager handoff to the final product entry.

The v8 hardware replay proved all three Chip-RAM targets byte-identical, then
returned from the product chain to the stager's terminal error loop.  The
linked chain jumped to $2026 although the final product manifest and C-side
C2-lite contract both name $2023.  This tool records that first red and builds
a fresh acceptance-tool-only media identity with the profile-bound entry.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import termios
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_media_product as MEDIA  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


BUILD = ROOT / "build/c2.2/acceptance/g5/entry-bound-repack-v9"
RECEIPT = BUILD / "g5-entry-bound-repack-receipt.json"
RUNBOOK = BUILD / "g5-runbook.json"
V8 = ROOT / "build/c2.2/acceptance/g5/rom-write-enable-repack-v8"
V8_RECEIPT = V8 / "g5-rom-write-enable-repack-receipt.json"
V8_RUNBOOK = V8 / "g5-runbook.json"
V8_ELF = Path(str(V8 / "autoboot.c65") + ".elf")
V8_CAPTURE = (
    ROOT / "build/c2.2/acceptance/g5/replay-v8-rom-write-enable/"
    "first-red-readback"
)
V8_PC = V8_CAPTURE / "pc-register.json"
R5 = ROOT / "build/c2.2/acceptance/r5"
R5_PREFLIGHT = R5 / "r5-preflight-receipt.json"
DEVICE = "/dev/ttyUSB1"


class RepackError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RepackError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"entry-bound authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def configure() -> None:
    MEDIA.BUILD = BUILD
    MEDIA.MANIFEST = BUILD / "candidate-manifest.json"
    MEDIA.DESCRIPTOR = BUILD / "boot.id"
    MEDIA.STAGER = BUILD / "autoboot.c65"
    MEDIA.STAGER_MAP = BUILD / "autoboot.c65.map"
    MEDIA.PRODUCT_D81 = BUILD / "lisp65-product.d81"
    MEDIA.WORK_D81 = BUILD / "lisp65-work.d81"
    MEDIA.MOUNT = BUILD / "lisp65-product.mount.json"


def serial_read(fd: int, seconds: float) -> bytes:
    result = b""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            result += os.read(fd, 65536)
        except BlockingIOError:
            pass
        time.sleep(0.005)
    return result


def slow_write(fd: int, value: bytes) -> None:
    for byte in value:
        os.write(fd, bytes((byte,)))
        time.sleep(0.001)


def capture_v8_pc() -> dict[str, Any]:
    require(not V8_PC.exists(), "v8 PC capture is one-shot")
    fd = os.open(DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        fcntl.fcntl(
            fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)
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
        slow_write(fd, b"\x15#\r")
        time.sleep(0.05)
        serial_read(fd, 0.2)
        token = b"#g5v8entry\r"
        slow_write(fd, token)
        require(token in serial_read(fd, 0.5),
                "serial monitor synchronisation failed")
        slow_write(fd, b"t1\r")
        time.sleep(0.02)
        slow_write(fd, b"r\r")
        raw = serial_read(fd, 0.7)
        slow_write(fd, b"t0\r")
        serial_read(fd, 0.1)
    finally:
        os.close(fd)
    match = re.search(rb"\n,[0-9A-Fa-f]{4}([0-9A-Fa-f]{4})", raw)
    require(match is not None, "v8 PC absent from monitor response")
    pc = int(match.group(1), 16)
    value = {
        "format": "lisp65-c2-lite-G5-v8-first-red-PC-v1",
        "captured_at_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "device": DEVICE,
        "PC": f"0x{pc:04x}",
        "raw_hex": raw.hex(),
        "monitor_effect": "t1/r/t0 register sample; execution resumed",
    }
    V8_PC.write_bytes(json_bytes(value))
    return value


def v8_attribution() -> dict[str, Any]:
    pc = json.loads(V8_PC.read_text(encoding="utf-8"))
    full = V8_CAPTURE / "full"
    pairs = (
        (full / "bank2-full.bin",
         R5 / "product/01-bank2-static-code.bin"),
        (full / "bank5-c2d.bin",
         R5 / "product/09-initial.c2d-v6.bin"),
        (full / "bank5-bootstage.bin",
         R5 / "product/08-bootstage.bin"),
    )
    require(all(a.read_bytes() == b.read_bytes() for a, b in pairs),
            "v8 Chip-RAM target identity drift")
    stack = (full / "stack.bin").read_bytes()
    require(
        len(stack) == 32 and stack[0x0C:0x0E] == bytes.fromhex("9926"),
        "v8 terminal-error caller return address drift")
    old = (
        ROOT / "build/c2.2/acceptance/g5/replay-v7/"
        "first-red-readback/bank2-prefix-live.bin"
    ).read_bytes()
    expected = (R5 / "product/01-bank2-static-code.bin").read_bytes()
    old_differences = sum(a != b for a, b in zip(old, expected))
    v8_manifest = json.loads(
        (V8 / "candidate-manifest.json").read_text(encoding="utf-8"))
    truth = ElfTruth.read(
        V8_ELF, llvm_readobj=MEDIA.CANONICAL.COMPILER.parent / "llvm-readobj",
        include_section_data=True)
    chain = truth.section_bytes(".r3_chain_trampoline")
    require(
        pc["PC"] in ("0x2998", "0x2999")
        and b" 01EB " in bytes.fromhex(pc["raw_hex"])
        and chain[-3:] == bytes.fromhex("4c2620")
        and v8_manifest["stager"]["product_entry"] == "0x2023"
        and old_differences == 251,
        "v8 entry-profile attribution drift")
    return {
        "status": "hardware-first-red-wrong-profile-entry",
        "PC": pc,
        "caller_return": "0x2699-after-chain-return",
        "linked_terminal_jump": "JMP $2026",
        "final_product_entry": "0x2023",
        "entry_delta_bytes": 3,
        "targets_byteidentical": [bind(a) for a, _ in pairs],
        "v7_old_bank2_differences_of_254": old_differences,
        "v7_coincidental_equal_offsets": [140, 168, 189],
        "authority": {
            "v8_manifest": bind(V8 / "candidate-manifest.json"),
            "v8_elf": bind(V8_ELF),
            "pc": bind(V8_PC),
            "stack": bind(full / "stack.bin"),
        },
    }


def scope(value: dict[str, Any]) -> dict[str, Any]:
    r5 = json.loads(R5_PREFLIGHT.read_text(encoding="utf-8"))
    before = {
        row["role"]: row["sha256"] for row in r5["materialized_artifacts"]}
    after = {row["role"]: row["sha256"] for row in value["artifacts"]}
    changed = {role for role in before if before[role] != after[role]}
    handoff = value["stager"]["gate"]["chain_handoff"]
    require(
        changed == {
            "cold-stager", "product-d81", "product-mount-descriptor"}
        and handoff["status"] == "passed-profile-bound-final-product-entry"
        and handoff["product_entry"] == "0x2023"
        and handoff["terminal_jump_bytes"] == "4c2320"
        and handoff["wrong_profile_entry"] == "0x2026"
        and handoff["wrong_profile_mutations_rejected"] == 1
        and value["execution_accounting"]["product_compiler_runs"] == 0
        and value["execution_accounting"]["product_linker_runs"] == 0,
        "entry-bound G5 scope/gate drift")
    return {
        "changed_roles": sorted(changed),
        "unchanged_roles": len(before) - len(changed),
        "product_byte_changes": 0,
        "product_compiler_runs": 0,
        "product_linker_runs": 0,
    }


def build() -> dict[str, Any]:
    require(not BUILD.exists(), "G5 entry-bound repack is one-shot")
    for path in (V8_RECEIPT, V8_RUNBOOK, R5_PREFLIGHT, V8_PC):
        require(path.is_file(), f"required predecessor absent: {path}")
    finding = v8_attribution()
    value = MEDIA.build()
    MEDIA.check()
    changed = scope(value)
    previous = json.loads(V8_RUNBOOK.read_text(encoding="utf-8"))
    runbook = {
        **previous,
        "status": "ready-G5-hardware-replay-after-entry-profile-binding",
        "artifact_set_sha256": value["artifact_set_sha256"],
        "product_d81": MEDIA.PRODUCT_D81.relative_to(ROOT).as_posix(),
        "work_d81": MEDIA.WORK_D81.relative_to(ROOT).as_posix(),
        "mount_descriptor": MEDIA.MOUNT.relative_to(ROOT).as_posix(),
        "supersedes": bind(V8_RUNBOOK),
        "entry_profile_fix": value["stager"]["gate"]["chain_handoff"],
        "tool_fix_scope": changed,
    }
    RUNBOOK.write_bytes(json_bytes(runbook))
    receipt = {
        "format": "lisp65-c2-lite-G5-entry-bound-repack-v1",
        "recorded_on": "2026-07-26",
        "status": "passed-host-repack-hardware-not-run",
        "cause": finding,
        "fix": {
            **value["stager"]["gate"]["chain_handoff"],
            "profile_specific_generated_include":
                value["stager"]["gate"]["assembler_C_contract"],
            "scope": changed,
        },
        "candidate": {
            "manifest": bind(MEDIA.MANIFEST),
            "runbook": bind(RUNBOOK),
            "stager": bind(MEDIA.STAGER),
            "stager_elf": bind(Path(str(MEDIA.STAGER) + ".elf")),
            "stager_map": bind(MEDIA.STAGER_MAP),
            "product_d81": bind(MEDIA.PRODUCT_D81),
            "work_d81": bind(MEDIA.WORK_D81),
            "mount": bind(MEDIA.MOUNT),
        },
        "gates": {
            "chain_handoff": value["stager"]["gate"]["chain_handoff"],
            "ROM_write_boundary":
                value["stager"]["gate"]["rom_backing_write_enable"],
            "transport": value["stager"]["gate"]["linked_transport"],
            "complete_media": value["status"],
        },
        "execution_accounting": value["execution_accounting"],
        "claim_limit": (
            "G5 acceptance-tool identity only. No product compile, product "
            "link, product-byte change, G5/G6 or release claim occurred."
        ),
    }
    RECEIPT.write_bytes(json_bytes(receipt))
    return receipt


def check() -> dict[str, Any]:
    value = MEDIA.check()
    changed = scope(value)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(
        receipt["status"] == "passed-host-repack-hardware-not-run"
        and receipt["candidate"]["manifest"] == bind(MEDIA.MANIFEST)
        and receipt["candidate"]["runbook"] == bind(RUNBOOK)
        and receipt["candidate"]["product_d81"] == bind(MEDIA.PRODUCT_D81)
        and receipt["fix"]["scope"] == changed,
        "entry-bound repack receipt drift")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("capture-v8-pc", "build", "check"))
    args = parser.parse_args()
    configure()
    if args.action == "capture-v8-pc":
        value = capture_v8_pc()
    elif args.action == "build":
        value = build()
        check()
    else:
        value = check()
    print(
        "c2-lite-media-g5-entry-repack: PASS "
        f"action={args.action} status={value.get('status', 'captured')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
