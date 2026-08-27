#!/usr/bin/env python3
"""Prove whether the reviewed r9 VMA/LMA pair has an encodable MAP tuple."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v17_ide_idle_blink_product_card as CARD  # noqa: E402
import c2_v17_ide_idle_blink_product_card_r9 as R9  # noqa: E402
import c2_v160_r1_graph_conversions as GRAPH  # noqa: E402
import c2_v20_map_tuple_fix as MAP  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
REPORT = ROOT / "docs/planning/v1.7.0-block3-r10-map-geometry-preflight-red.md"
RECEIPT = ARCH / "c2.3-v1.7-block3-r10-map-geometry-preflight-red.json"
SOURCE = ROOT / "src/optional/c2_mapped_far_service_liveness_v4.s"
CONTRACT = ROOT / "config/c2-mapped-far-map-contract-v2.json"
PROFILE = R9.PROFILE
AUTHORIZATION = "46a02bc5"
FORMAT = "lisp65-c2-v17-block3-r10-map-geometry-preflight-v1"
STATUS = "PREFLIGHT RED: R9 UPPER ANCHOR IS NOT MAP-ENCODABLE"


class PreflightError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PreflightError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    value = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode().lower()
    for token in ("block 3 r10 map-geometry repair authority",
                  "loadaddr(.lisp65_c2_mapped_far_service)",
                  "preflight first proves", "one new wplto",
                  "representability or attribution failure"):
        require(token in raw, f"r10 authority absent: {token}")
    return value


def pair() -> dict[str, Any]:
    return {"ELF": bind(R9.ELF), "PRG": bind(R9.PRG)}


def emitted_tuple(truth: ElfTruth) -> dict[str, int]:
    enter = truth.symbol("c2_mapped_far_enter")
    section = truth.section(enter.section)
    raw = truth.section_bytes(enter.section)[
        enter.value - section.address:enter.value - section.address + enter.bytes]
    operation = GRAPH._interpret_trampoline(raw)["map_operations"][0]
    require(operation == {"A": 0x40, "X": 0x82, "Y": 0, "Z": 0x80},
            "r9 emitted MAP tuple drift")
    return {name: operation[name] for name in "AXYZ"}


def encode(offset: int, mask: int = 0x8) -> dict[str, int] | None:
    if offset < 0 or offset > 0xFFF00 or offset & 0xFF:
        return None
    return {"A": (offset >> 8) & 0xFF,
            "X": ((mask & 0xF) << 4) | ((offset >> 16) & 0xF),
            "Y": 0, "Z": 0x80}


def relation(vma: int, lma: int, tuple_value: dict[str, int]) -> bool:
    decoded = MAP.decode_low(tuple_value["A"], tuple_value["X"])
    return (decoded["mapped_low_half_blocks"] == [3]
            and MAP.map_low(vma, decoded) == lma)


def mutation_proof(vma: int, lower_lma: int) -> dict[str, str]:
    derived = encode(lower_lma - vma)
    require(derived is not None and relation(vma, lower_lma, derived),
            "representable control geometry did not validate")
    moved_lma = lower_lma + 0x100
    manipulated = {**derived, "A": (derived["A"] + 1) & 0xFF}
    require(not relation(vma, moved_lma, derived),
            "LMA move without tuple follow survived")
    require(not relation(vma, lower_lma, manipulated),
            "tuple mutation without LMA reason survived")
    require(encode(lower_lma + 0x3A - vma) is None,
            "non-page-congruent LOADADDR unexpectedly encoded")
    return {
        "move-LMA-without-tuple-follow": "rejected",
        "mutate-tuple-without-LMA-reason": "rejected",
        "non-page-congruent-LOADADDR": "rejected",
    }


def derive() -> dict[str, Any]:
    before = pair()
    truth = ElfTruth.read(R9.ELF, llvm_readobj=CARD.BASE.READOBJ,
                          include_section_data=True)
    far = truth.section(".lisp65_c2_mapped_far_service")
    cold = truth.section(".lisp65_c2_mapped_product_cold")
    lma = truth.symbol("__lisp65_c2_mapped_far_service_load_start").value
    load_end = truth.symbol("__lisp65_c2_mapped_far_service_load_end").value
    cold_lma = truth.symbol("__lisp65_c2_mapped_product_cold_load_start").value
    cold_load_end = truth.symbol(
        "__lisp65_c2_mapped_product_cold_load_end").value
    required = lma - far.address
    current = emitted_tuple(truth)
    current_decoded = MAP.decode_low(current["A"], current["X"])
    exact = [
        {"A": a, "X": 0x80 | high}
        for high in range(16) for a in range(256)
        if ((high << 16) | (a << 8)) == required
    ]
    lower_offset = required & ~0xFF
    upper_offset = lower_offset + 0x100
    lower_lma = far.address + lower_offset
    upper_lma = far.address + upper_offset

    source = SOURCE.read_text(encoding="utf-8")
    match = re.search(
        r"c2_mapped_far_enter:.*?lda\s+#(0x[0-9a-f]+).*?"
        r"ldx\s+#(0x[0-9a-f]+).*?ldy\s+#(0x[0-9a-f]+).*?"
        r"ldz\s+#(0x[0-9a-f]+).*?\n\s*map\s*\n\s*eom",
        source, re.IGNORECASE | re.DOTALL)
    require(match is not None and tuple(int(x, 16) for x in match.groups())
            == (0x40, 0x82, 0, 0x80), "literal tuple source drift")
    profile = PROFILE.read_text(encoding="utf-8")
    source_binding = bind(SOURCE)
    require(("input_sha256=" + source_binding["path"] + ":"
             + source_binding["sha256"]) in profile,
            "r9 compiler profile did not consume the literal owner")
    contract = load(CONTRACT)
    require(contract["format"] == "lisp65-c2-mapped-far-map-contract-v2"
            and contract["tuple"]["maplo_a"] == "0x40"
            and contract["tuple"]["maplo_x"] == "0x82"
            and contract["map_semantics"]["intended_offset"] == "0x24000",
            "historical MAP contract drift")

    require((far.address, far.bytes, lma, load_end,
             cold.address, cold.bytes, cold_lma, cold_load_end)
            == (0x78B2, 1488, 0x2F8EC, 0x2FEBC,
                0x7E8D, 324, 0x2FEBC, 0x30000),
            "r9 linked geometry drift")
    require(required == 0x2803A and required & 0xFF == 0x3A
            and (far.address & 0xFF) == 0xB2 and (lma & 0xFF) == 0xEC
            and encode(required) is None and exact == [],
            "r9 representability attribution drift")
    require(MAP.map_low(far.address, current_decoded) == 0x2B8B2,
            "historical tuple projection drift")
    lower = encode(lower_offset); upper = encode(upper_offset)
    require(lower is not None and upper is not None,
            "nearest representable tuple derivation drift")
    mutations = mutation_proof(far.address, lower_lma)
    bank_start, bank_end, static_end = 0x20000, 0x30000, 0x2CC06
    highest_cpu_end = max(far.address + far.bytes,
                          cold.address + cold.bytes)
    common_offset = (bank_end - highest_cpu_end) & ~0xFF
    derived_far_lma = far.address + common_offset
    derived_far_end = derived_far_lma + far.bytes
    derived_cold_lma = cold.address + common_offset
    derived_cold_end = derived_cold_lma + cold.bytes
    common_tuple = encode(common_offset)
    require(common_offset == 0x28000 and common_tuple == lower
            and (derived_far_lma, derived_far_end,
                 derived_cold_lma, derived_cold_end)
            == (0x2F8B2, 0x2FE82, 0x2FE8D, 0x2FFD1)
            and static_end < derived_far_lma < derived_far_end
            < derived_cold_lma < derived_cold_end < bank_end,
            "maximal common-offset placement price drift")
    free_intervals = [
        {"start": static_end, "end_exclusive": derived_far_lma,
         "bytes": derived_far_lma - static_end},
        {"start": derived_far_end, "end_exclusive": derived_cold_lma,
         "bytes": derived_cold_lma - derived_far_end},
        {"start": derived_cold_end, "end_exclusive": bank_end,
         "bytes": bank_end - derived_cold_end},
    ]
    require([row["bytes"] for row in free_intervals] == [11436, 11, 47]
            and sum(row["bytes"] for row in free_intervals) == 11494,
            "MAP-encodable placement capacity arithmetic drift")
    after = pair()
    require(before == after, "read-only preflight changed frozen r9 pair")

    return {
        "format": FORMAT, "recorded_on": "2026-08-26", "status": STATUS,
        "authority": authority(), "frozen_r9_pair_before": before,
        "frozen_r9_pair_after": after,
        "historical_tuple_authority": {
            "active_literal_owner": source_binding,
            "compiler_profile": bind(PROFILE),
            "contract": bind(CONTRACT),
            "contract_tuple": contract["tuple"],
            "mechanism": ("the active assembly owner consumes the v2 contract's "
                          "fixed $24000-era A/X tuple as source literals; it has "
                          "no data path from final-link LOADADDR symbols"),
        },
        "linker_authority": {
            "section": far.name, "VMA": far.address, "LMA": lma,
            "bytes": far.bytes, "load_end_exclusive": load_end,
            "next_owner": {"section": cold.name, "VMA": cold.address,
                           "LMA": cold_lma, "bytes": cold.bytes,
                           "load_end_exclusive": cold_load_end},
            "source_symbols": [
                "__lisp65_c2_mapped_far_service_load_start",
                "__lisp65_c2_mapped_far_service_load_end"],
        },
        "hardware_encoding": {
            "rule": "offset20=(X[3:0]<<16)|(A<<8); low block mask=X[7:4]",
            "granularity_bytes": 256,
            "preserves_CPU_address_low_byte": True,
            "primary_semantics": MAP.primary_semantics(),
        },
        "representability": {
            "required_offset": required,
            "required_offset_hex": f"0x{required:05X}",
            "offset_residue": required & 0xFF,
            "VMA_low_byte": far.address & 0xFF,
            "LMA_low_byte": lma & 0xFF,
            "exact_tuple_count": len(exact), "exact_tuples": exact,
            "current_tuple": current, "current_decode": current_decoded,
            "current_tuple_maps_section_start_to": MAP.map_low(
                far.address, current_decoded),
            "nearest_lower": {"LMA": lower_lma,
                              "distance_from_r9_LMA": lower_lma - lma,
                              "tuple": lower},
            "nearest_upper": {"LMA": upper_lma,
                              "distance_from_r9_LMA": upper_lma - lma,
                              "tuple": upper},
        },
        "priced_MAP_encodable_successor": {
            "status": "PRICED-NOT-AUTHORIZED",
            "policy": ("maximal shared page-aligned offset below Bank-2 end, "
                       "derived from tenant VMAs/extents"),
            "bank": {"start": bank_start, "end_exclusive": bank_end},
            "static_plane_end_exclusive": static_end,
            "shared_offset": common_offset, "tuple": common_tuple,
            "tenants": [
                {"section": far.name, "VMA": far.address,
                 "LMA": derived_far_lma, "bytes": far.bytes,
                 "end_exclusive": derived_far_end},
                {"section": cold.name, "VMA": cold.address,
                 "LMA": derived_cold_lma, "bytes": cold.bytes,
                 "end_exclusive": derived_cold_end},
            ],
            "free_intervals": free_intervals,
            "aggregate_free_bytes": sum(row["bytes"] for row in free_intervals),
            "largest_contiguous_hole_bytes": max(
                row["bytes"] for row in free_intervals),
            "higher_page_offset_rejected": {
                "offset": common_offset + 0x100,
                "bytes_past_bank_end": (highest_cpu_end + common_offset
                                        + 0x100 - bank_end)},
            "difference_from_r9": {
                "far_service_LMA_delta": derived_far_lma - lma,
                "product_cold_LMA_delta": derived_cold_lma - cold_lma,
                "far_to_cold_gap_bytes": derived_cold_lma - derived_far_end,
                "bank_end_reserve_bytes": bank_end - derived_cold_end,
            },
        },
        "tuple_LOADADDR_gate_prototype": {
            "claim": "emitted MAP tuple maps section VMA exactly to LOADADDR",
            "mutations": mutations,
            "r9_result": "rejected-before-WPLTO",
            "permanent_installation": "waits for an authorized encodable candidate",
        },
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
                               "scope_runs": 0, "qualification_runs": 0,
                               "media_builds": 0, "device_contacts": 0},
        "disposition": {
            "r10_link_authority_consumed": False,
            "r9_pair": "FROZEN-UNQUALIFIED-PRODUCT-EVIDENCE",
            "next": ("review may authorize the priced maximal shared-offset "
                     "placement or choose a VMA/payload-layout change; a "
                     "tuple-only r10 cannot exist"),
        },
    }


def render(value: dict[str, Any]) -> str:
    relation_value = value["representability"]
    lower = relation_value["nearest_lower"]
    upper = relation_value["nearest_upper"]
    priced = value["priced_MAP_encodable_successor"]
    tenants = priced["tenants"]
    return f"""# Block 3 r10 MAP-Geometry Preflight Red

