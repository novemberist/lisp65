#!/usr/bin/env python3
"""Diagnose C1 cutpoint 3 from existing product-owned IRQ witnesses."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / (
    "build/c2.2/"
    "c1-freezer-memory-hold-hardware-link58-attempt5-NONPROMOTABLE")
EVIDENCE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks")
FIRST_RED = EVIDENCE / (
    "c2.2-link58-C1-Freezer-memory-hold-cutpoint3-continuation-"
    "hardware-first-red.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-C1-Freezer-source-less-IRQ-episode-diagnosis.json")
WINDOW_SOURCE = ROOT / "src/c2_kernal_window.s"
CONTRACT = ROOT / "config/c2-cross-invariant-c2.2-open-addenda.json"

FRAME_LO = 0x1F83
FRAME_HI = 0x1F84
SOURCELESS = 0x1F86
STATE = 0x1F88
UNOWNED_VIC = 0x1F89


class DiagnosisError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise DiagnosisError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def snapshot(cutpoint: int, stage: str) -> dict[str, int]:
    path = OUT / f"cutpoint-{cutpoint}/{stage}-e000.bin"
    require(path.is_file() and path.stat().st_size == 8192,
            f"missing E000 witness: {path}")
    data = path.read_bytes()
    return {
        "frame": data[FRAME_LO] | data[FRAME_HI] << 8,
        "source_less_IRQ_count": data[SOURCELESS],
        "product_state": data[STATE],
        "unowned_VIC_sources": data[UNOWNED_VIC],
    }


def current_model(count: int, owned_raster: bool) -> tuple[int, bool]:
    if owned_raster:
        return count, False
    count = (count + 1) & 0xFF
    return count, count >= 2


def episode_model(count: int, owned_raster: bool) -> tuple[int, bool]:
    if owned_raster:
        return 0, False
    count = (count + 1) & 0xFF
    return count, count >= 2


def main() -> int:
    require(not RECEIPT.exists(), "source-less IRQ diagnosis is one-shot")
    for path in (FIRST_RED, WINDOW_SOURCE, CONTRACT):
        require(path.is_file(), f"missing diagnosis authority: {path}")
    first_red = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(
        first_red["status"] ==
            "first-red-C1-header-before-exports-continuation-"
            "stalled-after-thaw"
        and first_red["hardware"]["command_reached_after_release"] == [0, 3]
        and first_red["hardware"]["C2J"]["state"] == "unchanged-ACTIVE",
        "cutpoint-3 First Red authority drift")

    observed = {
        str(cutpoint): {
            stage: snapshot(cutpoint, stage)
            for stage in ("hold-before", "hold-after", "post")
        }
        for cutpoint in (2, 3)
    }
    require(
        observed["2"]["hold-before"]["source_less_IRQ_count"] == 0
        and observed["2"]["hold-after"]["source_less_IRQ_count"] == 1
        and observed["2"]["post"]["source_less_IRQ_count"] == 1
        and observed["2"]["post"]["frame"]
            > observed["2"]["hold-after"]["frame"]
        and observed["3"]["hold-before"]["source_less_IRQ_count"] == 1
        and observed["3"]["hold-after"]["source_less_IRQ_count"] == 2
        and observed["3"]["post"]["source_less_IRQ_count"] == 2
        and observed["3"]["post"]["frame"]
            == observed["3"]["hold-after"]["frame"]
        and all(
            row["product_state"] == 4
            for cutpoint in observed.values() for row in cutpoint.values())
        and observed["3"]["hold-after"]["unowned_VIC_sources"] == 0,
        "E000 IRQ/frame witnesses do not match the observed First Red")

    source = WINDOW_SOURCE.read_text(encoding="utf-8")
    source_less = source[source.index(".Lsource_less:"):
                         source.index(
                             ".section .lisp65_c2_kernal_window."
                             "nmi_and_freezer_return")]
    irq = source[source.index("c2_kernal_irq_handler:"):
                 source.index(".Lsource_less:")]
    fail_closed = source[source.index("c2_kernal_fail_closed:"):
                         source.index(
                             ".section .lisp65_c2_kernal_window."
                             "post_startup_output_seam")]
    require(
        all(token in source_less for token in (
            "inc C2K_SOURCELESS_IRQS",
            "lda C2K_SOURCELESS_IRQS",
            "cmp #$02",
            "bcc .Lirq_return",
            "jmp c2_kernal_fail_closed"))
        and "stz C2K_SOURCELESS_IRQS" not in irq
        and all(token in fail_closed for token in (
            "sei", "sta $d01a", "lda #$02", "sta $d020",
            "jmp .Lfailed")),
        "product-owned source-less IRQ/fail-closed sequence drift")

    count, failed_first = current_model(0, False)
    count, failed_raster = current_model(count, True)
    count, failed_second = current_model(count, False)
    require(
        (count, failed_first, failed_raster, failed_second)
            == (2, False, False, True),
        "current source-less IRQ model does not reproduce hardware")
    episode_count, episode_failed_first = episode_model(0, False)
    episode_count, episode_failed_raster = episode_model(
        episode_count, True)
    episode_count, episode_failed_second = episode_model(
        episode_count, False)
    consecutive_count, _ = episode_model(0, False)
    consecutive_count, consecutive_failed = episode_model(
        consecutive_count, False)
    require(
        (episode_count, episode_failed_first, episode_failed_raster,
         episode_failed_second) == (1, False, False, False)
        and consecutive_count == 2 and consecutive_failed,
        "episode-latch counterfactual does not preserve storm rejection")

    receipt = {
        "format": (
            "lisp65-c2.2-C1-Freezer-source-less-IRQ-episode-"
            "diagnosis-v1"),
        "status": "diagnosed-cumulative-source-less-IRQ-counter-first-red",
        "matrix_row": "C1",
        "matrix_status": "OPEN-product-semantics-first-red",
        "authority": {
            "hardware_first_red": bind(FIRST_RED),
            "window_source": bind(WINDOW_SOURCE),
            "C3_addendum": bind(CONTRACT),
        },
        "existing_memory_witnesses": observed,
        "source_attribution": {
            "owned_raster_path_resets_source_less_counter": False,
            "source_less_path": [
                "increment FF86",
                "allow values below 2",
                "jump c2_kernal_fail_closed at value 2",
            ],
            "fail_closed": [
                "SEI",
                "disable VIC IRQ mask",
                "set border red",
                "loop forever",
            ],
        },
        "causal_chain": [
            "cutpoint 2 first Freezer return increments FF86 from 0 to 1",
            "ordinary owned raster IRQs advance frames but never reset FF86",
            "cutpoint 3 second Freezer return increments FF86 from 1 to 2",
            "the explicit cmp-2 branch enters c2_kernal_fail_closed",
            "red border, stable frame, ACTIVE C2J and no REPL continuation follow",
        ],
        "counterfactual_gate_model": {
            "candidate_not_authorized_as_fix": (
                "reset the episode latch only on a real owned raster IRQ"),
            "first_source_less_after_each_owned_raster": "allowed",
            "second_consecutive_source_less_without_owned_raster": (
                "still-fail-closed"),
        },
        "avoided_diagnostic_cycle": {
            "new_carrier_built": False,
            "new_product_bytes": 0,
            "new_hardware_runs": 0,
            "reason": (
                "existing FF83/FF84/FF86/FF89 witnesses and exact source "
                "control flow already distinguish the proposed hypotheses"),
        },
        "claim_limit": (
            "Diagnosis only. No product fix, C1 closure, matrix-gate fall, "
            "promotion or acceptance-chain claim."),
        "next_gate": (
            "Class-C contract decision for source-less IRQ episode reset; "
            "then host mutations, product probe/link and a fresh bundled "
            "C1 hardware run"),
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-c1-freezer-sourceless-irq-diagnosis: PASS "
        "cp2=0->1+continues cp3=1->2+fail-closed "
        "hardware-runs=0 product-bytes=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        DiagnosisError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-c1-freezer-sourceless-irq-diagnosis: FIRST RED: "
            + str(error), file=sys.stderr)
        raise SystemExit(2)
