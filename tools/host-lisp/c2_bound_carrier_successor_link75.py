#!/usr/bin/env python3
"""Qualify and link the Link-75 source-bound compiler carrier."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_asm_z_boundary_successor_link74 as PREV  # noqa: E402
import c2_bound_artifact_source_parity as BOUND  # noqa: E402


BASE = PREV.BASE
LINK = 75
ROOT_BUILD = ROOT / "build/post-promotion/link75-bound-compiler-carrier"
PROBE_BUILD = ROOT_BUILD / "product-shaped-probe"
LINK_BUILD = ROOT_BUILD
CARRIER = ROOT_BUILD / "compiler-carrier/lcc.manifest.json"
TIER_RECEIPT = (
    ROOT_BUILD / "compiler-carrier/compiler-tier/tier-generation.json")
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
WPLTO_RECEIPT = EVIDENCE / (
    "c2.2-link75-bound-compiler-carrier-wplto-receipt.json")
LINK_RECEIPT = EVIDENCE / (
    "c2.2-product-link75-bound-compiler-carrier-structural-receipt.json")
PREDECESSOR = EVIDENCE / (
    "c2.2-product-link74-asm-z-boundary-structural-receipt.json")
DIAGNOSIS = EVIDENCE / (
    "c2.2-link74-lit1-two-timepoint-hardware-first-red.json")
FOLLOWUPS = EVIDENCE / "c2.2-link75-carrier-followups-open.json"
LINK_FIRST_RED = EVIDENCE / (
    "c2.2-link75-bound-carrier-link-receipt-key-first-red.json")
POSTLINK_FIRST_RED = EVIDENCE / (
    "c2.2-link75-bound-carrier-postlink-selector-first-red.json")
DRIVER = Path(__file__).resolve()

EXPECTED_STATIC = 40284
EXPECTED_ENTRIES = 677
EXPECTED_RESOLUTIONS = 2685
EXPECTED_ROOTS = 340
EXPECTED_DIRECT_REFS = 643


class SuccessorError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SuccessorError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def bind(path: Path) -> dict[str, Any]:
    return BASE.bind(path)


def select_carrier() -> None:
    """Bind every static-plane producer to the regenerated LCC carrier."""
    req = BASE.PROBE.REQ
    req.SPECS = tuple(
        (key, name, CARRIER) if key == "lcc" else (key, name, path)
        for key, name, path in req.SPECS
    )
    req.EXPECTED_STATIC = EXPECTED_STATIC
    req.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    req.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    req.EXPECTED_ROOTS = EXPECTED_ROOTS
    req.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    req.F1W.EXPECTED_STATIC = EXPECTED_STATIC
    req.F1W.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    req.F1W.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    req.F1W.EXPECTED_ROOTS = EXPECTED_ROOTS


def configure() -> None:
    select_carrier()
    BASE.LINK = LINK
    BASE.EXPECTED_STATIC = EXPECTED_STATIC
    BASE.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    BASE.ROOT_BUILD = ROOT_BUILD
    BASE.PROBE_BUILD = PROBE_BUILD
    BASE.LINK_BUILD = LINK_BUILD
    BASE.WPLTO_RECEIPT = WPLTO_RECEIPT
    BASE.LINK_RECEIPT = LINK_RECEIPT
    BASE.LINK69 = PREDECESSOR
    BASE.EVIDENCE = EVIDENCE
    BASE.DRIVER = DRIVER
    BASE.fix_gates = fix_gates


def bound_gate(product_identity: Path, receipt: Path) -> dict[str, Any]:
    inventory = BOUND.contract_gate()
    carrier, suite, source = BOUND.source_binding_gate(
        CARRIER, TIER_RECEIPT)
    execution = BOUND.execute_bound_cases(CARRIER, carrier, suite)
    generated = BOUND.generated_gate()
    product = BOUND.product_manifest_gate(product_identity, CARRIER)
    mutations = BOUND.mutation_gate()
    value = {
        "format": BOUND.FORMAT,
        "status":
            "passed-source-to-actual-product-bound-artifact-parity",
        "inventory": inventory,
        "compiler_carrier": source,
        "bound_execution": execution,
        "generated_artifacts": generated,
        "single_emitter_manifests": product,
        "mutations_rejected": mutations,
    }
    write(receipt, value)
    return value


def fix_gates() -> dict[str, Any]:
    inherited = PREV.fix_gates()
    product = (
        ROOT_BUILD / "static-plane/narrow-static/product/"
        "substitution-artifacts.json")
    parity = bound_gate(
        product,
        ROOT_BUILD / "receipts/bound-artifact-source-parity.json",
    )
    require(
        parity["bound_execution"]["prim67"] == 67
        and parity["bound_execution"]["prim68"] == 68
        and parity["bound_execution"]["is_prim68_case"] == "passed"
        and parity["single_emitter_manifests"]["manifest_count"] == 6
        and len(parity["mutations_rejected"]) == 5,
        "bound carrier or broad artifact/source parity red",
    )
    inherited["bound_artifact_source_parity"] = parity
    return inherited


def probe_action() -> int:
    configure()
    require(
        CARRIER.is_file() and TIER_RECEIPT.is_file()
        and not WPLTO_RECEIPT.exists()
        and not (PROBE_BUILD / "wplto").exists(),
        "Link-75 carrier/WPLTO one-shot boundary red",
    )
    diagnosis = load(DIAGNOSIS)
    followups = load(FOLLOWUPS)
    require(
        diagnosis["status"]
            == "first-red-checkpoint-not-reached-bound-device-compiler-carrier-stale"
        and followups["status"].startswith("OPEN")
        and load(PREDECESSOR)["status"].startswith("passed-Link74-"),
        "Link-74 diagnosis, follow-up or predecessor authority drift",
    )
    paths, result = BASE.run_wplto(PROBE_BUILD)
    parity = bound_gate(
        paths["static_product"] / "substitution-artifacts.json",
        paths["receipts"] / "bound-artifact-source-parity.json",
    )
    walls = result["walls"]
    capacity = result["capacity"]
    require(
        result["plane"]["static_code_bytes"] == EXPECTED_STATIC
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_family_headroom_bytes"] >= 0
        and parity["bound_execution"]["is_prim68_case"] == "passed",
        "Link-75 WPLTO geometry or bound-carrier execution red",
    )
    value = {
        "format": "lisp65-c2.2-link75-bound-compiler-carrier-WPLTO-v1",
        "recorded_on": "2026-07-28",
        "status":
            "passed-Link75-source-bound-compiler-carrier-product-shaped-WPLTO",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "diagnosis": bind(DIAGNOSIS),
        "predecessor": bind(PREDECESSOR),
        "carrier_split": {
            "tail_boundary": "%lcc-v2-prim4-to-%lcc-v2-prim5",
            "prim4_bytes":
                parity["compiler_carrier"]["primitive_tail_sizes"][
                    "%lcc-v2-prim4"],
            "prim5_bytes":
                parity["compiler_carrier"]["primitive_tail_sizes"][
                    "%lcc-v2-prim5"],
            "bound_is_prim68_case": "passed",
        },
        "static_geometry": {
            "bank2_static_code_bytes": EXPECTED_STATIC,
            "bank2_headroom_bytes": 65536 - EXPECTED_STATIC,
            "entries": EXPECTED_ENTRIES,
            "resolutions": EXPECTED_RESOLUTIONS,
            "roots": EXPECTED_ROOTS,
            "direct_entry_refs": EXPECTED_DIRECT_REFS,
        },
        "static_code_bytes": EXPECTED_STATIC,
        "bound_artifact_source_parity": parity,
        "walls": walls,
        "capacity": capacity,
        "wplto": result["wplto"],
        "authority": {
            "carrier": bind(CARRIER),
            "tier_generation": bind(TIER_RECEIPT),
            "profile": bind(
                ROOT / "config/c2-l-full-product-profile.json"),
            "linked_ELF": bind(
                paths["wplto"] /
                "lisp65-c2-substitution-linked.prg.elf"),
            "driver": bind(DRIVER),
        },
        "open_followups": bind(FOLLOWUPS),
        "next_gate": "one authorized Link-75 successor product link",
        "claim_limit":
            "Product-shaped carrier identity and capacity only; "
            "no Link-75 product or hardware claim.",
    }
    write(WPLTO_RECEIPT, value)
    print(
        "c2-bound-carrier-link75: WPLTO PASS "
        f"bank2={EXPECTED_STATIC} refs={EXPECTED_DIRECT_REFS} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_headroom_bytes']}")
    return 0


def link_action() -> int:
    configure()
    require(
        WPLTO_RECEIPT.is_file(),
        "accepted Link-75 WPLTO absent",
    )
    result = 0
    if not LINK_RECEIPT.exists():
        paths = BASE.paths(LINK_BUILD)
        if (
            paths["wplto"].is_dir()
            and not paths["final"].is_dir()
            and not (
                paths["receipts"] / "artifact-completion.json"
            ).is_file()
        ):
            BASE.fresh_completion()
        result = BASE.link_action()
    else:
        BASE.configure(LINK_BUILD)
    paths = BASE.paths(LINK_BUILD)
    manifest = load(paths["manifest"])
    manifest["static_plane"].update({
        "status":
            "passed-source-bound-compiler-carrier-single-emitter-static-plane",
        "bank2_static_code_bytes": EXPECTED_STATIC,
        "entries": EXPECTED_ENTRIES,
        "resolutions": EXPECTED_RESOLUTIONS,
        "roots": EXPECTED_ROOTS,
        "direct_entry_refs": EXPECTED_DIRECT_REFS,
        "compiler_carrier": bind(CARRIER),
    })
    write(paths["manifest"], manifest)
    checked = BASE.CAN.check()
    parity = bound_gate(
        paths["static_product"] / "substitution-artifacts.json",
        paths["receipts"] / "bound-artifact-source-parity-final.json",
    )
    receipt = load(LINK_RECEIPT)
    authority = load(WPLTO_RECEIPT)
    require(
        checked["identity"] == manifest["identity"]
        and parity["bound_execution"]["is_prim68_case"] == "passed"
        and receipt["walls"]["bank0_text_headroom_bytes"]
            == authority["walls"]["bank0_text_headroom_bytes"]
        and receipt["walls"]["e000_headroom_bytes"]
            == authority["walls"]["e000_headroom_bytes"]
        and receipt["walls"]["session_family_headroom_bytes"]
            == authority["capacity"]["session_family_headroom_bytes"],
        "Link-75 final identity, carrier parity or map replay red",
    )
    receipt.update({
        "format":
            "lisp65-c2.2-product-link75-bound-compiler-carrier-v1",
        "status":
            "passed-Link75-source-bound-compiler-carrier-hardware-not-run",
        "predecessor": bind(PREDECESSOR),
        "qualified_WPLTO": bind(WPLTO_RECEIPT),
        "artifact_receipt_first_red": bind(LINK_FIRST_RED),
        "postlink_checker_first_red": bind(POSTLINK_FIRST_RED),
        "manifest": bind(paths["manifest"]),
        "static_geometry": authority["static_geometry"],
        "bound_artifact_source_parity": parity,
        "open_followups": bind(FOLLOWUPS),
        "next_gate":
            "One bundled hardware session: (%is 1), DIRMISS full-name "
            "negative fixture, require defstruct, construct/access/mutate "
            "point, and re-evaluate the Link-72 red-frame observation.",
        "claim_limit":
            "Link 75 structural completion only; hardware unclaimed.",
    })
    receipt["authority"]["driver"] = bind(DRIVER)
    write(LINK_RECEIPT, receipt)
    print(
        "c2-bound-carrier-link75: LINK PASS "
        f"product={receipt['product']['sha256']} "
        f"bank2={EXPECTED_STATIC} "
        f"text={receipt['walls']['bank0_text_headroom_bytes']} "
        f"e000={receipt['walls']['e000_headroom_bytes']} "
        f"session={receipt['walls']['session_family_headroom_bytes']}")
    return result


def main() -> int:
    action = sys.argv[1:] or ["probe"]
    require(
        action in (["probe"], ["link"], ["_complete"]),
        "usage: c2_bound_carrier_successor_link75.py "
        "[probe|link|_complete]",
    )
    if action == ["probe"]:
        return probe_action()
    if action == ["link"]:
        return link_action()
    configure()
    return BASE.complete_action()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        SuccessorError, PREV.SuccessorError, BASE.SuccessorError,
        BASE.PROBE.ProbeError, BASE.CAN.CanonicalError,
        BASE.SERVICE.GateError, BASE.SERVICE.ElfTruthError,
        BOUND.GateError, OSError, ValueError, KeyError,
        json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        print(
            "c2-bound-carrier-link75: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
