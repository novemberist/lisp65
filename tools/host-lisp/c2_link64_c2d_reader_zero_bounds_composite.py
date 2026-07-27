#!/usr/bin/env python3
"""Build cycle 3's composite reader-zero/bounds discriminator."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link64_slot39_reader_return_hold as B  # noqa: E402
import c2_link64_slot39_threshold_hold as H  # noqa: E402
import c2_link64_c2d_reader_bounds_hold as D  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
NOHIT1 = EVIDENCE / (
    "c2.2-link64-c2d-reader-bounds-nohit-hardware-receipt.json")
NOHIT2 = EVIDENCE / (
    "c2.2-link64-c2d-reader-bounds-nohit-cycle2-hardware-receipt.json")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link64-reader-zero-bounds-composite-NONPROMOTABLE")
CARRIER = OUT / "runtime-overlays-session-reader-zero-bounds.bin"
MANIFEST = OUT / "manifest.json"
RECEIPT = EVIDENCE / (
    "c2.2-link64-reader-zero-bounds-composite-nonpromotable-receipt.json")
HW_OUT = ROOT / (
    "build/c2.2/hardware-link64-reader-zero-bounds-composite-"
    "NONPROMOTABLE")
DEPLOYMENT = HW_OUT / "deployment.json"
HARDWARE_DRIVER = ROOT / (
    "scripts/c2-link64-reader-zero-bounds-composite-hw.sh")

ZERO_JMP_OPERAND_VMA = 0xC82F
ZERO_JMP_FILE_OFFSET = B.SLOT_FILE_OFFSET + (
    ZERO_JMP_OPERAND_VMA - B.SLOT_VMA)
ZERO_BEFORE = bytes.fromhex("f0c8")
ZERO_AFTER = bytes.fromhex("2ec8")


class CompositeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CompositeError(message)


def data(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink(),
            f"authority absent or not regular: {path}")
    return path.read_bytes()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    value = data(path)
    row: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(value),
        "sha256": sha_bytes(value),
    }
    if address is not None:
        row["address"] = f"0x{address:08x}"
    return row


def load(path: Path) -> dict[str, Any]:
    value = json.loads(data(path))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(data(path) == value, f"generated artifact differs: {path}")
        return
    path.write_bytes(value)
    path.chmod(0o444)


def write_json(path: Path, value: dict[str, Any]) -> None:
    write(
        path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def configure_builder() -> None:
    # Reuse the already mutation-proven v4 rebinder with the zero-exit JMP
    # operand as its sole executable edit.
    B.OUT = OUT
    B.CARRIER = CARRIER
    B.HOLD_VMA = ZERO_JMP_OPERAND_VMA
    B.PATCH_FILE_OFFSET = ZERO_JMP_FILE_OFFSET
    B.PATCH_IN_SLOT = ZERO_JMP_OPERAND_VMA - B.SLOT_VMA
    B.BEFORE = ZERO_BEFORE
    B.AFTER = ZERO_AFTER


def feasibility() -> dict[str, Any]:
    truth = ElfTruth.read(
        B.DONOR_ELF, llvm_readobj=H.LENGTH.READOBJ,
        include_section_data=True)
    poll = truth.symbol("c2_completion_poll")
    section = truth.section(poll.section)
    body = truth.section_bytes(poll.section)[
        poll.value - section.address:
        poll.value - section.address + poll.bytes]
    index = 0xC828 - poll.value
    require(
        poll.value == 0xC706 and poll.bytes == 563
        and body[index:index + 9]
            == bytes.fromhex("2091e6aad0034cf0c8")
        and data(H.BASE_CARRIER)[
            ZERO_JMP_FILE_OFFSET:ZERO_JMP_FILE_OFFSET + 2] == ZERO_BEFORE,
        "reader-zero exit geometry drift")
    return {
        "poll_symbol": poll.name,
        "reader_call": "JSR $e691 at $c828",
        "return_test": "TAX; BNE $c831 at $c82b/$c82c",
        "zero_exit_before": "JMP $c8f0",
        "zero_exit_after": "JMP $c82e (self-loop)",
        "executable_operand_bytes_changed": 1,
        "outcomes": {
            "inner_reader_hold": (
                "a bounds reject fired; entry length remains in $06/$07"),
            "caller_zero_hold": (
                "reader returned zero without a held bounds edge; "
                "post-facade length remains in $05/$06"),
            "bad_bytecode": (
                "reader returned nonzero and the later poll path failed"),
        },
    }


def build() -> tuple[bytes, dict[str, Any], bytes]:
    configure_builder()
    source = data(H.BASE_CARRIER)
    tail, candidate = B.solve(source)
    gate = B.validate(source, candidate)
    require(
        gate["instruction_file_offset"] == ZERO_JMP_FILE_OFFSET
        and gate["before_hex"] == ZERO_BEFORE.hex()
        and gate["after_hex"] == ZERO_AFTER.hex()
        and candidate[ZERO_JMP_FILE_OFFSET:ZERO_JMP_FILE_OFFSET + 2]
            == ZERO_AFTER,
        "composite zero-exit rebinding drift")
    return candidate, gate, tail


def prepare() -> dict[str, Any]:
    D.verify()
    source, base_deployment = H.validate_authority()
    require(source == data(H.BASE_CARRIER), "base carrier drift")
    nohit1 = load(NOHIT1)
    nohit2 = load(NOHIT2)
    require(
        nohit1["answer"]["runtime_bounds_rejection_observed"] is False
        and nohit2["answer"]["runtime_bounds_rejection_observed"] is False
        and nohit2["answer"]["consecutive_nohit_episodes"] == 2,
        "composite prior no-hit authority drift")
    shape = feasibility()
    candidate, gate, tail = build()
    write(CARRIER, candidate)
    write_json(MANIFEST, {
        "format":
            "lisp65-Link64-reader-zero-bounds-composite-manifest-v1",
        "status": "ready-nonpromotable-cycle-3",
        "promotable": False,
        "source": bind(H.BASE_CARRIER, 0x08000000),
        "candidate": bind(CARRIER, 0x08000000),
        "carrier_zero_exit_patch": gate,
        "live_bounds_patches": bind(D.MANIFEST),
        "solved_post_RTS_tail": {
            "hex": tail.hex(),
            "bytes_little_endian": list(tail),
        },
    })
    write_json(RECEIPT, {
        "format":
            "lisp65-c2.2-Link64-reader-zero-bounds-composite-"
            "nonpromotable-v1",
        "recorded_on": "2026-07-26",
        "status": "ready-authorized-nonpromotable-cycle-3",
        "promotable": False,
        "authority": {
            "cycle_1_nohit": bind(NOHIT1),
            "cycle_2_nohit": bind(NOHIT2),
            "source_carrier": bind(H.BASE_CARRIER, 0x08000000),
            "source_deployment": bind(H.BASE_DEPLOYMENT),
            "donor_ELF": bind(B.DONOR_ELF),
            "bounds_attribution": bind(D.RECEIPT),
            "driver": bind(Path(__file__)),
            "hardware_driver": bind(HARDWARE_DRIVER),
        },
        "ELF_feasibility": shape,
        "candidate": {
            "carrier": bind(CARRIER, 0x08000000),
            "manifest": bind(MANIFEST),
            "identity_separate_from_Link64": True,
            "lifecycle": "discard after the cycle-3 outcome",
        },
        "carrier_patch_and_rebinding": gate,
        "live_reader_bounds_patches": load(D.MANIFEST)[
            "live_patch_bytes"],
        "construction": {
            "product_bytes_changed": 0,
            "compiler_runs": 0,
            "linker_runs": 0,
            "hardware_runs": 0,
            "all_capacity_deltas": 0,
        },
        "claim_limit": (
            "Third and final nonpromotable cycle of the commissioned "
            "reader-return question. C1 remains OPEN."),
    })

    preloads: list[dict[str, Any]] = []
    replaced = 0
    for row in base_deployment["preloads"]:
        copy = dict(row)
        if copy["sha256"] == H.sha(H.BASE_CARRIER):
            copy = bind(CARRIER, int(copy["address"], 16))
            replaced += 1
        preloads.append(copy)
    require(replaced == 1, "composite deployment carrier not unique")
    write_json(DEPLOYMENT, {
        "format":
            "lisp65-c2.2-Link64-reader-zero-bounds-composite-hardware-v1",
        "recorded_on": "2026-07-26",
        "status": "ready-authorized-nonpromotable-cycle-3",
        "promotable": False,
        "diagnostic_cycle": 3,
        "authority": {
            "composite_receipt": bind(RECEIPT),
            "manifest": bind(MANIFEST),
            "source_deployment": bind(H.BASE_DEPLOYMENT),
        },
        "product": base_deployment["product"],
        "preloads": preloads,
        "live_bounds_patch": load(D.DEPLOYMENT)["live_patch"],
        "test": {
            "form": "(defun %c1e () (quote t))",
            "capture_intervals_seconds": [0, 1, 5],
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs_before_this_cycle": 2,
            "latency_attempts_consumed": 0,
        },
        "claim_limit": (
            "Final autonomous diagnostic cycle; product Link 64 remains "
            "unmodified and C1 OPEN."),
    })
    return {
        "status": "ready",
        "diagnostic_cycle": 3,
        "carrier_sha256": sha_bytes(candidate),
        "family_crc16": gate["family_crc16"],
        "live_bounds_patch_bytes": len(D.PATCHES),
        "carrier_executable_patch_bytes": 1,
        "capacity_delta": 0,
    }


def verify() -> dict[str, Any]:
    D.verify()
    deployment = load(DEPLOYMENT)
    receipt = load(RECEIPT)
    candidate, gate, _tail = build()
    require(
        deployment["status"]
            == "ready-authorized-nonpromotable-cycle-3"
        and receipt["carrier_patch_and_rebinding"] == gate
        and data(CARRIER) == candidate
        and deployment["authority"]["composite_receipt"]["sha256"]
            == sha_bytes(data(RECEIPT)),
        "composite deployment binding drift")
    for row in deployment["preloads"]:
        path = ROOT / row["path"]
        require(
            len(data(path)) == row["bytes"]
            and sha_bytes(data(path)) == row["sha256"],
            f"composite preload drift: {path}")
    feasibility()
    return {
        "status": "verified",
        "diagnostic_cycle": 3,
        "carrier_sha256": sha_bytes(candidate),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", nargs="?", default="prepare",
        choices=("prepare", "verify"))
    action = parser.parse_args().action
    value = {"prepare": prepare, "verify": verify}[action]()
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CompositeError, B.ReaderHoldError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-link64-reader-zero-bounds: FIRST RED: " + str(error))
        raise SystemExit(2)
