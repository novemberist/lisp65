#!/usr/bin/env python3
"""Run the focused dialect-v1/v2 LCC source-surface differential."""

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

import bytecode_p0 as P0
import bytecode_p0_compiler as P0C


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = ROOT / "tests/bytecode/dialect-v2/lcc-surface/cases.json"
DEFAULT_V1_SOURCE_ROOT = ROOT / "build/equivalence/frozen-v1-f6527d25/source"
DEFAULT_V1_BINARY = ROOT / "build/equivalence/frozen-v1-f6527d25/equivalence-check"
DEFAULT_V2_BINARY = ROOT / "build/equivalence/dialect-v2-equivalence-check"
DEFAULT_V1_BUILD = ROOT / "build/equivalence/frozen-v1-f6527d25/build-receipt.json"
DEFAULT_V2_BUILD = ROOT / "build/equivalence/dialect-v2-build-receipt.json"
DEFAULT_LISTS_FIXTURE = ROOT / "tests/bytecode/dialect-v2/lists/cases.json"
DEFAULT_LISTS_OUTPUT = ROOT / "build/bytecode/dialect-v2/lists"
DEFAULT_STRINGS_FIXTURE = ROOT / "tests/bytecode/dialect-v2/strings/cases.json"
DEFAULT_STRINGS_OUTPUT = ROOT / "build/bytecode/dialect-v2/strings"
FROZEN_V1_COMMIT = "f6527d25e2035eae5a98dae7431d641515e2fd2e"
LEDGER = ROOT / "config/bytecode-abi-ledger.json"
PROFILES = ("dialect-v1", "dialect-v2")
LISTS_ENGINES = {
    "native-c-treewalk", "native-c-compiler-vm", "python-p0-compiler-vm", "lisp-lcc",
}
LISTS_REQUIRED_IDS = {
    "assoc-asymmetric-predicate-order", "assoc-default-first-pair",
    "assoc-default-structural-miss", "assoc-equal-structural-hit",
    "assoc-explicit-nil-default", "assoc-finite-dotted-tail",
    "assoc-finite-malformed-entry", "assoc-funcall-too-many",
    "assq-public-name-removed", "count-core-tier-absent",
    "count-library-dotted-tail", "count-library-predicate",
    "filter-finite-dotted-tail", "filter-stable-order",
    "find-finite-dotted-tail", "find-first-predicate-hit", "find-if-public-name-removed",
    "find-too-many", "library-reverse-available", "member-apply-too-many",
    "member-asymmetric-predicate-order", "member-default-tail-identity",
    "member-default-structural-miss", "member-equal-structural-hit",
    "member-explicit-nil-default", "member-finite-dotted-tail",
    "nreverse-apply-too-few", "nreverse-dotted-prefix",
    "nreverse-funcall-too-many", "nreverse-non-cons",
    "nth-negative-index", "nth-non-fixnum-index",
    "nthcdr-negative-index", "nthcdr-non-fixnum-index",
    "optional-nil-ambiguity", "optional-rest-lowering",
    "position-core-tier-absent", "position-library-dotted-tail", "position-library-predicate",
    "rplaca-direct-too-few", "rplaca-funcall-too-many",
    "rplacd-apply-too-few", "rplacd-direct-too-many",
}
STRINGS_ENGINES = {
    "native-c-treewalk", "native-c-compiler-vm", "python-p0-compiler-vm", "lisp-lcc",
}
PRELOADS = {
    "dialect-v1": (
        "lib/lcc.lisp", "lib/prelude-m1.lisp", "lib/stdlib-control.lisp",
    ),
    "dialect-v2": (
        "lib/lcc.lisp", "lib/dialect-v2/lcc-profile.lisp",
        "lib/dialect-v2/prelude-control.lisp",
    ),
}
LISTS_PRELOADS = {
    "dialect-v1": {
        "core": (
            "lib/lcc.lisp", "lib/prelude-m1.lisp", "lib/stdlib-control.lisp",
            "lib/stdlib-lists.lisp",
        ),
        "library": (
            "lib/lcc.lisp", "lib/prelude-m1.lisp", "lib/stdlib-control.lisp",
            "lib/stdlib-lists.lisp", "lib/stdlib-sequences.lisp",
            "lib/stdlib-plists.lisp",
        ),
    },
    "dialect-v2": {
        "core": (
            "lib/lcc.lisp", "lib/dialect-v2/lcc-profile.lisp",
            "lib/dialect-v2/prelude-control.lisp",
        ),
        "library": (
            "lib/lcc.lisp", "lib/dialect-v2/lcc-profile.lisp",
            "lib/dialect-v2/prelude-control.lisp",
        ),
    },
}
LISTS_COMPILED_SOURCES = {
    "dialect-v1": {"core": (), "library": ()},
    "dialect-v2": {
        "core": ("lib/dialect-v2/lists-core.lisp",),
        "library": (
            "lib/dialect-v2/lists-core.lisp", "lib/dialect-v2/lists-library.lisp",
        ),
    },
}
STRINGS_PRELOADS = {
    "dialect-v1": (
        "lib/lcc.lisp", "lib/prelude-m1.lisp", "lib/stdlib-control.lisp",
        "lib/stdlib-lists.lisp", "lib/stdlib-strings.lisp",
    ),
    "dialect-v2": (
        "lib/lcc.lisp", "lib/dialect-v2/lcc-profile.lisp",
        "lib/dialect-v2/prelude-control.lisp",
    ),
}
STRINGS_COMPILED_SOURCES = {
    "dialect-v1": (),
    "dialect-v2": ("lib/dialect-v2/strings-core.lisp",),
}
# The all-view registry closed the last native `symbol-value` gap.  The LCC
# Stage-3 carrier now shares the zero-blocker invariant with the other engines.
STRINGS_STAGE3_CARRIER_BLOCKERS = set()
REQUIRED_IDS = {
    "arity-combined-00-define", "arity-combined-01-required-only",
    "arity-combined-02-optional", "arity-combined-03-rest",
    "arity-combined-04-too-few", "arity-header-closure-helper",
    "arity-header-top-level", "arity-helper-closure-runtime", "arity-immediate-lambda",
    "arity-invalid-duplicate-marker", "arity-invalid-duplicate-parameter",
    "arity-invalid-non-symbol-optional", "arity-invalid-rest-missing-name",
    "arity-invalid-rest-not-final",
    "arity-optional-00-define", "arity-optional-01-required-only",
    "arity-optional-02-supplied", "arity-optional-03-too-few",
    "arity-optional-04-too-many", "arity-rest-00-define",
    "arity-rest-01-empty", "arity-rest-02-collected",
    "do-removed", "do-star-removed", "dolist-retained", "dotimes-retained",
    "mod-retained", "remainder-direct-removed", "remainder-funcall-removed",
}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class SurfaceError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SurfaceError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SurfaceError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SurfaceError(f"{path} must contain an object")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise SurfaceError(f"{label} keys drift: {actual}")
    return value


