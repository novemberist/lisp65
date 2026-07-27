#!/usr/bin/env python3
"""Complete Link 58's receipt from its already frozen product artifacts."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_fixed_block_leaf_gate as FIXED  # noqa: E402
import c2_link58_matrix_addenda_successor_link as LINK  # noqa: E402


OUT = LINK.OUT
RECEIPT = LINK.RECEIPT
PRODUCT = OUT / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
FIXED_RECEIPT = OUT / "fixed-block-rtov-fail-final.json"
PRE_COMPLETION_RECEIPT_SHA = (
    "afd03c191ca9320512c1f23ae8e8f5fde95e55cc72403bd9dd881c02db18f6ab")
PRODUCT_SHA = (
    "4bab8371aa54060bef4ab9493e12dd6afd230baeb83a11f07daccdaa05000e6f")


class CompletionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CompletionError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"completion input absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def main() -> int:
    require(
        RECEIPT.is_file()
        and sha(RECEIPT) == PRE_COMPLETION_RECEIPT_SHA
        and sha(PRODUCT) == PRODUCT_SHA,
        "Link-58 completion identity drift")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    fixed_file = json.loads(FIXED_RECEIPT.read_text(encoding="utf-8"))
    fixed = FIXED.audit_elf(ELF)
    gates = receipt["fresh_replacement_gates"]
    walls = gates["walls"]
    capacity = gates["capacity"]
    require(
        receipt["status"] ==
            "passed-keymap-and-published-nullary-product-identity-hardware-not-run"
        and receipt["link_number"] == 58
        and receipt["execution_accounting"]["product_closure_links"] == 1
        and receipt["execution_accounting"]["hardware_runs"] == 0
        and receipt["product_identity"]["product"]["sha256"] == PRODUCT_SHA
        and receipt["product_identity"]["predecessor_sha256"] ==
            LINK.BASELINE_SHA
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["ordinary_bank0_bss_headroom_bytes"] == 213
        and walls["fixed_hot_block_headroom_bytes"] == 4
        and walls["resident_island_headroom_bytes"] == 5
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_family_bytes"] == 65438
        and capacity["session_family_headroom_bytes"] == 98
        and fixed_file == fixed
        and fixed["status"] ==
            "passed-fixed-block-rtov-fail-identity-and-fixed-target"
        and fixed["hot_bss"]["headroom_to_overlay_bytes"] == 4
        and [row["target"] for row in
             fixed["leaf"]["outgoing_control_edges"]] == ["rtov_wipe"],
        "Link-58 artifact completion qualification red")

    receipt["format"] = "lisp65-c2-lite-v6-link58-matrix-addenda-v1"
    receipt["status"] = (
        "passed-link58-matrix-addenda-product-identity-hardware-not-run")
    receipt["authority"]["link57_rollback_product"] = {
        **LINK.L.bind(LINK.BASELINE), "status": "untouched"}
    receipt["authority"]["qualified_matrix_addenda_WPLTO"] = (
        LINK.L.bind(LINK.WPLTO))
    receipt["authority"]["matrix_disposition_review"] = (
        LINK.L.bind(LINK.MATRIX_REVIEW))
    receipt["authority"]["cold_placement_contract"] = (
        LINK.L.bind(LINK.COLD_CONTRACT))
    receipt["authority"]["kernal_window_contract"] = (
        LINK.L.bind(LINK.KERNAL_CONTRACT))
    receipt["authority"]["latency_attempt_2_pass"] = (
        LINK.L.bind(LINK.LATENCY_PASS))
    receipt["authority"]["artifact_completion_driver"] = bind(Path(__file__))
    receipt["matrix_addenda_and_fixed_block"] = {
        "fixed_block_gate": {
            **fixed, "receipt": LINK.L.bind(FIXED_RECEIPT)},
        "text_noise_reserve_required_bytes": 32,
        "E000_floor_required_bytes": 54,
        "session_limit_bytes": 65536,
        "C1_Freezer_cutpoints": "hardware-not-run",
    }
    receipt["product_identity"] = {
        "product": LINK.L.bind(PRODUCT),
        "elf": LINK.L.bind(ELF),
        "map": LINK.L.bind(MAP),
        "predecessor_sha256": LINK.BASELINE_SHA,
        "new_identity": True,
    }
    receipt["class_A_Link58_receipt_completion"] = {
        "pre_completion_receipt_sha256": PRE_COMPLETION_RECEIPT_SHA,
        "cause":
            "the product link had already emitted and frozen the fixed-block "
            "gate at the requested path; the wrapper attempted to emit that "
            "same read-only gate a second time",
        "correction":
            "consume the existing SHA-bound gate and replay its structured "
            "ELF audit without an output path",
        "product_bytes_changed": 0,
        "compiler_runs": 0,
        "linker_runs": 0,
        "hardware_runs": 0,
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
        "c2-link58-matrix-addenda-artifact-completion: PASS "
        f"product={PRODUCT_SHA} text={walls['bank0_text_headroom_bytes']} "
        f"fixed={walls['fixed_hot_block_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        "compiler=0 linker=0 hardware=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CompletionError, FIXED.GateError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-link58-matrix-addenda-artifact-completion: FIRST RED: "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
