#!/usr/bin/env python3
"""One product-shaped WPLTO for the approved BADOPCODE detail withdrawal."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link50_persistent_header_successor_link as LINK50  # noqa: E402
import c2_vm_badopcode_detail_gate as RETIRE  # noqa: E402
import c2_badopcode_hold_shelf_gate as SHELF  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE_DIR = ROOT / ("build/c2.2/substitution/"
                   "product-link-50-c2-lite-v6-persistent-header")
BASE_PRODUCT = BASE_DIR / "lisp65-c2-substitution-linked.prg"
BASE_RECEIPT = EVIDENCE / (
    "c2.2-product-link50-c2-lite-v6-persistent-header-"
    "artifact-replay-structural-receipt.json")
CONTRACT = ROOT / "config/c2-vm-badopcode-detail-contract.json"
SCOPE = EVIDENCE / (
    "c2.2-link50-badopcode-detail-single-constructor-scope-decision.json")
SHELF_RECEIPT = EVIDENCE / (
    "c2.2-link50-badopcode-hold-shelf-recipe-receipt.json")
OUT = ROOT / "build/c2.2/substitution/link50-badopcode-retirement-wplto"
INTERNAL = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-wplto-internal-structural.json")
RECEIPT = EVIDENCE / (
    "c2.2-link50-badopcode-retirement-wplto-receipt.json")


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"retirement authority absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def authority() -> dict[str, Any]:
    expected = {
        BASE_PRODUCT:
            "3e13c9101b53ba89b8fb33e0f11c641ca53803b3f447831c5e1243475f7bc216",
        BASE_RECEIPT:
            "e7f47adebda448583efa6e28d86ff28bb335adf3178853b5177e736cccd36170",
        SCOPE:
            "b0301c4e684741529e96b72643161e3722fffbc7e924a7d797e194b02001b315",
        SHELF_RECEIPT:
            "201fa752bce17ac9d8ee1e9b120ed2781dc81d85f13257376fd798dbe55bbb4e",
    }
    for path, digest in expected.items():
        require(path.is_file() and sha(path) == digest,
                f"retirement authority SHA drift: {path}")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    baseline = json.loads(BASE_RECEIPT.read_text(encoding="utf-8"))
    require(contract["decision"]["choice"] ==
                "option_3_withdraw_permanent_BADOPCODE_detail"
            and baseline["fresh_replacement_gates"]["walls"] == {
                "bank0_text_headroom_bytes": 37,
                "ordinary_bank0_bss_headroom_bytes": 213,
                "fixed_hot_block_headroom_bytes": 33,
                "resident_island_headroom_bytes": 5,
                "e000_headroom_bytes": 58}
            and baseline["fresh_replacement_gates"]["capacity"]
                ["session_family_bytes"] == 65438,
            "retirement baseline/decision authority incomplete")
    return {
        "link50_rollback_product": {**bind(BASE_PRODUCT),
                                    "status": "untouched"},
        "link50_structural_authority": bind(BASE_RECEIPT),
        "approved_retirement_contract": bind(CONTRACT),
        "measured_scope_decision": bind(SCOPE),
        "prepared_hold_shelf": bind(SHELF_RECEIPT),
        "driver": bind(Path(__file__)),
    }


def main() -> int:
    require(not OUT.exists() and not INTERNAL.exists() and not RECEIPT.exists(),
            "BADOPCODE retirement WPLTO is one-shot")
    auth = authority()
    old = {
        "out": LINK50.OUT,
        "receipt": LINK50.RECEIPT,
        "replacement": LINK50.corrected_replacement,
        "prelink": LINK50.BASE_LINK.fresh_prelink_gates,
        "single_link": LINK50.P.single_link,
    }

    def prelink() -> dict[str, Any]:
        value = old["prelink"]()
        value["vm_badopcode_retirement_source"] = {
            "source": RETIRE.source_gate(mutations=True),
            "semantics": RETIRE.semantic_fixture(),
            "hold_shelf": SHELF.qualify(
                SHELF.BASE_PRODUCT, SHELF.BASE_ELF, SHELF.READOBJ),
        }
        return value

    def replacement(product: Path, elf: Path,
                    host: dict[str, Any]) -> dict[str, Any]:
        value = old["replacement"](product, elf, host)
        value["vm_badopcode_retirement"] = RETIRE.linked_gate(
            elf, LINK50.P.TOOLCHAIN / "llvm-readobj")
        value["badopcode_hold_shelf_rebased"] = SHELF.qualify(
            product, elf, LINK50.P.TOOLCHAIN / "llvm-readobj")
        return value

    def nonpromotable_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(line for line in kwargs.get("extra_contract_lines", ())
                      if not line.startswith(("promotable=", "probe_scope=")))
        kwargs["extra_contract_lines"] = (
            "promotable=no-product-shaped-WPLTO-only",
            "probe_scope=BADOPCODE-detail-withdrawal-and-shelf-rebase",
            *lines)
        return old["single_link"](*args, **kwargs)

    try:
        LINK50.OUT = OUT
        LINK50.RECEIPT = INTERNAL
        LINK50.corrected_replacement = replacement
        LINK50.BASE_LINK.fresh_prelink_gates = prelink
        LINK50.P.single_link = nonpromotable_link
        result = LINK50.main()
    finally:
        LINK50.OUT = old["out"]
        LINK50.RECEIPT = old["receipt"]
        LINK50.corrected_replacement = old["replacement"]
        LINK50.BASE_LINK.fresh_prelink_gates = old["prelink"]
        LINK50.P.single_link = old["single_link"]

    if result != 0:
        value = {
            "format": "lisp65-c2-badopcode-retirement-wplto-first-red-v1",
            "recorded_on": "2026-07-22",
            "status": "FIRST RED: BADOPCODE retirement WPLTO stopped",
            "promotable": False,
            "authority": auth,
            "internal_receipt": bind(INTERNAL) if INTERNAL.is_file() else None,
            "execution_accounting": {"whole_program_lto_closure_links": 1,
                                     "promotable_product_links": 0,
                                     "hardware_runs": 0},
            "next_gate": "stop; return measured red to Class-C review",
        }
        write(RECEIPT, value)
        os.chmod(RECEIPT, 0o444)
        return 2

    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    gates = internal["fresh_replacement_gates"]
    walls = gates["walls"]
    capacity = gates["capacity"]
    retirement = gates["vm_badopcode_retirement"]
    shelf = gates["badopcode_hold_shelf_rebased"]
    require(walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and walls["ordinary_bank0_bss_headroom_bytes"] == 213
            and walls["fixed_hot_block_headroom_bytes"] >= 0
            and walls["resident_island_headroom_bytes"] >= 0
            and capacity["session_family_bytes"] <= 65536
            and retirement["status"].startswith("passed-linked")
            and shelf["capacity_delta_bytes"] == 0,
            "BADOPCODE retirement WPLTO crossed a bound wall or gate")
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    value = {
        "format": "lisp65-c2-badopcode-retirement-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-product-shaped-WPLTO-no-product-link-no-hardware",
        "promotable": False,
        "authority": auth,
        "source_gate": RETIRE.source_gate(mutations=True),
        "semantic_fixture": RETIRE.semantic_fixture(),
        "linked_gate": retirement,
        "hold_shelf_rebased": shelf,
        "capacity": {"walls": walls,
                     "session_family_bytes": capacity["session_family_bytes"],
                     "session_family_headroom_bytes":
                         capacity["session_family_headroom_bytes"],
                     "bank0_text_noise_reserve_required_bytes": 32,
                     "e000_floor_bytes": 54},
        "product_shaped_identity": {**bind(product), "nonpromotable": True},
        "product_shaped_elf": bind(elf),
        "internal_structural_receipt": bind(INTERNAL),
        "link50_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
        "execution_accounting": {"whole_program_lto_closure_links": 1,
                                 "promotable_product_links": 0,
                                 "hardware_runs": 0},
        "counters": {"class_b_diagnostic_cycles": "3/3 closed",
                     "line1_product_first_reds": "2/3",
                     "completed_latency_measurements": "0/2"},
        "next_gate": "authorized successor product link",
    }
    write(RECEIPT, value)
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link50-badopcode-retirement-wplto: PASS "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"session={capacity['session_family_bytes']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProbeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link50-badopcode-retirement-wplto: FAIL: " +
              str(error), file=sys.stderr)
        raise SystemExit(2)
