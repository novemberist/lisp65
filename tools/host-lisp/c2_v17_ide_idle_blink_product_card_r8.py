#!/usr/bin/env python3
"""Run the one authorized card-3 r8 link over candidate header consumption."""

from __future__ import annotations

from dataclasses import asdict
import argparse
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

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_lite_v6_first_product_link as ATTIC  # noqa: E402
import c2_v17_ide_idle_blink_product_card as CARD  # noqa: E402
import error_text_table as ERROR_TEXT  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
DEAD_RECEIPT = ARCH / (
    "c2.3-v1.7-ide-idle-blink-header-rebind-resume-final-red.json")
BUILD = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-card-r8"
PREFLIGHT = ROOT / "build/c2.3/v1.7-ide-idle-blink-product-preflight-r8"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
POSTLINK = BUILD / "postlink-observation.json"
RECEIPT = ARCH / "c2.3-v1.7-ide-idle-blink-product-card-r8-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.7-ide-idle-blink-product-card-r8-final-red.json"
REPORT = ROOT / "docs/planning/v1.7.0-ide-idle-blink-card-r8-report.md"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "d4faacdb"
FORMAT = "lisp65-c2-v17-ide-idle-blink-product-card-r8-v1"
STATUS = "PASS: V1.7 IDE IDLE BLINK R8 FINAL WORLD GREEN"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
OLD_BUILD = CARD.BUILD
OLD_ELF = CARD.ELF
OLD_PRG = CARD.PRG
OLD_PROFILE = OLD_BUILD / "wplto/resolved-profile.txt"
PROFILE = BUILD / "wplto/resolved-profile.txt"
SCOPE = BUILD / "owner-scope-result.json"
ACCEPTANCE = BUILD / "artifact-acceptance.json"
FUNCTIONS = ("c2_stream_phase_02b", "c2_stream_phase_03b")
EXPECTED_OLD = {"ELF":
    "c5aaccf702a655223b540e18ccb58176aa500baa37554a0d610c07c2381b6c52",
    "PRG": "7345e84de9e30eae3428ff2444de1c626b873109abb0f2c9dc4c6a35f03ce5d0"}


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


