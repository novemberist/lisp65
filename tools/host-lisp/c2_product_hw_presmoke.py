#!/usr/bin/env python3
"""Prepare and verify a receipt-less SHA-bound C2 hardware pre-smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import tempfile
from typing import Any
import zlib
import runtime_overlay_bank as R


ROOT = Path(__file__).resolve().parents[2]
LINK = ROOT / "build/c2.2/substitution/product-link-19"
CANDIDATE_LINK: Path | None = None
AUTHORIZATION_RECEIPT: Path | None = None
SUBSTITUTION = ROOT / "build/c2.2/substitution"
DEFAULT_OUT = ROOT / "build/c2.2/hardware-presmoke-link19"
PIN_RECEIPT = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
               "c2.2-product-substitution-link-19-pin-receipt.json")
REPLAY_RECEIPT = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                  "c2.2-product-substitution-link-19-replay-receipt.json")
C2D_HEADER_AUDIT_RECEIPT = (
    ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-header-source-audit-receipt.json")
NM = ROOT / "tools/llvm-mos/bin/llvm-nm"
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"

DESCRIPTOR_MAGIC = b"L65O"
DESCRIPTOR_VERSION = 1
DESCRIPTOR_BYTES = 18
BOOT_OVERLAY_STAGE = 0x00058500
BOOT_FAMILY_STAGE = 0x08200000
SESSION_FAMILY_STAGE = 0x08000000
SHELF_STAGE = 0x08100000
C2D_STAGE = 0x00050000
KERNAL_WINDOW_STAGE = 0x087FE000
PHYSICAL_LIMIT = 0x10000000


class PreSmokeError(RuntimeError):
    pass


def regular(path: Path, label: str) -> bytes:
    try:
        info = path.lstat()
    except OSError as exc:
        raise PreSmokeError(f"missing {label}: {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise PreSmokeError(f"{label} must be a regular, symlink-free file: {path}")
    return path.read_bytes()


def sha(path: Path) -> str:
    return hashlib.sha256(regular(path, "hash input")).hexdigest()


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(regular(path, label).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PreSmokeError(f"invalid {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PreSmokeError(f"{label} root must be an object")
    return value


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def run(args: list[str]) -> str:
    try:
        result = subprocess.run(args, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or getattr(exc, "stdout", "") or str(exc)
        raise PreSmokeError(f"command failed: {' '.join(args)}: {detail.strip()}") from exc
    if result.stderr:
        raise PreSmokeError(f"unexpected command diagnostic: {result.stderr.strip()}")
    return result.stdout


def symbols(elf: Path, *, bank3_bootstrap: bool = False) -> dict[str, int]:
    wanted = {
        "__lisp65_workbench_overlay_start",
        "__lisp65_workbench_overlay_end",
        "vm_workbench_boot_overlay_entry",
    }
    if bank3_bootstrap:
        wanted.update({
            "__lisp65_boot_bank3_stage_start",
            "__lisp65_boot_bank3_stage_end",
            "vm_bank3_boot_stage_entry",
        })
    result: dict[str, int] = {}
    for line in run([str(NM), "--defined-only", str(elf)]).splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[-1] in wanted:
            if fields[-1] in result:
                raise PreSmokeError(f"duplicate ELF symbol: {fields[-1]}")
            result[fields[-1]] = int(fields[0], 16)
    if set(result) != wanted:
        raise PreSmokeError(f"missing ELF symbols: {sorted(wanted - set(result))}")
    return result


def crc16(data: bytes) -> int:
    value = 0xFFFF
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = (((value << 1) ^ 0x1021) & 0xFFFF
                     if value & 0x8000 else (value << 1) & 0xFFFF)
    return value


def boot_overlay_descriptor(*, build_id: int, start: int, entry: int,
                            payload: bytes) -> bytes:
    """Emit the sole L65O-v1 descriptor representation."""
    return struct.pack(
        "<4sBBIHHHH", DESCRIPTOR_MAGIC, DESCRIPTOR_VERSION,
        DESCRIPTOR_BYTES, build_id, start, entry, len(payload),
        crc16(payload))


def binding(path: Path, address: int) -> dict[str, Any]:
    data = regular(path, "deployment artifact")
    if not 0 <= address < PHYSICAL_LIMIT or address + len(data) > PHYSICAL_LIMIT:
        raise PreSmokeError(f"deployment span outside physical address space: {path}")
    return {
        "path": str(path.relative_to(ROOT)),
        "address": f"0x{address:08x}",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def assert_binding(path: Path, expected: dict[str, Any], label: str) -> None:
    data = regular(path, label)
    if len(data) != expected["bytes"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
        raise PreSmokeError(f"{label} differs from its pinned binding: {path}")


def resolved_profile_value(path: Path, key: str) -> str:
    prefix = key + "="
    values = [line[len(prefix):] for line in regular(
        path, "resolved profile").decode("utf-8").splitlines()
        if line.startswith(prefix)]
    if len(values) != 1 or not values[0]:
        raise PreSmokeError(
            f"resolved profile needs exactly one nonempty {key}: {path}")
    return values[0]


def c2_lite_real_abi_link_number(format_name: object) -> int | None:
    if not isinstance(format_name, str):
        return None
    match = re.fullmatch(
        r"lisp65-c2-lite-v6-real-abi-link([1-9][0-9]*)-structural-v1",
        format_name)
    return int(match.group(1)) if match else None


def c2d_build_id(data: bytes) -> int:
    if (len(data) < 48 or data[:4] != b"C2D\0"
            or data[5] != 48 or data[4] not in (3, 5, 6)):
        raise PreSmokeError("deployment C2D lacks a supported 48-byte header")
    return struct.unpack_from("<I", data, 44)[0]


def c2d_catalog_crc(data: bytes) -> int:
    if (len(data) < 48 or data[:4] != b"C2D\0"
            or data[5] != 48 or data[4] not in (3, 5, 6)):
        raise PreSmokeError("deployment C2D lacks a supported 48-byte header")
    return struct.unpack_from("<I", data, 40)[0]


def shelf_product_identity(data: bytes) -> tuple[int, int]:
    if (len(data) < 32 or data[:4] != b"L65S" or data[4] != 4
            or data[5] != 32 or data[6] != 32):
        raise PreSmokeError("deployment shelf lacks an L65S-v4 header")
    image_count = data[7]
    catalog_offset = struct.unpack_from("<H", data, 8)[0]
    catalog_bytes = struct.unpack_from("<H", data, 16)[0]
    catalog_crc = struct.unpack_from("<I", data, 18)[0]
    build_id = struct.unpack_from("<I", data, 22)[0]
    if (not image_count or catalog_offset != 32
            or catalog_bytes != image_count * 32
            or catalog_offset + catalog_bytes > len(data)):
        raise PreSmokeError("deployment shelf catalog geometry is invalid")
    computed = zlib.crc32(
        data[catalog_offset:catalog_offset + catalog_bytes]) & 0xffffffff
    if computed != catalog_crc:
        raise PreSmokeError(
            "deployment shelf catalog CRC is not self-consistent: "
            f"header=0x{catalog_crc:08x} computed=0x{computed:08x}")
    return catalog_crc, build_id


def verify_c2d_product_identity(
        paths: dict[str, Path],
        artifact_authority_path: Path | None = None) -> None:
    """Bind C2D to the shelf's catalog and product-build identities."""
    authority_path = (
        artifact_authority_path
        if artifact_authority_path is not None
        else SUBSTITUTION / "substitution-artifacts.json")
    if artifact_authority_path is None:
        expected_authority_sha = resolved_profile_value(
            paths["contract"], "c2_artifacts_sha256")
        if sha(authority_path) != expected_authority_sha:
            raise PreSmokeError(
                "candidate resolved profile does not bind the current C2 authority")
    authority = load_json(authority_path, "C2 product artifact authority")
    expected = authority.get("product_build_id_u32")
    expected_hex = authority.get("product_build_id_hex")
    if (not isinstance(expected, int) or not 0 <= expected <= 0xffffffff
            or expected_hex != f"0x{expected:08x}"):
        raise PreSmokeError("C2 product authority has an invalid build identity")
    c2d = regular(paths["c2d"], "deployment C2D plane")
    shelf = regular(paths["shelf"], "deployment product shelf")
    shelf_catalog_crc, shelf_build_id = shelf_product_identity(shelf)
    actual = c2d_build_id(c2d)
    if actual != expected or shelf_build_id != expected:
        raise PreSmokeError(
            "C2D/product build identity mismatch: "
            f"c2d=0x{actual:08x} shelf=0x{shelf_build_id:08x} "
            f"product=0x{expected:08x}")
    actual_catalog_crc = c2d_catalog_crc(c2d)
    if actual_catalog_crc != shelf_catalog_crc:
        raise PreSmokeError(
            "C2D/shelf catalog identity mismatch: "
            f"c2d=0x{actual_catalog_crc:08x} "
            f"shelf=0x{shelf_catalog_crc:08x}")


