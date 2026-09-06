#!/usr/bin/env python3
"""Seal and check Block 2.6 Card 6's first final-link red."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import block_26_small_hardening_product_card as CARD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/2.6/card6-small-hardening-product-r1/wplto"
PREDECESSOR = ROOT / "build/2.6/card3-vm-hardening-product-r2/wplto"
MAP = BUILD / "resident-island-seed.prg.map"
PREDECESSOR_MAP = PREDECESSOR / "resident-island-seed.prg.map"
LTO = BUILD / "resident-island-seed.prg.lto.o"
PREDECESSOR_LTO = PREDECESSOR / "resident-island-seed.prg.lto.o"
STDERR = BUILD / "resident-island-seed.prg.link.stderr.txt"
STDOUT = BUILD / "resident-island-seed.prg.link.stdout.txt"
PROFILE = BUILD / "resolved-profile.txt"
ELF = BUILD / "lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "lisp65-c2-substitution-linked.prg"
PREFLIGHT = ARCH / "block-2.6-card6-small-hardening-product-r1-preflight.json"
INVOCATION = (ROOT / "build/2.6/card6-small-hardening-product-r1-preflight"
              / "candidate-invocation.json")
RECEIPT = ARCH / "block-2.6-card6-small-hardening-product-r1-final-link-red.json"
REPORT = ROOT / "docs/planning/2.6-card6-small-hardening-product-r1-final-link-red.md"
FORMAT = "lisp65-block-2.6-card6-small-hardening-product-r1-final-link-red-v1"
STATUS = "FROZEN: CARD 6 FINAL LINK STOPPED ON REAL E000 WALL"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

E000_NAMES = (
    ".lisp65_c2_kernal_window.typed_queue_driver",
    ".lisp65_c2_kernal_window.irq_handler",
    ".lisp65_c2_kernal_window.nmi_and_freezer_return",
    ".lisp65_c2_kernal_window.map_switch_and_guards",
    ".lisp65_c2_kernal_window.post_startup_output_seam",
    ".lisp65_c2_kernal_window.c2_resident",
    ".lisp65_c2_kernal_window.reopen_gap0",
    ".lisp65_c2_kernal_window.input_capture_main",
    ".lisp65_c2_kernal_window.profile_rodata",
    ".lisp65_c2_kernal_window.reopen_gap1",
    ".lisp65_c2_kernal_window.input_capture_helper",
    ".lisp65_c2_kernal_window.input_consumer",
    ".lisp65_c2_kernal_window.state",
    ".lisp65_c2_kernal_window.reopen_gap2",
    ".lisp65_c2_vectors",
)


class RedError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RedError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def map_sections(path: Path) -> dict[str, dict[str, int]]:
    pattern = re.compile(
        r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+(\.[^ ]+)$")
    rows: dict[str, dict[str, int]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line)
        if match is None:
            continue
        vma, lma, size = (int(value, 16) for value in match.groups()[:3])
        rows[match.group(4)] = {"VMA": vma, "LMA": lma, "bytes": size,
                                "VMA_end": vma + size, "LMA_end": lma + size}
    return rows


def map_symbol(path: Path, name: str) -> dict[str, int]:
    match = re.search(
        rf"^\s*([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+{re.escape(name)}$",
        path.read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
    require(match is not None, f"map symbol absent: {name}")
    address, size = (int(value, 16) for value in match.groups())
    return {"address": address, "bytes": size, "end": address + size}


def e000_world(path: Path) -> dict[str, Any]:
    sections = map_sections(path)
    owners = {name: sections[name] for name in E000_NAMES}
    occupied = sum(row["bytes"] for row in owners.values())
    main = owners[".lisp65_c2_kernal_window.input_capture_main"]
    profile = owners[".lisp65_c2_kernal_window.profile_rodata"]
    consumer = owners[".lisp65_c2_kernal_window.input_consumer"]
    state = owners[".lisp65_c2_kernal_window.state"]
    capture_reserve = ((profile["VMA"] - main["VMA_end"])
                       + (state["VMA"] - consumer["VMA_end"]))
    return {"owners": owners, "occupied_bytes": occupied,
        "total_free_bytes": 0x2000 - occupied,
        "capture_main_to_profile_rodata_bytes": profile["VMA"] - main["VMA_end"],
        "consumer_to_state_bytes": state["VMA"] - consumer["VMA_end"],
        "combined_capture_reserve_bytes": capture_reserve}


def lto_delta() -> list[dict[str, Any]]:
    old = ElfTruth.read(PREDECESSOR_LTO, llvm_readobj=READOBJ)
    new = ElfTruth.read(LTO, llvm_readobj=READOBJ)
    before = {row.name: row.bytes for row in old.sections}
    after = {row.name: row.bytes for row in new.sections}
    rows = []
    for name in sorted(set(before) | set(after)):
        delta = after.get(name, 0) - before.get(name, 0)
        if delta == 0:
            continue
        if name in {".data.rtov_edma_job", ".bss.rtov_edma_job"}:
            family = "A13 descriptor seam: zero-initialized job moved data-to-BSS"
        elif name == ".lisp65_c2_kernal_window.c2_resident":
            family = "A15 string-builder latch inlined into c2_stream_name_value"
        elif (name.startswith(".text.") or name.startswith(".rela.text.")
              or name in {".lisp65_boot", ".lisp65_rt_boot_02",
                          ".lisp65_rt_buffer_alloc", ".lisp65_rt_c2d_03b"}):
            family = "A10-A15 authored hardening carrier"
        elif name.startswith(".rela."):
            family = "derived relocation population"
        elif (name.startswith(".bss.") or name in {".llvm_addrsig", ".strtab",
                                                    ".symtab"}
              or name.startswith(".rodata.")):
            family = "whole-program allocation or metadata projection"
        else:
            family = "UNCLASSIFIED"
        rows.append({"section": name, "predecessor_bytes": before.get(name, 0),
                     "candidate_bytes": after.get(name, 0), "delta_bytes": delta,
                     "family": family})
    require(all(row["family"] != "UNCLASSIFIED" for row in rows),
            "unclassified LTO section delta")
    return rows


def derive() -> dict[str, Any]:
    stderr = STDERR.read_text(encoding="utf-8", errors="replace")
    messages = [
        "Comfort input capture main escaped its final-image-derived hole",
        "adaptive input consumer breached the 54-byte floor plus 3-byte watch",
        "ordinary full-map chain drift",
        "C2 final E000 floor below 54 bytes",
        "ordinary low BSS escaped the fixed input-owner predecessor",
    ]
    require(all(message in stderr for message in messages),
            "Card-6 final-link stop population drift")
    require(LTO.is_file() and MAP.is_file() and not ELF.exists() and not PRG.exists(),
            "red boundary requires one LTO/map and no final product pair")

    preflight = load(PREFLIGHT)
    invocation = load(INVOCATION)
    toolchain = CARD.toolchain_identity()
    require(preflight["toolchain"] == toolchain
            and invocation["toolchain"] == toolchain,
            "link did not use the manifest-pinned Card-5 toolchain world")

    old_sections, new_sections = map_sections(PREDECESSOR_MAP), map_sections(MAP)
    old_e000, new_e000 = e000_world(PREDECESSOR_MAP), e000_world(MAP)
    old_name = map_symbol(PREDECESSOR_MAP, "c2_stream_name_value")
    new_name = map_symbol(MAP, "c2_stream_name_value")
    require(old_e000["occupied_bytes"] == 8125
            and new_e000["occupied_bytes"] == 8147
            and old_e000["total_free_bytes"] == 67
            and new_e000["total_free_bytes"] == 45
            and old_e000["combined_capture_reserve_bytes"] == 57
            and new_e000["combined_capture_reserve_bytes"] == 35
            and new_e000["capture_main_to_profile_rodata_bytes"] == -14
            and new_e000["consumer_to_state_bytes"] == 49
            and old_name["bytes"] == 833 and new_name["bytes"] == 855
            and new_name["bytes"] - old_name["bytes"] == 22,
            "Card-6 E000 attribution drift")

    old_data, new_data = old_sections[".data"], new_sections[".data"]
    old_bss, new_bss = old_sections[".bss"], new_sections[".bss"]
    raw = new_sections[".lisp65_c2_input_raw_owner"]
    old_job = map_symbol(PREDECESSOR_MAP, "rtov_edma_job")
    new_job = map_symbol(MAP, "rtov_edma_job")
    require(old_data["bytes"] == 22 and new_data["bytes"] == 2
            and old_bss["bytes"] == 508 and new_bss["bytes"] == 528
            and old_job["bytes"] == new_job["bytes"] == 20
            and raw["VMA"] - new_bss["VMA_end"] == 182,
            "Card-6 data/BSS attribution drift")

    deltas = lto_delta()
    return {"format": FORMAT, "recorded_on": "2026-09-04", "status": STATUS,
        "authority": CARD.authority(),
        "inputs": {"preflight": bind(PREFLIGHT), "invocation": bind(INVOCATION),
            "predecessor_map": bind(PREDECESSOR_MAP), "candidate_map": bind(MAP),
            "predecessor_LTO": bind(PREDECESSOR_LTO), "candidate_LTO": bind(LTO),
            "link_stderr": bind(STDERR), "link_stdout": bind(STDOUT),
            "resolved_profile": bind(PROFILE)},
        "toolchain": {"status": "PASS: MANIFEST-PINNED TOOLCHAIN USED",
            "identity": toolchain,
            "cards_1_to_3_attribution": toolchain["historical_cards_1_to_3"]},
        "artifact_boundary": {"LTO_object_present": True, "link_map_present": True,
            "final_ELF_present": False, "final_PRG_present": False,
            "disposition": "NO-FINAL-PAIR; LTO/MAP FROZEN AS FIRST-RED EVIDENCE"},
        "link_messages": messages,
        "real_product_wall": {"owner": "E000/C2 KERNAL window",
            "predecessor": old_e000, "candidate": new_e000,
            "growth_owner": {"symbol": "c2_stream_name_value",
                "predecessor_bytes": old_name["bytes"],
                "candidate_bytes": new_name["bytes"], "delta_bytes": 22},
            "fixed_floor": {"required_bytes": 54, "actual_bytes": 45,
                "deficit_bytes": 9},
            "capture_watch": {"required_bytes": 57, "actual_bytes": 35,
                "deficit_bytes": 22},
            "overlap": {"capture_main_end": new_e000["owners"][
                    ".lisp65_c2_kernal_window.input_capture_main"]["VMA_end"],
                "profile_rodata_start": new_e000["owners"][
                    ".lisp65_c2_kernal_window.profile_rodata"]["VMA"],
                "bytes": 14},
            "minimum_reclaim_or_relocation_bytes": 22,
            "classification": "REAL PLACEMENT/CAPACITY WALL"},
        "derived_checker_pins": {
            "ordinary_full_map_chain": {"classification": "STALE EXACT-SIZE PIN",
                "predecessor_data_bytes": old_data["bytes"],
                "candidate_data_bytes": new_data["bytes"],
                "reason": "rtov_edma_job is runtime-filled and moved from data to BSS"},
            "ordinary_low_BSS": {"classification": "STALE EXACT-SIZE PIN",
                "predecessor_BSS_bytes": old_bss["bytes"],
                "candidate_BSS_bytes": new_bss["bytes"],
                "raw_owner_start": raw["VMA"], "candidate_BSS_end": new_bss["VMA_end"],
                "actual_margin_bytes": 182, "required_margin_bytes": 5,
                "passed_semantic_floor": True},
            "job": {"symbol": "rtov_edma_job", "bytes": 20,
                "predecessor_storage": ".data", "candidate_storage": ".bss"},
            "required_conversion": ("derive data/BSS admission from actual owner intervals "
                "and named floors; do not replace 22/508 with new literals")},
        "failed_link_attribution": {"LTO_section_deltas": deltas,
            "changed_LTO_section_members": len(deltas),
            "unexplained_link_messages": [], "unexplained_link_message_count": 0,
            "final_ELF_difference_attribution": "NOT RUN: NO FINAL PAIR EXISTS"},
        "unpaid_acceptance": {"descriptor_emission_nine_users":
                "NOT CLAIMED: FINAL ELF ABSENT",
            "memory_clobber_final_emission": "NOT CLAIMED: FINAL ELF ABSENT",
            "owner_floor_gate": "RED: E000",
            "scope": "NOT RUN", "acceptance": "NOT RUN",
            "packed_DWX": "NOT RUN", "boot_cycles": "NOT RUN",
            "print_9": "NOT RUN"},
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "completed_product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0, "DWX_prefilter_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "next": ("reviewer/owner decision: host-only E000 reclaim/placement pricing "
            "for one candidate restoring at least 22 bytes, plus semantic conversion "
            "of the two stale data/BSS pins; no WPLTO or link is authorized")}


def report(value: dict[str, Any]) -> str:
    wall = value["real_product_wall"]
    pins = value["derived_checker_pins"]
    return f"""# Block 2.6 Card 6 — first final-link red

