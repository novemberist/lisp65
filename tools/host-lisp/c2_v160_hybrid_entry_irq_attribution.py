#!/usr/bin/env python3
"""Attribute the v1.6 Hybrid-entry red from the frozen stopped-state row."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from elf_truth import ElfTruth


ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / (
    "build/c2.3/v1.6-items12-hybrid-owner-contact/"
    "hybrid-entry-first-red-stopped-state/capture.json")
ELF = ROOT / (
    "build/c2.3/v1.6-hybrid-live-stack-replacement-card-r1/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
SOURCE = ROOT / "src/optional/c2_kernal_input_capture.s"
CORE_AUTHORITY = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-post-v1.4-defstruct-irq-origin-desk-attribution-receipt.json")
OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-hybrid-entry-brk-attribution-receipt.json")
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
COMMISSION = "73163f2dc8c881b38e93d2ab0724f702f6243d8e"
EXPECTED = {
    "capture": "73827d43bb82102b434bd81a92bc2ce216bf9c3c5b67cc85b3b9b29a89188992",
    "ELF": "a03f9fafc5629f913dcf213925d7f007fd91b353ab2229a6189080c37f604c9c",
}


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def historical_plan() -> dict[str, Any]:
    name = "docs/planning/v1.6.0-freight-work-plan.md"
    raw = subprocess.run(["git", "show", f"{COMMISSION}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    for token in (b"IRQ acknowledge-choreography attribution commissioned",
                  b"host-only attribution", b"no further contact"):
        require(token in raw, f"commission token absent: {token!r}")
    return {"authority": "git-blob", "commit": COMMISSION, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def read_capture() -> tuple[dict[str, Any], dict[str, bytes]]:
    document = json.loads(CAPTURE.read_text(encoding="utf-8"))
    rows = {row["name"]: bytes.fromhex(row["observed_hex"])
            for row in document["reads"]}
    require(set(rows) == {"bank0-zp-stack", "gc-runs", "input-ring",
                          "c2-fixed-state"}, "capture range set drift")
    require(document["discipline"] == {
        "CPU_left_stopped": True, "D2_D5_executed": False,
        "raw_first": True, "resets": 0, "resumes": 0, "runs": 0,
        "stops": 1, "tuple_before_memory": True,
    }, "capture discipline drift")
    return document, rows


def symbol_bytes(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    raw = truth.section_bytes(section.name)
    offset = symbol.value - section.address
    require(symbol.bytes > 0 and 0 <= offset <= len(raw) - symbol.bytes,
            f"symbol bytes unavailable: {name}")
    return raw[offset:offset + symbol.bytes]


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"check", "write"},
            "usage: c2_v160_hybrid_entry_irq_attribution.py check|write")
    identities = {"capture": bind(CAPTURE), "ELF": bind(ELF)}
    require({name: row["sha256"] for name, row in identities.items()} == EXPECTED,
            "attribution evidence identity drift")
    capture, rows = read_capture()
    truth = ElfTruth.read(ELF, llvm_readobj=LLVM_READOBJ,
                          include_section_data=True)
    fixed = rows["c2-fixed-state"]
    bank0 = rows["bank0-zp-stack"]
    ring = rows["input-ring"]
    tuple_ = capture["tuple"]
    require(tuple_["PC"].lower() == "0xe096"
            and tuple_["MAPL"].lower() == "0x0000",
            "terminal PC/MAP tuple drift")
    sp = int(tuple_["SP"], 0) & 0xff
    frame = bank0[0x100 + sp + 1:0x100 + sp + 8]
    require(frame == bytes.fromhex("00c7000032b8c5"),
            f"saved handler/hardware frame drift: {frame.hex()}")
    stacked_p = frame[4]
    return_pc = frame[5] | frame[6] << 8
    require(stacked_p & 0x10 and return_pc == 0xc5b8,
            "terminal frame is not the captured B=1 continuation")

    core = json.loads(CORE_AUTHORITY.read_text(encoding="utf-8"))
    semantic = core["authorities"]["tested_core_CPU"]["semantic_result"]
    require(semantic == ("hardware IRQ stacks B=0 and the resume PC; BRK stacks "
                         "B=1 and the PC two bytes after opcode $00"),
            "tested-core IRQ/BRK discriminator drift")

    irq = truth.section_bytes(".lisp65_c2_kernal_window.irq_handler")
    fail = truth.symbol("c2_kernal_fail_closed")
    capture_symbol = truth.symbol("c2_kernal_input_capture")
    require(len(irq) == 74 and irq.startswith(bytes.fromhex("48da5adba300ad19d0")),
            "emitted Hybrid IRQ entry drift")
    ack = bytes.fromhex("8d19d0")
    call = bytes((0x20, capture_symbol.value & 0xff,
                  capture_symbol.value >> 8))
    classify = bytes.fromhex("ad19d02901f028")
    require(irq.count(classify) == 1 and irq.count(ack) == 1
            and irq.count(call) == 1
            and irq.index(classify) < irq.index(ack) < irq.index(call),
            "emitted classify/ack/capture order drift")
    capture_body = symbol_bytes(truth, "c2_kernal_input_capture")
    require(capture_body.startswith(bytes.fromhex("9c86ff"))
            and bytes.fromhex("8d19d0") not in capture_body,
            "capture body latch/D019 contract drift")
    fail_raw = truth.section_bytes(
        ".lisp65_c2_kernal_window.map_switch_and_guards")
    require(fail.value == 0xe08b
            and fail_raw == bytes.fromhex("78a9008d1ad0a9028d20d04c96e0"),
            "fail-closed identity drift")

    buffer = truth.symbol("buf_from_string")
    buffer_raw = symbol_bytes(truth, "buf_from_string")
    brk_pc = return_pc - 2
    buffer_offset = brk_pc - buffer.value
    require(buffer.value == 0xc5af and 0 <= buffer_offset < len(buffer_raw),
            "BRK continuation is outside candidate buf_from_string")
    candidate_byte = buffer_raw[buffer_offset]
    require(candidate_byte == 0x02,
            "candidate byte at captured BRK site is no longer $02")

    require(fixed[6] == 1 and fixed[9] == 0
            and fixed[12] == fixed[13] == 0,
            "fixed-state latch/witness/ring cursors drift")
    require(rows["gc-runs"] == bytes.fromhex("0300")
            and bank0[0x8f] == 0 and tuple_["MAPL"].lower() == "0x0000",
            "GC/OOM/MAP exclusion drift")

    result = {
        "format": "lisp65-c2.3-v1.6-hybrid-entry-brk-attribution-v1",
        "status": "ATTRIBUTED-BRK-NOT-IRQ",
        "recorded_on": "2026-08-20",
        "authority": historical_plan(),
        "inputs": {**identities, "source": bind(SOURCE),
                   "tested_core_authority": bind(CORE_AUTHORITY)},
        "stopped_state": {
            "PC": tuple_["PC"], "SP": tuple_["SP"],
            "MAPL": tuple_["MAPL"], "MAPH": tuple_["MAPH"],
            "saved_frame_hex": frame.hex(), "stacked_P": f"0x{stacked_p:02x}",
            "stacked_B": 1, "continuation_PC": f"0x{return_pc:04x}",
            "BRK_opcode_PC": f"0x{brk_pc:04x}",
            "C2K_SOURCELESS_IRQS": fixed[6],
            "C2K_UNOWNED_VIC": fixed[9],
            "ring_head": fixed[12], "ring_tail": fixed[13],
            "ring_logically_empty": fixed[12] == fixed[13],
            "ring_residue_sha256": sha(ring),
            "gc_runs": int.from_bytes(rows["gc-runs"], "little"),
            "mem_oom": bank0[0x8f],
        },
        "emitted_choreography": {
            "handler": "0xe038..0xe081",
            "order": ["read D019 and classify raster bit",
                      "acknowledge owned D019 raster bit",
                      "call capture/drain", "increment frame", "RTI"],
            "capture_entry": f"0x{capture_symbol.value:04x}",
            "capture_first_action": "STZ C2K_SOURCELESS_IRQS",
            "capture_writes_D019": False,
            "second_class_entry": "0xe06d",
            "terminal_edge": "0xe07a -> 0xe08b",
        },
        "candidate_world_at_continuation": {
            "intended_owner": "buf_from_string",
            "owner_start": f"0x{buffer.value:04x}",
            "candidate_byte_at_BRK_PC": f"0x{candidate_byte:02x}",
            "candidate_neighborhood_hex": buffer_raw[max(0, buffer_offset-3):
                                                       buffer_offset+4].hex(),
            "meaning": ("the tested core says B=1 makes $c5b8 the continuation "
                        "of opcode $00 at $c5b6; the candidate's intended "
                        "buf_from_string byte there is $02, so the executing "
                        "CPU view did not match that intended owner"),
        },
        "decision": {
            "acknowledge_order_defect": "excluded for the terminal entry",
            "owned_raster_misclassification": "excluded for the terminal entry",
            "genuine_second_hardware_IRQ_source": "excluded by stacked B=1",
            "selected": "software BRK in a CPU view inconsistent with candidate buf_from_string",
            "claim_correction": ("C2K_SOURCELESS_IRQS is a shared IRQ/BRK-class "
                                 "episode latch. Its value 1 did not prove that "
                                 "the terminal second entry was a hardware IRQ."),
        },
        "exonerated": ["input ring backlog", "Hybrid consumer", "rendering",
                       "GC", "OOM", "MAP residue", "IRQ acknowledge ordering as terminal cause"],
        "open_boundary": ("the frozen row did not read the live CPU-view bytes at "
                          "$c5b6; host evidence attributes BRK and candidate-view "
                          "mismatch, but does not yet name which overlay install or "
                          "control-transfer mechanism supplied the zero byte"),
        "claim_limit": ("Host-only attribution from frozen bytes. No product fix, "
                        "link, medium, resume, reset, or device contact."),
    }
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if sys.argv[1] == "write":
        OUT.write_text(encoded, encoding="utf-8")
    else:
        require(OUT.is_file() and OUT.read_text(encoding="utf-8") == encoded,
                "attribution receipt absent or stale")
    print("v1.6 Hybrid-entry IRQ attribution: PASS selected=BRK-not-IRQ")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"v1.6 Hybrid-entry IRQ attribution: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
