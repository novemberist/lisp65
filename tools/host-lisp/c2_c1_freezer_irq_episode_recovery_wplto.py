#!/usr/bin/env python3
"""Fresh WPLTO for the fixed IRQ episode branch and canonical-t recovery."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_c1_freezer_irq_episode_wplto as BASE  # noqa: E402
import c2_vm_badopcode_detail_gate as RETIRE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link59-c1-freezer-irq-episode-recovery-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-link59-c1-freezer-irq-episode-recovery-wplto-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link59-c1-freezer-irq-episode-recovery-wplto-base.json")
RAW_RECEIPT = EVIDENCE / (
    "c2.2-link59-c1-freezer-irq-episode-recovery-wplto-raw-receipt.json")
REPLAY_OUT = ROOT / (
    "build/c2.2/substitution/"
    "link59-c1-freezer-irq-episode-recovery-wplto-replay3")
REPLAY_RECEIPT = EVIDENCE / (
    "c2.2-link59-c1-freezer-irq-episode-recovery-wplto-replay3-receipt.json")
EPISODE_RECEIPT = (
    ROOT
    / "build/c2.2/c1-freezer-irq-episode/recovery-source-gate-receipt.json"
)
RECEIPT = EVIDENCE / (
    "c2.2-link59-c1-freezer-irq-episode-recovery-wplto-receipt.json")
PRODUCT = OUT / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
C2D = OUT / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin"
FIRST_RED = EVIDENCE / (
    "c2.2-link59-c1-freezer-irq-episode-wplto-first-red.json")


def configure_base() -> None:
    BASE.OUT = OUT
    BASE.INTERNAL = INTERNAL
    BASE.BASE_RECEIPT = BASE_RECEIPT
    BASE.RAW_RECEIPT = RAW_RECEIPT
    BASE.REPLAY_OUT = REPLAY_OUT
    BASE.REPLAY_RECEIPT = REPLAY_RECEIPT
    BASE.EPISODE_RECEIPT = EPISODE_RECEIPT
    BASE.RECEIPT = RECEIPT
    BASE.PRODUCT = PRODUCT
    BASE.ELF = ELF
    BASE.MAP = MAP
    BASE.C2D = C2D


def linked_irq_gate() -> dict[str, object]:
    result = subprocess.run(
        [
            str(ROOT / "tools/llvm-mos/bin/llvm-objdump"),
            "-d",
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
    end = text.index("0000e080 <c2_kernal_nmi_handler>:", begin)
    body = text[begin:end]
    required = (
        "e03f: 29 01",
        "e041: f0 28",
        "e043: 8d 19 d0",
        "e046: 9c 86 ff",
        "e06b: ad 19 d0",
        "e073: ad 86 ff",
        "e076: f0 03",
        "e078: 4c 89 e0",
        "e07b: ee 86 ff",
        "e07e: 80 e6",
    )
    for token in required:
        BASE.require(token in body, f"linked IRQ opcode drift: {token}")
    BASE.require(
        "d3 0e 00" not in body
        and "bne\t$e088" not in body
        and "0000e089 <c2_kernal_fail_closed>:" in text,
        "section-crossing conditional branch or wrong fail target survived",
    )
    return {
        "irq_handler": "0xe038",
        "owned_raster_ack": "A from AND #$01; no redundant reload",
        "episode_rearm": "STZ $FF86 at 0xe046",
        "source_less_path": "0xe06b",
        "local_condition": "BEQ 0xe07b at 0xe076",
        "absolute_fail_closed_jump": "JMP 0xe089 at 0xe078",
        "nmi_handler": "0xe080",
        "fail_closed": "0xe089",
        "wrong_RTI_target_references": 0,
    }


def linked_canonical_t_gate() -> dict[str, object]:
    source = RETIRE.source_gate(mutations=True)
    linked = RETIRE.linked_gate(
        ELF, ROOT / "tools/llvm-mos/bin/llvm-readobj")
    symbols = subprocess.run(
        [str(ROOT / "tools/llvm-mos/bin/llvm-nm"), "-S", str(ELF)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    BASE.require(
        " vm_t\n" not in symbols
        and linked["canonical_t"]["bytes"] == 2
        and linked["canonical_t"]["private_facade_intern_relocations"] == 0
        and len(source["mutations_rejected"]) == 13,
        "canonical-t VM cache consolidation is not linked one-truth",
    )
    return {
        "source": source["canonical_t"],
        "source_mutations_rejected": sorted(source["mutations_rejected"]),
        "linked": linked["canonical_t"],
        "product_vm_t_symbols": 0,
        "non_C2_profiles": "private vm_t bootstrap retained",
    }


def main() -> int:
    configure_base()
    completed_wplto = (
        OUT.is_dir()
        and INTERNAL.is_file()
        and RAW_RECEIPT.is_file()
        and PRODUCT.is_file()
        and ELF.is_file()
    )
    BASE.require(
        FIRST_RED.is_file()
        and (completed_wplto or (
            not OUT.exists()
            and not INTERNAL.exists()
            and not BASE_RECEIPT.exists()
            and not RAW_RECEIPT.exists()
        ))
        and not REPLAY_OUT.exists()
        and not REPLAY_RECEIPT.exists()
        and not RECEIPT.exists(),
        "recovery WPLTO is one-shot or First Red authority absent",
    )
    episode = BASE.run_episode_gate()
    if not completed_wplto:
        BASE.run_wplto()
    replay = BASE.run_replay()
    walls = replay["fresh_read_only_replay"]["walls"]
    capacity = replay["fresh_read_only_replay"]["capacity"]
    irq = linked_irq_gate()
    canonical = linked_canonical_t_gate()
    BASE.require(
        walls["bank0_text_headroom_bytes"] >= 32
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 213
        and walls["fixed_hot_block_headroom_bytes"] == 4
        and walls["resident_island_headroom_bytes"] == 5
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_family_bytes"] == 65438
        and capacity["session_family_headroom_bytes"] == 98,
        "recovery WPLTO did not close every wall",
    )
    value = {
        "format": "lisp65-c2-link59-c1-freezer-irq-episode-recovery-WPLTO-v1",
        "recorded_on": "2026-07-23",
        "status": "passed-episode-branch-and-canonical-t-recovery-WPLTO",
        "promotable": False,
        "authority": {
            "first_red": BASE.bind(FIRST_RED),
            "episode_source_gate": BASE.bind(EPISODE_RECEIPT),
            "canonical_t_contract": BASE.bind(RETIRE.CONTRACT),
            "raw_WPLTO": BASE.bind(RAW_RECEIPT),
            "read_only_replay": BASE.bind(REPLAY_RECEIPT),
            "driver": BASE.bind(Path(__file__)),
        },
        "episode_contract": episode,
        "linked_irq": irq,
        "canonical_t_recovery": {
            "name": "retire product-private vm_t identity derivation",
            "reason": (
                "vm_init and eval_init derived the same interned t twice; "
                "the C2 product now publishes vm_init's result directly as "
                "the existing canonical lisp_t object"
            ),
            "linked_gate": canonical,
            "before_bank0_text_headroom_bytes": 25,
            "after_bank0_text_headroom_bytes":
                walls["bank0_text_headroom_bytes"],
            "recovered_bank0_text_bytes":
                walls["bank0_text_headroom_bytes"] - 25,
            "private_BSS_cells_retired_bytes":
                walls["ordinary_bank0_bss_headroom_bytes"] - 213,
        },
        "walls": walls,
        "capacity": {
            "session_family_bytes": capacity["session_family_bytes"],
            "session_family_headroom_bytes":
                capacity["session_family_headroom_bytes"],
        },
        "execution_accounting": {
            "whole_program_LTO_closure_links": 1,
            "read_only_gate_replays": 1,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
        "next_gate": "owner-authorized Link 59 product link",
        "claim_limit": "No product link, hardware C1 closure or matrix-gate claim.",
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-c1-freezer-irq-episode-recovery-wplto: PASS "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"bss={walls['ordinary_bank0_bss_headroom_bytes']} "
        f"fixed={walls['fixed_hot_block_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_bytes']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BASE.ProbeError,
        RuntimeError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        print(
            "c2-c1-freezer-irq-episode-recovery-wplto: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