Status: **{value['status']}; REVIEW DECISION REQUIRED**

The authorized invocation consumed exactly **one WPLTO and one product-link
attempt**. It retained the LTO object and failed-link map, but emitted **no
final ELF or PRG**. Scope, Acceptance, DWX/media and device counts remain zero.
No resume exists and no second build is authorized.

The Card-5 toolchain gate was active and green before compilation. The link
used the manifest-pinned tree `{value['toolchain']['identity']['installed']['tree']['sha256']}`.
Cards 1–3 used byte-identical required compiler/linker executables; their build
trees additionally carried one unused self-referential symlink that the new
whole-tree gate now rejects. Their zero-unexplained product attributions remain
valid, while their complete historical trees would not pass today's stricter
gate.

## The real wall

E000 grew by **22 bytes**, from {wall['predecessor']['occupied_bytes']:,} to
{wall['candidate']['occupied_bytes']:,} occupied bytes. The entire growth is
owned by `c2_stream_name_value`, **833 → 855 bytes**. Total E000 free space
therefore fell **67 → 45 bytes**, nine below the fixed 54-byte floor.

The sharper placement constraint is the capture watch. Its two derived holes
fell from the admitted **57 bytes** to **35 bytes**. The capture main now ends
14 bytes past profile rodata, while the consumer-to-state hole remains 49
bytes. Restoring only the overlap would be insufficient: an admissible
reclaim/placement must return **at least {wall['minimum_reclaim_or_relocation_bytes']} E000 bytes**.
The floor and watch are not candidates for relaxation.

