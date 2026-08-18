#!/usr/bin/env python3
"""Bind the corrected Link-112 D2 probe-oracle capture.

The preserved state belongs to the owner's follow-up ``test-probe`` form,
not to the immediately preceding ``trace-probe`` First Red.  This checker
keeps that boundary explicit while binding the stronger reproducibility fact:
a fresh name produced a different staged object with the same twenty corrupt
code bytes and the same non-canonical ``$a0`` literal byte.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable
import zlib


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
from c2_v150_name_freight_d2_badopcode_capture import (  # noqa: E402
    stream,
    u16,
    u24,
    u32,
)


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CAPTURE = ROOT / "build/c2.3/v2.1-link112-d2-full-span-oracle-capture"
ELF = ROOT / (
    "build/c2.3/v2.1-full-span-convergence-card/final/"
    "lisp65-c2-substitution-linked.prg.elf"
)
MEDIA = ARCH / "c2.3-v2.1-full-span-completion-media-receipt.json"
HISTORICAL = ARCH / (
    "c2.3-v1.5.0-name-freight-d2-defun-badopcode-capture-receipt.json"
)
PREDECESSOR = ARCH / "c2.3-v2.1-link111-d2-partial-span-capture-receipt.json"
RECEIPT = ARCH / "c2.3-v2.1-link112-d2-probe-oracle-capture-receipt.json"

FORMAT = "lisp65-c2.3-v2.1-link112-D2-probe-oracle-capture-v1"
STATUS = "PROBE-ORACLE-F018B-REPRODUCED-WITH-FRESH-NAME"
STAGED_OFFSET = 0x6A00
STAGED_BYTES = 148
STAGED_SHA = "a1029fc815207908304659dda52576334743e869101bb999d78cba61f35d0626"
CORRUPT_CODE = bytes.fromhex("b50100020b0001000006003d13013b0b01010205")


class CaptureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CaptureError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def staged_object(bank4: bytes) -> dict[str, Any]:
    raw = bank4[STAGED_OFFSET:STAGED_OFFSET + STAGED_BYTES]
    require(len(raw) == STAGED_BYTES, "staged object outside captured Bank 4")
    require(raw[:4] == b"L65S" and raw[4:8] == bytes((4, 32, 32, 1))
            and u24(raw, 13) == STAGED_BYTES and raw[32:36] == b"SESS",
            "test-probe staged envelope drift")
    code_off, code_len = u24(raw, 40), u16(raw, 43)
    meta_off, meta_len = u24(raw, 45), u16(raw, 48)
    require((code_off, code_len, meta_off, meta_len) == (64, 20, 84, 64),
            "test-probe staged geometry drift")
    require(
        u32(raw, 18) == (zlib.crc32(raw[32:64]) & 0xFFFFFFFF)
        and u32(raw, 50) == (zlib.crc32(raw[64:84]) & 0xFFFFFFFF)
        and u32(raw, 54) == (zlib.crc32(raw[84:148]) & 0xFFFFFFFF)
        and u32(raw, 58) == (zlib.crc32(raw[64:148]) & 0xFFFFFFFF),
        "test-probe staged CRC mismatch")
    code = raw[code_off:code_off + code_len]
    meta = raw[meta_off:meta_off + meta_len]
    require(code == CORRUPT_CODE, "fresh-name corruption code drift")
    require(meta[:20] == bytes.fromhex(
        "4332490002181008000001000100180028003000"),
        "test-probe C2I header drift")
    descriptor = meta[40:48]
    strings = meta[48:64]
    require(descriptor == bytes.fromhex("080001000c000000")
            and strings == b"\x0a\x00test-probe\x01\x00\xa0\x00",
            "test-probe name/literal pool drift")
    require(sha(raw) == STAGED_SHA, "fresh staged-object identity drift")
    return {
        "physical_address": "0x00046a00", "bytes": len(raw),
        "sha256": sha(raw), "all_CRCs_valid": True,
        "install_name": "test-probe", "fresh_name": True,
        "code": {"bytes": len(code), "hex": code.hex()},
        "metadata": {
            "literal_descriptor_hex": descriptor.hex(),
            "strings": [
                {"offset": 0, "length": 10, "bytes": "test-probe"},
                {"offset": 12, "length": 1, "hex": "a0",
                 "canonical_ASCII": False},
            ],
        },
    }


def stopped_state(bank0: bytes, bank5: bytes, truth: ElfTruth) -> dict[str, Any]:
    base = truth.symbol("lisp65_c2_phase_scratch").value
    raw = bank0[base:base + 304]
    require(len(raw) == 304, "phase scratch capture incomplete")
    decoder = stream(raw, 4)
    names = (
        "length", "code_off", "code_len", "meta_off", "meta_len",
        "entries", "literals", "roots", "old_images", "old_entries",
        "old_resolutions", "old_roots", "new_images", "new_entries",
        "new_resolutions", "new_roots",
    )
    scalars = {name: u16(raw, 50 + index * 2)
               for index, name in enumerate(names)}
    expected = {
        "length": 148, "code_off": 64, "code_len": 20,
        "meta_off": 84, "meta_len": 64, "entries": 1,
        "literals": 1, "roots": 0, "old_images": 8,
        "old_entries": 771, "old_resolutions": 3348, "old_roots": 563,
        "new_images": 9, "new_entries": 772,
        "new_resolutions": 3349, "new_roots": 563,
    }
    require(decoder["phase"] == 10 and decoder["finished"] == 0
            and decoder["error"] == 7 and scalars == expected
            and u32(raw, 82) == 0 and raw[238:241] == bytes((1, 0, 0))
            and raw[302:304] == bytes((39, 128)),
            "phase-10 clean-rollback boundary drift")

    def value(name: str, width: int | None = None) -> int:
        symbol = truth.symbol(name)
        size = symbol.bytes if width is None else width
        return int.from_bytes(bank0[symbol.value:symbol.value + size], "little")

    runtime = stream(bank0, truth.symbol("c2_runtime").value)
    scratch_at = truth.symbol("sym_name_scratch").value
    scratch = bank0[scratch_at:scratch_at + 34]
    require(scratch == b"\xa0\0test-probe" + b"\0" * 22,
            "resolution scratch no longer corroborates fresh name")
    require(value("c2_journal_count") == 0 and value("vm_status", 1) == 0
            and value("mem_oom", 1) == 0 and value("gc_badobj") == 0
            and value("c2_phase_owner", 1) == 0 and value("c2_ready", 1) == 1,
            "clean stopped-state exclusions drift")
    require(runtime["image_count"] == 8 and runtime["entry_count"] == 771
            and runtime["resolution_count"] == 3348
            and runtime["phase"] == 13 and runtime["finished"] == 1
            and runtime["error"] == 0,
            "committed runtime changed despite rollback")
    require(bank5[runtime["c2d_bytes"]:runtime["c2d_bytes"] + 64] == b"\0" * 64,
            "C2J is not CLEAR")
    return {
        "decoder_context": decoder, "append_scalars": scalars,
        "staged": raw[238], "committed": raw[239],
        "rollback_rebuild_header": raw[240],
        "installer_trace": {"last_slot": raw[302], "flags": raw[303]},
        "committed_runtime": runtime, "C2J_CLEAR": True,
        "phase_owner": value("c2_phase_owner", 1),
        "vm_status_after_REPL_cleanup": value("vm_status", 1),
        "mem_oom": value("mem_oom", 1), "gc_badobj": value("gc_badobj"),
        "symbol_count": value("nsym"), "namepool_used": value("npool"),
        "sym_name_scratch_hex": scratch.hex(),
    }


def derive() -> dict[str, Any]:
    bank0 = (CAPTURE / "physical-bank0.bin").read_bytes()
    bank4 = (CAPTURE / "physical-bank4.bin").read_bytes()
    bank5 = (CAPTURE / "physical-bank5.bin").read_bytes()
    require((len(bank0), len(bank4), len(bank5)) == (65536, 27648, 50816),
            "capture range length drift")
    registers = load(CAPTURE / "registers.json")
    expected_registers = {
        "A": "0x01", "B": "0x00", "MAPH": "0x8000",
        "MAPL": "0x0000", "PC": "0xe000", "SP": "0x01d8",
        "X": "0xcf", "Y": "0x00", "Z": "0x00",
    }
    require({key: registers.get(key) for key in expected_registers}
            == expected_registers, "stopped register tuple drift")
    truth = ElfTruth.read(ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
                          include_section_data=False)
    staged = staged_object(bank4)
    historical = load(HISTORICAL)["staged_object"]
    predecessor = load(PREDECESSOR)["staged_object"]
    require(historical["code"]["hex"] == predecessor["code"]["hex"]
            == staged["code"]["hex"] and historical["sha256"] != STAGED_SHA,
            "fresh-name versus historical-code control drift")
    media = load(MEDIA)
    require(media.get("status") ==
            "PASS: Link 112 completed and same-world full-span media closed",
            "Link-112 media authority drift")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-16", "status": STATUS,
        "capture": {
            "registers": registers, "CPU_remains_stopped": True,
            "device_stops": 1, "device_resumes": 0,
            "physical_reads": [bind(CAPTURE / name) for name in (
                "physical-bank0.bin", "physical-bank4.bin", "physical-bank5.bin")],
        },
        "staged_object": staged,
        "stopped_state": stopped_state(bank0, bank5, truth),
        "historical_control": {
            "historical_receipt": bind(HISTORICAL),
            "Link111_capture": bind(PREDECESSOR),
            "historical_staged_sha256": historical["sha256"],
            "fresh_staged_sha256": STAGED_SHA,
            "different_object_identity": True,
            "identical_corruption_codebytes": True,
            "same_noncanonical_literal_byte": "0xa0",
        },
        "claim_boundary": {
            "captured_form": "(defun test-probe (x) (+ x 1))",
            "immediately_preceding_trace_probe_red_stopped_state_bound": False,
            "fresh_name_reproduces_same_mechanism": True,
            "fix_authorized": False, "device_resume_authorized": False,
            "D3_D5_open": False,
        },
        "authority": {"ELF": bind(ELF), "media": bind(MEDIA),
                      "checker": bind(Path(__file__))},
        "execution_accounting": {"WPLTO": 0, "links": 0,
            "product_bytes_changed": 0, "device_stops": 1,
            "device_resumes": 0},
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    staged = value["staged_object"]
    state = value["stopped_state"]
    boundary = value["claim_boundary"]
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "capture identity drift")
    require(staged["sha256"] == STAGED_SHA and staged["all_CRCs_valid"] is True
            and staged["code"]["hex"] == CORRUPT_CODE.hex()
            and staged["metadata"]["strings"][1]["hex"] == "a0",
            "fresh-name corruption evidence lost")
    require(state["decoder_context"]["phase"] == 10
            and state["decoder_context"]["error"] == 7
            and state["staged"] == 1 and state["committed"] == 0
            and state["C2J_CLEAR"] is True and state["mem_oom"] == 0,
            "phase-10 rollback evidence lost")
    require(boundary == {
        "captured_form": "(defun test-probe (x) (+ x 1))",
        "immediately_preceding_trace_probe_red_stopped_state_bound": False,
        "fresh_name_reproduces_same_mechanism": True,
        "fix_authorized": False, "device_resume_authorized": False,
        "D3_D5_open": False,
    }, "corrected claim boundary drift")
    require(value["capture"]["CPU_remains_stopped"] is True
            and value["capture"]["device_resumes"] == 0,
            "stopped-state discipline drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rename-captured-form": lambda x: x["claim_boundary"].__setitem__(
            "captured_form", "(defun trace-probe (x) (+ x 1))"),
        "inherit-trace-stop": lambda x: x["claim_boundary"].__setitem__(
            "immediately_preceding_trace_probe_red_stopped_state_bound", True),
        "deny-fresh-reproduction": lambda x: x["claim_boundary"].__setitem__(
            "fresh_name_reproduces_same_mechanism", False),
        "change-code": lambda x: x["staged_object"]["code"].__setitem__(
            "hex", "00" * 20),
        "normalize-literal": lambda x: x["staged_object"]["metadata"]
            ["strings"][1].__setitem__("hex", "2b"),
        "break-CRC": lambda x: x["staged_object"].__setitem__(
            "all_CRCs_valid", False),
        "erase-phase-error": lambda x: x["stopped_state"]["decoder_context"]
            .__setitem__("error", 0),
        "claim-commit": lambda x: x["stopped_state"].__setitem__("committed", 1),
        "invent-OOM": lambda x: x["stopped_state"].__setitem__("mem_oom", 1),
        "silently-authorize-fix": lambda x: x["claim_boundary"].__setitem__(
            "fix_authorized", True),
        "open-D3": lambda x: x["claim_boundary"].__setitem__("D3_D5_open", True),
        "resume": lambda x: x["capture"].__setitem__("CPU_remains_stopped", False),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except CaptureError:
            rejected.append(name)
    require(rejected == list(cases), "probe-oracle capture mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    value = derive()
    value["mutations_rejected"] = mutations(value)
    if action == "record":
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        require(load(RECEIPT) == value, "probe-oracle capture receipt stale")
    else:
        require(len(value["mutations_rejected"]) == 12, "mutation count drift")
    print(f"Link-112 probe-oracle capture: PASS action={action} mutations=12")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CaptureError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"Link-112 probe-oracle capture: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
