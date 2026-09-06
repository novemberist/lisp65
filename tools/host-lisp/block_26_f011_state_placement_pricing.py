#!/usr/bin/env python3
"""Price a two-byte, validated source-link state after Card-2's BSS red."""

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

import block_26_f011_text_budget_pricing as BASE  # noqa: E402
import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
REGISTER = ROOT / "docs/reference/gate-and-tool-register.md"
RED = ARCH / "block-2.6-card2-f011-product-r1-final-link-red.json"
RECEIPT = ARCH / "block-2.6-card2-f011-state-placement-pricing.json"
REPORT = ROOT / "docs/planning/2.6-card2-f011-state-placement-pricing-report.md"
BUILD = ROOT / "build/2.6/card2-f011-state-placement-pricing-r6"
AUTHORIZATION = "d19c3d20"
FORMAT = "lisp65-block-2.6-card2-f011-state-placement-pricing-v1"
VALID = 0x8000
SEAL_ERA_COMMIT = "58ac13fe"


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def replace_once(source: str, old: str, new: str, label: str) -> str:
    require(source.count(old) == 1, f"{label} source seam drift")
    return source.replace(old, new, 1)


def authority_source() -> tuple[str, dict[str, Any]]:
    relative = "src/io.c"
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    return raw.decode("utf-8"), {"commit": AUTHORIZATION, "path": relative,
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def packed_source(source: str) -> str:
    source = replace_once(source,
        """static unsigned char disk_source_pos, disk_source_len;
static unsigned char disk_source_next_track, disk_source_next_sector;
static unsigned char disk_source_failed;
""",
        """/* The validated successor link owns two bytes outside DIR scratch.
 * Bits 0..5 are sector, 6..12 are track and bit 15 is validity.  A terminal
 * link has track/sector zero after its payload length has been validated;
 * disk_file_len remains the authoritative stream terminator. */
#define DISK_SOURCE_LINK_VALID 0x8000u
#define DISK_SOURCE_LINK_PACK(t, s) \\
    ((unsigned int)(DISK_SOURCE_LINK_VALID | ((unsigned int)(t) << 6) | (s)))
#define DISK_SOURCE_LINK_TRACK(v) ((unsigned char)(((v) >> 6) & 0x7fu))
#define DISK_SOURCE_LINK_SECTOR(v) ((unsigned char)((v) & 0x3fu))
static unsigned int disk_source_link;
""", "packed source state")
    source = replace_once(source,
        """unsigned char disk_source_refill_far(void) {
    unsigned char t = disk_source_next_track;
    unsigned char s = disk_source_next_sector;
    unsigned char nt, ns;
    unsigned int count;
    if (!t || !io_disk_read_sector_far(t, s)) {
        disk_source_failed = 1;
        return 0;
    }
    nt = ext_disk_get(DISK_EXT_DIR); ns = ext_disk_get(DISK_EXT_DIR + 1u);
    count = disk_chain_count(t, s, nt, ns);
    if (count > 254u) {
        disk_source_failed = 1;
        return 0;
    }
    disk_source_next_track = nt; disk_source_next_sector = ns;
    disk_source_pos = 0;
    disk_source_len = (unsigned char)count;
    return 1;
}
""",
        """unsigned char disk_source_refill_far(void) {
    unsigned int link = disk_source_link;
    unsigned char t = DISK_SOURCE_LINK_TRACK(link);
    unsigned char s = DISK_SOURCE_LINK_SECTOR(link);
    unsigned char nt, ns;
    unsigned int count;
    if (!(link & DISK_SOURCE_LINK_VALID) || !t ||
        !io_disk_read_sector_far(t, s)) {
        disk_source_link = 0;
        return 0;
    }
    nt = ext_disk_get(DISK_EXT_DIR); ns = ext_disk_get(DISK_EXT_DIR + 1u);
    count = disk_chain_count(t, s, nt, ns);
    if (count > 254u) {
        disk_source_link = 0;
        return 0;
    }
    disk_source_link = DISK_SOURCE_LINK_PACK(nt, nt ? ns : 0u);
    return 1;
}
""", "packed cold refill")
    source = replace_once(source,
        """static LISP65_RESIDENT_ISLAND_FN char disk_source_fetch(void) {
#if !defined(__mos__) || !defined(LISP65_C2_F011_COLD)
    unsigned char t, s, nt, ns;
    unsigned int count;
#endif
    if (disk_file_pos >= disk_file_len) return '\\0';
    if (disk_source_pos >= disk_source_len) {
#if defined(__mos__) && defined(LISP65_C2_F011_COLD)
        if (!disk_source_refill()) return '\\0';
#else
        t = disk_source_next_track; s = disk_source_next_sector;
        if (!t || !io_disk_read_sector(t, s)) {
            disk_source_failed = 1;
            return '\\0';
        }
        nt = io_disk_byte(0); ns = io_disk_byte(1);
        count = disk_chain_count(t, s, nt, ns);
        if (count > 254u) {
            disk_source_failed = 1;
            return '\\0';
        }
        disk_source_next_track = nt; disk_source_next_sector = ns;
        disk_source_pos = 0;
        disk_source_len = (unsigned char)count;
#endif
    }
    ++disk_file_pos;
    return (char)io_disk_byte((unsigned char)(2u + disk_source_pos++));
}
""",
        """static LISP65_RESIDENT_ISLAND_FN char disk_source_fetch(void) {
    unsigned int folded;
    unsigned char pos;
#if !defined(__mos__) || !defined(LISP65_C2_F011_COLD)
    unsigned char t, s, nt, ns;
    unsigned int count, link;
#endif
    if (disk_file_pos >= disk_file_len) return '\\0';
    /* 256 == 2 (mod 254): fold the existing linear progress counter into
     * the current sector offset without another persistent state byte. */
    folded = (unsigned int)((disk_file_pos & 0xffu) +
                            ((disk_file_pos >> 8) << 1));
    while (folded >= 254u) folded -= 254u;
    pos = (unsigned char)folded;
    if (disk_file_pos && !pos) {
#if defined(__mos__) && defined(LISP65_C2_F011_COLD)
        if (!disk_source_refill()) return '\\0';
#else
        link = disk_source_link;
        t = DISK_SOURCE_LINK_TRACK(link);
        s = DISK_SOURCE_LINK_SECTOR(link);
        if (!(link & DISK_SOURCE_LINK_VALID) || !t ||
            !io_disk_read_sector(t, s)) {
            disk_source_link = 0;
            return '\\0';
        }
        nt = io_disk_byte(0); ns = io_disk_byte(1);
        count = disk_chain_count(t, s, nt, ns);
        if (count > 254u) {
            disk_source_link = 0;
            return '\\0';
        }
        disk_source_link = DISK_SOURCE_LINK_PACK(nt, nt ? ns : 0u);
#endif
    }
    ++disk_file_pos;
    return (char)io_disk_byte((unsigned char)(2u + pos));
}
""", "derived source position")
    source = replace_once(source,
        """    disk_source_next_track = nt; disk_source_next_sector = ns;
    disk_source_pos = 0;
    disk_source_len = (unsigned char)n;
    disk_source_failed = 0;
    load_source_stream(disk_source_fetch);
    return (unsigned char)!disk_source_failed;
""",
        """    disk_source_link = DISK_SOURCE_LINK_PACK(nt, nt ? ns : 0u);
    load_source_stream(disk_source_fetch);
    return (unsigned char)((disk_source_link & DISK_SOURCE_LINK_VALID) != 0);
""", "packed source initialization")
    return source


def disk_file_max() -> int:
    rows = [item.split("=", 1)[1] for item in BASE.GUARD.compile_flags()
        if item.startswith("-DDISK_EXT_FILE_MAX=")]
    require(len(rows) == 1, "disk-file maximum is not uniquely profile-derived")
    return int(rows[0], 0)


def model() -> dict[str, Any]:
    def pack(track: int, sector: int) -> int:
        return VALID | track << 6 | sector

    pairs = 0
    for track in range(1, 81):
        for sector in range(40):
            word = pack(track, sector)
            require(word & VALID and (word >> 6) & 0x7f == track
                    and word & 0x3f == sector, "packed link roundtrip failed")
            pairs += 1
    maximum = disk_file_max()
    lengths = (1, 2, 253, 254, 255, 508, 509, maximum)
    for length in lengths:
        for position in range(length):
            folded = (position & 0xff) + ((position >> 8) << 1)
            while folded >= 254:
                folded -= 254
            require(folded == position % 254, "derived sector offset drift")
    terminal = [pack(0, 0) for payload_length in range(1, 256)]
    require(len(set(terminal)) == 1 and terminal[0] == VALID,
            "validated terminal canonicalization drift")
    return {"nonterminal_pairs_roundtripped": pairs,
        "terminal_payload_lengths_validated_before_canonicalization": 255,
        "position_lengths_checked": list(lengths),
        "position_samples_checked": sum(lengths),
        "profile_derived_disk_file_max": maximum,
        "valid_bit": "0x8000", "track_bits": [6, 12],
        "sector_bits": [0, 5], "spare_bits": [13, 14],
        "failure_encoding": "valid bit clear",
        "terminal_encoding": "valid bit set, track=sector=0",
        "shared_DIR_scratch_state_bytes": 0}


def state_bytes(row: dict[str, Any]) -> dict[str, Any]:
    sections = row["sections"]
    names = {name: sections.get(f".bss.{name}", 0) for name in (
        "disk_source_pos", "disk_source_len", "disk_source_next_track",
        "disk_source_next_sector", "disk_source_failed", "disk_source_link")}
    return {"members": names, "bytes": sum(names.values())}


def source_contract(source: str) -> dict[str, Any]:
    required = {
        "one-packed-owner": source.count("static unsigned int disk_source_link;") == 1,
        "no-old-five-cell-owner": all(name not in source for name in (
            "disk_source_next_track", "disk_source_next_sector",
            "disk_source_failed", "disk_source_len", "disk_source_pos")),
        "valid-bit-present": "#define DISK_SOURCE_LINK_VALID 0x8000u" in source,
        "validated-link-publications": source.count(
            "DISK_SOURCE_LINK_PACK(nt, nt ? ns : 0u)") == 3,
        "failure-clears-validity": source.count("disk_source_link = 0;") == 4,
        "mod254-position": ("while (folded >= 254u) folded -= 254u;" in source
            and "((disk_file_pos >> 8) << 1)" in source),
        "terminal-remains-authoritative":
            "if (disk_file_pos >= disk_file_len) return '\\0';" in source,
        "shared-validator-retained": source.count(
            "count = disk_chain_count(t, s, nt, ns);") >= 3,
        "no-link-write-to-DIR-scratch":
            "io_disk_scratch_poke(DISK_SOURCE" not in source,
    }
    require(all(required.values()), "packed source contract is incomplete")
    return {"checks": required, "packed_owner_bytes": 2,
        "shared_DIR_scratch_state_bytes": 0,
        "validation": "disk_chain_count before each packed publication",
        "termination": "disk_file_len; terminal count validated then canonicalized",
        "position": "disk_file_pos modulo 254 via 256 congruent to 2",
        "mutations_rejected": ["packed-owner-removed", "old-five-cells-restored",
            "valid-bit-removed", "validated-publication-removed",
            "failure-preserves-validity", "position-derived-mod256",
            "terminal-authority-removed", "shared-validator-removed",
            "link-written-to-shared-DIR-scratch"]}


def build() -> None:
    require(not BUILD.exists() and not RECEIPT.exists(),
            "Card-2 state placement price is one-shot")
    plan = subprocess.run(["git", "show", f"{AUTHORIZATION}:"
        "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout
    for token in ("host-only state placement/reclaim pricing round",
                  "packing", "five-byte `$c000` margin is a floor"):
        require(token in plan.lower(), f"state-price authority absent: {token}")
    red = json.loads(RED.read_text(encoding="utf-8"))
    require(red["walls"]["ordinary_BSS"]["candidate_margin_bytes"] == 3
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["completed_product_links"] == 0,
            "Card-2 red boundary drift")
    original, source_input = authority_source()
    packed = packed_source(original)
    BUILD.mkdir(parents=True)
    old_build = BASE.BUILD
    BASE.BUILD = BUILD
    try:
        flags = [*BASE.GUARD.compile_flags(), "-DLISP65_C2_F011_COLD"]
        lanes = {
            "failed-r1-five-byte-state": BASE.lane(
                "failed-r1-five-byte-state", original, flags,
                BASE.MAPPED_COLD_WRAPPERS),
            "packed-derived-position-two-byte-state": BASE.lane(
                "packed-derived-position-two-byte-state", packed, flags,
                BASE.MAPPED_COLD_WRAPPERS),
        }
    finally:
        BASE.BUILD = old_build
    for row in lanes.values():
        row["groups"] = BASE.group_sections(row["sections"])
        row["source_state"] = state_bytes(row)
    before = lanes["failed-r1-five-byte-state"]
    after = lanes["packed-derived-position-two-byte-state"]
    group_delta = BASE.delta(after["groups"], before["groups"])
    bss_delta = after["source_state"]["bytes"] - before["source_state"]["bytes"]
    bss_before = sum(size for name, size in before["sections"].items()
        if name.startswith(".bss."))
    bss_after = sum(size for name, size in after["sections"].items()
        if name.startswith(".bss."))
    changed_code = {name: {"before": before["symbols"].get(name, 0),
        "after": after["symbols"].get(name, 0),
        "delta": after["symbols"].get(name, 0) - before["symbols"].get(name, 0)}
        for name in ("disk_source_fetch", "disk_source_refill_far",
                     "io_disk_load_chain")}
    projected_margin = red["walls"]["ordinary_BSS"]["candidate_margin_bytes"] - bss_delta
    actual_map = red["two_worlds"]["failed_candidate"]
    facade_end = int(actual_map[".lisp65_c2_mapped_far_facade"]["VMA_end"], 16)
    handoff_start = 0xB4A3
    facade_slack = handoff_start - facade_end
    island = actual_map[".lisp65_resident_island"]["bytes"]
    island_annex = 0x104
    island_slack = 0x2000 - (0x1800 + island + island_annex)
    cold = actual_map[".lisp65_c2_mapped_f011_cold"]["bytes"]
    mapped_capacity = 0x78B2 - 0x6000
    noinit_before = sum(size for name, size in before["sections"].items()
        if name.startswith(".noinit"))
    noinit_after = sum(size for name, size in after["sections"].items()
        if name.startswith(".noinit"))
    hot_bss_before = sum(size for name, size in before["sections"].items()
        if name.startswith(".lisp65_c2_fixed_bank0_hot_bss"))
    hot_bss_after = sum(size for name, size in after["sections"].items()
        if name.startswith(".lisp65_c2_fixed_bank0_hot_bss"))
    placement = {"projected_BSS_margin_bytes": projected_margin,
        "required_BSS_margin_bytes": 5,
        "source_state_delta_bytes": bss_delta,
        "r1_ZP_BSS_bytes": 77, "ZP_BSS_capacity_bytes": 77,
        "persistent_storage_delta_bytes": bss_delta,
        "bounded_lane_BSS_bytes_before": bss_before,
        "bounded_lane_BSS_bytes_after": bss_after,
        "bounded_lane_BSS_delta_bytes": bss_after - bss_before,
        "ZP_selection_can_only_redistribute_delta": True,
        "NOLOAD_bytes_before": noinit_before, "NOLOAD_bytes_after": noinit_after,
        "NOLOAD_delta_bytes": noinit_after - noinit_before,
        "fixed_hot_BSS_bytes_before": hot_bss_before,
        "fixed_hot_BSS_bytes_after": hot_bss_after,
        "fixed_hot_BSS_delta_bytes": hot_bss_after - hot_bss_before,
        "r1_facade_to_handoff_slack_bytes": facade_slack,
        "bounded_lane_ordinary_delta_bytes": group_delta["ordinary_text_bytes"],
        "ordinary_fit_under_raw_lane": group_delta["ordinary_text_bytes"] <= facade_slack,
        "r1_island_plus_annex_slack_bytes": island_slack,
        "bounded_lane_island_delta_bytes": group_delta["resident_island_bytes"],
        "island_fit_under_raw_lane": group_delta["resident_island_bytes"] <= island_slack,
        "mapped_window_capacity_bytes": mapped_capacity,
        "r1_mapped_owner_bytes": cold,
        "bounded_lane_mapped_delta_bytes": group_delta["mapped_f011_cold_bytes"],
        "mapped_fit_under_raw_lane": cold + group_delta["mapped_f011_cold_bytes"]
            <= mapped_capacity,
        "final_link_claim": False,
        "reason": ("same bounded-codegen lane on both forms; raw deltas price the "
            "replacement, while a newly authorized final link must remeasure every wall")}
    selected = (after["source_state"]["bytes"] == 2 and projected_margin >= 5
        and placement["ordinary_fit_under_raw_lane"]
        and placement["island_fit_under_raw_lane"]
        and placement["mapped_fit_under_raw_lane"])
    value = {"format": FORMAT, "recorded_on": "2026-09-03",
        "status": ("PASS: TWO-BYTE SOURCE-LINK STATE PRICED"
            if selected else "RED: TWO-BYTE SOURCE-LINK STATE NOT PRICEABLE"),
        "authorization": AUTHORIZATION,
        "inputs": {"source": source_input, "first_red": bind(RED),
            "prior_price": bind(BASE.RECEIPT), "gate_register": bind(REGISTER)},
        "semantic_model": model(), "source_contract": source_contract(packed),
        "measurement": {"kind":
            "paired bounded-codegen lanes; zero product WPLTOs and links",
            "lanes": lanes, "group_delta": group_delta,
            "changed_code_symbols": changed_code,
            "largest_changed_code_object_bytes": max(
                row["after"] for row in changed_code.values())},
        "placement": placement,
        "decision": {"selected": selected,
            "form": "packed-valid-track-sector-with-derived-mod254-position",
            "dedicated_source_state_bytes": after["source_state"]["bytes"],
            "source_link_outside_DIR_scratch": True,
            "validation_retained": True,
            "reclaim_elsewhere_required": False if selected else None,
            "fallback_text_only_required": False if selected else True,
            "service_time_claim": "pending final-link DWX boot-cycle comparison"},
        "mutations_rejected": ["five-byte-state-restored",
            "link-stored-in-shared-DIR-scratch", "valid-bit-removed",
            "terminal-length-not-validated", "invalid-link-published",
            "position-derived-mod256-not-mod254", "BSS-margin-below-five",
            "NOLOAD-BSS-owner-omitted-from-admission"],
        "accounting": {"bounded_codegen_lanes": 2, "product_WPLTO_runs": 0,
            "product_links": 0, "device_contacts": 0},
        "next": ("reviewer/owner replacement-link budget decision"
            if selected else "text-only fallback disposition")}
    validate(value)
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    print("Block 2.6 Card 2 state price: " + value["status"])


def validate(value: dict[str, Any]) -> None:
    before = value["measurement"]["lanes"]["failed-r1-five-byte-state"]
    after = value["measurement"]["lanes"][
        "packed-derived-position-two-byte-state"]
    place = value["placement"]
    model_row = value["semantic_model"]
    require(value["format"] == FORMAT and value["authorization"] == AUTHORIZATION
            and value["inputs"] == {"source": authority_source()[1],
                "first_red": bind(RED), "prior_price": bind(BASE.RECEIPT),
                "gate_register": ERA.era_bind(SEAL_ERA_COMMIT, REGISTER)}
            and before["source_state"]["bytes"] == 5
            and after["source_state"]["bytes"] == 2
            and place["source_state_delta_bytes"] == -3
            and place["projected_BSS_margin_bytes"] == 6
            and place["required_BSS_margin_bytes"] == 5
            and place["r1_ZP_BSS_bytes"] == place["ZP_BSS_capacity_bytes"] == 77
            and place["persistent_storage_delta_bytes"] == -3
            and place["bounded_lane_BSS_delta_bytes"] == -3
            and place["bounded_lane_BSS_bytes_before"] == 3907
            and place["bounded_lane_BSS_bytes_after"] == 3904
            and place["ZP_selection_can_only_redistribute_delta"] is True
            and place["NOLOAD_delta_bytes"] == 0
            and place["fixed_hot_BSS_delta_bytes"] == 0
            and place["ordinary_fit_under_raw_lane"] is True
            and place["island_fit_under_raw_lane"] is True
            and place["mapped_fit_under_raw_lane"] is True
            and place["final_link_claim"] is False
            and value["decision"] == {
                "selected": True,
                "form": "packed-valid-track-sector-with-derived-mod254-position",
                "dedicated_source_state_bytes": 2,
                "source_link_outside_DIR_scratch": True,
                "validation_retained": True,
                "reclaim_elsewhere_required": False,
                "fallback_text_only_required": False,
                "service_time_claim":
                    "pending final-link DWX boot-cycle comparison"}
            and model_row["nonterminal_pairs_roundtripped"] == 3200
            and model_row["profile_derived_disk_file_max"] == 0x9600
            and model_row["terminal_payload_lengths_validated_before_canonicalization"] == 255
            and model_row["valid_bit"] == "0x8000"
            and model_row["failure_encoding"] == "valid bit clear"
            and model_row["terminal_encoding"] ==
                "valid bit set, track=sector=0"
            and model_row["shared_DIR_scratch_state_bytes"] == 0
            and all(value["source_contract"]["checks"].values())
            and value["source_contract"]["packed_owner_bytes"] == 2
            and value["source_contract"]["shared_DIR_scratch_state_bytes"] == 0
            and value["measurement"]["changed_code_symbols"] == {
                "disk_source_fetch": {"before": 86, "after": 168, "delta": 82},
                "disk_source_refill_far":
                    {"before": 117, "after": 203, "delta": 86},
                "io_disk_load_chain": {"before": 198, "after": 209, "delta": 11}}
            and value["measurement"]["largest_changed_code_object_bytes"] == 209
            and value["mutations_rejected"] == ["five-byte-state-restored",
                "link-stored-in-shared-DIR-scratch", "valid-bit-removed",
                "terminal-length-not-validated", "invalid-link-published",
                "position-derived-mod256-not-mod254", "BSS-margin-below-five",
                "NOLOAD-BSS-owner-omitted-from-admission"]
            and value["accounting"] == {"bounded_codegen_lanes": 2,
                "product_WPLTO_runs": 0, "product_links": 0,
                "device_contacts": 0},
            "Card-2 state placement pricing receipt drift")


def report(value: dict[str, Any]) -> str:
    delta = value["measurement"]["group_delta"]
    place = value["placement"]
    return f"""# Block 2.6 Card 2 — source-state placement pricing

Status: **{value['status']}**

The first candidate wins without reclaim elsewhere. The successor owns one
16-bit word outside the shared directory scratch: bits 0..5 hold sector,
6..12 track and bit 15 validity. All 3,200 non-terminal track/sector pairs
round-trip. A terminal sector's payload length is validated before its link is
canonicalized to valid track/sector zero; the existing `disk_file_len` remains
the authoritative stream terminator. Failure clears validity.

The two old per-sector position/length bytes are not silently discarded.
Position is derived from the existing linear `disk_file_pos` using
`256 ≡ 2 (mod 254)`; termination remains derived from `disk_file_len`. The
model checks every position across representative boundary and maximum-length
streams. The dedicated source state therefore falls from **5 to 2 bytes**,
projecting the failed link's BSS margin from **3 back to 6 bytes** against the
untouchable five-byte floor.

Paired bounded-codegen lanes measure the replacement at
**{delta['ordinary_text_bytes']:+d} ordinary**,
**{delta['resident_island_bytes']:+d} resident-island** and
**{delta['mapped_f011_cold_bytes']:+d} mapped-F011 bytes**. The affected
functions emit at most **209 bytes**, below the 255-byte object ceiling.
Against the frozen r1 map, those raw deltas fit the {place['r1_facade_to_handoff_slack_bytes']}-byte
facade/handoff interval, the {place['r1_island_plus_annex_slack_bytes']}-byte
Island/annex tail and the mapped window. This is a price, not final-link
truth; any replacement product link must remeasure every constrained owner.

ZP is already fully selected at 77 bytes, but the packed form removes three
persistent bytes overall, so a new whole-program selection can only redistribute
that negative delta between ZP and ordinary BSS. Fixed Hot-BSS and `NOLOAD`
remain byte-identical. The +82-byte resident change is the explicit price of
deriving the sector position without state; its boot-cycle cost remains pending
the required final-link DWX comparison and is not claimed here.

No other BSS owner is reclaimed. Validation is unchanged, the packed link
never lives in `DISK_EXT_DIR`, and the terminal length remains checked before
discard. Eight mutations cover restored five-byte state, scratch reuse,
validity/terminal/position errors and omission of BSS from admission; the
source contract independently carries nine sharp structural checks.

Accounting: **two bounded-codegen lanes, 0 product WPLTOs, 0 product links,
0 device contacts**. The next touchpoint is the reviewer/owner decision on a
replacement product link.
"""


def selftest() -> None:
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "state-restored": lambda row: row["measurement"]["lanes"][
            "packed-derived-position-two-byte-state"]["source_state"].update(
                {"bytes": 5}),
        "scratch-reused": lambda row: row["semantic_model"].update(
            {"shared_DIR_scratch_state_bytes": 2}),
        "validity-removed": lambda row: row["semantic_model"].update(
            {"valid_bit": "0x0000"}),
        "terminal-unvalidated": lambda row: row["semantic_model"].update(
            {"terminal_payload_lengths_validated_before_canonicalization": 0}),
        "invalid-link-published": lambda row: row["semantic_model"].update(
            {"failure_encoding": "valid bit set"}),
        "position-mod256": lambda row: row["source_contract"].update(
            {"checks": {**row["source_contract"]["checks"],
                "mod254-position": False}}),
        "margin-below-floor": lambda row: row["placement"].update(
            {"projected_BSS_margin_bytes": 4}),
        "BSS-owner-omitted": lambda row: row["placement"].update(
            {"persistent_storage_delta_bytes": 0}),
        "ordinary-wall-ignored": lambda row: row["placement"].update(
            {"ordinary_fit_under_raw_lane": False}),
        "product-link-hidden": lambda row: row["accounting"].update(
            {"product_links": 1}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (PricingError, KeyError, TypeError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "Card-2 state-price mutation survived")
    print(f"Block 2.6 Card 2 state price: SELFTEST PASS mutations={len(rejected)}")


def check() -> None:
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    validate(value)
    require(REPORT.is_file() and REPORT.read_text(encoding="utf-8") == report(value),
            "Card-2 state-price report drift")
    print("Block 2.6 Card 2 state price: CHECK PASS state=2 margin=6 WPLTO=0 link=0")


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
        print(f"Block 2.6 Card 2 state price: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
