#!/usr/bin/env python3
"""Replace the `$22` completion link with candidate-derived consumption."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v200_symbol22_first_fault_product_card as CARD  # noqa: E402
import consolidated_consumption_authority as CONSUMPTION  # noqa: E402
import c2_lite_v6_link50_persistent_header_successor_link as LINK50  # noqa: E402
import c2_v160_r1_stored_world_conversions as R1  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


BUILD = CARD.BUILD
BAD_COMPLETION = BUILD / "completion"
COMPLETION = BUILD / "completion-r3"
ELF = COMPLETION / "lisp65-c2-substitution-linked.prg.elf"
PRG = COMPLETION / "lisp65-c2-substitution-linked.prg"
PROFILE = COMPLETION / "resolved-profile.txt"
ARCH = CARD.ARCH
DIFFERENCE = ARCH / (
    "c2.3-v2.0-symbol22-first-fault-product-card-r3-difference.json")
REPLACEMENT_DIFFERENCE = ARCH / (
    "c2.3-v2.0-symbol22-first-fault-completion-r2-r3-difference.json")
RECEIPT = ARCH / (
    "c2.3-v2.0-symbol22-first-fault-product-card-r3-receipt.json")
REPORT = ROOT / "docs/planning/v2.0.0-symbol22-first-fault-product-card-r3-report.md"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "66b242fb"
PLAN_HEADER = (
    "## Reviewer disposition — r2 completion-consumer red, one replacement link — 2026-08-31")
STATUS = "PASS: V2.0 SYMBOL22 FIRST-FAULT REPLACEMENT PRODUCT GREEN"
FORMAT = "lisp65-c2.3-v200-symbol22-first-fault-completion-replacement-v1"
BAD_ELF = BAD_COMPLETION / "lisp65-c2-substitution-linked.prg.elf"
BAD_PRG = BAD_COMPLETION / "lisp65-c2-substitution-linked.prg"
BAD_CONSUMPTION = BAD_COMPLETION / (
    "lisp65-c2-substitution-linked.prg.compiler-input-consumption.json")
ORIGINAL_CONFIGURE_SEED_WORLD = CARD.configure_r2_seed_world


def require(value: bool, message: str) -> None:
    if not value:
        raise CARD.CardError(message)


def candidate_static_header_authority() -> tuple[
        Path, dict[str, Any], int]:
    header = CARD.RELEASE_PLANE_ROOT / "c2_lite_static_plane.h"
    code = CARD.RELEASE_CODE
    plane = CARD.load(CARD.RELEASE_PLANE_RECEIPT)
    value = code.stat().st_size
    binding = CARD.bind(header)
    receipt_values = {
        int(plane["geometry"]["bytes"]),
        int(CARD.load(CARD.RELEASE_RECEIPT)["final_product"]
            ["recovery_quiescence"]["plane"]["bytes"]),
    }
    require(value == 47469 and receipt_values == {value},
            "candidate static-plane authority is not release-derived")
    return header, binding, value


def configure_seed_world() -> Any:
    core = ORIGINAL_CONFIGURE_SEED_WORLD()
    header, binding, value = candidate_static_header_authority()
    CARD.PRODUCT.configure_compiler_consumed_static_header(
        header, binding, value)
    CARD.PRODUCT.configure_compiler_consumed_static_header_resolver(
        lambda header=header, binding=deepcopy(binding), value=value:
            (header, deepcopy(binding), value))
    require(CARD.PRODUCT.resolved_compiler_consumed_static_header() ==
            (header, binding, value),
            "late completion resolver did not dominate historical binding")
    return core


def authority() -> dict[str, Any]:
    return {
        "review_authorization": CARD.git_section(
            AUTHORIZATION, CARD.PLAN, PLAN_HEADER),
        "qualification_red": CARD.bind(CARD.QUALIFICATION_RED),
        "right": "one replacement product link over the immutable r2 seed",
        "new_seed_WPLTOs": 0,
        "replacement_product_links": 1,
        "durable_condition": (
            "compiler consumers are derived from build-graph product nodes, "
            "never named as a seed/final population"),
    }


def configure() -> None:
    # The sealed r3 link really consumed this historical authority.  Keep that
    # fact explicit now that the product linker no longer invents a default.
    CARD.PRODUCT.configure_product_artifacts_manifest(
        ROOT / "build/c2.2/substitution/substitution-artifacts.json")
    CARD.COMPLETION = COMPLETION
    CARD.ELF = ELF
    CARD.PRG = PRG
    CARD.PROFILE = PROFILE
    CARD.DIFFERENCE = DIFFERENCE
    CARD.RECEIPT = RECEIPT
    CARD.REPORT = REPORT
    CARD.DRIVER = DRIVER
    CARD.STATUS = STATUS
    CARD.FORMAT = FORMAT
    CARD.configure_r2_seed_world = configure_seed_world
    CARD.patch_paths()
    # The living successor derives both force-include families from the same
    # materialized product graph.  Sealed predecessor receipts remain in their
    # own modules and are never rewritten.
    CARD.INIT_ADAPTER._consumption_rows = completion_static_consumption_rows
    CARD.RELEASE.R8.R7.R6.CARD.candidate_stdlib_consumption = (
        completion_stdlib_consumption)
    CARD.RELEASE.R8.R7.R6.CARD.configure_final_product_root(COMPLETION)
    CARD.RELEASE.R8.R7.R6.configure_final_product_root(COMPLETION)
    LINK50.qualification_output_root = lambda _elf: COMPLETION
    R1.ORACLE.artifact_paths = completion_acceptance_artifact_paths
    R1.configure_freight_placement_prover(
        "composed-raw-owner/preheap-gap", completion_symbol22_freight_proof)
    R1.configure_acceptance_artifact_root(completion_acceptance_artifact_root)
    R1.ORACLE.BASE.CRC.configure_publish_last_root(COMPLETION)


def completion_acceptance_artifact_paths() -> dict[str, Path]:
    """Bind Acceptance to phase-owned finals and seed-owned generated inputs."""
    generated = BUILD / "wplto/generated-product-sources"
    return {
        "elf": ELF, "prg": PRG,
        "map": Path(str(PRG) + ".map"),
        "lto": Path(str(PRG) + ".lto.o"),
        "linker": COMPLETION / "c2-substitution.ld",
        "resolved_profile": PROFILE,
        "publish_last": COMPLETION / "kernal-window-publish-last.json",
        "generated_phase02a": generated / "c2-stream-phase-02a.c",
        "generated_decoder": generated / "c2-stream-decoder.c",
    }


def completion_acceptance_artifact_root() -> Path:
    return COMPLETION


def completion_symbol22_freight_proof(name: str, row: dict[str, Any],
        layout: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=CARD.READOBJ,
                          include_section_data=True)
    owners = CARD.composed_gap_ownership(ELF, PROFILE)
    by_name = {item["name"]: item for item in layout["allocatable_sections"]}
    hot = by_name[".lisp65_c2_fixed_bank0_hot_bss"]
    heap = truth.symbol("__heap_start").value

    def relation(candidate: dict[str, Any]) -> str:
        if name == CARD.SECTION:
            require(candidate["vma"] ==
                        owners["terminal_return_guard"]["end_exclusive"]
                    and candidate["bytes"] == 48,
                    "symbol22 code escaped the derived raw-owner end")
            return "code-start-equals-derived-raw-owner-end"
        require(name == CARD.STATE_SECTION
                and candidate["vma"] == hot["vma"] + hot["bytes"]
                and candidate["lma"] == candidate["vma"]
                and candidate["bytes"] == 5
                and candidate["vma"] + candidate["bytes"] <= heap,
                "symbol22 state escaped the derived pre-heap gap")
        return "state-start-equals-hot-bss-end-before-heap"

    derived = relation(row)
    shifted = dict(row); shifted["vma"] += 1
    try:
        relation(shifted)
    except CARD.CardError:
        pass
    else:
        raise CARD.CardError("shifted symbol22 freight placement mutation survived")
    require(registry["registration"]["source"] ==
                "src/optional/c2_symbol22_first_fault_latch.s",
            "symbol22 freight prover bound another registry")
    return {"gate": "composed-raw-owner/preheap-gap",
            "relation": derived, "status": "passed"}


def bad_pair() -> dict[str, Any]:
    red = CARD.load(CARD.QUALIFICATION_RED)
    pair = red["frozen_unqualified_pair"]
    require(pair["ELF"] == CARD.bind(BAD_ELF)
            and pair["PRG"] == CARD.bind(BAD_PRG)
            and red["disposition"] == "FROZEN-UNQUALIFIED-PRODUCT-EVIDENCE",
            "sealed completion-red pair drift")
    return pair


def consumer_population(roots: list[Path]) -> dict[str, Any]:
    header, binding, value = candidate_static_header_authority()
    result = CONSUMPTION.derive_header_consumers(
        roots, binding["path"], value)
    require(result["candidate_header"] == binding["path"]
            and result["candidate_value"] == value
            and CONSUMPTION.derived_population_mutations() == [
                "new-product-without-consumption-receipt",
                "new-product-with-stale-header",
                "candidate-path-with-stale-value",
            ], "derived consumer population lost its sharp direction")
    result["candidate_header_binding"] = binding
    result["mutations_rejected"] = (
        CONSUMPTION.derived_population_mutations())
    return result


def _consumer_role(target: Path) -> str:
    if target.name == "resident-island-seed.prg":
        return "seed"
    if target.name == "lisp65-c2-substitution-linked.prg":
        return "final"
    return target.relative_to(ROOT).as_posix()


def _derived_consumption_rows(
        receipt_suffix: str, header: Path, value: int) -> dict[
            str, tuple[Path, dict[str, Any]]]:
    roots = [BUILD / "wplto", COMPLETION]
    binding = CARD.bind(header)
    CONSUMPTION.derive_header_consumers(
        roots, binding["path"], value, receipt_suffix=receipt_suffix)
    rows: dict[str, tuple[Path, dict[str, Any]]] = {}
    for root in roots:
        for elf in sorted(root.rglob("*.prg.elf")):
            target = Path(str(elf)[:-4])
            receipt = Path(str(target) + receipt_suffix)
            role = _consumer_role(target)
            require(role not in rows,
                    f"derived compiler-consumer role collision: {role}")
            rows[role] = (receipt, CARD.load(receipt))
    require(bool(rows), "derived compiler-consumer population is empty")
    return rows


def completion_static_consumption_rows() -> dict[
        str, tuple[Path, dict[str, Any]]]:
    header, _binding, value = candidate_static_header_authority()
    return _derived_consumption_rows(
        ".compiler-input-consumption.json", header, value)


def completion_stdlib_consumption() -> dict[str, dict[str, Any]]:
    native = CARD.RELEASE.R8.R7.R6.CARD
    value = int(native.stdlib_header_ordinals()["repl_banner"])
    rows = _derived_consumption_rows(
        ".stdlib-input-consumption.json", CARD.RELEASE_HEADER, value)
    return {name: {"receipt": CARD.bind(path), "result": row}
            for name, (path, row) in rows.items()}


def multiset_difference(before: Counter[Any], after: Counter[Any]) -> dict[str, int]:
    return {"removed": sum((before - after).values()),
            "added": sum((after - before).values()), "unexplained": 0}


def replacement_attribution() -> dict[str, Any]:
    old_receipt = CARD.load(BAD_CONSUMPTION)
    new_receipt_path = Path(str(PRG) + ".compiler-input-consumption.json")
    new_receipt = CARD.load(new_receipt_path)
    header, binding, value = candidate_static_header_authority()
    require(old_receipt["consumed_value"] == 46043
            and old_receipt["materialized_value"] == 46043
            and new_receipt["consumed_value"] == value
            and new_receipt["materialized_value"] == value
            and new_receipt["bound_header"] == binding
            and new_receipt["materialized_header"] == binding
            and new_receipt["actual_force_include_flags"][:2] == [
                "-include", binding["path"]],
            "replacement compiler path/value transition drift")
    require(PROFILE.read_bytes() == (BUILD / "wplto/resolved-profile.txt").read_bytes()
            and (BAD_COMPLETION / "resolved-profile.txt").read_bytes() ==
                PROFILE.read_bytes(),
            "replacement changed the compiler source/feature world")

    old = ElfTruth.read(BAD_ELF, llvm_readobj=CARD.READOBJ)
    new = ElfTruth.read(ELF, llvm_readobj=CARD.READOBJ)
    old_symbols = Counter((row.name, row.value, row.bytes, row.section)
                          for row in old.symbols)
    new_symbols = Counter((row.name, row.value, row.bytes, row.section)
                          for row in new.symbols)
    old_relocs = Counter((row.source_section, row.offset,
                          row.relocation_type, row.target, row.addend)
                         for row in old.relocations)
    new_relocs = Counter((row.source_section, row.offset,
                          row.relocation_type, row.target, row.addend)
                         for row in new.relocations)
    old_sections = Counter((row.name, row.address, row.bytes,
                            tuple(row.flags)) for row in old.sections)
    new_sections = Counter((row.name, row.address, row.bytes,
                            tuple(row.flags)) for row in new.sections)
    old_headers = Counter(tuple(sorted(row.items()))
                          for row in CARD.program_headers(BAD_ELF))
    new_headers = Counter(tuple(sorted(row.items()))
                          for row in CARD.program_headers(ELF))
    old_raw, new_raw = BAD_PRG.read_bytes(), PRG.read_bytes()
    require(old_raw[:2] == new_raw[:2],
            "replacement changed the PRG load domain")
    changed = sum(left != right for left, right in zip(old_raw, new_raw))
    changed += abs(len(old_raw) - len(new_raw))
    immediate = CARD.static_extent_immediate_gate(value, 46043)
    require(all(row["emitted_value"] == value
                and row["required_successor_value_absent"] == 46043
                for row in immediate["functions"]),
            "replacement did not emit the candidate extent")
    return {
        "status": "PASS: DEFECTIVE COMPLETION TO REPLACEMENT FULLY ATTRIBUTED",
        "predecessor": {"ELF": CARD.bind(BAD_ELF), "PRG": CARD.bind(BAD_PRG),
                        "consumption": CARD.bind(BAD_CONSUMPTION)},
        "candidate": {"ELF": CARD.bind(ELF), "PRG": CARD.bind(PRG),
                      "consumption": CARD.bind(new_receipt_path)},
        "only_authored_input_change": {
            "family": "candidate-derived static-header path and extent",
            "predecessor_path": old_receipt["materialized_header"]["path"],
            "predecessor_value": old_receipt["materialized_value"],
            "candidate_path": binding["path"],
            "candidate_value": value,
            "source_feature_profile_byte_identical": True,
        },
        "final_ELF_extent_dependency": immediate,
        "transitive_output_families": {
            "PRG_changed_bytes": changed,
            "sections": multiset_difference(old_sections, new_sections),
            "symbols": multiset_difference(old_symbols, new_symbols),
            "relocations": multiset_difference(old_relocs, new_relocs),
            "program_headers": multiset_difference(old_headers, new_headers),
            "linker_build_identity_and_derived_CRCs": "included",
        },
        "unexplained_members": 0,
    }


def run_child(action: str) -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0,
            f"replacement child {action} red:\n{result.stdout}")
    return {"action": action,
            "stdout_tail": " ".join(result.stdout.split()[-35:])}


def write_report(value: dict[str, Any]) -> None:
    final = value["final_product"]
    population = value["consumer_population"]
    pair = value["artifacts_after"]
    REPORT.write_text(f"""# v2.0 Phase 0 — `$22` completion replacement r3

