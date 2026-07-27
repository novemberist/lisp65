#!/usr/bin/env python3
"""Bind the Link-40 hardware First Red caused by a family-blind slot test."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / (
    "build/c2.2/substitution/product-link-40-c2-lite-v6-real-abi-e000")
HW = ROOT / (
    "build/c2.2/hardware-presmoke-link40-c2d-canonical-header-audited")
CAPTURE = HW / "line1-first-red"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.2-product-link40-c2-lite-v6-family-slot-collision-"
    "hardware-first-red.json")


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }


def record(manifest: dict[str, object], slot: int) -> dict[str, object]:
    rows = manifest.get("slices")
    require(isinstance(rows, list), "overlay manifest has no slice list")
    matches = [row for row in rows
               if isinstance(row, dict) and row.get("id") == slot]
    require(len(matches) == 1, f"slot {slot} is not unique")
    return matches[0]


def main() -> None:
    require(not RECEIPT.exists(), "First-Red receipt already exists")

    product = CANDIDATE / "lisp65-c2-substitution-linked.prg"
    deployment = HW / "deployment.json"
    boot_path = CANDIDATE / "runtime-overlays-boot-final.json"
    session_path = CANDIDATE / "runtime-overlays-session-final.json"
    session_bin_path = CANDIDATE / "runtime-overlays-session-final.bin"
    source_path = CANDIDATE / "generated-product-sources/vm_runtime_overlay.c"
    slots_path = ROOT / "src/c2_product_runtime.h"
    linker_path = ROOT / "tools/host-lisp/c2_product_substitution_link.py"

    require(sha_bytes(product.read_bytes()) ==
            "a683a2e9b3be92b41bcc5ef0013f0e1c7ef379a63c26f4fe1883a21508bf44a0",
            "Link-40 product identity drift")
    require(sha_bytes(deployment.read_bytes()) ==
            "f1a3a5e5c0b7593c3d7883f9880c6e9a9b5f0445a5dd0b4900b79b74c76712dd",
            "audited deployment identity drift")

    low = (CAPTURE / "low-0000-0100.bin").read_bytes()
    bank0 = (CAPTURE / "bank0-c000-c100.bin").read_bytes()
    bank3 = (CAPTURE / "bank3-live.bin").read_bytes()
    session_bin = session_bin_path.read_bytes()
    require(len(low) == 0x100 and len(bank0) == 0x100,
            "hardware state capture length drift")
    require(bank3[:len(session_bin)] == session_bin,
            "live Bank 3 differs from the bound Session family")

    boot = json.loads(boot_path.read_text(encoding="utf-8"))
    session = json.loads(session_path.read_text(encoding="utf-8"))
    boot9 = record(boot, 9)
    session9 = record(session, 9)
    require(boot9.get("name") == "resident-island-installer",
            "Boot slot 9 is not the Island installer")
    require(session9.get("name") == "c2-decode-09",
            "Session slot 9 is not c2-decode-09")
    require(session9.get("flags") == 6 and session9.get("entry_offset") == 0
            and session9.get("file_size") == 1580,
            "Session slot-9 record geometry drift")

    runtime = bank0[0x84:0x84 + 48]
    require(runtime[:4] == (70897).to_bytes(4, "little"),
            "live C2 shelf-byte identity drift")
    require(runtime[4:8] == bytes.fromhex("f302633d"),
            "live canonical shelf CRC did not pass")
    require(runtime[8:10] == (33840).to_bytes(2, "little"),
            "live C2D-v6 length drift")
    require(runtime[10:12] == (1).to_bytes(2, "little"),
            "live C2 generation drift")
    require(runtime[42] == 9 and runtime[43] == 0 and runtime[44] == 0,
            "decoder did not stop cleanly at the phase-09 boundary")

    require(low[0x38] == 0x25, "unexpected product-facing error")
    require(low[0x78] == 0x0b, "runtime overlay fault is not ERR_ENTRY")
    require(low[0x79] == 2 and low[0x7a] == 2,
            "fault did not occur in the ready Session family")
    require(low[0x74] == 0, "append transaction was unexpectedly active")
    require(low[0x8c] == 0, "C2 was published despite the First Red")

    source = source_path.read_text(encoding="utf-8")
    require(
        "if (context->slot == LISP65_RUNTIME_ISLAND_INSTALL_SLOT) {" in source
        and "rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_BOOT" in source,
        "family-blind installer special case not found")
    slots = slots_path.read_text(encoding="utf-8")
    require("#define LISP65_C2_PHASE_09_SLOT 9u" in slots,
            "v6 Session phase-09 slot authority drift")
    linker = linker_path.read_text(encoding="utf-8")
    require("BOOT_ISLAND_SLOT = BOOT_BANK3_STAGE_SLOT + 1" in linker,
            "Bank-3 staging did not move the Boot installer slot")
    require("LISP65_RUNTIME_ISLAND_INSTALL_SLOT={BOOT_ISLAND_SLOT}" in linker,
            "product definition no longer consumes the Boot installer slot")

    receipt = {
        "format": "lisp65-c2-lite-v6-family-slot-collision-first-red-v1",
        "recorded_on": "2026-07-22",
        "status": "first-red-session-slot-9-rejected-by-family-blind-boot-installer-special-case",
        "claim_boundary": {
            "hardware": "failed-before-c2-ready-and-before-latency-measurement",
            "latency_attempts_consumed": 0,
            "promotion": "blocked",
            "product_changes_authorized_by_this_receipt": 0,
        },
        "candidate": {
            "product": bind(product),
            "deployment": bind(deployment),
        },
        "hardware_witness": {
            "lisp65_error": "0x25",
            "runtime_overlay_fault": {
                "value": "0x0b",
                "name": "VM_RUNTIME_OVERLAY_ERR_ENTRY",
            },
            "runtime_family": {"value": 2, "name": "session"},
            "resident_island_state": {"value": 2, "name": "ready"},
            "append_transaction_active": False,
            "c2_ready": 0,
            "decoder": {
                "phase": 9,
                "finished": 0,
                "semantic_error": 0,
                "resolution_cursor": 2264,
                "resolution_count": 2264,
            },
            "canonical_header_fields_passed": {
                "product_build_id": "0x69496476",
                "shelf_catalog_crc32": "0x3d6302f3",
            },
            "bank3_session_prefix_byteidentical": True,
            "bank3_session_bytes": len(session_bin),
        },
        "collision": {
            "numeric_slot": 9,
            "boot_meaning": {
                "name": boot9["name"],
                "file_size": boot9["file_size"],
                "entry_offset": boot9["entry_offset"],
            },
            "session_meaning": {
                "name": session9["name"],
                "file_size": session9["file_size"],
                "entry_offset": session9["entry_offset"],
                "flags": session9["flags"],
            },
            "fault_mechanism": (
                "vm_runtime_overlay_record_verifier tests only the numeric "
                "slot against LISP65_RUNTIME_ISLAND_INSTALL_SLOT, then "
                "rejects the same numeric slot whenever the active family is "
                "not Boot. Slot identity is family-qualified everywhere else."
            ),
            "required_design_question": (
                "Qualify the installer-only record rule by the Boot family, "
                "or otherwise make family part of the special-case identity; "
                "do not renumber or patch before Class-C review."
            ),
        },
        "authority": {
            "boot_manifest": bind(boot_path),
            "session_manifest": bind(session_path),
            "session_image": bind(session_bin_path),
            "product_verifier_source": bind(source_path),
            "session_slot_source": bind(slots_path),
            "link_driver_source": bind(linker_path),
        },
        "captures": {
            path.name: bind(path)
            for path in sorted(CAPTURE.iterdir()) if path.is_file()
        },
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    print(RECEIPT.relative_to(ROOT))
    print(sha_bytes(RECEIPT.read_bytes()))
    print(receipt["status"])


if __name__ == "__main__":
    main()
