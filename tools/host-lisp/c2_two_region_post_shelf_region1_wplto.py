#!/usr/bin/env python3
"""Run the sole WPLTO map for post-shelf Region-1 staging."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_two_region_e000_s1_final_wplto as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"


def main() -> int:
    stem = "two-region-post-shelf-region1"
    BASE.OUT = ROOT / f"build/c2.2/substitution/{stem}-wplto"
    BASE.INTERNAL = EVIDENCE / f"c2.2-{stem}-wplto-internal.json"
    BASE.BASE_RECEIPT = EVIDENCE / f"c2.2-{stem}-wplto-base.json"
    BASE.RAW_RECEIPT = EVIDENCE / f"c2.2-{stem}-wplto-raw.json"
    BASE.REPLAY_OUT = ROOT / f"build/c2.2/substitution/{stem}-qualification"
    BASE.REPLAY_RECEIPT = EVIDENCE / f"c2.2-{stem}-qualification.json"
    BASE.BASE_RESULT = EVIDENCE / f"c2.2-{stem}-wplto-base-result.json"
    BASE.FORMAT_RECEIPT = EVIDENCE / (
        f"c2.2-{stem}-format-and-stage-gate.json")
    BASE.COMPLETION_SOURCE_RECEIPT = ROOT / (
        f"build/c2.2/two-region-session-store/"
        f"{stem}-write-completion-source-gate.json")
    BASE.EMITTER_RECEIPT = EVIDENCE / (
        f"c2.2-{stem}-emitter-union-gate.json")
    BASE.ISLAND_RECEIPT = EVIDENCE / (
        f"c2.2-{stem}-preinstall-source-host-gate.json")
    BASE.RECEIPT = EVIDENCE / f"c2.2-{stem}-wplto-receipt.json"
    BASE.PRODUCT = BASE.OUT / "lisp65-c2-substitution-linked.prg"
    BASE.ELF = Path(str(BASE.PRODUCT) + ".elf")
    BASE.MAP = Path(str(BASE.PRODUCT) + ".map")
    BASE.C2D = (
        BASE.OUT
        / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
    BASE.RUNNER_PATH = Path(__file__)
    return BASE.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BASE.FinalMapError, RuntimeError, OSError, ValueError, KeyError,
    ) as error:
        print(
            "c2-two-region-post-shelf-region1-wplto: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
