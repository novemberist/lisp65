#!/usr/bin/env python3
"""One owner-authorized WPLTO for append-plan facade vector sixteen.

The preceding ABI-correct WPLTO stopped at the fixed-facade gate.  This run
adds exactly one three-byte vector at $B5F1, advances the predecessor-bound
low-resident chain by three bytes, and re-pins its 40-byte publish-last table
at $B949.  It is product-shaped only: no promotable product or hardware run is
created here.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link48_append_final_hybrid_wplto as HYBRID  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


P = HYBRID.P
BASE_LINK = HYBRID.BASE.FINAL.BASE_LINK
STAGE = BASE_LINK.STAGE
ART = BASE_LINK.ART
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/link48-append-final-hybrid-facade16-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-facade16-wplto-internal.json")
RECEIPT = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-facade16-wplto-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-abi-wplto-"
    "facade-first-red-diagnosis.json")
CLASS_A_FIRST_RED = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-facade16-wplto-"
    "class-a-first-red.json")
CONTRACT = ROOT / "config/c2-append-final-hybrid-contract.json"
FEATURE = "LISP65_C2_APPEND_PLAN_FACADE"
VERIFIER_BASE = 0xB949
FACADE_BASE = 0xB5C4
FACADE_BYTES = 48


class FacadeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FacadeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"facade authority absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    require(not OUT.exists() and not INTERNAL.exists() and not RECEIPT.exists(),
            "facade-16 WPLTO is one-shot")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    decision = contract["append_plan_facade16"]
    require(decision["status"] == "owner-authorized"
            and decision["vector"]["address"] == "0xb5f1"
            and decision["vector"]["ordinal"] == 16
            and decision["following_chain_shift_bytes"] == 3
            and decision["publish_last"]["address"] == "0xb949"
            and sha(FIRST_RED) ==
                "ebbd781ad8424c86152530707dd7fcb4131fd163b6cf8ca438337b0b3f0e8bd4",
            "owner facade-16 authority drift")

    old = {
        "out": HYBRID.OUT,
        "internal": HYBRID.INTERNAL,
        "receipt": HYBRID.RECEIPT,
        "file": HYBRID.__file__,
        "first_red": HYBRID.ABI_FIRST_RED,
        "profile_features": HYBRID.BASE.PROFILE.feature_defines,
        "rf_configure": HYBRID.BASE.RF.configure_roots_fronts,
        "base_link_verifier": BASE_LINK.VERIFIER_BASE,
        "stage_verifier": STAGE.VERIFIER_BASE,
        "art_verifier": ART.VERIFIER_BASE,
        "p_verifier": P.VERIFIER_BINDING_BASE,
    }
    selected_features = (*old["profile_features"](), FEATURE)

    def feature_defines() -> tuple[str, ...]:
        require(len(selected_features) == len(set(selected_features)),
                "facade feature duplicated")
        return selected_features

    def configure_facade16() -> None:
        old["rf_configure"]()
        P.configure_append_plan_facade()
        require(P.host_facade_bytes() == FACADE_BYTES
                and P.host_facade_vector_addresses()[
                    "c2_facade_append_plan_walk"] == 0xB5F1,
                "facade-16 profile geometry drift")

    try:
        HYBRID.OUT = OUT
        HYBRID.INTERNAL = INTERNAL
        HYBRID.RECEIPT = RECEIPT
        HYBRID.__file__ = str(Path(__file__).resolve())
        HYBRID.ABI_FIRST_RED = FIRST_RED
        HYBRID.BASE.PROFILE.feature_defines = feature_defines
        HYBRID.BASE.RF.configure_roots_fronts = configure_facade16
        BASE_LINK.VERIFIER_BASE = VERIFIER_BASE
        STAGE.VERIFIER_BASE = VERIFIER_BASE
        ART.VERIFIER_BASE = VERIFIER_BASE
        result = HYBRID.main()
    except (FacadeError, OSError, RuntimeError, ValueError) as error:
        print("c2-lite-v6-append-final-facade16-wplto: FAIL: " + str(error),
              file=sys.stderr)
        return 1
    finally:
        HYBRID.OUT = old["out"]
        HYBRID.INTERNAL = old["internal"]
        HYBRID.RECEIPT = old["receipt"]
        HYBRID.__file__ = old["file"]
        HYBRID.ABI_FIRST_RED = old["first_red"]
        HYBRID.BASE.PROFILE.feature_defines = old["profile_features"]
        HYBRID.BASE.RF.configure_roots_fronts = old["rf_configure"]
        BASE_LINK.VERIFIER_BASE = old["base_link_verifier"]
        STAGE.VERIFIER_BASE = old["stage_verifier"]
        ART.VERIFIER_BASE = old["art_verifier"]
        P.VERIFIER_BINDING_BASE = old["p_verifier"]

    if result != 0:
        return result
    os.chmod(RECEIPT, 0o644)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    gates = internal["fresh_replacement_gates"]
    append = gates["transient_execution_lookup"]["linked"][
        "append_phase_plan"]
    elf = OUT / "lisp65-c2-substitution-linked.prg.elf"
    truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    sections = {name: truth.section(name) for name in (
        ".lisp65_c2_host_facade", ".lisp65_c2_kernal_io_reveal",
        ".lisp65_c2_kernal_map_switch", ".lisp65_c2_kernal_state",
        ".rodata", ".lisp65_runtime_overlay_verifier_bindings", ".data",
        ".bss")}
    expected = {
        ".lisp65_c2_host_facade": (0xB5C4, 48),
        ".lisp65_c2_kernal_io_reveal": (0xB5F4, 11),
        ".lisp65_c2_kernal_map_switch": (0xB5FF, 10),
        ".lisp65_c2_kernal_state": (0xB609, 20),
        ".rodata": (0xB61D, 812),
        ".lisp65_runtime_overlay_verifier_bindings": (0xB949, 40),
        ".data": (0xB971, 2),
        ".bss": (0xB973, 1587),
    }
    require(all((sections[name].address, sections[name].bytes) == row
                for name, row in expected.items())
            and append["walker"]["facade"]["address"] == 0xB5F1
            and append["walker"]["facade_routed_C_call_edges"] == 2
            and gates["capacity"]["session_family_bytes"] <= 65536,
            "facade-16 WPLTO final chain or aggregate drift")
    receipt["status"] = (
        "passed-owner-facade16-full-repin-WPLTO-no-product-no-hardware")
    receipt["facade16"] = {
        "authority": bind(CONTRACT),
        "first_red": bind(FIRST_RED),
        "class_a_preflight_first_red": bind(CLASS_A_FIRST_RED),
        "feature": FEATURE,
        "vector": {"ordinal": 16, "symbol":
                   "c2_facade_append_plan_walk", "address": 0xB5F1,
                   "bytes": 3, "target": "c2_append_plan_walk"},
        "low_resident_chain": {
            name: {"address": section.address, "bytes": section.bytes}
            for name, section in sections.items()},
        "publish_last_table_address": VERIFIER_BASE,
        "fixed_points": {"fixed_block": 0xC080,
                         "fixed_code": 0xC218,
                         "runtime_overlay_vma": 0xC356},
        "fresh_session_aggregate_qualified": True,
        "product_links": 0,
        "hardware_runs": 0,
    }
    receipt["next_gate"] = (
        "Owner-authorized successor product link with no inherited green; "
        "then the defun hardware run if and only if the link is fully green.")
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-append-final-facade16-wplto: PASS "
          f"text={gates['walls']['bank0_text_headroom_bytes']} "
          f"e000={gates['walls']['e000_headroom_bytes']} "
          f"session={gates['capacity']['session_family_bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
