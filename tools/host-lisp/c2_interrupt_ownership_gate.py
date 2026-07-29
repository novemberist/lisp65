#!/usr/bin/env python3
"""Bind strict C2 interrupt ownership to source, policy and final ELF.

The exact tested-core graph has three software-maskable internal interrupt
families that the old ownership cut inherited from firmware: Ethernet,
Auto-IEC and Audio-DMA.  This gate proves all three are disabled under SEI
after I/O personality selection and before raster publication.  Source
mutations close omission/wrong-value/wrong-register classes; the optional
ELF audit proves the final WPLTO artifact still contains the six MMIO edges
in the required order.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import c2_crc_codegen_gate as DISASM
from elf_truth import ElfTruth


ROOT = Path(__file__).resolve().parents[2]
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
SOURCE = ROOT / "src/c2_kernal_runtime.c"
WINDOW = ROOT / "src/c2_kernal_window.s"
POLICY = ROOT / "config/c2-interrupt-ownership-policy.json"
KNOWN = ROOT / "config/v12-known-issues.json"
KNOWN_DOC = ROOT / "docs/known-issues.md"
UPSTREAM = ROOT / "docs/upstream-findings.md"
HARDWARE = ROOT / "config/c2-interrupt-ownership-hardware-session.json"
FUNCTION = "c2_kernal_take_ownership"
BOOT_ONLY_CRC = "c2k_crc16"
BOOT_ONLY_CRC_INPUT_SECTION = ".text.c2_kernal_boot_only"
BOOT_ONLY_CRC_OUTPUT_SECTION = ".text"

FAMILIES = {
    "ethernet": {
        "macro": "ETHERNET_IRQ",
        "address": 0xD6E1,
        "write": 0x00,
        "read_mask": 0xC0,
        "wrong_address": "0xd6e0",
    },
    "auto-iec": {
        "macro": "AUTOIEC_IRQ",
        "address": 0xD697,
        "write": 0xF0,
        "read_mask": 0x0F,
        "wrong_address": "0xd696",
    },
    "audio-dma": {
        "macro": "AUDIODMA_IRQ",
        "address": 0xD713,
        "write": 0x00,
        "read_mask": 0x0F,
        "wrong_address": "0xd712",
    },
}


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority missing: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def _between(text: str, start: str, end: str) -> str:
    first = text.index(start)
    last = text.index(end, first)
    return text[first:last]


def source_gate(source: str) -> dict[str, Any]:
    require(
        '#define C2K_BOOT_ONLY __attribute__((noinline, '
        'section(".text.c2_kernal_boot_only")))' in source
        and source.count(
            "static C2K_BOOT_ONLY uint16_t c2k_crc16(") == 1,
        "boot-only CRC placement contract drift",
    )
    body = _between(
        source,
        "C2K_SECTION uint8_t c2_kernal_take_ownership(void) {",
        "C2K_SECTION uint16_t c2_kernal_frame_count(void) {",
    )
    order_tokens = [
        '__asm__ volatile("sei\\n\\tldz #0"',
        "c2_kernal_reveal_io();",
        "ETHERNET_IRQ = 0u;",
        "AUTOIEC_IRQ = 0xf0u;",
        "AUDIODMA_IRQ = 0u;",
        "if ((ETHERNET_IRQ & 0xc0u) != 0u",
        "|| (AUTOIEC_IRQ & 0x0fu) != 0u",
        "|| (AUDIODMA_IRQ & 0x0fu) != 0u)",
        "c2k_copy(C2_KERNAL_WINDOW_STAGE_PHYSICAL,",
        "VIC_D01A = 0x01u;",
        '__asm__ volatile("cli"',
    ]
    positions: list[int] = []
    for token in order_tokens:
        require(body.count(token) == 1, f"ownership token drift: {token}")
        positions.append(body.index(token))
    require(positions == sorted(positions), "ownership ordering drift")

    for row in FAMILIES.values():
        define = (
            f"#define {row['macro']}"
            + (" " * (13 - len(str(row["macro"]))))
            + f"REG8(0x{int(row['address']):04x})"
        )
        # Whitespace in the aligned macro block is intentionally not an
        # authority.  Address and one-definition identity are.
        pattern = re.compile(
            rf"^#define\s+{re.escape(str(row['macro']))}\s+"
            rf"REG8\(0x{int(row['address']):04x}\)$",
            re.MULTILINE,
        )
        require(len(pattern.findall(source)) == 1,
                f"MMIO macro drift: {define.strip()}")
    require("c2_kernal_fail_closed" not in body,
            "ownership readback must use the existing return-false boundary")
    return {
        "SEI_before_personality": True,
        "personality_before_masks": True,
        "source_masks": {
            name: {
                "address": f"${int(row['address']):04X}",
                "write": int(row["write"]),
                "readback_mask": int(row["read_mask"]),
            }
            for name, row in FAMILIES.items()
        },
        "readback_before_window_publish": True,
        "raster_enable_and_CLI_last": True,
        "handler_changed": False,
        "boot_only_crc": {
            "symbol": BOOT_ONLY_CRC,
            "input_section": BOOT_ONLY_CRC_INPUT_SECTION,
            "linked_output_section": BOOT_ONLY_CRC_OUTPUT_SECTION,
            "direct_callers": [FUNCTION],
            "post_ownership_reachable": False,
        },
    }


def policy_gate(policy: dict[str, Any]) -> dict[str, Any]:
    require(policy.get("status") == "owner-accepted-product-cut-authorized",
            "interrupt policy is not owner-accepted")
    summary = policy["inventory_summary"]
    require(summary["new_internal_mask_families"] ==
            ["ethernet", "auto-iec", "audio-dma"],
            "mask-family inventory drift")
    inventory = {row["id"]: row for row in policy["inventory"]}
    require(inventory["f011-sd"]["current_classification"] ==
            "structurally-impossible",
            "F011 was restored as a live CPU IRQ source")
    require(inventory["buffered-uart"]["current_classification"] ==
            "structurally-line-inactive-on-bound-core",
            "Buffered-UART line classification drift")
    require(inventory["audio-dma"]["current_classification"] == "unhandled"
            and "irq_pending" in inventory["audio-dma"]["route"],
            "Audio-DMA exact-core IRQ route was erased")
    require(policy["owner_review"]["decision"] ==
            "accepted-as-one-unit-2026-07-28",
            "owner decision drift")
    return {
        "tested_core": policy["scope"]["device_core_commit"],
        "inventory_rows": len(policy["inventory"]),
        "new_mask_families": summary["new_internal_mask_families"],
        "external_exclusions": summary["external_profile_exclusions"],
    }


def documentation_gate() -> dict[str, Any]:
    known = load(KNOWN)
    active = {row["id"]: row for row in known["active"]}
    cartridge = active.get("c2-lite-interrupt-generating-cartridge", {})
    require(cartridge.get("status") == "unsupported-hardware-profile"
            and "One foreign or source-less IRQ" in
            cartridge.get("claim_limit", "")
            and "held or repeating cartridge" in
            cartridge.get("claim_limit", ""),
            "machine-readable cartridge storm boundary missing")
    known_text = " ".join(
        KNOWN_DOC.read_text(encoding="utf-8").split())
    require("interrupt-generating cartridges" in known_text
            and "raster-delimited episode" in known_text
            and "interrupt storm" in known_text,
            "public cartridge storm boundary missing")
    upstream = " ".join(UPSTREAM.read_text(encoding="utf-8").split())
    require("### L11 — Audio-DMA interrupt documentation" in upstream
            and "gs4510.vhdl#L4533-L4549" in upstream
            and "gs4510.vhdl#L4551-L4553" in upstream
            and "cannot presently generate interrupts" in upstream,
            "public Audio-DMA upstream finding is incomplete")
    hardware = load(HARDWARE)
    require(hardware["expected"] == "(0 0 0)"
            and [row["address"] for row in hardware["registers"]]
            == ["$D6E1", "$D697", "$D713"]
            and "final Phase-I/Phase-V/K2 bundled device session"
            in hardware["session_rule"],
            "bundled hardware row drift")
    return {
        "public_known_issue": binding(KNOWN_DOC),
        "known_issue_authority": binding(KNOWN),
        "upstream_L11": binding(UPSTREAM),
        "bundled_hardware_line": binding(HARDWARE),
    }


def mutation_gate(source: str, policy: dict[str, Any]) -> dict[str, Any]:
    mutations: dict[str, str] = {}
    for name, row in FAMILIES.items():
        macro = str(row["macro"])
        value = f"0x{int(row['write']):x}u"
        if int(row["write"]) == 0:
            value = "0u"
        write = f"    {macro} = {value};\n"
        require(write in source, f"mutation anchor absent: {name} write")
        mutations[f"{name}-mask-omitted"] = source.replace(write, "", 1)
        wrong_value = "0xffu" if int(row["write"]) != 0xFF else "0u"
        mutations[f"{name}-mask-value"] = source.replace(
            write, f"    {macro} = {wrong_value};\n", 1)
        address = f"0x{int(row['address']):04x}"
        mutations[f"{name}-wrong-register"] = source.replace(
            address, str(row["wrong_address"]), 1)
        mask = f"0x{int(row['read_mask']):02x}u"
        require(mask in source, f"mutation anchor absent: {name} read mask")
        mutations[f"{name}-readback-omitted"] = source.replace(
            f"({macro} & {mask})", f"(0u & {mask})", 1)

    rejected: list[str] = []
    for name, candidate in mutations.items():
        try:
            source_gate(candidate)
        except (GateError, ValueError):
            rejected.append(name)
    require(len(rejected) == len(mutations),
            "one or more ownership source mutations survived")

    placement_mutations = {
        "crc-restored-to-fixed-handoff": source.replace(
            "static C2K_BOOT_ONLY uint16_t c2k_crc16(",
            "static C2K_SECTION uint16_t c2k_crc16(", 1),
        "crc-moved-to-owned-e000-window": source.replace(
            'section(".text.c2_kernal_boot_only")',
            'section(".lisp65_c2_kernal_window.c2_resident")', 1),
    }
    for name, candidate in placement_mutations.items():
        try:
            source_gate(candidate)
        except (GateError, ValueError):
            rejected.append(name)
    require(
        len(rejected) == len(mutations) + len(placement_mutations),
        "one or more boot-only CRC placement mutations survived",
    )

    policy_mutations: dict[str, dict[str, Any]] = {}
    audio = copy.deepcopy(policy)
    next(row for row in audio["inventory"]
         if row["id"] == "audio-dma")["current_classification"] = \
        "structurally-impossible"
    policy_mutations["audio-dma-classified-impossible"] = audio
    f011 = copy.deepcopy(policy)
    next(row for row in f011["inventory"]
         if row["id"] == "f011-sd")["current_classification"] = "unhandled"
    policy_mutations["f011-classified-live"] = f011
    policy_rejected: list[str] = []
    for name, candidate in policy_mutations.items():
        try:
            policy_gate(candidate)
        except (GateError, ValueError):
            policy_rejected.append(name)
    require(len(policy_rejected) == len(policy_mutations),
            "interrupt-graph policy mutation survived")
    return {
        "source_mutations_rejected": rejected,
        "policy_mutations_rejected": policy_rejected,
        "rejected": len(rejected) + len(policy_rejected),
        "total":
            len(mutations) + len(placement_mutations)
            + len(policy_mutations),
    }


def _direct_address(operand: str) -> int | None:
    match = re.match(r"^\$([0-9a-f]+)\b", operand)
    return int(match.group(1), 16) if match else None


def elf_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
    symbol = truth.symbol(FUNCTION)
    require(symbol.symbol_type == "Function" and symbol.bytes > 0,
            "ownership function missing or unsized in final ELF")
    crc = truth.symbol(BOOT_ONLY_CRC)
    require(
        crc.symbol_type == "Function"
        and crc.bytes > 0
        and crc.section == BOOT_ONLY_CRC_OUTPUT_SECTION
        and crc.value < symbol.value,
        "boot-only CRC is absent, late, or not in ordinary resident text",
    )
    completed = subprocess.run(
        [str(TOOLCHAIN / "llvm-objdump"), "-d", "--no-show-raw-insn",
         "--disassemble-symbols=" + FUNCTION, str(elf)],
        check=True, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    rows = [
        row for row in DISASM.disassembly_rows(completed.stdout)
        if symbol.value <= int(row["address"]) < symbol.value + symbol.bytes
    ]
    require(rows and rows[0]["opcode"] == "sei"
            and any(row["opcode"] == "cli" for row in rows),
            "final ownership function lost SEI/CLI boundary")
    crc_edges = [
        row for row in rows
        if row["opcode"] in {"jsr", "jmp"}
        and _direct_address(str(row["operand"])) == crc.value
    ]
    require(
        len(crc_edges) == 1 and crc_edges[0]["opcode"] == "jsr",
        f"ownership-to-boot-only-CRC edge drift: {crc_edges}",
    )
    all_disassembly = subprocess.run(
        [str(TOOLCHAIN / "llvm-objdump"), "-d", "--no-show-raw-insn",
         str(elf)],
        check=True, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    all_crc_edges = [
        row for row in DISASM.disassembly_rows(all_disassembly.stdout)
        if row["opcode"] in {"jsr", "jmp"}
        and _direct_address(str(row["operand"])) == crc.value
    ]
    require(
        len(all_crc_edges) == 1,
        f"boot-only CRC has a post-ownership or second caller: {all_crc_edges}",
    )

    def edge_indices(address: int, opcodes: set[str]) -> list[int]:
        return [
            index for index, row in enumerate(rows)
            if row["opcode"] in opcodes
            and _direct_address(str(row["operand"])) == address
        ]

    stores: dict[str, int] = {}
    loads: dict[str, int] = {}
    for name, family in FAMILIES.items():
        store_rows = edge_indices(
            int(family["address"]), {"sta", "stx", "sty", "stz"})
        load_rows = edge_indices(
            int(family["address"]), {"lda", "ldx", "ldy"})
        require(len(store_rows) == 1,
                f"final ELF {name} mask-store edge drift: {store_rows}")
        require(len(load_rows) == 1 and load_rows[0] > store_rows[0],
                f"final ELF {name} readback edge drift: {load_rows}")
        stores[name] = store_rows[0]
        loads[name] = load_rows[0]

    reveal = next(
        (index for index, row in enumerate(rows)
         if row["opcode"] == "jsr"
         and "c2_kernal_reveal_io" in str(row["operand"])), None)
    publish = next(
        (index for index, row in enumerate(rows)
         if row["opcode"] == "jsr"
         and "c2k_copy" in str(row["operand"])), None)
    cli = next(index for index, row in enumerate(rows)
               if row["opcode"] == "cli")
    require(reveal is not None and publish is not None,
            "final ELF ownership call edges missing")
    require(
        int(reveal) < min(stores.values())
        and max(loads.values()) < int(publish) < cli,
        "final ELF MMIO edge ordering drift")
    immediates = {
        str(row["operand"]) for row in rows
        if row["opcode"] in {"and", "bit"}
        and str(row["operand"]).startswith("#$")
    }
    ethernet_threshold = any(
        row["opcode"] == "cpx"
        and str(row["operand"]) == "#$40"
        and index > loads["ethernet"]
        for index, row in enumerate(rows)
    )
    require(
        "#$f" in immediates
        and ("#$c0" in immediates or ethernet_threshold),
        f"final ELF readback masks drift: masks={sorted(immediates)} "
        f"ethernet-threshold={ethernet_threshold}",
    )
    return {
        "elf": binding(elf),
        "function": {
            "value": symbol.value,
            "bytes": symbol.bytes,
            "section": symbol.section,
        },
        "boot_only_crc": {
            "value": crc.value,
            "bytes": crc.bytes,
            "section": crc.section,
            "source_input_section": BOOT_ONLY_CRC_INPUT_SECTION,
            "direct_caller": FUNCTION,
            "direct_edge_count_whole_ELF": len(all_crc_edges),
            "before_handoff_address": True,
            "post_ownership_reachable": False,
        },
        "stores": {name: rows[index]["address"]
                   for name, index in stores.items()},
        "readbacks": {name: rows[index]["address"]
                      for name, index in loads.items()},
        "personality_call_before_masks": True,
        "readbacks_before_window_publish": True,
        "CLI_after_publish": True,
    }


def audit(*, elf: Path | None = None) -> dict[str, Any]:
    source = SOURCE.read_text(encoding="utf-8")
    policy = load(POLICY)
    window_before = sha(WINDOW)
    result = {
        "format": "lisp65-c2-interrupt-ownership-gate-v1",
        "status": "passed-strict-internal-interrupt-ownership",
        "source": binding(SOURCE),
        "window_handler": {
            **binding(WINDOW),
            "unchanged_by_policy": True,
            "source_less_episode_guard": "retained",
        },
        "policy": {
            **binding(POLICY),
            **policy_gate(policy),
        },
        "source_contract": source_gate(source),
        "documentation": documentation_gate(),
        "mutations": mutation_gate(source, policy),
        "final_ELF": elf_gate(elf) if elf is not None else {
            "status": "not-requested-source-gate-only",
        },
    }
    require(sha(WINDOW) == window_before,
            "source gate modified the IRQ handler")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    elf = args.elf
    if elf is not None and not elf.is_absolute():
        elf = ROOT / elf
    value = audit(elf=elf)
    if args.selftest:
        require(value["mutations"]["rejected"] == 16,
                "ownership selftest mutation census drift")
    rendered = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if args.receipt is not None:
        receipt = args.receipt
        if not receipt.is_absolute():
            receipt = ROOT / receipt
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(rendered, encoding="utf-8")
    print(
        "c2-interrupt-ownership: PASS "
        f"masks={len(FAMILIES)} "
        f"mutations={value['mutations']['rejected']}/"
        f"{value['mutations']['total']} "
        f"elf={'yes' if elf is not None else 'no'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, KeyError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"c2-interrupt-ownership: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