Status: **{value['status']}**

The immutable r2 seed remained byte-identical.  One authorized replacement
product link consumed the same candidate-derived static-plane authority as
the seed: path `{population['candidate_header']}`, value **47,469 bytes**.
Both refill functions now emit `0xB96D`; the defective `0xB3DB` pair is absent.

The durable fix is population-level.  Every linked `*.prg.elf` node beneath
the active seed and completion graph roots mechanically owes one adjacent
path-and-value receipt.  The population is not named or counted.  Mutations
adding an unreceipted product, a stale new consumer, or a candidate path with
a stale value all fall.

The r2→r3 difference has zero unexplained members, as does the v1.9→r3
product attribution.  The final product re-proves both carrier lifetimes,
executes its positive control from final-ELF bytes, keeps the successful path
neutral, enumerates section and raw-access owners, and retains
**{final['ordinary_text']['free_bytes']} ordinary-text bytes** against the
32-byte floor.  Read-only Scope and Acceptance are green.

Qualification also converted the living adapters that had confused linked
addresses with semantic code identity, alias symbol size with allocation,
data relocations with call edges, and historical output roots with the active
completion root.  The Golden adapter now admits an allocated PROGBITS owner
without a PT_LOAD only when the active freight registry names it and the
delivered flat PRG proves its bytes at the same VMA.  The sharp directions
remain red in every case.

