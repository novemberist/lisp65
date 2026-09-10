#!/usr/bin/env python3
"""Build Card 2's packed-state replacement after the r1 BSS wall."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import block_26_f011_product_card as CARD  # noqa: E402
import block_26_f011_state_placement_pricing as PRICE  # noqa: E402
import c2_bank2_composed_ownership as BANK2  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_transitive_map_nesting_gate as NESTING  # noqa: E402
import consolidated_consumption_authority as CONSUMPTION  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
AUTHORIZATION = "c3148b04"
PLAN_HEADER = (
    "## Reviewer authorization — card 2 replacement link after packing — 2026-09-03"
)
BUILD = ROOT / "build/2.6/card2-f011-product-r2"
PREFLIGHT = ROOT / "build/2.6/card2-f011-product-r2-preflight"
PLANE = PREFLIGHT / "setup-owned/static-plane/narrow-static"
WPLTO = BUILD / "wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
PROFILE = WPLTO / "resolved-profile.txt"
BOUND_PROFILE = PREFLIGHT / "card2-bound-feature-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
PLANE_RECEIPT = ARCH / "block-2.6-card2-f011-product-r2-plane.json"
PREFLIGHT_RECEIPT = ARCH / "block-2.6-card2-f011-product-r2-preflight.json"
SOURCE_PREFLIGHT = ARCH / "block-2.6-card2-f011-product-r2-source-preflight.json"
PRELINK_RED = ARCH / "block-2.6-card2-f011-product-r2-prelink-red.json"
DIFFERENCE = ARCH / "block-2.6-card2-f011-product-r2-difference.json"
RECEIPT = ARCH / "block-2.6-card2-f011-product-r2-receipt.json"
REPORT = ROOT / "docs/planning/2.6-card2-f011-product-r2-report.md"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-block-2.6-card2-f011-product-r2-v1"
STATUS = "PASS: BLOCK 2.6 CARD 2 PACKED F011 PRODUCT GREEN"
INITIAL_RED = ARCH / "block-2.6-card2-f011-product-r1-final-link-red.json"
RESIDENT_ISLAND_FLOOR = 5
SEALED_R2_SOURCE_COMMIT = "1f558365"
ORIGINAL_CONFIGURE = CARD.configure
_CONFIGURED = False


class ReplacementError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplacementError(message)


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


def sealed_source(path: Path) -> tuple[str, dict[str, Any]]:
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{SEALED_R2_SOURCE_COMMIT}:{relative}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    return raw.decode(), {"path": relative, "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest()}


def git_section() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(PLAN_HEADER) == 1, "replacement authority section drift")
    payload = (PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]).split(
        "\n## ", 1)[0].rstrip().encode() + b"\n"
    folded = " ".join(payload.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("one replacement wplto", "one replacement product link",
                  "resident island against its own floor", "validity bit",
                  "no third link"):
        require(token in folded, f"replacement authority token absent: {token}")
    return {"commit": AUTHORIZATION, "path": relative,
            "section": PLAN_HEADER, "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest()}


def authority() -> dict[str, Any]:
    return {"commission": git_section(), "initial_final_link_red": bind(INITIAL_RED),
        "state_placement_price": bind(PRICE.RECEIPT),
        "right": "one replacement WPLTO and one replacement product link",
        "replacement_budget": {"WPLTO_runs": 1, "product_links": 1,
            "device_contacts": 0},
        "card_history_before_replacement": {"WPLTO_runs": 1,
            "product_link_attempts": 1, "completed_product_links": 0}}


def packed_link_model() -> dict[str, Any]:
    valid = 0x8000

    def pack(track: int, sector: int) -> int:
        return valid | track << 6 | sector

    def can_read(word: int, *, check_valid: bool = True) -> bool:
        track = (word >> 6) & 0x7f
        return (not check_valid or bool(word & valid)) and bool(track)

    pairs = 0
    stale_words = []
    for track in range(1, 81):
        for sector in range(40):
            word = pack(track, sector)
            require(can_read(word), "valid packed link cannot reach its sector")
            stale = word & ~valid
            require(not can_read(stale), "stale packed link reached a foreign chain")
            stale_words.append(stale)
            pairs += 1
    require(not can_read(0), "cleared packed link reached a foreign chain")
    mutant_reads = sum(can_read(word, check_valid=False) for word in stale_words)
    require(mutant_reads == pairs, "validity mutation is not sharp")
    return {"nonterminal_pairs": pairs, "cleared_words_rejected": 1,
        "stale_words_rejected": len(stale_words),
        "mutations_rejected": ["validity-check-removed-allows-stale-chain"]}


def source_checks(source: str, wrappers: str) -> dict[str, bool]:
    return {
        "one-packed-owner": source.count(
            "static unsigned int disk_source_link;") == 1,
        "old-five-cell-owner-absent": all(name not in source for name in (
            "disk_source_pos", "disk_source_len", "disk_source_next_track",
            "disk_source_next_sector", "disk_source_failed")),
        "validity-tested-before-read": source.count(
            "!(link & DISK_SOURCE_LINK_VALID)") == 2,
        "failure-clears-validity": source.count("disk_source_link = 0;") == 4,
        "validated-publication": source.count(
            "DISK_SOURCE_LINK_PACK(nt, nt ? ns : 0u)") == 3,
        "position-derived-mod254": (
            "while (folded >= 254u) folded -= 254u;" in source and
            "((disk_file_pos >> 8) << 1)" in source),
        "length-remains-terminator": source.count(
            "if (disk_file_pos >= disk_file_len) return '\\0';") == 2,
        "shared-validator-retained": source.count(
            "count = disk_chain_count(t, s, nt, ns);") >= 3,
        "busy-bounded": "while (fuel--)" in source,
        "completion-bits-evaluated": (
            "(status & LISP65_F011_STATUS_READ_MASK) !=" in source),
        "three-mapped-wrappers": wrappers.count(
            "jsr c2_mapped_far_enter") == 3,
    }


def source_contract(source: str, wrappers: str) -> dict[str, Any]:
    checks = source_checks(source, wrappers)
    require(all(checks.values()), "packed F011 source contract is incomplete")
    mutations = {
        "validity-check-removed": source.replace(
            "!(link & DISK_SOURCE_LINK_VALID)", "0", 1),
        "failure-preserves-validity": source.replace(
            "disk_source_link = 0;", "/* retained stale link */", 1),
        "validated-publication-removed": source.replace(
            "DISK_SOURCE_LINK_PACK(nt, nt ? ns : 0u)",
            "DISK_SOURCE_LINK_PACK(nt, ns)", 1),
        "position-derived-mod256": source.replace(
            "while (folded >= 254u) folded -= 254u;", "", 1),
        "terminal-authority-removed": source.replace(
            "if (disk_file_pos >= disk_file_len) return '\\0';", ""),
    }
    rejected = []
    for name, mutant in mutations.items():
        if not all(source_checks(mutant, wrappers).values()):
            rejected.append(name)
    require(rejected == list(mutations), "packed source mutation survived")
    return {"checks": checks, "packed_owner_bytes": 2,
        "link_model": packed_link_model(), "mutations_rejected": rejected}


def semantic_source_gate() -> dict[str, Any]:
    source_path = ROOT / "src/io.c"
    wrappers_path = ROOT / "src/optional/c2_f011_cold_wrappers.s"
    source = source_path.read_text(encoding="utf-8")
    wrappers = wrappers_path.read_text(encoding="utf-8")
    return {"status": "PASS: PACKED F011 SOURCE EDGES BOUND",
        "source": bind(source_path), "wrappers": bind(wrappers_path),
        **source_contract(source, wrappers)}


def sealed_semantic_source_gate() -> dict[str, Any]:
    source_path = ROOT / "src/io.c"
    wrappers_path = ROOT / "src/optional/c2_f011_cold_wrappers.s"
    source, source_binding = sealed_source(source_path)
    wrappers, wrappers_binding = sealed_source(wrappers_path)
    return {"status": "PASS: PACKED F011 SOURCE EDGES BOUND",
        "source": source_binding, "wrappers": wrappers_binding,
        **source_contract(source, wrappers)}


def source_preflight() -> dict[str, Any]:
    """Materialize generated sources from the already configured root graph."""
    output = PREFLIGHT / "candidate-generated-source-preflight-card2-r2"
    mapping = CARD.BASE.CHAIN.LINK.materialize_candidate_sources(output)
    features = CARD.bound_features()
    sources = CARD.projected_source_list(mapping, features)
    require(len(sources) == 71 and len(mapping) >= 20 and len(features) == 36
            and str(PRODUCT.F011_COLD_SOURCE) in sources
            and PRODUCT.F011_COLD_FEATURE in features,
            "replacement source/profile population drift")
    value = {"format": FORMAT + "-source-preflight",
        "recorded_on": "2026-09-03",
        "status": "PASS: CARD-2 PACKED GENERATED SOURCE WORLD ARMED",
        "compiler_sources": {"total": len(sources), "generated": len(mapping)},
        "qualified_predecessor_profile": bind(
            CARD.BASE.CHAIN.LINK.predecessor_profile()),
        "feature_authority": CARD.materialize_bound_feature_profile(),
        "feature_count": len(features), "F011_feature": PRODUCT.F011_COLD_FEATURE,
        "F011_source": PRODUCT.F011_COLD_SOURCE.relative_to(ROOT).as_posix(),
        "mutations_rejected": ["F011-feature-empty", "F011-source-owner-omitted",
            "product-world-unbound", "packed-source-state-omitted"]}
    SOURCE_PREFLIGHT.write_bytes(canonical(value))
    return value


def composed_bank2() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    f011 = truth.section(".lisp65_c2_mapped_f011_cold")
    mapped = ((".lisp65_c2_mapped_f011_cold", "__lisp65_c2_mapped_f011_cold"),
        (".lisp65_c2_mapped_far_service", "__lisp65_c2_mapped_far_service"),
        (".lisp65_c2_mapped_product_cold", "__lisp65_c2_mapped_product_cold"))
    result = BANK2.derive(elf=ELF,
        plane=PLANE / "v6-semantics/bank2-static-code.bin", readobj=READOBJ,
        mapped_owners=mapped, placement_policy="map-page-top-derived",
        expected_vmas={".lisp65_c2_mapped_f011_cold": 0x78B2 - f011.bytes,
            ".lisp65_c2_mapped_far_service": 0x78B2,
            ".lisp65_c2_mapped_product_cold": 0x7E8D})
    require(result["overlaps"] == [], "packed F011 composed Bank-2 overlap")
    return result


def initialized_zp_load_fits(load_start: int, initialized_bytes: int,
                             text_start: int) -> bool:
    """Physical load ownership, independently of CPU-space ZP allocation.

    Callers derive these values from their consumed map/ELF. A pre-WPLTO
    projection must also bind its source transformation; it never replaces
    checking the emitted seed and final load intervals.
    """
    return (all(type(value) is int for value in
                (load_start, initialized_bytes, text_start))
            and 0 <= load_start <= text_start
            and 0 <= initialized_bytes <= text_start - load_start)


def initialized_zp_linker_has_guard(text: str) -> bool:
    import re
    expression = (r'ASSERT\s*\(\s*LOADADDR\s*\(\s*\.zp\.data\s*\)\s*'
                  r'\+\s*SIZEOF\s*\(\s*\.zp\.data\s*\)\s*<=\s*'
                  r'ADDR\s*\(\s*\.text\s*\)\s*,')
    return len(re.findall(expression, text)) == 1


def initialized_zp_load_selftest() -> None:
    # Boundary controls have no fixed product origin or capacity pin.
    for start in (0, 8199, 32768):
        for capacity in (0, 1, 12, 15):
            for size in range(18):
                assert initialized_zp_load_fits(start, size, start + capacity) == (size <= capacity)
    assert not initialized_zp_load_fits(12, 0, 11)
    assert not initialized_zp_load_fits(12, -1, 20)
    assert not initialized_zp_load_fits(12, True, 20)
    import c2_product_substitution_link as product
    saved = product.FULL_MAP_OWNERSHIP, product.FIXED_RAW_BSS_OWNERS
    try:
        product.FULL_MAP_OWNERSHIP = True
        for fixed_raw in (False, True):
            product.FIXED_RAW_BSS_OWNERS = fixed_raw
            script = product.full_map_platform_c_ld()
            assert initialized_zp_linker_has_guard(script)
            guard = product.ZP_INITIALIZER_LOAD_ASSERTION
            assert not initialized_zp_linker_has_guard(script.replace(guard, ''))
            assert not initialized_zp_linker_has_guard(script + guard)
            assert not initialized_zp_linker_has_guard(script.replace(
                'LOADADDR(.zp.data) + SIZEOF(.zp.data) <= ADDR(.text)',
                'LOADADDR(.zp.data) + SIZEOF(.zp.data) >= ADDR(.text)'))
    finally:
        product.FULL_MAP_OWNERSHIP, product.FIXED_RAW_BSS_OWNERS = saved


def zero_page_within_bounds(data, bss, noinit, convergence, fixed) -> bool:
    return (data.address + data.bytes <= bss.address and
            bss.address + bss.bytes <= noinit.address and
            noinit.address + noinit.bytes <= convergence.address and
            convergence.address == 0x87 and convergence.bytes == 2 and
            fixed.address == 0x89 and fixed.bytes == 7)


def zero_page_population_selftest() -> None:
    from types import SimpleNamespace
    def section(address, size):
        return SimpleNamespace(address=address, bytes=size)
    # The same live footprint split differently by LTO remains within bounds.
    tail = (section(0x7B, 12), section(0x87, 2), section(0x89, 7))
    for initialized, zeroed in ((12, 77), (15, 74)):
        data, bss = section(0x22, initialized), section(0x22 + initialized, zeroed)
        require(zero_page_within_bounds(data, bss, *tail), "legal ZP partition rejected")
        require(not zero_page_within_bounds(section(data.address, initialized + 1), bss, *tail),
                "initialized-ZP overlap accepted")
        require(not zero_page_within_bounds(data, section(bss.address, zeroed + 1), *tail),
                "zeroed-ZP overlap accepted")
    old_accepts = bss.bytes == 77 and zero_page_within_bounds(data, bss, *tail)
    require(not old_accepts, "historical population pin accepted successor")


def bounded_owners(truth: ElfTruth) -> dict[str, Any]:
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    bss = truth.section(".bss")
    island = truth.section(".lisp65_resident_island")
    annex = truth.section(".lisp65_resident_island_annex")
    zp_data = truth.section(".zp.data")
    zp_bss = truth.section(".zp.bss")
    # The input `.zp.noinit` members are collected into the final `.zp`
    # output section; qualify the emitted section identity, not its mnemonic
    # input name from the map file.
    zp_noinit = truth.section(".zp")
    convergence_zp = truth.section(".lisp65_c2_convergence_zp")
    fixed_zp = truth.section(".lisp65_c2_fixed_zp")
    noinit = truth.section(".noinit")
    heap = truth.symbol("__heap_start").value
    text_margin = facade.address - (text.address + text.bytes)
    bss_margin = 0xC000 - (bss.address + bss.bytes)
    island_end = annex.address + annex.bytes
    island_margin = 0x2000 - island_end
    noinit_margin = heap - (noinit.address + noinit.bytes)
    require(text_margin >= 32, "ordinary-text owner below 32-byte floor")
    require(bss_margin >= 5, "ordinary-BSS owner below five-byte floor")
    require(island.address == 0x1800 and
            annex.address >= island.address + island.bytes and
            island_margin >= RESIDENT_ISLAND_FLOOR,
            "resident-Island owner below its five-byte floor")
    # LTO may move live owners between initialized ZP and zeroed ZP.
    # Their emitted intervals, not a predecessor's 77-byte population,
    # are the bound; the final section inventory binds each exact owner.
    require(zero_page_within_bounds(zp_data, zp_bss, zp_noinit, convergence_zp, fixed_zp),
            "ZP owners escaped their final-link intervals")
    require(noinit.address == 0xC34D and noinit_margin >= 0,
            "NOLOAD owner crossed the derived heap floor")
    symbols = {row.name: row for row in truth.symbols}
    require(symbols["disk_source_link"].bytes == 2 and not any(
        name in symbols for name in ("disk_source_pos", "disk_source_len",
            "disk_source_next_track", "disk_source_next_sector",
            "disk_source_failed")), "final source-link owner is not two bytes")
    return {
        "ordinary_text": {"margin_bytes": text_margin, "floor_bytes": 32},
        "ordinary_BSS": {"margin_bytes": bss_margin, "floor_bytes": 5,
            "bytes": bss.bytes, "end": hex(bss.address + bss.bytes)},
        "resident_island": {"payload_bytes": island.bytes,
            "annex_bytes": annex.bytes, "margin_bytes": island_margin,
            "alignment_gap_bytes": annex.address - (island.address + island.bytes),
            "floor_bytes": RESIDENT_ISLAND_FLOOR,
            "floor_authority": "late-product resident-island safety floor"},
        "zero_page": {"selected_zp_bss_bytes": zp_bss.bytes,
            "zp_noinit_bytes": zp_noinit.bytes,
            "convergence_interval": [convergence_zp.address,
                convergence_zp.address + convergence_zp.bytes],
            "fixed_interval": [fixed_zp.address,
                fixed_zp.address + fixed_zp.bytes], "within_bounds": True},
        "NOLOAD": {"address": hex(noinit.address), "bytes": noinit.bytes,
            "heap_start": hex(heap), "margin_bytes": noinit_margin,
            "floor_bytes": 0},
        "source_link": {"symbol": "disk_source_link", "bytes": 2,
            "old_five_members_present": False},
        "all_floors_green": True,
    }


def final_gate() -> dict[str, Any]:
    CARD.configure()
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    compiler = load(Path(str(PRG) + ".compiler-input-consumption.json"))
    final_input = load(Path(str(PRG) + ".authority-input-consumption.json"))
    seed_input = load(WPLTO / "resident-island-seed.prg.authority-input-consumption.json")
    final_authority = CONSUMPTION.validate_authority_input_inventory(final_input)
    seed_authority = CONSUMPTION.validate_authority_input_inventory(seed_input)
    require(final_authority["categories"] == seed_authority["categories"]
            and final_authority["features"] == seed_authority["features"] == 36
            and "product-world-identity" in final_authority["categories"]
            and final_input["product_world_identity"] ==
                seed_input["product_world_identity"] == CARD.product_world_identity()
            and compiler["consumed_value"] == CARD.EXTENT,
            "replacement consumers escaped candidate authority")
    nesting = NESTING.check(ELF)
    require(".lisp65_c2_mapped_f011_cold" in nesting["mapped_sections"]
            and set(("f011_wait_not_busy", "f011_read_at_far",
                     "io_disk_read_sector_far", "disk_source_refill_far")) <=
                set(nesting["tenants"]) and nesting["violations"] == [],
            "packed F011 owner escaped transitive nesting proof")
    symbol_names = ("f011_read_at", "f011_read_at_far",
        "io_disk_read_sector", "io_disk_read_sector_far",
        "disk_source_refill", "disk_source_refill_far", "disk_source_fetch")
    return {"status": "PASS: FINAL PACKED CARD-2 F011 PRODUCT CLOSED",
        "static_extent": CARD.EXTENT,
        "F011_registration": PRODUCT.f011_cold_inventory_registration(),
        "compiler_consumption": compiler, "final_authority": final_input,
        "seed_authority": seed_input, "authority_inventory": final_authority,
        "bounded_owners": bounded_owners(truth),
        "composed_bank2": composed_bank2(), "nesting": nesting,
        "emitted_symbols": {name: truth.symbol(name).bytes for name in symbol_names},
        "semantics": semantic_source_gate(),
        "packed_prefilter": {"status": "PENDING"},
        "boot_cycles": {"status": "PENDING"}}


def validate(value: dict[str, Any], *, require_prefilter: bool = True) -> None:
    final = value["final_product"]
    owners = final["bounded_owners"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["difference"]["unexplained_members"] == 0
            and owners["all_floors_green"] is True
            and owners["ordinary_text"]["margin_bytes"] >= 32
            and owners["ordinary_BSS"]["margin_bytes"] >= 5
            and owners["resident_island"]["margin_bytes"] >=
                owners["resident_island"]["floor_bytes"] == RESIDENT_ISLAND_FLOOR
            and owners["zero_page"]["selected_zp_bss_bytes"] == 77
            and owners["zero_page"]["within_bounds"] is True
            and owners["NOLOAD"]["margin_bytes"] >= owners["NOLOAD"]["floor_bytes"]
            and owners["source_link"]["bytes"] == 2
            and final["composed_bank2"]["overlaps"] == []
            and final["nesting"]["violations"] == []
            and final["semantics"]["link_model"]["stale_words_rejected"] == 3200
            and value["artifacts_before"] == value["artifacts_after"] ==
                CARD.frozen_artifacts()
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["attempt_accounting"]["product_links"] == 1
            and value["attempt_accounting"]["device_contacts"] == 0,
            "Card-2 replacement receipt drift")
    if require_prefilter:
        require(final["packed_prefilter"]["status"] == "PASS"
                and final["boot_cycles"]["status"] == "PASS"
                and value["review_ready"] is True,
                "Card-2 replacement DWX rows remain open")


def write_report(value: dict[str, Any]) -> None:
    final = value["final_product"]
    owners = final["bounded_owners"]
    bank = final["composed_bank2"]
    history = value.get("attempt_history", {})
    REPORT.write_text(f"""# Block 2.6 Card 2 — packed F011 product report

