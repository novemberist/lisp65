#!/usr/bin/env python3
"""Prove the strict L65R-v3 emissions-bound record CRC contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import runtime_overlay_bank as R  # noqa: E402


CONFIG = ROOT / "config/c2-l65r-v3-record-crc-contract.json"
DOCUMENT = ROOT / "docs/planning/c2.2-l65r-v3-record-crc-contract.md"
PACKER = ROOT / "tools/host-lisp/runtime_overlay_bank.py"
PRODUCT = ROOT / "src/vm_runtime_overlay.c"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v3-record-crc-contract-probe-receipt.json")


class ContractError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"required contract input absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def refresh_outer(data: bytearray) -> None:
    count = data[7]
    end = R.HEADER_SIZE + count * R.ENTRY_SIZE
    struct.pack_into("<H", data, 24,
                     R.crc16_ccitt_false(data[R.HEADER_SIZE:end]))
    struct.pack_into("<H", data, 26, 0)
    struct.pack_into("<H", data, 26,
                     R.crc16_ccitt_false(data[:R.HEADER_SIZE]))


def image_fixture(version: int) -> tuple[bytes, R.ParsedBank]:
    boot = R.SliceSpec(
        0, "boot", ".boot", "boot_start", "boot_end", "boot_entry",
        R.FLAG_BOOT, R.ENTRY_ABI, 0)
    data = R.SliceSpec(
        1, "island", ".island", "island_start", "island_end", "",
        R.FLAG_BOOT | R.FLAG_DATA_ONLY, 0, 0, "", True, 0x1800)
    slices = [
        R.ExtractedSlice(boot, 0xC356, 0xC35A, 0xC356, b"BOOT"),
        R.ExtractedSlice(data, 0x1800, 0x1804, R.DATA_ENTRY_SENTINEL,
                         b"ISLD"),
    ]
    return R.build_image(
        slices, profile_build_id=0x12345678, expected_vma=0xC356,
        max_slice_bytes=1792, format_version=version)


def rejection(candidate: bytes, label: str) -> str:
    try:
        R.validate_image(candidate, expected_build_id=0x12345678,
                         expected_vma=0xC356, max_slice_bytes=1792,
                         format_version=R.VERSION_V3)
    except R.OverlayBankError:
        return "rejected-fail-closed"
    raise ContractError(f"strict v3 validator accepted {label}")


def convergence(samples: list[tuple[int, bytes]], start: int,
                offset: int = 22) -> str:
    for frame, record in samples:
        expected = struct.unpack_from("<H", record, offset)[0]
        check = bytearray(record)
        check[offset:offset + 2] = b"\x00\x00"
        if expected and R.crc16_ccitt_false(check) == expected:
            return "complete"
        if ((frame - start) & 0xFFFF) >= 64:
            return "completion-timeout"
    return "pending"


def run() -> dict[str, Any]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    require(config["version"] == 3 and config["entry_bytes"] == 32,
            "machine-readable v3 geometry drift")
    require(config["record_crc16"]["offset"] == 22
            and config["record_crc16"]["zero"] == "format-error",
            "machine-readable record CRC rule drift")
    image, parsed = image_fixture(R.VERSION_V3)
    checked = R.validate_image(
        image, expected_build_id=0x12345678, expected_vma=0xC356,
        max_slice_bytes=1792, format_version=R.VERSION_V3)
    require(parsed == checked and all(item.record_crc16 for item in checked.slices),
            "canonical v3 image did not round-trip with nonzero record CRCs")

    wrong = bytearray(image)
    wrong[R.HEADER_SIZE + 22] ^= 1
    refresh_outer(wrong)
    zero = bytearray(image)
    zero[R.HEADER_SIZE + R.ENTRY_SIZE + 22:
         R.HEADER_SIZE + R.ENTRY_SIZE + 24] = b"\x00\x00"
    refresh_outer(zero)
    v2, _ = image_fixture(R.VERSION_V2)
    mutations = {
        "wrong-record-crc": rejection(bytes(wrong), "wrong record CRC"),
        "zero-record-crc": rejection(bytes(zero), "zero record CRC"),
        "v2-to-v3-decoder": rejection(v2, "v2 image"),
    }

    record = image[R.HEADER_SIZE:R.HEADER_SIZE + R.ENTRY_SIZE]
    torn = bytearray(record)
    torn[4] ^= 1
    require(convergence([(100, bytes(torn)), (164, bytes(torn))], 100) ==
            "completion-timeout", "record timeout model drift")
    mutations["record-convergence-timeout"] = "rejected-fail-closed"
    require(convergence([(0xFFFE, bytes(torn)), (0x001E, record)], 0xFFFE) ==
            "complete", "record convergence wrap model drift")

    packer = PACKER.read_text(encoding="utf-8")
    product = PRODUCT.read_text(encoding="utf-8")
    emitter_token = 'struct.pack_into("<H", record, 22, record_crc)'
    require(packer.count(emitter_token) == 1,
            "record CRC is absent or emitted at more than one site")
    require("if format_version == VERSION_V3:" in packer
            and "raw_record[22:24] = b\"\\x00\\x00\"" in packer,
            "packer lacks strict virtual-zero v3 validation")
    require(product.count("rtov_record_converge(record)") == 2,
            "both product record consumers are not convergence-gated")
    require("#error \"L65R-v3 record reads require CRC convergence\"" in product,
            "v3 product can compile without record convergence")
    mutations["second-record-crc-emitter"] = "rejected-by-single-site-gate"

    return {
        "format": "lisp65-l65r-v3-record-crc-contract-probe-receipt-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-strict-l65r-v3-record-crc-contract",
        "claim_limit": (
            "Host contract/emitter/decoder-source proof only; no WPLTO, "
            "product link, capacity claim or hardware execution."),
        "authority": {"config": bind(CONFIG), "document": bind(DOCUMENT),
                      "packer": bind(PACKER), "product_source": bind(PRODUCT)},
        "format_proof": {
            "version": 3, "entry_bytes": 32, "crc_offset": 22,
            "record_count": len(checked.slices),
            "record_crc16": [f"0x{x.record_crc16:04x}" for x in checked.slices],
            "round_trip": "byte-and-model-identical",
            "emitter_sites": 1,
            "product_record_consumers": 2,
        },
        "mutations": mutations,
        "execution_accounting": {"compiler_runs": 0,
                                 "whole_program_lto_runs": 0,
                                 "product_closure_links": 0,
                                 "hardware_runs": 0},
        "next_gate": "product-shaped WPLTO capacity/placement probe",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.parse_args()
    value = run()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    print(value["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