def authority() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("card-3 r8 link authority", "one new wplto",
                  "one new product link", "unchanged card sources",
                  "every final-elf byte difference", "0xcc06",
                  "scope and qualification", "media and device contact remain closed"):
        require(token in text, f"r8 link authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def r8_setup_plane(preflight: Path = PREFLIGHT) -> Path:
    return preflight / "setup-owned/static-plane/narrow-static"


def install() -> None:
    CARD.BUILD = BUILD; CARD.PREFLIGHT = PREFLIGHT
    CARD.ELF = ELF; CARD.PRG = PRG; CARD.RECEIPT = RECEIPT
    CARD.DRIVER = DRIVER; CARD.AUTHORIZATION = AUTHORIZATION
    CARD.FORMAT = FORMAT; CARD.STATUS = STATUS
    CARD.authority = authority; CARD.setup_plane = r8_setup_plane
    CARD.configure()


def old_pair() -> dict[str, dict[str, Any]]:
    result = {"ELF": bind(OLD_ELF), "PRG": bind(OLD_PRG)}
    require({name: row["sha256"] for name, row in result.items()} == EXPECTED_OLD,
            "dead r7 pair identity drift")
    return result


def predecessor() -> dict[str, Any]:
    value = load(DEAD_RECEIPT)
    require(value["status"] ==
                "RESUME RED: FROZEN CARD3 PAIR DEPENDS ON STALE STATIC EXTENT"
            and value["pair_disposition"] == "DEAD"
            and value["new_product_link_authorized"] is False
            and value["final_ELF_dependency"]["historical_value"] == 46043
            and value["final_ELF_dependency"]["candidate_value"] == 52230,
            "r8 dead-pair predecessor drift")
    return value


def source_closure() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for line in OLD_PROFILE.read_text(encoding="utf-8").splitlines():
        if not line.startswith("input_sha256="):
            continue
        name, digest = line.removeprefix("input_sha256=").rsplit(":", 1)
        path = ROOT / name
        current = bind(path)
        require(current["sha256"] == digest,
                f"card source changed since dead r7: {name}")
        rows.append({"path": name, "sha256": digest, "bytes": current["bytes"]})
    require(len(rows) >= 60, "r7 compiler source closure is incomplete")
    return {"status": "PASS: R8 CARD SOURCES IDENTICAL TO DEAD R7",
            "source_count": len(rows), "sources": rows,
            "r7_resolved_profile": bind(OLD_PROFILE)}


def macro_value(path: Path) -> int:
    values = re.findall(
        rb"^#define LISP65_C2_LITE_STATIC_CODE_BYTES ([0-9]+)UL$",
        path.read_bytes(), re.MULTILINE)
    require(len(values) == 1, f"static extent ambiguous: {path}")
    return int(values[0])


def projected_consumers(target: Path) -> dict[str, Any]:
    CARD.bind_current_plane(target)
    header, header_binding, code_bytes = (
        PRODUCT.resolved_compiler_consumed_static_header())
    require(header is not None and header_binding is not None
            and code_bytes is not None and macro_value(header) == code_bytes,
            "r8 candidate compiler header resolver red")
    bank2 = target / "v6-semantics/bank2-static-code.bin"
    require(code_bytes == bank2.stat().st_size == 52230,
            "r8 candidate compiler plane extent drift")
    rows = []
    for stem in ("resident-island-seed", "lisp65-c2-substitution-linked"):
        assertion = BUILD / "wplto" / (stem + ".compiler-input-assert.h")
        rows.append({"target": stem + ".prg",
            "force_include_path": header.relative_to(ROOT).as_posix(),
            "assertion_path": assertion.relative_to(ROOT).as_posix(),
            "derived_value": code_bytes})
    return {"status": "PASS: R8 BOTH REAL CONSUMERS PROJECT CANDIDATE HEADER",
        "candidate_plane": bind(bank2), "candidate_header": header_binding,
        "derived_value": code_bytes, "consumers": rows}


def preflight() -> None:
    require(not any(path.exists() for path in
                    (BUILD, PREFLIGHT, RECEIPT, FINAL_RED, REPORT)),
            "card-3 r8 is one-shot")
    predecessor(); auth = authority(); old = old_pair(); closure = source_closure()
    target = r8_setup_plane()
    static = CARD.install_current_plane(target)
    projection = projected_consumers(target)
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-08-26",
        "status": "PASS: CARD3 R8 HEADER-CORRECT LINK ARMED 0/1",
        "authority": auth, "dead_pair": old,
        "dead_pair_receipt": bind(DEAD_RECEIPT),
        "unchanged_card_sources": closure,
        "candidate_static_plane": static,
        "compiler_projection": projection,
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "scope_runs": 0, "qualification_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Link-free r8 preflight only; media/device closed."}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v1.7 IDE idle/blink r8: PREFLIGHT PASS card=0/1 WPLTO=0 link=0")


def setup_child() -> tuple[Any, dict[str, Any], dict[str, object]]:
    core, activation, product_cold = CARD.BASE.configure_clean_stack()
    target = r8_setup_plane()
    static = CARD.bind_current_plane(target)
    core.bind_paths_only(BUILD, PREFLIGHT)
    old_paths = (core.PROJECTED_OWNERSHIP, core.PROJECTED_FULL_MAP)
    core.PROJECTED_OWNERSHIP = PREFLIGHT / "projected-ownership-contract.json"
    core.PROJECTED_FULL_MAP = PREFLIGHT / "projected-full-map-authority.json"
    try:
        core.write_projections()
    finally:
        core.PROJECTED_OWNERSHIP, core.PROJECTED_FULL_MAP = old_paths
    require(static["consumer_observed_bytes"] == 52230,
            "r8 setup consumed another Bank-2 extent")
    # Product manifests carry repository-relative paths.  The card-3 setup
    # used the copied plane as their root, which made the live linked gate
    # look below ``target/build/...``.  Bind the real consumer to the root in
    # which those materialized paths actually live.
    CARD.CANDIDATE.ZERO_LITERAL.LINKED_PRODUCT_INVENTORY = (
        target / "product/substitution-artifacts.json", ROOT)
    return core, activation, product_cold


def produce_child() -> None:
    CARD.child_binding_gate()
    core, _activation, _cold = setup_child()
    CARD.install_final_v6_consumer(record=True)
    raise SystemExit(core.PRODUCT.BASE.produce_child())


