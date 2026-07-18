#!/usr/bin/env python3
"""Bind the temporary C1 compiler container to a device-side header."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zlib


FORMAT = "lisp65-v11-c1-compiler-contract-v1"


class ContractError(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _crc16(data: bytes) -> int:
    value = 0xFFFF
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = (
                ((value << 1) ^ 0x1021) & 0xFFFF
                if value & 0x8000 else (value << 1) & 0xFFFF
            )
    return value


def _validator_report(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw or raw.startswith("phase=") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        values[key] = value
    required = {
        "schema", "artifact", "artifact_bytes", "entry_count", "index_count",
        "node_count", "patch_count", "source_length", "source_crc16",
        "source_blob_off", "source_metadata_off", "blob_len", "metadata_len",
        "entries_off", "index_off", "nodes_off", "patches_off", "strings_off",
        "strings_bytes", "new_symbols", "new_name_bytes", "heap_cells",
        "arena_bytes", "root_slots", "max_graph_depth", "format_version", "gate",
    }
    missing = sorted(required - set(values))
    if missing:
        raise ContractError(f"native validator report is incomplete: {missing}")
    return values


def bind(manifest_path: Path, container_path: Path, shelf_path: Path,
         validator_report_path: Path) -> tuple[str, dict]:
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    container = container_path.read_bytes()
    shelf = json.loads(shelf_path.read_bytes())
    validator = _validator_report(validator_report_path)
    external = manifest.get("external_image")
    entries = manifest.get("entries")
    exports = manifest.get("exports")
    if manifest.get("artifact_role") != "disk-lib" or not isinstance(external, dict):
        raise ContractError("compiler manifest is not a disk-lib artifact")
    if exports != ["%c1-compile"]:
        raise ContractError("compiler tier must export exactly %c1-compile")
    if not isinstance(entries, list) or len(entries) != len(manifest.get("functions", [])):
        raise ContractError("compiler entry/function census mismatch")
    if external.get("sha256") != _sha(container):
        raise ContractError("compiler container SHA does not match its manifest")
    if external.get("bytes") != len(container):
        raise ContractError("compiler container length does not match its manifest")
    code_bytes = manifest.get("code_bytes")
    if not isinstance(code_bytes, int) or code_bytes <= 0:
        raise ContractError("compiler code_bytes must be positive")
    if external.get("code_bytes") != code_bytes:
        raise ContractError("compiler code-byte views disagree")
    version = external.get("metadata_format", {}).get("version")
    if version != 2:
        raise ContractError("C1 requires the strict L65M-v2 compiler container")
    containers = shelf.get("containers")
    if not isinstance(containers, list):
        raise ContractError("shelf contract has no container list")
    compiler_ids = [
        index for index, item in enumerate(containers)
        if isinstance(item, dict) and item.get("key") == "lcc"
        and item.get("role") == "temporary-compiler-tier"
    ]
    if len(compiler_ids) != 1 or compiler_ids[0] > 0x7f:
        raise ContractError("shelf must contain one encodable temporary compiler tier")
    shelf_id = compiler_ids[0]
    crc16 = _crc16(container)
    crc32 = zlib.crc32(container) & 0xFFFFFFFF
    numeric = {
        key: int(validator[key], 16 if key == "source_crc16" else 10)
        for key in (
            "artifact_bytes", "entry_count", "index_count", "node_count",
            "patch_count", "source_length", "source_crc16", "source_blob_off",
            "source_metadata_off", "blob_len", "metadata_len", "entries_off",
            "index_off", "nodes_off", "patches_off", "strings_off",
            "strings_bytes", "new_symbols", "new_name_bytes", "heap_cells",
            "arena_bytes", "root_slots", "max_graph_depth", "format_version",
        )
    }
    if (
        validator["schema"] != "lisp65-l65m-transport-ops-v2"
        or validator["gate"] != "PASS"
        or Path(validator["artifact"]).resolve() != container_path.resolve()
        or numeric["artifact_bytes"] != len(container)
        or numeric["source_length"] != len(container)
        or numeric["source_crc16"] != crc16
        or numeric["source_blob_off"] != 4
        or numeric["source_metadata_off"] != 4 + code_bytes
        or numeric["blob_len"] != code_bytes
        or numeric["entry_count"] != len(entries)
        or numeric["format_version"] != version
    ):
        raise ContractError("native v2 validator report does not bind the exact compiler")
    report = {
        "format": FORMAT,
        "manifest": manifest_path.as_posix(),
        "manifest_sha256": _sha(manifest_bytes),
        "container": container_path.as_posix(),
        "container_sha256": _sha(container),
        "container_bytes": len(container),
        "container_crc16_ccitt_false": f"{crc16:04x}",
        "container_crc32": f"{crc32:08x}",
        "blob_bytes": code_bytes,
        "entry_count": len(entries),
        "format_version": version,
        "shelf_contract": shelf_path.as_posix(),
        "shelf_contract_sha256": _sha(shelf_path.read_bytes()),
        "shelf_record_id": shelf_id,
        "exports": exports,
        "native_validator_report": validator_report_path.as_posix(),
        "native_validator_report_sha256": _sha(validator_report_path.read_bytes()),
        "validated_plan": numeric,
        "identity_rule": (
            "the generated shelf record and exact L65M preflight fields jointly bind "
            "all device lifetime operations"
        ),
    }
    header = """/* Generated by v11_c1_compiler_contract.py; do not edit. */