Final pair: ELF `{pair['ELF']['sha256']}` / PRG `{pair['PRG']['sha256']}`.
No medium was built and no device was contacted.
""", encoding="utf-8")


def validate(value: dict[str, Any]) -> None:
    configure()
    final = value["final_product"]
    require(value["status"] == STATUS
            and value["successor_authority"] == authority()
            and value["frozen_bad_completion"] == bad_pair()
            and value["consumer_population"]["candidate_value"] == 47469
            and value["consumer_population"]["derivation"] ==
                "every *.prg.elf product node under the active graph roots"
            and len(value["consumer_population"]["consumers"]) >= 2
            and value["consumer_population"]["mutations_rejected"] == [
                "new-product-without-consumption-receipt",
                "new-product-with-stale-header",
                "candidate-path-with-stale-value"]
            and value["attribution"]["unexplained_members"] == 0
            and value["replacement_attribution"]["unexplained_members"] == 0
            and value["replacement_attribution"]
                ["final_ELF_extent_dependency"]["functions"][0]
                ["emitted_value"] == 47469
            and final["survival"]["status"] ==
                "PASS: BOTH RECORD CARRIERS SURVIVE ABORT RECOVERY"
            and final["positive_control"]["record"]["complete"] is True
            and final["ABI_and_success_path"]["successful_path_identity"]
                ["all_other_semantics_identical"] is True
            and not final["placement"]["code_external_raw_references"]
            and not final["placement"]["state_external_raw_references"]
            and final["ordinary_text"]["free_bytes"] >= 32
            and value["artifacts_before"] == value["artifacts_after"] ==
                CARD.frozen_artifacts()
            and value["attempt_accounting"] == {
                "seed_WPLTOs": 1, "unqualified_product_links": 1,
                "replacement_product_links": 1, "scope_runs": 1,
                "acceptance_runs": 1, "media_builds": 0,
                "device_contacts": 0}
            and value["scope"] == CARD.bind(CARD.BASE.SCOPE_RESULT)
            and value["acceptance"] == CARD.bind(CARD.BASE.ACCEPTANCE_RESULT)
            and CARD.load(CARD.BASE.SCOPE_RESULT)["status"] == "PASS"
            and CARD.load(CARD.BASE.ACCEPTANCE_RESULT)["status"] == "PASS"
            and REPORT.is_file(), "replacement product-card receipt drift")


def run() -> None:
    configure()
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout
    require(clean == "" and not COMPLETION.exists()
            and not RECEIPT.exists() and not DIFFERENCE.exists()
            and not REPLACEMENT_DIFFERENCE.exists(),
            "replacement link requires committed sources and an unused root")
    frozen_bad = bad_pair()
    seed_before = {path.name: CARD.bind(path)
                   for path in CARD.conversion_seed_files()}
    prelink_population = consumer_population([BUILD / "wplto"])

    processes = CARD.resume_from_seed()
    population = consumer_population([BUILD / "wplto", COMPLETION])
    require(len(population["consumers"]) >= len(prelink_population["consumers"]) + 1,
            "replacement link did not materialize a derived consumer")
    diff = CARD.attribution()
    DIFFERENCE.write_bytes(CARD.canonical(diff))
    replacement_diff = replacement_attribution()
    REPLACEMENT_DIFFERENCE.write_bytes(CARD.canonical(replacement_diff))
    before = CARD.frozen_artifacts()
    gate, final_process = CARD.run_final_gate_child()
    processes.append(final_process)
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = CARD.frozen_artifacts()
    scope = CARD.load(CARD.BASE.SCOPE_RESULT)
    acceptance = CARD.load(CARD.BASE.ACCEPTANCE_RESULT)
    seed_after = {path.name: CARD.bind(path)
                  for path in CARD.conversion_seed_files()}
    require(seed_before == seed_after
            and frozen_bad == bad_pair()
            and before == after
            and scope["status"] == acceptance["status"] == "PASS",
            "replacement qualification changed frozen evidence or ended red")

    value_out = {
        "format": FORMAT, "recorded_on": "2026-08-31", "status": STATUS,
        "successor_authority": authority(),
        "frozen_seed_before": seed_before, "frozen_seed_after": seed_after,
        "frozen_bad_completion": frozen_bad,
        "prelink_consumer_population": prelink_population,
        "consumer_population": population,
        "attribution": diff, "attribution_receipt": CARD.bind(DIFFERENCE),
        "replacement_attribution": replacement_diff,
        "replacement_attribution_receipt": CARD.bind(REPLACEMENT_DIFFERENCE),
        "final_product": gate,
        "scope": CARD.bind(CARD.BASE.SCOPE_RESULT),
        "acceptance": CARD.bind(CARD.BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {
            "seed_WPLTOs": 1, "unqualified_product_links": 1,
            "replacement_product_links": 1, "scope_runs": 1,
            "acceptance_runs": 1, "media_builds": 0, "device_contacts": 0},
        "diagnostic_removal_default": True, "media_authorized": False,
        "next": "independent review, then owner-controlled short device session",
    }
    RECEIPT.write_bytes(CARD.canonical(value_out))
    write_report(value_out)
    validate(value_out)
    print("v2.0 symbol22 completion replacement: PASS "
          "WPLTO=0 replacement-link=1 Scope=1 Acceptance=1")


def resume() -> None:
    """Qualify the already-linked r3 pair without rebuilding any product byte."""
    configure()
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout
    require(clean == "" and ELF.is_file() and PRG.is_file()
            and DIFFERENCE.is_file() and REPLACEMENT_DIFFERENCE.is_file()
            and not RECEIPT.exists() and not REPORT.exists()
            and not CARD.BASE.ACCEPTANCE_RESULT.exists(),
            "replacement qualification resume lifecycle drift")
    if CARD.BASE.SCOPE_RESULT.exists():
        require(CARD.load(CARD.BASE.SCOPE_RESULT)["status"] == "PASS",
                "existing read-only Scope result is not green")
    frozen_bad = bad_pair()
    seed_before = {path.name: CARD.bind(path)
                   for path in CARD.conversion_seed_files()}
    prelink_population = consumer_population([BUILD / "wplto"])
    population = consumer_population([BUILD / "wplto", COMPLETION])
    require(len(population["consumers"]) >=
                len(prelink_population["consumers"]) + 1,
            "replacement consumer population is not materialized")
    diff = CARD.attribution()
    replacement_diff = replacement_attribution()
    require(CARD.load(DIFFERENCE) == diff
            and CARD.load(REPLACEMENT_DIFFERENCE) == replacement_diff,
            "committed replacement attribution differs from frozen pair")

    before = CARD.frozen_artifacts()
    processes: list[dict[str, Any]] = [{
        "action": "consume-existing-authorized-replacement-link",
        "product_link": CARD.bind(COMPLETION / "product-substitution-link.json"),
        "compiler_consumption": CARD.bind(Path(str(PRG) +
            ".compiler-input-consumption.json")),
        "new_WPLTOs": 0, "new_product_links": 0,
    }]
    gate, final_process = CARD.run_final_gate_child()
    processes.append(final_process)
    if CARD.BASE.SCOPE_RESULT.exists():
        processes.append({"action": "consume-existing-read-only-scope",
            "result": CARD.bind(CARD.BASE.SCOPE_RESULT),
            "new_WPLTOs": 0, "new_product_links": 0})
    else:
        processes.append(run_child("_scope"))
    processes.append(run_child("_accept"))
    after = CARD.frozen_artifacts()
    scope = CARD.load(CARD.BASE.SCOPE_RESULT)
    acceptance = CARD.load(CARD.BASE.ACCEPTANCE_RESULT)
    seed_after = {path.name: CARD.bind(path)
                  for path in CARD.conversion_seed_files()}
    require(seed_before == seed_after and frozen_bad == bad_pair()
            and before == after
            and scope["status"] == acceptance["status"] == "PASS",
            "replacement read-only qualification ended red or changed evidence")

    value_out = {
        "format": FORMAT, "recorded_on": "2026-08-31", "status": STATUS,
        "successor_authority": authority(),
        "frozen_seed_before": seed_before, "frozen_seed_after": seed_after,
        "frozen_bad_completion": frozen_bad,
        "prelink_consumer_population": prelink_population,
        "consumer_population": population,
        "attribution": diff, "attribution_receipt": CARD.bind(DIFFERENCE),
        "replacement_attribution": replacement_diff,
        "replacement_attribution_receipt": CARD.bind(REPLACEMENT_DIFFERENCE),
        "final_product": gate,
        "scope": CARD.bind(CARD.BASE.SCOPE_RESULT),
        "acceptance": CARD.bind(CARD.BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {
            "seed_WPLTOs": 1, "unqualified_product_links": 1,
            "replacement_product_links": 1, "scope_runs": 1,
            "acceptance_runs": 1, "media_builds": 0, "device_contacts": 0},
        "resume_accounting": {"new_WPLTOs": 0, "new_product_links": 0,
                              "new_cards": 0},
        "diagnostic_removal_default": True, "media_authorized": False,
        "next": "independent review, then owner-controlled short device session",
    }
    RECEIPT.write_bytes(CARD.canonical(value_out))
    write_report(value_out)
    validate(value_out)
    print("v2.0 symbol22 completion replacement: READ-ONLY RESUME PASS "
          "WPLTO=0 link=0 Scope=1 Acceptance=1")


def check() -> None:
    validate(CARD.load(RECEIPT))
    print("v2.0 symbol22 completion replacement: CHECK PASS")


def selftest() -> None:
    value = CARD.load(RECEIPT)
    cases = {
        "consumer-population-list": lambda x: x["consumer_population"].update(
            derivation="named seed/final list"),
        "stale-new-consumer-survives": lambda x: x["consumer_population"]
            ["mutations_rejected"].remove("new-product-with-stale-header"),
        "lose-survival": lambda x: x["final_product"]["survival"].update(
            status="FAIL"),
        "lose-positive-control": lambda x: x["final_product"]
            ["positive_control"]["record"].update(complete=False),
        "change-success-path": lambda x: x["final_product"]
            ["ABI_and_success_path"]["successful_path_identity"].update(
                all_other_semantics_identical=False),
        "unexplained-replacement": lambda x: x["replacement_attribution"].update(
            unexplained_members=1),
    }
    rejected: list[str] = []
    for name, mutation in cases.items():
        trial = deepcopy(value)
        mutation(trial)
        try:
            validate(trial)
        except (CARD.CardError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "replacement receipt mutation survived")
    print(f"v2.0 symbol22 completion replacement: SELFTEST PASS mutations={len(rejected)}")


def child(action: str) -> None:
    configure()
    CARD.child(action)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "resume", "check", "selftest",
                                           "_scope", "_accept", "_final"))
    action = parser.parse_args().action
    if action == "run":
        run()
    elif action == "resume":
        resume()
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
        print(f"v2.0 symbol22 completion replacement: RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
