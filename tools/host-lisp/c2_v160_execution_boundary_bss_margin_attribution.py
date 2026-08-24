#!/usr/bin/env python3
"""Attribute the execution-boundary card's protected BSS-margin red."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OLD = ROOT / "build/c2.3/v1.6-boot-refill-generator-template-card/wplto/resident-island-seed.prg.map"
RED = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-projection-replacement-card/wplto/resident-island-seed.prg.map"
CARD_RED = ARCH / "c2.3-v1.6-execution-boundary-backstop-projection-replacement-card-final-red.json"
OUT = ARCH / "c2.3-v1.6-execution-boundary-bss-margin-attribution.json"
CLANG = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
LD = ROOT / "tools/llvm-mos/bin/ld.lld"
NM = ROOT / "tools/llvm-mos/bin/llvm-nm"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def geometry(path: Path) -> dict[str, Any]:
    text = path.read_text()
    match = re.search(r"^\s*b9ca\s+b9ca\s+([0-9a-f]+)\s+1\s+\.bss$", text,
                      re.MULTILINE)
    require(match is not None, f"BSS geometry absent: {path}")
    size = int(match.group(1), 16); end = 0xB9CA + size
    return {"address": "0xb9ca", "bytes": size, "end": f"0x{end:04x}",
            "validation_margin_to_0xc000": 0xC000 - end}


def alias_probe() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="c2-local-alias-") as raw:
        root = Path(raw)
        (root / "owner.s").write_text(
            '.section .bss.owner,"aw",@nobits\n.local private_cell\n'
            'private_cell: .space 1\n.globl linked_alias\n'
            '.set linked_alias, private_cell\n')
        (root / "consumer.s").write_text(
            '.text\n.globl _start\n_start:\n lda linked_alias\n rts\n')
        (root / "link.ld").write_text(
            'SECTIONS { .text 0x2000 : { *(.text) } '
            '.bss 0x3000 : { *(.bss*) } }\n')
        for name in ("owner", "consumer"):
            subprocess.run([str(CLANG), "-c", str(root / f"{name}.s"), "-o",
                            str(root / f"{name}.o")], check=True)
        subprocess.run([str(LD), "-T", str(root / "link.ld"),
                        str(root / "owner.o"), str(root / "consumer.o"),
                        "-o", str(root / "probe.elf")], check=True)
        nm = subprocess.run([str(NM), "--format=posix", str(root / "probe.elf")],
            check=True, text=True, stdout=subprocess.PIPE).stdout
        require(re.search(r"^linked_alias B 3000 0$", nm, re.MULTILINE)
                and re.search(r"^private_cell b 3000 0$", nm, re.MULTILINE),
                "local-owner alias did not resolve to the same byte")
        return {"private_cell": "0x3000", "linked_alias": "0x3000",
                "allocated_bytes": 1, "extra_alias_bytes": 0,
                "scope": "object/linker mechanism only; full-LTO price unproven"}


def derive() -> dict[str, Any]:
    old = geometry(OLD); red = geometry(RED)
    require(old["bytes"] == 1585 and old["validation_margin_to_0xc000"] == 5
            and red["bytes"] == 1586 and red["validation_margin_to_0xc000"] == 4,
            "protected-margin attribution geometry drift")
    receipt = json.loads(CARD_RED.read_text())
    require(receipt["attempt_accounting"]["WPLTO_runs"] == 1
            and receipt["attempt_accounting"]["product_link_attempts"] == 1,
            "card-red accounting drift")
    return {"format": "lisp65-c2-v160-execution-boundary-bss-margin-attribution-v1",
        "status": "ATTRIBUTED: GLOBAL VISIBILITY SPENDS ONE PROTECTED BSS MARGIN BYTE",
        "recorded_on": "2026-08-23",
        "inputs": {"predecessor_map": bind(OLD), "red_map": bind(RED),
                   "card_Final_Red": bind(CARD_RED)},
        "two_worlds": {"predecessor": old, "failed_candidate": red,
                       "delta_bytes": 1},
        "mechanism": {"writer": "execution-boundary implementation",
            "change": "four existing private C cells were made externally global for assembler relocation",
            "effect": "whole-program LTO BSS selection/layout grew by one real byte",
            "linker_guards": ["ordinary full-map chain drift",
                               "five-byte validation margin drifted; it is not capacity"]},
        "classification": {"stored_world_pin": False,
            "capacity_wall": True, "product_backstop_semantics_exonerated": True,
            "reason": "the five-byte gap is explicitly a validation margin, not spendable capacity"},
        "replacement_price_candidate": {"form":
            "retain C internal linkage; export zero-byte global aliases from each owning object and consume only aliases in assembler",
            "mechanism_probe": alias_probe(),
            "expected_BSS_delta": 0,
            "claim_limit": "mechanism-priced only; a fresh full-LTO card requires explicit authorization"},
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "media_builds": 0,
            "device_contacts": 0},
        "next": "reviewer/owner price decision; no third card under self-disposition"}


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"write", "check"},
            "usage: c2_v160_execution_boundary_bss_margin_attribution.py write|check")
    value = derive(); raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if sys.argv[1] == "write": OUT.write_bytes(raw)
    else: require(OUT.read_bytes() == raw, "BSS-margin attribution receipt drift")
    print("v1.6 execution boundary BSS margin: ATTRIBUTED delta=+1 protected=5->4")
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 execution boundary BSS margin: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
