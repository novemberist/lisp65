#!/usr/bin/env python3
"""Attribute the recovery-sanitization early-boot First Red from frozen bytes.

The final linked call graph contains a return-sensitive facade selector.  A
source-level call to that facade is therefore not evidence of which transport
the caller consumes.  This attribution enumerates every caller in the final
ELF and executes the selector decision on each hardware-pushed return value.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ELF = ROOT / (
    "build/c2.3/v1.6-recovery-sanitization-library-replacement-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
CAPTURE = ROOT / (
    "build/c2.3/v1.6-recovery-sanitization-media/"
    "device-first-red-20260824/capture.json")
CAPTURE_DRIVER = ROOT / (
    "tools/host-lisp/c2_v160_recovery_sanitization_seam_first_red_capture.py")
MANIFEST = ROOT / (
    "build/c2.3/v1.6-recovery-sanitization-library-replacement-card/"
    "static-plane/narrow-static/stdlib-p0.manifest.json")
BLOB = MANIFEST.with_name("stdlib-p0.blob.bin")
GENERATED = ELF.parent / "generated-product-sources/c2_product_runtime.c"
GENERATOR = ROOT / "tools/host-lisp/c2_lite_v6_product_probe.py"
SELECTOR_SOURCE = ROOT / "src/optional/c2_map_cpu_read.s"
FACADE_SOURCE = ROOT / "src/c2_kernal_facade_reopen.s"
OLD_FINAL_GATE = ROOT / "tools/host-lisp/c2_v160_boot_refill_dma_closure.py"
OLD_SELECTOR_GATE = ROOT / "tools/host-lisp/c2_v21_candidate_derived_local_return.py"
REPLAY_DRIVER = ROOT / "tools/host-lisp/c2_v160_boot_path_two_layer_attribution.py"
OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-recovery-sanitization-seam-first-red-attribution.json")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-c2.3-v1.6-recovery-sanitization-seam-first-red-attribution-v1"
EVIDENCE_SEAL = "64b99b59"

EXPECTED = {
    "ELF": "93201ddea4dbbd58f6905bc93abcd49cc92b4905baffedb873743016826e4945",
    "capture": "53ccaa7db73c93a146dda2a7041ae8e56ff25848b7a9b92c9788dc292f34bd36",
    "capture_driver": "cc7e85f2b8998f9c12da284abaf4dce80dd1c570aa6ecb80ece06792a7e09c83",
    "manifest": "04f3c93d00a72cf2725064223feb53949327249a534c0a8045e5c01a66a8d858",
    "blob": "bb8b95eb4742e91b5182aba882186607939c85ac963e45572936cb6154f949c1",
    "generated_source": "05603996719acf64ce2f379bd340817ffdfab59c921078690737628f36abab54",
    "generator": "f70b84937c0751a1b1206d2cc289c2dc0207fa810c22580d3990e8f0973e06c4",
    "selector_source": "23ac439dbae2655a20a3c858717aeb924ecba3d817ef6a83c43ffe166ee063ef",
    "facade_source": "873891701fc955461d80725ecdcd3533b1b56faedd1d0341a4fbb4005b47958d",
    "old_final_gate": "affb4cc729b4c56a81b5e5a804320a29a4eba5c2a4d97ddefd5afbf5f609aba0",
    "old_selector_gate": "9536a4c7fc2ae7d7e5a61150923649180479260658c99ff18d71ae016584c132",
    "replay_driver": "78ab374e2942043e11210dc7764260f3ad9add645154ea2cc62cfaab500387c5",
}


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def sealed_bytes(path: Path) -> bytes:
    name = path.relative_to(ROOT).as_posix()
    return subprocess.run(["git", "show", f"{EVIDENCE_SEAL}:{name}"],
                          cwd=ROOT, check=True,
                          stdout=subprocess.PIPE).stdout


def bind_sealed(path: Path) -> dict[str, Any]:
    raw = sealed_bytes(path)
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def row(capture: dict[str, Any], name: str) -> bytes:
    matches = [item for item in capture["reads"] if item["name"] == name]
    require(len(matches) == 1, f"capture row identity drift: {name}")
    raw = bytes.fromhex(matches[0]["observed_hex"])
    require(len(raw) == int(matches[0]["bytes"]),
            f"capture row length drift: {name}")
    return raw


def u16(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset:offset + 2], "little")


def replay_module() -> Any:
    spec = importlib.util.spec_from_file_location("boot_replay", REPLAY_DRIVER)
    require(spec is not None and spec.loader is not None,
            "boot replay driver unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def owner_at(truth: ElfTruth, section_name: str, address: int) -> str:
    matches = [symbol for symbol in truth.symbols
               if symbol.section == section_name
               and symbol.symbol_type == "Function" and symbol.bytes > 0
               and symbol.value <= address < symbol.value + symbol.bytes]
    require(len(matches) == 1, f"call owner drift at 0x{address:04x}: {matches}")
    return matches[0].name


def facade_callers(truth: ElfTruth, vector: int) -> list[dict[str, Any]]:
    needle = bytes((0x20, vector & 0xFF, vector >> 8))
    result: list[dict[str, Any]] = []
    for section in truth.sections:
        if "SHF_EXECINSTR" not in section.flags or not section.bytes:
            continue
        raw = truth.section_bytes(section.name)
        start = 0
        while True:
            offset = raw.find(needle, start)
            if offset < 0:
                break
            address = section.address + offset
            result.append({
                "section": section.name,
                "owner": owner_at(truth, section.name, address),
                "call_address": f"0x{address:04x}",
                "hardware_pushed_return": f"0x{address + 2:04x}",
            })
            start = offset + 1
    return sorted(result, key=lambda item: int(item["call_address"], 16))


def selector_model(truth: ElfTruth, callers: list[dict[str, Any]]) -> dict[str, Any]:
    selector = truth.symbol("c2_map_cpu_selector")
    section = truth.section(selector.section)
    raw = truth.section_bytes(selector.section)[
        selector.value - section.address:selector.value - section.address + selector.bytes]
    require(raw.hex() == (
        "48dababd0401c9e3d009bd0301c928f012800bc9e8d007bd0301c94df005"
        "fa684c252afa684ce522"), "selector final bytes drift")
    admitted = ((raw[7] << 8) | raw[14], (raw[20] << 8) | raw[27])
    runtime_sink = raw[33] | raw[34] << 8
    reader_sink = raw[38] | raw[39] << 8
    require(admitted == (0xE328, 0xE84D)
            and runtime_sink == truth.symbol("vm_runtime_overlay_exec").value
            and reader_sink == truth.symbol("c2_map_cpu_read").value,
            "selector operand/sink drift")
    evaluated = []
    for caller in callers:
        pushed = int(caller["hardware_pushed_return"], 16)
        selected = reader_sink if pushed in admitted else runtime_sink
        evaluated.append({**caller, "admitted": pushed in admitted,
                          "selected_sink": ("c2_map_cpu_read" if selected == reader_sink
                                            else "vm_runtime_overlay_exec"),
                          "selected_address": f"0x{selected:04x}"})
    return {
        "address": f"0x{selector.value:04x}", "bytes": selector.bytes,
        "machine_bytes": raw.hex(),
        "admitted_hardware_pushed_returns": [f"0x{value:04x}" for value in admitted],
        "reader_sink": {"name": "c2_map_cpu_read",
                        "address": f"0x{reader_sink:04x}"},
        "fallback_sink": {"name": "vm_runtime_overlay_exec",
                          "address": f"0x{runtime_sink:04x}"},
        "evaluated_callers": evaluated,
    }


def validate_claim(value: dict[str, Any]) -> None:
    selector = value["linked_selector"]
    callers = selector["evaluated_callers"]
    boot_rows = [row for row in callers
                 if row["owner"] == "c2_product_entry_read"]
    require(len(boot_rows) == 1, "boot selector-caller population drift")
    boot = boot_rows[0]
    require(len(callers) == 3
            and [row["hardware_pushed_return"] for row in callers]
                == ["0xa10b", "0xe328", "0xe84d"]
            and boot["admitted"] is False
            and boot["selected_sink"] == "vm_runtime_overlay_exec"
            and value["source_bound_expectation"]["transport"] == "c2_map_cpu_read"
            and value["device_stop"]["witness_armed"] is False,
            "path-sensitive selector attribution drift")


def derive() -> dict[str, Any]:
    paths = {
        "ELF": ELF, "capture": CAPTURE, "capture_driver": CAPTURE_DRIVER,
        "manifest": MANIFEST, "blob": BLOB, "generated_source": GENERATED,
        "generator": GENERATOR, "selector_source": SELECTOR_SOURCE,
        "facade_source": FACADE_SOURCE, "old_final_gate": OLD_FINAL_GATE,
        "old_selector_gate": OLD_SELECTOR_GATE, "replay_driver": REPLAY_DRIVER,
    }
    inputs = {name: (bind_sealed(path) if name == "generator" else bind(path))
              for name, path in paths.items()}
    require({name: row["sha256"] for name, row in inputs.items()} == EXPECTED,
            "recovery-sanitization First-Red attribution identity drift")

    capture = load(CAPTURE)
    require(capture["tuple"] == {
        "A": "0x02", "B": "0x00", "MAPH": "0x8000", "MAPL": "0x0000",
        "PC": "0xe096", "SP": "0x013e", "X": "0x3e", "Y": "0xf6",
        "Z": "0x00",
        "suffix": "4C96E0  00     24 ..E..I.. ...P 15 -  00 - .....lh.",
    }, "stopped tuple drift")
    require(capture["discipline"] == {
        "CPU_left_stopped": True, "D2_D5_executed": False,
        "raw_first": True, "resets": 0, "resumes": 0, "runs": 0,
        "stops": 1, "tuple_before_memory": True,
    }, "read-only discipline drift")
    zp_stack = row(capture, "bank0-zp-stack")
    trace_origin = row(capture, "refill-trace-origin")
    trace_slots = row(capture, "refill-trace-slots")
    require(trace_origin == bytes(5) and trace_slots == bytes(68),
            "refill witness unexpectedly armed")
    sp = 0x3E
    saved = {
        "Z": zp_stack[0x100 + sp + 1], "Y": zp_stack[0x100 + sp + 2],
        "X": zp_stack[0x100 + sp + 3], "A": zp_stack[0x100 + sp + 4],
        "P": zp_stack[0x100 + sp + 5],
        "continuation": u16(zp_stack, 0x100 + sp + 6),
    }
    require(saved == {"Z": 0, "Y": 3, "X": 0x45, "A": 1,
                      "P": 0x30, "continuation": 0x004E},
            "software-BRK frame drift")
    require(u16(zp_stack, 0x1D9) == 0x451E
            and u16(zp_stack, 0x1DF) == 0xACB9
            and u16(zp_stack, 0x1E5) == 0xA70A,
            "boot native-stack chain drift")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    expected_symbols = {
        "c2_product_entry_read": (0x9FAC, 743),
        "c2_facade_runtime_overlay_exec": (0xB5EB, 0),
        "c2_map_cpu_selector": (0x23A2, 40),
        "c2_map_cpu_read": (0x22E5, 189),
        "vm_runtime_overlay_exec": (0x2A25, 38),
        "c2_stream_c2d_read": (0xE2DD, 85),
        "c2_stream_shelf_read": (0xE79D, 194),
    }
    observed_symbols = {name: (truth.symbol(name).value, truth.symbol(name).bytes)
                        for name in expected_symbols}
    require(observed_symbols == expected_symbols, "linked identity drift")
    callers = facade_callers(truth, 0xB5EB)
    selector = selector_model(truth, callers)

    generated = GENERATED.read_text(encoding="utf-8")
    body = generated.split("uint8_t c2_product_entry_read(", 1)[1].split("\n}\n", 1)[0]
    require('extern uint8_t c2_facade_map_cpu_read' in body
            and '__asm__("c2_facade_runtime_overlay_exec")' in body
            and "if (!c2_facade_map_cpu_read(" in body,
            "generated source expectation drift")
    generator = sealed_bytes(GENERATOR).decode()
    require(generator.count('__asm__("c2_facade_runtime_overlay_exec")') >= 1
            and 'replace_c_function(runtime_source, "c2_product_entry_read"' in generator,
            "upstream generator ownership drift")

    replay = replay_module().replay(MANIFEST, BLOB)
    require(replay["entry_ordinal"] == 239 and replay["entry_bytes"] == 145
            and replay["steps"] == 8693 and replay["result"] == "nil"
            and replay["first_type_error"] is None,
            "exact packed banner host replay drift")

    final_gate_source = OLD_FINAL_GATE.read_text(encoding="utf-8")
    selector_gate_source = OLD_SELECTOR_GATE.read_text(encoding="utf-8")
    require('"MAP_CPU_edges": (product.count' in final_gate_source
            and "CPU_READ_FACADE" in final_gate_source
            and "for name, spec in OLD.IDENTITIES.items()" in selector_gate_source,
            "historical gate blind-spot shape drift")

    value = {
        "format": FORMAT,
        "status": "ATTRIBUTED: THIRD FACADE CALLER FALLS THROUGH TO WRONG OVERLAY SINK",
        "recorded_on": "2026-08-24", "inputs": inputs,
        "contact": {"kind": "one authorized raw-first stopped-state read",
                    "stops": 1, "resumes": 0, "runs": 0, "resets": 0,
                    "bytes_read": 667, "CPU_left_stopped": True},
        "device_stop": {
            "fail_closed_PC": "0xe096", "software_BRK": True,
            "BRK_address": "0x004c", "saved_continuation": "0x004e",
            "vm_status": "VM_TYPEERROR (3)",
            "native_call_chain": [
                {"raw_return": "0x451e", "resume": "0x451f",
                 "owner": "vm_run_dir", "callee": "vm_run"},
                {"raw_return": "0xacb9", "resume": "0xacba",
                 "owner": "repl", "callee": "vm_run_dir"},
                {"raw_return": "0xa70a", "resume": "0xa70b",
                 "owner": "main", "callee": "repl"},
            ],
            "witness_origin": "5/5 zero", "witness_slots": "68/68 zero",
            "witness_armed": False,
            "decision": "failure is before Comfort/refill witness activation",
        },
        "logical_object_replay": replay,
        "source_bound_expectation": {
            "owner": "c2_product_entry_read",
            "declared_C_name": "c2_facade_map_cpu_read",
            "ASM_alias": "c2_facade_runtime_overlay_exec",
            "transport": "c2_map_cpu_read",
            "failure_propagated": True,
            "generator_is_upstream_owner": True,
        },
        "linked_selector": selector,
        "mechanical_decision": {
            "source_binding_consumed": False,
            "boot_call": "JSR $B5EB at $A109",
            "boot_hardware_pushed_return": "0xa10b",
            "selector_admits": ["0xe328", "0xe84d"],
            "actual_sink": "vm_runtime_overlay_exec at $2A25",
            "intended_sink": "c2_map_cpu_read at $22E5",
            "class": "bound-not-consumed / return-identity selector population",
            "root_cause": ("the fixed facade selector retained its two historical caller "
                           "identities after c2_product_entry_read became a third caller"),
            "downstream_observation": ("the wrong overlay-family consumer receives the boot-"
                                       "refill argument tuple; the frozen device state then "
                                       "records VM_TYPEERROR and a low-RAM software BRK"),
            "exact_low_RAM_corruption_step": "not required and not claimed",
        },
        "gate_blind_spots": {
            "final_DMA_closure": ("counted a call to the facade as a MAP-CPU edge without "
                                  "executing the return-sensitive selector"),
            "local_return_gate": ("proved the two registered historical identities but did "
                                  "not derive the complete caller population of $B5EB"),
            "permanent_rule": ("derive every final-ELF caller of a return-sensitive vector "
                               "and execute selector semantics on its actual hardware-pushed "
                               "return identity; registration is not consumption"),
        },
        "next_step": {
            "authorization": "not granted by this attribution",
            "preferred_price_candidate": ("make ordinary-text c2_product_entry_read call "
                                          "c2_map_cpu_read directly; retain the selector only "
                                          "for the two fixed-window callers"),
            "alternative": "admit the third linked return identity in the selector",
            "required_owner": "upstream generator plus materialized source",
            "required_gate": ("all $B5EB callers resolve to their declared sink in final "
                              "ELF; the zero-unsafe-DMA claim consumes that result"),
        },
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
                                 "cards_consumed": 0, "media_builds": 0,
                                 "additional_device_contacts": 0},
        "claim_limit": ("Host-only attribution after one authorized read. No fix, card, "
                        "build, medium, resume or further device contact is authorized."),
    }
    validate_claim(value)
    return value


def selftest() -> None:
    value = derive()
    cases = {
        "hide-third-caller": lambda x: x["linked_selector"]["evaluated_callers"].pop(0),
        "pretend-third-caller-admitted": lambda x: x["linked_selector"]
            ["evaluated_callers"][0].update(admitted=True,
                                             selected_sink="c2_map_cpu_read"),
        "count-binding-as-consumption": lambda x: x["mechanical_decision"].update(
            source_binding_consumed=True),
    }
    rejected = []
    for name, mutate in cases.items():
        clone = json.loads(json.dumps(value))
        mutate(clone)
        try:
            validate_claim(clone)
            require(clone["mechanical_decision"]["source_binding_consumed"] is False,
                    "source binding accepted as consumption")
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "path-sensitive attribution mutation survived")
    print(f"v1.6 recovery-seam First-Red attribution: SELFTEST PASS "
          f"mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    if action == "selftest":
        selftest()
        return 0
    value = derive()
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if action == "write":
        require(not OUT.exists(), "attribution receipt already exists")
        OUT.write_text(encoded, encoding="utf-8")
    else:
        require(OUT.is_file() and OUT.read_text(encoding="utf-8") == encoded,
                "recovery-seam First-Red attribution receipt drift")
    print("v1.6 recovery-seam First-Red attribution: PASS "
          "boot-return=$a10b selected=vm_runtime_overlay_exec")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"v1.6 recovery-seam First-Red attribution: FAIL: {error}",
              file=sys.stderr)
        raise SystemExit(1)
