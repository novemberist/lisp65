#!/usr/bin/env python3
"""Run the Python P0 compiler/VM leg of the dialect-v2 Lists matrix."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import bytecode_p0 as P0  # noqa: E402
import bytecode_p0_compiler as P0C  # noqa: E402
import bytecode_p0_stdlib as STDLIB  # noqa: E402


ENGINE = "python-p0-compiler-vm"
ENGINES = (
    "native-c-treewalk",
    "native-c-compiler-vm",
    ENGINE,
    "lisp-lcc",
)
PROFILES = ("dialect-v1", "dialect-v2")
DEFAULT_FIXTURE = ROOT / "tests/bytecode/dialect-v2/lists/cases.json"
DEFAULT_V1_ROOT = ROOT / "build/equivalence/frozen-v1-f6527d25/source"
DEFAULT_OUTPUT = ROOT / "build/bytecode/dialect-v2/lists"
ABI_LEDGER = ROOT / "config/bytecode-abi-ledger.json"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

PROFILE_SOURCES = {
    "dialect-v1": ("lib/prelude-m1.lisp", "lib/stdlib-lists.lisp"),
    "dialect-v2": (
        "lib/dialect-v2/lists-core.lisp",
        "lib/dialect-v2/lists-library.lisp",
    ),
}
PROFILE_FUNCTIONS = {
    "dialect-v1": (
        "member", "assoc", "find", "assq", "find-if", "count",
        "%count-from", "position", "%position-from", "reverse", "%reverse-into",
        "list", "1+", "1-", "zerop", "nth", "nthcdr",
    ),
    "dialect-v2": (
        "member", "assoc", "find", "filter", "%v2-filter-into", "list",
        "count", "%v2-count-from", "position", "%v2-position-from", "reverse",
        "%v2-library-reverse-into", "%v2-reverse-into",
        "nth", "%v2-nth", "nthcdr", "%v2-nthcdr",
    ),
}
V2_LIBRARY_ONLY = {
    "count", "%v2-count-from", "position", "%v2-position-from", "reverse",
    "%v2-library-reverse-into",
}
PUBLIC_HEADERS = {
    "dialect-v1": {
        name: (2, 0x00)
        for name in ("member", "assoc", "find", "assq", "find-if", "count", "position")
    },
    "dialect-v2": {
        "member": (3, 0x06),
        "assoc": (3, 0x06),
        "find": (2, 0x02),
        "filter": (2, 0x02),
        "count": (2, 0x02),
        "position": (2, 0x02),
    },
}
TOOL_INPUTS = (
    "tools/host-lisp/bytecode_p0.py",
    "tools/host-lisp/bytecode_p0_compiler.py",
    "tools/host-lisp/bytecode_p0_stdlib.py",
    "tools/host-lisp/dialect_v2_lists_p0.py",
)


class ListsP0Error(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ListsP0Error(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ListsP0Error(f"fixture is not a regular file: {path}")
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except ListsP0Error:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ListsP0Error(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ListsP0Error("fixture root must be an object")
    return value


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def validate_fixture(value: dict[str, Any]) -> list[dict[str, Any]]:
    required_root = {"format", "profile", "family", "cases"}
    if not required_root <= set(value):
        raise ListsP0Error(f"fixture root misses keys: {sorted(required_root - set(value))}")
    if (
        value["format"] != "lisp65-dialect-v2-lists-cases-v1"
        or value["profile"] != "dialect-v1-v2-differential"
        or value["family"] != "lists"
    ):
        raise ListsP0Error("fixture identity drift")
    cases = value["cases"]
    if not isinstance(cases, list) or not cases:
        raise ListsP0Error("fixture cases must be a non-empty list")
    ids = []
    for index, case in enumerate(cases):
        required = {"id", "tier", "forms", "migration_anchor", "observations"}
        if not isinstance(case, dict) or not required <= set(case):
            raise ListsP0Error(f"cases[{index}] schema drift")
        case_id = case["id"]
        if not isinstance(case_id, str) or not ID_RE.fullmatch(case_id):
            raise ListsP0Error(f"cases[{index}] has invalid id")
        ids.append(case_id)
        if case["tier"] not in {"core", "library"}:
            raise ListsP0Error(f"case {case_id} has invalid tier")
        forms = case["forms"]
        if not isinstance(forms, list) or not forms or any(
            not isinstance(form, str) or not form.strip() for form in forms
        ):
            raise ListsP0Error(f"case {case_id} has invalid forms")
        observations = case["observations"]
        if not isinstance(observations, dict) or set(observations) != set(PROFILES):
            raise ListsP0Error(f"case {case_id} profile matrix drift")
        for profile in PROFILES:
            engines = observations[profile]
            if not isinstance(engines, dict) or set(engines) != set(ENGINES):
                raise ListsP0Error(f"case {case_id}/{profile} engine matrix drift")
            if any(
                not isinstance(engines[engine], str) or not engines[engine]
                for engine in ENGINES
            ):
                raise ListsP0Error(f"case {case_id}/{profile} has invalid observations")
    if ids != sorted(set(ids)):
        raise ListsP0Error("fixture case ids must be sorted and unique")
    return cases


def _source_paths(profile: str, source_root: Path) -> list[Path]:
    paths = []
    for relative in PROFILE_SOURCES[profile]:
        path = source_root / relative
        if path.is_symlink() or not path.is_file():
            raise ListsP0Error(f"missing {profile} source: {path}")
        paths.append(path)
    return paths


def _validate_v1_export(source_root: Path) -> None:
    manifest_path = source_root / "export-manifest.json"
    manifest = _load(manifest_path)
    commit = "f6527d25e2035eae5a98dae7431d641515e2fd2e"
    if (
        manifest.get("format") != "lisp65-frozen-source-export-v1"
        or manifest.get("profile") != "dialect-v1"
        or manifest.get("source_commit") != commit
    ):
        raise ListsP0Error("dialect-v1 frozen export identity drift")
    raw_bindings = manifest.get("bindings")
    if not isinstance(raw_bindings, list):
        raise ListsP0Error("dialect-v1 frozen export lacks bindings")
    bindings = {
        item.get("path"): item
        for item in raw_bindings
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    for relative in PROFILE_SOURCES["dialect-v1"]:
        item = bindings.get(relative)
        path = source_root / relative
        if (
            not isinstance(item, dict)
            or item.get("origin") != f"git:{commit}:{relative}"
            or item.get("sha256") != _sha_file(path)
        ):
            raise ListsP0Error(f"dialect-v1 frozen export binding drift: {relative}")


def _compile_profile(
    profile: str, source_root: Path, cases: list[dict[str, Any]]
) -> tuple[P0.Heap, dict[int, P0.CodeObject], dict[str, P0.CodeObject], list[dict[str, str]]]:
    sources = _source_paths(profile, source_root)
    forms, defuns, _macros = STDLIB._source_top_defs([str(path) for path in sources])
    required = PROFILE_FUNCTIONS[profile]
    missing = sorted(set(required) - set(defuns))
    if missing:
        raise ListsP0Error(f"{profile} source misses functions: {missing}")
    entry_names = [f"%ap85-p0-case-{index}" for index in range(len(cases))]
    heap = P0C.prepare_heap(list(required) + entry_names)
    code_by_name: dict[str, P0.CodeObject] = {}
    strict = profile == "dialect-v2"

    def add(name: str, code: P0.CodeObject) -> None:
        if name in code_by_name:
            if code_by_name[name].encode() == code.encode():
                return
            raise ListsP0Error(f"{profile} conflicting code object: {name}")
        code_by_name[name] = code

    for name in required:
        compiled_name, code, helpers = P0C.compile_top_form_with_helpers(
            forms[name], heap, strict_arity=strict
        )
        if compiled_name != name:
            raise ListsP0Error(f"{profile} compiled name drift: {name}")
        add(name, code)
        for helper_name, helper in helpers:
            add(helper_name, helper)

    for entry, case in zip(entry_names, cases):
        parsed = [_lower_immediate_calls(P0C.parse_one(form)) for form in case["forms"]]
        expressions = []
        for parsed_form in parsed:
            if (
                isinstance(parsed_form, list)
                and len(parsed_form) >= 4
                and parsed_form[0] == "defun"
            ):
                support_name, support_code, support_helpers = (
                    P0C.compile_top_form_with_helpers(
                        parsed_form, heap, strict_arity=strict
                    )
                )
                add(support_name, support_code)
                for helper_name, helper in support_helpers:
                    add(helper_name, helper)
            else:
                expressions.append(parsed_form)
        if not expressions:
            raise ListsP0Error(f"case {case['id']} has no executable form")
        expression = expressions[0] if len(expressions) == 1 else ["progn", *expressions]
        form = ["defun", entry, [], expression]
        compiled_name, code, helpers = P0C.compile_top_form_with_helpers(
            form, heap, strict_arity=strict
        )
        add(compiled_name, code)
        for helper_name, helper in helpers:
            add(helper_name, helper)

    directory = {heap.intern(name): code for name, code in code_by_name.items()}
    bindings = [
        {"path": relative, "sha256": _sha_file(path)}
        for relative, path in zip(PROFILE_SOURCES[profile], sources)
    ]
    return heap, directory, code_by_name, bindings


def _lower_immediate_calls(form: Any) -> Any:
    """Route immediate lambdas through real CodeObjects for profile arity checks."""
    if isinstance(form, P0C.DottedList):
        return P0C.DottedList(
            tuple(_lower_immediate_calls(item) for item in form.items),
            _lower_immediate_calls(form.tail),
        )
    if not isinstance(form, list) or not form:
        return form
    if form[0] == "quote":
        return form
    if isinstance(form[0], list) and form[0] and form[0][0] == "lambda":
        return [
            "funcall",
            _lower_immediate_calls(form[0]),
            *[_lower_immediate_calls(item) for item in form[1:]],
        ]
    return [_lower_immediate_calls(item) for item in form]


def _header_report(profile: str, code_by_name: dict[str, P0.CodeObject]) -> dict[str, Any]:
    functions = []
    for name, (expected_nargs, expected_flags) in PUBLIC_HEADERS[profile].items():
        code = code_by_name.get(name)
        if code is None:
            raise ListsP0Error(f"{profile} header function is missing: {name}")
        if code.nargs != expected_nargs or code.flags != expected_flags:
            raise ListsP0Error(
                f"{profile}/{name} header drift: "
                f"nargs={code.nargs} flags=0x{code.flags:02x}, "
                f"expected nargs={expected_nargs} flags=0x{expected_flags:02x}"
            )
        functions.append(
            {
                "name": name,
                "nargs": code.nargs,
                "flags": code.flags,
                "strict_arity": bool(code.flags & P0.CO_FLAG_STRICT_ARITY),
                "optional_count": code.flags >> P0.CO_FLAG_OPTIONAL_SHIFT,
                "rest": bool(code.flags & P0.CO_FLAG_REST),
            }
        )
    return {"profile": profile, "functions": functions}


def _normalize_error(exc: P0.VMError) -> str:
    if exc.status == "ArityError":
        return "!error:arity"
    if exc.status == "DirMiss":
        return "!error:undefined-public-name"
    return "!error:runtime"


def _run_cases(
    profile: str,
    heap: P0.Heap,
    directory: dict[int, P0.CodeObject],
    cases: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    abi_ledger = _load(ABI_LEDGER) if profile == "dialect-v2" else None
    verdicts = []
    failed = 0
    for index, case in enumerate(cases):
        entry = heap.intern(f"%ap85-p0-case-{index}")
        case_heap = heap.clone()
        case_directory = dict(directory)
        if profile == "dialect-v2" and case["tier"] == "core":
            for name in V2_LIBRARY_ONLY:
                case_directory.pop(heap.intern(name), None)
        vm = P0.P0VM(
            heap=case_heap,
            directory=case_directory,
            abi_profile=profile,
            abi_ledger=abi_ledger,
        )
        try:
            result = vm.run(case_directory[entry], [])
            observed = case_heap.obj_to_text(result)
        except P0.VMError as exc:
            observed = _normalize_error(exc)
        except RecursionError:
            observed = "!error:runtime"
        expected = case["observations"][profile][ENGINE]
        accepted = observed == expected
        failed += int(not accepted)
        verdicts.append(
            {
                "id": case["id"],
                "decision": case["migration_anchor"],
                "verdict": "accept" if accepted else "reject",
                "result_sha256": _sha_bytes(observed.encode("utf-8")),
            }
        )
        print(
            f"{profile}/{ENGINE}/{case['id']}: "
            f"{'PASS' if accepted else 'FAIL'} observed={observed} expected={expected}"
        )
    return verdicts, failed


def _provenance(
    profile: str, bindings: list[dict[str, str]], source_root: Path
) -> dict[str, Any]:
    tool_bindings = [{"path": path, "sha256": _sha_file(ROOT / path)} for path in TOOL_INPUTS]
    engine_sha = _sha_bytes(_canonical(tool_bindings))
    build = {
        "engine": ENGINE,
        "profile": profile,
        "strict_arity": profile == "dialect-v2",
        "tools": tool_bindings,
        "sources": bindings,
    }
    preload = b"".join(
        relative.encode("utf-8") + b"\0" + (source_root / relative).read_bytes()
        for relative in PROFILE_SOURCES[profile]
    )
    return {
        "source_commit": (
            "f6527d25e2035eae5a98dae7431d641515e2fd2e"
            if profile == "dialect-v1" else None
        ),
        "binary_sha256": engine_sha,
        "build_profile_sha256": _sha_bytes(_canonical(build)),
        "preload_sha256": _sha_bytes(preload),
    }


def run(fixture_path: Path, v1_root: Path, output_dir: Path) -> int:
    fixture = _load(fixture_path)
    cases = validate_fixture(fixture)
    _validate_v1_export(v1_root)
    roots = {"dialect-v1": v1_root, "dialect-v2": ROOT}
    fixture_sha = _sha_file(fixture_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    failed = 0
    for profile in PROFILES:
        heap, directory, code_by_name, bindings = _compile_profile(
            profile, roots[profile], cases
        )
        reports.append(_header_report(profile, code_by_name))
        verdict_cases, profile_failed = _run_cases(profile, heap, directory, cases)
        failed += profile_failed
        verdict = {
            "format": "lisp65-dialect-v2-family-verdict-v1",
            "family": "lists",
            "profile": profile,
            "engine": ENGINE,
            "fixture_sha256": fixture_sha,
            "provenance": _provenance(profile, bindings, roots[profile]),
            "cases": verdict_cases,
        }
        (output_dir / f"{profile}-{ENGINE}-verdict.json").write_bytes(_canonical(verdict))
    report = {
        "format": "lisp65-dialect-v2-lists-p0-arity-v1",
        "engine": ENGINE,
        "fixture_sha256": fixture_sha,
        "profiles": reports,
        "result": "passed" if failed == 0 else "failed",
    }
    (output_dir / "lists-python-p0-arity-report.json").write_bytes(_canonical(report))
    print(
        f"dialect-v2-lists-p0: {'PASS' if failed == 0 else 'FAIL'} "
        f"cases={len(cases)} runs={len(cases) * len(PROFILES)} failed={failed}"
    )
    return 0 if failed == 0 else 1


def _synthetic_fixture() -> dict[str, Any]:
    raw = [
        ("arity-member-too-few", "(member 'a)", "nil", "!error:arity"),
        ("assoc-symbol", "(assoc 'b '((a 1) (b 2)))", "(b 2)", "(b 2)"),
        ("assq-removed", "(assq 'b '((a 1) (b 2)))", "(b 2)", "!error:undefined-public-name"),
        ("filter-added", "(filter (lambda (x) (> x 1)) '(1 2 3))", "!error:undefined-public-name", "(2 3)"),
        ("find-if-removed", "(find-if (lambda (x) (> x 2)) '(1 2 3))", "3", "!error:undefined-public-name"),
        ("find-predicate", "(find (lambda (x) (> x 2)) '(1 2 3 4))", "nil", "3"),
        ("member-symbol", "(member 'b '(a b c))", "(b c)", "(b c)"),
        ("position-predicate", "(position (lambda (x) (> x 2)) '(1 2 3 4))", "nil", "2"),
    ]
    cases = []
    for case_id, form, v1, v2 in raw:
        observations = {}
        for profile, expected in (("dialect-v1", v1), ("dialect-v2", v2)):
            observations[profile] = {engine: expected for engine in ENGINES}
        cases.append(
            {
                "id": case_id,
                "tier": "library" if case_id == "position-predicate" else "core",
                "forms": [form],
                "migration_anchor": None if v1 == v2 else "decision:selftest",
                "observations": observations,
            }
        )
    return {
        "format": "lisp65-dialect-v2-lists-cases-v1",
        "profile": "dialect-v1-v2-differential",
        "family": "lists",
        "cases": sorted(cases, key=lambda item: item["id"]),
    }


def selftest(v1_root: Path) -> None:
    fixture = _synthetic_fixture()
    validate_fixture(fixture)
    missing = copy.deepcopy(fixture)
    del missing["cases"][0]["observations"]["dialect-v2"][ENGINE]
    try:
        validate_fixture(missing)
    except ListsP0Error:
        pass
    else:
        raise ListsP0Error("selftest accepted a missing Python engine observation")
    with tempfile.TemporaryDirectory(prefix="lisp65-ap85-p0-") as raw:
        directory = Path(raw)
        fixture_path = directory / "cases.json"
        fixture_path.write_bytes(_canonical(fixture))
        if run(fixture_path, v1_root, directory / "out") != 0:
            raise ListsP0Error("selftest semantic matrix failed")
        report = json.loads(
            (directory / "out/lists-python-p0-arity-report.json").read_text(encoding="utf-8")
        )
        if report["result"] != "passed":
            raise ListsP0Error("selftest arity report failed")
    print("dialect-v2-lists-p0: SELFTEST PASS mutations=1 semantic_cases=8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--source-root-v1", type=Path, default=DEFAULT_V1_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            selftest(args.source_root_v1)
            return 0
        return run(args.fixture, args.source_root_v1, args.output_dir)
    except (ListsP0Error, P0C.CompileError, STDLIB.StdlibCheckError, OSError) as exc:
        print(f"dialect-v2-lists-p0: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
