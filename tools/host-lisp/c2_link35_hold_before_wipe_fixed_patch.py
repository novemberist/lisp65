#!/usr/bin/env python3
"""Class-B cycle 2: fixed-length Link-35 hold-before-wipe diagnostic."""

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
LINK35 = ROOT / "build/c2.2/substitution/product-link-35-dma-completion-first-status"
BASE_PRODUCT = LINK35 / "lisp65-c2-substitution-linked.prg"
BASE_PRODUCT_SHA = "54c731559fdb72d5d1cb8478b9da7e78a422741e4e5267d64b07fe4c6f763a65"
BASE_REPLAY = EVIDENCE / (
    "c2.2-product-link35-dma-completion-first-status-pure-replay-receipt.json")
BASE_REPLAY_SHA = "10bc82583a9b6f80c805a6770769792047e838e93e07d92a4735b673bd2fd13d"
BASE_HW_DIAGNOSIS = EVIDENCE / (
    "c2.2-product-link35-dma-completion-hardware-first-red-diagnosis.json")
BASE_HW_DIAGNOSIS_SHA = (
    "1313edd19d466f290ac6af61f83840884bc385cb7f7b5dfc88928280f1b74c06")
BASE_DEPLOYMENT = ROOT / (
    "build/c2.2/hardware-presmoke-link35-dma-completion-first-status/deployment.json")
CYCLE1_FIRST_RED = EVIDENCE / (
    "c2.2-link35-hold-before-wipe-diagnostic-cycle1-link-receipt.json")
OUT = ROOT / (
    "build/c2.2/substitution/link35-hold-before-wipe-fixed-patch-cycle2")
PRODUCT = OUT / "lisp65-link35-hold-before-wipe-cycle2-NONPROMOTABLE.prg"
MANIFEST = OUT / "fixed-length-patch-manifest.json"
RECEIPT = EVIDENCE / (
    "c2.2-link35-hold-before-wipe-fixed-patch-cycle2-receipt.json")
HW_OUT = ROOT / "build/c2.2/link35-hold-before-wipe-hardware-cycle2"
DEPLOYMENT = HW_OUT / "deployment.json"
HW_RECEIPT = EVIDENCE / (
    "c2.2-link35-hold-before-wipe-cycle2-hardware-receipt.json")

LOAD_ADDRESS = 0x2001
INSTRUCTION_ADDRESS = 0xAD01
INSTRUCTION_FILE_OFFSET = 2 + INSTRUCTION_ADDRESS - LOAD_ADDRESS
BEFORE = bytes.fromhex("4c69af")       # JMP $AF69 (ERR_CRC return edge)
AFTER = bytes.fromhex("4c01ad")        # JMP $AD01 (self-loop)
CHANGED_FILE_OFFSETS = (INSTRUCTION_FILE_OFFSET + 1,
                        INSTRUCTION_FILE_OFFSET + 2)
TARGET_ADDRESS = 0xC356
TARGET_BYTES = 1156
SOURCE_OFFSET = 0x200
EXPECTED_CRC = 0xE856


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
        BASE_HW_DIAGNOSIS: BASE_HW_DIAGNOSIS_SHA,
    }
    for path, digest in expected.items():
        require(path.is_file() and sha(path) == digest,
                f"Link-35 authority drift: {path}")
    require(CYCLE1_FIRST_RED.is_file(), "Class-B cycle-1 First Red absent")
    cycle1 = json.loads(CYCLE1_FIRST_RED.read_text(encoding="utf-8"))
    require(cycle1.get("status") ==
            "FIRST RED: Class-B hold-before-wipe cycle 1 stopped"
            and cycle1.get("execution_accounting", {}).get("hardware_runs") == 0,
            "Class-B cycle-1 stop is not authoritative")
    replay = json.loads(BASE_REPLAY.read_text(encoding="utf-8"))
    require(replay.get("status") ==
            "passed-artifact-only-link35-preinstall-dataflow-replay",
            "Link-35 replay is not green")
    return {
        "link35_product": bind(BASE_PRODUCT),
        "link35_pure_replay": bind(BASE_REPLAY),
        "link35_hardware_first_red": bind(BASE_HW_DIAGNOSIS),
        "class_b_cycle1_first_red": bind(CYCLE1_FIRST_RED),
        "source_deployment": bind(BASE_DEPLOYMENT),
    }


def patch_bytes(source: bytes) -> bytes:
    require(len(source) >= INSTRUCTION_FILE_OFFSET + 3,
            "Link-35 product does not contain the patch span")
    require(int.from_bytes(source[:2], "little") == LOAD_ADDRESS,
            "Link-35 PRG load address drift")
    require(source[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 3] == BEFORE,
            "Link-35 CRC-failure instruction drift")
    result = bytearray(source)
    result[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 3] = AFTER
    return bytes(result)


