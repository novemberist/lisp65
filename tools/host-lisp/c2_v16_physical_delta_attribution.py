#!/usr/bin/env python3
"""Attribute the hook-free v1.6 physical-launch delta at the desk.

The stopped PC is a one-point sample, not a progress trace.  This checker
binds that sample to the exact Link-82 instruction, proves which diagnostic
delta could already have been observed, and keeps DMA-class membership behind
an independent content/completion witness.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
CONFIG = ROOT / "config/c2-v16-defstruct-phase-c-diagnostic.json"
CONTROL_ELF = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/control-link82.elf"
CONTROL_PRG = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/control-link82.prg"
DIAGNOSTIC_PRG = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-link82.prg"
PHYSICAL_PRG = ROOT / (
    "build/c2.3/v1.6-defstruct-d2-physical-fallback/diagnostic-link82-physical.prg")
CONTROL_WINDOW = ROOT / (
    "build/c2.2/v1.2.5-candidate-product-link82/final/"
    "c2-product-kernal-window.bin")
DIAGNOSTIC_WINDOW = ROOT / (
    "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-window.bin")
PHASE_C = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-c-diagnostic-preparation-receipt.json")
PHYSICAL_PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-physical-fallback-preparation-receipt.json")
STOPPED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-launch-boundary-stopped-state-receipt.json")
APPOINTMENT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-launch-boundary-appointment-result.json")
CONTROL_DEVICE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-launch-boundary-control-device-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-physical-delta-desk-attribution-receipt.json")
DRIVER = Path(__file__).resolve()

OBSERVED_PC = 0x32AA
ENTRY_PATCH = 0x202C
REFILL_HOOK = 0x47C5
ERROR_HOOK = 0x8EB7
CODE0 = (0xB3B0, 0xB4A3)
CODE1 = (0xBFF7, 0xC03E)
RECORD = (0xC03F, 0xC080)
FAIL_HOOK = 0xE08B


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha_bytes(path.read_bytes()),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def prg_payload(path: Path) -> tuple[int, bytes]:
    raw = path.read_bytes()
    require(len(raw) >= 2, f"truncated PRG: {path}")
    return int.from_bytes(raw[:2], "little"), raw[2:]


def prg_slice(path: Path, address: int, length: int) -> bytes:
    load_address, payload = prg_payload(path)
    offset = address - load_address
    require(0 <= offset <= len(payload) - length,
            f"PRG address outside payload: 0x{address:04x}")
    return payload[offset:offset + length]


def ranges(before: bytes, after: bytes, *, base: int) -> list[dict[str, Any]]:
    require(len(before) == len(after), "identity length drift")
    runs: list[list[int]] = []
    for index, (left, right) in enumerate(zip(before, after)):
        if left == right:
            continue
        if not runs or index != runs[-1][-1] + 1:
            runs.append([index])
        else:
            runs[-1].append(index)
    return [{
        "start": f"0x{base + row[0]:04x}",
        "bytes": len(row),
        "before": before[row[0]:row[-1] + 1].hex(),
        "after": after[row[0]:row[-1] + 1].hex(),
    } for row in runs]


def git_blob(commit: str, path: str) -> tuple[bytes, dict[str, Any]]:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(result.returncode == 0,
            f"source authority absent: {commit}:{path}: {result.stderr.decode(errors='replace')}")
    return result.stdout, {
        "commit": commit,
        "path": path,
        "bytes": len(result.stdout),
        "sha256": sha_bytes(result.stdout),
    }


def source_facts(source_commit: str) -> dict[str, Any]:
    mem_raw, mem_binding = git_blob(source_commit, "src/mem.c")
    obj_raw, obj_binding = git_blob(source_commit, "src/obj.h")
    eval_raw, eval_binding = git_blob(source_commit, "src/eval.c")
    work_raw, work_binding = git_blob(source_commit, "config/workbench.mk")
    mem = mem_raw.decode(); obj = obj_raw.decode(); ev = eval_raw.decode(); work = work_raw.decode()

    ext_cells = int(re.search(r"#define EXT_CELLS\s+(\d+)", obj).group(1))
    heap_cells = int(re.search(r"WORKBENCH_HEAP_CELLS\s*:=\s*(\d+)", work).group(1))
    require(ext_cells == 4096 and heap_cells == 48,
            "Link-82 EXT/hot heap geometry drift")
    required = (
        "for (i = MAX_CELLS - 1; i >= HEAP_CELLS; i--)",
        "cell_set_a((obj)(i << 1), freelist);",
        "void    ext_set_a(uint16_t i,obj v)",
        "ext_dma((uint16_t)(uintptr_t)&ext_stg,0,EXT_OFF(i)+2,EXT_BANK,2)",
        '"sta $d700\\n\\t"',
    )
    require(all(text in mem for text in required), "bound mem-init/DMA source chain drift")
    require("static inline void    cell_set_a" in obj and "else ext_set_a(i,v)" in obj,
            "bound EXT cell dispatch drift")
    require("WORKBENCH_BOOTFN void eval_init(void)" in ev
            and re.search(r"void eval_init\(void\)\s*\{\s*obj t;\s*mem_init\(\);", ev),
            "bound boot entry no longer calls mem_init first")
    return {
        "source_commit": source_commit,
        "bindings": {"mem": mem_binding, "obj": obj_binding,
                     "eval": eval_binding, "workbench": work_binding},
        "boot_chain": "vm_workbench_boot_overlay_entry -> eval_init -> mem_init -> cell_set_a -> ext_set_a -> ext_dma",
        "hot_cells": heap_cells,
        "EXT_cells": ext_cells,
        "mem_init_EXT_write_jobs": ext_cells,
        "DMA_direction": "Bank-0 ext_stg -> Bank-4 EXT cell a-field",
        "bytes_per_job": 2,
    }


def exact_facts() -> dict[str, Any]:
    config = load(CONFIG)
    stopped = load(STOPPED)
    appointment = load(APPOINTMENT)
    control_device = load(CONTROL_DEVICE)
    phase_c = load(PHASE_C)
    physical_prep = load(PHYSICAL_PREP)
    truth = ElfTruth.read(CONTROL_ELF, llvm_readobj=READOBJ,
                          include_section_data=True)

    control_load, control_payload = prg_payload(CONTROL_PRG)
    physical_load, physical_payload = prg_payload(PHYSICAL_PRG)
    diagnostic_load, diagnostic_payload = prg_payload(DIAGNOSTIC_PRG)
    require(control_load == physical_load == diagnostic_load == 0x2001,
            "PRG load address drift")

    physical_delta = ranges(control_payload, physical_payload, base=control_load)
    removal_delta = ranges(diagnostic_payload, physical_payload, base=control_load)
    window_delta = ranges(CONTROL_WINDOW.read_bytes(), DIAGNOSTIC_WINDOW.read_bytes(),
                          base=0xE000)
    require([(row["start"], row["bytes"]) for row in physical_delta] == [
        ("0x47c5", 10), ("0x8eb7", 5), ("0xb3b0", 243),
        ("0xbff7", 71), ("0xc03f", 65)], "physical/control delta inventory drift")
    require([(row["start"], row["bytes"]) for row in removal_delta] == [
        ("0x202c", 5), ("0xc03f", 9)], "hook-removal delta inventory drift")
    require([(row["start"], row["bytes"]) for row in window_delta] == [
        ("0xe08b", 14)], "diagnostic window delta inventory drift")

    ext_dma = truth.symbol("ext_dma")
    ext_dl = truth.symbol("ext_dl")
    ext_stg = truth.symbol("ext_stg")
    ext_body = prg_slice(CONTROL_PRG, ext_dma.value, ext_dma.bytes)
    stop_offset = OBSERVED_PC - ext_dma.value
    submit_offset = ext_body.index(bytes.fromhex("8d00d7"))
    require(ext_dma.value == 0x3287 and ext_dma.bytes == 0x44
            and stop_offset == 0x23 and submit_offset == 0x40,
            "stopped ext_dma geometry drift")
    require(ext_body[stop_offset:stop_offset + 3] == bytes.fromhex("8e7fbc")
            and prg_slice(PHYSICAL_PRG, OBSERVED_PC, 3) == bytes.fromhex("8e7fbc"),
            "stopped instruction is not shared STX ext_dl+7")
    require(ext_dl.value == 0xBC78 and ext_stg.value == 0xB9EE,
            "EXT DMA storage geometry drift")
    registers = stopped["registers"]
    require(registers["PC"] == "0x32aa" and registers["X"] == "0xb9",
            "stopped register authority drift")

    deployment = load(ROOT / phase_c["bindings"]["deployment"]["path"])
    canonical_reset = (ROOT / deployment["record"]["reset"]["path"]).read_bytes()
    stopped_record = (ROOT / stopped["captures"]["record"]["path"]).read_bytes()
    require(stopped_record == canonical_reset
            and stopped["summary"]["record_non_reset_bytes"] == 0
            and not stopped["summary"]["C07A_is_boot_witness_in_this_identity"],
            "stopped diagnostic record is not canonical/unarmed")

    require(prg_slice(PHYSICAL_PRG, ENTRY_PATCH, 5)
            == prg_slice(CONTROL_PRG, ENTRY_PATCH, 5)
            == bytes.fromhex("a2448e30d0"),
            "hook-free entry does not restore control bytes")
    require(prg_slice(DIAGNOSTIC_PRG, ENTRY_PATCH, 5) == bytes.fromhex("203fc0eaea"),
            "full diagnostic entry hook drift")

    text = truth.section(".text")
    handoff = truth.section(".lisp65_c2_kernal_handoff")
    bss = truth.section(".bss")
    require(text.address + text.bytes == CODE0[0]
            and handoff.address == CODE0[1]
            and truth.symbol("__init_array_start").value == CODE0[0]
            and truth.symbol("__init_array_end").value == CODE0[0]
            and bss.address + bss.bytes == CODE1[0]
            and truth.symbol("__lisp65_c2_fixed_bank0_committed_roots").value == RECORD[1],
            "diagnostic cave/record placement ownership drift")

    require(control_device["status"] == "CONTROL-PHYSICAL-BOOT-PASS"
            and appointment["control"]["visible_lisp65_prompt"]
            and physical_prep["facts"]["entry_hook_present"] is False,
            "launch-boundary authority drift")

    return {
        "identities": {
            "control_PRG": bind(CONTROL_PRG),
            "full_diagnostic_PRG": bind(DIAGNOSTIC_PRG),
            "physical_hook_free_PRG": bind(PHYSICAL_PRG),
            "physical_vs_control": physical_delta,
            "full_diagnostic_to_physical_removal": removal_delta,
            "window_vs_control": window_delta,
            "entry_removal_restores_control_bytes": True,
        },
        "stopped_PC": {
            "PC": "0x32aa",
            "symbol": "ext_dma",
            "symbol_start": "0x3287",
            "symbol_offset": 0x23,
            "instruction": "STX $BC7F (ext_dl+7)",
            "linked_bytes": "8e7fbc",
            "X": "0xb9",
            "X_matches_ext_stg_high_byte": True,
            "D700_submit_offset": 0x40,
            "bytes_before_submit": submit_offset - stop_offset,
            "submit_reached_by_this_PC_witness": False,
            "completion_or_content_consumed_by_this_PC_witness": False,
        },
        "instrument_state": {
            "record_bytes": len(stopped_record),
            "record_matches_canonical_reset": True,
            "record_non_reset_bytes": 0,
            "entry_witness_exists_in_physical_identity": False,
            "refill_error_fail_closed_record_writes_observed": False,
            "first_error_state": stopped["summary"]["first_error_state_hex"],
        },
        "placement": {
            "code0_gap": ["0xb3b0", "0xb4a3"],
            "init_array_start_equals_end_at_code0": True,
            "code1_starts_at_bss_end": "0xbff7",
            "record_ends_at_first_fixed_bank0_state": "0xc080",
            "caves_and_record_are_not_CRT_BSS_or_init_array_members": True,
        },
        "source": source_facts(config["authority"]["source_commit"]),
    }


def decision() -> dict[str, Any]:
    return {
        "hook_removal_hypothesis": "exonerated-through-observed-stage",
        "record_or_witness_delta_hypothesis": "not-consumed-before-observed-stage",
        "F018B_completion_visibility_membership": "not-proved-and-not-reached-by-PC-witness",
        "named_mechanism": (
            "the one-point stop sampled the shared 4096-job EXT-freelist bootstrap "
            "before the first diagnostic hook; it was promoted from progress state "
            "to delta-owned freeze without a progress/liveness witness"),
        "prior_delta_boundary_causality": "rejected",
        "physical_no-prompt_observation": "still-real-but-mechanism-unattributed",
        "control_green_implication": (
            "the common boot can complete; without matched progress timing it does not "
            "make a pre-delta stopped sample diagnostic-owned"),
        "required_next_evidence_if_reopened": (
            "matched control/physical early-boot progress counts or two time-separated "
            "CPU-side mem_init/DMA progress witnesses; one PC sample is insufficient"),
        "new_device_contact_authorized": False,
        "product_or_diagnostic_fix_authorized": False,
        "R_A_I_G_claimed": False,
    }


def audit(facts: dict[str, Any], result: dict[str, Any]) -> None:
    pc = facts["stopped_PC"]
    identity = facts["identities"]
    instrument = facts["instrument_state"]
    source = facts["source"]
    require(identity["entry_removal_restores_control_bytes"],
            "hook-removal exoneration drift")
    require(pc["symbol"] == "ext_dma" and pc["symbol_offset"] == 0x23
            and pc["linked_bytes"] == "8e7fbc"
            and pc["bytes_before_submit"] == 29
            and not pc["submit_reached_by_this_PC_witness"]
            and not pc["completion_or_content_consumed_by_this_PC_witness"],
            "stopped-PC claim boundary drift")
    require(instrument["record_matches_canonical_reset"]
            and instrument["record_non_reset_bytes"] == 0
            and not instrument["entry_witness_exists_in_physical_identity"]
            and not instrument["refill_error_fail_closed_record_writes_observed"],
            "diagnostic record reachability claim drift")
    require(source["mem_init_EXT_write_jobs"] == 4096
            and source["bytes_per_job"] == 2,
            "shared bootstrap workload drift")
    require(result["hook_removal_hypothesis"] == "exonerated-through-observed-stage"
            and result["record_or_witness_delta_hypothesis"] ==
            "not-consumed-before-observed-stage"
            and result["F018B_completion_visibility_membership"] ==
            "not-proved-and-not-reached-by-PC-witness"
            and result["prior_delta_boundary_causality"] == "rejected"
            and result["physical_no-prompt_observation"] ==
            "still-real-but-mechanism-unattributed"
            and not result["new_device_contact_authorized"]
            and not result["product_or_diagnostic_fix_authorized"]
            and not result["R_A_I_G_claimed"],
            "attribution/claim limit drift")


def mutations(facts: dict[str, Any], result: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[str, list[str], Any]] = {
        "claim-hook-removal-cause": (
            "result", ["hook_removal_hypothesis"], "causal"),
        "claim-record-hook-reached": (
            "facts", ["instrument_state", "refill_error_fail_closed_record_writes_observed"], True),
        "claim-submit-reached": (
            "facts", ["stopped_PC", "submit_reached_by_this_PC_witness"], True),
        "claim-DMA-class-member": (
            "result", ["F018B_completion_visibility_membership"], "proved"),
        "claim-delta-causality": (
            "result", ["prior_delta_boundary_causality"], "proved"),
        "erase-unresolved-no-prompt": (
            "result", ["physical_no-prompt_observation"], "resolved"),
        "authorize-device": (
            "result", ["new_device_contact_authorized"], True),
        "authorize-fix": (
            "result", ["product_or_diagnostic_fix_authorized"], True),
        "claim-R-row": (
            "result", ["R_A_I_G_claimed"], True),
    }
    rejected: dict[str, str] = {}
    for name, (which, path, replacement) in cases.items():
        trial_facts = deepcopy(facts); trial_result = deepcopy(result)
        target: Any = trial_facts if which == "facts" else trial_result
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = replacement
        try:
            audit(trial_facts, trial_result)
        except AttributionError as error:
            rejected[name] = str(error)
        else:
            raise AttributionError(f"physical-delta mutation survived: {name}")
    require(len(rejected) == len(cases), "physical-delta mutation count drift")
    return rejected


def expected() -> dict[str, Any]:
    facts = exact_facts()
    result = decision()
    audit(facts, result)
    rejected = mutations(facts, result)
    return {
        "format": "lisp65-c2.3-v1.6-defstruct-D2-physical-delta-desk-attribution-v1",
        "recorded_on": date.today().isoformat(),
        "status": "ATTRIBUTED SHARED PRE-DELTA BOOTSTRAP SAMPLE; DELTA CAUSALITY REJECTED",
        "authorities": {
            "owner_commission": bind(PLAN),
            "phase_C": bind(PHASE_C),
            "physical_preparation": bind(PHYSICAL_PREP),
            "stopped_state": bind(STOPPED),
            "appointment": bind(APPOINTMENT),
            "control_device": bind(CONTROL_DEVICE),
            "driver": bind(DRIVER),
        },
        "facts": facts,
        "decision": result,
        "mutations_rejected": rejected,
        "execution_witnesses": 1 + len(rejected),
        "claim_limit": (
            "Host/source/ELF and already-captured stopped-state attribution only. "
            "It rejects causal ownership by the diagnostic delta at the observed "
            "stage but does not claim the physical no-prompt symptom resolved, does "
            "not prove DMA liveness/completion, and authorizes no device contact, "
            "product/diagnostic fix, measured form, Link or R/A/I/G row."),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "write", "check"))
    args = parser.parse_args()
    value = expected()
    if args.action == "selftest":
        print("c2-v16-physical-delta-attribution: SELFTEST PASS mutations=9")
        return 0
    if args.action == "write":
        write_json(RECEIPT, value)
    else:
        require(RECEIPT.is_file() and RECEIPT.read_bytes() == canonical(value),
                "physical-delta attribution receipt drift")
    print("c2-v16-physical-delta-attribution: PASS PC=ext_dma+0x23 "
          "submit=no shared-mem-init=4096 delta-causality=rejected")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, ElfTruthError, OSError, KeyError, ValueError,
            AttributeError, json.JSONDecodeError) as error:
        print(f"c2-v16-physical-delta-attribution: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(1)
