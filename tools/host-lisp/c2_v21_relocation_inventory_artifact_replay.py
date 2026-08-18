#!/usr/bin/env python3
"""Qualify the frozen root-fix link with candidate-derived RELA counts."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v20_vma_golden_review_rebind_20260816 as VMA_REBIND  # noqa: E402
import c2_v21_probe_oracle_root_padding_replacement_card as CARD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
FINAL_RED = CARD.FINAL_RED
ATTRIBUTION = ARCH / (
    "c2.3-v2.1-probe-oracle-root-padding-replacement-red-attribution-receipt.json")
BUILD = CARD.BUILD
SEED = BUILD / "wplto/resident-island-seed.prg"
ELF = Path(str(SEED) + ".elf")
LTO = Path(str(SEED) + ".lto.o")
MAP = Path(str(SEED) + ".map")
REPLAY = BUILD / "relocation-artifact-replay"
PREFLIGHT = REPLAY / "preflight.json"
INVENTORY_REPORT = REPLAY / "final-section-inventory.json"
LTO_REPORT = REPLAY / "lto-partition-metadata.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-relocation-inventory-artifact-replay-receipt.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "da4bf9f5"
RECORDED_ON = "2026-08-16"


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


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


def git_bind(commit: str, path: Path) -> tuple[bytes, dict[str, Any]]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return raw, {"authority": "git-blob", "commit": full, "path": name,
                 "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    raw, value = git_bind(AUTHORIZATION, PLAN)
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("relocation derivation and replay authorized",
                  "size and count for `.rela.lisp65_c2_mapped_far_facade`",
                  "derive from the candidate",
                  "name, address and flags stay fixed contract",
                  "artifact-only qualification replay",
                  "no wplto, no relink, no card"):
        require(token in text, f"relocation replay authority absent: {token}")
    return value


def final_red() -> dict[str, Any]:
    value = load(FINAL_RED)
    message = value.get("error", {}).get("message", "")
    require(
        value.get("status") ==
            "FINAL RED: root-padding replacement returns to owner"
        and value.get("retry_authorized") is False
        and value.get("owner_disposition_required") is True
        and value.get("attempt_accounting", {}).get("WPLTO_runs") == 1
        and value.get("attempt_accounting", {}).get(
            "product_link_attempts") == 1
        and message.count(
            "full-map-owner-size:.rela.lisp65_c2_mapped_far_facade") == 1
        and message.count("missing=[]; additional=[]") == 1,
        "root-padding Final Red authority drift")
    return value


def attribution() -> dict[str, Any]:
    value = load(ATTRIBUTION)
    require(
        value.get("status") ==
            "FINAL-RED-ATTRIBUTED: FACADE-RELOCATION-SNAPSHOT-PIN"
        and value.get("mechanism", {}).get("facade_relocations", {}).get(
            "replacement_records") == 14
        and value["mechanism"]["facade_relocations"]["Link112_records"] == 21
        and value["classification"]["geometry_red"] is False
        and value["classification"]["capacity_red"] is False,
        "relocation Final Red attribution drift")
    return value


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    expected = attribution()["authority"]
    current = {
        "candidate_PRG": bind(SEED),
        "candidate_ELF": bind(ELF),
        "candidate_map": bind(MAP),
        "candidate_LTO": bind(LTO),
    }
    require(all(current[name] == expected[name] for name in current),
            "frozen linked root-fix artifact drift")
    return current


def owner_rows() -> list[dict[str, object]]:
    contract = load(CARD.PROJECTED_FULL_MAP)
    raw = contract["generated_linker_requirements"][
        "final_section_inventory_additions"]
    require(isinstance(raw, list) and len(raw) == 7,
            "projected full-map owner inventory drift")
    rows: list[dict[str, object]] = []
    for item in raw:
        name = str(item["name"])
        rows.append({
            "name": name,
            "address": int(str(item["address"]), 0),
            "bytes": int(item["bytes"]),
            "flags": tuple(str(flag) for flag in item["required_flags"]),
            "size_policy": (
                "candidate-derived-relocation-records"
                if name.startswith(".rela.") else "fixed-contract"),
        })
    return rows


def section_rows() -> list[dict[str, object]]:
    truth = ElfTruth.read(ELF, llvm_readobj=PRODUCT.TOOLCHAIN / "llvm-readobj")
    return [{"name": row.name, "address": row.address, "bytes": row.bytes,
             "type": row.section_type, "flags": list(row.flags)}
            for row in truth.sections if row.name]


def inventory_gate(
        sections_override: list[dict[str, object]] | None = None,
        owners_override: list[dict[str, object]] | None = None
        ) -> dict[str, Any]:
    sections = section_rows() if sections_override is None else sections_override
    owners = owner_rows() if owners_override is None else owners_override
    # The consumed card already established the complete section-name set:
    # its sole violation carried missing=[] and additional=[].  This replay
    # changes only the owner-size policy which stopped that exact ELF.
    expected = [str(row["name"]) for row in sections]
    violations = PRODUCT._final_section_inventory_violations(
        expected, sections, owners)
    require(not violations, f"candidate-derived inventory red: {violations}")
    by_name = {str(row["name"]): row for row in sections}
    relocation = []
    for owner in owners:
        if owner["size_policy"] != "candidate-derived-relocation-records":
            continue
        row = by_name[str(owner["name"])]
        relocation.append({
            "name": owner["name"], "address": row["address"],
            "flags": sorted(row["flags"]),
            "contract_snapshot_bytes": owner["bytes"],
            "candidate_derived_bytes": row["bytes"],
            "candidate_derived_records": int(row["bytes"]) // 12,
            "record_bytes": 12,
        })
    return {
        "status": "PASS: relocation size/count derived from candidate",
        "inherited_name_set": "original-card-exact-missing-0-additional-0",
        "fixed_contract_fields": ["name", "address", "flags"],
        "candidate_derived_fields": ["bytes", "record_count"],
        "relocation_sections": relocation,
        "non_relocation_owner_count": sum(
            row["size_policy"] == "fixed-contract" for row in owners),
        "violations": violations,
    }


def inventory_mutations() -> list[str]:
    sections = section_rows()
    owners = owner_rows()
    facade = ".rela.lisp65_c2_mapped_far_facade"
    index = next(i for i, row in enumerate(sections) if row["name"] == facade)
    owner_index = next(i for i, row in enumerate(owners)
                       if row["name"] == facade)
    cases: dict[str, Callable[[], None]] = {}

    def expect_red(name: str, rows: list[dict[str, object]],
                   owner_values: list[dict[str, object]] = owners) -> None:
        try:
            inventory_gate(rows, owner_values)
        except ReplayError:
            return
        raise ReplayError(f"relocation inventory mutation survived: {name}")

    pinned = deepcopy(owners)
    pinned[owner_index]["size_policy"] = "fixed-contract"
    cases["restore-21-record-count-pin"] = lambda: expect_red(
        "restore-21-record-count-pin", sections, pinned)
    for field, value in (("name", facade + ".old"), ("address", 1),
                         ("flags", [])):
        trial = deepcopy(sections)
        trial[index][field] = value
        cases[f"mutate-fixed-{field}"] = (
            lambda name=f"mutate-fixed-{field}", rows=trial:
            expect_red(name, rows))
    malformed = deepcopy(sections)
    malformed[index]["bytes"] = 167
    cases["partial-rela-record"] = lambda: expect_red(
        "partial-rela-record", malformed)

    # The exact predecessor count remains legal because it is freight, not a
    # fixed acceptance value.  Rejecting it would be a renamed count pin.
    predecessor_count = deepcopy(sections)
    predecessor_count[index]["bytes"] = 252
    inventory_gate(predecessor_count, owners)

    rejected: list[str] = []
    for name, action in cases.items():
        action()
        rejected.append(name)
    require(rejected == list(cases), "relocation inventory mutation drift")
    return rejected


def _function_text(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next((row for row in tree.body
                 if isinstance(row, ast.FunctionDef) and row.name == name), None)
    require(node is not None, f"function absent: {name}")
    return ast.unparse(node)


def source_gate() -> dict[str, Any]:
    owner = _function_text(Path(PRODUCT.__file__),
                           "_full_map_final_section_owners")
    checker = _function_text(Path(PRODUCT.__file__),
                             "_final_section_inventory_violations")
    combined = owner + "\n" + checker
    require(
        "candidate-derived-relocation-records" in owner
        and "name.startswith('.rela.')" in owner
        and "int(row['bytes']) % 12 != 0" in checker
        and all(token not in combined for token in (
            "== 14", "== 21", "== 168", "== 252")),
        "final inventory source retains a relocation record-count pin")
    return {
        "status": "PASS: relocation verifier is born candidate-derived",
        "record_count_pins": 0,
        "record_shape": "positive whole ELF32 RELA records",
        "fixed_contract_fields": ["name", "address", "flags"],
    }


def lto_metadata_gate() -> dict[str, Any]:
    lto = PRODUCT._readobj_sections(LTO)
    final = PRODUCT._readobj_sections(ELF)
    violations = PRODUCT._lto_partition_metadata_violations(lto, final)
    require(not violations, f"frozen LTO metadata tail red: {violations}")
    return {
        "status": "PASS: frozen post-inventory LTO metadata tail",
        "violations": violations,
        "negative_matrix": PRODUCT._lto_partition_metadata_model_selftest(),
    }


def preflight_value() -> dict[str, Any]:
    final_red(); attribution(); frozen = frozen_artifacts()
    return {
        "format": "lisp65-c2.3-v2.1-relocation-artifact-replay-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: frozen linked artifacts armed for one replay",
        "authority": {"owner": authorization(), "Final_Red": bind(FINAL_RED),
            "attribution": bind(ATTRIBUTION), "driver": bind(DRIVER),
            "VMA_review_rebind": bind(VMA_REBIND.RECEIPT)},
        "frozen_artifacts": frozen,
        "inventory_source_gate": source_gate(),
        "execution_lock": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 0, "WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "claim_limit": (
            "Qualification tail over frozen linked artifacts only; no WPLTO, "
            "relink, card, Completion, media or device."),
    }


def preflight() -> None:
    require(not REPLAY.exists() and not RECEIPT.exists(),
            "relocation artifact replay is one-shot")
    REPLAY.mkdir(parents=True)
    value = preflight_value()
    PREFLIGHT.write_bytes(canonical(value))
    print("relocation inventory replay: PREFLIGHT PASS replay=0/1 link=0")


def replay() -> None:
    require(load(PREFLIGHT) == preflight_value(),
            "relocation replay preflight drift")
    require(not INVENTORY_REPORT.exists() and not LTO_REPORT.exists()
            and not RECEIPT.exists(), "relocation replay output exists")
    before = frozen_artifacts()
    inventory = inventory_gate()
    observed = {
        str(row["name"]): (int(row["candidate_derived_bytes"]),
                           int(row["candidate_derived_records"]))
        for row in inventory["relocation_sections"]}
    require(observed == {
        ".rela.lisp65_c2_mapped_far_facade": (168, 14),
        ".rela.lisp65_c2_mapped_far_service": (4644, 387)},
        "frozen candidate relocation evidence drift")
    inventory["mutations_rejected"] = inventory_mutations()
    INVENTORY_REPORT.write_bytes(canonical(inventory))
    lto = lto_metadata_gate()
    LTO_REPORT.write_bytes(canonical(lto))
    after = frozen_artifacts()
    require(after == before, "artifact replay changed frozen linked bytes")
    value = {
        "format": load(PREFLIGHT)["format"], "recorded_on": RECORDED_ON,
        "status": "PASS: frozen root-fix link qualification tail green",
        "authority": {"owner": authorization(), "preflight": bind(PREFLIGHT),
            "Final_Red": bind(FINAL_RED), "attribution": bind(ATTRIBUTION),
            "VMA_review_rebind": bind(VMA_REBIND.RECEIPT),
            "driver": bind(DRIVER)},
        "execution_accounting": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 1, "WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "frozen_artifacts_before": before, "frozen_artifacts_after": after,
        "qualification_tail": {"final_section_inventory": inventory,
                               "lto_partition_metadata": lto},
        "next": "linked-image DMA content-reader structural-absence gate",
        "claim_limit": (
            "The frozen link passed its two remaining compile-link "
            "qualification gates. Final product continuation, Completion, "
            "media and device remain not run."),
    }
    RECEIPT.write_bytes(canonical(value))
    print("relocation inventory replay: PASS records=14 replay=1/1 WPLTO=0 link=0")


def check() -> None:
    value = load(RECEIPT)
    require(
        value.get("status") ==
            "PASS: frozen root-fix link qualification tail green"
        and value.get("execution_accounting", {}).get(
            "artifact_replays_run") == 1
        and value["frozen_artifacts_before"] == frozen_artifacts()
        and value["frozen_artifacts_after"] == value[
            "frozen_artifacts_before"]
        and value["qualification_tail"]["final_section_inventory"] ==
            inventory_gate()
            | {"mutations_rejected": inventory_mutations()}
        and value["qualification_tail"]["lto_partition_metadata"] ==
            lto_metadata_gate(),
        "relocation artifact replay receipt drift")
    print("relocation inventory replay: CHECK PASS records=14 WPLTO=0 link=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "replay", "check"))
    action = parser.parse_args().action
    {"preflight": preflight, "replay": replay, "check": check}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.CalledProcessError) as error:
        print(f"relocation inventory replay: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
