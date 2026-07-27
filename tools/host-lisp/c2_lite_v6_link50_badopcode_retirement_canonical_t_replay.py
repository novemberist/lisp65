#!/usr/bin/env python3
"""Pure qualification replay of the immutable canonical-lisp_t WPLTO ELF."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link50_badopcode_retirement_artifact_replay as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "link50-badopcode-retirement-canonical-t-wplto")
PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
FIRST_RED = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-canonical-t-"
    "wplto-internal-structural.json")
FIRST_RED_SHA = (
    "038f51a37de4a3e97dc2f39cf0b1bf11e61c2a0c467f30db55e2d48a7c41989a")
FIRST_RED_RECEIPT = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-canonical-t-wplto-base.json")
FIRST_RED_RECEIPT_SHA = (
    "9a15eec229fbc688dae49590b9723f1f3795ba68b2afc80d2fe4be6fa6699e44")
AUTHORIZATION = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-capacity-recovery-wplto-first-red.json")
AUTHORIZATION_SHA = (
    "39bd68d78963bf6977d6a72e19d1fd6f67855d1c624ea5f8426f73c5235e9e16")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link50-badopcode-retirement-canonical-t-artifact-replay")
REPLAY_RECEIPT = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-canonical-t-"
    "artifact-replay-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-canonical-t-wplto-receipt.json")


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"canonical-t replay input absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def main() -> int:
    require(sha(FIRST_RED) == FIRST_RED_SHA
            and sha(FIRST_RED_RECEIPT) == FIRST_RED_RECEIPT_SHA
            and sha(AUTHORIZATION) == AUTHORIZATION_SHA,
            "canonical-t WPLTO replay authority drift")
    require(not OUT.exists() and not REPLAY_RECEIPT.exists()
            and not RECEIPT.exists(),
            "canonical-t qualification replay is one-shot")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(first["diagnostic"] == {
                "type": "GateError",
                "message":
                    "linked installer retained private t derivation or "
                    "lost lisp_t"},
            "replay is not bound to the exact section/addend checker Red")

    old = {
        "source": BASE.SOURCE, "product": BASE.PRODUCT,
        "elf": BASE.ELF, "map": BASE.MAP,
        "first": BASE.FIRST_RED,
        "first_receipt": BASE.FIRST_RED_RECEIPT,
        "out": BASE.OUT, "receipt": BASE.RECEIPT,
        "require": BASE.require,
    }

    def current_require(value: bool, message: str) -> None:
        # The imported replay pins its predecessor pair and diagnostic.  This
        # wrapper pins the current pair above and relaxes only those literals.
        if message in {"retirement WPLTO First-Red authority drift",
                       "artifact replay is not bound to the shape-checker Red"}:
            return
        old["require"](value, message)

    try:
        BASE.SOURCE = SOURCE
        BASE.PRODUCT = PRODUCT
        BASE.ELF = ELF
        BASE.MAP = MAP
        BASE.FIRST_RED = FIRST_RED
        BASE.FIRST_RED_RECEIPT = FIRST_RED_RECEIPT
        BASE.OUT = OUT
        BASE.RECEIPT = REPLAY_RECEIPT
        BASE.require = current_require
        value = BASE.build()
    finally:
        BASE.SOURCE = old["source"]
        BASE.PRODUCT = old["product"]
        BASE.ELF = old["elf"]
        BASE.MAP = old["map"]
        BASE.FIRST_RED = old["first"]
        BASE.FIRST_RED_RECEIPT = old["first_receipt"]
        BASE.OUT = old["out"]
        BASE.RECEIPT = old["receipt"]
        BASE.require = old["require"]

    walls = value["fresh_read_only_replay"]["walls"]
    capacity = value["fresh_read_only_replay"]["capacity"]
    canonical = value["badopcode_retirement"]["canonical_t"]
    source_gate = BASE.RETIRE.source_gate(mutations=True)
    require(walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and walls["ordinary_bank0_bss_headroom_bytes"] == 213
            and walls["fixed_hot_block_headroom_bytes"] >= 0
            and walls["resident_island_headroom_bytes"] >= 0
            and capacity["session_family_bytes"] <= 65536,
            "canonical-t WPLTO has a real capacity Red")
    require(canonical["bytes"] == 2
            and canonical["installer_resolved_bytes"] == [0, 1]
            and canonical["private_facade_intern_relocations"] == 0
            and source_gate["canonical_t"]["private_intern_edges"] == 0,
            "canonical-t WPLTO has a real one-truth Red")
    final = {
        "format": "lisp65-c2-canonical-t-consumption-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-WPLTO-and-pure-section-addend-replay",
        "promotable": False,
        "authority": {
            "thirty_byte_first_red": bind(AUTHORIZATION),
            "checker_first_red": bind(FIRST_RED),
            "checker_first_red_receipt": bind(FIRST_RED_RECEIPT),
            "contract": bind(BASE.CONTRACT),
            "wplto_driver": bind(ROOT / "tools/host-lisp/"
                "c2_lite_v6_link50_badopcode_retirement_canonical_t_wplto.py"),
            "replay_driver": bind(Path(__file__))},
        "class_a_checker_correction": {
            "old_model": "relocation target spelling must be lisp_t",
            "current_model":
                "structured section-symbol plus addend resolves uniquely "
                "to both bytes of the sized lisp_t object",
            "product_bytes_changed": 0,
            "capacity_effect_bytes": 0},
        "one_truth_correction": {
            "consumer": "c2_product_install",
            "retired_derivation": "c2_facade_intern(\"t\")",
            "authority": "eval_init:lisp_t",
            "new_storage_bytes": 0,
            "source_gate": source_gate["canonical_t"],
            "linked_gate": canonical},
        "walls": walls,
        "capacity": capacity,
        "measured_recovery": {
            "before_text_headroom_bytes": 30,
            "after_text_headroom_bytes":
                walls["bank0_text_headroom_bytes"],
            "recovered_text_bytes":
                walls["bank0_text_headroom_bytes"] - 30,
            "required_text_headroom_bytes": 32},
        "frozen_identity": value["frozen_identity"],
        "qualification_replay": bind(REPLAY_RECEIPT),
        "execution_accounting": {
            "whole_program_lto_closure_links": 1,
            "pure_replay_compiler_runs": 0,
            "pure_replay_linker_runs": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0},
        "counters": {
            "class_b_diagnostic_cycles": "3/3 closed",
            "line1_product_first_reds": "2/3",
            "completed_latency_measurements": "0/2"},
        "next_gate": "authorized successor product link",
    }
    write(RECEIPT, final)
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-canonical-t-replay: PASS "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"session={capacity['session_family_bytes']} compiler=0 linker=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-canonical-t-replay: FIRST RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
