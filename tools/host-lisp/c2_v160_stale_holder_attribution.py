#!/usr/bin/env python3
"""Attribute every observable holder of the retired v1.6 RTOV window."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from elf_truth import ElfTruth


ROOT = Path(__file__).resolve().parents[2]
ELF = ROOT / ("build/c2.3/v1.6-hybrid-live-stack-replacement-card-r1/"
              "wplto/lisp65-c2-substitution-linked.prg.elf")
CAPTURE = ROOT / ("build/c2.3/v1.6-items12-hybrid-owner-contact/"
                  "hybrid-entry-first-red-stopped-state/capture.json")
RESULT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                 "c2.3-v1.6-overlay-view-device-result-receipt.json")
OUT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
              "c2.3-v1.6-stale-holder-attribution-receipt.json")
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
COMMISSION = "a6f0038bec6005d1436204742cd48a83b21425d8"
EXPECTED = {
    "ELF": "a03f9fafc5629f913dcf213925d7f007fd91b353ab2229a6189080c37f604c9c",
    "capture": "73827d43bb82102b434bd81a92bc2ce216bf9c3c5b67cc85b3b9b29a89188992",
}
WINDOW = (0xC356, 0xCA92)


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


def authority() -> dict[str, Any]:
    name = "docs/planning/v1.6.0-freight-work-plan.md"
    raw = subprocess.run(["git", "show", f"{COMMISSION}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    for token in (b"Stale-holder attribution commissioned",
                  b"decode the preserved stack against ElfTruth",
                  b"No card, no media, no device contact"):
        require(token in raw, f"commission token absent: {token!r}")
    return {"authority": "git-blob", "commit": COMMISSION, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"check", "write"},
            "usage: c2_v160_stale_holder_attribution.py check|write")
    inputs = {"ELF": bind(ELF), "capture": bind(CAPTURE),
              "device_result": bind(RESULT)}
    require({k: inputs[k]["sha256"] for k in EXPECTED} == EXPECTED,
            "frozen input identity drift")
    result = json.loads(RESULT.read_text())
    require(result["status"] == "SELECTED-STALE-CONTROL-AFTER-WIPE",
            "device decision drift")
    capture = json.loads(CAPTURE.read_text())
    rows = {r["name"]: bytes.fromhex(r["observed_hex"])
            for r in capture["reads"]}
    bank0 = rows["bank0-zp-stack"]
    require(len(bank0) == 512 and capture["tuple"]["SP"] == "0x01c5",
            "stack evidence drift")
    truth = ElfTruth.read(ELF, llvm_readobj=LLVM_READOBJ,
                          include_section_data=True)

    # Adjacent native-stack words whose successor is immediately after an
    # emitted JSR.  These are the mechanically defensible frames; arbitrary
    # adjacent byte pairs are deliberately not promoted to return records.
    frames = [
        (0x01CF, 0x2E8E, "lisp_abort_symbol", "c2_product_abort_cleanup"),
        (0x01D1, 0x8F24, "vm_check_status", "lisp_abort_code"),
        (0x01D5, 0x8FF5, "eval_vm_native_apply_checked", "vm_check_status"),
        (0x01DB, 0xA1D7, "eval", "eval_vm_native_apply_checked"),
        (0x01DF, 0xAC04, "repl", "eval"),
        (0x01E5, 0xA70B, "main", "repl"),
    ]
    decoded = []
    for address, raw_return, caller, callee in frames:
        observed = int.from_bytes(bank0[address:address + 2], "little")
        require(observed == raw_return, f"stack frame drift at {address:#x}")
        require(truth.symbol(caller).value <= raw_return + 1
                < truth.symbol(caller).value + truth.symbol(caller).bytes,
                f"stack caller ownership drift: {caller}")
        decoded.append({"stack_address": f"0x{address:04x}",
                        "raw_jsr_return": f"0x{raw_return:04x}",
                        "resume": f"0x{raw_return + 1:04x}",
                        "caller": caller, "callee": callee})

    frame = bank0[0x1C6:0x1CD]
    require(frame == bytes.fromhex("00c7000032b8c5"), "BRK frame drift")
    stack_window_pairs = []
    for address in range(0x1CD, 0x1FF):
        value = int.from_bytes(bank0[address:address + 2], "little")
        if WINDOW[0] <= value < WINDOW[1]:
            stack_window_pairs.append((address, value))
    require(stack_window_pairs == [], "unexpected pre-BRK window pair appeared")

    require(bank0[0x38] == 0x26 and bank0[0x5F] == 0x03,
            "VM type-error carrier drift")
    require(bank0[0x74:0x76] == bytes.fromhex("9bcf")
            and bank0[0x14:0x16] == bytes.fromhex("56c3"),
            "cached RTOV context/entry drift")

    # Static linked references to the non-boundary site would be a separate
    # published holder.  Relocations are authoritative; raw byte coincidences
    # in relocation tables are not references.
    direct_site = [r for r in truth.relocations
                   if r.target in {"buf_from_string",
                                   "lisp65_buffer_overlay_alloc_entry"}]
    to_owner = [r for r in direct_site if r.target == "buf_from_string"]
    to_entry = [r for r in direct_site
                if r.target == "lisp65_buffer_overlay_alloc_entry"]
    require(len(to_owner) == 1 and to_owner[0].source_section ==
            ".lisp65_rt_buffer_alloc" and not to_entry,
            "linked overlay holder set drift")

    output = {
        "format": "lisp65-c2.3-v1.6-stale-holder-attribution-v1",
        "status": "NARROWED-DYNAMIC-HOLDER-NOT-CAPTURED",
        "recorded_on": "2026-08-20",
        "authority": authority(), "inputs": inputs,
        "stack_main_witness": {
            "saved_frame_hex": frame.hex(), "stacked_P": "0x32",
            "BRK_opcode": "0xc5b6", "BRK_continuation": "0xc5b8",
            "important_distinction": ("$c5b8 belongs to the BRK frame created "
                "after the stale transfer; it is not a pre-wipe return holder"),
            "decoded_jsr_chain_inner_to_outer": decoded,
            "error_carrier": {"pending_code": "0x26 (VM type error)",
                              "vm_status": "0x03 (VM_TYPE)"},
            "pre_BRK_adjacent_words_in_window": [],
            "conclusion": ("the captured native stack proves the abort/wipe "
                "chain but contains no defensible pre-retirement return address "
                "into $c356..$ca91")},
        "retirement_path": {
            "normal_slice_exit": ["indirect call through __call_indir",
                                  "store entry result",
                                  "rtov_wipe at $2dd9",
                                  "clear rtov_busy at $2ddf"],
            "error_path_at_stop": ["vm_check_status observes VM_TYPE",
                                   "lisp_abort_code / lisp_abort_symbol",
                                   "c2_product_abort_cleanup",
                                   "vm_runtime_overlay_abort_cleanup -> rtov_wipe"],
            "captured_lifecycle": "busy=0, loaded_len=0, target all zero",
            "violated_rule": ("no control target in a runtime-overlay VMA may "
                "remain usable after rtov_wipe retires that generation"),
        },
        "holder_enumeration": [
            {"class": "native stack return addresses", "result": "excluded in captured bytes",
             "evidence": "six exact JSR frames decoded; no adjacent post-frame word lies in the window"},
            {"class": "linked/published static cells", "result": "no static bypass",
             "evidence": "one relocation to buf_from_string, internal to its own slice; zero relocations to the public entry"},
            {"class": "hardware vectors", "result": "excluded as holder of $c5b6",
             "evidence": "terminal vector entered resident $e038; stacked B=1 identifies BRK, not a vector to the window"},
            {"class": "setjmp continuation record at $bd47", "result": "not captured; statically bounded",
             "evidence": "setjmp is called at $aa5e and its legal resume is $aa61, outside the window; live 19-byte record was not in the authorized ranges"},
            {"class": "RTOV cached direct target/context", "result": "captured target is slice base, not fault site",
             "evidence": "__rc18/__rc19=$c356; rtov_call_context=$cf9b; neither is $c5b6"},
            {"class": "heap/VM continuation or dynamically published cell", "result": "not captured",
             "evidence": "authorized row contains Bank 0/ZP/stack, input ring and fixed state, not heap or VM continuation storage"},
        ],
        "decision": {
            "selected": "retirement/liveness violation remains the mechanism class",
            "named_holder": None,
            "why_not_named": ("the only in-window word in evidence is the post-transfer BRK continuation; "
                "the dynamic heap/continuation stores needed to distinguish the residual holders were not read"),
            "claim_correction": ("the frozen stack does not contain the commissioned pre-wipe return witness; "
                "claiming one would misclassify the BRK frame"),
        },
        "mechanism_boundary": ("Host-only evidence names the retirement path and excludes native-stack, static-link, "
            "vector, setjmp and captured RTOV-cache holders, but cannot distinguish an uncaptured VM/heap continuation "
            "from a dynamic publication. No fix may be derived from this receipt."),
        "claim_limit": "No product change, card, link, medium, or device contact.",
    }
    encoded = json.dumps(output, indent=2, sort_keys=True) + "\n"
    if sys.argv[1] == "write":
        OUT.write_text(encoded, encoding="utf-8")
    else:
        require(OUT.is_file() and OUT.read_text() == encoded,
                "stale-holder attribution receipt absent or stale")
    print("v1.6 stale-holder attribution: PASS boundary=dynamic-holder-not-captured")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"v1.6 stale-holder attribution: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