Status: **{value['status']}**

The source-stream continuation is one validated 16-bit link word. Its valid
bit, track and sector round-trip all 3,200 legal non-terminal pairs; cleared
and stale words fail before any sector read. Position is derived from the
existing linear stream counter modulo 254, while `disk_file_len` remains the
termination authority.

Every simultaneously live constrained owner is measured on the final link:
ordinary text leaves **{owners['ordinary_text']['margin_bytes']} bytes**
against 32, ordinary BSS leaves **{owners['ordinary_BSS']['margin_bytes']}**
against 5, and resident Island plus annex leaves
**{owners['resident_island']['margin_bytes']} bytes** against its named
**{owners['resident_island']['floor_bytes']}-byte late-product floor**. The
77-byte ZP selection and its fixed successors are in bounds; NOLOAD leaves
{owners['NOLOAD']['margin_bytes']} bytes before the derived heap start. The
composed Bank-2 map is disjoint and its largest contiguous hole is
**{bank['largest_contiguous_hole']['bytes']:,} bytes**.

The initial five-byte-state attempt remains sealed at
`{history.get('initial_red', {}).get('sha256', 'pending')}`. This replacement
spends one WPLTO and one completed product link; across the card that is two
WPLTO runs, two link attempts and one final pair. Scope and Acceptance are
read-only over that pair. Packed DWX corruption and boot-cycle rows are
**{final['packed_prefilter']['status']}** / **{final['boot_cycles']['status']}**;
there were zero physical device contacts.
""", encoding="utf-8")


def configure_once() -> None:
    """Install the deep product graph once per process.

    The inherited configurator deliberately rejects a duplicate root hook.
    Every replacement action enters through a fresh process, while the card's
    nested gates call ``configure`` repeatedly inside that one action.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    ORIGINAL_CONFIGURE()
    _CONFIGURED = True


