#!/usr/bin/env python3
"""Build product Link 58 with the matrix addenda and fixed rtov_fail tenant."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_fixed_block_leaf_gate as FIXED  # noqa: E402
import c2_link57_keymap_nullary_successor_link as BASE  # noqa: E402


L = BASE.L
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK_NUMBER = 58
OUT = ROOT / (
    "build/c2.2/substitution/product-link-58-matrix-addenda-fixed-block")
RECEIPT = EVIDENCE / (
    "c2.2-product-link58-matrix-addenda-fixed-block-structural-receipt.json")
WPLTO = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-artifact-replay2-receipt.json")
WPLTO_SHA = (
    "bfd59267829319a48bd8f3bd26f2089137ed4b1ce7a4c655bda6537a5ebb7bb1")
WPLTO_SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-fixed-block-wplto-final2")
WPLTO_PROFILE = WPLTO_SOURCE / "resolved-profile.txt"
BASELINE = ROOT / (
    "build/c2.2/substitution/product-link-57-keymap-nullary-fast-path2/"
    "lisp65-c2-substitution-linked.prg")
BASELINE_SHA = (
    "7d568ceb7edab95a237ff3079fcf689768373a9ea48a5a43f355f6275ddc5df8")
BASELINE_RECEIPT = EVIDENCE / (
    "c2.2-product-link57-keymap-nullary-fast-path2-structural-receipt.json")
BASELINE_RECEIPT_SHA = (
    "6632a7d00ea3bfaef294924ea618e0af70e34b75da929de05b2e7c451ce26059")
LATENCY_PASS = EVIDENCE / (
    "c2.2-product-link57-keymap-nullary-latency-attempt2-"
    "hardware-presmoke.json")
MATRIX_REVIEW = EVIDENCE / (
    "c2.2-cross-invariant-full-matrix-link57-review-receipt.json")
COLD_CONTRACT = ROOT / "config/c2-matrix-addenda-cold-placement-contract.json"
KERNAL_CONTRACT = ROOT / "config/c2-kernal-unmap-contract.json"


class Link58Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise Link58Error(message)


def validate_authority() -> dict[str, Any]:
    for path, digest in {
            WPLTO: WPLTO_SHA,
            BASELINE: BASELINE_SHA,
            BASELINE_RECEIPT: BASELINE_RECEIPT_SHA,
            }.items():
        require(path.is_file() and L.sha(path) == digest,
                f"Link-58 authority SHA drift: {path}")
    qualified = json.loads(WPLTO.read_text(encoding="utf-8"))
    replay = qualified["fresh_read_only_replay"]
    baseline = json.loads(BASELINE_RECEIPT.read_text(encoding="utf-8"))
    require(
        qualified["status"] ==
            "passed-rtov-fail-fixed-block-WPLTO-all-walls-and-gates-green"
        and not qualified["promotable"]
        and qualified["execution_accounting"]["compiler_runs"] == 0
        and qualified["execution_accounting"]["linker_runs"] == 0
        and replay["walls"] == {
            "bank0_text_headroom_bytes": 35,
            "ordinary_bank0_bss_headroom_bytes": 213,
            "fixed_hot_block_headroom_bytes": 4,
            "resident_island_headroom_bytes": 5,
            "e000_headroom_bytes": 56}
        and replay["capacity"]["session_family_bytes"] == 65438
        and replay["capacity"]["session_family_headroom_bytes"] == 98
        and qualified["fixed_block"]["leaf"]["name"] == "rtov_fail"
        and qualified["fixed_block"]["leaf"]["bytes"] == 21
        and baseline["status"] ==
            "passed-keymap-and-published-nullary-product-identity-hardware-not-run"
        and baseline["product_identity"]["product"]["sha256"] == BASELINE_SHA,
        "Link-58 matrix-addenda authority is incomplete")
    BASE.BASE.BASE.profile_features()
    return qualified


def main() -> int:
    require(not OUT.exists() and not RECEIPT.exists(), "Link 58 is one-shot")
    validate_authority()
    base_names = (
        "LINK_NUMBER", "OUT", "RECEIPT", "WPLTO", "WPLTO_SHA",
        "WPLTO_SOURCE", "WPLTO_PROFILE", "BASELINE", "BASELINE_SHA",
        "BASELINE_RECEIPT", "BASELINE_RECEIPT_SHA", "validate_authority",
    )
    old_base = {name: getattr(BASE, name) for name in base_names}
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
        result = BASE.main()
    finally:
        for name, value in old_base.items():
            setattr(BASE, name, value)
    if result != 0:
        return result

    os.chmod(RECEIPT, 0o644)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    gates = receipt["fresh_replacement_gates"]
    walls = gates["walls"]
    capacity = gates["capacity"]
    fixed_path = OUT / "fixed-block-rtov-fail-link58.json"
    fixed = FIXED.audit_elf(elf, out=fixed_path)
    require(
        receipt["link_number"] == LINK_NUMBER
        and L.sha(product) != BASELINE_SHA
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["ordinary_bank0_bss_headroom_bytes"] == 213
        and walls["fixed_hot_block_headroom_bytes"] == 4
        and walls["resident_island_headroom_bytes"] == 5
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_family_bytes"] == 65438
        and capacity["session_family_headroom_bytes"] == 98
        and fixed["status"] ==
            "passed-fixed-block-rtov-fail-identity-and-fixed-target"
        and fixed["hot_bss"]["headroom_to_overlay_bytes"] == 4
        and [row["target"] for row in
             fixed["leaf"]["outgoing_control_edges"]] == ["rtov_wipe"],
        "Link-58 final fixed-block qualification red")

    receipt["format"] = "lisp65-c2-lite-v6-link58-matrix-addenda-v1"
    receipt["status"] = (
        "passed-link58-matrix-addenda-product-identity-hardware-not-run")
    receipt["authority"]["link57_rollback_product"] = {
        **L.bind(BASELINE), "status": "untouched"}
    receipt["authority"]["qualified_matrix_addenda_WPLTO"] = L.bind(WPLTO)
    receipt["authority"]["matrix_disposition_review"] = L.bind(MATRIX_REVIEW)
    receipt["authority"]["cold_placement_contract"] = L.bind(COLD_CONTRACT)
    receipt["authority"]["kernal_window_contract"] = L.bind(KERNAL_CONTRACT)
    receipt["authority"]["latency_attempt_2_pass"] = L.bind(LATENCY_PASS)
    receipt["matrix_addenda_and_fixed_block"] = {
        "fixed_block_gate": {**fixed, "receipt": L.bind(fixed_path)},
        "text_noise_reserve_required_bytes": 32,
        "E000_floor_required_bytes": 54,
        "session_limit_bytes": 65536,
        "C1_Freezer_cutpoints": "hardware-not-run",
    }
    receipt["product_identity"] = {
        "product": L.bind(product),
        "elf": L.bind(elf),
        "map": L.bind(Path(str(product) + ".map")),
        "predecessor_sha256": BASELINE_SHA,
        "new_identity": True,
    }
    receipt["counters"] = {
        "line1_product_first_reds": "2/3",
        "completed_latency_measurements": "2/2-passed",
    }
    receipt["execution_accounting"]["latency_attempts_consumed"] = "2/2"
    receipt["next_gate"] = (
        "bundled C1 Freezer cutpoints on this exact product identity; "
        "hardware promotion and acceptance are not claimed")
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-link58-matrix-addenda: COMPLETE "
        f"product={L.sha(product)} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"fixed={walls['fixed_hot_block_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_bytes']} "
        "hardware=not-run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        Link58Error,
        BASE.Link57Error,
        FIXED.GateError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-link58-matrix-addenda: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
