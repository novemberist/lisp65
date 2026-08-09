#!/usr/bin/env python3
"""Build and decode the non-promotable Link-90 per-instruction witness."""

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


CONFIG = ROOT / "config/c2-v14-link90-instruction-witness.json"
OWNER = ROOT / "docs/planning/1.4-parity-pilot-work-plan.md"
VM = ROOT / "src/vm.c"
MAIN = ROOT / "products/runtime-core/main.c"
WRAPPER = ROOT / "scripts/c2-v14-link90-instruction-cc.sh"
HW = ROOT / "scripts/c2-v14-link90-instruction-witness-hw.sh"
BUILDER = ROOT / "tools/host-lisp/ship_builder.py"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PREPARATION = EVIDENCE / (
    "c2.3-v1.4-link90-instruction-witness-preparation-receipt.json")
RESULT = EVIDENCE / (
    "c2.3-v1.4-link90-instruction-witness-device-receipt.json")
BASE = ROOT / "build/post-promotion/v14/link90-instruction-witness"
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
    require(shape["lit_count"] == 7
            and shape["literals"][config["expected_literal_index"]] == 208,
            "Link-90 literal-1 manifest identity drift")
    shape_ops = dict(shared.disassembly_block(
        ROOT / config["artifact_disassembly"], "m65-sprite-shape"))
    expected_span = {
        0x24: "DROP", 0x25: "PUSHLIT 1", 0x27: "PUSHI8 47",
        0x29: "PUSHI8 83", 0x2B: "CALL lit=2 argc=3",
    }
    require(all(shape_ops.get(offset) == instruction
                for offset, instruction in expected_span.items()),
            "Link-90 four-instruction span drift")
    expected_literal = (208 << 1) | 1
    require(expected_literal == config["expected_literal_value"],
            "configured literal-1 object word drift")
    return {
        "artifact_bound": True,
        "shape_bank": config["shape_bank"],
        "shape_offset": f"0x{config['shape_offset']:04x}",
        "span": "0x0024..0x002a",
        "instructions": [expected_span[key] for key in sorted(expected_span)[:-1]],
        "bracketing_call": expected_span[0x2B],
        "literal_index": config["expected_literal_index"],
        "literal_source_value": 208,
        "literal_object_word": f"0x{expected_literal:04x}",
        "literal_object_kind": "fixnum",
    }