def patch_card() -> None:
    for name, value in {
        "AUTHORIZATION": AUTHORIZATION, "PLAN_HEADER": PLAN_HEADER,
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "PLANE": PLANE,
        "WPLTO": WPLTO, "ELF": ELF, "PRG": PRG, "PROFILE": PROFILE,
        "BOUND_PROFILE": BOUND_PROFILE, "INVOCATION": INVOCATION,
        "PLANE_RECEIPT": PLANE_RECEIPT, "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT,
        "SOURCE_PREFLIGHT": SOURCE_PREFLIGHT, "PRELINK_RED": PRELINK_RED,
        "DIFFERENCE": DIFFERENCE, "RECEIPT": RECEIPT, "REPORT": REPORT,
        "DRIVER": DRIVER, "FORMAT": FORMAT, "STATUS": STATUS,
    }.items():
        setattr(CARD, name, value)
    CARD.git_section = git_section
    CARD.authority = authority
    CARD.semantic_source_gate = semantic_source_gate
    CARD.source_preflight = source_preflight
    CARD.composed_bank2 = composed_bank2
    CARD.final_gate = final_gate
    CARD.validate = validate
    CARD.write_report = write_report
    CARD.configure = configure_once


def preflight() -> None:
    patch_card()
    require(not any(path.exists() for path in (
        BUILD, PREFLIGHT, PLANE_RECEIPT, PREFLIGHT_RECEIPT,
        SOURCE_PREFLIGHT, DIFFERENCE, RECEIPT)),
        "Card-2 replacement preflight is one-shot")
    CARD.configure()
    CARD.materialize_plane()
    CARD.materialize_bound_feature_profile()
    # The first configuration must precede Plane materialization so every
    # inherited geometry resolver sees this card's paths.  The successor
    # profile does not exist until materialization; install its three derived
    # consumers now, without reinstalling the non-idempotent root graph.
    CARD.BASE.CHAIN.LINK.predecessor_profile = lambda: BOUND_PROFILE
    CARD.BASE.CHAIN.LINK.predecessor_features = CARD.bound_features
    CARD.BASE.CHAIN.LINK.projected_source_list = CARD.projected_source_list
    gate, sources = CARD.configuration_gate(), CARD.source_preflight()
    boundary = {
        "initial_red": bind(INITIAL_RED), "state_price": bind(PRICE.RECEIPT),
        "bounded_owners_required_at_final_link": ["ordinary text", "ordinary BSS",
            "ZP", "NOLOAD", "resident Island", "mapped F011 cold owner"],
        "resident_island_floor_bytes": RESIDENT_ISLAND_FLOOR,
        "validity_model": packed_link_model(),
        "stop_before_scope_if_any_floor_red": True,
    }
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-09-03",
        "status": "PASS: BLOCK 2.6 CARD 2 F011 ARMED 0/1",
        "authority": authority(), "plane": bind(PLANE_RECEIPT),
        "configuration": gate, "source_preflight": bind(SOURCE_PREFLIGHT),
        "source_population": sources, "replacement_boundary": boundary,
        "requirements": ["product world bound before replacement WPLTO",
            "packed source-link validity fails closed", "every live constrained owner",
            "five-byte resident-Island floor", "five-byte ordinary-BSS floor",
            "32-byte ordinary-text floor", "transitive no-nested-MAP proof",
            "full difference attribution", "Scope and Acceptance read-only",
            "packed DWX corruption and boot-cycle rows", "zero device contacts"],
        "attempt_accounting": {"product_cards": 0, "WPLTO_runs": 0,
            "product_links": 0, "scope_runs": 0, "acceptance_runs": 0,
            "DWX_prefilter_runs": 0, "media_builds": 0, "device_contacts": 0}}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("Block 2.6 Card 2 replacement: PREFLIGHT PASS WPLTO=0/1 link=0/1")