def scope_child() -> None:
    CARD.child_binding_gate()
    core, _activation, _cold = setup_child()
    CARD.install_final_v6_consumer(record=False)
    raise SystemExit(core.PRODUCT.BASE.scope_child())


def acceptance_child() -> None:
    CARD.child_binding_gate()
    core, _activation, _cold = setup_child()
    CARD.install_final_v6_consumer(record=False)
    CARD.os.environ["LISP65_R1_ACCEPTANCE_RESULT"] = str(
        CARD.BASE.ACCEPTANCE_RESULT)
    raise SystemExit(core.PRODUCT.BASE.acceptance_child())


def run_child(action: str) -> dict[str, Any]:
    run = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(run.returncode == 0, f"card-3 r8 child {action} red:\n{run.stdout}")
    return {"action": action, "status": "PASS",
            "witness": " ".join(run.stdout.split())}


def artifacts() -> dict[str, dict[str, Any]]:
    return {"ELF": bind(ELF), "PRG": bind(PRG),
        "map": bind(BUILD / "wplto/lisp65-c2-substitution-linked.prg.map"),
        "lto": bind(BUILD / "wplto/lisp65-c2-substitution-linked.prg.lto.o")}


def compiler_consumption() -> dict[str, Any]:
    target = r8_setup_plane()
    expected_header = bind(target / "c2_lite_static_plane.h")
    rows = []
    for stem in ("resident-island-seed", "lisp65-c2-substitution-linked"):
        path = BUILD / "wplto" / (stem + ".prg.compiler-input-consumption.json")
        value = load(path)
        require(value["format"] == "lisp65-real-compiler-input-consumption-v2"
                and value["status"] ==
                    "passed-bound-candidate-header-consumed"
                and value["bound_header"] == expected_header
                and value["materialized_header"] == expected_header
                and value["consumed_value"] == value["materialized_value"]
                    == 52230
                and value["actual_force_include_flags"][1]
                    == expected_header["path"],
                f"r8 real compiler consumption red: {stem}")
        rows.append({"target": stem + ".prg", "receipt": bind(path),
            "header": value["materialized_header"],
            "value": value["materialized_value"],
            "actual_force_include_flags": value["actual_force_include_flags"]})
    return {"status": "PASS: BOTH R8 COMPILERS CONSUMED CANDIDATE EXTENT",
            "consumers": rows, "value": 52230}


def positions(body: bytes, pattern: bytes) -> list[int]:
    return [index for index in range(len(body)) if body.startswith(pattern, index)]


def extent_immediates(elf: Path, expected: int, forbidden: int) -> dict[str, Any]:
    generated = elf.parent / "generated-product-sources/c2-stream-decoder.c"
    source = generated.read_text(encoding="utf-8")
    truth = ElfTruth.read(elf, llvm_readobj=CARD.BASE.READOBJ,
                          include_section_data=True)
    rows = []
    for name in FUNCTIONS:
        definition = CARD.V6.c_function_definition(source, name)
        require(definition.count("LISP65_C2_LITE_STATIC_CODE_BYTES") == 1,
                f"r8 extent source consumer drift: {name}")
        symbol = truth.symbol(name); body = truth.section_bytes(symbol.section)
        high = positions(body, bytes((0xC9, (expected >> 8) & 0xFF)))
        low = positions(body, bytes((0xC9, expected & 0xFF)))
        old_high = positions(body, bytes((0xC9, (forbidden >> 8) & 0xFF)))
        old_low = positions(body, bytes((0xC9, forbidden & 0xFF)))
        require(len(high) == len(low) == 1 and 0 < low[0] - high[0] <= 16
                and not old_high and not old_low,
                f"r8 final ELF did not consume candidate extent: {name}")
        rows.append({"function": name, "section": symbol.section,
            "section_index": symbol.section_index, "bytes": symbol.bytes,
            "candidate_value": expected, "candidate_hex": f"0x{expected:04x}",
            "high_compare_offset": high[0], "low_compare_offset": low[0],
            "historical_compare_offsets": []})
    return {"status": "PASS: FINAL ELF CARRIES CANDIDATE EXTENT IMMEDIATES",
            "value": expected, "historical_value_absent": forbidden,
            "functions": rows}


def diff_offsets(before: bytes, after: bytes) -> list[int]:
    require(len(before) == len(after), "r7/r8 section size changed")
    return [index for index, (left, right) in enumerate(zip(before, after))
            if left != right]


