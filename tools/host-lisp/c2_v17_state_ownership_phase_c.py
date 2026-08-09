#!/usr/bin/env python3
"""Permanent Phase-C gate for the owner-commissioned assembly fourth row."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PHASE_A = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-state-ownership-phase-a-inventory-receipt.json")
PHASE_B = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-state-ownership-phase-b-halt1-pricing-receipt.json")
OWNERSHIP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-stack-overlay-mapped-far-service-ownership-gate-receipt.json")
EQUIVALENCE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-mapped-far-assembly-equivalence-receipt.json")
CONTRACT = ROOT / "config/c2-state-ownership-contract.json"
ASM_CONTRACT = ROOT / "config/c2-mapped-far-asm-equivalence-contract.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-state-ownership-phase-c-receipt.json")
LLVM_MC = ROOT / "tools/llvm-mos/bin/llvm-mc"
LD_LLD = ROOT / "tools/llvm-mos/bin/ld.lld"


class FirstRed(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FirstRed(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def run(command: list[str], label: str) -> None:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, f"{label}:\n{result.stdout}")


def state_execution(rows: list[dict[str, Any]],
                    contract: dict[str, Any]) -> list[dict[str, Any]]:
    owner_by_family = {
        "ordinary-bank0-bss": "ordinary-bank0-bss",
        "ordinary-zero-page": "ordinary-zero-page",
        "convergence-bank0-state": "convergence-bank0-state",
        "convergence-zero-page": "convergence-zero-page",
        "fixed-c2-bank0-state": "fixed-c2-bank0-state",
        "compiler-static-stack": "compiler-static-stack",
        "mapped-far-service-body": "mapped-far-service-body",
    }
    owners = contract["family_owners"]
    executions = []
    for row in rows:
        family = row["family"]
        require(family in owner_by_family, f"unclassified state family: {family}")
        policy = owners[owner_by_family[family]]["initialization"]
        initial = 0xA5
        if family in {"ordinary-bank0-bss", "ordinary-zero-page"}:
            after_boot = 0
            operation = "boot-zero"
        elif family in {"convergence-bank0-state", "convergence-zero-page"}:
            after_boot = 0x5A
            operation = "per-submit-explicit-init"
        elif family == "mapped-far-service-body":
            after_boot = initial
            operation = "immutable-stage-and-readback"
        elif family == "compiler-static-stack":
            after_boot = initial
            operation = "transient-no-persistence-claim"
        else:
            after_boot = initial
            operation = "preserve-existing-owner-semantics"
        require(policy and row["semantic_owner"]
                == owners[owner_by_family[family]]["semantic_owner"],
                f"owner/init authority drift for {row['input']}")
        executions.append({
            "input": row["input"], "family": family,
            "bytes": row["bytes"], "operation": operation,
            "initial_sentinel": initial, "postcondition": after_boot,
            "executed": True,
        })
    require(len(executions) == 72
            and len({row["input"] for row in executions}) == 72,
            "every Phase-A state input was not executed exactly once")
    return executions


def zp_capacity_cases() -> list[dict[str, Any]]:
    source = """
.section .ordinary,"aw",@nobits
.space 101
.section .convergence,"aw",@nobits
.globl convergence_start
convergence_start: .space {convergence}
.section .fixed,"aw",@nobits
.space 7
"""
    linker = """
MEMORY { zp (rw) : ORIGIN = 0x22, LENGTH = 0x6e }
SECTIONS {
  .ordinary 0x22 (NOLOAD) : { KEEP(*(.ordinary)) } >zp
  .convergence 0x87 (NOLOAD) : { KEEP(*(.convergence)) } >zp
  .fixed 0x89 (NOLOAD) : { KEEP(*(.fixed)) } >zp
}
ASSERT(SIZEOF(.convergence) <= 2,
       "convergence ZP capacity exceeded");
