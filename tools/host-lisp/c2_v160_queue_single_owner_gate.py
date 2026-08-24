#!/usr/bin/env python3
"""Enforce single ownership of the hardware key queue while capture is armed."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/interrupt.c"
ATTRIBUTION = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                     "c2.3-v1.6-second-queue-consumer-attribution.json")
CANDIDATE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-recovery-sanitization-adapter-qualification-resume.json")
OUT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
             "c2.3-v1.6-queue-single-owner-gate-receipt.json")


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def function_body(text: str, name: str) -> str:
    start = text.index(f"void {name}(void) {{")
    depth = 0
    opened = False
    for offset, char in enumerate(text[start:]):
        if char == "{": depth += 1; opened = True
        elif char == "}":
            depth -= 1
            if opened and depth == 0: return text[start:start + offset + 1]
    raise RuntimeError(f"unterminated function: {name}")


def simulate(*, armed: bool, break_pending: bool, queue_present: bool) -> dict[str, Any]:
    queue_reads = 0
    queue_acks = 0
    aborted = False
    if armed:
        if break_pending: aborted = True
    elif queue_present:
        queue_reads = 1; queue_acks = 1
    return {"armed": armed, "break_pending": break_pending,
            "queue_present": queue_present, "queue_reads": queue_reads,
            "queue_acks": queue_acks, "run_stop_abort": aborted}


def derive(source: str | None = None) -> dict[str, Any]:
    text = SOURCE.read_text(encoding="utf-8") if source is None else source
    body = function_body(text, "lisp_poll")
    guard = "if (C2K_INPUT_RING_TAIL != C2K_INPUT_RING_CLOSED)"
    pending = "if (C2K_BREAK_PENDING)"
    call = "while (c2_kernal_event_poll(&event))"
    require(body.index(guard) < body.index(call),
            "capture-owner guard must precede hardware queue consumer")
    guarded = body[body.index(guard):body.index(call)]
    require(pending in guarded and "C2K_BREAK_PENDING = 0u;" in guarded
            and "lisp_abort_static(LISP65_ERR_STOPPED" in guarded
            and "return;" in guarded,
            "armed path must preserve matrix RUN/STOP and return before queue poll")
    require("(*(volatile uint8_t *)0xff8d)" in text
            and "(*(volatile uint8_t *)0xff8a)" in text
            and "C2K_INPUT_RING_CLOSED 0xffu" in text,
            "single-owner state authority drift")
    armed_key = simulate(armed=True, break_pending=False, queue_present=True)
    armed_stop = simulate(armed=True, break_pending=True, queue_present=True)
    closed_key = simulate(armed=False, break_pending=False, queue_present=True)
    require(armed_key["queue_reads"] == armed_key["queue_acks"] == 0,
            "armed evaluator poll consumed ordinary event")
    require(armed_stop["run_stop_abort"] is True
            and armed_stop["queue_reads"] == 0,
            "armed RUN/STOP lost independent matrix authority")
    require(closed_key["queue_reads"] == closed_key["queue_acks"] == 1,
            "closed-capture legacy drain changed")
    attribution = json.loads(ATTRIBUTION.read_text(encoding="utf-8"))
    require(attribution["status"] ==
            "PASS: SECOND PRODUCT QUEUE CONSUMER PROVES LOSS RACE",
            "queue race attribution absent")
    return {
        "format": "lisp65-c2-v160-queue-single-owner-gate-v1",
        "recorded_on": "2026-08-21",
        "status": "PASS: ARMED CAPTURE IS SOLE HARDWARE QUEUE OWNER",
        "inputs": {"source": bind(SOURCE), "attribution": bind(ATTRIBUTION)},
        "contract": {
            "capture_armed": "lisp_poll performs zero D60A/D619 reads or acks",
            "run_stop": "matrix-pending latch remains evaluator abort authority",
            "capture_closed": "historic queue drain remains available"},
        "model": {"armed_ordinary": armed_key, "armed_run_stop": armed_stop,
                  "closed_ordinary": closed_key}}


def validate(value: dict[str, Any], source: str | None = None) -> None:
    require(value == derive(source), "queue single-owner receipt drift")


def current_candidate_reproof() -> dict[str, Any]:
    # Import lazily: the linked gate imports this source gate for its preflight
    # projection.  The receipt, unlike that source projection, also owes a
    # fresh proof against the accepted current final-world candidate.
    import c2_v160_queue_single_owner_card as LINKED

    resume = json.loads(CANDIDATE_RECEIPT.read_text(encoding="utf-8"))
    before = resume["frozen_pair_before"]["ELF"]
    after = resume["frozen_pair_after"]["ELF"]
    require(resume["status"] ==
            "PASS: V1.6 RECOVERY SANITIZATION CLOSED READ-ONLY"
            and before == after,
            "queue-owner current-candidate authority drift")
    elf = ROOT / after["path"]
    require(bind(elf) == after,
            "queue-owner current-candidate ELF identity drift")
    linked = LINKED.linked_owner_gate(elf)
    require(linked["queue_poll_calls"] == 2
            and linked["dominated_calls"] == 1
            and [row["owner"] for row in linked["consumers"]] ==
                ["vm_run_inner", "lisp_input_event"],
            "queue-owner current-candidate linked claim drift")
    return {"authority": bind(CANDIDATE_RECEIPT), "ELF": after,
            "linked_single_owner": linked}


def receipt() -> dict[str, Any]:
    value = derive()
    value["current_candidate_reproof"] = current_candidate_reproof()
    return value


def validate_receipt(value: dict[str, Any]) -> None:
    require(value == receipt(), "queue single-owner receipt drift")


def selftest(value: dict[str, Any]) -> None:
    source = SOURCE.read_text(encoding="utf-8")
    mutations = (
        source.replace("if (C2K_INPUT_RING_TAIL != C2K_INPUT_RING_CLOSED) {",
                       "if (0) {", 1),
        source.replace("if (C2K_BREAK_PENDING) {", "if (0) {", 1),
        source.replace("C2K_BREAK_PENDING = 0u;", "/* no acknowledge */", 1),
        source.replace("        return;\n    }\n    /* Evaluator polling", "    }\n    /* Evaluator polling", 1),
    )
    rejected = 0
    for mutant in mutations:
        try: derive(mutant)
        except (RuntimeError, ValueError): rejected += 1
        else: raise RuntimeError("queue single-owner mutation survived")
    require(rejected == 4, "queue single-owner mutation count drift")
    receipt_mutations = (
        lambda row: row["current_candidate_reproof"]["ELF"].update(
            sha256="0" * 64),
        lambda row: row["current_candidate_reproof"]["linked_single_owner"]
            ["consumers"][0].update(armed_state_before=False),
    )
    receipt_rejected = 0
    for mutate in receipt_mutations:
        trial = copy.deepcopy(value); mutate(trial)
        try: validate_receipt(trial)
        except (RuntimeError, ValueError): receipt_rejected += 1
        else: raise RuntimeError("queue single-owner candidate mutation survived")
    require(receipt_rejected == 2,
            "queue single-owner candidate mutation count drift")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    if action == "write": OUT.write_bytes(canonical(receipt()))
    value = json.loads(OUT.read_text(encoding="utf-8"))
    validate_receipt(value)
    if action == "selftest": selftest(value)
    print("v1.6 queue single owner: PASS armed-poll queue-reads=0 "
          "run-stop=matrix final-callers=2 dominated=1")


if __name__ == "__main__":
    main()