def elf_difference() -> dict[str, Any]:
    old = ElfTruth.read(OLD_ELF, llvm_readobj=CARD.BASE.READOBJ,
                        include_section_data=True)
    new = ElfTruth.read(ELF, llvm_readobj=CARD.BASE.READOBJ,
                        include_section_data=True)
    old_geometry = [asdict(row) for row in old.sections]
    new_geometry = [asdict(row) for row in new.sections]
    require(old_geometry == new_geometry, "r8 ELF section geometry differs from r7")
    require([asdict(row) for row in old.symbols]
                == [asdict(row) for row in new.symbols],
            "r8 ELF symbol geometry differs from r7")
    require([asdict(row) for row in old.relocations]
                == [asdict(row) for row in new.relocations],
            "r8 ELF relocation geometry differs from r7")
    profile_before = OLD_PROFILE.read_bytes()
    profile_after = PROFILE.read_bytes()
    old_root = OLD_BUILD.relative_to(ROOT).as_posix().encode()
    new_root = BUILD.relative_to(ROOT).as_posix().encode()
    normalized_before = profile_before.replace(old_root, b"<CARD_BUILD>")
    normalized_after = profile_after.replace(new_root, b"<CARD_BUILD>")
    require(normalized_before == normalized_after,
            "r8 resolved profile changed beyond its output-root identity")
    old_build_id = int(hashlib.sha256(profile_before).hexdigest()[:8], 16)
    new_build_id = int(hashlib.sha256(profile_after).hexdigest()[:8], 16)
    old_build_bytes = old_build_id.to_bytes(4, "little")
    new_build_bytes = new_build_id.to_bytes(4, "little")

    changed = []
    for section in old.sections:
        if section.bytes == 0 or section.section_type == "SHT_NOBITS":
            continue
        left = old.section_bytes(section.name)
        right = new.section_bytes(section.name)
        offsets = diff_offsets(left, right)
        if offsets:
            changed.append({"section": section.name,
                "section_index": section.index, "address": section.address,
                "bytes": section.bytes, "changed_offsets": offsets,
                "changes": [{"offset": at, "before": left[at], "after": right[at]}
                            for at in offsets]})
    by_name = {row["section"]: row for row in changed}
    extent_sections: list[dict[str, Any]] = []
    for name in FUNCTIONS:
        old_symbol = old.symbol(name); new_symbol = new.symbol(name)
        require(old_symbol.section == new_symbol.section,
                f"r8 extent owner section moved: {name}")
        row = by_name[old_symbol.section]
        before = old.section_bytes(old_symbol.section)
        after = new.section_bytes(new_symbol.section)
        section_row = old.section(old_symbol.section)
        symbol_offset = old_symbol.value - section_row.address
        expected_offsets = [index for index in row["changed_offsets"]
                            if symbol_offset <= index
                            < symbol_offset + old_symbol.bytes]
        require(len(expected_offsets) == 2
                and [before[index] for index in expected_offsets]
                    == [0xB3, 0xDB]
                and [after[index] for index in expected_offsets]
                    == [0xCC, 0x06],
                f"r8 extent operand delta is not exactly 0xb3db->0xcc06: {name}")
        extent_sections.append({"function": name,
            "section": old_symbol.section, "changed_offsets": expected_offsets,
            "historical_immediate": "0xb3db",
            "candidate_immediate": "0xcc06"})

    l65e_before = old.section_bytes(".lisp65_rt_l65e")
    l65e_after = new.section_bytes(".lisp65_rt_l65e")
    old_table = ERROR_TEXT.find_table(l65e_before, old_build_id, 1)
    new_table = ERROR_TEXT.find_table(l65e_after, new_build_id, 1)
    require(old_table["offset"] == new_table["offset"]
            and old_table["size"] == new_table["size"] == 803,
            "r8 L65E table geometry drift")
    table_at = int(old_table["offset"])
    l65e_expected = list(range(table_at + 8, table_at + 12)) + [
        table_at + 14, table_at + 15]
    require(by_name[".lisp65_rt_l65e"]["changed_offsets"] == l65e_expected,
            "r8 L65E delta exceeds build ID and its derived table CRC")
    old_table_bytes = (BUILD.parent / "v1.7-ide-idle-blink-product-card-r7"
                       / "wplto/error-text-table.bin").read_bytes()
    new_table_bytes = (BUILD / "wplto/error-text-table.bin").read_bytes()
    require(l65e_before[table_at:table_at + 803] == old_table_bytes
            and l65e_after[table_at:table_at + 803] == new_table_bytes,
            "r8 final L65E bytes diverge from their derived tables")

    build_projection_sections = {
        ".text", ".lisp65_boot_bank3_stage", ".lisp65_rt_rtov_catalog",
        ".lisp65_rt_rtov_record", ".lisp65_rt_island_00"}
    profile_rows: list[dict[str, Any]] = []
    for section in sorted(build_projection_sections):
        row = by_name[section]
        before = old.section_bytes(section); after = new.section_bytes(section)
        offsets = row["changed_offsets"]
        require(len(offsets) == 4
                and bytes(before[index] for index in offsets) == old_build_bytes
                and bytes(after[index] for index in offsets) == new_build_bytes,
                f"r8 profile-build-ID projection drift: {section}")
        profile_rows.append({"section": section, "changed_offsets": offsets,
            "historical_build_id": f"0x{old_build_id:08x}",
            "candidate_build_id": f"0x{new_build_id:08x}"})

    classified = (set(build_projection_sections)
                  | {".lisp65_rt_l65e"}
                  | {row["section"] for row in extent_sections})
    require(set(by_name) == classified
            and sum(len(row["changed_offsets"]) for row in changed) == 30,
            "r8 ELF contains an unattributed byte difference")
    return {"status": "PASS: ALL R7/R8 ELF BYTE DIFFERENCES ATTRIBUTED",
        "section_geometry_identical": True,
        "symbol_geometry_identical": True,
        "relocation_geometry_identical": True,
        "source_world": {
            "normalized_profiles_identical": True,
            "normalization": "only card output-root path replaced",
            "historical_profile": bind(OLD_PROFILE),
            "candidate_profile": bind(PROFILE),
            "historical_build_id": f"0x{old_build_id:08x}",
            "candidate_build_id": f"0x{new_build_id:08x}"},
        "classification": {
            "extent_immediate_bytes": 4,
            "profile_build_id_projection_bytes": 24,
            "profile_derived_L65E_crc_bytes": 2,
            "unattributed_bytes": 0,
            "extent_immediates": extent_sections,
            "profile_build_id_projections": profile_rows,
            "L65E": {"section": ".lisp65_rt_l65e",
                "table_offset": table_at, "table_bytes": 803,
                "build_id_offsets": list(range(table_at + 8, table_at + 12)),
                "crc_offsets": [table_at + 14, table_at + 15],
                "historical_crc16": f"0x{old_table['crc16']:04x}",
                "candidate_crc16": f"0x{new_table['crc16']:04x}",
                "crc_derived_from_complete_table": True}},
        "changed_sections": changed,
        "changed_section_count": len(changed),
        "changed_byte_count": 30,
        "raw_ELF": {"r7": bind(OLD_ELF), "r8": bind(ELF),
            "same_file_bytes": OLD_ELF.stat().st_size == ELF.stat().st_size}}


