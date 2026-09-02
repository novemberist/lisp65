#!/usr/bin/env python3
"""Rebind the phase-0 product build ID and qualify the successor product."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
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

import c2_v200_symbol22_first_fault_completion_replacement as R3  # noqa: E402
import consolidated_consumption_authority as CONSUMPTION  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


CARD = R3.CARD
BUILD = CARD.BUILD
OLD_COMPLETION = BUILD / "completion-r3"
COMPLETION = BUILD / "completion-r4"
ELF = COMPLETION / "lisp65-c2-substitution-linked.prg.elf"
PRG = COMPLETION / "lisp65-c2-substitution-linked.prg"
PROFILE = COMPLETION / "resolved-profile.txt"
PRELINK = ROOT / "build/c2.3/v2.0-symbol22-build-id-authority-prelink-r2"
ARCH = CARD.ARCH
PRELINK_RECEIPT = ARCH / (
    "c2.3-v2.0-symbol22-build-id-authority-prelink.json")
DIFFERENCE = ARCH / (
    "c2.3-v2.0-symbol22-first-fault-r3-r4-build-id-difference.json")
RELEASE_DIFFERENCE = ARCH / (
    "c2.3-v2.0-symbol22-first-fault-product-card-r4-difference.json")
RECEIPT = ARCH / (
    "c2.3-v2.0-symbol22-first-fault-product-card-r4-receipt.json")
REPORT = ROOT / "docs/planning/v2.0.0-symbol22-build-id-rebind-report.md"
DRIVER = Path(__file__).resolve()
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
AUTHORIZATION = "fc455a29"
PLAN_HEADER = (
    "## Reviewer disposition — E25 build-ID rebind, both axes derived — 2026-08-31")
STATUS = "PASS: V2.0 SYMBOL22 BUILD-ID REBOUND PRODUCT GREEN"
FORMAT = "lisp65-c2.3-v200-symbol22-build-id-rebind-v1"
OLD_ELF = OLD_COMPLETION / "lisp65-c2-substitution-linked.prg.elf"
OLD_PRG = OLD_COMPLETION / "lisp65-c2-substitution-linked.prg"
OLD_MANIFEST = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
R3_SEALED_RECEIPT = ARCH / (
    "c2.3-v2.0-symbol22-first-fault-product-card-r3-receipt.json")
CANDIDATE_MANIFEST = BUILD / (
    "static-plane/narrow-static/product/substitution-artifacts.json")


def require(value: bool, message: str) -> None:
    if not value:
        raise CARD.CardError(message)


def bind(path: Path) -> dict[str, Any]:
    return CARD.bind(path)


def load(path: Path) -> dict[str, Any]:
    return CARD.load(path)


def authority() -> dict[str, Any]:
    return {
        "review_authorization": CARD.git_section(
            AUTHORIZATION, PLAN, PLAN_HEADER),
        "device_red": {
            "status": "E25-before-library-load",
            "delivered_header_build_id": "0x8c6cc520",
            "r3_decoder_build_id": "0x69496476",
            "all_other_phase00_header_checks": "passed",
        },
        "right": "build-ID consumer rebind plus exactly one product link",
        "budget": {"seed_WPLTOs": 1, "product_links_total": 3,
                   "new_WPLTOs": 0, "new_product_links": 1},
    }


def configure_seed_world() -> Any:
    core = R3.configure_seed_world()
    CARD.PRODUCT.configure_product_artifacts_manifest_resolver(
        lambda: CANDIDATE_MANIFEST)
    resolved = CARD.PRODUCT.resolved_product_artifacts_manifest()
    require(resolved == CANDIDATE_MANIFEST
            and load(resolved)["product_build_id_hex"] == "0x8c6cc520",
            "candidate product authority did not dominate the historical default")
    return core


def configure() -> None:
    # Reuse the qualified r3 configuration graph while redirecting every live
    # completion output to an independent successor root.
    R3.COMPLETION = COMPLETION
    R3.ELF = ELF
    R3.PRG = PRG
    R3.PROFILE = PROFILE
    R3.DIFFERENCE = RELEASE_DIFFERENCE
    R3.REPLACEMENT_DIFFERENCE = DIFFERENCE
    R3.RECEIPT = RECEIPT
    R3.REPORT = REPORT
    R3.DRIVER = DRIVER
    R3.STATUS = STATUS
    R3.FORMAT = FORMAT
    R3.configure()
    CARD.configure_r2_seed_world = configure_seed_world
    CARD.COMPLETION = COMPLETION
    CARD.ELF = ELF
    CARD.PRG = PRG
    CARD.PROFILE = PROFILE
    CARD.DIFFERENCE = RELEASE_DIFFERENCE
    CARD.RECEIPT = RECEIPT
    CARD.REPORT = REPORT
    CARD.DRIVER = DRIVER
    CARD.STATUS = STATUS
    CARD.FORMAT = FORMAT
    CARD.patch_paths()
    CARD.BASE.SCOPE_RESULT = COMPLETION / "owner-scope-result.json"
    CARD.BASE.ACCEPTANCE_RESULT = COMPLETION / "artifact-acceptance.json"
    # The qualification chain bottoms out in the source-authoritative oracle;
    # bind its lifecycle sentinels to the same phase-owned successor root too.
    card_source_oracle = R3.R1.ORACLE

    def bind_oracle_root() -> None:
        card_source_oracle.BUILD = COMPLETION
        card_source_oracle.SCOPE_RESULT = CARD.BASE.SCOPE_RESULT
        card_source_oracle.ACCEPTANCE_RESULT = CARD.BASE.ACCEPTANCE_RESULT

    bind_oracle_root()
    # Historical setup code legitimately reconstructs its own card era while
    # walking to the living Scope/Acceptance seam.  Rebind at the real oracle
    # consumer, after that setup, so an inherited root cannot dominate r4.
    if not hasattr(card_source_oracle, "_r4_original_scope_child"):
        card_source_oracle._r4_original_scope_child = \
            card_source_oracle.scope_child
        card_source_oracle._r4_original_acceptance_child = \
            card_source_oracle.acceptance_child

    def scope_from_successor() -> int:
        bind_oracle_root()
        return card_source_oracle._r4_original_scope_child()

    def acceptance_from_successor() -> int:
        bind_oracle_root()
        return card_source_oracle._r4_original_acceptance_child()

    card_source_oracle.scope_child = scope_from_successor
    card_source_oracle.acceptance_child = acceptance_from_successor
    CARD.PRODUCT.configure_product_artifacts_manifest_resolver(
        lambda: CANDIDATE_MANIFEST)


def no_silent_default_control() -> dict[str, Any]:
    product = CARD.PRODUCT
    old_manifest = product.PRODUCT_ARTIFACTS_MANIFEST
    old_resolver = product.PRODUCT_ARTIFACTS_MANIFEST_RESOLVER
    product.PRODUCT_ARTIFACTS_MANIFEST = None
    product.PRODUCT_ARTIFACTS_MANIFEST_RESOLVER = None
    try:
        product.resolved_product_artifacts_manifest()
    except RuntimeError as error:
        message = str(error)
    else:
        raise CARD.CardError("unbound product authority silently selected a default")
    finally:
        product.PRODUCT_ARTIFACTS_MANIFEST = old_manifest
        product.PRODUCT_ARTIFACTS_MANIFEST_RESOLVER = old_resolver
    require("unbound" in message and "silent defaults" in message,
            "fail-closed authority control produced the wrong failure")
    return {"mutation": "remove-explicit-product-authority",
            "result": "rejected-before-compiler", "diagnostic": message}


def prelink_inventory() -> dict[str, Any]:
    configure_seed_world()
    contract = BUILD / "wplto/resolved-profile.txt"
    features, compiler_sources = CARD.seed_compile_inputs(contract)
    PRELINK.mkdir(parents=True, exist_ok=False)
    CARD.PRODUCT.write_product_linker_sources(PRELINK, features)
    target = PRELINK / "authority-preview.prg"
    _flags, static_report = CARD.PRODUCT.compiler_consumed_static_header_flags(
        PRELINK, target)
    _stdlib_flags, stdlib_report = (
        CARD.PRODUCT.compiler_consumed_stdlib_header_flags(PRELINK, target))
    manifest = CARD.PRODUCT.resolved_product_artifacts_manifest()
    value = CONSUMPTION.build_authority_input_inventory(
        target=target, manifest_path=manifest, artifacts=load(manifest),
        renderer=CARD.PRODUCT.definitions, static_report=static_report,
        stdlib_report=stdlib_report,
        linker_script=PRELINK / "c2-substitution.ld",
        compiler_sources=compiler_sources)
    constants = value["manifest"]["derived_constants"]
    require([(row["authority_path"], row["compiler_definition"])
             for row in constants] == [
                ("artifacts/shelf/bytes", "LISP65_C2_PRODUCT_SHELF_BYTES"),
                ("product_build_id_hex", "LISP65_C2_PRODUCT_BUILD_ID")]
            and all(row["seed_source_consumers"] for row in constants),
            "prelink did not derive the complete living manifest population")
    value["fail_closed_control"] = no_silent_default_control()
    value["timing"] = "completed-before-authorized-product-link"
    value["authority"] = authority()
    PRELINK_RECEIPT.write_bytes(CARD.canonical(value))
    return value


def cmp_immediates(path: Path, section: str) -> list[int]:
    output = subprocess.run([
        str(CARD.OBJDUMP), "-d", f"--section={section}", str(path)],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout
    return [int(value, 16) for value in re.findall(r"\bcmp\s+#\$([0-9a-fA-F]+)",
                                                   output)]


def contains_subsequence(values: list[int], wanted: list[int]) -> bool:
    return any(values[index:index + len(wanted)] == wanted
               for index in range(len(values) - len(wanted) + 1))


def counter_delta(left: Counter[Any], right: Counter[Any]) -> dict[str, int]:
    return {"removed": sum((left - right).values()),
            "added": sum((right - left).values())}


def successor_attribution() -> dict[str, Any]:
    old_profile = PROFILE.read_bytes()
    require(old_profile == (OLD_COMPLETION / "resolved-profile.txt").read_bytes(),
            "r4 changed the transported/generated seed source world")
    old_manifest, new_manifest = load(OLD_MANIFEST), load(CANDIDATE_MANIFEST)
    old_definitions = dict(row.split("=", 1) if "=" in row else (row, "<defined>")
                           for row in CARD.PRODUCT.definitions(old_manifest))
    new_definitions = dict(row.split("=", 1) if "=" in row else (row, "<defined>")
                           for row in CARD.PRODUCT.definitions(new_manifest))
    changed_definitions = sorted(name for name in set(old_definitions) |
        set(new_definitions) if old_definitions.get(name) != new_definitions.get(name))
    require(changed_definitions == ["LISP65_C2_PRODUCT_BUILD_ID",
                                    "LISP65_C2_PRODUCT_SHELF_BYTES"]
            and old_definitions["LISP65_C2_PRODUCT_BUILD_ID"] ==
                "0x69496476UL"
            and new_definitions["LISP65_C2_PRODUCT_BUILD_ID"] ==
                "0x8c6cc520UL"
            and old_definitions["LISP65_C2_PRODUCT_SHELF_BYTES"] == "70897UL"
            and new_definitions["LISP65_C2_PRODUCT_SHELF_BYTES"] == "95981UL",
            "r3/r4 compiler-authority difference escaped the derived population")

    old_cmp = cmp_immediates(OLD_ELF, ".lisp65_rt_c2d_00")
    new_cmp = cmp_immediates(ELF, ".lisp65_rt_c2d_00")
    # The generated decoder reaches the four bytes in MSB, byte-2, byte-1,
    # LSB order; this is not the little-endian storage order of the header.
    old_sequence, new_sequence = [0x69, 0x49, 0x64, 0x76], [0x8C, 0x6C, 0xC5, 0x20]
    require(contains_subsequence(old_cmp, old_sequence)
            and not contains_subsequence(old_cmp, new_sequence)
            and contains_subsequence(new_cmp, new_sequence)
            and not contains_subsequence(new_cmp, old_sequence),
            "phase-0 decoder did not consume the candidate product build ID")

    old_truth = ElfTruth.read(OLD_ELF, llvm_readobj=CARD.READOBJ)
    new_truth = ElfTruth.read(ELF, llvm_readobj=CARD.READOBJ)
    old_sections = Counter((row.name, row.address, row.bytes, tuple(row.flags))
                           for row in old_truth.sections)
    new_sections = Counter((row.name, row.address, row.bytes, tuple(row.flags))
                           for row in new_truth.sections)
    old_symbols = Counter((row.name, row.value, row.bytes, row.section)
                          for row in old_truth.symbols)
    new_symbols = Counter((row.name, row.value, row.bytes, row.section)
                          for row in new_truth.symbols)
    old_relocations = Counter((row.source_section, row.offset,
                               row.relocation_type, row.target, row.addend)
                              for row in old_truth.relocations)
    new_relocations = Counter((row.source_section, row.offset,
                               row.relocation_type, row.target, row.addend)
                              for row in new_truth.relocations)
    old_headers = Counter(tuple(sorted(row.items()))
                          for row in CARD.program_headers(OLD_ELF))
    new_headers = Counter(tuple(sorted(row.items()))
                          for row in CARD.program_headers(ELF))
    old_raw, new_raw = OLD_PRG.read_bytes(), PRG.read_bytes()
    load_old, load_new = (int.from_bytes(old_raw[:2], "little"),
                          int.from_bytes(new_raw[:2], "little"))
    require(load_old == load_new, "r4 changed the PRG load domain")
    changed = [load_new + index for index, pair in enumerate(
        zip(old_raw[2:], new_raw[2:])) if pair[0] != pair[1]]
    changed.extend(range(load_new + min(len(old_raw), len(new_raw)) - 2,
                         load_new + max(len(old_raw), len(new_raw)) - 2))
    headers = CARD.program_headers(ELF)
    owner_counts: Counter[str] = Counter()
    unowned: list[int] = []
    for address in changed:
        owner = (CARD.prg_domain_owner(new_truth, headers, address)
                 or CARD.prg_derived_padding_owner(new_truth, address))
        if owner is None:
            unowned.append(address)
        else:
            owner_counts[owner] += 1
    require(not unowned, f"r3/r4 PRG difference escaped ownership: {unowned[:8]}")

    actual_inventory = load(Path(str(PRG) +
        ".authority-input-consumption.json"))
    CONSUMPTION.validate_authority_input_inventory(actual_inventory)
    actual_build = next(row for row in actual_inventory["manifest"]
        ["derived_constants"] if row["compiler_definition"] ==
            "LISP65_C2_PRODUCT_BUILD_ID")
    require(actual_build["consumed_value"] == "0x8c6cc520UL",
            "actual product link did not consume candidate build-ID authority")
    return {
        "status": "PASS: R3 TO R4 DIFFERENCE FULLY ATTRIBUTED",
        "input_roots": {
            "source_and_feature_profile": "byte-identical",
            "changed_compiler_definitions": changed_definitions,
            "phase_owned_output_root": {
                "before": OLD_COMPLETION.relative_to(ROOT).as_posix(),
                "after": COMPLETION.relative_to(ROOT).as_posix()},
        },
        "phase00_build_id": {
            "r3": "0x69496476", "r4": "0x8c6cc520",
            "r3_compare_sequence": old_sequence,
            "r4_compare_sequence": new_sequence},
        "PRG": {"changed_bytes": len(changed),
                "owner_families": dict(sorted(owner_counts.items())),
                "unexplained": 0},
        "ELF": {"sections": counter_delta(old_sections, new_sections),
                "symbols": counter_delta(old_symbols, new_symbols),
                "relocations": counter_delta(old_relocations, new_relocations),
                "program_headers": counter_delta(old_headers, new_headers),
                "unexplained": 0},
        "families": [
            "candidate manifest definitions (product build ID and shelf extent) and transitive codegen",
            "phase-owned output-root Build-ID projection"],
        "actual_authority_inventory": bind(Path(str(PRG) +
            ".authority-input-consumption.json")),
        "unexplained_members": 0,
    }


def run_child(action: str) -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0,
            f"build-ID successor child {action} red:\n{result.stdout}")
    return {"action": action,
            "stdout_tail": " ".join(result.stdout.split()[-35:])}


def validate(value: dict[str, Any]) -> None:
    configure()
    final = value["final_product"]
    prelink = load(PRELINK_RECEIPT)
    actual = load(Path(str(PRG) + ".authority-input-consumption.json"))
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["prelink"] == bind(PRELINK_RECEIPT)
            and prelink["timing"] == "completed-before-authorized-product-link"
            and len(prelink["manifest"]["derived_constants"]) == 2
            and prelink["fail_closed_control"]["result"] ==
                "rejected-before-compiler"
            and len(prelink["mutations_rejected"]) == 8
            and CONSUMPTION.validate_authority_input_inventory(actual)
                ["constants"] == 2
            and value["successor_attribution"]["unexplained_members"] == 0
            and value["successor_attribution"]["phase00_build_id"]["r4"] ==
                "0x8c6cc520"
            and value["release_attribution"]["unexplained_members"] == 0
            and final["survival"]["status"] ==
                "PASS: BOTH RECORD CARRIERS SURVIVE ABORT RECOVERY"
            and final["positive_control"]["record"]["complete"] is True
            and value["artifacts_before"] == value["artifacts_after"] ==
                CARD.frozen_artifacts()
            and load(CARD.BASE.SCOPE_RESULT)["status"] == "PASS"
            and load(CARD.BASE.ACCEPTANCE_RESULT)["status"] == "PASS"
            and value["accounting"] == {"seed_WPLTOs": 1,
                "product_links_total": 3, "new_WPLTOs": 0,
                "new_product_links": 1, "media_builds": 0,
                "device_contacts": 0},
            "build-ID successor receipt drift")


def write_report(value: dict[str, Any]) -> None:
    diff = value["successor_attribution"]
    REPORT.write_text(f"""# v2.0 `$22` product build-ID authority rebind

