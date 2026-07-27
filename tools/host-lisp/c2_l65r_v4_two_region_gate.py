#!/usr/bin/env python3
"""Strict L65R-v4 two-region format and mutation gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import runtime_overlay_bank as R  # noqa: E402


CONTRACT = ROOT / "config/c2-two-region-session-store-contract.json"
EMITTER = ROOT / "tools/host-lisp/runtime_overlay_bank.py"
DECODER = ROOT / "src/vm_runtime_overlay.c"
PRODUCT_LINK = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
HOST_FIXTURE = ROOT / "scripts/c2-l65r-v2-product-main.c"
DEFAULT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v4-two-region-contract-receipt.json"
)
REGION1_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link61-region1-stage-hardware-first-red.json"
)

V4_TRANSFORM = """#if LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 4u
    /* L65R-v4 turns the authenticated record tuple into the DMA-native
     * installer frame.  This is a representation change inside the sealed
     * domain, so it must be complete before the producer signs or publishes
     * the frame.  The original installer identity remains available in the
     * CRC-bound record and is consumed from there below. */
    context->slot = source_bank;
    context->count = source_megabyte;
#endif
"""


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def bind(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def fixtures() -> tuple[bytes, bytes, R.ParsedBank]:
    vma = 0xC356
    specs = [
        R.SliceSpec(
            0, "main", ".main", "main_start", "main_end", "main_entry",
            R.FLAG_RUNTIME | R.FLAG_REUSABLE, R.ENTRY_ABI, 0, "main_impl",
        ),
        R.SliceSpec(
            1, "rollback", ".rollback", "rollback_start", "rollback_end",
            "rollback_entry", R.FLAG_RUNTIME | R.FLAG_REUSABLE,
            R.ENTRY_ABI, 0, "rollback_impl", False, 0,
            R.REGION_C2D_OVERFLOW,
        ),
    ]
    slices = [
        R.ExtractedSlice(specs[0], vma, vma + 17, vma, bytes(range(17))),
        R.ExtractedSlice(
            specs[1], vma, vma + 23, vma, bytes(range(0x40, 0x57))),
    ]
    return R.build_region_images(
        slices,
        profile_build_id=0x13579BDF,
        expected_vma=vma,
        max_slice_bytes=R.MAX_SLICE_BYTES,
        format_version=R.VERSION_V4,
    )


def refresh_record_and_catalog(image: bytearray, slot: int) -> None:
    at = R.HEADER_SIZE + slot * R.ENTRY_SIZE
    image[at + 22:at + 24] = b"\x00\x00"
    struct.pack_into(
        "<H", image, at + 22,
        R.crc16_ccitt_false(image[at:at + R.ENTRY_SIZE]),
    )
    R._refresh_catalog_crcs(image)


def stage_source_authority_errors(
        emitter: str, decoder: str, product_link: str) -> list[str]:
    errors: list[str] = []
    emitter_required = (
        "REGION1_SOURCE_BASE = 0x08300000",
        "expected_source = source_base + canonical_offset",
        "if source_address != expected_source:",
        'struct.pack_into("<H", record, 22, record_crc)',
    )
    for marker in emitter_required:
        if marker not in emitter:
            errors.append("emitter-" + marker.split("(")[0].strip())

    binding_begin = product_link.find("def family_stage_binding_bytes(")
    binding_end = product_link.find("\ndef ", binding_begin + 1)
    if binding_begin < 0 or binding_end < 0:
        errors.append("stage-binding-function-missing")
    else:
        binding = product_link[binding_begin:binding_end]
        for marker in (
                'storage = manifest["storage"]',
                'values.extend((int(storage["size"]), int(storage["crc16"])))',
                'return struct.pack("<4H", *values)'):
            if marker not in binding:
                errors.append("stage-binding-" + marker.split("(")[0].strip())

    stage_begin = decoder.find("#define C2_LITE_STAGE_BODY")
    stage_end = decoder.find("#undef C2_LITE_STAGE_BODY", stage_begin)
    if stage_begin < 0 or stage_end < 0:
        errors.append("target-stage-body-missing")
    else:
        stage = decoder[stage_begin:stage_end]
        crc = stage.find("if (crc == expected)")
        overflow = stage.find(
            "if (!C2_LITE_STAGE_SESSION_OVERFLOW(family_value))")
        publish = stage.find(
            "rtov_family = (uint8_t)((family_value) | "
            "RTOV_FAMILY_VERIFIED);")
        if min(crc, overflow, publish) < 0:
            errors.append("stage-proof-member-missing")
        elif not crc < overflow < publish:
            errors.append("stage-publishes-before-complete-target-proof")

    overflow_begin = decoder.find(
        "static uint8_t c2_lite_stage_session_overflow(void)")
    overflow_end = decoder.find(
        "#define C2_LITE_STAGE_SESSION_OVERFLOW", overflow_begin)
    if overflow_begin < 0 or overflow_end < 0:
        errors.append("region1-stage-function-missing")
    else:
        overflow_stage = decoder[overflow_begin:overflow_end]
        copy = overflow_stage.find(
            "LISP65_RUNTIME_OVERLAY_REGION1_SOURCE_BASE")
        target = overflow_stage.find(
            "LISP65_RUNTIME_OVERLAY_REGION1_BANK", copy + 1)
        crc = overflow_stage.find("if (crc == expected)")
        if min(copy, target, crc) < 0:
            errors.append("region1-copy-or-target-proof-missing")
        elif not copy < target < crc:
            errors.append("region1-target-proof-order")

    verifier_begin = decoder.find(
        "RTOV_RECORDFN uint8_t vm_runtime_overlay_record_verifier(")
    verifier_end = decoder.find(
        "/* Keep both generated verifier tuples", verifier_begin)
    if verifier_begin < 0 or verifier_end < 0:
        errors.append("record-verifier-boundary-missing")
    else:
        verifier = decoder[verifier_begin:verifier_end]
        for forbidden in (
                "LISP65_RUNTIME_OVERLAY_REGION_C2D_OVERFLOW",
                "LISP65_RUNTIME_OVERLAY_REGION1_ADDRESS",
                "LISP65_RUNTIME_OVERLAY_REGION1_CAPACITY",
                "region_id"):
            if forbidden in verifier:
                errors.append("runtime-duplicate-region-proof-" + forbidden)
        required = (
            "rtov_r_record_converge(record)",
            "source_bank = record[25];",
            "source_megabyte = record[26];",
            "context->slot = source_bank;",
            "context->count = source_megabyte;",
        )
        for marker in required:
            if marker not in verifier:
                errors.append("runtime-bound-tuple-" + marker.split("(")[0])
    return errors


def stage_source_authority_selftest(
        emitter: str, decoder: str, product_link: str) -> dict[str, str]:
    errors = stage_source_authority_errors(emitter, decoder, product_link)
    require(not errors, f"stage/source authority red: {errors}")
    mutations = {
        "emitter-source-comparison-removed": (
            emitter.replace("if source_address != expected_source:",
                            "if False:", 1),
            decoder, product_link),
        "region1-source-aliased-to-product-shelf": (
            emitter.replace(
                "REGION1_SOURCE_BASE = 0x08300000",
                "REGION1_SOURCE_BASE = 0x08100000", 1),
            decoder, product_link),
        "record-crc-binding-moved": (
            emitter.replace(
                'struct.pack_into("<H", record, 22, record_crc)',
                'struct.pack_into("<H", record, 20, record_crc)', 1),
            decoder, product_link),
        "manifest-crc-not-consumed": (
            emitter, decoder,
            product_link.replace(
                'values.extend((int(storage["size"]), int(storage["crc16"])))',
                'values.extend((int(storage["size"]), 1))', 1)),
        "family-published-before-target-crc": (
            emitter,
            decoder.replace(
                "if (crc == expected) {",
                "rtov_family = (uint8_t)((family_value) | "
                "RTOV_FAMILY_VERIFIED);\\\n"
                "        if (crc == expected) {", 1),
            product_link),
        "session-overflow-proof-removed": (
            emitter,
            decoder.replace(
                "if (!C2_LITE_STAGE_SESSION_OVERFLOW(family_value))",
                "if (0)", 1),
            product_link),
        "session-overflow-copy-removed": (
            emitter,
            decoder.replace(
                "LISP65_RUNTIME_OVERLAY_REGION1_SOURCE_BASE,",
                "0x08100000UL,", 1),
            product_link),
        "runtime-region-dispatch-restored": (
            emitter,
            decoder.replace(
                "/* The canonical emitter validates region-qualified",
                "LISP65_RUNTIME_OVERLAY_REGION_C2D_OVERFLOW;\n"
                "    /* The canonical emitter validates region-qualified",
                1),
            product_link),
    }
    for name, parts in mutations.items():
        require(stage_source_authority_errors(*parts),
                f"stage/source authority mutation accepted: {name}")
    return {name: "rejected" for name in mutations}


def post_shelf_region1_hardware_fixture(
        emitter: str, decoder: str) -> dict[str, object]:
    public_clean_build = os.environ.get("LISP65_PUBLIC_CLEAN_BUILD") == "1"
    if public_clean_build:
        # The historical Link-61 capture explains why this fixture exists,
        # but it is acceptance evidence rather than a source-build input.
        # The public gate proves the same negative class from current source:
        # Region 1 has a disjoint durable source, target CRC precedes family
        # publication, and the source-alias/publication-order mutations in
        # stage_source_authority_selftest() are rejected.
        require(
            "REGION1_SOURCE_BASE = 0x08300000" in emitter
            and "LISP65_RUNTIME_OVERLAY_REGION1_SOURCE_BASE," in decoder
            and decoder.index("if (crc == expected)")
                < decoder.index(
                    "rtov_family = (uint8_t)((family_value) | "
                    "RTOV_FAMILY_VERIFIED);"),
            "current post-shelf Region-1 negative fixture drift")
        authority: object = "acceptance-evidence-not-a-public-build-input"
    else:
        first_red = json.loads(REGION1_FIRST_RED.read_text(encoding="utf-8"))
        proof = first_red["proof"]
        require(
            first_red["status"]
            == "FIRST RED: Session Region-1 source overwritten before stage proof"
            and first_red["hardware"]["rtov_fault"] == 23
            and first_red["hardware"]["rtov_family"] == 0
            and first_red["hardware"]["c2_ready"] == 0
            and proof["upload_readback"]["crc16"] == "0x66c6"
            and proof["region1_at_failure"]["crc16"] == "0xa942"
            and proof["region1_at_failure"]["different_bytes"] == 1908
            and proof["region1_at_failure"][
                "byteidentical_to_boot_shelf_prefix"]
            and "REGION1_SOURCE_BASE = 0x08300000" in emitter
            and "LISP65_RUNTIME_OVERLAY_REGION1_SOURCE_BASE," in decoder,
            "Link-61 post-shelf Region-1 negative fixture drift")
        authority = bind(REGION1_FIRST_RED)
    return {
        "status":
            "passed-Link61-shelf-prefix-is-publication-negative-fixture",
        "durable_source": "0x08300000",
        "destination": "Bank5:0xbd00",
        "negative_target_crc16": "0xa942",
        "required_target_crc16": "0x66c6",
        "different_bytes": 1908,
        "fault": "VM_RUNTIME_OVERLAY_ERR_FAMILY_STAGE",
        "family_after_reject": 0,
        "READY_after_reject": 0,
        "authority": authority,
    }


def frame_seal_order_errors(decoder: str) -> list[str]:
    errors: list[str] = []
    begin = decoder.find(
        "RTOV_RECORDFN uint8_t vm_runtime_overlay_record_verifier(")
    end = decoder.find("/* Keep both generated verifier tuples", begin)
    if begin < 0 or end < 0:
        return ["record-verifier-boundary-missing"]
    verifier = decoder[begin:end]
    converge = verifier.find("rtov_r_record_converge(record)")
    transform_slot = verifier.find("context->slot = source_bank;")
    transform_count = verifier.find("context->count = source_megabyte;")
    identity = verifier.find(
        "rtov_r_u16(record) == LISP65_RUNTIME_ISLAND_INSTALL_SLOT")
    seal = verifier.find("context->seal = rtov_crc_mem(")
    publish = verifier.find("RTOV_INSTALL_CONTEXT = context;")
    if min(converge, transform_slot, transform_count, identity, seal, publish) < 0:
        errors.append("v4-frame-seal-member-missing")
    elif not converge < transform_slot < transform_count < identity < seal < publish:
        errors.append("v4-transform-seal-publication-order")
    if seal >= 0 and publish >= 0:
        between = verifier[seal:publish].replace("context->seal =", "", 1)
        if re.search(r"context->[A-Za-z_][A-Za-z0-9_]*\s*=", between):
            errors.append("frame-written-after-seal")
    installer = decoder.find(
        "offsetof(rtov_verify_context, seal)) != frame->seal")
    if installer < 0:
        errors.append("installer-seal-consumer-missing")
    return errors


def host_command(source: Path, binary: Path) -> list[str]:
    return [
        "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined",
        "-DLISP65_VM", "-DLISP65_RUNTIME_OVERLAY_HOST_TEST",
        "-DLISP65_RUNTIME_OVERLAY_CATALOG_VERSION=4",
        "-DLISP65_RUNTIME_OVERLAY_FORMAT_V4",
        "-DLISP65_RTOV_CRC_CONVERGENCE",
        "-DLISP65_RUNTIME_OVERLAY_LIFETIME_FAMILIES",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_STORAGE_BASE=0x08200000UL",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_OFF=0x0500u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_FILE_SIZE=8u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_ENTRY_OFFSET=0u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_CATALOG_VERIFIER_CRC16=0x37e8u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_OFF=0x0600u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_FILE_SIZE=8u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_ENTRY_OFFSET=0u",
        "-DLISP65_RUNTIME_OVERLAY_BOOT_RECORD_VERIFIER_CRC16=0x5afbu",
        "-DLISP65_RUNTIME_ISLAND_INSTALL_SLOT=8",
        "-DLISP65_RUNTIME_ISLAND_CARRIER_SLOT=9",
        "-I" + str(ROOT / "src"),
        str(HOST_FIXTURE), str(source), "-o", str(binary),
    ]


def frame_seal_end_to_end(decoder: str, out: Path) -> dict[str, object]:
    require(not frame_seal_order_errors(decoder),
            "v4 frame-seal source order red: "
            + str(frame_seal_order_errors(decoder)))
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    env = {
        **os.environ,
        "ASAN_OPTIONS": "detect_leaks=1",
        "UBSAN_OPTIONS": "halt_on_error=1",
    }
    positive = out / "v4-final-frame-positive"
    subprocess.run(host_command(DECODER, positive), cwd=ROOT, check=True)
    pos = subprocess.run(
        [str(positive)], cwd=ROOT, env=env, check=False,
        capture_output=True, text=True)
    require(
        pos.returncode == 0
        and "PASS publish-last+14 fail-closed cases" in pos.stdout,
        "v4 verifier-to-installer positive fixture red: " + pos.stderr)
    (out / "positive.stdout.txt").write_text(pos.stdout, encoding="utf-8")

    require(decoder.count(V4_TRANSFORM) == 1,
            "v4 transform mutation anchor drift")
    begin = decoder.index(
        "RTOV_RECORDFN uint8_t vm_runtime_overlay_record_verifier(")
    end = decoder.index("/* Keep both generated verifier tuples", begin)
    verifier = decoder[begin:end]
    require(verifier.count(V4_TRANSFORM) == 1
            and verifier.count("    return VM_RUNTIME_OVERLAY_OK;\n") == 1,
            "record verifier old-order mutation boundary drift")
    old_order = verifier.replace(V4_TRANSFORM, "", 1).replace(
        "    return VM_RUNTIME_OVERLAY_OK;\n",
        V4_TRANSFORM + "    return VM_RUNTIME_OVERLAY_OK;\n",
        1)
    mutant_text = decoder[:begin] + old_order + decoder[end:]
    require(frame_seal_order_errors(mutant_text),
            "old seal-before-transform mutation escaped the source gate")
    mutant = out / "vm_runtime_overlay.seal-before-transform.c"
    mutant.write_text(mutant_text, encoding="utf-8")
    negative = out / "v4-old-order-negative"
    subprocess.run(host_command(mutant, negative), cwd=ROOT, check=True)
    neg = subprocess.run(
        [str(negative)], cwd=ROOT, env=env, check=False,
        capture_output=True, text=True)
    require(
        neg.returncode != 0
        and "FAIL two-record install" in neg.stderr
        and "FAIL READY published last" in neg.stderr,
        "seal-before-transform mutation did not reproduce the end-to-end red")
    (out / "negative.stderr.txt").write_text(neg.stderr, encoding="utf-8")
    return {
        "status": "passed-verifier-transform-seal-installer-through-path",
        "sealed_representation": "final-v4-absolute-source-frame",
        "positive_cases": 14,
        "asan": "passed",
        "ubsan": "passed",
        "old_order_mutation": "reproduced-binding-red-before-READY",
        "fixture": bind(HOST_FIXTURE),
        "positive_binary": bind(positive),
        "positive_stdout": bind(out / "positive.stdout.txt"),
        "negative_source": bind(mutant),
        "negative_binary": bind(negative),
        "negative_stderr": bind(out / "negative.stderr.txt"),
    }


def run(host_out: Path) -> dict[str, object]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    emitter = EMITTER.read_text(encoding="utf-8")
    decoder = DECODER.read_text(encoding="utf-8")
    product_link = PRODUCT_LINK.read_text(encoding="utf-8")
    require(
        contract["format_contract"]["version"] == 4
        and contract["format_contract"]["region_id_offset"] == 24
        and contract["format_contract"]["source_address_low_offset"] == 4
        and contract["format_contract"]["source_address_bank_offset"] == 25
        and contract["format_contract"]["source_address_megabyte_offset"] == 26
        and contract["regions"]["rollback_overflow"]["capacity_bytes"]
            == R.REGION1_CAPACITY
        and contract["loading"]["region1_attic_stage_source"]
            == R.REGION1_SOURCE_BASE
        and contract["loading"]["region1_attic_stage_source_hex"]
            == "0x08300000",
        "v4 contract authority drift",
    )
    require(
        "source_bank = record[25];" in decoder
        and "source_megabyte = record[26];" in decoder
        and "context->slot = source_bank;" in decoder
        and "context->count = source_megabyte;" in decoder
        and "rtov_read_source(\n        verify.file_off," in decoder
        and "rtov_read_region(\n        verify.region_id" not in decoder,
        "target hot loader retained region dispatch or lost source binding")
    require(
        decoder.index("context->slot = source_bank;")
        < decoder.index(
            "rtov_r_u16(record) == LISP65_RUNTIME_ISLAND_INSTALL_SLOT")
        < decoder.index(
            "rtov_read_source(\n        verify.file_off,"),
        "final source transform, record-qualified installer identity or hot "
        "load ordering drift")
    frame_seal = frame_seal_end_to_end(decoder, host_out)
    source_authority_mutations = stage_source_authority_selftest(
        emitter, decoder, product_link)
    post_shelf_fixture = post_shelf_region1_hardware_fixture(
        emitter, decoder)
    image, overflow, parsed = fixtures()
    require(
        len(parsed.slices) == 2
        and [row.region_id for row in parsed.slices] == [0, 1]
        and parsed.slices[1].file_offset == 0
        and [row.source_address for row in parsed.slices]
            == [R.STORAGE_BASE + 256, R.REGION1_RUNTIME_SOURCE_BASE]
        and parsed.overflow_used == len(overflow) == 23,
        "canonical v4 fixture drift",
    )

    mutations: dict[str, str] = {}

    def reject(
        name: str,
        candidate: bytes,
        overflow_candidate: bytes = overflow,
        *,
        version: int = R.VERSION_V4,
        expected: str,
    ) -> None:
        try:
            R.validate_region_images(
                candidate,
                overflow_candidate,
                expected_build_id=0x13579BDF,
                expected_vma=0xC356,
                max_slice_bytes=R.MAX_SLICE_BYTES,
                format_version=version,
            )
        except R.OverlayBankError as error:
            require(
                error.code == expected,
                f"{name}: expected {expected}, got {error.code}",
            )
            mutations[name] = error.code
            return
        raise RuntimeError(f"{name}: mutation accepted")

    reject("v4-as-v3", image, b"", version=R.VERSION_V3,
           expected="bad-version")
    legacy = bytearray(image)
    legacy[4] = R.VERSION_V3
    R._refresh_header_crc(legacy)
    reject("v3-as-v4", bytes(legacy), expected="bad-version")

    swapped = bytearray(image)
    swapped[R.HEADER_SIZE + 24] = R.REGION_C2D_OVERFLOW
    refresh_record_and_catalog(swapped, 0)
    reject("main-as-overflow", bytes(swapped), expected="source-address")

    swapped = bytearray(image)
    second = R.HEADER_SIZE + R.ENTRY_SIZE
    swapped[second + 24] = R.REGION_MAIN
    refresh_record_and_catalog(swapped, 1)
    reject("overflow-as-main", bytes(swapped), expected="source-address")

    unknown = bytearray(image)
    unknown[second + 24] = 2
    refresh_record_and_catalog(unknown, 1)
    reject("unknown-region", bytes(unknown), expected="bad-region")

    wrong_bank = bytearray(image)
    wrong_bank[second + 25] ^= 1
    refresh_record_and_catalog(wrong_bank, 1)
    reject("wrong-source-bank", bytes(wrong_bank), expected="source-address")

    wrong_megabyte = bytearray(image)
    wrong_megabyte[second + 26] = 1
    refresh_record_and_catalog(wrong_megabyte, 1)
    reject(
        "wrong-source-megabyte", bytes(wrong_megabyte),
        expected="source-address")

    reserved = bytearray(image)
    reserved[second + 27] = 1
    refresh_record_and_catalog(reserved, 1)
    reject("source-reserved-byte", bytes(reserved), expected="bad-region")

    wrong_low = bytearray(image)
    wrong_low[second + 4] ^= 1
    refresh_record_and_catalog(wrong_low, 1)
    reject("wrong-source-low", bytes(wrong_low), expected="source-address")

    unbound = bytearray(image)
    unbound[second + 24] = 0
    R._refresh_catalog_crcs(unbound)
    reject("region-without-record-crc", bytes(unbound), expected="record-crc")

    zero_crc = bytearray(image)
    zero_crc[second + 22:second + 24] = b"\x00\x00"
    R._refresh_catalog_crcs(zero_crc)
    reject("zero-record-crc", bytes(zero_crc), expected="record-crc-zero")

    reject(
        "overflow-truncated",
        image,
        overflow[:-1],
        expected="overflow-binding",
    )

    oversized_spec = R.SliceSpec(
        0, "too-large", ".too_large", "large_start", "large_end",
        "large_entry", R.FLAG_RUNTIME | R.FLAG_REUSABLE, R.ENTRY_ABI, 0,
        "large_impl", False, 0, R.REGION_C2D_OVERFLOW,
    )
    try:
        R.build_region_images(
            [
                R.ExtractedSlice(
                    oversized_spec, 0xC356,
                    0xC356 + R.REGION1_CAPACITY + 1, 0xC356,
                    bytes(R.REGION1_CAPACITY + 1),
                )
            ],
            profile_build_id=0x13579BDF,
            expected_vma=0xC356,
            max_slice_bytes=0xFFFF,
            format_version=R.VERSION_V4,
        )
    except R.OverlayBankError as error:
        require(error.code == "bank-overflow", "region capacity mutation drift")
        mutations["overflow-capacity"] = error.code
    else:
        raise RuntimeError("overflow-capacity mutation accepted")

    return {
        "format": "lisp65-c2-l65r-v4-two-region-contract-receipt-v1",
        "recorded_on": "2026-07-24",
        "status": "passed-strict-v4-two-region-format-and-mutations",
        "authority": {
            "contract": bind(CONTRACT),
            "emitter": bind(EMITTER),
            "target_decoder": bind(DECODER),
            "product_link": bind(PRODUCT_LINK),
            "gate": bind(Path(__file__)),
        },
        "stage_source_authority": {
            "status":
                "passed-emitter-bound-record-and-target-stage-composite-proof",
            "hot_record_verifier_region_dispatch": "absent",
            "hot_record_verifier_source_bounds_reconstruction": "absent",
            "publication_order":
                "emitter-bounds -> record-CRC -> final-manifest-binding -> "
                "target-family-CRC -> region1-target-CRC -> VERIFIED",
            "mutations": source_authority_mutations,
        },
        "post_shelf_region1_stage": post_shelf_fixture,
        "v4_installer_frame_seal": frame_seal,
        "canonical_fixture": {
            "header_bytes": R.HEADER_SIZE,
            "record_bytes": R.ENTRY_SIZE,
            "main_image_bytes": len(image),
            "overflow_image_bytes": len(overflow),
            "record_regions": [row.region_id for row in parsed.slices],
            "record_source_addresses": [
                row.source_address for row in parsed.slices],
            "record_crc_nonzero": all(row.record_crc16 for row in parsed.slices),
        },
        "strict_asymmetry": {
            "accepted_versions": [R.VERSION_V4],
            "dual_decoder": False,
            "one_emitter": True,
        },
        "mutations": mutations,
        "mutation_count": len(mutations),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    host_out = ROOT / (
        "build/c2.2/l65r-v4-frame-seal-gates/" + args.receipt.stem)
    value = run(host_out)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "c2-l65r-v4-two-region-gate: PASS "
        f"mutations={value['mutation_count']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print("c2-l65r-v4-two-region-gate: FIRST RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
