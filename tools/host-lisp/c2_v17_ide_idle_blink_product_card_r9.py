#!/usr/bin/env python3
"""Relink Block 3 with derived, composed Bank-2 mapped-tenant LMAs."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_bank2_composed_ownership as COMPOSED  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v17_ide_idle_blink_product_card as CARD  # noqa: E402
import c2_v17_ide_idle_blink_product_card_r8 as R8  # noqa: E402
import error_text_table as ERROR_TEXT  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
BUILD = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-card-r9"
PREFLIGHT = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-preflight-r9"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
PROBE = PREFLIGHT / "mapped-tenant-linker-probe.ld"
PROBE_RECEIPT = PREFLIGHT / "placement-probe.json"
POSTLINK = BUILD / "postlink-observation.json"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PROFILE = BUILD / "wplto/resolved-profile.txt"
SCOPE = BUILD / "owner-scope-result.json"
ACCEPTANCE = BUILD / "artifact-acceptance.json"
RECEIPT = ARCH / "c2.3-v1.7-ide-idle-blink-product-card-r9-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.7-ide-idle-blink-product-card-r9-final-red.json"
REPORT = ROOT / "docs/planning/v1.7.0-ide-idle-blink-card-r9-report.md"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "48d33835"
FORMAT = "lisp65-c2-v17-ide-idle-blink-product-card-r9-v1"
STATUS = "PASS: V1.7 BLOCK3 COMPOSED BANK2 R9 GREEN"
R8_ELF = R8.ELF
R8_PRG = R8.PRG
R8_PROFILE = R8.PROFILE
R8_RECEIPT = R8.RECEIPT
R8_BUILD = R8.BUILD
R8_PREFLIGHT = R8.PREFLIGHT
MEDIA_RED = ARCH / "c2.3-v1.7-block3-acceptance-media-preflight-first-red.json"
READOBJ = CARD.BASE.READOBJ
ORIGINAL_R8_SETUP = R8.setup_child
LOAD_SYMBOLS = {
    "__lisp65_c2_mapped_far_service_load_start",
    "__lisp65_c2_mapped_far_service_load_end",
    "__lisp65_c2_mapped_product_cold_load_start",
    "__lisp65_c2_mapped_product_cold_load_end",
}


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


def run(command: list[str], label: str) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("composed bank-2 relocation authority", "upper anchor wins",
                  "one card-3 r9 wplto", "pairwise-disjoint physical ownership",
                  "largest contiguous hole", "media and hardware remain closed"):
        require(token in text, f"r9 authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def setup_plane() -> Path:
    return PREFLIGHT / "setup-owned/static-plane/narrow-static"


def install() -> None:
    R8.BUILD = BUILD; R8.PREFLIGHT = PREFLIGHT
    R8.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT; R8.INVOCATION = INVOCATION
    R8.POSTLINK = POSTLINK; R8.RECEIPT = RECEIPT; R8.REPORT = REPORT
    R8.ELF = ELF; R8.PRG = PRG; R8.PROFILE = PROFILE
    R8.SCOPE = SCOPE; R8.ACCEPTANCE = ACCEPTANCE
    R8.DRIVER = DRIVER; R8.AUTHORIZATION = AUTHORIZATION
    R8.FORMAT = FORMAT; R8.STATUS = STATUS
    R8.authority = authority; R8.r8_setup_plane = setup_plane
    R8.setup_child = setup_child
    R8.install()


def setup_child() -> tuple[Any, dict[str, Any], dict[str, object]]:
    core, activation, cold = ORIGINAL_R8_SETUP()
    PRODUCT.configure_mapped_tenant_lma_policy("bank2-top")
    return core, activation, cold


def static_images() -> list[dict[str, Any]]:
    rows = []
    for key, name, path in CARD.specs(setup_plane()):
        value = load(path)
        rows.append({"name": name, "key": key,
                     "bytes": int(value["code_bytes"]),
                     "authority": bind(path)})
    require(len(rows) == 6 and sum(row["bytes"] for row in rows) == 52230,
            "r9 six-image static owner inventory drift")
    return rows


def expected_vmas() -> dict[str, int]:
    truth = ElfTruth.read(R8_ELF, llvm_readobj=READOBJ,
                          include_section_data=False)
    return {name: truth.section(name).address for name, _prefix in COMPOSED.MAPPED}


def composed(elf: Path = ELF) -> dict[str, Any]:
    return COMPOSED.derive(
        elf=elf,
        plane=setup_plane() / "v6-semantics/bank2-static-code.bin",
        readobj=READOBJ, static_images=static_images(),
        expected_vmas=expected_vmas())


def price() -> dict[str, Any]:
    truth = ElfTruth.read(R8_ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    plane_bytes = 52230
    static_end = COMPOSED.BANK2_START + plane_bytes
    far = truth.section(".lisp65_c2_mapped_far_service").bytes
    cold = truth.section(".lisp65_c2_mapped_product_cold").bytes
    total = far + cold
    lower_end = static_end + total
    upper_start = COMPOSED.BANK2_END - total
    lower_hole = COMPOSED.BANK2_END - lower_end
    upper_hole = upper_start - static_end
    require((far, cold, total) == (1488, 324, 1812)
            and lower_hole == upper_hole > 0,
            "r9 anchor price arithmetic drift")
    return {
        "status": "PASS: UPPER DERIVED ANCHOR WINS EQUAL-CAPACITY PRICE",
        "inputs": {"static_plane_bytes": plane_bytes,
                   "static_plane_end_exclusive": static_end,
                   "far_service_bytes": far, "product_cold_bytes": cold,
                   "mapped_total_bytes": total},
        "lower_anchor": {"kind": "static-end-derived",
                         "first_tenant_start": static_end,
                         "last_tenant_end_exclusive": lower_end,
                         "largest_contiguous_hole_bytes": lower_hole,
                         "moves_when_static_plane_grows": True},
        "upper_anchor": {"kind": "bank-end-derived",
                         "first_tenant_start": upper_start,
                         "last_tenant_end_exclusive": COMPOSED.BANK2_END,
                         "largest_contiguous_hole_bytes": upper_hole,
                         "moves_when_static_plane_grows": False},
        "winner": "bank-end-derived",
        "reason": ("equal contiguous capacity; upper anchor maximizes current "
                   "separation and does not churn on static-plane-only growth"),
    }


def probe_child() -> None:
    setup_child()
    # The producer selects this same ownership branch later in its configure
    # closure.  Force only that branch here; no compiler or linker is invoked.
    script = PRODUCT.linker_script(ownership_opt_in=True)
    far_at = ("AT((0x00030000 - SIZEOF(.lisp65_c2_mapped_product_cold) - "
              "SIZEOF(.lisp65_c2_mapped_far_service)))")
    cold_at = ("AT((0x00030000 - "
               "SIZEOF(.lisp65_c2_mapped_product_cold)))")
    require(script.count(far_at) == script.count(cold_at) == 1
            and "AT(0x0002b8b2)" not in script
            and "AT(0x0002be8d)" not in script
            and script.count("LOADADDR(.lisp65_c2_mapped_far_service)") >= 2
            and script.count("LOADADDR(.lisp65_c2_mapped_product_cold)") >= 3,
            "real r9 linker consumer did not materialize structural LMAs")
    PROBE.write_text(script, encoding="utf-8")
    value = {"status": "PASS: REAL LINKER CONSUMES DERIVED UPPER ANCHOR",
        "linker_script": bind(PROBE), "far_expression": far_at,
        "product_cold_expression": cold_at,
        "historical_tenant_LMA_literals_absent": True,
        "copy_source_symbols": sorted(LOAD_SYMBOLS),
        "mutations": {"fixed_far_LMA": "rejected",
                      "fixed_product_cold_LMA": "rejected",
                      "lower_anchor_substitution": "rejected"}}
    PROBE_RECEIPT.write_bytes(canonical(value))
    print("v1.7 Block3 r9: LINKER PROBE PASS anchor=bank2-top")


def preflight() -> None:
    require(not any(path.exists() for path in
                    (BUILD, PREFLIGHT, RECEIPT, REPORT)),
            "Block3 r9 is one-shot")
    auth = authority()
    r8 = load(R8_RECEIPT); red = load(MEDIA_RED)
    require(r8["status"] == "PASS: V1.7 IDE IDLE BLINK R8 FINAL WORLD GREEN"
            and red["status"].startswith("FIRST RED: BLOCK3")
            and red["accounting"]["WPLTO_runs"] == 0,
            "r9 predecessor evidence drift")
    source = R8_PREFLIGHT / "setup-owned/static-plane/narrow-static"
    setup_plane().parent.mkdir(parents=True)
    shutil.copytree(source, setup_plane())
    run([sys.executable, str(DRIVER), "_probe"], "r9 real-linker preflight")
    pricing = price(); probe = load(PROBE_RECEIPT)
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-08-26",
        "status": "PASS: BLOCK3 R9 COMPOSED BANK2 LINK ARMED 0/1",
        "authority": auth, "r8_pair": {"ELF": bind(R8_ELF),
                                         "PRG": bind(R8_PRG)},
        "media_First_Red": bind(MEDIA_RED), "anchor_price": pricing,
        "real_linker_projection": probe,
        "static_plane": bind(setup_plane() /
                             "v6-semantics/bank2-static-code.bin"),
        "static_owners": static_images(),
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "scope_runs": 0, "qualification_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Link-free placement preflight; media/device closed."}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v1.7 Block3 r9: PREFLIGHT PASS anchor=bank2-top WPLTO=0 link=0")


def run_child(action: str) -> dict[str, Any]:
    output = run([sys.executable, str(DRIVER), action], f"r9 child {action}")
    return {"action": action, "status": "PASS",
            "witness": " ".join(output.split())}


def profile_build_ids() -> tuple[int, int]:
    left = R8_PROFILE.read_bytes(); right = PROFILE.read_bytes()
    old_root = R8_BUILD.relative_to(ROOT).as_posix().encode()
    new_root = BUILD.relative_to(ROOT).as_posix().encode()
    require(left.replace(old_root, b"<BUILD>")
            == right.replace(new_root, b"<BUILD>"),
            "r9 compiler profile changed beyond output-root identity")
    return (int(hashlib.sha256(left).hexdigest()[:8], 16),
            int(hashlib.sha256(right).hexdigest()[:8], 16))


def changed_offsets(left: bytes, right: bytes) -> list[int]:
    require(len(left) == len(right), "r8/r9 section size changed")
    return [index for index, pair in enumerate(zip(left, right))
            if pair[0] != pair[1]]


def program_headers(path: Path) -> list[dict[str, int]]:
    output = run([str(READOBJ), "--program-headers", str(path)],
                 "read program headers")
    rows = []
    for block in output.split("  ProgramHeader {")[1:]:
        def field(name: str) -> int:
            match = re.search(rf"^    {name}: (0x[0-9A-F]+|[0-9]+)$",
                              block, re.MULTILINE)
            require(match is not None, f"program-header field absent: {name}")
            return int(match.group(1), 0)
        rows.append({"offset": field("Offset"),
                     "virtual_address": field("VirtualAddress"),
                     "physical_address": field("PhysicalAddress"),
                     "file_bytes": field("FileSize"),
                     "memory_bytes": field("MemSize")})
    require(rows, "ELF program-header population absent")
    return rows


def difference() -> dict[str, Any]:
    old = ElfTruth.read(R8_ELF, llvm_readobj=READOBJ, include_section_data=True)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    require([asdict(row) for row in old.sections]
            == [asdict(row) for row in new.sections],
            "r9 VMA/section geometry changed")
    require([asdict(row) for row in old.relocations]
            == [asdict(row) for row in new.relocations],
            "r9 relocation geometry changed")
    old_symbols = {row.name: asdict(row) for row in old.symbols}
    new_symbols = {row.name: asdict(row) for row in new.symbols}
    require(old_symbols.keys() == new_symbols.keys(), "r9 symbol population changed")
    symbol_changes = []
    for name in sorted(old_symbols):
        if old_symbols[name] == new_symbols[name]:
            continue
        require(name in LOAD_SYMBOLS
                and {key for key in old_symbols[name]
                     if old_symbols[name][key] != new_symbols[name][key]}
                    == {"value"},
                f"r9 unexpected symbol change: {name}")
        symbol_changes.append({"name": name,
                               "before": old_symbols[name]["value"],
                               "after": new_symbols[name]["value"]})
    require({row["name"] for row in symbol_changes} == LOAD_SYMBOLS,
            "r9 LOADADDR symbol difference incomplete")

    old_id, new_id = profile_build_ids()
    old_id_bytes = old_id.to_bytes(4, "little")
    new_id_bytes = new_id.to_bytes(4, "little")
    changed_sections = []
    pairs: Counter[tuple[int, int]] = Counter()
    for section in old.sections:
        if section.bytes == 0 or section.section_type == "SHT_NOBITS":
            continue
        left = old.section_bytes(section.name)
        right = new.section_bytes(section.name)
        offsets = changed_offsets(left, right)
        if not offsets:
            continue
        pairs.update((left[index], right[index]) for index in offsets)
        changed_sections.append({"section": section.name,
            "changed_offsets": offsets,
            "changes": [{"offset": index, "before": left[index],
                         "after": right[index]} for index in offsets]})

    allowed_build_sections = {
        ".text", ".lisp65_boot_bank3_stage", ".lisp65_rt_rtov_catalog",
        ".lisp65_rt_rtov_record", ".lisp65_rt_island_00"}
    by_name = {row["section"]: row for row in changed_sections}
    for name in allowed_build_sections:
        row = by_name.get(name)
        require(row is not None and len(row["changes"]) == 4
                and bytes(item["before"] for item in row["changes"])
                    == old_id_bytes
                and bytes(item["after"] for item in row["changes"])
                    == new_id_bytes,
                f"r9 build-ID projection drift: {name}")
    require(set(by_name) == allowed_build_sections | {".lisp65_rt_l65e"},
            "r9 emitted content changed outside build identity family")
    l65e = by_name[".lisp65_rt_l65e"]
    require(len(l65e["changes"]) == 6,
            "r9 L65E build-ID/CRC difference is not six bytes")
    old_l65e = old.section_bytes(".lisp65_rt_l65e")
    new_l65e = new.section_bytes(".lisp65_rt_l65e")
    old_table = ERROR_TEXT.find_table(old_l65e, old_id, 1)
    new_table = ERROR_TEXT.find_table(new_l65e, new_id, 1)
    require(old_table["offset"] == new_table["offset"]
            and old_table["size"] == new_table["size"] == 803,
            "r9 L65E table geometry drift")

    left_prg = R8_PRG.read_bytes(); right_prg = PRG.read_bytes()
    prg_offsets = changed_offsets(left_prg, right_prg)
    prg_pairs = Counter((left_prg[index], right_prg[index])
                        for index in prg_offsets)
    require(len(prg_offsets) == sum(len(row["changes"])
                                    for row in changed_sections)
            and prg_pairs == pairs,
            "r9 PRG difference differs from attributed allocated-section bytes")

    old_ph = program_headers(R8_ELF); new_ph = program_headers(ELF)
    require(len(old_ph) == len(new_ph), "r9 program-header population changed")
    ph_changes = []
    for index, (left, right) in enumerate(zip(old_ph, new_ph)):
        if left == right:
            continue
        fields = {key for key in left if left[key] != right[key]}
        require(fields <= {"physical_address"}
                and left["virtual_address"] == right["virtual_address"]
                and left["virtual_address"] in (0x78B2, 0x7E8D),
                f"r9 program-header difference outside mapped LMA family: {index}")
        ph_changes.append({"index": index, "before": left, "after": right,
                           "classification": "mapped-tenant-LMA"})
    require({row["before"]["virtual_address"] for row in ph_changes}
            == {0x78B2, 0x7E8D},
            "r9 mapped program-header LMA difference incomplete")

    return {"status": "PASS: ALL R8/R9 PRODUCT DIFFERENCES ATTRIBUTED",
        "section_geometry_unchanged": True, "relocations_unchanged": True,
        "load_symbol_changes": symbol_changes,
        "program_header_changes": ph_changes,
        "allocated_section_changes": changed_sections,
        "allocated_changed_bytes": sum(len(row["changes"])
                                       for row in changed_sections),
        "PRG_changed_bytes": len(prg_offsets),
        "classification": {"mapped_tenant_LMA_symbols": len(symbol_changes),
            "mapped_tenant_program_headers": len(ph_changes),
            "profile_build_id_projection_bytes": 20,
            "profile_derived_L65E_bytes": 6, "unattributed_bytes": 0}}


def artifacts() -> dict[str, Any]:
    return {"ELF": bind(ELF), "PRG": bind(PRG),
        "map": bind(BUILD / "wplto/lisp65-c2-substitution-linked.prg.map"),
        "lto": bind(BUILD / "wplto/lisp65-c2-substitution-linked.prg.lto.o")}


def red_difference() -> dict[str, Any]:
    old = ElfTruth.read(R8_ELF, llvm_readobj=READOBJ, include_section_data=True)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    section_rows = []
    allocated_bytes = 0
    metadata_bytes = 0
    for section in old.sections:
        if section.bytes == 0 or section.section_type == "SHT_NOBITS":
            continue
        left = old.section_bytes(section.name)
        right = new.section_bytes(section.name)
        require(len(left) == len(right), f"r9 section size drift: {section.name}")
        count = sum(a != b for a, b in zip(left, right))
        if not count:
            continue
        row = {"section": section.name, "changed_bytes": count,
               "section_bytes": len(left),
               "allocated": "SHF_ALLOC" in section.flags}
        section_rows.append(row)
        if row["allocated"]:
            allocated_bytes += count
        else:
            metadata_bytes += count
    symbol_changes = sum(left != right
                         for left, right in zip(old.symbols, new.symbols))
    relocation_changes = sum(left != right for left, right in
                             zip(old.relocations, new.relocations))
    left_prg = R8_PRG.read_bytes(); right_prg = PRG.read_bytes()
    require(len(left_prg) == len(right_prg), "r9 PRG size changed")
    prg_changes = sum(a != b for a, b in zip(left_prg, right_prg))
    old_lines = R8_PROFILE.read_text(encoding="utf-8").splitlines()
    new_lines = PROFILE.read_text(encoding="utf-8").splitlines()
    old_root = R8_BUILD.relative_to(ROOT).as_posix()
    new_root = BUILD.relative_to(ROOT).as_posix()
    normalized_old = [line.replace(old_root, "<BUILD>") for line in old_lines]
    normalized_new = [line.replace(new_root, "<BUILD>") for line in new_lines]
    profile_diff = []
    for before, after in zip(normalized_old, normalized_new):
        if before != after:
            profile_diff.append({"before": before, "after": after})
    require(len(normalized_old) == len(normalized_new)
            and len(profile_diff) == 1
            and profile_diff[0]["before"].startswith("linker_sha256=")
            and profile_diff[0]["after"].startswith("linker_sha256="),
            "r9 normalized profile difference is not linker-only")
    old_id = int(hashlib.sha256(R8_PROFILE.read_bytes()).hexdigest()[:8], 16)
    new_id = int(hashlib.sha256(PROFILE.read_bytes()).hexdigest()[:8], 16)
    return {"status": "RED: R8/R9 DIFFERENCE EXCEEDS AUTHORIZED FAMILY",
        "normalized_profile_differences": profile_diff,
        "profile_build_id": {"before": f"0x{old_id:08x}",
                             "after": f"0x{new_id:08x}"},
        "PRG_changed_bytes": prg_changes,
        "changed_symbols": symbol_changes,
        "changed_relocations": relocation_changes,
        "allocated_section_changed_bytes": allocated_bytes,
        "ELF_metadata_section_changed_bytes": metadata_bytes,
        "changed_sections": section_rows,
        "authorized_direct_family": {
            "mapped_LOADADDR_symbols": sorted(LOAD_SYMBOLS),
            "build_ID_projection_bytes": 20,
            "derived_L65E_bytes": 6},
        "unexonerated": True,
        "reason": ("the linker identity changed the LTO product world far "
                   "beyond direct LMA/build-ID/CRC bytes; no counterfactual "
                   "second link is authorized")}


def record_red() -> None:
    require(INVOCATION.is_file() and ELF.is_file() and PRG.is_file()
            and not POSTLINK.exists() and not RECEIPT.exists(),
            "r9 Final-Red lifecycle drift")
    actual = BUILD / "static-plane/narrow-static/v6-semantics"
    expected = BUILD / "wplto/fresh-c2-lite-prelink-gates/v6-semantics"
    c2d = actual / "initial.c2d-v6.bin"
    require(c2d.is_file() and expected.is_dir()
            and not (expected / "initial.c2d-v6.bin").exists(),
            "r9 output-root First Red evidence drift")
    geometry = composed()
    value = {"format": FORMAT + "-final-red", "recorded_on": "2026-08-26",
        "status": "FINAL RED: R9 GEOMETRY GREEN; POSTLINK WORLD UNQUALIFIED",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION), "artifacts": artifacts(),
        "composed_bank2": geometry, "placement_defect": False,
        "postlink_consumer_red": {
            "family": "phase/output ownership; bound output not consumed",
            "expected_consumer_root": expected.relative_to(ROOT).as_posix(),
            "observed_materialization_root": actual.relative_to(ROOT).as_posix(),
            "candidate_c2d": bind(c2d),
            "expected_c2d_absent": True,
            "mechanism": ("the card-3 V6 wrapper redirects the caller-owned "
                          "output while the inherited consumer reads its own root"),
            "product_link_completed_before_red": True},
        "difference": red_difference(),
        "pair_disposition": "FROZEN-FIRST-RED-EVIDENCE-NOT-CANDIDATE",
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 0, "qualification_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": ("Placement evidence only. Product pair, Scope, "
                        "Qualification, media and hardware are not green."),
        "next": ("review disposition of the consumer rebind and the "
                 "build-ID-mediated difference family; no retry authorized")}
    FINAL_RED.write_bytes(canonical(value))
    print("v1.7 Block3 r9: FINAL RED RECORDED geometry=GREEN link=1 "
          "scope=0 qualification=0 media=0 device=0")


def check_red() -> None:
    value = load(FINAL_RED)
    require(value["status"] ==
                "FINAL RED: R9 GEOMETRY GREEN; POSTLINK WORLD UNQUALIFIED"
            and value["authority"] == authority()
            and value["preflight"] == bind(PREFLIGHT_RECEIPT)
            and value["invocation"] == bind(INVOCATION)
            and value["artifacts"] == artifacts()
            and value["composed_bank2"] == composed()
            and value["difference"] == red_difference()
            and value["pair_disposition"] ==
                "FROZEN-FIRST-RED-EVIDENCE-NOT-CANDIDATE"
            and value["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_links": 1, "scope_runs": 0,
                "qualification_runs": 0, "media_builds": 0,
                "device_contacts": 0},
            "r9 Final-Red receipt drift")
    print("v1.7 Block3 r9: FINAL RED VERIFIED geometry=GREEN "
          "pair=NOT-CANDIDATE WPLTO=1 link=1")


def link() -> None:
    pre = load(PREFLIGHT_RECEIPT)
    require(pre["status"] == "PASS: BLOCK3 R9 COMPOSED BANK2 LINK ARMED 0/1"
            and not BUILD.exists() and not INVOCATION.exists(),
            "r9 link lifecycle drift")
    INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "budget": {"WPLTO_runs": 1, "product_links": 1}}))
    process = run_child("_produce")
    geometry = composed()
    diff = difference()
    value = {"format": FORMAT + "-postlink", "recorded_on": "2026-08-26",
        "status": "PASS: R9 LINK COMPOSED AND FULLY ATTRIBUTED",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION), "r8_pair": {"ELF": bind(R8_ELF),
            "PRG": bind(R8_PRG)}, "artifacts": artifacts(),
        "process": process, "composed_bank2": geometry,
        "difference": diff,
        "compiler_consumption": R8.compiler_consumption(),
        "final_ELF_extent_immediates": R8.extent_immediates(ELF, 52230, 46043),
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 0, "qualification_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Post-link attribution only; media/device closed."}
    POSTLINK.write_bytes(canonical(value))
    print("v1.7 Block3 r9: LINK PASS composed=disjoint unattributed=0")


def frozen_pair() -> dict[str, Any]:
    return {"ELF": bind(ELF), "PRG": bind(PRG)}


def render_report(value: dict[str, Any]) -> str:
    bank = value["postlink_value"]["composed_bank2"]
    diff = value["postlink_value"]["difference"]
    pair = value["frozen_pair_after"]
    owners = "\n".join(
        f"- `{row['owner']}`: `${row['start']:06X}..${row['end_exclusive']:06X}` "
        f"({row['bytes']:,} bytes)" for row in bank["owners"])
    return f"""# v1.7 Block 3 composed Bank-2 r9 report

