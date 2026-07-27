#!/usr/bin/env python3
"""Build and evaluate the nonpromotable Link-62 Slot-39 threshold hold."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE_RUN = ROOT / (
    "build/c2.2/c1-freezer-hardware-link62-"
    "cutpoints3-4-NONPROMOTABLE")
BASE_DEPLOYMENT = BASE_RUN / "deployment.json"
BASE_CARRIER = ROOT / (
    "build/c2.2/substitution/"
    "link62-c1-freezer-cutpoints-stage-bound-NONPROMOTABLE/"
    "runtime-overlays-session-c1-freezer-link62-stage-bound.bin")
ATTRIBUTION = EVIDENCE / (
    "c2.2-link62-slot39-completion-host-elf-attribution.json")
FIRST_RED = EVIDENCE / (
    "c2.2-link62-C1-Freezer-cutpoint3-"
    "prefreezer-hardware-first-red.json")

OUT = ROOT / (
    "build/c2.2/substitution/"
    "link62-slot39-threshold-hold-NONPROMOTABLE")
PATCHED_CARRIER = OUT / (
    "runtime-overlays-session-link62-slot39-"
    "threshold-hold-NONPROMOTABLE.bin")
PATCH_MANIFEST = OUT / "fixed-length-threshold-hold-manifest.json"
PATCH_RECEIPT = EVIDENCE / (
    "c2.2-link62-slot39-threshold-hold-nonpromotable-receipt.json")

HW_OUT = ROOT / (
    "build/c2.2/hardware-link62-slot39-"
    "threshold-hold-NONPROMOTABLE")
DEPLOYMENT = HW_OUT / "deployment.json"
HARDWARE_RECEIPT = EVIDENCE / (
    "c2.2-link62-slot39-threshold-hold-hardware-receipt.json")
HARDWARE_SCRIPT = ROOT / "scripts/c2-link62-slot39-threshold-hold-hw.sh"

SOURCE_SHA = (
    "f7ac2e34d8a8566e93c928c7bfa9aa7bc0379241ca01f6f7941694ba0faf2206")
ATTRIBUTION_SHA = (
    "739bd351360f480bd878c6c7ec3221b963a86e5e9a8c680969428705fe5e6dd4")
FIRST_RED_SHA = (
    "7c8309f790796c5b711e1d60fd818db038874ba0283ea3e458506556345645ab")
BASE_DEPLOYMENT_SHA = (
    "f06f679b1b60ad78aa821ae0df6af501de8905571d95fedc2a7bb7d4bea99234")

INSTRUCTION_VMA = 0xC8CA
INSTRUCTION_FILE_OFFSET = 56436
BEFORE = bytes.fromhex("b003")
AFTER = bytes.fromhex("b0fe")
CHANGED_FILE_OFFSETS = (INSTRUCTION_FILE_OFFSET + 1,)
TRACE_ADDRESS = 0xC1F0
RECORD_ADDRESS = 0xC17C
SEAL_ADDRESS = 0xC195
C2J_ADDRESS = 0x0005C640
FRAME_ADDRESS = 0xFF83
START_ZP_ADDRESS = 0x17
TIMEOUT_FRAMES = 64


class HoldError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise HoldError(message)


def regular(path: Path, label: str = "artifact") -> bytes:
    try:
        info = path.lstat()
    except OSError as error:
        raise HoldError(f"missing {label}: {path}: {error}") from error
    require(
        stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode),
        f"{label} is not a regular symlink-free file: {path}")
    return path.read_bytes()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(regular(path))


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    data = regular(path)
    result: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }
    if address is not None:
        result["address"] = f"0x{address:08x}"
    return result


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(regular(path, label).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise HoldError(f"invalid {label}: {path}: {error}") from error
    require(isinstance(value, dict), f"{label} root is not an object")
    return value


def write_exact(path: Path, data: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(regular(path) == data, f"existing generated artifact differs: {path}")
    else:
        path.write_bytes(data)
        os.chmod(path, mode)


def write_json(path: Path, value: dict[str, Any], mode: int = 0o644) -> None:
    write_exact(
        path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode(),
        mode)


def exact_patch_no_mutations(source: bytes, candidate: bytes) -> None:
    require(len(source) == len(candidate), "threshold patch changed carrier size")
    changed = [
        index for index, pair in enumerate(zip(source, candidate))
        if pair[0] != pair[1]]
    require(
        changed == list(CHANGED_FILE_OFFSETS),
        f"threshold patch changed unexpected bytes: {changed}")
    require(
        source[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 2] == BEFORE
        and candidate[
            INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 2] == AFTER,
        "threshold branch identity drift")


def exact_patch_gate(source: bytes, candidate: bytes) -> dict[str, Any]:
    exact_patch_no_mutations(source, candidate)
    mutations: dict[str, bytearray] = {}
    mutations["opcode-changed"] = bytearray(candidate)
    mutations["opcode-changed"][INSTRUCTION_FILE_OFFSET] ^= 1
    mutations["operand-unchanged"] = bytearray(candidate)
    mutations["operand-unchanged"][INSTRUCTION_FILE_OFFSET + 1] = BEFORE[1]
    mutations["wrong-self-loop-displacement"] = bytearray(candidate)
    mutations["wrong-self-loop-displacement"][INSTRUCTION_FILE_OFFSET + 1] = 0xFD
    mutations["extra-left-neighbour"] = bytearray(candidate)
    mutations["extra-left-neighbour"][INSTRUCTION_FILE_OFFSET - 1] ^= 1
    mutations["extra-right-neighbour"] = bytearray(candidate)
    mutations["extra-right-neighbour"][INSTRUCTION_FILE_OFFSET + 2] ^= 1
    rejected: dict[str, str] = {}
    for name, value in mutations.items():
        try:
            exact_patch_no_mutations(source, bytes(value))
        except HoldError:
            rejected[name] = "rejected"
        else:
            raise HoldError(f"threshold patch mutation accepted: {name}")
    return {
        "status": "passed-exact-threshold-branch-self-loop",
        "instruction_VMA": f"0x{INSTRUCTION_VMA:04x}",
        "instruction_file_offset": INSTRUCTION_FILE_OFFSET,
        "before_hex": BEFORE.hex(),
        "after_hex": AFTER.hex(),
        "instruction_bytes": 2,
        "changed_bytes": 1,
        "changed_file_offsets": list(CHANGED_FILE_OFFSETS),
        "carrier_size_delta": 0,
        "mutations_rejected": rejected,
        "mutation_count": len(rejected),
    }


def validate_authority() -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    require(sha(BASE_CARRIER) == SOURCE_SHA, "Link-62 carrier authority drift")
    require(sha(ATTRIBUTION) == ATTRIBUTION_SHA, "attribution authority drift")
    require(sha(FIRST_RED) == FIRST_RED_SHA, "hardware First-Red authority drift")
    require(
        sha(BASE_DEPLOYMENT) == BASE_DEPLOYMENT_SHA,
        "Link-62 deployment authority drift")
    attribution = load_json(ATTRIBUTION, "Slot-39 attribution")
    deployment = load_json(BASE_DEPLOYMENT, "Link-62 deployment")
    require(
        attribution["answers"]["classification"]
            == "evidence-model First Red; no product fix is justified yet"
        and attribution["recommended_next_class_C_question"]["post_link_patch"][
            "carrier_file_offset_opcode"] == INSTRUCTION_FILE_OFFSET
        and deployment["status"]
            == "ready-nonpromotable-Link62-cutpoints-3-and-4",
        "threshold-hold authorization chain drift")
    return regular(BASE_CARRIER), attribution, deployment


def patched_bytes(source: bytes) -> bytes:
    require(
        source[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 2] == BEFORE,
        "source carrier no longer has BCS +3 threshold edge")
    result = bytearray(source)
    result[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 2] = AFTER
    return bytes(result)


def prepare() -> dict[str, Any]:
    source, attribution, base_deployment = validate_authority()
    candidate = patched_bytes(source)
    gate = exact_patch_gate(source, candidate)
    write_exact(PATCHED_CARRIER, candidate, 0o444)

    patch_manifest = {
        "format": "lisp65-Link62-slot39-threshold-hold-manifest-v1",
        "status": "ready-nonpromotable-threshold-hold",
        "promotable": False,
        "source": bind(BASE_CARRIER, 0x08000000),
        "candidate": bind(PATCHED_CARRIER, 0x08000000),
        "patch": gate,
        "runtime_identity": {
            "slot": 39,
            "section": ".lisp65_rt_c2append_header",
            "threshold_frames": TIMEOUT_FRAMES,
            "hold_PC": f"0x{INSTRUCTION_VMA:04x}",
        },
    }
    write_json(PATCH_MANIFEST, patch_manifest, 0o444)

    patch_receipt = {
        "format": "lisp65-c2.2-Link62-slot39-threshold-hold-patch-v1",
        "recorded_on": "2026-07-24",
        "status": "passed-nonpromotable-threshold-hold-hardware-not-run",
        "promotable": False,
        "authority": {
            "host_ELF_attribution": bind(ATTRIBUTION),
            "hardware_First_Red": bind(FIRST_RED),
            "source_carrier": bind(BASE_CARRIER, 0x08000000),
            "source_deployment": bind(BASE_DEPLOYMENT),
            "driver": bind(Path(__file__)),
            "hardware_driver": bind(HARDWARE_SCRIPT),
        },
        "candidate": {
            "carrier": bind(PATCHED_CARRIER, 0x08000000),
            "manifest": bind(PATCH_MANIFEST),
            "identity_separate_from_Link62": True,
            "directory": OUT.relative_to(ROOT).as_posix(),
            "lifecycle": "nonpromotable; discard after the diagnostic receipt",
        },
        "exact_patch_gate": gate,
        "capture_contract": {
            "PC": f"breakpoint-trigger at ${INSTRUCTION_VMA:04x}",
            "poll_start": "$17 high, $1e low",
            "producer_seal": "$c195/$c196",
            "completion_record": "$c17c..$c19b",
            "target_C2J": "$05c640..$05c67f",
            "phase_trace": "$c1f0..$c1f7",
            "timed_capture_count": 3,
        },
        "construction": {
            "product_bytes_changed": 0,
            "carrier_bytes_changed": 1,
            "carrier_size_delta": 0,
            "compiler_runs": 0,
            "linker_runs": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "Nonpromotable diagnostic identity only; no product, C1, "
            "matrix-gate, acceptance-chain or release claim."),
    }
    write_json(PATCH_RECEIPT, patch_receipt, 0o444)

    preloads = []
    replaced = 0
    for row in base_deployment["preloads"]:
        copy = dict(row)
        if copy["sha256"] == SOURCE_SHA:
            copy = bind(PATCHED_CARRIER, int(copy["address"], 16))
            replaced += 1
        preloads.append(copy)
    require(replaced == 1, "source deployment does not uniquely name carrier")
    diagnostic_deployment = {
        "format": "lisp65-c2.2-Link62-slot39-threshold-hold-hardware-v1",
        "recorded_on": "2026-07-24",
        "status": "ready-nonpromotable-threshold-hold-hardware",
        "promotable": False,
        "authority": {
            "patch_receipt": bind(PATCH_RECEIPT),
            "patch_manifest": bind(PATCH_MANIFEST),
            "source_deployment": bind(BASE_DEPLOYMENT),
            "hardware_driver": bind(HARDWARE_SCRIPT),
        },
        "product": base_deployment["product"],
        "preloads": preloads,
        "test": {
            "form": "(defun %c1e () 't)",
            "hold_VMA": f"0x{INSTRUCTION_VMA:04x}",
            "timeout_frames": TIMEOUT_FRAMES,
            "capture_intervals_seconds": [0, 1, 5],
            "capture_count": 3,
        },
        "capture_domains": {
            "poll_start": {"address": "0x00000017", "bytes": 8},
            "completion_record": {"address": "0x0000c17c", "bytes": 32},
            "phase_trace": {"address": "0x0000c1f0", "bytes": 8},
            "runtime_ZP": {"address": "0x00000070", "bytes": 48},
            "current_frame": {"address": "0x0000ff83", "bytes": 5},
            "target_C2J": {"address": "0x0005c640", "bytes": 64},
            "runtime_slot39": {"address": "0x0000c356", "bytes": 1526},
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 0,
            "latency_attempts_consumed": 0,
        },
        "claim_limit": patch_receipt["claim_limit"],
    }
    write_json(DEPLOYMENT, diagnostic_deployment, 0o444)
    return {
        "status": "ready",
        "carrier_sha256": sha(PATCHED_CARRIER),
        "patch_mutations": gate["mutation_count"],
        "deployment": DEPLOYMENT.relative_to(ROOT).as_posix(),
    }


def verify() -> dict[str, Any]:
    source, _, base_deployment = validate_authority()
    candidate = regular(PATCHED_CARRIER, "patched carrier")
    gate = exact_patch_gate(source, candidate)
    manifest = load_json(PATCH_MANIFEST, "threshold manifest")
    receipt = load_json(PATCH_RECEIPT, "threshold patch receipt")
    deployment = load_json(DEPLOYMENT, "threshold deployment")
    require(
        manifest["candidate"]["sha256"] == sha(PATCHED_CARRIER)
        and receipt["status"]
            == "passed-nonpromotable-threshold-hold-hardware-not-run"
        and receipt["candidate"]["carrier"]["sha256"] == sha(PATCHED_CARRIER)
        and deployment["status"]
            == "ready-nonpromotable-threshold-hold-hardware"
        and deployment["product"] == base_deployment["product"]
        and deployment["execution_accounting"]["product_links"] == 0,
        "threshold diagnostic binding drift")
    for row in deployment["preloads"]:
        path = ROOT / row["path"]
        require(
            bind(path)["bytes"] == row["bytes"]
            and sha(path) == row["sha256"],
            f"threshold preload drift: {path}")
    return {
        "status": "verified",
        "carrier_sha256": sha(PATCHED_CARRIER),
        "patch_mutations": gate["mutation_count"],
    }


def capture_path(index: int, name: str) -> Path:
    return HW_OUT / f"capture-{index}" / f"{name}.bin"


def evaluate() -> dict[str, Any]:
    verify()
    pc_log = regular(HW_OUT / "threshold-pc.txt", "threshold PC log").decode(
        "utf-8", errors="replace")
    require(
        re.search(r"breakpoint\\s+@\\s+\\$?c8ca\\s+triggered", pc_log, re.I)
        is not None,
        "debugger did not bind PC=$c8ca")
    timing = load_json(HW_OUT / "capture-times.json", "capture timing")
    require(
        timing["interval_seconds"] == [0, 1, 5]
        and len(timing["captures"]) == 3,
        "three-capture timing contract drift")

    rows: list[dict[str, Any]] = []
    immutable_names = ("start-zp", "completion-record", "trace", "c2j")
    immutable: dict[str, list[bytes]] = {name: [] for name in immutable_names}
    for index in range(1, 4):
        start = regular(capture_path(index, "start-zp"))
        record = regular(capture_path(index, "completion-record"))
        trace = regular(capture_path(index, "trace"))
        zp = regular(capture_path(index, "runtime-zp"))
        frame = regular(capture_path(index, "frame"))
        c2j = regular(capture_path(index, "c2j"))
        require(
            len(start) == 8 and len(record) == 32 and len(trace) == 8
            and len(zp) == 48 and len(frame) == 5 and len(c2j) == 64,
            f"capture {index} geometry drift")
        for name, value in (
                ("start-zp", start), ("completion-record", record),
                ("trace", trace), ("c2j", c2j)):
            immutable[name].append(value)
        poll_start = start[7] | start[0] << 8
        current = frame[0] | frame[1] << 8
        elapsed = (current - poll_start) & 0xFFFF
        target_crc32 = zlib.crc32(c2j[:60]) & 0xFFFFFFFF
        target_seal = binascii.crc_hqx(c2j, 0xFFFF)
        producer_seal = int.from_bytes(record[25:27], "little")
        rows.append({
            "index": index,
            "captured_at_utc": timing["captures"][index - 1]["utc"],
            "poll_start": f"0x{poll_start:04x}",
            "current_frame": f"0x{current:04x}",
            "elapsed_frames": elapsed,
            "completion_mode": f"0x{record[24]:02x}",
            "journal_result": record[31],
            "producer_seal": f"0x{producer_seal:04x}",
            "target_seal": f"0x{target_seal:04x}",
            "seal_matches": producer_seal == target_seal,
            "target_format_CRC32": f"0x{target_crc32:08x}",
            "target_format_CRC32_valid":
                int.from_bytes(c2j[60:64], "little") == target_crc32,
            "slot_stamp": trace[4],
            "stamp_lock_flags": trace[5],
            "rtov_busy": zp[0x79 - 0x70],
            "rtov_loaded_len":
                int.from_bytes(zp[0x7B - 0x70:0x7D - 0x70], "little"),
        })

    for name, values in immutable.items():
        require(
            values[0] == values[1] == values[2],
            f"time-separated {name} witnesses are not stable")
    require(
        all(row["elapsed_frames"] >= TIMEOUT_FRAMES for row in rows)
        and all(row["slot_stamp"] == 39 for row in rows)
        and all(row["rtov_busy"] == 1 for row in rows)
        and all(row["rtov_loaded_len"] == 1532 for row in rows)
        and all(row["target_format_CRC32_valid"] for row in rows),
        "threshold hold did not capture the contracted runtime state")
    window = regular(HW_OUT / "runtime-slot39.bin", "runtime Slot-39")
    require(
        len(window) == 1526
        and window[INSTRUCTION_VMA - 0xC356:
                   INSTRUCTION_VMA - 0xC356 + 2] == AFTER,
        "runtime Slot-39 does not contain the threshold hold")

    first = rows[0]
    mode = int(first["completion_mode"], 16)
    seal_matches = first["seal_matches"]
    if mode == 0xA3:
        timeout_stage = (
            "rollback re-entry: an earlier Slot-39 failure/timeout already "
            "returned to the rollback plan")
    elif mode == 0xA1:
        timeout_stage = "initial ACTIVE bookend poll"
    else:
        timeout_stage = f"unexpected completion mode 0x{mode:02x}"

    if seal_matches:
        convergence = (
            "producer and captured target seals match at the threshold; "
            "the target became correct too late for the prior comparisons")
    else:
        convergence = (
            "producer and target seals differ at the threshold; "
            "producer/consumer identity divergence is proven")

    value = {
        "format": "lisp65-c2.2-Link62-slot39-threshold-hold-hardware-v1",
        "recorded_on": "2026-07-24",
        "status": "completed-nonpromotable-threshold-hold-discarded",
        "promotable": False,
        "authority": {
            "patch_receipt": bind(PATCH_RECEIPT),
            "deployment": bind(DEPLOYMENT),
            "patched_carrier": bind(PATCHED_CARRIER, 0x08000000),
            "PC_log": bind(HW_OUT / "threshold-pc.txt"),
            "capture_timing": bind(HW_OUT / "capture-times.json"),
            "driver": bind(Path(__file__)),
        },
        "PC_witness": {
            "value": "0xc8ca",
            "source": "hardware breakpoint trigger",
            "threshold_branch_taken": True,
        },
        "time_separated_captures": rows,
        "stable_witnesses": {
            name: {
                "byteidentical_across_three": True,
                "sha256": sha_bytes(values[0]),
            } for name, values in immutable.items()
        },
        "answers": {
            "timeout": (
                "the 64-frame fail-closed threshold was reached in linked "
                "target code"),
            "timeout_stage": timeout_stage,
            "convergence": convergence,
            "producer_seal": first["producer_seal"],
            "target_seal": first["target_seal"],
            "completion_mode": first["completion_mode"],
            "journal_result": first["journal_result"],
        },
        "diagnostic_lifecycle": {
            "identity": sha(PATCHED_CARRIER),
            "state": "discarded-after-capture",
            "archive_separation": OUT.relative_to(ROOT).as_posix(),
            "eligible_for_promotion": False,
        },
        "execution_accounting": {
            "diagnostic_hardware_runs": 1,
            "product_links": 0,
            "compiler_runs": 0,
            "latency_attempts_consumed": 0,
        },
        "captures": {
            "runtime_slot39": bind(HW_OUT / "runtime-slot39.bin", 0xC356),
            "screen": bind(HW_OUT / "threshold-screen.png"),
            "sets": {
                str(index): {
                    name: bind(capture_path(index, name), address)
                    for name, address in (
                        ("start-zp", START_ZP_ADDRESS),
                        ("completion-record", RECORD_ADDRESS),
                        ("trace", TRACE_ADDRESS),
                        ("runtime-zp", 0x70),
                        ("frame", FRAME_ADDRESS),
                        ("c2j", C2J_ADDRESS),
                    )
                } for index in range(1, 4)
            },
        },
        "claim_limit": (
            "Diagnostic answer only; no product fix, C1 closure, matrix-gate, "
            "acceptance-chain, promotion or release claim."),
    }
    write_json(HARDWARE_RECEIPT, value, 0o444)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "verify", "evaluate"))
    args = parser.parse_args()
    if args.action == "prepare":
        value = prepare()
    elif args.action == "verify":
        value = verify()
    else:
        value = evaluate()
    print(
        "c2-link62-slot39-threshold-hold: "
        + str(value.get("status", "ok")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HoldError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-link62-slot39-threshold-hold: FIRST RED: " + str(error))
        raise SystemExit(2)
