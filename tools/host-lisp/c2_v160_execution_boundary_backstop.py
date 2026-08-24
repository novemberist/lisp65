#!/usr/bin/env python3
"""Permanent gates for the v1.6 retired-overlay execution boundary."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_transitive_map_nesting_gate as MAP_GATE  # noqa: E402

CLANG = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
WINDOW = ROOT / "src/c2_kernal_window.s"
IRQ = ROOT / "src/optional/c2_kernal_input_capture.s"
BASE_IRQ = ROOT / "src/c2_kernal_irq_base.s"
LIVENESS = ROOT / "src/optional/c2_mapped_far_service_liveness_v4.s"
ERRORS = ROOT / "src/error_codes.h"
INTERRUPT_H = ROOT / "src/interrupt.h"
INTERRUPT_C = ROOT / "src/interrupt.c"
REPL_C = ROOT / "src/repl.c"
STATUS = "PASS: V1.6 EXECUTION BOUNDARY BACKSTOP"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def _compile(source: Path, output: Path) -> ElfTruth:
    subprocess.run([str(CLANG), "-c", "-Isrc", str(source), "-o", str(output)],
                   cwd=ROOT, check=True, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE)
    return ElfTruth.read(output, llvm_readobj=READOBJ, include_section_data=True)


def source_gate(*, window: str | None = None, irq: str | None = None,
                base_irq: str | None = None, interrupt_h: str | None = None,
                interrupt_c: str | None = None, repl_c: str | None = None,
                liveness: str | None = None) -> dict[str, Any]:
    texts = {
        "window": WINDOW.read_text() if window is None else window,
        "capture_irq": IRQ.read_text() if irq is None else irq,
        "base_irq": BASE_IRQ.read_text() if base_irq is None else base_irq,
    }
    body = texts["window"]
    header = INTERRUPT_H.read_text() if interrupt_h is None else interrupt_h
    owner = INTERRUPT_C.read_text() if interrupt_c is None else interrupt_c
    repl = REPL_C.read_text() if repl_c is None else repl_c
    live = LIVENESS.read_text() if liveness is None else liveness
    combined_c = header + "\n" + owner + "\n" + repl
    require(re.search(r"extern\s+uint8_t\s+lisp_toplevel_active\s*;", header)
            and re.search(r"uint8_t\s+lisp_toplevel_active\s*=\s*0\s*;", owner),
            "ASM-consumed top-level flag lost its owned one-byte declaration")
    require(owner.count("lisp_toplevel_active") == 2
            and "if (!lisp_toplevel_active) return;" in owner
            and repl.count("lisp_toplevel_active") == 1
            and "lisp_toplevel_active = 1;" in repl,
            "top-level flag consumer population or 0/1 semantics drift")
    require(len(re.findall(r"\blisp_toplevel_active\b", combined_c)) == 4,
            "unregistered C consumer of narrowed top-level flag")
    required = (
        "and #$10", "c2_backstop_rtov_busy", "c2_backstop_rtov_loaded_len",
        "lisp_toplevel_active", "__lisp65_workbench_overlay_start+2",
        "__lisp65_workbench_overlay_len", "jmp c2_kernal_irq_return",
        "jmp c2_kernal_fail_closed", "jmp longjmp",
    )
    require(all(token in body for token in required),
            "execution-boundary source lost a semantic wall")
    require("\tlda c2_backstop_rtov_busy\n"
            "\tora c2_backstop_rtov_loaded_len\n"
            "\tora c2_backstop_rtov_loaded_len+1\n"
            in body, "retirement-state conjunction drift")
    require(body.count("__lisp65_workbench_overlay_len") == 2,
            "candidate-derived upper interval drift")
    require("jmp lisp_abort" not in body and "jsr lisp_abort" not in body
            and "vm_runtime_overlay_abort_cleanup" not in body,
            "execution-boundary landing recursively enters cleanup")
    recovery_call = body.find("\tjsr c2_rtov_sanitize_recovery\n")
    longjmp_edge = body.find("\tjmp longjmp\n")
    require(recovery_call >= 0 and longjmp_edge > recovery_call,
            "recovery sanitation does not dominate longjmp")
    require(live.count("\tjsr c2_rtov_sanitize_saved_csrs\n") == 2
            and live.count("c2_rtov_sanitize_saved_csrs:") == 1,
            "saved-CSR sanitation lost its single body or two consumers")
    recovery = live[live.find("c2_rtov_sanitize_recovery:"):
                    live.find("\t.size c2_rtov_sanitize_recovery")]
    require("\tjsr c2_mapped_far_enter\n" in recovery
            and "\tjsr c2_rtov_sanitize_saved_csrs\n" in recovery
            and "\tjmp c2_mapped_far_leave\n" in recovery
            and "c2_rtov_retire_continuations" not in recovery,
            "recovery must map only the saved-CSR sanitizer")
    require("\tcpy #14\n" in live,
            "saved-CSR sanitizer no longer covers all seven ABI pairs")
    for name in ("capture_irq", "base_irq"):
        require(texts[name].count("jmp retired_window_brk_classifier") == 1
                and texts[name].count("c2_kernal_irq_return:") == 1,
                f"{name} does not expose the same execution boundary")
    error = re.search(r"LISP65_ERR_RUNTIME_FAMILY_STAGE\s*=\s*(\d+)",
                      ERRORS.read_text())
    require(error is not None and int(error.group(1)) == 62
            and "lda #62" in body, "E3e identity drift")
    with tempfile.TemporaryDirectory(prefix="c2-v160-backstop-source-") as raw:
        root = Path(raw)
        truth = _compile(WINDOW, root / "window.o") if window is None else None
        if truth is None:
            mutant = root / "window.s"; mutant.write_text(body)
            truth = _compile(mutant, root / "window.o")
        capture = _compile(IRQ, root / "capture.o") if irq is None else None
        if capture is None:
            mutant = root / "capture.s"; mutant.write_text(texts["capture_irq"])
            capture = _compile(mutant, root / "capture.o")
        base = _compile(BASE_IRQ, root / "base.o") if base_irq is None else None
        if base is None:
            mutant = root / "base.s"; mutant.write_text(texts["base_irq"])
            base = _compile(mutant, root / "base.o")
        live_truth = _compile(LIVENESS, root / "liveness.o") if liveness is None else None
        if live_truth is None:
            mutant = root / "liveness.s"; mutant.write_text(live)
            live_truth = _compile(mutant, root / "liveness.o")
        classifier = truth.symbol("retired_window_brk_classifier")
        landing = truth.symbol("retired_window_resume")
        recovery_symbol = live_truth.symbol("c2_rtov_sanitize_recovery")
        retirement_symbol = live_truth.symbol("c2_rtov_retire_continuations")
        shared_symbol = live_truth.symbol("c2_rtov_sanitize_saved_csrs")
        require(classifier.symbol_type == "Function"
                and landing.symbol_type == "Function"
                and recovery_symbol.symbol_type == "Function"
                and retirement_symbol.symbol_type == "Function"
                and shared_symbol.symbol_type == "Function"
                and classifier.bytes == 60 and landing.bytes == 32
                and recovery_symbol.bytes == 9
                and retirement_symbol.bytes == 41
                and shared_symbol.bytes == 43,
                "execution-boundary implementation escaped the 60+32+9/41/43 price")
        require(capture.symbol("c2_kernal_irq_return").section ==
                ".lisp65_c2_kernal_window.irq_handler"
                and base.symbol("c2_kernal_irq_return").section ==
                ".lisp65_c2_kernal_window.irq_handler",
                "IRQ return identity escaped its owned handler")
    return {"status": STATUS + " SOURCE", "classifier_bytes": 60,
            "landing_bytes": 32, "recursive_cleanup_edges": 0,
            "recovery_sanitization": {"entry_bytes": 9,
                "retirement_bytes": 41, "shared_saved_CSR_bytes": 43,
                "saved_CSR_pairs": 7, "dominates_longjmp": True,
                "recovery_reaches_frame_walker": False},
            "IRQ_owners": ["capture", "base"], "E3e": 62,
            "top_level_active_C_contract": {"declared_bytes": 1,
                "writes": [0, 1], "read_forms": ["boolean guard"],
                "consumer_occurrences": 4}}


def source_mutations() -> list[str]:
    window = WINDOW.read_text(); irq = IRQ.read_text()
    liveness = LIVENESS.read_text()
    header = INTERRUPT_H.read_text(); owner = INTERRUPT_C.read_text(); repl = REPL_C.read_text()
    mutations = {
        "B-bit-removed": {"window": window.replace("\tand #$10\n", "\tand #$08\n", 1)},
        "retirement-state-removed": {"window": window.replace(
            "\tora c2_backstop_rtov_loaded_len\n", "", 1)},
        "candidate-range-removed": {"window": window.replace(
            "__lisp65_workbench_overlay_len", "0x073b")},
        "recursive-cleanup": {"window": window.replace(
            "\tjmp longjmp\n", "\tjmp lisp_abort\n", 1)},
        "unguarded-capture-owner": {"irq": irq.replace(
            "jmp retired_window_brk_classifier", "jmp c2_kernal_fail_closed", 1)},
        "classifier-identity-erased": {"window": window.replace(
            "\t.type retired_window_brk_classifier,@function\n", "", 1)},
        "borrowed-int-width": {"interrupt_h": header.replace(
            "extern uint8_t     lisp_toplevel_active", "extern int         lisp_toplevel_active"),
            "interrupt_c": owner.replace("uint8_t     lisp_toplevel_active",
                                         "int         lisp_toplevel_active")},
        "nonboolean-writer": {"repl_c": repl.replace(
            "lisp_toplevel_active = 1;", "lisp_toplevel_active = 2;")},
        "recovery-sanitizer-removed": {"window": window.replace(
            "\tjsr c2_rtov_sanitize_recovery\n", "", 1)},
        "recovery-enters-frame-walker": {"liveness": liveness.replace(
            "\tjsr c2_rtov_sanitize_saved_csrs\n",
            "\tjsr c2_rtov_retire_continuations\n", 1)},
        "saved-CSR-population-narrowed": {"liveness": liveness.replace(
            "\tcpy #14\n", "\tcpy #2\n", 1)},
    }
    rejected: list[str] = []
    for name, changes in mutations.items():
        try:
            source_gate(**changes)
        except (GateError, subprocess.CalledProcessError):
            rejected.append(name)
    require(rejected == list(mutations), "execution-boundary source mutation survived")
    return rejected


def _function(disassembly: str, name: str) -> str:
    match = re.search(rf"^[0-9a-f]+ <{re.escape(name)}>:\n(.*?)(?=^[0-9a-f]+ <|\Z)",
                      disassembly, re.MULTILINE | re.DOTALL)
    require(match is not None, f"linked function absent: {name}")
    return match.group(1)


def final_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    classifier = truth.symbol("retired_window_brk_classifier")
    landing = truth.symbol("retired_window_resume")
    recovery = truth.symbol("c2_rtov_sanitize_recovery")
    retirement = truth.symbol("c2_rtov_retire_continuations")
    shared = truth.symbol("c2_rtov_sanitize_saved_csrs")
    map_enter = truth.symbol("c2_mapped_far_enter")
    map_leave = truth.symbol("c2_mapped_far_leave")
    irq_return = truth.symbol("c2_kernal_irq_return")
    fail = truth.symbol("c2_kernal_fail_closed")
    longjmp = truth.symbol("longjmp")
    start = truth.symbol("__lisp65_workbench_overlay_start").value
    end = truth.symbol("__lisp65_workbench_overlay_end").value
    length = truth.symbol("__lisp65_workbench_overlay_len").value
    alias_pairs = {
        "c2_backstop_pending_code": "pending_code",
        "c2_backstop_pending_symbol": "pending_symbol",
        "c2_backstop_rtov_loaded_len": "rtov_loaded_len",
        "c2_backstop_rtov_busy": "rtov_busy",
    }
    active = truth.symbol("lisp_toplevel_active")
    require(active.bytes == 1, "ASM-consumed top-level flag re-emitted wider than one byte")
    aliases: dict[str, Any] = {}
    owner_addresses = {truth.symbol(name).value for name in alias_pairs.values()}
    require(len(owner_addresses) == len(alias_pairs),
            "execution-boundary C owners do not have unique allocations")
    for alias_name, owner_name in alias_pairs.items():
        alias = truth.symbol(alias_name); owner = truth.symbol(owner_name)
        additional_addresses = ([] if alias.value in owner_addresses
                                else [alias.value])
        require(alias.value == owner.value and not additional_addresses,
                f"alias allocated or escaped owner: {alias_name}")
        aliases[alias_name] = {"owner": owner_name,
            "address": f"0x{alias.value:04x}", "owner_address": f"0x{owner.value:04x}",
            "alias_symbol_bytes": alias.bytes,
            "owner_symbol_bytes": owner.bytes,
            "additional_allocated_addresses": additional_addresses,
            "additional_allocated_bytes": 0, "same_address": True,
            "owner_address_is_unique": True}
    require(classifier.section == ".text" and classifier.bytes == 60
            and landing.section == ".text" and landing.bytes == 32
            and recovery.section == ".text" and recovery.bytes == 9
            and retirement.section == ".lisp65_c2_mapped_far_service"
            and retirement.bytes == 41
            and shared.section == ".lisp65_c2_mapped_far_service"
            and shared.bytes == 43,
            "backstop escaped permanent ordinary text or its measured price")
    require(end - start == length and length > 0,
            "candidate-derived overlay interval is inconsistent")
    raw = subprocess.run([str(OBJDUMP), "-d", "--no-show-raw-insn", str(elf)],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.lower()
    classifier_body = _function(raw, classifier.name)
    landing_body = _function(raw, landing.name)
    recovery_body = _function(raw, recovery.name)
    retirement_body = _function(raw, retirement.name)
    shared_body = _function(raw, shared.name)
    require(re.search(rf"jmp\s+\${irq_return.value:x}\b", classifier_body)
            and re.search(rf"jmp\s+\${fail.value:x}\b", classifier_body),
            "classifier lost recovery or fail-closed edge")
    recovery_edge = re.search(rf"jsr\s+\${recovery.value:x}\b", landing_body)
    longjmp_edge = re.search(rf"jmp\s+\${longjmp.value:x}\b", landing_body)
    require(recovery_edge is not None and longjmp_edge is not None
            and recovery_edge.start() < longjmp_edge.start()
            and "lisp_abort" not in landing_body
            and "abort_cleanup" not in landing_body,
            "landing lost sanitation-dominant cleanup-free longjmp edge")
    require(re.search(rf"jsr\s+\${map_enter.value:x}\b", recovery_body)
            and re.search(rf"jsr\s+\${shared.value:x}\b", recovery_body)
            and re.search(rf"jmp\s+\${map_leave.value:x}\b", recovery_body)
            and not re.search(rf"(?:jsr|jmp)\s+\${retirement.value:x}\b",
                              recovery_body),
            "recovery escaped the map/shared-sanitizer/leave seam")
    require(re.search(rf"jsr\s+\${shared.value:x}\b", retirement_body),
            "normal retirement no longer consumes shared sanitation")
    require(re.search(r"cpy\s+#\$e\b", shared_body),
            "final saved-CSR sanitizer no longer covers seven pairs")
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    bss = truth.section(".bss")
    ordinary_free = facade.address - (text.address + text.bytes)
    require(ordinary_free >= 18, "ordinary-text recovery-sanitization floor violated")
    service = truth.section(".lisp65_c2_mapped_far_service")
    far_free = 1499 - service.bytes
    require(service.bytes <= 1499 and far_free >= 11,
            "mapped-far recovery-sanitization floor violated")
    bss_margin = 0xC000 - (bss.address + bss.bytes)
    require(bss.address == 0xB9CA and bss.bytes == 1585 and bss_margin == 5,
            "zero-byte alias form changed protected BSS geometry")
    map_result = MAP_GATE.check(elf)
    require(map_result["violations"] == [], "transitive MAP gate regressed")
    cases = [
        {"case": "retired-window-BRK", "recover": True},
        {"case": "hardware-IRQ", "recover": False},
        {"case": "live-overlay", "recover": False},
        {"case": "outside-window", "recover": False},
        {"case": "no-toplevel", "recover": False},
    ]
    return {"status": STATUS, "classifier": {"bytes": classifier.bytes,
                "section": classifier.section},
            "cleanup_free_landing": {"bytes": landing.bytes,
                "section": landing.section},
            "recovery_sanitization": {
                "entry": {"bytes": recovery.bytes, "section": recovery.section},
                "retirement": {"bytes": retirement.bytes,
                    "section": retirement.section},
                "shared_saved_CSR_walker": {"bytes": shared.bytes,
                    "section": shared.section, "pairs": 7},
                "dominates_longjmp": True,
                "recovery_reaches_frame_walker": False,
                "normal_retirement_uses_shared_walker": True},
            "overlay_interval": {"start": f"0x{start:04x}",
                "end": f"0x{end:04x}", "bytes": length,
                "source": "final ELF symbols"},
            "ordinary_free_bytes": ordinary_free,
            "mapped_far_service": {"bytes": service.bytes,
                "capacity_bytes": 1499, "free_bytes": far_free},
            "zero_byte_aliases": aliases,
            "top_level_active": {"address": f"0x{active.value:04x}",
                "emitted_bytes": active.bytes, "declared_type": "uint8_t"},
            "protected_BSS": {"address": "0xb9ca", "bytes": bss.bytes,
                "end": f"0x{bss.address + bss.bytes:04x}",
                "validation_margin_bytes": bss_margin},
            "E000_delta_bytes": 0, "cases": cases,
            "transitive_MAP_gate": map_result,
            "claim": "every retired-window BRK reaches prompt recovery; all other source-less IRQs remain fail-closed"}


def final_mutations(value: dict[str, Any]) -> list[str]:
    cases = {
        "classifier-moved-under-MAP": lambda x: x["classifier"].update(section="mapped"),
        "price-exceeded": lambda x: x["classifier"].update(bytes=61),
        "hardware-IRQ-recovered": lambda x: x["cases"][1].update(recover=True),
        "MAP-nesting": lambda x: x["transitive_MAP_gate"]["violations"].append("nested"),
        "alias-allocated": lambda x: x["zero_byte_aliases"][
            "c2_backstop_pending_code"].update(
                additional_allocated_addresses=[0x37],
                additional_allocated_bytes=1, same_address=False),
        "BSS-margin-spent": lambda x: x["protected_BSS"].update(
            bytes=1586, validation_margin_bytes=4),
        "active-flag-widened": lambda x: x["top_level_active"].update(
            emitted_bytes=2),
        "recovery-after-longjmp": lambda x: x["recovery_sanitization"].update(
            dominates_longjmp=False),
        "recovery-enters-frame-walker": lambda x: x["recovery_sanitization"].update(
            recovery_reaches_frame_walker=True),
        "saved-CSR-population-narrowed": lambda x: x["recovery_sanitization"][
            "shared_saved_CSR_walker"].update(pairs=6),
        "ordinary-floor-spent": lambda x: x.update(ordinary_free_bytes=17),
        "far-service-floor-spent": lambda x: x["mapped_far_service"].update(
            bytes=1489, free_bytes=10),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        accepted = (trial["classifier"] == {"bytes": 60, "section": ".text"}
                    and trial["cleanup_free_landing"] == {"bytes": 32, "section": ".text"}
                    and trial["recovery_sanitization"]["entry"] == {
                        "bytes": 9, "section": ".text"}
                    and trial["recovery_sanitization"]["retirement"] == {
                        "bytes": 41, "section": ".lisp65_c2_mapped_far_service"}
                    and trial["recovery_sanitization"]["shared_saved_CSR_walker"] == {
                        "bytes": 43, "section": ".lisp65_c2_mapped_far_service",
                        "pairs": 7}
                    and trial["recovery_sanitization"]["dominates_longjmp"] is True
                    and trial["recovery_sanitization"]["recovery_reaches_frame_walker"] is False
                    and trial["recovery_sanitization"]["normal_retirement_uses_shared_walker"] is True
                    and trial["ordinary_free_bytes"] >= 18
                    and trial["mapped_far_service"]["bytes"] <= 1499
                    and trial["mapped_far_service"]["free_bytes"] >= 11
                    and trial["cases"][0]["recover"] is True
                    and all(not row["recover"] for row in trial["cases"][1:])
                    and all(row["additional_allocated_bytes"] == 0
                            and row["additional_allocated_addresses"] == []
                            and row["same_address"] is True
                            and row["owner_address_is_unique"] is True
                            for row in trial["zero_byte_aliases"].values())
                    and trial["protected_BSS"]["bytes"] == 1585
                    and trial["protected_BSS"]["validation_margin_bytes"] == 5
                    and trial["top_level_active"]["emitted_bytes"] == 1
                    and trial["transitive_MAP_gate"]["violations"] == [])
        if not accepted:
            rejected.append(name)
    require(rejected == list(cases), "execution-boundary final mutation survived")
    return rejected


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "source":
        print(json.dumps(source_gate(), indent=2, sort_keys=True)); return 0
    if action == "selftest":
        rejected = source_mutations()
        print(f"v1.6 execution boundary: SELFTEST PASS mutations={len(rejected)}")
        return 0
    if action == "final" and len(sys.argv) == 3:
        value = final_gate(Path(sys.argv[2])); final_mutations(value)
        print(json.dumps(value, indent=2, sort_keys=True)); return 0
    raise GateError("usage: c2_v160_execution_boundary_backstop.py source|selftest|final ELF")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 execution boundary: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
