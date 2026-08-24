#!/usr/bin/env python3
"""Capture the authorized execution-boundary Low-RAM discriminator."""

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


ELF = ROOT / (
    "build/c2.3/v1.6-execution-boundary-backstop-uint8-irq-return-"
    "replacement-card/wplto/lisp65-c2-substitution-linked.prg.elf")
FIRST = ROOT / "build/c2.3/v1.6-execution-boundary-first-red/capture.json"
ATTRIBUTION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-execution-boundary-first-red-attribution.json")
OUT = ROOT / "build/c2.3/v1.6-execution-boundary-followup-read-20260824"
EXPECTED = {
    "engine": "da6e7ebf54fe782657a0b896fe1acc86d8eef658e2001db5fb502225732e5322",
    "candidate_ELF": "c8b74690e682370f14c68bc837cd9642b702df024e71c82753b0b21d678fd10d",
    "first_red": "334e67a7a4ecd746c381fc38751607c916d35b100390ddba5abdbe20c14c94d4",
    "attribution": "407c7c9968167645f3269040a9575518cc512322c59829a62dfadf9767dd973f",
}

RANGES = (
    ("current-lisp-toplevel-jmp-buf", 0x0000BD49, 19),
    ("vm-codebuf-and-bookkeeping", 0x0000BFA4, 75),
    ("low-ram-brk-neighborhood", 0x00000600, 16),
    ("IRQ-episode-state", 0x0000FF83, 11),
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    ENGINE.require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def preflight() -> dict[str, Any]:
    bindings = {"engine": bind(ENGINE_PATH), "candidate_ELF": bind(ELF),
                "first_red": bind(FIRST), "attribution": bind(ATTRIBUTION)}
    ENGINE.require({name: row["sha256"] for name, row in bindings.items()}
                   == EXPECTED, "follow-up input identity drift")
    truth = ElfTruth.read(ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    symbols = {name: (truth.symbol(name).value, truth.symbol(name).bytes)
               for name in ("lisp_toplevel", "vm_codebuf", "vm_buf_bank",
                            "vmr_hdrlen", "vmr_streaming")}
    ENGINE.require(symbols == {
        "lisp_toplevel": (0xBD49, 19), "vm_codebuf": (0xBFA4, 56),
        "vm_buf_bank": (0xBFDC, 1), "vmr_hdrlen": (0xBFDD, 2),
        "vmr_streaming": (0xBFED, 1),
    }, "follow-up candidate geometry drift")
    decision = json.loads(ATTRIBUTION.read_text(encoding="utf-8"))
    expected_ranges = decision["open_mechanism"]["minimal_discriminator_read"]
    ENGINE.require([(row["name"], int(str(row["address"]).split()[-1], 16)
                    if "derived" in str(row["address"]) else int(row["address"], 16),
                    int(row["bytes"])) for row in expected_ranges] == list(RANGES),
                   "follow-up ranges differ from attributed minimum")
    ENGINE.require(not ENGINE.CAPTURE.exists() and not ENGINE.PARTIAL.exists(),
                   "execution-boundary follow-up is one-shot")
    return {
        "authorization": {"authority": "owner-live-authorization",
                          "date": "2026-08-24",
                          "scope": ("four attributed read-only ranges at the conserved stop; "
                                    "no resume, reset, run or input; CPU remains stopped")},
        **bindings,
        "ranges": [{"name": name, "address": f"0x{address:08x}", "bytes": count}
                   for name, address, count in RANGES],
        "derived_symbols": {name: {"address": f"0x{value:04x}", "bytes": size}
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
    value["format"] = "lisp65-c2-v160-execution-boundary-followup-raw-v1"
    value["captured_on"] = "2026-08-24"
    value["claim_limit"] = (
        "Raw authorized discriminator only; attribution is separate. CPU remains stopped.")
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
        print(f"execution-boundary-followup: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
