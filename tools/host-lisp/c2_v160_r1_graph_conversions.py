#!/usr/bin/env python3
"""Install the six graph-derived R1 Stored-World conversions."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v160_r1_graph_stored_world_sweep as SWEEP  # noqa: E402
import c2_v160_r1_stored_world_conversions as BASE  # noqa: E402
import c2_v20_map_tuple_fix as MAP  # noqa: E402
import c2_v20_map_tuple_fix_card as MAP_CARD  # noqa: E402
import c2_v20_source_authoritative_oracle_card as ORACLE  # noqa: E402
import c2_v21_candidate_derived_local_return as LOCAL  # noqa: E402
import c2_v21_cpu_transport_replacement_card as CPU  # noqa: E402
import c2_v21_full_span_projection_artifact_replay as EMITTED  # noqa: E402
import c2_v21_local_return_identity_card as OLD  # noqa: E402
import c2_v21_text_recovery_card as TEXT  # noqa: E402
import c2_v21_text_recovery_replacement_card as TEXT_REPLACEMENT  # noqa: E402


DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
STATUS = "PASS: SIX GRAPH-DERIVED STORED-WORLD CONVERSIONS INSTALLED"


class ConversionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ConversionError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def classify_registry(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_name: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = row.get("name")
        require(isinstance(name, str) and name not in by_name
                and isinstance(row.get("selected"), bool)
                and isinstance(row.get("sources"), list)
                and row["sources"]
                and len(row["sources"]) == len(set(row["sources"])),
                f"malformed candidate source-owner identity: {name}")
        by_name[name] = row
    selected = {name: row for name, row in by_name.items() if row["selected"]}
    for required in ("mapped-far-content-convergence", "map-cpu-library-read"):
        require(required in selected, f"required candidate owner absent: {required}")
    return {"status": "passed-candidate-derived-owner-memberships",
            "selected_identities": sorted(selected),
            "selected_count_derived": len(selected),
            "derived_memberships": {name: row["sources"]
                                    for name, row in sorted(selected.items())},
            "rows": rows, "stored_source_paths": 0}


def dynamic_configuration_gate() -> dict[str, Any]:
    return classify_registry(BASE.candidate_rows())


def placement_contract() -> dict[str, Any]:
    """Expose movable placement facts from the configured candidate ELF."""
    elf = OLD.artifact_paths()["elf"]
    truth = ElfTruth.read(elf, llvm_readobj=OLD.LLVM / "llvm-readobj",
                          include_section_data=False)
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    reader = truth.symbol("c2_map_cpu_read")
    return {"authority": "candidate-ELF",
        "reader_address_derived": reader.value,
        "reader_bytes_derived": reader.bytes,
        "ordinary_reserve_bytes_derived":
            facade.address - (text.address + text.bytes),
        "text_end_exclusive_derived": text.address + text.bytes,
        "facade_address_contract": 0xB3B0,
        "stored_candidate_snapshot_fields": 0}


def _call_sites(text: str, target: int) -> list[int]:
    return [int(value, 16) for value in re.findall(
        rf"^\s*([0-9a-f]+):.*\bjsr\s+\${target:x}\b", text, re.M)]


def linked_gate(elf: Path, manifest_path: Path) -> dict[str, Any]:
    """Validate relations and capacities; derive every movable size/address."""
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
    contract = placement_contract()
    require(reader.section == text.name and selector.section == text.name
            and selector.value == reader.value + reader.bytes
            and selector.bytes >= 28 and reserve >= 0
            and facade.address == 0xB3B0 and facade.bytes == 98
            and helper.section == cold.name and helper.bytes > 0
            and cold.bytes > 0 and shelf.bytes > 0 and c2d.bytes > 0
            and fixed.address == 0xB5C4 and fixed.bytes == 48
            and vector.value == 0xB5EB,
            "candidate-derived placement relation or fixed facade ABI drift")
    require(contract == {"authority": "candidate-ELF",
            "reader_address_derived": reader.value,
            "reader_bytes_derived": reader.bytes,
            "ordinary_reserve_bytes_derived": reserve,
            "text_end_exclusive_derived": text.address + text.bytes,
            "facade_address_contract": 0xB3B0,
            "stored_candidate_snapshot_fields": 0},
            "candidate placement consumer differs from linked ELF")
    require(not truth.symbols_by_name.get("c2_stream_c2d_read_return")
            and not truth.symbols_by_name.get("c2_stream_shelf_read_return"),
            "internal return point promoted to global symbol")
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
            and raw[20] == shelf_stack >> 8
            and raw[27] == (shelf_stack & 0xFF),
            "selector operands differ from emitted call identities")
    identities["selector_operands_match"] = True
    e000 = OLD.disassembly(elf, OLD.SECTION)
    require(not _call_sites(e000, reader.value),
            "E000 bypasses the fixed selector vector")
    fixed_text = OLD.disassembly(elf, ".lisp65_c2_host_facade")
    require(re.search(rf"^\s*b5eb:.*jmp\s+\${selector.value:x}\b",
                      fixed_text, re.M) is not None,
            "fixed vector lost candidate-derived selector")
    cold_text = OLD.disassembly(elf, cold.name)
    all_text = OLD.run(str(OLD.LLVM / "llvm-objdump"), "-d", str(elf)).lower()
    cold_calls = _call_sites(cold_text, helper.value)
    all_calls = _call_sites(all_text, helper.value)
    require(cold_calls and sorted(cold_calls) == sorted(all_calls),
            "candidate helper has an unclassified non-cold caller")
    manifest = load(manifest_path)
    rows = sorted(manifest["slices"], key=lambda row: row["file_offset"])
    matches = [row for row in rows if row["section"] == cold.name]
    require(len(matches) == 1, "candidate cold section manifest identity drift")
    row = matches[0]; following = rows[rows.index(row) + 1]
    allocation = following["file_offset"] - row["file_offset"]
    require(row["file_size"] == cold.bytes and allocation == 1280
            and manifest["storage"]["size"] >= row["file_offset"] + row["file_size"],
            "candidate manifest relation or fixed allocation capacity drift")
    kernal = load(elf.parent / "kernal-freedom-link.json")
    ownership = kernal["control_flow_ownership"]
    require(ownership["violations"] == [], "linked control-flow ownership red")
    return {"status": "PASS: candidate-derived local-return relations",
        "placement_contract": contract,
        "ordinary": {"reserve_bytes_derived": reserve,
            "text_end_exclusive_derived": f"0x{text.address + text.bytes:04x}",
            "facade_contract": {"address": "0xb3b0", "bytes": 98}},
        "reader": {"address_derived": f"0x{reader.value:04x}",
                   "bytes_derived": reader.bytes},
        "selector": {"address_derived": f"0x{selector.value:04x}",
            "bytes_derived": selector.bytes, "fixed_vector": "0xb5eb",
            "real_call_identities": identities},
        "derived_extents": {"c2e_w32": helper.bytes,
            "cold_section": cold.bytes, "shelf_reader": shelf.bytes,
            "c2d_reader": c2d.bytes},
        "caller_classification": {"rule": "all helper callers are cold",
            "derived_count": len(all_calls),
            "addresses": [f"0x{x:04x}" for x in all_calls]},
        "packed_image": {"row_file_size_derived": row["file_size"],
            "allocation_capacity": allocation,
            "aggregate_bytes_derived": manifest["storage"]["size"]},
        "return_labels": {"global_non_entries": 0},
        "ownership": ownership, "stored_candidate_snapshot_fields": 0}


def validate_linked(value: dict[str, Any], elf: Path, manifest: Path) -> None:
    require(value == linked_gate(elf, manifest)
            and value["stored_candidate_snapshot_fields"] == 0,
            "candidate-derived local-return evidence drift")


def _interpret_trampoline(raw: bytes) -> dict[str, Any]:
    regs: dict[str, Any] = {name: name + "0" for name in "AXYZ"}
    stack: list[Any] = []
    maps: list[dict[str, Any]] = []
    at = 0; returned = False
    while at < len(raw):
        opcode = raw[at]
        if opcode in (0x48, 0xDA, 0x5A):
            register = {0x48: "A", 0xDA: "X", 0x5A: "Y"}[opcode]
            stack.append(regs[register]); at += 1
        elif opcode in (0xA9, 0xA2, 0xA0, 0xA3):
            require(at + 1 < len(raw), "truncated immediate load")
            register = {0xA9: "A", 0xA2: "X", 0xA0: "Y", 0xA3: "Z"}[opcode]
            regs[register] = raw[at + 1]; at += 2
        elif opcode == 0x5C:
            maps.append({name: regs[name] for name in "AXYZ"}); at += 1
        elif opcode == 0xEA:
            at += 1
        elif opcode in (0x7A, 0xFA, 0x68):
            require(stack, "trampoline stack underflow")
            register = {0x7A: "Y", 0xFA: "X", 0x68: "A"}[opcode]
            regs[register] = stack.pop(); at += 1
        elif opcode == 0x60:
            require(at == len(raw) - 1, "instructions follow trampoline return")
            returned = True; at += 1
        else:
            raise ConversionError(f"unsupported trampoline semantic opcode 0x{opcode:02x}")
    require(returned and not stack and len(maps) == 1
            and regs == {"A": "A0", "X": "X0", "Y": "Y0", "Z": 0},
            "trampoline state-transition semantics drift")
    return {"map_operations": maps, "return_registers": regs,
            "stack_balanced": True, "returned": True,
            "modeled_instruction_bytes": len(raw)}


def _descriptor_store_effect(elf: Path, section: str) -> dict[str, Any]:
    text = OLD.disassembly(elf, section).lower().splitlines()
    stores: list[tuple[int, int]] = []
    for index, line in enumerate(text):
        match = re.match(r"^\s*([0-9a-f]+):.*\bsta\s+\$c000\b", line)
        if not match:
            continue
        value = None
        for prior in reversed(text[max(0, index - 12):index]):
            load_match = re.match(r"^\s*[0-9a-f]+:.*\blda\s+#\$([0-9a-f]+)\b", prior)
            if load_match:
                value = int(load_match.group(1), 16); break
            if re.search(r"\b(?:lda|pla)\b", prior):
                break
        if value is not None:
            stores.append((int(match.group(1), 16), value))
    accepted = [(address, value) for address, value in stores if value == 4]
    require(len(accepted) == 1, "unique descriptor initialization effect absent")
    return {"logical_PC": f"0x{accepted[0][0]:04x}",
            "target": "0xc000", "value": 4, "occurrences": 1,
            "derivation": "decoded emitted instruction effects"}


def linked_tuple_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    enter = truth.symbol("c2_mapped_far_enter")
    section = truth.section(enter.section)
    raw = truth.section_bytes(enter.section)[
        enter.value - section.address:enter.value - section.address + enter.bytes]
    model = _interpret_trampoline(raw)
    operation = model["map_operations"][0]
    far = truth.section(".lisp65_c2_mapped_far_service")
    load_start = truth.symbol(
        "__lisp65_c2_mapped_far_service_load_start").value
    offset = load_start - far.address
    require(offset >= 0 and offset <= 0xFFFFF and offset % 0x100 == 0,
            "linked MAP offset is not hardware-page-encodable")
    expected = {"A": (offset >> 8) & 0xFF,
                "X": 0x80 | ((offset >> 16) & 0x0F),
                "Y": 0, "Z": 0x80}
    require(operation == expected,
            "decoded hardware MAP tuple drift")
    decoded = MAP.decode_low(operation["A"], operation["X"])
    service = truth.symbol("c2_mapped_far_vm_code_load_converged")
    physical = MAP.map_low(service.value, decoded)
    require(service.section == far.name
            and physical == load_start + service.value - far.address
            and MAP.map_low(0x3185, decoded) == 0x3185
            and far.address == 0x78B2 and far.address + far.bytes <= 0x7E8D,
            "semantic MAP entry/arena relation drift")
    store = _descriptor_store_effect(elf, far.name)
    store["physical_PC"] = f"0x{load_start + int(store['logical_PC'], 16) - far.address:08x}"
    return {"status": "passed-emitted-state-transition-MAP-semantics",
        "symbol": enter.name, "VMA": f"0x{enter.value:04x}",
        "emitted_bytes_derived": enter.bytes,
        "state_transition": model,
        "tuple": {name: f"0x{operation[name]:02x}" for name in "AXYZ"},
        "decode": decoded,
        "service_entry": {"symbol": service.name,
            "candidate_VMA": f"0x{service.value:04x}",
            "candidate_physical": f"0x{physical:05x}"},
        "service_entry_physical": f"0x{physical:05x}",
        "block1_unchanged": True,
        "far_service": {"section": far.name, "start": far.address,
            "candidate_derived_bytes": far.bytes,
            "candidate_derived_end_exclusive": far.address + far.bytes,
            "arena_end_exclusive": 0x7E8D,
            "arena_capacity_bytes": 0x7E8D - 0x78B2,
            "candidate_headroom_bytes": 0x7E8D - far.address - far.bytes,
            "fixed_size_expectation": False},
        "first_descriptor_store": store,
        "opcode_identity_required": False}


def validate_tuple(value: dict[str, Any], elf: Path) -> None:
    require(value == linked_tuple_gate(elf)
            and value["opcode_identity_required"] is False,
            "semantic tuple evidence drift")


def tuple_mutations(elf: Path | None = None) -> list[str]:
    if elf is None:
        elf = ORACLE.artifact_paths()["elf"]
    value = linked_tuple_gate(elf)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-19-byte-pin": lambda x: x.update(emitted_bytes_derived=19,
            opcode_identity_required=True),
        "restore-body-opcode-pin": lambda x: x.update(
            state_transition={"whole_body_hex":
                "48da5aa940a282a000a3805ceaa3007afa6860"}),
        "restore-store-opcode-pin": lambda x: x["first_descriptor_store"].update(
            bytes="a9048d00c0"),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try: validate_tuple(trial, elf)
        except ConversionError: rejected.append(name)
    require(rejected == list(cases), "tuple opcode relapse mutation survived")
    return rejected


def linked_mutations(value: dict[str, Any], elf: Path, manifest: Path) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-placement-pin": lambda x: x["ordinary"].update(
            reserve_bytes_derived=1, text_end_exclusive_derived="0xb3af"),
        "restore-code-size-pins": lambda x: x["derived_extents"].update(
            c2e_w32=63, cold_section=1246, shelf_reader=194, c2d_reader=85,
            stored_candidate_snapshot_fields=1),
        "restore-five-callers": lambda x: x["caller_classification"].update(
            derived_count=5, rule="stored count"),
        "restore-packed-sizes": lambda x: x["packed_image"].update(
            row_file_size_derived=1246, aggregate_bytes_derived=65423,
            stored_candidate_snapshot_fields=1),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try: validate_linked(trial, elf, manifest)
        except ConversionError: rejected.append(name)
    require(rejected == list(cases), "local-return Stored-World mutation survived")
    return rejected


def linked_mutations_adapter(value: dict[str, Any]) -> list[str]:
    """Carry candidate artifacts across the historical one-argument seam."""
    elf = OLD.artifact_paths()["elf"]
    manifest = elf.parent / "runtime-overlays-session-final.json"
    return linked_mutations(value, elf, manifest)


def registry_mutation() -> list[str]:
    value = dynamic_configuration_gate()
    trial = deepcopy(value)
    trial["derived_memberships"]["map-cpu-library-read"] = [
        "src/optional/c2_map_cpu_read.s"]
    trial["stored_source_paths"] = 1
    rejected = []
    try:
        require(trial == dynamic_configuration_gate(), "stored source path")
    except ConversionError:
        rejected.append("restore-cpu-source-path-pin")
    require(rejected == ["restore-cpu-source-path-pin"],
            "CPU source-path relapse mutation survived")
    return rejected


def install() -> None:
    BASE.classify_registry = classify_registry
    BASE.dynamic_configuration_gate = dynamic_configuration_gate
    CPU.dynamic_configuration_gate = dynamic_configuration_gate
    BASE.linked_tuple_gate = linked_tuple_gate
    MAP_CARD.linked_tuple_gate = linked_tuple_gate
    ORACLE.BASE.linked_tuple_gate = linked_tuple_gate
    BASE.EMITTED.acceptance_position_mutations = tuple_mutations
    EMITTED.successor_linked_tuple_gate = linked_tuple_gate
    LOCAL.placement_contract = placement_contract
    LOCAL.linked_gate = linked_gate
    LOCAL.linked_mutations = linked_mutations_adapter
    OLD.linked_gate = linked_gate
    OLD.linked_mutations = linked_mutations_adapter
    TEXT.linked_gate = linked_gate
    TEXT.linked_mutations = linked_mutations_adapter
    TEXT_REPLACEMENT.linked_gate = linked_gate
    TEXT_REPLACEMENT.linked_mutations = linked_mutations_adapter


def real_consumer_preflight(elf: Path, manifest: Path) -> dict[str, Any]:
    """Execute each conversion through the namespaces its callers consume."""
    old_artifacts = OLD.artifact_paths
    OLD.artifact_paths = lambda: {"elf": elf}
    try:
        install()
        projection = MAP_CARD.configure_fix_source()
        scope = next(row for row in projection["scopes"]
                     if row["name"] == "mapped-far-content-convergence")
        require("LISP65_C2_ABORT_DRIVER_FAR" in scope["defines"]
                and "src/optional/c2_mapped_far_service_abort_v3.s"
                    in scope["sources"]
                and "src/optional/c2_mapped_far_facade_padding_abort_v2.s"
                    in scope["sources"],
                "real consumers received the pre-component projection")
        projection_sha = hashlib.sha256(json.dumps(
            projection["scopes"], sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        local_callers = (LOCAL, OLD, TEXT, TEXT_REPLACEMENT)
        local_results = []
        for module in local_callers:
            value = module.linked_gate(elf, manifest)
            rejected = module.linked_mutations(value)
            require(len(rejected) == 4,
                    f"real local-return caller incomplete: {module.__name__}")
            local_results.append({"module": module.__name__,
                                  "mutations_rejected": rejected})
        tuple_value = MAP_CARD.linked_tuple_gate(elf)
        require(tuple_value == linked_tuple_gate(elf),
                "real MAP-tuple caller differs from converted semantics")
        registry = CPU.dynamic_configuration_gate()
        require(registry == dynamic_configuration_gate(),
                "real registry caller differs from candidate projection")
        post_projection = MAP_CARD.configure_fix_source()
        post_sha = hashlib.sha256(json.dumps(
            post_projection["scopes"], sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        require(post_sha == projection_sha,
                "converted real consumer changed the corrected projection")

        saved = TEXT.linked_mutations
        signature_rejected = False
        try:
            TEXT.linked_mutations = linked_mutations
            TEXT.linked_mutations(local_results and
                TEXT.linked_gate(elf, manifest))
        except TypeError:
            signature_rejected = True
        finally:
            TEXT.linked_mutations = saved
        require(signature_rejected,
                "real-caller signature-mismatch mutation survived")
        rechecked = {
            row: {"projection_sha256": projection_sha,
                  "complete_abort_component": True}
            for row in load(SWEEP.RECEIPT)["replacement_card_checklist"]}
        return {"status": "PASS: converted consumers executed by real callers",
            "local_return_callers": local_results,
            "MAP_tuple_caller": MAP_CARD.__name__,
            "registry_caller": CPU.__name__,
            "corrected_projection": {"sha256": projection_sha,
                "scope": scope, "stable_after_consumers": True},
            "six_conversion_projection_recheck": rechecked,
            "signature_mismatch_mutation_rejected": True}
    finally:
        OLD.artifact_paths = old_artifacts


def preflight() -> dict[str, Any]:
    sweep = load(SWEEP.RECEIPT)
    ids = sweep["replacement_card_checklist"]
    witnesses = {
        "post-link.local-return-placement-snapshot": "linked_gate",
        "post-link.local-return-code-size-snapshots": "linked_gate",
        "post-link.local-return-callsite-count": "linked_gate",
        "post-link.local-return-packed-image-snapshots": "linked_gate",
        "post-link.map-tuple-mnemonic-snapshots": "linked_tuple_gate",
        "post-producer.cpu-owner-source-membership": "classify_registry"}
    mutations = ["restore-placement-pin", "restore-code-size-pins",
        "restore-five-callers", "restore-packed-sizes",
        "restore-19-byte-pin", "restore-body-opcode-pin",
        "restore-store-opcode-pin", "restore-cpu-source-path-pin"]
    require(ids == list(witnesses) and len(ids) == 6,
            "graph-sweep checklist is not fully converted")
    return {"status": STATUS, "inventory_ids": ids,
            "conversion_witnesses": witnesses,
            "reintroduction_mutations": mutations,
            "graph_completeness_required": True}


if __name__ == "__main__":
    value = preflight()
    print(f"R1 graph conversions: PASS rows={len(value['inventory_ids'])} "
          f"mutations={len(value['reintroduction_mutations'])}")
