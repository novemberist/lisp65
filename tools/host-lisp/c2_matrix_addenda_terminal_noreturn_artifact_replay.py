#!/usr/bin/env python3
"""Pure replay of the completed E5 cold-front WPLTO artifact.

The closure link and all product bytes are frozen.  This replay exists only
because the historical BADOPCODE-retirement gate still pinned the pre-E5
error-renderer shape.  Compiler and linker entry points are forbidden.
"""

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
import c2_matrix_b3_d3_break_delivery as B3D3  # noqa: E402
import c2_matrix_c3_handoff_freezer as C3  # noqa: E402
import c2_matrix_e5_nesting_depth as E5  # noqa: E402
import c2_vm_badopcode_detail_gate as RETIRE  # noqa: E402
import c2_zero_literal_execution_gate as ZERO  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-cold-front-terminal-noreturn-wplto-replay2")
PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
C2D = SOURCE / (
    "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
FIRST_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-front-terminal-noreturn-"
    "wplto-replay2-receipt.json")
FIRST_INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-front-terminal-noreturn-"
    "wplto-replay2-internal.json")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-cold-front-terminal-noreturn-artifact-replay2")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-front-terminal-noreturn-"
    "artifact-replay2-receipt.json")
PREVIOUS_OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-cold-front-terminal-noreturn-artifact-replay")


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


def fixture(path: Path, status: str, mutations: int) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(value["status"] == status, f"fixture status drift: {path.name}")
    require(len(value["mutations"]) == mutations,
            f"fixture mutation count drift: {path.name}")
    return value


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "cold-front artifact replay is one-shot")
    require(
        (PREVIOUS_OUT / "final-island-single-runtime-identity.json").is_file(),
        "first artifact-replay checker stop is absent")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    internal = json.loads(FIRST_INTERNAL.read_text(encoding="utf-8"))
    require(
        first["status"] ==
            "FIRST RED: historical checker stopped current-product "
            "L-full keymap WPLTO"
        and internal["diagnostic"] == {
            "type": "GateError",
            "message": "retired L65E shape/capacity drift"}
        and internal["execution_accounting"]["product_closure_links"] == 1,
        "L65E-shape checker First Red drift")
    before = snapshot(SOURCE)
    require(before and all((int(row["mode"], 8) & 0o222) == 0
                           for row in before.values()),
            "completed WPLTO tree is not read-only")
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
        retirement_source = RETIRE.source_gate(mutations=True)
        retirement_linked = RETIRE.linked_gate(
            ELF, ROOT / "tools/llvm-mos/bin/llvm-readobj")
    finally:
        subprocess.run = original_run
        BASE.BASE.BASE.BASE_LINK.OUT = old_out
    require(before == snapshot(SOURCE),
            "artifact replay modified the frozen WPLTO tree")

    b3d3 = fixture(
        B3D3.RECEIPT,
        "passed-host-source-model-awaiting-hardware-queue-full", 16)
    c3 = json.loads(C3.RECEIPT.read_text(encoding="utf-8"))
    e5 = fixture(
        E5.RECEIPT,
        "passed-product-shaped-host-awaiting-real-eval-hardware", 14)
    walls = replay["walls"]
    capacity = replay["capacity"]
    require(
        walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and capacity["session_family_bytes"] <= 65536
        and capacity["session_family_headroom_bytes"] >= 0
        and plane["static_code_bytes"] == 34509
        and plane["mutations_rejected"] == 6
        and keymap["status"] ==
            "passed-queue-tuple-to-compiled-product-action"
        and keymap["mutations_rejected"] == 10
        and zero["c2d_witness"]["literal_count"] == 0
        and retirement_source["status"] ==
            "passed-BADOPCODE-detail-retired-DIRMISS-preserved"
        and retirement_linked["l65e"] == {
            "entry_bytes": 333,
            "ordinal_leaf_bytes": 68,
            "table_bytes": 803,
            "slice_bytes": 1204,
            "slice_headroom_bytes": 116}
        and len(c3["mutations"]) == 6
        and len(e5["cases"]) == 5,
        "cold-front simultaneous replay qualification red")

    value = {
        "format":
            "lisp65-c2-link58-matrix-addenda-cold-front-"
            "terminal-noreturn-artifact-replay-v1",
        "recorded_on": "2026-07-23",
        "status":
            "passed-E5-cold-front-existing-seam-WPLTO-all-walls-green",
        "promotable": False,
        "authority": {
            "WPLTO_checker_first_red": bind(FIRST_RED),
            "WPLTO_checker_diagnosis": bind(FIRST_INTERNAL),
            "updated_BADOPCODE_retirement_contract": bind(RETIRE.CONTRACT),
            "BADOPCODE_retirement_gate": bind(Path(RETIRE.__file__)),
            "B3_D3_fixture": bind(B3D3.RECEIPT),
            "C3_fixture": bind(C3.RECEIPT),
            "E5_fixture": bind(E5.RECEIPT),
            "replay_driver": bind(Path(__file__)),
        },
        "class_A_correction": {
            "old_L65E_shape": {
                "entry_bytes": 301,
                "ordinal_leaf_bytes": 68,
                "table_bytes": 774,
                "slice_bytes": 1143},
            "authorized_E5_shape": retirement_linked["l65e"],
            "cause":
                "the BADOPCODE-retirement checker remembered the pre-E5 "
                "renderer while the approved code-63/Fixnum-5 seam expanded "
                "the same L65E slice",
            "product_bytes_changed": 0,
            "capacity_effect_bytes": 0,
        },
        "class_A_followup_correction": {
            "first_replay_stop":
                "the BCODE ordinal linked gate independently retained the "
                "same pre-E5 literal renderer shape",
            "correction":
                "the linked gate now consumes l65e_expected_shape from the "
                "same current BADOPCODE-retirement renderer contract",
            "first_replay_partial_evidence": bind(
                PREVIOUS_OUT / "final-island-single-runtime-identity.json"),
            "product_bytes_changed": 0,
            "capacity_effect_bytes": 0,
        },
        "frozen_generic_gates": generic,
        "fresh_read_only_replay": replay,
        "L_full_product_plane": {
            "static_plane_gate": plane,
            "zero_literal_execution": zero,
        },
        "queue_to_action_gate": keymap,
        "BADOPCODE_retirement": {
            "source": retirement_source,
            "linked": retirement_linked,
        },
        "matrix_addenda": {
            "B3_D3": b3d3["status"],
            "C3": c3["status"],
            "E5": e5["status"],
        },
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
        "next_gate":
            "authorized successor product link, then bundled C1 Freezer "
            "cutpoints",
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
            "c2-matrix-addenda-terminal-noreturn-artifact-replay: "
            "FIRST RED: " + str(error),
            file=sys.stderr)
        return 2
    replay = value["fresh_read_only_replay"]
    print(
        "c2-matrix-addenda-terminal-noreturn-artifact-replay: PASS "
        f"text={replay['walls']['bank0_text_headroom_bytes']} "
        f"e000={replay['walls']['e000_headroom_bytes']} "
        f"session={replay['capacity']['session_family_bytes']} "
        "compiler=0 linker=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
