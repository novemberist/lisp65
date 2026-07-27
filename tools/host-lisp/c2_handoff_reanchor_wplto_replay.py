#!/usr/bin/env python3
"""Pure gate replay for the stopped Handoff-reanchor WPLTO artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_handoff_reanchor_wplto_probe as W  # noqa: E402
import c2_l65r_v2_boot_family_probe as BOOT  # noqa: E402
import c2_preinstall_island_guard as ISLAND  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402


SOURCE = ROOT / "build/c2.2/substitution/link33-handoff-reanchor-wplto"
TARGET = SOURCE / "l65r-v2-boot-family-placement.prg"
ELF = Path(str(TARGET) + ".elf")
MAP = Path(str(TARGET) + ".map")
OUT = ROOT / "build/c2.2/substitution/link33-handoff-reanchor-wplto-replay"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-handoff-reanchor-wplto-pure-replay-receipt.json")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-handoff-reanchor-wplto-probe-receipt.json")
FIRST_RED_SHA256 = (
    "8332fabca7ee785dffaa9b980cca3bbf1f0d3e1204387845263d4a66411dafec")
DIAGNOSIS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-handoff-reanchor-wplto-preinstall-gate-diagnosis.json")
DIAGNOSIS_SHA256 = (
    "c7560e1f2dd5ad69d5124cf3b8e021ffe3f4149aa3a95d5c028564d1eabbc1a9")
ELF_SHA256 = (
    "c82b9bd0763e1c515e083c615b7f35742b571a262e75b03649a5798382110d2b")
MAP_SHA256 = (
    "3c756c120f3f2d3227e30efacbc91ae148f62d28a29860f8122efd38f334fcf4")


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


def immutable_tree_gate() -> dict[str, Any]:
    require(sha(FIRST_RED) == FIRST_RED_SHA256,
            "Handoff-reanchor WPLTO First Red receipt drift")
    require(sha(DIAGNOSIS) == DIAGNOSIS_SHA256,
            "authorized gate diagnosis drift")
    require(sha(ELF) == ELF_SHA256 and sha(MAP) == MAP_SHA256,
            "immutable WPLTO placement identity drift")
    first_red = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(first_red.get("status") ==
            "FIRST RED: handoff-reanchor WPLTO stopped",
            "replay source is not the reviewed First Red")
    verified = 0
    for item in first_red["evidence"]:
        path = ROOT / item["path"]
        require(path.is_file() and path.stat().st_size == item["bytes"]
                and sha(path) == item["sha256"],
                f"WPLTO evidence drift: {path}")
        require(path.stat().st_mode & 0o222 == 0,
                f"WPLTO evidence is writable: {path}")
        verified += 1
    require(SOURCE.stat().st_mode & 0o222 == 0,
            "WPLTO source tree is writable")
    contract = json.loads(ISLAND.CONTRACT.read_text(encoding="utf-8"))
    amendment = contract.get("manufacturing_write_amendment_2026_07_21", {})
    require(amendment.get("status") ==
            "owner-authorized-narrow-gate-correction-and-pure-replay"
            and amendment.get("replay_scope", {}).get(
                "immutable_elf_sha256") == ELF_SHA256,
            "manufacturing-write replay authorization drift")
    return {
        "status": "passed-entire-first-red-evidence-tree-sha-bound-read-only",
        "files": verified,
        "first_red": bind(FIRST_RED),
        "diagnosis": bind(DIAGNOSIS),
        "elf": bind(ELF),
        "map": bind(MAP),
        "corrected_contract": bind(ISLAND.CONTRACT),
        "corrected_contract_document": bind(ISLAND.DOCUMENT),
        "corrected_gate_source": bind(Path(ISLAND.__file__).resolve()),
    }


def existing_report(name: str) -> dict[str, Any]:
    path = SOURCE / name
    value = json.loads(path.read_text(encoding="utf-8"))
    require(value.get("status") == "passed",
            f"pre-First-Red gate report is not green: {name}")
    return {"identity": bind(path), "status": value["status"]}


def replay_once() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "pure replay is one-shot and already has output")
    OUT.mkdir(parents=True)
    try:
        immutable = immutable_tree_gate()
        BOOT.BASE.configure()
        source_pins = W.pin_source_gate()
        source_guard = ISLAND.source_gate()
        preinstall = ISLAND.static_elf_gate(ELF)
        boot_manifest_path = SOURCE / "runtime-overlays-boot-final.json"
        session_manifest_path = SOURCE / "runtime-overlays-session-final.json"
        boot_manifest = json.loads(boot_manifest_path.read_text(encoding="utf-8"))
        session_manifest = json.loads(
            session_manifest_path.read_text(encoding="utf-8"))
        lifetime = BOOT.boot_lifetime_gate(
            ELF, boot_manifest, session_manifest)
        geometry = W.geometry_gate(TARGET)
        sections = P.section_table(ELF)
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
            "fixed_hot_block_headroom_bytes": 273,
            "resident_island_headroom_bytes": 7,
            "e000_headroom_bytes": 115,
        }, f"replayed resident wall set drift: {walls}")

        prior_reports = {
            name: existing_report(name) for name in (
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
                    "product_profile": BOOT.PROFILE.receipt_identity(),
                })
        finally:
            W.OUT = original_out
        value = {
            "format": "lisp65-c2-handoff-reanchor-wplto-pure-replay-v1",
            "recorded_on": "2026-07-21",
            "status": "passed-pure-gate-replay-no-link33",
            "authorization_scope": {
                "compiler_runs": 0,
                "linker_runs": 0,
                "wplto_retries": 0,
                "product_closure_links": 0,
                "link33_attempts": 0,
                "hardware_runs": 0,
            },
            "immutable_source": immutable,
            "corrected_preinstallation_island_gate": preinstall,
            "source_guard": source_guard,
            "boot_lifetime": lifetime,
            "handoff_reanchor_source_pins": source_pins,
            "handoff_reanchor_geometry": geometry,
            "resident_walls": walls,
            "e000_equation": "531 - 416 = 115; total formal debit 416 + 6 = 422/450",
            "existing_pre_first_red_gate_reports": prior_reports,
            "v2_packer_mutations": packer_mutations,
            "successor_pin_package": pins,
            "claim_limit": (
                "Pure analysis replay against one SHA-bound read-only WPLTO "
                "artifact set. No compiler, linker, WPLTO retry, product link, "
                "hardware execution, promotion or acceptance is claimed."),
            "next_gate": "review before any fresh Link 33",
        }
    except (ReplayError, ISLAND.GateError, W.ProbeError, RuntimeError,
            OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        value = {
            "format": "lisp65-c2-handoff-reanchor-wplto-pure-replay-first-red-v1",
            "recorded_on": "2026-07-21",
            "status": "FIRST RED: pure replay stopped",
            "diagnostic": {"type": type(error).__name__, "message": str(error)},
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
    require(RECEIPT.is_file(), "pure replay receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") == "passed-pure-gate-replay-no-link33",
            "pure replay receipt is not green")
    require(value["authorization_scope"] == {
        "compiler_runs": 0, "linker_runs": 0, "wplto_retries": 0,
        "product_closure_links": 0, "link33_attempts": 0,
        "hardware_runs": 0,
    }, "pure replay execution accounting drift")
    require(sha(ELF) == ELF_SHA256 and sha(MAP) == MAP_SHA256,
            "pure replay source identity drift")
    require(sha(BOOT.BASE.LINK32) == BOOT.BASE.LINK32_SHA,
            "Link-32 rollback identity drift")
    return value


def selftest() -> dict[str, Any]:
    BOOT.BASE.configure()
    return {
        "status": "passed",
        "wipe_mutations": ISLAND.installer_wipe_model_selftest(),
        "lifetime_mutations": BOOT.lifetime_model_selftest(),
        "pin_mutations": W.pin_source_gate()["negative_mutations"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "run", "check"))
    args = parser.parse_args()
    result = (selftest() if args.action == "selftest" else
              replay_once() if args.action == "run" else check())
    print("c2-handoff-reanchor-wplto-replay: " + result["status"])
    return 3 if str(result["status"]).startswith("FIRST RED") else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, ISLAND.GateError, W.ProbeError, RuntimeError,
            OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"c2-handoff-reanchor-wplto-replay: FAIL {error}",
              file=sys.stderr)
        raise SystemExit(2)
