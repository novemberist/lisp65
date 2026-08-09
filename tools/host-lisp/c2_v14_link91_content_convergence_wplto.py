#!/usr/bin/env python3
"""One product-shaped WPLTO for Link 91 DMA content convergence."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_v14_link90_vic_unlock_wplto as LINK90  # noqa: E402


JOINT = LINK90.BASE.JOINT
M65 = LINK90.M65
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/post-promotion/v14/link91-content-convergence-compact-wplto"
RECEIPT = EVIDENCE / (
    "c2.3-v1.4-link91-content-convergence-wplto-receipt.json")
PROFILE_RECEIPT = EVIDENCE / (
    "c2.3-v1.4-link90-vic-unlock-profile-receipt.json")
PREDECESSOR = EVIDENCE / (
    "c2.3-v1.4-link90-vic-unlock-wplto-receipt.json")
CONVERGENCE = EVIDENCE / (
    "c2.3-v1.4-code-window-content-convergence-gate-receipt.json")
SWEEP = EVIDENCE / (
    "c2.3-v1.4-dma-content-consumption-broaden-once-sweep.json")
SHIP = ROOT / (
    "build/post-promotion/v14/link91-content-convergence-preflight8/"
    "parity-toy.receipt.json")
SHIP_RUNTIME = SHIP.parent / "parity-toy.runtime.elf"
SHIP_STAGER = SHIP.parent / "parity-toy.stager.elf"
EXPECTED_STATIC = 47282
EXPECTED_ENTRIES = 787
EXPECTED_RESOLUTIONS = 3031
EXPECTED_ROOTS = 350
EXPECTED_DIRECT_REFS = 710
DRIVER = Path(__file__).resolve()


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout.strip().splitlines()[-1]


def ship_witness() -> str:
    value = load(SHIP)
    require(
        value["status"] == "passed"
        and value["executions"] == 1
        and value["verification"]["members_verified"] == 9
        and value["stager_audit"]["transport"]
        == "normal-f018b-d700-manifest-crc-content-convergence"
        and "status=0 input=1" in value["host_execution"]["output"]
        and SHIP_RUNTIME.is_file() and SHIP_STAGER.is_file(),
        "fixed Ship Runtime/stager witness drift")
    return (
        "ship-builder: PASS sample=parity-toy host=1 media-members=9 "
        "runtime=converged stager=manifest-crc")


def host_gates() -> dict[str, str]:
    base = LINK90.BASE.ORIGINAL_HOST_GATES()
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
        "code_window_convergence": run(
            [sys.executable,
             "tools/host-lisp/c2_code_window_convergence_gate.py"],
            "code-window convergence gate"),
        "dma_broaden_once_sweep": run(
            [sys.executable,
             "tools/host-lisp/c2_dma_content_consumption_sweep.py"],
            "DMA content-consumption sweep"),
        "fixed_ship_sample": ship_witness(),
    }


def configure() -> None:
    JOINT.BUILD = BUILD
    # The static Bank-2 plane is byte-identical to Link 90.  Reuse its fresh,
    # already bound profile; this card changes only native DMA consumption.
    JOINT.PREFLIGHT = LINK90.PREFLIGHT
    JOINT.RECEIPT = RECEIPT
    JOINT.PROFILE_RECEIPT = PROFILE_RECEIPT
    JOINT.PREDECESSOR = PREDECESSOR
    JOINT.BASELINE_STDLIB = M65.BASE_PREFIX.with_suffix(".manifest.json")
    JOINT.INPUT_MANIFEST = M65.PREFIX.with_suffix(".manifest.json")
    JOINT.INPUT_RECEIPT = M65.RECEIPT
    JOINT.EXPECTED_STATIC = EXPECTED_STATIC
    JOINT.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    JOINT.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    JOINT.EXPECTED_ROOTS = EXPECTED_ROOTS
    JOINT.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    JOINT.DRIVER = DRIVER
    JOINT.freight_delta = LINK90.delta
    JOINT.host_gates = host_gates


def annotate() -> None:
    value = load(RECEIPT)
    predecessor = load(PREDECESSOR)
    require(
        value["static_geometry"]["bank2_static_code_bytes"]
        == EXPECTED_STATIC
        and value["static_geometry"]["entries"] == EXPECTED_ENTRIES
        and value["static_geometry"]["resolutions"] == EXPECTED_RESOLUTIONS
        and value["capacity"] == predecessor["capacity"],
        "Link-91 convergence changed the static plane or session capacity")
    walls = value["walls"]
    require(
        walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0,
        f"Link-91 convergence crossed a closed product wall: {walls}")
    facade = load(BUILD / "wplto/fixed-host-facade-final.json")
    fixed = facade["fixed_state_contract"]["bank0_hot_bss"]
    noinit_address = fixed["end_exclusive"]
    noinit_bytes = fixed["following_noinit_bytes"]
    overlay_floor = (noinit_address + noinit_bytes + 1) & ~1
    require(
        noinit_address == 0xC34D and noinit_bytes == 6
        and overlay_floor == 0xC354,
        "Link-91 convergence moved pinned noinit/overlay geometry")
    value.update({
        "format": "lisp65-c2.3-v1.4-link91-content-convergence-WPLTO-v1",
        "recorded_on": "2026-08-04",
        "status": "passed-v1.4-link91-content-convergence-one-WPLTO",
        "wplto_probes_consumed": 1,
        "resident_delta_bytes": 0,
        "native_primitive_delta": 0,
        "inherited_native_geometry": {
            "noinit_address": "0xc34d",
            "noinit_bytes": 6,
            "overlay_floor": "0xc354",
            "status": "held-exactly",
        },
        "wall_headroom_delta_from_link90": {
            key: walls[key] - predecessor["walls"][key]
            for key in walls
        },
        "authority": {
            **value["authority"],
            "code_window_convergence": JOINT.bind(CONVERGENCE),
            "dma_broaden_once_sweep": JOINT.bind(SWEEP),
            "ship_sample": JOINT.bind(SHIP),
            "ship_runtime": JOINT.bind(SHIP_RUNTIME),
            "ship_stager": JOINT.bind(SHIP_STAGER),
            "driver": JOINT.bind(DRIVER),
        },
        "next_gate": "one Link 91 successor and unchanged parity-toy target boot",
        "claim_limit": (
            "One non-promotable product-shaped WPLTO plus host/ELF DMA "
            "closure; no successor identity or hardware claim."),
    })
    value.pop("wall_headroom_delta_from_link83", None)
    RECEIPT.write_bytes(JOINT.CAN.json_bytes(value))


def main() -> int:
    configure()
    result = JOINT.wplto()
    if result == 0:
        annotate()
        value = load(RECEIPT)
        print(
            "c2-v14-link91-content-convergence-wplto: PASS "
            f"text={value['walls']['bank0_text_headroom_bytes']} "
            f"e000={value['walls']['e000_headroom_bytes']} "
            f"bss={value['walls']['ordinary_bank0_bss_headroom_bytes']} "
            "noinit=6 overlay=0xc354 probes=1")
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, JOINT.WPLTOError, OSError, KeyError, ValueError) as error:
        print(
            f"c2-v14-link91-content-convergence-wplto: FIRST RED: {error}",
            file=sys.stderr)
        raise SystemExit(2)
