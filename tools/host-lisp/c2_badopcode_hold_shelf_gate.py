#!/usr/bin/env python3
"""Qualify the zero-byte BADOPCODE hold recipe against a final product."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

from elf_truth import ElfTruth


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/c2-badopcode-hold-shelf-recipe.json"
BASE = ROOT / ("build/c2.2/substitution/"
               "product-link-50-c2-lite-v6-persistent-header")
BASE_PRODUCT = BASE / "lisp65-c2-substitution-linked.prg"
BASE_ELF = Path(str(BASE_PRODUCT) + ".elf")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
RECEIPT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                  "c2.2-link50-badopcode-hold-shelf-recipe-receipt.json")
BEFORE = bytes.fromhex("8617")
AFTER = bytes.fromhex("80fe")


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def _exact_patch_gate(source: bytes, candidate: bytes,
                      offset: int) -> dict[str, str]:
    require(len(source) == len(candidate), "patch changed file size")
    changed = [i for i, pair in enumerate(zip(source, candidate))
               if pair[0] != pair[1]]
    require(changed == [offset, offset + 1], "patch diff domain drift")
    require(candidate[offset:offset + 2] == AFTER, "self-loop bytes drift")
    return {"status": "passed-exact-two-byte-self-loop",
            "changed_file_offsets": [hex(offset), hex(offset + 1)]}


def qualify(product: Path, elf: Path,
            llvm_readobj: Path = READOBJ,
            *, mutations: bool = True) -> dict[str, Any]:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    require(cfg["schema"] == "lisp65.c2.badopcode-hold-shelf-recipe.v1"
            and cfg["patch"]["before_hex"] == BEFORE.hex()
            and cfg["patch"]["after_hex"] == AFTER.hex(),
            "hold shelf contract drift")
    data = product.read_bytes()
    require(len(data) >= 4, "product too short")
    load = int.from_bytes(data[:2], "little")
    truth = ElfTruth.read(elf, llvm_readobj=llvm_readobj)
    fn = truth.symbol("vm_check_status")
    status_symbol = truth.symbol("vm_status")
    require(fn.symbol_type == "Function" and fn.bytes > 0,
            "vm_check_status is not a sized function")
    start = 2 + fn.value - load
    end = start + fn.bytes
    require(2 <= start < end <= len(data), "vm_check_status outside PRG")
    body = data[start:end]
    candidates = []
    for at in range(6, len(body) - 1):
        if (body[at:at + 2] == BEFORE
                and body[at - 6:at - 2] ==
                    bytes((0xa5, status_symbol.value & 0xff, 0xc9, 0x02))
                and body[at - 2] == 0x90):
            candidates.append(at)
    require(len(candidates) == 1,
            f"hold edge is not unique in actual final function: {candidates}")
    rel = candidates[0]
    offset = start + rel
    address = fn.value + rel
    candidate = bytearray(data)
    candidate[offset:offset + 2] = AFTER
    _exact_patch_gate(data, bytes(candidate), offset)

    rejected: dict[str, str] = {}
    if mutations:
        trials: dict[str, bytearray] = {}
        trials["wrong-opcode"] = bytearray(candidate)
        trials["wrong-opcode"][offset] = 0xea
        trials["wrong-relative-target"] = bytearray(candidate)
        trials["wrong-relative-target"][offset + 1] = 0xfc
        trials["only-opcode-changed"] = bytearray(candidate)
        trials["only-opcode-changed"][offset + 1] = BEFORE[1]
        trials["only-operand-changed"] = bytearray(candidate)
        trials["only-operand-changed"][offset] = BEFORE[0]
        trials["extra-neighbour-byte"] = bytearray(candidate)
        trials["extra-neighbour-byte"][offset + 2] ^= 1
        for name, trial in trials.items():
            try:
                _exact_patch_gate(data, bytes(trial), offset)
            except GateError:
                rejected[name] = "rejected"
            else:
                raise GateError(f"hold recipe mutation accepted: {name}")
    symbols = {}
    for name in ("vm_status", "vm_codebuf", "vm_buf_off", "vm_buf_bank",
                 "vmr_hdrlen", "vmr_littab", "vmr_code", "vmr_poff",
                 "vmr_plen", "vmr_pwmax", "vmr_win", "vmr_winlen",
                 "vmr_streaming"):
        row = truth.symbol(name)
        symbols[name] = {"address": hex(row.value), "bytes": row.bytes}
    return {
        "status": "passed-prequalified-BADOPCODE-hold-shelf-recipe",
        "product": {"path": product.relative_to(ROOT).as_posix(),
                    "bytes": len(data), "sha256": sha(product)},
        "elf": {"path": elf.relative_to(ROOT).as_posix(),
                "bytes": elf.stat().st_size, "sha256": sha(elf)},
        "patch": {
            "function": "vm_check_status",
            "function_interval": f"0x{fn.value:04x}..0x{fn.value + fn.bytes - 1:04x}",
            "instruction_address": f"0x{address:04x}",
            "instruction_file_offset": f"0x{offset:04x}",
            "before_hex": BEFORE.hex(), "after_hex": AFTER.hex(),
            "changed_bytes": 2, "file_size_delta_bytes": 0,
        },
        "capture_symbols": symbols,
        "capture_banks": ["0x00000000..0x0000ffff (three timed reads)",
                          "0x00020000..0x0002ffff",
                          "0x00050000..0x0005ffff"],
        "capacity_delta_bytes": 0,
        "promotable": False,
        "mutations_rejected": rejected,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", type=Path, default=BASE_PRODUCT)
    parser.add_argument("--elf", type=Path, default=BASE_ELF)
    parser.add_argument("--llvm-readobj", type=Path, default=READOBJ)
    parser.add_argument("--write-receipt", action="store_true")
    args = parser.parse_args()
    try:
        value = qualify(args.product, args.elf, args.llvm_readobj)
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        if args.product.resolve() == BASE_PRODUCT.resolve():
            require(value["product"]["sha256"] ==
                        cfg["authority"]["product_sha256"]
                    and value["elf"]["sha256"] ==
                        cfg["authority"]["elf_sha256"]
                    and value["patch"]["instruction_address"] ==
                        cfg["patch"]["template_instruction_address"]
                    and value["patch"]["instruction_file_offset"] ==
                        cfg["patch"]["template_file_offset"],
                    "Link-50 shelf template authority drift")
        if args.write_receipt:
            require(not RECEIPT.exists(), "shelf receipt already exists")
            value = {
                "format": "lisp65-c2-badopcode-hold-shelf-recipe-receipt-v1",
                "recorded_on": "2026-07-22",
                "status": value["status"],
                "promotable": False,
                "authority": {"contract": bind(CONFIG),
                              "gate": bind(Path(__file__))},
                "qualification": value,
                "execution_accounting": {
                    "compiler_runs": 0, "linker_runs": 0,
                    "product_bytes_changed": 0, "hardware_runs": 0},
                "next_use": "instantiate only after a future BADOPCODE recurrence"
            }
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
            os.chmod(RECEIPT, 0o444)
    except (GateError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-badopcode-hold-shelf: FAIL: {error}", file=sys.stderr)
        return 1
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
