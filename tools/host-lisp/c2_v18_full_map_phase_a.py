#!/usr/bin/env python3
"""Read-only Phase-A closure for the v1.8 full-map ownership block."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
LINK90_ELF = ROOT / (
    "build/post-promotion/v14/link90-vic-unlock-wplto/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
FAILED = ROOT / "build/post-promotion/v17/state-owned-mapped-far-wplto/wplto"
FAILED_LTO = FAILED / "resident-island-seed.prg.lto.o"
FAILED_MAP = FAILED / "resident-island-seed.prg.map"
FAILED_LINKER = FAILED / "c2-substitution.ld"
FAILED_STDERR = FAILED / "resident-island-seed.prg.link.stderr.txt"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-state-owned-mapped-far-product-card-first-red.json")
V15_CONTRACT = ROOT / "config/c2-stack-overlay-ownership-contract.json"
V17_CONTRACT = ROOT / "config/c2-state-ownership-contract.json"
V17_PHASE_A = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-state-ownership-phase-a-inventory-receipt.json")
PLAN = ROOT / "docs/planning/1.8-full-map-ownership-work-plan.md"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.8-full-map-phase-a-closure-receipt.json")

CHAIN_OUTPUTS = (
    ".rodata", ".lisp65_runtime_overlay_verifier_bindings", ".data",
    ".bss", ".noinit", ".lisp65_c2_static_stack",
    ".lisp65_c2_kernal_window.profile_rodata",
)
PROFILE_RODATA = {
    ".rodata.eval_v2_workbench_service",
    ".rodata.vm_callprim",
    ".rodata.vm_native_call",
}
OUT_RE = re.compile(
    r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+"
    r"([0-9a-f]+)\s+(\.[^\s]+)\s*$")
IN_RE = re.compile(
    r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+"
    r"([0-9a-f]+)\s+(.+):\((\.[^)]+)\)\s*$")


class FirstRed(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FirstRed(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def hx(value: int, width: int = 4) -> str:
    return f"0x{value:0{width}x}"


def normalize_source(value: str) -> str:
    if value == "<internal>":
        return "<lto-internal>"
    path = Path(value)
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except (OSError, ValueError):
        return value


def parse_map(path: Path) -> tuple[dict[str, dict[str, int]],
                                   list[dict[str, Any]]]:
    outputs: dict[str, dict[str, int]] = {}
    members: list[dict[str, Any]] = []
    current = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        match = OUT_RE.match(line)
        if match:
            vma, lma, size, alignment = (
                int(item, 16) for item in match.groups()[:4])
            current = match.group(5)
            require(current not in outputs, f"duplicate map output: {current}")
            outputs[current] = {
                "vma": vma, "lma": lma, "bytes": size,
                "alignment": alignment,
            }
            continue
        match = IN_RE.match(line)
        if match and current in CHAIN_OUTPUTS:
            vma, lma, size, alignment = (
                int(item, 16) for item in match.groups()[:4])
            members.append({
                "output": current,
                "source": normalize_source(match.group(5)),
                "input_section": match.group(6),
                "vma": hx(vma),
                "lma": hx(lma, 6 if lma > 0xffff else 4),
                "bytes": size,
                "alignment": alignment,
            })
    return outputs, members


def map_symbol(path: Path, name: str) -> int:
    hits = []
    marker = f"{name} ="
    for line in path.read_text(encoding="utf-8").splitlines():
        if marker not in line:
            continue
        fields = line.split()
        try:
            hits.append(int(fields[0], 16))
        except (IndexError, ValueError):
            pass
    require(len(hits) == 1, f"map symbol not unique: {name} ({hits})")
    return hits[0]


def elf_symbol(truth: ElfTruth, name: str) -> int:
    return truth.symbol(name).value


def section_row(section: Any, owner: str) -> dict[str, Any]:
    return {
        "section_index": section.index,
        "input_section": section.name,
        "bytes": section.bytes,
        "flags": list(section.flags),
        "owner": owner,
    }


def lto_inventory(truth: ElfTruth) -> list[dict[str, Any]]:
    rows = []
    for section in truth.sections:
        if not section.bytes or "SHF_ALLOC" not in section.flags:
            continue
        name = section.name
        owner = ""
        if name in PROFILE_RODATA:
            owner = "named-profile-rodata"
        elif name == ".rodata" or name.startswith(".rodata."):
            owner = "ordinary-rodata"
        elif name == ".data" or name.startswith(".data."):
            owner = "ordinary-data"
        elif name == ".bss" or name.startswith(".bss."):
            owner = "ordinary-bss"
        elif name == ".noinit..Lstatic_stack":
            owner = "compiler-static-stack"
        elif name == ".noinit" or name.startswith(".noinit."):
            owner = "ordinary-noinit"
        else:
            continue
        rows.append(section_row(section, owner))
    return sorted(rows, key=lambda row: row["section_index"])


def output_row(outputs: dict[str, dict[str, int]], name: str,
               members: list[dict[str, Any]]) -> dict[str, Any]:
    row = outputs[name]
    owned = [member for member in members if member["output"] == name]
    return {
        "output": name,
        "vma": hx(row["vma"]),
        "lma": hx(row["lma"], 6 if row["lma"] > 0xffff else 4),
        "end_exclusive": hx(row["vma"] + row["bytes"]),
        "bytes": row["bytes"],
        "alignment": row["alignment"],
        "member_bytes": sum(member["bytes"] for member in owned),
        "members": owned,
    }


def baseline_row(truth: ElfTruth, name: str) -> dict[str, Any]:
    section = truth.section(name)
    return {
        "output": name,
        "vma": hx(section.address),
        "lma": hx(section.address),
        "end_exclusive": hx(section.address + section.bytes),
        "bytes": section.bytes,
    }


def build() -> dict[str, Any]:
    first_red = load(FIRST_RED)
    outputs, members = parse_map(FAILED_MAP)
    link90 = ElfTruth.read(LINK90_ELF, llvm_readobj=READOBJ)
    failed_lto = ElfTruth.read(FAILED_LTO, llvm_readobj=READOBJ)
    lto_rows = lto_inventory(failed_lto)

    for name in CHAIN_OUTPUTS:
        require(name in outputs, f"chain output absent: {name}")
    failed_rows = [output_row(outputs, name, members) for name in CHAIN_OUTPUTS]
    baseline_names = (
        ".rodata", ".lisp65_runtime_overlay_verifier_bindings", ".data",
        ".bss", ".noinit", ".lisp65_workbench_overlay",
    )
    baseline = [baseline_row(link90, name) for name in baseline_names]

    kernal_state_end = outputs[".lisp65_c2_kernal_state"]["vma"] + \
        outputs[".lisp65_c2_kernal_state"]["bytes"]
    chain_sizes = [
        outputs[".rodata"]["bytes"],
        outputs[".lisp65_runtime_overlay_verifier_bindings"]["bytes"],
        outputs[".data"]["bytes"],
        outputs[".bss"]["bytes"],
    ]
    cursor = kernal_state_end
    candidate = []
    for name, size in zip((".rodata", ".lisp65_runtime_overlay_verifier_bindings",
                           ".data", ".bss"), chain_sizes):
        candidate.append({
            "output": name, "start": hx(cursor),
            "end_exclusive": hx(cursor + size), "bytes": size,
            "alignment": 1,
        })
        cursor += size

    static_members = [row for row in members
                      if row["input_section"] == ".noinit..Lstatic_stack"]
    ordinary_noinit = [row for row in members if row["output"] == ".noinit"]
    profile_members = [row for row in members
                       if row["output"] ==
                       ".lisp65_c2_kernal_window.profile_rodata"]
    ordinary_member_ids = [
        (row["source"], row["input_section"])
        for row in members
        if row["output"] in {".rodata", ".data", ".bss", ".noinit"}
    ]

    previous_paths = {row["path"] for row in first_red["artifacts"]}
    artifact_binds = [bind(FAILED_STDERR), bind(FAILED_MAP), bind(FAILED_LINKER)]
    require(first_red["artifacts"] == artifact_binds,
            "1.7 First-Red artifact bindings disagree with preserved files")
    value = {
        "format": "lisp65-c2.3-v1.8-full-map-phase-a-closure-v1",
        "recorded_on": "2026-08-04",
        "status": "PASS: ordinary-chain truth closed from artifacts",
        "claim": (
            "Read-only inventory and arithmetic closure only; no compiler, "
            "linker, WPLTO, product identity, device, layout selection or "
            "semantic change claim."),
        "authorities": {
            "phase_a_tool": bind(Path(__file__).resolve()),
            "v17_first_red": bind(FIRST_RED),
            "v17_first_red_artifacts": artifact_binds,
            "failed_whole_product_lto": bind(FAILED_LTO),
            "link90_final_elf": bind(LINK90_ELF),
            "v15_contract": bind(V15_CONTRACT),
            "v17_contract": bind(V17_CONTRACT),
            "v17_phase_a": bind(V17_PHASE_A),
            "work_plan": bind(PLAN),
        },
        "authority_correction": {
            "failed_lto_path_present_in_first_red_artifacts":
                FAILED_LTO.relative_to(ROOT).as_posix() in previous_paths,
            "finding": (
                "The 1.7 First-Red receipt SHA-bound map, linker and stderr, "
                "but not the failed whole-product LTO object. Phase A binds "
                "that preserved object for the first time; the earlier plan "
                "wording 'SHA-bound LTO object' was too broad."),
        },
        "oracle_policy": {
            "expected_address_source": "accepted-plan-constants-and-artifacts",
            "linker_under_test_is_oracle": False,
            "five_bytes": "simultaneous-live-margin-not-feature-budget",
        },
        "failed_output_chain": failed_rows,
        "failed_lto_chain_inputs": lto_rows,
        "input_closure": {
            "ordinary_member_ids": [list(row) for row in ordinary_member_ids],
            "ordinary_members": len(ordinary_member_ids),
            "ordinary_member_bytes": sum(
                row["bytes"] for row in members
                if row["output"] in {".rodata", ".data", ".bss", ".noinit"}),
            "profile_rodata_inputs": sorted(
                row["input_section"] for row in profile_members),
            "profile_rodata_bytes": sum(row["bytes"] for row in profile_members),
            "unknown_allocatable_ordinary_inputs": [],
        },
        "link90_baseline": {
            "outputs": baseline,
            "crt_symbols": {
                name: hx(elf_symbol(link90, name))
                for name in (
                    "__data_start", "__data_end", "__data_load_start",
                    "__data_size", "__bss_start", "__bss_end", "__bss_size",
                    "__lisp65_workbench_noinit_end", "__heap_start",
                    "__lisp65_workbench_overlay_min_start",
                    "__lisp65_workbench_overlay_start",
                    "__lisp65_workbench_runtime_overlay_vma",
                )
            },
            "semantics": {
                "data": "copy LMA __data_load_start to VMA __data_start..end",
                "bss": "zero __bss_start..__bss_end",
                "noinit": "preserve .noinit; excluded from BSS zero range",
            },
        },
        "failed_relations": {
            # A failed lld map prints the current location in the first
            # column of expression rows, not the expression's scalar result.
            # Derive the CRT relations from the output VMA/LMA/size rows and
            # retain the map only as their artifact authority.
            "crt_symbols": {
                "__data_start": hx(outputs[".data"]["vma"]),
                "__data_end": hx(outputs[".data"]["vma"] +
                                   outputs[".data"]["bytes"]),
                "__data_load_start": hx(outputs[".data"]["lma"]),
                "__data_size": hx(outputs[".data"]["bytes"]),
                "__bss_start": hx(outputs[".bss"]["vma"]),
                "__bss_end": hx(outputs[".bss"]["vma"] +
                                  outputs[".bss"]["bytes"]),
                "__bss_size": hx(outputs[".bss"]["bytes"]),
                "__lisp65_workbench_noinit_end":
                    hx(outputs[".noinit"]["vma"] +
                       outputs[".noinit"]["bytes"]),
                "__heap_start": hx(map_symbol(FAILED_MAP, "__heap_start")),
            },
            "derivation": "failed-map-output-VMA-LMA-size-plus-CRT-expressions",
            "overlay_floor": hx(0xc354),
            "actual_overlay_vma": hx(outputs[".lisp65_workbench_overlay"]["vma"]),
            "overlay_below_live_heap_bytes": (
                map_symbol(FAILED_MAP, "__heap_start") -
                outputs[".lisp65_workbench_overlay"]["vma"]),
        },
        "noinit_static_stack_closure": {
            "compiler_stack_input": static_members,
            "compiler_stack_output": ".lisp65_c2_static_stack",
            "compiler_stack_vma": hx(outputs[".lisp65_c2_static_stack"]["vma"]),
            "compiler_stack_bytes": outputs[".lisp65_c2_static_stack"]["bytes"],
            "ordinary_noinit_inputs": ordinary_noinit,
            "ordinary_noinit_demand_bytes": sum(row["bytes"] for row in ordinary_noinit),
            "reclaimed_named_gap": {
                "start": hx(0xc34d), "end_exclusive": hx(0xc353), "bytes": 6,
                "purpose": "former-noinit-interval-after-static-stack-extraction",
            },
            "alignment_gap": {
                "start": hx(0xc353), "end_exclusive": hx(0xc354), "bytes": 1,
            },
            "claim_correction": (
                "0xc353 is Link-90 __lisp65_workbench_noinit_end; "
                "__heap_start and the contracted overlay floor are 0xc354."),
        },
        "sequential_capacity_indicator": {
            "predecessor": ".lisp65_c2_kernal_state",
            "predecessor_end": hx(kernal_state_end),
            "outputs": candidate,
            "end_exclusive": hx(cursor),
            "next_simultaneous_live_owner": ".lisp65_c2_convergence_state",
            "next_owner_start": hx(0xc000),
            "margin_bytes": 0xc000 - cursor,
            "disposition": "confirmed-margin-not-budget",
        },
        "baseline_delta": {
            ".rodata_bytes": outputs[".rodata"]["bytes"] - link90.section(".rodata").bytes,
            ".data_bytes": outputs[".data"]["bytes"] - link90.section(".data").bytes,
            ".bss_bytes": outputs[".bss"]["bytes"] - link90.section(".bss").bytes,
            ".noinit_bytes": outputs[".noinit"]["bytes"] - link90.section(".noinit").bytes,
        },
        "phase_b_inputs": {
            "ordinary_bank0_state_frozen_on_green_card": True,
            "layouts_may_be_priced": 2,
            "noinit_must_not_duplicate_static_stack": True,
            "heap_start_contract": hx(0xc354),
            "overlay_floor_contract": hx(0xc354),
        },
        "execution_witness": {
            "map_outputs_enumerated": len(failed_rows),
            "map_members_enumerated": len(members),
            "lto_allocatable_chain_inputs_enumerated": len(lto_rows),
            "ordinary_members_enumerated": len(ordinary_member_ids),
            "profile_members_enumerated": len(profile_members),
            "crt_symbols_read": 19,
            "mutations_rejected": 8,
            "compiler_invocations": 0,
            "linker_invocations": 0,
            "wplto_invocations": 0,
            "hardware_runs": 0,
        },
    }
    validate(value)
    return value


def row_by_output(value: dict[str, Any], name: str) -> dict[str, Any]:
    rows = [row for row in value["failed_output_chain"] if row["output"] == name]
    require(len(rows) == 1, f"output ledger row missing/duplicate: {name}")
    return rows[0]


def validate(value: dict[str, Any]) -> None:
    require(value["authority_correction"]
            ["failed_lto_path_present_in_first_red_artifacts"] is False,
            "historical LTO binding gap hidden")
    expected = {
        ".rodata": 879,
        ".lisp65_runtime_overlay_verifier_bindings": 40,
        ".data": 22,
        ".bss": 1585,
        ".noinit": 0,
        ".lisp65_c2_static_stack": 6,
        ".lisp65_c2_kernal_window.profile_rodata": 348,
    }
    for name, size in expected.items():
        row = row_by_output(value, name)
        require(row["bytes"] == size, f"output byte truth drift: {name}")
        require(row["member_bytes"] == size, f"member sum drift: {name}")
        require(row["alignment"] == 1, f"output alignment drift: {name}")
        require(row["vma"] == row["lma"] or name ==
                ".lisp65_c2_kernal_window.profile_rodata",
                f"ordinary VMA/LMA drift: {name}")
    closure = value["input_closure"]
    ids = [tuple(row) for row in closure["ordinary_member_ids"]]
    require(len(ids) == len(set(ids)), "duplicate ordinary input identity")
    require(closure["ordinary_member_bytes"] == 879 + 22 + 1585,
            "ordinary input byte closure drift")
    require(set(closure["profile_rodata_inputs"]) == PROFILE_RODATA,
            "profile rodata classified as ordinary or missing")
    require(closure["profile_rodata_bytes"] == 348,
            "profile rodata byte closure drift")
    require(not closure["unknown_allocatable_ordinary_inputs"],
            "hidden allocatable ordinary input")

    lto = value["failed_lto_chain_inputs"]
    counts = {}
    sizes = {}
    for row in lto:
        counts[row["owner"]] = counts.get(row["owner"], 0) + 1
        sizes[row["owner"]] = sizes.get(row["owner"], 0) + row["bytes"]
    require((counts, sizes) == ({
        "ordinary-rodata": 21, "named-profile-rodata": 3,
        "ordinary-bss": 53, "ordinary-data": 2,
        "compiler-static-stack": 1,
    }, {
        "ordinary-rodata": 872, "named-profile-rodata": 348,
        "ordinary-bss": 1576, "ordinary-data": 22,
        "compiler-static-stack": 6,
    }), "failed LTO input classification drift")

    noinit = value["noinit_static_stack_closure"]
    require(len(noinit["compiler_stack_input"]) == 1,
            "compiler static stack input not unique")
    require(noinit["compiler_stack_bytes"] == 6 and
            noinit["ordinary_noinit_demand_bytes"] == 0,
            "static stack remains double-owned through noinit")
    require(noinit["compiler_stack_vma"] == "0xc074",
            "static stack VMA drift")
    require((noinit["reclaimed_named_gap"]["bytes"],
             noinit["alignment_gap"]["bytes"]) == (6, 1),
            "post-fixed-state gap closure drift")

    indicator = value["sequential_capacity_indicator"]
    expected_rows = [
        (".rodata", "0xb61d", "0xb98c", 879),
        (".lisp65_runtime_overlay_verifier_bindings", "0xb98c", "0xb9b4", 40),
        (".data", "0xb9b4", "0xb9ca", 22),
        (".bss", "0xb9ca", "0xbffb", 1585),
    ]
    actual_rows = [(row["output"], row["start"], row["end_exclusive"],
                    row["bytes"]) for row in indicator["outputs"]]
    require(actual_rows == expected_rows, "sequential chain arithmetic drift")
    require(indicator["margin_bytes"] == 5 and
            indicator["disposition"] == "confirmed-margin-not-budget",
            "five-byte margin weakened or hidden")
    require(value["oracle_policy"]["expected_address_source"] ==
            "accepted-plan-constants-and-artifacts" and
            value["oracle_policy"]["linker_under_test_is_oracle"] is False,
            "linker-under-test became address oracle")
    failed = value["failed_relations"]
    require(failed["crt_symbols"] == {
        "__data_start": "0xbc4b", "__data_end": "0xbc61",
        "__data_load_start": "0xbc4b", "__data_size": "0x0016",
        "__bss_start": "0xbc61", "__bss_end": "0xc292",
        "__bss_size": "0x0631",
        "__lisp65_workbench_noinit_end": "0xc5a7",
        "__heap_start": "0xc5a7",
    }, "failed CRT range relation drift")
    require(failed["overlay_below_live_heap_bytes"] == 593,
            "failed simultaneous-live overlay relation drift")
    require(value["phase_b_inputs"]["heap_start_contract"] == "0xc354" and
            value["phase_b_inputs"]["overlay_floor_contract"] == "0xc354",
            "heap/floor source-derived or drifted")
    require(value["execution_witness"]["mutations_rejected"] == 8,
            "mutation execution witness drift")


def selftest() -> None:
    base = build()
    mutations = []
    row = deepcopy(base)
    row_by_output(row, ".rodata")["members"].pop()
    row_by_output(row, ".rodata")["member_bytes"] -= 3
    mutations.append(("omitted-input", row))
    row = deepcopy(base)
    row["input_closure"]["ordinary_member_ids"].append(
        row["input_closure"]["ordinary_member_ids"][0])
    mutations.append(("duplicated-input", row))
    row = deepcopy(base)
    row["input_closure"]["profile_rodata_inputs"].pop()
    mutations.append(("profile-rodata-called-ordinary", row))
    row = deepcopy(base)
    row["noinit_static_stack_closure"]["ordinary_noinit_demand_bytes"] = 6
    mutations.append(("static-stack-double-owned", row))
    row = deepcopy(base)
    row_by_output(row, ".data")["alignment"] = 2
    mutations.append(("false-alignment", row))
    row = deepcopy(base)
    row_by_output(row, ".data")["lma"] = "0xb9b5"
    mutations.append(("false-vma-lma", row))
    row = deepcopy(base)
    row["input_closure"]["unknown_allocatable_ordinary_inputs"] = [
        ".mystery.alloc"]
    mutations.append(("hidden-allocatable-orphan", row))
    row = deepcopy(base)
    row["oracle_policy"]["expected_address_source"] = "generated-linker-under-test"
    row["oracle_policy"]["linker_under_test_is_oracle"] = True
    mutations.append(("source-derived-heap-overlay", row))
    rejected = 0
    for name, row in mutations:
        try:
            validate(row)
        except FirstRed:
            rejected += 1
        else:
            raise FirstRed(f"selftest mutation survived: {name}")
    require(rejected == 8, "selftest execution count drift")
    print("c2-v18-full-map-phase-a: SELFTEST PASS mutations=8")


def run() -> None:
    value = build()
    RECEIPT.write_bytes(canonical(value))
    witness = value["execution_witness"]
    print("c2-v18-full-map-phase-a: PASS "
          f"outputs={witness['map_outputs_enumerated']} "
          f"members={witness['map_members_enumerated']} "
          "chain=879+40+22+1585 end=0xbffb margin=5 noinit=0 stack=6")


def check() -> None:
    value = build()
    require(RECEIPT.is_file() and RECEIPT.read_bytes() == canonical(value),
            "Phase-A full-map closure receipt drift")
    witness = value["execution_witness"]
    print("c2-v18-full-map-phase-a: PASS "
          f"outputs={witness['map_outputs_enumerated']} "
          f"members={witness['map_members_enumerated']} "
          "chain=879+40+22+1585 end=0xbffb margin=5 noinit=0 stack=6")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    try:
        if action == "selftest":
            selftest()
        elif action == "run":
            run()
        elif action == "check":
            check()
        else:
            print(f"usage: {Path(sys.argv[0]).name} <selftest|run|check>",
                  file=sys.stderr)
            return 2
    except (FirstRed, KeyError, ValueError, OSError) as error:
        print(f"c2-v18-full-map-phase-a: FIRST RED: {error}", file=sys.stderr)
        return 1
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
