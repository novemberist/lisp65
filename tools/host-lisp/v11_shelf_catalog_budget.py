#!/usr/bin/env python3
"""Bind the standing u16 Attic-shelf catalog budget to canonical artifacts."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SHELF = ROOT / "build/bytecode/dialect-v2/shelf/library-shelf.bin"
MANIFEST = ROOT / "build/bytecode/dialect-v2/shelf/library-shelf-manifest.json"
CONTRACT = ROOT / "config/v11-attic-library-shelf.json"
BUILDER = ROOT / "tools/host-lisp/v11_attic_library_shelf.py"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-shelf-catalog-headroom-receipt.json"
)
U16_LIMIT = 0xFFFF


class BudgetError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BudgetError(message)


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BudgetError(f"cannot read {label}: {exc}") from exc
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def binding(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing regular artifact: {path}")
    payload = path.read_bytes()
    return {
        "path": rel(path),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def collect() -> dict[str, Any]:
    manifest = load(MANIFEST, "shelf manifest")
    contract = load(CONTRACT, "shelf contract")
    require(manifest.get("format") == "lisp65-v11-attic-library-shelf-manifest-v1",
            "shelf manifest format drift")
    require(contract.get("format") == "lisp65-v11-attic-library-shelf-contract-v1",
            "shelf contract format drift")
    shelf_bytes = SHELF.stat().st_size
    require(manifest.get("shelf_bytes") == shelf_bytes, "manifest shelf length drift")
    require(manifest.get("shelf_sha256") == binding(SHELF)["sha256"],
            "manifest shelf SHA drift")
    rows = manifest.get("containers")
    contract_rows = contract.get("containers")
    require(isinstance(rows, list), "shelf manifest containers must be a list")
    require(isinstance(contract_rows, list) and contract_rows,
            "shelf contract containers must be a nonempty list")
    expected_keys = [row.get("key") for row in contract_rows]
    require(len(rows) == len(expected_keys), "shelf container count drift")
    require([row.get("key") for row in rows] == expected_keys,
            "shelf container order drift")
    require(shelf_bytes <= U16_LIMIT, "canonical shelf exceeds the u16 catalog")

    containers = []
    for row in rows:
        container = ROOT / str(row["container"])
        container_manifest = ROOT / str(row["manifest"])
        container_binding = binding(container)
        manifest_binding = binding(container_manifest)
        require(row.get("bytes") == container_binding["bytes"],
                f"container length drift: {row.get('key')}")
        require(row.get("container_sha256") == container_binding["sha256"],
                f"container SHA drift: {row.get('key')}")
        require(row.get("manifest_sha256") == manifest_binding["sha256"],
                f"container manifest SHA drift: {row.get('key')}")
        containers.append({
            "key": row["key"],
            "role": row["role"],
            "attic_offset": row["attic_offset"],
            "container": container_binding,
            "manifest": manifest_binding,
        })

    return {
        "format": "lisp65-v11-shelf-catalog-budget-receipt-v1",
        "version": 1,
        "status": "canonical-five-container-budget-after-trio-fallback",
        "recorded_on": "2026-07-17",
        "encoding_limit_bytes": U16_LIMIT,
        "shelf_bytes": shelf_bytes,
        "catalog_headroom_bytes": U16_LIMIT - shelf_bytes,
        "utilization_basis_points": (shelf_bytes * 10000) // U16_LIMIT,
        "standing_rule": (
            "Recompute and review this number before every Wave-3 planning pass; "
            "no shelf module may consume unreviewed catalog headroom."
        ),
        "claim_limit": (
            "Canonical host shelf capacity only; this receipt makes no claim about "
            "future Wave-3 modules or an extended catalog format."
        ),
        "canonical_state": {
            "containers": 5,
            "shelf_bytes": 65368,
            "catalog_headroom_bytes": 167,
            "note": "The unpromoted room record was removed after the one permitted carrier attempt failed.",
        },
        "rejected_candidate_history": {
            "containers": 6,
            "shelf_bytes": 65528,
            "catalog_headroom_bytes": 7,
            "room_container_bytes": 128,
            "catalog_record_bytes": 32,
            "claim": "Historical capacity observation only; never promoted.",
        },
        "bindings": {
            "shelf": binding(SHELF),
            "shelf_manifest": binding(MANIFEST),
            "shelf_contract": binding(CONTRACT),
            "shelf_builder": binding(BUILDER),
        },
        "containers": containers,
    }


def write() -> dict[str, Any]:
    value = collect()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return value


def check() -> dict[str, Any]:
    actual = load(RECEIPT, "shelf budget receipt")
    expected = collect()
    require(actual == expected, "shelf budget receipt does not bind current artifacts")
    return actual


def selftest() -> None:
    sample = {"shelf_bytes": 65368, "catalog_headroom_bytes": 167}
    for label, mutation in (
        ("shelf", lambda value: value.update(shelf_bytes=65369)),
        ("headroom", lambda value: value.update(catalog_headroom_bytes=168)),
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
            print("v11-shelf-catalog-budget: SELFTEST PASS mutations=2")
            return 0
        value = write() if args.command == "collect" else check()
    except (BudgetError, OSError, ValueError, KeyError) as exc:
        print(f"v11-shelf-catalog-budget: FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "v11-shelf-catalog-budget: PASS "
        f"bytes={value['shelf_bytes']} headroom={value['catalog_headroom_bytes']} "
        f"limit={value['encoding_limit_bytes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
