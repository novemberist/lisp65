#!/usr/bin/env python3
"""Generate and verify the Wave-2 public function-metadata contract index."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import bytecode_p0 as P0  # noqa: E402


CONTRACT = ROOT / "config/v11-function-metadata-contract.json"
SURFACE = ROOT / "config/dialect-v2-surface.json"
BUFFER_CONTRACT = ROOT / "docs/contracts/first-class-buffer.md"
NATIVE_REGISTRY = ROOT / "config/v2-native-function-registry.json"
INDEX = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-function-metadata-index.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-function-metadata-contract-receipt.json"
)


class MetadataError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MetadataError(message)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MetadataError(f"cannot read {path}: {exc}") from exc
    require(isinstance(value, dict), f"object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": rel(path), "bytes": len(data), "sha256": sha(data)}


def arity(code: P0.CodeObject) -> dict[str, Any]:
    optional = code.flags >> P0.CO_FLAG_OPTIONAL_SHIFT
    require(optional <= code.nargs, "code object optional arity exceeds nargs")
    rest = bool(code.flags & P0.CO_FLAG_REST)
    strict = bool(code.flags & P0.CO_FLAG_STRICT_ARITY)
    require(strict, "public bytecode metadata requires strict arity")
    return {
        "status": "exact-code-object",
        "required": code.nargs - optional,
        "optional": optional,
        "rest": rest,
        "maximum": None if rest else code.nargs,
    }


def public_definitions(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    surface = load(SURFACE)
    definitions = surface.get("definitions")
    require(isinstance(definitions, list) and definitions,
            "public dialect surface has no definitions")
    result: dict[str, dict[str, Any]] = {}
    for row in definitions:
        require(isinstance(row, dict), "invalid public-surface row")
        name = row.get("name")
        require(isinstance(name, str) and name == name.lower(),
                "surface names must be case-folded")
        require(name not in result, f"duplicate public name: {name}")
        result[name] = {
            "name": name,
            "kind": row.get("kind"),
            "visibility": row.get("visibility"),
            "public_authority": "dialect-v2-surface",
        }
    addition = contract["public_authorities"]["buffer_addition"]
    text = BUFFER_CONTRACT.read_text(encoding="utf-8")
    for name in addition["names"]:
        require(f"({name}" in text, f"buffer public authority does not name {name}")
        require(name not in result, f"buffer name already has a public authority: {name}")
        result[name] = {
            "name": name,
            "kind": addition["kind"],
            "visibility": "public",
            "public_authority": "first-class-buffer-contract",
        }
    return result


def bytecode_definitions(contract: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    result: dict[str, dict[str, Any]] = {}
    bindings: list[dict[str, Any]] = []
    for library, manifest_name in contract["bytecode_authorities"]:
        manifest_path = ROOT / manifest_name
        manifest = load(manifest_path)
        blob_path = ROOT / manifest["blob"]
        blob = blob_path.read_bytes()
        require(sha(blob) == manifest["blob_sha256"],
                f"blob SHA drift: {library}")
        entries = manifest.get("entries")
        require(isinstance(entries, list), f"manifest entries missing: {library}")
        for ordinal, entry in enumerate(entries):
            name = entry.get("name")
            require(isinstance(name, str), f"entry name missing: {library}#{ordinal}")
            start = entry.get("blob_offset")
            length = entry.get("length")
            require(isinstance(start, int) and isinstance(length, int),
                    f"entry span missing: {library}#{ordinal}")
            code_bytes = blob[start:start + length]
            require(len(code_bytes) == length, f"entry outside blob: {library}#{ordinal}")
            code = P0.decode_code_object(code_bytes)
            require(code.flags == entry.get("code_flags"),
                    f"code flags drift: {library}#{ordinal}")
            if name in result:
                result[name]["duplicates"].append({"library": library, "ordinal": ordinal})
                continue
            result[name] = {
                "library": library,
                "ordinal": ordinal,
                "anonymous": bool(entry.get("anonymous", False)),
                "manifest_kind": entry.get("kind"),
                "arity": arity(code),
                "code_object": {
                    "bytes": length,
                    "sha256": sha(code_bytes),
                    "flags": code.flags,
                },
                "duplicates": [],
            }
        bindings.append({
            "library": library,
            "manifest": binding(manifest_path),
            "blob": binding(blob_path),
            "entries": len(entries),
        })
    return result, bindings


def unresolved_authority(name: str, kind: str, registry_names: set[str]) -> str:
    if kind == "primitive" and name in registry_names:
        return "native-function-registry-without-arity-field"
    if kind == "macro":
        return "macro-or-evaluator-authority-not-yet-generated"
    return "public-surface-only-no-arity-authority"


def build_index() -> tuple[dict[str, Any], dict[str, Any]]:
    contract = load(CONTRACT)
    require(contract.get("status") ==
            "wave2-host-contract-active-device-delivery-deferred-to-c2",
            "metadata contract state drift")
    public = public_definitions(contract)
    bytecode, bytecode_bindings = bytecode_definitions(contract)
    registry = load(NATIVE_REGISTRY)
    registry_names = {row["name"] for row in registry["entries"]}
    records = []
    exact = 0
    unresolved = 0
    for name in sorted(public):
        definition = public[name]
        implementation = bytecode.get(name)
        if implementation is not None:
            require(not implementation["anonymous"],
                    f"anonymous entry cannot satisfy public metadata: {name}")
            require(not implementation["duplicates"],
                    f"ambiguous public bytecode authority: {name}")
            record_arity = implementation["arity"]
            authority: dict[str, Any] = {
                "public": definition["public_authority"],
                "arity": "bytecode-code-object",
                "library": implementation["library"],
                "ordinal": implementation["ordinal"],
                "code_object": implementation["code_object"],
            }
            exact += 1
        else:
            reason = unresolved_authority(name, definition["kind"], registry_names)
            record_arity = {"status": "unresolved", "reason": reason}
            authority = {
                "public": definition["public_authority"],
                "arity": reason,
            }
            unresolved += 1
        records.append({
            "name": name,
            "kind": definition["kind"],
            "visibility": definition["visibility"],
            "arity": record_arity,
            "signature": None,
            "docstring": None,
            "authority": authority,
        })
    index = {
        "format": "lisp65-v11-function-metadata-index-v1",
        "version": 1,
        "recorded_on": "2026-07-18",
        "profile": "dialect-v2-wave2-candidate",
        "delivery": "host-only; device delivery deferred with ide-help to C2",
        "records": records,
    }
    stats = {
        "records": len(records),
        "exact_arity": exact,
        "unresolved_arity": unresolved,
        "null_signatures": sum(row["signature"] is None for row in records),
        "null_docstrings": sum(row["docstring"] is None for row in records),
        "bytecode_authorities": bytecode_bindings,
    }
    return index, stats


def validate(index: dict[str, Any]) -> None:
    require(index.get("format") == "lisp65-v11-function-metadata-index-v1",
            "metadata index format drift")
    require(index.get("delivery") == "host-only; device delivery deferred with ide-help to C2",
            "metadata index overclaims device delivery")
    records = index.get("records")
    require(isinstance(records, list) and records, "metadata records missing")
    names = [row.get("name") for row in records]
    require(names == sorted(names) and len(names) == len(set(names)),
            "metadata names must be sorted and unique")
    for row in records:
        require(set(row) == {"name", "kind", "visibility", "arity",
                             "signature", "docstring", "authority"},
                f"metadata record shape drift: {row.get('name')}")
        require(row["visibility"] == "public", "non-public metadata leaked")
        require(row["kind"] in ("function", "primitive", "macro"),
                "unknown public kind")
        arity_value = row["arity"]
        require(isinstance(arity_value, dict)
                and arity_value.get("status") in ("exact-code-object", "unresolved"),
                "invalid arity state")
        if arity_value["status"] == "exact-code-object":
            required = arity_value.get("required")
            optional = arity_value.get("optional")
            require(isinstance(required, int) and required >= 0
                    and isinstance(optional, int) and optional >= 0,
                    "invalid exact arity counts")
            expected_max = None if arity_value.get("rest") else required + optional
            require(arity_value.get("maximum") == expected_max,
                    "exact arity maximum drift")
        require(row["signature"] is None and row["docstring"] is None,
                "unbound optional metadata must remain null")


def collect() -> tuple[dict[str, Any], dict[str, Any]]:
    index, stats = build_index()
    validate(index)
    require(stats["records"] == 135 and stats["exact_arity"] == 101
            and stats["unresolved_arity"] == 34,
            "current public metadata coverage drift")
    index_bytes = canonical(index)
    receipt = {
        "format": "lisp65-v11-function-metadata-contract-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-18",
        "status": "host-contract-passed-device-delivery-deferred-to-c2",
        "claim_limit": load(CONTRACT)["claim_limit"],
        "bindings": {
            "contract": binding(CONTRACT),
            "dialect_surface": binding(SURFACE),
            "buffer_contract": binding(BUFFER_CONTRACT),
            "native_registry": binding(NATIVE_REGISTRY),
            "bytecode_authorities": stats["bytecode_authorities"],
        },
        "index": {
            "path": rel(INDEX),
            "bytes": len(index_bytes),
            "sha256": sha(index_bytes),
            "records": stats["records"],
            "exact_arity": stats["exact_arity"],
            "unresolved_arity": stats["unresolved_arity"],
            "null_signatures": stats["null_signatures"],
            "null_docstrings": stats["null_docstrings"],
        },
        "delivery_gate": {
            "ide_help_ready": False,
            "reasons": [
                "34 public records still lack an arity authority",
                "the single L65S-v4 real-link attempt failed and device metadata moved behind C2",
            ],
            "one_swap_rule": "future device index stays reset-persistent and product-identity-bound",
        },
        "capacity_delta": {
            "bank0_bytes": 0,
            "ext_bytes": 0,
            "fixed_overlay_bytes": 0,
            "runtime_overlay_bank_bytes": 0,
            "resident_island_bytes": 0,
            "installer_slice_bytes": 0,
            "symbols": 0,
            "namepool_bytes": 0,
            "directory_entries": 0,
            "shelf_bytes": 0,
        },
    }
    return index, receipt


def write() -> dict[str, Any]:
    index, receipt = collect()
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_bytes(canonical(index))
    RECEIPT.write_bytes(canonical(receipt))
    return receipt


def check() -> dict[str, Any]:
    expected_index, expected_receipt = collect()
    actual_index = load(INDEX)
    actual_receipt = load(RECEIPT)
    validate(actual_index)
    require(actual_index == expected_index, "function metadata index drift")
    require(actual_receipt == expected_receipt, "function metadata receipt drift")
    require(actual_receipt["index"]["sha256"] == sha(INDEX.read_bytes()),
            "function metadata index SHA binding drift")
    return actual_receipt


def selftest() -> None:
    index, _receipt = collect()
    mutations = []
    duplicate = json.loads(json.dumps(index))
    duplicate["records"].append(dict(duplicate["records"][0]))
    try:
        validate(duplicate)
    except MetadataError:
        mutations.append("duplicate-name")
    bad_max = json.loads(json.dumps(index))
    exact = next(row for row in bad_max["records"]
                 if row["arity"]["status"] == "exact-code-object")
    exact["arity"]["maximum"] = 255
    try:
        validate(bad_max)
    except MetadataError:
        mutations.append("bad-arity")
    overclaim = json.loads(json.dumps(index))
    overclaim["delivery"] = "device-ready"
    try:
        validate(overclaim)
    except MetadataError:
        mutations.append("device-overclaim")
    require(mutations == ["duplicate-name", "bad-arity", "device-overclaim"],
            "metadata mutation selftest drift")
    print("v11-function-metadata: SELFTEST PASS mutations=3")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "check", "selftest"))
    args = parser.parse_args()
    if args.command == "collect":
        receipt = write()
    elif args.command == "check":
        receipt = check()
    else:
        selftest()
        return 0
    index = receipt["index"]
    print("v11-function-metadata: PASS "
          f"records={index['records']} exact={index['exact_arity']} "
          f"unresolved={index['unresolved_arity']} delivery=host-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