def validate_fixture(value: dict[str, Any]) -> list[dict[str, str]]:
    _exact(value, {"format", "cases"}, "fixture")
    if value["format"] != "lisp65-dialect-v2-lcc-surface-cases-v1":
        raise SurfaceError("fixture identity drift")
    cases = value["cases"]
    if not isinstance(cases, list) or not cases:
        raise SurfaceError("fixture cases must be a non-empty list")
    ids: list[str] = []
    sources: set[str] = set()
    for index, raw in enumerate(cases):
        case = _exact(
            raw, {"id", "source", "dialect-v1", "dialect-v2"},
            f"cases[{index}]",
        )
        case_id = case["id"]
        if not isinstance(case_id, str) or not ID_RE.fullmatch(case_id):
            raise SurfaceError(f"cases[{index}] id is invalid")
        ids.append(case_id)
        for key in ("source", *PROFILES):
            if not isinstance(case[key], str) or not case[key] or case[key] != case[key].strip():
                raise SurfaceError(f"case {case_id} has an invalid {key}")
        if case["source"] in sources:
            raise SurfaceError(f"duplicate source form: {case['source']}")
        sources.add(case["source"])
    if ids != sorted(set(ids)) or set(ids) != REQUIRED_IDS:
        raise SurfaceError(f"fixture coverage/order drift: {ids}")
    return cases


