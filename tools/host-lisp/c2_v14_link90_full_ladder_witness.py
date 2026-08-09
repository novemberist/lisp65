#!/usr/bin/env python3
"""Build and decode the non-promotable Link-90 full witness ladder."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v14_link90_read_edge_witness as shared  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


CONFIG = ROOT / "config/c2-v14-link90-full-ladder-witness.json"
OWNER = ROOT / "docs/planning/1.4-parity-pilot-work-plan.md"
VM = ROOT / "src/vm.c"
MAIN = ROOT / "products/runtime-core/main.c"
WRAPPER = ROOT / "scripts/c2-v14-link90-full-ladder-cc.sh"
HW = ROOT / "scripts/c2-v14-link90-full-ladder-witness-hw.sh"
BUILDER = ROOT / "tools/host-lisp/ship_builder.py"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PREPARATION = EVIDENCE / (
    "c2.3-v1.4-link90-full-ladder-witness-preparation-receipt.json")
RESULT = EVIDENCE / (
    "c2.3-v1.4-link90-full-ladder-witness-device-receipt.json")
BASE = ROOT / "build/post-promotion/v14/link90-full-ladder-witness"
DEPLOYMENT = BASE / "deployment.json"
RUN = BASE / "run"


WitnessError = shared.WitnessError
require = shared.require
sha = shared.sha
bind = shared.bind
load = shared.load
write_json = shared.write_json


def artifact_edges(config: dict[str, Any]) -> dict[str, Any]:
    manifest = load(ROOT / config["artifact_manifest"])
    by_name = {row["name"]: row for row in manifest["entries"]}
    shape = by_name["m65-sprite-shape"]
    helper = by_name["m65-byte-write"]
    shape_address = int(shape["ext_addr"], 16)
    helper_address = int(helper["ext_addr"], 16)
    require(shape_address == (config["shape_bank"] << 16) + config["shape_offset"],
            "Link-90 shape object address drift")
    require(helper_address == (config["helper_bank"] << 16) + config["helper_offset"]
            and helper["length"] == config["helper_length"],
            "Link-90 byte-write helper identity drift")
    shape_ops = dict(shared.disassembly_block(
        ROOT / config["artifact_disassembly"], "m65-sprite-shape"))
    helper_ops = dict(shared.disassembly_block(
        ROOT / config["artifact_disassembly"], "m65-byte-write"))
    expected_shape = {
        0x1B: "PUSHLIT 1", 0x1D: "PUSHI8 47", 0x1F: "PUSHI8 71",
        0x21: "CALL lit=2 argc=3", 0x24: "DROP", 0x25: "PUSHLIT 1",
        0x27: "PUSHI8 47", 0x29: "PUSHI8 83",
        0x2B: "CALL lit=2 argc=3", 0x2E: "DROP",
    }
    require(all(shape_ops.get(offset) == instruction
                for offset, instruction in expected_shape.items()),
            "Link-90 two-unlock ladder seam drift")
    require(helper_ops == {
        0x00: "PUSHARG0", 0x01: "PUSHARG1", 0x02: "PUSHARG2",
        0x03: "CALLPRIM prim=62:poke argc=3", 0x06: "RET",
    }, "Link-90 m65-byte-write payload drift")
    header = 7 + 2 * shape["lit_count"]
    require(header == 21 and 56 - header == 35,
            "Link-90 streamed window geometry drift")
    require(config["first_return_pc"] == 0x24
            and config["second_return_pc"] == 0x2E,
            "configured ladder PCs drift")
    return {
        "shape_bank": config["shape_bank"],
        "shape_offset": f"0x{config['shape_offset']:04x}",
        "shape_header_bytes": header,
        "initial_payload_window_bytes": 56 - header,
        "first_call_pc": "0x0021", "first_return_pc": "0x0024",
        "second_call_pc": "0x002b", "second_return_pc": "0x002e",
        "helper_bank": config["helper_bank"],
        "helper_offset": f"0x{config['helper_offset']:04x}",
        "helper_length": config["helper_length"],
        "helper_payload": [row for _, row in sorted(helper_ops.items())],
    }


def audit(facts: dict[str, Any]) -> None:
    require(facts["identity"] == {
        "promotable": False, "product_candidate_bytes_changed": 0,
        "product_links": 0, "diagnostic_identities": 1,
    }, "diagnostic identity boundary drift")
    require(facts["contact"] == {
        "hardware_contacts": 1, "physical_keys": 0, "virtual_keys": 0,
        "screen_polls_during_execution": 0,
        "monitor_reads_during_execution": 0, "post_stop_ram_reads": 2,
    }, "device-contact boundary drift")
    require(facts["witness"] == {
        "layout": ["first_return_tag", "first_return_status",
                   "middle_refill_stage", "second_entry_stage"],
        "initial": [49, 66, 83, 100], "first_return_tag": 209,
        "middle_refill_complete": 226, "second_entry_complete": 243,
        "status_value_unconstrained": True, "tag_written_after_status": True,
        "second_entry_state_coupled": True, "ordinary_ram_only": True,
    }, "full-ladder witness contract drift")
    edges = facts["edges"]
    require(edges["artifact_bound"] is True
            and edges["first_status_before_ok_branch"] is True
            and edges["middle_refill_after_successful_load"] is True
            and edges["second_entry_before_object_load"] is True,
            "full-ladder placement drift")


def mutation_check(facts: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[list[Any], Any]] = {
        "make-promotable": (["identity", "promotable"], True),
        "claim-product-delta": (["identity", "product_candidate_bytes_changed"], 1),
        "claim-product-link": (["identity", "product_links"], 1),
        "add-physical-key": (["contact", "physical_keys"], 1),
        "add-virtual-key": (["contact", "virtual_keys"], 1),
        "add-screen-poll": (["contact", "screen_polls_during_execution"], 1),
        "read-during-execution": (["contact", "monitor_reads_during_execution"], 1),
        "drop-post-stop-read": (["contact", "post_stop_ram_reads"], 1),
        "zero-tag-sentinel": (["witness", "initial", 0], 0),
        "zero-status-sentinel": (["witness", "initial", 1], 0),
        "zero-refill-sentinel": (["witness", "initial", 2], 0),
        "zero-entry-sentinel": (["witness", "initial", 3], 0),
        "constrain-status": (["witness", "status_value_unconstrained"], False),
        "tag-before-status": (["witness", "tag_written_after_status"], False),
        "uncouple-second-entry": (["witness", "second_entry_state_coupled"], False),
        "drop-artifact-bind": (["edges", "artifact_bound"], False),
        "status-after-branch": (["edges", "first_status_before_ok_branch"], False),
        "refill-before-load": (["edges", "middle_refill_after_successful_load"], False),
        "entry-after-load": (["edges", "second_entry_before_object_load"], False),
    }
    rejected: dict[str, str] = {}
    for name, (path, value) in cases.items():
        candidate = deepcopy(facts)
        target: Any = candidate
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = value
        try:
            audit(candidate)
        except WitnessError as error:
            rejected[name] = str(error)
        else:
            raise WitnessError(f"full-ladder mutation survived: {name}")
    return rejected


def prepare() -> int:
    head = shared.clean_head()
    config = load(CONFIG)
    owner = " ".join(OWNER.read_text(encoding="utf-8").split())
    owner = owner.replace("*", "").replace("`", "")
    vm_source = VM.read_text(encoding="utf-8")
    main_source = MAIN.read_text(encoding="utf-8")
    wrapper_source = WRAPPER.read_text(encoding="utf-8")
    require(config["status"] ==
            "owner-authorized-non-promotable-full-ladder-witness",
            "owner authorization status drift")
    for token in (
        "witness contact 5", "full ladder", "first unlock helper",
        "intervening refill", "second helper's entry", "zero product bytes",
        "no Link 91", "one contact, postcondition read",
    ):
        require(token.lower() in owner.lower(),
                f"owner authorization text absent: {token}")
    for token in (
        "LISP65_V14_FULL_LADDER_WITNESS", "first_return_tag",
        "first_return_status", "middle_refill_stage", "second_entry_stage",
        "LISP65_V14_LADDER_FIRST_RETURN(bank, off, pcur, vm_status);",
        "LISP65_V14_LADDER_MIDDLE_REFILL(bank, off, pc_);",
        "LISP65_V14_LADDER_SECOND_ENTRY(bank, off);",
    ):
        require(token in vm_source, f"full-ladder VM seam drift: {token}")
    first_call = vm_source.index(
        "LISP65_V14_LADDER_FIRST_RETURN(bank, off, pcur, vm_status);")
    require(first_call < vm_source.index(
        "if (vm_status != VM_OK) { r = res; goto done; }", first_call),
        "first-return status moved after the OK branch")
    refill_call = vm_source.index(
        "LISP65_V14_LADDER_MIDDLE_REFILL(bank, off, pc_);")
    require(vm_source.rfind("if (!vm_object_load(", 0, refill_call) >= 0,
            "middle-refill witness lost its successful load predecessor")
    entry_call = vm_source.index("LISP65_V14_LADDER_SECOND_ENTRY(bank, off);")
    require(entry_call < vm_source.index("base = gc_rootsp;", entry_call),
            "second-helper entry witness moved after VM setup work")
    require("lisp65_v14_full_ladder_witness_reset();" in main_source,
            "full-ladder reset is not bound to Runtime entry")
    for token in (
        "LISP65_V14_LADDER_SHAPE_OFF=0x06e1",
        "LISP65_V14_LADDER_FIRST_RETURN_PC=0x0024",
        "LISP65_V14_LADDER_HELPER_OFF=0x0310",
    ):
        require(token in wrapper_source, f"diagnostic wrapper drift: {token}")

    prior = load(ROOT / config["prior_witness_receipt"])
    require(prior["status"] == "BOUNDED-FIRST-RED-HELPER-RETURN-NOT-REACHED"
            and prior["device"]["witness_bytes"] == [49, 66, 83],
            "contact-4 boundary authority drift")
    edges = artifact_edges(config)
    reference_image = ROOT / config["reference_image"]
    reference_elf = ROOT / config["reference_runtime_elf"]
    reference_receipt = load(ROOT / config["reference_receipt"])
    require(sha(reference_image) == config["reference_image_sha256"],
            "Link-90 reference image drift")
    require(sha(reference_elf) == config["reference_runtime_elf_sha256"],
            "Link-90 reference Runtime ELF drift")
    before = {reference_image: sha(reference_image), reference_elf: sha(reference_elf)}

    control = ROOT / config["control_output"]
    diagnostic = ROOT / config["diagnostic_output"]
    shared.build_image(control, config, None)
    control_elf = control.with_suffix(".runtime.elf")
    require(sha(control_elf) == config["reference_runtime_elf_sha256"],
            "inactive full-ladder seams changed the ordinary Runtime ELF")
    toolchain = diagnostic.parent / "diagnostic-toolchain"
    toolchain.mkdir(parents=True, exist_ok=False)
    cc = toolchain / "mos-mega65-clang"
    readobj = toolchain / "llvm-readobj"
    cc.symlink_to(WRAPPER)
    readobj.symlink_to(READOBJ)
    diagnostic_build = shared.build_image(diagnostic, config, cc)
    diagnostic_elf = diagnostic.with_suffix(".runtime.elf")
    diagnostic_receipt = load(diagnostic.with_suffix(".receipt.json"))
    require(diagnostic_receipt["build_identity_sha256"]
            == reference_receipt["build_identity_sha256"],
            "diagnostic identity changed the emitted Lisp artifact")
    require(diagnostic_receipt["host_execution"]["status"] == "passed",
            "diagnostic identity host execution is not green")

    truth = ElfTruth.read(diagnostic_elf, llvm_readobj=READOBJ)
    control_truth = ElfTruth.read(control_elf, llvm_readobj=READOBJ)
    witness = shared.symbol_row(truth, config["witness_symbol"], 4)
    state = shared.symbol_row(truth, config["runtime_state_symbol"], 1)
    require(config["witness_symbol"] not in {row.name for row in control_truth.symbols},
            "full-ladder witness escaped into the ordinary Runtime")
    reserve = truth.symbol(
        "__lisp65_runtime_core_inline_required_post_boot_reserve_param").value
    actual_stack_heap = truth.symbol("__stack").value - truth.symbol("__heap_start").value
    require(reserve == config["diagnostic_post_boot_reserve_param"]
            and actual_stack_heap >= 8192 + reserve,
            "diagnostic-only stack/heap reserve proof drift")
    require(all(sha(path) == digest for path, digest in before.items()),
            "Link-90 product candidate changed during diagnostic build")

    facts = {
        "identity": {"promotable": False, "product_candidate_bytes_changed": 0,
                     "product_links": 0, "diagnostic_identities": 1},
        "contact": {"hardware_contacts": 1, "physical_keys": 0,
                    "virtual_keys": 0, "screen_polls_during_execution": 0,
                    "monitor_reads_during_execution": 0,
                    "post_stop_ram_reads": 2},
        "witness": {
            "layout": ["first_return_tag", "first_return_status",
                       "middle_refill_stage", "second_entry_stage"],
            "initial": config["initial_bytes"],
            "first_return_tag": config["first_return_tag"],
            "middle_refill_complete": config["middle_refill_stage"],
            "second_entry_complete": config["second_entry_stage"],
            "status_value_unconstrained": True, "tag_written_after_status": True,
            "second_entry_state_coupled": True, "ordinary_ram_only": True,
        },
        "edges": {"artifact_bound": True,
                  "first_status_before_ok_branch": True,
                  "middle_refill_after_successful_load": True,
                  "second_entry_before_object_load": True, **edges},
    }
    audit(facts)
    rejected = mutation_check(facts)
    deployment = {
        "format": "lisp65-c2.3-v1.4-link90-full-ladder-deployment-v1",
        "status": "prepared", "source_commit": head, "candidate_link": 90,
        "image": bind(diagnostic), "runtime_elf": bind(diagnostic_elf),
        "remote": config["remote"], "terminal_value": config["terminal_value"],
        "runtime_state": state, "witness": witness,
    }
    write_json(DEPLOYMENT, deployment)
    receipt = {
        "format": "lisp65-c2.3-v1.4-link90-full-ladder-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "PREPARED-NON-PROMOTABLE-FULL-LADDER-WITNESS",
        "candidate_link": 90, "facts": facts,
        "diagnostic_runtime_contract": {
            "product_wall_changed": False, "post_boot_reserve_param": reserve,
            "actual_stack_heap_bytes": actual_stack_heap},
        "control": {"image": bind(control), "runtime_elf": bind(control_elf),
                    "byteidentical_to_link90_runtime_elf": True},
        "diagnostic": {"image": bind(diagnostic), "runtime_elf": bind(diagnostic_elf),
                       "ship_receipt": bind(diagnostic.with_suffix(".receipt.json")),
                       "build_output": diagnostic_build},
        "reference_candidate": {"image": bind(reference_image),
                                "runtime_elf": bind(reference_elf),
                                "unchanged_after_build": True},
        "verification": {"executions": 2, "mutation_count": len(rejected),
                         "mutations_rejected": rejected},
        "bindings": {
            "config": bind(CONFIG), "owner_review": bind(OWNER), "vm": bind(VM),
            "runtime_main": bind(MAIN), "compiler_wrapper": bind(WRAPPER),
            "hardware_script": bind(HW), "ship_builder": bind(BUILDER),
            "driver": bind(DRIVER), "artifact_manifest": bind(
                ROOT / config["artifact_manifest"]),
            "artifact_disassembly": bind(ROOT / config["artifact_disassembly"]),
            "contact_4": bind(ROOT / config["prior_witness_receipt"]),
            "deployment": bind(DEPLOYMENT),
        },
    }
    write_json(PREPARATION, receipt)
    print(f"FULL LADDER PREPARED host=2 mutations={len(rejected)} "
          f"witness={witness['address']}+4")
    return 0


def verify_preparation_bindings(preparation: dict[str, Any]) -> None:
    for name, row in preparation["bindings"].items():
        require(bind(ROOT / row["path"]) == row,
                f"prepared source binding drift: {name}")


def dry_run() -> int:
    config = load(CONFIG)
    preparation = load(PREPARATION)
    deployment = load(DEPLOYMENT)
    require(preparation["status"] ==
            "PREPARED-NON-PROMOTABLE-FULL-LADDER-WITNESS",
            "preparation status drift")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", deployment["source_commit"], "HEAD"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    require(ancestry.returncode == 0,
            "prepared identity source commit is not an ancestor of HEAD")
    verify_preparation_bindings(preparation)
    require(deployment["image"] == bind(ROOT / config["diagnostic_output"]),
            "prepared image drift")
    require(sha(ROOT / config["reference_image"]) == config["reference_image_sha256"]
            and sha(ROOT / config["reference_runtime_elf"])
            == config["reference_runtime_elf_sha256"],
            "Link-90 candidate drift")
    require(not (RUN / "contact.consumed").exists(),
            "full-ladder hardware contact already consumed")
    print("FULL LADDER DRY RUN PASS contact=1 sentinels=31/42/53/64")
    return 0


def classify(values: list[int], config: dict[str, Any]) -> tuple[str, str]:
    tag, status, refill, entry = values
    if values == config["initial_bytes"]:
        return ("ATTRIBUTED-FIRST-HELPER-RETURN-NOT-REACHED",
                "the first unlock helper did not reach its return edge")
    require(tag == config["first_return_tag"],
            f"unknown first-helper return tag: {tag}")
    if status != config["ok_status"]:
        require(refill == 83 and entry == 100,
                "non-OK first return cannot precede later completed stages")
        return ("ATTRIBUTED-FIRST-HELPER-NON-OK-RETURN",
                f"first unlock helper returned raw VM status {status}")
    if refill == 83:
        require(entry == 100, "second entry cannot precede the middle refill")
        return ("ATTRIBUTED-MIDDLE-REFILL-NOT-COMPLETED",
                "first helper returned VM_OK; the middle caller refill did not complete")
    require(refill == config["middle_refill_stage"],
            f"unknown middle-refill stage: {refill}")
    if entry == 100:
        return ("ATTRIBUTED-PATH-TO-SECOND-HELPER-ENTRY",
                "middle refill completed; the second helper entry was not reached")
    require(entry == config["second_entry_stage"],
            f"unknown second-entry stage: {entry}")
    return ("ATTRIBUTED-SECOND-HELPER-EXECUTION",
            "second helper entry was reached; contact 4 proves its return edge was not")


def analyze() -> int:
    config = load(CONFIG)
    deployment = load(DEPLOYMENT)
    witness_path = RUN / "full_ladder_witness.bin"
    state_path = RUN / "lisp65_runtime_state.bin"
    readback_path = RUN / "readback.d81"
    require(witness_path.is_file() and witness_path.stat().st_size == 4,
            "four-byte full-ladder witness absent")
    require(state_path.is_file() and state_path.stat().st_size == 1,
            "runtime-state capture absent")
    require(readback_path.is_file(), "D81 readback absent")
    require(sha(readback_path) == deployment["image"]["sha256"],
            "device-upload D81 readback drift")
    state = state_path.read_bytes()[0]
    require(state == config["terminal_value"],
            f"unexpected runtime state: {state}")
    values = list(witness_path.read_bytes())
    status, conclusion = classify(values, config)
    reference_image = ROOT / config["reference_image"]
    reference_elf = ROOT / config["reference_runtime_elf"]
    require(sha(reference_image) == config["reference_image_sha256"]
            and sha(reference_elf) == config["reference_runtime_elf_sha256"],
            "Link-90 candidate drift after contact")
    receipt = {
        "format": "lisp65-c2.3-v1.4-link90-full-ladder-device-v1",
        "recorded_on": date.today().isoformat(), "status": status,
        "candidate_link": 90, "promotable": False,
        "device": {"hardware_contacts": 1, "runtime_state": state,
                   "witness_bytes": values, "conclusion": conclusion},
        "interpretation": {"first_return_tagged": True,
                           "later_nonzero_sentinels": True,
                           "contact_4_return_edge_authority": True,
                           "product_fix_authorized": False},
        "candidate_unchanged": {"image": bind(reference_image),
                                "runtime_elf": bind(reference_elf)},
        "bindings": {
            "preparation": bind(PREPARATION), "deployment": bind(DEPLOYMENT),
            "config": bind(CONFIG), "owner_review": bind(OWNER),
            "driver": bind(DRIVER), "hardware_script": bind(HW),
            "witness": bind(witness_path), "runtime_state": bind(state_path),
            "device_readback": bind(readback_path),
            "fresh_basic": bind(RUN / "fresh-basic.txt"),
            "upload_log": bind(RUN / "upload.log"),
            "contact_consumed": bind(RUN / "contact.consumed"),
        },
    }
    write_json(RESULT, receipt)
    print(f"FULL LADDER {status} witness={values} state={state}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "dry-run", "analyze"))
    action = parser.parse_args().action
    try:
        return {"prepare": prepare, "dry-run": dry_run,
                "analyze": analyze}[action]()
    except WitnessError as error:
        print(f"FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
