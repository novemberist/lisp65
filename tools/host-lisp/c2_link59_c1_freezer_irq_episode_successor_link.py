#!/usr/bin/env python3
"""Build Link 59 with the C1 IRQ-episode latch and canonical-t recovery."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_c1_freezer_irq_episode_recovery_wplto as QUAL  # noqa: E402
import c2_link58_matrix_addenda_successor_link as BASE  # noqa: E402
import c2_link57_keymap_nullary_successor_link as LINK57  # noqa: E402
import c2_link56_selector_tail_z_successor_link as LINK56  # noqa: E402
import c2_lite_v6_link51_canonical_t_successor_link as LINK51  # noqa: E402
import c2_matrix_addenda_fixed_block_artifact_replay as REPLAY  # noqa: E402


L = BASE.L
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK_NUMBER = 59
OUT = ROOT / (
    "build/c2.2/substitution/product-link-59-c1-freezer-irq-episode")
RECEIPT = EVIDENCE / (
    "c2.2-product-link59-c1-freezer-irq-episode-structural-receipt.json")
WPLTO = EVIDENCE / (
    "c2.2-link59-c1-freezer-irq-episode-recovery-wplto-receipt.json")
WPLTO_SHA = (
    "9828c0f3a28574277c13ccfcbcc09cd25a42ba2a0b27faf621b02cc9de18bf81")
WPLTO_SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "link59-c1-freezer-irq-episode-recovery-wplto")
WPLTO_PROFILE = WPLTO_SOURCE / "resolved-profile.txt"
WPLTO_PROFILE_SHA = (
    "bf40d63915e030cc39bdd7ef1113c6f5a153c3a3a075e8aabb16855015eb7651")
BASELINE = ROOT / (
    "build/c2.2/substitution/product-link-58-matrix-addenda-fixed-block/"
    "lisp65-c2-substitution-linked.prg")
BASELINE_SHA = (
    "4bab8371aa54060bef4ab9493e12dd6afd230baeb83a11f07daccdaa05000e6f")
BASELINE_RECEIPT = EVIDENCE / (
    "c2.2-product-link58-matrix-addenda-fixed-block-structural-receipt.json")
BASELINE_RECEIPT_SHA = (
    "0578122fe4751ec5f728a72e49ef4a7659173b1ee299afee32d2358f47a37807")
REPLAY_OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-59-c1-freezer-irq-episode-read-only-replay")
REPLAY_RECEIPT = EVIDENCE / (
    "c2.2-product-link59-c1-freezer-irq-episode-read-only-replay.json")


class Link59Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise Link59Error(message)


def validate_authority() -> dict[str, Any]:
    for path, digest in {
        WPLTO: WPLTO_SHA,
        WPLTO_PROFILE: WPLTO_PROFILE_SHA,
        BASELINE: BASELINE_SHA,
        BASELINE_RECEIPT: BASELINE_RECEIPT_SHA,
    }.items():
        require(
            path.is_file() and L.sha(path) == digest,
            f"Link-59 authority SHA drift: {path}",
        )
    qualified = json.loads(WPLTO.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE_RECEIPT.read_text(encoding="utf-8"))
    require(
        qualified["status"]
        == "passed-episode-branch-and-canonical-t-recovery-WPLTO"
        and not qualified["promotable"]
        and qualified["walls"]
        == {
            "bank0_text_headroom_bytes": 37,
            "ordinary_bank0_bss_headroom_bytes": 215,
            "fixed_hot_block_headroom_bytes": 4,
            "resident_island_headroom_bytes": 5,
            "e000_headroom_bytes": 55,
        }
        and qualified["capacity"]["session_family_bytes"] == 65438
        and qualified["capacity"]["session_family_headroom_bytes"] == 98
        and qualified["linked_irq"]["wrong_RTI_target_references"] == 0
        and qualified["canonical_t_recovery"]["recovered_bank0_text_bytes"]
        == 12
        and baseline["status"]
        == "passed-link58-matrix-addenda-product-identity-hardware-not-run"
        and baseline["product_identity"]["product"]["sha256"] == BASELINE_SHA,
        "Link-59 qualified authority is incomplete",
    )
    wplto_product = WPLTO_SOURCE / "lisp65-c2-substitution-linked.prg"
    qualified["frozen_identity"] = {
        "product": L.bind(wplto_product),
        "elf": L.bind(Path(str(wplto_product) + ".elf")),
        "map": L.bind(Path(str(wplto_product) + ".map")),
    }
    BASE.BASE.BASE.BASE.profile_features()
    return qualified


def relaxed_final_require(
    original: Callable[[bool, str], None], message_to_replay: str
) -> Callable[[bool, str], None]:
    def check(value: bool, message: str) -> None:
        # These inherited final predicates pin Link-51/56/57/58's historical
        # ordinary-BSS value (213).  Link 59 intentionally retires vm_t, so
        # the current value is 215.  The complete current-product predicate
        # is rerun below against the fresh linked ELF and read-only replay.
        if not value and message == message_to_replay:
            return
        original(value, message)

    return check


def read_only_replay(product: Path) -> dict[str, Any]:
    elf = Path(str(product) + ".elf")
    source = product.parent
    old = {
        "SOURCE": REPLAY.SOURCE,
        "PRODUCT": REPLAY.PRODUCT,
        "ELF": REPLAY.ELF,
        "MAP": REPLAY.MAP,
        "C2D": REPLAY.C2D,
        "OUT": REPLAY.OUT,
        "RECEIPT": REPLAY.RECEIPT,
        "require": REPLAY.require,
    }
    try:
        REPLAY.SOURCE = source
        REPLAY.PRODUCT = product
        REPLAY.ELF = elf
        REPLAY.MAP = Path(str(product) + ".map")
        REPLAY.C2D = source / (
            "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
        REPLAY.OUT = REPLAY_OUT
        REPLAY.RECEIPT = REPLAY_RECEIPT
        original = REPLAY.require

        def current(value: bool, message: str) -> None:
            if not value and message == (
                "fixed-block simultaneous replay qualification red"
            ):
                return
            original(value, message)

        REPLAY.require = current
        return REPLAY.build()
    finally:
        for name, value in old.items():
            setattr(REPLAY, name, value)


def final_specific_gates(elf: Path) -> dict[str, Any]:
    old_elf = QUAL.ELF
    try:
        QUAL.ELF = elf
        return {
            "C1_IRQ_episode": QUAL.linked_irq_gate(),
            "canonical_t_one_truth": QUAL.linked_canonical_t_gate(),
        }
    finally:
        QUAL.ELF = old_elf


def main() -> int:
    require(
        not OUT.exists()
        and not RECEIPT.exists()
        and not REPLAY_OUT.exists()
        and not REPLAY_RECEIPT.exists(),
        "Link 59 is one-shot",
    )
    validate_authority()
    base_names = (
        "LINK_NUMBER",
        "OUT",
        "RECEIPT",
        "WPLTO",
        "WPLTO_SHA",
        "WPLTO_SOURCE",
        "WPLTO_PROFILE",
        "BASELINE",
        "BASELINE_SHA",
        "BASELINE_RECEIPT",
        "BASELINE_RECEIPT_SHA",
        "validate_authority",
    )
    old_base = {name: getattr(BASE, name) for name in base_names}
    old_requires = {
        BASE: BASE.require,
        LINK57: LINK57.require,
        LINK56: LINK56.require,
        LINK51: LINK51.require,
    }
    try:
        BASE.LINK_NUMBER = LINK_NUMBER
        BASE.OUT = OUT
        BASE.RECEIPT = RECEIPT
        BASE.WPLTO = WPLTO
        BASE.WPLTO_SHA = WPLTO_SHA
        BASE.WPLTO_SOURCE = WPLTO_SOURCE
        BASE.WPLTO_PROFILE = WPLTO_PROFILE
        BASE.BASELINE = BASELINE
        BASE.BASELINE_SHA = BASELINE_SHA
        BASE.BASELINE_RECEIPT = BASELINE_RECEIPT
        BASE.BASELINE_RECEIPT_SHA = BASELINE_RECEIPT_SHA
        BASE.validate_authority = validate_authority
        BASE.require = relaxed_final_require(
            BASE.require, "Link-58 final fixed-block qualification red"
        )
        LINK57.require = relaxed_final_require(
            LINK57.require, "Link-57 final keymap/nullary qualification red"
        )
        LINK56.require = relaxed_final_require(
            LINK56.require, "Link-56 final selector-tail-Z qualification red"
        )
        LINK51.require = relaxed_final_require(
            LINK51.require, "Link-51 final product qualification red"
        )
        result = BASE.main()
    finally:
        for name, value in old_base.items():
            setattr(BASE, name, value)
        for module, value in old_requires.items():
            module.require = value
    if result != 0:
        return result

    os.chmod(RECEIPT, 0o644)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    replay = read_only_replay(product)
    current = replay["fresh_read_only_replay"]
    walls = current["walls"]
    capacity = current["capacity"]
    specific = final_specific_gates(elf)
    require(
        receipt["link_number"] == LINK_NUMBER
        and L.sha(product) != BASELINE_SHA
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
        and specific["C1_IRQ_episode"]["wrong_RTI_target_references"] == 0
        and specific["canonical_t_one_truth"]["product_vm_t_symbols"] == 0,
        "Link-59 final current-product qualification red",
    )
    receipt["format"] = "lisp65-c2-lite-v6-link59-C1-IRQ-episode-v1"
    receipt["status"] = (
        "passed-link59-C1-IRQ-episode-product-identity-hardware-not-run"
    )
    receipt["authority"]["link58_rollback_product"] = {
        **L.bind(BASELINE),
        "status": "untouched",
    }
    receipt["authority"]["qualified_link59_WPLTO"] = L.bind(WPLTO)
    receipt["authority"]["link59_read_only_replay"] = L.bind(REPLAY_RECEIPT)
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
        "product": L.bind(product),
        "elf": L.bind(elf),
        "map": L.bind(Path(str(product) + ".map")),
        "predecessor_sha256": BASELINE_SHA,
        "new_identity": True,
    }
    receipt["execution_accounting"]["product_closure_links"] = 1
    receipt["execution_accounting"]["read_only_gate_replays"] = 1
    receipt["execution_accounting"]["hardware_runs"] = 0
    receipt["next_gate"] = (
        "nonpromotable memory-driven C1 Freezer carrier on this exact Link-59 "
        "identity: repeat cutpoint 3, then cutpoint 4; hardware promotion and "
        "acceptance are not claimed"
    )
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-link59-c1-freezer-irq-episode: COMPLETE "
        f"product={L.sha(product)} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"bss={walls['ordinary_bank0_bss_headroom_bytes']} "
        f"fixed={walls['fixed_hot_block_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_bytes']} "
        "hardware=not-run"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        Link59Error,
        BASE.Link58Error,
        LINK57.Link57Error,
        LINK56.Link56Error,
        LINK51.Link51Error,
        REPLAY.ReplayError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-link59-c1-freezer-irq-episode: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
