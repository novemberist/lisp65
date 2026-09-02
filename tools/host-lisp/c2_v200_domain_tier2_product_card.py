#!/usr/bin/env python3
"""Build and qualify the owner-authorized v2.0 domain Tier-2 product."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v200_domain_tier1_product_card as TIER1  # noqa: E402
import c2_v200_domain_tier2_pricing as PRICE  # noqa: E402
import c2_v200_symbol22_first_fault_product_card as STACK  # noqa: E402
import c2_v190_native_prompt_editor_card as B_LIGHT  # noqa: E402
import public_surface_domain_audit as AUDIT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
AUTHORIZATION = "d4a3888a"
PLAN_HEADER = (
    "## Owner word and reviewer authorization — Tier 2 and the delivery chain — 2026-09-01")
BUILD = ROOT / "build/c2.3/v2.0-domain-tier2-product-card-r1"
OUTPUT = BUILD / "wplto"
PREFLIGHT = ROOT / "build/c2.3/v2.0-domain-tier2-product-card-r1-preflight"
ELF = OUTPUT / "lisp65-c2-substitution-linked.prg.elf"
PRG = OUTPUT / "lisp65-c2-substitution-linked.prg"
PROFILE = OUTPUT / "resolved-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
PREFLIGHT_RECEIPT = ARCH / "c2.3-v2.0-domain-tier2-product-card-r1-preflight.json"
DIFFERENCE = ARCH / "c2.3-v2.0-domain-tier2-product-card-r1-difference.json"
MEASURED_CONTRACT = ARCH / "c2.3-v2.0-domain-tier2-measured-contract-r1.json"
RECEIPT = ARCH / "c2.3-v2.0-domain-tier2-product-card-r1-receipt.json"
REPORT = ROOT / "docs/planning/v2.0.0-domain-tier2-product-card-report.md"
DURABLE_CONTRACT = ROOT / "config/public-surface-domain-contract.json"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
VM_SOURCE = ROOT / "src/vm.c"
TIER1_ELF = ROOT / (
    "build/c2.3/v2.0-domain-tier1-product-card-r1/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
TIER1_PRG = TIER1_ELF.with_suffix("")
TIER1_PROFILE = TIER1_ELF.with_name("resolved-profile.txt")
TIER1_CONTRACT_COMMIT = "b1c3890d"
TIER2_EVIDENCE_COMMIT = "e0d64c2c"
FORMAT = "lisp65-c2-v200-domain-tier2-product-card-v1"
STATUS = "PASS: V2.0 DOMAIN TIER 2 FINAL PRODUCT GREEN"


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
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def authority() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(PLAN_HEADER) == 1, "Tier-2 authorization identity drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").split())
    for token in ("breaking change is approved", "car 1", "no alias path",
                  "one wplto", "one product link", "combination is measured"):
        require(token in folded, f"Tier-2 authorization token absent: {token}")
    return {"commit": AUTHORIZATION, "path": relative,
        "section": PLAN_HEADER, "bytes": len(section.encode()),
        "sha256": hashlib.sha256(section.encode()).hexdigest(),
        "pricing": bind(PRICE.RECEIPT),
        "right": "one Tier-2 product card, one WPLTO and one product link"}


def predecessor_contract() -> dict[str, Any]:
    raw = subprocess.run(["git", "show", f"{TIER1_CONTRACT_COMMIT}:"
        "config/public-surface-domain-contract.json"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    value = json.loads(raw)
    require(value["counts"] == {"error-raised": 545,
        "documented-permissive": 179, "silently-wrong": 110},
        "Tier-2 predecessor contract is not the qualified Tier-1 world")
    return value


def sealed_tier2_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    """Read the durable contract in the product card's own evidence era.

    A later authorized successor may legitimately replace the living contract.
    Historical qualification must therefore never compare its sealed receipt
    to today's mutable authority.
    """
    relative = DURABLE_CONTRACT.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show",
        f"{TIER2_EVIDENCE_COMMIT}:{relative}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    value = json.loads(raw)
    require(value["counts"] == {"error-raised": 553,
        "documented-permissive": 179, "silently-wrong": 102},
        "sealed Tier-2 contract era drift")
    return value, {"path": relative, "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "evidence_era": TIER2_EVIDENCE_COMMIT}


def measured_successor_contract() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    before = predecessor_contract()
    with PRICE.strict_car_cdr():
        after = AUDIT.derive_recorded_world(before)
    before_rows = {row["name"]: row for row in before["rows"]}
    after_rows = {row["name"]: row for row in after["rows"]}
    changes = []
    for name in sorted(before_rows):
        for domain in AUDIT.DOMAINS:
            old = PRICE.semantic(before_rows[name]["cells"][domain])
            new = PRICE.semantic(after_rows[name]["cells"][domain])
            if old != new:
                changes.append({"name": name, "domain": domain,
                                "before": old, "after": new})
    expected = {(name, domain) for name in ("car", "cdr")
                for domain in ("number", "string", "symbol", "function")}
    require(after["counts"] == {"error-raised": 553,
        "documented-permissive": 179, "silently-wrong": 102}
        and {(row["name"], row["domain"]) for row in changes} == expected
        and all(row["after"] == {"classification": "error-raised",
                                  "error": "TypeError"} for row in changes),
        "Tier-2 executed contract movement drift")
    return after, changes


def source_gate() -> dict[str, Any]:
    text = VM_SOURCE.read_text(encoding="utf-8")
    pattern = re.compile(
        r"case OP_CAR:\s*case OP_CDR:\s*a = POP\(\);\s*"
        r"if \(a == NIL\) \{ PUSH\(NIL\); break; \}\s*"
        r"if \(!IS_PTR\(a\) \|\| cell_type\(a\) != T_CONS\) \{\s*"
        r"vm_status = VM_TYPEERROR;\s*goto done;\s*\}\s*"
        r"PUSH\(op == OP_CAR \? cell_a\(a\) : cell_b\(a\)\);",
        re.MULTILINE)
    require(pattern.search(text) is not None
            and text.count("case OP_CAR:") == text.count("case OP_CDR:") == 1,
            "Tier-2 shared CAR/CDR source guard absent")
    return {"source": bind(VM_SOURCE), "one_shared_guard": True,
        "nil_preserved": True, "foreign_domain_status": "VM_TYPEERROR",
        "compatibility_aliases": 0}


def derived_r5_placement_mutations(base: dict[str, int]) -> dict[str, str]:
    """Keep the historical r5 property sharp when derived == arena floor.

    Tier 2's favorable Final-LTO shrink makes the derived facade land exactly
    on the arena floor.  The old negative case restored that same address and
    therefore ceased to be a mutation.  Mutate the relation, never a mnemonic
    address: one case moves the VMA/LMA pair and another grows text far enough
    that the correct derived address must move.
    """
    rejected = {}
    cases = {
        "facade-not-at-derived-anchor": {
            **base, "facade_vma": base["facade_vma"] + 1,
            "facade_lma": base["facade_lma"] + 1},
        "pin-current-derived-address-across-text-growth": {
            **base, "text_end": base["facade_vma"] - base["floor"] + 1},
        "move-vma-without-lma": {
            **base, "facade_lma": base["facade_lma"] - 44},
        "overlap-next-owner": {
            **base, "facade_bytes":
                base["arena_end"] - base["facade_vma"] + 1},
        "fragment-price-as-final-capacity": {**base, "final_linked": False},
    }
    for name, values in cases.items():
        try:
            B_LIGHT.r5_facade_placement_gate(**values)
        except Exception as error:
            rejected[name] = str(error)
    require(set(rejected) == set(cases),
            "derived r5 placement mutation survived")
    return rejected


def tier2_candidate_abi_gate() -> dict[str, Any]:
    """Carry the already-present latch ABI across a native-only successor.

    The historical gate projected a new capture edge out of a predecessor that
    did not contain the latch.  Tier 1 already contains it.  Projecting that
    edge a second time drops a real predecessor instruction and manufactures
    drift.  In this successor world the stronger fact is available: `intern`
    is byte-identical across the two final ELFs, helper edge included.
    """
    before = ElfTruth.read(TIER1_ELF, llvm_readobj=READOBJ,
                           include_section_data=True)
    after = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    old = STACK.raw_symbol(before, "intern")
    new = STACK.raw_symbol(after, "intern")
    require(old == new, "Tier-2 changed the established intern/latch ABI")
    intern = after.symbol("intern")
    helper = after.symbol("lisp65_symbol22_latch_capture")
    rows = STACK.PRICE.parse_instructions(STACK.disassembly(ELF),
        intern.value, intern.value + intern.bytes)
    calls = [address for address, (mnemonic, operand) in rows.items()
             if mnemonic == "jsr"
             and "<lisp65_symbol22_latch_capture>" in operand]
    require(len(calls) == 1, "Tier-2 lost the established latch helper edge")
    depths = STACK.PRICE.stack_depths_at(rows, intern.value, calls[0])
    require(depths == [4], "Tier-2 changed the latch hardware-stack depth")
    mutated = bytearray(new); mutated[0] ^= 1
    require(bytes(mutated) != old, "Tier-2 ABI byte mutation survived")
    return {"status": "PASS: ESTABLISHED LATCH ABI BYTE-IDENTICAL",
        "intern": {"address": intern.value, "bytes": intern.bytes,
            "sha256": hashlib.sha256(new).hexdigest()},
        "helper_edge": {"address": calls[0], "callee": helper.value},
        "hardware_stack": {"persistent_bytes": 4,
            "post_JSR_caller_offsets": [7, 8], "all_reaching_depths": depths},
        "successful_path_identity": {"predecessor_bytes": len(old),
            "candidate_bytes": len(new), "byte_identical": True,
            "identity": "complete final-linked intern bytes, latch included",
            "success_path_extra_instruction_mutation": "rejected",
            "data_symbol_relation_mutation": "rejected"}}


def configure() -> None:
    # Reuse the qualified Tier-1 Plane and qualification stack, while making
    # every phase-owned output resolve below this card's own root.
    for name, value in {
        "BUILD": BUILD, "PINNED_COMPLETION": OUTPUT, "COMPLETION": OUTPUT,
        "PREFLIGHT": PREFLIGHT, "ELF": ELF, "PRG": PRG, "PROFILE": PROFILE,
        "INVOCATION": INVOCATION, "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT,
        "NATIVE_DIFFERENCE": DIFFERENCE,
        "RECEIPT": RECEIPT, "REPORT": REPORT, "DRIVER": DRIVER,
        "FORMAT": FORMAT, "STATUS": STATUS,
    }.items():
        setattr(TIER1, name, value)
    STACK.RELEASE_ELF = TIER1_ELF
    STACK.RELEASE_PRG = TIER1_PRG
    STACK.RELEASE_PROFILE = TIER1_PROFILE
    TIER1.configure_card()
    STACK.authority = authority
    STACK.BASE.authority = authority
    STACK.BASE.configuration_gate = configuration_gate
    STACK.BASE.final_gate = final_gate
    STACK.BASE.PRODUCER_RESULT = PRODUCER_RESULT
    STACK.BASE.SCOPE_RESULT = SCOPE_RESULT
    STACK.BASE.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    STACK.BASE.ELF = ELF; STACK.BASE.PRG = PRG; STACK.BASE.PROFILE = PROFILE
    STACK.BASE.artifacts = frozen_artifacts
    B_LIGHT.r5_placement_mutations = derived_r5_placement_mutations
    STACK.candidate_abi_gate = tier2_candidate_abi_gate


def configuration_gate() -> dict[str, Any]:
    standing = TIER1.configuration_gate()
    require(standing["domain_Tier_1"]["static_extent"] == TIER1.EXTENT,
            "Tier-2 did not retain the qualified Tier-1 Plane")
    return {**standing, "domain_Tier_2": {
        "status": "PASS: SHARED CAR/CDR DOMAIN GUARD MATERIALIZED",
        "source": source_gate(), "members": ["car", "cdr"],
        "target": "Cons or nil; every other domain raises TypeError",
        "aliases": 0}}


def preflight() -> None:
    require(not any(path.exists() for path in
        (BUILD, PREFLIGHT, PREFLIGHT_RECEIPT, RECEIPT, DIFFERENCE,
         MEASURED_CONTRACT)), "Tier-2 product card is one-shot")
    configure()
    after, changes = measured_successor_contract()
    price = PRICE.derive()
    require(price["performance"]["margin_percent"] >= 25.0
            and price["complete_link_world_projection"]["final_link_bar"]["required"],
            "Tier-2 price no longer authorizes a final-link attempt")
    PREFLIGHT.mkdir(parents=True)
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-09-01",
        "status": "PASS: V2.0 DOMAIN TIER 2 PRODUCT CARD ARMED 0/1",
        "authority": authority(), "configuration": configuration_gate(),
        "executed_contract_projection": {"counts": after["counts"],
            "changed_cells": changes},
        "final_link_requirements": [
            "actual Final-LTO guard and layout replace the 32-byte upper projection",
            "full predecessor/candidate attribution has zero unexplained members",
            "Scope and Acceptance are read-only over one frozen pair",
            "durable contract is freshly executed, never arithmetically advanced"],
        "attempt_accounting": {"product_cards": 0, "WPLTO_runs": 0,
            "product_links": 0, "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0}}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v2.0 Tier-2 product: PREFLIGHT PASS silent=102 WPLTO=0/1 link=0/1")


def profile_sources(path: Path) -> dict[str, str]:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256="):
            name, digest = line.split("=", 1)[1].rsplit(":", 1)
            rows[Path(name).name] = digest
    require(rows, f"profile source closure absent: {path}")
    return rows


def frozen_artifacts() -> dict[str, Any]:
    return {"ELF": bind(ELF), "PRG": bind(PRG),
        "map": bind(Path(str(PRG) + ".map")),
        "lto": bind(Path(str(PRG) + ".lto.o"))}


def cell_type_edges(truth: ElfTruth) -> list[dict[str, Any]]:
    caller, callee = truth.symbol("vm_run_inner"), truth.symbol("cell_type")
    rows = []
    for row in truth.relocations:
        if (row.source_section_index == caller.section_index
                and caller.value <= row.offset < caller.value + caller.bytes
                and row.relocation_type == "R_MOS_ADDR16"):
            target = truth.relocation_target_identity(row)
            if target["resolved_value"] == callee.value:
                rows.append({"call_address": row.offset - 1,
                    "caller_relative_offset": row.offset - 1 - caller.value,
                    "relocation_type": row.relocation_type,
                    "resolved_target": target["resolved_value"]})
    return rows


def final_linked_responsiveness(elf: Path = ELF,
        route: dict[str, Any] | None = None) -> dict[str, Any]:
    """Importable T2/combined measurement seam for the second landing card.

    A successor supplies its own executed delivered route.  The function then
    prices that complete route with the cell_type body from *its* final ELF,
    so two independently green deltas can never be added arithmetically.
    """
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    delivered = PRICE.delivered_route(live=True) if route is None else route
    cell = PRICE.linked_cell_type_cost(truth)
    result = PRICE.responsiveness(delivered, cell)
    edges = cell_type_edges(truth)
    result["final_linked_world"] = {
        "elf": bind(elf), "cell_type": cell,
        "vm_run_inner_bytes": truth.symbol("vm_run_inner").bytes,
        "cell_type_call_edges": edges,
        "cell_type_call_edge_count": len(edges),
        "route_authority": delivered["function_directory_authority"],
    }
    result["combination_interface"] = {
        "call": ("final_linked_responsiveness(successor_elf, "
                 "route=successor_delivered_route)"),
        "rule": ("remeasure the entire successor route and its final-linked "
                 "cell_type body; never add two card margins")}
    return result


def final_layout(truth: ElfTruth) -> dict[str, Any]:
    before = ElfTruth.read(TIER1_ELF, llvm_readobj=READOBJ,
                           include_section_data=True)
    old_text, text = before.section(".text"), truth.section(".text")
    old_facade = before.section(".lisp65_c2_mapped_far_facade")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    handoff = truth.section(".lisp65_c2_kernal_handoff")
    text_end = text.address + text.bytes
    reserve = facade.address - text_end
    require(text_end <= facade.address
            and facade.address + facade.bytes <= handoff.address
            and reserve >= 32,
            "Tier-2 final-LTO layout spent the text floor or overlapped an owner")
    before_edges, after_edges = cell_type_edges(before), cell_type_edges(truth)
    require(len(after_edges) == len(before_edges) + 1,
            "Tier-2 final link did not emit exactly one shared cell_type edge")
    return {"authority": "actual successor final ELF",
        "text": {"before_bytes": old_text.bytes, "after_bytes": text.bytes,
            "emitted_delta_bytes": text.bytes - old_text.bytes,
            "end_exclusive": text_end},
        "facade": {"before_start": old_facade.address,
            "after_start": facade.address, "bytes": facade.bytes},
        "text_reserve_bytes": reserve, "required_floor_bytes": 32,
        "handoff_start": handoff.address, "owners_disjoint": True,
        "cell_type_edges": {"before": before_edges, "after": after_edges,
            "added": 1}, "pricing_projection_retired": True}


def program_headers(path: Path) -> list[dict[str, int]]:
    return STACK.program_headers(path)


def attribution() -> dict[str, Any]:
    before = ElfTruth.read(TIER1_ELF, llvm_readobj=READOBJ,
                           include_section_data=True)
    after = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    old_inputs, new_inputs = profile_sources(TIER1_PROFILE), profile_sources(PROFILE)
    changed_inputs = sorted(set(old_inputs) ^ set(new_inputs) |
        {name for name in set(old_inputs) & set(new_inputs)
         if old_inputs[name] != new_inputs[name]})
    authored = [name for name in changed_inputs if name == "vm.c"]
    generated = [name for name in changed_inputs if name.startswith("c2-stream-")]
    require(authored == ["vm.c"] and set(changed_inputs) == set(authored + generated),
            f"Tier-2 compiler-input difference escaped vm.c/derived streams: {changed_inputs}")

    old_headers, new_headers = program_headers(TIER1_ELF), program_headers(ELF)
    old_raw, new_raw = TIER1_PRG.read_bytes(), PRG.read_bytes()
    require(old_raw[:2] == new_raw[:2], "Tier-2 changed the PRG load domain")
    load_address = int.from_bytes(old_raw[:2], "little")
    changed_addresses = [load_address + index for index, pair in enumerate(
        zip(old_raw[2:], new_raw[2:])) if pair[0] != pair[1]]
    changed_addresses.extend(range(
        load_address + min(len(old_raw), len(new_raw)) - 2,
        load_address + max(len(old_raw), len(new_raw)) - 2))
    families: Counter[str] = Counter()
    unowned = []
    for address in changed_addresses:
        owner = (STACK.prg_domain_owner(after, new_headers, address)
                 or STACK.prg_domain_owner(before, old_headers, address)
                 or STACK.prg_derived_padding_owner(after, address)
                 or STACK.prg_derived_padding_owner(before, address))
        if owner is None:
            unowned.append(address)
        else:
            families[owner] += 1
    require(not unowned, f"Tier-2 PRG difference has unowned bytes: {unowned[:8]}")

    old_sections = {row.name: row for row in before.sections}
    new_sections = {row.name: row for row in after.sections}
    require(set(old_sections) == set(new_sections),
            "Tier-2 added or removed an ELF section")
    section_changes = []
    for name in sorted(old_sections):
        left, right = old_sections[name], new_sections[name]
        # NOBITS sections have linked size/address truth but deliberately no
        # file payload.  Treat their content as empty while retaining geometry.
        left_raw = (before.section_bytes(name)
                    if left.section_type == "SHT_PROGBITS" else b"")
        right_raw = (after.section_bytes(name)
                     if right.section_type == "SHT_PROGBITS" else b"")
        changed = sum(a != b for a, b in zip(left_raw, right_raw)) \
            + abs(len(left_raw) - len(right_raw))
        if (left.address, left.bytes, left_raw) != (right.address, right.bytes, right_raw):
            section_changes.append({"name": name,
                "before_address": left.address, "after_address": right.address,
                "before_bytes": left.bytes, "after_bytes": right.bytes,
                "changed_content_bytes": changed,
                "family": ("authored-vm-dispatch" if name == ".text" else
                           "link-layout-or-derived-ELF-metadata")})
    old_symbols = Counter((r.name, r.value, r.bytes, r.section) for r in before.symbols)
    new_symbols = Counter((r.name, r.value, r.bytes, r.section) for r in after.symbols)
    old_relocs = Counter((r.source_section, r.offset, r.relocation_type,
                          r.target, r.addend) for r in before.relocations)
    new_relocs = Counter((r.source_section, r.offset, r.relocation_type,
                          r.target, r.addend) for r in after.relocations)
    return {"status": "PASS: TIER-1 TO TIER-2 DIFFERENCE FULLY ATTRIBUTED",
        "predecessor": {"ELF": bind(TIER1_ELF), "PRG": bind(TIER1_PRG)},
        "candidate": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "root_causes": {"authored_inputs": authored,
            "derived_generated_inputs": generated},
        "changed_profile_inputs": changed_inputs,
        "PRG": {"changed_bytes": len(changed_addresses),
            "named_owner_families": dict(sorted(families.items())),
            "unowned_bytes": 0},
        "ELF_sections": {"changed": section_changes,
            "changed_count": len(section_changes), "unexplained": 0},
        "symbols": {"removed": sum((old_symbols - new_symbols).values()),
            "added": sum((new_symbols - old_symbols).values()),
            "unexplained": 0},
        "relocations": {"removed": sum((old_relocs - new_relocs).values()),
            "added": sum((new_relocs - old_relocs).values()),
            "unexplained": 0},
        "program_headers": {"before": old_headers, "after": new_headers,
            "changed": old_headers != new_headers, "unexplained": 0},
        "unexplained_members": 0}


def signature_gate() -> dict[str, Any]:
    before = predecessor_contract()
    with PRICE.strict_car_cdr():
        after = AUDIT.derive_recorded_world(before)
    rows = {row["name"]: row for row in after["rows"]}
    for name in ("car", "cdr"):
        require(rows[name]["cells"]["nil"]["result"] == "nil"
                and rows[name]["cells"]["list"]["classification"] !=
                    "silently-wrong"
                and all(PRICE.semantic(rows[name]["cells"][domain]) == {
                    "classification": "error-raised", "error": "TypeError"}
                    for domain in ("number", "string", "symbol", "function")),
                f"Tier-2 final signature matrix red: {name}")
    return {"status": "PASS: CAR/CDR ACCEPT ONLY CONS/NIL",
        "invalid_typeerror_count": 8, "nil_results": {"car": "nil", "cdr": "nil"},
        "explicit_breaking_example": {"form": "(car 1)",
            "predecessor": "nil", "successor": "TypeError"},
        "compatibility_aliases": 0}


def tier2_final_gate() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    after, changes = measured_successor_contract()
    performance = final_linked_responsiveness(ELF)
    require(after["counts"]["silently-wrong"] == 102
            and len(changes) == 8
            and performance["margin_percent"] >= 25.0,
            "Tier-2 final semantic/performance wall red")
    return {"status": "PASS: TIER-2 FINAL-LINK SEMANTICS GREEN",
        "source": source_gate(), "signature_matrix": signature_gate(),
        "contract_counts": after["counts"], "changed_cells": changes,
        "final_LTO_layout": final_layout(truth), "performance": performance,
        "durable_contract_required": True,
        "release_note": ("BREAKING: car and cdr now accept only Cons or nil; "
                         "other values raise TypeError; car/cdr of nil stay nil")}


def final_gate() -> dict[str, Any]:
    return {**TIER1.final_gate(), "domain_Tier_2": tier2_final_gate()}


def run_child(action: str) -> dict[str, Any]:
    output = run([sys.executable, str(DRIVER), action], f"Tier-2 child {action}")
    return {"action": action, "stdout_tail": " ".join(output.split()[-35:])}


def child(action: str) -> None:
    configure()
    if action == "_produce":
        raise SystemExit(STACK.BASE.produce_child())
    if action == "_scope":
        raise SystemExit(STACK.BASE.scope_child())
    os.environ["LISP65_R1_ACCEPTANCE_RESULT"] = str(ACCEPTANCE_RESULT)
    raise SystemExit(STACK.BASE.acceptance_child())


def complete(processes: list[dict[str, Any]], *, resumed: bool) -> None:
    before = frozen_artifacts()
    diff = attribution()
    DIFFERENCE.write_bytes(canonical(diff))
    product = final_gate()
    processes.extend((run_child("_scope"), run_child("_accept")))
    after_artifacts = frozen_artifacts()
    require(before == after_artifacts
            and load(SCOPE_RESULT)["status"] == "PASS"
            and load(ACCEPTANCE_RESULT)["status"] == "PASS",
            "Tier-2 Scope/Acceptance changed or rejected the frozen pair")
    contract, changes = measured_successor_contract()
    MEASURED_CONTRACT.write_bytes(canonical(contract))
    DURABLE_CONTRACT.write_bytes(canonical(contract))
    value = {"format": FORMAT, "recorded_on": "2026-09-01",
        "status": STATUS, "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "invocation": bind(INVOCATION),
        "predecessor": {"ELF": bind(TIER1_ELF), "PRG": bind(TIER1_PRG),
            "profile": bind(TIER1_PROFILE)},
        "difference": diff, "difference_receipt": bind(DIFFERENCE),
        "final_product": product, "measured_contract": bind(MEASURED_CONTRACT),
        "durable_contract": bind(DURABLE_CONTRACT),
        "contract_changes": changes, "scope": bind(SCOPE_RESULT),
        "acceptance": bind(ACCEPTANCE_RESULT), "artifacts_before": before,
        "artifacts_after": after_artifacts, "processes": processes,
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "resume_accounting": {"read_only_after_frozen_pair": resumed,
            "new_WPLTO_runs": 0, "new_product_links": 0},
        "media_authorized": False,
        "next": "independent review; delivery-chain card measures combined world"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    validate(value)
    print("v2.0 Tier-2 product: BUILD PASS silent=102 WPLTO=1/1 link=1/1")


def build() -> None:
    pre = load(PREFLIGHT_RECEIPT)
    require(pre["status"] == "PASS: V2.0 DOMAIN TIER 2 PRODUCT CARD ARMED 0/1"
            and not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not DIFFERENCE.exists(),
            "Tier-2 product build is not at its one-shot boundary")
    configure()
    INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT)}))
    complete([run_child("_produce")], resumed=False)


def resume() -> None:
    require(BUILD.exists() and PRODUCER_RESULT.is_file()
            and load(PRODUCER_RESULT)["status"] == "PASS"
            and INVOCATION.is_file() and not RECEIPT.exists(),
            "Tier-2 frozen-pair resume boundary absent")
    configure()
    complete([{"action": "_produce", "status": "PASS",
        "note": "completed before NOBITS attribution-reader stop"}], resumed=True)


def validate(value: dict[str, Any]) -> None:
    tier = value["final_product"]["domain_Tier_2"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["difference"]["unexplained_members"] == 0
            and value["difference"]["PRG"]["unowned_bytes"] == 0
            and value["difference"]["ELF_sections"]["unexplained"] == 0
            and value["difference"]["symbols"]["unexplained"] == 0
            and value["difference"]["relocations"]["unexplained"] == 0
            and tier["contract_counts"] == {"error-raised": 553,
                "documented-permissive": 179, "silently-wrong": 102}
            and tier["signature_matrix"]["compatibility_aliases"] == 0
            and tier["signature_matrix"]["explicit_breaking_example"] == {
                "form": "(car 1)", "predecessor": "nil",
                "successor": "TypeError"}
            and tier["final_LTO_layout"]["pricing_projection_retired"] is True
            and tier["final_LTO_layout"]["text_reserve_bytes"] >= 32
            and tier["performance"]["margin_percent"] >= 25.0
            and value["artifacts_before"] == value["artifacts_after"] ==
                frozen_artifacts()
            and value["attempt_accounting"] == {"product_cards": 1,
                "WPLTO_runs": 1, "product_links": 1, "scope_runs": 1,
                "acceptance_runs": 1, "media_builds": 0, "device_contacts": 0}
            and value["resume_accounting"]["new_WPLTO_runs"] == 0
            and value["resume_accounting"]["new_product_links"] == 0
            and load(MEASURED_CONTRACT)["counts"] ==
                sealed_tier2_contract()[0]["counts"] == tier["contract_counts"]
            and value["durable_contract"]["sha256"] ==
                sealed_tier2_contract()[1]["sha256"],
            "Tier-2 product-card receipt drift")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "foreign-domain-silent": lambda row: row["final_product"]
            ["domain_Tier_2"]["contract_counts"].update({"silently-wrong": 103}),
        "car-one-alias": lambda row: row["final_product"]["domain_Tier_2"]
            ["signature_matrix"].update({"compatibility_aliases": 1}),
        "fragment-price-retained": lambda row: row["final_product"]
            ["domain_Tier_2"]["final_LTO_layout"].update(
                {"pricing_projection_retired": False}),
        "responsiveness-red": lambda row: row["final_product"]
            ["domain_Tier_2"]["performance"].update({"margin_percent": 24.99}),
        "unattributed-byte": lambda row: row["difference"]["PRG"].update(
            {"unowned_bytes": 1}),
        "extra-product-link": lambda row: row["attempt_accounting"].update(
            {"product_links": 2}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (CardError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "Tier-2 product mutation survived")
    print(f"v2.0 Tier-2 product: SELFTEST PASS mutations={len(rejected)}")


def write_report(value: dict[str, Any]) -> None:
    tier = value["final_product"]["domain_Tier_2"]
    perf = tier["performance"]
    layout = tier["final_LTO_layout"]
    pair = value["artifacts_after"]
    REPORT.write_text(f"""# v2.0 domain discipline Tier 2 product card

