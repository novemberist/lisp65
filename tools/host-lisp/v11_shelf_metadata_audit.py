#!/usr/bin/env python3
"""Bind the Wave-3 shelf metadata arithmetic and load-time classification."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SHELF = ROOT / "build/bytecode/dialect-v2/shelf/library-shelf.bin"
SHELF_MANIFEST = ROOT / "build/bytecode/dialect-v2/shelf/library-shelf-manifest.json"
SHELF_CONTRACT = ROOT / "config/v11-attic-library-shelf.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-shelf-metadata-audit-receipt.json"
)
LIBRARIES = ("ide", "idex", "m65d", "buffer", "lcc")
HEADER_BYTES = 38
ENTRY_BYTES = 8
INDEX_BYTES = 2
NODE_BYTES = 10
PATCH_BYTES = 4
SHELF_PREFIX_BYTES = 192


class AuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"cannot read {label}: {exc}") from exc
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def binding(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing regular binding: {path}")
    data = path.read_bytes()
    return {"path": rel(path), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def u16(data: bytes, at: int) -> int:
    require(at + 2 <= len(data), f"u16 outside image at {at}")
    return struct.unpack_from("<H", data, at)[0]


def library_row(key: str, manifest_path: Path) -> dict[str, Any]:
    manifest = load(manifest_path, f"{key} manifest")
    image = manifest.get("external_image")
    require(isinstance(image, dict), f"{key} external_image missing")
    image_path = ROOT / str(image.get("path", ""))
    data = image_path.read_bytes()
    code_bytes = u16(data, 0)
    metadata_bytes = u16(data, 2)
    require(len(data) == 4 + code_bytes + metadata_bytes,
            f"{key} file prefix does not close")
    require(code_bytes == image.get("code_bytes") == manifest.get("code_bytes"),
            f"{key} code length drift")
    require(metadata_bytes == image.get("metadata_bytes"),
            f"{key} metadata length drift")
    md = data[4 + code_bytes:]
    require(md[:4] == b"L65M" and md[5] == HEADER_BYTES,
            f"{key} metadata header drift")
    require(u16(md, 12) == code_bytes and u16(md, 14) == metadata_bytes,
            f"{key} header length mismatch")
    entry_count = u16(md, 16)
    index_count = u16(md, 18)
    node_count = u16(md, 20)
    patch_count = u16(md, 22)
    entries_off = u16(md, 24)
    index_off = u16(md, 26)
    nodes_off = u16(md, 28)
    patches_off = u16(md, 30)
    strings_off = u16(md, 32)
    strings_bytes = u16(md, 34)
    require(entries_off == HEADER_BYTES, f"{key} entries offset drift")
    require(index_off == entries_off + entry_count * ENTRY_BYTES,
            f"{key} index offset drift")
    require(nodes_off == index_off + index_count * INDEX_BYTES,
            f"{key} node offset drift")
    require(patches_off == nodes_off + node_count * NODE_BYTES,
            f"{key} patch offset drift")
    require(strings_off == patches_off + patch_count * PATCH_BYTES,
            f"{key} string offset drift")
    require(metadata_bytes == (strings_off + strings_bytes + 1) & ~1,
            f"{key} metadata alignment drift")
    require(len(manifest.get("entries", [])) == entry_count,
            f"{key} entry count differs from manifest")
    require(len(manifest.get("literal_index", [])) == index_count,
            f"{key} literal-index count differs from manifest")
    require(len(manifest.get("literal_nodes", [])) == node_count,
            f"{key} literal-node count differs from manifest")
    require(len(manifest.get("literal_patches", [])) == patch_count,
            f"{key} literal-patch count differs from manifest")
    sections = {
        "header": HEADER_BYTES,
        "entries": entry_count * ENTRY_BYTES,
        "literal_index": index_count * INDEX_BYTES,
        "literal_nodes": node_count * NODE_BYTES,
        "literal_patches": patch_count * PATCH_BYTES,
        "string_pool_bytes": strings_bytes,
        "string_region_with_alignment": metadata_bytes - strings_off,
    }
    require(sum((sections["header"], sections["entries"],
                 sections["literal_index"], sections["literal_nodes"],
                 sections["literal_patches"],
                 sections["string_region_with_alignment"])) == metadata_bytes,
            f"{key} metadata section arithmetic does not close")
    return {
        "key": key,
        "container": binding(image_path),
        "manifest": binding(manifest_path),
        "code_bytes": code_bytes,
        "metadata_bytes": metadata_bytes,
        "metadata_percent_of_container": round(metadata_bytes * 100 / len(data), 4),
        "counts": {
            "entries": entry_count,
            "literal_index": index_count,
            "literal_nodes": node_count,
            "literal_patches": patch_count,
        },
        "sections": sections,
    }


def collect() -> dict[str, Any]:
    shelf_manifest = load(SHELF_MANIFEST, "shelf manifest")
    shelf_contract = load(SHELF_CONTRACT, "shelf contract")
    contract_rows = shelf_contract.get("containers")
    require(isinstance(contract_rows, list), "shelf contract containers missing")
    require([row.get("key") for row in contract_rows] == list(LIBRARIES),
            "canonical shelf library order drift")
    manifest_rows = shelf_manifest.get("containers")
    require(isinstance(manifest_rows, list), "shelf manifest containers missing")
    require([row.get("key") for row in manifest_rows] == list(LIBRARIES),
            "shelf manifest library order drift")
    require(SHELF.stat().st_size == shelf_manifest.get("shelf_bytes") == 65368,
            "canonical shelf length drift")

    rows = []
    for contract_row, shelf_row in zip(contract_rows, manifest_rows):
        manifest_path = ROOT / str(contract_row["manifest"])
        require(rel(manifest_path) == shelf_row.get("manifest"),
                f"shelf manifest binding drift: {contract_row['key']}")
        row = library_row(str(contract_row["key"]), manifest_path)
        require(row["container"]["bytes"] == shelf_row.get("bytes"),
                f"shelf container length drift: {row['key']}")
        require(row["container"]["sha256"] == shelf_row.get("container_sha256"),
                f"shelf container SHA drift: {row['key']}")
        rows.append(row)

    totals = {
        "containers": sum(row["container"]["bytes"] for row in rows),
        "code": sum(row["code_bytes"] for row in rows),
        "metadata": sum(row["metadata_bytes"] for row in rows),
        "file_headers": len(rows) * 4,
        "shelf_alignment": SHELF.stat().st_size - SHELF_PREFIX_BYTES
            - sum(row["container"]["bytes"] for row in rows),
        "metadata_headers": sum(row["sections"]["header"] for row in rows),
        "entries": sum(row["sections"]["entries"] for row in rows),
        "literal_index": sum(row["sections"]["literal_index"] for row in rows),
        "literal_nodes": sum(row["sections"]["literal_nodes"] for row in rows),
        "literal_patches": sum(row["sections"]["literal_patches"] for row in rows),
        "string_pool_bytes": sum(row["sections"]["string_pool_bytes"] for row in rows),
        "string_regions_with_alignment": sum(
            row["sections"]["string_region_with_alignment"] for row in rows
        ),
    }
    totals["literal_machinery"] = (
        totals["literal_index"] + totals["literal_nodes"] + totals["literal_patches"]
    )
    totals["literal_machinery_plus_string_regions"] = (
        totals["literal_machinery"] + totals["string_regions_with_alignment"]
    )
    payload_bytes = SHELF.stat().st_size - SHELF_PREFIX_BYTES
    require(totals == {
        "containers": 65175,
        "code": 28895,
        "metadata": 36260,
        "file_headers": 20,
        "shelf_alignment": 1,
        "metadata_headers": 190,
        "entries": 2976,
        "literal_index": 3474,
        "literal_nodes": 17370,
        "literal_patches": 6900,
        "string_pool_bytes": 5347,
        "string_regions_with_alignment": 5350,
        "literal_machinery": 27744,
        "literal_machinery_plus_string_regions": 33094,
    }, "canonical metadata totals drift")
    require(SHELF_PREFIX_BYTES + totals["containers"] + totals["shelf_alignment"]
            == SHELF.stat().st_size, "shelf arithmetic does not close")
    require(totals["metadata_headers"] + totals["entries"]
            + totals["literal_machinery"] + totals["string_regions_with_alignment"]
            == totals["metadata"], "metadata arithmetic does not close")

    sources = (
        ROOT / "tools/host-lisp/l65m_contract.py",
        ROOT / "src/l65m_validate.c",
        ROOT / "src/l65m_commit_overlay.c",
        ROOT / "src/l65m_validate.h",
        ROOT / "src/l65m_commit_overlay.h",
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    for marker in ("literal_index", "literal_nodes", "literal_patches",
                   "strings_off", "source_metadata_off"):
        require(marker in combined, f"load-time source marker missing: {marker}")

    return {
        "format": "lisp65-v11-shelf-metadata-audit-receipt-v1",
        "version": 1,
        "status": "audit-confirmed-input-to-one-v4-probe",
        "recorded_on": "2026-07-18",
        "claim_limit": (
            "Exact current-manifest arithmetic and current-loader ownership only. "
            "This receipt does not claim that a side-file split is implemented, "
            "capacity-neutral, or media-independent."
        ),
        "shelf": {
            "bytes": SHELF.stat().st_size,
            "prefix_bytes": SHELF_PREFIX_BYTES,
            "payload_bytes": payload_bytes,
            "metadata_percent_of_whole_shelf": round(totals["metadata"] * 100
                                                       / SHELF.stat().st_size, 4),
            "metadata_percent_of_payload_region": round(totals["metadata"] * 100
                                                         / payload_bytes, 4),
            "binding": binding(SHELF),
            "manifest": binding(SHELF_MANIFEST),
            "contract": binding(SHELF_CONTRACT),
        },
        "totals": totals,
        "libraries": rows,
        "classification": {
            "literal_machinery": "load-time materialization input",
            "entry_table": "load-time publication input",
            "string_pool": "shared by load-time literal materialization and entry publication",
            "post_commit_retention": "no metadata pointer is part of the published code/directory ABI",
            "important_limit": (
                "Moving bytes outside the u16 shelf still requires an identity-bound, "
                "reset-persistent source. A D81-only side file would regress the one-swap "
                "media contract and is not an accepted implementation."
            ),
            "source_bindings": [binding(path) for path in sources],
        },
        "audit_correction": {
            "55.6_percent_denominator": "65,176-byte shelf payload region",
            "whole_shelf_percent_one_decimal": 55.5,
            "payload_region_percent_one_decimal": 55.6,
            "raw_string_bytes": 5347,
            "reclaimable_string_regions_including_alignment": 5350,
        },
    }


def write() -> dict[str, Any]:
    value = collect()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return value


def check() -> dict[str, Any]:
    actual = load(RECEIPT, "metadata audit receipt")
    expected = collect()
    require(actual == expected, "metadata audit receipt does not bind current inputs")
    return actual


def selftest() -> None:
    sample = {"metadata": 36260, "literal_machinery": 27744,
              "string_regions": 5350, "payload_percent": 55.6}
    for label, mutation in (
        ("metadata", lambda value: value.update(metadata=36259)),
        ("literal", lambda value: value.update(literal_machinery=27743)),
        ("strings", lambda value: value.update(string_regions=5347)),
        ("denominator", lambda value: value.update(payload_percent=55.5)),
    ):
        candidate = copy.deepcopy(sample)
        mutation(candidate)
        require(candidate != sample, f"selftest mutation survived: {label}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "check", "selftest"))
    args = parser.parse_args()
    try:
        if args.command == "selftest":
            selftest()
            print("v11-shelf-metadata-audit: SELFTEST PASS mutations=4")
            return 0
        value = write() if args.command == "collect" else check()
    except (AuditError, OSError, ValueError, KeyError, struct.error) as exc:
        print(f"v11-shelf-metadata-audit: FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "v11-shelf-metadata-audit: PASS "
        f"metadata={value['totals']['metadata']} "
        f"literal={value['totals']['literal_machinery']} "
        f"strings={value['totals']['string_regions_with_alignment']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
