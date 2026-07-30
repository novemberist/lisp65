#!/usr/bin/env python3
"""Bind the read-only v1.2.4 BASIC-65 parity revalidation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

from elf_truth import ElfTruth, ElfTruthError


ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/planning/basic65-parity-revalidation-2026-07-30.md"
PLAN = ROOT / "docs/planning/1.2.4-work-plan.md"
OLD_DESIGN = (
    ROOT / "docs/archive/pre-1.0/designs/mega65-basic-parity-libraries.md")
SCOPE = ROOT / "docs/planning/v1.2-scope-memo.md"
LINK80 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.3-phase-b-link80-receipt.json")
G_PROBE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-g-language-polish-probe-receipt.json")
L_LITE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-l-lite-probe-receipt.json")
HW_AUDIT = ROOT / (
    "docs/archive/pre-1.0/reference/mega65-hardware-opportunity-audit.md")
TICK_CONTRACT = ROOT / "docs/planning/v11-g-contract-drafts.md"
L10_CONTRACT = (
    ROOT / "docs/planning/c2.2-runtime-overlay-dma-completion-contract.md")
SESSION_SERVICE = ROOT / "config/c2-session-service-contract.json"
WORD_TOMBSTONE = ROOT / "config/v11-g-word-access-tombstone.json"
KEYMAP = ROOT / "config/v11-l-lite-keymap.json"
REGISTRY = ROOT / "config/v2-native-function-registry.json"
BUFFER = ROOT / "lib/buffer.lisp"
KERNAL_HEADER = ROOT / "src/c2_kernal_runtime.h"
KERNAL_WINDOW = ROOT / "src/c2_kernal_window.s"
SCREEN = ROOT / "src/screen.c"
SCREEN_OVERLAY = ROOT / "src/screen_scroll_overlay.c"
C2_RUNTIME = ROOT / "src/c2_product_runtime.c"
LINK80_ELF = ROOT / (
    "build/c2.2/v1.2.3-candidate-product-link80/final/"
    "lisp65-c2-substitution-linked.prg.elf")
DRIVER = Path(__file__).resolve()
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-basic65-parity-revalidation-receipt.json")

CC = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
SIZE = ROOT / "tools/llvm-mos/bin/llvm-size"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

FORMAT = "lisp65-c2.2-v1.2.4-basic65-parity-revalidation-v1"


class RevalidationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RevalidationError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing file: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(
        result.returncode == 0,
        f"{label} failed ({result.returncode}):\n{result.stdout[-6000:]}")
    return result.stdout


def validate_document(text: str) -> None:
    required = [
        "The five obsolete assumptions",
        "C2 direct execution",
        "Byte transport is no longer missing",
        "Bit operations are delivered",
        "Raster ownership exists",
        "Input is an atomic typed event",
        "Revalidated module graph",
        "24,051 B",
        "Session native family | 113 B",
        "m65-word-read",
        "m65-word-write",
        "622 B code",
        "20 B job state",
        "1,024-byte allocation",
        "911 bytes more",
        "$FF80000",
        "`(time form)` time base",
        "low byte `$FF83`, high byte `$FF84`",
        "20 ms per frame",
        "327.68 seconds",
        "Tick-hook scheduling contract draft",
        "`VM_YIELD_SAFE`",
        "Pilot contract for 1.3",
        "2,048 Bank-2 bytes",
        "no product authorization",
    ]
    for token in required:
        require(token in text, f"revalidation document lacks: {token}")
    modules = [
        "`m65-hw`", "`m65-text`", "`m65-input`", "`m65-gfx`",
        "`m65-draw`", "`m65-disk`", "`m65-sprite`", "`m65-sound`",
        "`m65-system`", "`basic65`",
    ]
    for module in modules:
        require(text.count(module) >= 1, f"module is not graphed: {module}")
    forbidden_claims = [
        "Phase R complete; product authorized",
        "Color-RAM scroll rider is affordable",
        "callback may run from `lisp_poll()`",
        "callback may run in IRQ context",
        "full unsigned word Fixnum",
    ]
    for token in forbidden_claims:
        require(token not in text, f"forbidden parity claim survived: {token}")


def document_mutations(text: str) -> list[str]:
    replacements = [
        ("24,051 B", "24,052 B"),
        ("Session native family | 113 B", "Session native family | 114 B"),
        ("622 B code", "621 B code"),
        ("20 B job state", "19 B job state"),
        ("1,024-byte allocation", "512-byte allocation"),
        ("low byte `$FF83`, high byte `$FF84`",
         "low byte `$FF84`, high byte `$FF83`"),
        ("20 ms per frame", "16 ms per frame"),
        ("`VM_YIELD_SAFE`", "`lisp_poll`"),
        ("2,048 Bank-2 bytes", "4,096 Bank-2 bytes"),
        ("no product authorization", "product authorized"),
    ]
    rejected: list[str] = []
    for old, new in replacements:
        require(old in text, f"mutation source missing: {old}")
        try:
            validate_document(text.replace(old, new))
        except RevalidationError:
            rejected.append(f"{old} -> {new}")
    require(
        len(rejected) == len(replacements),
        "one or more parity-document mutations survived")
    return rejected


def overlay_measurement() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="lisp65-v124-r-") as raw:
        obj = Path(raw) / "screen-scroll.o"
        run(
            [
                str(CC), "-Os", "-fno-lto",
                "-DLISP65_SCREEN_EDMA_SCROLL",
                "-DLISP65_RUNTIME_OVERLAY",
                "-Isrc", "-c", str(SCREEN_OVERLAY), "-o", str(obj),
            ],
            "current color-scroll native-body compile")
        size_output = run([str(SIZE), "-A", str(obj)], "color-scroll size")
        code_match = re.search(
            r"^\.lisp65_rt_screen_scroll\s+(\d+)\s+", size_output,
            re.MULTILINE)
        data_match = re.search(
            r"^\.lisp65_rt_screen_scroll_data\s+(\d+)\s+", size_output,
            re.MULTILINE)
        require(code_match is not None and data_match is not None,
                "color-scroll section sizes missing")
        code = int(code_match.group(1))
        data = int(data_match.group(1))
        require(code == 622 and data == 20,
                f"color-scroll size drift: code={code} data={data}")
        return {
            "compiler": run([str(CC), "--version"], "compiler version")
                .splitlines()[0],
            "compile_flags": [
                "-Os", "-fno-lto", "-DLISP65_SCREEN_EDMA_SCROLL",
                "-DLISP65_RUNTIME_OVERLAY", "-Isrc",
            ],
            "code_bytes": code,
            "job_state_bytes": data,
            "raw_total_bytes": code + data,
            "packing_quantum_bytes": 512,
            "packed_allocation_bytes": 1024,
            "session_headroom_bytes": 113,
            "shortfall_before_record_or_dispatch_bytes": 911,
        }


def linked_native_facts() -> dict[str, Any]:
    elf = ElfTruth.read(LINK80_ELF, llvm_readobj=READOBJ)
    copy_bytes = elf.symbol("c2_product_physical_copy").bytes
    job_bytes = elf.symbol("c2_edma_job").bytes
    require(copy_bytes == 145 and job_bytes == 20,
            "Link-80 private EDMA cost drift")
    return {
        "private_copy_code_bytes": copy_bytes,
        "private_job_bytes": job_bytes,
        "public_api": False,
        "fill_semantics": False,
        "caller_owned_content_fence": True,
    }


def collect() -> dict[str, Any]:
    text = DOC.read_text(encoding="utf-8")
    validate_document(text)
    mutations = document_mutations(text)

    link80 = load(LINK80)
    candidate = link80.get("qualifying_candidate", {})
    walls = candidate.get("walls", {})
    require(
        candidate.get("link") == 80
        and candidate.get("bank2", {}).get("headroom_bytes") == 24051
        and walls == {
            "bank0_text_headroom_bytes": 243,
            "e000_headroom_bytes": 54,
            "fixed_hot_block_headroom_bytes": 2,
            "ordinary_bank0_bss_headroom_bytes": 137,
            "resident_island_headroom_bytes": 50,
            "session_family_headroom_bytes": 113,
        },
        "Link-80 capacity authority drift")

    g_probe = load(G_PROBE)
    tick = g_probe.get("variants", {}).get("tick", {})
    require(
        tick.get("status") == "passed-not-promoted"
        and tick.get("delta_from_baseline", {}).get(
            "bank_post_boot_reserve_bytes") == -23
        and g_probe.get("semantic_results", {}).get(
            "tick_hook", {}).get("status")
        == "lower-bound-only-not-a-hook-candidate",
        "historical 23-byte tick floor drift")

    word = load(WORD_TOMBSTONE)
    require(
        word.get("names") == ["peekw", "pokew"]
        and "15-bit fixnum" in word.get("reason", "").lower(),
        "word-access tombstone drift")

    service = load(SESSION_SERVICE)
    require(
        service.get("capacity", {}).get("slice_limit_bytes") == 1792
        and service.get("capacity", {}).get(
            "packing_quantum_bytes") == 512,
        "Session service geometry drift")

    kernal = KERNAL_HEADER.read_text(encoding="utf-8")
    require(
        "#define LISP65_C2_FRAME_LO_ADDRESS 0xff83u" in kernal
        and "#define LISP65_C2_FRAME_HI_ADDRESS 0xff84u" in kernal
        and "high_a = *high_cell;" in kernal
        and "low = *low_cell;" in kernal
        and "high_b = *high_cell;" in kernal
        and "while (high_a != high_b)" in kernal,
        "owned frame-counter read contract drift")

    irq = KERNAL_WINDOW.read_text(encoding="utf-8")
    irq_handler = irq[
        irq.index("c2_kernal_irq_handler:"):
        irq.index("c2_kernal_nmi_handler:")
    ]
    require(
        "inc C2K_FRAME_LO" in irq
        and "inc C2K_FRAME_HI" in irq
        and "jsr" not in irq_handler,
        "owned raster source drift")

    registry = load(REGISTRY)
    entries = {
        row.get("name"): row for row in registry.get("entries", [])
        if isinstance(row, dict)
    }
    require(
        entries.get("key-event", {}).get("value") == 60
        and entries.get("peek", {}).get("value") == 61
        and entries.get("poke", {}).get("value") == 62,
        "native input/memory registry drift")
    keymap = load(KEYMAP)
    require(
        keymap.get("status") == "c2-l-full-product"
        and keymap.get("event_model", {}).get("modifier_identity")
        == "consumed-from-the-same-typed-queue-event",
        "typed-event keymap drift")

    buffer = BUFFER.read_text(encoding="utf-8")
    for name in (
            "make-buffer", "buffer-length", "buffer-ref", "buffer-set!",
            "buffer->string", "string->buffer"):
        require(f"(defun {name}" in buffer, f"Buffer surface missing {name}")

    l_lite = load(L_LITE)
    rider = l_lite.get("color_scroll_rider", {})
    require(
        rider.get("resident_attempt", {}).get("overrun_bytes") == 338
        and rider.get("status")
        == "final-fallback-to-c2-after-authorized-retry-hard-gate",
        "historical color-scroll integration disposition drift")
    audit = HW_AUDIT.read_text(encoding="utf-8")
    require(
        "hw-edma-screen-smoke" in audit
        and "7/7" in audit
        and "bank0_text_data_bytes" in audit
        and "(+439)" in audit
        and "bank0_bss_bytes" in audit
        and "(+14)" in audit,
        "historical color-scroll mechanics/cost authority drift")

    overlay = overlay_measurement()
    native = linked_native_facts()

    authorities = [
        PLAN, DOC, OLD_DESIGN, SCOPE, LINK80, G_PROBE, L_LITE, HW_AUDIT,
        TICK_CONTRACT, L10_CONTRACT, SESSION_SERVICE, WORD_TOMBSTONE,
        KEYMAP, REGISTRY, BUFFER, KERNAL_HEADER, KERNAL_WINDOW, SCREEN,
        SCREEN_OVERLAY, C2_RUNTIME, LINK80_ELF, DRIVER,
    ]
    return {
        "format": FORMAT,
        "recorded_on": "2026-07-30",
        "status": "passed-read-only-parity-revalidation",
        "five_replacements": [
            "resident-or-disk delivery -> C2 Bank-2/Bank-3 direct execution",
            "missing byte carrier -> delivered first-class Buffer",
            "missing bitops -> delivered bitops with Buffer-valued word API",
            "deferred timer -> owned raster plus drafted safe scheduler boundary",
            "GETIN input -> atomic typed key-event",
        ],
        "module_graph": {
            "prefixed_modules": 9,
            "optional_facades": 1,
            "priority_one": "m65-hw",
            "pilot_status": "paper-only-waits-for-1.3-ship-builder",
        },
        "capacity": {
            "bank2_headroom_bytes": 24051,
            "p1_recommended_bank2_envelope_bytes": 2048,
            "closed_walls": walls,
            "session_native_slice_limit_bytes": 1792,
            "session_packing_quantum_bytes": 512,
        },
        "word_access": {
            "old_names": "remain-tombstoned",
            "replacement":
                "two-byte-little-endian-Buffer-read-and-write",
            "reason":
                "bitops compose bytes but do not widen signed 15-bit Fixnums",
        },
        "time_base": {
            "owner": "product VIC raster IRQ",
            "low_address": "0xff83",
            "high_address": "0xff84",
            "atomic_read": "high-low-high",
            "nominal_hz": 50,
            "milliseconds_per_frame": 20,
            "fixnum_result_limit_frames": 16383,
            "maximum_representable_interval_seconds": 327.68,
            "historical_native_floor_bytes": 23,
            "resident_delta_required": 0,
        },
        "tick_hook": {
            "implementation_status": "not-authorized",
            "legal_boundary": "top-level-after-VM_YIELD_SAFE",
            "forbidden_boundaries": [
                "IRQ/NMI", "lisp_poll", "nested evaluator",
                "blocking key-event", "GC", "C2J/append/rollback",
                "overlay or Session-service ownership", "disk mutation",
            ],
            "callback_identity": "canonical-symbol-value-not-private-registry",
        },
        "color_path": {
            "isolated_hardware_cases": "7/7",
            "historical_resident_delta": {
                "text_bytes": 439,
                "bss_bytes": 14,
            },
            "current_native_body": overlay,
            "linked_private_transport": native,
            "completion_status":
                "prototype-predates-L10-and-is-not-product-complete",
            "v1.2.4_disposition": "not-affordable-remains-parked",
        },
        "mutations": {
            "attempted": len(mutations),
            "rejected": len(mutations),
            "cases": mutations,
        },
        "scope_effects": {
            "product_source_bytes": 0,
            "product_links": 0,
            "wplto_runs": 0,
            "hardware_runs": 0,
        },
        "authorities": {
            path.relative_to(ROOT).as_posix(): bind(path)
            for path in authorities
        },
        "claim_limit": (
            "Read-only source, historical hardware, linked-artifact and "
            "isolated non-LTO size evidence only. No parity module, time API, "
            "tick hook, EDMA product path, package, link or hardware claim."),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true",
        help="verify the tracked receipt instead of rewriting it")
    args = parser.parse_args()
    try:
        value = collect()
        encoded = json.dumps(
            value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
        if args.check:
            require(RECEIPT.is_file(), f"missing receipt: {RECEIPT}")
            require(
                RECEIPT.read_text(encoding="utf-8") == encoded,
                "tracked parity revalidation receipt drift")
        else:
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_text(encoded, encoding="utf-8")
        print(
            "c2-v1.2.4-parity-revalidation: PASS modules=9+1 "
            "document-mutations=10/10 color-native=622+20 "
            "session-shortfall=911 product-delta=0")
        return 0
    except (RevalidationError, ElfTruthError, OSError, UnicodeError,
            json.JSONDecodeError, ValueError) as error:
        print(
            f"c2-v1.2.4-parity-revalidation: FIRST RED: {error}",
            file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