def verify_source_bindings() -> dict[str, Path]:
    if CANDIDATE_LINK is not None:
        return verify_candidate_source_bindings()
    pin = load_json(PIN_RECEIPT, "Link-19 pin receipt")
    replay = load_json(REPLAY_RECEIPT, "Link-19 replay receipt")
    if pin.get("status") != "pinned-structural-hardware-not-run":
        raise PreSmokeError("Link-19 pin is not structurally passed and hardware-not-run")
    if replay.get("status") != "passed-structural-hardware-not-run":
        raise PreSmokeError("Link-19 replay is not structurally passed and hardware-not-run")
    if pin.get("link_number") != 19 or replay.get("link_number") != 19:
        raise PreSmokeError("Link-19 receipt number drift")
    if not str(pin.get("inheritance", "")).startswith("none;"):
        raise PreSmokeError("Link-19 pin unexpectedly inherits an earlier green claim")
    if replay.get("new_product_links") != 0:
        raise PreSmokeError("Link-19 replay unexpectedly performed a product link")
    if replay.get("remaining_claims", {}).get("hardware") != "not-run":
        raise PreSmokeError("Link-19 hardware claim is no longer the expected not-run state")
    if sha(PIN_RECEIPT) != replay.get("pin_receipt", {}).get("sha256"):
        raise PreSmokeError("Link-19 pin-receipt binding drift")
    evidence = pin.get("evidence_objects", [])
    if pin.get("evidence_object_count") != 43 or len(evidence) != 43:
        raise PreSmokeError("Link-19 evidence-object count drift")
    pinned: dict[str, dict[str, Any]] = {}
    for item in evidence:
        relative = item.get("path")
        if not isinstance(relative, str) or relative in pinned:
            raise PreSmokeError("invalid or duplicate Link-19 evidence path")
        pinned[relative] = item
        assert_binding(ROOT / relative, item, f"Link-19 pinned object {relative}")
    if replay.get("pinned_evidence_objects_verified") != 43:
        raise PreSmokeError("Link-19 replay did not verify all pinned objects")
    if replay.get("pinned_evidence_drift") != 0:
        raise PreSmokeError("Link-19 replay recorded pinned evidence drift")

    paths = {
        "product": LINK / "lisp65-c2-substitution-linked.prg",
        "elf": LINK / "lisp65-c2-substitution-linked.prg.elf",
        "window": LINK / "c2-product-kernal-window.bin",
        "boot_family": LINK / "runtime-overlays-boot-final.bin",
        "session_family": LINK / "runtime-overlays-session-final.bin",
        "shelf": SUBSTITUTION / "product-shelf-v4-direct.bin",
        "c2d": SUBSTITUTION / "initial.c2d-v3.bin",
        "contract": LINK / "resolved-profile.txt",
        "stage_header": LINK / "stage-config.h",
    }
    product = replay.get("product_identity", {})
    if sha(paths["product"]) != product.get("sha256"):
        raise PreSmokeError("Link-19 product SHA drift")
    for name, path in paths.items():
        relative = str(path.relative_to(ROOT))
        if relative not in pinned:
            raise PreSmokeError(f"deployment source is absent from Link-19 pin: {name}")
        assert_binding(path, pinned[relative], name)
    regular(paths["contract"], "resolved profile")
    regular(paths["stage_header"], "stage header")
    return paths


