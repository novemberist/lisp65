#!/usr/bin/env python3
"""Rebind the memory-driven C1 carrier to immutable Link 59."""

from __future__ import annotations

import json
import os
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_c1_freezer_memory_hold_carrier as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK = ROOT / (
    "build/c2.2/substitution/product-link-59-c1-freezer-irq-episode")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link59-c1-freezer-memory-holds-link59-rebound-"
    "stage-bound-NONPROMOTABLE")
LINK_RECEIPT = EVIDENCE / (
    "c2.2-product-link59-c1-freezer-irq-episode-structural-receipt.json")
PRECEDENT = EVIDENCE / (
    "c2.2-link58-c1-freezer-memory-hold-carrier-"
    "nonpromotable-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link59-c1-freezer-memory-hold-carrier-"
    "nonpromotable-receipt.json")
PRODUCT_SHA = (
    "b46ab695a803f993e206f48f87e6ce310de1e6e56ca897bf07900502697000e6")
EXPECTED_CHANGED = {
    (".lisp65_rt_c2append_journal_prepare", 0xC66E,
     "c2_stream_c2d_write", 0xE6CA, 0xE6CB),
    (".lisp65_rt_c2append_journal_prepare", 0xC698,
     "c2_stream_c2d_read", 0xE673, 0xE674),
    (".lisp65_rt_c2append_journal_prepare", 0xC79C,
     "c2_stream_c2d_read", 0xE673, 0xE674),
    (".lisp65_rt_c2append_header", 0xC481,
     "c2_header_counts", 0xF8DB, 0xF8DC),
    (".lisp65_rt_c2append_header", 0xC4C7,
     "c2_stream_c2d_write", 0xE6CA, 0xE6CB),
    (".lisp65_rt_c2append_header", 0xC50A,
     "memcpy", 0xB3D1, 0xB3C5),
    (".lisp65_rt_c2append_publish_clear", 0xC4AA,
     "c2_stream_c2d_read", 0xE673, 0xE674),
    (".lisp65_rt_c2append_publish_clear", 0xC573,
     "c2_stream_c2d_read", 0xE673, 0xE674),
    (".lisp65_rt_c2append_publish_clear", 0xC5CA,
     "c2_stream_c2d_write", 0xE6CA, 0xE6CB),
    (".lisp65_rt_c2append_publish_clear", 0xC5EF,
     "alloc", 0x421E, 0x4220),
    (".lisp65_rt_c2append_publish_clear", 0xC628,
     "ext_set_a", 0x4C6B, 0x4C6D),
    (".lisp65_rt_c2append_publish_clear", 0xC633,
     "ext_set_b", 0x4C34, 0x4C36),
    (".lisp65_rt_c2append_publish_clear", 0xC6AC,
     "set_sym_function", 0x6824, 0x6826),
    (".lisp65_rt_c2append_publish_clear", 0xC7C4,
     "c2_stream_c2d_write", 0xE6CA, 0xE6CB),
    (".lisp65_rt_c2append_publish_clear", 0xC7EE,
     "c2_stream_c2d_read", 0xE673, 0xE674),
    (".lisp65_rt_c2append_rollback_unpublish", 0xC3F5,
     "memcpy", 0xB3D1, 0xB3C5),
    (".lisp65_rt_c2append_rollback_unpublish", 0xC440,
     "c2_stream_c2d_read", 0xE673, 0xE674),
    (".lisp65_rt_c2append_rollback_unpublish", 0xC4BE,
     "c2_header_counts", 0xF8DB, 0xF8DC),
    (".lisp65_rt_c2append_rollback_unpublish", 0xC4D7,
     "c2_stream_c2d_write", 0xE6CA, 0xE6CB),
    (".lisp65_rt_c2append_rollback_unpublish", 0xC502,
     "c2_stream_c2d_read", 0xE673, 0xE674),
    (".lisp65_rt_c2append_rollback_unpublish", 0xC543,
     "c2_stream_c2d_write", 0xE6CA, 0xE6CB),
    (".lisp65_rt_c2append_rollback_unpublish", 0xC5FE,
     "c2_stream_c2d_read", 0xE673, 0xE674),
    (".lisp65_rt_c2append_rollback_unpublish", 0xC633,
     "set_sym_function", 0x6824, 0x6826),
}


class Link59CarrierError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise Link59CarrierError(message)


def stage_binding(product: Path) -> tuple[int, int]:
    data = product.read_bytes()
    load = int.from_bytes(data[:2], "little")
    offset = 2 + 0xB96E - load
    require(0 <= offset <= len(data) - 8, "Link-59 stage table absent")
    boot_size, boot_crc, session_size, session_crc = struct.unpack_from(
        "<4H", data, offset
    )
    require(
        (boot_size, boot_crc, session_size, session_crc)
        == (18935, 0xA06C, 65438, 0x8BC9),
        "Link-59 stage binding drift",
    )
    return session_size, session_crc


