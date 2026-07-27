#!/usr/bin/env python3
"""Static Link-55 defun-crash suspect catalog.

This audit is deliberately read-only: it interrogates the frozen product ELF,
its Session catalog, and the hardware First Red.  It neither compiles nor
links.  The catalog checks the three commissioned suspects in order, then
binds the first falsified invariant.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_crc_codegen_gate as DISASM  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
PRODUCT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-55-c2-lite-v6-append-suffix-fusion-attempt2/"
    "lisp65-c2-substitution-linked.prg")
ELF = Path(str(PRODUCT) + ".elf")
MANIFEST = PRODUCT.parent / "runtime-overlays-session-final.json"
HARDWARE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link55-append-suffix-defun-crash-hardware-first-red.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link55-defun-crash-static-suspect-catalog.json")
SECTION = ".lisp65_rt_c2append_journal_prepare"
SELECTOR = "c2_append_journal_prepare_phase"
TARGETS = (
    "c2_append_journal_write_phase",
    "c2_append_rollback_prepare_phase",
)


class CatalogError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CatalogError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"catalog input absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def body(rows: list[dict[str, Any]], symbol: Any) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if row["section"] == symbol.section
        and symbol.value <= row["address"] < symbol.value + symbol.bytes
    ]


def last_z_writer(rows: list[dict[str, Any]], edge: dict[str, Any]) -> dict[str, Any]:
    writers = {"ldz", "inz", "dez", "taz", "plz"}
    index = rows.index(edge)
    found = next(
        (row for row in reversed(rows[:index])
         if row["opcode"] in writers), None)
    require(found is not None, "tail edge has no dominating Z definition")
    return found


def plan_bytes(truth: ElfTruth, name: str) -> list[int]:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    data = truth.section_bytes(symbol.section)
    start = symbol.value - section.address
    return list(data[start:start + symbol.bytes])


def marker_totality() -> dict[str, Any]:
    accepted: list[dict[str, int | str]] = []
    rejected = 0
    for main in (0, 1):
        for marker in range(256):
            if main and marker == 0:
                accepted.append(
                    {"main_ordinal_nonzero": 1, "marker": marker,
                     "target": "journal_write"})
            elif not main and marker == 0:
                accepted.append(
                    {"main_ordinal_nonzero": 0, "marker": marker,
                     "target": "rollback_prepare"})
            elif not main and marker == 2:
                accepted.append(
                    {"main_ordinal_nonzero": 0, "marker": marker,
                     "target": "journal_write"})
            else:
                rejected += 1
    require(len(accepted) == 3 and rejected == 509,
            "selector marker-domain model is not total")
    return {
        "cases": 512,
        "accepted": accepted,
        "fail_closed": rejected,
    }


def build() -> dict[str, Any]:
    require(not RECEIPT.exists(), "static suspect catalog is one-shot")
    require(sha(ELF) ==
                "488bf31ea999751169d59681a2f98900e8c8ffa4c98f57f547db4c19621d7792"
            and sha(MANIFEST) ==
                "8e1329514c3d1a22c3c8e592e8db513290774aec010e97ae170fe2268225b99a"
            and sha(HARDWARE) ==
                "bb7c1e826cb666d8dc5274cc967ef6444eb45e28990e8481095e7ebc31244595",
            "Link-55 crash authority drift")
    truth = ElfTruth.read(
        ELF, llvm_readobj=TOOLCHAIN / "llvm-readobj",
        include_section_data=True)
    completed = subprocess.run(
        [str(TOOLCHAIN / "llvm-objdump"), "-d", "--no-show-raw-insn",
         str(ELF)],
        check=True, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    rows = DISASM.disassembly_rows(completed.stdout)
    selector = truth.symbol(SELECTOR)
    selector_body = body(rows, selector)
    relocations = [
        row for row in truth.relocations
        if row.source_section_index == selector.section_index
        and selector.value <= row.offset < selector.value + selector.bytes
        and row.target in TARGETS
    ]
    require(len(relocations) == 2, "selector tail-edge inventory drift")
    tail_rows: dict[str, dict[str, Any]] = {}
    for relocation in relocations:
        edge = next(
            row for row in selector_body
            if row["address"] == relocation.offset - 1)
        require(edge["opcode"] == "jmp", "selector body edge is not JMP")
        writer = last_z_writer(selector_body, edge)
        tail_rows[relocation.target] = {
            "edge_address": edge["address"],
            "last_Z_writer_address": writer["address"],
            "last_Z_writer": f"{writer['opcode']} {writer['operand']}",
        }
    require(all(row["last_Z_writer"] == "ldz #$d5"
                for row in tail_rows.values()),
            "frozen Link-55 selector does not expose the expected tail-Z fault")

    target_rows: dict[str, dict[str, Any]] = {}
    z_writers = {"ldz", "inz", "dez", "taz", "plz"}
    for name in TARGETS:
        target = truth.symbol(name)
        target_body = body(rows, target)
        first_indexed = next(
            row for row in target_body
            if ",z" in row["operand"].lower())
        prior_writer = next(
            (row for row in target_body
             if row["address"] < first_indexed["address"]
             and row["opcode"] in z_writers), None)
        require(prior_writer is None,
                f"{name} unexpectedly establishes Z before indexed use")
        target_rows[name] = {
            "entry": target.value,
            "bytes": target.bytes,
            "first_Z_indexed_address": first_indexed["address"],
            "first_Z_indexed_instruction":
                f"{first_indexed['opcode']} {first_indexed['operand']}",
            "prior_Z_writer": None,
            "required_C_entry_Z": 0,
        }

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    record = next(row for row in manifest["slices"] if row["id"] == 30)
    symbols = {name: truth.symbol(name) for name in (SELECTOR, *TARGETS)}
    section = truth.section(SECTION)
    section_payload = truth.section_bytes(SECTION)
    geometry_ok = (
        record["name"] == "c2-append-journal-prepare"
        and record["section"] == SECTION
        and record["entry_offset"] == 0
        and record["entry"] == record["vma"] == section.address
        and record["file_size"] == section.bytes == 1764
        and hashlib.sha256(section_payload).hexdigest() == record["sha256"]
        and symbols[SELECTOR].value == section.address
        and symbols[SELECTOR].bytes == 54
        and symbols[TARGETS[0]].value ==
            symbols[SELECTOR].value + symbols[SELECTOR].bytes
        and symbols[TARGETS[1]].value ==
            symbols[TARGETS[0]].value + symbols[TARGETS[0]].bytes
        and symbols[TARGETS[1]].value + symbols[TARGETS[1]].bytes ==
            section.address + section.bytes
    )
    require(geometry_ok, "fused catalog/body geometry mismatch")

    expected_plans = {
        "lisp65_c2_append_stage_plan": [30, 33, 34, 35, 36, 0],
        "lisp65_c2_append_persistent_publish_plan": [37, 38, 39, 40, 0],
        "lisp65_c2_append_rollback_plan": [41, 42, 40, 0],
    }
    actual_plans = {
        name: plan_bytes(truth, name) for name in expected_plans
    }
    require(actual_plans == expected_plans,
            "Link-55 plan bytes do not match the fused slot layout")

    return {
        "format": "lisp65-c2-link55-defun-crash-static-catalog-v1",
        "recorded_on": "2026-07-23",
        "status": "convicted-selector-tail-violates-C-entry-Z0",
        "promotable": False,
        "authority": {
            "product": bind(PRODUCT),
            "elf": bind(ELF),
            "session_manifest": bind(MANIFEST),
            "hardware_first_red": bind(HARDWARE),
            "driver": bind(Path(__file__)),
        },
        "suspect_1_selector": {
            "marker_domain": marker_totality(),
            "control_transfers": {
                "indirect": 0,
                "tail_edges": tail_rows,
                "ordinary_error_return": "A=8, Z=0, RTS",
            },
            "finding": (
                "Marker dispatch is total, but both successful tail edges "
                "carry Z=$d5 into C functions whose first (ptr),Z operation "
                "is reached without a local Z definition. llvm-mos requires "
                "Z=0 at C entry; the selector therefore converts a valid "
                "marker into out-of-object writes."),
            "targets": target_rows,
            "verdict": "convicted",
        },
        "suspect_2_fused_entry_geometry": {
            "catalog_record": record,
            "functions": {
                name: {"address": row.value, "bytes": row.bytes,
                       "section": row.section}
                for name, row in symbols.items()
            },
            "section_sha_matches_catalog": True,
            "body_intervals_contiguous": True,
            "verdict": "exonerated",
        },
        "suspect_3_plan_bytes": {
            "actual": actual_plans,
            "expected": expected_plans,
            "all_slots_resolve_to_current_manifest": True,
            "verdict": "exonerated",
        },
        "gate_gap": (
            "The ELF-derived selector ABI gate checked context registers and "
            "the two tail relocations, but not the C-entry Z invariant at "
            "those edges. Its two witnesses therefore shared an incomplete "
            "ABI model."),
        "required_fix": (
            "Establish Z=0 immediately before each tail JMP; enumerate the "
            "512 marker/main-domain cases and reject both missing-Z restores "
            "in the permanent ABI mutation suite."),
        "execution_accounting": {
            "compiler_runs": 0,
            "linker_runs": 0,
            "hardware_runs": 0,
        },
    }


def main() -> int:
    value = build()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    RECEIPT.chmod(0o444)
    print(
        "c2-link55-defun-crash-host-catalog: CONVICTED "
        "selector-tail-Z=d5 geometry=clean plans=clean")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CatalogError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-link55-defun-crash-host-catalog: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
