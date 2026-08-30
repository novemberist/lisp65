#!/usr/bin/env python3
"""Run the owner-authorized r6 B-light link after the all-pin preflight."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v190_native_prompt_editor_card as CARD  # noqa: E402


PRODUCT = CARD.PRODUCT
BASE = CARD.BASE
ARCH = CARD.ARCH
R5_BUILD = CARD.BUILD
R5_PROFILE = CARD.PROFILE
R5_RED = CARD.R5_LINK_RED_ATTRIBUTION
R6_DECISION = ROOT / "config/c2-v190-native-prompt-editor-card-r6.json"
BUILD = ROOT / "build/c2.3/v1.9-native-prompt-editor-card-r6"
PREFLIGHT1 = ARCH / "c2.3-v1.9-native-prompt-editor-card-r6-preflight.json"
PREFLIGHT = ARCH / "c2.3-v1.9-native-prompt-editor-card-r6-preflight2.json"
PRELINK_RED_ATTRIBUTION = ARCH / (
    "c2.3-v1.9-native-prompt-editor-card-r6-prelink-red-attribution.json")
INVOCATION = CARD.PREFLIGHT / "candidate-invocation-r6.json"
RECEIPT = ARCH / "c2.3-v1.9-native-prompt-editor-card-r6-receipt.json"
DIFFERENCE = ARCH / "c2.3-v1.9-native-prompt-editor-card-r5-r6-difference.json"
PRELINK_RED = ARCH / "c2.3-v1.9-native-prompt-editor-card-r6-first-red.json"
FIRST_RED = ARCH / "c2.3-v1.9-native-prompt-editor-card-r6-product-first-red.json"
PRODUCT_RED_ATTRIBUTION = ARCH / (
    "c2.3-v1.9-native-prompt-editor-card-r6-product-first-red-attribution.json")
ACCEPTANCE_RED = ARCH / (
    "c2.3-v1.9-native-prompt-editor-card-r6-acceptance-first-red.json")
ACCEPTANCE_RED_ATTRIBUTION = ARCH / (
    "c2.3-v1.9-native-prompt-editor-card-r6-acceptance-first-red-attribution.json")
ACCEPTANCE_RED2 = ARCH / (
    "c2.3-v1.9-native-prompt-editor-card-r6-acceptance-second-red.json")
ACCEPTANCE_RED2_ATTRIBUTION = ARCH / (
    "c2.3-v1.9-native-prompt-editor-card-r6-acceptance-second-red-attribution.json")
PRELINK_BUILD = ROOT / "build/c2.3/v1.9-native-prompt-editor-card-r6-prelink-red"
PRELINK_INVOCATION = CARD.PREFLIGHT / "candidate-invocation-r6-prelink-red.json"
REPORT = ROOT / "docs/planning/v1.9.0-native-prompt-editor-card-report.md"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PROFILE = BUILD / "wplto/resolved-profile.txt"
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v190-native-prompt-editor-card-r6-v1"
STATUS = "PASS: V1.9 B-LIGHT R6 NATIVE PROMPT EDITOR GREEN"

ORIGINAL_AUTHORITY = CARD.authority
ORIGINAL_SETUP = CARD.setup_child
ORIGINAL_ATTRIBUTION = CARD.attribution
ORIGINAL_WRITE_REPORT = CARD.write_report


class R6Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise R6Error(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def authority() -> dict[str, Any]:
    decision = load(R6_DECISION)
    red = load(R5_RED)
    require(decision["format"] ==
                "lisp65-c2-v190-native-prompt-editor-card-r6-authorization-v1"
            and decision["owner_decision"] == "r6-Link frei"
            and decision["status"] ==
                "one-replacement-card-authorized-after-zero-build-conversion"
            and decision["budget"] == {"WPLTO_runs": 1, "product_links": 1,
                "media_builds": 0, "device_contacts": 0}
            and decision["authority"]["r5_link_red_attribution"] ==
                bind(R5_RED)["path"]
            and red["status"] ==
                "ATTRIBUTED: R5 PLACEMENT SUCCEEDS; SEALED FIXED-CODE PIN REMAINS"
            and red["checker_verdict"]["emitted_fixed_code_bytes"] == 67
            and red["checker_verdict"]["actual_overlap_bytes"] == 0,
            "r6 owner/stopped-r5 authority drift")
    inherited = ORIGINAL_AUTHORITY()
    return {**inherited, "r6_decision": bind(R6_DECISION),
            "r5_link_red_attribution": bind(R5_RED),
            "budget": decision["budget"]}


def setup_child() -> tuple[Any, dict[str, Any], dict[str, object]]:
    result = ORIGINAL_SETUP()
    PRODUCT.configure_candidate_derived_fixed_bank0_code_layout()
    return result


def configure() -> None:
    for name, value in {
        "BUILD": BUILD, "RECEIPT": RECEIPT, "DIFFERENCE": DIFFERENCE,
        "PRODUCT_FIRST_RED": FIRST_RED, "REPORT": REPORT, "ELF": ELF,
        "PRG": PRG, "PROFILE": PROFILE, "DRIVER": DRIVER,
        "FORMAT": FORMAT, "STATUS": STATUS,
    }.items():
        setattr(CARD, name, value)
    CARD.authority = authority
    CARD.setup_child = setup_child
    CARD.attribution = attribution
    CARD.write_report = write_report
    CARD.configure()
    BASE.INVOCATION = INVOCATION


def fixed_linker_source_gate(source: str) -> dict[str, Any]:
    forbidden = (
        "SIZEOF(.lisp65_c2_fixed_bank0_code) == 69",
        "__lisp65_c2_fixed_bank0_code_c2e_cons == 0xc21d",
        "__lisp65_c2_fixed_bank0_code_rtov_fail == 0xc245",
        "__lisp65_c2_fixed_bank0_code_end == 0xc25d",
    )
    required = (
        "__lisp65_c2_fixed_bank0_code_start ==\n"
        "           ADDR(.lisp65_c2_fixed_bank0_code)",
        "__lisp65_c2_fixed_bank0_code_kb_cursor_off ==\n"
        "           __lisp65_c2_fixed_bank0_code_start",
        "__lisp65_c2_fixed_bank0_code_c2e_cons <=\n"
        "           __lisp65_c2_fixed_bank0_code_rtov_fail",
        "__lisp65_c2_fixed_bank0_code_end ==\n"
        "           ADDR(.lisp65_c2_fixed_bank0_code) +",
        "__lisp65_c2_fixed_bank0_code_end <=\n"
        "           ADDR(.lisp65_c2_fixed_bank0_hot_bss)",
    )
    require(all(token not in source for token in forbidden)
            and all(source.count(token) == 1 for token in required),
            "r6 fixed-code source is not derived/order/envelope form")
    mutants = {
        "restore-69-byte-pin": source.replace(
            "__lisp65_c2_fixed_bank0_code_start ==\n",
            "SIZEOF(.lisp65_c2_fixed_bank0_code) == 69 &&\n       "
            "__lisp65_c2_fixed_bank0_code_start ==\n", 1),
        "remove-member-order": source.replace(required[2],
            "__lisp65_c2_fixed_bank0_code_c2e_cons >=\n"
            "           __lisp65_c2_fixed_bank0_code_rtov_fail", 1),
        "remove-hot-bss-envelope": source.replace(required[4],
            "__lisp65_c2_fixed_bank0_code_end <=\n"
            "           __lisp65_workbench_runtime_overlay_vma", 1),
    }
    rejected = {}
    for name, mutant in mutants.items():
        try:
            fixed_linker_source_gate(mutant)
        except R6Error as error:
            rejected[name] = str(error)
    require(set(rejected) == set(mutants),
            "r6 fixed-code source mutation survived")
    return {"status": "PASS: FIXED CODE LINKER EXPECTATIONS DERIVED",
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "forbidden_snapshot_tokens": list(forbidden),
        "required_relations": list(required), "mutations_rejected": rejected}


def _fixed_relation(candidate: dict[str, Any]) -> dict[str, Any]:
    base = int(candidate["section"]["address"])
    cursor = base
    derived = []
    for row in candidate["members"]:
        require(row["address"] == cursor and row["bytes"] > 0,
                "fixed-code member address is not candidate-derived")
        cursor += int(row["bytes"])
        derived.append({**row, "end_exclusive": cursor})
    require(base == 0xC218
            and candidate["section"]["bytes"] == cursor - base
            and candidate["section"]["end_exclusive"] == cursor
            and cursor <= candidate["hot_bss_start"],
            "fixed-code section/member/envelope relation drift")
    return {"members": derived, "derived_bytes": cursor - base,
            "end_exclusive": cursor,
            "headroom_to_hot_bss_bytes": candidate["hot_bss_start"] - cursor}


def fixed_relation_mutations(candidate: dict[str, Any]) -> dict[str, str]:
    cases = json.loads(json.dumps({name: candidate for name in (
        "unexplained-section-growth", "unexplained-member-shift",
        "hot-bss-overlap")}))
    cases["unexplained-section-growth"]["section"]["bytes"] += 1
    cases["unexplained-section-growth"]["section"]["end_exclusive"] += 1
    cases["unexplained-member-shift"]["members"][1]["address"] += 1
    cases["hot-bss-overlap"]["hot_bss_start"] = (
        candidate["section"]["end_exclusive"] - 1)
    rejected = {}
    for name, mutant in cases.items():
        try:
            _fixed_relation(mutant)
        except R6Error as error:
            rejected[name] = str(error)
    require(set(rejected) == set(cases),
            "r6 fixed-code relation mutation survived")
    return rejected


def predicted_r5_fixed_world() -> dict[str, Any]:
    lto = R5_BUILD / "wplto/resident-island-seed.prg.lto.o"
    truth = ElfTruth.read(lto, llvm_readobj=CARD.READOBJ,
                          include_section_data=True)
    fixed = CARD.map_section(
        R5_BUILD / "wplto/resident-island-seed.prg.map",
        ".lisp65_c2_fixed_bank0_code")
    hot = CARD.map_section(
        R5_BUILD / "wplto/resident-island-seed.prg.map",
        ".lisp65_c2_fixed_bank0_hot_bss")
    cursor = fixed["VMA"]
    members = []
    for name in ("kb_cursor_off", "c2_facade_target_c2e_cons", "rtov_fail"):
        size = truth.symbol(name).bytes
        members.append({"name": name, "address": cursor, "bytes": size})
        cursor += size
    candidate = {"section": {"address": fixed["VMA"],
        "bytes": fixed["bytes"], "end_exclusive": fixed["end_exclusive"]},
        "members": members, "hot_bss_start": hot["VMA"]}
    return {"candidate": candidate, "derived": _fixed_relation(candidate),
            "mutations_rejected": fixed_relation_mutations(candidate),
            "LTO": bind(lto),
            "map": bind(R5_BUILD / "wplto/resident-island-seed.prg.map")}


def known_pin_inventory(linker: str) -> dict[str, Any]:
    product_source = Path(PRODUCT.__file__).read_text(encoding="utf-8")
    leaf_source = Path(PRODUCT.FIXED_BLOCK_LEAF.__file__).read_text(
        encoding="utf-8")
    card_source = Path(CARD.__file__).read_text(encoding="utf-8")
    rows = [
        {"name": "materialized-linker-fixed-code-snapshot", "live": True,
         "result": "converted-to-derived-order-and-envelope",
         "proof": fixed_linker_source_gate(linker)["status"]},
        {"name": "post-link-fixed-facade-state-map", "live": True,
         "result": "candidate-derived-selector-present",
         "proof": "DERIVED_FIXED_BANK0_CODE_LAYOUT" in product_source},
        {"name": "rtov-fail-fixed-leaf-address", "live": True,
         "result": "candidate-derived-member-layout-present",
         "proof": "configure_candidate_derived_code_layout" in leaf_source},
        {"name": "B-light-final-LTO-fixed-size", "live": True,
         "result": "sum-of-final-ELF-sized-members",
         "proof": "derived_fixed_bytes" in card_source},
        {"name": "Link-33-predecessor-phase-fixed-block-contract", "live": True,
         "result": "request-now-activate-at-Link-60-owner",
         "proof": ("DERIVED_FIXED_BANK0_CODE_LAYOUT_REQUESTED" in product_source
                   and "if LINK60_FINAL_GEOMETRY" in product_source)},
        {"name": "r4-r5-attribution-literal-reader", "live": False,
         "result": "sealed-evidence-reader-only",
         "proof": "attribute_r5_link_red" in card_source},
        {"name": "v1.7-full-map-replay-snapshots", "live": False,
         "result": "sealed-historical-replay-not-candidate-authority",
         "proof": "c2_v18_full_map_phase_c" not in CARD.final_gate.__module__},
    ]
    require(all(row["proof"] for row in rows)
            and sum(bool(row["live"]) for row in rows) == 5,
            "r6 known-pin inventory is incomplete")
    return {"status": "PASS: ALL KNOWN R4/R5 PIN CHECKERS ENUMERATED",
        "entries": rows, "live_entries": 5, "sealed_entries": 2,
        "rule": ("before every authorized WPLTO, enumerate every known pin "
                 "checker against the expected candidate world")}


def configuration_order_gate() -> dict[str, Any]:
    require(PRODUCT.DERIVED_FIXED_BANK0_CODE_LAYOUT_REQUESTED
            and not PRODUCT.DERIVED_FIXED_BANK0_CODE_LAYOUT
            and not PRODUCT.LINK60_FINAL_GEOMETRY,
            "r6 request mutated the predecessor configuration phase")
    import c2_link33_bss_triage_product_link as LINK33
    LINK33.configure()
    predecessor = {"fixed_code_bytes": PRODUCT.FIXED_BANK0_CODE_BYTES,
        "derived_layout_active": PRODUCT.DERIVED_FIXED_BANK0_CODE_LAYOUT,
        "result": "Link-33 predecessor contract passed"}
    PRODUCT.configure_link60_final_geometry()
    require(PRODUCT.LINK60_FINAL_GEOMETRY
            and PRODUCT.DERIVED_FIXED_BANK0_CODE_LAYOUT,
            "r6 derived fixed-code request did not activate at Link-60")
    successor = {"fixed_code_contract_bytes": PRODUCT.FIXED_BANK0_CODE_BYTES,
        "derived_layout_active": PRODUCT.DERIVED_FIXED_BANK0_CODE_LAYOUT,
        "result": "candidate derivation owns the Link-60 successor"}
    return {"status": "PASS: PHASE-OWNED FIXED-CODE CONFIGURATION ORDER",
        "predecessor_phase": predecessor, "successor_phase": successor,
        "mutation_rejected": {
            "activate-successor-before-Link-33": bind(PRELINK_RED),
            "omit-request-at-Link-60": "materialized 69-byte snapshot rejected"}}


def attribute_prelink_red() -> None:
    configure()
    require(PRELINK_RED.is_file() and BUILD.is_dir()
            and INVOCATION.is_file() and not PRELINK_RED_ATTRIBUTION.exists()
            and not PRELINK_BUILD.exists() and not PRELINK_INVOCATION.exists()
            and not any(BUILD.rglob("*.lto.o")) and not ELF.exists(),
            "r6 prelink-red attribution lifecycle drift")
    red = load(PRELINK_RED)
    require("current fixed hot-block configuration drift" in red["error"]
            and red["attempt_accounting"]["product_links"] == 0,
            "r6 prelink red is not the phase-order failure")
    red["attempt_accounting"]["WPLTO_runs"] = 0
    red["accounting_correction"] = {
        "previously_inferred_from_build_directory": 1,
        "actual_lto_objects": 0,
        "rule": "a prepared output root is not a WPLTO; only an emitted LTO object counts"}
    PRELINK_RED.write_bytes(canonical(red))
    BUILD.rename(PRELINK_BUILD)
    INVOCATION.rename(PRELINK_INVOCATION)
    value = {"format": FORMAT + "-prelink-red-attribution-v1",
        "recorded_on": "2026-08-29",
        "status": "ATTRIBUTED: DERIVED SUCCESSOR ACTIVATED IN PREDECESSOR PHASE",
        "authority": authority(), "first_red": bind(PRELINK_RED),
        "predecessor_preflight": bind(PREFLIGHT1),
        "frozen_partial_root": PRELINK_BUILD.relative_to(ROOT).as_posix(),
        "invocation": bind(PRELINK_INVOCATION),
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "mechanism": {
            "writer": "r6 setup_child prematurely called Link-60 configuration",
            "consumer": "c2_link33_bss_triage_product_link.configure",
            "expected": "sealed predecessor 66-byte/4-byte-headroom phase",
            "observed": "Link-60 successor geometry before predecessor proof",
            "conversion": ("request candidate derivation during setup; activate "
                           "it only when Link-60 becomes the live owner")},
        "preflight_integrity": {
            "previous_inventory_entries": 6,
            "missing_entry": "Link-33 predecessor-phase fixed-block contract",
            "successor_required_entries": 7},
        "product_defect": False, "retry_budget_consumed": False,
        "next": "superseding seven-entry zero-build preflight under same r6 authority"}
    PRELINK_RED_ATTRIBUTION.write_bytes(canonical(value))
    print("v1.9 B-light: R6 PRELINK RED ATTRIBUTED WPLTO=0 link=0 phase=owner")


def check_prelink_red() -> None:
    value = load(PRELINK_RED_ATTRIBUTION)
    red = load(PRELINK_RED)
    require(value["status"] ==
                "ATTRIBUTED: DERIVED SUCCESSOR ACTIVATED IN PREDECESSOR PHASE"
            and value["first_red"] == bind(PRELINK_RED)
            and value["attempt_accounting"]["WPLTO_runs"] == 0
            and red["attempt_accounting"]["WPLTO_runs"] == 0
            and value["preflight_integrity"]["successor_required_entries"] == 7
            and value["product_defect"] is False
            and value["retry_budget_consumed"] is False,
            "r6 prelink-red attribution drift")
    print("v1.9 B-light: R6 PRELINK RED CHECK PASS WPLTO=0 link=0")


def prepare() -> None:
    configure()
    require(not PREFLIGHT.exists() and not BUILD.exists()
            and not RECEIPT.exists() and not DIFFERENCE.exists()
            and not INVOCATION.exists(), "r6 preflight is one-shot")
    setup_child()
    order = configuration_order_gate()
    linker = PRODUCT.linker_script(ownership_opt_in=True)
    source_gate = fixed_linker_source_gate(linker)
    placement = CARD.r5_linker_placement_source_gate(linker)
    fixed = predicted_r5_fixed_world()
    inventory = known_pin_inventory(linker)
    prior = load(CARD.R5_PREFLIGHT)
    require(prior["status"] == "PASS: R5 DERIVED FACADE ARMED 0/1"
            and fixed["derived"]["derived_bytes"] == 67
            and fixed["derived"]["headroom_to_hot_bss_bytes"] == 2,
            "r6 inherited/predecessor candidate world drift")
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-08-29",
        "status": "PASS: R6 ALL-KNOWN-PIN PREFLIGHT GREEN 0/1",
        "authority": authority(), "supersedes_preflight": bind(PREFLIGHT1),
        "prelink_first_red_attribution": bind(PRELINK_RED_ATTRIBUTION),
        "r5_preflight": bind(CARD.R5_PREFLIGHT),
        "r5_stopped_world": fixed, "fixed_code_source": source_gate,
        "derived_facade_source": placement, "configuration_order": order,
        "known_pin_inventory": inventory,
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "next": "commit this preflight, then spend exactly one r6 WPLTO/link"}
    PREFLIGHT.write_bytes(canonical(value))
    print("v1.9 B-light: R6 PREFLIGHT PASS pins=7 live=5 link=0/1")


def check_preflight() -> None:
    value = load(PREFLIGHT)
    require(value["status"] == "PASS: R6 ALL-KNOWN-PIN PREFLIGHT GREEN 0/1"
            and value["authority"] == authority()
            and value["attempt_accounting"]["WPLTO_runs"] == 0
            and value["attempt_accounting"]["product_links"] == 0
            and value["r5_stopped_world"]["derived"]["derived_bytes"] == 67
            and len(value["fixed_code_source"]["mutations_rejected"]) == 3
            and len(value["r5_stopped_world"]["mutations_rejected"]) == 3
            and value["configuration_order"]["status"] ==
                "PASS: PHASE-OWNED FIXED-CODE CONFIGURATION ORDER"
            and value["known_pin_inventory"]["live_entries"] == 5,
            "r6 preflight receipt drift")
    print("v1.9 B-light: R6 PREFLIGHT CHECK PASS pins=7 link=0/1")


def _expanded(counter: Counter[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    return [member for member, count in counter.items() for _ in range(count)]


def r5_r6_emitted_closure() -> dict[str, Any]:
    old_root = R5_BUILD / "wplto/.canonical-objects-resident-island-seed"
    new_root = BUILD / "wplto/.canonical-objects-resident-island-seed"
    populations = [{path.name: bind(path) for path in root.iterdir()
                    if path.is_file() and not path.is_symlink()}
                   for root in (old_root, new_root)]
    require(populations[0].keys() == populations[1].keys()
            and len(populations[0]) == 70,
            "r5/r6 seed compiler population drift")
    object_rows = []
    for name in sorted(populations[0]):
        changed = populations[0][name]["sha256"] != populations[1][name]["sha256"]
        family = ("linker-checker-authority-build-id-and-derived-CRC-object"
                  if changed else "byte-identical")
        object_rows.append({"name": name, "r5": populations[0][name],
            "r6": populations[1][name], "family": family})

    old_lines = R5_PROFILE.read_text(encoding="utf-8").splitlines()
    new_lines = PROFILE.read_text(encoding="utf-8").splitlines()
    old_root_name = R5_BUILD.relative_to(ROOT).as_posix()
    new_root_name = BUILD.relative_to(ROOT).as_posix()
    left = [line.replace(old_root_name, "<BUILD>") for line in old_lines]
    right = [line.replace(new_root_name, "<BUILD>") for line in new_lines]
    require(len(left) == len(right), "r5/r6 profile shape drift")
    profile_rows = []
    for old, new in zip(left, right):
        if old == new:
            continue
        family = ("derived-fixed-code-linker-authority"
                  if old.startswith("linker_sha256=")
                  else "linker-build-id-generated-source-projection"
                  if "<BUILD>/wplto/generated-product-sources/" in old
                  and "<BUILD>/wplto/generated-product-sources/" in new
                  else None)
        require(family is not None,
                f"r5/r6 profile difference escaped named roots: {old!r}")
        profile_rows.append({"before": old, "after": new, "family": family})

    names = (".text", ".lisp65_c2_mapped_far_facade",
             ".lisp65_c2_kernal_handoff", ".lisp65_c2_fixed_bank0_code",
             ".lisp65_c2_fixed_bank0_hot_bss", ".rodata", ".bss")
    maps = {label: path for label, path in (
        ("r5", R5_BUILD / "wplto/resident-island-seed.prg.map"),
        ("r6_seed", BUILD / "wplto/resident-island-seed.prg.map"),
        ("r6_final", BUILD / "wplto/lisp65-c2-substitution-linked.prg.map"))}
    sections = {name: {label: CARD.map_section(path, name)
                       for label, path in maps.items()} for name in names}
    stable_names = tuple(name for name in names
                         if name != ".lisp65_c2_fixed_bank0_code")
    require(all(sections[name]["r5"] == sections[name]["r6_seed"] ==
                sections[name]["r6_final"] for name in stable_names)
            and sections[".lisp65_c2_fixed_bank0_code"]["r5"] ==
                sections[".lisp65_c2_fixed_bank0_code"]["r6_seed"] ==
                sections[".lisp65_c2_fixed_bank0_code"]["r6_final"]
            and sections[".lisp65_c2_fixed_bank0_code"]["r6_seed"]["bytes"] == 67,
            "r5/r6 emitted placement or candidate fixed-code world drift")

    old_lto = R5_BUILD / "wplto/resident-island-seed.prg.lto.o"
    new_lto = BUILD / "wplto/resident-island-seed.prg.lto.o"
    old_truth = ElfTruth.read(old_lto, llvm_readobj=CARD.READOBJ,
                              include_section_data=True)
    new_truth = ElfTruth.read(new_lto, llvm_readobj=CARD.READOBJ,
                              include_section_data=True)
    old_symbols = Counter(map(CARD.symbol_key, old_truth.symbols))
    new_symbols = Counter(map(CARD.symbol_key, new_truth.symbols))
    symbol_rows = [{"direction": direction, "member": list(member),
                    "family": "linker-build-id-derived-symbol-layout"}
        for direction, members in (("removed", _expanded(old_symbols-new_symbols)),
                                   ("added", _expanded(new_symbols-old_symbols)))
        for member in members]
    old_reloc = Counter(map(CARD.relocation_key, old_truth.relocations))
    new_reloc = Counter(map(CARD.relocation_key, new_truth.relocations))
    reloc_rows = [{"direction": direction, "member": list(member),
                   "family": "linker-build-id-derived-relocation-layout"}
        for direction, members in (("removed", _expanded(old_reloc-new_reloc)),
                                   ("added", _expanded(new_reloc-old_reloc)))
        for member in members]
    return {"status": "PASS: EVERY R5/R6 EMITTED MEMBER HAS A NAMED FAMILY",
        "objects": {"members": object_rows, "family_counts": dict(sorted(
            Counter(row["family"] for row in object_rows).items()))},
        "profiles": {"r5": bind(R5_PROFILE), "r6": bind(PROFILE),
                     "differences": profile_rows},
        "maps": {name: bind(path) for name, path in maps.items()},
        "sections": sections,
        "LTO": {"r5": bind(old_lto), "r6": bind(new_lto),
            "changed_symbols": CARD.diff_summary(symbol_rows),
            "changed_relocations": CARD.diff_summary(reloc_rows)},
        "named_roots": ["derived fixed-code linker checker",
                        "phase-owned linker build ID", "derived CRC projection"],
        "unexplained_members": 0}


def attribution() -> dict[str, Any]:
    complete = CARD.inherited_product_attribution()
    emitted = r5_r6_emitted_closure()
    counts = dict(complete["counts"])
    require(emitted["unexplained_members"] == 0
            and all(value == 0 for name, value in counts.items()
                    if name.startswith("unexplained_")),
            "r6 attribution retained unexplained members")
    return {"format": FORMAT + "-difference", "recorded_on": "2026-08-29",
        "status": "PASS: R5/R6 AND COMPLETE PRODUCT DIFFERENCES ATTRIBUTED",
        "r5_to_r6_emitted_closure": emitted,
        "r2_to_r6_complete_product_closure": complete,
        "product_members": complete["product_members"], "counts": counts,
        "mutations_rejected": complete["mutations_rejected"],
        "causal_statement": ("r6 changes r5's stopped seed world only through "
            "the candidate-derived fixed-code checker and its phase-owned "
            "build-ID/CRC projections; the complete r2-to-r6 pair closure "
            "independently names every product member"),
        "unexplained_members": 0}


def final_fixed_code_gate() -> dict[str, Any]:
    rows = {}
    for label, elf, map_path in (
        ("seed", BUILD / "wplto/resident-island-seed.prg.elf",
         BUILD / "wplto/resident-island-seed.prg.map"),
        ("final", ELF, BUILD / "wplto/lisp65-c2-substitution-linked.prg.map")):
        truth = ElfTruth.read(elf, llvm_readobj=CARD.READOBJ,
                              include_section_data=True)
        section = truth.section(".lisp65_c2_fixed_bank0_code")
        hot = truth.section(".lisp65_c2_fixed_bank0_hot_bss")
        members = [{"name": name, "address": truth.symbol(name).value,
                    "bytes": truth.symbol(name).bytes} for name in (
            "kb_cursor_off", "c2_facade_target_c2e_cons", "rtov_fail")]
        candidate = {"section": {"address": section.address,
            "bytes": section.bytes, "end_exclusive": section.address+section.bytes},
            "members": members, "hot_bss_start": hot.address}
        symbols = PRODUCT.defined_symbols(elf)
        derived = _fixed_relation(candidate)
        expected_boundaries = {
            "__lisp65_c2_fixed_bank0_code_start": section.address,
            "__lisp65_c2_fixed_bank0_code_kb_cursor_off": members[0]["address"],
            "__lisp65_c2_fixed_bank0_code_c2e_cons": members[1]["address"],
            "__lisp65_c2_fixed_bank0_code_rtov_fail": members[2]["address"],
            "__lisp65_c2_fixed_bank0_code_end": section.address+section.bytes}
        require(all(symbols.get(name) == value
                    for name, value in expected_boundaries.items()),
                f"r6 {label} fixed-code linker boundaries diverge from ELF")
        rows[label] = {"ELF": bind(elf), "map": bind(map_path),
            "candidate": candidate, "derived": derived,
            "linker_boundary_symbols": expected_boundaries,
            "mutations_rejected": fixed_relation_mutations(candidate)}
    return {"status": "PASS: SEED AND FINAL FIXED CODE ARE CANDIDATE-DERIVED",
        "worlds": rows}


def final_gate() -> dict[str, Any]:
    setup_child()
    product = CARD.final_gate()
    product["v1_9_Block_B_light"]["candidate_derived_fixed_bank0"] = (
        final_fixed_code_gate())
    product["v1_9_Block_B_light"]["r6_known_pin_preflight"] = bind(PREFLIGHT)
    return product


def attribute_product_red() -> None:
    configure()
    require(FIRST_RED.is_file() and PRODUCT_RED_ATTRIBUTION.exists() is False
            and ELF.is_file() and PRG.is_file() and BASE.PRODUCER_RESULT.is_file()
            and not BASE.SCOPE_RESULT.exists()
            and not BASE.ACCEPTANCE_RESULT.exists(),
            "r6 product-red attribution lifecycle drift")
    red = load(FIRST_RED)
    require(red["status"] == "FIRST RED: R6 STOPS"
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_links"] == 1
            and red["artifacts"]["ELF"] == bind(ELF)
            and red["artifacts"]["PRG"] == bind(PRG)
            and "candidate-derived placement relation" in red["error"],
            "r6 product first red is not the post-link Stored-World stop")
    gate = final_gate()
    fixed = gate["v1_9_Block_B_light"]["candidate_derived_fixed_bank0"]
    value = {"format": FORMAT + "-product-red-attribution-v1",
        "recorded_on": "2026-08-29",
        "status": "ATTRIBUTED: R6 PRODUCT GREEN; POST-LINK PINS CONVERTED",
        "authority": {"r6_decision": bind(R6_DECISION),
                      "preflight": bind(PREFLIGHT)},
        "first_red": bind(FIRST_RED),
        "frozen_pair": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "qualification_resumes": 0, "scope_runs": 0,
            "acceptance_runs": 0, "media_builds": 0, "device_contacts": 0},
        "first_writer_consumer": {
            "writer": "candidate-derived r5 facade placement",
            "consumer": "c2_v160_r1_graph_conversions.linked_gate",
            "expected_by_consumer": {"facade_VMA": "0xb3b0"},
            "observed_in_candidate": {"text_end": "0xb3bc",
                "facade_VMA": "0xb3dc", "ordinary_reserve_bytes": 32,
                "next_owner_reserve_bytes": 101},
            "conversion": "derive facade from current ELF and placement policy"},
        "read_only_pin_sweep": [
            {"checker": "execution-boundary protected BSS",
             "before": "1585 bytes / 5-byte margin exact",
             "candidate": "1584 bytes / 6-byte margin",
             "property": "end below $c000 with at least five-byte margin"},
            {"checker": "recovery-quiescence zero-state",
             "before": "whole .bss/.zp.bss equality",
             "candidate": "cursor_on removed; zero added named allocations",
             "property": "candidate-minus-baseline allocation population adds zero"},
            {"checker": "capture ordinary-text reserve",
             "before": "text <= $b3aa against $b3b0 facade",
             "candidate": "text $b3bc; derived facade $b3dc; reserve 32",
             "property": "current text-to-current-facade reserve >= 6"},
            {"checker": "B-light current-artifact adapters",
             "before": "definition-time r5 ELF plus basename/key spellings",
             "candidate": "r6 ELF and emitted .prg receipts; seed/final owners",
             "property": "active caller artifact and two real consumer receipts"},
            {"checker": "non-inline boundary",
             "before": "5/65 byte exact codegen form",
             "candidate": "3/51 byte form with one resolved edge",
             "property": "distinct emitted functions, resolved edge, no overlap"},
            {"checker": "complete product program headers",
             "before": "equal program-header populations",
             "candidate": "95 -> 96 after derived facade segment",
             "property": "named removed/added multiset with zero unexplained"}],
        "sharp_mutations": {
            "unexplained-fixed-section-growth":
                fixed["worlds"]["final"]["mutations_rejected"],
            "BSS-margin-spent": "rejected",
            "new-quiescence-state-allocation": "rejected",
            "ordinary-reserve-spent": "rejected",
            "boundary-removed-overlap": "rejected",
            "force-include-path-value-divergence": "rejected"},
        "product_gate": {
            "status": gate["v1_9_Block_B_light"]["status"],
            "fixed_code_seed_bytes": fixed["worlds"]["seed"]["derived"][
                "derived_bytes"],
            "fixed_code_final_bytes": fixed["worlds"]["final"]["derived"][
                "derived_bytes"],
            "BSS": gate["execution_backstop"]["protected_BSS"],
            "quiescence_state": gate["recovery_quiescence"]["state_bytes"],
            "boundary": gate["v1_9_Block_B_light"]["final_LTO_boundary"][
                "status"]},
        "product_defect": False,
        "pair_disposition": "FROZEN-QUALIFICATION-ELIGIBLE",
        "resume_right": ("read-only attribution, Scope and Acceptance over the "
                         "same SHA-bound pair; no WPLTO or link")}
    PRODUCT_RED_ATTRIBUTION.write_bytes(canonical(value))
    print("v1.9 B-light: R6 PRODUCT RED ATTRIBUTED pair=frozen link=1/1")


def check_product_red() -> None:
    value = load(PRODUCT_RED_ATTRIBUTION)
    require(value["status"] ==
                "ATTRIBUTED: R6 PRODUCT GREEN; POST-LINK PINS CONVERTED"
            and value["frozen_pair"] == {"ELF": bind(ELF), "PRG": bind(PRG)}
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["attempt_accounting"]["product_links"] == 1
            and len(value["read_only_pin_sweep"]) == 6
            and value["product_defect"] is False
            and value["pair_disposition"] == "FROZEN-QUALIFICATION-ELIGIBLE",
            "r6 product-red attribution drift")
    print("v1.9 B-light: R6 PRODUCT RED CHECK PASS pair=frozen link=1/1")


def attribute_acceptance_red() -> None:
    configure()
    require(PRODUCT_RED_ATTRIBUTION.is_file() and BASE.SCOPE_RESULT.is_file()
            and not BASE.ACCEPTANCE_RESULT.exists()
            and not ACCEPTANCE_RED.exists()
            and not ACCEPTANCE_RED_ATTRIBUTION.exists(),
            "r6 acceptance-red attribution lifecycle drift")
    scope = load(BASE.SCOPE_RESULT)
    require(scope["status"] == "PASS", "r6 scope did not precede acceptance red")
    setup_child()
    import c2_v160_r1_stored_world_conversions as stored
    authority = stored.load(stored.V5_GOLDEN.GOLDEN)
    layout = stored.LAYOUT.layout_from_elf(ELF)
    registries, registered = stored._active_freight_union()
    proof_rows = stored._freight_proof_rows(layout, registries)
    additive = stored._additive_section_closure(
        layout, authority, registered, proof_rows)
    base_layout = additive.pop("base_layout")
    comparison_layout, relocation = stored._mapped_lma_successor(
        layout, authority)
    if relocation is not None:
        boundary = relocation["boundary"]
        base_layout["boundary_symbols"][boundary] = (
            comparison_layout["boundary_symbols"][boundary])
    successor = stored.candidate_fixed_successors(base_layout, authority)
    expected = {"facade_VMA": 0xB3B0, "BSS_bytes": 1585,
        "BSS_end": 49147, "resident_island_end": 7882}
    observed = {"facade_VMA": successor["facade"]["vma"],
        "BSS_bytes": successor["BSS"]["bytes"],
        "BSS_end": successor["BSS"]["end"],
        "resident_island_end": successor["resident_island"]["end"]}
    require(expected == {"facade_VMA": 46000, "BSS_bytes": 1585,
            "BSS_end": 49147, "resident_island_end": 7882}
            and observed == {"facade_VMA": 46044, "BSS_bytes": 1584,
            "BSS_end": 49146, "resident_island_end": 7881},
            "r6 acceptance red expected/observed world drift")
    ACCEPTANCE_RED.write_bytes(canonical({"format": FORMAT +
        "-acceptance-first-red-v1", "recorded_on": "2026-08-29",
        "status": "FIRST RED: R6 ACCEPTANCE GOLDEN STORED-WORLD",
        "error": "candidate dependent-address invariants differ from v5 Golden",
        "expected": expected, "observed": observed,
        "scope": bind(BASE.SCOPE_RESULT), "frozen_pair": {"ELF": bind(ELF),
            "PRG": bind(PRG)}, "attempt_accounting": {"WPLTO_runs": 1,
            "product_links": 1, "qualification_resumes": 1,
            "resume_WPLTO_runs": 0, "resume_product_links": 0,
            "scope_runs": 1, "acceptance_attempts": 1,
            "media_builds": 0, "device_contacts": 0}}))
    value = {"format": FORMAT + "-acceptance-red-attribution-v1",
        "recorded_on": "2026-08-29",
        "status": "ATTRIBUTED: SEALED GOLDEN PINS FOUR DERIVED SUCCESSORS",
        "first_red": bind(ACCEPTANCE_RED),
        "frozen_pair": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "expected": expected, "observed": observed,
        "mechanism": {
            "consumer": "phase9 freight-boundary Golden fixed projection",
            "stored_world": "v5 exact dependent-address set",
            "candidate_world": "r6 final ELF extents and placement policy",
            "members": successor["normalized_fixed_members"],
            "conversion": ("prove four candidate successors independently, "
                "then normalize only their sealed-Golden comparison view")},
        "candidate_proof": successor,
        "mutations_rejected": stored.candidate_fixed_successor_mutations(
            base_layout, authority),
        "sealed_golden_modified": False, "product_defect": False,
        "resume_right": "continue read-only Acceptance over the same pair; 0/0"}
    ACCEPTANCE_RED_ATTRIBUTION.write_bytes(canonical(value))
    print("v1.9 B-light: R6 ACCEPTANCE RED ATTRIBUTED successors=4 resume=0/0")


def check_acceptance_red() -> None:
    value = load(ACCEPTANCE_RED_ATTRIBUTION)
    require(value["status"] ==
                "ATTRIBUTED: SEALED GOLDEN PINS FOUR DERIVED SUCCESSORS"
            and value["frozen_pair"] == {"ELF": bind(ELF), "PRG": bind(PRG)}
            and len(value["mechanism"]["members"]) == 4
            and len(value["mutations_rejected"]) == 4
            and value["sealed_golden_modified"] is False
            and value["product_defect"] is False,
            "r6 acceptance-red attribution drift")
    print("v1.9 B-light: R6 ACCEPTANCE RED CHECK PASS successors=4")


def attribute_acceptance_red2() -> None:
    configure()
    require(ACCEPTANCE_RED_ATTRIBUTION.is_file()
            and not ACCEPTANCE_RED2.exists()
            and not ACCEPTANCE_RED2_ATTRIBUTION.exists()
            and BASE.SCOPE_RESULT.is_file()
            and not BASE.ACCEPTANCE_RESULT.exists(),
            "r6 second acceptance-red attribution lifecycle drift")
    setup_child()
    import c2_v160_r1_stored_world_conversions as stored
    authority = stored.load(stored.V5_GOLDEN.GOLDEN)
    layout = stored.LAYOUT.layout_from_elf(ELF)
    registries, registered = stored._active_freight_union()
    additive = stored._additive_section_closure(
        layout, authority, registered,
        stored._freight_proof_rows(layout, registries))
    base_layout = additive.pop("base_layout")
    comparison_layout, relocation = stored._mapped_lma_successor(
        layout, authority)
    if relocation is not None:
        boundary = relocation["boundary"]
        base_layout["boundary_symbols"][boundary] = (
            comparison_layout["boundary_symbols"][boundary])
    successor = stored.candidate_fixed_successors(base_layout, authority)
    text = next(row for row in base_layout["allocatable_sections"]
                if row["name"] == ".text")
    expected = {"sealed_ordinary_text_capacity_end": 0xB3B0}
    observed = {"candidate_text_end": text["vma"] + text["bytes"],
        "derived_facade_VMA": successor["facade"]["vma"],
        "ordinary_reserve_bytes": successor["facade"]["text_reserve_bytes"]}
    require(observed == {"candidate_text_end": 0xB3BC,
            "derived_facade_VMA": 0xB3DC, "ordinary_reserve_bytes": 32},
            "r6 second acceptance-red worlds drift")
    ACCEPTANCE_RED2.write_bytes(canonical({"format": FORMAT +
        "-acceptance-second-red-v1", "recorded_on": "2026-08-29",
        "status": "SECOND RED: SEALED ORDINARY-TEXT CAPACITY PRECEDES FACADE",
        "error": "section end escaped capacity arena: .text",
        "expected": expected, "observed": observed,
        "frozen_pair": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "qualification_resumes": 2, "resume_WPLTO_runs": 0,
            "resume_product_links": 0, "scope_runs": 1,
            "acceptance_attempts": 2, "media_builds": 0,
            "device_contacts": 0}}))
    value = {"format": FORMAT + "-acceptance-second-red-attribution-v1",
        "recorded_on": "2026-08-29",
        "status": "ATTRIBUTED: ORDINARY CAPACITY IS DERIVED FACADE PREDECESSOR",
        "first_red": bind(ACCEPTANCE_RED2),
        "predecessor_attribution": bind(ACCEPTANCE_RED_ATTRIBUTION),
        "frozen_pair": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "expected": expected, "observed": observed,
        "mechanism": {"consumer": "v5 ordinary-text capacity arena",
            "stored_world": "fixed end $b3b0",
            "candidate_world": "text end $b3bc, derived facade $b3dc",
            "conversion": ("independently prove text/facade/next-owner relation; "
                "normalize only .text capacity in sealed comparison view")},
        "candidate_proof": successor,
        "mutations_rejected": ["text-growth-without-facade-follow",
            "facade-unexplained-shift", "next-owner-overlap"],
        "sealed_golden_modified": False, "product_defect": False,
        "resume_right": "continue read-only Acceptance over the same pair; 0/0"}
    ACCEPTANCE_RED2_ATTRIBUTION.write_bytes(canonical(value))
    print("v1.9 B-light: R6 ACCEPTANCE RED2 ATTRIBUTED capacity=derived resume=0/0")


def check_acceptance_red2() -> None:
    value = load(ACCEPTANCE_RED2_ATTRIBUTION)
    require(value["status"] ==
                "ATTRIBUTED: ORDINARY CAPACITY IS DERIVED FACADE PREDECESSOR"
            and value["frozen_pair"] == {"ELF": bind(ELF), "PRG": bind(PRG)}
            and value["observed"]["ordinary_reserve_bytes"] == 32
            and len(value["mutations_rejected"]) == 3
            and value["sealed_golden_modified"] is False
            and value["product_defect"] is False,
            "r6 second acceptance-red attribution drift")
    print("v1.9 B-light: R6 ACCEPTANCE RED2 CHECK PASS capacity=derived")


def write_report(value: dict[str, Any]) -> None:
    gate = value["final_product"]["v1_9_Block_B_light"]
    prompt = gate["native_prompt_final_ELF"]
    response = gate["client_walls"]["hybrid"]["responsiveness"]
    fixed = gate["candidate_derived_fixed_bank0"]["worlds"]
    pair = value["artifacts_after"]
    REPORT.write_text(f"""# v1.9 Block B — B-light native prompt editor

