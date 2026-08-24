#!/usr/bin/env python3
"""Gate the direct boot-refill reader and total linked selector population."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_boot_refill_dma_closure as OLD  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


GENERATOR = ROOT / "tools/host-lisp/c2_lite_v6_product_probe.py"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
STATUS = "PASS: BOOT REFILL BYPASSES RETURN SELECTOR IN FINAL ELF"

# Preserve the predecessor implementations before a successor card installs
# these functions into the inherited real-consumer stack.
OLD_GENERATED_GATE = OLD.generated_source_gate
OLD_LINKED_MODEL = OLD.linked_read_model
OLD_VALIDATE_FINAL = OLD.validate_final
OLD_FINAL_MUTATIONS = OLD.final_mutations


class BypassError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise BypassError(message)


def replacement_body(source: str) -> str:
    marker = 'replace_c_function(runtime_source, "c2_product_entry_read", r\'\'\''
    require(source.count(marker) == 1, "boot-refill generator owner drift")
    return source.split(marker, 1)[1].split("''')", 1)[0]


def generated_body(source: str) -> str:
    marker = "uint8_t c2_product_entry_read("
    require(source.count(marker) == 1, "emitted boot-refill owner drift")
    return source.split(marker, 1)[1].split("\n}\n", 1)[0]


def validate_source_body(body: str) -> None:
    require("if (!c2_map_cpu_read(" in body
            and "c2_facade_map_cpu_read" not in body
            and "c2_facade_runtime_overlay_exec" not in body
            and "c2_dma_copy(" not in body
            and "return 1;" in body,
            "boot refill is not direct MAP-CPU fail-propagating")


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = (GENERATOR.read_text(encoding="utf-8")
              if source_override is None else source_override)
    body = replacement_body(source)
    validate_source_body(body)
    return {"status": "PASS: GENERATOR OWNS DIRECT BOOT MAP-CPU CALL",
            "owner": "c2_lite_v6_product_probe.generate_sources",
            "generated_function": "c2_product_entry_read",
            "transport": "c2_map_cpu_read", "selector_dependency": False,
            "failure_propagated": True}


def source_mutations() -> list[str]:
    source = GENERATOR.read_text(encoding="utf-8")
    cases = {
        "restore-return-selector-alias": source.replace(
            "    if (!c2_map_cpu_read(\n",
            "    extern uint8_t c2_facade_map_cpu_read(uint32_t, uint8_t *, uint16_t)\n"
            "        __asm__(\"c2_facade_runtime_overlay_exec\");\n"
            "    if (!c2_facade_map_cpu_read(\n", 1),
        "discard-direct-reader-failure": source.replace(
            "    if (!c2_map_cpu_read(\n"
            "            ((uint32_t)2u << 16) + (uint16_t)(c2_u16(row + 2) + relative),\n"
            "            destination, length)) return 0;",
            "    (void)c2_map_cpu_read(\n"
            "            ((uint32_t)2u << 16) + (uint16_t)(c2_u16(row + 2) + relative),\n"
            "            destination, length);", 1),
    }
    rejected: list[str] = []
    for name, mutant in cases.items():
        try:
            source_gate(mutant)
        except BypassError:
            rejected.append(name)
    require(rejected == list(cases), "selector-bypass source mutation survived")
    return rejected


def generated_source_gate(path: Path) -> dict[str, Any]:
    body = generated_body(path.read_text(encoding="utf-8"))
    validate_source_body(body)
    return {"status": "PASS: EMITTED BOOT REFILL CALLS MAP-CPU DIRECTLY",
            "emitted_source": OLD.bind(path), "owner": "c2_product_entry_read",
            "transport": "c2_map_cpu_read", "selector_dependency": False,
            "failure_propagated": True, "raw_read_edges": 0}


def owner_at(truth: ElfTruth, section_name: str, address: int) -> str:
    matches = [symbol for symbol in truth.symbols
               if symbol.section == section_name
               and symbol.symbol_type == "Function" and symbol.bytes > 0
               and symbol.value <= address < symbol.value + symbol.bytes]
    require(len(matches) == 1, f"selector caller owner drift at 0x{address:04x}")
    return matches[0].name


def absolute_transfers(truth: ElfTruth, target: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for relocation in truth.relocations:
        identity = truth.relocation_target_identity(relocation)
        if (identity.get("section"), identity.get("resolved_value")) != \
                (target.section, target.value):
            continue
        section = truth.section(relocation.source_section)
        raw = truth.section_bytes(section.name)
        address = relocation.offset - 1
        offset = address - section.address
        if not 0 <= offset < len(raw) or raw[offset] not in (0x20, 0x4C):
            continue
        kind = "JSR" if raw[offset] == 0x20 else "JMP"
        result.append({"kind": kind, "section": section.name,
            "owner": owner_at(truth, section.name, address),
            "address": f"0x{address:04x}",
            "target_identity": [target.section, target.value],
            "hardware_pushed_return": (
                f"0x{address + 2:04x}" if kind == "JSR" else None)})
    return sorted(result, key=lambda row: int(row["address"], 16))


def function_edges(truth: ElfTruth, owner: str, target: Any) -> int:
    symbol = truth.symbol(owner)
    section = truth.section(symbol.section)
    raw = truth.section_bytes(symbol.section)
    result = 0
    for relocation in truth.relocations:
        identity = truth.relocation_target_identity(relocation)
        pc = relocation.offset - 1
        at = pc - section.address
        if (relocation.source_section == symbol.section
                and symbol.value <= pc < symbol.value + symbol.bytes
                and (identity.get("section"), identity.get("resolved_value")) ==
                    (target.section, target.value)
                and 0 <= at < len(raw) and raw[at] == 0x20):
            result += 1
    return result


def selector_semantics(truth: ElfTruth) -> dict[str, Any]:
    selector = truth.symbol("c2_map_cpu_selector")
    section = truth.section(selector.section)
    raw = truth.section_bytes(selector.section)[
        selector.value - section.address:selector.value - section.address + selector.bytes]
    shape = bytearray(raw)
    for index in (7, 14, 20, 27, 33, 34, 38, 39):
        shape[index] = 0
    require(bytes(shape).hex() == (
        "48dababd0401c900d009bd0301c900f012800bc900d007bd0301c900f005"
        "fa684c0000fa684c0000"), "selector semantic shape drift")
    admitted = ((raw[7] << 8) | raw[14], (raw[20] << 8) | raw[27])
    fallback = raw[33] | raw[34] << 8
    reader = raw[38] | raw[39] << 8
    require(fallback == truth.symbol("vm_runtime_overlay_exec").value
            and reader == truth.symbol("c2_map_cpu_read").value,
            "selector sink drift")
    vector = truth.symbol("c2_facade_runtime_overlay_exec")
    callers = absolute_transfers(truth, vector)
    evaluated = []
    for row in callers:
        pushed = (int(row["hardware_pushed_return"], 16)
                  if row["hardware_pushed_return"] is not None else None)
        selected = reader if pushed in admitted else fallback
        evaluated.append({**row, "admitted": pushed in admitted,
                          "selected_sink": ("c2_map_cpu_read"
                            if selected == reader else "vm_runtime_overlay_exec"),
                          "selected_address": f"0x{selected:04x}"})
    return {"selector": {"address": f"0x{selector.value:04x}",
                          "bytes": selector.bytes},
            "fixed_vector": f"0x{vector.value:04x}",
            "admitted_hardware_pushed_returns": [
                f"0x{value:04x}" for value in admitted],
            "actual_callers": evaluated,
            "fallback_sink": "vm_runtime_overlay_exec",
            "reader_sink": "c2_map_cpu_read"}


def validate_selector(value: dict[str, Any]) -> None:
    callers = value.get("actual_callers", [])
    actual = [row["hardware_pushed_return"] for row in callers
              if row.get("kind") == "JSR"]
    admitted = value.get("admitted_hardware_pushed_returns", [])
    require(callers and all(row.get("kind") == "JSR" for row in callers)
            and len(actual) == len(set(actual))
            and set(actual) == set(admitted)
            and all(row.get("admitted") is True
                    and row.get("selected_sink") == "c2_map_cpu_read"
                    for row in callers),
            "final selector population or selected sink drift")


def linked_read_model(elf: Path) -> dict[str, Any]:
    value = OLD_LINKED_MODEL(elf)
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    reader = truth.symbol("c2_map_cpu_read")
    vector = truth.symbol("c2_facade_runtime_overlay_exec")
    direct = function_edges(truth, "c2_product_entry_read", reader)
    indirect = function_edges(truth, "c2_product_entry_read", vector)
    selector = selector_semantics(truth)
    selector["violations"] = []
    value["product_entry"].update({"direct_MAP_CPU_edges": direct,
                                    "selector_edges": indirect})
    value["selector_totality"] = selector
    value["selector_retirement"] = {
        "current_fallback_callers": sum(
            row["selected_sink"] == "vm_runtime_overlay_exec"
            for row in selector["actual_callers"]),
        "current_reader_callers": sum(
            row["selected_sink"] == "c2_map_cpu_read"
            for row in selector["actual_callers"]),
        "selector_body_bytes_reclaimable": truth.symbol(
            "c2_map_cpu_selector").bytes,
        "current_linked_reason_to_retain_fallback": False,
        "decision": ("no current linked caller needs the fallback; retirement is priceable "
                     "as a separate ABI-reviewed change, not implemented by this card"),
    }
    return value


def validate_final(value: dict[str, Any]) -> None:
    OLD_VALIDATE_FINAL(value)
    entry = value.get("product_entry", {})
    require(entry.get("direct_MAP_CPU_edges") == 1
            and entry.get("selector_edges") == 0,
            "boot refill still depends on return selector")
    validate_selector(value.get("selector_totality", {}))
    retirement = value.get("selector_retirement", {})
    require(retirement.get("current_fallback_callers") == 0
            and retirement.get("current_reader_callers") == 2
            and retirement.get("selector_body_bytes_reclaimable") == 40
            and retirement.get("current_linked_reason_to_retain_fallback") is False,
            "selector retirement decision drift")


def final_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-boot-selector-dependency": lambda x: x["product_entry"].update(
            direct_MAP_CPU_edges=0, selector_edges=1),
        "add-unregistered-selector-caller": lambda x: x["selector_totality"]
            ["actual_callers"].append({"kind": "JSR", "owner": "new_caller",
                "address": "0xa000", "hardware_pushed_return": "0xa002",
                "admitted": False, "selected_sink": "vm_runtime_overlay_exec",
                "selected_address": "0x0000", "section": ".text"}),
        "divert-registered-caller": lambda x: x["selector_totality"]
            ["actual_callers"][0].update(selected_sink="vm_runtime_overlay_exec"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate_final(trial)
        except (BypassError, OLD.ClosureError):
            rejected.append(name)
    require(rejected == list(cases), "selector-bypass final mutation survived")
    return [*OLD_FINAL_MUTATIONS(value), *rejected]


def install_inherited_gate() -> None:
    OLD.generated_source_gate = generated_source_gate
    OLD.linked_read_model = linked_read_model
    OLD.validate_final = validate_final
    OLD.final_mutations = final_mutations


def selftest() -> None:
    require(len(source_mutations()) == 2, "selector-bypass source selftest drift")
    print("v1.6 boot refill selector bypass: SELFTEST PASS source=2")


if __name__ == "__main__":
    try:
        selftest()
    except (BypassError, OLD.ClosureError, OSError, KeyError, ValueError,
            json.JSONDecodeError) as error:
        print(f"v1.6 boot refill selector bypass: FAIL: {error}", file=sys.stderr)
        raise SystemExit(2)