Status: **{value['status']}**

The early device E25 was an authority mismatch, not damaged staging.  The
delivered 48-byte C2D header carries `0x8c6cc520`; r3's phase-0 decoder
compared `0x69496476`.  The historical implicit manifest default is removed:
an unbound product authority now fails before the compiler.

Before the sole successor link, the consolidated authority perturbed every
scalar leaf of the explicitly bound candidate manifest through the real
definition renderer.  It discovered two living embedded constants without a
case list: `LISP65_C2_PRODUCT_SHELF_BYTES` and
`LISP65_C2_PRODUCT_BUILD_ID`.  Their transported/generated source consumers,
both active force-include authorities, phase-owned output root, and symbolic
LOADADDR/MAP geometry were materialized in one prelink inventory.  Eight
sharp mutations are red, including absence of an authority and omission of a
derived constant or consumer.

The successor phase-0 code now carries compare sequence
`{diff['phase00_build_id']['r4_compare_sequence']}` for `0x8c6cc520`; the old
sequence is absent.  The r3→r4 difference has
{diff['PRG']['changed_bytes']} changed PRG bytes, all assigned to named
section owners, and zero unexplained section, symbol, relocation, program-
header or PRG members.  Scope and Acceptance then ran read-only over the
frozen successor pair.  No media or device contact was consumed; the bounded
`$22` session remains unspent.
""", encoding="utf-8")


def run() -> None:
    configure()
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout
    completion_unused = (not COMPLETION.exists()
        or (COMPLETION.is_dir() and not any(COMPLETION.iterdir())))
    require(clean == "" and completion_unused
            and PRELINK_RECEIPT.exists() and not DIFFERENCE.exists()
            and not RELEASE_DIFFERENCE.exists() and not RECEIPT.exists()
            and not REPORT.exists(),
            "build-ID successor requires committed sources and unused outputs")
    seed_before = {path.name: bind(path) for path in CARD.conversion_seed_files()}
    prelink = load(PRELINK_RECEIPT)
    require(prelink["timing"] == "completed-before-authorized-product-link"
            and CONSUMPTION.validate_authority_input_inventory(prelink)
                ["constants"] == 2,
            "sealed prelink authority inventory is not green")
    processes = CARD.resume_from_seed()
    actual = load(Path(str(PRG) + ".authority-input-consumption.json"))
    require(actual["manifest"]["derived_constants"] ==
                prelink["manifest"]["derived_constants"]
            and actual["derived_authority_categories"] ==
                prelink["derived_authority_categories"],
            "real link diverged from prelink authority population")
    release_diff = CARD.attribution()
    RELEASE_DIFFERENCE.write_bytes(CARD.canonical(release_diff))
    difference = successor_attribution()
    DIFFERENCE.write_bytes(CARD.canonical(difference))
    before = CARD.frozen_artifacts()
    gate, final_process = CARD.run_final_gate_child()
    processes.append(final_process)
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = CARD.frozen_artifacts()
    seed_after = {path.name: bind(path) for path in CARD.conversion_seed_files()}
    require(seed_before == seed_after and before == after
            and load(CARD.BASE.SCOPE_RESULT)["status"] == "PASS"
            and load(CARD.BASE.ACCEPTANCE_RESULT)["status"] == "PASS",
            "build-ID qualification changed frozen artifacts or ended red")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-31", "status": STATUS,
        "authority": authority(), "prelink": bind(PRELINK_RECEIPT),
        "actual_authority_inventory": bind(Path(str(PRG) +
            ".authority-input-consumption.json")),
        "frozen_seed_before": seed_before, "frozen_seed_after": seed_after,
        "predecessor": {"ELF": bind(OLD_ELF), "PRG": bind(OLD_PRG)},
        "successor_attribution": difference,
        "successor_attribution_receipt": bind(DIFFERENCE),
        "release_attribution": release_diff,
        "release_attribution_receipt": bind(RELEASE_DIFFERENCE),
        "final_product": gate, "scope": bind(CARD.BASE.SCOPE_RESULT),
        "acceptance": bind(CARD.BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "accounting": {"seed_WPLTOs": 1, "product_links_total": 3,
            "new_WPLTOs": 0, "new_product_links": 1,
            "media_builds": 0, "device_contacts": 0},
        "next": "independent review, then the still-unspent bounded $22 session",
    }
    RECEIPT.write_bytes(CARD.canonical(value))
    write_report(value)
    validate(value)
    print("v2.0 symbol22 build-ID rebind: PASS WPLTO=0 link=1 Scope=1 Acceptance=1")


def resume() -> None:
    """Finish attribution and qualification over the already-linked r4 pair."""
    configure()
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout
    linked = (PRG, ELF, Path(str(PRG) + ".map"), Path(str(PRG) + ".lto.o"),
              Path(str(PRG) + ".authority-input-consumption.json"))
    require(clean == "" and all(path.is_file() for path in linked)
            and PRELINK_RECEIPT.is_file() and RELEASE_DIFFERENCE.is_file()
            and DIFFERENCE.is_file() and not RECEIPT.exists()
            and not REPORT.exists() and not CARD.BASE.SCOPE_RESULT.exists()
            and not CARD.BASE.ACCEPTANCE_RESULT.exists(),
            "build-ID read-only resume lifecycle drift")
    seed_before = {path.name: bind(path) for path in CARD.conversion_seed_files()}
    prelink = load(PRELINK_RECEIPT)
    actual = load(Path(str(PRG) + ".authority-input-consumption.json"))
    require(CONSUMPTION.validate_authority_input_inventory(prelink)["constants"] == 2
            and CONSUMPTION.validate_authority_input_inventory(actual)
                ["constants"] == 2,
            "resume lost the two-axis authority inventory")
    release_diff = CARD.attribution()
    require(load(RELEASE_DIFFERENCE) == release_diff,
            "sealed release-to-r4 attribution drift")
    difference = successor_attribution()
    require(load(DIFFERENCE) == difference,
            "sealed r3-to-r4 attribution drift")
    before = CARD.frozen_artifacts()
    processes: list[dict[str, Any]] = [{
        "action": "consume-existing-authorized-r4-link",
        "product_link": bind(COMPLETION / "product-substitution-link.json"),
        "authority_inventory": bind(Path(str(PRG) +
            ".authority-input-consumption.json")),
        "new_WPLTOs": 0, "new_product_links": 0}]
    gate, final_process = CARD.run_final_gate_child()
    processes.append(final_process)
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = CARD.frozen_artifacts()
    seed_after = {path.name: bind(path) for path in CARD.conversion_seed_files()}
    require(seed_before == seed_after and before == after
            and load(CARD.BASE.SCOPE_RESULT)["status"] == "PASS"
            and load(CARD.BASE.ACCEPTANCE_RESULT)["status"] == "PASS",
            "read-only build-ID resume changed artifacts or ended red")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-31", "status": STATUS,
        "authority": authority(), "prelink": bind(PRELINK_RECEIPT),
        "actual_authority_inventory": bind(Path(str(PRG) +
            ".authority-input-consumption.json")),
        "frozen_seed_before": seed_before, "frozen_seed_after": seed_after,
        "predecessor": {"ELF": bind(OLD_ELF), "PRG": bind(OLD_PRG)},
        "successor_attribution": difference,
        "successor_attribution_receipt": bind(DIFFERENCE),
        "release_attribution": release_diff,
        "release_attribution_receipt": bind(RELEASE_DIFFERENCE),
        "final_product": gate, "scope": bind(CARD.BASE.SCOPE_RESULT),
        "acceptance": bind(CARD.BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "accounting": {"seed_WPLTOs": 1, "product_links_total": 3,
            "new_WPLTOs": 0, "new_product_links": 1,
            "media_builds": 0, "device_contacts": 0},
        "resume_accounting": {"new_WPLTOs": 0, "new_product_links": 0,
                              "new_cards": 0},
        "next": "independent review, then the still-unspent bounded $22 session",
    }
    RECEIPT.write_bytes(CARD.canonical(value))
    write_report(value)
    validate(value)
    print("v2.0 symbol22 build-ID rebind: READ-ONLY RESUME PASS "
          "WPLTO=0 link=0 Scope=1 Acceptance=1")


def reclose() -> None:
    """Rebind attribution to the sealed r3 ELF; never rerun qualification."""
    configure()
    expected_r3 = load(R3_SEALED_RECEIPT)["artifacts_after"]
    require(bind(OLD_ELF) == expected_r3["ELF"]
            and bind(OLD_PRG) == expected_r3["PRG"]
            and RECEIPT.is_file() and REPORT.is_file()
            and CARD.BASE.SCOPE_RESULT.is_file()
            and CARD.BASE.ACCEPTANCE_RESULT.is_file(),
            "r3/r4 read-only reclosure lifecycle drift")
    pair_before = CARD.frozen_artifacts()
    value = load(RECEIPT)
    difference = successor_attribution()
    DIFFERENCE.write_bytes(CARD.canonical(difference))
    value["predecessor"] = {"ELF": bind(OLD_ELF), "PRG": bind(OLD_PRG)}
    value["successor_attribution"] = difference
    value["successor_attribution_receipt"] = bind(DIFFERENCE)
    value["reclosure"] = {
        "reason": "local r3 ELF restored from SHA-identical accepted device-media twin",
        "sealed_r3_identity": expected_r3["ELF"],
        "new_WPLTOs": 0, "new_product_links": 0,
        "scope_runs": 0, "acceptance_runs": 0,
    }
    require(pair_before == CARD.frozen_artifacts()
            and load(CARD.BASE.SCOPE_RESULT)["status"] == "PASS"
            and load(CARD.BASE.ACCEPTANCE_RESULT)["status"] == "PASS",
            "attribution reclosure changed r4 or lost qualification")
    RECEIPT.write_bytes(CARD.canonical(value))
    write_report(value)
    validate(value)
    print("v2.0 symbol22 build-ID rebind: RECLOSE PASS "
          "r3=sealed r4=unchanged WPLTO=0 link=0")


def child(action: str) -> None:
    configure()
    if action == "_scope":
        CARD.BASE.scope_child()
    elif action == "_accept":
        CARD.BASE.acceptance_child()
    else:
        print("FIRST_FAULT_FINAL_GATE_JSON=" + json.dumps(
            CARD.final_gate(), sort_keys=True, separators=(",", ":")))


def check() -> None:
    validate(load(RECEIPT))
    print("v2.0 symbol22 build-ID rebind: CHECK PASS")


def selftest() -> None:
    value = load(RECEIPT)
    cases = {
        "silent-default-accepted": lambda x: x.update(
            prelink={"fail_closed_control": {"result": "accepted"}}),
        "authority-constant-lost": lambda x: x["successor_attribution"].update(
            unexplained_members=1),
        "stale-phase00-survives": lambda x: x["successor_attribution"]
            ["phase00_build_id"].update(r4="0x69496476"),
        "carrier-survival-lost": lambda x: x["final_product"]["survival"].update(
            status="FAIL"),
    }
    rejected: list[str] = []
    for name, mutation in cases.items():
        trial = deepcopy(value)
        mutation(trial)
        try:
            validate(trial)
        except (CARD.CardError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "build-ID receipt mutation survived")
    print(f"v2.0 symbol22 build-ID rebind: SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "resume", "reclose",
                                           "check", "selftest",
                                           "_scope", "_accept", "_final"))
    action = parser.parse_args().action
    if action == "run":
        run()
    elif action == "resume":
        resume()
    elif action == "reclose":
        reclose()
    elif action == "check":
        check()
    elif action == "selftest":
        selftest()
    else:
        child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CARD.CardError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"v2.0 symbol22 build-ID rebind: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