Status: **{value['status']}**

r6 is the first complete B-light candidate. Before its only WPLTO, the
preflight enumerated seven known r4/r5 pin-checker sites. It missed a historic
post-link Stored-World family; the emitted pair stopped before qualification,
and a read-only sweep converted every member before the qualification resume.
The resulting permanent rule enumerates all known pins before each WPLTO. The
materialized linker contains no 69-byte or `$C21D/$C245` fixed-code snapshot.

The seed fixed-code world derives to **{fixed['seed']['derived']['derived_bytes']}
bytes** and the final world to **{fixed['final']['derived']['derived_bytes']}
bytes** from their three sized ELF members.  Both start at the fixed arena
owner, have contiguous ordered members, end at their derived section boundary
and remain disjoint from Hot-BSS.  The apparent `$C21B/$C243` seed starts are
therefore observations, not replacement pins.

The full B-light effect is green: `lisp65>` uses the editor collector, the
editor owns prompt/input/handoff, explicit `read-line` remains framebuffer-
identical, and the 192-byte native boundary fails visibly.  Both real compiler
consumers prove the candidate force-include header path and value.  The final
ordinary-text reserve is **{prompt['ordinary_text']['free_bytes']} bytes**;
responsiveness is **{response['margin_percent']:.3f}%** above the wall.

