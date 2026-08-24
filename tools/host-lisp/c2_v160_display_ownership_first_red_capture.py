#!/usr/bin/env python3
"""Capture the authorized v1.6 display-entry First Red, raw-first."""

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

PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-display-ownership-device-preparation-receipt.json")
ELF = ROOT / (
    "build/c2.3/v1.6-display-ownership-device-preparation/canonical-product/"
    "final/lisp65-c2-substitution-linked.prg.elf")
PRODUCT = ROOT / (
    "build/c2.3/v1.6-display-ownership-device-preparation/shared-system/"
    "lisp65-product.d81")
LIBRARY = ROOT / (
    "build/c2.3/v1.6-display-ownership-device-preparation/library/"
    "lisp65-library.d81")
CONTACT = ROOT / "build/c2.3/v1.6-display-ownership-device-contact"
PRODUCT_READBACK = CONTACT / "readback/V16D6.D81"
LIBRARY_READBACK = CONTACT / "readback/V16L6.D81"
OUT = CONTACT / "display-entry-first-red-stopped-state"

# The first three rows bind CPU/VM status.  Bank 4 is the complete live EXT
# heap carrier for installed code-object headers; the Bank-5 suffix is the
# complete name/value/name-offset/function-cell publication layout derived
# from SYMPOOL_EXT_OFF=0xc680, NAMEPOOL=10208 and MAX_SYM=752.
RANGES = (
    ("bank0-zp-stack", 0x00000000, 0x0200),
    ("vm-error-status", 0x0000BFE0, 0x0020),
    ("hot-heap-state", 0x0000C25D, 0x00F7),
    ("bank4-installed-object-headers", 0x00040000, 0x6C00),
    ("bank5-symbol-publication", 0x0005C680, 0x3980),
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    ENGINE.require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def preflight() -> dict[str, Any]:
    bindings = {
        "engine": bind(ENGINE_PATH), "preparation": bind(PREPARATION),
        "candidate_ELF": bind(ELF), "product": bind(PRODUCT),
        "library": bind(LIBRARY), "product_readback": bind(PRODUCT_READBACK),
        "library_readback": bind(LIBRARY_READBACK),
    }
    receipt = json.loads(PREPARATION.read_text(encoding="utf-8"))
    ENGINE.require(
        receipt["status"] == "PASS: V1.6 DISPLAY OWNERSHIP SIXTH CONTACT READY"
        and receipt["media"]["product"]["sha256"] == bindings["product"]["sha256"]
        and receipt["media"]["library"]["sha256"] == bindings["library"]["sha256"],
        "display preparation identity drift")
    ENGINE.require(PRODUCT.read_bytes() == PRODUCT_READBACK.read_bytes()
                   and LIBRARY.read_bytes() == LIBRARY_READBACK.read_bytes(),
                   "mounted-media readback/source mismatch")
    ENGINE.require(not ENGINE.CAPTURE.exists() and not ENGINE.PARTIAL.exists(),
                   "display-entry First-Red capture is one-shot")
    return {
        "authorization": {
            "authority": "owner-live-authorization",
            "date": "2026-08-22",
            "scope": (
                "one read-only stopped-state row: registers, stack, VM status, "
                "installed descriptors, symbol cells and code-object headers; "
                "no resume, reset or input; CPU remains stopped"),
        },
        **bindings,
        "ranges": [{"name": name, "address": f"0x{address:08x}", "bytes": count}
                   for name, address, count in RANGES],
    }


ENGINE.OUT = OUT
ENGINE.CAPTURE = OUT / "capture.json"
ENGINE.PARTIAL = OUT / "capture.partial.json"
ENGINE.RANGES = RANGES
ENGINE.preflight = preflight


def main() -> int:
    ENGINE.require(len(sys.argv) == 2 and sys.argv[1] in {"preflight", "capture"},
                   "usage: c2_v160_display_ownership_first_red_capture.py preflight|capture")
    if sys.argv[1] == "preflight":
        print(json.dumps({"status": "PREFLIGHT PASS", "authority": preflight()},
                         indent=2, sort_keys=True))
        return 0
    value = ENGINE.capture()
    value["format"] = "lisp65-c2.3-v1.6-display-entry-first-red-raw-v1"
    value["captured_on"] = "2026-08-22"
    value["claim_limit"] = (
        "Raw authorized stopped-state row only; loader/helper attribution is "
        "separate. CPU remains stopped.")
    ENGINE.CAPTURE.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                              encoding="utf-8")
    print(json.dumps({"status": "CAPTURE PASS", "tuple": value["tuple"],
        "reads": [{"name": row["name"], "bytes": row["bytes"],
                   "sha256": sha(bytes.fromhex(row["observed_hex"]))}
                  for row in value["reads"]]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ENGINE.CaptureError, OSError, ValueError, KeyError) as error:
        print(f"c2-v160-display-entry-first-red: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
