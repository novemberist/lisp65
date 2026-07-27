#!/usr/bin/env python3
"""Pure artifact replay after the L65E ABI gate learned both indirect edges.

No source compiler or linker is invoked.  The script re-asks the corrected
gates against the immutable product-shaped WPLTO ELF, derives every wall from
that ELF, and proves that the only runtime-overlay size change is the two-byte
L65E reduction (therefore the packed 64-KiB Session aggregate is unchanged).
"""

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
import c2_lite_v6_bank2_target_stage_successor_link as LINK44  # noqa: E402
import c2_lite_v6_link45_bcode_ordinal_wplto as ORDINAL  # noqa: E402
import c2_transient_execution_lookup_gate as TRANSIENT  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
WPLTO = ROOT / "build/c2.2/substitution/link46-l65e-transient-wplto"
REPLAY = ROOT / (
    "build/c2.2/substitution/link46-l65e-transient-artifact-replay")
BASE_ELF = ROOT / (
    "build/c2.2/substitution/"
    "product-link-46-c2-lite-v6-bcode-ordinal-renderer/"
    "lisp65-c2-substitution-linked.prg.elf")
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRODUCT = WPLTO / "lisp65-c2-substitution-linked.prg"
MAP = WPLTO / "lisp65-c2-substitution-linked.prg.map"
INTERNAL = EVIDENCE / "c2.2-link46-l65e-transient-wplto-internal.json"
FIRST_RED = EVIDENCE / "c2.2-link46-l65e-transient-wplto-receipt.json"
ABI_REPORT = REPLAY / "c2-assembler-leaf-abi-derived-replay.json"
TRANSIENT_REPORT = REPLAY / "transient-execution-lookup-replay.json"
RECEIPT = EVIDENCE / (
    "c2.2-link46-l65e-transient-wplto-artifact-replay-receipt.json")

PINS = {
    INTERNAL: "3bcd31032fe6d636a1fc2bebc4864028203308501206ef51d1c992dd1c702e48",
    FIRST_RED: "7a78c5af44cc2b3b1a912ce22b767a05cae3dbaffacb69243830aa0483874a6f",
    PRODUCT: "917678d7329b24409178bff92097b11f701736a27c3af5248306d038db9f3ce4",
    ELF: "a37c9bfe45298b44b41327572b5ac89834723c826b4dfbdfc3f5c90fb18cb6ed",
    MAP: "b29f894823284bcceb0735f98c97e17e28a42b105402bc9d61d162da502164ca",
}


class ReplayError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def runtime_sizes(elf: Path) -> dict[str, int]:
    sections = LINK44.P.section_table(elf)
    return {name: row["bytes"] for name, row in sections.items()
            if name.startswith(".lisp65_rt_")
            and not name.startswith(".rela")}


def walls() -> dict[str, int]:
    sections = LINK44.P.section_table(ELF)
    text, bss = sections[".text"], sections[".bss"]
    # $C335 is linker-owned hot-BSS end and $C356 the fixed overlay VMA.
    fixed_end = 0xc335
    overlay_vma = 0xc356
    e000_bytes = sum(row["bytes"] for row in sections.values()
                     if 0xe000 <= row["address"] < 0x10000)
    result = {
        "bank0_text_headroom_bytes":
            LINK44.P.HANDOFF_BASE - text["address"] - text["bytes"],
        "ordinary_bank0_bss_headroom_bytes":
            LINK44.P.FIXED_BANK0_BASE - bss["address"] - bss["bytes"],
        "fixed_hot_block_headroom_bytes": overlay_vma - fixed_end,
        "resident_island_headroom_bytes": 2048 - sum(
            sections.get(name, {}).get("bytes", 0) for name in
            (".lisp65_resident_island", ".lisp65_resident_island_annex")),
        "e000_headroom_bytes": 8192 - e000_bytes,
    }
    require(all(value >= 0 for value in result.values())
            and result["e000_headroom_bytes"] >= 115,
            f"artifact wall red: {result}")
    return result


