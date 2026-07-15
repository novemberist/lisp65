#!/usr/bin/env python3
"""Run a cumulative lisp65 CI gate from an unmodified Git checkout."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Sequence


EXIT_OK = 0
EXIT_GATE_FAILED = 1
EXIT_DIRTY_BEFORE = 2
EXIT_DIRTY_AFTER = 3
EXIT_INFRASTRUCTURE = 4
EXIT_SELFTEST_FAILED = 5
EXIT_USAGE = 64

GATE_TARGETS = {
    "source": ("G0", "check-source"),
    "host": ("G1", "check-host"),
}
MAKE_COMMAND_PREFIX = ("make", "--no-print-directory")


class InfrastructureError(RuntimeError):
    """Raised when the CI wrapper cannot inspect or run the checkout."""


class CIArgumentParser(argparse.ArgumentParser):
    """Use an exit code that cannot be confused with a dirty checkout."""

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def _run_git(args: Sequence[str], cwd: Path) -> bytes:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise InfrastructureError(f"cannot run git: {exc}") from exc
    if result.returncode != 0:
        detail = os.fsdecode(result.stderr).strip() or "no diagnostic"
        raise InfrastructureError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def repo_root(cwd: Path) -> Path:
    output = _run_git(["rev-parse", "--show-toplevel"], cwd)
    root = os.fsdecode(output).strip()
    if not root:
        raise InfrastructureError("git returned an empty repository root")
    return Path(root)


def dirty_entries(root: Path) -> list[str]:
    # Ignored build products are intentionally absent; untracked, staged and
    # unstaged changes remain visible.
    output = _run_git(
        ["status", "--porcelain=v1", "-z", "--untracked-files=all"], root
    )
    return [
        os.fsdecode(entry).replace("\n", "\\n")
        for entry in output.split(b"\0")
        if entry
    ]


def _dirty_summary(entries: Sequence[str]) -> str:
    summary = ", ".join(entries[:5])
    if len(entries) > 5:
        summary += f", ... ({len(entries)} entries)"
    return summary


CommandRunner = Callable[..., subprocess.CompletedProcess[bytes]]
Emitter = Callable[[str], None]


def run_gate(
    root: Path,
    selector: str,
    *,
    command_runner: CommandRunner = subprocess.run,
    emit: Emitter = print,
) -> int:
    gate_name, target = GATE_TARGETS[selector]
    before = dirty_entries(root)
    if before:
        emit(
            "ci-gate: FAIL "
            f"phase=preflight exit={EXIT_DIRTY_BEFORE} dirty={_dirty_summary(before)}"
        )
        return EXIT_DIRTY_BEFORE

    command = [*MAKE_COMMAND_PREFIX, target]
    emit(f"ci-gate: START gate={gate_name} selector={selector} target={target}")
    launch_error: OSError | None = None
    gate_returncode: int | None = None
    try:
        result = command_runner(command, cwd=root, check=False)
        gate_returncode = result.returncode
    except OSError as exc:
        launch_error = exc

    after = dirty_entries(root)
    if after:
        gate_detail = "not-started" if gate_returncode is None else str(gate_returncode)
        emit(
            "ci-gate: FAIL "
            f"phase=postflight exit={EXIT_DIRTY_AFTER} gate_exit={gate_detail} "
            f"dirty={_dirty_summary(after)}"
        )
        return EXIT_DIRTY_AFTER

    if launch_error is not None:
        emit(
            "ci-gate: ERROR "
            f"phase=gate exit={EXIT_INFRASTRUCTURE} target={target} "
            f"detail=cannot run make: {launch_error}"
        )
        return EXIT_INFRASTRUCTURE
    if gate_returncode != 0:
        emit(
            "ci-gate: FAIL "
            f"phase=gate exit={EXIT_GATE_FAILED} target={target} "
            f"make_exit={gate_returncode}"
        )
        return EXIT_GATE_FAILED

    emit(f"ci-gate: PASS gate={gate_name} selector={selector} target={target}")
    return EXIT_OK


def _selftest_git(root: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = os.fsdecode(result.stderr).strip() or "no diagnostic"
        raise InfrastructureError(f"selftest git {' '.join(args)} failed: {detail}")


def selftest() -> int:
    if shutil.which("git") is None:
        print("ci-gate selftest: ERROR git not found", file=sys.stderr)
        return EXIT_INFRASTRUCTURE

    failures: list[str] = []
    case_count = 0

    def expect(label: str, condition: bool, detail: str) -> None:
        nonlocal case_count
        case_count += 1
        if not condition:
            failures.append(f"{label}: {detail}")

    with tempfile.TemporaryDirectory(prefix="lisp65-ci-gate-") as temp_name:
        root = Path(temp_name)
        _selftest_git(root, "init", "--quiet")
        _selftest_git(root, "config", "user.name", "CI Gate Selftest")
        _selftest_git(root, "config", "user.email", "ci-gate-selftest@example.invalid")
        (root / ".gitignore").write_text("build/\n", encoding="ascii")
        tracked = root / "tracked.txt"
        tracked.write_text("baseline\n", encoding="ascii")
        _selftest_git(root, "add", ".gitignore", "tracked.txt")
        _selftest_git(root, "commit", "--quiet", "-m", "selftest baseline")

        calls: list[tuple[tuple[str, ...], Path, bool]] = []

        def passing_runner(
            command: Sequence[str], *, cwd: Path, check: bool
        ) -> subprocess.CompletedProcess[bytes]:
            calls.append((tuple(command), cwd, check))
            return subprocess.CompletedProcess(command, 0)

        expect("clean", dirty_entries(root) == [], "baseline reported dirty")
        messages: list[str] = []
        result = run_gate(root, "source", command_runner=passing_runner, emit=messages.append)
        expect("source-result", result == EXIT_OK, f"got exit {result}")
        expect(
            "source-command",
            calls == [((*MAKE_COMMAND_PREFIX, "check-source"), root, False)],
            f"unexpected calls: {calls!r}",
        )

        calls.clear()
        (root / "build").mkdir()
        (root / "build" / "ignored.bin").write_bytes(b"ignored")
        result = run_gate(root, "host", command_runner=passing_runner, emit=messages.append)
        expect("ignored-result", result == EXIT_OK, f"got exit {result}")
        expect(
            "host-command",
            calls == [((*MAKE_COMMAND_PREFIX, "check-host"), root, False)],
            f"unexpected calls: {calls!r}",
        )

        for label, prepare in (
            ("unstaged", lambda: tracked.write_text("unstaged\n", encoding="ascii")),
            ("staged", lambda: _selftest_git(root, "add", "tracked.txt")),
            ("untracked", lambda: (root / "untracked.txt").write_text("new\n", encoding="ascii")),
        ):
            if label == "staged":
                tracked.write_text("staged\n", encoding="ascii")
            calls.clear()
            prepare()
            result = run_gate(root, "source", command_runner=passing_runner, emit=messages.append)
            expect(label, result == EXIT_DIRTY_BEFORE, f"got exit {result}")
            expect(f"{label}-no-command", not calls, f"gate ran: {calls!r}")
            _selftest_git(root, "reset", "--quiet", "HEAD", "--", "tracked.txt")
            tracked.write_text("baseline\n", encoding="ascii")
            (root / "untracked.txt").unlink(missing_ok=True)

        def failing_runner(
            command: Sequence[str], *, cwd: Path, check: bool
        ) -> subprocess.CompletedProcess[bytes]:
            return subprocess.CompletedProcess(command, 17)

        result = run_gate(root, "host", command_runner=failing_runner, emit=messages.append)
        expect("gate-failure", result == EXIT_GATE_FAILED, f"got exit {result}")

        def dirtying_runner(
            command: Sequence[str], *, cwd: Path, check: bool
        ) -> subprocess.CompletedProcess[bytes]:
            (cwd / "generated.txt").write_text("not ignored\n", encoding="ascii")
            return subprocess.CompletedProcess(command, 0)

        result = run_gate(root, "source", command_runner=dirtying_runner, emit=messages.append)
        expect("postflight-dirty", result == EXIT_DIRTY_AFTER, f"got exit {result}")
        (root / "generated.txt").unlink()

        expect(
            "gate-selectors",
            set(GATE_TARGETS) == {"source", "host"},
            f"unexpected selectors: {sorted(GATE_TARGETS)}",
        )

    for failure in failures:
        print(f"ci-gate selftest: FAIL {failure}")
    if failures:
        print(
            f"ci-gate selftest: FAIL cases={case_count} failures={len(failures)}"
        )
        return EXIT_SELFTEST_FAILED

    print(f"ci-gate selftest: PASS cases={case_count} failures=0")
    return EXIT_OK


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = CIArgumentParser(
        description="run lisp65 G0 or G1 from a clean Git checkout"
    )
    parser.add_argument(
        "gate",
        nargs="?",
        choices=tuple(GATE_TARGETS),
        help="source runs cumulative G0; host runs cumulative G1",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="test clean-tree and command contracts in temporary repositories",
    )
    args = parser.parse_args(argv)
    if args.selftest and args.gate is not None:
        parser.error("gate and --selftest are mutually exclusive")
    if not args.selftest and args.gate is None:
        parser.error("a gate is required (source or host)")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.selftest:
            return selftest()
        return run_gate(repo_root(Path.cwd()), args.gate)
    except InfrastructureError as exc:
        print(
            f"ci-gate: ERROR exit={EXIT_INFRASTRUCTURE} detail={exc}",
            file=sys.stderr,
        )
        return EXIT_INFRASTRUCTURE


if __name__ == "__main__":
    raise SystemExit(main())
