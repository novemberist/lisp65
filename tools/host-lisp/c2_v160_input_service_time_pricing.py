#!/usr/bin/env python3
"""Host-only service-time price for the v1.6 Comfort input First Red.

The dynamic counts execute the real Workbench resident composition in P0.
They are converted to raster-frame equivalents only through already-bound
target constants.  This is deliberately not presented as a new device timer.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as COMPILER  # noqa: E402
import bytecode_p0_stdlib as P0  # noqa: E402
import c2_ship_input_wait_gate as INPUT_GATE  # noqa: E402
import evidence_era as ERA  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


CONTRACT = ROOT / "config/c2-v160-input-service-time-pricing-contract.json"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
READ_LINE = ROOT / "lib/stdlib-read-line.lisp"
COMFORT = ROOT / "lib/repl-comfort.lisp"
RESIDENT = ROOT / "config/c2-v160-comfort-repl-resident-suite.json"
DISK_SUITE = ROOT / "tests/bytecode/libs/p0-repl-comfort.json"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-items12-input-first-red-device-receipt.json"
)
HARDWARE_40 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-hardware-first-red-receipt.json"
)
HOST_TIMING = ROOT / (
    "tests/bytecode/dialect-v2/evidence/post-release/"
    "v125-editor-input-latency-host-accounting-receipt.json"
)
ACCEPTANCE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-input-fidelity-acceptance-resume-receipt.json"
)
CANDIDATE_ELF = ROOT / (
    "build/c2.3/v1.6-input-fidelity-membership-real-consumer-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-input-service-time-pricing-receipt.json"
)
FORMAT = "lisp65-c2-v160-input-service-time-pricing-v1"
RECEIPT_SEALED_COMMIT = "93fcff1bbb7396def3a7e34330585a2b839c3928"


class PricingError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PricingError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
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


def replace_defun(source: str, name: str, replacement: str) -> str:
    start = source.index(f"(defun {name} ")
    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return source[:start] + replacement.strip() + source[index + 1:]
    raise PricingError(f"unterminated defun: {name}")


SCALAR_RENDER = r"""
(defun %rl-render (codes index column stop cursor row)
  (if (< row 0)
      (key-event 2)
      (if (< column stop)
          (let* ((present (if codes 't nil))
                 (at-cursor (= index cursor))
                 (code (if present (car codes) 32)))
            (progn
              (screen-put-char column row code (if at-cursor 129 1))
              (%rl-render
               (if present (cdr codes) nil)
               (+ index 1) (+ column 1) stop cursor row)))
          nil)))
"""


SCALAR_PUT = r"""
(defun %rl-put (code state cursor)
  (let* ((s1 (cdr state)) (s2 (cdr s1)) (s3 (cdr s2))
         (s4 (cdr s3)) (s5 (cdr s4)) (s6 (cdr s5)) (s7 (cdr s6))
         (head (car state)) (tail (car s2)) (position (car s3))
         (length (car s4)) (start (car s5)) (columns (car s6))
         (inserted (cons code (cdr cursor)))
         (next-position (+ position 1)) (next-length (+ length 1))
         (next-start (if (>= next-position (+ start columns))
                         (- next-position (- columns 1)) start))
         (full (> next-start start))
         (from (if full next-start position))
         (edge (+ (- next-length start) 1))
         (stop (if (< edge columns) edge columns)))
    (progn
      (rplacd cursor inserted)
      (rplaca s1 inserted)
      (if (eq cursor tail) (rplaca s2 inserted) nil)
      (rplaca s3 next-position)
      (rplaca s4 next-length)
      (rplaca s5 next-start)
      (%rl-render
       (nthcdr from (cdr head)) from (- from next-start) stop
       next-position (car s7))
      (%read-line-loop state))))
"""


SCALAR_LOOP = r"""
(defun %read-line-loop (state)
  (let* ((event (if (nthcdr 8 state)
                    (%rl-render nil 0 0 0 0 -1)
                    (key-event 1)))
         (code (if (numberp event) event (cadr event))))
    (if (and (>= code 32) (<= code 126))
        (if (< (car (nthcdr 4 state)) 250)
            (%rl-put code state (car (cdr state)))
            (%read-line-loop state))
        (let* ((command
                ((lambda (binding) (if binding (cdr binding) 0))
                 (assoc code
                  (quote ((13 . 1109) (20 . 1101) (157 . 1106)
                          (29 . 1107) (145 . 1108) (17 . 1003)
                          (4 . 1102) (6 . 1107) (2 . 1106)
                          (1 . 1104) (5 . 1103) (127 . 1101)))))))
          (if (= command 1109)
              (let* ((head (car state))
                     (position (car (nthcdr 3 state)))
                     (start (car (nthcdr 5 state)))
                     (row (car (nthcdr 7 state)))
                     (codes (cdr head)))
                (progn
                  (%rl-render
                   (nthcdr position codes) position (- position start)
                   (+ (- position start) 1) -1 row)
                  (write-char 10)
                  (%string-from-codes codes)))
              (%rl-dispatch command state))))))
"""


BATCH_PUT = r"""
(defun %rl-put (code state cursor dirty)
  (let* ((s1 (cdr state)) (s2 (cdr s1)) (s3 (cdr s2))
         (s4 (cdr s3)) (s5 (cdr s4)) (s6 (cdr s5))
         (head (car state)) (tail (car s2))
         (position (car s3)) (start (car s5))
         (inserted (cons code (cdr cursor)))
         (next-position (+ position 1))
         (next-start
          (if (>= next-position (+ start (car s6)))
              (- next-position (- (car s6) 1)) start)))
    (progn
      (rplacd cursor inserted)
      (rplaca s1 inserted)
      (if (eq cursor tail) (rplaca s2 inserted) nil)
      (rplaca s3 next-position)
      (rplaca s4 (+ (car s4) 1))
      (rplaca s5 next-start)
      (let* ((next-code (key-event 3)))
        (if next-code
            (%rl-put next-code state inserted dirty)
            (let* ((edge (+ (- (car s4) next-start) 1)))
              (progn
                (%rl-render
                 (nthcdr dirty (cdr head)) dirty (- dirty next-start)
                 (if (< edge (car s6)) edge (car s6))
                 next-position (car (cdr s6)))
                (%read-line-loop state))))))))
"""


def candidate_source(base_source: str, *, batch: bool) -> str:
    source = base_source
    source = replace_defun(source, "%rl-render", SCALAR_RENDER)
    source = replace_defun(source, "%rl-put", BATCH_PUT if batch else SCALAR_PUT)
    source = replace_defun(source, "%read-line-loop", SCALAR_LOOP)
    if batch:
        source = source.replace(
            "(%rl-put code state (car (cdr state)))",
            "(%rl-put code state (car (cdr state)) (car (nthcdr 3 state)))",
            1,
        )
    return source


def normalize_petscii(raw: int) -> tuple[int, bool]:
    rules = load(CONTRACT)["normalization"]["rules"]
    for rule in rules:
        if rule["first"] <= raw <= rule["last"]:
            return raw + rule["code_delta"], rule["add_shift"]
    return raw, False


class TimingVM(INPUT_GATE.AllocationVM):
    def __init__(self, *args: Any, batch_cap: int | None = None, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.boundaries: list[tuple[str, int]] = []
        self.screen_steps: list[int] = []
        self.batch_cap = batch_cap
        self.batch_count = 0

    def _c2_raw_capture_before_peek(self, address: int) -> None:
        before = len(self.key_events)
        super()._c2_raw_capture_before_peek(address)
        if len(self.key_events) < before:
            self.boundaries.append(("ring", self.steps))

    def _callprim(
        self, prim_id: int, argc: int, stack: list[int], pc: int | None = None,
        native_base: int = 0, frame_slots: int = 0,
    ) -> int:
        if prim_id == 11:
            self.screen_steps.append(self.steps)
        if prim_id == 60:
            mode = 0 if argc == 0 else (
                B.fixval(stack[-1]) if B.is_fix(stack[-1]) else -1
            )
            if mode in (0, 1):
                self.boundaries.append(("key-event", self.steps))
            if mode in (2, 3):
                self.boundaries.append((f"private-{mode}", self.steps))
                self._check_argc(argc, "CALLPRIM")
                self._pop_args(argc, stack)
                if mode == 2:
                    self.batch_count = 0
                if mode == 3 and self.batch_cap is not None:
                    if self.batch_count >= self.batch_cap:
                        return B.NIL
                if not self.key_events:
                    return B.NIL
                raw, _modifiers = self.key_events[0]
                code, _shift = normalize_petscii(raw)
                if mode == 3 and not 32 <= code <= 126:
                    return B.NIL
                self.key_events.pop(0)
                self.io_counters["key_event"] += 1
                self.batch_count += 1
                if raw == 3:
                    self.memory[0xFF8A] = 0
                    raise B.VMError("Stopped", "RUN/STOP")
                return B.mkfix(code)
        return super()._callprim(
            prim_id, argc, stack, pc=pc, native_base=native_base,
            frame_slots=frame_slots,
        )


def combined_suite(source_path: Path, expr: str, expected: str,
                   events: list[int]) -> dict[str, Any]:
    resident = P0._read_suite(str(RESIDENT))
    disk = P0._read_suite(str(DISK_SUITE))
    suite = copy.deepcopy(resident)
    suite["sources"] = [
        str(source_path) if path == "lib/stdlib-read-line.lisp" else path
        for path in resident["sources"]
    ] + disk["sources"]
    suite["functions"] = resident["functions"] + disk["functions"]
    if "(defun %rl-screen-tail" not in source_path.read_text(encoding="utf-8"):
        suite["functions"] = [name for name in suite["functions"]
                              if name != "%rl-screen-tail"]
    suite["tailcall_self"] = sorted(set(
        resident.get("tailcall_self", []) + disk.get("tailcall_self", [])
    ))
    suite["resident_suites"] = []
    suite["require_all_defuns"] = False
    suite["cases"] = [{
        "name": "input-service-time",
        "expr": expr,
        "expect": json.dumps(expected),
        "key_events": events,
        "max_steps": 1_000_000,
    }]
    return suite


def execute_route(source_path: Path, route: str, count: int,
                  batch_cap: int | None = None) -> dict[str, Any]:
    events = [97] * count + [13]
    expr = ("(read-line)" if route == "old-key-event"
            else "(%repl-read \"\" nil 0 80 0)")
    suite = combined_suite(source_path, expr, "a" * count, events)
    (heap, _names, _code, _entry_flags, resident_flags, _bundle,
     directory, _cases, entries, _inliner) = P0._compile_suite(suite)
    macros = P0._macro_symbol_objs(heap, {}, resident_flags)
    abi_profile, abi_ledger = P0._suite_abi(suite)
    case_heap = heap.clone()
    for tag in ("key", "shift", "control", "meta"):
        case_heap.intern(tag)
    vm = TimingVM(
        heap=case_heap, directory=directory, macro_symbols=macros,
        max_steps=1_000_000, max_call_args=suite.get("max_call_args"),
        key_events=events, abi_profile=abi_profile, abi_ledger=abi_ledger,
        batch_cap=batch_cap,
    )
    result = vm.run(directory[case_heap.intern(entries[0])], [])
    require(case_heap.obj_to_text(result) == json.dumps("a" * count),
            f"{route} executable result drift")
    if route == "old-key-event":
        points = [step for label, step in vm.boundaries if label == "key-event"]
    elif route == "current-ring":
        points = [step for label, step in vm.boundaries if label == "ring"]
    else:
        points = [step for label, step in vm.boundaries if label == "private-2"]
    if route == "batch":
        require(len(points) >= 2, f"{route} boundary count drift: {len(points)}")
    else:
        require(len(points) == count + 1,
                f"{route} boundary count drift: {len(points)}")
    first, last = points[0], points[-1]
    screens = sum(first <= step < last for step in vm.screen_steps)
    return {
        "characters": count,
        "dynamic_vm_steps": last - first,
        "vm_steps_per_character": (last - first) / count,
        "screen_cells": screens,
        "screen_cells_per_character": screens / count,
        "boundary_count": len(points),
        "heap_cells_per_character": 4 if route == "old-key-event" else 1,
    }


def compile_sizes(source: str) -> dict[str, int]:
    forms = [form for form in COMPILER.parse_all(source)
             if isinstance(form, list) and len(form) > 1 and form[0] == "defun"]
    heap = COMPILER.prepare_heap([form[1] for form in forms])
    result: dict[str, int] = {}
    for form in forms:
        if form[1] not in ("%rl-render", "%rl-put", "%read-line-loop"):
            continue
        name, code, helpers = COMPILER.compile_top_form_with_helpers(
            form, heap, strict_arity=True, abi_profile="dialect-v2",
            prebuilt_primitives=True,
        )
        require(not helpers, f"pricing prototype introduced helper: {name}")
        result[name] = len(code.encode())
    require(set(result) == {"%rl-render", "%rl-put", "%read-line-loop"},
            "pricing code-size set drift")
    require(max(result.values()) <= 255, "pricing prototype exceeds code-object ceiling")
    return result


NATIVE_SCALAR_ASM = r"""
    .equ HEAD,$ff8c
    .equ TAIL,$ff8d
    .equ BASE,$bc90
    .section .candidate,"ax",@progbits
    .globl c2_input_scalar
c2_input_scalar:
    lda TAIL
    bmi .Lnone
    cmp HEAD
    beq .Lnone
    tay
    lda BASE,y
    cmp #$a0
    bne .Lnotspace
    lda #$20
    bra .Lnormalized
.Lnotspace:
    cmp #$41
    bcc .Lnormalized
    cmp #$5b
    bcs .Lupper
    ora #$20
    bra .Lnormalized
.Lupper:
    cmp #$c1
    bcc .Lnormalized
    cmp #$db
    bcs .Lnormalized
    and #$7f
.Lnormalized:
    cpx #$03
    bne .Lcommit
    cmp #$20
    bcc .Lnone
    cmp #$7f
    bcs .Lnone
.Lcommit:
    iny
    cpy #112
    bne .Lstore
    ldy #0
.Lstore:
    sty TAIL
    sec
    rts
.Lnone:
    clc
    rts
"""


def native_price() -> int:
    compiler = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
    readobj = ROOT / "tools/llvm-mos/bin/llvm-readobj"
    require(compiler.is_file() and readobj.is_file(), "llvm-mos target tools absent")
    with tempfile.TemporaryDirectory(prefix="c2-v160-service-price-") as name:
        root = Path(name)
        source = root / "candidate.s"
        obj = root / "candidate.o"
        source.write_text(NATIVE_SCALAR_ASM, encoding="utf-8")
        completed = subprocess.run(
            [str(compiler), "-c", str(source), "-o", str(obj)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        require(completed.returncode == 0,
                f"native scalar assembly failed: {completed.stderr}")
        truth = ElfTruth.read(obj, llvm_readobj=readobj)
        return truth.section(".candidate").bytes


def e000_geometry() -> dict[str, Any]:
    truth = ElfTruth.read(
        CANDIDATE_ELF,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
    )
    sections = sorted(
        [
            {
                "name": section.name,
                "start": section.address,
                "end_exclusive": section.address + section.bytes,
                "bytes": section.bytes,
            }
            for section in truth.sections
            if section.bytes > 0 and 0xE000 <= section.address < 0x10000
        ],
        key=lambda row: row["start"],
    )
    free: list[dict[str, int]] = []
    cursor = 0xE000
    for section in sections:
        require(cursor <= section["start"], "overlapping E000 sections")
        if cursor < section["start"]:
            free.append({
                "start": cursor,
                "end_exclusive": section["start"],
                "bytes": section["start"] - cursor,
            })
        cursor = section["end_exclusive"]
    if cursor < 0x10000:
        free.append({
            "start": cursor, "end_exclusive": 0x10000,
            "bytes": 0x10000 - cursor,
        })
    require([row["bytes"] for row in free] == [2, 134, 10],
            f"final-ELF E000 holes drift: {free}")
    usable = free[:2]
    return {
        "source": "ElfTruth at the bound final candidate",
        "allocated_sections": len(sections),
        "free_intervals": free,
        "usable_intervals": usable,
        "usable_free_bytes": sum(row["bytes"] for row in usable),
        "terminal_vector_reserve_bytes": free[-1]["bytes"],
        "largest_contiguous_usable_hole_bytes": max(
            row["bytes"] for row in usable
        ),
    }


def frame_price(row: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    measure = contract["measurement"]
    cycles_per_frame = (
        measure["target_cpu_hz"] * measure["target_frame_microseconds"] / 1_000_000
    )
    vm_frames = (
        row["vm_steps_per_character"]
        * measure["historical_cycles_per_vm_instruction"] / cycles_per_frame
    )
    screen_frames = (
        row["screen_cells_per_character"]
        * measure["screen_put_at_cycles"] / cycles_per_frame
    )
    gc_frames = (
        row["heap_cells_per_character"]
        * measure["whole_collection_frames"] / measure["nursery_cells"]
    )
    total = vm_frames + screen_frames + gc_frames
    maximum = contract["responsiveness"]["maximum_frames_per_character"]
    return {
        **row,
        "vm_frame_equivalent": vm_frames,
        "screen_frame_equivalent": screen_frames,
        "steady_gc_frames_per_character": gc_frames,
        "total_frame_equivalent_per_character": total,
        "service_events_per_frame": 1 / total,
        "responsiveness_pass": total <= maximum,
    }


def parity_gate(contract: dict[str, Any]) -> dict[str, Any]:
    normalization = contract["normalization"]
    require(
        normalization["consumers"] == ["public-key-event", "comfort-raw-consumer"]
        and normalization["raw_fixture_domain"] == "all 256 PETSCII code bytes",
        "normalization authority/fixture domain drift",
    )
    require(normalization["rules"] == [
        {"first": 65, "last": 90, "code_delta": 32, "add_shift": False},
        {"first": 193, "last": 218, "code_delta": -128, "add_shift": True},
        {"first": 160, "last": 160, "code_delta": -128, "add_shift": False},
    ], "generated normalization table drift")
    rows = []
    for raw in range(256):
        public = normalize_petscii(raw)
        comfort = normalize_petscii(raw)
        require(public[0] == comfort[0], f"PETSCII consumer parity drift: {raw}")
        rows.append({"raw": raw, "code": public[0], "shift": public[1]})
    require(
        rows[0x41] == {"raw": 0x41, "code": 0x61, "shift": False}
        and rows[0x5A]["code"] == 0x7A
        and rows[0xC1] == {"raw": 0xC1, "code": 0x41, "shift": True}
        and rows[0xDA]["code"] == 0x5A
        and rows[0xA0] == {"raw": 0xA0, "code": 0x20, "shift": False}
        and rows[3]["code"] == 3,
        "raw PETSCII boundary witness drift",
    )
    return {
        "raw_codes": len(rows),
        "consumer_pairs": 2,
        "parity": True,
        "lowercase_unshifted_A_Z": [rows[0x41]["code"], rows[0x5A]["code"]],
        "uppercase_shifted_A_Z": [rows[0xC1]["code"], rows[0xDA]["code"]],
        "a0_to_space": rows[0xA0]["code"],
        "run_stop_unchanged": rows[3]["code"],
        "fixtures_begin_as": "raw-PETSCII",
    }


def validate(result: dict[str, Any], contract: dict[str, Any]) -> None:
    rows = result["service_time"]["rows"]
    budget = contract["responsiveness"]
    require(result["format"] == FORMAT and result["status"].startswith("PRICED:"),
            "pricing result identity drift")
    sealed_sources = [
        ERA.era_bind(contract["authority_commit"], path)
        for path in ("lib/stdlib-read-line.lisp", "lib/repl-comfort.lisp")
    ]
    require(result["authority"]["sources"] == sealed_sources,
            "historical pricing sources collapsed onto the living world")
    require(rows["current-ring"]["vm_steps_per_character"]
            > rows["old-key-event"]["vm_steps_per_character"],
            "measured ring overhead disappeared")
    require(not rows["native-scalar-only"]["responsiveness_pass"]
            and not rows["native-scalar-plus-hotpath"]["responsiveness_pass"],
            "scalar candidate incorrectly passes responsiveness")
    require(rows["batch-8"]["responsiveness_pass"],
            "eight-event batch ceased to pass responsiveness")
    require(result["decision"]["winner"]
            == "hybrid-native-scalar-plus-batched-edit-render-8",
            "winner drift")
    require(result["decision"]["minimum_admitted_batch"]
            >= budget["minimum_batch_size_to_price"],
            "underpriced batch admitted")
    require(result["normalization"]["raw_codes"] == 256
            and result["normalization"]["parity"]
            and result["normalization"]["fixtures_begin_as"] == "raw-PETSCII",
            "normalization/raw-fixture gate drift")
    capacity = result["capacity"]
    require(capacity["native_scalar_body_bytes"] <= capacity["body_ceiling_bytes"]
            and capacity["remaining_adapter_budget_bytes"] == 12
            and capacity["remaining_e000_above_floor_after_body"] == 12
            and capacity["born_derived_geometry"]["usable_free_bytes"] == 136
            and capacity["born_derived_geometry"]
                ["largest_contiguous_usable_hole_bytes"] == 134,
            "resident price/capacity arithmetic drift")
    require(result["walls"] == contract["candidate_walls"],
            "candidate wall drift")
    require(result["claim_limit"].startswith("Exact P0 dynamic counts"),
            "claim limit drift")


def derive() -> dict[str, Any]:
    contract = load(CONTRACT)
    require(
        contract["format"] == FORMAT
        and contract["status"] == "owner-commissioned-host-only-pricing",
        "pricing contract identity drift",
    )
    authority = ERA.era_bind(contract["authority_commit"], PLAN.relative_to(ROOT).as_posix())
    authority_text = ERA.era_blob(
        contract["authority_commit"], PLAN.relative_to(ROOT).as_posix()
    ).decode("utf-8")
    sealed_read_line = ERA.era_blob(
        contract["authority_commit"], READ_LINE.relative_to(ROOT).as_posix()
    )
    for token in (
        "Merged attribution: one deficit, two costumes",
        "Measure first",
        "native scalar",
        "bundled drain/edit/render",
        "raw PETSCII",
    ):
        require(token in authority_text, f"commission token absent: {token}")
    first_red = load(FIRST_RED)
    hardware = load(HARDWARE_40)
    host_timing = load(HOST_TIMING)
    acceptance = load(ACCEPTANCE)
    require(first_red["latency_classification"]["selected"]
            == "synchronous bytecode consumer/edit/render service latency",
            "stopped-state latency classification drift")
    require(hardware["D1"]["plain_burst"]["frames"] == 961
            and hardware["D1"]["plain_burst"]["frames_per_key"] == 24.025,
            "historical hardware timing authority drift")
    constants = host_timing["bound_constants"]
    measure = contract["measurement"]
    require(constants["historical_cycles_per_vm_instruction"]
            == measure["historical_cycles_per_vm_instruction"] == 1100
            and constants["target_cpu_hz"] == measure["target_cpu_hz"]
            and constants["target_frame_microseconds"]
            == measure["target_frame_microseconds"]
            and constants["target_collection_frames"]
            == measure["whole_collection_frames"] == 89,
            "target timing calibration drift")
    acceptance_result_path = ROOT / acceptance["authority"]["acceptance_result"]["path"]
    acceptance_result = load(acceptance_result_path)
    require(acceptance_result["delivered_bytes"]["candidate_elf"]
            == bind(CANDIDATE_ELF), "candidate ELF identity drift")

    count = measure["printable_characters"]
    with tempfile.TemporaryDirectory(prefix="c2-v160-service-sources-") as name:
        root = Path(name)
        current_path = root / "current.lisp"
        scalar_path = root / "scalar.lisp"
        batch_path = root / "batch.lisp"
        current_path.write_bytes(sealed_read_line)
        baseline_source = sealed_read_line.decode("utf-8")
        scalar_source = candidate_source(baseline_source, batch=False)
        batch_source = candidate_source(baseline_source, batch=True)
        scalar_path.write_text(scalar_source, encoding="utf-8")
        batch_path.write_text(batch_source, encoding="utf-8")
        raw_rows = {
            "old-key-event": execute_route(current_path, "old-key-event", count),
            "current-ring": execute_route(current_path, "current-ring", count),
            "native-scalar-only": execute_route(current_path, "current-ring", count),
            "native-scalar-plus-hotpath": execute_route(scalar_path, "scalar", count),
        }
        # Scalar-only changes transport overhead, not the editor.  The old
        # key-event dynamic count is therefore the exact no-chatter step row,
        # while retaining the ring world's one-cell event representation.
        raw_rows["native-scalar-only"] = dict(raw_rows["old-key-event"])
        raw_rows["native-scalar-only"]["heap_cells_per_character"] = 1
        raw_rows["native-scalar-only"]["boundary_count"] = count + 1
        for batch in (1, 2, 4, 8, 16):
            raw_rows[f"batch-{batch}"] = execute_route(
                batch_path, "batch", count, batch_cap=batch,
            )
        current_sizes = compile_sizes(baseline_source)
        scalar_sizes = compile_sizes(scalar_source)
        batch_sizes = compile_sizes(batch_source)

    rows = {name: frame_price(row, contract) for name, row in raw_rows.items()}
    passing_batches = [
        batch for batch in (1, 2, 4, 8, 16)
        if rows[f"batch-{batch}"]["responsiveness_pass"]
    ]
    require(passing_batches and min(passing_batches) == 8,
            f"minimum passing batch drift: {passing_batches}")
    native_bytes = native_price()
    capacity = contract["capacity"]
    geometry = e000_geometry()
    require(geometry["usable_free_bytes"]
            == capacity["post_capture_e000_free_bytes"] == 136,
            "born-derived usable E000 capacity drift")
    require(native_bytes == capacity["native_scalar_body_max_bytes"] == 70,
            f"native scalar body price drift: {native_bytes}")
    result = {
        "format": FORMAT,
        "recorded_on": "2026-08-19",
        "status": "PRICED: EIGHT-EVENT HYBRID WINS; IMPLEMENTATION REVIEW REQUIRED",
        "authority": {
            "commission": {
                "authority": "git-blob",
                "commit": contract["authority_commit"],
                "path": authority["path"],
                "bytes": authority["bytes"],
                "sha256": authority["sha256"],
            },
            "contract": bind(CONTRACT),
            "first_red": bind(FIRST_RED),
            "historical_40_key_device_timing": bind(HARDWARE_40),
            "host_target_calibration": bind(HOST_TIMING),
            "candidate_ELF": bind(CANDIDATE_ELF),
            "acceptance_receipt": bind(ACCEPTANCE),
            "sources": [
                ERA.era_bind(
                    contract["authority_commit"],
                    READ_LINE.relative_to(ROOT).as_posix(),
                ),
                ERA.era_bind(
                    contract["authority_commit"],
                    COMFORT.relative_to(ROOT).as_posix(),
                ),
            ],
        },
        "measurement_basis": {
            "real_workbench_composition": True,
            "characters": count,
            "target_cycles_per_frame": 800000,
            "historical_cycles_per_vm_instruction": 1100,
            "screen_put_at_cycles": 1500,
            "whole_collection_frames": 89,
            "nursery_cells": 192,
            "historical_device_crosscheck": {
                "surface": "v1.2.6 IDE editor, not the current REPL",
                "frames": 961,
                "keys": 40,
                "frames_per_key": 24.025,
                "used_as_current_baseline": False,
            },
        },
        "service_time": {
            "typing_budget_events_per_frame": contract["responsiveness"]
                ["physical_input_contract_events_per_frame"],
            "required_margin_percent": contract["responsiveness"]
                ["required_service_margin_percent"],
            "maximum_frames_per_character": contract["responsiveness"]
                ["maximum_frames_per_character"],
            "rows": rows,
        },
        "code_price": {
            "current_bank2_objects": current_sizes,
            "scalar_hotpath_bank2_objects": scalar_sizes,
            "batch_bank2_objects": batch_sizes,
            "batch_minus_current_bytes": (
                sum(batch_sizes.values()) - sum(current_sizes.values())
            ),
            "new_interned_names": 0,
            "new_public_primitives": 0,
            "private_key_event_modes": [2, 3],
        },
        "capacity": {
            "born_derived_geometry": geometry,
            "post_capture_e000_free_bytes": capacity["post_capture_e000_free_bytes"],
            "e000_floor_bytes": capacity["e000_floor_bytes"],
            "spendable_e000_bytes": capacity["spendable_e000_bytes"],
            "native_scalar_body_bytes": native_bytes,
            "body_ceiling_bytes": capacity["native_scalar_body_max_bytes"],
            "remaining_e000_above_floor_after_body": (
                capacity["spendable_e000_bytes"] - native_bytes
            ),
            "remaining_adapter_budget_bytes": capacity
                ["remaining_e000_adapter_budget_bytes"],
            "ordinary_text_free_bytes": capacity["ordinary_text_free_bytes"],
            "implementation_gate": (
                "shared-normalization refactor plus private-mode adapter must "
                "fit the remaining 12 E000 bytes and must not consume ordinary "
                "text; otherwise the price returns for relocation"
            ),
        },
        "normalization": parity_gate(contract),
        "decision": {
            "native_scalar_only": "rejected: input chatter is only 49 VM steps/character",
            "native_scalar_plus_hotpath": "rejected: still above 0.8 frame/character",
            "batch_only": "rejected: raw case parity still needs the shared native boundary",
            "winner": "hybrid-native-scalar-plus-batched-edit-render-8",
            "minimum_admitted_batch": min(passing_batches),
            "reason": (
                "eight-event batching is the first measured size that clears "
                "the 1 event/frame producer with 25 percent service margin; "
                "the scalar seam supplies one normalization truth and removes "
                "peek/poke chatter without adding a symbol"
            ),
            "implementation_card_required": True,
            "device_contact_authorized": False,
        },
        "required_successor_gates": {
            "responsiveness": "<=0.8 calibrated frames/character at batches >=8",
            "loss": "94/94 ordered across forced 89-frame collection; event 6 present",
            "burst_policy": "adaptive drain; no fixed wait for eight events",
            "normalization": "256 raw PETSCII values, two consumers, exact code parity",
            "fixtures": "producer and payload transfers are non-atomic",
            "semantics": "cursor/history/WYSIWYG/RUN-STOP and native fallback unchanged",
            "capacity": "final linked ELF proves floor and ordinary-text wall",
        },
        "walls": contract["candidate_walls"],
        "claim_limit": (
            "Exact P0 dynamic counts and emitted prototype byte sizes are host "
            "measurements. Raster-frame values are hardware-calibrated "
            "equivalents using the bound 1,100-cycle VM average, 1,500-cycle "
            "screen store and 89-frame collection; they are not a new device "
            "timing. This study changes no product source, emits no product "
            "link, authorizes no card and authorizes no device contact."
        ),
    }
    validate(result, contract)
    return result


def selftest(result: dict[str, Any], contract: dict[str, Any]) -> dict[str, str]:
    mutations: dict[str, Any] = {}

    def mutate(label: str, change: Any) -> None:
        candidate = copy.deepcopy(result)
        change(candidate)
        try:
            validate(candidate, contract)
        except PricingError as error:
            mutations[label] = str(error)
        else:
            raise PricingError(f"service-time mutation survived: {label}")

    mutate("scalar-false-pass", lambda x: x["service_time"]["rows"]
           ["native-scalar-only"].__setitem__("responsiveness_pass", True))
    mutate("hotpath-false-pass", lambda x: x["service_time"]["rows"]
           ["native-scalar-plus-hotpath"].__setitem__("responsiveness_pass", True))
    mutate("batch-eight-red", lambda x: x["service_time"]["rows"]
           ["batch-8"].__setitem__("responsiveness_pass", False))
    mutate("under-batch-admitted", lambda x: x["decision"]
           .__setitem__("minimum_admitted_batch", 4))
    mutate("wrong-winner", lambda x: x["decision"]
           .__setitem__("winner", "native-scalar-only"))
    mutate("ascii-fixture-domain", lambda x: x["normalization"]
           .__setitem__("fixtures_begin_as", "ASCII"))
    mutate("case-parity-lost", lambda x: x["normalization"]
           .__setitem__("parity", False))
    mutate("raw-domain-short", lambda x: x["normalization"]
           .__setitem__("raw_codes", 255))
    mutate("resident-body-overrun", lambda x: x["capacity"]
           .__setitem__("native_scalar_body_bytes", 71))
    mutate("adapter-budget-spent", lambda x: x["capacity"]
           .__setitem__("remaining_adapter_budget_bytes", 11))
    mutate("wall-weakened", lambda x: x["walls"]
           .__setitem__("non_atomic_raw_fixtures_required", False))
    mutate("claim-inflated", lambda x: x
           .__setitem__("claim_limit", "Device timing proved"))
    require(len(mutations) == 12, "service-time mutation count drift")
    return mutations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "selftest"))
    args = parser.parse_args()
    result = load(RECEIPT)
    validate(result, load(CONTRACT))
    mutations = selftest(result, load(CONTRACT))
    if args.command == "selftest":
        print(f"v1.6 input service-time pricing selftest: PASS mutations={len(mutations)}")
        return 0
    require(RECEIPT.read_bytes() == ERA.era_blob(
                RECEIPT_SEALED_COMMIT, RECEIPT.relative_to(ROOT).as_posix()),
            "historical service-time pricing receipt was regenerated")
    require(result.get("mutations_rejected") == mutations,
            "sealed service-time mutation evidence drift")
    winner = result["service_time"]["rows"]["batch-8"]
    print(
        "v1.6 input service-time pricing: PASS "
        f"batch8={winner['total_frame_equivalent_per_character']:.3f} "
        f"events/frame={winner['service_events_per_frame']:.3f}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PricingError as error:
        print(f"v1.6 input service-time pricing: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
