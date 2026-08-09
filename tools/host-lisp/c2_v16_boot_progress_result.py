#!/usr/bin/env python3
"""Classify the unregistered v1.6 physical boot-progress outcome.

The device appointment deliberately had a closed three-row decision table.
Its samples matched none of those rows: they were outside the EXT-freelist
bootstrap, the entry byte was back at its reset value, and the only changing
value was not the pre-registered monotonic oracle.  This checker binds that
boundary to the exact Link-82 ELF without turning a useful instrument First
Red into a product, F018B, liveness, or R/A/I/G claim.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
CONFIG = ROOT / "config/c2-v16-defstruct-phase-c-diagnostic.json"
KERNAL_CONTRACT = ROOT / "config/c2-kernal-unmap-contract.json"
DEPLOYMENT = ROOT / "build/c2.3/v1.6-defstruct-phase-c/deployment.json"
ELF = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-link82.elf"
PRG = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-link82.prg"
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-progress-witness-preparation-receipt.json")
DEVICE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-progress-witness-device-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-progress-witness-desk-first-red-receipt.json")
DRIVER = Path(__file__).resolve()

ROOT_SCAN = 0xE0BA
ROOT_SCAN_BYTES = 547
GC_COLLECT = 0x38F7
GC_CALL_ROOT_SCAN = 0x398F
ENTRY_HOOK = 0x202C
ENTRY_ROUTINE = 0xC03F
ENTRY_STAMP_STORE = 0xC044
ENTRY_STAMP_ADDRESS = 0xC07A
ENTRY_STAMP = 0x44
ENTRY_RESET = 0x6B
EARLY_INTERVALS = (
    (0x3287, 0x32CB, "ext_dma"),
    (0x3521, 0x3570, "cell_set_a"),
    (0x3570, 0x35A7, "ext_set_a"),
    (0xC45C, 0xC4BD, "eval_init/freelist-loop"),
)


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


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


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def prg_slice(address: int, size: int) -> bytes:
    raw = PRG.read_bytes()
    load_address = int.from_bytes(raw[:2], "little")
    offset = address - load_address + 2
    require(2 <= offset <= len(raw) - size,
            f"PRG slice outside image: 0x{address:04x}")
    return raw[offset:offset + size]


def symbol_bytes(truth: ElfTruth, name: str) -> tuple[int, bytes]:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    data = truth.section_bytes(symbol.section)
    offset = symbol.value - section.address
    require(symbol.bytes > 0 and 0 <= offset <= len(data) - symbol.bytes,
            f"sized symbol outside section: {name}")
    return symbol.value, data[offset:offset + symbol.bytes]


def git_blob(commit: str, path: str) -> tuple[bytes, dict[str, Any]]:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(result.returncode == 0,
            f"source authority absent: {commit}:{path}")
    return result.stdout, {
        "commit": commit,
        "path": path,
        "bytes": len(result.stdout),
        "sha256": sha_bytes(result.stdout),
    }


def pc_inside(pc: int, start: int, size: int) -> bool:
    return start <= pc < start + size


def exact_facts() -> dict[str, Any]:
    preparation = load(PREPARATION)
    device = load(DEVICE)
    config = load(CONFIG)
    contract = load(KERNAL_CONTRACT)
    deployment = load(DEPLOYMENT)
    require(device["status"] == "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM"
            and device["result"] == {
                "classification": "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM",
                "CPU_left_stopped": True,
                "measured_forms_run": 0,
                "R_A_I_G_claimed": False,
            }, "device First-Red boundary drift")
    require(device["authorities"]["preparation"]["sha256"] ==
            sha_bytes(PREPARATION.read_bytes()),
            "device/preparation binding drift")
    require(preparation["facts"]["decision_table"]["other"] ==
            "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM",
            "unregistered-outcome row absent")
    require(deployment["entry_witness"]["hook"] == ENTRY_HOOK
            and deployment["entry_witness"]["routine"] == ENTRY_ROUTINE
            and deployment["entry_witness"]["stamp_address"] == ENTRY_STAMP_ADDRESS
            and deployment["entry_witness"]["stamp_initial"] == ENTRY_RESET
            and deployment["entry_witness"]["stamp_value"] == ENTRY_STAMP,
            "entry-witness deployment drift")
    require(prg_slice(ENTRY_HOOK, 5) == bytes.fromhex("203fc0eaea")
            and prg_slice(ENTRY_ROUTINE, 9) == bytes.fromhex(
                "a2448e30d08e7ac060"),
            "linked entry hook/routine drift")

    samples = device["samples"]
    require(len(samples) == 3, "device sample count drift")
    pcs = [int(row["PC"], 16) for row in samples]
    boots = [int(row["boot_witness"], 16) for row in samples]
    heads = [int(row["freelist_head"], 16) for row in samples]
    jobs = [row["freelist_jobs_completed"] for row in samples]
    xs = [int(row["registers"]["X"], 16) for row in samples]
    require(pcs == [0xE18D, 0xE1BF, 0xE1BF]
            and boots == [ENTRY_RESET] * 3
            and heads == [0, 0, 0]
            and jobs == [0, 0, 0]
            and xs == [0, 8, 5],
            "device observation drift")
    require(not any(start <= pc < end
                    for pc in pcs for start, end, _ in EARLY_INTERVALS),
            "a sample unexpectedly lies in the freelist-build intervals")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    root_start, root = symbol_bytes(truth, "c2_product_gc_mark_roots")
    gc_start, gc = symbol_bytes(truth, "gc_collect")
    require((root_start, len(root)) == (ROOT_SCAN, ROOT_SCAN_BYTES)
            and gc_start == GC_COLLECT,
            "GC/root-scan symbol geometry drift")
    require(all(pc_inside(pc, root_start, len(root)) for pc in pcs),
            "device PC lies outside c2_product_gc_mark_roots")
    require(root[0xCA:0xD3] == bytes.fromhex("20dde2aad0034c08e2")
            and root[0xD3:0xD7] == bytes.fromhex("a619861b"),
            "first root-scan sample instruction neighborhood drift")
    require(root[0x104:0x108] == bytes.fromhex("a41fb104"),
            "later root-scan sample instruction neighborhood drift")
    require(gc[GC_CALL_ROOT_SCAN - gc_start:
               GC_CALL_ROOT_SCAN - gc_start + 3] == bytes.fromhex("20bae0"),
            "gc_collect/root-scan call edge drift")
    root_section = truth.section(truth.symbol("c2_product_gc_mark_roots").section)

    rules = contract["fixed_cross_domain_facade"]["link_rules"]
    ownership_rule = next((row for row in rules
                           if "c2_product_gc_mark_roots" in row
                           and "unreachable before" in row), None)
    require(ownership_rule is not None,
            "post-ownership root-scan contract rule absent")

    source_commit = config["authority"]["source_commit"]
    runtime_raw, runtime_binding = git_blob(source_commit, "src/c2_product_runtime.c")
    mem_raw, mem_binding = git_blob(source_commit, "src/mem.c")
    require(b"C2_KERNAL_RESIDENT void c2_product_gc_mark_roots(void)" in runtime_raw
            and b"c2_product_gc_mark_roots();" in mem_raw,
            "bound source call-chain drift")

    return {
        "device_observation": {
            "PCs": [f"0x{pc:04x}" for pc in pcs],
            "X_values": [f"0x{x:02x}" for x in xs],
            "boot_witness_values": [f"0x{x:02x}" for x in boots],
            "freelist_heads": [f"0x{x:04x}" for x in heads],
            "freelist_jobs_completed": jobs,
            "CPU_left_stopped": True,
            "measured_forms_run": 0,
            "R_A_I_G_claimed": False,
        },
        "ELF_binding": {
            "symbol": "c2_product_gc_mark_roots",
            "section": root_section.name,
            "start": f"0x{root_start:04x}",
            "bytes": len(root),
            "sample_offsets": [f"0x{pc - root_start:x}" for pc in pcs],
            "first_sample_instruction": "$E18D: LDX $19",
            "later_PC_note": (
                "$E1BF lies inside the two-byte LDY $1F encoding at $E1BE; "
                "the monitor PC is not promoted to an instruction-boundary claim"),
            "gc_collect_call_edge": "$398F: JSR $E0BA",
            "ownership_contract": ownership_rule,
        },
        "entry_witness_contradiction": {
            "hook": "$202C: JSR $C03F",
            "routine": "$C03F: replay displaced bytes; $C044: STX $C07A; RTS",
            "expected": "0x44",
            "observed": "0x6b in all three samples",
            "durable_entry_claim_supported": False,
            "entry_non_execution_claim_supported": False,
            "reason": (
                "the sampled PCs are in a contractually post-ownership routine, "
                "so reset-valued $C07A cannot by itself prove that _start was not reached"),
        },
        "source_bindings": {
            "source_commit": source_commit,
            "runtime": runtime_binding,
            "mem": mem_binding,
        },
    }


def decision() -> dict[str, Any]:
    return {
        "pre_bound_row": "other / FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM",
        "earlier_ext_dma_freeze_reproduced": False,
        "freelist_loop_liveness_answered": False,
        "why_freelist_oracle_is_out_of_scope": (
            "all samples are already in c2_product_gc_mark_roots; a zero freelist "
            "is legal after later allocation consumes the completed bootstrap list"),
        "later_root_scan_progress_observation": (
            "PC2=PC3=$E1BF while X changed $08->$05 over five seconds"),
        "later_root_scan_progress_claim": False,
        "why_not_progress_claim": (
            "X was neither pre-registered as monotonic nor sampled at a proved "
            "instruction boundary; it is an observation, not the appointment oracle"),
        "entry_witness_disposition": (
            "$C07A is contradicted as a durable post-entry witness for this sampling "
            "horizon; overwrite/view/lifetime must be attributed before reuse"),
        "product_hang_claim": False,
        "F018B_membership_claim": False,
        "R_A_I_G_claim": False,
        "new_device_contact_authorized": False,
        "required_owner_review": (
            "the authorized three-row table did not cover post-bootstrap execution "
            "with a reset-valued entry byte; choose a witness whose lifetime covers "
            "the intended sampling horizon before any new contact"),
    }


def audit(facts: dict[str, Any], disposition: dict[str, Any]) -> None:
    observed = facts["device_observation"]
    linked = facts["ELF_binding"]
    contradiction = facts["entry_witness_contradiction"]
    require(observed["PCs"] == ["0xe18d", "0xe1bf", "0xe1bf"]
            and observed["X_values"] == ["0x00", "0x08", "0x05"]
            and observed["boot_witness_values"] == ["0x6b"] * 3
            and observed["freelist_jobs_completed"] == [0, 0, 0]
            and observed["CPU_left_stopped"]
            and observed["measured_forms_run"] == 0
            and not observed["R_A_I_G_claimed"],
            "device boundary claim drift")
    require(linked["symbol"] == "c2_product_gc_mark_roots"
            and linked["start"] == "0xe0ba"
            and linked["bytes"] == 547
            and linked["sample_offsets"] == ["0xd3", "0x105", "0x105"]
            and linked["gc_collect_call_edge"] == "$398F: JSR $E0BA",
            "root-scan binding claim drift")
    require(contradiction["expected"] == "0x44"
            and contradiction["observed"] == "0x6b in all three samples"
            and not contradiction["durable_entry_claim_supported"]
            and not contradiction["entry_non_execution_claim_supported"],
            "entry-witness contradiction drift")
    require(disposition["pre_bound_row"] ==
            "other / FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM"
            and not disposition["earlier_ext_dma_freeze_reproduced"]
            and not disposition["freelist_loop_liveness_answered"]
            and not disposition["later_root_scan_progress_claim"]
            and not disposition["product_hang_claim"]
            and not disposition["F018B_membership_claim"]
            and not disposition["R_A_I_G_claim"]
            and not disposition["new_device_contact_authorized"],
            "First-Red claim boundary drift")


def expected() -> dict[str, Any]:
    facts = exact_facts()
    disposition = decision()
    audit(facts, disposition)
    return {
        "format": "lisp65-c2.3-v1.6-defstruct-D2-progress-witness-desk-first-red-v1",
        "recorded_on": date.today().isoformat(),
        "status": "DESK-FIRST-RED-PREBOUND-TABLE-INCOMPLETE",
        "authorities": {
            "owner_commission": bind(PLAN),
            "configuration": bind(CONFIG),
            "kernal_ownership_contract": bind(KERNAL_CONTRACT),
            "deployment": bind(DEPLOYMENT),
            "diagnostic_ELF": bind(ELF),
            "diagnostic_PRG": bind(PRG),
            "preparation": bind(PREPARATION),
            "device_observation": bind(DEVICE),
            "driver": bind(DRIVER),
        },
        "facts": facts,
        "decision": disposition,
        "execution_witnesses": [
            "all three PCs resolve inside the sized Link-82 c2_product_gc_mark_roots symbol",
            "the linked gc_collect edge calls c2_product_gc_mark_roots at $398F",
            "none of the three PCs lies in any pre-bound EXT-freelist bootstrap interval",
            "all three $C07A reads retain the reset byte instead of the bound entry stamp",
            "the later two register packets share PC $E1BF but change X from $08 to $05",
            "the device receipt leaves the CPU stopped and records zero measured forms",
        ],
        "rejected_mutations": [
            "move-PC-outside-root-scan", "claim-freelist-stall",
            "claim-slow-freelist-progress", "claim-durable-entry-stamp",
            "claim-entry-never-ran", "promote-X-to-preregistered-oracle",
            "claim-product-hang", "claim-F018B-member", "claim-R-A-I-G",
            "claim-device-retry-authorized",
        ],
        "claim_limit": (
            "Desk classification of the consumed progress-witness row only. "
            "No product hang, F018B membership, entry non-execution, measured "
            "form, R/A/I/G result, fix, link, retry, reset or CPU resume is claimed."),
    }


def selftest() -> dict[str, Any]:
    facts = exact_facts()
    disposition = decision()
    cases = {
        "move-PC-outside-root-scan": (facts, disposition,
                                      ["ELF_binding", "sample_offsets"],
                                      ["0xd3", "0x105", "0x600"]),
        "claim-freelist-stall": (facts, disposition,
                                 ["decision", "earlier_ext_dma_freeze_reproduced"], True),
        "claim-slow-freelist-progress": (facts, disposition,
                                         ["decision", "freelist_loop_liveness_answered"], True),
        "claim-durable-entry-stamp": (facts, disposition,
                                      ["facts", "entry_witness_contradiction",
                                       "durable_entry_claim_supported"], True),
        "claim-entry-never-ran": (facts, disposition,
                                  ["facts", "entry_witness_contradiction",
                                   "entry_non_execution_claim_supported"], True),
        "promote-X-to-preregistered-oracle": (facts, disposition,
                                               ["decision", "later_root_scan_progress_claim"], True),
        "claim-product-hang": (facts, disposition,
                               ["decision", "product_hang_claim"], True),
        "claim-F018B-member": (facts, disposition,
                               ["decision", "F018B_membership_claim"], True),
        "claim-R-A-I-G": (facts, disposition,
                          ["decision", "R_A_I_G_claim"], True),
        "claim-device-retry-authorized": (facts, disposition,
                                           ["decision", "new_device_contact_authorized"], True),
    }
    rejected: list[str] = []
    for name, (base_facts, base_decision, path, replacement) in cases.items():
        trial_facts = deepcopy(base_facts)
        trial_decision = deepcopy(base_decision)
        if path[0] == "facts":
            cursor: Any = trial_facts
            keys = path[1:]
        elif path[0] == "decision":
            cursor = trial_decision
            keys = path[1:]
        else:
            cursor = trial_facts
            keys = path
        for key in keys[:-1]:
            cursor = cursor[key]
        cursor[keys[-1]] = replacement
        try:
            audit(trial_facts, trial_decision)
        except ResultError:
            rejected.append(name)
        else:
            raise ResultError(f"result mutation survived: {name}")
    require(len(rejected) == 10, "result mutation count drift")
    return {"status": "SELFTEST PASS", "mutations": len(rejected)}


def run() -> dict[str, Any]:
    value = expected()
    write(RECEIPT, value)
    return value


def check() -> dict[str, Any]:
    value = expected()
    require(RECEIPT.is_file() and RECEIPT.read_bytes() == canonical(value),
            "progress-result receipt drift")
    return {"status": "PASS", "classification": value["status"]}


def main() -> int:
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    try:
        if action == "run":
            value = run()
        elif action == "check":
            value = check()
        elif action == "selftest":
            value = selftest()
        else:
            print(f"usage: {Path(sys.argv[0]).name} <run|check|selftest>",
                  file=sys.stderr)
            return 2
        print(json.dumps(value, sort_keys=True))
    except (ResultError, ElfTruthError, KeyError, ValueError, OSError,
            json.JSONDecodeError) as error:
        print(f"c2-v1.6-boot-progress-result: FIRST RED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