def inherited_producer_tail() -> dict[str, Any]:
    """Name the inherited non-promotable tail without spending another link."""
    current = load(BUILD / "receipts/wplto-base-result.json")
    previous = load(OLD_BUILD / "receipts/wplto-base-result.json")
    for value in (current, previous):
        require(value["status"] ==
                    "FIRST RED: product-shaped two-region package did not close"
                and value["WPLTO"]["product_completed"] is True
                and value["WPLTO"]["exception"] ==
                    "WPLTOError: linked artifact-profile evidence is absent",
                "r8 inherited producer-tail attribution drift")
    generic = load(BUILD / "wplto/product-substitution-link.json")
    require(generic["status"] == "passed"
            and ELF.is_file() and PRG.is_file(),
            "r8 generic product output is incomplete")
    return {"classification": "inherited non-promotable raw-WPLTO probe tail",
        "same_status_as_dead_r7_world": True,
        "product_completed": True,
        "generic_product_link": bind(
            BUILD / "wplto/product-substitution-link.json"),
        "r7_tail": bind(OLD_BUILD / "receipts/wplto-base-result.json"),
        "r8_tail": bind(BUILD / "receipts/wplto-base-result.json"),
        "additional_WPLTO_or_link_required": False}


def inventory_root_gate() -> dict[str, Any]:
    manifest = r8_setup_plane() / "product/substitution-artifacts.json"
    value = load(manifest)
    paths: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, item in node.items():
                if key == "path" and isinstance(item, str):
                    paths.append(item)
                else:
                    walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(value)
    materialized = [name for name in paths if (ROOT / name).is_file()]
    require(paths and materialized, "candidate product inventory has no materialized paths")
    return {"status": "PASS: CANDIDATE INVENTORY ROOT IS REPOSITORY ROOT",
        "manifest": bind(manifest), "recorded_paths": len(paths),
        "materialized_paths": len(materialized),
        "consumer_binding": {"manifest": manifest.relative_to(ROOT).as_posix(),
            "root": "."}}


