#!/usr/bin/env python3
"""Capture the owner-authorized misspelled-require First Red raw-first."""

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

CONFIG = ROOT / "config/c2-v160-bound-origin-fragmentation-device-session.json"
ELF = ROOT / ("build/c2.3/v1.6-bound-origin-fragmentation-second-replacement-card/"
              "wplto/lisp65-c2-substitution-linked.prg.elf")
PRODUCT = ROOT / ("build/c2.3/v1.6-bound-origin-fragmentation-device-preparation/"
                  "shared-system/lisp65-product.d81")
LIBRARY = ROOT / ("build/c2.3/v1.6-bound-origin-fragmentation-device-preparation/"
                  "library/lisp65-library.d81")
CONTACT = ROOT / "build/c2.3/v1.6-bound-origin-fragmentation-device-contact"
PRODUCT_READBACK = CONTACT / "product-readback.d81"
LIBRARY_READBACK = CONTACT / "library-readback.d81"
OUT = CONTACT / "misspelled-require-first-red-stopped-state"
EXPECTED = {
    "engine": "da6e7ebf54fe782657a0b896fe1acc86d8eef658e2001db5fb502225732e5322",
    "config": "afc8b0f9da28991fd0826fea35651eee4caf2e344f425a153066918c7d9adda1",
    "candidate_ELF": "8bb00fd560ddfef9b4f1da5d6269e134de8dc6548a33e3659eb79fc580fecd45",
    "product": "1dfe154d49780831b92214c0740280e02adda915dddfbea375b59d329305cc84",
    "library": "f264756c89d737ea37e1c4072cf42c70238dfb69f0ef9768324c974758ddfbc3",
    "product_readback": "1dfe154d49780831b92214c0740280e02adda915dddfbea375b59d329305cc84",
    "library_readback": "f264756c89d737ea37e1c4072cf42c70238dfb69f0ef9768324c974758ddfbc3",
}
RANGES = (
    ("bank0-zp-stack", 0x00000000, 0x0200),
    ("input-ring-and-counters", 0x0000BC90, 0x0070),
    ("toplevel-jmpbuf", 0x0000BD47, 0x0020),
    ("error-and-overlay-status", 0x0000BFEF, 0x0010),
    ("heap-status", 0x0000C25D, 0x0100),
    ("workbench-overlay-window", 0x0000C354, 0x0740),
    ("c2-fixed-state", 0x0000FF80, 0x0080),
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
        "engine": bind(ENGINE_PATH), "config": bind(CONFIG),
        "candidate_ELF": bind(ELF), "product": bind(PRODUCT),
        "library": bind(LIBRARY), "product_readback": bind(PRODUCT_READBACK),
        "library_readback": bind(LIBRARY_READBACK),
    }
    ENGINE.require({name: row["sha256"] for name, row in bindings.items()} == EXPECTED,
                   "misspelled-require stopped-state identity drift")
    ENGINE.require(PRODUCT.read_bytes() == PRODUCT_READBACK.read_bytes()
                   and LIBRARY.read_bytes() == LIBRARY_READBACK.read_bytes(),
                   "device readback/source mismatch")
    ENGINE.require(not ENGINE.CAPTURE.exists() and not ENGINE.PARTIAL.exists(),
                   "misspelled-require capture is one-shot")
    return {
        "authorization": {"authority": "owner-live-authorization",
            "date": "2026-08-21", "trigger": "owner answered ja",
            "scope": "one raw-first stopped-state read; no resume, reset, run or input"},
        **bindings,
        "trigger_form": "(requre 'v16core)",
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
                   "usage: c2_v160_bound_origin_typo_first_red_capture.py preflight|capture")
    if sys.argv[1] == "preflight":
        print(json.dumps({"status": "PREFLIGHT PASS", "authority": preflight()},
                         indent=2, sort_keys=True))
        return 0
    value = ENGINE.capture()
    value["format"] = "lisp65-c2.3-v1.6-bound-origin-typo-first-red-raw-v1"
    value["captured_on"] = "2026-08-21"
    value["claim_limit"] = (
        "Raw authorized row only. Attribution is separate; CPU remains stopped.")
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
        print(f"c2-v160-bound-origin-typo-first-red: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
