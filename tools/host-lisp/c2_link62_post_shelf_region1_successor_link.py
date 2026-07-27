#!/usr/bin/env python3
"""Build the one successor product link for post-shelf Region-1 staging."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link60_two_region_e000_s1_successor_link as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"


def configure() -> None:
    BASE.LINK_NUMBER = 62
    BASE.OUT = ROOT / (
        "build/c2.2/substitution/product-link-62-post-shelf-region1")
    BASE.PRODUCT = BASE.OUT / "lisp65-c2-substitution-linked.prg"
    BASE.ELF = Path(str(BASE.PRODUCT) + ".elf")
    BASE.MAP = Path(str(BASE.PRODUCT) + ".map")
    BASE.C2D = (
        BASE.OUT
        / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
    BASE.INTERNAL = EVIDENCE / "c2.2-product-link62-internal.json"
    BASE.BASE_RECEIPT = EVIDENCE / "c2.2-product-link62-base.json"
    BASE.RAW_RECEIPT = EVIDENCE / "c2.2-product-link62-raw.json"
    BASE.REPLAY_OUT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-62-post-shelf-region1-read-only-qualification")
    BASE.REPLAY_RECEIPT = EVIDENCE / (
        "c2.2-product-link62-post-shelf-region1-read-only-qualification.json")
    BASE.BASE_RESULT = EVIDENCE / "c2.2-product-link62-base-result.json"
    BASE.FORMAT_RECEIPT = EVIDENCE / (
        "c2.2-product-link62-post-shelf-region1-format-and-stage-gate.json")
    BASE.COMPLETION_SOURCE_RECEIPT = ROOT / (
        "build/c2.2/two-region-session-store/"
        "link62-post-shelf-region1-write-completion-source-gate.json")
    BASE.EMITTER_RECEIPT = EVIDENCE / (
        "c2.2-product-link62-post-shelf-region1-emitter-union-gate.json")
    BASE.ISLAND_RECEIPT = EVIDENCE / (
        "c2.2-product-link62-post-shelf-region1-preinstall-source-host-gate.json")
    BASE.QUALIFICATION_RECEIPT = EVIDENCE / (
        "c2.2-product-link62-post-shelf-region1-fresh-qualification.json")
    BASE.RECEIPT = EVIDENCE / (
        "c2.2-product-link62-post-shelf-region1-structural-receipt.json")

    BASE.ARTIFACT_COMPLETION = EVIDENCE / (
        "c2.2-two-region-post-shelf-region1-artifact-completion-raw.json")
    BASE.ARTIFACT_COMPLETION_SHA = (
        "f43b03170c54e852cd381eb00db5c5103bf34db4ab728ba76b55dac4661fb9f5")
    BASE.WPLTO_PROFILE = ROOT / (
        "build/c2.2/substitution/"
        "two-region-post-shelf-region1-wplto/resolved-profile.txt")
    BASE.WPLTO_PROFILE_SHA = (
        "354dd47dba3a9168bf9082cc4b7dbc65f30689af6bcf341db0c9cf0fa7fc8294")

    BASE.FAILED_PREDECESSOR_PRODUCT = ROOT / (
        "build/c2.2/substitution/product-link-61-v4-final-frame-seal/"
        "lisp65-c2-substitution-linked.prg")
    BASE.FAILED_PREDECESSOR_PRODUCT_SHA = (
        "c4dc74a7729778ad79a1990bf88a25d7803040740bf626c15b08dc2a85607b9b")
    BASE.FAILED_PREDECESSOR_RECEIPT = EVIDENCE / (
        "c2.2-link61-region1-stage-hardware-first-red.json")


def main() -> int:
    configure()
    return BASE.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BASE.Link60Error, BASE.FINAL.FinalMapError, RuntimeError, OSError,
        ValueError, KeyError,
    ) as error:
        print(
            "c2-link62-post-shelf-region1: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