def verify_candidate_source_bindings() -> dict[str, Path]:
    assert CANDIDATE_LINK is not None
    link = CANDIDATE_LINK
    authorization: dict[str, Any] | None = None
    c2d_identity_rebind: dict[str, Any] | None = None
    c2d_catalog_rebind: dict[str, Any] | None = None
    c2_artifact_authority_path: Path | None = None
    c2_lite = False
    c2_lite_bank3 = False
    if AUTHORIZATION_RECEIPT is not None:
        authorization = load_json(
            AUTHORIZATION_RECEIPT, "candidate authorization receipt")
        authorization_format = authorization.get("format")
        if authorization_format == (
                "lisp65-c2-lite-v6-c2d-catalog-identity-rebind-v1"):
            c2d_catalog_rebind = authorization
            audit = load_json(
                C2D_HEADER_AUDIT_RECEIPT, "C2D-v6 header-source audit")
            correction_binding = audit.get("authority", {}).get(
                "catalog_correction", {})
            if (audit.get("status") !=
                    "passed-all-header-fields-and-product-writers-accounted"
                    or audit.get("field_source_audit", {}).get(
                        "covered_byte_count") != 48
                    or audit.get("field_source_audit", {}).get(
                        "private_identity_derivations") != []
                    or audit.get("product_writer_checks", {}).get(
                        "canonical_field_assignment_count") != 0
                    or correction_binding.get("path") != str(
                        AUTHORIZATION_RECEIPT.relative_to(ROOT))
                    or correction_binding.get("sha256") !=
                        sha(AUTHORIZATION_RECEIPT)
                    or correction_binding.get("bytes") !=
                        AUTHORIZATION_RECEIPT.stat().st_size):
                raise PreSmokeError(
                    "C2D-v6 header-source audit is absent, stale or incomplete")
            row = authorization.get("authority", {}).get(
                "prior_product_identity_rebind", {})
            if not isinstance(row.get("path"), str):
                raise PreSmokeError(
                    "C2D catalog rebind lacks its product-identity authority")
            path = ROOT / row["path"]
            if (row.get("sha256") != sha(path)
                    or row.get("bytes") != path.stat().st_size):
                raise PreSmokeError(
                    "C2D catalog rebind product-identity authority drift")
            authorization = load_json(
                path, "C2D catalog rebind product-identity authority")
            authorization_format = authorization.get("format")
        if authorization_format == (
                "lisp65-c2-lite-v6-c2d-product-identity-rebind-v1"):
            c2d_identity_rebind = authorization
            row = authorization.get("authority", {}).get(
                "link40_structural_receipt", {})
            if not isinstance(row.get("path"), str):
                raise PreSmokeError(
                    "C2D identity rebind lacks Link-40 structural authority")
            path = ROOT / row["path"]
            if (row.get("sha256") != sha(path)
                    or row.get("bytes") != path.stat().st_size):
                raise PreSmokeError(
                    "C2D identity rebind structural authority drift")
            authorization = load_json(
                path, "C2D identity rebind Link-40 structural authority")
            authorization_format = authorization.get("format")
        real_abi_link_number = c2_lite_real_abi_link_number(
            authorization_format)
        c2_lite_link49 = (
            authorization_format ==
                "lisp65-c2-lite-v6-link49-facade16-artifact-replay-v1"
            and authorization.get("link_number") == 49)
        c2_lite_link50 = (
            authorization_format ==
                "lisp65-c2-lite-v6-link50-persistent-header-artifact-replay-v1"
            and authorization.get("link_number") == 50)
        c2_lite_link40 = (
            real_abi_link_number is not None
            and authorization.get("link_number") == real_abi_link_number)
        c2_lite_link52 = (
            authorization_format ==
                "lisp65-c2-lite-v6-link52-phase-self-stamp-v1"
            and authorization.get("link_number") == 52)
        c2_lite_link53 = (
            authorization_format ==
                "lisp65-c2-lite-v6-link53-first-fault-stamp-v1"
            and authorization.get("link_number") == 53)
        c2_lite_link54 = (
            authorization_format ==
                "lisp65-c2-lite-v6-link54-phase06a-cutpoint-v1"
            and authorization.get("link_number") == 54)
        c2_lite_link55 = (
            authorization_format ==
                "lisp65-c2-lite-v6-link55-append-suffix-fusion-final-v1"
            and authorization.get("link_number") == 55)
        c2_lite_link56 = (
            authorization_format ==
                "lisp65-c2-lite-v6-link56-selector-tail-z-v1"
            and authorization.get("link_number") == 56)
        c2_lite_link57 = (
            authorization_format ==
                "lisp65-c2-lite-v6-link57-keymap-nullary-v1"
            and authorization.get("link_number") == 57)
        if c2_lite_link57:
            row = authorization.get("authority", {}).get(
                "canonical_c2_product_artifacts", {})
            if not isinstance(row.get("path"), str):
                raise PreSmokeError(
                    "Link-57 authorization lacks canonical C2 artifacts")
            c2_artifact_authority_path = ROOT / row["path"]
            if (row.get("sha256") != sha(c2_artifact_authority_path)
                    or row.get("bytes")
                    != c2_artifact_authority_path.stat().st_size):
                raise PreSmokeError(
                    "Link-57 canonical C2 artifact authority drift")
        c2_frame_attribution = (
            authorization_format ==
                "lisp65-c2-top-level-frame-attribution-deployment-v1"
            and authorization.get("promotable") is False)
        if c2_frame_attribution:
            row = authorization.get("frame_attribution", {}).get(
                "c2_artifact_authority", {})
            if not isinstance(row.get("path"), str):
                raise PreSmokeError(
                    "frame attribution lacks current C2 artifact authority")
            c2_artifact_authority_path = ROOT / row["path"]
            if (row.get("sha256") != sha(c2_artifact_authority_path)
                    or row.get("bytes")
                    != c2_artifact_authority_path.stat().st_size):
                raise PreSmokeError(
                    "frame-attribution C2 artifact authority drift")
        c2_lite_phase_stamp = (
            c2_lite_link52 or c2_lite_link53 or c2_lite_link54
            or c2_lite_link55 or c2_lite_link56 or c2_lite_link57)
        c2_lite_link38 = authorization_format == (
            "lisp65-c2-lite-v6-boot-crc-abi-link38-artifact-replay-v1")
        c2_lite_bank3 = authorization_format == (
            "lisp65-c2-lite-v6-bank3-artifact-completion-v1") or (
                c2_lite_link38 or c2_lite_link40 or c2_lite_phase_stamp
                or c2_lite_link49
                or c2_lite_link50 or c2_frame_attribution)
        c2_lite = authorization_format in (
            "lisp65-c2-lite-product-link37-artifact-resume-v1",
            "lisp65-c2-lite-v6-bank3-artifact-completion-v1",
        ) or c2_lite_link38 or c2_lite_link40 or c2_lite_phase_stamp \
            or c2_lite_link49 \
            or c2_lite_link50 or c2_frame_attribution
    else:
        c2_lite_link49 = False
        c2_lite_link50 = False
        c2_lite_link40 = False
        c2_lite_link52 = False
        c2_lite_link53 = False
        c2_lite_link54 = False
        c2_lite_link55 = False
        c2_lite_link56 = False
        c2_lite_link57 = False
        c2_frame_attribution = False
        c2_lite_phase_stamp = False
        c2_lite_link38 = False
    structural_path = link / "product-substitution-link.json"
    if not structural_path.is_file():
        structural_path = link / "eighteenth-substitution-link.json"
    handoff_path = link / "handoff-z-abi-final.json"
    structural = load_json(structural_path, "candidate structural report")
    handoff = load_json(handoff_path, "candidate handoff-boundary report")
    window_publish = load_json(
        link / "kernal-window-publish-last.json",
        "candidate KERNAL-window publish-last report")
    total_publish = load_json(
        link / "total-publish-last-domain.json",
        "candidate total publish-last report")
    required_green = (
        "identity_gate", "capacity_gate", "one_truth_gate",
        "kernal_freedom_gate", "fixed_host_facade_gate",
        "pre_ownership_gate", "handoff_z_abi_gate",
    )
    if c2_lite:
        assert authorization is not None
        if c2_lite_link49 or c2_lite_link50:
            fresh = authorization.get("fresh_generic_gates", {})
            replacement = authorization.get("fresh_replacement_gates", {})
            fresh_green = (
                fresh.get("status") == "passed-frozen-generic-gate-set"
                and all("pass" in str(value) for value in
                        fresh.get("structure", {}).values()))
            replacement_green = (
                str(replacement.get("capacity", {}).get(
                    "status", "")).startswith("passed")
                and replacement.get("product_semantics", {}).get("status")
                    == "passed"
                and str(replacement.get("no_runtime_attic", {}).get(
                    "status", "")).startswith("passed")
                and replacement.get("bank3_stage_before_publish", {}).get(
                    "status") == "passed"
                and replacement.get("overlay_closure", {}).get("status")
                    == "passed-final-elf-overlay-closure"
                and replacement.get("preinstallation_island", {}).get(
                    "status") == "passed-static-preinstallation-Island-gate"
                and replacement.get("root_surrogate", {}).get(
                    "status", "").startswith("passed-bound")
                and replacement.get("append_phase_plan", {}).get(
                    "linked", {}).get("walker", {}).get(
                        "facade_routed_C_call_edges") == (
                            3 if c2_lite_link50 else 2)
                and replacement.get("workbench_crc", {}).get("status") ==
                    "passed-linked-leaf-current-workbench")
            expected_structural_format = "lisp65-c2-product-substitution-link-v2"
            expected_authorization_status = (
                "passed-new-c2-lite-persistent-header-identity-hardware-not-run"
                if c2_lite_link50 else
                "passed-new-c2-lite-facade16-identity-hardware-not-run")
        elif c2_lite_link40 or c2_lite_phase_stamp or c2_frame_attribution:
            fresh = authorization.get("fresh_generic_gates", {})
            replacement = authorization.get("fresh_replacement_gates", {})
            fresh_green = (
                all("pass" in str(value) for value in fresh.values())
                and authorization.get("fresh_prelink_gates", {}).get(
                    "status") == "passed"
                and authorization.get("fresh_real_abi_gate", {}).get(
                    "status") == "passed-all-assembler-leaf-abi-contracts")
            replacement_green = (
                replacement.get("status") == "passed"
                and str(replacement.get("capacity", {}).get(
                    "status", "")).startswith("passed")
                and replacement.get("product_semantics", {}).get("status")
                    == "passed"
                and str(replacement.get("no_runtime_attic", {}).get(
                    "status", "")).startswith("passed")
                and replacement.get("bank3_stage_before_publish", {}).get(
                    "status") == "passed"
                and replacement.get("overlay_closure", {}).get("status")
                    == "passed-final-elf-overlay-closure"
                and replacement.get("preinstallation_island", {}).get(
                    "status") == "passed-static-preinstallation-Island-gate"
                and replacement.get("generated_direct_entry", {}).get(
                    "status") == "passed-generated-product-sources-637-of-637"
                and replacement.get("workbench_crc_end_to_end", {}).get(
                    "status") ==
                        "passed-linked-leaf-equals-current-descriptor-emitter"
                and (not c2_frame_attribution or
                     (authorization.get("frame_attribution", {}).get(
                         "source_contract_gate", {}).get("status") ==
                        "passed-nonpromotable-source-and-lifetime-contract"
                      and authorization.get("frame_attribution", {}).get(
                          "linked_dataflow_gate", {}).get("status") ==
                        "passed-15-section-qualified-ff83-to-scratch-dataflows"
                      and authorization.get("frame_attribution", {}).get(
                          "capture_bytes") == 15
                      and authorization.get("frame_attribution", {}).get(
                          "acceptance_claim") == "none"))
                and (not c2_lite_phase_stamp or
                     (replacement.get("install_phase_self_stamp", {}).get(
                         "status") == (
                            "passed-linked-first-error-stamped-install-provenance"
                            if (c2_lite_link53 or c2_lite_link54
                                or c2_lite_link55 or c2_lite_link56
                                or c2_lite_link57) else
                            "passed-linked-slot-stamped-install-provenance")
                      and replacement.get("install_phase_self_stamp", {}).get(
                          "new_state_objects") == 0))
                and (not (c2_lite_link54 or c2_lite_link55
                          or c2_lite_link56 or c2_lite_link57) or
                     (replacement.get("phase06a_cutpoint", {}).get(
                         "status") ==
                            "passed-linked-phase06a-cutpoint-carrier"
                      and replacement.get("phase06a_cutpoint", {}).get(
                          "new_state_objects") == 0))
                and (not (c2_lite_link55 or c2_lite_link56
                          or c2_lite_link57) or
                     (replacement.get("phase06a_cutpoint", {}).get(
                         "append_suffix_read_domain", {}).get("status") ==
                            "passed-linked-four-phase-suffix-domain-closure"
                      and replacement.get("phase06a_cutpoint", {}).get(
                         "journal_prepare_co_residence", {}).get("status") ==
                            "passed-linked-one-record-journal-prepare-cutpoint"
                      and replacement.get("capacity", {}).get(
                          "session_catalog_records") == 48
                      and replacement.get("capacity", {}).get(
                          "session_family_bytes") == 65438))
                and (not (c2_lite_link56 or c2_lite_link57) or
                     (replacement.get("phase06a_cutpoint", {}).get(
                         "assembler_leaf_abi", {}).get(
                             "journal_prepare_selector", {}).get("status") ==
                        "passed-real-context-ABI-two-total-tail-edges-Z0"
                      and replacement.get("phase06a_cutpoint", {}).get(
                          "assembler_leaf_abi", {}).get(
                              "journal_prepare_selector", {}).get(
                                  "marker_totality", {}).get("cases") == 512)))
            expected_structural_format = "lisp65-c2-product-substitution-link-v2"
            expected_authorization_status = (
                "passed-nonpromotable-frame-attribution-deployment-authority"
                if c2_frame_attribution else
                "passed-keymap-and-published-nullary-product-identity-hardware-not-run"
                if c2_lite_link57 else
                "passed-selector-tail-Z0-product-identity-hardware-not-run"
                if c2_lite_link56 else
                ("passed-append-suffix-and-one-quantum-fusion-"
                 "product-identity-hardware-not-run")
                if c2_lite_link55 else
                "passed-phase06a-five-cutpoint-product-identity-hardware-not-run"
                if c2_lite_link54 else
                "passed-first-error-stamp-product-identity-hardware-not-run"
                if c2_lite_link53 else
                "passed-new-phase-self-stamp-product-identity-hardware-not-run"
                if c2_lite_link52 else
                "passed-new-c2-lite-real-abi-identity-hardware-not-run")
        elif c2_lite_link38:
            fresh = authorization.get("authority", {}).get(
                "generic_closure", {})
            replacement = authorization.get("fresh_artifact_gates", {})
            fresh_green = (
                fresh.get("status") == "passed"
                and fresh.get("product_closure_link_count") == 1
                and all("pass" in str(fresh.get(name, ""))
                        for name in required_green))
            replacement_green = (
                replacement.get("capacity", {}).get("status") == "passed"
                and replacement.get("semantics", {}).get("status") == "passed"
                and str(replacement.get("no_runtime_attic", {}).get(
                    "status", "")).startswith("passed")
                and replacement.get("bank3_stage_before_publish", {}).get(
                    "status") == "passed"
                and replacement.get("overlay_closure", {}).get("status")
                    == "passed-final-elf-overlay-closure"
                and replacement.get("preinstallation_island", {}).get(
                    "status") == "passed-static-preinstallation-Island-gate"
                and authorization.get("direct_entry_v6", {}).get("status")
                    == "passed-pure-artifact-637-of-637"
                and authorization.get("assembler_leaf_abi", {}).get("status")
                    == "passed-all-assembler-leaf-abi-contracts"
                and authorization.get("workbench_crc_end_to_end", {}).get(
                    "status") == "passed")
            expected_structural_format = "lisp65-c2-product-substitution-link-v2"
            expected_authorization_status = (
                "passed-link38-artifact-only-structural-closure-hardware-not-run")
        elif c2_lite_bank3:
            fresh = authorization.get("fresh_generic_gates", {})
            fresh_green = all("pass" in str(value) for value in fresh.values())
            replacement = authorization.get("fresh_c2_lite_gates", {})
            replacement_green = (
                replacement.get("capacity", {}).get("status") == "passed"
                and replacement.get("product_semantics", {}).get("status")
                    == "passed"
                and str(replacement.get("no_runtime_attic", {}).get(
                    "status", "")).startswith("passed")
                and replacement.get("bank3_stage_before_publish", {}).get(
                    "status") == "passed"
                and replacement.get("overlay_closure")
                    == "passed-final-elf-overlay-closure"
                and replacement.get("preinstallation_island")
                    == "passed-static-preinstallation-Island-gate"
                and replacement.get("section_inventory") == "passed")
            expected_structural_format = "lisp65-c2-product-substitution-link-v2"
            expected_authorization_status = (
                "passed-complete-c2-lite-bank3-candidate-hardware-not-run")
        else:
            fresh = authorization.get("fresh_generic_gates", {})
            fresh_green = all("pass" in str(value) for value in fresh.values())
            replacement = authorization.get(
                "fresh_c2_lite_replacement_gates", {})
            replacement_green = replacement.get("status") == "passed"
            expected_structural_format = (
                "lisp65-c2-lite-product-link37-artifact-completion-v1")
            expected_authorization_status = None
        if (structural.get("format") != expected_structural_format
                or structural.get("status") != "passed"
                or structural.get("product_closure_link_count") != 1
                or not fresh_green
                or not replacement_green
                or (expected_authorization_status is not None
                    and authorization.get("status")
                        != expected_authorization_status)):
            raise PreSmokeError(
                "C2-lite candidate structural report is not fully passed")
    elif structural.get("status") != "passed" or any(
            structural.get(field) != "passed" for field in required_green):
        raise PreSmokeError("candidate structural report is not fully passed")
    if structural.get("direct_entry_encoding_gate") not in (
            None, "passed-637-of-637-fixnum-values-zero"):
        raise PreSmokeError("candidate direct-entry encoding gate is not passed")
    if ("direct_entry_encoding_gate" in structural
            and structural["direct_entry_encoding_gate"]
            != "passed-637-of-637-fixnum-values-zero"):
        raise PreSmokeError("candidate direct-entry encoding claim drift")
    if structural.get("product_closure_link_count") != 1:
        raise PreSmokeError("candidate is not a single product-closure link")

    successor_path = link / "preinstall-island-successor-link.json"
    successor_kind = "preinstall-island"
    if not successor_path.is_file():
        successor_path = link / "transaction-auth-successor-link.json"
        successor_kind = "transaction-auth"
    if not successor_path.is_file():
        successor_path = link / "hot-refill-successor-link.json"
        successor_kind = "hot-refill"
    if successor_path.is_file() and not c2_lite:
        successor = load_json(successor_path, "candidate successor report")
        common_green = (
            successor.get("status")
                == "passed-new-product-identity-hardware-not-run"
            and successor.get("inheritance")
                == "none; every structural and capacity gate ran freshly"
            and successor.get("execution_accounting", {}).get(
                "product_closure_links") == 1
            and successor.get("execution_accounting", {}).get(
                "hardware_runs") == 0
            and successor.get("post_link_identity", {}).get(
                "declared_mutable_product_bytes") == 34)
        if successor_kind == "preinstall-island":
            specific_green = (
                successor.get("format")
                    == ("lisp65-c2-product-link32-preinstall-island-guard-"
                        "structural-receipt-v1")
                and successor.get("link_number") == 32
                and successor.get("capacity", {}).get(
                    "bank0_text_headroom_bytes") == 10
                and successor.get("capacity", {}).get("e000", {}).get(
                    "delta_bytes") == 0
                and successor.get("preinstallation_Island", {}).get(
                    "status") == "passed-static-preinstallation-Island-gate"
                and not successor.get("preinstallation_Island", {}).get(
                    "unguarded_or_data_references")
                and successor.get("transaction_auth", {}).get(
                    "dedicated_transaction_bss_symbols") == 0
                and successor.get("hot_refill", {}).get(
                    "direct_shared_materializer", {}).get("status") == "passed")
        elif successor_kind == "transaction-auth":
            specific_green = (
                successor.get("format")
                    == "lisp65-c2-product-link31-transaction-auth-structural-receipt-v1"
                and successor.get("link_number") == 31
                and successor.get("capacity", {}).get("e000", {}).get(
                    "delta_bytes") == 0
                and successor.get("transaction_auth", {}).get(
                    "dedicated_transaction_bss_symbols") == 0
                and successor.get("hot_refill", {}).get(
                    "direct_shared_materializer", {}).get("status") == "passed")
        else:
            specific_green = (
                successor.get("format")
                    == "lisp65-c2-product-link30-hot-refill-structural-receipt-v1"
                and successor.get("link_number") == 30
                and successor.get("e000", {}).get("delta_bytes") == 0
                and successor.get("hot_refill", {}).get(
                    "direct_shared_materializer", {}).get("status") == "passed")
        if not common_green or not specific_green:
            raise PreSmokeError("candidate successor report is not fully passed")
        product_binding = successor.get("product_identity", {}).get("product", {})
        if (product_binding.get("sha256") != structural.get("product_sha256")
                or product_binding.get("path") != str(
                    (link / "lisp65-c2-substitution-linked.prg").relative_to(ROOT))):
            raise PreSmokeError(
                "candidate successor report/product identity binding drift")
    expected_publish_domain = 42 if c2_lite_bank3 else 34
    if (window_publish.get("status") != "passed"
            or total_publish.get("status") != "passed"
            or total_publish.get("declared_domain_bytes")
                != expected_publish_domain
            or total_publish.get("bound_product_sha256")
            != structural.get("product_sha256")):
        raise PreSmokeError("candidate post-link identity binding is not fully passed")
    if (handoff.get("status") != "passed"
            or handoff.get("boundary") !=
            "firmware-owned-state-to-llvm-mos-mega65-io-and-c2-ownership-order"
            or handoff.get("io_reveal_sequence") != [
                "lda #$47", "sta $d02f", "lda #$53", "sta $d02f", "rts"]
            or handoff.get("map_operand_sequence") != [
                "tza", "tax", "tay", "ldz #$80", "map", "nop",
                "ldz #$0", "rts"]):
        raise PreSmokeError(
            "candidate lacks the complete Z/I-O/MAP handoff-boundary gate")

    paths = {
        "product": link / "lisp65-c2-substitution-linked.prg",
        "elf": link / "lisp65-c2-substitution-linked.prg.elf",
        "window": link / "c2-product-kernal-window.bin",
        "boot_family": link / "runtime-overlays-boot-final.bin",
        "session_family": link / "runtime-overlays-session-final.bin",
        "shelf": SUBSTITUTION / "product-shelf-v4-direct.bin",
        "c2d": SUBSTITUTION / "initial.c2d-v3.bin",
        "contract": link / "resolved-profile.txt",
        "stage_header": link / "stage-config.h",
    }
    region1 = link / "runtime-overlays-session-final-region1.bin"
    if region1.is_file():
        paths["session_region1"] = region1
    if c2_frame_attribution or c2_lite_link57:
        assert c2_artifact_authority_path is not None
        current_artifacts = load_json(
            c2_artifact_authority_path,
            "current C2 artifact authority")
        shelf_binding = current_artifacts.get("artifacts", {}).get("shelf", {})
        if not isinstance(shelf_binding.get("path"), str):
            raise PreSmokeError(
                "current C2 authority lacks shelf binding")
        shelf_path = ROOT / shelf_binding["path"]
        if (shelf_binding.get("sha256") != sha(shelf_path)
                or shelf_binding.get("bytes") != shelf_path.stat().st_size):
            raise PreSmokeError(
                "current shelf binding drift")
        paths["shelf"] = shelf_path
    if c2_lite:
        assert authorization is not None
        artifact_authority = authorization
        if c2_lite_link50:
            protected = authorization.get("protected_planes", {})
            for label, key in (("c2d", "c2d"),
                               ("bank2_static", "bank2_static")):
                row = protected.get(key, {})
                if not isinstance(row.get("path"), str):
                    raise PreSmokeError(
                        f"Link-50 authorization lacks {label} binding")
                path = ROOT / row["path"]
                if (row.get("sha256") != sha(path)
                        or row.get("bytes") != path.stat().st_size):
                    raise PreSmokeError(
                        f"Link-50 {label} protected-plane binding drift")
                paths[label] = path
        elif c2_lite_link49:
            first_binding = authorization.get("authority", {}).get(
                "checker_model_first_red", {})
            if not isinstance(first_binding.get("path"), str):
                raise PreSmokeError(
                    "Link-49 authorization lacks protected-tree authority")
            first_path = ROOT / first_binding["path"]
            if (first_binding.get("sha256") != sha(first_path)
                    or first_binding.get("bytes") != first_path.stat().st_size):
                raise PreSmokeError(
                    "Link-49 protected-tree authority binding drift")
            first = load_json(first_path, "Link-49 protected-tree authority")
            evidence = first.get("evidence", {})
            link49_planes = {
                "c2d": (
                    "fresh-c2-lite-prelink-gates/v6-semantics/"
                    "initial.c2d-v6.bin"),
                "bank2_static": (
                    "fresh-c2-lite-prelink-gates/v6-semantics/"
                    "bank2-static-code.bin"),
            }
            for label, relative in link49_planes.items():
                row = evidence.get(relative, {})
                path = link / relative
                if (row.get("sha256") != sha(path)
                        or row.get("bytes") != path.stat().st_size):
                    raise PreSmokeError(
                        f"Link-49 {label} protected-plane binding drift")
                paths[label] = path
        elif c2_lite_link40 or c2_lite_phase_stamp or c2_frame_attribution:
            if c2d_catalog_rebind is not None:
                corrected = c2d_catalog_rebind.get("corrected_c2d", {})
                host_artifacts = {
                    "c2d": corrected.get("new", {}),
                    "code": corrected.get("bank2_static", {}),
                }
                accounting = c2d_catalog_rebind.get(
                    "execution_accounting", {})
                audit = c2d_catalog_rebind.get("header_source_audit", {})
                if (c2d_catalog_rebind.get("status") !=
                        "passed-c2d-v6-canonical-header-identities-hardware-not-run"
                        or accounting.get("product_compiler_runs") != 0
                        or accounting.get("product_linker_runs") != 0
                        or accounting.get("product_links") != 0
                        or accounting.get("hardware_runs") != 0
                        or corrected.get("changed_offsets") != [40, 41, 42, 43]
                        or corrected.get("new_catalog_crc32") != "0x3d6302f3"
                        or corrected.get("product_build_id_unchanged")
                            != "0x69496476"
                        or not corrected.get("all_noncatalog_bytes_equal")
                        or not corrected.get("executable_plane_byte_identical")
                        or audit.get("status") !=
                            "passed-all-48-header-bytes-accounted"
                        or audit.get("covered_byte_count") != 48
                        or audit.get("private_identity_derivations") != []):
                    raise PreSmokeError(
                        "C2D catalog rebind is not an exact audited correction")
                for label, authorized in (
                        ("product", c2d_catalog_rebind.get(
                            "product_identity", {}).get("product", {})),
                        ("ELF", c2d_catalog_rebind.get(
                            "product_identity", {}).get("elf", {}))):
                    expected = (link / "lisp65-c2-substitution-linked.prg"
                                if label == "product" else
                                link / "lisp65-c2-substitution-linked.prg.elf")
                    if (authorized.get("path") != str(expected.relative_to(ROOT))
                            or authorized.get("sha256") != sha(expected)
                            or authorized.get("bytes") != expected.stat().st_size):
                        raise PreSmokeError(
                            f"C2D catalog rebind {label} binding drift")
            elif c2d_identity_rebind is not None:
                corrected = c2d_identity_rebind.get("corrected_c2d", {})
                host_artifacts = {
                    "c2d": corrected.get("new", {}),
                    "code": corrected.get("bank2_static", {}),
                }
                accounting = c2d_identity_rebind.get(
                    "execution_accounting", {})
                if (c2d_identity_rebind.get("status") !=
                        "passed-c2d-v6-canonical-product-identity-hardware-not-run"
                        or accounting.get("product_compiler_runs") != 0
                        or accounting.get("product_linker_runs") != 0
                        or accounting.get("product_links") != 0
                        or accounting.get("hardware_runs") != 0
                        or corrected.get("changed_offsets") != [44, 45, 46, 47]
                        or corrected.get("new_build_id") != "0x69496476"
                        or not corrected.get("all_nonidentity_bytes_equal")
                        or not corrected.get("executable_plane_byte_identical")):
                    raise PreSmokeError(
                        "C2D identity rebind is not an exact passed correction")
                for label, authorized in (
                        ("product", c2d_identity_rebind.get(
                            "product_identity", {}).get("product", {})),
                        ("ELF", c2d_identity_rebind.get(
                            "product_identity", {}).get("elf", {}))):
                    expected = (link / "lisp65-c2-substitution-linked.prg"
                                if label == "product" else
                                link / "lisp65-c2-substitution-linked.prg.elf")
                    if (authorized.get("path") != str(expected.relative_to(ROOT))
                            or authorized.get("sha256") != sha(expected)
                            or authorized.get("bytes") != expected.stat().st_size):
                        raise PreSmokeError(
                            f"C2D identity rebind {label} binding drift")
            else:
                host_artifacts = authorization.get(
                    "fresh_prelink_gates", {}).get(
                        "c2d_v6_host_semantics", {}).get("artifacts", {})
            for label, key in (("c2d", "c2d"),
                               ("bank2_static", "code")):
                row = host_artifacts.get(key, {})
                if not isinstance(row.get("path"), str):
                    raise PreSmokeError(
                        f"Link-40 authorization lacks {label} binding")
                path = ROOT / row["path"]
                if (row.get("sha256") != sha(path)
                        or row.get("bytes") != path.stat().st_size):
                    raise PreSmokeError(
                        f"Link-40 {label} deployment-plane binding drift")
                paths[label] = path
        elif c2_lite_link38:
            first_binding = authorization.get("authority", {}).get(
                "first_red", {})
            if not isinstance(first_binding.get("path"), str):
                raise PreSmokeError(
                    "Link-38 authorization lacks protected-tree authority")
            first_path = ROOT / first_binding["path"]
            if (first_binding.get("sha256") != sha(first_path)
                    or first_binding.get("bytes") != first_path.stat().st_size):
                raise PreSmokeError(
                    "Link-38 protected-tree authority binding drift")
            first = load_json(first_path, "Link-38 protected-tree authority")
            evidence = first.get("evidence", {})
            link38_planes = {
                "c2d": (
                    "fresh-c2-lite-prelink-gates/v6-semantics/"
                    "initial.c2d-v6.bin"),
                "bank2_static": (
                    "fresh-c2-lite-prelink-gates/v6-semantics/"
                    "bank2-static-code.bin"),
            }
            for label, relative in link38_planes.items():
                row = evidence.get(relative, {})
                path = link / relative
                if (row.get("sha256") != sha(path)
                        or row.get("bytes") != path.stat().st_size):
                    raise PreSmokeError(
                        f"Link-38 {label} protected-plane binding drift")
                paths[label] = path
        elif c2_lite_bank3:
            prior_binding = authorization.get("authority", {}).get(
                "prior_c2_lite_structural_baseline", {})
            if not isinstance(prior_binding.get("path"), str):
                raise PreSmokeError(
                    "Bank-3 C2-lite authorization lacks its C2D-v6 authority")
            prior_path = ROOT / prior_binding["path"]
            if (prior_binding.get("sha256") != sha(prior_path)
                    or prior_binding.get("bytes") != prior_path.stat().st_size):
                raise PreSmokeError(
                    "Bank-3 C2-lite C2D-v6 authority binding drift")
            artifact_authority = load_json(
                prior_path, "bound C2-lite C2D-v6 authority")
        if (not c2_lite_link38 and not c2_lite_link40
                and not c2_lite_phase_stamp
                and not c2_frame_attribution
                and not c2_lite_link49 and not c2_lite_link50):
            host_artifacts = artifact_authority.get(
                "artifact_model_replay", {}).get(
                    "c2d_v6_host_semantics", {}).get("artifacts", {})
            c2d_binding = host_artifacts.get("c2d", {})
            code_binding = host_artifacts.get("code", {})
            for label, row in (("C2D-v6", c2d_binding),
                               ("Bank-2 static code", code_binding)):
                if (not isinstance(row, dict)
                        or not isinstance(row.get("path"), str)):
                    raise PreSmokeError(
                        f"C2-lite authorization lacks {label} binding")
                path = ROOT / row["path"]
                if (row.get("sha256") != sha(path)
                        or row.get("bytes") != path.stat().st_size):
                    raise PreSmokeError(f"C2-lite {label} binding drift")
            paths["c2d"] = ROOT / c2d_binding["path"]
            paths["bank2_static"] = ROOT / code_binding["path"]
    for name, path in paths.items():
        regular(path, f"candidate source {name}")
    if sha(paths["product"]) != structural.get("product_sha256"):
        raise PreSmokeError("candidate product differs from its structural report")
    if c2_lite:
        verify_c2d_product_identity(paths, c2_artifact_authority_path)
    generated = regular(link / "c2-kernal-window.generated.h",
                        "candidate generated KERNAL-window header").decode("ascii")
    expected_window = re.search(
        r'C2_KERNAL_WINDOW_SHA256 "([0-9a-f]{64})"', generated)
    if not expected_window or sha(paths["window"]) != expected_window.group(1):
        raise PreSmokeError("candidate KERNAL window differs from its generated binding")
    window_identity = window_publish.get("single_product_link_window", {})
    if (window_identity.get("sha256") != sha(paths["window"])
            or window_identity.get("crc16")
            != f"0x{crc16(regular(paths['window'], 'candidate KERNAL window')):04x}"):
        raise PreSmokeError("candidate post-link KERNAL-window identity drift")
    product = regular(paths["product"], "candidate bound product")
    for operand in window_publish.get("binding_operands", []):
        offset = operand.get("file_offset")
        value = operand.get("published_value")
        if (not isinstance(offset, int) or not isinstance(value, int)
                or offset >= len(product) or product[offset] != value):
            raise PreSmokeError("candidate KERNAL CRC operand binding drift")
    if AUTHORIZATION_RECEIPT is not None:
        assert authorization is not None
        accounting = authorization.get("execution_accounting", {})
        authorized_product = authorization.get("product_identity", {}).get(
            "product", {})
        authorized_elf = authorization.get("product_identity", {}).get(
            "elf", {})
        if not str(authorization.get("status", "")).startswith("passed-"):
            raise PreSmokeError("candidate authorization receipt is not passed")
        artifact_only = (
            (accounting.get("compiler_runs") == 0
             and accounting.get("linker_runs") == 0)
            or (accounting.get("additional_compiler_runs") == 0
                and accounting.get("additional_linker_runs") == 0
                and accounting.get("product_closure_links") == 1)
            or (accounting.get("artifact_completion_compiler_runs") == 0
                and accounting.get("artifact_completion_linker_runs") == 0
                and accounting.get("product_links") == 0)
            or (accounting.get("artifact_resume_compiler_runs") == 0
                and accounting.get("artifact_resume_linker_runs") == 0
                and accounting.get("artifact_resume_product_closure_links")
                    == 0))
        direct_structural_authority = (
            (c2_lite_link40 or c2_lite_phase_stamp)
            and accounting.get("resident_island_seed_links") == 1
            and accounting.get("product_closure_links") == 1
            and accounting.get("latency_attempts_consumed") == (
                "1/2" if c2_lite_link57 else "0/2"))
        diagnostic_structural_authority = (
            c2_frame_attribution
            and accounting.get("resident_island_seed_links") == 1
            and accounting.get("product_closure_links") == 1
            and accounting.get("hardware_runs") == 0
            and accounting.get("latency_attempts_consumed_this_run") == 0
            and accounting.get("completed_latency_measurements") == "1/2")
        if (not (artifact_only or direct_structural_authority)
                and not diagnostic_structural_authority
                or accounting.get("hardware_runs") != 0):
            raise PreSmokeError(
                "candidate authorization was neither a pure artifact replay "
                "nor the exact fresh Real-ABI structural closure")
        for label, authorized, path in (
                ("product", authorized_product, paths["product"]),
                ("ELF", authorized_elf, paths["elf"])):
            if (authorized.get("path") != str(path.relative_to(ROOT))
                    or authorized.get("sha256") != sha(path)
                    or authorized.get("bytes") != path.stat().st_size):
                raise PreSmokeError(
                    f"candidate authorization {label} binding drift")
    return paths