def validate_lists_fixture(value: dict[str, Any]) -> list[dict[str, Any]]:
    _exact(value, {"format", "profile", "family", "cases"}, "lists fixture")
    if (
        value["format"] != "lisp65-dialect-v2-lists-cases-v1"
        or value["profile"] != "dialect-v1-v2-differential"
        or value["family"] != "lists"
    ):
        raise SurfaceError("lists fixture identity drift")
    cases = value["cases"]
    if not isinstance(cases, list) or not cases:
        raise SurfaceError("lists fixture cases must be a non-empty list")
    ids: list[str] = []
    for index, raw in enumerate(cases):
        case = _exact(
            raw, {"id", "tier", "forms", "migration_anchor", "observations"},
            f"lists cases[{index}]",
        )
        case_id = case["id"]
        if not isinstance(case_id, str) or not ID_RE.fullmatch(case_id):
            raise SurfaceError(f"lists cases[{index}] has invalid id")
        ids.append(case_id)
        if case["tier"] not in {"core", "library"}:
            raise SurfaceError(f"lists case {case_id} has invalid tier")
        if not isinstance(case["forms"], list) or not case["forms"] or any(
            not isinstance(form, str) or not form.strip() for form in case["forms"]
        ):
            raise SurfaceError(f"lists case {case_id} has invalid forms")
        observations = _exact(
            case["observations"], set(PROFILES), f"lists case {case_id} observations",
        )
        for profile in PROFILES:
            engines = _exact(
                observations[profile], LISTS_ENGINES,
                f"lists case {case_id}/{profile} observations",
            )
            if any(
                not isinstance(result, str) or not result or result != result.strip()
                for result in engines.values()
            ):
                raise SurfaceError(f"lists case {case_id}/{profile} has invalid result")
    if ids != sorted(set(ids)) or set(ids) != LISTS_REQUIRED_IDS:
        raise SurfaceError(f"lists fixture coverage/order drift: {ids}")
    return cases


def validate_strings_fixture(value: dict[str, Any]) -> list[dict[str, Any]]:
    _exact(value, {"format", "profile", "family", "cases"}, "strings fixture")
    if (
        value["format"] != "lisp65-dialect-v2-strings-cases-v1"
        or value["profile"] != "dialect-v1-v2-differential"
        or value["family"] != "strings"
    ):
        raise SurfaceError("strings fixture identity drift")
    cases = value["cases"]
    if not isinstance(cases, list) or len(cases) != 36:
        raise SurfaceError("strings fixture must contain exactly 36 cases")
    ids: list[str] = []
    for index, raw in enumerate(cases):
        case = _exact(
            raw, {"id", "forms", "migration_anchor", "observations"},
            f"strings cases[{index}]",
        )
        case_id = case["id"]
        if not isinstance(case_id, str) or not ID_RE.fullmatch(case_id):
            raise SurfaceError(f"strings cases[{index}] has invalid id")
        ids.append(case_id)
        if not isinstance(case["forms"], list) or not case["forms"] or any(
            not isinstance(form, str) or not form.strip() for form in case["forms"]
        ):
            raise SurfaceError(f"strings case {case_id} has invalid forms")
        observations = _exact(
            case["observations"], set(PROFILES),
            f"strings case {case_id} observations",
        )
        for profile in PROFILES:
            engines = _exact(
                observations[profile], STRINGS_ENGINES,
                f"strings case {case_id}/{profile} observations",
            )
            if any(
                not isinstance(result, str) or not result or result != result.strip()
                for result in engines.values()
            ):
                raise SurfaceError(f"strings case {case_id}/{profile} invalid result")
    if ids != sorted(set(ids)):
        raise SurfaceError("strings fixture ids must be sorted and unique")
    return cases


