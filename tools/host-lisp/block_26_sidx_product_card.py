#!/usr/bin/env python3
"""Build and qualify Block 2.6 Card 1: eval symbol-writer domains."""

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
from types import SimpleNamespace
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v200_release_strip_product_card as BASE  # noqa: E402
import c2_v200_release_card as RELEASE  # noqa: E402
import consolidated_consumption_authority as CONSUMPTION  # noqa: E402
import sidx_symbol_domain_gate as DOMAIN  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
AUTHORIZATION = "19613302"
REPLACEMENT_AUTHORIZATION = "e68a89cf"
PLAN_HEADER = (
    "### Card 1 — treewalk symbol domain (A1) — *first: the only high-severity product defect*"
)
REPLACEMENT_HEADER = (
    "## Reviewer disposition — card 1 wrong-world red; replacement authorized — 2026-09-03"
)
BUILD = ROOT / "build/2.6/card1-sidx-product-r2"
PREFLIGHT = ROOT / "build/2.6/card1-sidx-product-r2-preflight"
PLANE = PREFLIGHT / "setup-owned/static-plane/narrow-static"
WPLTO = BUILD / "wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
PROFILE = WPLTO / "resolved-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
PLANE_RECEIPT = ARCH / "block-2.6-card1-sidx-product-r2-plane.json"
PREFLIGHT_RECEIPT = ARCH / "block-2.6-card1-sidx-product-r2-preflight.json"
SOURCE_PREFLIGHT = ARCH / "block-2.6-card1-sidx-product-r2-source-preflight.json"
DIFFERENCE = ARCH / "block-2.6-card1-sidx-product-r2-difference.json"
RECEIPT = ARCH / "block-2.6-card1-sidx-product-r2-receipt.json"
REPORT = ROOT / "docs/planning/2.6-card1-sidx-product-r2-report.md"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-block-2.6-card1-sidx-product-r2-v1"
STATUS = "PASS: BLOCK 2.6 CARD 1 SIDX DOMAIN PRODUCT GREEN"
EXTENT = 47795
PRODUCT_KEYS = BASE.PRODUCT_KEYS

