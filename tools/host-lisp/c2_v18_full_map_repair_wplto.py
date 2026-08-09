#!/usr/bin/env python3
"""The owner-reauthorized final v1.8 full-map product card.

The original card and its terminal First Red remain immutable.  This driver
consumes the repaired seven-row inventory closure, proves the repaired checker
against that card's SHA-bound seed artifacts, and owns one last fresh WPLTO.
Any red is terminal for the ownership programme.
"""

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
import c2_v18_full_map_wplto as BASE  # noqa: E402
import c2_v18_full_map_phase_c as PHASE_C  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/post-promotion/v18/full-map-ownership-repair-wplto"
PREFLIGHT = ROOT / "build/post-promotion/v18/full-map-ownership-repair-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
RECEIPT = EVIDENCE / (
    "c2.3-v1.8-full-map-ownership-repair-product-card-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.3-v1.8-full-map-ownership-repair-product-card-first-red.json")
HISTORICAL_FIRST_RED = EVIDENCE / (
    "c2.3-v1.8-full-map-ownership-product-card-first-red.json")
PHASE_C_RECEIPT = EVIDENCE / (
    "c2.3-v1.8-full-map-phase-c-gate-receipt.json")
CONTRACT = ROOT / "config/c2-full-map-ownership-contract.json"
PLAN = ROOT / "docs/planning/1.8-full-map-ownership-work-plan.md"
PREDECESSOR_BUILD = (
    ROOT / "build/post-promotion/v17/state-owned-mapped-far-wplto")
HISTORICAL_BUILD = (
    ROOT / "build/post-promotion/v18/full-map-ownership-wplto")
HISTORICAL_SEED = HISTORICAL_BUILD / "wplto/resident-island-seed.prg"
HISTORICAL_SEED_ELF = Path(str(HISTORICAL_SEED) + ".elf")
HISTORICAL_SEED_LTO = Path(str(HISTORICAL_SEED) + ".lto.o")
DRIVER = Path(__file__).resolve()
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
ORIGINAL_HOST_GATES = BASE.host_gates


class RepairCardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RepairCardError(message)


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


def configure_base() -> None:
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    BASE.RECEIPT = RECEIPT
    BASE.FIRST_RED = FIRST_RED
    BASE.TOOL_FIRST_RED = FIRST_RED
    BASE.SHIP_IMAGE = PREFLIGHT / "parity-toy.d81"
    BASE.SHIP_RECEIPT = PREFLIGHT / "parity-toy.receipt.json"
    BASE.SHIP_RUNTIME = PREFLIGHT / "parity-toy.runtime.elf"
    BASE.SHIP_STAGER = PREFLIGHT / "parity-toy.stager.elf"
    BASE.DRIVER = DRIVER
    BASE.full_map_layout = full_map_layout
    BASE.annotate = annotate


def normalized_profile(path: Path) -> tuple[list[str], list[tuple[str, str]]]:
    ordinary: list[str] = []
    inputs: list[tuple[str, str]] = []
    allowed_delta_keys = {
        "c2_artifacts_sha256", "linker_sha256", "full_map_ownership",
        "ordinary_chain", "ordinary_margin",
    }
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256="):
            source, digest = line[len("input_sha256="):].rsplit(":", 1)
            marker = "/generated-product-sources/"
            if marker in source:
                source = "generated-product-sources/" + source.split(
                    marker, 1)[1]
            inputs.append((source, digest))
            continue
        if line.split("=", 1)[0] not in allowed_delta_keys:
            ordinary.append(line)
    return ordinary, inputs


def without_paths(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: without_paths(item) for key, item in value.items()
                if key != "path"}
    if isinstance(value, list):
        return [without_paths(item) for item in value]
    return value


def semantic_profile_delta(build: Path) -> dict[str, Any]:
    current_profile = build / "wplto/resolved-profile.txt"
    prior_profile = PREDECESSOR_BUILD / "wplto/resolved-profile.txt"
    current_lines, current_inputs = normalized_profile(current_profile)
    prior_lines, prior_inputs = normalized_profile(prior_profile)
    require(current_lines == prior_lines,
            "non-linker resolved-profile semantics changed")
    require(current_inputs == prior_inputs and len(current_inputs) == 64,
            "compiled source-content identity changed")
    current_manifest = build / (
        "static-plane/narrow-static/product/substitution-artifacts.json")
    prior_manifest = PREDECESSOR_BUILD / (
        "static-plane/narrow-static/product/substitution-artifacts.json")
    require(without_paths(load(current_manifest)) ==
            without_paths(load(prior_manifest)),
            "C2D/shelf product semantics changed")
    return {
        "status": "PASS",
        "compiled_source_content_rows": len(current_inputs),
        "compiled_source_content_byteidentical": True,
        "resolved_profile_equal_after_owned_linker_identity_delta": True,
        "c2d_and_shelf_content_byteidentical": True,
        "allowed_profile_delta_keys": [
            "c2_artifacts_sha256 (manifest path identity only)",
            "linker_sha256",
            "full_map_ownership",
            "ordinary_chain",
            "ordinary_margin",
        ],
        "current_profile": bind(current_profile),
        "predecessor_profile": bind(prior_profile),
        "current_product_manifest": bind(current_manifest),
        "predecessor_product_manifest": bind(prior_manifest),
    }


