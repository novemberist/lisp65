#!/usr/bin/env python3
"""Validate and run the AP8.4 Prelude/Control profile matrix.

The existing equivalence harness has no runtime profile switch.  The runner
therefore requires one binary built from the frozen v1 profile and one binary
built from the v2 candidate.  Both binaries must preserve the established CLI:

    equivalence-check tree|vm FORMS [--preload SOURCE]

Each case runs in a fresh process.  The runner combines the profile and engine
preloads into a temporary source file and emits one verdict artifact for every
profile/engine pair.  A missing profile binary fails closed.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = ROOT / "tests/bytecode/dialect-v2/prelude-control/cases.json"
DEFAULT_V1_SOURCE_ROOT = ROOT / "build/equivalence/frozen-v1-f6527d25/source"
DEFAULT_V1_BINARY = ROOT / "build/equivalence/frozen-v1-f6527d25/equivalence-check"
DEFAULT_V2_BINARY = ROOT / "build/equivalence/dialect-v2-equivalence-check"
DEFAULT_V1_BUILD = ROOT / "build/equivalence/frozen-v1-f6527d25/build-receipt.json"
DEFAULT_V2_BUILD = ROOT / "build/equivalence/dialect-v2-build-receipt.json"
FROZEN_V1_COMMIT = "f6527d25e2035eae5a98dae7431d641515e2fd2e"
PROFILES = ("dialect-v1", "dialect-v2")
ENGINES = ("native-c-treewalk", "native-c-compiler-vm")
ENGINE_MODES = {"native-c-treewalk": "tree", "native-c-compiler-vm": "vm"}
PRELUDE_ANCHORS = {
    "decision:defparameter-defvar-surface",
    "decision:do-removal",
    "decision:not-equal-binary-arity",
    "decision:remainder-v2-surface",
}
PRELUDE_REQUIRED_CASE_IDS = {
    "defparameter-always-evaluates-init",
    "defparameter-overwrites-reloaded-value",
    "defvar-bound-skips-init",
    "defvar-extra-init-arity",
    "defvar-no-init-leaves-unbound",
    "defvar-reload-preserves-current-value",
    "do-public-form-removed",
    "dolist-survives-do-removal",
    "dotimes-survives-do-removal",
    "mod-negative-keeps-divisor-sign",
    "not-equal-apply-arity-one",
    "not-equal-arity-one",
    "not-equal-arity-three",
    "not-equal-arity-zero",
    "not-equal-binary-distinct",
    "not-equal-binary-equal",
    "not-equal-funcall-arity-three",
    "remainder-negative-keeps-dividend-sign",
    "remainder-public-funcall-removed",
}
PRELUDE_PRELOADS = {
    "dialect-v1": {
        "native-c-treewalk": ("lib/prelude-m1.lisp", "lib/stdlib-control.lisp"),
        # The frozen compiler has native dotimes/dolist but no user-macro route for do.
        "native-c-compiler-vm": ("lib/prelude-m1.lisp",),
    },
    "dialect-v2": {
        "native-c-treewalk": ("lib/dialect-v2/prelude-control.lisp",),
        "native-c-compiler-vm": ("lib/dialect-v2/prelude-control.lisp",),
    },
}
LISTS_ANCHORS = {
    "decision:assq-assoc-semantics",
    "decision:find-member-assoc-predicate",
    "decision:lists-core-library-boundary",
    "decision:lists-malformed-input",
    "decision:lists-mutation-arity-semantics",
    "decision:optional-source-lowering",
    "decision:strict-arity-codeobject",
}
LISTS_REQUIRED_CASE_IDS = {
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
LISTS_PRELOADS = {
    "dialect-v1": {
        "core": {
            "native-c-treewalk": ("lib/prelude-m1.lisp", "lib/stdlib-lists.lisp"),
            "native-c-compiler-vm": ("lib/prelude-m1.lisp", "lib/stdlib-lists.lisp"),
        },
        "library": {
            "native-c-treewalk": (
                "lib/prelude-m1.lisp", "lib/stdlib-lists.lisp",
                "lib/stdlib-sequences.lisp", "lib/stdlib-plists.lisp",
            ),
            "native-c-compiler-vm": (
                "lib/prelude-m1.lisp", "lib/stdlib-lists.lisp",
                "lib/stdlib-sequences.lisp", "lib/stdlib-plists.lisp",
            ),
        },
    },
    "dialect-v2": {
        "core": {
            "native-c-treewalk": (
                "lib/dialect-v2/prelude-control.lisp", "lib/dialect-v2/lists-core.lisp",
            ),
            "native-c-compiler-vm": (
                "lib/dialect-v2/prelude-control.lisp", "lib/dialect-v2/lists-core.lisp",
            ),
        },
        "library": {
            "native-c-treewalk": (
                "lib/dialect-v2/prelude-control.lisp", "lib/dialect-v2/lists-core.lisp",
                "lib/dialect-v2/lists-library.lisp",
            ),
            "native-c-compiler-vm": (
                "lib/dialect-v2/prelude-control.lisp", "lib/dialect-v2/lists-core.lisp",
                "lib/dialect-v2/lists-library.lisp",
            ),
        },
    },
}
EVAL_APPLY_FUNCALL_ANCHORS = {
    "decision:eval-apply-funcall-surface",
    "decision:strict-arity-codeobject",
}
EVAL_APPLY_FUNCALL_REQUIRED_CASE_IDS = {
    "apply-bcode-result", "apply-bcode-too-few",
    "apply-closure-result", "direct-bcode-too-few",
    "direct-eval-atom", "direct-eval-form",
    "funcall-bcode-too-many", "funcall-closure-too-many",
    "funcall-eval-form", "funcall-primitive-too-many",
}
EVAL_APPLY_FUNCALL_PRELOADS = {
    profile: {
        "native-c-treewalk": (),
        "native-c-compiler-vm": (),
    }
    for profile in PROFILES
}
STRINGS_ANCHORS = {
    "decision:eval-apply-funcall-surface",
    "decision:optional-source-lowering",
    "decision:string-bounds-contract",
    "decision:string-character-list-removal",
    "decision:strict-arity-codeobject",
}
STRINGS_REQUIRED_CASE_IDS = {
    "internal-concat-apply-not-designator",
    "internal-concat-funcall-not-designator",
    "internal-slice-apply-not-designator",
    "internal-slice-funcall-not-designator",
    "list-to-string-public-name-removed",
    "string-append-apply-multi",
    "string-append-empty",
    "string-append-funcall-one",
    "string-append-multi",
    "string-equal-apply",
    "string-equal-empty",
    "string-equal-false",
    "string-equal-funcall",
    "string-equal-true",
    "string-less-apply",
    "string-less-equal-false",
    "string-less-funcall",
    "string-less-lexicographic",
    "string-less-prefix",
    "string-length-apply",
    "string-length-direct",
    "string-length-funcall",
    "string-ref-apply",
    "string-ref-direct",
    "string-ref-funcall",
    "string-to-list-public-name-removed",
    "substring-apply-default",
    "substring-bounds-end-too-large",
    "substring-bounds-negative-start",
    "substring-bounds-reversed",
    "substring-empty",
    "substring-explicit-nil-default",
    "substring-funcall-explicit",
    "substring-full-default",
    "substring-middle",
    "substring-too-many",
}
STRINGS_PRELOADS = {
    "dialect-v1": {
        "native-c-treewalk": (
            "lib/prelude-m1.lisp", "lib/stdlib-lists.lisp",
            "lib/stdlib-strings.lisp",
        ),
        "native-c-compiler-vm": (
            "lib/prelude-m1.lisp", "lib/stdlib-lists.lisp",
            "lib/stdlib-strings.lisp",
        ),
    },
    "dialect-v2": {
        "native-c-treewalk": ("lib/dialect-v2/strings-core.lisp",),
        "native-c-compiler-vm": ("lib/dialect-v2/strings-core.lisp",),
    },
}
FAMILY_SPECS = {
    "prelude-control": {
        "format": "lisp65-dialect-v2-prelude-control-cases-v1",
        "anchors": PRELUDE_ANCHORS,
        "required_ids": PRELUDE_REQUIRED_CASE_IDS,
        "tiers": {"core"},
        "engines": set(ENGINES),
        "preloads": {
            profile: {"core": engines} for profile, engines in PRELUDE_PRELOADS.items()
        },
    },
    "lists": {
        "format": "lisp65-dialect-v2-lists-cases-v1",
        "anchors": LISTS_ANCHORS,
        "required_ids": LISTS_REQUIRED_CASE_IDS,
        "tiers": {"core", "library"},
        "engines": {"native-c-treewalk", "native-c-compiler-vm", "python-p0-compiler-vm", "lisp-lcc"},
        "preloads": LISTS_PRELOADS,
    },
    "eval-apply-funcall": {
        "format": "lisp65-dialect-v2-eval-apply-funcall-cases-v1",
        "block": "config/dialect-v2-eval-apply-funcall-block.json",
        "anchors": EVAL_APPLY_FUNCALL_ANCHORS,
        "required_ids": EVAL_APPLY_FUNCALL_REQUIRED_CASE_IDS,
        "tiers": {"core"},
        "engines": set(ENGINES),
        "preloads": {
            profile: {"core": engines}
            for profile, engines in EVAL_APPLY_FUNCALL_PRELOADS.items()
        },
    },
    "strings": {
        "format": "lisp65-dialect-v2-strings-cases-v1",
        "anchors": STRINGS_ANCHORS,
        "required_ids": STRINGS_REQUIRED_CASE_IDS,
        "tiers": {"core"},
        "engines": {
            "native-c-treewalk", "native-c-compiler-vm",
            "python-p0-compiler-vm", "lisp-lcc",
        },
        "preloads": {
            profile: {"core": engines}
            for profile, engines in STRINGS_PRELOADS.items()
        },
    },
}
# The all-view primitive registry closed the last Treewalk gap (`symbol-value`)
# on 2026-07-14. Stage 3 now pins the stronger invariant: no native blockers.
STRINGS_STAGE3_NATIVE_BLOCKERS = frozenset()
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
BUILD_SOURCES = (
    "src/eval.c", "src/compile.c", "src/compile_repl.c",
    "src/lcc_install_overlay.c", "src/vm.c", "src/mem.c", "src/symbol.c",
    "src/reader.c", "src/printer.c", "src/io.c", "src/interrupt.c", "src/screen.c",
)
COMMON_DEFINES = (
    "GC_ROOTS=1024", "HEAP_CELLS=8192", "IO_BUF_MAX=16",
    "LISP65_COMPILE_REPL", "LISP65_DIALECT_FAMILY_HARNESS",
    "LISP65_EVAL_CONTROL_SF", "LISP65_EVAL_PRIMS", "LISP65_LCC_INSTALL",
    "LISP65_MACROEXPAND_PRIM", "LISP65_NUMERIC_ERRORS", "LISP65_VM",
    "LISP65_VM_APPLY_OPFN", "LISP65_VM_GLOBAL_PRIMS", "MAX_SYM=512",
    "NAMEPOOL=8192", "VM_DIR_MAX=128",
)


class PreludeControlError(Exception):
    pass


def _validate_strings_source(text: str | None = None) -> None:
    source = (
        (ROOT / "lib" / "dialect-v2" / "strings-core.lisp").read_text(encoding="utf-8")
        if text is None else text
    )
    names = re.findall(r"\(defun\s+([^\s()]+)", source)
    public = {name for name in names if not name.startswith("%")}
    expected_public = {"substring", "string-append", "string=", "string<"}
    if public != expected_public or len(names) != len(set(names)):
        raise PreludeControlError("strings-core public/private definition surface drift")
    if "string->list" in source or "list->string" in source:
        raise PreludeControlError("strings-core reintroduced a character-list converter")
    if any(name in source for name in ("%string-slice", "%string-concat-list")):
        raise PreludeControlError("retired string capability was reintroduced")
    required = {
        "(%string-codes string)",
        "(%string-from-codes",
        "(%v2-substring-codes (%string-codes string)",
        "(%v2-string-append-codes strings nil)",
    }
    if any(needle not in source for needle in required):
        raise PreludeControlError("strings-core constructor lowering drift")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PreludeControlError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except PreludeControlError:
        raise
    except (OSError, ValueError) as exc:
        raise PreludeControlError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PreludeControlError("fixture root must be an object")
    return value


def _exact(value: Any, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise PreludeControlError(f"{where} keys drift: {actual}")
    return value


def _validate_family_block(family: str, fixture_format: str) -> None:
    spec = FAMILY_SPECS[family]
    relative = spec.get("block")
    if relative is None:
        return
    block = load_json(ROOT / relative)
    _exact(
        block,
        {
            "format", "version", "id", "status", "family", "fixture",
            "decision_anchors", "surface", "classification_gap", "carrier",
            "acceptance",
        },
        f"{family} block",
    )
    bound_fixture = _exact(block["fixture"], {"path", "format"}, f"{family} block fixture")
    acceptance = block["acceptance"]
    if not isinstance(acceptance, dict):
        raise PreludeControlError(f"{family} block acceptance must be an object")
    if (
        block["format"] != "lisp65-dialect-v2-block-v1"
        or block["id"] != "dialect-v2-eval-apply-funcall"
        or block["status"] != "pre-carrier-contract"
        or block["family"] != "system-runtime"
        or bound_fixture != {
            "path": "tests/bytecode/dialect-v2/eval-apply-funcall/cases.json",
            "format": fixture_format,
        }
        or set(block["decision_anchors"]) != spec["anchors"]
        or set(acceptance.get("required_engines", [])) != spec["engines"]
        or block["classification_gap"].get("blocks_profile_switch") is not True
        or set(block["carrier"].get("forbidden_in_this_stage", []))
        != {"src/eval.c", "src/mem.c", "src/vm.c"}
    ):
        raise PreludeControlError(f"{family} block binding drift")


def validate_fixture(value: dict[str, Any]) -> list[dict[str, Any]]:
    _exact(value, {"format", "profile", "family", "cases"}, "fixture")
    family = value["family"]
    spec = FAMILY_SPECS.get(family)
    if spec is None or (
        value["format"] != spec["format"]
        or value["profile"] != "dialect-v1-v2-differential"
    ):
        raise PreludeControlError("fixture identity drift")
    cases = value["cases"]
    if not isinstance(cases, list) or not cases:
        raise PreludeControlError("fixture cases must be a non-empty list")
    ids: list[str] = []
    seen_anchors: set[str] = set()
    for index, raw in enumerate(cases):
        case_keys = {"id", "forms", "migration_anchor", "observations"}
        if family == "lists":
            case_keys.add("tier")
        case = _exact(raw, case_keys, f"cases[{index}]")
        case_id = case["id"]
        if not isinstance(case_id, str) or not ID_RE.fullmatch(case_id):
            raise PreludeControlError(f"cases[{index}] has invalid id")
        ids.append(case_id)
        anchor = case["migration_anchor"]
        if anchor is not None and anchor not in spec["anchors"]:
            raise PreludeControlError(f"case {case_id} has unknown migration_anchor")
        if anchor is not None:
            seen_anchors.add(anchor)
        tier = case.get("tier", "core")
        if tier not in spec["tiers"]:
            raise PreludeControlError(f"case {case_id} has invalid tier")
        forms = case["forms"]
        if not isinstance(forms, list) or not forms or any(
            not isinstance(form, str) or not form.strip() for form in forms
        ):
            raise PreludeControlError(f"case {case_id} has invalid forms")
        observations = _exact(case["observations"], set(PROFILES), f"case {case_id} observations")
        for profile in PROFILES:
            engines = _exact(observations[profile], spec["engines"], f"case {case_id}/{profile}")
            for engine in spec["engines"]:
                expected = engines[engine]
                if not isinstance(expected, str) or not expected or expected != expected.strip():
                    raise PreludeControlError(f"case {case_id}/{profile}/{engine} has invalid observation")
        divergent = any(
            observations["dialect-v1"][engine] != observations["dialect-v2"][engine]
            for engine in spec["engines"]
        )
        if divergent != (anchor is not None):
            raise PreludeControlError(
                f"case {case_id} migration_anchor must be set exactly for cross-profile drift"
            )
    if ids != sorted(set(ids)):
        raise PreludeControlError("fixture case ids must be sorted and unique")
    if set(ids) != spec["required_ids"]:
        missing = sorted(spec["required_ids"] - set(ids))
        extra = sorted(set(ids) - spec["required_ids"])
        raise PreludeControlError(f"fixture coverage drift: missing={missing} extra={extra}")
    if seen_anchors != spec["anchors"]:
        raise PreludeControlError("fixture does not cover every migration_anchor")
    if family == "strings":
        _validate_strings_source()
    _validate_family_block(family, value["format"])
    return cases


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise PreludeControlError(f"build provenance path leaves repository: {path}") from exc


def _build_inputs(profile: str, source_root: Path) -> tuple[str, ...]:
    headers = tuple(
        path.relative_to(source_root).as_posix()
        for path in sorted((source_root / "src").glob("*.h"))
    )
    preloads = tuple(
        dict.fromkeys(
            source for engine in ENGINES for source in PRELUDE_PRELOADS[profile][engine]
        )
    )
    return tuple(sorted(("Makefile", "scripts/equivalence-main.c", *BUILD_SOURCES, *headers, *preloads)))


def _build_defines(profile: str) -> list[str]:
    if profile not in PROFILES:
        raise PreludeControlError(f"unknown build profile: {profile}")
    if profile == "dialect-v1":
        profile_defines = ("LISP65_FROZEN_V1_HARNESS",)
    else:
        profile_defines = (
            "LISP65_DIALECT_V2",
            "LISP65_STRING_ARENA",
            "LISP65_V2_NATIVE_CAPABILITIES",
            "LISP65_V2_NATIVE_STRING_CODECS",
        )
    return sorted((*COMMON_DEFINES, *profile_defines))


def _build_profile_sha(value: dict[str, Any]) -> str:
    profile = {
        key: value[key]
        for key in (
            "format", "profile", "source_commit", "make_target", "compiler",
            "makefile_sha256", "input_bindings", "defines",
        )
    }
    encoded = json.dumps(profile, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def record_build(
    profile: str,
    binary: Path,
    compiler: str,
    output: Path,
    source_commit: str | None,
    source_root: Path,
) -> None:
    if binary.is_symlink() or not binary.is_file():
        raise PreludeControlError(f"profile binary is missing: {binary}")
    compiler_path_text = shutil.which(compiler)
    if compiler_path_text is None:
        raise PreludeControlError(f"cannot resolve host compiler: {compiler}")
    compiler_path = Path(compiler_path_text).resolve()
    if not compiler_path.is_file():
        raise PreludeControlError(f"host compiler is not a file: {compiler_path}")
    if source_commit is not None and not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise PreludeControlError("source commit must be null or a full lowercase commit id")
    if profile == "dialect-v1" and source_commit != FROZEN_V1_COMMIT:
        raise PreludeControlError("dialect-v1 build must bind the frozen f6527d25 source commit")
    if profile == "dialect-v2" and source_commit is not None:
        raise PreludeControlError("dialect-v2 candidate build must bind the worktree, not a frozen commit")
    input_bindings = []
    for path in _build_inputs(profile, source_root):
        from_root = path in {"Makefile", "scripts/equivalence-main.c"}
        source = (ROOT if from_root else source_root) / path
        if source.is_symlink() or not source.is_file():
            raise PreludeControlError(f"build input is missing: {source}")
        origin = (
            f"worktree:{path}" if from_root or profile == "dialect-v2"
            else f"git:{source_commit}:{path}"
        )
        input_bindings.append({"path": path, "origin": origin, "sha256": _sha256(source)})
    value: dict[str, Any] = {
        "format": "lisp65-dialect-v2-profile-build-v1",
        "profile": profile,
        "source_commit": source_commit,
        "make_target": _relative(binary),
        "binary_sha256": _sha256(binary),
        "compiler": {"name": compiler_path.name, "sha256": _sha256(compiler_path)},
        "makefile_sha256": _sha256(ROOT / "Makefile"),
        "input_bindings": input_bindings,
        "defines": _build_defines(profile),
    }
    value["build_profile_sha256"] = _build_profile_sha(value)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_canonical(value))


def validate_build(
    value: dict[str, Any], profile: str, binary: Path, source_root: Path
) -> dict[str, Any]:
    _exact(
        value,
        {
            "format", "profile", "source_commit", "make_target", "binary_sha256",
            "build_profile_sha256", "compiler", "makefile_sha256", "input_bindings",
            "defines",
        },
        f"{profile} build provenance",
    )
    compiler = _exact(value["compiler"], {"name", "sha256"}, f"{profile} compiler")
    if (
        value["format"] != "lisp65-dialect-v2-profile-build-v1"
        or value["profile"] != profile
        or value["make_target"] != _relative(binary)
        or value["binary_sha256"] != _sha256(binary)
        or value["build_profile_sha256"] != _build_profile_sha(value)
        or value["makefile_sha256"] != _sha256(ROOT / "Makefile")
        or value["defines"] != _build_defines(profile)
    ):
        raise PreludeControlError(f"{profile} build provenance identity drift")
    if profile == "dialect-v1" and value["source_commit"] != FROZEN_V1_COMMIT:
        raise PreludeControlError("dialect-v1 build does not bind the frozen source commit")
    if profile == "dialect-v2" and value["source_commit"] is not None:
        raise PreludeControlError("dialect-v2 build must bind the candidate worktree")
    if (
        not isinstance(compiler["name"], str) or not compiler["name"]
        or not isinstance(compiler["sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", compiler["sha256"])
        or (value["source_commit"] is not None and not re.fullmatch(r"[0-9a-f]{40}", value["source_commit"]))
    ):
        raise PreludeControlError(f"{profile} compiler/source provenance drift")
    compiler_path_text = shutil.which(compiler["name"])
    if compiler_path_text is None:
        raise PreludeControlError(f"{profile} build compiler is unavailable: {compiler['name']}")
    compiler_path = Path(compiler_path_text).resolve()
    if not compiler_path.is_file() or _sha256(compiler_path) != compiler["sha256"]:
        raise PreludeControlError(f"{profile} build compiler SHA drift")
    bindings = value["input_bindings"]
    expected_paths = list(_build_inputs(profile, source_root))
    if not isinstance(bindings, list) or [item.get("path") for item in bindings if isinstance(item, dict)] != expected_paths:
        raise PreludeControlError(f"{profile} build input coverage drift")
    for index, raw in enumerate(bindings):
        item = _exact(raw, {"path", "origin", "sha256"}, f"{profile} input_bindings[{index}]")
        from_root = item["path"] in {"Makefile", "scripts/equivalence-main.c"}
        expected_origin = (
            f"worktree:{item['path']}" if from_root or profile == "dialect-v2"
            else f"git:{value['source_commit']}:{item['path']}"
        )
        if item["origin"] != expected_origin:
            raise PreludeControlError(f"{profile} build input origin drift: {item['path']}")
        path = (ROOT if from_root else source_root) / item["path"]
        if path.is_symlink() or not path.is_file() or _sha256(path) != item["sha256"]:
            raise PreludeControlError(f"{profile} build input SHA drift: {item['path']}")
    return value


def _observation_sha(observed: str) -> str:
    return hashlib.sha256(observed.encode("utf-8")).hexdigest()


def _combined_preload(
    family: str, tier: str, profile: str, engine: str, directory: Path, source_root: Path,
) -> Path:
    output = directory / f"{family}-{tier}-{profile}-{engine}-preload.lisp"
    parts: list[str] = []
    for relative in FAMILY_SPECS[family]["preloads"][profile][tier][engine]:
        source = source_root / relative
        if source.is_file():
            parts.append(source.read_text(encoding="utf-8"))
            continue
        if profile == "dialect-v1":
            frozen = subprocess.run(
                ["git", "show", f"{FROZEN_V1_COMMIT}:{relative}"],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            if frozen.returncode == 0:
                parts.append(frozen.stdout)
                continue
        raise PreludeControlError(f"missing {profile}/{engine} preload: {relative}")
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return output


def _parse_results(stdout: str, expected_count: int, label: str) -> list[str]:
    results = [line.rsplit(" => ", 1)[1].strip() for line in stdout.splitlines() if " => " in line]
    if len(results) != expected_count:
        raise PreludeControlError(
            f"{label}: harness returned {len(results)} observations for {expected_count} forms"
        )
    return results


def _run_case(
    binary: Path,
    profile: str,
    engine: str,
    case: dict[str, Any],
    preload: Path,
    directory: Path,
) -> str:
    forms_path = directory / f"{profile}-{engine}-{case['id']}.lisp"
    forms_path.write_text("\n".join(case["forms"]) + "\n", encoding="utf-8")
    command = [str(binary), ENGINE_MODES[engine], str(forms_path), "--preload", str(preload)]
    try:
        process = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PreludeControlError(f"{profile}/{engine}/{case['id']}: harness failed: {exc}") from exc
    if process.returncode != 0:
        raise PreludeControlError(
            f"{profile}/{engine}/{case['id']}: harness exited {process.returncode}: {process.stderr.strip()}"
        )
    return _parse_results(
        process.stdout,
        len(case["forms"]),
        f"{profile}/{engine}/{case['id']}",
    )[-1]


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _validate_strings_stage3_blockers(
    mismatches: set[tuple[str, str, str]],
) -> None:
    if mismatches != STRINGS_STAGE3_NATIVE_BLOCKERS:
        missing = sorted(STRINGS_STAGE3_NATIVE_BLOCKERS - mismatches)
        extra = sorted(mismatches - STRINGS_STAGE3_NATIVE_BLOCKERS)
        raise PreludeControlError(
            f"strings Stage-3 native blocker drift: missing={missing} extra={extra}"
        )


def run_matrix(
    fixture_path: Path,
    v1_binary: Path,
    v2_binary: Path,
    v1_build: Path,
    v2_build: Path,
    output_dir: Path,
    engines: tuple[str, ...] = ENGINES,
    preload_roots: dict[str, Path] | None = None,
    stage3_carrier_active: bool = False,
) -> int:
    fixture = load_json(fixture_path)
    cases = validate_fixture(fixture)
    family = fixture["family"]
    if stage3_carrier_active and (
        family != "strings" or len(engines) != len(ENGINES) or set(engines) != set(ENGINES)
    ):
        raise PreludeControlError(
            "--stage3-carrier-active requires Strings and both native engines"
        )
    binaries = {"dialect-v1": v1_binary, "dialect-v2": v2_binary}
    for profile, binary in binaries.items():
        if not binary.is_file():
            raise PreludeControlError(
                f"missing {profile} equivalence harness: {binary}; {interface_text()}"
            )
    if v1_binary.resolve() == v2_binary.resolve():
        raise PreludeControlError("v1 and v2 must use distinct profile binaries")
    if _sha256(v1_binary) == _sha256(v2_binary):
        raise PreludeControlError("v1 and v2 profile binaries are byte-identical")
    roots = preload_roots or {profile: ROOT for profile in PROFILES}
    builds = {
        "dialect-v1": validate_build(
            load_json(v1_build), "dialect-v1", v1_binary, roots["dialect-v1"]
        ),
        "dialect-v2": validate_build(
            load_json(v2_build), "dialect-v2", v2_binary, roots["dialect-v2"]
        ),
    }
    fixture_sha = _sha256(fixture_path)
    failed = 0
    mismatches: set[tuple[str, str, str]] = set()
    with tempfile.TemporaryDirectory(prefix="lisp65-ap84-") as temporary:
        temp = Path(temporary)
        for profile in PROFILES:
            for engine in engines:
                verdict_cases: list[dict[str, Any]] = []
                preload_shas: dict[str, str] = {}
                for case in cases:
                    tier = case.get("tier", "core")
                    preload = _combined_preload(
                        family, tier, profile, engine, temp, roots[profile]
                    )
                    preload_shas[tier] = _sha256(preload)
                    observed = _run_case(
                        binaries[profile], profile, engine, case, preload, temp
                    )
                    expected = case["observations"][profile][engine]
                    accepted = observed == expected
                    failed += int(not accepted)
                    if not accepted:
                        mismatches.add((profile, engine, case["id"]))
                    verdict_cases.append(
                        {
                            "id": case["id"],
                            "decision": case["migration_anchor"],
                            "verdict": "accept" if accepted else "reject",
                            "result_sha256": _observation_sha(observed),
                        }
                    )
                    print(
                        f"{profile}/{engine}/{case['id']}: "
                        f"{'PASS' if accepted else 'FAIL'} observed={observed} expected={expected}"
                    )
                verdict = {
                    "format": "lisp65-dialect-v2-family-verdict-v1",
                    "family": family,
                    "profile": profile,
                    "engine": engine,
                    "fixture_sha256": fixture_sha,
                    "provenance": {
                        "source_commit": builds[profile]["source_commit"],
                        "binary_sha256": builds[profile]["binary_sha256"],
                        "build_profile_sha256": builds[profile]["build_profile_sha256"],
                        "preload_sha256": (
                            next(iter(preload_shas.values()))
                            if len(preload_shas) == 1
                            else hashlib.sha256(
                                "".join(
                                    f"{tier}:{preload_shas[tier]}\n"
                                    for tier in sorted(preload_shas)
                                ).encode("ascii")
                            ).hexdigest()
                        ),
                    },
                    "cases": verdict_cases,
                }
                _write_json(output_dir / f"{profile}-{engine}-verdict.json", verdict)
    if stage3_carrier_active:
        _validate_strings_stage3_blockers(mismatches)
        print(
            f"dialect-v2-strings: STAGE3 PASS cases={len(cases)} "
            f"runs={len(cases) * len(PROFILES) * len(engines)} "
            f"carrier-cut-blockers={len(mismatches)}"
        )
        return 0
    print(
        f"dialect-v2-{family}: {'PASS' if failed == 0 else 'FAIL'} "
        f"cases={len(cases)} runs={len(cases) * len(PROFILES) * len(engines)} failed={failed}"
    )
    return 0 if failed == 0 else 1


def interface_text() -> str:
    return (
        "required interface: separate frozen-v1 and candidate-v2 binaries, each accepting "
        "`tree|vm FORMS [--preload SOURCE]` and printing one `SOURCE => OBSERVATION` "
        "line per form; Lisp failures must be normalized to `!error:<class>` while the process exits 0"
    )


def selftest(fixture_path: Path) -> None:
    fixture = load_json(fixture_path)
    cases = validate_fixture(fixture)
    family = fixture["family"]
    spec = FAMILY_SPECS[family]
    checks = 1

    def expect_failure(label: str, mutate: Any) -> None:
        nonlocal checks
        candidate = copy.deepcopy(fixture)
        mutate(candidate)
        try:
            validate_fixture(candidate)
        except PreludeControlError:
            checks += 1
            return
        raise PreludeControlError(f"selftest mutation accepted: {label}")

    expect_failure("missing case", lambda value: value["cases"].pop())
    expect_failure("unknown anchor", lambda value: value["cases"][0].update(migration_anchor="unknown"))
    invariant_index = next(
        index for index, case in enumerate(cases) if case["migration_anchor"] is None
    )
    expect_failure(
        "anchor on invariant case",
        lambda value: value["cases"][invariant_index].update(
            migration_anchor=sorted(spec["anchors"])[0]
        ),
    )
    divergent_index = next(
        index for index, case in enumerate(cases) if case["migration_anchor"] is not None
    )
    expect_failure(
        "missing divergent anchor",
        lambda value: value["cases"][divergent_index].update(migration_anchor=None),
    )
    expect_failure(
        "missing engine observation",
        lambda value: value["cases"][0]["observations"]["dialect-v2"].pop("native-c-compiler-vm"),
    )
    expect_failure("identity drift", lambda value: value.update(profile="dialect-v2"))
    if family == "strings":
        source = (ROOT / "lib" / "dialect-v2" / "strings-core.lisp").read_text(
            encoding="utf-8"
        )
        for label, mutated in (
            ("public surface", source.replace("(defun string<", "(defun string>")),
            ("character-list converter", source + "\n; string->list\n"),
            ("constructor lowering", source.replace("(%string-codes string)", "(missing string)")),
        ):
            try:
                _validate_strings_source(mutated)
            except PreludeControlError:
                checks += 1
            else:
                raise PreludeControlError(f"selftest mutation accepted: strings {label}")
        _validate_strings_stage3_blockers(set(STRINGS_STAGE3_NATIVE_BLOCKERS))
        try:
            _validate_strings_stage3_blockers(
                set(STRINGS_STAGE3_NATIVE_BLOCKERS)
                | {("dialect-v1", "native-c-treewalk", "unexpected")}
            )
        except PreludeControlError:
            checks += 1
        else:
            raise PreludeControlError("selftest accepted an additional Stage-3 blocker")
    parsed = _parse_results("a => 1\nb => !error\n", 2, "selftest")
    if parsed != ["1", "!error"]:
        raise PreludeControlError("selftest output parser drift")
    checks += 1
    runs = len(cases) * len(PROFILES) * len(ENGINES)
    if runs != len(cases) * 4:
        raise PreludeControlError("selftest matrix cardinality drift")
    checks += 1
    print(f"dialect-v2-{family}: SELFTEST PASS checks={checks} cases={len(cases)} runs={runs}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check")
    subparsers.add_parser("selftest")
    subparsers.add_parser("interface")
    run = subparsers.add_parser("run")
    run.add_argument("--binary-v1", type=Path, default=DEFAULT_V1_BINARY)
    run.add_argument("--binary-v2", type=Path, default=DEFAULT_V2_BINARY)
    run.add_argument("--build-receipt-v1", type=Path, default=DEFAULT_V1_BUILD)
    run.add_argument("--build-receipt-v2", type=Path, default=DEFAULT_V2_BUILD)
    run.add_argument("--engine", choices=ENGINES, action="append")
    run.add_argument("--stage3-carrier-active", action="store_true")
    run.add_argument("--source-root-v1", type=Path, default=DEFAULT_V1_SOURCE_ROOT)
    run.add_argument("--source-root-v2", type=Path, default=ROOT)
    run.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "build/bytecode/dialect-v2/prelude-control",
    )
    record = subparsers.add_parser("record-build")
    record.add_argument("--profile", choices=PROFILES, required=True)
    record.add_argument("--binary", type=Path, required=True)
    record.add_argument("--compiler", required=True)
    record.add_argument("--output", type=Path, required=True)
    record.add_argument("--source-commit")
    record.add_argument("--source-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            cases = validate_fixture(load_json(args.fixture))
            family = load_json(args.fixture)["family"]
            print(f"dialect-v2-{family}: PASS cases={len(cases)} runs={len(cases) * 4}")
            return 0
        if args.command == "selftest":
            selftest(args.fixture)
            return 0
        if args.command == "interface":
            print(interface_text())
            return 0
        if args.command == "record-build":
            record_build(
                args.profile, args.binary, args.compiler, args.output,
                args.source_commit, args.source_root,
            )
            print(f"dialect-v2-prelude-control: BUILD RECORDED profile={args.profile}")
            return 0
        engines = tuple(args.engine) if args.engine else ENGINES
        if len(set(engines)) != len(engines):
            raise PreludeControlError("--engine selections must be unique")
        return run_matrix(
            args.fixture, args.binary_v1, args.binary_v2,
            args.build_receipt_v1, args.build_receipt_v2,
            args.output_dir, engines,
            {"dialect-v1": args.source_root_v1, "dialect-v2": args.source_root_v2},
            args.stage3_carrier_active,
        )
    except PreludeControlError as exc:
        print(f"dialect-v2-prelude-control: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
