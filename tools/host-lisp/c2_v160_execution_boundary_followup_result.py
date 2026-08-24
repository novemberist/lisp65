#!/usr/bin/env python3
"""Bind the Low-RAM follow-up and expose its two trace-equivalent histories."""

from __future__ import annotations

import argparse
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


ELF = ROOT / (
    "build/c2.3/v1.6-execution-boundary-backstop-uint8-irq-return-"
    "replacement-card/wplto/lisp65-c2-substitution-linked.prg.elf")
FIRST = ROOT / "build/c2.3/v1.6-execution-boundary-first-red/capture.json"
FOLLOWUP = ROOT / (
    "build/c2.3/v1.6-execution-boundary-followup-read-20260824/capture.json")
PRECEDING = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-execution-boundary-first-red-attribution.json")
OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-execution-boundary-followup-result.json")
FORMAT = "lisp65-c2.3-v1.6-execution-boundary-followup-result-v1"
EXPECTED = {
    "ELF": "c8b74690e682370f14c68bc837cd9642b702df024e71c82753b0b21d678fd10d",
    "first_red": "334e67a7a4ecd746c381fc38751607c916d35b100390ddba5abdbe20c14c94d4",
    "followup": "84ba73069944f131a2c547a9c788f417b0cbac2b7081163a59754c3c3623aeda",
    "preceding_attribution": "407c7c9968167645f3269040a9575518cc512322c59829a62dfadf9767dd973f",
}


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def capture_rows(value: dict[str, Any]) -> dict[str, bytes]:
    return {row["name"]: bytes.fromhex(row["observed_hex"])
            for row in value["reads"]}


def u16(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset:offset + 2], "little")


