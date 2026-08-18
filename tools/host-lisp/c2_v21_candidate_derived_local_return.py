#!/usr/bin/env python3
"""Candidate-derived local-return identity checker.

The historical checker remains immutable for its historical worlds.  This
successor gets the reader size and ordinary-text reserve from the bound
product-liveness contract, while retaining every semantic selector,
ownership, packed-image, fixed-vector and MAP-window check.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"

from elf_truth import ElfTruth
import c2_v21_local_return_identity_card as OLD
import c2_v21_product_loading_liveness as LIVE


LIVENESS = LIVE.RECEIPT
DRIVER = Path(__file__).resolve()


class CandidateCheckerError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CandidateCheckerError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def placement_contract() -> dict[str, Any]:
    persisted = load(LIVENESS)
    current = LIVE.derive()
    current["source_mutations"] = LIVE.source_mutations()
    require(persisted == current,
            "candidate-derived checker does not consume current liveness contract")
    implementation = persisted["implementation"]
    capacity = persisted["capacity"]
    return {
        "authority": LIVENESS.relative_to(ROOT).as_posix(),
        "reader_address": 0x2277,
        "reader_bytes": implementation["progress_reader_bytes"],
        "ordinary_reserve_bytes": capacity["projected_free_bytes"],
        "text_end_exclusive": int(capacity["projected_text_end_exclusive"], 16),
        "facade_address": int(capacity["mapped_far_facade"], 16),
        "delta_bytes": implementation["delta_bytes"],
    }


def validate_linked(value: dict[str, Any], contract: dict[str, Any]) -> None:
    identities = value["selector"]["real_call_identities"]
    require(
        value["reader"]["bytes"] == contract["reader_bytes"]
        and value["ordinary"]["reserve_bytes"] ==
            contract["ordinary_reserve_bytes"]
        and value["ordinary"]["text_end_exclusive"] ==
            f"0x{contract['text_end_exclusive']:04x}"
        and value["return_labels"]["global_non_entries"] == 0
        and value["selector"]["identity_depends_on_global_return_label"] is False
        and identities["c2d"]["entry_offset"] == 0x4B
        and identities["shelf"]["entry_offset"] == 0xB0
        and identities["selector_operands_match"] is True
        and value["ownership"]["violations"] == [],
        "candidate-derived linked local-return identity drift")


def linked_gate(elf: Path, manifest_path: Path) -> dict[str, Any]:
    contract = placement_contract()
    truth = ElfTruth.read(elf, llvm_readobj=OLD.LLVM / "llvm-readobj",
                          include_section_data=True)
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    fixed = truth.section(".lisp65_c2_host_facade")
    cold = truth.section(".lisp65_rt_c2emit_final_crc")
    reader = truth.symbol("c2_map_cpu_read")
    selector = truth.symbol("c2_map_cpu_selector")
    helper = truth.symbol("c2e_w32")
    vector = truth.symbol("c2_facade_runtime_overlay_exec")
    shelf = truth.symbol("c2_stream_shelf_read")
    c2d = truth.symbol("c2_stream_c2d_read")
    reserve = facade.address - (text.address + text.bytes)
    require(
        reader.value == contract["reader_address"]
        and reader.bytes == contract["reader_bytes"]
        and text.address + text.bytes == contract["text_end_exclusive"]
        and facade.address == contract["facade_address"]
        and reserve == contract["ordinary_reserve_bytes"]
        and selector.value == reader.value + reader.bytes
        and selector.bytes == 40
        and helper.section == cold.name and helper.bytes == 63
        and cold.bytes == 1246
        and fixed.address == 0xB5C4 and fixed.bytes == 48
        and vector.value == 0xB5EB and shelf.bytes == 194 and c2d.bytes == 85,
        "candidate-derived placement contract does not match linked ELF")
    require(not truth.symbols_by_name.get("c2_stream_c2d_read_return")
            and not truth.symbols_by_name.get("c2_stream_shelf_read_return"),
            "linked ELF promotes an internal return point to a symbol")

    identities = {name: OLD._call_identity(
        truth, spec["function"], vector.value, spec["tail"])
        for name, spec in OLD.IDENTITIES.items()}
    selector_section = truth.section(selector.section)
    raw = truth.section_bytes(selector.section)[
        selector.value - selector_section.address:
        selector.value - selector_section.address + selector.bytes]
    c2d_stack = int(identities["c2d"]["hardware_pushed_return"], 16)
    shelf_stack = int(identities["shelf"]["hardware_pushed_return"], 16)
    require(raw[7] == c2d_stack >> 8 and raw[14] == (c2d_stack & 0xFF)
            and raw[20] == shelf_stack >> 8 and raw[27] == (shelf_stack & 0xFF),
            "selector operands differ from actual emitted call identities")
    identities["selector_operands_match"] = True

    e000 = OLD.disassembly(elf, OLD.SECTION)
    require(len(re.findall(
        rf"\b(?:jsr|jmp)\s+\${contract['reader_address']:x}\b", e000)) == 0,
        "E000 bypasses the fixed selector vector")
    fixed_text = OLD.disassembly(elf, ".lisp65_c2_host_facade")
    require(re.search(rf"^\s*b5eb:.*jmp\s+\${selector.value:x}\b",
                      fixed_text, re.M), "fixed vector lost selector")
    cold_text = OLD.disassembly(elf, cold.name)
    all_text = OLD.run(str(OLD.LLVM / "llvm-objdump"), "-d", str(elf)).lower()
    require(len(re.findall(rf"^\s*[0-9a-f]+:.*jsr\s+\${helper.value:x}\b",
                           cold_text, re.M)) == 5
            and len(re.findall(rf"^\s*[0-9a-f]+:.*jsr\s+\${helper.value:x}\b",
                               all_text, re.M)) == 5,
            "cold helper caller identity drift")
    manifest = load(manifest_path)
    rows = sorted(manifest["slices"], key=lambda row: row["file_offset"])
    row = next(item for item in rows if item["section"] == cold.name)
    following = rows[rows.index(row) + 1]
    allocation = following["file_offset"] - row["file_offset"]
    require(row["file_size"] == 1246 and allocation == 1280
            and manifest["storage"]["size"] == 65423,
            "candidate-derived checker saw packed-image growth")
    kernal = load(elf.parent / "kernal-freedom-link.json")
    ownership = kernal["control_flow_ownership"]
    require(ownership["violations"] == [],
            "actual linked KERNAL-freedom consumer is not green")
    value = {
        "status": "PASS: candidate-derived local-return identities linked",
        "placement_contract": contract,
        "ordinary": {"reserve_bytes": reserve,
                     "text_end_exclusive": f"0x{text.address + text.bytes:04x}"},
        "reader": {"address": f"0x{reader.value:04x}", "bytes": reader.bytes},
        "selector": {"address": f"0x{selector.value:04x}",
            "bytes": selector.bytes, "fixed_vector": "0xb5eb",
            "identity_depends_on_global_return_label": False,
            "real_call_identities": identities},
        "return_labels": {"global_non_entries": 0,
                          "symbol_names_present": []},
        "ownership": ownership,
        "cold_displacement": {"bytes": helper.bytes,
            "section_bytes": cold.bytes, "packed_page_bytes": allocation,
            "aggregate_bytes": manifest["storage"]["size"],
            "aggregate_growth_bytes": 0},
        "fixed_block_delta_bytes": 0, "E000_delta_bytes": 0,
        "contracted_margins_used_as_freight": False,
    }
    validate_linked(value, contract)
    return value


def linked_mutations(value: dict[str, Any]) -> list[str]:
    contract = value["placement_contract"]
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "promote-non-entry-to-global": lambda x: x["return_labels"].update(
            global_non_entries=1),
        "derive-identity-from-global-label": lambda x: x["selector"].update(
            identity_depends_on_global_return_label=True),
        "accept-wrong-selector-operands": lambda x: x["selector"][
            "real_call_identities"].update(selector_operands_match=False),
        "restore-predecessor-reader-size": lambda x: x["reader"].update(bytes=166),
        "restore-predecessor-reserve": lambda x: x["ordinary"].update(
            reserve_bytes=24),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_linked(candidate, contract)
        except CandidateCheckerError:
            rejected.append(name)
    require(rejected == list(cases), "candidate-derived linked mutation survived")
    return rejected


def birth_gate(source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") if source_override is None else source_override
    start = source.index("def linked_gate(")
    end = source.index("\ndef linked_mutations(", start)
    linked_source = source[start:end]
    required = (
        'reader.bytes == contract["reader_bytes"]',
        'reserve == contract["ordinary_reserve_bytes"]',
        'text.address + text.bytes == contract["text_end_exclusive"]',
        'selector.value == reader.value + reader.bytes',
    )
    reader_pin = "reader.bytes == " + "188"
    reserve_pin = "reserve == " + "2"
    require(all(token in linked_source for token in required)
            and reader_pin not in linked_source
            and reserve_pin not in linked_source,
            "new checker pins candidate placement instead of deriving it")
    return {"status": "PASS: new checker born candidate-derived",
            "derived_fields": ["reader_bytes", "ordinary_reserve_bytes",
                               "text_end_exclusive", "selector_address"],
            "direct_candidate_value_pins": 0}


def source_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    cases = {
        "pin-reader-size": source.replace(
            'reader.bytes == contract["reader_bytes"]',
            "reader.bytes == " + "188", 1),
        "pin-reserve": source.replace(
            'reserve == contract["ordinary_reserve_bytes"]',
            "reserve == " + "2", 1),
        "pin-text-end": source.replace(
            'text.address + text.bytes == contract["text_end_exclusive"]',
            "text.address + text.bytes == 0xb3ae", 1),
        "pin-selector": source.replace(
            "selector.value == reader.value + reader.bytes",
            "selector.value == 0x2333", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            birth_gate(candidate)
        except CandidateCheckerError:
            rejected.append(name)
    require(rejected == list(cases), "checker-birth mutation survived")
    return rejected


def selftest() -> None:
    contract = placement_contract()
    require(contract["reader_bytes"] == 188
            and contract["ordinary_reserve_bytes"] == 2
            and len(source_mutations()) == 4,
            "candidate-derived checker selftest drift")
    print("candidate-derived local return: SELFTEST PASS birth=4 reader=contract")


if __name__ == "__main__":
    try:
        selftest()
    except (CandidateCheckerError, OLD.LocalIdentityError) as error:
        print(f"candidate-derived local return: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