def postlink() -> None:
    require(INVOCATION.is_file() and ELF.is_file() and PRG.is_file()
            and not POSTLINK.exists() and not RECEIPT.exists()
            and not SCOPE.exists() and not ACCEPTANCE.exists(),
            "r8 postlink lifecycle drift")
    consumption = compiler_consumption()
    extents = extent_immediates(ELF, 52230, 46043)
    differences = elf_difference()
    value = {"format": FORMAT + "-postlink", "recorded_on": "2026-08-26",
        "status": "PASS: R8 LINK PAIR FULLY ATTRIBUTED AND FROZEN",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION), "dead_pair": old_pair(),
        "artifacts": artifacts(), "producer_tail": inherited_producer_tail(),
        "compiler_consumption": consumption,
        "final_ELF_extent_immediates": extents,
        "ELF_difference": differences,
        "inventory_root": inventory_root_gate(),
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 0, "qualification_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Post-link attribution only; qualification tail not yet run."}
    POSTLINK.write_bytes(canonical(value))
    print("v1.7 IDE idle/blink r8: POSTLINK PASS differences=30 "
          "extent=4 build-id=24 l65e-crc=2 unattributed=0")


def render_report(value: dict[str, Any]) -> str:
    card = value["final_product"]["card3"]
    diff = value["postlink_value"]["ELF_difference"]
    pair = value["frozen_pair_after"]
    host = load(CARD.HOST_RECEIPT)
    emission = host["exact_emission"]
    capacity = host["capacity"]
    card1_bytes = emission["card1_total_bytes"]
    card2_bytes = emission["successor_card2_total_bytes"]
    historical_card2_bytes = emission["historical_card2_total_bytes"]
    card3_bytes = emission["card3_total_bytes"]
    total_bytes = emission["three_card_total_bytes"]
    cursor_blink_bytes = emission["current_cursor_blink_bytes"]
    frame_low_bytes = emission["frame_low_bytes"]
    maximum_object_bytes = emission["maximum_object_bytes"]
    object_rows = "\n".join(
        f"| `{name}` | {size} |"
        for name, size in emission["ide_function_bytes"].items()
    )
    return f"""# v1.7 IDE idle/blink card 3 — r8 report

Status: **{value['status']}**

The one authorized r8 WPLTO/product link consumed the candidate-owned
52,230-byte Bank-2 extent at both real compiler consumers.  The final ELF
carries `0xCC06` in both extent-dependent function sections; the historical
`0xB3DB` value is absent.

## Exact card-3 successor price

The accepted one-name prototype was replaced loudly by the emitted product
shape.  Card 3 adds 13 names / {capacity['card3_name_bytes']} NUL-inclusive
name bytes and leaves **{capacity['free_after_card3']['symbol_slots']} symbol
slots / {capacity['free_after_card3']['namepool_bytes']} name bytes**, or
**{capacity['margin_after_card3']['symbol_slots']} symbol slots /
{capacity['margin_after_card3']['namepool_bytes']} name bytes above the release
floor**.
This is the reviewed card-2 world moving 87 → 74 slots, not hidden freight.

`%frame-low` contributes {emission['frame_low_bytes']} bytes.  The twelve IDE
objects are:

| Object | Emitted bytes |
|---|---:|
{object_rows}

Card 2 contributes **{card2_bytes:,} bytes** in the successor world, not its
historical {historical_card2_bytes:,} bytes: `%cursor-blink` is
{cursor_blink_bytes} instead of 186 bytes after the shared {frame_low_bytes}-byte `%frame-low`
extraction.  The complete arithmetic is therefore
**{card1_bytes:,} + {card2_bytes:,} + {card3_bytes:,} = {total_bytes:,} bytes**.
The largest object is {maximum_object_bytes} bytes, below the 255-byte ceiling.

## Difference attribution

The dead r7 and r8 ELFs have identical section, symbol and relocation
geometry.  Exactly {diff['changed_byte_count']} bytes differ, all accounted
for before qualification:

- {diff['classification']['extent_immediate_bytes']} bytes are the authorized
  `0xB3DB` → `0xCC06` extent-immediate changes.
- {diff['classification']['profile_build_id_projection_bytes']} bytes are the
  deterministic profile build-ID projection caused solely by the r7/r8
  output-root identity in otherwise byte-identical resolved profiles.
- {diff['classification']['profile_derived_L65E_crc_bytes']} bytes are the
  L65E table CRC derived from that table's changed profile build ID.
- {diff['classification']['unattributed_bytes']} bytes remain unexplained.

Card sources and all 70 compiler input contents are unchanged from r7.

## Qualification

Scope and Acceptance both passed read-only over the frozen r8 pair.  Their
before/after identities are equal:

- ELF: `{pair['ELF']['sha256']}`
- PRG: `{pair['PRG']['sha256']}`

The final linked Bank-2 plane occupies
{card['bank2_static_code_bytes']:,} bytes and leaves
{card['bank2_remaining_headroom_bytes']:,} bytes.  The three implementation
cards contribute exactly {card['exact_three_card_object_freight_bytes']:,}
Bank-2 bytes; the post-card name projection is 74 slots / 1,076 name bytes.
No timing claim is made from the historical projection.

## Accounting and claim boundary

Exactly one card, one WPLTO, one product link, one Scope run and one Acceptance
run were consumed.  No media was built and no device was contacted.  Hardware
remains closed pending review of this report.

## Integration closure

The three reviewed r8-tail consumers are converted without another WPLTO,
link or card:

- The v1.26 allocation gate parses the Lisp call tree and proves that both
  `%ide-drain-pending` and `%ide-poll` pass an `ide-step` result into
  `%ide-drain-pending`.  Local-variable spelling is irrelevant; removing the
  real edge is mutationsrot.
- The 139-record public metadata index is regenerated from the 194-entry
  successor IDE artifact.  Public arities are unchanged, and a permanent
  mutation rejects every private `%ide-*` record.
- The twelve private card-3 IDE objects are named explicitly in each consumed
  omission authority.  No wildcard is accepted.  The subsequently exposed
  `%frame-low` omission belongs separately to the historical `v16core` delta
  and is registered as resident Workbench freight.

The complete `make -k check-source` tail then passes **twice consecutively**;
the second run makes no tracked change.  This proves the regenerated living
receipts and metadata are idempotent in the final card-3 world.  The working
tree is clean after the closure commit.
"""


