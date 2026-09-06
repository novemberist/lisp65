#!/usr/bin/env python3
"""Price Card 6's E000 wall without compiling or linking the product."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
from evidence_era import era_bind  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
PARKED = ROOT / "docs/reference/parked-items-register.md"
RED = ARCH / "block-2.6-card6-small-hardening-product-r1-final-link-red.json"
REACH = ARCH / "c2.3-stack-overlay-ownership-inventory-receipt.json"
TEMP = ARCH / "c2.2-c2-lite-v6-phase11-split-e000-analysis-receipt.json"
BIAS = ARCH / "block-2.6-card2-f011-text-budget-pricing.json"
OLD = ROOT / "build/2.6/card3-vm-hardening-product-r2/wplto"
NEW = ROOT / "build/2.6/card6-small-hardening-product-r1/wplto"
OLD_LTO = OLD / "resident-island-seed.prg.lto.o"
NEW_LTO = NEW / "resident-island-seed.prg.lto.o"
OLD_MAP = OLD / "resident-island-seed.prg.map"
NEW_MAP = NEW / "resident-island-seed.prg.map"
OLD_RUNTIME = OLD / "generated-product-sources/c2_product_runtime.c"
NEW_RUNTIME = NEW / "generated-product-sources/c2_product_runtime.c"
LINKER = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
MEM = ROOT / "src/mem.c"
RUNTIME = ROOT / "src/c2_product_runtime.c"
RECEIPT = ARCH / "block-2.6-card6-small-hardening-e000-pricing.json"
REPORT = ROOT / "docs/planning/2.6-card6-small-hardening-e000-pricing-report.md"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORIZATION = "15704748"
CARD6_SOURCE_COMMIT = "426a1788"
PRICING_EVIDENCE_ERA = "14c956a1bf9926190bafead2d6da7f029e5c8e40"
FORMAT = "lisp65-block-2.6-card6-small-hardening-e000-pricing-v1"
STATUS = "PASS: OMIT A15 STRING-BUILDER LATCH; RECLAIM AND COLD MOVE REJECTED"


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


# The one-shot pricing receipt was sealed with the parked register as it stood
# in this commit.  The register is a living document (every later descope adds
# a row), so its identity is bound in the sealing era, read-only; the A15
# restart-package tokens are still required in the live text (see derive()).
PRICING_SEAL_COMMIT = "14c956a1"


def bind_sealed(path: Path, commit: str) -> dict[str, Any]:
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    return {"path": relative, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_show(commit: str, path: Path) -> str:
    relative = path.relative_to(ROOT).as_posix()
    result = subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE)
    return result.stdout.decode("utf-8")


def authority() -> dict[str, Any]:
    text = git_show(AUTHORIZATION, PLAN)
    marker = "## Reviewer disposition — card 6 E000 wall; pricing round with omission option"
    require(text.count(marker) == 1, "pricing authority section absent")
    section = text.split(marker, 1)[1].split("\n## ", 1)[0]
    words = " ".join(section.split())
    for token in ("Three forms, not two", "omission", "no WPLTO, no link",
                  "Exactly one recommended form"):
        require(token.lower() in words.lower(), f"authority token absent: {token}")
    return {"commit": AUTHORIZATION, "plan": PLAN.relative_to(ROOT).as_posix(),
        "section_sha256": hashlib.sha256(section.encode()).hexdigest(),
        "right": "host-only E000 reclaim/placement/omission pricing; no WPLTO or link"}


def map_rows(path: Path) -> dict[str, dict[str, int]]:
    pattern = re.compile(
        r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+(\.[^ ]+)$")
    result: dict[str, dict[str, int]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line)
        if match is None:
            continue
        vma, lma, size = (int(value, 16) for value in match.groups()[:3])
        result[match.group(4)] = {"vma": vma, "lma": lma, "bytes": size,
            "vma_end": vma + size, "lma_end": lma + size}
    return result


def map_symbol(path: Path, name: str) -> dict[str, int]:
    match = re.search(
        rf"^\s*([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+{re.escape(name)}$",
        path.read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
    require(match is not None, f"map symbol absent: {name}")
    address, size = (int(value, 16) for value in match.groups())
    return {"address": address, "bytes": size, "end": address + size}


def function_span(text: str, start: str, following: str) -> str:
    require(text.count(start) == 1 and text.count(following) == 1,
            f"function span drift: {start}")
    return text.split(start, 1)[1].split(following, 1)[0]


def symbol(elf: ElfTruth, name: str):
    rows = [row for row in elf.symbols if row.name == name]
    require(len(rows) == 1, f"ELF symbol population drift: {name}")
    return rows[0]


def refs(elf: ElfTruth, name: str, target: str) -> list[dict[str, Any]]:
    owner = symbol(elf, name)
    rows = [row for row in elf.relocations
            if row.source_section == owner.section
            and owner.value <= row.offset < owner.value + owner.bytes
            and target in row.target]
    return [{"offset": row.offset, "type": row.relocation_type,
             "target": row.target} for row in rows]


OLD_BSS_PIN = '''ASSERT(SIZEOF(.bss) <= 508,
       "ordinary low BSS escaped the fixed input-owner predecessor")'''
NEW_BSS_FLOOR = '''ASSERT(ADDR(.bss) + SIZEOF(.bss) + 5 <=
           ADDR(.lisp65_c2_input_raw_owner),
       "ordinary low BSS breached the input-owner floor")'''
OLD_DATA_PIN = "SIZEOF(.data) == 22"
NEW_DATA_OWNER = "ADDR(.data) + SIZEOF(.data) <= ADDR(.bss)"


def validate_pin_source(text: str) -> None:
    require(OLD_BSS_PIN not in text and OLD_DATA_PIN not in text,
            "stale exact data/BSS size pin remains")
    require(text.count(NEW_BSS_FLOOR) == 1,
            "derived low-BSS owner/floor guard absent or duplicated")
    require(text.count(NEW_DATA_OWNER + " &&") == 1,
            "derived data-owner containment guard absent or duplicated")
    require(text.count("ADDR(.bss) + SIZEOF(.bss) + 5 <=") == 2,
            "full-map and platform BSS floors must both be derived")
    require("LOADADDR(.data) == ADDR(.data)" in text,
            "data VMA/LMA ownership relation absent")


def pin_mutations(text: str) -> list[str]:
    cases = {
        "restore-exact-BSS-508-pin": text.replace(NEW_BSS_FLOOR, OLD_BSS_PIN, 1),
        "restore-exact-data-22-pin": text.replace(NEW_DATA_OWNER, OLD_DATA_PIN, 1),
        "weaken-low-BSS-floor-to-zero": text.replace(
            "ADDR(.bss) + SIZEOF(.bss) + 5 <=", "ADDR(.bss) + SIZEOF(.bss) <=", 1),
        "permit-data-to-overlap-BSS": text.replace(
            NEW_DATA_OWNER, "ADDR(.data) + SIZEOF(.data) <= ADDR(.bss) + 1", 1),
    }
    rejected = []
    for name, trial in cases.items():
        try:
            validate_pin_source(trial)
        except PricingError:
            rejected.append(name)
    require(rejected == list(cases), "derived-pin mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    red = load(RED)
    reach = load(REACH)["e000_post_boot_reachability"]
    temperature = load(TEMP)["e000_baseline_attribution"][
        "complete_c2_resident_inventory"]
    bias = load(BIAS)["measurement"]
    require(red["real_product_wall"]["minimum_reclaim_or_relocation_bytes"] == 22,
            "frozen E000 red drift")
    require(bias["known_signed_bias_bytes"] == 31,
            "bounded-codegen bias authority drift")
    parked = PARKED.read_text(encoding="utf-8")
    for token in ("A15 string-builder latch (deferred from Block 2.6 Card 6",
                  "essentially free **≥22-byte E000 reclaim**",
                  "legal non-nesting cold/facade placement"):
        require(token in parked, f"A15 parked-register token absent: {token}")

    old_elf = ElfTruth.read(OLD_LTO, llvm_readobj=READOBJ)
    new_elf = ElfTruth.read(NEW_LTO, llvm_readobj=READOBJ)
    old_name = symbol(old_elf, "c2_stream_name_value")
    new_name = symbol(new_elf, "c2_stream_name_value")
    old_putc = symbol(old_elf, "str_putc")
    new_putc = symbol(new_elf, "str_putc")
    old_refs = refs(old_elf, "c2_stream_name_value", "str_building")
    new_refs = refs(new_elf, "c2_stream_name_value", "str_building")
    require((old_name.bytes, new_name.bytes, new_name.bytes - old_name.bytes)
            == (833, 855, 22), "E000 function delta drift")
    require((old_putc.bytes, new_putc.bytes, new_putc.bytes - old_putc.bytes)
            == (319, 370, 51), "ordinary str_putc delta drift")
    require((len(old_refs), len(new_refs)) == (4, 8),
            "inlined str_close relocation witness drift")

    old_generated = OLD_RUNTIME.read_text(encoding="utf-8")
    new_generated = NEW_RUNTIME.read_text(encoding="utf-8")
    start = "C2_KERNAL_RESIDENT uint8_t c2_stream_name_value"
    following = "\nuint8_t c2_stream_pair_value"
    generated_body = function_span(old_generated, start, following)
    require(generated_body == function_span(new_generated, start, following),
            "c2_stream_name_value source body changed between product worlds")
    require(generated_body.count("str_close(string)") == 3,
            "str_close call population drift in E000 owner")

    prior_mem = git_show(CARD6_SOURCE_COMMIT + "^", MEM)
    current_mem = git_show(CARD6_SOURCE_COMMIT, MEM)
    guard = "if (s == NIL || s != str_building) return 0;"
    old_close = "obj str_close(obj s) { str_building = NIL; return s; }"
    new_close = "if (s == str_building) str_building = NIL;"
    require(guard not in prior_mem and old_close in prior_mem
            and guard in current_mem and new_close in current_mem,
            "A15 string-builder-latch source attribution drift")

    old_functions = {row.name for row in old_elf.symbols
        if row.symbol_type == "Function"
        and row.section == ".lisp65_c2_kernal_window.c2_resident"}
    new_functions = {row.name for row in new_elf.symbols
        if row.symbol_type == "Function"
        and row.section == ".lisp65_c2_kernal_window.c2_resident"}
    reachable = {row["name"] for row in reach["functions"]
                 if row["post_boot_reachable"]}
    require(len(old_functions) == len(new_functions) == len(reachable) == 25
            and old_functions == new_functions == reachable,
            "sealed reachability population does not cover live E000 functions")
    temp_row = [row for row in temperature if row["object"] == "c2_stream_name_value"]
    require(len(temp_row) == 1 and temp_row[0]["temperature"] == "cold-decoder-helper",
            "historical temperature classification drift")

    old_map, new_map = map_rows(OLD_MAP), map_rows(NEW_MAP)
    text = new_map[".text"]
    facade = new_map[".lisp65_c2_mapped_far_facade"]
    host_facade = new_map[".lisp65_c2_host_facade"]
    reveal = new_map[".lisp65_c2_kernal_io_reveal"]
    island = new_map[".lisp65_resident_island"]
    require(facade["vma"] - text["vma_end"] == 32,
            "ordinary-text floor drift")
    require(host_facade["bytes"] == 48
            and host_facade["vma_end"] == reveal["vma"],
            "host-facade capacity drift")
    require(0x1f00 - island["vma_end"] == 33,
            "resident-island headroom drift")
    require("#ifdef LISP65_C2_MAP_CPU_TRANSPORT" in RUNTIME.read_text(encoding="utf-8")
            and '__asm__("c2_facade_runtime_overlay_exec")' in
                function_span(RUNTIME.read_text(encoding="utf-8"),
                    "C2_KERNAL_RESIDENT uint8_t c2_stream_shelf_read",
                    "\nC2_KERNAL_RESIDENT uint8_t c2_stream_c2d_read"),
            "MAP edge inside c2_stream_name_value dependency drift")

    linker = LINKER.read_text(encoding="utf-8")
    validate_pin_source(linker)
    rejected_pins = pin_mutations(linker)
    data = new_map[".data"]
    bss = new_map[".bss"]
    raw = new_map[".lisp65_c2_input_raw_owner"]
    require(data["bytes"] == 2 and data["vma_end"] <= bss["vma"]
            and bss["bytes"] == 528 and raw["vma"] - bss["vma_end"] == 182,
            "candidate semantic data/BSS floor facts drift")

    options = {
        "a_reclaim_e000": {
            "required_bytes": 22, "proven_dead_bytes": 0,
            "live_owner_population": 25,
            "result": "REJECTED",
            "reason": ("all 25 emitted E000 functions map exactly to the sealed "
                       "post-boot-reachable population; moving a live owner is form b, "
                       "not free reclaim"),
        },
        "b_relocate_grown_code": {
            "full_owner_bytes": 855,
            "largest_bank2_hole_bytes": 15240,
            "ordinary_text_spendable_bytes": 0,
            "resident_island_headroom_bytes": 33,
            "resident_island_floor_bytes": 5,
            "resident_island_spendable_bytes": 28,
            "host_facade_spendable_bytes": 0,
            "result": "REJECTED",
            "reason": ("the only capacious target is a mapped Bank-2 owner, but the "
                       "function transitively calls c2_stream_shelf_read, whose live "
                       "transport enters c2_facade_runtime_overlay_exec; this is MAP-in-MAP. "
                       "Extracting only the close guard still needs a new facade entry, "
                       "while the 48-byte facade ends at the next owner"),
        },
        "c_omit_low_severity_item": {
            "item": "A15 string-builder latch only",
            "removed_semantics": ("a closed or superseded string handle is no longer "
                                  "rejected before borrowing the active append tail; a "
                                  "stale close may clear the active builder"),
            "retained_card6_items": "A10-A14 plus all non-string-latch A15 hardening",
            "projected_e000_reclaim_bytes": 22,
            "projected_e000_free_bytes": 67,
            "required_e000_floor_bytes": 54,
            "projected_capture_watch_bytes": 57,
            "required_capture_watch_bytes": 57,
            "projected_ordinary_text_reduction_bytes": 51,
            "projected_ordinary_text_floor_bytes": 32,
            "ordinary_text_note": ("the derived mapped facade follows final text, "
                                   "so this is not spendable reserve"),
            "projection_basis": ("final-LTO predecessor/current symbol deltas; the "
                                 "replacement final link must remeasure every number"),
            "result": "RECOMMENDED",
        },
    }
    require([name for name, row in options.items()
             if row["result"] == "RECOMMENDED"] == ["c_omit_low_severity_item"],
            "pricing must select exactly one form")

    return {
        "format": FORMAT, "recorded_on": "2026-09-04", "status": STATUS,
        "authority": authority(),
        "inputs": {"first_red": bind(RED), "reachability": bind(REACH),
            "temperature": bind(TEMP), "codegen_bias": bind(BIAS),
            "parked_register": bind_sealed(PARKED, PRICING_SEAL_COMMIT),
            "predecessor_LTO": bind(OLD_LTO), "candidate_LTO": bind(NEW_LTO),
            "predecessor_map": bind(OLD_MAP), "candidate_map": bind(NEW_MAP),
            "predecessor_generated_runtime": bind(OLD_RUNTIME),
            "candidate_generated_runtime": bind(NEW_RUNTIME),
            "live_mem_source": {
                "path": MEM.relative_to(ROOT).as_posix(),
                "bytes": len(current_mem.encode()),
                "sha256": hashlib.sha256(current_mem.encode()).hexdigest(),
            },
            "live_linker_source": era_bind(PRICING_EVIDENCE_ERA, LINKER)},
        "attribution": {
            "card_item": "A15 string-builder latch",
            "why_E000": ("str_close is inlined into the explicitly C2_KERNAL_RESIDENT "
                         "c2_stream_name_value body at its three close sites"),
            "generated_c2_stream_body_identical": True,
            "c2_stream_name_value_bytes": {"predecessor": old_name.bytes,
                "candidate": new_name.bytes, "delta": 22},
            "str_building_relocations": {"predecessor": old_refs,
                "candidate": new_refs, "counts": [len(old_refs), len(new_refs)]},
            "ordinary_str_putc_bytes": {"predecessor": old_putc.bytes,
                "candidate": new_putc.bytes, "delta": 51},
            "incorrect_first_red_label_corrected": "A11 -> A15",
            "unexplained_bytes": 0,
        },
        "three_form_price": options,
        "pin_conversion": {
            "status": "PASS: EXACT SIZES REPLACED BY OWNER/FLOOR RELATIONS",
            "candidate_facts": {"data_bytes": data["bytes"],
                "data_end": data["vma_end"], "BSS_start": bss["vma"],
                "BSS_bytes": bss["bytes"], "BSS_end": bss["vma_end"],
                "raw_owner_start": raw["vma"],
                "BSS_to_raw_owner_margin_bytes": raw["vma"] - bss["vma_end"],
                "required_margin_bytes": 5},
            "mutations_rejected": rejected_pins,
        },
        "decision": {"selected_form": "omit-A15-string-builder-latch",
            "replacement_product_card_open": False,
            "reason": ("the only zero-placement-cost form restores the full 22-byte "
                       "capture watch; no dead E000 bytes or legal cold owner exists")},
        "registered_followup": {
            "item": "A15 string-builder latch",
            "restart_condition": ("an essentially free >=22-byte E000 reclaim or a "
                                  "legal non-nesting cold/facade placement"),
        },
        "owed_on_replacement_link": [
            "manifest-pinned toolchain identity and cards-1-to-3 attribution statement",
            "nine-user DMA descriptor/trigger byte equivalence and memory-clobber mutation",
            "all constrained owners against their final-link floors",
            "full predecessor attribution with zero unexplained members",
            "packed DWX prefilter including boot cycles and print-9 witness",
            "Scope and Acceptance",
        ],
        "accounting": {"pricing_WPLTO_runs": 0, "pricing_product_links": 0,
            "bounded_codegen_lanes": 0, "device_contacts": 0,
            "prior_card6_WPLTO_runs": 1, "prior_card6_link_attempts": 1},
        "claim_limit": ("The omission is selected from existing final-LTO and map "
                        "evidence. Capacity projections are not final-link claims; no "
                        "replacement WPLTO or product link is authorized by this receipt."),
    }


def report(value: dict[str, Any]) -> str:
    a = value["three_form_price"]["a_reclaim_e000"]
    b = value["three_form_price"]["b_relocate_grown_code"]
    c = value["three_form_price"]["c_omit_low_severity_item"]
    pins = value["pin_conversion"]["candidate_facts"]
    return f"""# Block 2.6 Card 6 — E000 pricing round

