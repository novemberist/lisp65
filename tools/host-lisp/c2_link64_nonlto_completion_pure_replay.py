#!/usr/bin/env python3
"""Pure full-gate replay of immutable First-Red Link 64."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_completion_retry_length_elf_gate as LENGTH  # noqa: E402
import c2_link60_boot_inventory_pure_replay as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"


def configure() -> None:
    BASE.LINK_NUMBER = 64
    BASE.SOURCE = ROOT / (
        "build/c2.2/substitution/"
        "product-link-64-nonlto-stateless-completion-length")
    BASE.PRODUCT = BASE.SOURCE / "lisp65-c2-substitution-linked.prg"
    BASE.ELF = Path(str(BASE.PRODUCT) + ".elf")
    BASE.PROFILE = BASE.SOURCE / "resolved-profile.txt"
    BASE.SOURCE_RECEIPT = EVIDENCE / "c2.2-product-link64-internal.json"
    BASE.OUT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-64-nonlto-stateless-completion-length-pure-replay")
    BASE.RECEIPT = EVIDENCE / (
        "c2.2-product-link64-nonlto-stateless-completion-length-"
        "structural-receipt.json")
    BASE.EXPECTED_PRODUCT_SHA = (
        "13c82707ae1797885ff2ddeb7bff62198bf897a9163ed63b7531df8212d49b2c")
    BASE.EXPECTED_SOURCE_STATUS = (
        "FIRST RED: C2-lite real-ABI Link 50 stopped")
    BASE.EXPECTED_SOURCE_DIAGNOSTIC = {
        "message": "final consolidation aggregate/profile gate red",
        "type": "GateError",
    }
    BASE.REQUIRE_SOURCE_PRODUCT_BINDING = False
    BASE.FAILED_PREDECESSOR_PRODUCT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-63-canonical-completion-length/"
        "lisp65-c2-substitution-linked.prg")
    BASE.FAILED_PREDECESSOR_RECEIPT = EVIDENCE / (
        "c2.2-product-link63-canonical-completion-length-"
        "structural-receipt.json")


def main() -> int:
    configure()
    linked = LENGTH.audit_elf(BASE.ELF)
    abi = ABI.audit_elf(BASE.ELF, require_bank3_chain=True)
    BASE.require(
        linked["status"]
            == "passed-linked-stateless-mode-derived-completion-length"
        and linked["mutation_count"] == 9
        and linked["linked_dataflow"][
            "rematerialization_call_count"] == 3
        and len(linked["linked_dataflow"]["structured_call_edges"]) == 4
        and abi["status"] == "passed-all-assembler-leaf-abi-contracts"
        and "c2_completion_mode_length"
            in abi["ELF_derived_C_called_inventory"]["C_called_functions"],
        "Link-64 stateless length or leaf ABI gate red")
    result = BASE.main()
    BASE.require(result == 0, "Link-64 pure full-gate replay stopped")

    length_path = BASE.OUT / "c2-stateless-completion-length-elf-gate.json"
    length_value = {
        "format": "lisp65-c2-stateless-completion-length-ELF-gate-v1",
        "recorded_on": "2026-07-25",
        "status": linked["status"],
        "authority": {
            "contract": BASE.bind(LENGTH.CONTRACT),
            "ELF": BASE.bind(BASE.ELF),
            "gate": BASE.bind(Path(LENGTH.__file__)),
        },
        "result": linked,
    }
    BASE.write_json(length_path, length_value)
    os.chmod(length_path, 0o444)

    abi_path = BASE.OUT / "c2-asm-leaf-abi-dataflow-gate-link64.json"
    BASE.write_json(
        abi_path,
        {
            "format": "lisp65-c2-link64-complete-assembler-ABI-gate-v1",
            "recorded_on": "2026-07-25",
            "status": abi["status"],
            "authority": {
                "ELF": BASE.bind(BASE.ELF),
                "gate": BASE.bind(Path(ABI.__file__)),
            },
            "result": abi,
        })
    os.chmod(abi_path, 0o444)

    os.chmod(BASE.RECEIPT, 0o644)
    receipt = json.loads(BASE.RECEIPT.read_text(encoding="utf-8"))
    receipt["format"] = (
        "lisp65-c2-lite-v6-link64-nonlto-stateless-completion-length-v1")
    receipt["status"] = (
        "passed-link64-nonlto-stateless-completion-length-product-"
        "identity-hardware-not-run")
    receipt["authority"]["link64_replay_driver"] = BASE.bind(Path(__file__))
    receipt["authority"]["completion_length_contract"] = BASE.bind(
        LENGTH.CONTRACT)
    receipt["gates"]["stateless_completion_length_ELF"] = linked["status"]
    receipt["gates"]["complete_assembler_leaf_ABI"] = abi["status"]
    receipt["gates"]["all_green"] = True
    receipt["completion_retry_length"] = {
        "authority":
            "completion mode rematerialized by a named 27-byte non-LTO leaf",
        "linked_leaf": {
            "symbol": "c2_completion_mode_length",
            "section": ".lisp65_rt_c2append_header",
            "bytes": 27,
            "direct_poll_edges": 4,
        },
        "per_attempt_rematerializations": 3,
        "linked_mutations_rejected": 9,
        "source_mutations_rejected": 24,
        "retired_record_27_references": 0,
        "product_bytes_changed_by_replay": 0,
    }
    receipt["next_gate"] = (
        "prepare nonpromotable Cutpoint-3 episode-latch and Cutpoint-4 "
        "write-completion carriers from this exact Link-64 identity; "
        "request device start before hardware")
    receipt["claim_limit"] = (
        "Structurally complete Link 64 only. Hardware Cutpoints 3/4, C1, "
        "the full matrix, promotion and R4/R5/R6/G5/G6 remain unclaimed.")
    BASE.write_json(BASE.RECEIPT, receipt)
    os.chmod(BASE.RECEIPT, 0o444)
    print(
        "c2-link64-nonlto-completion-replay: COMPLETE "
        f"product={BASE.sha(BASE.PRODUCT)} rematerializations=3 "
        "mutations=9 compiler=0 linker=0 product-delta=0 hardware=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BASE.ReplayError, RuntimeError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-link64-nonlto-completion-replay: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