def prepare(out: Path) -> None:
    if out.exists():
        raise PreSmokeError(f"pre-smoke output must be fresh: {out}")
    paths = verify_source_bindings()
    out.mkdir(parents=True)
    bank3_bootstrap = False
    if AUTHORIZATION_RECEIPT is not None:
        authorization_format = load_json(
            AUTHORIZATION_RECEIPT, "candidate authorization receipt").get(
                "format")
        bank3_bootstrap = (
            c2_lite_real_abi_link_number(authorization_format) is not None
            or authorization_format in (
            "lisp65-c2-lite-v6-bank3-artifact-completion-v1",
            "lisp65-c2-lite-v6-boot-crc-abi-link38-artifact-replay-v1",
            "lisp65-c2-lite-v6-c2d-product-identity-rebind-v1",
            "lisp65-c2-lite-v6-c2d-catalog-identity-rebind-v1",
            "lisp65-c2-lite-v6-link49-facade16-artifact-replay-v1",
            "lisp65-c2-lite-v6-link50-persistent-header-artifact-replay-v1",
            "lisp65-c2-lite-v6-link52-phase-self-stamp-v1",
            "lisp65-c2-lite-v6-link53-first-fault-stamp-v1",
            "lisp65-c2-lite-v6-link54-phase06a-cutpoint-v1",
            "lisp65-c2-lite-v6-link55-append-suffix-fusion-final-v1",
            "lisp65-c2-lite-v6-link56-selector-tail-z-v1",
            "lisp65-c2-lite-v6-link57-keymap-nullary-v1",
            "lisp65-c2-top-level-frame-attribution-deployment-v1"))
    elf_symbols = symbols(paths["elf"], bank3_bootstrap=bank3_bootstrap)
    start = elf_symbols["__lisp65_workbench_overlay_start"]
    end = elf_symbols["__lisp65_workbench_overlay_end"]
    entry = elf_symbols["vm_workbench_boot_overlay_entry"]
    if not 0 < start <= entry < end <= 0x10000:
        raise PreSmokeError("boot-overlay ELF geometry is invalid")

    overlay = out / "boot-overlay.raw.bin"
    # llvm-objcopy rewrites its input in place when no explicit output object
    # is given, even for --dump-section.  Work only on a disposable copy and
    # name an explicit normalized output so the SHA-bound evidence ELF is
    # never an objcopy destination.
    scratch_input = out / "elf-section-source.copy"
    scratch_output = out / "elf-section-normalized.discard"
    shutil.copyfile(paths["elf"], scratch_input)
    run([str(OBJCOPY), "--dump-section",
         f".lisp65_workbench_overlay={overlay}",
         str(scratch_input), str(scratch_output)])
    scratch_input.unlink()
    scratch_output.unlink()
    overlay_data = regular(overlay, "boot-overlay payload")
    if len(overlay_data) != end - start:
        raise PreSmokeError("boot-overlay extraction length differs from ELF geometry")

    contract_sha = sha(paths["contract"])
    build_id = int(contract_sha[:8], 16)
    header_text = regular(paths["stage_header"], "stage header").decode("ascii")
    expected_build = re.search(r"LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x([0-9a-fA-F]+)UL", header_text)
    expected_bank = re.search(r"LISP65_BOOT_OVERLAY_STAGE_BANK 0x([0-9a-fA-F]+)u", header_text)
    expected_off = re.search(r"LISP65_BOOT_OVERLAY_STAGE_OFF 0x([0-9a-fA-F]+)u", header_text)
    if not expected_build or not expected_bank or not expected_off:
        raise PreSmokeError("stage header is missing a pinned overlay binding")
    if int(expected_build.group(1), 16) != build_id:
        raise PreSmokeError("boot-overlay build ID differs from resolved-profile SHA")
    header_address = (int(expected_bank.group(1), 16) << 16) | int(expected_off.group(1), 16)
    if header_address != BOOT_OVERLAY_STAGE:
        raise PreSmokeError("boot-overlay stage address drift")

    descriptor = boot_overlay_descriptor(
        build_id=build_id, start=start, entry=entry, payload=overlay_data)
    stage = out / "boot-overlay.stage.bin"
    boot_chain: dict[str, Any] | None = None
    if bank3_bootstrap:
        first_start = elf_symbols["__lisp65_boot_bank3_stage_start"]
        first_end = elf_symbols["__lisp65_boot_bank3_stage_end"]
        first_entry = elf_symbols["vm_bank3_boot_stage_entry"]
        if not 0 < first_start <= first_entry < first_end <= 0x10000:
            raise PreSmokeError("Bank-3 bootstrap ELF geometry is invalid")
        first_payload = out / "boot-bank3-stage.raw.bin"
        first_scratch_input = out / "elf-bank3-section-source.copy"
        first_scratch_output = out / "elf-bank3-section-normalized.discard"
        shutil.copyfile(paths["elf"], first_scratch_input)
        run([str(OBJCOPY), "--dump-section",
             f".lisp65_boot_bank3_stage={first_payload}",
             str(first_scratch_input), str(first_scratch_output)])
        first_scratch_input.unlink()
        first_scratch_output.unlink()
        first_data = regular(first_payload, "Bank-3 bootstrap payload")
        if len(first_data) != first_end - first_start:
            raise PreSmokeError(
                "Bank-3 bootstrap extraction length differs from ELF geometry")
        first_descriptor = boot_overlay_descriptor(
            build_id=build_id, start=first_start, entry=first_entry,
            payload=first_data)
        stage_offset = int(expected_off.group(1), 16)
        second_offset = ((stage_offset + DESCRIPTOR_BYTES + len(first_data)
                          + 0xff) & ~0xff) - stage_offset
        first_record = first_descriptor + first_data
        if second_offset < len(first_record):
            raise PreSmokeError("Bank-3 bootstrap successor offset underflow")
        stage_data = (first_record + bytes(second_offset - len(first_record))
                      + descriptor + overlay_data)
        boot_chain = {
            "format": "L65O-v1-fixed-two-record-bootstrap",
            "first_record": {
                "role": "bank3-boot-stager",
                "vma": f"0x{first_start:04x}",
                "entry": f"0x{first_entry:04x}",
                "payload_bytes": len(first_data),
                "payload_crc16": f"0x{crc16(first_data):04x}",
                "record_offset": 0,
            },
            "second_record": {
                "role": "workbench-overlay",
                "vma": f"0x{start:04x}",
                "entry": f"0x{entry:04x}",
                "payload_bytes": len(overlay_data),
                "payload_crc16": f"0x{crc16(overlay_data):04x}",
                "record_offset": second_offset,
            },
            "padding_bytes": second_offset - len(first_record),
            "total_bytes": len(stage_data),
        }
        write_atomic(stage, stage_data)
    else:
        write_atomic(stage, descriptor + overlay_data)

    deployment = {
        "format": "lisp65-c2-hardware-presmoke-deployment-v2",
        "status": "ready-receipt-less",
        "claim_limit": (
            "Host-verified deployment plan for a receipt-less fail-fast hardware "
            "pre-smoke. It is not hardware evidence, promotion, acceptance or release."),
        "product": binding(paths["product"], 0x00002001),
        "preloads": [
            binding(paths["c2d"], C2D_STAGE),
            binding(stage, BOOT_OVERLAY_STAGE),
            binding(paths["session_family"], SESSION_FAMILY_STAGE),
            binding(paths["shelf"], SHELF_STAGE),
            binding(paths["boot_family"], BOOT_FAMILY_STAGE),
            *(
                [binding(paths["session_region1"], R.REGION1_SOURCE_BASE)]
                if "session_region1" in paths else []
            ),
            binding(paths["window"], KERNAL_WINDOW_STAGE),
        ],
        "boot_overlay": {
            "build_id": f"0x{build_id:08x}",
            "vma": f"0x{start:04x}",
            "entry": f"0x{entry:04x}",
            "payload_bytes": len(overlay_data),
            "payload_crc16": f"0x{crc16(overlay_data):04x}",
            "descriptor_bytes": DESCRIPTOR_BYTES,
        },
        "span_checks": {
            "c2d_ends_before_boot_overlay": C2D_STAGE + paths["c2d"].stat().st_size <= BOOT_OVERLAY_STAGE,
            "session_ends_before_shelf": SESSION_FAMILY_STAGE + paths["session_family"].stat().st_size <= SHELF_STAGE,
            "shelf_ends_before_boot_family": SHELF_STAGE + paths["shelf"].stat().st_size <= BOOT_FAMILY_STAGE,
            "region1_source_after_boot_before_window": (
                "session_region1" not in paths
                or (
                    BOOT_FAMILY_STAGE + paths["boot_family"].stat().st_size
                        <= R.REGION1_SOURCE_BASE
                    and R.REGION1_SOURCE_BASE
                        + paths["session_region1"].stat().st_size
                        <= KERNAL_WINDOW_STAGE
                )
            ),
            "window_ends_at_attic_limit": KERNAL_WINDOW_STAGE + paths["window"].stat().st_size == 0x08800000,
        },
        "new_product_links": 0,
    }
    if boot_chain is not None:
        deployment["boot_chain"] = boot_chain
    if CANDIDATE_LINK is None:
        deployment["source_pin_receipt"] = {
            "path": str(PIN_RECEIPT.relative_to(ROOT)),
            "sha256": sha(PIN_RECEIPT),
        }
        deployment["source_replay_receipt"] = {
            "path": str(REPLAY_RECEIPT.relative_to(ROOT)),
            "sha256": sha(REPLAY_RECEIPT),
        }
    else:
        structural = CANDIDATE_LINK / "product-substitution-link.json"
        if not structural.is_file():
            structural = CANDIDATE_LINK / "eighteenth-substitution-link.json"
        handoff = CANDIDATE_LINK / "handoff-z-abi-final.json"
        deployment["source_candidate"] = {
            "directory": str(CANDIDATE_LINK.relative_to(ROOT)),
            "structural_report_sha256": sha(structural),
            "handoff_z_gate_sha256": sha(handoff),
        }
        if AUTHORIZATION_RECEIPT is not None:
            deployment["source_candidate"]["authorization_receipt"] = {
                "path": str(AUTHORIZATION_RECEIPT.relative_to(ROOT)),
                "sha256": sha(AUTHORIZATION_RECEIPT),
            }
            if load_json(AUTHORIZATION_RECEIPT,
                         "candidate authorization receipt").get("format") == (
                    "lisp65-c2-lite-v6-c2d-catalog-identity-rebind-v1"):
                deployment["source_candidate"]["c2d_header_source_audit"] = {
                    "path": str(C2D_HEADER_AUDIT_RECEIPT.relative_to(ROOT)),
                    "sha256": sha(C2D_HEADER_AUDIT_RECEIPT),
                }
        successor = CANDIDATE_LINK / "preinstall-island-successor-link.json"
        if not successor.is_file():
            successor = CANDIDATE_LINK / "transaction-auth-successor-link.json"
        if not successor.is_file():
            successor = CANDIDATE_LINK / "hot-refill-successor-link.json"
        if successor.is_file():
            deployment["source_candidate"]["successor_report"] = {
                "path": str(successor.relative_to(ROOT)),
                "sha256": sha(successor),
            }
    if not all(deployment["span_checks"].values()):
        raise PreSmokeError("deployment spans overlap or drift")
    write_atomic(out / "deployment.json",
                 (json.dumps(deployment, indent=2, sort_keys=True) + "\n").encode("ascii"))
    verify(out)
    print(f"c2-product-hw-presmoke: PREPARE PASS out={out} new-links=0")


