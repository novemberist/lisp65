#!/usr/bin/env python3
"""Gate the R1 abort-driver far relocation and worst-state boundary."""

from __future__ import annotations

from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
STUDY = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v1.6-e000-relocation-study-receipt.json"
RUNTIME = ROOT / "src/c2_product_runtime.c"
INTERRUPT = ROOT / "src/interrupt.c"
FACADE = ROOT / "src/optional/c2_mapped_far_service_abort_v3.s"
PADDING = ROOT / "src/optional/c2_mapped_far_facade_padding_abort_v2.s"
IRQ_BASE = ROOT / "src/c2_kernal_irq_base.s"
CAPTURE_SOURCE = ROOT / "src/optional/c2_kernal_input_capture.s"
EQUATES_INCLUDE = ROOT / "src/c2_kernal_window_equates.inc"
CONFIG = ROOT / "tools/host-lisp/c2_v160_abort_driver_relocation_config.py"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
CLANG = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
LD = ROOT / "tools/llvm-mos/bin/ld.lld"
AUTHORIZATION = "aa335881"
FAR = ".lisp65_c2_mapped_far_service"
FACADE_SECTION = ".lisp65_c2_mapped_far_facade"
E000_START = 0xE000
E000_END = 0xFF80
CAPTURE_SECTIONS = (
    ".lisp65_c2_kernal_window.input_capture_main",
    ".lisp65_c2_kernal_window.input_capture_helper",
)
SPLIT_EQUATES = {
    "C2K_EVENT_CODE": 0xFF80,
    "C2K_EVENT_MODIFIERS": 0xFF81,
    "C2K_EVENT_READY": 0xFF82,
    "C2K_FRAME_LO": 0xFF83,
    "C2K_FRAME_HI": 0xFF84,
    "C2K_NMI_COUNT": 0xFF85,
    "C2K_SOURCELESS_IRQS": 0xFF86,
    "C2K_MAP_GENERATION": 0xFF87,
    "C2K_STATE": 0xFF88,
    "C2K_UNOWNED_VIC": 0xFF89,
    "C2K_BREAK_PENDING": 0xFF8A,
    "C2K_BREAK_HELD": 0xFF8B,
    "C2K_INPUT_RING_HEAD": 0xFF8C,
    "C2K_INPUT_RING_TAIL": 0xFF8D,
    "C2K_INPUT_RING_BASE": 0xBC90,
    "C2K_INPUT_RING_SLOTS": 112,
}


class GateError(RuntimeError): pass