def source_edges() -> dict[str, bool]:
    source = VM.read_text(encoding="utf-8")
    drop_case = source.index("        case OP_DROP:")
    drop_pop = source.index("            (void)POP();", drop_case)
    drop_stamp = source.index("            LISP65_V14_INSTR_AFTER_DROP(", drop_pop)
    drop_break = source.index("            break;", drop_stamp)
    lit_case = source.index("        case OP_PUSHLIT:")
    lit_push = source.index("            PUSH(LIT(i));", lit_case)
    lit_stamp = source.index("            LISP65_V14_INSTR_AFTER_PUSHLIT(", lit_push)
    lit_break = source.index("            break;", lit_stamp)
    pushi_case = source.index("        case OP_PUSHI8:")
    pushi_push = source.index("            PUSH(MKFIX((int8_t)RD8()));", pushi_case)
    pushi_stamp = source.index("            LISP65_V14_INSTR_AFTER_PUSHI8(", pushi_push)
    pushi_break = source.index("            break;", pushi_stamp)
    macro = source.index("#define LISP65_V14_INSTR_AFTER_PUSHLIT")
    low_store = source.index(
        "lisp65_v14_instruction_witness.pushlit_value_low", macro)
    high_store = source.index(
        "lisp65_v14_instruction_witness.pushlit_value_high", low_store)
    tag_store = source.index(
        "lisp65_v14_instruction_witness.post_pushlit_tag = 0xb2u", high_store)
    return {
        "drop_after_pop_before_break": drop_pop < drop_stamp < drop_break,
        "pushlit_after_push_before_break": lit_push < lit_stamp < lit_break,
        "pushi_after_push_before_break": pushi_push < pushi_stamp < pushi_break,
        "pushlit_tag_after_value": low_store < high_store < tag_store,
        "sequence_state_coupled": (
            "lisp65_v14_instruction_witness.after_drop_stage == 0xa1u" in source
            and "lisp65_v14_instruction_witness.post_pushlit_tag == 0xb2u" in source
            and "lisp65_v14_instruction_witness.after_pushi47_stage" in source),
        "pushlit_sets_no_vm_typeerror": (
            "case OP_PUSHLIT: {" in source
            and "PUSH(LIT(i));" in source
            and "VM_TYPEERROR" not in source[lit_case:lit_break]),
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
        "layout": ["after_drop_stage", "post_pushlit_tag",
                   "pushlit_value_low", "pushlit_value_high",
                   "after_pushi47_stage", "after_pushi83_stage"],
        "initial": [17, 18, 33, 49, 19, 20],
        "complete_stages": [161, 178, 195, 212],
        "raw_value_unconstrained": True,
        "separate_value_tag": True,
        "tag_written_after_value": True,
        "state_coupled_order": True,
        "ordinary_ram_only": True,
    }, "instruction-witness contract drift")
    edges = facts["edges"]
    require(edges["artifact_bound"] is True
            and edges["drop_after_pop_before_break"] is True
            and edges["pushlit_after_push_before_break"] is True
            and edges["pushi_after_push_before_break"] is True
            and edges["pushlit_tag_after_value"] is True
            and edges["sequence_state_coupled"] is True
            and edges["pushlit_sets_no_vm_typeerror"] is True,
            "instruction-witness placement drift")


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
        "zero-drop-sentinel": (["witness", "initial", 0], 0),
        "zero-pushlit-sentinel": (["witness", "initial", 1], 0),
        "zero-pushi47-sentinel": (["witness", "initial", 4], 0),
        "zero-pushi83-sentinel": (["witness", "initial", 5], 0),
        "constrain-raw-value": (["witness", "raw_value_unconstrained"], False),
        "drop-value-tag": (["witness", "separate_value_tag"], False),
        "tag-before-value": (["witness", "tag_written_after_value"], False),
        "uncouple-order": (["witness", "state_coupled_order"], False),
        "drop-artifact-bind": (["edges", "artifact_bound"], False),
        "drop-before-pop": (["edges", "drop_after_pop_before_break"], False),
        "pushlit-before-push": (["edges", "pushlit_after_push_before_break"], False),
        "pushi-before-push": (["edges", "pushi_after_push_before_break"], False),
        "claim-pushlit-typeerror": (["edges", "pushlit_sets_no_vm_typeerror"], False),
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
            raise WitnessError(f"instruction-witness mutation survived: {name}")
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
            "owner-authorized-non-promotable-instruction-witness",
            "owner authorization status drift")
    for token in (
        "witness contact 7", "per-instruction resolution",
        "sentinel stamps interleaved between the four instructions",
        "top-of-stack value", "zero product bytes", "no Link 91",
        "one contact, postcondition read",
    ):
        require(token.lower() in owner.lower(),
                f"owner authorization text absent: {token}")
    for token in (
        "LISP65_V14_INSTRUCTION_WITNESS", "after_drop_stage",
        "post_pushlit_tag", "pushlit_value_low", "after_pushi47_stage",
        "after_pushi83_stage", "LISP65_V14_INSTR_AFTER_DROP(",
        "LISP65_V14_INSTR_AFTER_PUSHLIT(", "LISP65_V14_INSTR_AFTER_PUSHI8(",
    ):
        require(token in vm_source, f"instruction VM seam drift: {token}")
    require("lisp65_v14_instruction_witness_reset();" in main_source,
            "instruction-witness reset is not bound to Runtime entry")
    for token in ("LISP65_V14_INSTRUCTION_WITNESS",
                  "LISP65_V14_INSTR_SHAPE_OFF=0x06e1"):
        require(token in wrapper_source, f"diagnostic wrapper drift: {token}")

    prior = load(ROOT / config["prior_witness_receipt"])
    require(prior["status"] == "ATTRIBUTED-PAYLOAD-DISPATCH-NOT-COMPLETED"
            and prior["device"]["witness_bytes"]
            == [17, 33, 49, 65, 18, 34, 50, 66, 82, 19],
            "contact-6 boundary authority drift")
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
            "inactive instruction seams changed the ordinary Runtime ELF")
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
    witness = shared.symbol_row(truth, config["witness_symbol"], 6)
    state = shared.symbol_row(truth, config["runtime_state_symbol"], 1)
    require(config["witness_symbol"] not in
            {row.name for row in control_truth.symbols},
            "instruction witness escaped into the ordinary Runtime")
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
            "layout": ["after_drop_stage", "post_pushlit_tag",
                       "pushlit_value_low", "pushlit_value_high",
                       "after_pushi47_stage", "after_pushi83_stage"],
            "initial": config["initial_bytes"],
            "complete_stages": [config["after_drop_stage"],
                                config["post_pushlit_tag"],
                                config["after_pushi47_stage"],
                                config["after_pushi83_stage"]],
            "raw_value_unconstrained": True, "separate_value_tag": True,
            "tag_written_after_value": True, "state_coupled_order": True,
            "ordinary_ram_only": True,
        },
        "edges": edges,
    }
    audit(facts)
    rejected = mutation_check(facts)
    deployment = {
        "format": "lisp65-c2.3-v1.4-link90-instruction-deployment-v1",
        "status": "prepared", "source_commit": head, "candidate_link": 90,
        "image": bind(diagnostic), "runtime_elf": bind(diagnostic_elf),
        "remote": config["remote"], "terminal_value": config["terminal_value"],
        "runtime_state": state, "witness": witness,
    }
    write_json(DEPLOYMENT, deployment)
    receipt = {
        "format": "lisp65-c2.3-v1.4-link90-instruction-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "PREPARED-NON-PROMOTABLE-INSTRUCTION-WITNESS",
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
            "contact_6": bind(ROOT / config["prior_witness_receipt"]),
            "deployment": bind(DEPLOYMENT),
        },
    }
    write_json(PREPARATION, receipt)
    print(f"INSTRUCTION WITNESS PREPARED host=2 mutations={len(rejected)} "
          f"witness={witness['address']}+6")
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
            "PREPARED-NON-PROMOTABLE-INSTRUCTION-WITNESS",
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
            "instruction-witness hardware contact already consumed")
    print("INSTRUCTION WITNESS DRY RUN PASS contact=1 bytes=6 post-stop-reads=2")
    return 0


