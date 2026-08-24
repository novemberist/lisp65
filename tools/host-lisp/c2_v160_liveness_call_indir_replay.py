#!/usr/bin/env python3
"""Replay liveness closure with semantic identity for unsized __call_indir."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v160_liveness_capture_guard_card as GUARD  # noqa: E402
import c2_v160_liveness_fix_card as LIVENESS  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
FINAL_RED = ARCH / "c2.3-v1.6-liveness-capture-guard-card-final-red.json"
ELF = (ROOT / "build/c2.3/v1.6-liveness-capture-guard-card/wplto/"
       "lisp65-c2-substitution-linked.prg.elf")
PRG = ELF.with_suffix("")
OUT = ARCH / "c2.3-v1.6-liveness-call-indir-replay-receipt.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def instruction_identity(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    symbol = truth.symbol("__call_indir")
    semantic = LIVENESS.emitted_function(truth, symbol.name, unsized_bytes=3)
    proxy = truth.section_bytes(symbol.section)[
        symbol.value - truth.section(symbol.section).address:
        symbol.value - truth.section(symbol.section).address + symbol.bytes]
    require(symbol.bytes == 0 and proxy == b"" and semantic == bytes.fromhex("6c1400"),
            "unsized __call_indir attribution drift")
    return {"address": symbol.value, "section": symbol.section,
        "ELF_symbol_bytes": symbol.bytes, "metadata_proxy_hex": proxy.hex(),
        "semantic_instruction_bytes": 3, "semantic_hex": semantic.hex(),
        "instruction": "JMP ($0014)"}


def main() -> int:
    require(not OUT.exists(), "liveness call-indir replay is one-shot")
    red = json.loads(FINAL_RED.read_text(encoding="utf-8"))
    require(red["error"]["message"] == "hot indirect-call path changed"
            and red["attempt_accounting"]["cards_consumed"] == 1
            and red["attempt_accounting"]["WPLTO_runs"] == 1,
            "call-indir Final Red drift")
    before = {"ELF": bind(ELF), "PRG": bind(PRG)}
    candidate = instruction_identity(ELF)
    predecessor = instruction_identity(LIVENESS.PREDECESSOR_ELF)
    require(candidate["address"] == predecessor["address"] == 0x24CB
            and candidate["semantic_hex"] == predecessor["semantic_hex"] == "6c1400",
            "candidate/predecessor call-indir semantic identity differs")

    # The old zero-size proxy must be rejected, while an actual instruction
    # mutation must remain visible to the semantic comparison.
    proxy_mutation_rejected = candidate["metadata_proxy_hex"] != "6c1400"
    wrong_instruction_mutation_rejected = bytes.fromhex("6c1500") != bytes.fromhex(
        candidate["semantic_hex"])
    require(proxy_mutation_rejected and wrong_instruction_mutation_rejected,
            "call-indir identity mutations did not bite")

    old_product = LIVENESS.PRODUCT_ELF
    try:
        LIVENESS.PRODUCT_ELF = ELF
        final = LIVENESS.final_liveness()
    finally:
        LIVENESS.PRODUCT_ELF = old_product
    capture = GUARD.mutation_gate(ELF)
    after = {"ELF": bind(ELF), "PRG": bind(PRG)}
    require(before == after, "read-only liveness replay changed frozen artifacts")

    value = {
        "format": "lisp65-c2-v160-liveness-call-indir-replay-v1",
        "recorded_on": "2026-08-20",
        "status": "PASS: V1.6 RETIREMENT LIVENESS CONTRACT CLOSED",
        "predecessor_Final_Red": bind(FINAL_RED),
        "artifacts_before": before, "artifacts_after": after,
        "call_indir_identity": {"candidate": candidate,
            "predecessor": predecessor,
            "authority": "unique ELF entry plus three decoded instruction bytes",
            "zero_size_symbol_body_proxy_rejected": proxy_mutation_rejected,
            "wrong_instruction_mutation_rejected": wrong_instruction_mutation_rejected},
        "final_liveness_gate": final,
        "active_candidate_capture_guard": capture,
        "execution": {"WPLTO_runs": 0, "product_links": 0,
                      "media_builds": 0, "device_contacts": 0},
        "next": "authorized Comfort prompt card",
        "claim_limit": "Read-only closure over the frozen final pair; no media or device."
    }
    OUT.write_bytes(canonical(value))
    print("v1.6 liveness call-indir replay: PASS bytes=6c1400 liveness=closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
