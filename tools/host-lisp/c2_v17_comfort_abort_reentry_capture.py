#!/usr/bin/env python3
"""Capture the owner-authorized v1.7 Comfort abort-to-reentry First Red."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ENGINE_PATH = ROOT / "tools/host-lisp/c2_v21_phase1_rescue_capture.py"
SPEC = importlib.util.spec_from_file_location(
    "c2_v21_phase1_rescue_capture", ENGINE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("raw-first stopped-state engine unavailable")
ENGINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE)

HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))
from elf_truth import ElfTruth  # noqa: E402


SESSION = ROOT / "config/c2-v17-comfort-phase1b-device-session.json"
ELF = ROOT / (
    "build/c2.3/v1.7-comfort-phase1b-acceptance-media-r1/"
    "canonical-product/final/lisp65-c2-substitution-linked.prg.elf")
MEDIA = ROOT / "build/c2.3/v1.7-comfort-phase1b-acceptance-media-r1"
PRODUCT = MEDIA / "shared-system/lisp65-product.d81"
LIBRARY = MEDIA / "library/lisp65-library.d81"
DEVICE = MEDIA / "device-session"
PRODUCT_READBACK = DEVICE / "product-readback.d81"
LIBRARY_READBACK = DEVICE / "library-readback.d81"
OUT = DEVICE / "abort-reentry-first-red-20260825"

EXPECTED = {
    "engine": "da6e7ebf54fe782657a0b896fe1acc86d8eef658e2001db5fb502225732e5322",
    "session": "eaa181b684de13e312f54723ad4ce04fe933161f843afab2e13712a51166fa05",
    "candidate_ELF": "79158c0e0b0034d6843b90b4acae32ed6363cc4c835e1a68f4a37317bf00aa3e",
    "product": "fba8843fccd7ab5f33dfc7973a7398f4a0f7864e78f161ac3436ab759585c9ae",
    "library": "6ad3ec8edbeba5f5688e9660535fdf5fd9d3e0ddf93668129809f9aade5949f3",
    "product_readback": "fba8843fccd7ab5f33dfc7973a7398f4a0f7864e78f161ac3436ab759585c9ae",
    "library_readback": "6ad3ec8edbeba5f5688e9660535fdf5fd9d3e0ddf93668129809f9aade5949f3",
}

# The fixed ranges are derived from the accepted final ELF and the C2D-v6
# schema.  They distinguish READY loss, overlay-cleanup failure, abort phase,
# and live-directory damage without a second target observation.
RANGES = (
    ("bank0-runtime-status", 0x00000020, 0x0070),
    ("pending-error-detail", 0x0000B9E8, 0x0004),
    ("runtime-overlay-lifecycle", 0x0000BFF0, 0x0010),
    ("c2-runtime", 0x0000C084, 0x002E),
    ("abort-record-and-meta", 0x0000C17C, 0x0024),
    ("c2d-header", 0x00050000, 0x0030),
    ("c2d-high-row63", 0x00050810, 0x0020),
    ("c2d-comfort-rows353-356", 0x000515FA, 0x0028),
    ("c2j", 0x0005C640, 0x0040),
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path, name: str) -> dict[str, Any]:
    ENGINE.require(path.is_file() and not path.is_symlink(),
                   f"file absent: {path}")
    raw = path.read_bytes()
    return {"name": name, "path": path.relative_to(ROOT).as_posix(),
            "bytes": len(raw), "sha256": sha(raw)}


def preflight() -> dict[str, Any]:
    paths = {
        "engine": ENGINE_PATH, "session": SESSION, "candidate_ELF": ELF,
        "product": PRODUCT, "library": LIBRARY,
        "product_readback": PRODUCT_READBACK,
        "library_readback": LIBRARY_READBACK,
    }
    bindings = {name: bind(path, name) for name, path in paths.items()}
    ENGINE.require({name: row["sha256"] for name, row in bindings.items()}
                   == EXPECTED, "Comfort abort-reentry identity drift")
    ENGINE.require(PRODUCT.read_bytes() == PRODUCT_READBACK.read_bytes()
                   and LIBRARY.read_bytes() == LIBRARY_READBACK.read_bytes(),
                   "deployed media readbacks differ from bound sources")
    truth = ElfTruth.read(
        ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    symbols = {name: (truth.symbol(name).value, truth.symbol(name).bytes)
               for name in (
                   "pending_code", "pending_symbol", "vm_status",
                   "rtov_busy", "rtov_loaded_len", "c2_phase_owner",
                   "c2_ready", "rtov_fault", "rtov_family",
                   "rtov_family_generation", "c2_runtime",
                   "lisp65_c2_phase_scratch")}
    ENGINE.require(symbols == {
        "pending_code": (0x0036, 1), "pending_symbol": (0xB9E9, 2),
        "vm_status": (0x005D, 1), "rtov_busy": (0x0078, 1),
        "rtov_loaded_len": (0x0079, 2), "c2_phase_owner": (0x0089, 1),
        "c2_ready": (0x008C, 1), "rtov_fault": (0xBFF7, 1),
        "rtov_family": (0xBFF8, 1),
        "rtov_family_generation": (0xBFF9, 2),
        "c2_runtime": (0xC084, 46),
        "lisp65_c2_phase_scratch": (0xC0C6, 304),
    }, "Comfort abort-reentry read geometry drift")
    ENGINE.require(not ENGINE.CAPTURE.exists() and not ENGINE.PARTIAL.exists(),
                   "Comfort abort-reentry capture is one-shot")
    return {
        "authorization": {
            "authority": "owner-live-authorization",
            "date": "2026-08-25",
            "scope": ("one raw-first read after second (repl) returned E29; "
                      "one CPU stop, no resume/reset/input; CPU remains stopped"),
        },
        **bindings,
        "ranges": [{"name": name, "address": f"0x{address:08x}",
                    "bytes": count} for name, address, count in RANGES],
        "derived_symbols": {
            name: {"address": f"0x{value:04x}", "bytes": size}
            for name, (value, size) in symbols.items()},
    }


ENGINE.OUT = OUT
ENGINE.CAPTURE = OUT / "capture.json"
ENGINE.PARTIAL = OUT / "capture.partial.json"
ENGINE.RANGES = RANGES
ENGINE.preflight = preflight


def main() -> int:
    ENGINE.require(len(sys.argv) == 2 and sys.argv[1] in {"preflight", "capture"},
                   "usage: preflight|capture")
    if sys.argv[1] == "preflight":
        print(json.dumps({"status": "PREFLIGHT PASS", "authority": preflight()},
                         indent=2, sort_keys=True))
        return 0
    value = ENGINE.capture()
    value["format"] = "lisp65-c2-v17-comfort-abort-reentry-raw-v1"
    value["captured_on"] = "2026-08-25"
    value["claim_limit"] = (
        "Raw owner-authorized post-E29 state only; attribution is separate. "
        "CPU remains stopped.")
    ENGINE.CAPTURE.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "CAPTURE PASS", "tuple": value["tuple"],
        "reads": [{"name": row["name"], "bytes": row["bytes"],
                   "sha256": sha(bytes.fromhex(row["observed_hex"]))}
                  for row in value["reads"]]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ENGINE.CaptureError, OSError, ValueError, KeyError) as error:
        print(f"v1.7-comfort-abort-reentry-capture: FAIL: {error}",
              file=sys.stderr)
        raise SystemExit(1)
