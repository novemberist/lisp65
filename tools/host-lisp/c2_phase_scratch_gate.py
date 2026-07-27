#!/usr/bin/env python3
"""Compile and execute the product's C2 shared-state ownership guard."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cc", default=os.environ.get("CC", "cc"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="c2-phase-scratch-") as tmp:
        target = Path(tmp) / "gate"
        subprocess.run([
            args.cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2",
            "-DLISP65_C2_PRODUCT_CUT", "-I", str(ROOT / "src"),
            str(ROOT / "src/c2_phase_scratch.c"),
            str(ROOT / "scripts/c2-phase-scratch-main.c"),
            "-o", str(target),
        ], check=True)
        subprocess.run([str(target)], check=True)
    print("c2-phase-scratch-gate: PASS overlap-reject=yes same-owner-reject=yes "
          "wrong-release-reject=yes literal-cursor-cutpoint=yes mutations=5/5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
