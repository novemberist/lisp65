#!/usr/bin/env python3
"""Build reproducible dialect-family L65M measurement artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

import bytecode_p0_stdlib as STDLIB


ROOT = Path(__file__).resolve().parents[2]
FAMILY_SOURCES = {
    "prelude-control": {
        "v1": (
            "lib/prelude-m1.lisp",
            "lib/stdlib-control.lisp",
            "lib/stdlib-places.lisp",
        ),
        "v2": ("lib/dialect-v2/prelude-control.lisp",),
    },
    "lists": {
        "v1": (
            "lib/prelude-m1.lisp",
            "lib/stdlib-lists.lisp",
            "lib/stdlib-sequences.lisp",
            "lib/stdlib-plists.lisp",
        ),
        "v2": (
            "lib/dialect-v2/lists-core.lisp",
            "lib/dialect-v2/lists-library.lisp",
        ),
    },
    "strings": {
        "v1": ("lib/stdlib-strings.lisp",),
        "v2": (
            "lib/dialect-v2/strings-core.lisp",
            "lib/dialect-v2/strings-library.lisp",
            "lib/dialect-v2/eval-runtime.lisp",
        ),
    },
    "system-runtime": {
        "v1": (
            "lib/m65-disk.lisp",
            "lib/runtime-core.lisp",
        ),
        "v2": (
            "lib/m65-disk.lisp",
            "lib/runtime-core.lisp",
            "lib/dialect-v2/system-format-library.lisp",
            "lib/dialect-v2/system-screen-library.lisp",
        ),
    },
}
FAMILY_NATIVE_PUBLIC = {
    "strings": {
        "dialect-v1": {
            "stringp", "string-length", "string-ref", "string->list",
            "list->string", "number->string",
        },
        "dialect-v2": {"stringp", "string-length", "string-ref"},
    },
}
LIST_TIER_DESCRIPTORS = {
    "core": "tests/bytecode/dialect-v2/lists/core-artifact.json",
    "library": "tests/bytecode/dialect-v2/lists/library-artifact.json",
}
LISP_SPECIAL_FORMS = {
    "and", "cond", "defun", "dolist", "dotimes", "function", "if", "lambda",
    "let", "let*", "or", "progn", "quote", "setq", "unless", "when",
}


class FamilyArtifactError(RuntimeError):
    pass


def _git_file(commit: str, relative: str) -> bytes:
    process = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise FamilyArtifactError(
            f"cannot read frozen source {commit}:{relative}: "
            f"{process.stderr.decode('utf-8', 'replace').strip()}"
        )
    return process.stdout


def _unique(items: list[str] | tuple[str, ...]) -> list[str]:
    return list(dict.fromkeys(items))


def _source_paths(
    profile: str,
    family: str,
    source_commit: str,
    v1_contract: dict[str, Any],
    directory: Path,
) -> tuple[list[Path], list[dict[str, str]]]:
    surface = next(
        (
            item for item in v1_contract["current_surfaces"]
            if item["id"] == "workbench-preload"
        ),
        None,
    )
    if surface is None:
        raise FamilyArtifactError("dialect-v1 contract lacks workbench-preload")
    if family not in FAMILY_SOURCES:
        raise FamilyArtifactError(f"unsupported family: {family}")
    relative_sources = _unique(
        list(surface["sources"]) + list(FAMILY_SOURCES[family]["v1"])
    )
    if profile == "dialect-v2":
        relative_sources.extend(FAMILY_SOURCES[family]["v2"])

    paths: list[Path] = []
    bindings: list[dict[str, str]] = []
    for relative in relative_sources:
        if profile == "dialect-v1":
            payload = _git_file(source_commit, relative)
            origin = f"git:{source_commit}:{relative}"
        else:
            source = ROOT / relative
            if source.is_symlink() or not source.is_file():
                raise FamilyArtifactError(f"candidate source is missing: {relative}")
            payload = source.read_bytes()
            origin = f"worktree:{relative}"
        target = directory / profile / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        paths.append(target)
        bindings.append(
            {
                "path": relative,
                "origin": origin,
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return paths, bindings


def _called_names(form: Any) -> set[str]:
    if not isinstance(form, list) or not form:
        return set()
    if form[0] == "quote":
        return set()
    if form[0] == "function":
        if len(form) == 2 and isinstance(form[1], str):
            return {form[1]}
        return set()
    if form[0] == "lambda":
        result: set[str] = set()
        for item in form[2:]:
            result.update(_called_names(item))
        return result
    if isinstance(form[0], str) and form[0] in {"let", "let*"}:
        result = set()
        if len(form) > 1 and isinstance(form[1], list):
            for binding in form[1]:
                if isinstance(binding, list):
                    for item in binding[1:]:
                        result.update(_called_names(item))
        for item in form[2:]:
            result.update(_called_names(item))
        return result
    result: set[str] = set()
    if isinstance(form[0], str):
        result.add(form[0])
    else:
        result.update(_called_names(form[0]))
    for item in form[1:]:
        result.update(_called_names(item))
    return result


def _internal_closure(names: set[str], forms: dict[str, Any]) -> set[str]:
    internal: set[str] = set()
    pending = list(names)
    seen: set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen or name not in forms:
            continue
        seen.add(name)
        form = forms[name]
        called_names: set[str] = set()
        for body in form[3:]:
            called_names.update(_called_names(body))
        for called in called_names:
            if called.startswith("%") and called in forms and called not in internal:
                internal.add(called)
                pending.append(called)
    return internal


def _list_tier_descriptor(tier: str) -> tuple[dict[str, Any], bytes]:
    relative = LIST_TIER_DESCRIPTORS[tier]
    path = ROOT / relative
    payload = path.read_bytes()
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise FamilyArtifactError(f"invalid Lists {tier} descriptor: {exc}") from exc
    keys = {"format", "profile", "family", "tier", "source", "provides", "requires"}
    if not isinstance(value, dict) or set(value) != keys:
        raise FamilyArtifactError(f"Lists {tier} descriptor keys drift")
    if (
        value["format"] != "lisp65-dialect-v2-family-tier-v1"
        or value["profile"] != "dialect-v2"
        or value["family"] != "lists"
        or value["tier"] != tier
    ):
        raise FamilyArtifactError(f"Lists {tier} descriptor identity drift")
    for key in ("provides", "requires"):
        names = value[key]
        if (
            not isinstance(names, list)
            or not all(isinstance(name, str) and name for name in names)
            or names != sorted(set(names))
        ):
            raise FamilyArtifactError(f"Lists {tier} descriptor {key} drift")
    if set(value["provides"]) & set(value["requires"]):
        raise FamilyArtifactError(f"Lists {tier} descriptor provides/requires overlap")
    if any(name.startswith("%") for name in value["requires"]):
        raise FamilyArtifactError(f"Lists {tier} descriptor requires a private name")
    return value, payload


def _build_list_tier(
    tier: str, sources: list[Path], output_dir: Path
) -> tuple[bytes, dict[str, Any]]:
    descriptor, descriptor_payload = _list_tier_descriptor(tier)
    source = next(
        (
            path for path in sources
            if path.as_posix().endswith("/" + descriptor["source"])
        ),
        None,
    )
    if source is None:
        raise FamilyArtifactError(f"Lists {tier} descriptor source is not staged")
    forms, defuns, macros = STDLIB._source_top_defs([str(source)])
    source_public = {name for name in forms if not name.startswith("%")}
    provides = set(descriptor["provides"])
    if source_public != provides:
        raise FamilyArtifactError(
            f"Lists {tier} descriptor/source public drift: "
            f"missing={sorted(source_public - provides)} "
            f"extra={sorted(provides - source_public)}"
        )
    internal = {name for name in forms if name.startswith("%")}
    compiled = provides | internal
    calls: set[str] = set()
    for form in forms.values():
        for body in form[3:]:
            calls.update(_called_names(body))
    external = calls - compiled - LISP_SPECIAL_FORMS
    requires = set(descriptor["requires"])
    if external != requires:
        raise FamilyArtifactError(
            f"Lists {tier} descriptor requires drift: "
            f"missing={sorted(external - requires)} extra={sorted(requires - external)}"
        )
    prefix = output_dir / f"dialect-v2-lists-{tier}"
    suite = {
        "format": "lisp65-bytecode-p0-disk-lib-suite-v1",
        "name": f"dialect-v2-lists-{tier}",
        "d81_name": "L2CORE" if tier == "core" else "L2LISTS",
        "provides": descriptor["provides"],
        "requires": descriptor["requires"],
        "allowed_external_calls": descriptor["requires"],
        "dependency_gate": True,
        "sources": [str(source)],
        "functions": sorted(compiled),
        "require_all_defuns": True,
        "strict_arity": True,
        "abi_profile": "dialect-v2",
        "max_call_args": 255,
        "cases": [{"name": "artifact-probe", "expr": "nil", "expect": "nil"}],
    }
    try:
        STDLIB.emit_artifacts(
            f"generated:dialect-v2:lists:{tier}", suite, str(prefix),
            artifact_role="disk-lib",
        )
    except Exception as exc:
        raise FamilyArtifactError(f"cannot build Lists {tier} tier: {exc}") from exc
    image = prefix.with_suffix(".ext.bin").read_bytes()
    raw_manifest = json.loads(
        prefix.with_suffix(".manifest.json").read_text(encoding="utf-8")
    )
    if (
        raw_manifest["provides"] != descriptor["provides"]
        or raw_manifest["requires"] != descriptor["requires"]
        or set(raw_manifest["functions"]) != compiled
        or not raw_manifest["strict_arity"]
    ):
        raise FamilyArtifactError(f"Lists {tier} emitted manifest drift")
    manifest = {
        "format": "lisp65-dialect-v2-family-tier-artifact-v1",
        "profile": "dialect-v2",
        "family": "lists",
        "tier": tier,
        "descriptor": LIST_TIER_DESCRIPTORS[tier],
        "descriptor_sha256": hashlib.sha256(descriptor_payload).hexdigest(),
        "source": descriptor["source"],
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "provides": descriptor["provides"],
        "requires": descriptor["requires"],
        "private_definitions": sorted(internal),
        "image_sha256": hashlib.sha256(image).hexdigest(),
        "image_bytes": len(image),
        "directory_entries": len(raw_manifest["entries"]),
        "code_bytes": raw_manifest["code_bytes"],
        "strict_arity": True,
    }
    return image, manifest


def _name_bytes(names: set[str] | list[str]) -> int:
    return sum(len(name) + 1 for name in names)


def _artifact_accounting(
    public: set[str], native_public: set[str], internal: set[str],
    manifest: dict[str, Any], blob: bytes, *, require_internal_closure: bool
) -> dict[str, Any]:
    entry_names = {entry["name"] for entry in manifest["entries"]}
    percent = {name for name in entry_names if name.startswith("%")}
    generated = entry_names - public - percent
    symbol_names = set(manifest["cost"]["symbol_names"])
    referenced = symbol_names - entry_names
    unresolved_percent = sorted(name for name in referenced if name.startswith("%"))
    if require_internal_closure and unresolved_percent:
        raise FamilyArtifactError(
            f"internal definitions escaped the L65M image: {unresolved_percent}"
        )
    arity = []
    for entry in manifest["entries"]:
        offset = entry["blob_offset"]
        if offset + 4 > len(blob) or blob[offset] != 0xB5:
            raise FamilyArtifactError(f"cannot decode CodeObject header: {entry['name']}")
        flags = blob[offset + 3]
        arity.append(
            {
                "name": entry["name"],
                "class": (
                    "public" if entry["name"] in public
                    else "percent-internal" if entry["name"].startswith("%")
                    else "generated-internal"
                ),
                "nargs": blob[offset + 1],
                "nlocals": blob[offset + 2],
                "flags": flags,
                "strict_arity": bool(flags & 2),
                "optional_count": flags >> 2,
                "rest": bool(flags & 1),
            }
        )
    return {
        "public_definitions": sorted(public),
        "native_public_bindings": sorted(native_public),
        "percent_definitions": sorted(percent),
        "declared_percent_definitions": sorted(internal),
        "generated_definitions": sorted(generated),
        "referenced_only_names": sorted(referenced),
        "directory_entries": {
            "public": len(public & entry_names),
            "native_public_outside_l65m": len(native_public),
            "percent_internal": len(percent),
            "generated_internal": len(generated),
            "total": len(entry_names),
        },
        "namepool_bytes": {
            "public_definitions": _name_bytes(public & entry_names),
            "native_public_outside_l65m": _name_bytes(native_public),
            "percent_definitions": _name_bytes(percent),
            "generated_definitions": _name_bytes(generated),
            "referenced_only": _name_bytes(referenced),
            "total_unique_names": _name_bytes(symbol_names),
        },
        "arity": sorted(arity, key=lambda item: item["name"]),
    }


def _validate_lists_arity(
    profile: str, role: str, accounting: dict[str, Any]
) -> None:
    expected = {
        "dialect-v1": {
            "member": (2, 0x00), "assoc": (2, 0x00), "find": (2, 0x00),
            "count": (2, 0x00), "position": (2, 0x00),
        },
        "dialect-v2": {
            "member": (3, 0x06), "assoc": (3, 0x06), "find": (2, 0x02),
            "filter": (2, 0x02), "count": (2, 0x02), "position": (2, 0x02),
        },
    }[profile]
    if role == "boot":
        expected = {
            name: shape for name, shape in expected.items()
            if name not in {"count", "position"}
        }
    headers = {item["name"]: (item["nargs"], item["flags"]) for item in accounting["arity"]}
    for name, shape in expected.items():
        if headers.get(name) != shape:
            raise FamilyArtifactError(
                f"{profile}/{role}/{name} arity drift: {headers.get(name)} != {shape}"
            )


def _validate_strings_arity(
    profile: str, role: str, accounting: dict[str, Any]
) -> None:
    if profile != "dialect-v2":
        return
    expected = {
        "string-append": (0, 0x03),
        "substring": (3, 0x06),
        "search": (2, 0x02),
        "string-equal": (2, 0x02),
        "string-trim": (2, 0x02),
        "char": (2, 0x02),
        "char->string": (1, 0x02),
    }
    headers = {item["name"]: (item["nargs"], item["flags"]) for item in accounting["arity"]}
    for name, shape in expected.items():
        if name in accounting["public_definitions"] and headers.get(name) != shape:
            raise FamilyArtifactError(
                f"{profile}/{role}/{name} arity drift: {headers.get(name)} != {shape}"
            )


def _build_one(
    profile: str,
    family: str,
    role: str,
    names: set[str],
    sources: list[Path],
    output_dir: Path,
    include_internal: bool,
) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    prefix = output_dir / f"{profile}-{role}"
    forms, defuns, macros = STDLIB._source_top_defs([str(path) for path in sources])
    native_declared = FAMILY_NATIVE_PUBLIC.get(family, {}).get(profile, set())
    source_public = (names & set(forms)) - native_declared
    native_public = names - source_public
    internal = _internal_closure(source_public, forms) if include_internal else set()
    compiled = source_public | internal
    external_names = (set(defuns) | set(macros)) - compiled
    if family == "system-runtime":
        calls: set[str] = set()
        for name in compiled:
            for body in forms[name][3:]:
                calls.update(_called_names(body))
        external_names |= calls - compiled - LISP_SPECIAL_FORMS
    external = sorted(external_names)
    block = {
        "prelude-control": "ap84", "lists": "ap85", "strings": "ap86",
        "system-runtime": "r2-system-runtime",
    }[family]
    suite = {
        "format": "lisp65-bytecode-p0-disk-lib-suite-v1",
        "name": f"{block}-{profile}-{role}",
        "d81_name": "R2SYS" if family == "system-runtime" else block.upper(),
        "provides": sorted(source_public),
        "requires": external,
        "allowed_external_calls": external,
        "sources": [str(path) for path in sources],
        "functions": sorted(compiled),
        "strict_arity": profile == "dialect-v2",
        "abi_profile": profile,
        "max_call_args": 255,
        "cases": [{"name": "artifact-probe", "expr": "nil", "expect": "nil"}],
    }
    try:
        STDLIB.emit_artifacts(
            f"generated:{profile}:{role}",
            suite,
            str(prefix),
            artifact_role="disk-lib",
        )
    except Exception as exc:
        raise FamilyArtifactError(
            f"cannot build {profile}/{role} L65M artifact: {exc}"
        ) from exc
    image = prefix.with_suffix(".ext.bin").read_bytes()
    manifest = json.loads(prefix.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    configured = set(manifest["functions"])
    if configured != compiled:
        raise FamilyArtifactError(
            f"{profile}/{role} compiled surface drift: "
            f"missing={sorted(compiled - configured)} extra={sorted(configured - compiled)}"
        )
    strict_flags = {
        entry["name"]: bool(entry["code_flags"] & 2)
        for entry in manifest["entries"]
        if entry["name"] in compiled
    }
    expected_strict = profile == "dialect-v2"
    if set(strict_flags) != compiled or any(
        value != expected_strict for value in strict_flags.values()
    ):
        raise FamilyArtifactError(f"{profile}/{role} strict-arity flag drift")
    blob = prefix.with_suffix(".blob.bin").read_bytes()
    accounting = _artifact_accounting(
        source_public, native_public, internal, manifest, blob,
        require_internal_closure=include_internal,
    )
    if family == "lists":
        _validate_lists_arity(profile, role, accounting)
    elif family == "strings":
        _validate_strings_arity(profile, role, accounting)
    return image, manifest, accounting


def build_profile(
    profile: str,
    sets: dict[str, set[str]],
    source_commit: str,
    v1_contract: dict[str, Any],
    directory: Path,
    family: str = "prelude-control",
) -> tuple[dict[str, bytes], dict[str, Any]]:
    if profile not in {"dialect-v1", "dialect-v2"}:
        raise FamilyArtifactError(f"unsupported profile: {profile}")
    sources, bindings = _source_paths(
        profile, family, source_commit, v1_contract, directory / "sources"
    )
    images: dict[str, bytes] = {}
    manifests: dict[str, Any] = {}
    accounting: dict[str, Any] = {}
    for role in ("loaded", "boot"):
        image, manifest, role_accounting = _build_one(
            profile, family, role, sets[role], sources, directory / "artifacts",
            include_internal=family in {"lists", "strings"},
        )
        images[role] = image
        manifests[role] = manifest
        accounting[role] = role_accounting

    tier_manifests: dict[str, Any] = {}
    if family == "lists" and profile == "dialect-v2":
        for tier in ("core", "library"):
            image, tier_manifest = _build_list_tier(
                tier, sources, directory / "tier-artifacts"
            )
            images[f"tier-{tier}"] = image
            tier_manifests[tier] = tier_manifest

    loaded_public = (
        set(sets["loaded"]) if family in {"lists", "strings", "system-runtime"}
        else set(manifests["loaded"]["functions"])
    )
    boot_public = (
        set(sets["boot"]) if family in {"lists", "strings", "system-runtime"}
        else set(manifests["boot"]["functions"])
    )
    loaded_entries = [entry["name"] for entry in manifests["loaded"]["entries"]]
    boot_entries = [entry["name"] for entry in manifests["boot"]["entries"]]
    result = {
        "source_commit": source_commit if profile == "dialect-v1" else None,
        "source_bindings": bindings,
        "loaded_symbols": sorted(loaded_public),
        "boot_symbols": sorted(boot_public),
        "directory_entries": (
            sorted(sets["directory"])
            if family == "system-runtime"
            else sorted(loaded_public)
            if family in {"lists", "strings"}
            else sorted(loaded_entries)
        ),
        "boot_directory_entries": (
            sorted(boot_public)
            if family in {"lists", "strings", "system-runtime"}
            else sorted(boot_entries)
        ),
        "loaded_symbol_names": manifests["loaded"]["cost"]["symbol_names"],
        "boot_symbol_names": manifests["boot"]["cost"]["symbol_names"],
        "loaded_image_bytes": len(images["loaded"]),
        "boot_image_bytes": len(images["boot"]),
        "loaded_image_sha256": hashlib.sha256(images["loaded"]).hexdigest(),
        "boot_image_sha256": hashlib.sha256(images["boot"]).hexdigest(),
        "strict_arity": profile == "dialect-v2",
        "internal_accounting": accounting,
        "tier_manifests": tier_manifests,
    }
    return images, result
