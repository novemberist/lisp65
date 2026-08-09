#!/usr/bin/env python3
"""Phase-B ownership pricing for the v1.7 state-ownership block."""

from __future__ import annotations

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
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402
import c2_stack_overlay_ownership as OWN  # noqa: E402


READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
LLVM_MC = ROOT / "tools/llvm-mos/bin/llvm-mc"
LD_LLD = ROOT / "tools/llvm-mos/bin/ld.lld"
CONTRACT = ROOT / "config/c2-state-ownership-contract.json"
PHASE_A = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-state-ownership-phase-a-inventory-receipt.json")
V15_CONTRACT = ROOT / "config/c2-stack-overlay-ownership-contract.json"
V15_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-stack-overlay-mapped-far-service-wplto-first-red.json")
PLAN = ROOT / "docs/planning/1.7-state-ownership-work-plan.md"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-state-ownership-phase-b-halt1-pricing-receipt.json")


class FirstRed(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FirstRed(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def parse(value: str | int) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def section_lma(path: Path, section_name: str) -> int:
    structured, raw, headers = OWN.read_elf(path)
    row = structured.section(section_name)
    return OWN.section_lma(row, raw[row.index], headers)


def fixture_source(stack_bytes: int) -> str:
    return f"""
.section .lisp65_fixture_far,"ax",@progbits
.space 1433, 0xea

.section .lisp65_fixture_bss,"aw",@nobits
.space 1585
.section .lisp65_fixture_convergence,"aw",@nobits
.space 66
.section .lisp65_fixture_stack,"aw",@nobits
.space {stack_bytes}
.section .lisp65_fixture_fixed_state,"aw",@nobits
.space 408
.section .lisp65_fixture_fixed_code,"ax",@progbits
.space 69, 0xea
.section .lisp65_fixture_fixed_hot,"aw",@nobits
.space 240
.section .lisp65_fixture_overlay,"ax",@progbits
.byte 0xea

.section .lisp65_fixture_zp_ordinary,"aw",@nobits
.space 101
.section .lisp65_fixture_zp_convergence,"aw",@nobits
.space 2
.section .lisp65_fixture_zp_fixed,"aw",@nobits
.space 7
""".strip() + "\n"


def fixture_linker() -> str:
    return """
MEMORY {
  zp (rw) : ORIGIN = 0x22, LENGTH = 0x6e
  ram (rwx) : ORIGIN = 0x2000, LENGTH = 0xe000
  farload (rx) : ORIGIN = 0x2b8b2, LENGTH = 1499
}
SECTIONS {
  .lisp65_fixture_zp_ordinary 0x22 (NOLOAD) : {
    KEEP(*(.lisp65_fixture_zp_ordinary))
  } >zp
  .lisp65_fixture_zp_convergence 0x87 (NOLOAD) : {
    KEEP(*(.lisp65_fixture_zp_convergence))
  } >zp
  .lisp65_fixture_zp_fixed 0x89 (NOLOAD) : {
    KEEP(*(.lisp65_fixture_zp_fixed))
  } >zp
  .lisp65_fixture_far 0x78b2 : {
    KEEP(*(.lisp65_fixture_far))
  } >ram AT>farload
  .lisp65_fixture_bss 0xb9c8 (NOLOAD) : {
    KEEP(*(.lisp65_fixture_bss))
  } >ram
  .lisp65_fixture_convergence 0xc000 (NOLOAD) : {
    KEEP(*(.lisp65_fixture_convergence))
  } >ram
  .lisp65_fixture_stack 0xc074 (NOLOAD) : {
    KEEP(*(.lisp65_fixture_stack))
  } >ram
  .lisp65_fixture_fixed 0xc080 : {
    KEEP(*(.lisp65_fixture_fixed_state))
    KEEP(*(.lisp65_fixture_fixed_code))
    KEEP(*(.lisp65_fixture_fixed_hot))
  } >ram
  .lisp65_fixture_overlay 0xc354 : {
    KEEP(*(.lisp65_fixture_overlay))
  } >ram
}
ASSERT(SIZEOF(.lisp65_fixture_bss) <= 1592,
       "ordinary state arena overflow");
ASSERT(SIZEOF(.lisp65_fixture_convergence) == 66,
       "convergence state size drift");
ASSERT(SIZEOF(.lisp65_fixture_stack) <= 12,
       "compiler stack arena overflow");
ASSERT(SIZEOF(.lisp65_fixture_fixed) == 717,
       "fixed C2 arena drift");
ASSERT(SIZEOF(.lisp65_fixture_zp_ordinary) == 101 &&
       SIZEOF(.lisp65_fixture_zp_convergence) == 2 &&
       SIZEOF(.lisp65_fixture_zp_fixed) == 7,
       "zero-page ownership drift");
ASSERT(SIZEOF(.lisp65_fixture_far) <= LENGTH(farload),
       "far owner capacity overflow");
ASSERT(ADDR(.lisp65_fixture_overlay) == 0xc354,
       "overlay floor drift");
""".strip() + "\n"


def run(command: list[str], *, input_text: str | None = None,
        expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command, cwd=ROOT, text=True, input=input_text,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(result.returncode == expect,
            f"fixture command exit={result.returncode}: {result.stderr}")
    return result


def micro_fixtures() -> dict[str, Any]:
    rows = []
    linker = fixture_linker()
    with tempfile.TemporaryDirectory(prefix="lisp65-v17-state-price-") as name:
        temp = Path(name)
        script = temp / "owned.ld"
        script.write_text(linker, encoding="utf-8")
        final: dict[str, Any] | None = None
        for stack_bytes in (3, 4, 6, 12, 13):
            obj = temp / f"owned-{stack_bytes}.o"
            elf = temp / f"owned-{stack_bytes}.elf"
            run([str(LLVM_MC), "--triple=mos", "--mcpu=mos45gs02",
                 "-filetype=obj", "-o", str(obj)],
                input_text=fixture_source(stack_bytes))
            linked = subprocess.run(
                [str(LD_LLD), "--emit-relocs", "-T", str(script),
                 "-o", str(elf), str(obj)], cwd=ROOT, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if stack_bytes == 13:
                require(linked.returncode != 0
                        and "compiler stack arena overflow" in linked.stderr,
                        "13-byte stack did not fail closed")
                rows.append({"stack_bytes": 13, "status": "rejected"})
                continue
            require(linked.returncode == 0,
                    f"owned-state fixture link failed: {linked.stderr}")
            truth = ElfTruth.read(
                elf, llvm_readobj=READOBJ, include_section_data=True)
            observed = {
                "ordinary": (truth.section(".lisp65_fixture_bss").address,
                             truth.section(".lisp65_fixture_bss").bytes),
                "convergence": (
                    truth.section(".lisp65_fixture_convergence").address,
                    truth.section(".lisp65_fixture_convergence").bytes),
                "stack": (truth.section(".lisp65_fixture_stack").address,
                          truth.section(".lisp65_fixture_stack").bytes),
                "fixed": (truth.section(".lisp65_fixture_fixed").address,
                          truth.section(".lisp65_fixture_fixed").bytes),
                "overlay": truth.section(".lisp65_fixture_overlay").address,
                "zp": (
                    truth.section(".lisp65_fixture_zp_ordinary").address,
                    truth.section(".lisp65_fixture_zp_convergence").address,
                    truth.section(".lisp65_fixture_zp_fixed").address),
                "far": (truth.section(".lisp65_fixture_far").address,
                        truth.section(".lisp65_fixture_far").bytes,
                        section_lma(elf, ".lisp65_fixture_far")),
            }
            require(observed == {
                "ordinary": (0xB9C8, 1585),
                "convergence": (0xC000, 66),
                "stack": (0xC074, stack_bytes),
                "fixed": (0xC080, 717),
                "overlay": 0xC354,
                "zp": (0x22, 0x87, 0x89),
                "far": (0x78B2, 1433, 0x2B8B2),
            }, f"owned-state micro geometry drift: {observed}")
            rows.append({
                "stack_bytes": stack_bytes,
                "status": "passed",
                "overlay_floor": "0xc354",
                "far_payload_bytes": 1433,
                "far_owner_capacity_bytes": 1499,
            })
            if stack_bytes == 12:
                final = {
                    "elf_bytes": elf.stat().st_size,
                    "elf_sha256": sha(elf),
                    "linker_sha256": hashlib.sha256(
                        linker.encode()).hexdigest(),
                    "far_lma": "0x0002b8b2",
                }
        require(final is not None, "12-byte micro fixture absent")
    return {"stack_cases": rows, "twelve_byte_fixture": final}


def build() -> dict[str, Any]:
    contract = load(CONTRACT)
    require(contract["format"] == "lisp65-c2-state-ownership-contract-v2",
            "Phase-B ownership-contract format drift")
    phase_a = load(PHASE_A)
    owners = contract["family_owners"]
    assignments = []
    for row in phase_a["failed_product_input_state"]:
        family = row["family"]
        require(family in owners, f"state input has no Phase-B owner: {row['id']}")
        owner = owners[family]
        assignments.append({
            "input": row["id"],
            "bytes": row["bytes"],
            "family": family,
            "semantic_owner": owner["semantic_owner"],
            "arena": owner["arena"],
        })
    fixture = micro_fixtures()
    value = {
        "format": "lisp65-c2.3-v1.7-state-ownership-phase-b-pricing-v1",
        "recorded_on": date.today().isoformat(),
        "status": "halt1-zero-of-three-structural-rows-fit",
        "claim": contract["claim"],
        "authorities": {
            "contract": bind(CONTRACT),
            "phase_A": bind(PHASE_A),
            "v15_contract": bind(V15_CONTRACT),
            "v15_First_Red": bind(V15_FIRST_RED),
            "plan": bind(PLAN),
            "tool": bind(Path(__file__).resolve()),
        },
        "execution_witness": {
            "state_inputs_owned_once": len(assignments),
            "state_families": len(owners),
            "micro_stack_cases": 5,
            "candidate_rows_priced": len(contract["candidate_rows"]),
            "negative_mutations": 7,
        },
        "input_ownership": assignments,
        "arena_skeleton": contract["arena_skeleton"],
        "micro_fixture": fixture,
        "candidate_rows": contract["candidate_rows"],
        "decision": contract["halt1"],
        "reading": {
            "state_and_zp": "One geometric skeleton fits: 1585/1592 Bank-0 bytes and the exact 0x87..0x89 ZP gap.",
            "far_body": "The micro ELF proves VMA/LMA and 1433/1499 capacity, but not exact optimizer-independent code identity.",
            "why_zero_fit": "Each cheap far-body closure is explicitly forbidden: current-output repin, padding, or compiler/frozen-object partition.",
            "not_priced": "A separately proved assembly implementation would be a new semantic implementation owner, not an ownership-only Phase-C step; adding it would be an owner charter extension and a fourth row.",
        },
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    require(value["status"] == "halt1-zero-of-three-structural-rows-fit",
            "Phase-B status drift")
    assignments = value["input_ownership"]
    require(len(assignments) == 72
            and len({row["input"] for row in assignments}) == 72,
            "state input missing or duplicated")
    require(all(isinstance(row["semantic_owner"], str)
                and row["semantic_owner"] and isinstance(row["arena"], str)
                and row["arena"] for row in assignments),
            "state input ownership is not singular")
    arenas = value["arena_skeleton"]
    bank0 = arenas["ordinary_bank0_state"]
    require((bank0["capacity_bytes"], bank0["demand_bytes"],
             bank0["headroom_bytes"]) == (1592, 1585, 7),
            "Bank-0 skeleton price drift")
    zp = arenas["zero_page"]
    require((parse(zp["ordinary_end_exclusive"]),
             parse(zp["convergence_gap_start"]),
             parse(zp["convergence_gap_end_exclusive"]),
             parse(zp["fixed_start"]), parse(zp["fixed_end_exclusive"]),
             parse(zp["capacity_end_exclusive"])) ==
            (0x87, 0x87, 0x89, 0x89, 0x90, 0x90),
            "zero-page skeleton is not contiguous/exact")
    far = arenas["mapped_far"]
    require((far["owner_capacity_bytes"],
             far["observed_product_LTO_payload_bytes"],
             far["identity_delta_bytes"]) == (1499, 1433, -66),
            "far identity drift hidden")
    rows = value["candidate_rows"]
    require(len(rows) == 3 and value["decision"]["priced"] == 3
            and value["decision"]["fits"] == 0
            and value["decision"]["no_fourth_row"] is True,
            "candidate-count or Halt-1 disposition drift")
    require([row["status"] for row in rows] == [
        "rejected-current-output-repin", "rejected-padding",
        "rejected-partition"], "forbidden candidate survived pricing")
    cases = value["micro_fixture"]["stack_cases"]
    require([row["status"] for row in cases] ==
            ["passed", "passed", "passed", "passed", "rejected"],
            "micro stack execution witness drift")


def selftest() -> None:
    base = build()
    mutations: list[tuple[str, dict[str, Any]]] = []
    row = deepcopy(base)
    row["input_ownership"].pop()
    mutations.append(("missing-state-input", row))
    row = deepcopy(base)
    row["input_ownership"][0]["semantic_owner"] = ["one", "two"]
    mutations.append(("double-owner", row))
    row = deepcopy(base)
    row["arena_skeleton"]["ordinary_bank0_state"]["headroom_bytes"] = 8
    mutations.append(("falsified-bank0-fit", row))
    row = deepcopy(base)
    row["arena_skeleton"]["zero_page"]["convergence_gap_start"] = "0x88"
    mutations.append(("zp-gap-drift", row))
    for index, name in enumerate(("repin", "padding", "partition")):
        row = deepcopy(base)
        row["candidate_rows"][index]["status"] = "green"
        mutations.append((f"forbidden-{name}-accepted", row))
    rejected = 0
    for name, row in mutations:
        try:
            validate(row)
        except FirstRed:
            rejected += 1
        else:
            raise FirstRed(f"selftest mutation survived: {name}")
    require(rejected == 7, "selftest execution count drift")
    print("c2-v17-state-ownership-phase-b: SELFTEST PASS mutations=7")


def run_receipt() -> None:
    value = build()
    RECEIPT.write_bytes(canonical(value))
    print("c2-v17-state-ownership-phase-b: PASS "
          "owners=72 micro=5 candidates=3 fits=0 mutations=7")


def check() -> None:
    value = build()
    require(RECEIPT.is_file() and RECEIPT.read_bytes() == canonical(value),
            "Phase-B pricing receipt drift")
    print("c2-v17-state-ownership-phase-b: PASS "
          "owners=72 micro=5 candidates=3 fits=0 mutations=7")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    try:
        if action == "selftest":
            selftest()
        elif action == "run":
            run_receipt()
        elif action == "check":
            check()
        else:
            print(f"usage: {Path(sys.argv[0]).name} <selftest|run|check>",
                  file=sys.stderr)
            return 2
    except (FirstRed, KeyError, TypeError, ValueError, OSError) as error:
        print(f"c2-v17-state-ownership-phase-b: FIRST RED: {error}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
