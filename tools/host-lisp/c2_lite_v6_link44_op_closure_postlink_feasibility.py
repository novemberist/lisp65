#!/usr/bin/env python3
"""Prove the zero-growth Link-44 OP_CLOSURE hold-patch geometry.

This is paper/ELF work only.  It never writes a patched product.  The two-byte
candidate is constructed in memory solely to prove its exact diff domain.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any

from elf_truth import ElfTruth


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "build/c2.2/substitution/product-link-44-c2-lite-v6-bank2-target-stage-replay"
PRODUCT = BASE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
LTO = Path(str(PRODUCT) + ".lto.o")
SITE2_LTO = ROOT / (
    "build/c2.2/substitution/link44-op-closure-latch-wplto/"
    "resident-island-seed.prg.lto.o")
CAPACITY_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link44-op-closure-latch-wplto-capacity-first-red-diagnosis.json")
SITE1_CORRECTION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link44-vm-run-dir-latch-hardware-cycle1-interpretation-correction.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link44-op-closure-postlink-patch-feasibility-receipt.json")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

PRODUCT_SHA = "db3112e6503ca96d572cccb7a399c91eb06028faeaa05e595454fb9502b7f926"
LOAD_ADDRESS = 0x2001
VM_RUN_INNER = 0x6920
VM_RUN_INNER_BYTES = 7975
FAIL_EDGE = 0x8755
FAIL_EDGE_OFFSET = FAIL_EDGE - VM_RUN_INNER
BEFORE = bytes.fromhex("a2064c346a")       # LDX #VM_DIRMISS; JMP common error
AFTER = bytes.fromhex("a2064c5587")        # LDX #VM_DIRMISS; JMP $8755
PATCH_CPU_ADDRESSES = (0x8758, 0x8759)
PATCH_FILE_OFFSETS = tuple(2 + value - LOAD_ADDRESS for value in PATCH_CPU_ADDRESSES)


class FeasibilityError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FeasibilityError(message)


def regular(path: Path) -> bytes:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode),
            f"artifact must be regular and symlink-free: {path}")
    return path.read_bytes()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    data = regular(path)
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": digest(data),
    }


def product_slice(product: bytes, address: int, count: int) -> bytes:
    offset = 2 + address - LOAD_ADDRESS
    require(0 <= offset <= len(product) - count,
            f"CPU address outside product: 0x{address:04x}")
    return product[offset:offset + count]


def exact_patch_gate(product: bytes) -> dict[str, Any]:
    require(int.from_bytes(product[:2], "little") == LOAD_ADDRESS,
            "Link-44 PRG load address drift")
    require(product_slice(product, FAIL_EDGE, len(BEFORE)) == BEFORE,
            "OP_CLOSURE failure edge bytes drift")
    require(product.count(BEFORE) == 1,
            "OP_CLOSURE failure-edge byte sequence is not unique")
    result = bytearray(product)
    for address, value in zip(PATCH_CPU_ADDRESSES, AFTER[3:]):
        result[2 + address - LOAD_ADDRESS] = value
    changed = [index for index, (left, right) in
               enumerate(zip(product, result)) if left != right]
    require(changed == list(PATCH_FILE_OFFSETS),
            f"prospective patch diff-domain drift: {changed}")
    require(len(result) == len(product), "prospective patch changed file size")
    require(product_slice(bytes(result), FAIL_EDGE, len(AFTER)) == AFTER,
            "prospective patch did not produce the exact self-loop")

    mutants = {
        "wrong-low-target-byte": bytearray(result),
        "wrong-high-target-byte": bytearray(result),
        "opcode-changed": bytearray(result),
        "extra-neighbour-byte": bytearray(result),
        "only-one-operand-changed": bytearray(result),
    }
    mutants["wrong-low-target-byte"][PATCH_FILE_OFFSETS[0]] ^= 1
    mutants["wrong-high-target-byte"][PATCH_FILE_OFFSETS[1]] ^= 1
    mutants["opcode-changed"][PATCH_FILE_OFFSETS[0] - 1] = 0x80
    mutants["extra-neighbour-byte"][PATCH_FILE_OFFSETS[1] + 1] ^= 1
    mutants["only-one-operand-changed"][PATCH_FILE_OFFSETS[1]] = BEFORE[4]
    rejected: dict[str, str] = {}
    for name, mutant in mutants.items():
        try:
            mutant_changed = [index for index, (left, right) in
                               enumerate(zip(product, mutant)) if left != right]
            require(mutant_changed == list(PATCH_FILE_OFFSETS),
                    "mutation changed the exact diff domain")
            require(product_slice(bytes(mutant), FAIL_EDGE, len(AFTER)) == AFTER,
                    "mutation changed the exact hold loop")
        except FeasibilityError:
            rejected[name] = "rejected"
        else:
            raise FeasibilityError(f"patch mutation passed: {name}")
    return {
        "status": "passed-exact-two-operand-byte-self-loop-feasibility",
        "instruction_address": "0x8755",
        "prg_instruction_file_offset": "0x6756",
        "before_hex": BEFORE.hex(),
        "before_semantics": "LDX #VM_DIRMISS; JMP $6A34 common error path",
        "after_hex": AFTER.hex(),
        "after_semantics": "LDX #VM_DIRMISS; JMP $8755 self-loop",
        "changed_cpu_addresses": ["0x8758", "0x8759"],
        "changed_file_offsets": ["0x6759", "0x675a"],
        "before_changed_bytes": ["0x34", "0x6a"],
        "after_changed_bytes": ["0x55", "0x87"],
        "changed_bytes": 2,
        "file_size_delta_bytes": 0,
        "mutations_rejected": rejected,
    }


def elf_gate() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    fn = truth.symbol("vm_run_inner")
    require(fn.section == ".text" and fn.value == VM_RUN_INNER
            and fn.bytes == VM_RUN_INNER_BYTES,
            "vm_run_inner ELF identity drift")
    require(fn.value <= FAIL_EDGE < fn.value + fn.bytes,
            "failure edge is outside vm_run_inner")
    for name, address, size in (
        ("vm_codebuf", 0xBFD9, 56),
        ("vmr_littab", 0xC014, 2),
        ("vmr_code", 0xC016, 2),
        ("vmr_poff", 0xC018, 2),
        ("vmr_streaming", 0xC022, 1),
    ):
        symbol = truth.symbol(name)
        require(symbol.value == address and symbol.bytes == size,
                f"frozen-state symbol drift: {name}")

    base = ElfTruth.read(LTO, llvm_readobj=READOBJ)
    incoming = [row for row in base.relocations
                if row.source_section == ".text.vm_run_inner"
                and row.target == ".text.vm_run_inner"
                and row.addend == FAIL_EDGE_OFFSET]
    require(len(incoming) == 1 and incoming[0].offset == 0x0E53
            and incoming[0].relocation_type == "R_MOS_ADDR16",
            "failure edge does not have exactly the OP_CLOSURE dir_find ingress")

    site2 = ElfTruth.read(SITE2_LTO, llvm_readobj=READOBJ)
    expected = {
        (0x1E4B, "R_MOS_ADDR8", "__rc22", 0),
        (0x1E4D, "R_MOS_ADDR16", ".bss.vmr_hdrlen", 0),
        (0x1E50, "R_MOS_ADDR8", "__rc24", 0),
        (0x1E52, "R_MOS_ADDR16", ".bss.vmr_hdrlen", 1),
    }
    observed = {(row.offset, row.relocation_type, row.target, row.addend)
                for row in site2.relocations
                if 0x1E4A <= row.offset <= 0x1E53}
    require(expected <= observed,
            "failed source-form latch no longer proves its compiler liveness cost")
    return {
        "status": "passed-structured-ELF-edge-and-state-provenance",
        "vm_run_inner": {
            "section": fn.section,
            "address": "0x6920",
            "bytes": fn.bytes,
        },
        "failure_edge": {
            "address": "0x8755",
            "function_offset": "0x1e35",
            "incoming_edges": 1,
            "incoming_relocation_offset": "0x0e53",
            "incoming_semantics": (
                "the negative dir_find result reached from OP_CLOSURE only"),
        },
        "source_form_latch_explanation": {
            "target_low_was_forced_live_in": "__rc22",
            "target_high_was_forced_live_in": "__rc24",
            "use": (
                "proves why the source-form diagnostic grew; these cells are not "
                "assumed to retain the target in uninstrumented Link 44"),
        },
    }


def frozen_state_gate(product: bytes) -> dict[str, Any]:
    spans = {
        "operand-read": (0x71EC, "a001b1048508"),
        "cursor-preserved": (0x71F8, "c8a6048616a6058617b104851e"),
        "literal-target-load": (
            0x7205,
            "a5080a2607186d14c08504a5076d15c08505b2048507a406b104aa"),
        "dir-find-and-negative-edge": (
            0x7761,
            "a50720fa8ba00b91028aa01091028a10034c5587"),
        "hold-edge": (0x8755, BEFORE.hex()),
        "sym-function-preserve-entry": (0x6766, "a4165aa4175a"),
        "sym-function-preserve-exit": (0x67AD, "7a84177a8416"),
    }
    for name, (address, expected_hex) in spans.items():
        expected = bytes.fromhex(expected_hex)
        require(product_slice(product, address, len(expected)) == expected,
                f"frozen-state dataflow span drift: {name}")
    return {
        "status": "passed-handle-reconstruction-with-zero-conserving-bytes",
        "hold_timing": (
            "after dir_find returned negative, before VM_DIRMISS is stored, before "
            "the common cleanup path, abort journal or any wipe"),
        "stable_capture_ranges": [
            {
                "start": "0x0016",
                "end_exclusive": "0x001c",
                "meaning": "preserved bytecode cursor plus adjacent provenance",
            },
            {
                "start": "0xbfd9",
                "end_exclusive": "0xc023",
                "meaning": "complete 56-byte VM buffer and header-derived VM globals",
            },
        ],
        "reconstruction": [
            "cursor = little_endian(memory[0x16], memory[0x17])",
            "require memory[cursor] == 0x3f (OP_CLOSURE)",
            "li = memory[cursor + 1] and nuv = memory[cursor + 2]",
            "littab = little_endian(memory[0xc014], memory[0xc015])",
            "require littab and littab + 2*li + 1 lie inside vm_codebuf",
            "raw_target_obj = little_endian(memory[littab + 2*li], memory[littab + 2*li + 1])",
        ],
        "raw_target_domain_decode": {
            "odd": "Fixnum; illegal OP_CLOSURE target witness",
            "positive-even-nonzero": "heap pointer; inspect its cell type if needed",
            "0xc000..0xdffe-even": "BCODE; ordinal = (raw >> 1) - 0x6000",
            "0xe000..0xfffe-even": "SYMI; index = (raw >> 1) - 0x7000",
            "zero": "NIL; illegal OP_CLOSURE target witness",
        },
        "interrupt_safety": (
            "the owned IRQ saves and restores A/X/Y/Z and updates only fixed frame/VIC "
            "state; the two capture ranges and frozen VM cursor are not modified"),
        "recommended_capture_count": 3,
        "capture_spacing": ["immediate", "250 ms", "1000 ms"],
        "required_stability": "all three raw captures byteidentical",
    }


def main() -> int:
    try:
        require(not RECEIPT.exists(), "feasibility receipt already exists")
        product = regular(PRODUCT)
        require(digest(product) == PRODUCT_SHA, "Link-44 product authority drift")
        capacity = json.loads(regular(CAPACITY_FIRST_RED).decode("utf-8"))
        require(capacity.get("status") ==
                "first-red-class-b-capacity-review-required",
                "site-2 capacity First Red is not authoritative")
        site1 = json.loads(regular(SITE1_CORRECTION).decode("utf-8"))
        require(site1.get("status") ==
                "corrected-site1-silent-no-lookup-identity",
                "site-1 exclusion is not authoritative")
        patch = exact_patch_gate(product)
        elf = elf_gate()
        frozen = frozen_state_gate(product)
        receipt = {
            "format": "lisp65-c2-lite-v6-link44-op-closure-postlink-feasibility-v1",
            "recorded_on": "2026-07-22",
            "status": "passed-zero-growth-postlink-hold-patch-feasibility-hardware-not-run",
            "promotable": False,
            "scope": {
                "class": "C paper/ELF feasibility",
                "compiler_runs": 0,
                "linker_runs": 0,
                "patched_product_artifacts_created": 0,
                "hardware_runs": 0,
            },
            "authority": {
                "link44_product": bind(PRODUCT),
                "link44_elf": bind(ELF),
                "link44_map": bind(MAP),
                "link44_lto_object": bind(LTO),
                "site2_failed_lto_object": bind(SITE2_LTO),
                "site2_capacity_first_red": bind(CAPACITY_FIRST_RED),
                "site1_interpretation_correction": bind(SITE1_CORRECTION),
            },
            "patch_feasibility": patch,
            "elf_provenance": elf,
            "frozen_state_readout": frozen,
            "capacity_effect": {
                "product_file_bytes": 0,
                "bank0_text_bytes": 0,
                "ordinary_bank0_bss_bytes": 0,
                "fixed_hot_block_bytes": 0,
                "resident_island_bytes": 0,
                "e000_bytes": 0,
                "runtime_overlay_bytes": 0,
            },
            "prospective_class_b_cycle2": {
                "diagnostic_identity": (
                    "a separate SHA-bound copy of Link 44 with exactly the two "
                    "documented operand-byte changes"),
                "forms_submitted": 1,
                "form": "(list(peek 255 132)(peek 255 131)(peek 255 132))",
                "additional_forms": 0,
                "read_only_jtag": True,
                "cleanup": "diagnostic identity discarded after binding the result",
            },
            "budgets": {
                "class_b_cycles": "1/3 consumed; proposed run would consume cycle 2",
                "line1_product_first_reds": "2/3 unchanged",
                "completed_latency_measurements": "0/2 unchanged",
            },
            "claim_boundary": (
                "This receipt proves only that the diagnostic can be made as an exact "
                "two-byte, zero-growth, nonpromotable post-link hold patch and that the "
                "raw OP_CLOSURE target can be reconstructed from frozen Link-44 state. "
                "It creates no patched identity and carries no hardware, product-fix, "
                "latency, acceptance or promotion claim."),
            "next_gate": "separate authorization for one Class-B cycle-2 hardware run",
        }
        RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        os.chmod(RECEIPT, 0o444)
        print("c2-link44-op-closure-postlink-feasibility: PASS "
              "patch_bytes=2 size_delta=0 conserving_bytes=0 hardware=not-run")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, FeasibilityError) as exc:
        print(f"c2-link44-op-closure-postlink-feasibility: FAIL: {exc}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
