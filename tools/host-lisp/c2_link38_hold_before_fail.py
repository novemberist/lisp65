#!/usr/bin/env python3
"""Build and evaluate the non-promotable Link-38 hold-before-fail patch."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK38 = ROOT / (
    "build/c2.2/substitution/"
    "product-link-38-c2-lite-v6-boot-crc-abi-replay")
BASE_PRODUCT = LINK38 / "lisp65-c2-substitution-linked.prg"
BASE_PRODUCT_SHA = (
    "61f406b57eeb2e258e941be432e8f6cea797c0623f421f09cc56e91f6f1419a2")
BASE_REPLAY = EVIDENCE / (
    "c2.2-product-link38-c2-lite-v6-boot-crc-abi-artifact-replay-receipt.json")
BASE_REPLAY_SHA = (
    "3cad09e6a609f7b7e860896bf30ba707a17acb68975b9d56d9ba1c08117f1cfc")
FIRST_RED = EVIDENCE / (
    "c2.2-product-link38-c2-lite-v6-hardware-line1-first-red-diagnosis.json")
FIRST_RED_SHA = (
    "d90edf4414d3bacf7081e4b46cea7f50a08b3a0227c9b36d2c6cdc565c9685bd")
BASE_DEPLOYMENT = ROOT / (
    "build/c2.2/hardware-presmoke-link38-c2-lite-v6/deployment.json")
BASE_DEPLOYMENT_SHA = (
    "56a916950c18ce6a285517c667b2aa16bd341bda91573fafc2ff10fbc28f60b1")

OUT = ROOT / (
    "build/c2.2/substitution/"
    "link38-c2-lite-hold-before-fail-NONPROMOTABLE")
PRODUCT = OUT / "lisp65-link38-hold-before-fail-NONPROMOTABLE.prg"
MANIFEST = OUT / "patch-manifest.json"
RECEIPT = EVIDENCE / (
    "c2.2-link38-c2-lite-hold-before-fail-instrumentation-receipt.json")
HW_OUT = ROOT / "build/c2.2/link38-c2-lite-hold-before-fail-hardware"
DEPLOYMENT = HW_OUT / "deployment.json"
HW_RECEIPT = EVIDENCE / (
    "c2.2-link38-c2-lite-hold-before-fail-hardware-receipt.json")

LOAD_ADDRESS = 0x2001
INSTRUCTION_ADDRESS = 0xAE23
INSTRUCTION_FILE_OFFSET = 2 + INSTRUCTION_ADDRESS - LOAD_ADDRESS
BEFORE = bytes.fromhex("80f6")       # BRA $AE1B (rtov_fail call edge)
AFTER = bytes.fromhex("80fe")        # BRA $AE23 (self-loop)
CHANGED_FILE_OFFSETS = (INSTRUCTION_FILE_OFFSET + 1,)

TARGET_ADDRESS = 0xC356
TARGET_BYTES = 1287
SOURCE_OFFSET = 0x3300
EXPECTED_CRC = 0xA8EA
BOOT_AT_ADDRESS = 0x08200000
CHIP_BANK3_ADDRESS = 0x00030000
FRAME_BYTES = 52


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def regular(path: Path) -> bytes:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode),
            f"artifact is not a regular symlink-free file: {path}")
    return path.read_bytes()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(regular(path))


def bind(path: Path) -> dict[str, Any]:
    data = regular(path)
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": len(data), "sha256": sha_bytes(data)}


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def crc16(data: bytes) -> int:
    value = 0xffff
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = (((value << 1) ^ 0x1021) & 0xffff
                     if value & 0x8000 else (value << 1) & 0xffff)
    return value


def prerequisites() -> dict[str, Any]:
    expected = {
        BASE_PRODUCT: BASE_PRODUCT_SHA,
        BASE_REPLAY: BASE_REPLAY_SHA,
        FIRST_RED: FIRST_RED_SHA,
        BASE_DEPLOYMENT: BASE_DEPLOYMENT_SHA,
    }
    for path, digest in expected.items():
        require(path.is_file() and sha(path) == digest,
                f"Link-38 authority drift: {path}")
    replay = json.loads(BASE_REPLAY.read_text(encoding="utf-8"))
    require(replay.get("status") ==
            "passed-link38-artifact-only-structural-closure-hardware-not-run",
            "Link-38 structural replay is not authoritative")
    first_red = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(first_red.get("status") ==
            "first-red-receipt-less-hardware-presmoke-stopped-before-repl",
            "Link-38 hardware First Red is not authoritative")
    return {
        "link38_product": bind(BASE_PRODUCT),
        "link38_structural_replay": bind(BASE_REPLAY),
        "link38_hardware_first_red": bind(FIRST_RED),
        "source_deployment": bind(BASE_DEPLOYMENT),
    }


def patch_gate(source: bytes, candidate: bytes) -> dict[str, Any]:
    require(int.from_bytes(source[:2], "little") == LOAD_ADDRESS,
            "Link-38 PRG load address drift")
    require(len(source) == len(candidate), "patch changed product length")
    require(source[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 2] == BEFORE,
            "Link-38 failure branch drift")
    require(candidate[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 2] == AFTER,
            "diagnostic self-loop absent")
    changed = [index for index, (left, right) in enumerate(zip(source, candidate))
               if left != right]
    require(changed == list(CHANGED_FILE_OFFSETS),
            f"unexpected patch diff domain: {changed}")
    mutations: dict[str, str] = {}
    variants = {
        "wrong-opcode": (INSTRUCTION_FILE_OFFSET, 0xea),
        "old-operand": (INSTRUCTION_FILE_OFFSET + 1, BEFORE[1]),
        "extra-byte": (INSTRUCTION_FILE_OFFSET + 2,
                       candidate[INSTRUCTION_FILE_OFFSET + 2] ^ 1),
    }
    for name, (offset, value) in variants.items():
        mutated = bytearray(candidate)
        mutated[offset] = value
        try:
            patch_gate_shallow(source, bytes(mutated))
        except GateError:
            mutations[name] = "rejected"
        else:
            raise GateError(f"patch mutation accepted: {name}")
    return {
        "status": "passed-exact-self-loop-instruction-patch",
        "load_address": f"0x{LOAD_ADDRESS:04x}",
        "instruction_address": f"0x{INSTRUCTION_ADDRESS:04x}",
        "instruction_file_offset": f"0x{INSTRUCTION_FILE_OFFSET:04x}",
        "instruction_span_bytes": 2,
        "changed_bytes": 1,
        "changed_file_offsets": [f"0x{value:04x}"
                                 for value in CHANGED_FILE_OFFSETS],
        "changed_cpu_addresses": ["0xae24"],
        "before_instruction_hex": BEFORE.hex(),
        "after_instruction_hex": AFTER.hex(),
        "before_semantics": "BRA $AE1B, then call rtov_fail and wipe",
        "after_semantics": "BRA $AE23, self-loop before rtov_fail and wipe",
        "file_size_delta_bytes": 0,
        "mutations": mutations,
        "precision_note": (
            "The authorized patch spans one two-byte instruction. The opcode "
            "remains 0x80; exactly its one-byte relative operand changes."),
    }


def patch_gate_shallow(source: bytes, candidate: bytes) -> None:
    require(len(source) == len(candidate), "patch length mutation")
    changed = [index for index, (left, right) in enumerate(zip(source, candidate))
               if left != right]
    require(changed == list(CHANGED_FILE_OFFSETS), "patch domain mutation")
    require(candidate[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 2] == AFTER,
            "patch instruction mutation")


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Link-38 diagnostic identity already exists")
    authority = prerequisites()
    source = regular(BASE_PRODUCT)
    require(source[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 2] == BEFORE,
            "Link-38 patch origin drift")
    candidate = bytearray(source)
    candidate[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 2] = AFTER
    candidate = bytes(candidate)
    gate = patch_gate(source, candidate)
    OUT.mkdir(parents=True)
    PRODUCT.write_bytes(candidate)
    require(regular(PRODUCT) == candidate, "diagnostic writeback drift")
    require(sha(PRODUCT) != BASE_PRODUCT_SHA,
            "diagnostic identity did not diverge from Link 38")
    manifest = {
        "format": "lisp65-c2-link38-hold-before-fail-patch-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-nonpromotable-fixed-length-instrumentation",
        "promotable": False,
        "authority": authority,
        "diagnostic_identity": bind(PRODUCT),
        "patch_gate": gate,
        "expected_witness": {
            "source": "Boot family in Chip Bank 3",
            "source_offset": f"0x{SOURCE_OFFSET:04x}",
            "destination_address": f"0x{TARGET_ADDRESS:04x}",
            "bytes": TARGET_BYTES,
            "crc16": f"0x{EXPECTED_CRC:04x}",
        },
        "capacity_effect": {
            "bank0_text_bytes": 0,
            "ordinary_bank0_bss_bytes": 0,
            "fixed_hot_block_bytes": 0,
            "resident_island_bytes": 0,
            "e000_bytes": 0,
            "runtime_overlay_bank_bytes": 0,
            "runtime_slice_bytes": 0,
            "file_bytes": 0,
        },
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0,
            "diagnostic_instruction_patches": 1,
            "instruction_span_bytes": 2, "changed_bytes": 1,
            "hardware_runs": 0, "promotable_candidates": 0,
        },
        "claim_limit": (
            "Permanently non-promotable diagnostic identity derived from the "
            "SHA-bound Link-38 product without compilation or relinking. It "
            "carries no product, capacity, promotion or acceptance claim."),
        "rollback_line": {**bind(BASE_PRODUCT), "status": "untouched"},
        "next_gate": "one authorized hold-before-fail hardware run",
    }
    write_json(MANIFEST, manifest)
    receipt = {**manifest, "manifest": bind(MANIFEST)}
    write_json(RECEIPT, receipt)
    for path in (PRODUCT, MANIFEST, RECEIPT):
        os.chmod(path, 0o444)
    os.chmod(OUT, 0o555)
    return receipt


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "Link-38 diagnostic receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") ==
            "passed-nonpromotable-fixed-length-instrumentation"
            and value.get("promotable") is False,
            "Link-38 diagnostic receipt is not green/non-promotable")
    prerequisites()
    source = regular(BASE_PRODUCT)
    candidate = regular(PRODUCT)
    require(bind(PRODUCT) == value["diagnostic_identity"],
            "diagnostic identity drift")
    patch_gate(source, candidate)
    require(all(delta == 0 for delta in value["capacity_effect"].values()),
            "diagnostic capacity delta is not zero")
    return value


def prepare_hardware() -> dict[str, Any]:
    receipt = check()
    require(not DEPLOYMENT.exists(), "diagnostic deployment already exists")
    source = json.loads(BASE_DEPLOYMENT.read_text(encoding="utf-8"))
    require(source.get("status") == "ready-receipt-less"
            and source.get("product", {}).get("sha256") == BASE_PRODUCT_SHA,
            "Link-38 source deployment drift")
    for row in source["preloads"]:
        path = ROOT / row["path"]
        require(len(regular(path)) == row["bytes"] and sha(path) == row["sha256"],
                f"source preload drift: {path}")
    deployment = {
        **source,
        "format": "lisp65-c2-link38-hold-before-fail-deployment-v1",
        "status": "ready-nonpromotable-hold-before-fail",
        "product": {**bind(PRODUCT), "address": "0x00002001"},
        "source_candidate": {
            "base_link38_product": bind(BASE_PRODUCT),
            "authorization_receipt": bind(RECEIPT),
            "patch_manifest": bind(MANIFEST),
        },
        "new_product_links": 0,
        "promotable": False,
        "claim_limit": (
            "One non-promotable hardware diagnostic; never a product "
            "presmoke, latency attempt, promotion or acceptance run."),
    }
    HW_OUT.mkdir(parents=True)
    write_json(DEPLOYMENT, deployment)
    return deployment


def verify_hardware() -> dict[str, Any]:
    check()
    require(DEPLOYMENT.is_file(), "diagnostic deployment absent")
    value = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    require(value.get("status") == "ready-nonpromotable-hold-before-fail"
            and value.get("promotable") is False
            and value.get("new_product_links") == 0,
            "diagnostic deployment status drift")
    require(bind(PRODUCT) == {key: value["product"][key]
                              for key in ("path", "bytes", "sha256")},
            "diagnostic deployment product drift")
    for row in value["preloads"]:
        path = ROOT / row["path"]
        require(len(regular(path)) == row["bytes"] and sha(path) == row["sha256"],
                f"diagnostic preload drift: {path}")
    return value


def u16(data: bytes, offset: int) -> int:
    return data[offset] | data[offset + 1] << 8


def parse_frame(bank0: bytes, low: bytes) -> dict[str, Any]:
    pointer = u16(low, 0x6e)
    require(pointer + FRAME_BYTES <= len(bank0),
            f"verifier frame pointer outside Bank 0: 0x{pointer:04x}")
    frame = bank0[pointer:pointer + FRAME_BYTES]
    return {
        "address": f"0x{pointer:04x}",
        "bytes": FRAME_BYTES,
        "sha256": sha_bytes(frame),
        "read_pointer": f"0x{u16(frame, 0):04x}",
        "file_off": f"0x{u16(frame, 2):04x}",
        "file_len": u16(frame, 4),
        "entry_off": f"0x{u16(frame, 6):04x}",
        "payload_crc": f"0x{u16(frame, 8):04x}",
        "payload_off": f"0x{u16(frame, 10):04x}",
        "image_limit": u16(frame, 12),
        "flags": f"0x{u16(frame, 14):04x}",
        "slot": frame[16],
        "count": frame[17],
        "seal": f"0x{u16(frame, 50):04x}",
        "expected_installer_tuple": (
            u16(frame, 2) == SOURCE_OFFSET
            and u16(frame, 4) == TARGET_BYTES
            and u16(frame, 8) == EXPECTED_CRC
            and frame[16] == 8),
    }


def evaluate_hardware() -> dict[str, Any]:
    deployment = verify_hardware()
    require(not HW_RECEIPT.exists(), "diagnostic hardware receipt already exists")
    boot_row = next(row for row in deployment["preloads"]
                    if int(row["address"], 16) == BOOT_AT_ADDRESS)
    boot = regular(ROOT / boot_row["path"])
    target_paths = [HW_OUT / f"held-target-{index}.bin"
                    for index in range(1, 4)]
    captures = [regular(path) for path in target_paths]
    require(all(len(value) == TARGET_BYTES for value in captures),
            "held target capture length drift")
    bank0_path = HW_OUT / "held-bank0-0000-ffff.bin"
    bank0 = regular(bank0_path)
    require(len(bank0) == 0x10000, "held Bank-0 capture length drift")
    low = bank0[:0x2000]
    bank3_path = HW_OUT / "held-chip-bank3-boot.bin"
    bank3 = regular(bank3_path)
    require(bank3 == boot, "held Chip-Bank-3 Boot family drift")

    held_state = {
        "busy": low[0x77],
        "fault": low[0x78],
        "family": low[0x79],
        "island_state": low[0x7a],
        "loaded_len": u16(low, 0x7b),
        "ready": low[0x6d],
    }
    # The pre-run hypothesis expected the 1,287-byte installer edge.  The
    # machine stopped earlier: the first Boot verifier tuple at the pinned
    # non-LTO table is the 1,135-byte catalog payload.  Derive the evaluated
    # span from that immutable table and the held length rather than forcing
    # the disproved hypothesis into the evidence.
    binding_address = 0xb9cd
    binding = bank0[binding_address:binding_address + 8]
    file_off = u16(binding, 0)
    file_len = u16(binding, 2)
    entry_off = u16(binding, 4)
    payload_crc = u16(binding, 6)
    require((file_off, file_len, entry_off, payload_crc) ==
            (0x0200, 1135, 0x0199, 0x399d),
            "held Boot catalog verifier binding drift")
    require(held_state["busy"] == 1
            and held_state["fault"] == 0
            and held_state["family"] == 1
            and held_state["island_state"] == 1
            and held_state["loaded_len"] == file_len,
            f"execution did not hold before rtov_fail/wipe: {held_state}")
    expected = boot[file_off:file_off + file_len]
    require(len(expected) == file_len and crc16(expected) == payload_crc,
            "held catalog payload authority drift")

    # At the self-loop, vm_runtime_overlay_exec_family has saved the CRC
    # return value in __rc6/__rc7.  The caller and the hand-written Leaf use
    # opposite ABI layouts: caller pointer in __rc2/__rc3 and length in A/X;
    # Leaf pointer in A/X and length in __rc2/__rc3.  Pin both instruction
    # sequences from the untouched Link-38 image so this is a data-flow proof,
    # not an inference from the wrong CRC alone.
    product = regular(BASE_PRODUCT)
    def product_bytes(address: int, length: int) -> bytes:
        offset = 2 + address - LOAD_ADDRESS
        return product[offset:offset + length]
    caller_sequence = product_bytes(0xad81, 15)
    leaf_sequence = product_bytes(0x222d, 10)
    require(caller_sequence == bytes.fromhex(
        "a57ba67ca0568404a0c38405202d22"),
        "Link-38 CRC caller ABI sequence drift")
    require(leaf_sequence == bytes.fromhex("85068607a9ff85088509"),
            "Link-38 CRC Leaf ABI sequence drift")
    on_device_crc = u16(low, 0x08)

    rows = []
    for index, (path, capture) in enumerate(zip(target_paths, captures), start=1):
        evaluated = capture[:file_len]
        rows.append({
            "capture": index,
            **bind(path),
            "captured_bytes": len(capture),
            "evaluated_prefix_bytes": file_len,
            "evaluated_prefix_crc16": f"0x{crc16(evaluated):04x}",
            "matches_expected": evaluated == expected,
            "nonmatching_bytes": sum(left != right
                                      for left, right in zip(evaluated, expected)),
        })
    evaluated_captures = [capture[:file_len] for capture in captures]
    stable = evaluated_captures[0] == evaluated_captures[1] == evaluated_captures[2]
    exact = all(capture == expected for capture in evaluated_captures)
    if exact:
        classification = "transport-exact-crc-leaf-abi-reversed"
        answer = (
            "The machine stopped on the first 1,135-byte Boot catalog edge, "
            "not the later installer edge assumed before the run. All three "
            "held $C356 prefixes are byteidentical to Bank 3 and host-CRC to "
            "0x399d. The target Leaf returned 0x2c14 because its handwritten "
            "ABI consumes pointer in A/X and length in __rc2/__rc3, while the "
            "linked caller supplies length in A/X and pointer in "
            "__rc2/__rc3. Transport is exonerated; the CRC Leaf ABI is "
            "structurally reversed at this call edge.")
        next_gate = "Class C: correct the CRC Leaf ABI and its data-flow gate"
    elif stable:
        classification = "transport-side-stably-wrong"
        answer = (
            "All held $C356 captures are byteidentically wrong while the "
            "authenticated frame and Bank-3 source remain exact. The fault is "
            "on the Bank3-to-$C356 transport/operand side, not delayed motion "
            "or outer cleanup.")
        next_gate = "Class C: diagnose the transport operands/length"
    else:
        classification = "transport-side-still-changing"
        answer = (
            "The held $C356 destination changes across read-only captures. "
            "The Chip-to-Chip transfer remained in motion after the verifier "
            "compared it, contradicting the immediate-completion premise.")
        next_gate = "Class C: revisit Chip-DMA completion semantics"

    value = {
        "format": "lisp65-c2-link38-hold-before-fail-hardware-v1",
        "recorded_on": "2026-07-21",
        "status": "answered-link38-bank3-island-edge",
        "promotable": False,
        "authorization": bind(RECEIPT),
        "deployment": bind(DEPLOYMENT),
        "diagnostic_identity": bind(PRODUCT),
        "patch_gate": json.loads(MANIFEST.read_text(encoding="utf-8"))
            ["patch_gate"],
        "observations": {
            "classification": classification,
            "expected": {
                "source_offset": f"0x{file_off:04x}",
                "destination": f"0x{TARGET_ADDRESS:04x}",
                "bytes": file_len,
                "entry_offset": f"0x{entry_off:04x}",
                "crc16": f"0x{payload_crc:04x}",
                "sha256": sha_bytes(expected),
            },
            "pre_run_hypothesis_falsified": {
                "assumed_edge": "installer payload",
                "assumed_source_offset": f"0x{SOURCE_OFFSET:04x}",
                "assumed_bytes": TARGET_BYTES,
                "assumed_crc16": f"0x{EXPECTED_CRC:04x}",
                "observed_first_edge": "Boot catalog payload",
            },
            "held_target_captures": rows,
            "captures_byteidentical": stable,
            "held_state": held_state,
            "verifier_binding": {
                "address": f"0x{binding_address:04x}",
                "raw_hex": binding.hex(),
                "file_off": f"0x{file_off:04x}",
                "file_len": file_len,
                "entry_off": f"0x{entry_off:04x}",
                "payload_crc": f"0x{payload_crc:04x}",
            },
            "crc_abi_witness": {
                "caller_address": "0xad81",
                "caller_sequence_hex": caller_sequence.hex(),
                "caller_semantics": (
                    "length from rtov_loaded_len enters A/X; $C356 enters "
                    "__rc2/__rc3 before JSR rtov_crc_mem"),
                "leaf_address": "0x222d",
                "leaf_sequence_hex": leaf_sequence.hex(),
                "leaf_semantics": (
                    "A/X is stored as pointer __rc4/__rc5; __rc2/__rc3 is "
                    "consumed as length"),
                "on_device_return_crc": f"0x{on_device_crc:04x}",
                "host_crc_over_exact_target": f"0x{crc16(expected):04x}",
                "abi_match": False,
            },
            "bank0": bind(bank0_path),
            "chip_bank3_boot": {**bind(bank3_path),
                                 "matches_deployed": True},
            "e000": bind(HW_OUT / "held-e000-ffff.bin"),
        },
        "answer": answer,
        "next_gate": next_gate,
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0,
            "diagnostic_instruction_patches": 1,
            "instruction_span_bytes": 2, "changed_bytes": 1,
            "hardware_runs": 1, "latency_attempts_consumed": "0/2",
            "read_only_post_stop_captures": 6,
        },
        "claim_limit": (
            "One non-promotable diagnostic hardware run. It is not a product "
            "presmoke, latency attempt, promotion or acceptance result."),
        "disposition": (
            "The diagnostic identity is isolated, read-only, and permanently "
            "excluded from candidate and promotion artifact sets."),
        "link38_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
    }
    write_json(HW_RECEIPT, value)
    for path in HW_OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(HW_OUT, 0o555)
    os.chmod(HW_RECEIPT, 0o444)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "build", "check", "prepare-hardware", "verify-hardware",
        "evaluate-hardware"))
    args = parser.parse_args()
    try:
        if args.action == "build":
            value = build()
        elif args.action == "check":
            value = check()
        elif args.action == "prepare-hardware":
            value = prepare_hardware()
        elif args.action == "verify-hardware":
            value = verify_hardware()
        else:
            value = evaluate_hardware()
        print("c2-link38-hold-before-fail: " + str(value["status"]))
        return 0
    except Exception as error:
        print("c2-link38-hold-before-fail: FAIL " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
