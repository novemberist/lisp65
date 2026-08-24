#!/usr/bin/env python3
"""Bind the third-contact input First Red and price its two follow-up tracks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from elf_truth import ElfTruth


ROOT = Path(__file__).resolve().parents[2]
ELF = ROOT / ("build/c2.3/v1.6-liveness-prompt-device-preparation-r1/"
              "canonical-product/final/lisp65-c2-substitution-linked.prg.elf")
CAPTURE = ROOT / ("build/c2.3/v1.6-liveness-prompt-owner-contact/"
                  "input-first-red-stopped-state/capture.json")
OUT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
              "c2.3-v1.6-input-first-red-two-track-attribution.json")
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
COMMISSION = "23a46098"
EXPECTED = {
    "ELF": "102eac84ab25ec57b39990377d4808c3287746b94c65617cca3259fd43f73bcd",
    "capture": "f31fca37b0b335bde5730744c5f2c067f19d68a63016b6141ec3502c1d606eb2",
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


def authority() -> dict[str, Any]:
    name = "docs/planning/v1.6.0-freight-work-plan.md"
    raw = subprocess.run(["git", "show", f"{COMMISSION}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    for token in (b"Track A corrected", b"active frame belongs to it",
                  b"Track B instrument authorized"):
        require(token in raw, f"commission token absent: {token!r}")
    return {"authority": "git-blob", "commit": COMMISSION, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"check", "write"},
            "usage: c2_v160_input_first_red_two_track_attribution.py check|write")
    inputs = {"ELF": bind(ELF), "capture": bind(CAPTURE)}
    require({name: row["sha256"] for name, row in inputs.items()} == EXPECTED,
            "frozen third-contact identity drift")

    capture = json.loads(CAPTURE.read_text())
    rows = {row["name"]: bytes.fromhex(row["observed_hex"])
            for row in capture["reads"]}
    bank0 = rows["bank0-zp-stack"]
    fixed = rows["c2-fixed-state"]
    keyboard = rows["physical-keyboard-io"]
    require(len(bank0) == 0x200 and len(fixed) == 16 and len(keyboard) == 32,
            "raw row geometry drift")
    require(capture["tuple"]["PC"] == "0xe096"
            and capture["tuple"]["SP"] == "0x0175",
            "fail-closed tuple drift")
    require(bank0[0x17A:0x17D] == bytes.fromhex("32b6c8"),
            "BRK frame drift")
    require(bank0[0x38] == 5 and bank0[0x4F] == 2
            and bank0[0x50] == 8 and bank0[0x54] == 1,
            "reader-error carrier drift")
    require(bank0[0x77] == 0 and bank0[0x79:0x7B] == b"\0\0"
            and bank0[0x89] == 2 and bank0[0x8C] == 1,
            "append-abort lifecycle drift")
    require(fixed[6] == 1 and fixed[12] == fixed[13] == 0x2F,
            "source-less/ring witness drift")
    require(keyboard[0x0A] == 0x80 and keyboard[0x19] == 0x0D,
            "physical RETURN witness drift")

    truth = ElfTruth.read(ELF, llvm_readobj=LLVM_READOBJ,
                          include_section_data=True)
    overlay_start = truth.symbol("__lisp65_workbench_overlay_start").value
    overlay_end = truth.symbol("__lisp65_workbench_overlay_end").value
    require((overlay_start, overlay_end) == (0xC356, 0xCA91),
            "overlay generation drift")
    workbench = truth.section(".lisp65_workbench_overlay")
    transient = truth.section(".lisp65_rt_c2append_reserve_transient_code")
    workbench_bytes = truth.section_bytes(workbench.name)
    transient_bytes = truth.section_bytes(transient.name)
    brk = 0xC8B4
    require(workbench_bytes[brk - workbench.address] == 0x02,
            "Workbench byte at BRK site drift")
    require(transient_bytes[brk - transient.address] == 0x60,
            "append transient-code return at BRK site drift")

    # The restorable setjmp population is derived from relocations, not a hand
    # list.  The final ELF contains one call and one storage object.  The new
    # fault occurs before longjmp (the caller return $2e8e remains below the
    # active cleanup frame), so claiming a second jmp_buf would contradict the
    # artifact rather than complete the population.
    setjmp_refs = [row for row in truth.relocations if row.target == "setjmp"]
    longjmp_refs = [row for row in truth.relocations if row.target == "longjmp"]
    top_refs = [row for row in truth.relocations if row.target == "lisp_toplevel"]
    require(len(setjmp_refs) == 1 and len(longjmp_refs) == 1
            and len(top_refs) == 8, "derived setjmp population drift")
    require(truth.symbol("lisp_toplevel").value == 0xBD47
            and truth.symbol("lisp_toplevel").bytes == 19,
            "jmp_buf storage drift")
    require(bank0[0x17F:0x181] == bytes.fromhex("8e2e"),
            "active c2_product_abort_cleanup return witness drift")

    # Derive the live-frame retirement path from relocated final-ELF control
    # transfers.  A stored continuation is not involved: the mapped phase
    # calls the resident abort path, which retires the generation before the
    # nonlocal transfer can abandon the mapped caller's hardware frame.
    def call_site(source_section: str, target: str) -> int:
        target_value = truth.symbol(target).value
        section = truth.section(source_section)
        raw = truth.section_bytes(source_section)
        sites = []
        for row in truth.relocations:
            if row.source_section != source_section:
                continue
            identity = truth.relocation_target_identity(row)
            offset = row.offset - section.address
            if (identity["resolved_value"] == target_value and offset >= 1
                    and raw[offset - 1] == 0x20):
                sites.append(row.offset - 1)
        require(len(sites) == 1,
                f"direct call-site multiplicity: {source_section}->{target}")
        return sites[0]

    active_abort_site = call_site(
        ".lisp65_rt_c2append_roots_fronts", "lisp_abort_symbol")
    cleanup_site = call_site(".text", "c2_product_abort_cleanup")
    wipe_sites = []
    text = truth.section(".text")
    text_raw = truth.section_bytes(".text")
    wipe_value = truth.symbol("rtov_wipe").value
    cleanup = truth.symbol("c2_product_abort_cleanup")
    for row in truth.relocations:
        identity = truth.relocation_target_identity(row)
        offset = row.offset - text.address
        if (row.source_section == ".text"
                and cleanup.value <= row.offset - 1 < cleanup.value + cleanup.bytes
                and identity["resolved_value"] == wipe_value
                and offset >= 1 and text_raw[offset - 1] == 0x20):
            wipe_sites.append(row.offset - 1)
    require(active_abort_site == 0xC939 and cleanup_site == 0x2E8C
            and wipe_sites == [0x2EAA],
            "active-frame retirement path drift")

    transient_entry = truth.symbol("c2_append_reserve_transient_code_phase")
    require(transient_entry.section == transient.name
            and transient_entry.value == overlay_start
            and transient_entry.bytes == transient.bytes
            and transient.address <= brk < transient.address + transient.bytes
            and transient_bytes[brk - transient.address] == 0x60,
            "retired live-frame carrier identity drift")

    active_frame_population = [{
        "generation_section": transient.name,
        "function": "c2_append_reserve_transient_code_phase",
        "entry": f"0x{transient_entry.value:04x}",
        "extent_end_exclusive":
            f"0x{transient_entry.value + transient_entry.bytes:04x}",
        "observed_live_exit": f"0x{brk:04x}",
        "exit_identity": "RTS ($60) in the owning generation; $00 after wipe",
        "abort_trigger": {
            "generation_section": ".lisp65_rt_c2append_roots_fronts",
            "function": "c2_append_fronts_phase",
            "call_site": f"0x{active_abort_site:04x}",
            "callee": "lisp_abort_symbol",
        },
        "retirement_path": [
            f"lisp_abort_symbol+0x1b@0x{cleanup_site:04x}",
            f"c2_product_abort_cleanup+0x0c@0x{wipe_sites[0]:04x}",
            "rtov_wipe"],
        "carrier": "live mapped execution frame, not a stored continuation",
    }]

    def active_frames_covered(rows: list[dict[str, Any]]) -> bool:
        return rows == active_frame_population

    require(active_frames_covered(list(active_frame_population)),
            "derived active-frame population rejected")
    require(not active_frames_covered([]),
            "unclassified active overlay frame mutation was accepted")

    # Mutation for the inventory rule: coverage is equality with the
    # artifact-derived population.  Omitting even the sole member must fail.
    derived_population = {(setjmp_refs[0].source_section,
                           setjmp_refs[0].offset,
                           truth.symbol("lisp_toplevel").value)}

    def population_covered(declared: set[tuple[str, int, int]]) -> bool:
        return declared == derived_population

    require(population_covered(set(derived_population)),
            "derived continuation population rejected")
    require(not population_covered(set()),
            "unlisted continuation-store mutation was accepted")
    require(not population_covered(derived_population | {(".mutant", 1, 2)}),
            "foreign hand-listed continuation mutation was accepted")

    result = {
        "format": "lisp65-c2.3-v1.6-input-first-red-two-track-attribution-v2",
        "status": "ATTRIBUTED: ACTIVE-FRAME-RETIREMENT PLUS INPUT-COUNTERS",
        "recorded_on": "2026-08-20",
        "authority": authority(), "inputs": inputs,
        "raw_decision": {
            "reader_error": "READER_ERR_TOKEN_TOO_LONG (8)",
            "pending_error": "LISP65_ERR_READER_INVALID_TOKEN (5)",
            "physical_return": {"queue_present": "0x80", "code": "0x0d"},
            "software_ring": {"head": 47, "tail": 47, "backlog": 0},
            "gc_runs": int.from_bytes(rows["gc-runs"], "little"),
            "software_BRK": {"stacked_P": "0x32", "B": 1,
                              "opcode": "0xc8b4", "continuation": "0xc8b6"},
            "abort_state": {"phase_owner": 2, "c2_ready": 1,
                            "rtov_busy": 0, "rtov_loaded_len": 0},
        },
        "track_A": {
            "derived_setjmp_population": [{
                "call_source_section": setjmp_refs[0].source_section,
                "call_relocation": f"0x{setjmp_refs[0].offset:04x}",
                "storage": "lisp_toplevel", "storage_address": "0xbd47",
                "storage_bytes": 19, "saved_csr_pairs": 7,
            }],
            "population_count": 1,
            "mutations": [
                "removing the derived member makes coverage unequal and fails",
                "adding a hand-listed foreign member makes coverage unequal and fails",
            ],
            "commission_hypothesis": "a second jmp_buf-class store exists",
            "hypothesis_result": "REFUTED BY FINAL ELF",
            "second_live_continuation_class": {
                "name": "append-abort overlay episode continuation",
                "site": "0xc8b4",
                "site_identity": ("RTS exit in c2_append_reserve_transient_code_phase; "
                                  "the same address is $02 in the ordinary Workbench overlay"),
                "timing": ("software BRK occurs while c2_product_abort_cleanup is still active; "
                           "it precedes the top-level longjmp"),
                "storage_identity": None,
                "why_not_named": ("the authorized rows omit c2 phase scratch and the live overlay-call "
                                  "continuation carrier; the consumed carrier is absent from the stopped stack"),
            },
            "derived_active_frame_population": active_frame_population,
            "active_frame_population_count": len(active_frame_population),
            "claim_correction": ("setjmp/jmp_buf derivation is complete at one stored member but the "
                                 "retirement population has a second carrier class: live call frames"),
            "permanent_rule": ("a generation may not retire while any active frame belongs to it; "
                               "stored continuations and live hardware frames are separate populations"),
            "required_gate_broadening": ("derive retirement-reachable live mapped frames from final-ELF "
                                         "control flow; an unclassified frame fails completeness"),
            "mutation": "removing the C8B4 live-frame member fails coverage",
            "fix_authorized": False,
        },
        "track_B_pricing": {
            "instrument": "three bounded 8-bit monotonic counters",
            "state_layout": {
                "ring_slots_before": 112, "usable_capacity_before": 111,
                "ring_slots_instrumented": 109, "usable_capacity_instrumented": 108,
                "counter_bytes": 3,
                "aliases": ["events_seen", "events_stored", "events_taken"],
                "loss_test_events": 94, "capacity_margin_events": 14,
            },
            "code_price": {
                "events_seen_INC_abs": 3,
                "events_stored_INC_abs": 3,
                "events_taken_INC_abs": 3,
                "total_E000_bytes": 9,
                "current_E000_margin_over_floor": 15,
                "instrumented_margin_over_floor": 6,
                "ordinary_text_delta": 0,
            },
            "bounded_measurement": ("cold boot, fewer than 256 physical events, pre/post counter read; "
                                    "8-bit wrap is excluded by the session bound"),
            "decision_table": [
                "seen < physical events: loss before capture / hardware queue service",
                "seen > stored: capture-ring full or capture commit loss",
                "stored > taken: consumer backlog or take failure",
                "seen = stored = taken but visible input differs: edit/render semantic path",
            ],
            "claim_limit": "permanent product health signal; no acceptance claim by itself",
            "implementation_authorized": True,
            "implementation_authority": COMMISSION,
        },
        "claim_limit": ("Host-only attribution. Track B product implementation is separately "
                        "authorized; no link, medium, device contact or Track-A fix."),
    }
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if sys.argv[1] == "write":
        OUT.write_text(encoded, encoding="utf-8")
    else:
        require(OUT.is_file() and OUT.read_text() == encoded,
                "two-track attribution receipt absent or stale")
    print("v1.6 input First Red: PASS setjmp=1 live-frame=1@c8b4 "
          "instrument=9B-E000")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"v1.6 input First Red: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