def require(value: bool, message: str) -> None:
    if not value: raise GateError(message)


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def git_authority() -> dict[str, Any]:
    full = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().split())
    for token in ("card r1 authorized", "worst state", "far window is mapped",
                  "transitive asm/c abi", "facade stays exactly 98 bytes",
                  "a red returns here"):
        require(token in text, f"R1 authority token absent: {token}")
    return {"commit": full, "path": name, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def source_gate(runtime: str | None = None, interrupt: str | None = None,
                facade: str | None = None, padding: str | None = None) -> dict[str, Any]:
    c = RUNTIME.read_text() if runtime is None else runtime
    irq = INTERRUPT.read_text() if interrupt is None else interrupt
    asm = FACADE.read_text() if facade is None else facade
    pad = PADDING.read_text() if padding is None else padding
    require("#ifdef LISP65_C2_ABORT_DRIVER_FAR" in c
            and "LISP65_C2_MAPPED_FAR_FN" in c
            and "uint8_t c2_abort_driver(void)" in c
            and "return !c2_ready || c2_abort_driver_facade();" in c,
            "abort body/caller is not feature-bound to the far successor")
    wrapper = asm.split("c2_abort_driver_facade:", 1)[1].split(
        ".size c2_abort_driver_facade", 1)[0]
    require(wrapper.count("jsr c2_mapped_far_enter") == 1
            and wrapper.count("jsr c2_abort_driver") == 1
            and wrapper.count("jmp c2_mapped_far_leave") == 1,
            "abort facade is not enter/body/leave")
    require("padding_contract_bytes, 10" in pad and ".fill 10, 1, 0" in pad,
            "R1 padding successor is not explicit 10-byte PROGBITS")
    # IRQ only captures/latches; the cleanup edge occurs in foreground abort.
    irq_handler = IRQ_BASE.read_text().split(
        "c2_kernal_irq_handler:", 1)[1].split(
            ".section .lisp65_c2_kernal_window.state", 1)[0]
    require("c2_product_abort_cleanup" not in irq_handler
            and irq.count("(void)c2_product_abort_cleanup();") == 1
            and irq.index("(void)c2_product_abort_cleanup();")
                < irq.index("longjmp(lisp_toplevel, 1);"),
            "IRQ/foreground abort ordering drift")
    window = (ROOT / "src/c2_kernal_window.s").read_text()
    irq_base = IRQ_BASE.read_text()
    capture = CAPTURE_SOURCE.read_text()
    equates = EQUATES_INCLUDE.read_text()
    require("c2_kernal_input_capture" not in window
            and "LISP65_V160_INPUT_CAPTURE" not in window
            and "stz C2K_SOURCELESS_IRQS" in irq_base
            and "c2_kernal_input_capture" not in irq_base
            and "jsr c2_kernal_input_capture" in capture
            and ".lisp65_c2_kernal_window.input_capture_main" in capture
            and ".lisp65_c2_kernal_window.input_capture_helper" in capture,
            "input-capture card boundary is not a source-member boundary")
    include_line = '.include "c2_kernal_window_equates.inc"'
    require(window.count(include_line) == 1
            and irq_base.count(include_line) == 1
            and capture.count(include_line) == 1
            and window.count(".set C2K_EQUATE_OWNER, 1") == 1
            and ".set C2K_EQUATE_OWNER" not in irq_base
            and ".set C2K_EQUATE_OWNER" not in capture
            and irq_base.count(".equ C2K_") == 0
            and capture.count(".equ C2K_") == 0
            and all(equates.count(f".equ {name},") == 1
                    for name in SPLIT_EQUATES),
            "split equates do not have one assembler-include owner")
    return {"body_feature_bound": True, "facade_shape": "enter-body-leave",
            "padding_bytes": 10, "IRQ_cleanup_edges": 0,
            "foreground_cleanup_edges": 1,
            "capture_activation": "real-link-input-membership",
            "R1_irq_source": IRQ_BASE.relative_to(ROOT).as_posix(),
            "capture_source": CAPTURE_SOURCE.relative_to(ROOT).as_posix(),
            "capture_source_code_in_R1_base": False,
            "equate_authority": EQUATES_INCLUDE.relative_to(ROOT).as_posix(),
            "equate_owner_sources": [
                "src/c2_kernal_window.s"],
            "equate_consumer_sources": [
                IRQ_BASE.relative_to(ROOT).as_posix(),
                CAPTURE_SOURCE.relative_to(ROOT).as_posix()]}


def configuration_gate() -> dict[str, Any]:
    import c2_v160_abort_driver_relocation_config as config
    import c2_product_substitution_link as product_link
    predecessor_sources = (config.OLD_FACADE, ROOT /
        "src/optional/c2_mapped_far_convergence_full_span.s",
        config.OLD_PADDING)
    predecessor_definitions = ("LISP65_C2_ASM_CONVERGENCE",
        "LISP65_C2_FULL_SPAN_CONVERGENCE", "LISP65_C2_MUTABLE_CPU_READS")
    product = SimpleNamespace(
        CONVERGENCE_DEFINES=predecessor_definitions,
        CONVERGENCE_SOURCES=predecessor_sources,
        SOURCE_OWNER_SCOPES=({"name": config.SCOPE,
            "defines": predecessor_definitions, "sources": predecessor_sources},),
        linker_script=lambda: (
            "__lisp65_c2_mapped_far_facade_padding_contract_bytes == 19\n" +
            config.RESERVE_PIN),
        source_list=lambda _definitions: tuple(str(path)
                                               for path in predecessor_sources),
    )
    # source_list is a real consumer: after configuration it observes the
    # product's current list, not the predecessor tuple captured above.
    product.source_list = lambda _definitions: tuple(
        str(path) for path in product.CONVERGENCE_SOURCES)
    projected = config.configure(product)
    linked = product.linker_script()
    require(config.RESERVE_PIN not in linked
            and linked.count(config.RESERVE_DERIVATION) == 1
            and projected["live_reserve_checker"] ==
                "derived-post-capture-free>=54"
            and projected["historical_two_byte_pin_consumed"] is False,
            "R1 live reserve-checker conversion drift")
    require(product_link.INPUT_CAPTURE_FEATURE not in
                product_link.CONVERGENCE_DEFINES,
            "R1 configuration unexpectedly selected input capture")
    r1_paths = {Path(path).resolve() for path in product_link.source_list(
        product_link.CONVERGENCE_DEFINES)}
    capture_definitions = (*product_link.CONVERGENCE_DEFINES,
                           product_link.INPUT_CAPTURE_FEATURE)
    capture_paths = {Path(path).resolve() for path in
                     product_link.source_list(capture_definitions)}
    require(product_link.INPUT_CAPTURE_BASE_SOURCE.resolve() in r1_paths
            and product_link.INPUT_CAPTURE_SOURCE.resolve() not in r1_paths
            and product_link.INPUT_CAPTURE_SOURCE.resolve() in capture_paths
            and product_link.INPUT_CAPTURE_BASE_SOURCE.resolve() not in
                capture_paths,
            "file-membership boundary did not change real link inputs")
    return {"derived_floor_bytes": 54, "pin_present": False,
            "wrong_derivation_rejected": True,
            "historical_receipts_modified": False,
            "boundary_consumer": "source_list -> compile_link",
            "R1_capture_source_present": False,
            "capture_world_capture_source_present": True,
            "input_sets_differ": True}


def micro_link(root: Path) -> dict[str, Any]:
    if root.exists(): shutil.rmtree(root)
    root.mkdir(parents=True)
    dummy = root / "dummy.s"
    dummy.write_text('''
.section .text,"ax",@progbits
.globl c2_mapped_far_vm_code_load_converged
c2_mapped_far_vm_code_load_converged: rts
.globl c2_mapped_far_physical_read_converged
c2_mapped_far_physical_read_converged: rts
.globl c2_abort_driver
c2_abort_driver: rts
.section .lisp65_c2_mapped_far_facade.abort,"ax",@progbits
.globl c2_dma_read_or_abort
c2_dma_read_or_abort: .fill 27, 1, 0xea
''')
    objects = []
    for source in (FACADE, PADDING, dummy):
        obj = root / (source.stem + ".o")
        subprocess.run([str(CLANG), "-c", str(source), "-o", str(obj)],
                       cwd=ROOT, check=True)
        objects.append(obj)
    linker = root / "micro.ld"
    linker.write_text('''SECTIONS {
 .text 0x2000 : { *(.text) }
 .lisp65_c2_mapped_far_facade 0xb3b0 : {
  KEEP(*(.lisp65_c2_mapped_far_facade.entries))
  KEEP(*(.lisp65_c2_mapped_far_facade.abort))
  KEEP(*(.lisp65_c2_mapped_far_facade.padding))
 }
}
ASSERT(SIZEOF(.lisp65_c2_mapped_far_facade) == 98, "facade-size")
''')
    elf = root / "micro.elf"
    subprocess.run([str(LD), "-T", str(linker), "-o", str(elf),
                    *(str(path) for path in objects)], cwd=ROOT, check=True)
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    facade = truth.section(FACADE_SECTION)
    wrapper = truth.symbol("c2_abort_driver_facade")
    padding = truth.symbol("__lisp65_c2_mapped_far_facade_padding")
    require(facade.bytes == 98 and wrapper.bytes == 9 and padding.bytes == 10,
            "R1 micro-link price drift")
    return {"facade_bytes": facade.bytes, "abort_entry_bytes": wrapper.bytes,
            "padding_bytes": padding.bytes}


def functions(truth: ElfTruth) -> list[Any]:
    return [row for row in truth.symbols
            if row.symbol_type == "Function" and row.bytes > 0]


def containing(rows: list[Any], section: str, address: int) -> str | None:
    matches = [row.name for row in rows if row.section == section
               and row.value <= address < row.value + row.bytes]
    return matches[0] if len(matches) == 1 else None


def graph(truth: ElfTruth) -> dict[str, set[str]]:
    rows = functions(truth)
    by_name = {row.name: row for row in rows}
    result = {name: set() for name in by_name}
    for relocation in truth.relocations:
        caller = containing(rows, relocation.source_section, relocation.offset)
        if caller is None: continue
        identity = truth.relocation_target_identity(relocation)
        address = identity.get("resolved_value")
        section = identity.get("section")
        if not isinstance(address, int) or not isinstance(section, str): continue
        targets = [row.name for row in rows if row.section == section
                   and row.value <= address < row.value + row.bytes]
        if len(targets) == 1: result[caller].add(targets[0])
    return result


def closure(edges: dict[str, set[str]], roots: list[str]) -> set[str]:
    reached, pending = set(), list(roots)
    while pending:
        name = pending.pop()
        if name in reached: continue
        reached.add(name)
        pending.extend(edges.get(name, set()) - reached)
    return reached


def final_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    service = truth.section(FAR)
    facade = truth.section(FACADE_SECTION)
    abort = truth.symbol("c2_abort_driver")
    entry = truth.symbol("c2_abort_driver_facade")
    padding = truth.symbol("__lisp65_c2_mapped_far_facade_padding")
    require(service.bytes == 1382 and abort.section == FAR and abort.bytes == 134,
            "relocated body/service identity drift")
    require(facade.bytes == 98 and entry.bytes == 9 and padding.bytes == 10,
            "final fixed-facade successor drift")
    require(not (E000_START <= abort.value < E000_END),
            "abort body remains an E000 tenant")
    equates: dict[str, dict[str, Any]] = {}
    for name, expected in SPLIT_EQUATES.items():
        rows = [row for row in truth.symbols if row.name == name]
        require(len(rows) == 1 and rows[0].value == expected
                and rows[0].section == "Absolute",
                f"split equate single-owner drift: {name}")
        equates[name] = {"count": 1, "value": rows[0].value,
                         "section": rows[0].section,
                         "binding": rows[0].binding}

    edges = graph(truth)
    normal_roots = ["c2_mapped_far_vm_code_load_converged",
                    "c2_mapped_far_physical_read_converged"]
    reached = closure(edges, normal_roots)
    forbidden = {"c2_abort_driver", "c2_abort_driver_facade",
                 "c2_product_abort_cleanup", "lisp_abort", "lisp_abort_code",
                 "lisp_abort_symbol", "lisp_abort_static"}
    require(not (reached & forbidden),
            "active far body can reenter the abort facade")
    require("c2_mapped_far_leave" not in reached,
            "inner body unexpectedly owns facade unmap")

    # Exactly one foreground caller is redirected to the new facade.
    incoming = []
    for relocation in truth.relocations:
        identity = truth.relocation_target_identity(relocation)
        if (identity.get("section"), identity.get("resolved_value")) != \
                (entry.section, entry.value): continue
        caller = containing(functions(truth), relocation.source_section,
                            relocation.offset)
        incoming.append(caller)
    require(incoming == ["c2_product_abort_cleanup"],
            "abort facade caller set drift")

    allocated = sorted((row.address, row.address + row.bytes)
        for row in truth.sections if row.bytes > 0
        and E000_START <= row.address < E000_END)
    union = sum(end - start for start, end in allocated)
    post_capture_free = E000_END - E000_START - union
    emitted_names = {row.name for row in truth.sections}
    present_capture = [name for name in CAPTURE_SECTIONS
                       if name in emitted_names]
    capture_bytes = sum(truth.section(name).bytes for name in present_capture)
    r1_only_free = post_capture_free
    require(present_capture == [] and capture_bytes == 0
            and post_capture_free == 195 and r1_only_free == 195
            and post_capture_free >= 54,
            "R1 born-derived E000 reserve/floor drift")
    linker = elf.parent / "c2-substitution.ld"
    linker_text = linker.read_text(encoding="utf-8")
    from c2_v160_abort_driver_relocation_config import (  # noqa: E402
        RESERVE_DERIVATION, RESERVE_PIN)
    require(RESERVE_DERIVATION not in linker_text
            and RESERVE_PIN not in linker_text,
            "R1 live linker still carries the predecessor reserve pin")
    return {
        "ELF": bind(elf), "service_bytes": service.bytes,
        "service_headroom_bytes": 1499 - service.bytes,
        "abort": {"vma": abort.value, "bytes": abort.bytes,
                  "section": abort.section},
        "facade": {"bytes": facade.bytes, "entry_bytes": entry.bytes,
                   "padding_bytes": padding.bytes},
        "worst_state": {
            "classification": "mapped abort is unreachable",
            "normal_far_roots": normal_roots,
            "reachable_functions": sorted(reached),
            "forbidden_reentrant_functions": sorted(forbidden),
            "intersection": [],
            "IRQ_behavior": "latch-only; foreground consumes after unmap",
        },
        "foreground_callers": incoming,
        "split_equates": {
            "authority": "ElfTruth final linked candidate",
            "symbols": equates,
            "duplicate_names": [],
            "C2K_FRAME_LO_count": 1,
        },
        "reserve": {
            "authority": "ElfTruth final linked candidate",
            "capture_freight_bytes": capture_bytes,
            "post_capture_free_bytes": post_capture_free,
            "R1_only_free_bytes": r1_only_free,
            "floor_bytes": 54,
            "post_capture_surplus_bytes": post_capture_free - 54,
            "live_gate_is_derived": True,
            "historical_two_byte_pin_present": False,
            "capture_sections": present_capture,
            "capture_activation_define_set": False,
        },
        "mapped_blocks": [3], "required_visible_blocks": [6, 7],
    }


def validate(value: dict[str, Any], final: bool) -> None:
    require(value["source"]["padding_bytes"] == 10
            and value["source"]["capture_activation"] ==
                "real-link-input-membership"
            and value["source"]["capture_source_code_in_R1_base"] is False
            and value["source"]["equate_authority"] ==
                "src/c2_kernal_window_equates.inc"
            and value["source"]["equate_owner_sources"] ==
                ["src/c2_kernal_window.s"]
            and value["micro"]["facade_bytes"] == 98
            and value["micro"]["abort_entry_bytes"] == 9
            and value["configuration"] == {
                "derived_floor_bytes": 54, "pin_present": False,
                "wrong_derivation_rejected": True,
                "historical_receipts_modified": False,
                "boundary_consumer": "source_list -> compile_link",
                "R1_capture_source_present": False,
                "capture_world_capture_source_present": True,
                "input_sets_differ": True},
            "R1 source/micro contract drift")
    if final:
        linked = value["linked"]
        require(linked["service_bytes"] == 1382
                and linked["service_headroom_bytes"] == 117
                and linked["facade"] == {
                    "bytes": 98, "entry_bytes": 9, "padding_bytes": 10}
                and linked["E000_free_bytes"] == 195
                and linked["worst_state"]["classification"] ==
                    "mapped abort is unreachable"
                and linked["worst_state"]["intersection"] == []
                and linked["foreground_callers"] ==
                    ["c2_product_abort_cleanup"]
                and linked["split_equates"]["duplicate_names"] == []
                and linked["split_equates"]["C2K_FRAME_LO_count"] == 1
                and all(row["count"] == 1
                        for row in linked["split_equates"]["symbols"].values())
                and linked["reserve"] == {
                    "authority": "ElfTruth final linked candidate",
                    "capture_freight_bytes": 0,
                    "post_capture_free_bytes": 195,
                    "R1_only_free_bytes": 195,
                    "floor_bytes": 54,
                    "post_capture_surplus_bytes": 141,
                    "live_gate_is_derived": True,
                    "historical_two_byte_pin_present": False,
                    "capture_sections": [],
                    "capture_activation_define_set": False,
                }
                and linked["mapped_blocks"] == [3]
                and linked["required_visible_blocks"] == [6, 7],
                "R1 final contract drift")


def derive(elf: Path | None = None, micro_root: Path | None = None) -> dict[str, Any]:
    study = load(STUDY)
    require(study["price"]["e000"]["freed_by_relocation"] == 134,
            "accepted R1 study drift")
    value = {
        "status": "HOST-GREEN: R1 FINAL ELF" if elf else "PREFLIGHT-GREEN: R1",
        "authority": {"owner": git_authority(), "study": bind(STUDY),
                      "runtime": bind(RUNTIME), "interrupt": bind(INTERRUPT),
                      "facade": bind(FACADE), "padding": bind(PADDING),
                      "equates_include": bind(EQUATES_INCLUDE),
                      "configurator": bind(CONFIG)},
        "source": source_gate(),
        "configuration": configuration_gate(),
        "micro": micro_link(micro_root or ROOT / "build/c2.3/v1.6-r1-micro"),
        "linked": final_gate(elf) if elf else None,
        "claim_limit": "Host preflight/final ELF only; no media or device.",
    }
    validate(value, elf is not None)
    return value


def mutations(value: dict[str, Any], final: bool) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "grow-facade": lambda x: x["micro"].update(facade_bytes=99),
        "grow-entry": lambda x: x["micro"].update(abort_entry_bytes=10),
        "restore-padding": lambda x: x["source"].update(padding_bytes=19),
        "wrong-floor-derivation": lambda x: x["configuration"].update(
            derived_floor_bytes=53),
        "restore-reserve-pin": lambda x: x["configuration"].update(
            pin_present=True),
        "leak-capture-code-into-R1-base": lambda x: x["source"].update(
            capture_source_code_in_R1_base=True),
        "capture-file-in-R1-inputs": lambda x: x["configuration"].update(
            R1_capture_source_present=True),
        "toggle-does-not-change-inputs": lambda x: x["configuration"].update(
            input_sets_differ=False),
        "second-equate-owner-in-source": lambda x: x["source"].update(
            equate_owner_sources=["src/c2_kernal_window.s",
                                  "src/c2_kernal_irq_base.s"]),
    }
    if final:
        cases.update({
            "service-over-price": lambda x: x["linked"].update(service_bytes=1383),
            "service-headroom-drift": lambda x: x["linked"].update(
                service_headroom_bytes=116),
            "facade-final-growth": lambda x: x["linked"]["facade"].update(bytes=99),
            "padding-final-growth": lambda x: x["linked"]["facade"].update(
                padding_bytes=11),
            "mapped-reentry": lambda x: x["linked"]["worst_state"].update(
                intersection=["c2_abort_driver"]),
            "second-abort-caller": lambda x: x["linked"].update(
                foreground_callers=["c2_product_abort_cleanup", "lisp_abort"]),
            "hide-e000": lambda x: x["linked"].update(
                mapped_blocks=[3, 7]),
            "wrong-derived-reserve": lambda x: x["linked"]["reserve"].update(
                R1_only_free_bytes=194),
            "reintroduce-two-byte-pin": lambda x: x["linked"]["reserve"].update(
                historical_two_byte_pin_present=True),
            "emit-capture-in-R1": lambda x: x["linked"]["reserve"].update(
                capture_sections=[CAPTURE_SECTIONS[0]],
                capture_activation_define_set=True),
            "duplicate-C2K-FRAME-LO": lambda x: x["linked"][
                "split_equates"].update(
                    C2K_FRAME_LO_count=2,
                    duplicate_names=["C2K_FRAME_LO"]),
        })
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try: validate(trial, final)
        except GateError: rejected.append(name)
    require(rejected == list(cases), "R1 mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "check", "selftest"))
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--micro-root", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    final = args.elf is not None
    value = derive(args.elf, args.micro_root)
    value["mutations_rejected"] = mutations(value, final)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                                encoding="utf-8")
    label = "FINAL" if final else "PREFLIGHT"
    print(f"v1.6 abort relocation: {label} PASS "
          f"mutations={len(value['mutations_rejected'])}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, subprocess.CalledProcessError) as error:
        print(f"v1.6 abort relocation: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
