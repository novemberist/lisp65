#!/usr/bin/env python3
"""One fresh Link 33 after the green Handoff-reanchor wall-pin replay."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link33_bss_triage_product_link as BASE  # noqa: E402


OUT = ROOT / (
    "build/c2.2/substitution/product-link-33-handoff-reanchor-final")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link33-handoff-reanchor-structural-receipt.json")
REPLAY = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-handoff-reanchor-wplto-wall-pin-pure-replay-receipt.json")
REPLAY_SHA256 = (
    "53371fc692f60dd822b098c5172b80ff8b87f83911380abdc226d80724ee547d")
AUTHORIZATION = ROOT / "config/c2-handoff-reanchor-authorization.json"
ELF_TRUTH_CONTRACT = ROOT / "config/c2-elf-truth-contract.json"
PROFILE_PIN = ROOT / (
    "build/c2.2/substitution/"
    "link33-handoff-reanchor-wplto-wall-pin-replay/"
    "successor-pin-profile-binding.json")
PROFILE_PIN_SHA256 = (
    "377afbeb6288ecf2bcf2db09b4ae3fa1d7ba6df7ad16d5be2e6de27360d6a3be")
INVENTORY_PIN = ROOT / (
    "build/c2.2/substitution/"
    "link33-handoff-reanchor-wplto-wall-pin-replay/"
    "successor-pin-section-inventory.json")
INVENTORY_PIN_SHA256 = (
    "f9ab8bffefaad67f52e73b72579d2a3f1b0e8550ecfa23b78fcbbf0d21496a64")
CURRENT_PROFILE_SHA256 = (
    "6226b60c3b9785bbef2210644c4ab558a2487e6cbfcbde25a1e99fe8cc9de2a6")
PREFLIGHT_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link33-handoff-reanchor-preflight-first-red-receipt.json")
PREFLIGHT_FIRST_RED_SHA256 = (
    "260d317a2af7b235ec170d432724db5d229c9d524afa2932ed7c94809bd18874")
PREFLIGHT_DIAGNOSIS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link33-handoff-reanchor-preflight-diagnosis.json")
PREFLIGHT_DIAGNOSIS_SHA256 = (
    "37788f32b17bd878cf3e9dc66ed88abc8f772f36e5a747dc4c1476724e63eecf")


class LinkError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LinkError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"Link-33 prerequisite absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def prerequisites() -> dict[str, Any]:
    # Historical receipts remain immutable evidence of their own product
    # profiles.  They are deliberately identity-bound here, but are not
    # compared with the successor profile after the Handoff reanchor.
    for path, expected in BASE.PREREQUISITES.items():
        require(path.is_file() and sha(path) == expected,
                f"historical Link-33 prerequisite drift: {path}")
    require(BASE.LINK32_PRG.is_file()
            and sha(BASE.LINK32_PRG) == BASE.LINK32_SHA,
            "Link-32 rollback product identity drift")
    section_replay = json.loads(
        BASE.SECTION_REPLAY_RECEIPT.read_text(encoding="utf-8"))
    require(section_replay.get("status") ==
            "passed-pure-section-index-gate-replay-no-link",
            "historical section-index replay is not green")
    require(BASE.PROFILE_BINDING_RECEIPT.is_file()
            and sha(BASE.PROFILE_BINDING_RECEIPT) ==
            BASE.PROFILE_BINDING_RECEIPT_SHA,
            "historical profile-object binding replay drift")
    historical_profile = json.loads(
        BASE.PROFILE_BINDING_RECEIPT.read_text(encoding="utf-8"))
    require(historical_profile.get("status") ==
            "passed-profile-object-binding-pure-replay-no-link"
            and historical_profile["product_profile_object"]["sha256"] ==
            historical_profile["historical_green_wplto_profile"]
                ["equivalent_to_profile_object_sha256"],
            "historical profile-object receipt is internally inconsistent")
    historical_inventory = json.loads(
        BASE.INVENTORY_REPLAY_RECEIPT.read_text(encoding="utf-8"))
    require(historical_inventory.get("status") ==
            "passed-profile-derived-inventory-pure-replay-no-link"
            and historical_inventory["derivation"]
                ["expected_link33_names"] == 167,
            "historical inventory receipt is internally inconsistent")

    # Current authority is the pair of successor pins emitted by the green
    # WPLTO replay.  Both must consume the current canonical profile object.
    require(PROFILE_PIN.is_file() and sha(PROFILE_PIN) == PROFILE_PIN_SHA256,
            "current successor profile pin drift")
    profile_pin = json.loads(PROFILE_PIN.read_text(encoding="utf-8"))
    require(BASE.PROFILE.sha256() == CURRENT_PROFILE_SHA256
            and profile_pin.get("status") == "passed"
            and profile_pin["canonical_profile"]["sha256"] ==
            CURRENT_PROFILE_SHA256
            and profile_pin["probe_profile"]["sha256"] ==
            CURRENT_PROFILE_SHA256,
            "current probe/link profile authority is not green")
    require(INVENTORY_PIN.is_file()
            and sha(INVENTORY_PIN) == INVENTORY_PIN_SHA256,
            "current successor inventory pin drift")
    inventory_pin = json.loads(INVENTORY_PIN.read_text(encoding="utf-8"))
    inventory = inventory_pin["inventory"]
    require(inventory_pin.get("status") == "passed"
            and inventory.get("status") == "passed"
            and inventory["pin"]["expected_sections"] == 167
            and len(inventory["actual_sections"]) == 167
            and not inventory["missing_sections"]
            and not inventory["unknown_sections"]
            and inventory_pin["lto_partition"]["status"] == "passed",
            "current successor section-inventory authority is not green")

    contract = json.loads(BASE.CONTRACT.read_text(encoding="utf-8"))
    floor = contract["formal_reopening_2026_07_21"]["final_floor_rule"]
    require(floor.get("status") ==
            "bound-after-green-st_shndx-provenance-replay"
            and floor.get("bytes") == BASE.P.E000_FINAL_FLOOR_BYTES == 115,
            "final E000 floor contract is not bound at 115 bytes")
    require(sha(REPLAY) == REPLAY_SHA256,
            "green wall-pin replay identity drift")
    replay = json.loads(REPLAY.read_text(encoding="utf-8"))
    require(replay.get("status") ==
            "passed-wall-pin-pure-replay-no-link33"
            and replay.get("resident_walls") == {
                "bank0_text_headroom_bytes": 42,
                "ordinary_bank0_bss_headroom_bytes": 195,
                "fixed_hot_block_headroom_bytes": 33,
                "resident_island_headroom_bytes": 7,
                "e000_headroom_bytes": 115,
            }
            and replay["corrected_boot_lifetime_gate"]
                ["external_installer_target_relocations"] == 0,
            "wall-pin replay is not a complete green Link-33 prerequisite")
    authorization = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    amendment = authorization.get(
        "post_preflight_authority_correction_2026_07_21", {})
    require(amendment.get("status") ==
            "owner-authorized-one-fresh-link33-on-current-successor-pins"
            and amendment.get("current_profile_pin", {}).get("sha256") ==
            PROFILE_PIN_SHA256
            and amendment.get("current_inventory_pin", {}).get("sha256") ==
            INVENTORY_PIN_SHA256
            and amendment.get("preflight_first_red", {}).get("sha256") ==
            PREFLIGHT_FIRST_RED_SHA256
            and amendment.get("execution_limits", {}).get(
                "product_closure_links") == 1,
            "post-preflight Link-33 owner authorization drift")
    require(sha(PREFLIGHT_FIRST_RED) == PREFLIGHT_FIRST_RED_SHA256
            and sha(PREFLIGHT_DIAGNOSIS) == PREFLIGHT_DIAGNOSIS_SHA256,
            "bound preflight First Red evidence drift")
    return {
        "historical_receipts": {
            path.name: bind(path) for path in BASE.PREREQUISITES},
        "historical_profile_binding": bind(BASE.PROFILE_BINDING_RECEIPT),
        "historical_inventory_binding": bind(BASE.INVENTORY_REPLAY_RECEIPT),
        "contract": bind(BASE.CONTRACT),
        "contract_document": bind(BASE.CONTRACT_DOC),
        "plan": bind(BASE.PLAN),
        "current_product_profile_object": BASE.PROFILE.receipt_identity(),
        "current_successor_profile_pin": bind(PROFILE_PIN),
        "current_successor_inventory_pin": bind(INVENTORY_PIN),
        "handoff_reanchor_wall_pin_replay": bind(REPLAY),
        "handoff_reanchor_authorization": bind(AUTHORIZATION),
        "shared_elf_truth_contract": bind(ELF_TRUTH_CONTRACT),
        "preflight_first_red": bind(PREFLIGHT_FIRST_RED),
        "preflight_diagnosis": bind(PREFLIGHT_DIAGNOSIS),
        "link32_rollback": {
            "product": bind(BASE.LINK32_PRG), "status": "untouched"},
        "wall_pin_replay_status": replay["status"],
    }


def configure_base() -> None:
    BASE.OUT = OUT
    BASE.RECEIPT = RECEIPT
    BASE.prerequisites = prerequisites
    BASE.ADDITIONAL_CONTRACT_LINES = (
        "handoff_reanchor_wall_pin_replay_sha256=" + REPLAY_SHA256,
        "shared_elf_truth_contract_sha256=" + sha(ELF_TRUTH_CONTRACT),
        "fixed_hot_block_headroom_pin_bytes=33",
    )


def build() -> dict[str, Any]:
    configure_base()
    return BASE.build()


def check() -> dict[str, Any]:
    configure_base()
    value = BASE.check()
    require(value.get("status") in {
        "passed-new-product-identity-hardware-not-run",
        "FIRST RED: fresh Link 33 failed",
    }, "fresh Handoff-reanchor Link-33 receipt status unknown")
    return value


def selftest() -> dict[str, Any]:
    configure_base()
    BASE.configure()
    require(BASE.P.HANDOFF_BASE == 0xB4A3
            and BASE.P.fixed_bank0_headroom_bytes() == 33,
            "Handoff-reanchor/fixed-wall Link-33 selftest drift")
    require(REPLAY.is_file() and sha(REPLAY) == REPLAY_SHA256,
            "green wall-pin replay absent")
    bound = prerequisites()
    return {"status": "passed", "handoff": "0xb4a3",
            "fixed_hot_block_headroom_bytes": 33,
            "current_profile_sha256": CURRENT_PROFILE_SHA256,
            "current_profile_pin_sha256":
                bound["current_successor_profile_pin"]["sha256"],
            "current_inventory_pin_sha256":
                bound["current_successor_inventory_pin"]["sha256"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "run", "check"))
    args = parser.parse_args()
    result = (selftest() if args.action == "selftest" else
              build() if args.action == "run" else check())
    print("c2-link33-handoff-reanchor: " + result["status"])
    return 3 if str(result["status"]).startswith("FIRST RED") else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (LinkError, BASE.LinkError, BASE.PRE.GateError,
            BASE.ISLAND.GateError, RuntimeError, OSError, ValueError,
            KeyError, json.JSONDecodeError) as error:
        print(f"c2-link33-handoff-reanchor: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
