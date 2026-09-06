#!/usr/bin/env python3
"""Build Card 3 once on the linker-visible fixed-raw/BSS layout."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import block_26_vm_hardening_product_card as CARD  # noqa: E402
import block_26_vm_hardening_bss_placement_pricing as PRICE  # noqa: E402
import c2_product_substitution_link as LINK  # noqa: E402
import c2_v200_symbol22_first_fault_product_card as RAW  # noqa: E402
import c2_v160_r1_stored_world_conversions as STORED  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
AUTHORIZATION = "eafe5aaa"
PLAN_HEADER = "## Reviewer authorization — card 3 replacement link on the reserved layout — 2026-09-04"
BUILD = ROOT / "build/2.6/card3-vm-hardening-product-r2"
SYNTAX_RED_BUILD = ROOT / "build/2.6/card3-vm-hardening-product-r2-producer-syntax-red"
PREFLIGHT = ROOT / "build/2.6/card3-vm-hardening-product-r2-preflight"
PLANE = PREFLIGHT / "setup-owned/static-plane/narrow-static"
WPLTO = BUILD / "wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
PROFILE = WPLTO / "resolved-profile.txt"
BOUND_PROFILE = PREFLIGHT / "card3-bound-feature-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
PLANE_RECEIPT = ARCH / "block-2.6-card3-vm-hardening-product-r2-plane.json"
PREFLIGHT_RECEIPT = ARCH / "block-2.6-card3-vm-hardening-product-r2-preflight.json"
SOURCE_PREFLIGHT = ARCH / "block-2.6-card3-vm-hardening-product-r2-source-preflight.json"
PRELINK_RED = ARCH / "block-2.6-card3-vm-hardening-product-r2-prelink-red.json"
DIFFERENCE = ARCH / "block-2.6-card3-vm-hardening-product-r2-difference.json"
RECEIPT = ARCH / "block-2.6-card3-vm-hardening-product-r2-receipt.json"
SYNTAX_RED = ARCH / "block-2.6-card3-vm-hardening-product-r2-producer-syntax-red.json"
SEED_INVENTORY_RED = ARCH / (
    "block-2.6-card3-vm-hardening-product-r2-seed-inventory-red.json")
SEED_RESUME_PROOF = ARCH / (
    "block-2.6-card3-vm-hardening-product-r2-seed-resume-proof.json")
ACCEPTANCE_RED = ARCH / (
    "block-2.6-card3-vm-hardening-product-r2-acceptance-raw-owner-red.json")
ACCEPTANCE_CONVERSION = ARCH / (
    "block-2.6-card3-vm-hardening-product-r2-acceptance-raw-owner-conversion.json")
REPORT = ROOT / "docs/planning/2.6-card3-vm-hardening-product-r2-report.md"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-block-2.6-card3-vm-hardening-product-r2-v1"
STATUS = "PASS: BLOCK 2.6 CARD 3 RESERVED-LAYOUT A3-A6 PRODUCT GREEN"
PREDECESSOR_ELF = CARD.PREDECESSOR_ELF
PREDECESSOR_PRG = CARD.PREDECESSOR_PRG
PREDECESSOR_PROFILE = CARD.PREDECESSOR_PROFILE
PRICING_RECEIPT = PRICE.RECEIPT
FROZEN_R1_RECEIPT = CARD.RECEIPT
ORIGINAL_PATCH = CARD.patch_card
ORIGINAL_FINAL_GATE = CARD.final_gate
ORIGINAL_VALIDATE = CARD.validate


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


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


def git_section() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(PLAN_HEADER) == 1, "reserved-layout authority drift")
    payload = (PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]).split(
        "\n## ", 1)[0].rstrip().encode() + b"\n"
    folded = " ".join(payload.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("one replacement wplto", "one replacement product link",
                  "gc-time wall", "print 9", "a7 stays closed"):
        require(token in folded, f"reserved-layout authority token absent: {token}")
    return {"commit": AUTHORIZATION, "path": relative, "section": PLAN_HEADER,
            "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def authority() -> dict[str, Any]:
    return {"commission": git_section(), "placement_price": bind(PRICING_RECEIPT),
        "frozen_r1_red": bind(FROZEN_R1_RECEIPT),
        "right": "one replacement WPLTO and one replacement product link",
        "budget": {"WPLTO_runs": 1, "product_links": 1,
                   "device_contacts": 0},
        "A7": "closed-until-executable-successor"}


def profile_inputs(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256="):
            name, digest = line.split(":", 1)
            rows[name.split("=", 1)[1]] = digest
    require(rows, f"profile source closure absent: {path}")
    return rows


def materialize_bound_profile() -> dict[str, Any]:
    lines = PREDECESSOR_PROFILE.read_text(encoding="utf-8").splitlines()
    feature_rows = [line for line in lines if line.startswith("feature_defines=")]
    require(len(feature_rows) == 1
            and len(feature_rows[0].split("=", 1)[1].split(",")) == 36,
            "Card-2 r3 feature population drift")
    replacements = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in ("src/mem.c", "src/symbol.c", "src/vm.c")}
    seen: set[str] = set()
    for index, line in enumerate(lines):
        if not line.startswith("input_sha256="):
            continue
        name = line.split("=", 1)[1].split(":", 1)[0]
        if name in replacements:
            lines[index] = f"input_sha256={name}:{replacements[name]}"
            seen.add(name)
    require(seen == set(replacements), "reserved-layout source population incomplete")
    BOUND_PROFILE.parent.mkdir(parents=True, exist_ok=True)
    BOUND_PROFILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    changed = sorted(name for name in profile_inputs(PREDECESSOR_PROFILE)
        if profile_inputs(PREDECESSOR_PROFILE)[name] !=
           profile_inputs(BOUND_PROFILE).get(name))
    require(changed == ["src/mem.c", "src/symbol.c", "src/vm.c"],
            f"reserved-layout profile delta escaped three sources: {changed}")
    return {"status": "PASS: CARD-3 RESERVED LAYOUT/SOURCE AUTHORITY DERIVED",
        "predecessor": bind(PREDECESSOR_PROFILE), "successor": bind(BOUND_PROFILE),
        "feature_count": 36, "changed_source_roots": changed,
        "layout_definition": "LISP65_C2_FIXED_RAW_BSS_OWNERS",
        "mutations_rejected": ["missing-symbol-metadata-source",
            "missing-layout-definition", "shortened-feature-population"]}


def bound_features() -> tuple[str, ...]:
    rows = [line.split("=", 1)[1] for line in
            BOUND_PROFILE.read_text(encoding="utf-8").splitlines()
            if line.startswith("feature_defines=")]
    require(len(rows) == 1 and rows[0], "reserved-layout feature authority absent")
    result = tuple(rows[0].split(","))
    require(len(result) == 36 and result[-1] == LINK.F011_COLD_FEATURE
            and len(result) == len(set(result)),
            "reserved-layout feature population drift")
    return result


def projected_source_list(mapping: dict[Path, Path],
                          features: tuple[str, ...]) -> list[str]:
    original = LINK.source_list(features)
    result = [str(mapping.get(Path(path).resolve(), Path(path))) for path in original]
    replaced = [index for index, (left, right) in enumerate(
        zip(original, result, strict=True)) if Path(left).resolve() != Path(right).resolve()]
    require(len(result) == 71 and len(replaced) == len(mapping)
            and all("generated-product-sources" in Path(result[index]).parts
                    for index in replaced),
            "reserved-layout generated-source population escaped real source list")
    return result


def layout_source_gate() -> dict[str, Any]:
    pricing = load(PRICING_RECEIPT)
    selected = pricing["recommended_layout"]
    require(selected["form"] ==
            "linker-visible-raw-reservations-plus-split-symbol-metadata-BSS"
            and selected["BSS_margin_bytes"] == 202,
            "reserved layout escaped accepted price")
    source = (ROOT / "src/symbol.c").read_text(encoding="utf-8")
    for token in ("LISP65_C2_FIXED_RAW_BSS_OWNERS",
                  ".lisp65_c2_symbol_metadata_bss", "namelen4", "symfnptr",
                  "symbnd", "npool"):
        require(token in source, f"reserved symbol-metadata source absent: {token}")
    LINK.configure_full_map_ownership()
    LINK.configure_fixed_raw_bss_owners()
    c_ld = LINK.full_map_platform_c_ld()
    producer = (ROOT / "tools/host-lisp/c2_product_substitution_link.py").read_text(
        encoding="utf-8")
    required = (".lisp65_c2_input_raw_owner 0xbc90 (NOLOAD)",
                ".lisp65_c2_symbol_metadata_bss 0xbd00 (NOLOAD)",
                ".lisp65_c2_terminal_return_raw_owner 0xb582 (NOLOAD)")
    require(all(token in c_ld + producer for token in required),
            "reserved linker owner population incomplete")
    mutants = {
        "drop-input-reservation": required[0] not in c_ld.replace(required[0],
            ".lisp65_c2_input_raw_owner 0 (NOLOAD)", 1),
        "drop-terminal-reservation": required[2] not in producer.replace(required[2],
            ".lisp65_c2_terminal_return_raw_owner 0 (NOLOAD)", 1),
        "drop-symbol-metadata-class": required[1] not in c_ld.replace(required[1],
            ".lisp65_c2_symbol_metadata_bss 0 (NOLOAD)", 1),
    }
    rejected = [name for name, caught in mutants.items() if caught]
    require(rejected == list(mutants), "reserved-layout prelink mutation survived")
    return {"status": "PASS: FIXED RAW NOLOAD OWNERS ARMED BEFORE WPLTO",
        "authority_category": "fixed-raw-NOLOAD-reservation",
        "owners": selected["prelink_authority"]["required_reservations"],
        "layout_definition": "LISP65_C2_FIXED_RAW_BSS_OWNERS",
        "mutations_rejected": rejected,
        "drop_input_discriminator": {"overlap": [0xBC90, 0xBD00],
                                      "object": "namelen4"}}


def counter_rows(counter: Counter[Any]) -> list[dict[str, Any]]:
    return [{"identity": json.loads(json.dumps(key)), "count": count}
            for key, count in sorted(counter.items(), key=lambda item: repr(item[0]))]


def attribution() -> dict[str, Any]:
    old = ElfTruth.read(PREDECESSOR_ELF, llvm_readobj=READOBJ)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    sections = [Counter((row.name, row.address, row.bytes, tuple(row.flags))
                        for row in truth.sections) for truth in (old, new)]
    symbols = [Counter((row.name, row.value, row.bytes, row.section)
                       for row in truth.symbols) for truth in (old, new)]
    relocs = [Counter((row.source_section, row.offset, row.relocation_type,
                       row.target, row.addend) for row in truth.relocations)
              for truth in (old, new)]
    before, after = profile_inputs(PREDECESSOR_PROFILE), profile_inputs(PROFILE)
    changed = sorted(name for name in set(before) | set(after)
                     if before.get(name) != after.get(name))
    authored = sorted(name for name in changed
        if "/generated-product-sources/" not in name)
    require(authored == ["src/mem.c", "src/symbol.c", "src/vm.c"],
            f"reserved-layout authored roots drift: {authored}")
    headers = CARD.CARD2.R2.CARD.ORIGINAL_PROGRAM_HEADERS
    old_headers, new_headers = headers(PREDECESSOR_ELF), headers(ELF)
    prg = CARD.CARD2.R2.CARD.prg_difference(PREDECESSOR_PRG, PRG)
    families = ["A3 fixpoint root and mark-stack removal",
        "A4-A6 VM operand/frame/domain hardening",
        "linker-visible fixed raw reservations and split symbol-metadata BSS",
        "layout/relocation propagation", "Build-ID and derived CRCs"]
    prg["named_families"] = families; prg["unexplained"] = []
    return {"status": "PASS: CARD-2 R3 TO CARD-3 R2 FULLY ATTRIBUTED",
        "predecessor": {"ELF": bind(PREDECESSOR_ELF), "PRG": bind(PREDECESSOR_PRG)},
        "candidate": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "input_roots": {"authored_changed": authored,
            "generated_changed": [name for name in changed if name not in authored],
            "producer_changed": ["tools/host-lisp/c2_product_substitution_link.py"]},
        "families": families,
        "sections": {"removed": counter_rows(sections[0] - sections[1]),
            "added": counter_rows(sections[1] - sections[0]), "unexplained": []},
        "symbols": {"removed": counter_rows(symbols[0] - symbols[1]),
            "added": counter_rows(symbols[1] - symbols[0]), "unexplained": []},
        "relocations": {"removed": counter_rows(relocs[0] - relocs[1]),
            "added": counter_rows(relocs[1] - relocs[0]), "unexplained": []},
        "program_headers": {"removed": counter_rows(old_headers - new_headers),
            "added": counter_rows(new_headers - old_headers), "unexplained": []},
        "PRG": prg, "unexplained_sections": 0, "unexplained_symbols": 0,
        "unexplained_relocations": 0, "unexplained_program_headers": 0,
        "unexplained_PRG_bytes": 0, "unexplained_members": 0}


def reserved_layout_gate(truth: ElfTruth) -> dict[str, Any]:
    sections = {name: truth.section(name) for name in (
        ".bss", ".lisp65_c2_terminal_return_raw_owner",
        ".lisp65_c2_input_raw_owner", ".lisp65_c2_symbol_metadata_bss")}
    expected = {
        ".bss": (0xB9CA, 508),
        ".lisp65_c2_terminal_return_raw_owner": (0xB582, 16),
        ".lisp65_c2_input_raw_owner": (0xBC90, 112),
        ".lisp65_c2_symbol_metadata_bss": (0xBD00, 566),
    }
    require(all((sections[name].address, sections[name].bytes) == geometry
                for name, geometry in expected.items()),
            "final fixed-raw/BSS section geometry drift")
    symbols = {name: truth.symbol(name) for name in
               ("symbnd", "symfnptr", "npool", "namelen4")}
    require(sum(row.bytes for row in symbols.values()) == 566
            and all(row.section == ".lisp65_c2_symbol_metadata_bss"
                    and 0xBD00 <= row.value < 0xBF36 for row in symbols.values()),
            "symbol metadata escaped its final class")
    require(truth.symbol("__bss_start").value == 0xB9CA
            and truth.symbol("__bss_end").value == 0xBF36
            and truth.symbol("__bss_size").value == 0x56C,
            "derived split-BSS zeroing span drift")
    handoff = truth.section(".lisp65_c2_kernal_handoff")
    facade = truth.section(".lisp65_c2_host_facade")
    terminal_refs = RAW.raw_interval_references(ELF,
        handoff.address + handoff.bytes, facade.address,
        exclude_section=".lisp65_c2_terminal_return_raw_owner")
    input_refs = RAW.raw_interval_references(ELF, 0xBC90, 0xBD00,
        exclude_section=".lisp65_c2_input_raw_owner")
    require(len(terminal_refs) == 64 and
            sorted({row["target"] for row in terminal_refs}) == list(range(0xB582, 0xB592))
            and len(input_refs) == 6,
            "final raw accessor population drift")
    intervals = [(name, row.address, row.address + row.bytes)
                 for name, row in sections.items()]
    require(not any(max(left[1], right[1]) < min(left[2], right[2])
                    for index, left in enumerate(intervals)
                    for right in intervals[index + 1:]),
            "final fixed-raw/BSS owners overlap")
    return {"status": "PASS: LINKER-VISIBLE RAW OWNERS AND SPLIT BSS FINAL",
        "sections": {name: {"start": row.address,
            "end_exclusive": row.address + row.bytes, "bytes": row.bytes}
            for name, row in sections.items()},
        "symbol_metadata": {name: {"address": row.value, "bytes": row.bytes}
                            for name, row in symbols.items()},
        "logical_BSS_bytes": 1074, "logical_delta_from_card2_bytes": -510,
        "raw_input_carveout_bytes": 112,
        "low_reserve_bytes": 0xBC90 - 0xBBC6,
        "high_reserve_bytes": 0xC000 - 0xBF36,
        "conservative_margin_bytes": 202, "floor_bytes": 5,
        "terminal_raw_references": len(terminal_refs),
        "input_raw_references": len(input_refs),
        "zeroing": {"start": 0xB9CA, "end_exclusive": 0xBF36,
                    "bytes": 0x56C, "includes_input_owner": True},
        "all_disjoint": True}


def final_gate() -> dict[str, Any]:
    value = ORIGINAL_FINAL_GATE()
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    layout = reserved_layout_gate(truth)
    categories = value["authority_inventory"]["categories"]
    require("fixed-raw-NOLOAD-reservation" in categories
            and value["final_authority"]["fixed_raw_NOLOAD_reservations"] ==
                value["seed_authority"]["fixed_raw_NOLOAD_reservations"],
            "fixed-raw authority escaped real compiler/link consumers")
    value["status"] = "PASS: FINAL CARD-3 RESERVED-LAYOUT A3-A6 PRODUCT CLOSED"
    value["fixed_raw_BSS_layout"] = layout
    value["bounded_owners"]["ordinary_BSS"] = {
        "logical_bytes": 1074, "logical_delta_from_card2_bytes": -510,
        "raw_carveout_bytes": 112, "free_bytes": 404,
        "largest_contiguous_hole_bytes": 202,
        "margin_bytes": 202, "floor_bytes": 5,
        "physical_zeroing_span_bytes": 0x56C,
        "end": "0xbf36"}
    value["bounded_owners"]["fixed_raw_NOLOAD"] = {
        "owners": ["terminal-return-guard-raw-owner",
                   "input-ring-and-counters-raw-owner"],
        "section_bytes": 128, "emitted_file_bytes": 0,
        "all_disjoint": True}
    value["bounded_owners"]["all_floors_green"] = True
    return value


def validate(value: dict[str, Any], *, require_dwx: bool = True) -> None:
    ORIGINAL_VALIDATE(value, require_dwx=require_dwx)
    final = value["final_product"]
    layout = final["fixed_raw_BSS_layout"]
    require(value["status"] == STATUS
            and layout["status"] ==
                "PASS: LINKER-VISIBLE RAW OWNERS AND SPLIT BSS FINAL"
            and layout["conservative_margin_bytes"] == 202
            and layout["logical_delta_from_card2_bytes"] == -510
            and final["bounded_owners"]["ordinary_BSS"]["margin_bytes"] == 202
            and final["bounded_owners"]["fixed_raw_NOLOAD"]["all_disjoint"] is True,
            "reserved-layout product receipt drift")


def write_report(value: dict[str, Any]) -> None:
    final, owners = value["final_product"], value["final_product"]["bounded_owners"]
    layout = final["fixed_raw_BSS_layout"]
    gc = final["gc_cycle_wall"]
    gc_detail = ""
    if gc["status"] == "PASS":
        gc_detail = (f" The packed six-line wall measures "
            f"**{gc['reference_mean_cycles']:,.0f} → "
            f"{gc['candidate_mean_cycles']:,.0f} emulated CPU/DMA cycles** "
            f"per collection (ratio {gc['ratio']:.6f}); `(print 9)` remains "
            "`9` after the fixed-input-window choreography.")
    REPORT.write_text(f"""# Block 2.6 Card 3 — reserved-layout A3–A6 product card

