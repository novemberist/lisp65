#!/usr/bin/env python3
"""Candidate-derived Link-116 placement contract.

The reader and the mapped-far facade are owned addresses.  The ordinary-text
end and the gap before that facade are properties of the candidate that was
actually emitted; they are measurements, not inherited constants.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ELF = ROOT / (
    "build/c2.3/v2.1-wysiwyg-text-recovery-replacement-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()


class ContractError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ContractError(message)


def derive(elf: Path = ELF) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    reader = truth.symbol("c2_map_cpu_read")
    end = text.address + text.bytes
    reserve = facade.address - end
    require(reader.value == 0x2277 and reader.bytes == 189,
            "owned MAP-CPU reader identity drift")
    require(facade.address == 0xB3B0 and facade.bytes == 98,
            "owned mapped-far facade identity drift")
    require(end <= facade.address and reserve == facade.address - end,
            "ordinary text overlaps the fixed facade")
    return {
        "status": "PASS: ordinary end/reserve derived from emitted candidate",
        "authority": DRIVER.relative_to(ROOT).as_posix(),
        "reader_address": reader.value,
        "reader_bytes": reader.bytes,
        "ordinary_reserve_bytes": reserve,
        "text_end_exclusive": end,
        "facade_address": facade.address,
        "facade_bytes": facade.bytes,
        "delta_bytes": 1,
        "derivation": {
            "ordinary_end": ".text.sh_addr + .text.sh_size",
            "ordinary_reserve": (
                ".lisp65_c2_mapped_far_facade.sh_addr - ordinary_end"),
            "historical_reserve_consumed": False,
        },
    }


def validate(value: dict[str, Any]) -> None:
    require(value["status"] ==
                "PASS: ordinary end/reserve derived from emitted candidate"
            and value["reader_address"] == 0x2277
            and value["reader_bytes"] == 189
            and value["facade_address"] == 0xB3B0
            and value["facade_bytes"] == 98
            and value["text_end_exclusive"] +
                value["ordinary_reserve_bytes"] == value["facade_address"]
            and value["ordinary_reserve_bytes"] >= 0
            and value["derivation"]["ordinary_end"] ==
                ".text.sh_addr + .text.sh_size"
            and value["derivation"]["ordinary_reserve"] ==
                ".lisp65_c2_mapped_far_facade.sh_addr - ordinary_end"
            and value["derivation"]["historical_reserve_consumed"] is False,
            "candidate-derived placement contract drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-prior-world-reserve": lambda x: x.update(
            ordinary_reserve_bytes=1),
        "restore-prior-world-text-end": lambda x: x.update(
            text_end_exclusive=0xB3AF),
        "consume-historical-reserve": lambda x: x["derivation"].update(
            historical_reserve_consumed=True),
        "move-reader": lambda x: x.update(reader_address=0x2278),
        "resize-reader": lambda x: x.update(reader_bytes=188),
        "move-facade": lambda x: x.update(facade_address=0xB3B1),
        "resize-facade": lambda x: x.update(facade_bytes=97),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except ContractError:
            rejected.append(name)
    require(rejected == list(cases), "candidate-placement mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check",))
    parser.parse_args()
    value = derive()
    validate(value)
    rejected = mutations(value)
    print("WYSIWYG candidate placement: PASS "
          f"reserve={value['ordinary_reserve_bytes']} mutations={len(rejected)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"WYSIWYG candidate placement: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
