#!/usr/bin/env python3
"""Bind Link 48's post-zero-literal hardware First Red.

This is a read-only evidence binder.  It consumes the SHA-bound Link-48
candidate and captures taken after the first failed dynamic definition.  It
does not compile, link, patch, deploy, reset, or otherwise alter product or
device state.
"""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / (
    "build/c2.2/substitution/"
    "product-link-48-c2-lite-v6-zero-literal-execution")
PRESMOKE = ROOT / "build/c2.2/hardware-presmoke-link48-zero-literal"
CAPTURE = PRESMOKE / "first-red"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
STRUCTURAL = EVIDENCE / (
    "c2.2-product-link48-c2-lite-v6-zero-literal-execution-"
    "structural-receipt.json")
WPLTO = EVIDENCE / "c2.2-link47-zero-literal-wplto-receipt.json"
RECEIPT = EVIDENCE / (
    "c2.2-product-link48-zero-literal-append-hardware-first-red.json")

PRODUCT = CANDIDATE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
DEPLOYMENT = PRESMOKE / "deployment.json"
LINE1_SCREEN = PRESMOKE / "line1/screen.png"
TRANSCRIPT = PRESMOKE / "latency/definition_setup.txt"
ERROR_SCREEN = PRESMOKE / "latency/definition_setup.png"
LOW = CAPTURE / "low64k.bin"
BANK2 = CAPTURE / "bank2-static-code.bin"
CODEBUF = CAPTURE / "vm-codebuf-256.bin"
LIVE_C2D = CAPTURE / "bank5-c2d-live.bin"
C2D_REGION = CAPTURE / "bank5-c2d-region-live.bin"
SESSION_IMAGE = CAPTURE / "session-emission-119.bin"
BANK2_AUTHORITY = (
    CANDIDATE
    / "fresh-c2-lite-prelink-gates/v6-semantics/bank2-static-code.bin")

EXPECTED_SHA256 = {
    PRODUCT: "1b7f7309a415d113a0d8718805e8c860ff3583b82ee2037dfae9dac5f7f5eae6",
    ELF: "1844e69f265025d5d3179db3e6a4e0d8ffd22b67f14b121e2a8ee139864e0404",
    MAP: "283685ba1916ef7fbde56784019f12d828242c0b79b972c4ef01acdf8a68a0a8",
    STRUCTURAL: "867bd59ff9c669e98b4969062eeb0dfd39b0fb633f21dd3e19f067fedb3c7f25",
    WPLTO: "d8cdd3f3df1aad0483c78b81075be740006490c4e840039ff327cf71bb8b667f",
    DEPLOYMENT: "5073343b7bac1bd739424b85d951a617232eedccdaf170c4673624862818d0d0",
    LINE1_SCREEN: "7bc0ff2468c8dcbd089f000422dc62f4f607f2e7394ae04790f06ef4d3725e6c",
    TRANSCRIPT: "1fd6f363ea2096be9e0634675c87205f131cbce56ee71deb4fda8fae9e1c5b70",
    ERROR_SCREEN: "4d8fc02fed2ca4c6ae1b92993a3701f13a199885dfa70111f2bcf019349d2a3c",
    LOW: "8f6575725e5c1117a3c36ef35aa249bfde458fbc542e1eaa36ede47a0b2c59d7",
    BANK2: "5b0fcfca7cb63967e36e603276bbccae8f359086b734fcfb8ad85d1da610a2ac",
    CODEBUF: "e65bb8e9de1b2c37b9ad3ace7d780f432a628e664a0a9fe77b2d113df67ad29d",
    LIVE_C2D: "8f9a7f6ded2bcc0f58ec3d4172560fc57eabcbf5a4e77ce45ef0e1223d7dc009",
    C2D_REGION: "72aad9da265fb26a472a8eaa19f75e3e8935c0cb6210e519f3697226001545bf",
    SESSION_IMAGE: "176de02000b6d29914175c2303216f7530b5a73f0b8bf6cc7f190ab643602531",
    BANK2_AUTHORITY: "5b0fcfca7cb63967e36e603276bbccae8f359086b734fcfb8ad85d1da610a2ac",
}


