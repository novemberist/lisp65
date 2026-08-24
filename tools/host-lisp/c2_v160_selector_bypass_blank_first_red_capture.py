#!/usr/bin/env python3
"""Capture the authorized selector-bypass blank-screen First Red, raw first."""

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


SESSION = ROOT / "config/c2-v160-boot-refill-selector-bypass-domain-session.json"
ELF = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-domain-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
PRODUCT = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-domain-media/"
    "shared-system/lisp65-product.d81")
LIBRARY = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-domain-media/"
    "library/lisp65-library.d81")
READBACK = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-domain-media/"
    "deploy-readback")
PRODUCT_READBACK = READBACK / "V16SEL3.D81"
LIBRARY_READBACK = READBACK / "V16SL3.D81"
TRACE_SOURCE = ROOT / "src/optional/c2_refill_boundary_witness.s"
OUT = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-domain-media/"
    "device-blank-first-red-20260824")

EXPECTED = {
    "engine": "da6e7ebf54fe782657a0b896fe1acc86d8eef658e2001db5fb502225732e5322",
    "session": "224c12c0aeeac39b0ef52b938925db95aef7100ce1be4f03c4a6eff2e8ecdd71",
    "candidate_ELF": "bbb1547779ea2c9366fa5a29633aa07061a3607fa753043071df1780cc5ea3e4",
    "product": "9f388a5e67fdb3441e69bece41a74330e1d011be84bc66b31f4657d5ec239af6",
    "library": "f005f654ec3d6ac424f09cfe1cf6ae0f19a8a5b7ceb1f559960e97e4acab61a6",
    "product_readback": "9f388a5e67fdb3441e69bece41a74330e1d011be84bc66b31f4657d5ec239af6",
    "library_readback": "f005f654ec3d6ac424f09cfe1cf6ae0f19a8a5b7ceb1f559960e97e4acab61a6",
}

RANGES = (
    ("bank0-zp-stack", 0x00000000, 0x0200),
    ("vm-and-overlay-status", 0x0000BFE0, 0x0020),
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
                   == EXPECTED, "selector-bypass blank-screen identity drift")
    ENGINE.require(PRODUCT.read_bytes() == PRODUCT_READBACK.read_bytes()
                   and LIBRARY.read_bytes() == LIBRARY_READBACK.read_bytes(),
                   "deployed media readbacks differ from bound sources")
    session = json.loads(SESSION.read_text(encoding="utf-8"))
    ENGINE.require(session["media"]["product"]["remote_name"] == "V16SEL3.D81"
                   and session["media"]["library"]["remote_name"] == "V16SL3.D81"
                   and session["status"] == "ready-owner-contact",
                   "selector-bypass session identity/status drift")
    source = TRACE_SOURCE.read_text(encoding="utf-8")
    for token in ("BC87/88/89", "BC8A", "BC8B", "stz $bd00,x",
                  "ldx #$22"):
        ENGINE.require(token in source, f"trace geometry token absent: {token}")
    truth = ElfTruth.read(
        ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    symbols = {name: (truth.symbol(name).value, truth.symbol(name).bytes)
               for name in ("vm_codebuf", "vm_buf_bank", "vmr_hdrlen",
                            "vmr_streaming", "c2_committed_roots",
                            "c2_decode_active", "c2_runtime", "c2_edma_job",
                            "c2_refill_trace_read")}
    ENGINE.require(symbols == {
        "vm_codebuf": (0xBFA4, 56), "vm_buf_bank": (0xBFDC, 1),
        "vmr_hdrlen": (0xBFDD, 2), "vmr_streaming": (0xBFED, 1),
        "c2_committed_roots": (0xC080, 2),
        "c2_decode_active": (0xC082, 2), "c2_runtime": (0xC084, 46),
        "c2_edma_job": (0xC0B2, 20), "c2_refill_trace_read": (0x23D6, 205),
    }, "selector-bypass blank-screen read geometry drift")
    ENGINE.require(not ENGINE.CAPTURE.exists() and not ENGINE.PARTIAL.exists(),
                   "selector-bypass blank-screen capture is one-shot")
    return {
        "authorization": {
            "authority": "owner-live-authorization",
            "date": "2026-08-24",
            "scope": (
                "one raw-first stopped-state read after post-library blank screen: "
                "registers/stack, VM/overlay status, boot runtime and refill "
                "origin/two slots; no resume, reset or input; CPU remains stopped"),
        },
        **bindings,
        "trace_source": bind(TRACE_SOURCE, "trace_source"),
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
    value["format"] = "lisp65-c2-v160-selector-bypass-blank-first-red-raw-v1"
    value["captured_on"] = "2026-08-24"
    value["claim_limit"] = (
        "Raw authorized stopped-state row only; attribution is separate. "
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
        print(f"selector-bypass-blank-first-red: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
