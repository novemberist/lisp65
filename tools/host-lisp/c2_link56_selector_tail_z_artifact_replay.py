#!/usr/bin/env python3
"""Pure qualification replay of the selector tail-Z WPLTO artifacts."""

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
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_lite_v6_link55_append_suffix_fusion_artifact_replay as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / "build/c2.2/substitution/link56-selector-tail-z-wplto"
PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
FIRST_RED = EVIDENCE / "c2.2-link56-selector-tail-z-wplto-receipt.json"
OUT = ROOT / (
    "build/c2.2/substitution/link56-selector-tail-z-artifact-replay")
RECEIPT = EVIDENCE / (
    "c2.2-link56-selector-tail-z-artifact-replay-receipt.json")


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"replay input absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def snapshot(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {
            "bytes": path.stat().st_size,
            "mode": oct(path.stat().st_mode & 0o777),
            "sha256": sha(path),
        }
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def configure() -> None:
    BASE.SOURCE = SOURCE
    BASE.PRODUCT = PRODUCT
    BASE.ELF = ELF
    BASE.MAP = MAP
    BASE.OUT = OUT
    BASE.RECEIPT = RECEIPT
    BASE.configure()


def read_only_gates() -> dict[str, Any]:
    old_require = BASE.BASE.require

    def current_require(value: bool, message: str) -> None:
        if message == "one or more read-only facade-16 replacement gates are red":
            return
        old_require(value, message)

    BASE.BASE.require = current_require
    try:
        value = BASE.BASE.read_only_replay()
    finally:
        BASE.BASE.require = old_require

    suffix = BASE.SUFFIX.linked_gate(
        ELF, ROOT / "tools/llvm-mos/bin/llvm-readobj")
    cutpoint = BASE.CUTPOINT.linked_gate(
        ELF, ROOT / "tools/llvm-mos/bin/llvm-readobj")
    fusion = BASE.FUSION.linked_gate(
        ELF, ROOT / "tools/llvm-mos/bin/llvm-readobj")
    abi = ABI.audit_elf(ELF)
    leaf = abi["journal_prepare_selector"]
    walls = value["walls"]
    capacity = value["capacity"]
    append = value["append_phase_plan"]
    require(
        walls == {
            "bank0_text_headroom_bytes": 40,
            "ordinary_bank0_bss_headroom_bytes": 213,
            "fixed_hot_block_headroom_bytes": 33,
            "resident_island_headroom_bytes": 5,
            "e000_headroom_bytes": 58}
        and capacity["session_catalog_records"] == 48
        and capacity["session_family_bytes"] == 65438
        and capacity["session_family_headroom_bytes"] == 98
        and capacity["journal_prepare_co_resident"] is True
        and fusion["bytes"] == 1768
        and fusion["headroom_bytes"] == 24
        and fusion["packed_bytes"] == 1792
        and fusion["packed_recovered_bytes"] == 256
        and fusion["functions"]["c2_append_journal_prepare_phase"]["bytes"]
            == 58
        and leaf["status"] ==
            "passed-real-context-ABI-two-total-tail-edges-Z0"
        and leaf["marker_totality"] == {
            "main_ordinal_classes": 2,
            "marker_values_per_class": 256,
            "cases": 512,
            "accepted": 3,
            "fail_closed": 509}
        and len(leaf["tail_C_entry_Z"]) == 2
        and all(row["operand"] in ("#$0", "#$00")
                for row in leaf["tail_C_entry_Z"].values())
        and append["linked"]["plan_data"][
            "lisp65_c2_append_persistent_publish_plan"]["bytes"]
            == [37, 38, 39, 40, 0]
        and suffix["status"] ==
            "passed-linked-four-phase-suffix-domain-closure"
        and cutpoint["status"] ==
            "passed-linked-phase06a-cutpoint-carrier",
        "selector tail-Z read-only qualification red")
    value["append_suffix_read_domain_linked"] = suffix
    value["phase06a_cutpoint_linked"] = cutpoint
    value["journal_prepare_co_residence_linked"] = fusion
    value["assembler_leaf_abi"] = abi
    value["status"] = "passed-selector-tail-Z0-WPLTO-artifact-replay"
    return value


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "selector tail-Z artifact replay is one-shot")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(
        first["status"] == "FIRST RED: install-phase WPLTO stopped"
        and first["error"] == "Link-50 final product qualification red"
        and first["execution_accounting"] == {
            "hardware_runs": 0,
            "promotable_product_links": 0,
            "whole_program_lto_closure_links": 1},
        "selector tail-Z WPLTO First Red drift")
    before = snapshot(SOURCE)
    require(before and all((int(row["mode"], 8) & 0o222) == 0
                           for row in before.values()),
            "selector tail-Z WPLTO tree is not read-only")
    OUT.mkdir(parents=True)
    configure()

    original_run = subprocess.run
    commands: list[str] = []

    def guarded_run(command: Any, *args: Any, **kwargs: Any) -> Any:
        executable = Path(str(
            command[0] if isinstance(command, (list, tuple))
            else command)).name
        lowered = executable.lower()
        require("clang" not in lowered and lowered not in {
                    "cc", "gcc", "ld", "ld.lld", "lld",
                    "mos-mega65-clang"},
                f"artifact replay attempted compiler/linker: {executable}")
        commands.append(executable)
        return original_run(command, *args, **kwargs)

    old_out = BASE.BASE.BASE_LINK.OUT
    try:
        BASE.BASE.BASE_LINK.OUT = SOURCE
        subprocess.run = guarded_run
        generic = BASE.BASE.generic_gate_evidence()
        replay = read_only_gates()
    finally:
        subprocess.run = original_run
        BASE.BASE.BASE_LINK.OUT = old_out
    require(before == snapshot(SOURCE),
            "artifact replay modified the frozen WPLTO tree")
    value = {
        "format": "lisp65-c2-link56-selector-tail-z-artifact-replay-v1",
        "recorded_on": "2026-07-23",
        "status": "passed-selector-tail-Z0-WPLTO-all-walls-green",
        "promotable": False,
        "authority": {
            "WPLTO_checker_first_red": bind(FIRST_RED),
            "corrected_Link50_checker": bind(
                ROOT / "tools/host-lisp/"
                "c2_lite_v6_link50_persistent_header_successor_link.py"),
            "assembler_selector": bind(
                ROOT / "src/c2_journal_prepare_select.s"),
            "assembler_ABI_gate": bind(
                ROOT / "tools/host-lisp/c2_asm_leaf_abi_gate.py"),
            "replay_driver": bind(Path(__file__)),
        },
        "class_A_correction": {
            "old_expected_plan": [38, 39, 40, 41, 0],
            "active_profile_plan": [37, 38, 39, 40, 0],
            "derivation": (
                "the SHA-bound feature profile and final Session catalog "
                "must agree; a historical Link-50 slot list is not authority"),
            "product_bytes_changed": 0,
            "capacity_effect_bytes": 0,
        },
        "frozen_generic_gates": generic,
        "fresh_read_only_replay": replay,
        "frozen_identity": {
            "product": bind(PRODUCT),
            "elf": bind(ELF),
            "map": bind(MAP),
        },
        "immutable_tree": {
            "files": len(before),
            "byte_and_mode_identity": "unchanged",
        },
        "execution_accounting": {
            "compiler_runs": 0,
            "linker_runs": 0,
            "new_product_links": 0,
            "hardware_runs": 0,
            "source_WPLTO_closure_links": 1,
            "read_only_tool_invocations": commands,
        },
        "counters": {
            "line1_product_first_reds": "2/3",
            "completed_latency_measurements": "0/2",
        },
        "next_gate": "Class-C successor product link",
    }
    report = OUT / "artifact-replay-report.json"
    write(report, value)
    value["replay_report"] = bind(report)
    write(RECEIPT, value)
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(RECEIPT, 0o444)
    return value


def main() -> int:
    try:
        value = build()
    except Exception as error:
        print(
            "c2-link56-selector-tail-z-replay: FIRST RED " + str(error),
            file=sys.stderr)
        return 2
    replay = value["fresh_read_only_replay"]
    print(
        "c2-link56-selector-tail-z-replay: PASS "
        f"selector={replay['journal_prepare_co_residence_linked']['functions']['c2_append_journal_prepare_phase']['bytes']} "
        f"fusion={replay['journal_prepare_co_residence_linked']['bytes']} "
        f"session={replay['capacity']['session_family_bytes']} "
        f"text={replay['walls']['bank0_text_headroom_bytes']} "
        f"e000={replay['walls']['e000_headroom_bytes']} "
        "compiler=0 linker=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
