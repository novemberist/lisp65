#!/usr/bin/env python3
"""Run the sole WPLTO map for the Link 64 non-LTO mode-length leaf."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_two_region_e000_s1_final_wplto as BASE  # noqa: E402
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_completion_retry_length_elf_gate as LENGTH  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
STEM = "link64-nonlto-stateless-completion-length"
LINKED_GATE = EVIDENCE / f"c2.2-{STEM}-linked-leaf-gates.json"


def bind(path: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main() -> int:
    stem = STEM
    if LINKED_GATE.exists():
        raise RuntimeError("Link 64 non-LTO linked gate is one-shot")
    BASE.OUT = ROOT / f"build/c2.2/substitution/{stem}-wplto"
    BASE.INTERNAL = EVIDENCE / f"c2.2-{stem}-wplto-internal.json"
    BASE.BASE_RECEIPT = EVIDENCE / f"c2.2-{stem}-wplto-base.json"
    BASE.RAW_RECEIPT = EVIDENCE / f"c2.2-{stem}-wplto-raw.json"
    BASE.REPLAY_OUT = ROOT / f"build/c2.2/substitution/{stem}-qualification"
    BASE.REPLAY_RECEIPT = EVIDENCE / f"c2.2-{stem}-qualification.json"
    BASE.BASE_RESULT = EVIDENCE / f"c2.2-{stem}-wplto-base-result.json"
    BASE.FORMAT_RECEIPT = EVIDENCE / (
        f"c2.2-{stem}-format-and-stage-gate.json")
    BASE.COMPLETION_SOURCE_RECEIPT = ROOT / (
        f"build/c2.2/two-region-session-store/"
        f"{stem}-write-completion-source-gate.json")
    BASE.EMITTER_RECEIPT = EVIDENCE / (
        f"c2.2-{stem}-emitter-union-gate.json")
    BASE.ISLAND_RECEIPT = EVIDENCE / (
        f"c2.2-{stem}-preinstall-source-host-gate.json")
    BASE.RECEIPT = EVIDENCE / f"c2.2-{stem}-wplto-receipt.json"
    BASE.PRODUCT = BASE.OUT / "lisp65-c2-substitution-linked.prg"
    BASE.ELF = Path(str(BASE.PRODUCT) + ".elf")
    BASE.MAP = Path(str(BASE.PRODUCT) + ".map")
    BASE.C2D = (
        BASE.OUT
        / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
    BASE.RUNNER_PATH = Path(__file__)
    result = BASE.main()
    if not BASE.ELF.is_file():
        return result
    linked = LENGTH.audit_elf(BASE.ELF)
    abi = ABI.audit_elf(BASE.ELF, require_bank3_chain=True)
    value = {
        "format": "lisp65-c2-link64-non-LTO-mode-length-linked-gates-v1",
        "recorded_on": "2026-07-25",
        "status": (
            "passed-linked-non-LTO-mode-length-and-complete-assembler-ABI"
            if linked["status"].startswith("passed")
            and abi["status"] == "passed-all-assembler-leaf-abi-contracts"
            else "FIRST RED: linked non-LTO mode-length gate stopped"),
        "authority": {
            "ELF": bind(BASE.ELF),
            "mode_length_source": bind(
                ROOT / "src/c2_completion_mode_length.s"),
            "mode_length_gate": bind(Path(LENGTH.__file__)),
            "assembler_ABI_gate": bind(Path(ABI.__file__)),
        },
        "mode_length": linked,
        "assembler_ABI": {
            "status": abi["status"],
            "source_inventory": abi["source_inventory"],
            "linked_leaf":
                abi["linked_inventory"]["c2_completion_mode_length"],
            "ELF_derived_C_called_inventory":
                abi["ELF_derived_C_called_inventory"],
        },
        "execution_accounting": {
            "additional_compiler_or_linker_runs": 0,
            "hardware_runs": 0,
        },
    }
    LINKED_GATE.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(LINKED_GATE, 0o444)
    return result if value["status"].startswith("passed") else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BASE.FinalMapError, RuntimeError, OSError, ValueError, KeyError,
    ) as error:
        print(
            "c2-link64-nonlto-stateless-completion-wplto: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
