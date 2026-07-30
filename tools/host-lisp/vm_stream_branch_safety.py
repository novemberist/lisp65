#!/usr/bin/env python3
"""Pin relative VM branches to the logical streamed-payload PC domain."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


def check(text: str) -> None:
    required = (
        (
            "#define VM_LOGICAL_PC_HELPER \\\n"
            '    __attribute__((noinline, section(".lisp65_c2_kernal_window.c2_resident")))'
        ),
        "static VM_LOGICAL_PC_HELPER uint8_t\nvm_logical_relative_target(",
        "vm_logical_relative_target(uint16_t next, uint16_t payload_length,",
        "#define JUMP_REL(delta_)",
        "uint16_t target__",
        "vm_logical_relative_target(next__, payload_len,",
        "win = target__; winlen = 0; ip = code; streaming = 1;",
        "case OP_JMPREL:",
        "case OP_JFALSEREL:",
        "goto relative_branch;",
        "relative_branch:",
        "if (a == NIL) JUMP_REL(d);",
    )
    missing = [needle for needle in required if needle not in text]
    if missing:
        raise ValueError("logical branch seam missing: " + ", ".join(missing))

    dispatch = re.search(
        r"case OP_JMPREL:.*?relative_branch:.*?break;", text, re.S)
    if not dispatch or re.search(r"\bip\s*\+=", dispatch.group(0)):
        raise ValueError("relative branch dispatch bypasses logical-PC seam")
    if text.count("JUMP_REL(d)") != 1:
        raise ValueError("relative branch seam is not emitted exactly once")


def selftest(text: str) -> int:
    mutations = (
        text.replace(
            "if (a == NIL) JUMP_REL(d);",
            "if (a == NIL) ip += d;",
            1,
        ),
        text.replace(
            (
                "#define VM_LOGICAL_PC_HELPER \\\n"
                '    __attribute__((noinline, section(".lisp65_c2_kernal_window.c2_resident")))'
            ),
            (
                "#define VM_LOGICAL_PC_HELPER \\\n"
                '    __attribute__((noinline, section(".text")))'
            ),
            1,
        ),
    )
    rejected = 0
    for mutation in mutations:
        if mutation == text:
            raise ValueError("selftest could not install branch-seam mutation")
        try:
            check(mutation)
        except ValueError:
            rejected += 1
    if rejected != len(mutations):
        raise ValueError("relative-branch mutation was accepted")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    text = args.source.read_text(encoding="utf-8")
    check(text)
    mutations = selftest(text)
    print(
        "vm-stream-branch-safety: PASS "
        "logical-pc=uint16 shared-dispatch=one e000-helper=required "
        f"cross-window-reload=required mutations={mutations}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