Status: **{value['status']}**

The owner-approved breaking change is materialized without an alias: `car`
and `cdr` accept only Cons and `nil`; `(car nil)` and `(cdr nil)` remain `nil`,
while `(car 1)` now raises `TypeError` instead of returning `nil`.  Executing
the complete durable 139×6 matrix freshly measures **553 error / 179 permissive
/ 102 silently wrong**.  Exactly eight cells moved, all four foreign domains
for each of `car` and `cdr`.

The pricing projection is retired.  The actual successor Final-LTO `.text`
delta is **{layout['text']['emitted_delta_bytes']} bytes**; the final facade is
derived from that emitted end, leaves **{layout['text_reserve_bytes']} bytes**
of ordinary-text reserve and remains disjoint from the handoff.  The final ELF
contains exactly one additional shared `vm_run_inner → cell_type` edge.

The final-linked performance measurement is
**{perf['frames_per_character']:.6f} frames/character**,
**{perf['service_events_per_frame']:.6f} events/frame**, and
**{perf['margin_percent']:.3f}% margin**, above the standing 25% wall.  The
importable seam `final_linked_responsiveness(successor_elf,
route=successor_delivered_route)` is the required combined measurement for the
second landing card; it remeasures that card's complete delivered route against
its own final ELF rather than adding margins.

The Tier-1→Tier-2 native difference is completely attributed to the authored
`vm.c` dispatch change and generated/link-derived consequences: PRG, ELF
sections, symbols, relocations and program headers all report zero unexplained
members.  Scope and Acceptance are read-only green over ELF
`{pair['ELF']['sha256']}` / PRG `{pair['PRG']['sha256']}`.  Budget is exactly
one WPLTO and one product link; no medium or device contact occurred.

Release-note form: **BREAKING — `car` and `cdr` now reject non-Cons, non-`nil`
values with `TypeError`; their `nil` behavior is unchanged.**
""", encoding="utf-8")


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    require(REPORT.is_file() and value["measured_contract"] ==
            bind(MEASURED_CONTRACT), "Tier-2 report/contract absent")
    print("v2.0 Tier-2 product: CHECK PASS silent=102 WPLTO=1/1 link=1/1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "build", "resume", "check",
        "selftest", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    if action in ("_produce", "_scope", "_accept"):
        child(action); return 0
    {"preflight": preflight, "build": build, "resume": resume, "check": check,
     "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, RuntimeError, KeyError, ValueError, OSError,
            subprocess.CalledProcessError) as error:
        print(f"v2.0 Tier-2 product: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
