#!/usr/bin/env python3
"""Run the Python P0 compiler/VM leg of the dialect-v2 Strings matrix."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import bytecode_p0 as P0  # noqa: E402
import bytecode_p0_compiler as P0C  # noqa: E402
import dialect_v2_lists_p0 as FAMILY  # noqa: E402


ENGINE = "python-p0-compiler-vm"
ENGINES = {
    "native-c-treewalk", "native-c-compiler-vm", ENGINE, "lisp-lcc",
}
PROFILES = ("dialect-v1", "dialect-v2")
DEFAULT_FIXTURE = ROOT / "tests/bytecode/dialect-v2/strings/cases.json"
DEFAULT_V1_ROOT = ROOT / "build/equivalence/frozen-v1-f6527d25/source"
DEFAULT_OUTPUT = ROOT / "build/bytecode/dialect-v2/strings"
ABI_LEDGER = ROOT / "config/bytecode-abi-ledger.json"
FROZEN_V1_COMMIT = "f6527d25e2035eae5a98dae7431d641515e2fd2e"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

PROFILE_SOURCES = {
    "dialect-v1": (
        "lib/prelude-m1.lisp", "lib/stdlib-lists.lisp", "lib/stdlib-strings.lisp",
    ),
    "dialect-v2": ("lib/dialect-v2/strings-core.lisp",),
}
PROFILE_FUNCTIONS = {
    "dialect-v1": (
        "%char-list=", "string=", "%char-list<", "string<", "string-append",
        "%subseq-list", "%subseq-list-into", "substring", "append", "%append2",
        "%append2-rev", "%append-lists", "reverse", "%reverse-into", "mapcar",
        "%any-null", "%cars", "%cdrs", "%mapcar-into", "1+",
    ),
    "dialect-v2": (
        "%v2-string-bounds-error", "%v2-substring-codes", "substring",
        "%v2-string-reverse-onto", "%v2-string-append-codes", "string-append",
        "%v2-string=-at", "string=", "%v2-string<-at", "string<",
    ),
}
TOOL_INPUTS = (
    "tools/host-lisp/bytecode_p0.py",
    "tools/host-lisp/bytecode_p0_compiler.py",
    "tools/host-lisp/dialect_v2_lists_p0.py",
    "tools/host-lisp/dialect_v2_strings_p0.py",
)


class StringsP0Error(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=FAMILY._strict_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, FAMILY.ListsP0Error) as exc:
        raise StringsP0Error(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise StringsP0Error("fixture root must be an object")
    return value


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def validate_fixture(value: dict[str, Any]) -> list[dict[str, Any]]:
    if set(value) != {"format", "profile", "family", "cases"}:
        raise StringsP0Error("fixture root schema drift")
    if (
        value["format"] != "lisp65-dialect-v2-strings-cases-v1"
        or value["profile"] != "dialect-v1-v2-differential"
        or value["family"] != "strings"
    ):
        raise StringsP0Error("fixture identity drift")
    cases = value["cases"]
    if not isinstance(cases, list) or len(cases) != 36:
        raise StringsP0Error("fixture must contain exactly 36 Strings cases")
    ids: list[str] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or set(case) != {
            "id", "forms", "migration_anchor", "observations",
        }:
            raise StringsP0Error(f"cases[{index}] schema drift")
        case_id = case["id"]
        if not isinstance(case_id, str) or not ID_RE.fullmatch(case_id):
            raise StringsP0Error(f"cases[{index}] invalid id")
        ids.append(case_id)
        if not isinstance(case["forms"], list) or not case["forms"] or any(
            not isinstance(form, str) or not form.strip() for form in case["forms"]
        ):
            raise StringsP0Error(f"case {case_id} invalid forms")
        observations = case["observations"]
        if not isinstance(observations, dict) or set(observations) != set(PROFILES):
            raise StringsP0Error(f"case {case_id} profile matrix drift")
        for profile in PROFILES:
            engines = observations[profile]
            if not isinstance(engines, dict) or set(engines) != ENGINES:
                raise StringsP0Error(f"case {case_id}/{profile} engine matrix drift")
            if any(not isinstance(result, str) or not result for result in engines.values()):
                raise StringsP0Error(f"case {case_id}/{profile} invalid observation")
    if ids != sorted(set(ids)):
        raise StringsP0Error("fixture ids must be sorted and unique")
    return cases


def _source_text(profile: str, root: Path, relative: str) -> str:
    path = root / relative
    if path.is_file():
        return path.read_text(encoding="utf-8")
    if profile != "dialect-v1":
        raise StringsP0Error(f"missing source: {path}")
    process = subprocess.run(
        ["git", "show", f"{FROZEN_V1_COMMIT}:{relative}"],
        cwd=ROOT, capture_output=True, text=True, timeout=10, check=False,
    )
    if process.returncode or not process.stdout:
        raise StringsP0Error(f"frozen v1 source unavailable: {relative}")
    return process.stdout


def _profile_forms(profile: str, root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    forms: dict[str, Any] = {}
    bindings = []
    for relative in PROFILE_SOURCES[profile]:
        text = _source_text(profile, root, relative)
        bindings.append(
            {"path": relative, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
        )
        for form in P0C.parse_all(text):
            if (
                isinstance(form, list) and len(form) >= 4
                and form[0] == "defun" and isinstance(form[1], str)
            ):
                forms[form[1]] = form
    missing = sorted(set(PROFILE_FUNCTIONS[profile]) - set(forms))
    if missing:
        raise StringsP0Error(f"{profile} source misses functions: {missing}")
    return forms, bindings


def _compile_profile(
    profile: str, root: Path, cases: list[dict[str, Any]],
) -> tuple[P0.Heap, dict[int, P0.CodeObject], list[dict[str, str]]]:
    forms, bindings = _profile_forms(profile, root)
    required = PROFILE_FUNCTIONS[profile]
    entries = [f"%ap85-strings-p0-case-{index}" for index in range(len(cases))]
    heap = P0C.prepare_heap([*required, *entries])
    by_name: dict[str, P0.CodeObject] = {}
    strict = profile == "dialect-v2"

    def add(name: str, code: P0.CodeObject) -> None:
        prior = by_name.get(name)
        if prior is not None and prior.encode() != code.encode():
            raise StringsP0Error(f"conflicting code object: {name}")
        by_name[name] = code

    for name in required:
        compiled, code, helpers = P0C.compile_top_form_with_helpers(
            forms[name], heap, strict_arity=strict, abi_profile=profile,
        )
        add(compiled, code)
        for helper_name, helper in helpers:
            add(helper_name, helper)

    for entry, case in zip(entries, cases):
        parsed = [FAMILY._lower_immediate_calls(P0C.parse_one(form)) for form in case["forms"]]
        expression = parsed[0] if len(parsed) == 1 else ["progn", *parsed]
        compiled, code, helpers = P0C.compile_top_form_with_helpers(
            ["defun", entry, [], expression], heap,
            strict_arity=strict, abi_profile=profile,
        )
        add(compiled, code)
        for helper_name, helper in helpers:
            add(helper_name, helper)
    return heap, {heap.intern(name): code for name, code in by_name.items()}, bindings


def _normalize_error(exc: P0.VMError) -> str:
    if exc.status == "ArityError":
        return "!error:arity"
    if exc.status == "DirMiss":
        return "!error:undefined-public-name"
    return "!error:runtime"


def _provenance(profile: str, bindings: list[dict[str, str]]) -> dict[str, Any]:
    tools = [{"path": path, "sha256": _sha_file(ROOT / path)} for path in TOOL_INPUTS]
    build = {"profile": profile, "strict_arity": profile == "dialect-v2", "tools": tools}
    return {
        "source_commit": FROZEN_V1_COMMIT if profile == "dialect-v1" else None,
        "binary_sha256": hashlib.sha256(_canonical(tools)).hexdigest(),
        "build_profile_sha256": hashlib.sha256(_canonical(build)).hexdigest(),
        "preload_sha256": hashlib.sha256(_canonical(bindings)).hexdigest(),
    }


def run(fixture: Path, v1_root: Path, output_dir: Path) -> int:
    cases = validate_fixture(_load(fixture))
    roots = {"dialect-v1": v1_root, "dialect-v2": ROOT}
    ledger = _load(ABI_LEDGER)
    fixture_sha = _sha_file(fixture)
    output_dir.mkdir(parents=True, exist_ok=True)
    failed = 0
    for profile in PROFILES:
        heap, directory, bindings = _compile_profile(profile, roots[profile], cases)
        verdict_cases = []
        for index, case in enumerate(cases):
            case_heap = heap.clone()
            vm = P0.P0VM(
                heap=case_heap, directory=dict(directory), abi_profile=profile,
                abi_ledger=ledger if profile == "dialect-v2" else None,
            )
            entry = case_heap.intern(f"%ap85-strings-p0-case-{index}")
            try:
                observed = case_heap.obj_to_text(vm.run(directory[entry], []))
            except P0.VMError as exc:
                observed = _normalize_error(exc)
            expected = case["observations"][profile][ENGINE]
            accepted = observed == expected
            failed += int(not accepted)
            verdict_cases.append(
                {
                    "id": case["id"], "decision": case["migration_anchor"],
                    "verdict": "accept" if accepted else "reject",
                    "result_sha256": hashlib.sha256(observed.encode("utf-8")).hexdigest(),
                }
            )
            print(
                f"{profile}/{ENGINE}/{case['id']}: "
                f"{'PASS' if accepted else 'FAIL'} observed={observed} expected={expected}"
            )
        verdict = {
            "format": "lisp65-dialect-v2-family-verdict-v1", "family": "strings",
            "profile": profile, "engine": ENGINE, "fixture_sha256": fixture_sha,
            "provenance": _provenance(profile, bindings), "cases": verdict_cases,
        }
        (output_dir / f"{profile}-{ENGINE}-verdict.json").write_bytes(_canonical(verdict))
    print(
        f"dialect-v2-strings-p0: {'PASS' if failed == 0 else 'FAIL'} "
        f"cases={len(cases)} runs={len(cases) * 2} failed={failed}"
    )
    return 0 if failed == 0 else 1


def selftest(fixture: Path) -> None:
    value = _load(fixture)
    cases = validate_fixture(value)
    missing = copy.deepcopy(value)
    del missing["cases"][0]["observations"]["dialect-v2"][ENGINE]
    try:
        validate_fixture(missing)
    except StringsP0Error:
        pass
    else:
        raise StringsP0Error("fixture accepted a missing Python-P0 observation")
    for case in cases:
        if case["id"].startswith("internal-") and not all(
            case["observations"][profile][ENGINE].startswith("!error:")
            for profile in PROFILES
        ):
            raise StringsP0Error(f"internal capability became a designator: {case['id']}")
    print(
        f"dialect-v2-strings-p0: SELFTEST PASS cases={len(cases)} "
        "mutations=1 internal-designators=4"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--source-root-v1", type=Path, default=DEFAULT_V1_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            selftest(args.fixture)
            return 0
        return run(args.fixture, args.source_root_v1, args.output_dir)
    except (StringsP0Error, P0C.CompileError, P0.VMError, OSError) as exc:
        print(f"dialect-v2-strings-p0: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