class DiagnosisError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DiagnosisError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, object]:
    require(path.is_file(), f"evidence absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def u16(data: bytes, offset: int = 0) -> int:
    return int.from_bytes(data[offset:offset + 2], "little")


def u24(data: bytes, offset: int = 0) -> int:
    return int.from_bytes(data[offset:offset + 3], "little")


def u32(data: bytes, offset: int = 0) -> int:
    return int.from_bytes(data[offset:offset + 4], "little")


def main() -> None:
    require(not RECEIPT.exists(), "Link-48 append First-Red receipt exists")
    for path, expected in EXPECTED_SHA256.items():
        require(sha(path) == expected, f"bound evidence drift: {path}")

    structural = json.loads(STRUCTURAL.read_text(encoding="utf-8"))
    deployment = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    require(structural["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run",
            "Link-48 structural prerequisite is not green")
    require(structural["product_identity"]["product"]["sha256"] ==
            EXPECTED_SHA256[PRODUCT], "structural product identity drift")
    require(deployment["status"] == "ready-receipt-less"
            and deployment["product"]["sha256"] == EXPECTED_SHA256[PRODUCT],
            "deployment does not bind Link 48")
    require("*** vm: bad bytecode" in TRANSCRIPT.read_text(encoding="utf-8"),
            "captured first deviation absent")

    low = LOW.read_bytes()
    bank2 = BANK2.read_bytes()
    codebuf = CODEBUF.read_bytes()
    c2d = LIVE_C2D.read_bytes()
    c2d_region = C2D_REGION.read_bytes()
    session = SESSION_IMAGE.read_bytes()
    require(len(low) == 65536 and len(bank2) == 34403
            and len(codebuf) == 256 and len(c2d) == 50752
            and len(c2d_region) == 50816 and len(session) == 119,
            "capture geometry drift")
    require(bank2 == BANK2_AUTHORITY.read_bytes(),
            "live Bank-2 code differs from Link-48 authority")

    # The emitted session object is independently self-authenticating.
    require(session[:4] == b"L65S" and session[4:8] == bytes((4, 32, 32, 1)),
            "dynamic L65S-v4 envelope invalid")
    require(u16(session, 8) == 32 and u24(session, 10) == 64
            and u24(session, 13) == len(session) and u16(session, 16) == 32,
            "dynamic L65S-v4 geometry invalid")
    require((zlib.crc32(session[32:64]) & 0xffffffff) == u32(session, 18),
            "dynamic catalog CRC invalid")
    require(session[32:36] == b"SESS" and session[62] == 1
            and session[63] == 0, "dynamic record invalid")
    code_off, code_len = u24(session, 40), u16(session, 43)
    meta_off, meta_len = u24(session, 45), u16(session, 48)
    require((code_off, code_len, meta_off, meta_len) == (64, 9, 73, 46),
            "dynamic code/metadata geometry drift")
    require((zlib.crc32(session[code_off:code_off + code_len]) & 0xffffffff)
            == u32(session, 50), "dynamic code CRC invalid")
    require((zlib.crc32(session[meta_off:meta_off + meta_len]) & 0xffffffff)
            == u32(session, 54), "dynamic metadata CRC invalid")
    require((zlib.crc32(session[code_off:]) & 0xffffffff) == u32(session, 58),
            "dynamic combined CRC invalid")
    metadata = session[meta_off:]
    require(metadata[:8] == b"C2I\0\x02\x18\x10\x08"
            and u16(metadata, 10) == 1 and u16(metadata, 12) == 0
            and u16(metadata, 20) == 6 and metadata[-6:] == b"\x04\x00%c2h",
            "dynamic zero-literal C2I payload invalid")

    # The emitter completed normally and left a canonical, inactive state.
    c2e = low[0xfd08:0xfd12]
    require(c2e == bytes.fromhex("49 00 01 00 00 00 06 00 00 00"),
            "unexpected C2 emitter state")

    # The executing outer frame is the static lcc-run entry (ordinal 171).
    vm = {
        "status_after_renderer_reset": low[0x005d],
        "buffer_bank": low[0xc011],
        "buffer_ordinal": u16(low, 0xb9f5),
        "header_length": u16(low, 0xc012),
        "literal_table_vma": f"0x{u16(low, 0xc014):04x}",
        "code_vma": f"0x{u16(low, 0xc016):04x}",
        "payload_offset": u16(low, 0xc018),
        "payload_length": u16(low, 0xc01a),
        "payload_window_max": u16(low, 0xc01c),
        "window_pc": u16(low, 0xc01e),
        "window_length": u16(low, 0xc020),
        "streaming": low[0xc022],
    }
    require(vm == {
        "status_after_renderer_reset": 0,
        "buffer_bank": 1,
        "buffer_ordinal": 171,
        "header_length": 13,
        "literal_table_vma": "0xbfe0",
        "code_vma": "0xbfe6",
        "payload_offset": 13,
        "payload_length": 63,
        "payload_window_max": 43,
        "window_pc": 45,
        "window_length": 18,
        "streaming": 1,
    }, f"unexpected VM frame: {vm}")
    lcc_run = bank2[0x0f3b:0x0f3b + 76]
    require(lcc_run[:7] == bytes.fromhex("b5 01 01 02 3f 00 03")
            and codebuf[:7] == lcc_run[:7]
            and codebuf[13:31] == lcc_run[13 + 45:],
            "captured VM window is not lcc-run pc 45..62")

    runtime = low[0xc084:0xc084 + 46]
    runtime_state = {
        "shelf_bytes": u32(runtime, 0),
        "catalog_crc32": f"0x{u32(runtime, 4):08x}",
        "c2d_bytes": u16(runtime, 8),
        "generation": u16(runtime, 10),
        "image_count": u16(runtime, 12),
        "entry_count": u16(runtime, 14),
        "resolution_count": u16(runtime, 16),
        "root_count": u16(runtime, 26),
        "phase": runtime[42],
        "finished": runtime[43],
        "error": runtime[44],
    }
    require(runtime_state == {
        "shelf_bytes": 70897,
        "catalog_crc32": "0x3d6302f3",
        "c2d_bytes": 33840,
        "generation": 1,
        "image_count": 6,
        "entry_count": 588,
        "resolution_count": 2264,
        "root_count": 283,
        "phase": 13,
        "finished": 1,
        "error": 0,
    }, f"unexpected restored runtime state: {runtime_state}")
    require(low[0x008c] == 0 and u16(low, 0x002e) == 0,
            "append failure was not fail-closed at the public boundary")

    # The published C2D header was restored, but the new image and entry rows
    # remain in the unreachable suffix and the durable C2J is still ACTIVE.
    require(c2d[:4] == b"C2D\0" and c2d[4] == 6
            and u16(c2d, 8) == 4096 and u16(c2d, 10) == 1
            and u16(c2d, 12) == 6 and u16(c2d, 16) == 588
            and u16(c2d, 20) == 2264 and u16(c2d, 24) == 283,
            "live C2D header was not restored to the published prefix")
    image_row = c2d[48 + 6 * 32:48 + 7 * 32]
    entry_row = c2d[2096 + 588 * 10:2096 + 589 * 10]
    require(image_row == bytes.fromhex(
        "01 00 00 00 01 00 4c 02 01 00 d8 08 00 00 1b 01 "
        "00 00 63 86 00 09 00 00 00 00 00 00 0a d3 f6 2a"),
        "unreachable appended image row drift")
    require(entry_row == bytes.fromhex("06 00 63 86 09 00 d8 08 01 00"),
            "unreachable appended entry row drift")

    journal = c2d_region[50752:50816]
    journal_state = {
        "magic": journal[:4].decode("ascii", errors="replace"),
        "version": journal[4],
        "active": journal[5],
        "flags": journal[6],
        "journal_count": journal[7],
        "generation": u16(journal, 8),
        "old_counts": [u16(journal, i) for i in (10, 12, 14, 16)],
        "new_counts": [u16(journal, i) for i in (18, 20, 22, 24)],
        "delta_counts": [u16(journal, i) for i in (26, 28, 30)],
        "session_offset": u32(journal, 32),
        "session_length": u16(journal, 36),
        "watermark": u16(journal, 38),
        "stored_crc32": f"0x{u32(journal, 60):08x}",
        "computed_crc32": f"0x{zlib.crc32(journal[:60]) & 0xffffffff:08x}",
    }
    require(journal_state == {
        "magic": "C2J\u0000",
        "version": 1,
        "active": 1,
        "flags": 0,
        "journal_count": 0,
        "generation": 1,
        "old_counts": [6, 588, 2264, 283],
        "new_counts": [7, 589, 2264, 283],
        "delta_counts": [1, 0, 0],
        "session_offset": 0,
        "session_length": 119,
        "watermark": 4096,
        "stored_crc32": "0x914e4da3",
        "computed_crc32": "0x914e4da3",
    }, f"unexpected persistent journal: {journal_state}")

    # The exclusive append scratch independently carries the same transaction.
    scratch = low[0xc0c6:0xc0c6 + 304]
    append_state = {
        "length": u16(scratch, 50),
        "code_offset": u16(scratch, 52),
        "code_length": u16(scratch, 54),
        "metadata_offset": u16(scratch, 56),
        "metadata_length": u16(scratch, 58),
        "entries": u16(scratch, 60),
        "literals": u16(scratch, 62),
        "roots": u16(scratch, 64),
        "old_counts": [u16(scratch, i) for i in (66, 68, 70, 72)],
        "new_counts": [u16(scratch, i) for i in (74, 76, 78, 80)],
        "journal_result": scratch[182 + 31],
        "staged": scratch[238],
        "committed": scratch[239],
        "rollback_flags": scratch[240],
    }
    require(append_state == {
        "length": 119,
        "code_offset": 64,
        "code_length": 9,
        "metadata_offset": 73,
        "metadata_length": 46,
        "entries": 1,
        "literals": 0,
        "roots": 0,
        "old_counts": [6, 588, 2264, 283],
        "new_counts": [7, 589, 2264, 283],
        "journal_result": 1,
        "staged": 1,
        "committed": 1,
        "rollback_flags": 1,
    }, f"unexpected append scratch: {append_state}")

    receipt = {
        "format": "lisp65-c2-lite-v6-link48-zero-literal-append-hardware-first-red-v1",
        "recorded_on": "2026-07-22",
        "status": "first-red-product-semantics-review-required",
        "classification": (
            "Class C: dynamic zero-literal emit succeeds, then append/rollback "
            "fails before a completed definition or latency measurement"),
        "candidate": {
            "link": 48,
            "product": bind(PRODUCT),
            "elf": bind(ELF),
            "map": bind(MAP),
            "structural_receipt": bind(STRUCTURAL),
            "qualified_wplto_receipt": bind(WPLTO),
            "deployment": bind(DEPLOYMENT),
        },
        "hardware_result": {
            "line_1": {
                "status": "passed",
                "observed": "complete Workbench Dialect V2 banner and REPL",
                "screen": bind(LINE1_SCREEN),
            },
            "definition_setup": {
                "form": "(defun %c2h()(quote t))",
                "expected": "a successfully appended and published definition",
                "observed": "*** vm: bad bytecode",
                "status": "first-red",
                "transcript": bind(TRANSCRIPT),
                "screen": bind(ERROR_SCREEN),
            },
        },
        "read_only_localization": {
            "static_code_plane": {
                "status": "byte-identical-to-Link-48-authority",
                "hardware": bind(BANK2),
                "authority": bind(BANK2_AUTHORITY),
            },
            "dynamic_emission": {
                "status": "valid-complete-zero-literal-L65S-v4-image",
                "image": bind(SESSION_IMAGE),
                "length": len(session),
                "code_offset": code_off,
                "code_length": code_len,
                "metadata_offset": meta_off,
                "metadata_length": meta_len,
                "entry_count": u16(metadata, 10),
                "literal_count": u16(metadata, 12),
                "string_bytes": u16(metadata, 20),
                "export_name": "%c2h",
                "emitter_state_hex": c2e.hex(" "),
                "emitter_active": c2e[8],
                "emitter_failed": c2e[9],
            },
            "outer_execution_frame": {
                "attribution": "static ordinal 171, stdlib lcc-run",
                "state": vm,
                "code_window": bind(CODEBUF),
                "proved": (
                    "The zero-literal callee reader no longer rejects %lcc-consp; "
                    "execution advanced through lcc-run to its install suffix."),
                "not_proved": (
                    "The exact failing opcode/PC is not persisted and is not "
                    "inferred from the final streamed window."),
            },
            "fail_closed_boundary": {
                "ready": low[0x008c],
                "vm_status_after_renderer_reset": low[0x005d],
                "resident_journal_count": u16(low, 0x002e),
                "restored_runtime": runtime_state,
            },
            "append_transaction": {
                "scratch": append_state,
                "persistent_journal": journal_state,
                "c2d_capture": bind(LIVE_C2D),
                "c2d_plus_journal_capture": bind(C2D_REGION),
                "published_header_counts": [6, 588, 2264, 283],
                "unreachable_suffix": {
                    "image_index": 6,
                    "image_row_hex": image_row.hex(" "),
                    "entry_ordinal": 588,
                    "entry_row_hex": entry_row.hex(" "),
                },
                "finding": (
                    "The append wrote a valid persistent C2J and staged one image "
                    "and one entry. The public header was restored to the old "
                    "counts, but the suffix rows and ACTIVE journal remain. This "
                    "localizes the First Red to the downstream append/rollback "
                    "chain, after successful zero-literal emission."),
            },
        },
        "fixture_assessment": {
            "source_gate": {
                "path": "tools/host-lisp/c2_zero_literal_execution_gate.py",
                "sha256": sha(ROOT / "tools/host-lisp/c2_zero_literal_execution_gate.py"),
            },
            "proved_before_hardware": (
                "Reader/model acceptance, the linked vm_run_dir-to-entry-record "
                "chain, and seven malformed-record negatives."),
            "gap_exposed_by_hardware": (
                "The fixture did not execute a real dynamically emitted "
                "zero-literal definition through append, publication, and install. "
                "It must be strengthened at that end-to-end boundary in the next "
                "authorized product cut."),
        },
        "claim_boundary": {
            "proved": [
                "Link 48 passed hardware line 1 with banner and REPL",
                "the requested zero-literal record-reader rejection is removed",
                "the dynamic emitter produced a valid one-entry, zero-literal image",
                "Bank 2 is byte-identical to the Link-48 authority",
                "append reached journal write and staged the new image and entry",
                "fail-closed restored the published C2D counts and removed READY",
            ],
            "not_proved": [
                "the exact append/decode/publication slice that first returned red",
                "the exact rollback slice that prevented journal/suffix cleanup",
                "any cold or warm latency value",
                "a product fix for this newly exposed downstream defect",
            ],
        },
        "accounting": {
            "line_1_status": "passed",
            "line_1_product_first_red_budget": "2/3 unchanged",
            "completed_latency_measurements": "0/2 unchanged",
            "new_product_links_during_read_only_diagnosis": 0,
            "additional_hardware_inputs_after_first_deviation": 0,
        },
        "next_action": (
            "Class-C review. No product fix, diagnostic link, additional hardware "
            "input, promotion, acceptance, or release is authorized by this receipt."),
        "value_string": (
            "link48=1b7f7309a415d113a0d8718805e8c860ff3583b82ee2037dfae9dac5f7f5eae6 "
            "line1=pass banner=repl definition=FIRST-RED-VM_BADOPCODE "
            "emit=L65S-v4/119B/entries1/literals0 bank2=34403-identical "
            "append=staged+committed c2j=ACTIVE old=6/588/2264/283 "
            "new=7/589/2264/283 ready=0 line1-budget=2/3 latency=0/2 "
            "acceptance=blocked"),
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    print(f"PASS: {RECEIPT.relative_to(ROOT)}")
    print(f"receipt_sha256={sha(RECEIPT)}")
    print(receipt["value_string"])


if __name__ == "__main__":
    main()
