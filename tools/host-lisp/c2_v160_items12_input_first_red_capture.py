#!/usr/bin/env python3
"""Capture the one owner-authorized Comfort input First-Red stopped state."""

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
    raise RuntimeError("raw-first stopped-state engine unavailable")
ENGINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE)

PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
CONFIG = ROOT / "config/c2-v160-items12-device-session.json"
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-items12-device-preparation-receipt.json")
ELF = ROOT / (
    "build/c2.3/v1.6-items12-device-preparation/canonical-product/final/"
    "lisp65-c2-substitution-linked.prg.elf")
CONTACT = ROOT / "build/c2.3/v1.6-items12-device-contact"
PRODUCT = CONTACT / "product-readback.d81"
LIBRARY = CONTACT / "library-readback.d81"
OUT = CONTACT / "input-first-red-stopped-state"

AUTHORITY_COMMIT = "c65089ad72598b57f75d6ce5c55cee52ab55726a"
AUTHORITY_BYTES = 160211
AUTHORITY_SHA256 = "ea3135145bc850b0ee91435baafcf03fa6e96b63e3a028b91180ff891048a40b"
EXPECTED = {
    "engine": "da6e7ebf54fe782657a0b896fe1acc86d8eef658e2001db5fb502225732e5322",
    "config": "fcf8bceab1cc58391220715945d43bf91f5afe6377497780f3c1f8b80f580781",
    "preparation": "d9b0572574271501d76d13aab352597791ab4c4035411ae4df9bc1c4670cd5d1",
    "candidate_ELF": "4b2dfa0e7a33968863ec73f2162894ee1f644bd7ccbe6d9e745def7f376fb711",
    "product_readback": "025e1721b63a914213fb563e068d8784104182aa87059d26101cfe015bb765b5",
    "library_readback": "487d21131ed283de48d796ab191d6f41c906f127747761252be681119270a8f0",
}

RANGES = (
    ("bank0-zp-stack", 0x00000000, 0x0200),
    ("gc-runs", 0x0000B9F0, 0x0002),
    ("input-ring", 0x0000BC90, 0x0070),
    ("heap", 0x0000C25D, 0x00F0),
    ("c2-fixed-state", 0x0000FF80, 0x0010),
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    ENGINE.require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORITY_COMMIT}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    ENGINE.require(len(raw) == AUTHORITY_BYTES and sha(raw) == AUTHORITY_SHA256,
                   "owner authorization identity drift")
    for token in (b"uppercase and latency First Red", b"one `t1`",
                  b"No resume, reset, run or further", b"input follows"):
        ENGINE.require(token in raw, f"authorization token absent: {token!r}")
    return {"authority": "git-blob", "commit": AUTHORITY_COMMIT,
            "path": name, "bytes": len(raw), "sha256": sha(raw)}


def preflight() -> dict[str, Any]:
    bindings = {
        "engine": bind(ENGINE_PATH), "config": bind(CONFIG),
        "preparation": bind(PREPARATION), "candidate_ELF": bind(ELF),
        "product_readback": bind(PRODUCT), "library_readback": bind(LIBRARY),
    }
    ENGINE.require({name: row["sha256"] for name, row in bindings.items()} == EXPECTED,
                   "stopped-state input identity drift")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    ENGINE.require(
        PRODUCT.read_bytes() == (ROOT / config["media"]["product"]["path"]).read_bytes()
        and LIBRARY.read_bytes() ==
            (ROOT / config["media"]["library"]["path"]).read_bytes(),
        "mounted-media readback/source mismatch")
    ENGINE.require((CONTACT / "contact.consumed").is_file()
                   and (CONTACT / "owner-observation-awaiting").is_file(),
                   "owner contact state absent")
    ENGINE.require(not ENGINE.CAPTURE.exists() and not ENGINE.PARTIAL.exists(),
                   "input First-Red capture is one-shot")
    capture_source = inspect.getsource(ENGINE.capture)
    ENGINE.require(capture_source.count('command(fd, b"t1"') == 1
                   and 'command(fd, b"t0"' not in capture_source
                   and 'command(fd, b"g"' not in capture_source,
                   "one-stop/no-resume discipline drift")
    return {"authorization": authority(), **bindings,
            "ranges": [{"name": name, "address": f"0x{address:08x}", "bytes": count}
                       for name, address, count in RANGES]}


ENGINE.OUT = OUT
ENGINE.CAPTURE = OUT / "capture.json"
ENGINE.PARTIAL = OUT / "capture.partial.json"
ENGINE.RANGES = RANGES
ENGINE.preflight = preflight


def main() -> int:
    ENGINE.require(len(sys.argv) == 2 and sys.argv[1] in {"preflight", "capture"},
                   "usage: c2_v160_items12_input_first_red_capture.py preflight|capture")
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
        print(f"c2-v160-items12-input-first-red: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
