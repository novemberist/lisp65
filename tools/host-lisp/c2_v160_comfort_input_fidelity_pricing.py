#!/usr/bin/env python3
"""Price a lossless Comfort input boundary without changing the product."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0_compiler as P0  # noqa: E402
import evidence_era as ERA  # noqa: E402
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


CONTRACT = ROOT / "config/c2-v160-comfort-input-fidelity-pricing-contract.json"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-comfort-repl-input-fidelity-device-first-red-receipt.json"
)
QUEUE = ROOT / "config/c2-cross-invariant-c2.2-open-addenda.json"
GC_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.2-g2-gc-work-attribution-receipt.json"
)
GEOMETRY = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.1-wysiwyg-text-recovery-artifact-replay-receipt.json"
)
EDITOR = ROOT / "lib/stdlib-read-line.lisp"
COMFORT = ROOT / "lib/repl-comfort.lisp"
REPL_C = ROOT / "src/repl.c"
VM_C = ROOT / "src/vm.c"
INTERRUPT_C = ROOT / "src/interrupt.c"
WINDOW_S = ROOT / "src/c2_kernal_window.s"
PROFILE = ROOT / "config/workbench.mk"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-comfort-input-fidelity-pricing-receipt.json"
)
FORMAT = "lisp65-c2-v160-comfort-input-fidelity-pricing-receipt-v1"
PRICING_SOURCE_COMMIT = "c4a78738"


class PricingError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PricingError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def write(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


CAPTURE_ASM = r"""
    .equ RING_HEAD, $ff8c
    .equ RING_TAIL, $ff8d
    .equ RING_BASE, $bc90
    .equ RING_SLOTS, 112

    .section .capture.wrapper,"ax",@progbits
    .globl priced_irq_wrapper
    .globl c2_kernal_irq_after_save
    .globl priced_capture_drain
priced_irq_wrapper:
    pha
    phx
    phy
    phz
    lda $d019
    and #$01
    beq .Lresume
    jsr priced_capture_drain
.Lresume:
    jmp c2_kernal_irq_after_save

    .section .capture.driver,"ax",@progbits
priced_capture_drain:
    lda RING_TAIL
    bmi .Ldone
.Lagain:
    lda $d60a
    bpl .Ldone
    lda $d619
    cmp #$03
    beq .Ldiscard
    ldx RING_HEAD
    inx
    cpx #RING_SLOTS
    bne .Lnext
    ldx #$00
.Lnext:
    cpx RING_TAIL
    beq .Ldone
    ldy RING_HEAD
    sta RING_BASE,y
    sta $d619
    stx RING_HEAD
    bra .Lagain
.Ldiscard:
    sta $d619
    bra .Lagain
.Ldone:
    rts

    .section .capture.error_cleanup,"ax",@progbits
priced_capture_error_cleanup:
    lda #$ff
    sta RING_TAIL