def object_kind(raw: int) -> str:
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
    drop, lit_tag, low, high, push47, push83 = values
    raw = low | (high << 8)
    if drop == initial[0]:
        require(values == initial, f"non-atomic DROP witness: {values}")
        return ("ATTRIBUTED-DROP-NOT-COMPLETED",
                "the refilled DROP did not complete", {"pushlit_value": None})
    require(drop == config["after_drop_stage"], f"unknown DROP stage: {drop}")
    if lit_tag == initial[1]:
        require(values[2:] == initial[2:], f"non-atomic PUSHLIT witness: {values}")
        return ("ATTRIBUTED-PUSHLIT1-NOT-COMPLETED",
                "DROP completed; PUSHLIT 1 did not complete its tagged push",
                {"pushlit_value": None})
    require(lit_tag == config["post_pushlit_tag"],
            f"unknown PUSHLIT tag: {lit_tag}")
    details = {"pushlit_value_raw": f"0x{raw:04x}",
               "pushlit_value_kind": object_kind(raw),
               "expected_raw": f"0x{config['expected_literal_value']:04x}",
               "expected_kind": "fixnum"}
    if raw != config["expected_literal_value"]:
        require(push47 == initial[4] and push83 == initial[5],
                "wrong literal value cannot precede completed later stages")
        return ("ATTRIBUTED-POST-REFILL-LITERAL1-MISMATCH",
                f"PUSHLIT 1 pushed 0x{raw:04x} ({object_kind(raw)}), expected "
                f"0x{config['expected_literal_value']:04x} (fixnum)", details)
    if push47 == initial[4]:
        require(push83 == initial[5], "PUSHI8 83 cannot precede PUSHI8 47")
        return ("ATTRIBUTED-PUSHI8-47-NOT-COMPLETED",
                "DROP and PUSHLIT 1 completed correctly; PUSHI8 47 did not",
                details)
    require(push47 == config["after_pushi47_stage"],
            f"unknown PUSHI8-47 stage: {push47}")
    if push83 == initial[5]:
        return ("ATTRIBUTED-PUSHI8-83-NOT-COMPLETED",
                "DROP, PUSHLIT 1 and PUSHI8 47 completed; PUSHI8 83 did not",
                details)
    require(push83 == config["after_pushi83_stage"],
            f"unknown PUSHI8-83 stage: {push83}")
    return ("ATTRIBUTED-AFTER-FOUR-INSTRUCTION-PREFIX",
            "all four prefix instructions completed; contact 6's boundary did not repeat",
            details)


def analyze() -> int:
    config = load(CONFIG)
    deployment = load(DEPLOYMENT)
    witness_path = RUN / "instruction_witness.bin"
    state_path = RUN / "lisp65_runtime_state.bin"
    readback_path = RUN / "readback.d81"
    require(witness_path.is_file() and witness_path.stat().st_size == 6,
            "six-byte instruction witness absent")
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
        "format": "lisp65-c2.3-v1.4-link90-instruction-device-v1",
        "recorded_on": date.today().isoformat(), "status": status,
        "candidate_link": 90, "promotable": False,
        "device": {"hardware_contacts": 1, "runtime_state": state,
                   "witness_bytes": values, "conclusion": conclusion,
                   "decoded": details},
        "interpretation": {"per_instruction_completion_tags": True,
                           "literal_value_has_separate_tag": True,
                           "contact_5_and_6_boundary_authority": True,
                           "pushlit_itself_has_no_typeerror_edge": True,
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
    print(f"INSTRUCTION WITNESS {status} witness={values} state={state} "
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
