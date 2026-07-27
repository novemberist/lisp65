#!/usr/bin/env python3
"""Expose the target ABI's MK_BCODE constructor to C2 host proofs.

The host side deliberately does not reproduce the tag arithmetic.  It builds
one tiny native helper which includes src/obj.h and materializes the complete
12-bit constructor domain.  Python consumers therefore query the same macro
that the product decoder uses.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
OBJ_HEADER = ROOT / "src/obj.h"
DOMAIN_SIZE = 4096


class BcodeContractError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def constructor_table() -> tuple[int, ...]:
    source = r'''#include <stdint.h>
#include <stdio.h>
#include "src/obj.h"
int main(void) {
    uint16_t i;
    for (i = 0; i < 4096u; ++i)
        if (printf("%04x\n", (unsigned)(uint16_t)MK_BCODE(i)) < 0)
            return 2;
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="lisp65-mk-bcode-") as raw:
        directory = Path(raw)
        c_path = directory / "mk_bcode.c"
        executable = directory / "mk_bcode"
        c_path.write_text(source, encoding="ascii")
        compiler = os.environ.get("CC", "cc")
        built = subprocess.run(
            [compiler, "-std=c99", "-Os", "-Wall", "-Wextra", "-Werror",
             "-I", str(ROOT), str(c_path), "-o", str(executable)],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        if built.returncode or built.stdout or built.stderr:
            raise BcodeContractError(
                "MK_BCODE ABI helper did not compile cleanly: "
                + (built.stderr or built.stdout).strip())
        ran = subprocess.run(
            [str(executable)], cwd=ROOT, capture_output=True, text=True,
            check=False,
        )
        if ran.returncode or ran.stderr:
            raise BcodeContractError(
                "MK_BCODE ABI helper failed: " + ran.stderr.strip())
    try:
        table = tuple(int(line, 16) for line in ran.stdout.splitlines())
    except ValueError as error:
        raise BcodeContractError("MK_BCODE ABI helper emitted non-hex data") from error
    if (len(table) != DOMAIN_SIZE or len(set(table)) != DOMAIN_SIZE
            or table[0] != 0xC000 or table[-1] != 0xDFFE
            or any(value & 1 for value in table)):
        raise BcodeContractError("MK_BCODE ABI constructor domain is not canonical")
    return table


@lru_cache(maxsize=1)
def _reverse_table() -> dict[int, int]:
    return {value: index for index, value in enumerate(constructor_table())}


def mk_bcode(directory_ordinal: int) -> int:
    if not 0 <= directory_ordinal < DOMAIN_SIZE:
        raise BcodeContractError(
            f"directory ordinal outside MK_BCODE domain: {directory_ordinal}")
    return constructor_table()[directory_ordinal]


def is_bcode_value(value: int) -> bool:
    return value in _reverse_table()


def bcode_index(value: int) -> int:
    try:
        return _reverse_table()[value]
    except KeyError as error:
        raise BcodeContractError(f"not a canonical BCODE value: 0x{value:04x}") from error


def require_published_entry(value: int, expected_ordinal: int) -> None:
    if value & 1:
        raise BcodeContractError(
            f"published entry decodes as a Fixnum: 0x{value:04x}")
    expected = mk_bcode(expected_ordinal)
    if not is_bcode_value(value) or value != expected:
        raise BcodeContractError(
            f"published entry 0x{value:04x} != MK_BCODE({expected_ordinal}) "
            f"0x{expected:04x}")


def source_binding() -> dict[str, object]:
    data = OBJ_HEADER.read_bytes()
    return {
        "path": OBJ_HEADER.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "constructor": "MK_BCODE",
        "host_formula_reimplemented": False,
    }


def mutation_selftest() -> dict[str, str]:
    expected_ordinal = 489
    expected = mk_bcode(expected_ordinal)
    rows = {"canonical-mk-bcode": "passed"}
    cases = {
        "missing-tag-scale-fixnum": 0xC000 + expected_ordinal,
        "missing-image-base": mk_bcode(239),
        "below-bcode-domain": 0xBFFE,
        "above-bcode-domain": 0xE000,
    }
    for label, value in cases.items():
        try:
            require_published_entry(value, expected_ordinal)
        except BcodeContractError:
            rows[label] = "rejected"
        else:
            raise BcodeContractError(f"BCODE mutation accepted: {label}")
    require_published_entry(expected, expected_ordinal)
    if len(rows) != 5:
        raise BcodeContractError("BCODE mutation matrix did not close")
    return rows


if __name__ == "__main__":
    matrix = mutation_selftest()
    print("c2-bcode-contract: SELFTEST PASS "
          f"domain={len(constructor_table())} negatives={len(matrix) - 1}")
