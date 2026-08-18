#!/usr/bin/env python3
"""Attribute the Final Red of the Workbench capacity-domain card."""

from __future__ import annotations

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

import c2_lite_canonical_product as CAN  # noqa: E402
import c2_v21_workbench_capacity_card as CARD  # noqa: E402
import c2_v21_workbench_capacity_domain as DOMAIN  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = ARCH / (
    "c2.3-v2.1-workbench-capacity-card-red-attribution-receipt.json")
ABI_REPORT = CARD.BUILD / "wplto/c2-asm-leaf-real-abi-callers.json"
DRIVER = Path(__file__).resolve()
RECORDED_ON = "2026-08-14"
HISTORICAL_SOURCE_COMMIT = "4db8b6dc7d08c233c330a34c46a184eb05588504"


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


def historical_file(path: Path) -> tuple[bytes, dict[str, Any]]:
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{HISTORICAL_SOURCE_COMMIT}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    return raw, {"path": name, "bytes": len(raw),
                 "sha256": hashlib.sha256(raw).hexdigest()}


def expected_inventory() -> dict[str, int]:
    return {
        "vm_runtime_overlay_exec_family": 2,
        "vm_runtime_overlay_catalog_verifier": 1,
        "vm_runtime_overlay_record_verifier": 1,
        "c2_append_journal_write_phase": 1,
        "c2_append_journal_validate_phase": 1,
        "c2_completion_poll": 1,
        "vm_resident_island_install": 2,
    }