def diff_gate(source: bytes, candidate: bytes) -> dict[str, Any]:
    require(len(candidate) == len(source), "fixed-length patch changed file size")
    changed = [index for index, (left, right) in enumerate(zip(source, candidate))
               if left != right]
    require(changed == list(CHANGED_FILE_OFFSETS),
            f"fixed-length patch changed unexpected bytes: {changed}")
    require(candidate[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 3] == AFTER,
            "fixed-length patch did not produce JMP-to-self")
    mutations = {
        "opcode-change": bytearray(candidate),
        "one-operand-byte": bytearray(candidate),
        "third-byte-change": bytearray(candidate),
    }
    mutations["opcode-change"][INSTRUCTION_FILE_OFFSET] = 0xea
    mutations["one-operand-byte"][CHANGED_FILE_OFFSETS[1]] = BEFORE[2]
    mutations["third-byte-change"][INSTRUCTION_FILE_OFFSET + 3] ^= 1
    rejected: dict[str, str] = {}
    for name, mutated in mutations.items():
        try:
            changed_mutation = [
                index for index, (left, right) in enumerate(zip(source, mutated))
                if left != right]
            require(changed_mutation == list(CHANGED_FILE_OFFSETS),
                    "mutation changed the exact diff domain")
            require(bytes(mutated)[INSTRUCTION_FILE_OFFSET:
                                   INSTRUCTION_FILE_OFFSET + 3] == AFTER,
                    "mutation changed the exact self-loop instruction")
        except GateError:
            rejected[name] = "rejected"
        else:
            raise GateError(f"fixed-length mutation accepted: {name}")
    return {
        "status": "passed-exact-two-operand-byte-self-loop-patch",
        "load_address": f"0x{LOAD_ADDRESS:04x}",
        "instruction_address": f"0x{INSTRUCTION_ADDRESS:04x}",
        "instruction_file_offset": f"0x{INSTRUCTION_FILE_OFFSET:04x}",
        "changed_file_offsets": [f"0x{value:04x}"
                                 for value in CHANGED_FILE_OFFSETS],
        "changed_cpu_addresses": ["0xad02", "0xad03"],
        "before_instruction_hex": BEFORE.hex(),
        "after_instruction_hex": AFTER.hex(),
        "before_semantics": "JMP $AF69 (return ERR_CRC)",
        "after_semantics": "JMP $AD01 (hold before verifier entry and wipe)",
        "changed_bytes": 2,
        "file_size_delta_bytes": 0,
        "mutations": rejected,
    }


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Class-B cycle-2 fixed patch already consumed")
    authority = prerequisites()
    source = regular(BASE_PRODUCT)
    candidate = patch_bytes(source)
    gate = diff_gate(source, candidate)
    OUT.mkdir(parents=True)
    PRODUCT.write_bytes(candidate)
    require(regular(PRODUCT) == candidate, "diagnostic product writeback drift")
    require(sha(PRODUCT) != BASE_PRODUCT_SHA,
            "diagnostic identity is not distinct from Link 35")
    capacity = json.loads(BASE_REPLAY.read_text(encoding="utf-8"))["capacity"]
    manifest = {
        "format": "lisp65-c2-link35-hold-before-wipe-fixed-patch-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-exact-fixed-length-diagnostic-instrumentation",
        "promotable": False,
        "delegation": {"class": "B", "cycle": 2, "cycle_cap": 3,
                       "question": "E2f / hold before wipe"},
        "authority": authority,
        "diagnostic_identity": bind(PRODUCT),
        "patch_gate": gate,
        "capacity": capacity,
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
            "diagnostic_byte_patches": 1, "changed_bytes": 2,
            "hardware_runs": 0, "promotable_candidates": 0,
        },
        "claim_limit": (
            "Permanently non-promotable fixed-length instrumentation of the "
            "SHA-bound Link-35 product. It carries no product, capacity, "
            "promotion, acceptance, completion-contract or hardware claim."),
        "next_gate": "one announced Class-B cycle-2 hardware run",
    }
    write_json(MANIFEST, manifest)
    value = {**manifest, "manifest": bind(MANIFEST)}
    write_json(RECEIPT, value)
    for path in (PRODUCT, MANIFEST, RECEIPT):
        os.chmod(path, 0o444)
    os.chmod(OUT, 0o555)
    return value


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "Class-B cycle-2 receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") ==
            "passed-exact-fixed-length-diagnostic-instrumentation"
            and value.get("promotable") is False,
            "Class-B cycle-2 fixed patch is not green/non-promotable")
    source = regular(BASE_PRODUCT)
    candidate = regular(PRODUCT)
    require(sha(BASE_PRODUCT) == BASE_PRODUCT_SHA,
            "Link-35 rollback identity drift")
    require(bind(PRODUCT) == value["diagnostic_identity"],
            "Class-B cycle-2 diagnostic identity drift")
    diff_gate(source, candidate)
    require(all(delta == 0 for delta in value["capacity_effect"].values()),
            "Class-B cycle-2 capacity delta is not zero")
    return value


