#!/usr/bin/env python3
"""Gate-aware, side-effect-free project toolchain diagnostics.

The doctor never downloads software or contacts an emulator or MEGA65. Compiler
and D81 capability probes write only to an automatically removed temporary
directory outside the project worktree.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Sequence


FORMAT = "lisp65-project-doctor-v1"
SELFTEST_FORMAT = "lisp65-project-doctor-selftest-v1"
GATES = ("G0", "G1", "G2", "G4", "G5")
EXIT_READY = 0
EXIT_NOT_READY = 3
EXIT_USAGE = 64
EXIT_INTERNAL = 70
MIN_PYTHON = (3, 10)
COMMAND_TIMEOUT = 10.0


class UsageError(Exception):
    """Raised for a command-line contract violation."""


class DoctorArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise UsageError(message)


@dataclass(frozen=True)
class Check:
    id: str
    label: str
    requirement: str
    status: str
    gates: list[str]
    path: str | None = None
    version: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        return "\n".join(part for part in (self.stdout, self.stderr) if part).strip()


def _run(
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout: float = COMMAND_TIMEOUT,
    env: dict[str, str] | None = None,
) -> CommandResult:
    try:
        completed = subprocess.run(
            list(argv),
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"command not found: {argv[0]}") from exc
    except PermissionError as exc:
        raise RuntimeError(f"command is not executable: {argv[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"command timed out after {timeout:g}s: {argv[0]}") from exc
    except OSError as exc:
        raise RuntimeError(f"cannot execute {argv[0]}: {exc}") from exc
    return CommandResult(
        list(argv), completed.returncode, completed.stdout.strip(), completed.stderr.strip()
    )


def _command(value: str, *, root: Path) -> tuple[list[str], str]:
    try:
        argv = shlex.split(value)
    except ValueError as exc:
        raise RuntimeError(f"invalid command value {value!r}: {exc}") from exc
    if not argv:
        raise RuntimeError("empty command value")

    program = Path(argv[0]).expanduser()
    if program.is_absolute() or "/" in argv[0]:
        candidate = program if program.is_absolute() else root / program
        # Target-selecting compiler symlinks (for example mos-mega65-clang)
        # derive their target from argv[0], so do not resolve the final symlink.
        candidate = Path(os.path.abspath(candidate))
        if not candidate.is_file():
            raise RuntimeError(f"command not found: {candidate}")
        if not os.access(candidate, os.X_OK):
            raise RuntimeError(f"command is not executable: {candidate}")
        argv[0] = str(candidate)
        return argv, str(candidate)

    resolved = shutil.which(argv[0])
    if resolved is None:
        raise RuntimeError(f"command not found on PATH: {argv[0]}")
    argv[0] = resolved
    return argv, resolved


def _first_line(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return None


def _version_line(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if re.search(r"\bversion\b", line, re.IGNORECASE):
            return line
    return lines[0] if lines else None


def _validated_temp_base(root: Path, candidate: Path | None = None) -> Path:
    if candidate is None:
        for name in ("TMPDIR", "TEMP", "TMP"):
            value = os.environ.get(name)
            if value:
                _validated_temp_base(root, Path(value).expanduser())
    base = (candidate if candidate is not None else Path(tempfile.gettempdir())).resolve()
    try:
        base.relative_to(root.resolve())
    except ValueError:
        return base
    raise RuntimeError(f"temporary directory must be outside the worktree: {base}")


def _temporary_directory(*, root: Path, prefix: str):
    return tempfile.TemporaryDirectory(prefix=prefix, dir=_validated_temp_base(root))


def _pass(
    check_id: str,
    label: str,
    gates: Sequence[str],
    *,
    path: str | None = None,
    version: str | None = None,
    detail: str | None = None,
) -> Check:
    return Check(check_id, label, "required", "pass", list(gates), path, version, detail)


def _fail(
    check_id: str,
    label: str,
    gates: Sequence[str],
    detail: str,
    *,
    path: str | None = None,
) -> Check:
    return Check(check_id, label, "required", "fail", list(gates), path, None, detail)


def _probe(
    check_id: str,
    label: str,
    gates: Sequence[str],
    action: Callable[[], Check],
) -> Check:
    try:
        return action()
    except (OSError, RuntimeError, ValueError) as exc:
        return _fail(check_id, label, gates, str(exc))


def _python_check() -> Check:
    gates = GATES
    version = ".".join(str(part) for part in sys.version_info[:3])
    if sys.version_info < MIN_PYTHON:
        return _fail(
            "python",
            "Python runtime",
            gates,
            f"Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]} required, found {version}",
            path=sys.executable,
        )

    modules = (
        "argparse",
        "ast",
        "dataclasses",
        "hashlib",
        "json",
        "pathlib",
        "shlex",
        "shutil",
        "subprocess",
        "tempfile",
    )
    missing = [name for name in modules if importlib.util.find_spec(name) is None]
    if missing:
        return _fail(
            "python",
            "Python runtime",
            gates,
            "missing standard-library modules: " + ", ".join(missing),
            path=sys.executable,
        )
    return _pass(
        "python",
        "Python runtime",
        gates,
        path=str(Path(sys.executable).resolve()),
        version=version,
        detail="stdlib modules available",
    )


def _make_check(root: Path) -> Check:
    gates = GATES

    def action() -> Check:
        argv, path = _command(os.environ.get("MAKE", "make"), root=root)
        result = _run([*argv, "--version"], cwd=root)
        first = _first_line(result.output)
        if result.returncode != 0 or first is None:
            raise RuntimeError(f"make --version failed with exit {result.returncode}")
        if "GNU Make" not in first:
            raise RuntimeError(f"GNU Make required, found: {first}")
        return _pass("make", "GNU Make", gates, path=path, version=first)

    return _probe("make", "GNU Make", gates, action)


def _sh_check(root: Path) -> Check:
    gates = GATES

    def action() -> Check:
        argv, path = _command("sh", root=root)
        result = _run([*argv, "-c", "set -eu; test x = x"], cwd=root)
        if result.returncode != 0:
            raise RuntimeError(f"POSIX shell probe failed with exit {result.returncode}")
        return _pass("posix-sh", "POSIX shell", gates, path=path)

    return _probe("posix-sh", "POSIX shell", gates, action)


def _git_check(root: Path) -> Check:
    gates = GATES

    def action() -> Check:
        argv, path = _command("git", root=root)
        version_result = _run([*argv, "--version"], cwd=root)
        if version_result.returncode != 0:
            raise RuntimeError(f"git --version failed with exit {version_result.returncode}")
        repo_result = _run([*argv, "rev-parse", "--show-toplevel"], cwd=root)
        if repo_result.returncode != 0:
            detail = _first_line(repo_result.stderr) or "not a Git worktree"
            raise RuntimeError(detail)
        actual_root = Path(repo_result.stdout).resolve()
        if actual_root != root.resolve():
            raise RuntimeError(f"Git root mismatch: expected {root}, found {actual_root}")
        return _pass(
            "git",
            "Git worktree",
            gates,
            path=path,
            version=_first_line(version_result.output),
            detail=str(actual_root),
        )

    return _probe("git", "Git worktree", gates, action)


def _host_cc_check(root: Path) -> Check:
    gates = ("G1", "G2", "G4", "G5")

    def action() -> Check:
        argv, path = _command(os.environ.get("HOSTCC", "cc"), root=root)
        version_result = _run([*argv, "--version"], cwd=root)
        with _temporary_directory(root=root, prefix="lisp65-doctor-hostcc-") as temp_name:
            temp = Path(temp_name)
            source = temp / "probe.c"
            binary = temp / "probe"
            source.write_text(
                "#include <stdint.h>\nint main(void) { uint16_t x = 0; return x; }\n",
                encoding="ascii",
            )
            compile_result = _run(
                [*argv, "-std=c99", "-Wall", "-Werror", str(source), "-o", str(binary)],
                cwd=root,
            )
            if compile_result.returncode != 0:
                detail = _first_line(compile_result.output) or "no compiler diagnostics"
                raise RuntimeError(f"C99 compile/link failed: {detail}")
            run_result = _run([str(binary)], cwd=root)
            if run_result.returncode != 0:
                raise RuntimeError(f"compiled C99 probe exited {run_result.returncode}")
        return _pass(
            "host-cc-c99",
            "Host C99 compiler",
            gates,
            path=path,
            version=_first_line(version_result.output),
            detail="compile, link and execution passed",
        )

    return _probe("host-cc-c99", "Host C99 compiler", gates, action)


def _sanitizer_check(root: Path) -> Check:
    gates = ("G1", "G2")

    def action() -> Check:
        argv, path = _command(os.environ.get("HOSTCC", "cc"), root=root)
        with _temporary_directory(root=root, prefix="lisp65-doctor-sanitizer-") as temp_name:
            temp = Path(temp_name)
            source = temp / "probe.c"
            binary = temp / "probe"
            source.write_text("int main(void) { return 0; }\n", encoding="ascii")
            compile_result = _run(
                [
                    *argv,
                    "-std=c99",
                    "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer",
                    str(source),
                    "-o",
                    str(binary),
                ],
                cwd=root,
            )
            if compile_result.returncode != 0:
                detail = _first_line(compile_result.output) or "no compiler diagnostics"
                raise RuntimeError(f"ASan/UBSan compile/link failed: {detail}")
            env = os.environ.copy()
            env.setdefault("ASAN_OPTIONS", "detect_leaks=0:halt_on_error=1")
            env.setdefault("UBSAN_OPTIONS", "halt_on_error=1")
            run_result = _run([str(binary)], cwd=root, env=env)
            if run_result.returncode != 0:
                detail = _first_line(run_result.output) or "no sanitizer diagnostics"
                raise RuntimeError(
                    f"ASan/UBSan runtime probe exited {run_result.returncode}: {detail}"
                )
        return _pass(
            "host-sanitizers",
            "Host ASan and UBSan",
            gates,
            path=path,
            detail="compile, link and execution passed",
        )

    return _probe("host-sanitizers", "Host ASan and UBSan", gates, action)


def _c1541_check(root: Path) -> Check:
    gates = ("G1", "G2", "G4", "G5")

    def action() -> Check:
        argv, path = _command(os.environ.get("C1541", "c1541"), root=root)
        version_result = _run([*argv, "-version"], cwd=root)
        if version_result.returncode != 0:
            raise RuntimeError(f"c1541 -version failed with exit {version_result.returncode}")
        with _temporary_directory(root=root, prefix="lisp65-doctor-c1541-") as temp_name:
            image = Path(temp_name) / "probe.d81"
            format_result = _run(
                [*argv, "-format", "L65DOC,65", "d81", str(image)], cwd=root
            )
            if (
                format_result.returncode != 0
                or not image.is_file()
                or image.stat().st_size != 819200
            ):
                detail = _first_line(format_result.output) or "D81 image was not created"
                raise RuntimeError(f"D81 format probe failed: {detail}")
            list_result = _run([*argv, str(image), "-list"], cwd=root)
            if list_result.returncode != 0:
                detail = _first_line(list_result.output) or "no c1541 diagnostics"
                raise RuntimeError(f"D81 list probe failed: {detail}")
        version = next(
            (
                line.strip()
                for line in version_result.output.splitlines()
                if line.strip().lower().startswith("c1541 ")
            ),
            _version_line(version_result.output),
        )
        return _pass(
            "c1541",
            "VICE c1541 with D81 support",
            gates,
            path=path,
            version=version,
            detail="temporary D81 format and list passed",
        )

    return _probe("c1541", "VICE c1541 with D81 support", gates, action)


def _coreutils_check(root: Path) -> Check:
    gates = ("G2", "G4", "G5")

    def action() -> Check:
        names = (
            "awk",
            "cp",
            "dd",
            "env",
            "grep",
            "mkdir",
            "rm",
            "sed",
            "sha256sum",
            "stat",
            "tr",
            "wc",
        )
        paths = {name: shutil.which(name) for name in names}
        missing = [name for name, path in paths.items() if path is None]
        if missing:
            raise RuntimeError("required commands missing: " + ", ".join(missing))

        stat_result = _run([paths["stat"] or "stat", "-c%s", str(__file__)], cwd=root)
        if stat_result.returncode != 0 or not stat_result.stdout.isdigit():
            raise RuntimeError("stat lacks required -c%s capability")
        hash_result = _run([paths["sha256sum"] or "sha256sum", str(__file__)], cwd=root)
        if hash_result.returncode != 0 or not re.match(r"^[0-9a-f]{64}\s", hash_result.stdout):
            raise RuntimeError("sha256sum capability probe failed")
        dd_result = _run(
            [
                paths["dd"] or "dd",
                "if=/dev/null",
                "of=/dev/null",
                "status=none",
            ],
            cwd=root,
        )
        if dd_result.returncode != 0:
            raise RuntimeError("dd lacks required status=none capability")
        env_result = _run(
            [paths["env"] or "env", "-u", "LISP65_DOCTOR_PROBE", "sh", "-c", "exit 0"],
            cwd=root,
        )
        if env_result.returncode != 0:
            raise RuntimeError("env lacks required -u capability")
        return _pass(
            "coreutils",
            "Build command capabilities",
            gates,
            detail="required commands and GNU-style stat/dd/env capabilities passed",
        )

    return _probe("coreutils", "Build command capabilities", gates, action)


def _configured_path(value: str, root: Path) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def _llvm_check(root: Path) -> Check:
    gates = ("G2", "G4", "G5")

    def action() -> Check:
        llvm_dir = _configured_path(os.environ.get("LLVM", "tools/llvm-mos/bin"), root)
        clang_value = os.environ.get("CC_M65", str(llvm_dir / "mos-mega65-clang"))
        nm_value = os.environ.get("M65VMSTDLIB_NM", str(llvm_dir / "llvm-nm"))
        size_value = os.environ.get("M65VMSTDLIB_SIZE", str(llvm_dir / "llvm-size"))
        clang_argv, clang_path = _command(clang_value, root=root)
        nm_argv, nm_path = _command(nm_value, root=root)
        size_argv, size_path = _command(size_value, root=root)

        version_result = _run([*clang_argv, "--version"], cwd=root)
        if version_result.returncode != 0 or "mos-mega65" not in version_result.output:
            detail = _first_line(version_result.output) or "no compiler version output"
            raise RuntimeError(f"llvm-mos MEGA65 target not confirmed: {detail}")

        with _temporary_directory(root=root, prefix="lisp65-doctor-llvm-") as temp_name:
            temp = Path(temp_name)
            source = temp / "probe.c"
            prg = temp / "probe.prg"
            elf = Path(str(prg) + ".elf")
            source.write_text("int main(void) { return 0; }\n", encoding="ascii")
            compile_result = _run(
                [*clang_argv, "-Os", str(source), "-o", str(prg)], cwd=root, timeout=30.0
            )
            if compile_result.returncode != 0 or not prg.is_file() or not elf.is_file():
                detail = _first_line(compile_result.output) or "PRG/ELF output missing"
                raise RuntimeError(f"llvm-mos compile/link failed: {detail}")
            nm_result = _run([*nm_argv, "--defined-only", str(elf)], cwd=root)
            if nm_result.returncode != 0:
                raise RuntimeError(f"llvm-nm probe failed with exit {nm_result.returncode}")
            size_result = _run([*size_argv, "-A", str(elf)], cwd=root)
            if size_result.returncode != 0:
                raise RuntimeError(f"llvm-size probe failed with exit {size_result.returncode}")

        return _pass(
            "llvm-mos",
            "llvm-mos MEGA65 toolchain",
            gates,
            path=clang_path,
            version=_first_line(version_result.output),
            detail=f"compile/link, nm and size passed; nm={nm_path}; size={size_path}",
        )

    return _probe("llvm-mos", "llvm-mos MEGA65 toolchain", gates, action)


def _timeout_check(root: Path) -> Check:
    gates = GATES

    def action() -> Check:
        argv, path = _command("timeout", root=root)
        result = _run([*argv, "--kill-after=1", "2", "sh", "-c", "exit 0"], cwd=root)
        if result.returncode != 0:
            raise RuntimeError(f"timeout capability probe failed with exit {result.returncode}")
        version_result = _run([*argv, "--version"], cwd=root)
        return _pass(
            "timeout",
            "Process timeout utility",
            gates,
            path=path,
            version=_first_line(version_result.output),
        )

    return _probe("timeout", "Process timeout utility", gates, action)


def _m65tools_check(root: Path) -> Check:
    gates = ("G5",)

    def action() -> Check:
        tools_dir = _configured_path(os.environ.get("TOOLS", "tools/m65tools"), root)
        identities = {
            "etherload": ("MEGA65 Ethernet Loading Tool", "--help"),
            "mega65_ftp": ("MEGA65 SD card file transfer tool", "-h"),
            "m65": ("MEGA65 Cross-Development Tool", "--help"),
        }
        versions: list[str] = []
        for name, (identity, help_flag) in identities.items():
            path = tools_dir / name
            argv, _ = _command(str(path), root=root)
            result = _run([*argv, help_flag], cwd=root, timeout=3.0)
            if identity not in result.output:
                detail = _first_line(result.output) or "no tool identity output"
                raise RuntimeError(f"{name} executable probe failed: {detail}")
            if "Usage:" not in result.output and f"{name}: [options]" not in result.output:
                raise RuntimeError(f"{name} help probe did not emit usage information")
            version = next(
                (
                    line.strip()
                    for line in result.output.splitlines()
                    if re.match(r"^version\s*:", line.strip(), re.IGNORECASE)
                ),
                None,
            )
            if version is None:
                raise RuntimeError(f"{name} help probe did not emit a version")
            versions.append(f"{name}: {version}")
        return _pass(
            "m65tools",
            "MEGA65 live hardware tools",
            gates,
            path=str(tools_dir),
            detail="; ".join(versions),
        )

    return _probe("m65tools", "MEGA65 live hardware tools", gates, action)


def _hardware_deferred() -> Check:
    device = os.environ.get("DEVICE", "/dev/ttyUSB1")
    return Check(
        "hardware-access",
        "MEGA65 hardware access",
        "informational",
        "deferred",
        ["G5"],
        path=device,
        detail="not contacted; device, Ethernet discovery and remote mode remain unchecked",
    )


def collect_checks(gate: str, root: Path) -> list[Check]:
    checks = [
        _python_check(),
        _make_check(root),
        _sh_check(root),
        _git_check(root),
        _timeout_check(root),
    ]
    if gate in {"G1", "G2", "G4", "G5"}:
        checks.extend((_host_cc_check(root), _c1541_check(root)))
    if gate in {"G1", "G2"}:
        checks.append(_sanitizer_check(root))
    if gate in {"G2", "G4", "G5"}:
        checks.extend((_coreutils_check(root), _llvm_check(root)))
    if gate == "G5":
        checks.extend((_m65tools_check(root), _hardware_deferred()))
    return checks


def _summary(checks: Sequence[Check]) -> dict[str, int]:
    return {
        "passed": sum(check.status == "pass" for check in checks),
        "required_failed": sum(
            check.requirement == "required" and check.status == "fail" for check in checks
        ),
        "optional_missing": sum(check.status == "optional-missing" for check in checks),
        "deferred": sum(check.status == "deferred" for check in checks),
    }


def make_report(gate: str, checks: Sequence[Check]) -> dict[str, object]:
    summary = _summary(checks)
    if summary["required_failed"]:
        status = "not-ready"
    elif summary["deferred"]:
        status = "ready-with-deferred"
    else:
        status = "ready"
    return {
        "format": FORMAT,
        "requested_gate": gate,
        "status": status,
        "checks": [asdict(check) for check in checks],
        "summary": summary,
    }


def _render_text(report: dict[str, object]) -> str:
    lines = [
        f"lisp65 project doctor: {report['requested_gate']}",
        f"status: {report['status']}",
    ]
    checks = report["checks"]
    assert isinstance(checks, list)
    for raw in checks:
        assert isinstance(raw, dict)
        status = str(raw["status"]).upper()
        line = f"[{status:8}] {raw['id']}: {raw['label']}"
        if raw.get("version"):
            line += f" ({raw['version']})"
        lines.append(line)
        if raw.get("path"):
            lines.append(f"           path: {raw['path']}")
        if raw.get("detail"):
            lines.append(f"           {raw['detail']}")
    summary = report["summary"]
    assert isinstance(summary, dict)
    lines.append(
        "summary: passed={passed} required_failed={required_failed} "
        "optional_missing={optional_missing} deferred={deferred}".format(**summary)
    )
    return "\n".join(lines)


def _emit(value: dict[str, object], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(value, indent=2, sort_keys=True))
    else:
        print(_render_text(value))


def _selftest() -> tuple[int, list[str]]:
    failures: list[str] = []
    cases = 0

    def expect(name: str, condition: bool) -> None:
        nonlocal cases
        cases += 1
        if not condition:
            failures.append(name)

    passing = [_pass("ok", "OK", ["G0"])]
    report = make_report("G0", passing)
    expect("ready-report", report["status"] == "ready")
    expect("ready-summary", report["summary"] == {
        "passed": 1,
        "required_failed": 0,
        "optional_missing": 0,
        "deferred": 0,
    })
    expect("json-roundtrip", json.loads(json.dumps(report))["format"] == FORMAT)
    expect("text-status", "status: ready" in _render_text(report))

    failing = [_fail("missing", "Missing", ["G2"], "not found")]
    failed_report = make_report("G2", failing)
    expect("not-ready-report", failed_report["status"] == "not-ready")
    expect("not-ready-summary", _summary(failing)["required_failed"] == 1)

    deferred = [_hardware_deferred()]
    expect(
        "deferred-status",
        make_report("G5", deferred)["status"] == "ready-with-deferred",
    )
    expect("deferred-count", _summary(deferred)["deferred"] == 1)
    expect("version-selection", _version_line("noise\nVersion: 1.2\n") == "Version: 1.2")
    expect("first-line", _first_line("\n alpha\n beta") == "alpha")

    with tempfile.TemporaryDirectory(prefix="lisp65-doctor-selftest-") as temp_name:
        temp = Path(temp_name)
        fake = temp / "fake-tool"
        fake.write_text(
            f"#!{sys.executable}\nprint('fake tool version 1')\n", encoding="utf-8"
        )
        fake.chmod(0o755)
        argv, path = _command(str(fake), root=temp)
        result = _run([*argv, "--version"], cwd=temp)
        expect("fake-tool-resolve", path == str(fake.resolve()))
        expect("fake-tool-run", result.returncode == 0 and "version 1" in result.stdout)
        try:
            _command(str(temp / "missing"), root=temp)
        except RuntimeError:
            expect("missing-command", True)
        else:
            expect("missing-command", False)

        try:
            _validated_temp_base(temp, temp)
        except RuntimeError:
            expect("worktree-temp-rejected", True)
        else:
            expect("worktree-temp-rejected", False)

    expect("parse-g5-json", parse_args(["--gate", "G5", "--format", "json"]).gate == "G5")
    try:
        parse_args(["--gate", "G3"])
    except UsageError:
        expect("parse-invalid-gate", True)
    else:
        expect("parse-invalid-gate", False)

    return cases, failures


def _selftest_report(cases: int, failures: Sequence[str]) -> dict[str, object]:
    return {
        "format": SELFTEST_FORMAT,
        "status": "pass" if not failures else "fail",
        "cases": cases,
        "failures": list(failures),
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = DoctorArgumentParser(description=__doc__)
    parser.add_argument("--gate", choices=GATES, default="G2")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--selftest", action="store_true")
    return parser.parse_args(argv)


def _format_from_raw_args(argv: Sequence[str]) -> str:
    for index, value in enumerate(argv):
        if value == "--format" and index + 1 < len(argv) and argv[index + 1] == "json":
            return "json"
        if value == "--format=json":
            return "json"
    return "text"


def _emit_error(kind: str, message: str, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps({"format": FORMAT, "status": kind, "error": message}, sort_keys=True))
    else:
        print(f"project-doctor: {kind}: {message}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    requested_format = _format_from_raw_args(raw_args)
    try:
        args = parse_args(raw_args)
    except UsageError as exc:
        _emit_error("usage-error", str(exc), requested_format)
        return EXIT_USAGE

    try:
        if args.selftest:
            cases, failures = _selftest()
            report = _selftest_report(cases, failures)
            if args.format == "json":
                print(json.dumps(report, indent=2, sort_keys=True))
            elif failures:
                print(
                    f"project-doctor selftest: FAIL ({cases} cases): {', '.join(failures)}",
                    file=sys.stderr,
                )
            else:
                print(f"project-doctor selftest: PASS ({cases} cases)")
            return EXIT_READY if not failures else EXIT_INTERNAL

        root = Path(__file__).resolve().parents[2]
        report = make_report(args.gate, collect_checks(args.gate, root))
        _emit(report, args.format)
        summary = report["summary"]
        assert isinstance(summary, dict)
        return EXIT_READY if summary["required_failed"] == 0 else EXIT_NOT_READY
    except Exception as exc:  # keep the CLI exit-code contract stable
        _emit_error("internal-error", str(exc), args.format)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
