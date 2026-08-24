#!/usr/bin/env python3
"""Pack artifact-only media for the single Finish-Plan product fix."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_clean_product_acceptance_media as MEDIA  # noqa: E402
import c2_v160_clean_product_operand_root_fix as FIX  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-clean-product-operand-root-media"
ADAPTER = BUILD.parent / "v1.6-clean-product-operand-root-media-adapter.json"
RECEIPT = ARCH / "c2.3-v1.6-clean-product-operand-root-media-receipt.json"
SESSION = ROOT / "config/c2-v160-clean-product-operand-root-session.json"
PRODUCT_REMOTE = "V16B.D81"
LIBRARY_REMOTE = "V16BLIB.D81"
EXPECTED = {
    "PRG": (41566,
            "2dbd282e32185b580bfd4083596307e4cd73d27b7ead5c684b299ca74616a312"),
    "ELF": (647532,
            "b390ec5dfbc049ea7e857b3af984da7769117ac439c0ffe4ca758c159b2f846b"),
}
STATUS = "PASS: V1.6 CLEAN PRODUCT OPERAND ROOT MEDIA READY"
_SESSION_CONFIG = MEDIA.session_config


def session_config(product: Path, library: Path) -> dict[str, object]:
    value = _SESSION_CONFIG(product, library)
    value["format"] = "lisp65-c2-v160-clean-product-operand-root-session-v1"
    value["media"]["product"]["remote_name"] = PRODUCT_REMOTE
    value["media"]["library"]["remote_name"] = LIBRARY_REMOTE
    value["fix_round"] = {
        "class": "nested-result-root-lifetime",
        "round": "one-and-only Finish-Plan product fix",
        "rule": "root nested CALL results before shared caller-window repair",
    }
    return value


def configure() -> None:
    FIX.configure_paths()
    # The media producer is intentionally reused as a reader.  Point every
    # one-shot path at the already accepted fix pair; none of these bindings
    # can invoke WPLTO or relink the product.
    MEDIA.CLEAN = FIX.BASE
    MEDIA.CARD_BUILD = FIX.BUILD
    MEDIA.WPLTO = FIX.BUILD / "wplto"
    MEDIA.STATIC = FIX.BUILD / "static-plane/narrow-static"
    MEDIA.BUILD = BUILD
    MEDIA.ADAPTER = ADAPTER
    MEDIA.RECEIPT = RECEIPT
    MEDIA.SESSION = SESSION
    MEDIA.CLOSURE = FIX.RECEIPT
    MEDIA.ACCEPTANCE = FIX.BUILD / "artifact-acceptance.json"
    MEDIA.PRODUCT_REMOTE = PRODUCT_REMOTE
    MEDIA.LIBRARY_REMOTE = LIBRARY_REMOTE
    MEDIA.EXPECTED = EXPECTED
    MEDIA.STATUS = STATUS
    MEDIA.session_config = session_config


def run(action: str) -> None:
    configure()
    if action == "preflight":
        MEDIA.preflight()
    elif action == "build":
        MEDIA.build()
    elif action == "finalize":
        MEDIA.finalize()
    else:
        MEDIA.check()


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action not in ("preflight", "build", "finalize", "check"):
        raise RuntimeError("usage: preflight|build|finalize|check")
    run(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 operand-root media: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