Status: **{value['status']}**

The old authority is now exact.  The active compiler profile consumes
`src/optional/c2_mapped_far_service_liveness_v4.s`; its
`c2_mapped_far_enter` body embeds `A=$40/X=$82` directly.  Those literals are
the inherited implementation of `config/c2-mapped-far-map-contract-v2.json`,
whose fixed intended offset is `$24000`.  Neither source has a data path from
the linker's final `LOADADDR` symbols.

The reviewed r9 geometry cannot be repaired by deriving a different tuple.
Far Service VMA `$78B2` and LMA `$02F8EC` require offset
`{relation_value['required_offset_hex']}`.  The hardware encoding is
`offset20=(X[3:0]<<16)|(A<<8)`, so every representable offset is a multiple of
`$100`; it also necessarily preserves an address's low byte.  Here VMA low is
`$B2`, LMA low is `$EC`, and the required residue is `$3A`.  Exhaustive
enumeration of all 4,096 A/X offset encodings yields **zero** exact tuples.

The page-aligned form has one clear price.  Both MAP tenants must share the
same offset, so the maximal bank-end-near offset that fits their final VMA
extents is `$28000` (`A=$80/X=$82`).  It places Far Service at
`${tenants[0]['LMA']:06X}..${tenants[0]['end_exclusive']:06X}`, preserves the
11-byte VMA gap, places Product-Cold at
`${tenants[1]['LMA']:06X}..${tenants[1]['end_exclusive']:06X}`, and leaves 47
bytes at Bank-2 end.  The largest contiguous hole remains
{priced['largest_contiguous_hole_bytes']:,} bytes (aggregate free space remains
{priced['aggregate_free_bytes']:,}).  The next higher page offset overruns the
bank by {priced['higher_page_offset_rejected']['bytes_past_bank_end']} bytes.
This derived placement moves Far Service by -58 and Product-Cold by -47 bytes
relative to r9.  It is priced but not authorized: r9 required adjacency and an
exact Product-Cold top anchor, whereas executable MAP geometry requires the
VMA-congruent 11/47-byte gaps.

