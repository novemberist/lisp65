#!/usr/bin/env python3
"""Gate public resident-bytecode claims across contracts, docs, and product."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "config/v11-surface-delivery-parity.json"
CONTRACT_KEYS = {
    "format", "version", "status", "profile", "surface", "dialect_contract",
    "language_reference", "native_registry", "workbench_profile",
    "resident_manifest", "library_manifests", "artifact_closure",
    "profile_exclusions", "claims",
}


class ParityError(RuntimeError):
    pass


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ParityError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ParityError(f"{label} must be an object")
    return value


def repo_path(value: str) -> Path:
    path = (ROOT / value).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ParityError(f"path escapes repository: {value}") from exc
    return path


def defun_names(text: str) -> set[str]:
    return set(re.findall(r"\(defun\s+([^\s()]+)", text))


def reference_public_names(text: str) -> set[str]:
    start_marker = "The current Wave 1 candidate surface includes:"
    end_marker = "The complete native visibility"
    if text.count(start_marker) != 1 or text.count(end_marker) != 1:
        raise ParityError("language-reference public-surface section drift")
    section = text.split(start_marker, 1)[1].split(end_marker, 1)[0].strip().split("\n\n", 1)[0]
    return set(re.findall(r"`([^`]+)`", section))


def verify_authority(claim: dict[str, Any]) -> None:
    name = claim["name"]
    authority = claim.get("authority")
    if not isinstance(authority, dict) or not isinstance(authority.get("path"), str):
        raise ParityError(f"claim {name} has no authority")
    value = load(repo_path(authority["path"]), f"authority for {name}")
    if authority.get("kind") == "capability-surface":
        public = value.get("surface", {}).get("public_names", [])
        if name not in public:
            raise ParityError(f"authority does not publish {name}")
        resolution = authority.get("resolution")
        if not isinstance(resolution, dict) or set(resolution) != {"path", "decision_id", "status"}:
            raise ParityError(f"capability authority for {name} has no exact resolution binding")
        migration = load(repo_path(resolution["path"]), f"resolution for {name}")
        decisions = migration.get("open_decisions", [])
        matches = [
            row for row in decisions
            if isinstance(row, dict) and row.get("id") == resolution["decision_id"]
        ]
        if len(matches) != 1 or matches[0].get("status") != resolution["status"]:
            raise ParityError(f"capability authority for {name} is not resolved")
    elif authority.get("kind") == "migration-new-name":
        rows = value.get("classification", {}).get("new_names", [])
        matches = [row for row in rows if isinstance(row, dict) and row.get("name") == name]
        if len(matches) != 1:
            raise ParityError(f"migration authority for {name} is not unique")
        row = matches[0]
        for key in ("target_role", "target_delivery", "target_library"):
            if row.get(key) != authority.get(key):
                raise ParityError(f"migration authority for {name} drifts at {key}")
    elif authority.get("kind") == "owner-feature-contract":
        if authority.get("status") != value.get("status"):
            raise ParityError(f"owner feature authority for {name} status drift")
        feature = value.get("features", {}).get(name)
        if not isinstance(feature, dict):
            raise ParityError(f"owner feature authority does not define {name}")
    else:
        raise ParityError(f"claim {name} has unknown authority kind")

    implementation = claim.get("implementation")
    if implementation is not None:
        if not isinstance(implementation, dict) or not isinstance(implementation.get("path"), str):
            raise ParityError(f"claim {name} has invalid implementation binding")
        required = implementation.get("required_defuns")
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            raise ParityError(f"claim {name} has invalid required_defuns")
        present = defun_names(repo_path(implementation["path"]).read_text(encoding="utf-8"))
        missing = sorted(set(required) - present)
        if missing:
            raise ParityError(f"implementation for {name} misses {missing}")


def verify_values(
    contract: dict[str, Any], surface: dict[str, Any], dialect: dict[str, Any],
    manifest: dict[str, Any], library_manifests: list[dict[str, Any]],
    reference: str, registry: dict[str, Any], closure: dict[str, Any],
    workbench_profile: str, *, authorities: bool = True,
) -> list[str]:
    if (
        contract.get("format") != "lisp65-v11-surface-delivery-parity-v1"
        or contract.get("version") != 1
        or contract.get("status") != "active"
        or contract.get("profile") != "dialect-v2"
        or set(contract) != CONTRACT_KEYS
    ):
        raise ParityError("contract format/profile drift")
    claims = contract.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ParityError("claims must be a non-empty list")
    names = [claim.get("name") for claim in claims if isinstance(claim, dict)]
    if names != sorted(set(names)) or len(names) != len(claims):
        raise ParityError("claim names must be sorted and unique")
    definitions = surface.get("definitions")
    public_names = dialect.get("public_names")
    entries = manifest.get("entries")
    registry_entries = registry.get("entries")
    if (
        not isinstance(definitions, list)
        or not isinstance(public_names, list)
        or not isinstance(entries, list)
        or not isinstance(registry_entries, list)
    ):
        raise ParityError("surface, dialect, registry, or manifest schema drift")
    reference_names = reference_public_names(reference)
    delivered_names = {
        row.get("name") for row in entries if isinstance(row, dict)
    }
    for library in library_manifests:
        library_entries = library.get("entries")
        if not isinstance(library_entries, list):
            raise ParityError("library manifest schema drift")
        delivered_names.update(
            row.get("name") for row in library_entries if isinstance(row, dict)
        )
    registry_names: set[str] = set()
    for key in ("entries", "intrinsic_aliases", "restricted_primitives"):
        rows = registry.get(key)
        if not isinstance(rows, list):
            raise ParityError(f"native registry {key} schema drift")
        registry_names.update(row.get("name") for row in rows if isinstance(row, dict))
    restricted_names = {
        row.get("name") for row in registry["restricted_primitives"]
        if isinstance(row, dict)
    }
    excluded_names = {
        row.get("name") for row in contract["profile_exclusions"]
        if isinstance(row, dict)
    }
    implemented = closure.get("implemented_bindings")
    if not isinstance(implemented, dict) or not isinstance(implemented.get("native-service"), list):
        raise ParityError("artifact closure native-service binding drift")
    native_service_names = {
        row.get("name") for row in implemented["native-service"]
        if isinstance(row, dict)
    }
    known_names = (
        delivered_names | native_service_names
        | (registry_names - restricted_names - excluded_names)
    )
    missing_reference = sorted(reference_names - known_names)
    if missing_reference:
        raise ParityError(f"language reference names have no surface/registry/library delivery: {missing_reference}")
    for claim in claims:
        name = claim["name"]
        kind = claim.get("kind")
        matches = [
            row for row in definitions
            if isinstance(row, dict) and row.get("name") == name
            and row.get("kind") == kind and row.get("visibility") == "public"
        ]
        if len(matches) != 1:
            raise ParityError(f"surface does not publish exactly one {kind} {name}")
        if public_names.count(name) != 1:
            raise ParityError(f"dialect contract does not publish exactly one {name}")
        manifest_matches = [
            row for row in entries
            if isinstance(row, dict) and row.get("name") == name and row.get("kind") == kind
        ]
        if len(manifest_matches) != 1:
            raise ParityError(f"resident manifest does not deliver exactly one {name}")
        if name not in reference_names:
            raise ParityError(f"language reference does not document {name}")
        if authorities:
            verify_authority(claim)

    exclusions = contract.get("profile_exclusions")
    if not isinstance(exclusions, list) or not exclusions:
        raise ParityError("profile_exclusions must be a non-empty list")
    exclusion_names = [row.get("name") for row in exclusions if isinstance(row, dict)]
    if exclusion_names != sorted(set(exclusion_names)) or len(exclusion_names) != len(exclusions):
        raise ParityError("profile exclusion names must be sorted and unique")
    manifest_names = {
        row.get("name") for row in entries if isinstance(row, dict)
    }
    for row in exclusions:
        name = row["name"]
        kind = row.get("kind")
        value = row.get("value")
        required_define = row.get("required_define")
        fallback = row.get("fallback_resident_name")
        reason = row.get("reason")
        if not all(isinstance(item, str) and item for item in (
            name, kind, required_define, fallback, reason,
        )) or not isinstance(value, int):
            raise ParityError(f"profile exclusion {name} has invalid fields")
        surface_matches = [
            item for item in definitions
            if isinstance(item, dict) and item.get("name") == name
            and item.get("visibility") == "public"
        ]
        if len(surface_matches) != 1 or public_names.count(name) != 1:
            raise ParityError(f"profile exclusion {name} is not dialect-public")
        registry_matches = [
            item for item in registry_entries
            if isinstance(item, dict) and item.get("name") == name
            and item.get("kind") == kind and item.get("value") == value
        ]
        if len(registry_matches) != 1:
            raise ParityError(f"profile exclusion {name} is not uniquely registry-bound")
        if name in manifest_names:
            raise ParityError(f"profile exclusion {name} leaked into resident manifest")
        if re.search(rf"(?:^|\s)-D{re.escape(required_define)}(?:\s|$)", workbench_profile):
            raise ParityError(f"profile exclusion {name} is enabled by product define")
        if fallback not in manifest_names:
            raise ParityError(f"profile exclusion {name} misses resident fallback {fallback}")
    return sorted(set(names) | reference_names)


def selftest() -> None:
    claims = [
        {"name": "eval", "kind": "function"},
        {"name": "filter", "kind": "function"},
    ]
    contract = {
        "format": "lisp65-v11-surface-delivery-parity-v1", "version": 1,
        "status": "active", "profile": "dialect-v2", "surface": "surface",
        "dialect_contract": "dialect", "language_reference": "reference",
        "native_registry": "registry", "workbench_profile": "profile",
        "resident_manifest": "manifest", "library_manifests": ["library"],
        "artifact_closure": "closure", "claims": claims,
        "profile_exclusions": [{
            "name": "screen-write-string", "kind": "callprim", "value": 12,
            "required_define": "LISP65_SCREEN_WRITE_STRING",
            "fallback_resident_name": "screen-bulk-p", "reason": "profile excluded",
        }],
    }
    surface = {"definitions": [
        {"name": name, "kind": "function", "visibility": "public"} for name in ("eval", "filter")
    ] + [{"name": "screen-write-string", "kind": "primitive", "visibility": "public"}]}
    dialect = {"public_names": ["eval", "filter", "screen-write-string"]}
    manifest = {"entries": [
        {"name": "eval", "kind": "function"}, {"name": "filter", "kind": "function"},
        {"name": "screen-bulk-p", "kind": "function"},
    ]}
    registry = {"entries": [
        {"name": "screen-write-string", "kind": "callprim", "value": 12},
    ], "intrinsic_aliases": [], "restricted_primitives": []}
    closure = {"implemented_bindings": {"native-service": []}}
    workbench_profile = "WORKBENCH_DEFINES := -DLISP65_VM_SCREEN_PRIMS\n"
    reference = (
        "The current Wave 1 candidate surface includes:\n\n- symbols: `eval`, `filter`.\n\n"
        "The complete native visibility follows.\n"
    )
    verify_values(
        contract, surface, dialect, manifest, [], reference, registry, closure,
        workbench_profile, authorities=False,
    )
    for label in ("surface", "dialect", "manifest", "reference", "registry", "profile", "reverse"):
        c, s, d, m, n = map(copy.deepcopy, (contract, surface, dialect, manifest, registry))
        r = reference
        p = workbench_profile
        if label == "surface": s["definitions"].pop()
        elif label == "dialect": d["public_names"].pop()
        elif label == "manifest": m["entries"].pop()
        elif label == "reference": r = r.replace(", `filter`", "")
        elif label == "registry": n["entries"].pop()
        elif label == "profile": p += "WORKBENCH_DEFINES += -DLISP65_SCREEN_WRITE_STRING\n"
        else: r = r.replace("`eval`", "`ghost-function`")
        try:
            verify_values(c, s, d, m, [], r, n, closure, p, authorities=False)
        except ParityError:
            continue
        raise ParityError(f"selftest mutation accepted: {label}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            selftest()
            print("v11-surface-delivery-parity: SELFTEST PASS mutations=7")
            return 0
        contract = load(args.contract, "parity contract")
        names = verify_values(
            contract,
            load(repo_path(contract["surface"]), "surface"),
            load(repo_path(contract["dialect_contract"]), "dialect contract"),
            load(repo_path(contract["resident_manifest"]), "resident manifest"),
            [load(repo_path(path), "library manifest") for path in contract["library_manifests"]],
            repo_path(contract["language_reference"]).read_text(encoding="utf-8"),
            load(repo_path(contract["native_registry"]), "native registry"),
            load(repo_path(contract["artifact_closure"]), "artifact closure"),
            repo_path(contract["workbench_profile"]).read_text(encoding="utf-8"),
        )
    except (KeyError, OSError, UnicodeError, ParityError) as exc:
        print(f"v11-surface-delivery-parity: FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"v11-surface-delivery-parity: PASS bound_names={len(names)} names={','.join(names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
