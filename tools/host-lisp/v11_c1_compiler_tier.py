#!/usr/bin/env python3
"""Materialize the temporary 1.1-C1 compiler-tier disk-lib suite."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
HOST_TOOLS = ROOT / "tools" / "host-lisp"
if str(HOST_TOOLS) not in sys.path:
    sys.path.insert(0, str(HOST_TOOLS))

import bytecode_p0_stdlib as Stdlib  # noqa: E402
from v2_workbench_codemod import rewrite_tokens  # noqa: E402


SOURCES = (
    "lib/lcc.lisp",
    "lib/lcc-fasl.lisp",
    "lib/dialect-v2/lcc-profile.lisp",
)
EXPORTS = ("%c1-compile",)
OMIT = {
    "%compile-slot-capacity",
    "%compile-slot-find",
    "%compile-slot-scan-entries",
    "compile-error",
    "compile-file",
    "compile-string",
    "fasl-emit-scratch",
    "lcc-compile",
    "lcc-lits",
    "lcc-run",
}
FORMAT = "lisp65-v11-c1-compiler-tier-suite-generator-v1"


class CompilerTierError(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def generate(out: Path) -> dict:
    source_root = out.parent / "c1-compiler-sources"
    if source_root.exists():
        shutil.rmtree(source_root)
    generated_sources: list[str] = []
    functions: list[str] = []
    inputs: list[dict] = []
    outputs: list[dict] = []
    replacement_counts = {"string->list": 0, "list->string": 0}
    definition_sources: dict[str, list[str]] = {}
    for source in SOURCES:
        original = ROOT / source
        text, counts = rewrite_tokens(original.read_text(encoding="utf-8"))
        for name, count in counts.items():
            replacement_counts[name] += count
        target = source_root / source
        target.parent.mkdir(parents=True, exist_ok=True)
        data = text.encode("utf-8")
        target.write_bytes(data)
        generated_sources.append(_relative(target))
        source_functions = Stdlib._defun_names([target])
        functions = Stdlib._append_unique(functions, source_functions)
        for name in source_functions:
            definition_sources.setdefault(name, []).append(_relative(target))
        inputs.append({"path": source, "sha256": _sha(original.read_bytes())})
        outputs.append({"path": _relative(target), "sha256": _sha(data)})
    functions = [name for name in functions if name not in OMIT]
    missing = sorted(set(EXPORTS) - set(functions))
    if missing:
        raise CompilerTierError("missing compiler exports: " + ", ".join(missing))
    suite = {
        "format": "lisp65-bytecode-p0-disk-lib-suite-v1",
        "name": "c1-compiler-tier",
        "d81_name": "LCC",
        "provides": list(EXPORTS),
        "requires": ["core", "buffer"],
        "description": (
            "Temporary 1.1-C1 self-hosting compiler tier; all internal entries "
            "are ordinal-only and the resident coordinator owns its LIFO lifetime."
        ),
        "sources": generated_sources,
        "functions": functions,
        "resident_suite": (
            "build/bytecode/dialect-v2/suites/"
            "p0-stdlib-einsuite-core-workbench-subset.json"
        ),
        "strict_arity": True,
        "abi_profile": "dialect-v2",
        "max_call_args": 12,
        "directory_only_prefixes": ["%", "lcc-"],
        "exports": list(EXPORTS),
        "definition_source_overrides": {
            name: sources[-1]
            for name, sources in sorted(definition_sources.items())
            if len(sources) > 1
        },
        "cases": [
            {
                "name": "c1-expression-detaches-codeobject",
                "expr": "(car (car (%c1-compile 0 (quote (+ 1 2)) nil)))",
                "expect": "0",
            },
            {
                "name": "c1-source-detaches-buffer",
                "expr": (
                    "(%buffer-read 0 (%c1-compile 1 "
                    "\"(defun c1-probe () 42)\" nil))"
                ),
                "expect": "t",
            },
        ],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    data = _json_bytes(suite)
    out.write_bytes(data)
    outputs.append({"path": _relative(out), "sha256": _sha(data)})
    return {
        "format": FORMAT,
        "suite": _relative(out),
        "functions": len(functions),
        "exports": list(EXPORTS),
        "omitted": sorted(OMIT),
        "replacement_counts": replacement_counts,
        "inputs": inputs,
        "outputs": outputs,
    }


def selftest() -> None:
    (ROOT / "build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c1-tier-", dir=ROOT / "build") as raw:
        root = Path(raw)
        first = generate(root / "suite.json")
        first_files = {
            path.relative_to(root).as_posix(): _sha(path.read_bytes())
            for path in root.rglob("*") if path.is_file()
        }
        second = generate(root / "suite.json")
        second_files = {
            path.relative_to(root).as_posix(): _sha(path.read_bytes())
            for path in root.rglob("*") if path.is_file()
        }
        if first != second or first_files != second_files:
            raise CompilerTierError("compiler-tier generation is not deterministic")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "build/bytecode/dialect-v2/suites/p0-c1-compiler-tier.json",
    )
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    try:
        if args.selftest:
            selftest()
            print("v11-c1-compiler-tier: SELFTEST PASS")
            return 0
        report = generate(args.out)
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_bytes(_json_bytes(report))
    except (CompilerTierError, OSError, ValueError) as exc:
        print(f"v11-c1-compiler-tier: FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "v11-c1-compiler-tier: PASS functions=%d suite=%s"
        % (report["functions"], report["suite"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