Status: **{value['status']}**

The r9 link keeps every mapped CPU VMA unchanged and derives both MAP-copy
source LMAs from the Bank-2 end and the final section sizes.  Product-Cold
ends at `$030000`; Far-Service ends exactly where Product-Cold begins.  No
tenant address literal is an authority.

## Composed ownership

{owners}

All intervals are disjoint.  The largest contiguous hole is
**{bank['largest_contiguous_hole']['bytes']:,} bytes** at
`${bank['largest_contiguous_hole']['start']:06X}..${bank['largest_contiguous_hole']['end_exclusive']:06X}`.
The aggregate-free figure ({bank['aggregate_free_bytes']:,}) is informational;
placement capacity is the largest hole.

## r8 to r9 attribution

Every section VMA/size and every relocation is unchanged.  The four LOADADDR
symbols and the two mapped program-header LMAs move.  The only allocated
product-byte changes are {diff['classification']['profile_build_id_projection_bytes']}
profile build-ID bytes plus {diff['classification']['profile_derived_L65E_bytes']}
derived L65E bytes; PRG and allocated-section counts agree.  Unattributed
bytes: **{diff['classification']['unattributed_bytes']}**.

## Qualification and accounting

Scope and Qualification pass read-only over the frozen pair:

- ELF: `{pair['ELF']['sha256']}`
- PRG: `{pair['PRG']['sha256']}`

