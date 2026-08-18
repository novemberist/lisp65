#!/usr/bin/env python3
"""Classify the preserved Link-111 D2 partial-span First Red.

The device was stopped exactly once after ``defun trace-probe`` returned
``VM_BADOPCODE`` to a usable REPL.  This checker binds the three raw physical
reads, reconstructs the staged object and append state, and compares the
staged bytes with the independently bound historical F018B capture.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
from c2_v150_name_freight_d2_badopcode_capture import (  # noqa: E402
    staged_object,
    stream,
    u16,
    u32,
)


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CAPTURE = ROOT / "build/c2.3/v2.1-link111-d2-partial-span-capture"
ELF = ROOT / (
    "build/c2.3/v2.1-terminal-screen-lease-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf"
)
DESK = ARCH / "c2.3-v2.1-link111-d2-partial-span-desk-receipt.json"
HISTORICAL = ARCH / (
    "c2.3-v1.5.0-name-freight-d2-defun-badopcode-capture-receipt.json"
)
RECEIPT = ARCH / "c2.3-v2.1-link111-d2-partial-span-capture-receipt.json"

FORMAT = "lisp65-c2.3-v2.1-link111-D2-partial-span-capture-v1"
STATUS = "PARTIAL-SPAN-F018B-TARGET-MEMBERSHIP-PROVEN"
STAGED_SHA = "40acc5f061b755f2a2ddda4b6cbd64ac3bba9eae1c6295493411d38b09d86fcd"


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
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def append_state(bank0: bytes, truth: ElfTruth) -> dict[str, Any]:
    base = truth.symbol("lisp65_c2_phase_scratch").value
    raw = bank0[base:base + 304]
    require(len(raw) == 304, "phase scratch capture incomplete")
    context = stream(raw, 4)
    scalar_names = (
        "length", "code_off", "code_len", "meta_off", "meta_len",
        "entries", "literals", "roots", "old_images", "old_entries",
        "old_resolutions", "old_roots", "new_images", "new_entries",
        "new_resolutions", "new_roots",
    )
    scalars = {
        name: u16(raw, 50 + index * 2)
        for index, name in enumerate(scalar_names)
    }
    scalars["attic"] = u32(raw, 82)
    expected_scalars = {
        "length": 148, "code_off": 64, "code_len": 20,
        "meta_off": 84, "meta_len": 64, "entries": 1,
        "literals": 1, "roots": 0, "old_images": 8,
        "old_entries": 771, "old_resolutions": 3348,
        "old_roots": 563, "new_images": 9, "new_entries": 772,
        "new_resolutions": 3349, "new_roots": 563, "attic": 0,
    }
    require(
        context["phase"] == 10 and context["finished"] == 0
        and context["error"] == 7,
        "append decoder no longer names phase-10 resolution failure",
    )
    require(scalars == expected_scalars, "Link-111 append scalars drift")
    require(raw[238:241] == bytes((1, 0, 0)),
            "staged/committed/rollback flags drift")
    require(raw[302:304] == bytes((39, 128)),
            "cleanup trace drift")
    return {
        "decoder_context": context,
        "append_scalars": scalars,
        "staged": raw[238],
        "committed": raw[239],
        "rollback_rebuild_header": raw[240],
        "installer_trace": {
            "last_slot": raw[302],
            "flags": raw[303],
            "interpretation": (
                "cleanup/rollback provenance only; phase-10 decoder state "
                "names the forward failure"
            ),
        },
    }


def target_state(bank0: bytes, bank5: bytes, truth: ElfTruth) -> dict[str, Any]:
    def value(name: str, size: int | None = None) -> int:
        symbol = truth.symbol(name)
        width = size if size is not None else symbol.bytes
        return int.from_bytes(bank0[symbol.value:symbol.value + width], "little")

    runtime_at = truth.symbol("c2_runtime").value
    runtime = stream(bank0, runtime_at)
    scratch_at = truth.symbol("sym_name_scratch").value
    scratch = bank0[scratch_at:scratch_at + 34]
    require(scratch == b"\xa0" + b"\0" * 33,
            "sym_name_scratch no longer corroborates staged non-name")
    require(
        value("c2_journal_count") == 0
        and value("vm_status", 1) == 0
        and value("mem_oom", 1) == 0
        and value("gc_badobj") == 0
        and value("c2_phase_owner", 1) == 0
        and value("c2_ready", 1) == 1,
        "clean stopped-state exclusions drift",
    )
    require(
        runtime["image_count"] == 8
        and runtime["entry_count"] == 771
        and runtime["resolution_count"] == 3348
        and runtime["image_cursor"] == 563
        and runtime["phase"] == 13
        and runtime["finished"] == 1
        and runtime["error"] == 0,
        "committed runtime changed despite rollback",
    )
    journal_at = runtime["c2d_bytes"]
    require(bank5[journal_at:journal_at + 64] == b"\0" * 64,
            "C2J is not CLEAR")
    return {
        "committed_runtime": runtime,
        "c2_journal_count": value("c2_journal_count"),
        "C2J_CLEAR": True,
        "phase_owner": value("c2_phase_owner", 1),
        "vm_status_after_REPL_cleanup": value("vm_status", 1),
        "mem_oom": value("mem_oom", 1),
        "gc_badobj": value("gc_badobj"),
        "gc_runs": value("gc_runs"),
        "symbol_count": value("nsym"),
        "namepool_used": value("npool"),
        "sym_name_scratch_hex": scratch.hex(),
    }


def derive() -> dict[str, Any]:
    require((CAPTURE / "capture-complete").read_text(encoding="ascii") ==
            "CPU stopped; no resume\n", "capture completion discipline drift")
    bank0 = (CAPTURE / "physical-bank0.bin").read_bytes()
    bank4 = (CAPTURE / "physical-bank4.bin").read_bytes()
    bank5 = (CAPTURE / "physical-bank5.bin").read_bytes()
    require((len(bank0), len(bank4), len(bank5)) == (65536, 27648, 50816),
            "capture range length drift")
    truth = ElfTruth.read(
        ELF,
        llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=False,
    )
    registers = load(CAPTURE / "registers.json")
    expected_registers = {
        "A": "0xcf", "B": "0x00", "MAPH": "0x8000",
        "MAPL": "0x0000", "PC": "0xe004", "SP": "0x01d8",
        "X": "0xcf", "Y": "0x00", "Z": "0x00",
    }
    require({name: registers.get(name) for name in expected_registers}
            == expected_registers, "stopped register tuple drift")

    staged = staged_object(bank4)
    historical = load(HISTORICAL)
    historical_staged = historical.get("staged_object", {})
    require(
        staged["sha256"] == STAGED_SHA
        and historical_staged.get("sha256") == STAGED_SHA
        and staged == historical_staged,
        "current staged object no longer byteequals historical F018B poison",
    )
    desk = load(DESK)
    require(
        desk.get("status") ==
            "PARTIAL-SPAN-VERIFIER-DEFECT-PROVEN; TARGET-MEMBERSHIP-PENDING",
        "partial-span desk authority drift",
    )

    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-16",
        "status": STATUS,
        "capture": {
            "registers": registers,
            "CPU_remains_stopped": True,
            "device_stops": 1,
            "device_resumes": 0,
            "physical_reads": [
                bind(CAPTURE / "physical-bank0.bin"),
                bind(CAPTURE / "physical-bank4.bin"),
                bind(CAPTURE / "physical-bank5.bin"),
            ],
        },
        "append": append_state(bank0, truth),
        "staged_object": staged,
        "historical_control": {
            "receipt": bind(HISTORICAL),
            "staged_object_sha256": STAGED_SHA,
            "current_staged_object_byteidentical": True,
            "same_terminal_surface": "defun trace-probe -> VM_BADOPCODE",
        },
        "target_state": target_state(bank0, bank5, truth),
        "conclusion": {
            "mechanism": (
                "the first-difference-only convergence verifier returned "
                "before the complete requested span was content-converged"
            ),
            "evidence_chain": [
                "the delivered primitive accepts the retained first byte without a full-span rescan",
                "the current target staged the exact historical poisoned object byte for byte",
                "phase 10 rejected its noncanonical 0xa0 resolution name",
                "rollback left C2J CLEAR and the committed runtime unchanged",
            ],
            "partial_span_F018B_family_membership": True,
            "product_guard_behavior": "correct fail-closed rollback; no C2D commit",
            "slot39_correction": (
                "slot 39 is cleanup/rollback provenance and does not name the forward failure"
            ),
            "fix_authorized": False,
            "D3_D5_open": False,
            "next": (
                "owner disposition for pricing a verifier that covers the whole span under real partial transfers"
            ),
        },
        "claim_limit": (
            "This capture proves target membership and the failure mechanism. "
            "It authorizes no fix, relink, media rebuild, resume, or D3-D5 continuation."
        ),
        "authority": {
            "desk_receipt": bind(DESK),
            "historical_capture": bind(HISTORICAL),
            "ELF": bind(ELF),
            "capture_checker": bind(Path(__file__)),
        },
        "execution_accounting": {
            "product_bytes_changed": 0,
            "links": 0,
            "WPLTO": 0,
            "device_contacts": 1,
            "device_stops": 1,
            "device_resumes": 0,
        },
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "capture identity drift")
    append = value["append"]
    require(
        append["decoder_context"]["phase"] == 10
        and append["decoder_context"]["error"] == 7
        and append["staged"] == 1
        and append["committed"] == 0,
        "phase-10 precommit boundary lost",
    )
    staged = value["staged_object"]
    require(
        staged["sha256"] == STAGED_SHA
        and staged["all_CRCs_valid"] is True
        and staged["metadata"]["strings"][1] == {
            "offset": 13, "length": 1, "hex": "a0",
            "canonical_ASCII": False,
        },
        "poisoned staged-object evidence lost",
    )
    require(value["historical_control"]["current_staged_object_byteidentical"] is True,
            "historical byteidentity lost")
    require(
        value["target_state"]["C2J_CLEAR"] is True
        and value["target_state"]["mem_oom"] == 0
        and value["target_state"]["phase_owner"] == 0,
        "clean rollback/resource exclusion lost",
    )
    conclusion = value["conclusion"]
    require(
        conclusion["partial_span_F018B_family_membership"] is True
        and conclusion["fix_authorized"] is False
        and conclusion["D3_D5_open"] is False,
        "membership or authorization boundary drift",
    )
    require(
        value["capture"]["CPU_remains_stopped"] is True
        and value["capture"]["device_resumes"] == 0
        and value["execution_accounting"]["device_resumes"] == 0,
        "stopped-state discipline drift",
    )


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "move-decoder-phase": lambda x: x["append"]["decoder_context"].__setitem__("phase", 9),
        "erase-resolution-error": lambda x: x["append"]["decoder_context"].__setitem__("error", 0),
        "claim-commit": lambda x: x["append"].__setitem__("committed", 1),
        "change-staged-sha": lambda x: x["staged_object"].__setitem__("sha256", "0" * 64),
        "normalize-symbol-byte": lambda x: x["staged_object"]["metadata"]["strings"].__setitem__(
            1, {"offset": 13, "length": 1, "hex": "2b", "canonical_ASCII": True}),
        "break-staged-CRC": lambda x: x["staged_object"].__setitem__("all_CRCs_valid", False),
        "deny-historical-identity": lambda x: x["historical_control"].__setitem__(
            "current_staged_object_byteidentical", False),
        "invent-OOM": lambda x: x["target_state"].__setitem__("mem_oom", 1),
        "invent-phase-owner": lambda x: x["target_state"].__setitem__("phase_owner", 1),
        "withdraw-membership": lambda x: x["conclusion"].__setitem__(
            "partial_span_F018B_family_membership", False),
        "silently-authorize-fix": lambda x: x["conclusion"].__setitem__("fix_authorized", True),
        "open-D3": lambda x: x["conclusion"].__setitem__("D3_D5_open", True),
        "resume-after-capture": lambda x: x["capture"].__setitem__("CPU_remains_stopped", False),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except CaptureError:
            rejected.append(name)
    require(rejected == list(cases), "capture-result mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    value = derive()
    value["mutations_rejected"] = mutations(value)
    if action == "record":
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        require(load(RECEIPT) == value, "Link-111 D2 capture receipt stale")
    else:
        require(len(value["mutations_rejected"]) == 13, "mutation count drift")
    print(f"Link-111 D2 partial-span capture: PASS action={action} mutations=13")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CaptureError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Link-111 D2 partial-span capture: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
