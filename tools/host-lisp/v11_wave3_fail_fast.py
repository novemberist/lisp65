#!/usr/bin/env python3
"""Verify the Wave-3 fail-fast ordering without creating evidence receipts."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/v11-wave3-fail-fast.json"
CASES = ROOT / "tests/bytecode/dialect-v2/ide/l-lite-hardware-cases.generated.json"
PRESMOKE = ROOT / "scripts/hw-v11-wave3-presmoke.sh"


class FailFastError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FailFastError(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FailFastError(f"cannot read {path.relative_to(ROOT)}: {exc}") from exc
    require(isinstance(value, dict), f"{path.relative_to(ROOT)} must contain an object")
    return value


def validate(contract: dict[str, Any], matrix: dict[str, Any], workbench_profile: str,
             repl: str, screen: str, screen_overlay: str, interrupt: str,
             presmoke: str) -> None:
    require(contract.get("format") == "lisp65-v11-wave3-fail-fast-v1",
            "fail-fast format drift")
    require(contract.get("status") == "wave3-repin-authorized-hardware-not-run",
            "Wave-3 fail-fast lifecycle status drift")
    authority = contract.get("authority")
    require(isinstance(authority, dict)
            and "non-authoritative" in authority.get("dry_variants", "")
            and "receipt-less" in authority.get("hardware_presmoke", ""),
            "dry/presmoke authority limit missing")
    require(matrix.get("execution_order") == "new-surfaces-first",
            "hardware matrix does not require new surfaces first")
    require(matrix.get("claims_before_hardware") == "none",
            "dry variants must not claim hardware evidence")

    cases = matrix.get("cases")
    require(isinstance(cases, list) and cases, "generated hardware cases missing")
    seen_old = False
    new_ids: list[str] = []
    for row in cases:
        require(isinstance(row, dict), "hardware case row must be an object")
        is_new = row.get("new_surface") is True
        if not is_new:
            seen_old = True
        else:
            require(not seen_old, f"new case appears after an old case: {row.get('id')}")
            new_ids.append(str(row.get("id")))
        require(row.get("fidelity") == "emulator-dry-plus-hardware",
                f"dry variant missing: {row.get('id')}")
        require(row.get("receipt_policy") ==
                "dry-variant-non-authoritative; hardware-exactly-once",
                f"receipt policy drift: {row.get('id')}")
    require(set(new_ids) == set(contract.get("new_cases_first", [])),
            f"new-case inventory drift: matrix={sorted(new_ids)}")

    dry = contract.get("dry_variants")
    require(isinstance(dry, list) and len(dry) == 3, "three dry-variant classes required")
    for row in dry:
        require(isinstance(row.get("command"), str) and row["command"].startswith("make "),
                f"dry command missing: {row.get('id')}")
        require("only" in row.get("claim", ""), f"dry claim limit missing: {row.get('id')}")

    require(contract.get("color_scroll_product_status") ==
            "final-fallback-to-c2-after-authorized-retry-hard-gate",
            "color-scroll probe status is not explicit")
    require("-DLISP65_SCREEN_EDMA_SCROLL" not in workbench_profile,
            "C2-deferred color scroll remains active in the product profile")
    require("LISP65_REPL_IDE_TOGGLE" not in repl,
            "retired RUN/STOP editor toggle remains in the REPL")
    require("M65_COLOR_RAM_28 + context->columns" in screen_overlay
            and "M65_COLOR_RAM_28 + context->copy_bytes" in screen_overlay,
            "isolated screen-scroll probe lacks color copy/fill jobs")
    require("STKEY" in interrupt and "LISP65_ERR_STOPPED" in interrupt,
            "RUN/STOP abort seam missing")
    require("receipt" in presmoke.lower() and "forbidden" in presmoke.lower(),
            "presmoke does not explicitly forbid receipts")
    require("evidence" not in presmoke.lower(),
            "presmoke must not write or name evidence artifacts")
    require("no old banner color masks" not in presmoke,
            "C2-deferred color-scroll rider remains a Wave-3 pass criterion")


def inputs() -> tuple[dict[str, Any], dict[str, Any], str, str, str, str, str, str]:
    return (
        read_json(CONTRACT),
        read_json(CASES),
        (ROOT / "config/workbench.mk").read_text(encoding="utf-8"),
        (ROOT / "src/repl.c").read_text(encoding="utf-8"),
        (ROOT / "src/screen.c").read_text(encoding="utf-8"),
        (ROOT / "src/screen_scroll_overlay.c").read_text(encoding="utf-8"),
        (ROOT / "src/interrupt.c").read_text(encoding="utf-8"),
        PRESMOKE.read_text(encoding="utf-8"),
    )


def check() -> None:
    validate(*inputs())
    contract, matrix, *_ = inputs()
    new_count = sum(row.get("new_surface") is True for row in matrix["cases"])
    print(f"v11-wave3-fail-fast: PASS new-first={new_count} "
          f"dry-classes={len(contract['dry_variants'])} receiptless=true")


def selftest() -> None:
    args = list(inputs())
    validate(*args)
    reordered = copy.deepcopy(args[1])
    first_old = next(i for i, row in enumerate(reordered["cases"])
                     if row.get("new_surface") is not True)
    reordered["cases"][0], reordered["cases"][first_old] = (
        reordered["cases"][first_old], reordered["cases"][0])
    try:
        validate(args[0], reordered, *args[2:])
    except FailFastError:
        pass
    else:
        raise FailFastError("new-case ordering mutation was accepted")
    unsafe = copy.deepcopy(args[1])
    unsafe["cases"][0]["receipt_policy"] = "dry-pass-is-hardware-pass"
    try:
        validate(args[0], unsafe, *args[2:])
    except FailFastError:
        pass
    else:
        raise FailFastError("authority mutation was accepted")
    print("v11-wave3-fail-fast: SELFTEST PASS mutations=2")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "selftest"))
    args = parser.parse_args(argv)
    try:
        selftest() if args.command == "selftest" else check()
    except FailFastError as exc:
        print(f"v11-wave3-fail-fast: FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
