#!/usr/bin/env python3
"""Complete the sole post-shelf Region-1 WPLTO through current B972 gates."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_two_region_e000_s1_frame_seal_artifact_completion as FRAME  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
STEM = "two-region-post-shelf-region1"


def main() -> int:
    FRAME.SOURCE = ROOT / f"build/c2.2/substitution/{STEM}-wplto"
    FRAME.FIRST_RED = EVIDENCE / f"c2.2-{STEM}-wplto-internal.json"
    FRAME.WPLTO_RECEIPT = EVIDENCE / f"c2.2-{STEM}-wplto-receipt.json"
    FRAME.FORMAT_RECEIPT = EVIDENCE / (
        f"c2.2-{STEM}-format-and-stage-gate.json")
    FRAME.RAW_COMPLETION_RECEIPT = EVIDENCE / (
        f"c2.2-{STEM}-artifact-completion-raw.json")
    FRAME.RECEIPT = EVIDENCE / (
        f"c2.2-{STEM}-wplto-green-receipt.json")
    FRAME.OUT = ROOT / (
        f"build/c2.2/substitution/{STEM}-artifact-completion")
    result = FRAME.main()
    value = json.loads(FRAME.RECEIPT.read_text(encoding="utf-8"))
    format_gate = json.loads(
        FRAME.FORMAT_RECEIPT.read_text(encoding="utf-8"))
    post_shelf = format_gate["post_shelf_region1_stage"]
    FRAME.require(
        result == 0
        and post_shelf["status"]
            == "passed-Link61-shelf-prefix-is-publication-negative-fixture"
        and post_shelf["durable_source"] == "0x08300000",
        "post-shelf Region-1 completion authority red")
    os.chmod(FRAME.RECEIPT, 0o644)
    value["format"] = (
        "lisp65-c2-l65r-v4-post-shelf-region1-WPLTO-v1")
    value["status"] = (
        "passed-post-shelf-region1-WPLTO-all-walls-and-gates-green")
    value["post_shelf_region1_stage"] = post_shelf
    value["authority"]["post_shelf_completion_driver"] = FRAME.bind(
        Path(__file__))
    value["next_gate"] = (
        "one separate Link-62 product link with a fresh identity and no "
        "inherited green")
    FRAME.RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(FRAME.RECEIPT, 0o444)
    print(
        "c2-post-shelf-region1-WPLTO: PASS "
        "source=08300000 target=05bd00 negative=a942 required=66c6 "
        "compiler=1 linker=1 artifact-replay=0/0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        FRAME.CompletionError, FRAME.BASE.CompletionError, RuntimeError,
        OSError, ValueError, KeyError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-post-shelf-region1-WPLTO: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
