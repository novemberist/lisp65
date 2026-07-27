#!/usr/bin/env python3
"""Bind four C1 cutpoint overlays to the immutable Link-58 runtime family.

The diagnostic WPLTO link is useful only as the source of the four cold
overlay payloads.  Its resident image is deliberately not used: changing a
global compile profile caused unrelated LTO layout noise in Bank-0 text.
This artifact-only step therefore keeps every Link-58 runtime slice except
the four named cutpoint slices, rebuilds the L65R-v3 catalog with Link-58's
canonical profile identity, and emits a non-promotable Session-family image.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import runtime_overlay_bank as R  # noqa: E402


BASE = ROOT / (
    "build/c2.2/substitution/product-link-58-matrix-addenda-fixed-block")
DIAGNOSTIC = ROOT / (
    "build/c2.2/substitution/"
    "link58-c1-freezer-cutpoints-attempt3-NONPROMOTABLE")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-c1-freezer-hybrid-carrier-NONPROMOTABLE")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-c1-freezer-hybrid-carrier-nonpromotable-receipt.json")
SOURCE_GATE = ROOT / "build/c2.2/c1-freezer-cutpoints/source-gate-attempt3.json"
BASE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link58-matrix-addenda-fixed-block-structural-receipt.json")
DIAGNOSTIC_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-c1-freezer-cutpoints-attempt3-"
    "nonpromotable-structural-receipt.json")

BASE_PRODUCT_SHA = (
    "4bab8371aa54060bef4ab9493e12dd6afd230baeb83a11f07daccdaa05000e6f")
AFFECTED = {
    30: ".lisp65_rt_c2append_journal_prepare",
    39: ".lisp65_rt_c2append_header",
    40: ".lisp65_rt_c2append_publish_clear",
    41: ".lisp65_rt_c2append_rollback_unpublish",
}


class CarrierError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CarrierError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rows_by_id(manifest: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(row["id"]): row for row in manifest["slices"]}


def payload(image: bytes, row: dict[str, Any]) -> bytes:
    start = int(row["file_offset"])
    end = start + int(row["file_size"])
    require(0 <= start < end <= len(image), "slice payload lies outside image")
    data = image[start:end]
    require(hashlib.sha256(data).hexdigest() == row["sha256"],
            f"slice payload SHA drift: {row['section']}")
    return data


def extracted(row: dict[str, Any], data: bytes) -> R.ExtractedSlice:
    require(row["entry"] is not None, "C1 carrier accepts executable slices only")
    spec = R.SliceSpec(
        int(row["id"]),
        str(row["name"]),
        str(row["section"]),
        str(row["start_symbol"]),
        str(row["end_symbol"]),
        str(row["entry_symbol"]),
        int(row["flags"]),
        int(row["abi_version"]),
        int(row["capability_mask"]),
    )
    vma = int(row["vma"])
    entry = int(row["entry"])
    return R.ExtractedSlice(spec, vma, vma + len(data), entry, data)


def main() -> int:
    require(not OUT.exists() and not RECEIPT.exists(),
            "C1 hybrid carrier is one-shot")
    base_product = BASE / "lisp65-c2-substitution-linked.prg"
    base_image_path = BASE / "runtime-overlays-session-final.bin"
    base_manifest_path = BASE / "runtime-overlays-session-final.json"
    base_header_path = BASE / "runtime-overlay-session-final.h"
    diag_image_path = DIAGNOSTIC / "runtime-overlays-session-final.bin"
    diag_manifest_path = DIAGNOSTIC / "runtime-overlays-session-final.json"
    diag_elf = DIAGNOSTIC / "lisp65-c2-substitution-linked.prg.elf"
    for path in (
            base_product, base_image_path, base_manifest_path, base_header_path,
            diag_image_path, diag_manifest_path, diag_elf, SOURCE_GATE,
            BASE_RECEIPT, DIAGNOSTIC_RECEIPT):
        require(path.is_file(), f"missing authority: {path}")
    require(sha(base_product) == BASE_PRODUCT_SHA,
            "immutable Link-58 product identity drift")

    base_receipt = read_json(BASE_RECEIPT)
    diag_receipt = read_json(DIAGNOSTIC_RECEIPT)
    source_gate = read_json(SOURCE_GATE)
    require(
        base_receipt["status"] ==
            "passed-link58-matrix-addenda-product-identity-hardware-not-run"
        and diag_receipt["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and diag_receipt["fresh_replacement_gates"]["status"] == "passed"
        and source_gate["source"]["status"] ==
            "passed-four-cold-overlay-holds-and-post-export-abort"
        and len(source_gate["mutations_rejected"]) == 8,
        "C1 carrier authorities are not in their expected states")

    base_manifest = read_json(base_manifest_path)
    diag_manifest = read_json(diag_manifest_path)
    base_rows = rows_by_id(base_manifest)
    diag_rows = rows_by_id(diag_manifest)
    require(
        set(base_rows) == set(range(48))
        and set(diag_rows) == set(range(48))
        and base_manifest["catalog"]["version"] == 3
        and diag_manifest["catalog"]["version"] == 3,
        "C1 Session catalogs are not the expected dense L65R-v3 family")

    base_image = base_image_path.read_bytes()
    diag_image = diag_image_path.read_bytes()
    slices: list[R.ExtractedSlice] = []
    provenance: list[dict[str, Any]] = []
    for slot in range(48):
        base_row = base_rows[slot]
        diag_row = diag_rows[slot]
        require(
            base_row["id"] == diag_row["id"]
            and base_row["section"] == diag_row["section"]
            and base_row["vma"] == diag_row["vma"]
            and base_row["entry_offset"] == diag_row["entry_offset"]
            and base_row["flags"] == diag_row["flags"]
            and base_row["abi_version"] == diag_row["abi_version"]
            and base_row["capability_mask"] == diag_row["capability_mask"],
            f"slice ABI/geometric drift at slot {slot}")
        use_diagnostic = slot in AFFECTED
        if use_diagnostic:
            require(diag_row["section"] == AFFECTED[slot],
                    f"wrong diagnostic section at slot {slot}")
        chosen = diag_row if use_diagnostic else base_row
        chosen_image = diag_image if use_diagnostic else base_image
        data = payload(chosen_image, chosen)
        slices.append(extracted(chosen, data))
        provenance.append({
            "id": slot,
            "section": chosen["section"],
            "source": "diagnostic-cutpoint" if use_diagnostic else "link58",
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    build_id = int(base_manifest["profile_build_id"])
    image, parsed = R.build_image(
        slices,
        profile_build_id=build_id,
        expected_vma=int(base_manifest["policy"]["common_vma"]),
        max_slice_bytes=int(base_manifest["policy"]["max_slice_bytes"]),
        format_version=3,
    )
    header = R.render_header(
        profile_build_id=build_id,
        verifier_slices=parsed.slices,
        format_version=3,
    )
    require(
        len(image) == 65438
        and 65536 - len(image) == 98
        and header == base_header_path.read_bytes(),
        "hybrid carrier changed the Session aggregate or resident verifier ABI")
    R.validate_image(
        image,
        expected_build_id=build_id,
        expected_vma=int(base_manifest["policy"]["common_vma"]),
        max_slice_bytes=int(base_manifest["policy"]["max_slice_bytes"]),
        format_version=3,
    )

    hybrid_rows = {row.id: row for row in parsed.slices}
    capacities: dict[str, dict[str, int]] = {}
    for slot, ceiling in {30: 1792, 39: 768, 40: 1280, 41: 768}.items():
        row = hybrid_rows[slot]
        require(row.file_size <= ceiling,
                f"cutpoint slice {slot} crossed its pack quantum")
        capacities[AFFECTED[slot]] = {
            "payload_bytes": row.file_size,
            "pack_ceiling_bytes": ceiling,
            "headroom_bytes": ceiling - row.file_size,
        }

    OUT.mkdir(parents=True)
    image_out = OUT / "runtime-overlays-session-c1-freezer.bin"
    manifest_out = OUT / "runtime-overlays-session-c1-freezer.json"
    header_out = OUT / "runtime-overlay-session-c1-freezer.h"
    image_out.write_bytes(image)
    header_out.write_bytes(header)
    manifest = {
        "format": "lisp65-C1-Freezer-hybrid-Session-family-v1",
        "status": "passed-artifact-only-nonpromotable-carrier",
        "promotable": False,
        "profile": base_manifest["profile"],
        "profile_build_id": build_id,
        "storage": {
            "bytes": len(image),
            "headroom_bytes": 65536 - len(image),
            "sha256": hashlib.sha256(image).hexdigest(),
            "crc16": R.crc16_ccitt_false(image),
        },
        "catalog": {
            "version": 3,
            "slice_count": len(parsed.slices),
            "directory_crc16": parsed.directory_crc16,
            "header_crc16": parsed.header_crc16,
        },
        "affected_slices": capacities,
        "slice_provenance": provenance,
    }
    manifest_out.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    receipt = {
        "format": "lisp65-c2.2-C1-Freezer-hybrid-carrier-receipt-v1",
        "status": "passed-nonpromotable-carrier-hardware-not-run",
        "promotable": False,
        "authority": {
            "immutable_link58_product": bind(base_product),
            "link58_receipt": bind(BASE_RECEIPT),
            "diagnostic_first_red_receipt": bind(DIAGNOSTIC_RECEIPT),
            "diagnostic_elf": bind(diag_elf),
            "source_gate": bind(SOURCE_GATE),
        },
        "artifacts": {
            "session_family": bind(image_out),
            "manifest": bind(manifest_out),
            "verifier_header": bind(header_out),
        },
        "construction": {
            "compiler_runs": 0,
            "linker_runs": 0,
            "product_bytes_changed": 0,
            "resident_bytes_changed": 0,
            "base_slices": 44,
            "diagnostic_slices": 4,
            "diagnostic_slice_ids": sorted(AFFECTED),
            "diagnostic_sections": [AFFECTED[key] for key in sorted(AFFECTED)],
            "all_other_payloads": "byteidentical-Link58",
            "profile_identity": "canonical-Link58",
            "verifier_header": "byteidentical-Link58",
            "session_family_bytes": len(image),
            "session_family_headroom_bytes": 65536 - len(image),
        },
        "cutpoint_capacity": capacities,
        "execution_accounting": {
            "hardware_runs": 0,
            "latency_attempts_consumed": 0,
        },
        "next_gate": "one bundled real-MEGA65 C1 four-cutpoint run",
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    for path in (image_out, manifest_out, header_out, RECEIPT):
        os.chmod(path, 0o444)
    os.chmod(OUT, 0o555)
    print(
        "c2-c1-freezer-hybrid-carrier: PASS "
        f"product={BASE_PRODUCT_SHA} carrier={sha(image_out)} "
        f"session={len(image)}/65536 headroom={65536-len(image)} "
        "compiler=0 linker=0 hardware=not-run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CarrierError, R.OverlayBankError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-c1-freezer-hybrid-carrier: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