def verify(out: Path) -> None:
    verify_source_bindings()
    deployment = load_json(out / "deployment.json", "pre-smoke deployment")
    if deployment.get("status") != "ready-receipt-less" or deployment.get("new_product_links") != 0:
        raise PreSmokeError("pre-smoke deployment status drift")
    if CANDIDATE_LINK is None:
        if sha(PIN_RECEIPT) != deployment["source_pin_receipt"]["sha256"]:
            raise PreSmokeError("pre-smoke pin-receipt binding drift")
        if sha(REPLAY_RECEIPT) != deployment["source_replay_receipt"]["sha256"]:
            raise PreSmokeError("pre-smoke replay-receipt binding drift")
    else:
        candidate = deployment.get("source_candidate", {})
        if candidate.get("directory") != str(CANDIDATE_LINK.relative_to(ROOT)):
            raise PreSmokeError("pre-smoke candidate directory binding drift")
        structural = CANDIDATE_LINK / "product-substitution-link.json"
        if not structural.is_file():
            structural = CANDIDATE_LINK / "eighteenth-substitution-link.json"
        if sha(structural) != candidate.get("structural_report_sha256"):
            raise PreSmokeError("pre-smoke candidate structural binding drift")
        if sha(CANDIDATE_LINK / "handoff-z-abi-final.json") != candidate.get(
                "handoff_z_gate_sha256"):
            raise PreSmokeError("pre-smoke candidate handoff binding drift")
        successor = CANDIDATE_LINK / "preinstall-island-successor-link.json"
        if not successor.is_file():
            successor = CANDIDATE_LINK / "transaction-auth-successor-link.json"
        if not successor.is_file():
            successor = CANDIDATE_LINK / "hot-refill-successor-link.json"
        bound_successor = candidate.get("successor_report")
        if successor.is_file():
            if (not isinstance(bound_successor, dict)
                    or bound_successor.get("path")
                    != str(successor.relative_to(ROOT))
                    or bound_successor.get("sha256") != sha(successor)):
                raise PreSmokeError(
                    "pre-smoke candidate successor report binding drift")
        elif bound_successor is not None:
            raise PreSmokeError("pre-smoke candidate lost its successor report")
        bound_authorization = candidate.get("authorization_receipt")
        if AUTHORIZATION_RECEIPT is not None:
            if (not isinstance(bound_authorization, dict)
                    or bound_authorization.get("path")
                    != str(AUTHORIZATION_RECEIPT.relative_to(ROOT))
                    or bound_authorization.get("sha256")
                    != sha(AUTHORIZATION_RECEIPT)):
                raise PreSmokeError(
                    "pre-smoke candidate authorization binding drift")
            if load_json(AUTHORIZATION_RECEIPT,
                         "candidate authorization receipt").get("format") == (
                    "lisp65-c2-lite-v6-c2d-catalog-identity-rebind-v1"):
                bound_audit = candidate.get("c2d_header_source_audit")
                if (not isinstance(bound_audit, dict)
                        or bound_audit.get("path") != str(
                            C2D_HEADER_AUDIT_RECEIPT.relative_to(ROOT))
                        or bound_audit.get("sha256") !=
                            sha(C2D_HEADER_AUDIT_RECEIPT)):
                    raise PreSmokeError(
                        "pre-smoke C2D header-source audit binding drift")
        elif bound_authorization is not None:
            raise PreSmokeError(
                "pre-smoke deployment unexpectedly gained an authorization")
    for item in [deployment["product"], *deployment["preloads"]]:
        path = ROOT / item["path"]
        assert_binding(path, item, "pre-smoke deployment artifact")
    if not all(deployment["span_checks"].values()):
        raise PreSmokeError("pre-smoke span check drift")
    print(f"c2-product-hw-presmoke: VERIFY PASS out={out} new-links=0")


