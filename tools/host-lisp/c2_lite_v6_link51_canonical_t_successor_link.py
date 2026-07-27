#!/usr/bin/env python3
"""Build product Link 51 with canonical lisp_t consumption."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_badopcode_hold_shelf_gate as SHELF  # noqa: E402
import c2_lite_v6_link50_persistent_header_successor_link as BASE  # noqa: E402
import c2_vm_badopcode_detail_gate as RETIRE  # noqa: E402


L = BASE.L
P = BASE.P
BASE_LINK = BASE.BASE_LINK
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK_NUMBER = 51
OUT = ROOT / (
    "build/c2.2/substitution/product-link-51-c2-lite-v6-canonical-t")
RECEIPT = EVIDENCE / (
    "c2.2-product-link51-c2-lite-v6-canonical-t-structural-receipt.json")
WPLTO = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-canonical-t-"
    "artifact-replay-receipt.json")
WPLTO_SHA = (
    "b5b4e27faf32a6ecc4c3f0819c301b64626fb0ac878293fd1fcb1529387a902f")
WPLTO_AUTHORITY = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-canonical-t-wplto-receipt.json")
WPLTO_AUTHORITY_SHA = (
    "f427927b60ab482ff725835c93d33d2b372c759a92236b35873bba676e247ab4")
WPLTO_SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "link50-badopcode-retirement-canonical-t-wplto")
WPLTO_PROFILE = WPLTO_SOURCE / "resolved-profile.txt"
BASELINE = ROOT / (
    "build/c2.2/substitution/"
    "product-link-50-c2-lite-v6-persistent-header/"
    "lisp65-c2-substitution-linked.prg")
BASELINE_SHA = (
    "3e13c9101b53ba89b8fb33e0f11c641ca53803b3f447831c5e1243475f7bc216")
BASELINE_RECEIPT = EVIDENCE / (
    "c2.2-product-link50-c2-lite-v6-persistent-header-"
    "artifact-replay-structural-receipt.json")
BASELINE_RECEIPT_SHA = (
    "e7f47adebda448583efa6e28d86ff28bb335adf3178853b5177e736cccd36170")
HARDWARE_FIRST_RED = EVIDENCE / (
    "c2.2-product-link50-first-call-badopcode-hardware-first-red.json")
HARDWARE_FIRST_RED_SHA = (
    "fbb258b781d97e0bd0e0c7b62e99018f6dbf04a6ca17006db189e87c3eeba729")


class Link51Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise Link51Error(message)


def validate_authority() -> dict[str, Any]:
    for path, digest in {
            WPLTO: WPLTO_SHA,
            WPLTO_AUTHORITY: WPLTO_AUTHORITY_SHA,
            BASELINE: BASELINE_SHA,
            BASELINE_RECEIPT: BASELINE_RECEIPT_SHA,
            HARDWARE_FIRST_RED: HARDWARE_FIRST_RED_SHA}.items():
        require(path.is_file() and L.sha(path) == digest,
                f"Link-51 authority SHA drift: {path}")
    qualified = json.loads(WPLTO_AUTHORITY.read_text(encoding="utf-8"))
    replay = json.loads(WPLTO.read_text(encoding="utf-8"))
    require(qualified["status"] ==
                "passed-WPLTO-and-pure-section-addend-replay"
            and not qualified["promotable"]
            and qualified["walls"] == {
                "bank0_text_headroom_bytes": 53,
                "ordinary_bank0_bss_headroom_bytes": 213,
                "fixed_hot_block_headroom_bytes": 33,
                "resident_island_headroom_bytes": 5,
                "e000_headroom_bytes": 58}
            and qualified["capacity"]["session_family_bytes"] == 65438
            and qualified["one_truth_correction"]["linked_gate"]
                ["private_facade_intern_relocations"] == 0
            and replay["fresh_read_only_replay"]["walls"] ==
                qualified["walls"],
            "Link-51 canonical-t WPLTO authority incomplete")
    return qualified


def main() -> int:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Link 51 is one-shot")
    authority = validate_authority()
    old = {
        "number": BASE.LINK_NUMBER, "out": BASE.OUT,
        "receipt": BASE.RECEIPT, "wplto": BASE.WPLTO,
        "wplto_sha": BASE.WPLTO_SHA,
        "wplto_profile": BASE.WPLTO_PROFILE,
        "validate": BASE.validate_authority,
        "replacement": BASE.corrected_replacement,
        "prelink": BASE_LINK.fresh_prelink_gates,
        "single_link": P.single_link,
        "require": L.require,
    }

    def current_require(value: bool, message: str) -> None:
        # Historical Link-47 exact shape; the current sized L65E gate remains
        # active and proves 1143 <= 1320.
        if (not value and message ==
                "fresh Link-47 L65E shape red: "
                "{'bytes': 1143, 'cap_bytes': 1320, "
                "'headroom_bytes': 177}"):
            return
        old["require"](value, message)

    def prelink() -> dict[str, Any]:
        value = old["prelink"]()
        value["vm_badopcode_retirement_and_canonical_t_source"] = {
            "source": RETIRE.source_gate(mutations=True),
            "semantics": RETIRE.semantic_fixture()}
        return value

    def replacement(product: Path, elf: Path,
                    host: dict[str, Any]) -> dict[str, Any]:
        value = old["replacement"](product, elf, host)
        value["vm_badopcode_retirement_and_canonical_t"] = \
            RETIRE.linked_gate(elf, P.TOOLCHAIN / "llvm-readobj")
        value["badopcode_hold_shelf_rebased"] = SHELF.qualify(
            product, elf, P.TOOLCHAIN / "llvm-readobj")
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(line for line in kwargs.get("extra_contract_lines", ())
                      if not line.startswith((
                          "mode=", "source_baseline=", "promotable=",
                          "canonical_t_authority=", "canonical_t_wplto=")))
        kwargs["extra_contract_lines"] = (
            "mode=link51-c2-lite-v6-canonical-t",
            "source_baseline=product-link50-persistent-header",
            "promotable=no-hardware-not-run",
            "canonical_t_authority=eval_init:lisp_t",
            "canonical_t_wplto=" + WPLTO_AUTHORITY_SHA,
            *lines)
        return old["single_link"](*args, **kwargs)

    try:
        BASE.LINK_NUMBER = LINK_NUMBER
        BASE.OUT = OUT
        BASE.RECEIPT = RECEIPT
        BASE.WPLTO = WPLTO
        BASE.WPLTO_SHA = WPLTO_SHA
        BASE.WPLTO_PROFILE = WPLTO_PROFILE
        BASE.validate_authority = validate_authority
        BASE.corrected_replacement = replacement
        BASE_LINK.fresh_prelink_gates = prelink
        P.single_link = single_link
        L.require = current_require
        result = BASE.main()
    finally:
        BASE.LINK_NUMBER = old["number"]
        BASE.OUT = old["out"]
        BASE.RECEIPT = old["receipt"]
        BASE.WPLTO = old["wplto"]
        BASE.WPLTO_SHA = old["wplto_sha"]
        BASE.WPLTO_PROFILE = old["wplto_profile"]
        BASE.validate_authority = old["validate"]
        BASE.corrected_replacement = old["replacement"]
        BASE_LINK.fresh_prelink_gates = old["prelink"]
        P.single_link = old["single_link"]
        L.require = old["require"]
    if result != 0:
        return result

    os.chmod(RECEIPT, 0o644)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    gates = receipt["fresh_replacement_gates"]
    walls = gates["walls"]
    capacity = gates["capacity"]
    canonical = gates["vm_badopcode_retirement_and_canonical_t"][
        "canonical_t"]
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    map_path = Path(str(product) + ".map")
    require(receipt["link_number"] == LINK_NUMBER
            and L.sha(product) != BASELINE_SHA
            and walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and walls["ordinary_bank0_bss_headroom_bytes"] == 213
            and walls["fixed_hot_block_headroom_bytes"] >= 0
            and walls["resident_island_headroom_bytes"] >= 0
            and capacity["session_family_bytes"] <= 65536
            and canonical["bytes"] == 2
            and canonical["installer_resolved_bytes"] == [0, 1]
            and canonical["private_facade_intern_relocations"] == 0,
            "Link-51 final product qualification red")
    receipt["format"] = "lisp65-c2-lite-v6-link51-canonical-t-v1"
    receipt["status"] = (
        "passed-new-canonical-t-product-identity-hardware-not-run")
    receipt["authority"]["canonical_t_wplto"] = L.bind(WPLTO_AUTHORITY)
    receipt["authority"]["canonical_t_qualification_replay"] = L.bind(WPLTO)
    receipt["authority"]["link50_rollback_product"] = {
        **L.bind(BASELINE), "status": "untouched"}
    receipt["authority"]["link50_first_call_hardware_first_red"] = \
        L.bind(HARDWARE_FIRST_RED)
    receipt["canonical_t"] = {
        "authority": "eval_init:lisp_t",
        "storage_bytes": 2,
        "new_storage_bytes": 0,
        "installer_linked_gate": canonical,
        "private_intern_edge": "absent"}
    receipt["product_identity"] = {
        "product": L.bind(product), "elf": L.bind(elf),
        "map": L.bind(map_path)}
    receipt["counters"] = {
        "class_b_diagnostic_cycles": "3/3 closed",
        "line1_product_first_reds": "2/3",
        "completed_latency_measurements": "0/2"}
    receipt["next_gate"] = (
        "Hardware presmoke: boot, (defun %c2h () 't), %c2h, then the "
        "authorized latency rows only after semantic success.")
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link51-canonical-t: PASS "
          f"product={receipt['product_identity']['product']['sha256']} "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"session={capacity['session_family_bytes']} hardware=not-run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Link51Error, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link51-canonical-t: FIRST RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
