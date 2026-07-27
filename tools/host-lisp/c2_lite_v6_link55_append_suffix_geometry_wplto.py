#!/usr/bin/env python3
"""One product-shaped geometry WPLTO for the cold suffix-domain guard."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link55_append_suffix_domain_wplto as BASE  # noqa: E402


P = BASE.P
SUFFIX = BASE.SUFFIX
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.2/substitution/link55-append-suffix-geometry-wplto"
INTERNAL = EVIDENCE / (
    "c2.2-link55-append-suffix-geometry-wplto-internal-structural.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link55-append-suffix-geometry-wplto-base-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link55-append-suffix-geometry-wplto-receipt.json")
LINK54_PRODUCT = BASE.LINK54_PRODUCT
LINK54_RECEIPT = BASE.LINK54_RECEIPT
LINK54_HARDWARE = BASE.LINK54_HARDWARE
CONTRACT_PROBE = BASE.CONTRACT_PROBE
RESIDENT_FIRST_RED = EVIDENCE / (
    "c2.2-link55-append-suffix-domain-wplto-first-red.json")
COLD_FIRST_RED = EVIDENCE / (
    "c2.2-link55-append-suffix-cold-guard-wplto-first-red.json")


def authority() -> dict[str, Any]:
    expected = {
        LINK54_PRODUCT:
            "4cfc797f4ac4fac6cc4fea363ea684ea0dc8c7b395372ebc8bbfe2072fedef07",
        LINK54_RECEIPT:
            "1d57762c36832d70f91299e6cc7ea44b72a5634301075983ffd3441ae3a08b34",
        LINK54_HARDWARE:
            "08cb5b0a3a258a47614bb01f60ca71ace2c20101f3b1442c9bc137765fe64ad8",
        CONTRACT_PROBE:
            "8ab10e9a0b858f162900d6d527dfd902fcca7f0e97a6115e4151546af88d607a",
        RESIDENT_FIRST_RED:
            "9510a3f57439a7b73c5b3c72e4ee3bdb51101ad040d507560deb13ef1e205f41",
        COLD_FIRST_RED:
            "e4e97d2bae4f6f4125a39078206bf86f9adb77ac8d230c911d03f0a68f2d9c09",
        SUFFIX.CONTRACT:
            "b45091d6c16b1d19b48078a21ac66bb49e8fb5693fd14789b983cb352e36f83a",
        ROOT / "tools/host-lisp/c2_append_suffix_read_domain_gate.py":
            "919417e77a676fa59ea6ef397a910084b9b084c12731352bc269ae67e8583747",
    }
    for path, digest in expected.items():
        P.require(path.is_file() and P.sha(path) == digest,
                  f"Link-55 geometry authority SHA drift: {path}")
    baseline = json.loads(LINK54_RECEIPT.read_text(encoding="utf-8"))
    cold_red = json.loads(COLD_FIRST_RED.read_text(encoding="utf-8"))
    gates = baseline["fresh_replacement_gates"]
    P.require(
        gates["capacity"]["session_family_bytes"] == 65438
        and cold_red["status"] ==
            "first-red-cold-source-domain-seal-exceeds-entries-slice-and-session-aggregate"
        and cold_red["cold_placement_result"]["resident_window"]["delta_bytes"] == 0
        and cold_red["first_red"]["cold_sections"]["append_entries"]["over_cap_bytes"] == 70
        and cold_red["first_red"]["session_aggregate_projection"]["over_capacity_bytes"] == 414,
        "Link-55 geometry baseline or cold First Red drift")
    return {
        "link54_rollback_product": {**P.bind(LINK54_PRODUCT),
                                    "status": "untouched"},
        "link54_structural_authority": P.bind(LINK54_RECEIPT),
        "link54_phase06a_hardware_first_red": P.bind(LINK54_HARDWARE),
        "append_suffix_contract_probe": P.bind(CONTRACT_PROBE),
        "resident_guard_WPLTO_first_red": P.bind(RESIDENT_FIRST_RED),
        "cold_seal_geometry_WPLTO_first_red": P.bind(COLD_FIRST_RED),
        "cold_append_read_domain_contract": P.bind(SUFFIX.CONTRACT),
        "source_gate": P.bind(
            ROOT / "tools/host-lisp/c2_append_suffix_read_domain_gate.py"),
        "driver": P.bind(Path(__file__)),
    }


def packed(bytes_: int) -> int:
    return (bytes_ + 255) & ~255


def main() -> int:
    P.require(not OUT.exists() and not RECEIPT.exists(),
              "Link-55 suffix geometry WPLTO is one-shot")
    authority()
    original = {
        "out": BASE.OUT,
        "internal": BASE.INTERNAL,
        "base_receipt": BASE.BASE_RECEIPT,
        "receipt": BASE.RECEIPT,
        "authority": BASE.authority,
    }
    try:
        BASE.OUT = OUT
        BASE.INTERNAL = INTERNAL
        BASE.BASE_RECEIPT = BASE_RECEIPT
        BASE.RECEIPT = RECEIPT
        BASE.authority = authority
        result = BASE.main()
    finally:
        BASE.OUT = original["out"]
        BASE.INTERNAL = original["internal"]
        BASE.BASE_RECEIPT = original["base_receipt"]
        BASE.RECEIPT = original["receipt"]
        BASE.authority = original["authority"]
    if result != 0:
        return result

    os.chmod(RECEIPT, 0o644)
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    walls = value["walls"]
    capacity = value["capacity"]
    source = value["append_suffix_read_domain_source_gate"]
    linked = value["append_suffix_read_domain_linked_gate"]
    entries = linked["append_entries"]
    header = linked["append_header"]
    guard = linked["cold_guard"]
    phase04 = linked["phases"]["04"] if "04" in linked["phases"] else None
    # The four suffix phases are listed separately; derive phase 04 from the
    # co-resident guard's section inventory when the linked gate omits it.
    if phase04 is None:
        from elf_truth import ElfTruth
        elf = Path(str(OUT / "lisp65-c2-substitution-linked.prg") + ".elf")
        truth = ElfTruth.read(
            elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
        symbol = truth.symbol("c2_stream_phase_04")
        phase04 = {"section": symbol.section, "address": symbol.value,
                   "bytes": symbol.bytes,
                   "headroom_bytes": 1792 - symbol.bytes}
    P.require(
        source["status"] ==
            "passed-four-phase-suffix-and-source-domain-contract"
        and len(source["negative_mutations"]) == 13
        and source["cold_barrier"]["handoff_bytes"] == 0
        and linked["status"] ==
            "passed-linked-four-phase-suffix-domain-closure"
        and linked["source_read"]["bytes"] == 209
        and guard["section"] == ".lisp65_rt_c2d_04"
        and guard["phase04_call_edges"] == 1
        and phase04["section"] == guard["section"]
        and phase04["bytes"] <= 1792
        and entries["bytes"] <= 1792
        and header["bytes"] <= 1792
        and all(row["bytes"] <= 1792
                for row in linked["phases"].values())
        and capacity["session_family_bytes"] <= 65536
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] == 58
        and walls["ordinary_bank0_bss_headroom_bytes"] == 213
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0,
        "Link-55 append geometry WPLTO qualification red")
    value["format"] = "lisp65-c2-link55-append-suffix-geometry-wplto-v1"
    value["recorded_on"] = "2026-07-23"
    value["status"] = "passed-append-suffix-geometry-WPLTO-all-walls-green"
    value["authority"] = authority()
    value["geometry"] = {
        "method": (
            "phase-04 co-residence consumes active transaction scratch; "
            "the former entries/header seal handoff is eliminated"),
        "append_entries": {**entries, "packed_bytes": packed(entries["bytes"])},
        "append_header": {**header, "packed_bytes": packed(header["bytes"])},
        "phase04": {**phase04, "packed_bytes": packed(phase04["bytes"])},
        "cold_guard": guard,
        "transition_state": {
            "new_bytes": 0,
            "new_pointers": 0,
            "marker": "existing active c2aw transaction identity",
        },
        "cutpoint_fixture": {
            "source_mutations_rejected": len(source["negative_mutations"]),
            "phase04_guard_edges": guard["phase04_call_edges"],
        },
        "session_family_bytes": capacity["session_family_bytes"],
        "session_family_headroom_bytes":
            65536 - capacity["session_family_bytes"],
    }
    value["next_gate"] = "authorized product Link 55; hardware not yet run"
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link55-append-suffix-geometry-wplto: PASS "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"phase04={phase04['bytes']} entries={entries['bytes']} "
          f"header={header['bytes']} session={capacity['session_family_bytes']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (P.ProbeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link55-append-suffix-geometry-wplto: FIRST RED: "
              + str(error), file=sys.stderr)
        raise SystemExit(2)
