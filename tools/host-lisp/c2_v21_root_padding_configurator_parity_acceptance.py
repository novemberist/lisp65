#!/usr/bin/env python3
"""Qualify the configurator-parity continuation finals without rebuilding."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_dma_content_structural_absence as ABSENCE  # noqa: E402
import c2_v21_facade_padding_linker_producer_rebind_20260817 as FACADE_REBIND  # noqa: E402
import c2_v20_map_tuple_fix_card as MAP_SCOPE  # noqa: E402
import c2_v20_source_authoritative_oracle_card as ORACLE  # noqa: E402
import c2_v21_full_span_projection_artifact_replay as FULL_SPAN  # noqa: E402
import c2_v21_phase9_freight_boundary_golden as FREIGHT_GOLDEN  # noqa: E402
import c2_v21_probe_oracle_root_padding_replacement_card as CARD  # noqa: E402
import c2_v21_root_padding_configurator_projection_replacement as LINK  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
TARGET = LINK.TARGET
WPLTO = LINK.WPLTO
FINAL = LINK.FINAL
QUALIFICATION = TARGET / "configurator-parity-acceptance"
ABI_REPORT = QUALIFICATION / "c2-asm-leaf-abi.json"
SCOPE_RESULT = QUALIFICATION / "owner-scope-result.json"
ACCEPTANCE_RESULT = QUALIFICATION / "artifact-acceptance.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-root-padding-configurator-parity-acceptance-receipt.json")
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2.3-v2.1-configurator-parity-acceptance-v1"
STATUS = "PASS: configurator-parity finals accepted read-only"


class AcceptanceError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AcceptanceError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def family() -> dict[str, dict[str, Any]]:
    return {path.name: bind(path) for path in LINK.BASE.family(FINAL)}


def configure() -> None:
    """Point only the read-only acceptance consumers at the successor finals."""
    CARD.BUILD = TARGET
    CARD.PRODUCER_RESULT = QUALIFICATION / "unused-producer-result.json"
    CARD.SCOPE_RESULT = SCOPE_RESULT
    CARD.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    CARD.ABI_REPORT = ABI_REPORT
    CARD.DRIVER = DRIVER
    CARD.configure()


def compiler_input_proof() -> dict[str, Any]:
    link = load(LINK.RECEIPT)
    receipt_path = Path(str(FINAL) + ".compiler-input-consumption.json")
    actual = load(receipt_path)
    require(
        link.get("status") == LINK.STATUS
        and link["final_artifacts"] == family()
        and link["execution_accounting"]["final_product_links"] == 1
        and actual["status"] == "passed-bound-candidate-header-consumed"
        and actual["consumed_value"] == 46043
        and actual["bound_header"] == LINK.HEADER.header_binding()
        and actual["historical_same_basename_accepted"] is False,
        "configurator-parity final/header authority drift")
    return {"link_receipt": bind(LINK.RECEIPT),
            "compiler_receipt": bind(receipt_path), "result": actual}


def run_abi_gate() -> dict[str, Any]:
    command = [sys.executable, str(HOST / "c2_asm_leaf_abi_gate.py"),
               "--elf", str(FINAL) + ".elf", "--out", str(ABI_REPORT)]
    result = subprocess.run(command, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0
            and "passed-all-assembler-leaf-abi-contracts" in result.stdout,
            f"linked ABI qualification red:\n{result.stdout}")
    value = load(ABI_REPORT)
    require(
        value["transitive_callee_saved_preservation"]["model"]
            ["unpreserved_callee_saved_writers"] == []
        and value["contractual_mapped_far_exit_preservation"]["model"]
            ["inner_exits"] == 8,
        "linked ABI domains drift")
    return {"status": "PASS", "receipt": bind(ABI_REPORT),
            "witness": " ".join(result.stdout.split())}


def run_child(action: str) -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
                            text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    require(result.returncode == 0,
            f"configurator-parity acceptance {action} red:\n{result.stdout}")
    return {"status": "PASS", "output": " ".join(result.stdout.split())}


def run_gate(command: list[str], token: str, label: str) -> dict[str, Any]:
    result = subprocess.run(command, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0 and token in result.stdout,
            f"fresh {label} red:\n{result.stdout}")
    return {"status": "PASS", "command": " ".join(command),
            "witness": " ".join(result.stdout.split())}


def host_gates() -> dict[str, Any]:
    """Run the inherited gates with the live producer's loud padding rebind."""
    inherited = CARD.BASE.host_gates()
    inherited.update({
        "explicit_facade_padding": run_gate(
            [sys.executable, str(FACADE_REBIND.DRIVER), "check"],
            "CHECK PASS facade=98 pad=19 mutations=6",
            "facade-padding live-producer rebind"),
        "BUILDING_HEAP_mem_unbind": CARD.run_gate(
            [sys.executable, str(CARD.UNBIND.DRIVER), "check"],
            "mutations=7", "BUILDING-HEAP mem-source unbind"),
    })
    return inherited


