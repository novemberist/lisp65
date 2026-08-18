#!/usr/bin/env python3
"""Bind the post-liveness E25 D1 first red and its one-row discriminator."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402

EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
ELF = ROOT / ("build/c2.3/v2.0-map-tuple-fix-replacement-card/final/"
              "lisp65-c2-substitution-linked.prg.elf")
PRODUCT = ROOT / "build/c2.3/v2.0-map-tuple-media/shared-system/lisp65-product.d81"
LIBRARY = ROOT / "build/c2.3/v2.0-map-tuple-media-base/library/lisp65-library.d81"
SCREEN = ROOT / "build/c2.3/v2.0-map-tuple-d1/product-boot.png"
SCREEN_TEXT = ROOT / "build/c2.3/v2.0-map-tuple-d1/product-boot.txt"
PRODUCT_READBACK = ROOT / "build/c2.3/v2.0-map-tuple-d1/product-readback.d81"
LIBRARY_READBACK = ROOT / "build/c2.3/v2.0-map-tuple-d1/library-readback.d81"
SESSION = ROOT / "config/c2-v150-v20-map-tuple-far-device-session.json"
ROW = ROOT / "config/c2-v20-map-tuple-d1-e25-capture-row.json"
MAIN = ROOT / "src/main.c"
ERRORS = ROOT / "src/error_codes.h"
RUNTIME = ROOT / "src/c2_product_runtime.c"
LAYOUT = ROOT / "scripts/c2-stream-decoder.h"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
RECEIPT = EVIDENCE / "c2.3-v2.0-map-tuple-d1-e25-first-red-receipt.json"
DRIVER = Path(__file__).resolve()

FORMAT = "lisp65-c2.3-v20-map-tuple-d1-e25-first-red-v1"
ELF_SHA256 = "a481eff4acd32f04dde6660090aa2761a2f4a4b6307945cbcb2cda0f70435673"
PRODUCT_SHA256 = "43da1ce57ced3088a56349c84d3b0c32bbc25f1aae34928b808fe31af8462a95"
LIBRARY_SHA256 = "15e4405929be0686d12c8079509fbd9e12f9314041218ed773fd57b895692060"
SCREEN_SHA256 = "27225182cc1222b075900be7dbb69099ddb20d89e0c13d839bbc683889d09a7a"
TEXT_SHA256 = "3f5cbb30109fb71c0d596ffd4149e7c6ca49c110f4bdf03dba275447157921d5"

SYMBOLS = {
    "c2_journal_count": 0x002E,
    "pending_code": 0x0036,
    "c2_pending_roots": 0x008A,
    "c2_ready": 0x008C,
    "mem_oom": 0x008F,
    "lisp_error_msg": 0xBFEF,
    "c2_committed_roots": 0xC080,
    "c2_decode_active": 0xC082,
    "c2_runtime": 0xC084,
}


class EvidenceError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise EvidenceError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def elf_symbols() -> dict[str, int]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    found = {name: truth.symbol(name).value for name in SYMBOLS}
    require(found == SYMBOLS, f"candidate symbol layout drift: {found!r}")
    return found


def derive() -> dict[str, Any]:
    session = load(SESSION)
    row = load(ROW)
    elf = bind(ELF)
    product = bind(PRODUCT)
    library = bind(LIBRARY)
    screen = bind(SCREEN)
    screen_text = bind(SCREEN_TEXT)
    product_readback = bind(PRODUCT_READBACK)
    library_readback = bind(LIBRARY_READBACK)
    require(elf["sha256"] == ELF_SHA256, "candidate ELF identity drift")
    require(product["sha256"] == PRODUCT_SHA256
            and product_readback["sha256"] == PRODUCT_SHA256,
            "product medium/readback identity drift")
    require(library["sha256"] == LIBRARY_SHA256
            and library_readback["sha256"] == LIBRARY_SHA256,
            "library medium/readback identity drift")
    require(screen["sha256"] == SCREEN_SHA256, "screen identity drift")
    require(screen_text["sha256"] == TEXT_SHA256, "screen-text identity drift")
    visible = SCREEN_TEXT.read_text(encoding="utf-8")
    require("E25" in visible and "lisp65>" not in visible,
            "E25/no-prompt screen classification drift")
    require(session["D2_D5_open"] is False,
            "D2-D5 must remain closed after D1 red")
    require(row["status"] == "host-specified-owner-authorization-pending",
            "capture row must not self-authorize device access")
    symbols = elf_symbols()
    runtime = RUNTIME.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    errors = ERRORS.read_text(encoding="utf-8")
    layout = LAYOUT.read_text(encoding="utf-8")
    require("LISP65_ERR_STDLIB_PROFILED_PRELOAD = 37" in errors,
            "E25 enum binding absent")
    require("if (!c2_product_boot())" in main
            and '"c2: invalid product image"' in main,
            "E25 c2_product_boot call-site binding absent")
    require("if (!c2_decode_from(&c2_runtime, 0u)) return 0;" in runtime
            and "if (!c2_publish_exports_from(0))" in runtime,
            "decoder/publication split drift")
    require("uint8_t phase;" in layout and "uint8_t finished;" in layout
            and "uint8_t error;" in layout and "uint8_t reserved;" in layout,
            "c2_stream_context terminal layout drift")
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-13",
        "status": "D1-FIRST-RED-E25; SUBMECHANISM-UNDECIDED",
        "artifacts": {
            "candidate_ELF": elf,
            "product_D81": product,
            "product_D81_readback": product_readback,
            "library_D81": library,
            "library_D81_readback": library_readback,
            "screen": screen,
            "screen_text": screen_text,
        },
        "owner_observation": {
            "liveness_lines": ["LISP65: STAGING MEDIA",
                               "LISP65: BUILDING HEAP",
                               "LISP65: LOADING LIBRARIES"],
            "terminal": {"frame": "red", "background": "blue",
                         "text": "E25", "prompt_visible": False},
            "provenance": "owner physical observation; E25/no-prompt independently screen-bound",
        },
        "classification": {
            "error_code": {"hex": "0x25", "decimal": 37,
                           "name": "LISP65_ERR_STDLIB_PROFILED_PRELOAD"},
            "bound_call": "c2_product_boot",
            "excluded_before_libraries_liveness": [
                "KERNAL ownership rejection", "c2_product_prepare_boot rejection",
                "runtime-island installation rejection"],
            "remaining_split": ["c2_decode_from", "c2_publish_exports_from"],
            "claim_limit": "E25 proves c2_product_boot returned non-OK after decoder entry; it does not yet identify decoder versus export publication.",
        },
        "elf_state": {
            "symbols": {name: f"0x{address:04x}" for name, address in symbols.items()},
            "c2_runtime_bytes": 46,
            "terminal_offsets": {"phase": "0xc0ae", "finished": "0xc0af",
                                 "error": "0xc0b0", "reserved": "0xc0b1"},
            "successful_decode_tuple": {"phase": 13, "finished": 1, "error": 0},
        },
        "capture": row,
        "authority": {
            "device_session": bind(SESSION), "capture_row": bind(ROW),
            "main": bind(MAIN), "error_codes": bind(ERRORS),
            "runtime": bind(RUNTIME), "runtime_layout": bind(LAYOUT),
            "driver": bind(DRIVER),
        },
        "next": "Owner authorization for the single stopped-state discriminator row; no repeat boot is needed while the state remains available.",
    }


def verify(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT, "format drift")
    require(value["status"] == "D1-FIRST-RED-E25; SUBMECHANISM-UNDECIDED",
            "status overclaim or drift")
    require(value["classification"]["error_code"] == {
        "hex": "0x25", "decimal": 37,
        "name": "LISP65_ERR_STDLIB_PROFILED_PRELOAD"}, "E25 binding drift")
    require(value["classification"]["remaining_split"]
            == ["c2_decode_from", "c2_publish_exports_from"],
            "decoder/publication split drift")
    require(value["elf_state"]["terminal_offsets"] == {
        "phase": "0xc0ae", "finished": "0xc0af",
        "error": "0xc0b0", "reserved": "0xc0b1"},
        "runtime terminal offsets drift")
    require(value["elf_state"]["successful_decode_tuple"]
            == {"phase": 13, "finished": 1, "error": 0},
            "successful decoder tuple drift")
    capture = value["capture"]
    require(capture["status"] == "host-specified-owner-authorization-pending",
            "capture row self-authorized")
    require(capture["observation"]["stop_count"] == 1
            and capture["observation"]["resume_count"] == 0,
            "single stopped-session contract drift")
    require(capture["data_rule"].startswith("Read the listed state as physical Bank-0"),
            "physical-data evidence rule drift")
    require(capture["claim_limit"].startswith("This specification authorizes no device access"),
            "authorization boundary drift")
    require(value["owner_observation"]["terminal"] == {
        "frame": "red", "background": "blue", "text": "E25",
        "prompt_visible": False}, "terminal observation drift")


def selftest() -> None:
    base = derive()
    verify(base)
    mutations: dict[str, Callable[[dict[str, Any]], None]] = {
        "wrong-error": lambda x: x["classification"]["error_code"].update(hex="0x24"),
        "collapse-split": lambda x: x["classification"].update(remaining_split=["c2_decode_from"]),
        "move-error-byte": lambda x: x["elf_state"]["terminal_offsets"].update(error="0xc0af"),
        "self-authorize": lambda x: x["capture"].update(status="device-authorized"),
        "raw-mapped-data": lambda x: x["capture"].update(data_rule="Read logical addresses directly."),
        "allow-resume": lambda x: x["capture"]["observation"].update(resume_count=1),
        "erase-e25": lambda x: x["owner_observation"]["terminal"].update(text=""),
    }
    rejected = 0
    for name, mutate in mutations.items():
        candidate = deepcopy(base)
        mutate(candidate)
        try:
            verify(candidate)
        except EvidenceError:
            rejected += 1
        else:
            raise EvidenceError(f"mutation survived: {name}")
    require(rejected == len(mutations), "mutation count drift")
    print(json.dumps({"status": "green", "mutations_rejected": rejected}, sort_keys=True))


def main() -> int:
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    if action == "selftest":
        selftest()
        return 0
    value = derive()
    verify(value)
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if action == "record":
        RECEIPT.write_bytes(raw)
        print(RECEIPT.relative_to(ROOT))
        return 0
    if action == "check":
        require(RECEIPT.read_bytes() == raw, "persisted E25 receipt drift")
        print(json.dumps({"status": "green", "receipt_sha256": sha(raw)}, sort_keys=True))
        return 0
    raise EvidenceError("usage: c2_v20_map_tuple_d1_e25.py record|check|selftest")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        print(f"c2-v20-map-tuple-d1-e25: {exc}", file=sys.stderr)
        raise SystemExit(1)
