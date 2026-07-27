#!/usr/bin/env python3
"""Materialize the immutable C2 product compiler-tier suite.

The generated tier deliberately contains no L65M/FASL emitter.  It returns
detached CodeObject lists; the sole native C2 session emitter turns those into
C2I-v2 for both interactive installation and persistent compile-string output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
HOST_TOOLS = ROOT / "tools/host-lisp"
if str(HOST_TOOLS) not in sys.path:
    sys.path.insert(0, str(HOST_TOOLS))

import bytecode_p0_stdlib as Stdlib  # noqa: E402
from v2_workbench_codemod import rewrite_tokens  # noqa: E402


SOURCES = ("lib/lcc.lisp", "lib/dialect-v2/lcc-profile.lisp")
EXPORTS = ("%c2-compile-form",)
OMIT = {"lcc-compile", "lcc-lits", "lcc-run"}
FORMAT = "lisp65-c2-product-compiler-tier-suite-generator-v1"


class C2CompilerTierError(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def generate(out: Path) -> dict:
    source_root = out.parent / "c2-compiler-sources"
    if source_root.exists():
        shutil.rmtree(source_root)
    generated_sources: list[str] = []
    functions: list[str] = []
    inputs: list[dict] = []
    outputs: list[dict] = []
    replacement_counts = {"string->list": 0, "list->string": 0,
                          "%c1-compile-form": 0}
    definition_sources: dict[str, list[str]] = {}
    for source in SOURCES:
        original = ROOT / source
        text, counts = rewrite_tokens(original.read_text(encoding="utf-8"))
        for name, count in counts.items():
            replacement_counts[name] += count
        if source == "lib/lcc.lisp":
            count = text.count("%c1-compile-form")
            if count != 1:
                raise C2CompilerTierError(
                    f"unexpected %c1-compile-form token count: {count}"
                )
            text = text.replace("%c1-compile-form", "%c2-compile-form")
            replacement_counts["%c1-compile-form"] = count
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
        raise C2CompilerTierError("missing compiler exports: " + ", ".join(missing))
    if any("fasl" in name.lower() for name in functions):
        raise C2CompilerTierError("legacy FASL emitter leaked into the C2 compiler tier")
    suite = {
        "format": "lisp65-bytecode-p0-disk-lib-suite-v1",
        "name": "c2-product-compiler-tier",
        "d81_name": "LCC",
        "provides": list(EXPORTS),
        "requires": ["core", "buffer"],
        "description": (
            "Immutable C2 compiler tier. Born code is emitted only by the shared "
            "native C2I-v2 session emitter; no L65M/FASL emitter is present."
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
        "cases": [{
            "name": "c2-expression-detaches-codeobject",
            "expr": "(car (car (%c2-compile-form (quote (+ 1 2)))))",
            "expect": "0",
        }],
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
        "legacy_emitters": [],
    }


def selftest() -> None:
    (ROOT / "build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c2-tier-", dir=ROOT / "build") as raw:
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
            raise C2CompilerTierError("compiler-tier generation is not deterministic")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=(
        ROOT / "build/bytecode/dialect-v2/suites/p0-c2-compiler-tier.json"
    ))
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    try:
        if args.selftest:
            selftest(); print("c2-product-compiler-tier: SELFTEST PASS"); return 0
        report = generate(args.out)
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_bytes(_json_bytes(report))
    except (C2CompilerTierError, OSError, ValueError) as exc:
        print(f"c2-product-compiler-tier: FAIL: {exc}", file=sys.stderr); return 1
    print(f"c2-product-compiler-tier: PASS functions={report['functions']} suite={report['suite']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
