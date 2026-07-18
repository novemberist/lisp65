#!/usr/bin/env python3
"""Execute and verify the v1.1 Workbench REPL banner in the P0 VM."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import bytecode_p0 as B
import bytecode_p0_stdlib as S


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUITE = ROOT / "build/bytecode/dialect-v2/suites/p0-stdlib-einsuite-core-workbench-subset.json"
DEFAULT_SOURCE = ROOT / "build/bytecode/dialect-v2/sources/lib/repl-banner.lisp"
RUN_STREAM = "&AC'BC(CC)DC*EC+FC(DJ&EK%FK3AS3BS3CS3DS3ES3FW;AU<BS<CS<DS<ES;FUAAWABSACWEDSEESAFWIAWIBSMBSICWIDSIESIFSQAWQBSQCWQDSUDSQESUESQFWYAWYBSYCW]DS]ESYFW%GY"
SUBTITLE = "WORKBENCH - DIALECT V2"
SCREEN_BASE = 0x0800
SCREEN_COLUMNS = 80
SEPARATOR_ROW = 6
SEPARATOR_START = 1
SEPARATOR_LENGTH = 66
SEPARATOR_CODE = 64


class BannerError(RuntimeError):
    pass


class ObservingVM(B.P0VM):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.screen_writes: list[tuple[int, int, int, int]] = []
        self.screen_put_calls = 0
        self.screen_span_calls = 0
        self.output_codes: list[int] = []
        self.poke_writes: list[tuple[int, int]] = []

    def _callprim(self, prim_id, argc, stack, **kwargs):
        raw_args = list(stack[-argc:]) if argc else []
        result = super()._callprim(prim_id, argc, stack, **kwargs)
        if prim_id == 11:
            self.screen_put_calls += 1
            values = tuple(B.fixval(arg) for arg in raw_args)
            attr = values[3] if argc == 4 else 0
            self.screen_writes.append((values[0], values[1], values[2], attr))
        elif prim_id == 12:
            self.screen_span_calls += 1
            x, y = (B.fixval(arg) for arg in raw_args[:2])
            text = self.heap.string_to_text(raw_args[2])
            attr = B.fixval(raw_args[3]) if argc == 4 else 0
            self.screen_writes.extend(
                (x + index, y, ord(char), attr) for index, char in enumerate(text)
            )
        elif prim_id == 45:
            self.output_codes.append(B.fixval(raw_args[0]))
        elif prim_id == 62:
            hi, lo, value = (B.fixval(arg) for arg in raw_args)
            self.poke_writes.append(((hi << 8) | lo, value))
        return result


def expected_screen_writes() -> list[tuple[int, int, int, int]]:
    writes: list[tuple[int, int, int, int]] = []
    for offset in range(0, len(RUN_STREAM), 3):
        x = ord(RUN_STREAM[offset]) - 36
        y = ord(RUN_STREAM[offset + 1]) - 65
        tag = ord(RUN_STREAM[offset + 2]) - 65
        kind, length = divmod(tag, 8)
        if kind == 3:
            writes.extend(
                (column, SEPARATOR_ROW, 32, 15)
                for column in range(SEPARATOR_START, SEPARATOR_START + SEPARATOR_LENGTH)
            )
            continue
        code = 32
        attr = 135 if kind < 2 else 129
        writes.extend((x + cell, y, code, attr) for cell in range(length))
    writes.extend(
        (44 + index, 7, ord(char), 15) for index, char in enumerate(SUBTITLE)
    )
    return writes


def expected_pokes() -> list[tuple[int, int]]:
    writes: list[tuple[int, int]] = []
    for offset in range(0, len(RUN_STREAM), 3):
        x = ord(RUN_STREAM[offset]) - 36
        y = ord(RUN_STREAM[offset + 1]) - 65
        tag = ord(RUN_STREAM[offset + 2]) - 65
        kind, length = divmod(tag, 8)
        if kind == 3:
            first = SCREEN_BASE + SEPARATOR_ROW * SCREEN_COLUMNS + SEPARATOR_START
            writes.extend(
                (first + index, SEPARATOR_CODE)
                for index in range(SEPARATOR_LENGTH)
            )
    return writes


def validate_observation(
    result: int,
    screen_writes: list[tuple[int, int, int, int]],
    screen_put_calls: int,
    screen_span_calls: int,
    output_codes: list[int],
    poke_writes: list[tuple[int, int]],
) -> None:
    if result != B.NIL:
        raise BannerError("banner result is not nil")
    expected_writes = expected_screen_writes()
    if screen_writes != expected_writes:
        raise BannerError(
            f"screen-write mismatch: expected {len(expected_writes)}, got {len(screen_writes)}"
        )
    if screen_put_calls != 235 or screen_span_calls != 0:
        raise BannerError(
            f"screen call shape drift: put={screen_put_calls}, span={screen_span_calls}"
        )
    if output_codes != [10] * 9:
        raise BannerError(f"prompt advance mismatch: {output_codes!r}")
    if poke_writes != expected_pokes():
        raise BannerError("raw banner poke sequence mismatch")


def observe(suite_path: Path) -> tuple[dict, ObservingVM]:
    suite = S._read_suite(str(suite_path))
    (
        heap,
        _names,
        _code_by_name,
        entry_flags,
        resident_entry_flags,
        _bundle,
        directory,
        _cases,
        _entry_names,
        _inliner,
    ) = S._compile_suite(suite, include_cases=False)
    macro_symbols = S._macro_symbol_objs(heap, entry_flags, resident_entry_flags)
    abi_profile, abi_ledger = S._suite_abi(suite)
    vm = ObservingVM(
        heap=heap,
        directory=directory,
        macro_symbols=macro_symbols,
        abi_profile=abi_profile,
        abi_ledger=abi_ledger,
    )
    entry = heap.intern("%repl-banner")
    if entry not in directory:
        raise BannerError("generated suite does not deliver %repl-banner")
    result = vm.run(directory[entry], [])
    validate_observation(
        result,
        vm.screen_writes,
        vm.screen_put_calls,
        vm.screen_span_calls,
        vm.output_codes,
        vm.poke_writes,
    )
    report = {
        "format": "lisp65-v11-repl-banner-visual-oracle-v1",
        "status": "pass",
        "entry": "%repl-banner",
        "suite": suite_path.relative_to(ROOT).as_posix(),
        "suite_sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
        "source": DEFAULT_SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": hashlib.sha256(DEFAULT_SOURCE.read_bytes()).hexdigest(),
        "screen_writes": len(vm.screen_writes),
        "screen_put_char_calls": vm.screen_put_calls,
        "screen_write_string_calls": vm.screen_span_calls,
        "lambda_and_block_writes": len(vm.screen_writes) - SEPARATOR_LENGTH - len(SUBTITLE),
        "separator_writes": SEPARATOR_LENGTH,
        "subtitle_writes": len(SUBTITLE),
        "cursor_linefeeds": len(vm.output_codes),
        "first_prompt_row": 9,
        "separator_screen_base": f"0x{expected_pokes()[0][0]:04x}",
        "separator_screen_end": f"0x{expected_pokes()[-1][0]:04x}",
        "separator_screen_code": SEPARATOR_CODE,
        "steps": vm.steps,
        "claim_limit": "Host P0 execution oracle; real-hardware appearance remains a wave-seal condition.",
    }
    return report, vm


def selftest() -> None:
    writes = expected_screen_writes()
    pokes = expected_pokes()
    valid = (B.NIL, writes, 235, 0, [10] * 9, pokes)
    validate_observation(*valid)
    mutations = [
        (B.NIL, [(writes[0][0] + 1,) + writes[0][1:]] + writes[1:], 235, 0, [10] * 9, pokes),
        (B.NIL, writes, 234, 0, [10] * 9, pokes),
        (B.NIL, writes, 235, 0, [10] * 8, pokes),
        (B.NIL, writes, 235, 0, [10] * 9, pokes[:-1] + [(pokes[-1][0], 63)]),
        (1, writes, 235, 0, [10] * 9, pokes),
    ]
    for index, mutation in enumerate(mutations, 1):
        try:
            validate_observation(*mutation)
        except BannerError:
            continue
        raise AssertionError(f"mutation {index} was accepted")
    print(f"v11-repl-banner-visual: SELFTEST PASS mutations={len(mutations)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            selftest()
            if args.json_out is None:
                return 0
        report, _vm = observe(args.suite.resolve())
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(
            "v11-repl-banner-visual: PASS "
            f"writes={report['screen_writes']} prompt_row={report['first_prompt_row']} "
            f"steps={report['steps']}"
        )
        return 0
    except (BannerError, OSError, ValueError, AssertionError) as error:
        print(f"v11-repl-banner-visual: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
