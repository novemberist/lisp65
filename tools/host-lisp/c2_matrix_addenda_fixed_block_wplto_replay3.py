#!/usr/bin/env python3
"""Class-A replay after preserving rtov_read's section in generated source."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_matrix_addenda_fixed_block_wplto_replay2 as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-fixed-block-wplto-replay3")
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-replay3-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-replay3-base.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-replay3-receipt.json")
HARNESS_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-replay2-receipt.json")
HARNESS_INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-replay2-internal.json")
HARNESS_STDERR = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-fixed-block-wplto-replay2/"
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
    red = json.loads(HARNESS_RED.read_text(encoding="utf-8"))
    internal = json.loads(HARNESS_INTERNAL.read_text(encoding="utf-8"))
    stderr = HARNESS_STDERR.read_text(encoding="utf-8")
    require(
        red["status"] ==
            "FIRST RED: historical checker stopped current-product "
            "L-full keymap WPLTO"
        and internal["diagnostic"]["message"] ==
            "link command failed before orphan-wrapper acceptance: exit=1"
        and internal["execution_accounting"]["product_closure_links"] == 0
        and "duplicate 'static' declaration specifier" in stderr
        and "cannot combine with previous 'void' declaration specifier"
            in stderr,
        "generated-source section-preservation First Red drift")
    value["class_A_generated_source_first_red"] = bind(HARNESS_RED)
    value["class_A_generated_source_diagnosis"] = bind(HARNESS_INTERNAL)
    value["class_A_generated_source_stderr"] = bind(HARNESS_STDERR)
    value["class_A_generated_source_correction"] = {
        "cause":
            "the C2-lite source replacement regenerated an unannotated "
            "rtov_read definition below the retained section attribute",
        "correction":
            "the replacement emits the canonical annotated definition",
        "product_semantics": "unchanged",
        "product_bytes_before_replay": 0,
        "completed_product_closure_links": 0,
    }
    value["driver"] = bind(Path(__file__))
    return value


def main() -> int:
    require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
        "fixed-block generated-source replay is one-shot")
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
            "c2-matrix-addenda-fixed-block-wplto-replay3: FIRST RED: "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
