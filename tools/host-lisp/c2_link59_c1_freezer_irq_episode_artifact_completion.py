#!/usr/bin/env python3
"""Complete Link 59 from its immutable post-link artifact without relinking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link59_c1_freezer_irq_episode_successor_link as LINK  # noqa: E402


EVIDENCE = LINK.EVIDENCE
FIRST_RED = EVIDENCE / (
    "c2.2-product-link59-c1-freezer-irq-episode-"
    "wrapper-authority-first-red.json")
PARTIAL_COPY = EVIDENCE / (
    "c2.2-product-link59-c1-freezer-irq-episode-"
    "precompletion-partial-receipt.json")
PRODUCT = LINK.OUT / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
EXPECTED = {
    PRODUCT: "b46ab695a803f993e206f48f87e6ce310de1e6e56ca897bf07900502697000e6",
    ELF: "0ca5aad4540ece6304291b5fb2a4ea4251454ca821470cfa429b27f9fc5bcdae",
    MAP: "a94d333367cc3e74808641b630c68cfab6289162f82161164c958a599c9e63dd",
    LINK.RECEIPT:
        "75f2c9f47c9c7ae1b97d427065ed1c97f4db79694bc79cdc9091f82ebf92287b",
}


class CompletionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CompletionError(message)


def main() -> int:
    require(
        FIRST_RED.is_file()
        and not PARTIAL_COPY.exists()
        and not LINK.REPLAY_OUT.exists()
        and not LINK.REPLAY_RECEIPT.exists(),
        "Link-59 artifact completion is one-shot or First Red absent",
    )
    for path, digest in EXPECTED.items():
        require(
            path.is_file() and LINK.L.sha(path) == digest,
            f"immutable Link-59 input drift: {path}",
        )
    before = {path: LINK.L.sha(path) for path in (PRODUCT, ELF, MAP)}
    partial = json.loads(LINK.RECEIPT.read_text(encoding="utf-8"))
    require(
        partial["link_number"] == 59
        and partial["post_link_identity"]["status"] == "passed"
        and partial["execution_accounting"]["product_closure_links"] == 1
        and partial["fresh_prelink_gates"]["status"] == "passed"
        and partial["fresh_real_abi_gate"]["status"]
        == "passed-all-assembler-leaf-abi-contracts",
        "Link-59 partial receipt stopped before product completion",
    )
    shutil.copy2(LINK.RECEIPT, PARTIAL_COPY)
    os.chmod(PARTIAL_COPY, 0o444)

    replay = LINK.read_only_replay(PRODUCT)
    current = replay["fresh_read_only_replay"]
    walls = current["walls"]
    capacity = current["capacity"]
    specific = LINK.final_specific_gates(ELF)
    require(
        before == {path: LINK.L.sha(path) for path in (PRODUCT, ELF, MAP)}
        and walls
        == {
            "bank0_text_headroom_bytes": 37,
            "ordinary_bank0_bss_headroom_bytes": 215,
            "fixed_hot_block_headroom_bytes": 4,
            "resident_island_headroom_bytes": 5,
            "e000_headroom_bytes": 55,
        }
        and capacity["session_family_bytes"] == 65438
        and capacity["session_family_headroom_bytes"] == 98
        and replay["fixed_block"]["status"]
        == "passed-fixed-block-rtov-fail-identity-and-fixed-target"
        and replay["fixed_block"]["hot_bss"]["headroom_to_overlay_bytes"] == 4
        and replay["L_full_product_plane"]["static_plane_gate"]["status"]
        == "passed-canonical-L-full-static-plane-to-target-dataflow"
        and replay["queue_to_action_gate"]["status"]
        == "passed-queue-tuple-to-compiled-product-action"
        and replay["BADOPCODE_retirement"]["source"]["status"]
        == "passed-BADOPCODE-detail-retired-DIRMISS-preserved"
        and specific["C1_IRQ_episode"]["wrong_RTI_target_references"] == 0
        and specific["canonical_t_one_truth"]["product_vm_t_symbols"] == 0,
        "Link-59 read-only completion qualification red",
    )

    receipt: dict[str, Any] = partial
    receipt["format"] = "lisp65-c2-lite-v6-link59-C1-IRQ-episode-v1"
    receipt["status"] = (
        "passed-link59-C1-IRQ-episode-product-identity-hardware-not-run"
    )
    receipt["authority"]["link58_rollback_product"] = {
        **LINK.L.bind(LINK.BASELINE),
        "status": "untouched",
    }
    receipt["authority"]["qualified_link59_WPLTO"] = LINK.L.bind(LINK.WPLTO)
    receipt["authority"]["link59_postlink_checker_first_red"] = LINK.L.bind(
        FIRST_RED
    )
    receipt["authority"]["precompletion_partial_receipt"] = LINK.L.bind(
        PARTIAL_COPY
    )
    receipt["authority"]["link59_read_only_replay"] = LINK.L.bind(
        LINK.REPLAY_RECEIPT
    )
    receipt["C1_IRQ_episode_and_recovery"] = {
        **specific,
        "named_recovery": {
            "symbol_retired": "vm_t",
            "canonical_symbol": "lisp_t",
            "bank0_text_recovered_bytes": 12,
            "ordinary_BSS_recovered_bytes": 2,
        },
        "text_noise_reserve_required_bytes": 32,
        "C1_Freezer_cutpoints": {
            "cutpoint_1": "accepted-on-Link58",
            "cutpoint_2": "accepted-on-Link58",
            "cutpoint_3": "requires-repeat-on-Link59",
            "cutpoint_4": "not-run",
        },
    }
    receipt["fresh_read_only_replay"] = current
    receipt["product_identity"] = {
        "product": LINK.L.bind(PRODUCT),
        "elf": LINK.L.bind(ELF),
        "map": LINK.L.bind(MAP),
        "predecessor_sha256": LINK.BASELINE_SHA,
        "new_identity": True,
    }
    receipt["counters"] = {
        "line1_product_first_reds": "2/3",
        "completed_latency_measurements": "2/2-passed",
    }
    receipt["execution_accounting"] = {
        "product_closure_links": 1,
        "resident_island_seed_links": 1,
        "read_only_gate_replays": 1,
        "hardware_runs": 0,
        "latency_attempts_consumed": "2/2-passed",
    }
    receipt["claim_limit"] = (
        "One fresh product link plus complete read-only structural replay. "
        "C1 cutpoints 3/4, matrix-gate fall, promotion, acceptance, and "
        "R4/R5/R6/G5/G6 remain not-run."
    )
    receipt["next_gate"] = (
        "nonpromotable memory-driven C1 Freezer carrier on this exact Link-59 "
        "identity: repeat cutpoint 3, then cutpoint 4"
    )
    os.chmod(LINK.RECEIPT, 0o644)
    LINK.RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(LINK.RECEIPT, 0o444)
    print(
        "c2-link59-c1-freezer-artifact-completion: PASS "
        f"product={LINK.L.sha(PRODUCT)} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"bss={walls['ordinary_bank0_bss_headroom_bytes']} "
        f"fixed={walls['fixed_hot_block_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_bytes']} "
        "links=1 replay=1 hardware=0"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CompletionError,
        LINK.Link59Error,
        LINK.REPLAY.ReplayError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-link59-c1-freezer-artifact-completion: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