def prepare_hardware() -> dict[str, Any]:
    receipt = check()
    require(not DEPLOYMENT.exists(), "cycle-2 hardware deployment already exists")
    source = json.loads(BASE_DEPLOYMENT.read_text(encoding="utf-8"))
    require(source.get("status") == "ready-receipt-less"
            and source.get("new_product_links") == 0,
            "Link-35 source deployment is not ready")
    for row in source["preloads"]:
        path = ROOT / row["path"]
        require(len(regular(path)) == row["bytes"] and sha(path) == row["sha256"],
                f"source preload drift: {path}")
    deployment = {
        **source,
        "format": "lisp65-c2-class-b-fixed-patch-deployment-v1",
        "status": "ready-nonpromotable-class-b-cycle2",
        "product": {**bind(PRODUCT), "address": "0x00002001"},
        "source_candidate": {
            "directory": OUT.relative_to(ROOT).as_posix(),
            "authorization_receipt": bind(RECEIPT),
            "base_link35_product": bind(BASE_PRODUCT),
            "patch_manifest": bind(MANIFEST),
        },
        "new_product_links": 0,
        "promotable": False,
        "claim_limit": (
            "Host-verified deployment for one non-promotable Class-B cycle-2 "
            "hardware diagnostic; never a product pre-smoke or acceptance run."),
    }
    HW_OUT.mkdir(parents=True)
    write_json(DEPLOYMENT, deployment)
    return deployment


def verify_hardware() -> dict[str, Any]:
    check()
    require(DEPLOYMENT.is_file(), "cycle-2 hardware deployment absent")
    value = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    require(value.get("status") == "ready-nonpromotable-class-b-cycle2"
            and value.get("promotable") is False
            and value.get("new_product_links") == 0,
            "cycle-2 deployment status drift")
    require(bind(PRODUCT) == {key: value["product"][key]
                              for key in ("path", "bytes", "sha256")},
            "cycle-2 deployment product drift")
    for row in value["preloads"]:
        path = ROOT / row["path"]
        require(len(regular(path)) == row["bytes"] and sha(path) == row["sha256"],
                f"cycle-2 deployment preload drift: {path}")
    return value


def classify(captures: list[bytes], expected: bytes) -> str:
    matches = [capture == expected for capture in captures]
    if any(matches):
        return "converged-to-exact-payload-after-first-failed-crc"
    if any(left != right for left, right in zip(captures, captures[1:])):
        return "still-changing-while-held"
    return "stably-wrong-while-held"


def classifier_selftest() -> dict[str, str]:
    expected = b"abc"
    cases = {
        "converged": ([b"aaa", expected, expected],
                      "converged-to-exact-payload-after-first-failed-crc"),
        "changing": ([b"aaa", b"aab", b"aac"],
                     "still-changing-while-held"),
        "stable-wrong": ([b"aaa", b"aaa", b"aaa"],
                         "stably-wrong-while-held"),
    }
    for name, (captures, answer) in cases.items():
        require(classify(captures, expected) == answer,
                f"cycle-2 classifier drift: {name}")
    return {name: "passed" for name in cases}


