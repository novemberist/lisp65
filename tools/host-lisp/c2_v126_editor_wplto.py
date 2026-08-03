#!/usr/bin/env python3
"""Emit the v1.2.6 editor plane and run its one product-shaped WPLTO."""

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

import c2_v125_require_fix_wplto as PREV  # noqa: E402


V = PREV.V
BASE = PREV.BASE
CAN = PREV.CAN
PRODUCT = PREV.PRODUCT
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/post-promotion/v126/editor/product-shaped-wplto"
PREFLIGHT = ROOT / "build/post-promotion/v126/editor/profile-preflight"
RECEIPT = EVIDENCE / "c2.2-v1.2.6-editor-wplto-receipt.json"
PROFILE_RECEIPT = EVIDENCE / (
    "c2.2-v1.2.6-editor-profile-preflight-receipt.json")
EDITOR_RECEIPT = EVIDENCE / (
    "c2-v126-editor-allocation-gate-receipt.json")
PREDECESSOR = EVIDENCE / "c2.2-v1.2.5-phase-b-link82-receipt.json"
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
STATIC_HEADER = ROOT / "src/c2_lite_static_plane.h"
EXECUTION_CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
CURRENT_IDE = ROOT / "build/bytecode/dialect-v2/libs/ide.manifest.json"
BOUND_IDE = ROOT / (
    "build/c2.2/substitution/published-nullary-call-bytecode-artifacts/"
    "libs/ide.manifest.json")
EXPECTED_STATIC = 45063
EXPECTED_ENTRIES = 750
EXPECTED_RESOLUTIONS = 2931
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


def bind_editor_spec() -> None:
    """Select the current IDE artifact at every canonical producer view."""
    req = BASE.PROBE.REQ
    specs = tuple(
        (key, name, CURRENT_IDE if key == "ide" else path)
        for key, name, path in req.SPECS
    )
    require(
        len(specs) == 6
        and sum(key == "ide" for key, _name, _path in specs) == 1,
        "canonical six-image inventory does not have one IDE role",
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
    V.RANDOM_MANIFEST = PREV.TIME_MANIFEST
    V.EXPECTED_STATIC = EXPECTED_STATIC
    V.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    V.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    V.EXPECTED_ROOTS = EXPECTED_ROOTS
    V.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    V.configure_candidate()
    BASE.LINK = 83
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
    bind_editor_spec()
    os.environ.update(CAN.canonical_build_environment())
    return paths


def editor_delta() -> dict[str, int]:
    old = load(BOUND_IDE)
    new = load(CURRENT_IDE)
    delta = {
        "bank2_code_bytes": new["code_bytes"] - old["code_bytes"],
        "entries": len(new["entries"]) - len(old["entries"]),
        "resolution_words":
            len(new["literal_patches"]) - len(old["literal_patches"]),
        "roots": 10,
        "resident_bytes": 0,
    }
    require(
        delta == {
            "bank2_code_bytes": 1826,
            "entries": 25,
            "resolution_words": 89,
            "roots": 10,
            "resident_bytes": 0,
        },
        f"editor artifact delta drift: {delta}",
    )
    return delta


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
        "editor preflight static geometry drift",
    )
    return {
        "paths": paths,
        "product": product,
        "semantics": semantics,
        "bank2_sha256":
            hashlib.sha256(bank2_path.read_bytes()).hexdigest(),
    }


