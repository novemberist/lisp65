#!/usr/bin/env python3
"""Bind Link 43's missing static Bank-2 stage hardware First Red.

This is a read-only diagnosis.  It consumes the SHA-bound Link-43 product and
the captures taken at the hardware stop; it does not compile, link, patch,
deploy, reset or otherwise alter product or device state.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / (
    "build/c2.2/substitution/"
    "product-link-43-c2-lite-v6-export-symbol-domain")
PRESMOKE = ROOT / (
    "build/c2.2/hardware-presmoke-link43-export-symbol-domain")
CAPTURE = PRESMOKE / "first-red-banner-missing"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
STRUCTURAL = EVIDENCE / (
    "c2.2-product-link43-c2-lite-v6-export-symbol-domain-"
    "structural-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-product-link43-c2-lite-v6-bank2-stage-hardware-first-red.json")

PRODUCT = CANDIDATE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
DEPLOYMENT = PRESMOKE / "deployment.json"
WORKBENCH = PRESMOKE / "boot-overlay.raw.bin"
BOOT_STAGE = PRESMOKE / "boot-overlay.stage.bin"
SESSION = CANDIDATE / "runtime-overlays-session-final.bin"
INITIAL_C2D = (CANDIDATE / "fresh-c2-lite-prelink-gates/v6-semantics/"
               "initial.c2d-v6.bin")
EXPECTED_BANK2 = (CANDIDATE / "fresh-c2-lite-prelink-gates/v6-semantics/"
                  "bank2-static-code.bin")
RUNTIME_SOURCE = CANDIDATE / "generated-product-sources/c2_product_runtime.c"
BOOT_SOURCE = ROOT / "src/vm_boot_overlay.c"
COMMIT_SOURCE = ROOT / "src/c2_boot_chain_commit.s"
REPL_SOURCE = ROOT / "src/repl.c"
VM_SOURCE = ROOT / "src/vm.c"
VM_HEADER = ROOT / "src/vm.h"

LOW = CAPTURE / "low-0000-ffff.bin"
BANK2 = CAPTURE / "bank2.bin"
BANK3 = CAPTURE / "bank3.bin"
LIVE_C2D = CAPTURE / "c2d-v6.bin"
COLOR = CAPTURE / "color-ram.bin"

EXPECTED_SHA256 = {
    PRODUCT: "9bbfb17707fe6e57bfd93c49db13f920fa48d0654227c19150aec4a34f1be43b",
    ELF: "7663dd5d511e01dfde8be07e06eaf3f61a86bb02fa539f987415483e8a3b8cb5",
    MAP: "8f3f4568c9702c28ec3e02754bbd30f8f8239f08a269fb5bc9c94af941eff5d1",
    STRUCTURAL: "6cad468649ac5af85876be5e14b66e28fa4f5d6e32d64c25a6389a7934e04ae4",
    DEPLOYMENT: "f747495877f265cf3c136ca7138b0a0b45915dab16012f0b7d954a3a523d5333",
    WORKBENCH: "9d6bb3df12de7de367724c460a261ad85aaaf37423bf148a28162776aadd4fc3",
    BOOT_STAGE: "d5b715cc9da4388b4a0b51134da074995dabc6087fbf7db539873d658b8ad82a",
    SESSION: "5112a8df96e2fbd6ab8d54993afafd30a638d7cd3833398243cbb82d380d1548",
    INITIAL_C2D: "1b924a1d33a7ce4d56ed4cf02c76db047d75b44adee99d315620d52224a05e7d",
    EXPECTED_BANK2: "5b0fcfca7cb63967e36e603276bbccae8f359086b734fcfb8ad85d1da610a2ac",
    RUNTIME_SOURCE: "3eb24e84a40e4c51c3389294450b2d033e1fd248dd37255ab50abc2d9b959522",
    BOOT_SOURCE: "78572685b2810b483fea1c32f93e70218ec6e203b89993ac39b3b57408ed6916",
    COMMIT_SOURCE: "d9d70bd437fc2bea2a6ea9fecb81672cb18c09a1e0f54ff1eeee2fb022cc9cb4",
    REPL_SOURCE: "0abc660c84df174c720f8c3b65f5df603f1698fd5f3441e1f85016cddaca5850",
    VM_SOURCE: "229612ebf6ab30ea3b26a17c91f3efe14e01fa5db8f874c1e49d1c7d4c88ea47",
    VM_HEADER: "c5398009a0ef63a649c1da7908b822160f73cbf66a415ca416db90987d38aae2",
    LOW: "ce5acbb807d602b81f30ba93e1227ddec118bdb6cd45d4d5881ae6b5c788477e",
    BANK2: "19cf4869042a3e49768670b0fc3f2ac493bd955de462bd034156a504bfd22e28",
    BANK3: "5114e718536dd4dcbfffaa5a21a420929b3c189f6c0e26c5caa841dd8f7df9be",
    LIVE_C2D: "ff4e9643e3886d6dc3ae4a7dc26ec3daae105f0f338889708430de28306c2f25",
    COLOR: "0024bf428bdf784cf5e185d49b00cd641f52d0146ac50414d66dbceb548ff490",
}

C2D_ENTRIES_OFFSET = 2096
C2D_ENTRY_BYTES = 10
REPL_BANNER_ORDINAL = 239
STATIC_CODE_BYTES = 34403
CO_MAGIC = 0xB5
VM_BADOPCODE = 2


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


def u32(data: bytes, offset: int = 0) -> int:
    return int.from_bytes(data[offset:offset + 4], "little")


def c_function(source: str, name: str) -> str:
    marker = name + "("
    start = source.find(marker)
    require(start >= 0, f"C function absent: {name}")
    brace = source.find("{", start)
    require(brace >= 0, f"C function body absent: {name}")
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise DiagnosisError(f"unterminated C function: {name}")


def entry(data: bytes, ordinal: int) -> dict[str, int | str]:
    at = C2D_ENTRIES_OFFSET + ordinal * C2D_ENTRY_BYTES
    row = data[at:at + C2D_ENTRY_BYTES]
    require(len(row) == C2D_ENTRY_BYTES, "C2D entry outside artifact")
    return {
        "ordinal": ordinal,
        "raw_hex": row.hex(),
        "image_slot": row[0],
        "literal_count": row[1],
        "code_offset": u16(row, 2),
        "code_length": u16(row, 4),
        "resolution_base": u16(row, 6),
        "generation": u16(row, 8),
    }


def main() -> None:
    require(not RECEIPT.exists(), "Link-43 Bank-2-stage receipt already exists")
    for path, expected in EXPECTED_SHA256.items():
        require(path.is_file() and sha(path) == expected,
                f"bound evidence drift: {path}")

    deployment = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    structural = json.loads(STRUCTURAL.read_text(encoding="utf-8"))
    require(deployment["status"] == "ready-receipt-less"
            and deployment["product"]["sha256"] == EXPECTED_SHA256[PRODUCT],
            "deployment does not bind Link 43")
    require(structural["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run",
            "Link-43 structural prerequisite is not accepted")
    require(all(row["address"] != "0x00020000"
                for row in deployment["preloads"]),
            "hardware harness unexpectedly preloaded the product Bank-2 plane")

    low = LOW.read_bytes()
    bank2 = BANK2.read_bytes()
    bank3 = BANK3.read_bytes()
    live_c2d = LIVE_C2D.read_bytes()
    initial_c2d = INITIAL_C2D.read_bytes()
    expected_bank2 = EXPECTED_BANK2.read_bytes()
    workbench = WORKBENCH.read_bytes()
    session = SESSION.read_bytes()
    require(len(low) == len(bank2) == len(bank3) == 65536,
            "hardware bank capture geometry drift")
    require(len(live_c2d) == len(initial_c2d) == 33840
            and len(expected_bank2) == STATIC_CODE_BYTES
            and len(workbench) == 1731,
            "C2-lite evidence geometry drift")

    runtime_bytes = low[0xc084:0xc084 + 46]
    runtime = {
        "shelf_bytes": u32(runtime_bytes, 0),
        "catalog_crc32": f"0x{u32(runtime_bytes, 4):08x}",
        "c2d_bytes": u16(runtime_bytes, 8),
        "generation": u16(runtime_bytes, 10),
        "image_count": u16(runtime_bytes, 12),
        "entry_count": u16(runtime_bytes, 14),
        "resolution_count": u16(runtime_bytes, 16),
        "root_count": u16(runtime_bytes, 26),
        "resolution_cursor": u16(runtime_bytes, 30),
        "root_cursor": u16(runtime_bytes, 32),
        "phase": runtime_bytes[42],
        "finished": runtime_bytes[43],
        "error": runtime_bytes[44],
    }
    require(runtime == {
        "shelf_bytes": 70897,
        "catalog_crc32": "0x3d6302f3",
        "c2d_bytes": 33840,
        "generation": 1,
        "image_count": 6,
        "entry_count": 588,
        "resolution_count": 2264,
        "root_count": 283,
        "resolution_cursor": 2264,
        "root_cursor": 283,
        "phase": 13,
        "finished": 1,
        "error": 0,
    }, f"unexpected live decoder state: {runtime}")

    fixed_state = {
        "pending_code": low[0x0036],
        "vm_status": low[0x005d],
        "toplevel_active": low[0x0052],
        "screen_base": u16(low, 0x0054),
        "screen_columns": low[0x0056],
        "screen_rows": low[0x0057],
        "cursor_row": low[0x0059],
        "cursor_column": low[0x005a],
        "interned_symbols": u16(low, 0x005b),
        "rtov_busy": low[0x0077],
        "rtov_fault": low[0x0078],
        "rtov_family": low[0x0079],
        "rtov_island_state": low[0x007a],
        "pending_roots": u16(low, 0x008a),
        "ready": low[0x008c],
        "mem_oom": low[0x008f],
        "family_generation": u16(low, 0xc028),
        "committed_roots": u16(low, 0xc080),
    }
    require(fixed_state == {
        "pending_code": 0,
        "vm_status": VM_BADOPCODE,
        "toplevel_active": 1,
        "screen_base": 0x0800,
        "screen_columns": 80,
        "screen_rows": 25,
        "cursor_row": 0,
        "cursor_column": 8,
        "interned_symbols": 473,
        "rtov_busy": 0,
        "rtov_fault": 0,
        "rtov_family": 2,
        "rtov_island_state": 2,
        "pending_roots": 283,
        "ready": 1,
        "mem_oom": 0,
        "family_generation": 1,
        "committed_roots": 283,
    }, f"unexpected live fixed state: {fixed_state}")

    screen = low[0x0800:0x0800 + 80 * 25]
    prompt_codes = bytes((0x0c, 0x09, 0x13, 0x10, 0x36, 0x35, 0x3e, 0x20))
    require(screen[:8] == prompt_codes and screen[8] == 0xa0
            and screen[9:] == bytes((0x20,)) * (len(screen) - 9),
            "screen capture is not the reported bannerless top-row prompt")

    expected_entry = entry(initial_c2d, REPL_BANNER_ORDINAL)
    live_entry = entry(live_c2d, REPL_BANNER_ORDINAL)
    require(expected_entry == live_entry == {
        "ordinal": 239,
        "raw_hex": "0003901d91005e010100",
        "image_slot": 0,
        "literal_count": 3,
        "code_offset": 7568,
        "code_length": 145,
        "resolution_base": 350,
        "generation": 1,
    }, f"repl-banner C2D row drift: {expected_entry}/{live_entry}")

    code_offset = int(expected_entry["code_offset"])
    require(expected_bank2[code_offset] == CO_MAGIC
            and bank2[code_offset] == 0x2c,
            "banner opcode witness drift")
    bank2_differences = sum(a != b for a, b in
                            zip(expected_bank2, bank2[:STATIC_CODE_BYTES]))
    require(bank2_differences == 32483,
            f"unexpected Bank-2 difference count: {bank2_differences}")
    require(bank2[:len(workbench)] == workbench,
            "live Bank 2 is not the authenticated Workbench scratch payload")
    require(bank3[:len(session)] == session,
            "Session Bank 3 differs from Link-43 authority")

    boot_source = BOOT_SOURCE.read_text(encoding="utf-8")
    runtime_source = RUNTIME_SOURCE.read_text(encoding="utf-8")
    repl_source = REPL_SOURCE.read_text(encoding="utf-8")
    vm_source = VM_SOURCE.read_text(encoding="utf-8")
    vm_header = VM_HEADER.read_text(encoding="utf-8")
    product_boot = c_function(runtime_source, "c2_product_boot")
    require("#define B3_CHAIN_BANK 2u" in boot_source
            and "the later C2-lite code stage replaces it" in boot_source
            and "0u, B3_CHAIN_BANK, expected_length" in boot_source,
            "Bank-2 Workbench scratch producer drift")
    require("c2_decode_from(&c2_runtime, 0u)" in product_boot
            and "c2_ready = 1" in product_boot
            and "vm_ext_write" not in product_boot
            and "c2_facade_c2_dma" not in product_boot,
            "static product-boot source audit drift")
    decoder_sources = sorted((CANDIDATE / "generated-product-sources").glob(
        "c2-stream*.c"))
    decoder_text = "\n".join(path.read_text(encoding="utf-8")
                             for path in decoder_sources)
    require(decoder_sources and "vm_ext_write(" not in decoder_text
            and "c2_facade_c2_dma(" not in decoder_text,
            "decode phase unexpectedly owns a Bank-2 write")
    require("(void)vm_run_dir(LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY"
            in repl_source and "#define CO_MAGIC 0xB5" in vm_header
            and "VM_OK=0, VM_HALT, VM_BADOPCODE" in vm_header
            and "cbuf[CO_OFF_MAGIC] != CO_MAGIC" in vm_source,
            "banner/VM failure chain source audit drift")

    receipt = {
        "format": "lisp65-c2-lite-v6-bank2-stage-hardware-first-red-v1",
        "recorded_on": "2026-07-22",
        "status": "first-red-product-semantic-review-required",
        "classification": (
            "Class C: the static Bank-2 code plane is published without being "
            "staged or destination-verified"),
        "observed": "REPL prompt on row 0 without the Lisp65 banner",
        "finding": (
            "All thirteen decode phases and export publication completed and "
            "C2 READY is 1, but physical Bank 2 still begins with the 1,731-byte "
            "Workbench bootstrap scratch payload. The promised later static "
            "34,403-byte code-plane stage is absent from the target boot/decode "
            "closure. Entry 239 therefore reads 0x2c instead of CO_MAGIC 0xb5, "
            "sets VM_BADOPCODE, and repl() discards that status before printing "
            "the top-row prompt."),
        "root_cause": {
            "scratch_producer": (
                "vm_boot_overlay_chain_prepare copies authenticated Workbench "
                "Record 2 to unpublished Bank 2 offset 0"),
            "missing_consumer": (
                "no static Bank-2 copy/destination-identity operation exists in "
                "c2_product_boot or any generated boot decoder phase"),
            "false_green_gate": (
                "the existing stage-before-publish gate binds the host-emitted "
                "Bank-2 artifact and abstract publication model, not a linked "
                "target dataflow that dominates c2_ready=1"),
            "masked_failure": (
                "repl() casts the banner vm_run_dir result to void; the prompt "
                "is not evidence that the published execution plane is usable"),
        },
        "hardware_state": {
            "runtime": runtime,
            "fixed_state": fixed_state,
            "screen": {
                "screen_codes_hex": screen[:9].hex(),
                "prompt": "LISP65>",
                "prompt_row": 0,
                "banner_rows_present": 0,
            },
            "repl_banner_entry": {
                **expected_entry,
                "expected_first_byte": "0xb5",
                "live_first_byte": "0x2c",
                "vm_status_after_call": "VM_BADOPCODE",
            },
            "bank2": {
                "expected_static_bytes": STATIC_CODE_BYTES,
                "different_bytes_in_static_span": bank2_differences,
                "workbench_scratch_prefix_bytes": len(workbench),
                "workbench_scratch_prefix_byteidentical": True,
                "expected_static_sha256": sha(EXPECTED_BANK2),
                "live_full_bank_sha256": sha(BANK2),
            },
            "bank3": {
                "active_session_bytes": len(session),
                "byteidentical_to_link43": True,
                "active_sha256": hashlib.sha256(
                    bank3[:len(session)]).hexdigest(),
            },
        },
        "publication_safety": {
            "ready": 1,
            "decode_finished": True,
            "decode_error": 0,
            "static_bank2_identity_valid": False,
            "stage_before_publish_gate_hardware_result": "false-green",
            "fail_closed": False,
        },
        "budgets": {
            "line1_product_first_reds_consumed": "2/3",
            "latency_measurements_consumed": "0/2",
        },
        "claim_limit": (
            "Read-only diagnosis of the Link-43 line-1 hardware First Red. "
            "It does not authorize or claim a product fix, capacity result, "
            "new link, retry, latency result, promotion or acceptance."),
        "recommended_class_c_cut": {
            "product_rule": (
                "Stage the exact authenticated 34,403-byte static code plane "
                "into Bank 2 and prove its destination identity before C2D "
                "header/export publication and READY."),
            "source_rule": (
                "The target stage consumes the canonical cold shelf/code-plane "
                "authority; no second emitter or externally preloaded Bank-2 "
                "workaround is permitted."),
            "permanent_gates": [
                "linked target dataflow proves the Bank-2 stage dominates READY",
                "all six static image spans and the aggregate 34,403-byte plane match their canonical identities",
                "retained Workbench scratch or one mutated Bank-2 byte rejects before READY",
                "entry 239 begins with CO_MAGIC and the banner call cannot be masked by a prompt",
            ],
            "capacity": (
                "unknown until a product-shaped WPLTO placement probe; no "
                "resident, slice, Bank-3 or E000 credit is prebooked"),
        },
        "artifacts": [bind(path) for path in (
            PRODUCT, ELF, MAP, STRUCTURAL, DEPLOYMENT, WORKBENCH, BOOT_STAGE,
            SESSION, INITIAL_C2D, EXPECTED_BANK2, RUNTIME_SOURCE, BOOT_SOURCE,
            COMMIT_SOURCE, REPL_SOURCE, VM_SOURCE, VM_HEADER, LOW, BANK2,
            BANK3, LIVE_C2D, COLOR)],
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    for path in (*CAPTURE.iterdir(), RECEIPT):
        if path.is_file():
            os.chmod(path, 0o444)
    print("c2-lite-v6-link43-bank2-stage-first-red: PASS "
          f"ready=1 vm_status=VM_BADOPCODE differences={bank2_differences} "
          "workbench_prefix=1731")
    print(f"receipt={RECEIPT.relative_to(ROOT)} sha256={sha(RECEIPT)}")


if __name__ == "__main__":
    main()
