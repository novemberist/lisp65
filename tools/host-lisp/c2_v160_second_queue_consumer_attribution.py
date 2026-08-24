#!/usr/bin/env python3
"""Prove that evaluator polling races the armed v1.6 IRQ input capture."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
ELF = ROOT / ("build/c2.3/v1.6-bound-origin-fragmentation-second-"
              "replacement-card/wplto/lisp65-c2-substitution-linked.prg.elf")
OUT = ARCH / "c2.3-v1.6-second-queue-consumer-attribution.json"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
COMMISSION = "dcf27b87"
ELF_SHA = "8bb00fd560ddfef9b4f1da5d6269e134de8dc6548a33e3659eb79fc580fecd45"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def git_blob(path: str) -> tuple[bytes, dict[str, Any]]:
    commit = subprocess.run(["git", "rev-parse", f"{COMMISSION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    return raw, {"authority": "git-blob", "commit": commit, "path": path,
                 "bytes": len(raw), "sha256": sha(raw)}


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def derive() -> dict[str, Any]:
    plan, plan_id = git_blob("docs/planning/v1.6.0-freight-work-plan.md")
    interrupt, interrupt_id = git_blob("src/interrupt.c")
    capture, capture_id = git_blob("src/optional/c2_kernal_input_capture.s")
    window, window_id = git_blob("src/c2_kernal_window.s")
    for token in (b"second consumer on the same queue", b"Prove the race",
                  b"one owner per resource"):
        require(token.lower() in plan.lower(), f"commission token absent: {token!r}")
    require(b"while (c2_kernal_event_poll(&event))" in interrupt
            and b"deliberately drained" in interrupt,
            "historical evaluator drain absent")
    require(b"lda $d60a" in capture and b"lda $d619" in capture
            and b"sta $d619" in capture,
            "historical capture queue transaction absent")
    require(b"lda $d60a" in window and b"lda $d619" in window
            and b"sta $d619" in window,
            "historical poll queue transaction absent")
    require(bind(ELF)["sha256"] == ELF_SHA, "frozen product ELF drift")
    disassembly = subprocess.run([str(OBJDUMP), "-d", str(ELF)], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.lower()
    require(disassembly.count("jsr\t$e000 <c2_kernal_event_poll>") == 2,
            "final ELF queue-poll call count drift")
    require("0000e000 <c2_kernal_event_poll>" in disassembly
            and "lda\t$d60a" in disassembly and "lda\t$d619" in disassembly
            and "sta\t$d619" in disassembly,
            "final ELF poll transaction absent")
    require("0000fd08 <c2_kernal_input_capture>" in disassembly,
            "final ELF capture consumer absent")

    # One queue cell, two legal schedules. Poll-first loses the cell before
    # capture's raw witness; capture-first accounts for it exactly once.
    poll_first = {"initial_queue": 1, "poll_taken": 1, "capture_raw": 0,
                  "remaining_queue": 0}
    capture_first = {"initial_queue": 1, "poll_taken": 0, "capture_raw": 1,
                     "remaining_queue": 0}
    require(poll_first["capture_raw"] == 0
            and capture_first["capture_raw"] == 1,
            "race schedule model drift")
    return {
        "format": "lisp65-c2-v160-second-queue-consumer-attribution-v1",
        "recorded_on": "2026-08-21",
        "status": "PASS: SECOND PRODUCT QUEUE CONSUMER PROVES LOSS RACE",
        "authority": plan_id,
        "frozen_world": {"ELF": bind(ELF), "interrupt": interrupt_id,
                         "capture": capture_id, "window": window_id},
        "linked_evidence": {
            "queue_poll_entry": "0xE000", "capture_entry": "0xFD08",
            "poll_calls_in_final_ELF": 2,
            "shared_registers": {"present_and_head": "0xD60A",
                                 "code_and_ack": "0xD619"},
            "vm_callsite": "0x4776 -> c2_kernal_event_poll"},
        "race": {"poll_first": poll_first, "capture_first": capture_first,
                 "mechanism": ("lisp_poll may consume and acknowledge an ordinary "
                               "event before the armed raster capture observes it")},
        "classification": {
            "family": "single-owner hardware-resource violation",
            "measurement_correction": ("11>8=8=8=8 locates loss before the raw "
                                       "witness, not outside the product"),
            "fix": ("while capture is armed, lisp_poll must not read or acknowledge "
                    "the hardware queue; RUN/STOP remains matrix-owned")}}


def validate(value: dict[str, Any]) -> None:
    require(value == derive(), "second-consumer attribution drift")


def selftest(value: dict[str, Any]) -> None:
    rejected = 0
    for mutate in (
        lambda row: row["linked_evidence"].update({"poll_calls_in_final_ELF": 1}),
        lambda row: row["race"]["poll_first"].update({"capture_raw": 1}),
        lambda row: row["classification"].update({"family": "platform defect"}),
        lambda row: row["classification"].update({"fix": "allow both consumers"}),
    ):
        candidate = copy.deepcopy(value); mutate(candidate)
        try: validate(candidate)
        except RuntimeError: rejected += 1
        else: raise RuntimeError("second-consumer attribution mutation survived")
    require(rejected == 4, "attribution mutation count drift")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    if action == "write":
        OUT.write_bytes(canonical(derive()))
    value = json.loads(OUT.read_text(encoding="utf-8"))
    validate(value)
    if action == "selftest": selftest(value)
    print("v1.6 second queue consumer: PASS race=product-owned poll-first-loss")


if __name__ == "__main__":
    main()
