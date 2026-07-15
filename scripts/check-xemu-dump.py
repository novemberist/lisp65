#!/usr/bin/env python3
"""Find an expected ASCII marker anywhere in an xemu memory dump.

The check deliberately ignores the exact dump layout. A marker from the $C000
output sink is sufficient for a pass.
"""
import sys


def main(argv):
    if len(argv) != 3:
        print("usage: check-xemu-dump.py path/to/dump.bin \"expected string\"",
              file=sys.stderr)
        return 2
    data = open(argv[1], "rb").read()
    expect = argv[2].encode("latin-1")
    if expect in data:
        print(f"xemu smoke OK: found {argv[2]!r} in dump ({len(data)} bytes)")
        return 0
    print(f"xemu smoke FAIL: {argv[2]!r} is absent from dump ({len(data)} bytes)",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