The relation-gate prototype already rejects all three relevant
mutations: LMA moved without tuple follow, tuple manipulated without an LMA
reason, and a non-page-congruent LOADADDR.  It therefore stops this world
before the one authorized WPLTO/link rather than weakening `Tuple = LOADADDR`.

Accounting is zero WPLTOs, zero links, zero qualification runs, zero media and
zero device contacts.  The frozen r9 pair is SHA-identical before and after.
The r10 link authority remains unconsumed.  Review may authorize the priced
maximal-common-offset placement (or choose a separately priced VMA/payload
layout change) before r10 can exist.
"""


def record() -> None:
    require(not RECEIPT.exists() and not REPORT.exists(),
            "r10 representability preflight is one-shot")
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(render(value), encoding="utf-8")
    print("v1.7 Block3 r10: PREFLIGHT RED offset=0x2803A residue=0x3A "
          "WPLTO=0 link=0")


def check() -> None:
    value = load(RECEIPT)
    require(value == derive() and REPORT.read_text(encoding="utf-8")
            == render(value), "r10 MAP-geometry preflight evidence drift")
    print("v1.7 Block3 r10: PREFLIGHT RED CHECK PASS exact-tuples=0")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("record", "check"))
    args = parser.parse_args()
    {"record": record, "check": check}[args.command]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