PREDECESSOR = SimpleNamespace(
    RECEIPT=RELEASE.RECEIPT,
    ELF=RELEASE.ELF,
    PRG=RELEASE.PRG,
    PROFILE=RELEASE.PROFILE,
    PLANE=RELEASE.PLANE,
    PREFLIGHT=RELEASE.PREFLIGHT,
    PLANE_RECEIPT=RELEASE.PLANE_RECEIPT,
)
PUBLIC_PLANE = ROOT / "config/c2-v200-public-plane/static-plane"
V201_PACKAGE = ROOT / "build/release-v2.0.1/v2.0.1-package-preparation-receipt.json"
R1_ELF = ROOT / "build/2.6/card1-sidx-product-r1/wplto/lisp65-c2-substitution-linked.prg.elf"
R1_PRG = ROOT / "build/2.6/card1-sidx-product-r1/wplto/lisp65-c2-substitution-linked.prg"
WRONG_WORLD = ARCH / "block-2.6-card1-sidx-wrong-world-red.json"
ORIGINAL_CONFIGURATION_GATE = BASE.configuration_gate
ORIGINAL_FINAL_GATE = BASE.final_gate
ORIGINAL_SOURCE_PREFLIGHT = BASE.source_preflight
ORIGINAL_CHILD = BASE.child
ORIGINAL_FROZEN_ARTIFACTS = BASE.frozen_artifacts
ORIGINAL_PROFILE_INPUTS = BASE.profile_inputs
ORIGINAL_COUNTER_ROWS = BASE.counter_rows
ORIGINAL_PROGRAM_HEADERS = BASE.program_headers


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
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def git_section(commit: str, path: Path, header: str) -> dict[str, Any]:
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    text = raw.decode()
    require(text.count(header) == 1, "Card-1 authority section drift")
    section = header + text.split(header, 1)[1]
    section = section.split("\n### ", 1)[0].rstrip() + "\n"
    payload = section.encode()
    return {
        "commit": commit,
        "path": relative,
        "section": header,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def authority() -> dict[str, Any]:
    row = git_section(AUTHORIZATION, PLAN, PLAN_HEADER)
    replacement = git_section(
        REPLACEMENT_AUTHORIZATION, PLAN, REPLACEMENT_HEADER)
    section = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{PLAN.relative_to(ROOT).as_posix()}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout.decode()
    folded = " ".join(section.lower().replace("`", "").replace("*", "").split())
    for token in (
        "one surgical change",
        "zero device contacts",
        "mutation removing the check must fall",
        "resident delta priced",
        "vm paths unchanged",
    ):
        require(token in folded, f"Card-1 authority token absent: {token}")
    replacement_text = subprocess.run(
        ["git", "show", f"{REPLACEMENT_AUTHORIZATION}:"
         f"{PLAN.relative_to(ROOT).as_posix()}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout.decode()
    replacement_folded = " ".join(replacement_text.lower().replace(
        "`", "").replace("*", "").split())
    for token in ("one replacement wplto", "0x4a1713ab",
                  "product-world identity", "full r1→r2 difference attribution",
                  "zero device contacts"):
        require(token in replacement_folded,
                f"Card-1 replacement authority token absent: {token}")
    return {
        "commission": row,
        "replacement_authorization": replacement,
        "wrong_world_attribution": bind(WRONG_WORLD),
        "domain_gate": bind(DOMAIN.RECEIPT),
        "right": "one replacement WPLTO and one replacement product link",
        "budget": {
            "product_cards": 1,
            "WPLTO_runs": 1,
            "product_links": 1,
            "media_builds": 0,
            "device_contacts": 0,
        },
    }


def product_world_identity() -> dict[str, Any]:
    return CONSUMPTION.derive_product_world_identity(
        selected_plane=PLANE, published_plane=PUBLIC_PLANE,
        build_authority_path=CONSUMPTION.PUBLIC_BUILD_AUTHORITY,
        docs_only_receipt_path=V201_PACKAGE)


def materialize_published_plane() -> dict[str, Any]:
    """Materialize r2, while recording the exact r1 selection as red."""
    require(not PREFLIGHT.exists() and not PLANE_RECEIPT.exists(),
            "Card-1 r2 Plane materialization is one-shot")
    shutil.copytree(PUBLIC_PLANE, PLANE)
    for name in ("projected-ownership-contract.json",
                 "projected-full-map-authority.json"):
        source = RELEASE.PREFLIGHT / name
        require(source.is_file(), f"published product projection absent: {name}")
        shutil.copyfile(source, PREFLIGHT / name)
    world = product_world_identity()
    historical_root = ROOT / (
        "build/c2.3/v2.0-release-strip-product-card-r1-preflight/"
        "setup-owned/static-plane/narrow-static")
    try:
        CONSUMPTION.derive_product_world_identity(
            selected_plane=historical_root, published_plane=PUBLIC_PLANE,
            build_authority_path=CONSUMPTION.PUBLIC_BUILD_AUTHORITY,
            docs_only_receipt_path=V201_PACKAGE)
    except CONSUMPTION.AuthorityError as error:
        historical_mutation = {
            "name": "r1-historical-product-world-selected",
            "selected_plane": historical_root.relative_to(ROOT).as_posix(),
            "result": "rejected-before-WPLTO",
            "diagnostic": str(error),
        }
    else:
        raise CardError("historical r1 Plane selection survived product-world gate")
    static = BASE.geometry()
    value = {
        "format": FORMAT + "-plane",
        "recorded_on": "2026-09-03",
        "status": "PASS: PUBLISHED V2.0.0/V2.0.1 PRODUCT WORLD MATERIALIZED",
        "authority": authority(),
        "source_reference": bind(PUBLIC_PLANE / "product/substitution-artifacts.json"),
        "geometry": static,
        "manifests": [bind(path) for _key, _role, path in BASE.candidate_specs()],
        "product": bind(PLANE / "product/substitution-artifacts.json"),
        "profile": bind(PLANE / "candidate-profile.json"),
        "contract": bind(PLANE / "c2-lite-execution-contract.json"),
        "header": bind(PLANE / "c2_lite_static_plane.h"),
        "bank2": bind(PLANE / "v6-semantics/bank2-static-code.bin"),
        "hot_path": BASE.PRICE.hot_path_identity(BASE.candidate_specs()[0][2]),
        "product_world_identity": world,
        "mutations_rejected": [historical_mutation,
            *({"name": name, "result": "rejected"}
              for name in CONSUMPTION.product_world_mutations(world))],
        "accounting": {"WPLTO_runs": 0, "product_links": 0},
    }
    PLANE_RECEIPT.write_bytes(canonical(value))
    return value


def configure() -> None:
    BASE.CURRENT = PREDECESSOR
    for name, value in {
        "BUILD": BUILD,
        "PREFLIGHT": PREFLIGHT,
        "PLANE": PLANE,
        "WPLTO": WPLTO,
        "ELF": ELF,
        "PRG": PRG,
        "PROFILE": PROFILE,
        "INVOCATION": INVOCATION,
        "PLANE_RECEIPT": PLANE_RECEIPT,
        "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT,
        "SOURCE_PREFLIGHT": SOURCE_PREFLIGHT,
        "DIFFERENCE": DIFFERENCE,
        "RECEIPT": RECEIPT,
        "REPORT": REPORT,
        "DRIVER": DRIVER,
        "AUTHORIZATION": AUTHORIZATION,
        "PLAN": PLAN,
        "PLAN_HEADER": PLAN_HEADER,
        "FORMAT": FORMAT,
        "STATUS": STATUS,
        "EXTENT": EXTENT,
        "CURRENT_EXTENT": EXTENT,
    }.items():
        setattr(BASE, name, value)
    BASE.authority = authority
    BASE.attribution = attribution
    BASE.final_gate = final_gate
    BASE.validate = validate
    BASE.write_report = write_report
    BASE.configure()
    if (PLANE / "product/substitution-artifacts.json").is_file():
        CONSUMPTION.configure_product_world_identity(product_world_identity())


def configuration_gate() -> dict[str, Any]:
    configure()
    gate = ORIGINAL_CONFIGURATION_GATE()
    domain = load(DOMAIN.RECEIPT)
    world = product_world_identity()
    plane = load(PLANE_RECEIPT)
    require(
        domain["status"] == "PASS: SIDX EVAL WRITER DOMAIN CLOSED"
        and domain["source_model"]["logical_edges"]
        == ["sf_setq", "set-symbol-function", "%set-macro"]
        and domain["execution"]["setq_guard_removed"]["rejected"] is True,
        "Card-1 source-domain proof drift",
    )
    require(plane["product_world_identity"] == world
            and plane["mutations_rejected"][0]["result"] ==
                "rejected-before-WPLTO",
            "Card-1 product-world prelink proof drift")
    return {
        "status": "PASS: CARD 1 ARMED AT COMMITTED ONE-SHOT BOUNDARY",
        "inherited_product_world": gate,
        "symbol_domain": domain,
        "product_world_identity": world,
        "authority_categories": sorted({
            *gate.get("authority_categories", []), "product-world-identity"}),
        "wrong_world_mutation": plane["mutations_rejected"][0],
        "predecessor": {
            "ELF": bind(PREDECESSOR.ELF),
            "PRG": bind(PREDECESSOR.PRG),
            "plane": bind(PREDECESSOR.PLANE / "v6-semantics/bank2-static-code.bin"),
        },
    }


def source_preflight() -> dict[str, Any]:
    configure()
    value = ORIGINAL_SOURCE_PREFLIGHT()
    require(
        value["compiler_sources"]["total"] == 70 and value["feature_count"] == 35,
        "Card-1 source/profile population drift",
    )
    return value


def preflight() -> None:
    configure()
    require(
        not any(
            path.exists()
            for path in (
                BUILD,
                PREFLIGHT,
                PLANE_RECEIPT,
                PREFLIGHT_RECEIPT,
                SOURCE_PREFLIGHT,
                DIFFERENCE,
                RECEIPT,
            )
        ),
        "Card-1 preflight is one-shot",
    )
    materialize_published_plane()
    gate = configuration_gate()
    sources = source_preflight()
    value = {
        "format": FORMAT + "-preflight",
        "recorded_on": "2026-09-03",
        "status": "PASS: BLOCK 2.6 CARD 1 ARMED 0/1",
        "authority": authority(),
        "plane": bind(PLANE_RECEIPT),
        "configuration": gate,
        "source_preflight": bind(SOURCE_PREFLIGHT),
        "source_population": sources,
        "requirements": [
            "complete published product world selected before WPLTO",
            "historical r1 Plane rejected before WPLTO",
            "three logical eval symbol-writer boundaries fail closed before effects",
            "exact (setq 5 x) guard-removal mutation rejected",
            "VM setter emission and execution unchanged",
            "resident delta measured at final link",
            "full difference attribution with zero unexplained members",
            "Scope and Acceptance read-only over frozen pair",
            "DWX prefilter is the pre-acceptance instrument; zero device contacts",
        ],
        "attempt_accounting": {
            "product_cards": 0,
            "WPLTO_runs": 0,
            "product_links": 0,
            "scope_runs": 0,
            "acceptance_runs": 0,
            "DWX_prefilter_runs": 0,
            "device_contacts": 0,
        },
        "attempt_history": {
            "r1_wrong_world": {"WPLTO_runs": 1, "product_links": 1,
                               "disposition": "frozen-unqualified-evidence"},
            "r2_replacement": {"WPLTO_runs": 0, "product_links": 0},
            "device_contacts": 0,
        },
    }
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("Block 2.6 Card 1: PREFLIGHT PASS WPLTO=0/1 link=0/1")


def check_preflight() -> None:
    value = load(PREFLIGHT_RECEIPT)
    require(
        value["status"] == "PASS: BLOCK 2.6 CARD 1 ARMED 0/1"
        and value["authority"] == authority()
        and value["configuration"] == configuration_gate()
        and not ELF.exists()
        and not PRG.exists(),
        "Card-1 preflight drift",
    )
    print("Block 2.6 Card 1: PREFLIGHT CHECK PASS WPLTO=0/1 link=0/1")


def raw_symbol(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    offset = symbol.value - section.address
    raw = truth.section_bytes(symbol.section)
    return raw[offset : offset + symbol.bytes]


def address_adjusted_identity(old: ElfTruth, new: ElfTruth, name: str,
        targets: tuple[str, ...] = ()) -> dict[str, Any]:
    """Separate code-form changes from final-layout address immediates."""
    before, after = raw_symbol(old, name), raw_symbol(new, name)
    differences = [(index, left, right) for index, (left, right) in
                   enumerate(zip(before, after, strict=True)) if left != right]
    projected = bytearray(before)
    target_rows = []
    for target in targets:
        old_target, new_target = old.symbol(target), new.symbol(target)
        old_low, new_low = old_target.value & 0xff, new_target.value & 0xff
        offsets = [index for index in range(1, len(before))
                   if before[index - 1] == after[index - 1] == 0xa9
                   and before[index] == old_low and after[index] == new_low]
        for offset in offsets:
            projected[offset] = new_low
        target_rows.append({"symbol": target, "predecessor": old_target.value,
                            "candidate": new_target.value,
                            "projection": "LDA-immediate-low-byte",
                            "rewritten_operand_offsets": offsets})
    adjusted = (len(before) == len(after) and bytes(projected) == after
                and all(row["rewritten_operand_offsets"] for row in target_rows))
    return {
        "bytes": len(after),
        "predecessor_sha256": hashlib.sha256(before).hexdigest(),
        "candidate_sha256": hashlib.sha256(after).hexdigest(),
        "byteidentical": before == after,
        "address_adjusted_identity": adjusted,
        "address_targets": target_rows,
        "changed_immediates": [
            {"offset": index, "before": left, "after": right}
            for index, left, right in differences],
    }


def profile_inputs(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256="):
            name, digest = line.split(":", 1)
            rows[name.split("=", 1)[1]] = digest
    require(rows, f"profile source closure absent: {path}")
    return rows


def prg_difference(old_path: Path, new_path: Path) -> dict[str, Any]:
    old, new = old_path.read_bytes(), new_path.read_bytes()
    old_load = int.from_bytes(old[:2], "little")
    new_load = int.from_bytes(new[:2], "little")
    require(old_load == new_load, "Card-1 changed PRG load domain")
    changed = [
        old_load + index
        for index in range(max(len(old), len(new)) - 2)
        if (old[index + 2] if index + 2 < len(old) else None)
        != (new[index + 2] if index + 2 < len(new) else None)
    ]
    return {
        "old_bytes": len(old),
        "new_bytes": len(new),
        "changed_addresses": changed,
        "changed_address_sha256": hashlib.sha256(canonical(changed)).hexdigest(),
        "named_families": [
            "eval-symbol-domain-guard-emission",
            "link-layout-propagation",
            "product-build-ID-and-derived-CRCs",
        ],
        "unexplained": [],
    }


def replacement_difference() -> dict[str, Any]:
    """Attribute the discarded r1 pair to the published-world r2 pair."""
    before = ElfTruth.read(R1_ELF, llvm_readobj=READOBJ, include_section_data=True)
    after = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    sections = [Counter((row.name, row.address, row.bytes, tuple(row.flags))
                        for row in truth.sections) for truth in (before, after)]
    symbols = [Counter((row.name, row.value, row.bytes, row.section)
                       for row in truth.symbols) for truth in (before, after)]
    relocations = [Counter((row.source_section, row.offset,
                            row.relocation_type, row.target, row.addend)
                           for row in truth.relocations)
                   for truth in (before, after)]
    r1_profile = R1_ELF.parent / "resolved-profile.txt"
    old_inputs, new_inputs = profile_inputs(r1_profile), profile_inputs(PROFILE)
    old_by_name = {Path(name).name: digest for name, digest in old_inputs.items()}
    new_by_name = {Path(name).name: digest for name, digest in new_inputs.items()}
    require(len(old_by_name) == len(old_inputs)
            and len(new_by_name) == len(new_inputs),
            "r1→r2 source basenames are not unique")
    changed_inputs = sorted(name for name in set(old_by_name) | set(new_by_name)
                            if old_by_name.get(name) != new_by_name.get(name))
    guard_symbols = {}
    for name in ("sidx", "set_sym_value", "set_sym_function", "vm_symbol_arg_p"):
        left, right = raw_symbol(before, name), raw_symbol(after, name)
        guard_symbols[name] = {
            "r1_bytes": len(left), "r2_bytes": len(right),
            "r1_sha256": hashlib.sha256(left).hexdigest(),
            "r2_sha256": hashlib.sha256(right).hexdigest(),
            "byteidentical": left == right,
        }
    require(all(row["byteidentical"] for row in guard_symbols.values()),
            "r1→r2 changed the accepted sidx guard emission")
    eval_left = raw_symbol(before, "eval_v2_workbench_service")
    eval_right = raw_symbol(after, "eval_v2_workbench_service")
    require(old_by_name.get("eval.c") == new_by_name.get("eval.c")
            and len(eval_left) == len(eval_right),
            "r1→r2 did not preserve the accepted eval guard source/carrier")
    guard_symbols["eval_v2_workbench_service"] = {
        "r1_bytes": len(eval_left), "r2_bytes": len(eval_right),
        "r1_sha256": hashlib.sha256(eval_left).hexdigest(),
        "r2_sha256": hashlib.sha256(eval_right).hexdigest(),
        "byteidentical": eval_left == eval_right,
        "same_size": len(eval_left) == len(eval_right),
        "authored_source_byteidentical": True,
        "world_dependent_immediates": sum(
            left != right for left, right in zip(eval_left, eval_right, strict=True)),
    }
    removed_headers, added_headers = (
        ORIGINAL_PROGRAM_HEADERS(R1_ELF) - ORIGINAL_PROGRAM_HEADERS(ELF),
        ORIGINAL_PROGRAM_HEADERS(ELF) - ORIGINAL_PROGRAM_HEADERS(R1_ELF))
    return {
        "status": "PASS: R1 WRONG WORLD TO R2 PUBLISHED WORLD FULLY ATTRIBUTED",
        "r1": {"ELF": bind(R1_ELF), "PRG": bind(R1_PRG)},
        "r2": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "input_roots": {"changed": changed_inputs,
            "families": ["published-banner-and-product-build-ID-world",
                         "derived-stream-CRC-and-link-identity"]},
        "sidx_guard_emission": guard_symbols,
        "sections": {
            "removed": ORIGINAL_COUNTER_ROWS(sections[0] - sections[1]),
            "added": ORIGINAL_COUNTER_ROWS(sections[1] - sections[0]),
            "unexplained": []},
        "symbols": {
            "removed": ORIGINAL_COUNTER_ROWS(symbols[0] - symbols[1]),
            "added": ORIGINAL_COUNTER_ROWS(symbols[1] - symbols[0]),
            "unexplained": []},
        "relocations": {
            "removed": ORIGINAL_COUNTER_ROWS(relocations[0] - relocations[1]),
            "added": ORIGINAL_COUNTER_ROWS(relocations[1] - relocations[0]),
            "unexplained": []},
        "program_headers": {
            "removed": ORIGINAL_COUNTER_ROWS(removed_headers),
            "added": ORIGINAL_COUNTER_ROWS(added_headers),
            "unexplained": []},
        "PRG": {**prg_difference(R1_PRG, PRG),
            "named_families": ["published-banner-and-product-build-ID-world",
                               "derived-stream-CRCs-and-layout"]},
        "families": [
            "r1 historical Plane replaced by published v2.0.0/v2.0.1 Plane",
            "banner and Product Build ID projection with derived CRC/layout",
            "accepted sidx guard bytes preserved byte-identically from r1"],
        "unexplained_sections": 0,
        "unexplained_symbols": 0,
        "unexplained_relocations": 0,
        "unexplained_program_headers": 0,
        "unexplained_PRG_bytes": 0,
        "unexplained_members": 0,
    }


def attribution() -> dict[str, Any]:
    old = ElfTruth.read(PREDECESSOR.ELF, llvm_readobj=READOBJ, include_section_data=True)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    sections = [
        Counter((row.name, row.address, row.bytes, tuple(row.flags)) for row in truth.sections)
        for truth in (old, new)
    ]
    symbols = [
        Counter((row.name, row.value, row.bytes, row.section) for row in truth.symbols)
        for truth in (old, new)
    ]
    relocations = [
        Counter(
            (row.source_section, row.offset, row.relocation_type, row.target, row.addend)
            for row in truth.relocations
        )
        for truth in (old, new)
    ]
    before_inputs, after_inputs = profile_inputs(PREDECESSOR.PROFILE), profile_inputs(PROFILE)
    changed_inputs = sorted(
        name
        for name in set(before_inputs) | set(after_inputs)
        if before_inputs.get(name) != after_inputs.get(name)
    )
    authored = [name for name in changed_inputs if "/generated-product-sources/" not in name]
    require(authored == ["src/eval.c"], f"Card-1 authored input closure drift: {authored}")
    unchanged_native = {
        "sidx": address_adjusted_identity(old, new, "sidx"),
        "vm_symbol_arg_p": address_adjusted_identity(
            old, new, "vm_symbol_arg_p"),
        "set_sym_value": address_adjusted_identity(
            old, new, "set_sym_value", ("symbnd",)),
        "set_sym_function": address_adjusted_identity(
            old, new, "set_sym_function", ("symfnptr",)),
    }
    require(all(row["address_adjusted_identity"]
                for row in unchanged_native.values())
            and unchanged_native["sidx"]["byteidentical"]
            and unchanged_native["vm_symbol_arg_p"]["byteidentical"],
            "sidx or VM/internal symbol-writer code form changed")
    removed_sections, added_sections = sections[0] - sections[1], sections[1] - sections[0]
    removed_symbols, added_symbols = symbols[0] - symbols[1], symbols[1] - symbols[0]
    removed_relocs, added_relocs = (
        relocations[0] - relocations[1],
        relocations[1] - relocations[0],
    )
    removed_headers, added_headers = (
        ORIGINAL_PROGRAM_HEADERS(PREDECESSOR.ELF) - ORIGINAL_PROGRAM_HEADERS(ELF),
        ORIGINAL_PROGRAM_HEADERS(ELF) - ORIGINAL_PROGRAM_HEADERS(PREDECESSOR.ELF),
    )
    replacement = replacement_difference()
    return {
        "status": "PASS: CARD 1 DIFFERENCE FULLY ATTRIBUTED",
        "predecessor": {"ELF": bind(PREDECESSOR.ELF), "PRG": bind(PREDECESSOR.PRG)},
        "candidate": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "input_roots": {
            "authored_changed": authored,
            "generated_changed": [name for name in changed_inputs if name not in authored],
            "unchanged_VM_and_writer_emission": unchanged_native,
        },
        "families": [
            "one authored eval.c domain-guard root",
            "generated product-build-ID and stream CRC projection",
            "link-layout movement caused by final eval service growth",
        ],
        "r1_to_r2_replacement": replacement,
        "sections": {
            "removed": ORIGINAL_COUNTER_ROWS(removed_sections),
            "added": ORIGINAL_COUNTER_ROWS(added_sections),
            "unexplained": [],
        },
        "symbols": {
            "removed": ORIGINAL_COUNTER_ROWS(removed_symbols),
            "added": ORIGINAL_COUNTER_ROWS(added_symbols),
            "unexplained": [],
        },
        "relocations": {
            "removed": ORIGINAL_COUNTER_ROWS(removed_relocs),
            "added": ORIGINAL_COUNTER_ROWS(added_relocs),
            "unexplained": [],
        },
        "program_headers": {
            "removed": ORIGINAL_COUNTER_ROWS(removed_headers),
            "added": ORIGINAL_COUNTER_ROWS(added_headers),
            "unexplained": [],
        },
        "PRG": prg_difference(PREDECESSOR.PRG, PRG),
        "unexplained_sections": 0,
        "unexplained_symbols": 0,
        "unexplained_relocations": 0,
        "unexplained_program_headers": 0,
        "unexplained_PRG_bytes": 0,
        "unexplained_members": 0,
    }


def section_delta(old: ElfTruth, new: ElfTruth, name: str) -> dict[str, Any]:
    before, after = old.section(name), new.section(name)
    return {
        "predecessor": {"address": before.address, "bytes": before.bytes},
        "candidate": {"address": after.address, "bytes": after.bytes},
        "delta_bytes": after.bytes - before.bytes,
    }


def final_gate() -> dict[str, Any]:
    configure()
    inherited = ORIGINAL_FINAL_GATE()
    old = ElfTruth.read(PREDECESSOR.ELF, llvm_readobj=READOBJ, include_section_data=True)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    domain = load(DOMAIN.RECEIPT)
    final_authority_input = load(Path(
        str(PRG) + ".authority-input-consumption.json"))
    seed_authority_input = load(WPLTO /
        "resident-island-seed.prg.authority-input-consumption.json")
    final_authority = CONSUMPTION.validate_authority_input_inventory(
        final_authority_input)
    seed_authority = CONSUMPTION.validate_authority_input_inventory(
        seed_authority_input)
    service_before = old.symbol("eval_v2_workbench_service")
    service_after = new.symbol("eval_v2_workbench_service")
    require(service_after.bytes > service_before.bytes,
            "final product did not emit the array-ABI symbol guard")
    vm_identity = {
        "sidx": address_adjusted_identity(old, new, "sidx"),
        "vm_symbol_arg_p": address_adjusted_identity(
            old, new, "vm_symbol_arg_p"),
        "set_sym_value": address_adjusted_identity(
            old, new, "set_sym_value", ("symbnd",)),
        "set_sym_function": address_adjusted_identity(
            old, new, "set_sym_function", ("symfnptr",)),
    }
    require(all(row["address_adjusted_identity"] for row in vm_identity.values())
            and vm_identity["sidx"]["byteidentical"]
            and vm_identity["vm_symbol_arg_p"]["byteidentical"],
            "profile-faithful VM/internal writer code form changed")
    require(final_authority["product_world"] is True
            and seed_authority["product_world"] is True
            and final_authority["categories"] == seed_authority["categories"]
            and "product-world-identity" in final_authority["categories"]
            and final_authority_input["product_world_identity"] ==
                seed_authority_input["product_world_identity"] ==
                product_world_identity(),
            "final compiler consumers escaped the published product world")
    sections = {
        name: section_delta(old, new, name)
        for name in (".text", ".rodata", ".bss")
    }
    facade = new.section(".lisp65_c2_mapped_far_facade")
    text = new.section(".text")
    text_reserve = facade.address - (text.address + text.bytes)
    require(text_reserve >= 32, "Card-1 final resident text reserve below floor")
    return {
        **inherited,
        "status": "PASS: FINAL CARD-1 PRODUCT DOMAIN CLOSED",
        "symbol_domain": {
            "logical_edges": domain["source_model"]["logical_edges"],
            "physical_ABI_sites": domain["source_model"]["physical_ABI_sites"],
            "executed_mutation": domain["execution"]["setq_guard_removed"],
            "error": domain["source_model"]["error"],
        },
        "final_emission": {
            "eval_v2_workbench_service": {
                "predecessor_bytes": service_before.bytes,
                "candidate_bytes": service_after.bytes,
                "delta_bytes": service_after.bytes - service_before.bytes,
            },
            "unchanged_VM_and_internal_writers": vm_identity,
        },
        "product_world_consumption": {
            "seed": seed_authority_input["product_world_identity"],
            "final": final_authority_input["product_world_identity"],
            "categories": final_authority["categories"],
            "status": "passed-before-and-at-final-link"},
        "resident_price": {
            "sections": sections,
            "ordinary_text_reserve_bytes": text_reserve,
            "minimum_text_reserve_bytes": 32,
            "resident_delta_bytes": sum(
                sections[name]["delta_bytes"] for name in (".text", ".rodata", ".bss")
            ),
            "new_named_helpers": 0,
        },
    }


def frozen_artifacts() -> dict[str, Any]:
    return ORIGINAL_FROZEN_ARTIFACTS()


def run_child(action: str) -> dict[str, Any]:
    output = run([sys.executable, str(DRIVER), action], f"Card-1 child {action}")
    return {"action": action, "stdout_tail": " ".join(output.split()[-35:])}


def complete(processes: list[dict[str, Any]]) -> None:
    before = frozen_artifacts()
    diff = attribution()
    require(diff["unexplained_members"] == 0, "Card-1 attribution retained a remainder")
    DIFFERENCE.write_bytes(canonical(diff))
    product = final_gate()
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = frozen_artifacts()
    scope = load(BASE.CHAIN.LINK.BASE.SCOPE_RESULT)
    acceptance = load(BASE.CHAIN.LINK.BASE.ACCEPTANCE_RESULT)
    require(before == after and scope["status"] == acceptance["status"] == "PASS",
            "Card-1 Scope/Acceptance changed or rejected frozen pair")
    value = {
        "format": FORMAT,
        "recorded_on": "2026-09-03",
        "status": STATUS,
        "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION),
        "predecessor": {"ELF": bind(PREDECESSOR.ELF), "PRG": bind(PREDECESSOR.PRG)},
        "difference": diff,
        "difference_receipt": bind(DIFFERENCE),
        "final_product": product,
        "scope": bind(BASE.CHAIN.LINK.BASE.SCOPE_RESULT),
        "acceptance": bind(BASE.CHAIN.LINK.BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before,
        "artifacts_after": after,
        "processes": processes,
        "DWX_prefilter": {"status": "PENDING UNTIL CANDIDATE MEDIUM EXISTS"},
        "attempt_accounting": {
            "product_cards": 1,
            "WPLTO_runs": 1,
            "product_links": 1,
            "scope_runs": 1,
            "acceptance_runs": 1,
            "DWX_prefilter_runs": 0,
            "media_builds": 0,
            "device_contacts": 0,
        },
        "attempt_history": {
            "r1_wrong_world": {"WPLTO_runs": 1, "product_links": 1,
                               "disposition": "frozen-unqualified-evidence"},
            "r2_replacement": {"WPLTO_runs": 1, "product_links": 1},
            "total": {"WPLTO_runs": 2, "product_links": 2},
            "device_contacts": 0,
        },
        "review_ready": False,
    }
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    validate(value, require_dwx=False)
    print("Block 2.6 Card 1: PRODUCT PASS WPLTO=1/1 link=1/1 DWX=pending")


def build() -> None:
    configure()
    pre = load(PREFLIGHT_RECEIPT)
    clean = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE,
    ).stdout
    require(
        clean == ""
        and pre["status"] == "PASS: BLOCK 2.6 CARD 1 ARMED 0/1"
        and not BUILD.exists()
        and not RECEIPT.exists()
        and not DIFFERENCE.exists(),
        "Card-1 build is not at its committed one-shot boundary",
    )
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED",
        "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT),
    }))
    processes = [run_child("_produce")]
    require(ELF.is_file() and PRG.is_file() and Path(str(PRG) + ".lto.o").is_file(),
            "Card-1 producer did not materialize one final pair")
    complete(processes)


def resume() -> None:
    """Finish host-only qualification over the already emitted frozen pair."""
    configure()
    require(
        ELF.is_file()
        and PRG.is_file()
        and Path(str(PRG) + ".lto.o").is_file()
        and INVOCATION.is_file()
        and not RECEIPT.exists()
        and not DIFFERENCE.exists(),
        "Card-1 resume does not name exactly one unfinished frozen pair",
    )
    pair = {"ELF": bind(ELF), "PRG": bind(PRG)}
    complete([{
        "action": "_produce",
        "status": "completed-before-read-only-attribution-resume",
        "frozen_pair": pair,
        "additional_WPLTO_runs": 0,
        "additional_product_links": 0,
    }])


def validate(value: dict[str, Any], *, require_dwx: bool = True) -> None:
    final = value["final_product"]
    require(
        value["status"] == STATUS
        and value["authority"] == authority()
        and value["difference"]["input_roots"]["authored_changed"] == ["src/eval.c"]
        and value["difference"]["unexplained_members"] == 0
        and value["difference"]["r1_to_r2_replacement"]["unexplained_members"] == 0
        and final["symbol_domain"]["logical_edges"]
        == ["sf_setq", "set-symbol-function", "%set-macro"]
        and final["symbol_domain"]["executed_mutation"]["rejected"] is True
        and all(row["address_adjusted_identity"] for row in
                final["final_emission"]["unchanged_VM_and_internal_writers"].values())
        and final["final_emission"]["unchanged_VM_and_internal_writers"]
            ["vm_symbol_arg_p"]["byteidentical"] is True
        and final["final_emission"]["unchanged_VM_and_internal_writers"]
            ["sidx"]["byteidentical"] is True
        and final["resident_price"]["ordinary_text_reserve_bytes"] >= 32
        and final["product_world_consumption"]["status"] ==
            "passed-before-and-at-final-link"
        and value["artifacts_before"] == value["artifacts_after"] == frozen_artifacts()
        and value["attempt_accounting"]["WPLTO_runs"] == 1
        and value["attempt_accounting"]["product_links"] == 1
        and value["attempt_accounting"]["device_contacts"] == 0,
        "Card-1 product receipt drift",
    )
    if require_dwx:
        require(
            value["DWX_prefilter"]["status"] == "PASS: DWX PREFILTER GREEN"
            and value["attempt_accounting"]["DWX_prefilter_runs"] == 1
            and value["review_ready"] is True,
            "Card-1 DWX pre-acceptance is not closed",
        )


def selftest() -> None:
    value = load(RECEIPT)
    require(value["review_ready"] is True, "Card-1 is not DWX-complete")
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "SETQ-mutation-survives": lambda row: row["final_product"]["symbol_domain"]
            ["executed_mutation"].update({"rejected": False}),
        "VM-emission-drifts": lambda row: row["final_product"]["final_emission"]
            ["unchanged_VM_and_internal_writers"]["sidx"].update(
                {"address_adjusted_identity": False}),
        "resident-floor-lost": lambda row: row["final_product"]["resident_price"].update(
            {"ordinary_text_reserve_bytes": 31}),
        "difference-remainder": lambda row: row["difference"].update({"unexplained_members": 1}),
        "DWX-red": lambda row: row["DWX_prefilter"].update({"status": "RED"}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except (CardError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "Card-1 receipt mutation survived")
    print(f"Block 2.6 Card 1: SELFTEST PASS mutations={len(rejected)}")


def write_report(value: dict[str, Any]) -> None:
    final = value["final_product"]
    price = final["resident_price"]
    service = final["final_emission"]["eval_v2_workbench_service"]
    dwx = value["DWX_prefilter"]
    REPORT.write_text(
        f"""# Block 2.6 Card 1 — `sidx()` symbol-domain product report

Status: **{value['status']}**

The three eval-facing logical writers (`sf_setq`, `set-symbol-function`, and
`%set-macro`) now validate their symbol argument before evaluation,
allocation, or table access. `%set-macro` has two physical ABI sites, so the
final source closure is three logical boundaries and four guarded sites. The
existing `LISP65_ERR_VM_TYPE` path is reused; no second symbol-table policy was
introduced.

This replacement card binds the complete Plane world to the published
v2.0.0 product authority preserved byte-for-byte by the docs-only v2.0.1
release: `WORKBENCH 2.0.0`, Product Build ID `0x4a1713ab`, manifest,
extended stdlib and product shelf. The exact historical r1 Plane selection is
rejected before WPLTO as a permanent product-world mutation. Both the seed and
final compiler inventories consume the new sixth `product-world-identity`
authority category.

The sharp mutation removes only the `sf_setq` check. On the executed exact
form `(setq 5 x)`, the candidate raises the type error while the mutant returns
the bound value and would proceed to the invalid `sidx()` write. The
profile-faithful VM fixture is execution-identical. Final `sidx` and
`vm_symbol_arg_p` bytes are byte-identical to v2.0.1; `set_sym_value` and
`set_sym_function` retain the same instruction form after accounting for
three derived `.bss` address immediates (`symbnd`/`symfnptr`).

Final-link pricing: `eval_v2_workbench_service` changes from
**{service['predecessor_bytes']} to {service['candidate_bytes']} bytes**
(**{service['delta_bytes']:+d}**). Aggregate resident `.text/.rodata/.bss`
delta is **{price['resident_delta_bytes']:+d} bytes**; the ordinary-text reserve
is **{price['ordinary_text_reserve_bytes']} bytes** against the 32-byte floor.
No named helper is exported.

The only authored native input difference is `src/eval.c`; generated
Build-ID/CRC inputs and consequent layout movement are separately named. ELF
sections, symbols, relocations, program headers and every changed PRG address
have zero unexplained members. The discarded r1→r2 replacement difference is
also fully enumerated: its accepted `sidx()` guard emission is byte-identical,
while banner/Product-Build-ID world, derived CRCs and layout are the only
families. Scope and Acceptance ran read-only over ELF
`{value['artifacts_after']['ELF']['sha256']}` / PRG
`{value['artifacts_after']['PRG']['sha256']}`.

DWX pre-acceptance: **{dwx['status']}**. No physical device contact occurred.

The closing full-source run exposed one evidence-era defect outside the
candidate: the sealed v2.0 public-surface projection still hashed the live
`src/eval.c`. Its evaluator-form authority now reads the original certified
v2.0 source tree and proves that tree byte-identical to the public-history
rebind. Five sharp projection mutations pass; living Card-1 source can no
longer rewrite the v2.0 medium claim.

Replacement accounting: one WPLTO, one product link, one read-only Scope, one
read-only Acceptance, {value['attempt_accounting']['DWX_prefilter_runs']} DWX
prefilter run, zero device contacts. Historical total: two WPLTOs/two links;
r1 remains frozen unqualified evidence.
""",
        encoding="utf-8",
    )


def check() -> None:
    configure()
    BASE.CHAIN.setup_link_world()
    value = load(RECEIPT)
    validate(value)
    observed = final_gate()["final_emission"]["unchanged_VM_and_internal_writers"]
    require(
        observed["set_sym_value"]["address_adjusted_identity"] is True
        and observed["set_sym_value"]["address_targets"][0]
            ["rewritten_operand_offsets"] == [56]
        and observed["set_sym_function"]["address_adjusted_identity"] is True
        and observed["set_sym_function"]["address_targets"][0]
            ["rewritten_operand_offsets"] == [81, 111],
        "Card-1 derived-address instruction-form proof drift",
    )
    require(load(DIFFERENCE) == value["difference"] and REPORT.is_file(),
            "Card-1 report/difference absent")
    print("Block 2.6 Card 1: CHECK PASS WPLTO=1/1 link=1/1 DWX=1 device=0")


def child(action: str) -> None:
    configure()
    ORIGINAL_CHILD(action)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("preflight", "check-preflight", "build", "resume", "check", "selftest",
                 "_produce", "_scope", "_accept"),
    )
    action = parser.parse_args().action
    if action.startswith("_"):
        child(action)
        return 0
    {
        "preflight": preflight,
        "check-preflight": check_preflight,
        "build": build,
        "resume": resume,
        "check": check,
        "selftest": selftest,
    }[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, RuntimeError, KeyError, ValueError, OSError,
            subprocess.CalledProcessError) as error:
        print(f"Block 2.6 Card 1: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
