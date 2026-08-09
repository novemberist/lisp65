#!/usr/bin/env python3
"""Build and decode the non-promotable Link-90 opcode-view witness."""

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


CONFIG = ROOT / "config/c2-v14-link90-opcode-view-witness.json"
OWNER = ROOT / "docs/planning/1.4-parity-pilot-work-plan.md"
VM = ROOT / "src/vm.c"
VMH = ROOT / "src/vm.h"
MAIN = ROOT / "products/runtime-core/main.c"
WRAPPER = ROOT / "scripts/c2-v14-link90-opcode-view-cc.sh"
HW = ROOT / "scripts/c2-v14-link90-opcode-view-witness-hw.sh"
BUILDER = ROOT / "tools/host-lisp/ship_builder.py"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PREPARATION = EVIDENCE / (
    "c2.3-v1.4-link90-opcode-view-witness-preparation-receipt.json")
RESULT = EVIDENCE / (
    "c2.3-v1.4-link90-opcode-view-witness-device-receipt.json")
BASE = ROOT / "build/post-promotion/v14/link90-opcode-view-witness"
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
    shape = next(row for row in manifest["entries"]
                 if row["name"] == "m65-sprite-shape")
    require(int(shape["ext_addr"], 16) ==
            (config["shape_bank"] << 16) + config["shape_offset"],
            "Link-90 shape object address drift")
    shape_ops = dict(shared.disassembly_block(
        ROOT / config["artifact_disassembly"], "m65-sprite-shape"))
    require(shape_ops.get(0x24) == "DROP"
            and shape_ops.get(0x25) == "PUSHLIT 1",
            "Link-90 first post-refill opcode seam drift")
    require("OP_DROP=59" in VMH.read_text(encoding="utf-8").replace(" ", "")
            and config["expected_opcode"] == 59,
            "OP_DROP numeric identity drift")
    require(config["expected_cursor"] == 0x24
            and config["expected_window"] == 0x24
            and config["expected_owner_bank"] == config["shape_bank"]
            and config["expected_owner_offset"] == config["shape_offset"],
            "configured post-refill view identity drift")
    return {
        "artifact_bound": True,
        "shape_bank": config["shape_bank"],
        "shape_offset": f"0x{config['shape_offset']:04x}",
        "expected_cursor": "0x0024",
        "expected_opcode": "0x3b",
        "expected_instruction": "DROP",
        "expected_owner": "5:0x06e1",
        "expected_window_base": "0x0024",
    }


