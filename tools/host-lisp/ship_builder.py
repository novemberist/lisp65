#!/usr/bin/env python3
"""Build and verify standalone lisp65 Ship-v1 D81 application images."""

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import asm_c_constant_contract as AsmContract  # noqa: E402
import bytecode_p0_compiler as Reader  # noqa: E402
import bytecode_p0_stdlib as Stdlib  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402
import l65p_v1 as L65P  # noqa: E402
import runtime_export_preload as Preload  # noqa: E402


CONTRACT = ROOT / "config" / "ship-builder-v1.json"
CATALOG = ROOT / "config" / "ship-library-catalog-v1.json"
CONTRACT_FORMAT = "lisp65-ship-builder-contract-v1"
CATALOG_FORMAT = "lisp65-ship-library-catalog-v1"
MANIFEST_FORMAT = "lisp65-ship-image-v1"
CLOSURE_FORMAT = "lisp65-ship-closure-v1"
RECEIPT_FORMAT = "lisp65-ship-build-receipt-v1"
REPRO_FORMAT = "lisp65-ship-reproducibility-v1"
DESCRIPTOR_VERSION = 3
DESCRIPTOR_HEADER_BYTES = 16
DESCRIPTOR_RECORD_BYTES = 32
DESCRIPTOR_RECORDS = 2
DESCRIPTOR_BYTES = 80
RESTAGE_LIMIT = 2
RUNTIME_LOAD_ADDRESS = 0x2001
RUNTIME_STAGE_ADDRESS = 0x00040000
PRELOAD_ADDRESS = 0x00050000
STAGE_FLAG = 0x01
PRG_FLAG = 0x02
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")

DYNAMIC_CALLS = {"apply", "funcall", "mapcar"}
SAMPLE_FLEET = (
    ("hello", "examples/ship/hello/project.l65p"),
    ("random-q", "examples/ship/random-q/project.l65p"),
    ("long-runner", "examples/ship/long-runner/project.l65p"),
    ("interactive", "examples/ship/interactive/project.l65p"),
    ("parity-toy", "examples/ship/parity-toy/project.l65p"),
)


