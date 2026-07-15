#!/usr/bin/env python3
"""Compatibility CLI for the normative L65M disk-lib validator."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

from l65m_contract import ContractError, validate_image  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <fasl-file>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        summary = validate_image(path.read_bytes())
    except OSError as exc:
        print(f"FASL-VALIDATE FAIL: cannot read {path}: {exc}", file=sys.stderr)
        return 2
    except ContractError as exc:
        print(f"FASL-VALIDATE FAIL: {exc.code}: {exc}", file=sys.stderr)
        return 1
    print("FASL OK: " + json.dumps(asdict(summary), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
