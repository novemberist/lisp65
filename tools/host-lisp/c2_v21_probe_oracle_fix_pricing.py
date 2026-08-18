#!/usr/bin/env python3
"""Price the commissioned Link-112 probe-oracle root and narrow fixes."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
CAPTURE = ARCH / "c2.3-v2.1-link112-d2-probe-oracle-capture-receipt.json"
CPU = ARCH / "c2.3-v2.1-cpu-transport-preflight-receipt.json"
CALL_SEAM = ARCH / "c2.3-v2.1-call-seam-pricing-receipt.json"
FULL_SPAN = ARCH / "c2.3-v2.1-full-span-convergence-receipt.json"
ELF = ROOT / (
    "build/c2.3/v2.1-full-span-convergence-card/final/"
    "lisp65-c2-substitution-linked.prg.elf"
)
ASM = ROOT / "src/optional/c2_mapped_far_convergence_full_span.s"
READER = ROOT / "src/optional/c2_map_cpu_read.s"
DMA = ROOT / "src/c2_platform_dma.c"
MEM = ROOT / "src/mem.c"
EQUIV = ROOT / "tools/host-lisp/c2_mapped_far_asm_equivalence.py"
FULL_SPAN_GATE = ROOT / "tools/host-lisp/c2_v21_full_span_convergence.py"
RECEIPT = ARCH / "c2.3-v2.1-probe-oracle-fix-pricing-receipt.json"
ROOT_SUCCESSOR = ARCH / "c2.3-v2.1-probe-oracle-root-fix-receipt.json"

LLVM_MC = ROOT / "tools/llvm-mos/bin/llvm-mc"
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
LLVM_OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
AUTHORIZATION = "852aca83"
FORMAT = "lisp65-c2.3-v2.1-probe-oracle-fix-pricing-v1"
STATUS = "PRICED: MAP-CPU-ROOT-OPTION-SELECTED; FIX-AND-CARD-PENDING"


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_bind(commit: str, path: Path) -> tuple[bytes, dict[str, Any]]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return raw, {"authority": "git-blob", "commit": full, "path": name,
                 "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    raw, authority = git_bind(AUTHORIZATION, PLAN)
    text = " ".join(raw.decode().split()).lower()
    for token in (
            "probe-oracle fix pricing commissioned",
            "convert the nine mutable readers to map-based cpu reads outright",
            "probes become cpu reads",
            "no fixture may model any dma operation atomically",
            "the card question returns with the winner"):
        require(token in text, f"probe-oracle commission token absent: {token}")
    return authority


def assemble(source: str) -> ElfTruth:
    with tempfile.TemporaryDirectory(prefix="c2-v21-probe-price-") as raw:
        directory = Path(raw)
        assembly = directory / "price.s"
        obj = directory / "price.o"
        assembly.write_text(source, encoding="utf-8")
        completed = subprocess.run(
            [str(LLVM_MC), "--triple=mos", "--mcpu=mos45gs02",
             "-filetype=obj", "-o", str(obj), str(assembly)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, check=False)
        require(completed.returncode == 0,
                f"pricing prototype did not assemble:\n{completed.stdout}")
        return ElfTruth.read(obj, llvm_readobj=LLVM_READOBJ)


ROOT_WRAPPERS = r"""
	.zeropage __rc2
	.zeropage __rc3
	.zeropage __rc4
	.zeropage __rc5
	.zeropage __rc6
	.zeropage __rc7
	.globl c2_map_cpu_read
	.globl lisp_abort_code

	.section .text.price_ext_root,"ax",@progbits
	.globl price_ext_root
	.type price_ext_root,@function
price_ext_root:
	tay
	lda __rc4
	sta __rc6
	lda __rc5
	sta __rc7
	lda __rc2
	sta __rc4
	lda __rc3
	sta __rc5
	lda #4
	sta __rc2
	stz __rc3
	tya
	jsr c2_map_cpu_read
	tax
	beq .Lext_fail
	rts
.Lext_fail:
	lda #0x3d
	jsr lisp_abort_code
	rts
	.size price_ext_root, .-price_ext_root

	.section .text.price_c2_root,"ax",@progbits
	.globl price_c2_root
	.type price_c2_root,@function
