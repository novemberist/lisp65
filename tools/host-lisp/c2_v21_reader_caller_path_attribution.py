#!/usr/bin/env python3
"""Attribute the Link-112/113 D2 poison to the physical REPL input seam.

The commissioned question started at the Bank-4 MAP reader.  This checker
follows the evidence one stage farther upstream: it decodes the captured EXT
heap, reconstructs the exact compiler object which the C2 emitter consumed,
and models the target REPL/reader treatment of PETSCII shifted-space $A0.
No product byte is changed and no device is contacted.
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


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
from c2_v150_name_freight_d2_badopcode_capture import host_compile  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
ELF = ROOT / (
    "build/c2.3/v2.1-root-padding-configurator-parity-continuation/final/"
    "lisp65-c2-substitution-linked.prg.elf")
FINAL_LINK = ROOT / (
    "build/c2.3/v2.1-root-padding-configurator-parity-continuation/"
    "configurator-parity-final-link.json")
CAP112 = ROOT / "build/c2.3/v2.1-link112-d2-full-span-oracle-capture"
CAP113 = ROOT / "build/c2.3/v2.1-link113-d2-root-reader-rescue"
R112 = ARCH / "c2.3-v2.1-link112-d2-probe-oracle-capture-receipt.json"
R113 = ARCH / "c2.3-v2.1-link113-d2-bank4-root-reader-rescue-receipt.json"
PROBE = ARCH / "c2.3-v2.1-bank4-map-probe-device-receipt.json"
RECEIPT = ARCH / "c2.3-v2.1-reader-caller-path-attribution-receipt.json"
REPL = ROOT / "src/repl.c"
READER = ROOT / "src/reader.c"
SCREEN = ROOT / "src/screen.c"
KERNAL = ROOT / "src/c2_kernal_window.s"
MEM = ROOT / "src/mem.c"
EMITTER = ROOT / "src/c2_session_emitter.c"

AUTHORIZATION = "f1aabb5f"
FORMAT = "lisp65-c2.3-v2.1-reader-caller-path-attribution-v1"
STATUS = "ATTRIBUTED: INVISIBLE-PETSCII-A0-INGRESS"
HEAP_CELLS = 48
EXT_CELLS = 1024
DISK_EXT_BASE = 0x6900
EXT_BANK = 4
STAGED_PHYSICAL = 0x00046A00
STAGED_BYTES = 148
POISON_CODE = bytes.fromhex("b50100020b0001000006003d13013b0b01010205")
POISON_PAYLOAD = bytes.fromhex("06003d13013b0b01010205")
CANONICAL_CODE = bytes.fromhex("b50100020500000b01010205")
SYMI_BASE = 0x7000


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def git_authority() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().split())
    for token in (
        "reader/caller-path attribution commissioned", "bind the caller's derivation",
        "the write side stays in scope", "host-model the exact staging",
        "no fix before the name",
    ):
        require(token in text, f"authorization token absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def symi(index: int) -> int:
    return ((SYMI_BASE + index) << 1) & 0xFFFF


def fixnum(value: int) -> int:
    return ((value << 1) | 1) & 0xFFFF


class ExtHeap:
    def __init__(self, raw: bytes):
        require(len(raw) == 0x6C00, "captured Bank-4 range drift")
        self.raw = raw

    def cell(self, index: int) -> dict[str, int]:
        require(HEAP_CELLS <= index < HEAP_CELLS + EXT_CELLS,
                f"EXT cell outside product heap: {index}")
        at = (index - HEAP_CELLS) * 8
        return {"index": index, "physical": 0x40000 + at,
                "type": self.raw[at],
                "a": int.from_bytes(self.raw[at + 2:at + 4], "little"),
                "b": int.from_bytes(self.raw[at + 4:at + 6], "little")}

    def list(self, value: int, limit: int = 128) -> tuple[list[int], list[int]] | None:
        cells: list[int] = []
        values: list[int] = []
        while value:
            if value & 1 or value >= 0xE000:
                return None
            index = value >> 1
            if index in cells or not HEAP_CELLS <= index < HEAP_CELLS + EXT_CELLS:
                return None
            row = self.cell(index)
            if row["type"] != 0:
                return None
            cells.append(index)
            values.append(row["a"])
            value = row["b"]
            if len(cells) > limit:
                return None
        return cells, values

    def source_forms(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index in range(HEAP_CELLS, HEAP_CELLS + EXT_CELLS):
            top = self.list(index << 1)
            if top is None or len(top[1]) != 5:
                continue
            values = top[1]
            args = self.list(values[2])
            body = self.list(values[4])
            if args is None or body is None:
                continue
            if (values[0] != symi(181) or len(args[1]) != 1
                    or args[1] != [symi(709)]
                    or values[3] != symi(710)
                    or body[1] != [symi(527), symi(709), fixnum(1)]):
                continue
            name_index = ((values[1] >> 1) - SYMI_BASE)
            rows.append({
                "root_cell": index,
                "root_physical": f"0x{self.cell(index)['physical']:08x}",
                "spine_cells": top[0],
                "spine_physical": [f"0x{self.cell(i)['physical']:08x}" for i in top[0]],
                "element_symbol_indices": [181, name_index, None, 710, None],
                "name_symbol_index": name_index,
                "parameter_symbol_index": 709,
                "inserted_symbol_index": 710,
                "inserted_symbol_object": "0xe58c",
                "inserted_position": "between parameter list and function body",
                "body": ["SYMI:527 (+)", "SYMI:709 (x)", "FIX:1"],
                "top_level_element_count": 5,
            })
        return rows

    def compiler_records(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index in range(HEAP_CELLS, HEAP_CELLS + EXT_CELLS):
            record = self.list(index << 1)
            if record is None or record[1][:3] != [fixnum(1), fixnum(0), fixnum(2)] \
                    or len(record[1]) != 5:
                continue
            literals = self.list(record[1][3])
            code = self.list(record[1][4])
            if literals is None or code is None or literals[1] != [symi(710)]:
                continue
            if not all(value & 1 for value in code[1]):
                continue
            payload = bytes(value >> 1 for value in code[1])
            if payload != POISON_PAYLOAD:
                continue
            encoded = (bytes((0xB5, 1, 0, 2)) + len(payload).to_bytes(2, "little")
                       + bytes((1, 0, 0)) + payload)
            rows.append({
                "record_root_cell": index,
                "record_cells": record[0],
                "literal_cells": literals[0],
                "code_cells": code[0],
                "code_cell_physical": [f"0x{self.cell(i)['physical']:08x}" for i in code[0]],
                "nargs": 1, "nlocals": 0, "flags": 2,
                "literal_symbol_index": 710,
                "code_count": len(payload), "payload_hex": payload.hex(),
                "emitter_model_hex": encoded.hex(),
                "emitter_model_matches_staged_poison": encoded == POISON_CODE,
            })
        return rows


def staged_object(raw: bytes) -> dict[str, Any]:
    value = raw[0x6A00:0x6A00 + STAGED_BYTES]
    require(len(value) == STAGED_BYTES and value[:4] == b"L65S",
            "staged object envelope drift")
    code_off = int.from_bytes(value[40:43], "little")
    code_len = int.from_bytes(value[43:45], "little")
    code = value[code_off:code_off + code_len]
    require(code == POISON_CODE, "staged poison bytes drift")
    return {"physical": "0x00046a00", "bytes": len(value),
            "sha256": digest(value), "code_offset": code_off,
            "code_bytes": code_len, "code_hex": code.hex()}


def parse_model(raw: bytes) -> Any:
    at = 0

    def delim(value: int) -> bool:
        return value <= 0x20 or value in b"();'\"`,"

    def skip() -> None:
        nonlocal at
        while at < len(raw) and raw[at] <= 0x20:
            at += 1

    def one() -> Any:
        nonlocal at
        skip()
        require(at < len(raw), "model parser unexpected EOF")
        if raw[at] == ord("("):
            at += 1
            result = []
            while True:
                skip()
                require(at < len(raw), "model parser unclosed list")
                if raw[at] == ord(")"):
                    at += 1
                    return result
                result.append(one())
        start = at
        while at < len(raw) and not delim(raw[at]):
            at += 1
        require(at > start, "model parser empty atom")
        token = raw[start:at]
        if all(ord("0") <= value <= ord("9") for value in token):
            return int(token)
        return {"atom_hex": token.hex(),
                "atom_ascii": token.decode("ascii") if token.isascii() else None}

    result = one()
    skip()
    require(at == len(raw), "model parser trailing input")
    return result


def input_seam() -> dict[str, Any]:
    repl = REPL.read_text(encoding="utf-8")
    reader = READER.read_text(encoding="utf-8")
    screen = SCREEN.read_text(encoding="utf-8")
    kernal = KERNAL.read_text(encoding="utf-8")
    require("if (c < 0x20 || (c >= 0x80 && c < 0xA0)) continue;" in repl,
            "REPL acceptance boundary changed")
    require("buf[n++] = (char)c;" in repl,
            "REPL raw-byte store changed")
    require("return 0x20;" in screen and "Unbekanntes: Leerzeichen" in screen,
            "screen invisibility mapping changed")
    require("return c <= ' ' || c == '(' || c == ')'" in reader,
            "reader delimiter rule changed")
    require("lda $d619" in kernal and "sta (__rc2),z" in kernal,
            "typed queue raw PETSCII handoff changed")

    compiler = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
    probe = subprocess.run(
        [str(compiler), "-x", "c", "-fsyntax-only", "-"], cwd=ROOT,
        input=("_Static_assert((char)0xA0 > (char)0x20, "
               "\"llvm-mos char must be unsigned\");\n"), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(probe.returncode == 0, "target char signedness changed")

    typed = b"(defun trace-probe (x) \xa0 (+ x 1))"
    accepted = bytes(value for value in typed
                     if not (value < 0x20 or 0x80 <= value < 0xA0))
    rendered = bytes(value if 0x20 <= value <= 0x3F else 0x20
                     for value in accepted)
    tree = parse_model(accepted)
    require(isinstance(tree, list) and len(tree) == 5
            and tree[3] == {"atom_hex": "a0", "atom_ascii": None},
            "$A0 model no longer creates a fifth top-level element")
    control = host_compile("(defun trace-probe (x) ghost-token (+ x 1))")
    require(control["payload_hex"] == POISON_PAYLOAD.hex()
            and control["literal_count"] == 1,
            "one-symbol expression compiler control drift")
    return {
        "queue_transport": "$D619 PETSCII byte is copied unchanged into event.code",
        "accepted_byte": "0xa0",
        "accepted_by_filter": accepted == typed,
        "target_char_semantics": "unsigned; 0xa0 > ASCII space",
        "reader_classification": "one-byte atom, not whitespace",
        "rendering": "screen driver maps the unknown byte to visible blank 0x20",
        "stealth_property": rendered[typed.index(0xA0)] == 0x20,
        "model_tree": tree,
        "model_top_level_elements": len(tree),
        "compiler_control": control,
        "compiler_control_payload_matches_capture": True,
    }


def symbol_bytes(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    raw = truth.section_bytes(symbol.section)
    at = symbol.value - section.address
    require(0 <= at <= len(raw) and at + symbol.bytes <= len(raw),
            f"symbol outside section: {name}")
    return raw[at:at + symbol.bytes]


def emitted_paths() -> dict[str, Any]:
    truth = ElfTruth.read(
        ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    symbols = {name: truth.symbol(name) for name in (
        "c2_map_cpu_read", "ext_dma", "ext_disk_get", "ext_disk_put",
        "ext_set_type", "ext_set_a", "ext_set_b", "alloc", "cons")}
    expected = {
        "c2_map_cpu_read": (0x2277, 0xBD), "ext_dma": (0x3633, 0x44),
        "ext_disk_get": (0x3677, 0x1E), "ext_disk_put": (0x3764, 0x27),
        "ext_set_type": (0x3F90, 0x2E), "ext_set_a": (0x3600, 0x33),
        "ext_set_b": (0x398D, 0x33), "alloc": (0x378B, 0x119),
        "cons": (0x6759, 0xE8),
    }
    require({name: (row.value, row.bytes) for name, row in symbols.items()}
            == expected, "emitted caller/write symbol identity drift")
    dma = symbol_bytes(truth, "ext_dma")
    require(dma.endswith(bytes.fromhex(
        "a9008d02d7a9bc8d01d7a9788d00d760")),
        "ext_dma no longer triggers D700 then returns immediately")
    require(symbol_bytes(truth, "ext_disk_get").find(bytes.fromhex("205033")) >= 0,
            "ext_disk_get no longer calls CPU read wrapper")
    for name in ("ext_set_type", "ext_set_a", "ext_set_b", "ext_disk_put"):
        require(symbol_bytes(truth, name).endswith(bytes.fromhex("4c3336")),
                f"{name} no longer tail-calls ext_dma")

    mem = MEM.read_text(encoding="utf-8")
    emitter = EMITTER.read_text(encoding="utf-8")
    require("ext_disk_get((uint16_t)(256u + at))" in emitter
            and "ext_disk_put((uint16_t)(256u + at), value)" in emitter,
            "emitter disk caller derivation changed")
    require("EXT_BANK, &ext_stg1, 1" in mem,
            "ext_disk_get byte length changed")
    require("HEAP_CELLS=48" in FINAL_LINK.read_text(encoding="utf-8")
            and "EXT_CELLS=1024" in FINAL_LINK.read_text(encoding="utf-8")
            and "DISK_EXT_BASE=0x6900" in FINAL_LINK.read_text(encoding="utf-8"),
            "consumed candidate geometry drift")
    require(((EXT_BANK << 16) | (DISK_EXT_BASE + 256)) == STAGED_PHYSICAL,
            "staged caller arithmetic drift")
    return {
        "symbols": {name: {"address": f"0x{row.value:04x}", "bytes": row.bytes,
                           "sha256": digest(symbol_bytes(truth, name))}
                    for name, row in symbols.items()},
        "staging_caller": {
            "operation": "148 separate one-byte ext_disk_get/ext_disk_put calls",
            "first_physical": "0x00046a00", "last_physical": "0x00046a93",
            "length_per_call": 1, "page_crossing_per_call": False,
            "MAP_window_crossing_per_call": False,
        },
        "heap_caller": {
            "type_length": 1, "a_length": 2, "b_length": 2,
            "MAP_window_crossing_per_call": False,
        },
        "reader": {
            "address": "0x2277", "bytes": symbols["c2_map_cpu_read"].bytes,
            "Bank4_probe": "256/256 exact raw reads; MAP/Z restored",
        },
        "write_side": {
            "disk_stage": "raw ext_dma writes through shared ext_stg1",
            "EXT_heap": "raw ext_dma writes through shared ext_stg1/ext_stg",
            "ext_dma_exit": "D700 trigger followed immediately by RTS",
            "this_failure": (
                "not introduced by disk staging: both source form and exact "
                "compiler record pre-exist in EXT heap before serialization"),
            "general_write_completion_claim": "not decided by this attribution",
        },
    }


def capture_model(path: Path, expected_source_names: list[int],
                  expected_count: int) -> dict[str, Any]:
    raw = (path / "physical-bank4.bin").read_bytes()
    heap = ExtHeap(raw)
    forms = sorted(heap.source_forms(), key=lambda row: row["name_symbol_index"])
    records = heap.compiler_records()
    require([row["name_symbol_index"] for row in forms] == expected_source_names,
            f"captured source-form set drift: {path}")
    require(len(records) == expected_count
            and all(row["emitter_model_matches_staged_poison"] for row in records),
            f"compiler-record set drift: {path}")
    return {"capture": path.relative_to(ROOT).as_posix(),
            "source_forms": forms, "compiler_records": records,
            "staged_object": staged_object(raw)}


def derive() -> dict[str, Any]:
    link112 = capture_model(CAP112, [708, 711], 2)
    link113 = capture_model(CAP113, [708], 1)
    require(link112["staged_object"]["sha256"]
            == "a1029fc815207908304659dda52576334743e869101bb999d78cba61f35d0626",
            "Link-112 staged identity drift")
    require(link113["staged_object"]["sha256"]
            == "40acc5f061b755f2a2ddda4b6cbd64ac3bba9eae1c6295493411d38b09d86fcd",
            "Link-113 staged identity drift")
    r112, r113, probe = load(R112), load(R113), load(PROBE)
    require(r112["staged_object"]["fresh_name"] is True
            and r112["historical_control"]["same_noncanonical_literal_byte"] == "0xa0"
            and r112["stopped_state"]["sym_name_scratch_hex"].startswith("a000")
            and r113["stopped_state"]["sym_name_scratch_hex"].startswith("a000")
            and r113["three_way_comparison"]["staged_object"]["metadata"]
                ["noncanonical_literal_byte"] == "0xa0"
            and r113["conclusion"]["product_path_membership"] is True,
            "capture authority drift")
    require(probe.get("decision")
            == "INTRINSIC-BANK4-PROPERTY-REFUTED; READER-CALLER-PATH-CONVICTED",
            "Bank-4 probe decision drift")
    seam = input_seam()
    paths = emitted_paths()
    value = {
        "format": FORMAT, "recorded_on": "2026-08-17", "status": STATUS,
        "capture_models": {"Link112": link112, "Link113": link113},
        "input_seam": seam, "emitted_paths": paths,
        "attribution": {
            "named_site": "src/repl.c:read_line PETSCII acceptance boundary",
            "mechanism": (
                "PETSCII shifted-space $A0 is passed raw by the typed queue, "
                "accepted and stored by read_line, rendered as an invisible "
                "blank, then parsed as a one-byte symbol rather than whitespace"),
            "two_live_forms": [
                "trace-probe source graph contains SYMI710 between args and body",
                "test-probe source graph contains the same SYMI710 at the same position",
            ],
            "compiler_behavior": (
                "correctly compiles the resulting five-element defun as one "
                "extra symbol expression plus the intended body"),
            "emitter_behavior": (
                "correctly serializes the pre-existing 11-byte compiler payload "
                "into the exact 20-byte poison object"),
            "captured_symbol_name_evidence": (
                "both independently persisted symbol-name scratch rows begin "
                "a000; the inserted SYMI710 is the one-byte $A0 atom"),
            "bank4_MAP_reader_exonerated_for_this_failure": True,
            "copy_boundary_exonerated_for_this_failure": True,
            "disk_staging_write_exonerated_for_this_failure": True,
            "historical_F018B_membership_for_these_poison_objects": False,
            "fix_authorized": False,
            "device_contact_authorized": False,
        },
        "claim_limit": (
            "This desk attribution names the D2 poison mechanism and corrects "
            "the earlier F018B classification for these two objects. It does "
            "not authorize a REPL fix, product link, medium, device contact, "
            "resume, or D3-D5. The general completion status of unrelated EXT "
            "writes remains outside this claim."),
        "authority": {
            "owner": git_authority(), "ELF": bind(ELF),
            "final_link": bind(FINAL_LINK), "Link112_receipt": bind(R112),
            "Link113_receipt": bind(R113), "Bank4_probe": bind(PROBE),
            "Link112_bank4": bind(CAP112 / "physical-bank4.bin"),
            "Link113_bank4": bind(CAP113 / "physical-bank4.bin"),
            "repl": bind(REPL), "reader": bind(READER), "screen": bind(SCREEN),
            "kernal": bind(KERNAL), "mem": bind(MEM), "emitter": bind(EMITTER),
            "checker": bind(Path(__file__)),
        },
        "execution_accounting": {"WPLTO": 0, "links": 0,
                                 "product_bytes_changed": 0,
                                 "device_contacts": 0, "device_resumes": 0},
    }
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    attr = value["attribution"]
    seam = value["input_seam"]
    captures = value["capture_models"]
    require(value["format"] == FORMAT and value["status"] == STATUS,
            "attribution identity drift")
    require(seam["accepted_byte"] == "0xa0"
            and seam["accepted_by_filter"] is True
            and seam["stealth_property"] is True
            and seam["model_top_level_elements"] == 5
            and seam["compiler_control_payload_matches_capture"] is True,
            "input-seam mechanism lost")
    require(len(captures["Link112"]["source_forms"]) == 2
            and len(captures["Link113"]["source_forms"]) == 1
            and all(row["inserted_symbol_index"] == 710
                    for capture in captures.values()
                    for row in capture["source_forms"]),
            "repeated source-form evidence lost")
    require(all(row["emitter_model_matches_staged_poison"] is True
                for capture in captures.values()
                for row in capture["compiler_records"]),
            "pre-stage compiler graph proof lost")
    require(attr["bank4_MAP_reader_exonerated_for_this_failure"] is True
            and attr["copy_boundary_exonerated_for_this_failure"] is True
            and attr["disk_staging_write_exonerated_for_this_failure"] is True
            and attr["historical_F018B_membership_for_these_poison_objects"] is False
            and attr["fix_authorized"] is False
            and attr["device_contact_authorized"] is False,
            "claim boundary drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "reject-A0-fact": lambda x: x["input_seam"].__setitem__("accepted_by_filter", False),
        "make-A0-visible": lambda x: x["input_seam"].__setitem__("stealth_property", False),
        "parse-four-elements": lambda x: x["input_seam"].__setitem__("model_top_level_elements", 4),
        "change-compiler-payload": lambda x: x["input_seam"].__setitem__(
            "compiler_control_payload_matches_capture", False),
        "drop-link112-repeat": lambda x: x["capture_models"]["Link112"]
            ["source_forms"].pop(),
        "drop-link113-form": lambda x: x["capture_models"]["Link113"]
            ["source_forms"].clear(),
        "change-inserted-symbol": lambda x: x["capture_models"]["Link113"]
            ["source_forms"][0].__setitem__("inserted_symbol_index", 709),
        "break-emitter-model": lambda x: x["capture_models"]["Link113"]
            ["compiler_records"][0].__setitem__(
                "emitter_model_matches_staged_poison", False),
        "convict-bank4-MAP-reader": lambda x: x["attribution"].__setitem__(
            "bank4_MAP_reader_exonerated_for_this_failure", False),
        "convict-boundary": lambda x: x["attribution"].__setitem__(
            "copy_boundary_exonerated_for_this_failure", False),
        "convict-stage-write": lambda x: x["attribution"].__setitem__(
            "disk_staging_write_exonerated_for_this_failure", False),
        "retain-F018B-claim": lambda x: x["attribution"].__setitem__(
            "historical_F018B_membership_for_these_poison_objects", True),
        "silently-authorize-fix": lambda x: x["attribution"].__setitem__(
            "fix_authorized", True),
        "silently-authorize-device": lambda x: x["attribution"].__setitem__(
            "device_contact_authorized", True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "reader/caller mutation survived")
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
        require(load(RECEIPT) == value, "reader/caller attribution receipt stale")
    else:
        require(len(value["mutations_rejected"]) == 14, "mutation count drift")
    print(f"reader/caller attribution: PASS action={action} site=REPL-A0 mutations=14")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"reader/caller attribution: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
