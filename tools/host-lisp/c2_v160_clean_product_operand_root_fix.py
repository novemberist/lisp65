#!/usr/bin/env python3
"""Build the one Finish-Plan fix round with nested results rooted pre-refill."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_clean_product_candidate as BASE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-clean-product-operand-root-fix"
PREFLIGHT = ROOT / "build/c2.3/v1.6-clean-product-operand-root-fix-preflight"
RECEIPT = ARCH / "c2.3-v1.6-clean-product-operand-root-fix-receipt.json"
DRIVER = Path(__file__).resolve()


def configure_paths() -> None:
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
    BASE.INVOCATION = PREFLIGHT / "candidate-invocation.json"
    BASE.ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    BASE.PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
    BASE.PROFILE = BUILD / "wplto/resolved-profile.txt"
    BASE.PRODUCER_RESULT = BUILD / "producer-result.json"
    BASE.SCOPE_RESULT = BUILD / "owner-scope-result.json"
    BASE.ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
    BASE.RECEIPT = RECEIPT
    BASE.DRIVER = DRIVER
    BASE.FORMAT = "lisp65-c2-v160-clean-product-operand-root-fix-v1"
    BASE.STATUS = "PASS: V1.6 CLEAN PRODUCT OPERAND ROOT FIX FINAL GREEN"


def source_gate() -> None:
    source = (ROOT / "src/vm.c").read_text(encoding="utf-8")
    call = source[source.index("        case OP_CALL: {"):
                  source.index("        case OP_TAILCALL: {")]
    callprim = source[source.index("        case OP_CALLPRIM: {"):
                      source.index("#if defined(LISP65_COMPILE_REPL)",
                                   source.index("        case OP_CALLPRIM: {"))]
    for name, body in (("OP_CALL", call), ("OP_CALLPRIM", callprim)):
        push = body.index("PUSH(res);")
        repair = body.index("BUF_ENSURE_MINE(pcur);")
        if push >= repair:
            raise RuntimeError(f"{name} leaves nested result unrooted across caller refill")


def run(action: str) -> None:
    configure_paths()
    # This hypothesis was device-widerlegt and moved with Comfort's sealed
    # fault file to v1.7.  Historical check remains read-only over its emitted
    # pair; only a newly authorized build attempt may demand its source form.
    if action != "check":
        source_gate()
    {"preflight": BASE.preflight, "build": BASE.build, "check": BASE.check,
     "_produce": BASE.produce_child, "_scope": BASE.scope_child,
     "_accept": BASE.acceptance_child}[action]()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "build", "check",
                                           "_produce", "_scope", "_accept"))
    run(parser.parse_args().action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 operand-root fix: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