price_c2_root:
	tay
	lda __rc2
	sta __rc6
	lda __rc3
	sta __rc7
	lda #5
	sta __rc2
	stz __rc3
	tya
	jsr c2_map_cpu_read
	tax
	beq .Lc2_fail
	rts
.Lc2_fail:
	lda #0x3d
	jsr lisp_abort_code
	rts
	.size price_c2_root, .-price_c2_root
"""


NARROW_BOUNCE = r"""
	.section .lisp65_c2_mapped_far_facade.price_probe,"ax",@progbits
	.globl price_probe_cpu_bounce
	.globl c2_mapped_far_leave
	.globl c2_mapped_far_enter
	.globl c2_map_cpu_read
	.type price_probe_cpu_bounce,@function
price_probe_cpu_bounce:
	jsr c2_mapped_far_leave
	jsr c2_map_cpu_read
	jmp c2_mapped_far_enter
	.size price_probe_cpu_bounce, .-price_probe_cpu_bounce
"""


NARROW_COMMON = r"""
; A DMA-source probe cannot call the ordinary reader while its caller remains
; mapped in CPU block 3.  This target-shaped helper preserves the service's
; caller-clobbered working set, crosses through a facade bounce that unmaps
; block 3, performs one synchronous byte read, remaps the service, and returns.
.Lc2_cpu_probe_common:
	lda __rc8
	pha
	lda __rc9
	pha
	lda __rc10
	pha
	lda __rc11
	pha
	lda __rc12
	pha
	lda __rc13
	pha
	lda __rc14
	pha
	lda __rc15
	pha
	lda __rc25
	sta __rc2
	lda __rc26
	sta __rc3
	lda #mos16lo(__rc27)
	sta __rc4
	lda #mos16hi(__rc27)
	sta __rc5
	lda #1
	sta __rc6
	stz __rc7
	lda __rc23
	ldx __rc24
	jsr price_probe_cpu_bounce
	tax
	pla
	sta __rc15
	pla
	sta __rc14
	pla
	sta __rc13
	pla
	sta __rc12
	pla
	sta __rc11
	pla
	sta __rc10
	pla
	sta __rc9
	pla
	sta __rc8
	txa
	rts

"""


def narrow_service_variant(source: str) -> str:
    d700_start = source.index(".Lc2_d700_source_byte:")
    d700_end = source.index("; Submit the primary ordinary DMA", d700_start)
    d700 = NARROW_COMMON + r""".Lc2_d700_source_byte:
	clc
	lda __rc9
	adc __rc15
	sta __rc23
	lda __rc10
	adc __rc16
	sta __rc24
	lda __rc8
	adc #0
	sta __rc25
	lda #0
	sta __rc26
	jmp .Lc2_cpu_probe_common

"""
    result = source[:d700_start] + d700 + source[d700_end:]
    d705_start = result.index(".Lc2_d705_source_byte:")
    d705_end = result.index(".Lc2_d705_primary:", d705_start)
    d705 = r""".Lc2_d705_source_byte:
	jsr .Lc2_d705_address
	jmp .Lc2_cpu_probe_common

