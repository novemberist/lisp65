#!/usr/bin/env python3
"""Build and decode the non-promotable Link-90 mechanism witness."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v14_link90_read_edge_witness as shared  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


CONFIG = ROOT / "config/c2-v14-link90-mechanism-witness.json"
OWNER = ROOT / "docs/planning/1.4-parity-pilot-work-plan.md"
VM = ROOT / "src/vm.c"
MAIN = ROOT / "products/runtime-core/main.c"
WRAPPER = ROOT / "scripts/c2-v14-link90-mechanism-cc.sh"
HW = ROOT / "scripts/c2-v14-link90-mechanism-witness-hw.sh"
BUILDER = ROOT / "tools/host-lisp/ship_builder.py"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PREPARATION = EVIDENCE / (
    "c2.3-v1.4-link90-mechanism-witness-preparation-receipt.json")
RESULT = EVIDENCE / (
    "c2.3-v1.4-link90-mechanism-witness-device-receipt.json")
BASE = ROOT / "build/post-promotion/v14/link90-mechanism-witness"
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
    require(int(shape["ext_addr"], 16) ==
            (config["shape_bank"] << 16) + config["shape_offset"],
            "Link-90 shape object address drift")
    require(int(helper["ext_addr"], 16) ==
            (config["helper_bank"] << 16) + config["helper_offset"]
            and helper["length"] == config["helper_length"],
            "Link-90 byte-write helper identity drift")
    shape_ops = dict(shared.disassembly_block(
        ROOT / config["artifact_disassembly"], "m65-sprite-shape"))
    helper_ops = dict(shared.disassembly_block(
        ROOT / config["artifact_disassembly"], "m65-byte-write"))
    expected_span = {
        0x24: "DROP", 0x25: "PUSHLIT 1", 0x27: "PUSHI8 47",
        0x29: "PUSHI8 83", 0x2B: "CALL lit=2 argc=3", 0x2E: "DROP",
    }
    require(all(shape_ops.get(offset) == instruction
                for offset, instruction in expected_span.items()),
            "Link-90 post-refill caller span drift")
    require(helper_ops == {
        0x00: "PUSHARG0", 0x01: "PUSHARG1", 0x02: "PUSHARG2",
        0x03: "CALLPRIM prim=62:poke argc=3", 0x06: "RET",
    }, "Link-90 m65-byte-write payload drift")
    header = 7 + 2 * shape["lit_count"]
    require(header == 21 and 56 - header == 35,
            "Link-90 streamed window geometry drift")
    descriptor = ((0x6000 + config["helper_directory"]) << 1) & 0xffff
    require(descriptor == config["expected_descriptor"],
            "configured byte-write BCode descriptor drift")
    return {
        "artifact_bound": True,
        "shape_bank": config["shape_bank"],
        "shape_offset": f"0x{config['shape_offset']:04x}",
        "shape_header_bytes": header,
        "initial_payload_window_bytes": 56 - header,
        "post_refill_span": "0x0024..0x002b",
        "second_call_pc": "0x002b",
        "second_return_pc": "0x002e",
        "expected_decoded_payload": config["expected_decode"],
        "helper_bank": config["helper_bank"],
        "helper_offset": f"0x{config['helper_offset']:04x}",
        "helper_directory": config["helper_directory"],
        "expected_descriptor": f"0x{descriptor:04x}",
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
        "layout": ["decode_tag", "decoded_opcode", "decoded_literal",
                   "decoded_argc", "resolution_tag", "descriptor_low",
                   "descriptor_high", "directory_low", "directory_high",
                   "pre_inner_stage"],
        "initial": [17, 33, 49, 65, 18, 34, 50, 66, 82, 19],
        "decode_tag": 161, "resolution_tag": 178,
        "pre_inner_stage": 195,
        "raw_values_unconstrained": True,
        "separate_completion_tags": True,
        "tags_written_after_values": True,
        "ordinary_ram_only": True,
    }, "mechanism-witness contract drift")
    edges = facts["edges"]
    require(edges["artifact_bound"] is True
            and edges["payload_after_opcode_fetch"] is True
            and edges["payload_before_dispatch"] is True
            and edges["resolution_after_descriptor"] is True
            and edges["resolution_before_argument_pop"] is True
            and edges["pre_inner_after_stack_guard"] is True
            and edges["pre_inner_before_vm_run_inner"] is True,
            "mechanism-witness placement drift")


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
        "zero-decode-tag": (["witness", "initial", 0], 0),
        "zero-resolution-tag": (["witness", "initial", 4], 0),
        "zero-preinner-sentinel": (["witness", "initial", 9], 0),
        "constrain-raw-values": (["witness", "raw_values_unconstrained"], False),
        "drop-completion-tags": (["witness", "separate_completion_tags"], False),
        "tags-before-values": (["witness", "tags_written_after_values"], False),
        "drop-artifact-bind": (["edges", "artifact_bound"], False),
        "payload-before-fetch": (["edges", "payload_after_opcode_fetch"], False),
        "payload-after-dispatch": (["edges", "payload_before_dispatch"], False),
        "resolve-before-descriptor": (["edges", "resolution_after_descriptor"], False),
        "resolve-after-pop": (["edges", "resolution_before_argument_pop"], False),
        "preinner-before-guard": (["edges", "pre_inner_after_stack_guard"], False),
        "preinner-after-inner": (["edges", "pre_inner_before_vm_run_inner"], False),
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
            raise WitnessError(f"mechanism-witness mutation survived: {name}")
    return rejected


def source_edges() -> dict[str, bool]:
    source = VM.read_text(encoding="utf-8")
    dispatch = source.index("        op = RD8();")
    payload = source.index("        LISP65_V14_MECH_PAYLOAD(", dispatch)
    switch = source.index("        switch (op) {", dispatch)
    call = source.index("        case OP_CALL:", switch)
    descriptor = source.index("            int di = IS_BCODE(sym)", call)
    resolution = source.index("            LISP65_V14_MECH_RESOLVE(", descriptor)
    args = source.index("            obj cargs[VM_MAXARGS]", resolution)
    wrapper = source.index("obj vm_run(uint8_t bank")
    guard = source.index("    if (lisp_stack_low())", wrapper)
    pre_inner = source.index("    LISP65_V14_MECH_PRE_INNER(bank, off);", guard)
    inner = source.index("    return vm_run_inner(bank, off", pre_inner)
    macro = source.index("#define LISP65_V14_MECH_RESOLVE")
    descriptor_store = source.index(
        "lisp65_v14_mechanism_witness.descriptor_low", macro)
    resolution_tag = source.index(
        "lisp65_v14_mechanism_witness.resolution_tag = 0xb2u", descriptor_store)
    decode_macro = source.index("#define LISP65_V14_MECH_PAYLOAD")
    opcode_store = source.index(
        "lisp65_v14_mechanism_witness.decoded_opcode", decode_macro)
    decode_tag = source.index(
        "lisp65_v14_mechanism_witness.decode_tag = 0xa1u", opcode_store)
    return {
        "payload_after_opcode_fetch": dispatch < payload,
        "payload_before_dispatch": payload < switch,
        "resolution_after_descriptor": descriptor < resolution,
        "resolution_before_argument_pop": resolution < args,
        "pre_inner_after_stack_guard": guard < pre_inner,
        "pre_inner_before_vm_run_inner": pre_inner < inner,
        "decode_tag_after_values": opcode_store < decode_tag,
        "resolution_tag_after_values": descriptor_store < resolution_tag,
    }


def prepare() -> int:
    head = shared.clean_head()
    config = load(CONFIG)
    owner = " ".join(OWNER.read_text(encoding="utf-8").split())
    owner = owner.replace("*", "").replace("`", "")
    vm_source = VM.read_text(encoding="utf-8")
    main_source = MAIN.read_text(encoding="utf-8")
    wrapper_source = WRAPPER.read_text(encoding="utf-8")
    require(config["status"] ==
            "owner-authorized-non-promotable-mechanism-witness",
            "owner authorization status drift")
    for token in (
        "witness contact 6", "mechanism witness", "payload decoding",
        "directory resolution", "stack guard", "zero product bytes",
        "no Link 91", "one contact, postcondition read",
    ):
        require(token.lower() in owner.lower(),
                f"owner authorization text absent: {token}")
    for token in (
        "LISP65_V14_MECHANISM_WITNESS", "decode_tag", "resolution_tag",
        "descriptor_low", "directory_low", "pre_inner_stage",
        "LISP65_V14_MECH_PAYLOAD(", "LISP65_V14_MECH_RESOLVE(",
        "LISP65_V14_MECH_PRE_INNER(bank, off);",
    ):
        require(token in vm_source, f"mechanism VM seam drift: {token}")
    require("lisp65_v14_mechanism_witness_reset();" in main_source,
            "mechanism-witness reset is not bound to Runtime entry")
    for token in (
        "LISP65_V14_MECH_SHAPE_OFF=0x06e1",
        "LISP65_V14_MECH_SECOND_CALL_PC=0x002b",
        "LISP65_V14_MECH_SECOND_RETURN_PC=0x002e",
        "LISP65_V14_MECH_HELPER_OFF=0x0310",
    ):
        require(token in wrapper_source, f"diagnostic wrapper drift: {token}")

    prior = load(ROOT / config["prior_witness_receipt"])
    require(prior["status"] == "ATTRIBUTED-PATH-TO-SECOND-HELPER-ENTRY"
            and prior["device"]["witness_bytes"] == [209, 0, 226, 100],
            "contact-5 boundary authority drift")
    edges = {**artifact_edges(config), **source_edges()}
    require(edges["decode_tag_after_values"]
            and edges["resolution_tag_after_values"],
            "completion tags moved before raw values")

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
            "inactive mechanism seams changed the ordinary Runtime ELF")
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
    witness = shared.symbol_row(truth, config["witness_symbol"], 10)
    state = shared.symbol_row(truth, config["runtime_state_symbol"], 1)
    require(config["witness_symbol"] not in
            {row.name for row in control_truth.symbols},
            "mechanism witness escaped into the ordinary Runtime")
    reserve = truth.symbol(
        "__lisp65_runtime_core_inline_required_post_boot_reserve_param").value
    actual_stack_heap = truth.symbol("__stack").value - truth.symbol("__heap_start").value
    require(reserve == config["diagnostic_post_boot_reserve_param"]
            and actual_stack_heap >= 8192 + reserve,
            "diagnostic-only stack/heap reserve proof drift")
    require(all(sha(path) == digest for path, digest in before.items()),
            "Link-90 product candidate changed during diagnostic build")

    facts = {
        "identity": {"promotable": False,
                     "product_candidate_bytes_changed": 0,
                     "product_links": 0, "diagnostic_identities": 1},
        "contact": {"hardware_contacts": 1, "physical_keys": 0,
                    "virtual_keys": 0, "screen_polls_during_execution": 0,
                    "monitor_reads_during_execution": 0,
                    "post_stop_ram_reads": 2},
        "witness": {
            "layout": ["decode_tag", "decoded_opcode", "decoded_literal",
                       "decoded_argc", "resolution_tag", "descriptor_low",
                       "descriptor_high", "directory_low", "directory_high",
                       "pre_inner_stage"],
            "initial": config["initial_bytes"],
            "decode_tag": config["decode_tag"],
            "resolution_tag": config["resolution_tag"],
            "pre_inner_stage": config["pre_inner_stage"],
            "raw_values_unconstrained": True,
            "separate_completion_tags": True,
            "tags_written_after_values": True,
            "ordinary_ram_only": True,
        },
        "edges": edges,
    }
    audit(facts)
    rejected = mutation_check(facts)
    deployment = {
        "format": "lisp65-c2.3-v1.4-link90-mechanism-deployment-v1",
        "status": "prepared", "source_commit": head, "candidate_link": 90,
        "image": bind(diagnostic), "runtime_elf": bind(diagnostic_elf),
        "remote": config["remote"], "terminal_value": config["terminal_value"],
        "runtime_state": state, "witness": witness,
    }
    write_json(DEPLOYMENT, deployment)
    receipt = {
        "format": "lisp65-c2.3-v1.4-link90-mechanism-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "PREPARED-NON-PROMOTABLE-MECHANISM-WITNESS",
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
            "contact_5": bind(ROOT / config["prior_witness_receipt"]),
            "deployment": bind(DEPLOYMENT),
        },
    }
    write_json(PREPARATION, receipt)
    print(f"MECHANISM WITNESS PREPARED host=2 mutations={len(rejected)} "
          f"witness={witness['address']}+10")
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
            "PREPARED-NON-PROMOTABLE-MECHANISM-WITNESS",
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
            "mechanism-witness hardware contact already consumed")
    print("MECHANISM WITNESS DRY RUN PASS contact=1 bytes=10 post-stop-reads=2")
    return 0


def descriptor_kind(raw: int) -> str:
    signed = raw if raw < 0x8000 else raw - 0x10000
    if raw == 0:
        return "nil"
    if raw & 1:
        return "fixnum"
    if signed > 0:
        return "pointer"
    if raw < 0xe000:
        return "bcode"
    return "symi"


def classify(values: list[int], config: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    initial = config["initial_bytes"]
    dtag, op, li, argc, rtag, dlo, dhi, ilo, ihi, pre = values
    raw_decode = [op, li, argc]
    descriptor = dlo | (dhi << 8)
    directory_raw = ilo | (ihi << 8)
    directory = directory_raw if directory_raw < 0x8000 else directory_raw - 0x10000
    decoded_initial = values[1:4] == initial[1:4]
    resolution_initial = values[5:9] == initial[5:9]
    if dtag == initial[0]:
        require(decoded_initial and values[4:] == initial[4:],
                f"non-atomic payload witness: {values}")
        return ("ATTRIBUTED-PAYLOAD-DISPATCH-NOT-COMPLETED",
                "the refilled second CALL payload did not complete its tagged fetch",
                {"decoded_payload": None})
    require(dtag == config["decode_tag"], f"unknown decode tag: {dtag}")
    if raw_decode != config["expected_decode"]:
        require(rtag == initial[4] and resolution_initial and pre == initial[9],
                "mismatched payload cannot have later completed stages")
        return ("ATTRIBUTED-DECODED-PAYLOAD-MISMATCH",
                f"refilled bytes are {raw_decode}, expected {config['expected_decode']}",
                {"decoded_payload": raw_decode})
    if rtag == initial[4]:
        require(resolution_initial and pre == initial[9],
                f"non-atomic resolution witness: {values}")
        return ("ATTRIBUTED-LITERAL-DIRECTORY-RESOLUTION-NOT-COMPLETED",
                "CALL bytes decode correctly; lit=2 resolution did not complete",
                {"decoded_payload": raw_decode})
    require(rtag == config["resolution_tag"], f"unknown resolution tag: {rtag}")
    details = {"decoded_payload": raw_decode,
               "descriptor_raw": f"0x{descriptor:04x}",
               "descriptor_kind": descriptor_kind(descriptor),
               "directory_raw": f"0x{directory_raw:04x}",
               "directory_signed": directory}
    if descriptor != config["expected_descriptor"]:
        require(pre == initial[9],
                "wrong descriptor cannot have reached expected helper pre-inner edge")
        return ("ATTRIBUTED-REMATERIALIZED-DESCRIPTOR-MISMATCH",
                f"lit=2 resolved as 0x{descriptor:04x} ({descriptor_kind(descriptor)}), "
                f"expected 0x{config['expected_descriptor']:04x} (bcode)", details)
    if directory != config["helper_directory"]:
        require(pre == initial[9],
                "wrong directory cannot have reached expected helper pre-inner edge")
        return ("ATTRIBUTED-DIRECTORY-INDEX-MISMATCH",
                f"descriptor is correct but directory is {directory}, "
                f"expected {config['helper_directory']}", details)
    if pre == initial[9]:
        return ("ATTRIBUTED-PRE-INNER-EDGE-NOT-COMPLETED",
                "payload and directory identity are correct; the second length/address or "
                "stack-guard path did not reach vm_run_inner", details)
    require(pre == config["pre_inner_stage"], f"unknown pre-inner stage: {pre}")
    return ("ATTRIBUTED-AFTER-PRE-INNER-EDGE",
            "payload, directory identity and stack guard all completed; fault is inside helper",
            details)


def analyze() -> int:
    config = load(CONFIG)
    deployment = load(DEPLOYMENT)
    witness_path = RUN / "mechanism_witness.bin"
    state_path = RUN / "lisp65_runtime_state.bin"
    readback_path = RUN / "readback.d81"
    require(witness_path.is_file() and witness_path.stat().st_size == 10,
            "ten-byte mechanism witness absent")
    require(state_path.is_file() and state_path.stat().st_size == 1,
            "runtime-state capture absent")
    require(readback_path.is_file(), "D81 readback absent")
    require(sha(readback_path) == deployment["image"]["sha256"],
            "device-upload D81 readback drift")
    state = state_path.read_bytes()[0]
    require(state == config["terminal_value"], f"unexpected runtime state: {state}")
    values = list(witness_path.read_bytes())
    status, conclusion, details = classify(values, config)
    reference_image = ROOT / config["reference_image"]
    reference_elf = ROOT / config["reference_runtime_elf"]
    require(sha(reference_image) == config["reference_image_sha256"]
            and sha(reference_elf) == config["reference_runtime_elf_sha256"],
            "Link-90 candidate drift after contact")
    receipt = {
        "format": "lisp65-c2.3-v1.4-link90-mechanism-device-v1",
        "recorded_on": date.today().isoformat(), "status": status,
        "candidate_link": 90, "promotable": False,
        "device": {"hardware_contacts": 1, "runtime_state": state,
                   "witness_bytes": values, "conclusion": conclusion,
                   "decoded": details},
        "interpretation": {"raw_values_have_separate_tags": True,
                           "contact_5_span_authority": True,
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
    print(f"MECHANISM WITNESS {status} witness={values} state={state} "
          f"details={details}")
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