#ifndef LISP65_V11_C1_COMPILER_CONTRACT_H
#define LISP65_V11_C1_COMPILER_CONTRACT_H
#define LISP65_C1_COMPILER_CONTAINER_BYTES %du
#define LISP65_C1_COMPILER_CONTAINER_CRC16 0x%04xu
#define LISP65_C1_COMPILER_CONTAINER_CRC32 0x%08xul
#define LISP65_C1_COMPILER_CONTAINER_SHA_PREFIX_0 0x%08xul
#define LISP65_C1_COMPILER_CONTAINER_SHA_PREFIX_1 0x%08xul
#define LISP65_C1_COMPILER_CONTAINER_SHA_PREFIX_2 0x%08xul
#define LISP65_C1_COMPILER_CONTAINER_SHA_PREFIX_3 0x%08xul
#define LISP65_C1_COMPILER_BLOB_BYTES %du
#define LISP65_C1_COMPILER_ENTRY_COUNT %du
#define LISP65_C1_COMPILER_FORMAT_VERSION %du
#define LISP65_C1_COMPILER_SHELF_RECORD_ID %du
#define LISP65_C1_PLAN_INDEX_COUNT %du
#define LISP65_C1_PLAN_NODE_COUNT %du
#define LISP65_C1_PLAN_PATCH_COUNT %du
#define LISP65_C1_PLAN_METADATA_BYTES %du
#define LISP65_C1_PLAN_ENTRIES_OFF %du
#define LISP65_C1_PLAN_INDEX_OFF %du
#define LISP65_C1_PLAN_NODES_OFF %du
#define LISP65_C1_PLAN_PATCHES_OFF %du
#define LISP65_C1_PLAN_STRINGS_OFF %du
#define LISP65_C1_PLAN_STRINGS_BYTES %du
#define LISP65_C1_PLAN_SYMBOL_CEILING %du
#define LISP65_C1_PLAN_NAME_BYTES_CEILING %du
#define LISP65_C1_PLAN_HEAP_CELLS %du
#define LISP65_C1_PLAN_ARENA_BYTES %du
#define LISP65_C1_PLAN_ROOT_SLOTS %du
#define LISP65_C1_PLAN_MAX_GRAPH_DEPTH %du
#endif
""" % (
        len(container), crc16, crc32,
        *[int.from_bytes(bytes.fromhex(_sha(container))[at:at + 4], "little")
          for at in range(0, 16, 4)],
        code_bytes, len(entries), version, shelf_id,
        numeric["index_count"], numeric["node_count"], numeric["patch_count"],
        numeric["metadata_len"], numeric["entries_off"], numeric["index_off"],
        numeric["nodes_off"], numeric["patches_off"], numeric["strings_off"],
        numeric["strings_bytes"], numeric["new_symbols"],
        numeric["new_name_bytes"], numeric["heap_cells"],
        numeric["arena_bytes"], numeric["root_slots"],
        numeric["max_graph_depth"],
    )
    return header, report


def selftest() -> None:
    with tempfile.TemporaryDirectory(prefix="c1-contract-") as raw:
        root = Path(raw)
        container = b"\x04\x00\x00\x00test"
        container_path = root / "lcc.ext.bin"
        manifest_path = root / "lcc.manifest.json"
        shelf_path = root / "shelf.json"
        validator_path = root / "validator.txt"
        container_path.write_bytes(container)
        manifest = {
            "artifact_role": "disk-lib",
            "exports": ["%c1-compile"],
            "functions": ["%c1-compile"],
            "entries": [{"name": "%c1-compile"}],
            "code_bytes": 4,
            "external_image": {
                "bytes": len(container),
                "code_bytes": 4,
                "sha256": _sha(container),
                "metadata_format": {"version": 2},
            },
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        shelf_path.write_text(json.dumps({"containers": [
            {"key": "buffer", "role": "first-class-buffer"},
            {"key": "lcc", "role": "temporary-compiler-tier"},
        ]}), encoding="utf-8")
        crc16 = _crc16(container)
        validator_path.write_text("\n".join([
            "schema=lisp65-l65m-transport-ops-v2", f"artifact={container_path}",
            f"artifact_bytes={len(container)}", "entry_count=1", "index_count=0",
            "node_count=0", "patch_count=0", f"source_length={len(container)}",
            f"source_crc16={crc16:04x}", "source_blob_off=4",
            "source_metadata_off=8", "blob_len=4", "metadata_len=0",
            "entries_off=38", "index_off=46", "nodes_off=46", "patches_off=46",
            "strings_off=46", "strings_bytes=0", "new_symbols=1",
            "new_name_bytes=4", "heap_cells=0", "arena_bytes=0", "root_slots=0",
            "max_graph_depth=1", "format_version=2", "gate=PASS", "",
        ]), encoding="utf-8")
        first = bind(manifest_path, container_path, shelf_path, validator_path)
        second = bind(manifest_path, container_path, shelf_path, validator_path)
        if first != second:
            raise ContractError("contract generation is not deterministic")
        manifest["external_image"]["sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        try:
            bind(manifest_path, container_path, shelf_path, validator_path)
        except ContractError:
            pass
        else:
            raise ContractError("mutated container binding was accepted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--container", type=Path)
    parser.add_argument("--shelf-contract", type=Path)
    parser.add_argument("--validator-report", type=Path)
    parser.add_argument("--header", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    try:
        if args.selftest:
            selftest()
            print("v11-c1-compiler-contract: SELFTEST PASS")
            return 0
        if not all((args.manifest, args.container, args.shelf_contract,
                    args.validator_report,
                    args.header, args.receipt)):
            raise ContractError(
                "manifest, container, shelf-contract, header and receipt are required")
        header, report = bind(args.manifest, args.container, args.shelf_contract,
                              args.validator_report)
        args.header.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.header.write_text(header, encoding="utf-8")
        args.receipt.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except (ContractError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"v11-c1-compiler-contract: FAIL: {exc}")
        return 1
    print(
        "v11-c1-compiler-contract: PASS bytes=%d entries=%d crc16=%s"
        % (report["container_bytes"], report["entry_count"],
           report["container_crc16_ccitt_false"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
