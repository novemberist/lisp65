#!/usr/bin/env python3
"""One product-shaped WPLTO for the selected mapped Bank-2 ownership row."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

from elf_truth import ElfTruth  # noqa: E402
import c2_mapped_far_service_gate as OWNERSHIP  # noqa: E402
import c2_v14_link90_vic_unlock_wplto as LINK90  # noqa: E402


JOINT = LINK90.BASE.JOINT
M65 = LINK90.M65
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/post-promotion/v17/state-owned-mapped-far-wplto"
PREFLIGHT = ROOT / "build/post-promotion/v17/state-owned-mapped-far-preflight"
RECEIPT = EVIDENCE / (
    "c2.3-v1.7-state-owned-mapped-far-product-card-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.3-v1.7-state-owned-mapped-far-product-card-first-red.json")
TOOL_FIRST_RED = EVIDENCE / (
    "c2.3-v1.7-state-owned-mapped-far-pre-card-tool-first-red.json")
PROFILE_RECEIPT = EVIDENCE / (
    "c2.3-v1.4-link90-vic-unlock-profile-receipt.json")
PREDECESSOR = EVIDENCE / (
    "c2.3-v1.4-link90-vic-unlock-wplto-receipt.json")
CONTRACT = ROOT / "config/c2-stack-overlay-ownership-contract.json"
OWNERSHIP_RECEIPT = EVIDENCE / (
    "c2.3-stack-overlay-mapped-far-service-ownership-gate-receipt.json")
CONVERGENCE = EVIDENCE / (
    "c2.3-v1.4-code-window-content-convergence-gate-receipt.json")
SWEEP = EVIDENCE / (
    "c2.3-v1.4-dma-content-consumption-broaden-once-sweep.json")
EQUIVALENCE = EVIDENCE / (
    "c2.3-v1.7-mapped-far-assembly-equivalence-receipt.json")
PHASE_C = EVIDENCE / (
    "c2.3-v1.7-state-ownership-phase-c-receipt.json")
SHIP_PROJECT = ROOT / "examples/ship/parity-toy/project.l65p"
SHIP_IMAGE = PREFLIGHT / "parity-toy.d81"
SHIP_RECEIPT = PREFLIGHT / "parity-toy.receipt.json"
SHIP_RUNTIME = PREFLIGHT / "parity-toy.runtime.elf"
SHIP_STAGER = PREFLIGHT / "parity-toy.stager.elf"
FEATURE = "LISP65_CODE_WINDOW_CONVERGENCE"
EXPECTED_STATIC = 47282
EXPECTED_OWNED_STATIC = 48156
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


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout.strip().splitlines()[-1]


def fresh_ship_witness() -> str:
    require(not PREFLIGHT.exists(),
            "mapped-far parity-toy preflight is one-shot")
    PREFLIGHT.parent.mkdir(parents=True, exist_ok=True)
    run([
        sys.executable, "tools/host-lisp/ship_builder.py", "build",
        "--form", "(ship \"parity-toy\" :entry 'main)",
        "--project", str(SHIP_PROJECT), "--out", str(SHIP_IMAGE),
    ], "fresh mapped-far parity-toy build")
    verify = run([
        sys.executable, "tools/host-lisp/ship_builder.py", "verify",
        "--image", str(SHIP_IMAGE),
    ], "fresh mapped-far parity-toy media verification")
    value = load(SHIP_RECEIPT)
    require(
        value["status"] == "passed"
        and value["executions"] == 1
        and value["verification"]["members_verified"] == 9
        and value["verification"]["image_sha256"] == sha(SHIP_IMAGE)
        and "status=0 input=1" in value["host_execution"]["output"]
        and SHIP_RUNTIME.is_file() and SHIP_STAGER.is_file()
        and "members=9" in verify,
        "fresh parity-toy execution/media witness drift")
    return (
        "ship-builder: PASS sample=parity-toy host=1 media-members=9 "
        "fresh=true")


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
        "mapped_far_ownership": run(
            [sys.executable,
             "tools/host-lisp/c2_mapped_far_service_gate.py"],
            "mapped far-service ownership gate"),
        "mapped_far_assembly_equivalence": run(
            [sys.executable,
             "tools/host-lisp/c2_mapped_far_asm_equivalence.py"],
            "mapped far-service assembly equivalence"),
        "state_ownership_phase_c": run(
            [sys.executable,
             "tools/host-lisp/c2_v17_state_ownership_phase_c.py"],
            "v1.7 state-ownership Phase C"),
        "code_window_convergence": run(
            [sys.executable,
             "tools/host-lisp/c2_code_window_convergence_gate.py"],
            "code-window convergence gate"),
        "dma_broaden_once_sweep": run(
            [sys.executable,
             "tools/host-lisp/c2_dma_content_consumption_sweep.py"],
            "DMA content-consumption sweep"),
        "fresh_ship_sample": fresh_ship_witness(),
    }


def configure() -> None:
    JOINT.BUILD = BUILD
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

    original_single_link = JOINT.CAN.PRODUCT.single_link

    def mapped_far_single_link(
        out: Path, *, probe_definitions: tuple[str, ...] = (),
        direct_entry_receipt: Path =
            JOINT.CAN.PRODUCT.DIRECT_ENTRY_CONTRACT_RECEIPT,
        direct_entry_check_tool: str = "c2_direct_entry_contract.py",
        extra_contract_lines: tuple[str, ...] = (),
    ) -> None:
        definitions = tuple(dict.fromkeys((*probe_definitions, FEATURE)))
        return original_single_link(
            out,
            probe_definitions=definitions,
            direct_entry_receipt=direct_entry_receipt,
            direct_entry_check_tool=direct_entry_check_tool,
            extra_contract_lines=(
                *extra_contract_lines,
                "stack_overlay_ownership=mapped-bank2-far-service",
                "mapped_far_service_physical=0x02b8b2-0x02bc1c",
                "mapped_far_service_cpu=0x78b2-0x7c1c",
                "mapped_far_service_facade=0xb3b0-0xb412",
                "owned_overlay_floor=0xc354",
            ),
        )

    JOINT.CAN.PRODUCT.single_link = mapped_far_single_link


def section_row(truth: ElfTruth, name: str, *, lma: int | None = None,
                address: int, size: int) -> dict[str, Any]:
    row = truth.section(name)
    require((row.address, row.bytes) == (address, size),
            f"owned final section drift: {name} "
            f"got=({row.address:#x},{row.bytes})")
    value = {"name": name, "vma": f"0x{row.address:04x}",
             "bytes": row.bytes}
    if lma is not None:
        actual_lma = OWNERSHIP.section_lma(
            BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf", name)
        require(actual_lma == lma,
                f"owned final section LMA drift: {name}: {actual_lma:#x}")
        value["lma"] = f"0x{actual_lma:08x}"
    return value


def reconstruct_owned_plane(truth: ElfTruth) -> dict[str, Any]:
    prefix = (BUILD / "static-plane/narrow-static/v6-semantics/"
              "bank2-static-code.bin")
    require(prefix.is_file() and prefix.stat().st_size == EXPECTED_STATIC,
            "fresh static Bank-2 prefix geometry drift")
    suffix = truth.section_bytes(".lisp65_c2_mapped_far_service")
    require(len(suffix) == EXPECTED_OWNED_STATIC - EXPECTED_STATIC,
            "far-service packaging length drift")
    pack = BUILD / "owned-bank2"
    pack.mkdir(parents=True, exist_ok=True)
    outputs = []
    # Two independent reads/reconstructions, no second compile or link.
    for label in ("a", "b"):
        prefix_bytes = prefix.read_bytes()
        suffix_bytes = truth.section_bytes(
            ".lisp65_c2_mapped_far_service")
        output = pack / f"bank2-static-code-owned-{label}.bin"
        output.write_bytes(prefix_bytes + suffix_bytes)
        outputs.append(output)
    require(outputs[0].read_bytes() == outputs[1].read_bytes(),
            "owned Bank-2 clean reconstruction is not byteidentical")
    payload = outputs[0].read_bytes()
    require(
        len(payload) == EXPECTED_OWNED_STATIC
        and payload[:EXPECTED_STATIC] == prefix.read_bytes()
        and payload[EXPECTED_STATIC:] == suffix,
        "owned Bank-2 prefix/suffix reconstruction drift")
    return {
        "source_prefix": bind(prefix),
        "far_service_suffix": {
            "bytes": len(suffix),
            "sha256": hashlib.sha256(suffix).hexdigest(),
        },
        "reconstructions": [bind(path) for path in outputs],
        "byteidentical": True,
        "owned_bytes": len(payload),
        "headroom_bytes": 65536 - len(payload),
        "existing_product_prefix_byteidentical": True,
        "existing_product_bytes_displaced": 0,
    }


def final_layout() -> dict[str, Any]:
    contract = load(CONTRACT)
    far = contract["mapped_far_service"]
    sections = contract["phase_c_owners"]["sections"]
    elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    truth = ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    rows = {
        "facade": section_row(
            truth, sections["facade"],
            address=int(far["resident"]["start"], 0),
            size=far["resident"]["total_bytes"]),
        "far_service": section_row(
            truth, sections["far_service"],
            address=int(far["map_tuple"]["mapped_service_cpu_start"], 0),
            size=far["bank2"]["service_bytes"],
            lma=int(far["bank2"]["service_physical_start"], 0)),
        "state": section_row(
            truth, sections["state"], address=0xC000, size=66),
        "scratch_zp": section_row(
            truth, sections["scratch_zp"], address=0x87, size=2),
    }
    stack = truth.section(sections["static_stack"])
    require(stack.address == 0xC074 and 0 < stack.bytes <= 12,
            f"owned static-stack arena drift: {stack}")
    rows["static_stack"] = {
        "name": stack.name, "vma": "0xc074", "bytes": stack.bytes,
        "capacity_bytes": 12,
    }
    linker = (BUILD / "wplto/c2-substitution.ld").read_text(
        encoding="utf-8")
    require(
        "__lisp65_workbench_overlay_min_start = 0xc354;" in linker
        and "ALIGN(__lisp65_workbench_noinit_end + 1, 2)" not in linker,
        "final linker no longer owns the exact 0xc354 floor")

    facade = truth.section(sections["facade"])
    service = truth.section(sections["far_service"])
    for row in truth.sections:
        if row.bytes == 0 or "SHF_ALLOC" not in row.flags:
            continue
        if row.name in {facade.name, service.name}:
            continue
        if max(row.address, facade.address) < min(
                row.address + row.bytes, facade.address + facade.bytes):
            raise CardError(
                f"ordinary final section overlaps facade: {row.name}")
    return {
        "sections": rows,
        "overlay_floor": "0xc354",
        "ordinary_facade_overlaps": 0,
        "far_window_temporarily_occluded_bytes": 8192,
        "map_unmap_restores_caller_view": True,
        "bank2_packaging": reconstruct_owned_plane(truth),
        "elf": bind(elf),
        "product": bind(
            BUILD / "wplto/lisp65-c2-substitution-linked.prg"),
        "map": bind(
            BUILD / "wplto/lisp65-c2-substitution-linked.prg.map"),
    }


def annotate() -> None:
    value = load(RECEIPT)
    predecessor = load(PREDECESSOR)
    ownership = load(OWNERSHIP_RECEIPT)
    convergence = load(CONVERGENCE)
    sweep = load(SWEEP)
    equivalence = load(EQUIVALENCE)
    phase_c = load(PHASE_C)
    ship = load(SHIP_RECEIPT)
    layout = final_layout()
    require(
        value["static_geometry"]["bank2_static_code_bytes"]
            == EXPECTED_STATIC
        and value["static_geometry"]["entries"] == EXPECTED_ENTRIES
        and value["static_geometry"]["resolutions"]
            == EXPECTED_RESOLUTIONS
        and value["capacity"] == predecessor["capacity"],
        "owned card changed Lisp-plane or Session geometry")
    require(
        ownership["status"] == "PASS"
        and ownership["execution_witness"]["total"] == 125
        and equivalence["status"] == "PASS"
        and equivalence["facts"]["equivalent_cases"] == 16
        and phase_c["status"] == "PASS"
        and phase_c["facts"]["state_executions"] == 72
        and convergence["status"] == "PASS"
        and convergence["execution_witness"] == 8
        and len(convergence["mutations_rejected"]) == 15
        and sweep["status"] == "PASS"
        and sweep["counts"]["linked_submission_sites"] == 13
        and sweep["counts"]["independently_protected_or_verifier"] == 11,
        "ownership/convergence/sweep authority drift")
    walls = value["walls"]
    require(
        walls["bank0_text_headroom_bytes"] >= 0
        and walls["e000_headroom_bytes"] >= 54
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0,
        f"mapped-far card crossed a closed wall: {walls}")
    require(
        ship["status"] == "passed" and ship["executions"] == 1
        and ship["verification"]["members_verified"] == 9,
        "fresh parity-toy witness drift at annotation")
    value.update({
        "format": "lisp65-c2.3-stack-overlay-mapped-far-WPLTO-v1",
        "recorded_on": "2026-08-04",
        "status": "passed-one-mapped-far-service-ownership-WPLTO",
        "wplto_probes_consumed": 1,
        "product_links": 0,
        "hardware_runs": 0,
        "promotable": False,
        "selected_ownership": "mapped-bank2-far-service",
        "owned_layout": layout,
        "static_geometry": {
            **value["static_geometry"],
            "lisp_plane_bytes": EXPECTED_STATIC,
            "mapped_native_suffix_bytes":
                EXPECTED_OWNED_STATIC - EXPECTED_STATIC,
            "owned_bank2_bytes": EXPECTED_OWNED_STATIC,
            "owned_bank2_headroom_bytes": 65536 - EXPECTED_OWNED_STATIC,
        },
        "wall_headroom_delta_from_link90": {
            key: walls[key] - predecessor["walls"][key] for key in walls
        },
        "clean_reconstruction": {
            "new_compiles": 0,
            "new_links": 0,
            "owned_layout_reconstructions": 2,
            "byteidentical_product_shaped_bank2_artifacts": True,
            "sha256": layout["bank2_packaging"]["reconstructions"][0][
                "sha256"],
        },
        "authority": {
            **value["authority"],
            "ownership_contract": bind(CONTRACT),
            "ownership_gate": bind(OWNERSHIP_RECEIPT),
            "code_window_convergence": bind(CONVERGENCE),
            "dma_broaden_once_sweep": bind(SWEEP),
            "assembly_equivalence": bind(EQUIVALENCE),
            "state_ownership_phase_c": bind(PHASE_C),
            "fresh_ship_sample": bind(SHIP_RECEIPT),
            "fresh_ship_image": bind(SHIP_IMAGE),
            "fresh_ship_runtime": bind(SHIP_RUNTIME),
            "fresh_ship_stager": bind(SHIP_STAGER),
            "driver": bind(DRIVER),
        },
        "next_gate": (
            "Halt 2; if accepted, reopen the preserved parity pilot at "
            "the already authorized Link 91 successor"),
        "claim_limit": (
            "One non-promotable product-shaped ownership WPLTO and fresh "
            "host Ship witness; no Link 91, hardware, release or parity "
            "surface claim."),
    })
    value.pop("wall_headroom_delta_from_link83", None)
    RECEIPT.write_bytes(JOINT.CAN.json_bytes(value))


def record_first_red(error: BaseException) -> None:
    wplto_started = BUILD.exists()
    target = FIRST_RED if wplto_started else TOOL_FIRST_RED
    artifacts = []
    for relative in (
        "wplto/resident-island-seed.prg.link.stderr.txt",
        "wplto/resident-island-seed.prg.map",
        "wplto/lisp65-c2-substitution-linked.prg.link.stderr.txt",
        "wplto/lisp65-c2-substitution-linked.prg.map",
        "wplto/c2-substitution.ld",
    ):
        path = BUILD / relative
        if path.is_file():
            artifacts.append(bind(path))
    error_text = str(error)
    failure_stage = "host-preflight"
    seed_link_stderr = (
        BUILD / "wplto/resident-island-seed.prg.link.stderr.txt")
    if wplto_started and seed_link_stderr.is_file():
        # The canonical WPLTO driver currently attempts to build its green
        # receipt after a failed seed link.  Never let a later missing green
        # field mask the first linker failure in the bound First Red.
        error_text = seed_link_stderr.read_text(encoding="utf-8").strip()
        failure_stage = "seed-link"
    value = {
        "format": (
            "lisp65-c2.3-stack-overlay-mapped-far-WPLTO-first-red-v1"
            if wplto_started else
            "lisp65-c2.3-stack-overlay-mapped-far-pre-WPLTO-first-red-v1"),
        "recorded_on": "2026-08-04",
        "status": (
            "FIRST RED: one mapped-far ownership WPLTO did not close"
            if wplto_started else
            "TOOL FIRST RED: mapped-far host gate stopped before WPLTO"),
        "error": error_text,
        "failure_stage": failure_stage,
        "wplto_probes_consumed": int(wplto_started),
        "compiler_invocations": "not-started" if not wplto_started else
            "see-bound-WPLTO-artifacts",
        "linker_invocations": "not-started" if not wplto_started else
            "see-bound-WPLTO-artifacts",
        "product_links": 0,
        "hardware_runs": 0,
        "retry_authorized": not wplto_started,
        "artifacts": artifacts,
        "authority": {
            "contract": bind(CONTRACT),
            "ownership_gate": bind(OWNERSHIP_RECEIPT),
            "driver": bind(DRIVER),
        },
        "claim_limit": (
            "Pre-WPLTO harness classification only; the commissioned single "
            "WPLTO remains unused."
            if not wplto_started else
            "Exact first red from the sole Phase-D WPLTO; no retry, address "
            "negotiation, Link 91 or hardware claim."),
    }
    target.write_bytes(JOINT.CAN.json_bytes(value))


def main() -> int:
    configure()
    try:
        result = JOINT.wplto()
        if result == 0:
            annotate()
            value = load(RECEIPT)
            layout = value["owned_layout"]
            print(
                "c2-stack-overlay-mapped-far-wplto: PASS "
                f"facade={layout['sections']['facade']['bytes']}/243 "
                f"far={layout['sections']['far_service']['bytes']} "
                f"bank2={value['static_geometry']['owned_bank2_bytes']} "
                f"headroom={value['static_geometry']['owned_bank2_headroom_bytes']} "
                f"stack={layout['sections']['static_stack']['bytes']}/12 "
                "overlay=0xc354 probes=1")
        return result
    except (CardError, JOINT.WPLTOError, OSError, KeyError,
            ValueError) as error:
        record_first_red(error)
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, JOINT.WPLTOError, OSError, KeyError,
            ValueError) as error:
        print(f"c2-stack-overlay-mapped-far-wplto: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
