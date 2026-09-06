#!/usr/bin/env python3
"""Price the complete Block-2.6 Card-2 F011 successor without a product build."""

from __future__ import annotations

import argparse
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

import block_26_sidx_guard_form_pricing as GUARD  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
REGISTER = ROOT / "docs/reference/gate-and-tool-register.md"
MAP_CONTRACT = ROOT / "config/c2-mapped-far-map-contract-v2.json"
CARD1 = ARCH / "block-2.6-card1-sidx-product-r2-receipt.json"
GUARD_PRICE = ARCH / "block-2.6-card1-sidx-guard-form-pricing.json"
RECEIPT = ARCH / "block-2.6-card2-f011-text-budget-pricing.json"
REPORT = ROOT / "docs/planning/2.6-card2-f011-text-budget-pricing-report.md"
BUILD = ROOT / "build/2.6/card2-f011-text-budget-pricing-r5"
WPLTO = ROOT / "build/2.6/card1-sidx-product-r2/wplto"
CANONICAL = WPLTO / ".canonical-objects-lisp65-c2-substitution-linked"
COMPILER = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
LLVM_LINK = Path("/usr/bin/llvm-link")
AUTHORIZATION = "63dca58d"
SOURCE_EVIDENCE_ERA = "a1cf1e61"
FORMAT = "lisp65-block-2.6-card2-f011-text-budget-pricing-v2"
TEXT_FLOOR = 32
PLACEMENT_SLACK = 28
RESIDENT_ISLAND_SLACK = 1


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def evidence_binding(path: Path) -> dict[str, Any]:
    """Bind a pricing input in the era that produced the sealed receipt."""
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{SOURCE_EVIDENCE_ERA}:{relative}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    return {"path": relative, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def evidence_source() -> tuple[str, dict[str, Any]]:
    relative = "src/io.c"
    raw = subprocess.run(
        ["git", "show", f"{SOURCE_EVIDENCE_ERA}:{relative}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    return raw.decode("utf-8"), {"path": relative, "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest()}


def run(command: list[str], label: str) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def replace_once(text: str, old: str, new: str, label: str) -> str:
    require(text.count(old) == 1, f"{label} source target drift")
    return text.replace(old, new, 1)


def successor_source(source: str, *, shared_validator: bool) -> str:
    source = replace_once(
        source,
        '#include "f011_context.h"\n',
        '''#include "f011_context.h"

enum {
    LISP65_F011_STATUS_BUSY = 0x80u,
    LISP65_F011_STATUS_READ_COMPLETE = 0x60u,
    LISP65_F011_STATUS_READ_MASK = 0x7cu
};
#define LISP65_F011_READ_FAILED 0xffffu

static __attribute__((noinline)) unsigned char f011_wait_not_busy(
    unsigned int fuel
) {
    while (fuel--) {
        if (!(LISP65_F011_READ8(0xd082u) & LISP65_F011_STATUS_BUSY))
            return 1;
    }
    return 0;
}
''',
        "F011 status authority",
    )
    old_read = '''static unsigned int f011_read_at(unsigned char T, unsigned char S) {
    unsigned char b    = (unsigned char)(S >> 1);              /* 0..19  512-byte block in the track */
    unsigned char half = (unsigned char)(S & 1);              /* 0=lower, 1=upper 256 B */
    unsigned char side = (unsigned char)(b >= 10 ? 1 : 0);
    unsigned char fsec = (unsigned char)((b >= 10 ? b - 10 : b) + 1);   /* 1..10 */
    unsigned int  g;
    m65_io_enable();
    lisp65_f011_take_context();                               /* Drive 0 + F011-Puffer */
    *((volatile unsigned char *)0xD081) = 0x20;               /* spinup */
    for (g = 0; g < 20000; g++) {}
    *((volatile unsigned char *)0xD084) = (unsigned char)(T - 1);      /* f011 track 0..79 */
    *((volatile unsigned char *)0xD085) = fsec;                        /* f011 sektor 1..10 */
    *((volatile unsigned char *)0xD086) = side;                        /* seite 0/1 */
    *((volatile unsigned char *)0xD081) = 0x40;                        /* read */
    for (g = 0; g < 60000 && (*((volatile unsigned char *)0xD082) & 0x80); g++) {}   /* BUSY */
    lisp65_f011_map_buffer();                                          /* F011-Puffer -> $DE00 */
    return (unsigned int)half << 8;
}'''
    new_read = '''static unsigned int f011_read_at(unsigned char T, unsigned char S) {
    unsigned char b    = (unsigned char)(S >> 1);              /* 0..19  512-byte block in the track */
    unsigned char half = (unsigned char)(S & 1);              /* 0=lower, 1=upper 256 B */
    unsigned char side = (unsigned char)(b >= 10 ? 1 : 0);
    unsigned char fsec = (unsigned char)((b >= 10 ? b - 10 : b) + 1);   /* 1..10 */
    unsigned char status;
    m65_io_enable();
    lisp65_f011_take_context();                               /* Drive 0 + F011-Puffer */
    *((volatile unsigned char *)0xD081) = 0x20;               /* spinup */
    if (!f011_wait_not_busy(20000u)) return LISP65_F011_READ_FAILED;
    *((volatile unsigned char *)0xD084) = (unsigned char)(T - 1);      /* f011 track 0..79 */
    *((volatile unsigned char *)0xD085) = fsec;                        /* f011 sektor 1..10 */
    *((volatile unsigned char *)0xD086) = side;                        /* seite 0/1 */
    *((volatile unsigned char *)0xD081) = 0x40;                        /* read */
    if (!f011_wait_not_busy(60000u)) return LISP65_F011_READ_FAILED;
    status = LISP65_F011_READ8(0xd082u);
    if ((status & LISP65_F011_STATUS_READ_MASK) !=
        LISP65_F011_STATUS_READ_COMPLETE)
        return LISP65_F011_READ_FAILED;
    lisp65_f011_map_buffer();                                          /* F011-Puffer -> $DE00 */
    return (unsigned int)half << 8;
}'''
    source = replace_once(source, old_read, new_read, "F011 read successor")
    source = replace_once(
        source,
        '''    off = f011_read_at(track, sector);
    for (i = 0; i < 256; i++)''',
        '''    off = f011_read_at(track, sector);
    if (off == LISP65_F011_READ_FAILED) return 0;
    for (i = 0; i < 256; i++)''',
        "public sector failure",
    )
    source = replace_once(
        source,
        "static unsigned int disk_chain_count(unsigned char t, unsigned char s,\n",
        (("static __attribute__((noinline)) unsigned int disk_chain_count("
          "unsigned char t, unsigned char s,\n") if shared_validator else
         "static unsigned int disk_chain_count(unsigned char t, unsigned char s,\n"),
        "shared link validator",
    )
    source = replace_once(
        source,
        '''    off = f011_read_at(T, S);                                 /* RMW: Block holen, $DE00 aktiv */
    if (!disk_transaction_mount_token_op(0)) {''',
        '''    off = f011_read_at(T, S);                                 /* RMW: Block holen, $DE00 aktiv */
    if (off == LISP65_F011_READ_FAILED)
        return LISP65_DISK_STATUS_READ_INVALID;
    if (!disk_transaction_mount_token_op(0)) {''',
        "RMW read failure",
    )
    source = replace_once(
        source,
        '''    off = f011_read_at(track, sector);
    if (!disk_transaction_mount_token_op(0)) {''',
        '''    off = f011_read_at(track, sector);
    if (off == LISP65_F011_READ_FAILED)
        return LISP65_DISK_STATUS_READ_INVALID;
    if (!disk_transaction_mount_token_op(0)) {''',
        "readback read failure",
    )
    source = replace_once(
        source,
        "static unsigned char disk_source_pos, disk_source_len;\n",
        "static unsigned char disk_source_pos, disk_source_len;\n"
        "static unsigned char disk_source_next_track, disk_source_next_sector;\n"
        "static unsigned char disk_source_failed;\n",
        "source-owned link state",
    )
    old_fetch = '''static LISP65_RESIDENT_ISLAND_FN char disk_source_fetch(void) {
    unsigned char nt, ns;
    if (disk_file_pos >= disk_file_len) return '\\0';
    if (disk_source_pos >= disk_source_len) {
        nt = io_disk_byte(0); ns = io_disk_byte(1);
        if (!nt || !io_disk_read_sector(nt, ns)) return '\\0';
        nt = io_disk_byte(0); ns = io_disk_byte(1);
        if (!nt && !ns) return '\\0';
        disk_source_pos = 0;
        disk_source_len = nt ? 254u : (unsigned char)(ns - 1u);
    }
    ++disk_file_pos;
    return (char)io_disk_byte((unsigned char)(2u + disk_source_pos++));
}'''
    new_fetch = '''static LISP65_RESIDENT_ISLAND_FN char disk_source_fetch(void) {
    unsigned char t, s, nt, ns;
    unsigned int count;
    if (disk_file_pos >= disk_file_len) return '\\0';
    if (disk_source_pos >= disk_source_len) {
        t = disk_source_next_track; s = disk_source_next_sector;
        if (!t || !io_disk_read_sector(t, s)) {
            disk_source_failed = 1;
            return '\\0';
        }
        nt = io_disk_byte(0); ns = io_disk_byte(1);
        count = disk_chain_count(t, s, nt, ns);
        if (count > 254u) {
            disk_source_failed = 1;
            return '\\0';
        }
        disk_source_next_track = nt; disk_source_next_sector = ns;
        disk_source_pos = 0;
        disk_source_len = (unsigned char)count;
    }
    ++disk_file_pos;
    return (char)io_disk_byte((unsigned char)(2u + disk_source_pos++));
}'''
    source = replace_once(source, old_fetch, new_fetch, "source-link successor")
    source = replace_once(
        source,
        '''        off = f011_read_at(t, s);
        nt = ((volatile unsigned char *)0xDE00)[off];''',
        '''        off = f011_read_at(t, s);
        if (off == LISP65_F011_READ_FAILED) return 0;
        nt = ((volatile unsigned char *)0xDE00)[off];''',
        "cold chain read failure",
    )
    old_load = '''    nt = io_disk_byte(0); ns = io_disk_byte(1);
    disk_source_pos = 0;
    disk_source_len = nt ? 254u : (unsigned char)(ns - 1u);
    load_source_stream(disk_source_fetch);
    return 1;'''
    new_load = '''    nt = io_disk_byte(0); ns = io_disk_byte(1);
    n = disk_chain_count(track, sector, nt, ns);
    if (n > 254u) return 0;
    disk_source_next_track = nt; disk_source_next_sector = ns;
    disk_source_pos = 0;
    disk_source_len = (unsigned char)n;
    disk_source_failed = 0;
    load_source_stream(disk_source_fetch);
    return (unsigned char)!disk_source_failed;'''
    source = replace_once(source, old_load, new_load, "source-link initialization")
    return source


def mapped_cold_successor(source: str) -> str:
    """Materialize the complete successor with its cold boundary priced.

    Ordinary and resident callers enter the existing MAP domain through three
    exact assembly wrappers.  Code already executing in that domain calls the
    far bodies directly, so this form adds no nested MAP transition.
    """
    source = successor_source(source, shared_validator=True)
    source = replace_once(
        source,
        "#define LISP65_F011_READ_FAILED 0xffffu\n",
        '''#define LISP65_F011_READ_FAILED 0xffffu
#define LISP65_F011_CARD2_COLD_FN \\
    __attribute__((used, noinline, section(".lisp65_c2_mapped_f011_cold")))

unsigned int f011_read_at(unsigned char T, unsigned char S);
unsigned char io_disk_read_sector(unsigned char track, unsigned char sector);
unsigned char disk_source_refill(void);
''',
        "mapped F011 owner declarations",
    )
    source = replace_once(
        source,
        "static __attribute__((noinline)) unsigned char f011_wait_not_busy(\n",
        "static LISP65_F011_CARD2_COLD_FN unsigned char f011_wait_not_busy(\n",
        "mapped BUSY poll",
    )
    source = replace_once(
        source,
        "static unsigned int f011_read_at(unsigned char T, unsigned char S) {",
        "LISP65_F011_CARD2_COLD_FN\nunsigned int f011_read_at_far(unsigned char T, unsigned char S) {",
        "mapped F011 read body",
    )
    source = replace_once(
        source,
        '''unsigned char io_disk_read_sector(unsigned char track, unsigned char sector) {
    unsigned int off, i;
    off = f011_read_at(track, sector);''',
        '''LISP65_F011_CARD2_COLD_FN
unsigned char io_disk_read_sector_far(unsigned char track, unsigned char sector) {
    unsigned int off, i;
    off = f011_read_at_far(track, sector);''',
        "mapped public-sector body",
    )
    old_state_fetch = '''static unsigned char disk_source_pos, disk_source_len;
static unsigned char disk_source_next_track, disk_source_next_sector;
static unsigned char disk_source_failed;
static LISP65_RESIDENT_ISLAND_FN char disk_source_fetch(void) {
    unsigned char t, s, nt, ns;
    unsigned int count;
    if (disk_file_pos >= disk_file_len) return '\\0';
    if (disk_source_pos >= disk_source_len) {
        t = disk_source_next_track; s = disk_source_next_sector;
        if (!t || !io_disk_read_sector(t, s)) {
            disk_source_failed = 1;
            return '\\0';
        }
        nt = io_disk_byte(0); ns = io_disk_byte(1);
        count = disk_chain_count(t, s, nt, ns);
        if (count > 254u) {
            disk_source_failed = 1;
            return '\\0';
        }
        disk_source_next_track = nt; disk_source_next_sector = ns;
        disk_source_pos = 0;
        disk_source_len = (unsigned char)count;
    }
    ++disk_file_pos;
    return (char)io_disk_byte((unsigned char)(2u + disk_source_pos++));
}'''
    new_state_fetch = '''static unsigned char disk_source_pos, disk_source_len;
static unsigned char disk_source_next_track, disk_source_next_sector;
static unsigned char disk_source_failed;

LISP65_F011_CARD2_COLD_FN
unsigned char disk_source_refill_far(void) {
    unsigned char t = disk_source_next_track;
    unsigned char s = disk_source_next_sector;
    unsigned char nt, ns;
    unsigned int count;
    if (!t || !io_disk_read_sector_far(t, s)) {
        disk_source_failed = 1;
        return 0;
    }
    nt = ext_disk_get(DISK_EXT_DIR); ns = ext_disk_get(DISK_EXT_DIR + 1u);
    if (!nt) count = ns ? (unsigned int)(ns - 1u) : 255u;
    else if (nt > 80u || ns > 39u || (nt == t && ns == s)) count = 255u;
    else count = 254u;
    if (count > 254u) {
        disk_source_failed = 1;
        return 0;
    }
    disk_source_next_track = nt; disk_source_next_sector = ns;
    disk_source_pos = 0;
    disk_source_len = (unsigned char)count;
    return 1;
}

static LISP65_RESIDENT_ISLAND_FN char disk_source_fetch(void) {
    if (disk_file_pos >= disk_file_len) return '\\0';
    if (disk_source_pos >= disk_source_len && !disk_source_refill())
        return '\\0';
    ++disk_file_pos;
    return (char)io_disk_byte((unsigned char)(2u + disk_source_pos++));
}'''
    source = replace_once(source, old_state_fetch, new_state_fetch,
                          "mapped source-refill boundary")
    source = replace_once(
        source,
        '''    while (t) {
        off = f011_read_at(t, s);
        if (off == LISP65_F011_READ_FAILED) return 0;''',
        '''    while (t) {
        off = f011_read_at_far(t, s);
        if (off == LISP65_F011_READ_FAILED) return 0;''',
        "non-nested cold-chain read",
    )
    return source


MAPPED_COLD_WRAPPERS = r'''

        .section .text.f011_read_at,"ax",@progbits
        .globl f011_read_at
        .type f011_read_at,@function
f011_read_at:
        jsr c2_mapped_far_enter
        jsr f011_read_at_far
        phx
        jsr c2_mapped_far_leave
        plx
        rts
        .size f011_read_at, .-f011_read_at

        .section .text.io_disk_read_sector,"ax",@progbits
        .globl io_disk_read_sector
        .type io_disk_read_sector,@function
io_disk_read_sector:
        jsr c2_mapped_far_enter
        jsr io_disk_read_sector_far
        jmp c2_mapped_far_leave
        .size io_disk_read_sector, .-io_disk_read_sector

        .section .text.disk_source_refill,"ax",@progbits
        .globl disk_source_refill
        .type disk_source_refill,@function
disk_source_refill:
        jsr c2_mapped_far_enter
        jsr disk_source_refill_far
        jmp c2_mapped_far_leave
        .size disk_source_refill, .-disk_source_refill
'''


def symbol_sizes(path: Path) -> dict[str, int]:
    rows: dict[str, int] = {}
    truth = ElfTruth.read(path, llvm_readobj=READOBJ)
    for symbol in truth.symbols:
        if (symbol.name and symbol.section != "Undefined"
                and symbol.symbol_type not in ("Section", "File")):
            require(symbol.name not in rows or rows[symbol.name] == symbol.bytes,
                    f"non-unique symbol size: {symbol.name}")
            rows[symbol.name] = symbol.bytes
    return rows


def section_sizes(path: Path) -> dict[str, int]:
    rows: dict[str, int] = {}
    truth = ElfTruth.read(path, llvm_readobj=READOBJ)
    for section in truth.sections:
        name = section.name or "NULL"
        require(name not in rows, f"non-unique section: {name}")
        rows[name] = section.bytes
    return rows


def lane(name: str, io_source: str | None, flags: list[str],
         assembly_suffix: str = "") -> dict[str, Any]:
    directory = BUILD / name
    directory.mkdir(parents=True)
    objects = GUARD.canonical_c_objects()
    io_object = objects[13]
    source_binding: dict[str, Any]
    if io_source is not None:
        source = directory / "io.c"
        source.write_text(io_source, encoding="utf-8")
        io_object = directory / "io.c.o"
        run([str(COMPILER), *flags, "-c", source.relative_to(ROOT).as_posix(),
             "-o", io_object.relative_to(ROOT).as_posix()], f"{name} frontend")
        source_binding = bind(source)
    else:
        source_binding = evidence_source()[1]
    linked = directory / "combined-c.bc"
    run([str(LLVM_LINK), *(str(io_object if index == 13 else path)
        for index, path in enumerate(objects)), "-o", str(linked)],
        f"{name} deterministic llvm-link")
    assembly = directory / "combined-c.s"
    run([str(COMPILER), "-target", "mos", "-Oz", "-x", "ir", "-S",
         str(linked), "-o", str(assembly)], f"{name} relocatable codegen")
    if assembly_suffix:
        with assembly.open("a", encoding="utf-8") as stream:
            stream.write(assembly_suffix)
    obj = directory / "combined-c.o"
    run([str(COMPILER), "-c", str(assembly), "-o", str(obj)],
        f"{name} assembly")
    return {"source": source_binding, "bitcode": bind(io_object),
            "combined_bitcode": bind(linked), "object": bind(obj),
            "symbols": symbol_sizes(obj), "sections": section_sizes(obj)}


def group_sections(rows: dict[str, int]) -> dict[str, int]:
    code = {name: size for name, size in rows.items()
            if name == ".text" or name.startswith(".text.") or
            name.startswith(".lisp65_") and "rela" not in name}
    ordinary = sum(size for name, size in code.items()
                   if name == ".text" or name.startswith(".text."))
    island = sum(size for name, size in code.items()
                 if name.startswith(".lisp65_resident_island"))
    mapped_cold = sum(size for name, size in code.items()
                      if name.startswith(".lisp65_c2_mapped_product_cold"))
    mapped_f011 = sum(size for name, size in code.items()
                      if name.startswith(".lisp65_c2_mapped_f011_cold"))
    return {"ordinary_text_bytes": ordinary,
            "resident_island_bytes": island,
            "mapped_product_cold_bytes": mapped_cold,
            "mapped_f011_cold_bytes": mapped_f011,
            "all_named_code_bytes": sum(code.values())}


def delta(after: dict[str, int], before: dict[str, int]) -> dict[str, int]:
    return {key: after[key] - before[key] for key in sorted(before)}


def build() -> None:
    require(not BUILD.exists() and not RECEIPT.exists(),
            "Card-2 F011 price is one-shot")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", AUTHORIZATION, "HEAD"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    require(ancestry.returncode == 0, "Card-2 text-preflight authorization drift")
    plan = " ".join(PLAN.read_text(encoding="utf-8").split())
    register = " ".join(REGISTER.read_text(encoding="utf-8").split())
    for token in ("evaluate the `$D082` error bits", "honour the BUSY",
                  "keeps its next-sector link in its own state cells",
                  "32-byte floor"):
        require(token in plan, f"Card-2 contract absent: {token}")
    require("bounded-codegen lane" in register
            and "measured signed bias" in register,
            "bounded-codegen bias rule absent from gate register")
    guard_price = load(GUARD_PRICE)
    card1 = load(CARD1)
    map_contract = load(MAP_CONTRACT)
    require(guard_price["decision"]["selected"] ==
            "accepted-inline-shared-predicate", "Card-1 guard decision drift")
    BUILD.mkdir(parents=True)
    flags = GUARD.compile_flags()
    original, source_binding = evidence_source()
    variants = {
        "accepted-card1-world": (None, ""),
        "complete-successor-inline-validator": (successor_source(
            original, shared_validator=False), ""),
        "complete-successor-shared-validator": (successor_source(
            original, shared_validator=True), ""),
        "complete-successor-mapped-cold": (
            mapped_cold_successor(original), MAPPED_COLD_WRAPPERS),
    }
    lanes = {name: lane(name, source, flags, suffix)
             for name, (source, suffix) in variants.items()}
    for row in lanes.values():
        row["groups"] = group_sections(row["sections"])
    baseline = lanes["accepted-card1-world"]["groups"]
    for name, row in lanes.items():
        row["group_delta_vs_card1"] = delta(row["groups"], baseline)
    bias = (guard_price["calibration"]["relocatable_codegen_delta_bytes"] -
            guard_price["calibration"]["final_link_delta_bytes"])
    candidates = {name: row for name, row in lanes.items()
                  if name != "accepted-card1-world"}
    composed = card1["final_product"]["composed_bank2"]
    shared_offset = composed["shared_offset"]
    far_lma_start = composed["owners"]["mapped_far_service"][0]
    far_vma_start = far_lma_start - shared_offset
    mapped_window_start = int(
        map_contract["map_semantics"]["cpu_window_start"], 0)
    mapped_capacity = far_vma_start - mapped_window_start
    for row in candidates.values():
        changes = row["group_delta_vs_card1"]
        row["placement_feasible"] = (
            changes["ordinary_text_bytes"] <= PLACEMENT_SLACK
            and changes["resident_island_bytes"] <= RESIDENT_ISLAND_SLACK
            and row["groups"]["mapped_f011_cold_bytes"] <= mapped_capacity)
    feasible = {name: row for name, row in candidates.items()
                if row["placement_feasible"]}
    selected = (min(feasible,
        key=lambda key: feasible[key]["group_delta_vs_card1"]["ordinary_text_bytes"])
        if feasible else min(candidates,
        key=lambda key: candidates[key]["group_delta_vs_card1"]["ordinary_text_bytes"]))
    selected_row = candidates[selected]
    selected_groups = selected_row["groups"]
    selected_delta = selected_row["group_delta_vs_card1"]
    raw_delta = selected_delta["ordinary_text_bytes"]
    calibrated = raw_delta - bias
    conservative = raw_delta
    text_deficit = max(0, conservative - PLACEMENT_SLACK)
    island_deficit = max(0, selected_delta["resident_island_bytes"] -
                         RESIDENT_ISLAND_SLACK)
    mapped_bytes = selected_groups["mapped_f011_cold_bytes"]
    mapped_vma_start = far_vma_start - mapped_bytes
    mapped_lma_start = mapped_vma_start + shared_offset
    largest_hole = composed["largest_contiguous_hole"]
    card_open = selected in feasible
    value = {
        "format": FORMAT, "recorded_on": "2026-09-03",
        "status": ("PASS: CARD 2 TEXT BUDGET PREFLIGHT" if card_open else
                   "RED: CARD 2 REQUIRES PRICED PLACEMENT"),
        "authorization": AUTHORIZATION,
        "inputs": {"plan": bind(PLAN), "gate_register": bind(REGISTER),
                   "map_contract": bind(MAP_CONTRACT),
                   "card1": bind(CARD1), "guard_price": bind(GUARD_PRICE),
                   "source": source_binding},
        "successor_contract": {
            "D082": "BUSY timeout plus DRQ/EQ completion and RNF/CRC/LOST rejection",
            "spinup": "bounded volatile register poll, not removable delay loop",
            "read_result": "failure reaches every direct f011_read_at consumer",
            "source_chain": "next link and failure state owned across nested compilation",
            "error_surface": "io_disk_load_chain returns false for existing LOAD_OPEN path",
        },
        "measurement": {
            "kind": "exact-frontend whole-C relocatable MOS codegen; no final link",
            "known_signed_bias_bytes": bias,
            "bias_definition": "relocatable lane minus final-link delta on Card 1",
            "final_capacity_claim": False,
            "lanes": lanes,
        },
        "placement": {
            "card1_text_floor_bytes": TEXT_FLOOR,
            "card1_facade_to_handoff_slack_bytes": PLACEMENT_SLACK,
            "card1_resident_island_slack_bytes": RESIDENT_ISLAND_SLACK,
            "selected_form": selected,
            "raw_lane_ordinary_text_delta_bytes": raw_delta,
            "bias_calibrated_point_bytes": calibrated,
            "conservative_pricing_delta_bytes": conservative,
            "ordinary_text_bytes_remaining_above_floor":
                PLACEMENT_SLACK - conservative,
            "required_text_reclaim_bytes": text_deficit,
            "resident_island_delta_bytes":
                selected_delta["resident_island_bytes"],
            "required_resident_island_reclaim_bytes": island_deficit,
            "mapped_cold": {
                "section": ".lisp65_c2_mapped_f011_cold",
                "bytes": mapped_bytes,
                "available_bytes_below_far_service": mapped_capacity,
                "remaining_mapped_window_bytes": mapped_capacity - mapped_bytes,
                "mapped_window_start": mapped_window_start,
                "vma_interval": [mapped_vma_start, far_vma_start],
                "lma_interval": [mapped_lma_start,
                                 far_lma_start],
                "shared_offset": shared_offset,
                "page_congruent_offset":
                    shared_offset % 0x100 == 0,
                "ordinary_wrapper_bytes": sum(
                    selected_row["symbols"].get(name, 0) for name in
                    ("f011_read_at", "io_disk_read_sector",
                     "disk_source_refill")),
                "body_symbols": {name: selected_row["symbols"].get(name, 0)
                                 for name in ("f011_wait_not_busy",
                                     "f011_read_at_far",
                                     "io_disk_read_sector_far",
                                     "disk_source_refill_far")},
                "composed_largest_hole_before_bytes": largest_hole["bytes"],
                "composed_largest_hole_after_bytes":
                    largest_hole["bytes"] - mapped_bytes,
            },
            "complete_successor_code_delta_bytes":
                selected_delta["all_named_code_bytes"],
            "existing_mapped_product_cold_delta_bytes":
                selected_delta["mapped_product_cold_bytes"],
            "service_time": {
                "disk_chain_MAP_transitions_added": 0,
                "ordinary_sector_read_MAP_transition_pairs_added": 1,
                "source_refill_transition_pairs_per_sector_boundary": 1,
                "hot_character_path_transition_pairs_added": 0,
                "reason": ("the already-mapped chain calls far read directly; "
                           "only cold ordinary reads and source-sector boundaries "
                           "cross the shared MAP facade"),
            },
            "rule": ("the raw over-reading lane is the conservative price; the real product "
                     "link must remeasure final text and retain the 32-byte floor"),
        },
        "decision": {
            "product_card_open": card_open,
            "selected_form": selected if card_open else None,
            "reason": ("complete successor fits ordinary text and resident island by placing "
                       "the cold F011/refill boundary below the existing mapped far service"
                       if card_open else
                       "no measured complete successor satisfies every composed placement wall"),
        },
        "accounting": {"product_WPLTO_runs": 0, "product_links": 0,
                       "device_contacts": 0},
    }
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    print(f"Block 2.6 Card 2 F011 price: {value['status']} "
          f"form={selected} text_delta={conservative} "
          f"island_delta={selected_delta['resident_island_bytes']}")


def validate(value: dict[str, Any]) -> None:
    placement = value["placement"]
    measurement = value["measurement"]
    require(
        value["format"] == FORMAT
        and value["authorization"] == AUTHORIZATION
        and measurement["known_signed_bias_bytes"] == 31
        and measurement["final_capacity_claim"] is False
        and placement["card1_text_floor_bytes"] == TEXT_FLOOR
        and placement["card1_facade_to_handoff_slack_bytes"] == PLACEMENT_SLACK
        and placement["card1_resident_island_slack_bytes"] ==
            RESIDENT_ISLAND_SLACK
        and placement["conservative_pricing_delta_bytes"] ==
            placement["raw_lane_ordinary_text_delta_bytes"]
        and placement["required_text_reclaim_bytes"] == max(
            0, placement["conservative_pricing_delta_bytes"] - PLACEMENT_SLACK)
        and placement["required_resident_island_reclaim_bytes"] == max(
            0, placement["resident_island_delta_bytes"] - RESIDENT_ISLAND_SLACK)
        and placement["mapped_cold"]["shared_offset"] % 0x100 == 0
        and placement["mapped_cold"]["page_congruent_offset"] is True
        and placement["mapped_cold"]["bytes"] > 0
        and placement["mapped_cold"]["ordinary_wrapper_bytes"] == 30
        and sum(placement["mapped_cold"]["body_symbols"].values()) ==
            placement["mapped_cold"]["bytes"]
        and placement["mapped_cold"]["remaining_mapped_window_bytes"] ==
            placement["mapped_cold"]["available_bytes_below_far_service"] -
            placement["mapped_cold"]["bytes"]
        and placement["mapped_cold"]["composed_largest_hole_after_bytes"] ==
            placement["mapped_cold"]["composed_largest_hole_before_bytes"] -
            placement["mapped_cold"]["bytes"]
        and placement["mapped_cold"]["vma_interval"][1] ==
            placement["mapped_cold"]["lma_interval"][1] -
            placement["mapped_cold"]["shared_offset"]
        and placement["mapped_cold"]["vma_interval"][0] >=
            placement["mapped_cold"]["mapped_window_start"]
        and placement["mapped_cold"]["vma_interval"][1] -
            placement["mapped_cold"]["vma_interval"][0] ==
            placement["mapped_cold"]["bytes"]
        and [value + placement["mapped_cold"]["shared_offset"] for value in
             placement["mapped_cold"]["vma_interval"]] ==
            placement["mapped_cold"]["lma_interval"]
        and placement["service_time"]["disk_chain_MAP_transitions_added"] == 0
        and placement["service_time"]["hot_character_path_transition_pairs_added"] == 0
        and value["accounting"] == {"product_WPLTO_runs": 0,
            "product_links": 0, "device_contacts": 0},
        "Card-2 F011 pricing receipt drift",
    )
    if value["decision"]["product_card_open"]:
        require(value["status"] == "PASS: CARD 2 TEXT BUDGET PREFLIGHT"
                and placement["required_text_reclaim_bytes"] == 0
                and placement["required_resident_island_reclaim_bytes"] == 0
                and value["measurement"]["lanes"][
                    value["decision"]["selected_form"]]["placement_feasible"],
                "Card-2 opened below text floor")
    else:
        require(value["status"] == "RED: CARD 2 REQUIRES PRICED PLACEMENT"
                and value["decision"]["selected_form"] is None,
                "Card-2 red did not remain closed")


def report(value: dict[str, Any]) -> str:
    lanes = value["measurement"]["lanes"]
    direct = lanes["complete-successor-shared-validator"][
        "group_delta_vs_card1"]
    rows = []
    for name, row in lanes.items():
        groups = row["groups"]
        delta_row = row["group_delta_vs_card1"]
        rows.append(f"| `{name}` | {groups['ordinary_text_bytes']} | "
                    f"{delta_row['ordinary_text_bytes']:+d} | "
                    f"{delta_row['resident_island_bytes']:+d} | "
                    f"{groups['mapped_f011_cold_bytes']} | "
                    f"{'yes' if row.get('placement_feasible') else 'no'} |")
    placement = value["placement"]
    return f"""# Block 2.6 Card 2 — F011 text-budget preflight

Status: **{value['status']}**

This host-only preflight materializes the complete successor source: bounded
spin-up and read BUSY polls, final `$D082` completion/error evaluation, failure
propagation through every direct F011 read consumer, and source-owned validated
next-sector state across nested compilation. It performs **0 product WPLTOs,
0 product links and 0 device contacts**.

| form | ordinary lane bytes | delta | resident-island delta | F011 cold bytes | composed fit |
|---|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

The lane is deliberately not promoted to final-link truth. Its known Card-1
bias is **+{value['measurement']['known_signed_bias_bytes']} bytes**
(relocatable codegen minus real final-link delta). The raw successor delta of
**{placement['raw_lane_ordinary_text_delta_bytes']} bytes** is therefore kept
as the conservative price; the bias-corrected
**{placement['bias_calibrated_point_bytes']} bytes** is informative only.

The accepted Card-1 image has {TEXT_FLOOR} required bytes before the movable
far facade, exactly **{PLACEMENT_SLACK} additional ordinary-text bytes** before
the fixed Handoff owner, and **{RESIDENT_ISLAND_SLACK} resident-island byte**
before its annex. The selected complete form changes ordinary text by
**{placement['conservative_pricing_delta_bytes']:+d} bytes** and the island by
**{placement['resident_island_delta_bytes']:+d} bytes**. It therefore leaves
**{placement['ordinary_text_bytes_remaining_above_floor']} ordinary-text bytes
above the floor** and requires no reclaim in either constrained arena.

For comparison, leaving every new body in its old arena costs
**{direct['ordinary_text_bytes']:+d} ordinary-text bytes** and
**{direct['resident_island_bytes']:+d} resident-island bytes**; both walls fail. The selected
form materializes the same full successor with **{placement['complete_successor_code_delta_bytes']:+d}
bytes total code**, including the existing product-cold chain's
**{placement['existing_mapped_product_cold_delta_bytes']:+d}-byte** live failure
branch, but changes where that code is owned rather than deleting semantics.

The priced source is a new **{placement['mapped_cold']['bytes']}-byte** cold
owner, `.lisp65_c2_mapped_f011_cold`, top-anchored immediately below the
existing far service. The current far-service boundary and `$28000` offset
come from the accepted Card-1 composed map; the `$6000` CPU-window floor comes
from the bound MAP contract. Its derived VMA interval is
`${placement['mapped_cold']['vma_interval'][0]:04X}..${placement['mapped_cold']['vma_interval'][1]:04X}`
and its LMA interval is
`${placement['mapped_cold']['lma_interval'][0]:06X}..${placement['mapped_cold']['lma_interval'][1]:06X}`;
the shared `$28000` offset is page-congruent. Its three measured ordinary
wrappers total **{placement['mapped_cold']['ordinary_wrapper_bytes']} bytes**.
The 467-byte owner leaves **{placement['mapped_cold']['remaining_mapped_window_bytes']}
bytes** in the mapped CPU interval below the far service and reduces the
composed largest Bank-2 hole from
**{placement['mapped_cold']['composed_largest_hole_before_bytes']}** to
**{placement['mapped_cold']['composed_largest_hole_after_bytes']} bytes**.
The already-mapped disk-chain path calls the far reader directly, so it adds
zero MAP transitions. Ordinary cold reads add one enter/leave pair; the source
reader adds one pair only at a sector boundary, never per character.

Decision: **{'open the product card' if value['decision']['product_card_open'] else 'keep the product card closed'}**.
The final product link, if later authorized, must derive the actual text end,
retain the 32-byte floor and reject any facade/Handoff overlap.
"""


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    require(value["inputs"] == {"plan": evidence_binding(PLAN),
        "gate_register": evidence_binding(REGISTER),
        "map_contract": bind(MAP_CONTRACT),
        "card1": bind(CARD1), "guard_price": bind(GUARD_PRICE),
        "source": evidence_source()[1]}, "Card-2 pricing input drift")
    print(f"Block 2.6 Card 2 F011 price: CHECK PASS "
          f"open={int(value['decision']['product_card_open'])}")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "bias-forgotten": lambda row: row["measurement"].update(
            {"known_signed_bias_bytes": 0}),
        "fragment-promoted": lambda row: row["measurement"].update(
            {"final_capacity_claim": True}),
        "floor-lowered": lambda row: row["placement"].update(
            {"card1_text_floor_bytes": 31}),
        "text-reclaim-miscalculated": lambda row: row["placement"].update(
            {"required_text_reclaim_bytes": 1}),
        "island-reclaim-miscalculated": lambda row: row["placement"].update(
            {"required_resident_island_reclaim_bytes": 1}),
        "mapped-offset-not-congruent": lambda row: row["placement"][
            "mapped_cold"].update({"page_congruent_offset": False}),
        "cold-owner-removed": lambda row: row["placement"][
            "mapped_cold"].update({"bytes": 0}),
        "cold-body-unaccounted": lambda row: row["placement"][
            "mapped_cold"]["body_symbols"].update({"f011_wait_not_busy": 0}),
        "nested-map-added": lambda row: row["placement"]["service_time"].update(
            {"disk_chain_MAP_transitions_added": 1}),
        "red-card-opened": lambda row: row["decision"].update(
            {"product_card_open": True, "selected_form": "unpriced"}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (PricingError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "Card-2 pricing mutation survived")
    print(f"Block 2.6 Card 2 F011 price: SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "selftest"))
    action = parser.parse_args().action
    try:
        {"build": build, "check": check, "selftest": selftest}[action]()
    except (PricingError, OSError, subprocess.SubprocessError,
            json.JSONDecodeError) as error:
        print(f"Block 2.6 Card 2 F011 price: RED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
