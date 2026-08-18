#!/usr/bin/env python3
"""Bind Link-116 WYSIWYG behavior without constraining instructions.

The linked image is tied to the exact source consumed by the real target
compiler.  The source contract and all 512 input/capacity cases establish the
behavior.  No opcode, mnemonic, register choice, or adjacency is contractual.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v21_wysiwyg_input as WYSIWYG  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v2.1-wysiwyg-text-recovery-replacement-card"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PROFILE = BUILD / "wplto/resolved-profile.txt"
SEMANTIC = ROOT / (
    "build/c2.3/v2.1-wysiwyg-text-recovery-replacement-card-preflight-r3/"
    "semantic-repl-compile.json")
PRICING = ARCH / "c2.3-v2.1-wysiwyg-text-recovery-pricing-receipt.json"
REPL = ROOT / "src/repl.c"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()


class SemanticError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SemanticError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def derive(elf: Path = ELF) -> dict[str, Any]:
    source_sha = hashlib.sha256(REPL.read_bytes()).hexdigest()
    semantic = load(SEMANTIC)
    pricing = load(PRICING)
    behavior = WYSIWYG.derive()
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
    repl = truth.symbol("repl")
    profile = PROFILE.read_text(encoding="utf-8")
    equivalence = pricing["option_a_micro"]["semantic_equivalence"]
    require(semantic["source"]["sha256"] == source_sha
            and semantic["status"] ==
                "PASS: current repl consumed by real configured compiler"
            and f"input_sha256=src/repl.c:{source_sha}" in profile
            and behavior["contract"]["a0_normalized_before_echo"] is True
            and behavior["contract"]["a0_normalized_before_store"] is True
            and behavior["control_rejection"]["silent_drop_allowed"] is False
            and equivalence == {
                "a0_result": "0x20", "buffer_full_external_delta": 0,
                "byte_values": 256, "cases": 512, "mismatches": 0,
                "room_states": 2, "visible_rejection_bytes": 64,
                "visible_rejection_ranges": ["0x00..0x1f", "0x80..0x9f"]}
            and repl.bytes > 0,
            "linked WYSIWYG semantic authority drift")
    return {
        "status": "PASS: linked WYSIWYG behavior; instruction selection free",
        "linked_repl": {"address": f"0x{repl.value:04x}",
                         "bytes": repl.bytes,
                         "consumed_source_sha256": source_sha},
        "behavior": {
            "a0_result": "0x20",
            "normalizes_before_echo": True,
            "normalizes_before_store": True,
            "unmappable_controls_reject_visibly": True,
            "historical_poison_forms": 2,
            "historical_poison_forms_canonical_bytes": 12,
            "exhaustive_cases": 512,
            "semantic_mismatches": 0,
        },
        "compiler_evidence": {
            "real_configured_target_compile": True,
            "profile_consumed_exact_source": True,
            "instruction_selection_constraint": None,
            "opcode_or_mnemonic_identity_is_contract": False,
        },
        "authority": {
            "semantic_compile_sha256": hashlib.sha256(
                SEMANTIC.read_bytes()).hexdigest(),
            "pricing_sha256": hashlib.sha256(PRICING.read_bytes()).hexdigest(),
            "WYSIWYG_receipt_sha256": hashlib.sha256(
                WYSIWYG.RECEIPT.read_bytes()).hexdigest(),
            "checker": DRIVER.relative_to(ROOT).as_posix(),
        },
    }


def validate(value: dict[str, Any]) -> None:
    behavior = value["behavior"]
    compiler = value["compiler_evidence"]
    require(value["status"] ==
                "PASS: linked WYSIWYG behavior; instruction selection free"
            and behavior == {
                "a0_result": "0x20", "normalizes_before_echo": True,
                "normalizes_before_store": True,
                "unmappable_controls_reject_visibly": True,
                "historical_poison_forms": 2,
                "historical_poison_forms_canonical_bytes": 12,
                "exhaustive_cases": 512, "semantic_mismatches": 0}
            and compiler["real_configured_target_compile"] is True
            and compiler["profile_consumed_exact_source"] is True
            and compiler["instruction_selection_constraint"] is None
            and compiler["opcode_or_mnemonic_identity_is_contract"] is False,
            "WYSIWYG behavioral contract drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "reintroduce-CMP-LDA-opcode-pin": lambda x: x[
            "compiler_evidence"].update(
                instruction_selection_constraint="CMP #$A0; LDA #$20"),
        "reintroduce-CPY-LDX-opcode-pin": lambda x: x[
            "compiler_evidence"].update(
                instruction_selection_constraint="CPY #$A0; LDX #$20"),
        "make-mnemonics-contractual": lambda x: x[
            "compiler_evidence"].update(
                opcode_or_mnemonic_identity_is_contract=True),
        "normalize-after-echo": lambda x: x["behavior"].update(
            normalizes_before_echo=False),
        "normalize-after-store": lambda x: x["behavior"].update(
            normalizes_before_store=False),
        "silently-drop-control": lambda x: x["behavior"].update(
            unmappable_controls_reject_visibly=False),
        "restore-poison-size": lambda x: x["behavior"].update(
            historical_poison_forms_canonical_bytes=20),
        "hide-semantic-mismatch": lambda x: x["behavior"].update(
            semantic_mismatches=1),
        "drop-real-compiler": lambda x: x["compiler_evidence"].update(
            real_configured_target_compile=False),
        "drop-consumed-source": lambda x: x["compiler_evidence"].update(
            profile_consumed_exact_source=False),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except SemanticError:
            rejected.append(name)
    require(rejected == list(cases), "WYSIWYG semantic mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check",))
    parser.parse_args()
    value = derive()
    validate(value)
    rejected = mutations(value)
    print("WYSIWYG linked semantics: PASS cases=512 "
          f"opcode-pins=0 mutations={len(rejected)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SemanticError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"WYSIWYG linked semantics: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
