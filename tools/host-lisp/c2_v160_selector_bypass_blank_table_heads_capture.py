#!/usr/bin/env python3
"""Read the authorized thirteen X=0 indirect-table heads from the stopped CPU."""

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

FOLLOWUP = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-domain-media/"
    "device-blank-followup-20260824/capture.json")
ATTRIBUTION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-selector-bypass-blank-cycle-attribution.json")
ELF = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-domain-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
OUT = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-domain-media/"
    "device-blank-table-heads-20260824")
CAPTURE = OUT / "capture.json"
PARTIAL = OUT / "capture.partial.json"
DEVICE = os.environ.get("DEVICE", "/dev/ttyUSB1")

TABLES = (
    ("dispatch-b634", 0x0000B634, 0x4DB9),
    ("dispatch-b6b8", 0x0000B6B8, 0x6770),
    ("dispatch-fd4c", 0x0000FD4C, 0x742E),
    ("dispatch-fdd6", 0x0000FDD6, 0x6A10),
    ("dispatch-fdec", 0x0000FDEC, 0x70DF),
    ("dispatch-fdf4", 0x0000FDF4, 0x803D),
    ("dispatch-fd2c", 0x0000FD2C, 0x843D),
    ("dispatch-b6e6", 0x0000B6E6, 0x8DBD),
    ("dispatch-b6f2", 0x0000B6F2, 0x9517),
    ("dispatch-b71c", 0x0000B71C, 0xC7E5),
    ("dispatch-b624", 0x0000B624, 0xC43D),
    ("dispatch-b708", 0x0000B708, 0xC39D),
    ("dispatch-b62c", 0x0000B62C, 0xC49A),
)
RANGES = tuple((name, address, 2) for name, address, _expected in TABLES)

EXPECTED = {
    "engine": "da6e7ebf54fe782657a0b896fe1acc86d8eef658e2001db5fb502225732e5322",
    "followup": "8691c6105e4edbf9bbaa2c312760e3f50d680c185b3ff460c0f128533bab5525",
    "attribution": "1282b8f4ac446d17156345e961d0dbdc5f5943bdc46aa867f84103c28fe5b8c4",
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
    bindings = {
        "engine": bind(ENGINE_PATH), "followup": bind(FOLLOWUP),
        "attribution": bind(ATTRIBUTION), "candidate_ELF": bind(ELF),
    }
    ENGINE.require({name: row["sha256"] for name, row in bindings.items()}
                   == EXPECTED, "table-head read identity drift")
    followup = json.loads(FOLLOWUP.read_text(encoding="utf-8"))
    ENGINE.require(followup["tuple"]["PC"] == "0x2020"
                   and followup["tuple"]["SP"] == "0x011e"
                   and followup["tuple"]["MAPH"] == "0x8000"
                   and followup["tuple"]["MAPL"] == "0x0000"
                   and followup["discipline"]["CPU_left_stopped"] is True,
                   "preserved blank-screen tuple drift")
    attribution = json.loads(ATTRIBUTION.read_text(encoding="utf-8"))
    specified = attribution["open_mechanism"][
        "next_minimal_live_discriminator_if_state_is_still_available"]
    expected_rows = [
        {"address": f"0x{address:04x}", "bytes": 2,
         "expected": f"0x{expected:04x}"}
        for _name, address, expected in TABLES]
    ENGINE.require(specified["reads"] == expected_rows
                   and specified["total_bytes"] == 26,
                   "authorized table-head geometry differs from attribution")
    ENGINE.require(sum(count for _name, _address, count in RANGES) == 26,
                   "table-head byte budget drift")
    ENGINE.require(not CAPTURE.exists() and not PARTIAL.exists(),
                   "table-head read is one-shot")
    source = Path(__file__).read_text(encoding="utf-8")
    capture_source = source.split("\ndef capture() ->", 1)[1].split(
        "\ndef main() ->", 1)[0]
    ENGINE.require('command(fd, b"t1"' not in capture_source
                   and 'command(fd, b"t0"' not in capture_source
                   and 'command(fd, b"g"' not in capture_source,
                   "table-head read attempted stop/resume/run")
    return {
        "authorization": {
            "authority": "owner-live-authorization",
            "date": "2026-08-24",
            "scope": ("exactly 26 read-only bytes: the X=0 heads of all thirteen "
                      "indirect jump tables; no stop, resume, reset or input; CPU "
                      "remains stopped"),
        },
        **bindings,
        "ranges": [{"name": name, "address": f"0x{address:08x}",
                    "bytes": 2, "expected_u16": f"0x{expected:04x}"}
                   for name, address, expected in TABLES],
    }


def persist(value: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PARTIAL.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")


def capture() -> dict[str, Any]:
    authority = preflight()
    ENGINE.require(Path(DEVICE).is_char_device(), f"serial device absent: {DEVICE}")
    value: dict[str, Any] = {
        "format": "lisp65-c2-v160-selector-bypass-blank-table-heads-raw-v1",
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
                       and value["tuple"]["SP"] == "0x011e"
                       and value["tuple"]["MAPH"] == "0x8000"
                       and value["tuple"]["MAPL"] == "0x0000",
                       "CPU no longer at the preserved blank-screen stop")
        persist(value)
        for name, address, count in RANGES:
            item = ENGINE.read_range(fd, name, address, count, value)
            value["reads"].append(item)
            value.pop("active_range", None)
            persist(value)
    finally:
        os.close(fd)

    expected = {name: target for name, _address, target in TABLES}
    observed = {item["name"]: int.from_bytes(
        bytes.fromhex(item["observed_hex"]), "little") for item in value["reads"]}
    divergent = [{"name": name, "expected": f"0x{expected[name]:04x}",
                  "observed": f"0x{target:04x}"}
                 for name, target in observed.items() if target != expected[name]]
    targets_8040 = [name for name, target in observed.items() if target == 0x8040]
    if targets_8040:
        verdict = "TABLE SOURCE FOUND: live X=0 head targets $8040"
    elif not divergent:
        verdict = "ALL TABLE HEADS MATCH: indirect table-dispatch class excluded"
    else:
        verdict = "TABLE DRIFT PRESENT BUT NO X=0 HEAD TARGETS $8040"
    value["comparison"] = {
        "expected_count": 13, "observed_count": len(observed),
        "divergent": divergent, "targets_8040": targets_8040,
        "verdict": verdict,
    }
    value["claim_limit"] = (
        "Twenty-six authorized live bytes only. The table comparison decides "
        "only the X=0 indirect-dispatch class; CPU remains stopped.")
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
                  for row in value["reads"]],
        "comparison": value["comparison"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ENGINE.CaptureError, OSError, ValueError, KeyError) as error:
        print(f"selector-blank-table-heads: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
