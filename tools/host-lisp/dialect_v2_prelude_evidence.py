#!/usr/bin/env python3
"""Generate and verify profile-bound dialect-family budget evidence."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
from typing import Any

import dialect_contract as V1
import dialect_v2_family_artifact as FAMILY_ARTIFACT


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "config/dialect-migration-contract.json"
PROFILES = ("dialect-v1", "dialect-v2")
FAMILY_CONFIGS = {
    "prelude-control": {
        "fixture": ROOT / "tests/bytecode/dialect-v2/prelude-control/cases.json",
        "verdicts": ROOT / "build/bytecode/dialect-v2/prelude-control",
        "evidence": ROOT / "tests/bytecode/dialect-v2/evidence/prelude-control",
        "fixture_format": "lisp65-dialect-v2-prelude-control-cases-v1",
        "semantic_contract": "dialect-v2-prelude-control",
        "engines": ("native-c-compiler-vm", "native-c-treewalk"),
    },
    "lists": {
        "fixture": ROOT / "tests/bytecode/dialect-v2/lists/cases.json",
        "verdicts": ROOT / "build/bytecode/dialect-v2/lists",
        "evidence": ROOT / "tests/bytecode/dialect-v2/evidence/lists",
        "fixture_format": "lisp65-dialect-v2-lists-cases-v1",
        "semantic_contract": "dialect-v2-lists",
        "engines": (
            "lisp-lcc", "native-c-compiler-vm", "native-c-treewalk",
            "python-p0-compiler-vm",
        ),
    },
    "strings": {
        "fixture": ROOT / "tests/bytecode/dialect-v2/strings/cases.json",
        "verdicts": ROOT / "build/bytecode/dialect-v2/strings",
        "evidence": ROOT / "tests/bytecode/dialect-v2/evidence/strings",
        "fixture_format": "lisp65-dialect-v2-strings-cases-v1",
        "semantic_contract": "dialect-v2-strings",
        "engines": (
            "lisp-lcc", "native-c-compiler-vm", "native-c-treewalk",
            "python-p0-compiler-vm",
        ),
    },
    "system-runtime": {
        "fixture": ROOT / "tests/bytecode/dialect-v2/system-runtime/cases.json",
        "verdicts": ROOT / "build/bytecode/dialect-v2/system-runtime",
        "evidence": ROOT / "tests/bytecode/dialect-v2/evidence/system-runtime",
        "fixture_format": "lisp65-dialect-v2-system-runtime-cases-v1",
        "semantic_contract": "dialect-v2-system-runtime",
        "engines": (
            "lisp-lcc", "native-c-compiler-vm", "native-c-treewalk",
            "python-p0-compiler-vm",
        ),
    },
}
FAMILY = "prelude-control"
SEMANTIC_CONTRACT = "dialect-v2-prelude-control"
ENGINES = FAMILY_CONFIGS[FAMILY]["engines"]
FIXTURE_FORMAT = FAMILY_CONFIGS[FAMILY]["fixture_format"]
V1_MACRO_SOURCES = (
    "lib/prelude-m1.lisp",
    "lib/stdlib-control.lisp",
    "lib/stdlib-places.lisp",
)
V2_PRELUDE = "lib/dialect-v2/prelude-control.lisp"
V2_LIST_SOURCES = (
    "lib/dialect-v2/lists-core.lisp",
    "lib/dialect-v2/lists-library.lisp",
)
V2_STRING_SOURCES = (
    "lib/dialect-v2/strings-core.lisp",
    "lib/dialect-v2/strings-library.lisp",
    "lib/dialect-v2/eval-runtime.lisp",
)
V2_SYSTEM_SOURCES = (
    "lib/dialect-v2/system-format-library.lisp",
    "lib/dialect-v2/system-screen-library.lisp",
    "lib/m65-disk.lisp",
    "lib/runtime-core.lisp",
)
PLACES_SOURCE = "lib/stdlib-places.lisp"
NATIVE_SOURCES = ("src/compile.c", "src/eval.c")
GENERATED_NAMES: set[str] = set()
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _configure(family: str) -> None:
    global FAMILY, SEMANTIC_CONTRACT, ENGINES, FIXTURE_FORMAT, GENERATED_NAMES
    if family not in FAMILY_CONFIGS:
        raise EvidenceError(f"unsupported evidence family: {family}")
    FAMILY = family
    config = FAMILY_CONFIGS[family]
    SEMANTIC_CONTRACT = config["semantic_contract"]
    ENGINES = config["engines"]
    FIXTURE_FORMAT = config["fixture_format"]
    GENERATED_NAMES = {
        "dialect-v1-inventory.json",
        "dialect-v1-manifest.json",
        "dialect-v2-inventory.json",
        "dialect-v2-manifest.json",
        "dialect-v1-profile.l65p",
        "dialect-v2-profile.l65p",
        "differential-receipt.json",
        *{
            f"{profile}-{engine}-verdict.json"
            for profile in PROFILES for engine in ENGINES
        },
    }
    if family != "prelude-control":
        GENERATED_NAMES.update(
            {
                "dialect-v1-internal-accounting.json",
                "dialect-v2-internal-accounting.json",
            }
        )
    if family == "lists":
        GENERATED_NAMES.update(
            {
                "dialect-v2-lists-core.l65m",
                "dialect-v2-lists-core.manifest.json",
                "dialect-v2-lists-library.l65m",
                "dialect-v2-lists-library.manifest.json",
            }
        )


_configure(FAMILY)


class EvidenceError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise EvidenceError(f"{label} must be a regular non-symlink file: {path}")
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except EvidenceError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"{label} must be an object")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise EvidenceError(f"{label} keys drift: {actual}")
    return value


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise EvidenceError(f"evidence path must remain inside the repository: {path}") from exc


def _source_binding(path_text: str) -> dict[str, str]:
    path = ROOT / path_text
    if path.is_symlink() or not path.is_file():
        raise EvidenceError(f"inventory source is missing: {path_text}")
    return {"path": path_text, "sha256": _sha_file(path)}


def _lisp_definitions(path_text: str) -> dict[str, str]:
    text = (ROOT / path_text).read_text(encoding="utf-8")
    definitions: dict[str, str] = {}
    for kind, name in re.findall(r"^\(def(un|macro)\s+([^\s()]+)", text, re.M):
        if name in definitions:
            raise EvidenceError(f"duplicate top-level definition in {path_text}: {name}")
        definitions[name] = "function" if kind == "un" else "macro"
    return definitions


def _v1_surfaces(contract: dict[str, Any]) -> tuple[set[str], dict[str, set[str]]]:
    surfaces = contract.get("current_surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        raise EvidenceError("dialect-v1 contract lacks current surfaces")
    public: set[str] = set()
    by_name: dict[str, set[str]] = {}
    for index, raw in enumerate(surfaces):
        surface = _exact(
            raw,
            {
                "id", "status", "kind", "public_role", "internal_role", "delivery",
                "suite_manifest", "application_descriptor", "generated_manifest",
                "binding", "sources", "public_names", "internal_inventory",
                "private_inline_inventory", "private_inline_delivery",
            },
            f"dialect-v1 current_surfaces[{index}]",
        )
        surface_id = surface["id"]
        names = surface["public_names"]
        if not isinstance(surface_id, str) or not isinstance(names, list):
            raise EvidenceError("dialect-v1 surface identity/public names are invalid")
        for name in names:
            if not isinstance(name, str) or not name:
                raise EvidenceError(f"dialect-v1 surface {surface_id} has an invalid name")
            public.add(name)
            by_name.setdefault(name, set()).add(surface_id)
    return public, by_name


def _replacement_targets(contract: dict[str, Any]) -> dict[str, str | None]:
    replacements = contract["classification"]["replacements"]
    removals = contract["classification"]["removals"]
    result = {item["name"]: item["target"] for item in replacements}
    result.update({item["name"]: None for item in removals})
    return result


def _classification_snapshot(contract: dict[str, Any]) -> dict[str, Any]:
    groups = [
        group for group in contract["classification"]["name_groups"]
        if group["family"] == FAMILY
    ]
    names = {name for group in groups for name in group["names"]}
    replacements = [
        item for item in contract["classification"]["replacements"]
        if item["name"] in names
    ]
    removals = [
        item for item in contract["classification"]["removals"]
        if item["name"] in names
    ]
    macros = [
        item for item in contract["syntax"]["macro_migrations"]
        if item["family"] == FAMILY
    ]
    new_names = [
        item for item in contract["classification"]["new_names"]
        if item["family"] == FAMILY
    ]
    family = next((item for item in contract["families"] if item["id"] == FAMILY), None)
    if not groups or family is None or (FAMILY == "prelude-control" and not macros):
        raise EvidenceError(f"{FAMILY} classification is incomplete")
    result = {
        "family": FAMILY,
        "name_groups": groups,
        "replacements": replacements,
        "removals": removals,
        "macro_migrations": macros,
        "retained_macros": (
            contract["syntax"]["retained_macros"]
            if FAMILY == "prelude-control" else []
        ),
        "projection": family["projection"],
        "acceptance": family["acceptance"],
    }
    if FAMILY in {"lists", "system-runtime"}:
        result["new_names"] = new_names
    return result


def _inventory_sets(contract: dict[str, Any]) -> dict[str, dict[str, set[str]]]:
    snapshot = _classification_snapshot(contract)
    targets = _replacement_targets(contract)
    ordinary: dict[str, dict[str, Any]] = {}
    for group in snapshot["name_groups"]:
        for name in group["names"]:
            if name in ordinary:
                raise EvidenceError(f"Prelude/Control classification duplicates {name}")
            ordinary[name] = group
    migrations = {item["name"]: item for item in snapshot["macro_migrations"]}
    retained = set(snapshot["retained_macros"])
    new_names = {item["name"]: item for item in snapshot.get("new_names", [])}
    if (
        set(ordinary) & (set(migrations) | retained | set(new_names))
        or set(migrations) & (retained | set(new_names))
        or retained & set(new_names)
    ):
        raise EvidenceError(f"{FAMILY} public inventories overlap")

    baseline_loaded = set(ordinary) | set(migrations) | retained
    candidate_ordinary = {
        name for name, group in ordinary.items()
        if group["disposition"] not in {"internalize", "remove-v2"}
        and not (group["disposition"] == "replace" and targets.get(name) != name)
    }
    candidate_macros = retained | {
        name for name, item in migrations.items() if item["disposition"] != "remove-v2"
    }
    candidate_loaded = candidate_ordinary | candidate_macros | set(new_names)
    baseline_boot = set(baseline_loaded)
    candidate_boot = retained | {
        name for name, group in ordinary.items()
        if name in candidate_ordinary
        and group["target_delivery"] in {"unchanged", "bank0-native", "bank5-preload"}
    } | {
        name for name, item in migrations.items()
        if item["target_delivery"] == "bank5-preload"
    } | {
        name for name, item in new_names.items()
        if item["target_delivery"] in {"unchanged", "bank0-native", "bank5-preload"}
    }
    baseline_directory = set(baseline_loaded)
    candidate_directory = set(candidate_loaded)
    if FAMILY == "system-runtime":
        groups_by_id = {group["id"]: set(group["names"]) for group in snapshot["name_groups"]}
        baseline_boot -= (
            groups_by_id["system-m65d-keep"]
            | groups_by_id["system-runtime-export-keep"]
        )
        candidate_boot -= groups_by_id["system-runtime-export-keep"]
        candidate_directory |= groups_by_id["system-internalize"]
    result = {
        "dialect-v1": {
            "loaded": baseline_loaded,
            "boot": baseline_boot,
            "directory": baseline_directory,
        },
        "dialect-v2": {
            "loaded": candidate_loaded,
            "boot": candidate_boot,
            "directory": candidate_directory,
        },
    }
    projection = snapshot["projection"]
    actual = {
        "loaded_symbol_delta": len(candidate_loaded) - len(baseline_loaded),
        "loaded_namepool_delta_bytes": _namepool(candidate_loaded) - _namepool(baseline_loaded),
        "boot_symbol_delta": len(candidate_boot) - len(baseline_boot),
        "boot_namepool_delta_bytes": _namepool(candidate_boot) - _namepool(baseline_boot),
        "directory_delta": len(candidate_directory) - len(baseline_directory),
    }
    if actual != projection:
        raise EvidenceError(f"derived {FAMILY} budget misses projection: {actual} != {projection}")
    return result


def _namepool(names: set[str] | list[str]) -> int:
    return sum(len(name) + 1 for name in names)


def _validate_prelude_sources(
    contract: dict[str, Any],
    v1_contract: dict[str, Any],
    inventories: dict[str, dict[str, set[str]]],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    snapshot = _classification_snapshot(contract)
    ordinary = {
        name for group in snapshot["name_groups"] for name in group["names"]
    }
    public, surfaces = _v1_surfaces(v1_contract)
    if not ordinary <= public:
        raise EvidenceError(f"v1 public inventory misses classified names: {sorted(ordinary - public)}")
    for name in ordinary:
        if not surfaces[name] & {"native-eval-and-p0-primitives", "workbench-preload"}:
            raise EvidenceError(f"classified v1 Prelude name is not boot-loaded: {name}")
        if surfaces[name] == {"native-eval-and-p0-primitives"}:
            raise EvidenceError(f"classified v1 Prelude name has no directory binding: {name}")

    v1_defs: dict[str, tuple[str, str]] = {}
    for source in V1_MACRO_SOURCES:
        for name, kind in _lisp_definitions(source).items():
            if kind == "macro":
                if name in v1_defs:
                    raise EvidenceError(f"v1 macro definition is ambiguous: {name}")
                v1_defs[name] = (kind, source)
    expected_v1_macros = set(snapshot["retained_macros"]) | {
        item["name"] for item in snapshot["macro_migrations"]
    }
    if any(
        item["source_delivery"] != "bank5-preload"
        for item in snapshot["macro_migrations"]
    ):
        raise EvidenceError("v1 Prelude macro source delivery is not uniformly boot-loaded")
    if set(v1_defs) != expected_v1_macros:
        raise EvidenceError(
            "v1 macro source/contract drift: "
            f"missing={sorted(expected_v1_macros - set(v1_defs))} "
            f"extra={sorted(set(v1_defs) - expected_v1_macros)}"
        )

    v2_defs = _lisp_definitions(V2_PRELUDE)
    v2_functions = {name for name, kind in v2_defs.items() if kind == "function"}
    v2_macros = {name for name, kind in v2_defs.items() if kind == "macro"}
    places_macros = {
        name for name, kind in _lisp_definitions(PLACES_SOURCE).items() if kind == "macro"
    }
    compile_text = (ROOT / "src/compile.c").read_text(encoding="utf-8")
    match = re.search(r"static const char \*sf\[\]\s*=\s*\{(.*?)\};", compile_text, re.S)
    if match is None:
        raise EvidenceError("cannot derive native compiler special forms")
    native_macros = set(re.findall(r'"([^"]+)"', match.group(1))) | {"defun"}

    groups = {
        name: group for group in snapshot["name_groups"] for name in group["names"]
    }
    for name, group in groups.items():
        if group["disposition"] == "redefine" and name not in v2_functions:
            raise EvidenceError(f"v2 redefinition lacks a real function definition: {name}")
    migrations = {item["name"]: item for item in snapshot["macro_migrations"]}
    for name, item in migrations.items():
        if item["disposition"] == "keep" and name not in v2_macros:
            raise EvidenceError(f"kept v2 macro lacks a real profile definition: {name}")
        if item["disposition"] == "move-library" and name not in places_macros:
            raise EvidenceError(f"moved v2 macro lacks its library definition: {name}")
        if item["disposition"] == "remove-v2" and (
            name in v2_macros or name in native_macros
        ):
            raise EvidenceError(f"removed v2 macro remains in the target profile: {name}")
    retained = set(snapshot["retained_macros"])
    missing_retained = retained - (v2_macros | native_macros)
    if missing_retained:
        raise EvidenceError(f"v2 retained macros lack real definitions: {sorted(missing_retained)}")
    expected_v2_public_defs = inventories["dialect-v2"]["loaded"]
    leaked_defs = {
        name for name in v2_defs
        if not name.startswith("%") and name not in expected_v2_public_defs
    }
    if leaked_defs:
        raise EvidenceError(f"v2 Prelude source leaks unclassified public definitions: {sorted(leaked_defs)}")

    baseline_provenance = {
        name: [f"dialect-v1-surface:{surface}" for surface in sorted(surfaces[name])]
        for name in ordinary
    }
    baseline_provenance.update(
        {name: [f"source:{source}"] for name, (_kind, source) in v1_defs.items()}
    )
    candidate_provenance: dict[str, list[str]] = {}
    for name in inventories["dialect-v2"]["loaded"]:
        if name in groups:
            candidate_provenance[name] = (
                [f"source:{V2_PRELUDE}"] if name in v2_defs
                else [f"unchanged-v1-surface:{surface}" for surface in sorted(surfaces[name])]
            )
        elif name in v2_macros:
            candidate_provenance[name] = [f"source:{V2_PRELUDE}"]
        elif name in places_macros:
            candidate_provenance[name] = [f"source:{PLACES_SOURCE}"]
        elif name in native_macros:
            candidate_provenance[name] = ["native-special-form:src/compile.c"]
        else:
            raise EvidenceError(f"cannot prove v2 definition provenance: {name}")
    return baseline_provenance, candidate_provenance


def _validate_lists_sources(
    contract: dict[str, Any],
    v1_contract: dict[str, Any],
    inventories: dict[str, dict[str, set[str]]],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    snapshot = _classification_snapshot(contract)
    ordinary = {
        name for group in snapshot["name_groups"] for name in group["names"]
    }
    public, surfaces = _v1_surfaces(v1_contract)
    if not ordinary <= public:
        raise EvidenceError(f"dialect-v1 public inventory misses Lists names: {sorted(ordinary - public)}")

    definitions: dict[str, str] = {}
    for source in V2_LIST_SOURCES:
        for name in _lisp_definitions(source):
            if name in definitions and not name.startswith("%"):
                raise EvidenceError(f"duplicate public Lists definition: {name}")
            definitions[name] = source
    public_definitions = {name for name in definitions if not name.startswith("%")}
    expected_public = inventories["dialect-v2"]["loaded"]
    leaked = public_definitions - expected_public
    if leaked:
        raise EvidenceError(f"v2 Lists sources leak unclassified public definitions: {sorted(leaked)}")

    groups = {
        name: group for group in snapshot["name_groups"] for name in group["names"]
    }
    required_defs = {
        name for name, group in groups.items()
        if group["disposition"] in {"redefine", "move-library"}
    } | {item["name"] for item in snapshot["new_names"]}
    missing = required_defs - public_definitions
    if missing:
        raise EvidenceError(f"v2 Lists definitions are missing: {sorted(missing)}")

    baseline = {
        name: [f"dialect-v1-surface:{surface}" for surface in sorted(surfaces[name])]
        for name in ordinary
    }
    candidate: dict[str, list[str]] = {}
    for name in expected_public:
        if name in definitions:
            candidate[name] = [f"source:{definitions[name]}"]
        elif name in surfaces:
            candidate[name] = [
                f"unchanged-v1-surface:{surface}" for surface in sorted(surfaces[name])
            ]
        else:
            raise EvidenceError(f"cannot prove v2 Lists definition provenance: {name}")
    return baseline, candidate


def _validate_strings_sources(
    contract: dict[str, Any],
    v1_contract: dict[str, Any],
    inventories: dict[str, dict[str, set[str]]],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    snapshot = _classification_snapshot(contract)
    ordinary = {
        name for group in snapshot["name_groups"] for name in group["names"]
    }
    public, surfaces = _v1_surfaces(v1_contract)
    if not ordinary <= public:
        raise EvidenceError(
            f"dialect-v1 public inventory misses Strings names: {sorted(ordinary - public)}"
        )

    definitions: dict[str, str] = {}
    dedicated_public: set[str] = set()
    for source in V2_STRING_SOURCES:
        for name in _lisp_definitions(source):
            if name in definitions and not name.startswith("%"):
                raise EvidenceError(f"duplicate public Strings definition: {name}")
            definitions[name] = source
            if source != "lib/dialect-v2/eval-runtime.lisp" and not name.startswith("%"):
                dedicated_public.add(name)
    expected_public = inventories["dialect-v2"]["loaded"]
    leaked = dedicated_public - expected_public
    if leaked:
        raise EvidenceError(
            f"v2 Strings sources leak unclassified public definitions: {sorted(leaked)}"
        )
    groups = {
        name: group for group in snapshot["name_groups"] for name in group["names"]
    }
    required_defs = {
        name for name, group in groups.items()
        if group["disposition"] in {"redefine", "move-library"}
        or name in dedicated_public
    }
    missing = required_defs - set(definitions)
    if missing:
        raise EvidenceError(f"v2 Strings definitions are missing: {sorted(missing)}")

    baseline = {
        name: [f"dialect-v1-surface:{surface}" for surface in sorted(surfaces[name])]
        for name in ordinary
    }
    candidate: dict[str, list[str]] = {}
    for name in expected_public:
        if name in definitions:
            candidate[name] = [f"source:{definitions[name]}"]
        elif name in surfaces:
            candidate[name] = [
                f"unchanged-v1-surface:{surface}" for surface in sorted(surfaces[name])
            ]
        else:
            raise EvidenceError(f"cannot prove v2 Strings definition provenance: {name}")
    return baseline, candidate


def _validate_system_sources(
    contract: dict[str, Any],
    v1_contract: dict[str, Any],
    inventories: dict[str, dict[str, set[str]]],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    snapshot = _classification_snapshot(contract)
    ordinary = {
        name for group in snapshot["name_groups"] for name in group["names"]
    }
    public, surfaces = _v1_surfaces(v1_contract)
    if not ordinary <= public:
        raise EvidenceError(
            "dialect-v1 public inventory misses System/Runtime names: "
            f"{sorted(ordinary - public)}"
        )

    definitions: dict[str, str] = {}
    for source in V2_SYSTEM_SOURCES:
        for name in _lisp_definitions(source):
            definitions[name] = source

    baseline = {
        name: [f"dialect-v1-surface:{surface}" for surface in sorted(surfaces[name])]
        for name in inventories["dialect-v1"]["loaded"]
    }
    candidate: dict[str, list[str]] = {}
    native_new = {"key-event", "set"}
    for name in inventories["dialect-v2"]["loaded"]:
        if name in definitions:
            candidate[name] = [f"source:{definitions[name]}"]
        elif name in native_new:
            candidate[name] = ["native-primitive:config/bytecode-abi-ledger.json"]
        elif name in surfaces:
            candidate[name] = [
                f"unchanged-v1-surface:{surface}" for surface in sorted(surfaces[name])
            ]
        else:
            raise EvidenceError(
                f"cannot prove v2 System/Runtime definition provenance: {name}"
            )
    return baseline, candidate


def _validate_sources(
    contract: dict[str, Any],
    v1_contract: dict[str, Any],
    inventories: dict[str, dict[str, set[str]]],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    if FAMILY == "prelude-control":
        return _validate_prelude_sources(contract, v1_contract, inventories)
    if FAMILY == "lists":
        return _validate_lists_sources(contract, v1_contract, inventories)
    if FAMILY == "strings":
        return _validate_strings_sources(contract, v1_contract, inventories)
    if FAMILY == "system-runtime":
        return _validate_system_sources(contract, v1_contract, inventories)
    raise EvidenceError(f"unsupported evidence family: {FAMILY}")


def _inventory_artifact(
    profile: str,
    sets: dict[str, set[str]],
    provenance: dict[str, list[str]],
    policy_sha: str,
    source_bindings: list[dict[str, str]],
) -> dict[str, Any]:
    definitions = []
    for name in sorted(sets["loaded"]):
        definitions.append(
            {
                "name": name,
                "boot": name in sets["boot"],
                "directory": name in sets["directory"],
                "provenance": provenance[name],
            }
        )
    return {
        "format": "lisp65-dialect-family-inventory-v1",
        "profile": profile,
        "family": FAMILY,
        "classification_sha256": policy_sha,
        "source_bindings": source_bindings,
        "definitions": definitions,
    }


def _manifest(
    profile: str,
    sets: dict[str, set[str]],
    artifact_path: Path,
    artifact_bytes: bytes,
) -> dict[str, Any]:
    return {
        "format": "lisp65-dialect-family-artifact-v1",
        "profile": profile,
        "family": FAMILY,
        "loaded_symbols": sorted(sets["loaded"]),
        "boot_symbols": sorted(sets["boot"]),
        "directory_entries": sorted(sets["directory"]),
        "artifact": {
            "path": _relative(artifact_path),
            "sha256": _sha_bytes(artifact_bytes),
        },
    }


def _pack_profile_artifact(
    profile: str,
    loaded: bytes,
    boot: bytes,
    measurement: dict[str, Any],
) -> bytes:
    metadata_value = {
        "format": "lisp65-dialect-family-profile-container-v1",
        "profile": profile,
        "family": FAMILY,
        "source_commit": measurement["source_commit"],
        "source_bindings": measurement["source_bindings"],
        "strict_arity": measurement["strict_arity"],
        "loaded_image_sha256": measurement["loaded_image_sha256"],
        "boot_image_sha256": measurement["boot_image_sha256"],
    }
    if FAMILY != "prelude-control":
        metadata_value["internal_accounting_sha256"] = _sha_bytes(
            _canonical(_internal_accounting_artifact(profile, measurement))
        )
    if FAMILY == "lists":
        metadata_value["tier_manifest_sha256s"] = {
            tier: _sha_bytes(_canonical(manifest))
            for tier, manifest in sorted(measurement["tier_manifests"].items())
        }
    metadata = _canonical(metadata_value)
    return (
        b"L65P\x01\x00\x00\x00"
        + len(metadata).to_bytes(4, "little")
        + len(loaded).to_bytes(4, "little")
        + len(boot).to_bytes(4, "little")
        + metadata
        + loaded
        + boot
    )


def _internal_accounting_artifact(
    profile: str, measurement: dict[str, Any]
) -> dict[str, Any]:
    return {
        "format": "lisp65-dialect-family-internal-accounting-v1",
        "family": FAMILY,
        "profile": profile,
        "source_commit": measurement["source_commit"],
        "roles": {
            role: {
                "image_sha256": measurement[f"{role}_image_sha256"],
                **measurement["internal_accounting"][role],
            }
            for role in ("loaded", "boot")
        },
    }


def _fixture_cases(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    _exact(fixture, {"format", "profile", "family", "cases"}, "fixture")
    if (
        fixture["format"] != FIXTURE_FORMAT
        or fixture["profile"] != "dialect-v1-v2-differential"
        or fixture["family"] != FAMILY
        or not isinstance(fixture["cases"], list)
        or not fixture["cases"]
    ):
        raise EvidenceError(f"{FAMILY} fixture identity drift")
    ids: list[str] = []
    for index, raw in enumerate(fixture["cases"]):
        case_keys = {"id", "forms", "migration_anchor", "observations"}
        if FAMILY == "lists":
            case_keys.add("tier")
        if FAMILY == "system-runtime":
            case_keys.remove("migration_anchor")
            case_keys.add("decision")
        case = _exact(
            raw, case_keys,
            f"fixture cases[{index}]",
        )
        if FAMILY == "system-runtime":
            decision = case.pop("decision")
            if not isinstance(decision, str) or not decision:
                raise EvidenceError(f"fixture case {index} decision is invalid")
            case["migration_anchor"] = f"decision:{decision}"
        case_id = case["id"]
        if not isinstance(case_id, str) or not ID_RE.fullmatch(case_id):
            raise EvidenceError(f"fixture case {index} id is invalid")
        ids.append(case_id)
        if FAMILY == "lists" and case["tier"] not in {"core", "library"}:
            raise EvidenceError(f"fixture case {case_id} tier is invalid")
        observations = _exact(
            case["observations"], set(PROFILES), f"fixture case {case_id} observations"
        )
        for profile in PROFILES:
            values = _exact(
                observations[profile], set(ENGINES),
                f"fixture case {case_id}/{profile}",
            )
            if any(
                not isinstance(values[engine], str)
                or not values[engine]
                or values[engine] != values[engine].strip()
                for engine in ENGINES
            ):
                raise EvidenceError(f"fixture case {case_id}/{profile} observation is invalid")
    if ids != sorted(set(ids)):
        raise EvidenceError("fixture cases must be sorted and unique")
    return fixture["cases"]


def _resolved_decisions(contract: dict[str, Any]) -> set[str]:
    decisions = contract["open_decisions"]
    if not isinstance(decisions, list):
        raise EvidenceError("open_decisions must be a list")
    resolved = {
        f"decision:{item['id']}" for item in decisions
        if isinstance(item, dict) and item.get("status") in {"resolved", "decided"}
    }
    if "decision:string-list-conversion-removal" in resolved:
        resolved.add("decision:string-character-list-removal")
    return resolved


def _validate_fixture_anchors(cases: list[dict[str, Any]], contract: dict[str, Any]) -> None:
    resolved = _resolved_decisions(contract)
    for case in cases:
        differs = any(
            case["observations"]["dialect-v1"][engine]
            != case["observations"]["dialect-v2"][engine]
            for engine in ENGINES
        )
        anchor = case["migration_anchor"]
        if differs:
            if anchor not in resolved:
                raise EvidenceError(f"fixture case {case['id']} lacks a resolved migration anchor")
        elif anchor is not None:
            raise EvidenceError(f"fixture case {case['id']} anchors an invariant observation matrix")


def _verdict_name(profile: str, engine: str) -> str:
    return f"{profile}-{engine}-verdict.json"


def _validate_verdict(
    value: dict[str, Any],
    profile: str,
    engine: str,
    fixture_sha: str,
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    _exact(
        value,
        {"format", "family", "profile", "engine", "fixture_sha256", "provenance", "cases"},
        f"{profile}/{engine} verdict",
    )
    if (
        value["format"] != "lisp65-dialect-v2-family-verdict-v1"
        or value["family"] != FAMILY
        or value["profile"] != profile
        or value["engine"] != engine
        or value["fixture_sha256"] != fixture_sha
        or not isinstance(value["cases"], list)
    ):
        raise EvidenceError(f"{profile}/{engine} verdict identity drift")
    provenance = _exact(
        value["provenance"],
        {"source_commit", "binary_sha256", "build_profile_sha256", "preload_sha256"},
        f"{profile}/{engine} provenance",
    )
    if (
        provenance["source_commit"] is not None
        and not isinstance(provenance["source_commit"], str)
    ) or (
        provenance["source_commit"] is not None
        and re.fullmatch(r"[0-9a-f]{40}", provenance["source_commit"]) is None
    ) or any(
        not isinstance(provenance[key], str)
        or re.fullmatch(r"[0-9a-f]{64}", provenance[key]) is None
        for key in ("binary_sha256", "build_profile_sha256", "preload_sha256")
    ):
        raise EvidenceError(f"{profile}/{engine} provenance is invalid")
    expected_by_id = {case["id"]: case for case in cases}
    ids: list[str] = []
    for index, raw in enumerate(value["cases"]):
        item = _exact(
            raw, {"id", "decision", "verdict", "result_sha256"},
            f"{profile}/{engine} verdict case {index}",
        )
        case_id = item["id"]
        ids.append(case_id)
        if case_id not in expected_by_id:
            raise EvidenceError(f"{profile}/{engine} verdict has an unknown case: {case_id}")
        case = expected_by_id[case_id]
        expected = case["observations"][profile][engine]
        if (
            item["decision"] != case["migration_anchor"]
            or item["verdict"] != "accept"
            or item["result_sha256"] != hashlib.sha256(expected.encode("utf-8")).hexdigest()
        ):
            raise EvidenceError(f"{profile}/{engine}/{case_id} observation binding drift")
    if ids != list(expected_by_id):
        raise EvidenceError(f"{profile}/{engine} verdict does not exactly cover the fixture")
    return provenance


def _metrics(manifest: dict[str, Any], artifact_bytes: bytes) -> dict[str, int]:
    return {
        "loaded_symbols": len(manifest["loaded_symbols"]),
        "loaded_namepool_bytes": _namepool(manifest["loaded_symbols"]),
        "boot_symbols": len(manifest["boot_symbols"]),
        "boot_namepool_bytes": _namepool(manifest["boot_symbols"]),
        "directory_entries": len(manifest["directory_entries"]),
        "artifact_bytes": len(artifact_bytes),
    }


def _actual_delta(
    baseline_manifest: dict[str, Any],
    candidate_manifest: dict[str, Any],
    baseline_artifact: bytes,
    candidate_artifact: bytes,
) -> dict[str, int]:
    baseline = _metrics(baseline_manifest, baseline_artifact)
    candidate = _metrics(candidate_manifest, candidate_artifact)
    return {
        "loaded_symbol_delta": candidate["loaded_symbols"] - baseline["loaded_symbols"],
        "loaded_namepool_delta_bytes": candidate["loaded_namepool_bytes"] - baseline["loaded_namepool_bytes"],
        "boot_symbol_delta": candidate["boot_symbols"] - baseline["boot_symbols"],
        "boot_namepool_delta_bytes": candidate["boot_namepool_bytes"] - baseline["boot_namepool_bytes"],
        "directory_delta": candidate["directory_entries"] - baseline["directory_entries"],
        "artifact_delta_bytes": candidate["artifact_bytes"] - baseline["artifact_bytes"],
    }


def render_evidence(
    contract_path: Path,
    fixture_path: Path,
    verdict_dir: Path,
    output_dir: Path,
) -> dict[str, bytes]:
    contract = _load(contract_path, "migration contract")
    fixture = _load(fixture_path, f"{FAMILY} fixture")
    cases = _fixture_cases(fixture)
    _validate_fixture_anchors(cases, contract)
    v1_path_value = contract["source_profile"]["dialect_contract"]
    if not isinstance(v1_path_value, str) or PurePosixPath(v1_path_value).is_absolute():
        raise EvidenceError("source_profile.dialect_contract is invalid")
    v1_path = ROOT / v1_path_value
    if _sha_file(v1_path) != contract["source_profile"]["dialect_contract_sha256"]:
        raise EvidenceError("dialect-v1 contract SHA binding drift")
    v1_contract = _load(v1_path, "dialect-v1 contract")
    try:
        V1.validate_schema(v1_contract)
        V1.validate_frozen_commit(
            contract["source_profile"]["source_commit"],
            v1_path_value,
            contract["source_profile"]["dialect_contract_sha256"],
        )
    except V1.DialectContractError as exc:
        raise EvidenceError(f"dialect-v1 source binding is invalid: {exc}") from exc

    inventory_sets = _inventory_sets(contract)
    baseline_provenance, candidate_provenance = _validate_sources(
        contract, v1_contract, inventory_sets
    )
    policy_sha = _canonical_digest(_classification_snapshot(contract))
    inventory_paths = {
        profile: output_dir / f"{profile}-inventory.json" for profile in PROFILES
    }
    artifact_bytes: dict[str, bytes] = {}
    measured_sets: dict[str, dict[str, set[str]]] = {}
    measurements: dict[str, dict[str, Any]] = {}
    tier_images: dict[str, bytes] = {}
    try:
        with tempfile.TemporaryDirectory(prefix=f".{FAMILY}-artifacts-", dir=ROOT / "build") as raw:
            build_root = Path(raw)
            for profile in PROFILES:
                images, measurement = FAMILY_ARTIFACT.build_profile(
                    profile,
                    inventory_sets[profile],
                    contract["source_profile"]["source_commit"],
                    v1_contract,
                    build_root / profile,
                    family=FAMILY,
                )
                measured_sets[profile] = {
                    "loaded": set(measurement["loaded_symbols"]),
                    "boot": set(measurement["boot_symbols"]),
                    "directory": set(measurement["directory_entries"]),
                }
                measurements[profile] = measurement
                if FAMILY == "lists" and profile == "dialect-v2":
                    tier_images = {
                        tier: images[f"tier-{tier}"]
                        for tier in ("core", "library")
                    }
                if measured_sets[profile] != inventory_sets[profile]:
                    raise EvidenceError(
                        f"{profile} built L65M surface differs from the classified profile"
                    )
                artifact_bytes[profile] = _pack_profile_artifact(
                    profile, images["loaded"], images["boot"], measurement
                )
    except FAMILY_ARTIFACT.FamilyArtifactError as exc:
        raise EvidenceError(str(exc)) from exc
    artifact_paths = {
        profile: output_dir / f"{profile}-profile.l65p" for profile in PROFILES
    }
    inventory_values = {
        "dialect-v1": _inventory_artifact(
            "dialect-v1", measured_sets["dialect-v1"], baseline_provenance,
            policy_sha, measurements["dialect-v1"]["source_bindings"],
        ),
        "dialect-v2": _inventory_artifact(
            "dialect-v2", measured_sets["dialect-v2"], candidate_provenance,
            policy_sha, measurements["dialect-v2"]["source_bindings"],
        ),
    }
    inventory_bytes = {
        profile: _canonical(value) for profile, value in inventory_values.items()
    }
    manifest_values = {
        profile: _manifest(
            profile,
            measured_sets[profile],
            artifact_paths[profile],
            artifact_bytes[profile],
        )
        for profile in PROFILES
    }
    manifest_bytes = {
        profile: _canonical(value) for profile, value in manifest_values.items()
    }
    accounting_bytes: dict[str, bytes] = {}
    if FAMILY != "prelude-control":
        accounting_bytes = {
            profile: _canonical(_internal_accounting_artifact(profile, measurements[profile]))
            for profile in PROFILES
        }

    fixture_sha = _sha_file(fixture_path)
    rendered: dict[str, bytes] = {}
    engine_results = []
    profile_builds: dict[str, dict[str, Any]] = {}
    engine_builds: list[dict[str, Any]] = []
    for engine in ENGINES:
        paths: dict[str, Path] = {}
        shas: dict[str, str] = {}
        for profile in PROFILES:
            source = verdict_dir / _verdict_name(profile, engine)
            verdict = _load(source, f"{profile}/{engine} verdict")
            provenance = _validate_verdict(verdict, profile, engine, fixture_sha, cases)
            build = {
                "profile": profile,
                "source_commit": provenance["source_commit"],
                "binary_sha256": provenance["binary_sha256"],
                "build_profile_sha256": provenance["build_profile_sha256"],
            }
            if FAMILY == "prelude-control":
                if profile in profile_builds and profile_builds[profile] != build:
                    raise EvidenceError(f"{profile} build provenance differs between engines")
                profile_builds[profile] = build
            else:
                engine_builds.append({"engine": engine, **build})
            encoded = _canonical(verdict)
            name = _verdict_name(profile, engine)
            rendered[name] = encoded
            paths[profile] = output_dir / name
            shas[profile] = _sha_bytes(encoded)
        engine_results.append(
            {
                "engine": engine,
                "baseline_verdict": _relative(paths["dialect-v1"]),
                "baseline_verdict_sha256": shas["dialect-v1"],
                "candidate_verdict": _relative(paths["dialect-v2"]),
                "candidate_verdict_sha256": shas["dialect-v2"],
                "baseline_preload_sha256": json.loads(
                    rendered[_verdict_name("dialect-v1", engine)]
                )["provenance"]["preload_sha256"],
                "candidate_preload_sha256": json.loads(
                    rendered[_verdict_name("dialect-v2", engine)]
                )["provenance"]["preload_sha256"],
                "result": "passed",
            }
        )

    baseline_manifest_path = output_dir / "dialect-v1-manifest.json"
    candidate_manifest_path = output_dir / "dialect-v2-manifest.json"
    actual = _actual_delta(
        manifest_values["dialect-v1"], manifest_values["dialect-v2"],
        artifact_bytes["dialect-v1"], artifact_bytes["dialect-v2"],
    )
    receipt = {
        "format": (
            "lisp65-dialect-family-differential-v1"
            if FAMILY == "prelude-control"
            else "lisp65-dialect-family-differential-v2"
        ),
        "family": FAMILY,
        "baseline_profile": "dialect-v1",
        "candidate_profile": "dialect-v2",
        "baseline_manifest_sha256": _sha_bytes(manifest_bytes["dialect-v1"]),
        "candidate_manifest_sha256": _sha_bytes(manifest_bytes["dialect-v2"]),
        "actual": actual,
        "semantic_contract_id": SEMANTIC_CONTRACT,
        "fixture_sha256": fixture_sha,
        "engine_results": engine_results,
        "verdicts_conform_to_decisions": True,
        "result": "passed",
    }
    if FAMILY == "prelude-control":
        receipt["profile_builds"] = [profile_builds[profile] for profile in PROFILES]
    else:
        receipt["engine_builds"] = engine_builds
        receipt["internal_accounting"] = [
            {
                "profile": profile,
                "path": _relative(output_dir / f"{profile}-internal-accounting.json"),
                "sha256": _sha_bytes(accounting_bytes[profile]),
            }
            for profile in PROFILES
        ]
        receipt["tier_artifacts"] = (
            [
                {
                    "tier": tier,
                    "image": _relative(output_dir / f"dialect-v2-lists-{tier}.l65m"),
                    "image_sha256": _sha_bytes(tier_images[tier]),
                    "manifest": _relative(
                        output_dir / f"dialect-v2-lists-{tier}.manifest.json"
                    ),
                    "manifest_sha256": _sha_bytes(
                        _canonical(measurements["dialect-v2"]["tier_manifests"][tier])
                    ),
                }
                for tier in ("core", "library")
            ]
            if FAMILY == "lists" else []
        )
    rendered.update(
        {
            "dialect-v1-inventory.json": inventory_bytes["dialect-v1"],
            "dialect-v2-inventory.json": inventory_bytes["dialect-v2"],
            "dialect-v1-manifest.json": manifest_bytes["dialect-v1"],
            "dialect-v2-manifest.json": manifest_bytes["dialect-v2"],
            "dialect-v1-profile.l65p": artifact_bytes["dialect-v1"],
            "dialect-v2-profile.l65p": artifact_bytes["dialect-v2"],
            "differential-receipt.json": _canonical(receipt),
        }
    )
    if FAMILY != "prelude-control":
        rendered.update(
            {
                f"{profile}-internal-accounting.json": accounting_bytes[profile]
                for profile in PROFILES
            }
        )
    if FAMILY == "lists":
        for tier in ("core", "library"):
            rendered[f"dialect-v2-lists-{tier}.l65m"] = tier_images[tier]
            rendered[f"dialect-v2-lists-{tier}.manifest.json"] = _canonical(
                measurements["dialect-v2"]["tier_manifests"][tier]
            )
    if set(rendered) != GENERATED_NAMES:
        raise EvidenceError("generated evidence inventory drift")
    del baseline_manifest_path, candidate_manifest_path
    return rendered


def write_evidence(rendered: dict[str, bytes], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in sorted(rendered):
        (output_dir / name).write_bytes(rendered[name])


def check_evidence(rendered: dict[str, bytes], evidence_dir: Path) -> None:
    actual_names = {
        path.name for path in evidence_dir.iterdir()
        if path.is_file() and not path.is_symlink()
    } if evidence_dir.is_dir() else set()
    if actual_names != GENERATED_NAMES:
        raise EvidenceError(
            f"evidence file coverage drift: missing={sorted(GENERATED_NAMES - actual_names)} "
            f"extra={sorted(actual_names - GENERATED_NAMES)}"
        )
    for name, expected in rendered.items():
        path = evidence_dir / name
        if path.read_bytes() != expected:
            raise EvidenceError(f"generated evidence drift: {name}")


def _synthetic_verdicts(directory: Path, fixture_path: Path) -> None:
    fixture = _load(fixture_path, "selftest fixture")
    cases = _fixture_cases(fixture)
    fixture_sha = _sha_file(fixture_path)
    for profile in PROFILES:
        for engine in ENGINES:
            verdict = {
                "format": "lisp65-dialect-v2-family-verdict-v1",
                "family": FAMILY,
                "profile": profile,
                "engine": engine,
                "fixture_sha256": fixture_sha,
                "provenance": {
                    "source_commit": None,
                    "binary_sha256": ("1" if profile == "dialect-v1" else "2") * 64,
                    "build_profile_sha256": ("3" if profile == "dialect-v1" else "4") * 64,
                    "preload_sha256": hashlib.sha256(
                        f"{profile}:{engine}".encode("ascii")
                    ).hexdigest(),
                },
                "cases": [
                    {
                        "id": case["id"],
                        "decision": case["migration_anchor"],
                        "verdict": "accept",
                        "result_sha256": hashlib.sha256(
                            case["observations"][profile][engine].encode("utf-8")
                        ).hexdigest(),
                    }
                    for case in cases
                ],
            }
            (directory / _verdict_name(profile, engine)).write_bytes(_canonical(verdict))


def selftest(contract_path: Path, fixture_path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix=f".{FAMILY}-evidence-selftest-", dir=ROOT) as raw:
        temp = Path(raw)
        verdicts = temp / "verdicts"
        evidence = temp / "evidence"
        verdicts.mkdir()
        _synthetic_verdicts(verdicts, fixture_path)
        rendered = render_evidence(contract_path, fixture_path, verdicts, evidence)
        write_evidence(rendered, evidence)
        check_evidence(
            render_evidence(contract_path, fixture_path, evidence, evidence), evidence
        )

        mutated_contract = _load(contract_path, "selftest migration contract")
        mutated_contract = deepcopy(mutated_contract)
        family_group = next(
            group for group in mutated_contract["classification"]["name_groups"]
            if group["family"] == FAMILY
        )
        family_group["disposition"] = "remove-v2"
        mutated_contract_path = temp / "migration-contract.json"
        mutated_contract_path.write_bytes(_canonical(mutated_contract))
        try:
            render_evidence(mutated_contract_path, fixture_path, verdicts, temp / "bad-contract")
        except EvidenceError:
            pass
        else:
            raise EvidenceError("selftest accepted classification/inventory drift")

        bad_verdict = verdicts / _verdict_name("dialect-v2", ENGINES[0])
        value = _load(bad_verdict, "selftest verdict")
        value["cases"][0]["result_sha256"] = "0" * 64
        bad_verdict.write_bytes(_canonical(value))
        try:
            render_evidence(contract_path, fixture_path, verdicts, temp / "bad")
        except EvidenceError:
            pass
        else:
            raise EvidenceError("selftest accepted a verdict observation drift")

        corrupted = evidence / "dialect-v2-inventory.json"
        corrupted.write_bytes(corrupted.read_bytes() + b" ")
        try:
            check_evidence(rendered, evidence)
        except EvidenceError:
            pass
        else:
            raise EvidenceError("selftest accepted generated evidence drift")
        mutations = 3
        if FAMILY != "prelude-control":
            corrupted.write_bytes(rendered[corrupted.name])
            accounting = evidence / "dialect-v2-internal-accounting.json"
            accounting.write_bytes(accounting.read_bytes() + b" ")
            try:
                check_evidence(rendered, evidence)
            except EvidenceError:
                mutations += 1
            else:
                raise EvidenceError("selftest accepted internal-accounting drift")
            accounting.write_bytes(rendered[accounting.name])
        if FAMILY == "lists":
            tier_manifest = evidence / "dialect-v2-lists-library.manifest.json"
            tier_manifest.write_bytes(tier_manifest.read_bytes() + b" ")
            try:
                check_evidence(rendered, evidence)
            except EvidenceError:
                mutations += 1
            else:
                raise EvidenceError("selftest accepted Lists tier-manifest drift")
    print(
        f"dialect-v2-family-evidence: SELFTEST PASS family={FAMILY} "
        f"mutations={mutations}"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", choices=sorted(FAMILY_CONFIGS), default="prelude-control")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--fixture", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate")
    generate.add_argument("--verdict-dir", type=Path)
    generate.add_argument("--output-dir", type=Path)
    check = subparsers.add_parser("check")
    check.add_argument("--evidence-dir", type=Path)
    check.add_argument("--verdict-dir", type=Path)
    subparsers.add_parser("selftest")
    args = parser.parse_args(argv)
    _configure(args.family)
    family_config = FAMILY_CONFIGS[FAMILY]
    contract = args.contract if args.contract.is_absolute() else ROOT / args.contract
    fixture_arg = args.fixture or family_config["fixture"]
    fixture = fixture_arg if fixture_arg.is_absolute() else ROOT / fixture_arg
    try:
        if args.command == "selftest":
            selftest(contract, fixture)
            return 0
        if args.command == "generate":
            verdict_arg = args.verdict_dir or family_config["verdicts"]
            output_arg = args.output_dir or family_config["evidence"]
            verdicts = verdict_arg if verdict_arg.is_absolute() else ROOT / verdict_arg
            output = output_arg if output_arg.is_absolute() else ROOT / output_arg
            rendered = render_evidence(contract, fixture, verdicts, output)
            write_evidence(rendered, output)
            receipt = json.loads(rendered["differential-receipt.json"])
            print(
                f"dialect-v2-family-evidence: GENERATED family={FAMILY} "
                f"loaded_delta={receipt['actual']['loaded_symbol_delta']} "
                f"namepool_delta={receipt['actual']['loaded_namepool_delta_bytes']}"
            )
            return 0
        evidence_arg = args.evidence_dir or family_config["evidence"]
        verdict_arg = args.verdict_dir or evidence_arg
        evidence = evidence_arg if evidence_arg.is_absolute() else ROOT / evidence_arg
        verdicts = verdict_arg if verdict_arg.is_absolute() else ROOT / verdict_arg
        rendered = render_evidence(contract, fixture, verdicts, evidence)
        check_evidence(rendered, evidence)
        print(
            f"dialect-v2-family-evidence: PASS family={FAMILY} files={len(GENERATED_NAMES)} "
            f"engines={len(ENGINES)}"
        )
        return 0
    except EvidenceError as exc:
        print(f"dialect-v2-family-evidence: FAIL family={FAMILY}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
