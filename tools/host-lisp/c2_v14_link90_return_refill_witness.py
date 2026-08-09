#!/usr/bin/env python3
"""Build and decode the non-promotable Link-90 return/refill witness."""

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


CONFIG = ROOT / "config/c2-v14-link90-return-refill-witness.json"
OWNER = ROOT / "docs/planning/1.4-parity-pilot-work-plan.md"
VM = ROOT / "src/vm.c"
MAIN = ROOT / "products/runtime-core/main.c"
WRAPPER = ROOT / "scripts/c2-v14-link90-return-refill-cc.sh"
HW = ROOT / "scripts/c2-v14-link90-return-refill-witness-hw.sh"
BUILDER = ROOT / "tools/host-lisp/ship_builder.py"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PREPARATION = EVIDENCE / (
    "c2.3-v1.4-link90-return-refill-witness-preparation-receipt.json")
RESULT = EVIDENCE / (
    "c2.3-v1.4-link90-return-refill-witness-device-receipt.json")
BASE = ROOT / "build/post-promotion/v14/link90-return-refill-witness"
DEPLOYMENT = BASE / "deployment.json"
RUN = BASE / "run"


WitnessError = shared.WitnessError
require = shared.require
sha = shared.sha
bind = shared.bind
load = shared.load
write_json = shared.write_json
run = shared.run


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
        "layout": ["helper_return_tag", "helper_return_status", "refill_stage"],
        "initial": [49, 66, 83], "helper_return_tag": 209,
        "refill_complete": 226, "status_value_unconstrained": True,
        "tag_written_after_status": True, "ordinary_ram_only": True,
    }, "return/refill witness contract drift")
    edges = facts["edges"]
    require(edges["artifact_bound"] is True
            and edges["status_immediately_after_second_helper"] is True
            and edges["status_before_ok_branch"] is True
            and edges["refill_after_successful_load"] is True,
            "return/refill placement drift")


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
        "constrain-status": (["witness", "status_value_unconstrained"], False),
        "tag-before-status": (["witness", "tag_written_after_status"], False),
        "drop-artifact-bind": (["edges", "artifact_bound"], False),
        "status-after-branch": (["edges", "status_before_ok_branch"], False),
        "refill-before-load": (["edges", "refill_after_successful_load"], False),
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
            raise WitnessError(f"return/refill mutation survived: {name}")
    return rejected


def prepare() -> int:
    head = shared.clean_head()
    config = load(CONFIG)
    owner = " ".join(OWNER.read_text(encoding="utf-8").split())
    vm_source = VM.read_text(encoding="utf-8")
    main_source = MAIN.read_text(encoding="utf-8")
    wrapper_source = WRAPPER.read_text(encoding="utf-8")
    require(config["status"] ==
            "owner-authorized-non-promotable-return-refill-witness",
            "owner authorization status drift")
    for token in (
        "witness contact 4", "raw return status", "tag byte",
        "after the reload/refill completes", "zero product bytes",
        "no Link 91", "One contact, postcondition read",
    ):
        require(token.lower() in owner.lower(),
                f"owner authorization text absent: {token}")
    for token in (
        "LISP65_V14_RETURN_REFILL_WITNESS", "helper_return_tag",
        "helper_return_status", "refill_stage",
        "LISP65_V14_RR_HELPER_RETURN(bank, off, pcur, vm_status);",
        "LISP65_V14_RR_REFILL(bank, off, pc_);",
    ):
        require(token in vm_source, f"return/refill VM seam drift: {token}")
    require(vm_source.index("LISP65_V14_RR_HELPER_RETURN(bank, off, pcur, vm_status);")
            < vm_source.index("if (vm_status != VM_OK) { r = res; goto done; }"),
            "raw return witness moved after the status branch")
    refill_load = "if (!vm_object_load(bank, off, (uint16_t)(payload_off + pc_), winlen"
    require(vm_source.index(refill_load)
            < vm_source.index("LISP65_V14_RR_REFILL(bank, off, pc_);"),
            "refill witness moved before the successful load")
    require("lisp65_v14_return_refill_witness_reset();" in main_source,
            "return/refill reset is not bound to Runtime entry")
    for token in (
        "LISP65_V14_RR_SHAPE_OFF=0x06e1",
        "LISP65_V14_RR_SECOND_RETURN_PC=0x002e",
    ):
        require(token in wrapper_source, f"diagnostic wrapper drift: {token}")

    prior = load(ROOT / config["prior_witness_receipt"])
    require(prior["status"] == "ATTRIBUTED-REFILL-NOT-COMPLETED"
            and prior["device"]["witness_bytes"] == [17, 34, 51, 68, 85],
            "contact-3 boundary authority drift")
    edges = shared.artifact_edges(config)
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
            "inactive return/refill seams changed the ordinary Runtime ELF")

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
    witness = shared.symbol_row(truth, config["witness_symbol"], 3)
    state = shared.symbol_row(truth, config["runtime_state_symbol"], 1)
    control_names = {row.name for row in control_truth.symbols}
    require(config["witness_symbol"] not in control_names,
            "return/refill witness escaped into the ordinary Runtime")
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
            "layout": ["helper_return_tag", "helper_return_status", "refill_stage"],
            "initial": config["initial_bytes"],
            "helper_return_tag": config["helper_return_tag"],
            "refill_complete": config["refill_stage"],
            "status_value_unconstrained": True,
            "tag_written_after_status": True, "ordinary_ram_only": True,
        },
        "edges": {
            "artifact_bound": True,
            "status_immediately_after_second_helper": True,
            "status_before_ok_branch": True,
            "refill_after_successful_load": True,
            **edges,
        },
    }
    audit(facts)
    rejected = mutation_check(facts)
    deployment = {
        "format": "lisp65-c2.3-v1.4-link90-return-refill-deployment-v1",
        "status": "prepared", "source_commit": head, "candidate_link": 90,
        "image": bind(diagnostic), "runtime_elf": bind(diagnostic_elf),
        "remote": config["remote"], "terminal_value": config["terminal_value"],
        "runtime_state": state, "witness": witness,
    }
    write_json(DEPLOYMENT, deployment)
    receipt = {
        "format": "lisp65-c2.3-v1.4-link90-return-refill-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "PREPARED-NON-PROMOTABLE-RETURN-REFILL-WITNESS",
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
            "contact_3": bind(ROOT / config["prior_witness_receipt"]),
            "deployment": bind(DEPLOYMENT),
        },
    }
    write_json(PREPARATION, receipt)
    print(f"RETURN REFILL PREPARED host=2 mutations={len(rejected)} "
          f"witness={witness['address']}+3")
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
            "PREPARED-NON-PROMOTABLE-RETURN-REFILL-WITNESS",
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
            "return/refill hardware contact already consumed")
    print("RETURN REFILL DRY RUN PASS contact=1 sentinels=31/42/53 tag=d1")
    return 0


