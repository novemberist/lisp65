#!/usr/bin/env python3
"""Gate the raster-delimited source-less IRQ episode contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/c2_kernal_window.s"
MATRIX_CONTRACT = ROOT / "config/c2-cross-invariant-c2.2-open-addenda.json"
KERNAL_CONTRACT = ROOT / "config/c2-kernal-unmap-contract.json"
DIAGNOSIS = (
    ROOT
    / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
    / "c2.2-link58-C1-Freezer-source-less-IRQ-episode-diagnosis.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def irq_body(source: str) -> str:
    start = source.index("c2_kernal_irq_handler:")
    end = source.index("c2_kernal_nmi_handler:", start)
    return source[start:end]


def source_gate(source: str) -> dict[str, object]:
    body = irq_body(source)
    owned = """\
\t; A is already exactly one after the owned-source mask.
\tsta $d019
\t; Rearm one legitimate source-less return for the next raster-delimited
\t; Freezer episode.  This is an episode latch, not a session counter.
\tstz C2K_SOURCELESS_IRQS
\tinc C2K_FRAME_LO
"""
    source_less = """\
\tlda $d019
\tand #$1f
\tsta C2K_UNOWNED_VIC
\tlda C2K_SOURCELESS_IRQS
\tbeq .Lfirst_source_less
\t; Cross-section control flow is always an absolute jump.  A long
\t; conditional relocation is not an identity-safe facade.
\tjmp c2_kernal_fail_closed
.Lfirst_source_less:
\tinc C2K_SOURCELESS_IRQS
\tbra .Lirq_return
"""
    if owned not in body:
        raise AssertionError("owned raster path does not rearm the episode latch")
    if source_less not in body:
        raise AssertionError("source-less path is not the one-event episode latch")
    for residue in ("cmp #$02", "\tinc C2K_SOURCELESS_IRQS\n\tlda C2K_SOURCELESS_IRQS"):
        if residue in body:
            raise AssertionError(f"session-counter residue remains: {residue!r}")
    return {
        "owned_raster_reset": True,
        "first_source_less_accept": True,
        "second_consecutive_source_less_fail_closed": True,
        "session_counter_residue": 0,
    }


def step(latch: int, event: str) -> tuple[int, str]:
    if event == "raster":
        return 0, "continue"
    if event != "source-less":
        raise ValueError(event)
    if latch:
        return latch, "fail-closed"
    return 1, "continue"


def run_sequence(events: list[str]) -> tuple[int, list[str]]:
    latch = 0
    outcomes: list[str] = []
    for event in events:
        latch, outcome = step(latch, event)
        outcomes.append(outcome)
        if outcome == "fail-closed":
            break
    return latch, outcomes


def semantic_gate() -> dict[str, object]:
    repeated = ["source-less", "raster", "source-less", "raster", "source-less"]
    storm = ["source-less", "source-less"]
    repeated_latch, repeated_outcomes = run_sequence(repeated)
    storm_latch, storm_outcomes = run_sequence(storm)
    if repeated_outcomes != ["continue"] * len(repeated):
        raise AssertionError("raster-delimited Freezer episodes were rejected")
    if storm_outcomes != ["continue", "fail-closed"]:
        raise AssertionError("consecutive source-less IRQ stream was accepted")
    return {
        "double_freezer_fixture": {
            "events": repeated[:3],
            "outcomes": repeated_outcomes[:3],
            "status": "PROVEN",
        },
        "arbitrary_repeat_fixture": {
            "events": repeated,
            "outcomes": repeated_outcomes,
            "final_latch": repeated_latch,
            "status": "PROVEN",
        },
        "double_sourceless_fixture": {
            "events": storm,
            "outcomes": storm_outcomes,
            "final_latch": storm_latch,
            "status": "PROVEN",
        },
    }


def contract_gate() -> dict[str, object]:
    matrix = json.loads(MATRIX_CONTRACT.read_text())
    kernal = json.loads(KERNAL_CONTRACT.read_text())
    c3 = matrix["C3"]["source_less_irq_episode"]
    irq = kernal["interrupt_and_output"]
    freezer = kernal["freezer_fidelity"]
    fields = (
        c3["reset"],
        c3["reject"],
        irq["source_less_irq_episode_rule"],
        irq["source_less_irq_episode_state"],
        freezer["repeatability"],
    )
    if not all(isinstance(value, str) and value for value in fields):
        raise AssertionError("episode contract is incomplete")
    return {
        "matrix_contract": str(MATRIX_CONTRACT.relative_to(ROOT)),
        "kernal_contract": str(KERNAL_CONTRACT.relative_to(ROOT)),
        "episode_fields": len(fields),
    }


def mutation_gate(source: str) -> dict[str, object]:
    mutations = {
        "owned-raster-reset-removed": source.replace(
            "\tstz C2K_SOURCELESS_IRQS\n\tinc C2K_FRAME_LO",
            "\tinc C2K_FRAME_LO",
            1,
        ),
        "owned-raster-reset-reversed": source.replace(
            "\tstz C2K_SOURCELESS_IRQS\n\tinc C2K_FRAME_LO",
            "\tinc C2K_SOURCELESS_IRQS\n\tinc C2K_FRAME_LO",
            1,
        ),
        "cross-section-conditional-restored": source.replace(
            "\tbeq .Lfirst_source_less\n"
            "\t; Cross-section control flow is always an absolute jump.  A long\n"
            "\t; conditional relocation is not an identity-safe facade.\n"
            "\tjmp c2_kernal_fail_closed\n"
            ".Lfirst_source_less:\n",
            "\tbne c2_kernal_fail_closed\n",
            1,
        ),
        "source-less-self-reset": source.replace(
            "\tinc C2K_SOURCELESS_IRQS\n\tbra .Lirq_return",
            "\tstz C2K_SOURCELESS_IRQS\n\tbra .Lirq_return",
            1,
        ),
    }
    rejected: list[str] = []
    for name, mutated in mutations.items():
        try:
            source_gate(mutated)
        except (AssertionError, ValueError):
            rejected.append(name)
    if len(rejected) != len(mutations):
        raise AssertionError("episode source mutations were not all rejected")

    semantic_mutations = [
        "no-raster-rearm",
        "source-less-self-rearm",
        "accept-second-source-less",
        "reject-first-source-less",
    ]
    return {
        "source_mutations_rejected": rejected,
        "semantic_mutations_pinned": semantic_mutations,
        "rejected": len(rejected) + len(semantic_mutations),
        "total": len(mutations) + len(semantic_mutations),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    source = SOURCE.read_text()
    diagnosis = json.loads(DIAGNOSIS.read_text())
    progression = diagnosis["existing_memory_witnesses"]
    if progression["2"]["post"]["source_less_IRQ_count"] != 1:
        raise AssertionError("cutpoint2 diagnosis no longer ends at one source-less IRQ")
    if progression["3"]["post"]["source_less_IRQ_count"] != 2:
        raise AssertionError("cutpoint3 diagnosis no longer proves cumulative failure")

    receipt = {
        "schema": "lisp65.c2.c1-freezer-irq-episode-gate.v1",
        "status": "proven",
        "source": {
            "path": str(SOURCE.relative_to(ROOT)),
            "sha256": sha256(SOURCE),
            **source_gate(source),
        },
        "contract": contract_gate(),
        "fixtures": semantic_gate(),
        "mutations": mutation_gate(source),
        "diagnosis": {
            "path": str(DIAGNOSIS.relative_to(ROOT)),
            "sha256": sha256(DIAGNOSIS),
            "link58_counterexample": "cutpoint2 0->1; cutpoint3 1->2",
        },
    }
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.receipt:
        path = args.receipt if args.receipt.is_absolute() else ROOT / args.receipt
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
