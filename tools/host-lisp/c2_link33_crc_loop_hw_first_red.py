#!/usr/bin/env python3
"""Bind the receipt-less Link-33 boot hang to the emitted CRC loop."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LINK = ROOT / "build/c2.2/substitution/product-link-33-handoff-reanchor-final"
DEPLOY = ROOT / "build/c2.2/hardware-presmoke-link33-handoff-reanchor"
FIRST_RED = DEPLOY / "first-red"
STRUCTURAL = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
              "c2.2-product-link33-handoff-reanchor-structural-receipt.json")
OUTPUT = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
          "c2.2-product-link33-crc-loop-hardware-first-red-diagnosis.json")
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"

PRODUCT_SHA = "5f44b65a1a67530a9c3c8b687d7be597422978ae749f56101f42bdcebaf50044"
CATALOG_SHA = "897f3eba94474906304cf7146667e1df94e4832a331620f5bcde48cba7a3d52a"
WINDOW_SHA = "2081c7e22679e2b44c1426b1a1fdc4d53661d0f52c46ab4cf41d642a3973fdeb"


class DiagnosisError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DiagnosisError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def run(*args: str) -> str:
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    require(not result.stderr, f"unexpected diagnostic: {result.stderr.strip()}")
    return result.stdout


def c2_state(path: Path) -> dict[str, int]:
    data = path.read_bytes()
    require(len(data) == 16, f"bad C2 state capture: {path}")
    return {
        "event_code": data[0],
        "event_modifiers": data[1],
        "event_ready": data[2],
        "frame_count": data[3] | data[4] << 8,
        "nmi_count": data[5],
        "sourceless_irq_count": data[6],
        "map_generation": data[7],
        "ownership_state": data[8],
        "unowned_vic_flags": data[9],
    }


def build() -> dict[str, Any]:
    structural = load(STRUCTURAL)
    deployment = load(DEPLOY / "deployment.json")
    product = LINK / "lisp65-c2-substitution-linked.prg"
    elf = LINK / "lisp65-c2-substitution-linked.prg.elf"
    lto = LINK / "lisp65-c2-substitution-linked.prg.lto.o"
    boot_manifest_path = LINK / "runtime-overlays-boot-final.json"
    boot_manifest = load(boot_manifest_path)

    require(structural.get("status") ==
            "passed-new-product-identity-hardware-not-run",
            "Link-33 structural status drift")
    require(structural.get("link_number") == 33 and
            structural.get("inheritance") ==
            "none; every structural and capacity gate ran freshly",
            "Link-33 structural provenance drift")
    require(sha(product) == PRODUCT_SHA == deployment.get("product", {}).get("sha256"),
            "Link-33 product/deployment identity mismatch")
    require(deployment.get("status") == "ready-receipt-less" and
            deployment.get("new_product_links") == 0,
            "hardware deployment is not receipt-less")

    slices = boot_manifest.get("slices")
    require(isinstance(slices, list) and slices, "missing boot slices")
    catalog = slices[0]
    require(catalog.get("id") == 0 and catalog.get("name") == "catalog-verifier"
            and catalog.get("file_offset") == 512
            and catalog.get("file_size") == 1156
            and catalog.get("vma") == 0xC356
            and catalog.get("sha256") == CATALOG_SHA,
            "boot catalog-verifier binding drift")

    captured_catalog = FIRST_RED / "rtov-catalog-c356-c7da.bin"
    captured_window = FIRST_RED / "e000-window.bin"
    require(sha(captured_catalog) == CATALOG_SHA,
            "hardware catalog-verifier bytes differ from the bound payload")
    require(sha(captured_window) == WINDOW_SHA ==
            sha(LINK / "c2-product-kernal-window.bin"),
            "hardware $E000 bytes differ from the Link-33 window")

    early = c2_state(FIRST_RED / "c2-window-state-ff80-ff90.bin")
    later = c2_state(FIRST_RED / "c2-window-state-ff80-ff90-later.bin")
    for row in (early, later):
        require(row["map_generation"] == 1 and row["ownership_state"] == 4
                and row["sourceless_irq_count"] == 0
                and row["unowned_vic_flags"] == 0,
                f"owned-window state drift: {row}")
    require(later["frame_count"] > early["frame_count"],
            "frame source did not advance during the boot hang")

    zp = (FIRST_RED / "zp-0000-0100.bin").read_bytes()
    require(len(zp) == 256, "bad zero-page capture")
    soft_sp = int.from_bytes(zp[2:4], "little")
    runtime = {
        "soft_stack_pointer": soft_sp,
        "family": zp[0x77],
        "island_state": zp[0x78],
        "loaded_length": int.from_bytes(zp[0x79:0x7B], "little"),
        "busy": zp[0x7B],
        "fault": zp[0x7C],
    }
    require(runtime == {
        "soft_stack_pointer": 0xCF8D,
        "family": 1,
        "island_state": 1,
        "loaded_length": 1156,
        "busy": 1,
        "fault": 0,
    }, f"unexpected runtime-overlay halt state: {runtime}")

    dma = (FIRST_RED / "rtov-edma-job-later.bin").read_bytes()
    require(len(dma) == 20 and dma[2] == 0x82
            and int.from_bytes(dma[9:11], "little") == 1156
            and int.from_bytes(dma[11:13], "little") == 512
            and int.from_bytes(dma[14:16], "little") == 0xC356,
            "DMA descriptor advanced past or differs from the verifier load")

    linked_disassembly = run(
        str(OBJDUMP), "-d", "--start-address=0xa9bd", "--stop-address=0xa9e6",
        str(elf))
    require(re.search(r"a9bd:.*sta\s+\$7d", linked_disassembly)
            and re.search(r"a9bf:.*stx\s+\$7e", linked_disassembly)
            and re.search(r"a9cd:.*lda\s+\$7e", linked_disassembly)
            and re.search(r"a9d1:.*dew\s+\$16", linked_disassembly)
            and re.search(r"a9e0:.*lda\s+\$7d", linked_disassembly),
            "linked CRC-loop signature drift")

    relocatable = run(
        str(OBJDUMP), "-dr", "--section=.text.rtov_crc_mem", str(lto))
    require("00000001:  R_MOS_ADDR8\t.zp.noinit" in relocatable
            and "00000003:  R_MOS_ADDR8\t.zp.noinit+0x1" in relocatable
            and "00000015:  R_MOS_ADDR8\t__rc20" in relocatable,
            "LTO-object CRC-loop relocation signature drift")

    link32 = (ROOT / "build/c2.2/substitution/"
              "product-link-32-preinstall-island-guard/"
              "lisp65-c2-substitution-linked.prg.elf")
    previous_disassembly = run(str(OBJDUMP), "-d", "--no-show-raw-insn",
                               str(link32))
    previous_body = previous_disassembly.split("<rtov_crc_mem>:", 1)[1].split("\n\n", 1)[0]
    require("dew" not in previous_body and previous_body.count("dec\t$") >= 2,
            "Link-32 comparison no longer carries the bytewise decrement form")

    historical_gate = ROOT / "tools/host-lisp/workbench_overlay_control_audit.py"
    gate_text = historical_gate.read_text(encoding="utf-8")
    require("resident rtov_crc_mem contains forbidden dew regression" in gate_text
            and "resident rtov_crc_mem does not decrement both length bytes" in gate_text,
            "historical CRC codegen guard drift")
    require("workbench_overlay_control_audit" not in
            json.dumps(structural, sort_keys=True),
            "Link-33 structural receipt unexpectedly claims the historical audit")

    artifacts = [
        FIRST_RED / name for name in (
            "screen.png", "screen.txt", "screen.ansi.txt",
            "screen-0800-1800.bin", "zp-0000-0100.bin",
            "zp-0000-0100-later.bin", "soft-stack-ca00-d000.bin",
            "rtov-resident-a900-c080.bin", "rtov-edma-job-later.bin",
            "rtov-catalog-c356-c7da.bin", "e000-window.bin",
            "c2-window-state-ff80-ff90.bin",
            "c2-window-state-ff80-ff90-later.bin",
        )]
    require(all(path.is_file() for path in artifacts), "missing First Red capture")

    return {
        "format": "lisp65-c2-product-link33-crc-loop-hardware-first-red-diagnosis-v1",
        "recorded_on": "2026-07-21",
        "status": "first-red-receipt-less-hardware-presmoke-stopped-at-boot",
        "claim_limit": (
            "Read-only diagnosis of a receipt-less fail-fast hardware pre-smoke. "
            "It is not promotion, acceptance, latency evidence or authorization "
            "for a source change or successor product link."),
        "scope": {
            "candidate_product_sha256": PRODUCT_SHA,
            "structural_receipt": binding(STRUCTURAL),
            "deployment": binding(DEPLOY / "deployment.json"),
            "new_product_links_after_first_red": 0,
            "product_source_changes_after_first_red": 0,
            "presmoke_rows": {
                "boot_to_repl": "first-red-no-repl",
                "definition_first_call": "not-run",
                "warm_second_call": "not-run",
                "gc_blockread": "not-run",
                "freezer_e000_identity": "not-run",
                "nested_eval": "not-run",
            },
        },
        "hardware_localization": {
            "kernal_handoff": "passed-in-this-diagnostic",
            "e000_window_identity": "byte-identical-to-Link-33-pin",
            "frame_continuity": {
                "early": early["frame_count"],
                "later": later["frame_count"],
                "advanced_frames": later["frame_count"] - early["frame_count"],
            },
            "runtime_overlay": runtime,
            "loaded_payload": {
                "name": "boot catalog-verifier",
                "vma": "0xc356",
                "bytes": 1156,
                "sha256": CATALOG_SHA,
                "hardware_matches_bound_payload": True,
            },
            "dma_descriptor": {
                "source_tenant": "0x08200000",
                "relative_offset": 512,
                "target": "0xc356",
                "bytes": 1156,
                "observation": (
                    "Still describes the verifier payload load; the verifier's "
                    "first 32-byte header read was never issued."),
            },
        },
        "root_cause": {
            "classification": "target-codegen-regression-in-resident-crc-loop",
            "function": "rtov_crc_mem",
            "source_shape": "while (length--) crc = rtov_crc_byte(crc, *p++);",
            "linked_loop": {
                "length_shadow_low": "0x7d",
                "length_shadow_high": "0x7e",
                "loop_test_reads": ["0x7e", "0x7d"],
                "decrement_instruction": "dew $16",
                "decrement_target": "__rc20/__rc21, not the tested length shadow",
                "consequence": (
                    "The initial 1156-byte payload length never reaches zero; "
                    "the pre-call CRC loops forever before catalog verification."),
            },
            "lto_object_relocation": {
                "instruction_offset": "0x14",
                "operand_relocation_offset": "0x15",
                "operand_symbol": "__rc20",
                "finding": "The wrong decrement is already present before final linking.",
            },
            "comparison": {
                "Link-32": "bytewise DEC form, no DEW",
                "Link-33": "DEW __rc20 form",
                "source_change_required_to_trigger": False,
                "whole_program_lto_layout_can_change_codegen": True,
            },
        },
        "gate_gap": {
            "historical_guard": binding(historical_gate),
            "guarded_failure": "forbidden DEW plus missing two bytewise decrements",
            "Link_33_receipt_includes_historical_guard": False,
            "finding": (
                "The exact regression class was guarded in the legacy Workbench "
                "overlay audit, but that retired-target audit was not migrated as "
                "a product-independent CRC-loop codegen gate in Link 33."),
        },
        "evidence": {
            "product": binding(product),
            "elf": binding(elf),
            "lto_object": binding(lto),
            "boot_manifest": binding(boot_manifest_path),
            "hardware_captures": [binding(path) for path in artifacts],
        },
        "next_decision": {
            "required_before_any_successor_link": [
                "restore a target-stable bytewise 16-bit CRC length decrement",
                "extract/migrate the existing DEW-and-two-DEC guard into every C2 product link",
                "pin mutations for DEW and one-byte-only decrement",
                "run a capacity/placement probe because Bank-0 text has only 32 bytes headroom",
            ],
            "automatic_fix_or_link_authorized": False,
            "device_recovery": "disk reboot/power-cycle required",
        },
    }


def main() -> int:
    try:
        value = build()
    except (DiagnosisError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"c2-link33-crc-loop-first-red: FAIL {exc}")
        return 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                      encoding="ascii")
    print("c2-link33-crc-loop-first-red: PASS "
          f"product={PRODUCT_SHA} root=rtov_crc_mem/dew-$16")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
