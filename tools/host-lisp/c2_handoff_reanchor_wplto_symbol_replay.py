#!/usr/bin/env python3
"""One pure replay using the shared structured ELF truth first client."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_handoff_reanchor_wplto_probe as W  # noqa: E402
import c2_handoff_reanchor_wplto_replay as ORIGINAL  # noqa: E402
import c2_handoff_reanchor_wplto_lifetime_replay as PREVIOUS  # noqa: E402
import c2_l65r_v2_boot_family_probe as BOOT  # noqa: E402
import c2_preinstall_island_guard as ISLAND  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402
import elf_truth as ELF  # noqa: E402


SOURCE = ORIGINAL.SOURCE
TARGET = ORIGINAL.TARGET
ELF_PATH = ORIGINAL.ELF
MAP = ORIGINAL.MAP
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link33-handoff-reanchor-wplto-symbol-replay")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-handoff-reanchor-wplto-symbol-pure-replay-receipt.json")
PREVIOUS_RECEIPT = PREVIOUS.RECEIPT
PREVIOUS_RECEIPT_SHA256 = (
    "c56302e76297f8a12481c013684139c34f135c2dfc004789fda80c19ebe65e08")
DIAGNOSIS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-handoff-reanchor-wplto-lifetime-symbol-parser-diagnosis.json")
DIAGNOSIS_SHA256 = (
    "217a833186dc8583008e28afa47875a37c66b332026ab494013dffa8b28050b4")
TRUTH_CONTRACT = ROOT / "config/c2-elf-truth-contract.json"
FIXED_HOT_BLOCK_HEADROOM_PIN_BYTES = 273
REPLAY_FORMAT = "lisp65-c2-handoff-reanchor-wplto-symbol-pure-replay-v1"
REPLAY_STATUS = "passed-symbol-pure-replay-no-link33"
FIRST_RED_FORMAT = (
    "lisp65-c2-handoff-reanchor-wplto-symbol-pure-replay-first-red-v1")
FIRST_RED_STATUS = "FIRST RED: symbol pure replay stopped"


class ReplayError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"replay input absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
        "mode": oct(path.stat().st_mode & 0o777),
    }


def write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def authorization_gate() -> dict[str, Any]:
    require(sha(PREVIOUS_RECEIPT) == PREVIOUS_RECEIPT_SHA256,
            "symbol-parser predecessor First Red drift")
    require(sha(DIAGNOSIS) == DIAGNOSIS_SHA256,
            "symbol-parser diagnosis drift")
    previous = json.loads(PREVIOUS_RECEIPT.read_text(encoding="utf-8"))
    require(previous.get("status") ==
            "FIRST RED: lifetime pure replay stopped",
            "symbol-parser successor does not bind the reviewed First Red")
    contract = json.loads(TRUTH_CONTRACT.read_text(encoding="utf-8"))
    authorization = contract.get(
        "immediate_parser_replay_authorization_2026_07_21", {})
    require(contract.get("status") ==
            "owner-commissioned-before-c2.2-acceptance-chain"
            and authorization.get("status") ==
            "owner-authorized-one-pure-replay"
            and authorization.get("bound_elf_sha256") ==
            ORIGINAL.ELF_SHA256,
            "shared ELF-truth parser replay authorization drift")
    return {
        "status": "passed-bound-structured-symbol-replay-authorization",
        "previous_first_red": bind(PREVIOUS_RECEIPT),
        "diagnosis": bind(DIAGNOSIS),
        "elf_truth_contract": bind(TRUTH_CONTRACT),
        "elf_truth_source": bind(Path(ELF.__file__).resolve()),
        "boot_contract": bind(BOOT.CONTRACT),
        "boot_gate_source": bind(Path(BOOT.__file__).resolve()),
    }


def replay_once() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "structured-symbol pure replay is one-shot and already has output")
    OUT.mkdir(parents=True)
    try:
        immutable = ORIGINAL.immutable_tree_gate()
        authorization = authorization_gate()
        BOOT.BASE.configure()
        source_pins = W.pin_source_gate()
        source_guard = ISLAND.source_gate()
        preinstall = ISLAND.static_elf_gate(ELF_PATH)
        boot_manifest_path = SOURCE / "runtime-overlays-boot-final.json"
        session_manifest_path = SOURCE / "runtime-overlays-session-final.json"
        boot_manifest = json.loads(
            boot_manifest_path.read_text(encoding="utf-8"))
        session_manifest = json.loads(
            session_manifest_path.read_text(encoding="utf-8"))
        lifetime = BOOT.boot_lifetime_gate(
            ELF_PATH, boot_manifest, session_manifest)
        geometry = W.geometry_gate(TARGET)
        sections = P.section_table(ELF_PATH)
        kernal = json.loads(
            (SOURCE / "kernal-freedom-link.json").read_text(encoding="utf-8"))
        walls = {
            "bank0_text_headroom_bytes": (
                P.HANDOFF_BASE - sections[".text"]["address"]
                - sections[".text"]["bytes"]),
            "ordinary_bank0_bss_headroom_bytes": (
                P.FIXED_BANK0_BASE - sections[".bss"]["address"]
                - sections[".bss"]["bytes"]),
            "fixed_hot_block_headroom_bytes": P.fixed_bank0_headroom_bytes(),
            "resident_island_headroom_bytes": (
                2048 - sections[".lisp65_resident_island"]["bytes"]
                - sections[".lisp65_resident_island_annex"]["bytes"]),
            "e000_headroom_bytes": kernal["capacity"][
                "actual_future_margin_bytes"],
        }
        require(walls == {
            "bank0_text_headroom_bytes": 42,
            "ordinary_bank0_bss_headroom_bytes": 195,
            "fixed_hot_block_headroom_bytes":
                FIXED_HOT_BLOCK_HEADROOM_PIN_BYTES,
            "resident_island_headroom_bytes": 7,
            "e000_headroom_bytes": 115,
        }, f"replayed resident wall set drift: {walls}")

        prior_reports = {
            name: ORIGINAL.existing_report(name) for name in (
                "handoff-z-abi-l65r-v2-boot-family.json",
                "pre-ownership-closure-l65r-v2-boot-family.json",
                "profile-data-reference-l65r-v2-boot-family.json",
                "fixed-host-facade-l65r-v2-boot-family.json",
                "runtime-family-total-identity.json",
                "one-truth-closure.json",
                "kernal-freedom-link.json",
                "runtime-verifier-publish-last.json",
                "substitution-balance.json",
                "final-section-inventory-l65r-v2-boot-family-placement.prg.json",
                "lto-partition-metadata-l65r-v2-boot-family-placement.prg.json",
            )
        }
        inventory = json.loads((SOURCE /
            "final-section-inventory-l65r-v2-boot-family-placement.prg.json"
        ).read_text(encoding="utf-8"))
        lto = json.loads((SOURCE /
            "lto-partition-metadata-l65r-v2-boot-family-placement.prg.json"
        ).read_text(encoding="utf-8"))
        packer_mutations = BOOT.BASE.packer_mutations(
            SOURCE / "runtime-overlays-boot-final.bin", boot_manifest_path)
        require(len(packer_mutations) == 10,
                "v2 packer replay mutation matrix incomplete")
        original_out = W.OUT
        W.OUT = OUT
        try:
            pins = W.write_successor_pins(
                TARGET, source_pins, geometry, inventory, lto, {
                    "preinstallation_island": preinstall,
                    "boot_lifetime": lifetime,
                    "product_profile": BOOT.PROFILE.receipt_identity(),
                })
        finally:
            W.OUT = original_out
        value = {
            "format": REPLAY_FORMAT,
            "recorded_on": "2026-07-21",
            "status": REPLAY_STATUS,
            "authorization_scope": {
                "compiler_runs": 0,
                "linker_runs": 0,
                "wplto_retries": 0,
                "product_closure_links": 0,
                "link33_attempts": 0,
                "hardware_runs": 0,
            },
            "immutable_source": immutable,
            "authorization": authorization,
            "elf_truth_selftest": ELF.selftest(),
            "corrected_preinstallation_island_gate": preinstall,
            "corrected_boot_lifetime_gate": lifetime,
            "source_guard": source_guard,
            "handoff_reanchor_source_pins": source_pins,
            "handoff_reanchor_geometry": geometry,
            "resident_walls": walls,
            "e000_equation": (
                "531 - 416 = 115; total formal debit 416 + 6 = 422/450"),
            "existing_pre_first_red_gate_reports": prior_reports,
            "v2_packer_mutations": packer_mutations,
            "successor_pin_package": pins,
            "claim_limit": (
                "Pure analysis replay against one SHA-bound read-only WPLTO "
                "artifact set. No compiler, linker, WPLTO retry, product link, "
                "hardware execution, promotion or acceptance is claimed."),
            "next_gate": "review before any fresh Link 33",
        }
    except (ReplayError, ORIGINAL.ReplayError, PREVIOUS.ReplayError,
            ISLAND.GateError, W.ProbeError, BOOT.GateError, ELF.ElfTruthError,
            RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        value = {
            "format": FIRST_RED_FORMAT,
            "recorded_on": "2026-07-21",
            "status": FIRST_RED_STATUS,
            "diagnostic": {"type": type(error).__name__,
                           "message": str(error)},
            "authorization_scope": {
                "compiler_runs": 0, "linker_runs": 0, "wplto_retries": 0,
                "product_closure_links": 0, "link33_attempts": 0,
                "hardware_runs": 0,
            },
            "next_gate": "review; no Link 33",
        }
    write(RECEIPT, value)
    for path in OUT.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
    OUT.chmod(0o555)
    RECEIPT.chmod(0o444)
    return value


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "structured-symbol replay receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") == REPLAY_STATUS,
            "structured-symbol replay receipt is not green")
    require(value["authorization_scope"] == {
        "compiler_runs": 0, "linker_runs": 0, "wplto_retries": 0,
        "product_closure_links": 0, "link33_attempts": 0,
        "hardware_runs": 0,
    }, "structured-symbol replay execution accounting drift")
    require(sha(ELF_PATH) == ORIGINAL.ELF_SHA256
            and sha(MAP) == ORIGINAL.MAP_SHA256,
            "structured-symbol replay source identity drift")
    require(sha(BOOT.BASE.LINK32) == BOOT.BASE.LINK32_SHA,
            "Link-32 rollback identity drift")
    return value


def selftest() -> dict[str, Any]:
    BOOT.BASE.configure()
    return {
        "status": "passed",
        "elf_truth": ELF.selftest(),
        "wipe_mutations": ISLAND.installer_wipe_model_selftest(),
        "lifetime_mutations": BOOT.lifetime_model_selftest(),
        "relocation_mutations": BOOT.lifetime_relocation_model_selftest(),
        "symbol_mutations": BOOT.lifetime_symbol_provenance_selftest(),
        "pin_mutations": W.pin_source_gate()["negative_mutations"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "run", "check"))
    args = parser.parse_args()
    result = (selftest() if args.action == "selftest" else
              replay_once() if args.action == "run" else check())
    print("c2-handoff-reanchor-wplto-symbol-replay: " + result["status"])
    return 3 if str(result["status"]).startswith("FIRST RED") else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, ORIGINAL.ReplayError, PREVIOUS.ReplayError,
            ISLAND.GateError, W.ProbeError, BOOT.GateError, ELF.ElfTruthError,
            RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-handoff-reanchor-wplto-symbol-replay: FAIL {error}",
              file=sys.stderr)
        raise SystemExit(2)
