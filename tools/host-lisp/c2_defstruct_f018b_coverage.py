#!/usr/bin/env python3
"""Close the commissioned F018B coverage question for the defstruct escape.

The stopped hardware stack is joined to the linked call/prologue bytes.  The
byte immediately above the surviving $E329 JSR word is no longer treated as
an anonymous temporary: it is the bank argument held by ``vm_code_load``
between its PHA and PLA.  Consequently the in-flight C2D read had not reached
the DMA facade, descriptor construction, $D700 submission or return.

This is a desk-only replay.  It neither opens a device nor promotes the
remaining one-byte refill views into a full-window oracle.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RESCUE = EVIDENCE / "c2.3-post-v1.4-defstruct-brk-stack-rescue-receipt.json"
DEVICE = EVIDENCE / "c2.3-post-v1.4-defstruct-terminal-ingress-device-receipt.json"
RESULT = EVIDENCE / "c2.3-post-v1.4-defstruct-terminal-ingress-result-receipt.json"
ELF = ROOT / (
    "build/c2.3/defstruct-terminal-ingress-sister-link92/artifacts/"
    "diagnostic-terminal-ingress.elf")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
PLAN = "docs/planning/post-v1.4.0-direction-plan.md"
AUTHORIZATION_COMMIT = "17e68e8e"
RECEIPT = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-f018b-coverage-receipt.json")

FORMAT = "lisp65-c2.3-post-v1.4-defstruct-f018b-coverage-v1"
RECORDED_ON = "2026-08-10"


class CoverageError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CoverageError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def git_bind(commit: str, path: str) -> dict[str, Any]:
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{path}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": path,
            "bytes": len(raw), "sha256": digest(raw)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(canonical(value))
    temporary.replace(path)


def symbol_bytes(truth: ElfTruth, name: str, *, size: int = 0) -> bytes:
    symbol = truth.symbol(name)
    count = symbol.bytes or size
    require(count > 0, f"sized symbol required: {name}")
    section = truth.section(symbol.section)
    raw = truth.section_bytes(symbol.section)
    at = symbol.value - section.address
    require(0 <= at and at + count <= len(raw), f"symbol outside section: {name}")
    return raw[at:at + count]


def linked_path() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    stream = symbol_bytes(truth, "c2_stream_c2d_read")
    facade = symbol_bytes(truth, "c2_facade_vm_code_load", size=3)
    load_body = symbol_bytes(truth, "vm_code_load")
    dma_facade = symbol_bytes(truth, "c2_facade_c2_dma", size=3)
    dma_body = symbol_bytes(truth, "c2_facade_target_c2_dma")

    stream_tail = bytes.fromhex(
        "a905a6048608a6058609a60a8604a6068605a6078606a60b20c4b5a2018a60")
    require(stream.count(stream_tail) == 1, "C2D call adapter drift")
    require(facade == bytes.fromhex("4cb7a1"), "vm-code-load facade drift")
    expected_load = bytes.fromhex(
        "da7aa60448a505850aa506850b6407a5088505a5098506688504a50a8508"
        "a50b8509984cc7b5")
    require(load_body == expected_load, "vm_code_load ABI adapter drift")
    require(dma_facade == bytes.fromhex("4c90ff"), "DMA facade drift")
    submit = bytes.fromhex("a9008d02d7a9b98d01d7a9d18d00d7")
    submit_at = dma_body.find(submit)
    require(submit_at >= 0 and dma_body.count(bytes.fromhex("8d00d7")) == 1,
            "unique $D700 submit drift")
    symbols = {
        name: truth.symbol(name).value
        for name in ("c2_stream_c2d_read", "c2_facade_vm_code_load",
                     "vm_code_load", "c2_facade_c2_dma",
                     "c2_facade_target_c2_dma")
    }
    require(symbols == {
        "c2_stream_c2d_read": 0xE2DD,
        "c2_facade_vm_code_load": 0xB5C4,
        "vm_code_load": 0xA1B7,
        "c2_facade_c2_dma": 0xB5C7,
        "c2_facade_target_c2_dma": 0xFF90,
    }, "linked path address drift")
    return {
        "symbols": {name: f"0x{address:04X}" for name, address in symbols.items()},
        "c2d_adapter_tail_hex": stream_tail.hex(),
        "vm_code_load_hex": load_body.hex(),
        "stack_sequence": [
            {"PC": "0xE30F", "instruction": "LDA #$05",
             "effect": "C2D source-bank argument A=$05"},
            {"PC": "0xE327", "instruction": "JSR $B5C4",
             "effect": "push return word $E329"},
            {"PC": "0xB5C4", "instruction": "JMP $A1B7",
             "effect": "facade changes neither A nor SP"},
            {"PC": "0xA1B7..0xA1B8", "instruction": "PHX; PLY",
             "effect": "balanced temporary; A remains $05"},
            {"PC": "0xA1BB", "instruction": "PHA",
             "effect": "push bank argument $05"},
            {"PC": "0xA1CE", "instruction": "PLA",
             "effect": "first instruction that removes saved $05"},
            {"PC": "0xA1DA", "instruction": "JMP $B5C7",
             "effect": "DMA facade is reachable only after PLA"},
            {"PC": f"0x{symbols['c2_facade_target_c2_dma'] + submit_at + 12:04X}",
             "instruction": "STA $D700",
             "effect": "first and only F018B submit"},
        ],
        "PHA_PC": "0xA1BB", "PLA_PC": "0xA1CE",
        "DMA_facade_jump_PC": "0xA1DA", "D700_submit_PC": "0xFFD0",
        "submit_is_downstream_of_PLA": True,
    }


def derive() -> dict[str, Any]:
    rescue = load(RESCUE)
    device = load(DEVICE)
    result = load(RESULT)
    raw = bytes.fromhex(rescue["device_protocol"]["raw_hex"])
    require(len(raw) == 512 and rescue["hardware_stack"]["pre_BRK_SP"] == "0x94",
            "rescued stack geometry drift")
    require(raw[0x195] == 0x05 and raw[0x196:0x198] == bytes.fromhex("29e3"),
            "active stack prefix drift")
    require(rescue["hardware_stack"]["nearest_linked_return_word"]["word"]
            == "0xE329", "surviving call word drift")

    path = linked_path()
    fills = result["R"]["retained_completed_views"]
    require(len(fills) == 2, "retained refill cardinality drift")
    prior, last = fills
    require((prior["owner_ordinal"], prior["cursor"], prior["fetched"],
             last["owner_ordinal"], last["cursor"], last["fetched"])
            == (656, 29, 0x3E, 696, 10, 0x0C),
            "retained refill identity drift")
    require(result["progress"]["owner_ordinal"] == 696,
            "terminal logical owner drift")
    require(result["R"]["claim_scope"]
            == "only the two retained completed refill views",
            "historical R scope drift")
    decoded = device["record"]["decoded"]
    require(decoded["last-fill.owner"]["value_hex"] == "01b802"
            and decoded["last-fill.fetched-opcode"]["value_le"] == 0x0C,
            "device last-fill row drift")

    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": (
            "ACTIVE-LOAD-PRE-SUBMIT; F018B-ACTIVE-LOAD-MEMBERSHIP-REFUTED; "
            "FULL-CONSUMED-SPAN-ROW-SPECIFIED"),
        "authorities": {
            "owner_commission": git_bind(AUTHORIZATION_COMMIT, PLAN),
            "stack_rescue": bind(RESCUE),
            "terminal_device": bind(DEVICE),
            "terminal_result": bind(RESULT),
            "diagnostic_ELF": bind(ELF),
        },
        "active_load": {
            "transport": "C2D bank-5 read through vm_code_load/F018B",
            "logical_VM_owner_ordinal": 696,
            "logical_owner_authority": (
                "target-owned progress producer at the last completed dispatch"),
            "window_class": (
                "no new VM code window materialized; in-flight internal C2D read"),
            "exact_C2D_offset_destination_length_recoverable": False,
            "exact_parameter_claim_required_for_submit_decision": False,
            "stack": {
                "pre_BRK_SP": "0x94",
                "saved_bank_address": "0x0195", "saved_bank_value": "0x05",
                "JSR_return_address": "0x0196", "JSR_return_word": "0xE329",
                "interpretation": (
                    "$05 is the A=$05 C2D bank argument held by vm_code_load PHA; "
                    "$E329 is the immediately underlying active JSR word"),
            },
            "linked_path": path,
            "bounded_execution_interval": "after PHA $A1BB and before PLA $A1CE",
            "D700_submit_reached": False,
            "submit_return_reached": False,
            "content_completion_signal_possible": False,
        },
        "coverage": {
            "retained_completed_views": [
                {"owner_ordinal": row["owner_ordinal"], "cursor": row["cursor"],
                 "fetched": row["fetched"], "expected": row["expected"],
                 "source_object_sha256": row["object_sha256"]}
                for row in fills
            ],
            "active_load_is_one_of_retained_completed_views": False,
            "active_load_is_later_unstored_activation": True,
            "active_load_is_unstored_completed_refill": False,
            "reason": (
                "the current activation is absent from the post-success ring because "
                "it escaped before DMA submission, not because a completed load went "
                "unobserved"),
        },
        "delivered_old_content_check": {
            "candidate": "whole prior buffer survives the last completed owner-696 fill",
            "prior_first_byte": "0x3E",
            "new_source_first_byte": "0x0C",
            "target_post_fill_first_byte": "0x0C",
            "candidate_rejected": True,
            "partial_tail_visibility_excluded": False,
            "claim": (
                "the delivered immediate-prior whole-window candidate is inconsistent "
                "at byte zero; the one-byte oracle does not prove the rest of the "
                "consumed span"),
        },
        "host_narrative": {
            "active_load_post_return_stale_execution_modeled": False,
            "reason": (
                "there is no active-load submit or return from which post-return stale "
                "execution could begin; inventing window bytes would violate the "
                "commission"),
            "causal_chain": [
                {"stage": "active C2D load submitted", "holds": False},
                {"stage": "submission consumed as content completion", "holds": False},
                {"stage": "stale active-load bytes executed", "holds": False},
                {"stage": "stale active-load route reaches $BF71", "holds": False},
            ],
        },
        "specified_final_evidence_row": {
            "authorized_by_this_result": False,
            "purpose": (
                "close only the residual partial-tail question for the completed fill "
                "immediately preceding the escape"),
            "writer": "target-owned post-refill/pre-dispatch code",
            "observation_timing": "before the first opcode of the refilled span executes",
            "oracle": "exhaustive source-vs-window comparison over the consumed span",
            "commit_rule": "tag last; completion metadata is never oracle",
            "fields": [
                "commit-tag", "owner-ordinal", "window-base", "consumed-byte-count",
                "first-difference-index-or-FFFF", "source-byte", "window-byte",
            ],
            "decision": {
                "difference": "F018B membership proven for that completed fill",
                "FFFF_full_match_then_same_pre-submit_escape": (
                    "F018B membership refuted for the retained-to-active chain; "
                    "continue at the local pre-submit control/interrupt edge"),
            },
        },
        "decision": {
            "F018B_membership_for_active_load": "REFUTED",
            "F018B_membership_for_any_earlier_partial_tail": "UNPROVEN",
            "ownership_recharter_new_decision_basis_established": False,
            "local_mechanism_boundary": (
                "control escaped while vm_code_load held its bank argument on the "
                "hardware stack, before PLA and before F018B submission"),
            "fix_authorized": False,
            "device_contact_authorized": False,
            "product_bytes_changed": 0,
        },
        "claim_limit": (
            "This desk result refutes F018B completion/visibility as the mechanism of "
            "the active load on the surviving stack. It does not turn the two one-byte "
            "views into full-window evidence, does not exclude an earlier partial-tail "
            "visibility defect, does not identify the destroyed immediate RTS/RTI edge, "
            "and authorizes no fix, link or device contact."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT and value["status"].startswith(
        "ACTIVE-LOAD-PRE-SUBMIT"), "coverage identity drift")
    active = value["active_load"]
    require(active["logical_VM_owner_ordinal"] == 696
            and active["stack"]["saved_bank_address"] == "0x0195"
            and active["stack"]["saved_bank_value"] == "0x05"
            and active["stack"]["JSR_return_word"] == "0xE329"
            and active["bounded_execution_interval"]
            == "after PHA $A1BB and before PLA $A1CE"
            and active["D700_submit_reached"] is False
            and active["submit_return_reached"] is False
            and active["content_completion_signal_possible"] is False,
            "active pre-submit boundary drift")
    path = active["linked_path"]
    require(path["PHA_PC"] == "0xA1BB" and path["PLA_PC"] == "0xA1CE"
            and path["DMA_facade_jump_PC"] == "0xA1DA"
            and path["D700_submit_PC"] == "0xFFD0"
            and path["submit_is_downstream_of_PLA"] is True,
            "linked submit ordering drift")
    coverage = value["coverage"]
    require([(row["owner_ordinal"], row["cursor"], row["fetched"])
             for row in coverage["retained_completed_views"]]
            == [(656, 29, 0x3E), (696, 10, 0x0C)]
            and coverage["active_load_is_one_of_retained_completed_views"] is False
            and coverage["active_load_is_later_unstored_activation"] is True
            and coverage["active_load_is_unstored_completed_refill"] is False,
            "coverage classification drift")
    old = value["delivered_old_content_check"]
    require(old["prior_first_byte"] == "0x3E"
            and old["new_source_first_byte"] == "0x0C"
            and old["target_post_fill_first_byte"] == "0x0C"
            and old["candidate_rejected"] is True
            and old["partial_tail_visibility_excluded"] is False,
            "delivered old-content boundary drift")
    narrative = value["host_narrative"]
    require(narrative["active_load_post_return_stale_execution_modeled"] is False
            and [row["holds"] for row in narrative["causal_chain"]]
            == [False, False, False, False], "impossible stale narrative promoted")
    final = value["specified_final_evidence_row"]
    require(final["authorized_by_this_result"] is False
            and final["writer"] == "target-owned post-refill/pre-dispatch code"
            and "completion metadata is never oracle" in final["commit_rule"]
            and "first-difference-index-or-FFFF" in final["fields"],
            "final evidence row drift")
    decision = value["decision"]
    require(decision["F018B_membership_for_active_load"] == "REFUTED"
            and decision["F018B_membership_for_any_earlier_partial_tail"] == "UNPROVEN"
            and decision["ownership_recharter_new_decision_basis_established"] is False
            and decision["fix_authorized"] is False
            and decision["device_contact_authorized"] is False
            and decision["product_bytes_changed"] == 0,
            "coverage decision overclaim")


def audit(value: dict[str, Any]) -> None:
    validate(value)
    require(value == derive(), "coverage receipt differs from reconstruction")


def mutate(value: dict[str, Any], path: list[Any], replacement: Any) -> None:
    cursor: Any = value
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = replacement


def selftest() -> dict[str, Any]:
    base = derive()
    cases: list[tuple[str, list[Any], Any]] = [
        ("move-bank-byte", ["active_load", "stack", "saved_bank_address"], "0x0194"),
        ("change-bank", ["active_load", "stack", "saved_bank_value"], "0x04"),
        ("change-return", ["active_load", "stack", "JSR_return_word"], "0xE32A"),
        ("move-PHA", ["active_load", "linked_path", "PHA_PC"], "0xA1BA"),
        ("move-PLA", ["active_load", "linked_path", "PLA_PC"], "0xA1CF"),
        ("move-submit", ["active_load", "linked_path", "D700_submit_PC"], "0xFFCE"),
        ("invert-order", ["active_load", "linked_path",
                          "submit_is_downstream_of_PLA"], False),
        ("claim-submit", ["active_load", "D700_submit_reached"], True),
        ("claim-return", ["active_load", "submit_return_reached"], True),
        ("claim-completion", ["active_load", "content_completion_signal_possible"], True),
        ("change-owner", ["active_load", "logical_VM_owner_ordinal"], 656),
        ("cover-active", ["coverage", "active_load_is_one_of_retained_completed_views"], True),
        ("complete-active", ["coverage", "active_load_is_unstored_completed_refill"], True),
        ("move-prior-view", ["coverage", "retained_completed_views", 0,
                             "owner_ordinal"], 655),
        ("move-last-view", ["coverage", "retained_completed_views", 1,
                            "cursor"], 11),
        ("claim-whole-old", ["delivered_old_content_check", "candidate_rejected"], False),
        ("claim-tail", ["delivered_old_content_check",
                        "partial_tail_visibility_excluded"], True),
        ("invent-narrative", ["host_narrative",
                              "active_load_post_return_stale_execution_modeled"], True),
        ("invent-chain", ["host_narrative", "causal_chain", 0, "holds"], True),
        ("authorize-row", ["specified_final_evidence_row",
                           "authorized_by_this_result"], True),
        ("metadata-oracle", ["specified_final_evidence_row", "commit_rule"],
         "completion metadata is oracle"),
        ("claim-broad-refutation", ["decision",
                                    "F018B_membership_for_any_earlier_partial_tail"],
         "REFUTED"),
        ("reopen-ownership", ["decision",
                              "ownership_recharter_new_decision_basis_established"], True),
        ("authorize-fix", ["decision", "fix_authorized"], True),
        ("authorize-contact", ["decision", "device_contact_authorized"], True),
    ]
    rejected = []
    for name, path, replacement in cases:
        trial = deepcopy(base)
        mutate(trial, path, replacement)
        try:
            validate(trial)
            require(trial == derive(), "mutated receipt accepted")
        except CoverageError:
            rejected.append(name)
        else:
            raise CoverageError(f"mutation survived: {name}")
    require(len(rejected) == len(cases), "mutation accounting drift")
    return {"status": "SELFTEST PASS", "mutations_rejected": len(rejected),
            "cases": rejected,
            "active_load_membership": "REFUTED",
            "partial_tail_membership": "UNPROVEN"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("derive", "record", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "derive":
        value = derive()
    elif args.action == "record":
        value = derive()
        write(RECEIPT, value)
    elif args.action == "selftest":
        value = selftest()
    else:
        audit(load(RECEIPT))
        value = {"status": "PASS", "mutations_rejected": 25,
                 "active_load_membership": "REFUTED",
                 "partial_tail_membership": "UNPROVEN"}
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CoverageError, ElfTruthError, OSError, ValueError, KeyError,
            IndexError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"DEFSTRUCT F018B COVERAGE: {error}", file=sys.stderr)
        raise SystemExit(1)
