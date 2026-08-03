#!/usr/bin/env python3
"""One product-shaped WPLTO for the Link-87 repeated Ship time base."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

from elf_truth import ElfTruth, ElfTruthError  # noqa: E402
import c2_v13_bank2_read_line_wplto as CARD  # noqa: E402


JOINT = CARD.JOINT
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/ship-builder/v13/link87-repeated-timebase-wplto"
RECEIPT = EVIDENCE / "c2.3-v1.3-link87-repeated-timebase-wplto-receipt.json"
BOOT_RECEIPT = EVIDENCE / "c2.3-v1.3-ship-boot-inheritance-gate-receipt.json"
SHIP_FLEET = ROOT / "build/ship-builder/v13/link87-repeated-timebase-host-first"
OLD_SHIP_FLEET = ROOT / "build/ship-builder/v13/link86-final-5a7c0d18"
LINK86_ELF = ROOT / (
    "build/c2.3/v1.3.0-candidate-product-link86-r1/final/"
    "lisp65-c2-substitution-linked.prg.elf"
)
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def symbol_bytes(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    require(symbol.bytes > 0, f"unsized symbol: {name}")
    section = truth.section(symbol.section)
    data = truth.section_bytes(symbol.section)
    offset = symbol.value - section.address
    require(0 <= offset <= len(data) - symbol.bytes,
            f"symbol outside section: {name}")
    return data[offset:offset + symbol.bytes]


def truth(path: Path) -> ElfTruth:
    return ElfTruth.read(path, llvm_readobj=READOBJ, include_section_data=True)


def ship_prices() -> dict[str, Any]:
    rows = []
    runtime_delta: int | None = None
    for name in ("hello", "long-runner", "random-q", "interactive"):
        old = load(OLD_SHIP_FLEET / f"{name}.receipt.json")
        new = load(SHIP_FLEET / f"{name}.receipt.json")
        delta = (new["runtime_audit"]["prg_bytes"]
                 - old["runtime_audit"]["prg_bytes"])
        runtime_delta = delta if runtime_delta is None else runtime_delta
        require(delta == runtime_delta == 220,
                f"Ship repeated-timebase price drift: {name}/{delta}")
        require("boot-armed=1 boot-verified=1 input-armed=1"
                in new["host_execution"]["output"],
                f"Ship host boot witness drift: {name}")
        rows.append({
            "sample": name,
            "before_prg_bytes": old["runtime_audit"]["prg_bytes"],
            "after_prg_bytes": new["runtime_audit"]["prg_bytes"],
            "delta_bytes": delta,
            "host_boot_witness": True,
        })
    return {"runtime_delta_bytes": runtime_delta, "samples": rows}


def target_runtime() -> dict[str, Any]:
    path = SHIP_FLEET / "interactive.runtime.elf"
    image = truth(path)
    handler = symbol_bytes(image, "lisp65_ship_timebase_irq")
    require(handler == bytes.fromhex(
        "48 ad 19 d0 29 01 f0 0b 8d 19 d0 ee d8 8b d0 03 ee d9 8b "
        "68 6c da 8b"),
        "linked Ship IRQ handler bytes drift")
    require(image.symbol("lisp65_ship_frame_lo").value == 0x8BD8
            and image.symbol("lisp65_ship_frame_hi").value == 0x8BD9
            and image.symbol("lisp65_ship_old_irq").value == 0x8BDA,
            "linked Ship timebase BSS geometry drift")
    frame_read = symbol_bytes(image, "ship_frame_read")
    require(bytes.fromhex("ae d9 8b ad d8 8b ac d9 8b") in frame_read
            and bytes.fromhex("a6 a1 a5 a2") not in frame_read,
            "linked Ship public clock still reads A1/A2")
    getin_sites = []
    for section in image.sections:
        if "SHF_EXECINSTR" not in section.flags:
            continue
        data = image.section_bytes(section.name)
        for offset in range(max(0, len(data) - 2)):
            if data[offset:offset + 3] == bytes.fromhex("20 e4 ff"):
                getin_sites.append(f"0x{section.address + offset:04x}")
    require(len(getin_sites) == 3, "linked GETIN edge inventory drift")
    return {
        "elf": JOINT.bind(path),
        "irq_handler_address": f"0x{image.symbol('lisp65_ship_timebase_irq').value:04x}",
        "irq_handler_bytes": len(handler),
        "irq_handler_sha256": hashlib.sha256(handler).hexdigest(),
        "counter": {"low": "0x8bd8", "high": "0x8bd9"},
        "old_irq_vector": "0x8bda",
        "retired_a1_a2_reader_absent": True,
        "getin_call_sites": getin_sites,
    }


def main() -> int:
    boot = load(BOOT_RECEIPT)
    require(boot["status"] == "passed-ship-owned-repeated-frame-clock"
            and boot["host_execution"]["executions"] == 3
            and boot["host_execution"]["negative_executions"] == 2
            and boot["mutation_count"] == 19
            and boot["target_object_execution"]["bytes"] == 23,
            "Ship repeated-progress gate authority drift")
    prices = ship_prices()
    runtime = target_runtime()
    if RECEIPT.exists():
        value = load(RECEIPT)
        require(value["status"]
                == "passed-Link87-repeated-timebase-one-product-shaped-WPLTO"
                and BUILD.exists(),
                "Link-87 WPLTO finalization has no completed receipt")
    else:
        require(not BUILD.exists(), "Link-87 repeated-timebase WPLTO is one-shot")
        CARD.configure()
        JOINT.BUILD = BUILD
        JOINT.RECEIPT = RECEIPT
        JOINT.DRIVER = DRIVER
        result = JOINT.wplto()
        require(result == 0, "Link-87 repeated-timebase WPLTO red")
    value = load(RECEIPT)
    facade = load(BUILD / "wplto/fixed-host-facade-final.json")
    fixed = facade["fixed_state_contract"]["bank0_hot_bss"]
    noinit_address = fixed["end_exclusive"]
    noinit_bytes = fixed["following_noinit_bytes"]
    overlay_floor = (noinit_address + noinit_bytes + 1) & ~1
    require(noinit_address == 0xC34D and noinit_bytes == 6
            and overlay_floor == 0xC354,
            "Link-87 fix moved pinned Workbench geometry")
    new_elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    old_truth = truth(LINK86_ELF)
    new_truth = truth(new_elf)
    old_owner = symbol_bytes(old_truth, "c2_kernal_take_ownership")
    new_owner = symbol_bytes(new_truth, "c2_kernal_take_ownership")
    require(old_owner == new_owner,
            "Ship-only clock changed Workbench ownership bytes")
    value.update({
        "format": "lisp65-c2.3-v1.3-link87-repeated-timebase-WPLTO-v1",
        "recorded_on": "2026-08-03",
        "status": "passed-Link87-repeated-timebase-one-product-shaped-WPLTO",
        "wplto_probes_consumed": 1,
        "ship_runtime_price": prices,
        "target_runtime": runtime,
        "workbench_owner": {
            "c2_kernal_take_ownership_bytes": len(new_owner),
            "byteidentical_to_link86": True,
            "noinit_address": "0xc34d",
            "noinit_bytes": 6,
            "overlay_floor": "0xc354",
        },
        "boot_inheritance_gate": JOINT.bind(BOOT_RECEIPT),
        "authority": {
            **value["authority"],
            "driver": JOINT.bind(DRIVER),
            "link86_ELF": JOINT.bind(LINK86_ELF),
            "ship_fleet": JOINT.bind(SHIP_FLEET / "fleet-receipt.json"),
        },
        "next_gate": "one Link 87 and one physical Ada+RETURN row",
        "claim_limit": (
            "One non-promotable product-shaped WPLTO plus target Ship builds; "
            "no successor product identity or hardware claim."
        ),
    })
    RECEIPT.write_bytes(JOINT.CAN.json_bytes(value))
    print(
        "c2-v13-link87-repeated-timebase-wplto: PASS "
        f"ship=+{prices['runtime_delta_bytes']} irq=23 owner=byteidentical "
        "noinit=6 overlay=0xc354 probes=1"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, JOINT.WPLTOError, ElfTruthError,
            OSError, KeyError, ValueError) as error:
        print(f"c2-v13-link87-repeated-timebase-wplto: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