def source_edges() -> dict[str, bool]:
    source = VM.read_text(encoding="utf-8")
    ensure_macro = source.index("#define WIN_ENSURE()")
    load = source.index("if (!vm_object_load(", ensure_macro)
    arm = source.index("LISP65_V14_OPCODE_VIEW_ARM(bank, off, pc_);", load)
    macro_end = source.index("#define JUMP_REL", arm)
    loop = source.index("    for (;;) {", macro_end)
    ensure_call = source.index("        WIN_ENSURE();", loop)
    capture = source.index("        LISP65_V14_OPCODE_VIEW_CAPTURE(", ensure_call)
    opcode_fetch = source.index("        op = RD8();", capture)
    dispatch = source.index("        switch (op) {", opcode_fetch)
    capture_macro = source.index("#define LISP65_V14_OPCODE_VIEW_CAPTURE")
    tag_predicate = source.index(
        "lisp65_v14_opcode_view_witness.refill_arm_tag == 0xa1u", capture_macro)
    cursor_filter = source.find("(cursor_) ==", capture_macro,
                                source.index("#else", capture_macro))
    cursor_store = source.index(
        "lisp65_v14_opcode_view_witness.cursor_low", capture_macro)
    opcode_store = source.index(
        "lisp65_v14_opcode_view_witness.opcode", cursor_store)
    owner_store = source.index(
        "lisp65_v14_opcode_view_witness.owner_bank", opcode_store)
    window_store = source.index(
        "lisp65_v14_opcode_view_witness.window_low", owner_store)
    tag_store = source.index(
        "lisp65_v14_opcode_view_witness.dispatch_view_tag = 0xb2u", window_store)
    return {
        "arm_after_successful_refill_load": load < arm < macro_end,
        "capture_after_win_ensure": ensure_call < capture,
        "capture_before_opcode_fetch": capture < opcode_fetch,
        "capture_before_dispatch": capture < dispatch,
        "capture_reads_unadvanced_ip": "vm_buf_bank, vm_buf_off, win);" in
            source[capture:opcode_fetch] and "*ip" in source[capture:opcode_fetch],
        "arm_is_only_capture_gate": tag_predicate < cursor_store
            and cursor_filter == -1,
        "view_tag_after_all_values": cursor_store < opcode_store < owner_store
            < window_store < tag_store,
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
        "layout": ["refill_arm_tag", "dispatch_view_tag", "cursor_low",
                   "cursor_high", "opcode", "owner_bank", "owner_off_low",
                   "owner_off_high", "window_low", "window_high"],
        "initial": [17, 18, 33, 49, 65, 81, 97, 113, 129, 145],
        "refill_arm_tag": 161, "dispatch_view_tag": 178,
        "raw_values_unconstrained": True,
        "separate_completion_tags": True,
        "view_tag_written_after_values": True,
        "capture_not_filtered_by_expected_cursor": True,
        "ordinary_ram_only": True,
    }, "opcode-view witness contract drift")
    edges = facts["edges"]
    require(edges["artifact_bound"] is True
            and edges["arm_after_successful_refill_load"] is True
            and edges["capture_after_win_ensure"] is True
            and edges["capture_before_opcode_fetch"] is True
            and edges["capture_before_dispatch"] is True
            and edges["capture_reads_unadvanced_ip"] is True
            and edges["arm_is_only_capture_gate"] is True
            and edges["view_tag_after_all_values"] is True,
            "opcode-view witness placement drift")


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
        "zero-arm-sentinel": (["witness", "initial", 0], 0),
        "zero-view-sentinel": (["witness", "initial", 1], 0),
        "zero-cursor-sentinel": (["witness", "initial", 2], 0),
        "zero-opcode-sentinel": (["witness", "initial", 4], 0),
        "zero-owner-sentinel": (["witness", "initial", 5], 0),
        "zero-window-sentinel": (["witness", "initial", 8], 0),
        "constrain-raw-values": (["witness", "raw_values_unconstrained"], False),
        "drop-tags": (["witness", "separate_completion_tags"], False),
        "tag-before-values": (["witness", "view_tag_written_after_values"], False),
        "filter-expected-cursor": (
            ["witness", "capture_not_filtered_by_expected_cursor"], False),
        "drop-artifact-bind": (["edges", "artifact_bound"], False),
        "arm-before-load": (["edges", "arm_after_successful_refill_load"], False),
        "capture-before-ensure": (["edges", "capture_after_win_ensure"], False),
        "capture-after-fetch": (["edges", "capture_before_opcode_fetch"], False),
        "capture-after-dispatch": (["edges", "capture_before_dispatch"], False),
        "read-advanced-ip": (["edges", "capture_reads_unadvanced_ip"], False),
        "add-cursor-gate": (["edges", "arm_is_only_capture_gate"], False),
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
            raise WitnessError(f"opcode-view mutation survived: {name}")
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
            "owner-authorized-non-promotable-opcode-view-witness",
            "owner authorization status drift")
    for token in (
        "witness contact 8", "opcode-view witness", "resume cursor/PC",
        "actual byte fetched", "window identity/base", "zero product bytes",
        "no Link 91", "one contact, postcondition read",
    ):
        require(token.lower() in owner.lower(),
                f"owner authorization text absent: {token}")
    for token in (
        "LISP65_V14_OPCODE_VIEW_WITNESS", "refill_arm_tag",
        "dispatch_view_tag", "cursor_low", "opcode", "owner_bank",
        "owner_off_low", "window_low", "LISP65_V14_OPCODE_VIEW_ARM(",
        "LISP65_V14_OPCODE_VIEW_CAPTURE(",
    ):
        require(token in vm_source, f"opcode-view VM seam drift: {token}")
    require("lisp65_v14_opcode_view_witness_reset();" in main_source,
            "opcode-view reset is not bound to Runtime entry")
    for token in ("LISP65_V14_OPCODE_VIEW_WITNESS",
                  "LISP65_V14_OPCODE_SHAPE_OFF=0x06e1"):
        require(token in wrapper_source, f"diagnostic wrapper drift: {token}")

    prior = load(ROOT / config["prior_witness_receipt"])
    require(prior["status"] == "ATTRIBUTED-DROP-NOT-COMPLETED"
            and prior["device"]["witness_bytes"] == [17, 18, 33, 49, 19, 20],
            "contact-7 boundary authority drift")
    edges = {**artifact_edges(config), **source_edges()}

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
            "inactive opcode-view seams changed the ordinary Runtime ELF")
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
            "opcode-view witness escaped into the ordinary Runtime")
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
            "layout": ["refill_arm_tag", "dispatch_view_tag", "cursor_low",
                       "cursor_high", "opcode", "owner_bank", "owner_off_low",
                       "owner_off_high", "window_low", "window_high"],
            "initial": config["initial_bytes"],
            "refill_arm_tag": config["refill_arm_tag"],
            "dispatch_view_tag": config["dispatch_view_tag"],
            "raw_values_unconstrained": True,
            "separate_completion_tags": True,
            "view_tag_written_after_values": True,
            "capture_not_filtered_by_expected_cursor": True,
            "ordinary_ram_only": True,
        },
        "edges": edges,
    }
    audit(facts)
    rejected = mutation_check(facts)
    deployment = {
        "format": "lisp65-c2.3-v1.4-link90-opcode-view-deployment-v1",
        "status": "prepared", "source_commit": head, "candidate_link": 90,
        "image": bind(diagnostic), "runtime_elf": bind(diagnostic_elf),
        "remote": config["remote"], "terminal_value": config["terminal_value"],
        "runtime_state": state, "witness": witness,
    }
    write_json(DEPLOYMENT, deployment)
    receipt = {
        "format": "lisp65-c2.3-v1.4-link90-opcode-view-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "PREPARED-NON-PROMOTABLE-OPCODE-VIEW-WITNESS",
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
            "vm_header": bind(VMH), "runtime_main": bind(MAIN),
            "compiler_wrapper": bind(WRAPPER), "hardware_script": bind(HW),
            "ship_builder": bind(BUILDER), "driver": bind(DRIVER),
            "artifact_manifest": bind(ROOT / config["artifact_manifest"]),
            "artifact_disassembly": bind(ROOT / config["artifact_disassembly"]),
            "contact_7": bind(ROOT / config["prior_witness_receipt"]),
            "deployment": bind(DEPLOYMENT),
        },
    }
    write_json(PREPARATION, receipt)
    print(f"OPCODE VIEW PREPARED host=2 mutations={len(rejected)} "
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
            "PREPARED-NON-PROMOTABLE-OPCODE-VIEW-WITNESS",
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
            "opcode-view hardware contact already consumed")
    print("OPCODE VIEW DRY RUN PASS contact=1 bytes=10 post-stop-reads=2")
    return 0


