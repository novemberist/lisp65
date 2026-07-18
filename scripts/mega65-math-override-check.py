#!/usr/bin/env python3
"""Static ABI/link proof for src/mega65_math.s.

The math unit cannot be executed on the host.  This gate combines a host-side
semantic oracle with target assembly inspection and three real llvm-mos links:
baseline, strong unsigned overrides, and overrides plus signed libcrt wrappers.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import random
import re
import shutil
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
LLVM_MOS_ROOT = pathlib.Path(
    os.environ.get("LLVM_MOS_ROOT", ROOT / "tools/llvm-mos")
).resolve()
DEFAULT_CC = LLVM_MOS_ROOT / "bin/mos-mega65-clang"
DEFAULT_NM = LLVM_MOS_ROOT / "bin/llvm-nm"
DEFAULT_OBJDUMP = LLVM_MOS_ROOT / "bin/llvm-objdump"
DEFAULT_SIZE = LLVM_MOS_ROOT / "bin/llvm-size"
DEFAULT_AR = LLVM_MOS_ROOT / "bin/llvm-ar"
FIXTURE = ROOT / "scripts/mega65-math-abi-main.c"
HOST_FIXTURE = ROOT / "scripts/mega65-math-host-oracle-main.c"
ABI_FIXTURE = ROOT / "scripts/mega65-math-caller-abi.c"
OVERRIDE = ROOT / "src/mega65_math.s"
UNSIGNED = ("__udivhi3", "__umodhi3", "__udivmodhi4", "__mulhi3")
SIGNED = ("__divhi3", "__modhi3")
ALL_RUNTIME = UNSIGNED + SIGNED
IMPLEMENTATION = {symbol: "lisp65_hw_" + symbol[2:] for symbol in ALL_RUNTIME}
MOD_ADJUST = "lisp65_mod_adjust_tagged"
LIBCRT = LLVM_MOS_ROOT / "mos-platform/common/lib/libcrt.a"


def run(argv: list[str]) -> str:
    proc = subprocess.run(argv, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    if proc.returncode:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(argv)}\n{proc.stdout}")
    return proc.stdout


def section_size(size: pathlib.Path, elf: pathlib.Path, section: str) -> int:
    output = run([str(size), "--format=sysv", str(elf)])
    match = re.search(rf"^{re.escape(section)}\s+(\d+)\s+", output, re.MULTILINE)
    if not match:
        raise RuntimeError(f"{section} missing from {elf}\n{output}")
    return int(match.group(1))


def symbols(nm: pathlib.Path, elf: pathlib.Path) -> dict[str, tuple[int, int, str]]:
    output = run([str(nm), "--print-size", "--radix=x", str(elf)])
    result: dict[str, tuple[int, int, str]] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) == 4:
            address_hex, size_hex, kind, name = fields
            result[name] = (int(address_hex, 16), int(size_hex, 16), kind)
    return result


def link(cc: pathlib.Path, out: pathlib.Path, *, override: bool, signed: bool) -> pathlib.Path:
    argv = [str(cc), "-Os", "-I", str(ROOT / "src")]
    if signed:
        argv.append("-DLISP65_MATH_TEST_SIGNED")
    argv.append(str(FIXTURE))
    if override:
        argv.append(str(OVERRIDE))
        for abi_name, implementation in IMPLEMENTATION.items():
            argv.append(f"-Wl,--defsym={abi_name}={implementation}")
    argv.extend([f"-Wl,-Map={out}.map", "-o", str(out)])
    run(argv)
    return pathlib.Path(f"{out}.elf")


def check_model() -> None:
    values = [0, 1, 2, 3, 7, 0x7f, 0x80, 0xff, 0x100, 0x7fff, 0x8000,
              0xfffe, 0xffff]
    rng = random.Random(0x65)
    pairs = [(a, b) for a in values for b in values]
    pairs.extend((rng.randrange(0x10000), rng.randrange(0x10000)) for _ in range(8192))
    for dividend, divisor in pairs:
        if divisor == 0:
            quotient, remainder = 0, dividend
        else:
            quotient, remainder = divmod(dividend, divisor)
        if not (0 <= quotient <= 0xffff and 0 <= remainder <= 0xffff):
            raise AssertionError((dividend, divisor, quotient, remainder))
        if divisor and quotient * divisor + remainder != dividend:
            raise AssertionError((dividend, divisor, quotient, remainder))
        product = (dividend * divisor) & 0xffff
        if product != ((dividend * divisor) % 0x10000):
            raise AssertionError((dividend, divisor, product))

    fix_edges = [-16384, -16383, -257, -3, -2, -1, 0, 1, 2, 3, 257, 16382, 16383]
    fix_divisors = [value for value in fix_edges if value]
    fix_pairs = [(a, b) for a in fix_edges for b in fix_edges if b]
    fix_pairs.extend(
        (rng.randrange(-16384, 16384), rng.choice(fix_divisors))
        for _ in range(8192)
    )
    for dividend, divisor in fix_pairs:
        quotient = abs(dividend) // abs(divisor)
        if (dividend < 0) != (divisor < 0):
            quotient = -quotient
        remainder = dividend - quotient * divisor
        tagged_remainder = ((remainder << 1) | 1) & 0xFFFF
        tagged_divisor = ((divisor << 1) | 1) & 0xFFFF
        adjusted = tagged_remainder
        signed_xor = (tagged_remainder ^ tagged_divisor) & 0xFFFF
        if tagged_remainder != 1 and signed_xor & 0x8000:
            adjusted = (tagged_remainder + tagged_divisor - 1) & 0xFFFF
        value = adjusted >> 1
        if adjusted & 0x8000:
            value -= 0x8000
        if value != dividend % divisor:
            raise AssertionError((dividend, divisor, remainder, value))


def check_object(cc: pathlib.Path, objdump: pathlib.Path, temp: pathlib.Path) -> None:
    obj = temp / "mega65_math.o"
    run([str(cc), "-c", str(OVERRIDE), "-o", str(obj)])
    dis = run([str(objdump), "-dr", "--no-show-raw-insn", str(obj)]).lower()
    for symbol in ALL_RUNTIME:
        implementation = IMPLEMENTATION[symbol]
        if f"<{implementation}>:" not in dis:
            raise AssertionError(f"missing assembly symbol {implementation}")
    if f"<{MOD_ADJUST}>:" not in dis:
        raise AssertionError(f"missing assembly symbol {MOD_ADJUST}")
    required = ("php", "sei", "plp", "bit\t$d70f", "sta\t$d770", "sta\t$d771",
                "stz\t$d772", "stz\t$d773", "sta\t$d774", "sta\t$d775",
                "stz\t$d776", "stz\t$d777", "lda\t$d76c", "lda\t$d76d",
                "sbc\t$d778", "sbc\t$d779", "ldz\t#$0")
    for instruction in required:
        if instruction not in dis:
            raise AssertionError(f"missing target instruction: {instruction}")
    if re.search(r"\b(stw|ldw)\b", dis):
        raise AssertionError("math-unit accesses must be byte-wide")
    calls = re.findall(r"\bjsr\b[^\n]*(?:\n[^\n]*)?", dis)
    if len(calls) != 2:
        raise AssertionError(f"only the two signed-wrapper calls are allowed: {calls}")


def check_c_abi(cc: pathlib.Path, temp: pathlib.Path) -> None:
    asm = temp / "caller.s"
    run([str(cc), "-Os", "-fno-lto", "-I", str(ROOT / "src"), "-S",
         str(ABI_FIXTURE), "-o", str(asm)])
    text = asm.read_text(encoding="utf-8")
    for symbol in UNSIGNED:
        if f"jsr\t{symbol}" not in text:
            raise AssertionError(f"C fixture did not emit a call to {symbol}")
    if f"jsr\t{MOD_ADJUST}" not in text:
        raise AssertionError(f"C fixture did not emit a call to {MOD_ADJUST}")
    for rc in ("__rc2", "__rc3", "__rc4", "__rc5"):
        if rc not in text:
            raise AssertionError(f"expected ABI register {rc} is absent")


def check_links(cc: pathlib.Path, nm: pathlib.Path, size: pathlib.Path,
                temp: pathlib.Path) -> None:
    baseline = link(cc, temp / "baseline.prg", override=False, signed=True)
    replaced = link(cc, temp / "replaced.prg", override=True, signed=True)
    unsigned_only = link(cc, temp / "unsigned.prg", override=True, signed=False)

    base_symbols = symbols(nm, baseline)
    new_symbols = symbols(nm, replaced)
    unsigned_symbols = symbols(nm, unsigned_only)
    for symbol in ALL_RUNTIME:
        if symbol not in base_symbols or symbol not in new_symbols:
            raise AssertionError(f"missing comparison symbol {symbol}")
        implementation = IMPLEMENTATION[symbol]
        if implementation not in new_symbols:
            raise AssertionError(f"missing implementation symbol {implementation}")
        if new_symbols[symbol][0] != new_symbols[implementation][0]:
            raise AssertionError(f"ABI alias does not bind {symbol} to {implementation}")
    for symbol in UNSIGNED:
        if symbol not in unsigned_symbols:
            raise AssertionError(f"missing unsigned override {symbol}")

    unsigned_map = pathlib.Path(f"{temp / 'unsigned.prg'}.map").read_text(encoding="utf-8")
    if "divmod.cc.obj" in unsigned_map or "mul.cc.obj" in unsigned_map:
        raise AssertionError("unsigned link still extracted libcrt divmod/mul implementations")
    signed_map = pathlib.Path(f"{temp / 'replaced.prg'}.map").read_text(encoding="utf-8")
    if "divmod.cc.obj" in signed_map or "mul.cc.obj" in signed_map:
        raise AssertionError("signed link still extracted libcrt divmod/mul implementations")
    if "mega65_math" not in signed_map:
        raise AssertionError("override object has no contribution in signed link")

    baseline_text = section_size(size, baseline, ".text")
    replaced_text = section_size(size, replaced, ".text")
    reclaim = baseline_text - replaced_text
    if reclaim <= 0:
        raise AssertionError(f"override did not reclaim text: {baseline_text} -> {replaced_text}")
    print("mega65-math-override: PASS unsigned_model=8361 tagged_mod_model=8348 "
          "abi=AX+rc2/3+rc4/5")
    print(f"mega65-math-override: baseline_text={baseline_text} override_text={replaced_text} "
          f"net_reclaim={reclaim}")
    print("mega65-math-override: libcrt divmod/mul bodies not extracted; strict aliases selected")


def ir_function(ir: str, name: str) -> str:
    match = re.search(rf"^define [^\n]*@{re.escape(name)}\([^\n]*\) [^\n]*\{{\n(.*?)^\}}",
                      ir, re.MULTILINE | re.DOTALL)
    if not match:
        raise AssertionError(f"missing libcrt IR function {name}")
    return match.group(1)


def check_libcrt_ir(cc: pathlib.Path, bitcode: pathlib.Path, temp: pathlib.Path) -> None:
    ll = temp / "divmod.ll"
    run([str(cc), "-x", "ir", "-S", "-emit-llvm", str(bitcode), "-o", str(ll)])
    ir = ll.read_text(encoding="utf-8")
    udiv = ir_function(ir, "__udivhi3")
    umod = ir_function(ir, "__umodhi3")
    divmod = ir_function(ir, "__udivmodhi4")
    sdiv = ir_function(ir, "__divhi3")
    smod = ir_function(ir, "__modhi3")
    if "icmp eq i16 %1, 0" not in udiv or not re.search(r"phi i16 \[ 0, %\d+ \]", udiv):
        raise AssertionError("libcrt no longer defines unsigned x/0 as zero")
    if "icmp eq i16 %1, 0" not in umod or not re.search(r"phi i16 \[ %0, %\d+ \]", umod):
        raise AssertionError("libcrt no longer defines unsigned x%0 as x")
    if ("icmp eq i16 %1, 0" not in divmod or
            not re.search(r"phi i16 \[ %0, %\d+ \]", divmod) or
            not re.search(r"phi i16 \[ 0, %\d+ \]", divmod) or
            "store i16" not in divmod):
        raise AssertionError("libcrt __udivmodhi4 zero/remainder contract changed")
    if "udiv i16" not in sdiv or "urem i16" not in smod:
        raise AssertionError("libcrt signed-wrapper structure changed")


def check_host_oracle(cc: pathlib.Path, ar: pathlib.Path, host_clang: str,
                      temp: pathlib.Path) -> None:
    if not LIBCRT.is_file():
        raise RuntimeError(f"missing llvm-mos libcrt: {LIBCRT}")
    subprocess.run([str(ar), "x", str(LIBCRT), "divmod.cc.obj"], cwd=temp,
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    bitcode = temp / "divmod.cc.obj"
    check_libcrt_ir(cc, bitcode, temp)
    host_obj = temp / "divmod-host.o"
    host_bin = temp / "host-oracle"
    run([host_clang, "-target", "x86_64-unknown-linux-gnu", "-x", "ir", "-c",
         str(bitcode), "-o", str(host_obj)])
    run([host_clang, "-O2", "-fno-builtin", str(HOST_FIXTURE), str(host_obj),
         "-o", str(host_bin)])
    output = run([str(host_bin)])
    if "mega65-math-host-oracle: PASS " not in output:
        raise AssertionError(output)
    print(output.strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cc", type=pathlib.Path, default=DEFAULT_CC)
    parser.add_argument("--nm", type=pathlib.Path, default=DEFAULT_NM)
    parser.add_argument("--objdump", type=pathlib.Path, default=DEFAULT_OBJDUMP)
    parser.add_argument("--size", type=pathlib.Path, default=DEFAULT_SIZE)
    parser.add_argument("--ar", type=pathlib.Path, default=DEFAULT_AR)
    parser.add_argument("--host-clang", default=shutil.which("clang") or "clang")
    args = parser.parse_args()
    for tool in (args.cc, args.nm, args.objdump, args.size, args.ar):
        if not tool.is_file():
            raise SystemExit(f"missing tool: {tool}")
    check_model()
    with tempfile.TemporaryDirectory(prefix="lisp65-mega65-math-") as tmp:
        temp = pathlib.Path(tmp)
        check_object(args.cc, args.objdump, temp)
        check_c_abi(args.cc, temp)
        check_host_oracle(args.cc, args.ar, args.host_clang, temp)
        check_links(args.cc, args.nm, args.size, temp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
