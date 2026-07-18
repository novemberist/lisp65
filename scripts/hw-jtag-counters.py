#!/usr/bin/env python3
"""Read lisp65 hardware counters via m65/JTAG.

The script resolves known counter symbols from the PRG ELF with llvm-nm, dumps each
symbol-sized memory range with m65 --memsave, decodes little-endian values, and
writes a small text report. It never resets the MEGA65.
"""
from __future__ import annotations

import argparse
import struct
import subprocess
from pathlib import Path


SYMBOLS: dict[str, tuple[str, int]] = {
    "nsym": ("u16", 2),
    "npool": ("u16", 2),
    "dir_n": ("u16", 2),
    "ext_code_init": ("u8", 1),
    "ext_code_hw": ("u16", 2),
    "crepl_gensym": ("u16", 2),
    "perf_vm_ops": ("u32", 4),
    "perf_allocs": ("u32", 4),
    "gc_runs": ("u16", 2),
    "gc_badobj": ("u16", 2),
    "mem_oom": ("u8", 1),
    "dma_cell": ("u16", 2),
    "dma_code": ("u16", 2),
    "dma_wr": ("u16", 2),
    "dma_sym": ("u16", 2),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--elf", required=True, help="PRG ELF file to resolve symbols from")
    p.add_argument("--device", default="/dev/ttyUSB1", help="m65 serial/JTAG device")
    p.add_argument("--tools", default="tools/m65tools", help="m65tools directory")
    p.add_argument("--nm", default="tools/llvm-mos/bin/llvm-nm", help="llvm-nm path")
    p.add_argument("--out-dir", default="build/hw", help="directory for dumps/report")
    p.add_argument("--prefix", default="hw-counters", help="output filename prefix")
    p.add_argument("--dry-run", action="store_true", help="print commands, do not run m65")
    return p.parse_args()


def nm_symbols(nm: str, elf: Path) -> dict[str, int]:
    cp = subprocess.run(
        [nm, "--radix=x", str(elf)],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    out: dict[str, int] = {}
    for line in cp.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] in SYMBOLS:
            out[parts[2]] = int(parts[0], 16)
    return out


def decode(kind: str, data: bytes) -> int:
    if kind == "u8":
        return data[0]
    if kind == "u16":
        return struct.unpack_from("<H", data)[0]
    if kind == "u32":
        return struct.unpack_from("<I", data)[0]
    raise ValueError(kind)


def main() -> int:
    args = parse_args()
    elf = Path(args.elf)
    if not elf.is_file():
        raise SystemExit(f"missing ELF: {elf}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    m65 = Path(args.tools) / "m65"
    syms = nm_symbols(args.nm, elf)

    report: list[str] = []
    report.append(f"elf={elf}")
    report.append(f"device={args.device}")
    report.append(f"dry_run={int(args.dry_run)}")

    values: dict[str, int] = {}
    for name, (kind, size) in SYMBOLS.items():
        if name not in syms:
            report.append(f"{name}=missing")
            continue
        addr = syms[name]
        dump = out_dir / f"{args.prefix}-{name}.bin"
        spec = f"0x{addr:04x}:0x{addr + size:04x}={dump}"
        cmd = [str(m65), "-l", args.device, "--memsave", spec]
        report.append(f"{name}_addr=0x{addr:04x}")
        if args.dry_run:
            print("DRY-RUN:", " ".join(cmd))
            continue
        subprocess.run(cmd, check=True)
        data = dump.read_bytes()
        if len(data) != size:
            raise SystemExit(f"{name}: expected {size} bytes, got {len(data)} from {dump}")
        values[name] = decode(kind, data)
        report.append(f"{name}={values[name]}")

    if values:
        print("HW counters:")
        for name in SYMBOLS:
            if name in values:
                print(f"  {name}={values[name]}")

    report_path = out_dir / f"{args.prefix}.txt"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
