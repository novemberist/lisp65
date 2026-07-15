#!/usr/bin/env python3
"""Read and gate lisp65 runtime-stack watermark results through m65/JTAG."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import time
from typing import Mapping, Sequence


SCHEMA = "lisp65-hw-stack-probe-readback-v2"
SOFT_FLOOR_SYMBOL = "__lisp65_workbench_runtime_overlay_limit"
SOFT_STACK_TOP = 0xD000
SOFT_CANARY = 0xA5
HW_CANARY = 0x5A
ANNEX_SYMBOLS = {
    "annex_start": "__lisp65_resident_island_annex_start",
    "annex_before": "lisp65_rootstack_canary_before",
    "annex_rootstack": "gc_rootstack",
    "annex_after": "lisp65_rootstack_canary_after",
    "annex_end": "__lisp65_resident_island_annex_end",
}
ANNEX_BEFORE_CANARY = 0x65A5
ANNEX_AFTER_CANARY = 0xA565
ANNEX_BYTES = 260


@dataclass(frozen=True)
class Field:
    symbol: str
    size: int


FIELDS = {
    "complete": Field("lisp65_boot_probe_complete", 1),
    "flags": Field("lisp65_boot_probe_flags", 1),
    "soft_initial": Field("lisp65_boot_probe_soft_initial", 2),
    "hw_initial": Field("lisp65_boot_probe_hw_initial", 1),
    "wipe_ok": Field("lisp65_boot_overlay_wipe_ok", 1),
}


class ProbeError(RuntimeError):
    pass


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", help="probe PRG ELF used to resolve readback symbols")
    parser.add_argument("--device", default="/dev/ttyUSB1", help="m65 serial/JTAG device")
    parser.add_argument("--tools", default="tools/m65tools", help="m65tools directory")
    parser.add_argument("--nm", default="tools/llvm-mos/bin/llvm-nm", help="llvm-nm path")
    parser.add_argument("--out-dir", default="build/hw", help="dump and report directory")
    parser.add_argument("--prefix", default="hw-stack-probe", help="output filename prefix")
    parser.add_argument("--min-soft-margin", type=int, default=256,
                        help="minimum accepted soft-stack margin in bytes")
    parser.add_argument("--min-hw-remaining", type=int, default=32,
                        help="minimum accepted hardware-stack remainder in bytes")
    parser.add_argument("--ready-timeout", type=int, default=15,
                        help="seconds to wait for complete=1 and wipe_ok=1")
    parser.add_argument("--poll-interval", type=float, default=0.5,
                        help="seconds between readiness reads")
    parser.add_argument("--dry-run", action="store_true",
                        help="resolve symbols and print memsave commands without hardware access")
    parser.add_argument("--selftest", action="store_true",
                        help="run decoder and mutation tests")
    return parser.parse_args(argv)


def nm_symbols(nm: str, elf: Path) -> dict[str, int]:
    try:
        completed = subprocess.run(
            [nm, "--defined-only", "--radix=x", str(elf)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ProbeError(f"cannot read symbols from {elf}: {exc}") from exc

    symbols: dict[str, int] = {}
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        try:
            address = int(parts[0], 16)
        except ValueError:
            continue
        name = parts[2]
        if name in symbols and symbols[name] != address:
            raise ProbeError(f"duplicate symbol with conflicting addresses: {name}")
        symbols[name] = address
    return symbols


def required_addresses(symbols: Mapping[str, int]) -> dict[str, int]:
    required = [field.symbol for field in FIELDS.values()] + [SOFT_FLOOR_SYMBOL]
    missing = [symbol for symbol in required if symbol not in symbols]
    if missing:
        raise ProbeError("missing probe symbols: " + ", ".join(missing))
    addresses = {name: symbols[field.symbol] for name, field in FIELDS.items()}
    addresses["soft_floor"] = symbols[SOFT_FLOOR_SYMBOL]
    missing_annex = [name for name in ANNEX_SYMBOLS.values() if name not in symbols]
    if missing_annex:
        raise ProbeError("missing rootstack annex symbols: " + ", ".join(missing_annex))
    addresses.update({name: symbols[symbol] for name, symbol in ANNEX_SYMBOLS.items()})
    start = addresses["annex_start"]
    expected = {
        "annex_before": start,
        "annex_rootstack": start + 2,
        "annex_after": start + 258,
        "annex_end": start + ANNEX_BYTES,
    }
    drift = [
        "%s=0x%04x (expected 0x%04x)" % (name, addresses[name], value)
        for name, value in expected.items() if addresses[name] != value
    ]
    if drift:
        raise ProbeError("rootstack annex layout drift: " + ", ".join(drift))
    return addresses


def dump_field(m65: Path, device: str, field: Field, address: int,
               out_dir: Path, prefix: str, dry_run: bool) -> bytes:
    path = out_dir / f"{prefix}-{field.symbol}.bin"
    spec = f"0x{address:x}:0x{address + field.size:x}={path}"
    command = [str(m65), "-l", device, "--memsave", spec]
    if dry_run:
        print("DRY-RUN:", " ".join(command))
        return bytes(field.size)
    try:
        subprocess.run(command, check=True)
        data = path.read_bytes()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ProbeError(f"cannot read {field.symbol}: {exc}") from exc
    if len(data) != field.size:
        raise ProbeError(
            f"{field.symbol}: expected {field.size} bytes, got {len(data)} from {path}"
        )
    return data


def dump_range(m65: Path, device: str, name: str, address: int, size: int,
               out_dir: Path, prefix: str, dry_run: bool) -> bytes:
    field = Field(name, size)
    return dump_field(m65, device, field, address, out_dir, prefix, dry_run)


def decode(raw: Mapping[str, bytes]) -> dict[str, int]:
    unexpected = sorted(set(raw) - set(FIELDS))
    missing = sorted(set(FIELDS) - set(raw))
    if unexpected:
        raise ProbeError("unexpected readback fields: " + ", ".join(unexpected))
    if missing:
        raise ProbeError("missing readback fields: " + ", ".join(missing))

    values: dict[str, int] = {}
    for name, field in FIELDS.items():
        data = raw[name]
        if len(data) != field.size:
            raise ProbeError(
                f"{field.symbol}: expected {field.size} bytes, got {len(data)}"
            )
        values[name] = int.from_bytes(data, byteorder="little", signed=False)
    return values


def derive_low_water(values: Mapping[str, int], soft_floor: int,
                     soft_window: bytes, page1: bytes) -> dict[str, int]:
    initial = values["soft_initial"]
    hw_initial = values["hw_initial"]
    if not soft_floor < initial <= SOFT_STACK_TOP:
        raise ProbeError(
            f"invalid soft-stack probe range: soft_floor=0x{soft_floor:04x} "
            f"initial=0x{initial:04x}"
        )
    expected_soft = SOFT_STACK_TOP - soft_floor
    if len(soft_window) != expected_soft:
        raise ProbeError(
            f"soft-stack dump has {len(soft_window)} bytes, expected {expected_soft}"
        )
    if len(page1) != 256:
        raise ProbeError(f"Page-1 dump has {len(page1)} bytes, expected 256")

    armed_soft = soft_window[:initial - soft_floor]
    changed_soft = next(
        (index for index, value in enumerate(armed_soft) if value != SOFT_CANARY),
        len(armed_soft),
    )
    armed_hw = page1[:hw_initial + 1]
    changed_hw = next(
        (index for index, value in enumerate(armed_hw) if value != HW_CANARY),
        len(armed_hw),
    )
    derived = dict(values)
    derived["soft_low"] = soft_floor + changed_soft
    derived["soft_margin"] = changed_soft
    # The changed byte itself is conservatively not counted as free.
    derived["hw_low"] = changed_hw if changed_hw <= hw_initial else hw_initial
    derived["hw_remaining"] = derived["hw_low"]
    return derived


def evaluate(values: Mapping[str, int], min_soft_margin: int,
             min_hw_remaining: int) -> list[str]:
    missing = sorted(set(FIELDS) - set(values))
    if missing:
        raise ProbeError("missing decoded fields: " + ", ".join(missing))
    errors: list[str] = []
    if values["complete"] != 1:
        errors.append(f"probe incomplete: complete={values['complete']}")
    if values["flags"] != 0:
        errors.append(f"probe flags/collision: flags=0x{values['flags']:02x}")
    if values["wipe_ok"] != 1:
        errors.append(f"overlay wipe check failed: wipe_ok={values['wipe_ok']}")
    if values["soft_margin"] < min_soft_margin:
        errors.append(
            f"soft-stack margin {values['soft_margin']} < required {min_soft_margin}"
        )
    if values["hw_remaining"] < min_hw_remaining:
        errors.append(
            f"hardware-stack remaining {values['hw_remaining']} < required {min_hw_remaining}"
        )
    return errors


def evaluate_annex(before: int | None, after: int | None) -> list[str]:
    if before is None and after is None:
        return []
    if before is None or after is None:
        raise ProbeError("partial rootstack annex canary readback")
    errors = []
    if before != ANNEX_BEFORE_CANARY:
        errors.append(
            f"rootstack annex lower canary 0x{before:04x} != 0x{ANNEX_BEFORE_CANARY:04x}"
        )
    if after != ANNEX_AFTER_CANARY:
        errors.append(
            f"rootstack annex upper canary 0x{after:04x} != 0x{ANNEX_AFTER_CANARY:04x}"
        )
    return errors


def report_lines(elf: Path, device: str, dry_run: bool, min_soft_margin: int,
                 min_hw_remaining: int, values: Mapping[str, int] | None,
                 errors: Sequence[str], annex_before: int | None = None,
                 annex_after: int | None = None,
                 annex_present: bool = False) -> list[str]:
    lines = [
        f"schema={SCHEMA}",
        f"elf={elf}",
        f"device={device}",
        f"dry_run={int(dry_run)}",
        f"min_soft_margin={min_soft_margin}",
        f"min_hw_remaining={min_hw_remaining}",
        f"rootstack_annex_evidence={'present' if annex_present else 'unavailable'}",
    ]
    if annex_present and not dry_run:
        lines.extend((
            f"rootstack_annex_canary_before=0x{annex_before:04x}",
            f"rootstack_annex_canary_after=0x{annex_after:04x}",
        ))
    if values is None:
        lines.extend(("decode=skipped", "status=DRY-RUN"))
        return lines
    lines.extend((
        f"complete={values['complete']}",
        f"flags=0x{values['flags']:02x}",
        f"collision={int(values['flags'] != 0)}",
        f"soft_initial=0x{values['soft_initial']:04x}",
        f"soft_low=0x{values['soft_low']:04x}",
        f"soft_margin={values['soft_margin']}",
        f"hw_initial=0x{values['hw_initial']:02x}",
        f"hw_low=0x{values['hw_low']:02x}",
        f"hw_remaining={values['hw_remaining']}",
        f"wipe_ok={values['wipe_ok']}",
        f"status={'FAIL' if errors else 'PASS'}",
    ))
    lines.extend(f"error={error}" for error in errors)
    return lines


def _raw(values: Mapping[str, int]) -> dict[str, bytes]:
    return {
        name: int(values[name]).to_bytes(field.size, byteorder="little", signed=False)
        for name, field in FIELDS.items()
    }


def selftest() -> int:
    soft_floor = 0xCC00
    valid = {
        "complete": 1,
        "flags": 0,
        "soft_initial": 0xd000,
        "hw_initial": 0xff,
        "wipe_ok": 1,
    }
    cases = 0
    failures: list[str] = []

    def canaries(soft_margin: int, hw_remaining: int) -> tuple[bytes, bytes]:
        soft = bytearray([SOFT_CANARY] * (SOFT_STACK_TOP - soft_floor))
        soft[soft_margin:] = bytes([SOFT_CANARY ^ 0xff]) * (len(soft) - soft_margin)
        page = bytearray([HW_CANARY] * 256)
        page[hw_remaining:] = bytes([HW_CANARY ^ 0xff]) * (256 - hw_remaining)
        return bytes(soft), bytes(page)

    def check(name: str, candidate: Mapping[str, int], soft_margin: int,
              hw_remaining: int, should_pass: bool) -> None:
        nonlocal cases
        cases += 1
        soft, page = canaries(soft_margin, hw_remaining)
        decoded = derive_low_water(decode(_raw(candidate)), soft_floor, soft, page)
        passed = not evaluate(decoded, 256, 32)
        if passed != should_pass:
            failures.append(name)

    check("valid-boundaries", valid, 256, 32, True)
    for name, value in (
        ("incomplete", ("complete", 0)),
        ("complete-noncanonical", ("complete", 2)),
        ("flags", ("flags", 1)),
        ("wipe-zero", ("wipe_ok", 0)),
        ("wipe-noncanonical", ("wipe_ok", 2)),
    ):
        mutated = dict(valid)
        mutated[value[0]] = value[1]
        check(name, mutated, 256, 32, False)
    check("soft-below", valid, 255, 32, False)
    check("hw-below", valid, 256, 31, False)

    cases += 1
    truncated = _raw(valid)
    truncated["soft_initial"] = truncated["soft_initial"][:1]
    try:
        decode(truncated)
        failures.append("truncated-decoder")
    except ProbeError:
        pass

    cases += 1
    bad_range = dict(valid)
    bad_range["soft_initial"] = soft_floor
    soft, page = canaries(256, 32)
    try:
        derive_low_water(decode(_raw(bad_range)), soft_floor, soft, page)
        failures.append("invalid-soft-range")
    except ProbeError:
        pass

    cases += 1
    missing = _raw(valid)
    del missing["flags"]
    try:
        decode(missing)
        failures.append("missing-decoder")
    except ProbeError:
        pass

    cases += 1
    extra = _raw(valid)
    extra["extra"] = b"\x00"
    try:
        decode(extra)
        failures.append("extra-decoder")
    except ProbeError:
        pass

    cases += 1
    if evaluate_annex(ANNEX_BEFORE_CANARY, ANNEX_AFTER_CANARY):
        failures.append("annex-valid")
    cases += 1
    if not evaluate_annex(ANNEX_BEFORE_CANARY ^ 1, ANNEX_AFTER_CANARY):
        failures.append("annex-before-corrupt")
    cases += 1
    if not evaluate_annex(ANNEX_BEFORE_CANARY, ANNEX_AFTER_CANARY ^ 1):
        failures.append("annex-after-corrupt")

    symbol_fixture = {
        field.symbol: 0x3000 + index * 2
        for index, field in enumerate(FIELDS.values())
    }
    symbol_fixture[SOFT_FLOOR_SYMBOL] = soft_floor
    cases += 1
    try:
        required_addresses(symbol_fixture)
        failures.append("annex-missing-symbols")
    except ProbeError:
        pass
    full_annex = dict(symbol_fixture)
    full_annex.update({
        ANNEX_SYMBOLS["annex_start"]: 0x1C5C,
        ANNEX_SYMBOLS["annex_before"]: 0x1C5C,
        ANNEX_SYMBOLS["annex_rootstack"]: 0x1C5E,
        ANNEX_SYMBOLS["annex_after"]: 0x1D5E,
        ANNEX_SYMBOLS["annex_end"]: 0x1D60,
    })
    cases += 1
    if required_addresses(full_annex).get("annex_end") != 0x1D60:
        failures.append("annex-full-layout")
    cases += 1
    partial_annex = dict(full_annex)
    del partial_annex[ANNEX_SYMBOLS["annex_after"]]
    try:
        required_addresses(partial_annex)
        failures.append("annex-partial-symbols")
    except ProbeError:
        pass
    cases += 1
    drifted_annex = dict(full_annex)
    drifted_annex[ANNEX_SYMBOLS["annex_rootstack"]] += 2
    try:
        required_addresses(drifted_annex)
        failures.append("annex-layout-drift")
    except ProbeError:
        pass

    if failures:
        print("hw-stack-probe-readback selftest: FAIL " + ",".join(failures), file=sys.stderr)
        return 1
    print(f"hw-stack-probe-readback selftest: PASS cases={cases}")
    return 0


def run(args: argparse.Namespace) -> int:
    if not 0 <= args.min_soft_margin <= 0xffff:
        raise ProbeError("--min-soft-margin must be in 0..65535")
    if not 0 <= args.min_hw_remaining <= 0xff:
        raise ProbeError("--min-hw-remaining must be in 0..255")
    if args.ready_timeout < 0:
        raise ProbeError("--ready-timeout must be non-negative")
    if args.poll_interval <= 0:
        raise ProbeError("--poll-interval must be positive")
    if not args.elf:
        raise ProbeError("--elf is required unless --selftest is used")
    elf = Path(args.elf)
    if not elf.is_file():
        raise ProbeError(f"missing ELF: {elf}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    symbols = nm_symbols(args.nm, elf)
    addresses = required_addresses(symbols)
    annex_present = "annex_start" in addresses
    soft_floor = addresses["soft_floor"]
    if not 0 <= soft_floor < SOFT_STACK_TOP:
        raise ProbeError(
            f"{SOFT_FLOOR_SYMBOL}=0x{soft_floor:x} is outside the runtime stack window"
        )
    m65 = Path(args.tools) / "m65"
    if not args.dry_run and not m65.is_file():
        raise ProbeError(f"missing m65 tool: {m65}")

    raw: dict[str, bytes] = {}
    ready_names = ("complete", "wipe_ok")
    if args.dry_run:
        for name, field in FIELDS.items():
            raw[name] = dump_field(
                m65, args.device, field, addresses[name], out_dir,
                args.prefix, True,
            )
    else:
        deadline = time.monotonic() + args.ready_timeout
        while True:
            for name in ready_names:
                field = FIELDS[name]
                raw[name] = dump_field(
                    m65, args.device, field, addresses[name], out_dir,
                    args.prefix, False,
                )
            complete = raw["complete"][0]
            wipe_ok = raw["wipe_ok"][0]
            if complete == 1 and wipe_ok == 1:
                break
            if complete not in (0, 1) or wipe_ok not in (0, 1):
                raise ProbeError(
                    f"noncanonical readiness values: complete={complete} wipe_ok={wipe_ok}"
                )
            if time.monotonic() >= deadline:
                raise ProbeError(
                    f"probe readiness timeout: complete={complete} wipe_ok={wipe_ok}"
                )
            time.sleep(args.poll_interval)
        for name, field in FIELDS.items():
            if name in ready_names:
                continue
            raw[name] = dump_field(
                m65, args.device, field, addresses[name], out_dir,
                args.prefix, False,
            )
    soft_window = dump_range(
        m65, args.device, "runtime-soft-canary", soft_floor,
        SOFT_STACK_TOP - soft_floor, out_dir, args.prefix, args.dry_run,
    )
    page1 = dump_range(
        m65, args.device, "boot-page1-canary", 0x0100, 256,
        out_dir, args.prefix, args.dry_run,
    )
    annex_before_raw: bytes | None = None
    annex_after_raw: bytes | None = None
    if annex_present:
        annex_before_raw = dump_range(
            m65, args.device, "rootstack-annex-canary-before",
            addresses["annex_before"], 2, out_dir, args.prefix, args.dry_run,
        )
        annex_after_raw = dump_range(
            m65, args.device, "rootstack-annex-canary-after",
            addresses["annex_after"], 2, out_dir, args.prefix, args.dry_run,
        )
    report = out_dir / f"{args.prefix}.txt"
    if args.dry_run:
        lines = report_lines(
            elf, args.device, True, args.min_soft_margin,
            args.min_hw_remaining, None, (), annex_present=annex_present,
        )
        report.write_text("\n".join(lines) + "\n", encoding="ascii")
        print(f"hw-stack-probe: dry-run, decode skipped; wrote {report}")
        return 0

    values = derive_low_water(decode(raw), soft_floor, soft_window, page1)
    errors = evaluate(values, args.min_soft_margin, args.min_hw_remaining)
    annex_before = (
        int.from_bytes(annex_before_raw, "little") if annex_before_raw is not None else None
    )
    annex_after = (
        int.from_bytes(annex_after_raw, "little") if annex_after_raw is not None else None
    )
    errors.extend(evaluate_annex(annex_before, annex_after))
    lines = report_lines(
        elf, args.device, False, args.min_soft_margin,
        args.min_hw_remaining, values, errors, annex_before, annex_after,
        annex_present,
    )
    report.write_text("\n".join(lines) + "\n", encoding="ascii")
    print(
        "hw-stack-probe: "
        f"soft_margin={values['soft_margin']} hw_remaining={values['hw_remaining']} "
        f"flags=0x{values['flags']:02x} wipe_ok={values['wipe_ok']} "
        f"annex_canaries={'checked' if annex_present else 'unavailable'} "
        f"status={'FAIL' if errors else 'PASS'}"
    )
    print(f"wrote {report}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.selftest:
        return selftest()
    try:
        return run(args)
    except ProbeError as exc:
        print(f"hw-stack-probe-readback: ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