def derive() -> dict[str, Any]:
    red = load(CARD.FINAL_RED)
    report = load(ABI_REPORT)
    require(
        red.get("status") ==
            "FINAL RED: sole Workbench capacity card returns to owner"
        and red.get("retry_authorized") is False
        and red.get("owner_disposition_required") is True
        and red["attempt_accounting"]["replacement_cards_consumed"] == 1
        and report["status"] == "passed-all-assembler-leaf-abi-contracts"
        and report["ELF_derived_C_called_inventory"]["status"] ==
            "passed-ELF-derived-C-called-assembler-universe"
        and report["ELF_derived_C_called_inventory"]
            ["unclassified_C_called_functions"] == [],
        "Workbench card/ABI report authority drift",
    )
    callers = report["rtov_crc_mem_callers"]
    owners: dict[str, int] = {}
    for row in callers["callers"]:
        owners[row["owner"]] = owners.get(row["owner"], 0) + 1
    expected = expected_inventory()
    added = {name: count for name, count in owners.items()
             if expected.get(name) != count}
    missing = {name: count for name, count in expected.items()
               if owners.get(name) != count}
    new_rows = [row for row in callers["callers"]
                if row["owner"] == "c2_phase02a_record_read"]
    source_raw, source_binding = historical_file(Path(CAN.__file__).resolve())
    source = source_raw.decode()
    _driver_raw, driver_binding = historical_file(DRIVER)
    require(
        callers["status"] == "passed-complete-final-elf-caller-inventory"
        and callers["callsite_count"] == 10
        and owners == {**expected, "c2_phase02a_record_read": 1}
        and added == {"c2_phase02a_record_read": 1}
        and missing == {}
        and len(new_rows) == 1
        and new_rows[0]["owner_section"] == ".lisp65_rt_c2d_02a"
        and 'and callers["callsite_count"] == 9' in source
        and '"c2_phase02a_record_read"' not in source[
            source.index("def fresh_real_abi_gate"):
            source.index("_HISTORICAL_WPLTO_QUALIFICATION_MESSAGES")],
        "real-ABI expected/actual inventory delta drift",
    )
    domain = CARD.domain_authority()
    require(domain["arena"] == "workbench-boot-overlay"
            and domain["headroom_bytes"] == 879,
            "correct-domain F1 predecessor did not remain green")
    return {
        "format": "lisp65-c2.3-v21-workbench-capacity-card-red-attribution-v1",
        "recorded_on": RECORDED_ON,
        "status": "ATTRIBUTED FINAL RED: Real-ABI expected inventory omits current ELF caller",
        "authority": {"final_red": bind(CARD.FINAL_RED),
            "ABI_report": bind(ABI_REPORT),
            "candidate_ELF": red["artifacts"]["elf"],
            "capacity_domain": bind(DOMAIN.RECEIPT),
            "canonical_consumer": source_binding,
            "driver": driver_binding},
        "authorized_work_result": {
            "F1_correct_domain_reached_and_returned": True,
            "workbench_capacity_bytes": domain["capacity_bytes"],
            "workbench_candidate_bytes": domain["candidate_bytes"],
            "workbench_headroom_bytes": domain["headroom_bytes"],
            "product_link_artifacts_exist": True},
        "new_final_red": {
            "class": "CURRENT-ELF-INVENTORY-COMPARED-TO-HISTORICAL-EXPECTED-SET",
            "gate": "fresh_real_abi_gate",
            "actual_inventory_source": "candidate ELF relocations",
            "actual_callsite_count": callers["callsite_count"],
            "expected_callsite_count": 9,
            "actual_owners": owners,
            "expected_owners": expected,
            "added_current_ELF_owners": added,
            "missing_expected_owners": missing,
            "new_callsite": new_rows[0],
            "leaf_ABI_audit_status": report["status"],
            "unclassified_C_called_functions": [],
            "mechanism": (
                "The gate correctly derived ten CRC callsites from the current "
                "ELF, including the phase-02a delivered-content verifier. It "
                "then compared that complete inventory with a nine-callsite "
                "historical expected dictionary that predates this legitimate "
                "candidate owner. The ABI audit itself is green."),
        },
        "card_disposition": {"card_consumed": True,
            "retry_authorized": False, "owner_disposition_required": True,
            "completion_allowed": False, "media_allowed": False,
            "device_allowed": False},
        "claim_limit": (
            "Read-only Final-Red attribution. No expected-set conversion, "
            "replacement card, completion, media or device is authorized."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("status") ==
            "ATTRIBUTED FINAL RED: Real-ABI expected inventory omits current ELF caller"
        and value["authorized_work_result"]["F1_correct_domain_reached_and_returned"]
            is True
        and value["new_final_red"]["actual_callsite_count"] == 10
        and value["new_final_red"]["expected_callsite_count"] == 9
        and value["new_final_red"]["added_current_ELF_owners"] == {
            "c2_phase02a_record_read": 1}
        and value["new_final_red"]["missing_expected_owners"] == {}
        and value["new_final_red"]["leaf_ABI_audit_status"] ==
            "passed-all-assembler-leaf-abi-contracts"
        and value["card_disposition"] == {"card_consumed": True,
            "retry_authorized": False, "owner_disposition_required": True,
            "completion_allowed": False, "media_allowed": False,
            "device_allowed": False},
        "Workbench card red-attribution receipt red",
    )
    if verify:
        require(value == derive(), "Workbench card red-attribution drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "blame-F1-domain": lambda x: x["authorized_work_result"].update(
            F1_correct_domain_reached_and_returned=False),
        "hide-new-owner": lambda x: x["new_final_red"].update(
            added_current_ELF_owners={}),
        "invent-missing-owner": lambda x: x["new_final_red"].update(
            missing_expected_owners={"c2_completion_poll": 1}),
        "call-ABI-red": lambda x: x["new_final_red"].update(
            leaf_ABI_audit_status="red"),
        "erase-callsite-delta": lambda x: x["new_final_red"].update(
            expected_callsite_count=10),
        "authorize-retry": lambda x: x["card_disposition"].update(
            retry_authorized=True),
        "allow-completion": lambda x: x["card_disposition"].update(
            completion_allowed=True),
        "allow-device": lambda x: x["card_disposition"].update(
            device_allowed=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=True)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "Workbench card attribution mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "Workbench card red-attribution receipt exists")
    value = derive(); validate(value, verify=True)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 Workbench card red attribution: PASS F1=green ABI=green "
          "actual=10 expected=9 new=c2_phase02a_record_read retry=none")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value),
            "Workbench card attribution mutation set drift")
    print("2.1 Workbench card red attribution: CHECK PASS actual=10 expected=9")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check"),
            "usage: c2_v21_workbench_capacity_card_red_attribution.py record|check")
    {"record": record, "check": check}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, CARD.CardError, DOMAIN.DomainError,
            OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.SubprocessError) as error:
        print(f"2.1 Workbench card red attribution: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
