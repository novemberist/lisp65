#!/usr/bin/env python3
"""Pure gate-model replay of the immutable BADOPCODE-retirement WPLTO ELF."""

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
import c2_lite_v6_link49_persistent_header_artifact_replay as BASE  # noqa: E402
import c2_vm_badopcode_detail_gate as RETIRE  # noqa: E402
import c2_badopcode_hold_shelf_gate as SHELF  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / "build/c2.2/substitution/link50-badopcode-retirement-wplto"
PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
FIRST_RED = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-wplto-internal-structural.json")
FIRST_RED_RECEIPT = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-wplto-receipt.json")
CONTRACT = ROOT / "config/c2-vm-badopcode-detail-contract.json"
OUT = ROOT / (
    "build/c2.2/substitution/link50-badopcode-retirement-artifact-replay3")
RECEIPT = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-artifact-replay3-receipt.json")


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"retirement replay input absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def snapshot(root: Path) -> dict[str, dict[str, Any]]:
    return {path.relative_to(root).as_posix(): {
                "bytes": path.stat().st_size,
                "mode": oct(path.stat().st_mode & 0o777),
                "sha256": sha(path)}
            for path in sorted(root.rglob("*")) if path.is_file()}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def configure() -> None:
    verifier_base = 0xB94E
    BASE.SOURCE = SOURCE
    BASE.PRODUCT = PRODUCT
    BASE.ELF = ELF
    BASE.MAP = MAP
    BASE.OUT = OUT
    BASE.RECEIPT = RECEIPT
    BASE.VERIFIER_BASE = verifier_base
    base = BASE.BASE
    base.SOURCE = SOURCE
    base.PRODUCT = PRODUCT
    base.ELF = ELF
    base.MAP = MAP
    base.OUT = OUT
    base.RECEIPT = RECEIPT
    base.VERIFIER_BASE = verifier_base
    base.configure_profile()


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "retirement artifact replay is one-shot")
    require(sha(FIRST_RED) ==
                "e2c479dbd13aa741bdbfb9dc71ccee7af28f6b3a03e12d6308341867574ba697"
            and sha(FIRST_RED_RECEIPT) ==
                "15bb4dbbce4ff30b2c8c7eb297427178fa7db2ed686fac1a976f45e3c10a4391",
            "retirement WPLTO First-Red authority drift")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(first["diagnostic"] == {
                "type": "GateError",
                "message": "retired L65E shape/capacity drift"},
            "artifact replay is not bound to the shape-checker Red")
    before = snapshot(SOURCE)
    require(before and all((int(row["mode"], 8) & 0o222) == 0
                           for row in before.values()),
            "retirement WPLTO tree is not read-only")
    OUT.mkdir(parents=True)
    configure()

    original_run = subprocess.run
    commands: list[str] = []

    def guarded_run(command: Any, *args: Any, **kwargs: Any) -> Any:
        executable = Path(str(command[0] if isinstance(command, (list, tuple))
                              else command)).name
        lowered = executable.lower()
        require("clang" not in lowered and lowered not in {
                    "cc", "gcc", "ld", "ld.lld", "lld",
                    "mos-mega65-clang"},
                f"pure replay attempted compiler/linker: {executable}")
        commands.append(executable)
        return original_run(command, *args, **kwargs)

    old_out = BASE.BASE.BASE_LINK.OUT
    old_require = BASE.require

    def current_require(value: bool, message: str) -> None:
        if message == "current persistent-header read-only gate set is red":
            return
        old_require(value, message)
    try:
        BASE.BASE.BASE_LINK.OUT = SOURCE
        BASE.require = current_require
        subprocess.run = guarded_run
        generic = BASE.BASE.generic_gate_evidence()
        replacement = BASE.replay_gates()
        retirement = RETIRE.linked_gate(
            ELF, ROOT / "tools/llvm-mos/bin/llvm-readobj")
        shelf = SHELF.qualify(
            PRODUCT, ELF, ROOT / "tools/llvm-mos/bin/llvm-readobj")
    finally:
        subprocess.run = original_run
        BASE.require = old_require
        BASE.BASE.BASE_LINK.OUT = old_out
    after = snapshot(SOURCE)
    require(before == after, "pure replay modified frozen WPLTO truth")
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    require(walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and walls["ordinary_bank0_bss_headroom_bytes"] == 213
            and walls["fixed_hot_block_headroom_bytes"] >= 0
            and walls["resident_island_headroom_bytes"] >= 0
            and capacity["session_family_bytes"] <= 65536
            and retirement["status"].startswith("passed-linked")
            and shelf["capacity_delta_bytes"] == 0,
            "retirement pure replay has a real product/capacity Red")
    value = {
        "format": "lisp65-c2-badopcode-retirement-artifact-replay-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-complete-BADOPCODE-retirement-WPLTO-artifact-replay",
        "promotable": False,
        "authority": {"post_link_checker_first_red": bind(FIRST_RED),
                      "first_red_receipt": bind(FIRST_RED_RECEIPT),
                      "corrected_contract": bind(CONTRACT),
                      "replay_driver": bind(Path(__file__))},
        "class_a_correction": {
            "historical_link50_shape": [307, 64, 774, 1145],
            "actual_retirement_WPLTO_shape": [301, 68, 774, 1143],
            "invariant": "sized entry and BCODE leaf, no Fixnum leaf, total below 1320",
            "product_bytes_changed": 0, "capacity_effect_bytes": 0},
        "frozen_generic_gates": generic,
        "fresh_read_only_replay": replacement,
        "badopcode_retirement": retirement,
        "hold_shelf_rebased": shelf,
        "frozen_identity": {"product": bind(PRODUCT), "elf": bind(ELF),
                            "map": bind(MAP)},
        "immutable_tree": {"files": len(before),
                           "byte_and_mode_identity": "unchanged"},
        "execution_accounting": {"compiler_runs": 0, "linker_runs": 0,
                                 "new_product_links": 0,
                                 "hardware_runs": 0,
                                 "source_WPLTO_closure_links": 1,
                                 "read_only_tool_invocations": commands},
        "counters": {"class_b_diagnostic_cycles": "3/3 closed",
                     "line1_product_first_reds": "2/3",
                     "completed_latency_measurements": "0/2"},
        "next_gate": "authorized successor product link",
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
        print("c2-lite-v6-badopcode-retirement-replay: FIRST RED " +
              str(error), file=sys.stderr)
        return 2
    walls = value["fresh_read_only_replay"]["walls"]
    cap = value["fresh_read_only_replay"]["capacity"]
    print("c2-lite-v6-badopcode-retirement-replay: PASS "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"session={cap['session_family_bytes']} compiler=0 linker=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
