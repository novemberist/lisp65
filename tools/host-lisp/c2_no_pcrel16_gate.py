#!/usr/bin/env python3
"""Reject core-derived PCRel16 instructions in an explicitly selected ELF.

Data are excluded only by ELF Object ownership or byte-matching generated
phase-02a table declarations. No historical product or core default exists.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from elf_truth import ElfTruth


def require(ok, message):
    if not ok:
        raise ValueError(message)


def bind(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def inspect(elf, core, core_sha256, phase02a, readobj, objdump):
    require(bind(core)["sha256"] == core_sha256, "core source identity mismatch")
    rtl = re.sub(r"--[^\n]*", "", core.read_text())
    match = re.search(r"constant mode_lut\s*:\s*mlut9bit\s*:=\s*\((.*?)\);", rtl, re.S)
    require(match is not None, "missing core addressing-mode authority")
    modes = re.findall(r"\bM_\w+\b", match[1])
    require(len(modes) == 512, "incomplete core addressing-mode population")
    instructions_match = re.search(
        r"constant instruction_lut\s*:\s*ilut9bit\s*:=\s*\((.*?)\);", rtl, re.S)
    require(instructions_match is not None, "missing core instruction authority")
    operations = re.findall(r"\bI_\w+\b", instructions_match[1])
    require(len(operations) == 512, "incomplete core instruction population")
    # BSR is relative in microcode despite its M_nnnn table entry. Bind its
    # opcode through instruction_lut, not a literal or the mode table alone.
    forbidden = {i for i, mode in enumerate(modes[:256])
                 if mode == "M_rrrr" or operations[i] == "I_BSR"}
    require(bool(forbidden), "empty PCRel16 opcode population")
    truth = ElfTruth.read(elf, llvm_readobj=readobj, include_section_data=True)
    sections = {s.name: s for s in truth.sections if s.bytes and
                "SHF_EXECINSTR" in s.flags and "SHF_ALLOC" in s.flags}
    require(bool(sections), "no executable sections")
    tables = []
    declarations = re.findall(r'"(\w+):\\n((?:\.short 0x[0-9a-f]+\\n)+)"', phase02a.read_text())
    require(bool(declarations), "missing generated data-owner declarations")
    for name, body in declarations:
        symbol = truth.symbol(name)
        expected = b"".join(int(v, 16).to_bytes(2, "little")
                            for v in re.findall(r"\.short 0x([0-9a-f]+)", body))
        section = truth.section(symbol.section)
        offset = symbol.value - section.address
        require(truth.section_bytes(section.name)[offset:offset+len(expected)] == expected,
                "generated table bytes differ from selected ELF: " + name)
        tables.append((section.name, symbol.value, symbol.value+len(expected), name))
    objects = [(s.section, s.value, s.value+s.bytes, s.name)
               for s in truth.symbols if s.symbol_type == "Object" and s.bytes]
    covered = {name: set() for name in sections}
    violations = []
    data_spans = []
    instructions = 0
    section_name = None
    disassembly = subprocess.check_output([str(objdump), "-d", "--disassemble-zeroes", str(elf)], text=True)
    for line in disassembly.splitlines():
        heading = re.match(r"Disassembly of section (.*):", line)
        if heading:
            section_name = heading[1]
            continue
        if section_name not in sections:
            continue
        row = re.match(r"\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )*[0-9a-f]{2})\s+(.+)", line)
        if not row:
            continue
        pc, raw, text = int(row[1], 16), bytes.fromhex(row[2]), row[3].strip()
        section = sections[section_name]
        offset = pc-section.address
        require(truth.section_bytes(section_name)[offset:offset+len(raw)] == raw,
                "disassembly bytes differ from ELF")
        owners = [name for sec, start, end, name in objects+tables
                  if sec == section_name and start <= pc and pc+len(raw) <= end]
        # objdump can decode a source-owned table across adjacent table labels.
        data_bytes = all(any(sec == section_name and start <= a < end
                            for sec, start, end, _ in objects+tables)
                         for a in range(pc, pc+len(raw)))
        covered[section_name].update(range(pc, pc+len(raw)))
        if data_bytes:
            data_spans.append({"section": section_name, "address": pc,
                               "bytes": raw.hex(), "owners": owners})
            continue
        require(len(raw) <= 4 and text.split()[0] not in ("unknown", "byte") and
                re.fullmatch(r"[a-z][a-z0-9]*", text.split()[0]) is not None,
                "unclassified executable bytes at " + section_name + ":" + hex(pc))
        instructions += 1
        if raw[0] in forbidden:
            require(len(raw) == 3, "PCRel16 instruction width mismatch")
            violations.append({"section": section_name, "address": pc, "bytes": raw.hex()})
    for name, section in sections.items():
        require(covered[name] == set(range(section.address, section.address+section.bytes)),
                "executable byte coverage incomplete: " + name)
    return {"status": "FAIL" if violations else "PASS", "elf": bind(elf),
            "core": bind(core), "generated_data_owner": bind(phase02a),
            "readobj": bind(readobj), "objdump": bind(objdump),
            "opcodes": sorted(forbidden), "executable_sections": len(sections),
            "instructions": instructions, "data_spans": data_spans,
            "violations": violations,
            "claim": "No PCRel16 in selected ELF code; not a reachability or behavior proof."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("elf", "core", "phase02a", "readobj", "objdump"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--core-sha256", required=True)
    args = parser.parse_args()
    try:
        result = inspect(args.elf, args.core, args.core_sha256, args.phase02a, args.readobj, args.objdump)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
