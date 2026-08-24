#!/usr/bin/env python3
"""Capture the authorized execution-boundary seam First Red, raw first."""

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

SESSION = ROOT / "config/c2-v160-execution-boundary-seam-session.json"
ELF = ROOT / (
    "build/c2.3/v1.6-execution-boundary-backstop-uint8-irq-return-"
    "replacement-card/wplto/lisp65-c2-substitution-linked.prg.elf")
PRODUCT = ROOT / (
    "build/c2.3/v1.6-execution-boundary-media/shared-system/"
    "lisp65-product.d81")
LIBRARY = ROOT / (
    "build/c2.3/v1.6-execution-boundary-media/library/lisp65-library.d81")
PRODUCT_READBACK = Path(
    "/tmp/lisp65-v16bstp-deploy-20260823/V16BSTP.readback.D81")
LIBRARY_READBACK = Path(
    "/tmp/lisp65-v16bstp-deploy-20260823/V16BSTL.readback.D81")
OUT = ROOT / "build/c2.3/v1.6-execution-boundary-first-red"

EXPECTED = {
    "engine": "da6e7ebf54fe782657a0b896fe1acc86d8eef658e2001db5fb502225732e5322",
    "session": "e1ba3c7ef033ec9882946c49b7f31554f54b65e3098bd6e6d3377aacf0565d56",
    "candidate_ELF": "c8b74690e682370f14c68bc837cd9642b702df024e71c82753b0b21d678fd10d",
    "product": "f6c6b1afc36fd5007022a66da640aa139c46eb78fe0d2e244274b26ff3cb76b7",
    "library": "f005f654ec3d6ac424f09cfe1cf6ae0f19a8a5b7ceb1f559960e97e4acab61a6",
    "product_readback": "f6c6b1afc36fd5007022a66da640aa139c46eb78fe0d2e244274b26ff3cb76b7",
    "library_readback": "f005f654ec3d6ac424f09cfe1cf6ae0f19a8a5b7ceb1f559960e97e4acab61a6",
}

RANGES = (
    ("bank0-zp-stack", 0x00000000, 0x0200),
    ("vm-and-boot-status", 0x0000BFE0, 0x0020),
    ("c2-boot-runtime", 0x0000C080, 0x0032),
    ("refill-trace-origin", 0x0000BC87, 0x0005),
    ("refill-trace-slots", 0x0000BD00, 0x0044),
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path, name: str) -> dict[str, Any]:
    ENGINE.require(path.is_file() and not path.is_symlink(),
                   f"file absent: {path}")
    raw = path.read_bytes()
    try:
        display = path.relative_to(ROOT).as_posix()
    except ValueError:
        display = str(path)
    return {"name": name, "path": display, "bytes": len(raw),
            "sha256": sha(raw)}


def preflight() -> dict[str, Any]:
    paths = {
        "engine": ENGINE_PATH, "session": SESSION, "candidate_ELF": ELF,
        "product": PRODUCT, "library": LIBRARY,
        "product_readback": PRODUCT_READBACK,
        "library_readback": LIBRARY_READBACK,
    }
    bindings = {name: bind(path, name) for name, path in paths.items()}
    ENGINE.require({name: row["sha256"] for name, row in bindings.items()}
                   == EXPECTED, "execution-boundary First-Red identity drift")
    ENGINE.require(PRODUCT.read_bytes() == PRODUCT_READBACK.read_bytes()
                   and LIBRARY.read_bytes() == LIBRARY_READBACK.read_bytes(),
                   "deployed media readbacks differ from bound sources")
    ENGINE.require(not ENGINE.CAPTURE.exists() and not ENGINE.PARTIAL.exists(),
                   "execution-boundary First-Red capture is one-shot")
    return {
        "authorization": {"authority": "owner-live-authorization",
            "date": "2026-08-23",
            "scope": ("one raw-first stopped-state read: registers/stack, "
                "VM/boot status and refill origin/two slots; no resume or "
                "input; CPU remains stopped")},
        **bindings,
        "ranges": [{"name": name, "address": f"0x{address:08x}",
                    "bytes": count} for name, address, count in RANGES],
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
    value["format"] = "lisp65-c2-v160-execution-boundary-first-red-raw-v1"
    value["captured_on"] = "2026-08-23"
    value["claim_limit"] = (
        "Raw authorized stopped-state row only; attribution is separate. "
        "CPU remains stopped.")
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
        print(f"execution-boundary-first-red: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
