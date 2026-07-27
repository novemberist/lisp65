#!/usr/bin/env python3
"""Prepare/verify/evaluate Class-B cycle 1 for the Link-44 vm_run_dir latch."""

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

import c2_product_hw_presmoke as HW


ROOT = Path(__file__).resolve().parents[2]
LINK = ROOT / "build/c2.2/substitution/link44-vm-run-dir-latch-diagnostic"
BASE = ROOT / "build/c2.2/substitution/product-link-44-c2-lite-v6-bank2-target-stage-replay"
OUT = ROOT / "build/c2.2/hardware-link44-vm-run-dir-latch-cycle1"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
DIAG_RECEIPT = EVIDENCE / "c2.2-link44-vm-run-dir-latch-diagnostic-link-receipt.json"
WPLTO_RECEIPT = EVIDENCE / "c2.2-link44-vm-run-dir-latch-wplto-pure-replay-receipt.json"
BASE_RECEIPT = EVIDENCE / "c2.2-product-link44-c2-lite-v6-bank2-target-stage-replay-structural-receipt.json"
HARDWARE_RECEIPT = EVIDENCE / "c2.2-link44-vm-run-dir-latch-hardware-cycle1-receipt.json"
SHELF = ROOT / "build/c2.2/substitution/product-shelf-v4-direct.bin"
AUTHORITY = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
TEST_FORM = "(list(peek 255 132)(peek 255 131)(peek 255 132))"
LATCH_START = 0xBFC3
LATCH_END = 0xBFC7
LATCH_CONTEXT = 0x8201


class DiagnosticError(RuntimeError):
    pass


