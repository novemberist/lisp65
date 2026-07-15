#!/usr/bin/env python3
"""Run the native C reader against the normative MVP fixture and boundaries."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from reader_fixture import FixtureError, load_fixture


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DRIVER = ROOT / "build" / "reader-conformance-host"
DEFAULT_FIXTURE = ROOT / "lib" / "tests" / "mvp-reader-cases.json"


@dataclass(frozen=True)
class NativeCase:
    name: str
    source: str
    value: str | None = None
    error: str | None = None
    status: str = "ok"
    offset: int | None = None


class HarnessFailure(RuntimeError):
    pass


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver", type=Path, default=DEFAULT_DRIVER)
    parser.add_argument("--root-driver", type=Path)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--timeout", type=float, default=3.0)
    return parser.parse_args(argv)


def sanitizer_environment() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("ASAN_OPTIONS", "detect_leaks=0:halt_on_error=1:abort_on_error=1")
    env.setdefault("UBSAN_OPTIONS", "halt_on_error=1:print_stacktrace=1")
    return env


def invoke(driver: Path, source: str, timeout: float) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [str(driver)],
            input=source,
            text=True,
            capture_output=True,
            cwd=ROOT,
            env=sanitizer_environment(),
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HarnessFailure(f"native driver timed out after {timeout:g}s") from exc
    except OSError as exc:
        raise HarnessFailure(f"cannot execute {driver}: {exc}") from exc

    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "no diagnostic"
        raise HarnessFailure(f"native driver exited {proc.returncode}: {detail}")
    lines = proc.stdout.splitlines()
    if len(lines) != 1:
        raise HarnessFailure(f"native driver returned {len(lines)} protocol lines: {proc.stdout!r}")
    try:
        result = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        raise HarnessFailure(f"invalid native driver JSON: {lines[0]!r}") from exc
    required = {
        "status",
        "status_code",
        "error",
        "error_code",
        "message",
        "offset",
        "value",
    }
    if not isinstance(result, dict):
        raise HarnessFailure(f"native driver result is not an object: {result!r}")
    if set(result) != required:
        raise HarnessFailure(f"native driver protocol keys differ: {sorted(result)}")
    if result["status"] not in {"ok", "eof", "error"}:
        raise HarnessFailure(f"unknown reader status: {result['status']!r}")
    if not isinstance(result["error"], str) or not isinstance(result["message"], str):
        raise HarnessFailure("reader error name/message must be strings")
    if not isinstance(result["offset"], int) or not 0 <= result["offset"] <= len(source):
        raise HarnessFailure(f"invalid reader offset: {result['offset']!r}")
    if not isinstance(result["status_code"], int) or not isinstance(result["error_code"], int):
        raise HarnessFailure("reader status/error codes must be integers")
    return result


def tail_is_ignorable(source: str, offset: int) -> bool:
    pos = offset
    while pos < len(source):
        if source[pos].isspace():
            pos += 1
        elif source[pos] == ";":
            newline = source.find("\n", pos)
            pos = len(source) if newline < 0 else newline + 1
        else:
            return False
    return True


def check_case(driver: Path, case: NativeCase, timeout: float) -> None:
    result = invoke(driver, case.source, timeout)
    if result["status"] != case.status:
        raise HarnessFailure(
            f"{case.name}: status={result['status']!r}, expected {case.status!r}; "
            f"error={result['error']!r} message={result['message']!r}"
        )
    if case.offset is not None and result["offset"] != case.offset:
        raise HarnessFailure(
            f"{case.name}: offset={result['offset']}, expected {case.offset}"
        )
    if case.status == "ok":
        if result["error"] != "none" or result["error_code"] != 0:
            raise HarnessFailure(f"{case.name}: successful read retained error {result['error']!r}")
        if result["value"] != case.value:
            raise HarnessFailure(
                f"{case.name}: value={result['value']!r}, expected {case.value!r}"
            )
        if not tail_is_ignorable(case.source, result["offset"]):
            tail = case.source[result["offset"] :]
            raise HarnessFailure(f"{case.name}: unconsumed non-comment input {tail!r}")
    elif case.status == "eof":
        if result["value"] is not None or result["error"] != "none":
            raise HarnessFailure(f"{case.name}: EOF carried a value/error: {result!r}")
    else:
        if result["value"] is not None or result["error"] == "none":
            raise HarnessFailure(f"{case.name}: error status without a concrete error: {result!r}")
        if case.error is not None and result["error"] != case.error:
            raise HarnessFailure(
                f"{case.name}: error={result['error']!r}, expected {case.error!r}"
            )


def fixture_cases(path: Path) -> list[NativeCase]:
    raw_cases = load_fixture(path)
    cases: list[NativeCase] = []
    fixture_errors = {
        "reject-unclosed-list": "unclosed-list",
        "reject-extra-after-dotted-tail": "expected-rparen",
        "reject-unclosed-string": "unclosed-string",
    }
    for item in raw_cases:
        if "error" in item:
            cases.append(
                NativeCase(
                    name=f"fixture/{item['name']}",
                    source=item["input"],
                    status="error",
                    error=fixture_errors.get(item["name"]),
                )
            )
        else:
            cases.append(
                NativeCase(
                    name=f"fixture/{item['name']}",
                    source=item["input"],
                    value=item["expect"],
                )
            )
    return cases


def boundary_cases() -> list[NativeCase]:
    symbol32 = "a" * 32
    symbol33 = symbol32 + "b"
    symbol34 = symbol33 + "c"
    long_string_body = 'Abc \\"quoted\\" ' * 64
    return [
        NativeCase("eof/empty", "", status="eof"),
        NativeCase("eof/whitespace", " \t\r\n", status="eof"),
        NativeCase("eof/comment", "; only a comment", status="eof"),
        NativeCase("fixnum/min", "-16384", value="-16384"),
        NativeCase("fixnum/max", "+16383", value="16383"),
        NativeCase("fixnum/negative-overflow", "-16385", status="error", error="fixnum-range"),
        NativeCase("fixnum/positive-overflow", "16384", status="error", error="fixnum-range"),
        NativeCase("symbol/mixed-case", "MiXeD-Case", value="MIXED-CASE"),
        NativeCase("token/max-symbol", symbol32, value=symbol32.upper()),
        NativeCase("token/max-symbol-33", symbol33, value=symbol33.upper()),
        NativeCase(
            "token/too-long",
            symbol34,
            status="error",
            error="token-too-long",
            offset=len(symbol34),
        ),
        NativeCase(
            "token/too-long-consumed",
            symbol34 + " next",
            status="error",
            error="token-too-long",
            offset=len(symbol34),
        ),
        NativeCase("syntax/unexpected-rparen", ")", status="error", error="unexpected-rparen"),
        NativeCase("syntax/dot-outside-list", ".", status="error", error="dot-without-head"),
        NativeCase("syntax/dot-without-head", "(. a)", status="error", error="dot-without-head"),
        NativeCase("syntax/dotted-tail-missing", "(a .)", status="error"),
        NativeCase("syntax/dotted-tail-unclosed", "(a . b", status="error", error="expected-rparen"),
        NativeCase("syntax/dotted-tail-extra", "(a . b c)", status="error", error="expected-rparen"),
        NativeCase("syntax/sugar-eof", "'", status="error", error="unexpected-eof"),
        NativeCase("syntax/function-sugar-eof", "#'", status="error", error="unexpected-eof"),
        NativeCase("syntax/unquote-eof", ",", status="error", error="unexpected-eof"),
        NativeCase("syntax/unquote-splicing-eof", ",@", status="error", error="unexpected-eof"),
        NativeCase("string/empty", '""', value='""'),
        NativeCase("string/backslash", '"a\\\\b"', value='"a\\\\b"'),
        NativeCase("string/unfinished-escape", '"abc\\', status="error", error="unfinished-escape"),
        NativeCase(
            "string/long-with-escapes",
            '"' + long_string_body + '"',
            value='"' + long_string_body + '"',
        ),
    ]


def eof_prefix_cases() -> list[NativeCase]:
    samples = {
        "list": "(alpha (beta . gamma))",
        "string": '"say \\"hi\\""',
        "quote": "'(alpha beta)",
    }
    cases: list[NativeCase] = []
    for sample_name, source in samples.items():
        for end in range(1, len(source)):
            prefix = source[:end]
            if sample_name == "string" and prefix == '"say \\"hi\\"':
                expected_error = "unclosed-string"
            else:
                expected_error = None
            cases.append(
                NativeCase(
                    name=f"eof-prefix/{sample_name}/{end}",
                    source=prefix,
                    status="error",
                    error=expected_error,
                )
            )
    return cases


def nested_source(depth: int) -> str:
    return "(" * depth + "nil" + ")" * depth


def check_depths(driver: Path, timeout: float) -> int:
    depths = (1, 8, 32, 64, 128, 256, 512, 1000)
    rejected = False
    count = 0
    last: dict[str, Any] | None = None
    for depth in depths:
        source = nested_source(depth)
        result = invoke(driver, source, timeout)
        last = result
        count += 1
        if result["status"] == "ok":
            if rejected:
                raise HarnessFailure(f"depth/{depth}: reader accepted input after its depth limit")
            expected = "(" * depth + "NIL" + ")" * depth
            if result["value"] != expected:
                raise HarnessFailure(f"depth/{depth}: malformed canonical value")
            if not tail_is_ignorable(source, result["offset"]):
                raise HarnessFailure(f"depth/{depth}: native reader did not consume the full form")
        elif result["status"] == "error" and result["error"] in {"too-deep", "root-overflow"}:
            rejected = True
        else:
            raise HarnessFailure(
                f"depth/{depth}: expected success or guarded depth error, got {result!r}"
            )
    if not rejected:
        raise HarnessFailure("depth/1000: native reader did not enforce a depth/root limit")
    if last is None or last["status"] != "error" or last["error"] != "too-deep":
        raise HarnessFailure(f"depth/1000: expected too-deep, got {last!r}")
    return count


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    driver = args.driver.resolve()
    fixture = args.fixture.resolve()
    if not driver.is_file():
        print(f"native-reader-conformance: FAIL: missing driver {driver}", file=sys.stderr)
        return 2

    passed = 0
    try:
        groups = [fixture_cases(fixture), boundary_cases(), eof_prefix_cases()]
        for cases in groups:
            for case in cases:
                check_case(driver, case, args.timeout)
                passed += 1
        passed += check_depths(driver, args.timeout)
        if args.root_driver is not None:
            check_case(
                args.root_driver.resolve(),
                NativeCase(
                    "root-guard/exhausted",
                    "(((nil)))",
                    status="error",
                    error="root-overflow",
                ),
                args.timeout,
            )
            passed += 1
    except FixtureError as exc:
        print(f"native-reader-conformance: FIXTURE ERROR: {exc}", file=sys.stderr)
        return 2
    except (HarnessFailure, KeyError, TypeError, ValueError) as exc:
        print(f"native-reader-conformance: FAIL after {passed} cases: {exc}", file=sys.stderr)
        return 1

    print(f"native-reader-conformance: PASS cases={passed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
