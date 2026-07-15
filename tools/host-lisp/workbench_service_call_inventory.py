#!/usr/bin/env python3
"""Inventory unresolved Workbench bytecode calls before carrier removal.

This is a build-time/link-time audit.  It deliberately does not define a
runtime service registry or a function-pointer dispatch path.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST_TOOLS = ROOT / "tools" / "host-lisp"
if str(HOST_TOOLS) not in sys.path:
    sys.path.insert(0, str(HOST_TOOLS))

import bytecode_p0 as B  # noqa: E402
import bytecode_abi_ledger as ABI  # noqa: E402


DEFAULT_CONTRACT = ROOT / "config" / "workbench-native-service-registry.json"
FORMAT = "lisp65-workbench-native-service-registry-v1"
CLOSURE_FORMAT = "lisp65-v2-workbench-artifact-closure-v1"
REPORT_FORMAT = "lisp65-workbench-service-call-inventory-v1"
TOP_KEYS = {
    "format", "version", "abi_ledger", "staging_closure", "policies",
    "staging_only_targets", "staging_retired_targets", "artifacts",
    "current_misses",
}
CLOSURE_TOP_KEYS = {
    "format", "version", "abi_ledger", "target_abi_profile", "policies",
    "target_counts", "artifacts", "classifications", "implemented_bindings",
}
ARTIFACT_KEYS = {
    "id", "manifest", "manifest_format", "artifact_role", "name", "suite",
    "abi_profile", "visible_artifacts",
}
STAGING_ARTIFACT_KEYS = ARTIFACT_KEYS | {"source_suite"}
MISS_KEYS = {
    "name", "classification", "owner", "current_lowering", "target_lowering",
    "expected_calls",
}
POLICIES = {
    "current_mode": "exact-allowlist",
    "zero_miss_mode": "no-unresolved-call-or-tailcall",
    "new_miss": "reject",
    "binding": "static-build-time",
    "runtime_function_pointer_registry": "forbidden",
}
CLASSIFICATIONS = {"native-service", "intentional-error-sentinel"}
CLOSURE_POLICIES = {
    "artifact_set": "exact-four",
    "classification": "dense-exact-partition",
    "new_classification": "reject",
    "tombstone_callprim": "reject",
    "unresolved_call_or_tailcall": "reject",
    "runtime_function_pointer_registry": "forbidden",
}
CLOSURE_CLASS_COUNTS = {"callprim": 4, "native-service": 14, "error-service": 11}
CLOSURE_TOTAL = sum(CLOSURE_CLASS_COUNTS.values())
CLOSURE_BINDING_IDS = {
    "native-service": [*range(30, 34), *range(35, 40), *range(41, 46)],
    "error-service": list(range(46, 57)),
}
CLOSURE_ARTIFACT_IDS = ["resident", "ide", "idex", "m65d"]


class InventoryError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InventoryError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise InventoryError(f"must be a regular non-symlink file: {path}")
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except InventoryError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InventoryError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise InventoryError(f"JSON root must be an object: {path}")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InventoryError(f"{label} must be an object")
    missing = sorted(keys - set(value))
    unknown = sorted(set(value) - keys)
    if missing or unknown:
        raise InventoryError(f"{label} keys drift: missing={missing} unknown={unknown}")
    return value


def _relpath(root: Path, raw: Any, label: str) -> Path:
    if not isinstance(raw, str) or not raw or Path(raw).is_absolute():
        raise InventoryError(f"{label} must be a non-empty project-relative path")
    path = (root / raw).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise InventoryError(f"{label} escapes project root: {raw}") from exc
    if path.is_symlink() or not path.is_file():
        raise InventoryError(f"{label} must resolve to a regular non-symlink file: {raw}")
    return path


def validate_contract(value: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    _exact(value, TOP_KEYS, "contract")
    if value["format"] != FORMAT or value["version"] != 1:
        raise InventoryError("contract format/version drift")
    if value["policies"] != POLICIES:
        raise InventoryError("contract policies drift")
    if not isinstance(value["abi_ledger"], str) or not value["abi_ledger"]:
        raise InventoryError("abi_ledger must be a path")
    if not isinstance(value["staging_closure"], str) or not value["staging_closure"]:
        raise InventoryError("staging_closure must be a path")
    if value["staging_only_targets"] != ["%lcc-error-invalid-parameter-list"]:
        raise InventoryError("staging_only_targets drift")
    retired = value["staging_retired_targets"]
    if (
        not isinstance(retired, list)
        or retired != sorted(set(retired))
        or any(not isinstance(name, str) or not name for name in retired)
    ):
        raise InventoryError("staging_retired_targets must be sorted unique names")
    artifacts = value["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        raise InventoryError("artifacts must be a non-empty list")
    artifact_ids: list[str] = []
    for index, raw in enumerate(artifacts):
        item = _exact(raw, ARTIFACT_KEYS, f"artifacts[{index}]")
        if not isinstance(item["id"], str) or not item["id"]:
            raise InventoryError(f"artifacts[{index}].id is invalid")
        artifact_ids.append(item["id"])
        for key in ("manifest", "manifest_format", "artifact_role", "suite", "abi_profile"):
            if not isinstance(item[key], str) or not item[key]:
                raise InventoryError(f"artifacts[{index}].{key} is invalid")
        if item["name"] is not None and (not isinstance(item["name"], str) or not item["name"]):
            raise InventoryError(f"artifacts[{index}].name is invalid")
        if not isinstance(item["visible_artifacts"], list):
            raise InventoryError(f"artifacts[{index}].visible_artifacts must be a list")
    if artifact_ids != list(dict.fromkeys(artifact_ids)):
        raise InventoryError("artifact ids must be unique")
    known = set(artifact_ids)
    for index, item in enumerate(artifacts):
        visible = item["visible_artifacts"]
        if visible != list(dict.fromkeys(visible)) or not set(visible) <= known or item["id"] not in visible:
            raise InventoryError(f"artifacts[{index}].visible_artifacts is invalid")

    misses = value["current_misses"]
    if not isinstance(misses, list):
        raise InventoryError("current_misses must be a list")
    by_name: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for index, raw in enumerate(misses):
        item = _exact(raw, MISS_KEYS, f"current_misses[{index}]")
        name = item["name"]
        if not isinstance(name, str) or not name or name in by_name:
            raise InventoryError(f"current_misses[{index}].name is invalid or duplicate")
        if item["classification"] not in CLASSIFICATIONS:
            raise InventoryError(f"current_misses[{index}].classification is invalid")
        if item["current_lowering"] != "op-call-carrier":
            raise InventoryError(f"current_misses[{index}].current_lowering must be op-call-carrier")
        if not isinstance(item["owner"], str) or not item["owner"]:
            raise InventoryError(f"current_misses[{index}].owner is invalid")
        if not isinstance(item["target_lowering"], str) or not item["target_lowering"]:
            raise InventoryError(f"current_misses[{index}].target_lowering is invalid")
        calls = item["expected_calls"]
        if not isinstance(calls, dict) or not calls or not set(calls) <= known:
            raise InventoryError(f"current_misses[{index}].expected_calls is invalid")
        if any(type(count) is not int or count <= 0 for count in calls.values()):
            raise InventoryError(f"current_misses[{index}].expected_calls counts must be positive integers")
        order.append(name)
        by_name[name] = item
    if order != sorted(order):
        raise InventoryError("current_misses must be sorted by name")
    if not set(value["staging_retired_targets"]) <= set(by_name):
        raise InventoryError("staging_retired_targets must name current targets")
    return artifacts, by_name


def validate_closure(
    value: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, set[str]], dict[str, set[str]]]:
    _exact(value, CLOSURE_TOP_KEYS, "staging closure")
    if value["format"] != CLOSURE_FORMAT or value["version"] != 1:
        raise InventoryError("staging closure format/version drift")
    if value["target_abi_profile"] != "dialect-v2":
        raise InventoryError("staging closure must target dialect-v2")
    if not isinstance(value["abi_ledger"], str) or not value["abi_ledger"]:
        raise InventoryError("staging closure abi_ledger must be a path")
    if value["policies"] != CLOSURE_POLICIES:
        raise InventoryError("staging closure policies drift")
    if value["target_counts"] != {**CLOSURE_CLASS_COUNTS, "total": CLOSURE_TOTAL}:
        raise InventoryError("staging closure target counts drift")

    artifacts = value["artifacts"]
    if not isinstance(artifacts, list) or len(artifacts) != 4:
        raise InventoryError("staging closure must contain exactly four artifacts")
    artifact_ids: list[str] = []
    for index, raw in enumerate(artifacts):
        item = _exact(raw, STAGING_ARTIFACT_KEYS, f"staging artifacts[{index}]")
        artifact_ids.append(item.get("id"))
        for key in (
            "id", "manifest", "manifest_format", "artifact_role", "source_suite",
            "suite", "abi_profile",
        ):
            if not isinstance(item.get(key), str) or not item[key]:
                raise InventoryError(f"staging artifacts[{index}].{key} is invalid")
        if item["abi_profile"] != "dialect-v2":
            raise InventoryError(f"staging artifacts[{index}] is not dialect-v2")
        if item["name"] is not None and (not isinstance(item["name"], str) or not item["name"]):
            raise InventoryError(f"staging artifacts[{index}].name is invalid")
        visible = item["visible_artifacts"]
        if not isinstance(visible, list) or visible != CLOSURE_ARTIFACT_IDS:
            raise InventoryError(f"staging artifacts[{index}].visible_artifacts drift")
    if artifact_ids != CLOSURE_ARTIFACT_IDS:
        raise InventoryError("staging artifact ids/order drift")

    raw_classes = _exact(
        value["classifications"], set(CLOSURE_CLASS_COUNTS), "staging classifications"
    )
    classes: dict[str, set[str]] = {}
    seen: set[str] = set()
    for class_name, expected_count in CLOSURE_CLASS_COUNTS.items():
        names = raw_classes[class_name]
        if (
            not isinstance(names, list)
            or names != sorted(names)
            or len(names) != expected_count
            or len(names) != len(set(names))
            or any(not isinstance(name, str) or not name for name in names)
        ):
            raise InventoryError(
                f"staging classification {class_name} must pin {expected_count} sorted unique names"
            )
        overlap = seen & set(names)
        if overlap:
            raise InventoryError(f"staging classifications overlap: {sorted(overlap)}")
        classes[class_name] = set(names)
        seen.update(names)
    expected_total = sum(CLOSURE_CLASS_COUNTS.values())
    if len(seen) != expected_total:
        raise InventoryError(
            f"staging classifications must form a dense {expected_total}-target partition"
        )

    raw_bindings = _exact(
        value["implemented_bindings"], {"native-service", "error-service"},
        "staging implemented_bindings",
    )
    bindings: dict[str, set[str]] = {}
    for class_name in ("native-service", "error-service"):
        entries = raw_bindings[class_name]
        if not isinstance(entries, list):
            raise InventoryError(f"implemented {class_name} bindings must be a list")
        names: list[str] = []
        for index, raw in enumerate(entries):
            item = _exact(raw, {"name", "id"}, f"implemented {class_name}[{index}]")
            if item["id"] != CLOSURE_BINDING_IDS[class_name][index] or not isinstance(item["name"], str):
                raise InventoryError(f"implemented {class_name} binding ID/order drift")
            names.append(item["name"])
        if names != sorted(set(names)):
            raise InventoryError(f"implemented {class_name} bindings must be sorted unique names")
        if not set(names) <= classes[class_name]:
            raise InventoryError(f"implemented {class_name} binding is not classified")
        bindings[class_name] = set(names)
    return artifacts, classes, bindings


def _require_registry_closure_alignment(
    registry: dict[str, Any], closure: dict[str, Any]
) -> None:
    if registry["abi_ledger"] != closure["abi_ledger"]:
        raise InventoryError("registry and staging closure ABI ledgers differ")
    _, current = validate_contract(registry)
    _, classes, _ = validate_closure(closure)
    expected = {
        "callprim": {
            name for name, item in current.items() if item["target_lowering"] == "callprim"
        },
        "error-service": {
            name for name, item in current.items()
            if item["classification"] == "intentional-error-sentinel"
        },
    }
    directory = {
        name for name, item in current.items()
        if item["target_lowering"] == "static-directory"
    }
    expected["native-service"] = (
        set(current) - expected["callprim"] - expected["error-service"] - directory
    )
    expected["native-service"].difference_update(registry["staging_retired_targets"])
    expected["error-service"].update(registry["staging_only_targets"])
    if classes != expected:
        raise InventoryError("staging classification partition differs from the v1 baseline")


def _require_closure_abi_bindings(closure: dict[str, Any], ledger: dict[str, Any]) -> None:
    for class_name in ("native-service", "error-service"):
        for item in closure["implemented_bindings"][class_name]:
            classified = ABI.classify_id(ledger, "dialect-v2", "prim", item["id"])
            if classified["status"] != "active" or classified["canonical_name"] != item["name"]:
                raise InventoryError(
                    f"staging service binding differs from ABI: {item['name']}/{item['id']}"
                )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_exact_misses(
    actual: dict[str, dict[str, int]], expected: dict[str, dict[str, Any]]
) -> None:
    expected_counts = {name: item["expected_calls"] for name, item in expected.items()}
    if actual == expected_counts:
        return
    unknown = sorted(set(actual) - set(expected_counts))
    absent = sorted(set(expected_counts) - set(actual))
    changed = sorted(
        name for name in set(actual) & set(expected_counts)
        if actual[name] != expected_counts[name]
    )
    raise InventoryError(
        f"current miss inventory drift: unknown={unknown} absent={absent} changed={changed}"
    )


def _require_zero_miss(report: dict[str, Any]) -> None:
    count = report["summary"]["unresolved_calls"]
    if count:
        names = ", ".join(row["name"] for row in report["current_misses"])
        raise InventoryError(f"zero-miss target blocked by {count} calls: {names}")


def _staging_target_class(target: str, classes: dict[str, set[str]]) -> str:
    matches = [class_name for class_name, members in classes.items() if target in members]
    if len(matches) != 1:
        raise InventoryError(f"staging target {target!r} has no unique explicit classification")
    return matches[0]


def _require_staging_closure(report: dict[str, Any], closure: dict[str, Any]) -> None:
    _, classes, bindings = validate_closure(closure)
    profiles = [artifact["abi_profile"] for artifact in report["artifacts"]]
    if len(profiles) != 4 or any(profile != "dialect-v2" for profile in profiles):
        raise InventoryError("staging closure is not a four-artifact dialect-v2 set")
    tombstones = report["summary"]["tombstone_callprim_calls"]
    if tombstones:
        raise InventoryError(f"staging closure contains {tombstones} tombstone CALLPRIM calls")
    _require_zero_miss(report)
    for class_name in ("native-service", "error-service"):
        missing = sorted(classes[class_name] - bindings[class_name])
        if missing:
            raise InventoryError(
                f"staging closure lacks implemented {class_name} bindings: {missing}"
            )
    observed = {
        row["name"] for row in report["callprim_services"] if row["total_calls"] > 0
    }
    required_observed = set().union(*classes.values())
    missing_callprims = sorted(required_observed - observed)
    if missing_callprims:
        raise InventoryError(
            "staging closure did not emit every classified CALLPRIM target: "
            f"{missing_callprims}"
        )
    if report["summary"]["classified_targets"] != CLOSURE_CLASS_COUNTS:
        raise InventoryError("staging report classification counts drift")


def analyze(
    contract: dict[str, Any], root: Path, *, check_abi_mirrors: bool,
    closure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    staging = closure is not None
    if staging:
        artifacts, closure_classes, implemented_bindings = validate_closure(closure)
        expected: dict[str, dict[str, Any]] = {}
    else:
        artifacts, expected = validate_contract(contract)
        closure_classes = {}
        implemented_bindings = {}
    ledger_path = _relpath(root, contract["abi_ledger"], "abi_ledger")
    ledger = ABI.load_json(ledger_path)
    ABI.validate(ledger, check_mirrors=check_abi_mirrors)
    if staging:
        _require_closure_abi_bindings(closure, ledger)

    loaded: dict[str, dict[str, Any]] = {}
    providers: dict[str, set[str]] = {}
    artifact_receipts: list[dict[str, Any]] = []
    for spec in artifacts:
        manifest_path = _relpath(root, spec["manifest"], f"artifact {spec['id']} manifest")
        manifest = load_json(manifest_path)
        for key, expected_value in (
            ("format", spec["manifest_format"]), ("artifact_role", spec["artifact_role"]),
            ("name", spec["name"]), ("suite", spec["suite"]),
        ):
            if manifest.get(key) != expected_value:
                raise InventoryError(f"artifact {spec['id']} manifest {key} drift")
        if staging and manifest.get("abi_profile") != "dialect-v2":
            raise InventoryError(
                f"staging artifact {spec['id']} manifest is not explicitly dialect-v2"
            )
        blob_path = _relpath(root, manifest.get("blob"), f"artifact {spec['id']} blob")
        blob = blob_path.read_bytes()
        if _sha256(blob) != manifest.get("blob_sha256"):
            raise InventoryError(f"artifact {spec['id']} blob SHA-256 mismatch")
        entries = manifest.get("entries")
        if not isinstance(entries, list):
            raise InventoryError(f"artifact {spec['id']} entries must be a list")
        names: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
                raise InventoryError(f"artifact {spec['id']} contains a malformed entry")
            names.append(entry["name"])
        if len(names) != len(set(names)):
            raise InventoryError(f"artifact {spec['id']} contains duplicate definitions")
        providers[spec["id"]] = set(names)
        loaded[spec["id"]] = {"spec": spec, "manifest": manifest, "blob": blob}
        artifact_receipts.append({
            "id": spec["id"], "manifest": spec["manifest"],
            "manifest_sha256": _sha256(manifest_path.read_bytes()),
            "blob": manifest["blob"], "blob_sha256": manifest["blob_sha256"],
            "definitions": len(entries), "abi_profile": spec["abi_profile"],
        })

    unresolved: dict[str, Counter[str]] = defaultdict(Counter)
    sites: list[dict[str, Any]] = []
    callprim_counts: dict[str, Counter[str]] = defaultdict(Counter)
    tombstone_callprim_counts: dict[str, Counter[str]] = defaultdict(Counter)
    bound_service_counts: dict[str, Counter[str]] = defaultdict(Counter)
    directory_calls = Counter()
    for artifact_id, item in loaded.items():
        spec, manifest, blob = item["spec"], item["manifest"], item["blob"]
        visible = set().union(*(providers[other] for other in spec["visible_artifacts"]))
        for entry in manifest["entries"]:
            off, length = entry.get("blob_offset"), entry.get("length")
            if type(off) is not int or type(length) is not int or off < 0 or length <= 0 or off + length > len(blob):
                raise InventoryError(f"artifact {artifact_id} entry {entry['name']} has invalid blob bounds")
            try:
                code = B.decode_code_object(blob[off:off + length])
            except B.DecodeError as exc:
                raise InventoryError(f"artifact {artifact_id} entry {entry['name']} is not a CodeObject: {exc}") from exc
            literals = entry.get("literals")
            if not isinstance(literals, list) or len(literals) != len(code.littab):
                raise InventoryError(f"artifact {artifact_id} entry {entry['name']} literal table drift")
            pc = 0
            while pc < len(code.payload):
                here = pc
                try:
                    op, operand, pc = B.decode_instruction(
                        code.payload, pc, profile_id=spec["abi_profile"], abi_ledger=ledger
                    )
                except B.DecodeError as exc:
                    raise InventoryError(f"artifact {artifact_id} entry {entry['name']} decode failed: {exc}") from exc
                if op.mnemonic == "CALLPRIM":
                    prim_id, _argc = operand
                    identity = ABI.classify_id(ledger, spec["abi_profile"], "prim", prim_id)
                    if identity["status"] == "tombstone":
                        name = identity["canonical_name"] or f"prim-{prim_id}"
                        tombstone_callprim_counts[name][artifact_id] += 1
                        continue
                    if identity["status"] != "active" or identity["canonical_name"] is None:
                        raise InventoryError(f"artifact {artifact_id} uses non-active Prim-ID {prim_id}")
                    callprim_counts[identity["canonical_name"]][artifact_id] += 1
                elif op.mnemonic in {"CALL", "TAILCALL"}:
                    lit_index, argc = operand
                    if lit_index >= len(literals) or not isinstance(literals[lit_index], dict) or set(literals[lit_index]) != {"symbol"}:
                        raise InventoryError(f"artifact {artifact_id} entry {entry['name']} call target is not a symbol literal")
                    target = literals[lit_index]["symbol"]
                    if not isinstance(target, str) or not target:
                        raise InventoryError(f"artifact {artifact_id} entry {entry['name']} has an invalid call target")
                    if target in visible:
                        directory_calls[artifact_id] += 1
                    elif staging:
                        target_class = _staging_target_class(target, closure_classes)
                        if (
                            target_class in implemented_bindings
                            and target in implemented_bindings[target_class]
                        ):
                            bound_service_counts[target][artifact_id] += 1
                        else:
                            unresolved[target][artifact_id] += 1
                            sites.append({
                                "artifact": artifact_id, "function": entry["name"], "pc": here,
                                "opcode": op.mnemonic, "argc": argc, "target": target,
                                "classification": target_class,
                            })
                    else:
                        unresolved[target][artifact_id] += 1
                        sites.append({
                            "artifact": artifact_id, "function": entry["name"], "pc": here,
                            "opcode": op.mnemonic, "argc": argc, "target": target,
                        })

    actual = {name: dict(sorted(counts.items())) for name, counts in sorted(unresolved.items())}
    if not staging:
        _require_exact_misses(actual, expected)

    class_counts = Counter()
    service_rows = []
    for name, counts in sorted(unresolved.items()):
        if staging:
            target_class = _staging_target_class(name, closure_classes)
            fixture = {
                "classification": target_class,
                "owner": "staging-closure",
                "current_lowering": "unresolved-op-call",
                "target_lowering": target_class,
            }
        else:
            fixture = expected[name]
        total = sum(counts.values())
        class_counts[fixture["classification"]] += total
        service_rows.append({
            "name": name, "classification": fixture["classification"], "owner": fixture["owner"],
            "current_lowering": fixture["current_lowering"], "target_lowering": fixture["target_lowering"],
            "calls": dict(sorted(counts.items())), "total_calls": total,
        })
    profile_order = ledger["profile_order"]
    prim_rows = []
    for prim_id, name in sorted(B.PRIM_IDS.items()):
        profile_states = {}
        for profile_id in profile_order:
            classified = ABI.classify_id(ledger, profile_id, "prim", prim_id)
            profile_states[profile_id] = {
                "status": classified["status"],
                "function_designator": B.prim_is_function_designator(
                    prim_id, profile_id=profile_id, abi_ledger=ledger
                ),
            }
        prim_rows.append({
            "id": prim_id,
            "name": name,
            "lowering": (
                "callprim-internal-only"
                if prim_id in B.INTERNAL_ONLY_PRIM_IDS else "callprim"
            ),
            "profiles": profile_states,
            "calls": dict(sorted(callprim_counts[name].items())),
            "total_calls": sum(callprim_counts[name].values()),
            "abi_mirrors": "verified",
        })
    abi_profiles = [
        {
            "id": profile_id,
            "active_prim_ids": list(
                next(item for item in ledger["profiles"] if item["id"] == profile_id)["prim_ids"]["active"]
            ),
            "tombstone_prim_ids": list(
                next(item for item in ledger["profiles"] if item["id"] == profile_id)["prim_ids"]["tombstone"]
            ),
        }
        for profile_id in profile_order
    ]
    return {
        "format": REPORT_FORMAT, "version": 1, "binding": "static-build-time",
        "mode": "staging" if staging else "current",
        "runtime_function_pointer_registry": False, "artifacts": artifact_receipts,
        "abi_profiles": abi_profiles,
        "summary": {
            "directory_calls": sum(directory_calls.values()),
            "callprim_calls": sum(row["total_calls"] for row in prim_rows),
            "tombstone_callprim_calls": sum(
                sum(counts.values()) for counts in tombstone_callprim_counts.values()
            ),
            "unresolved_calls": len(sites), "unresolved_targets": len(service_rows),
            "native_service_calls": class_counts["native-service"],
            "intentional_error_sentinel_calls": (
                class_counts["error-service"] if staging
                else class_counts["intentional-error-sentinel"]
            ),
            "bound_service_calls": sum(
                sum(counts.values()) for counts in bound_service_counts.values()
            ),
            "classified_targets": (
                {name: len(members) for name, members in closure_classes.items()}
                if staging else None
            ),
            "zero_miss_ready": (
                len(sites) == 0
                and not tombstone_callprim_counts
                and (
                    not staging
                    or all(
                        implemented_bindings[name] == closure_classes[name]
                        for name in implemented_bindings
                    )
                )
            ),
        },
        "current_misses": service_rows, "unresolved_sites": sorted(sites, key=lambda row: (row["target"], row["artifact"], row["function"], row["pc"])),
        "bound_services": [
            {"name": name, "calls": dict(sorted(counts.items())), "total_calls": sum(counts.values())}
            for name, counts in sorted(bound_service_counts.items())
        ],
        "tombstone_callprims": [
            {"name": name, "calls": dict(sorted(counts.items())), "total_calls": sum(counts.values())}
            for name, counts in sorted(tombstone_callprim_counts.items())
        ],
        "callprim_services": prim_rows,
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _expect_failure(label: str, action: Callable[[], None]) -> None:
    try:
        action()
    except InventoryError:
        return
    raise InventoryError(f"selftest mutation was accepted: {label}")


def selftest() -> None:
    # Contract mutations are source-only and do not depend on generated artifacts.
    base = {
        "format": FORMAT, "version": 1, "abi_ledger": "config/bytecode-abi-ledger.json",
        "staging_closure": "config/v2-workbench-artifact-closure.json",
        "staging_only_targets": ["%lcc-error-invalid-parameter-list"],
        "staging_retired_targets": [],
        "policies": dict(POLICIES),
        "artifacts": [{
            "id": "resident", "manifest": "build/a.json", "manifest_format": "fixture",
            "artifact_role": "stdlib", "name": None, "suite": "fixture.json",
            "abi_profile": "dialect-v1", "visible_artifacts": ["resident"],
        }],
        "current_misses": [{
            "name": "native-x", "classification": "native-service", "owner": "fixture",
            "current_lowering": "op-call-carrier", "target_lowering": "callprim",
            "expected_calls": {"resident": 1},
        }],
    }
    validate_contract(base)
    ledger = ABI.load_json(ROOT / "config" / "bytecode-abi-ledger.json")
    ABI.validate(ledger, check_mirrors=False)
    profiles = {item["id"]: item["prim_ids"] for item in ledger["profiles"]}
    if profiles["dialect-v1"]["active"] != list(range(23)):
        raise InventoryError("dialect-v1 Prim-ID allocation drift")
    required_v2 = {0, *range(3, 26), 28, 29}
    if (
        not required_v2 <= set(profiles["dialect-v2"]["active"])
        or {1, 2} & set(profiles["dialect-v2"]["active"])
        or profiles["dialect-v2"]["tombstone"] != [1, 2, 26, 27, 34, 40]
    ):
        raise InventoryError("dialect-v2 Prim-ID allocation drift")
    if any(
        B.prim_is_function_designator(ident, "dialect-v2", ledger)
        for ident in B.INTERNAL_ONLY_PRIM_IDS
    ):
        raise InventoryError("internal-only Prim-ID is a function designator")
    mutations = 0
    def reject(change: Callable[[dict[str, Any]], None]) -> None:
        nonlocal mutations
        value = deepcopy(base); change(value)
        _expect_failure(str(mutations), lambda: validate_contract(value)); mutations += 1
    reject(lambda value: value.update(version=2))
    reject(lambda value: value.update(staging_closure=""))
    reject(lambda value: value["policies"].update(binding="runtime"))
    reject(lambda value: value["artifacts"][0].update(extra=True))
    reject(lambda value: value["artifacts"][0].update(visible_artifacts=[]))
    reject(lambda value: value["current_misses"][0].update(classification="mystery"))
    reject(lambda value: value["current_misses"][0].update(current_lowering="callprim"))
    reject(lambda value: value["current_misses"][0].update(expected_calls={"resident": 0}))
    duplicate = json.dumps(base)[:-1] + ',"version":1}'
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "duplicate.json"; path.write_text(duplicate, encoding="utf-8")
        _expect_failure("duplicate JSON key", lambda: load_json(path)); mutations += 1
    expected = {"native-x": base["current_misses"][0]}
    _require_exact_misses({"native-x": {"resident": 1}}, expected)
    for label, actual in (
        ("new miss", {"native-x": {"resident": 1}, "new-x": {"resident": 1}}),
        ("missing miss", {}),
        ("miss count", {"native-x": {"resident": 2}}),
    ):
        _expect_failure(label, lambda actual=actual: _require_exact_misses(actual, expected))
        mutations += 1
    zero_report = {"summary": {"unresolved_calls": 0}, "current_misses": []}
    _require_zero_miss(zero_report)
    nonzero_report = {
        "summary": {"unresolved_calls": 1}, "current_misses": [{"name": "native-x"}],
    }
    _expect_failure("zero-miss allowlist bypass", lambda: _require_zero_miss(nonzero_report))
    mutations += 1

    closure_artifacts = []
    for artifact_id, role, name in (
        ("resident", "stdlib", None), ("ide", "disk-lib", "ide"),
        ("idex", "disk-lib", "ide-extra"), ("m65d", "disk-lib", "m65d"),
    ):
        closure_artifacts.append({
            "id": artifact_id, "manifest": f"build/{artifact_id}.json",
            "manifest_format": "fixture", "artifact_role": role, "name": name,
            "source_suite": f"tests/source-{artifact_id}.json",
            "suite": f"build/suite-{artifact_id}.json", "abi_profile": "dialect-v2",
            "visible_artifacts": list(CLOSURE_ARTIFACT_IDS),
        })
    closure_base = {
        "format": CLOSURE_FORMAT, "version": 1,
        "abi_ledger": "config/bytecode-abi-ledger.json",
        "target_abi_profile": "dialect-v2", "policies": dict(CLOSURE_POLICIES),
        "target_counts": {**CLOSURE_CLASS_COUNTS, "total": CLOSURE_TOTAL},
        "artifacts": closure_artifacts,
        "classifications": {
            "callprim": ["cp0", "cp1", "cp2", "cp3"],
            "native-service": [f"native-{index:02d}" for index in range(14)],
            "error-service": [f"error-{index:02d}" for index in range(11)],
        },
        "implemented_bindings": {"native-service": [], "error-service": []},
    }
    validate_closure(closure_base)

    def reject_closure(change: Callable[[dict[str, Any]], None]) -> None:
        nonlocal mutations
        value = deepcopy(closure_base); change(value)
        _expect_failure(f"closure-{mutations}", lambda: validate_closure(value)); mutations += 1

    reject_closure(lambda value: value.update(target_abi_profile="dialect-v1"))
    reject_closure(lambda value: value["policies"].update(new_classification="allow"))
    reject_closure(lambda value: value["target_counts"].update(total=31))
    reject_closure(lambda value: value["artifacts"].pop())
    reject_closure(lambda value: value["artifacts"][0].update(abi_profile="dialect-v1"))
    reject_closure(lambda value: value["artifacts"][0]["visible_artifacts"].pop())
    reject_closure(lambda value: value["classifications"]["callprim"].pop())
    reject_closure(lambda value: value["classifications"]["native-service"].append("native-16"))
    reject_closure(lambda value: value["classifications"]["error-service"].reverse())
    reject_closure(lambda value: value["classifications"]["error-service"].__setitem__(0, "cp0"))
    reject_closure(lambda value: value["implemented_bindings"]["native-service"].append({"name": "unknown", "id": 30}))
    _expect_failure(
        "unclassified staging target",
        lambda: _staging_target_class("new-service", validate_closure(closure_base)[1]),
    )
    mutations += 1

    complete = deepcopy(closure_base)
    for class_name in ("native-service", "error-service"):
        complete["implemented_bindings"][class_name] = []
        for name, prim_id in zip(
            complete["classifications"][class_name], CLOSURE_BINDING_IDS[class_name]
        ):
            complete["implemented_bindings"][class_name].append({"name": name, "id": prim_id})
    staging_report = {
        "artifacts": [{"abi_profile": "dialect-v2"} for _ in range(4)],
        "summary": {
            "unresolved_calls": 0, "tombstone_callprim_calls": 0,
            "classified_targets": dict(CLOSURE_CLASS_COUNTS),
        },
        "current_misses": [],
        "callprim_services": [
            {"name": name, "total_calls": 1}
            for class_name in CLOSURE_CLASS_COUNTS
            for name in complete["classifications"][class_name]
        ],
    }
    _require_staging_closure(staging_report, complete)
    for label, mutate_report, mutate_closure in (
        ("staging-v1", lambda report: report["artifacts"][0].update(abi_profile="dialect-v1"), None),
        ("staging-tombstone", lambda report: report["summary"].update(tombstone_callprim_calls=1), None),
        ("staging-unresolved", lambda report: report["summary"].update(unresolved_calls=1), None),
        ("staging-callprim-missing", lambda report: report["callprim_services"].pop(), None),
        ("staging-binding-missing", None, lambda value: value["implemented_bindings"]["native-service"].pop()),
    ):
        report = deepcopy(staging_report); closure_value = deepcopy(complete)
        if mutate_report: mutate_report(report)
        if mutate_closure: mutate_closure(closure_value)
        _expect_failure(label, lambda r=report, c=closure_value: _require_staging_closure(r, c))
        mutations += 1

    real_registry = load_json(DEFAULT_CONTRACT)
    real_closure = load_json(ROOT / real_registry["staging_closure"])
    _require_registry_closure_alignment(real_registry, real_closure)
    print(f"workbench service inventory selftest: PASS ({mutations} rejected mutations)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--closure", type=Path)
    parser.add_argument("--mode", choices=("current", "staging", "zero-miss"), default="current")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest(); return 0
    contract = load_json(args.contract)
    validate_contract(contract)
    closure = None
    if args.mode != "current":
        closure_path = args.closure or _relpath(ROOT, contract["staging_closure"], "staging_closure")
        closure = load_json(closure_path)
        _require_registry_closure_alignment(contract, closure)
    report = analyze(contract, ROOT, check_abi_mirrors=True, closure=closure)
    if args.json_out:
        _write_json(args.json_out, report)
    summary = report["summary"]
    print(
        "workbench service inventory: "
        f"unresolved={summary['unresolved_calls']} targets={summary['unresolved_targets']} "
        f"native={summary['native_service_calls']} sentinels={summary['intentional_error_sentinel_calls']} "
        f"tombstone_callprims={summary['tombstone_callprim_calls']}"
    )
    if args.mode != "current":
        _require_staging_closure(report, closure)
    print(f"workbench service inventory {args.mode}: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InventoryError as exc:
        print(f"workbench service inventory: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
