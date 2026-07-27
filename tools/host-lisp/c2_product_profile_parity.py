#!/usr/bin/env python3
"""Bind the C2 product compiler to the canonical Dialect-v2 profile bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex


ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"
MAKE_VARIABLE = "V2_CAPABILITY_CARRIER_G5_V2_DEFINES"
EXPECTED_COUNT = 8


def _name(definition: str) -> str:
    value = definition[2:] if definition.startswith("-D") else definition
    return value.split("=", 1)[0]


def canonical_v2_product_defines(text: str | None = None) -> tuple[str, ...]:
    """Read the one-line canonical bundle without maintaining a second list."""
    source = MAKEFILE.read_text(encoding="utf-8") if text is None else text
    match = re.search(
        rf"^{re.escape(MAKE_VARIABLE)}\s*:?=\s*(.+)$", source, re.MULTILINE)
    if not match:
        raise RuntimeError(f"missing canonical make variable {MAKE_VARIABLE}")
    tokens = shlex.split(match.group(1), comments=False, posix=True)
    if not tokens or any(not token.startswith("-D") for token in tokens):
        raise RuntimeError(f"{MAKE_VARIABLE} contains a non-define token")
    names = tuple(_name(token) for token in tokens)
    if len(names) != EXPECTED_COUNT or len(set(names)) != len(names):
        raise RuntimeError(
            f"{MAKE_VARIABLE} must contain {EXPECTED_COUNT} unique defines, "
            f"found {len(names)}/{len(set(names))}")
    if any("=" in token for token in tokens):
        raise RuntimeError(f"{MAKE_VARIABLE} may contain only boolean defines")
    return names


def _belongs_to_v2_profile(name: str) -> bool:
    return (name.startswith("LISP65_DIALECT_")
            or name.startswith("LISP65_V2_")
            or name.startswith("LISP65_VM_NATIVE_"))


def profile_difference(definitions: list[str] | tuple[str, ...],
                       expected: tuple[str, ...] | None = None
                       ) -> tuple[list[str], list[str], list[str]]:
    canonical = canonical_v2_product_defines() if expected is None else expected
    names = [_name(value) for value in definitions]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    selected = {name for name in names if _belongs_to_v2_profile(name)}
    required = set(canonical)
    return (sorted(required - selected), sorted(selected - required), duplicates)


def require_exact_v2_profile(definitions: list[str] | tuple[str, ...],
                             expected: tuple[str, ...] | None = None) -> None:
    missing, extra, duplicates = profile_difference(definitions, expected)
    if missing or extra or duplicates:
        raise RuntimeError(
            "C2 v2 profile parity red: "
            f"missing={missing} extra={extra} duplicates={duplicates}")


def mutation_selftest() -> dict[str, object]:
    expected = canonical_v2_product_defines()
    require_exact_v2_profile(list(expected), expected)
    removals: dict[str, str] = {}
    for removed in expected:
        candidate = [name for name in expected if name != removed]
        try:
            require_exact_v2_profile(candidate, expected)
        except RuntimeError:
            removals[removed] = "rejected"
        else:
            raise AssertionError(f"missing profile define was accepted: {removed}")
    extra_name = "LISP65_V2_UNDECLARED_CAPABILITY"
    try:
        require_exact_v2_profile([*expected, extra_name], expected)
    except RuntimeError:
        extra = "rejected"
    else:
        raise AssertionError("overbroad v2 profile was accepted")
    try:
        require_exact_v2_profile([*expected, expected[0]], expected)
    except RuntimeError:
        duplicate = "rejected"
    else:
        raise AssertionError("duplicate v2 profile define was accepted")
    return {
        "valid_exact_bundle": "passed",
        "missing_define_mutations": removals,
        "missing_define_mutations_rejected": len(removals),
        "overbroad_define_mutation": {extra_name: extra},
        "duplicate_define_mutation": {expected[0]: duplicate},
    }


def profile_report(definitions: list[str] | tuple[str, ...]) -> dict[str, object]:
    expected = canonical_v2_product_defines()
    require_exact_v2_profile(definitions, expected)
    selected = sorted(
        _name(value) for value in definitions
        if _belongs_to_v2_profile(_name(value)))
    matrix = mutation_selftest()
    return {
        "format": "lisp65-c2-product-v2-profile-parity-v1",
        "status": "passed",
        "truth_source": {
            "path": str(MAKEFILE.relative_to(ROOT)),
            "sha256": hashlib.sha256(MAKEFILE.read_bytes()).hexdigest(),
            "variable": MAKE_VARIABLE,
        },
        "expected_defines": list(expected),
        "actual_profile_defines": selected,
        "missing": [],
        "extra": [],
        "bidirectional": True,
        "mutation_matrix": matrix,
        "claim_limit": (
            "Compile-profile equality and mutation proof only; no link, "
            "capacity, hardware, promotion or release claim."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if not args.selftest:
        parser.error("--selftest is required; product checks run inside the C2 linker")
    report = mutation_selftest()
    print("c2-product-profile-parity: SELFTEST PASS "
          f"missing={report['missing_define_mutations_rejected']}/8 "
          "overbroad=1/1 duplicate=1/1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