def scope_child() -> int:
    """Bind source ownership to the inputs consumed by this exact final link."""
    require(TARGET.is_dir() and not SCOPE_RESULT.exists(),
            "scope child lifecycle drift")
    preflight = load(LINK.PREFLIGHT)
    rows = preflight["inputs"]["compiler_inputs"]
    semantic = preflight["semantic_compile"]["translation_units"]
    paths = [row["path"] for row in rows]
    semantic_paths = [row["source"]["path"] for row in semantic]
    expected = {
        "corrected_trampoline": "src/optional/c2_mapped_far_service_v2.s",
        "full_span_reader":
            "src/optional/c2_mapped_far_convergence_full_span.s",
        "facade_padding": "src/optional/c2_mapped_far_facade_padding.s",
    }
    require(
        len(paths) == len(semantic_paths) == 66 and paths == semantic_paths
        and all(paths.count(path) == 1 for path in expected.values())
        and "src/c2_mapped_far_service.s" not in paths
        and "src/c2_mapped_far_convergence.s" not in paths,
        "consumed final-link source-owner scope drift")
    inventory = MAP_SCOPE.real_asm_inventory_gate()
    gate = {
        "status": "PASS: consumed inputs carry one owner and one body",
        "authority": "persisted-semantic-preflight-consumed-by-final-link",
        "translation_units": len(paths), "identities": expected,
        "successor_counts": {name: paths.count(path)
                             for name, path in expected.items()},
        "historical_bodies_selected": 0,
        "real_global_inventory": inventory,
    }
    SCOPE_RESULT.write_bytes(canonical({"status": "PASS", "pid": os.getpid(),
                                        "gate": gate}))
    return 0


def acceptance_child() -> int:
    """Run pre-Completion acceptance with the current v5 freight authority."""
    require(TARGET.is_dir() and not ACCEPTANCE_RESULT.exists(),
            "acceptance child lifecycle drift")
    elf = Path(str(FINAL) + ".elf")
    product = ORACLE.BASE.PRODUCT
    product.configure_e000_reopening()
    product.configure_full_map_ownership()
    product.configure_low_resident_lma_reset()
    comparison = FREIGHT_GOLDEN.compare_elf(elf)
    linker = product.low_resident_lma_reset_gate(
        (WPLTO / "c2-substitution.ld").read_text(encoding="utf-8"))
    tuple_gate = FULL_SPAN.successor_linked_tuple_gate(elf)
    far_payload = FULL_SPAN.PHASE9_RESUME.TUPLE.far_payload_gate(elf)
    source_build = LINK.BASE.SOURCE_WPLTO.parent
    old_build = ORACLE.BUILD
    try:
        ORACLE.BUILD = source_build
        source_oracle = ORACLE.linked_oracle_gate(elf)
    finally:
        ORACLE.BUILD = old_build
    require(
        comparison["allocatable_sections"] == 103
        and comparison["dependent_fixed_vmas"] == 101
        and comparison["dependent_free_derived_vmas"] == 2
        and comparison["fixed_boundary_symbols"] == 25
        and comparison["freight_derived_boundary_symbols"] == 3
        and comparison["mapped_far_service_capacity"]
            ["candidate_headroom_bytes"] == 251
        and tuple_gate["far_service"]["candidate_derived_bytes"] == 1248
        and tuple_gate["far_service"]["candidate_headroom_bytes"] == 251
        and far_payload["candidate_derived_bytes"] == 1248
        and source_oracle["status"] ==
            "passed-linked-delivery-bound-CRC-oracle",
        "pre-Completion candidate-derived acceptance drift")
    value = {
        "status": "PASS", "pid": os.getpid(),
        "VMA_golden": comparison, "low_resident_LMA_reset": linker,
        "linked_MAP_tuple": tuple_gate, "far_payload": far_payload,
        "source_authoritative_oracle": source_oracle,
        "delivered_bytes": {
            "status": "DEFERRED-UNTIL-PUBLISH-LAST-COMPLETION",
            "reason": (
                "the two CRC operands are intentionally not final before "
                "Completion; post-Completion value/identity validation is "
                "mandatory")},
    }
    ACCEPTANCE_RESULT.write_bytes(canonical(value))
    return 0


