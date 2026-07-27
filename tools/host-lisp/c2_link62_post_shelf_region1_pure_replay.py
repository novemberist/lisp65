#!/usr/bin/env python3
"""Pure full-gate replay of the immutable Link-62 product."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link60_boot_inventory_pure_replay as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"


def configure() -> None:
    BASE.LINK_NUMBER = 62
    BASE.SOURCE = ROOT / (
        "build/c2.2/substitution/product-link-62-post-shelf-region1")
    BASE.PRODUCT = BASE.SOURCE / "lisp65-c2-substitution-linked.prg"
    BASE.ELF = Path(str(BASE.PRODUCT) + ".elf")
    BASE.PROFILE = BASE.SOURCE / "resolved-profile.txt"
    BASE.SOURCE_RECEIPT = EVIDENCE / "c2.2-product-link62-internal.json"
    BASE.OUT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-62-post-shelf-region1-pure-replay")
    BASE.RECEIPT = EVIDENCE / (
        "c2.2-product-link62-post-shelf-region1-structural-receipt.json")
    BASE.EXPECTED_PRODUCT_SHA = (
        "85fc3cad0eded7fd6a9079194a25b59415d86f2eb99ccec7d684ac756a831b3f")
    BASE.EXPECTED_SOURCE_STATUS = (
        "FIRST RED: C2-lite real-ABI Link 50 stopped")
    BASE.EXPECTED_SOURCE_DIAGNOSTIC = {
        "message": "final consolidation aggregate/profile gate red",
        "type": "GateError",
    }
    BASE.REQUIRE_SOURCE_PRODUCT_BINDING = False
    BASE.FAILED_PREDECESSOR_PRODUCT = ROOT / (
        "build/c2.2/substitution/product-link-61-v4-final-frame-seal/"
        "lisp65-c2-substitution-linked.prg")
    BASE.FAILED_PREDECESSOR_RECEIPT = EVIDENCE / (
        "c2.2-link61-region1-stage-hardware-first-red.json")


def main() -> int:
    configure()
    return BASE.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BASE.ReplayError, RuntimeError, OSError, ValueError, KeyError,
    ) as error:
        print(
            "c2-link62-post-shelf-region1-replay: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