"""


def assemble_price() -> dict[str, int]:
    compiler = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
    require(compiler.is_file(), "llvm-mos MEGA65 compiler absent")
    with tempfile.TemporaryDirectory(prefix="c2-v160-input-price-") as name:
        source = Path(name) / "capture.s"
        obj = Path(name) / "capture.o"
        source.write_text(CAPTURE_ASM, encoding="utf-8")
        completed = subprocess.run(
            [str(compiler), "-c", str(source), "-o", str(obj)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        require(completed.returncode == 0,
                f"target capture assembly failed: {completed.stderr}")
        truth = ElfTruth.read(
            obj, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    sizes: dict[str, int] = {}
    for section, key in [
        (".capture.wrapper", "irq_wrapper"),
        (".capture.driver", "queue_drain"),
        (".capture.error_cleanup", "native_error_cleanup"),
    ]:
        try:
            sizes[key] = truth.section(section).bytes
        except ElfTruthError as error:
            raise PricingError(f"assembled section absent: {section}") from error
    require(sizes == {
        "irq_wrapper": 17,
        "queue_drain": 52,
        "native_error_cleanup": 5,
    }, f"target capture price drift: {sizes}")
    return sizes


def defuns(path: Path) -> list[Any]:
    relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    source = ERA.era_blob(PRICING_SOURCE_COMMIT, relative).decode("utf-8")
    return [form for form in P0.parse_all(source)
            if isinstance(form, list) and len(form) > 1 and form[0] == "defun"]


def compile_sizes(forms: list[Any]) -> dict[str, int]:
    heap = P0.prepare_heap([form[1] for form in forms])
    result: dict[str, int] = {}
    for form in forms:
        name, code, helpers = P0.compile_top_form_with_helpers(
            form, heap, strict_arity=True, abi_profile="dialect-v2",
            prebuilt_primitives=True,
        )
        require(not helpers, f"pricing shape introduced helper: {name}")
        result[name] = len(code.encode())
    return result


def hybrid_bytecode_price() -> dict[str, Any]:
    editor = defuns(EDITOR)
    comfort = defuns(COMFORT)
    forms = [copy.deepcopy(form) for form in editor + comfort]
    by_name = {form[1]: form for form in forms}
    baseline = compile_sizes(forms)

    render = by_name["%rl-render"]
    old_render = render[3]
    raw_again = ["%rl-render", "nil", 0, 0, 0, 0, -1]
    raw_poll = [
        "if", [">", ["peek", 255, 138], 0],
        ["progn", ["key-event", 0], raw_again],
        ["let*", [
            ["head", ["peek", 255, 140]],
            ["tail", ["peek", 255, 141]],
        ], ["if", ["=", "head", "tail"], raw_again,
            ["let*", [
                ["code", ["peek", 188, ["+", 144, "tail"]]],
                ["next", ["if", ["=", "tail", 111], 0,
                          ["+", "tail", 1]]],
            ], ["progn", ["poke", 255, 141, "next"],
                ["if", ["=", "code", 160], 32, "code"]]]]],
    ]
    render[3] = ["if", ["<", "row", 0], raw_poll, old_render]

    loop = by_name["%read-line-loop"]
    bindings = loop[3][1]
    bindings[0][1] = ["if", ["nthcdr", 8, "state"], raw_again,
                      ["key-event", 1]]
    bindings[1][1] = ["if", ["numberp", "event"], "event",
                      ["cadr", "event"]]

    repl = by_name["repl"]
    conditional = repl[3]
    eval_let = conditional[1][1]
    for binding in eval_let[1]:
        if binding[0] == "result":
            binding[1] = ["progn", ["poke", 255, 141, 255], binding[1]]
    eval_let[2:2] = [["poke", 255, 140, 0], ["poke", 255, 141, 0]]
    top = conditional[2]
    top[1] = [
        "let*", [["answer", ["progn", ["poke", 255, 140, 0],
                                         ["poke", 255, 141, 0], top[1]]]],
        ["poke", 255, 141, 255], "answer",
    ]

    candidate = compile_sizes(forms)
    selected = ["%rl-render", "%read-line-loop", "repl"]
    require(
        {name: baseline[name] for name in selected}
            == {"%rl-render": 91, "%read-line-loop": 202, "repl": 118}
        and {name: candidate[name] for name in selected}
            == {"%rl-render": 236, "%read-line-loop": 237, "repl": 189},
        "target bytecode pricing shape drift",
    )
    require(all(candidate[name] <= 255 for name in selected),
            "hybrid pricing shape exceeds code-object ceiling")
    deltas = {name: candidate[name] - baseline[name] for name in selected}
    return {
        "baseline_bytes": {name: baseline[name] for name in selected},
        "candidate_bytes": {name: candidate[name] for name in selected},
        "delta_bytes": deltas,
        "total_delta_bytes": sum(deltas.values()),
        "maximum_object_bytes": max(candidate[name] for name in selected),
        "object_ceiling_bytes": 255,
        "new_names": 0,
        "new_primitives": 0,
    }


def simulate_capture(queue_depth: int, pause: int, rate: int,
                     slots: int) -> dict[str, Any]:
    hardware = list(range(queue_depth))
    ring: list[int] = []
    dropped: list[int] = []
    next_event = queue_depth
    for _ in range(pause):
        while hardware and len(ring) < slots - 1:
            ring.append(hardware.pop(0))
        for _ in range(rate):
            if len(hardware) < queue_depth:
                hardware.append(next_event)
            else:
                dropped.append(next_event)
            next_event += 1
    while hardware and len(ring) < slots - 1:
        ring.append(hardware.pop(0))
    expected = list(range(queue_depth + pause * rate))
    return {
        "events_produced": len(expected),
        "events_captured": len(ring),
        "dropped": len(dropped),
        "ordered": ring == expected,
        "sixth_event_present": 5 in ring,
        "maximum_ring_occupancy": len(ring),
    }


def derive(contract: dict[str, Any]) -> dict[str, Any]:
    require(
        contract.get("format")
            == "lisp65-c2-v160-comfort-input-fidelity-pricing-v1"
        and contract.get("status") == "owner-commissioned-host-only-pricing"
        and contract.get("authority_commit") == "89369d50",
        "pricing authority drift",
    )
    authority_raw = ERA.era_blob(
        contract["authority_commit"],
        "docs/planning/v1.6.0-freight-work-plan.md",
    )
    authority = ERA.era_bind(
        contract["authority_commit"],
        "docs/planning/v1.6.0-freight-work-plan.md",
    )
    authority_text = authority_raw.decode("utf-8")
    for token in ["Device first red accepted", "Lossless capture path",
                  "Allocation-free event/editor path", "Hybrid pricing"]:
        require(token in authority_text, f"owner pricing token absent: {token}")

    first_red = load(FIRST_RED)
    queue = load(QUEUE)["D3"]["queue_fact"]
    gc = load(GC_RECEIPT)
    geometry = load(GEOMETRY)
    loss = contract["loss_model"]
    shape = contract["capture_shape"]
    walls = contract["walls"]
    candidate_geometry = contract["candidate_geometry"]
    require(candidate_geometry == {
        "ordinary_text_free_bytes": 11,
        "c2_window_gap_bytes": 606,
        "fixed_state_section_bytes": 16,
        "fixed_state_first_unowned_address": "0xff8c",
        "native_repl_buffer_address": "0xbc89",
        "native_repl_buffer_bytes": 192,
        "canonical_activation_bytes_including_nul": 7,
    }, "candidate geometry contract drift")
    require(shape == {
        "ring_base": "0xbc90",
        "ring_storage_bytes": 112,
        "ring_index_values": 112,
        "usable_events": 111,
        "head_address": "0xff8c",
        "tail_address": "0xff8d",
        "disabled_tail": 255,
        "event_representation": "one raw PETSCII code byte; modifiers are intentionally absent because the Comfort editor consumes only code",
        "producer": "owned raster IRQ drains every available ordinary hardware event before returning",
        "consumer": "Comfort-only raw scalar poll through existing peek/poke primitives",
        "lifetime": "enabled only while Comfort is collecting input; disabled before evaluation, on normal exit, and in native error recovery",
    }, "capture shape contract drift")
    require(
        first_red["functional_result"]["rows_passed"] == 10
        and first_red["functional_result"]["rows_total"] == 10
        and first_red["owner_observation"]["classification"]
            == "release-relevant ordinary-input loss"
        and queue["total_events"] == loss["hardware_queue_events"] == 5
        and "sixth event is not enqueued" in queue["overflow_behavior"]
        and gc["target_binding"]["target_phase_frames"]
            ["whole_collection_authority"]
            == loss["worst_collection_frames"] == 89,
        "first-red/queue/GC authority drift",
    )
    ordinary = geometry["producer_tail"]["v21_text_recovery"]["ordinary"]
    require(
        ordinary["reserve_bytes"]
            == candidate_geometry["ordinary_text_free_bytes"] == 11
        and ordinary["text_end_exclusive"] == "0xb3a5",
        "candidate ordinary geometry drift",
    )

    def era_text(path: Path) -> str:
        relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
        return ERA.era_blob(PRICING_SOURCE_COMMIT, relative).decode("utf-8")

    profile = era_text(PROFILE)
    repl_c = era_text(REPL_C)
    vm_c = era_text(VM_C)
    interrupt_c = era_text(INTERRUPT_C)
    window_s = era_text(WINDOW_S)
    editor = era_text(EDITOR)
    require("-DREPL_BUF_MAX=192" in profile
            and "-DLISP65_REPL_HISTORY_IN_BUF" in profile
            and "static char buf[BUF_MAX]" in repl_c,
            "native REPL buffer/lifetime authority drift")
    require(window_s.count(".space 16, 0") == 1
            and "$ff8c" not in window_s.lower()
            and "$ff8d" not in window_s.lower(),
            "two fixed-state bytes are no longer unowned")
    require("while (c2_kernal_event_poll(&event))" in interrupt_c
            and "keystrokes typed while computation is running" in interrupt_c,
            "evaluation-time input discard contract drift")
    key_body = vm_c[vm_c.index("static obj vm_key_event"):
                    vm_c.index("#endif", vm_c.index("static obj vm_key_event"))]
    require(key_body.count("e = cons(") == 3
            and "(inserted (cons code (cdr cursor)))" in editor,
            "whole hot-path allocation count drift")
    require(walls == {
        "device_contacts": 0,
        "product_links": 0,
        "product_source_changes": 0,
        "do_not_lower_input_rate": True,
        "do_not_shorten_collection_envelope": True,
        "public_key_event_abi_unchanged": True,
        "native_repl_fallback_unchanged": True,
        "wysiwyg_a0_to_space_preserved": True,
        "run_stop_abort_preserved": True,
        "resident_cost_requires_owner_decision": True,
    }, "pricing walls weakened")

    required = (loss["hardware_queue_events"]
                + loss["worst_collection_frames"]
                * loss["physical_input_contract_events_per_frame"])
    usable = shape["ring_index_values"] - 1
    require(required == loss["required_capture_events"] == 94
            and shape["ring_storage_bytes"] == shape["ring_index_values"] == 112
            and usable == shape["usable_events"] == 111,
            "loss/ring arithmetic drift")
    simulation = simulate_capture(5, 89, 1, 112)
    require(simulation == {
        "events_produced": 94,
        "events_captured": 94,
        "dropped": 0,
        "ordered": True,
        "sixth_event_present": True,
        "maximum_ring_occupancy": 94,
    }, f"forced-collection capture failed: {simulation}")

    target = assemble_price()
    bytecode = hybrid_bytecode_price()
    capture_code = target["irq_wrapper"] + target["queue_drain"]
    total_resident = capture_code + target["native_error_cleanup"]
    require(capture_code == 69 and total_resident == 74
            and target["native_error_cleanup"] <= candidate_geometry["ordinary_text_free_bytes"]
            and capture_code <= candidate_geometry["c2_window_gap_bytes"],
            "hybrid resident placement does not fit")

    current_cells = first_red["attribution"]["comfort_printable_path"]
    require(current_cells["key_event_cells"] == 3
            and current_cells["editor_cells"] == 1
            and current_cells["total_cells"] == 4
            and current_cells["nursery_cells"] == 192,
            "first-red allocation price drift")
    one_byte_tuple_capacity = usable
    two_byte_tuple_capacity = candidate_geometry["native_repl_buffer_bytes"] // 2 - 1
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-18",
        "status": "PRICED: HYBRID WINS; OWNER RESIDENT-BYTE DECISION REQUIRED",
        "authority": {
            "owner": {
                "authority": "git-blob",
                "commit": contract["authority_commit"],
                "path": authority["path"],
                "bytes": authority["bytes"],
                "sha256": authority["sha256"],
            },
            "contract": bind(CONTRACT),
            "first_red": bind(FIRST_RED),
            "queue": bind(QUEUE),
            "whole_collection": bind(GC_RECEIPT),
            "candidate_geometry": bind(GEOMETRY),
            "sources": [
                ERA.era_bind(
                    PRICING_SOURCE_COMMIT,
                    path.resolve().relative_to(ROOT.resolve()).as_posix(),
                )
                for path in
                [EDITOR, COMFORT, REPL_C, VM_C, INTERRUPT_C, WINDOW_S, PROFILE]
            ],
        },
        "loss_model": {
            "hardware_queue_events": 5,
            "worst_collection_frames": 89,
            "physical_input_contract_events_per_frame": 1,
            "required_capture_events": required,
            "ring_physical_slots": 112,
            "ring_usable_events": usable,
            "margin_events": usable - required,
            "simulation": simulation,
            "why_event_six_survives": "the owned raster IRQ drains the full hardware queue into the independent raw ring while Lisp and GC are stopped; event six therefore occupies the ring instead of meeting a full five-event hardware queue",
        },
        "prices": {
            "capture_only_full_event_tuples": {
                "status": "REJECTED IN REUSED STORAGE",
                "bytes_per_event": 2,
                "maximum_usable_events_in_full_185_byte_tail": two_byte_tuple_capacity,
                "required_events": required,
                "deficit_events": required - two_byte_tuple_capacity,
                "reason": "preserving code plus modifiers does not fit the reusable native-buffer tail; new state would be required",
            },
            "synchronous_fully_allocation_free": {
                "status": "REJECTED BY THE COMMON ACCEPTANCE TEST",
                "heap_cells_per_key": 0,
                "capture_events": 5,
                "required_events_during_forced_collection": required,
                "reason": "removing key allocations prevents periodic GC but cannot preserve a key arriving during the explicitly forced 89-frame collection; event six still meets the five-event hardware queue",
            },
            "hybrid_raw_capture_plus_one_cell_editor": {
                "status": "SELECTED FOR OWNER DISPOSITION",
                "event_representation": "one code byte",
                "target_code_bytes": {
                    **target,
                    "c2_window_capture_total": capture_code,
                    "all_new_resident_code": total_resident,
                },
                "state": {
                    "new_emitted_bytes": 0,
                    "newly_owned_fixed_state_bytes": 2,
                    "fixed_state_addresses": ["0xff8c", "0xff8d"],
                    "lifetime_reused_bank0_bss_bytes": 112,
                    "bank0_ring_range": ["0xbc90", "0xbcff"],
                    "native_history_prefix_preserved_bytes": 7,
                },
                "placement_after": {
                    "ordinary_text_free_bytes": 6,
                    "c2_window_gap_bytes": 537,
                },
                "bank2_bytecode": bytecode,
                "heap_cells_per_printable": 1,
                "maximum_printables_between_hot_path_collections": 192,
                "improvement_over_current": "four to one heap cells per printable; collection interval rises from at most 48 to at most 192 printables, while the ring preserves input during the collection",
                "public_key_event_changed": False,
                "new_public_symbols": 0,
                "new_private_symbols": 0,
                "new_native_primitives": 0,
            },
            "hybrid_capture_plus_preallocated_editor": {
                "status": "NOT SELECTED",
                "reason": "it pays the same mandatory asynchronous capture and adds a non-local editor/storage refactor; current %rl-cut and %rl-put are 253-byte objects, %repl-read is 249 bytes, and measured symbol margin is zero. It provides no additional losslessness after the ring is present.",
            },
        },
        "selected": {
            "name": "raw IRQ capture plus scalar Comfort consumption and existing one-cell insertion",
            "resident_promise": "BROKEN: +74 emitted resident code bytes even though no new state section bytes are emitted",
            "owner_decision": "authorize or reject +69 mapped C2-window code bytes, +5 ordinary Bank-0 code bytes, ownership of two reserved fixed-state bytes, and exclusive Comfort-time reuse of 112 existing Bank-0 REPL-buffer bytes",
            "implementation_not_authorized": True,
        },
        "permanent_acceptance": {
            "forced_collection_frames": 89,
            "input_rate_events_per_frame": 1,
            "initial_hardware_events": 5,
            "expected_ordered_events": 94,
            "expected_dropped_events": 0,
            "must_observe_event_six": True,
            "must_disable_before_eval_and_on_every_exit": True,
            "must_preserve_a0_to_space_and_matrix_run_stop": True,
        },
        "mutations_rejected": [
            "queue-depth-six", "omit-three-key-event-cells",
            "accept-synchronous-zero-allocation", "hide-resident-code",
            "allocate-new-ring-state", "overwrite-native-history-prefix",
            "ring-full-off-by-one", "lower-input-rate", "shorten-GC-envelope",
            "drop-event-six", "lose-event-order", "omit-A0-normalization",
            "route-RUN-STOP-through-raw-PETSCII", "leave-capture-active-during-eval",
            "omit-error-cleanup", "add-public-primitive", "exceed-code-object-ceiling"
        ],
        "claim_limit": "Host-only exact pricing and target-object assembly. No product source changed, no product was linked, no hardware was contacted, and no implementation or acceptance is claimed.",
    }


def selftest(contract: dict[str, Any]) -> int:
    baseline = derive(contract)
    require(baseline["loss_model"]["simulation"]["dropped"] == 0,
            "baseline loss model is not green")
    mutations = [
        ("queue", lambda c: c["loss_model"].__setitem__("hardware_queue_events", 6)),
        ("pause", lambda c: c["loss_model"].__setitem__("worst_collection_frames", 88)),
        ("rate", lambda c: c["loss_model"].__setitem__("physical_input_contract_events_per_frame", 0)),
        ("ring", lambda c: c["capture_shape"].__setitem__("ring_index_values", 94)),
        ("state", lambda c: c["candidate_geometry"].__setitem__("fixed_state_section_bytes", 14)),
        ("history", lambda c: c["candidate_geometry"].__setitem__("canonical_activation_bytes_including_nul", 6)),
        ("resident-wall", lambda c: c["walls"].__setitem__("resident_cost_requires_owner_decision", False)),
        ("contact", lambda c: c["walls"].__setitem__("device_contacts", 1)),
    ]
    rejected = 0
    for _, mutate in mutations:
        candidate = copy.deepcopy(contract)
        mutate(candidate)
        try:
            derive(candidate)
        except PricingError:
            rejected += 1
    require(rejected == len(mutations), "pricing mutation escaped")
    print(f"v1.6 Comfort input fidelity pricing: SELFTEST PASS mutations={rejected}")
    return 0


def check(contract: dict[str, Any]) -> int:
    value = derive(contract)
    require(RECEIPT.is_file(), "pricing receipt absent")
    require(load(RECEIPT) == value, "pricing receipt drift")
    print("v1.6 Comfort input fidelity pricing: PASS "
          "required=94 ring=111 margin=17 resident=74 bank2=251 owner=required")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("emit", "selftest", "check"))
    args = parser.parse_args()
    contract = load(CONTRACT)
    if args.mode == "emit":
        write(RECEIPT, derive(contract))
        print(f"wrote {RECEIPT.relative_to(ROOT)}")
        return 0
    if args.mode == "selftest":
        return selftest(contract)
    return check(contract)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PricingError, ERA.EraError, subprocess.CalledProcessError) as exc:
        print(f"v1.6 Comfort input fidelity pricing: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
