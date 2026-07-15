#!/usr/bin/env python3
"""Read MEGA65 hardware-opportunity smoke results via m65/JTAG.

This helper resolves the result symbols from the PRG ELF, dumps them with
``m65 --memsave`` and decodes the PASS/FAIL arrays. It never resets the machine.
"""
from __future__ import annotations

import argparse
import struct
import subprocess
from pathlib import Path


SCHEMAS = {
    "access": {
        "prefix": "hw_access",
        "cases": [
            "legacy_dma",
            "edma_copy",
            "edma_fill",
            "edma_attic",
            "flat_bank0",
            "q_reg",
            "math_mul",
            "math_div",
            "flat_bank4_obs",
        ],
    },
    "color": {
        "prefix": "hw_color",
        "cases": [
            "edma_fill",
            "edma_pattern",
            "flat_cell_obs",
        ],
    },
    "screen": {
        "prefix": "hw_screen",
        "cases": [
            "geometry",
            "screen_copy_top",
            "screen_copy_last_visible",
            "screen_tail_fill",
            "color_copy_top",
            "color_copy_last_visible",
            "color_tail_fill",
        ],
    },
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("kind", choices=sorted(SCHEMAS), help="smoke kind to decode")
    p.add_argument("--elf", required=True, help="PRG ELF file to resolve symbols from")
    p.add_argument("--device", default="/dev/ttyUSB1", help="m65 serial/JTAG device")
    p.add_argument("--tools", default="tools/m65tools", help="m65tools directory")
    p.add_argument("--nm", default="tools/llvm-mos/bin/llvm-nm", help="llvm-nm path")
    p.add_argument("--out-dir", default="build/hw", help="directory for dumps/report")
    p.add_argument("--prefix", default="", help="output filename prefix")
    p.add_argument("--dry-run", action="store_true", help="print commands, do not run m65")
    return p.parse_args()


def nm_symbols(nm: str, elf: Path) -> dict[str, int]:
    cp = subprocess.run([nm, "--radix=x", str(elf)], check=True, text=True, stdout=subprocess.PIPE)
    out: dict[str, int] = {}
    for line in cp.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3:
            out[parts[2]] = int(parts[0], 16)
    return out


def dump_symbol(m65: Path, device: str, name: str, addr: int, size: int,
                out_dir: Path, prefix: str, dry_run: bool) -> bytes:
    path = out_dir / f"{prefix}-{name}.bin"
    spec = f"0x{addr:04x}:0x{addr + size:04x}={path}"
    cmd = [str(m65), "-l", device, "--memsave", spec]
    if dry_run:
        print("DRY-RUN:", " ".join(cmd))
        return bytes(size)
    subprocess.run(cmd, check=True)
    data = path.read_bytes()
    if len(data) != size:
        raise SystemExit(f"{name}: expected {size} bytes, got {len(data)} from {path}")
    return data


def main() -> int:
    args = parse_args()
    schema = SCHEMAS[args.kind]
    elf = Path(args.elf)
    if not elf.is_file():
        raise SystemExit(f"missing ELF: {elf}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = args.prefix or f"hw-{args.kind}"
    m65 = Path(args.tools) / "m65"
    syms = nm_symbols(args.nm, elf)
    sp = schema["prefix"]
    cases = schema["cases"]

    names = {
        "pass": f"{sp}_pass",
        "total": f"{sp}_total",
        "results": f"{sp}_results",
        "got": f"{sp}_got",
        "want": f"{sp}_want",
    }
    missing = [name for name in names.values() if name not in syms]
    if missing:
        raise SystemExit(f"missing symbols in {elf}: {', '.join(missing)}")

    raw_pass = dump_symbol(m65, args.device, names["pass"], syms[names["pass"]], 1,
                           out_dir, prefix, args.dry_run)
    raw_total = dump_symbol(m65, args.device, names["total"], syms[names["total"]], 1,
                            out_dir, prefix, args.dry_run)
    raw_results = dump_symbol(m65, args.device, names["results"], syms[names["results"]],
                              len(cases), out_dir, prefix, args.dry_run)
    raw_got = dump_symbol(m65, args.device, names["got"], syms[names["got"]],
                          len(cases) * 2, out_dir, prefix, args.dry_run)
    raw_want = dump_symbol(m65, args.device, names["want"], syms[names["want"]],
                           len(cases) * 2, out_dir, prefix, args.dry_run)

    if args.dry_run:
        lines = [
            f"kind={args.kind}",
            f"elf={elf}",
            f"device={args.device}",
            "dry_run=1",
            "decode=skipped",
        ]
        report = out_dir / f"{prefix}.txt"
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{args.kind}: dry-run, decode skipped")
        print(f"wrote {report}")
        return 0

    passed = raw_pass[0]
    total = raw_total[0]
    got = list(struct.unpack("<" + "H" * len(cases), raw_got))
    want = list(struct.unpack("<" + "H" * len(cases), raw_want))

    lines = [
        f"kind={args.kind}",
        f"elf={elf}",
        f"device={args.device}",
        f"dry_run={int(args.dry_run)}",
        f"pass={passed}",
        f"total={total}",
    ]
    print(f"{args.kind}: pass {passed}/{total}")
    for i, case in enumerate(cases):
        ok = raw_results[i]
        line = f"{case}={'PASS' if ok else 'FAIL'} got=0x{got[i]:04x} want=0x{want[i]:04x}"
        print("  " + line)
        lines.append(line)

    report = out_dir / f"{prefix}.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {report}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
