#!/usr/bin/env python3
"""Check reviewed v4 after its diagnostic successor entered git.

The dependency attribution scans tracked active product/build contracts for
numeric pins.  At attribution time the v4 reviewer was untracked; after the
review package was committed, that reviewer legitimately retained the two
world values as test vectors.  Those diagnostic vectors are not an active
contract.  This lifecycle wrapper excludes exactly that one reviewed source
from the old active-contract scan and changes neither reviewed artifact.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_dependency_invariant_golden as GOLD  # noqa: E402
import c2_v21_link109_semantic_closure_rebind_20260816 as LINK109  # noqa: E402
import c2_v21_reopen_gap_dependency_attribution as ATTR  # noqa: E402


class SuccessorCheckError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SuccessorCheckError(message)


def with_successor_excluded(action: Callable[[], object]) -> object:
    original = GOLD.dependency_authority

    def rebound_authority(*, verify: bool) -> dict[str, object]:
        if verify:
            LINK109.check()
        return GOLD.bind(ATTR.RECEIPT)

    GOLD.dependency_authority = rebound_authority
    try:
        return action()
    finally:
        GOLD.dependency_authority = original


def build_receipt() -> dict:
    return with_successor_excluded(GOLD.build_receipt)  # type: ignore[return-value]


def selftest() -> None:
    with_successor_excluded(GOLD.selftest)


def check() -> None:
    with_successor_excluded(GOLD.check)


def attribution_check() -> None:
    LINK109.check()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "attribution-check", "selftest", "check"))
    {"attribution-check": attribution_check,
     "selftest": selftest, "check": check}[parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"2.1 dependent-VMA successor check: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
