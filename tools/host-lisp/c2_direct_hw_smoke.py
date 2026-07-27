#!/usr/bin/env python3
"""Build the receipt-less C2.1 direct-Attic MEGA65 pre-smoke."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_direct_oracles as O  # noqa: E402
import c2_direct_target as T  # noqa: E402

BUILD = ROOT / "build/c2.1/direct-hw-smoke"
HEADER = BUILD / "c2-direct-vectors.h"
SHELF = BUILD / "c2-direct-shelf.bin"
PRG = BUILD / "c2-direct-hw-smoke.prg"
MAP = BUILD / "c2-direct-hw-smoke.map"
CC = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
PROOF = ROOT / "scripts/c2-direct-target-main.c"
MAIN = ROOT / "scripts/c2-direct-hw-smoke-main.c"
IRQ = ROOT / "scripts/c2-direct-hw-smoke-irq.s"
SCREEN = ROOT / "src/screen.c"


class SmokeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    target, code, metadata = O.target_inputs()
    shelf = O.build_shelf(target, code, metadata)
    require(len(shelf) == 319, "proof shelf size drift")
    HEADER.write_bytes(T.generate_header())
    SHELF.write_bytes(shelf)
    result = subprocess.run([
        str(CC), "-mllvm", "-rng-seed=0", "-std=c99", "-Os",
        "-DLISP65_SCREEN_DRIVER", "-DC2_TARGET_LINK_ONLY",
        "-DC2_TARGET_MAIN=c2_target_proof_main",
        "-DC2_TARGET_REFILL_FUNCTION=c2_hw_refill",
        "-I", str(BUILD), "-I", str(ROOT / "scripts"), "-I", str(ROOT / "src"),
        str(PROOF), str(MAIN), str(IRQ), str(SCREEN),
        "-Wl,--icf=none", "-Wl,-Map," + str(MAP), "-o", str(PRG),
    ], cwd=ROOT, capture_output=True, text=True, timeout=180, check=False)
    require(result.returncode == 0,
            f"hardware-smoke link failed: {(result.stderr or result.stdout).strip()}")
    require(not result.stdout and not result.stderr, "hardware-smoke compiler diagnostics")
    require(PRG.is_file() and Path(str(PRG) + ".elf").is_file(),
            "hardware-smoke artifacts absent")
    end = 0x2001 + PRG.stat().st_size - 2
    require(end < 0xC000, "hardware-smoke PRG crosses etherload $C000 invariant")
    print(
        "c2-direct-hw-smoke: BUILT receipt-less "
        f"shelf={len(shelf)}:{digest(SHELF)} prg={PRG.stat().st_size}:{digest(PRG)} "
        f"end=${end:04x}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "paths"))
    args = parser.parse_args()
    try:
        if args.action == "build":
            build()
        else:
            require(PRG.is_file() and SHELF.is_file(), "build the smoke first")
            print(f"{SHELF}\n{PRG}")
        return 0
    except (OSError, subprocess.SubprocessError, SmokeError, O.OracleError) as error:
        print(f"c2-direct-hw-smoke: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
