#!/usr/bin/env python3
"""Inventory Link 75's symbol-read DMA seams and prepare one bundled probe.

This is deliberately attribution-only.  It does not change product sources,
build a product link or authorize a hardware run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_crc_codegen_gate as DISASM  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ELF = ROOT / (
    "build/post-promotion/link75-bound-compiler-carrier/final/"
    "lisp65-c2-substitution-linked.prg.elf")
PRODUCT = ROOT / (
    "build/post-promotion/link75-bound-compiler-carrier/final/"
    "lisp65-c2-substitution-linked.prg")
SESSION = ROOT / (
    "build/post-promotion/link75-bound-compiler-carrier/final/"
    "runtime-overlays-session-final.bin")
SOURCE = ROOT / "src/c2_platform_dma.c"
SYMBOL_SOURCE = ROOT / "src/symbol.c"
RUNTIME_HEADER = ROOT / "src/c2_product_runtime.h"
OVERLAY_SOURCE = ROOT / "src/vm_runtime_overlay.c"
CONTRACT = ROOT / "config/c2-symbol-read-completion-investigation.json"
PRE_SYMNAME_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-dirmiss-detail-hold-nonpromotable-receipt.json")
REAL_RESOLVER_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-real-require-resolver-host-receipt.json")
OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-symbol-read-completion-static-attribution.json")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"

ERROR_OVERLAY_SLOT = 47
ERROR_OVERLAY_VMA = 0xC356
ERROR_OVERLAY_FILE_OFFSET = 0xEA00
SYMNAME_CALL_VMA = 0xC46F
POST_SYMNAME_HOLD_VMA = 0xC472
POST_SYMNAME_HOLD_FILE_OFFSET = (
    ERROR_OVERLAY_FILE_OFFSET
    + POST_SYMNAME_HOLD_VMA
    - ERROR_OVERLAY_VMA
)
POST_SYMNAME_BEFORE = bytes.fromhex("85 04")
POST_SYMNAME_AFTER = bytes.fromhex("80 fe")
LINK75_PUBLISHED_C2D_END = 33840
REGION1_FLOOR = 0xBD00
MIXED_RECORD_BYTES = 64


class InventoryError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise InventoryError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"bound input absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode(
        "ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == data, f"receipt drift: {path}")
        return
    with tempfile.NamedTemporaryFile(
            dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    temporary.replace(path)


def disassembly() -> list[dict[str, Any]]:
    completed = subprocess.run(
        [str(OBJDUMP), "-d", "--no-show-raw-insn", str(ELF)],
        check=True, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    return DISASM.disassembly_rows(completed.stdout)


def function_symbols(truth: ElfTruth) -> list[Any]:
    return [
        row for row in truth.symbols
        if row.symbol_type == "Function" and row.bytes > 0
        and row.section not in ("Absolute", "Undefined")
    ]


def owners_at(truth: ElfTruth, section: str, address: int) -> list[str]:
    return sorted(
        row.name for row in function_symbols(truth)
        if row.section == section
        and row.value <= address < row.value + row.bytes)


def call_edges(truth: ElfTruth, rows: list[dict[str, Any]],
               target: str) -> list[dict[str, Any]]:
    symbol = truth.symbol(target)
    needle = f"${symbol.value:x}"
    result = []
    for row in rows:
        if row["opcode"] not in ("jsr", "jmp"):
            continue
        if str(row["operand"]).split()[0].lower() != needle:
            continue
        address = int(row["address"])
        result.append({
            "section": row["section"],
            "address": f"0x{address:04x}",
            "edge": row["opcode"].upper(),
            "owners": owners_at(truth, row["section"], address),
        })
    return result


def facade_edges(truth: ElfTruth) -> list[dict[str, Any]]:
    functions = function_symbols(truth)
    result = []
    for row in truth.relocations:
        if row.target != "c2_facade_c2_dma":
            continue
        owners = sorted(
            item.name for item in functions
            if item.section_index == row.source_section_index
            and item.value <= row.offset < item.value + item.bytes)
        require(len(owners) == 1,
                f"facade edge has no unique function owner: {row}")
        result.append({
            "owner": owners[0],
            "section": row.source_section,
            "relocation_offset": f"0x{row.offset:04x}",
            "relocation_type": row.relocation_type,
        })
    return sorted(result, key=lambda item: (
        item["section"], item["relocation_offset"], item["owner"]))


def require_edge_owners(
        edges: dict[str, list[dict[str, Any]]],
        expected: dict[str, list[str]]) -> None:
    for target, owners in expected.items():
        observed = sorted(
            owner for row in edges[target] for owner in row["owners"])
        require(observed == sorted(owners),
                f"{target} linked caller inventory drift: "
                f"{observed} != {sorted(owners)}")


def classify_measurement(
        *, single_immediate_mismatches: int,
        single_settled_mismatches: int,
        paired_first_mismatches: int,
        paired_second_mismatches: int,
        mixed_failure_batches: tuple[
            tuple[tuple[int, ...], ...], ...],
        observation_hashes: tuple[int, int, int]) -> dict[str, str]:
    require(len(mixed_failure_batches) == 3,
            "mixed lane requires exactly three batches")
    require(all(len(batch) == 3 for batch in mixed_failure_batches),
            "each mixed batch requires Prim67/roundtrip64/cell2 bitmaps")
    require(all(
        all(0 <= iteration < 256 for iteration in bitmap)
        for batch in mixed_failure_batches for bitmap in batch),
        "mixed failure iteration outside the 256-iteration batch")
    require(
        len(observation_hashes) == 3
        and all(0 <= value <= 0xffff for value in observation_hashes),
        "mixed lane requires three uint16 observation hashes")

    mixed_has_failure = any(
        bitmap
        for batch in mixed_failure_batches for bitmap in batch)
    if not mixed_has_failure:
        mixed = "M0-mixed-sequence-stable"
    elif all(
            batch == mixed_failure_batches[0]
            for batch in mixed_failure_batches[1:]) \
            and observation_hashes[1:] == observation_hashes[:1] * 2:
        mixed = "MD-mixed-sequence-deterministic"
    else:
        mixed = "MI-mixed-sequence-intermittent"

    if single_immediate_mismatches > single_settled_mismatches:
        homogeneous = (
            "A-single-job-destination-converges-with-descriptor-untouched")
    elif single_immediate_mismatches == 0 \
            and single_settled_mismatches == 0 \
            and (paired_first_mismatches or paired_second_mismatches):
        homogeneous = "B-shared-descriptor-or-back-to-back-submission"
    elif not any((
            single_immediate_mismatches, single_settled_mismatches,
            paired_first_mismatches, paired_second_mismatches)):
        homogeneous = "C-homogeneous-lanes-stable"
    else:
        homogeneous = (
            "D-read-seam-failure-without-discriminator-convergence")
    if mixed == "MD-mixed-sequence-deterministic":
        implication = "attribute-order-or-descriptor-discipline-first"
    elif mixed == "MI-mixed-sequence-intermittent":
        implication = "attribute-content-defined-completion-first"
    elif homogeneous.startswith("A-"):
        implication = "attribute-content-defined-completion-first"
    elif homogeneous.startswith("B-"):
        implication = "attribute-order-or-descriptor-discipline-first"
    elif homogeneous.startswith("D-"):
        implication = "return-to-review-no-fix"
    else:
        implication = "no-reproduction-no-fix"
    return {
        "homogeneous": homogeneous,
        "mixed": mixed,
        "fix_class": implication,
    }


def classify_campaign(
        *, post_symname_scratch_matches: bool,
        single_immediate_mismatches: int,
        single_settled_mismatches: int,
        paired_first_mismatches: int,
        paired_second_mismatches: int,
        mixed_failure_batches: tuple[
            tuple[tuple[int, ...], ...], ...],
        observation_hashes: tuple[int, int, int]) -> dict[str, str]:
    result = classify_measurement(
        single_immediate_mismatches=single_immediate_mismatches,
        single_settled_mismatches=single_settled_mismatches,
        paired_first_mismatches=paired_first_mismatches,
        paired_second_mismatches=paired_second_mismatches,
        mixed_failure_batches=mixed_failure_batches,
        observation_hashes=observation_hashes)
    result["renderer"] = (
        "R-post-symname-scratch-correct-renderer-consumption"
        if post_symname_scratch_matches
        else "S-post-symname-scratch-damaged-reader-interval")
    return result


def selftest() -> dict[str, Any]:
    stable = (((), (), ()), ((), (), ()), ((), (), ()))
    deterministic = (
        ((7,), (), ()),
        ((7,), (), ()),
        ((7,), (), ()))
    intermittent = (
        ((7,), (), ()),
        ((), (), ()),
        ((31,), (), ()))
    cases = [
        ((True, 9, 9, 9, 9, stable, (1, 1, 1)), {
            "renderer": "R-post-symname-scratch-correct-renderer-consumption",
            "homogeneous":
                "D-read-seam-failure-without-discriminator-convergence",
            "mixed": "M0-mixed-sequence-stable",
            "fix_class": "return-to-review-no-fix",
        }),
        ((False, 4, 0, 0, 0, stable, (1, 1, 1)), {
            "renderer": "S-post-symname-scratch-damaged-reader-interval",
            "homogeneous":
                "A-single-job-destination-converges-with-descriptor-untouched",
            "mixed": "M0-mixed-sequence-stable",
            "fix_class": "attribute-content-defined-completion-first",
        }),
        ((False, 1, 0, 3, 2, stable, (1, 1, 1)), {
            "renderer": "S-post-symname-scratch-damaged-reader-interval",
            "homogeneous":
                "A-single-job-destination-converges-with-descriptor-untouched",
            "mixed": "M0-mixed-sequence-stable",
            "fix_class": "attribute-content-defined-completion-first",
        }),
        ((False, 0, 0, 1, 0, stable, (1, 1, 1)), {
            "renderer": "S-post-symname-scratch-damaged-reader-interval",
            "homogeneous":
                "B-shared-descriptor-or-back-to-back-submission",
            "mixed": "M0-mixed-sequence-stable",
            "fix_class": "attribute-order-or-descriptor-discipline-first",
        }),
        ((False, 0, 0, 0, 1, stable, (1, 1, 1)), {
            "renderer": "S-post-symname-scratch-damaged-reader-interval",
            "homogeneous":
                "B-shared-descriptor-or-back-to-back-submission",
            "mixed": "M0-mixed-sequence-stable",
            "fix_class": "attribute-order-or-descriptor-discipline-first",
        }),
        ((False, 0, 0, 0, 0, stable, (1, 1, 1)), {
            "renderer": "S-post-symname-scratch-damaged-reader-interval",
            "homogeneous": "C-homogeneous-lanes-stable",
            "mixed": "M0-mixed-sequence-stable",
            "fix_class": "no-reproduction-no-fix",
        }),
        ((False, 2, 2, 0, 0, stable, (1, 1, 1)), {
            "renderer": "S-post-symname-scratch-damaged-reader-interval",
            "homogeneous":
                "D-read-seam-failure-without-discriminator-convergence",
            "mixed": "M0-mixed-sequence-stable",
            "fix_class": "return-to-review-no-fix",
        }),
        ((False, 0, 0, 0, 0, deterministic, (2, 2, 2)), {
            "renderer": "S-post-symname-scratch-damaged-reader-interval",
            "homogeneous": "C-homogeneous-lanes-stable",
            "mixed": "MD-mixed-sequence-deterministic",
            "fix_class": "attribute-order-or-descriptor-discipline-first",
        }),
        ((True, 0, 0, 0, 0, intermittent, (3, 4, 5)), {
            "renderer": "R-post-symname-scratch-correct-renderer-consumption",
            "homogeneous": "C-homogeneous-lanes-stable",
            "mixed": "MI-mixed-sequence-intermittent",
            "fix_class": "attribute-content-defined-completion-first",
        }),
        ((False, 0, 0, 0, 0, deterministic, (6, 7, 6)), {
            "renderer": "S-post-symname-scratch-damaged-reader-interval",
            "homogeneous": "C-homogeneous-lanes-stable",
            "mixed": "MI-mixed-sequence-intermittent",
            "fix_class": "attribute-content-defined-completion-first",
        }),
    ]
    for values, expected in cases:
        observed = classify_campaign(
            post_symname_scratch_matches=values[0],
            single_immediate_mismatches=values[1],
            single_settled_mismatches=values[2],
            paired_first_mismatches=values[3],
            paired_second_mismatches=values[4],
            mixed_failure_batches=values[5],
            observation_hashes=values[6])
        require(observed == expected,
                f"measurement classifier mismatch: {values}")
    return {
        "status": "passed",
        "cases": len(cases),
        "accepted": len(cases),
    }


def build() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    rows = disassembly()
    source = SOURCE.read_text(encoding="utf-8")
    symbol_source = SYMBOL_SOURCE.read_text(encoding="utf-8")
    runtime_header = RUNTIME_HEADER.read_text(encoding="utf-8")
    overlay_source = OVERLAY_SOURCE.read_text(encoding="utf-8")

    for token in (
            "__attribute__((used)) uint8_t c2_dma_list[12];",
            'sta $d700\\n\\t"',
            '::: "a", "memory"',
            "void sympool_read(uint16_t offset, char *destination, "
            "uint16_t length)",
            "obj symval_get(uint16_t index)",
            "uint16_t nameoff_get(uint16_t index)",
            "obj symfn_ext_get(uint16_t index)"):
        require(token in source, f"symbol transport source token absent: {token}")
    require("$d705" not in source.lower(),
            "symbol transport acquired an Enhanced-DMA trigger")
    require("busy" not in source.lower() and "completion" not in source.lower(),
            "symbol transport unexpectedly acquired a completion observation")
    for token in (
            "sympool_read(off, buf, LISP65_SYMBOL_NAME_BUFFER);",
            "sympool_read(off, sym_name_scratch, "
            "LISP65_SYMBOL_NAME_BUFFER);",
            "obj  sym_value(obj s)",
            "obj  sym_function(obj s)"):
        require(token in symbol_source,
                f"symbol consumer source token absent: {token}")
    require(
        "#define LISP65_C2D_BYTES 33840u" in runtime_header,
        "Link75 published C2D end drift")
    require(
        "#define LISP65_RUNTIME_OVERLAY_REGION1_ADDRESS      0xbd00u"
        in overlay_source,
        "Link75 Region-1 floor drift")
    require(
        LINK75_PUBLISHED_C2D_END + MIXED_RECORD_BYTES <= REGION1_FLOOR,
        "mixed diagnostic record crosses the Region-1 floor")

    descriptor = truth.symbol("c2_dma_list")
    require(descriptor.bytes == 12 and descriptor.section == ".bss",
            "shared symbol/code DMA descriptor geometry drift")

    targets = (
        "nameoff_get", "sympool_read", "sym_value", "sym_function",
        "symname")
    edges = {name: call_edges(truth, rows, name) for name in targets}
    require_edge_owners(edges, {
        "nameoff_get": [
            "intern", "eval_v2_workbench_service", "symname"],
        "sympool_read": ["intern", "symname"],
        "sym_value": ["gc_collect", "vm_callprim", "eval"],
        "sym_function": [
            "gc_collect", "dir_find", "vm_native_call",
            "eval_v2_workbench_service", "eval_v2_workbench_service",
            "eval", "c2_append_publish_plan_resolve_phase"],
        "symname": [
            "eval_v2_workbench_service", "print_obj",
            "c2_session_emit_name_phase", "c2e_prepare_atom",
            "c2e_prepare_atom", "lisp65_error_overlay_entry"],
    })

    all_facade = facade_edges(truth)
    physical_read_owners = {
        "nameoff_get", "sympool_read", "sym_value", "sym_function"}
    observed_read_owners = {
        row["owner"] for row in all_facade
        if row["owner"] in physical_read_owners}
    require(observed_read_owners == physical_read_owners,
            "not every physical symbol read reaches the shared DMA facade")
    require(sum(
        1 for row in all_facade if row["owner"] in physical_read_owners
    ) == 4, "physical symbol-read facade edge count drift")

    target_body = [
        row for row in rows
        if row["section"] == truth.symbol(
            "c2_facade_target_c2_dma").section
        and truth.symbol("c2_facade_target_c2_dma").value
        <= int(row["address"])
        < truth.symbol("c2_facade_target_c2_dma").value
        + truth.symbol("c2_facade_target_c2_dma").bytes
    ]
    instructions = [
        (row["opcode"],
         (str(row["operand"]).split()[0].lower()
          if str(row["operand"]).split() else ""))
        for row in target_body
    ]
    require(("sta", "$d700") in instructions,
            "linked symbol transport lacks D700 trigger")
    require(not any(operand == "$d705" for _, operand in instructions),
            "linked symbol transport unexpectedly uses D705")
    trigger = next(
        index for index, item in enumerate(instructions)
        if item == ("sta", "$d700"))
    require(instructions[trigger + 1][0] == "rts",
            "linked symbol transport no longer returns immediately after D700")

    symname_call_rows = [
        row for row in rows
        if row["section"] == truth.symbol(
            "lisp65_error_overlay_entry").section
        and int(row["address"]) == SYMNAME_CALL_VMA
    ]
    require(
        len(symname_call_rows) == 1
        and symname_call_rows[0]["opcode"] == "jsr"
        and str(symname_call_rows[0]["operand"]).split()[0].lower()
            == f"${truth.symbol('symname').value:x}",
        "Link75 error-overlay symname call edge drift")
    post_return_rows = [
        row for row in rows
        if row["section"] == truth.symbol(
            "lisp65_error_overlay_entry").section
        and int(row["address"]) == POST_SYMNAME_HOLD_VMA
    ]
    require(
        len(post_return_rows) == 1
        and post_return_rows[0]["opcode"] == "sta"
        and str(post_return_rows[0]["operand"]).split()[0].lower() == "$4",
        "Link75 post-symname return edge drift")
    session = SESSION.read_bytes()
    require(
        session[
            POST_SYMNAME_HOLD_FILE_OFFSET:
            POST_SYMNAME_HOLD_FILE_OFFSET + 2
        ] == POST_SYMNAME_BEFORE,
        "Link75 post-symname patch bytes drift")

    return {
        "format": "lisp65-c2.2-symbol-read-completion-static-attribution-v2",
        "recorded_on": "2026-07-28",
        "status": (
            "passed-inventory-real-resolver-green-mixed-DMA-before-require"),
        "authority": {
            "product": bind(PRODUCT),
            "elf": bind(ELF),
            "session_family": bind(SESSION),
            "transport_source": bind(SOURCE),
            "symbol_source": bind(SYMBOL_SOURCE),
            "runtime_geometry_header": bind(RUNTIME_HEADER),
            "runtime_overlay_source": bind(OVERLAY_SOURCE),
            "investigation_contract": bind(CONTRACT),
            "pre_symname_capture_receipt": bind(PRE_SYMNAME_RECEIPT),
            "real_resolver_host_receipt": bind(REAL_RESOLVER_RECEIPT),
        },
        "physical_seam": {
            "descriptor": {
                "symbol": descriptor.name,
                "address": f"0x{descriptor.value:04x}",
                "bytes": descriptor.bytes,
                "section": descriptor.section,
                "single_owner": "c2_facade_target_c2_dma",
            },
            "transport": {
                "trigger": "$D700",
                "list_format": "normal F018B",
                "descriptor_bytes": 12,
                "post_trigger_instruction": "RTS",
                "software_completion_observation": "none",
                "software_busy_register":
                    "none documented by the bound completion contract",
                "compiler_ordering": "inline-asm memory clobber present",
            },
            "all_linked_facade_edges": all_facade,
            "symbol_read_facade_edges": [
                row for row in all_facade
                if row["owner"] in physical_read_owners],
        },
        "consumer_inventory": {
            "linked_call_edges": edges,
            "temperature": [
                {
                    "seam": "sym_function/symfn_get",
                    "class": "hot-critical",
                    "frequency": (
                        "dir_find reads once for every VM CALL/TAILCALL; "
                        "additional native/tree evaluator and GC consumers"),
                    "linked_static_call_edges": len(edges["sym_function"]),
                    "fix_constraint":
                        "no per-call CRC or frame-bounded retry",
                },
                {
                    "seam": "sym_value/symval_get",
                    "class": "warm-runtime",
                    "frequency": (
                        "global value lookup in VM/tree evaluation and one "
                        "read per symbol during GC"),
                    "linked_static_call_edges": len(edges["sym_value"]),
                    "fix_constraint":
                        "no unbounded or frame-scale per-cell retry",
                },
                {
                    "seam": "nameoff_get + sympool_read in intern",
                    "class": "cold-bursty",
                    "frequency": (
                        "one nameoff plus one 34-byte pool read for each "
                        "length-filtered candidate; repeated per Reader/"
                        "compiler/service intern"),
                    "linked_static_call_edges":
                        len(edges["nameoff_get"]) + len(edges["sympool_read"]),
                    "fix_constraint":
                        "transaction/order amortization is permitted",
                },
                {
                    "seam": "symname",
                    "class": "cold",
                    "frequency": (
                        "printer, diagnostic renderer, session emitter and "
                        "workbench metadata only"),
                    "linked_static_call_edges": len(edges["symname"]),
                    "fix_constraint":
                        "content-defined retry is affordable if required",
                },
            ],
        },
        "static_discriminator": {
            "epistemic_correction": (
                "the Link75 hold is before JSR symname; it proves correct "
                "scratch before the call and corrupt displayed output, but "
                "does not prove that symname overwrote the scratch"),
            "remaining_interval": (
                "symname call plus renderer pointer/length consumption"),
            "documented_CPU_semantics":
                "normal D700 DMA stops instruction execution until completion",
            "descriptor_race_status": (
                "not statically established: no product IRQ/NMI owner writes "
                "c2_dma_list, and documented CPU-stall semantics forbid CPU "
                "overwrite while a normal job is active"),
            "nonconvergence_status": (
                "not statically established: current Link75 capture proves "
                "correct storage and pre-symname scratch, but captured neither "
                "post-symname scratch nor the two post-trigger destinations"),
            "why_hardware_row_remains_required": (
                "the observed result contradicts at least one shared model "
                "assumption; additionally, the exact host resolver performs "
                "399 Prim-67 reads while physical Bank-5 transport remains "
                "outside its claim, so renderer exoneration cannot cancel "
                "the DMA measurement"),
        },
        "bundled_measurement": {
            "hardware_runs_authorized": 0,
            "identity": (
                "one future-successor nonpromotable diagnostic family with "
                "post-symname and unconditional DMA variants"),
            "stage0_post_symname_hold": {
                "row_position":
                    "first diagnostic row of the next already-required session",
                "trigger": "(intern-renderer-missing)",
                "capture":
                    "sym_name_scratch immediately after JSR symname returns",
                "link75_feasibility": {
                    "slot": ERROR_OVERLAY_SLOT,
                    "slot_vma": f"0x{ERROR_OVERLAY_VMA:04x}",
                    "symname_call_vma": f"0x{SYMNAME_CALL_VMA:04x}",
                    "hold_vma": f"0x{POST_SYMNAME_HOLD_VMA:04x}",
                    "session_family_file_offset":
                        POST_SYMNAME_HOLD_FILE_OFFSET,
                    "before": POST_SYMNAME_BEFORE.hex(),
                    "after": POST_SYMNAME_AFTER.hex(),
                    "size_delta": 0,
                    "ordering":
                        "before STA __rc2 and every renderer read",
                },
                "correct_scratch": (
                    "symname and its DMA reads are exonerated for the DIRMISS "
                    "finding; attribute renderer consumption, then continue "
                    "the independent resolver DMA row"),
                "damaged_scratch": (
                    "continue to stage1 in the same device appointment"),
            },
            "stage1_DMA_before_require": {
                "condition": (
                    "always run before another require retry; the compiled "
                    "resolver's 399 host reads do not prove physical DMA"),
                "row": "(symbol-read-completion-probe)",
                "iterations": 256,
                "batches": 3,
                "source": (
                    "same two bytes in Bank 5 NAMEOFF_EXT, address rebound "
                    "from the successor ELF and verified by read-only JTAG"),
                "single_lane": (
                    "poison A; submit one two-byte D700/F018B read; save A "
                    "immediately; leave c2_dma_list untouched; save A again "
                    "after a bounded settle interval"),
                "paired_lane": (
                    "poison disjoint A/B; submit A then immediately rebuild "
                    "the same c2_dma_list and submit the same source to B; "
                    "compare A, B and the read-only Bank5 source"),
                "mixed_lane": {
                    "preconditions": [
                        "C2J CLEAR",
                        "append/emitter phase-scratch owner NONE",
                        "all Bank0 buffers owned by the nonpromotable probe",
                    ],
                    "link75_scratch_geometry": {
                        "published_c2d_end": LINK75_PUBLISHED_C2D_END,
                        "published_c2d_end_hex":
                            f"0x{LINK75_PUBLISHED_C2D_END:04x}",
                        "bytes": MIXED_RECORD_BYTES,
                        "end_exclusive":
                            LINK75_PUBLISHED_C2D_END + MIXED_RECORD_BYTES,
                        "end_exclusive_hex": (
                            f"0x{LINK75_PUBLISHED_C2D_END + MIXED_RECORD_BYTES:04x}"),
                        "region1_floor": REGION1_FLOOR,
                        "region1_floor_hex": f"0x{REGION1_FLOOR:04x}",
                        "successor_rule": (
                            "rederive the published end and exact meet; "
                            "do not inherit the Link75 address"),
                    },
                    "sequence": [
                        {
                            "step": "prim67-byte",
                            "operation": "actual %c2d-byte(0,0)",
                            "source": "Bank5 C2D offset 0",
                            "target": "diagnostic Bank0 byte",
                            "direction": "Bank5->Bank0",
                            "bytes": 1,
                            "expected": "0x43",
                        },
                        {
                            "step": "record-seed",
                            "operation": (
                                "D700/F018B copy of an iteration/index-"
                                "derived record pattern"),
                            "source": "diagnostic Bank0 record",
                            "target": (
                                "Bank5 uncommitted append scratch at the "
                                "live published C2D end"),
                            "direction": "Bank0->Bank5",
                            "bytes": MIXED_RECORD_BYTES,
                        },
                        {
                            "step": "record-readback",
                            "operation": (
                                "after seed return, poison and lifetime-reuse "
                                "the probe-owned Bank0 record, then copy back"),
                            "source": (
                                "Bank5 uncommitted append scratch at the "
                                "live published C2D end"),
                            "target": "lifetime-reused diagnostic Bank0 record",
                            "direction": "Bank5->Bank0",
                            "bytes": MIXED_RECORD_BYTES,
                            "expected": "exact record-seed bytes",
                        },
                        {
                            "step": "cell-word",
                            "operation": "real canonical lisp_t value-cell read",
                            "source": "Bank5 symbol value cell for live lisp_t",
                            "target": "diagnostic Bank0 word",
                            "direction": "Bank5->Bank0",
                            "bytes": 2,
                            "expected": "live lisp_t tagged word",
                        },
                    ],
                    "write_scope": (
                        "unpublished append scratch only; no product code, "
                        "published C2D, symbol cell, Service record or counter"),
                },
                "reproducibility": {
                    "batches": 3,
                    "iterations_per_batch": 256,
                    "required_receipt_fields": [
                        "one 256-bit failure bitmap per checked mixed observation and batch",
                        "first failing substep and byte sample",
                        "hash of each complete ordered observation stream",
                        "stable/deterministic/intermittent classification",
                    ],
                    "stable": "all mixed failure bitmaps zero",
                    "deterministic": (
                        "nonzero complete failure signatures are byteidentical "
                        "in all three batches"),
                    "intermittent": (
                        "at least one mixed failure occurs and complete batch "
                        "signatures differ"),
                },
                "witness": (
                    "magic, rebound source address, immediate/settled samples "
                    "and four u16 homogeneous mismatch counters plus mixed "
                    "bitmaps/samples/hashes in diagnostic-only scratch"),
            },
            "execution": (
                "stage0 runs first and stage1 follows in the same device "
                "appointment regardless of the renderer outcome; another "
                "canonical require retry is allowed only after classification; "
                "discard every diagnostic variant afterward"),
            "outcomes": {
                "R": (
                    "post-symname scratch matches: renderer consumption is "
                    "the failing DIRMISS layer; DMA still runs for resolver "
                    "transport"),
                "A": (
                    "single immediate mismatches decrease with descriptor "
                    "untouched: genuine destination nonconvergence"),
                "B": (
                    "single lane is stable but paired lane differs: shared "
                    "descriptor/back-to-back submission lifetime"),
                "C": (
                    "both lanes stable: no reproduction; do not choose a fix"),
                "D": (
                    "single lane remains wrong without convergence: read seam "
                    "is confirmed but this discriminator is insufficient"),
                "MD": (
                    "mixed sequence fails at the same iteration/substep with "
                    "the same samples in all batches: deterministic boundary "
                    "failure; attribute ordering/descriptor discipline first"),
                "MI": (
                    "mixed failure signatures vary: intermittent boundary "
                    "failure; attribute content-defined completion first"),
                "M0": (
                    "all mixed bitmaps are zero: real-shape sequence did not "
                    "reproduce and authorizes no fix"),
            },
            "classifier_selftest": selftest(),
        },
        "historical_reconciliation": {
            "link72_defstruct_red_frame": {
                "status": "plausibly-related-not-closed",
                "reason": (
                    "22 intern calls create the largest known burst of "
                    "nameoff/pool reads through this descriptor; however the "
                    "stale carrier and STZ IRQ-latch findings are independent "
                    "coexisting mechanisms and no Link72 symbol-read witness "
                    "was captured"),
            },
            "intermittent_dynamic_BADOPCODE_series": {
                "status": "not-reclassified",
                "reason": (
                    "phase stamps and later host/ELF proofs attributed those "
                    "specific stops to suffix/Attic, plan and completion "
                    "mechanisms; a possible symbol-read contribution is not "
                    "evidence against those named causes"),
            },
            "earlier_DIRMISS_symptoms": {
                "status": "mechanistically-compatible-only",
                "reason": (
                    "sym_function is read on every dir_find edge and a stale "
                    "two-byte stack target could yield NIL, a stale BCODE or "
                    "a stale pointer; no older capture binds such a value to "
                    "this seam"),
            },
            "freezer_red_frames": {
                "status": "not-reclassified",
                "reason": (
                    "the STZ/Z and episode-latch mechanisms were independently "
                    "proved and remain the authoritative causes"),
            },
        },
        "decision_boundary": (
            "No product fix is selected. Outcome R sends the renderer to "
            "fix-form review but does not cancel resolver DMA work. Outcome A permits "
            "completion only on cold/bursty consumers unless a hot-safe "
            "amortized form is proved; outcome B permits descriptor/order "
            "discipline. MD prioritizes an attributed ordering fix; MI "
            "prioritizes attributed content-defined completion. M0, C or D "
            "authorizes no product change."),
        "execution_accounting": {
            "compiler_runs": 0,
            "product_links": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "Link75 static inventory, corrected pre-symname evidence boundary "
            "and future single/paired/mixed DMA-before-require measurement "
            "contract only; no renderer "
            "fault, normal-DMA core defect, descriptor race, product fix, new "
            "link, hardware result or closure is claimed."),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        print(json.dumps(selftest(), sort_keys=True))
        return
    value = build()
    write_json(OUT, value)
    print(
        "c2-symbol-read-completion-inventory: "
        f"{value['status']} "
        f"reads={len(value['physical_seam']['symbol_read_facade_edges'])} "
        f"mutations={value['bundled_measurement']['classifier_selftest']['accepted']}")


if __name__ == "__main__":
    main()
