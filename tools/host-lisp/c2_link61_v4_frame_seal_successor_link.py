#!/usr/bin/env python3
"""Build the one successor product link for the final L65R-v4 frame seal."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link60_two_region_e000_s1_successor_link as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"


def configure() -> None:
    BASE.LINK_NUMBER = 61
    BASE.OUT = ROOT / (
        "build/c2.2/substitution/product-link-61-v4-final-frame-seal")
    BASE.PRODUCT = BASE.OUT / "lisp65-c2-substitution-linked.prg"
    BASE.ELF = Path(str(BASE.PRODUCT) + ".elf")
    BASE.MAP = Path(str(BASE.PRODUCT) + ".map")
    BASE.C2D = (
        BASE.OUT
        / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
    BASE.INTERNAL = EVIDENCE / "c2.2-product-link61-internal.json"
    BASE.BASE_RECEIPT = EVIDENCE / "c2.2-product-link61-base.json"
    BASE.RAW_RECEIPT = EVIDENCE / "c2.2-product-link61-raw.json"
    BASE.REPLAY_OUT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-61-v4-frame-seal-read-only-qualification")
    BASE.REPLAY_RECEIPT = EVIDENCE / (
        "c2.2-product-link61-v4-frame-seal-read-only-qualification.json")
    BASE.BASE_RESULT = EVIDENCE / "c2.2-product-link61-base-result.json"
    BASE.FORMAT_RECEIPT = EVIDENCE / (
        "c2.2-product-link61-v4-frame-seal-format-and-stage-gate.json")
    BASE.COMPLETION_SOURCE_RECEIPT = ROOT / (
        "build/c2.2/two-region-session-store/"
        "link61-v4-frame-seal-write-completion-source-gate.json")
    BASE.EMITTER_RECEIPT = EVIDENCE / (
        "c2.2-product-link61-v4-frame-seal-emitter-union-gate.json")
    BASE.ISLAND_RECEIPT = EVIDENCE / (
        "c2.2-product-link61-v4-frame-seal-preinstall-source-host-gate.json")
    BASE.QUALIFICATION_RECEIPT = EVIDENCE / (
        "c2.2-product-link61-v4-frame-seal-fresh-qualification.json")
    BASE.RECEIPT = EVIDENCE / (
        "c2.2-product-link61-v4-frame-seal-structural-receipt.json")

    BASE.ARTIFACT_COMPLETION = EVIDENCE / (
        "c2.2-two-region-e000-s1-frame-seal-artifact-completion-raw.json")
    BASE.ARTIFACT_COMPLETION_SHA = (
        "2a6cec2ea7fda4f874b6dc1229711b95ad7f6a4371eccb7ae286900e2da21dc8")
    BASE.WPLTO_PROFILE = ROOT / (
        "build/c2.2/substitution/"
        "two-region-session-store-e000-s1-frame-seal-wplto2/"
        "resolved-profile.txt")
    BASE.WPLTO_PROFILE_SHA = (
        "9b29e03c9ab71116ec1b65778ee6da4d54931c9c75af77316de25560254b8f6f")

    BASE.FAILED_PREDECESSOR_PRODUCT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-60-boot-inventory-artifact-repair/"
        "lisp65-c2-substitution-linked.prg")
    BASE.FAILED_PREDECESSOR_PRODUCT_SHA = (
        "5a4e2221c1e03cad4ec5fa1dd3529cdd2e3f593c84e9ee4e7e8cd53eaf750227")
    BASE.FAILED_PREDECESSOR_RECEIPT = EVIDENCE / (
        "c2.2-product-link60-repaired-catalog-v4-frame-seal-"
        "hardware-first-red.json")


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
            "c2-link61-v4-frame-seal: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
