#!/usr/bin/env python3
"""One replacement for the display card's path-vs-content identity First Red."""

from __future__ import annotations

import sys

import c2_v160_display_ownership_card as CARD


CARD.PREFLIGHT = CARD.ROOT / "build/c2.3/v1.6-display-ownership-replacement2-preflight"
CARD.BUILD = CARD.ROOT / "build/c2.3/v1.6-display-ownership-replacement-card"
CARD.INVOCATION = CARD.PREFLIGHT / "card-invocation.json"
CARD.RECEIPT = CARD.ARCH / "c2.3-v1.6-display-ownership-replacement-card-receipt.json"
CARD.RED = CARD.ARCH / "c2.3-v1.6-display-ownership-replacement-card-final-red.json"


if __name__ == "__main__":
    try:
        raise SystemExit(CARD.main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            CARD.record_red(error)
        print(f"v1.6 display replacement: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