def classify(values: list[int], ok_status: int) -> tuple[str, str]:
    tag, status, refill = values
    if values == [49, 66, 83]:
        return ("BOUNDED-FIRST-RED-HELPER-RETURN-NOT-REACHED",
                "the second helper return edge was not reached")
    require(tag == 209, f"unknown helper-return tag: {tag}")
    if status != ok_status:
        require(refill == 83,
                "non-OK helper return cannot precede a completed caller refill")
        return ("ATTRIBUTED-HELPER-NON-OK-RETURN",
                f"second unlock helper returned raw VM status {status}")
    if refill == 83:
        return ("ATTRIBUTED-RELOAD-REFILL-NOT-COMPLETED",
                "second unlock helper returned VM_OK; caller reload/refill did not complete")
    if refill == 226:
        return ("ATTRIBUTED-AFTER-REFILL",
                "second unlock helper returned VM_OK and caller refill completed")
    raise WitnessError(f"unknown refill-stage value: {refill}")


def analyze() -> int:
    config = load(CONFIG)
    deployment = load(DEPLOYMENT)
    witness_path = RUN / "return_refill_witness.bin"
    state_path = RUN / "lisp65_runtime_state.bin"
    readback_path = RUN / "readback.d81"
    require(witness_path.is_file() and witness_path.stat().st_size == 3,
            "three-byte return/refill witness absent")
    require(state_path.is_file() and state_path.stat().st_size == 1,
            "runtime-state capture absent")
    require(readback_path.is_file(), "D81 readback absent")
    require(sha(readback_path) == deployment["image"]["sha256"],
            "device-upload D81 readback drift")
    state = state_path.read_bytes()[0]
    require(state == config["terminal_value"],
            f"unexpected runtime state: {state}")
    values = list(witness_path.read_bytes())
    status, conclusion = classify(values, config["ok_status"])
    reference_image = ROOT / config["reference_image"]
    reference_elf = ROOT / config["reference_runtime_elf"]
    require(sha(reference_image) == config["reference_image_sha256"]
            and sha(reference_elf) == config["reference_runtime_elf_sha256"],
            "Link-90 candidate drift after contact")
    receipt = {
        "format": "lisp65-c2.3-v1.4-link90-return-refill-device-v1",
        "recorded_on": date.today().isoformat(), "status": status,
        "candidate_link": 90, "promotable": False,
        "device": {"hardware_contacts": 1, "runtime_state": state,
                   "witness_bytes": values, "conclusion": conclusion},
        "interpretation": {"helper_return_tagged": True,
                           "refill_nonzero_sentinel": True,
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
    print(f"RETURN REFILL {status} witness={values} state={state}")
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