def _check_abi_ledger() -> None:
    ledger = _load(LEDGER)
    profiles = {item["id"]: item for item in ledger.get("profiles", [])}
    identities = {item["id"]: item for item in ledger.get("opcode_identities", [])}
    prim_identities = {
        item["id"]: item for item in ledger.get("prim_identities", [])
    }
    if identities.get(24) != {"id": 24, "canonical_name": "REMAINDER", "operand": "none"}:
        raise SurfaceError("P0 opcode 24 identity drift")
    for profile in PROFILES:
        item = profiles.get(profile)
        if not isinstance(item, dict) or 24 not in item["opcodes"]["active"]:
            raise SurfaceError(f"opcode 24 must remain active in {profile}")
        if item["opcodes"]["tombstone"]:
            raise SurfaceError(f"unexpected opcode tombstone in {profile}")
    v1 = profiles["dialect-v1"]["prim_ids"]
    v2 = profiles["dialect-v2"]["prim_ids"]
    if v1["active"] != list(range(23)) or v1["tombstone"]:
        raise SurfaceError("dialect-v1 Prim-ID allocation must remain exactly 0..22 active")
    expected_v2_active = [0, *range(3, 26), 28, 29, *range(30, 34), *range(35, 40), *range(41, 67)]
    if v2["active"] != expected_v2_active or v2["tombstone"] != [1, 2, 26, 27, 34, 40]:
        raise SurfaceError("dialect-v2 Prim-ID active/tombstone allocation drift")
    expected_new = {
        23: "nreverse", 24: "rplaca", 25: "rplacd",
        26: "%string-slice", 27: "%string-concat-list",
    }
    if {
        ident: prim_identities.get(ident, {}).get("canonical_name")
        for ident in expected_new
    } != expected_new:
        raise SurfaceError("dialect-v2 Prim-ID identity allocation drift")
    if any(
        P0.prim_is_function_designator(ident, "dialect-v2", ledger)
        for ident in P0.INTERNAL_ONLY_PRIM_IDS
    ):
        raise SurfaceError("internal string Prim-ID exposed as a function designator")
    if any(item.get("canonical_name") == "remainder" for item in ledger.get("prim_identities", [])):
        raise SurfaceError("remainder must not be invented as a Prim-ID")


def _combined_preload(profile: str, directory: Path, source_root: Path) -> Path:
    path = directory / f"{profile}-lcc-preload.lisp"
    parts = []
    for relative in PRELOADS[profile]:
        source = source_root / relative
        if not source.is_file():
            raise SurfaceError(f"missing preload source: {relative}")
        parts.append(source.read_text(encoding="utf-8"))
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return path


