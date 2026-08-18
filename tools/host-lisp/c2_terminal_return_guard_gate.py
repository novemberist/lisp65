#!/usr/bin/env python3
"""Prove terminal-ingress return shadowing, logging and restoration.

The product implementation is deliberately a small naked 65CE02 wrapper at
each of the four persistent-publication overlay entries.  This gate binds the
linked instruction stream, the complete persistent plan, the already-owned
phase-owner byte, the owner-free/zero-delivered shadow arena and a semantic
model of clean, repair and fail-closed outcomes.  It never treats the wrapper's
own arm byte as proof that a transfer completed.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from elf_truth import ElfTruth


ROOT = Path(__file__).resolve().parents[2]
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
RUNTIME = ROOT / "src/c2_product_runtime.c"
SCRATCH = ROOT / "src/c2_phase_scratch.c"
OWNER_AUTHORITY = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-boot-order-durable-witness-receipt.json"
)
COMMISSION = ROOT / "docs/planning/post-v1.4.0-direction-plan.md"
COMMISSION_PREFIX_BYTES = 72691
COMMISSION_PREFIX_SHA256 = (
    "0868997f94ec97f586350cecf8e7a95495a16d6247f1652f352964b613f94424"
)

ARM = 0xB582
SHADOW = (0xB583, 0xB584, 0xB585)
ARENA_START = 0xB582
ARENA_END = 0xB592
OWNER_GAP_END = 0xB5C4
PHASE_OWNER_ZP = 0x89
APPEND_OWNER = 2
PLAN = bytes((37, 38, 39, 40, 0))
PHASES = (
    ("header", "c2_append_header_phase", "c2tr_header_body", 1),
    ("publish_plan_scan", "c2_append_publish_plan_scan_phase",
     "c2tr_publish_plan_scan_body", 2),
    ("publish_plan_resolve", "c2_append_publish_plan_resolve_phase",
     "c2tr_publish_plan_resolve_body", 3),
    ("publish_clear", "c2_append_publish_clear_phase",
     "c2tr_publish_clear_body", 4),
)


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": sha(data),
    }


def bind_commission_prefix() -> dict[str, Any]:
    """Preserve the accepted commission while allowing later plan entries."""
    require(COMMISSION.is_file() and not COMMISSION.is_symlink(),
            f"authority absent: {COMMISSION}")
    current = COMMISSION.read_bytes()
    prefix = current[:COMMISSION_PREFIX_BYTES]
    require(
        len(prefix) == COMMISSION_PREFIX_BYTES
        and sha(prefix) == COMMISSION_PREFIX_SHA256,
        "terminal-return-guard historical commission prefix drift")
    return {
        "path": COMMISSION.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": COMMISSION_PREFIX_BYTES,
        "sha256": COMMISSION_PREFIX_SHA256,
    }


def symbol_body(truth: ElfTruth, name: str) -> tuple[Any, bytes]:
    symbol = truth.symbol(name)
    require(symbol.bytes > 0, f"unsized terminal symbol: {name}")
    section = truth.section(symbol.section)
    start = symbol.value - section.address
    body = truth.section_bytes(symbol.section)[start:start + symbol.bytes]
    require(len(body) == symbol.bytes, f"terminal symbol extraction drift: {name}")
    return symbol, body


class WrapperImage:
    def __init__(self) -> None:
        self.data = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str]] = []

    def emit(self, *values: int) -> None:
        self.data.extend(value & 0xff for value in values)

    def word(self, opcode: int, address: int) -> None:
        self.emit(opcode, address, address >> 8)

    def label(self, name: str) -> None:
        self.labels[name] = len(self.data)

    def branch(self, opcode: int, target: str) -> None:
        self.emit(opcode, 0)
        self.fixups.append((len(self.data) - 1, target))

    def finish(self) -> bytes:
        for operand, target in self.fixups:
            require(target in self.labels, f"wrapper label absent: {target}")
            delta = self.labels[target] - (operand + 1)
            require(-128 <= delta <= 127, f"wrapper branch out of range: {target}")
            self.data[operand] = delta & 0xff
        return bytes(self.data)


def expected_wrapper(body: int, fail_closed: int, transfer: int) -> bytes:
    tag = 0xB583 + transfer * 3
    live = tag + 1
    saved = tag + 2
    w = WrapperImage()
    w.emit(0xBA)                         # TSX
    w.word(0xBD, 0x0101); w.word(0x8D, SHADOW[0])
    w.word(0xBD, 0x0102); w.word(0x8D, SHADOW[1])
    w.emit(0xA5, PHASE_OWNER_ZP, 0xC9, APPEND_OWNER)
    w.branch(0xD0, "fail")
    w.word(0x8D, SHADOW[2])
    w.emit(0xA9, 1); w.word(0x8D, ARM)
    w.word(0x20, body); w.emit(0x48)
    w.word(0xCE, ARM); w.branch(0xD0, "fail")
    w.emit(0xBA)
    w.word(0xBD, 0x0102); w.word(0xCD, SHADOW[0])
    w.branch(0xD0, "low")
    w.word(0xBD, 0x0103); w.word(0xCD, SHADOW[1])
    w.branch(0xD0, "high")
    w.emit(0xA5, PHASE_OWNER_ZP); w.word(0xCD, SHADOW[2])
    w.branch(0xF0, "done")
    w.emit(0xA2, 2); w.branch(0x80, "mismatch")
    w.label("low"); w.emit(0xA2, 0); w.branch(0x80, "mismatch")
    w.label("high"); w.emit(0xA2, 1); w.branch(0x80, "mismatch")
    w.label("mismatch")
    w.emit(0xA8); w.word(0xAD, tag); w.branch(0xD0, "restore")
    w.emit(0x98); w.word(0x8D, live)
    w.word(0xBD, SHADOW[0]); w.word(0x8D, saved)
    w.emit(0xE8); w.word(0x8E, tag)      # commit tag is last
    w.label("restore")
    w.emit(0xBA)
    w.word(0xAD, SHADOW[0]); w.word(0x9D, 0x0102)
    w.word(0xAD, SHADOW[1]); w.word(0x9D, 0x0103)
    w.word(0xAD, SHADOW[2]); w.emit(0x85, PHASE_OWNER_ZP)
    w.label("done"); w.emit(0x68, 0x60)
    w.label("fail"); w.word(0x4C, fail_closed)
    return w.finish()


def record_addresses(transfer: int) -> tuple[int, int, int]:
    tag = 0xB583 + transfer * 3
    return tag, tag + 1, tag + 2


def audit_wrapper(actual: bytes, *, body: int, fail_closed: int,
                  transfer: int) -> dict[str, Any]:
    expected = expected_wrapper(body, fail_closed, transfer)
    require(actual == expected,
            f"terminal return wrapper {transfer} instruction identity drift")
    tag, live, saved = record_addresses(transfer)
    require(ARENA_START <= tag < live < saved < ARENA_END,
            f"terminal record {transfer} escaped owner-free arena")
    return {
        "bytes": len(actual),
        "sha256": sha(actual),
        "transfer_id": transfer,
        "shadow": [f"0x{x:04x}" for x in SHADOW],
        "arm": f"0x{ARM:04x}",
        "record": {
            "tag": f"0x{tag:04x}",
            "live": f"0x{live:04x}",
            "shadow": f"0x{saved:04x}",
            "commit_order": "live,shadow,tag-last",
        },
        "clean_path_cycles": 98,
        "first_mismatch_cycles": {
            "return_low": 139,
            "return_high": 149,
            "phase_owner": 157,
        },
    }


def guard_model(*, live: tuple[int, int, int], shadow: tuple[int, int, int],
                arm: int, record: tuple[int, int, int], result: int,
                initial_owner: int = APPEND_OWNER) -> dict[str, Any]:
    require(all(0 <= item <= 0xff for item in (*live, *shadow, *record, result)),
            "guard model byte outside range")
    if initial_owner != APPEND_OWNER or arm != 1:
        return {"outcome": "fail-closed", "record": record}
    mismatch = next((i for i in range(3) if live[i] != shadow[i]), None)
    if mismatch is None:
        return {"outcome": "clean", "return_state": live,
                "record": record, "result": result}
    updated = record
    if record[0] == 0:
        updated = (mismatch + 1, live[mismatch], shadow[mismatch])
    return {"outcome": "restored", "return_state": shadow,
            "record": updated, "result": result}


def validate_model(result: dict[str, Any], *, outcome: str,
                   state: tuple[int, int, int] | None,
                   record: tuple[int, int, int], value: int | None) -> None:
    require(result.get("outcome") == outcome, "guard model outcome drift")
    require(result.get("record") == record, "guard record provenance drift")
    if state is not None:
        require(result.get("return_state") == state,
                "guard did not preserve/restore complete return state")
    if value is not None:
        require(result.get("result") == value, "guard changed phase result")


def semantic_cases() -> list[dict[str, Any]]:
    shadow = (0xE4, 0x2C, APPEND_OWNER)
    rows: list[dict[str, Any]] = []
    clean = guard_model(live=shadow, shadow=shadow, arm=1,
                        record=(0, 0, 0), result=7)
    validate_model(clean, outcome="clean", state=shadow,
                   record=(0, 0, 0), value=7)
    rows.append({"name": "clean-transparent", **clean})
    for index, name in enumerate(("return-low", "return-high", "phase-owner")):
        live = list(shadow); live[index] ^= 0x55
        repaired = guard_model(live=tuple(live), shadow=shadow, arm=1,
                               record=(0, 0, 0), result=9)
        expected_record = (index + 1, live[index], shadow[index])
        validate_model(repaired, outcome="restored", state=shadow,
                       record=expected_record, value=9)
        rows.append({"name": name, **repaired})
    preserved = guard_model(live=(0, 0x2C, APPEND_OWNER), shadow=shadow,
                            arm=1, record=(2, 0x11, 0x22), result=3)
    validate_model(preserved, outcome="restored", state=shadow,
                   record=(2, 0x11, 0x22), value=3)
    rows.append({"name": "first-record-survives", **preserved})
    for arm, owner, name in ((0, APPEND_OWNER, "unarmed"),
                             (2, APPEND_OWNER, "invalid-arm"),
                             (1, 0, "invalid-owner")):
        stopped = guard_model(live=shadow, shadow=shadow, arm=arm,
                              record=(0, 0, 0), result=1,
                              initial_owner=owner)
        validate_model(stopped, outcome="fail-closed", state=None,
                       record=(0, 0, 0), value=None)
        rows.append({"name": name, **stopped})
    return rows


def audit_owner_authority() -> dict[str, Any]:
    value = json.loads(OWNER_AUTHORITY.read_text(encoding="utf-8"))
    witness = value["facts"]["durable_witness"]
    gap = witness["containing_gap"]
    require(
        gap == {"start": "0xb582", "end_exclusive": "0xb5c4", "bytes": 66}
        and witness["disjoint_from_all_post_ownership_owners"] is True
        and int(value["facts"]["durable_witness"]["active_owner_ranges_rejected"])
            == 30,
        "historical owner-free interval authority drift")
    return {
        "authority": bind(OWNER_AUTHORITY),
        "interval": gap,
        "active_owner_ranges_rejected": 30,
    }


def allocated_owners(truth: ElfTruth, start: int, end: int) -> list[dict[str, Any]]:
    return [
        {"name": row.name, "start": row.address,
         "end_exclusive": row.address + row.bytes}
        for row in truth.sections
        if row.bytes and "SHF_ALLOC" in row.flags
        and row.address < end and start < row.address + row.bytes
    ]


def audit_placement(truth: ElfTruth, *, start: int = ARENA_START,
                    end: int = ARENA_END) -> dict[str, Any]:
    require(ARENA_START <= start < end <= OWNER_GAP_END,
            "terminal shadow moved outside the proven owner-free interval")
    overlaps = allocated_owners(truth, start, end)
    require(not overlaps, f"terminal shadow overlaps a linked owner: {overlaps}")
    allocated = [row for row in truth.sections
                 if row.bytes and "SHF_ALLOC" in row.flags]
    predecessor = max(row.address + row.bytes for row in allocated
                      if row.address + row.bytes <= start)
    successor = min(row.address for row in allocated if row.address >= end)
    require(predecessor == ARENA_START and successor == OWNER_GAP_END,
            "current ELF no longer proves the complete B582..B5C4 gap")
    return {
        "start": f"0x{start:04x}", "end_exclusive": f"0x{end:04x}",
        "bytes": end - start, "linked_owner_overlaps": 0,
        "linked_gap": [f"0x{predecessor:04x}", f"0x{successor:04x}"],
        "outside_G4_E000_FFFF": end <= 0xE000,
        "outside_C2J_and_C2D_planes": True,
    }


def prg_bytes(prg: bytes, address: int, length: int) -> bytes:
    require(len(prg) >= 2, "product PRG lacks load address")
    load = prg[0] | prg[1] << 8
    offset = 2 + address - load
    require(address >= load and 0 <= offset <= len(prg) - length,
            "terminal shadow outside delivered PRG extent")
    return prg[offset:offset + length]


def audit_zero_delivery(prg: bytes) -> dict[str, Any]:
    delivered = prg_bytes(prg, ARENA_START, ARENA_END - ARENA_START)
    require(delivered == bytes(len(delivered)),
            "terminal shadow arena is not delivered zero-filled")
    return {"bytes": len(delivered), "sha256": sha(delivered),
            "initial_record_tags": [0, 0, 0, 0]}


def plan_bytes(truth: ElfTruth) -> bytes:
    _symbol, body = symbol_body(
        truth, "lisp65_c2_append_persistent_publish_plan")
    return body


def audit(elf: Path, prg: Path) -> dict[str, Any]:
    truth = ElfTruth.read(
        elf, llvm_readobj=READOBJ, include_section_data=True)
    fail_closed = truth.symbol("c2_kernal_fail_closed")
    owner = truth.symbol("c2_phase_owner")
    require(owner.value == PHASE_OWNER_ZP and owner.bytes == 1
            and owner.section == ".lisp65_c2_fixed_zp",
            "terminal guard phase-owner identity drift")
    require(plan_bytes(truth) == PLAN,
            "persistent publication plan does not contain exactly four guarded entries")
    wrappers: list[dict[str, Any]] = []
    for section_name, public_name, body_name, transfer in PHASES:
        public, public_body = symbol_body(truth, public_name)
        body = truth.symbol(body_name)
        require(public.section == body.section
                == f".lisp65_rt_c2append_{section_name}"
                and public.binding == "Global" and body.bytes > 0,
                f"terminal wrapper/body ownership drift: {public_name}")
        row = audit_wrapper(public_body, body=body.value,
                            fail_closed=fail_closed.value, transfer=transfer)
        row.update({"entry": public_name, "body": body_name,
                    "section": public.section,
                    "entry_address": f"0x{public.value:04x}",
                    "body_address": f"0x{body.value:04x}",
                    "body_bytes": body.bytes})
        wrappers.append(row)
    placement = audit_placement(truth)
    product = prg.read_bytes()
    zero = audit_zero_delivery(product)
    model = semantic_cases()
    return {
        "format": "lisp65-c2.3-terminal-ingress-return-guard-v1",
        "recorded_on": "2026-08-11",
        "status": "passed-terminal-return-shadow-restore-and-first-signature",
        "authorities": {
            "commission": bind_commission_prefix(), "runtime": bind(RUNTIME),
            "phase_scratch": bind(SCRATCH), "ELF": bind(elf),
            "product_PRG": bind(prg), **audit_owner_authority(),
        },
        "persistent_plan": {
            "symbol": "lisp65_c2_append_persistent_publish_plan",
            "bytes": list(PLAN), "guarded_transfer_count": 4,
        },
        "return_state": {
            "hardware_return_word": ["stack+1", "stack+2"],
            "phase_owner": f"ZP 0x{PHASE_OWNER_ZP:02x}",
            "required_initial_owner": APPEND_OWNER,
            "indirect_entry_vector": (
                "consumed before phase ingress; not a return-state slot"),
        },
        "placement": placement,
        "cold_delivery": zero,
        "wrappers": wrappers,
        "semantic_cases": model,
        "pricing": {
            "clean_cycles_per_transfer": 98,
            "clean_cycles_per_four-transfer_append": 392,
            "clean_cycles_per_nine-append_defstruct": 3528,
            "resident_bytes": 0,
            "overlay_quantum_growth_bytes": 0,
            "ordinary_state_bytes": 0,
            "owner_free_shadow_bytes": ARENA_END - ARENA_START,
        },
        "claim_limit": (
            "Host/ELF proof of terminal return-state guarding and repair. "
            "No hardware success, defstruct completion, release or root-writer "
            "attribution is claimed."),
    }


def mutation_selftest(elf: Path | None = None, prg: Path | None = None) -> list[str]:
    # The linked wrapper is exact intentionally: each mutation below removes
    # one commissioned semantic edge and therefore must cease to match it.
    base = expected_wrapper(0xC440, 0xE08B, 1)
    patterns: dict[str, tuple[bytes, int]] = {
        "skip-initial-owner-check": (bytes.fromhex("c902"), 0),
        "accept-unarmed-return": (bytes.fromhex("ce82b5d0"), 3),
        "wrong-live-return-offset": (bytes.fromhex("bd0201cd83b5"), 1),
        "swallow-low-mismatch": (bytes.fromhex("cd83b5d0"), 3),
        "swallow-high-mismatch": (bytes.fromhex("cd84b5d0"), 3),
        "swallow-owner-mismatch": (bytes.fromhex("cd85b5f0"), 3),
        "silent-restore-no-live-log": (bytes.fromhex("988d87b5"), 1),
        "silent-restore-no-shadow-log": (bytes.fromhex("bd83b58d88b5"), 3),
        "tag-not-commit-last": (bytes.fromhex("e88e86b5"), 1),
        "skip-return-low-restore": (bytes.fromhex("ad83b59d0201"), 3),
        "skip-return-high-restore": (bytes.fromhex("ad84b59d0301"), 3),
        "skip-owner-restore": (bytes.fromhex("ad85b58589"), 3),
    }
    rejected: list[str] = []
    for name, (needle, within) in patterns.items():
        at = base.find(needle)
        require(at >= 0, f"mutation anchor absent: {name}")
        mutant = bytearray(base); mutant[at + within] ^= 1
        try:
            audit_wrapper(bytes(mutant), body=0xC440,
                          fail_closed=0xE08B, transfer=1)
        except GateError:
            rejected.append(name)
    require(len(rejected) == len(patterns), "terminal wrapper mutation survived")

    # Semantic negatives are independent of opcode identity.
    clean = guard_model(live=(1, 2, 2), shadow=(1, 2, 2), arm=1,
                        record=(0, 0, 0), result=5)
    semantic_mutants: dict[str, dict[str, Any]] = {
        "clean-result-changed": clean | {"result": 4},
        "clean-record-written": clean | {"record": (1, 1, 1)},
        "clean-state-changed": clean | {"return_state": (0, 2, 2)},
    }
    for name, candidate in semantic_mutants.items():
        try:
            validate_model(candidate, outcome="clean", state=(1, 2, 2),
                           record=(0, 0, 0), value=5)
        except GateError:
            rejected.append(name)

    if elf is not None:
        truth = ElfTruth.read(elf, llvm_readobj=READOBJ,
                              include_section_data=True)
        try:
            audit_placement(truth, start=0xB5C4, end=0xB5D4)
        except GateError:
            rejected.append("shadow-inside-owned-facade")
    if prg is not None:
        mutant = bytearray(prg.read_bytes())
        load = mutant[0] | mutant[1] << 8
        mutant[2 + ARENA_START - load] = 1
        try:
            audit_zero_delivery(bytes(mutant))
        except GateError:
            rejected.append("nonzero-cold-record-tag")
    expected = len(patterns) + len(semantic_mutants)
    if elf is not None:
        expected += 1
    if prg is not None:
        expected += 1
    require(len(rejected) == expected, "terminal return mutation count drift")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--elf", type=Path, required=True)
    audit_parser.add_argument("--prg", type=Path, required=True)
    audit_parser.add_argument("--receipt", type=Path)
    sub.add_parser("selftest")
    args = parser.parse_args()
    if args.action == "selftest":
        semantic_cases()
        rejected = mutation_selftest()
        print("c2-terminal-return-guard-selftest: PASS "
              f"mutations={len(rejected)}")
        return 0
    result = audit(args.elf, args.prg)
    rejected = mutation_selftest(args.elf, args.prg)
    result["mutations_rejected"] = rejected
    result["mutation_count"] = len(rejected)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_bytes(canonical(result))
    print("c2-terminal-return-guard: PASS "
          f"transfers=4 clean_cycles=98 mutations={len(rejected)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, OSError, ValueError, KeyError) as error:
        print(f"c2-terminal-return-guard: FAIL: {error}")
        raise SystemExit(1)
