#!/usr/bin/env python3
"""Close the G4-corrected defstruct full run against R/A/I/G.

The device receipt intentionally stopped before interpreting its two retained
refill views.  This checker resolves their owner tuple through the captured
C2D and Bank-2 backing planes, rebuilds the Phase-B state, and binds the first
failed persistent append without using refill or transaction metadata as an
oracle.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v16_defstruct_phase_b as PHASE_B  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
DEVICE = EVIDENCE / (
    "c2.3-v1.6-defstruct-ownership-crc-full-run-device-receipt.json"
)
PHASE_A = EVIDENCE / (
    "c2.3-v1.6-defstruct-phase-a-host-reconstruction-receipt.json"
)
PHASE_B_RECEIPT = EVIDENCE / (
    "c2.3-v1.6-defstruct-phase-b-guard-partition-receipt.json"
)
OVERLAYS = ROOT / (
    "build/c2.2/v1.2.5-candidate-product-link82/final/"
    "runtime-overlays-session-final.json"
)
RESULT = EVIDENCE / (
    "c2.3-v1.6-defstruct-ownership-crc-full-run-result-receipt.json"
)

FORMAT = "lisp65-c2.3-v1.6-defstruct-ownership-crc-full-run-result-v1"
RECORDED_ON = "2026-08-06"
C2_PRODUCT_CODE_BANK_TAG = 1
C2_CODE_HEADER_SCALAR_BYTES = 7
C2D_ENTRIES_OFFSET = 2096
C2D_ENTRY_BYTES = 10
OWNER_ORDINAL = 0x0274
RECORD_HEX = (
    "a1a2a31000a4017402a51000a60ba7a81400a9017402aa1400ab3e5c5dcc"
    "5ecccc5fcc60cccccc61ccccb2b327b400b500b6b701b800b900ba9701bbbc"
    "00bd0600"
)


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }


def u16(value: bytes, offset: int) -> int:
    require(offset >= 0 and offset + 2 <= len(value), "u16 outside artifact")
    return int.from_bytes(value[offset:offset + 2], "little")


def c2d_entry(c2d: bytes, ordinal: int) -> dict[str, Any]:
    at = C2D_ENTRIES_OFFSET + ordinal * C2D_ENTRY_BYTES
    raw = c2d[at:at + C2D_ENTRY_BYTES]
    require(len(raw) == C2D_ENTRY_BYTES, "C2D entry outside captured plane")
    return {
        "ordinal": ordinal,
        "raw_hex": raw.hex(),
        "image_slot": raw[0],
        "literal_count": raw[1],
        "code_offset": u16(raw, 2),
        "code_length": u16(raw, 4),
        "resolution_base": u16(raw, 6),
        "generation": u16(raw, 8),
    }


def bound_capture(device: dict[str, Any], name: str) -> tuple[bytes, dict[str, Any]]:
    row = device["backing_plane_oracles"][name]
    path = ROOT / row["path"]
    binding = bind(path)
    require(
        binding == {key: row[key] for key in ("path", "bytes", "sha256")},
        f"{name} capture binding drift",
    )
    return path.read_bytes(), binding


def record_field(device: dict[str, Any], name: str) -> dict[str, Any]:
    row = device["decoded_record"][name]
    require(isinstance(row, dict), f"record field absent: {name}")
    return row


def derive() -> dict[str, Any]:
    device = load(DEVICE)
    phase_a = load(PHASE_A)
    phase_b = load(PHASE_B_RECEIPT)
    overlays = load(OVERLAYS)

    require(
        device["format"] == "lisp65-c2.3-v1.6-ownership-crc-full-run-device-v1"
        and device["recorded_on"] == RECORDED_ON,
        "device receipt identity drift",
    )
    require(
        device["result"] == {
            "CPU_left_stopped": True,
            "R_A_I_G": None,
            "boot_witness": "0x44",
            "classification_widened": False,
            "mem_init": "INIT-BUILT-NO-FAILURE-REPRODUCED",
            "record_stable_reads": 3,
        },
        "device result prerequisite drift",
    )
    stable = device["stable_record_reads"]
    require(
        len(stable) == 3
        and [row["index"] for row in stable] == [1, 2, 3]
        and all(row["hex"] == RECORD_HEX for row in stable),
        "diagnostic record is not stable 3/3",
    )

    bank2, bank2_bind = bound_capture(device, "Bank-2")
    c2d, c2d_bind = bound_capture(device, "C2D")
    c2j, c2j_bind = bound_capture(device, "C2J")
    require(
        len(bank2) == 65536
        and len(c2d) == 50816
        and c2d[:8] == b"C2D\0\x06\x30\x20\x0a"
        and len(c2j) == 64
        and c2j == bytes(64)
        and c2d[-64:] == c2j,
        "captured backing-plane geometry/C2J drift",
    )

    require_counts = phase_a["require_only_control"]["final_counts"]
    counts = {
        "images": u16(c2d, 12),
        "entries": u16(c2d, 16),
        "resolutions": u16(c2d, 20),
        "roots": u16(c2d, 24),
    }
    require(
        counts == {key: require_counts[key] for key in counts},
        "target C2D is not the exact Phase-A post-require state",
    )
    code_bytes = max(
        c2d_entry(c2d, ordinal)["code_offset"]
        + c2d_entry(c2d, ordinal)["code_length"]
        for ordinal in range(counts["entries"])
    )
    require(code_bytes == require_counts["code_bytes"] == 44933,
            "post-require code extent drift")

    owner = c2d_entry(c2d, OWNER_ORDINAL)
    require(
        owner == {
            "ordinal": 628,
            "raw_hex": "0506908d2a0006090100",
            "image_slot": 5,
            "literal_count": 6,
            "code_offset": 36240,
            "code_length": 42,
            "resolution_base": 2310,
            "generation": 1,
        },
        "captured active-owner C2D row drift",
    )
    object_end = owner["code_offset"] + owner["code_length"]
    require(object_end <= len(bank2), "active owner outside captured Bank-2")
    obj = bank2[owner["code_offset"]:object_end]
    header_bytes = C2_CODE_HEADER_SCALAR_BYTES + 2 * owner["literal_count"]
    require(
        len(obj) == 42
        and header_bytes == 19
        and obj.hex() == (
            "b50200021700060000000000000000000000000b3c00010c3c01020b3c0201"
            "0b3c03010b3c04013e0504"
        ),
        "captured active-owner object drift",
    )

    fills: list[dict[str, Any]] = []
    fill_rows = (("previous-fill", 16, 0x0B), ("last-fill", 20, 0x3E))
    for prefix, cursor, expected in fill_rows:
        complete = record_field(device, f"{prefix}.complete")
        cursor_row = record_field(device, f"{prefix}.cursor")
        owner_row = record_field(device, f"{prefix}.owner")
        win_row = record_field(device, f"{prefix}.window-base")
        fetched_row = record_field(device, f"{prefix}.fetched-opcode")
        owner_raw = bytes.fromhex(owner_row["value_hex"])
        require(
            complete["state"] == "reached"
            and cursor_row["value_le"] == cursor
            and win_row["value_le"] == cursor
            and owner_raw[0] == C2_PRODUCT_CODE_BANK_TAG
            and int.from_bytes(owner_raw[1:3], "little") == OWNER_ORDINAL,
            f"{prefix} identity/cursor drift",
        )
        source_byte = obj[header_bytes + cursor]
        require(source_byte == expected and fetched_row["value_le"] == expected,
                f"{prefix} source-byte mismatch")
        fills.append({
            "tagged": True,
            "identity_correct": True,
            "owner_bank_tag": owner_raw[0],
            "owner_ordinal": int.from_bytes(owner_raw[1:3], "little"),
            "cursor": cursor,
            "fetched": fetched_row["value_le"],
            "expected": source_byte,
            "oracle": "bound-C2D-source",
        })

    append_checkpoint = record_field(
        device, "append.first-non-ok-checkpoint"
    )
    append_complete = record_field(device, "append.complete")
    append_owner = record_field(device, "append.phase-owner")
    append_c2j = record_field(device, "append.c2j-state")
    require(
        append_complete["state"] == "reached"
        and append_checkpoint["state"] == "reached"
        and append_checkpoint["value_le"] == 39
        and append_owner["value_le"] == 0
        and append_c2j["value_le"] == 0,
        "append transaction result drift",
    )

    state = PHASE_B.base_state()
    state["fills"] = [{
        "tagged": row["tagged"],
        "identity_correct": row["identity_correct"],
        "fetched": row["fetched"],
        "expected": row["expected"],
        "oracle": row["oracle"],
    } for row in fills]
    state["append"] = {
        "reached": True,
        "failure_checkpoint": 39,
        "phase_owner": append_owner["value_le"],
        "c2j": "CLEAR",
        "non_ok": True,
    }
    error_complete = record_field(device, "first-error.complete")
    state["error"] = {
        "reached": error_complete["state"] == "reached",
        "status": None,
        "edge": None,
    }
    state["gc"] = {
        "reached": record_field(device, "gc.complete")["state"] == "reached",
        "mem_oom": record_field(device, "gc.mem-oom")["value_le"],
        "runs": record_field(device, "gc.runs")["value_le"],
    }
    state["irq"] = {
        "reached": record_field(device, "irq.source-less-entry-2")["state"]
        == "reached",
        "source_less_entry": 2,
        "episode_latch": record_field(device, "irq.episode-latch")["value_le"],
        "d019": record_field(device, "irq.d019")["value_le"],
        "d01a": record_field(device, "irq.d01a")["value_le"],
        "return_pc": record_field(device, "irq.interrupted-return-pc")["value_le"],
    }
    selected = PHASE_B.classify(state)
    require(selected == "A", f"R/A/I/G selection drift: {selected}")

    slot = [row for row in overlays["slices"] if row["id"] == 39]
    require(len(slot) == 1, "runtime overlay slot 39 is not unique")
    slot39 = slot[0]
    expected_slot = {
        "id": 39,
        "name": "c2-append-header",
        "section": ".lisp65_rt_c2append_header",
        "source_address": 251648,
        "vma": 50006,
        "entry": 50033,
        "file_size": 1419,
        "memory_size": 1419,
        "sha256": "57daff5bb39482b08f14f936fe9342e8ec3cf07ce2c24393d09ccea3d05f61e2",
    }
    require(
        {key: slot39[key] for key in expected_slot} == expected_slot,
        "slot-39 overlay authority drift",
    )

    forms = phase_a["windowed_sequence"]["forms"]
    generated = [row for row in forms if row["kind"] == "persistent-definition"]
    require(
        len(generated) == 9
        and generated[0]["entry"] == "make-point"
        and generated[0]["append"]["before"] == {
            "entry": 757, "generation": 1, "image": 8, "journal": "CLEAR"
        }
        and generated[0]["append"]["after"] == {
            "entry": 758, "generation": 1, "image": 9, "journal": "CLEAR"
        }
        and c2d_entry(c2d, 757)["raw_hex"] == "00" * 10,
        "first generated persistent definition boundary drift",
    )

    require(
        device["mem_init"]["classification"]
        == "INIT-BUILT-NO-FAILURE-REPRODUCED"
        and device["mem_init"]["snapshot"]["after"] == {
            "EXT_occupancy": 0,
            "alloc_high": 0,
            "freelist_head": "0x0060",
            "reached": True,
            "tag": "0xa6",
        },
        "mem_init witness drift",
    )
    require(
        device["stop"]["code_owner"]["selected_owner"]
        == "ownership-CRC-bound-diagnostic-PRG"
        and device["stop"]["code_owner"]["unique"] is True
        and device["stop"]["PC"] == "0xb431",
        "stopped code-owner binding drift",
    )

    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "A-PERSISTENT-APPEND-SLOT39-HEADER-NON-OK",
        "authorities": {
            "device": bind(DEVICE),
            "phase_A": bind(PHASE_A),
            "phase_B": bind(PHASE_B_RECEIPT),
            "runtime_overlay_manifest": bind(OVERLAYS),
            "backing_planes": {
                "Bank-2": bank2_bind,
                "C2D": c2d_bind,
                "C2J": c2j_bind,
            },
        },
        "stopped_state": {
            "PC": "0xb431",
            "code_owner": "ownership-CRC-bound-diagnostic-PRG",
            "record_hex": RECORD_HEX,
            "stable_reads": 3,
            "CPU_left_stopped": True,
        },
        "mem_init": {
            "classification": "INIT-BUILT-NO-FAILURE-REPRODUCED",
            "after_freelist_head": "0x0060",
            "current_freelist_head": "0x0354",
        },
        "source_oracle": {
            "owner_model": "Link-82 C2 product bank-tag plus C2D ordinal",
            "bank_tag": C2_PRODUCT_CODE_BANK_TAG,
            "ordinal": OWNER_ORDINAL,
            "C2D_entry": owner,
            "object_sha256": sha_bytes(obj),
            "header_bytes": header_bytes,
            "retained_fills": fills,
            "R_excluded": True,
            "scope": "last-two-retained-completed-refills-only",
        },
        "post_require_state": {
            **counts,
            "code_bytes": code_bytes,
            "matches_Phase_A_require_only": True,
            "next_C2D_entry_757_raw_hex": "00" * 10,
        },
        "decision": {
            "R_A_I_G": selected,
            "classifier": "c2_v16_defstruct_phase_b.classify",
            "terminal_precedence": phase_b["facts"]["decision"]
            ["terminal_precedence"],
            "append": {
                "first_non_ok_checkpoint": 39,
                "slot": expected_slot,
                "phase_owner_after_cleanup": "NONE",
                "C2J_after_cleanup": "CLEAR",
                "first_failed_persistent_definition": "make-point",
                "target_definition_landed": False,
            },
            "excluded": {
                "R": "both retained completed refill bytes equal captured source",
                "G": "first-error record unreached and mem_oom=0",
                "I": "A has precedence and pure-I precondition D01A=1 is absent (D01A=0)",
            },
        },
        "accounting": {
            "product_bytes_changed": 0,
            "product_links": 0,
            "device_recontacts": 0,
            "measured_forms": 1,
        },
        "claim_limit": (
            "A is attributed to c2-append-header slot 39 on the first generated "
            "persistent append (make-point). This result does not identify the "
            "internal predicate within that 1419-byte slice, claim F018B membership, "
            "authorize a fix/link/device run, or widen the two retained refill views "
            "into a claim about every historical refill."
        ),
    }


def audit(value: dict[str, Any]) -> None:
    expected = derive()
    require(value == expected, "result receipt differs from independently derived result")


def selftest() -> dict[str, Any]:
    base = derive()
    cases: list[tuple[list[Any], Any]] = [
        (["status"], "R"),
        (["stopped_state", "CPU_left_stopped"], False),
        (["stopped_state", "stable_reads"], 2),
        (["mem_init", "classification"], "INIT-NEVER-BUILT"),
        (["source_oracle", "bank_tag"], 2),
        (["source_oracle", "ordinal"], 627),
        (["source_oracle", "C2D_entry", "code_offset"], 0),
        (["source_oracle", "header_bytes"], 7),
        (["source_oracle", "retained_fills", 0, "cursor"], 15),
        (["source_oracle", "retained_fills", 0, "fetched"], 0x3B),
        (["source_oracle", "retained_fills", 1, "expected"], 0x0B),
        (["source_oracle", "R_excluded"], False),
        (["post_require_state", "entries"], 758),
        (["post_require_state", "code_bytes"], 44934),
        (["post_require_state", "next_C2D_entry_757_raw_hex"], "01" + "00" * 9),
        (["decision", "R_A_I_G"], "G"),
        (["decision", "terminal_precedence"], ["R", "G", "A", "I"]),
        (["decision", "append", "first_non_ok_checkpoint"], 38),
        (["decision", "append", "slot", "name"], "c2-append-code"),
        (["decision", "append", "slot", "sha256"], "0" * 64),
        (["decision", "append", "phase_owner_after_cleanup"], "APPEND"),
        (["decision", "append", "C2J_after_cleanup"], "ACTIVE"),
        (["decision", "append", "first_failed_persistent_definition"], "point-p"),
        (["decision", "append", "target_definition_landed"], True),
        (["accounting", "product_bytes_changed"], 1),
        (["accounting", "product_links"], 1),
        (["accounting", "device_recontacts"], 1),
        (["claim_limit"], "F018B member; fix authorized"),
    ]
    rejected: dict[str, str] = {}
    for index, (path, replacement) in enumerate(cases, 1):
        trial = deepcopy(base)
        cursor: Any = trial
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except ResultError as error:
            rejected[f"mutation-{index:02d}"] = str(error)
        else:
            raise ResultError(f"result mutation survived: {path}")
    return {
        "status": "SELFTEST PASS",
        "mutations": len(rejected),
        "R_A_I_G": base["decision"]["R_A_I_G"],
        "checkpoint": base["decision"]["append"]["first_non_ok_checkpoint"],
        "rejected": rejected,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("derive", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "derive":
        value = derive()
    elif args.action == "selftest":
        value = selftest()
    else:
        audit(load(RESULT))
        value = {
            "status": "PASS",
            "R_A_I_G": "A",
            "checkpoint": 39,
            "slice": "c2-append-header",
        }
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResultError, OSError, ValueError, KeyError, IndexError,
            json.JSONDecodeError) as error:
        print(f"OWNERSHIP CRC FULL-RUN RESULT FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
