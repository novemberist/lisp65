#!/usr/bin/env python3
"""One product-shaped WPLTO for the Link-49 persistent-header repair.

The product change is deliberately one data-plan correction: the persistent
post-decode plan is 38,39,40,41,0.  This run creates no promotable product and
uses no hardware.  It also re-pins the publish-last table after the five-byte
canonical plan is present in ordinary rodata.
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
    "build/c2.2/substitution/link49-persistent-header-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-link49-persistent-header-wplto-internal.json")
RECEIPT = EVIDENCE / (
    "c2.2-link49-persistent-header-wplto-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.2-product-link49-facade16-missing-persistent-header-"
    "hardware-first-red.json")
CONTRACT = ROOT / "config/c2-append-final-hybrid-contract.json"
CUTPOINT_CONTRACT = ROOT / "config/c2-append-cutpoint-contract.json"
FEATURE = "LISP65_C2_APPEND_PLAN_FACADE"
VERIFIER_BASE = 0xB94E
FACADE_BASE = 0xB5C4
FACADE_BYTES = 48


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"persistent-header authority absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    require(not OUT.exists() and not INTERNAL.exists() and not RECEIPT.exists(),
            "persistent-header WPLTO is one-shot")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    cutpoint = json.loads(CUTPOINT_CONTRACT.read_text(encoding="utf-8"))
    decision = contract["persistent_publish_header_completion"]
    require(decision["status"] == "reviewer-authorized"
            and decision["canonical_plan"]["slots"] == [38, 39, 40, 41]
            and cutpoint["phase_plans"]["persistent_publish"]["slots"] ==
                [38, 39, 40, 41]
            and sha(FIRST_RED) ==
                "ed7e07312a78e77c1fef08bdf607e87b685606e7f0de57172f34d4676811fbff",
            "persistent-header authority drift")

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
    base_features = tuple(old["profile_features"]())
    selected_features = (base_features if FEATURE in base_features
                         else (*base_features, FEATURE))

    def feature_defines() -> tuple[str, ...]:
        require(len(selected_features) == len(set(selected_features)),
                "persistent-header profile duplicates a feature")
        return selected_features

    def configure_geometry() -> None:
        old["rf_configure"]()
        P.configure_append_plan_facade()
        require(P.host_facade_bytes() == FACADE_BYTES
                and P.host_facade_vector_addresses()[
                    "c2_facade_append_plan_walk"] == 0xB5F1,
                "persistent-header facade geometry drift")

    try:
        HYBRID.OUT = OUT
        HYBRID.INTERNAL = INTERNAL
        HYBRID.RECEIPT = RECEIPT
        HYBRID.__file__ = str(Path(__file__).resolve())
        HYBRID.ABI_FIRST_RED = FIRST_RED
        HYBRID.BASE.PROFILE.feature_defines = feature_defines
        HYBRID.BASE.RF.configure_roots_fronts = configure_geometry
        BASE_LINK.VERIFIER_BASE = VERIFIER_BASE
        STAGE.VERIFIER_BASE = VERIFIER_BASE
        ART.VERIFIER_BASE = VERIFIER_BASE
        P.VERIFIER_BINDING_BASE = VERIFIER_BASE
        result = HYBRID.main()
    except (ProbeError, OSError, RuntimeError, ValueError) as error:
        print("c2-lite-v6-link49-persistent-header-wplto: FAIL: "
              + str(error), file=sys.stderr)
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
    expected = {
        ".lisp65_c2_host_facade": (0xB5C4, 48),
        ".lisp65_c2_kernal_io_reveal": (0xB5F4, 11),
        ".lisp65_c2_kernal_map_switch": (0xB5FF, 10),
        ".lisp65_c2_kernal_state": (0xB609, 20),
        ".rodata": (0xB61D, 817),
        ".lisp65_runtime_overlay_verifier_bindings": (0xB94E, 40),
        ".data": (0xB976, 2),
        ".bss": (0xB978, 1587),
    }
    actual = {name: (truth.section(name).address, truth.section(name).bytes)
              for name in expected}
    walls = gates["walls"]
    capacity = gates["capacity"]
    require(actual == expected
            and append["walker"]["facade"]["address"] == 0xB5F1
            and append["walker"]["facade_routed_C_call_edges"] == 3
            and append["plan_data"][
                "lisp65_c2_append_persistent_publish_plan"]["bytes"] ==
                [38, 39, 40, 41, 0]
            and gates["transient_execution_lookup"]["source"]
                ["append_phase_plan"]["persistent_publish"]["status"] ==
                "passed-persistent-plan-completeness-and-order"
            and walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and capacity["session_family_bytes"] <= 65536,
            "persistent-header WPLTO geometry, plan, or wall gate red")
    receipt["status"] = (
        "passed-persistent-header-complete-plan-WPLTO-no-product-no-hardware")
    receipt["persistent_header"] = {
        "authority": bind(CONTRACT),
        "cutpoint_contract": bind(CUTPOINT_CONTRACT),
        "hardware_first_red": bind(FIRST_RED),
        "plan": {"symbol": "lisp65_c2_append_persistent_publish_plan",
                 "bytes": [38, 39, 40, 41, 0]},
        "low_resident_chain": {
            name: {"address": row[0], "bytes": row[1]}
            for name, row in actual.items()},
        "publish_last_table_address": VERIFIER_BASE,
        "walls": walls,
        "session_family_bytes": capacity["session_family_bytes"],
        "session_family_headroom_bytes":
            capacity["session_family_headroom_bytes"],
        "product_links": 0,
        "hardware_runs": 0,
    }
    receipt["next_gate"] = (
        "Reviewer-authorized successor product link with no inherited green; "
        "then the defun hardware run if and only if the link is fully green.")
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link49-persistent-header-wplto: PASS "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"session={capacity['session_family_bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
