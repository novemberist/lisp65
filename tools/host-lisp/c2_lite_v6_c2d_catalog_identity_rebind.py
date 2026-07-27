#!/usr/bin/env python3
"""Re-emit Link-40 C2D-v6 with the canonical L65S catalog identity.

This is the approved artifact-only successor to the product-build identity
rebind.  It audits every header byte, changes only catalog_crc32, and never
compiles or links product code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_product_probe as V6  # noqa: E402


OUT = ROOT / "build/c2.2/c2d-v6-catalog-identity-rebind-link40"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link40-c2d-v6-catalog-identity-rebind-receipt.json"
)
PRIOR_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link40-c2d-v6-product-identity-rebind-receipt.json"
)
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link40-c2d-v6-shelf-catalog-hardware-first-red-diagnosis.json"
)
LINK40 = ROOT / "build/c2.2/substitution/product-link-40-c2-lite-v6-real-abi-e000"


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def bound(path: Path, row: dict[str, Any], label: str) -> None:
    require(path.is_file() and row == bind(path), f"{label} binding drift")


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "C2D-v6 catalog rebind output already exists")
    require(PRIOR_RECEIPT.is_file() and FIRST_RED.is_file(),
            "catalog rebind authority is incomplete")
    prior = json.loads(PRIOR_RECEIPT.read_text(encoding="utf-8"))
    require(prior.get("status") ==
            "passed-c2d-v6-canonical-product-identity-hardware-not-run",
            "prior product-identity rebind is not passed")
    old_row = prior.get("corrected_c2d", {}).get("new", {})
    old_code_row = prior.get("corrected_c2d", {}).get("bank2_static", {})
    require(isinstance(old_row.get("path"), str)
            and isinstance(old_code_row.get("path"), str),
            "prior rebind lacks corrected plane bindings")
    old_path = ROOT / old_row["path"]
    old_code_path = ROOT / old_code_row["path"]
    bound(old_path, old_row, "prior corrected C2D-v6")
    bound(old_code_path, old_code_row, "prior Bank-2 plane")

    product = LINK40 / "lisp65-c2-substitution-linked.prg"
    elf = LINK40 / "lisp65-c2-substitution-linked.prg.elf"
    bound(product, prior["product_identity"]["product"], "Link-40 product")
    bound(elf, prior["product_identity"]["elf"], "Link-40 ELF")

    OUT.mkdir(parents=True)
    old_out = V6.OUT
    old_emitter = (V6._ENTRY_EMITTER, V6._ENTRY_EMITTER_PATH)
    try:
        V6.OUT = OUT / "v6-semantics"
        V6.OUT.mkdir()
        V6._ENTRY_EMITTER = None
        V6._ENTRY_EMITTER_PATH = None
        host = V6.host_semantics()
    finally:
        V6.OUT = old_out
        V6._ENTRY_EMITTER, V6._ENTRY_EMITTER_PATH = old_emitter

    new_path = OUT / "v6-semantics/initial.c2d-v6.bin"
    new_code_path = OUT / "v6-semantics/bank2-static-code.bin"
    old = old_path.read_bytes()
    new = new_path.read_bytes()
    require(len(old) == len(new) == V6.C2D_TOTAL_BYTES,
            "C2D-v6 plane width changed")
    changed = [index for index, (before, after) in enumerate(zip(old, new))
               if before != after]
    require(changed == [40, 41, 42, 43],
            f"catalog rebind changed bytes outside catalog_crc32: {changed}")
    old_crc = struct.unpack_from("<I", old, 40)[0]
    new_crc = struct.unpack_from("<I", new, 40)[0]
    old_build = struct.unpack_from("<I", old, 44)[0]
    new_build = struct.unpack_from("<I", new, 44)[0]
    authority = V6.canonical_product_shelf_identity()
    require(old_crc == 0xD3186BEC
            and new_crc == authority["catalog_crc32"] == 0x3D6302F3,
            "C2D-v6 catalog transition differs from diagnosed repair")
    require(old_build == new_build == authority["product_build_id"] == 0x69496476,
            "catalog repair disturbed the canonical product identity")
    require(new_code_path.read_bytes() == old_code_path.read_bytes(),
            "Bank-2 executable plane changed during catalog rebind")

    audit = host.get("c2d_v6_header_source_audit", {})
    require(audit.get("status") == "passed-all-48-header-bytes-accounted"
            and audit.get("covered_byte_count") == 48
            and audit.get("field_count") == 23
            and audit.get("private_identity_derivations") == [],
            "C2D-v6 header source audit is incomplete")
    shelf_identity = host.get("product_shelf_identity", {})
    require(shelf_identity.get("catalog_crc32") == "0x3d6302f3"
            and shelf_identity.get("immutable_image_count") == 6
            and shelf_identity.get("private_derivation_sites") == 0,
            "fresh semantics did not consume the canonical shelf identity")
    fixtures = set(host.get("negative_fixtures", []))
    required_fixtures = {
        "c2d-product-build-identity-mismatch",
        "c2d-zero-product-build-identity",
        "c2d-shelf-catalog-identity-mismatch",
        "c2d-zero-shelf-catalog-identity",
        "c2d-immutable-image-count-mismatch",
    }
    require(required_fixtures <= fixtures,
            "fresh header identity mutations did not all run")

    header_values = {
        "transient_entry_watermark": struct.unpack_from("<H", new, 8)[0],
        "session_generation": struct.unpack_from("<H", new, 10)[0],
        "image_count": struct.unpack_from("<H", new, 12)[0],
        "entry_count": struct.unpack_from("<H", new, 16)[0],
        "resolution_count": struct.unpack_from("<H", new, 20)[0],
        "root_count": struct.unpack_from("<H", new, 24)[0],
        "immutable_image_count": struct.unpack_from("<H", new, 38)[0],
        "product_shelf_catalog_crc32": f"0x{new_crc:08x}",
        "product_build_id_u32": f"0x{new_build:08x}",
    }
    value = {
        "format": "lisp65-c2-lite-v6-c2d-catalog-identity-rebind-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-c2d-v6-canonical-header-identities-hardware-not-run",
        "authority": {
            "prior_product_identity_rebind": bind(PRIOR_RECEIPT),
            "catalog_first_red": bind(FIRST_RED),
            "product_identity": bind(V6.PRODUCT_IDENTITY),
            "product_shelf": authority["shelf"],
        },
        "execution_accounting": {
            "product_compiler_runs": 0,
            "product_linker_runs": 0,
            "product_links": 0,
            "host_entry_emitter_compiles": 1,
            "hardware_runs": 0,
            "product_bytes_changed": 0,
            "c2d_header_bytes_changed": 4,
        },
        "product_identity": {"product": bind(product), "elf": bind(elf)},
        "corrected_c2d": {
            "status": "passed",
            "old": bind(old_path),
            "new": bind(new_path),
            "bank2_static": bind(new_code_path),
            "changed_offsets": changed,
            "old_catalog_crc32": f"0x{old_crc:08x}",
            "new_catalog_crc32": f"0x{new_crc:08x}",
            "product_build_id_unchanged": f"0x{new_build:08x}",
            "all_noncatalog_bytes_equal": True,
            "executable_plane_byte_identical": True,
        },
        "header_source_audit": audit,
        "header_values": header_values,
        "fresh_host_semantics": host,
        "presmoke_authorization": {
            "candidate": LINK40.relative_to(ROOT).as_posix(),
            "corrected_c2d_path": new_path.relative_to(ROOT).as_posix(),
            "link40_prg_unchanged": True,
            "link40_elf_unchanged": True,
        },
        "claim_limit": (
            "Fresh C2D-v6 host semantics, a complete 48-byte header-source "
            "audit and one exact four-byte catalog identity correction. "
            "Link-40 executable bytes are unchanged; hardware, latency, "
            "promotion and acceptance remain not run."
        ),
        "next_gate": "fresh receipt-less hardware presmoke from line 1",
    }
    report_path = OUT / "c2d-v6-catalog-identity-rebind.json"
    write_json(report_path, value)
    value["report"] = bind(report_path)
    write_json(RECEIPT, value)
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(RECEIPT, 0o444)
    return value


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "C2D-v6 catalog rebind receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") ==
            "passed-c2d-v6-canonical-header-identities-hardware-not-run",
            "C2D-v6 catalog rebind receipt is not passed")
    rows = [
        value["authority"]["prior_product_identity_rebind"],
        value["authority"]["catalog_first_red"],
        value["authority"]["product_identity"],
        value["authority"]["product_shelf"],
        value["product_identity"]["product"],
        value["product_identity"]["elf"],
        value["corrected_c2d"]["old"],
        value["corrected_c2d"]["new"],
        value["corrected_c2d"]["bank2_static"],
        value["report"],
    ]
    for row in rows:
        bound(ROOT / row["path"], row, "catalog rebind evidence")
    new = (ROOT / value["corrected_c2d"]["new"]["path"]).read_bytes()
    authority = V6.canonical_product_shelf_identity()
    require(struct.unpack_from("<I", new, 40)[0] == authority["catalog_crc32"]
            and struct.unpack_from("<I", new, 44)[0] ==
                authority["product_build_id"],
            "corrected C2D-v6 header identity drift")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("build", "check"))
    args = parser.parse_args()
    value = build() if args.mode == "build" else check()
    print("c2-lite-v6-c2d-catalog-identity-rebind: " + value["status"])


if __name__ == "__main__":
    main()
