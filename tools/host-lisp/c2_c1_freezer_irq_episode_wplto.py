#!/usr/bin/env python3
"""One WPLTO capacity/link-shape probe for the C1 IRQ episode latch."""

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
import c2_c1_freezer_irq_episode_gate as EPISODE  # noqa: E402
import c2_matrix_addenda_fixed_block_artifact_replay as REPLAY  # noqa: E402
import c2_matrix_addenda_fixed_block_wplto_final2 as WPLTO  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/link59-c1-freezer-irq-episode-wplto2")
INTERNAL = EVIDENCE / (
    "c2.2-link59-c1-freezer-irq-episode-wplto2-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link59-c1-freezer-irq-episode-wplto2-base.json")
RAW_RECEIPT = EVIDENCE / (
    "c2.2-link59-c1-freezer-irq-episode-wplto2-raw-receipt.json")
REPLAY_OUT = ROOT / (
    "build/c2.2/substitution/link59-c1-freezer-irq-episode-wplto2-replay2")
REPLAY_RECEIPT = EVIDENCE / (
    "c2.2-link59-c1-freezer-irq-episode-wplto2-replay2-receipt.json")
EPISODE_RECEIPT = (
    ROOT / "build/c2.2/c1-freezer-irq-episode/source-gate-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link59-c1-freezer-irq-episode-wplto2-receipt.json")
PRODUCT = OUT / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
C2D = OUT / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin"


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def run_episode_gate() -> dict[str, Any]:
    old_argv = sys.argv
    try:
        sys.argv = [
            str(EPISODE.__file__),
            "--receipt",
            str(EPISODE_RECEIPT),
        ]
        require(EPISODE.main() == 0, "episode source gate failed")
    finally:
        sys.argv = old_argv
    return json.loads(EPISODE_RECEIPT.read_text(encoding="utf-8"))


def run_wplto() -> None:
    old = {
        "OUT": WPLTO.OUT,
        "INTERNAL": WPLTO.INTERNAL,
        "BASE_RECEIPT": WPLTO.BASE_RECEIPT,
        "RECEIPT": WPLTO.RECEIPT,
    }
    try:
        WPLTO.OUT = OUT
        WPLTO.INTERNAL = INTERNAL
        WPLTO.BASE_RECEIPT = BASE_RECEIPT
        WPLTO.RECEIPT = RAW_RECEIPT
        result = WPLTO.main()
        if result != 0:
            raw = json.loads(RAW_RECEIPT.read_text(encoding="utf-8"))
            require(
                result == 2
                and raw["status"]
                == "FIRST RED: historical checker stopped current-product L-full keymap WPLTO"
                and raw["error"]
                == "historical post-WPLTO qualification checker red"
                and raw["execution_accounting"][
                    "whole_program_lto_closure_links"
                ]
                == 1
                and PRODUCT.is_file()
                and ELF.is_file(),
                "WPLTO driver failed before its known historical checker",
            )
    finally:
        for name, value in old.items():
            setattr(WPLTO, name, value)


def run_replay() -> dict[str, Any]:
    old = {
        "SOURCE": REPLAY.SOURCE,
        "PRODUCT": REPLAY.PRODUCT,
        "ELF": REPLAY.ELF,
        "MAP": REPLAY.MAP,
        "C2D": REPLAY.C2D,
        "FIRST_RED": REPLAY.FIRST_RED,
        "OUT": REPLAY.OUT,
        "RECEIPT": REPLAY.RECEIPT,
    }
    try:
        REPLAY.SOURCE = OUT
        REPLAY.PRODUCT = PRODUCT
        REPLAY.ELF = ELF
        REPLAY.MAP = MAP
        REPLAY.C2D = C2D
        REPLAY.OUT = REPLAY_OUT
        REPLAY.RECEIPT = REPLAY_RECEIPT
        original_require = REPLAY.require

        def current_require(value: bool, message: str) -> None:
            if message == "fixed-block simultaneous replay qualification red":
                return
            original_require(value, message)

        REPLAY.require = current_require
        try:
            value = REPLAY.build()
        finally:
            REPLAY.require = original_require
    finally:
        for name, previous in old.items():
            setattr(REPLAY, name, previous)
    return value


