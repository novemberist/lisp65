#!/usr/bin/env python3
"""One product-shaped WPLTO for keymap plus published-nullary call.

This is the single capacity/placement truth requested after hardware frame
attribution.  It deliberately builds without the nonpromotable frame-stamp
feature and performs no promotable product link or hardware action.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_l_full_keymap_end_to_end_gate as KEYGATE  # noqa: E402
import c2_l_full_static_plane_gate as PLANE  # noqa: E402
import c2_link57_l_full_keymap_current_product_wplto as CURRENT  # noqa: E402
import c2_lite_v6_link49_append_final_hybrid_facade16_successor_link as PROFILE  # noqa: E402
import c2_top_level_published_nullary_call_gate as DIRECT  # noqa: E402


P = CURRENT.P
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/published-nullary-call-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-published-nullary-call-wplto-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-published-nullary-call-wplto-base.json")
RECEIPT = EVIDENCE / (
    "c2.2-published-nullary-call-wplto-receipt.json")
ARTIFACT_RECEIPT = EVIDENCE / (
    "c2.2-published-nullary-call-bytecode-product-artifacts-receipt.json")
ATTRIBUTION = EVIDENCE / (
    "c2.2-link57-top-level-frame-attribution-hardware-receipt.json")
PRODUCT_IDENTITY = ROOT / (
    "build/c2.2/substitution/published-nullary-call-bytecode-artifacts/"
    "product/substitution-artifacts.json")
BYTECODE = ROOT / (
    "build/c2.2/substitution/published-nullary-call-bytecode-artifacts")
SPECS = (
    ("stdlib-p0", "stdlib", BYTECODE / "workbench/stdlib-p0.manifest.json"),
    ("ide", "ide", BYTECODE / "libs/ide.manifest.json"),
    ("idex", "idex", BYTECODE / "libs/idex.manifest.json"),
    ("m65d", "m65d", BYTECODE / "libs/m65d.manifest.json"),
    ("buffer", "buffer",
     ROOT / "build/bytecode/dialect-v2/libs/buffer.manifest.json"),
    ("lcc", "lcc", ROOT / "build/c2.2/substitution/lcc.manifest.json"),
)
LINK56 = ROOT / (
    "build/c2.2/substitution/product-link-56-selector-tail-z/"
    "lisp65-c2-substitution-linked.prg")
LATENCY = ROOT / (
    "build/c2.2/hardware-presmoke-link56-selector-tail-z/latency/result.json")


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def authority() -> dict[str, Any]:
    plane_bundle = PLANE.source_bundle()
    plane = PLANE.validate(plane_bundle)
    plane["mutations_rejected"] = len(PLANE.mutations(plane_bundle))
    key_bundle = KEYGATE.source_bundle()
    keymap = KEYGATE.validate(key_bundle, run_oracle=True)
    keymap["mutations_rejected"] = KEYGATE.mutation_tests(key_bundle)
    direct_bundle = DIRECT.bundle()
    direct = DIRECT.validate_source(direct_bundle)
    direct["mutations_rejected"] = DIRECT.mutation_tests(direct_bundle)
    execution = DIRECT.executable_fixtures()
    artifacts = json.loads(ARTIFACT_RECEIPT.read_text(encoding="utf-8"))
    attribution = json.loads(ATTRIBUTION.read_text(encoding="utf-8"))
    latency = json.loads(LATENCY.read_text(encoding="utf-8"))
    features = PROFILE.resolved_features()
    require(
        artifacts["status"] ==
            "passed-L-full-plus-published-nullary-six-image-product-and-C2D-v6-plane"
        and artifacts["capacity"]["bank2_static_code_bytes"] == 34542
        and artifacts["compiled_attribution"]["delta_bytes"] == 33
        and artifacts["six_image_product"]["entries"] == 590
        and plane["static_code_bytes"] == 34542
        and plane["bank2_headroom_bytes"] == 30994
        and plane["mutations_rejected"] == 6
        and keymap["mutations_rejected"] == 10
        and direct["mutations_rejected"] == 7
        and execution["direct"]["compiler_calls"] == 0
        and execution["direct"]["install_calls"] == 0
        and attribution["conclusions"]["single_station_dominates"] is False
        and attribution["conclusions"]["whole_plane_crc_dominates"] is False
        and latency["measurement"]["definition_first_call"]["frames"] == 60
        and latency["measurement"]["warm_second_call"]["frames"] == 61
        and "LISP65_C2_FRAME_ATTRIBUTION_DIAGNOSTIC" not in features,
        "published-nullary WPLTO authority incomplete",
    )
    return {
        "link56_rollback_product": {**P.bind(LINK56), "status": "untouched"},
        "latency_attempt_1_of_2": P.bind(LATENCY),
        "hardware_frame_attribution": P.bind(ATTRIBUTION),
        "published_nullary_product_artifacts": P.bind(ARTIFACT_RECEIPT),
        "current_product_identity": P.bind(PRODUCT_IDENTITY),
        "L_full_product_profile": P.bind(PLANE.PROFILE),
        "static_plane_header": P.bind(PLANE.HEADER),
        "static_plane_gate": {
            **P.bind(Path(PLANE.__file__)), "result": plane},
        "keymap_end_to_end_gate": {
            **P.bind(Path(KEYGATE.__file__)), "result": keymap},
        "published_nullary_call_gate": {
            **P.bind(Path(DIRECT.__file__)),
            "source_result": direct,
            "execution_result": execution,
        },
        "resolved_product_features": {
            "values": list(features),
            "frame_attribution_diagnostic_absent": True,
        },
        "driver": P.bind(Path(__file__)),
    }


def main() -> int:
    require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
        "published-nullary WPLTO is one-shot",
    )
    original = {
        "out": CURRENT.OUT,
        "internal": CURRENT.INTERNAL,
        "base_receipt": CURRENT.BASE_RECEIPT,
        "receipt": CURRENT.RECEIPT,
        "product_artifacts": CURRENT.PRODUCT_ARTIFACTS,
        "product_identity": CURRENT.PRODUCT_IDENTITY,
        "bytecode": CURRENT.BYTECODE,
        "specs": CURRENT.SPECS,
        "authority": CURRENT.authority,
    }
    try:
        CURRENT.OUT = OUT
        CURRENT.INTERNAL = INTERNAL
        CURRENT.BASE_RECEIPT = BASE_RECEIPT
        CURRENT.RECEIPT = RECEIPT
        CURRENT.PRODUCT_ARTIFACTS = ARTIFACT_RECEIPT
        CURRENT.PRODUCT_IDENTITY = PRODUCT_IDENTITY
        CURRENT.BYTECODE = BYTECODE
        CURRENT.SPECS = SPECS
        CURRENT.authority = authority
        result = CURRENT.main()
    finally:
        CURRENT.OUT = original["out"]
        CURRENT.INTERNAL = original["internal"]
        CURRENT.BASE_RECEIPT = original["base_receipt"]
        CURRENT.RECEIPT = original["receipt"]
        CURRENT.PRODUCT_ARTIFACTS = original["product_artifacts"]
        CURRENT.PRODUCT_IDENTITY = original["product_identity"]
        CURRENT.BYTECODE = original["bytecode"]
        CURRENT.SPECS = original["specs"]
        CURRENT.authority = original["authority"]

    if RECEIPT.is_file():
        os.chmod(RECEIPT, 0o644)
        value = json.loads(RECEIPT.read_text(encoding="utf-8"))
        value["format"] = "lisp65-c2-published-nullary-call-WPLTO-v1"
        value["promotable"] = False
        value["targeted_fix"] = {
            "kind": "published-nullary-bytecode-direct-call",
            "static_bank2_delta_bytes": 33,
            "resident_product_delta_bytes": 0,
            "new_state_bytes": 0,
            "transaction_path_for_direct_case": "bypassed",
            "frame_attribution_diagnostic_present": False,
        }
        value["latency_accounting"] = {
            "completed_measurements": "1/2",
            "cold_frames_attempt_1": 60,
            "warm_frames_attempt_1": 61,
            "this_WPLTO_consumed_measurements": 0,
            "attempt_2_authorized": False,
        }
        value["execution_accounting"] = {
            "whole_program_lto_closure_links": 1,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        }
        value["next_gate"] = (
            "separate Class-C authorization for one successor product link; "
            "latency attempt 2 remains blocked until that linked candidate "
            "is fully qualified")
        RECEIPT.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        os.chmod(RECEIPT, 0o444)
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ProbeError,
        CURRENT.WPLTOError,
        DIRECT.GateError,
        KEYGATE.GateError,
        KEYGATE.KEYMAP.KeymapError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-published-nullary-call-WPLTO: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
