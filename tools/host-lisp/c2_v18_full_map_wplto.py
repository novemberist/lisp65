#!/usr/bin/env python3
"""The sole product-shaped WPLTO card for v1.8 full-map ownership."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

from elf_truth import ElfTruth  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_stack_overlay_mapped_far_wplto as V17  # noqa: E402
import c2_v18_full_map_phase_c as PHASE_C  # noqa: E402


JOINT = V17.JOINT
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/post-promotion/v18/full-map-ownership-wplto"
PREFLIGHT = ROOT / "build/post-promotion/v18/full-map-ownership-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
RECEIPT = EVIDENCE / "c2.3-v1.8-full-map-ownership-product-card-receipt.json"
FIRST_RED = EVIDENCE / "c2.3-v1.8-full-map-ownership-product-card-first-red.json"
TOOL_FIRST_RED = EVIDENCE / "c2.3-v1.8-full-map-ownership-pre-card-tool-first-red.json"
CONTRACT = ROOT / "config/c2-full-map-ownership-contract.json"
PHASE_B = EVIDENCE / "c2.3-v1.8-full-map-phase-b-contract-pricing-receipt.json"
PHASE_C_RECEIPT = EVIDENCE / "c2.3-v1.8-full-map-phase-c-gate-receipt.json"
PLAN = ROOT / "docs/planning/1.8-full-map-ownership-work-plan.md"
LINK90 = EVIDENCE / "c2.3-v1.4-link90-vic-unlock-wplto-receipt.json"
LINK90_ELF = (
    ROOT / "build/post-promotion/v14/link90-vic-unlock-wplto/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
SHIP_PROJECT = ROOT / "examples/ship/parity-toy/project.l65p"
SHIP_IMAGE = PREFLIGHT / "parity-toy.d81"
SHIP_RECEIPT = PREFLIGHT / "parity-toy.receipt.json"
SHIP_RUNTIME = PREFLIGHT / "parity-toy.runtime.elf"
SHIP_STAGER = PREFLIGHT / "parity-toy.stager.elf"
FEATURE = "LISP65_CODE_WINDOW_CONVERGENCE"
DRIVER = Path(__file__).resolve()
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    lines = result.stdout.strip().splitlines()
    return lines[-1] if lines else f"{label}: PASS"


def validate_ship_witness() -> str:
    value = load(SHIP_RECEIPT)
    require(
        value.get("status") == "passed"
        and value.get("executions") == 1
        and value["verification"]["members_verified"] == 9
        and value["verification"]["image_sha256"] == sha(SHIP_IMAGE)
        and "status=0 input=1" in value["host_execution"]["output"]
        and SHIP_RUNTIME.is_file() and SHIP_STAGER.is_file(),
        "fresh parity-toy execution/media witness drift")
    return "ship-builder: PASS sample=parity-toy host=1 media-members=9 fresh=true"


def create_ship_witness() -> str:
    require(not PREFLIGHT.exists(),
            "v1.8 full-map preflight is one-shot before the product card")
    PREFLIGHT.parent.mkdir(parents=True, exist_ok=True)
    run([
        sys.executable, "tools/host-lisp/ship_builder.py", "build",
        "--form", "(ship \"parity-toy\" :entry 'main)",
        "--project", str(SHIP_PROJECT), "--out", str(SHIP_IMAGE),
    ], "fresh full-map parity-toy build")
    verify = run([
        sys.executable, "tools/host-lisp/ship_builder.py", "verify",
        "--image", str(SHIP_IMAGE),
    ], "fresh full-map parity-toy media verification")
    require("members=9" in verify,
            "fresh parity-toy media member count drift")
    return validate_ship_witness()


def host_gates() -> dict[str, str]:
    base = V17.LINK90.BASE.ORIGINAL_HOST_GATES()
    return {
        **base,
        "m65_hw": run(
            [sys.executable, "tools/host-lisp/c2_m65_hw_gate.py"],
            "m65-hw gate"),
        "ship_contract": run(
            [sys.executable, "tools/host-lisp/ship_builder.py", "selftest"],
            "Ship contract selftest"),
        "asm_c_contract": run(
            [sys.executable, "tools/host-lisp/asm_c_constant_contract.py",
             "check", "--cc", "cc", "--out",
             "build/generated/asm-c-contract.inc"],
            "ASM/C constant contract"),
        "mapped_far_ownership": run(
            [sys.executable, "tools/host-lisp/c2_mapped_far_service_gate.py"],
            "mapped far-service ownership gate"),
        "mapped_far_assembly_equivalence": run(
            [sys.executable,
             "tools/host-lisp/c2_mapped_far_asm_equivalence.py"],
            "mapped far-service assembly equivalence"),
        "state_ownership_phase_c": run(
            [sys.executable,
             "tools/host-lisp/c2_v17_state_ownership_phase_c.py"],
            "v1.7 state-ownership Phase C"),
        "full_map_phase_c": run(
            [sys.executable, "tools/host-lisp/c2_v18_full_map_phase_c.py",
             "check"],
            "v1.8 full-map Phase C"),
        "code_window_convergence": run(
            [sys.executable,
             "tools/host-lisp/c2_code_window_convergence_gate.py"],
            "code-window convergence gate"),
        "dma_broaden_once_sweep": run(
            [sys.executable,
             "tools/host-lisp/c2_dma_content_consumption_sweep.py"],
            "DMA content-consumption sweep"),
        "fresh_ship_sample": validate_ship_witness(),
    }


def configure() -> None:
    JOINT.BUILD = BUILD
    JOINT.PREFLIGHT = V17.LINK90.PREFLIGHT
    JOINT.RECEIPT = RECEIPT
    JOINT.PROFILE_RECEIPT = V17.PROFILE_RECEIPT
    JOINT.PREDECESSOR = V17.PREDECESSOR
    JOINT.BASELINE_STDLIB = V17.M65.BASE_PREFIX.with_suffix(".manifest.json")
    JOINT.INPUT_MANIFEST = V17.M65.PREFIX.with_suffix(".manifest.json")
    JOINT.INPUT_RECEIPT = V17.M65.RECEIPT
    JOINT.EXPECTED_STATIC = V17.EXPECTED_STATIC
    JOINT.EXPECTED_ENTRIES = V17.EXPECTED_ENTRIES
    JOINT.EXPECTED_RESOLUTIONS = V17.EXPECTED_RESOLUTIONS
    JOINT.EXPECTED_ROOTS = V17.EXPECTED_ROOTS
    JOINT.EXPECTED_DIRECT_REFS = V17.EXPECTED_DIRECT_REFS
    JOINT.DRIVER = DRIVER
    JOINT.freight_delta = V17.LINK90.delta
    JOINT.host_gates = host_gates

    original_single_link = JOINT.CAN.PRODUCT.single_link

    def full_map_single_link(
        out: Path, *, probe_definitions: tuple[str, ...] = (),
        direct_entry_receipt: Path =
            JOINT.CAN.PRODUCT.DIRECT_ENTRY_CONTRACT_RECEIPT,
        direct_entry_check_tool: str = "c2_direct_entry_contract.py",
        extra_contract_lines: tuple[str, ...] = (),
    ) -> None:
        definitions = tuple(dict.fromkeys((*probe_definitions, FEATURE)))
        return original_single_link(
            out, probe_definitions=definitions,
            direct_entry_receipt=direct_entry_receipt,
            direct_entry_check_tool=direct_entry_check_tool,
            extra_contract_lines=(
                *extra_contract_lines,
                "stack_overlay_ownership=mapped-bank2-far-service",
                "full_map_ownership=owned-sequential-crt-chain-empty-noinit",
                "mapped_far_service_physical=0x02b8b2-0x02bc1c",
                "mapped_far_service_cpu=0x78b2-0x7c1c",
                "mapped_far_service_facade=0xb3b0-0xb412",
                "ordinary_chain=0xb61d-0xbffb",
                "ordinary_margin=0xbffb-0xc000-nonallocatable",
                "owned_overlay_floor=0xc354",
            ),
        )

    JOINT.CAN.PRODUCT.single_link = full_map_single_link
    PRODUCT.configure_full_map_ownership()


def symbol_values(truth: ElfTruth) -> dict[str, int]:
    expected = {
        "__data_load_start": 0xB9B4,
        "__data_start": 0xB9B4,
        "__data_end": 0xB9CA,
        "__data_size": 22,
        "__bss_start": 0xB9CA,
        "__bss_end": 0xBFFB,
        "__bss_size": 1585,
        "__heap_start": 0xC354,
        "__lisp65_workbench_noinit_end": 0xC34D,
        "__lisp65_workbench_overlay_min_start": 0xC354,
    }
    actual = {name: truth.symbol(name).value for name in expected}
    require(actual == expected,
            f"final CRT/heap/overlay symbol relation drift: {actual}")
    return actual


def allocatable_output_delta(truth: ElfTruth) -> dict[str, Any]:
    require(LINK90_ELF.is_file(), "Link-90 allocated-section authority absent")
    baseline = ElfTruth.read(LINK90_ELF, llvm_readobj=LLVM_READOBJ)
    current = {
        row.name for row in truth.sections
        if row.bytes > 0 and "SHF_ALLOC" in row.flags
    }
    prior = {
        row.name for row in baseline.sections
        if row.bytes > 0 and "SHF_ALLOC" in row.flags
    }
    allowed_added = {
        ".lisp65_c2_mapped_far_facade",
        ".lisp65_c2_mapped_far_service",
        ".lisp65_c2_convergence_state",
        ".lisp65_c2_convergence_zp",
        ".lisp65_c2_static_stack",
        ".lisp65_c2_fixed_bank0",
        ".lisp65_c2_fixed_bank0_code",
        ".lisp65_c2_fixed_bank0_hot_bss",
    }
    added = sorted(current - prior)
    removed = sorted(prior - current)
    unknown = sorted(set(added) - allowed_added)
    require(not unknown and not removed,
            f"unknown allocatable output delta: added={added} removed={removed}")
    return {
        "baseline": bind(LINK90_ELF),
        "baseline_count": len(prior),
        "final_count": len(current),
        "added_owned_outputs": added,
        "removed_outputs": removed,
        "unknown_allocatable_outputs": unknown,
    }


def full_map_layout() -> dict[str, Any]:
    # Reuse the already permanent 1.5/1.7 facade/far/state/ZP/stack checks,
    # then add the v1.8 ordinary-chain and startup-range closure.
    V17.BUILD = BUILD
    inherited = V17.final_layout()
    elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    prg = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
    truth = ElfTruth.read(
        elf, llvm_readobj=LLVM_READOBJ, include_section_data=True)
    expected = {
        ".rodata": (0xB61D, 879),
        ".lisp65_runtime_overlay_verifier_bindings": (0xB98C, 40),
        ".data": (0xB9B4, 22),
        ".bss": (0xB9CA, 1585),
        ".noinit": (0xC34D, 0),
        ".lisp65_c2_convergence_state": (0xC000, 66),
        ".lisp65_c2_static_stack": (0xC074, 6),
        ".lisp65_c2_fixed_bank0": (0xC080, 408),
        ".lisp65_c2_fixed_bank0_code": (0xC218, 69),
        ".lisp65_c2_fixed_bank0_hot_bss": (0xC25D, 240),
        ".lisp65_c2_mapped_far_facade": (0xB3B0, 98),
        ".lisp65_c2_mapped_far_service": (0x78B2, 874),
    }
    sections: dict[str, dict[str, Any]] = {}
    for name, pair in expected.items():
        row = truth.section(name)
        require((row.address, row.bytes) == pair,
                f"final full-map section drift {name}: "
                f"{(row.address, row.bytes)}")
        sections[name] = {"vma": f"0x{row.address:04x}", "bytes": row.bytes}
    require(V17.OWNERSHIP.section_lma(elf, ".data") == 0xB9B4,
            "final data LMA/VMA relation drift")
    far_lma = V17.OWNERSHIP.section_lma(
        elf, ".lisp65_c2_mapped_far_service")
    require(far_lma == 0x02B8B2, f"final far LMA drift: {far_lma:#x}")
    phase_c = load(PHASE_C_RECEIPT)["bound_product_object_replay"]
    lto = BUILD / "wplto/resident-island-seed.prg.lto.o"
    phase_c_lto = load(PHASE_C_RECEIPT)["authorities"]["bound_v17_lto"]
    require(sha(lto) == phase_c_lto["sha256"],
            "fresh WPLTO LTO object differs from the SHA-bound v1.7 object")
    require(sha(elf) == phase_c["elf_sha256"] and
            sha(prg) == phase_c["prg_sha256"],
            "fresh final product differs from the bound Phase-C replay")
    stderr = BUILD / "wplto/lisp65-c2-substitution-linked.prg.link.stderr.txt"
    text = stderr.read_text(encoding="utf-8") if stderr.is_file() else ""
    warnings = [line for line in text.splitlines() if "warning:" in line]
    require(not warnings or
            (len(warnings) == 1 and ".llvm_sympart" in warnings[0]),
            f"unexpected final linker warning: {warnings}")
    return {
        "ordinary_and_fixed_sections": sections,
        "crt_and_boundary_symbols": symbol_values(truth),
        "five_byte_margin": 0xC000 - (0xB9CA + 1585),
        "margin_allocatable": False,
        "far_service_lma": "0x02b8b2",
        "allocatable_output_delta": allocatable_output_delta(truth),
        "inherited_ownership_checks": inherited,
        "relocation_aware_delta": {
            "fresh_lto_byteidentical_to_bound_v17": True,
            "final_elf_byteidentical_to_phase_c_replay": True,
            "final_prg_byteidentical_to_phase_c_replay": True,
            "allowed_linker_relocation_or_fixup_deltas": 0,
            "unexpected_semantic_bytes": 0,
            "oracle": "whole ELF/PRG SHA after byteidentical LTO authority",
        },
        "artifacts": {
            "elf": bind(elf), "prg": bind(prg), "lto": bind(lto),
            "map": bind(BUILD / "wplto/lisp65-c2-substitution-linked.prg.map"),
            "linker": bind(BUILD / "wplto/c2-substitution.ld"),
        },
    }


def annotate() -> None:
    value = load(RECEIPT)
    phase_c = load(PHASE_C_RECEIPT)
    phase_b = load(PHASE_B)
    ship = load(SHIP_RECEIPT)
    layout = full_map_layout()
    require(
        phase_b["status"].startswith("PASS: one-of-one")
        and phase_c["status"] == "PASS"
        and phase_c["execution_witness"]["phase_a_inputs_routed_once"] == 84
        and phase_c["execution_witness"]["mutations"] == 14,
        "v1.8 contract or permanent-gate authority drift")
    require(ship["status"] == "passed" and ship["executions"] == 1,
            "fresh parity-toy witness drift at annotation")
    walls = value["walls"]
    require(
        walls["bank0_text_headroom_bytes"] >= 0
        and walls["e000_headroom_bytes"] >= 54
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and value["capacity"]["session_family_headroom_bytes"] >= 0,
        f"full-map card crossed a closed wall: {walls}")
    value.update({
        "format": "lisp65-c2.3-v1.8-full-map-ownership-WPLTO-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-sole-full-map-ownership-WPLTO",
        "promotable": False,
        "wplto_probes_consumed": 1,
        "product_links": 0,
        "hardware_runs": 0,
        "selected_layout": "owned-sequential-crt-chain-empty-noinit",
        "full_map_layout": layout,
        "fresh_ship_and_reconstruction": {
            "parity_toy_host_executions": 1,
            "parity_toy_media_members": 9,
            "parity_toy": bind(SHIP_RECEIPT),
            "parity_toy_image": bind(SHIP_IMAGE),
            "bank2_reconstructions": layout["inherited_ownership_checks"]
                ["bank2_packaging"]["reconstructions"],
            "bank2_byteidentical": True,
            "phase_c_product_replay_links": 2,
            "phase_c_product_replay_byteidentical": True,
        },
        "authority": {
            **value["authority"],
            "full_map_contract": bind(CONTRACT),
            "full_map_phase_b": bind(PHASE_B),
            "full_map_phase_c": bind(PHASE_C_RECEIPT),
            "plan": bind(PLAN),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "fresh_ship_sample": bind(SHIP_RECEIPT),
            "driver": bind(DRIVER),
        },
        "next_gate": (
            "Halt 2 terminal ownership decision; green may reopen 1.5 Halt 2, "
            "the preserved parity pilot and then Link 91."),
        "claim_limit": (
            "One non-promotable product-shaped full-map WPLTO and fresh host "
            "Ship/reconstruction witnesses; no Link 91, hardware, product "
            "identity, parity-surface or release claim."),
    })
    value.pop("wall_headroom_delta_from_link83", None)
    RECEIPT.write_bytes(canonical(value))


def preflight() -> None:
    require(not BUILD.exists() and not RECEIPT.exists() and
            not FIRST_RED.exists(),
            "v1.8 product card or its terminal receipt already exists")
    gates = {
        "source_syntax": run(
            [sys.executable, "tools/host-lisp/source_syntax_check.py"],
            "source syntax"),
        "phase_c": run(
            [sys.executable, "tools/host-lisp/c2_v18_full_map_phase_c.py",
             "check"], "v1.8 Phase C"),
        "mapped_far_equivalence": run(
            [sys.executable,
             "tools/host-lisp/c2_mapped_far_asm_equivalence.py"],
            "mapped far assembly equivalence"),
        "convergence": run(
            [sys.executable,
             "tools/host-lisp/c2_code_window_convergence_gate.py"],
            "code-window convergence"),
    }
    gates["fresh_ship"] = create_ship_witness()
    configure()
    platform, parent, zp_data, product = PHASE_C.render_sources()
    facts = PHASE_C.source_facts(
        platform, parent, zp_data, product,
        load(PHASE_C.PHASE_A), load(PHASE_B), load(CONTRACT))
    PHASE_C.audit_source(facts)
    value = {
        "format": "lisp65-c2.3-v1.8-full-map-pre-WPLTO-v1",
        "recorded_on": date.today().isoformat(),
        "status": "PASS",
        "card_directory_absent": True,
        "wplto_started": False,
        "compiler_invocations": 0,
        "hardware_runs": 0,
        "phase_a_inputs_routed_once": facts["assignments"],
        "full_check_source": {
            "status": "PASS immediately before driver preparation",
            "exit_code": 0,
            "committed_content": "9d0de815",
            "note": "The driver adds no product source and is syntax-checked here.",
        },
        "gate_summaries": gates,
        "authority": {
            "contract": bind(CONTRACT), "phase_b": bind(PHASE_B),
            "phase_c": bind(PHASE_C_RECEIPT), "plan": bind(PLAN),
            "driver": bind(DRIVER), "link90": bind(LINK90),
        },
        "next": "the sole v1.8 product-shaped WPLTO card",
    }
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print(
        "c2-v18-full-map-wplto: PREFLIGHT PASS "
        f"inputs={facts['assignments']} ship=1 compiles=0 wplto=0")


def record_first_red(error: BaseException) -> None:
    started = BUILD.exists()
    target = FIRST_RED if started else TOOL_FIRST_RED
    artifacts = []
    for relative in (
        "wplto/resident-island-seed.prg.link.stderr.txt",
        "wplto/resident-island-seed.prg.map",
        "wplto/resident-island-seed.prg.lto.o",
        "wplto/lisp65-c2-substitution-linked.prg.link.stderr.txt",
        "wplto/lisp65-c2-substitution-linked.prg.map",
        "wplto/lisp65-c2-substitution-linked.prg.elf",
        "wplto/c2-substitution.ld",
    ):
        path = BUILD / relative
        if path.is_file():
            artifacts.append(bind(path))
    text = str(error)
    seed_stderr = BUILD / "wplto/resident-island-seed.prg.link.stderr.txt"
    stage = "pre-card-tool"
    if started:
        stage = "product-WPLTO-or-final-card-check"
        if seed_stderr.is_file() and seed_stderr.read_text(
                encoding="utf-8").strip():
            text = seed_stderr.read_text(encoding="utf-8").strip()
            stage = "seed-link"
    value = {
        "format": (
            "lisp65-c2.3-v1.8-full-map-WPLTO-first-red-v1" if started else
            "lisp65-c2.3-v1.8-full-map-pre-WPLTO-first-red-v1"),
        "recorded_on": date.today().isoformat(),
        "status": "FIRST RED" if started else "TOOL FIRST RED",
        "error": text,
        "failure_stage": stage,
        "wplto_probes_consumed": int(started),
        "product_links": 0,
        "hardware_runs": 0,
        "retry_authorized": not started,
        "artifacts": artifacts,
        "authority": {
            "contract": bind(CONTRACT), "phase_c": bind(PHASE_C_RECEIPT),
            "driver": bind(DRIVER),
        },
        "claim_limit": (
            "Exact terminal First Red from the sole Phase-D WPLTO; no retry, "
            "address negotiation, narrower claim, Link 91 or hardware."
            if started else
            "Pre-card harness stop only; the commissioned WPLTO remains unused."),
    }
    target.write_bytes(canonical(value))


def selftest() -> None:
    require(PRODUCT is JOINT.CAN.PRODUCT,
            "canonical product-linker module identity split")
    contract = load(CONTRACT)
    require(contract["candidate_selection"]["fitting_rows"] == 1 and
            contract["selected_layout"]["margin"]["bytes"] == 5 and
            contract["selected_layout"]["margin"]["allocatable"] is False,
            "selected full-map contract drift")
    phase_c = load(PHASE_C_RECEIPT)
    require(phase_c["status"] == "PASS" and
            phase_c["bound_product_object_replay"]["links"] == 2,
            "Phase-C replay authority drift")
    print("c2-v18-full-map-wplto: SELFTEST PASS card=one retry=none")


def card() -> None:
    require(PREFLIGHT_RECEIPT.is_file(),
            "green pre-card receipt required before the sole WPLTO")
    require(load(PREFLIGHT_RECEIPT)["status"] == "PASS",
            "pre-card receipt is not green")
    require(not BUILD.exists() and not RECEIPT.exists() and
            not FIRST_RED.exists(),
            "v1.8 full-map WPLTO is one-shot")
    configure()
    result = JOINT.wplto()
    require(result == 0, f"canonical WPLTO returned {result}")
    annotate()
    value = load(RECEIPT)
    layout = value["full_map_layout"]
    print(
        "c2-v18-full-map-wplto: PASS "
        f"ordinary=0xb61d-0xbffb margin={layout['five_byte_margin']} "
        f"facade=98/243 far=874 stack=6/12 "
        f"text={value['walls']['bank0_text_headroom_bytes']} "
        f"e000={value['walls']['e000_headroom_bytes']} probes=1")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("selftest", "preflight", "card"))
    args = parser.parse_args()
    if args.mode == "selftest":
        selftest()
    elif args.mode == "preflight":
        preflight()
    else:
        card()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, JOINT.WPLTOError, OSError, KeyError,
            ValueError) as error:
        try:
            record_first_red(error)
        except Exception as recording_error:  # never hide the first failure
            print(f"c2-v18-full-map-wplto: receipt failure: {recording_error}",
                  file=sys.stderr)
        print(f"c2-v18-full-map-wplto: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