def read_bytes(path: Path, label: str) -> bytes:
    try:
        info = path.lstat()
    except OSError as exc:
        raise DiagnosticError(f"missing {label}: {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise DiagnosticError(f"{label} must be a regular, symlink-free file: {path}")
    return path.read_bytes()


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(read_bytes(path, label).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DiagnosticError(f"invalid {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DiagnosticError(f"{label} root is not an object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(read_bytes(path, "hash input")).hexdigest()


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def binding(path: Path, address: int | None = None) -> dict[str, Any]:
    data = read_bytes(path, "bound artifact")
    value: dict[str, Any] = {
        "path": relative(path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DiagnosticError(message)


def assert_binding(row: object, path: Path, label: str) -> None:
    require(isinstance(row, dict), f"{label} binding is absent")
    assert isinstance(row, dict)
    require(row.get("path") == relative(path), f"{label} path drift")
    require(row.get("bytes") == path.stat().st_size, f"{label} size drift")
    require(row.get("sha256") == sha(path), f"{label} SHA drift")


def chmod_read_only(path: Path) -> None:
    os.chmod(path, 0o444)


def source_paths() -> dict[str, Path]:
    return {
        "product": LINK / "lisp65-c2-substitution-linked.prg",
        "elf": LINK / "lisp65-c2-substitution-linked.prg.elf",
        "map": LINK / "lisp65-c2-substitution-linked.prg.map",
        "window": LINK / "c2-product-kernal-window.bin",
        "boot_family": LINK / "runtime-overlays-boot-final.bin",
        "session_family": LINK / "runtime-overlays-session-final.bin",
        "shelf": SHELF,
        "c2d": LINK / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin",
        "bank2_static": LINK / "fresh-c2-lite-prelink-gates/v6-semantics/bank2-static-code.bin",
        "contract": LINK / "resolved-profile.txt",
        "stage_header": LINK / "stage-config.h",
    }


def verify_sources() -> dict[str, Path]:
    paths = source_paths()
    for name, path in paths.items():
        read_bytes(path, f"diagnostic source {name}")

    diagnostic = load_json(DIAG_RECEIPT, "diagnostic link receipt")
    require(diagnostic.get("format") ==
            "lisp65-c2-lite-v6-vm-run-dir-latch-diagnostic-link-v1",
            "diagnostic receipt format drift")
    require(diagnostic.get("status") ==
            "passed-nonpromotable-vm-run-dir-latch-hardware-not-run",
            "diagnostic link is not hardware-ready")
    require(diagnostic.get("promotable") is False,
            "diagnostic receipt lost its nonpromotable boundary")
    require(diagnostic.get("delegation") == {"class": "B", "cycle": "1-of-3"},
            "diagnostic Class-B cycle binding drift")
    accounting = diagnostic.get("execution_accounting", {})
    require(accounting.get("hardware_runs") == 0
            and accounting.get("promotable_product_links") == 0
            and accounting.get("whole_program_lto_closure_links") == 1,
            "diagnostic execution accounting drift")
    assert_binding(diagnostic.get("identity"), paths["product"],
                   "diagnostic product")
    require(diagnostic.get("identity", {}).get("diagnostic_only") is True,
            "diagnostic product is not marked diagnostic-only")
    require(diagnostic.get("linked_latch", {}).get("cells") == {
        "vmr_hdrlen": {"address": "0xbfc3", "bytes": 2, "section": ".bss"},
        "vmr_poff": {"address": "0xbfc5", "bytes": 2, "section": ".bss"},
    }, "diagnostic latch-cell contract drift")
    rollback = diagnostic.get("link44_rollback", {})
    assert_binding(rollback, BASE / "lisp65-c2-substitution-linked.prg",
                   "Link-44 rollback product")
    require(rollback.get("status") == "untouched", "Link-44 rollback status drift")

    replay = load_json(WPLTO_RECEIPT, "WPLTO pure replay receipt")
    require(replay.get("status") ==
            "passed-vm-run-dir-latch-WPLTO-pure-replay-no-hardware",
            "WPLTO latch replay is not green")
    replay_accounting = replay.get("execution_accounting", {})
    require(replay_accounting.get("hardware_runs") == 0
            and replay_accounting.get("class_b_cycles_consumed") == 0,
            "WPLTO replay already consumed hardware")

    internal_row = diagnostic.get("internal_structural_receipt", {})
    internal_path = ROOT / str(internal_row.get("path", ""))
    assert_binding(internal_row, internal_path, "internal structural receipt")
    internal = load_json(internal_path, "internal structural receipt")
    require(internal.get("status") ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run",
            "internal diagnostic structure is not green")
    for label in ("product", "elf", "map"):
        assert_binding(internal.get("product_identity", {}).get(label),
                       paths[label], f"internal diagnostic {label}")

    structural = load_json(LINK / "product-substitution-link.json",
                           "diagnostic structural report")
    require(structural.get("status") == "passed"
            and structural.get("product_closure_link_count") == 1
            and structural.get("product_sha256") == sha(paths["product"]),
            "diagnostic structural report drift")
    base = load_json(BASE_RECEIPT, "Link-44 baseline receipt")
    require(base.get("status", "").startswith("passed-")
            and base.get("product_identity", {}).get("product", {}).get("sha256")
                == sha(BASE / "lisp65-c2-substitution-linked.prg"),
            "Link-44 rollback authority drift")
    require(sha(paths["c2d"]) == sha(BASE /
            "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin"),
            "diagnostic C2D differs from Link 44")
    require(sha(paths["bank2_static"]) == sha(BASE /
            "fresh-c2-lite-prelink-gates/v6-semantics/bank2-static-code.bin"),
            "diagnostic Bank-2 static plane differs from Link 44")

    HW.verify_c2d_product_identity(paths)
    generated = read_bytes(LINK / "c2-kernal-window.generated.h",
                           "generated window identity").decode("ascii")
    expected = re.search(r'C2_KERNAL_WINDOW_SHA256 "([0-9a-f]{64})"', generated)
    require(expected is not None and expected.group(1) == sha(paths["window"]),
            "diagnostic window generated binding drift")
    publish = load_json(LINK / "kernal-window-publish-last.json",
                        "window publish-last report")
    require(publish.get("status") == "passed", "window publish-last gate is not green")
    identity = publish.get("single_product_link_window", {})
    require(identity.get("sha256") == sha(paths["window"])
            and identity.get("crc16") == f"0x{HW.crc16(read_bytes(paths['window'], 'window')):04x}",
            "diagnostic window identity drift")
    product = read_bytes(paths["product"], "diagnostic product")
    for operand in publish.get("binding_operands", []):
        offset, value = operand.get("file_offset"), operand.get("published_value")
        require(isinstance(offset, int) and isinstance(value, int)
                and 0 <= offset < len(product) and product[offset] == value,
                "diagnostic window publication operand drift")
    return paths


def extract_section(elf: Path, section: str, destination: Path) -> None:
    scratch_input = destination.with_suffix(".elf.copy")
    scratch_output = destination.with_suffix(".elf.discard")
    shutil.copyfile(elf, scratch_input)
    try:
        subprocess.run([
            str(HW.OBJCOPY), "--dump-section", f"{section}={destination}",
            str(scratch_input), str(scratch_output),
        ], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", b"") or str(exc).encode()
        raise DiagnosticError(f"section extraction failed: {detail.decode(errors='replace')}") from exc
    finally:
        scratch_input.unlink(missing_ok=True)
        scratch_output.unlink(missing_ok=True)


def build_stage(paths: dict[str, Path], out: Path) -> tuple[Path, dict[str, Any]]:
    symbols = HW.symbols(paths["elf"], bank3_bootstrap=True)
    first_start = symbols["__lisp65_boot_bank3_stage_start"]
    first_end = symbols["__lisp65_boot_bank3_stage_end"]
    first_entry = symbols["vm_bank3_boot_stage_entry"]
    second_start = symbols["__lisp65_workbench_overlay_start"]
    second_end = symbols["__lisp65_workbench_overlay_end"]
    second_entry = symbols["vm_workbench_boot_overlay_entry"]
    require(0 < first_start <= first_entry < first_end <= 0x10000,
            "Bank-3 bootstrap geometry is invalid")
    require(0 < second_start <= second_entry < second_end <= 0x10000,
            "workbench bootstrap geometry is invalid")

    first_payload = out / "boot-bank3-stage.raw.bin"
    second_payload = out / "boot-overlay.raw.bin"
    extract_section(paths["elf"], ".lisp65_boot_bank3_stage", first_payload)
    extract_section(paths["elf"], ".lisp65_workbench_overlay", second_payload)
    first_data = read_bytes(first_payload, "Bank-3 bootstrap payload")
    second_data = read_bytes(second_payload, "workbench bootstrap payload")
    require(len(first_data) == first_end - first_start,
            "Bank-3 bootstrap payload length drift")
    require(len(second_data) == second_end - second_start,
            "workbench bootstrap payload length drift")

    contract_sha = sha(paths["contract"])
    build_id = int(contract_sha[:8], 16)
    header = read_bytes(paths["stage_header"], "stage header").decode("ascii")
    expected_build = re.search(
        r"LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x([0-9a-fA-F]+)UL", header)
    expected_bank = re.search(
        r"LISP65_BOOT_OVERLAY_STAGE_BANK 0x([0-9a-fA-F]+)u", header)
    expected_off = re.search(
        r"LISP65_BOOT_OVERLAY_STAGE_OFF 0x([0-9a-fA-F]+)u", header)
    require(expected_build is not None and expected_bank is not None
            and expected_off is not None, "stage header lacks its bindings")
    require(int(expected_build.group(1), 16) == build_id,
            "stage build ID differs from diagnostic profile")
    stage_address = (int(expected_bank.group(1), 16) << 16) | int(expected_off.group(1), 16)
    require(stage_address == HW.BOOT_OVERLAY_STAGE, "boot stage address drift")

    first_descriptor = HW.boot_overlay_descriptor(
        build_id=build_id, start=first_start, entry=first_entry, payload=first_data)
    second_descriptor = HW.boot_overlay_descriptor(
        build_id=build_id, start=second_start, entry=second_entry, payload=second_data)
    stage_offset = int(expected_off.group(1), 16)
    second_offset = ((stage_offset + HW.DESCRIPTOR_BYTES + len(first_data) + 0xFF)
                     & ~0xFF) - stage_offset
    first_record = first_descriptor + first_data
    require(second_offset >= len(first_record), "boot-stage successor offset underflow")
    stage_data = (first_record + bytes(second_offset - len(first_record))
                  + second_descriptor + second_data)
    stage = out / "boot-overlay.stage.bin"
    stage.write_bytes(stage_data)
    chain = {
        "format": "L65O-v1-fixed-two-record-bootstrap",
        "first_record": {
            "role": "bank3-boot-stager", "record_offset": 0,
            "vma": f"0x{first_start:04x}", "entry": f"0x{first_entry:04x}",
            "payload_bytes": len(first_data),
            "payload_crc16": f"0x{HW.crc16(first_data):04x}",
        },
        "second_record": {
            "role": "workbench-overlay", "record_offset": second_offset,
            "vma": f"0x{second_start:04x}", "entry": f"0x{second_entry:04x}",
            "payload_bytes": len(second_data),
            "payload_crc16": f"0x{HW.crc16(second_data):04x}",
        },
        "padding_bytes": second_offset - len(first_record),
        "total_bytes": len(stage_data),
        "profile_build_id": f"0x{build_id:08x}",
    }
    return stage, chain


def prepare() -> None:
    require(not OUT.exists(), f"diagnostic hardware output must be fresh: {OUT}")
    require(not HARDWARE_RECEIPT.exists(), "Class-B cycle 1 hardware receipt already exists")
    paths = verify_sources()
    OUT.mkdir(parents=True)
    stage, chain = build_stage(paths, OUT)
    preloads = [
        binding(paths["c2d"], HW.C2D_STAGE),
        binding(stage, HW.BOOT_OVERLAY_STAGE),
        binding(paths["session_family"], HW.SESSION_FAMILY_STAGE),
        binding(paths["shelf"], HW.SHELF_STAGE),
        binding(paths["boot_family"], HW.BOOT_FAMILY_STAGE),
        binding(paths["window"], HW.KERNAL_WINDOW_STAGE),
    ]
    deployment = {
        "format": "lisp65-c2-lite-v6-vm-run-dir-latch-hardware-deployment-v1",
        "status": "ready-nonpromotable-class-b-cycle1-hardware-not-run",
        "promotable": False,
        "claim_limit": (
            "One Class-B diagnostic hardware cycle only. No promotion, latency, "
            "acceptance or product-semantic fix claim may be derived from it."),
        "delegation": {"class": "B", "cycle": "1-of-3"},
        "product": binding(paths["product"], 0x00002001),
        "preloads": preloads,
        "boot_chain": chain,
        "diagnostic_latch": {
            "cells": {
                "vmr_hdrlen": {"address": "0x0000bfc3", "bytes": 2,
                               "meaning": "signed raw vm_run_dir directory ordinal"},
                "vmr_poff": {"address": "0x0000bfc5", "bytes": 2,
                             "meaning": "little-endian 0x8201 = Session family, site 1, valid"},
            },
            "capture_range": "0x0000bfc3:0x0000bfc7",
            "expected_context": "0x8201",
        },
        "input_contract": {
            "exact_form_count": 1,
            "forms": [TEST_FORM],
            "additional_forms_forbidden": True,
        },
        "authority": {
            "diagnostic_link_receipt": binding(DIAG_RECEIPT),
            "wplto_pure_replay_receipt": binding(WPLTO_RECEIPT),
            "link44_rollback_receipt": binding(BASE_RECEIPT),
            "diagnostic_elf": binding(paths["elf"]),
            "diagnostic_map": binding(paths["map"]),
        },
        "span_checks": {
            "c2d_before_boot_stage":
                HW.C2D_STAGE + paths["c2d"].stat().st_size <= HW.BOOT_OVERLAY_STAGE,
            "session_before_shelf":
                HW.SESSION_FAMILY_STAGE + paths["session_family"].stat().st_size <= HW.SHELF_STAGE,
            "shelf_before_boot":
                HW.SHELF_STAGE + paths["shelf"].stat().st_size <= HW.BOOT_FAMILY_STAGE,
            "window_ends_at_attic_limit":
                HW.KERNAL_WINDOW_STAGE + paths["window"].stat().st_size == 0x08800000,
        },
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0, "promotable_product_links": 0,
            "hardware_runs": 0, "class_b_cycles_consumed": 0,
        },
    }
    require(all(deployment["span_checks"].values()), "diagnostic deployment spans overlap")
    deployment_path = OUT / "deployment.json"
    deployment_path.write_text(json.dumps(deployment, indent=2, sort_keys=True) + "\n")
    for path in (OUT / "boot-bank3-stage.raw.bin", OUT / "boot-overlay.raw.bin",
                 stage, deployment_path):
        chmod_read_only(path)
    verify()
    print("c2-link44-vm-run-dir-latch-hw: PREPARE PASS class-B=cycle1/3 hardware=not-run")


def verify() -> None:
    paths = verify_sources()
    deployment_path = OUT / "deployment.json"
    deployment = load_json(deployment_path, "diagnostic deployment")
    require(deployment.get("status") ==
            "ready-nonpromotable-class-b-cycle1-hardware-not-run"
            and deployment.get("promotable") is False,
            "diagnostic deployment boundary drift")
    require(deployment.get("input_contract") == {
        "exact_form_count": 1, "forms": [TEST_FORM],
        "additional_forms_forbidden": True,
    }, "diagnostic input contract drift")
    assert_binding(deployment.get("product"), paths["product"], "deployed product")
    expected_preloads = [
        (paths["c2d"], HW.C2D_STAGE),
        (OUT / "boot-overlay.stage.bin", HW.BOOT_OVERLAY_STAGE),
        (paths["session_family"], HW.SESSION_FAMILY_STAGE),
        (paths["shelf"], HW.SHELF_STAGE),
        (paths["boot_family"], HW.BOOT_FAMILY_STAGE),
        (paths["window"], HW.KERNAL_WINDOW_STAGE),
    ]
    preloads = deployment.get("preloads", [])
    require(len(preloads) == len(expected_preloads), "diagnostic preload count drift")
    for row, (path, address) in zip(preloads, expected_preloads):
        assert_binding(row, path, f"preload {path.name}")
        require(row.get("address") == f"0x{address:08x}",
                f"preload address drift: {path.name}")
    for key, path in (
        ("diagnostic_link_receipt", DIAG_RECEIPT),
        ("wplto_pure_replay_receipt", WPLTO_RECEIPT),
        ("link44_rollback_receipt", BASE_RECEIPT),
        ("diagnostic_elf", paths["elf"]),
        ("diagnostic_map", paths["map"]),
    ):
        assert_binding(deployment.get("authority", {}).get(key), path, key)
    require(all(deployment.get("span_checks", {}).values()), "deployment span gate drift")
    require(deployment.get("execution_accounting", {}).get("hardware_runs") == 0
            and deployment.get("execution_accounting", {}).get(
                "class_b_cycles_consumed") == 0,
            "prepared deployment already claims a hardware cycle")
    require(not HARDWARE_RECEIPT.exists(), "Class-B cycle 1 is already consumed")
    print("c2-link44-vm-run-dir-latch-hw: VERIFY PASS hardware=not-run")


def static_entry_name(ordinal: int) -> dict[str, Any] | None:
    authority = load_json(AUTHORITY, "static product artifact authority")
    cursor = 0
    for manifest_row in authority.get("manifests", []):
        path = ROOT / str(manifest_row.get("path", ""))
        if (manifest_row.get("sha256") != sha(path)
                or manifest_row.get("bytes") != path.stat().st_size):
            raise DiagnosticError(f"static manifest authority drift: {path}")
        manifest = load_json(path, "static image manifest")
        entries = manifest.get("entries", [])
        if cursor <= ordinal < cursor + len(entries):
            entry = entries[ordinal - cursor]
            return {
                "image": manifest.get("name"),
                "local_ordinal": ordinal - cursor,
                "name": entry.get("name"),
                "kind": entry.get("kind"),
            }
        cursor += len(entries)
    require(cursor == authority.get("entries") == 588,
            "static entry-name authority count drift")
    return None


def evaluate() -> None:
    verify()
    latch_path = OUT / "latch-bfc3-bfc6.bin"
    latch = read_bytes(latch_path, "hardware latch capture")
    require(len(latch) == 4, "hardware latch capture must be four bytes")
    raw_ordinal, context = struct.unpack("<HH", latch)
    signed_ordinal = raw_ordinal if raw_ordinal < 0x8000 else raw_ordinal - 0x10000
    hit = context == LATCH_CONTEXT
    bcode = ((0x6000 + raw_ordinal) << 1) & 0xFFFF if raw_ordinal < 4096 else None
    normalized = None
    handle_class = "outside-12-bit-bcode-domain"
    static_name = None
    if raw_ordinal < 2048:
        normalized = raw_ordinal
        handle_class = "persistent-low-handle"
        static_name = static_entry_name(raw_ordinal) if raw_ordinal < 588 else None
    elif raw_ordinal < 4096:
        normalized = raw_ordinal - 2048
        handle_class = "transient-high-handle"

    screen = OUT / "after-expression.txt"
    screenshot = OUT / "after-expression.png"
    ansi = OUT / "after-expression.ansi.txt"
    for path, label in ((screen, "screen text"), (screenshot, "screenshot"),
                        (ansi, "ANSI screen capture")):
        read_bytes(path, label)
    deployment_path = OUT / "deployment.json"
    lookup = ({
        "status": "captured-at-instrumented-site",
        "raw_directory_handle": raw_ordinal,
        "normalized_directory_ordinal": normalized,
        "handle_class": handle_class,
        "bcode_obj": f"0x{bcode:04x}" if bcode is not None else None,
        "static_entry": static_name,
    } if hit else {
        "status": "not-a-latch-unmarked-scratch-provenance-only",
        "raw_scratch_word": raw_ordinal,
        "interpretation_forbidden": True,
    })
    receipt = {
        "format": "lisp65-c2-lite-v6-vm-run-dir-latch-hardware-cycle1-v1",
        "status": ("captured-vm-run-dir-failing-lookup"
                   if hit else "site1-silent-next-site-review-required"),
        "recorded_on": "2026-07-22",
        "promotable": False,
        "delegation": {"class": "B", "cycle": "1-of-3", "consumed": 1},
        "diagnostic_identity": binding(source_paths()["product"]),
        "deployment": binding(deployment_path),
        "input": {"forms_submitted": 1, "form": TEST_FORM,
                  "additional_forms_submitted": 0},
        "capture": {
            "raw": binding(latch_path),
            "screen": binding(screen),
            "screenshot": binding(screenshot),
            "ansi": binding(ansi),
            "bytes_hex": latch.hex(),
            "vmr_hdrlen_raw_u16": raw_ordinal,
            "vmr_hdrlen_signed": signed_ordinal,
            "vmr_poff_context": f"0x{context:04x}",
            "expected_context": "0x8201",
            "site_hit": hit,
        },
        "lookup": lookup,
        "budgets": {
            "line1_product_first_reds": "2/3 unchanged",
            "completed_latency_measurements": "0/2 unchanged",
            "class_b_diagnostic_cycles": "1/3 consumed",
        },
        "claim_boundary": (
            "This nonpromotable cycle identifies whether vm_run_dir rejected the "
            "captured raw handle. It does not prove a product fix, latency, acceptance "
            "or promotion."),
        "next_action": ("Class-C interpretation of the captured lookup"
                        if hit else "Class-B site 2 only after the sequential disposition"),
    }
    HARDWARE_RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    for path in (latch_path, screen, screenshot, ansi, HARDWARE_RECEIPT):
        chmod_read_only(path)
    print("c2-link44-vm-run-dir-latch-hw: HARDWARE CAPTURED "
          f"site_hit={str(hit).lower()} raw={raw_ordinal} signed={signed_ordinal} "
          f"context=0x{context:04x} class_b=1/3")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "verify", "evaluate"))
    args = parser.parse_args()
    try:
        if args.mode == "prepare":
            prepare()
        elif args.mode == "verify":
            verify()
        else:
            evaluate()
    except DiagnosticError as exc:
        print(f"c2-link44-vm-run-dir-latch-hw: FAIL {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