def historical_seed_authority() -> dict[str, Any]:
    first = load(HISTORICAL_FIRST_RED)
    artifacts = first["artifacts"]
    expected = {
        "seed_prg": HISTORICAL_SEED,
        "seed_elf": HISTORICAL_SEED_ELF,
        "seed_lto": HISTORICAL_SEED_LTO,
    }
    for name, path in expected.items():
        require(artifacts[name]["sha256"] == sha(path),
                f"historical First-Red artifact drift: {name}")
    BASE.PRODUCT.configure_full_map_ownership()
    truth = ElfTruth.read(
        HISTORICAL_SEED_ELF, llvm_readobj=LLVM_READOBJ)
    closure = PHASE_C.final_inventory_closure(truth, load(CONTRACT))
    require(closure["execution_witness"]["total_mutations"] == 15,
            "historical seed did not pass the repaired closure")
    return {
        "first_red": bind(HISTORICAL_FIRST_RED),
        "seed_prg": bind(HISTORICAL_SEED),
        "seed_elf": bind(HISTORICAL_SEED_ELF),
        "seed_lto": bind(HISTORICAL_SEED_LTO),
        "repaired_inventory_on_exact_red_artifact": {
            "status": "PASS",
            "sections": closure["execution_witness"][
                "artifact_sections_checked"],
            "mutations": closure["execution_witness"]["total_mutations"],
        },
        "semantic_profile_delta": semantic_profile_delta(HISTORICAL_BUILD),
    }


def fresh_seed_reproduction() -> dict[str, Any]:
    fresh = BUILD / "wplto/resident-island-seed.prg"
    pairs = [
        ("prg", fresh, HISTORICAL_SEED),
        ("elf", Path(str(fresh) + ".elf"), HISTORICAL_SEED_ELF),
        ("lto", Path(str(fresh) + ".lto.o"), HISTORICAL_SEED_LTO),
    ]
    report: dict[str, Any] = {}
    for name, current, prior in pairs:
        require(sha(current) == sha(prior),
                f"fresh repair {name} is not byteidentical to First-Red seed")
        report[name] = {
            "byteidentical": True,
            "fresh": bind(current),
            "first_red_authority": bind(prior),
        }
    return report


