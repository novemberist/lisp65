#!/usr/bin/env python3
"""One product-shaped WPLTO for the Link-86 Ship boot time-base fix."""

from __future__ import annotations

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
BUILD = ROOT / "build/ship-builder/v13/link86-boot-timebase-wplto"
RECEIPT = EVIDENCE / "c2.3-v1.3-link86-boot-timebase-wplto-receipt.json"
BOOT_RECEIPT = EVIDENCE / "c2.3-v1.3-ship-boot-inheritance-gate-receipt.json"
SHIP_FLEET = ROOT / "build/ship-builder/v13/link86-boot-timebase-host-first"
OLD_SHIP_FLEET = ROOT / "build/ship-builder/v13/final-fleet-bank2"
LINK85_ELF = ROOT / (
    "build/c2.3/v1.3.0-candidate-product-link85-r1/final/"
    "lisp65-c2-substitution-linked.prg.elf"
)
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


def symbol_bytes(path: Path, name: str) -> bytes:
    truth = ElfTruth.read(
        path, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    symbol = truth.symbol(name)
    require(symbol.bytes > 0, f"unsized symbol: {name}")
    section = truth.section(symbol.section)
    data = truth.section_bytes(symbol.section)
    offset = symbol.value - section.address
    require(0 <= offset <= len(data) - symbol.bytes,
            f"symbol outside section: {name}")
    return data[offset:offset + symbol.bytes]


def ship_prices() -> dict[str, Any]:
    rows = []
    for name in ("hello", "long-runner", "random-q", "interactive"):
        old = load(OLD_SHIP_FLEET / f"{name}.receipt.json")
        new = load(SHIP_FLEET / f"{name}.receipt.json")
        delta = (new["runtime_audit"]["prg_bytes"]
                 - old["runtime_audit"]["prg_bytes"])
        require(
            delta == 116
            and "boot-armed=1 boot-verified=1 input-armed=1"
                in new["host_execution"]["output"],
            f"Ship target/host boot price drift: {name}",
        )
        rows.append({
            "sample": name,
            "before_prg_bytes": old["runtime_audit"]["prg_bytes"],
            "after_prg_bytes": new["runtime_audit"]["prg_bytes"],
            "delta_bytes": delta,
            "host_boot_witness": True,
        })
    return {"runtime_delta_bytes": 116, "samples": rows}


def main() -> int:
    boot = load(BOOT_RECEIPT)
    require(
        boot["status"] == "passed-ship-boot-arms-and-verifies-inherited-io"
        and boot["host_execution"]["executions"] == 1
        and boot["mutation_count"] == 10,
        "Ship boot-inheritance gate authority drift",
    )
    prices = ship_prices()
    if RECEIPT.exists():
        value = load(RECEIPT)
        require(
            value["status"] == "passed-v1.3-joint-one-product-shaped-WPLTO"
            and BUILD.exists(),
            "Link-86 WPLTO finalization has no completed generic receipt",
        )
    else:
        require(not BUILD.exists(), "Link-86 boot time-base WPLTO is one-shot")
        CARD.configure()
        JOINT.BUILD = BUILD
        JOINT.RECEIPT = RECEIPT
        JOINT.DRIVER = DRIVER
        result = JOINT.wplto()
        require(result == 0, "Link-86 boot time-base WPLTO red")
    value = load(RECEIPT)
    facade = load(BUILD / "wplto/fixed-host-facade-final.json")
    fixed = facade["fixed_state_contract"]["bank0_hot_bss"]
    noinit_address = fixed["end_exclusive"]
    noinit_bytes = fixed["following_noinit_bytes"]
    overlay_floor = (noinit_address + noinit_bytes + 1) & ~1
    require(
        noinit_address == 0xc34d
        and noinit_bytes == 6
        and overlay_floor == 0xc354,
        "Link-86 fix moved pinned Workbench geometry",
    )
    new_elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    old_owner = symbol_bytes(LINK85_ELF, "c2_kernal_take_ownership")
    new_owner = symbol_bytes(new_elf, "c2_kernal_take_ownership")
    require(old_owner == new_owner,
            "shared inline raster arm changed Workbench ownership bytes")
    value.update({
        "format": "lisp65-c2.3-v1.3-link86-boot-timebase-WPLTO-v1",
        "recorded_on": "2026-08-02",
        "status": "passed-Link86-boot-timebase-one-product-shaped-WPLTO",
        "wplto_probes_consumed": 1,
        "ship_runtime_price": prices,
        "workbench_owner": {
            "c2_kernal_take_ownership_bytes": len(new_owner),
            "byteidentical_to_link85": True,
            "noinit_address": "0xc34d",
            "noinit_bytes": 6,
            "overlay_floor": "0xc354",
        },
        "boot_inheritance_gate": JOINT.bind(BOOT_RECEIPT),
        "authority": {
            **value["authority"],
            "driver": JOINT.bind(DRIVER),
            "link85_ELF": JOINT.bind(LINK85_ELF),
            "ship_fleet": JOINT.bind(SHIP_FLEET / "fleet-receipt.json"),
        },
        "next_gate": "one Link 86 and one physical Ada+RETURN row",
        "claim_limit": (
            "One non-promotable product-shaped WPLTO plus target Ship builds; "
            "no successor product identity or hardware claim."
        ),
    })
    RECEIPT.write_bytes(JOINT.CAN.json_bytes(value))
    print(
        "c2-v13-link86-boot-timebase-wplto: PASS "
        f"ship=+{prices['runtime_delta_bytes']} owner=byteidentical "
        "noinit=6 overlay=0xc354 probes=1"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, JOINT.WPLTOError, ElfTruthError,
            OSError, KeyError, ValueError) as error:
        print(f"c2-v13-link86-boot-timebase-wplto: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