## Two messages that are not product walls

The descriptor seam makes the zero-initialized 20-byte `rtov_edma_job`
runtime-filled and moves it from `.data` to `.bss`: `.data` is
{pins['ordinary_full_map_chain']['predecessor_data_bytes']} →
{pins['ordinary_full_map_chain']['candidate_data_bytes']} bytes and `.bss` is
{pins['ordinary_low_BSS']['predecessor_BSS_bytes']} →
{pins['ordinary_low_BSS']['candidate_BSS_bytes']} bytes. The candidate BSS
still ends **{pins['ordinary_low_BSS']['actual_margin_bytes']} bytes** before
the linker-visible raw-input owner, far above its five-byte floor. Thus
`ordinary full-map chain drift` and `ordinary low BSS escaped...` are stale
exact-size checker pins. Their successor must derive owner intervals and
floors; replacing 22/508 with new literals is forbidden.

All {value['failed_link_attribution']['changed_LTO_section_members']} nonzero
LTO-section deltas and all five link messages are enumerated and assigned;
there are zero unexplained link symptoms. This is not the card's promised
final-pair attribution: no final pair exists. Likewise the nine-user DMA
emission equivalence, final `"memory"`-clobber proof, Scope, Acceptance,
packed prefilter, boot-cycle comparison and `(print 9)` remain explicitly
unclaimed.