def frozen_pair() -> dict[str, dict[str, Any]]:
    return {"ELF": bind(ELF), "PRG": bind(PRG)}


def validate_final(value: dict[str, Any]) -> None:
    card = value["final_product"]["card3"]
    diff = value["postlink_value"]["ELF_difference"]
    require(value["status"] == STATUS
            and value["frozen_pair_before"] == value["frozen_pair_after"]
            and value["scope"]["status"] == "PASS"
            and value["qualification"]["status"] == "PASS"
            and diff["status"] ==
                "PASS: ALL R7/R8 ELF BYTE DIFFERENCES ATTRIBUTED"
            and diff["classification"]["unattributed_bytes"] == 0
            and value["postlink_value"]["compiler_consumption"]["value"] == 52230
            and card["status"] ==
                "PASS: IDE IDLE/BLINK PROVED THROUGH REAL PRODUCT LINK"
            and value["attempt_accounting"] == {
                "cards_consumed": 1, "WPLTO_runs": 1, "product_links": 1,
                "scope_runs": 1, "qualification_runs": 1,
                "media_builds": 0, "device_contacts": 0},
            "r8 final receipt drift")


def qualify() -> None:
    post = load(POSTLINK)
    require(post["status"] == "PASS: R8 LINK PAIR FULLY ATTRIBUTED AND FROZEN"
            and not RECEIPT.exists() and not FINAL_RED.exists()
            and not SCOPE.exists() and not ACCEPTANCE.exists(),
            "r8 qualification lifecycle drift")
    before = frozen_pair()
    processes = [run_child("_scope"), run_child("_accept")]
    scope = load(SCOPE); acceptance = load(ACCEPTANCE)
    after = frozen_pair()
    require(before == after and scope.get("status") == "PASS"
            and acceptance.get("status") == "PASS",
            "r8 read-only Scope/Qualification tail red")
    semantic = ATTIC.no_runtime_attic_gate(
        ELF, ELF.parent / "generated-product-sources")
    final_product = {"card3": CARD.card3_final_gate()}
    value = {"format": FORMAT, "recorded_on": "2026-08-26",
        "status": STATUS, "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "postlink": bind(POSTLINK),
        "postlink_value": post,
        "frozen_pair_before": before, "frozen_pair_after": after,
        "semantic_no_runtime_attic": semantic,
        "final_product": final_product,
        "scope": {"status": scope["status"], "receipt": bind(SCOPE),
                  "value": scope},
        "qualification": {"status": acceptance["status"],
                          "receipt": bind(ACCEPTANCE), "value": acceptance},
        "processes": processes,
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "qualification_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "media_authorized": False,
        "claim_limit": "Card 3 host/product qualification only; media and device remain closed.",
        "next": "review the r8 card report before any hardware contact"}
    validate_final(value)
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(render_report(value), encoding="utf-8")
    print("v1.7 IDE idle/blink r8: QUALIFICATION PASS scope=PASS "
          "qualification=PASS WPLTO=1 link=1 media=0 device=0")


