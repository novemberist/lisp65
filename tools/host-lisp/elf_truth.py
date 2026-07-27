#!/usr/bin/env python3
"""Shared structured ELF truth for Lisp65 host gates.

The only tool input is llvm-readobj JSON.  Section identity is never inferred
from a VMA, and symbol/relocation provenance is retained without parsing
human-oriented columns from llvm-nm or llvm-objdump.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable


class ElfTruthError(RuntimeError):
    pass


@dataclass(frozen=True)
class Section:
    index: int
    name: str
    address: int
    bytes: int
    section_type: str
    flags: tuple[str, ...]
    info: int


@dataclass(frozen=True)
class Symbol:
    index: int
    name: str
    value: int
    bytes: int
    binding: str
    symbol_type: str
    section: str
    section_index: int


@dataclass(frozen=True)
class Relocation:
    relocation_section: str
    source_section: str
    source_section_index: int
    offset: int
    relocation_type: str
    target_symbol_index: int
    target: str
    addend: int


@dataclass(frozen=True)
class ContractInterval:
    name: str
    section: str
    start: int
    bytes: int
    kind: str = "contract"

    @property
    def end_exclusive(self) -> int:
        return self.start + self.bytes


def _name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("Name", ""))
    return str(value)


class ElfTruth:
    def __init__(self, *, sections: list[Section], symbols: list[Symbol],
                 relocations: list[Relocation],
                 section_data: dict[int, bytes] | None = None,
                 absolute_markers: dict[str, int] | None = None,
                 contract_intervals: Iterable[ContractInterval] = ()) -> None:
        self.sections = sections
        self.symbols = symbols
        self.relocations = relocations
        self._section_data = dict(section_data or {})
        self.absolute_markers = dict(absolute_markers or {})
        self.contract_intervals = tuple(contract_intervals)
        self.sections_by_index = {row.index: row for row in sections}
        if len(self.sections_by_index) != len(sections):
            raise ElfTruthError("duplicate ELF section index")
        self.sections_by_name: dict[str, list[Section]] = {}
        for row in sections:
            self.sections_by_name.setdefault(row.name, []).append(row)
        self.symbols_by_name: dict[str, list[Symbol]] = {}
        for row in symbols:
            self.symbols_by_name.setdefault(row.name, []).append(row)
        for name, expected in self.absolute_markers.items():
            matches = self.symbols_by_name.get(name, [])
            if len(matches) != 1 or matches[0].section != "Absolute" \
                    or matches[0].value != expected:
                raise ElfTruthError(
                    f"registered Absolute marker drift: {name} expected "
                    f"0x{expected:x}, found {matches}")
        for row in self.contract_intervals:
            if row.bytes <= 0 or row.section not in self.sections_by_name:
                raise ElfTruthError(f"invalid contract interval: {row}")

    @classmethod
    def read(cls, elf: Path, *, llvm_readobj: Path,
             absolute_markers: dict[str, int] | None = None,
             contract_intervals: Iterable[ContractInterval] = (),
             include_section_data: bool = False) -> "ElfTruth":
        command = [
            str(llvm_readobj), "--elf-output-style=JSON", "--sections",
            "--symbols", "--relocations", str(elf),
        ]
        if include_section_data:
            command.insert(-1, "--section-data")
        completed = subprocess.run(
            command, check=True, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        try:
            document = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise ElfTruthError("llvm-readobj did not emit valid JSON") from error
        return cls.from_document(
            document, absolute_markers=absolute_markers,
            contract_intervals=contract_intervals)

    @classmethod
    def from_document(cls, document: Any, *,
                      absolute_markers: dict[str, int] | None = None,
                      contract_intervals: Iterable[ContractInterval] = (
                      )) -> "ElfTruth":
        if not isinstance(document, list) or len(document) != 1 \
                or not isinstance(document[0], dict):
            raise ElfTruthError("expected exactly one llvm-readobj JSON file")
        root = document[0]
        sections: list[Section] = []
        section_data: dict[int, bytes] = {}
        for wrapper in root.get("Sections", []):
            raw = wrapper["Section"]
            flags = tuple(_name(item) for item in
                          raw.get("Flags", {}).get("Flags", []))
            section_index = int(raw["Index"])
            sections.append(Section(
                index=section_index, name=_name(raw["Name"]),
                address=int(raw["Address"]), bytes=int(raw["Size"]),
                section_type=_name(raw["Type"]), flags=flags,
                info=int(raw.get("Info", 0))))
            if "SectionData" in raw:
                section_data[section_index] = bytes(
                    raw["SectionData"].get("Bytes", []))
        by_index = {row.index: row for row in sections}
        symbols: list[Symbol] = []
        for index, wrapper in enumerate(root.get("Symbols", [])):
            raw = wrapper["Symbol"]
            symbols.append(Symbol(
                index=index, name=_name(raw["Name"]),
                value=int(raw["Value"]), bytes=int(raw["Size"]),
                binding=_name(raw["Binding"]),
                symbol_type=_name(raw["Type"]),
                section=_name(raw["Section"]),
                section_index=int(raw["Section"].get("Value", 0))))
        relocations: list[Relocation] = []
        for group in root.get("Relocations", []):
            relocation_section_index = int(group["SectionIndex"])
            relocation_section = by_index.get(relocation_section_index)
            if relocation_section is None:
                raise ElfTruthError(
                    f"relocation section index absent: {relocation_section_index}")
            source = by_index.get(relocation_section.info)
            if source is None:
                raise ElfTruthError(
                    f"relocation source section index absent: "
                    f"{relocation_section.info}")
            for wrapper in group.get("Relocs", []):
                raw = wrapper["Relocation"]
                target_index = int(raw["Symbol"]["Value"])
                if not 0 <= target_index < len(symbols):
                    raise ElfTruthError(
                        f"relocation symbol index absent: {target_index}")
                target = symbols[target_index]
                if target.name != _name(raw["Symbol"]):
                    raise ElfTruthError(
                        f"relocation symbol-name/index mismatch: "
                        f"{_name(raw['Symbol'])}/{target.name}")
                relocations.append(Relocation(
                    relocation_section=relocation_section.name,
                    source_section=source.name,
                    source_section_index=source.index,
                    offset=int(raw["Offset"]),
                    relocation_type=_name(raw["Type"]),
                    target_symbol_index=target_index,
                    target=target.name, addend=int(raw.get("Addend", 0))))
        return cls(
            sections=sections, symbols=symbols, relocations=relocations,
            section_data=section_data,
            absolute_markers=absolute_markers,
            contract_intervals=contract_intervals)

    def section(self, name: str) -> Section:
        matches = self.sections_by_name.get(name, [])
        if len(matches) != 1:
            raise ElfTruthError(
                f"section identity is not unique: {name} ({len(matches)})")
        return matches[0]

    def section_bytes(self, name: str) -> bytes:
        row = self.section(name)
        data = self._section_data.get(row.index, b"")
        if row.bytes and len(data) != row.bytes:
            raise ElfTruthError(
                f"section data was not loaded or is incomplete: {name}")
        return data

    def symbol(self, name: str) -> Symbol:
        matches = self.symbols_by_name.get(name, [])
        if len(matches) != 1:
            raise ElfTruthError(
                f"symbol identity is not unique: {name} ({len(matches)})")
        return matches[0]

    def sections_at_vma(self, address: int) -> list[Section]:
        """Return all owners; overlapping VMAs are expected and never merged."""
        return [row for row in self.sections
                if row.bytes > 0 and row.address <= address <
                row.address + row.bytes]

    def relocation_target_identity(self, row: Relocation) -> dict[str, Any]:
        symbol = self.symbols[row.target_symbol_index]
        if symbol.section == "Absolute":
            registered = self.absolute_markers.get(symbol.name)
            kind = ("registered-absolute" if registered == symbol.value
                    else "unregistered-absolute")
        elif symbol.section == "Undefined":
            kind = "undefined"
        else:
            kind = "section-symbol"
        return {
            "kind": kind,
            "section": symbol.section,
            "symbol": symbol.name,
            "symbol_index": symbol.index,
            "symbol_type": symbol.symbol_type,
            "symbol_size": symbol.bytes,
            "symbol_value": symbol.value,
            "addend": row.addend,
            "resolved_value": symbol.value + row.addend,
        }

    def sized_intervals(self, *, section: str | None = None,
                        symbol_types: tuple[str, ...] = (
                            "Function",)) -> list[ContractInterval]:
        return [ContractInterval(
            name=row.name, section=row.section, start=row.value,
            bytes=row.bytes, kind="elf-symbol")
            for row in self.symbols
            if row.bytes > 0 and row.symbol_type in symbol_types
            and row.section not in ("Absolute", "Undefined")
            and (section is None or row.section == section)]

    def resolve_interval(self, *, section: str, address: int) -> dict[str, Any]:
        candidates = [row for row in (
            self.sized_intervals(section=section) +
            [item for item in self.contract_intervals
             if item.section == section])
            if row.start <= address < row.end_exclusive]
        if len(candidates) != 1:
            raise ElfTruthError(
                f"interval provenance must resolve exactly once: "
                f"section={section} address=0x{address:x} candidates="
                f"{[asdict(row) for row in candidates]}")
        return asdict(candidates[0]) | {
            "end_exclusive": candidates[0].end_exclusive}

    def resolve_split_address_binding(
            self, *, owner: str, target: str, addend: int = 0,
            high_type: str = "R_MOS_ADDR16_HI",
            low_type: str = "R_MOS_ADDR16_LO") -> dict[str, Any]:
        """Resolve one linker-owned split address inside a sized symbol.

        Rendered disassembly exposes only the final immediate bytes and is not
        provenance.  The structured relocations are the authority: exactly one
        high and one low relocation must originate inside the same sized owner
        interval and target the same unique ELF symbol/addend.
        """
        owner_symbol = self.symbol(owner)
        target_symbol = self.symbol(target)
        if owner_symbol.bytes <= 0 \
                or owner_symbol.section in ("Absolute", "Undefined"):
            raise ElfTruthError(
                f"split-address owner is not a sized section symbol: {owner}")
        begin = owner_symbol.value
        end = begin + owner_symbol.bytes
        rows = [row for row in self.relocations
                if row.source_section_index == owner_symbol.section_index
                and begin <= row.offset < end
                and row.target_symbol_index == target_symbol.index
                and row.addend == addend
                and row.relocation_type in (high_type, low_type)]
        high = [row for row in rows if row.relocation_type == high_type]
        low = [row for row in rows if row.relocation_type == low_type]
        if len(high) != 1 or len(low) != 1 or len(rows) != 2:
            raise ElfTruthError(
                f"split-address binding must have exactly one HI and one LO: "
                f"owner={owner} target={target} addend={addend} "
                f"hi={len(high)} lo={len(low)} total={len(rows)}")
        resolved = target_symbol.value + addend
        return {
            "owner": owner,
            "owner_section": owner_symbol.section,
            "owner_start": owner_symbol.value,
            "owner_bytes": owner_symbol.bytes,
            "target": target,
            "target_section": target_symbol.section,
            "target_value": target_symbol.value,
            "addend": addend,
            "resolved_value": resolved,
            "high": {
                "type": high_type, "offset": high[0].offset,
                "value": (resolved >> 8) & 0xff},
            "low": {
                "type": low_type, "offset": low[0].offset,
                "value": resolved & 0xff},
        }

    def section_symbol_sets(self) -> dict[str, set[str]]:
        return {name: {row.section for row in rows}
                for name, rows in self.symbols_by_name.items()}

    def symbol_values(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for name, rows in self.symbols_by_name.items():
            values = {row.value for row in rows}
            if len(values) == 1:
                result[name] = next(iter(values))
        return result


def selftest() -> dict[str, str]:
    def named(name: str, value: int = 0) -> dict[str, Any]:
        return {"Name": name, "Value": value}

    sections = [
        {"Section": {"Index": 0, "Name": named(""),
         "Type": named("SHT_NULL"), "Flags": {"Flags": []},
         "Address": 0, "Size": 0, "Info": 0}},
        {"Section": {"Index": 1, "Name": named(".text"),
         "Type": named("SHT_PROGBITS"), "Flags": {"Flags": []},
         "Address": 0x2000, "Size": 0x100, "Info": 0}},
        {"Section": {"Index": 2, "Name": named(".overlay.a"),
         "Type": named("SHT_PROGBITS"), "Flags": {"Flags": []},
         "Address": 0xC356, "Size": 0x100, "Info": 0}},
        {"Section": {"Index": 3, "Name": named(".overlay.b"),
         "Type": named("SHT_PROGBITS"), "Flags": {"Flags": []},
         "Address": 0xC356, "Size": 0x80, "Info": 0}},
        {"Section": {"Index": 4, "Name": named(".rela.text"),
         "Type": named("SHT_RELA"), "Flags": {"Flags": []},
         "Address": 0, "Size": 12, "Info": 1}},
        {"Section": {"Index": 5, "Name": named(".data"),
         "Type": named("SHT_PROGBITS"), "Flags": {"Flags": []},
         "Address": 0xB900, "Size": 0x100, "Info": 0}},
    ]

    def symbol(name: str, value: int, size: int, kind: str,
               section: str, section_index: int) -> dict[str, Any]:
        return {"Symbol": {
            "Name": named(name), "Value": value, "Size": size,
            "Binding": named("Global"), "Type": named(kind),
            "Section": named(section, section_index)}}

    symbols = [
        symbol("", 0, 0, "None", "Undefined", 0),
        symbol("notype_a", 0xC356, 0, "None", ".overlay.a", 2),
        symbol("runtime_vma", 0xC356, 0, "None", "Absolute", 0xFFF1),
        symbol("func_a", 0xC360, 16, "Function", ".overlay.a", 2),
        symbol("unknown_abs", 0xC356, 0, "None", "Absolute", 0xFFF1),
        symbol("dma_job", 0xB976, 40, "Object", ".data", 5),
        symbol("text_func", 0x2000, 16, "Function", ".text", 1),
    ]
    relocations = [{"SectionIndex": 4, "Relocs": [
        {"Relocation": {"Offset": 0x2002,
         "Type": named("R_MOS_ADDR16"), "Symbol": named("notype_a", 1),
         "Addend": 0}},
        {"Relocation": {"Offset": 0x2006,
         "Type": named("R_MOS_ADDR16"), "Symbol": named("runtime_vma", 2),
         "Addend": 0}},
        {"Relocation": {"Offset": 0x200A,
         "Type": named("R_MOS_ADDR16_HI"), "Symbol": named("dma_job", 5),
         "Addend": 0}},
        {"Relocation": {"Offset": 0x200E,
         "Type": named("R_MOS_ADDR16_LO"), "Symbol": named("dma_job", 5),
         "Addend": 0}},
    ]}]
    truth = ElfTruth.from_document([{
        "Sections": sections, "Symbols": symbols,
        "Relocations": relocations}],
        absolute_markers={"runtime_vma": 0xC356},
        contract_intervals=[ContractInterval(
            "facade-vector", ".overlay.a", 0xC370, 3)])
    if len(truth.sections_at_vma(0xC356)) != 2:
        raise ElfTruthError("overlay VMAs were collapsed")
    if truth.symbol("notype_a").section != ".overlay.a":
        raise ElfTruthError("NOTYPE st_shndx provenance lost")
    if truth.relocation_target_identity(
            truth.relocations[1])["kind"] != "registered-absolute":
        raise ElfTruthError("registered Absolute marker rejected")
    if truth.relocation_target_identity(Relocation(
            ".rela.text", ".text", 1, 0x2008, "R_MOS_ADDR16", 4,
            "unknown_abs", 0))["kind"] != "unregistered-absolute":
        raise ElfTruthError("unknown Absolute marker accepted")
    if truth.resolve_interval(section=".overlay.a", address=0xC362)[
            "name"] != "func_a":
        raise ElfTruthError("sized function interval did not resolve")
    if truth.resolve_interval(section=".overlay.a", address=0xC371)[
            "name"] != "facade-vector":
        raise ElfTruthError("contract interval did not resolve")
    split = truth.resolve_split_address_binding(
        owner="text_func", target="dma_job")
    if split["resolved_value"] != 0xB976 \
            or split["high"]["value"] != 0xB9 \
            or split["low"]["value"] != 0x76:
        raise ElfTruthError("split-address relocation binding drift")
    try:
        truth.resolve_split_address_binding(owner="text_func", target="notype_a")
    except ElfTruthError:
        pass
    else:
        raise ElfTruthError("missing split-address pair was accepted")
    return {
        "structured-json": "passed",
        "section-symbol-addend": "passed",
        "overlay-awareness": "passed",
        "notype-st-shndx": "passed",
        "registered-absolute": "passed",
        "contract-interval": "passed",
        "unique-sized-interval": "passed",
        "split-address-hi-lo": "passed",
        "split-address-missing-pair": "rejected",
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2, sort_keys=True))
