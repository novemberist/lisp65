#!/usr/bin/env python3
"""Check the exact byte stream produced by output-smoke-main."""

from pathlib import Path
import sys


EXPECTED = b'hi\n"x"\nabc ' + b'\x22say \x5c\x22hi\x5c\x22\x5c\x5c\x22\n'


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check-output-smoke.py output-file", file=sys.stderr)
        return 2
    got = Path(argv[1]).read_bytes()
    if got != EXPECTED:
        print(f"output-smoke: FAIL expected={EXPECTED!r} got={got!r}", file=sys.stderr)
        return 1
    print(f"output-smoke: PASS bytes={len(got)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