def check_preflight() -> None:
    patch_card()
    value = load(PREFLIGHT_RECEIPT)
    require(value["authority"] == authority()
            and value["replacement_boundary"]["resident_island_floor_bytes"] == 5
            and value["replacement_boundary"]["validity_model"] == packed_link_model()
            and value["replacement_boundary"]["stop_before_scope_if_any_floor_red"],
            "Card-2 replacement preflight drift")
    # Reconstruct the sealed r2 configuration with its own source semantics.
    # The living r3 source deliberately implements the mapped error-return
    # successor and cannot be used to requalify its historical predecessor.
    CARD.semantic_source_gate = sealed_semantic_source_gate
    current = CARD.configuration_gate()
    sealed = value["configuration"]
    require(sealed["product_world_identity"] == current["product_world_identity"]
            and sealed["authority_categories"] == current["authority_categories"]
            and sealed["F011_registration"] == current["F011_registration"]
            and sealed["semantics"] == sealed_semantic_source_gate(),
            "Card-2 replacement product configuration drift")
    print("Block 2.6 Card 2 replacement: PREFLIGHT CHECK PASS")


def build() -> None:
    patch_card()
    CARD.build()
    value = load(RECEIPT)
    value["attempt_history"] = {"initial_red": bind(INITIAL_RED),
        "state_placement_price": bind(PRICE.RECEIPT),
        "initial": {"WPLTO_runs": 1, "product_link_attempts": 1,
            "completed_product_links": 0},
        "replacement": {"WPLTO_runs": 1, "product_link_attempts": 1,
            "completed_product_links": 1},
        "card_total": {"WPLTO_runs": 2, "product_link_attempts": 2,
            "completed_product_links": 1}}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    validate(value, require_prefilter=False)


