#!/usr/bin/env python3
"""Bind the sole collective-card Red without authorizing a retry."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
FINAL_RED = ARCH / "c2.3-v1.6-r1-stored-world-collective-card-final-red.json"
CONTRACT = ARCH / "c2.3-v2.1-terminal-screen-map-authority-rebind-receipt.json"
SWEEP = ARCH / "c2.3-v1.6-r1-stored-world-sweep-receipt.json"
ELF = ROOT / (
    "build/c2.3/v1.6-r1-stored-world-collective-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
PREDECESSOR_ELF = ROOT / (
    "build/c2.3/v1.6-abort-driver-relocation-witness-conversion-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
RECEIPT = ARCH / (
    "c2.3-v1.6-r1-stored-world-collective-card-red-attribution-receipt.json")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()
STATUS = "FINAL RED ATTRIBUTED: NINTH STORED-WORLD PLACEMENT SNAPSHOT"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def linked(path: Path) -> dict[str, Any]:
    truth = ElfTruth.read(path, llvm_readobj=READOBJ,
                          include_section_data=False)
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    reader = truth.symbol("c2_map_cpu_read")
    selector = truth.symbol("c2_map_cpu_selector")
    helper = truth.symbol("c2e_w32")
    fixed = truth.section(".lisp65_c2_host_facade")
    cold = truth.section(".lisp65_rt_c2emit_final_crc")
    vector = truth.symbol("c2_facade_runtime_overlay_exec")
    shelf = truth.symbol("c2_stream_shelf_read")
    c2d = truth.symbol("c2_stream_c2d_read")
    return {"ELF": bind(path), "text_end_exclusive": text.address + text.bytes,
            "ordinary_reserve_bytes": facade.address - text.address - text.bytes,
            "facade_address": facade.address, "reader_address": reader.value,
            "reader_bytes": reader.bytes, "selector_address": selector.value,
            "selector_bytes": selector.bytes, "helper_bytes": helper.bytes,
            "cold_bytes": cold.bytes, "fixed_address": fixed.address,
            "fixed_bytes": fixed.bytes, "vector_address": vector.value,
            "shelf_bytes": shelf.bytes, "c2d_bytes": c2d.bytes}


def derive() -> dict[str, Any]:
    red = load(FINAL_RED); sweep = load(SWEEP); contract = load(CONTRACT)
    require(red["status"] ==
                "FINAL RED: R1 STORED-WORLD COLLECTIVE RETURNS TO OWNER"
            and red["retry_authorized"] is False
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_link_attempts"] == 1,
            "collective Final Red authority drift")
    actual = linked(ELF); predecessor = linked(PREDECESSOR_ELF)
    price = contract["semantic_equivalence"]["placement_price"]
    expected = {"reader_address": 0x2277,
        "reader_bytes": price["expected_linked_bytes"],
        "ordinary_reserve_bytes": price["expected_reserve_bytes"],
        "text_end_exclusive": 0xB3B0 - price["expected_reserve_bytes"],
        "facade_address": 0xB3B0}
    shared = {key: actual[key] == predecessor[key] for key in actual
              if key != "ELF"}
    require(expected == {"reader_address": 0x2277, "reader_bytes": 189,
                         "ordinary_reserve_bytes": 1,
                         "text_end_exclusive": 0xB3AF,
                         "facade_address": 0xB3B0}
            and actual["reader_address"] == expected["reader_address"]
            and actual["reader_bytes"] == expected["reader_bytes"]
            and actual["facade_address"] == expected["facade_address"]
            and actual["ordinary_reserve_bytes"] == 6
            and actual["text_end_exclusive"] == 0xB3AA
            and all(shared.values()),
            "placement Final Red attribution drift")
    return {"format": "lisp65-c2-v160-r1-collective-red-attribution-v1",
        "recorded_on": "2026-08-19", "status": STATUS,
        "classification": "stored-world placement reserve/end snapshot",
        "failed_consumer":
            "c2_v21_candidate_derived_local_return.linked_gate",
        "stored_authority": bind(CONTRACT), "stored_expectation": expected,
        "candidate_observation": actual,
        "predecessor_counterproof": {"observation": predecessor,
            "all_nonidentity_fields_equal": all(shared.values())},
        "passed_conjuncts": ["reader address 0x2277", "reader bytes 189",
            "facade address 0xb3b0", "selector follows reader and is 40 bytes",
            "cold helper/service/fixed identities"],
        "failed_conjuncts": ["stored reserve 1 vs candidate 6",
            "stored text end 0xb3af vs candidate 0xb3aa"],
        "sweep_failure": {"inventory_rows_reported": sweep["inventory_count"],
            "missing_row": "post-link.local-return-placement-reserve",
            "cause": "the sweep bound the wrapper entry but did not traverse the linked gate installed transitively by configure()",
            "completeness_claim_withdrawn": True},
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "authority": {"Final_Red": bind(FINAL_RED), "sweep": bind(SWEEP),
            "driver": bind(DRIVER)},
        "retry_authorized": False, "owner_disposition_required": True,
        "claim_limit": "Attribution over frozen linked artifacts only; no scope, acceptance, fix, or retry."}


def check() -> None:
    require(load(RECEIPT) == derive(), "collective Red attribution drift")
    print("R1 collective Final Red attribution: PASS ninth-site reserve=1->6 retry=0")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "print":
        print(json.dumps(derive(), indent=2, sort_keys=True))
    elif len(sys.argv) == 2 and sys.argv[1] == "check":
        check()
    else:
        raise SystemExit("usage: ... {print|check}")
