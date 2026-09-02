#!/usr/bin/env python3
"""Price v2.0 domain discipline Tier 2 without building a product.

The price executes the successor semantics over the living Tier-1 product
directory, measures CAR/CDR frequency on the delivered editor route, and
executes the already-linked ``cell_type`` path from the qualified Tier-1 ELF.
It then projects the shared guard into the complete linked layout.  It never
invokes WPLTO or a product linker; final-LTO emission remains a product-card
obligation.
"""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import c2_v160_input_service_time_pricing as PRICE  # noqa: E402
import c2_v18_capture_hybrid_responsiveness_repair as TRACE  # noqa: E402
import cpu6502 as CPU6502  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402
import evidence_era as ERA  # noqa: E402
import public_surface_domain_audit as AUDIT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CONTRACT = ROOT / "config/public-surface-domain-contract.json"
CONTRACT_EVIDENCE_ERA = "b1c3890d"
RESPONSIVENESS_CONTRACT = ROOT / "config/c2-v160-input-service-hybrid-contract.json"
EDITOR = ROOT / "lib/stdlib-read-line.lisp"
EDITOR_EVIDENCE_ERA = "3626e151"
TIER1_RECEIPT = ARCH / "c2.3-v2.0-domain-tier1-product-card-r1-receipt.json"
ELF = ROOT / (
    "build/c2.3/v2.0-domain-tier1-product-card-r1/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
PRG = ELF.with_suffix("")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
RECEIPT = ARCH / "c2.3-v2.0-domain-tier2-pricing-receipt.json"
REPORT = ROOT / "docs/planning/v2.0.0-domain-tier2-pricing-report.md"
AUTHORITY_COMMIT = "a699ca1e"
AUTHORITY_HEADER = (
    "## Reviewer commission — Tier 2 pricing and the delivery-chain block — 2026-09-01")
FORMAT = "lisp65-c2-v200-domain-tier2-pricing-v1"
STATUS = "PASS: V2.0 DOMAIN TIER 2 PRICED; IMPLEMENTATION OWNER-GATED"
SEALED_COMMIT = "3626e151"
SUCCESSOR_RECEIPT = ARCH / (
    "c2.3-v2.0-block3-hot-path-repair-card-r1-receipt.json")

# This is an upper price, assembled from an exact final-linked guard already
# emitted inside vm_run_inner.  The final product card must replace the price
# with its actual linked delta.  The derived facade anchor makes the projection
# safe even if LTO spends the whole allowance.
PROJECTED_SHARED_GUARD_BYTES = 32
TEXT_RESERVE_FLOOR = 32


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    path = "docs/planning/v2.0.0-pre-plan.md"
    raw = subprocess.run(
        ["git", "show", f"{AUTHORITY_COMMIT}:{path}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode("utf-8")
    require(text.count(AUTHORITY_HEADER) == 1,
            "Tier-2 commission identity drift")
    section = AUTHORITY_HEADER + text.split(AUTHORITY_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").split())
    for token in ("car/cdr accept cons and nil only", "25% responsiveness wall",
                  "final link and never from a fragment", "remaining 110"):
        require(token in folded, f"Tier-2 commission token absent: {token}")
    payload = section.encode()
    return {"commit": AUTHORITY_COMMIT, "path": path,
            "section": AUTHORITY_HEADER, "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "right": "host-only Tier-2 price; no implementation, WPLTO or product link"}


def semantic(cell: dict[str, Any]) -> dict[str, Any]:
    return {key: cell[key] for key in ("classification", "result", "error")
            if key in cell}


def tier1_contract_authority() -> tuple[dict[str, Any], dict[str, Any]]:
    raw = subprocess.run(["git", "show",
        f"{CONTRACT_EVIDENCE_ERA}:"
        "config/public-surface-domain-contract.json"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    value = json.loads(raw)
    binding = {"path": CONTRACT.relative_to(ROOT).as_posix(),
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    return value, binding


def priced_editor_binding() -> dict[str, Any]:
    raw = subprocess.run(["git", "show",
        f"{EDITOR_EVIDENCE_ERA}:{EDITOR.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    return {"path": EDITOR.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


@contextmanager
def strict_car_cdr() -> Iterator[None]:
    old_car, old_cdr = B.Heap.car, B.Heap.cdr

    def require_cons(heap: B.Heap, value: int, name: str) -> Any:
        if value == B.NIL:
            return None
        if not heap.consp(value):
            raise B.VMError("TypeError", f"{name} expects cons or nil")
        return heap.cell(value)

    def strict_car(heap: B.Heap, value: int) -> int:
        cell = require_cons(heap, value, "car")
        return B.NIL if cell is None else cell.a

    def strict_cdr(heap: B.Heap, value: int) -> int:
        cell = require_cons(heap, value, "cdr")
        return B.NIL if cell is None else cell.b

    B.Heap.car, B.Heap.cdr = strict_car, strict_cdr
    try:
        yield
    finally:
        B.Heap.car, B.Heap.cdr = old_car, old_cdr


def successor_contract() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    before, _binding = tier1_contract_authority()
    require(before["counts"] == {"error-raised": 545,
                "documented-permissive": 179, "silently-wrong": 110},
            "Tier-2 predecessor is not the durable Tier-1 authority")
    with strict_car_cdr():
        after = AUDIT.derive_recorded_world(before)
    before_rows = {row["name"]: row for row in before["rows"]}
    after_rows = {row["name"]: row for row in after["rows"]}
    changes: list[dict[str, Any]] = []
    for name in sorted(before_rows):
        for domain in AUDIT.DOMAINS:
            old = before_rows[name]["cells"][domain]
            new = after_rows[name]["cells"][domain]
            if semantic(old) != semantic(new):
                changes.append({"name": name, "domain": domain,
                    "before": semantic(old), "after": semantic(new)})
    require(after["counts"] == {"error-raised": 553,
                "documented-permissive": 179, "silently-wrong": 102},
            "Tier-2 successor contract count drift")
    expected = {(name, domain) for name in ("car", "cdr")
                for domain in ("number", "string", "symbol", "function")}
    require({(row["name"], row["domain"]) for row in changes} == expected,
            "Tier-2 changed-cell population is not exact")
    require(all(row["before"]["classification"] == "silently-wrong"
                and row["after"] == {"classification": "error-raised",
                                     "error": "TypeError"}
                for row in changes),
            "Tier-2 changed cell did not become target TypeError")
    for name in ("car", "cdr"):
        for domain in ("nil", "list"):
            require(semantic(before_rows[name]["cells"][domain]) ==
                    semantic(after_rows[name]["cells"][domain]),
                    f"Tier-2 positive semantic drift: {name}/{domain}")
    return after, changes


class OperandTrace:
    def __init__(self) -> None:
        self.vm: PRICE.TimingVM | None = None
        self.rows: list[tuple[int, str, str, int]] = []

    def record(self, operation: str, heap: B.Heap, value: int) -> None:
        assert self.vm is not None
        if value == B.NIL:
            kind, index = "nil", 0
        elif B.is_ptr(value):
            cell = heap.cell(value)
            kind, index = str(cell.type), (value & 0xffff) >> 1
        else:
            kind, index = "non-pointer", -1
        self.rows.append((self.vm.steps, operation, kind, index))


def delivered_route(*, live: bool = False) -> dict[str, Any]:
    events = [97] * 40 + [13]
    suite = PRICE.combined_suite(
        EDITOR, '(%repl-read "" nil 0 80 0)', "a" * 40, events)
    directory_authority = PRICE.live_function_directory(suite, EDITOR)
    if not live:
        rows = directory_authority["sources"]
        matches = [index for index, row in enumerate(rows)
                   if row["path"] == EDITOR.relative_to(ROOT).as_posix()]
        require(matches == [0], "priced editor source authority is not unique")
        rows[0] = {**rows[0], **priced_editor_binding()}
    (heap, _names, _code, _entry_flags, resident_flags, _bundle,
     directory, _cases, entries, _inliner) = PRICE.P0._compile_suite(suite)
    macros = PRICE.P0._macro_symbol_objs(heap, {}, resident_flags)
    abi_profile, abi_ledger = PRICE.P0._suite_abi(suite)
    case_heap = heap.clone()
    for tag in ("key", "shift", "control", "meta"):
        case_heap.intern(tag)
    names = {id(code): case_heap.obj_to_text(symbol)
             for symbol, code in directory.items()}
    operand_trace = OperandTrace()
    old_car, old_cdr = case_heap.car, case_heap.cdr

    def traced(operation: str, original: Any) -> Any:
        def call(value: int) -> int:
            operand_trace.record(operation, case_heap, value)
            return original(value)
        return call

    case_heap.car = traced("CAR", old_car)  # type: ignore[method-assign]
    case_heap.cdr = traced("CDR", old_cdr)  # type: ignore[method-assign]
    vm = PRICE.TimingVM(
        heap=case_heap, directory=directory, macro_symbols=macros,
        max_steps=1_000_000, max_call_args=suite.get("max_call_args"),
        key_events=events, abi_profile=abi_profile,
        abi_ledger=abi_ledger, batch_cap=8, code_names=names)
    operand_trace.vm = vm
    result = vm.run(directory[case_heap.intern(entries[0])], [])
    require(case_heap.obj_to_text(result) == json.dumps("a" * 40),
            "Tier-2 responsiveness route result drift")
    points = [step for label, step in vm.boundaries if label == "private-2"]
    require(len(points) == 6, "Tier-2 responsiveness boundary drift")
    first, last = points[0], points[-1]
    rows = [row for row in operand_trace.rows if first <= row[0] < last]
    counts = Counter((operation, kind) for _, operation, kind, _ in rows)
    ext = [index for _, _, kind, index in rows if kind == B.T_CONS]
    require(len(rows) == 820 and counts[("CAR", B.T_CONS)] == 315
            and counts[("CAR", "nil")] == 5
            and counts[("CDR", B.T_CONS)] == 500,
            f"Tier-2 delivered CAR/CDR population drift: {counts}")
    require(ext and min(ext) >= 96,
            "Tier-2 delivered CAR/CDR operands are not all extended cells")
    raw = PRICE.execute_route(
        EDITOR, "batch", 40, batch_cap=8, function_world="live-artifacts")
    require(raw["vm_steps_per_character"] == (last - first) / 40,
            "Tier-2 operand and route step worlds diverge")
    return {**raw, "function_directory_authority": directory_authority,
            "steady_window": {"first_step": first, "last_step": last},
            "car_cdr": {
                "total": len(rows), "characters": 40,
                "per_character": len(rows) / 40,
                "extended_cons": sum(kind == B.T_CONS
                                     for _, _, kind, _ in rows),
                "nil": sum(kind == "nil" for _, _, kind, _ in rows),
                "foreign": sum(kind not in (B.T_CONS, "nil")
                               for _, _, kind, _ in rows),
                "counts": [
                    {"operation": operation, "operand": kind, "count": count}
                    for (operation, kind), count in sorted(counts.items())],
                "extended_index_min": min(ext),
                "extended_index_max": max(ext),
                "hot_cell_limit": 96,
            }}


# Standard 65C02/45GS02 CPU-cycle model for every opcode reached by the exact
# linked cell_type success paths.  MAP and LDZ are charged two CPU cycles; no
# DMA guess is involved because the linked product uses c2_map_cpu_read.
CYCLES = {
    0x05: 3, 0x06: 5, 0x08: 3, 0x09: 2, 0x0A: 2, 0x18: 2,
    0x20: 6, 0x26: 5, 0x28: 4, 0x29: 2, 0x2A: 2, 0x38: 2, 0x46: 5,
    0x4A: 2, 0x4C: 3, 0x5C: 2, 0x60: 6, 0x64: 3, 0x65: 3,
    0x66: 5, 0x69: 2, 0x78: 2, 0x80: 3, 0x84: 3, 0x85: 3,
    0x86: 3, 0x8A: 2, 0x8D: 4, 0x90: 2, 0x91: 6, 0x98: 2,
    0xA0: 2, 0xA2: 2, 0xA3: 2, 0xA4: 3, 0xA5: 3, 0xA6: 3,
    0xA8: 2, 0xA9: 2, 0xAA: 2, 0xAD: 4, 0xB0: 2, 0xB1: 5,
    0xB2: 5, 0xC6: 5, 0xC9: 2, 0xD0: 2, 0xD3: 3, 0xE0: 2,
    0xE6: 5, 0xE9: 2, 0xEA: 2, 0xF0: 2,
}
SHORT_BRANCHES = {0x90, 0xB0, 0xD0, 0xF0}


class LinkedCPU(CPU6502.CPU):
    def __init__(self, memory: bytearray):
        super().__init__(memory)
        self.z = 0
        self.executed: list[tuple[int, int, int]] = []
        self.cycles = 0

    def step(self) -> None:
        pc, op = self.PC, self.rd(self.PC)
        if op == 0x64:                 # STZ zp
            self.PC += 1; self.wr(self.fetch(), 0)
        elif op == 0x80:               # BRA rel
            self.PC += 1; self.branch(True)
        elif op == 0xA3:               # LDZ #imm
            self.PC += 1; self.z = self.fetch()
        elif op == 0x5C:               # MAP
            self.PC += 1
        elif op == 0xB2:               # LDA (zp),Z; Z is zero here
            self.PC += 1; zp = self.fetch()
            self.A = self.rd(self.rd16zp(zp) + self.z); self.set_zn(self.A)
        elif op == 0xD3:               # LBNE rel16
            self.PC += 1
            delta = self.fetch() | self.fetch() << 8
            if delta & 0x8000:
                delta -= 0x10000
            if not self.get(CPU6502.Z):
                self.PC = (self.PC + delta) & 0xffff
        else:
            super().step()
        require(op in CYCLES, f"unpriced linked opcode ${op:02x} at ${pc:04x}")
        cost = CYCLES[op]
        fallthrough = pc + (2 if op in SHORT_BRANCHES else 0)
        if op in SHORT_BRANCHES and self.PC != fallthrough:
            cost += 1
            if (fallthrough & 0xff00) != (self.PC & 0xff00):
                cost += 1
        elif op == 0xD3 and self.PC != pc + 3:
            cost += 1
        self.cycles += cost
        self.executed.append((pc, op, cost))


def linked_memory(truth: ElfTruth) -> bytearray:
    memory = bytearray(65536)
    for section in truth.sections:
        if ("SHF_ALLOC" in section.flags
                and section.section_type == "SHT_PROGBITS"
                and section.address + section.bytes <= len(memory)):
            raw = truth.section_bytes(section.name)
            memory[section.address:section.address + section.bytes] = raw
    return memory


def linked_cell_type_cost(truth: ElfTruth) -> dict[str, Any]:
    symbol = truth.symbol("cell_type")
    require(symbol.section == ".text" and symbol.bytes == 67,
            "Tier-2 linked cell_type identity drift")
    results = {}
    for kind, value in (("hot_cons", 2), ("extended_cons", 0x0100)):
        memory = linked_memory(truth)
        if kind == "extended_cons":
            # c2_map_cpu_read maps physical EXT storage into CPU $4000..$5fff.
            # The functional witness does not emulate MAP address translation;
            # make that aperture carry the requested T_CONS byte explicitly.
            # All routines executed by this witness live below $4000.
            memory[0x4000:0x6000] = bytes(0x2000)
        cpu = LinkedCPU(memory)
        cpu.A, cpu.X = value & 0xff, value >> 8
        cpu.call(symbol.value, max_steps=512)
        require(cpu.A == 0 and cpu.executed,
                f"Tier-2 linked cell_type did not return T_CONS: {kind}")
        results[kind] = {
            "input_obj": value, "instructions": len(cpu.executed),
            "cycles_inside_callee": cpu.cycles,
            "path_sha256": hashlib.sha256(canonical([
                {"pc": pc, "opcode": op, "cycles": cycles}
                for pc, op, cycles in cpu.executed])).hexdigest(),
            "entered_symbols": [name for name in
                ("cell_type", "ext_type", "ext_dma_read_or_abort",
                 "c2_map_cpu_read")
                if any(pc == truth.symbol(name).value
                       for pc, _, _ in cpu.executed)],
        }
    require(results["hot_cons"]["instructions"] == 31
            and results["extended_cons"]["instructions"] == 141,
            "Tier-2 linked cell_type path length drift")
    return {"symbol": {"name": symbol.name, "address": symbol.value,
                       "bytes": symbol.bytes}, **results,
            "cycle_model": ("documented 65C02 cycles over exact final-ELF bytes; "
                            "45GS02 MAP and LDZ charged two cycles")}


def linked_op_consp_guard(truth: ElfTruth) -> dict[str, Any]:
    """Derive OP_CONSP's shared guard from linked provenance and semantics.

    The final link legitimately contains multiple vm_run_inner calls to the
    shared cell_type body.  Address identity is therefore insufficient.  Start
    with every structured relocation edge from vm_run_inner to cell_type, then
    select the one whose emitted instruction sequence implements the OP_CONSP
    contract: reject a non-pointer, call cell_type, require its T_CONS result,
    clear the result cell, and load the linked Lisp true object from `lisp_t`
    on the fall-through path.
    """
    text = truth.section(".text")
    raw = truth.section_bytes(".text")
    caller = truth.symbol("vm_run_inner")
    callee = truth.symbol("cell_type")
    lisp_true = truth.symbol("lisp_t")
    require(caller.section == text.name and callee.section == text.name,
            "Tier-2 OP_CONSP/cell_type linked ownership drift")
    require(lisp_true.value <= 0xff,
            "Tier-2 linked lisp_t object is not zero-page addressable")

    edges = []
    matches = []
    for row in truth.relocations:
        if (row.source_section_index != caller.section_index
                or not caller.value <= row.offset < caller.value + caller.bytes
                or row.relocation_type != "R_MOS_ADDR16"):
            continue
        identity = truth.relocation_target_identity(row)
        if identity["resolved_value"] != callee.value:
            continue
        call = row.offset - 1       # relocation covers JSR's two-byte operand
        offset = call - text.address
        require(raw[offset] == 0x20
                and raw[offset + 1] | raw[offset + 2] << 8 == callee.value,
                "Tier-2 cell_type relocation is not consumed by linked JSR")
        edge = {
            "call_address": call,
            "operand_relocation_offset": row.offset,
            "relocation_type": row.relocation_type,
            "target": identity,
        }
        edges.append(edge)
        before = raw[offset - 10:offset]
        after = raw[offset + 3:offset + 12]
        # A5 objlo; AND #IS_PTR; BNE error; A6 objhi; A5 objlo
        pointer_guard = (
            len(before) == 10 and before[0] == 0xA5
            and before[2:4] == b"\x29\x01" and before[4] == 0xD0
            and before[6] == 0xA6 and before[8] == 0xA5
            and before[1] == before[9])
        # STZ resultlo; STZ resulthi; TAX; BNE error; LDX lisp_t
        consp_result = (
            len(after) == 9 and after[0] == 0x64 and after[2] == 0x64
            and after[4] == 0xAA and after[5] == 0xD0
            and after[7:9] == bytes((0xA6, lisp_true.value)))
        if pointer_guard and consp_result:
            start, end = call - 10, call + 10
            template = raw[start - text.address:end - text.address]
            matches.append({
                **edge,
                "start": start,
                "end_exclusive": end,
                "bytes": len(template),
                "sha256": hashlib.sha256(template).hexdigest(),
            })
    require(edges and len(matches) == 1,
            "Tier-2 OP_CONSP guard is not uniquely derived from linked edges")
    selected = matches[0]
    require(selected["bytes"] == 20,
            "Tier-2 derived OP_CONSP guard core size drift")
    return {
        "selection": {
            "method": ("ElfTruth vm_run_inner-to-cell_type relocation edges plus "
                       "OP_CONSP pointer/result instruction semantics"),
            "caller": {"name": caller.name, "address": caller.value,
                       "bytes": caller.bytes},
            "callee": {"name": callee.name, "address": callee.value,
                       "bytes": callee.bytes},
            "candidate_edge_count": len(edges),
            "semantic_match_count": len(matches),
            "address_literals_used_for_selection": False,
        },
        "observed_final_linked_interval": selected,
    }


def layout_projection(truth: ElfTruth) -> dict[str, Any]:
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    handoff = truth.section(".lisp65_c2_kernal_handoff")
    text_end = text.address + text.bytes
    facade_end = facade.address + facade.bytes
    require(text_end <= facade.address
            and facade_end <= handoff.address
            and facade.address - text_end == TEXT_RESERVE_FLOOR,
            "Tier-2 final-linked owner disjointness/reserve property red")
    guard = linked_op_consp_guard(truth)
    template_bytes = guard["observed_final_linked_interval"]["bytes"]
    projected_text_end = text_end + PROJECTED_SHARED_GUARD_BYTES
    projected_facade = max(facade.address,
                           projected_text_end + TEXT_RESERVE_FLOOR)
    projected_facade_end = projected_facade + facade.bytes
    require(projected_facade_end <= handoff.address,
            "Tier-2 projected facade collides with handoff")
    return {
        "authority": "complete qualified Tier-1 ELF, not an isolated fragment",
        "baseline": {
            "derivation": ("unique ElfTruth sections and their emitted address/size; "
                           "no text-end or facade-start address literal"),
            "address_literals_used_as_requirements": False,
            "text_start": text.address, "text_bytes": text.bytes,
            "text_end_exclusive": text_end, "facade_start": facade.address,
            "facade_bytes": facade.bytes, "handoff_start": handoff.address,
            "text_reserve_bytes": facade.address - text_end,
            "owners_disjoint": True,
        },
        "shared_guard_projection": {
            "bytes_upper_price": PROJECTED_SHARED_GUARD_BYTES,
            "derived_final_linked_op_consp_guard": guard,
            "remaining_control_allowance_bytes":
                PROJECTED_SHARED_GUARD_BYTES - template_bytes,
            "strategy": ("one shared nil/IS_PTR/cell_type guard for OP_CAR and "
                         "OP_CDR; OP_CONSP's final-linked guard is the template"),
            "fragment_price_claimed_as_final": False,
        },
        "projected": {
            "text_end_exclusive": projected_text_end,
            "facade_start": projected_facade,
            "facade_shift_bytes": projected_facade - facade.address,
            "facade_end_exclusive": projected_facade_end,
            "reserve_before_handoff_bytes": handoff.address - projected_facade_end,
            "text_reserve_bytes": projected_facade - projected_text_end,
        },
        "final_link_bar": {
            "required": True,
            "rule": ("implementation price is replaced by actual final-LTO bytes; "
                     "facade VMA derives from final text end plus 32-byte floor"),
            "mutations": ["fragment-price-presented-as-final",
                          "facade-left-at-old-VMA-after-text-growth",
                          "text-reserve-below-32", "handoff-overlap"],
        },
    }


def responsiveness(route: dict[str, Any], cell_cost: dict[str, Any]) -> dict[str, Any]:
    contract = load(RESPONSIVENESS_CONTRACT)["responsiveness"]
    counts = route["car_cdr"]
    # The shared guard charges a conservative eight cycles at every CAR/CDR
    # for NIL/pointer discrimination.  Every non-NIL operand then pays exact
    # linked cell_type, plus the 17-cycle call/result adapter visible in the
    # linked OP_CONSP template (loads, JSR, result branch).
    base_guard_cycles = 8
    call_adapter_cycles = 17
    added_total = (counts["total"] * base_guard_cycles
                   + counts["extended_cons"]
                   * (cell_cost["extended_cons"]["cycles_inside_callee"]
                      + call_adapter_cycles))
    added_per_character = added_total / counts["characters"]
    base_frames = (
        route["vm_steps_per_character"]
        * contract["calibration_cycles_per_vm_step"] / contract["cycles_per_frame"]
        + route["screen_cells_per_character"]
        * contract["screen_cell_cycles"] / contract["cycles_per_frame"]
        + route["heap_cells_per_character"]
        * contract["collection_frames"] / contract["nursery_cells"])
    after_frames = base_frames + added_per_character / contract["cycles_per_frame"]
    rate = 1.0 / after_frames
    margin = (rate - 1.0) * 100.0
    walls = {
        "maximum_frames_per_character": {
            "required": contract["maximum_frames_per_character"],
            "observed": after_frames,
            "passed": after_frames <= contract["maximum_frames_per_character"]},
        "minimum_service_events_per_frame": {
            "required": contract["minimum_service_events_per_frame"],
            "observed": rate,
            "passed": rate >= contract["minimum_service_events_per_frame"]},
        "minimum_margin_percent": {
            "required": contract["minimum_margin_percent"],
            "observed": margin,
            "passed": margin >= contract["minimum_margin_percent"]},
    }
    require(all(row["passed"] for row in walls.values()),
            f"Tier-2 responsiveness projection red: {walls}")
    return {
        "route": route, "base_frames_per_character": base_frames,
        "added_native_cycles_total": added_total,
        "added_native_cycles_per_character": added_per_character,
        "base_guard_cycles_per_opcode": base_guard_cycles,
        "cell_type_call_adapter_cycles": call_adapter_cycles,
        "frames_per_character": after_frames,
        "service_events_per_frame": rate, "margin_percent": margin,
        "walls": walls,
        "claim_limit": ("host price over exact linked cell_type path and executed "
                        "delivered editor frequency; final product card remeasures "
                        "the actual linked OP_CAR/OP_CDR emission"),
    }


def validate(value: dict[str, Any]) -> None:
    projection = value["contract_projection"]
    require(projection["baseline_counts"]["silently-wrong"] == 110
            and projection["successor_counts"]["silently-wrong"] == 102
            and projection["silent_cells_removed"] == 8
            and projection["changed_cell_count"] == 8,
            "Tier-2 receipt contract projection red")
    require(projection["nil_and_cons_positive_cells_unchanged"] == 4,
            "Tier-2 nil/cons preservation absent")
    perf = value["performance"]
    require(perf["route"]["car_cdr"]["extended_cons"] == 815
            and perf["route"]["car_cdr"]["nil"] == 5
            and perf["margin_percent"] >= 25.0
            and all(row["passed"] for row in perf["walls"].values()),
            "Tier-2 receipt responsiveness red")
    layout = value["complete_link_world_projection"]
    baseline = layout["baseline"]
    guard = layout["shared_guard_projection"][
        "derived_final_linked_op_consp_guard"]
    require(layout["shared_guard_projection"]["fragment_price_claimed_as_final"] is False
            and baseline["address_literals_used_as_requirements"] is False
            and baseline["owners_disjoint"] is True
            and baseline["text_reserve_bytes"] == TEXT_RESERVE_FLOOR
            and guard["selection"]["address_literals_used_for_selection"] is False
            and guard["selection"]["semantic_match_count"] == 1
            and guard["selection"]["candidate_edge_count"] >= 1
            and layout["projected"]["text_reserve_bytes"] >= 32
            and layout["projected"]["reserve_before_handoff_bytes"] >= 0
            and layout["final_link_bar"]["required"],
            "Tier-2 receipt full-link projection red")
    require(value["budget"] == {"WPLTOs": 0, "product_links": 0,
                                "media": 0, "device_contacts": 0,
                                "product_sources_changed": 0},
            "Tier-2 pricing spent unauthorized budget")


def derive() -> dict[str, Any]:
    after, changes = successor_contract()
    predecessor, predecessor_binding = tier1_contract_authority()
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    route = delivered_route()
    cell_cost = linked_cell_type_cost(truth)
    value = {
        "format": FORMAT, "recorded_on": "2026-09-01", "status": STATUS,
        "authority": authority(),
        "scope": {
            "members": ["car", "cdr"],
            "target_semantics": ("accept Cons and nil only; car(nil) and "
                                 "cdr(nil) remain nil; every other domain raises TypeError"),
            "implementation_status": "closed pending owner breaking-change word",
        },
        "contract_projection": {
            "population_authority": predecessor_binding,
            "baseline_counts": predecessor["counts"],
            "successor_counts": after["counts"],
            "silent_cells_removed": 8, "changed_cell_count": len(changes),
            "changed_cells": changes,
            "nil_and_cons_positive_cells_unchanged": 4,
            "method": ("executed same 139x6 materialized Tier-1 product directory "
                       "with strict native OP_CAR/OP_CDR successor semantics"),
        },
        "linked_cell_type_measurement": cell_cost,
        "performance": responsiveness(route, cell_cost),
        "complete_link_world_projection": layout_projection(truth),
        "recommendation": {
            "variant": ("shared OP_CAR/OP_CDR guard, reusing the final-linked "
                        "OP_CONSP cell_type shape; facade anchor derives from final text"),
            "performance_result": "green above the standing 25-percent wall",
            "placement_result": ("32-byte upper price consumes the current 32-byte "
                                 "text reserve; derived facade shift retains the floor"),
            "next_touchpoint": ("owner decision on breaking semantics and one product "
                                "card; final-LTO bytes must replace this projection"),
            "implementation_authorized": False,
        },
        "sharp_mutations": [
            "foreign-pointer-still-succeeds", "car-nil-raises",
            "cdr-nil-raises", "contract-change-outside-car-cdr",
            "cell-type-cost-omitted", "delivered-route-frequency-under-counted",
            "responsiveness-wall-relaxed", "fragment-price-presented-as-final",
            "guard-selected-by-address-literal",
            "baseline-layout-selected-by-address-literal",
            "facade-not-derived-from-final-text", "product-build-during-pricing",
        ],
        "budget": {"WPLTOs": 0, "product_links": 0, "media": 0,
                   "device_contacts": 0, "product_sources_changed": 0},
        "bindings": [bind(TIER1_RECEIPT), bind(ELF), bind(PRG),
                     priced_editor_binding(),
                     bind(RESPONSIVENESS_CONTRACT)],
    }
    validate(value)
    return value


def report(value: dict[str, Any]) -> str:
    projection = value["contract_projection"]
    perf = value["performance"]
    route = perf["route"]["car_cdr"]
    cost = value["linked_cell_type_measurement"]
    layout = value["complete_link_world_projection"]
    changed = "\n".join(
        f"- `{row['name']}` / `{row['domain']}`: silently-wrong → TypeError"
        for row in projection["changed_cells"])
    return f"""# v2.0 domain discipline Tier 2 pricing

Status: **priced; implementation remains owner-gated**. This host-only round
ran no WPLTO, product link, media build or device contact.

## Executed contract movement

The durable Tier-1 contract was used as the population, and the same
materialized 139×6 product directory was executed with the successor native
semantics. Counts move from **545 / 179 / 110** to
**553 / 179 / 102** (error / permissive / silently wrong). Tier 2 therefore
removes exactly **8** of the remaining 110 silent cells:

{changed}

`(car nil)` and `(cdr nil)` remain `nil`; both list cases retain their exact
positive results. No cell outside `car`/`cdr` changes.

## Delivered hot-path price

The live delivered editor route executes **{route['total']} CAR/CDR opcodes per
40 characters** ({route['per_character']:.3f}/character):
{route['extended_cons']} operate on extended Cons cells and {route['nil']} on
`nil`. Thus the expensive case is measured rather than guessed.

The qualified Tier-1 ELF's actual, final-linked `cell_type` body is
{cost['symbol']['bytes']} bytes at `${cost['symbol']['address']:04X}`. Executing
those linked bytes takes {cost['hot_cons']['instructions']} instructions /
{cost['hot_cons']['cycles_inside_callee']} cycles for a hot Cons and
{cost['extended_cons']['instructions']} instructions /
{cost['extended_cons']['cycles_inside_callee']} cycles for an extended Cons;
the latter includes the linked `ext_type → ext_dma_read_or_abort →
c2_map_cpu_read` path.

Charging every opcode an 8-cycle NIL/pointer guard and every non-NIL operand
the linked `cell_type` path plus its 17-cycle call/result adapter adds
**{perf['added_native_cycles_per_character']:.3f} native cycles/character**.
The standing model moves from {perf['base_frames_per_character']:.6f} to
**{perf['frames_per_character']:.6f} frames/character**, or
**{perf['service_events_per_frame']:.6f} events/frame** and
**{perf['margin_percent']:.3f}% margin**. All three 0.8 / 1.25 / 25% walls are
green. This is a host price; the product card must remeasure actual final-LTO
OP_CAR/OP_CDR bytes.

## Complete linked-world baseline and successor upper projection

The **baseline** is measured from the complete qualified Tier-1 final ELF, not
from a fragment and not from address constants. ElfTruth derives `.text`'s end,
the far-facade start and the handoff start from their unique emitted sections;
the required property is that those owners are disjoint and that the semantic
text reserve is exactly {layout['baseline']['text_reserve_bytes']} bytes. The
observed addresses are `${layout['baseline']['text_end_exclusive']:04X}` and
`${layout['baseline']['facade_start']:04X}`, but neither is a requirement.

The reused `cell_type` path and the 20-byte OP_CONSP guard core are likewise
**final-linked measurements**. The guard is selected from all
{layout['shared_guard_projection']['derived_final_linked_op_consp_guard']['selection']['candidate_edge_count']}
structured `vm_run_inner → cell_type` relocation edges by the emitted
pointer/result instruction semantics; its observed interval is not an address
pin. The still-unauthorized successor emission is different: its
{layout['shared_guard_projection']['bytes_upper_price']}-byte shared-guard
figure is expressly an **upper projection**, with 12 bytes reserved for NIL,
TypeError and CAR/CDR selection.

That price consumes the entire existing text reserve. The admissible form is
therefore the established derived facade anchor:
`max(old facade, final text end + 32)`. At the upper price it moves the facade
by **{layout['projected']['facade_shift_bytes']} bytes** to
`${layout['projected']['facade_start']:04X}`, retains the 32-byte text floor,
and leaves {layout['projected']['reserve_before_handoff_bytes']} bytes before
the next owner.

The projection deliberately does not claim successor-emitted bytes. A product
card, if the owner accepts the breaking semantics, must replace it with
**Final-LTO truth** from the actual successor link, derive the facade from that
linked text end, and reject a fragment estimate, a sub-32-byte floor or an
overlap.

## Recommendation and touchpoint

The shared native guard is performance-green and removes eight silent public
cells without Bank-2 names or bytecode. Implementation remains closed because
the public semantic break needs the owner's word. The next touchpoint is:
**accept/reject Tier-2 semantics and, if accepted, authorize one product card
whose final link replaces the 32-byte projection with emitted truth**.

Machine-readable evidence:
`tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v2.0-domain-tier2-pricing-receipt.json`.
"""


def selftest() -> None:
    value = derive()
    mutations = []

    def reject(name: str, mutate: Any) -> None:
        bad = deepcopy(value); mutate(bad)
        try:
            validate(bad)
        except PricingError:
            mutations.append(name)
        else:
            raise PricingError(f"Tier-2 mutation survived: {name}")

    reject("foreign-pointer-still-succeeds", lambda x:
           x["contract_projection"].update(successor_counts={
               "error-raised": 552, "documented-permissive": 179,
               "silently-wrong": 103}))
    reject("nil-positive-lost", lambda x:
           x["contract_projection"].update(nil_and_cons_positive_cells_unchanged=3))
    reject("delivered-frequency-undercounted", lambda x:
           x["performance"]["route"]["car_cdr"].update(extended_cons=814))
    reject("responsiveness-wall-red", lambda x:
           x["performance"].update(margin_percent=24.999))
    reject("fragment-price-as-final", lambda x:
           x["complete_link_world_projection"]["shared_guard_projection"].update(
               fragment_price_claimed_as_final=True))
    reject("guard-selected-by-address-literal", lambda x:
           x["complete_link_world_projection"]["shared_guard_projection"]
           ["derived_final_linked_op_consp_guard"]["selection"].update(
               address_literals_used_for_selection=True))
    reject("baseline-selected-by-address-literal", lambda x:
           x["complete_link_world_projection"]["baseline"].update(
               address_literals_used_as_requirements=True))
    reject("text-floor-lost", lambda x:
           x["complete_link_world_projection"]["projected"].update(
               text_reserve_bytes=31))
    reject("product-budget-spent", lambda x:
           x["budget"].update(product_links=1))
    require(len(mutations) == 9, "Tier-2 mutation population drift")
    print(f"c2-v200-domain-tier2-pricing: SELFTEST PASS mutations={len(mutations)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("record", "check", "selftest"))
    args = parser.parse_args()
    if args.command == "selftest":
        selftest(); return 0
    if args.command == "check" and SUCCESSOR_RECEIPT.is_file():
        require(RECEIPT.read_bytes() == ERA.era_blob(
            SEALED_COMMIT, RECEIPT.relative_to(ROOT).as_posix()),
            "sealed Tier-2 pricing receipt was rewritten")
        require(REPORT.read_bytes() == ERA.era_blob(
            SEALED_COMMIT, REPORT.relative_to(ROOT).as_posix()),
            "sealed Tier-2 pricing report was rewritten")
        value = json.loads(RECEIPT.read_text())
        validate(value)
        successor = json.loads(SUCCESSOR_RECEIPT.read_text())
        final = successor.get("final_product", {})
        require(successor.get("status") ==
                "PASS: V2.0 BLOCK-3 HOT-PATH REPAIR PRODUCT GREEN"
                and final.get("contract_counts", {}).get("silently-wrong") == 110
                and final.get("responsiveness_lanes", {}).get(
                    "single_keystroke", {}).get("successor", {}).get(
                        "vm_steps_per_character") == 904,
                "living successor does not separate Tier-2 price from live route")
        print("c2-v200-domain-tier2-pricing: PASS sealed=3626e151 "
              "live-single=904 Tier2=descoped")
        return 0
    value = derive(); raw = canonical(value); prose = report(value)
    if args.command == "record":
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(raw); REPORT.write_text(prose, encoding="utf-8")
    else:
        require(RECEIPT.is_file() and REPORT.is_file(),
                "Tier-2 pricing evidence absent")
        require(RECEIPT.read_bytes() == raw, "Tier-2 pricing receipt drift")
        require(REPORT.read_text(encoding="utf-8") == prose,
                "Tier-2 pricing report drift")
    print("c2-v200-domain-tier2-pricing: PASS "
          f"silent={value['contract_projection']['successor_counts']['silently-wrong']} "
          f"margin={value['performance']['margin_percent']:.3f}% "
          f"guard={value['complete_link_world_projection']['shared_guard_projection']['bytes_upper_price']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PricingError, KeyError, ValueError, OSError,
            subprocess.CalledProcessError) as error:
        print(f"c2-v200-domain-tier2-pricing: FAIL {error}")
        raise SystemExit(1)
