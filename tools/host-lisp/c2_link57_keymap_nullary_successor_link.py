#!/usr/bin/env python3
"""Build Link 57 with L-full keymap and published-nullary direct calls."""

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
import c2_link56_selector_tail_z_successor_link as BASE  # noqa: E402
import c2_link57_l_full_keymap_current_product_wplto as PROFILE_GATE  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_substitution_artifacts as SUB  # noqa: E402
import c2_top_level_published_nullary_call_gate as DIRECT  # noqa: E402
import c2_zero_literal_execution_gate as ZERO  # noqa: E402


L = BASE.L
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK_NUMBER = 57
OUT = ROOT / (
    "build/c2.2/substitution/product-link-57-keymap-nullary-fast-path")
RECEIPT = EVIDENCE / (
    "c2.2-product-link57-keymap-nullary-fast-path-structural-receipt.json")
WPLTO = EVIDENCE / (
    "c2.2-published-nullary-call-artifact-replay3-receipt.json")
WPLTO_SHA = (
    "e624ca8902267b8c1b8c54e03db32af7056bc37a8836f7b2c528280a27cf6d1e")
WPLTO_SOURCE = ROOT / (
    "build/c2.2/substitution/published-nullary-call-wplto")
WPLTO_PROFILE = WPLTO_SOURCE / "resolved-profile.txt"
BASELINE = ROOT / (
    "build/c2.2/substitution/product-link-56-selector-tail-z/"
    "lisp65-c2-substitution-linked.prg")
BASELINE_SHA = (
    "723579250e692112d4208ae56c0eede15f422858b3f99cc9cd2af1639599d93d")
BASELINE_RECEIPT = EVIDENCE / (
    "c2.2-product-link56-selector-tail-z-structural-receipt.json")
BASELINE_RECEIPT_SHA = (
    "81b45bb16c4b4d5861aafd1dd44e1b76a98111818eba4e62e472163c1b485d7b")
ATTRIBUTION = EVIDENCE / (
    "c2.2-link57-top-level-frame-attribution-hardware-receipt.json")
ATTRIBUTION_SHA = (
    "b4bf579f325a3976b58ba51219981403e40aaa6eb0674f3e1cbc10c8d9ee6ce3")
LATENCY = ROOT / (
    "build/c2.2/hardware-presmoke-link56-selector-tail-z/latency/result.json")
LATENCY_SHA = (
    "800b96bfee2066749e9895dd56a3ca74f32bdcb26d43c3c65e97f7725c042939")
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


class Link57Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise Link57Error(message)


def validate_authority() -> dict[str, Any]:
    for path, digest in {
            WPLTO: WPLTO_SHA,
            BASELINE: BASELINE_SHA,
            BASELINE_RECEIPT: BASELINE_RECEIPT_SHA,
            ATTRIBUTION: ATTRIBUTION_SHA,
            LATENCY: LATENCY_SHA,
            }.items():
        require(path.is_file() and L.sha(path) == digest,
                f"Link-57 authority SHA drift: {path}")
    qualified = json.loads(WPLTO.read_text(encoding="utf-8"))
    replay = qualified["fresh_read_only_replay"]
    baseline = json.loads(BASELINE_RECEIPT.read_text(encoding="utf-8"))
    attribution = json.loads(ATTRIBUTION.read_text(encoding="utf-8"))
    latency = json.loads(LATENCY.read_text(encoding="utf-8"))
    require(
        qualified["status"] ==
            "passed-keymap-plus-published-nullary-WPLTO-all-walls-green"
        and not qualified["promotable"]
        and qualified["execution_accounting"]["compiler_runs"] == 0
        and qualified["execution_accounting"]["linker_runs"] == 0
        and replay["walls"] == {
            "bank0_text_headroom_bytes": 38,
            "ordinary_bank0_bss_headroom_bytes": 213,
            "fixed_hot_block_headroom_bytes": 33,
            "resident_island_headroom_bytes": 5,
            "e000_headroom_bytes": 58}
        and replay["capacity"]["session_family_bytes"] == 65438
        and replay["capacity"]["session_family_headroom_bytes"] == 98
        and qualified["published_nullary_call"][
            "static_bank2_delta_bytes"] == 33
        and qualified["published_nullary_call"][
            "resident_product_delta_bytes"] == 0
        and qualified["queue_to_action_gate"]["mutations_rejected"] == 10
        and baseline["status"] ==
            "passed-selector-tail-Z0-product-identity-hardware-not-run"
        and baseline["product_identity"]["product"]["sha256"] == BASELINE_SHA
        and attribution["conclusions"]["whole_plane_crc_dominates"] is False
        and attribution["conclusions"]["single_station_dominates"] is False
        and latency["measurement"]["definition_first_call"]["frames"] == 60
        and latency["measurement"]["warm_second_call"]["frames"] == 61,
        "Link-57 keymap/nullary authority is incomplete",
    )
    BASE.BASE.profile_features()
    return qualified


