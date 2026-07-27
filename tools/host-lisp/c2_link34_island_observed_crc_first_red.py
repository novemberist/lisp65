#!/usr/bin/env python3
"""Bind the Link-34 double-CRC hardware First Red without another device run."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RESULT = ROOT / "build/c2.2/link34-observed-crc-hardware/hardware-result.json"
PROBE = EVIDENCE / "c2.2-link34-observed-crc-double-wplto-probe-receipt.json"
LINK = EVIDENCE / "c2.2-link34-observed-crc-diagnostic-link-receipt.json"
SOURCE = ROOT / "src/vm_runtime_overlay.c"
LINK34 = ROOT / (
    "build/c2.2/substitution/product-link-34-crc-asm-leaf/"
    "lisp65-c2-substitution-linked.prg")
OUTPUT = EVIDENCE / (
    "c2.2-product-link34-catalog-verifier-edma-completion-hardware-first-red-"
    "diagnosis.json")

EXPECTED = {
    RESULT: "c4b82a8c0928d89220a9a8a5fab4174ce942a0a68c9a956d224df2c082595029",
    PROBE: "66dd5f35ebb3f24eb58861a1e6c2c317be174c675d501c018b2ef5cf4a4e7fbf",
    LINK: "4db71f5cb6225b222e5565a9f1aaf40c920933312890af9e43daec76c0e9a544",
    LINK34: "bef7708baa12b8e23094c2150a53f5bee529be25b9b9e11d0d68a3191ee6a485",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise RuntimeError(f"observed-CRC evidence absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("observed-CRC First-Red diagnosis already exists")
    for path, digest in EXPECTED.items():
        if sha(path) != digest:
            raise RuntimeError(f"observed-CRC evidence drift: {path}")
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    observed = result["observed"]
    if not (
        result["status"] == "FIRST RED: evolving-or-partially-visible-cpu-view"
        and result["promotable"] is False
        and observed["expected_crc16"] == "0xb47f"
        and observed["first_crc16"] == "0x8e92"
        and observed["second_crc16"] == "0xe092"
        and observed["first_crc16"] != observed["second_crc16"]
    ):
        raise RuntimeError("observed-CRC result does not prove the bounded First Red")
    source = SOURCE.read_text(encoding="utf-8")
    trigger = (
        '"lda #1\\n\\t"\n'
        '        "sta $d703\\n\\t"\n'
        '        "lda #0\\n\\t"\n'
        '        "sta $d702\\n\\t"\n'
        '        "sta $d704\\n\\t"')
    if trigger not in source or "sta $d705" not in source:
        raise RuntimeError("runtime-overlay Enhanced-DMA trigger source drift")

    value = {
        "format": "lisp65-c2-link34-edma-completion-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": (
            "FIRST RED: first verifier EDMA payload changes across immediate "
            "sequential CPU CRCs"),
        "promotable": False,
        "observation": {
            "destination": "0xc356",
            "length_bytes": 1156,
            "expected_crc16": "0xb47f",
            "first_cpu_crc16": "0x8e92",
            "second_cpu_crc16": "0xe092",
            "same_routine": "rtov_crc_mem assembler leaf",
            "same_address_and_length": True,
            "intervening_mapping_change": False,
            "intervening_software_write": False,
            "second_read_is_immediate": True,
        },
        "diagnosis": {
            "proved": [
                "the first verifier transfer is not fully/stably visible to the CPU when its first CRC starts",
                "the CPU-visible payload continues changing across the two sequential CRC traversals",
                "stable mapping/aliasing divergence is not the observed failure mode",
                "the original payload-CRC failure is real and occurs before verifier entry",
            ],
            "strong_inference": (
                "Enhanced-DMA completion/visibility ordering is missing at the "
                "rtov_read-to-CRC boundary"),
            "not_yet_proved": (
                "the exact target completion primitive/barrier and its capacity cost"),
            "source_fact": (
                "rtov_read publishes the Enhanced-DMA descriptor and immediately "
                "returns after the trigger sequence; it contains no explicit "
                "software completion observation before the caller starts CRC"),
        },
        "error_path_followup": {
            "required_product_rule": (
                "the first innermost status wins; outer layers may enrich it but "
                "must never replace it"),
            "implementation": "deferred until the diagnosis is reviewed",
        },
        "execution_accounting": {
            "diagnostic_hardware_runs": 1,
            "capture_evaluation_replays": 1,
            "product_presmoke_retries": 0,
            "promotable_product_links": 0,
        },
        "capacity": {
            "new_state_bytes": 0,
            "diagnostic_bank0_text_debit_vs_link34_bytes": 44,
            "diagnostic_bank0_text_headroom_bytes": 11,
            "all_other_resident_walls": "unchanged",
        },
        "evidence": {
            "hardware_result": bind(RESULT),
            "capacity_probe": bind(PROBE),
            "diagnostic_link": bind(LINK),
            "diagnostic_source": bind(SOURCE),
            "link34_rollback_product": {**bind(LINK34), "status": "untouched"},
        },
        "claim_limit": (
            "One non-promotable diagnostic hardware run. This receipt localizes "
            "the transport ordering failure; it is not a product fix, product "
            "acceptance, promotion or authorization for a successor link."),
        "next_gate": (
            "review completion/barrier contract and first-status-wins fix; no "
            "automatic product change or additional hardware run"),
    }
    OUTPUT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    os.chmod(OUTPUT, 0o444)
    print("c2-link34-island-observed-crc-first-red: " + value["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