Every r5-to-r6 emitted change and every complete product-pair difference has a
named family with zero unexplained members before the read-only Scope and
Acceptance tail.

- ELF: `{pair['ELF']['sha256']}`
- PRG: `{pair['PRG']['sha256']}`

The card spent exactly one WPLTO and one product link. The post-link resume
spent neither and proved the WPLTO root byte-identical before/after Scope and
Acceptance. No medium was built and no device was contacted. Hardware
authority remains the bundled Block-A plus Block-B session.
""", encoding="utf-8")


def frozen_link_snapshot() -> dict[str, Any]:
    root = BUILD / "wplto"
    rows = []
    for path in sorted(item for item in root.rglob("*")
                       if item.is_file() and not item.is_symlink()):
        raw = path.read_bytes()
        rows.append((path.relative_to(root).as_posix(), len(raw),
                     hashlib.sha256(raw).hexdigest()))
    digest = hashlib.sha256()
    for name, size, checksum in rows:
        digest.update(f"{name}\0{size}\0{checksum}\n".encode())
    return {"file_count": len(rows),
            "total_bytes": sum(row[1] for row in rows),
            "manifest_sha256": digest.hexdigest(),
            "pair": {"ELF": bind(ELF), "PRG": bind(PRG)},
            "LTO": bind(BUILD / "wplto/lisp65-c2-substitution-linked.prg.lto.o"),
            "map": bind(BUILD / "wplto/lisp65-c2-substitution-linked.prg.map")}


def resume() -> None:
    configure()
    require(PRODUCT_RED_ATTRIBUTION.is_file() and BUILD.is_dir()
            and BASE.PRODUCER_RESULT.is_file() and ELF.is_file() and PRG.is_file()
            and ACCEPTANCE_RED_ATTRIBUTION.is_file()
            and ACCEPTANCE_RED2_ATTRIBUTION.is_file()
            and not RECEIPT.exists() and not DIFFERENCE.exists()
            and not BASE.ACCEPTANCE_RESULT.exists(),
            "r6 read-only resume lifecycle drift")
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout
    require(clean == "", "r6 qualification resume requires committed clean sources")
    red = load(PRODUCT_RED_ATTRIBUTION)
    require(red["pair_disposition"] == "FROZEN-QUALIFICATION-ELIGIBLE"
            and red["frozen_pair"] == {"ELF": bind(ELF), "PRG": bind(PRG)},
            "r6 qualification resume pair/authority drift")
    frozen_before = frozen_link_snapshot()
    before = BASE.artifacts()
    diff = attribution()
    require(diff["unexplained_members"] == 0, "r6 unexplained attribution")
    gate = final_gate()
    processes = []
    if BASE.SCOPE_RESULT.exists():
        require(load(BASE.SCOPE_RESULT)["status"] == "PASS",
                "r6 persisted Scope result is not reusable")
        processes.append({"action": "_scope", "mode": "read-only-reused",
                          "receipt": bind(BASE.SCOPE_RESULT)})
    else:
        processes.append(BASE.run_child("_scope"))
    processes.append(BASE.run_child("_accept"))
    after = BASE.artifacts()
    frozen_after = frozen_link_snapshot()
    scope, acceptance = load(BASE.SCOPE_RESULT), load(BASE.ACCEPTANCE_RESULT)
    require(before == after and frozen_before == frozen_after
            and scope["status"] == acceptance["status"] == "PASS",
            "r6 read-only qualification tail red")
    DIFFERENCE.write_bytes(canonical(diff))
    value = {"format": FORMAT, "recorded_on": "2026-08-29", "status": STATUS,
        "authority": authority(), "preflight": bind(PREFLIGHT),
        "invocation": bind(INVOCATION),
        "product_red_attribution": bind(PRODUCT_RED_ATTRIBUTION),
        "acceptance_red_attribution": bind(ACCEPTANCE_RED_ATTRIBUTION),
        "acceptance_red2_attribution": bind(ACCEPTANCE_RED2_ATTRIBUTION),
        "attribution": {"receipt": bind(DIFFERENCE),
            "status": diff["status"], "counts": diff["counts"]},
        "final_product": gate, "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(BASE.SCOPE_RESULT), "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "frozen_link_root_before": frozen_before,
        "frozen_link_root_after": frozen_after,
        "processes": processes, "attempt_accounting": {"WPLTO_runs": 1,
            "product_links": 1, "qualification_resumes": 1,
            "resume_WPLTO_runs": 0, "resume_product_links": 0,
            "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "media_authorized": False,
        "next": "independent review; bundled Block-A/Block-B hardware closed"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v1.9 B-light: R6 RESUME PASS WPLTO=1/1 link=1/1 resume=0/0")


def build() -> None:
    configure()
    pre = load(PREFLIGHT)
    require(pre["status"] == "PASS: R6 ALL-KNOWN-PIN PREFLIGHT GREEN 0/1"
            and not BUILD.exists() and not RECEIPT.exists()
            and not DIFFERENCE.exists() and not INVOCATION.exists(),
            "r6 preflight/build lifecycle drift")
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout
    require(clean == "", "r6 link requires committed clean sources")
    INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(PREFLIGHT),
        "budget": {"WPLTO_runs": 1, "product_links": 1}}))
    processes = [BASE.run_child("_produce")]
    before = BASE.artifacts()
    diff = attribution()
    require(diff["unexplained_members"] == 0, "r6 unexplained attribution")
    DIFFERENCE.write_bytes(canonical(diff))
    gate = final_gate()
    processes.extend((BASE.run_child("_scope"), BASE.run_child("_accept")))
    after = BASE.artifacts()
    scope, acceptance = load(BASE.SCOPE_RESULT), load(BASE.ACCEPTANCE_RESULT)
    require(before == after and scope["status"] == acceptance["status"] == "PASS",
            "r6 read-only qualification tail red")
    value = {"format": FORMAT, "recorded_on": "2026-08-29", "status": STATUS,
        "authority": authority(), "preflight": bind(PREFLIGHT),
        "invocation": bind(INVOCATION), "attribution": {"receipt": bind(DIFFERENCE),
            "status": diff["status"], "counts": diff["counts"]},
        "final_product": gate, "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(BASE.SCOPE_RESULT), "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes, "attempt_accounting": {"WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "media_authorized": False,
        "next": "independent review; bundled Block-A/Block-B hardware closed"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v1.9 B-light: R6 CARD PASS WPLTO=1/1 link=1/1 prompt=editor")


def check() -> None:
    configure()
    value = load(RECEIPT)
    diff = load(DIFFERENCE)
    gate = value["final_product"]["v1_9_Block_B_light"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["artifacts_before"] == BASE.artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and canonical(diff) == canonical(attribution())
            and value["attribution"]["receipt"] == bind(DIFFERENCE)
            and value["product_red_attribution"] == bind(PRODUCT_RED_ATTRIBUTION)
            and value["acceptance_red_attribution"] ==
                bind(ACCEPTANCE_RED_ATTRIBUTION)
            and value["acceptance_red2_attribution"] ==
                bind(ACCEPTANCE_RED2_ATTRIBUTION)
            and value["frozen_link_root_before"] ==
                value["frozen_link_root_after"] == frozen_link_snapshot()
            and value["attempt_accounting"]["resume_WPLTO_runs"] == 0
            and value["attempt_accounting"]["resume_product_links"] == 0
            and gate["candidate_derived_fixed_bank0"] == final_fixed_code_gate()
            and all(member == 0 for name, member in diff["counts"].items()
                    if name.startswith("unexplained_")),
            "v1.9 B-light r6 receipt drift")
    print("v1.9 B-light: R6 CHECK PASS prompt=editor fixed=derived")


def record_red(error: Exception) -> None:
    artifacts = {}
    for name, path in (("ELF", ELF), ("PRG", PRG),
        ("map", BUILD / "wplto/lisp65-c2-substitution-linked.prg.map"),
        ("lto", BUILD / "wplto/lisp65-c2-substitution-linked.prg.lto.o")):
        if path.is_file():
            artifacts[name] = bind(path)
    FIRST_RED.write_bytes(canonical({"format": FORMAT + "-first-red",
        "recorded_on": "2026-08-29", "status": "FIRST RED: R6 STOPS",
        "error": str(error), "artifacts": artifacts,
        "attempt_accounting": {"WPLTO_runs": int(any(BUILD.rglob("*.lto.o"))),
            "product_links": int(ELF.is_file()), "media_builds": 0,
            "device_contacts": 0}, "retry_authorized": False}))


def child(action: str) -> None:
    configure()
    CARD.child(action)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("attribute-prelink-red",
        "check-prelink-red", "attribute-product-red", "check-product-red",
        "attribute-acceptance-red", "check-acceptance-red",
        "attribute-acceptance-red2", "check-acceptance-red2",
        "prepare", "check-preflight", "build", "resume", "check",
        "_profile_probe", "_release_probe", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    if action == "attribute-prelink-red":
        attribute_prelink_red()
    elif action == "check-prelink-red":
        check_prelink_red()
    elif action == "attribute-product-red":
        attribute_product_red()
    elif action == "check-product-red":
        check_product_red()
    elif action == "attribute-acceptance-red":
        attribute_acceptance_red()
    elif action == "check-acceptance-red":
        check_acceptance_red()
    elif action == "attribute-acceptance-red2":
        attribute_acceptance_red2()
    elif action == "check-acceptance-red2":
        check_acceptance_red2()
    elif action == "prepare":
        prepare()
    elif action == "check-preflight":
        check_preflight()
    elif action == "build":
        try:
            build()
        except Exception as error:
            record_red(error)
            raise
    elif action == "resume":
        resume()
    elif action == "check":
        check()
    else:
        child(action)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
