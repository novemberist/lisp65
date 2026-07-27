#!/usr/bin/env python3
"""Final WPLTO entry after the two generated-source Class-A corrections."""

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
    "link58-matrix-addenda-fixed-block-wplto-final")
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-final-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-final-base.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-final-receipt.json")
GENERATED_REDS = [
    (
        EVIDENCE / (
            "c2.2-link58-matrix-addenda-fixed-block-wplto-replay2-"
            "internal.json"),
        ROOT / (
            "build/c2.2/substitution/"
            "link58-matrix-addenda-fixed-block-wplto-replay2/"
            "resident-island-seed.prg.link.stderr.txt"),
    ),
    (
        EVIDENCE / (
            "c2.2-link58-matrix-addenda-fixed-block-wplto-replay3-"
            "internal.json"),
        ROOT / (
            "build/c2.2/substitution/"
            "link58-matrix-addenda-fixed-block-wplto-replay3/"
            "resident-island-seed.prg.link.stderr.txt"),
    ),
]
GEOMETRY_RED = EVIDENCE / (
    "c2.2-link58-fixed-block-mod-adjust-geometry-first-red-receipt.json")
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
    geometry = json.loads(GEOMETRY_RED.read_text(encoding="utf-8"))
    require(
        geometry["candidate"]["overflow_bytes"] == 2
        and geometry["disposition"]["selected_replacement"] == "rtov_read",
        "fixed-block geometry First Red drift")
    generated: list[dict[str, Any]] = []
    for internal_path, stderr_path in GENERATED_REDS:
        internal = json.loads(internal_path.read_text(encoding="utf-8"))
        stderr = stderr_path.read_text(encoding="utf-8")
        require(
            internal["diagnostic"]["message"] ==
                "link command failed before orphan-wrapper acceptance: exit=1"
            and internal["execution_accounting"]["product_closure_links"] == 0
            and "duplicate 'static' declaration specifier" in stderr
            and "cannot combine with previous 'void' declaration specifier"
                in stderr,
            "generated-source First Red drift")
        generated.append({
            "internal": bind(internal_path),
            "stderr": bind(stderr_path),
        })
    value["fixed_block_geometry_first_red"] = bind(GEOMETRY_RED)
    value["class_A_generated_source_first_red_chain"] = generated
    value["class_A_generated_source_final_correction"] = {
        "replacement_start":
            "the generator replaces from the rtov_read declarator line",
        "retained_prefix":
            "static void LISP65_C2_FIXED_BANK0_CODE(\"rtov_read\")",
        "replacement_prefix": "rtov_read(...)",
        "duplicate_specifiers": 0,
        "product_semantics": "unchanged",
        "completed_product_closure_links_before_final": 0,
    }
    value["driver"] = bind(Path(__file__))
    return value


def main() -> int:
    require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
        "final fixed-block WPLTO is one-shot")
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
            "c2-matrix-addenda-fixed-block-wplto-final: FIRST RED: "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
