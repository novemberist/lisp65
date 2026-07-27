#!/usr/bin/env python3
"""Pure qualification of the immutable phase-self-stamp WPLTO truth."""

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
import c2_install_phase_discriminator_gate as PHASE  # noqa: E402
import c2_lite_v6_link48_zero_literal_successor_link as FLOOR  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / (
    "build/c2.2/substitution/link52-phase-self-stamp-wplto-replay3")
PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
INTERNAL = EVIDENCE / (
    "c2.2-link52-phase-self-stamp-wplto-replay3-internal-structural.json")
INTERNAL_SHA = (
    "f7e9113d4e56a1110ecad930be06dfca2a27b7e8262b6dd291bab23c7fee67eb")
FIRST_RED = EVIDENCE / (
    "c2.2-link52-phase-self-stamp-wplto-replay3-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link52-phase-self-stamp-wplto-artifact-replay-receipt.json")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact replay input absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


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
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def main() -> int:
    require(not RECEIPT.exists(), "phase-self-stamp artifact replay is one-shot")
    require(sha(INTERNAL) == INTERNAL_SHA,
            "immutable WPLTO structural receipt drift")
    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    first_red = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    identity = internal["product_identity"]
    for path, field in ((PRODUCT, "product"), (ELF, "elf"), (MAP, "map")):
        require(sha(path) == identity[field]["sha256"],
                f"immutable WPLTO {field} identity drift")
    require(internal["status"] ==
                "passed-new-c2-lite-real-abi-identity-hardware-not-run"
            and internal["fresh_replacement_gates"]["status"] == "passed"
            and first_red["error"] == "Link-48 post-receipt qualification red",
            "artifact replay does not bind the expected checker-only First Red")

    before = snapshot(SOURCE)
    require(before and all((int(row["mode"], 8) & 0o222) == 0
                           for row in before.values()),
            "WPLTO truth tree is not entirely read-only")
    commands: list[str] = []
    original_run = subprocess.run

    def guarded_run(command: Any, *args: Any, **kwargs: Any) -> Any:
        executable = Path(str(command[0] if isinstance(command, (list, tuple))
                              else command)).name
        lowered = executable.lower()
        require("clang" not in lowered and lowered not in {
                    "cc", "gcc", "ld", "ld.lld", "lld",
                    "mos-mega65-clang"},
                f"artifact replay attempted compiler/linker: {executable}")
        commands.append(executable)
        return original_run(command, *args, **kwargs)

    try:
        subprocess.run = guarded_run
        source_gate = PHASE.source_gate(mutations=True)
        linked_gate = PHASE.linked_gate(ELF, READOBJ)
    finally:
        subprocess.run = original_run

    after = snapshot(SOURCE)
    require(before == after, "artifact replay modified immutable WPLTO truth")
    gates = internal["fresh_replacement_gates"]
    walls = gates["walls"]
    capacity = gates["capacity"]
    active_floor = FLOOR.current_e000_floor()
    require(active_floor == 54
            and walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= active_floor
            and walls["ordinary_bank0_bss_headroom_bytes"] == 213
            and walls["fixed_hot_block_headroom_bytes"] >= 0
            and walls["resident_island_headroom_bytes"] >= 0
            and capacity["session_family_bytes"] <= 65536
            and linked_gate["new_state_objects"] == 0
            and linked_gate["scratch"]["bytes"] == 304,
            "immutable WPLTO truth crosses an active wall or phase gate")

    value = {
        "format": "lisp65-c2-link52-phase-self-stamp-artifact-replay-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-read-only-current-contract-WPLTO-qualification",
        "promotable": False,
        "authority": {
            "immutable_internal_receipt": bind(INTERNAL),
            "checker_only_first_red": bind(FIRST_RED),
            "hybrid_contract": bind(FLOOR.HYBRID_CONTRACT),
            "phase_contract": bind(PHASE.CONTRACT),
            "replay_driver": bind(Path(__file__)),
        },
        "class_a_checker_correction": {
            "retired_private_expectation_bytes": 115,
            "active_contract_floor_bytes": active_floor,
            "derivation": "config/c2-append-final-hybrid-contract.json",
            "product_bytes_changed": 0,
            "capacity_effect_bytes": 0,
        },
        "phase_self_stamp": {"source": source_gate, "linked": linked_gate},
        "walls": walls,
        "capacity": capacity,
        "baseline_delta": {
            "bank0_text_bytes": 43 - walls["bank0_text_headroom_bytes"],
            "ordinary_bss_bytes": 213 -
                walls["ordinary_bank0_bss_headroom_bytes"],
            "e000_bytes": 58 - walls["e000_headroom_bytes"],
            "session_family_bytes": capacity["session_family_bytes"] - 65438,
        },
        "identity": {"product": bind(PRODUCT), "elf": bind(ELF),
                     "map": bind(MAP)},
        "immutable_tree": {"files": len(before),
                           "byte_and_mode_identity": "unchanged"},
        "execution_accounting": {
            "original_whole_program_lto_closure_links": 1,
            "replay_compiler_runs": 0, "replay_linker_runs": 0,
            "promotable_product_links": 0, "hardware_runs": 0,
            "read_only_tool_invocations": commands,
        },
        "counters": {"line1_product_first_reds": "2/3",
                     "completed_latency_measurements": "0/2"},
        "next_gate": "authorized successor product Link 52",
    }
    write(RECEIPT, value)
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link52-phase-self-stamp-artifact-replay: PASS "
          f"product={identity['product']['sha256']} "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"session={capacity['session_family_bytes']} "
          "compiler=0 linker=0 hardware=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link52-phase-self-stamp-artifact-replay: FIRST RED: "
              + str(error), file=sys.stderr)
        raise SystemExit(2)
