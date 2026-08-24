#!/usr/bin/env python3
"""Capture the authorized boot-refill DMA seam First Red, raw-first."""

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

SESSION = ROOT / "config/c2-v160-boot-refill-dma-session.json"
ELF = ROOT / (
    "build/c2.3/v1.6-boot-refill-generator-template-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
PRODUCT = ROOT / (
    "build/c2.3/v1.6-boot-refill-dma-media/shared-system/lisp65-product.d81")
LIBRARY = ROOT / (
    "build/c2.3/v1.6-boot-refill-dma-media/library/lisp65-library.d81")
DEPLOY = ROOT / "build/c2.3/v1.6-boot-refill-dma-media/device-deploy-20260823"
PRODUCT_READBACK = DEPLOY / "V16DMA.readback.D81"
LIBRARY_READBACK = DEPLOY / "V16DML.readback.D81"
TRACE = ROOT / "build/c2.3/v1.6-boot-refill-dma-media/device-trace-20260823"
OUT = ROOT / "build/c2.3/v1.6-boot-refill-dma-media/device-first-red-20260823"

EXPECTED = {
    "engine": "da6e7ebf54fe782657a0b896fe1acc86d8eef658e2001db5fb502225732e5322",
    "session": "f49e6df7bc7454c574585736118cd5022895c9b6d71dd0261eeddf449482f0b2",
    "candidate_ELF": "02209a9ddda93b49bc3025f6b0caa9b2d88cb96b2504167b3ccc98d6f9ffba99",
    "product": "3c8901f6abf96451597fb7bf827fea9aba39eae8b3d88aadc3273583064f9606",
    "library": "f005f654ec3d6ac424f09cfe1cf6ae0f19a8a5b7ceb1f559960e97e4acab61a6",
    "product_readback": "3c8901f6abf96451597fb7bf827fea9aba39eae8b3d88aadc3273583064f9606",
    "library_readback": "f005f654ec3d6ac424f09cfe1cf6ae0f19a8a5b7ceb1f559960e97e4acab61a6",
}

CLASSIFICATION = {
    "class": "historical-one-shot-device-capture-producer",
    "build_reachable": False,
    "live_product_gate": False,
    "retention_reason": (
        "tracked citation target for the SHA-bound 2026-08-23 boot-refill "
        "First-Red capture; its inputs are historical and it is never an "
        "acceptance or media authority"),
}

RANGES = (
    ("bank0-zp-stack", 0x00000000, 0x0200),
    ("vm-and-boot-status", 0x0000BFE0, 0x0020),
    ("c2-boot-runtime", 0x0000C080, 0x0032),
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
        "engine": bind(ENGINE_PATH), "session": bind(SESSION),
        "candidate_ELF": bind(ELF), "product": bind(PRODUCT),
        "library": bind(LIBRARY), "product_readback": bind(PRODUCT_READBACK),
        "library_readback": bind(LIBRARY_READBACK),
        "trace_origin": bind(TRACE / "trace-origin.bin"),
        "trace_slot0": bind(TRACE / "trace-slot0.bin"),
        "trace_slot1": bind(TRACE / "trace-slot1.bin"),
    }
    ENGINE.require(
        {name: row["sha256"] for name, row in bindings.items()
         if name in EXPECTED} == EXPECTED,
        "boot-refill First-Red identity drift")
    ENGINE.require(PRODUCT.read_bytes() == PRODUCT_READBACK.read_bytes()
                   and LIBRARY.read_bytes() == LIBRARY_READBACK.read_bytes(),
                   "mounted media differ from the bound sources")
    ENGINE.require(all((TRACE / name).read_bytes() == bytes(size) for name, size in (
        ("trace-origin.bin", 5), ("trace-slot0.bin", 34),
        ("trace-slot1.bin", 34))), "pre-boot-refill zero witness drift")
    ENGINE.require(not ENGINE.CAPTURE.exists() and not ENGINE.PARTIAL.exists(),
                   "boot-refill First-Red capture is one-shot")
    return {
        "authorization": {
            "authority": "owner-live-authorization",
            "date": "2026-08-23",
            "scope": (
                "one raw-first stopped-state row: register/MAP tuple, hardware "
                "stack and VM/boot status; no resume or input; CPU remains stopped"),
        },
        "tool_classification": CLASSIFICATION,
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
                   "usage: c2_v160_boot_refill_dma_first_red_capture.py preflight|capture")
    if sys.argv[1] == "preflight":
        print(json.dumps({"status": "PREFLIGHT PASS", "authority": preflight()},
                         indent=2, sort_keys=True))
        return 0
    value = ENGINE.capture()
    value["format"] = "lisp65-c2.3-v1.6-boot-refill-dma-first-red-raw-v1"
    value["captured_on"] = "2026-08-23"
    value["claim_limit"] = (
        "Raw authorized stopped-state row only; mechanism attribution is separate. "
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
        print(f"c2-v160-boot-refill-dma-first-red: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
