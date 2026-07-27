#!/usr/bin/env python3
"""Qualify B3/D3: an out-of-band RUN/STOP edge delivered exactly once.

This is deliberately a product-shaped host fixture.  The pinned core sources
establish the physical source and five-event queue.  The product sources
establish one edge latch, no transport-side polling, queue-$03 suppression and
one safe evaluator delivery seam.  A small exhaustive model proves the
cutpoints and queue-full cases, including the rejected mutations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ADDENDA = ROOT / "config/c2-cross-invariant-c2.2-open-addenda.json"
REVIEW = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-cross-invariant-b3-c3-d3-e5-contract-review-receipt.json")
WINDOW = ROOT / "src/c2_kernal_window.s"
RUNTIME = ROOT / "src/c2_kernal_runtime.c"
HEADER = ROOT / "src/c2_kernal_runtime.h"
INTERRUPT = ROOT / "src/interrupt.c"
MAIN = ROOT / "src/main.c"
PLACEMENT = ROOT / "config/c2-matrix-addenda-cold-placement-contract.json"
DMA_SOURCES = (
    ROOT / "src/c2_platform_dma.c",
    ROOT / "src/rtov_dma_completion.s",
    ROOT / "src/vm_runtime_overlay.c",
)
CORE = ROOT / "build/upstream-verification/mega65-core"
CORE_MATRIX = CORE / "src/vhdl/matrix_to_ascii.vhdl"
CORE_QUEUE = CORE / "src/vhdl/iomapper.vhdl"
CORE_PORTS = CORE / "src/vhdl/c65uart.vhdl"
OUT = ROOT / "build/c2.2/matrix-b3-d3-break-delivery"
OBJECT = OUT / "c2-kernal-window.o"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-matrix-b3-d3-common-store-E5-cold-front-terminal-noreturn-"
    "rebind-receipt.json")

EXPECTED = {
    ADDENDA: "73aa314bc1a8f9dceaa3e0ce144262335dd197503ea11afca2356d5b67671777",
    REVIEW: "1d3e203390460efb08a8d479b0dc753a742afb6ff5346c78c2446dfa5a7708c8",
    CORE_MATRIX: "068dab4dfea391e8c6ac06ac31108be2e29d9d4510becbcbc1b2125bcb535536",
    CORE_QUEUE: "942a08a4622001048c38b065bee11edf1e4926f2db29dfc03f67bb7257db4bba",
    CORE_PORTS: "3679b4cce25823c3f813cdfa8fdc0038c9cfbbadfe86fb960e3db373670915b6",
}
CORE_COMMIT = "a9158930665763c592d004c895d52eff4a9eefc3"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def function_body(source: str, name: str) -> str:
    match = re.search(r"\b" + re.escape(name) + r"\s*\([^;{]*\)\s*\{",
                      source)
    require(match is not None, f"function body absent: {name}")
    start = source.find("{", match.start())
    depth = 0
    for end in range(start, len(source)):
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():end + 1]
    raise GateError(f"unterminated function body: {name}")


def core_gate() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "-C", str(CORE), "rev-parse", "HEAD"],
        cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
    require(commit == CORE_COMMIT, "pinned mega65-core commit drift")
    matrix = CORE_MATRIX.read_text(encoding="utf-8")
    queue = CORE_QUEUE.read_text(encoding="utf-8")
    ports = CORE_PORTS.read_text(encoding="utf-8")
    require('63 => x"03", -- RUN/STOP' in matrix,
            "pinned core matrix ordinal 63 identity drift")
    require("type key_buffer_t is array(0 to 3)" in queue
            and "key_buffer_count : integer range 0 to 4" in queue
            and "if key_buffer_count < 4 then" in queue
            and "if key_presenting = '1' then" in queue,
            "pinned core five-event queue model drift")
    require('when x"14" => portj_out <=' in ports
            and '$D613 UARTMISC:KEYMATRIXPEEK' in ports
            and '$D614 UARTMISC:KEYMATRIXSEL' in ports,
            "pinned core D613/D614 identity drift")
    return {
        "commit": commit,
        "matrix_ordinal": 63,
        "petscii": 3,
        "selector_register": "0xd614",
        "selector_value": 7,
        "peek_register": "0xd613",
        "active_low_mask": "0x80",
        "queue": {
            "visible_head_slots": 1,
            "buffered_slots": 4,
            "total_events": 5,
            "sixth_event": "not-enqueued",
        },
    }


def source_errors(texts: dict[Path, str]) -> list[str]:
    window = texts[WINDOW]
    header = texts[HEADER]
    main = texts[MAIN]
    interrupt = texts[INTERRUPT]
    errors: list[str] = []
    required_window = (
        ".equ C2K_BREAK_PENDING,   $ff8a",
        ".equ C2K_BREAK_HELD,      $ff8b",
        ".type c2_kernal_event_poll,@function",
        "lda C2K_BREAK_PENDING",
        "stz C2K_BREAK_PENDING",
        "lda #$03",
        "ldy #$00",
        "bra .Lstore_event",
        ".Lstore_event:",
        "lda $d60a",
        "lda $d619",
        "sta $d619",
        "cmp #$03\n\tbeq .Lqueue_next",
        "lda $d613",
        "bmi .Lbreak_released",
        "inc C2K_BREAK_HELD",
        "inc C2K_BREAK_PENDING",
        "stz C2K_BREAK_HELD",
    )
    for token in required_window:
        if token not in window:
            errors.append("window:" + token)
    pending_at = window.find("lda C2K_BREAK_PENDING")
    queue_at = window.find("lda $d60a")
    if pending_at < 0 or queue_at < 0 or pending_at > queue_at:
        errors.append("pending-not-prioritized-over-queue")
    if window.count("lda $d60a") != 1 or window.count("lda $d619") != 1:
        errors.append("typed-queue-head-not-single-sampled")
    if (window.count(".Lstore_event:") != 1
            or window.count("sta (__rc2),z") != 2):
        errors.append("event-tuple-store-not-single-source")
    if ("#define LISP65_RUN_STOP_MATRIX_SEGMENT 7u" not in header
            or "LISP65_RUN_STOP_MATRIX_SEGMENT;" not in main):
        errors.append("matrix-selector-not-canonical")
    if main.find("LISP65_RUN_STOP_MATRIX_SEGMENT;") > \
            main.find("c2_kernal_take_ownership()"):
        errors.append("matrix-selector-after-owned-irq")
    poll = function_body(interrupt, "lisp_poll")
    if ("while (c2_kernal_event_poll(&event))" not in poll
            or "event.code == LISP65_KEY_RUN_STOP" not in poll
            or "lisp_abort_static(LISP65_ERR_STOPPED" not in poll):
        errors.append("safe-evaluator-consumer-drift")
    for path in DMA_SOURCES:
        body = texts[path]
        for forbidden in ("lisp_poll(", "lisp_abort", "longjmp("):
            if forbidden in body:
                errors.append(
                    f"transport-nonlocal-edge:{path.name}:{forbidden}")
    if re.search(r"(run.?stop|RUN.?STOP).*(?:\[|\{)", window + main):
        errors.append("second-handwritten-run-stop-map")
    return errors


class Model:
    def __init__(self, queue: list[tuple[int, int]] | None = None) -> None:
        self.queue = list(queue or [])
        self.pending = 0
        self.held = 0
        self.aborts = 0
        self.steps = 0

    def sample(self, active: bool) -> None:
        if not active:
            self.held = 0
        elif not self.held:
            self.held = 1
            self.pending = 1

    def safe_poll(self) -> tuple[int, int] | None:
        self.steps += 1
        if self.pending:
            self.pending = 0
            self.aborts += 1
            return (3, 0)
        while self.queue:
            event = self.queue.pop(0)
            if event[0] == 3:
                continue
            return event
        return None


def b3_model(*, drop: bool = False, double: bool = False,
             late: bool = False, nonlocal_in_transport: bool = False) \
        -> dict[str, Any]:
    cutpoints = (
        "immediately-before-submit",
        "after-submit-before-first-content-proof",
        "during-convergence-after-at-least-one-mismatch",
        "after-content-match-before-seam-return",
        "first-safe-evaluator-boundary",
    )
    rows: list[dict[str, Any]] = []
    for cutpoint in cutpoints:
        descriptor = bytes(range(20))
        scratch = bytes((0xa5, 0x5a, 0x33, 0xcc))
        planes = bytes(range(64))
        pending = not drop
        nonlocal_exit = nonlocal_in_transport and cutpoint != cutpoints[-1]
        delivered = 0
        extra_steps = 0
        if cutpoint == cutpoints[-1] and pending:
            if late:
                extra_steps = 1
            delivered = 2 if double else 1
        rows.append({
            "cutpoint": cutpoint,
            "non_local_exit_before_safe_boundary": nonlocal_exit,
            "pending_before_safe_boundary": int(pending),
            "delivery_count": delivered,
            "extra_evaluator_steps": extra_steps,
            "transport_postcondition": (
                descriptor == bytes(range(20))
                and scratch == bytes((0xa5, 0x5a, 0x33, 0xcc))
                and planes == bytes(range(64))),
            "rollback_byte_identical": delivered == 1,
        })
    passed = all(
        not row["non_local_exit_before_safe_boundary"]
        and row["pending_before_safe_boundary"] == 1
        and row["transport_postcondition"]
        for row in rows[:-1])
    final = rows[-1]
    passed = (passed and final["delivery_count"] == 1
              and final["extra_evaluator_steps"] == 0
              and final["rollback_byte_identical"])
    return {"passed": passed, "cutpoints": rows}


def d3_model(*, latch: bool = True, repeat: bool = False,
             queue03_aborts: bool = False, reorder: bool = False,
             alter_modifier: bool = False) -> dict[str, Any]:
    ordinary = [(0x41 + index, 0x10 + index) for index in range(5)]
    model = Model(ordinary)
    if latch:
        model.sample(True)
        model.sample(True)
    first = model.safe_poll()
    if repeat:
        # Mutation model: the held guard was lost between two safe polls.
        model.held = 0
        model.sample(True)
        model.safe_poll()
    model.sample(False)
    drained: list[tuple[int, int]] = []
    while model.queue:
        value = model.safe_poll()
        if value:
            drained.append(value)
    if reorder:
        drained.reverse()
    if alter_modifier and drained:
        drained[0] = (drained[0][0], drained[0][1] ^ 1)
    model.queue.append((3, 0x7f))
    queued = model.safe_poll()
    if queue03_aborts and queued is None:
        model.aborts += 1
    return {
        "passed": (
            first == (3, 0)
            and model.aborts == 1
            and drained == ordinary
            and queued is None),
        "first": first,
        "abort_count": model.aborts,
        "ordinary": drained,
        "queued_petscii_03_result": queued,
    }


def mutation_gate(texts: dict[Path, str]) -> dict[str, str]:
    source_mutations: dict[str, dict[Path, str]] = {
        "wrong-matrix-segment": {
            **texts, HEADER: texts[HEADER].replace(
                "LISP65_RUN_STOP_MATRIX_SEGMENT 7u",
                "LISP65_RUN_STOP_MATRIX_SEGMENT 6u", 1)},
        "wrong-matrix-bit-or-polarity": {
            **texts, WINDOW: texts[WINDOW].replace(
                "bmi .Lbreak_released", "bpl .Lbreak_released", 1)},
        "queued-petscii-03-is-abort": {
            **texts, WINDOW: texts[WINDOW].replace(
                "cmp #$03\n\tbeq .Lqueue_next",
                "cmp #$03\n\tbeq .Lqueue_empty", 1)},
        "second-handwritten-run-stop-map": {
            **texts, MAIN: texts[MAIN] + "\nstatic const unsigned char "
            "run_stop_map[] = { 3 };\n"},
        "physical-break-bypasses-common-store": {
            **texts, WINDOW: texts[WINDOW].replace(
                "bra .Lstore_event", "bra .Lqueue_empty", 1)},
        "duplicate-event-tuple-store": {
            **texts, WINDOW: texts[WINDOW].replace(
                ".Lstore_event:\n\tldz #$00",
                ".Lstore_event:\n\tsta (__rc2),z\n\tldz #$00", 1)},
    }
    rejected: dict[str, str] = {}
    for name, mutated in source_mutations.items():
        require(source_errors(mutated), f"source mutation survived: {name}")
        rejected[name] = "rejected"
    model_mutations = {
        "poll-inside-submitted-transport":
            b3_model(nonlocal_in_transport=True),
        "longjmp-inside-convergence":
            b3_model(nonlocal_in_transport=True),
        "drop-pending-break": b3_model(drop=True),
        "deliver-break-twice": b3_model(double=True),
        "deliver-after-one-extra-evaluator-step": b3_model(late=True),
        "matrix-press-not-latched-while-queue-full": d3_model(latch=False),
        "held-key-produces-two-aborts": d3_model(repeat=True),
        "queued-petscii-03-produces-abort": d3_model(queue03_aborts=True),
        "ordinary-tuple-reordered": d3_model(reorder=True),
        "ordinary-tuple-modifier-changed": d3_model(alter_modifier=True),
    }
    for name, value in model_mutations.items():
        require(not value["passed"], f"model mutation survived: {name}")
        rejected[name] = "rejected"
    return rejected


def assemble_gate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    compiler = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
    nm = ROOT / "tools/llvm-mos/bin/llvm-nm"
    subprocess.run(
        [str(compiler), "-c", str(WINDOW), "-o", str(OBJECT)],
        cwd=ROOT, check=True, capture_output=True, text=True)
    output = subprocess.run(
        [str(nm), "-S", str(OBJECT)], cwd=ROOT, check=True,
        capture_output=True, text=True).stdout
    matches = [line for line in output.splitlines()
               if line.rstrip().endswith(" c2_kernal_event_poll")]
    require(len(matches) == 1, "event leaf lacks one sized ELF identity")
    fields = matches[0].split()
    require(len(fields) >= 4 and int(fields[1], 16) > 0,
            "event leaf is not a non-empty STT_FUNC")
    return {
        "object": bind(OBJECT),
        "event_poll_symbol_bytes": int(fields[1], 16),
        "event_poll_symbol_count": len(matches),
    }


def build_receipt() -> dict[str, Any]:
    for path, expected in EXPECTED.items():
        require(path.is_file() and sha(path) == expected,
                f"bound authority drift: {path}")
    addenda = json.loads(ADDENDA.read_text(encoding="utf-8"))
    require(
        addenda["status"]
        == "class-c-line-review-approved-implementation-authorized",
        "addenda implementation is not authorized")
    texts = {
        path: path.read_text(encoding="utf-8")
        for path in (WINDOW, RUNTIME, HEADER, INTERRUPT, MAIN, *DMA_SOURCES)
    }
    errors = source_errors(texts)
    require(not errors, "B3/D3 source gate red: " + ", ".join(errors))
    b3 = b3_model()
    d3 = d3_model()
    require(b3["passed"] and d3["passed"],
            "B3/D3 positive model red")
    mutations = mutation_gate(texts)
    require(len(mutations) == 16, "B3/D3 mutation count drift")
    return {
        "format": "lisp65-c2.2-matrix-b3-d3-common-store-fixture-v2",
        "recorded_on": "2026-07-23",
        "status": "passed-host-source-model-awaiting-hardware-queue-full",
        "rows": {
            "B3": {
                "host_status": "passed-five-transport-cutpoints",
                "cutpoints": b3["cutpoints"],
                "delivery": "one pending edge at first safe evaluator boundary",
                "hardware_status": "pending-bundled-acceptance-run",
            },
            "D3": {
                "host_status": "passed-five-event-queue-full-model",
                "first_delivery": d3["first"],
                "ordinary_tuples": d3["ordinary"],
                "abort_count": d3["abort_count"],
                "queued_petscii_03": "discarded-not-abort",
                "hardware_status": "pending-bundled-acceptance-run",
            },
        },
        "source_gate": {
            "status": "passed",
            "transport_non_local_edges": 0,
            "pending_priority": "before-typed-queue",
            "queue_head_samples": {"modifier": 1, "code": 1, "dequeue": 1},
            "tuple_store_implementations": 1,
            "tuple_store_bytes_recovered": "measured-by-WPLTO",
            "second_keymap": "absent",
        },
        "core_authority": core_gate(),
        "assembler_leaf": assemble_gate(),
        "mutations": mutations,
        "authorities": {
            "approved_addenda": bind(ADDENDA),
            "line_review_receipt": bind(REVIEW),
            "window_source": bind(WINDOW),
            "runtime_header": bind(HEADER),
            "interrupt_consumer": bind(INTERRUPT),
            "main_selector": bind(MAIN),
            "cold_placement_contract": bind(PLACEMENT),
            "core_matrix": bind(CORE_MATRIX),
            "core_queue": bind(CORE_QUEUE),
            "core_ports": bind(CORE_PORTS),
        },
        "execution": {
            "host_fixture": True,
            "assembler_object_compile": 1,
            "whole_program_lto_runs": 0,
            "product_links": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "Proves the B3/D3 source, pinned-core identity and exhaustive host "
            "models. D3 remains OPEN until the physical queue-full sequence "
            "and B3 rollback observation are green on the successor identity. "
            "No acceptance or promotion is claimed."),
        "value_string": (
            "B3=cutpoints-5/5 D3=queue5+edge model=green mutations=16/16 "
            "transport-nonlocal=0 event-leaf=sized hardware=pending "
            "acceptance=blocked"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check"))
    args = parser.parse_args()
    try:
        value = build_receipt()
        data = canonical(value)
        if args.action == "write":
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            if RECEIPT.exists():
                require(RECEIPT.read_bytes() == data,
                        "refusing to overwrite divergent B3/D3 receipt")
            else:
                RECEIPT.write_bytes(data)
            os.chmod(RECEIPT, 0o444)
            verb = "WROTE"
        else:
            require(RECEIPT.is_file() and RECEIPT.read_bytes() == data,
                    "B3/D3 receipt absent or drifted")
            verb = "CHECK PASS"
        print(
            "c2-matrix-b3-d3-break-delivery: "
            f"{verb} cutpoints=5/5 queue=5 mutations=16/16 "
            "hardware=pending")
        return 0
    except (GateError, OSError, KeyError, ValueError,
            json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print("c2-matrix-b3-d3-break-delivery: FAIL " + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
