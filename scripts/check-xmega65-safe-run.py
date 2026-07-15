#!/usr/bin/env python3
"""Guard against direct headless xmega65 launches in scripts."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "scripts"
SKIP = {
    SCRIPT_ROOT / "xmega65-safe-run.sh",
    SCRIPT_ROOT / "check-xmega65-safe-run.py",
}
EMU_VAR = r'(?:\$"?\{?(?:XMEGA65|EMU|emu|emulator)\}?"?)'
TIMEOUT_EMU_RE = re.compile(r"\btimeout\b.*(?:\bxmega65\b|%s)" % EMU_VAR)
DIRECT_XMEGA65_RE = re.compile(r"^(?:env\s+)?(?:xmega65|[\"']?%s[\"']?)\b" % EMU_VAR)
PY_SUBPROCESS_CALL = r"subprocess\.(?:Popen|run|call|check_call|check_output)"
PY_XEMU_ARG = r"(?:XEMU\b|[\"'][^\"']*xmega65[^\"']*[\"'])"
PY_DIRECT_SUBPROCESS_RE = re.compile(r"%s\(\s*\[\s*%s" % (PY_SUBPROCESS_CALL, PY_XEMU_ARG))
PY_DIRECT_LAUNCH_RE = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\[\s*%s" % PY_XEMU_ARG
)
PY_DIRECT_SUBPROCESS_VAR_RE = re.compile(
    r"%s\(\s*([A-Za-z_][A-Za-z0-9_]*)\b" % PY_SUBPROCESS_CALL
)


def _script_paths(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.suffix in {".sh", ".py"}
    )


def _strip_inline_comment(line: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    out: list[str] = []
    for ch in line:
        if escaped:
            out.append(ch)
            escaped = False
            continue
        if ch == "\\" and not in_single:
            out.append(ch)
            escaped = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        if ch == "#" and not in_single and not in_double:
            break
        out.append(ch)
    return "".join(out).strip()


def _heredoc_token(line: str) -> str | None:
    match = re.search(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?", line)
    return match.group(1) if match else None


def _shell_violations(path: Path) -> list[tuple[int, str, str]]:
    if path.resolve() in {item.resolve() for item in SKIP}:
        return []
    out: list[tuple[int, str, str]] = []
    heredoc: str | None = None
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped_raw = raw.strip()
        if heredoc is not None:
            if stripped_raw == heredoc:
                heredoc = None
            continue
        line = _strip_inline_comment(raw)
        if not line:
            continue
        token = _heredoc_token(line)
        if token is not None:
            heredoc = token
            continue
        if "xmega65-safe-run.sh" in line:
            continue
        if TIMEOUT_EMU_RE.search(line):
            out.append((lineno, "timeout-emulator", raw.rstrip()))
            continue
        if DIRECT_XMEGA65_RE.search(line):
            out.append((lineno, "direct-emulator", raw.rstrip()))
    return out


def _python_violations(path: Path) -> list[tuple[int, str, str]]:
    if path.resolve() in {item.resolve() for item in SKIP}:
        return []
    out: list[tuple[int, str, str]] = []
    direct_launch_vars: set[str] = set()
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = _strip_inline_comment(raw)
        if not line:
            continue
        if "xmega65-safe-run.sh" in line:
            continue
        if PY_DIRECT_SUBPROCESS_RE.search(line):
            out.append((lineno, "direct-python-emulator", raw.rstrip()))
            continue
        launch_match = PY_DIRECT_LAUNCH_RE.search(line)
        if launch_match:
            direct_launch_vars.add(launch_match.group(1))
            out.append((lineno, "direct-python-emulator-list", raw.rstrip()))
            continue
        popen_match = PY_DIRECT_SUBPROCESS_VAR_RE.search(line)
        if popen_match and popen_match.group(1) in direct_launch_vars:
            out.append((lineno, "direct-python-emulator", raw.rstrip()))
    return out


def _violations(path: Path) -> list[tuple[int, str, str]]:
    if path.suffix == ".py":
        return _python_violations(path)
    return _shell_violations(path)


def check(paths: list[Path]) -> int:
    failures = 0
    for path in paths:
        for lineno, kind, line in _violations(path):
            rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
            print(f"{rel}:{lineno}: {kind}: {line}", file=sys.stderr)
            failures += 1
    if failures:
        print(
            "xmega65-safe-run-check: FAIL direct emulator launch found; use scripts/xmega65-safe-run.sh",
            file=sys.stderr,
        )
        return 1
    print(f"xmega65-safe-run-check: PASS scripts={len(paths)}")
    return 0


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bad = root / "bad.sh"
        bad.write_text('timeout 1 "$emu" -headless\n', encoding="utf-8")
        good_sh = root / "good.sh"
        good_sh.write_text(
            'scripts/xmega65-safe-run.sh "$dump_abs" 1 "$emu" -headless\n',
            encoding="utf-8",
        )
        bad_py = root / "bad.py"
        bad_py.write_text(
            'import subprocess\nXEMU="xmega65"\nsubprocess.Popen([XEMU, "-headless"])\n',
            encoding="utf-8",
        )
        bad_py_run = root / "bad-run.py"
        bad_py_run.write_text(
            'import subprocess\ncmd=["/usr/bin/xmega65", "-headless"]\nsubprocess.run(cmd)\n',
            encoding="utf-8",
        )
        good_py = root / "good.py"
        good_py.write_text(
            'import subprocess\n'
            'safe = "scripts/xmega65-safe-run.sh"\n'
            'cmd = [safe, "/tmp/token", "1", "xmega65", "-headless"]\n'
            'subprocess.Popen(cmd)\n',
            encoding="utf-8",
        )
        doc = root / "doc.sh"
        doc.write_text("cat <<EOF\n  xmega65 -headless\nEOF\n", encoding="utf-8")
        if not _violations(bad):
            print("selftest failed: bad.sh was not rejected", file=sys.stderr)
            return 1
        if _violations(good_sh):
            print("selftest failed: good.sh was rejected", file=sys.stderr)
            return 1
        if not _violations(bad_py):
            print("selftest failed: bad.py was not rejected", file=sys.stderr)
            return 1
        if not _violations(bad_py_run):
            print("selftest failed: bad-run.py was not rejected", file=sys.stderr)
            return 1
        if _violations(good_py):
            print("selftest failed: good.py was rejected", file=sys.stderr)
            return 1
        if _violations(doc):
            print("selftest failed: heredoc doc was rejected", file=sys.stderr)
            return 1
    print("xmega65-safe-run-check selftest OK")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args(argv[1:])
    if args.selftest:
        return selftest()
    paths = [Path(path) for path in args.paths] if args.paths else _script_paths(SCRIPT_ROOT)
    return check(paths)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