def main() -> int:
    require(not OUT.exists() and not RECEIPT.exists(), "Link 57 is one-shot")
    validate_authority()
    base_names = (
        "LINK_NUMBER", "OUT", "RECEIPT", "WPLTO", "WPLTO_SHA",
        "WPLTO_AUTHORITY", "WPLTO_AUTHORITY_SHA", "WPLTO_SOURCE",
        "WPLTO_PROFILE", "BASELINE", "BASELINE_SHA", "BASELINE_RECEIPT",
        "BASELINE_RECEIPT_SHA", "validate_authority",
    )
    old_base = {name: getattr(BASE, name) for name in base_names}
    old_product = PRODUCT.PRODUCT_ARTIFACTS_MANIFEST
    old_v6 = (
        V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS)
    old_sub = SUB.SPECS
    try:
        BASE.LINK_NUMBER = LINK_NUMBER
        BASE.OUT = OUT
        BASE.RECEIPT = RECEIPT
        BASE.WPLTO = WPLTO
        BASE.WPLTO_SHA = WPLTO_SHA
        BASE.WPLTO_AUTHORITY = WPLTO
        BASE.WPLTO_AUTHORITY_SHA = WPLTO_SHA
        BASE.WPLTO_SOURCE = WPLTO_SOURCE
        BASE.WPLTO_PROFILE = WPLTO_PROFILE
        BASE.BASELINE = BASELINE
        BASE.BASELINE_SHA = BASELINE_SHA
        BASE.BASELINE_RECEIPT = BASELINE_RECEIPT
        BASE.BASELINE_RECEIPT_SHA = BASELINE_RECEIPT_SHA
        BASE.validate_authority = validate_authority
        PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = PRODUCT_IDENTITY
        V6.PRODUCT_IDENTITY = PRODUCT_IDENTITY
        V6.STATIC_CODE_BYTES = 34542
        V6.A.SPECS = SPECS
        SUB.SPECS = SPECS
        result = BASE.main()
    finally:
        for name, value in old_base.items():
            setattr(BASE, name, value)
        PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = old_product
        V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS = old_v6
        SUB.SPECS = old_sub
    if result != 0:
        return result

    os.chmod(RECEIPT, 0o644)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    c2d = OUT / (
        "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
    gates = receipt["fresh_replacement_gates"]
    walls = gates["walls"]
    capacity = gates["capacity"]

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
    zero = ZERO.linked_gate(elf, c2d)
    old_identity = PROFILE_GATE.PRODUCT_IDENTITY
    try:
        PROFILE_GATE.PRODUCT_IDENTITY = PRODUCT_IDENTITY
        artifact_profile = PROFILE_GATE.canonical_artifact_profile_gate(OUT)
    finally:
        PROFILE_GATE.PRODUCT_IDENTITY = old_identity
    resolved = (OUT / "resolved-profile.txt").read_text(encoding="utf-8")

    require(
        receipt["link_number"] == LINK_NUMBER
        and L.sha(product) != BASELINE_SHA
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["ordinary_bank0_bss_headroom_bytes"] == 213
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_family_bytes"] == 65438
        and capacity["session_family_headroom_bytes"] == 98
        and plane["static_code_bytes"] == 34542
        and plane["mutations_rejected"] == 6
        and keymap["mutations_rejected"] == 10
        and direct["mutations_rejected"] == 7
        and execution["direct"]["compiler_calls"] == 0
        and execution["direct"]["install_calls"] == 0
        and zero["status"] ==
            "passed-linked-vm-run-dir-zero-literal-chain"
        and artifact_profile["status"] ==
            "passed-one-canonical-artifact-profile"
        and artifact_profile["compiled_shelf_bytes"] == 71194
        and "LISP65_C2_FRAME_ATTRIBUTION_DIAGNOSTIC" not in resolved,
        "Link-57 final keymap/nullary qualification red",
    )
    receipt["format"] = "lisp65-c2-lite-v6-link57-keymap-nullary-v1"
    receipt["status"] = (
        "passed-keymap-and-published-nullary-product-identity-hardware-not-run")
    receipt["authority"]["link56_rollback_product"] = {
        **L.bind(BASELINE), "status": "untouched"}
    receipt["authority"]["qualified_keymap_nullary_WPLTO"] = L.bind(WPLTO)
    receipt["authority"]["canonical_c2_product_artifacts"] = L.bind(
        PRODUCT_IDENTITY)
    receipt["authority"]["frame_attribution_hardware"] = L.bind(ATTRIBUTION)
    receipt["authority"]["latency_attempt_1"] = L.bind(LATENCY)
    receipt["keymap_and_published_nullary"] = {
        "static_plane_gate": plane,
        "canonical_artifact_profile_gate": artifact_profile,
        "keymap_end_to_end_gate": keymap,
        "published_nullary_source_gate": direct,
        "published_nullary_execution_gate": execution,
        "zero_literal_linked_gate": zero,
        "static_bank2_delta_bytes": 33,
        "resident_product_delta_bytes": 0,
        "frame_attribution_diagnostic_present": False,
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
        "completed_latency_measurements": "1/2",
        "latency_attempt_2_consumed": False,
    }
    receipt["execution_accounting"]["latency_attempts_consumed"] = "1/2"
    receipt["next_gate"] = (
        "authorized hardware measurement attempt 2: boot, definition/cold "
        "nullary call, immediate warm nullary call, informative published "
        "argument call without limit, then remaining C2-lite presmoke rows")
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-link57-keymap-nullary: COMPLETE "
        f"product={L.sha(product)} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_bytes']} "
        "hardware=not-run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        Link57Error,
        BASE.Link56Error,
        KEYGATE.GateError,
        KEYGATE.KEYMAP.KeymapError,
        DIRECT.GateError,
        ZERO.GateError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-link57-keymap-nullary: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
