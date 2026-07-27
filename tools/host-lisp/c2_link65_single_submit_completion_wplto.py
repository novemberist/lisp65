#!/usr/bin/env python3
"""Run the sole WPLTO map for single-submit completion observation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_completion_retry_length_elf_gate as LENGTH  # noqa: E402
import c2_two_region_e000_s1_final_wplto as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
STEM = "link65-single-submit-completion"
LINKED_GATE = EVIDENCE / f"c2.2-{STEM}-linked-gates.json"
RECEIPT = EVIDENCE / f"c2.2-{STEM}-wplto-qualification-receipt.json"


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def write_receipt(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(path, 0o444)


def configure() -> None:
    BASE.OUT = ROOT / f"build/c2.2/substitution/{STEM}-wplto"
    BASE.INTERNAL = EVIDENCE / f"c2.2-{STEM}-wplto-internal.json"
    BASE.BASE_RECEIPT = EVIDENCE / f"c2.2-{STEM}-wplto-base.json"
    BASE.RAW_RECEIPT = EVIDENCE / f"c2.2-{STEM}-wplto-raw.json"
    BASE.REPLAY_OUT = ROOT / (
        f"build/c2.2/substitution/{STEM}-qualification")
    BASE.REPLAY_RECEIPT = EVIDENCE / (
        f"c2.2-{STEM}-qualification.json")
    BASE.BASE_RESULT = EVIDENCE / (
        f"c2.2-{STEM}-wplto-base-result.json")
    BASE.FORMAT_RECEIPT = EVIDENCE / (
        f"c2.2-{STEM}-format-and-stage-gate.json")
    BASE.COMPLETION_SOURCE_RECEIPT = ROOT / (
        "build/c2.2/two-region-session-store/"
        f"{STEM}-write-completion-source-gate.json")
    BASE.EMITTER_RECEIPT = EVIDENCE / (
        f"c2.2-{STEM}-emitter-union-gate.json")
    BASE.ISLAND_RECEIPT = EVIDENCE / (
        f"c2.2-{STEM}-preinstall-source-host-gate.json")
    BASE.RECEIPT = EVIDENCE / f"c2.2-{STEM}-wplto-receipt.json"
    BASE.PRODUCT = BASE.OUT / "lisp65-c2-substitution-linked.prg"
    BASE.ELF = Path(str(BASE.PRODUCT) + ".elf")
    BASE.MAP = Path(str(BASE.PRODUCT) + ".map")
    BASE.C2D = (
        BASE.OUT
        / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
    BASE.RUNNER_PATH = Path(__file__)


def linked_gates() -> tuple[dict[str, Any], dict[str, Any]]:
    linked = LENGTH.audit_elf(BASE.ELF)
    abi = ABI.audit_elf(BASE.ELF, require_bank3_chain=True)
    require(
        linked["status"] ==
            "passed-linked-stateless-mode-derived-completion-length"
        and linked["mutation_count"] == 10
        and linked["phase_mutation_count"] == 6
        and linked["linked_dataflow"]["rematerialization_call_count"] == 3
        and len(linked["linked_dataflow"]["structured_call_edges"]) == 4,
        "linked stateless-length proof is incomplete")
    single = linked["linked_dataflow"]["poll"]["single_submit"]
    require(
        single == {
            "reader_call_count": 1,
            "retry_target_is_after_reader": True,
            "retry_target_is_after_poison": True,
        },
        "linked completion loop is not one submit plus local observation")
    require(
        abi["status"] == "passed-all-assembler-leaf-abi-contracts",
        "complete assembler-leaf ABI inventory is red")
    value = {
        "format":
            "lisp65-c2-link65-single-submit-completion-linked-gates-v1",
        "recorded_on": "2026-07-26",
        "status":
            "passed-single-submit-local-observation-and-complete-leaf-ABI",
        "authority": {
            "ELF": bind(BASE.ELF),
            "mode_length_source": bind(
                ROOT / "src/c2_completion_mode_length.s"),
            "mode_length_gate": bind(Path(LENGTH.__file__)),
            "assembler_ABI_gate": bind(Path(ABI.__file__)),
        },
        "completion": linked,
        "assembler_ABI": {
            "status": abi["status"],
            "source_inventory": abi["source_inventory"],
            "ELF_derived_C_called_inventory":
                abi["ELF_derived_C_called_inventory"],
        },
        "execution_accounting": {
            "additional_compiler_or_linker_runs": 0,
            "hardware_runs": 0,
        },
    }
    write_receipt(LINKED_GATE, value)
    return linked, abi


def main() -> int:
    require(not LINKED_GATE.exists() and not RECEIPT.exists(),
            "single-submit completion qualification is one-shot")
    configure()
    result = BASE.main()
    require(result == 0 and BASE.ELF.is_file() and BASE.MAP.is_file(),
            "base WPLTO stopped before linked qualification")
    linked, abi = linked_gates()
    base = json.loads(BASE.RECEIPT.read_text(encoding="utf-8"))
    source = json.loads(
        BASE.COMPLETION_SOURCE_RECEIPT.read_text(encoding="utf-8"))
    walls = base["walls"]
    capacity = base["regions"]
    green = (
        base["status"].startswith("passed")
        and source["status"].startswith("passed")
        and source["mutation_count"] == 25
        and linked["status"].startswith("passed")
        and abi["status"] == "passed-all-assembler-leaf-abi-contracts"
        and int(walls["bank0_text_headroom_bytes"]) >= 32
        and int(walls["ordinary_bank0_bss_headroom_bytes"]) >= 0
        and int(walls["fixed_hot_block_headroom_bytes"]) >= 0
        and int(walls["resident_island_headroom_bytes"]) >= 0
        and int(walls["e000_headroom_bytes"]) >= 54
        and int(capacity["main_bytes"]) <= 65536)
    value = {
        "format":
            "lisp65-c2-link65-single-submit-completion-WPLTO-v1",
        "recorded_on": "2026-07-26",
        "status": (
            "passed-single-submit-completion-all-walls-and-gates-green"
            if green else
            "FIRST RED: single-submit completion qualification did not close"),
        "promotable": False,
        "authority": {
            "contract": bind(
                ROOT / "config/c2-cpu-chip-write-completion-contract.json"),
            "runtime": bind(ROOT / "src/c2_product_runtime.c"),
            "source_gate": bind(BASE.COMPLETION_SOURCE_RECEIPT),
            "linked_gate": bind(LINKED_GATE),
            "base_WPLTO": bind(BASE.RECEIPT),
            "driver": bind(Path(__file__)),
            "ELF": bind(BASE.ELF),
            "map": bind(BASE.MAP),
        },
        "fix": {
            "poison_passes": 1,
            "target_read_submissions": 1,
            "retry_scope": "local observed-buffer comparison only",
            "source_mutations_rejected": source["mutation_count"],
            "linked_mutations_rejected": linked["mutation_count"],
            "phase_mutations_rejected": linked["phase_mutation_count"],
        },
        "walls": walls,
        "wall_requirements": {
            "bank0_text_noise_headroom_bytes": 32,
            "E000_floor_bytes": 54,
            "ordinary_bank0_bss_headroom_bytes": 0,
            "fixed_hot_block_headroom_bytes": 0,
            "resident_island_headroom_bytes": 0,
        },
        "regions": capacity,
        "execution_accounting": {
            "whole_program_LTO_closure_links": 1,
            "automatic_retries": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "Product-shaped WPLTO only. No product identity, hardware run, "
            "C1 closure, matrix-gate fall or acceptance-chain claim."),
        "next_gate": (
            "Separate Class-C authorization for the successor product link"
            if green else
            "First-Red review; no product link or hardware"),
    }
    write_receipt(RECEIPT, value)
    print(
        "c2-link65-single-submit-completion-wplto: "
        + ("PASS" if green else "FIRST RED")
        + f" text={walls['bank0_text_headroom_bytes']}"
        + f" e000={walls['e000_headroom_bytes']}"
        + f" session={capacity['main_bytes']}")
    return 0 if green else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BASE.FinalMapError, ProbeError, RuntimeError, OSError, ValueError,
        KeyError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-link65-single-submit-completion-wplto: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
