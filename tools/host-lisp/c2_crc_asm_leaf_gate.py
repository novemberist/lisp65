#!/usr/bin/env python3
"""Execute the linked MOS CRC leaf over reference vectors.

This deliberately consumes the final ELF disassembly.  The portable CRC is
the oracle; the tiny interpreter covers exactly the instructions admitted in
the hand-written leaf and therefore proves the bytes that WPLTO actually
placed, rather than a second transcription of the assembler source.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Sequence

import c2_crc_codegen_gate as CODEGEN
from elf_truth import ElfTruth, ElfTruthError


ROOT = Path(__file__).resolve().parents[2]
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
DIRECT = re.compile(r"^\$([0-9a-f]+)\b")
IMMEDIATE = re.compile(r"^#\$([0-9a-f]+)$")
INDIRECT_Z = re.compile(r"^\(\$([0-9a-f]+)\),z\b")
ALLOWED = {
    "asl", "bcc", "beq", "bne", "bra", "dec", "dey", "eor", "inw",
    "lda", "ldx", "ldy", "ldz", "ora", "rol", "rts", "sta", "stx",
    "sty",
}
VECTORS = {
    "empty": b"",
    "ccitt-check": b"123456789",
    "all-byte-values": bytes(range(256)),
    "length-high-byte-borrow": bytes((index * 73 + 19) & 0xff
                                     for index in range(1156)),
    "multi-page": bytes((index ^ (index >> 3) ^ 0xa5) & 0xff
                         for index in range(4097)),
}


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def crc_reference(data: bytes, *, polynomial: int = 0x1021) -> int:
    crc = 0xffff
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ polynomial) & 0xffff \
                if crc & 0x8000 else (crc << 1) & 0xffff
    return crc


def _number(pattern: re.Pattern[str], operand: str, kind: str) -> int:
    match = pattern.match(operand)
    if not match:
        raise GateError(f"unsupported {kind} operand: {operand}")
    return int(match.group(1), 16)


def execute(rows: list[dict[str, Any]], *, rc: dict[str, int],
            data: bytes) -> dict[str, int]:
    require(rows, "CRC leaf has no linked instructions")
    by_address = {int(row["address"]): row for row in rows}
    addresses = sorted(by_address)
    require(len(addresses) == len(rows), "duplicate CRC instruction address")
    next_address = {address: addresses[index + 1]
                    for index, address in enumerate(addresses[:-1])}
    memory = bytearray(65536)
    base = 0x4000
    require(base + len(data) <= len(memory), "CRC vector exceeds model memory")
    memory[base:base + len(data)] = data
    zp = bytearray(256)
    # Exercise the actual llvm-mos C ABI observed at the linked C->ASM
    # callsites: argument 0 (pointer) is in __rc2/__rc3 and the final
    # argument (length) is in A/X.
    a, x, y, z = len(data) & 0xff, (len(data) >> 8) & 0xff, 0, 0
    zp[rc["__rc2"]] = base & 0xff
    zp[rc["__rc3"]] = base >> 8
    carry = False
    zero = False
    pc = addresses[0]
    steps = 0
    limit = max(128, len(data) * 96 + 128)

    def nz(value: int) -> int:
        nonlocal zero
        value &= 0xff
        zero = value == 0
        return value

    while True:
        steps += 1
        require(steps <= limit, "CRC leaf did not terminate")
        require(pc in by_address, f"CRC control escaped leaf at 0x{pc:04x}")
        row = by_address[pc]
        opcode = str(row["opcode"])
        operand = str(row["operand"])
        require(opcode in ALLOWED, f"unsupported CRC opcode: {opcode}")
        following = next_address.get(pc)

        if opcode in ("lda", "ldx", "ldy", "ldz"):
            immediate = IMMEDIATE.match(operand)
            indirect = INDIRECT_Z.match(operand)
            if immediate:
                value = int(immediate.group(1), 16)
            elif indirect:
                pointer = int(indirect.group(1), 16)
                address = zp[pointer] | (zp[(pointer + 1) & 0xff] << 8)
                value = memory[(address + z) & 0xffff]
            else:
                value = zp[_number(DIRECT, operand, "direct")]
            value = nz(value)
            if opcode == "lda": a = value
            elif opcode == "ldx": x = value
            elif opcode == "ldy": y = value
            else: z = value
        elif opcode in ("sta", "stx", "sty"):
            target = _number(DIRECT, operand, "direct")
            zp[target] = a if opcode == "sta" else x if opcode == "stx" else y
        elif opcode in ("ora", "eor"):
            immediate = IMMEDIATE.match(operand)
            value = (int(immediate.group(1), 16) if immediate
                     else zp[_number(DIRECT, operand, "direct")])
            a = nz(a | value if opcode == "ora" else a ^ value)
        elif opcode == "dec":
            target = _number(DIRECT, operand, "direct")
            zp[target] = nz(zp[target] - 1)
        elif opcode == "dey":
            y = nz(y - 1)
        elif opcode in ("asl", "rol"):
            target = _number(DIRECT, operand, "direct")
            value = zp[target]
            old_carry = carry
            carry = bool(value & 0x80)
            zp[target] = nz((value << 1) | (old_carry if opcode == "rol" else 0))
        elif opcode == "inw":
            target = _number(DIRECT, operand, "direct")
            value = (zp[target] | (zp[(target + 1) & 0xff] << 8)) + 1
            zp[target] = value & 0xff
            zp[(target + 1) & 0xff] = (value >> 8) & 0xff
        elif opcode in ("beq", "bne", "bcc", "bra"):
            target = _number(DIRECT, operand, "branch")
            taken = (opcode == "bra" or opcode == "beq" and zero
                     or opcode == "bne" and not zero
                     or opcode == "bcc" and not carry)
            pc = target if taken else following
            require(pc is not None, "conditional branch fell beyond leaf")
            continue
        elif opcode == "rts":
            require(z == 0, "CRC leaf violated llvm-mos Z=0 return ABI")
            return {"crc": a | (x << 8), "steps": steps}
        require(following is not None, f"CRC leaf lacks RTS after 0x{pc:04x}")
        pc = following


def audit_elf(elf: Path, *, out: Path | None = None) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
    leaf = truth.symbol(CODEGEN.CRC)
    require(leaf.symbol_type == "Function" and leaf.bytes > 0
            and leaf.section == ".text",
            "CRC assembler leaf is not a named/sized .text function")
    rc = {name: truth.symbol(name).value for name in
          ("__rc2", "__rc3", "__rc4", "__rc5", "__rc6", "__rc7")}
    require(len(set(rc.values())) == len(rc)
            and all(0 <= value <= 0xff for value in rc.values()),
            f"CRC ABI ZP symbols are not distinct bytes: {rc}")
    completed = subprocess.run(
        [str(TOOLCHAIN / "llvm-objdump"), "-d", "--no-show-raw-insn",
         str(elf)], check=True, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    rows = [row for row in CODEGEN.disassembly_rows(completed.stdout)
            if row["section"] == leaf.section
            and leaf.value <= int(row["address"]) < leaf.value + leaf.bytes]
    results: dict[str, Any] = {}
    for name, data in VECTORS.items():
        actual = execute(rows, rc=rc, data=data)
        expected = crc_reference(data)
        require(actual["crc"] == expected,
                f"CRC parity failed for {name}: 0x{actual['crc']:04x} != "
                f"0x{expected:04x}")
        results[name] = {"bytes": len(data), "crc16": expected,
                         "executed_instructions": actual["steps"]}
    require(results["ccitt-check"]["crc16"] == 0x29b1,
            "portable CRC oracle failed canonical CCITT check")
    value = {
        "format": "lisp65-c2-crc-assembler-leaf-equivalence-v1",
        "elf": str(elf),
        "status": "passed-linked-assembler-leaf-crc-equivalence",
        "leaf": {"section": leaf.section, "address": leaf.value,
                 "bytes": leaf.bytes, "symbol_type": leaf.symbol_type},
        "abi_zero_page": rc,
        "vectors": results,
        "invariant": (
            "The executed final-ELF leaf equals CRC-16/CCITT-FALSE for every "
            "pinned vector when entered through the actual llvm-mos C ABI "
            "(pointer __rc2/__rc3, length A/X); WPLTO does not select its "
            "instructions."),
    }
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    return value


def selftest() -> dict[str, str]:
    require(crc_reference(b"123456789") == 0x29b1,
            "canonical CRC vector failed")
    mutations = {
        "wrong-polynomial": crc_reference(b"123456789", polynomial=0x1020),
        "wrong-init": crc_reference(b"123456789") ^ 0xffff,
    }
    for name, value in mutations.items():
        require(value != 0x29b1, f"CRC oracle mutation survived: {name}")
    CODEGEN.selftest()
    return {name: "rejected" for name in mutations} | {
        "linked-codegen-mutations": "delegated-to-central-gate"}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            print("c2-crc-asm-leaf-gate: SELFTEST PASS mutations="
                  + str(len(selftest())))
            return 0
        if args.elf is None:
            parser.error("--elf is required without --selftest")
        value = audit_elf(args.elf, out=args.out)
        print("c2-crc-asm-leaf-gate: " + value["status"])
        return 0
    except (GateError, CODEGEN.GateError, ElfTruthError, OSError,
            subprocess.CalledProcessError, ValueError) as error:
        print("c2-crc-asm-leaf-gate: FAIL: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
