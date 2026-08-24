#!/usr/bin/env python3
"""Attribute the consumed replacement card's final adapter Red."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402

ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RED = ARCH / "c2.3-v1.6-recovery-sanitization-library-replacement-card-final-red.json"
RECEIPT = ARCH / "c2.3-v1.6-recovery-sanitization-library-replacement-card-receipt.json"
ELF = ROOT / ("build/c2.3/v1.6-recovery-sanitization-library-replacement-"
              "card/wplto/lisp65-c2-substitution-linked.prg.elf")
ACTIVE_GATE = ROOT / "tools/host-lisp/c2_v160_active_frame_liveness_card.py"
BOUNDARY_GATE = ROOT / "tools/host-lisp/c2_v160_execution_boundary_backstop.py"
ALIAS_ATTRIBUTION = ARCH / "c2.3-v1.6-execution-boundary-alias-lto-attribution.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OUT = ARCH / "c2.3-v1.6-recovery-sanitization-final-adapter-attribution.json"
ALIASES = {
    "c2_backstop_pending_code": "pending_code",
    "c2_backstop_pending_symbol": "pending_symbol",
    "c2_backstop_rtov_loaded_len": "rtov_loaded_len",
    "c2_backstop_rtov_busy": "rtov_busy",
}


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def derive() -> dict[str, Any]:
    red = load(RED); receipt = load(RECEIPT); alias_evidence = load(ALIAS_ATTRIBUTION)
    active = receipt["active_frame_final_gate"]
    require(red["error"]["message"] == "active-frame final receipt drift"
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and active["input_counters"]["ring_usable_events"] == 107
            and active["input_counters"]["reserve_events"] == 13
            and len(active["input_counters"]["counter_addresses"]) == 4
            and receipt["candidate_v16core"]["empty_phase_semantic_claim"]
                ["fixed_status"] == "PASS: EMPTY PHASE WAITS AND CONTINUES",
            "final-adapter Red identity drift")
    active_source = ACTIVE_GATE.read_text()
    require('gate["input_counters"]["ring_usable_events"] == 108' in active_source
            and 'gate["input_counters"]["reserve_events"] == 14' in active_source,
            "stored pre-RAW adapter pins absent")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    alias_rows: dict[str, Any] = {}
    for alias_name, owner_name in ALIASES.items():
        alias = truth.symbol(alias_name); owner = truth.symbol(owner_name)
        require(alias.value == owner.value and alias.bytes == owner.bytes,
                f"alias/owner final identity drift: {alias_name}")
        alias_rows[alias_name] = {"owner": owner_name,
            "address": f"0x{alias.value:04x}", "same_address": True,
            "ELF_symbol_bytes": alias.bytes, "owner_symbol_bytes": owner.bytes,
            "additional_allocated_bytes": alias_evidence["alias_result"]
                ["identities"][alias_name]["additional_allocated_bytes"]}
    require(all(row["additional_allocated_bytes"] == 0
                for row in alias_rows.values()),
            "existing alias-allocation proof drift")
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    service = truth.section(".lisp65_c2_mapped_far_service")
    bss = truth.section(".bss")
    product = {"ordinary_text_free_bytes": facade.address - (text.address + text.bytes),
        "mapped_far_service_bytes": service.bytes,
        "mapped_far_service_free_bytes": 1499 - service.bytes,
        "BSS_bytes": bss.bytes,
        "BSS_validation_margin_bytes": 0xC000 - (bss.address + bss.bytes),
        "landing_bytes": truth.symbol("retired_window_resume").bytes,
        "recovery_entry_bytes": truth.symbol("c2_rtov_sanitize_recovery").bytes,
        "active_frame_walker_bytes": truth.symbol(
            "c2_rtov_retire_continuations").bytes,
        "saved_CSR_walker_bytes": truth.symbol(
            "c2_rtov_sanitize_saved_csrs").bytes}
    require(product == {"ordinary_text_free_bytes": 18,
        "mapped_far_service_bytes": 1488, "mapped_far_service_free_bytes": 11,
        "BSS_bytes": 1585, "BSS_validation_margin_bytes": 5,
        "landing_bytes": 32, "recovery_entry_bytes": 9,
        "active_frame_walker_bytes": 41, "saved_CSR_walker_bytes": 43},
        "sanitized final product geometry drift")
    return {"format": "lisp65-c2.3-v1.6-recovery-sanitization-final-adapter-attribution-v1",
        "recorded_on": "2026-08-24",
        "status": "ATTRIBUTED: TWO STORED-WORLD ADAPTERS AFTER SANITIZED LINK",
        "inputs": {"Final_Red": bind(RED), "partial_final_receipt": bind(RECEIPT),
            "candidate_ELF": bind(ELF), "active_frame_adapter": bind(ACTIVE_GATE),
            "execution_boundary_gate": bind(BOUNDARY_GATE),
            "sealed_alias_attribution": bind(ALIAS_ATTRIBUTION)},
        "stopper": {"class": "stored pre-RAW counter geometry",
            "expected_by_adapter": {"ring_usable_events": 108,
                "reserve_events_over_94_wall": 14, "counter_count": 3},
            "observed_from_final_ELF_gate": {"ring_usable_events": 107,
                "reserve_events_over_94_wall": 13, "counter_count": 4,
                "fourth_counter": "C2K_INPUT_EVENTS_RAW"},
            "product_defect": False,
            "required_conversion": ("derive usable events and reserve from the "
                "candidate counter population; retain the 94-event inequality")},
        "next_visible_gate": {"class": "alias allocation projection mismatch",
            "observed_aliases": alias_rows,
            "incorrect_live_predicate": "ElfTruth alias symbol bytes == 0",
            "correct_existing_proof": ("alias and owner share one address; map/section "
                "geometry reports zero additional allocated bytes"),
            "product_defect": False},
        "candidate_substance": product,
        "already_green": {"scope": "PASS", "acceptance": "PASS",
            "component_membership": "41+43=84; three mutations rejected",
            "v16core_empty_phase": "semantic PASS; unfixed TypeError; emitted==compiled"},
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "claim_limit": ("The one self-dispositional replacement is consumed. This "
            "attribution authorizes no adapter conversion, resume, card, medium or "
            "device contact; the partial green receipt is evidence, not acceptance.")}


def main() -> int:
    value = derive()
    OUT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print(f"recovery sanitization final adapter: {value['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
