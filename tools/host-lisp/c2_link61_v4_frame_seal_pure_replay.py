#!/usr/bin/env python3
"""Pure full-gate replay of the immutable Link-61 frame-seal product."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link60_boot_inventory_pure_replay as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"


def configure() -> None:
    BASE.LINK_NUMBER = 61
    BASE.SOURCE = ROOT / (
        "build/c2.2/substitution/product-link-61-v4-final-frame-seal")
    BASE.PRODUCT = BASE.SOURCE / "lisp65-c2-substitution-linked.prg"
    BASE.ELF = Path(str(BASE.PRODUCT) + ".elf")
    BASE.PROFILE = BASE.SOURCE / "resolved-profile.txt"
    BASE.SOURCE_RECEIPT = EVIDENCE / "c2.2-product-link61-internal.json"
    BASE.OUT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-61-v4-frame-seal-pure-replay")
    BASE.RECEIPT = EVIDENCE / (
        "c2.2-product-link61-v4-frame-seal-structural-receipt.json")
    BASE.EXPECTED_PRODUCT_SHA = (
        "c4dc74a7729778ad79a1990bf88a25d7803040740bf626c15b08dc2a85607b9b")
    BASE.EXPECTED_SOURCE_STATUS = (
        "FIRST RED: C2-lite real-ABI Link 50 stopped")
    BASE.EXPECTED_SOURCE_DIAGNOSTIC = {
        "message": "final consolidation aggregate/profile gate red",
        "type": "GateError",
    }
    BASE.REQUIRE_SOURCE_PRODUCT_BINDING = False
    BASE.FAILED_PREDECESSOR_PRODUCT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-60-boot-inventory-artifact-repair/"
        "lisp65-c2-substitution-linked.prg")
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
        BASE.ReplayError, RuntimeError, OSError, ValueError, KeyError,
    ) as error:
        print(
            "c2-link61-v4-frame-seal-replay: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
