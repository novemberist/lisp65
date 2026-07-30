#!/usr/bin/env python3
"""Prepare and run the one authorized combined fx+time v1.2.4 WPLTO card."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v123_candidate_product as LINK80  # noqa: E402
import c2_v124_time_gate as TIME  # noqa: E402


PRODUCT = LINK80.PRODUCT
V = PRODUCT.V
BASE = PRODUCT.BASE
CAN = PRODUCT.CAN
BUILD = ROOT / "build/post-promotion/v124/time/product-shaped-wplto"
PREFLIGHT = ROOT / "build/post-promotion/v124/time/profile-preflight"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / "c2.2-v1.2.4-time-wplto-receipt.json"
FIRST_RED = EVIDENCE / "c2.2-v1.2.4-time-wplto-first-red.json"
PROFILE_RECEIPT = EVIDENCE / (
    "c2.2-v1.2.4-time-profile-preflight-receipt.json")
HOST_RECEIPT = EVIDENCE / "c2.2-v1.2.4-time-host-first-receipt.json"
FX_WPLTO = EVIDENCE / "c2.2-v1.2.4-fx-wplto-receipt.json"
PHASE_M = EVIDENCE / "c2.2-v1.2.4-phase-m-hardware-receipt.json"
PREDECESSOR = EVIDENCE / "c2.2-v1.2.3-phase-b-link80-receipt.json"
TIME_MANIFEST = TIME.CANDIDATE_PREFIX.with_suffix(".manifest.json")
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
STATIC_HEADER = ROOT / "src/c2_lite_static_plane.h"
EXPECTED_STATIC = 43218
EXPECTED_ENTRIES = 725
EXPECTED_RESOLUTIONS = 2843
EXPECTED_ROOTS = 340
EXPECTED_DIRECT_REFS = 656
DRIVER = Path(__file__).resolve()


class WPLTOError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise WPLTOError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    return CAN.bind(path)


def configure(build: Path = BUILD) -> dict[str, Path]:
    V.RANDOM_MANIFEST = TIME_MANIFEST
    V.EXPECTED_STATIC = EXPECTED_STATIC
    V.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    V.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    V.EXPECTED_ROOTS = EXPECTED_ROOTS
    V.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    V.configure_candidate()
    BASE.LINK = 81
    BASE.EXPECTED_STATIC = EXPECTED_STATIC
    BASE.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    BASE.ROOT_BUILD = build
    BASE.PROBE_BUILD = build
    BASE.LINK_BUILD = build
    BASE.WPLTO_RECEIPT = RECEIPT
    BASE.LINK_RECEIPT = RECEIPT
    BASE.LINK69 = PREDECESSOR
    BASE.EVIDENCE = EVIDENCE
    BASE.DRIVER = DRIVER
    paths = BASE.configure(build)
    V.bind_candidate_specs()
    os.environ.update(CAN.canonical_build_environment())
    return paths


def emit_profile_plane() -> dict[str, Any]:
    """Produce the final static data without invoking the target linker."""
    paths = configure(PREFLIGHT)
    specs = tuple(CAN.SPECS)
    require(
        len(specs) == 6 and specs[0][2] == TIME_MANIFEST
        and all(path.is_file() for _key, _name, path in specs),
        "time preflight manifest inventory incomplete",
    )
    product_out = paths["static_product"]
    semantics_out = paths["v6"]
    old_sub = (CAN.SUBSTITUTION.BUILD, CAN.SUBSTITUTION.SPECS)
    old_v6 = (
        CAN.V6.OUT, CAN.V6.PRODUCT_IDENTITY,
        CAN.V6.STATIC_CODE_BYTES, CAN.V6.A.SPECS,
    )
    try:
        CAN.SUBSTITUTION.BUILD = product_out
        CAN.SUBSTITUTION.SPECS = specs
        product = CAN.SUBSTITUTION.build()
        CAN.V6.OUT = semantics_out
        CAN.V6.PRODUCT_IDENTITY = (
            product_out / "substitution-artifacts.json")
        CAN.V6.STATIC_CODE_BYTES = EXPECTED_STATIC
        CAN.V6.A.SPECS = specs
        semantics_out.mkdir(parents=True, exist_ok=True)
        semantics = CAN.V6.host_semantics()
    finally:
        CAN.SUBSTITUTION.BUILD, CAN.SUBSTITUTION.SPECS = old_sub
        (
            CAN.V6.OUT, CAN.V6.PRODUCT_IDENTITY,
            CAN.V6.STATIC_CODE_BYTES, CAN.V6.A.SPECS,
        ) = old_v6
    bank2 = semantics["static_bank2"]
    bank2_path = semantics_out / "bank2-static-code.bin"
    bank2_sha256 = hashlib.sha256(bank2_path.read_bytes()).hexdigest()
    require(
        product["images"] == 6
        and product["entries"] == EXPECTED_ENTRIES
        and product["resolutions"] == EXPECTED_RESOLUTIONS
        and product["roots"] == EXPECTED_ROOTS
        and bank2["code_bytes"] == EXPECTED_STATIC,
        "time preflight static geometry drift",
    )
    return {
        "specs": specs,
        "product": product,
        "semantics": semantics,
        "bank2": {**bank2, "sha256": bank2_sha256},
    }


def write_profile() -> int:
    require(not PROFILE_RECEIPT.exists(),
            "time profile preflight is one-shot")
    result = TIME.main()
    require(result == 0, "time host-first gate red")
    plane = emit_profile_plane()
    product = plane["product"]
    bank2 = plane["bank2"]
    profile = load(PROFILE)
    profile.update({
        "recorded_on": "2026-07-30",
        "authority": {
            "kind": "fresh-single-emitter-static-plane-dataflow",
            "emitter": "tools/host-lisp/c2_lite_canonical_product.py",
            "product_manifest": (
                "build/post-promotion/v124/time/product-shaped-wplto/"
                "static-plane/narrow-static/product/"
                "substitution-artifacts.json"
            ),
            "compiled_ide_manifest": (
                "build/c2.2/substitution/published-nullary-call-"
                "bytecode-artifacts/libs/ide.manifest.json"
            ),
            "bank2_static_plane": (
                "build/post-promotion/v124/time/product-shaped-wplto/"
                "static-plane/narrow-static/v6-semantics/"
                "bank2-static-code.bin"
            ),
            "manifest_source_bindings": (
                "build/post-promotion/v124/time/product-shaped-wplto/"
                "receipts/bound-artifact-manifest-source-bindings.json"
            ),
            "rule": (
                "The gate derives identity from the freshly emitted "
                "single-emitter artifacts. Historical private receipts are "
                "acceptance evidence, never clean-build inputs."
            ),
        },
        "product_build_id": product["product_build_id_hex"],
        "images": 6,
        "entries": EXPECTED_ENTRIES,
        "resolutions": EXPECTED_RESOLUTIONS,
        "roots": EXPECTED_ROOTS,
        "direct_entry_refs": EXPECTED_DIRECT_REFS,
        "bank2_static_code": {
            "bytes": EXPECTED_STATIC,
            "sha256": bank2["sha256"],
            "headroom_bytes": 65536 - EXPECTED_STATIC,
        },
        "time_base_delta": {
            "baseline": "v1.2.4 fx candidate",
            "stdlib_code_bytes": 282,
            "new_entries": 3,
            "new_resolutions": 12,
            "new_roots": 0,
            "new_direct_entry_refs": 0,
            "resident_bytes": 0,
            "native_primitives": 0,
            "contract": "config/c2-time-contract.json",
        },
    })
    PROFILE.write_bytes(CAN.json_bytes(profile))
    header = STATIC_HEADER.read_text(encoding="utf-8")
    updated, count = re.subn(
        r"(#define LISP65_C2_LITE_STATIC_CODE_BYTES )\d+(UL)",
        rf"\g<1>{EXPECTED_STATIC}\2",
        header,
    )
    require(count == 1, "static-plane byte pin not found exactly once")
    STATIC_HEADER.write_text(updated, encoding="utf-8")
    value = {
        "format": "lisp65-c2.2-v1.2.4-time-profile-preflight-v1",
        "recorded_on": "2026-07-30",
        "status": "passed-linker-free-final-static-profile-preflight",
        "target_linker_invocations": 0,
        "geometry": {
            "bank2_static_code_bytes": EXPECTED_STATIC,
            "bank2_headroom_bytes": 65536 - EXPECTED_STATIC,
            "entries": EXPECTED_ENTRIES,
            "resolutions": EXPECTED_RESOLUTIONS,
            "roots": EXPECTED_ROOTS,
            "direct_entry_refs": EXPECTED_DIRECT_REFS,
            "product_build_id": product["product_build_id_hex"],
            "bank2_sha256": bank2["sha256"],
        },
        "authority": {
            "time_host": bind(HOST_RECEIPT),
            "time_manifest": bind(TIME_MANIFEST),
            "profile": bind(PROFILE),
            "static_header": bind(STATIC_HEADER),
            "driver": bind(DRIVER),
            "preflight_product":
                bind(PREFLIGHT / "static-plane/narrow-static/product/"
                     "substitution-artifacts.json"),
            "preflight_bank2":
                bind(PREFLIGHT / "static-plane/narrow-static/v6-semantics/"
                     "bank2-static-code.bin"),
        },
        "next_gate": "The single authorized combined fx+time WPLTO.",
        "claim_limit": (
            "Linker-free static-plane emission and tracked profile/header "
            "binding only; no WPLTO, product link or hardware claim."
        ),
    }
    PROFILE_RECEIPT.write_bytes(CAN.json_bytes(value))
    print(
        "c2-v124-time-profile: PASS "
        f"bank2={EXPECTED_STATIC} headroom={65536 - EXPECTED_STATIC} "
        f"entries={EXPECTED_ENTRIES} linker=0"
    )
    return 0


def run_wplto() -> int:
    require(
        not RECEIPT.exists()
        and not (BUILD / "wplto").exists()
        and not (BUILD / "final").exists(),
        "v1.2.4 time WPLTO is a one-shot card",
    )
    profile_preflight = load(PROFILE_RECEIPT)
    host_result = TIME.main()
    require(host_result == 0, "time host-first replay red")
    host = load(HOST_RECEIPT)
    fx = load(FX_WPLTO)
    phase_m = load(PHASE_M)
    require(
        profile_preflight["status"]
            == "passed-linker-free-final-static-profile-preflight"
        and profile_preflight["target_linker_invocations"] == 0
        and host["status"] == "passed-time-host-reference-and-admission"
        and host["artifacts"]["delta"]["bank2_code_bytes"] == 282
        and fx["status"] == "passed-fx-one-product-shaped-WPLTO"
        and phase_m["M3_fx"]["status"]
            == "passed-target-multiply-divide-rounding-smoke"
        and phase_m["M4_time"]["status"] == "passed-50Hz-calibration"
        and 48 <= phase_m["M4_time"]["frames_per_second"] <= 52,
        "time WPLTO predecessor/measurement authority drift",
    )
    paths = configure(BUILD)
    static = BASE.PROBE.REQ.build_static_plane()
    plane = BASE.PROBE.REQ.F1W.static_gate()
    header = PRODUCT.bind_generated_stdlib_header(paths)
    product_path = (
        paths["static_product"] / "substitution-artifacts.json")
    product = load(product_path)
    profile = load(PROFILE)
    require(
        static["semantics"]["code_bytes"] == EXPECTED_STATIC
        and plane["static_code_bytes"] == EXPECTED_STATIC
        and product["images"] == 6
        and product["entries"] == EXPECTED_ENTRIES
        and product["resolutions"] == EXPECTED_RESOLUTIONS
        and product["roots"] == EXPECTED_ROOTS
        and profile["direct_entry_refs"] == EXPECTED_DIRECT_REFS
        and profile["bank2_static_code"]["bytes"] == EXPECTED_STATIC
        and profile["time_base_delta"]["stdlib_code_bytes"] == 282,
        "time single-emitter static-plane identity drift",
    )
    V.EXPECTED_PRODUCT_ID = product["product_build_id_hex"]
    V.EXPECTED_BANK2_SHA = profile["bank2_static_code"]["sha256"]
    wplto = CAN.run_wplto()
    replacement = wplto["historical_checker_boundary"][
        "current_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    predecessor = load(PREDECESSOR)
    old_walls = predecessor["qualifying_candidate"]["walls"]
    require(
        walls["bank0_text_headroom_bytes"]
            == old_walls["bank0_text_headroom_bytes"]
        and walls["e000_headroom_bytes"]
            == old_walls["e000_headroom_bytes"]
        and walls["fixed_hot_block_headroom_bytes"]
            == old_walls["fixed_hot_block_headroom_bytes"]
        and walls["ordinary_bank0_bss_headroom_bytes"]
            == old_walls["ordinary_bank0_bss_headroom_bytes"]
        and walls["resident_island_headroom_bytes"]
            == old_walls["resident_island_headroom_bytes"]
        and capacity["session_family_headroom_bytes"]
            == old_walls["session_family_headroom_bytes"]
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_family_headroom_bytes"] >= 0,
        "time WPLTO moved a closed resident/session wall",
    )
    elf = paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf"
    require(elf.is_file(), "time WPLTO linked ELF absent")
    value = {
        "format": "lisp65-c2.2-v1.2.4-time-WPLTO-v1",
        "recorded_on": "2026-07-30",
        "status": "passed-combined-fx-time-one-product-shaped-WPLTO",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "wplto_probes_consumed": 1,
        "pre_wplto_first_red": bind(FIRST_RED),
        "profile_preflight": bind(PROFILE_RECEIPT),
        "predecessor": bind(PREDECESSOR),
        "fx_wplto": bind(FX_WPLTO),
        "phase_m": bind(PHASE_M),
        "time_host": bind(HOST_RECEIPT),
        "static_geometry": {
            "bank2_static_code_bytes": EXPECTED_STATIC,
            "bank2_delta_from_Link80_bytes": 1733,
            "time_delta_from_fx_bytes": 282,
            "bank2_headroom_bytes": 65536 - EXPECTED_STATIC,
            "entries": EXPECTED_ENTRIES,
            "resolutions": EXPECTED_RESOLUTIONS,
            "roots": EXPECTED_ROOTS,
            "direct_entry_refs": EXPECTED_DIRECT_REFS,
            "product_build_id": product["product_build_id_hex"],
            "bank2_sha256": profile["bank2_static_code"]["sha256"],
        },
        "target_stdlib_header": header,
        "walls": walls,
        "capacity": capacity,
        "wplto": wplto,
        "authority": {
            "contract": bind(TIME.CONTRACT),
            "source": bind(TIME.SOURCE),
            "candidate_manifest": bind(TIME_MANIFEST),
            "profile": bind(PROFILE),
            "static_product": bind(product_path),
            "linked_ELF": bind(elf),
            "driver": bind(DRIVER),
        },
        "next_gate": "The owner-authorized v1.2.4 successor product link.",
        "claim_limit": (
            "One non-promotable combined fx+time WPLTO, with no successor "
            "product identity or release claim."
        ),
    }
    RECEIPT.write_bytes(CAN.json_bytes(value))
    print(
        "c2-v124-time-wplto: PASS "
        f"bank2={EXPECTED_STATIC} headroom={65536 - EXPECTED_STATIC} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_headroom_bytes']} links=0"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("profile", "wplto"))
    args = parser.parse_args()
    return write_profile() if args.action == "profile" else run_wplto()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (WPLTOError, KeyError, OSError, ValueError) as error:
        print(f"c2-v124-time-wplto: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
