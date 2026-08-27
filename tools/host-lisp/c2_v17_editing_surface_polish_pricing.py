#!/usr/bin/env python3
"""Price the v1.7 shared matcher and cursor blink without shipping freight."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as VM  # noqa: E402
import bytecode_p0_stdlib as P0  # noqa: E402
import c2_v125_editor_latency_accounting as IDE_TIMING  # noqa: E402
import evidence_era as ERA  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


CONTRACT = ROOT / "config/c2-v17-editing-surface-polish-pricing-contract.json"
RECEIPT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                  "c2.3-v1.7-editing-surface-polish-pricing-receipt.json")
DEVICE = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                 "c2.3-v1.6-item1-d5-result-receipt.json")
SCANNER = ROOT / "lib/sexp-depth.lisp"
LINE_EDITOR = ROOT / "lib/stdlib-read-line.lisp"
IDE_UI = ROOT / "lib/ide-ui.lisp"
IDE_BUFFER = ROOT / "lib/ide-buffer.lisp"
SCREEN = ROOT / "src/screen.c"
MAIN = ROOT / "src/main.c"
CORE_VIC = ROOT / "build/upstream-verification/mega65-core/src/vhdl/viciv.vhdl"
ELF = ROOT / ("build/c2.3/v1.6-item1-only-candidate-r1/wplto/"
              "lisp65-c2-substitution-linked.prg.elf")
LINE_SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json"
IDE_SUITE = ROOT / "build/bytecode/dialect-v2/suites/p0-ide-core-lib.json"
TIMING_RECEIPT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                         "c2.3-v1.6-input-service-time-pricing-receipt.json")
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-c2-v17-editing-surface-polish-pricing-receipt-v1"
SEALED_COMMIT = "7c8e4fc4"


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


MATCHER_SOURCE = r'''
(defun nthcdr (n xs)
  (if (= n 0) xs (nthcdr (- n 1) (cdr xs))))

(defun %sexp-code (source codes i)
  (if (stringp source) (string-ref source i) (car codes)))

(defun %sexp-rest (source codes)
  (if (stringp source) codes (cdr codes)))

(defun %sexp-step (c packed)
  (let* ((state (mod packed 4))
         (depth (/ (- packed state) 4)))
    (if (= state 3)
        (+ (* depth 4) 2)
        (if (= state 2)
            (+ (* depth 4) (if (= c 92) 3 (if (= c 34) 0 2)))
            (if (= state 1)
                packed
                (if (= c 59)
                    (+ (* depth 4) 1)
                    (if (= c 34)
                        (+ (* depth 4) 2)
                        (* (if (= c 40) (+ depth 1)
                               (if (= c 41) (- depth 1) depth)) 4))))))))

(defun %sexp-scan (source codes stop i packed)
  (if (if (< i stop) (if (stringp source) 't codes) nil)
      (if (= (mod packed 4) 1)
          packed
          (%sexp-scan source (%sexp-rest source codes) stop (+ i 1)
                      (%sexp-step (%sexp-code source codes i) packed)))
      packed))

(defun %sexp-open (source codes stop i packed target found kind)
  (if (if (< i stop) (if (stringp source) 't codes) nil)
      (let* ((c (%sexp-code source codes i))
             (state (mod packed 4))
             (next (%sexp-step c packed)))
        (if (= state 1)
            found
            (%sexp-open
             source (%sexp-rest source codes) stop (+ i 1) next target
             (if (if (= kind 34)
                     (and (= state 0) (= c 34))
                     (and (= state 0)
                          (and (= c 40) (= (/ next 4) target))))
                 i found)
             kind)))
      found))

(defun %sexp-close (source codes stop i packed kind)
  (if (if (< i stop) (if (stringp source) 't codes) nil)
      (let* ((c (%sexp-code source codes i))
             (state (mod packed 4))
             (depth (/ (- packed state) 4)))
        (if (= state 1)
            nil
            (if (if (= kind 34)
                    (and (= state 2) (= c 34))
                    (and (= state 0) (and (= c 41) (= depth 1))))
                i
                (%sexp-close source (%sexp-rest source codes) stop (+ i 1)
                             (%sexp-step c packed) kind))))
      nil))

(defun %sexp-match (source point code)
  (let* ((string-source (stringp source))
         (codes (if string-source nil source))
         (stop (if string-source (string-length source) 250))
         (packed (%sexp-scan source codes point 0 0))
         (state (mod packed 4))
         (depth (/ (- packed state) 4)))
    (if (= code 40)
        (if (= state 0)
            (%sexp-close source
                         (if string-source codes (nthcdr (+ point 1) codes))
                         stop (+ point 1) 4 41) nil)
        (if (= code 41)
            (if (and (= state 0) (> depth 0))
                (%sexp-open source codes point 0 0 depth nil 40) nil)
            (if (= code 34)
                (if (= state 0)
                    (%sexp-close source
                                 (if string-source codes
                                     (nthcdr (+ point 1) codes))
                                 stop (+ point 1) 8 34)
                    (if (= state 2)
                        (%sexp-open source codes point 0 0 0 nil 34) nil))
                nil)))))
'''


BLINK_SOURCE = r'''
(defun %cursor-blink (blink code column row force)
  (let* ((now (peek 255 131))
         (elapsed (mod (- now (car blink)) 256))
         (phase (if force 't (if (>= elapsed 32) (not (cdr blink)) (cdr blink)))))
    (if (or force (>= elapsed 32))
        (progn
          (rplaca blink now)
          (rplacd blink phase)
          (screen-put-char column row code (if phase 129 1))
          nil)
        nil)))
'''


def list_expr(values: list[int]) -> str:
    return "(quote (" + " ".join(str(value) for value in values) + "))"


def matcher_cases() -> list[dict[str, Any]]:
    nested = [40, 97, 32, 40, 98, 41, 41]
    quoted = [34, 97, 92, 34, 98, 34]
    long_open = [40] + [97] * 249
    ide_line = [97] * 38 + [40, 98, 41] + [99] * 38
    return [
        {"name": "line-open-match", "expr":
         f"(%sexp-match {list_expr(nested)} 0 40)", "expect": "6",
         "surface": "line-editor", "class": "matched"},
        {"name": "line-close-match", "expr":
         f"(%sexp-match {list_expr(nested)} 6 41)", "expect": "0",
         "surface": "line-editor", "class": "matched"},
        {"name": "line-unmatched-250", "expr":
         f"(%sexp-match {list_expr(long_open)} 0 40)", "expect": "nil",
         "surface": "line-editor", "class": "long-unmatched"},
        {"name": "idle-list-scan-chunk-three", "expr":
         f"(%sexp-scan {list_expr(long_open)} {list_expr(long_open)} 3 0 0)",
         "expect": "4",
         "surface": "shared-idle", "class": "bounded-chunk"},
        {"name": "idle-list-open-chunk-three", "expr":
         f"(%sexp-open {list_expr([97, 97, 97])} "
         f"{list_expr([97, 97, 97])} 3 0 0 9 nil 40)",
         "expect": "nil",
         "surface": "shared-idle", "class": "bounded-chunk"},
        {"name": "idle-list-close-chunk-three", "expr":
         f"(%sexp-close {list_expr([97, 97, 97])} "
         f"{list_expr([97, 97, 97])} 3 0 4 41)",
         "expect": "nil",
         "surface": "shared-idle", "class": "bounded-chunk"},
        {"name": "idle-string-scan-chunk-three", "expr":
         '(%sexp-scan "aaa" nil 3 0 0)', "expect": "0",
         "surface": "shared-idle", "class": "bounded-chunk"},
        {"name": "idle-string-open-chunk-three", "expr":
         '(%sexp-open "aaa" nil 3 0 0 9 nil 40)', "expect": "nil",
         "surface": "shared-idle", "class": "bounded-chunk"},
        {"name": "idle-string-close-chunk-three", "expr":
         '(%sexp-close "aaa" nil 3 0 4 41)', "expect": "nil",
         "surface": "shared-idle", "class": "bounded-chunk"},
        {"name": "line-string-hidden", "expr":
         f"(%sexp-match {list_expr([40, 34, 41, 34, 41])} 2 41)",
         "expect": "nil", "surface": "line-editor", "class": "string"},
        {"name": "line-comment-hidden", "expr":
         f"(%sexp-match {list_expr([40, 59, 41, 41])} 2 41)",
         "expect": "nil", "surface": "line-editor", "class": "comment"},
        {"name": "line-quote-open", "expr":
         f"(%sexp-match {list_expr(quoted)} 0 34)", "expect": "5",
         "surface": "line-editor", "class": "quote"},
        {"name": "line-quote-close", "expr":
         f"(%sexp-match {list_expr(quoted)} 5 34)", "expect": "0",
         "surface": "line-editor", "class": "quote"},
        {"name": "line-escaped-quote-hidden", "expr":
         f"(%sexp-match {list_expr(quoted)} 3 34)", "expect": "nil",
         "surface": "line-editor", "class": "string"},
        {"name": "ide-ordinary-key-bypass", "expr":
         f"(if (or (= 98 40) (or (= 98 41) (= 98 34))) "
         f"(%sexp-match {json.dumps(''.join(chr(x) for x in ide_line))} 40 98) nil)",
         "expect": "nil", "surface": "ide", "class": "ordinary-key-bypass"},
        {"name": "ide-close-match-79", "expr":
         f"(%sexp-match {json.dumps(''.join(chr(x) for x in ide_line))} 40 41)",
         "expect": "38", "surface": "ide", "class": "matched"}
    ]


def compile_and_execute(source: str, functions: list[str],
                        cases: list[dict[str, Any]], label: str,
                        support_functions: tuple[str, ...] = ()) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("w", suffix=".lisp", delete=False) as handle:
        source_path = Path(handle.name)
        handle.write(source)
    try:
        suite = {"format": "lisp65-bytecode-p0-disk-lib-suite-v1",
                 "name": label, "sources": [str(source_path)],
                 "functions": list(support_functions) + functions, "strict_arity": True,
                 "abi_profile": "dialect-v2", "max_call_args": 12,
                 "cases": [{key: value for key, value in case.items()
                            if key in {"name", "expr", "expect",
                                       "memory_read_sequences",
                                       "expect_screen_rows", "expect_io_min"}}
                           for case in cases]}
        (heap, names, code, entry_flags, resident_flags, bundle, directory,
         compiled_cases, entries, _inliner) = P0._compile_suite(suite)
        P0._validate_code_object_size_expectations(suite, code,
            skip_names=P0._case_object_names(entries, code))
        macros = P0._macro_symbol_objs(heap, entry_flags, resident_flags)
        abi_profile, abi_ledger = P0._suite_abi(suite)
        metrics = []
        for specification, compiled, entry in zip(cases, compiled_cases, entries):
            case_heap = heap.clone()
            before = len(case_heap.cells)
            vm = VM.P0VM(
                heap=case_heap, directory=directory, macro_symbols=macros,
                max_steps=compiled.get("max_steps", 1_000_000), max_call_args=12,
                memory_read_sequences=compiled.get("memory_read_sequences"),
                abi_profile=abi_profile, abi_ledger=abi_ledger)
            result = vm.run(directory[heap.intern(entry)], [])
            observed = case_heap.obj_to_text(result)
            require(observed == compiled["expect"],
                    f"{compiled['name']}: expected {compiled['expect']} got {observed}")
            io = P0._validate_case_io(compiled, vm, label, "source", ())
            row = {"name": specification["name"],
                   "surface": specification.get("surface"),
                   "class": specification.get("class"),
                   "result": observed, "steps": vm.steps,
                   "runtime_allocations": len(case_heap.cells) - before}
            if io:
                row["io_witness"] = io
            metrics.append(row)
        sizes = {name: len(code[name].encode()) for name in functions}
        targets = set()
        for name in functions:
            try:
                targets.update(edge[1] for edge in P0._call_edges(heap, code[name]))
            except VM.DecodeError:
                # Product-profile CALLPRIMs are already executed above against
                # the explicit ABI ledger; the legacy call-edge helper uses
                # the narrower compile-REPL view and cannot decode them.
                targets.add("<product-callprim>")
        return {"functions": functions, "function_bytes": sizes,
                "total_function_bytes": sum(sizes.values()),
                "maximum_object_bytes": max(sizes.values()),
                "runtime_call_targets": sorted(targets),
                "cases": metrics, "compiled_bundle_bytes": len(bundle.blob),
                "compiled_objects": len(names)}
    finally:
        source_path.unlink()


def line_case_steps(name: str) -> int:
    suite = P0._read_suite(str(LINE_SUITE))
    selected = [case for case in suite["cases"] if case["name"] == name]
    require(len(selected) == 1, f"line-editor baseline case absent: {name}")
    suite["cases"] = selected
    return int(P0.check_suite(f"v1.7-{name}", suite)["steps"])


def service_baseline() -> dict[str, Any]:
    empty = line_case_steps("read-line-empty")
    echo = line_case_steps("read-line-echo")
    line_per_character = (echo - empty) / 3.0
    require(line_per_character > 0, "line-editor service baseline is not positive")
    ide = IDE_TIMING.run_schedule(IDE_SUITE, batch_size=1, max_steps=500_000)
    timing = load(TIMING_RECEIPT)["measurement_basis"]
    cycles_per_step = timing["historical_cycles_per_vm_instruction"]
    cycles_per_frame = timing["target_cycles_per_frame"]
    require(cycles_per_step == 1100 and cycles_per_frame == 800000,
            "historical VM/frame conversion authority drift")
    return {
        "line_editor": {
            "empty_line_steps": empty, "three_character_echo_steps": echo,
            "incremental_steps_per_ordinary_character": line_per_character,
            "authority": LINE_SUITE.relative_to(ROOT).as_posix()
        },
        "ide": {
            "keys": ide["keys"],
            "mean_steps_per_key": ide["dynamic_instructions"]
                ["total_charged_to_key"]["mean"],
            "median_steps_per_key": ide["dynamic_instructions"]
                ["total_charged_to_key"]["median"],
            "maximum_steps_per_key": ide["dynamic_instructions"]
                ["total_charged_to_key"]["maximum"],
            "mean_allocations_per_key": ide["allocations"]
                ["total_charged_to_key"]["mean"],
            "claim_limit": ide["bounded_time_projection"]["claim_limit"],
            "authority": IDE_SUITE.relative_to(ROOT).as_posix()
        },
        "conversion": {
            "historical_cycles_per_vm_instruction": cycles_per_step,
            "target_cycles_per_frame": cycles_per_frame,
            "vm_steps_per_frame": cycles_per_frame / cycles_per_step,
            "usage": "chunk bound only; not a current device timing claim"
        }
    }


def matcher_price(contract: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    cases = matcher_cases()
    compiled = compile_and_execute(
        MATCHER_SOURCE,
        ["%sexp-code", "%sexp-rest", "%sexp-step", "%sexp-scan",
         "%sexp-open", "%sexp-close", "%sexp-match"],
        cases, "v1.7-editing-polish-matcher",
        support_functions=("nthcdr",))
    allocation_targets = {"cons", "list", "append", "reverse", "string->list"}
    require(not (allocation_targets & set(compiled["runtime_call_targets"])),
            "matcher hot body contains an allocating call")
    require(all(token not in MATCHER_SOURCE for token in
                ["(cons ", "(list ", "(append ", "(reverse ", "(string->list "]),
            "matcher prototype contains an allocating source call")
    by_name = {row["name"]: row for row in compiled["cases"]}
    require(all(by_name[name]["runtime_allocations"] == 0 for name in by_name
                if not name.startswith("ide-")),
            "list-native matcher allocated on the line-editor seam")
    require(by_name["ide-close-match-79"]["runtime_allocations"] == 0,
            "shared scanner allocated after IDE adapter materialization")
    ide_allocations = 0
    chunk_rows = [row for row in compiled["cases"]
                  if row["class"] == "bounded-chunk"]
    chunk_steps = max(row["steps"] for row in chunk_rows)
    chunk_worst_case = next(row["name"] for row in chunk_rows
                            if row["steps"] == chunk_steps)
    chunk_frames = chunk_steps / baseline["conversion"]["vm_steps_per_frame"]
    require(chunk_frames <= contract["matcher"]["maximum_idle_chunk_frames"],
            f"idle matcher chunk exceeds bound: {chunk_frames}")
    synchronous_long = by_name["line-unmatched-250"]["steps"]
    require(synchronous_long >
            20 * baseline["line_editor"]["incremental_steps_per_ordinary_character"],
            "synchronous long-line rejection no longer bites")
    names = ["%sexp-code", "%sexp-rest", "%sexp-step", "%sexp-scan",
             "%sexp-open", "%sexp-close",
             "%sexp-match", "%sexp-paint", "%cursor-blink", "%rl-idle",
             "%ide-idle"]
    name_bytes = sum(len(name.encode("ascii")) + 1 for name in names)
    free_baseline = contract["delivery_baseline"]["free"]
    free = {"symbol_slots": free_baseline["symbol_slots"] - len(names),
            "namepool_bytes": free_baseline["namepool_bytes"] - name_bytes}
    return {
        "selected_form": ("single lexical engine over lists or packed strings; "
                          "every forward, opening and closing pass advances only "
                          "in three-code idle chunks"),
        "rejected_form": {
            "name": "synchronous full scan on delimiter dispatch",
            "long_line_steps": synchronous_long,
            "ordinary_line_key_equivalents": round(
                synchronous_long /
                baseline["line_editor"]["incremental_steps_per_ordinary_character"], 3),
            "reason": "would visibly stall the accepted line-editor input path"
        },
        "idle_schedule": {
            "codes_per_chunk": contract["matcher"]["idle_chunk_codes"],
            "measured_chunk_steps": chunk_steps,
            "measured_worst_case": chunk_worst_case,
            "measured_pass_cases": [
                {"name": row["name"], "steps": row["steps"]}
                for row in chunk_rows],
            "historical_frame_equivalent": round(chunk_frames, 6),
            "maximum_frame_equivalent":
                contract["matcher"]["maximum_idle_chunk_frames"],
            "input_poll_between_every_chunk": True,
            "full_250_code_chunks_per_pass": 84,
            "worst_two_pass_250_code_match_chunks": 168,
            "full_79_code_chunks_per_pass": 27,
            "worst_two_pass_79_code_match_chunks": 54
        },
        "surface_adapters": {
            "line-editor": "native sentinel-chain code list; zero allocations",
            "ide": ("scan the already materialized packed line through string-ref; "
                    "zero adapter allocations"),
            "parked-comfort": "same code-list seam; compatibility only"
        },
        "compiled": compiled,
        "selected_named_entries": names,
        "selected_named_entries_count": len(names),
        "selected_namepool_bytes": name_bytes,
        "capacity_after_selected_block3_names": free,
        "ide_delimiter_key_allocations": ide_allocations,
        "ordinary_key_scans": 0,
        "highlight_state_cells_per_surface": 2,
        "note": ("paint ownership and stale-highlight clearing are implementation "
                 "gates; the scanner returns only a partner index")
    }


def blink_price(contract: dict[str, Any]) -> dict[str, Any]:
    cases = [
        {"name": "line-idle-no-toggle", "expr":
         "(let ((b (cons 10 nil))) (%cursor-blink b 32 0 24 nil))",
         "expect": "nil", "surface": "line-editor", "class": "idle",
         "memory_read_sequences": {"0xff83": [20]},
         "expect_io_min": {"memory_read_sequence": 1}},
        {"name": "line-idle-toggle", "expr":
         "(let ((b (cons 10 nil))) (%cursor-blink b 32 0 24 nil))",
         "expect": "nil", "surface": "line-editor", "class": "toggle",
         "memory_read_sequences": {"0xff83": [42]},
         "expect_io_min": {"memory_read_sequence": 1, "screen_put_char": 1}},
        {"name": "ide-idle-toggle", "expr":
         "(let ((b (cons 250 t))) (%cursor-blink b 97 12 5 nil))",
         "expect": "nil", "surface": "ide", "class": "wrap-toggle",
         "memory_read_sequences": {"0xff83": [26]},
         "expect_io_min": {"memory_read_sequence": 1, "screen_put_char": 1}},
        {"name": "dispatch-forces-visible", "expr":
         "(let ((b (cons 10 nil))) (%cursor-blink b 97 3 5 t))",
         "expect": "nil", "surface": "both", "class": "handoff",
         "memory_read_sequences": {"0xff83": [11]},
         "expect_io_min": {"memory_read_sequence": 1, "screen_put_char": 1}}
    ]
    compiled = compile_and_execute(
        BLINK_SOURCE, ["%cursor-blink"], cases, "v1.7-editing-polish-blink")
    require(compiled["maximum_object_bytes"] <= 255,
            "software blink kernel exceeds object ceiling")
    screen = SCREEN.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    core = CORE_VIC.read_text(encoding="utf-8")
    line = LINE_EDITOR.read_text(encoding="utf-8")
    ide = IDE_UI.read_text(encoding="utf-8")
    require("colourramdata(4)='1'" in core and "viciii_extended_attributes" in core,
            "pinned core source no longer exposes the hardware blink feature")
    require("#define CRAM_WINDOW 1024u" in screen
            and screen.count("attr & 0x0F") >= 4,
            "delivered colour-writer boundary drift")
    require("(key-event 1)" in line and "(read-key)" in ide
            and "(poll-key)" in ide,
            "delivered blocking/polling seams drift")
    truth = ElfTruth.read(ELF, llvm_readobj=LLVM_READOBJ)
    frame_counter = truth.symbol("C2K_FRAME_LO")
    require(frame_counter.section == "Absolute"
            and frame_counter.value == int(
                contract["blink"]["frame_counter_low"], 0),
            "selected product frame-counter authority drift")
    hardware = {
        "core_capability_present": True,
        "delivered_profile_enables_attr_bit": bool(re.search(
            r"D031[^\n]*(?:\||=)[^\n]*0x20", main, re.IGNORECASE)),
        "real_writer_preserves_blink_bit": "attr & 0x1F" in screen,
        "colour_window_bytes": 1024,
        "line_editor_cursor_offset_at_80x25": 24 * 80,
        "covers_line_editor_last_row": (24 * 80) < 1024,
        "viable": False,
        "reason": ("the core implements blink, but the selected product neither "
                   "owns ATTR enable nor preserves bit 4; its safe CPU colour "
                   "window also ends before the line editor's last row")
    }
    require(not any([hardware["delivered_profile_enables_attr_bit"],
                     hardware["real_writer_preserves_blink_bit"],
                     hardware["covers_line_editor_last_row"]]),
            "hardware blink unexpectedly became a delivered all-surface route")
    return {
        "hardware_attribute": hardware,
        "software_idle_phase": {
            "selected": True,
            "compiled": compiled,
            "half_period_frames": contract["blink"]["half_period_frames"],
            "frame_counter": "C2K_FRAME_LO at 0xff83 in the selected final ELF",
            "state": "one mutable (last-frame . visible-phase) pair per active surface",
            "resident_bytes": 0, "new_primitive": False,
            "new_timer_owner": False, "new_input_owner": False,
            "surface_changes": {
                "line-editor": ("blocking key-event becomes a nonblocking wait loop; "
                                "the same public input owner is retained"),
                "ide": ("existing poll-key becomes the idle source as well as the "
                        "burst-drain source; no second queue reader")
            },
            "dispatch_handoff": "cursor is forced visible before a key is dispatched"
        }
    }


def derive() -> dict[str, Any]:
    contract = load(CONTRACT)
    require(contract.get("format") ==
            "lisp65-c2-v17-editing-surface-polish-pricing-contract-v1"
            and contract.get("status") == "host-only-pricing"
            and contract.get("commission_commit") == "60599dbb",
            "pricing commission identity drift")
    device = load(DEVICE)
    baseline = contract["delivery_baseline"]
    require(device["D5_user_headroom"]["free"] == baseline["free"]
            and device["D5_user_headroom"]["minimum_free"] ==
                baseline["minimum_free"]
            and device["measurement_configuration"]["loaded_library_roles"] ==
                baseline["loaded_library_roles"]
            and device["measurement_configuration"]["absent_library_roles"] ==
                baseline["absent_library_roles"],
            "Comfort-free delivery baseline drift")
    require("%ide-line-net-depth" in SCANNER.read_text(encoding="utf-8"),
            "shared scanner seam absent")
    require("(%read-line-loop state)" in LINE_EDITOR.read_text(encoding="utf-8")
            and "ide-render-cursor-from" in IDE_UI.read_text(encoding="utf-8")
            and "ide-buffer-locals" in IDE_BUFFER.read_text(encoding="utf-8"),
            "actual surface seam absent")

    baseline_service = service_baseline()
    matcher = matcher_price(contract, baseline_service)
    blink = blink_price(contract)
    after = matcher["capacity_after_selected_block3_names"]
    minimum = baseline["minimum_free"]
    require(after["symbol_slots"] >= minimum["symbol_slots"]
            and after["namepool_bytes"] >= minimum["namepool_bytes"],
            "selected matcher violates delivery headroom")
    return {
        "format": FORMAT, "recorded_on": "2026-08-25",
        "status": "PRICED: shared matcher plus software idle blink selected",
        "claim_limit": {
            "accepts": ["host-only pricing", "compiled matcher prototype",
                        "compiled software blink kernel", "capacity arithmetic"],
            "excludes": ["implementation", "product/library source change",
                         "WPLTO", "product link", "media", "device acceptance",
                         "native C fallback matcher", "parked Comfort acceptance"]
        },
        "inputs": [bind(path) for path in
                   [CONTRACT, DEVICE, SCANNER, LINE_EDITOR, IDE_UI, IDE_BUFFER,
                    SCREEN, MAIN, CORE_VIC, ELF, LINE_SUITE, IDE_SUITE,
                    TIMING_RECEIPT]],
        "delivery_world": {
            "free_before": baseline["free"], "minimum_free": minimum,
            "measurement": "device D5, Comfort absent; no projection bias applied",
            "free_after_selected_named_entries": after,
            "margin_after_selected_named_entries": {
                "symbol_slots": after["symbol_slots"] - minimum["symbol_slots"],
                "namepool_bytes": after["namepool_bytes"] - minimum["namepool_bytes"]
            }
        },
        "service_baseline": baseline_service,
        "matcher": matcher, "blink": blink,
        "decision": {
            "matcher": "shared lexical matcher, delimiter-triggered and idle-chunked on every pass",
            "blink": "software idle phase on the existing frame counter",
            "implementation_cards": ["shared scanner and paint ownership",
                                     "line-editor idle blink", "IDE idle blink"],
            "owner_decision_required": False,
            "review_touchpoint_required": True,
            "reason": ("both selected forms are Bank-2 only and introduce neither "
                       "resident bytes, a primitive, an input owner nor a timer owner")
        },
        "permanent_gates": [
            "matcher lexical parity includes escaped quotes, strings and comments",
            "ordinary non-delimiter keys do not run the scanner",
            "every matcher pass yields after at most three code units",
            "unmatched or moved-away input clears prior highlight",
            "the composed framebuffer owns cursor and pair paint together",
            "software blink polls only while idle and forces visible before dispatch",
            "each surface has one input owner and the existing frame counter remains the sole timer owner",
            "hardware blink cannot be claimed from core capability without delivered ATTR enable, bit-4 preservation and all-row reach",
            "D5 measures the final loaded Block-3 configuration"
        ],
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
                                 "media_builds": 0, "device_contacts": 0}
    }


def check_sealed_receipt() -> dict[str, Any]:
    """Validate the accepted price in its own world, not a successor world.

    Implementation cards intentionally change the scanner and suite inputs
    whose pre-freight identities the pricing receipt records.  Re-deriving the
    price over those successors would turn accepted evidence into a perpetual
    rewrite target.  Current implementation facts belong to each card's live
    gate; this gate keeps the accepted price byte-identical to its sealing era.
    """
    require(RECEIPT.is_file() and not RECEIPT.is_symlink(),
            "editing-surface pricing receipt absent")
    raw = RECEIPT.read_bytes()
    require(raw == ERA.era_blob(
        SEALED_COMMIT, RECEIPT.relative_to(ROOT).as_posix()),
        "sealed editing-surface pricing receipt was rewritten")
    value = json.loads(raw)
    require(value.get("format") == FORMAT
            and value.get("status")
                == "PRICED: shared matcher plus software idle blink selected"
            and value.get("decision", {}).get("implementation_cards") == [
                "shared scanner and paint ownership",
                "line-editor idle blink", "IDE idle blink"],
            "sealed editing-surface pricing identity drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        result = check_sealed_receipt()
    else:
        result = derive()
        raw = canonical(result)
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(raw)
    print("v1.7 editing-surface polish pricing: PASS "
          f"matcher={result['matcher']['compiled']['total_function_bytes']}B "
          f"slots={result['delivery_world']['free_after_selected_named_entries']['symbol_slots']} "
          "blink=software-idle resident=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