def _profile_source(profile: str, source_root: Path, relative: str) -> str:
    source = source_root / relative
    if source.is_file():
        return source.read_text(encoding="utf-8")
    if profile != "dialect-v1":
        raise SurfaceError(f"missing {profile} source: {relative}")
    try:
        process = subprocess.run(
            ["git", "show", f"{FROZEN_V1_COMMIT}:{relative}"],
            cwd=ROOT, capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SurfaceError(f"cannot export frozen v1 source {relative}: {exc}") from exc
    if process.returncode or not process.stdout:
        raise SurfaceError(f"frozen v1 source is unavailable: {relative}")
    return process.stdout


def _lists_inputs(
    profile: str, tier: str, directory: Path, source_root: Path,
) -> tuple[Path, str, str]:
    preload_parts = [
        _profile_source(profile, source_root, relative)
        for relative in LISTS_PRELOADS[profile][tier]
    ]
    compiled_parts = [
        _profile_source(profile, source_root, relative)
        for relative in LISTS_COMPILED_SOURCES[profile][tier]
    ]
    preload_text = "\n".join(preload_parts) + "\n"
    compiled_text = "\n".join(compiled_parts)
    preload = directory / f"lists-{tier}-{profile}-lisp-lcc-preload.lisp"
    preload.write_text(preload_text, encoding="utf-8")
    binding = (
        "preload\n" + preload_text + "compiled-sources\n" + compiled_text
    ).encode("utf-8")
    return preload, compiled_text, hashlib.sha256(binding).hexdigest()


def _strings_inputs(
    profile: str, directory: Path, source_root: Path,
) -> tuple[Path, str, str]:
    preload_parts = [
        _profile_source(profile, source_root, relative)
        for relative in STRINGS_PRELOADS[profile]
    ]
    compiled_parts = [
        _profile_source(profile, source_root, relative)
        for relative in STRINGS_COMPILED_SOURCES[profile]
    ]
    preload_text = "\n".join(preload_parts) + "\n"
    compiled_text = "\n".join(compiled_parts)
    preload = directory / f"strings-{profile}-lisp-lcc-preload.lisp"
    preload.write_text(preload_text, encoding="utf-8")
    binding = (
        "preload\n" + preload_text + "compiled-sources\n" + compiled_text
    ).encode("utf-8")
    return preload, compiled_text, hashlib.sha256(binding).hexdigest()


def _parse_observations(stdout: str, expected: int, label: str) -> list[str]:
    observed = [
        line.rsplit(" => ", 1)[1].strip()
        for line in stdout.splitlines() if " => " in line
    ]
    if len(observed) != expected:
        raise SurfaceError(f"{label}: harness returned {len(observed)} results, expected {expected}")
    return observed


def _run_lists_case(
    profile: str, binary: Path, case: dict[str, Any], preload: Path,
    compiled_text: str, directory: Path,
) -> str:
    compiled_forms = P0C.parse_all(compiled_text) if compiled_text else []
    forms = directory / f"lists-{profile}-{case['id']}-lisp-lcc.lisp"
    source = compiled_text
    if source and not source.endswith("\n"):
        source += "\n"
    source += "\n".join(case["forms"]) + "\n"
    forms.write_text(source, encoding="utf-8")
    try:
        process = subprocess.run(
            [str(binary), "lcc", str(forms), "--preload", str(preload)],
            cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SurfaceError(f"{profile}/lisp-lcc/{case['id']}: harness failed: {exc}") from exc
    if process.returncode:
        raise SurfaceError(
            f"{profile}/lisp-lcc/{case['id']}: harness exited {process.returncode}: "
            f"{process.stderr.strip()}"
        )
    results = _parse_observations(
        process.stdout, len(compiled_forms) + len(case["forms"]),
        f"{profile}/lisp-lcc/{case['id']}",
    )
    bootstrap = results[:len(compiled_forms)]
    if any(result.startswith("!error:") for result in bootstrap):
        failed_index = next(i for i, result in enumerate(bootstrap) if result.startswith("!error:"))
        raise SurfaceError(
            f"{profile}/lisp-lcc/{case['id']}: list source form {failed_index} "
            f"failed with {bootstrap[failed_index]}"
        )
    return results[-1]


def _run_strings_case(
    profile: str, binary: Path, case: dict[str, Any], preload: Path,
    compiled_text: str, directory: Path,
) -> str:
    compiled_forms = P0C.parse_all(compiled_text)
    forms = directory / f"strings-{profile}-{case['id']}-lisp-lcc.lisp"
    source = compiled_text
    if source and not source.endswith("\n"):
        source += "\n"
    source += "\n".join(case["forms"]) + "\n"
    forms.write_text(source, encoding="utf-8")
    try:
        process = subprocess.run(
            [str(binary), "lcc", str(forms), "--preload", str(preload)],
            cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SurfaceError(
            f"{profile}/lisp-lcc/{case['id']}: harness failed: {exc}"
        ) from exc
    if process.returncode:
        raise SurfaceError(
            f"{profile}/lisp-lcc/{case['id']}: harness exited {process.returncode}: "
            f"{process.stderr.strip()}"
        )
    results = _parse_observations(
        process.stdout, len(compiled_forms) + len(case["forms"]),
        f"{profile}/lisp-lcc/{case['id']}",
    )
    bootstrap = results[:len(compiled_forms)]
    if any(result.startswith("!error:") for result in bootstrap):
        failed_index = next(
            i for i, result in enumerate(bootstrap) if result.startswith("!error:")
        )
        raise SurfaceError(
            f"{profile}/lisp-lcc/{case['id']}: strings source form {failed_index} "
            f"failed with {bootstrap[failed_index]}"
        )
    return results[-1]


def _build_receipt(path: Path, profile: str, binary: Path) -> dict[str, Any]:
    value = _load(path)
    required = {"profile", "source_commit", "binary_sha256", "build_profile_sha256"}
    if not required <= set(value) or value["profile"] != profile:
        raise SurfaceError(f"{profile} build receipt identity drift")
    if value["binary_sha256"] != hashlib.sha256(binary.read_bytes()).hexdigest():
        raise SurfaceError(f"{profile} build receipt binary SHA drift")
    expected_commit = FROZEN_V1_COMMIT if profile == "dialect-v1" else None
    if value["source_commit"] != expected_commit:
        raise SurfaceError(f"{profile} build receipt source provenance drift")
    for key in ("binary_sha256", "build_profile_sha256"):
        if not isinstance(value[key], str) or not re.fullmatch(r"[0-9a-f]{64}", value[key]):
            raise SurfaceError(f"{profile} build receipt {key} is invalid")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_profile(
    profile: str, binary: Path, cases: list[dict[str, str]], directory: Path,
    source_root: Path,
) -> list[str]:
    if not binary.is_file():
        raise SurfaceError(f"missing {profile} equivalence binary: {binary}")
    forms = directory / f"{profile}-lcc-forms.lisp"
    forms.write_text("\n".join(case["source"] for case in cases) + "\n", encoding="utf-8")
    command = [
        str(binary), "lcc", str(forms), "--preload",
        str(_combined_preload(profile, directory, source_root)),
    ]
    try:
        process = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SurfaceError(f"{profile} LCC harness failed: {exc}") from exc
    if process.returncode:
        raise SurfaceError(f"{profile} LCC harness exited {process.returncode}: {process.stderr.strip()}")
    observed = [
        line.rsplit(" => ", 1)[1].strip()
        for line in process.stdout.splitlines() if " => " in line
    ]
    if len(observed) != len(cases):
        raise SurfaceError(
            f"{profile} LCC returned {len(observed)} observations, expected {len(cases)}"
        )
    return observed


def run(
    fixture: Path, binary_v1: Path, binary_v2: Path,
    source_root_v1: Path, source_root_v2: Path,
) -> None:
    cases = validate_fixture(_load(fixture))
    _check_abi_ledger()
    if binary_v1.resolve() == binary_v2.resolve():
        raise SurfaceError("v1 and v2 binaries must be distinct")
    failed = 0
    with tempfile.TemporaryDirectory(prefix="lisp65-v2-lcc-") as raw:
        directory = Path(raw)
        for profile, binary, source_root in (
            ("dialect-v1", binary_v1, source_root_v1),
            ("dialect-v2", binary_v2, source_root_v2),
        ):
            observed = _run_profile(profile, binary, cases, directory, source_root)
            for case, actual in zip(cases, observed):
                expected = case[profile]
                ok = actual == expected
                failed += int(not ok)
                print(
                    f"{profile}/lisp-lcc/{case['id']}: {'PASS' if ok else 'FAIL'} "
                    f"observed={actual} expected={expected}"
                )
    if failed:
        raise SurfaceError(f"LCC surface differential failed cases={failed}")
    print(
        "dialect-v2-lcc-surface: PASS "
        f"cases={len(cases)} runs={len(cases) * 2} "
        f"v1_sha256={hashlib.sha256(binary_v1.read_bytes()).hexdigest()} "
        f"v2_sha256={hashlib.sha256(binary_v2.read_bytes()).hexdigest()}"
    )


def run_lists(
    fixture: Path, binary_v1: Path, binary_v2: Path,
    source_root_v1: Path, source_root_v2: Path,
    build_v1: Path, build_v2: Path, output_dir: Path,
) -> None:
    cases = validate_lists_fixture(_load(fixture))
    binaries = {"dialect-v1": binary_v1, "dialect-v2": binary_v2}
    roots = {"dialect-v1": source_root_v1, "dialect-v2": source_root_v2}
    builds = {
        "dialect-v1": _build_receipt(build_v1, "dialect-v1", binary_v1),
        "dialect-v2": _build_receipt(build_v2, "dialect-v2", binary_v2),
    }
    if binary_v1.resolve() == binary_v2.resolve():
        raise SurfaceError("lists differential requires distinct profile binaries")
    fixture_sha = hashlib.sha256(fixture.read_bytes()).hexdigest()
    failed = 0
    with tempfile.TemporaryDirectory(prefix="lisp65-v2-lists-lcc-") as raw:
        directory = Path(raw)
        inputs = {
            (profile, tier): _lists_inputs(profile, tier, directory, roots[profile])
            for profile in PROFILES for tier in ("core", "library")
        }
        for profile in PROFILES:
            verdict_cases: list[dict[str, str | None]] = []
            tier_shas: dict[str, str] = {}
            for case in cases:
                tier = case["tier"]
                preload, compiled_text, input_sha = inputs[(profile, tier)]
                tier_shas[tier] = input_sha
                observed = _run_lists_case(
                    profile, binaries[profile], case, preload, compiled_text, directory,
                )
                expected = case["observations"][profile]["lisp-lcc"]
                accepted = observed == expected
                failed += int(not accepted)
                verdict_cases.append(
                    {
                        "id": case["id"],
                        "decision": case["migration_anchor"],
                        "verdict": "accept" if accepted else "reject",
                        "result_sha256": hashlib.sha256(observed.encode("utf-8")).hexdigest(),
                    }
                )
                print(
                    f"{profile}/lisp-lcc/{case['id']}: "
                    f"{'PASS' if accepted else 'FAIL'} observed={observed} expected={expected}"
                )
            combined_input_sha = hashlib.sha256(
                "".join(f"{tier}:{tier_shas[tier]}\n" for tier in sorted(tier_shas)).encode("ascii")
            ).hexdigest()
            verdict = {
                "format": "lisp65-dialect-v2-family-verdict-v1",
                "family": "lists",
                "profile": profile,
                "engine": "lisp-lcc",
                "fixture_sha256": fixture_sha,
                "provenance": {
                    "source_commit": builds[profile]["source_commit"],
                    "binary_sha256": builds[profile]["binary_sha256"],
                    "build_profile_sha256": builds[profile]["build_profile_sha256"],
                    "preload_sha256": combined_input_sha,
                },
                "cases": verdict_cases,
            }
            _write_json(output_dir / f"{profile}-lisp-lcc-verdict.json", verdict)
    if failed:
        raise SurfaceError(f"lists LCC differential failed cases={failed}")
    print(f"dialect-v2-lists-lcc: PASS cases={len(cases)} runs={len(cases) * 2}")


def run_strings(
    fixture: Path, binary_v1: Path, binary_v2: Path,
    source_root_v1: Path, source_root_v2: Path,
    build_v1: Path, build_v2: Path, output_dir: Path,
    stage3_carrier_active: bool = False,
) -> None:
    cases = validate_strings_fixture(_load(fixture))
    binaries = {"dialect-v1": binary_v1, "dialect-v2": binary_v2}
    roots = {"dialect-v1": source_root_v1, "dialect-v2": source_root_v2}
    builds = {
        "dialect-v1": _build_receipt(build_v1, "dialect-v1", binary_v1),
        "dialect-v2": _build_receipt(build_v2, "dialect-v2", binary_v2),
    }
    if binary_v1.resolve() == binary_v2.resolve():
        raise SurfaceError("strings differential requires distinct profile binaries")
    fixture_sha = hashlib.sha256(fixture.read_bytes()).hexdigest()
    failed = 0
    mismatches: set[tuple[str, str]] = set()
    with tempfile.TemporaryDirectory(prefix="lisp65-v2-strings-lcc-") as raw:
        directory = Path(raw)
        inputs = {
            profile: _strings_inputs(profile, directory, roots[profile])
            for profile in PROFILES
        }
        for profile in PROFILES:
            preload, compiled_text, input_sha = inputs[profile]
            verdict_cases: list[dict[str, str | None]] = []
            for case in cases:
                observed = _run_strings_case(
                    profile, binaries[profile], case, preload, compiled_text, directory,
                )
                expected = case["observations"][profile]["lisp-lcc"]
                accepted = observed == expected
                failed += int(not accepted)
                if not accepted:
                    mismatches.add((profile, case["id"]))
                verdict_cases.append(
                    {
                        "id": case["id"], "decision": case["migration_anchor"],
                        "verdict": "accept" if accepted else "reject",
                        "result_sha256": hashlib.sha256(observed.encode("utf-8")).hexdigest(),
                    }
                )
                print(
                    f"{profile}/lisp-lcc/{case['id']}: "
                    f"{'PASS' if accepted else 'FAIL'} "
                    f"observed={observed} expected={expected}"
                )
            verdict = {
                "format": "lisp65-dialect-v2-family-verdict-v1",
                "family": "strings", "profile": profile, "engine": "lisp-lcc",
                "fixture_sha256": fixture_sha,
                "provenance": {
                    "source_commit": builds[profile]["source_commit"],
                    "binary_sha256": builds[profile]["binary_sha256"],
                    "build_profile_sha256": builds[profile]["build_profile_sha256"],
                    "preload_sha256": input_sha,
                },
                "cases": verdict_cases,
            }
            _write_json(output_dir / f"{profile}-lisp-lcc-verdict.json", verdict)
    if stage3_carrier_active:
        if mismatches != STRINGS_STAGE3_CARRIER_BLOCKERS:
            raise SurfaceError(
                "strings Stage-3 carrier blocker drift: "
                f"observed={sorted(mismatches)} "
                f"expected={sorted(STRINGS_STAGE3_CARRIER_BLOCKERS)}"
            )
        print(
            f"dialect-v2-strings-lcc: STAGE3 PASS cases={len(cases)} "
            f"runs={len(cases) * 2} carrier-cut-blockers={len(mismatches)}"
        )
        return
    if failed:
        raise SurfaceError(f"strings LCC differential failed cases={failed}")
    print(f"dialect-v2-strings-lcc: PASS cases={len(cases)} runs={len(cases) * 2}")


def selftest(fixture: Path) -> None:
    original = _load(fixture)
    validate_fixture(original)
    mutations = []
    missing = copy.deepcopy(original)
    missing["cases"].pop()
    mutations.append(missing)
    bad_expected = copy.deepcopy(original)
    bad_expected["cases"][0]["dialect-v2"] = ""
    mutations.append(bad_expected)
    duplicate = copy.deepcopy(original)
    duplicate["cases"][1]["source"] = duplicate["cases"][0]["source"]
    mutations.append(duplicate)
    for index, value in enumerate(mutations):
        try:
            validate_fixture(value)
        except SurfaceError:
            continue
        raise SurfaceError(f"selftest mutation {index} was accepted")
    _check_abi_ledger()
    print("dialect-v2-lcc-surface: SELFTEST PASS mutations=3 abi=opcode24-active")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--lists", action="store_true")
    parser.add_argument("--lists-fixture", type=Path, default=DEFAULT_LISTS_FIXTURE)
    parser.add_argument("--lists-output-dir", type=Path, default=DEFAULT_LISTS_OUTPUT)
    parser.add_argument("--strings", action="store_true")
    parser.add_argument("--stage3-carrier-active", action="store_true")
    parser.add_argument("--strings-fixture", type=Path, default=DEFAULT_STRINGS_FIXTURE)
    parser.add_argument("--strings-output-dir", type=Path, default=DEFAULT_STRINGS_OUTPUT)
    parser.add_argument("--binary-v1", type=Path, default=DEFAULT_V1_BINARY)
    parser.add_argument("--binary-v2", type=Path, default=DEFAULT_V2_BINARY)
    parser.add_argument("--build-receipt-v1", type=Path, default=DEFAULT_V1_BUILD)
    parser.add_argument("--build-receipt-v2", type=Path, default=DEFAULT_V2_BUILD)
    parser.add_argument("--source-root-v1", type=Path, default=DEFAULT_V1_SOURCE_ROOT)
    parser.add_argument("--source-root-v2", type=Path, default=ROOT)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    try:
        if args.stage3_carrier_active and not args.strings:
            raise SurfaceError("--stage3-carrier-active requires --strings")
        if args.lists and args.strings:
            raise SurfaceError("choose exactly one family mode")
        if args.strings:
            if args.selftest:
                fixture_value = _load(args.strings_fixture)
                cases = validate_strings_fixture(fixture_value)
                missing = copy.deepcopy(fixture_value)
                del missing["cases"][0]["observations"]["dialect-v2"]["lisp-lcc"]
                try:
                    validate_strings_fixture(missing)
                except SurfaceError:
                    pass
                else:
                    raise SurfaceError("strings fixture accepted a missing LCC observation")
                internal = [case for case in cases if case["id"].startswith("internal-")]
                if len(internal) != 4 or any(
                    not case["observations"][profile]["lisp-lcc"].startswith("!error:")
                    for case in internal for profile in PROFILES
                ):
                    raise SurfaceError("internal string capabilities became LCC designators")
                print(
                    "dialect-v2-strings-lcc: SELFTEST PASS "
                    f"cases={len(cases)} runs={len(cases) * 2} "
                    "mutations=1 internal-designators=4"
                )
            else:
                run_strings(
                    args.strings_fixture, args.binary_v1, args.binary_v2,
                    args.source_root_v1, args.source_root_v2,
                    args.build_receipt_v1, args.build_receipt_v2,
                    args.strings_output_dir,
                    args.stage3_carrier_active,
                )
            return 0
        if args.lists:
            if args.selftest:
                cases = validate_lists_fixture(_load(args.lists_fixture))
                print(
                    "dialect-v2-lists-lcc: SELFTEST PASS "
                    f"cases={len(cases)} runs={len(cases) * 2}"
                )
            else:
                run_lists(
                    args.lists_fixture, args.binary_v1, args.binary_v2,
                    args.source_root_v1, args.source_root_v2,
                    args.build_receipt_v1, args.build_receipt_v2,
                    args.lists_output_dir,
                )
            return 0
        if args.selftest:
            selftest(args.fixture)
        else:
            run(
                args.fixture, args.binary_v1, args.binary_v2,
                args.source_root_v1, args.source_root_v2,
            )
        return 0
    except SurfaceError as exc:
        print(f"dialect-v2-lcc-surface: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
