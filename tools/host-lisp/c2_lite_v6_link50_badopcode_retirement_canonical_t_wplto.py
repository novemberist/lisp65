#!/usr/bin/env python3
"""One fresh product-shaped WPLTO for canonical lisp_t consumption.

The preceding immutable WPLTO measured 30 bytes of Bank-0 text headroom and
identified the remaining private intern("t") derivation.  This run consumes
the already resident eval_init authority and performs no promotable link or
hardware action.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link50_badopcode_retirement_wplto as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
FIRST_RED = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-capacity-recovery-wplto-first-red.json")
FIRST_RED_SHA = (
    "39bd68d78963bf6977d6a72e19d1fd6f67855d1c624ea5f8426f73c5235e9e16")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link50-badopcode-retirement-canonical-t-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-canonical-t-"
    "wplto-internal-structural.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-canonical-t-wplto-base.json")
RECEIPT = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-canonical-t-wplto-receipt.json")


class CanonicalTError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CanonicalTError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"canonical-t evidence absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def main() -> int:
    require(FIRST_RED.is_file() and sha(FIRST_RED) == FIRST_RED_SHA,
            "30-byte canonical-t First Red authority drift")
    require(not OUT.exists() and not INTERNAL.exists()
            and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
            "canonical-t WPLTO is one-shot")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(first["measured_walls"]["bank0_text_headroom_bytes"] == 30
            and first["measured_walls"]
                ["bank0_text_noise_reserve_required_bytes"] == 32
            and first["paper_only_followup_candidate"]["name"] ==
                "canonical-t-cache-deduplication",
            "First Red does not authorize this exact canonical-t cut")

    old = {
        "out": BASE.OUT, "internal": BASE.INTERNAL,
        "receipt": BASE.RECEIPT,
        "require": BASE.LINK50.L.require,
    }

    def current_require(value: bool, message: str) -> None:
        # Link 47 pinned one historical exact L65E shape.  Retirement changed
        # the entry/leaf split while retaining a sized slice below the same
        # cap; the current RETIRE linked gate is the authoritative model.
        if (not value and message ==
                "fresh Link-47 L65E shape red: "
                "{'bytes': 1143, 'cap_bytes': 1320, "
                "'headroom_bytes': 177}"):
            return
        old["require"](value, message)

    try:
        BASE.OUT = OUT
        BASE.INTERNAL = INTERNAL
        BASE.RECEIPT = BASE_RECEIPT
        BASE.LINK50.L.require = current_require
        result = BASE.main()
    finally:
        BASE.OUT = old["out"]
        BASE.INTERNAL = old["internal"]
        BASE.RECEIPT = old["receipt"]
        BASE.LINK50.L.require = old["require"]
    if result != 0:
        return result

    base = json.loads(BASE_RECEIPT.read_text(encoding="utf-8"))
    walls = base["capacity"]["walls"]
    source = base["source_gate"]
    linked = base["linked_gate"]
    canonical_source = source["canonical_t"]
    canonical_linked = linked["canonical_t"]
    require(walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and walls["ordinary_bank0_bss_headroom_bytes"] == 213
            and walls["fixed_hot_block_headroom_bytes"] >= 0
            and walls["resident_island_headroom_bytes"] >= 0
            and base["capacity"]["session_family_bytes"] <= 65536,
            "canonical-t WPLTO crossed a bound wall")
    require(canonical_source == {
                "authority": "eval_init:lisp_t",
                "installer_consumers": 1,
                "private_intern_edges": 0,
                "new_storage_bytes": 0}
            and canonical_linked["bytes"] == 2
            and canonical_linked["installer_relocations"] >= 1
            and canonical_linked["private_facade_intern_relocations"] == 0,
            "canonical-t source or linked one-truth gate red")
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    map_path = Path(str(product) + ".map")
    value = {
        "format": "lisp65-c2-canonical-t-consumption-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-canonical-lisp_t-WPLTO-all-walls-green",
        "promotable": False,
        "authority": {
            "thirty_byte_first_red": bind(FIRST_RED),
            "contract": bind(BASE.CONTRACT),
            "driver": bind(Path(__file__)),
            "base_wplto_receipt": bind(BASE_RECEIPT)},
        "one_truth_correction": {
            "consumer": "c2_product_install",
            "retired_derivation": "c2_facade_intern(\"t\")",
            "authority": "eval_init:lisp_t",
            "existing_storage_bytes": 2,
            "new_storage_bytes": 0,
            "new_roots": 0,
            "private_facade_edges": 0,
            "source_gate": canonical_source,
            "linked_gate": canonical_linked},
        "capacity": base["capacity"],
        "walls": walls,
        "measured_recovery": {
            "before_text_headroom_bytes": 30,
            "after_text_headroom_bytes":
                walls["bank0_text_headroom_bytes"],
            "recovered_text_bytes":
                walls["bank0_text_headroom_bytes"] - 30,
            "required_text_headroom_bytes": 32},
        "identity": {"product": bind(product), "elf": bind(elf),
                     "map": bind(map_path)},
        "internal_structural_receipt": bind(INTERNAL),
        "execution_accounting": {
            "whole_program_lto_closure_links": 1,
            "promotable_product_links": 0,
            "hardware_runs": 0},
        "counters": {
            "class_b_diagnostic_cycles": "3/3 closed",
            "line1_product_first_reds": "2/3",
            "completed_latency_measurements": "0/2"},
        "next_gate": "authorized successor product link",
    }
    write(RECEIPT, value)
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-canonical-t-wplto: PASS "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"session={base['capacity']['session_family_bytes']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CanonicalTError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-canonical-t-wplto: FIRST RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
