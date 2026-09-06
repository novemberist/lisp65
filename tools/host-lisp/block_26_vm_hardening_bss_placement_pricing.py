#!/usr/bin/env python3
"""Price linker-visible raw owners and a split Card-3 ordinary-BSS layout."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v200_symbol22_first_fault_product_card as RAW  # noqa: E402
import block_26_vm_hardening_product_card as CARD  # noqa: E402
import block_26_vm_hardening_dwx_prefilter as DWX  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
REGISTER = ROOT / "docs/reference/gate-and-tool-register.md"
ELF = CARD.ELF
PRODUCT_RECEIPT = CARD.RECEIPT
RED_RECEIPT = DWX.PREFILTER_RECEIPT
REPORT = ROOT / "docs/planning/2.6-card3-vm-hardening-bss-placement-pricing-report.md"
RECEIPT = ARCH / "block-2.6-card3-vm-hardening-bss-placement-pricing.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORIZATION = "4e9dc729"
PLAN_HEADER = (
    "## Reviewer disposition — card 3 BSS/raw-owner collision; placement round "
    "— 2026-09-04"
)
FORMAT = "lisp65-block-2.6-card3-vm-hardening-bss-placement-pricing-v1"
STATUS = "PASS: LINKER-VISIBLE RAW OWNERS AND SPLIT BSS PRICED"

BSS_START = 0xB9CA
BSS_LIMIT = 0xC000
BSS_FLOOR = 5
METADATA_NAMES = ("symbnd", "symfnptr", "npool", "namelen4")


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


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


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    return {"commit": commit, "path": relative, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode()
    require(raw.count(PLAN_HEADER) == 1, "placement authority section drift")
    section = (PLAN_HEADER + raw.split(PLAN_HEADER, 1)[1]).split(
        "\n## ", 1)[0].rstrip().encode() + b"\n"
    folded = " ".join(section.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("host-only bss placement/reclaim pricing round",
                  "linker-visible reserved owner", "noload section",
                  "bss margin ≥ 5", "no wplto, no link"):
        require(token in folded, f"placement authority token absent: {token}")
    return {"review_authorization": {"commit": AUTHORIZATION,
            "path": relative, "section": PLAN_HEADER, "bytes": len(section),
            "sha256": hashlib.sha256(section).hexdigest()},
        "frozen_product_red": bind(RED_RECEIPT),
        "frozen_product_card": bind(PRODUCT_RECEIPT),
        "gate_register_at_authorization": git_bind(AUTHORIZATION, REGISTER),
        "right": "one host-only BSS placement/reclaim pricing round",
        "budget": {"bounded_codegen_lanes": 0, "product_cards": 0,
            "WPLTO_runs": 0, "product_links": 0, "device_contacts": 0}}


def interval(name: str, start: int, end: int, **extra: Any) -> dict[str, Any]:
    require(start <= end, f"negative interval: {name}")
    return {"owner": name, "start": start, "end_exclusive": end,
            "bytes": end - start, **extra}


def raw_owner_population(truth: ElfTruth) -> list[dict[str, Any]]:
    handoff = truth.section(".lisp65_c2_kernal_handoff")
    facade = truth.section(".lisp65_c2_host_facade")
    refs = RAW.raw_interval_references(ELF, handoff.address + handoff.bytes,
        facade.address, exclude_section="__no_reserved_owner_section__")
    targets = sorted({row["target"] for row in refs})
    terminal_sections = sorted({row["source_section"] for row in refs})
    require(len(refs) == 64 and targets == list(range(0xB582, 0xB592)),
            "terminal-return raw-owner discovery drift")
    input_start = truth.symbol("C2K_INPUT_RING_BASE").value
    input_end = truth.symbol("C2K_INPUT_EVENTS_TAKEN").value + 1
    require((input_start, input_end) == (0xBC90, 0xBD00),
            "input raw-owner derivation drift")
    input_refs = RAW.raw_interval_references(ELF, input_start, input_end,
        exclude_section="__no_reserved_owner_section__")
    input_sections = sorted({row["source_section"] for row in input_refs})
    require(len(input_refs) == 6 and input_sections == [
            ".lisp65_c2_kernal_window.input_capture_helper",
            ".lisp65_c2_kernal_window.input_capture_main",
            ".lisp65_c2_kernal_window.input_consumer"],
            "input raw-owner accessor population drift")
    return [
        interval("terminal-return-guard-raw-owner", targets[0], targets[-1] + 1,
            kind="fixed-raw-NOLOAD-reservation",
            derivation=("non-control raw targets between final handoff end and "
                        "host-facade start"),
            data_references=len(refs), source_sections=terminal_sections,
            emitted_bytes=0),
        interval("input-ring-and-counters-raw-owner", input_start, input_end,
            kind="fixed-raw-NOLOAD-reservation",
            derivation="C2K_INPUT_RING_BASE..C2K_INPUT_EVENTS_TAKEN+1",
            data_references=len(input_refs), source_sections=input_sections,
            emitted_bytes=0),
    ]


def object_row(truth: ElfTruth, name: str) -> dict[str, Any]:
    symbol = truth.symbol(name)
    require(symbol.symbol_type == "Object" and symbol.section == ".bss"
            and symbol.bytes > 0, f"ordinary-BSS object drift: {name}")
    return {"name": name, "start": symbol.value,
        "end_exclusive": symbol.value + symbol.bytes, "bytes": symbol.bytes}


def current_world(truth: ElfTruth, raw_owners: list[dict[str, Any]]) -> dict[str, Any]:
    bss = truth.section(".bss")
    metadata = [object_row(truth, name) for name in METADATA_NAMES]
    input_owner = next(row for row in raw_owners
                       if row["owner"] == "input-ring-and-counters-raw-owner")
    conflicts = []
    for symbol in truth.symbols:
        if symbol.symbol_type != "Object" or symbol.section != ".bss" or not symbol.bytes:
            continue
        lo, hi = symbol.value, symbol.value + symbol.bytes
        if max(lo, input_owner["start"]) < min(hi, input_owner["end_exclusive"]):
            conflicts.append({"name": symbol.name, "start": lo,
                "end_exclusive": hi, "bytes": symbol.bytes,
                "overlap": [max(lo, input_owner["start"]),
                            min(hi, input_owner["end_exclusive"])]})
    # The repl.buf alias is outside the raw window; no duplicate survives here.
    conflicts.sort(key=lambda row: (row["start"], row["name"]))
    require((bss.address, bss.bytes, bss.address + bss.bytes) ==
            (BSS_START, 1074, 0xBDFC), "frozen Card-3 BSS drift")
    require([row["name"] for row in conflicts] == ["namelen4"]
            and conflicts[0]["overlap"] == [0xBC90, 0xBD00],
            "frozen Card-3 raw/BSS red drift")
    require(sum(row["bytes"] for row in metadata) == 566,
            "symbol-metadata owner size drift")
    return {"ordinary_BSS": interval("monolithic-ordinary-BSS", bss.address,
            bss.address + bss.bytes),
        "aggregate_tail_margin_bytes": BSS_LIMIT - (bss.address + bss.bytes),
        "logical_BSS_bytes": bss.bytes,
        "symbol_metadata_members": metadata,
        "symbol_metadata_bytes": sum(row["bytes"] for row in metadata),
        "fixed_raw_conflicts": conflicts,
        "runtime_discriminator": {"six_line_oracle": "7",
            "subsequent_form": "(print 9)",
            "observed": "*** undefined function: print", "gc_runs": 0}}


def proposed_layout(current: dict[str, Any], raw_owners: list[dict[str, Any]],
                    inherited: dict[str, Any]) -> dict[str, Any]:
    input_owner = next(row for row in raw_owners
                       if row["owner"] == "input-ring-and-counters-raw-owner")
    metadata_bytes = current["symbol_metadata_bytes"]
    low_bytes = current["logical_BSS_bytes"] - metadata_bytes
    low_end = BSS_START + low_bytes
    metadata_start = input_owner["end_exclusive"]
    metadata_end = metadata_start + metadata_bytes
    low_slack = input_owner["start"] - low_end
    high_slack = BSS_LIMIT - metadata_end
    require((low_bytes, low_end, low_slack, metadata_bytes, metadata_end,
             high_slack) == (508, 0xBBC6, 202, 566, 0xBF36, 202),
            "recommended split-BSS arithmetic drift")
    components = [
        interval("ordinary-BSS-low", BSS_START, low_end,
            kind="ordinary-BSS-payload", logical_bytes=low_bytes),
        interval("ordinary-BSS-low-reserve", low_end, input_owner["start"],
            kind="largest-contiguous-free-BSS-hole"),
        input_owner,
        interval("symbol-metadata-BSS", metadata_start, metadata_end,
            kind="ordinary-BSS-payload", logical_bytes=metadata_bytes,
            members=list(METADATA_NAMES)),
        interval("ordinary-BSS-high-reserve", metadata_end, BSS_LIMIT,
            kind="largest-contiguous-free-BSS-hole"),
    ]
    for left, right in zip(components, components[1:]):
        require(left["end_exclusive"] == right["start"],
                "recommended BSS layout contains an unnamed gap")
    logical = sum(row.get("logical_bytes", 0) for row in components)
    carved = input_owner["bytes"]
    usable = BSS_LIMIT - BSS_START - carved
    free = usable - logical
    require(logical == 1074 and usable == 1478 and free == 404,
            "recommended BSS capacity accounting drift")
    base_categories = inherited["final_product"]["authority_inventory"]["categories"]
    categories = sorted({*base_categories, "fixed-raw-NOLOAD-reservation"})
    return {"selected": True,
        "form": "linker-visible-raw-reservations-plus-split-symbol-metadata-BSS",
        "selection_reason": ("one structural layout reserves every discovered raw "
            "owner and maximizes the smaller contiguous BSS reserve"),
        "linker_contract": {
            "terminal_owner": ("fixed NOLOAD output at the raw-target interval; "
                "zero emitted bytes"),
            "input_owner": ("fixed NOLOAD output at the equate-derived interval; "
                "zero emitted bytes"),
            "ordinary_low": "generic ordinary BSS below the input owner",
            "symbol_metadata": ("one explicit BSS input class above the input owner; "
                "not a namelen4-only reorder"),
            "zeroing": ("__bss_start/__bss_end or equivalent derived spans initialize "
                "both BSS payloads and name the raw-owner initialization explicitly")},
        "components": components,
        "logical_BSS_bytes": logical,
        "raw_carveout_bytes": carved,
        "allocatable_BSS_bytes": usable,
        "free_BSS_bytes": free,
        "largest_contiguous_BSS_hole_bytes": min(low_slack, high_slack),
        "BSS_floor_bytes": BSS_FLOOR,
        "BSS_margin_bytes": min(low_slack, high_slack),
        "predecessor_card2_BSS_bytes": 1584,
        "logical_BSS_delta_bytes": logical - 1584,
        "false_aggregate_margin_retired_bytes": current["aggregate_tail_margin_bytes"],
        "foreign_BSS_reclaim_bytes": 0,
        "prelink_authority": {
            "population_derivation": ("all non-control fixed raw targets discovered "
                "inside linker arenas plus fixed equate intervals with live readers/writers"),
            "categories_before": base_categories,
            "categories_after": categories,
            "new_category": "fixed-raw-NOLOAD-reservation",
            "required_reservations": [row["owner"] for row in raw_owners],
            "fail_closed_before_WPLTO": True},
        "bounded_owners": {
            "ordinary_text": {**inherited["final_product"]["bounded_owners"][
                "ordinary_text"], "kind": "frozen-r1-final-link-observation"},
            "ordinary_BSS": {"logical_bytes": logical,
                "raw_carveout_bytes": carved, "free_bytes": free,
                "largest_contiguous_hole_bytes": min(low_slack, high_slack),
                "floor_bytes": BSS_FLOOR,
                "margin_bytes": min(low_slack, high_slack)},
            "resident_island": inherited["final_product"]["bounded_owners"][
                "resident_island"],
            "zero_page": inherited["final_product"]["bounded_owners"]["zero_page"],
            "ordinary_NOLOAD": inherited["final_product"]["bounded_owners"]["NOLOAD"],
            "fixed_raw_NOLOAD": {"owners": raw_owners,
                "emitted_bytes": sum(row["emitted_bytes"] for row in raw_owners),
                "all_disjoint": True},
            "all_projected_floors_green": True,
            "final_link_claim": False},
        "fallback_namelen4_only_used": False,
        "remaining_link_debts": ["same-choreography GC-cycle non-increase",
            "fixpoint marking completeness", "product-root-omitted mutation",
            "slot-bound-removed mutation", "rest-transient-bound-removed mutation",
            "pop-fail-stop-and-disk-domain-removed mutation",
            "disk-poke-domain-removed mutation", "final-link owner measurements"]}


def validate(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT and value["status"] == STATUS
            and value["authority"] == authority(), "pricing identity drift")
    current = value["frozen_red_world"]
    raw_owners = value["raw_owner_population"]
    selected = value["recommended_layout"]
    require(len(raw_owners) == 2
            and [row["owner"] for row in raw_owners] == [
                "terminal-return-guard-raw-owner",
                "input-ring-and-counters-raw-owner"]
            and raw_owners[0]["data_references"] == 64
            and (raw_owners[0]["start"], raw_owners[0]["end_exclusive"]) ==
                (0xB582, 0xB592)
            and (raw_owners[1]["start"], raw_owners[1]["end_exclusive"]) ==
                (0xBC90, 0xBD00), "fixed raw-owner population drift")
    require(current["logical_BSS_bytes"] == 1074
            and current["aggregate_tail_margin_bytes"] == 516
            and current["fixed_raw_conflicts"] == [{"name": "namelen4",
                "start": 0xBC1A, "end_exclusive": 0xBD92, "bytes": 376,
                "overlap": [0xBC90, 0xBD00]}]
            and current["runtime_discriminator"]["gc_runs"] == 0,
            "frozen raw-owner red was weakened")
    require(selected["selected"] is True
            and selected["form"] ==
                "linker-visible-raw-reservations-plus-split-symbol-metadata-BSS"
            and selected["logical_BSS_bytes"] == 1074
            and selected["raw_carveout_bytes"] == 112
            and selected["allocatable_BSS_bytes"] == 1478
            and selected["free_BSS_bytes"] == 404
            and selected["largest_contiguous_BSS_hole_bytes"] == 202
            and selected["BSS_margin_bytes"] == 202
            and selected["BSS_floor_bytes"] == 5
            and selected["logical_BSS_delta_bytes"] == -510
            and selected["foreign_BSS_reclaim_bytes"] == 0
            and selected["fallback_namelen4_only_used"] is False,
            "recommended layout arithmetic or choice drift")
    components = selected["components"]
    require([(row["owner"], row["start"], row["end_exclusive"]) for row in components]
            == [("ordinary-BSS-low", 0xB9CA, 0xBBC6),
                ("ordinary-BSS-low-reserve", 0xBBC6, 0xBC90),
                ("input-ring-and-counters-raw-owner", 0xBC90, 0xBD00),
                ("symbol-metadata-BSS", 0xBD00, 0xBF36),
                ("ordinary-BSS-high-reserve", 0xBF36, 0xC000)],
            "recommended layout interval drift")
    owners = selected["bounded_owners"]
    require(owners["ordinary_text"]["margin_bytes"] >= 32
            and owners["ordinary_BSS"]["margin_bytes"] >= 5
            and owners["resident_island"]["margin_bytes"] >= 5
            and owners["zero_page"]["within_bounds"] is True
            and owners["ordinary_NOLOAD"]["margin_bytes"] >= 0
            and owners["fixed_raw_NOLOAD"]["all_disjoint"] is True
            and owners["fixed_raw_NOLOAD"]["emitted_bytes"] == 0
            and owners["all_projected_floors_green"] is True
            and owners["final_link_claim"] is False,
            "bounded-owner projection drift")
    prelink = selected["prelink_authority"]
    require(prelink["new_category"] == "fixed-raw-NOLOAD-reservation"
            and prelink["categories_after"] == sorted({
                *prelink["categories_before"], "fixed-raw-NOLOAD-reservation"})
            and prelink["required_reservations"] == [
                row["owner"] for row in raw_owners]
            and prelink["fail_closed_before_WPLTO"] is True,
            "prelink raw-owner authority drift")
    require(value["mutation_results"] == {
            "drop-input-reservation": {
                "result": "rejected-before-WPLTO",
                "reproduced_overlap": [0xBC90, 0xBD00],
                "conflicting_object": "namelen4"},
            "drop-terminal-reservation": {"result": "rejected-before-WPLTO"},
            "hide-minus-510-logical-delta": {"result": "rejected"},
            "namelen4-only-fallback-selected": {"result": "rejected"}},
            "prelink/reclaim mutation evidence drift")
    require(value["accounting"] == {"bounded_codegen_lanes": 0,
            "product_cards": 0, "WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0, "media_builds": 0,
            "device_contacts": 0}, "pricing round spent forbidden budget")


def report(value: dict[str, Any]) -> str:
    layout = value["recommended_layout"]
    owners = layout["bounded_owners"]
    return f"""# Block 2.6 Card 3 — fixed-raw/BSS placement pricing

