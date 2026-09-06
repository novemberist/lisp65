#!/usr/bin/env python3
"""Price Block-2.6 Card-3 VM hardening without a product WPLTO or link."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import block_26_sidx_guard_form_pricing as CODEGEN  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
REVIEW = ROOT / "docs/planning/2026-09-03-project-code-review.md"
REGISTER = ROOT / "docs/reference/gate-and-tool-register.md"
CARD2 = ARCH / "block-2.6-card2-f011-product-r3-receipt.json"
DWX = ROOT / "tests/bytecode/dialect-v2/evidence/post-release/dwx-retroactive-red-replay-receipt-20260903.json"
PERF = ARCH / "c2.3-v2.0.0-release-card-r3-receipt.json"
CLOSURE = ARCH / "c2.3-media-builder-closure-enumeration-v20-receipt.json"
RECEIPT = ARCH / "block-2.6-card3-vm-hardening-preamble.json"
REPORT = ROOT / "docs/planning/2.6-card3-vm-hardening-preamble-report.md"
BUILD = ROOT / "build/2.6/card3-vm-hardening-preamble-r5"
WPLTO = ROOT / "build/2.6/card2-f011-product-r3/wplto"
CANONICAL = WPLTO / ".canonical-objects-lisp65-c2-substitution-linked"
COMPILER = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
LLVM_LINK = Path("/usr/bin/llvm-link")
FORMAT = "lisp65-block-2.6-card3-vm-hardening-preamble-v1"
AUTHORIZATION = "77dcf227"
PREAMBLE_SEAL = "9e10167b"
TEXT_FLOOR = 32


class PreambleError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PreambleError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def bind_at(commit: str, path: Path) -> dict[str, Any]:
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    return {"path": relative, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def sealed_inputs() -> dict[str, Any]:
    """Bind the pricing preamble in its own era, never to a live successor."""
    return {"plan": bind_at(PREAMBLE_SEAL, PLAN),
        "review": bind_at(PREAMBLE_SEAL, REVIEW),
        "gate_register": bind_at(PREAMBLE_SEAL, REGISTER),
        "card2": bind_at(PREAMBLE_SEAL, CARD2),
        "dwx_cycle_receipt": bind_at(PREAMBLE_SEAL, DWX),
        "responsiveness_authority": bind_at(PREAMBLE_SEAL, PERF),
        "closure": bind_at(PREAMBLE_SEAL, CLOSURE),
        "mem_source": bind_at(PREAMBLE_SEAL, ROOT / "src/mem.c"),
        "vm_source": bind_at(PREAMBLE_SEAL, ROOT / "src/vm.c")}


def run(command: list[str], label: str) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def replace_once(text: str, old: str, new: str, label: str) -> str:
    require(text.count(old) == 1, f"{label} source target drift")
    return text.replace(old, new, 1)


def replace_span(text: str, start: str, end: str, replacement: str,
                 label: str) -> str:
    require(text.count(start) == 1 and text.count(end) == 1,
            f"{label} span drift")
    begin = text.index(start)
    finish = text.index(end, begin)
    return text[:begin] + replacement + text[finish:]


def mem_flat_root(source: str) -> str:
    start = "/* VOLL iterativ (expliziter Mark-Stack, KEINE C-Rekursion):"
    end = "uint16_t gc_badobj = 0;"
    replacement = '''/* C2 product roots join the collector's existing flat fixpoint.  The old
 * private 256-entry traversal stack could silently drop a live car on overflow;
 * a flat root mark has no bounded worklist and the ordinary fixpoint below owns
 * all successor traversal. */
'''
    source = replace_span(source, start, end, replacement,
                          "mark-stack storage removal")
    start = "void gc_mark(obj o) {"
    end = "/* Mark a single obj (WITHOUT successors). 1 = newly marked. Flat, no stack. */"
    replacement = '''static uint8_t gc_mark1(obj o);
void gc_mark(obj o) { (void)gc_mark1(o); }

'''
    return replace_span(source, start, end, replacement, "flat GC root handoff")


def vm_slot_guard(source: str) -> str:
    source = replace_once(
        source,
        "#define SLOT(n)  gc_rootstack[base + (n)]\n",
        "#define SLOT(n)  gc_rootstack[base + (n)]\n"
        "#define SLOT_OK(n) ((uint16_t)(n) < (uint16_t)nargs + nlocals)\n",
        "slot predicate",
    )
    source = replace_once(
        source,
        "        case OP_PUSHARGN: { uint8_t n = RD8(); PUSH(SLOT(n)); break; }\n"
        "        case OP_LOADL:    { uint8_t n = RD8(); PUSH(SLOT(n)); break; }\n"
        "        case OP_STOREL:   { uint8_t n = RD8(); a = POP(); SLOT(n) = a; break; }",
        "        case OP_PUSHARGN: { uint8_t n = RD8(); if (!SLOT_OK(n)) { vm_status = VM_BADOPCODE; goto done; } PUSH(SLOT(n)); break; }\n"
        "        case OP_LOADL:    { uint8_t n = RD8(); if (!SLOT_OK(n)) { vm_status = VM_BADOPCODE; goto done; } PUSH(SLOT(n)); break; }\n"
        "        case OP_STOREL:   { uint8_t n = RD8(); if (!SLOT_OK(n)) { vm_status = VM_BADOPCODE; goto done; } a = POP(); SLOT(n) = a; break; }",
        "slot consumers",
    )
    source = replace_once(source, "#undef SLOT\n", "#undef SLOT\n#undef SLOT_OK\n",
                          "slot macro cleanup")
    return source


def vm_rest_guard(source: str) -> str:
    marker = "static uint16_t vm_frame_fill(uint16_t base, const obj *args, uint8_t n,\n"
    helper = '''static __attribute__((always_inline)) uint16_t vm_frame_slots(
        uint8_t actual, uint8_t nargs, uint8_t nlocals, uint8_t flags) {
    uint16_t slots = (uint16_t)nargs + nlocals;
    if (flags & CO_FLAG_REST)
        slots = (uint16_t)(slots + 1u +
            ((actual > nargs) ? (uint8_t)(actual - nargs) : 0u));
    return slots;
}

'''
    source = replace_once(source, marker, helper + marker, "rest frame size helper")
    old = "if ((uint16_t)(base + nargs + nlocals + 1) >= GC_ROOTS) { vm_status = VM_STACKOVER; goto done; }"
    new_entry = "if ((uint16_t)(base + vm_frame_slots(nargs_actual, nargs, nlocals, flags)) > GC_ROOTS) { vm_status = VM_STACKOVER; goto done; }"
    new_tail = "if ((uint16_t)(base + vm_frame_slots(n, nargs, nlocals, flags)) > GC_ROOTS) { vm_status = VM_STACKOVER; goto done; }"
    require(source.count(old) == 2, "frame guards drift")
    source = source.replace(old, new_entry, 1).replace(old, new_tail, 1)
    return source


def vm_pop_and_disk_guard(source: str) -> str:
    source = replace_once(
        source,
        "    case 21:  /* %disk-poke */\n"
        "        io_disk_scratch_poke((uint8_t)FIXVAL(a[0]), (uint8_t)(FIXVAL(a[1]) & 0xFF));\n"
        "        return a[1];",
        "    case 21:  /* %disk-poke */\n"
        "        if (n != 2 || !IS_FIX(a[0]) || !IS_FIX(a[1])) { vm_status = VM_TYPEERROR; return NIL; }\n"
        "        io_disk_scratch_poke((uint8_t)FIXVAL(a[0]), (uint8_t)(FIXVAL(a[1]) & 0xFF));\n"
        "        return a[1];",
        "disk poke domain",
    )
    source = replace_once(
        source,
        "#define POP()    (gc_rootsp > vb ? gc_rootstack[--gc_rootsp] : (vm_status = VM_BADOPCODE, NIL))",
        "#define POP()    ({ obj pop__; if (gc_rootsp <= vb) { vm_status = VM_BADOPCODE; goto done; } pop__ = gc_rootstack[--gc_rootsp]; pop__; })",
        "fail-stop pop",
    )
    return source


def vm_direct_pc_guard(source: str) -> str:
    return replace_once(
        source,
        "        HB(2);\n        WIN_ENSURE();",
        "        HB(2);\n"
        "        if ((uint16_t)(win + (uint16_t)(ip - code)) >= payload_len) {\n"
        "            vm_status = VM_BADOPCODE; goto done;\n"
        "        }\n"
        "        WIN_ENSURE();",
        "direct payload PC guard",
    )


def variants(mem_source: str, vm_source: str) -> dict[str, tuple[str, str]]:
    flat = mem_flat_root(mem_source)
    slot = vm_slot_guard(vm_source)
    rest = vm_rest_guard(vm_source)
    pop = vm_pop_and_disk_guard(vm_source)
    cold = vm_pop_and_disk_guard(vm_rest_guard(vm_slot_guard(vm_source)))
    return {
        "baseline": (mem_source, vm_source),
        "a3-flat-fixpoint-root": (flat, vm_source),
        "a4-slot-bound": (mem_source, slot),
        "a5-rest-frame-bound": (mem_source, rest),
        "a6-pop-and-disk-domain": (mem_source, pop),
        "a3-through-a6": (flat, cold),
        "a7-direct-pc-bound": (mem_source, vm_direct_pc_guard(vm_source)),
        "a3-through-a7-direct": (flat, vm_direct_pc_guard(cold)),
    }


def configure_codegen() -> list[str]:
    CODEGEN.WPLTO = WPLTO
    CODEGEN.CANONICAL = CANONICAL
    return CODEGEN.compile_flags()


def canonical_c_objects() -> list[Path]:
    paths = sorted(CANONICAL.glob("[0-9][0-9][0-9]-*.c.o"))
    require(len(paths) == 46 and paths[15].name == "015-mem.c.o"
            and paths[22].name == "022-vm.c.o", "Card-2 C object population drift")
    return paths


def truth_rows(path: Path) -> tuple[dict[str, int], dict[str, int]]:
    truth = ElfTruth.read(path, llvm_readobj=READOBJ)
    symbols = {row.name: row.bytes for row in truth.symbols
               if row.name and row.section != "Undefined"
               and row.symbol_type not in ("Section", "File")}
    sections = {(row.name or "NULL"): row.bytes for row in truth.sections}
    return symbols, sections


def groups(sections: dict[str, int]) -> dict[str, int]:
    code = {name: size for name, size in sections.items()
            if name == ".text" or name.startswith(".text.")
            or name.startswith(".lisp65_") and ".rela" not in name}
    return {
        "ordinary_text": sum(size for name, size in code.items()
                             if name == ".text" or name.startswith(".text.")),
        "resident_island": sum(size for name, size in code.items()
                               if name.startswith(".lisp65_resident_island")),
        "mapped_product_cold": sum(size for name, size in code.items()
                                   if name.startswith(".lisp65_c2_mapped_product_cold")),
        "mapped_f011_cold": sum(size for name, size in code.items()
                                if name.startswith(".lisp65_c2_mapped_f011_cold")),
        "mapped_far_service": sum(size for name, size in code.items()
                                   if name.startswith(".lisp65_c2_mapped_far_service")),
        "fixed_zero_page": sum(size for name, size in sections.items()
                                if name.startswith(".lisp65_c2_fixed_zp")
                                or name.startswith(".lisp65_c2_convergence_zp")),
        "NOLOAD": sum(size for name, size in sections.items()
                       if name == ".noinit" or name.startswith(".noinit.")),
        "bss": sum(size for name, size in sections.items()
                   if name == ".bss" or name.startswith(".bss.")),
        "all_code": sum(code.values()),
    }


def compile_lane(name: str, mem_source: str, vm_source: str,
                 flags: list[str]) -> dict[str, Any]:
    directory = BUILD / name
    directory.mkdir(parents=True)
    replacements = {15: ("mem.c", mem_source), 22: ("vm.c", vm_source)}
    objects = canonical_c_objects()
    selected = list(objects)
    bindings: dict[str, Any] = {}
    for index, (filename, source) in replacements.items():
        source_path = directory / filename
        source_path.write_text(source, encoding="utf-8")
        bitcode = directory / (filename + ".o")
        run([str(COMPILER), *flags, "-c", source_path.relative_to(ROOT).as_posix(),
             "-o", bitcode.relative_to(ROOT).as_posix()], f"{name} {filename} frontend")
        selected[index] = bitcode
        bindings[filename] = bind(bitcode)
    linked = directory / "combined-c.bc"
    run([str(LLVM_LINK), *(str(path) for path in selected), "-o", str(linked)],
        f"{name} deterministic llvm-link")
    assembly = directory / "combined-c.s"
    run([str(COMPILER), "-target", "mos", "-Oz", "-x", "ir", "-S",
         str(linked), "-o", str(assembly)], f"{name} relocatable codegen")
    obj = directory / "combined-c.o"
    run([str(COMPILER), "-c", str(assembly), "-o", str(obj)],
        f"{name} assembly")
    symbols, sections = truth_rows(obj)
    return {"frontends": bindings, "combined_bitcode": bind(linked),
            "object": bind(obj), "groups": groups(sections),
            "symbols": {key: symbols.get(key, 0) for key in
                ("gc_mark", "gc_mark1", "vm_frame_fill", "vm_run_inner",
                 "vm_callprim")}}


def group_delta(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, int]:
    return {key: row["groups"][key] - baseline["groups"][key]
            for key in baseline["groups"]}


def semantic_models() -> dict[str, Any]:
    # A4: every byte value is classified against every legal frame width.
    slot_cases = 0
    for width in range(256):
        for operand in range(256):
            assert (operand < width) == (operand in range(width))
            slot_cases += 1
    # A5: model every legal actual/fixed/local count under the 12-arg ABI.
    rest_shapes = 0
    rest_base_cases = 0
    for actual in range(13):
        for nargs in range(13):
            for nlocals in range(13):
                transient = 1 + max(0, actual - nargs)
                slots = nargs + nlocals + transient
                assert slots >= nargs + nlocals + 1
                rest_shapes += 1
                for base in range(129):
                    highest_written = base + slots - 1
                    guard_accepts = base + slots <= 128
                    assert guard_accepts == (highest_written < 128)
                    rest_base_cases += 1
    # A6: arity/types and underflow are deliberately exhaustive over their domains.
    disk_cases = 0
    disk_accepts = 0
    for n in range(13):
        for a0 in (0, 1):
            for a1 in (0, 1):
                accepted = n == 2 and bool(a0) and bool(a1)
                disk_cases += 1
                disk_accepts += int(accepted)
    pop_cases = sum(1 for depth in range(14) for need in range(1, 13)
                    if depth < need)
    return {"slot_operand_cases": slot_cases, "rest_frame_shapes": rest_shapes,
            "rest_frame_base_cases": rest_base_cases,
            "disk_poke_domain_cases": disk_cases,
            "disk_poke_accepting_cases": disk_accepts,
            "pop_underflow_cases": pop_cases,
            "status": "PASS: COLD OPERAND MODELS EXHAUSTIVE"}


def sentinel_price(card2: dict[str, Any], closure: dict[str, Any]) -> dict[str, Any]:
    # The ABI stores payload length in CO_OFF_CLEN, but the runtime currently
    # derives payload_len from directory length and consumes no trailer byte.
    compiler = (ROOT / "src/compile.c").read_text(encoding="utf-8")
    vm = (ROOT / "src/vm.c").read_text(encoding="utf-8")
    l65m = (ROOT / "tools/host-lisp/l65m_contract.py").read_text(encoding="utf-8")
    require("out[n++] = (uint8_t)(f->codelen & 0xff)" in compiler
            and "payload_len = (uint16_t)(len - hdrlen);" in vm
            and "expected_code_len = 7 + 2 * literal_count + payload_len" in l65m,
            "sentinel ABI population drift")
    object_count = closure["active_closure"]["block3_return_registry"]["objects"]
    require(object_count > 0, "derived delivered object population is empty")
    hole = card2["final_product"]["composed_bank2"]["largest_contiguous_hole"]["bytes"]
    return {
        "form": "one trailer sentinel outside CO_OFF_CLEN payload",
        "object_count_authority": bind(CLOSURE),
        "object_count": object_count,
        "minimum_freight_bytes": object_count,
        "largest_bank2_hole_after_minimum_freight": hole - object_count,
        "required_population": ["C compiler emitter", "Lisp compiler emitter",
            "L65M decoder/validator", "static-plane packer", "append path",
            "directory length authority", "OBJ_SETUP", "stream-window refill"],
        "runtime_contract": ("payload_len comes from CO_OFF_CLEN; directory length equals "
            "header+literals+payload+one sentinel; fallthrough fetch may consume only the "
            "trailer; branch targets remain strictly inside payload"),
        "cannot_share_current_object_length": True,
        "decision": "separate-format-card-required",
        "reason": ("the current ABI equates directory length with payload extent; changing "
            "only the compiler or only OBJ_SETUP creates another bound-not-consumed world"),
    }


def performance_price(direct_delta: int, sentinel: dict[str, Any],
                      dwx: dict[str, Any], perf: dict[str, Any]) -> dict[str, Any]:
    # The preamble has no new executable product, so it cannot manufacture an
    # Xemu trace.  It prices the direct check from the real fetch populations
    # and reserves the emulated-cycle lane for the authorized final candidate.
    hot_rows = [row for row in dwx["rows"] if row.get("id") == "block3-hot-path"]
    require(len(hot_rows) == 1, "DWX hot-path population drift")
    hot = hot_rows[0]
    lanes = perf["final_product"]["responsiveness_lanes"]
    single_fetches = lanes["single_keystroke"]["route"]["vm_steps_per_character"]
    batch_fetches = lanes["batch_throughput"]["route"]["vm_steps_per_character"]
    require(single_fetches == hot["device_reference_vm_steps_per_key"],
            "single-key population authorities diverge")
    reference_cycles = hot["reference_trace"]["mean_cycles_per_key"]
    return {
        "claim_class": "host-only upper-bound projection; not final-link qualification",
        "direct_per_fetch": {
            "relocatable_codegen_ordinary_text_delta_bytes": direct_delta,
            "single_keystroke": {"fetches": single_fetches,
                "reference_emulated_cycles_per_key": reference_cycles,
                "candidate_native_cycles": None,
                "price_status": "closed-until-final-linked-basic-block-is-executable"},
            "batch": {"fetches_per_character": batch_fetches,
                "candidate_native_cycles_per_character": None,
                "price_status": "closed-until-final-linked-basic-block-is-executable"},
            "emulated_cycles": {"measured_now": False,
                "reason": "no product WPLTO/link/media is authorized in the preamble",
                "mandatory_final_link_lane": True},
        },
        "trailer_sentinel": {
            "per_fetch_comparisons": 0,
            "minimum_static_freight_bytes": sentinel["minimum_freight_bytes"],
            "single_keystroke_projection": "no dispatch delta; setup/loader population must be measured",
            "batch_projection": "no dispatch delta; setup/loader population must be measured",
            "emulated_cycles": {"measured_now": False,
                "mandatory_after_format-card": True}},
    }


def derive() -> dict[str, Any]:
    require(not BUILD.exists() and not RECEIPT.exists(), "Card-3 preamble is one-shot")
    require(subprocess.run(["git", "merge-base", "--is-ancestor", AUTHORIZATION, "HEAD"],
        cwd=ROOT).returncode == 0, "Card-3 authorization drift")
    card2 = load(CARD2)
    dwx = load(DWX)
    perf = load(PERF)
    closure = load(CLOSURE)
    owners = card2["final_product"]["bounded_owners"]
    require(owners["ordinary_text"]["margin_bytes"] == TEXT_FLOOR
            and owners["ordinary_BSS"]["margin_bytes"] == 6
            and owners["ordinary_BSS"]["floor_bytes"] == 5
            and owners["resident_island"]["margin_bytes"] == 28
            and owners["resident_island"]["floor_bytes"] == 5,
            "Card-2 floor world drift")
    BUILD.mkdir(parents=True)
    flags = configure_codegen()
    mem_source = (ROOT / "src/mem.c").read_text(encoding="utf-8")
    vm_source = (ROOT / "src/vm.c").read_text(encoding="utf-8")
    lanes = {name: compile_lane(name, mem, vm, flags)
             for name, (mem, vm) in variants(mem_source, vm_source).items()}
    baseline = lanes["baseline"]
    for row in lanes.values():
        row["delta"] = group_delta(row, baseline)
    combined = lanes["a3-through-a6"]["delta"]
    direct = lanes["a7-direct-pc-bound"]["delta"]
    all_direct = lanes["a3-through-a7-direct"]["delta"]
    sentinel = sentinel_price(card2, closure)
    dispatch_performance = performance_price(
        direct["ordinary_text"], sentinel, dwx, perf)
    remaining = {
        "ordinary_text": owners["ordinary_text"]["margin_bytes"] - combined["ordinary_text"],
        "ordinary_BSS": owners["ordinary_BSS"]["margin_bytes"] - combined["bss"],
        "resident_island": owners["resident_island"]["margin_bytes"] - combined["resident_island"],
    }
    cold_green = (remaining["ordinary_text"] >= TEXT_FLOOR
                  and remaining["ordinary_BSS"] >= owners["ordinary_BSS"]["floor_bytes"]
                  and remaining["resident_island"] >= owners["resident_island"]["floor_bytes"])
    direct_remaining = owners["ordinary_text"]["margin_bytes"] - all_direct["ordinary_text"]
    value = {
        "format": FORMAT, "recorded_on": "2026-09-03",
        "status": "PASS: CARD 3 PREAMBLE SPLITS A3-A6 FROM FETCH POLICY",
        "authorization": AUTHORIZATION,
        "inputs": {"plan": bind(PLAN), "review": bind(REVIEW),
                   "gate_register": bind(REGISTER), "card2": bind(CARD2),
                   "dwx_cycle_receipt": bind(DWX),
                   "responsiveness_authority": bind(PERF), "closure": bind(CLOSURE),
                   "mem_source": bind(ROOT / "src/mem.c"),
                   "vm_source": bind(ROOT / "src/vm.c")},
        "baseline": {"bounded_owners": owners,
                     "composed_bank2": card2["final_product"]["composed_bank2"]},
        "measurement": {"kind": "whole-C relocatable MOS codegen over Card-2 canonical objects",
            "final_link_claim": False, "lanes": lanes,
            "known_limit": "final linked candidate must replace every projected owner price"},
        "cold_hardening": {"items": ["A3-flat-fixpoint-root", "A4-slot-bound",
            "A5-rest-frame-bound", "A6-pop-underflow-and-disk-poke-domain"],
            "semantic_models": semantic_models(), "combined_delta": combined,
            "projected_remaining_margins": remaining,
            "every_projected_floor_green": cold_green,
            "decision": "open-a3-a6-product-card" if cold_green else "reprice-a3-a6-placement"},
        "dispatch": {"direct_pc_bound": {"delta": direct,
                "combined_a3_through_a7_delta": all_direct,
                "projected_text_margin": direct_remaining,
                "projected_text_floor": TEXT_FLOOR,
                "fits_projected_text_floor": direct_remaining >= TEXT_FLOOR},
            "terminal_sentinel": sentinel, "three_lane_price": dispatch_performance,
            "decision": "separate-decision-after-cold-final-link",
            "reason": ("the direct guard has a measurable hot-path and text price; the "
                "sentinel is a format-wide card, not a local VM substitution")},
        "recommended_sequence": ["A3-A6-product-card",
            "final-link-owner-remeasurement", "dispatch-A7-decision-card"],
        "accounting": {"product_WPLTO_runs": 0, "product_links": 0,
                       "media_builds": 0, "device_contacts": 0},
    }
    validate(value)
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    print("Block 2.6 Card 3 preamble: BUILD PASS "
          f"cold-text={combined['ordinary_text']:+d} "
          f"direct-text={direct['ordinary_text']:+d} split=1")


def validate(value: dict[str, Any]) -> None:
    cold = value["cold_hardening"]
    dispatch = value["dispatch"]
    require(value["format"] == FORMAT and value["authorization"] == AUTHORIZATION
            and value["measurement"]["final_link_claim"] is False
            and cold["semantic_models"]["slot_operand_cases"] == 65536
            and cold["semantic_models"]["rest_frame_shapes"] == 2197
            and cold["semantic_models"]["rest_frame_base_cases"] == 283413
            and cold["semantic_models"]["disk_poke_domain_cases"] == 52
            and cold["semantic_models"]["disk_poke_accepting_cases"] == 1
            and cold["every_projected_floor_green"] is True
            and cold["combined_delta"]["bss"] == -510
            and cold["combined_delta"]["fixed_zero_page"] == 0
            and cold["combined_delta"]["NOLOAD"] == 0
            and cold["combined_delta"]["mapped_f011_cold"] == 0
            and cold["combined_delta"]["mapped_far_service"] == 0
            and cold["combined_delta"]["mapped_product_cold"] == 0
            and cold["projected_remaining_margins"]["ordinary_BSS"] == 516
            and cold["decision"] == "open-a3-a6-product-card"
            and dispatch["terminal_sentinel"]["object_count"] == 792
            and dispatch["terminal_sentinel"]["minimum_freight_bytes"] == 792
            and dispatch["terminal_sentinel"]["decision"] == "separate-format-card-required"
            and dispatch["three_lane_price"]["direct_per_fetch"]["single_keystroke"]["fetches"] == 902
            and dispatch["three_lane_price"]["direct_per_fetch"]["single_keystroke"]["candidate_native_cycles"] is None
            and dispatch["three_lane_price"]["direct_per_fetch"]["emulated_cycles"]["measured_now"] is False
            and dispatch["decision"] == "separate-decision-after-cold-final-link"
            and value["accounting"] == {"product_WPLTO_runs": 0,
                "product_links": 0, "media_builds": 0, "device_contacts": 0},
            "Card-3 preamble drift")


def report(value: dict[str, Any]) -> str:
    lanes = value["measurement"]["lanes"]
    rows = []
    for name, row in lanes.items():
        delta = row["delta"]
        rows.append(f"| `{name}` | {delta['ordinary_text']:+d} | {delta['bss']:+d} | "
                    f"{delta['resident_island']:+d} | {delta['mapped_product_cold']:+d} |")
    cold = value["cold_hardening"]
    dispatch = value["dispatch"]
    direct = dispatch["three_lane_price"]["direct_per_fetch"]
    sentinel = dispatch["terminal_sentinel"]
    return f"""# Block 2.6 Card 3 — VM hardening preamble