def check() -> None:
    value = load(RECEIPT)
    validate_final(value)
    require(value["authority"] == authority()
            and value["postlink"] == bind(POSTLINK)
            and value["postlink_value"] == load(POSTLINK)
            and value["postlink_value"]["compiler_consumption"]
                == compiler_consumption()
            and value["postlink_value"]["final_ELF_extent_immediates"]
                == extent_immediates(ELF, 52230, 46043)
            and value["postlink_value"]["ELF_difference"] == elf_difference()
            and value["postlink_value"]["inventory_root"]
                == inventory_root_gate()
            and value["final_product"]["card3"] == CARD.card3_final_gate()
            and value["scope"]["receipt"] == bind(SCOPE)
            and value["qualification"]["receipt"] == bind(ACCEPTANCE)
            and value["frozen_pair_before"] == frozen_pair()
            and value["frozen_pair_after"] == frozen_pair()
            and REPORT.read_text(encoding="utf-8") == render_report(value),
            "r8 qualified artifacts or report drift")
    print("v1.7 IDE idle/blink r8: CHECK PASS extent=52230 "
          "unattributed=0 scope=PASS qualification=PASS")


def link() -> None:
    pre = load(PREFLIGHT_RECEIPT)
    require(pre["status"] == "PASS: CARD3 R8 HEADER-CORRECT LINK ARMED 0/1"
            and not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "card-3 r8 link lifecycle drift")
    INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "budget": {"WPLTO_runs": 1, "product_links": 1}}))
    process = run_child("_produce")
    consumption = compiler_consumption()
    extents = extent_immediates(ELF, 52230, 46043)
    differences = elf_difference()
    value = {"format": FORMAT + "-postlink", "recorded_on": "2026-08-26",
        "status": "PASS: R8 LINK EMITTED; DIFFERENCE ATTRIBUTION BOUNDARY",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION), "dead_pair": old_pair(),
        "artifacts": artifacts(), "process": process,
        "compiler_consumption": consumption,
        "final_ELF_extent_immediates": extents,
        "ELF_difference": differences,
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 0, "qualification_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Post-link attribution boundary; Scope/Qualification not run."}
    POSTLINK.write_bytes(canonical(value))
    print("v1.7 IDE idle/blink r8: LINK PASS WPLTO=1 link=1 "
          "extent=0xcc06 scope=0 qualification=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "link", "postlink", "qualify", "check",
        "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    install()
    {"preflight": preflight, "link": link, "postlink": postlink,
     "qualify": qualify, "check": check, "_produce": produce_child,
     "_scope": scope_child, "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.7 IDE idle/blink r8: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