def derive() -> dict[str, Any]:
    inputs = {"ELF": bind(ELF), "first_red": bind(FIRST),
              "followup": bind(FOLLOWUP),
              "preceding_attribution": bind(PRECEDING)}
    require({name: inputs[name]["sha256"] for name in EXPECTED} == EXPECTED,
            "execution-boundary follow-up identity drift")
    first = load(FIRST); followup = load(FOLLOWUP); preceding = load(PRECEDING)
    require(first["tuple"] == followup["tuple"]
            and first["discipline"] == followup["discipline"]
            and followup["discipline"] == {
                "CPU_left_stopped": True, "D2_D5_executed": False,
                "raw_first": True, "resets": 0, "resumes": 0, "runs": 0,
                "stops": 1, "tuple_before_memory": True,
            }, "original stopped state was not conserved")
    rows = capture_rows(followup)
    require({name: len(raw) for name, raw in rows.items()} == {
        "current-lisp-toplevel-jmp-buf": 19,
        "vm-codebuf-and-bookkeeping": 75,
        "low-ram-brk-neighborhood": 16,
        "IRQ-episode-state": 11,
    }, "follow-up extent drift")

    jmp = rows["current-lisp-toplevel-jmp-buf"]
    vm = rows["vm-codebuf-and-bookkeeping"]
    low = rows["low-ram-brk-neighborhood"]
    irq = rows["IRQ-episode-state"]
    require(jmp.hex() == "53aadececf56c3d0cf003901010904d3005602",
            "current jmp_buf bytes drift")
    require(u16(jmp, 5) == 0xC356, "saved __rc18/__rc19 is not the retired entry")
    require(vm == bytes(75), "VM code window/bookkeeping is not fully retired")
    require(low.hex() == "800000c00000e00000f00000f80000fc",
            "Low-RAM instruction/data bytes drift")
    require(irq == bytes.fromhex("db040001010400000000ff"),
            "IRQ episode state drift")

    truth = ElfTruth.read(
        ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    identities = {name: truth.symbol(name).value for name in (
        "lisp_toplevel", "retired_window_resume", "longjmp", "__call_indir",
        "c2_retired_continuation_stub", "c2_rtov_retire_continuations")}
    require(identities == {
        "lisp_toplevel": 0xBD49, "retired_window_resume": 0x2269,
        "longjmp": 0x259B, "__call_indir": 0x2606,
        "c2_retired_continuation_stub": 0xB411,
        "c2_rtov_retire_continuations": 0x7E2E,
    }, "current recovery identity drift")
    text = truth.section(".text"); text_raw = truth.section_bytes(".text")
    code = lambda first, last: text_raw[first - text.address:last - text.address]
    resume = code(0x2269, 0x2286)
    longjmp = code(0x259B, 0x2606)
    require(resume.hex() == (
        "a536d00aa93e85369ce9b99ceab9a9498504a9bd8505a901a2004c9b25"),
        "retired-window resume bytes drift")
    require(bytes.fromhex("b104851588b1048514") in longjmp,
            "longjmp saved __rc19/__rc18 restore drift")
    require(code(0x2606, 0x2609) == bytes.fromhex("6c1400"),
            "indirect consumer identity drift")

    # The first capture proves Y=$bf and pushed P=$b1 at the BRK.  Executing
    # CPY #$00 at $0603 with Y=$bf produces N=1,Z=0,C=1; BRK adds the pushed B
    # bit, exactly $b1.  Thus $0603 was executed immediately before $0605.
    first_rows = capture_rows(first)
    stack = first_rows["bank0-zp-stack"]
    require(stack[0x1CB] == 0xBF and stack[0x1CE] == 0xB1
            and low[3:6] == bytes.fromhex("c00000"),
            "immediate pre-BRK instruction proof drift")
    require(irq[3] == 1, "source-less history byte was not one")

    # Both paths below produce the exact observed terminal tuple and bytes.
    # No existing state byte records whether the classifier accepted before
    # this frame, so the commissioned read cannot select between them.
    histories = [
        {
            "name": "independent-low-RAM-entry",
            "steps": ["control enters $0601", "BRK $0601 sets source-less=1",
                      "RTI continues at $0603", "CPY #$00", "BRK $0605",
                      "classifier rejects continuation $0607"],
        },
        {
            "name": "prior-source-less-then-low-RAM-entry",
            "steps": ["an earlier source-less episode leaves source-less=1",
                      "control enters $0603", "CPY #$00", "BRK $0605",
                      "classifier rejects continuation $0607"],
            "retired_window_acceptance": "possible member, not recorded",
        },
    ]

    return {
        "format": FORMAT,
        "status": "PROVEN: BACKSTOP RECOVERY SELF-REARMS STALE CSR; CURRENT HISTORY AMBIGUOUS",
        "recorded_on": "2026-08-24", "inputs": inputs,
        "contact": {"kind": "authorized read of original conserved stop",
                    "stops": 1, "resumes": 0, "runs": 0, "resets": 0,
                    "bytes_read": 121, "CPU_left_stopped": True},
        "observed": {
            "jmp_buf": jmp.hex(), "saved___rc18___rc19": "0xc356",
            "neutral_target_expected_after_sanitization": "0xb411",
            "vm_codebuf_and_bookkeeping": "75/75 zero",
            "low_RAM_0600_060f": low.hex(),
            "IRQ_episode": {"frame": 0x04DB, "source_less": irq[3],
                            "MAP_generation": irq[4], "state": irq[5],
                            "unowned_VIC": irq[6], "break_pending": irq[7],
                            "break_held": irq[8], "ring_head": irq[9],
                            "ring_tail": irq[10]},
        },
        "low_RAM_execution": {
            "proven_instruction": "$0603: CPY #$00",
            "following_instruction": "$0605: BRK",
            "Y": "0xbf", "pushed_P": "0xb1",
            "flag_match": "N=1, Z=0, C=1 plus BRK's pushed B bit",
            "meaning": "control entered dynamic Low RAM no later than $0603",
        },
        "history_decision": {
            "commissioned_binary_question_decided": False,
            "trace_equivalent_histories": histories,
            "missing_instrument": ("no byte records an accepted retired-window continuation "
                                   "or the first source-less PC"),
            "correction": ("$ff86 is current episode state, not history; the specified read "
                           "was therefore insufficient to select the causal path"),
        },
        "static_product_finding": {
            "class": "recovery restores the carrier it is meant to contain",
            "proof": [
                "current lisp_toplevel offsets 5/6 contain $c356",
                "retired_window_resume tail-jumps directly to longjmp(lisp_toplevel)",
                "longjmp restores offsets 6/5 to __rc19/__rc18",
                "there is no continuation sanitizer on that recovery edge",
            ],
            "consequence": ("Whenever the backstop accepts this stale-jmp_buf member, its "
                            "recovery deterministically restores $c356 into the live ABI pair. "
                            "The boundary catches the first dead-window execution but does not "
                            "make the recovery state safe."),
            "caused_this_exact_0603_transfer": "not proven",
            "required_contract": ("Before longjmp on the accepted boundary path, the target "
                                  "continuation must contain no in-generation saved CSR pair; "
                                  "recovery may not restore its triggering carrier."),
        },
        "claim_limit": ("Proves the recovery self-rearm defect independently of the exact Low-"
                        "RAM causal history. It authorizes no fix, build, medium, resume or "
                        "additional device contact."),
    }


def selftest() -> None:
    value = derive()
    mutations = [
        ("observed", "saved___rc18___rc19", "0xb411"),
        ("history_decision", "commissioned_binary_question_decided", True),
        ("static_product_finding", "caused_this_exact_0603_transfer", "proven"),
    ]
    for first, second, replacement in mutations:
        clone = json.loads(json.dumps(value)); clone[first][second] = replacement
        accepted = (clone["observed"]["saved___rc18___rc19"] == "0xc356"
                    and clone["history_decision"]["commissioned_binary_question_decided"] is False
                    and clone["static_product_finding"]["caused_this_exact_0603_transfer"]
                    == "not proven")
        require(not accepted, "follow-up result mutation accepted")
    print(f"v1.6 execution-boundary follow-up result: SELFTEST PASS "
          f"mutations={len(mutations)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    if action == "selftest":
        selftest(); return 0
    value = derive(); encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if action == "write":
        OUT.write_text(encoded, encoding="utf-8")
    else:
        require(OUT.is_file() and OUT.read_text(encoding="utf-8") == encoded,
                "execution-boundary follow-up result drift")
    print("v1.6 execution-boundary follow-up result: PASS "
          "self-rearm=proven history=ambiguous")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResultError, OSError, ValueError, KeyError) as error:
        print(f"v1.6 execution-boundary follow-up result: FAIL: {error}",
              file=sys.stderr)
        raise SystemExit(1)
