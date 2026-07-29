#!/usr/bin/env python3
"""Qualify and build the accepted require-fastpath/IRQ Link-76 successor."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_bound_carrier_successor_link75 as PREV  # noqa: E402
import c2_interrupt_ownership_gate as IRQ  # noqa: E402
import c2_require_idempotence_fastpath as FAST  # noqa: E402


BASE = PREV.BASE
LINK = 76
EXPECTED_STATIC = 40746
EXPECTED_ENTRIES = 682
EXPECTED_RESOLUTIONS = 2711
EXPECTED_ROOTS = 340
EXPECTED_DIRECT_REFS = 643
ROOT_BUILD = (
    ROOT / "build/post-promotion/link76-require-fastpath-irq-ownership")
PROBE_BUILD = ROOT_BUILD / "product-shaped-probe-after-crc-relocation"
LINK_BUILD = ROOT_BUILD
FAST_MANIFEST = (
    ROOT / "build/post-promotion/phase-m/require-fastpath/"
    "stdlib-p0.manifest.json")
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
FAST_RECEIPT = EVIDENCE / "c2.2-require-idempotence-fastpath-receipt.json"
IRQ_SOURCE_RECEIPT = EVIDENCE / (
    "c2.2-interrupt-ownership-source-gate-receipt.json")
ARTIFACT_PRELINK = (
    PROBE_BUILD / "receipts/artifact-side-fresh-prelink.json")
ARTIFACT_QUALIFICATION = (
    PROBE_BUILD /
    "receipts/artifact-side-crc-relocation-qualification.json")
ARTIFACT_RESUME = (
    PROBE_BUILD /
    "receipts/artifact-side-crc-relocation-resume.json")
WPLTO_RECEIPT = EVIDENCE / (
    "c2.2-link76-require-fastpath-irq-ownership-wplto-receipt.json")
LINK_RECEIPT = EVIDENCE / (
    "c2.2-product-link76-require-fastpath-irq-ownership-"
    "structural-receipt.json")
PREDECESSOR = EVIDENCE / (
    "c2.2-product-link75-bound-compiler-carrier-structural-receipt.json")
DRIVER = Path(__file__).resolve()


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


def select_static_plane() -> None:
    PREV.EXPECTED_STATIC = EXPECTED_STATIC
    PREV.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    PREV.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    PREV.EXPECTED_ROOTS = EXPECTED_ROOTS
    PREV.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    PREV.select_carrier()
    req = BASE.PROBE.REQ
    req.SPECS = tuple(
        (key, name, FAST_MANIFEST if key == "stdlib-p0" else path)
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
    select_static_plane()
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
    os.environ.update(BASE.CAN.canonical_build_environment())


def fastpath_gate() -> dict[str, Any]:
    receipt = load(FAST_RECEIPT)
    require(
        receipt["status"] == "passed-parser-free-idempotence-fastpath"
        and receipt["geometry"]["bank2_delta_bytes"] == 462
        and receipt["geometry"]["resident_delta_bytes"] == 0
        and receipt["candidate"]["repeat_reduction"]["vm_steps_percent"]
            >= 90
        and receipt["candidate"]["repeat_reduction"][
            "prim67_reads_percent"] >= 90
        and len(receipt["fallback_mutations"]) == 5
        and FAST.source_gate()["cache_authority"] is False,
        "accepted require idempotence fastpath authority drift",
    )
    return {
        "authority": bind(FAST_RECEIPT),
        "source_gate": FAST.source_gate(),
        "bank2_delta_bytes": 462,
        "resident_delta_bytes": 0,
        "repeat_reduction": receipt["candidate"]["repeat_reduction"],
        "fallback_directions": sorted(receipt["fallback_mutations"]),
    }


def preplane_bound_carrier_gate() -> dict[str, Any]:
    """Prove the carrier before the current static plane exists.

    Link 75's combined helper also reopens its old product manifest and
    compares it with mutable workspace build outputs.  A successor pre-plane
    gate must not pretend that historical product binding is current.  Check
    the immutable carrier/source/execution surface here; ``link_action``
    performs the full product-manifest binding against Link 76's freshly
    emitted static plane.
    """
    inventory = PREV.BOUND.contract_gate()
    carrier, suite, source = PREV.BOUND.source_binding_gate(
        PREV.CARRIER, PREV.TIER_RECEIPT)
    execution = PREV.BOUND.execute_bound_cases(
        PREV.CARRIER, carrier, suite)
    generated = PREV.BOUND.generated_gate()
    mutations = PREV.BOUND.mutation_gate()
    require(
        execution["prim67"] == 67
        and execution["prim68"] == 68
        and execution["is_prim68_case"] == "passed"
        and len(mutations) == 6
        and "uncovered-artifact-class" in mutations,
        "pre-plane bound carrier/source parity red",
    )
    return {
        "status": "passed-bound-carrier-before-current-plane",
        "inventory": inventory,
        "compiler_carrier": source,
        "bound_execution": execution,
        "generated_artifacts": generated,
        "mutations_rejected": mutations,
        "deferred_current_product_binding":
            "performed by PREV.bound_gate after Link-76 static-plane emission",
    }


def fix_gates() -> dict[str, Any]:
    inherited = PREV.PREV.fix_gates()
    inherited["bound_artifact_source_parity_preplane"] = (
        preplane_bound_carrier_gate())
    fastpath = fastpath_gate()
    irq = IRQ.audit()
    require(
        irq["status"] == "passed-strict-internal-interrupt-ownership"
        and irq["mutations"]["rejected"]
            == irq["mutations"]["total"] == 16,
        "interrupt ownership source/contract gate red",
    )
    inherited["require_idempotence_fastpath"] = fastpath
    inherited["strict_interrupt_ownership"] = irq
    return inherited


def probe_action() -> int:
    configure()
    require(
        FAST_MANIFEST.is_file()
        and not PROBE_BUILD.exists()
        and not WPLTO_RECEIPT.exists(),
        "Link-76 WPLTO one-shot boundary red",
    )
    predecessor = load(PREDECESSOR)
    require(
        predecessor["status"].startswith(
            "passed-Link75-source-bound-compiler-carrier")
        and predecessor["static_geometry"] == {
            "bank2_static_code_bytes": 40284,
            "bank2_headroom_bytes": 25252,
            "entries": 677,
            "resolutions": 2685,
            "roots": 340,
            "direct_entry_refs": 643,
        },
        "Link-75 predecessor authority drift",
    )
    paths, result = BASE.run_wplto(PROBE_BUILD)
    irq_linked_path = (
        paths["receipts"] / "interrupt-ownership-WPLTO.json")
    irq = IRQ.audit(
        elf=paths["wplto"] /
        "lisp65-c2-substitution-linked.prg.elf")
    write(irq_linked_path, irq)
    fastpath = fastpath_gate()
    walls = result["walls"]
    capacity = result["capacity"]
    require(
        result["plane"]["static_code_bytes"] == EXPECTED_STATIC
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and capacity["session_family_headroom_bytes"] >= 0
        and irq["final_ELF"]["readbacks_before_window_publish"] is True,
        "Link-76 WPLTO geometry or linked ownership edge red",
    )
    value = {
        "format":
            "lisp65-c2.2-link76-require-fastpath-irq-ownership-WPLTO-v1",
        "recorded_on": "2026-07-28",
        "status":
            "passed-Link76-require-fastpath-and-strict-IRQ-ownership-WPLTO",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "predecessor": bind(PREDECESSOR),
        "static_code_bytes": EXPECTED_STATIC,
        "freight": {
            "bank2_static_code_bytes": EXPECTED_STATIC,
            "bank2_delta_bytes": 462,
            "resident_fastpath_delta_bytes": 0,
            "entries": EXPECTED_ENTRIES,
            "resolutions": EXPECTED_RESOLUTIONS,
            "roots": EXPECTED_ROOTS,
            "direct_entry_refs": EXPECTED_DIRECT_REFS,
        },
        "require_fastpath": fastpath,
        "interrupt_ownership": bind(irq_linked_path),
        "walls": walls,
        "capacity": capacity,
        "wplto": result["wplto"],
        "authority": {
            "profile": bind(
                ROOT / "config/c2-l-full-product-profile.json"),
            "execution_contract": bind(
                ROOT / "config/c2-lite-execution-contract.json"),
            "static_plane_header": bind(
                ROOT / "src/c2_lite_static_plane.h"),
            "linked_ELF": bind(
                paths["wplto"] /
                "lisp65-c2-substitution-linked.prg.elf"),
            "driver": bind(DRIVER),
        },
        "next_gate":
            "Exactly one Link-76 successor product link and full post-link "
            "replay; hardware remains bundled with Phase V/K2.",
        "claim_limit":
            "Product-shaped WPLTO and final-ELF dataflow only; "
            "no Link-76 or hardware claim.",
    }
    write(WPLTO_RECEIPT, value)
    print(
        "c2-link76-fastpath-irq: WPLTO PASS "
        f"bank2={EXPECTED_STATIC} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_headroom_bytes']}")
    return 0


def resume_probe_action() -> int:
    """Bind the completed first-red link without compiling or linking again.

    The sole product-shaped WPLTO link completed before two historical
    artifact checkers rejected the new CRC placement/pins.  The source fixes
    changed those checkers only.  Publish-last completion and every current
    replacement gate were then replayed against that same ELF/PRG identity.
    """
    configure()
    require(
        not WPLTO_RECEIPT.exists()
        and ARTIFACT_PRELINK.is_file()
        and ARTIFACT_QUALIFICATION.is_file(),
        "Link-76 artifact-side WPLTO resume boundary red",
    )
    paths = BASE.paths(PROBE_BUILD)
    wplto = paths["wplto"]
    product = wplto / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    structure_path = wplto / "product-substitution-link.json"
    pre_ownership_path = wplto / "pre-ownership-closure-final.json"
    unbound = wplto / "lisp65-c2-substitution-unbound.prg"
    first_red_unbound = (
        wplto / "lisp65-c2-substitution-unbound.first-red-old-pin.prg")
    structure = load(structure_path)
    pre_ownership = load(pre_ownership_path)
    prelink = load(ARTIFACT_PRELINK)
    qualification = load(ARTIFACT_QUALIFICATION)
    replacement = qualification["replacement"]
    abi = qualification["abi"]
    irq = qualification["interrupt_ownership"]
    walls = replacement["walls"]
    capacity = dict(replacement["capacity"])
    # The current adapter makes the historical replacement gate accept its
    # descriptive capacity status by temporarily projecting it to "passed".
    # Publish the underlying current status so the later fresh product run
    # compares semantic truth rather than adapter representation.
    if "current_profile_status" in capacity:
        capacity["status"] = capacity.pop("current_profile_status")
    crc = irq["final_ELF"]["boot_only_crc"]
    require(
        all(path.is_file() for path in (
            product, elf, unbound, first_red_unbound))
        and structure["status"] == "passed"
        and pre_ownership["status"] == "passed"
        and prelink["status"] == qualification["status"] == "passed"
        and replacement["status"] == "passed"
        and abi["status"] == "passed-all-assembler-leaf-abi-contracts"
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and capacity["session_family_headroom_bytes"] >= 0
        and crc == {
            "value": 0xA1DD,
            "bytes": 108,
            "section": ".text",
            "source_input_section": ".text.c2_kernal_boot_only",
            "before_handoff_address": True,
            "direct_edge_count_whole_ELF": 1,
            "direct_caller": "c2_kernal_take_ownership",
            "post_ownership_reachable": False,
        },
        "Link-76 artifact-side CRC relocation qualification red",
    )
    irq_linked_path = (
        paths["receipts"] / "interrupt-ownership-WPLTO.json")
    write(irq_linked_path, irq)
    fastpath = fastpath_gate()
    resume = {
        "format": "lisp65-link76-artifact-side-WPLTO-resume-v1",
        "recorded_on": "2026-07-28",
        "status":
            "passed-same-link-artifact-completion-after-checker-corrections",
        "compiler_runs": 0,
        "linker_runs": 0,
        "product_links_added": 0,
        "linked_identity": {
            "product": bind(product),
            "elf": bind(elf),
            "map": bind(Path(str(product) + ".map")),
            "unbound_link_identity": bind(unbound),
        },
        "first_red_link_identity": bind(first_red_unbound),
        "fresh_prelink": bind(ARTIFACT_PRELINK),
        "fresh_current_qualification": bind(ARTIFACT_QUALIFICATION),
        "generic_product_closure": bind(structure_path),
        "pre_ownership_closure": bind(pre_ownership_path),
        "claim_limit":
            "Artifact-side publish-last and current gates only; no compiler, "
            "linker, product-link or hardware run.",
    }
    write(ARTIFACT_RESUME, resume)
    value = {
        "format":
            "lisp65-c2.2-link76-require-fastpath-irq-ownership-WPLTO-v1",
        "recorded_on": "2026-07-28",
        "status":
            "passed-Link76-require-fastpath-and-strict-IRQ-ownership-WPLTO",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "predecessor": bind(PREDECESSOR),
        "freight": {
            "bank2_static_code_bytes": EXPECTED_STATIC,
            "bank2_delta_bytes": 462,
            "resident_fastpath_delta_bytes": 0,
            "entries": EXPECTED_ENTRIES,
            "resolutions": EXPECTED_RESOLUTIONS,
            "roots": EXPECTED_ROOTS,
            "direct_entry_refs": EXPECTED_DIRECT_REFS,
        },
        "require_fastpath": fastpath,
        "interrupt_ownership": bind(irq_linked_path),
        "CRC_relocation": crc,
        "walls": walls,
        "capacity": capacity,
        "wplto": {
            "status":
                "passed-current-artifact-side-closure-after-typed-first-red",
            "artifact_resume": bind(ARTIFACT_RESUME),
            "compiler_runs": 0,
            "linker_runs": 0,
            "product_links_added": 0,
        },
        "authority": {
            "profile": bind(
                ROOT / "config/c2-l-full-product-profile.json"),
            "execution_contract": bind(
                ROOT / "config/c2-lite-execution-contract.json"),
            "kernal_contract": bind(
                ROOT / "config/c2-kernal-unmap-contract.json"),
            "static_plane_header": bind(
                ROOT / "src/c2_lite_static_plane.h"),
            "linked_ELF": bind(elf),
            "driver": bind(DRIVER),
        },
        "next_gate":
            "Exactly one Link-76 successor product link and full post-link "
            "replay; hardware remains bundled with Phase V/K2.",
        "claim_limit":
            "Product-shaped WPLTO, pre-ownership closure and final-ELF "
            "dataflow only; no Link-76 or hardware claim.",
    }
    write(WPLTO_RECEIPT, value)
    print(
        "c2-link76-fastpath-irq: WPLTO RESUME PASS "
        f"bank2={EXPECTED_STATIC} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_headroom_bytes']}")
    return 0


def link_action() -> int:
    configure()
    inherited_receipt = (
        load(LINK_RECEIPT) if LINK_RECEIPT.is_file() else None)
    require(
        WPLTO_RECEIPT.is_file()
        and (
            inherited_receipt is None
            or inherited_receipt["status"]
                == "passed-Link76-header-CRC-successor-hardware-not-run"
        ),
        "accepted Link-76 WPLTO absent or completed product link already consumed",
    )
    paths = BASE.paths(LINK_BUILD)
    if inherited_receipt is None:
        if (
            paths["wplto"].is_dir()
            and not paths["final"].is_dir()
            and not (paths["receipts"] / "artifact-completion.json").is_file()
        ):
            BASE.fresh_completion()
        result = BASE.link_action()
    else:
        require(
            paths["final"].is_dir()
            and (paths["receipts"] / "artifact-completion.json").is_file(),
            "Link-76 inherited receipt lacks artifact-side completion",
        )
        # BASE.link_action normally performs this path binding.  The
        # artifact-only successor branch deliberately skips that function, so
        # bind CAN.check to Link 76's final directory explicitly.
        BASE.configure(LINK_BUILD)
        result = 0
    paths = BASE.paths(LINK_BUILD)
    manifest = load(paths["manifest"])
    manifest["static_plane"].update({
        "status":
            "passed-require-fastpath-IRQ-ownership-single-emitter-plane",
        "bank2_static_code_bytes": EXPECTED_STATIC,
        "entries": EXPECTED_ENTRIES,
        "resolutions": EXPECTED_RESOLUTIONS,
        "roots": EXPECTED_ROOTS,
        "direct_entry_refs": EXPECTED_DIRECT_REFS,
        "compiler_carrier": bind(PREV.CARRIER),
        "require_fastpath": bind(FAST_RECEIPT),
    })
    write(paths["manifest"], manifest)
    checked = BASE.CAN.check()
    final_elf = (
        paths["final"] / "lisp65-c2-substitution-linked.prg.elf")
    irq_path = (
        paths["receipts"] / "interrupt-ownership-final-replay.json")
    irq = IRQ.audit(elf=final_elf)
    write(irq_path, irq)
    parity = PREV.bound_gate(
        paths["static_product"] / "substitution-artifacts.json",
        paths["receipts"] / "bound-artifact-source-parity-final.json",
    )
    receipt = load(LINK_RECEIPT)
    authority = load(WPLTO_RECEIPT)
    require(
        checked["identity"] == manifest["identity"]
        and parity["bound_execution"]["is_prim68_case"] == "passed"
        and irq["mutations"]["rejected"] == 16
        and receipt["walls"]["bank0_text_headroom_bytes"]
            == authority["walls"]["bank0_text_headroom_bytes"]
        and receipt["walls"]["e000_headroom_bytes"]
            == authority["walls"]["e000_headroom_bytes"]
        and receipt["walls"]["session_family_headroom_bytes"]
            == authority["capacity"]["session_family_headroom_bytes"],
        "Link-76 final identity, carrier, IRQ or map replay red",
    )
    receipt.update({
        "format":
            "lisp65-c2.2-product-link76-require-fastpath-"
            "irq-ownership-v1",
        "status":
            "passed-Link76-require-fastpath-and-strict-IRQ-ownership-"
            "hardware-not-run",
        "predecessor": bind(PREDECESSOR),
        "qualified_WPLTO": bind(WPLTO_RECEIPT),
        "manifest": bind(paths["manifest"]),
        "static_geometry": authority["freight"],
        "require_fastpath": authority["require_fastpath"],
        "interrupt_ownership": bind(irq_path),
        "bundled_hardware_line": bind(IRQ.HARDWARE),
        "bound_artifact_source_parity": parity,
        "next_gate":
            "Continue Phase V. The single final Phase-I/Phase-V/K2 "
            "hardware session includes the post-boot (0 0 0) ownership row.",
        "claim_limit":
            "Link 76 structural completion only; IRQ register hardware "
            "readback and Phase-V behavior remain unclaimed.",
    })
    receipt["authority"]["driver"] = bind(DRIVER)
    write(LINK_RECEIPT, receipt)
    print(
        "c2-link76-fastpath-irq: LINK PASS "
        f"product={receipt['product']['sha256']} "
        f"bank2={EXPECTED_STATIC} "
        f"text={receipt['walls']['bank0_text_headroom_bytes']} "
        f"e000={receipt['walls']['e000_headroom_bytes']} "
        f"session={receipt['walls']['session_family_headroom_bytes']}")
    return result


def main() -> int:
    action = sys.argv[1:] or ["probe"]
    require(
        action in (["probe"], ["resume-probe"], ["link"], ["_complete"]),
        "usage: c2_require_fastpath_irq_successor_link76.py "
        "[probe|resume-probe|link|_complete]",
    )
    if action == ["probe"]:
        return probe_action()
    if action == ["resume-probe"]:
        return resume_probe_action()
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
        IRQ.GateError, OSError, ValueError, KeyError,
        json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        print("c2-link76-fastpath-irq: FIRST RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