def full_map_layout() -> dict[str, Any]:
    BASE.V17.BUILD = BUILD
    inherited = BASE.V17.final_layout()
    elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    prg = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
    lto = Path(str(prg) + ".lto.o")
    truth = ElfTruth.read(
        elf, llvm_readobj=LLVM_READOBJ, include_section_data=True)
    expected = {
        ".rodata": (0xB61D, 879),
        ".lisp65_runtime_overlay_verifier_bindings": (0xB98C, 40),
        ".data": (0xB9B4, 22), ".bss": (0xB9CA, 1585),
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
        sections[name] = {"vma": f"0x{row.address:04x}",
                          "bytes": row.bytes}
    require(BASE.V17.OWNERSHIP.section_lma(elf, ".data") == 0xB9B4,
            "final data LMA/VMA relation drift")
    far_lma = BASE.V17.OWNERSHIP.section_lma(
        elf, ".lisp65_c2_mapped_far_service")
    require(far_lma == 0x02B8B2, f"final far LMA drift: {far_lma:#x}")
    inventory = BASE.PRODUCT.final_section_inventory_check(prg)
    require(inventory["pin"]["expected_sections"] == 190,
            "final repaired section inventory count drift")
    stderr = BUILD / (
        "wplto/lisp65-c2-substitution-linked.prg.link.stderr.txt")
    warnings = [line for line in stderr.read_text(encoding="utf-8").splitlines()
                if "warning:" in line]
    require(not warnings or
            (len(warnings) == 1 and ".llvm_sympart" in warnings[0]),
            f"unexpected final linker warning: {warnings}")
    owned_sources = PHASE_C.FINAL_INVENTORY_NAMES
    relocations = [row for row in truth.relocations
                   if row.source_section in owned_sources]
    return {
        "ordinary_and_fixed_sections": sections,
        "crt_and_boundary_symbols": BASE.symbol_values(truth),
        "five_byte_margin": 0xC000 - (0xB9CA + 1585),
        "margin_allocatable": False,
        "far_service_lma": "0x02b8b2",
        "final_section_inventory": inventory,
        "allocatable_output_delta": BASE.allocatable_output_delta(truth),
        "inherited_ownership_checks": inherited,
        "relocation_aware_delta": {
            "semantic_profile": semantic_profile_delta(BUILD),
            "fresh_seed_reproduction": fresh_seed_reproduction(),
            "owned_output_relocations": len(relocations),
            "owned_output_relocation_sources": sorted(
                {row.source_section for row in relocations}),
            "unexpected_semantic_source_rows": 0,
            "oracle": (
                "64 normalized compiled-source content identities plus exact "
                "C2D/shelf semantics; linker ownership is checked separately "
                "through section, relocation, VMA/LMA and capacity truth"),
        },
        "artifacts": {
            "elf": bind(elf), "prg": bind(prg), "lto": bind(lto),
            "map": bind(BUILD / (
                "wplto/lisp65-c2-substitution-linked.prg.map")),
            "linker": bind(BUILD / "wplto/c2-substitution.ld"),
        },
    }


def annotate() -> None:
    value = load(RECEIPT)
    phase_c = load(PHASE_C_RECEIPT)
    phase_b = load(BASE.PHASE_B)
    ship = load(BASE.SHIP_RECEIPT)
    layout = full_map_layout()
    require(
        phase_b["status"].startswith("PASS: one-of-one")
        and phase_c["status"] == "PASS"
        and phase_c["execution_witness"]["source_mutations"] == 14
        and phase_c["execution_witness"]["final_inventory_mutations"] == 15
        and phase_c["execution_witness"]["mutations"] == 29,
        "repaired v1.8 contract or permanent gate drift")
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
        f"full-map repair card crossed a closed wall: {walls}")
    value.update({
        "format": "lisp65-c2.3-v1.8-full-map-ownership-repair-WPLTO-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-owner-reauthorized-final-full-map-WPLTO",
        "promotable": False,
        "wplto_probes_consumed_this_card": 1,
        "historical_first_red_cards": 1,
        "product_links": 0,
        "hardware_runs": 0,
        "selected_layout": "owned-sequential-crt-chain-empty-noinit",
        "full_map_layout": layout,
        "fresh_ship_and_reconstruction": {
            "parity_toy_host_executions": 1,
            "parity_toy_media_members": 9,
            "parity_toy": bind(BASE.SHIP_RECEIPT),
            "parity_toy_image": bind(BASE.SHIP_IMAGE),
            "bank2_reconstructions": layout["inherited_ownership_checks"]
                ["bank2_packaging"]["reconstructions"],
            "bank2_byteidentical": True,
            "phase_c_product_replay_links": 2,
            "phase_c_product_replay_byteidentical": True,
        },
        "authority": {
            **value["authority"],
            "full_map_contract": bind(CONTRACT),
            "full_map_phase_b": bind(BASE.PHASE_B),
            "full_map_phase_c": bind(PHASE_C_RECEIPT),
            "historical_terminal_first_red": bind(HISTORICAL_FIRST_RED),
            "owner_reauthorization_plan": bind(PLAN),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "fresh_ship_sample": bind(BASE.SHIP_RECEIPT),
            "repair_driver": bind(DRIVER),
        },
        "next_gate": (
            "Halt 2 terminal ownership decision; no Link 91 or hardware was "
            "started by this card."),
        "claim_limit": (
            "One owner-reauthorized non-promotable product-shaped full-map "
            "WPLTO after the bound inventory-only First Red; no Link 91, "
            "hardware, parity-surface, product identity or release claim."),
    })
    value.pop("wall_headroom_delta_from_link83", None)
    RECEIPT.write_bytes(canonical(value))


