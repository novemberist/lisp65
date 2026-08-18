#!/usr/bin/env python3
"""Bind the recoverable evidence and limits of the Link-105 capture red."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))
import c2_v20_link105_phase02a_capture as C  # noqa: E402


RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-source-oracle-link105-phase02a-capture-first-red.json")
CHECKPOINT_SHA256 = "ee3226904a09dec32e33d6ddf913d961082167fc761e68249f729a4ae01dfe47"


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def derive() -> dict[str, Any]:
    checkpoint = C.load(C.CHECKPOINT)
    require(bind(C.CHECKPOINT)["sha256"] == CHECKPOINT_SHA256,
            "Link-105 static checkpoint identity drift")
    require(checkpoint["discipline"] == {
        "CPU_left_stopped": True, "D2_D5_executed": False,
        "raw_before_interpretation": True, "resets": 0, "resumes": 0,
        "runs": 0, "stops": 1}, "Link-105 checkpoint discipline drift")
    static = {row["name"]: bytes.fromhex(row["observed_hex"])
              for row in checkpoint["reads"]}
    selected = C.select_site(static)
    require(selected["site"] == "inner-Shelf-cross-read"
            and selected["row"] == 5 and selected["source"] == 0x081000C0
            and selected["target"] == 0xCF4D,
            "Link-105 retained site drift")
    frame = static["phase02a-preserved-frame-domain"]
    phase = selected["geometry"]["phase02a_frame"]
    require(phase == 0xCF1F, "Link-105 phase frame drift")
    at = lambda address, count: frame[address - 0xCF00:address - 0xCF00 + count]
    # The phase-02a record persists CRC bytes in wire order (high, low),
    # unlike the little-endian CPU words elsewhere in the frame.
    actual_expected = struct.unpack(">H", at(phase + 4, 2))[0]
    target = at(selected["target"], 32)
    c2d_target = at(selected["geometry"]["c2d_target"], 32)
    source_truth = C.SHELF.read_bytes()[32 + 5 * 32:64 + 5 * 32]
    c2d_truth = C.C2D.read_bytes()
    images = struct.unpack_from("<H", c2d_truth, 28)[0]
    c2d_row_truth = c2d_truth[images + 5 * 32:images + 6 * 32]
    require(actual_expected == C.crc16(source_truth) == C.crc16(target) == 0xE3F7,
            "Link-105 preserved expected/target truth drift")
    require(target == source_truth and c2d_target == c2d_row_truth
            and C.crc16(c2d_target) == 0xE9DC,
            "Link-105 preserved record truth drift")
    cpu_tables = static["linked-verifier-oracle-tables"]
    require(cpu_tables == b"\xff" * 24,
            "post-error CPU-view oracle row drift")
    return {
        "format": "lisp65-c2.3-v20-link105-phase02a-capture-first-red-v1",
        "recorded_on": "2026-08-13",
        "status": "CAPTURE-HARNESS-RED; STATIC-RAW-SALVAGED; MECHANISM-UNDECIDED",
        "authority": {"owner_authorization": C.git_authorization(),
                      "row": bind(C.ROW), "capture_driver": bind(C.DRIVER),
                      "static_checkpoint": bind(C.CHECKPOINT),
                      "first_red": bind(C.FIRST_RED), "candidate_elf": bind(C.ELF),
                      "shelf_truth": bind(C.SHELF), "c2d_truth": bind(C.C2D)},
        "device_discipline": {
            "static_checkpoint": checkpoint["discipline"],
            "dynamic_raw_persisted_before_interpretation": False,
            "CPU_left_stopped": True,
            "D2_D5_executed": False,
        },
        "raw_static_checkpoint": checkpoint,
        "preserved": {
            "tuple": checkpoint["tuple"], "fail_loop": checkpoint["fail_loop"],
            "site": selected,
            "actual_expected_crc16_from_preserved_phase_frame": "0xe3f7",
            "target_at_stop": {"address": "0x0000cf4d", "hex": target.hex(),
                               "crc16": "0xe3f7"},
            "delivery_bound_shelf_truth": {"row": 5, "hex": source_truth.hex(),
                                            "crc16": "0xe3f7"},
            "preceding_c2d_target_at_stop": {"address": "0x0000cf2d",
                                              "hex": c2d_target.hex(),
                                              "crc16": "0xe9dc"},
            "target_matches_delivery_truth_at_stopped_read": True,
            "configured_timeout_frames": 64,
            "stopped_frame_counter_hex": static["frame-counter"].hex(),
        },
        "harness_first_red": {
            "trigger": (
                "the post-error CPU view at logical 0xc356 contained 24 bytes "
                "of 0xff rather than the phase-02a overlay; the driver correctly "
                "refused to interpret that view as the linked oracle table"),
            "raw_first_gap": (
                "the separately issued dynamic 32-byte source/target reads were "
                "not persisted before the identity check raised"),
            "missing_authorized_fields": [
                "current c2_runtime.error / phase cutpoint",
                "persisted physical source row 0x081000c0",
                "surviving exact timeout start (the implementation restores it)"],
        },
        "classification": {
            "site": "inner D705 Shelf cross-read, record 5",
            "actual_expected_matches_delivery_truth": True,
            "target_matches_expected_at_stopped_read": True,
            "latency_claim": "NOT-YET-AUTHORIZED",
            "reason": (
                "without the current runtime error byte, this row cannot "
                "exclude a subsequent phase-02a Shelf-validation failure; "
                "the physical source read was not retained"),
        },
        "required_rescue_if_authorized": {
            "stops": 0, "resumes": 0,
            "physical_ranges": [
                {"address": "0x0000c080", "bytes": 50,
                 "purpose": "runtime phase/error/cutpoint"},
                {"address": "0x081000c0", "bytes": 32,
                 "purpose": "selected immutable Shelf source row"}],
            "rule": "persist both raw ranges before any interpretation",
        },
        "unlock": {"D1": False, "D2_D5": False},
        "claim_limit": (
            "This is a capture-harness first red, not a product, oracle-sourcing "
            "or transport-latency result. No further device read, resume, reset, "
            "repeat, fix, card, media, D2-D5 or release action is authorized."),
    }


def main() -> int:
    require(not RECEIPT.exists(), "Link-105 capture first-red receipt exists")
    value = derive()
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    require(C.load(RECEIPT) == derive(), "Link-105 first-red replay drift")
    print("Link-105 phase-02a: CAPTURE HARNESS RED; STATIC RAW SALVAGED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResultError, C.CaptureError, OSError, ValueError, KeyError,
            json.JSONDecodeError, struct.error) as error:
        print(f"LINK-105 PHASE02A FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
