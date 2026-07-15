#!/usr/bin/env python3
"""Verify the dialect-v2 invalid-parameter LCC error across honest engine channels."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST_TOOLS = ROOT / "tools" / "host-lisp"
if str(HOST_TOOLS) not in sys.path:
    sys.path.insert(0, str(HOST_TOOLS))

import bytecode_p0 as P0  # noqa: E402
import bytecode_p0_compiler as P0C  # noqa: E402
import bytecode_p0_stdlib as Stdlib  # noqa: E402
import v2_workbench_codemod as Codemod  # noqa: E402


DEFAULT_FIXTURE = (
    ROOT / "tests/bytecode/dialect-v2/lcc-surface/invalid-parameter-list.json"
)
DEFAULT_BINARY = ROOT / "build/equivalence/dialect-v2-equivalence-check"
DEFAULT_MANIFEST = (
    ROOT / "build/bytecode/dialect-v2/workbench/stdlib-p0.manifest.json"
)
DEFAULT_INVENTORY = (
    ROOT / "build/bytecode/dialect-v2/workbench-service-call-inventory.json"
)
DEFAULT_OUTPUT = (
    ROOT / "build/bytecode/dialect-v2/lcc-invalid-parameter-list-verdict.json"
)
FORMAT = "lisp65-dialect-v2-lcc-compile-error-case-v1"
RECEIPT_FORMAT = "lisp65-dialect-v2-lcc-compile-error-verdict-v1"
SENTINEL = "%lcc-error-invalid-parameter-list"
ERROR_CODE = 59
PRIM_ID = 56
EXPECTED_OBSERVATION = (
    "!error:code=59:symbol=%lcc-error-invalid-parameter-list"
)
ENGINES = (
    "native-c-treewalk",
    "native-c-compiler-vm",
    "python-p0-compiler-vm",
    "lisp-lcc",
)
ENGINE_MODES = {
    "native-c-treewalk": "tree",
    "native-c-compiler-vm": "vm",
    "python-p0-compiler-vm": "python-p0",
    "lisp-lcc": "lcc",
}
ENGINE_COVERAGE = {
    "native-c-treewalk": "live-code-and-sentinel",
    "native-c-compiler-vm": "live-code-and-sentinel",
    "python-p0-compiler-vm": "live-code-and-sentinel",
    "lisp-lcc": "live-code-and-sentinel",
}
LCC_SOURCES = ("lib/lcc.lisp", "lib/dialect-v2/lcc-profile.lisp")
PROFILE_EXCLUDED_FOR_FOCUSED_PRELOAD = {
    "%lcc-do-p", "%lcc-expr-ops2", "%lcc-opform-p", "%lcc-prim",
    "%lcc-sf-p", "%lcc-v2-prim2", "%lcc-v2-prim3", "%lcc-v2-prim4",
}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
DEFINE_RE = re.compile(r"^#define\s+([A-Z0-9_]+)\s+([0-9]+)u$", re.MULTILINE)
MANIFEST_HARNESS = ROOT / "scripts/dialect-v2-lcc-manifest-main.c"


class CompileErrorCaseError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise CompileErrorCaseError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object
        )
    except CompileErrorCaseError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompileErrorCaseError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise CompileErrorCaseError(f"{label} must be an object")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise CompileErrorCaseError(f"{label} keys drift: {actual}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise CompileErrorCaseError(f"path escapes repository: {path}") from exc


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _repo_artifact(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise CompileErrorCaseError(f"resident manifest {label} is not a path")
    path = ROOT / value
    try:
        path.resolve().relative_to(ROOT.resolve())
    except ValueError as exc:
        raise CompileErrorCaseError(
            f"resident manifest {label} escapes repository"
        ) from exc
    if path.is_symlink() or not path.is_file():
        raise CompileErrorCaseError(f"resident manifest {label} is missing")
    return path


def _validate_resident_artifact(
    manifest_path: Path,
    *,
    manifest_override: dict[str, Any] | None = None,
    blob_override: bytes | None = None,
) -> dict[str, Any]:
    try:
        manifest_path.resolve().relative_to(ROOT.resolve())
    except ValueError as exc:
        raise CompileErrorCaseError("resident manifest escapes repository") from exc
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise CompileErrorCaseError("resident v2 manifest is missing")
    manifest = (
        deepcopy(manifest_override)
        if manifest_override is not None
        else _load(manifest_path, "resident v2 manifest")
    )
    if (
        manifest.get("format") != "lisp65-bytecode-p0-stdlib-artifacts-v1"
        or manifest.get("abi_profile") != "dialect-v2"
        or manifest.get("strict_arity") is not True
        or manifest.get("artifact_role") != "stdlib"
    ):
        raise CompileErrorCaseError("resident manifest profile/format drift")
    expected_sha = manifest.get("blob_sha256")
    if not isinstance(expected_sha, str) or not SHA_RE.fullmatch(expected_sha):
        raise CompileErrorCaseError("resident manifest blob SHA is malformed")
    blob_path = _repo_artifact(manifest.get("blob"), "blob")
    header_path = _repo_artifact(manifest.get("header"), "header")
    c_source_path = _repo_artifact(manifest.get("c_source"), "C source")
    blob = blob_override if blob_override is not None else blob_path.read_bytes()
    if hashlib.sha256(blob).hexdigest() != expected_sha:
        raise CompileErrorCaseError("resident manifest/blob SHA mismatch")
    code_bytes = manifest.get("code_bytes")
    entries = manifest.get("entries")
    literal_index = manifest.get("literal_index")
    literal_nodes = manifest.get("literal_nodes")
    literal_patches = manifest.get("literal_patches")
    if not isinstance(code_bytes, int) or code_bytes != len(blob):
        raise CompileErrorCaseError("resident manifest blob length drift")
    if not all(
        isinstance(value, list)
        for value in (entries, literal_index, literal_nodes, literal_patches)
    ):
        raise CompileErrorCaseError("resident manifest metadata is incomplete")
    if len(literal_index) != len(literal_nodes):
        raise CompileErrorCaseError("resident manifest literal index count drift")
    if not any(
        isinstance(entry, dict) and entry.get("name") == "lcc-compile-obj"
        for entry in entries
    ):
        raise CompileErrorCaseError("resident manifest omits lcc-compile-obj")
    expected_offset = 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise CompileErrorCaseError(f"resident entry {index} is malformed")
        offset, length = entry.get("blob_offset"), entry.get("length")
        if (
            not isinstance(offset, int)
            or not isinstance(length, int)
            or offset != expected_offset
            or length <= 0
            or offset + length > len(blob)
        ):
            raise CompileErrorCaseError(f"resident entry {index} layout drift")
        expected_offset += length
    if expected_offset != len(blob):
        raise CompileErrorCaseError("resident entries do not cover the bound blob")
    for index, node_index in enumerate(literal_index):
        if not isinstance(node_index, int) or not 0 <= node_index < len(literal_nodes):
            raise CompileErrorCaseError(f"literal index {index} is out of range")
    for index, patch in enumerate(literal_patches):
        if not isinstance(patch, dict):
            raise CompileErrorCaseError(f"literal patch {index} is malformed")
        offset, node = patch.get("blob_offset"), patch.get("node")
        if (
            not isinstance(offset, int)
            or not isinstance(node, int)
            or not 0 <= offset <= len(blob) - 2
            or not 0 <= node < len(literal_nodes)
        ):
            raise CompileErrorCaseError(f"literal patch {index} is out of range")
    header = header_path.read_text(encoding="utf-8")
    defines = {key: int(value) for key, value in DEFINE_RE.findall(header)}
    expected_defines = {
        "LISP65_BYTECODE_STDLIB_BLOB_BYTES": len(blob),
        "LISP65_BYTECODE_STDLIB_EMBED_COUNT": len(entries),
        "LISP65_BYTECODE_STDLIB_LITERAL_INDEX_COUNT": len(literal_index),
        "LISP65_BYTECODE_STDLIB_LITERAL_NODE_COUNT": len(literal_nodes),
        "LISP65_BYTECODE_STDLIB_LITERAL_PATCH_COUNT": len(literal_patches),
    }
    if any(defines.get(key) != value for key, value in expected_defines.items()):
        raise CompileErrorCaseError("generated header differs from resident manifest")
    if not c_source_path.read_text(encoding="utf-8").startswith(
        "/* generated by tools/host-lisp/bytecode_p0_stdlib.py; do not edit */"
    ):
        raise CompileErrorCaseError("resident generated C source provenance drift")
    return {
        "manifest": manifest,
        "manifest_path": manifest_path,
        "blob_path": blob_path,
        "header_path": header_path,
        "c_source_path": c_source_path,
        "blob": blob,
    }


def _validate_inventory_binding(
    inventory_path: Path,
    artifact: dict[str, Any],
    *,
    inventory_override: dict[str, Any] | None = None,
) -> dict[str, str]:
    try:
        inventory_path.resolve().relative_to(ROOT.resolve())
    except ValueError as exc:
        raise CompileErrorCaseError("service inventory escapes repository") from exc
    if inventory_path.is_symlink() or not inventory_path.is_file():
        raise CompileErrorCaseError("staging service inventory is missing")
    inventory = (
        deepcopy(inventory_override)
        if inventory_override is not None
        else _load(inventory_path, "staging service inventory")
    )
    records = inventory.get("artifacts")
    if not isinstance(records, list):
        raise CompileErrorCaseError("staging service inventory artifacts are missing")
    resident = [
        item for item in records
        if isinstance(item, dict) and item.get("id") == "resident"
    ]
    if len(resident) != 1:
        raise CompileErrorCaseError("staging service inventory resident binding drift")
    record = resident[0]
    manifest_sha = _sha(artifact["manifest_path"])
    blob_sha = hashlib.sha256(artifact["blob"]).hexdigest()
    if (
        record.get("abi_profile") != "dialect-v2"
        or record.get("manifest") != _relative(artifact["manifest_path"])
        or record.get("blob") != _relative(artifact["blob_path"])
        or record.get("manifest_sha256") != manifest_sha
        or record.get("blob_sha256") != blob_sha
    ):
        raise CompileErrorCaseError(
            "staging inventory manifest/blob SHA binding mismatch"
        )
    return {"path": _relative(inventory_path), "sha256": _sha(inventory_path)}


def _write_blob_source(path: Path, blob: bytes) -> None:
    lines = ["#include <stdint.h>", "const uint8_t lisp65_stdlib_blob[] = {"]
    for offset in range(0, len(blob), 16):
        lines.append(
            "    " + ", ".join(f"0x{byte:02x}" for byte in blob[offset:offset + 16]) + ","
        )
    lines.extend(("};", ""))
    path.write_text("\n".join(lines), encoding="ascii")


def _run_manifest_vm(
    manifest_path: Path, inventory_path: Path, source: str, directory: Path,
) -> tuple[str, list[dict[str, str]], list[str]]:
    artifact = _validate_resident_artifact(manifest_path)
    inventory_binding = _validate_inventory_binding(inventory_path, artifact)
    if MANIFEST_HARNESS.is_symlink() or not MANIFEST_HARNESS.is_file():
        raise CompileErrorCaseError("native resident-manifest harness is missing")
    blob_source = directory / "resident-v2-blob.c"
    source_path = directory / "invalid-parameter-manifest-vm.lisp"
    binary = directory / "dialect-v2-lcc-manifest-vm"
    _write_blob_source(blob_source, artifact["blob"])
    source_path.write_text(source + "\n", encoding="utf-8")
    compiler = os.environ.get("HOSTCC", "cc")
    definitions = (
        "LISP65_VM", "LISP65_DIALECT_V2", "LISP65_V2_SERVICE_REGISTRY_CLOSED",
        "LISP65_V2_WORKBENCH_SERVICES",
        "LISP65_STRING_ARENA", "LISP65_V2_NATIVE_CAPABILITIES",
        "LISP65_V2_NATIVE_STRING_CODECS", "LISP65_VM_NATIVE_APPLY",
        "LISP65_VM_GLOBAL_PRIMS", "LISP65_NUMERIC_ERRORS",
        "LISP65_TREEWALK_STRIP", "LISP65_V2_CARRIER_CUT",
        "LISP65_LCC_INSTALL",
        "LISP65_STDLIB_EXTERNAL_BLOB", "LISP65_BYTECODE_STDLIB_EMIT_METADATA",
    )
    command = [
        compiler, "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-Wno-unused-function", "-fsanitize=address,undefined",
        "-fno-omit-frame-pointer",
        *(f"-D{value}" for value in definitions),
        "-DHEAP_CELLS=8192", "-DGC_ROOTS=4096", "-DMAX_SYM=1024",
        "-DNAMEPOOL=32768", "-DSTR_ARENA_SIZE=16384", "-DVM_DIR_MAX=352",
        "-DVM_CODEBUF=256", f"-I{ROOT / 'src'}",
        f"-I{artifact['header_path'].parent}", str(MANIFEST_HARNESS),
        str(blob_source), str(artifact["c_source_path"]),
        str(ROOT / "src/eval.c"), str(ROOT / "src/lcc_install_overlay.c"),
        str(ROOT / "src/vm.c"), str(ROOT / "src/mem.c"),
        str(ROOT / "src/symbol.c"), str(ROOT / "src/reader.c"),
        str(ROOT / "src/printer.c"), str(ROOT / "src/interrupt.c"),
        "-o", str(binary),
    ]
    try:
        built = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True,
            timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CompileErrorCaseError(f"native manifest VM build failed: {exc}") from exc
    if built.returncode:
        raise CompileErrorCaseError(
            "native manifest VM build failed: " + built.stderr.strip()
        )
    environment = os.environ.copy()
    environment["ASAN_OPTIONS"] = "detect_leaks=0:halt_on_error=1"
    environment["UBSAN_OPTIONS"] = "halt_on_error=1"
    try:
        process = subprocess.run(
            [str(binary), str(source_path)], cwd=ROOT, capture_output=True,
            text=True, timeout=30, check=False, env=environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CompileErrorCaseError(f"native manifest VM failed: {exc}") from exc
    if process.returncode:
        raise CompileErrorCaseError(
            f"native manifest VM exited {process.returncode}: {process.stderr.strip()}"
        )
    observations = [
        line.strip() for line in process.stdout.splitlines()
        if line.startswith("!error:")
    ]
    if len(observations) != 1:
        raise CompileErrorCaseError(
            f"native manifest VM returned {len(observations)} observations"
        )
    surface = [
        line.strip() for line in process.stdout.splitlines()
        if line.startswith("surface:")
    ]
    expected_surface = [
        "surface:eval-direct=42",
        "surface:funcall-eval=42",
        "surface:apply-eval=42",
    ]
    if surface != expected_surface:
        raise CompileErrorCaseError(
            f"native carrier-cut surface drift: {surface}"
        )
    bindings = [
        {"path": _relative(path), "sha256": _sha(path)}
        for path in (
            artifact["manifest_path"], artifact["blob_path"],
            artifact["header_path"], artifact["c_source_path"], MANIFEST_HARNESS,
        )
    ]
    bindings.append(inventory_binding)
    return observations[0], bindings, surface


def validate_fixture(value: dict[str, Any]) -> dict[str, Any]:
    _exact(
        value,
        {"format", "id", "source", "expected", "engines"},
        "fixture",
    )
    if value["format"] != FORMAT or value["id"] != "arity-invalid-duplicate-marker-code59":
        raise CompileErrorCaseError("fixture identity drift")
    if (
        not isinstance(value["source"], str)
        or "&optional &optional" not in value["source"]
    ):
        raise CompileErrorCaseError("fixture no longer exercises a duplicate optional marker")
    expected = _exact(value["expected"], {"error_code", "sentinel", "prim_id"}, "expected")
    if expected != {"error_code": ERROR_CODE, "sentinel": SENTINEL, "prim_id": PRIM_ID}:
        raise CompileErrorCaseError("Code59/sentinel/Prim-ID expectation drift")
    engines = _exact(value["engines"], set(ENGINES), "engines")
    for engine in ENGINES:
        record = _exact(
            engines[engine], {"mode", "coverage", "expected_observation"},
            f"engines.{engine}",
        )
        if record["mode"] != ENGINE_MODES[engine] or record["coverage"] != ENGINE_COVERAGE[engine]:
            raise CompileErrorCaseError(f"{engine} mode/coverage drift")
        observation = record["expected_observation"]
        if observation != EXPECTED_OBSERVATION:
            raise CompileErrorCaseError(
                f"{engine} must pin code 59 and the exact sentinel"
            )
    return value


def _validate_static_contracts() -> list[dict[str, str]]:
    ledger_path = ROOT / "config/bytecode-abi-ledger.json"
    errors_path = ROOT / "config/error-code-contract.json"
    ledger = _load(ledger_path, "bytecode ABI ledger")
    errors = _load(errors_path, "error-code contract")
    prims = {
        item.get("id"): item.get("canonical_name")
        for item in ledger.get("prim_identities", []) if isinstance(item, dict)
    }
    profiles = {
        item.get("id"): item for item in ledger.get("profiles", [])
        if isinstance(item, dict)
    }
    v2 = profiles.get("dialect-v2", {}).get("prim_ids", {})
    if prims.get(PRIM_ID) != SENTINEL or PRIM_ID not in v2.get("active", []):
        raise CompileErrorCaseError("Prim-ID 56 is not the active invalid-parameter sentinel")
    codes = {
        item.get("code"): item for item in errors.get("codes", [])
        if isinstance(item, dict)
    }
    code = codes.get(ERROR_CODE)
    if (
        not isinstance(code, dict)
        or code.get("id") != "lcc-invalid-parameter-list"
        or code.get("c_name") != "LISP65_ERR_LCC_INVALID_PARAMETER_LIST"
    ):
        raise CompileErrorCaseError("error code 59 contract drift")
    return [
        {"path": _relative(ledger_path), "sha256": _sha(ledger_path)},
        {"path": _relative(errors_path), "sha256": _sha(errors_path)},
    ]


def _compile_python_lcc(source: str) -> str:
    forms, names, _macros = Stdlib._source_top_defs(list(LCC_SOURCES))
    entry = "%invalid-parameter-list-probe"
    heap = P0C.prepare_heap(names + [entry])
    directory: dict[int, P0.CodeObject] = {}

    def add(name: str, code: P0.CodeObject) -> None:
        symbol = heap.intern(name)
        existing = directory.get(symbol)
        if existing is not None and existing.encode() != code.encode():
            raise CompileErrorCaseError(f"conflicting Python P0 code object: {name}")
        directory[symbol] = code

    for name in names:
        compiled, code, helpers = P0C.compile_top_form_with_helpers(
            forms[name], heap, strict_arity=True, abi_profile="dialect-v2",
        )
        add(compiled, code)
        for helper_name, helper in helpers:
            add(helper_name, helper)
    entry_form = ["defun", entry, [], P0C.parse_one(source)]
    compiled, code, helpers = P0C.compile_top_form_with_helpers(
        entry_form, heap, strict_arity=True, abi_profile="dialect-v2",
    )
    add(compiled, code)
    for helper_name, helper in helpers:
        add(helper_name, helper)
    vm = P0.P0VM(
        heap=heap,
        directory=directory,
        abi_profile="dialect-v2",
        abi_ledger=P0C._abi_ledger("dialect-v2", None),
    )
    try:
        vm.run(directory[heap.intern(entry)])
    except P0.VMError as exc:
        if (
            exc.status != "CompileError"
            or exc.error_code != ERROR_CODE
            or exc.error_symbol != SENTINEL
        ):
            raise CompileErrorCaseError(
                "Python P0 returned the wrong structured compile error: "
                f"status={exc.status} code={exc.error_code} symbol={exc.error_symbol}"
            ) from exc
        return f"!error:code={exc.error_code}:symbol={exc.error_symbol}"
    raise CompileErrorCaseError("Python P0 accepted the invalid parameter list")


def _profile_forms() -> dict[str, str]:
    profile_path = ROOT / LCC_SOURCES[1]
    if profile_path.is_symlink() or not profile_path.is_file():
        raise CompileErrorCaseError("focused LCC profile source is missing")
    profile = profile_path.read_text(encoding="utf-8")
    forms: dict[str, str] = {}
    for start, end in Codemod._top_level_forms(profile):
        form = profile[start:end]
        atoms = Codemod._form_atoms(form)
        if len(atoms) < 2 or atoms[0] != "defun":
            continue
        forms[atoms[1]] = form
    return forms


def _native_preload(directory: Path) -> Path:
    path = directory / "dialect-v2-lcc-error-preload.lisp"
    lcc_path = ROOT / LCC_SOURCES[0]
    if lcc_path.is_symlink() or not lcc_path.is_file():
        raise CompileErrorCaseError("focused base LCC source is missing")
    forms = _profile_forms()
    focused: list[str] = []
    included: set[str] = set()
    for name, form in forms.items():
        if name in PROFILE_EXCLUDED_FOR_FOCUSED_PRELOAD:
            continue
        focused.append(form)
        included.add(name)
    required = {
        "%lcc-compile-defun", "%lcc-compile-lambda", "%lcc-imm-binds",
        "%lcc-lambda", "%lcc-v2-param-error", "%lcc-v2-params",
    }
    if not required <= included:
        raise CompileErrorCaseError(
            f"focused LCC preload misses profile definitions: {sorted(required - included)}"
        )
    path.write_text(
        lcc_path.read_text(encoding="utf-8") + "\n" + "\n\n".join(focused) + "\n",
        encoding="utf-8",
    )
    return path


def _run_native(
    binary: Path, mode: str, source: str, preload: Path | None, directory: Path,
) -> str:
    forms = directory / f"invalid-parameter-{mode}.lisp"
    forms.write_text(source + "\n", encoding="utf-8")
    try:
        command = [str(binary), mode, str(forms)]
        if preload is not None:
            command.extend(("--preload", str(preload)))
        process = subprocess.run(
            command,
            cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CompileErrorCaseError(f"native {mode} harness failed: {exc}") from exc
    if process.returncode:
        raise CompileErrorCaseError(
            f"native {mode} harness exited {process.returncode}: {process.stderr.strip()}"
        )
    observations = [
        line.rsplit(" => ", 1)[1].strip()
        for line in process.stdout.splitlines() if " => " in line
    ]
    if len(observations) != 1:
        raise CompileErrorCaseError(
            f"native {mode} harness returned {len(observations)} observations"
        )
    return observations[0]


def run(
    fixture_path: Path, binary: Path, manifest_path: Path,
    inventory_path: Path, output: Path,
) -> None:
    fixture = validate_fixture(_load(fixture_path, "compile-error fixture"))
    bindings = _validate_static_contracts()
    if binary.is_symlink() or not binary.is_file():
        raise CompileErrorCaseError(f"missing candidate-v2 equivalence binary: {binary}")
    observations: dict[str, dict[str, Any]] = {}
    failed: list[str] = []
    manifest_bindings: list[dict[str, str]] = []
    carrier_cut_surface: list[str] = []
    with tempfile.TemporaryDirectory(prefix="lisp65-v2-lcc-error-") as raw:
        directory = Path(raw)
        preload = _native_preload(directory)
        for engine in ENGINES:
            expected = fixture["engines"][engine]["expected_observation"]
            if engine == "python-p0-compiler-vm":
                actual = _compile_python_lcc(fixture["source"])
            elif engine == "native-c-compiler-vm":
                actual, manifest_bindings, carrier_cut_surface = _run_manifest_vm(
                    manifest_path, inventory_path, fixture["source"], directory,
                )
            else:
                source = fixture["source"]
                engine_preload: Path | None = preload
                actual = _run_native(
                    binary, ENGINE_MODES[engine], source, engine_preload, directory,
                )
            accepted = actual == expected
            if not accepted:
                failed.append(engine)
            observations[engine] = {
                "coverage": ENGINE_COVERAGE[engine],
                "lcc_parameter_path": "lcc-compile-obj",
                "observation": actual,
                "expected": expected,
                "verdict": "pass" if accepted else "fail",
            }
            if engine == "native-c-compiler-vm":
                observations[engine]["carrier_cut_surface"] = carrier_cut_surface
            print(
                f"dialect-v2/{engine}/{fixture['id']}: "
                f"{'PASS' if accepted else 'FAIL'} observed={actual} expected={expected}"
            )
    bindings.extend(
        {"path": relative, "sha256": _sha(ROOT / relative)} for relative in LCC_SOURCES
    )
    bindings.extend(manifest_bindings)
    bindings.extend((
        {"path": _relative(fixture_path), "sha256": _sha(fixture_path)},
        {"path": _relative(binary), "sha256": _sha(binary)},
        {"path": "scripts/equivalence-main.c", "sha256": _sha(ROOT / "scripts/equivalence-main.c")},
    ))
    receipt = {
        "format": RECEIPT_FORMAT,
        "case": fixture["id"],
        "contract": fixture["expected"],
        "inputs": sorted(bindings, key=lambda item: item["path"]),
        "engines": observations,
        "full_invalid_parameter_path_engines": [
            *ENGINES,
        ],
        "native_carrier_cut_surface": carrier_cut_surface,
        "evidence_gap": None,
        "verdict": "pass" if not failed else "fail",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_canonical(receipt))
    if failed:
        raise CompileErrorCaseError(f"compile-error differential failed: {failed}")


def selftest(
    fixture_path: Path, manifest_path: Path, inventory_path: Path,
) -> None:
    original = validate_fixture(_load(fixture_path, "compile-error fixture"))
    _validate_static_contracts()
    artifact = _validate_resident_artifact(manifest_path)
    _validate_inventory_binding(inventory_path, artifact)
    actual = _compile_python_lcc(original["source"])
    expected = original["engines"]["python-p0-compiler-vm"]["expected_observation"]
    if actual != expected:
        raise CompileErrorCaseError(
            f"Python P0 live sentinel drift: observed={actual} expected={expected}"
        )
    with tempfile.TemporaryDirectory(prefix="lisp65-v2-lcc-error-selftest-") as raw:
        native, _bindings, surface = _run_manifest_vm(
            manifest_path, inventory_path, original["source"], Path(raw),
        )
    if native != EXPECTED_OBSERVATION or surface != [
        "surface:eval-direct=42",
        "surface:funcall-eval=42",
        "surface:apply-eval=42",
    ]:
        raise CompileErrorCaseError("native carrier-cut selftest observation drift")
    mutations = []
    bad_code = deepcopy(original)
    bad_code["expected"]["error_code"] = 58
    mutations.append(bad_code)
    bad_sentinel = deepcopy(original)
    bad_sentinel["engines"]["lisp-lcc"]["expected_observation"] = (
        "!error:code=28:symbol=%lcc-error-do-body-too-big"
    )
    mutations.append(bad_sentinel)
    missing_engine = deepcopy(original)
    del missing_engine["engines"]["native-c-compiler-vm"]
    mutations.append(missing_engine)
    for index, mutation in enumerate(mutations):
        try:
            validate_fixture(mutation)
        except CompileErrorCaseError:
            continue
        raise CompileErrorCaseError(f"selftest mutation {index} was accepted")
    inventory = _load(inventory_path, "staging service inventory")
    bad_manifest_sha = deepcopy(inventory)
    for item in bad_manifest_sha["artifacts"]:
        if item.get("id") == "resident":
            item["manifest_sha256"] = "0" * 64
    try:
        _validate_inventory_binding(
            inventory_path, artifact, inventory_override=bad_manifest_sha,
        )
    except CompileErrorCaseError:
        pass
    else:
        raise CompileErrorCaseError("wrong manifest SHA mutation was accepted")
    bad_blob = bytearray(artifact["blob"])
    bad_blob[len(bad_blob) // 2] ^= 1
    try:
        _validate_resident_artifact(
            manifest_path, manifest_override=artifact["manifest"],
            blob_override=bytes(bad_blob),
        )
    except CompileErrorCaseError:
        pass
    else:
        raise CompileErrorCaseError("wrong blob SHA mutation was accepted")
    print(
        "dialect-v2-lcc-compile-error: SELFTEST PASS "
        "mutations=5 code59-engines=python-p0+native-carrier-cut "
        "surface=eval+funcall+apply manifest-sha=fail-closed"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            selftest(args.fixture, args.manifest, args.inventory)
        else:
            run(
                args.fixture, args.binary, args.manifest, args.inventory, args.output,
            )
        return 0
    except CompileErrorCaseError as exc:
        print(f"dialect-v2-lcc-compile-error: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