## Decision surface

Recommended next step: one **host-only E000 reclaim/placement price round**,
with no WPLTO or link. It must produce one candidate that restores at least 22
bytes while retaining every floor, and convert the two data/BSS exact-size
pins to semantic owner/floor checks. Only that measured winner should return
for a replacement-WPLTO/link decision.
"""


def validate(value: dict[str, Any]) -> None:
    current = derive()
    require(value == current and value["status"] == STATUS
            and value["real_product_wall"]["minimum_reclaim_or_relocation_bytes"] == 22
            and value["real_product_wall"]["fixed_floor"]["deficit_bytes"] == 9
            and value["real_product_wall"]["capture_watch"]["deficit_bytes"] == 22
            and value["derived_checker_pins"]["ordinary_low_BSS"][
                "passed_semantic_floor"] is True
            and value["failed_link_attribution"]["unexplained_link_message_count"] == 0
            and value["artifact_boundary"]["final_ELF_present"] is False
            and value["attempt_accounting"] == {"product_cards": 1,
                "WPLTO_runs": 1, "product_link_attempts": 1,
                "completed_product_links": 0, "scope_runs": 0,
                "acceptance_runs": 0, "DWX_prefilter_runs": 0,
                "media_builds": 0, "device_contacts": 0},
            "Card-6 final-link red receipt drift")


def write() -> None:
    require(not RECEIPT.exists() and not REPORT.exists(),
            "Card-6 final-link red is one-shot")
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    validate(value)
    print("Block 2.6 Card 6: FINAL RED E000=45/54 capture=35/57 reclaim=22")


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    require(REPORT.is_file() and REPORT.read_text(encoding="utf-8") == report(value),
            "Card-6 final-link red report drift")
    print("Block 2.6 Card 6: FINAL RED CHECK E000=45/54 capture=35/57")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "E000-wall-hidden": lambda row: row["real_product_wall"]["fixed_floor"].update(
            {"deficit_bytes": 0}),
        "capture-watch-weakened": lambda row: row["real_product_wall"].update(
            {"minimum_reclaim_or_relocation_bytes": 14}),
        "BSS-pin-called-product-wall": lambda row: row["derived_checker_pins"][
            "ordinary_low_BSS"].update({"passed_semantic_floor": False}),
        "failed-pair-promoted": lambda row: row["artifact_boundary"].update(
            {"final_ELF_present": True}),
        "link-attempt-hidden": lambda row: row["attempt_accounting"].update(
            {"product_link_attempts": 0}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (RedError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "Card-6 final-link red mutation survived")
    print(f"Block 2.6 Card 6: FINAL RED SELFTEST mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    {"write": write, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RedError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"Block 2.6 Card 6 final-link red: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