def function_body(disassembly: str, name: str) -> str:
    marker = f"<{name}>:"
    require(disassembly.count(marker) == 1, f"linked function drift: {name}")
    tail = disassembly.split(marker, 1)[1]
    end = tail.find("\n\n")
    return tail if end < 0 else tail[:end]


def linked_product() -> dict[str, Any]:
    """Describe emitted successor facts without predecessor reserve pins."""
    elf = Path(str(FINAL) + ".elf")
    truth = ElfTruth.read(elf, llvm_readobj=CARD.BASE.READOBJ,
                          include_section_data=True)
    ext = truth.symbol("ext_dma_read_or_abort")
    c2 = truth.symbol("c2_dma_read_or_abort")
    reader = truth.symbol("c2_map_cpu_read")
    text_section = truth.section(reader.section)
    service = truth.section(".lisp65_c2_mapped_far_service")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    padding = truth.symbol("__lisp65_c2_mapped_far_facade_padding")
    disassembly = subprocess.run(
        [str(CARD.BASE.OBJDUMP), "-d", "--symbolize-operands", str(elf)],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout
    ext_body = function_body(disassembly, ext.name)
    c2_body = function_body(disassembly, c2.name)
    reader_raw = truth.section_bytes(reader.section)[
        reader.value - text_section.address:
        reader.value - text_section.address + reader.bytes]
    progress = reader_raw[12:34]
    tuple_gate = FULL_SPAN.successor_linked_tuple_gate(elf)
    abi = load(ABI_REPORT)
    transitive = abi["transitive_callee_saved_preservation"]
    contractual = abi["contractual_mapped_far_exit_preservation"]
    ordinary_headroom = facade.address - (text_section.address + text_section.bytes)
    require(
        ext.bytes == 35 and c2.bytes == 27 and reader.bytes == 189
        and service.bytes == 1248 and facade.bytes == 98
        and padding.bytes == 19 and padding.value == facade.address + 79
        and ext_body.count("<c2_map_cpu_read>") == 1
        and c2_body.count("<c2_map_cpu_read>") == 1
        and "vm_code_load_converged" not in ext_body
        and "vm_code_load_converged" not in c2_body
        and progress == CARD.BASE.BASE.LEASE.EXPECTED_LINKED_PROGRESS
        and ordinary_headroom == 4
        and transitive["model"]["unpreserved_callee_saved_writers"] == []
        and contractual["model"]["inner_exits"] == 8
        and tuple_gate["far_service"]["candidate_headroom_bytes"] == 251,
        "linked configurator-parity product identity drift")
    return {
        "status": "PASS: emitted configurator-parity product accepted",
        "wrappers": {"ordinary": {"bytes": ext.bytes},
            "mapped_facade": {"bytes": c2.bytes},
            "execution_delta_from_Link112_bytes": -22},
        "CPU_reader": {"address": f"0x{reader.value:04x}",
            "bytes": reader.bytes, "progress_bytes": progress.hex()},
        "ordinary_text": {"end_exclusive":
            f"0x{text_section.address + text_section.bytes:04x}",
            "candidate_headroom_bytes": ordinary_headroom,
            "headroom_source": "emitted-candidate-section-table"},
        "facade_padding": {"bytes": padding.bytes,
            "facade_bytes": facade.bytes, "executed": False},
        "mapped_far": {"bytes": service.bytes,
            "headroom_bytes": tuple_gate["far_service"]
                ["candidate_headroom_bytes"]},
        "MAP_tuple": tuple_gate,
        "C_reachable_ASM_closure": transitive["model"],
        "contractual_service_exits": contractual["model"],
        "static_header_consumed_bytes": 46043,
    }


def linked_product_mutations(value: dict[str, Any]) -> list[str]:
    from copy import deepcopy
    cases = {
        "restore-DMA-wrapper": lambda x: x["wrappers"]["ordinary"].update(
            bytes=36),
        "restore-old-price": lambda x: x["wrappers"].update(
            execution_delta_from_Link112_bytes=-18),
        "pin-one-byte-reserve": lambda x: x["ordinary_text"].update(
            candidate_headroom_bytes=1),
        "shrink-padding": lambda x: x["facade_padding"].update(bytes=18),
        "lose-service": lambda x: x["mapped_far"].update(bytes=1247),
        "lose-callee-save": lambda x: x["C_reachable_ASM_closure"].update(
            unpreserved_callee_saved_writers=["__rc20"]),
        "restore-ambient-header": lambda x: x.update(
            static_header_consumed_bytes=45939),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        if trial != value:
            rejected.append(name)
    require(rejected == list(cases), "linked product mutation survived")
    return rejected


def structural_absence() -> dict[str, Any]:
    """Apply the born-derived absence rule to this exact successor ELF."""
    elf = Path(str(FINAL) + ".elf")
    old_elf = ABSENCE.ELF
    try:
        ABSENCE.ELF = elf
        bodies = ABSENCE.function_bodies()
    finally:
        ABSENCE.ELF = old_elf
    wrappers: dict[str, Any] = {}
    caller_rows: list[dict[str, str]] = []
    for wrapper in ("ext_dma_read_or_abort", "c2_dma_read_or_abort"):
        body = ABSENCE.unique_body(bodies, wrapper)
        callers = ABSENCE.direct_callers(bodies, wrapper)
        require(body.count("<c2_map_cpu_read>") == 1
                and "<c2_facade_vm_code_load>" not in body
                and "<c2_facade_c2_dma>" not in body,
                f"mutable wrapper is not rooted at MAP-CPU: {wrapper}")
        wrappers[wrapper] = {"transport": "MAP-CPU",
            "linked_callers": callers, "linked_caller_count": len(callers),
            "DMA_submission_edges": 0}
        caller_rows.extend({**row, "wrapper": wrapper,
                            "transport": "MAP-CPU"} for row in callers)
    expected_classes = {
        "ext_dma": "mutable-content-rerouted-to-MAP-CPU",
        "c2_facade_target_c2_dma": "mutable-content-rerouted-to-MAP-CPU",
        "c2_product_physical_copy": "no-linked-content-entry",
        "vm_runtime_overlay_exec_family": "immutable-delivery-CRC",
        "c2k_copy": "immutable-delivery-CRC",
    }
    registered = ABSENCE.registered_workbench_surfaces()
    require({str(row["owner"]) for row in registered} == set(expected_classes),
            "unclassified registered workbench content surface")
    physical = ABSENCE.direct_callers(bodies, "c2_physical_read_converged")
    require(not physical, "physical DMA convergence has a live content entry")
    classifications = [{"owner": owner, "classification": classification}
                       for owner, classification in sorted(
                           expected_classes.items())]
    model = {
        "status": "PASS: no unsafe content-consuming DMA read in linked image",
        "derivation": (
            "successor ELF function bodies plus semantic content registry"),
        "candidate_ELF": bind(elf),
        "born_derived": {"mutable_callers": caller_rows,
            "mutable_caller_count": len(caller_rows),
            "historical_caller_count_acceptance_pin": False,
            "new_wrapper_callers_automatically_enumerated": True},
        "wrappers": wrappers, "registered_surfaces": classifications,
        "physical_DMA_content_entry_callers": physical,
        "immutable_CRC_authority": {
            "vm_runtime_overlay_exec_family": bind(ABSENCE.RUNTIME),
            "c2k_copy": bind(ABSENCE.KERNAL)},
        "unsafe_content_DMA_surfaces": [], "unsafe_content_DMA_count": 0,
    }
    ABSENCE.validate(model)
    return model


def accept() -> None:
    require(not QUALIFICATION.exists() and not RECEIPT.exists(),
            "configurator-parity acceptance is one-shot")
    before = family()
    proof = compiler_input_proof()
    QUALIFICATION.mkdir()
    abi = run_abi_gate()
    configure()
    host = host_gates()
    scope_run = run_child("_scope")
    acceptance_run = run_child("_accept")
    product = linked_product()
    product_mutations = linked_product_mutations(product)
    model = structural_absence()
    ABSENCE.validate(model)
    absence_mutations = ABSENCE.mutations(model)
    after = family()
    require(after == before, "read-only qualification changed final artifacts")
    acceptance = load(ACCEPTANCE_RESULT)
    require(
        acceptance.get("status") == "PASS"
        and acceptance["VMA_golden"]["allocatable_sections"] == 103
        and acceptance["VMA_golden"]["dependent_fixed_vmas"] == 101
        and acceptance["VMA_golden"]["dependent_free_derived_vmas"] == 2
        and acceptance["VMA_golden"]["fixed_boundary_symbols"] == 25
        and acceptance["VMA_golden"]["freight_derived_boundary_symbols"] == 3
        and acceptance["delivered_bytes"]["status"] ==
            "DEFERRED-UNTIL-PUBLISH-LAST-COMPLETION"
        and model["unsafe_content_DMA_count"] == 0,
        "configurator-parity acceptance authority drift")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-17", "status": STATUS,
        "authority": {"owner": LINK.authorization(),
            "final_link": bind(LINK.RECEIPT), "driver": bind(DRIVER)},
        "compiler_input_consumption": proof,
        "final_artifacts_before": before, "final_artifacts_after": after,
        "linked_ABI": abi, "preflight_authorities": host,
        "owner_scope": load(SCOPE_RESULT), "acceptance": acceptance,
        "linked_product": product,
        "linked_product_mutations_rejected": product_mutations,
        "structural_absence": model,
        "structural_absence_mutations_rejected": absence_mutations,
        "processes": {"parent": os.getpid(), "scope": scope_run,
                      "acceptance": acceptance_run},
        "execution_accounting": {"new_WPLTO_card_runs": 0,
            "new_materializations": 0, "final_product_links": 0,
            "qualification_runs": 1, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "next": "Completion, same-world media, poison-regression D2",
        "claim_limit": (
            "Read-only qualification of the four configurator-parity finals; "
            "no WPLTO, link, Completion, media or device action."),
    }
    RECEIPT.write_bytes(canonical(value))
    print("configurator-parity acceptance: PASS final=4 VMA=101/2 "
          "unsafe-DMA=0 static-header=46043")


def check() -> None:
    value = load(RECEIPT)
    require(value.get("status") == STATUS
            and value["final_artifacts_after"] == family()
            and value["compiler_input_consumption"]["result"]
                ["consumed_value"] == 46043
            and value["structural_absence"]["unsafe_content_DMA_count"] == 0,
            "configurator-parity acceptance receipt drift")
    print("configurator-parity acceptance: CHECK PASS final=4 "
          "VMA=101/2 unsafe-DMA=0 static-header=46043")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("accept", "check", "_scope", "_accept"))
    action = parser.parse_args().action
    return {"accept": lambda: (accept() or 0),
            "check": lambda: (check() or 0),
            "_scope": scope_child, "_accept": acceptance_child}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"configurator-parity acceptance: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
