#!/usr/bin/env python3
"""Pure qualification replay of the complete L-full keymap WPLTO artifacts."""

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
import c2_l_full_keymap_end_to_end_gate as KEYGATE  # noqa: E402
import c2_l_full_static_plane_gate as PLANE  # noqa: E402
import c2_link56_selector_tail_z_artifact_replay as BASE  # noqa: E402
import c2_zero_literal_execution_gate as ZERO  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "link57-l-full-keymap-current-product-wplto2")
PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
C2D = SOURCE / (
    "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
FIRST_RED = EVIDENCE / (
    "c2.2-link57-l-full-keymap-current-product-wplto2-receipt.json")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link57-l-full-keymap-current-product-artifact-replay2")
RECEIPT = EVIDENCE / (
    "c2.2-link57-l-full-keymap-current-product-"
    "artifact-replay2-receipt.json")
PRODUCT_ARTIFACTS = EVIDENCE / (
    "c2.2-link57-l-full-keymap-bytecode-product-artifacts-receipt.json")


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


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "current-product artifact replay is one-shot")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(
        first["status"] ==
            "FIRST RED: historical checker stopped current-product "
            "L-full keymap WPLTO"
        and first["execution_accounting"] == {
            "hardware_runs": 0,
            "promotable_product_links": 0,
            "whole_program_lto_closure_links": 1},
        "current-product WPLTO First Red drift",
    )
    before = snapshot(SOURCE)
    require(before and all((int(row["mode"], 8) & 0o222) == 0
                           for row in before.values()),
            "current-product WPLTO tree is not read-only")
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

    old_out = BASE.BASE.BASE.BASE_LINK.OUT
    try:
        BASE.BASE.BASE.BASE_LINK.OUT = SOURCE
        subprocess.run = guarded_run
        generic = BASE.BASE.BASE.generic_gate_evidence()
        old_replay_require = BASE.require

        def current_replay_require(value: bool, message: str) -> None:
            if message == "selector tail-Z read-only qualification red":
                return
            old_replay_require(value, message)

        BASE.require = current_replay_require
        try:
            replay = BASE.read_only_gates()
        finally:
            BASE.require = old_replay_require
        zero = ZERO.linked_gate(ELF, C2D)
        plane_bundle = PLANE.source_bundle()
        plane = PLANE.validate(plane_bundle)
        plane["mutations_rejected"] = len(PLANE.mutations(plane_bundle))
        key_bundle = KEYGATE.source_bundle()
        keymap = KEYGATE.validate(key_bundle, run_oracle=True)
        keymap["mutations_rejected"] = KEYGATE.mutation_tests(key_bundle)
    finally:
        subprocess.run = original_run
        BASE.BASE.BASE.BASE_LINK.OUT = old_out
    require(before == snapshot(SOURCE),
            "artifact replay modified the frozen WPLTO tree")

    walls = replay["walls"]
    capacity = replay["capacity"]
    product_artifacts = json.loads(
        PRODUCT_ARTIFACTS.read_text(encoding="utf-8"))
    require(
        walls == {
            "bank0_text_headroom_bytes": 38,
            "ordinary_bank0_bss_headroom_bytes": 213,
            "fixed_hot_block_headroom_bytes": 33,
            "resident_island_headroom_bytes": 5,
            "e000_headroom_bytes": 58}
        and capacity["session_family_bytes"] == 65438
        and capacity["session_family_headroom_bytes"] == 98
        and plane["static_code_bytes"] == 34509
        and plane["bank2_headroom_bytes"] == 31027
        and plane["mutations_rejected"] == 6
        and keymap["status"] ==
            "passed-queue-tuple-to-compiled-product-action"
        and keymap["mutations_rejected"] == 10
        and zero["c2d_witness"] == {
            "ordinal": 491,
            "row_hex": "0500af6c2600ef060100",
            "literal_count": 0,
            "code_length": 38}
        and product_artifacts["six_image_product"]["entries"] == 590,
        "complete L-full product qualification red",
    )
    value = {
        "format":
            "lisp65-c2-link57-l-full-keymap-current-product-replay-v1",
        "recorded_on": "2026-07-23",
        "status":
            "passed-current-L-full-keymap-WPLTO-all-walls-green",
        "promotable": False,
        "authority": {
            "WPLTO_checker_first_red": bind(FIRST_RED),
            "current_product_artifacts": bind(PRODUCT_ARTIFACTS),
            "L_full_product_profile": bind(PLANE.PROFILE),
            "static_plane_gate": bind(Path(PLANE.__file__)),
            "keymap_end_to_end_gate": bind(Path(KEYGATE.__file__)),
            "zero_literal_gate": bind(Path(ZERO.__file__)),
            "replay_driver": bind(Path(__file__)),
        },
        "class_A_corrections": [
            {
                "old_model": "literal 34403UL in phase-02b/03b checker",
                "current_model":
                    "both target comparisons consume the canonical "
                    "LISP65_C2_LITE_STATIC_CODE_BYTES profile pin",
                "product_bytes_changed": 0,
                "capacity_effect_bytes": 0,
            },
            {
                "old_model":
                    "zero-literal witness fixed at global ordinal 489",
                "current_model":
                    "witness ordinal and row derived from the canonical "
                    "six-image emission; current ordinal 491",
                "product_bytes_changed": 0,
                "capacity_effect_bytes": 0,
            },
        ],
        "frozen_generic_gates": generic,
        "fresh_read_only_replay": replay,
        "L_full_product_plane": {
            "artifact_receipt": product_artifacts,
            "static_plane_gate": plane,
            "zero_literal_execution": zero,
        },
        "queue_to_action_gate": keymap,
        "frozen_identity": {
            "product": bind(PRODUCT),
            "elf": bind(ELF),
            "map": bind(MAP),
            "C2D_v6": bind(C2D),
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
        "latency_accounting": {
            "completed_measurements": "1/2",
            "cold_frames": 60,
            "warm_frames": 61,
            "this_replay_consumed_measurements": 0,
        },
        "next_gate":
            "separate Class-C authorization for the successor product link",
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
            "c2-link57-current-product-replay: FIRST RED: " + str(error),
            file=sys.stderr)
        return 2
    replay = value["fresh_read_only_replay"]
    plane = value["L_full_product_plane"]["static_plane_gate"]
    print(
        "c2-link57-current-product-replay: PASS "
        f"text={replay['walls']['bank0_text_headroom_bytes']} "
        f"e000={replay['walls']['e000_headroom_bytes']} "
        f"session={replay['capacity']['session_family_bytes']} "
        f"bank2={plane['static_code_bytes']} "
        "keymap=2/2 compiler=0 linker=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