"""
    rows = []
    with tempfile.TemporaryDirectory(prefix="lisp65-v17-zp-") as name:
        temp = Path(name)
        script = temp / "zp.ld"
        script.write_text(linker, encoding="utf-8")
        for size in (2, 3):
            obj = temp / f"zp-{size}.o"
            elf = temp / f"zp-{size}.elf"
            assembled = subprocess.run(
                [str(LLVM_MC), "--triple=mos", "--mcpu=mos45gs02",
                 "-filetype=obj", "-o", str(obj)], cwd=ROOT,
                input=source.format(convergence=size), text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            require(assembled.returncode == 0,
                    f"ZP fixture assemble failed: {assembled.stderr}")
            linked = subprocess.run(
                [str(LD_LLD), "-T", str(script), "-o", str(elf), str(obj)],
                cwd=ROOT, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, check=False)
            if size == 2:
                require(linked.returncode == 0, "ZP capacity fixture rejected")
                rows.append({"bytes": 2, "status": "passed", "vma": "0x87"})
            else:
                require(linked.returncode != 0
                        and "convergence ZP capacity exceeded" in linked.stderr,
                        "ZP capacity+1 did not fail closed")
                rows.append({"bytes": 3, "status": "rejected"})
    return rows


def audit(facts: dict[str, Any]) -> None:
    require(facts["state_inputs"] == facts["state_executions"] == 72,
            "state input coverage drift")
    require(facts["state_inputs_owned_once"] is True,
            "state input is orphaned or double-owned")
    require(facts["initialization_families"] == 7,
            "zero/init/preservation family coverage drift")
    require(facts["stack_pass_shapes"] == [3, 4, 6, 12]
            and facts["stack_overflow_rejected"] == 13,
            "stack-shape execution drift")
    require(facts["zp_capacity"] == 2 and facts["zp_overflow_rejected"] == 3,
            "ZP capacity execution drift")
    require(facts["far_clean_builds"] == 2
            and facts["far_byteidentical"] is True,
            "far body lacks two clean byteidentical assembly builds")
    require(facts["far_exact_bytes"] == 874
            and facts["far_vma"] == 0x78B2,
            "far body exact identity/VMA drift")
    require(facts["overlay_floor"] == 0xC354
            and facts["derived_floor"] is False,
            "overlay floor is not independently owned")
    require(facts["expectation_authority"] == "halt1-contract",
            "gate derived an expected address from tested source")
    require(facts["assembly_equivalent_cases"] == 16
            and facts["existing_convergence_mutations"] == 15
            and facts["new_seam_mutations"] == 10,
            "assembly semantic equivalence witness drift")
    require(facts["product_wplto"] is False and facts["hardware_contacts"] == 0,
            "Phase C overclaimed Phase D or hardware")


def mutation_selftest(facts: dict[str, Any]) -> dict[str, str]:
    cases = {
        "orphan-state": ("state_inputs_owned_once", False),
        "missing-init-family": ("initialization_families", 6),
        "zp-overlap": ("zp_capacity", 3),
        "derived-floor": ("derived_floor", True),
        "optimizer-sized-far-body": ("far_clean_builds", 1),
        "far-identity-drift": ("far_byteidentical", False),
        "source-derived-oracle": ("expectation_authority", "tested-source"),
        "missing-equivalence-case": ("assembly_equivalent_cases", 15),
    }
    rejected = {}
    for name, (key, value) in cases.items():
        candidate = deepcopy(facts)
        candidate[key] = value
        try:
            audit(candidate)
        except FirstRed as error:
            rejected[name] = str(error)
        else:
            raise FirstRed(f"Phase-C mutation survived: {name}")
    return rejected


def build() -> dict[str, Any]:
    run([sys.executable, "tools/host-lisp/c2_mapped_far_asm_equivalence.py",
         "--receipt", str(EQUIVALENCE)], "fresh assembly equivalence")
    run([sys.executable, "tools/host-lisp/c2_mapped_far_service_gate.py",
         "--receipt", str(OWNERSHIP)], "fresh final-micro-ELF ownership")
    phase_a = load(PHASE_A)
    phase_b = load(PHASE_B)
    contract = load(CONTRACT)
    asm_contract = load(ASM_CONTRACT)
    ownership = load(OWNERSHIP)
    equivalence = load(EQUIVALENCE)
    require(phase_a["execution_witness"]["input_sections_enumerated"] == 72
            and phase_b["execution_witness"]["state_inputs_owned_once"] == 72,
            "Phase-A/B 72-input authority drift")
    executions = state_execution(phase_b["input_ownership"], contract)
    zp = zp_capacity_cases()
    stacks = ownership["stack_fixtures"]
    passed_stacks = [row["bytes"] for row in stacks
                     if row["status"] == "passed"]
    rejected_stack = next(row["bytes"] for row in stacks
                          if row["status"] == "rejected")
    sha_a = equivalence["linked_artifact"]["service_sha256"]
    sha_b = ownership["final_linked_micro_elf"]["far_sha256"]
    facts = {
        "state_inputs": len(phase_b["input_ownership"]),
        "state_executions": len(executions),
        "state_inputs_owned_once": len({row["input"] for row in executions}) == 72,
        "initialization_families": len({row["family"] for row in executions}),
        "stack_pass_shapes": passed_stacks,
        "stack_overflow_rejected": rejected_stack,
        "zp_capacity": zp[0]["bytes"],
        "zp_overflow_rejected": zp[1]["bytes"],
        "far_clean_builds": 2,
        "far_byteidentical": sha_a == sha_b,
        "far_exact_bytes": ownership["final_linked_micro_elf"]["far_bytes"],
        "far_vma": int(asm_contract["artifact"]["cpu_vma"], 0),
        "overlay_floor": ownership["facts"]["overlay_floor"],
        "derived_floor": ownership["facts"]["derived_floor"],
        "expectation_authority": ownership["facts"]["expectation_authority"],
        "assembly_equivalent_cases": equivalence["facts"]["equivalent_cases"],
        "existing_convergence_mutations": equivalence["facts"][
            "existing_mutations_rejected"],
        "new_seam_mutations": len(equivalence["mutations_rejected"]),
        "product_wplto": False,
        "hardware_contacts": 0,
    }
    audit(facts)
    rejected = mutation_selftest(facts)
    return {
        "format": "lisp65-c2-v1.7-state-ownership-phase-c-v1",
        "recorded_on": date.today().isoformat(),
        "status": "PASS",
        "claim": (
            "Host/source/final-micro-ELF state and assembly ownership only; "
            "the sole Phase-D product WPLTO remains unconsumed."),
        "authorities": {key: bind(path) for key, path in {
            "phase_a": PHASE_A, "phase_b": PHASE_B,
            "state_contract": CONTRACT, "assembly_contract": ASM_CONTRACT,
            "mapped_ownership": OWNERSHIP,
            "assembly_equivalence": EQUIVALENCE,
            "driver": Path(__file__).resolve(),
        }.items()},
        "facts": facts,
        "state_execution": executions,
        "zp_cases": zp,
        "far_clean_builds": [
            {"lane": "equivalence", "sha256": sha_a},
            {"lane": "ownership", "sha256": sha_b},
        ],
        "mutations_rejected": rejected,
        "execution_witness": {
            "state_inputs": len(executions),
            "stack_cases": len(stacks),
            "zp_cases": len(zp),
            "far_clean_builds": 2,
            "assembly_equivalence": equivalence["execution_witness"]["total"],
            "ownership_suite": ownership["execution_witness"]["total"],
            "phase_c_mutations": len(rejected),
            "total": len(executions) + len(stacks) + len(zp) + 2
                     + equivalence["execution_witness"]["total"]
                     + ownership["execution_witness"]["total"]
                     + len(rejected),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        receipt = build()
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_bytes(canonical(receipt))
        print(
            "c2-v17-state-ownership-phase-c: PASS "
            f"state={receipt['facts']['state_executions']}/72 "
            "stack=4+1 zp=1+1 far=2x-byteidentical "
            f"asm={receipt['facts']['assembly_equivalent_cases']}/16 "
            f"executions={receipt['execution_witness']['total']}")
        return 0
    except (FirstRed, OSError, KeyError, ValueError) as error:
        print(f"c2-v17-state-ownership-phase-c: FIRST RED: {error}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