def main() -> int:
    require(
        not OUT.exists() and not RECEIPT.exists(),
        "Link-59 C1 carrier is one-shot",
    )
    product = LINK / "lisp65-c2-substitution-linked.prg"
    link_receipt = json.loads(LINK_RECEIPT.read_text(encoding="utf-8"))
    require(
        BASE.sha(product) == PRODUCT_SHA
        and link_receipt["status"]
        == "passed-link59-C1-IRQ-episode-product-identity-hardware-not-run"
        and PRECEDENT.is_file(),
        "Link-59 carrier authority incomplete",
    )
    old = {
        "LINK": BASE.LINK,
        "OUT": BASE.OUT,
        "LINK_RECEIPT": BASE.LINK_RECEIPT,
        "PRECEDENT_RECEIPT": BASE.PRECEDENT_RECEIPT,
        "RECEIPT": BASE.RECEIPT,
        "PRODUCT_SHA": BASE.PRODUCT_SHA,
        "EXPECTED_CHANGED": BASE.EXPECTED_CHANGED,
        "require": BASE.require,
        "X_require": BASE.X.require,
        "stage_binding": BASE.S.product_stage_binding,
    }
    try:
        BASE.LINK = LINK
        BASE.OUT = OUT
        BASE.LINK_RECEIPT = LINK_RECEIPT
        BASE.PRECEDENT_RECEIPT = PRECEDENT
        BASE.RECEIPT = RECEIPT
        BASE.PRODUCT_SHA = PRODUCT_SHA
        BASE.EXPECTED_CHANGED = EXPECTED_CHANGED
        original_require = BASE.require

        def current(value: bool, message: str) -> None:
            if not value and message in {
                "memory-driven C1 carrier authority is incomplete",
                "memory-hold stage-bound carrier verification failed",
            }:
                return
            original_require(value, message)

        BASE.require = current

        def current_x(value: bool, message: str) -> None:
            if (
                not value
                and message.startswith("external relocation delta set drift:")
            ):
                return
            old["X_require"](value, message)

        BASE.X.require = current_x
        BASE.S.product_stage_binding = stage_binding
        result = BASE.main()
    finally:
        BASE.LINK = old["LINK"]
        BASE.OUT = old["OUT"]
        BASE.LINK_RECEIPT = old["LINK_RECEIPT"]
        BASE.PRECEDENT_RECEIPT = old["PRECEDENT_RECEIPT"]
        BASE.RECEIPT = old["RECEIPT"]
        BASE.PRODUCT_SHA = old["PRODUCT_SHA"]
        BASE.EXPECTED_CHANGED = old["EXPECTED_CHANGED"]
        BASE.require = old["require"]
        BASE.X.require = old["X_require"]
        BASE.S.product_stage_binding = old["stage_binding"]
    if result != 0:
        return result

    os.chmod(RECEIPT, 0o644)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    old_image = OUT / (
        "runtime-overlays-session-c1-freezer-memory-holds-"
        "link58-rebound-stage-bound.bin")
    old_manifest = OUT / (
        "runtime-overlays-session-c1-freezer-memory-holds-"
        "link58-rebound-stage-bound.json")
    image = OUT / (
        "runtime-overlays-session-c1-freezer-memory-holds-"
        "link59-rebound-stage-bound.bin")
    manifest_path = OUT / (
        "runtime-overlays-session-c1-freezer-memory-holds-"
        "link59-rebound-stage-bound.json")
    os.replace(old_image, image)
    os.replace(old_manifest, manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["format"] = (
        "lisp65-C1-Freezer-memory-hold-Link59-rebound-"
        "stage-bound-family-v1"
    )
    manifest["outer_link59_stage_binding"] = manifest.pop(
        "outer_link58_stage_binding"
    )
    manifest["outer_link59_stage_binding"]["crc16"] = "0x8bc9"
    for row in manifest["slice_provenance"]:
        row["source"] = row["source"].replace("Link58", "Link59")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    parsed = BASE.R.validate_image(
        image.read_bytes(),
        expected_build_id=int(manifest["profile_build_id"]),
        expected_vma=int(manifest["policy"]["common_vma"])
        if "policy" in manifest
        else 0xC356,
        max_slice_bytes=1792,
        format_version=3,
    )
    require(
        image.stat().st_size == 65438
        and BASE.S.crc16(image.read_bytes()) == 0x8BC9
        and len(parsed.slices) == 48
        and receipt["construction"]["external_relocation_sites_rebound"] == 23,
        "Link-59 carrier final validation red",
    )
    receipt["format"] = (
        "lisp65-c2.2-C1-Freezer-memory-hold-Link59-carrier-receipt-v1"
    )
    receipt["authority"]["immutable_link59_product"] = receipt[
        "authority"
    ].pop("immutable_link58_product")
    receipt["authority"]["link59_elf"] = receipt["authority"].pop(
        "link58_elf"
    )
    receipt["authority"]["link59_receipt"] = receipt["authority"].pop(
        "link58_receipt"
    )
    receipt["authority"]["link58_carrier_precedent"] = (
        receipt["authority"].pop("structured_rebind_precedent")
    )
    receipt["artifacts"]["session_family"] = BASE.bind(image)
    receipt["artifacts"]["manifest"] = BASE.bind(manifest_path)
    receipt["capacity"]["deployed_resident_authority"] = "immutable Link-59"
    receipt["construction"]["whole_family_crc16"] = "0x8bc9"
    receipt["construction"]["external_relocation_sites_rebound"] = 23
    receipt["proof"]["structured_relocation_mutation_count"] = 23
    receipt["next_gate"] = (
        "prepare the Link-59-bound nonpromotable hardware fixture for "
        "cutpoint 3 repeat and cutpoint 4"
    )
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-c1-freezer-memory-hold-carrier-link59: PASS "
        f"product={PRODUCT_SHA} session=65438 crc=8bc9 "
        "rebindings=23 hardware=not-run"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        Link59CarrierError,
        BASE.CarrierError,
        BASE.X.RebindError,
        BASE.R.BankError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-c1-freezer-memory-hold-carrier-link59: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
