#!/usr/bin/env python3
"""Capture the owner-authorized P3/L3 input-fidelity First Red raw-first."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ENGINE_PATH = ROOT / "tools/host-lisp/c2_v21_phase1_rescue_capture.py"
SPEC = importlib.util.spec_from_file_location("c2_v21_phase1_rescue_capture", ENGINE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("raw-first stopped-state engine unavailable")
ENGINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE)

CONFIG = ROOT / "config/c2-v160-liveness-prompt-device-session.json"
ELF = ROOT / (
    "build/c2.3/v1.6-liveness-prompt-device-preparation-r1/"
    "canonical-product/final/lisp65-c2-substitution-linked.prg.elf")
PRODUCT = ROOT / (
    "build/c2.3/v1.6-liveness-prompt-device-preparation-r1/"
    "shared-system/lisp65-product.d81")
LIBRARY = ROOT / (
    "build/c2.3/v1.6-liveness-prompt-device-preparation-r1/"
    "library/lisp65-library.d81")
PRODUCT_READBACK = Path("/tmp/lisp65-v16p3-deploy-20260820-2/V16P3.D81")
LIBRARY_READBACK = Path("/tmp/lisp65-v16p3-deploy-20260820-2/V16L3.D81")
OUT = ROOT / "build/c2.3/v1.6-liveness-prompt-owner-contact/input-first-red-stopped-state"

EXPECTED = {
    "engine": "da6e7ebf54fe782657a0b896fe1acc86d8eef658e2001db5fb502225732e5322",
    "config": "c2fd3be305b3d33f5617cff23db4b742a008fb2761284d4145d260a0bddb07f8",
    "candidate_ELF": "102eac84ab25ec57b39990377d4808c3287746b94c65617cca3259fd43f73bcd",
    "product": "832fe006eaa2cc7094d067846c4cc84bfb48122f6b44826038d9a37e8e9c948a",
    "library": "899386137912b071bc8c3086cc811a5dc4a562301ad48104b9ea486d9b56201e",
    "product_readback": "832fe006eaa2cc7094d067846c4cc84bfb48122f6b44826038d9a37e8e9c948a",
    "library_readback": "899386137912b071bc8c3086cc811a5dc4a562301ad48104b9ea486d9b56201e",
}

RANGES = (
    ("bank0-zp-stack", 0x00000000, 0x0200),
    ("gc-runs", 0x0000B9EE, 0x0002),
    ("input-ring", 0x0000BC90, 0x0070),
    ("heap-head", 0x0000C25D, 0x00F0),
    ("c2-fixed-state", 0x0000FF80, 0x0010),
    ("physical-keyboard-io", 0x0FFD3600, 0x0020),
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    ENGINE.require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    raw = path.read_bytes()
    try:
        name = path.relative_to(ROOT).as_posix()
    except ValueError:
        name = str(path)
    return {"path": name, "bytes": len(raw), "sha256": sha(raw)}


def preflight() -> dict[str, Any]:
    bindings = {
        "engine": bind(ENGINE_PATH),
        "config": bind(CONFIG),
        "candidate_ELF": bind(ELF),
        "product": bind(PRODUCT),
        "library": bind(LIBRARY),
        "product_readback": bind(PRODUCT_READBACK),
        "library_readback": bind(LIBRARY_READBACK),
    }
    ENGINE.require(
        {name: row["sha256"] for name, row in bindings.items()} == EXPECTED,
        "P3/L3 stopped-state identity drift")
    ENGINE.require(PRODUCT.read_bytes() == PRODUCT_READBACK.read_bytes(),
                   "P3 device readback/source mismatch")
    ENGINE.require(LIBRARY.read_bytes() == LIBRARY_READBACK.read_bytes(),
                   "L3 device readback/source mismatch")
    ENGINE.require(not ENGINE.CAPTURE.exists() and not ENGINE.PARTIAL.exists(),
                   "P3/L3 input First-Red capture is one-shot")
    return {
        "authorization": {
            "authority": "owner-live-authorization",
            "date": "2026-08-20",
            "scope": "one raw-first stopped-state read; no resume, reset, run, or further input",
            "trigger": "Claude recommendation relayed and Codex given the word",
        },
        **bindings,
        "ranges": [
            {"name": name, "address": f"0x{address:08x}", "bytes": count}
            for name, address, count in RANGES
        ],
    }


ENGINE.OUT = OUT
ENGINE.CAPTURE = OUT / "capture.json"
ENGINE.PARTIAL = OUT / "capture.partial.json"
ENGINE.RANGES = RANGES
ENGINE.preflight = preflight


def main() -> int:
    ENGINE.require(len(sys.argv) == 2 and sys.argv[1] in {"preflight", "capture"},
                   "usage: c2_v160_liveness_prompt_input_first_red_capture.py preflight|capture")
    if sys.argv[1] == "preflight":
        print(json.dumps({"status": "PREFLIGHT PASS", "authority": preflight()},
                         indent=2, sort_keys=True))
        return 0
    value = ENGINE.capture()
    value["format"] = "lisp65-c2.3-v1.6-liveness-prompt-input-first-red-raw-v1"
    value["captured_on"] = "2026-08-20"
    value["claim_limit"] = (
        "Raw authorized row only. The physical I/O row is read-only; attribution "
        "belongs to a separate result binder. CPU remains stopped.")
    ENGINE.CAPTURE.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                              encoding="utf-8")
    print(json.dumps({
        "status": "CAPTURE PASS",
        "tuple": value["tuple"],
        "reads": [
            {"name": row["name"], "bytes": row["bytes"],
             "sha256": sha(bytes.fromhex(row["observed_hex"]))}
            for row in value["reads"]
        ],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ENGINE.CaptureError, OSError, ValueError, KeyError) as error:
        print(f"c2-v160-liveness-prompt-input-first-red: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
