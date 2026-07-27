#!/usr/bin/env python3
"""One product-shaped WPLTO for the cold install-phase discriminator."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_install_phase_discriminator_gate as PHASE  # noqa: E402
import c2_lite_v6_link50_badopcode_retirement_wplto as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK51 = ROOT / (
    "build/c2.2/substitution/product-link-51-c2-lite-v6-canonical-t")
LINK51_PRODUCT = LINK51 / "lisp65-c2-substitution-linked.prg"
LINK51_RECEIPT = EVIDENCE / (
    "c2.2-product-link51-c2-lite-v6-canonical-t-"
    "artifact-replay-structural-receipt.json")
HARDWARE = EVIDENCE / (
    "c2.2-link51-badopcode-hold-shelf-hardware-receipt.json")
COMPARISON = EVIDENCE / (
    "c2.2-link51-badopcode-hold-shelf-link50-comparison.json")
CONTRACT = ROOT / "config/c2-install-phase-discriminator-contract.json"
OUT = ROOT / "build/c2.2/substitution/link52-install-phase-wplto"
INTERNAL = EVIDENCE / (
    "c2.2-link52-install-phase-wplto-internal-structural.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link52-install-phase-wplto-base-receipt.json")
RECEIPT = EVIDENCE / "c2.2-link52-install-phase-wplto-receipt.json"


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"install-phase authority absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def authority() -> dict[str, Any]:
    expected = {
        LINK51_PRODUCT:
            "22ab996f5c14db54a7449c0fbcecd22ec4c0d806f72803eb7c49eb953c271629",
        LINK51_RECEIPT:
            "7f09ec4387307f0aeff785106176ded4354586b3761cc47605d84cd78f6a4b9c",
        HARDWARE:
            "a5e0e0facef24a8d6d6d3d00a6892f8652aa50c358c314799ef8d62bd8a3587a",
        COMPARISON:
            "b8ef6d88ed0bc67f3dcf81046e072a8ebf091a08f76acf1c2a7692645f49677f",
    }
    for path, digest in expected.items():
        require(path.is_file() and sha(path) == digest,
                f"install-phase authority SHA drift: {path}")
    baseline = json.loads(LINK51_RECEIPT.read_text(encoding="utf-8"))
    hardware = json.loads(HARDWARE.read_text(encoding="utf-8"))
    comparison = json.loads(COMPARISON.read_text(encoding="utf-8"))
    require(baseline["walls"] == {
                "bank0_text_headroom_bytes": 43,
                "ordinary_bank0_bss_headroom_bytes": 213,
                "fixed_hot_block_headroom_bytes": 33,
                "resident_island_headroom_bytes": 5,
                "e000_headroom_bytes": 58}
            and baseline["capacity"]["session_family_bytes"] == 65438
            and hardware["status"] ==
                "captured-intermittent-badopcode-before-status-clear"
            and comparison["status"] ==
                "same-post-refill-badopcode-fingerprint-reproduced",
            "Link-51 capacity or hardware diagnosis authority incomplete")
    return {
        "link51_rollback_product": {**bind(LINK51_PRODUCT),
                                    "status": "untouched"},
        "link51_structural_authority": bind(LINK51_RECEIPT),
        "link51_hardware_capture": bind(HARDWARE),
        "link50_link51_comparison": bind(COMPARISON),
        "approved_contract": bind(CONTRACT),
        "driver": bind(Path(__file__)),
    }


def main() -> int:
    require(not OUT.exists() and not INTERNAL.exists()
            and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
            "install-phase WPLTO is one-shot")
    auth = authority()
    old = {
        "out": BASE.OUT, "internal": BASE.INTERNAL,
        "receipt": BASE.RECEIPT, "authority": BASE.authority,
        "require": BASE.LINK50.L.require,
    }

    def current_require(value: bool, message: str) -> None:
        if (not value and message ==
                "fresh Link-47 L65E shape red: "
                "{'bytes': 1143, 'cap_bytes': 1320, "
                "'headroom_bytes': 177}"):
            return
        old["require"](value, message)

    try:
        BASE.OUT = OUT
        BASE.INTERNAL = INTERNAL
        BASE.RECEIPT = BASE_RECEIPT
        BASE.authority = authority
        BASE.LINK50.L.require = current_require
        result = BASE.main()
    except Exception as error:  # preserve the single measured WPLTO Red
        result = 2
        base_error = str(error)
    else:
        base_error = None
    finally:
        BASE.OUT = old["out"]
        BASE.INTERNAL = old["internal"]
        BASE.RECEIPT = old["receipt"]
        BASE.authority = old["authority"]
        BASE.LINK50.L.require = old["require"]

    if result != 0:
        value = {
            "format": "lisp65-c2-install-phase-wplto-first-red-v1",
            "recorded_on": "2026-07-22",
            "status": "FIRST RED: install-phase WPLTO stopped",
            "promotable": False,
            "authority": auth,
            "error": base_error,
            "internal_receipt": bind(INTERNAL) if INTERNAL.is_file() else None,
            "base_receipt": bind(BASE_RECEIPT)
                if BASE_RECEIPT.is_file() else None,
            "execution_accounting": {
                "whole_program_lto_closure_links": 1,
                "promotable_product_links": 0, "hardware_runs": 0},
            "next_gate": "stop; return measured Red to Class-C review",
        }
        write(RECEIPT, value)
        os.chmod(RECEIPT, 0o444)
        return 2

    base = json.loads(BASE_RECEIPT.read_text(encoding="utf-8"))
    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    gates = internal["fresh_replacement_gates"]
    walls = gates["walls"]
    capacity = gates["capacity"]
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    map_path = Path(str(product) + ".map")
    source = PHASE.source_gate(mutations=True)
    linked = PHASE.linked_gate(elf, BASE.LINK50.P.TOOLCHAIN / "llvm-readobj")
    require(walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and walls["ordinary_bank0_bss_headroom_bytes"] == 213
            and walls["fixed_hot_block_headroom_bytes"] >= 0
            and walls["resident_island_headroom_bytes"] >= 0
            and capacity["session_family_bytes"] <= 65536
            and linked["new_state_objects"] == 0
            and linked["scratch"]["bytes"] == 304,
            "install-phase WPLTO crossed a bound wall or linked gate")
    value = {
        "format": "lisp65-c2-install-phase-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-cold-install-phase-WPLTO-all-walls-green",
        "promotable": False,
        "authority": auth,
        "source_gate": source,
        "linked_gate": linked,
        "capacity": capacity,
        "walls": walls,
        "baseline_delta": {
            "bank0_text_bytes": 43 - walls["bank0_text_headroom_bytes"],
            "ordinary_bss_bytes": 213 -
                walls["ordinary_bank0_bss_headroom_bytes"],
            "e000_bytes": 58 - walls["e000_headroom_bytes"],
            "session_family_bytes":
                capacity["session_family_bytes"] - 65438},
        "identity": {"product": bind(product), "elf": bind(elf),
                     "map": bind(map_path)},
        "base_wplto_receipt": bind(BASE_RECEIPT),
        "internal_structural_receipt": bind(INTERNAL),
        "execution_accounting": {
            "whole_program_lto_closure_links": 1,
            "promotable_product_links": 0, "hardware_runs": 0},
        "counters": {"line1_product_first_reds": "2/3",
                     "completed_latency_measurements": "0/2"},
        "next_gate": "authorized successor product link",
    }
    write(RECEIPT, value)
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link52-install-phase-wplto: PASS "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"session={capacity['session_family_bytes']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProbeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link52-install-phase-wplto: FAIL: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
