#!/usr/bin/env python3
"""Bind and price the joint v1.3 Ship/public-surface/editor freight."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import c2_v126_editor_wplto as PREV  # noqa: E402
import c2_ship_input_wait_gate as INPUT  # noqa: E402


V = PREV.V
BASE = PREV.BASE
CAN = PREV.CAN
PRODUCT = PREV.PRODUCT
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/ship-builder/v13/joint-product-shaped-wplto"
PREFLIGHT = ROOT / "build/ship-builder/v13/joint-profile-preflight"
RECEIPT = EVIDENCE / "c2.3-v1.3-ship-joint-wplto-receipt.json"
PROFILE_RECEIPT = EVIDENCE / "c2.3-v1.3-ship-joint-profile-receipt.json"
INPUT_RECEIPT = EVIDENCE / (
    "c2.2-v1.3-ship-input-wait-host-first-receipt.json")
Q_RECEIPT = EVIDENCE / "c2.2-v1.3-q-host-first-receipt.json"
EDITOR_RECEIPT = EVIDENCE / "c2-v126-editor-allocation-gate-receipt.json"
PREDECESSOR = EVIDENCE / "c2.2-v1.2.6-editor-wplto-receipt.json"
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
STATIC_HEADER = ROOT / "src/c2_lite_static_plane.h"
EXECUTION_CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
CURRENT_IDE = ROOT / "build/bytecode/dialect-v2/libs/ide.manifest.json"
BASELINE_STDLIB = INPUT.BASE_PREFIX.with_suffix(".manifest.json")
INPUT_MANIFEST = INPUT.CANDIDATE_PREFIX.with_suffix(".manifest.json")
EXPECTED_STATIC = 45318
EXPECTED_ENTRIES = 755
EXPECTED_RESOLUTIONS = 2944
EXPECTED_ROOTS = 350
EXPECTED_DIRECT_REFS = 710
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


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout.strip().splitlines()[-1]


def bind_current_specs() -> None:
    req = BASE.PROBE.REQ
    specs = tuple(
        (
            key,
            name,
            INPUT_MANIFEST if key == "stdlib-p0"
            else CURRENT_IDE if key == "ide" else path,
        )
        for key, name, path in req.SPECS
    )
    require(
        len(specs) == 6
        and sum(key == "stdlib-p0" for key, _name, _path in specs) == 1
        and sum(key == "ide" for key, _name, _path in specs) == 1,
        "canonical six-image inventory lacks unique stdlib/IDE roles",
    )
    req.SPECS = specs
    req.EXPECTED_STATIC = EXPECTED_STATIC
    req.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    req.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    req.EXPECTED_ROOTS = EXPECTED_ROOTS
    req.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    req.F1W.SPECS = specs
    req.F1W.EXPECTED_STATIC = EXPECTED_STATIC
    req.F1W.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    req.F1W.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    req.F1W.EXPECTED_ROOTS = EXPECTED_ROOTS
    CAN.SPECS = specs
    CAN.PREFIXES = tuple(
        (
            path.with_suffix(""),
            "stdlib" if index == 0 else "disk-lib",
            None if index == 0 else "0x000000",
        )
        for index, (_key, _name, path) in enumerate(specs)
    )


def configure(build: Path) -> dict[str, Path]:
    V.RANDOM_MANIFEST = INPUT_MANIFEST
    V.EXPECTED_STATIC = EXPECTED_STATIC
    V.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    V.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    V.EXPECTED_ROOTS = EXPECTED_ROOTS
    V.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    V.configure_candidate()
    BASE.LINK = 84
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
    bind_current_specs()
    # BASE.configure installs the historical IDE before the successor specs
    # are selected.  Bind the static-plane validator to the same six current
    # manifests as the canonical emitter; otherwise it compares the new
    # product identity to a predecessor IDE path.
    plane_gate = BASE.PROBE.REQ.F1W.PLANE
    plane_gate.FRESH_PRODUCT = (
        paths["static_product"] / "substitution-artifacts.json")
    plane_gate.FRESH_IDE = CURRENT_IDE
    plane_gate.FRESH_BANK2 = paths["v6"] / "bank2-static-code.bin"
    plane_gate.FRESH_MANIFESTS = tuple(
        path for _key, _name, path in CAN.SPECS)
    os.environ.update(CAN.canonical_build_environment())
    return paths


def freight_delta() -> dict[str, int]:
    old = load(BASELINE_STDLIB)
    new = load(INPUT_MANIFEST)
    old_direct = sum(row["kind"] == 4 for row in old["literal_nodes"])
    new_direct = sum(row["kind"] == 4 for row in new["literal_nodes"])
    value = {
        "bank2_code_bytes": new["code_bytes"] - old["code_bytes"],
        "entries": len(new["entries"]) - len(old["entries"]),
        "resolution_words": (
            len(new["literal_patches"]) - len(old["literal_patches"])),
        "stdlib_kind4_literal_nodes": new_direct - old_direct,
        "direct_entry_refs": 0,
        "roots": 0,
    }
    require(
        value == {
            "bank2_code_bytes": 255,
            "entries": 5,
            "resolution_words": 13,
            "stdlib_kind4_literal_nodes": 11,
            "direct_entry_refs": 0,
            "roots": 0,
        },
        f"joint freight delta drift: {value}",
    )
    return value


def host_gates() -> dict[str, str]:
    return {
        "input_wait": run(
            [sys.executable, "tools/host-lisp/c2_ship_input_wait_gate.py"],
            "input/wait gate",
        ),
        "q": run(
            [sys.executable, "tools/host-lisp/c2_q_gate.py"],
            "q gate",
        ),
        "editor": run(
            [sys.executable,
             "tools/host-lisp/c2_v126_editor_allocation_gate.py", "check"],
            "editor allocation gate",
        ),
        "surface": run(
            [sys.executable,
             "tools/host-lisp/v11_surface_delivery_parity.py"],
            "surface-delivery parity",
        ),
    }


def emit_plane() -> dict[str, Any]:
    paths = configure(PREFLIGHT)
    specs = tuple(CAN.SPECS)
    old_sub = (CAN.SUBSTITUTION.BUILD, CAN.SUBSTITUTION.SPECS)
    old_v6 = (
        CAN.V6.OUT,
        CAN.V6.PRODUCT_IDENTITY,
        CAN.V6.STATIC_CODE_BYTES,
        CAN.V6.A.SPECS,
    )
    try:
        CAN.SUBSTITUTION.BUILD = paths["static_product"]
        CAN.SUBSTITUTION.SPECS = specs
        product = CAN.SUBSTITUTION.build()
        CAN.V6.OUT = paths["v6"]
        CAN.V6.PRODUCT_IDENTITY = (
            paths["static_product"] / "substitution-artifacts.json")
        CAN.V6.STATIC_CODE_BYTES = EXPECTED_STATIC
        CAN.V6.A.SPECS = specs
        paths["v6"].mkdir(parents=True, exist_ok=True)
        semantics = CAN.V6.host_semantics()
    finally:
        CAN.SUBSTITUTION.BUILD, CAN.SUBSTITUTION.SPECS = old_sub
        (
            CAN.V6.OUT,
            CAN.V6.PRODUCT_IDENTITY,
            CAN.V6.STATIC_CODE_BYTES,
            CAN.V6.A.SPECS,
        ) = old_v6
    bank2_path = paths["v6"] / "bank2-static-code.bin"
    require(
        product["images"] == 6
        and product["entries"] == EXPECTED_ENTRIES
        and product["resolutions"] == EXPECTED_RESOLUTIONS
        and product["roots"] == EXPECTED_ROOTS
        and semantics["static_bank2"]["code_bytes"] == EXPECTED_STATIC,
        "joint preflight static geometry drift",
    )
    return {
        "paths": paths,
        "product": product,
        "semantics": semantics,
        "bank2_sha256": hashlib.sha256(bank2_path.read_bytes()).hexdigest(),
    }


def profile() -> int:
    require(
        not PREFLIGHT.exists() and not PROFILE_RECEIPT.exists(),
        "v1.3 joint profile emission is one-shot",
    )
    gates = host_gates()
    delta = freight_delta()
    plane = emit_plane()
    product = plane["product"]
    value = load(PROFILE)
    value.update({
        "recorded_on": "2026-08-01",
        "authority": {
            "kind": "fresh-single-emitter-static-plane-dataflow",
            "emitter": "tools/host-lisp/c2_lite_canonical_product.py",
            "product_manifest": (
                "build/ship-builder/v13/joint-profile-preflight/"
                "static-plane/narrow-static/product/"
                "substitution-artifacts.json"),
            "compiled_stdlib_manifest": INPUT_MANIFEST.relative_to(ROOT).as_posix(),
            "compiled_ide_manifest": CURRENT_IDE.relative_to(ROOT).as_posix(),
            "bank2_static_plane": (
                "build/ship-builder/v13/joint-profile-preflight/"
                "static-plane/narrow-static/v6-semantics/"
                "bank2-static-code.bin"),
            "rule": (
                "The v1.3 card binds the q/time/input/wait base composition "
                "and the Link-83 editor at the canonical six-image producer."),
        },
        "product_build_id": product["product_build_id_hex"],
        "images": 6,
        "entries": EXPECTED_ENTRIES,
        "resolutions": EXPECTED_RESOLUTIONS,
        "roots": EXPECTED_ROOTS,
        "direct_entry_refs": EXPECTED_DIRECT_REFS,
        "bank2_static_code": {
            "bytes": EXPECTED_STATIC,
            "sha256": plane["bank2_sha256"],
            "headroom_bytes": 65536 - EXPECTED_STATIC,
        },
        "v13_ship_public_surface_delta": {
            **delta,
            "baseline": "Link 83 editor static plane",
            "contracts": [
                "config/c2-q-contract.json",
                "config/c2-time-contract.json",
                "config/c2-ship-input-wait-contract.json",
            ],
            "resident_bytes": 0,
            "native_primitives": 0,
        },
    })
    PROFILE.write_bytes(CAN.json_bytes(value))
    execution = load(EXECUTION_CONTRACT)
    execution["physical_planes"]["code"].update({
        "static_use_bytes": EXPECTED_STATIC,
        "gross_headroom_bytes": 65536 - EXPECTED_STATIC,
    })
    EXECUTION_CONTRACT.write_bytes(CAN.json_bytes(execution))
    source = STATIC_HEADER.read_text(encoding="utf-8")
    source, count = re.subn(
        r"(#define LISP65_C2_LITE_STATIC_CODE_BYTES )\d+(UL)",
        rf"\g<1>{EXPECTED_STATIC}\2",
        source,
    )
    require(count == 1, "static-plane byte pin not found exactly once")
    STATIC_HEADER.write_text(source, encoding="utf-8")
    # The q gate binds the current product profile in its receipt.  Replay it
    # after profile publication so the joint receipt never captures the
    # predecessor profile merely because q was also a preflight prerequisite.
    gates["q_post_profile"] = run(
        [sys.executable, "tools/host-lisp/c2_q_gate.py"],
        "post-profile q binding",
    )
    receipt = {
        "format": "lisp65-c2.3-v1.3-ship-joint-profile-v1",
        "recorded_on": "2026-08-01",
        "status": "passed-v1.3-joint-linker-free-profile",
        "target_linker_invocations": 0,
        "geometry": {
            "bank2_static_code_bytes": EXPECTED_STATIC,
            "bank2_headroom_bytes": 65536 - EXPECTED_STATIC,
            "entries": EXPECTED_ENTRIES,
            "resolutions": EXPECTED_RESOLUTIONS,
            "roots": EXPECTED_ROOTS,
            "direct_entry_refs": EXPECTED_DIRECT_REFS,
            "product_build_id": product["product_build_id_hex"],
            "bank2_sha256": plane["bank2_sha256"],
            "delta": delta,
        },
        "host_gate_summaries": gates,
        "authority": {
            "input_wait": bind(INPUT_RECEIPT),
            "q": bind(Q_RECEIPT),
            "editor": bind(EDITOR_RECEIPT),
            "stdlib_manifest": bind(INPUT_MANIFEST),
            "ide_manifest": bind(CURRENT_IDE),
            "profile": bind(PROFILE),
            "static_header": bind(STATIC_HEADER),
            "execution_contract": bind(EXECUTION_CONTRACT),
            "driver": bind(DRIVER),
        },
        "claim_limit": (
            "Linker-free profile binding only; no product link, hardware "
            "or release claim."),
    }
    PROFILE_RECEIPT.write_bytes(CAN.json_bytes(receipt))
    print(
        "c2-v13-ship-profile: PASS "
        f"bank2={EXPECTED_STATIC} delta=+{delta['bank2_code_bytes']} "
        f"headroom={65536 - EXPECTED_STATIC} linker=0")
    return 0


def wplto() -> int:
    require(
        PROFILE_RECEIPT.is_file()
        and not BUILD.exists()
        and not RECEIPT.exists(),
        "v1.3 joint WPLTO is one-shot after profile emission",
    )
    gates = host_gates()
    preflight = load(PROFILE_RECEIPT)
    profile_value = load(PROFILE)
    require(
        preflight["status"] == "passed-v1.3-joint-linker-free-profile"
        and profile_value["bank2_static_code"]["bytes"] == EXPECTED_STATIC
        and profile_value["bank2_static_code"]["sha256"]
            == preflight["geometry"]["bank2_sha256"],
        "joint profile authority drift",
    )
    paths = configure(BUILD)
    static = BASE.PROBE.REQ.build_static_plane()
    plane = BASE.PROBE.REQ.F1W.static_gate()
    header_binding = PRODUCT.bind_generated_stdlib_header(paths)
    product_path = paths["static_product"] / "substitution-artifacts.json"
    product = load(product_path)
    require(
        static["semantics"]["code_bytes"] == EXPECTED_STATIC
        and plane["static_code_bytes"] == EXPECTED_STATIC
        and product["entries"] == EXPECTED_ENTRIES
        and product["resolutions"] == EXPECTED_RESOLUTIONS
        and product["roots"] == EXPECTED_ROOTS
        and product["product_build_id_hex"] == profile_value["product_build_id"],
        "joint WPLTO static-plane identity drift",
    )
    V.EXPECTED_PRODUCT_ID = profile_value["product_build_id"]
    V.EXPECTED_BANK2_SHA = profile_value["bank2_static_code"]["sha256"]
    linked = CAN.run_wplto()
    replacement = linked["historical_checker_boundary"]["current_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    predecessor = load(PREDECESSOR)
    old_walls = predecessor["walls"]
    wall_delta = {
        key: walls[key] - old_walls[key]
        for key in (
            "bank0_text_headroom_bytes",
            "e000_headroom_bytes",
            "fixed_hot_block_headroom_bytes",
            "ordinary_bank0_bss_headroom_bytes",
            "resident_island_headroom_bytes",
        )
    }
    require(
        walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and capacity["session_family_headroom_bytes"] >= 0,
        "joint v1.3 freight crossed a closed product wall",
    )
    elf = paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf"
    require(elf.is_file(), "joint WPLTO linked ELF absent")
    receipt = {
        "format": "lisp65-c2.3-v1.3-ship-joint-WPLTO-v1",
        "recorded_on": "2026-08-01",
        "status": "passed-v1.3-joint-one-product-shaped-WPLTO",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "wplto_probes_consumed": 1,
        "predecessor": bind(PREDECESSOR),
        "profile_preflight": bind(PROFILE_RECEIPT),
        "host_gate_summaries": gates,
        "static_geometry": preflight["geometry"],
        "target_stdlib_header": header_binding,
        "walls": walls,
        "wall_headroom_delta_from_link83": wall_delta,
        "capacity": capacity,
        "wplto": linked,
        "authority": {
            "input_wait_contract": bind(INPUT.CONTRACT),
            "q_contract": bind(ROOT / "config/c2-q-contract.json"),
            "ship_contract": bind(ROOT / "config/ship-builder-v1.json"),
            "stdlib_manifest": bind(INPUT_MANIFEST),
            "ide_manifest": bind(CURRENT_IDE),
            "profile": bind(PROFILE),
            "static_product": bind(product_path),
            "linked_ELF": bind(elf),
            "driver": bind(DRIVER),
        },
        "next_gate": "Extended v1.3 Halt #1 before the Link-84 successor.",
        "claim_limit": (
            "One non-promotable product-shaped WPLTO; no successor product "
            "identity, hardware, acceptance or release claim."),
    }
    RECEIPT.write_bytes(CAN.json_bytes(receipt))
    print(
        "c2-v13-ship-wplto: PASS "
        f"bank2={EXPECTED_STATIC} "
        f"delta=+{preflight['geometry']['delta']['bank2_code_bytes']} "
        f"headroom={65536 - EXPECTED_STATIC} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_headroom_bytes']} links=0")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("profile", "wplto"))
    args = parser.parse_args()
    try:
        return profile() if args.phase == "profile" else wplto()
    except (OSError, KeyError, ValueError, WPLTOError) as error:
        print(f"c2-v13-ship-wplto: FIRST RED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