def classify(values: list[int], config: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    initial = config["initial_bytes"]
    arm, view, clo, chi, opcode, owner_bank, olo, ohi, wlo, whi = values
    cursor = clo | (chi << 8)
    owner_off = olo | (ohi << 8)
    window = wlo | (whi << 8)
    details = {"cursor": f"0x{cursor:04x}", "opcode": f"0x{opcode:02x}",
               "owner_bank": owner_bank, "owner_offset": f"0x{owner_off:04x}",
               "window_base": f"0x{window:04x}"}
    if arm == initial[0]:
        require(values == initial, f"non-atomic refill-arm witness: {values}")
        return ("ATTRIBUTED-BEFORE-REFILL-COMPLETION",
                "the target refill did not reach the opcode-view arm", {})
    require(arm == config["refill_arm_tag"], f"unknown refill arm tag: {arm}")
    if view == initial[1]:
        require(values[2:] == initial[2:], f"non-atomic dispatch view: {values}")
        return ("ATTRIBUTED-REFILL-EXIT-BEFORE-DISPATCH-VIEW",
                "refill completed; the pre-fetch dispatcher view was not captured", {})
    require(view == config["dispatch_view_tag"], f"unknown dispatch tag: {view}")
    if cursor != config["expected_cursor"]:
        return ("ATTRIBUTED-WRONG-CURSOR-RESTORE",
                f"dispatcher cursor is 0x{cursor:04x}, expected 0x0024", details)
    identity = (owner_bank, owner_off, window)
    expected_identity = (config["expected_owner_bank"],
                         config["expected_owner_offset"], config["expected_window"])
    if identity != expected_identity:
        return ("ATTRIBUTED-WRONG-WINDOW-IDENTITY",
                f"cursor is correct but owner/window is {owner_bank}:0x{owner_off:04x} "
                f"at 0x{window:04x}, expected 5:0x06e1 at 0x0024", details)
    if opcode != config["expected_opcode"]:
        return ("ATTRIBUTED-WRONG-POST-REFILL-OPCODE",
                f"cursor and window identity are correct but fetched opcode is "
                f"0x{opcode:02x}, expected DROP 0x3b", details)
    return ("ATTRIBUTED-DISPATCH-DOWNSTREAM-OF-CORRECT-VIEW",
            "cursor, owner, window base and DROP byte are all correct before dispatch",
            details)


def analyze() -> int:
    config = load(CONFIG)
    deployment = load(DEPLOYMENT)
    witness_path = RUN / "opcode_view_witness.bin"
    state_path = RUN / "lisp65_runtime_state.bin"
    readback_path = RUN / "readback.d81"
    require(witness_path.is_file() and witness_path.stat().st_size == 10,
            "ten-byte opcode-view witness absent")
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
        "format": "lisp65-c2.3-v1.4-link90-opcode-view-device-v1",
        "recorded_on": date.today().isoformat(), "status": status,
        "candidate_link": 90, "promotable": False,
        "device": {"hardware_contacts": 1, "runtime_state": state,
                   "witness_bytes": values, "conclusion": conclusion,
                   "decoded": details},
        "interpretation": {"refill_arm_is_separate": True,
                           "view_values_have_completion_tag": True,
                           "capture_has_no_expected_cursor_filter": True,
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
    print(f"OPCODE VIEW {status} witness={values} state={state} details={details}")
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
