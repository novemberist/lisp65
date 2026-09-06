#!/usr/bin/env python3
"""Seal and check the first Card-2 F011 final-link capacity red."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CARD1_MAP = ROOT / "build/2.6/card1-sidx-product-r2/wplto/lisp65-c2-substitution-linked.prg.map"
BUILD = ROOT / "build/2.6/card2-f011-product-r1/wplto"
RED_MAP = BUILD / "resident-island-seed.prg.map"
LTO = BUILD / "resident-island-seed.prg.lto.o"
STDERR = BUILD / "resident-island-seed.prg.link.stderr.txt"
STDOUT = BUILD / "resident-island-seed.prg.link.stdout.txt"
PROFILE = BUILD / "resolved-profile.txt"
ELF = BUILD / "lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "lisp65-c2-substitution-linked.prg"
PREFLIGHT = ARCH / "block-2.6-card2-f011-product-r1-preflight.json"
PRICE = ARCH / "block-2.6-card2-f011-text-budget-pricing.json"
OUT = ARCH / "block-2.6-card2-f011-product-r1-final-link-red.json"
REPORT = ROOT / "docs/planning/2.6-card2-f011-product-r1-final-link-red.md"
FORMAT = "lisp65-block-2.6-card2-f011-product-r1-final-link-red-v1"


class RedError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RedError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def section(path: Path, name: str) -> dict[str, int | str]:
    match = re.search(
        rf"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+{re.escape(name)}$",
        path.read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
    require(match is not None, f"section absent from map: {name}")
    vma, lma, size = (int(value, 16) for value in match.groups())
    return {"VMA": f"0x{vma:x}", "LMA": f"0x{lma:x}", "bytes": size,
            "VMA_end": f"0x{vma + size:x}", "LMA_end": f"0x{lma + size:x}"}


def symbol_address(path: Path, name: str) -> int | None:
    match = re.search(
        rf"^\s*([0-9a-f]+)\s+[0-9a-f]+\s+[0-9a-f]+\s+\d+\s+{re.escape(name)}$",
        path.read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
    return None if match is None else int(match.group(1), 16)


def derive() -> dict[str, Any]:
    stderr = STDERR.read_text(encoding="utf-8", errors="replace")
    require("ordinary full-map chain drift" in stderr
            and "five-byte validation margin floor violated" in stderr,
            "the two final-link walls were not the observed stop")
    require(LTO.is_file() and RED_MAP.is_file() and not ELF.exists()
            and not PRG.exists(),
            "red boundary must retain LTO/map and no final product pair")

    predecessor = {name: section(CARD1_MAP, name) for name in (
        ".text", ".lisp65_c2_mapped_far_facade",
        ".lisp65_resident_island", ".rodata", ".data", ".bss")}
    candidate = {name: section(RED_MAP, name) for name in (
        ".text", ".lisp65_c2_mapped_far_facade",
        ".lisp65_resident_island", ".lisp65_c2_mapped_f011_cold",
        ".lisp65_c2_mapped_far_service", ".rodata", ".data", ".bss")}

    predecessor_margin = 0xC000 - int(str(predecessor[".bss"]["VMA_end"]), 16)
    candidate_margin = 0xC000 - int(str(candidate[".bss"]["VMA_end"]), 16)
    text_reserve = (int(str(candidate[".lisp65_c2_mapped_far_facade"]["VMA"]), 16)
                    - int(str(candidate[".text"]["VMA_end"]), 16))
    cold = candidate[".lisp65_c2_mapped_f011_cold"]
    far = candidate[".lisp65_c2_mapped_far_service"]
    require(predecessor[".bss"]["bytes"] == 1584
            and candidate[".bss"]["bytes"] == 1587
            and predecessor_margin == 6 and candidate_margin == 3
            and text_reserve == 32
            and cold["bytes"] == 469
            and cold["VMA_end"] == far["VMA"]
            and int(str(cold["LMA"]), 16) - int(str(cold["VMA"]), 16) == 0x28000,
            "Card-2 final-link geometry drift")

    state = {
        "logical_predecessor_bytes": 2,
        "logical_candidate_bytes": 5,
        "logical_delta_bytes": 3,
        "candidate_cells": ["disk_source_pos", "disk_source_len",
            "disk_source_next_track", "disk_source_next_sector",
            "disk_source_failed"],
        "candidate_locations": {
            name: f"0x{symbol_address(RED_MAP, name):x}" for name in (
                "disk_source_pos", "disk_source_len", "disk_source_next_track",
                "disk_source_next_sector", "disk_source_failed")},
        "allocation_effect": ("the fixed-size zero-page selection moves two new cells "
            "into ZP and displaces existing cells into ordinary BSS; after every swap "
            "the exact linked BSS delta remains +3 bytes"),
    }
    price = json.loads(PRICE.read_text(encoding="utf-8"))
    priced_cold = price["placement"]["mapped_cold"]["bytes"]
    require(priced_cold == 467, "sealed mapped-cold price drift")

    return {
        "format": FORMAT, "recorded_on": "2026-09-03",
        "status": "FROZEN: CARD 2 FINAL LINK STOPPED ON REAL BSS MARGIN WALL",
        "inputs": {"predecessor_map": bind(CARD1_MAP), "red_link_map": bind(RED_MAP),
            "red_LTO_object": bind(LTO), "link_stderr": bind(STDERR),
            "link_stdout": bind(STDOUT), "resolved_profile": bind(PROFILE),
            "source_preflight": bind(PREFLIGHT), "sealed_price": bind(PRICE)},
        "artifact_boundary": {"LTO_object_present": True, "link_map_present": True,
            "final_ELF_present": False, "final_PRG_present": False,
            "pair_disposition": "NO-FINAL-PAIR; LTO/MAP FROZEN AS FIRST-RED EVIDENCE"},
        "two_worlds": {"predecessor": predecessor, "failed_candidate": candidate},
        "walls": {
            "ordinary_text": {"reserve_bytes": text_reserve, "required_bytes": 32,
                "passed": True, "delta_text_bytes": candidate[".text"]["bytes"]
                    - predecessor[".text"]["bytes"]},
            "mapped_F011_owner": {"priced_bytes": priced_cold,
                "linked_map_bytes": cold["bytes"], "price_delta_bytes": 2,
                "ends_exactly_at_far_service": True, "overlap_bytes": 0,
                "shared_MAP_offset": "0x28000"},
            "ordinary_BSS": {"predecessor_bytes": predecessor[".bss"]["bytes"],
                "candidate_bytes": candidate[".bss"]["bytes"], "delta_bytes": 3,
                "predecessor_end": predecessor[".bss"]["VMA_end"],
                "candidate_end": candidate[".bss"]["VMA_end"],
                "predecessor_margin_bytes": predecessor_margin,
                "candidate_margin_bytes": candidate_margin,
                "required_margin_bytes": 5, "deficit_bytes": 2,
                "linker_failures": ["ordinary full-map chain drift",
                    "five-byte validation margin floor violated; it is not capacity"]}},
        "attribution": {"source_reader_state": state,
            "unexplained_BSS_bytes": 0,
            "mapped_owner_difference": ("disk_source_refill_far emitted 114 rather "
                "than the priced 112 bytes; the top-derived placement moved down two "
                "bytes and remains disjoint"),
            "unexplained_mapped_owner_bytes": 0},
        "classification": {"checker_world_defect": False,
            "real_capacity_wall": True, "product_defect_not_exonerated": True,
            "reason": ("the required source-owned continuation state is simultaneously "
                "live and leaves only three protected bytes before 0xc000; the five-byte "
                "validation margin is not capacity")},
        "pricing_gate_finding": {"class": "constrained-live-owner-omitted-from-admission",
            "detail": ("the sealed lane recorded BSS sections but admitted the card from "
                "code-placement groups only; a price must cover every simultaneously live "
                "constrained owner, including NOLOAD/BSS"),
            "mutations_rejected": ["omit-constrained-BSS-owner",
                "treat-five-byte-validation-margin-as-capacity"]},
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "completed_product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0, "DWX_prefilter_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "next": ("reviewer/owner placement or reclaim decision; no retry, resume, "
            "WPLTO or product link is authorized")}


def validate(value: dict[str, Any]) -> None:
    bss = value["walls"]["ordinary_BSS"]
    require(value["format"] == FORMAT
            and value["status"].startswith("FROZEN:")
            and value["artifact_boundary"]["final_ELF_present"] is False
            and value["artifact_boundary"]["final_PRG_present"] is False
            and value["walls"]["ordinary_text"] == {
                "delta_text_bytes": -56, "passed": True,
                "required_bytes": 32, "reserve_bytes": 32}
            and value["walls"]["mapped_F011_owner"]["linked_map_bytes"] == 469
            and value["walls"]["mapped_F011_owner"]["overlap_bytes"] == 0
            and bss["delta_bytes"] == 3 and bss["candidate_margin_bytes"] == 3
            and bss["required_margin_bytes"] == 5 and bss["deficit_bytes"] == 2
            and value["attribution"]["source_reader_state"]["logical_delta_bytes"] == 3
            and value["attribution"]["unexplained_BSS_bytes"] == 0
            and value["classification"]["real_capacity_wall"] is True
            and value["pricing_gate_finding"]["mutations_rejected"] == [
                "omit-constrained-BSS-owner",
                "treat-five-byte-validation-margin-as-capacity"]
            and value["attempt_accounting"] == {"product_cards": 1,
                "WPLTO_runs": 1, "product_link_attempts": 1,
                "completed_product_links": 0, "scope_runs": 0,
                "acceptance_runs": 0, "DWX_prefilter_runs": 0,
                "media_builds": 0, "device_contacts": 0},
            "Card-2 F011 final-link red receipt drift")


def write_report(value: dict[str, Any]) -> None:
    bss = value["walls"]["ordinary_BSS"]
    REPORT.write_text(f"""# Block 2.6 Card 2 — F011 product first final-link red

