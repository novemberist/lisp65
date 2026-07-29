#!/usr/bin/env python3
"""Bind and capture a zero-growth Link-71 hold after disk-library append.

The three-byte JMP immediately following the sole
``c2_product_append_staged`` call is replaced late, after a pristine boot,
with ``SEI; BRA $-2``.  The loop therefore preserves the append return value
in A and stops before vm_callprim converts it to T/NIL or returns to the VM.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link71_slot39_failure_hold as H  # noqa: E402


BASE = ROOT / "build/post-promotion/link71-defstruct-header-crc-domain"
BASE_DEPLOYMENT = BASE / "hardware-session/deployment.json"
BASE_PRODUCT = BASE / "final/lisp65-c2-substitution-linked.prg"
BASE_ELF = BASE / "final/lisp65-c2-substitution-linked.prg.elf"
OUT = BASE / "post-append-return-hold-NONPROMOTABLE"
PATCH = OUT / "post-append-return-hold.bin"
DEPLOYMENT = OUT / "deployment.json"
RECEIPT = (
    ROOT / "tests/fixtures/c2-migration-evidence"
    / "c2.2-link71-post-append-return-hold-nonpromotable-receipt.json"
)
CAPTURE = OUT / "register-captures.json"

LOAD_ADDRESS = 0x2001
PATCH_ADDRESS = 0x7908
BEFORE = bytes.fromhex("4c 9f 74")
AFTER = bytes.fromhex("78 80 fe")
HOLD_PC = 0x7909


class HoldError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HoldError(message)


def data(path: Path) -> bytes:
    return path.read_bytes()


def sha(path: Path) -> str:
    return hashlib.sha256(data(path)).hexdigest()


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    require(isinstance(value, dict), f"object expected: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def product_span() -> tuple[int, bytes]:
    product = data(BASE_PRODUCT)
    require(int.from_bytes(product[:2], "little") == LOAD_ADDRESS,
            "Link-71 PRG load address drift")
    offset = 2 + PATCH_ADDRESS - LOAD_ADDRESS
    require(product[offset:offset + len(BEFORE)] == BEFORE,
            "post-append JMP bytes drift")
    return offset, product


def prepare() -> dict[str, Any]:
    require(not RECEIPT.exists(), "post-append receipt already exists")
    base = load(BASE_DEPLOYMENT)
    offset, product = product_span()
    require(base["product"]["sha256"] == sha(BASE_PRODUCT),
            "Link-71 product authority drift")
    OUT.mkdir(parents=True, exist_ok=True)
    PATCH.write_bytes(AFTER)
    write_json(RECEIPT, {
        "format": "lisp65-c2.2-Link71-post-append-return-hold-v1",
        "recorded_on": "2026-07-27",
        "status": "ready-authorized-nonpromotable-post-append-discriminator",
        "promotable": False,
        "authority": {
            "product": bind(BASE_PRODUCT, LOAD_ADDRESS),
            "ELF": bind(BASE_ELF),
            "source_deployment": bind(BASE_DEPLOYMENT),
            "driver": bind(Path(__file__).resolve()),
        },
        "patch": {
            "runtime_address": f"0x{PATCH_ADDRESS:04x}",
            "PRG_file_offset": offset,
            "before": BEFORE.hex(),
            "after": AFTER.hex(),
            "artifact": bind(PATCH, PATCH_ADDRESS),
            "product_file_bytes_delta": 0,
            "deployed_product_bytes_delta": 0,
            "late_RAM_bytes_changed": len(AFTER),
            "semantics": (
                "SEI once, then BRA to itself immediately after "
                "c2_product_append_staged returns; A/X/status and the "
                "vm_callprim/outer-VM software frames remain live."
            ),
        },
        "ELF_truth": {
            "call": "0x7905 JSR 0x24cb c2_product_append_staged",
            "patched_successor": "0x7908 JMP 0x749f",
            "normal_successor_semantics": (
                "convert uint8 append result to canonical T/NIL before "
                "returning from vm_callprim"
            ),
        },
        "outcomes": {
            "A_nonzero_status_OK": (
                "append and vm_callprim primitive body pass; failure is in "
                "the outer VM continuation after CALLPRIM"
            ),
            "A_zero_status_OK": (
                "append returned false without setting VM status despite "
                "all Slot-39/40 error exits being excluded"
            ),
            "status_nonzero": (
                "append path set a VM error outside the instrumented "
                "Slot-39/40 phase exits"
            ),
        },
        "claim_limit": (
            "One nonpromotable Link-71 return-edge attribution.  Product, "
            "require, and defstruct remain unqualified."
        ),
    })
    write_json(DEPLOYMENT, {
        "format": "lisp65-c2.2-Link71-post-append-return-hold-deployment-v1",
        "recorded_on": "2026-07-27",
        "status": "ready-authorized-nonpromotable-hardware",
        "promotable": False,
        "authority": {
            "receipt": bind(RECEIPT),
            "source_deployment": bind(BASE_DEPLOYMENT),
        },
        "product": base["product"],
        "media": base["media"],
        "remote_media": base["remote_media"],
        "preloads": base["preloads"],
        "late_patch": bind(PATCH, PATCH_ADDRESS),
        "test": {"form": "(%disk-load-lib 39 1)"},
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 0,
        },
    })
    return {
        "status": "ready",
        "patch_address": f"0x{PATCH_ADDRESS:04x}",
        "patch_sha256": sha(PATCH),
        "product_sha256": sha(BASE_PRODUCT),
    }


def verify() -> dict[str, Any]:
    offset, product = product_span()
    receipt = load(RECEIPT)
    deployment = load(DEPLOYMENT)
    require(data(PATCH) == AFTER, "late post-append patch drift")
    require(receipt["patch"]["PRG_file_offset"] == offset,
            "receipt PRG offset drift")
    require(
        deployment["authority"]["receipt"]["sha256"] == sha(RECEIPT),
        "deployment/receipt binding drift",
    )
    require(
        deployment["late_patch"]["sha256"] == sha(PATCH)
        and deployment["product"]["sha256"] == sha(BASE_PRODUCT),
        "deployment artifact binding drift",
    )
    require(product[offset:offset + 3] == BEFORE,
            "source product was modified")
    return {
        "status": "verified",
        "patch_address": f"0x{PATCH_ADDRESS:04x}",
        "source_bytes": BEFORE.hex(),
        "hold_bytes": AFTER.hex(),
    }


def capture_one(fd: int, index: int) -> dict[str, Any]:
    token = f"#c271pa{index:02x}\r".encode()
    H.monitor_sync(fd, token)
    H.slow_write(fd, b"t1\r")
    time.sleep(0.02)
    H.slow_write(fd, b"r\r")
    raw = H.serial_read(fd, 0.5)
    H.slow_write(fd, b"t0\r")
    H.serial_read(fd, 0.1)
    match = re.search(
        rb"(?:^|\n)([0-9A-Fa-f]{4})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+[0-9A-Fa-f]{4}\s",
        raw,
    )
    require(match is not None, f"register row absent in capture {index}")
    pc = int(match.group(1), 16)
    require(pc == HOLD_PC, f"unexpected PC 0x{pc:04x}")
    return {
        "index": index,
        "captured_at_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "PC": f"0x{pc:04x}",
        "A": f"0x{int(match.group(2), 16):02x}",
        "X": f"0x{int(match.group(3), 16):02x}",
        "Y": f"0x{int(match.group(4), 16):02x}",
        "Z": f"0x{int(match.group(5), 16):02x}",
        "B": f"0x{int(match.group(6), 16):02x}",
        "raw_hex": raw.hex(),
    }


def capture() -> dict[str, Any]:
    verify()
    require(not CAPTURE.exists(), "post-append capture is one-shot")
    fd = os.open(H.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        H.configure_serial(fd)
        rows = []
        for index, delay in enumerate((0, 1, 4), 1):
            if delay:
                time.sleep(delay)
            rows.append(capture_one(fd, index))
    finally:
        os.close(fd)
    require(len({(r["PC"], r["A"], r["X"]) for r in rows}) == 1,
            "post-append CPU result moved between captures")
    value = {
        "format": "lisp65-Link71-post-append-return-register-captures-v1",
        "capture_intervals_seconds": [0, 1, 5],
        "device": H.DEVICE,
        "driver": bind(Path(__file__).resolve()),
        "rows": rows,
    }
    write_json(CAPTURE, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "verify", "capture"))
    action = parser.parse_args().action
    value = (
        prepare() if action == "prepare"
        else verify() if action == "verify"
        else capture()
    )
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HoldError, H.HoldError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-defstruct-Link71-post-append-hold: FIRST RED: " + str(error))
        raise SystemExit(2)