Exactly one WPLTO, one product link, one Scope and one Qualification run were
consumed.  No medium was built and no device was contacted.  Media remains
closed pending review of this r9 pair and the permanent composed gate.
"""


def qualify() -> None:
    post = load(POSTLINK)
    require(post["status"] == "PASS: R9 LINK COMPOSED AND FULLY ATTRIBUTED"
            and not RECEIPT.exists() and not SCOPE.exists()
            and not ACCEPTANCE.exists(), "r9 qualification lifecycle drift")
    before = frozen_pair()
    processes = [run_child("_scope"), run_child("_accept")]
    scope = load(SCOPE); acceptance = load(ACCEPTANCE)
    after = frozen_pair()
    require(before == after and scope.get("status") == "PASS"
            and acceptance.get("status") == "PASS",
            "r9 read-only qualification tail red")
    final_geometry = composed()
    require(final_geometry == post["composed_bank2"],
            "r9 composed geometry changed during qualification")
    value = {"format": FORMAT, "recorded_on": "2026-08-26",
        "status": STATUS, "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "postlink": bind(POSTLINK),
        "postlink_value": post, "frozen_pair_before": before,
        "frozen_pair_after": after,
        "scope": {"status": scope["status"], "receipt": bind(SCOPE)},
        "qualification": {"status": acceptance["status"],
                          "receipt": bind(ACCEPTANCE)},
        "processes": processes,
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "qualification_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "media_authorized": False,
        "claim_limit": "Host/product r9 only; media and device remain closed."}
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(render_report(value), encoding="utf-8")
    print("v1.7 Block3 r9: QUALIFICATION PASS scope=PASS qualification=PASS")


def check() -> None:
    value = load(RECEIPT)
    require(value["status"] == STATUS
            and value["authority"] == authority()
            and value["frozen_pair_before"] == value["frozen_pair_after"]
                == frozen_pair()
            and value["postlink_value"] == load(POSTLINK)
            and value["postlink_value"]["composed_bank2"] == composed()
            and value["postlink_value"]["difference"] == difference()
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["attempt_accounting"]["product_links"] == 1
            and value["attempt_accounting"]["media_builds"] == 0
            and REPORT.read_text(encoding="utf-8") == render_report(value),
            "r9 receipt/report drift")
    print("v1.7 Block3 r9: CHECK PASS disjoint=all largest-hole="
          f"{value['postlink_value']['composed_bank2']['largest_contiguous_hole']['bytes']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "link", "record-red", "check-red", "qualify", "check",
        "_probe", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    install()
    {"preflight": preflight, "link": link, "record-red": record_red,
     "check-red": check_red,
     "qualify": qualify,
     "check": check, "_probe": probe_child, "_produce": R8.produce_child,
     "_scope": R8.scope_child, "_accept": R8.acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.7 Block3 r9: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
