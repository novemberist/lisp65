#!/usr/bin/env python3
"""Prove the dialect-v2 Runtime-Core artifact has a closed service surface."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import bytecode_abi_ledger as ABI  # noqa: E402
import bytecode_p0 as B  # noqa: E402


FORMAT = "lisp65-runtime-core-v2-service-registry-v1"
REPORT_FORMAT = "lisp65-runtime-core-v2-service-inventory-v1"
DEFAULT_CONTRACT = ROOT / "config/runtime-core-v2-service-registry.json"
TOP_KEYS = {
    "format", "version", "abi_ledger", "artifact", "policies",
    "allowed_callprim_ids", "forbidden_callprim_ids", "classifications",
}
ARTIFACT_KEYS = {"manifest", "format", "role", "suite", "abi_profile"}
POLICIES = {
    "binding": "static-build-time",
    "new_call": "reject-unless-explicitly-classified",
    "runtime_function_pointer_registry": "forbidden",
    "workbench_service_ids": "forbidden",
}
CLASSIFICATION_KEYS = {"kind", "target", "owner", "expected_calls"}
WORKBENCH_SERVICE_IDS = set(range(30, 57))
TOMBSTONE_IDS = {1, 2}


class InventoryError(RuntimeError):
    pass


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InventoryError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise InventoryError(f"{label} must be a JSON object")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise InventoryError(f"{label} keys differ")
    return value


def _relative(root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise InventoryError(f"{label} must be a non-empty relative path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or pure.as_posix() != value:
        raise InventoryError(f"{label} is not a canonical relative path")
    path = root / pure
    if path.is_symlink() or not path.is_file():
        raise InventoryError(f"{label} is not a regular file: {value}")
    return path


def _ints(value: Any, label: str) -> list[int]:
    if (
        not isinstance(value, list)
        or any(type(item) is not int or not 0 <= item <= 255 for item in value)
        or value != sorted(set(value))
    ):
        raise InventoryError(f"{label} must be sorted unique byte IDs")
    return value


def validate_contract(value: dict[str, Any]) -> dict[tuple[str, str | int], int]:
    _exact(value, TOP_KEYS, "contract")
    if value["format"] != FORMAT or value["version"] != 1:
        raise InventoryError("contract identity drift")
    artifact = _exact(value["artifact"], ARTIFACT_KEYS, "artifact")
    if artifact["abi_profile"] != "dialect-v2":
        raise InventoryError("Runtime-Core artifact must be explicitly dialect-v2")
    if value["policies"] != POLICIES:
        raise InventoryError("registry policy drift")
    allowed = set(_ints(value["allowed_callprim_ids"], "allowed_callprim_ids"))
    forbidden = set(_ints(value["forbidden_callprim_ids"], "forbidden_callprim_ids"))
    if allowed & forbidden:
        raise InventoryError("allowed and forbidden Prim-ID sets overlap")
    if not TOMBSTONE_IDS <= forbidden:
        raise InventoryError("v2 tombstones 1/2 must be forbidden")
    if not WORKBENCH_SERVICE_IDS <= forbidden:
        raise InventoryError("Workbench service IDs 30..56 must be forbidden")
    expected: dict[tuple[str, str | int], int] = {}
    rows = value["classifications"]
    if not isinstance(rows, list):
        raise InventoryError("classifications must be a list")
    for index, raw in enumerate(rows):
        row = _exact(raw, CLASSIFICATION_KEYS, f"classifications[{index}]")
        kind, target = row["kind"], row["target"]
        if kind not in {"directory", "callprim"}:
            raise InventoryError(f"classifications[{index}].kind is invalid")
        if kind == "directory" and (not isinstance(target, str) or not target):
            raise InventoryError(f"classifications[{index}].target is invalid")
        if kind == "callprim" and (type(target) is not int or target not in allowed):
            raise InventoryError(f"classifications[{index}] Prim-ID is not allowed")
        if not isinstance(row["owner"], str) or not row["owner"]:
            raise InventoryError(f"classifications[{index}].owner is invalid")
        if type(row["expected_calls"]) is not int or row["expected_calls"] <= 0:
            raise InventoryError(f"classifications[{index}].expected_calls is invalid")
        key = (kind, target)
        if key in expected:
            raise InventoryError(f"duplicate classification: {key}")
        expected[key] = row["expected_calls"]
    return expected


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze(contract: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    expected = validate_contract(contract)
    artifact = contract["artifact"]
    manifest_path = _relative(root, artifact["manifest"], "artifact.manifest")
    manifest = _load(manifest_path, "Runtime-Core manifest")
    for key, wanted in (
        ("format", artifact["format"]), ("artifact_role", artifact["role"]),
        ("suite", artifact["suite"]), ("abi_profile", artifact["abi_profile"]),
    ):
        if manifest.get(key) != wanted:
            raise InventoryError(f"Runtime-Core manifest {key} drift")
    if manifest.get("strict_arity") is not True:
        raise InventoryError("Runtime-Core v2 artifact lacks STRICT_ARITY")

    ledger_path = _relative(root, contract["abi_ledger"], "abi_ledger")
    ledger = ABI.load_json(ledger_path)
    ABI.validate(ledger, check_mirrors=True)
    blob_path = _relative(root, manifest.get("blob"), "manifest.blob")
    blob = blob_path.read_bytes()
    if hashlib.sha256(blob).hexdigest() != manifest.get("blob_sha256"):
        raise InventoryError("Runtime-Core blob SHA-256 mismatch")

    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise InventoryError("Runtime-Core manifest entries must be non-empty")
    providers = {
        entry.get("name") for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }
    if len(providers) != len(entries):
        raise InventoryError("Runtime-Core entries are malformed or duplicated")

    actual: Counter[tuple[str, str | int]] = Counter()
    sites: list[dict[str, Any]] = []
    callprim_ids: Counter[int] = Counter()
    for entry in entries:
        off, length = entry.get("blob_offset"), entry.get("length")
        if (
            type(off) is not int or type(length) is not int or off < 0
            or length <= 0 or off + length > len(blob)
        ):
            raise InventoryError(f"entry {entry['name']} has invalid blob bounds")
        try:
            code = B.decode_code_object(blob[off:off + length])
        except B.DecodeError as exc:
            raise InventoryError(f"entry {entry['name']} is invalid: {exc}") from exc
        if not (code.flags & B.CO_FLAG_STRICT_ARITY):
            raise InventoryError(f"entry {entry['name']} lacks STRICT_ARITY")
        literals = entry.get("literals")
        if not isinstance(literals, list) or len(literals) != len(code.littab):
            raise InventoryError(f"entry {entry['name']} literal table drift")
        pc = 0
        while pc < len(code.payload):
            here = pc
            try:
                op, operand, pc = B.decode_instruction(
                    code.payload, pc, profile_id="dialect-v2", abi_ledger=ledger
                )
            except B.DecodeError as exc:
                raise InventoryError(f"entry {entry['name']} decode failed: {exc}") from exc
            if op.mnemonic == "CALLPRIM":
                prim_id, argc = operand
                classified = ABI.classify_id(ledger, "dialect-v2", "prim", prim_id)
                if prim_id in TOMBSTONE_IDS or classified["status"] == "tombstone":
                    raise InventoryError(f"Runtime-Core calls tombstone Prim-ID {prim_id}")
                if prim_id in WORKBENCH_SERVICE_IDS:
                    raise InventoryError(f"Runtime-Core calls Workbench service Prim-ID {prim_id}")
                if prim_id not in set(contract["allowed_callprim_ids"]):
                    raise InventoryError(f"Runtime-Core calls unallowed Prim-ID {prim_id}")
                key: tuple[str, str | int] = ("callprim", prim_id)
                callprim_ids[prim_id] += 1
                actual[key] += 1
                sites.append({"function": entry["name"], "pc": here, "kind": "callprim", "target": prim_id, "argc": argc})
            elif op.mnemonic in {"CALL", "TAILCALL"}:
                lit_index, argc = operand
                if (
                    lit_index >= len(literals)
                    or not isinstance(literals[lit_index], dict)
                    or set(literals[lit_index]) != {"symbol"}
                ):
                    raise InventoryError(f"entry {entry['name']} call target is not a symbol")
                target = literals[lit_index]["symbol"]
                if target not in providers:
                    raise InventoryError(f"Runtime-Core unresolved directory call: {target}")
                key = ("directory", target)
                actual[key] += 1
                sites.append({"function": entry["name"], "pc": here, "kind": "directory", "target": target, "argc": argc})

    if dict(actual) != expected:
        unknown = sorted((str(key), count) for key, count in actual.items() if key not in expected)
        absent = sorted(str(key) for key in expected if key not in actual)
        changed = sorted(
            (str(key), expected[key], actual[key])
            for key in expected.keys() & actual.keys() if expected[key] != actual[key]
        )
        raise InventoryError(
            f"Runtime-Core call classification drift: unknown={unknown} absent={absent} changed={changed}"
        )

    return {
        "format": REPORT_FORMAT,
        "version": 1,
        "status": "closed",
        "service_registry_closed": True,
        "runtime_function_pointer_registry": False,
        "artifact": {
            "manifest": artifact["manifest"],
            "manifest_sha256": _sha(manifest_path),
            "blob": manifest["blob"],
            "blob_sha256": manifest["blob_sha256"],
            "suite": manifest["suite"],
            "abi_profile": manifest["abi_profile"],
            "strict_arity": True,
            "entries": len(entries),
        },
        "summary": {
            "classified_calls": sum(actual.values()),
            "directory_calls": sum(count for (kind, _), count in actual.items() if kind == "directory"),
            "callprim_calls": sum(callprim_ids.values()),
            "tombstone_callprim_calls": 0,
            "workbench_service_callprim_calls": 0,
            "unresolved_calls": 0,
            "unclassified_calls": 0,
        },
        "classifications": [
            {"kind": kind, "target": target, "calls": actual[(kind, target)]}
            for kind, target in sorted(actual, key=lambda item: (item[0], str(item[1])))
        ],
        "sites": sites,
    }


def selftest() -> None:
    sample = _load(DEFAULT_CONTRACT, "selftest contract")
    validate_contract(sample)
    mutations = (
        lambda value: value.update(format="wrong"),
        lambda value: value["policies"].update(new_call="accept"),
        lambda value: value["allowed_callprim_ids"].append(30),
        lambda value: value["forbidden_callprim_ids"].remove(1),
        lambda value: value["forbidden_callprim_ids"].remove(56),
        lambda value: value["classifications"][0].update(expected_calls=0),
    )
    for index, mutate in enumerate(mutations):
        candidate = deepcopy(sample)
        mutate(candidate)
        try:
            validate_contract(candidate)
        except InventoryError:
            continue
        raise InventoryError(f"selftest mutation {index} was accepted")
    print("runtime-core-v2-service-inventory: SELFTEST PASS mutations=6")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            selftest()
            return 0
        contract = _load(args.contract, "Runtime-Core service contract")
        report = analyze(contract)
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        summary = report["summary"]
        print(
            "runtime-core-v2-service-inventory: PASS "
            f"classified={summary['classified_calls']} directory={summary['directory_calls']} "
            f"callprim={summary['callprim_calls']} tombstones=0 workbench-services=0 unresolved=0"
        )
        return 0
    except (InventoryError, ABI.LedgerError, KeyError, TypeError, ValueError, OSError) as exc:
        print(f"runtime-core-v2-service-inventory: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