"""
    return result[:d705_start] + d705 + result[d705_end:]


def linked_inventory() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=LLVM_READOBJ,
                          include_section_data=False)
    symbols = {name: rows[0] for name, rows in truth.symbols_by_name.items()
               if len(rows) == 1}
    surfaces = {
        "Bank4_EXT": {
            "functions": ["str_read_byte", "ext_a", "ext_b", "ext_type",
                          "ext_disk_get"],
            "spans": [1, 2, 2, 1, 1], "physical_bank": 4,
        },
        "Bank5_symbols": {
            "functions": ["nameoff_get", "sympool_read", "sym_value",
                          "sym_function"],
            "spans": [2, "1..34", 2, 2], "physical_bank": 5,
        },
    }
    require(all(name in symbols for row in surfaces.values()
                for name in row["functions"]),
            "one mutable linked reader disappeared")
    disassembly = subprocess.run(
        [str(LLVM_OBJDUMP), "-d", "--symbolize-operands", str(ELF)],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout
    ext_edges = sum("<ext_dma_read_or_abort>" in line
                    and ("jsr" in line or "jmp" in line)
                    for line in disassembly.splitlines())
    c2_edges = sum("<c2_dma_read_or_abort>" in line
                   and ("jsr" in line or "jmp" in line)
                   for line in disassembly.splitlines())
    require((ext_edges, c2_edges) == (5, 4), "nine-reader edge inventory drift")
    section = truth.section(".lisp65_c2_mapped_far_facade")
    service = truth.section(".lisp65_c2_mapped_far_service")
    reader = symbols["c2_map_cpu_read"]
    require(section.bytes == 98 and service.bytes == 1248
            and reader.value == 0x2277 and reader.bytes == 189
            and symbols["ext_dma_read_or_abort"].bytes == 38
            and symbols["c2_dma_read_or_abort"].bytes == 46,
            "Link-112 price identity drift")
    return {
        "mutable_readers": 9, "maximum_span_bytes": 34,
        "wrapper_edges": {"Bank4_EXT": ext_edges, "Bank5_symbols": c2_edges},
        "surfaces": surfaces,
        "existing_CPU_reader": {"address": "0x2277", "bytes": reader.bytes,
                                "maximum_call_bytes": 64},
        "current_wrappers": {"ordinary_text_bytes": 38,
                             "mapped_facade_bytes": 46, "total_bytes": 84},
        "current_service_bytes": service.bytes,
        "mapped_facade_contract_bytes": section.bytes,
    }


def code_prices() -> dict[str, Any]:
    root = assemble(ROOT_WRAPPERS)
    ext = root.symbol("price_ext_root")
    c2 = root.symbol("price_c2_root")
    bounce = assemble(NARROW_BOUNCE).symbol("price_probe_cpu_bounce")
    source = ASM.read_text(encoding="utf-8")
    current = assemble(source).section(".lisp65_c2_mapped_far_service").bytes
    narrow = assemble(narrow_service_variant(source)).section(
        ".lisp65_c2_mapped_far_service").bytes
    require((ext.bytes, c2.bytes, bounce.bytes, current) == (37, 29, 9, 1248),
            "target-shaped prototype identity drift")
    return {
        "root": {
            "existing_reader_bytes": 189, "new_reader_bytes": 0,
            "ordinary_wrapper_before_bytes": 38,
            "ordinary_wrapper_after_bytes": ext.bytes,
            "ordinary_text_delta_bytes": ext.bytes - 38,
            "mapped_facade_wrapper_before_bytes": 46,
            "mapped_facade_wrapper_after_bytes": c2.bytes,
            "mapped_facade_executable_delta_bytes": c2.bytes - 46,
            "mapped_facade_contract_bytes": 98,
            "contract_padding_required_bytes": 46 - c2.bytes,
            "mapped_far_service_delta_bytes": 0,
            "current_service_retained_for_immutable_boot_spans": True,
            "new_fixed_vector_bytes": 0,
            "target_shaped_total_executable_delta_bytes":
                (ext.bytes - 38) + (c2.bytes - 46),
        },
        "narrow": {
            "existing_reader_bytes": 189, "new_reader_bytes": 0,
            "mapped_facade_bounce_bytes": bounce.bytes,
            "mapped_facade_contract_growth_bytes": bounce.bytes,
            "service_before_bytes": current,
            "service_after_target_prototype_bytes": narrow,
            "service_delta_bytes": narrow - current,
            "service_arena_capacity_bytes": 1499,
            "service_headroom_after_prototype_bytes": 1499 - narrow,
            "saved_service_working_registers_per_probe": 8,
            "hardware_stack_bytes_per_probe": 8,
            "new_fixed_vector_bytes": 0,
        },
        "prototype_scope": (
            "llvm-mc target-shaped ABI/section price only; no product source, "
            "WPLTO, link or delivered byte changed"),
    }


def partial_probe_fixtures() -> dict[str, Any]:
    source = bytes.fromhex("3b0601012f0153")
    stale = bytes.fromhex("0b000000000000")
    rows: dict[str, Any] = {}
    false_current = false_narrow = false_root = 0
    shapes = {
        "marker-before-any-probe-byte": stale,
        "probe-prefix-only": source[:1] + stale[1:],
        "probe-tail-only": stale[:-1] + source[-1:],
    }
    for lane in ("D700", "D705"):
        for name, expected in shapes.items():
            # The current fixture-impossible state: marker visible, probe data
            # only partly visible.  Destination can equal that stale echo and
            # therefore make a complete compare accept the wrong span.
            current_destination = expected
            current_accept = current_destination == expected
            current_correct = current_destination == source
            # A CPU reference sees source truth.  Narrow mode detects the
            # mismatch and accepts only after a genuine partial payload has
            # eventually converged in full.  Root mode copies synchronously.
            narrow_destination = source
            narrow_accept = narrow_destination == source
            root_destination = source
            root_accept = root_destination == source
            false_current += int(current_accept and not current_correct)
            false_narrow += int(narrow_accept and narrow_destination != source)
            false_root += int(root_accept and root_destination != source)
            rows[f"{lane}/{name}"] = {
                "probe_visibility_hex": expected.hex(),
                "current_full_span_accepts": current_accept,
                "current_result_is_source": current_correct,
                "narrow_CPU_oracle_accepts_only_full_source": narrow_accept,
                "root_CPU_copy_result_is_source": root_accept,
            }
    gate_source = FULL_SPAN_GATE.read_text(encoding="utf-8")
    emulator = EQUIV.read_text(encoding="utf-8")
    require("*value = reference_source" in gate_source
            and "super().wr(target, self._source_bank_byte" in emulator
            and "super().wr(done, super().rd(marker))" in emulator,
            "atomic probe-fixture predecessor shape drift")
    require(false_current == 6 and false_narrow == false_root == 0,
            "partial probe fixture conclusion drift")
    return {
        "lanes": 2, "partial_probe_shapes_per_lane": 3,
        "atomic_DMA_fixture_allowed": False,
        "payload_and_probe_jobs_both_partial": True,
        "current_false_accepts": false_current,
        "narrow_false_accepts": false_narrow,
        "root_false_accepts": false_root,
        "rows": rows,
    }


def operation_prices() -> dict[str, Any]:
    cpu = load(CPU)
    require(cpu["hardware"]["probe_reads"] == {"attic": 256, "bank5": 256}
            and cpu["hardware"]["probe_status"] == "0xa5/0xa5"
            and cpu["range_model"]["maximum_call_bytes"] == 64,
            "MAP CPU hardware/range authority drift")
    examples: dict[str, Any] = {}
    for length in (1, 2, 34):
        root_upper = 96 + 11 * length + 22
        narrow_upper = length * (96 + 11 + 22)
        examples[str(length)] = {
            "root_CPU_instruction_upper_bound": root_upper,
            "narrow_CPU_oracle_instruction_upper_bound": narrow_upper,
            "narrow_to_root_ratio": round(narrow_upper / root_upper, 3),
            "root_DMA_jobs": 0,
            "narrow_probe_DMA_jobs": 0,
            "narrow_primary_DMA_jobs_if_mismatch": 1,
        }
    return {
        "baseline": {
            "hardware_reads": {"Bank5": 256, "Attic": 256},
            "hardware_result": "0xa5/0xa5",
            "Bank4_domain": (
                "same sub-1MiB MAP arithmetic as hardware-proven Bank5; "
                "full range is host-exhaustive, not separately timed"),
            "setup_instruction_upper_bound_per_call": 96,
            "copy_instruction_upper_bound_per_byte": 11,
            "crossing_instruction_upper_bound_per_call": 22,
            "wall_time_per_call": None,
            "wall_time_claim": "MAP probe proved transport, not timing",
        },
        "examples": examples,
        "root": {
            "CPU_calls_per_span": 1, "DMA_probe_jobs_per_span": 0,
            "DMA_primary_jobs_per_span": 0,
            "completion_markers": 0, "reference_comparisons": 0,
        },
        "narrow": {
            "CPU_calls_per_span": "N", "DMA_probe_jobs_per_span": 0,
            "DMA_primary_jobs_per_mismatching_span": 1,
            "completion_marker_trust_for_payload": True,
            "full_reference_comparisons": "N per scan; scans may repeat",
        },
    }


def derive() -> dict[str, Any]:
    capture = load(CAPTURE)
    require(capture.get("status") ==
            "PROBE-ORACLE-F018B-REPRODUCED-WITH-FRESH-NAME",
            "corrected capture authority drift")
    call_seam = load(CALL_SEAM)
    require(call_seam["pricing"]["candidate_3_reader_in_far_service"]
            ["status"].startswith("REJECTED:"),
            "mapped-service hidden-callee precedent drift")
    prices = code_prices()
    operations = operation_prices()
    value = {
        "format": FORMAT, "recorded_on": "2026-08-16", "status": STATUS,
        "capture": {
            "fresh_name": "test-probe",
            "fresh_object_sha256": capture["staged_object"]["sha256"],
            "same_historical_corruption_codebytes": True,
            "same_noncanonical_literal_byte": "0xa0",
            "trace_probe_First_Red_stopped_state_bound": False,
        },
        "linked_inventory": linked_inventory(),
        "fixture_rule": partial_probe_fixtures(),
        "code_prices": prices,
        "operation_prices": operations,
        "boot_and_staging": {
            "root": {
                "immutable_boot_DMA_spans_unchanged": True,
                "library_bulk_CPU_transport_unchanged": True,
                "nine_mutable_runtime_readers_use_CPU": True,
                "mutable_read_DMA_jobs_removed": "all probes and all primary copies",
                "write_and_staging_paths_changed": False,
            },
            "narrow": {
                "immutable_boot_DMA_spans_unchanged": True,
                "library_bulk_CPU_transport_unchanged": True,
                "nine_mutable_runtime_readers_keep_bulk_DMA": True,
                "write_and_staging_paths_changed": False,
            },
        },
        "decision": {
            "winner": "root-map-cpu-for-all-nine-mutable-readers",
            "why": (
                "it removes the untrustworthy transport and its oracle for the "
                "whole mutable surface, fits the existing reader and section "
                "geometry in the target-shaped price, and pays one CPU setup per "
                "span; the narrow option needs a mapped-service bounce and pays "
                "one CPU setup per byte while retaining the bulk DMA"),
            "fixture_conversion_required_before_card": True,
            "fix_authorized": False, "card_authorized": False,
            "device_contact_authorized": False, "device_resume_authorized": False,
            "D3_D5_open": False,
            "next": "owner authorization for the root fix and exactly one product card",
        },
        "claim_limit": (
            "Desk pricing and target-shaped micro-assembly only. No product "
            "source fix, WPLTO, link, card, media, device access, resume or D3-D5."),
        "authority": {
            "commission": authorization(), "capture": bind(CAPTURE),
            "CPU_preflight": bind(CPU), "call_seam_precedent": bind(CALL_SEAM),
            "full_span_receipt": bind(FULL_SPAN), "ELF": bind(ELF),
            "assembly": bind(ASM), "CPU_reader": bind(READER),
            "DMA_source": bind(DMA), "EXT_source": bind(MEM),
            "equivalence_fixture": bind(EQUIV),
            "full_span_fixture": bind(FULL_SPAN_GATE),
            "checker": bind(Path(__file__)),
        },
        "execution_accounting": {
            "micro_assemblies": 4, "WPLTO": 0, "product_links": 0,
            "product_bytes_changed": 0, "device_contacts": 0,
            "device_resumes": 0,
        },
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "pricing identity drift")
    inventory = value["linked_inventory"]
    require(inventory["mutable_readers"] == 9
            and inventory["wrapper_edges"] == {"Bank4_EXT": 5,
                                                "Bank5_symbols": 4}
            and inventory["maximum_span_bytes"] == 34,
            "nine-reader inventory drift")
    fixtures = value["fixture_rule"]
    require(fixtures["atomic_DMA_fixture_allowed"] is False
            and fixtures["payload_and_probe_jobs_both_partial"] is True
            and fixtures["current_false_accepts"] == 6
            and fixtures["narrow_false_accepts"] == 0
            and fixtures["root_false_accepts"] == 0,
            "partial probe fixture rule weakened")
    root = value["code_prices"]["root"]
    narrow = value["code_prices"]["narrow"]
    require(root["ordinary_text_delta_bytes"] == -1
            and root["mapped_facade_executable_delta_bytes"] == -17
            and root["contract_padding_required_bytes"] == 17
            and root["mapped_far_service_delta_bytes"] == 0
            and root["new_fixed_vector_bytes"] == 0
            and narrow["mapped_facade_bounce_bytes"] == 9
            and narrow["mapped_facade_contract_growth_bytes"] == 9
            and narrow["service_headroom_after_prototype_bytes"] >= 0
            and narrow["saved_service_working_registers_per_probe"] == 8,
            "code price drift")
    operations = value["operation_prices"]
    require(operations["root"]["CPU_calls_per_span"] == 1
            and operations["root"]["DMA_primary_jobs_per_span"] == 0
            and operations["narrow"]["CPU_calls_per_span"] == "N"
            and operations["narrow"]["completion_marker_trust_for_payload"] is True
            and operations["examples"]["34"]["narrow_to_root_ratio"] > 8,
            "operation price/ordering drift")
    decision = value["decision"]
    require(decision["winner"] == "root-map-cpu-for-all-nine-mutable-readers"
            and decision["fixture_conversion_required_before_card"] is True
            and decision["fix_authorized"] is False
            and decision["card_authorized"] is False
            and decision["device_contact_authorized"] is False
            and decision["device_resume_authorized"] is False
            and decision["D3_D5_open"] is False,
            "pricing claim boundary drift")
    require(value["execution_accounting"] == {
        "micro_assemblies": 4, "WPLTO": 0, "product_links": 0,
        "product_bytes_changed": 0, "device_contacts": 0,
        "device_resumes": 0}, "desk execution accounting drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "lose-reader": lambda x: x["linked_inventory"].__setitem__(
            "mutable_readers", 8),
        "atomize-probe-fixture": lambda x: x["fixture_rule"].__setitem__(
            "atomic_DMA_fixture_allowed", True),
        "hide-probe-false-accept": lambda x: x["fixture_rule"].__setitem__(
            "current_false_accepts", 0),
        "break-root-fixture": lambda x: x["fixture_rule"].__setitem__(
            "root_false_accepts", 1),
        "spend-root-text": lambda x: x["code_prices"]["root"].__setitem__(
            "ordinary_text_delta_bytes", 1),
        "invent-root-vector": lambda x: x["code_prices"]["root"].__setitem__(
            "new_fixed_vector_bytes", 3),
        "hide-narrow-bounce": lambda x: x["code_prices"]["narrow"].__setitem__(
            "mapped_facade_bounce_bytes", 0),
        "hide-register-save": lambda x: x["code_prices"]["narrow"].__setitem__(
            "saved_service_working_registers_per_probe", 0),
        "make-narrow-one-call": lambda x: x["operation_prices"]["narrow"]
            .__setitem__("CPU_calls_per_span", 1),
        "give-root-DMA": lambda x: x["operation_prices"]["root"]
            .__setitem__("DMA_primary_jobs_per_span", 1),
        "select-narrow": lambda x: x["decision"].__setitem__(
            "winner", "narrow-cpu-probes"),
        "silently-authorize-fix": lambda x: x["decision"].__setitem__(
            "fix_authorized", True),
        "silently-authorize-card": lambda x: x["decision"].__setitem__(
            "card_authorized", True),
        "authorize-resume": lambda x: x["decision"].__setitem__(
            "device_resume_authorized", True),
        "open-D3": lambda x: x["decision"].__setitem__("D3_D5_open", True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except PricingError:
            rejected.append(name)
    require(rejected == list(cases), "probe-oracle pricing mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    if action == "record":
        value = derive()
        value["mutations_rejected"] = mutations(value)
        RECEIPT.write_bytes(canonical(value))
    else:
        value = load(RECEIPT)
        rejected = value.pop("mutations_rejected", None)
        validate(value)
        successor = load(ROOT_SUCCESSOR)
        require(
            rejected == mutations(value) and len(rejected) == 15
            and successor.get("status") ==
                "HOST-GREEN: NINE-MUTABLE-READERS-USE-MAP-CPU; CARD-PENDING"
            and successor.get("authority", {}).get("pricing") == {
                "path": RECEIPT.relative_to(ROOT).as_posix(),
                "bytes": RECEIPT.stat().st_size,
                "sha256": hashlib.sha256(RECEIPT.read_bytes()).hexdigest()},
            "historical probe-oracle pricing successor drift")
    narrow = value["code_prices"]["narrow"]
    print(
        "Link-112 probe-oracle pricing: PASS "
        f"action={action} winner=root root_delta=-18 "
        f"narrow_service={narrow['service_after_target_prototype_bytes']} "
        f"mutations={len(value['mutations_rejected'] if action == 'record' else rejected)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PricingError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"Link-112 probe-oracle pricing: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
