#!/usr/bin/env python3
"""Materialize token-safe dialect-v2 Workbench suites and source copies."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST_TOOLS = ROOT / "tools" / "host-lisp"
if str(HOST_TOOLS) not in sys.path:
    sys.path.insert(0, str(HOST_TOOLS))

import bytecode_p0_stdlib as Stdlib  # noqa: E402


DEFAULT_CLOSURE = ROOT / "config" / "v2-workbench-artifact-closure.json"
DEFAULT_OUTPUT = ROOT / "build" / "bytecode" / "dialect-v2"
FORMAT = "lisp65-v2-workbench-codemod-receipt-v1"
EXPECTED_ARTIFACTS = ("resident", "ide", "idex", "m65d")
BRIDGE_SOURCE = "lib/stdlib-einsuite-bridges.lisp"
LCC_PROFILE = "lib/dialect-v2/lcc-profile.lisp"
EVAL_RUNTIME = "lib/dialect-v2/eval-runtime.lisp"
EVAL_RUNTIME_PRIVATE_INLINE = ("%number->string-result",)
DIRECTORY_ONLY_EXT_RECLAIM_INLINE = ("%lcc-wrap", "%load-lib-note-loaded")
DIRECTORY_ONLY_IDE_EXPORTS = (
    "%ide-buffer-with-lines-point",
    "%ide-char-drop",
    "%ide-char-take-into",
    "%ide-dispatch-command",
    "%ide-line-at",
    "%ide-lines-replace",
    "%ide-lines-replace-range",
    "%ide-mini-start",
    "%ide-state-with-buffer",
    "%ide-state-with-message",
    "%ide-x",
)
DIRECTORY_ONLY_LATE_BOUND_EXPORTS = ("%ide-x",)
NUMBER_TO_STRING_FIXTURE = (
    "tests/bytecode/dialect-v2/number-to-string/cases.json"
)
LCC_PROFILE_TAILCALL_SELF = (
    "%lcc-v2-drop",
    "%lcc-v2-fixed-binds",
    "%lcc-v2-param-seen-p",
)
REPLACEMENTS = {
    "string->list": "%string-codes",
    "list->string": "%string-from-codes",
}
RESOLUTION_KEYS = {
    "extends",
    "cases_from_suites",
    "functions_from_sources",
    "remove_sources",
    "remove_functions",
    "remove_functions_from_sources",
    "remove_cases",
    "remove_cases_prefixes",
}


class CodemodError(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CodemodError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise CodemodError(f"{label} must be a JSON object")
    return value


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise CodemodError(f"path escapes repository: {path}") from exc


def _repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        resolved = path.resolve()
    else:
        resolved = (ROOT / path).resolve()
    _relative(resolved)
    return resolved


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _suite_json_bytes(value: Any) -> bytes:
    # disk_files insertion order models the on-disk directory order used by
    # the IDE fixtures; sorting that object changes observable behavior.
    return (json.dumps(value, indent=2) + "\n").encode("utf-8")


def _atom_end(text: str, start: int) -> int:
    delimiters = "()[]{}'`,;\""
    at = start
    while at < len(text) and not text[at].isspace() and text[at] not in delimiters:
        if text.startswith("#|", at):
            break
        at += 1
    return at


def _skip_string(text: str, start: int) -> int:
    at = start + 1
    while at < len(text):
        if text[at] == "\\":
            at += 2
        elif text[at] == '"':
            return at + 1
        else:
            at += 1
    raise CodemodError("unterminated Lisp string")


def _skip_block_comment(text: str, start: int) -> int:
    depth = 1
    at = start + 2
    while at < len(text):
        if text.startswith("#|", at):
            depth += 1
            at += 2
        elif text.startswith("|#", at):
            depth -= 1
            at += 2
            if depth == 0:
                return at
        else:
            at += 1
    raise CodemodError("unterminated Lisp block comment")


def _skip_character(text: str, start: int) -> int:
    at = start + 2
    if at >= len(text):
        return at
    if text[at].isspace():
        return at
    if text[at] in "()[]{}'`,;\"":
        return at + 1
    return _atom_end(text, at)


def rewrite_tokens(text: str) -> tuple[str, dict[str, int]]:
    """Rewrite exact Lisp atoms while preserving strings and comments byte-for-byte."""
    counts = {name: 0 for name in REPLACEMENTS}
    output: list[str] = []
    code_tokens: list[tuple[str, str]] = []
    at = 0
    while at < len(text):
        if text[at] == '"':
            end = _skip_string(text, at)
            code_tokens.append(("opaque", "string"))
        elif text[at] == ";":
            newline = text.find("\n", at)
            end = len(text) if newline < 0 else newline
        elif text.startswith("#|", at):
            end = _skip_block_comment(text, at)
        elif text.startswith("#\\", at):
            end = _skip_character(text, at)
            code_tokens.append(("opaque", "character"))
        elif text[at].isspace():
            output.append(text[at])
            at += 1
            continue
        elif text[at] in "()[]{}'`,":
            token_kind = "quote" if text[at] in "'`" else "delimiter"
            code_tokens.append((token_kind, text[at]))
            output.append(text[at])
            at += 1
            continue
        else:
            end = _atom_end(text, at)
            token = text[at:end]
            replacement = REPLACEMENTS.get(token)
            quoted = bool(code_tokens and code_tokens[-1][0] == "quote")
            function_designator = (
                len(code_tokens) >= 2
                and code_tokens[-2] == ("delimiter", "(")
                and code_tokens[-1] == ("atom", "function")
            )
            if replacement is not None and not quoted:
                if function_designator:
                    output.append(
                        "(lambda (value) (%s value))" % replacement
                    )
                else:
                    output.append(replacement)
                counts[token] += 1
            else:
                output.append(token)
            code_tokens.append(("atom", token))
            at = end
            continue
        output.append(text[at:end])
        at = end
    return "".join(output), counts


def _top_level_forms(text: str) -> list[tuple[int, int]]:
    forms: list[tuple[int, int]] = []
    depth = 0
    start: int | None = None
    at = 0
    while at < len(text):
        if text[at] == '"':
            at = _skip_string(text, at)
            continue
        if text[at] == ";":
            newline = text.find("\n", at)
            at = len(text) if newline < 0 else newline
            continue
        if text.startswith("#|", at):
            at = _skip_block_comment(text, at)
            continue
        if text.startswith("#\\", at):
            at = _skip_character(text, at)
            continue
        if text[at] == "(":
            if depth == 0:
                start = at
            depth += 1
        elif text[at] == ")":
            if depth == 0:
                raise CodemodError("unmatched closing parenthesis in Lisp source")
            depth -= 1
            if depth == 0:
                if start is None:
                    raise CodemodError("missing top-level form start")
                forms.append((start, at + 1))
                start = None
        at += 1
    if depth != 0:
        raise CodemodError("unterminated top-level form in Lisp source")
    return forms


def _form_atoms(form: str, limit: int = 2) -> list[str]:
    atoms: list[str] = []
    at = 0
    while at < len(form) and len(atoms) < limit:
        if form[at] == '"':
            at = _skip_string(form, at)
        elif form[at] == ";":
            newline = form.find("\n", at)
            at = len(form) if newline < 0 else newline
        elif form.startswith("#|", at):
            at = _skip_block_comment(form, at)
        elif form.startswith("#\\", at):
            at = _skip_character(form, at)
        elif form[at].isspace() or form[at] in "()[]{}'`,":
            at += 1
        else:
            end = _atom_end(form, at)
            atoms.append(form[at:end])
            at = end
    return atoms


def remove_bridge_defuns(text: str) -> tuple[str, dict[str, int]]:
    removals = {name: 0 for name in REPLACEMENTS}
    spans: list[tuple[int, int]] = []
    for start, end in _top_level_forms(text):
        atoms = _form_atoms(text[start:end])
        if len(atoms) >= 2 and atoms[0] == "defun" and atoms[1] in removals:
            removals[atoms[1]] += 1
            spans.append((start, end))
    output: list[str] = []
    cursor = 0
    for start, end in spans:
        output.append(text[cursor:start])
        cursor = end
    output.append(text[cursor:])
    return "".join(output), removals


def _require_bridge_defuns(counts: dict[str, int]) -> None:
    wrong = {name: count for name, count in counts.items() if count != 1}
    if wrong:
        raise CodemodError(
            "bridge source must contain exactly one top-level defun for each converter: "
            + ", ".join(f"{name}={count}" for name, count in sorted(wrong.items()))
        )


def _suite_dependencies(path: Path, found: set[Path] | None = None) -> set[Path]:
    if found is None:
        found = set()
    path = path.resolve()
    if path in found:
        return found
    found.add(path)
    value = _read_json(path, f"suite {path}")
    base = path.parent
    for key in ("extends", "cases_from_suites"):
        refs = value.get(key, [])
        if isinstance(refs, str):
            refs = [refs]
        if not isinstance(refs, list) or not all(isinstance(item, str) for item in refs):
            raise CodemodError(f"suite {path} has invalid {key}")
        for ref in refs:
            dependency = Path(Stdlib._suite_path(ref, str(base))).resolve()
            _suite_dependencies(dependency, found)
    return found


def _artifact_specs(closure: dict[str, Any]) -> list[dict[str, Any]]:
    if (
        closure.get("format") != "lisp65-v2-workbench-artifact-closure-v1"
        or closure.get("target_abi_profile") != "dialect-v2"
    ):
        raise CodemodError("artifact closure format/profile drift")
    artifacts = closure.get("artifacts")
    if not isinstance(artifacts, list) or tuple(item.get("id") for item in artifacts) != EXPECTED_ARTIFACTS:
        raise CodemodError("artifact closure must contain resident, ide, idex, m65d in order")
    for item in artifacts:
        if not isinstance(item.get("source_suite"), str):
            raise CodemodError(f"artifact {item.get('id')} has no source_suite")
    return artifacts


def _source_output(output_root: Path, source: str) -> Path:
    return output_root / "sources" / source


def _suite_output(output_root: Path, source_suite: str) -> Path:
    return output_root / "suites" / Path(source_suite).name


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def generate(closure_path: Path, output_root: Path) -> Path:
    closure_path = closure_path.resolve()
    output_root = output_root.resolve()
    _relative(closure_path)
    _relative(output_root)
    closure = _read_json(closure_path, "v2 Workbench artifact closure")
    specs = _artifact_specs(closure)

    resolved: dict[str, dict[str, Any]] = {}
    suite_inputs: set[Path] = set()
    suite_outputs: dict[str, Path] = {}
    for spec in specs:
        suite_path = _repo_path(spec["source_suite"])
        suite_inputs.update(_suite_dependencies(suite_path))
        try:
            suite = Stdlib._read_suite(str(suite_path))
        except (OSError, ValueError, Stdlib.StdlibCheckError) as exc:
            raise CodemodError(
                f"cannot resolve suite {spec['source_suite']}: {exc}"
            ) from exc
        resolved[spec["id"]] = {
            key: value for key, value in suite.items()
            if not key.startswith("_") and key not in RESOLUTION_KEYS
        }
        declared_output = _repo_path(spec["suite"])
        expected_output = _suite_output(DEFAULT_OUTPUT, spec["source_suite"])
        if declared_output != expected_output:
            raise CodemodError(
                f"artifact {spec['id']} suite output drifts from the canonical path"
            )
        suite_outputs[spec["id"]] = _suite_output(
            output_root, spec["source_suite"]
        )

    resident_sources = resolved["resident"].get("sources")
    if not isinstance(resident_sources, list) or not all(isinstance(item, str) for item in resident_sources):
        raise CodemodError("resolved resident suite has invalid sources")
    staging_sources = (EVAL_RUNTIME, LCC_PROFILE)
    resident_sources = [
        item for item in resident_sources if item not in staging_sources
    ]
    resident_sources.extend(staging_sources)
    resolved["resident"]["sources"] = resident_sources
    profile_functions = Stdlib._defun_names(list(staging_sources))
    resolved["resident"]["functions"] = Stdlib._append_unique(
        resolved["resident"].get("functions", []), profile_functions
    )
    resolved["resident"]["private_inline_functions"] = Stdlib._append_unique(
        resolved["resident"].get("private_inline_functions", []),
        EVAL_RUNTIME_PRIVATE_INLINE,
    )
    old_private_minimum = resolved["resident"].get("min_private_inline_functions", 0)
    if not isinstance(old_private_minimum, int) or old_private_minimum < 0:
        raise CodemodError("resolved resident suite has invalid min_private_inline_functions")
    resolved["resident"]["min_private_inline_functions"] = max(
        old_private_minimum, len(resolved["resident"]["private_inline_functions"])
    )
    old_tailcalls = resolved["resident"].get("tailcall_self", [])
    if not isinstance(old_tailcalls, list):
        raise CodemodError("resolved resident suite has invalid tailcall_self")
    resolved["resident"]["tailcall_self"] = Stdlib._append_unique(
        [name for name in old_tailcalls if name not in profile_functions],
        LCC_PROFILE_TAILCALL_SELF,
    )

    source_names: set[str] = set()
    for artifact_id, suite in resolved.items():
        sources = suite.get("sources")
        if not isinstance(sources, list) or not all(isinstance(item, str) for item in sources):
            raise CodemodError(f"resolved {artifact_id} suite has invalid sources")
        source_names.update(sources)

    source_data: dict[str, bytes] = {}
    source_counts = {name: 0 for name in REPLACEMENTS}
    bridge_counts = {name: 0 for name in REPLACEMENTS}
    for source in sorted(source_names):
        source_path = _repo_path(source)
        try:
            text = source_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise CodemodError(f"cannot read source {source}: {exc}") from exc
        if source == BRIDGE_SOURCE:
            text, bridge_counts = remove_bridge_defuns(text)
            _require_bridge_defuns(bridge_counts)
        rewritten, counts = rewrite_tokens(text)
        for name, count in counts.items():
            source_counts[name] += count
        source_data[source] = rewritten.encode("utf-8")

    generated_source_refs = {
        source: _relative(_source_output(output_root, source)) for source in source_names
    }
    removed_public_functions: dict[str, dict[str, int]] = {}
    for artifact_id, suite in resolved.items():
        suite["sources"] = [generated_source_refs[source] for source in suite["sources"]]
        functions = suite.get("functions", [])
        if not isinstance(functions, list):
            raise CodemodError(f"resolved {artifact_id} suite has invalid functions")
        removed_public_functions[artifact_id] = {
            name: functions.count(name) for name in REPLACEMENTS
        }
        suite["functions"] = [name for name in functions if name not in REPLACEMENTS]
        cases = suite.get("cases", [])
        if not isinstance(cases, list):
            raise CodemodError(f"resolved {artifact_id} suite has invalid cases")
        suite["strict_arity"] = True
        suite["abi_profile"] = "dialect-v2"

    case_counts = {name: 0 for name in REPLACEMENTS}
    for artifact_id, suite in resolved.items():
        for index, case in enumerate(suite["cases"]):
            if not isinstance(case, dict) or not isinstance(case.get("expr"), str):
                raise CodemodError(f"{artifact_id} case {index} has no string expr")
            case["expr"], counts = rewrite_tokens(case["expr"])
            for name, count in counts.items():
                case_counts[name] += count

    suite_refs = {key: _relative(path) for key, path in suite_outputs.items()}
    resolved["ide"]["resident_suites"] = [suite_refs["resident"], suite_refs["m65d"]]
    resolved["ide"].pop("resident_suite", None)
    resolved["idex"]["resident_suite"] = suite_refs["ide"]
    resolved["idex"].pop("resident_suites", None)
    resolved["m65d"]["resident_suite"] = suite_refs["resident"]
    resolved["m65d"].pop("resident_suites", None)
    resolved["resident"]["private_inline_functions"] = Stdlib._append_unique(
        resolved["resident"].get("private_inline_functions", []),
        DIRECTORY_ONLY_EXT_RECLAIM_INLINE,
    )
    resolved["resident"]["min_private_inline_functions"] = max(
        resolved["resident"].get("min_private_inline_functions", 0),
        len(resolved["resident"]["private_inline_functions"]),
    )
    resolved["ide"]["directory_only_prefixes"] = ["%"]
    resolved["idex"]["directory_only_prefixes"] = ["%"]
    resolved["ide"]["exports"] = list(DIRECTORY_ONLY_IDE_EXPORTS)
    resolved["idex"]["exports"] = ["%ide-x"]
    resolved["idex"]["override_exports"] = ["%ide-x"]
    resolved["ide"]["late_bound_exports"] = list(DIRECTORY_ONLY_LATE_BOUND_EXPORTS)
    resolved["idex"]["late_bound_exports"] = list(DIRECTORY_ONLY_LATE_BOUND_EXPORTS)

    for managed_dir in (output_root / "sources", output_root / "suites"):
        if managed_dir.exists():
            shutil.rmtree(managed_dir)
    receipt_path = output_root / "codemod-receipt.json"
    if receipt_path.exists():
        receipt_path.unlink()
    output_records: list[dict[str, Any]] = []
    for source in sorted(source_data):
        path = _source_output(output_root, source)
        data = source_data[source]
        _write(path, data)
        output_records.append({"path": _relative(path), "role": "source", "sha256": _sha(data)})
    artifact_records: list[dict[str, Any]] = []
    for spec in specs:
        artifact_id = spec["id"]
        path = suite_outputs[artifact_id]
        data = _suite_json_bytes(resolved[artifact_id])
        _write(path, data)
        output_records.append({"path": _relative(path), "role": "suite", "sha256": _sha(data)})
        artifact_records.append({
            "id": artifact_id,
            "input_suite": spec["source_suite"],
            "output_suite": _relative(path),
            "sources": len(resolved[artifact_id]["sources"]),
            "functions": len(resolved[artifact_id]["functions"]),
            "cases": len(resolved[artifact_id]["cases"]),
        })

    input_paths = suite_inputs | {_repo_path(source) for source in source_names}
    input_paths.update({closure_path, Path(__file__).resolve()})
    input_records = [
        {
            "path": _relative(path),
            "role": (
                "closure" if path == closure_path
                else "generator" if path == Path(__file__).resolve()
                else "suite" if path in suite_inputs
                else "source"
            ),
            "sha256": _sha(path.read_bytes()),
        }
        for path in sorted(input_paths, key=_relative)
    ]
    totals = {
        name: source_counts[name] + case_counts[name] for name in REPLACEMENTS
    }
    receipt = {
        "format": FORMAT,
        "version": 1,
        "profile": "v2-capability-candidate",
        "abi_profile": "dialect-v2",
        "strict_arity": True,
        "closure": _relative(closure_path),
        "artifacts": artifact_records,
        "inputs": input_records,
        "outputs": sorted(output_records, key=lambda item: item["path"]),
        "replacement_counts": {
            "sources": source_counts,
            "case_exprs": case_counts,
            "total": totals,
        },
        "removed_public_functions": removed_public_functions,
        "removed_bridge_defuns": bridge_counts,
    }
    _write(receipt_path, _json_bytes(receipt))
    return receipt_path


def _number_to_string_expr(invoke: str, alias: str, args: list[Any]) -> str:
    encoded = [json.dumps(arg) if isinstance(arg, str) else str(arg) for arg in args]
    tail = (" " + " ".join(encoded)) if encoded else ""
    if invoke == "direct":
        return f"({alias}{tail})"
    if invoke == "funcall":
        return f"(funcall (function {alias}){tail})"
    quoted_args = " ".join(encoded)
    return f"(apply (function {alias}) (quote ({quoted_args})))"


def _number_to_string_selftest(output_root: Path) -> int:
    fixture = _read_json(_repo_path(NUMBER_TO_STRING_FIXTURE), "number->string fixture")
    if set(fixture) != {"format", "profile", "cases"} or (
        fixture["format"]
        != "lisp65-dialect-v2-number-to-string-bytecode-cases-v1"
        or fixture["profile"] != "dialect-v2"
    ):
        raise CodemodError("number->string fixture identity drift")
    cases = fixture["cases"]
    if not isinstance(cases, list) or len(cases) < 10:
        raise CodemodError("number->string fixture is incomplete")
    ids: list[str] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or set(case) not in (
            {"id", "invoke", "args", "expect"},
            {"id", "invoke", "args", "expect_error"},
        ):
            raise CodemodError(f"number->string case {index} schema drift")
        if case["invoke"] not in {"direct", "funcall", "apply"}:
            raise CodemodError(f"number->string case {index} invalid invocation")
        if not isinstance(case["args"], list) or any(
            not isinstance(arg, (int, str)) or isinstance(arg, bool)
            for arg in case["args"]
        ):
            raise CodemodError(f"number->string case {index} invalid arguments")
        ids.append(case["id"])
    if ids != sorted(set(ids)):
        raise CodemodError("number->string fixture ids must be sorted and unique")

    generated_source = _relative(_source_output(output_root, EVAL_RUNTIME))
    suite = {
        "format": "lisp65-bytecode-p0-stdlib-suite-v1",
        "name": "dialect-v2-number-to-string-bytecode",
        "sources": [generated_source],
        "functions": [*EVAL_RUNTIME_PRIVATE_INLINE, "number->string"],
        "private_inline_functions": list(EVAL_RUNTIME_PRIVATE_INLINE),
        "min_private_inline_functions": len(EVAL_RUNTIME_PRIVATE_INLINE),
        "strict_arity": True,
        "abi_profile": "dialect-v2",
        "cases": [{"name": "compile-probe", "expr": "0", "expect": "0"}],
    }
    try:
        (
            heap, _names, code_by_name, _entry_flags, _resident_flags,
            _bundle, directory, _cases, _entries, inliner,
        ) = Stdlib._compile_suite(suite)
        gate = Stdlib._validate_private_inline_expectations(
            suite, heap, code_by_name, inliner
        )
    except (Stdlib.StdlibCheckError, ValueError) as exc:
        raise CodemodError(f"number->string bytecode compile failed: {exc}") from exc
    if gate["names"] != list(EVAL_RUNTIME_PRIVATE_INLINE):
        raise CodemodError("number->string private-inline inventory drift")
    if "%number->string-result" in code_by_name:
        raise CodemodError("number->string private helper leaked into bytecode directory")
    target = code_by_name.get("number->string")
    if target is None or len(target.encode()) > Stdlib.DEFAULT_MAX_CODE_OBJECT_BYTES:
        raise CodemodError("number->string CodeObject exceeds the resident byte limit")

    alias = "%number-to-string-bytecode-under-test"
    alias_obj = heap.intern(alias)
    directory[alias_obj] = target
    compiled: list[tuple[dict[str, Any], Any]] = []
    for case in cases:
        entry = "%number-to-string-case-" + case["id"]
        form = [
            "defun", entry, [],
            Stdlib.C.parse_one(_number_to_string_expr(case["invoke"], alias, case["args"])),
        ]
        try:
            name, code, helpers = Stdlib.C.compile_top_form_with_helpers(
                form, heap, strict_arity=True, abi_profile="dialect-v2"
            )
        except Stdlib.C.CompileError as exc:
            raise CodemodError(f"number->string case {case['id']} compile failed: {exc}") from exc
        if helpers:
            raise CodemodError(f"number->string case {case['id']} emitted helpers")
        directory[heap.intern(name)] = code
        compiled.append((case, code))

    abi_profile, abi_ledger = Stdlib._suite_abi(suite)
    for case, code in compiled:
        case_heap = heap.clone()
        vm = Stdlib.B.P0VM(
            heap=case_heap, directory=directory,
            abi_profile=abi_profile, abi_ledger=abi_ledger,
        )
        try:
            result = vm.run(code, [])
        except Stdlib.B.VMError as exc:
            if case.get("expect_error") != exc.status:
                raise CodemodError(
                    f"number->string case {case['id']} expected "
                    f"{case.get('expect_error')!r}, got {exc.status!r}"
                ) from exc
        else:
            if "expect_error" in case:
                raise CodemodError(
                    f"number->string case {case['id']} accepted invalid input"
                )
            got = case_heap.obj_to_text(result)
            if got != case["expect"]:
                raise CodemodError(
                    f"number->string case {case['id']} expected "
                    f"{case['expect']!r}, got {got!r}"
                )
    return len(cases)


def selftest() -> None:
    sample = (
        '(string->list x) "string->list \\" list->string" '
        'string->listing my-list->string\n'
        '; string->list list->string\n'
        '#| string->list #| list->string |# |# '
        '(list->string y) #\\( #\\semicolon\n'
    )
    rewritten, counts = rewrite_tokens(sample)
    if counts != {"string->list": 1, "list->string": 1}:
        raise CodemodError(f"token-aware counts drift: {counts}")
    if '"string->list \\" list->string"' not in rewritten:
        raise CodemodError("string literal was rewritten")
    if "; string->list list->string" not in rewritten or "string->listing" not in rewritten:
        raise CodemodError("comment or token boundary was rewritten")
    if "(%string-codes x)" not in rewritten or "(%string-from-codes y)" not in rewritten:
        raise CodemodError("exact converter tokens were not rewritten")
    designator, designator_counts = rewrite_tokens(
        "(mapcar (function string->list) xs) 'string->list"
    )
    if (
        designator_counts != {"string->list": 1, "list->string": 0}
        or "(function (lambda (value) (%string-codes value)))" not in designator
        or not designator.endswith("'string->list")
    ):
        raise CodemodError("function-designator or quoted-symbol rewrite drift")

    bridges = (
        "; (defun string->list (x) x)\n"
        "(defun string->list (x) (string->list x))\n"
        "(progn (defun string->list (x) x))\n"
        "(defun list->string (x) (list->string x))\n"
    )
    stripped, removals = remove_bridge_defuns(bridges)
    _require_bridge_defuns(removals)
    if stripped.count("(defun string->list") != 2 or "(defun list->string" in stripped:
        raise CodemodError("bridge removal crossed top-level/comment boundaries")
    try:
        _require_bridge_defuns({"string->list": 1, "list->string": 0})
    except CodemodError as exc:
        if "list->string=0" not in str(exc):
            raise CodemodError(f"missing-definition diagnostic drift: {exc}") from exc
    else:
        raise CodemodError("missing bridge definition was accepted")

    (ROOT / "build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="v2-workbench-codemod-", dir=ROOT / "build"
    ) as raw:
        output = Path(raw) / "out"
        generate(DEFAULT_CLOSURE, output)
        first = {
            path.relative_to(output).as_posix(): _sha(path.read_bytes())
            for path in sorted(output.rglob("*")) if path.is_file()
        }
        generate(DEFAULT_CLOSURE, output)
        second = {
            path.relative_to(output).as_posix(): _sha(path.read_bytes())
            for path in sorted(output.rglob("*")) if path.is_file()
        }
        if first != second:
            raise CodemodError("generation is not deterministic")
        semantic_cases = _number_to_string_selftest(output)
    if semantic_cases != 15:
        raise CodemodError("number->string semantic case count drift")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--closure", type=Path, default=DEFAULT_CLOSURE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            selftest()
            print("v2-workbench-codemod: SELFTEST PASS cases=21")
            return 0
        receipt = generate(args.closure, args.out)
    except (CodemodError, OSError, ValueError) as exc:
        print(f"v2-workbench-codemod: FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"v2-workbench-codemod: PASS receipt={_relative(receipt)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