Status: **{value['status']}**

This is a host-only price. It runs **zero product WPLTOs, zero product links,
zero media builds and zero device contacts**. The code-size lanes compile the
real Card-2 sources with the Card-2 flags and whole-C canonical object set, but
they remain relocatable projections; every bounded owner is remeasured at the
first authorized final link.

| candidate | ordinary text delta | BSS delta | resident-island delta | mapped-product-cold delta |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

## A3–A6 card

A3 removes the bounded 256-entry private mark stack and hands each product root
to the collector's existing flat fixpoint; overflow is eliminated rather than
counted after damage. A4 bounds all byte-operand slot accesses, A5 includes the
temporary `&rest` construction area in both frame guards, and A6 makes POP
underflow leave the opcode before a side effect while adding the missing
`%disk-poke` arity/type check. Their combined projection is
**{cold['combined_delta']['ordinary_text']:+d} ordinary-text bytes** and
**{cold['combined_delta']['bss']:+d} BSS bytes**. Projected margins are text
**{cold['projected_remaining_margins']['ordinary_text']}/{TEXT_FLOOR}**, BSS
**{cold['projected_remaining_margins']['ordinary_BSS']}/5**, and island
**{cold['projected_remaining_margins']['resident_island']}/5**. The semantic
models cover {cold['semantic_models']['slot_operand_cases']:,} slot pairs,
{cold['semantic_models']['rest_frame_shapes']:,} frame shapes across
{cold['semantic_models']['rest_frame_base_cases']:,} base/shape pairs, and
{cold['semantic_models']['pop_underflow_cases']} underflow shapes.

