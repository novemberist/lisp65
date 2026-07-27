#!/usr/bin/env python3
"""Finish Link 55 from its immutable artifact after a historical checker Red."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link55_append_suffix_fusion_artifact_replay as QUAL  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "product-link-55-c2-lite-v6-append-suffix-fusion-attempt2")
PRODUCT = SOURCE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
FIRST_RED = EVIDENCE / (
    "c2.2-product-link55-c2-lite-v6-append-suffix-fusion-"
    "attempt2-structural-receipt.json")
FIRST_RED_SHA = (
    "5826a9c7eb9a4125325a2482c0db62aa59fd865e89792ed09b492620ee1bfbc6")
WPLTO = EVIDENCE / (
    "c2.2-link55-append-suffix-fusion-asm-leaf-"
    "artifact-replay2-receipt.json")
WPLTO_SHA = (
    "2d0c8bf53596ac733fe379bb4f342c09f5ea0617c5dd6b2168c714ea2837cc6e")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-55-c2-lite-v6-append-suffix-fusion-completion2")
RECEIPT = EVIDENCE / (
    "c2.2-product-link55-c2-lite-v6-append-suffix-fusion-"
    "final-structural-receipt.json")


class CompletionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CompletionError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"Link-55 completion input absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def snapshot(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {
            "bytes": path.stat().st_size,
            "mode": oct(path.stat().st_mode & 0o777),
            "sha256": sha(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def replay() -> dict[str, Any]:
    old = {
        "source": QUAL.SOURCE,
        "product": QUAL.PRODUCT,
        "elf": QUAL.ELF,
        "map": QUAL.MAP,
        "out": QUAL.OUT,
        "receipt": QUAL.RECEIPT,
        "base_out": QUAL.BASE.BASE_LINK.OUT,
    }
    original_run = subprocess.run
    commands: list[str] = []

    def guarded_run(command: Any, *args: Any, **kwargs: Any) -> Any:
        executable = Path(str(command[0] if isinstance(command, (list, tuple))
                              else command)).name
        lowered = executable.lower()
        require("clang" not in lowered and lowered not in {
                    "cc", "gcc", "ld", "ld.lld", "lld",
                    "mos-mega65-clang"},
                f"Link-55 completion attempted compiler/linker: {executable}")
        commands.append(executable)
        return original_run(command, *args, **kwargs)

    try:
        QUAL.SOURCE = SOURCE
        QUAL.PRODUCT = PRODUCT
        QUAL.ELF = ELF
        QUAL.MAP = MAP
        QUAL.OUT = OUT
        QUAL.RECEIPT = OUT / "nested-replay-receipt.json"
        QUAL.configure()
        QUAL.BASE.BASE_LINK.OUT = SOURCE
        subprocess.run = guarded_run
        value = QUAL.read_only_gates()
    finally:
        subprocess.run = original_run
        QUAL.SOURCE = old["source"]
        QUAL.PRODUCT = old["product"]
        QUAL.ELF = old["elf"]
        QUAL.MAP = old["map"]
        QUAL.OUT = old["out"]
        QUAL.RECEIPT = old["receipt"]
        QUAL.BASE.BASE_LINK.OUT = old["base_out"]
    value["read_only_tool_invocations"] = commands
    return value


def main() -> int:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Link-55 artifact completion is one-shot")
    require(FIRST_RED.is_file() and sha(FIRST_RED) == FIRST_RED_SHA
            and WPLTO.is_file() and sha(WPLTO) == WPLTO_SHA,
            "Link-55 artifact-completion authority drift")
    before = snapshot(SOURCE)
    require(before and all((int(row["mode"], 8) & 0o222) == 0
                           for row in before.values()),
            "Link-55 product artifact tree is not read-only")
    source = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    prelink = source["fresh_prelink_gates"]
    linked = source["fresh_replacement_gates"]
    generic = source["fresh_generic_gates"]
    plan = linked["append_phase_plan"]["plan_data"][
        "lisp65_c2_append_persistent_publish_plan"]["bytes"]
    require(
        source["link_number"] == 55
        and source["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and source["execution_accounting"]["product_closure_links"] == 1
        and source["execution_accounting"]["hardware_runs"] == 0
        and source["post_link_identity"]["status"] == "passed"
        and prelink["status"] == "passed"
        and linked["status"] == "passed"
        and all((row == "passed" if isinstance(row, str)
                 else row["status"] == "passed")
                for row in generic.values())
        and plan == [37, 38, 39, 40, 0],
        "Link-55 immutable link evidence is incomplete")
    first_source = prelink["phase06a_cutpoint_source"]
    first_linked = linked["phase06a_cutpoint"]
    require(
        first_source["append_suffix_read_domain"]["status"] ==
            "passed-four-phase-suffix-and-source-domain-contract"
        and len(first_source["append_suffix_read_domain"][
            "negative_mutations"]) == 13
        and first_source["journal_prepare_co_residence"]["status"] ==
            "passed-one-record-journal-prepare-source-contract"
        and first_source["journal_prepare_co_residence"]["fixture"][
            "negative_mutations"] == 6
        and first_linked["append_suffix_read_domain"]["status"] ==
            "passed-linked-four-phase-suffix-domain-closure"
        and first_linked["journal_prepare_co_residence"]["status"] ==
            "passed-linked-one-record-journal-prepare-cutpoint"
        and first_linked["journal_prepare_co_residence"]["bytes"] == 1764
        and first_linked["assembler_leaf_abi"][
            "journal_prepare_selector"]["status"] ==
            "passed-real-context-ABI-and-two-tail-edges",
        "Link-55 fresh suffix/fusion gates are incomplete")

    OUT.mkdir(parents=True)
    fresh = replay()
    require(
        fresh["walls"] == {
            "bank0_text_headroom_bytes": 48,
            "ordinary_bank0_bss_headroom_bytes": 213,
            "fixed_hot_block_headroom_bytes": 33,
            "resident_island_headroom_bytes": 5,
            "e000_headroom_bytes": 58,
        }
        and fresh["capacity"]["session_catalog_records"] == 48
        and fresh["capacity"]["session_family_bytes"] == 65438
        and fresh["capacity"]["session_family_headroom_bytes"] == 98
        and fresh["journal_prepare_co_residence_linked"]["bytes"] == 1764
        and fresh["journal_prepare_co_residence_linked"][
            "packed_recovered_bytes"] == 256,
        "Link-55 pure completion replay red")
    require(before == snapshot(SOURCE),
            "Link-55 completion modified the immutable product tree")

    value = dict(source)
    value["format"] = (
        "lisp65-c2-lite-v6-link55-append-suffix-fusion-final-v1")
    value["recorded_on"] = "2026-07-23"
    value["status"] = (
        "passed-append-suffix-and-one-quantum-fusion-"
        "product-identity-hardware-not-run")
    value["promotable"] = False
    value["authority"]["link55_base_link_receipt"] = bind(FIRST_RED)
    value["authority"]["link55_WPLTO_artifact_replay"] = bind(WPLTO)
    value["authority"]["artifact_completion_driver"] = bind(Path(__file__))
    value["class_A_completion"] = {
        "historical_checker": (
            "Link-50 expected persistent plan [38,39,40,41,0]"),
        "current_authorized_truth": (
            "one-record journal/prepare fusion removes one catalog record "
            "and yields persistent plan [37,38,39,40,0]"),
        "verifier_binding": "$b94e+40 unchanged",
        "product_bytes_changed": 0,
        "capacity_effect_bytes": 0,
        "compiler_runs": 0,
        "linker_runs": 0,
        "hardware_runs": 0,
    }
    value["fresh_completion_replay"] = fresh
    value["append_suffix_and_fusion"] = {
        "suffix_source_gate":
            first_source["append_suffix_read_domain"],
        "suffix_linked_gate":
            fresh["append_suffix_read_domain_linked"],
        "fusion_source_gate":
            first_source["journal_prepare_co_residence"],
        "fusion_linked_gate":
            fresh["journal_prepare_co_residence_linked"],
        "assembler_leaf_ABI":
            fresh["assembler_leaf_abi"]["journal_prepare_selector"],
        "session_catalog_records": {"before": 49, "after": 48},
        "session_family_headroom_bytes": 98,
    }
    value["counters"] = {
        "line1_product_first_reds": "2/3",
        "completed_latency_measurements": "0/2",
    }
    value["next_gate"] = (
        "Hardware double run: boot, defun/cold first call, immediate warm "
        "second call; then the remaining seven-row C2-lite presmoke.")
    report = OUT / "artifact-completion-report.json"
    write(report, {
        "status": value["status"],
        "source_link_receipt": bind(FIRST_RED),
        "product_identity": value["product_identity"],
        "fresh_completion_replay": fresh,
        "execution_accounting": value["class_A_completion"],
    })
    value["artifact_completion_report"] = bind(report)
    write(RECEIPT, value)
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link55-artifact-completion: COMPLETE "
          f"product={sha(PRODUCT)} text={fresh['walls']['bank0_text_headroom_bytes']} "
          f"e000={fresh['walls']['e000_headroom_bytes']} "
          f"fusion={fresh['journal_prepare_co_residence_linked']['bytes']} "
          f"session={fresh['capacity']['session_family_bytes']} "
          "compiler=0 linker=0 hardware=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CompletionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link55-artifact-completion: FIRST RED: " +
              str(error), file=sys.stderr)
        raise SystemExit(2)