Status: **{value['status']}**

## One recommended layout

Make every discovered fixed raw interval a linker-visible, fixed-address
`NOLOAD` owner, then split ordinary BSS around the input owner. The two owners
are the active terminal-return guard at **`$B582..$B591`** (64 non-control raw
references from four emitted overlay wrappers) and the input ring/counters at
**`$BC90..$BCFF`**, derived from `C2K_INPUT_RING_BASE` through
`C2K_INPUT_EVENTS_TAKEN`.

The selected BSS layout is:

| Interval | Owner | Bytes |
|---|---|---:|
| `$B9CA..$BBC5` | ordinary low BSS | 508 |
| `$BBC6..$BC8F` | low contiguous reserve | 202 |
| `$BC90..$BCFF` | input raw `NOLOAD` owner | 112 |
| `$BD00..$BF35` | symbol-metadata BSS (`symbnd`, `symfnptr`, `npool`, `namelen4`) | 566 |
| `$BF36..$BFFF` | high contiguous reserve | 202 |

This is not a `namelen4`-only reorder. The raw window is the structural linker
owner; the four related symbol-metadata cells form one explicit successor BSS
input class above it. The linker contract also names how both BSS payloads are
zeroed, so the split cannot create an initialized/uninitialized-world mismatch.

The arena contains **1,590 bytes**. After carving out the 112-byte raw owner it
has **1,478 allocatable bytes**; 1,074 logical BSS bytes leave **404 bytes** in
two 202-byte holes. The conservative contiguous BSS margin is therefore
**202/5**. The old aggregate 516-byte tail is retired as a capacity claim.
The Card-2-to-Card-3 logical BSS delta remains exactly **−510 bytes**
(1,584 → 1,074); no foreign BSS owner is reclaimed.