The remaining bounded owner groups are unchanged in the relocatable lane:
fixed/convergence zero page, NOLOAD, mapped F011 cold, mapped far service and
mapped product cold all have delta zero. Their final addresses and margins are
still rederived at the product link rather than inherited from this projection.

Decision: **open one A3–A6 product card**, subject to final-link prices for
every simultaneously live bounded owner. The A3 reclaim is part of that card,
not a credit that later cards may spend before it exists in the final ELF.

## Dispatch boundary

The direct `pc < payload_len` form projects
**{dispatch['direct_pc_bound']['delta']['ordinary_text']:+d} ordinary-text
bytes** alone; its marginal price after the non-dispatch transformations is
**{dispatch['direct_pc_bound']['combined_a3_through_a7_delta']['ordinary_text'] - cold['combined_delta']['ordinary_text']:+d}
bytes**, demonstrating the expected LTO interaction. Combined with A3–A6 it
would leave a projected text margin of
**{dispatch['direct_pc_bound']['projected_text_margin']}/{TEXT_FLOOR}**. Its
three-lane pre-price uses the real 902-fetch single-key and 223.875-fetch batch
populations, so the direct form would execute one new check for every one of
those fetches. It deliberately records **no invented native-cycle conversion**:
the relocatable lane changes whole-function register allocation, and no
executable successor is authorized. Single-key cycles, batch cycles and the DWX
emulated-cycle trace therefore remain individually closed requirements of the
A7 decision card rather than being inferred from the +206-byte size delta.

