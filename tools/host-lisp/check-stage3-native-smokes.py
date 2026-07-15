#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
LISP64 = ROOT / "tools" / "host-lisp" / "lisp64.py"
SPEC = ROOT / "docs" / "phase6-stufe3-native-smoke-spec.md"
RUN_TESTS = ROOT / "tools" / "host-lisp" / "run-tests.sh"

SMOKES = [
    {
        "name": "structsmoke",
        "files": [
            "lisp/prelude.lsp",
            "lisp/cl-compat.lsp",
            "lisp/lib-struct.lsp",
            "lisp/struct-native-smoke.lsp",
        ],
        "marker": "PASS=5 FAIL=0",
    },
    {
        "name": "seqsmoke",
        "files": [
            "lisp/prelude.lsp",
            "lisp/cl-compat.lsp",
            "lisp/lib-seq.lsp",
            "lisp/seq-native-smoke.lsp",
        ],
        "marker": "PASS=5 FAIL=0",
    },
]


def fail(msg):
    print(f"stage3-native-smokes: FAIL: {msg}", file=sys.stderr)
    return 1


def run_smoke(smoke):
    cmd = ["python3", str(LISP64), *[str(ROOT / f) for f in smoke["files"]]]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if proc.returncode != 0:
        print(proc.stdout, end="")
        print(proc.stderr, end="", file=sys.stderr)
        return fail(f"{smoke['name']} exited with {proc.returncode}")
    out = proc.stdout.strip()
    if smoke["marker"] not in out:
        print(out)
        return fail(f"{smoke['name']} missing marker {smoke['marker']}")
    return 0


def check_wiring():
    spec = SPEC.read_text(encoding="utf-8")
    run_tests = RUN_TESTS.read_text(encoding="utf-8")
    for smoke in SMOKES:
        fixture = smoke["files"][-1]
        if smoke["name"] not in run_tests or fixture not in run_tests:
            return fail(f"{smoke['name']} not wired in run-tests.sh")
        if fixture not in spec or smoke["marker"] not in spec:
            return fail(f"{smoke['name']} not documented in stage3 spec")
    return 0


def main():
    rc = check_wiring()
    if rc:
        return rc
    for smoke in SMOKES:
        rc = run_smoke(smoke)
        if rc:
            return rc
        print(f"  [{smoke['name']}] {smoke['marker']}")
    print("stage3-native-smokes: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