## Other constrained owners

The frozen r1 final-link observations remain text
**{owners['ordinary_text']['margin_bytes']}/32**, resident Island
**{owners['resident_island']['margin_bytes']}/5**, ZP within bounds and ordinary
`NOLOAD` **{owners['ordinary_NOLOAD']['margin_bytes']}/0**. The two new raw
reservations emit zero bytes and are disjoint. These are projections over the
frozen red pair, not successor final-link claims; every owner is remeasured by
the replacement link.

The prelink authority gains the derived category
`fixed-raw-NOLOAD-reservation`. Its population comes from non-control raw
targets inside linker arenas plus fixed equate intervals with live accessors.
Dropping the input reservation reproduces the exact `namelen4` overlap
`$BC90..$BCFF` **before WPLTO**; dropping either discovered owner fails closed.

## Boundary

Accounting is **0 bounded-codegen lanes, 0 product cards, 0 WPLTOs, 0 product
links and 0 device contacts**. The replacement link still owes the same-
choreography GC-cycle wall, fixpoint marking completeness, the product-root
mutation and all four VM hardening mutations, plus final measurements of every
constrained owner. A7 remains closed.

Next touchpoint: reviewer/owner decision on one replacement WPLTO and product
link for this single layout.
"""


def build() -> None:
    require(not RECEIPT.exists(), "Card-3 BSS placement price is one-shot")
    artifact_paths = {"ELF": ELF, "PRG": CARD.PRG,
        "LTO": Path(str(CARD.PRG) + ".lto.o"),
        "map": Path(str(CARD.PRG) + ".map")}
    before = {role: bind(path) for role, path in artifact_paths.items()}
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    red = load(RED_RECEIPT)
    require(red["status"] == DWX.RED_STATUS
            and red["runtime_reproduction"]["gc_runs_before"] == 0
            and red["runtime_reproduction"]["gc_runs_after"] == 0,
            "Card-3 product-red authority drift")
    raw_owners = raw_owner_population(truth)
    current = current_world(truth, raw_owners)
    inherited = load(PRODUCT_RECEIPT)
    layout = proposed_layout(current, raw_owners, inherited)
    value = {"format": FORMAT, "recorded_on": "2026-09-04",
        "status": STATUS, "authority": authority(),
        "artifacts_before": before, "raw_owner_population": raw_owners,
        "frozen_red_world": current, "recommended_layout": layout,
        "mutation_results": {
            "drop-input-reservation": {
                "result": "rejected-before-WPLTO",
                "reproduced_overlap": current["fixed_raw_conflicts"][0]["overlap"],
                "conflicting_object": current["fixed_raw_conflicts"][0]["name"]},
            "drop-terminal-reservation": {"result": "rejected-before-WPLTO"},
            "hide-minus-510-logical-delta": {"result": "rejected"},
            "namelen4-only-fallback-selected": {"result": "rejected"}},
        "artifacts_after": {role: bind(path)
            for role, path in artifact_paths.items()},
        "accounting": {"bounded_codegen_lanes": 0, "product_cards": 0,
            "WPLTO_runs": 0, "product_links": 0, "scope_runs": 0,
            "acceptance_runs": 0, "media_builds": 0, "device_contacts": 0},
        "next": "reviewer/owner replacement-WPLTO-and-link decision"}
    require(value["artifacts_before"] == value["artifacts_after"],
            "host-only price changed the frozen product pair")
    validate(value)
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    print("Block 2.6 Card 3 BSS price: PASS layout=split raw=2 "
          "BSS-margin=202/5 WPLTO=0 link=0")


def selftest() -> None:
    value = load(RECEIPT)
    validate(value)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "input-owner-omitted": lambda row: row["raw_owner_population"].pop(),
        "terminal-owner-omitted": lambda row: row["raw_owner_population"].pop(0),
        "raw-category-omitted": lambda row: row["recommended_layout"][
            "prelink_authority"]["categories_after"].remove(
                "fixed-raw-NOLOAD-reservation"),
        "pre-WPLTO-stop-disabled": lambda row: row["recommended_layout"][
            "prelink_authority"].update(fail_closed_before_WPLTO=False),
        "namelen-only-fallback": lambda row: row["recommended_layout"].update(
            fallback_namelen4_only_used=True),
        "logical-delta-hidden": lambda row: row["recommended_layout"].update(
            logical_BSS_delta_bytes=0),
        "BSS-floor-lost": lambda row: row["recommended_layout"][
            "bounded_owners"]["ordinary_BSS"].update(margin_bytes=4),
        "island-floor-lost": lambda row: row["recommended_layout"][
            "bounded_owners"]["resident_island"].update(margin_bytes=4),
        "foreign-reclaim-hidden": lambda row: row["recommended_layout"].update(
            foreign_BSS_reclaim_bytes=1),
        "product-link-hidden": lambda row: row["accounting"].update(
            product_links=1),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except (PricingError, KeyError, TypeError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "Card-3 BSS placement mutation survived")
    print(f"Block 2.6 Card 3 BSS price: SELFTEST PASS mutations={len(rejected)}")


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    require(value["artifacts_before"] == value["artifacts_after"]
            and REPORT.is_file()
            and REPORT.read_text(encoding="utf-8") == report(value),
            "Card-3 BSS placement report/artifact neutrality drift")
    print("Block 2.6 Card 3 BSS price: CHECK PASS raw=2 "
          "logical-delta=-510 BSS-margin=202/5 WPLTO=0 link=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "selftest"))
    action = parser.parse_args().action
    {"build": build, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PricingError, OSError, json.JSONDecodeError,
            subprocess.CalledProcessError) as error:
        print(f"Block 2.6 Card 3 BSS price: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
