#!/usr/bin/env python3
"""Fresh Link-58 WPLTO after both rejected fixed-block candidates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_matrix_addenda_fixed_block_wplto as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-fixed-block-wplto-final2")
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-final2-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-final2-base.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-final2-receipt.json")
RTOV_READ_INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-final-internal.json")
RTOV_READ_MAP = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-fixed-block-wplto-final/"
    "resident-island-seed.prg.map")
RTOV_READ_STDERR = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-fixed-block-wplto-final/"
    "resident-island-seed.prg.link.stderr.txt")
ORIGINAL_AUTHORITY = BASE.authority


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def authority() -> dict[str, Any]:
    value = ORIGINAL_AUTHORITY()
    internal = json.loads(RTOV_READ_INTERNAL.read_text(encoding="utf-8"))
    map_text = RTOV_READ_MAP.read_text(encoding="utf-8")
    stderr = RTOV_READ_STDERR.read_text(encoding="utf-8")
    require(
        internal["execution_accounting"]["product_closure_links"] == 0
        and "    c351     c351        6     1 .noinit" in map_text
        and "__lisp65_workbench_overlay_min_start = "
            "ALIGN(__lisp65_workbench_noinit_end + 1, 2)" in map_text
        and ".noinit range is [0xC351, 0xC356]" in stderr,
        "rtov_read geometry First Red drift")
    value["rejected_rtov_read_geometry"] = {
        "status": "FIRST RED before completed product closure",
        "tenant_bytes": 28,
        "aligned_overlay_floor": "0xc358",
        "runtime_overlay_vma": "0xc356",
        "deficit_bytes": 2,
        "internal": bind(RTOV_READ_INTERNAL),
        "map": bind(RTOV_READ_MAP),
        "stderr": bind(RTOV_READ_STDERR),
    }
    value["driver"] = bind(Path(__file__))
    return value


def main() -> int:
    require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
        "final2 fixed-block WPLTO is one-shot")
    old = {
        "out": BASE.OUT,
        "internal": BASE.INTERNAL,
        "base_receipt": BASE.BASE_RECEIPT,
        "receipt": BASE.RECEIPT,
        "authority": BASE.authority,
    }
    try:
        BASE.OUT = OUT
        BASE.INTERNAL = INTERNAL
        BASE.BASE_RECEIPT = BASE_RECEIPT
        BASE.RECEIPT = RECEIPT
        BASE.authority = authority
        return BASE.main()
    finally:
        BASE.OUT = old["out"]
        BASE.INTERNAL = old["internal"]
        BASE.BASE_RECEIPT = old["base_receipt"]
        BASE.RECEIPT = old["receipt"]
        BASE.authority = old["authority"]


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-matrix-addenda-fixed-block-wplto-final2: FIRST RED: "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
