#!/usr/bin/env python3
"""Read the two authorized blank-screen discriminators from the stopped CPU."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
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

FIRST = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-domain-media/"
    "device-blank-first-red-20260824/capture.json")
ELF = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-domain-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
OUT = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-domain-media/"
    "device-blank-followup-20260824")
CAPTURE = OUT / "capture.json"
PARTIAL = OUT / "capture.partial.json"
DEVICE = os.environ.get("DEVICE", "/dev/ttyUSB1")
RANGES = (
    ("screen-indirect-target", 0x00000884, 2),
    ("native-loop-back-edge", 0x0000808C, 3),
)

EXPECTED = {
    "engine": "da6e7ebf54fe782657a0b896fe1acc86d8eef658e2001db5fb502225732e5322",
    "first_capture": "29a197788244c46ad457b0e743769da9bda2b82dc923d42f36038dfdb7fb979f",
    "candidate_ELF": "bbb1547779ea2c9366fa5a29633aa07061a3607fa753043071df1780cc5ea3e4",
}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    ENGINE.require(path.is_file() and not path.is_symlink(),
                   f"file absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def preflight() -> dict[str, Any]:
    bindings = {"engine": bind(ENGINE_PATH), "first_capture": bind(FIRST),
                "candidate_ELF": bind(ELF)}
    ENGINE.require({name: row["sha256"] for name, row in bindings.items()}
                   == EXPECTED, "blank-screen follow-up identity drift")
    first = json.loads(FIRST.read_text(encoding="utf-8"))
    ENGINE.require(first["tuple"]["PC"] == "0x2020"
                   and first["tuple"]["SP"] == "0x011e"
                   and first["tuple"]["MAPH"] == "0x8000"
                   and first["tuple"]["MAPL"] == "0x0000"
                   and first["discipline"]["CPU_left_stopped"] is True,
                   "blank-screen stopped-state tuple drift")
    ENGINE.require(not CAPTURE.exists() and not PARTIAL.exists(),
                   "blank-screen follow-up is one-shot")
    source = Path(__file__).read_text(encoding="utf-8")
    capture_source = source.split("\ndef capture() ->", 1)[1].split(
        "\ndef main() ->", 1)[0]
    ENGINE.require('command(fd, b"t1"' not in capture_source
                   and 'command(fd, b"t0"' not in capture_source
                   and 'command(fd, b"g"' not in capture_source,
                   "follow-up attempted stop/resume/run")
    return {
        "authorization": {
            "authority": "owner-live-authorization",
            "date": "2026-08-24",
            "scope": ("one follow-up read from the already stopped CPU: two "
                      "bytes at $0884 and three bytes at $808c; no stop, "
                      "resume, reset or input; CPU remains stopped"),
        },
        **bindings,
        "ranges": [{"name": name, "address": f"0x{address:08x}",
                    "bytes": count} for name, address, count in RANGES],
    }


def persist(value: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PARTIAL.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")


def capture() -> dict[str, Any]:
    authority = preflight()
    ENGINE.require(Path(DEVICE).is_char_device(), f"serial device absent: {DEVICE}")
    value: dict[str, Any] = {
        "format": "lisp65-c2-v160-selector-bypass-blank-followup-raw-v1",
        "captured_on": "2026-08-24", "authority": authority,
        "discipline": {"additional_stops": 0, "resumes": 0, "runs": 0,
                       "resets": 0, "input": 0, "CPU_left_stopped": True},
        "device": DEVICE, "reads": [],
    }
    fd = os.open(DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        ENGINE.configure_serial(fd)
        registers_raw = ENGINE.command(fd, b"r", 0.05)
        value["register_raw_hex"] = registers_raw.hex()
        value["tuple"] = ENGINE.parse_registers(registers_raw)
        ENGINE.require(value["tuple"]["PC"] == "0x2020"
                       and value["tuple"]["SP"] == "0x011e",
                       "CPU no longer at the preserved blank-screen stop")
        persist(value)
        for name, address, count in RANGES:
            row = ENGINE.read_range(fd, name, address, count, value)
            value["reads"].append(row)
            value.pop("active_range", None)
            persist(value)
    finally:
        os.close(fd)
    value["claim_limit"] = (
        "Five authorized live bytes only; mechanism attribution is separate. "
        "CPU remains stopped.")
    CAPTURE.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    PARTIAL.unlink()
    return value


def main() -> int:
    ENGINE.require(len(sys.argv) == 2 and sys.argv[1] in {"preflight", "capture"},
                   "usage: preflight|capture")
    if sys.argv[1] == "preflight":
        print(json.dumps({"status": "PREFLIGHT PASS", "authority": preflight()},
                         indent=2, sort_keys=True))
        return 0
    value = capture()
    print(json.dumps({"status": "CAPTURE PASS", "tuple": value["tuple"],
        "reads": [{"name": row["name"], "observed_hex": row["observed_hex"]}
                  for row in value["reads"]]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ENGINE.CaptureError, OSError, ValueError, KeyError) as error:
        print(f"selector-bypass-blank-followup: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
