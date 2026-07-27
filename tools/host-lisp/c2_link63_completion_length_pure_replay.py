#!/usr/bin/env python3
"""Pure full-gate replay of immutable First-Red Link 63."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_completion_retry_length_elf_gate as LENGTH_ELF  # noqa: E402
import c2_link60_boot_inventory_pure_replay as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"


def configure() -> None:
    BASE.LINK_NUMBER = 63
    BASE.SOURCE = ROOT / (
        "build/c2.2/substitution/"
        "product-link-63-canonical-completion-length")
    BASE.PRODUCT = BASE.SOURCE / "lisp65-c2-substitution-linked.prg"
    BASE.ELF = Path(str(BASE.PRODUCT) + ".elf")
    BASE.PROFILE = BASE.SOURCE / "resolved-profile.txt"
    BASE.SOURCE_RECEIPT = EVIDENCE / "c2.2-product-link63-internal.json"
    BASE.OUT = ROOT / (
        "build/c2.2/substitution/"
        "product-link-63-canonical-completion-length-pure-replay")
    BASE.RECEIPT = EVIDENCE / (
        "c2.2-product-link63-canonical-completion-length-"
        "structural-receipt.json")
    BASE.EXPECTED_PRODUCT_SHA = (
        "46f93f1bd890761af55fd1170349e841d3f8c906edff2f59ef12a96f40362fe6")
    BASE.EXPECTED_SOURCE_STATUS = (
        "FIRST RED: C2-lite real-ABI Link 50 stopped")
    BASE.EXPECTED_SOURCE_DIAGNOSTIC = {
        "message": "final consolidation aggregate/profile gate red",
        "type": "GateError",
    }
    BASE.REQUIRE_SOURCE_PRODUCT_BINDING = False
    BASE.FAILED_PREDECESSOR_PRODUCT = ROOT / (
        "build/c2.2/substitution/product-link-62-post-shelf-region1/"
        "lisp65-c2-substitution-linked.prg")
    BASE.FAILED_PREDECESSOR_RECEIPT = EVIDENCE / (
        "c2.2-link62-slot39-threshold-length-liveness-replay-receipt.json")


def main() -> int:
    configure()
    linked = LENGTH_ELF.audit_elf(BASE.ELF)
    BASE.require(
        linked["status"]
        == "passed-linked-record-owned-retry-length-and-scratch-clobber-pin"
        and linked["mutation_count"] == 4
        and linked["linked_dataflow"]["reload_count"] == 2
        and linked["linked_dataflow"]["retry_edge_count"] == 2,
        "Link-63 completion retry-length ELF gate red",
    )
    result = BASE.main()
    BASE.require(result == 0, "Link-63 pure full-gate replay stopped")

    gate_path = BASE.OUT / "c2-completion-retry-length-elf-gate.json"
    gate_value = {
        "format": "lisp65-c2-completion-retry-length-ELF-gate-v1",
        "recorded_on": "2026-07-24",
        "status": linked["status"],
        "authority": {
            "contract": BASE.bind(LENGTH_ELF.CONTRACT),
            "ELF": BASE.bind(BASE.ELF),
            "gate": BASE.bind(Path(LENGTH_ELF.__file__)),
        },
        "result": linked,
    }
    BASE.write_json(gate_path, gate_value)
    os.chmod(gate_path, 0o444)

    os.chmod(BASE.RECEIPT, 0o644)
    receipt = json.loads(BASE.RECEIPT.read_text(encoding="utf-8"))
    receipt["format"] = (
        "lisp65-c2-lite-v6-link63-canonical-completion-length-v1")
    receipt["status"] = (
        "passed-link63-canonical-completion-length-product-identity-"
        "hardware-not-run")
    receipt["authority"]["link63_replay_driver"] = BASE.bind(Path(__file__))
    receipt["authority"]["retry_length_contract"] = BASE.bind(
        LENGTH_ELF.CONTRACT)
    receipt["gates"]["completion_retry_length_ELF"] = linked["status"]
    receipt["gates"]["all_green"] = True
    receipt["completion_retry_length"] = {
        "authority": "verified record byte 27",
        "reload_policy":
            "reload before every attempt and after every nested Bank-5 read",
        "linked_reload_count": 2,
        "linked_retry_edges": 2,
        "linked_mutations_rejected": 4,
        "source_mutations_rejected": 22,
        "product_bytes_changed_by_replay": 0,
    }
    receipt["next_gate"] = (
        "prepare nonpromotable Cutpoint-3 episode-latch and Cutpoint-4 "
        "write-completion carriers from this exact Link-63 identity; "
        "request device start before hardware")
    receipt["claim_limit"] = (
        "Structurally complete Link 63 only. Hardware Cutpoints 3/4, C1, "
        "the full matrix, promotion and R4/R5/R6/G5/G6 remain unclaimed.")
    BASE.write_json(BASE.RECEIPT, receipt)
    os.chmod(BASE.RECEIPT, 0o444)
    print(
        "c2-link63-completion-length-replay: COMPLETE "
        f"product={BASE.sha(BASE.PRODUCT)} reloads=2 mutations=4 "
        "compiler=0 linker=0 product-delta=0 hardware=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BASE.ReplayError, RuntimeError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-link63-completion-length-replay: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
