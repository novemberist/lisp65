#!/usr/bin/env python3
"""Validate and execute the finite host-side Lisp65 eval-surface contract."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402


FORMAT = "lisp65-eval-surface-v1"
DEFAULT_FIXTURE = ROOT / "tests" / "bytecode" / "runtime" / "p0-eval-surface.json"
ROOT_KEYS = {"format", "description", "cases"}
CASE_KEYS = {"name", "forms", "expect", "expect_error"}
CASE_REQUIRED_KEYS = {"name", "forms"}
CASE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
NATIVE_ENGINES = {
    "native-treewalk": "tree",
    "native-c-compiler-vm": "vm",
    "lisp-lcc": "lcc",
}


class ContractError(Exception):
    pass


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ContractError("duplicate JSON key: %s" % key)
        out[key] = value
    return out


def _load_text(text: str, source: str) -> dict[str, Any]:
    try:
        data = json.loads(text, object_pairs_hook=_unique_object)
    except ContractError:
        raise
    except (TypeError, ValueError) as exc:
        raise ContractError("%s: invalid JSON: %s" % (source, exc)) from exc
    if not isinstance(data, dict):
        raise ContractError("%s: fixture root must be an object" % source)
    return data


def _load_fixture(path: Path) -> dict[str, Any]:
    try:
        return _load_text(path.read_text(encoding="utf-8"), str(path))
    except OSError as exc:
        raise ContractError("cannot read %s: %s" % (path, exc)) from exc


def _require_exact_keys(value: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(set(value) - allowed)
    missing = sorted(allowed - set(value))
    if unknown:
        raise ContractError("%s: unknown field(s): %s" % (where, ", ".join(unknown)))
    if missing:
        raise ContractError("%s: missing field(s): %s" % (where, ", ".join(missing)))


def validate_fixture(data: dict[str, Any], source: str = "fixture") -> list[dict[str, Any]]:
    _require_exact_keys(data, ROOT_KEYS, source)
    if data["format"] != FORMAT:
        raise ContractError("%s: bad format %r" % (source, data["format"]))
    if not isinstance(data["description"], str) or not data["description"].strip():
        raise ContractError("%s: description must be a non-empty string" % source)
    cases = data["cases"]
    if not isinstance(cases, list) or not cases:
        raise ContractError("%s: cases must be a non-empty list" % source)

    seen: set[str] = set()
    for index, case in enumerate(cases):
        where = "%s/cases[%d]" % (source, index)
        if not isinstance(case, dict):
            raise ContractError("%s: case must be an object" % where)
        unknown = sorted(set(case) - CASE_KEYS)
        missing = sorted(CASE_REQUIRED_KEYS - set(case))
        if unknown:
            raise ContractError("%s: unknown field(s): %s" % (where, ", ".join(unknown)))
        if missing:
            raise ContractError("%s: missing field(s): %s" % (where, ", ".join(missing)))
        result_fields = set(case) & {"expect", "expect_error"}
        if len(result_fields) != 1:
            raise ContractError("%s: exactly one of expect/expect_error is required" % where)
        name = case["name"]
        if not isinstance(name, str) or not CASE_NAME_RE.fullmatch(name):
            raise ContractError("%s: invalid case name %r" % (where, name))
        if name in seen:
            raise ContractError("%s: duplicate case name: %s" % (source, name))
        seen.add(name)
        forms = case["forms"]
        if not isinstance(forms, list) or not forms:
            raise ContractError("%s: forms must be a non-empty list" % where)
        for form_index, form in enumerate(forms):
            if not isinstance(form, str) or not form.strip():
                raise ContractError(
                    "%s/forms[%d]: form must be a non-empty string" % (where, form_index)
                )
            try:
                C.parse_one(form)
            except Exception as exc:
                raise ContractError(
                    "%s/forms[%d]: invalid form: %s" % (where, form_index, exc)
                ) from exc
        result_field = next(iter(result_fields))
        expect = case[result_field]
        if not isinstance(expect, str) or not expect or expect != expect.strip():
            raise ContractError("%s: %s must be a canonical non-empty string" % (where, result_field))
        if result_field == "expect_error" and expect != "!error":
            raise ContractError("%s: expect_error must be the normalized !error marker" % where)
    return cases


def _install(vm: B.P0VM, heap: B.Heap, name: str, code: B.CodeObject) -> None:
    vm.directory[heap.intern(name)] = code
    vm.code_names[id(code)] = name


def _compile_and_install(
    vm: B.P0VM,
    heap: B.Heap,
    form: Any,
    entry: str,
    *,
    abi_profile: str = "dialect-v1",
    abi_ledger: dict[str, Any] | None = None,
) -> tuple[B.CodeObject, int]:
    is_defun = isinstance(form, list) and len(form) >= 1 and form[0] == "defun"
    top_form = form if is_defun else ["defun", entry, [], form]
    try:
        name, code, helpers = C.compile_top_form_with_helpers(
            top_form, heap,
            strict_arity=abi_profile == "dialect-v2",
            abi_profile=abi_profile,
            abi_ledger=abi_ledger,
        )
    except Exception as exc:
        raise ContractError("compile failed: %s" % exc) from exc
    if name is None:
        raise ContractError("compiler returned an unnamed top-level form")
    for helper_name, helper_code in helpers:
        _install(vm, heap, helper_name, helper_code)
    _install(vm, heap, name, code)
    return code, len(helpers)


def _run_case(
    case: dict[str, Any], case_index: int, abi_profile: str = "dialect-v1"
) -> tuple[str, int, int]:
    heap = B.Heap()
    abi_ledger = None
    if abi_profile == "dialect-v2":
        abi_ledger = json.loads((ROOT / "config" / "bytecode-abi-ledger.json").read_text(encoding="utf-8"))
    vm = B.P0VM(
        heap=heap, directory={}, abi_profile=abi_profile, abi_ledger=abi_ledger
    )
    result = B.NIL
    steps = 0
    helpers = 0
    for form_index, source in enumerate(case["forms"]):
        form = C.parse_one(source)
        entry = "__eval_surface_%d_%d" % (case_index, form_index)
        code, helper_count = _compile_and_install(
            vm, heap, form, entry,
            abi_profile=abi_profile, abi_ledger=abi_ledger,
        )
        helpers += helper_count
        if isinstance(form, list) and form and form[0] == "defun":
            result = heap.intern(form[1])
            continue
        try:
            result = vm.run(code, [])
        except Exception as exc:
            if "expect_error" in case:
                return "!error", steps, helpers
            raise ContractError("runtime failed: %s" % exc) from exc
        steps += vm.steps
    return heap.obj_to_text(result), steps, helpers


def run_fixture(
    data: dict[str, Any],
    source: str = "fixture",
    verbose: bool = False,
    abi_profile: str = "dialect-v1",
) -> tuple[int, int, int, int]:
    cases = validate_fixture(data, source)
    total_forms = 0
    total_steps = 0
    total_helpers = 0
    for case_index, case in enumerate(cases):
        try:
            got, steps, helpers = _run_case(case, case_index, abi_profile=abi_profile)
        except ContractError as exc:
            raise ContractError("%s/%s: %s" % (source, case["name"], exc)) from exc
        expected = case.get("expect", case.get("expect_error"))
        if expected == "!error" and got.startswith("!error"):
            got = "!error"
        if got != expected:
            raise ContractError(
                "%s/%s: got %r, expected %r" % (source, case["name"], got, expected)
            )
        total_forms += len(case["forms"])
        total_steps += steps
        total_helpers += helpers
        if verbose:
            print("PASS %-34s result=%s" % (case["name"], got))
    return len(cases), total_forms, total_steps, total_helpers


def _run_native_case(
    case: dict[str, Any],
    binary: Path,
    engine: str,
    preload: Path | None = None,
) -> str:
    mode = NATIVE_ENGINES[engine]
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix=".lisp", delete=False
        ) as temp:
            temp.write("\n".join(case["forms"]) + "\n")
            temp_path = Path(temp.name)
        argv = [str(binary), mode, str(temp_path)]
        if engine == "lisp-lcc":
            argv.extend(["--preload", str(preload or (ROOT / "lib" / "lcc.lisp"))])
        process = subprocess.run(
            argv,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ContractError("%s adapter failed: %s" % (engine, exc)) from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    if process.returncode != 0:
        raise ContractError(
            "%s adapter exited %d: %s"
            % (engine, process.returncode, process.stderr.strip())
        )
    results = [
        line.rsplit(" => ", 1)[1].strip()
        for line in process.stdout.splitlines()
        if " => " in line
    ]
    if len(results) != len(case["forms"]):
        raise ContractError(
            "%s adapter returned %d results for %d forms"
            % (engine, len(results), len(case["forms"]))
        )
    return results[-1]


def run_native_fixture(
    data: dict[str, Any],
    binary: Path,
    engine: str,
    source: str = "fixture",
    verbose: bool = False,
    preload: Path | None = None,
) -> tuple[int, int]:
    cases = validate_fixture(data, source)
    if not binary.is_file():
        raise ContractError("native eval adapter is missing: %s" % binary)
    forms = 0
    for case in cases:
        try:
            got = _run_native_case(case, binary, engine, preload=preload)
        except ContractError as exc:
            raise ContractError("%s/%s: %s" % (source, case["name"], exc)) from exc
        expected = case.get("expect", case.get("expect_error"))
        if expected == "!error" and got.startswith("!error"):
            got = "!error"
        if got != expected:
            raise ContractError(
                "%s/%s: %s got %r, expected %r"
                % (source, case["name"], engine, got, expected)
            )
        forms += len(case["forms"])
        if verbose:
            print("PASS %-34s result=%s" % (case["name"], got))
    return len(cases), forms


def _expect_failure(label: str, action: Any, contains: str) -> None:
    try:
        action()
    except ContractError as exc:
        if contains not in str(exc):
            raise ContractError("selftest %s: wrong failure: %s" % (label, exc)) from exc
        return
    raise ContractError("selftest %s: mutation passed" % label)


def run_selftest(data: dict[str, Any], source: str) -> tuple[int, int]:
    cases, _forms, _steps, _helpers = run_fixture(data, source)

    bad_format = copy.deepcopy(data)
    bad_format["format"] = "lisp65-eval-surface-v0"
    _expect_failure(
        "format",
        lambda: validate_fixture(bad_format, "selftest-format"),
        "bad format",
    )

    duplicate_case = copy.deepcopy(data)
    duplicate_case["cases"].append(copy.deepcopy(duplicate_case["cases"][0]))
    _expect_failure(
        "duplicate-case",
        lambda: validate_fixture(duplicate_case, "selftest-duplicate-case"),
        "duplicate case name",
    )

    duplicate_json = '{"format":"%s","format":"%s"}' % (FORMAT, FORMAT)
    _expect_failure(
        "duplicate-json-key",
        lambda: _load_text(duplicate_json, "selftest-duplicate-json"),
        "duplicate JSON key",
    )

    missing_result = copy.deepcopy(data)
    missing_result["cases"][0].pop("expect", None)
    _expect_failure(
        "missing-result",
        lambda: validate_fixture(missing_result, "selftest-missing-result"),
        "exactly one of expect/expect_error",
    )

    conflicting_result = copy.deepcopy(data)
    conflicting_result["cases"][0]["expect_error"] = "!error"
    _expect_failure(
        "conflicting-result",
        lambda: validate_fixture(conflicting_result, "selftest-conflicting-result"),
        "exactly one of expect/expect_error",
    )

    value_drift = copy.deepcopy(data)
    value_drift["cases"][0]["expect"] = "9999"
    _expect_failure(
        "value-drift",
        lambda: run_fixture(value_drift, "selftest-value-drift"),
        "got",
    )
    return 6, cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", nargs="?", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument(
        "--engine",
        choices=["python-p0-compiler-vm"] + sorted(NATIVE_ENGINES),
        default="python-p0-compiler-vm",
    )
    parser.add_argument(
        "--binary",
        type=Path,
        default=ROOT / "build" / "equivalence" / "equivalence-check",
    )
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    try:
        data = _load_fixture(args.fixture)
        if args.selftest:
            checks, cases = run_selftest(data, str(args.fixture))
            print(
                "eval-surface-contract-selftest: PASS checks=%d cases=%d"
                % (checks, cases)
            )
        elif args.engine == "python-p0-compiler-vm":
            cases, forms, steps, helpers = run_fixture(
                data, str(args.fixture), verbose=args.verbose
            )
            print(
                "eval-surface-contract: PASS engine=%s cases=%d forms=%d "
                "p0_steps=%d helpers=%d"
                % (args.engine, cases, forms, steps, helpers)
            )
        else:
            cases, forms = run_native_fixture(
                data,
                args.binary,
                args.engine,
                str(args.fixture),
                verbose=args.verbose,
            )
            print(
                "eval-surface-contract: PASS engine=%s cases=%d forms=%d"
                % (args.engine, cases, forms)
            )
    except Exception as exc:
        label = (
            "eval-surface-contract-selftest" if args.selftest else "eval-surface-contract"
        )
        print("%s: FAIL: %s" % (label, exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
