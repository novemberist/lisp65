#!/usr/bin/env python3
"""Attribute fixed-address dependents of the mapped-far end symbols.

The phase-9 ABI candidate enlarged the mapped far-service without moving its
start VMA.  This desk gate distinguishes a real absolute consumer of either
end symbol from candidate-local ``start + size`` consistency checks.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
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

from elf_truth import ElfTruth  # noqa: E402
import c2_golden_layout_inversion as LAYOUT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
FINAL_RED = ARCH / (
    "c2.3-v2.1-phase9-abi-fix-replacement-card-final-red.json")
BUILD = ROOT / "build/c2.3/v2.1-phase9-abi-fix-replacement-card/wplto"
CANDIDATE_ELF = BUILD / "lisp65-c2-substitution-linked.prg.elf"
CANDIDATE_LINKER = BUILD / "c2-substitution.ld"
REFERENCE_ELF = ROOT / (
    "build/c2.3/v2.1-map-mask-fix-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
PREFLIGHT = ROOT / "build/c2.3/v2.1-phase9-abi-fix-replacement-preflight"
OWNERSHIP = PREFLIGHT / "candidate-ownership-contract.json"
FULL_MAP = PREFLIGHT / "candidate-full-map-contract.json"
ABI_CONTRACT = ROOT / "config/c2-mapped-far-abi-preservation-contract-v2.json"
OPT_IN = ROOT / "config/c2-v112-ownership-opt-in-closure.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()
RECEIPT = ARCH / (
    "c2.3-v2.1-phase9-service-end-dependency-attribution-receipt.json")

AUTHORIZATION = "b1dd0379"
RECORDED_ON = "2026-08-16"
FORMAT = "lisp65-c2.3-v2.1-phase9-service-end-dependency-attribution-v1"
STATUS = "ATTRIBUTED: mapped-far end symbols have no fixed-address dependent"

SECTION = ".lisp65_c2_mapped_far_service"
END = "__lisp65_c2_mapped_far_service_end"
LOAD_END = "__lisp65_c2_mapped_far_service_load_end"
SYMBOLS = (END, LOAD_END)
START = 0x78B2
LOAD_START = 0x2B8B2
OLD_BYTES = 874
NEW_BYTES = 1086
ARENA_END = 0x7E8D


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


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


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    authority = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode()
    text = " ".join(raw.lower().split())
    for token in ("dependency check, then reclassify",
                  "does anything reference `service_end`",
                  "without dependents, both end symbols reclassify",
                  "1,086/1,499 b",
                  "artifact-only replay"):
        require(token in text, f"service-end authority absent: {token}")
    return authority


def final_red() -> dict[str, Any]:
    value = load(FINAL_RED)
    require(
        value.get("status") == "FINAL RED: phase-9 replacement returns to owner"
        and value.get("retry_authorized") is False
        and value.get("owner_disposition_required") is True
        and value.get("attempt_accounting") == {
            "WPLTO_runs": 1, "completion_runs": 0, "device_contacts": 0,
            "media_builds": 0, "product_link_attempts": 1,
            "replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1},
        "phase-9 replacement Final Red authority drift")
    expected = value["artifacts"]["elf"]
    require(bind(ROOT / expected["path"]) == expected,
            "frozen candidate ELF identity drift")
    return value


def elf_facts(path: Path) -> dict[str, Any]:
    truth = ElfTruth.read(path, llvm_readobj=READOBJ)
    layout = LAYOUT.layout_from_elf(path)
    rows = {row["name"]: row for row in layout["allocatable_sections"]}
    section = rows[SECTION]
    symbols = {name: truth.symbol(name).value for name in SYMBOLS}
    relocations = {
        name: sorted({
            "source_section": row.source_section,
            "offset": row.offset,
            "type": row.relocation_type,
            "target": row.target,
        } for row in truth.relocations if row.target == name)
        for name in SYMBOLS}
    return {
        "section": {key: section[key] for key in
                    ("name", "vma", "lma", "bytes")},
        "symbols": symbols,
        "relocations": relocations,
    }


def candidate_contracts() -> dict[str, Any]:
    ownership = load(OWNERSHIP)
    full = load(FULL_MAP)
    successor = load(ABI_CONTRACT)["artifact_successor"]
    ledger = [row for row in full["fixed_simultaneous_live_ledger"]
              if row.get("owner") == "mapped-bank2-far-service"]
    require(len(ledger) == 1, "candidate far-service arena row is not unique")
    row = ledger[0]
    require(
        {key: successor[key] for key in (
            "cpu_end_exclusive", "cpu_vma", "exact_bytes",
            "physical_end_exclusive", "physical_lma", "section")} == {
                "cpu_end_exclusive": "0x7cf0", "cpu_vma": "0x78b2",
                "exact_bytes": 1086,
                "physical_end_exclusive": "0x0002bcf0",
                "physical_lma": "0x0002b8b2", "section": SECTION}
        and row["capacity_bytes"] == 1499
        and row["demand_bytes"] == NEW_BYTES
        and int(row["cpu_start"], 0) == START
        and int(row["owner_cpu_end_exclusive"], 0) == ARENA_END
        and int(row["service_cpu_end_exclusive"], 0) == START + NEW_BYTES
        and int(row["service_physical_end_exclusive"], 0)
            == LOAD_START + NEW_BYTES,
        "candidate far-service projection/capacity drift")
    return {
        "artifact_successor": successor,
        "arena": row,
        "ownership_contract": bind(OWNERSHIP),
        "full_map_contract": bind(FULL_MAP),
    }


def emitted_linker_contract() -> dict[str, Any]:
    text = " ".join(CANDIDATE_LINKER.read_text(encoding="utf-8").split())
    required = {
        "cpu_definition": (
            f"{END} = ADDR({SECTION}) + SIZEOF({SECTION});"),
        "load_definition": (
            f"{LOAD_END} = LOADADDR({SECTION}) + SIZEOF({SECTION});"),
        "candidate_consistency": (
            f"{END} == 0x7cf0 && {LOAD_END} == 0x0002bcf0"),
    }
    for label, fragment in required.items():
        require(fragment in text, f"emitted linker loses {label}")
    return {"definitions": {
                END: "ADDR(section)+SIZEOF(section)",
                LOAD_END: "LOADADDR(section)+SIZEOF(section)"},
            "independent_wall": (
                "mapped-bank2 arena capacity is enforced by the candidate "
                "full-map contract, not encoded as an end-symbol pin here"),
            "candidate_consistency_assertion":
                "end symbols equal candidate-projected successor contract",
            "fixed_numeric_consumer": False}


def source_mentions() -> dict[str, Any]:
    raw = subprocess.run(
        ["git", "ls-files", "-z", "src", "config", "scripts", "mk",
         "tools/host-lisp"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    files = [ROOT / item.decode() for item in raw.split(b"\0") if item]
    patterns = {
        "old_cpu_end": re.compile(r"(?i)(?:0x|\$)7c1c"),
        "new_cpu_end": re.compile(r"(?i)(?:0x|\$)7cf0"),
        "old_load_end": re.compile(r"(?i)(?:0x|\$)0*2bc1c"),
        "new_load_end": re.compile(r"(?i)(?:0x|\$)0*2bcf0"),
    }
    # Persist semantic membership, not source positions.  Line movement inside
    # an already classified evidence/contract owner is not a new dependent.
    hits: dict[str, set[str]] = {name: set() for name in patterns}
    for path in files:
        if path == DRIVER or path.suffix not in {
                ".c", ".h", ".s", ".S", ".py", ".json", ".ld", ".mk"}:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(lines, 1):
            for name, pattern in patterns.items():
                if pattern.search(line):
                    hits[name].add(path.relative_to(ROOT).as_posix())
    return {name: sorted(paths) for name, paths in hits.items()}


def derive() -> dict[str, Any]:
    red = final_red()
    old = elf_facts(REFERENCE_ELF)
    new = elf_facts(CANDIDATE_ELF)
    require(
        old["section"] == {"name": SECTION, "vma": START,
                           "lma": LOAD_START, "bytes": OLD_BYTES}
        and new["section"] == {"name": SECTION, "vma": START,
                               "lma": LOAD_START, "bytes": NEW_BYTES}
        and old["symbols"] == {END: START + OLD_BYTES,
                               LOAD_END: LOAD_START + OLD_BYTES}
        and new["symbols"] == {END: START + NEW_BYTES,
                               LOAD_END: LOAD_START + NEW_BYTES}
        and all(not rows for rows in new["relocations"].values()),
        "reference/candidate end-symbol geometry or relocation closure drift")
    contracts = candidate_contracts()
    linker = emitted_linker_contract()
    mentions = source_mentions()
    closure = load(OPT_IN)
    names = json.dumps(closure, sort_keys=True)
    require(all(symbol in names for symbol in SYMBOLS),
            "symbol identities absent from opt-in inventory")
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "claim": (
            "Both mapped-far end symbols are candidate freight boundaries. "
            "No relocation, vector or fixed media offset consumes either "
            "numeric value; capacity remains independently fixed."),
        "attribution": {
            "outcome": "NOT-INDEPENDENTLY-DEPENDED-UPON",
            "fixed_address_dependency_found": False,
            "symbols": {
                END: {"recommended_golden_class": "freight-derived-boundary",
                      "derivation": "section-vma-plus-bytes"},
                LOAD_END: {
                    "recommended_golden_class": "freight-derived-boundary",
                    "derivation": "section-lma-plus-bytes"}},
            "candidate_relocations": new["relocations"],
            "absolute_vector_consumers": [],
            "fixed_media_offset_consumers": [],
            "identity_inventory_is_numeric_dependency": False,
            "candidate_contract_assertions_are_independent_anchors": False,
        },
        "world_diff": {"reference": old, "candidate": new,
                       "authorized_growth_bytes": NEW_BYTES - OLD_BYTES,
                       "section_vma_changes": 0,
                       "end_symbol_delta_bytes": NEW_BYTES - OLD_BYTES},
        "candidate_contracts": contracts,
        "emitted_linker": linker,
        "capacity_invariant": {
            "arena_start": START, "arena_end_exclusive": ARENA_END,
            "capacity_bytes": ARENA_END - START,
            "candidate_demand_bytes": NEW_BYTES,
            "candidate_headroom_bytes": ARENA_END - START - NEW_BYTES,
            "status": "PASS"},
        "source_literal_audit": {
            "hits": mentions,
            "classification": (
                "Historical base-contract literals and historical evidence "
                "tools are not consumed as fixed candidate dependencies; the "
                "emitted linker consumes the projected candidate contracts.")},
        "execution_witness": {"ELFs_read": 2, "relocations_to_ends": 0,
            "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "authority": {"owner": authorization(), "Final_Red": bind(FINAL_RED),
            "reference_ELF": bind(REFERENCE_ELF),
            "candidate_ELF": bind(CANDIDATE_ELF),
            "candidate_linker": bind(CANDIDATE_LINKER),
            "ABI_successor_contract": bind(ABI_CONTRACT),
            "opt_in_identity_inventory": bind(OPT_IN), "driver": bind(DRIVER)},
    }


def validate(value: dict[str, Any]) -> None:
    expected = derive()
    require(value == expected, "service-end dependency attribution drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "invent-relocation-dependent": lambda x: x["attribution"][
            "candidate_relocations"][END].append({"target": END}),
        "invent-vector-dependent": lambda x: x["attribution"][
            "absolute_vector_consumers"].append("0x7cf0"),
        "invent-media-offset-dependent": lambda x: x["attribution"][
            "fixed_media_offset_consumers"].append("0x2bcf0"),
        "promote-cpu-end": lambda x: x["attribution"]["symbols"][END].update(
            recommended_golden_class="fixed-boundary"),
        "promote-load-end": lambda x: x["attribution"]["symbols"][
            LOAD_END].update(recommended_golden_class="fixed-boundary"),
        "dim-capacity": lambda x: x["capacity_invariant"].update(
            capacity_bytes=NEW_BYTES),
        "move-arena-wall": lambda x: x["capacity_invariant"].update(
            arena_end_exclusive=START + NEW_BYTES),
        "hide-growth": lambda x: x["world_diff"].update(
            authorized_growth_bytes=0),
        "authorize-wplto": lambda x: x["execution_witness"].update(
            WPLTO_runs=1),
        "claim-candidate-assertion-anchor": lambda x: x["attribution"].update(
            candidate_contract_assertions_are_independent_anchors=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "service-end attribution mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "service-end attribution receipt exists")
    value = derive(); validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 service-end attribution: PASS dependents=0 capacity=1086/1499")


def rebind() -> None:
    """Loudly bind successor evidence-tool mentions, never product facts."""
    value = load(RECEIPT)
    old_rejected = value.pop("mutations_rejected", None)
    value.get("authority", {}).pop("pre_rebind", None)
    expected = derive()
    comparison = deepcopy(expected)
    comparison["source_literal_audit"]["hits"] = value[
        "source_literal_audit"]["hits"]
    comparison["authority"]["driver"] = value["authority"]["driver"]
    require(value == comparison,
            "service-end rebind moved more than evidence mentions/driver")
    require(old_rejected is not None and len(old_rejected) == 10,
            "pre-rebind service-end mutation receipt drift")
    expected["authority"]["pre_rebind"] = {
        "driver": value["authority"]["driver"],
        "source_literal_audit_sha256": hashlib.sha256(canonical(
            value["source_literal_audit"]["hits"])).hexdigest()}
    # The additive lineage is part of the rebound receipt, not of the desk
    # attribution itself; validation continues to compare the semantic body.
    rebound = deepcopy(expected)
    lineage = rebound["authority"].pop("pre_rebind")
    validate(rebound)
    rebound["authority"]["pre_rebind"] = lineage
    rebound["mutations_rejected"] = mutations(expected)
    RECEIPT.write_bytes(canonical(rebound))
    print("2.1 service-end attribution: REBIND PASS product-change=0")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    value.get("authority", {}).pop("pre_rebind", None)
    validate(value)
    require(rejected == mutations(value),
            "service-end attribution mutation receipt drift")
    print("2.1 service-end attribution: CHECK PASS dependents=0 capacity=1086/1499")


def selftest() -> None:
    value = derive(); validate(value)
    require(len(mutations(value)) == 10,
            "service-end attribution mutation closure drift")
    print("2.1 service-end attribution: SELFTEST PASS mutations=10")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "rebind", "check", "selftest"))
    {"record": record, "rebind": rebind, "check": check, "selftest": selftest}[
        parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