Status: **{value['status']}**

This round performed **0 WPLTOs, 0 product links and 0 device contacts**.
It selects one form for a later replacement-link decision; it does not open or
execute that link.

## Exact attribution

The 22 bytes belong to **A15's string-builder latch**, not A11. A15 changed
`str_putc` to reject a closed/superseded handle and made `str_close` clear the
latch only for the active builder. The generated C body of
`c2_stream_name_value` is byte-for-byte source-identical in the predecessor
and candidate worlds, but it contains three `str_close` sites. Whole-program
LTO inlines the changed close body into that explicitly `C2_KERNAL_RESIDENT`
function. Its `str_building` relocations double **4 → 8** and the function grows
**833 → 855 bytes**, exactly +22. The non-E000 `str_putc` body independently
grows **319 → 370 bytes**. There are zero unattributed E000 bytes. The frozen
first-red receipt's earlier A11 family label is corrected to A15.

## Three priced forms

| form | price/result |
|---|---|
| Reclaim in E000 | **Rejected.** {a['proven_dead_bytes']} dead bytes are proved among {a['live_owner_population']} emitted functions; all map onto the sealed post-boot-reachable population. Moving a live owner is relocation, not free reclaim. |
| Move grown code cold | **Rejected.** The full owner is {b['full_owner_bytes']} bytes. Bank 2 has {b['largest_bank2_hole_bytes']:,} bytes, but the body reaches `c2_stream_shelf_read` and therefore the MAP transport: mapped placement would be MAP-in-MAP. Ordinary text has {b['ordinary_text_spendable_bytes']} spendable bytes, the Island only {b['resident_island_spendable_bytes']}, and the {b['host_facade_spendable_bytes']}-byte facade gap cannot carry even a new entry. |
| Omit the A15 string latch | **Recommended.** Existing final-LTO deltas project exactly {c['projected_e000_reclaim_bytes']} reclaimed E000 bytes: free space {c['projected_e000_free_bytes']}, floor {c['required_e000_floor_bytes']}, and capture watch {c['projected_capture_watch_bytes']}/{c['required_capture_watch_bytes']}. It also removes {c['projected_ordinary_text_reduction_bytes']} text bytes, but the derived mapped facade follows final text, so the {c['projected_ordinary_text_floor_bytes']}-byte floor remains a floor rather than becoming spendable reserve. A10–A14 and all other A15 hardening stay. |

