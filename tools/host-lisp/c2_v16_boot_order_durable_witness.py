#!/usr/bin/env python3
"""Bind the Link-82 boot order and price a boot-lifetime witness.

This is a desk-only forensic closure.  It proves which side of ``mem_init``
the consumed root-scan samples occupy and derives a one-byte diagnostic slot
from the owned 1.7/1.8 maps.  It never contacts or resumes the device and it
does not build or alter a product image.
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
from elf_truth import ElfTruth  # noqa: E402


READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
CONFIG = ROOT / "config/c2-v16-defstruct-phase-c-diagnostic.json"
PHASE_A = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-a-host-reconstruction-receipt.json")
PHASE_C = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-c-diagnostic-preparation-receipt.json")
CONTROL_BOOT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-launch-boundary-control-device-receipt.json")
PROGRESS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-progress-witness-desk-first-red-receipt.json")
OWNERSHIP_96 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-stack-overlay-ownership-inventory-receipt.json")
STATE_72 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-state-ownership-phase-a-inventory-receipt.json")
FULL_MAP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.8-full-map-phase-a-closure-receipt.json")
FULL_MAP_PRICE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.8-full-map-phase-b-contract-pricing-receipt.json")
CONTROL_ELF = ROOT / (
    "build/c2.3/v1.6-defstruct-phase-c/artifacts/control-link82.elf")
DIAGNOSTIC_ELF = ROOT / (
    "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-link82.elf")
DIAGNOSTIC_PRG = ROOT / (
    "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-link82.prg")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-boot-order-durable-witness-receipt.json")
DRIVER = Path(__file__).resolve()

SOURCE_COMMIT = "fe5c98fea63236af3bddca86bf1bb955cf9a6ffe"
ROOT_SCAN = 0xE0BA
ROOT_SCAN_BYTES = 547
WITNESS = 0xB5C3
WITNESS_RESET = 0xD7
WITNESS_STAMP = 0x44
GAP_START = 0xB582
GAP_END = 0xB5C4
DIAG_CODE1_END = 0xC03E
DIAG_RECORD_START = 0xC03F


class ClosureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ClosureError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    payload = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(payload),
        "sha256": sha_bytes(payload),
    }


def git_blob(path: str) -> tuple[str, dict[str, Any]]:
    result = subprocess.run(
        ["git", "show", f"{SOURCE_COMMIT}:{path}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(result.returncode == 0, f"historical source absent: {path}")
    raw = result.stdout
    return raw.decode("utf-8"), {
        "commit": SOURCE_COMMIT, "path": path,
        "bytes": len(raw), "sha256": sha_bytes(raw),
    }


def function(source: str, signature: str) -> str:
    start = source.find(signature)
    require(start >= 0, f"function absent: {signature}")
    brace = source.find("{", start)
    require(brace >= 0, f"function body absent: {signature}")
    depth = 0
    for at in range(brace, len(source)):
        if source[at] == "{":
            depth += 1
        elif source[at] == "}":
            depth -= 1
            if depth == 0:
                return source[start:at + 1]
    raise ClosureError(f"unterminated function: {signature}")


def ordered(text: str, tokens: list[str], label: str) -> None:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.DOTALL)
    positions = [text.find(token) for token in tokens]
    require(all(at >= 0 for at in positions) and positions == sorted(positions),
            f"{label} order drift: {positions}")


def section_row(truth: ElfTruth, name: str) -> dict[str, Any]:
    sec = truth.section(name)
    return {"name": name, "start": sec.address,
            "end_exclusive": sec.address + sec.bytes, "bytes": sec.bytes,
            "section_type": sec.section_type}


def prg_byte(address: int) -> int:
    raw = DIAGNOSTIC_PRG.read_bytes()
    load_address = int.from_bytes(raw[:2], "little")
    offset = 2 + address - load_address
    require(2 <= offset < len(raw), f"PRG address absent: 0x{address:04x}")
    return raw[offset]


def overlaps(address: int, row: dict[str, Any]) -> bool:
    return int(row["start"]) <= address < int(row["end_exclusive"])


def active_owner_ranges(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for row in inventory["ranges"]:
        start = row.get("vma")
        size = row.get("bytes")
        if (not isinstance(start, int) or not isinstance(size, int) or size <= 0
                or start >= 0x10000
                or "post-ownership-no-overlay" not in row.get("live_envelopes", [])):
            continue
        result.append({
            "name": row["name"], "owner": row["owner"],
            "start": start, "end_exclusive": start + size,
        })
    require(result, "post-ownership owner set is empty")
    return result


def exact_facts() -> dict[str, Any]:
    config = load(CONFIG)
    phase_a = load(PHASE_A)
    phase_c = load(PHASE_C)
    control_boot = load(CONTROL_BOOT)
    progress = load(PROGRESS)
    ownership = load(OWNERSHIP_96)
    state = load(STATE_72)
    full_map = load(FULL_MAP)
    full_map_price = load(FULL_MAP_PRICE)
    require(config["authority"]["source_commit"] == SOURCE_COMMIT,
            "Link-82 source authority drift")
    require(phase_a["base"]["link"] == 82
            and phase_a["base"]["geometry"]["roots"] == 340
            and phase_a["hardware_runs"] == 0,
            "Phase-A base/scope drift")
    require(progress["facts"]["device_observation"]["PCs"] ==
            ["0xe18d", "0xe1bf", "0xe1bf"]
            and progress["facts"]["device_observation"]["X_values"] ==
            ["0x00", "0x08", "0x05"]
            and progress["facts"]["device_observation"]["freelist_heads"] ==
            ["0x0000"] * 3,
            "consumed root-scan observation drift")
    require(control_boot["status"] == "CONTROL-PHYSICAL-BOOT-PASS"
            and control_boot["control_identity"]["screen_result"]["visible_REPL"],
            "healthy physical control authority drift")
    identity = phase_c["facts"]["identity"]
    instrument = phase_c["facts"]["instrument"]
    require(identity["control_byteidentical_to_Link82"]
            and identity["product_candidate_bytes_changed"] == 0
            and not instrument["stores_call_product_helpers"]
            and not instrument["stores_submit_DMA"]
            and not instrument["stores_can_fail"],
            "diagnostic transparency authority drift")
    require(ownership["range_count"] == 96
            and state["execution_witness"]["input_sections_enumerated"] == 72,
            "1.7/1.8 owner inventory count drift")

    main, main_bind = git_blob("src/main.c")
    mem, mem_bind = git_blob("src/mem.c")
    runtime, runtime_bind = git_blob("src/c2_product_runtime.c")
    evaluator, eval_bind = git_blob("src/eval.c")
    overlay, overlay_bind = git_blob("src/vm_boot_overlay.c")
    main_fn = function(main, "int main(void)")
    mem_init = function(mem, "void mem_init(void)")
    alloc = function(mem, "obj alloc(uint8_t type)")
    collect = function(mem, "void gc_collect(void)")
    boot = function(runtime, "uint8_t c2_product_boot(void)")
    roots = function(runtime, "void c2_product_gc_mark_roots(void)")
    eval_init = function(evaluator, "void eval_init(void)")
    overlay_entry = function(overlay, "void vm_workbench_boot_overlay_entry(void)")
    ordered(main_fn, ["c2_kernal_take_ownership()",
                      "vm_install_staged_boot_overlay()",
                      "c2_product_prepare_boot()",
                      "c2_product_boot()", "repl()"], "main boot")
    ordered(mem_init, ["freelist = NIL", "for (i = MAX_CELLS - 1"],
            "EXT freelist bootstrap")
    ordered(boot, ["c2_committed_roots = 0", "c2_decode_from",
                   "c2_pending_roots = c2_runtime.c2_root_count",
                   "c2_committed_roots = c2_runtime.c2_root_count",
                   "c2_publish_exports_from"], "C2 product publication")
    ordered(collect, ["c2_product_gc_mark_roots();", "freelist = NIL;"],
            "collection root/sweep")
    require("mem_init();" in eval_init and "eval_init();" in overlay_entry,
            "overlay/eval/mem init edge drift")
    require("if (freelist == NIL)" in alloc and "gc_collect();" in alloc,
            "allocation exhaustion edge drift")
    require("while (done < scan)" in roots
            and "scan = c2_committed_roots" in roots,
            "root walker semantics drift")

    control = ElfTruth.read(CONTROL_ELF, llvm_readobj=READOBJ,
                            include_section_data=True)
    diagnostic = ElfTruth.read(DIAGNOSTIC_ELF, llvm_readobj=READOBJ,
                               include_section_data=True)
    root = diagnostic.symbol("c2_product_gc_mark_roots")
    require((root.value, root.bytes) == (ROOT_SCAN, ROOT_SCAN_BYTES),
            "Link-82 root walker geometry drift")
    require(diagnostic.symbol("freelist").value == 0x003D
            and diagnostic.symbol("c2_committed_roots").value == 0xC080
            and diagnostic.symbol("c2_pending_roots").value == 0x008A,
            "Link-82 root/freelist symbols drift")

    control_rows = [section_row(control, name) for name in (
        ".text", ".lisp65_c2_kernal_handoff", ".lisp65_c2_host_facade",
        ".bss", ".noinit", ".lisp65_c2_fixed_bank0")]
    diag_rows = [section_row(diagnostic, name) for name in (
        ".lisp65_v16_defstruct_diagnostic_code0",
        ".lisp65_v16_defstruct_diagnostic_code1",
        ".lisp65_v16_defstruct_diagnostic_state")]
    by_name = {row["name"]: row for row in control_rows + diag_rows}
    require(by_name[".lisp65_c2_kernal_handoff"]["end_exclusive"] == GAP_START
            and by_name[".lisp65_c2_host_facade"]["start"] == GAP_END
            and by_name[".lisp65_v16_defstruct_diagnostic_code1"]
                ["end_exclusive"] == DIAG_CODE1_END
            and by_name[".lisp65_v16_defstruct_diagnostic_state"]
                ["start"] == DIAG_RECORD_START,
            "diagnostic/owned gap geometry drift")
    active = active_owner_ranges(ownership)
    require(not any(overlaps(WITNESS, row) for row in active),
            "candidate overlaps a post-ownership owner")
    require(GAP_START <= WITNESS < GAP_END and prg_byte(WITNESS) == 0,
            "candidate is not the zero-filled owned-map gap byte")
    ledger = full_map_price["fixed_simultaneous_live_ledger"]
    require(not any(
        int(str(row["start"]), 0) <= WITNESS <
        int(str(row["end_exclusive"]), 0)
        for row in ledger if "start" in row and "end_exclusive" in row),
        "candidate overlaps the accepted 1.8 simultaneous-live ledger")
    require(full_map["noinit_static_stack_closure"]["compiler_stack_vma"] ==
            "0xc074", "1.8 static-stack binding drift")

    return {
        "boot_order": {
            "main_order": ["KERNAL ownership", "boot overlay/eval_init/mem_init",
                           "C2 prepare", "runtime overlay", "C2 product boot",
                           "REPL"],
            "base_root_count": 340,
            "nonempty_scan_proof": (
                "$E18D/$E1BF are inside the done<scan body after a successful "
                "C2D root-block read"),
            "mark_before_EXT_freelist_build_reachable": False,
            "reason": (
                "mem_init completes the 4,096-cell EXT chain in the boot overlay "
                "before c2_product_boot publishes the 340 nonzero roots; the "
                "observed loop body cannot execute while those roots are zero"),
            "zero_freelist_at_root_scan": (
                "normal exhausted-list collection entry; gc_collect does not "
                "rebuild freelist until the later sweep"),
            "healthy_control_path": "physically reaches lisp65> with identical heap edges",
            "classification": "SHARED-POST-MEM-INIT-COLLECTION-ROOT-SCAN",
            "X_08_to_05": "progress hint only; not an instruction-boundary oracle",
        },
        "durable_witness": {
            "address": f"0x{WITNESS:04x}", "bytes": 1,
            "owner": "non-promotable-v1.6-diagnostic-session",
            "reservation": "owned gap after handoff and before host facade",
            "containing_gap": {
                "start": f"0x{GAP_START:04x}",
                "end_exclusive": f"0x{GAP_END:04x}",
                "bytes": GAP_END - GAP_START,
            },
            "prelaunch_reset": f"0x{WITNESS_RESET:02x}",
            "entry_stamp": f"0x{WITNESS_STAMP:02x}",
            "required_entry_store": "$202C bootstrap stores $44 to $B5C3",
            "initialization": "CPU-side reset+readback before physical RUN",
            "observation_horizon": "post-mapping _start entry through boot samples/prompt",
            "active_owner_ranges_rejected": len(active),
            "owned_inventory_counts": {"placement_ranges": 96,
                                       "state_inputs": 72},
            "disjoint_from_record_reset": True,
            "disjoint_from_static_stack": True,
            "disjoint_from_all_post_ownership_owners": True,
            "product_bytes_changed": 0,
            "diagnostic_identity_built": False,
        },
        "decision_table": {
            "identical_early_boot_samples": "STALLED-IN-FREELIST-BUILD",
            "increasing_job_indices": "SLOW-EARLY-BOOT-PROGRESS",
            "durable_stamp_and_later_stable_PC": "POST-ENTRY-HANG-SITE",
            "post_entry_PC_with_reset_durable_slot":
                "BOOT-ENTRY-IDENTITY-OR-VIEW-FIRST-RED",
            "other": "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM",
        },
        "limits": {"hardware_contacts": 0, "product_bytes": 0,
                   "diagnostic_builds": 0, "contact_authorized": False},
        "owner_ranges": active,
        "section_boundaries": control_rows + diag_rows,
        "source_bindings": {
            "main": main_bind, "mem": mem_bind, "runtime": runtime_bind,
            "eval": eval_bind, "boot_overlay": overlay_bind,
        },
    }


def audit(facts: dict[str, Any]) -> None:
    boot = facts["boot_order"]
    witness = facts["durable_witness"]
    table = facts["decision_table"]
    limits = facts["limits"]
    require(boot["classification"] ==
            "SHARED-POST-MEM-INIT-COLLECTION-ROOT-SCAN"
            and boot["base_root_count"] == 340
            and not boot["mark_before_EXT_freelist_build_reachable"]
            and boot["X_08_to_05"].startswith("progress hint only"),
            "boot-order conclusion drift")
    require(witness["address"] == "0xb5c3" and witness["bytes"] == 1
            and witness["prelaunch_reset"] == "0xd7"
            and witness["entry_stamp"] == "0x44"
            and witness["active_owner_ranges_rejected"] > 0
            and witness["owned_inventory_counts"] == {
                "placement_ranges": 96, "state_inputs": 72}
            and witness["disjoint_from_record_reset"]
            and witness["disjoint_from_static_stack"]
            and witness["disjoint_from_all_post_ownership_owners"]
            and witness["product_bytes_changed"] == 0
            and not witness["diagnostic_identity_built"],
            "durable-witness conclusion drift")
    require(table["post_entry_PC_with_reset_durable_slot"] ==
            "BOOT-ENTRY-IDENTITY-OR-VIEW-FIRST-RED"
            and table["other"] == "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM",
            "fourth decision row drift")
    require(limits == {"hardware_contacts": 0, "product_bytes": 0,
                       "diagnostic_builds": 0, "contact_authorized": False},
            "desk-only/contact boundary drift")
    address = int(witness["address"], 0)
    require(not any(overlaps(address, row) for row in facts["owner_ranges"]),
            "witness moved into an active owner")


def expected() -> dict[str, Any]:
    facts = exact_facts()
    audit(facts)
    return {
        "format": "lisp65-c2.3-v1.6-boot-order-durable-witness-v1",
        "recorded_on": date.today().isoformat(),
        "status": "HOST-GREEN; BOOT-ORDER-BOUND; DURABLE-WITNESS-DESIGNED",
        "authorities": {
            "owner_commission": bind(PLAN), "configuration": bind(CONFIG),
            "phase_A": bind(PHASE_A), "phase_C": bind(PHASE_C),
            "healthy_control_boot": bind(CONTROL_BOOT),
            "progress_First_Red": bind(PROGRESS),
            "ownership_96": bind(OWNERSHIP_96), "state_72": bind(STATE_72),
            "full_map_closure": bind(FULL_MAP),
            "full_map_pricing": bind(FULL_MAP_PRICE),
            "control_ELF": bind(CONTROL_ELF),
            "diagnostic_ELF": bind(DIAGNOSTIC_ELF),
            "diagnostic_PRG": bind(DIAGNOSTIC_PRG), "driver": bind(DRIVER),
        },
        "facts": facts,
        "execution_witnesses": [
            "exact source orders eval_init/mem_init before C2 root publication",
            "the sampled PCs are in the nonempty Link-82 root-block loop",
            "Phase A binds the unmodified product base at 340 roots",
            "physical control reaches lisp65> through the same heap-affecting edges",
            "the 96-range placement inventory leaves $B582..$B5C4 owner-free",
            "the 72-input state census and 1.8 simultaneous-live ledger do not own $B5C3",
            "every post-ownership owner-range placement mutation is rejected",
        ],
        "rejected_mutations": [
            "claim-mark-before-freelist-build", "change-base-root-count",
            "promote-X-to-oracle", "reuse-C07A", "move-witness-into-BSS",
            "move-witness-into-static-stack", "move-witness-into-fixed-C2-state",
            "move-witness-into-diagnostic-record", "drop-owner-disjointness",
            "drop-fourth-row", "claim-diagnostic-built", "claim-contact-authorized",
        ],
        "contact_authorized": False,
        "claim_limit": (
            "Desk-only boot-order and witness-lifetime design. No device contact, "
            "CPU resume/reset, diagnostic build, measured form, R/A/I/G result, "
            "F018B membership, product byte, fix or link is claimed."),
    }


def selftest() -> dict[str, Any]:
    facts = exact_facts()
    cases: dict[str, tuple[list[str], Any]] = {
        "claim-mark-before-freelist-build":
            (["boot_order", "mark_before_EXT_freelist_build_reachable"], True),
        "change-base-root-count": (["boot_order", "base_root_count"], 0),
        "promote-X-to-oracle": (["boot_order", "X_08_to_05"], "monotonic oracle"),
        "reuse-C07A": (["durable_witness", "address"], "0xc07a"),
        "move-witness-into-BSS": (["durable_witness", "address"], "0xb9c8"),
        "move-witness-into-static-stack":
            (["durable_witness", "address"], "0xc074"),
        "move-witness-into-fixed-C2-state":
            (["durable_witness", "address"], "0xc080"),
        "move-witness-into-diagnostic-record":
            (["durable_witness", "address"], "0xc03f"),
        "drop-owner-disjointness":
            (["durable_witness", "disjoint_from_all_post_ownership_owners"], False),
        "drop-fourth-row":
            (["decision_table", "post_entry_PC_with_reset_durable_slot"], "other"),
        "claim-diagnostic-built":
            (["durable_witness", "diagnostic_identity_built"], True),
        "claim-contact-authorized": (["limits", "contact_authorized"], True),
    }
    rejected = []
    for name, (path, replacement) in cases.items():
        trial = deepcopy(facts)
        cursor: Any = trial
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except ClosureError:
            rejected.append(name)
        else:
            raise ClosureError(f"mutation survived: {name}")

    # One ownership mutation per post-ownership owner proves the general rule
    # at the chosen address.  Keep the witness identity fixed and extend each
    # owner over it in turn, so rejection cannot come merely from the fixed
    # $B5C3 address check above.
    for index, row in enumerate(facts["owner_ranges"]):
        trial = deepcopy(facts)
        trial["owner_ranges"][index]["start"] = WITNESS
        trial["owner_ranges"][index]["end_exclusive"] = WITNESS + 1
        try:
            audit(trial)
        except ClosureError:
            continue
        raise ClosureError(f"boot-owner overlap survived: {row['name']}")
    require(len(rejected) == len(cases), "mutation count drift")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "active_owner_placements_rejected": len(facts["owner_ranges"])}


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("selftest", "write", "check"))
    args = parser.parse_args()
    try:
        if args.command == "selftest":
            result = selftest()
            print(f"BOOT ORDER/WITNESS SELFTEST PASS mutations={result['mutations']} "
                  f"owner-placements={result['active_owner_placements_rejected']}")
            return 0
        value = expected()
        if args.command == "write":
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_bytes(canonical(value))
            print("BOOT ORDER/WITNESS WRITE PASS root-scan=post-mem-init "
                  "slot=$B5C3 contact=closed")
            return 0
        require(RECEIPT.is_file() and RECEIPT.read_bytes() == canonical(value),
                "boot-order/durable-witness receipt drift; run write deliberately")
        print("BOOT ORDER/WITNESS PASS root-scan=post-mem-init "
              "slot=$B5C3 contact=closed")
        return 0
    except (ClosureError, KeyError, ValueError) as exc:
        print(f"BOOT ORDER/WITNESS FIRST RED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