Status: **FROZEN — REAL CAPACITY WALL; REVIEW DECISION REQUIRED**

The first authorized product invocation reached whole-program LTO and the real
linker, then stopped on both `ordinary full-map chain drift` and the protected
five-byte validation-margin assertion. It produced one LTO object and a link
map, but **no final ELF or PRG**. No retry or read-only resume is possible.

The cold placement itself is structurally sound in the failed-link map. Final
ordinary text shrank by **56 bytes** and retains exactly the required **32-byte
floor**. `.lisp65_c2_mapped_f011_cold` emitted **469 bytes**, two above the
467-byte price; its derived start moved from `$76DF` to `$76DD`, it keeps the
shared `$28000` MAP offset, and it still ends exactly at the Far Service at
`$78B2` with zero overlap.

The hard failure is the simultaneously live ordinary BSS chain. The source
reader now owns five cells (`pos`, `len`, next track, next sector and failure)
where the predecessor owned two. Whole-program ZP selection moves cells between
ZP and BSS, but the exact final balance is **+3 bytes**: BSS grows from
**{bss['predecessor_bytes']:,} bytes** ending at `{bss['predecessor_end']}` to
**{bss['candidate_bytes']:,} bytes** ending at `{bss['candidate_end']}`. The
protected margin before `$C000` therefore falls from
**{bss['predecessor_margin_bytes']} to {bss['candidate_margin_bytes']} bytes**,
two below the required five. There are zero unexplained BSS bytes.

