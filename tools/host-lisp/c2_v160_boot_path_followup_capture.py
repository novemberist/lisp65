#!/usr/bin/env python3
"""Capture the commissioned v1.6 boot-path membership discriminator."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ENGINE_PATH = ROOT / "tools/host-lisp/c2_v21_phase1_rescue_capture.py"
SPEC = importlib.util.spec_from_file_location("c2_v21_phase1_rescue_capture", ENGINE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("raw-first stopped-state engine unavailable")
ENGINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE)

HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))
from elf_truth import ElfTruth  # noqa: E402


PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
ELF = ROOT / ("build/c2.3/v1.6-boot-refill-generator-template-card/wplto/"
              "lisp65-c2-substitution-linked.prg.elf")
FIRST = ROOT / ("build/c2.3/v1.6-boot-refill-dma-media/"
                "device-first-red-20260823/capture.json")
OUT = ROOT / "build/c2.3/v1.6-boot-path-followup-read-20260823"
AUTHORIZATION_COMMIT = "17be2562"
AUTHORIZATION_BYTES = 441522
AUTHORIZATION_SHA256 = "489ab518eab8ea8c92f1b50375593a9df47dc1feea6aaca1382f3ae476f725da"
EXPECTED = {
    "engine": "da6e7ebf54fe782657a0b896fe1acc86d8eef658e2001db5fb502225732e5322",
    "candidate_ELF": "02209a9ddda93b49bc3025f6b0caa9b2d88cb96b2504167b3ccc98d6f9ffba99",
    "first_red": "58c1ce79d6eb2f7f036569d0f23f6915e6162ec533a580201d262d35c5c5f0a0",
}

# Complete current continuation; VM refill window and every adjacent ownership
# field; verifier/family registries; active overlay transaction/generation; and
# the fixed MAP generation byte.  All addresses are asserted from ElfTruth.
RANGES = (
    ("lisp-toplevel-jmp-buf", 0x0000BD4B, 19),
    ("vm-codebuf-and-bookkeeping", 0x0000BFA4, 75),
    ("overlay-registry-bindings", 0x0000B98C, 40),
    ("overlay-call-family-generation", 0x0000BFF1, 10),
    ("overlay-zp-transaction-state", 0x00000074, 8),
    ("map-generation", 0x0000FF87, 1),
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    ENGINE.require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION_COMMIT}:{name}"],
                         cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    full = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION_COMMIT}^{{commit}}"],
                          cwd=ROOT, check=True, text=True,
                          stdout=subprocess.PIPE).stdout.strip()
    ENGINE.require(len(raw) == AUTHORIZATION_BYTES and sha(raw) == AUTHORIZATION_SHA256,
                   "follow-up authorization identity drift")
    for token in (b"Follow-up read specified", b"current `lisp_toplevel`",
                  b"`vm_codebuf`", b"generation/registry state",
                  b"No fix, no build, no media before the read decides"):
        ENGINE.require(token in raw, f"authorization token absent: {token!r}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def preflight() -> dict[str, Any]:
    bindings = {"engine": bind(ENGINE_PATH), "candidate_ELF": bind(ELF),
                "first_red": bind(FIRST)}
    ENGINE.require({name: row["sha256"] for name, row in bindings.items()} == EXPECTED,
                   "follow-up input identity drift")
    truth = ElfTruth.read(ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    symbols = {name: (truth.symbol(name).value, truth.symbol(name).bytes) for name in (
        "lisp_toplevel", "vm_codebuf", "vm_buf_bank", "vmr_hdrlen", "vmr_streaming",
        "__lisp65_rtov_binding_section_start", "__lisp65_rtov_binding_section_end",
        "rtov_call_result", "rtov_family", "rtov_family_generation",
        "rtov_call_context", "rtov_loaded_len", "C2K_MAP_GENERATION")}
    ENGINE.require(symbols == {
        "lisp_toplevel": (0xBD4B, 19), "vm_codebuf": (0xBFA4, 56),
        "vm_buf_bank": (0xBFDC, 1), "vmr_hdrlen": (0xBFDD, 2),
        "vmr_streaming": (0xBFED, 1),
        "__lisp65_rtov_binding_section_start": (0xB98C, 0),
        "__lisp65_rtov_binding_section_end": (0xB9B4, 0),
        "rtov_call_result": (0xBFF1, 2), "rtov_family": (0xBFF8, 1),
        "rtov_family_generation": (0xBFF9, 2),
        "rtov_call_context": (0x74, 2), "rtov_loaded_len": (0x79, 2),
        "C2K_MAP_GENERATION": (0xFF87, 0),
    }, "follow-up range geometry drift")
    ENGINE.require(not ENGINE.CAPTURE.exists() and not ENGINE.PARTIAL.exists(),
                   "follow-up capture is one-shot")
    source = Path(__file__).read_text(encoding="utf-8")
    capture_source = source.split("\nENGINE.OUT =", 1)[1]
    ENGINE.require('b"t0"' not in capture_source and 'b"g"' not in capture_source,
                   "follow-up source contains resume/run command")
    return {"authorization": authorization(), **bindings,
            "ranges": [{"name": name, "address": f"0x{address:08x}", "bytes": count}
                       for name, address, count in RANGES],
            "derived_symbols": {name: {"address": f"0x{value:04x}", "bytes": size}
                                for name, (value, size) in symbols.items()}}


ENGINE.OUT = OUT
ENGINE.CAPTURE = OUT / "capture.json"
ENGINE.PARTIAL = OUT / "capture.partial.json"
ENGINE.RANGES = RANGES
ENGINE.preflight = preflight


def main() -> int:
    ENGINE.require(len(sys.argv) == 2 and sys.argv[1] in {"preflight", "capture"},
                   "usage: c2_v160_boot_path_followup_capture.py preflight|capture")
    if sys.argv[1] == "preflight":
        print(json.dumps({"status": "PREFLIGHT PASS", "authority": preflight()},
                         indent=2, sort_keys=True))
        return 0
    value = ENGINE.capture()
    value["format"] = "lisp65-c2.3-v1.6-boot-path-followup-raw-v1"
    value["captured_on"] = "2026-08-23"
    value["claim_limit"] = ("Raw commissioned membership discriminator only; no fix "
                            "or mechanism claim; CPU remains stopped.")
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
    except (ENGINE.CaptureError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"c2-v160-boot-path-followup: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
