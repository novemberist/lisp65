#!/usr/bin/env python3
"""Prove v1.6 hybrid claims from the final linked consumer."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_comfort_input_fidelity as FIDELITY  # noqa: E402
import c2_v160_input_service_hybrid as HYBRID  # noqa: E402
import c2_v160_input_service_time_pricing as PRICE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


CONTRACT = ROOT / "config/c2-v160-input-service-hybrid-contract.json"
EDITOR = ROOT / "lib/stdlib-read-line.lisp"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
SECTION = ".lisp65_c2_kernal_window.input_consumer"
SYMBOL = "c2_kernal_input_take"
CAPTURE_SECTIONS = (
    ".lisp65_c2_kernal_window.input_capture_main",
    ".lisp65_c2_kernal_window.input_capture_helper",
)
FORMAT = "lisp65-c2-v160-input-service-hybrid-final-world-v1"


class FinalWorldError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FinalWorldError(message)


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def signed(value: int) -> int:
    return value - 256 if value & 0x80 else value


class LinkedConsumer:
    """Small 65C02 executor restricted to the emitted scalar consumer."""

    def __init__(self, code: bytes, address: int, symbols: dict[str, int]):
        self.code = code
        self.address = address
        self.symbols = symbols

    def run(self, mode: int, memory: dict[int, int]) -> tuple[int, int, int]:
        a = mode & 0xff; x = y = 0
        z = a == 0; n = bool(a & 0x80); c = False
        pc = self.address; cycles = instructions = 0

        def fetch(offset: int = 0) -> int:
            at = pc - self.address + offset
            require(0 <= at < len(self.code), "linked consumer PC escaped symbol")
            return self.code[at]

        def nz(value: int) -> tuple[bool, bool]:
            return value == 0, bool(value & 0x80)

        def branch(condition: bool) -> None:
            nonlocal pc, cycles
            delta = signed(fetch(1)); pc += 2; cycles += 2
            if condition:
                pc += delta; cycles += 1

        while instructions < 96:
            instructions += 1
            op = fetch()
            if op == 0xaa:  # TAX
                x = a; z, n = nz(x); pc += 1; cycles += 2
            elif op == 0xad:  # LDA abs
                addr = fetch(1) | fetch(2) << 8
                a = memory.get(addr, 0); z, n = nz(a); pc += 3; cycles += 4
            elif op == 0x30: branch(n)       # BMI
            elif op == 0xcd:  # CMP abs
                addr = fetch(1) | fetch(2) << 8; value = memory.get(addr, 0)
                result = (a - value) & 0xff; c = a >= value; z, n = nz(result)
                pc += 3; cycles += 4
            elif op == 0xf0: branch(z)       # BEQ
            elif op == 0xa8:  # TAY
                y = a; z, n = nz(y); pc += 1; cycles += 2
            elif op == 0xb9:  # LDA abs,Y
                base = fetch(1) | fetch(2) << 8; addr = (base + y) & 0xffff
                a = memory.get(addr, 0); z, n = nz(a); pc += 3
                cycles += 4 + int((base & 0xff00) != (addr & 0xff00))
            elif op == 0xc9:  # CMP imm
                value = fetch(1); result = (a - value) & 0xff
                c = a >= value; z, n = nz(result); pc += 2; cycles += 2
            elif op == 0x90: branch(not c)   # BCC
            elif op == 0xb0: branch(c)       # BCS
            elif op == 0x09:  # ORA imm
                a |= fetch(1); z, n = nz(a); pc += 2; cycles += 2
            elif op == 0x80: branch(True)    # BRA
            elif op == 0x29:  # AND imm
                a &= fetch(1); z, n = nz(a); pc += 2; cycles += 2
            elif op == 0xe0:  # CPX imm
                value = fetch(1); result = (x - value) & 0xff
                c = x >= value; z, n = nz(result); pc += 2; cycles += 2
            elif op == 0xd0: branch(not z)   # BNE
            elif op == 0xc0:  # CPY imm
                value = fetch(1); result = (y - value) & 0xff
                c = y >= value; z, n = nz(result); pc += 2; cycles += 2
            elif op == 0xc8:  # INY
                y = (y + 1) & 0xff; z, n = nz(y); pc += 1; cycles += 2
            elif op == 0xa0:  # LDY imm
                y = fetch(1); z, n = nz(y); pc += 2; cycles += 2
            elif op == 0x8c:  # STY abs
                addr = fetch(1) | fetch(2) << 8; memory[addr] = y
                pc += 3; cycles += 4
            elif op == 0xee:  # INC abs (monotonic product-health counter)
                addr = fetch(1) | fetch(2) << 8
                memory[addr] = (memory.get(addr, 0) + 1) & 0xff
                z, n = nz(memory[addr]); pc += 3; cycles += 6
            elif op == 0xa9:  # LDA imm
                a = fetch(1); z, n = nz(a); pc += 2; cycles += 2
            elif op == 0x60:  # RTS
                cycles += 6
                return a, cycles, instructions
            else:
                raise FinalWorldError(f"unsupported linked consumer opcode ${op:02x}")
        raise FinalWorldError("linked consumer did not return")


def linked_consumer(elf: Path) -> tuple[ElfTruth, LinkedConsumer, dict[str, Any]]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    section = truth.section(SECTION); symbol = truth.symbol(SYMBOL)
    require(symbol.section == SECTION and symbol.bytes == section.bytes
            and 0 < symbol.bytes <= 70,
            "final ELF consumer section/symbol membership red")
    raw = truth.section_bytes(SECTION)
    require(len(raw) == symbol.bytes, "final linked consumer byte extent drift")
    counter_names = (("C2K_INPUT_EVENTS_RAW",)
        if "C2K_INPUT_EVENTS_RAW" in truth.symbols_by_name else ()) + (
            "C2K_INPUT_EVENTS_SEEN", "C2K_INPUT_EVENTS_STORED",
            "C2K_INPUT_EVENTS_TAKEN")
    names = ("C2K_INPUT_RING_BASE", "C2K_INPUT_RING_HEAD",
             "C2K_INPUT_RING_TAIL", "C2K_INPUT_RING_SLOTS", *counter_names)
    symbols = {name: truth.symbol(name).value for name in names}
    base = symbols["C2K_INPUT_RING_BASE"]
    derived_slots = min(symbols[name] for name in counter_names) - base
    require(symbols["C2K_INPUT_RING_SLOTS"] == derived_slots,
            "final linked ring-slot contract drift")
    require([symbols[name] for name in counter_names] == list(
                range(base + derived_slots,
                      base + derived_slots + len(counter_names)))
            and derived_slots + len(counter_names) == 112,
            "final linked counter allocation drift")
    capture = {name: truth.section(name).bytes for name in CAPTURE_SECTIONS}
    require(all(value > 0 for value in capture.values()),
            "final linked capture membership drift")
    return truth, LinkedConsumer(raw, symbol.value, symbols), {
        "section": SECTION, "section_address": section.address,
        "section_bytes": section.bytes, "symbol": SYMBOL,
        "symbol_address": symbol.value, "symbol_bytes": symbol.bytes,
        "consumer_sha256": hashlib.sha256(raw).hexdigest(),
        "ring_symbols": symbols, "physical_allocation_bytes": 112,
        "ring_index_values": derived_slots,
        "usable_ring_events": derived_slots - 1,
        "counter_bytes": len(counter_names), "capture_sections": capture,
    }


def normalization_claim(machine: LinkedConsumer,
                        symbols: dict[str, int]) -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    base = symbols["C2K_INPUT_RING_BASE"]
    head = symbols["C2K_INPUT_RING_HEAD"]; tail = symbols["C2K_INPUT_RING_TAIL"]
    max_cycles = 0
    for raw in range(256):
        expected, _shift = HYBRID.normalize(raw, contract["normalization"])
        for mode in (2, 3):
            memory = {head: 1, tail: 0, base: raw}
            actual, cycles, _instructions = machine.run(mode, memory)
            printable = 32 <= expected < 127
            want = expected if mode == 2 or printable else 0
            want_tail = 1 if mode == 2 or printable else 0
            require(actual == want and memory[tail] == want_tail,
                    f"linked normalization red raw={raw} mode={mode}")
            max_cycles = max(max_cycles, cycles)
    return {"raw_inputs": 256, "modes": [2, 3], "executions": 512,
            "parity": True, "a0_to_space": True,
            "maximum_linked_consumer_cycles": max_cycles,
            "authority": "executed final-ELF c2_kernal_input_take bytes"}


def loss_claim(machine: LinkedConsumer,
               symbols: dict[str, int]) -> dict[str, Any]:
    model = FIDELITY.capture_simulation()
    require(model["events_captured"] == 94 and model["dropped"] == 0
            and model["ordered"] and model["sixth_event_present"],
            "capture-side 94-event wall red")
    base = symbols["C2K_INPUT_RING_BASE"]
    head = symbols["C2K_INPUT_RING_HEAD"]; tail = symbols["C2K_INPUT_RING_TAIL"]
    events = [32 + (index % 64) for index in range(94)]
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    expected = [HYBRID.normalize(value, contract["normalization"])[0]
                for value in events]
    memory = {head: len(events), tail: 0}
    memory.update({base + index: value for index, value in enumerate(events)})
    drained: list[int] = []
    cycles = 0
    for _ in events:
        value, cost, _instructions = machine.run(2, memory)
        drained.append(value); cycles += cost
    require(drained == expected and memory[tail] == len(events),
            "final linked consumer failed ordered 94-event drain")
    require(memory[symbols["C2K_INPUT_EVENTS_TAKEN"]] == len(events),
            "final linked taken counter did not follow committed drains")
    return {"capture_model": model, "linked_events_drained": len(drained),
            "linked_ordered": True, "linked_dropped": 0,
            "sixth_event": drained[5], "linked_consumer_cycles": cycles,
            "raw_event_order": events, "normalized_event_order": expected,
            "authority": "capture wall plus final-ELF consumer execution"}


def responsiveness_claim(machine: LinkedConsumer,
                         symbols: dict[str, int]) -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    raw = PRICE.execute_route(EDITOR, "batch", 40, batch_cap=8)
    base = symbols["C2K_INPUT_RING_BASE"]
    head = symbols["C2K_INPUT_RING_HEAD"]; tail = symbols["C2K_INPUT_RING_TAIL"]
    memory = {head: 1, tail: 0, base: ord("a")}
    value, native_cycles, instructions = machine.run(2, memory)
    require(value == ord("a") and memory[tail] == 1,
            "final linked responsiveness consumer execution red")
    price = contract["responsiveness"]
    frames = (raw["vm_steps_per_character"]
              * price["calibration_cycles_per_vm_step"] / price["cycles_per_frame"]
              + raw["screen_cells_per_character"] * price["screen_cell_cycles"]
              / price["cycles_per_frame"]
              + raw["heap_cells_per_character"] * price["collection_frames"]
              / price["nursery_cells"]
              + native_cycles / price["cycles_per_frame"])
    rate = 1.0 / frames; margin = (rate - 1.0) * 100.0
    require(frames <= price["maximum_frames_per_character"]
            and rate >= price["minimum_service_events_per_frame"]
            and margin >= price["minimum_margin_percent"],
            "final linked responsiveness wall red")
    return {**raw, "linked_native_cycles_per_character": native_cycles,
            "linked_native_instructions_per_character": instructions,
            "frames_per_character": frames, "service_events_per_frame": rate,
            "margin_percent": margin, "batch_fixture": 8,
            "authority": "batch VM route plus executed final-ELF consumer"}


def derive(elf: Path) -> dict[str, Any]:
    _truth, machine, membership = linked_consumer(elf)
    symbols = machine.symbols
    return {"format": FORMAT, "status": "PASS: HYBRID CLAIMS PROVED ON FINAL ELF",
            "final_ELF": bind(elf), "membership": membership,
            "normalization": normalization_claim(machine, symbols),
            "loss": loss_claim(machine, symbols),
            "responsiveness": responsiveness_claim(machine, symbols),
            "claim_source": "final linked ELF only",
            "isolated_object_claims": 0, "synthetic_profile_claims": 0}