def host_gates() -> dict[str, str]:
    gates = ORIGINAL_HOST_GATES()
    gates["historical_seed_inventory_replay"] = (
        "PASS sections=7 mutations=15")
    return gates


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists() and
            not RECEIPT.exists() and not FIRST_RED.exists(),
            "final v1.8 repair card/preflight is one-shot")
    phase_c = load(PHASE_C_RECEIPT)
    require(phase_c["status"] == "PASS" and
            phase_c["execution_witness"]["mutations"] == 29,
            "repaired Phase-C closure is not green")
    historical = historical_seed_authority()
    PREFLIGHT.parent.mkdir(parents=True, exist_ok=True)
    configure_base()
    BASE.host_gates = host_gates
    BASE.configure()
    fresh_ship = BASE.create_ship_witness()
    value = {
        "format": "lisp65-c2.3-v1.8-full-map-repair-pre-WPLTO-v1",
        "recorded_on": date.today().isoformat(),
        "status": "PASS",
        "card_directory_absent": True,
        "wplto_started": False,
        "compiler_invocations": 0,
        "hardware_runs": 0,
        "historical_first_red_replay": historical,
        "fresh_ship": fresh_ship,
        "authority": {
            "contract": bind(CONTRACT),
            "phase_c": bind(PHASE_C_RECEIPT),
            "plan": bind(PLAN),
            "historical_first_red": bind(HISTORICAL_FIRST_RED),
            "driver": bind(DRIVER),
        },
        "next": "the owner-reauthorized final v1.8 product card",
    }
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("c2-v18-full-map-repair-wplto: PREFLIGHT PASS "
          "inventory=7 mutations=15 compiles=0 wplto=0")


def record_first_red(error: BaseException) -> None:
    started = BUILD.exists()
    text = str(error)
    seed_stderr = BUILD / "wplto/resident-island-seed.prg.link.stderr.txt"
    if seed_stderr.is_file():
        errors = [line for line in seed_stderr.read_text(
            encoding="utf-8").splitlines() if "error:" in line]
        if errors:
            text = "\n".join(errors)
    artifacts = []
    for relative in (
        "wplto/resident-island-seed.prg.lto.o",
        "wplto/resident-island-seed.prg.elf",
        "wplto/resident-island-seed.prg.map",
        "wplto/lisp65-c2-substitution-linked.prg.lto.o",
        "wplto/lisp65-c2-substitution-linked.prg.elf",
        "wplto/lisp65-c2-substitution-linked.prg.map",
        "wplto/c2-substitution.ld",
    ):
        path = BUILD / relative
        if path.is_file():
            artifacts.append(bind(path))
    value = {
        "format": "lisp65-c2.3-v1.8-final-repair-card-first-red-v1",
        "recorded_on": date.today().isoformat(),
        "status": "FIRST RED: final park required",
        "error": text,
        "card_started": started,
        "wplto_probes_consumed": int(started),
        "product_links": 0,
        "hardware_runs": 0,
        "retry_authorized": False,
        "final_park_required": True,
        "artifacts": artifacts,
        "authority": {
            "contract": bind(CONTRACT), "phase_c": bind(PHASE_C_RECEIPT),
            "owner_plan": bind(PLAN), "driver": bind(DRIVER),
            "historical_first_red": bind(HISTORICAL_FIRST_RED),
        },
        "claim_limit": (
            "The owner commission makes every red from this final repair "
            "attempt terminal. No retry, third repair, Link 91 or hardware."),
    }
    FIRST_RED.write_bytes(canonical(value))


def selftest() -> None:
    configure_base()
    phase_c = load(PHASE_C_RECEIPT)
    require(phase_c["execution_witness"]["mutations"] == 29,
            "Phase-C repair mutation count drift")
    historical = historical_seed_authority()
    require(historical["repaired_inventory_on_exact_red_artifact"] == {
        "status": "PASS", "sections": 7, "mutations": 15},
        "historical First-Red closure replay drift")
    require(not BUILD.exists() and not RECEIPT.exists() and
            not FIRST_RED.exists(), "final repair card already consumed")
    print("c2-v18-full-map-repair-wplto: SELFTEST PASS "
          "inventory=7 mutations=15 card=one retry=none")


def card() -> None:
    require(PREFLIGHT_RECEIPT.is_file() and
            load(PREFLIGHT_RECEIPT)["status"] == "PASS",
            "green repair preflight required")
    require(not BUILD.exists() and not RECEIPT.exists() and
            not FIRST_RED.exists(), "final repair WPLTO is one-shot")
    configure_base()
    BASE.host_gates = host_gates
    BASE.configure()
    result = BASE.JOINT.wplto()
    require(result == 0, f"canonical WPLTO returned {result}")
    annotate()
    value = load(RECEIPT)
    layout = value["full_map_layout"]
    print("c2-v18-full-map-repair-wplto: PASS "
          f"ordinary=0xb61d-0xbffb margin={layout['five_byte_margin']} "
          "inventory=190 facade=98/243 far=874 stack=6/12 probes=1")


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
    except (RepairCardError, BASE.CardError, BASE.JOINT.WPLTOError,
            OSError, KeyError, ValueError) as error:
        try:
            record_first_red(error)
        except Exception as recording_error:  # never hide the first failure
            print("c2-v18-full-map-repair-wplto: receipt failure: "
                  f"{recording_error}", file=sys.stderr)
        print(f"c2-v18-full-map-repair-wplto: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
