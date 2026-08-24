#!/usr/bin/env python3
"""Attribute the v1.6 stopped BRK against the runtime-overlay lifecycle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from elf_truth import ElfTruth


ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build/c2.3/v1.6-hybrid-live-stack-replacement-card-r1/wplto"
ELF = BUILD / "lisp65-c2-substitution-linked.prg.elf"
SESSION_JSON = BUILD / "runtime-overlays-session-final.json"
SESSION_BIN = BUILD / "runtime-overlays-session-final.bin"
BOOT_JSON = BUILD / "runtime-overlays-boot-final.json"
BOOT_BIN = BUILD / "runtime-overlays-boot-final.bin"
CAPTURE = ROOT / (
    "build/c2.3/v1.6-items12-hybrid-owner-contact/"
    "hybrid-entry-first-red-stopped-state/capture.json")
RTOV_SOURCE = ROOT / "src/vm_runtime_overlay.c"
VM_SOURCE = ROOT / "src/vm.c"
BUFFER_SOURCE = ROOT / "src/buffer_overlay.c"
MEM_SOURCE = ROOT / "src/mem.c"
INTERRUPT_SOURCE = ROOT / "src/interrupt.c"
OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-overlay-view-attribution-receipt.json")
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
COMMISSION = "93604f6429e44ed0397a753e69c68656226a7383"
EXPECTED = {
    "capture": "73827d43bb82102b434bd81a92bc2ce216bf9c3c5b67cc85b3b9b29a89188992",
    "ELF": "a03f9fafc5629f913dcf213925d7f007fd91b353ab2229a6189080c37f604c9c",
}
SITE = 0xC5B6


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
    for token in (b"Overlay-view attribution commissioned",
                  b"host-only overlay-view attribution",
                  b"specified but not executed"):
        require(token in raw, f"commission token absent: {token!r}")
    return {"authority": "git-blob", "commit": COMMISSION, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def symbol_bytes(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    raw = truth.section_bytes(section.name)
    offset = symbol.value - section.address
    require(symbol.bytes > 0 and 0 <= offset <= len(raw) - symbol.bytes,
            f"symbol bytes unavailable: {name}")
    return raw[offset:offset + symbol.bytes]


def read_capture() -> tuple[dict[str, Any], dict[str, bytes]]:
    document = json.loads(CAPTURE.read_text(encoding="utf-8"))
    rows = {row["name"]: bytes.fromhex(row["observed_hex"])
            for row in document["reads"]}
    require("bank0-zp-stack" in rows and "c2-fixed-state" in rows,
            "capture range set drift")
    return document, rows


def family(path_json: Path, path_bin: Path) -> tuple[dict[str, Any], bytes]:
    document = json.loads(path_json.read_text(encoding="utf-8"))
    raw = path_bin.read_bytes()
    require(sha(raw) == document["storage"]["sha256"],
            f"family image identity drift: {path_bin.name}")
    return document, raw


def slice_site_rows(document: dict[str, Any], raw: bytes) -> list[dict[str, Any]]:
    rows = []
    for item in document["slices"]:
        delta = SITE - int(item["vma"])
        if 0 <= delta < int(item["file_size"]):
            at = int(item["file_offset"]) + delta
            rows.append({"id": int(item["id"]), "name": item["name"],
                         "byte": f"0x{raw[at]:02x}",
                         "neighborhood_hex": raw[at-6:at+8].hex(),
                         "source_address": f"0x{int(item['source_address']):08x}"})
    return rows


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"check", "write"},
            "usage: c2_v160_overlay_view_attribution.py check|write")
    inputs = {"capture": bind(CAPTURE), "ELF": bind(ELF),
              "session_manifest": bind(SESSION_JSON),
              "session_image": bind(SESSION_BIN),
              "boot_manifest": bind(BOOT_JSON), "boot_image": bind(BOOT_BIN),
              "runtime_overlay_source": bind(RTOV_SOURCE),
              "vm_source": bind(VM_SOURCE), "buffer_source": bind(BUFFER_SOURCE),
              "memory_source": bind(MEM_SOURCE),
              "interrupt_source": bind(INTERRUPT_SOURCE)}
    require({key: inputs[key]["sha256"] for key in EXPECTED} == EXPECTED,
            "frozen evidence identity drift")
    capture, rows = read_capture()
    bank0 = rows["bank0-zp-stack"]
    require(len(bank0) == 512, "bank-0 capture length drift")
    require(bank0[0x77] == 0 and bank0[0x79:0x7b] == b"\0\0",
            "captured runtime-overlay lifecycle tuple drift")
    require(bank0[0x2e:0x30] == b"\0\0", "captured C2 journal count drift")

    truth = ElfTruth.read(ELF, llvm_readobj=LLVM_READOBJ,
                          include_section_data=True)
    owner = truth.symbol("buf_from_string")
    entry = truth.symbol("lisp65_buffer_overlay_alloc_entry")
    owner_raw = symbol_bytes(truth, "buf_from_string")
    offset = SITE - owner.value
    require(owner.section == ".lisp65_rt_buffer_alloc" and owner.value == 0xc5af
            and owner_raw[offset] == 0x02, "candidate site owner drift")
    require(owner_raw[offset-1:offset+2] == bytes.fromhex("8502a5"),
            "candidate site is no longer the operand of STA zp")

    session, session_raw = family(SESSION_JSON, SESSION_BIN)
    boot, boot_raw = family(BOOT_JSON, BOOT_BIN)
    selected = [row for row in session["slices"]
                if row["name"] == "first-class-buffer-alloc"]
    require(len(selected) == 1, "buffer-allocation slice multiplicity drift")
    slot = selected[0]
    require(slot["id"] == 50 and slot["section"] == owner.section
            and slot["vma"] == 0xc356 and slot["entry"] == entry.value
            and slot["file_size"] == 1687, "buffer slice identity drift")
    site_source = int(slot["source_address"]) + SITE - int(slot["vma"])
    site_file = int(slot["file_offset"]) + SITE - int(slot["vma"])
    require(site_source == 0x0003f960 and session_raw[site_file] == 0x02,
            "bound source byte/address drift")
    record_offset = (int(session["catalog"]["header_size"])
                     + int(slot["id"]) * int(session["catalog"]["entry_size"]))
    record = session_raw[record_offset:record_offset + 32]
    require(record == bytes.fromhex(
        "3200060000f7970656c39706fe0301004a53287edb74c19f0003000000000000"),
        "slot-50 record drift")

    target_relocations = [rel for rel in truth.relocations
                          if rel.target == "buf_from_string"]
    require(len(target_relocations) == 1
            and target_relocations[0].source_section == owner.section,
            "buf_from_string linked-call ownership drift")
    entry_relocations = [rel for rel in truth.relocations
                         if rel.target == "lisp65_buffer_overlay_alloc_entry"]
    require(not entry_relocations,
            "overlay entry acquired an unexpected direct linked caller")
    session_site = slice_site_rows(session, session_raw)
    boot_site = slice_site_rows(boot, boot_raw)
    require(not [row for row in session_site if row["byte"] == "0x00"],
            "a valid session slice unexpectedly supplies zero at the BRK site")
    boot_zero = [row for row in boot_site if row["byte"] == "0x00"]
    require([(row["id"], row["name"]) for row in boot_zero]
            == [(4, "c2-decode-01")], "boot zero-byte collision set drift")

    result = {
        "format": "lisp65-c2.3-v1.6-overlay-view-attribution-v1",
        "status": "NARROWED-LIVE-BYTES-REQUIRED",
        "recorded_on": "2026-08-20",
        "authority": historical_plan(), "inputs": inputs,
        "owner_and_lifecycle": {
            "site": "0xc5b6", "intended_symbol": owner.name,
            "symbol_range": "0xc5af..0xc6e7",
            "slice": slot["name"], "slice_id": slot["id"],
            "slice_section": slot["section"], "slice_vma": "0xc356",
            "slice_bytes": slot["file_size"], "slice_entry": "0xc754",
            "source_physical_site": f"0x{site_source:08x}",
            "source_byte": "0x02", "source_record_physical": "0x00030660",
            "source_record_hex": record.hex(),
            "only_static_call_to_owner": {
                "source_section": target_relocations[0].source_section,
                "relocation_offset": f"0x{target_relocations[0].offset:04x}"},
            "entry_contract": ["rtov_busy := 1", "wipe prior target",
                               "authenticate catalog and slot-50 record",
                               "publish rtov_loaded_len := 1687",
                               "copy source $0003f700 to target $c356",
                               "converge full target CRC $74db",
                               "indirect call $c754",
                               "after return wipe 1687 bytes",
                               "rtov_busy := 0"],
            "active_call_invariant": "rtov_busy=1 and rtov_loaded_len=1687",
            "captured_lifecycle": {"rtov_busy_at_0x77": bank0[0x77],
                                   "rtov_loaded_len_at_0x79": 0,
                                   "rtov_island_state_at_0x78": bank0[0x78],
                                   "c2_journal_count_at_0x2e": 0},
            "critical_contradiction": ("the CPU took BRK at an address inside "
                "the slice while the slice lifecycle said inactive; moreover "
                "$c5b6 is the $02 operand of STA $02, not a legal instruction "
                "boundary in buf_from_string"),
        },
        "candidate_matrix": [
            {"candidate": "ordinary uninstalled or partial initial load",
             "host_result": "excluded for every contract-respecting entry",
             "because": "the full target CRC converges before the indirect call; a normal call also requires busy=1 and length=1687",
             "decisive_live_evidence": "mixed expected/zero bytes with busy=1 would reopen an in-flight mutation outside the verified contract"},
            {"candidate": "stale C2 append/export journal",
             "host_result": "excluded as the code-slice authority",
             "because": "c2_journal_count is captured as zero and that journal owns export publication, not runtime-overlay target lifetime",
             "decisive_live_evidence": "a nonzero journal count would identify a concurrent append, but cannot by itself authorize bytes at $c5b6"},
            {"candidate": "call before commit or installation-contract bypass",
             "host_result": "no legitimate linked edge found",
             "because": "the only relocation to buf_from_string originates inside its own slice; the public entry has no direct relocation and is reached through manifest-derived RTOV_CALL after CRC",
             "decisive_live_evidence": "expected slice bytes with busy=0/length=0 would prove lifecycle-state corruption or a dynamic bypass"},
            {"candidate": "different valid session slice",
             "host_result": "excluded for the observed zero",
             "because": "none of all 52 authenticated session slices contains $00 at target offset $c5b6",
             "decisive_live_evidence": "the full live neighborhood matching another session-slice SHA would contradict the manifest enumeration"},
            {"candidate": "stale boot slice c2-decode-01",
             "host_result": "possible byte collision, not established",
             "because": "boot slot 4 alone has $00 at the offset, but its surrounding bytes differ and family/family-generation were not captured",
             "decisive_live_evidence": "live neighborhood plus rtov_family/generation distinguishes this exact stale image from a wiped target"},
            {"candidate": "stale control transfer after retirement/wipe or lifecycle-state clobber",
             "host_result": "leading residual class",
             "because": "busy=0 and loaded_len=0 are the post-wipe state, while BRK occurred inside the retired VMA and at a non-boundary operand address",
             "decisive_live_evidence": "all-zero neighborhood selects post-wipe stale transfer; expected bytes select state clobber; a mixed neighborhood selects asynchronous overwrite/partial wipe"},
        ],
        "valid_images_at_site": {"session": session_site, "boot_zero": boot_zero},
        "specified_not_executed_read": {
            "discipline": ["confirm frozen media/ELF tuple first", "read-only",
                           "no RUN", "no resume", "no reset", "CPU remains stopped"],
            "ranges": [
                {"physical": "0x0000c5a8..0x0000c5c0", "purpose": "live target neighborhood"},
                {"physical": "0x00000077..0x0000007a", "purpose": "busy/island-state/loaded-length"},
                {"physical": "0x0000bff7..0x0000bffa", "purpose": "fault/family/family-generation"},
                {"physical": "0x0000002e..0x0000002f", "purpose": "C2 append journal count control"},
                {"physical": "0x00030660..0x0003067f", "purpose": "active-family slot-50 registry record"},
                {"physical": "0x0003f958..0x0003f968", "purpose": "durable slot-50 source around the site"}],
            "decision_table": {"all_zero_live_target": "retired/wiped target plus stale control transfer",
                               "expected_slot50_live_target": "lifecycle state was cleared or bypassed while bytes remained",
                               "boot_slot4_neighborhood": "stale boot-family view",
                               "mixed_target": "partial wipe/overwrite after a once-valid install",
                               "durable_source_mismatch": "family staging/source corruption rather than target lifetime"},
        },
        "powered_off_fallback": {
            "assumption": "the owner said the device may be powered off; no access was attempted",
            "minimal_contact": ["cold boot the bound product/library pair",
                                "repeat require/Comfort activation only",
                                "on the first red stop once and do not resume",
                                "persist tuple and all six ranges raw-first"],
            "claim": "one reproduction is sufficient only if it reaches the same B=1/$c5b8 signature"},
        "decision": ("Host evidence excludes a normal incomplete install, C2 journal authority, "
                     "a valid session-slice substitution and a linked direct bypass. It cannot "
                     "choose between post-retirement stale control transfer, stale boot view, "
                     "or lifecycle corruption without the specified live bytes."),
        "claim_limit": "Host-only attribution. No fix, card, link, medium, or device contact.",
    }
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if sys.argv[1] == "write":
        OUT.write_text(encoded, encoding="utf-8")
    else:
        require(OUT.is_file() and OUT.read_text(encoding="utf-8") == encoded,
                "overlay attribution receipt absent or stale")
    print("v1.6 overlay-view attribution: PASS selected=live-bytes-required")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"v1.6 overlay-view attribution: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
