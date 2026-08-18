#!/usr/bin/env python3
"""Validate the latest form echo and result in a Lisp65 text screenshot."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import tempfile

from PIL import Image


RESULT_MISMATCH = 4
ECHO_MISMATCH = 5
SCREEN_MALFORMED = 6
FAIL_CLOSED_FRAME = 7
PROMPT = "lisp65> "
SCREEN_WIDTH = 80
EDITOR_STATUS_TAIL = re.compile(
    r"-- [A-Za-z0-9._-]+ \* L[0-9]+ -- [0-9]+/[0-9]+"
)


@dataclass(frozen=True)
class CheckError(Exception):
    code: int
    message: str


def check_fail_closed_frame(image_path: Path) -> None:
    try:
        with Image.open(image_path) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            samples = (
                rgb.getpixel((0, 0)),
                rgb.getpixel((width - 1, 0)),
                rgb.getpixel((0, height - 1)),
                rgb.getpixel((width - 1, height - 1)),
            )
    except OSError as error:
        raise CheckError(
            SCREEN_MALFORMED,
            f"cannot read screenshot image {image_path}: {error}",
        ) from error
    if all(red >= 240 and green <= 16 and blue <= 16
           for red, green, blue in samples):
        raise CheckError(
            FAIL_CLOSED_FRAME,
            "red fail-closed frame is visible",
        )


def _screen_content(raw_line: str) -> str:
    line = raw_line.rstrip("\r")
    if len(line) == SCREEN_WIDTH + 2 and line.startswith(" ") and line.endswith(" "):
        return line[1:-1]
    return line


def _last_form(path: Path) -> str:
    try:
        raw_forms = path.read_text(errors="replace")
    except OSError as error:
        raise CheckError(SCREEN_MALFORMED, f"cannot read forms {path}: {error}") from error
    forms = [line for line in raw_forms.splitlines() if line and not line.startswith((";", "#"))]
    if not forms:
        raise CheckError(SCREEN_MALFORMED, f"no REPL forms in {path}")
    return forms[-1]


def _reconstruct_echo(lines: list[str], form_start: int, expected_form: str) -> tuple[str, int]:
    prompt_line = lines[form_start].lstrip()
    if not prompt_line.startswith(PROMPT):
        raise CheckError(SCREEN_MALFORMED, "prompt has no submitted form")

    echo_rows = max(1, (len(PROMPT) + len(expected_form) + SCREEN_WIDTH - 1) // SCREEN_WIDTH)
    if form_start + echo_rows > len(lines):
        raise CheckError(SCREEN_MALFORMED, "form echo is not fully visible")

    parts: list[str] = []
    consumed = 0
    for row_offset in range(echo_rows):
        if row_offset == 0:
            row = prompt_line[len(PROMPT) :]
            capacity = SCREEN_WIDTH - len(PROMPT)
        else:
            row = lines[form_start + row_offset]
            capacity = SCREEN_WIDTH
        width = min(capacity, len(expected_form) - consumed)
        parts.append(row[:width])
        if width < capacity and row[width:].strip():
            parts.append(row[width:].rstrip())
        consumed += width
    return "".join(parts), echo_rows


def _reject_unless_editor_status_tail(
    trailing: list[str], *, allow_editor_status_tail: bool,
    context: str,
) -> None:
    if not trailing:
        return
    if (
        allow_editor_status_tail
        and all(EDITOR_STATUS_TAIL.fullmatch(line) for line in trailing)
    ):
        return
    raise CheckError(
        SCREEN_MALFORMED,
        f"non-empty screen content follows the {context}: "
        + " | ".join(trailing),
    )


def _latest_visible_results(
    screen_path: Path, expected_form: str,
    *, allow_editor_status_tail: bool = False,
) -> list[str]:
    try:
        raw_screen = screen_path.read_text(errors="replace")
    except OSError as error:
        raise CheckError(SCREEN_MALFORMED, f"cannot read screen {screen_path}: {error}") from error
    lines = [_screen_content(line) for line in raw_screen.splitlines()]
    prompts = [index for index, line in enumerate(lines) if line.lstrip().startswith("lisp65>")]
    if len(prompts) < 2:
        raise CheckError(SCREEN_MALFORMED, "latest REPL form/result segment is not visible")

    form_start, result_end = prompts[-2], prompts[-1]
    if lines[result_end].strip() != PROMPT.rstrip():
        raise CheckError(SCREEN_MALFORMED, "trailing REPL prompt is not empty")
    trailing = [line.strip() for line in lines[result_end + 1 :] if line.strip()]
    _reject_unless_editor_status_tail(
        trailing,
        allow_editor_status_tail=allow_editor_status_tail,
        context="trailing REPL prompt",
    )
    prompt_line = lines[form_start].lstrip()
    if not prompt_line.startswith(PROMPT):
        raise CheckError(SCREEN_MALFORMED, "penultimate prompt has no submitted form")

    actual_form, echo_rows = _reconstruct_echo(lines, form_start, expected_form)
    if form_start + echo_rows > result_end:
        raise CheckError(SCREEN_MALFORMED, "submitted form echo overlaps the trailing prompt")

    if actual_form != expected_form:
        raise CheckError(
            ECHO_MISMATCH,
            f"latest form echo differs: expected={expected_form!r} actual={actual_form!r}",
        )

    result_lines = lines[form_start + echo_rows : result_end]
    if (len(PROMPT) + len(expected_form)) % SCREEN_WIDTH == 0:
        if not result_lines or result_lines[0].strip():
            raise CheckError(ECHO_MISMATCH, "full-width form echo has no empty wrap row")
        result_lines = result_lines[1:]

    visible_results = [line.strip() for line in result_lines if line.strip()]
    if not visible_results:
        raise CheckError(SCREEN_MALFORMED, "latest REPL form has no visible result")
    if any(line.startswith("*** ") for line in visible_results):
        visible = " | ".join(visible_results)
        raise CheckError(RESULT_MISMATCH, f"latest REPL form reported an error: {visible}")
    return visible_results


def check_latest_result(
    screen_path: Path, expected_form: str, expect: str | None,
    *, allow_editor_status_tail: bool = False,
) -> None:
    visible_results = _latest_visible_results(
        screen_path,
        expected_form,
        allow_editor_status_tail=allow_editor_status_tail,
    )
    if expect is None:
        return

    if not visible_results or visible_results[-1] != expect:
        visible = " | ".join(visible_results)
        raise CheckError(
            RESULT_MISMATCH,
            f"latest result is not exactly {expect!r}: {visible or '<empty>'}",
        )


def check_latest_forbidden(
    screen_path: Path, expected_form: str, forbidden: list[str],
    *, allow_editor_status_tail: bool = False,
) -> None:
    """Reject forbidden text only in the latest form/result segment.

    Earlier output can legitimately remain visible on a 25-row screen.  A
    whole-screen negative search therefore confuses historical output with a
    side effect of the latest submitted form.
    """
    visible_results = _latest_visible_results(
        screen_path,
        expected_form,
        allow_editor_status_tail=allow_editor_status_tail,
    )
    escaped = [
        token for token in forbidden
        if any(token in line for line in visible_results)
    ]
    if escaped:
        raise CheckError(
            RESULT_MISMATCH,
            "latest result contains forbidden text: " + ", ".join(escaped),
        )


def check_active_input(
    screen_path: Path, expected_form: str,
    *, allow_editor_status_tail: bool = False,
) -> None:
    try:
        raw_screen = screen_path.read_text(errors="replace")
    except OSError as error:
        raise CheckError(SCREEN_MALFORMED, f"cannot read screen {screen_path}: {error}") from error
    lines = [_screen_content(line) for line in raw_screen.splitlines()]
    prompts = [index for index, line in enumerate(lines) if line.lstrip().startswith("lisp65>")]
    if not prompts:
        raise CheckError(SCREEN_MALFORMED, "active REPL prompt is not visible")

    form_start = prompts[-1]
    prompt_line = lines[form_start].lstrip()
    if not prompt_line.startswith(PROMPT):
        raise CheckError(SCREEN_MALFORMED, "active prompt has no input area")

    actual_form, echo_rows = _reconstruct_echo(lines, form_start, expected_form)
    if actual_form != expected_form:
        raise CheckError(
            ECHO_MISMATCH,
            f"active form echo differs: expected={expected_form!r} actual={actual_form!r}",
        )
    if (len(PROMPT) + len(expected_form)) % SCREEN_WIDTH == 0:
        wrap_index = form_start + echo_rows
        if wrap_index >= len(lines) or lines[wrap_index].strip():
            raise CheckError(ECHO_MISMATCH, "full-width active form echo has no empty wrap row")
        echo_rows += 1
    trailing = [line.strip() for line in lines[form_start + echo_rows :] if line.strip()]
    _reject_unless_editor_status_tail(
        trailing,
        allow_editor_status_tail=allow_editor_status_tail,
        context="active REPL input",
    )


def _frame(lines: list[str]) -> str:
    return "\n".join(f" {line:<80.80} " for line in lines) + "\n"


def selftest() -> None:
    cases = [
        (
            "short-pass",
            ["lisp65> (+ 20 22)", "42", "lisp65>"],
            "(+ 20 22)",
            "42",
            0,
        ),
        (
            "banner-prefix-pass",
            [
                "lambda row 0",
                "lambda row 1",
                "lambda row 2",
                "lambda row 3",
                "lambda row 4",
                "lambda row 5",
                "separator row 6",
                "WORKBENCH - DIALECT V2",
                "",
                "lisp65> (+ 20 22)",
                "42",
                "lisp65>",
            ],
            "(+ 20 22)",
            "42",
            0,
        ),
        (
            "wrapped-pass",
            [
                "lisp65> " + "x" * 72,
                "x" * 18,
                "(wrapped ok)",
                "lisp65>",
            ],
            "x" * 90,
            "(wrapped ok)",
            0,
        ),
        (
            "exact-width-pass",
            ["lisp65> " + "x" * 72, "", "ok", "lisp65>"],
            "x" * 72,
            "ok",
            0,
        ),
        (
            "exact-width-extra-echo-fails",
            ["lisp65> " + "x" * 72, "X", "ok", "lisp65>"],
            "x" * 72,
            "ok",
            ECHO_MISMATCH,
        ),
        (
            "stale-marker-fails",
            [
                "lisp65> (+ 20 22)",
                "42",
                "lisp65>",
                "lisp65> (+ 20 23)",
                "43",
                "lisp65>",
            ],
            "(+ 20 23)",
            "42",
            RESULT_MISMATCH,
        ),
        (
            "input-marker-fails",
            ["lisp65> (quote expected-marker)", "wrong", "lisp65>"],
            "(quote expected-marker)",
            "expected-marker",
            RESULT_MISMATCH,
        ),
        (
            "basic-ready-syntax-echo-fails",
            [
                "ready.",
                '(if t "expected-marker" "wrong")',
                "",
                "?syntax error",
                "ready.",
            ],
            '(if t "expected-marker" "wrong")',
            '"expected-marker"',
            SCREEN_MALFORMED,
        ),
        (
            "stale-lisp-before-basic-fails",
            [
                'lisp65> (if t "expected-marker" "wrong")',
                '"expected-marker"',
                "lisp65>",
                "ready.",
                '(if t "expected-marker" "wrong")',
                "?syntax error",
                "ready.",
            ],
            '(if t "expected-marker" "wrong")',
            '"expected-marker"',
            SCREEN_MALFORMED,
        ),
        (
            "echo-loss-fails",
            ["lisp65> (+ 2022)", "2022", "lisp65>"],
            "(+ 20 22)",
            "42",
            ECHO_MISMATCH,
        ),
        (
            "malformed-fails",
            ["lisp65> (+ 20 22)", "42"],
            "(+ 20 22)",
            "42",
            SCREEN_MALFORMED,
        ),
        (
            "setup-runtime-error-fails",
            ["lisp65> (broken-setup)", "*** undefined function: broken-setup", "lisp65>"],
            "(broken-setup)",
            None,
            RESULT_MISMATCH,
        ),
    ]
    with tempfile.TemporaryDirectory(prefix="lisp65-repl-screen-") as raw_tmp:
        tmp = Path(raw_tmp)
        normal_image = tmp / "normal.png"
        fail_closed_image = tmp / "fail-closed.png"
        Image.new("RGB", (8, 8), (0, 0, 0)).save(normal_image)
        Image.new("RGB", (8, 8), (255, 0, 0)).save(fail_closed_image)
        check_fail_closed_frame(normal_image)
        try:
            check_fail_closed_frame(fail_closed_image)
        except CheckError as error:
            if error.code != FAIL_CLOSED_FRAME:
                raise AssertionError(
                    "fail-closed image returned the wrong status"
                ) from error
        else:
            raise AssertionError("fail-closed image survived")
        for name, lines, form, expect, expected_code in cases:
            screen = tmp / f"{name}.txt"
            forms = tmp / f"{name}.forms"
            screen.write_text(_frame(lines))
            forms.write_text(form + "\n")
            actual_code = 0
            try:
                check_latest_result(screen, _last_form(forms), expect)
            except CheckError as error:
                actual_code = error.code
            if actual_code != expected_code:
                raise AssertionError(f"{name}: expected rc={expected_code}, got rc={actual_code}")

        historical_trace = tmp / "historical-trace-before-restored-call.txt"
        historical_trace.write_text(_frame([
            "lisp65> (trace-probe 4)",
            "(trace-enter trace-probe 4)",
            "(trace-exit trace-probe 5)",
            "5",
            "lisp65> (untrace trace-probe)",
            "trace-probe",
            "lisp65> (trace-probe 4)",
            "5",
            "lisp65>",
        ]))
        check_latest_forbidden(
            historical_trace,
            "(trace-probe 4)",
            ["trace-enter", "trace-exit"],
        )
        current_trace = tmp / "current-trace-after-restored-call.txt"
        current_trace.write_text(_frame([
            "lisp65> (trace-probe 4)",
            "(trace-enter trace-probe 4)",
            "5",
            "lisp65>",
        ]))
        try:
            check_latest_forbidden(
                current_trace,
                "(trace-probe 4)",
                ["trace-enter", "trace-exit"],
            )
        except CheckError as error:
            if error.code != RESULT_MISMATCH:
                raise AssertionError(
                    "current forbidden trace returned the wrong status"
                ) from error
        else:
            raise AssertionError("current forbidden trace survived")

        active_cases = [
            ("active-pass", ["lisp65> (+ 20 22)"], "(+ 20 22)", 0),
            (
                "active-wrapped-pass",
                ["lisp65> " + "x" * 72, "x" * 18],
                "x" * 90,
                0,
            ),
            (
                "active-significant-wrap-space-pass",
                [
                    'lisp65> (setq y (ide-make-state (ide-set-point (ide-make-buffer "scratch" (list ',
                    '"ab cd")) 0 5)))',
                ],
                '(setq y (ide-make-state (ide-set-point (ide-make-buffer "scratch" (list "ab cd")) 0 5)))',
                0,
            ),
            ("active-exact-width-pass", ["lisp65> " + "x" * 72, ""], "x" * 72, 0),
            (
                "active-exact-width-extra-fails",
                ["lisp65> " + "x" * 72, "X"],
                "x" * 72,
                ECHO_MISMATCH,
            ),
            ("active-loss-fails", ["lisp65> (+ 2022)"], "(+ 20 22)", ECHO_MISMATCH),
            (
                "active-stale-lisp-before-basic-fails",
                [
                    "lisp65> (+ 20 22)",
                    "ready.",
                    "(+ 20 22)",
                    "?syntax error",
                    "ready.",
                ],
                "(+ 20 22)",
                SCREEN_MALFORMED,
            ),
        ]
        for name, lines, form, expected_code in active_cases:
            screen = tmp / f"{name}.txt"
            screen.write_text(_frame(lines))
            actual_code = 0
            try:
                check_active_input(screen, form)
            except CheckError as error:
                actual_code = error.code
            if actual_code != expected_code:
                raise AssertionError(f"{name}: expected rc={expected_code}, got rc={actual_code}")

        editor_tail = "-- scratch * L1 -- 626/752"
        result_tail = tmp / "result-editor-status-tail.txt"
        result_tail.write_text(_frame([
            "lisp65> (+ 20 22)", "42", "lisp65>", editor_tail,
        ]))
        active_tail = tmp / "active-editor-status-tail.txt"
        active_tail.write_text(_frame([
            "lisp65> (+ 20 22)", editor_tail,
        ]))

        for path, checker in (
            (
                result_tail,
                lambda allow: check_latest_result(
                    result_tail,
                    "(+ 20 22)",
                    "42",
                    allow_editor_status_tail=allow,
                ),
            ),
            (
                active_tail,
                lambda allow: check_active_input(
                    active_tail,
                    "(+ 20 22)",
                    allow_editor_status_tail=allow,
                ),
            ),
        ):
            try:
                checker(False)
            except CheckError as error:
                if error.code != SCREEN_MALFORMED:
                    raise AssertionError(
                        f"{path.name}: wrong strict status {error.code}"
                    ) from error
            else:
                raise AssertionError(f"{path.name}: strict mode accepted tail")
            checker(True)

        malformed_tail = tmp / "malformed-editor-status-tail.txt"
        malformed_tail.write_text(_frame([
            "lisp65> (+ 20 22)", "42", "lisp65>",
            "-- scratch * L1 -- 626/752 EXTRA",
        ]))
        try:
            check_latest_result(
                malformed_tail,
                "(+ 20 22)",
                "42",
                allow_editor_status_tail=True,
            )
        except CheckError as error:
            if error.code != SCREEN_MALFORMED:
                raise AssertionError(
                    "malformed editor tail returned wrong status"
                ) from error
        else:
            raise AssertionError("malformed editor tail survived")
    print(
        "repl-screen-check selftest: PASS "
        f"({len(cases) + len(active_cases) + 9} cases)"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--screen", type=Path)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--forms", type=Path)
    parser.add_argument("--form-text")
    parser.add_argument("--expect")
    parser.add_argument("--echo-only", action="store_true")
    parser.add_argument("--active-input", action="store_true")
    parser.add_argument("--allow-editor-status-tail", action="store_true")
    args = parser.parse_args()
    if not args.selftest:
        if args.screen is None:
            parser.error("--screen is required")
        if (args.forms is None) == (args.form_text is None):
            parser.error("exactly one of --forms or --form-text is required")
        if not args.echo_only and not args.active_input and args.expect is None:
            parser.error("--expect is required unless --echo-only is used")
        if args.echo_only and args.active_input:
            parser.error("--echo-only and --active-input are mutually exclusive")
    return args


def main() -> int:
    args = parse_args()
    if args.selftest:
        selftest()
        return 0
    try:
        if args.image is not None:
            check_fail_closed_frame(args.image)
        expected_form = args.form_text if args.form_text is not None else _last_form(args.forms)
        if args.active_input:
            check_active_input(
                args.screen,
                expected_form,
                allow_editor_status_tail=args.allow_editor_status_tail,
            )
        else:
            check_latest_result(
                args.screen,
                expected_form,
                None if args.echo_only else args.expect,
                allow_editor_status_tail=args.allow_editor_status_tail,
            )
    except CheckError as error:
        print(f"repl-screen-check: {error.message}")
        return error.code
    if args.active_input:
        print("repl-screen-check: PASS active-input")
    elif args.echo_only:
        print("repl-screen-check: PASS echo-only")
    else:
        print(f"repl-screen-check: PASS expect={args.expect!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