def main() -> int:
    try:
        require(not RECEIPT.exists(), "artifact replay is one-shot")
        for path, digest in PINS.items():
            require(path.is_file() and sha(path) == digest,
                    f"immutable WPLTO artifact drift: {path}")
        internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
        require(internal["diagnostic"] == {
                    "type": "GateError",
                    "message":
                        "runtime-overlay dispatcher has no unique final indirect edge"},
                "artifact replay does not follow the qualified gate-model Red")

        abi = ABI.audit_elf(ELF)
        transient_source = TRANSIENT.source_gate(
            generated_runtime=WPLTO / "generated-product-sources/c2_product_runtime.c",
            generated_hot=WPLTO / "generated-product-sources/c2_hot_literal.c")
        transient_linked = TRANSIENT.linked_gate(ELF)
        renderer = ORDINAL.linked_gate(ELF)
        stored_abi = json.loads(ABI_REPORT.read_text(encoding="utf-8"))
        stored_transient = json.loads(
            TRANSIENT_REPORT.read_text(encoding="utf-8"))
        require(abi["status"] == stored_abi["status"] ==
                    "passed-all-assembler-leaf-abi-contracts"
                and abi["ELF_derived_C_called_inventory"]
                    ["unclassified_C_called_functions"] == []
                and abi["l65e_runtime_overlay_entry"]["dispatcher"]
                    ["indirect_call_count"] == 2,
                "corrected ELF-derived ABI replay red")
        require(stored_transient["source"]["status"] ==
                    transient_source["status"]
                and stored_transient["linked"]["status"] ==
                    transient_linked["status"],
                "callable transient high-edge replay red")

        before, after = runtime_sizes(BASE_ELF), runtime_sizes(ELF)
        changed = {name: {"before": before.get(name),
                          "after": after.get(name)}
                   for name in sorted(set(before) | set(after))
                   if before.get(name) != after.get(name)}
        require(changed == {
                    ".lisp65_rt_l65e": {"before": 1139, "after": 1137}},
                f"unexpected runtime-family payload drift: {changed}")
        # Both sizes occupy five 256-byte pack quanta.  No catalog record or
        # other runtime section changed, so Link 46's measured aggregate is
        # preserved exactly rather than re-projected from a stale spec list.
        require((1139 + 255) // 256 == (1137 + 255) // 256,
                "L65E reduction changed its pack-quantum debit")
        capacity = {"status": "passed-pack-identical-to-Link46",
                    "session_family_bytes": 65438,
                    "session_family_headroom_bytes": 98,
                    "runtime_section_delta": changed}
        wall_values = walls()

        gate_evidence = {}
        for name in (
                "c2-crc-codegen-gate.json",
                "c2-crc-asm-leaf-gate.json",
                "final-section-inventory-lisp65-c2-substitution-linked.prg.json",
                "exact-orphan-wrapper-lisp65-c2-substitution-linked.prg.json"):
            path = WPLTO / name
            data = json.loads(path.read_text(encoding="utf-8"))
            require(str(data.get("status", "")).startswith("pass"),
                    f"pre-ABI WPLTO gate was not green: {name}")
            gate_evidence[name] = bind(path)

        value = {
            "format": "lisp65-c2-lite-v6-link46-l65e-transient-artifact-replay-v1",
            "recorded_on": "2026-07-22",
            "status": "passed-pure-artifact-replay-no-compiler-no-link-no-hardware",
            "promotable": False,
            "authority": {"wplto_first_red": bind(FIRST_RED),
                          "wplto_internal": bind(INTERNAL),
                          "immutable_product_shaped_elf": bind(ELF),
                          "immutable_product_shaped_product": bind(PRODUCT),
                          "rollback_link46_elf": bind(BASE_ELF)},
            "gate_model_correction": {
                "old_model": "exactly one __call_indir edge",
                "actual_model": (
                    "every final __call_indir edge in the dispatcher must "
                    "establish target __rc18/__rc19 and context __rc2/__rc3"),
                "observed_indirect_edges": 2,
                "product_bytes_changed_by_replay": 0},
            "assembler_leaf_abi": abi,
            "assembler_leaf_abi_report": bind(ABI_REPORT),
            "transient_execution_lookup": {
                "source": transient_source, "linked": transient_linked},
            "transient_execution_report": bind(TRANSIENT_REPORT),
            "l65e_renderer": renderer,
            "walls": wall_values,
            "capacity": capacity,
            "pre_abi_wplto_gate_evidence": gate_evidence,
            "source_delta": {
                "l65e_entry_bytes": -2,
                "explanation": (
                    "LDA __rc2 replaces the first destructive store before "
                    "ORA __rc3; the safe entry therefore shrinks 2 B, not 4 B.")},
            "execution_accounting": {
                "replay_compiler_processes": 0,
                "replay_linker_processes": 0,
                "promotable_product_links": 0,
                "hardware_runs": 0},
            "counters": {"line1_product_first_reds": "2/3",
                         "completed_latency_measurements": "0/2"},
            "claim_limit": (
                "Pure replay of the one nonpromotable WPLTO identity. A "
                "successor product link requires separate Class-C approval."),
            "next_gate": "separate Class-C successor product-link review",
        }
        RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        os.chmod(RECEIPT, 0o444)
        os.chmod(REPLAY, 0o555)
        print("c2-lite-v6-link46-l65e-transient-artifact-replay: PASS "
              f"text={wall_values['bank0_text_headroom_bytes']} "
              f"island={wall_values['resident_island_headroom_bytes']} "
              f"e000={wall_values['e000_headroom_bytes']} "
              "session=65438 compiler=0 linker=0 hardware=0")
        return 0
    except (ReplayError, ABI.GateError, TRANSIENT.GateError, OSError,
            RuntimeError, ValueError, KeyError) as error:
        print("c2-lite-v6-link46-l65e-transient-artifact-replay: FAIL: "
              + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
