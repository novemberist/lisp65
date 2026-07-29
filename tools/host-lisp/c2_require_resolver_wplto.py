#!/usr/bin/env python3
"""Run the cold require resolver through one product-shaped WPLTO."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_f1_published_value_call_wplto as F1W  # noqa: E402
import c2_f2_bitops_wplto as F2  # noqa: E402
import c2_lite_canonical_product as CAN  # noqa: E402
import c2_l_full_static_plane_gate as PLANE  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_substitution_artifacts as SUBSTITUTION  # noqa: E402
import c2_require_resolver_gate as RESOLVER  # noqa: E402


BASE = ROOT / "build/post-promotion/require-resolver"
STATIC = BASE / "narrow-static"
STATIC_PRODUCT = STATIC / "product"
V6_OUT = STATIC / "v6-semantics"
BUILD = BASE / "private-c2d-byte-asm-leaf-product-shaped-v11"
WPLTO = BUILD / "wplto"
RECEIPTS = BUILD / "receipts"
STATIC_RECEIPT = RECEIPTS / "require-static-plane-authority.json"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / "c2.2-require-resolver-wplto-receipt.json"
FIRST_RED_RECEIPT = EVIDENCE / (
    "c2.2-require-resolver-wplto-first-red.json")
NARROW_FIRST_RED_RECEIPT = EVIDENCE / (
    "c2.2-require-resolver-bank2-orchestration-wplto-first-red.json")
PRIVATE_PRIMITIVE_FIRST_RED_RECEIPT = EVIDENCE / (
    "c2.2-require-resolver-private-c2d-byte-wplto-first-red.json")
C_HELPER_FIRST_RED_RECEIPT = EVIDENCE / (
    "c2.2-require-resolver-vm-byte-args-wplto-first-red.json")
C_HELPER_BUILD = (
    BASE / "private-c2d-byte-vm-byte-args-product-shaped-v7")
BASELINE_RECEIPT = EVIDENCE / (
    "c2.2-product-link67-f1-f2-structural-receipt.json")
BASELINE_WPLTO = (
    ROOT / "build/post-promotion/link67-f1-f2/wplto")
SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-require-resolver.json"
STDLIB = STATIC / "stdlib-p0.manifest.json"
EXPECTED_STATIC = 40241
EXPECTED_ENTRIES = 676
EXPECTED_RESOLUTIONS = 2676
EXPECTED_ROOTS = 340
EXPECTED_DIRECT_REFS = 642
BASELINE_STATIC = 34990
BASELINE_APPEND_IMAGE = 724
MAX_RESIDENT_TEXT_DELTA = 58
MIN_TEXT_NOISE_RESERVE = 32
FEATURE = "LISP65_C2_REQUIRE_RESOLVER"
SPECS = (
    ("stdlib-p0", "stdlib", STDLIB),
    *F2.SPECS[1:],
)


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"{label} failed ({result.returncode}):\n{result.stdout}")
    return result.stdout


def build_static_plane() -> dict[str, Any]:
    STATIC.mkdir(parents=True, exist_ok=True)
    output = run([
        sys.executable,
        "tools/host-lisp/bytecode_p0_stdlib.py",
        "--check",
        "--emit-artifacts",
        str((STATIC / "stdlib-p0").relative_to(ROOT)),
        "tests/bytecode/libs/p0-stdlib-require-resolver.json",
    ], "compile require resolver")
    require("bytecode-p0-stdlib-check: PASS" in output,
            "target Lisp compiler did not report green")
    old_sub = (SUBSTITUTION.BUILD, SUBSTITUTION.SPECS)
    old_v6 = (
        V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS)
    try:
        SUBSTITUTION.BUILD = STATIC_PRODUCT
        SUBSTITUTION.SPECS = SPECS
        product = SUBSTITUTION.build()
        manifest_code_bytes = sum(
            int(load(path)["code_bytes"]) for _key, _name, path in SPECS)
        V6.OUT = V6_OUT
        V6.PRODUCT_IDENTITY = (
            STATIC_PRODUCT / "substitution-artifacts.json")
        V6.A.SPECS = SPECS
        # The C2 emitter, not the input manifests, is the authority for the
        # packed Bank-2 plane.  Directory-only carrier helpers can change a
        # manifest's raw code total without occupying the execution plane.
        static_bytes = sum(
            len(V6.F.emit_image(*row).code) for row in V6.A.SPECS)
        V6.STATIC_CODE_BYTES = static_bytes
        V6_OUT.mkdir(parents=True, exist_ok=True)
        semantics = V6.host_semantics()
    finally:
        SUBSTITUTION.BUILD, SUBSTITUTION.SPECS = old_sub
        (V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES,
         V6.A.SPECS) = old_v6
    require(
        static_bytes == EXPECTED_STATIC
        and product["images"] == 6
        and product["entries"] == EXPECTED_ENTRIES
        and product["resolutions"] == EXPECTED_RESOLUTIONS
        and product["roots"] == EXPECTED_ROOTS
        and semantics["static_bank2"]["code_bytes"] == EXPECTED_STATIC,
        "require static-plane geometry drift")
    return {
        "compiler": output.strip().splitlines()[-3:],
        "product": product,
        "manifest_code_bytes": manifest_code_bytes,
        "semantics": semantics["static_bank2"],
    }


def bank2_fixture_product() -> dict[str, Any]:
    artifacts = {
        "c2d": bind(V6_OUT / "initial.c2d-v6.bin"),
        "code": bind(V6_OUT / "bank2-static-code.bin"),
        "shelf": bind(STATIC_PRODUCT / "product-shelf-v4-direct.bin"),
    }
    require(
        artifacts["c2d"]["bytes"] == 33840
        and artifacts["code"]["bytes"] == EXPECTED_STATIC,
        "require Bank-2 fixture geometry drift")
    return {"host_c2d_v6": {"artifacts": artifacts}}


def configure() -> None:
    old_static = CAN.STATIC
    os.environ.update(CAN.canonical_build_environment())
    CAN.PRODUCT.configure_require_resolver_profile_geometry()
    F1W.BASE = STATIC
    F1W.STATIC_PRODUCT = STATIC_PRODUCT
    F1W.V6 = V6_OUT
    F1W.BUILD = BUILD
    F1W.WPLTO = WPLTO
    F1W.RECEIPTS = RECEIPTS
    F1W.STATIC_RECEIPT = STATIC_RECEIPT
    F1W.EXPECTED_STATIC = EXPECTED_STATIC
    F1W.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    F1W.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    F1W.EXPECTED_ROOTS = EXPECTED_ROOTS
    F1W.SPECS = SPECS
    F1W.configure()
    PLANE.FRESH_ROOT = STATIC
    PLANE.FRESH_PRODUCT = (
        STATIC_PRODUCT / "substitution-artifacts.json")
    PLANE.FRESH_IDE = old_static / "libs/ide.manifest.json"
    PLANE.FRESH_BANK2 = V6_OUT / "bank2-static-code.bin"
    PLANE.FRESH_MANIFESTS = tuple(path for _key, _name, path in SPECS)
    CAN.fresh_bank2_fixture_product = bank2_fixture_product
    CAN.fresh_bank2_target_fixture = F1W.bank2_target_fixture

    original_single_link = CAN.PRODUCT.single_link

    def resolver_single_link(
        out: Path, *, probe_definitions: tuple[str, ...] = (),
        direct_entry_receipt: Path =
            CAN.PRODUCT.DIRECT_ENTRY_CONTRACT_RECEIPT,
        direct_entry_check_tool: str = "c2_direct_entry_contract.py",
        extra_contract_lines: tuple[str, ...] = (),
    ) -> None:
        definitions = tuple(dict.fromkeys(
            (*probe_definitions, FEATURE)))
        return original_single_link(
            out,
            probe_definitions=definitions,
            direct_entry_receipt=direct_entry_receipt,
            direct_entry_check_tool=direct_entry_check_tool,
            extra_contract_lines=(
                *extra_contract_lines,
                "require_resolver=L65I-v1-cold-c2d-derived",
                "require_resolver_new_session_records=0",
                "require_resolver_loaded_registry=none",
            ),
        )

    CAN.PRODUCT.single_link = resolver_single_link


def runtime_manifest_gate() -> dict[str, Any]:
    current_path = WPLTO / "runtime-overlays-session-final.json"
    baseline_path = (
        ROOT / "build/post-promotion/f2/product-shaped/wplto/"
        "runtime-overlays-session-final.json")
    current = load(current_path)
    baseline = load(baseline_path)
    current_rows = current["slices"]
    baseline_rows = baseline["slices"]
    require(len(current_rows) == len(baseline_rows) == 51,
            "Session catalog record count changed")
    current_names = [row["name"] for row in current_rows]
    baseline_names = [row["name"] for row in baseline_rows]
    require(current_names == baseline_names,
            "Session catalog inventory changed")
    row = next(item for item in current_rows
               if item["name"] == "c2-append-image")
    old = next(item for item in baseline_rows
               if item["name"] == "c2-append-image")
    require(
        row["section"] == ".lisp65_rt_c2append_image"
        and row["memory_size"] <= 1792
        and row["memory_size"] == old["memory_size"]
        and old["memory_size"] == BASELINE_APPEND_IMAGE,
        "retired query protocol left an append-image debit")
    return {
        "status": "passed-no-Session-record-or-append-slice-debit",
        "record_count": len(current_rows),
        "record_names_identical_to_Link67": True,
        "slice": row,
        "baseline_slice_bytes": old["memory_size"],
        "slice_delta_bytes": row["memory_size"] - old["memory_size"],
        "new_records": 0,
        "manifest": bind(current_path),
    }


def elf_symbol_gate() -> dict[str, Any]:
    elf = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
    baseline = BASELINE_WPLTO / "resident-island-seed.prg.lto.o"
    nm = CAN.TOOLCHAIN / "bin/llvm-nm"
    objdump = CAN.TOOLCHAIN / "bin/llvm-objdump"
    output = run([
        str(nm), "--print-size", "--size-sort", str(elf)
    ], "inspect private primitive ELF symbols")
    old_output = run([
        str(nm), "--print-size", "--size-sort", str(baseline)
    ], "inspect Link-67 baseline symbols")

    def symbol_row(text: str, name: str) -> tuple[str, int]:
        rows = [line for line in text.splitlines()
                if line.split()[-1:] == [name]]
        require(len(rows) == 1, f"ELF symbol absent or duplicated: {name}")
        tokens = rows[0].split()
        require(len(tokens) >= 4 and int(tokens[1], 16) > 0,
                f"ELF symbol has no bound size: {name}")
        return rows[0], int(tokens[1], 16)

    vm_row, vm_bytes = symbol_row(output, "vm_callprim")
    leaf_row, leaf_bytes = symbol_row(output, "vm_c2d_byte")
    _reader_row, reader_bytes = symbol_row(output, "c2_stream_c2d_read")
    _old_vm_row, old_vm_bytes = symbol_row(old_output, "vm_callprim")
    require("c2_require_query_phase" not in output,
            "retired query phase survived in final ELF")
    disassembly = run([
        str(objdump), "-d", str(elf)
    ], "disassemble private primitive edge")
    match = re.search(
        r"(?ms)^[0-9a-f]+ <vm_callprim>:\n(.*?)(?=^[0-9a-f]+ <[^>]+>:\n)",
        disassembly)
    require(match is not None, "vm_callprim disassembly interval absent")
    body = match.group(1)
    leaf_calls = [
        line.strip() for line in body.splitlines()
        if re.search(r"\b(jsr|jmp)\b", line)
        and "<vm_c2d_byte>" in line
    ]
    require(len(leaf_calls) == 1,
            "private primitive does not own exactly one assembler-leaf edge")
    leaf_match = re.search(
        r"(?ms)^[0-9a-f]+ <vm_c2d_byte>:\n"
        r"(.*?)(?=^[0-9a-f]+ <[^>]+>:\n)",
        disassembly)
    require(leaf_match is not None, "vm_c2d_byte disassembly interval absent")
    leaf_body = leaf_match.group(1)
    reader_calls = [
        line.strip() for line in leaf_body.splitlines()
        if re.search(r"\b(jsr|jmp)\b", line)
        and "<c2_stream_c2d_read>" in line
    ]
    require(len(reader_calls) == 1,
            "assembler leaf does not own exactly one linked C2D-read edge")
    return {
        "status": "passed-private-Prim67-linked-C2D-byte-edge",
        "prim_id": 67,
        "dispatcher_symbol": "vm_callprim",
        "dispatcher_baseline_bytes": old_vm_bytes,
        "dispatcher_candidate_bytes": vm_bytes,
        "dispatcher_delta_bytes": vm_bytes - old_vm_bytes,
        "leaf_symbol": "vm_c2d_byte",
        "leaf_bytes": leaf_bytes,
        "leaf_nm_row": leaf_row,
        "linked_leaf_edges": leaf_calls,
        "reader_symbol": "c2_stream_c2d_read",
        "reader_bytes": reader_bytes,
        "linked_reader_edges": reader_calls,
        "retired_query_symbols": 0,
        "nm_row": vm_row,
        "linked_elf": bind(elf),
    }


def map_item(text: str, name: str) -> tuple[int, int, int]:
    match = re.search(
        rf"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+1\s+"
        rf"{re.escape(name)}$",
        text, re.MULTILINE)
    require(match is not None, f"linked-map item absent: {name}")
    return tuple(int(value, 16) for value in match.groups())


def text_symbol_sizes(path: Path) -> dict[str, int]:
    nm = CAN.TOOLCHAIN / "bin/llvm-nm"
    output = run(
        [str(nm), "--print-size", "--size-sort", str(path)],
        f"inspect text symbols in {path.name}")
    rows: dict[str, int] = {}
    for line in output.splitlines():
        tokens = line.split(maxsplit=3)
        if len(tokens) == 4 and tokens[2] in ("t", "T"):
            rows[tokens[3]] = int(tokens[1], 16)
    return rows


def qualify_narrow_first_red() -> int:
    internal_path = RECEIPTS / "wplto-internal.json"
    lto = WPLTO / "resident-island-seed.prg.lto.o"
    link_error = WPLTO / "resident-island-seed.prg.link.stderr.txt"
    map_path = WPLTO / "resident-island-seed.prg.map"
    final_elf = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
    baseline_lto = BASELINE_WPLTO / "resident-island-seed.prg.lto.o"
    baseline_map = BASELINE_WPLTO / "resident-island-seed.prg.map"
    require(
        internal_path.is_file() and lto.is_file() and link_error.is_file()
        and map_path.is_file() and baseline_lto.is_file()
        and baseline_map.is_file() and not final_elf.exists(),
        "narrow First Red lacks an isolated failed seed link or baseline")
    internal = load(internal_path)
    error = link_error.read_text(encoding="utf-8")
    require(
        internal["status"] == "FIRST RED: C2-lite real-ABI Link 50 stopped"
        and "link command failed" in internal["diagnostic"]["message"]
        and "section .text virtual address range overlaps with "
            ".lisp65_c2_kernal_handoff" in error,
        "narrow First Red is not the expected resident/handoff stop")

    current_text = map_path.read_text(encoding="utf-8")
    old_text = baseline_map.read_text(encoding="utf-8")
    text_vma, _text_lma, text_bytes = map_item(current_text, ".text")
    old_text_vma, _old_text_lma, old_text_bytes = map_item(old_text, ".text")
    handoff_vma, _handoff_lma, handoff_bytes = map_item(
        current_text, ".lisp65_c2_kernal_handoff")
    old_handoff_vma, _old_handoff_lma, old_handoff_bytes = map_item(
        old_text, ".lisp65_c2_kernal_handoff")
    append_vma, _append_lma, append_section_bytes = map_item(
        current_text, ".lisp65_rt_c2append_image")
    _old_append_vma, _old_append_lma, old_append_section_bytes = map_item(
        old_text, ".lisp65_rt_c2append_image")
    append_phase_vma, _append_phase_lma, append_phase_bytes = map_item(
        current_text, "c2_append_image_phase")
    query_vma, _query_lma, query_bytes = map_item(
        current_text, "c2_require_query_phase")
    require(
        text_vma == old_text_vma == 0x2023
        and handoff_vma == old_handoff_vma == 0xb4a3
        and handoff_bytes == old_handoff_bytes == 0x121
        and old_text_bytes == 0x9426 and text_bytes == 0x94ce
        and old_append_section_bytes == BASELINE_APPEND_IMAGE
        and append_vma == append_phase_vma == 0xc356
        and append_phase_bytes == 0x326 and query_vma == 0xc67c
        and query_bytes == 0x1e1
        and append_section_bytes == append_phase_bytes + query_bytes,
        "narrow resolver map attribution drift")
    old_end = old_text_vma + old_text_bytes
    current_end = text_vma + text_bytes
    require(
        handoff_vma - old_end == 90
        and current_end - handoff_vma == 78,
        "resident overlap arithmetic drift")

    old_symbols = text_symbol_sizes(baseline_lto)
    symbols = text_symbol_sizes(lto)
    named_deltas = {
        name: {
            "baseline_bytes": old_symbols.get(name, 0),
            "candidate_bytes": symbols.get(name, 0),
            "delta_bytes":
                symbols.get(name, 0) - old_symbols.get(name, 0),
        }
        for name in (
            "vm_callprim", "eval_v2_workbench_service",
            "vm_key_event", "strlen")
    }
    require(
        named_deltas["vm_callprim"]["delta_bytes"] == 171
        and sum(row["delta_bytes"] for row in named_deltas.values())
            == text_bytes - old_text_bytes == 168,
        "resident symbol attribution does not close")

    source_index = load(RESOLVER.RECEIPT)
    static_product = load(STATIC_PRODUCT / "substitution-artifacts.json")
    profile = load(CAN.PROFILE)
    require(
        static_product["product_build_id_hex"] ==
            profile["product_build_id"]
        and static_product["entries"] == EXPECTED_ENTRIES
        and static_product["resolutions"] == EXPECTED_RESOLUTIONS
        and static_product["roots"] == EXPECTED_ROOTS,
        "narrow First-Red product identity drift")
    value = {
        "format":
            "lisp65-c2-require-resolver-bank2-WPLTO-first-red-v1",
        "recorded_on": "2026-07-27",
        "status":
            "FIRST RED-narrow-native-result-seam-crosses-resident-handoff",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "source_and_index": {
            "status": source_index["status"],
            "host_cutpoints":
                source_index["host_first_prerequisite"]["cutpoints"],
            "host_mutations":
                source_index["host_first_prerequisite"]["mutations"],
            "source_mutations": len(source_index["source_mutations"]),
            "binary_index_mutations":
                len(source_index["binary_index"]["mutations_rejected"]),
            "capacity_exact_meets":
                source_index["binary_index"]["capacity_exact_meets"],
            "loaded_registry": "absent",
            "static_bank2_edge":
                "derived from canonical C2D slots 0..5",
            "private_static_size_constants": 0,
        },
        "bank2_orchestration": {
            "status": "passed-single-emitter-before-target-WPLTO",
            "baseline_bytes": BASELINE_STATIC,
            "candidate_bytes": EXPECTED_STATIC,
            "delta_bytes": EXPECTED_STATIC - BASELINE_STATIC,
            "headroom_bytes": 65536 - EXPECTED_STATIC,
            "images": static_product["images"],
            "entries": static_product["entries"],
            "resolutions": static_product["resolutions"],
            "roots": static_product["roots"],
            "direct_entry_refs": EXPECTED_DIRECT_REFS,
            "product_build_id": static_product["product_build_id_hex"],
            "bank2_sha256":
                profile["bank2_static_code"]["sha256"],
        },
        "cold_native_seam": {
            "rejected_native_policy_bytes": 3491,
            "raw_c2d_query_bytes": query_bytes,
            "native_policy_bytes_removed": 3491 - query_bytes,
            "native_policy_decisions": 0,
            "append_phase_baseline_bytes": BASELINE_APPEND_IMAGE,
            "append_phase_candidate_bytes": append_phase_bytes,
            "append_phase_delta_bytes":
                append_phase_bytes - BASELINE_APPEND_IMAGE,
            "combined_slice_bytes": append_section_bytes,
            "slice_cap_bytes": 1792,
            "slice_headroom_bytes": 1792 - append_section_bytes,
            "new_session_records": 0,
        },
        "resident_first_red": {
            "baseline_text_bytes": old_text_bytes,
            "candidate_text_bytes": text_bytes,
            "text_delta_bytes": text_bytes - old_text_bytes,
            "baseline_handoff_headroom_bytes": handoff_vma - old_end,
            "handoff_start_vma": f"0x{handoff_vma:04x}",
            "candidate_text_end_exclusive": f"0x{current_end:04x}",
            "handoff_overlap_bytes": current_end - handoff_vma,
            "primary_attribution": {
                "symbol": "vm_callprim",
                **named_deltas["vm_callprim"],
                "reason":
                    "the raw result path is materialized in the resident "
                    "one-argument primitive dispatcher",
            },
            "remaining_LTO_deltas": {
                name: row for name, row in named_deltas.items()
                if name != "vm_callprim"
            },
            "remaining_LTO_delta_bytes":
                sum(row["delta_bytes"] for name, row
                    in named_deltas.items() if name != "vm_callprim"),
            "other_wall_claim": "not reached because the seed link stopped",
        },
        "execution_accounting": {
            "generator_prelink_first_reds": 2,
            "stale_derived-contract_prelink_first_reds": 1,
            "whole_program_LTO_seed_attempts": 2,
            "authoritative_semantic_candidate_seed_attempts": 1,
            "successful_whole_program_links": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
        "review_boundary": {
            "product_question": True,
            "reason":
                "Bank-2 orchestration and the cold slice fit, but the "
                "attached typed result path adds 168 resident text bytes "
                "against 90 bytes of Link-67 headroom.",
            "forbidden_without_review": [
                "resident placement change",
                "handoff-anchor movement",
                "resident content reduction",
                "alternate native seam representation",
                "retry link",
                "hardware run",
            ],
        },
        "authority": {
            "contract": bind(RESOLVER.CONTRACT),
            "contract_note": bind(RESOLVER.NOTE),
            "source_index_receipt": bind(RESOLVER.RECEIPT),
            "static_plane_receipt": bind(STATIC_RECEIPT),
            "profile": bind(CAN.PROFILE),
            "static_header": bind(PLANE.HEADER),
            "product_artifacts": bind(
                STATIC_PRODUCT / "substitution-artifacts.json"),
            "bank2": bind(V6_OUT / "bank2-static-code.bin"),
            "WPLTO_internal": bind(internal_path),
            "LTO_object": bind(lto),
            "linked_map": bind(map_path),
            "linker_diagnostic": bind(link_error),
            "baseline_LTO_object": bind(baseline_lto),
            "baseline_linked_map": bind(baseline_map),
            "driver": bind(Path(__file__).resolve()),
        },
        "claim_limit":
            "Product-shaped First-Red capacity attribution only. No "
            "successful linked product, complete resident-wall, hardware, "
            "defstruct or release claim.",
    }
    NARROW_FIRST_RED_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    NARROW_FIRST_RED_RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-require-resolver-WPLTO: NARROW FIRST RED QUALIFIED "
        f"bank2={EXPECTED_STATIC} delta=+{EXPECTED_STATIC - BASELINE_STATIC} "
        f"query={query_bytes} slice={append_section_bytes}/1792 "
        f"text-delta=+{text_bytes - old_text_bytes} "
        f"handoff-overlap={current_end - handoff_vma}")
    return 0


def qualify_private_primitive_first_red() -> int:
    map_path = WPLTO / "resident-island-seed.prg.map"
    lto = WPLTO / "resident-island-seed.prg.lto.o"
    link_error = WPLTO / "resident-island-seed.prg.link.stderr.txt"
    baseline_map = BASELINE_WPLTO / "resident-island-seed.prg.map"
    baseline_lto = BASELINE_WPLTO / "resident-island-seed.prg.lto.o"
    require(
        map_path.is_file() and lto.is_file() and link_error.is_file()
        and baseline_map.is_file() and baseline_lto.is_file(),
        "private-primitive First Red artifacts are incomplete")
    abi = run([
        sys.executable, "tools/host-lisp/bytecode_abi_ledger.py",
        "--selftest",
    ], "replay append-only Prim-ID ledger for First Red")
    registry = run([
        sys.executable, "tools/host-lisp/v2_native_function_registry.py",
        "check",
    ], "replay native-function registry for First Red")
    require("SELFTEST PASS" in abi and "registry: PASS" in registry,
            "private Prim-ID 67 ABI parity red")
    error = link_error.read_text(encoding="utf-8")
    require(
        "section .text virtual address range overlaps with "
        ".lisp65_c2_kernal_handoff" in error
        and "ordinary Bank-0 state overlaps fixed C2 state" in error,
        "private-primitive First Red is not the measured resident stop")
    current_text = map_path.read_text(encoding="utf-8")
    old_text = baseline_map.read_text(encoding="utf-8")
    text_vma, _text_lma, text_bytes = map_item(current_text, ".text")
    old_text_vma, _old_text_lma, old_text_bytes = map_item(old_text, ".text")
    handoff_vma, _handoff_lma, handoff_bytes = map_item(
        current_text, ".lisp65_c2_kernal_handoff")
    old_handoff_vma, _old_handoff_lma, old_handoff_bytes = map_item(
        old_text, ".lisp65_c2_kernal_handoff")
    _bss_vma, _bss_lma, bss_bytes = map_item(current_text, ".bss")
    bss_vma, _bss_lma, _ = map_item(current_text, ".bss")
    old_bss_vma, _old_bss_lma, old_bss_bytes = map_item(old_text, ".bss")
    fixed_vma, _fixed_lma, fixed_bytes = map_item(
        current_text, ".lisp65_c2_fixed_bank0")
    old_fixed_vma, _old_fixed_lma, old_fixed_bytes = map_item(
        old_text, ".lisp65_c2_fixed_bank0")
    _append_vma, _append_lma, append_bytes = map_item(
        current_text, ".lisp65_rt_c2append_image")
    _old_append_vma, _old_append_lma, old_append_bytes = map_item(
        old_text, ".lisp65_rt_c2append_image")
    _island_vma, _island_lma, island_bytes = map_item(
        current_text, ".lisp65_resident_island")
    _old_island_vma, _old_island_lma, old_island_bytes = map_item(
        old_text, ".lisp65_resident_island")
    require(
        text_vma == old_text_vma == 0x2023
        and text_bytes == 0x9526 and old_text_bytes == 0x9426
        and handoff_vma == old_handoff_vma == 0xb4a3
        and handoff_bytes == old_handoff_bytes == 0x121
        and bss_bytes == old_bss_bytes == 0x62f
        and fixed_vma == old_fixed_vma == 0xc080
        and fixed_bytes == old_fixed_bytes == 0x198
        and append_bytes == old_append_bytes == BASELINE_APPEND_IMAGE
        and island_bytes == old_island_bytes == 0x6b7,
        "private-primitive map attribution drift")
    symbols = text_symbol_sizes(lto)
    old_symbols = text_symbol_sizes(baseline_lto)
    named = {
        name: {
            "baseline_bytes": old_symbols.get(name, 0),
            "candidate_bytes": symbols.get(name, 0),
            "delta_bytes": symbols.get(name, 0) - old_symbols.get(name, 0),
        }
        for name in (
            "vm_callprim", "eval_v2_workbench_service",
            "vm_key_event", "strlen")
    }
    require(
        named["vm_callprim"]["delta_bytes"] == 252
        and named["eval_v2_workbench_service"]["delta_bytes"] == 2
        and named["vm_key_event"]["delta_bytes"] == 2
        and named["strlen"]["delta_bytes"] == 0
        and sum(row["delta_bytes"] for row in named.values())
            == text_bytes - old_text_bytes == 256,
        "private-primitive resident symbol attribution does not close")
    old_text_end = old_text_vma + old_text_bytes
    text_end = text_vma + text_bytes
    old_bss_end = old_bss_vma + old_bss_bytes
    bss_end = bss_vma + bss_bytes
    source = load(RESOLVER.RECEIPT)
    product = load(STATIC_PRODUCT / "substitution-artifacts.json")
    profile = load(CAN.PROFILE)
    require(
        source["status"] ==
            "passed-bank2-orchestrated-require-and-private-c2d-byte-gates"
        and product["product_build_id_hex"] == profile["product_build_id"]
        and product["resolutions"] == EXPECTED_RESOLUTIONS,
        "private-primitive authority drift")
    value = {
        "format":
            "lisp65-c2-require-resolver-private-c2d-byte-WPLTO-first-red-v1",
        "recorded_on": "2026-07-27",
        "status":
            "FIRST RED-private-C2D-byte-materializes-252-resident-bytes",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "source_and_abi": {
            "source_gate": source["status"],
            "source_mutations": len(source["source_mutations"]),
            "index_mutations":
                len(source["binary_index"]["mutations_rejected"]),
            "host_cutpoints":
                source["host_first_prerequisite"]["cutpoints"],
            "host_mutations":
                source["host_first_prerequisite"]["mutations"],
            "prim_id": 67,
            "canonical_name": "%c2d-byte",
            "ledger": abi.strip(),
            "native_registry": registry.strip(),
            "retired_string_query_protocol": True,
            "overlay_roundtrips": 0,
            "new_session_records": 0,
        },
        "bank2_orchestration": {
            "baseline_bytes": BASELINE_STATIC,
            "candidate_bytes": EXPECTED_STATIC,
            "delta_bytes": EXPECTED_STATIC - BASELINE_STATIC,
            "headroom_bytes": 65536 - EXPECTED_STATIC,
            "entries": EXPECTED_ENTRIES,
            "resolutions": EXPECTED_RESOLUTIONS,
            "roots": EXPECTED_ROOTS,
            "direct_entry_refs": EXPECTED_DIRECT_REFS,
            "product_build_id": product["product_build_id_hex"],
            "bank2_sha256":
                profile["bank2_static_code"]["sha256"],
        },
        "cold_native_surface": {
            "rejected_native_policy_bytes": 3491,
            "retired_query_phase_bytes": 481,
            "append_image_baseline_bytes": old_append_bytes,
            "append_image_candidate_bytes": append_bytes,
            "append_image_delta_bytes": append_bytes - old_append_bytes,
            "native_policy_decisions": 0,
        },
        "resident_first_red": {
            "baseline_text_bytes": old_text_bytes,
            "candidate_text_bytes": text_bytes,
            "text_delta_bytes": text_bytes - old_text_bytes,
            "primary_attribution": {
                "symbol": "vm_callprim",
                **named["vm_callprim"],
                "share_of_text_delta_bytes": 252,
            },
            "LTO_secondary_deltas": {
                name: row for name, row in named.items()
                if name != "vm_callprim"
            },
            "baseline_handoff_headroom_bytes":
                handoff_vma - old_text_end,
            "candidate_handoff_overlap_bytes": text_end - handoff_vma,
            "baseline_bss_headroom_bytes": fixed_vma - old_bss_end,
            "candidate_bss_overlap_bytes": bss_end - fixed_vma,
            "anchors": {
                "text_vma": "0x2023",
                "handoff_vma": "0xb4a3",
                "fixed_block_vma": "0xc080",
                "unchanged": True,
            },
            "unchanged_sections": {
                "append_image_bytes": append_bytes,
                "resident_island_bytes": island_bytes,
                "bss_payload_bytes": bss_bytes,
                "fixed_block_bytes": fixed_bytes,
            },
            "complete_wall_claim":
                "not reached because the seed link stopped at resident walls",
        },
        "review_boundary": {
            "product_question": True,
            "reason":
                "The private one-byte ABI removes the cold query protocol "
                "but llvm-mos materializes its validation/read/result path "
                "as +252 bytes inside resident vm_callprim. Together with "
                "four secondary LTO bytes this crosses the fixed handoff "
                "and ordinary-BSS walls.",
            "forbidden_without_review": [
                "assembler or non-LTO primitive leaf",
                "alternate primitive ABI",
                "resident placement change",
                "resident content reduction",
                "floor or anchor movement",
                "retry WPLTO",
                "product link",
                "hardware run",
            ],
        },
        "execution_accounting": {
            "prelink_source_first_reds": 1,
            "reason":
                "the first private-primitive identity stopped at C "
                "compilation because the existing resident reader lacked "
                "a public header declaration; it produced no map or link",
            "whole_program_LTO_seed_attempts": 1,
            "successful_whole_program_links": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
        "authority": {
            "contract": bind(RESOLVER.CONTRACT),
            "contract_note": bind(RESOLVER.NOTE),
            "bytecode_abi_contract": bind(
                ROOT / "docs/contracts/bytecode-abi.md"),
            "bytecode_abi_ledger": bind(
                ROOT / "config/bytecode-abi-ledger.json"),
            "native_function_registry": bind(
                ROOT / "config/v2-native-function-registry.json"),
            "generated_native_dispatch": bind(
                ROOT / "src/v2_native_function_dispatch.h"),
            "primitive_cross_parity": bind(
                ROOT / "tests/bytecode/dialect-v2/contracts/"
                "primitive-view-cross-parity.json"),
            "lisp_resolver": bind(RESOLVER.LISP),
            "product_vm": bind(RESOLVER.VM),
            "source_index_receipt": bind(RESOLVER.RECEIPT),
            "profile": bind(CAN.PROFILE),
            "static_header": bind(PLANE.HEADER),
            "product_artifacts": bind(
                STATIC_PRODUCT / "substitution-artifacts.json"),
            "bank2": bind(V6_OUT / "bank2-static-code.bin"),
            "LTO_object": bind(lto),
            "linked_map": bind(map_path),
            "linker_diagnostic": bind(link_error),
            "baseline_LTO_object": bind(baseline_lto),
            "baseline_linked_map": bind(baseline_map),
            "driver": bind(Path(__file__).resolve()),
        },
        "claim_limit":
            "Product-shaped WPLTO First-Red attribution only. No successful "
            "link, complete wall qualification, hardware, require execution "
            "or defstruct claim.",
    }
    PRIVATE_PRIMITIVE_FIRST_RED_RECEIPT.parent.mkdir(
        parents=True, exist_ok=True)
    PRIVATE_PRIMITIVE_FIRST_RED_RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-require-resolver-WPLTO: PRIVATE PRIMITIVE FIRST RED QUALIFIED "
        f"bank2={EXPECTED_STATIC} append-delta=0 "
        f"vm_callprim=+{named['vm_callprim']['delta_bytes']} "
        f"text=+{text_bytes - old_text_bytes} "
        f"handoff-overlap={text_end - handoff_vma} "
        f"bss-overlap={bss_end - fixed_vma}")
    return 0


def qualify_vm_byte_args_first_red() -> int:
    current = C_HELPER_BUILD / "wplto"
    map_path = current / "resident-island-seed.prg.map"
    lto = current / "resident-island-seed.prg.lto.o"
    link_error = current / "resident-island-seed.prg.link.stderr.txt"
    baseline_map = BASELINE_WPLTO / "resident-island-seed.prg.map"
    baseline_lto = BASELINE_WPLTO / "resident-island-seed.prg.lto.o"
    require(
        map_path.is_file() and lto.is_file() and link_error.is_file()
        and baseline_map.is_file() and baseline_lto.is_file(),
        "vm_byte_args First Red artifacts are incomplete")
    error = link_error.read_text(encoding="utf-8")
    require(
        "section .text virtual address range overlaps with "
        ".lisp65_c2_kernal_handoff" in error,
        "vm_byte_args First Red lacks the expected text wall")
    current_map = map_path.read_text(encoding="utf-8")
    old_map = baseline_map.read_text(encoding="utf-8")
    text_vma, _text_lma, text_bytes = map_item(current_map, ".text")
    old_text_vma, _old_text_lma, old_text_bytes = map_item(old_map, ".text")
    handoff_vma, _handoff_lma, handoff_bytes = map_item(
        current_map, ".lisp65_c2_kernal_handoff")
    old_handoff_vma, _old_handoff_lma, old_handoff_bytes = map_item(
        old_map, ".lisp65_c2_kernal_handoff")
    e000_vma, _e000_lma, e000_bytes = map_item(
        current_map, ".lisp65_c2_kernal_window.c2_resident")
    old_e000_vma, _old_e000_lma, old_e000_bytes = map_item(
        old_map, ".lisp65_c2_kernal_window.c2_resident")
    require(
        text_vma == old_text_vma == 0x2023
        and old_text_bytes == 0x9426 and text_bytes == 0x94ce
        and handoff_vma == old_handoff_vma == 0xb4a3
        and handoff_bytes == old_handoff_bytes == 0x121
        and e000_vma == old_e000_vma == 0xe09b
        and e000_bytes == old_e000_bytes == 0x1c23,
        "vm_byte_args First Red map attribution drift")
    symbols = text_symbol_sizes(lto)
    old_symbols = text_symbol_sizes(baseline_lto)
    vm_delta = (
        symbols.get("vm_callprim", 0)
        - old_symbols.get("vm_callprim", 0))
    require(
        vm_delta == 164
        and text_bytes - old_text_bytes == 168
        and text_vma + text_bytes - handoff_vma == 78,
        "vm_byte_args First Red arithmetic drift")
    value = {
        "format":
            "lisp65-c2-require-resolver-vm-byte-args-WPLTO-first-red-v1",
        "recorded_on": "2026-07-27",
        "status":
            "FIRST RED-vm-byte-args-C-form-misses-58-byte-ceiling",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "resident_text": {
            "baseline_bytes": old_text_bytes,
            "candidate_bytes": text_bytes,
            "delta_bytes": text_bytes - old_text_bytes,
            "maximum_authorized_delta_bytes": MAX_RESIDENT_TEXT_DELTA,
            "vm_callprim_delta_bytes": vm_delta,
            "secondary_LTO_delta_bytes":
                text_bytes - old_text_bytes - vm_delta,
            "baseline_headroom_bytes": handoff_vma
                - (old_text_vma + old_text_bytes),
            "candidate_handoff_overlap_bytes":
                text_vma + text_bytes - handoff_vma,
        },
        "unchanged_owned_window": {
            "vma": f"0x{e000_vma:04x}",
            "bytes": e000_bytes,
            "delta_bytes": e000_bytes - old_e000_bytes,
        },
        "decision": {
            "C_form_closed": True,
            "selected_successor":
                "eighth non-LTO vm_c2d_byte assembler leaf",
            "further_C_iterations": 0,
        },
        "authority": {
            "contract": bind(RESOLVER.CONTRACT),
            "contract_note": bind(RESOLVER.NOTE),
            "LTO_object": bind(lto),
            "linked_map": bind(map_path),
            "linker_diagnostic": bind(link_error),
            "baseline_LTO_object": bind(baseline_lto),
            "baseline_linked_map": bind(baseline_map),
            "driver": bind(Path(__file__).resolve()),
        },
        "claim_limit":
            "Non-promotable C-form capacity First Red only; no product link "
            "or hardware claim.",
    }
    C_HELPER_FIRST_RED_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    C_HELPER_FIRST_RED_RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-require-resolver-WPLTO: VM_BYTE_ARGS FIRST RED QUALIFIED "
        f"text-delta={text_bytes - old_text_bytes} "
        f"overlap={text_vma + text_bytes - handoff_vma}")
    return 0


def rebind_final_receipt() -> int:
    """Refresh source bindings from the already completed v11 WPLTO.

    This is artifact-side receipt completion only: it cannot compile, link or
    change product bytes.  The linked ELF and its full gate set must already
    exist and remain byte-bound.
    """
    elf = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
    asm_receipt = WPLTO / "c2-assembler-leaf-abi-derived-final.json"
    require(RECEIPT.is_file() and elf.is_file() and asm_receipt.is_file(),
            "final receipt rebind lacks completed v11 artifacts")
    source_replay = subprocess.run(
        [sys.executable, "tools/host-lisp/c2_require_resolver_gate.py"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(source_replay.returncode == 0,
            f"source receipt replay red:\n{source_replay.stdout}")
    value = load(RECEIPT)
    source = load(RESOLVER.RECEIPT)
    asm = load(asm_receipt)
    require(
        value["status"] ==
            "passed-bank2-orchestrated-require-product-shaped-WPLTO"
        and value["resident_text_criterion"]["passed"] is True
        and source["status"] ==
            "passed-bank2-orchestrated-require-and-private-c2d-byte-gates"
        and asm["status"] == "passed-all-assembler-leaf-abi-contracts"
        and "vm_c2d_byte" in asm[
            "ELF_derived_C_called_inventory"]["C_called_functions"],
        "final receipt rebind authority drift")
    value["source_index_gate"] = source
    value["session_gate"] = runtime_manifest_gate()
    value["ELF_gate"] = elf_symbol_gate()
    value["authority"].update({
        "source_index_receipt": bind(RESOLVER.RECEIPT),
        "assembler_leaf": bind(RESOLVER.LEAF),
        "assembler_leaf_ABI_receipt": bind(asm_receipt),
        "vm_byte_args_first_red_receipt": bind(C_HELPER_FIRST_RED_RECEIPT),
        "driver": bind(Path(__file__).resolve()),
    })
    value["artifact_side_completion"] = {
        "status": "passed-no-compile-no-link-rebind",
        "source_replay":
            source_replay.stdout.strip().splitlines()[-1],
        "linked_ELF_unchanged": bind(elf),
        "product_links": 0,
        "hardware_runs": 0,
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-require-resolver-WPLTO: RECEIPT REBOUND "
        "compile=0 link=0 hardware=0")
    return 0


def qualify_first_red() -> int:
    internal_path = RECEIPTS / "wplto-internal.json"
    lto = WPLTO / "resident-island-seed.prg.lto.o"
    link_error = WPLTO / "resident-island-seed.prg.link.stderr.txt"
    map_path = WPLTO / "resident-island-seed.prg.map"
    final_elf = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
    require(
        internal_path.is_file() and lto.is_file() and link_error.is_file()
        and map_path.is_file() and not final_elf.exists(),
        "first-red qualification lacks an isolated failed seed link")
    internal = load(internal_path)
    require(
        internal["status"] == "FIRST RED: C2-lite real-ABI Link 50 stopped"
        and "link command failed" in internal["diagnostic"]["message"],
        "WPLTO internal receipt is not the expected First Red")
    error = link_error.read_text(encoding="utf-8")
    require(
        "C2 append phase image exceeds its stack-safe window" in error
        and "overflowed by 1055 bytes" in error,
        "linker First Red differs from the resolver placement failure")
    map_text = map_path.read_text(encoding="utf-8")
    section_match = re.search(
        r"^\s*c356\s+1e576\s+([0-9a-f]+)\s+1 "
        r"\.lisp65_rt_c2append_image$",
        map_text, re.MULTILINE)
    append_match = re.search(
        r"^\s*c356\s+1e576\s+([0-9a-f]+)\s+1\s+"
        r"c2_append_image_phase$", map_text, re.MULTILINE)
    query_match = re.search(
        r"^\s*c67c\s+1e89c\s+([0-9a-f]+)\s+1\s+"
        r"c2_require_query_phase$", map_text, re.MULTILINE)
    require(section_match is not None and append_match is not None
            and query_match is not None,
            "linked-map resolver attribution is absent")
    section_bytes = int(section_match.group(1), 16)
    append_bytes = int(append_match.group(1), 16)
    query_bytes = int(query_match.group(1), 16)
    require(
        section_bytes == append_bytes + query_bytes == 4297
        and append_bytes == 806 and query_bytes == 3491,
        "resolver First-Red byte attribution drift")
    source_index = load(RESOLVER.RECEIPT)
    static_product = load(STATIC_PRODUCT / "substitution-artifacts.json")
    value = {
        "format": "lisp65-c2-require-resolver-WPLTO-first-red-v1",
        "recorded_on": "2026-07-27",
        "status":
            "FIRST RED-cold-native-query-exceeds-existing-append-image-slice",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "source_and_index": {
            "status": source_index["status"],
            "host_cutpoints":
                source_index["host_first_prerequisite"]["cutpoints"],
            "host_mutations":
                source_index["host_first_prerequisite"]["mutations"],
            "source_mutations": len(source_index["source_mutations"]),
            "binary_index_mutations":
                len(source_index["binary_index"]["mutations_rejected"]),
            "capacity_exact_meets":
                source_index["binary_index"]["capacity_exact_meets"],
        },
        "bank2": {
            "status": "passed-single-emitter-before-target-WPLTO",
            "baseline_bytes": BASELINE_STATIC,
            "candidate_bytes": EXPECTED_STATIC,
            "delta_bytes": EXPECTED_STATIC - BASELINE_STATIC,
            "images": static_product["images"],
            "entries": static_product["entries"],
            "resolutions": static_product["resolutions"],
            "roots": static_product["roots"],
        },
        "placement_first_red": {
            "section": ".lisp65_rt_c2append_image",
            "baseline_section_bytes": BASELINE_APPEND_IMAGE,
            "candidate_section_bytes": section_bytes,
            "candidate_delta_bytes":
                section_bytes - BASELINE_APPEND_IMAGE,
            "stack_safe_slice_cap_bytes": 1792,
            "stack_safe_overhang_bytes": section_bytes - 1792,
            "physical_window_overhang_bytes": 1055,
            "object_attribution": {
                "c2_append_image_phase_bytes": append_bytes,
                "c2_require_query_phase_bytes": query_bytes,
                "query_rodata_bytes": 12,
            },
            "new_session_records_attempted": 0,
            "resident_wall_claim": "not reached",
        },
        "execution_accounting": {
            "prelink_gate_replays": 1,
            "whole_program_LTO_seed_attempts": 1,
            "successful_whole_program_links": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
        "review_boundary": {
            "product_question": True,
            "reason":
                "The authorized no-new-record co-resident C form is "
                "measurably too large; another placement or representation "
                "is a Class-C design choice.",
            "unselected_directions": [
                "compact non-LTO cold query implementation",
                "semantic split with one or more new Session records",
                "narrower target query seam with more Bank-2 orchestration"
            ],
            "forbidden_without_review": [
                "slice-cap change",
                "resident debit",
                "new Session record",
                "retry link",
                "hardware run"
            ],
        },
        "authority": {
            "contract": bind(RESOLVER.CONTRACT),
            "source_index_receipt": bind(RESOLVER.RECEIPT),
            "static_plane_receipt": bind(STATIC_RECEIPT),
            "WPLTO_internal": bind(internal_path),
            "LTO_object": bind(lto),
            "linked_map": bind(map_path),
            "linker_diagnostic": bind(link_error),
            "driver": bind(Path(__file__).resolve()),
        },
        "claim_limit":
            "First-Red attribution only. No linked product, resident-wall, "
            "hardware, defstruct or release claim.",
    }
    FIRST_RED_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    FIRST_RED_RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-require-resolver-WPLTO: FIRST RED QUALIFIED "
        f"section={section_bytes} query={query_bytes} "
        f"overhang={section_bytes - 1792} product-links=0")
    return 0


def main() -> int:
    try:
        if sys.argv[1:] == ["--qualify-narrow-first-red"]:
            return qualify_narrow_first_red()
        if sys.argv[1:] == ["--qualify-private-primitive-first-red"]:
            return qualify_private_primitive_first_red()
        if sys.argv[1:] == ["--qualify-vm-byte-args-first-red"]:
            return qualify_vm_byte_args_first_red()
        if sys.argv[1:] == ["--rebind-final-receipt"]:
            return rebind_final_receipt()
        if sys.argv[1:] == ["--qualify-first-red"]:
            return qualify_first_red()
        require(not sys.argv[1:], "unknown arguments")
        require(
            not RECEIPT.exists()
            and not (WPLTO / "lisp65-c2-substitution-linked.prg.elf").exists(),
            "require WPLTO is one-shot; only a pre-link gate replay is legal")
        abi = run([
            sys.executable, "tools/host-lisp/bytecode_abi_ledger.py",
            "--selftest",
        ], "replay append-only Prim-ID ledger")
        registry = run([
            sys.executable, "tools/host-lisp/v2_native_function_registry.py",
            "check",
        ], "replay native-function registry")
        require("SELFTEST PASS" in abi and "registry: PASS" in registry,
                "private Prim-ID 67 ABI parity red")
        source_index = subprocess.run(
            [sys.executable,
             "tools/host-lisp/c2_require_resolver_gate.py"],
            cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, check=False)
        require(source_index.returncode == 0,
                f"resolver source/index gate red:\n{source_index.stdout}")
        static = build_static_plane()
        configure()
        BUILD.mkdir(parents=True, exist_ok=True)
        plane = F1W.static_gate()
        wplto = CAN.run_wplto()
        replacement = wplto["historical_checker_boundary"][
            "current_replacement_gates"]
        walls = replacement["walls"]
        capacity = replacement["capacity"]
        baseline = load(BASELINE_RECEIPT)["walls"]
        current_map = (
            WPLTO / "resident-island-seed.prg.map"
        ).read_text(encoding="utf-8")
        baseline_map = (
            BASELINE_WPLTO / "resident-island-seed.prg.map"
        ).read_text(encoding="utf-8")
        text_vma, _text_lma, text_bytes = map_item(current_map, ".text")
        old_text_vma, _old_text_lma, old_text_bytes = map_item(
            baseline_map, ".text")
        text_delta = text_bytes - old_text_bytes
        text_noise_reserve = 0xb4a3 - (text_vma + text_bytes)
        require(
            text_vma == old_text_vma == 0x2023
            and text_delta <= MAX_RESIDENT_TEXT_DELTA
            and text_noise_reserve >= MIN_TEXT_NOISE_RESERVE,
            "vm_byte_args C form misses the +58-byte/32-byte "
            "resident-text criterion")
        resident_keys = (
            "bank0_text_headroom_bytes",
            "e000_headroom_bytes",
            "fixed_hot_block_headroom_bytes",
            "ordinary_bank0_bss_headroom_bytes",
            "resident_island_headroom_bytes",
        )
        require(
            wplto["status"].startswith("passed-")
            and plane["static_code_bytes"] == EXPECTED_STATIC
            and all(walls[key] >= 0 for key in resident_keys)
            and capacity["session_family_headroom_bytes"] >= 0,
            "require WPLTO crossed a bound wall")
        session = runtime_manifest_gate()
        symbol = elf_symbol_gate()
        product = load(STATIC_PRODUCT / "substitution-artifacts.json")
        profile = load(CAN.PROFILE)
        require(
            profile["product_build_id"] == product["product_build_id_hex"]
            and profile["direct_entry_refs"] == EXPECTED_DIRECT_REFS
            and profile["bank2_static_code"]["bytes"] == EXPECTED_STATIC,
            "require profile/single-emitter identity drift")
        value = {
            "format": "lisp65-c2-require-resolver-WPLTO-v2",
            "recorded_on": "2026-07-27",
            "status":
                "passed-bank2-orchestrated-require-product-shaped-WPLTO",
            "promotable": False,
            "product_links": 0,
            "hardware_runs": 0,
            "qualification_mode": "one-product-shaped-WPLTO-no-link",
            "resident_text_criterion": {
                "baseline_text_bytes": old_text_bytes,
                "candidate_text_bytes": text_bytes,
                "delta_bytes": text_delta,
                "maximum_delta_bytes": MAX_RESIDENT_TEXT_DELTA,
                "noise_reserve_bytes": text_noise_reserve,
                "minimum_noise_reserve_bytes": MIN_TEXT_NOISE_RESERVE,
                "passed": True,
            },
            "source_index_gate": load(RESOLVER.RECEIPT),
            "abi_gate": {
                "ledger": abi.strip(),
                "native_registry": registry.strip(),
                "prim_id": 67,
                "canonical_name": "%c2d-byte",
            },
            "static_build": static,
            "static_plane_gate": plane,
            "freight": {
                "bank2_baseline_bytes": BASELINE_STATIC,
                "bank2_candidate_bytes": EXPECTED_STATIC,
                "bank2_delta_bytes": EXPECTED_STATIC - BASELINE_STATIC,
                "entries_delta": EXPECTED_ENTRIES - 602,
                "resolutions_delta": EXPECTED_RESOLUTIONS - 2299,
                "roots_delta": EXPECTED_ROOTS - 283,
                "resident_wall_deltas": {
                    key: walls[key] - baseline[key] for key in resident_keys
                },
                "first_red_native_policy_bytes": 3491,
                "private_primitive_dispatch_delta_bytes":
                    symbol["dispatcher_delta_bytes"],
                "native_policy_bytes_removed":
                    3491 - max(0, symbol["dispatcher_delta_bytes"]),
                "native_policy_decisions": 0,
                "retired_string_query_protocol": True,
                "overlay_roundtrips": 0,
                "new_session_records": 0,
                "append_image_slice_baseline_bytes": BASELINE_APPEND_IMAGE,
                "append_image_slice_candidate_bytes":
                    session["slice"]["memory_size"],
            },
            "walls": walls,
            "baseline_walls": {
                key: baseline[key] for key in resident_keys
            },
            "capacity": capacity,
            "session_gate": session,
            "ELF_gate": symbol,
            "wplto": wplto,
            "authority": {
                "contract": bind(RESOLVER.CONTRACT),
                "contract_note": bind(RESOLVER.NOTE),
                "bytecode_abi_contract": bind(
                    ROOT / "docs/contracts/bytecode-abi.md"),
                "bytecode_abi_ledger": bind(
                    ROOT / "config/bytecode-abi-ledger.json"),
                "native_function_registry": bind(
                    ROOT / "config/v2-native-function-registry.json"),
                "source_index_receipt": bind(RESOLVER.RECEIPT),
                "suite": bind(SUITE),
                "stdlib_manifest": bind(STDLIB),
                "profile": bind(CAN.PROFILE),
                "static_header": bind(PLANE.HEADER),
                "product_artifacts": bind(
                    STATIC_PRODUCT / "substitution-artifacts.json"),
                "bank2": bind(V6_OUT / "bank2-static-code.bin"),
                "driver": bind(Path(__file__).resolve()),
            },
            "next_gate":
                "separate Class-C review before a product link or hardware",
            "claim_limit":
                "WPLTO placement/capacity only; no product link, hardware, "
                "defstruct or release claim.",
        }
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print(
            "c2-require-resolver-WPLTO: PASS "
            f"bank2={EXPECTED_STATIC} delta=+{EXPECTED_STATIC - BASELINE_STATIC} "
            f"slice={session['slice']['memory_size']} "
            f"text={walls['bank0_text_headroom_bytes']} "
            f"e000={walls['e000_headroom_bytes']} "
            f"session={capacity['session_family_headroom_bytes']}")
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            ProbeError, CAN.CanonicalError, PLANE.GateError) as error:
        print(f"c2-require-resolver-WPLTO: FIRST RED: {error}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
