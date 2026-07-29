#!/usr/bin/env python3
"""Hold Link 71 at the common append failure edge, before rollback."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link71_pre_transaction_end_hold as P  # noqa: E402


BASE = ROOT / "build/post-promotion/link71-defstruct-header-crc-domain"
BASE_DEPLOYMENT = BASE / "hardware-session/deployment.json"
BASE_PRODUCT = BASE / "final/lisp65-c2-substitution-linked.prg"
BASE_ELF = BASE / "final/lisp65-c2-substitution-linked.prg.elf"
BASE_WINDOW = BASE / "final/c2-product-kernal-window.bin"
OUT = BASE / "pre-rollback-hold-NONPROMOTABLE"
PATCH = OUT / "pre-rollback-hold.bin"
DEPLOYMENT = OUT / "deployment.json"
RECEIPT = (
    ROOT / "tests/fixtures/c2-migration-evidence"
    / "c2.2-link71-pre-rollback-hold-nonpromotable-receipt.json"
)
CAPTURE = OUT / "register-captures.json"

PATCH_ADDRESS = 0xE9BC
WINDOW_ADDRESS = 0xE000
BEFORE = bytes.fromhex("20 e3 e9")
AFTER = bytes.fromhex("78 80 fe")
HOLD_PC = 0xE9BD


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


def window_span() -> tuple[int, bytes]:
    window = data(BASE_WINDOW)
    require(len(window) == 8192, "Link-71 window size drift")
    offset = PATCH_ADDRESS - WINDOW_ADDRESS
    require(window[offset:offset + len(BEFORE)] == BEFORE,
            "common rollback call bytes drift")
    return offset, window


def prepare() -> dict[str, Any]:
    require(not RECEIPT.exists(), "pre-rollback receipt already exists")
    base = load(BASE_DEPLOYMENT)
    offset, _window = window_span()
    require(base["product"]["sha256"] == sha(BASE_PRODUCT),
            "Link-71 product authority drift")
    OUT.mkdir(parents=True, exist_ok=True)
    PATCH.write_bytes(AFTER)
    write_json(RECEIPT, {
        "format": "lisp65-c2.2-Link71-pre-rollback-hold-v1",
        "recorded_on": "2026-07-27",
        "status": "ready-authorized-nonpromotable-primary-failure-capture",
        "promotable": False,
        "authority": {
            "product": bind(BASE_PRODUCT, 0x2001),
            "ELF": bind(BASE_ELF),
            "window": bind(BASE_WINDOW, 0x087FE000),
            "source_deployment": bind(BASE_DEPLOYMENT),
            "driver": bind(Path(__file__).resolve()),
        },
        "patch": {
            "runtime_address": f"0x{PATCH_ADDRESS:04x}",
            "window_file_offset": offset,
            "before": BEFORE.hex(),
            "after": AFTER.hex(),
            "artifact": bind(PATCH, PATCH_ADDRESS),
            "product_file_bytes_delta": 0,
            "deployed_product_bytes_delta": 0,
            "late_RAM_bytes_changed": 3,
            "semantics": (
                "SEI once, then BRA to itself at c2_append_begin's common "
                "failure edge, before c2_append_run_rollback_plan mutates "
                "the append context or installer provenance."
            ),
        },
        "ELF_truth": {
            "failure_edge": (
                "0xe9bc JSR 0xe9e3 c2_append_run_rollback_plan"
            ),
            "success_edge": (
                "0xe9b6 loads c2_phase_owner and bypasses 0xe9bc"
            ),
        },
        "capture_contract": {
            "phase_scratch": (
                "complete 304-byte c2_append_state plus permanent trace"
            ),
            "zero_page": "vm_status, transaction state, owner, READY",
            "C2J": "64-byte Bank-5 journal before cleanup",
            "stability": "three byte-identical captures",
        },
        "claim_limit": (
            "One nonpromotable Link-71 primary append-failure attribution."
        ),
    })
    write_json(DEPLOYMENT, {
        "format": "lisp65-c2.2-Link71-pre-rollback-deployment-v1",
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
    }


def verify() -> dict[str, Any]:
    offset, window = window_span()
    receipt, deployment = load(RECEIPT), load(DEPLOYMENT)
    require(data(PATCH) == AFTER, "pre-rollback patch drift")
    require(receipt["patch"]["window_file_offset"] == offset,
            "receipt window offset drift")
    require(
        deployment["authority"]["receipt"]["sha256"] == sha(RECEIPT)
        and deployment["late_patch"]["sha256"] == sha(PATCH)
        and deployment["product"]["sha256"] == sha(BASE_PRODUCT),
        "deployment binding drift",
    )
    require(window[offset:offset + len(BEFORE)] == BEFORE,
            "source window was modified")
    return {
        "status": "verified",
        "patch_address": f"0x{PATCH_ADDRESS:04x}",
        "source_bytes": BEFORE.hex(),
        "hold_bytes": AFTER.hex(),
    }


def capture() -> dict[str, Any]:
    verify()
    require(not CAPTURE.exists(), "pre-rollback capture is one-shot")
    P.HOLD_PC = HOLD_PC
    fd = os.open(P.H.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        P.H.configure_serial(fd)
        rows = []
        for index, delay in enumerate((0, 1, 4), 1):
            if delay:
                time.sleep(delay)
            rows.append(P.capture_one(fd, index))
    finally:
        os.close(fd)
    require(len({(r["PC"], r["A"], r["X"]) for r in rows}) == 1,
            "pre-rollback registers moved between captures")
    value = {
        "format": "lisp65-Link71-pre-rollback-register-captures-v1",
        "capture_intervals_seconds": [0, 1, 5],
        "device": P.H.DEVICE,
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
    except (HoldError, P.HoldError, P.H.HoldError, OSError, ValueError,
            KeyError, json.JSONDecodeError) as error:
        print("c2-defstruct-Link71-pre-rollback-hold: FIRST RED: " + str(error))
        raise SystemExit(2)
