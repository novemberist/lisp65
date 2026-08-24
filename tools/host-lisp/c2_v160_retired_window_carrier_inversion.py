#!/usr/bin/env python3
"""Attribute the third stale-overlay carrier and price constructive recovery.

This is a host-only study.  ``write`` consumes the frozen device capture and
candidate ELF once and seals the result.  ``check`` validates the sealed
result and the executable price model without requiring private build output.
It never changes product sources, links a product, builds media, or contacts a
device.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
ELF = ROOT / ("build/c2.3/v1.6-bound-origin-fragmentation-second-"
              "replacement-card/wplto/lisp65-c2-substitution-linked.prg.elf")
CAPTURE = ROOT / ("build/c2.3/v1.6-bound-origin-fragmentation-device-contact/"
                  "misspelled-require-first-red-stopped-state/capture.json")
OUT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
              "c2.3-v1.6-retired-window-carrier-inversion-study.json")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
CLANG = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
AUTHORITY = "d4506df2"
FORMAT = "lisp65-c2.3-v1.6-retired-window-carrier-inversion-study-v1"
EXPECTED = {
    "ELF": "8bb00fd560ddfef9b4f1da5d6269e134de8dc6548a33e3659eb79fc580fecd45",
}

WINDOW_START = 0xC356
WINDOW_END = 0xCA91
E000_FLOOR = 54
E000_REQUIRED_FREE = 57


class StudyError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise StudyError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def git_authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORITY}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    compact = " ".join(raw.decode().lower().split())
    for token in ("third liveness instance", "exact carrier of `$c8b5`",
                  "inversion question", "retirement safe by construction",
                  "no card, no media, no contact"):
        require(token in compact, f"commission token absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def canonical(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def price_source() -> str:
    # The classifier is modelled at the source-less IRQ seam.  The two terminal
    # JMPs stand for its edges to the pre-existing IRQ return and old source-
    # less classifier.  The low landing is deliberately cleanup-free: it
    # preserves an already pending error, supplies E3e only when none exists,
    # and enters longjmp directly.
    return r"""
        .section .text.retired_window_brk_classifier,"ax",@progbits
        .globl retired_window_brk_classifier
        .type retired_window_brk_classifier,@function
retired_window_brk_classifier:
        tsx
        lda $0105,x
        and #$10
        beq retired_window_not_ours
        lda $77
        bne retired_window_not_ours
        lda $79
        ora $7a
        bne retired_window_not_ours
        lda $54
        beq retired_window_not_ours
        lda $0107,x
        cmp #$c3
        bcc retired_window_not_ours
        beq retired_window_low_edge
        cmp #$ca
        bcc retired_window_accept
        bne retired_window_not_ours
        lda $0106,x
        cmp #$93
        bcs retired_window_not_ours
        bra retired_window_accept
retired_window_low_edge:
        lda $0106,x
        cmp #$58
        bcc retired_window_not_ours
retired_window_accept:
        lda #mos16lo(retired_window_resume)
        sta $0106,x
        lda #mos16hi(retired_window_resume)
        sta $0107,x
        jmp retired_window_irq_return
retired_window_not_ours:
        jmp retired_window_old_source_less
        .size retired_window_brk_classifier, .-retired_window_brk_classifier

        .section .text.retired_window_resume,"ax",@progbits
        .globl retired_window_resume
        .type retired_window_resume,@function
retired_window_resume:
        lda $38
        bne .Lpending
        lda #62
        sta $38
        stz $b9e7
        stz $b9e8
.Lpending:
        lda #mos16lo(lisp_toplevel)
        sta $04
        lda #mos16hi(lisp_toplevel)
        sta $05
        lda #1
        ldx #0
        jmp longjmp
        .size retired_window_resume, .-retired_window_resume