The omitted low-severity behavior is named rather than hidden: a closed or
superseded string handle is no longer rejected before it can borrow the active
append tail, and a stale close may clear the active builder. It is registered
for return only after an essentially free 22-byte E000 reclaim or a legal
non-nesting cold/facade placement.

## Pin conversion

The exact `SIZEOF(.data) == 22` and `SIZEOF(.bss) <= 508` checks are gone.
Admission is now derived from data containment and the named BSS-to-raw-owner
floor. In the stopped candidate map `.data` is {pins['data_bytes']} bytes,
`.bss` is {pins['BSS_bytes']} bytes, and BSS ends {pins['BSS_to_raw_owner_margin_bytes']}
bytes before the raw-input owner against the five-byte floor. Four sharp
mutations restore either exact pin, weaken the floor or permit overlap; all
fall.

The next touchpoint is the replacement-WPLTO/link decision on the omission
form. That link still owes the nine-user DMA emitted-byte/clobber proof,
toolchain statement, all floors, full attribution, Scope/Acceptance, packed
DWX rows and boot-cycle comparison. None is claimed here.
"""


def validate(value: dict[str, Any]) -> None:
    require(value == derive() and value["status"] == STATUS,
            "E000 pricing receipt drift")
    selected = [name for name, row in value["three_form_price"].items()
                if row["result"] == "RECOMMENDED"]
    require(selected == ["c_omit_low_severity_item"]
            and value["attribution"]["unexplained_bytes"] == 0
            and value["pin_conversion"]["candidate_facts"][
                "BSS_to_raw_owner_margin_bytes"] == 182
            and value["accounting"]["pricing_WPLTO_runs"] == 0
            and value["accounting"]["pricing_product_links"] == 0,
            "E000 price decision invariant drift")


def write() -> None:
    require(not RECEIPT.exists() and not REPORT.exists(), "pricing result is one-shot")
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    validate(value)
    print("Block 2.6 Card 6: E000 PRICE PASS selected=omit-A15-latch WPLTO=0 links=0")


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    require(REPORT.is_file() and REPORT.read_text(encoding="utf-8") == report(value),
            "E000 pricing report drift")
    print("Block 2.6 Card 6: E000 PRICE CHECK selected=omit-A15-latch")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "misattribute-A15-to-A11": lambda row: row["attribution"].update(
            {"card_item": "A11"}),
        "invent-dead-reclaim": lambda row: row["three_form_price"][
            "a_reclaim_e000"].update({"proven_dead_bytes": 22}),
        "ignore-MAP-nesting": lambda row: row["three_form_price"][
            "b_relocate_grown_code"].update({"result": "RECOMMENDED"}),
        "underrestore-capture-watch": lambda row: row["three_form_price"][
            "c_omit_low_severity_item"].update({"projected_capture_watch_bytes": 56}),
        "weaken-BSS-floor": lambda row: row["pin_conversion"][
            "candidate_facts"].update({"required_margin_bytes": 0}),
        "hide-product-build": lambda row: row["accounting"].update(
            {"pricing_WPLTO_runs": 1}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except (PricingError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "E000 pricing mutation survived")
    print(f"Block 2.6 Card 6: E000 PRICE SELFTEST mutations={len(rejected) + 4}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    {"write": write, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PricingError, OSError, UnicodeError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"Block 2.6 Card 6 E000 pricing: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