This is a real capacity wall, not a stored-world checker. The pricing lane did
record the new BSS sections, but its admission decision grouped only code
owners. The permanent correction is broader: every product price covers every
simultaneously live constrained owner, including `NOLOAD`/BSS; validation
margins are never spendable capacity.

Accounting is **1/1 WPLTO, 1/1 attempted product link, 0 completed product
links**, zero Scope/Acceptance runs, zero media and zero device contacts. The
next step is a reviewer/owner placement or reclaim decision; no further build
is authorized.
""", encoding="utf-8")


def selftest() -> None:
    value = derive()
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "BSS-owner-omitted": lambda row: row["attribution"].update(
            {"unexplained_BSS_bytes": 3}),
        "margin-treated-as-capacity": lambda row: row["walls"]["ordinary_BSS"].update(
            {"required_margin_bytes": 3, "deficit_bytes": 0}),
        "failed-link-promoted": lambda row: row["artifact_boundary"].update(
            {"final_ELF_present": True}),
        "retry-hidden": lambda row: row["attempt_accounting"].update(
            {"product_link_attempts": 0}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (RedError, KeyError, TypeError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "Card-2 final-link red mutation survived")
    print(f"Block 2.6 Card 2 final-link red: SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"write", "check", "selftest"},
            "usage: block_26_f011_final_link_red.py write|check|selftest")
    if sys.argv[1] == "selftest":
        selftest(); return 0
    value = derive(); validate(value); raw = canonical(value)
    if sys.argv[1] == "write":
        OUT.write_bytes(raw); write_report(value)
    else:
        require(OUT.read_bytes() == raw and REPORT.is_file(),
                "Card-2 final-link red evidence drift")
    print("Block 2.6 Card 2 final-link red: ATTRIBUTED BSS=+3 margin=6->3 deficit=2")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RedError, OSError, json.JSONDecodeError) as error:
        print(f"Block 2.6 Card 2 final-link red: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