def selftest() -> None:
    zero_page_population_selftest()
    patch_card()
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "text-floor-lost": lambda row: row["final_product"]["bounded_owners"][
            "ordinary_text"].update({"margin_bytes": 31}),
        "bss-floor-lost": lambda row: row["final_product"]["bounded_owners"][
            "ordinary_BSS"].update({"margin_bytes": 4}),
        "island-floor-lost": lambda row: row["final_product"]["bounded_owners"][
            "resident_island"].update({"margin_bytes": 4}),
        "zp-escaped": lambda row: row["final_product"]["bounded_owners"][
            "zero_page"].update({"within_bounds": False}),
        "noload-escaped": lambda row: row["final_product"]["bounded_owners"][
            "NOLOAD"].update({"margin_bytes": -1}),
        "stale-link-accepted": lambda row: row["final_product"]["semantics"][
            "link_model"].update({"stale_words_rejected": 0}),
        "nested-map": lambda row: row["final_product"]["nesting"].update(
            {"violations": [{"path": ["disk_source_refill_far", "map_enter"]}]}),
        "difference-remainder": lambda row: row["difference"].update(
            {"unexplained_members": 1}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial, require_prefilter=False)
        except (ReplacementError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "Card-2 replacement mutation survived")
    print(f"Block 2.6 Card 2 replacement: SELFTEST PASS mutations={len(rejected)}")


def check() -> None:
    patch_card()
    value = load(RECEIPT)
    validate(value)
    require(load(DIFFERENCE) == value["difference"] and REPORT.is_file(),
            "Card-2 replacement report/difference absent")
    print("Block 2.6 Card 2 replacement: CHECK PASS WPLTO=2 total link=1 complete")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "check-preflight", "build",
        "check", "selftest", "_source_preflight", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    patch_card()
    if action == "preflight":
        preflight()
    elif action == "check-preflight":
        check_preflight()
    elif action == "build":
        build()
    elif action == "check":
        check()
    elif action == "selftest":
        selftest()
    elif action == "_source_preflight":
        CARD.configure()
        source_preflight()
    else:
        CARD.child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplacementError, CARD.CardError, RuntimeError, KeyError, ValueError,
            OSError, subprocess.CalledProcessError) as error:
        print(f"Block 2.6 Card 2 replacement: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