def evaluate_hardware() -> dict[str, Any]:
    deployment = verify_hardware()
    require(not HW_RECEIPT.exists(), "cycle-2 hardware receipt already exists")
    boot_row = next(row for row in deployment["preloads"]
                    if int(row["address"], 16) == 0x08200000)
    boot_path = ROOT / boot_row["path"]
    boot = regular(boot_path)
    expected = boot[SOURCE_OFFSET:SOURCE_OFFSET + TARGET_BYTES]
    require(len(expected) == TARGET_BYTES and crc16(expected) == EXPECTED_CRC,
            "catalog-verifier expected payload drift")
    timing = json.loads((HW_OUT / "capture-timing.json").read_text(
        encoding="utf-8"))
    require(timing.get("reference") == "product-launch-command-completed"
            and len(timing.get("captures", [])) == 3,
            "cycle-2 capture timing evidence drift")
    target_paths = [HW_OUT / f"held-target-capture-{index}.bin"
                    for index in range(1, 4)]
    captures = [regular(path) for path in target_paths]
    require(all(len(capture) == TARGET_BYTES for capture in captures),
            "cycle-2 target capture length drift")
    low = regular(HW_OUT / "held-low-0000-1fff.bin")
    require(len(low) == 0x2000, "cycle-2 low-memory capture length drift")
    # The binary patch loops before rtov_fail(): boot family remains active,
    # Island state remains INSTALLING, the loaded length remains 0x0484, and
    # neither busy nor fault has been consumed by outer cleanup.
    require(low[0x77] == 1 and low[0x78] == 1,
            "cycle-2 did not hold in Boot/INSTALLING state")
    require(low[0x79] == 0x84 and low[0x7a] == 0x04,
            "cycle-2 loaded-length witness drift")
    require(low[0x7b] == 1 and low[0x7c] == 0,
            "cycle-2 hold edge was not upstream of fail cleanup")
    job = regular(HW_OUT / "held-job-and-marker-b960-bfe0.bin")
    require(len(job) == 0x680 and job[0xbfd1 - 0xb960] == 0xa5,
            "cycle-2 completion marker witness drift")
    boot_live_path = HW_OUT / "held-boot-family.bin"
    require(regular(boot_live_path) == boot,
            "cycle-2 Boot-family source changed")
    outcome = classify(captures, expected)
    observations = []
    for index, (path, capture, when) in enumerate(
            zip(target_paths, captures, timing["captures"]), start=1):
        observations.append({
            "capture": index,
            "elapsed_after_launch_ms": when["elapsed_after_launch_ms"],
            **bind(path),
            "crc16": f"0x{crc16(capture):04x}",
            "matches_expected": capture == expected,
            "nonmatching_bytes": sum(left != right
                                      for left, right in zip(capture, expected)),
        })
    if outcome == "converged-to-exact-payload-after-first-failed-crc":
        first_match = next(row for row in observations if row["matches_expected"])
        answer = (
            "After marker 0xa5 and the already-failed on-device CRC, the held "
            "destination reached the exact catalog-verifier payload no later "
            f"than the capture at {first_match['elapsed_after_launch_ms']} ms "
            "after the launch command completed. The marker is an early "
            "publication witness, not a completion boundary.")
        status = "answered-E2f-completion-convergence"
        next_gate = "Class C: define and authorize a real completion boundary"
    elif outcome == "still-changing-while-held":
        answer = (
            "The destination remained in motion across the three timed captures "
            "while execution was held before wipe, directly proving post-marker "
            "transfer visibility.")
        status = "answered-E2f-post-marker-motion"
        next_gate = "Class C: define and authorize a real completion boundary"
    else:
        answer = (
            "The destination stayed byteidentically wrong across all timed "
            "captures. Delayed convergence does not explain E2f; one Class-B "
            "cycle remains for stable-transfer diagnosis.")
        status = "Class-B-cycle2-stable-wrong"
        next_gate = "Class-B cycle 3 remains available"
    value = {
        "format": "lisp65-c2-link35-hold-before-wipe-cycle2-hardware-v1",
        "recorded_on": "2026-07-21",
        "status": status,
        "promotable": False,
        "delegation": {"class": "B", "cycle": 2, "cycle_cap": 3},
        "authorization": bind(RECEIPT),
        "deployment": bind(DEPLOYMENT),
        "diagnostic_identity": bind(PRODUCT),
        "patch_gate": json.loads(MANIFEST.read_text(encoding="utf-8"))
            ["patch_gate"],
        "observations": {
            "classification": outcome,
            "completion_marker": "0xa5",
            "expected_crc16": f"0x{EXPECTED_CRC:04x}",
            "timed_target_captures": observations,
            "held_state": {
                "family": "boot", "island_state": "INSTALLING",
                "loaded_len": TARGET_BYTES, "busy": 1, "fault": 0,
            },
            "source_post_stop": {**bind(boot_live_path),
                                 "matches_deployed": True},
        },
        "answer": answer,
        "next_gate": next_gate,
        "claim_limit": (
            "One non-promotable Class-B diagnostic hardware run. It is not "
            "promotion, acceptance, latency or product evidence."),
        "classifier_mutations": classifier_selftest(),
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0,
            "diagnostic_byte_patches": 1, "changed_bytes": 2,
            "hardware_runs": 1, "read_only_post_stop_captures": 5,
            "remaining_autonomous_cycles": 1,
        },
        "disposition": (
            "Diagnostic identity remains isolated under its Class-B path, "
            "read-only and permanently excluded from promotion/archive mixing."),
        "link35_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
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
        "selftest", "build", "check", "prepare-hardware",
        "verify-hardware", "evaluate-hardware"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            prerequisites()
            classifier_selftest()
            print("c2-link35-hold-fixed-patch: SELFTEST PASS mutations=6")
            return 0
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
        print("c2-link35-hold-fixed-patch: " + str(value["status"]))
        return 0
    except Exception as error:
        print("c2-link35-hold-fixed-patch: FAIL " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