def selftest() -> None:
    if crc16(b"123456789") != 0x29B1:
        raise PreSmokeError("CRC-16/CCITT-FALSE selftest failed")
    sample = struct.pack("<4sBBIHHHH", DESCRIPTOR_MAGIC, 1, 18,
                         0x12345678, 0xC000, 0xC123, 0x234, 0xABCD)
    if len(sample) != DESCRIPTOR_BYTES or sample[:4] != DESCRIPTOR_MAGIC:
        raise PreSmokeError("boot-overlay descriptor selftest failed")
    c2d = bytearray(48)
    c2d[:6] = b"C2D\0\x06\x30"
    catalog = bytes(range(64))
    catalog_crc = zlib.crc32(catalog) & 0xffffffff
    shelf = bytearray(32) + bytearray(catalog)
    shelf[:8] = b"L65S\x04\x20\x20\x02"
    struct.pack_into("<H", shelf, 8, 32)
    struct.pack_into("<H", shelf, 16, len(catalog))
    struct.pack_into("<I", shelf, 18, catalog_crc)
    struct.pack_into("<I", shelf, 22, 0x69496476)
    struct.pack_into("<I", c2d, 40, catalog_crc)
    struct.pack_into("<I", c2d, 44, 0x69496476)
    if c2d_build_id(bytes(c2d)) != 0x69496476:
        raise PreSmokeError("C2D build-identity parser selftest failed")
    mutated = bytearray(c2d)
    struct.pack_into("<I", mutated, 44, 0x79616f27)
    if c2d_build_id(bytes(mutated)) == c2d_build_id(bytes(c2d)):
        raise PreSmokeError("C2D build-identity mutation was accepted")
    if shelf_product_identity(bytes(shelf)) != (catalog_crc, 0x69496476):
        raise PreSmokeError("shelf product-identity parser selftest failed")
    if (c2_lite_real_abi_link_number(
            "lisp65-c2-lite-v6-real-abi-link41-structural-v1") != 41
            or c2_lite_real_abi_link_number(
                "lisp65-c2-lite-v6-real-abi-link0-structural-v1") is not None
            or c2_lite_real_abi_link_number(
                "lisp65-c2-lite-v6-real-abi-link41-artifact-v1") is not None
            or c2_lite_real_abi_link_number(None) is not None):
        raise PreSmokeError("Real-ABI authorization-family selftest failed")
    mutated_catalog = bytearray(c2d)
    struct.pack_into("<I", mutated_catalog, 40, catalog_crc ^ 1)
    if c2d_catalog_crc(bytes(mutated_catalog)) == c2d_catalog_crc(bytes(c2d)):
        raise PreSmokeError("C2D catalog-identity mutation was accepted")
    corrupted_shelf = bytearray(shelf)
    corrupted_shelf[-1] ^= 1
    try:
        shelf_product_identity(bytes(corrupted_shelf))
    except PreSmokeError:
        pass
    else:
        raise PreSmokeError("corrupt shelf catalog was accepted")
    print("c2-product-hw-presmoke: SELFTEST PASS")


def main() -> int:
    global AUTHORIZATION_RECEIPT, CANDIDATE_LINK
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "verify", "selftest"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--candidate-dir", type=Path)
    parser.add_argument("--authorization-receipt", type=Path)
    args = parser.parse_args()
    if args.candidate_dir is not None:
        CANDIDATE_LINK = args.candidate_dir.resolve()
    if args.authorization_receipt is not None:
        if CANDIDATE_LINK is None:
            parser.error("--authorization-receipt requires --candidate-dir")
        AUTHORIZATION_RECEIPT = args.authorization_receipt.resolve()
    try:
        if args.mode == "prepare":
            prepare(args.out.resolve())
        elif args.mode == "verify":
            verify(args.out.resolve())
        else:
            selftest()
    except PreSmokeError as exc:
        print(f"c2-product-hw-presmoke: FAIL {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
