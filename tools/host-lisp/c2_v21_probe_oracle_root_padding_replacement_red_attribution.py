#!/usr/bin/env python3
"""Attribute the root-padding replacement Red from frozen linked outputs."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v2.1-probe-oracle-root-padding-replacement-card/wplto"
OLD_BUILD = ROOT / "build/c2.3/v2.1-full-span-convergence-card/wplto"
PREFLIGHT = ROOT / (
    "build/c2.3/v2.1-probe-oracle-root-padding-replacement-preflight")
ELF = BUILD / "resident-island-seed.prg.elf"
PRG = BUILD / "resident-island-seed.prg"
MAP = BUILD / "resident-island-seed.prg.map"
LTO = BUILD / "resident-island-seed.prg.lto.o"
OLD_ELF = OLD_BUILD / "resident-island-seed.prg.elf"
PROJECTED = PREFLIGHT / "projected-full-map-authority.json"
FINAL_RED = ARCH / (
    "c2.3-v2.1-probe-oracle-root-padding-replacement-card-final-red.json")
RECEIPT = ARCH / (
    "c2.3-v2.1-probe-oracle-root-padding-replacement-red-attribution-receipt.json")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()
FORMAT = (
    "lisp65-c2.3-v2.1-probe-oracle-root-padding-replacement-red-"
    "attribution-v1")
STATUS = "FINAL-RED-ATTRIBUTED: FACADE-RELOCATION-SNAPSHOT-PIN"


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


def relocation_rows(truth: ElfTruth, section: str) -> list[dict[str, Any]]:
    return [{"offset": f"0x{row.offset:04x}", "type": row.relocation_type,
             "target": row.target, "addend": row.addend}
            for row in truth.relocations if row.source_section == section]


def derive() -> dict[str, Any]:
    red = load(FINAL_RED)
    require(
        red.get("status") ==
            "FINAL RED: root-padding replacement returns to owner"
        and red.get("retry_authorized") is False
        and red.get("owner_disposition_required") is True
        and red["attempt_accounting"] == {
            "replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "root-padding replacement Final Red boundary drift")
    current = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                            include_section_data=True)
    old = ElfTruth.read(OLD_ELF, llvm_readobj=READOBJ,
                        include_section_data=True)
    facade = current.section(".lisp65_c2_mapped_far_facade")
    old_facade = old.section(".lisp65_c2_mapped_far_facade")
    reloc = current.section(".rela.lisp65_c2_mapped_far_facade")
    old_reloc = old.section(".rela.lisp65_c2_mapped_far_facade")
    service_reloc = current.section(".rela.lisp65_c2_mapped_far_service")
    padding = current.symbol("__lisp65_c2_mapped_far_facade_padding")
    c2 = current.symbol("c2_dma_read_or_abort")
    old_c2 = old.symbol("c2_dma_read_or_abort")
    ext = current.symbol("ext_dma_read_or_abort")
    old_ext = old.symbol("ext_dma_read_or_abort")
    current_rows = relocation_rows(
        current, ".lisp65_c2_mapped_far_facade")
    old_rows = relocation_rows(old, ".lisp65_c2_mapped_far_facade")
    projected = load(PROJECTED)
    owners = projected["generated_linker_requirements"][
        "final_section_inventory_additions"]
    facade_owner = next(row for row in owners
                        if row["name"] == ".lisp65_c2_mapped_far_facade")
    relocation_owner = next(
        row for row in owners
        if row["name"] == ".rela.lisp65_c2_mapped_far_facade")
    service_relocation_owner = next(
        row for row in owners
        if row["name"] == ".rela.lisp65_c2_mapped_far_service")
    require(
        (facade.address, facade.bytes) ==
            (old_facade.address, old_facade.bytes) == (0xB3B0, 98)
        and (padding.value, padding.bytes) == (0xB3FF, 19)
        and (ext.bytes, c2.bytes) == (35, 27)
        and (old_ext.bytes, old_c2.bytes) == (38, 46)
        and (reloc.bytes, len(current_rows)) == (168, 14)
        and (old_reloc.bytes, len(old_rows)) == (252, 21)
        and relocation_owner["bytes"] == 252
        and facade_owner["bytes"] == 98
        and service_relocation_owner["bytes"] == service_reloc.bytes == 4644,
        "replacement relocation-pin mechanism drift")
    current_wrapper_rows = [row for row in current_rows
                            if int(row["offset"], 16) >= c2.value]
    old_wrapper_rows = [row for row in old_rows
                        if int(row["offset"], 16) >= old_c2.value]
    require(len(current_wrapper_rows) == 8 and len(old_wrapper_rows) == 15
            and not any(int(row["offset"], 16) >= padding.value
                        for row in current_rows),
            "relocation delta is not exactly the emitted wrapper shrink")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-16", "status": STATUS,
        "first_stopper": {
            "gate": "final_section_inventory_check",
            "diagnostic":
                "full-map-owner-size:.rela.lisp65_c2_mapped_far_facade",
            "stage": "post-link producer qualification",
            "link_succeeded": True, "qualification_succeeded": False},
        "mechanism": {
            "class": "FREIGHT-DERIVED-RELOCATION-COUNT-PINNED-AS-INVARIANT",
            "allocated_facade": {"address": "0xb3b0", "Link112_bytes": 98,
                                 "replacement_bytes": 98,
                                 "contract_bytes": facade_owner["bytes"]},
            "explicit_padding": {"address": "0xb3ff", "bytes": 19,
                                 "relocation_records": 0},
            "wrappers": {"ordinary": {"Link112_bytes": old_ext.bytes,
                                        "replacement_bytes": ext.bytes},
                         "mapped_facade": {"Link112_bytes": old_c2.bytes,
                                           "replacement_bytes": c2.bytes},
                         "execution_delta_bytes": -22},
            "facade_relocations": {"projected_contract_bytes":
                                        relocation_owner["bytes"],
                                    "Link112_bytes": old_reloc.bytes,
                                    "Link112_records": len(old_rows),
                                    "replacement_bytes": reloc.bytes,
                                    "replacement_records": len(current_rows),
                                    "record_delta": -7, "byte_delta": -84,
                                    "removed_records_belong_to_shrunk_wrapper":
                                        True},
            "control": {"service_relocation_contract_bytes":
                            service_relocation_owner["bytes"],
                        "service_relocation_candidate_bytes":
                            service_reloc.bytes,
                        "candidate_derived_control_passed": True}},
        "classification": {
            "product_semantics_red": False,
            "capacity_red": False, "geometry_red": False,
            "padding_contract_red": False,
            "acceptance_snapshot_pin_red": True,
            "narrow_candidate": (
                "derive facade-relocation size/count from emitted candidate "
                "while retaining name/address/flags ownership"),
            "narrow_candidate_authorized": False,
            "another_card_authorized": False},
        "execution_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_links_succeeded": 1, "qualified_product_artifacts": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "authority": {"Final_Red": bind(FINAL_RED), "candidate_ELF": bind(ELF),
            "candidate_PRG": bind(PRG), "candidate_map": bind(MAP),
            "candidate_LTO": bind(LTO), "Link112_ELF": bind(OLD_ELF),
            "projected_full_map": bind(PROJECTED), "driver": bind(DRIVER)},
        "next": "owner disposition; no replay, repair or card is implied",
        "claim_limit": (
            "Desk attribution over unqualified linked outputs only; the "
            "replacement remains consumed and downstream stages remain closed."),
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    mechanism = value["mechanism"]
    classification = value["classification"]
    require(value.get("format") == FORMAT and value.get("status") == STATUS
            and value["first_stopper"]["link_succeeded"] is True
            and value["first_stopper"]["qualification_succeeded"] is False
            and mechanism["allocated_facade"] == {
                "address": "0xb3b0", "Link112_bytes": 98,
                "replacement_bytes": 98, "contract_bytes": 98}
            and mechanism["explicit_padding"] == {
                "address": "0xb3ff", "bytes": 19, "relocation_records": 0}
            and mechanism["wrappers"]["execution_delta_bytes"] == -22
            and mechanism["facade_relocations"]["Link112_records"] == 21
            and mechanism["facade_relocations"]["replacement_records"] == 14
            and mechanism["facade_relocations"]["record_delta"] == -7
            and mechanism["facade_relocations"]["byte_delta"] == -84
            and mechanism["facade_relocations"]
                ["removed_records_belong_to_shrunk_wrapper"] is True
            and mechanism["control"]["candidate_derived_control_passed"] is True
            and classification["acceptance_snapshot_pin_red"] is True
            and classification["narrow_candidate_authorized"] is False
            and classification["another_card_authorized"] is False
            and value["execution_accounting"]["product_links_succeeded"] == 1
            and value["execution_accounting"]["qualified_product_artifacts"] == 0
            and value["execution_accounting"]["device_contacts"] == 0,
            "root-padding replacement attribution drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "deny-link": lambda x: x["first_stopper"].update(link_succeeded=False),
        "accept-qualification": lambda x: x["first_stopper"].update(
            qualification_succeeded=True),
        "resize-facade": lambda x: x["mechanism"]["allocated_facade"].update(
            replacement_bytes=79),
        "lose-padding": lambda x: x["mechanism"]["explicit_padding"].update(
            bytes=0),
        "inherit-relocations": lambda x: x["mechanism"][
            "facade_relocations"].update(replacement_records=21),
        "hide-delta": lambda x: x["mechanism"]["facade_relocations"].update(
            byte_delta=0),
        "blame-padding": lambda x: x["mechanism"]["explicit_padding"].update(
            relocation_records=1),
        "lose-control": lambda x: x["mechanism"]["control"].update(
            candidate_derived_control_passed=False),
        "authorize-fix": lambda x: x["classification"].update(
            narrow_candidate_authorized=True),
        "authorize-card": lambda x: x["classification"].update(
            another_card_authorized=True),
        "promote-artifact": lambda x: x["execution_accounting"].update(
            qualified_product_artifacts=1),
        "touch-device": lambda x: x["execution_accounting"].update(
            device_contacts=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "replacement attribution mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    value = derive(); value["mutations_rejected"] = mutations(value)
    if action == "record":
        require(not RECEIPT.exists(), "replacement attribution receipt exists")
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        require(load(RECEIPT) == value, "replacement attribution receipt stale")
    else:
        require(len(value["mutations_rejected"]) == 12,
                "replacement attribution mutation count drift")
    print(f"probe-oracle root padding replacement attribution: PASS "
          f"action={action} relocations=21->14 mutations=12")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("probe-oracle root padding replacement attribution: FAIL: "
              f"{error}", file=sys.stderr)
        raise SystemExit(2)
