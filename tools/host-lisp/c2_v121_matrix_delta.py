#!/usr/bin/env python3
"""Bind the v1.2.1 Link-77 cross-invariant delta review.

This is deliberately a delta review, not a replacement full-matrix proof.
Rows in the Link-77 change closure are re-derived against current artifacts.
Every other row retains its terminal C2.2 disposition with an explicit
not-re-derived marker, so no old green is silently presented as fresh.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

PLAN = ROOT / "docs/planning/v1.2.1-release-plan.md"
MATRIX = ROOT / "docs/planning/c2.2-cross-invariant-matrix.md"
BASELINE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-cross-invariant-full-matrix-link57-review-receipt.json")
TERMINAL = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-cross-invariant-C1-terminal-disposition-link66-receipt.json")
LINK77 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link77-random-while-structural-receipt.json")
HARDWARE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link77-gc-discriminator-bundled-hardware-receipt.json")
WHILE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v2-while-four-view-receipt.json")
FASTPATH = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-require-idempotence-fastpath-receipt.json")
UNWIND = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-nested-append-unwind-contract-probe-receipt.json")
B3_D3 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-matrix-b3-d3-common-store-E5-cold-front-terminal-"
    "noreturn-rebind-receipt.json")
ADDENDA_REVIEW = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-cross-invariant-b3-c3-d3-e5-contract-review-receipt.json")
IRQ = ROOT / (
    "build/post-promotion/link77-random-while/receipts/"
    "interrupt-ownership-final-replay.json")
ELF = ROOT / (
    "build/post-promotion/link77-random-while/final/"
    "lisp65-c2-substitution-linked.prg.elf")
INTERRUPT_SOURCE = ROOT / "src/interrupt.c"
WINDOW_SOURCE = ROOT / "src/c2_kernal_window.s"
RUNTIME_SOURCE = ROOT / "src/c2_kernal_runtime.c"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.1-link77-cross-invariant-delta-receipt.json")
LOG_ROOT = ROOT / "build/c2.2/v1.2.1/a2"
FRESH_IRQ = LOG_ROOT / "interrupt-ownership-fresh.json"

ORDER = (
    "A1", "A2", "A3", "A4",
    "B1", "B2", "B3", "B4", "B5",
    "C1", "C2", "C3", "C4", "C5",
    "D1", "D2", "D3",
    "E1", "E2", "E3", "E4", "E5",
    "F1", "F2", "F3",
)
REDERIVED = frozenset(("A3", "A4", "B1", "B2", "C5",
                       "D1", "D2", "D3", "E1"))
TERMINAL_STATUS = {
    "A1": "PROVEN",
    "A2": "PROVEN",
    "A3": "EXCLUDED",
    "A4": "EXCLUDED",
    "B1": "PROVEN",
    "B2": "PROVEN",
    "B3": "PROVEN",
    "B4": "PROVEN",
    "B5": "PROVEN",
    "C1": "DOCUMENTED-C2.3-DEFERRED",
    "C2": "PROVEN",
    "C3": "PROVEN",
    "C4": "PROVEN",
    "C5": "EXCLUDED",
    "D1": "PROVEN",
    "D2": "PROVEN",
    "D3": "PROVEN",
    "E1": "EXCLUDED",
    "E2": "EXCLUDED",
    "E3": "DOCUMENTED-C2.3-DEFERRED",
    "E4": "DOCUMENTED-C2.3-DEFERRED",
    "E5": "PROVEN",
    "F1": "PROVEN",
    "F2": "PROVEN",
    "F3": "PROVEN",
}


class DeltaError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DeltaError(message)


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
    require(path.is_file() and not path.is_symlink(), f"missing JSON: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeltaError(f"cannot load {path}: {error}") from error
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(command: list[str], name: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    (LOG_ROOT / f"{name}.log").write_text(result.stdout, encoding="utf-8")
    require(result.returncode == 0, f"{name} failed:\n{result.stdout[-5000:]}")
    return result.stdout


def fresh_gates() -> dict[str, Any]:
    irq_output = run([
        sys.executable,
        "tools/host-lisp/c2_interrupt_ownership_gate.py",
        "--elf", ELF.relative_to(ROOT).as_posix(),
        "--receipt", FRESH_IRQ.relative_to(ROOT).as_posix(),
        "--selftest",
    ], "interrupt-ownership")
    while_output = run([
        sys.executable, "tools/host-lisp/c2_while_gate.py", "--source-only",
    ], "while-source")
    require(
        "c2-interrupt-ownership: PASS masks=3 mutations=16/16 elf=yes"
        in irq_output,
        "fresh interrupt-ownership positive witness absent")
    require(
        "c2-while-gate: SOURCE PASS mutations=14 "
        "new-opcodes=0 resident-state=0" in while_output,
        "fresh while source positive witness absent")
    fresh_irq = load(FRESH_IRQ)
    require(
        fresh_irq.get("status") == "passed-strict-internal-interrupt-ownership"
        and fresh_irq.get("source_contract", {}).get("handler_changed") is False
        and fresh_irq.get("mutations", {}).get("rejected") == 16,
        "fresh interrupt-ownership receipt drift")
    return {
        "interrupt_ownership": bind(FRESH_IRQ),
        "interrupt_mutations": 16,
        "while_source_mutations": 14,
    }


def validate_authorities() -> dict[str, dict[str, Any]]:
    baseline = load(BASELINE)
    terminal = load(TERMINAL)
    link77 = load(LINK77)
    hardware = load(HARDWARE)
    while_receipt = load(WHILE)
    fastpath = load(FASTPATH)
    unwind = load(UNWIND)
    b3_d3 = load(B3_D3)
    irq = load(IRQ)

    rows = baseline.get("rows")
    require(
        isinstance(rows, list)
        and tuple(row.get("id") for row in rows) == ORDER,
        "canonical 25-row matrix inventory drift")
    require(
        terminal.get("status")
        == "C1-documented-C2.3-deferred-matrix-gate-may-fall"
        and terminal.get("gate_transition", {}).get("matrix_gate") == "FALLS"
        and terminal.get("other_open_rows", {}).get("explicit_C2_3_deferrals")
        == ["C1", "E3", "E4"],
        "terminal matrix disposition drift")
    require(
        link77.get("status") == "passed-Link77-random-while-hardware-not-run"
        and link77.get("gates", {}).get("all_green") is True,
        "Link-77 structural authority drift")
    product_rows = {
        row.get("id"): row for row in hardware.get("product_rows", [])
        if isinstance(row, dict)
    }
    require(
        hardware.get("status")
        == "completed-GC-random-RUNSTOP-IRQ-DIRMISS-bundle"
        and product_rows.get("while-run-stop", {}).get("status") == "passed"
        and product_rows.get("while-run-stop", {}).get("result")
        == "*** stopped (run/stop)"
        and product_rows.get("post-run-stop-repl", {}).get("result") == "3"
        and product_rows.get("irq-mask-readback", {}).get("result")
        == "(0 0 0)",
        "Link-77 hardware break/IRQ rows drift")
    require(
        while_receipt.get("status")
        == "passed-four-view-while-successor-link-authorized-not-run"
        and while_receipt.get("source_contract", {}).get(
            "new_runtime_state_bytes") == 0
        and len(while_receipt.get("mutations_rejected", {})) == 14,
        "while authority drift")
    require(
        fastpath.get("status") == "passed-parser-free-idempotence-fastpath"
        and len(fastpath.get("fallback_mutations", {})) == 5
        and fastpath.get("candidate", {}).get("idempotent_repeat", {}).get(
            "loader_attempts") == 0,
        "require fast-path authority drift")
    require(
        unwind.get("status")
        == "passed-host-contract-probe-product-work-not-authorized"
        and unwind.get("cases", {}).get("passed")
        == unwind.get("cases", {}).get("total"),
        "central abort/unwind authority drift")
    require(
        b3_d3.get("rows", {}).get("D3", {}).get("host_status")
        == "passed-five-event-queue-full-model"
        and b3_d3.get("source_gate", {}).get("second_keymap") == "absent",
        "D3 structural authority drift")
    require(
        irq.get("status") == "passed-strict-internal-interrupt-ownership"
        and irq.get("source_contract", {}).get("handler_changed") is False
        and irq.get("window_handler", {}).get("unchanged_by_policy") is True,
        "Link-77 interrupt replay drift")
    return {
        "baseline": baseline,
        "terminal": terminal,
        "link77": link77,
        "hardware": hardware,
        "while": while_receipt,
        "fastpath": fastpath,
        "unwind": unwind,
        "b3_d3": b3_d3,
        "irq": irq,
    }


def rederived_rows(authorities: dict[str, dict[str, Any]]) \
        -> dict[str, dict[str, Any]]:
    fastpath = authorities["fastpath"]
    stream = authorities["link77"]["streamed_backedge"]["measurement"]
    require(stream["backedge_target_refills_per_admitted_iteration"] == 1.0,
            "while streamed-backedge measurement drift")
    reductions = fastpath["candidate"]["repeat_reduction"]
    return {
        "A3": {
            "status": "EXCLUDED",
            "delta_surface": "while streamed backedge -> hot code-window refill",
            "finding": (
                "The new backedge exercises the refill seam and pays one "
                "refill per admitted iteration when it crosses the window. "
                "The window and Bank-2/3 code planes remain fixed raw storage "
                "outside the non-moving heap, so GC cannot relocate them."),
            "proof_boundary": (
                "This is a structural non-moving-GC exclusion, not a timing "
                "claim. The measured refill cost is documented separately."),
            "fresh_facts": {
                "logical_VM_steps": stream["logical_VM_steps"],
                "payload_refills_total": stream["payload_refills_total"],
                "backedge_refills_per_iteration":
                    stream["backedge_target_refills_per_admitted_iteration"],
            },
            "authorities": ["while", "link77", "matrix"],
        },
        "A4": {
            "status": "EXCLUDED",
            "delta_surface": "require fast path -> published C2D identity reads",
            "finding": (
                "The fast path is a serialized read-only decision before the "
                "parser. It neither opens a publication transaction nor "
                "writes C2D; every miss enters the unchanged slow path."),
            "proof_boundary": (
                "Excludes the new fast path from the GC/publication crossing. "
                "It does not re-prove the unchanged slow publication path."),
            "fresh_facts": {
                "loader_attempts_on_hit": 0,
                "fallback_directions": len(
                    fastpath["fallback_mutations"]),
            },
            "authorities": ["fastpath", "matrix"],
        },
        "B1": {
            "status": "PROVEN",
            "delta_surface": "while non-local exit -> central abort landing",
            "finding": (
                "while adds only JFALSEREL/JMPREL control flow and no abort "
                "landing, C2J field, root or resident state. Errors and "
                "longjmp continue through the one implemented abort cleanup."),
            "proof_boundary": (
                "Fresh delta proof plus the existing 48-case central-unwind "
                "fixture; no new Link-77 open-transaction hardware claim."),
            "fresh_facts": {
                "while_new_opcodes": 0,
                "while_new_resident_state_bytes": 0,
                "unwind_cases": authorities["unwind"]["cases"]["passed"],
            },
            "authorities": ["while", "unwind", "interrupt_source", "link77"],
        },
        "B2": {
            "status": "PROVEN",
            "delta_surface": "RUN/STOP inside while -> central abort landing",
            "finding": (
                "Link 77 physically aborts an active while through RUN/STOP "
                "and returns to a working REPL. The event consumer still calls "
                "the same C2J cleanup before longjmp; the delta adds no second "
                "abort path."),
            "proof_boundary": (
                "Hardware proves Link-77 ordinary RUN/STOP delivery and REPL "
                "survival. Byte-identical open-transaction restoration remains "
                "the previously reviewed central-landing proof; this receipt "
                "does not claim a fresh Link-77 transaction capture."),
            "fresh_facts": {
                "hardware_result": "*** stopped (run/stop)",
                "post_abort_repl_result": "3",
                "abort_landing_implementations": 1,
            },
            "authorities": [
                "hardware", "unwind", "interrupt_source", "link77",
            ],
        },
        "C5": {
            "status": "EXCLUDED",
            "delta_surface": "require fast path -> C2D index/identity reads",
            "finding": (
                "The fast path reads only the published C2D index and identity "
                "through Prim 67. It introduces no source locator and no "
                "runtime Attic edge; misses fall back before any library load."),
            "proof_boundary": (
                "Structural source-domain exclusion. It makes no physical "
                "one-byte-DMA timing claim."),
            "fresh_facts": {
                "repeat_prim67_reads":
                    fastpath["candidate"]["idempotent_repeat"]["prim67_reads"],
                "repeat_read_reduction_percent":
                    reductions["prim67_reads_percent"],
            },
            "authorities": ["fastpath", "link77", "matrix"],
        },
        "D1": {
            "status": "PROVEN",
            "delta_surface":
                "new interrupt-source masks -> publication-window closure",
            "finding": (
                "The new Ethernet, Auto-IEC and audio-DMA masks execute before "
                "window publication. The linked IRQ handler is byte-for-byte "
                "outside that change and retains no publication-state edge."),
            "proof_boundary": (
                "Fresh source/ELF ownership gate with 16/16 mutations plus "
                "hardware readback; no cartridge-storm support is claimed."),
            "fresh_facts": {
                "masked_families": 3,
                "hardware_readback": "(0 0 0)",
                "handler_changed": False,
            },
            "authorities": ["fresh_irq", "irq", "hardware", "window_source"],
        },
        "D2": {
            "status": "PROVEN",
            "delta_surface":
                "new interrupt-source masks -> island install/handoff ordering",
            "finding": (
                "SEI precedes personality selection; masks and readbacks "
                "precede window publication; raster enable and CLI remain "
                "last. The relocated CRC is boot-only, has one pre-ownership "
                "caller and is unreachable after ownership."),
            "proof_boundary": (
                "Fresh linked-ELF ordering and closure proof. It does not "
                "expand the externally supported interrupt profile."),
            "fresh_facts": {
                "source_masks": 3,
                "readbacks_before_window_publish": True,
                "raster_enable_and_CLI_last": True,
                "boot_crc_post_ownership_reachable": False,
            },
            "authorities": ["fresh_irq", "irq", "runtime_source", "link77"],
        },
        "D3": {
            "status": "PROVEN",
            "delta_surface":
                "interrupt ownership delta -> typed-queue break source",
            "finding": (
                "The Link-77 policy changes only pre-publication source masks. "
                "It leaves the matrix edge, pending/held latch, one queue "
                "consumer and source-less episode guard unchanged; the "
                "reviewed five-event queue-full model still rejects all "
                "sixteen source/model mutations."),
            "proof_boundary": (
                "Preserves the terminal C2.2 structural disposition and adds "
                "ordinary Link-77 RUN/STOP hardware confirmation. It does not "
                "rewrite history as a physical queue-full run on Link 77; none "
                "was performed in this delta review."),
            "fresh_facts": {
                "handler_changed": False,
                "second_keymap": "absent",
                "queue_model_events": 5,
                "hardware_queue_full_run": False,
            },
            "authorities": [
                "fresh_irq", "irq", "b3_d3", "terminal", "hardware",
            ],
        },
        "E1": {
            "status": "EXCLUDED",
            "delta_surface":
                "require idempotence cache -> generation/identity change",
            "finding": (
                "The cache is not a loaded-library authority. A hit requires "
                "the current generation, all five count/front values, the "
                "canonical index lock and the complete ordered persistent "
                "C2D identity; every mismatch takes the slow path."),
            "proof_boundary": (
                "Excludes stale fast-path acceptance. It does not claim that "
                "a changed generation can reuse the old cache."),
            "fresh_facts": {
                "fallback_directions": 5,
                "repeat_VM_step_reduction_percent":
                    reductions["vm_steps_percent"],
                "repeat_prim67_reduction_percent":
                    reductions["prim67_reads_percent"],
            },
            "authorities": ["fastpath", "link77"],
        },
    }


def build_receipt(run_fresh: bool) -> dict[str, Any]:
    authorities = validate_authorities()
    fresh = fresh_gates() if run_fresh else {
        "interrupt_ownership": bind(FRESH_IRQ),
        "interrupt_mutations": 16,
        "while_source_mutations": 14,
    }
    baseline_rows = {
        row["id"]: row for row in authorities["baseline"]["rows"]
    }
    changed = rederived_rows(authorities)
    require(set(changed) == set(REDERIVED), "re-derived row set drift")

    rows: list[dict[str, Any]] = []
    for row_id in ORDER:
        baseline = baseline_rows[row_id]
        if row_id in REDERIVED:
            row = {
                "id": row_id,
                "crossing": baseline["crossing"],
                "review": "re-derived-against-Link77-delta",
                "baseline_Link57_status": baseline["status"],
                "terminal_C2_2_status": TERMINAL_STATUS[row_id],
                **changed[row_id],
            }
        else:
            row = {
                "id": row_id,
                "crossing": baseline["crossing"],
                "review": "not-rederived-Link77-delta-disjoint",
                "status": TERMINAL_STATUS[row_id],
                "baseline_Link57_status": baseline["status"],
                "terminal_C2_2_status": TERMINAL_STATUS[row_id],
                "reason": (
                    "No Link-77 source, state, control, storage, ownership or "
                    "publication edge reaches this crossing. Its reviewed "
                    "terminal C2.2 disposition is retained, explicitly not "
                    "presented as fresh Link-77 proof."),
                "authorities": ["baseline", "terminal"],
            }
            if row_id in ("C1", "E3", "E4"):
                row["deferred_scope"] = "C2.3-explicit-unchanged"
        rows.append(row)

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    require(
        counts == {
            "PROVEN": 17,
            "EXCLUDED": 5,
            "DOCUMENTED-C2.3-DEFERRED": 3,
        },
        f"terminal disposition count drift: {counts}")
    require(
        sum(row["review"] == "re-derived-against-Link77-delta"
            for row in rows) == 9
        and sum(row["review"] == "not-rederived-Link77-delta-disjoint"
                for row in rows) == 16,
        "delta review coverage drift")

    bindings = {
        "plan": bind(PLAN),
        "matrix": bind(MATRIX),
        "baseline": bind(BASELINE),
        "terminal": bind(TERMINAL),
        "link77": bind(LINK77),
        "hardware": bind(HARDWARE),
        "while": bind(WHILE),
        "fastpath": bind(FASTPATH),
        "unwind": bind(UNWIND),
        "b3_d3": bind(B3_D3),
        "addenda_review": bind(ADDENDA_REVIEW),
        "irq": bind(IRQ),
        "interrupt_source": bind(INTERRUPT_SOURCE),
        "window_source": bind(WINDOW_SOURCE),
        "runtime_source": bind(RUNTIME_SOURCE),
        "verifier": bind(Path(__file__).resolve()),
        "fresh_irq": fresh["interrupt_ownership"],
    }
    return {
        "format": "lisp65-v1.2.1-link77-cross-invariant-delta-v1",
        "version": 1,
        "recorded_on": "2026-07-29",
        "status": "passed-Link77-delta-review-no-new-open-row",
        "candidate": "Link 77",
        "method": {
            "baseline_rows": 25,
            "rederived_rows": sorted(REDERIVED),
            "rederived_count": 9,
            "explicit_not_rederived_count": 16,
            "rule": (
                "Only crossings reachable from the Link-77 delta are "
                "re-derived. Every other row carries an explicit not-rederived "
                "marker and its reviewed terminal C2.2 disposition."),
            "no_silent_inheritance": True,
        },
        "summary": {
            "PROVEN": counts["PROVEN"],
            "EXCLUDED": counts["EXCLUDED"],
            "DOCUMENTED_C2_3_DEFERRED":
                counts["DOCUMENTED-C2.3-DEFERRED"],
            "new_OPEN_rows": 0,
            "matrix_gate": "remains-fallen-for-C2.2",
            "acceptance_chain": "A2-green-A3-still-requires-fresh-chain",
        },
        "fresh_execution_witness": {
            "interrupt_ownership_mutations":
                fresh["interrupt_mutations"],
            "while_source_mutations": fresh["while_source_mutations"],
        },
        "rows": rows,
        "bindings": bindings,
        "claim_limit": (
            "A Link-77 delta review only. It is not a fresh full-matrix "
            "derivation, R4/R5/R6/G5/G6 result, hardware queue-full run, "
            "promotion, tag, release or public push. C1/E3/E4 remain explicit "
            "C2.3 deferrals.")
    }


def write_receipt() -> None:
    value = build_receipt(run_fresh=True)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-v1.2.1-matrix-delta: PASS "
        "rows=25 rederived=9 explicit-not-rederived=16 "
        "new-open=0 deferred-C2.3=3")


def verify_receipt() -> None:
    require(RECEIPT.is_file(), "delta receipt absent")
    observed = load(RECEIPT)
    expected = build_receipt(run_fresh=False)
    require(observed == expected, "delta receipt or authority drift")
    print(
        "c2-v1.2.1-matrix-delta: VERIFY PASS "
        "rows=25 rederived=9 explicit-not-rederived=16")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "verify"))
    args = parser.parse_args()
    try:
        if args.action == "write":
            write_receipt()
        else:
            verify_receipt()
        return 0
    except (
        DeltaError, OSError, KeyError, ValueError,
        json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        print(f"c2-v1.2.1-matrix-delta: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
