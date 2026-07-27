#!/usr/bin/env python3
"""Audit every C2D-v6 header field and every product header writer."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_product_probe as V6  # noqa: E402


RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-header-source-audit-receipt.json"
)
REBINDED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link40-c2d-v6-catalog-identity-rebind-receipt.json"
)
RUNTIME_SOURCE = ROOT / "src/c2_product_runtime.c"
PRODUCT_RUNTIME_SOURCE = ROOT / (
    "build/c2.2/substitution/product-link-40-c2-lite-v6-real-abi-e000/"
    "generated-product-sources/c2_product_runtime.c"
)
DECODER_SOURCE = ROOT / "scripts/c2-stream-decoder.c"


class AuditError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AuditError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def function_body(source: str, name: str) -> str:
    match = re.search(rf"\b{name}\s*\([^;]*?\)\s*\{{", source, re.S)
    require(match is not None, f"missing function body: {name}")
    start = match.end() - 1
    depth = 0
    for at in range(start, len(source)):
        if source[at] == "{":
            depth += 1
        elif source[at] == "}":
            depth -= 1
            if depth == 0:
                return source[start:at + 1]
    raise AuditError(f"unterminated function body: {name}")


def assigned_offsets(body: str) -> list[int]:
    return sorted({int(value) for value in re.findall(
        r"\b(?:header|old_header|new_header)\s*\[\s*(\d+)\s*\]\s*=(?!=)",
        body)})


def audit_runtime_writer(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    watermark = function_body(source, "c2_header_watermark")
    counts = function_body(source, "c2_header_counts")
    prepare = function_body(source, "c2_product_prepare_boot")
    publish = function_body(source, "c2_append_header_phase")
    rollback = function_body(source, "c2_append_rollback_unpublish_phase")
    require(assigned_offsets(watermark) == [8, 9],
            "watermark helper writes outside its local field")
    require(assigned_offsets(counts) == [12, 13, 16, 17, 20, 21, 24, 25],
            "count helper writes outside active-count fields")
    for name, body in (("prepare", prepare), ("publish", publish),
                       ("rollback", rollback)):
        require(not any(offset >= 38 for offset in assigned_offsets(body)),
                f"{name} privately assigns a canonical header field")
    require("c2_stream_c2d_read(0u, header, sizeof header)" in prepare
            and "c2_header_watermark(header, C2D_HANDLE_CAP)" in prepare
            and "c2_stream_c2d_write(0u, header, sizeof header)" in prepare,
            "restage writer no longer preserves the authenticated header")
    require("w->new_header[i] = w->old_header[i]" in publish
            and "c2_header_counts(w->new_header" in publish
            and "c2_header_watermark(w->new_header" in publish,
            "append writer no longer derives from the authenticated predecessor")
    require("c2_stream_c2d_read(0, w->old_header" in rollback
            and "c2_header_counts(w->old_header" in rollback
            and "c2_header_watermark(w->old_header" in rollback,
            "rollback writer no longer restores an authenticated snapshot")
    identity_assignments = []
    for offset in range(38, 48):
        for match in re.finditer(
                rf"\b(?:header|old_header|new_header)\s*\[\s*{offset}\s*\]"
                r"\s*=(?!=)", source):
            identity_assignments.append({
                "offset": offset,
                "line": source.count("\n", 0, match.start()) + 1,
            })
    require(not identity_assignments,
            "product runtime contains a private canonical-field assignment")
    zero_header_writes = len(re.findall(
        r"c2_stream_c2d_write\(0u?\s*,", source))
    require(zero_header_writes == 7,
            f"unexpected C2D header writer inventory: {zero_header_writes}")
    return {
        "source": bind(path),
        "header_write_calls": zero_header_writes,
        "canonical_field_assignments": identity_assignments,
        "allowed_direct_assignment_offsets": {
            "watermark": assigned_offsets(watermark),
            "active_counts": assigned_offsets(counts),
        },
        "restage_preserves_canonical_fields": True,
        "append_preserves_canonical_fields": True,
        "rollback_preserves_canonical_fields": True,
    }


def build() -> dict[str, Any]:
    require(not RECEIPT.exists(), "C2D-v6 header audit receipt already exists")
    correction = json.loads(REBINDED.read_text(encoding="utf-8"))
    require(correction.get("status") ==
            "passed-c2d-v6-canonical-header-identities-hardware-not-run",
            "catalog correction is not passed")
    c2d_row = correction["corrected_c2d"]["new"]
    c2d_path = ROOT / c2d_row["path"]
    require(bind(c2d_path) == c2d_row, "corrected C2D binding drift")
    c2d = c2d_path.read_bytes()
    authority = V6.canonical_product_shelf_identity()
    field_audit = V6.header_source_audit()
    require(field_audit["covered_byte_count"] == 48
            and field_audit["private_identity_derivations"] == [],
            "field-source audit is incomplete")
    require(struct.unpack_from("<H", c2d, 38)[0] == authority["image_count"]
            and struct.unpack_from("<I", c2d, 40)[0] ==
                authority["catalog_crc32"]
            and struct.unpack_from("<I", c2d, 44)[0] ==
                authority["product_build_id"],
            "corrected C2D canonical header values drift")

    current = audit_runtime_writer(RUNTIME_SOURCE)
    linked = audit_runtime_writer(PRODUCT_RUNTIME_SOURCE)
    decoder = DECODER_SOURCE.read_text(encoding="utf-8")
    require("r32(h + 40) != c->catalog_crc32" in decoder
            and "r32(h + 44) != (uint32_t)LISP65_C2_PRODUCT_BUILD_ID" in decoder
            and "r32(h + 18) != c->catalog_crc32" in decoder,
            "decoder lost canonical C2D/shelf cross-binding")
    value = {
        "format": "lisp65-c2-lite-v6-header-source-audit-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-all-header-fields-and-product-writers-accounted",
        "authority": {
            "catalog_correction": bind(REBINDED),
            "corrected_c2d": c2d_row,
            "product_shelf": authority["shelf"],
            "product_identity": authority["authority"],
        },
        "field_source_audit": field_audit,
        "writer_inventory": [
            {
                "writer": "pristine host C2D-v6 emitter",
                "operation": "constructs all 48 bytes",
                "canonical_fields": "consumed from self-verified shelf authority",
            },
            {
                "writer": "c2_product_prepare_boot",
                "operation": "authenticated predecessor copy; watermark only",
                "direct_write_offsets": [8, 9],
            },
            {
                "writer": "c2_append_header_phase",
                "operation": "authenticated predecessor copy; watermark or active counts",
                "direct_write_offsets": [8, 9, 12, 13, 16, 17, 20, 21, 24, 25],
            },
            {
                "writer": "append rollback paths",
                "operation": "restore authenticated snapshot; watermark or active counts",
                "direct_write_offsets": [8, 9, 12, 13, 16, 17, 20, 21, 24, 25],
            },
        ],
        "product_writer_checks": {
            "current_source": current,
            "linked_link40_generated_source": linked,
            "canonical_field_assignment_count": 0,
            "identity_fields_preserved_byte_for_byte_after_pristine_emission": True,
        },
        "decoder_cross_binding": {
            "source": bind(DECODER_SOURCE),
            "c2d_build_id_to_product": True,
            "c2d_catalog_crc_to_shelf_header": True,
            "shelf_header_crc_to_recomputed_catalog": True,
        },
        "execution_accounting": {
            "product_compiler_runs": 0,
            "product_linker_runs": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "product_bytes_changed": 0,
        },
        "claim_limit": (
            "Paper/source audit of the complete C2D-v6 header and every current "
            "product header writer. It changes no product or deployment byte."
        ),
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    return value


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "C2D-v6 header audit receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") ==
            "passed-all-header-fields-and-product-writers-accounted",
            "C2D-v6 header audit is not passed")
    for row in (
        value["authority"]["catalog_correction"],
        value["authority"]["corrected_c2d"],
        value["authority"]["product_shelf"],
        value["authority"]["product_identity"],
        value["product_writer_checks"]["current_source"]["source"],
        value["product_writer_checks"]["linked_link40_generated_source"]["source"],
        value["decoder_cross_binding"]["source"],
    ):
        require(bind(ROOT / row["path"]) == row, "header audit binding drift")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("build", "check"))
    args = parser.parse_args()
    value = build() if args.mode == "build" else check()
    print("c2-lite-v6-header-source-audit: " + value["status"])


if __name__ == "__main__":
    main()