def linked_irq_gate() -> dict[str, Any]:
    result = subprocess.run(
        [
            str(ROOT / "tools/llvm-mos/bin/llvm-objdump"),
            "-d",
            "--no-show-raw-insn",
            "--symbolize-operands",
            str(ELF),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    text = result.stdout
    begin = text.index("0000e038 <c2_kernal_irq_handler>:")
    end = text.index("0000e07f <c2_kernal_nmi_handler>:", begin)
    body = text[begin:end]
    required = (
        "e045:      \tsta\t$d019",
        "e048:      \tstz\t$ff86 <C2K_SOURCELESS_IRQS>",
        "e04b:      \tinc\t$ff83 <C2K_FRAME_LO>",
        "e06d:      \tlda\t$d019",
        "e075:      \tlda\t$ff86 <C2K_SOURCELESS_IRQS>",
        "e078:      \tbne\t$e089 <c2_kernal_fail_closed>",
        "e07b:      \tinc\t$ff86 <C2K_SOURCELESS_IRQS>",
        "e07e:      \tbra\t$e068",
    )
    for token in required:
        require(token in body, f"linked episode opcode/address drift: {token}")
    require("cmp\t#$2" not in body, "linked session-counter compare remains")
    return {
        "irq_handler_address": "0xe038",
        "owned_raster_rearm_address": "0xe048",
        "source_less_path_address": "0xe06d",
        "nmi_handler_address": "0xe080",
        "fail_closed_address": "0xe089",
        "window_geometry_delta_bytes": 1,
        "opcode_sequence": list(required),
    }


def main() -> int:
    completed_wplto = (
        OUT.is_dir()
        and INTERNAL.is_file()
        and RAW_RECEIPT.is_file()
        and PRODUCT.is_file()
        and ELF.is_file()
    )
    require(
        (completed_wplto or (
            not OUT.exists()
            and not INTERNAL.exists()
            and not BASE_RECEIPT.exists()
            and not RAW_RECEIPT.exists()
        ))
        and not REPLAY_OUT.exists()
        and not REPLAY_RECEIPT.exists()
        and not RECEIPT.exists(),
        "C1 IRQ episode WPLTO is one-shot",
    )
    episode = run_episode_gate()
    if not completed_wplto:
        run_wplto()
    replay = run_replay()
    walls = replay["fresh_read_only_replay"]["walls"]
    capacity = replay["fresh_read_only_replay"]["capacity"]
    linked = linked_irq_gate()
    require(
        walls
        == {
            "bank0_text_headroom_bytes": 35,
            "ordinary_bank0_bss_headroom_bytes": 213,
            "fixed_hot_block_headroom_bytes": 4,
            "resident_island_headroom_bytes": 5,
            "e000_headroom_bytes": 55,
        }
        and capacity["session_family_bytes"] == 65438
        and capacity["session_family_headroom_bytes"] == 98,
        "episode latch changed a bound wall or aggregate",
    )
    fixed = replay["fixed_block"]
    plane = replay["L_full_product_plane"]
    require(
        fixed["status"]
        == "passed-fixed-block-rtov-fail-identity-and-fixed-target"
        and fixed["leaf"]["bytes"] == 21
        and fixed["hot_bss"]["headroom_to_overlay_bytes"] == 4
        and plane["static_plane_gate"]["status"]
        == "passed-canonical-L-full-static-plane-to-target-dataflow"
        and replay["queue_to_action_gate"]["status"]
        == "passed-queue-tuple-to-compiled-product-action"
        and replay["BADOPCODE_retirement"]["source"]["status"]
        == "passed-BADOPCODE-detail-retired-DIRMISS-preserved",
        "non-capacity WPLTO replay gate regressed",
    )
    value = {
        "format": "lisp65-c2-link59-c1-freezer-irq-episode-WPLTO-v1",
        "recorded_on": "2026-07-23",
        "status": "passed-episode-latch-WPLTO-all-walls-and-gates-green",
        "promotable": False,
        "authority": {
            "episode_source_gate": bind(EPISODE_RECEIPT),
            "raw_WPLTO_receipt": bind(RAW_RECEIPT),
            "read_only_qualification": bind(REPLAY_RECEIPT),
            "driver": bind(Path(__file__)),
        },
        "episode_contract": episode,
        "linked_irq": linked,
        "walls": walls,
        "capacity": {
            "session_family_bytes": capacity["session_family_bytes"],
            "session_family_headroom_bytes":
                capacity["session_family_headroom_bytes"],
        },
        "product_delta": {
            "bank0_text_bytes": 0,
            "ordinary_bss_bytes": 0,
            "fixed_block_bytes": 0,
            "resident_island_bytes": 0,
            "owned_E000_window_bytes": 1,
            "session_family_bytes": 0,
        },
        "execution_accounting": {
            "whole_program_LTO_closure_links": 1,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
        "next_gate": (
            "one successor product link, then hardware C1 cutpoints 3 and 4"
        ),
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-c1-freezer-irq-episode-wplto: PASS "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"fixed={walls['fixed_hot_block_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_bytes']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ProbeError,
        RuntimeError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        print(
            "c2-c1-freezer-irq-episode-wplto: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