class ShipError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ShipError(message)


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        require(key not in value, f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        require(path.is_file() and not path.is_symlink(), f"missing {label}: {path}")
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ShipError(f"cannot read {label}: {exc}") from exc
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def bind(path: Path, *, root: Path = ROOT) -> dict[str, Any]:
    data = path.read_bytes()
    try:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        relative = path.name
    return {"path": relative, "bytes": len(data), "sha256": sha_bytes(data)}


def run(argv: list[str], label: str, *, cwd: Path = ROOT) -> str:
    process = subprocess.run(
        argv, cwd=cwd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    if process.returncode:
        raise ShipError(f"{label} failed ({process.returncode}):\n{process.stdout}")
    return process.stdout


def validate_contract(contract: dict[str, Any], catalog: dict[str, Any], *, root: Path = ROOT) -> None:
    require(
        set(contract) == {
            "format", "version", "status", "surface", "authorities", "closure",
            "media", "runtime", "budgets", "redistribution", "gates",
        },
        "ship contract fields drift",
    )
    require(
        contract["format"] == CONTRACT_FORMAT and contract["version"] == 1
        and contract["status"] == "accepted-for-implementation",
        "ship contract identity drift",
    )
    require(contract["surface"] == {
        "form": "(ship string :entry quoted-symbol)",
        "project_format": "l65-project-v1",
        "entry_abi": "named-zero-argument-p0",
        "overwrite": "forbidden",
    }, "ship surface drift")
    authorities = contract["authorities"]
    require(isinstance(authorities, dict) and authorities, "empty ship authorities")
    for label, raw in authorities.items():
        path = root / str(raw)
        require(path.is_file() and not path.is_symlink(), f"missing ship authority: {label}")
    media = contract["media"]
    require(
        media["label"] == "L65APP" and media["disk_id"] == "65"
        and media["bytes"] == 819200 and media["descriptor_version"] == 3
        and media["runtime_entry"] == "linked-elf-_start"
        and len(media["files"]) == len(set(media["files"])) == 9,
        "ship media contract drift",
    )
    require(contract["runtime"]["preload_bank"] == 5, "ship preload bank drift")
    require(contract["runtime"]["base_library"] == "core", "ship base library drift")
    require(contract["budgets"]["max_preload_bytes"] == 65536, "ship preload budget drift")
    require(contract["redistribution"]["runtime_license"] == "MPL-2.0", "ship license drift")
    contracted_samples = contract["gates"]["samples"]
    fleet_names = [name for name, _project in SAMPLE_FLEET]
    require(
        contracted_samples == fleet_names
        and len(contracted_samples) == len(set(contracted_samples)),
        "ship contracted sample fleet does not match the executed fleet",
    )
    require(
        set(catalog) == {"format", "version", "libraries"}
        and catalog["format"] == CATALOG_FORMAT and catalog["version"] == 1,
        "ship library catalog identity drift",
    )
    names: set[str] = set()
    for index, row in enumerate(catalog["libraries"]):
        require(
            isinstance(row, dict)
            and set(row) == {"name", "requires", "suite", "sources", "exports"},
            f"ship library row {index} fields drift",
        )
        name = row["name"]
        require(isinstance(name, str) and name and name == name.lower() and name not in names,
                "invalid/duplicate ship library name")
        names.add(name)
        require((root / row["suite"]).is_file(), f"missing ship library suite: {name}")
        require(
            isinstance(row["sources"], list) and row["sources"]
            and len(row["sources"]) == len(set(row["sources"]))
            and all((root / source).is_file() for source in row["sources"]),
            f"missing/invalid ship library sources: {name}",
        )
        require(isinstance(row["requires"], list) and len(row["requires"]) == len(set(row["requires"])),
                f"invalid ship library dependencies: {name}")
        require(isinstance(row["exports"], list) and row["exports"],
                f"empty ship library exports: {name}")
    require(all(dep in names for row in catalog["libraries"] for dep in row["requires"]),
            "unknown ship library dependency")


def parse_ship_form(source: str) -> tuple[str, str]:
    try:
        form = Reader.parse_one(source)
    except Reader.CompileError as exc:
        raise ShipError("malformed-ship-form") from exc
    require(isinstance(form, list) and len(form) == 4 and form[0] == "ship",
            "malformed-ship-form")
    require(isinstance(form[1], Reader.StringLit) and form[1].value,
            "ship-name-type")
    require(form[2] == ":entry", "ship-entry-keyword")
    quoted = form[3]
    require(
        isinstance(quoted, list) and len(quoted) == 2 and quoted[0] == "quote"
        and isinstance(quoted[1], str) and quoted[1],
        "ship-entry-designator",
    )
    return form[1].value, quoted[1]


def read_project(project_path: Path, ship_name: str) -> tuple[L65P.Project, bytes]:
    require(project_path.is_file() and not project_path.is_symlink(), "project-manifest-missing")
    source = project_path.read_text(encoding="utf-8")
    try:
        project = L65P.parse_project(source)
    except L65P.L65PError as exc:
        raise ShipError(f"project-manifest:{exc}") from exc
    require(project.name == ship_name, "ship-project-name-mismatch")
    for raw in project.sources:
        path = project_path.parent / raw
        require(path.is_file() and not path.is_symlink(), f"project-source-missing:{raw}")
    return project, source.encode("utf-8")


def catalog_index(catalog: dict[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    rows = []
    for source in catalog["libraries"]:
        artifact = root / source["suite"]
        source_bindings = [bind(root / raw, root=root) for raw in source["sources"]]
        identity_material = {
            "format": "lisp65-ship-library-v1",
            "name": source["name"],
            "sources": source_bindings,
            "suite_sha256": sha(root / source["suite"]),
            "requires": source["requires"],
            "exports": source["exports"],
        }
        identity_sha = sha_bytes(json.dumps(
            identity_material, sort_keys=True, separators=(",", ":")
        ).encode("ascii"))
        rows.append({
            "name": source["name"],
            "identity_u32": int.from_bytes(bytes.fromhex(identity_sha[:8]), "little"),
            "identity_sha256": identity_sha,
            "artifact": source["suite"],
            "artifact_bytes": artifact.stat().st_size,
            "artifact_crc32": zlib.crc32(artifact.read_bytes()) & 0xFFFFFFFF,
            "artifact_sha256": sha(artifact),
            "requires": source["requires"],
            "exports": source["exports"],
            "c2_delta": {key: 0 for key in L65P.DELTA_KEYS},
            "execution_source": "bank2",
        })
    rows.sort(key=lambda row: row["name"])
    value = {"format": L65P.INDEX_FORMAT, "libraries": rows}
    value["index_sha256"] = sha_bytes(json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode("ascii"))
    return value


def top_definitions(paths: list[Path]) -> tuple[dict[str, list[Any]], dict[str, Path]]:
    forms: dict[str, list[Any]] = {}
    owners: dict[str, Path] = {}
    for path in paths:
        try:
            parsed = Reader.parse_all(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, Reader.CompileError) as exc:
            raise ShipError(f"cannot parse source {path}: {exc}") from exc
        for form in parsed:
            if (
                isinstance(form, list) and len(form) >= 4
                and form[0] in ("defun", "defmacro") and isinstance(form[1], str)
            ):
                name = form[1]
                require(name not in forms, f"duplicate-definition:{name}")
                forms[name] = form
                owners[name] = path
    return forms, owners


def expr_edges(expr: Any, definitions: set[str], *, quoted: bool = False) -> tuple[set[str], list[str]]:
    edges: set[str] = set()
    dynamic: list[str] = []
    if not isinstance(expr, list) or not expr or quoted:
        return edges, dynamic
    head = expr[0]
    if head == "quote":
        return edges, dynamic
    if head == "function":
        if len(expr) == 2 and isinstance(expr[1], str) and expr[1] in definitions:
            edges.add(expr[1])
        elif len(expr) != 2 or not isinstance(expr[1], str):
            dynamic.append("function")
        return edges, dynamic
    if isinstance(head, str):
        if head in definitions:
            edges.add(head)
        if head in DYNAMIC_CALLS:
            if len(expr) < 2:
                dynamic.append(head)
            else:
                target = expr[1]
                if isinstance(target, list) and len(target) == 2 and target[0] in ("quote", "function") and isinstance(target[1], str):
                    if target[1] in definitions:
                        edges.add(target[1])
                else:
                    dynamic.append(head)
    for item in expr[1:] if isinstance(head, str) else expr:
        child_edges, child_dynamic = expr_edges(item, definitions)
        edges.update(child_edges)
        dynamic.extend(child_dynamic)
    return edges, dynamic


def closure_for(
    project: L65P.Project, project_path: Path, entry: str,
    catalog: dict[str, Any], lock: dict[str, Any], *, root: Path = ROOT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    project_sources = [project_path.parent / raw for raw in project.sources]
    project_top, project_owners = top_definitions(project_sources)
    project_forms = {
        name: form for name, form in project_top.items() if form[0] == "defun"
    }
    require(entry in project_forms and project_forms[entry][0] == "defun", "unresolved-entry")
    params = project_forms[entry][2]
    require(isinstance(params, list) and not params, "entry-must-have-zero-arity")

    by_name = {row["name"]: row for row in catalog["libraries"]}
    ordered_libraries = [row["name"] for row in lock["libraries"]]
    library_paths = [
        root / source
        for name in ordered_libraries
        for source in by_name[name]["sources"]
    ]
    library_top, library_owners = top_definitions(library_paths)
    library_forms = {
        name: form for name, form in library_top.items() if form[0] == "defun"
    }
    overlap = set(project_forms) & set(library_forms)
    require(not overlap, "project-library-definition-collision:" + ",".join(sorted(overlap)))
    all_forms = {**project_forms, **library_forms}
    owners = {**project_owners, **library_owners}
    definitions = set(all_forms)

    graph: dict[str, list[str]] = {}
    dynamic: dict[str, list[str]] = {}
    for name, form in all_forms.items():
        edges: set[str] = set()
        unresolved: list[str] = []
        for body in form[3:]:
            found, dyn = expr_edges(body, definitions)
            edges.update(found)
            unresolved.extend(dyn)
        graph[name] = sorted(edges)
        if unresolved:
            dynamic[name] = sorted(set(unresolved))

    reachable = set(project_forms)
    work = list(project_forms)
    while work:
        current = work.pop()
        for target in graph[current]:
            if target not in reachable:
                reachable.add(target)
                work.append(target)
    bad_dynamic = {name: dynamic[name] for name in sorted(reachable & set(dynamic))}
    require(not bad_dynamic, "unresolved-dynamic-call:" + json.dumps(bad_dynamic, sort_keys=True))

    shipped_library = sorted(reachable & set(library_forms))
    functions = list(project_forms) + [
        name for name in library_forms if name in shipped_library
    ]
    declared_private_inline: list[str] = []
    for library_name in ordered_libraries:
        library_suite = load_json(
            root / by_name[library_name]["suite"],
            f"ship library suite {library_name}",
        )
        for name in library_suite.get("private_inline_functions", []):
            require(
                name not in declared_private_inline,
                f"duplicate-private-inline:{name}",
            )
            declared_private_inline.append(name)
    private_inline = [name for name in declared_private_inline if name in functions]
    suite = {
        "format": Stdlib.SUITE_FORMAT_DISK_LIB,
        "name": f"ship-{project.name}",
        "d81_name": "APP.L65M",
        "provides": [project.name],
        "requires": ordered_libraries,
        "description": "Generated by the Ship-v1 closure builder.",
        "strict_arity": True,
        "abi_profile": "dialect-v2",
        "sources": [str(path.resolve()) for path in project_sources + library_paths],
        "functions": functions,
        "max_code_object_bytes": 255,
        "max_call_args": 12,
        "private_inline_functions": private_inline,
        # Every symbolic callee in shipped code is supplied by the computed
        # project/library closure; no unresolved error edge is admissible.
        "allowed_external_calls": [],
        # The canonical emitter requires an executable oracle case even when
        # cases are excluded from the emitted artifact.  Entry execution is
        # proved separately by ship-runtime-host-main.c below.
        "cases": [{"name": "ship-compiler-smoke", "expr": "1", "expect": "1"}],
    }
    closure = {
        "format": CLOSURE_FORMAT,
        "project": project.name,
        "entry": entry,
        "project_functions": list(project_forms),
        "eligible_libraries": ordered_libraries,
        "eligible_library_functions": list(library_forms),
        "shipped_library_functions": shipped_library,
        "omitted_library_functions": sorted(set(library_forms) - set(shipped_library)),
        "functions": functions,
        "private_inline_functions": private_inline,
        "edges": [
            {"caller": name, "callees": graph[name]}
            for name in functions
        ],
        "dynamic_edges_rejected": 0,
        "definition_sources": {
            name: owners[name].name for name in functions
        },
    }
    return suite, closure


def prepare(form: str, project_path: Path, out: Path, *, root: Path = ROOT) -> dict[str, Any]:
    contract = load_json(root / CONTRACT.relative_to(ROOT), "ship contract")
    catalog = load_json(root / CATALOG.relative_to(ROOT), "ship catalog")
    validate_contract(contract, catalog, root=root)
    name, entry = parse_ship_form(form)
    project, project_bytes = read_project(project_path, name)
    index = catalog_index(catalog, root=root)
    base_library = contract["runtime"]["base_library"]
    resolution_project = L65P.Project(
        project.name,
        tuple(dict.fromkeys((base_library,) + project.requires)),
        project.sources,
        project.default_target,
    )
    try:
        lock = L65P.resolve(resolution_project, index, 1)
    except L65P.L65PError as exc:
        raise ShipError(f"dependency-resolution:{exc}") from exc
    suite, closure = closure_for(project, project_path, entry, catalog, lock, root=root)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "suite.json", suite)
    write_json(out / "closure.json", closure)
    write_json(out / "ship.lock", lock)
    (out / "project.l65p").write_bytes(project_bytes)
    value = {
        "name": name,
        "entry": entry,
        "project": asdict(project),
        "suite": bind(out / "suite.json", root=out),
        "closure": bind(out / "closure.json", root=out),
        "lock": bind(out / "ship.lock", root=out),
        "project_manifest": bind(out / "project.l65p", root=out),
    }
    write_json(out / "prepare.json", value)
    return value


def compiler_path(root: Path, override: Path | None = None) -> Path:
    path = override or root / "tools" / "llvm-mos" / "bin" / "mos-mega65-clang"
    require(path.is_file(), f"missing llvm-mos compiler: {path}")
    # The platform is selected from argv[0]; resolving the mos-mega65-clang
    # symlink to mos-clang silently drops the MEGA65 include/library profile.
    return path.absolute()


def build_artifact(build_dir: Path, root: Path) -> tuple[Path, dict[str, Any]]:
    # vm_embed.c intentionally has one generated-header authority.  Preserve
    # that basename instead of teaching the Runtime Core a Ship-only alias.
    prefix = build_dir / "stdlib-p0"
    output = run([
        sys.executable, str(root / "tools/host-lisp/bytecode_p0_stdlib.py"),
        "--emit-artifacts", str(prefix), "--base-addr", "0x050000",
        str(build_dir / "suite.json"),
    ], "ship bytecode emission", cwd=root)
    manifest = load_json(Path(str(prefix) + ".manifest.json"), "ship artifact manifest")
    require(manifest["abi_profile"] == "dialect-v2", "ship artifact ABI drift")
    require(manifest["objects"] == len(manifest["functions"]), "ship artifact object count drift")
    (build_dir / "artifact-emission.txt").write_text(output, encoding="utf-8")
    return prefix, manifest


def host_smoke(build_dir: Path, prefix: Path, entry: str, root: Path) -> dict[str, Any]:
    binary = build_dir / "ship-runtime-host"
    defines = [
        "-DLISP65_VM", "-DLISP65_VM_DIAGNOSTICS", "-DLISP65_EMBED_STDLIB", "-DLISP65_BYTECODE_STDLIB_EMIT_METADATA",
        "-DLISP65_RUNTIME_CORE", "-DVM_CODEBUF=56", "-DGC_ROOTS=128",
        "-DLISP65_MARK_BITMAP", "-DLISP65_EXT_HEAP", "-DEXT_CELLS=1024",
        "-DLISP65_STRING_ARENA", "-DSTR_ARENA_SIZE=0x2480",
        "-DLISP65_VM_GLOBAL_PRIMS", "-DLISP65_VM_NATIVE_APPLY",
        "-DNAMEPOOL=9536", "-DMAX_SYM=720", "-DVM_DIR_MAX=552",
        "-DLISP65_DIALECT_V2", "-DLISP65_V2_NATIVE_CAPABILITIES",
        "-DLISP65_V2_NATIVE_STRING_CODECS", "-DLISP65_TREEWALK_STRIP",
        "-DLISP65_V2_SERVICE_REGISTRY_CLOSED", "-DLISP65_V2_CARRIER_CUT",
        "-DLISP65_SCREEN_DRIVER", "-DLISP65_VM_SCREEN_PRIMS",
        "-DLISP65_SHIP_RUNTIME_IO", "-DLISP65_CODE_WINDOW_CONVERGENCE",
        "-DLISP65_DMA_CONTENT_CONVERGENCE",
        f'-DLISP65_SHIP_ENTRY="{entry}"',
    ]
    run([
        os.environ.get("HOSTCC", "cc"), "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-Wno-unused-function", "-Wno-type-limits", "-fsanitize=address,undefined",
        "-fno-omit-frame-pointer",
        *defines, "-Isrc", f"-I{prefix.parent}",
        "scripts/ship-runtime-host-main.c", "src/interrupt.c", "src/mem.c",
        "src/symbol.c", "src/vm.c", "src/vm_embed.c", "src/screen.c",
        "products/runtime-core/ship_io.c", str(prefix) + ".c",
        "-o", str(binary),
    ], "ship native host link", cwd=root)
    env = dict(os.environ)
    env.update({"ASAN_OPTIONS": "detect_leaks=0:halt_on_error=1", "UBSAN_OPTIONS": "halt_on_error=1"})
    process = subprocess.run([str(binary)], cwd=root, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(process.returncode == 0 and process.stdout.startswith("ship-runtime-host: PASS"),
            "ship native host execution failed:\n" + process.stdout)
    (build_dir / "host-smoke.txt").write_text(process.stdout, encoding="utf-8")
    return {"status": "passed", "output": process.stdout.strip()}


def runtime_compile(
    build_dir: Path, prefix: Path, entry: str, build_id: int,
    *, root: Path, cc_override: Path | None,
) -> tuple[Path, Path, dict[str, Any]]:
    payload = Path(str(prefix) + ".ext.bin")
    preload = build_dir / "runtime.bin"
    preload_header = build_dir / "runtime-preload-contract.h"
    preload.write_bytes(Preload.bind(payload.read_bytes(), build_id))
    preload_header.write_bytes(Preload.header(payload.read_bytes(), build_id))
    cc = compiler_path(root, cc_override)
    runtime = build_dir / "runtime.prg"
    defines = [
        "-DLISP65_VM", "-DLISP65_EMBED_STDLIB", "-DLISP65_EMBED_DMA",
        "-DHEAP_CELLS=48", "-DLISP65_RUNTIME_CORE", "-DVM_CODEBUF=56",
        "-DLISP65_SYMPOOL_EXT", "-DLISP65_SYMVAL_EXT", "-DLISP65_NAMEOFF_EXT",
        "-DLISP65_SYMFN_EXT", "-DGC_ROOTS=128", "-DLISP65_STDLIB_EXT_METADATA",
        "-DLISP65_STDLIB_EXTERNAL_BLOB", "-DLISP65_MARK_BITMAP", "-DLISP65_EXT_HEAP",
        "-DEXT_CELLS=1024", "-DLISP65_NURSERY_HYSTERESIS=192",
        "-DLISP65_STRING_ARENA", "-DSTR_ARENA_SIZE=0x2480",
        "-DDISK_EXT_BASE=0x6900", "-DDISK_EXT_FILE_MAX=0x9600",
        "-DLISP65_VM_GLOBAL_PRIMS", "-DLISP65_VM_NATIVE_APPLY",
        "-DSYMPOOL_EXT_OFF=0xc9e0", "-DNAMEPOOL=9536", "-DMAX_SYM=720",
        "-DVM_DIR_MAX=552", "-DLISP65_DIALECT_V2", "-DLISP65_V2_NATIVE_CAPABILITIES",
        "-DLISP65_V2_NATIVE_STRING_CODECS", "-DLISP65_TREEWALK_STRIP",
        "-DLISP65_V2_SERVICE_REGISTRY_CLOSED", "-DLISP65_V2_CARRIER_CUT",
        "-DLISP65_STDLIB_BOOT_OVERLAY_CODE", "-DLISP65_SHIP_RUNTIME",
        "-DLISP65_SCREEN_DRIVER", "-DLISP65_VM_SCREEN_PRIMS",
        "-DLISP65_SHIP_RUNTIME_IO", "-DLISP65_CODE_WINDOW_CONVERGENCE",
        "-DLISP65_DMA_CONTENT_CONVERGENCE",
        f'-DLISP65_RUNTIME_ENTRY="{entry}"',
    ]
    sources = [
        "src/interrupt.c", "src/mem.c", "src/symbol.c", "src/vm.c", "src/vm_embed.c",
        "src/screen.c",
        "products/runtime-core/ship_io.c",
        "products/runtime-core/ship_timebase.s",
        "products/runtime-core/preload_integrity.c", "products/runtime-core/main.c",
        str(prefix) + ".c",
    ]
    output = run([
        str(cc), "-Oz", "-Wall", f"-ffile-prefix-map={root}=.", *defines,
        "-include", str(preload_header), "-Isrc", "-Iproducts/runtime-core",
        f"-I{prefix.parent}", *sources,
        "-Wl,--icf=all", "-Wl,-T,scripts/lisp65-mega65-runtime-core-inline-overlay.ld",
        "-Wl,--defsym=__lisp65_runtime_core_inline_required_boot_stack_param=512",
        "-Wl,--defsym=__lisp65_runtime_core_inline_required_runtime_stack_param=8192",
        "-Wl,--defsym=__lisp65_runtime_core_inline_required_post_boot_reserve_param=8192",
        "-Wl,--defsym=__lisp65_runtime_core_inline_max_file_end_param=45056",
        "-o", str(runtime),
    ], "ship Runtime Core link", cwd=root)
    elf = Path(str(runtime) + ".elf")
    require(runtime.is_file() and elf.is_file(), "ship Runtime Core output missing")
    truth = ElfTruth.read(elf, llvm_readobj=cc.parent / "llvm-readobj")
    forbidden = load_json(root / "config/ship-builder-v1.json", "ship contract")["runtime"]["forbidden_symbols"]
    present = {
        symbol.name for symbol in truth.symbols if symbol.section != "Undefined"
    }
    escaped = sorted(set(forbidden) & present)
    require(not escaped, "forbidden Runtime symbols: " + ",".join(escaped))
    start = truth.symbol("_start")
    require(start.section not in ("Absolute", "Undefined"), "Runtime CRT entry is not linked")
    crt_entry = start.value
    require(RUNTIME_LOAD_ADDRESS <= crt_entry <= 0xFFFF, "Runtime CRT entry is outside Bank 0")
    (build_dir / "runtime-link.txt").write_text(output, encoding="utf-8")
    return runtime, elf, {
        "entry_address": f"0x{crt_entry:04x}",
        "forbidden_symbols_present": escaped,
        "defined_symbols": len(present),
        "prg_bytes": runtime.stat().st_size,
        "elf_sha256": sha(elf),
    }


def descriptor_rows(runtime: Path, preload: Path) -> list[dict[str, Any]]:
    return [
        {"role": 1, "flags": STAGE_FLAG, "name": "runtime.bin", "destination": PRELOAD_ADDRESS,
         "bytes": preload.stat().st_size, "crc32": zlib.crc32(preload.read_bytes()) & 0xFFFFFFFF},
        {"role": 2, "flags": PRG_FLAG, "name": "runtime.prg", "destination": RUNTIME_STAGE_ADDRESS,
         "bytes": runtime.stat().st_size, "crc32": zlib.crc32(runtime.read_bytes()) & 0xFFFFFFFF},
    ]


def make_descriptor(rows: list[dict[str, Any]], profile_id: int) -> tuple[bytes, int]:
    require(len(rows) == DESCRIPTOR_RECORDS, "ship descriptor row count drift")
    records = bytearray()
    for expected_role, row in enumerate(rows, 1):
        name = row["name"].encode("ascii")
        require(row["role"] == expected_role and 1 <= len(name) <= 16 and row["bytes"] > 0,
                "invalid ship descriptor row")
        record = bytearray(DESCRIPTOR_RECORD_BYTES)
        record[0:3] = bytes((row["role"], row["flags"], len(name)))
        struct.pack_into("<III", record, 4, row["destination"], row["bytes"], row["crc32"])
        record[16:16 + len(name)] = name
        records.extend(record)
    build_id = zlib.crc32(records) & 0xFFFFFFFF
    header = bytearray(DESCRIPTOR_HEADER_BYTES)
    header[:4] = b"L65B"
    header[4:8] = bytes((DESCRIPTOR_VERSION, DESCRIPTOR_HEADER_BYTES, DESCRIPTOR_RECORDS, RESTAGE_LIMIT))
    struct.pack_into("<II", header, 8, build_id, profile_id)
    result = bytes(header + records)
    require(len(result) == DESCRIPTOR_BYTES and zlib.crc32(result[16:]) & 0xFFFFFFFF == build_id,
            "ship descriptor envelope drift")
    return result, build_id


def parse_descriptor(data: bytes) -> tuple[int, int, list[dict[str, Any]]]:
    require(
        len(data) == DESCRIPTOR_BYTES and data[:4] == b"L65B"
        and tuple(data[4:8]) == (DESCRIPTOR_VERSION, 16, 2, RESTAGE_LIMIT),
        "ship descriptor header drift",
    )
    build_id, profile_id = struct.unpack_from("<II", data, 8)
    require(zlib.crc32(data[16:]) & 0xFFFFFFFF == build_id, "ship descriptor build-id drift")
    rows = []
    for index in range(2):
        record = data[16 + index * 32:48 + index * 32]
        role, flags, name_len, reserved = record[:4]
        destination, length, checksum = struct.unpack_from("<III", record, 4)
        require(role == index + 1 and reserved == 0 and 1 <= name_len <= 16 and length > 0,
                "ship descriptor record drift")
        rows.append({
            "role": role, "flags": flags,
            "name": record[16:16 + name_len].decode("ascii"),
            "destination": destination, "bytes": length, "crc32": checksum,
        })
    require(rows[0]["flags"] == STAGE_FLAG and rows[0]["destination"] == PRELOAD_ADDRESS,
            "ship preload descriptor drift")
    require(rows[1]["flags"] == PRG_FLAG and rows[1]["destination"] == RUNTIME_STAGE_ADDRESS,
            "ship Runtime descriptor drift")
    return build_id, profile_id, rows


def compile_stager(
    build_dir: Path, build_id: int, crt_entry: int, *,
    root: Path, cc_override: Path | None,
) -> tuple[Path, dict[str, Any]]:
    cc = compiler_path(root, cc_override)
    generated = root / "build/generated/c2-lite-asm-c-contract.inc"
    generated.parent.mkdir(parents=True, exist_ok=True)
    include = AsmContract.compile_output(
        AsmContract.load_contract(root / "config/asm-c-constant-contract.json"),
        str(os.environ.get("HOSTCC", "cc")),
        ("-DLISP65_SHIP_MEDIA_STAGER", f"-DR3_PRODUCT_ENTRY=0x{crt_entry:04x}u"),
    )
    symbols = AsmContract.parse_equ(include)
    require(symbols["ASM_R3_PRODUCT_ENTRY"] == crt_entry,
            "ship stager entry contract drift")
    generated.write_bytes(include)
    c_obj = build_dir / "autoboot-main.o"
    s_obj = build_dir / "autoboot-chain.o"
    stager = build_dir / "autoboot.c65"
    run([
        str(cc), "-std=c99", "-Oz", "-Wall", "-Wextra", "-Werror",
        "-DLISP65_SHIP_MEDIA_STAGER", f"-DR3_PRODUCT_ENTRY=0x{crt_entry:04x}u",
        f"-DR3_EXPECTED_PRODUCT_BUILD_ID=0x{build_id:08x}UL",
        "-c", "scripts/r3-cold-stager-main.c", "-o", str(c_obj),
    ], "ship cold-stager C build", cwd=root)
    run([
        str(cc), "-Qunused-arguments", "-c", "scripts/c2-lite-cold-stager-chain.s",
        "-o", str(s_obj),
    ], "ship cold-stager chain build", cwd=root)
    run([
        "/usr/bin/setarch", os.uname().machine, "-R", str(cc), "-Oz",
        str(c_obj), str(s_obj), "-o", str(stager),
    ], "ship cold-stager link", cwd=root)
    require(stager.is_file() and Path(str(stager) + ".elf").is_file(), "ship stager output missing")
    return stager, {
        "bytes": stager.stat().st_size,
        "sha256": sha(stager),
        "descriptor_build_id": f"{build_id:08x}",
        "entry": f"0x{symbols['ASM_R3_PRODUCT_ENTRY']:04x}",
        "transport": "normal-f018b-d700-manifest-crc-content-convergence",
    }


def license_notice(root: Path) -> bytes:
    return (
        "lisp65 Runtime Core\n\n"
        "The Runtime Core in this disk image is executable Covered Software "
        "under the Mozilla Public License 2.0. The corresponding source is "
        "available at https://github.com/MEGA65/lisp65. The user program and "
        "its data are separate files and are not relicensed by this notice.\n\n"
    ).encode("ascii") + (root / "LICENSE").read_bytes()


def c1541_build(image: Path, entries: list[tuple[Path, str]]) -> str:
    c1541 = shutil.which("c1541")
    require(c1541 is not None, "c1541-unavailable")
    argv = [c1541, "-format", "L65APP,65", "d81", str(image)]
    for path, name in entries:
        argv += ["-write", str(path), name]
    return run(argv, "ship D81 construction")


def c1541_extract(image: Path, name: str, out: Path) -> None:
    c1541 = shutil.which("c1541")
    require(c1541 is not None, "c1541-unavailable")
    if out.exists():
        out.unlink()
    run([c1541, "-attach", str(image), "-read", name, str(out)], f"extract {name}")
    require(out.is_file(), f"D81 member missing: {name}")


def media_identity(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    require(len(data) == 819200, "ship D81 size drift")
    # 1581 header is logical sector 40/0, stored at track 40 offset.  The
    # existing F011 stager validates the same bytes at offsets 4 and 22.
    sector = ((40 - 1) * 40) * 256
    header = data[sector:sector + 256]
    fold = lambda chunk: bytes(byte - 128 if byte > 127 else byte for byte in chunk)
    label = fold(header[4:20]).decode("ascii").rstrip(" ")
    disk_id = fold(header[22:24]).decode("ascii")
    return label, disk_id


def verify_image(image: Path, *, contract_path: Path = CONTRACT) -> dict[str, Any]:
    contract = load_json(contract_path, "ship contract")
    require(image.is_file() and not image.is_symlink(), "ship image missing")
    require(image.stat().st_size == contract["media"]["bytes"], "ship D81 byte count drift")
    label, disk_id = media_identity(image)
    require(label == "L65APP" and disk_id == "65", f"ship D81 identity drift:{label},{disk_id}")
    with tempfile.TemporaryDirectory(prefix="lisp65-ship-verify-") as raw:
        temp = Path(raw)
        extracted: dict[str, Path] = {}
        for name in contract["media"]["files"]:
            path = temp / name.lower()
            c1541_extract(image, name.lower(), path)
            extracted[name] = path
        manifest = load_json(extracted["SHIP.JSON"], "embedded ship manifest")
        require(manifest["format"] == MANIFEST_FORMAT and manifest["status"] == "verified-at-pack",
                "embedded ship manifest identity drift")
        require(isinstance(manifest["image_name"], str) and manifest["image_name"],
                "ship image name is absent")
        require(set(manifest["files"]) == set(contract["media"]["files"]) - {"SHIP.JSON"},
                "ship manifest file inventory drift")
        for name, row in manifest["files"].items():
            require(set(row) == {"bytes", "sha256"}, f"ship file row drift:{name}")
            path = extracted[name]
            require(path.stat().st_size == row["bytes"] and sha(path) == row["sha256"],
                    f"ship member identity drift:{name}")
        build_id, profile_id, rows = parse_descriptor(extracted["BOOT.ID"].read_bytes())
        by_name = {row["name"].upper(): row for row in rows}
        for name in ("RUNTIME.BIN", "RUNTIME.PRG"):
            row = by_name[name]
            payload = extracted[name].read_bytes()
            require(len(payload) == row["bytes"] and zlib.crc32(payload) & 0xFFFFFFFF == row["crc32"],
                    f"descriptor member mismatch:{name}")
        payload, preload_id = Preload.parse(extracted["RUNTIME.BIN"].read_bytes())
        require(payload == extracted["APP.L65M"].read_bytes() and preload_id == manifest["build_id_u32"],
                "Runtime preload/app identity drift")
        require(build_id == manifest["descriptor_build_id_u32"] and profile_id == manifest["profile_id_u32"],
                "ship descriptor manifest identity drift")
        lock = load_json(extracted["SHIP.LOCK"], "embedded ship lock")
        require(lock["lock_sha256"] == manifest["resolution_lock_sha256"], "ship lock manifest drift")
        require(extracted["PROJECT.L65P"].read_bytes() == bytes.fromhex(manifest["project_manifest_hex"]),
                "ship project manifest drift")
        require(b"Mozilla Public License Version 2.0" in extracted["LICENSE.TXT"].read_bytes(),
                "ship license text missing")
    return {
        "status": "passed",
        "image_sha256": sha(image),
        "image_bytes": image.stat().st_size,
        "members_verified": 9,
        "descriptor_build_id": f"{build_id:08x}",
        "profile_id": f"{profile_id:08x}",
    }


def build(
    form: str, project_path: Path, output: Path, *, root: Path = ROOT,
    cc_override: Path | None = None,
) -> dict[str, Any]:
    sidecars = (
        output.with_suffix(".receipt.json"),
        output.with_suffix(".runtime.elf"),
        output.with_suffix(".stager.elf"),
        output.with_suffix(".closure.json"),
    )
    require(
        not output.exists() and not output.is_symlink()
        and all(not path.exists() and not path.is_symlink() for path in sidecars),
        "ship-output-exists",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lisp65-ship-build-", dir=output.parent) as raw:
        build_dir = Path(raw)
        prepared = prepare(form, project_path, build_dir, root=root)
        require(output.name == prepared["name"] + ".d81", "ship-output-name-mismatch")
        prefix, artifact_manifest = build_artifact(build_dir, root)
        host = host_smoke(build_dir, prefix, prepared["entry"], root)
        identity_material = {
            "contract": sha(root / "config/ship-builder-v1.json"),
            "catalog": sha(root / "config/ship-library-catalog-v1.json"),
            "project": sha(build_dir / "project.l65p"),
            "lock": sha(build_dir / "ship.lock"),
            "closure": sha(build_dir / "closure.json"),
            "artifact": sha(Path(str(prefix) + ".ext.bin")),
            "entry": prepared["entry"],
        }
        identity_sha = sha_bytes(json.dumps(identity_material, sort_keys=True).encode("ascii"))
        build_id = int(identity_sha[:8], 16)
        runtime, elf, runtime_audit = runtime_compile(
            build_dir, prefix, prepared["entry"], build_id,
            root=root, cc_override=cc_override,
        )
        rows = descriptor_rows(runtime, build_dir / "runtime.bin")
        profile_id = int(identity_sha[8:16], 16)
        descriptor, descriptor_id = make_descriptor(rows, profile_id)
        (build_dir / "boot.id").write_bytes(descriptor)
        stager, stager_audit = compile_stager(
            build_dir, descriptor_id, int(runtime_audit["entry_address"], 16),
            root=root, cc_override=cc_override,
        )
        shutil.copyfile(Path(str(prefix) + ".ext.bin"), build_dir / "app.l65m")
        (build_dir / "license.txt").write_bytes(license_notice(root))
        closure = load_json(build_dir / "closure.json", "ship closure")
        lock = load_json(build_dir / "ship.lock", "ship lock")
        file_paths = {
            "AUTOBOOT.C65": stager,
            "BOOT.ID": build_dir / "boot.id",
            "RUNTIME.PRG": runtime,
            "RUNTIME.BIN": build_dir / "runtime.bin",
            "APP.L65M": build_dir / "app.l65m",
            "PROJECT.L65P": build_dir / "project.l65p",
            "SHIP.LOCK": build_dir / "ship.lock",
            "LICENSE.TXT": build_dir / "license.txt",
        }
        source_commit = run(["git", "rev-parse", "HEAD"], "resolve source commit", cwd=root).strip()
        require(COMMIT_RE.fullmatch(source_commit) is not None, "invalid source commit")
        manifest = {
            "format": MANIFEST_FORMAT,
            "version": 1,
            "status": "verified-at-pack",
            "image_name": prepared["name"],
            "entry": prepared["entry"],
            "source_commit": source_commit,
            "build_identity_sha256": identity_sha,
            "build_id_u32": build_id,
            "descriptor_build_id_u32": descriptor_id,
            "profile_id_u32": profile_id,
            "resolution_lock_sha256": lock["lock_sha256"],
            "project_manifest_hex": (build_dir / "project.l65p").read_bytes().hex(),
            "closure": {
                "project_functions": len(closure["project_functions"]),
                "eligible_library_functions": len(closure["eligible_library_functions"]),
                "shipped_library_functions": len(closure["shipped_library_functions"]),
                "omitted_library_functions": len(closure["omitted_library_functions"]),
                "function_names": closure["functions"],
            },
            "artifact": {
                "objects": artifact_manifest["objects"],
                "code_bytes": artifact_manifest["code_bytes"],
                "directory_bytes": artifact_manifest["directory_bytes"],
                "sha256": sha(build_dir / "app.l65m"),
            },
            "runtime_audit": runtime_audit,
            "stager_audit": stager_audit,
            "host_execution": host,
            "files": {
                name: {"bytes": path.stat().st_size, "sha256": sha(path)}
                for name, path in sorted(file_paths.items())
            },
        }
        write_json(build_dir / "ship.json", manifest)
        entries = [
            (stager, "autoboot.c65"),
            (build_dir / "boot.id", "boot.id"),
            (runtime, "runtime.prg"),
            (build_dir / "runtime.bin", "runtime.bin"),
            (build_dir / "app.l65m", "app.l65m"),
            (build_dir / "project.l65p", "project.l65p"),
            (build_dir / "ship.lock", "ship.lock"),
            (build_dir / "ship.json", "ship.json"),
            (build_dir / "license.txt", "license.txt"),
        ]
        packed_image = build_dir / output.name
        (build_dir / "c1541.txt").write_text(
            c1541_build(packed_image, entries), encoding="utf-8"
        )
        verification = verify_image(
            packed_image, contract_path=root / "config/ship-builder-v1.json"
        )
        receipt = {
            "format": RECEIPT_FORMAT,
            "status": "passed",
            "ship_form": form,
            "project": project_path.as_posix(),
            "image": {
                "path": output.name,
                "bytes": packed_image.stat().st_size,
                "sha256": sha(packed_image),
            },
            "build_identity_sha256": identity_sha,
            "closure": manifest["closure"],
            "host_execution": host,
            "runtime_audit": runtime_audit,
            "stager_audit": stager_audit,
            "verification": verification,
            "executions": 1,
        }
        staged_receipt = build_dir / sidecars[0].name
        staged_elf = build_dir / sidecars[1].name
        staged_stager_elf = build_dir / sidecars[2].name
        staged_closure = build_dir / sidecars[3].name
        write_json(staged_receipt, receipt)
        shutil.copyfile(elf, staged_elf)
        shutil.copyfile(Path(str(stager) + ".elf"), staged_stager_elf)
        shutil.copyfile(build_dir / "closure.json", staged_closure)
        # Publish the image last.  Any build, pack, verification or sidecar
        # failure therefore leaves no destination D81 behind.
        os.replace(staged_receipt, sidecars[0])
        os.replace(staged_elf, sidecars[1])
        os.replace(staged_stager_elf, sidecars[2])
        os.replace(staged_closure, sidecars[3])
        os.replace(packed_image, output)
        return receipt


def contract_selftest() -> dict[str, Any]:
    contract = load_json(CONTRACT, "ship contract")
    catalog = load_json(CATALOG, "ship catalog")
    validate_contract(contract, catalog)
    good = parse_ship_form("(ship \"probe\" :entry 'main)")
    require(good == ("probe", "main"), "ship form oracle drift")
    bad = [
        "(ship)", "(ship probe :entry 'main)", "(ship \"p\" :entry main)",
        "(ship \"p\" :entry 'main :extra t)", "(build \"p\" :entry 'main)",
    ]
    rejected = 0
    for source in bad:
        try:
            parse_ship_form(source)
        except ShipError:
            rejected += 1
    require(rejected == len(bad), "ship form mutation escaped")
    mutated = json.loads(json.dumps(contract))
    mutated["media"]["descriptor_version"] = 2
    try:
        validate_contract(mutated, catalog)
    except ShipError:
        rejected += 1
    else:
        raise ShipError("ship contract mutation escaped")
    bad_catalog = json.loads(json.dumps(catalog))
    bad_catalog["libraries"][0]["sources"] = []
    try:
        validate_contract(contract, bad_catalog)
    except ShipError:
        rejected += 1
    else:
        raise ShipError("ship catalog mutation escaped")
    missing_sample = json.loads(json.dumps(contract))
    missing_sample["gates"]["samples"] = missing_sample["gates"]["samples"][:-1]
    try:
        validate_contract(missing_sample, catalog)
    except ShipError:
        rejected += 1
    else:
        raise ShipError("ship sample execution-list mutation escaped")
    with tempfile.TemporaryDirectory(prefix="lisp65-ship-selftest-") as raw:
        wrong = Path(raw) / "wrong-name.d81"
        try:
            build(
                '(ship "hello" :entry \'main)',
                ROOT / "examples/ship/hello/project.l65p", wrong,
            )
        except ShipError:
            rejected += 1
        else:
            raise ShipError("ship output-name mutation escaped")
        require(not wrong.exists(), "failed ship build leaked destination image")
    return {"status": "passed", "form": good, "mutations_rejected": rejected}


def repro(
    form: str, project_path: Path, out: Path, *, fresh: bool,
    cc_override: Path | None,
) -> dict[str, Any]:
    require(not out.exists(), "repro-output-exists")
    out.mkdir(parents=True)
    images: list[Path] = []
    if fresh:
        status = run(["git", "status", "--porcelain", "--untracked-files=normal"],
                     "fresh reproducibility status")
        require(not status.strip(), "fresh reproducibility requires a clean tree")
        project_rel = project_path.resolve().relative_to(ROOT.resolve())
        for index in (1, 2):
            checkout = out / f"checkout-{index}"
            checkout.mkdir()
            archive = subprocess.Popen(["git", "archive", "HEAD"], cwd=ROOT, stdout=subprocess.PIPE)
            extract = subprocess.run(["tar", "-x", "-C", str(checkout)], stdin=archive.stdout)
            assert archive.stdout is not None
            archive.stdout.close()
            archive_rc = archive.wait()
            require(archive_rc == 0 and extract.returncode == 0, "fresh checkout extraction failed")
            image = out / f"build-{index}" / (parse_ship_form(form)[0] + ".d81")
            build(form, checkout / project_rel, image, root=checkout, cc_override=cc_override)
            images.append(image)
    else:
        for index in (1, 2):
            image = out / f"build-{index}" / (parse_ship_form(form)[0] + ".d81")
            build(form, project_path, image, root=ROOT, cc_override=cc_override)
            images.append(image)
    left, right = (path.read_bytes() for path in images)
    require(left == right, "ship clean builds are not byte-identical")
    value = {
        "format": REPRO_FORMAT,
        "status": "passed-byte-identical",
        "fresh_checkouts": fresh,
        "builds": [bind(path, root=out) for path in images],
        "comparison_sha256": sha_bytes(left),
        "executions": 2,
    }
    write_json(out / "reproducibility.json", value)
    return value


def sample_fleet(out: Path, *, cc_override: Path | None) -> dict[str, Any]:
    """Build and execute every contracted sample through the public path."""
    require(not out.exists(), "sample-fleet-output-exists")
    out.mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    for name, relative in SAMPLE_FLEET:
        image = out / f"{name}.d81"
        receipt = build(
            f'(ship "{name}" :entry \'main)', ROOT / relative, image,
            cc_override=cc_override,
        )
        require(
            receipt["executions"] == 1
            and receipt["host_execution"]["status"] == "passed"
            and receipt["verification"]["members_verified"] == 9,
            f"sample execution witness drift: {name}",
        )
        rows.append({
            "name": name,
            "project": relative,
            "image": bind(image, root=out),
            "closure_functions": len(receipt["closure"]["function_names"]),
            "host_executions": receipt["executions"],
            "media_members_verified": receipt["verification"]["members_verified"],
            "host_output": receipt["host_execution"]["output"],
        })
    value = {
        "format": "lisp65-ship-sample-fleet-receipt-v1",
        "status": "passed",
        "samples": rows,
        "sample_count": len(rows),
        "host_executions": sum(row["host_executions"] for row in rows),
        "media_members_verified": sum(row["media_members_verified"] for row in rows),
    }
    require(
        value["sample_count"] == 5 and value["host_executions"] == 5
        and value["media_members_verified"] == 45
        and "input=4 output=13" in next(
            row["host_output"] for row in rows if row["name"] == "interactive"
        ),
        "sample fleet execution witness drift",
    )
    write_json(out / "fleet-receipt.json", value)
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    prepare_parser = sub.add_parser("prepare")
    build_parser = sub.add_parser("build")
    verify_parser = sub.add_parser("verify")
    repro_parser = sub.add_parser("repro")
    fleet_parser = sub.add_parser("fleet")
    for item in (prepare_parser, build_parser, repro_parser):
        item.add_argument("--form", required=True)
        item.add_argument("--project", type=Path, required=True)
    prepare_parser.add_argument("--out", type=Path, required=True)
    build_parser.add_argument("--out", type=Path, required=True)
    build_parser.add_argument("--cc", type=Path)
    verify_parser.add_argument("--image", type=Path, required=True)
    repro_parser.add_argument("--out", type=Path, required=True)
    repro_parser.add_argument("--fresh", action="store_true")
    repro_parser.add_argument("--cc", type=Path)
    fleet_parser.add_argument("--out", type=Path, required=True)
    fleet_parser.add_argument("--cc", type=Path)
    args = parser.parse_args(argv)
    if args.command == "selftest":
        value = contract_selftest()
        print(f"ship-builder selftest: PASS mutations={value['mutations_rejected']}")
    elif args.command == "prepare":
        value = prepare(args.form, args.project.resolve(), args.out.resolve())
        print(f"ship-builder prepare: PASS project={value['name']} entry={value['entry']}")
    elif args.command == "build":
        value = build(args.form, args.project.resolve(), args.out.resolve(), cc_override=args.cc)
        print(f"ship-builder build: PASS image={args.out} sha256={value['image']['sha256']}")
    elif args.command == "verify":
        value = verify_image(args.image.resolve())
        print(f"ship-builder verify: PASS members={value['members_verified']} sha256={value['image_sha256']}")
    elif args.command == "repro":
        value = repro(args.form, args.project.resolve(), args.out.resolve(),
                      fresh=args.fresh, cc_override=args.cc)
        print(f"ship-builder repro: PASS fresh={str(args.fresh).lower()} sha256={value['comparison_sha256']}")
    else:
        value = sample_fleet(args.out.resolve(), cc_override=args.cc)
        print(
            "ship-builder fleet: PASS "
            f"samples={value['sample_count']} host-executions={value['host_executions']} "
            f"media-members={value['media_members_verified']}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, UnicodeError, ValueError, ShipError) as exc:
        print(f"ship-builder: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
