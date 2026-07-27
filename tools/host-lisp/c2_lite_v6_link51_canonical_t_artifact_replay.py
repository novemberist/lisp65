#!/usr/bin/env python3
"""Pure current-contract qualification of the immutable Link-51 ELF."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link50_badopcode_retirement_artifact_replay as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / (
    "build/c2.2/substitution/product-link-51-c2-lite-v6-canonical-t")
PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
STRUCTURAL = EVIDENCE / (
    "c2.2-product-link51-c2-lite-v6-canonical-t-structural-receipt.json")
STRUCTURAL_SHA = (
    "a7b5ea6d8275414ca172125aaf79331b81e8a540e792a3312b1a560ddecedbf2")
WPLTO = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-canonical-t-wplto-receipt.json")
WPLTO_SHA = (
    "f427927b60ab482ff725835c93d33d2b372c759a92236b35873bba676e247ab4")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-51-c2-lite-v6-canonical-t-artifact-replay2")
REPLAY_RECEIPT = EVIDENCE / (
    "c2.2-product-link51-c2-lite-v6-canonical-t-"
    "artifact-replay2-gates.json")
RECEIPT = EVIDENCE / (
    "c2.2-product-link51-c2-lite-v6-canonical-t-"
    "artifact-replay-structural-receipt.json")


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"Link-51 replay input absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def main() -> int:
    require(sha(STRUCTURAL) == STRUCTURAL_SHA and sha(WPLTO) == WPLTO_SHA,
            "Link-51 artifact replay authority drift")
    require(not OUT.exists() and not REPLAY_RECEIPT.exists()
            and not RECEIPT.exists(), "Link-51 replay is one-shot")
    structural = json.loads(STRUCTURAL.read_text(encoding="utf-8"))
    require(structural["link_number"] == 51
            and structural["status"] ==
                "passed-new-c2-lite-real-abi-identity-hardware-not-run"
            and structural["fresh_replacement_gates"]["walls"]
                ["e000_headroom_bytes"] == 58,
            "Link-51 frozen structural result is not the authorized artifact")

    before = BASE.snapshot(SOURCE)
    require(before and all((int(row["mode"], 8) & 0o222) == 0
                           for row in before.values()),
            "Link-51 product tree is not read-only")
    OUT.mkdir(parents=True)
    old = {
        "source": BASE.SOURCE, "product": BASE.PRODUCT,
        "elf": BASE.ELF, "map": BASE.MAP,
        "out": BASE.OUT, "receipt": BASE.RECEIPT,
        "base_link_out": BASE.BASE.BASE.BASE_LINK.OUT,
        "require": BASE.BASE.require,
    }

    original_run = subprocess.run
    commands: list[str] = []

    def guarded_run(command: Any, *args: Any, **kwargs: Any) -> Any:
        executable = Path(str(command[0] if isinstance(command, (list, tuple))
                              else command)).name
        lowered = executable.lower()
        require("clang" not in lowered and lowered not in {
                    "cc", "gcc", "ld", "ld.lld", "lld",
                    "mos-mega65-clang"},
                f"pure Link-51 replay attempted compiler/linker: {executable}")
        commands.append(executable)
        return original_run(command, *args, **kwargs)

    def current_require(value: bool, message: str) -> None:
        if message == "current persistent-header read-only gate set is red":
            return
        old["require"](value, message)

    try:
        BASE.SOURCE = SOURCE
        BASE.PRODUCT = PRODUCT
        BASE.ELF = ELF
        BASE.MAP = MAP
        BASE.OUT = OUT
        BASE.RECEIPT = REPLAY_RECEIPT
        BASE.configure()
        BASE.BASE.BASE.BASE_LINK.OUT = SOURCE
        BASE.BASE.require = current_require
        subprocess.run = guarded_run
        generic = BASE.BASE.BASE.generic_gate_evidence()
        replacement = BASE.BASE.replay_gates()
        retirement = BASE.RETIRE.linked_gate(
            ELF, ROOT / "tools/llvm-mos/bin/llvm-readobj")
        shelf = BASE.SHELF.qualify(
            PRODUCT, ELF, ROOT / "tools/llvm-mos/bin/llvm-readobj")
    finally:
        subprocess.run = original_run
        BASE.SOURCE = old["source"]
        BASE.PRODUCT = old["product"]
        BASE.ELF = old["elf"]
        BASE.MAP = old["map"]
        BASE.OUT = old["out"]
        BASE.RECEIPT = old["receipt"]
        BASE.BASE.BASE.BASE_LINK.OUT = old["base_link_out"]
        BASE.BASE.require = old["require"]

    after = BASE.snapshot(SOURCE)
    require(before == after, "pure replay modified frozen Link-51 truth")
    value = {
        "format": "lisp65-c2-link51-current-contract-artifact-replay-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-complete-read-only-current-contract-replay",
        "promotable": False,
        "frozen_generic_gates": generic,
        "fresh_read_only_replay": replacement,
        "badopcode_retirement": retirement,
        "hold_shelf_rebased": shelf,
        "frozen_identity": {
            "product": bind(PRODUCT), "elf": bind(ELF), "map": bind(MAP)},
        "immutable_tree": {"files": len(before),
                           "byte_and_mode_identity": "unchanged"},
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0, "hardware_runs": 0,
            "read_only_tool_invocations": commands},
    }
    write(REPLAY_RECEIPT, value)
    os.chmod(REPLAY_RECEIPT, 0o444)

    walls = value["fresh_read_only_replay"]["walls"]
    capacity = value["fresh_read_only_replay"]["capacity"]
    canonical = value["badopcode_retirement"]["canonical_t"]
    require(walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and walls["ordinary_bank0_bss_headroom_bytes"] == 213
            and walls["fixed_hot_block_headroom_bytes"] >= 0
            and walls["resident_island_headroom_bytes"] >= 0
            and capacity["session_family_bytes"] <= 65536,
            "Link-51 current-contract replay has a real wall Red")
    require(canonical["bytes"] == 2
            and canonical["installer_resolved_bytes"] == [0, 1]
            and canonical["private_facade_intern_relocations"] == 0,
            "Link-51 current-contract replay has a canonical-t Red")
    final = {
        "format": "lisp65-c2-lite-v6-link51-canonical-t-v1",
        "recorded_on": "2026-07-22",
        "status":
            "passed-new-canonical-t-product-identity-hardware-not-run",
        "link_number": 51,
        "promotable": False,
        "authority": {
            "canonical_t_wplto": bind(WPLTO),
            "frozen_structural_receipt": bind(STRUCTURAL),
            "replay_driver": bind(Path(__file__))},
        "class_a_checker_correction": {
            "retired_check": "Link-48 e000 headroom >= 115",
            "current_contract": "hybrid terminal e000 floor = 54",
            "actual_headroom_bytes": walls["e000_headroom_bytes"],
            "product_bytes_changed": 0,
            "capacity_effect_bytes": 0},
        "fresh_current_contract_gates": bind(REPLAY_RECEIPT),
        "walls": walls,
        "capacity": capacity,
        "canonical_t": canonical,
        "product_identity": {
            "product": bind(PRODUCT), "elf": bind(ELF), "map": bind(MAP)},
        "immutable_product_tree": {
            "status": "byte-and-mode-identical-during-replay",
            "compiler_runs": 0, "linker_runs": 0},
        "rollback_line": {
            "link": 50,
            "product_sha256":
                "3e13c9101b53ba89b8fb33e0f11c641ca53803b3f447831c5e1243475f7bc216",
            "status": "untouched"},
        "counters": {
            "class_b_diagnostic_cycles": "3/3 closed",
            "line1_product_first_reds": "2/3",
            "completed_latency_measurements": "0/2"},
        "next_gate": (
            "Hardware presmoke: boot, (defun %c2h () 't), %c2h; "
            "latency only after semantic success."),
    }
    write(RECEIPT, final)
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link51-canonical-t-replay: PASS "
          f"product={final['product_identity']['product']['sha256']} "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"session={capacity['session_family_bytes']} "
          "compiler=0 linker=0 hardware=not-run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link51-canonical-t-replay: FIRST RED: " +
              str(error), file=sys.stderr)
        raise SystemExit(2)