def profile() -> int:
    require(
        not PREFLIGHT.exists() and not PROFILE_RECEIPT.exists(),
        "v1.2.6 editor profile emission is one-shot",
    )
    run(
        [sys.executable,
         "tools/host-lisp/c2_v126_editor_allocation_gate.py", "check"],
        "editor allocation gate",
    )
    delta = editor_delta()
    plane = emit_plane()
    product = plane["product"]
    profile_value = load(PROFILE)
    profile_value.update({
        "recorded_on": "2026-07-31",
        "authority": {
            "kind": "fresh-single-emitter-static-plane-dataflow",
            "emitter": "tools/host-lisp/c2_lite_canonical_product.py",
            "product_manifest": (
                "build/post-promotion/v126/editor/profile-preflight/"
                "static-plane/narrow-static/product/"
                "substitution-artifacts.json"
            ),
            "compiled_ide_manifest":
                CURRENT_IDE.relative_to(ROOT).as_posix(),
            "bank2_static_plane": (
                "build/post-promotion/v126/editor/profile-preflight/"
                "static-plane/narrow-static/v6-semantics/"
                "bank2-static-code.bin"
            ),
            "rule": (
                "The current IDE artifact is bound at the canonical six-image "
                "producer; historical IDE bytes are only the delta baseline."
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
            "sha256": plane["bank2_sha256"],
            "headroom_bytes": 65536 - EXPECTED_STATIC,
        },
        "v126_editor_delta": delta,
    })
    PROFILE.write_bytes(CAN.json_bytes(profile_value))
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
    value = {
        "format": "lisp65-c2.2-v1.2.6-editor-profile-preflight-v1",
        "recorded_on": "2026-07-31",
        "status": "passed-editor-linker-free-static-profile-preflight",
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
        "authority": {
            "editor_gate": bind(EDITOR_RECEIPT),
            "current_ide": bind(CURRENT_IDE),
            "historical_ide": bind(BOUND_IDE),
            "profile": bind(PROFILE),
            "static_header": bind(STATIC_HEADER),
            "execution_contract": bind(EXECUTION_CONTRACT),
            "static_product": bind(
                plane["paths"]["static_product"]
                / "substitution-artifacts.json"),
            "driver": bind(DRIVER),
        },
        "claim_limit": (
            "Linker-free profile binding only; no WPLTO, product link, "
            "hardware or release claim."
        ),
    }
    PROFILE_RECEIPT.write_bytes(CAN.json_bytes(value))
    print(
        "c2-v126-editor-profile: PASS "
        f"bank2={EXPECTED_STATIC} delta=+{delta['bank2_code_bytes']} "
        f"headroom={65536 - EXPECTED_STATIC} linker=0")
    return 0


def wplto() -> int:
    require(
        PROFILE_RECEIPT.is_file()
        and not BUILD.exists()
        and not RECEIPT.exists(),
        "v1.2.6 editor WPLTO is a one-shot card after profile emission",
    )
    run(
        [sys.executable,
         "tools/host-lisp/c2_v126_editor_allocation_gate.py", "check"],
        "editor allocation gate",
    )
    preflight = load(PROFILE_RECEIPT)
    profile_value = load(PROFILE)
    require(
        preflight["status"]
            == "passed-editor-linker-free-static-profile-preflight"
        and profile_value["bank2_static_code"]["bytes"] == EXPECTED_STATIC
        and profile_value["bank2_static_code"]["sha256"]
            == preflight["geometry"]["bank2_sha256"],
        "editor profile authority drift",
    )
    paths = configure(BUILD)
    static = BASE.PROBE.REQ.build_static_plane()
    plane = BASE.PROBE.REQ.F1W.static_gate()
    header_binding = PRODUCT.bind_generated_stdlib_header(paths)
    product_path = (
        paths["static_product"] / "substitution-artifacts.json")
    product = load(product_path)
    require(
        static["semantics"]["code_bytes"] == EXPECTED_STATIC
        and plane["static_code_bytes"] == EXPECTED_STATIC
        and product["entries"] == EXPECTED_ENTRIES
        and product["resolutions"] == EXPECTED_RESOLUTIONS
        and product["roots"] == EXPECTED_ROOTS
        and product["product_build_id_hex"]
            == profile_value["product_build_id"],
        "editor WPLTO static-plane identity drift",
    )
    V.EXPECTED_PRODUCT_ID = profile_value["product_build_id"]
    V.EXPECTED_BANK2_SHA = profile_value["bank2_static_code"]["sha256"]
    linked = CAN.run_wplto()
    replacement = linked["historical_checker_boundary"][
        "current_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    predecessor = load(PREDECESSOR)
    old_walls = predecessor["qualifying_candidate"]["walls"]
    for key in (
        "bank0_text_headroom_bytes",
        "e000_headroom_bytes",
        "fixed_hot_block_headroom_bytes",
        "ordinary_bank0_bss_headroom_bytes",
        "resident_island_headroom_bytes",
    ):
        require(walls[key] == old_walls[key],
                f"closed resident wall moved: {key}")
    require(
        capacity["session_family_headroom_bytes"]
            == old_walls["session_family_headroom_bytes"]
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_family_headroom_bytes"] >= 0,
        "editor WPLTO crossed a closed wall",
    )
    elf = paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf"
    require(elf.is_file(), "editor WPLTO linked ELF absent")
    value = {
        "format": "lisp65-c2.2-v1.2.6-editor-WPLTO-v1",
        "recorded_on": "2026-07-31",
        "status": "passed-editor-one-product-shaped-WPLTO",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "wplto_probes_consumed": 1,
        "predecessor": bind(PREDECESSOR),
        "profile_preflight": bind(PROFILE_RECEIPT),
        "editor_gate": bind(EDITOR_RECEIPT),
        "room_disposition": {
            "status": "re-parked-without-probe",
            "reason": (
                "No existing read-only room seam is both Bank-2-only and "
                "zero-resident; correctness-phase fusion remains forbidden."
            ),
        },
        "static_geometry": preflight["geometry"],
        "target_stdlib_header": header_binding,
        "walls": walls,
        "capacity": capacity,
        "wplto": linked,
        "authority": {
            "contract": bind(
                ROOT / "config/c2-v126-editor-allocation-contract.json"),
            "current_ide": bind(CURRENT_IDE),
            "profile": bind(PROFILE),
            "static_product": bind(product_path),
            "linked_ELF": bind(elf),
            "driver": bind(DRIVER),
        },
        "next_gate": "The single commissioned v1.2.6 successor product link.",
        "claim_limit": (
            "One non-promotable product-shaped WPLTO; no product identity, "
            "hardware, acceptance or release claim."
        ),
    }
    RECEIPT.write_bytes(CAN.json_bytes(value))
    print(
        "c2-v126-editor-wplto: PASS "
        f"bank2={EXPECTED_STATIC} delta=+1826 "
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
        print(f"c2-v126-editor-wplto: FIRST RED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