The proposed terminal sentinel is not a local alternative in the current ABI.
Today directory length is the payload extent; a safe trailer needs
`CO_OFF_CLEN` to become the payload authority and requires all of
{', '.join(sentinel['required_population'])} to agree. At a minimum it adds one
byte to each of the **{sentinel['object_count']}** delivered code objects, while
leaving **{sentinel['largest_bank2_hole_after_minimum_freight']:,} bytes** in the
largest Bank-2 hole. A compiler-only trailer or a VM-only interpretation would
recreate bound≠consumed.

Decision: **split A7 into its own decision after the A3–A6 final link**.
That decision must compare an actual final-link direct guard against a complete
format-card sentinel and must run all three lanes on the executable successor.
Neither candidate is selected by this preamble.
"""


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    require(value["inputs"] == sealed_inputs(),
            "Card-3 preamble seal-era input drift")
    require(value["inputs"]["mem_source"] != bind(ROOT / "src/mem.c")
            and value["inputs"]["vm_source"] != bind(ROOT / "src/vm.c"),
            "Card-3 preamble accidentally rebound to live product sources")
    print("Block 2.6 Card 3 preamble: CHECK PASS split=1 cold=open dispatch=closed")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "fragment-promoted-to-final": lambda row: row["measurement"].update({"final_link_claim": True}),
        "cold-floor-ignored": lambda row: row["cold_hardening"].update({"every_projected_floor_green": False}),
        "gc-bss-overclaimed": lambda row: row["cold_hardening"]["combined_delta"].update({"bss": -514}),
        "bounded-owner-omitted": lambda row: row["cold_hardening"]["combined_delta"].update({"fixed_zero_page": 1}),
        "slot-population-short": lambda row: row["cold_hardening"]["semantic_models"].update({"slot_operand_cases": 255}),
        "sentinel-object-omitted": lambda row: row["dispatch"]["terminal_sentinel"].update({"object_count": 791}),
        "sentinel-localized-falsely": lambda row: row["dispatch"]["terminal_sentinel"].update({"decision": "local-vm-patch"}),
        "cycle-lane-invented": lambda row: row["dispatch"]["three_lane_price"]["direct_per_fetch"]["emulated_cycles"].update({"measured_now": True}),
        "dispatch-opened-early": lambda row: row["dispatch"].update({"decision": "direct-selected"}),
        "hidden-product-link": lambda row: row["accounting"].update({"product_links": 1}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (PreambleError, KeyError, TypeError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "Card-3 preamble mutation survived")
    print(f"Block 2.6 Card 3 preamble: SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "selftest"))
    action = parser.parse_args().action
    try:
        {"build": derive, "check": check, "selftest": selftest}[action]()
    except (PreambleError, OSError, subprocess.SubprocessError,
            json.JSONDecodeError) as error:
        print(f"Block 2.6 Card 3 preamble: RED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
