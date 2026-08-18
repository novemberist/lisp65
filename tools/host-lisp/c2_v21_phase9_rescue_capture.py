#!/usr/bin/env python3
"""Bind and capture the one authorized Link-109 phase-9 stopped-state row."""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ENGINE_PATH = ROOT / "tools/host-lisp/c2_v21_phase1_rescue_capture.py"
SPEC = importlib.util.spec_from_file_location("c2_v21_phase1_rescue_capture", ENGINE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("phase-1 raw-first capture engine unavailable")
ENGINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE)

OUT = ROOT / "build/c2.3/v2.1-map-mask-phase9-rescue"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.1-map-mask-d1-preparation-receipt.json")
ELF = ROOT / (
    "build/c2.3/v2.1-map-mask-fix-card/final/"
    "lisp65-c2-substitution-linked.prg.elf")
RUNNER = ROOT / "scripts/c2-v21-map-mask-d1-hw.sh"
CONTACT = ROOT / "build/c2.3/v2.1-map-mask-d1"
PRODUCT = CONTACT / "product-readback.d81"
LIBRARY = CONTACT / "library-readback.d81"
CONFIG = ROOT / "config/c2-v150-v21-map-mask-far-device-session.json"

AUTHORIZATION_COMMIT = "731bc72c"
AUTHORIZATION_BYTES = 88959
AUTHORIZATION_SHA256 = "3dd81e19eae3359ec97215fc84fbb7a88f5a9cf7d2dc2d241b0781937fb54d6b"
EXPECTED = {
    "preparation": "39d3914d1eef01b83b6f85272eacd1da1481a77146c4b5e154d966b96c1fdd8c",
    "candidate_ELF": "2091df026ad760ed5931d0290999aaf425ec3a0daa2ed6c96ce8f02e321162ba",
    "runner": "f6a576db13b9b1c4cc947259f9cba2491de666fa7e1f0689e6ed55ad2dc7671d",
    "product_readback": "bc0ac6cb10dff82022af2c1a3974b244a7b1979d2ceda9750ab8db787939527f",
    "library_readback": "15e4405929be0686d12c8079509fbd9e12f9314041218ed773fd57b895692060",
}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    ENGINE.require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION_COMMIT}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION_COMMIT}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    ENGINE.require(len(raw) == AUTHORIZATION_BYTES and sha(raw) == AUTHORIZATION_SHA256,
                   "phase-9 authorization identity drift")
    for token in (b"Phase 9 stopped-state read authorized", b"one read-only",
                  b"PC/MAP", b"stack", b"runtime and heap status",
                  b"one stop, no resume", b"D2\xe2\x80\x93D5 closed"):
        ENGINE.require(token in raw, f"authorization token absent: {token!r}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def preflight() -> dict[str, Any]:
    bindings = {"preparation": bind(PREP), "candidate_ELF": bind(ELF),
                "runner": bind(RUNNER), "product_readback": bind(PRODUCT),
                "library_readback": bind(LIBRARY), "engine": bind(ENGINE_PATH)}
    ENGINE.require({key: bindings[key]["sha256"] for key in EXPECTED} == EXPECTED,
                   "phase-9 input identity drift")
    ENGINE.require((CONTACT / "contact.consumed").is_file()
                   and (CONTACT / "owner-observation-awaiting").is_file()
                   and not (CONTACT / "owner-terminal-confirmed").exists(),
                   "preserved Link-109 owner-observed state absent")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    ENGINE.require(
        PRODUCT.read_bytes() == (ROOT / config["identity"]["product_medium"]).read_bytes()
        and LIBRARY.read_bytes() ==
            (ROOT / config["identity"]["library_medium"]).read_bytes(),
        "phase-9 media readback/source mismatch")
    ENGINE.require(not ENGINE.CAPTURE.exists() and not ENGINE.PARTIAL.exists(),
                   "phase-9 rescue capture is one-shot")
    capture_source = inspect.getsource(ENGINE.capture)
    ENGINE.require(capture_source.count('command(fd, b"t1"') == 1
                   and 'command(fd, b"t0"' not in capture_source
                   and 'command(fd, b"g"' not in capture_source,
                   "capture stop/no-resume discipline drift")
    ENGINE.require(ENGINE.RANGES == (
        ("bank0-zp-stack", 0x00000000, 0x0200),
        ("c2-runtime", 0x0000C080, 0x0032)),
        "phase-9 read domain drift")
    return {"authorization": authorization(), **bindings,
            "ranges": [{"name": name, "address": f"0x{address:08x}",
                        "bytes": count} for name, address, count in ENGINE.RANGES]}


ENGINE.OUT = OUT
ENGINE.CAPTURE = OUT / "capture.json"
ENGINE.PARTIAL = OUT / "capture.partial.json"
ENGINE.RANGES = (
    ("bank0-zp-stack", 0x00000000, 0x0200),
    ("c2-runtime", 0x0000C080, 0x0032),
)
ENGINE.preflight = preflight


def main() -> int:
    ENGINE.require(len(sys.argv) == 2 and sys.argv[1] in {"preflight", "capture"},
                   "usage: c2_v21_phase9_rescue_capture.py preflight|capture")
    if sys.argv[1] == "preflight":
        print(json.dumps({"status": "PREFLIGHT PASS", "authority": preflight()},
                         indent=2, sort_keys=True))
        return 0
    value = ENGINE.capture()
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
        print(f"c2-v21-phase9-rescue: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
