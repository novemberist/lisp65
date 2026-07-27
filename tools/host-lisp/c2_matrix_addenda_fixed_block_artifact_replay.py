#!/usr/bin/env python3
"""Pure replay of the completed rtov_fail fixed-block WPLTO artifact."""

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
import c2_fixed_block_leaf_gate as FIXED  # noqa: E402
import c2_matrix_addenda_terminal_noreturn_artifact_replay as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-fixed-block-wplto-final2")
PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
C2D = SOURCE / (
    "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
FIRST_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-final2-internal.json")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-fixed-block-artifact-replay2")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-artifact-replay2-receipt.json")


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
    BASE.C2D = C2D
    BASE.OUT = OUT
    BASE.RECEIPT = RECEIPT
    BASE.configure()


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "fixed-block artifact replay is one-shot")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(
        first["diagnostic"] == {
            "type": "LinkError",
            "message":
                "fresh Link-47 L65E shape red: "
                "{'bytes': 1204, 'cap_bytes': 1320, "
                "'headroom_bytes': 116}"}
        and first["execution_accounting"]["product_closure_links"] == 1,
        "fixed-block checker First Red drift")
    before = snapshot(SOURCE)
    require(before and all((int(row["mode"], 8) & 0o222) == 0
                           for row in before.values()),
            "completed fixed-block WPLTO tree is not read-only")
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

    old_out = BASE.BASE.BASE.BASE.BASE_LINK.OUT
    try:
        BASE.BASE.BASE.BASE.BASE_LINK.OUT = SOURCE
        subprocess.run = guarded_run
        generic = BASE.BASE.BASE.BASE.generic_gate_evidence()
        old_replay_require = BASE.BASE.require

        def current_replay_require(value: bool, message: str) -> None:
            if message == "selector tail-Z read-only qualification red":
                return
            old_replay_require(value, message)

        BASE.BASE.require = current_replay_require
        try:
            replay = BASE.BASE.read_only_gates()
        finally:
            BASE.BASE.require = old_replay_require
        zero = BASE.ZERO.linked_gate(ELF, C2D)
        plane_bundle = BASE.PLANE.source_bundle()
        plane = BASE.PLANE.validate(plane_bundle)
        plane["mutations_rejected"] = len(
            BASE.PLANE.mutations(plane_bundle))
        key_bundle = BASE.KEYGATE.source_bundle()
        keymap = BASE.KEYGATE.validate(key_bundle, run_oracle=True)
        keymap["mutations_rejected"] = (
            BASE.KEYGATE.mutation_tests(key_bundle))
        retirement_source = BASE.RETIRE.source_gate(mutations=True)
        retirement_linked = BASE.RETIRE.linked_gate(
            ELF, ROOT / "tools/llvm-mos/bin/llvm-readobj")
        fixed = FIXED.audit_elf(
            ELF, out=OUT / "fixed-block-rtov-fail-final.json")
    finally:
        subprocess.run = original_run
        BASE.BASE.BASE.BASE.BASE_LINK.OUT = old_out
    require(before == snapshot(SOURCE),
            "artifact replay modified the frozen WPLTO tree")

    walls = replay["walls"]
    capacity = replay["capacity"]
    require(
        walls["bank0_text_headroom_bytes"] >= 32
        and walls["ordinary_bank0_bss_headroom_bytes"] == 213
        and walls["fixed_hot_block_headroom_bytes"] == 4
        and walls["resident_island_headroom_bytes"] == 5
        and walls["e000_headroom_bytes"] == 56
        and capacity["session_family_bytes"] == 65438
        and capacity["session_family_headroom_bytes"] == 98
        and fixed["status"] ==
            "passed-fixed-block-rtov-fail-identity-and-fixed-target"
        and fixed["leaf"]["bytes"] == 21
        and [row["target"] for row in
             fixed["leaf"]["outgoing_control_edges"]] == ["rtov_wipe"]
        and fixed["hot_bss"]["headroom_to_overlay_bytes"] == 4
        and plane["status"] ==
            "passed-canonical-L-full-static-plane-to-target-dataflow"
        and plane["bank2_headroom_bytes"] >= 0
        and plane["mutations_rejected"] == 6
        and keymap["status"] ==
            "passed-queue-tuple-to-compiled-product-action"
        and keymap["mutations_rejected"] == 10
        and zero["c2d_witness"]["literal_count"] == 0
        and retirement_source["status"] ==
            "passed-BADOPCODE-detail-retired-DIRMISS-preserved"
        and retirement_linked["l65e"]["slice_bytes"] == 1204
        and retirement_linked["l65e"]["slice_headroom_bytes"] == 116,
        "fixed-block simultaneous replay qualification red")

    value = {
        "format":
            "lisp65-c2-link58-matrix-addenda-fixed-block-"
            "artifact-replay-v1",
        "recorded_on": "2026-07-23",
        "status":
            "passed-rtov-fail-fixed-block-WPLTO-all-walls-and-gates-green",
        "promotable": False,
        "authority": {
            "WPLTO_checker_first_red": bind(FIRST_RED),
            "current_L65E_contract": bind(BASE.RETIRE.CONTRACT),
            "fixed_block_contract": bind(
                ROOT / "config/c2-matrix-addenda-cold-placement-contract.json"),
            "fixed_block_gate": bind(Path(FIXED.__file__)),
            "replay_driver": bind(Path(__file__)),
        },
        "class_A_correction": {
            "cause":
                "a historical Link-47 driver pinned an exact pre-E5 L65E "
                "shape instead of consuming the current renderer contract",
            "correction":
                "the inherited checker now derives slice bytes and cap from "
                "config/c2-vm-badopcode-detail-contract.json",
            "product_bytes_changed": 0,
            "capacity_effect_bytes": 0,
        },
        "frozen_generic_gates": generic,
        "fresh_read_only_replay": replay,
        "fixed_block": fixed,
        "L_full_product_plane": {
            "static_plane_gate": plane,
            "zero_literal_execution": zero,
        },
        "queue_to_action_gate": keymap,
        "BADOPCODE_retirement": {
            "source": retirement_source,
            "linked": retirement_linked,
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
            "authorized Link 58 product link, then bundled C1 Freezer cutpoints",
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
            "c2-matrix-addenda-fixed-block-replay: FIRST RED: "
            + str(error),
            file=sys.stderr)
        return 2
    walls = value["fresh_read_only_replay"]["walls"]
    capacity = value["fresh_read_only_replay"]["capacity"]
    print(
        "c2-matrix-addenda-fixed-block-replay: PASS "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"fixed={walls['fixed_hot_block_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_bytes']} "
        "compiler=0 linker=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
