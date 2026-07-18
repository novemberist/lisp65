#!/usr/bin/env python3
"""Independent observation oracle for the 1.1-E C carrier gate."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess


EXPECTED = (
    "v11-buffer-carrier-observation-v1 checks=17 failures=0 "
    "length=4 last=255 copy=abc freeze=same oom=closed\n"
)


class OracleError(RuntimeError):
    pass


def verify_observation(text: str) -> None:
    if text != EXPECTED:
        raise OracleError("carrier observation differs from independent model")


def selftest() -> None:
    verify_observation(EXPECTED)
    for mutation in (
        EXPECTED.replace("last=255", "last=254"),
        EXPECTED.replace("oom=closed", "oom=open"),
        EXPECTED.replace("failures=0", "failures=1"),
    ):
        try:
            verify_observation(mutation)
        except OracleError:
            pass
        else:
            raise OracleError("mutated observation accepted")


def run(binary: Path) -> None:
    completed = subprocess.run(
        [str(binary)], check=False, text=True, capture_output=True,
    )
    if completed.returncode:
        raise OracleError(
            f"carrier binary failed ({completed.returncode}): {completed.stderr.strip()}"
        )
    verify_observation(completed.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        print("v11-buffer-oracle: SELFTEST PASS mutations=3")
    if args.binary:
        run(args.binary)
        print("v11-buffer-oracle: PASS independent-observation=yes")
    if not args.selftest and not args.binary:
        parser.error("one of --selftest or --binary is required")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, OracleError) as exc:
        print(f"v11-buffer-oracle: FAIL: {exc}")
        raise SystemExit(1)
