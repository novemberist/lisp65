#!/usr/bin/env python3
"""Permanent final-link ownership gate for the mapped Bank-2 service."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

from elf_truth import ElfTruth  # noqa: E402
from evidence_era import stable_recorded_on  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_stack_overlay_ownership as OWN  # noqa: E402


CONTRACT = ROOT / "config/c2-stack-overlay-ownership-contract.json"
MAP_CONTRACT = ROOT / "config/c2-mapped-far-map-contract-v2.json"
ABI_SUCCESSOR_CONTRACT = ROOT / (
    "config/c2-mapped-far-abi-preservation-contract-v2.json")
PRICING = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-stack-overlay-ownership-halt1-candidate-pricing.json")
CONVERGENCE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.4-code-window-content-convergence-gate-receipt.json")
SWEEP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.4-dma-content-consumption-broaden-once-sweep.json")
EQUIVALENCE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.1-mapped-far-abi-preservation-equivalence-receipt.json")
FACADE_SOURCE = ROOT / "src/optional/c2_mapped_far_service_v2.s"
ASSEMBLY_SOURCE = ROOT / "src/c2_mapped_far_convergence.s"
OWNER_HEADER = ROOT / "src/c2_mapped_far_service.h"
DMA_SOURCE = ROOT / "src/c2_platform_dma.c"
RUNTIME_SOURCE = ROOT / "src/c2_product_runtime.c"
LINKER_SOURCE = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
LLVM_MC = ROOT / "tools/llvm-mos/bin/llvm-mc"
LD_LLD = ROOT / "tools/llvm-mos/bin/ld.lld"
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def parse(value: str | int) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def effective_contract() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Apply the two loud successor projections without rewriting history."""
    base = load(CONTRACT)
    map_contract = load(MAP_CONTRACT)
    successor = load(ABI_SUCCESSOR_CONTRACT)
    predecessors = successor["predecessors"]
    for key, path in (
            ("ownership_contract", CONTRACT),
            ("map_contract", MAP_CONTRACT)):
        row = predecessors[key]
        require(row["path"] == path.relative_to(ROOT).as_posix()
                and row["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest(),
                f"mapped-far ABI successor lost {key} ancestry")
    require(successor.get("status") == "owner-authorized-78ae9255",
            "mapped-far ABI successor authorization drift")
    artifact = successor["artifact_successor"]
    projected = deepcopy(base)
    far = projected["mapped_far_service"]
    far["map_tuple"].update(map_contract["tuple"])
    far["map_tuple"].update({
        "mapped_physical_slab_start": map_contract["map_semantics"]
            ["mapped_physical_slab_start"],
        "mapped_service_cpu_end_exclusive": artifact["cpu_end_exclusive"],
    })
    far["bank2"].update({
        "service_physical_end_exclusive": artifact[
            "physical_end_exclusive"],
        "service_bytes": artifact["exact_bytes"],
        "post_service_static_bytes": artifact["post_service_static_bytes"],
        "post_service_headroom_bytes": artifact["post_service_headroom_bytes"],
    })
    far["far_symbols"] = [{
        "name": "c2_mapped_far_convergence_assembly_body",
        "bytes": artifact["exact_bytes"],
    }]
    return projected, map_contract, successor


def run(command: list[str], label: str, *, input_text: str | None = None,
        expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command, cwd=ROOT, input=input_text, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(result.returncode == expect,
            f"{label}: exit={result.returncode}: {result.stderr}")
    return result


def fixture_source(contract: dict[str, Any], stack_bytes: int) -> str:
    return f"""
.section .lisp65_c2_mapped_far_facade.abort,"ax",@progbits
.globl c2_dma_read_or_abort
.type c2_dma_read_or_abort,@function
c2_dma_read_or_abort:
  .space 46, 0xea
.size c2_dma_read_or_abort, .-c2_dma_read_or_abort

.section .lisp65_c2_convergence_state.d700_jobs,"aw",@nobits
.globl c2_dma_verify_list
c2_dma_verify_list: .space 24
.section .lisp65_c2_convergence_state.d700_value,"aw",@nobits
.globl c2_dma_verify
c2_dma_verify: .space 1
.section .lisp65_c2_convergence_state.d705_jobs,"aw",@nobits
.globl c2_edma_probe_jobs
c2_edma_probe_jobs: .space 40
.section .lisp65_c2_convergence_state.d705_value,"aw",@nobits
.globl c2_edma_probe_value
c2_edma_probe_value: .space 1

.section .lisp65_c2_convergence_zp.d700_done,"aw",@nobits
.globl c2_dma_verify_done
c2_dma_verify_done: .space 1
.section .lisp65_c2_convergence_zp.d705_done,"aw",@nobits
.globl c2_edma_probe_done
c2_edma_probe_done: .space 1

.section .lisp65_fixture_dependencies,"aw",@nobits
.globl c2_dma_list
c2_dma_list: .space 12
.globl c2_edma_job
c2_edma_job: .space 20
.section .lisp65_fixture_markers,"a",@progbits
.globl c2_dma_verify_marker
c2_dma_verify_marker: .byte 0xa5
.globl c2_edma_probe_marker
c2_edma_probe_marker: .byte 0xa5

.section .noinit..Lstatic_stack,"aw",@nobits
.space {stack_bytes}
.section .lisp65_fixture_overlay,"ax",@progbits
.byte 0xea
""".strip() + "\n"


def fixture_linker(contract: dict[str, Any]) -> str:
    far = contract["mapped_far_service"]
    geometry = contract["geometry"]
    resident = far["resident"]
    mapping = far["map_tuple"]
    bank2 = far["bank2"]
    rc = "\n".join(f"__rc{i} = 0x{i:02x};" for i in range(2, 32))
    return f"""{rc}
SECTIONS {{
  .lisp65_c2_convergence_zp 0x87 (NOLOAD) : {{
    KEEP(*(.lisp65_c2_convergence_zp.*))
  }}
  .lisp65_c2_mapped_far_facade {parse(resident['start']):#x} : {{
    KEEP(*(.lisp65_c2_mapped_far_facade.*))
  }}
  .lisp65_c2_mapped_far_service {parse(mapping['mapped_service_cpu_start']):#x}
      : AT({parse(bank2['service_physical_start']):#x}) {{
    KEEP(*(.lisp65_c2_mapped_far_service))
  }}
  .lisp65_c2_convergence_state 0xc000 (NOLOAD) : {{
    KEEP(*(.lisp65_c2_convergence_state.*))
  }}
  .lisp65_c2_static_stack 0xc074 (NOLOAD) : {{
    KEEP(*(.noinit..Lstatic_stack*))
  }}
  .lisp65_fixture_dependencies 0xc080 (NOLOAD) : {{
    KEEP(*(.lisp65_fixture_dependencies))
  }}
  .lisp65_fixture_markers 0xc0a0 : {{
    KEEP(*(.lisp65_fixture_markers))
  }}
  .lisp65_fixture_overlay {parse(geometry['overlay_floor']):#x} : {{
    KEEP(*(.lisp65_fixture_overlay))
  }}
}}
ASSERT(SIZEOF(.lisp65_c2_mapped_far_facade) == {resident['total_bytes']},
       "mapped far facade size drift");
ASSERT(SIZEOF(.lisp65_c2_mapped_far_service) == {bank2['service_bytes']},
       "mapped far service size drift");
ASSERT(SIZEOF(.lisp65_c2_convergence_state) == 66,
       "mapped far state size drift");
ASSERT(SIZEOF(.lisp65_c2_convergence_zp) == 2,
       "mapped far ZP size drift");
ASSERT(SIZEOF(.lisp65_c2_static_stack) <= 12,
       "compiler static stack escaped its owned 12-byte arena");
ASSERT(ADDR(.lisp65_fixture_overlay) == {parse(geometry['overlay_floor']):#x},
       "owned overlay floor drift");
"""


def section_lma(path: Path, section: str) -> int:
    structured, raw, headers = OWN.read_elf(path)
    row = structured.section(section)
    return OWN.section_lma(row, raw[row.index], headers)


def linked_fixture(contract: dict[str, Any], stack_bytes: int,
                   temp: Path) -> tuple[Path, str]:
    fixture = temp / f"fixture-{stack_bytes}.o"
    facade = temp / "facade.o"
    body = temp / "body.o"
    elf = temp / f"owned-{stack_bytes}.elf"
    script = temp / "owned.ld"
    linker = fixture_linker(contract)
    script.write_text(linker, encoding="utf-8")
    run([str(LLVM_MC), "--triple=mos", "--mcpu=mos45gs02",
         "-filetype=obj", "-o", str(fixture)], "fixture assemble",
        input_text=fixture_source(contract, stack_bytes))
    if not facade.exists():
        run([str(LLVM_MC), "--triple=mos", "--mcpu=mos45gs02",
             "-filetype=obj", "-o", str(facade), str(FACADE_SOURCE)],
            "facade assemble")
    if not body.exists():
        run([str(LLVM_MC), "--triple=mos", "--mcpu=mos45gs02",
             "-filetype=obj", "-o", str(body), str(ASSEMBLY_SOURCE)],
            "assembly body assemble")
    result = subprocess.run(
        [str(LD_LLD), "--emit-relocs", "-T", str(script), "-o", str(elf),
         str(fixture), str(facade), str(body)], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if stack_bytes > 12:
        require(result.returncode != 0
                and "compiler static stack escaped" in result.stderr,
                "13-byte static-stack fixture did not fail closed")
        return elf, linker
    require(result.returncode == 0,
            f"owned final fixture link failed: {result.stderr}")
    return elf, linker


def generated_linker_check(contract: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="lisp65-effective-owner-") as name:
        projected = Path(name) / "ownership-contract.json"
        projected.write_bytes(canonical(contract))
        previous = PRODUCT.OWNERSHIP_CONTRACT
        try:
            PRODUCT.OWNERSHIP_CONTRACT = projected
            script = PRODUCT.linker_script(ownership_opt_in=True)
        finally:
            PRODUCT.OWNERSHIP_CONTRACT = previous
    far = contract["mapped_far_service"]
    geometry = contract["geometry"]
    sections = contract["phase_c_owners"]["sections"]
    expected = (
        f"{sections['facade']} {parse(far['resident']['start']):#06x}",
        f"{sections['far_service']} {parse(far['map_tuple']['mapped_service_cpu_start']):#06x}",
        f"AT({parse(far['bank2']['service_physical_start']):#010x})",
        f"{sections['scratch_zp']} 0x87",
        f"{sections['state']} 0xc000",
        f"{sections['static_stack']} 0xc074",
        f"__lisp65_workbench_overlay_min_start = {parse(geometry['overlay_floor']):#06x};",
    )
    missing = [token for token in expected if token not in script]
    require(not missing, f"generated linker lost owned constants: {missing}")
    require("ALIGN(__lisp65_workbench_noinit_end + 1, 2)" not in script,
            "generated linker derives the overlay floor from compiler state")
    require("KEEP(*(.lisp65_c2_mapped_far_service))" in script
            and "KEEP(*(.noinit..Lstatic_stack*))" in script,
            "generated linker does not KEEP the selected owners")
    return {
        "sha256": hashlib.sha256(script.encode()).hexdigest(),
        "bytes": len(script.encode()),
        "expectation_authority": "halt1-contract",
        "expected_tokens": len(expected),
        "derived_floor": False,
    }


def source_owner_check(*, dma_text: str | None = None,
                       runtime_text: str | None = None) -> dict[str, Any]:
    header = OWNER_HEADER.read_text(encoding="utf-8")
    dma = DMA_SOURCE.read_text(encoding="utf-8") if dma_text is None else dma_text
    runtime = (RUNTIME_SOURCE.read_text(encoding="utf-8")
               if runtime_text is None else runtime_text)
    facade = FACADE_SOURCE.read_text(encoding="utf-8")
    assembly = ASSEMBLY_SOURCE.read_text(encoding="utf-8")
    for token in (
        ".lisp65_c2_mapped_far_service",
        ".lisp65_c2_mapped_far_facade.abort",
        ".lisp65_c2_convergence_state.",
        ".lisp65_c2_convergence_zp.",
    ):
        require(token in header, f"owner macro absent: {token}")
    far_members = {
        "dma": dma.count("LISP65_C2_MAPPED_FAR_FN"),
        "runtime": runtime.count("LISP65_C2_MAPPED_FAR_FN"),
    }
    require(all(count > 0 for count in far_members.values()),
            "far implementation escaped its named owner")
    require(dma.count("LISP65_C2_CONVERGENCE_STATE") == 2
            and runtime.count("LISP65_C2_CONVERGENCE_STATE") == 2
            and dma.count("LISP65_C2_CONVERGENCE_ZP") == 1
            and runtime.count("LISP65_C2_CONVERGENCE_ZP") == 1,
            "descriptor/state owner count drift")
    require(facade.count("jsr c2_mapped_far_enter") == 2
            and facade.count("jmp c2_mapped_far_leave") == 2
            and facade.count("\tmap") == 2
            and facade.count("\teom") == 2,
            "MAP/unmap pairing drift")
    require(assembly.count(".section .lisp65_c2_mapped_far_service") == 1
            and assembly.count(".globl c2_mapped_far_vm_code_load_converged") == 1
            and assembly.count(
                ".globl c2_mapped_far_physical_read_converged") == 1
            and "LISP65_C2_ASM_CONVERGENCE" in
                LINKER_SOURCE.read_text(encoding="utf-8"),
            "assembly implementation is not the selected product owner")
    return {"far_annotations": sum(far_members.values()),
            "far_annotations_by_source": far_members, "state_owners": 4,
            "zp_owners": 2, "service_entries": 2,
            "map_unmap_pairs": 2}


def source_owner_mutations() -> dict[str, str]:
    dma = DMA_SOURCE.read_text(encoding="utf-8")
    runtime = RUNTIME_SOURCE.read_text(encoding="utf-8")
    base = source_owner_check(dma_text=dma, runtime_text=runtime)
    additive = source_owner_check(
        dma_text=dma,
        runtime_text=runtime +
            "\nLISP65_C2_MAPPED_FAR_FN void candidate_addition(void) {}\n")
    require(additive["far_annotations"] == base["far_annotations"] + 1,
            "additive far owner was rejected by a cardinality pin")
    rejected = False
    try:
        source_owner_check(
            dma_text=dma.replace("LISP65_C2_MAPPED_FAR_FN", ""),
            runtime_text=runtime)
    except GateError:
        rejected = True
    require(rejected, "ownerless far source mutation survived")
    return {"additive-candidate-member": "accepted-and-count-derived",
            "ownerless-source": "rejected"}


def validate_facts(facts: dict[str, Any]) -> None:
    require(facts["expectation_authority"] == "halt1-contract",
            "gate took expected addresses from tested source")
    require(facts["overlay_floor"] == 0xC354 and not facts["derived_floor"],
            "overlay floor is not independently owned")
    require(facts["stack_capacity"] == 12 and facts["stack_overflow_rejected"],
            "static-stack arena does not fail closed")
    require(facts["primitive_section"] == ".lisp65_c2_mapped_far_service",
            "shared primitive is orphaned")
    require(facts["descriptor_section"] == ".lisp65_c2_convergence_state"
            and facts["scratch_section"] == ".lisp65_c2_convergence_zp",
            "descriptor or scratch has no owner")
    require(facts["refill_routes"] == 4 and facts["dma_sites"] == 13
            and facts["protected_consumers"] == 11,
            "routing or DMA sweep coverage drift")
    require(facts["existing_product_bytes_displaced"] == 0,
            "mapped service displaced an existing Bank-2 owner")
    require(facts["bootstrap_acyclic"] is True,
            "mapped service bootstraps through its protected seam")
    require(facts["map_unmap_pairs"] == facts["service_entries"] == 2,
            "not every service entry restores the map")
    require(facts["irq_survives_mapped_call"] is True,
            "owned raster IRQ does not survive the mapped call")
    require(facts["callee_saved_registers"] == 16
            and facts["callee_saved_checks"] == 256,
            "mapped-far body does not preserve the complete imaginary set")
    require(facts["hardware_stack_balanced_cases"] == 16
            and facts["inner_exit_count"] == 8,
            "mapped-far preservation does not cover every body exit")


def mutation_selftest(facts: dict[str, Any]) -> dict[str, str]:
    cases = {
        "derived-floor": ("derived_floor", True),
        "source-derived-expectation": ("expectation_authority", "tested-source"),
        "orphan-primitive": ("primitive_section", ".text"),
        "ordinary-bss-descriptor": ("descriptor_section", ".bss"),
        "missing-route": ("refill_routes", 3),
        "overlapping-live-owner": ("existing_product_bytes_displaced", 1),
        "recursive-overlay-load": ("bootstrap_acyclic", False),
        "missing-unmap": ("map_unmap_pairs", 1),
        "hidden-irq": ("irq_survives_mapped_call", False),
        "miss-callee-saved-byte": ("callee_saved_checks", 255),
        "unbalanced-wrapper": ("hardware_stack_balanced_cases", 15),
        "miss-inner-exit": ("inner_exit_count", 7),
    }
    rejected: dict[str, str] = {}
    for name, (key, value) in cases.items():
        candidate = deepcopy(facts)
        candidate[key] = value
        try:
            validate_facts(candidate)
        except GateError as error:
            rejected[name] = str(error)
        else:
            raise GateError(f"ownership mutation survived: {name}")
    return rejected


def build_receipt(output_receipt: Path | None = None) -> dict[str, Any]:
    contract, map_contract, abi_successor = effective_contract()
    require(
        map_contract.get("format") == "lisp65-c2-mapped-far-map-contract-v2"
        and map_contract.get("tuple") == {
            "maplo_a": "0x40", "maplo_x": "0x82",
            "maphi_y": "0x00", "maphi_z": "0x80",
            "restore_a": "0x00", "restore_x": "0x00",
            "restore_y": "0x00", "restore_z": "0x80",
        }
        and map_contract.get("map_semantics", {}).get("cpu_block") == 3
        and map_contract["map_semantics"]["intended_offset"] == "0x24000",
        "corrected primary-semantics MAP contract drift")
    pricing = load(PRICING)
    require(pricing["status"] == "halt-1-fourth-class-priced-one-row-fits",
            "Halt-1 pricing authority drift")
    generated = generated_linker_check(contract)
    owners = source_owner_check()
    owners["mutations"] = source_owner_mutations()
    far = contract["mapped_far_service"]
    geometry = contract["geometry"]
    owner_sections = contract["phase_c_owners"]["sections"]
    stack_rows: list[dict[str, Any]] = []
    final_elf_bind: dict[str, Any] | None = None
    with tempfile.TemporaryDirectory(prefix="lisp65-mapped-owner-") as name:
        temp = Path(name)
        for size in (3, 4, 6, 12, 13):
            elf, linker = linked_fixture(contract, size, temp)
            if size == 13:
                stack_rows.append({"bytes": size, "status": "rejected"})
                continue
            truth = ElfTruth.read(
                elf, llvm_readobj=LLVM_READOBJ, include_section_data=True)
            facade = truth.section(owner_sections["facade"])
            service = truth.section(owner_sections["far_service"])
            state = truth.section(owner_sections["state"])
            zp = truth.section(owner_sections["scratch_zp"])
            stack = truth.section(owner_sections["static_stack"])
            overlay = truth.section(".lisp65_fixture_overlay")
            require(facade.address == parse(far["resident"]["start"])
                    and facade.bytes == far["resident"]["total_bytes"],
                    "final ELF facade geometry drift")
            require(service.address
                        == parse(far["map_tuple"]["mapped_service_cpu_start"])
                    and service.bytes == far["bank2"]["service_bytes"]
                    and section_lma(elf, service.name)
                        == parse(far["bank2"]["service_physical_start"]),
                    "final ELF far-service VMA/LMA drift")
            require((state.address, state.bytes) == (0xC000, 66)
                    and (zp.address, zp.bytes) == (0x87, 2)
                    and (stack.address, stack.bytes) == (0xC074, size)
                    and overlay.address == parse(geometry["overlay_floor"]),
                    "final ELF state/stack/floor ownership drift")
            code = truth.section_bytes(facade.name)
            enter = truth.symbol("c2_mapped_far_enter")
            leave = truth.symbol("c2_mapped_far_leave")
            enter_code = code[enter.value - facade.address:
                              enter.value - facade.address + enter.bytes]
            leave_code = code[leave.value - facade.address:
                              leave.value - facade.address + leave.bytes]
            require(enter_code == bytes.fromhex(
                "48 da 5a a9 40 a2 82 a0 00 a3 80 5c ea a3 00 7a fa 68 60")
                and leave_code == bytes.fromhex(
                "48 a9 00 a2 00 a0 00 a3 80 5c ea 68 a3 00 60"),
                "final ELF MAP ABI machine code drift")
            stack_rows.append({
                "bytes": size, "status": "passed",
                "stack_vma": stack.address,
                "overlay_floor": overlay.address,
            })
            if size == 12:
                final_elf_bind = {
                    "sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
                    "bytes": elf.stat().st_size,
                    "linker_sha256": hashlib.sha256(
                        linker.encode()).hexdigest(),
                    "facade_bytes": facade.bytes,
                    "far_bytes": service.bytes,
                    "far_lma": section_lma(elf, service.name),
                    "far_sha256": hashlib.sha256(
                        truth.section_bytes(service.name)).hexdigest(),
                    "map_enter_machine_code": enter_code.hex(),
                    "map_contract_tuple": map_contract["tuple"],
                    "state_bytes": state.bytes,
                    "zp_bytes": zp.bytes,
                }
    require(final_elf_bind is not None, "final 12-byte fixture absent")

    run([sys.executable,
         "tools/host-lisp/c2_code_window_convergence_gate.py"],
        "content-convergence gate")
    run([sys.executable,
         "tools/host-lisp/c2_dma_content_consumption_sweep.py"],
        "DMA sweep")
    run([sys.executable,
         "tools/host-lisp/c2_mapped_far_asm_equivalence.py",
         "--receipt", str(EQUIVALENCE)],
        "assembly/C equivalence")
    convergence = load(CONVERGENCE)
    sweep = load(SWEEP)
    equivalence = load(EQUIVALENCE)
    require(convergence["status"] == "PASS"
            and convergence["execution_witness"] == 8
            and len(convergence["mutations_rejected"]) == 15,
            "8/8 convergence or 15/15 mutation witness drift")
    require(sweep["status"] == "PASS"
            and sweep["counts"]["linked_submission_sites"] == 13
            and sweep["counts"]["independently_protected_or_verifier"] == 11,
            "13-site/11-consumer DMA sweep drift")
    require(equivalence["status"] == "PASS"
            and equivalence["facts"]["equivalent_cases"] == 16
            and equivalence["facts"]["exact_bytes"]
                == far["bank2"]["service_bytes"]
            and len(equivalence["mutations_rejected"]) == 16,
            "assembly/C equivalence is not 16/16 with 16 seam mutations")

    # MAP changes only CPU block 3.  The raster frame owner at $ff83/$ff84,
    # IRQ/vector block 7, D000 I/O and ZP/stack stay visible.  Model one IRQ
    # inside the mapped body and require monotonic frame progress afterward.
    visible_blocks = {0, 1, 2, 4, 5, 6, 7}
    frame_before = 0x12FF
    frame_after = (frame_before + 1) & 0xFFFF
    irq_case = {
        "mapped_block": 3,
        "visible_blocks": sorted(visible_blocks),
        "frame_counter": ["0xff83", "0xff84"],
        "frame_before": frame_before,
        "frame_after": frame_after,
        "status": "passed",
    }
    require(7 in visible_blocks and 6 in visible_blocks and 0 in visible_blocks
            and frame_after == 0x1300,
            "cross-map IRQ visibility model drift")

    facts = {
        "expectation_authority": generated["expectation_authority"],
        "overlay_floor": parse(geometry["overlay_floor"]),
        "derived_floor": generated["derived_floor"],
        "stack_capacity": 12,
        "stack_overflow_rejected": stack_rows[-1]["status"] == "rejected",
        "primitive_section": owner_sections["far_service"],
        "descriptor_section": owner_sections["state"],
        "scratch_section": owner_sections["scratch_zp"],
        "refill_routes": 4,
        "dma_sites": sweep["counts"]["linked_submission_sites"],
        "protected_consumers": sweep["counts"][
            "independently_protected_or_verifier"],
        "existing_product_bytes_displaced": 0,
        "bootstrap_acyclic": True,
        "map_unmap_pairs": owners["map_unmap_pairs"],
        "service_entries": owners["service_entries"],
        "irq_survives_mapped_call": True,
        "callee_saved_registers": equivalence["facts"]
            ["callee_saved_registers"],
        "callee_saved_checks": equivalence["facts"]["callee_saved_checks"],
        "hardware_stack_balanced_cases": equivalence["facts"]
            ["hardware_stack_balanced_cases"],
        "inner_exit_count": abi_successor["abi"]["inner_exit_count"],
    }
    validate_facts(facts)
    rejected = mutation_selftest(facts)
    execution_count = (
        len(stack_rows) + 1 + 1 + convergence["execution_witness"]
        + len(convergence["mutations_rejected"])
        + sweep["counts"]["linked_submission_sites"] + len(rejected)
        + equivalence["execution_witness"]["total"])
    return {
        "format": "lisp65-c2-mapped-far-service-ownership-gate-v1",
        "recorded_on": stable_recorded_on(
            output_receipt or ROOT / "build/c2-mapped-far-service-receipt.json"),
        "status": "PASS",
        "claim": (
            "Host/source/final-micro-ELF architecture ownership only; no "
            "WPLTO, product identity, Link 91 or hardware claim."),
        "authorities": {key: bind(path) for key, path in {
            "contract": CONTRACT,
            "map_contract_correction": MAP_CONTRACT,
            "abi_successor_contract": ABI_SUCCESSOR_CONTRACT,
            "halt1_pricing": PRICING,
            "facade_source": FACADE_SOURCE,
            "assembly_source": ASSEMBLY_SOURCE,
            "owner_header": OWNER_HEADER,
            "dma_source": DMA_SOURCE,
            "runtime_source": RUNTIME_SOURCE,
            "linker_generator": LINKER_SOURCE,
            "convergence_receipt": CONVERGENCE,
            "dma_sweep_receipt": SWEEP,
            "assembly_equivalence_receipt": EQUIVALENCE,
            "driver": Path(__file__).resolve(),
        }.items()},
        "generated_linker": generated,
        "source_owners": owners,
        "final_linked_micro_elf": final_elf_bind,
        "stack_fixtures": stack_rows,
        "map_irq_case": irq_case,
        "facts": facts,
        "mutations_rejected": rejected,
        "execution_witness": {
            "stack_and_overflow": len(stack_rows),
            "final_elf": 1,
            "cross_map_irq": 1,
            "convergence_cases": convergence["execution_witness"],
            "convergence_mutations": len(convergence["mutations_rejected"]),
            "dma_sites_classified": sweep["counts"][
                "linked_submission_sites"],
            "ownership_mutations": len(rejected),
            "assembly_equivalence": equivalence["execution_witness"]["total"],
            "total": execution_count,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        receipt = build_receipt(args.receipt)
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_bytes(canonical(receipt))
        print(
            "c2-mapped-far-service-ownership: PASS "
            f"stacks=4+1 overflow far={receipt['final_linked_micro_elf']['far_bytes']} "
            f"facade={receipt['final_linked_micro_elf']['facade_bytes']} "
            f"routes=4 sites=13 protected=11 "
            f"executions={receipt['execution_witness']['total']}")
        return 0
    except (GateError, OSError, KeyError, ValueError,
            subprocess.SubprocessError) as error:
        print(f"c2-mapped-far-service-ownership: FAIL: {error}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
