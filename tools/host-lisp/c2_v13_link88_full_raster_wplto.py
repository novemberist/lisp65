#!/usr/bin/env python3
"""One product-shaped WPLTO for the Link-88 full 9-bit raster witness."""

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
BUILD = ROOT / "build/ship-builder/v13/link88-full-raster-wplto"
RECEIPT = EVIDENCE / "c2.3-v1.3-link88-full-raster-wplto-receipt.json"
BOOT_RECEIPT = EVIDENCE / "c2.3-v1.3-ship-boot-inheritance-gate-receipt.json"
SHIP_FLEET = ROOT / "build/ship-builder/v13/link88-full-raster-host-first"
OLD_SHIP_FLEET = ROOT / "build/ship-builder/v13/link87-final-3bcb488d"
LINK87_ELF = ROOT / (
    "build/c2.3/v1.3.0-candidate-product-link87-r1/final/"
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


def truth(path: Path) -> ElfTruth:
    return ElfTruth.read(path, llvm_readobj=READOBJ, include_section_data=True)


def symbol_bytes(image: ElfTruth, name: str) -> bytes:
    symbol = image.symbol(name)
    section = image.section(symbol.section)
    data = image.section_bytes(symbol.section)
    offset = symbol.value - section.address
    require(symbol.bytes > 0 and 0 <= offset <= len(data) - symbol.bytes,
            f"symbol outside section: {name}")
    return data[offset:offset + symbol.bytes]


def ship_prices() -> dict[str, Any]:
    rows = []
    for name in ("hello", "long-runner", "random-q", "interactive"):
        old = load(OLD_SHIP_FLEET / f"{name}.receipt.json")
        new = load(SHIP_FLEET / f"{name}.receipt.json")
        delta = new["runtime_audit"]["prg_bytes"] - old["runtime_audit"]["prg_bytes"]
        require(delta == 104, f"Ship full-raster price drift: {name}/{delta}")
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
    return {"runtime_delta_bytes": 104, "samples": rows}


def target_runtime() -> dict[str, Any]:
    path = SHIP_FLEET / "interactive.runtime.elf"
    image = truth(path)
    handler = symbol_bytes(image, "lisp65_ship_timebase_irq")
    reader = symbol_bytes(image, "ship_raster_read")
    reference = symbol_bytes(image, "ship_reference_wrap")
    require(handler == bytes.fromhex(
        "48 ad 19 d0 29 01 f0 0b 8d 19 d0 ee 40 8c d0 03 ee 41 8c "
        "68 6c 42 8c"), "linked Ship IRQ handler bytes drift")
    require(image.symbol("lisp65_ship_frame_lo").value == 0x8C40
            and image.symbol("lisp65_ship_frame_hi").value == 0x8C41
            and image.symbol("lisp65_ship_old_irq").value == 0x8C42,
            "linked Ship full-raster BSS geometry drift")
    require(reader.count(bytes.fromhex("ad 11 d0")) == 2
            and reader.count(bytes.fromhex("ae 12 d0")) == 1
            and reader.count(bytes.fromhex("29 80")) == 2
            and bytes.fromhex("d0 ec") in reader,
            "linked Ship reader does not take a tear-free 9-bit sample")
    reader_address = image.symbol("ship_raster_read").value
    call = bytes((0x20, reader_address & 0xff, reader_address >> 8))
    require(reference.count(call) == 2,
            "linked frame reference does not consume repeated 9-bit samples")
    return {
        "elf": JOINT.bind(path),
        "irq_handler_address": f"0x{image.symbol('lisp65_ship_timebase_irq').value:04x}",
        "irq_handler_bytes": len(handler),
        "irq_handler_sha256": hashlib.sha256(handler).hexdigest(),
        "counter": {"low": "0x8c40", "high": "0x8c41"},
        "old_irq_vector": "0x8c42",
        "raster_reader_address": f"0x{reader_address:04x}",
        "raster_reader_bytes": len(reader),
        "raster_reader_sha256": hashlib.sha256(reader).hexdigest(),
        "d011_reads": 2,
        "d012_reads": 1,
        "tear_retry_bound": True,
        "reference_reader_calls": 2,
    }


def main() -> int:
    boot = load(BOOT_RECEIPT)
    matrix = boot["raster_phase_matrix"]
    require(boot["status"]
            == "passed-ship-owned-full-9bit-repeated-frame-clock"
            and boot["host_execution"]["executions"] == 3
            and boot["mutation_count"] == 22
            and matrix["full_9bit_high_to_low_passes"] == 312
            and matrix["d012_low_decrease_passes"] == 0
            and boot["target_object_execution"]["bytes"] == 23,
            "Ship full-raster gate authority drift")
    prices = ship_prices()
    runtime = target_runtime()
    if RECEIPT.exists():
        value = load(RECEIPT)
        require(value["status"]
                == "passed-Link88-full-raster-one-product-shaped-WPLTO"
                and BUILD.exists(),
                "Link-88 WPLTO finalization has no completed receipt")
    else:
        require(not BUILD.exists(), "Link-88 full-raster WPLTO is one-shot")
        CARD.configure()
        JOINT.BUILD = BUILD
        JOINT.RECEIPT = RECEIPT
        JOINT.DRIVER = DRIVER
        require(JOINT.wplto() == 0, "Link-88 full-raster WPLTO red")
    value = load(RECEIPT)
    facade = load(BUILD / "wplto/fixed-host-facade-final.json")
    fixed = facade["fixed_state_contract"]["bank0_hot_bss"]
    noinit_address = fixed["end_exclusive"]
    noinit_bytes = fixed["following_noinit_bytes"]
    overlay_floor = (noinit_address + noinit_bytes + 1) & ~1
    require(noinit_address == 0xC34D and noinit_bytes == 6
            and overlay_floor == 0xC354,
            "Link-88 fix moved pinned Workbench geometry")
    new_elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    old_owner = symbol_bytes(truth(LINK87_ELF), "c2_kernal_take_ownership")
    new_owner = symbol_bytes(truth(new_elf), "c2_kernal_take_ownership")
    require(old_owner == new_owner,
            "Ship-only raster witness changed Workbench ownership bytes")
    value.update({
        "format": "lisp65-c2.3-v1.3-link88-full-raster-WPLTO-v1",
        "recorded_on": "2026-08-03",
        "status": "passed-Link88-full-raster-one-product-shaped-WPLTO",
        "wplto_probes_consumed": 1,
        "ship_runtime_price": prices,
        "target_runtime": runtime,
        "workbench_owner": {
            "c2_kernal_take_ownership_bytes": len(new_owner),
            "byteidentical_to_link87": True,
            "noinit_address": "0xc34d",
            "noinit_bytes": 6,
            "overlay_floor": "0xc354",
        },
        "boot_inheritance_gate": JOINT.bind(BOOT_RECEIPT),
        "authority": {
            **value["authority"],
            "driver": JOINT.bind(DRIVER),
            "link87_ELF": JOINT.bind(LINK87_ELF),
            "ship_fleet": JOINT.bind(SHIP_FLEET / "fleet-receipt.json"),
        },
        "next_gate": "one Link 88 and one physical Ada+RETURN row",
        "claim_limit": (
            "One non-promotable product-shaped WPLTO plus target Ship builds; "
            "no successor product identity or hardware claim."
        ),
    })
    RECEIPT.write_bytes(JOINT.CAN.json_bytes(value))
    print("c2-v13-link88-full-raster-wplto: PASS "
          "ship=+104 irq=23 raster=9bit phases=312/312 low-byte=0/312 "
          "owner=byteidentical noinit=6 overlay=0xc354 probes=1")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, JOINT.WPLTOError, ElfTruthError,
            OSError, KeyError, ValueError) as error:
        print(f"c2-v13-link88-full-raster-wplto: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