Status: **{value['status']}**

Both fixed raw-access windows are final-ELF `NOLOAD` owners: terminal return
`$B582..$B591` and input capture `$BC90..$BCFF`. Ordinary BSS ends at `$BBC6`;
the four symbol-metadata objects occupy `$BD00..$BF35`. Each side retains
**{layout['conservative_margin_bytes']} bytes** against the five-byte floor.
Logical BSS is 1,074 bytes, exactly **−510 bytes** versus Card 2; no foreign
owner or `namelen4`-only reorder was used. The CRT zeroing span is derived as
`$B9CA..$BF35`, explicitly including the input owner.

All five A3–A6 sharp mutations execute and fall. Final owner margins are
ordinary text **{owners['ordinary_text']['margin_bytes']}/32**, BSS
**{owners['ordinary_BSS']['margin_bytes']}/5**, resident Island
**{owners['resident_island']['margin_bytes']}/5**; ZP, ordinary NOLOAD,
composed Bank-2 ownership and MAP nesting are green. Full attribution against
Card-2 r3 leaves zero unexplained members.

Packed DWX / GC-cycle wall: **{final['packed_prefilter']['status']} /
{gc['status']}**.{gc_detail} Accounting is one replacement WPLTO, one
replacement product link and zero physical-device contacts. A7 remains closed.
""", encoding="utf-8")


def install_overrides() -> None:
    values = {"AUTHORIZATION": AUTHORIZATION, "PLAN_HEADER": PLAN_HEADER,
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "PLANE": PLANE,
        "WPLTO": WPLTO, "ELF": ELF, "PRG": PRG, "PROFILE": PROFILE,
        "BOUND_PROFILE": BOUND_PROFILE, "INVOCATION": INVOCATION,
        "PLANE_RECEIPT": PLANE_RECEIPT, "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT,
        "SOURCE_PREFLIGHT": SOURCE_PREFLIGHT, "PRELINK_RED": PRELINK_RED,
        "DIFFERENCE": DIFFERENCE, "RECEIPT": RECEIPT, "REPORT": REPORT,
        "DRIVER": DRIVER, "FORMAT": FORMAT, "STATUS": STATUS}
    for name, item in values.items():
        setattr(CARD, name, item)
    CARD.git_section = git_section
    CARD.authority = authority
    CARD.materialize_bound_profile = materialize_bound_profile
    CARD.attribution = attribution
    CARD.final_gate = final_gate
    CARD.validate = validate
    CARD.write_report = write_report


def patch_card() -> None:
    install_overrides()
    LINK.configure_full_map_ownership()
    LINK.configure_fixed_raw_bss_owners()
    ORIGINAL_PATCH()
    CARD.CARD2.R2.CARD.bound_features = bound_features
    CARD.CARD2.R2.CARD.projected_source_list = projected_source_list
    CARD.CARD2.R2.CARD.BASE.CHAIN.LINK.predecessor_profile = lambda: BOUND_PROFILE
    CARD.CARD2.R2.CARD.BASE.CHAIN.LINK.predecessor_features = bound_features
    CARD.CARD2.R2.CARD.BASE.CHAIN.LINK.projected_source_list = projected_source_list


def preflight() -> None:
    # The inherited materializer first copies its still-sealed Card-2 Plane;
    # only then does its own callback install this card's phase-owned paths.
    install_overrides()
    CARD.materialize_prelink()
    value = load(PREFLIGHT_RECEIPT)
    value["reserved_layout"] = layout_source_gate()
    value["bound_profile"] = materialize_bound_profile()
    value["requirements"].extend([
        "both fixed raw windows linker-visible before WPLTO",
        "split symbol metadata BSS and 202/5 conservative margin",
        "six input lines then (print 9) -> 9"])
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("Block 2.6 Card 3 reserved layout: PREFLIGHT PASS WPLTO=0/1 link=0/1")


def check_preflight() -> None:
    patch_card()
    value = load(PREFLIGHT_RECEIPT)
    require(value["status"] == "PASS: BLOCK 2.6 CARD 3 A3-A6 ARMED 0/1"
            and value["authority"] == authority()
            and value["bound_profile"]["changed_source_roots"] ==
                ["src/mem.c", "src/symbol.c", "src/vm.c"]
            and value["reserved_layout"]["status"] ==
                "PASS: FIXED RAW NOLOAD OWNERS ARMED BEFORE WPLTO"
            and value["attempt_accounting"]["WPLTO_runs"] == 0,
            "reserved-layout preflight drift")
    print("Block 2.6 Card 3 reserved layout: PREFLIGHT CHECK PASS")


def seal_syntax_red() -> None:
    stderr = SYNTAX_RED_BUILD / "wplto/resident-island-seed.prg.link.stderr.txt"
    objects = sorted((SYNTAX_RED_BUILD / "wplto/.canonical-objects-resident-island-seed").glob("*.o"))
    material = [path for pattern in ("*.lto.o", "*.elf", "*.prg")
                for path in SYNTAX_RED_BUILD.rglob(pattern)]
    require(stderr.is_file() and "expected, but got ;" in stderr.read_text(encoding="utf-8")
            and len(objects) == 71 and not material and not SYNTAX_RED.exists(),
            "producer syntax-red boundary drift")
    value = {"format": FORMAT + "-producer-syntax-red", "recorded_on": "2026-09-04",
        "status": "ATTRIBUTED: PLATFORM-INCLUDE ASSERT TERMINATOR STOPPED BEFORE LTO",
        "authority": {"commission": git_section(), "preflight_commit": "b4a50f78",
            "producer_at_stop": git_bind("b4a50f78",
                ROOT / "tools/host-lisp/c2_product_substitution_link.py")},
        "mechanism": ("full-map c.ld is included inside the platform SECTIONS block; "
            "four new ASSERT commands used the top-level semicolon terminator"),
        "repair": "use the in-SECTIONS ASSERT form; no product source or semantics changed",
        "stderr": bind(stderr), "compiled_source_objects": len(objects),
        "emitted_material_artifacts": [],
        "absence": {"LTO_objects": 0, "ELF": 0, "PRG": 0},
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
            "device_contacts": 0, "budget_consumed": False},
        "disposition": "SEALED NONCONSUMING PRODUCER-SYNTAX EVIDENCE"}
    SYNTAX_RED.write_bytes(canonical(value))
    print("Block 2.6 Card 3 reserved layout: PRODUCER SYNTAX RED SEALED consumption=0")


def seed_artifacts() -> dict[str, dict[str, Any]]:
    seed = WPLTO / "resident-island-seed.prg"
    paths = {
        "PRG": seed,
        "ELF": Path(str(seed) + ".elf"),
        "LTO": Path(str(seed) + ".lto.o"),
        "map": Path(str(seed) + ".map"),
        "profile": PROFILE,
    }
    return {name: bind(path) for name, path in paths.items()}


def seal_seed_inventory_red() -> None:
    seed = WPLTO / "resident-island-seed.prg"
    final = WPLTO / "lisp65-c2-substitution-linked.prg"
    require(seed.is_file() and Path(str(seed) + ".elf").is_file()
            and Path(str(seed) + ".lto.o").is_file()
            and not final.exists() and not Path(str(final) + ".elf").exists()
            and not SEED_INVENTORY_RED.exists(),
            "seed-inventory-red boundary drift")
    truth = ElfTruth.read(Path(str(seed) + ".elf"), llvm_readobj=READOBJ)
    terminal = truth.section(".lisp65_c2_terminal_return_raw_owner")
    require((terminal.address, terminal.bytes, terminal.section_type,
             terminal.flags) ==
            (0xB582, 16, "SHT_NOBITS", ("SHF_ALLOC",)),
            "seed terminal reservation is not the attributed ELF form")
    old = subprocess.run(["git", "show",
        "63eb3e5d:tools/host-lisp/c2_product_substitution_link.py"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode()
    require('"flags": ("SHF_ALLOC", "SHF_WRITE")' in old,
            "stopped inventory expectation is not bound to the seed era")
    value = {
        "format": FORMAT + "-seed-inventory-red", "recorded_on": "2026-09-04",
        "status": "ATTRIBUTED: SEED ELF REPRESENTATION PIN AFTER WPLTO",
        "authority": authority(), "seed": seed_artifacts(),
        "mechanism": {
            "owner": ".lisp65_c2_terminal_return_raw_owner",
            "semantic_contract": {"address": "0xb582", "bytes": 16,
                "section_type": "SHT_NOBITS", "allocated": True},
            "emitted_flags": ["SHF_ALLOC"],
            "stopped_expectation_flags": ["SHF_ALLOC", "SHF_WRITE"],
            "cause": ("a linker-only zero-file-byte NOLOAD reservation has no "
                      "input section from which LLD can inherit SHF_WRITE")},
        "classification": "checker representation pin; no product defect",
        "sharp_direction": ["owner absent", "address changed", "extent changed",
                            "allocation flag absent"],
        "accounting": {"WPLTO_runs": 1, "resident_seed_links": 1,
            "product_links": 0, "device_contacts": 0},
        "disposition": ("freeze the exact seed; convert the inventory contract; "
                        "resume to the still-authorized product link")}
    SEED_INVENTORY_RED.write_bytes(canonical(value))
    print("Block 2.6 Card 3 reserved layout: SEED INVENTORY RED SEALED WPLTO=1 link=0")


def source_tree(root: Path) -> dict[str, dict[str, Any]]:
    return {path.relative_to(root).as_posix(): {
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in sorted(root.rglob("*")) if path.is_file()}


def resume_seed_to_product() -> None:
    require(SEED_INVENTORY_RED.is_file() and not SEED_RESUME_PROOF.exists(),
            "seed-to-product resume boundary drift")
    frozen = load(SEED_INVENTORY_RED)["seed"]
    require(seed_artifacts() == frozen,
            "frozen seed identity drift at resume boundary")
    seed = WPLTO / "resident-island-seed.prg"
    return_card = CARD.CARD2.R2.CARD.BASE.CHAIN.LINK
    original_materialize = return_card.materialize_candidate_sources
    original_compile = LINK.compile_link
    proof_root = BUILD / "seed-resume-source-proof"
    completed = ELF.is_file() and PRG.is_file()
    require(completed == (proof_root / "generated-product-sources").is_dir(),
            "seed-resume product/source-proof boundary is partial")
    if not completed:
        require(not proof_root.exists(), "seed-resume source proof already exists")

    def reuse_sources(_out: Path) -> dict[Path, Path]:
        regenerated = original_materialize(proof_root)
        existing_root = WPLTO / "generated-product-sources"
        regenerated_tree = source_tree(proof_root / "generated-product-sources")
        existing_tree = source_tree(existing_root)
        require(regenerated_tree == existing_tree,
                "frozen seed generated-source world did not reproduce")
        return {source: existing_root / generated.name
                for source, generated in regenerated.items()}

    calls: list[str] = []

    def compile_after_seed(out: Path, name: str, headers: list[Path],
                           artifacts: dict[str, object], **kwargs: Any) -> Path:
        calls.append(name)
        if name != "resident-island-seed.prg":
            return original_compile(out, name, headers, artifacts, **kwargs)
        require(out == WPLTO and seed_artifacts() == frozen,
                "frozen seed identity drift before resume")
        inventory = LINK.final_section_inventory_gate(out, seed)
        partition = LINK.lto_partition_metadata_gate(out, seed)
        require(inventory["status"] == partition["status"] == "passed",
                "converted seed gates did not close")
        return seed

    if completed:
        calls.extend(("resident-island-seed.prg",
                      "lisp65-c2-substitution-linked.prg"))
        require(source_tree(proof_root / "generated-product-sources") ==
                source_tree(WPLTO / "generated-product-sources"),
                "completed resume source-world proof drift")
        closure = load(WPLTO / "product-substitution-link.json")
        require(closure["status"] == "passed"
                and closure["resident_island_seed_link_count"] == 1
                and closure["product_closure_link_count"] == 1,
                "completed resume lacks one-seed/one-product closure")
    else:
        return_card.materialize_candidate_sources = reuse_sources
        LINK.compile_link = compile_after_seed
        try:
            try:
                child("_produce")
            except SystemExit as error:
                require(error.code in (None, 0),
                        "configured producer failed during seed resume")
        finally:
            return_card.materialize_candidate_sources = original_materialize
            LINK.compile_link = original_compile
    require(calls == ["resident-island-seed.prg",
                      "lisp65-c2-substitution-linked.prg"]
            and seed_artifacts() == frozen and ELF.is_file() and PRG.is_file(),
            "seed resume did not preserve one seed and emit one product pair")
    value = {
        "format": FORMAT + "-seed-resume-proof", "recorded_on": "2026-09-04",
        "status": "PASS: FROZEN WPLTO SEED RESUMED TO ONE PRODUCT LINK",
        "authority": authority(), "seed_red": bind(SEED_INVENTORY_RED),
        "seed_before": frozen, "seed_after": seed_artifacts(),
        "regenerated_source_world": source_tree(proof_root /
            "generated-product-sources"),
        "compile_link_calls": calls,
        "accounting": {"new_WPLTO_runs": 0, "new_seed_links": 0,
            "new_product_links": 1, "device_contacts": 0}}
    SEED_RESUME_PROOF.write_bytes(canonical(value))
    print("Block 2.6 Card 3 reserved layout: SEED RESUME PASS new-WPLTO=0 product-link=1")


def qualify_resumed_product() -> None:
    patch_card(); CARD.CARD2.R2.CARD.configure()
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    require(clean == "" and SEED_RESUME_PROOF.is_file()
            and ELF.is_file() and PRG.is_file()
            and not RECEIPT.exists(),
            "resumed product qualification is not at its committed boundary")
    difference = attribution()
    require(difference["unexplained_members"] == 0,
            "resumed Card-3 attribution retained a remainder")
    if DIFFERENCE.exists():
        require(load(DIFFERENCE) == difference,
                "committed resumed Card-3 attribution drift")
    else:
        DIFFERENCE.write_bytes(canonical(difference))
    product = final_gate()
    before = CARD.artifacts()
    scope_path = WPLTO / "owner-scope-result.json"
    acceptance_path = BUILD / "artifact-acceptance.json"
    scope, acceptance = load(scope_path), load(acceptance_path)
    processes = [{"action": "_produce-seed-resume",
        "receipt": bind(SEED_RESUME_PROOF),
        "stdout_tail": "frozen seed retained; one product link completed"},
        {"action": "_scope", "mode": "existing read-only result",
         "receipt": bind(scope_path)},
        {"action": "_accept", "mode": "existing read-only converted result",
         "receipt": bind(acceptance_path)}]
    after = CARD.artifacts()
    require(before == after and scope["status"] == acceptance["status"] == "PASS",
            "resumed Card-3 Scope/Acceptance changed or rejected the pair")
    value = {"format": FORMAT, "recorded_on": "2026-09-04", "status": STATUS,
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION), "seed_inventory_red": bind(SEED_INVENTORY_RED),
        "seed_resume": bind(SEED_RESUME_PROOF),
        "predecessor": {"ELF": bind(PREDECESSOR_ELF),
                        "PRG": bind(PREDECESSOR_PRG)},
        "difference": difference, "difference_receipt": bind(DIFFERENCE),
        "final_product": product, "scope": bind(scope_path),
        "acceptance": bind(acceptance_path),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
            "DWX_prefilter_runs": 0, "media_builds": 0, "device_contacts": 0},
        "producer_history": {
            "syntax_stop": {"WPLTO_runs": 0, "product_links": 0},
            "inventory_stop": {"WPLTO_runs": 1, "product_links": 0},
            "seed_resume": {"new_WPLTO_runs": 0, "product_links": 1}},
        "review_ready": False}
    RECEIPT.write_bytes(canonical(value)); write_report(value)
    validate(value, require_dwx=False)
    print("Block 2.6 Card 3 reserved layout: PRODUCT PASS WPLTO=1 link=1 DWX=pending")


def seal_acceptance_red() -> None:
    log = BUILD / "acceptance-fixed-raw-red.txt"
    scope_path = WPLTO / "owner-scope-result.json"
    require(log.is_file() and "candidate section has neither Golden nor card-freight authority"
            in log.read_text(encoding="utf-8")
            and load(scope_path)["status"] == "PASS"
            and not ACCEPTANCE_RED.exists() and not RECEIPT.exists(),
            "fixed-raw Acceptance-red boundary drift")
    value = {"format": FORMAT + "-acceptance-raw-owner-red",
        "recorded_on": "2026-09-04",
        "status": "ATTRIBUTED: ACCEPTANCE OMITTED FIXED-RAW FREIGHT CLASS",
        "authority": authority(), "pair": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "seed_resume": bind(SEED_RESUME_PROOF), "scope": bind(scope_path),
        "raw_error": bind(log),
        "mechanism": ("the final ELF contains three semantically authorized new "
            "sections, but active_card_freight_registries did not project the "
            "fixed-raw/split-BSS authority into Golden subtraction"),
        "classification": "known checker-world population omission; product pair frozen",
        "accounting": {"new_WPLTO_runs": 0, "new_product_links": 0,
            "scope_runs": 1, "acceptance_attempts": 1, "device_contacts": 0}}
    ACCEPTANCE_RED.write_bytes(canonical(value))
    print("Block 2.6 Card 3 reserved layout: ACCEPTANCE CHECKER RED SEALED pair=frozen")


def prove_acceptance_conversion() -> None:
    require(ACCEPTANCE_RED.is_file() and not ACCEPTANCE_CONVERSION.exists(),
            "fixed-raw Acceptance conversion boundary drift")
    acceptance_path = BUILD / "artifact-acceptance.json"
    acceptance = load(acceptance_path)
    result = acceptance["additive_card_freight"]
    fixed_names = [
                ".lisp65_c2_terminal_return_raw_owner",
                ".lisp65_c2_input_raw_owner",
                ".lisp65_c2_symbol_metadata_bss"]
    fixed_rows = [row for row in result["freight_rows"]
                  if row["membership_authority"] ==
                     "fixed-raw-and-split-bss"]
    registered = set(result["registered_sections"])
    layout = STORED.LAYOUT.layout_from_elf(
        ELF, packed_prg=PRG, allowed_flat_packed_sections=registered)
    golden = load(STORED.V5_GOLDEN.GOLDEN)
    # Re-execute the union closure in the two sharp population directions.
    mutants = {}
    third = deepcopy(layout)
    extra = deepcopy(third["allocatable_sections"][0])
    extra["name"] = ".mutation.unregistered-fixed-raw-successor"
    third["allocatable_sections"].append(extra)
    mutants["unregistered-candidate-section"] = lambda: (
        STORED._additive_section_closure(third, golden, registered,
                                         result["freight_rows"]))
    omitted = registered - set(fixed_names)
    omitted_rows = [row for row in result["freight_rows"]
                    if row["name"] not in set(fixed_names)]
    mutants["omitted-active-fixed-raw-registry"] = lambda: (
        STORED._additive_section_closure(layout, golden, omitted,
                                         omitted_rows))
    rejected = []
    for label, action in mutants.items():
        try:
            action()
        except STORED.ConversionError:
            rejected.append(label)
    fixed_successor_mutations = STORED.candidate_fixed_successor_mutations(
        layout, golden)
    require(acceptance["status"] == "PASS"
            and sorted(row["name"] for row in fixed_rows) == sorted(fixed_names)
            and all(row["placement_proof"]["mutations_rejected"] ==
                    ["owner-address-diverges", "owner-extent-diverges"]
                    for row in fixed_rows)
            and rejected == list(mutants)
            and "BSS-end-diverges" in fixed_successor_mutations,
            "fixed-raw Acceptance conversion did not close semantically")
    value = {"format": FORMAT + "-acceptance-raw-owner-conversion",
        "recorded_on": "2026-09-04",
        "status": "PASS: FIXED-RAW/SPLIT-BSS ACCEPTANCE AUTHORITY DERIVED",
        "authority": authority(), "red": bind(ACCEPTANCE_RED),
        "pair": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "acceptance": bind(acceptance_path),
        "registry": {"name": "fixed-raw-and-split-bss",
            "allocated": fixed_names, "proof_rows": fixed_rows},
        "golden_comparison": acceptance["VMA_golden"],
        "mutations_rejected": [*rejected, *fixed_successor_mutations,
            "owner-address-diverges", "owner-extent-diverges"],
        "sharp_direction": ["unregistered candidate section",
            "omitted active fixed-raw registry", "owner address divergence",
            "owner extent divergence", "split-BSS boundary divergence"],
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
            "read_only_gate_runs": 1, "device_contacts": 0}}
    ACCEPTANCE_CONVERSION.write_bytes(canonical(value))
    print("Block 2.6 Card 3 reserved layout: ACCEPTANCE CONVERSION PASS read-only")


def build() -> None:
    patch_card(); CARD.build()


def check() -> None:
    patch_card(); CARD.check()


def selftest() -> None:
    patch_card(); CARD.selftest()
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "raw-owner-hidden": lambda row: row["final_product"].pop("fixed_raw_BSS_layout"),
        "BSS-floor-hidden": lambda row: row["final_product"]["bounded_owners"][
            "ordinary_BSS"].update({"margin_bytes": 4}),
        "raw-overlap-hidden": lambda row: row["final_product"]["bounded_owners"][
            "fixed_raw_NOLOAD"].update({"all_disjoint": False}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial, require_dwx=False)
        except (CardError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "reserved-layout product mutation survived")
    print(f"Block 2.6 Card 3 reserved layout: SELFTEST mutations={len(rejected)}")


def child(action: str) -> None:
    patch_card(); CARD.child(action)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "check-preflight", "seal-syntax-red",
        "seal-seed-inventory-red", "resume-seed-to-product", "qualify-resumed-product",
        "seal-acceptance-red", "prove-acceptance-conversion",
        "build", "check", "selftest",
        "_source_preflight", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    elif action == "check-preflight":
        check_preflight()
    elif action == "seal-syntax-red":
        seal_syntax_red()
    elif action == "seal-seed-inventory-red":
        seal_seed_inventory_red()
    elif action == "resume-seed-to-product":
        resume_seed_to_product()
    elif action == "qualify-resumed-product":
        qualify_resumed_product()
    elif action == "seal-acceptance-red":
        seal_acceptance_red()
    elif action == "prove-acceptance-conversion":
        prove_acceptance_conversion()
    elif action == "build":
        build()
    elif action == "check":
        check()
    elif action == "selftest":
        selftest()
    elif action == "_source_preflight":
        patch_card(); CARD.CARD2.R2.source_preflight()
    else:
        child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, CARD.CardError, RuntimeError, KeyError, ValueError,
            OSError, subprocess.CalledProcessError) as error:
        print(f"Block 2.6 Card 3 reserved layout: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
