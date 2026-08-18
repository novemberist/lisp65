#!/usr/bin/env python3
"""Bind the Link-113 D2 Bank-4 root-reader rescue capture.

The owner-authorized read stops the preserved ``trace-probe`` BADOPCODE once,
persists physical Banks 0, 4 and 5 raw-first, and never resumes the target.
The result is compared with both the historical poison object and the
canonical host compilation.  This checker deliberately separates the proven
product-path failure from the still-open question whether the cause is an
intrinsic Bank-4 MAP limitation or a Bank-4 case in the delivered mapper.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable
import zlib


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
from c2_v150_name_freight_d2_badopcode_capture import (  # noqa: E402
    FORM,
    POISONED_FORM,
    host_compile,
    stream,
    u16,
    u24,
    u32,
)


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
CAPTURE = ROOT / "build/c2.3/v2.1-link113-d2-root-reader-rescue"
ELF = ROOT / (
    "build/c2.3/v2.1-root-padding-configurator-parity-continuation/final/"
    "lisp65-c2-substitution-linked.prg.elf"
)
MEDIA = ARCH / "c2.3-v2.1-configurator-parity-completion-media-receipt.json"
ACCEPTANCE = ARCH / (
    "c2.3-v2.1-root-padding-configurator-parity-acceptance-receipt.json"
)
ROOT_FIX = ARCH / "c2.3-v2.1-probe-oracle-root-fix-receipt.json"
MAP_DEVICE = ARCH / (
    "c2.3-v2.0-loading-libraries-progress-map-device-receipt.json"
)
FLAT_CPU = ARCH / (
    "c2.3-v1.5.0-f018b-content-safe-read-pricing-receipt.json"
)
HISTORICAL = ARCH / (
    "c2.3-v1.5.0-name-freight-d2-defun-badopcode-capture-receipt.json"
)
RECEIPT = ARCH / (
    "c2.3-v2.1-link113-d2-bank4-root-reader-rescue-receipt.json"
)

AUTHORIZATION = "cdced6da"
FORMAT = "lisp65-c2.3-v2.1-link113-D2-bank4-root-reader-rescue-v1"
STATUS = "BANK4-MAP-CPU-PRODUCT-PATH-REFUTED"
STAGED_OFFSET = 0x6A00
STAGED_BYTES = 148
HISTORICAL_POISON_SHA = (
    "40acc5f061b755f2a2ddda4b6cbd64ac3bba9eae1c6295493411d38b09d86fcd"
)
POISON_CODE = bytes.fromhex(
    "b50100020b0001000006003d13013b0b01010205"
)
CANONICAL_CODE = bytes.fromhex("b50100020500000b01010205")


class RescueError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RescueError(message)


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


def git_authority() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE,
    ).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE,
    ).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in (
        "rescue read authorized",
        "banks 0, 4 and 5 raw-first",
        "historical poison object",
        "canonical host object",
        "no resume",
        "bank 4 was never probed",
    ):
        require(token in text, f"rescue authorization token absent: {token}")
    return {
        "authority": "git-blob", "commit": commit, "path": name,
        "bytes": len(raw), "sha256": sha(raw),
    }


def staged_object(bank4: bytes) -> dict[str, Any]:
    raw = bank4[STAGED_OFFSET:STAGED_OFFSET + STAGED_BYTES]
    require(len(raw) == STAGED_BYTES, "staged object outside captured Bank 4")
    require(
        raw[:4] == b"L65S"
        and raw[4:8] == bytes((4, 32, 32, 1))
        and u24(raw, 13) == STAGED_BYTES
        and raw[32:36] == b"SESS",
        "staged envelope drift",
    )
    code_off, code_len = u24(raw, 40), u16(raw, 43)
    meta_off, meta_len = u24(raw, 45), u16(raw, 48)
    require(
        (code_off, code_len, meta_off, meta_len) == (64, 20, 84, 64),
        "staged geometry drift",
    )
    require(
        u32(raw, 18) == (zlib.crc32(raw[32:64]) & 0xFFFFFFFF)
        and u32(raw, 50) == (zlib.crc32(raw[64:84]) & 0xFFFFFFFF)
        and u32(raw, 54) == (zlib.crc32(raw[84:148]) & 0xFFFFFFFF)
        and u32(raw, 58) == (zlib.crc32(raw[64:148]) & 0xFFFFFFFF),
        "staged object CRC mismatch",
    )
    code = raw[code_off:code_off + code_len]
    meta = raw[meta_off:meta_off + meta_len]
    require(code == POISON_CODE, "historical poison code no longer exact")
    require(
        meta[:24] == bytes.fromhex(
            "433249000218100800000100010018002800300010000000"
        )
        and meta[40:48] == bytes.fromhex("080001000d000000")
        and meta[48:64] == b"\x0b\x00trace-probe\x01\x00\xa0",
        "historical poison metadata no longer exact",
    )
    require(sha(raw) == HISTORICAL_POISON_SHA, "historical poison SHA drift")
    return {
        "physical_address": "0x00046a00",
        "source_domain": "Bank-4 EXT staging",
        "bytes": len(raw),
        "sha256": sha(raw),
        "all_CRCs_valid": True,
        "code": {
            "bytes": len(code), "hex": code.hex(),
            "canonical_bytes": len(CANONICAL_CODE),
            "canonical_hex": CANONICAL_CODE.hex(),
            "matches_canonical": code == CANONICAL_CODE,
            "matches_historical_poison": code == POISON_CODE,
        },
        "metadata": {
            "literal_count": code[6],
            "install_name": "trace-probe",
            "noncanonical_literal_byte": "0xa0",
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
    scalars = {
        name: u16(raw, 50 + index * 2) for index, name in enumerate(names)
    }
    require(
        decoder["phase"] == 10 and decoder["finished"] == 0
        and decoder["error"] == 7,
        "decoder no longer names phase-10 resolution refusal",
    )
    require(scalars == {
        "length": 148, "code_off": 64, "code_len": 20,
        "meta_off": 84, "meta_len": 64, "entries": 1,
        "literals": 1, "roots": 0, "old_images": 8,
        "old_entries": 771, "old_resolutions": 3348,
        "old_roots": 563, "new_images": 9, "new_entries": 772,
        "new_resolutions": 3349, "new_roots": 563,
    }, "append scalar state drift")
    require(
        u32(raw, 82) == 0 and raw[238:241] == bytes((1, 0, 0))
        and raw[302:304] == bytes((39, 128)),
        "clean rollback boundary drift",
    )

    def value(name: str, width: int | None = None) -> int:
        symbol = truth.symbol(name)
        size = symbol.bytes if width is None else width
        return int.from_bytes(bank0[symbol.value:symbol.value + size], "little")

    runtime = stream(bank0, truth.symbol("c2_runtime").value)
    scratch_at = truth.symbol("sym_name_scratch").value
    scratch = bank0[scratch_at:scratch_at + 34]
    require(scratch == b"\xa0" + b"\0" * 33,
            "resolution scratch no longer corroborates poison literal")
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
        runtime["image_count"] == 8 and runtime["entry_count"] == 771
        and runtime["resolution_count"] == 3348
        and runtime["phase"] == 13 and runtime["finished"] == 1
        and runtime["error"] == 0,
        "committed runtime changed despite rollback",
    )
    c2d_bytes = runtime["c2d_bytes"]
    require(bank5[c2d_bytes:c2d_bytes + 64] == b"\0" * 64,
            "C2J is not CLEAR")
    return {
        "decoder_context": decoder,
        "append_scalars": scalars,
        "staged": raw[238], "committed": raw[239],
        "rollback_rebuild_header": raw[240],
        "installer_trace": {"last_slot": raw[302], "flags": raw[303]},
        "committed_runtime": runtime,
        "C2J_CLEAR": True,
        "phase_owner": value("c2_phase_owner", 1),
        "vm_status_after_REPL_cleanup": value("vm_status", 1),
        "mem_oom": value("mem_oom", 1),
        "gc_badobj": value("gc_badobj"),
        "symbol_count": value("nsym"),
        "namepool_used": value("npool"),
        "sym_name_scratch_hex": scratch.hex(),
    }


def evidence_ledger() -> dict[str, Any]:
    root = load(ROOT_FIX)
    contract = root.get("source_contract", {})
    require(
        contract.get("mutable_readers", {}).get("Bank4_EXT") == [
            "ext_type", "ext_a", "ext_b", "ext_disk_get", "str_read_byte"
        ]
        and contract.get("mutable_readers", {}).get("Bank5_symbols") == [
            "sympool_read", "symval_get", "nameoff_get", "symfn_ext_get"
        ]
        and contract.get("reader_count") == 9,
        "nine-reader root-fix projection drift",
    )
    device = load(MAP_DEVICE)
    probe = device.get("probe", {})
    require(
        probe.get("decision") == "MAP-CPU-BANK5-AND-ATTIC-TARGET-GREEN"
        and probe.get("bank5") == probe.get("attic") == "PASS"
        and "Bank-5 and Attic" in device.get("claim_limit", "")
        and "Bank-4" not in device.get("claim_limit", ""),
        "MAP hardware proof scope drift",
    )
    flat = load(FLAT_CPU)
    require(
        flat.get("facts", {}).get("cpu_transport")
        == "rejected-by-bound-target-evidence",
        "historical flat-CPU rejection drift",
    )
    acceptance = load(ACCEPTANCE)
    absence = acceptance.get("structural_absence", {})
    require(
        absence.get("candidate_ELF", {}).get("sha256") == sha(ELF.read_bytes())
        and absence.get("unsafe_content_DMA_count") == 0
        and absence.get("born_derived", {}).get("mutable_caller_count") == 9,
        "exact Link-113 structural-absence authority drift",
    )
    return {
        "delivered_root_fix": contract,
        "hardware_MAP_proof": {
            "proved_domains": ["Bank-5", "Attic"],
            "reads_per_domain": 256,
            "Bank4_proved": False,
            "claim_limit": device["claim_limit"],
        },
        "historical_flat_CPU": flat["facts"]["cpu_transport"],
        "exact_Link113_unsafe_content_DMA_count": 0,
    }


def derive() -> dict[str, Any]:
    require((CAPTURE / "capture-complete").is_file(),
            "capture completion absent")
    bank0 = (CAPTURE / "physical-bank0.bin").read_bytes()
    bank4 = (CAPTURE / "physical-bank4.bin").read_bytes()
    bank5 = (CAPTURE / "physical-bank5.bin").read_bytes()
    require(
        (len(bank0), len(bank4), len(bank5)) == (65536, 27648, 50816),
        "capture range length drift",
    )
    registers = load(CAPTURE / "registers.json")
    expected_registers = {
        "A": "0x01", "B": "0x00", "MAPH": "0x8000",
        "MAPL": "0x0000", "PC": "0xe000", "SP": "0x01d8",
        "X": "0xcf", "Y": "0x00", "Z": "0x00",
    }
    require(
        {key: registers.get(key) for key in expected_registers}
        == expected_registers,
        "stopped register tuple drift",
    )
    truth = ElfTruth.read(
        ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=False,
    )
    staged = staged_object(bank4)
    host_good = host_compile(FORM)
    host_poison = host_compile(POISONED_FORM)
    require(
        host_good.get("encoded_hex") == CANONICAL_CODE.hex()
        and host_good.get("literal_count") == 0
        and host_poison.get("encoded_hex")
        == "b50100020b00010c0006003d13013b0b01010205"
        and host_poison.get("payload_hex") == staged["code"]["hex"][18:],
        "host canonical/poison controls drift",
    )
    historical = load(HISTORICAL)
    require(
        historical.get("staged_object", {}).get("sha256")
        == staged["sha256"]
        and historical.get("staged_object", {}).get("code", {}).get("hex")
        == staged["code"]["hex"],
        "historical poison identity control drift",
    )
    media = load(MEDIA)
    require(
        media.get("media", {}).get("product", {}).get("d81", {}).get(
            "sha256") ==
        "bce9b795c78dc859eb834231f0a1f7c41dee80ada33b026b58d9acd3da60be3d"
        or "bce9b795c78dc859eb834231f0a1f7c41dee80ada33b026b58d9acd3da60be3d"
        in MEDIA.read_text(encoding="utf-8"),
        "Link-113 media identity drift",
    )
    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-17",
        "status": STATUS,
        "capture": {
            "registers": registers,
            "CPU_remains_stopped": True,
            "device_stops": 1,
            "device_resumes": 0,
            "physical_reads": [bind(CAPTURE / name) for name in (
                "physical-bank0.bin", "physical-bank4.bin",
                "physical-bank5.bin")],
        },
        "three_way_comparison": {
            "captured_form": FORM,
            "canonical_host": host_good,
            "historical_poison_form": host_poison,
            "staged_object": staged,
            "staged_equals_historical_poison_object": True,
            "staged_equals_canonical_host_code": False,
        },
        "stopped_state": stopped_state(bank0, bank5, truth),
        "evidence_ledger": evidence_ledger(),
        "conclusion": {
            "product_path_membership": True,
            "Bank4_root_generalization_refuted": True,
            "mechanism": (
                "the delivered MAP-CPU path serving Bank-4 EXT compiler "
                "inputs reproduced the exact historical poison object"
            ),
            "guard_behavior": (
                "correct phase-10 decoder refusal and clean rollback; no C2D commit"
            ),
            "intrinsic_Bank4_MAP_unreadability_proven": False,
            "remaining_split": (
                "intrinsic Bank-4 MAP semantics versus a Bank-4 case in the "
                "delivered reader's tuple/pointer implementation"
            ),
            "fix_authorized": False,
            "next": "owner disposition for a Bank-4-specific MAP attribution",
        },
        "claim_limit": (
            "This capture proves the current Bank-4 mutable-read product path "
            "is not content-correct and reproduces the historical poison "
            "object. It does not yet distinguish intrinsic Bank-4 MAP "
            "semantics from a Bank-4 implementation case, authorize a fix, "
            "resume the device, or open D3-D5."
        ),
        "authority": {
            "owner": git_authority(),
            "ELF": bind(ELF),
            "media": bind(MEDIA),
            "acceptance": bind(ACCEPTANCE),
            "root_fix": bind(ROOT_FIX),
            "MAP_device": bind(MAP_DEVICE),
            "flat_CPU": bind(FLAT_CPU),
            "historical_poison": bind(HISTORICAL),
            "checker": bind(Path(__file__)),
        },
        "execution_accounting": {
            "WPLTO": 0, "links": 0, "product_bytes_changed": 0,
            "device_stops": 1, "device_resumes": 0,
        },
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    comparison = value["three_way_comparison"]
    staged = comparison["staged_object"]
    state = value["stopped_state"]
    conclusion = value["conclusion"]
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "capture identity drift")
    require(
        staged["sha256"] == HISTORICAL_POISON_SHA
        and staged["all_CRCs_valid"] is True
        and staged["code"]["matches_historical_poison"] is True
        and staged["code"]["matches_canonical"] is False
        and comparison["staged_equals_historical_poison_object"] is True
        and comparison["staged_equals_canonical_host_code"] is False,
        "three-way poison classification lost",
    )
    require(
        state["decoder_context"]["phase"] == 10
        and state["decoder_context"]["error"] == 7
        and state["staged"] == 1 and state["committed"] == 0
        and state["C2J_CLEAR"] is True and state["mem_oom"] == 0,
        "phase-10 rollback evidence lost",
    )
    require(
        conclusion["product_path_membership"] is True
        and conclusion["Bank4_root_generalization_refuted"] is True
        and conclusion["intrinsic_Bank4_MAP_unreadability_proven"] is False
        and conclusion["fix_authorized"] is False,
        "Bank-4 claim boundary drift",
    )
    require(
        value["capture"]["CPU_remains_stopped"] is True
        and value["capture"]["device_resumes"] == 0,
        "stopped-state discipline drift",
    )


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "change-staged-SHA": lambda x: x["three_way_comparison"]
            ["staged_object"].__setitem__("sha256", "0" * 64),
        "normalize-code": lambda x: x["three_way_comparison"]
            ["staged_object"]["code"].__setitem__("matches_canonical", True),
        "deny-poison-match": lambda x: x["three_way_comparison"]
            ["staged_object"]["code"].__setitem__(
                "matches_historical_poison", False),
        "break-CRC": lambda x: x["three_way_comparison"]
            ["staged_object"].__setitem__("all_CRCs_valid", False),
        "erase-resolution-error": lambda x: x["stopped_state"]
            ["decoder_context"].__setitem__("error", 0),
        "move-decoder-phase": lambda x: x["stopped_state"]
            ["decoder_context"].__setitem__("phase", 9),
        "claim-commit": lambda x: x["stopped_state"].__setitem__("committed", 1),
        "dirty-C2J": lambda x: x["stopped_state"].__setitem__("C2J_CLEAR", False),
        "invent-OOM": lambda x: x["stopped_state"].__setitem__("mem_oom", 1),
        "deny-product-membership": lambda x: x["conclusion"].__setitem__(
            "product_path_membership", False),
        "preserve-bank4-generalization": lambda x: x["conclusion"].__setitem__(
            "Bank4_root_generalization_refuted", False),
        "overclaim-intrinsic-hardware": lambda x: x["conclusion"].__setitem__(
            "intrinsic_Bank4_MAP_unreadability_proven", True),
        "silently-authorize-fix": lambda x: x["conclusion"].__setitem__(
            "fix_authorized", True),
        "resume": lambda x: x["capture"].__setitem__(
            "CPU_remains_stopped", False),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except RescueError:
            rejected.append(name)
    require(rejected == list(cases), "Bank-4 rescue mutation survived")
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
        require(load(RECEIPT) == value, "Bank-4 rescue receipt stale")
    else:
        require(len(value["mutations_rejected"]) == 14,
                "mutation count drift")
    print(
        f"Link-113 Bank-4 rescue: PASS action={action} "
        "poison=exact mutations=14 CPU=stopped"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RescueError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"Link-113 Bank-4 rescue: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
