#!/usr/bin/env python3
"""Attribute the sealed v1.7 `(repl)` VM_BADOPCODE without rebuilding it."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402

READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
ELF = ROOT / ("build/c2.3/v1.6-clean-product-operand-root-fix/wplto/"
              "lisp65-c2-substitution-linked.prg.elf")
LIBROOT = ROOT / ("build/c2.3/v1.6-clean-product-operand-root-media/"
                  "library-inputs")
COMFORT_DISASM = LIBROOT / "repl-comfort.disasm.txt"
COMFORT_MANIFEST = LIBROOT / "repl-comfort.manifest.json"
COMFORT_SOURCE = ROOT / "lib/repl-comfort.lisp"
PRODUCT_PROFILE = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
PROFILE_CONTRACT = ROOT / "config/v11-surface-delivery-parity.json"
HOST_VM = ROOT / "tools/host-lisp/bytecode_p0.py"
VM_SOURCE = ROOT / "src/vm.c"
VM_HEADER = ROOT / "src/vm.h"
FIX_RECEIPT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                      "c2.3-v1.6-clean-product-operand-root-fix-receipt.json")
MEDIA_RECEIPT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                        "c2.3-v1.6-clean-product-operand-root-media-receipt.json")
OUT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
              "c2.3-v1.7-comfort-phase1a-attribution-receipt.json")

CALLPRIM_ID = 12


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def source_function(source: str, name: str) -> str:
    match = re.search(
        rf"^(?P<indent>[ \t]*)def {re.escape(name)}\([^\n]*\).*?"
        rf"(?=^(?P=indent)(?:def |class )|\Z)",
        source, re.MULTILINE | re.DOTALL)
    require(match is not None, f"source function absent: {name}")
    return match.group(0)


def section_slice(truth: ElfTruth, section_name: str,
                  address: int, size: int) -> bytes:
    section = truth.section(section_name)
    require(section.address <= address
            and address + size <= section.address + section.bytes,
            f"range 0x{address:04x}+{size} is outside {section_name}")
    start = address - section.address
    return truth.section_bytes(section_name)[start:start + size]


def classify(*, emitted: bool, delivered: bool, tombstone: bool,
             host_accepts: bool) -> str:
    require(emitted, "Comfort CALLPRIM 12 consumer disappeared")
    require(not delivered, "product profile now delivers screen-write-string")
    require(tombstone, "final CALLPRIM 12 no longer reaches VM_BADOPCODE")
    require(host_accepts, "host oracle no longer explains the false host green")
    return "PROFILE-CAPABILITY CLOSURE: BOUND DIALECT PRIMITIVE NOT DELIVERED"


def mutation_selftest() -> dict[str, str]:
    ordinary = dict(emitted=True, delivered=False, tombstone=True,
                    host_accepts=True)
    require(classify(**ordinary).startswith("PROFILE-CAPABILITY"),
            "ordinary classification drift")
    mutations = {
        "remove-library-consumer": {**ordinary, "emitted": False},
        "deliver-required-capability": {**ordinary, "delivered": True},
        "route-callprim-to-implementation": {**ordinary, "tombstone": False},
        "make-host-oracle-profile-aware": {**ordinary, "host_accepts": False},
    }
    rejected: dict[str, str] = {}
    for name, mutant in mutations.items():
        try:
            classify(**mutant)
        except RuntimeError as error:
            rejected[name] = str(error)
        else:
            raise RuntimeError(f"attribution mutation survived: {name}")
    require(len(rejected) == len(mutations), "mutation accounting drift")
    return rejected


def derive() -> dict[str, Any]:
    truth = ElfTruth.read(
        ELF, llvm_readobj=READOBJ, include_section_data=True)
    table_start = truth.symbol(
        "__lisp65_c2_profile_rodata_callprim_start")
    table_end = truth.symbol("__lisp65_c2_profile_rodata_callprim_end")
    require(table_start.section == table_end.section,
            "CALLPRIM table markers split across sections")
    table = section_slice(
        truth, table_start.section, table_start.value,
        table_end.value - table_start.value)
    require(len(table) >= (CALLPRIM_ID + 1) * 2,
            "CALLPRIM table does not cover primitive 12")
    targets = [int.from_bytes(table[i:i + 2], "little")
               for i in range(0, len(table), 2)]
    target = targets[CALLPRIM_ID]
    require(targets[1] == targets[2] == target,
            "CALLPRIM 12 does not share the product tombstone sink")

    sink = section_slice(truth, ".text", target, 5)
    require(sink[:3] == bytes((0xA2, 0x02, 0x4C)),
            "CALLPRIM 12 sink no longer loads VM_BADOPCODE then jumps")
    status_target = int.from_bytes(sink[3:5], "little")
    status_store = section_slice(truth, ".text", status_target, 2)
    vm_status = truth.symbol("vm_status")
    require(status_store == bytes((0x86, vm_status.value & 0xFF)),
            "CALLPRIM tombstone no longer stores X into vm_status")

    vm_header = VM_HEADER.read_text()
    require("VM_OK=0, VM_HALT, VM_BADOPCODE" in vm_header,
            "VM_BADOPCODE enum ordinal drift")
    vm_source = VM_SOURCE.read_text()
    require("#ifdef LISP65_SCREEN_WRITE_STRING\n    case 12:" in vm_source,
            "screen-write-string compile-time capability guard drift")

    disasm = COMFORT_DISASM.read_text()
    call_line = re.search(
        r"^\s*004c CALLPRIM prim=12:screen-write-string argc=3\s*$",
        disasm, re.MULTILINE)
    require(call_line is not None,
            "sealed %repl-step CALLPRIM 12 site absent")
    manifest = json.loads(COMFORT_MANIFEST.read_text())
    repl_step = [row for row in manifest["entries"]
                 if row.get("name") == "%repl-step"]
    require(len(repl_step) == 1 and repl_step[0]["length"] == 255,
            "sealed %repl-step manifest identity drift")
    require("(screen-write-string 0 row \"l65> \")"
            in COMFORT_SOURCE.read_text(),
            "Comfort source no longer owns the primitive call")

    contract = json.loads(PROFILE_CONTRACT.read_text())
    exclusions = [row for row in contract["profile_exclusions"]
                  if row.get("value") == CALLPRIM_ID]
    require(len(exclusions) == 1, "profile exclusion for CALLPRIM 12 drift")
    required_define = exclusions[0]["required_define"]

    product_source = PRODUCT_PROFILE.read_text()
    definitions_source = source_function(product_source, "definitions")
    delivered = f'"{required_define}"' in definitions_source
    require('"LISP65_VM_SCREEN_PRIMS"' in definitions_source,
            "product no longer enables the parent screen primitive family")
    require(not delivered,
            "sealed profile unexpectedly enables screen-write-string")

    host_source = HOST_VM.read_text()
    host_callprim = source_function(host_source, "_callprim")
    host_accepts = "if prim_id == 12:" in host_callprim
    require(host_accepts,
            "host oracle no longer models CALLPRIM 12 unconditionally")

    mutations = mutation_selftest()
    classification = classify(
        emitted=True, delivered=delivered,
        tombstone=(sink[1] == 2), host_accepts=host_accepts)
    return {
        "format": "lisp65-c2.3-v1.7-comfort-phase1a-attribution-v1",
        "recorded_on": "2026-08-25",
        "status": f"ATTRIBUTED: {classification}",
        "authority": {
            "commission": bind(PLAN),
            "sealed_candidate_ELF": bind(ELF),
            "sealed_fix_receipt": bind(FIX_RECEIPT),
            "sealed_media_receipt": bind(MEDIA_RECEIPT),
        },
        "inputs": {
            "comfort_source": bind(COMFORT_SOURCE),
            "comfort_disassembly": bind(COMFORT_DISASM),
            "comfort_manifest": bind(COMFORT_MANIFEST),
            "product_profile_source": bind(PRODUCT_PROFILE),
            "surface_delivery_contract": bind(PROFILE_CONTRACT),
            "host_VM": bind(HOST_VM),
            "target_VM_source": bind(VM_SOURCE),
            "target_VM_header": bind(VM_HEADER),
        },
        "two_sides": {
            "consumer": {
                "object": "%repl-step",
                "object_bytes": repl_step[0]["length"],
                "logical_pc": "0x004c",
                "instruction": "CALLPRIM 12 screen-write-string argc=3",
            },
            "delivered_product": {
                "CALLPRIM_table_section": table_start.section,
                "CALLPRIM_table_start": f"0x{table_start.value:04x}",
                "primitive_id": CALLPRIM_ID,
                "dispatch_target": f"0x{target:04x}",
                "shared_tombstone_ids": [1, 2, 12],
                "sink_bytes": sink.hex(),
                "sink_semantics": "LDX #VM_BADOPCODE; JMP shared status store",
                "status_store": f"0x{status_target:04x}",
                "vm_status_address": f"0x{vm_status.value:04x}",
                "parent_define_present": True,
                "required_define": required_define,
                "required_define_present": delivered,
            },
        },
        "host_target_divergence": {
            "host": ("bytecode_p0.py implements primitive 12 without the "
                     "selected product-profile capability set"),
            "target": ("the final ELF routes primitive 12 to VM_BADOPCODE "
                       "because LISP65_SCREEN_WRITE_STRING is absent"),
            "why_prior_host_gates_were_green": ("they proved dialect-wide "
                                                "semantics, not delivery in "
                                                "the linked product profile"),
        },
        "mechanism": {
            "name": "library-to-product profile-capability closure gap",
            "sequence": [
                "%repl-step returns from %rl-screen-tail",
                "the next visible operation is CALLPRIM 12 at logical PC 0x004c",
                "the selected product has no LISP65_SCREEN_WRITE_STRING case",
                "the linked dispatch table enters the VM_BADOPCODE tombstone",
                "the native REPL prints *** vm: bad bytecode",
            ],
            "excluded_alternatives": [
                "raw refill contents: the sealed capture was byte-correct",
                "generic streamed return: target reductions returned correctly",
                "operand-result lifetime: the repaired ordering reproduced the same red",
                "screen writer corruption: the product never enters that implementation",
            ],
        },
        "decision": {
            "phase1a_outcome": "mechanism named within the three-day box",
            "automatic_block3_pivot": False,
            "next_authority": "owner touchpoint for Phase 1b",
            "not_authorized_here": [
                "enable LISP65_SCREEN_WRITE_STRING in the product profile",
                "rewrite Comfort to consume the resident fallback",
                "product card", "WPLTO", "link", "medium", "device contact",
            ],
            "phase1b_gate_required": ("every native primitive consumed by a "
                                      "library must be delivered by the selected "
                                      "final product profile"),
        },
        "verification": {
            "mutations_rejected": len(mutations),
            "mutation_results": mutations,
            "product_bytes_changed": 0,
            "WPLTO_runs": 0,
            "product_links": 0,
            "media_builds": 0,
            "device_contacts": 0,
        },
        "claim_limit": ("Host/ELF attribution of the sealed Comfort entry "
                        "failure only. It does not choose or qualify a fix."),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    value = derive()
    raw = canonical(value)
    if len(sys.argv) == 2 and sys.argv[1] == "--check":
        require(OUT.is_file() and OUT.read_bytes() == raw,
                "Phase 1a attribution receipt drift")
        print("v1.7 Comfort Phase 1a attribution: CHECK PASS")
        return 0
    require(len(sys.argv) == 1, "usage: c2_v17_comfort_phase1a_attribution.py [--check]")
    OUT.write_bytes(raw)
    print(value["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
