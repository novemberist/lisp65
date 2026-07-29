#!/usr/bin/env python3
"""Qualify and link the Link-73 vm_codebuf owner-lifetime correction."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_stz_successor_link72 as PREV  # noqa: E402


BASE = PREV.BASE
LINK = 73
ROOT_BUILD = ROOT / "build/post-promotion/link73-vm-codebuf-owner"
PROBE_BUILD = ROOT_BUILD / "product-shaped-probe"
LINK_BUILD = ROOT_BUILD
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
WPLTO_RECEIPT = EVIDENCE / (
    "c2.2-link73-vm-codebuf-owner-wplto-receipt.json")
LINK_RECEIPT = EVIDENCE / (
    "c2.2-product-link73-vm-codebuf-owner-structural-receipt.json")
PREDECESSOR = EVIDENCE / (
    "c2.2-product-link72-stz-semantics-structural-receipt.json")
DRIVER = Path(__file__).resolve()
BASELINE_MAP = (
    ROOT / "build/post-promotion/link72-stz-semantics/wplto/"
    "resident-island-seed.prg.map")
PROBE_MAP = PROBE_BUILD / "wplto/resident-island-seed.prg.map"


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
        encoding="utf-8")


def configure() -> None:
    BASE.LINK = LINK
    BASE.ROOT_BUILD = ROOT_BUILD
    BASE.PROBE_BUILD = PROBE_BUILD
    BASE.LINK_BUILD = LINK_BUILD
    BASE.WPLTO_RECEIPT = WPLTO_RECEIPT
    BASE.LINK_RECEIPT = LINK_RECEIPT
    BASE.LINK69 = PREDECESSOR
    BASE.EVIDENCE = EVIDENCE
    BASE.DRIVER = DRIVER
    BASE.fix_gates = fix_gates


def fix_gates() -> dict[str, Any]:
    gates = PREV.fix_gates()
    service = {
        "source": BASE.SERVICE.source_gate(),
        "source_mutations_rejected": BASE.SERVICE.mutation_gate(),
        "host": BASE.SERVICE.host_fixtures(
            ROOT_BUILD / "service-owner-lifetime-host"),
    }
    require(
        service["source"]["status"]
            == "passed-contract-stub-stateless-and-busy-dominance"
        and {
            "vm-codebuf-bank-owner-not-invalidated",
            "vm-codebuf-object-owner-not-invalidated",
            "vm-codebuf-owner-invalidated-too-late",
        } <= set(service["source_mutations_rejected"]),
        "vm_codebuf owner-lifetime source gate red")
    gates["session_service_owner_lifetime"] = service
    return gates


def existing_probe_result() -> dict[str, Any]:
    p = BASE.paths(PROBE_BUILD)
    internal = load(p["receipts"] / "wplto-internal.json")
    replacement = internal["fresh_replacement_gates"]
    service = BASE.SERVICE.linked_gate(
        p["wplto"] / "lisp65-c2-substitution-linked.prg.elf",
        p["wplto"] / "runtime-overlays-session-final.json",
        p["wplto"] / "runtime-overlays-boot-final.json")
    return {
        "walls": replacement["walls"],
        "capacity": replacement["capacity"],
        "linked_service": service,
        "static_code_bytes": 40243,
        "qualification": BASE.bind(
            p["receipts"] / "wplto-qualification.json"),
        "linked_gates": BASE.bind(
            p["receipts"] / "single-submit-linked-gates.json"),
        "ELF": BASE.bind(
            p["wplto"] / "lisp65-c2-substitution-linked.prg.elf"),
    }


def probe_action() -> int:
    configure()
    require(
        not WPLTO_RECEIPT.exists(),
        "Link-73 WPLTO receipt already exists")
    require(PROBE_MAP.is_file(), "the one Link-73 WPLTO probe is absent")
    gates = fix_gates()
    result = existing_probe_result()
    predecessor = load(PREDECESSOR)
    before = PREV.symbol_bytes(BASELINE_MAP, "vm_buffer_call")
    after = PREV.symbol_bytes(PROBE_MAP, "vm_buffer_call")
    invalidation = result["linked_service"]["vm_codebuf_owner_invalidation"]
    require(
        before == 54 and after == 65
        and invalidation["ordering"]
            == "both-owner-tags-before-first-context-write"
        and result["walls"]["resident_island_headroom_bytes"] == 50
        and result["walls"]["bank0_text_headroom_bytes"] == 351
        and result["walls"]["e000_headroom_bytes"] == 54
        and result["capacity"]["session_family_headroom_bytes"] == 113
        and result["static_code_bytes"] == 40243
        and predecessor["status"].startswith("passed-Link72-"),
        "Link-73 owner-lifetime WPLTO geometry or linked ordering red")
    value = {
        "format": "lisp65-c2.2-link73-vm-codebuf-owner-WPLTO-v1",
        "recorded_on": "2026-07-28",
        "status": "passed-Link73-vm-codebuf-owner-product-shaped-WPLTO",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "diagnosis": {
            "symptom":
                "verified (%is 22) returned undefined function i",
            "mechanism":
                "vm_buffer_call wrote its synchronous context into vm_codebuf "
                "without retiring the matching bank/object owner tag; "
                "BUF_ENSURE_MINE therefore consumed context bytes as the "
                "caller's literals and opcodes",
            "fix":
                "invalidate both owner coordinates before the first context "
                "write so OP_CALLPRIM reloads and reparses the caller",
        },
        "symbol_attribution": {
            "vm_buffer_call": {
                "Link72_bytes": before,
                "Link73_bytes": after,
                "delta_bytes": after - before,
            }
        },
        "fix_gates": gates,
        "linked_service": result["linked_service"],
        "static_code_bytes": result["static_code_bytes"],
        "walls": result["walls"],
        "capacity": result["capacity"],
        "authority": {
            "predecessor": BASE.bind(PREDECESSOR),
            "contract": BASE.bind(
                ROOT / "config/c2-session-service-contract.json"),
            "VM": BASE.bind(ROOT / "src/vm.c"),
            "service_gate": BASE.bind(
                ROOT / "tools/host-lisp/c2_intern_session_service_gate.py"),
            "qualification": result["qualification"],
            "linked_gates": result["linked_gates"],
            "ELF": result["ELF"],
            "driver": BASE.bind(DRIVER),
        },
        "next_gate": "authorized Link-73 successor product link",
        "claim_limit":
            "Product-shaped capacity and linked owner ordering only; no "
            "Link-73 or hardware claim.",
    }
    write(WPLTO_RECEIPT, value)
    print(
        "c2-defstruct-vm-codebuf-owner-link73: WPLTO PASS "
        f"stub={after} island={result['walls']['resident_island_headroom_bytes']} "
        f"session={result['capacity']['session_family_headroom_bytes']}")
    return 0


def link_action() -> int:
    configure()
    require(WPLTO_RECEIPT.is_file(), "accepted Link-73 WPLTO absent")
    result = 0
    if not LINK_RECEIPT.exists():
        result = BASE.link_action()
    receipt = load(LINK_RECEIPT)
    manifest_path = ROOT_BUILD / "canonical-product-manifest.json"
    manifest = load(manifest_path)
    manifest["static_plane"]["status"] = (
        "passed-vm-codebuf-owner-successor-single-emitter-static-plane")
    write(manifest_path, manifest)
    BASE.configure(LINK_BUILD)
    checked = BASE.CAN.check()
    service = BASE.SERVICE.linked_gate(
        ROOT_BUILD / "final/lisp65-c2-substitution-linked.prg.elf",
        ROOT_BUILD / "final/runtime-overlays-session-final.json",
        ROOT_BUILD / "final/runtime-overlays-boot-final.json")
    require(
        checked["identity"] == manifest["identity"]
        and service["vm_codebuf_owner_invalidation"]["ordering"]
            == "both-owner-tags-before-first-context-write",
        "Link-73 final owner-lifetime replay red")
    receipt.update({
        "format": "lisp65-c2.2-product-link73-vm-codebuf-owner-successor-v1",
        "status":
            "passed-Link73-vm-codebuf-owner-successor-hardware-not-run",
        "predecessor": BASE.bind(PREDECESSOR),
        "manifest": BASE.bind(manifest_path),
        "session_service": service,
        "fix_gates": fix_gates(),
        "next_gate":
            "focused %is/intern execution replay, then bundled "
            "require/defstruct hardware session",
        "claim_limit":
            "Link 73 structural completion only; hardware unclaimed.",
    })
    receipt["authority"]["driver"] = BASE.bind(DRIVER)
    write(LINK_RECEIPT, receipt)
    print(
        "c2-defstruct-vm-codebuf-owner-link73: LINK PASS "
        f"product={receipt['product']['sha256']} "
        f"island={receipt['walls']['resident_island_headroom_bytes']}")
    return result


def main() -> int:
    action = sys.argv[1:] or ["probe"]
    require(
        action in (["probe"], ["link"], ["_complete"]),
        "usage: c2_defstruct_vm_codebuf_owner_successor_link73.py "
        "[probe|link|_complete]")
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
        OSError, ValueError, KeyError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-defstruct-vm-codebuf-owner-link73: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