"""


def assembled_price() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="c2-retired-brk-price-") as name:
        source = Path(name) / "price.s"
        obj = Path(name) / "price.o"
        source.write_text(price_source(), encoding="utf-8")
        subprocess.run([str(CLANG), "-c", str(source), "-o", str(obj)],
                       cwd=ROOT, check=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
        truth = ElfTruth.read(obj, llvm_readobj=READOBJ,
                              include_section_data=True)
        classifier = truth.symbol("retired_window_brk_classifier")
        landing = truth.symbol("retired_window_resume")
        require(classifier.bytes > 0 and landing.bytes > 0,
                "assembled inversion symbols absent")
        return {
            "classifier_E000_bytes": classifier.bytes,
            "cleanup_free_landing_ordinary_text_bytes": landing.bytes,
            "gross_new_code_bytes": classifier.bytes + landing.bytes,
            "new_state_bytes": 0,
            "hot_path_tax": "source-less IRQ/BRK path only; zero ordinary-call tax",
            "classification_interval": {
                "stacked_return_inclusive": "0xc358",
                "stacked_return_exclusive": "0xca93",
                "equivalent_opcode_interval": "[0xc356,0xca91)",
            },
        }


def classifier_model(*, stacked_p: int, continuation: int, busy: int,
                     loaded_len: int, toplevel_active: int) -> str:
    opcode = (continuation - 2) & 0xFFFF
    if (stacked_p & 0x10 and busy == 0 and loaded_len == 0
            and toplevel_active and WINDOW_START <= opcode < WINDOW_END):
        return "recover-cleanup-free"
    return "existing-source-less/fail-closed-policy"


def classifier_cases() -> list[dict[str, Any]]:
    cases = [
        ("observed-retired-window-BRK", 0x32, 0xC8B8, 0, 0, 1,
         "recover-cleanup-free"),
        ("hardware-IRQ-same-PC", 0x22, 0xC8B8, 0, 0, 1,
         "existing-source-less/fail-closed-policy"),
        ("live-window-genuine-BRK", 0x32, 0xC8B8, 1, 0x123, 1,
         "existing-source-less/fail-closed-policy"),
        ("below-window", 0x32, WINDOW_START + 1, 0, 0, 1,
         "existing-source-less/fail-closed-policy"),
        ("window-first-byte", 0x32, WINDOW_START + 2, 0, 0, 1,
         "recover-cleanup-free"),
        ("window-last-byte", 0x32, WINDOW_END + 1, 0, 0, 1,
         "recover-cleanup-free"),
        ("above-window", 0x32, WINDOW_END + 2, 0, 0, 1,
         "existing-source-less/fail-closed-policy"),
        ("no-toplevel", 0x32, 0xC8B8, 0, 0, 0,
         "existing-source-less/fail-closed-policy"),
    ]
    result = []
    for name, p, pc, busy, length, active, expected in cases:
        observed = classifier_model(stacked_p=p, continuation=pc, busy=busy,
                                    loaded_len=length,
                                    toplevel_active=active)
        require(observed == expected, f"classifier model drift: {name}")
        result.append({"name": name, "expected": expected,
                       "observed": observed})
    return result


def _call_sites(truth: ElfTruth, caller: str, callee: str) -> list[int]:
    owner = truth.symbol(caller)
    target = truth.symbol(callee).value
    section = truth.section(owner.section)
    raw = truth.section_bytes(owner.section)
    sites = []
    for row in truth.relocations:
        identity = truth.relocation_target_identity(row)
        pc = row.offset - 1
        offset = pc - section.address
        if (row.source_section == owner.section
                and owner.value <= pc < owner.value + owner.bytes
                and identity.get("resolved_value") == target
                and 0 <= offset < len(raw) and raw[offset] == 0x20):
            sites.append(pc)
    return sorted(sites)


def derive_live() -> dict[str, Any]:
    inputs = {"ELF": bind(ELF), "capture": bind(CAPTURE)}
    require(inputs["ELF"]["sha256"] == EXPECTED["ELF"],
            "candidate ELF identity drift")
    capture = json.loads(CAPTURE.read_text(encoding="utf-8"))
    rows = {row["name"]: bytes.fromhex(row["observed_hex"])
            for row in capture["reads"]}
    bank0 = rows["bank0-zp-stack"]
    window = rows["workbench-overlay-window"]
    require(capture["tuple"]["PC"] == "0xe096"
            and capture["tuple"]["SP"] == "0x01a7",
            "terminal tuple drift")
    # Four handler pushes put P/PCL/PCH at SP+5/+6/+7.
    stacked_p = bank0[0x1AC]
    continuation = bank0[0x1AD] | bank0[0x1AE] << 8
    opcode = (continuation - 2) & 0xFFFF
    require(stacked_p == 0x32 and stacked_p & 0x10
            and continuation == 0xC8B8 and opcode == 0xC8B6,
            "software-BRK frame drift")
    require(window[opcode - 0xC354] == 0
            and not any(window[WINDOW_START - 0xC354:
                               WINDOW_END - 0xC354]),
            "retired zero window drift")
    require(bank0[0x38] == 0x1C and bank0[0x54] == 1
            and bank0[0x77] == 0 and bank0[0x79:0x7B] == b"\0\0"
            and bank0[0x89] == 2 and bank0[0x8C] == 1,
            "undefined-function/abort-driver lifecycle drift")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    start = truth.symbol("__lisp65_workbench_overlay_start").value
    end = truth.symbol("__lisp65_workbench_overlay_end").value
    require((start, end) == (WINDOW_START, WINDOW_END),
            "runtime-overlay extent drift")

    target = 0xC8B5
    origins = []
    for row in truth.relocations:
        identity = truth.relocation_target_identity(row)
        if identity.get("resolved_value") != target:
            continue
        section = truth.section(row.source_section)
        raw = truth.section_bytes(section.name)
        opcode_at = row.offset - 1
        i = opcode_at - section.address
        origins.append({
            "section": row.source_section, "relocation": row.offset,
            "opcode_address": opcode_at,
            "opcode": raw[i] if 0 <= i < len(raw) else None,
            "target": target,
        })
    require(origins == [{
        "section": ".lisp65_rt_c2append_reserve_transient_code",
        "relocation": 0xC7EC, "opcode_address": 0xC7EB,
        "opcode": 0x4C, "target": 0xC8B5,
    }], "static target-origin multiplicity drift")
    transient = truth.section(origins[0]["section"])
    transient_raw = truth.section_bytes(transient.name)
    require(transient_raw[0xC8B4 - transient.address:0xC8BA - transient.address]
            == bytes.fromhex("60e4084cf6c8"),
            "transient target neighborhood drift")

    cleanup_chain = {
        "lisp_abort_to_cleanup": _call_sites(
            truth, "lisp_abort_symbol", "c2_product_abort_cleanup"),
        "cleanup_to_retirement": _call_sites(
            truth, "c2_product_abort_cleanup",
            "c2_rtov_retire_continuations_facade"),
        "cleanup_to_abort_driver": _call_sites(
            truth, "c2_product_abort_cleanup", "c2_abort_driver_facade"),
        "abort_driver_to_overlay": _call_sites(
            truth, "c2_abort_driver", "c2_overlay_call"),
    }
    require(cleanup_chain == {
        "lisp_abort_to_cleanup": [0x2E8C],
        "cleanup_to_retirement": [0x2EA1],
        "cleanup_to_abort_driver": [0x2EC6],
        "abort_driver_to_overlay": [0x7DDE],
    }, "retirement/abort-driver call order drift")
    cleanup = truth.symbol("c2_product_abort_cleanup")
    require(cleanup_chain["cleanup_to_retirement"][0]
            < cleanup_chain["cleanup_to_abort_driver"][0]
            < cleanup.value + cleanup.bytes,
            "retirement does not precede transported abort cleanup")

    # The stopped stack still contains the outer resident error chain but no
    # C8B5 word: the dynamic transfer carrier was consumed before BRK pushed
    # its frame.  That distinguishes a named carrier value from an invented
    # storage owner.
    stack = bank0[0x100:0x200]
    words = [stack[i] | stack[i + 1] << 8 for i in range(len(stack) - 1)]
    require(target not in words and bytes.fromhex("8e2e3b8f") in stack,
            "consumed-carrier/outer-abort stack witness drift")

    price = assembled_price()
    require(price["classifier_E000_bytes"] > 49
            and price["cleanup_free_landing_ordinary_text_bytes"] > 14,
            "price unexpectedly fits a current thin arena")

    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-21",
        "status": "ATTRIBUTED TO CONSUMED TRANSFER; CONSTRUCTIVE BACKSTOP RECOMMENDED",
        "authority": git_authority(),
        "inputs": inputs,
        "capture_decision": {
            "trigger": "(requre 'v16core)",
            "primary_error": "LISP65_ERR_UNDEFINED_FUNCTION (0x1c)",
            "terminal": "c2_kernal_fail_closed+0x0b@0xe096",
            "software_BRK": {"stacked_P": "0x32", "B": 1,
                             "stacked_continuation": "0xc8b8",
                             "opcode_address": "0xc8b6",
                             "live_byte": "0x00"},
            "lifecycle": {"rtov_busy": 0, "rtov_loaded_len": 0,
                          "phase_owner": 2, "c2_ready": 1},
        },
        "carrier_attribution": {
            "named_value": "0xc8b5",
            "carrier_class": "already-consumed CPU transfer/return carrier",
            "why_value": ("the observed BRK begins at 0xc8b6; an RTS-style "
                          "carrier contains target-minus-one, 0xc8b5"),
            "static_origins": origins,
            "sole_static_origin_meaning": ("legitimate internal JMP in the "
                "reserve-transient-code overlay, not an illegal caller"),
            "storage_owner_at_stop": None,
            "storage_owner_claim": "UNRECOVERABLE FROM THE AUTHORIZED ROW",
            "evidence_boundary": ("0xc8b5 is absent from the stopped stack; "
                "the transfer consumed it before the BRK frame was created"),
            "retirement_order": cleanup_chain,
            "why_population_failed": ("the one-shot pre-wipe walker reasons "
                "about retained storage classes, while control transfer is an "
                "event whose carrier may already be consumed; cleanup also "
                "executes transported phases after that one sanitation pass"),
        },
        "inversion_decision": {
            "answer": "YES",
            "first_line": ("keep carrier prevention, but do not let its "
                "population claim completeness"),
            "complete_backstop_domain": ("every executed stale byte in the "
                "zero-filled retired interval becomes BRK and therefore "
                "presents a hardware frame independent of its former carrier"),
            "classifier": {
                "B_bit": 1,
                "opcode_interval": "[0xc356,0xca91)",
                "retired_registry": "rtov_busy == 0 && rtov_loaded_len == 0",
                "toplevel_active_required": True,
                "all_other_BRKs_and_source_less_IRQs": "unchanged fail-closed",
            },
            "recovery": ("rewrite the stacked continuation to a low, always-"
                "visible landing; preserve a pending error, synthesize E3e only "
                "when none exists, and enter longjmp without invoking cleanup again"),
            "not_sufficient": ("the existing one-byte RTS stub assumes a valid "
                "caller frame and is not a safe arbitrary-transfer landing"),
        },
        "assembled_price": price,
        "classifier_model": {
            "cases": classifier_cases(),
            "recovery_cases": 3,
            "unchanged_policy_cases": 5,
        },
        "carrier_specific_fix_price": {
            "verdict": "NOT HONESTLY PRICEABLE FROM THIS EVIDENCE",
            "reason": ("the value was consumed before capture and no storage "
                "owner remains; assigning a writer or stack offset would be a guess"),
            "next_instrument_if_still_required": ("pre-transfer trace at every "
                "dynamic control-transfer producer, which is strictly broader "
                "and costlier than the constructive BRK backstop"),
        },
        "capacity": {
            "current_E000_free_total": 57,
            "current_E000_largest_contiguous_hole": 49,
            "E000_fixed_floor": E000_FLOOR,
            "E000_required_free_with_watch": E000_REQUIRED_FREE,
            "current_ordinary_text_free": 14,
            "verdict": ("DOES NOT FIT: classifier exceeds the largest E000 "
                "hole and no E000 aggregate byte is freight; landing exceeds "
                "ordinary-text reserve"),
            "required_next_price": ("relocate/reclaim an always-visible E000 "
                "tenant and a low-text tenant, or co-design a smaller landing; "
                "floor and margins remain non-budgets"),
        },
        "walls": [
            "genuine BRK in live overlay remains fail-closed",
            "BRK outside the exact overlay interval remains fail-closed",
            "hardware source-less IRQ behavior remains unchanged",
            "recovery never calls c2_product_abort_cleanup recursively",
            "existing pending error identity is preserved",
            "final classification derives interval and state addresses from ElfTruth",
        ],
        "claim_limit": ("Host-only attribution and assembled price. The dynamic "
            "storage writer of the consumed 0xc8b5 carrier is not recoverable "
            "from the authorized row; no fix/card/link/media/device action is authorized."),
        "execution": {"WPLTO_runs": 0, "product_links": 0,
                      "media_builds": 0, "device_contacts": 0},
    }
    return value


def validate(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT
            and value["inversion_decision"]["answer"] == "YES",
            "sealed inversion decision drift")
    carrier = value["carrier_attribution"]
    require(carrier["named_value"] == "0xc8b5"
            and carrier["storage_owner_at_stop"] is None
            and carrier["storage_owner_claim"]
                == "UNRECOVERABLE FROM THE AUTHORIZED ROW"
            and len(carrier["static_origins"]) == 1,
            "sealed carrier claim exceeded or drifted")
    price = value["assembled_price"]
    live_price = assembled_price()
    require(price == live_price and price["classifier_E000_bytes"] > 49
            and price["cleanup_free_landing_ordinary_text_bytes"] > 14,
            "assembled backstop price drift")
    cases = classifier_cases()
    require(value["classifier_model"]["cases"] == cases
            and sum(row["observed"] == "recover-cleanup-free"
                    for row in cases) == 3,
            "classifier boundary model drift")
    require(value["carrier_specific_fix_price"]["verdict"]
            == "NOT HONESTLY PRICEABLE FROM THIS EVIDENCE",
            "consumed-carrier claim boundary drift")
    require(value["capacity"]["verdict"].startswith("DOES NOT FIT")
            and value["execution"] == {"WPLTO_runs": 0, "product_links": 0,
                                        "media_builds": 0, "device_contacts": 0},
            "study scope/capacity boundary drift")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"check", "write"},
            "usage: c2_v160_retired_window_carrier_inversion.py check|write")
    if sys.argv[1] == "write":
        value = derive_live()
        OUT.write_text(canonical(value), encoding="utf-8")
    else:
        require(OUT.is_file(), "sealed carrier-inversion receipt absent")
        value = json.loads(OUT.read_text(encoding="utf-8"))
    validate(value)
    price = value["assembled_price"]
    print("v1.6 retired-window carrier inversion: PASS "
          f"carrier=c8b5 backstop={price['classifier_E000_bytes']}+"
          f"{price['cleanup_free_landing_ordinary_text_bytes']}B fit=NO")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (StudyError, OSError, KeyError, ValueError,
            subprocess.CalledProcessError) as error:
        print(f"v1.6 retired-window carrier inversion: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
