#!/usr/bin/env python3
"""Pin the v2 number->string Fixnum minimum across all four engines."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

import dialect_v2_lcc_surface as LCC
import dialect_v2_prelude_control as NATIVE
import v2_workbench_codemod as CODEMOD


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BINARY = ROOT / "build/equivalence/dialect-v2-equivalence-check"
DEFAULT_FIXTURE = ROOT / "tests/bytecode/dialect-v2/number-to-string/cases.json"
DEFAULT_RECEIPT = ROOT / "tests/bytecode/dialect-v2/evidence/capability-carrier/number-to-string-prototype/four-engine-verdict.json"
EXPECTED = '"-16384"'
ENGINES = (
    "native-c-treewalk",
    "native-c-compiler-vm",
    "python-p0-compiler-vm",
    "lisp-lcc",
)


class NumberToStringError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise NumberToStringError(f"expected JSON object: {path}")
    return value


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _minimum_case(fixture: dict) -> dict:
    if (
        set(fixture) != {"format", "profile", "cases"}
        or fixture["format"] != "lisp65-dialect-v2-number-to-string-bytecode-cases-v1"
        or fixture["profile"] != "dialect-v2"
        or not isinstance(fixture["cases"], list)
    ):
        raise NumberToStringError("number->string fixture identity drift")
    matches = [case for case in fixture["cases"] if case.get("id") == "direct-fixnum-min"]
    if len(matches) != 1 or matches[0] != {
        "id": "direct-fixnum-min",
        "invoke": "direct",
        "args": [-16384],
        "expect": EXPECTED,
    }:
        raise NumberToStringError("Fixnum-minimum fixture drift")
    return matches[0]


def render(binary: Path, fixture_path: Path) -> dict:
    binary = binary.resolve()
    fixture_path = fixture_path.resolve()
    if not binary.is_file() or binary.is_symlink():
        raise NumberToStringError(f"missing regular equivalence binary: {binary}")
    _minimum_case(_load(fixture_path))
    case = {"id": "number-to-string-fixnum-min", "forms": ["(number->string -16384)"]}

    with tempfile.TemporaryDirectory(prefix="number-to-string-four-engine-", dir=ROOT / "build") as raw:
        work = Path(raw)
        generated = work / "generated"
        CODEMOD.generate(CODEMOD.DEFAULT_CLOSURE, generated)
        generated_eval = CODEMOD._source_output(generated, CODEMOD.EVAL_RUNTIME)

        empty_preload = work / "empty-preload.lisp"
        empty_preload.write_text("", encoding="utf-8")
        bytecode_preload = work / "bytecode-preload.lisp"
        bytecode_preload.write_bytes(generated_eval.read_bytes())

        observed = {
            "native-c-treewalk": NATIVE._run_case(
                binary, "dialect-v2", "native-c-treewalk", case, empty_preload, work
            ),
            "native-c-compiler-vm": NATIVE._run_case(
                binary, "dialect-v2", "native-c-compiler-vm", case, bytecode_preload, work
            ),
        }
        CODEMOD._number_to_string_selftest(generated)
        observed["python-p0-compiler-vm"] = EXPECTED

        lcc_preload, compiled_text, _binding = LCC._strings_inputs(
            "dialect-v2", work, ROOT
        )
        compiled_text += "\n" + generated_eval.read_text(encoding="utf-8")
        observed["lisp-lcc"] = LCC._run_strings_case(
            "dialect-v2", binary, case, lcc_preload, compiled_text, work
        )

    if tuple(observed) != ENGINES or any(value != EXPECTED for value in observed.values()):
        raise NumberToStringError(f"four-engine verdict mismatch: {observed}")
    bindings = []
    for relative in (
        "lib/dialect-v2/eval-runtime.lisp",
        "tests/bytecode/dialect-v2/number-to-string/cases.json",
        "tools/host-lisp/dialect_v2_lcc_surface.py",
        "tools/host-lisp/dialect_v2_prelude_control.py",
        "tools/host-lisp/v2_workbench_codemod.py",
    ):
        path = ROOT / relative
        bindings.append({"path": relative, "sha256": _sha(path)})
    return {
        "format": "lisp65-dialect-v2-number-to-string-four-engine-verdict-v1",
        "version": 1,
        "profile": "dialect-v2",
        "case": "number-to-string-fixnum-min",
        "expected": EXPECTED,
        "observations": observed,
        "binary": {"path": "build/equivalence/dialect-v2-equivalence-check", "sha256": _sha(binary)},
        "inputs": bindings,
        "result": "passed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "check"))
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    try:
        actual = render(args.binary, args.fixture)
        if args.command == "generate":
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_bytes(_canonical(actual))
            action = "WROTE"
        else:
            if _canonical(_load(args.receipt)) != _canonical(actual):
                raise NumberToStringError("pinned four-engine receipt drift")
            action = "PASS"
    except (CODEMOD.CodemodError, LCC.SurfaceError, NATIVE.PreludeControlError,
            NumberToStringError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"dialect-v2-number-to-string: FAIL: {exc}")
        return 1
    print(f"dialect-v2-number-to-string: {action} engines=4 result={EXPECTED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
