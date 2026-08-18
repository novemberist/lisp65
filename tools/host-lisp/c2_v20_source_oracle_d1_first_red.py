#!/usr/bin/env python3
"""Bind the fail-closed result of the fresh Link 105 D1 contact."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))
import c2_v20_source_oracle_d1 as D1  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


OUT = ROOT / "build/c2.3/v2.0-source-oracle-d1"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-source-oracle-d1-first-red-receipt.json")


class FirstRedError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FirstRedError(message)


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def assert_red(image: Path) -> None:
    try:
        SCREEN.check_fail_closed_frame(image)
    except SCREEN.CheckError as error:
        require(error.code == SCREEN.FAIL_CLOSED_FRAME,
                f"unexpected screen failure: {error.message}")
        return
    raise FirstRedError("terminal capture is not a red fail-closed frame")


def derive() -> dict[str, Any]:
    prep = load(D1.PREP)
    D1.validate_preparation(prep, verify=True)
    media = load(D1.MEDIA)
    product = ROOT / media["shared_system"]["product_D81"]["path"]
    library = ROOT / media["library"]["D81"]["path"]
    product_readback = OUT / "product-readback.d81"
    library_readback = OUT / "library-readback.d81"
    screen_text = OUT / "product-boot.txt"
    screen_image = OUT / "product-boot.png"
    assert_red(screen_image)
    raw = screen_text.read_text(encoding="utf-8", errors="replace")
    require("E25" in raw, "terminal capture does not contain E25")
    require(product.read_bytes() == product_readback.read_bytes(),
            "product media readback mismatch")
    require(library.read_bytes() == library_readback.read_bytes(),
            "library media readback mismatch")
    require(not (OUT / "terminal-banner-and-prompt-proven").exists()
            and not (OUT / "owner-visible-signs-confirmed").exists(),
            "green D1 state leaked into first-red contact")
    return {
        "format": "lisp65-c2.3-v2.0-source-oracle-d1-first-red-v1",
        "recorded_on": "2026-08-13",
        "status": "D1-FIRST-RED-E25; SOURCE-ORACLE-MECHANISM-UNDECIDED",
        "authority": {
            "preparation": bind(D1.PREP),
            "media": bind(D1.MEDIA),
            "runner": bind(D1.RUNNER),
        },
        "delivery": {
            "product_source": bind(product),
            "product_readback": bind(product_readback),
            "product_byteidentical": True,
            "library_source": bind(library),
            "library_readback": bind(library_readback),
            "library_byteidentical": True,
        },
        "observed": {
            "access_free_seconds": 45,
            "terminal_text": bind(screen_text),
            "terminal_image": bind(screen_image),
            "visible": ["E25", "red fail-closed frame"],
            "required_terminal_absent": ["WORKBENCH 1.5.0", "lisp65>"],
            "owner_liveness_confirmation": "NOT-CAPTURED",
        },
        "classification": {
            "result": "Link 105 D1 returned E25 under a red fail-closed frame",
            "transport_and_mount": "EXONERATED-BY-BYTEIDENTICAL-READBACKS",
            "source_oracle_fix_on_hardware": "NOT-GREEN",
            "mechanism": "UNDECIDED-WITHOUT-AN-AUTHORIZED-STOPPED-STATE-ROW",
        },
        "execution_accounting": {
            "hardware_contacts": 1,
            "forms": 0,
            "product_links": 0,
            "WPLTO_runs": 0,
            "post_red_device_accesses": 0,
        },
        "unlock": {"D1": False, "D2_D5": False},
        "claim_limit": (
            "This binds the fresh Link 105 D1 E25 and exact media readbacks. "
            "It does not identify the failing convergence site or distinguish "
            "oracle, latency, decoder, or publication; no stopped-state row, "
            "repeat contact, D2-D5, release, fix, or resume is authorized."),
    }


def main() -> int:
    require(not RECEIPT.exists(), "Link 105 D1 first-red receipt exists")
    value = derive()
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    require(load(RECEIPT) == derive(), "Link 105 D1 first-red replay drift")
    print("Link 105 D1: FIRST RED E25; D2-D5 CLOSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FirstRedError, D1.D1Error, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"LINK 105 D1 FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
