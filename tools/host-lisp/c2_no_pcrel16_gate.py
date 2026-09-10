#!/usr/bin/env python3
"""Reject core-derived PCRel16 instructions in an explicitly selected ELF.

Unique input-section ownership is derived through the final link map.
Executable inputs are code except for independently proven data subranges;
the phase02a table extents come from the consumed record population.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import struct
import tempfile
from elf_truth import ElfTruth


def require(ok, message):
    if not ok:
        raise ValueError(message)


def bind(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def linked_data_owners(truth, input_truth, map_text, input_path):
    """Project read-only input data into EXEC outputs, checking every byte.

    The map supplies placement, never permission to exclude bytes by itself.
    Input ELF flags/extent, relocations and final ELF bytes must all agree.
    Unsupported relocations and ambiguous/partial placements fail closed.
    """
    placements = {}
    output = None
    for line in map_text.splitlines():
        row = re.match(r'\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+(.+?)\s*$', line)
        if not row:
            continue
        start, lma, size = (int(row[i], 16) for i in (1, 2, 3))
        label = row[4]
        if label in truth.sections_by_name:
            output = truth.section(label)
            require((start, size) == (output.address, output.bytes),
                    'link-map output extent differs from ELF: ' + label)
            continue
        item = re.fullmatch(r'(.*):\(([^)]+)\)', label)
        if not item or Path(item[1]).resolve() != input_path.resolve():
            continue
        require(output is not None, 'input placement has no output owner')
        section = input_truth.section(item[2])
        require(section.name not in placements, 'duplicate input-section placement')
        require(size == section.bytes and output.address <= start and
                start + size <= output.address + output.bytes,
                'input-section extent differs from ELF: ' + section.name)
        placements[section.name] = (output.name, start, lma)
    require(bool(placements), 'selected input is absent from link map')
    owners = []
    for name, (out_name, start, lma) in placements.items():
        source = input_truth.section(name)
        destination = truth.section(out_name)
        if not source.bytes or 'SHF_ALLOC' not in source.flags or \
                'SHF_EXECINSTR' in source.flags or 'SHF_WRITE' in source.flags or \
                'SHF_EXECINSTR' not in destination.flags:
            continue
        require(source.section_type == 'SHT_PROGBITS', 'non-PROGBITS data owner')
        require(not any(s.section == out_name and s.symbol_type == 'Function' and
                        s.value < start + source.bytes and start < s.value + s.bytes
                        for s in truth.symbols), 'read-only input overlaps a function')
        expected = bytearray(input_truth.section_bytes(name))
        occupied = set()
        relocated = []
        for r in input_truth.relocations:
            if r.source_section != name:
                continue
            require(r.relocation_type == 'R_MOS_ADDR16',
                    'unsupported read-only input relocation: ' + r.relocation_type)
            require(0 <= r.offset and r.offset + 2 <= len(expected) and
                    not occupied.intersection((r.offset, r.offset + 1)),
                    'overlapping/out-of-range data relocation')
            occupied.update((r.offset, r.offset + 1))
            symbol = input_truth.symbols[r.target_symbol_index]
            require(symbol.section in placements, 'unresolved input relocation target')
            target_section, target_base, _ = placements[symbol.section]
            target = target_base + symbol.value + r.addend
            require(0 <= target <= 0xffff, 'data relocation overflow')
            # ET_EXEC r_offset is a VMA; ET_REL input offsets are relative.
            final_offset = start + r.offset
            final = [f for f in truth.relocations if f.source_section == out_name
                     and f.offset == final_offset]
            require(len(final) == 1 and final[0].relocation_type == r.relocation_type,
                    'final data relocation missing or changed')
            final_symbol = truth.symbols[final[0].target_symbol_index]
            require(final_symbol.section == target_section and
                    final_symbol.value + final[0].addend == target,
                    'final data relocation target differs')
            expected[r.offset:r.offset + 2] = target.to_bytes(2, 'little')
            relocated.append({'offset': r.offset, 'target_section': target_section,
                              'target': target, 'type': r.relocation_type})
        offset = start - destination.address
        actual = truth.section_bytes(out_name)[offset:offset + source.bytes]
        require(bytes(expected) == actual, 'relocated read-only bytes differ: ' + name)
        owners.append({'section': out_name, 'start': start, 'end': start + source.bytes,
                       'input_section': name, 'input_flags': list(source.flags),
                       'lma': lma, 'bytes': actual.hex(), 'relocations': relocated})
    return owners


def input_owners(truth, link_map, readobj):
    """Every EXEC output byte has exactly one consumed input-section owner."""
    outputs = {s.name: s for s in truth.sections if s.bytes and
               'SHF_ALLOC' in s.flags and 'SHF_EXECINSTR' in s.flags}
    rows = []; output = None
    for line in link_map.read_text().splitlines():
        m = re.match(r'\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+(.+?)\s*$', line)
        if not m:
            continue
        start, lma, size = (int(m[i], 16) for i in (1, 2, 3))
        if m[4] in truth.sections_by_name:
            output = truth.section(m[4])
            require((start, size) == (output.address, output.bytes), 'map output extent mismatch')
            continue
        item = re.fullmatch(r'(.*):\(([^)]+)\)', m[4])
        if item and size and output and output.name in outputs:
            rows.append(dict(section=output.name, start=start, end=start+size,
                             lma=lma, input_path=item[1], input_section=item[2]))
    for name, s in outputs.items():
        occupied = set()
        for r in [r for r in rows if r['section'] == name]:
            extent = set(range(r['start'], r['end']))
            require(s.address <= r['start'] < r['end'] <= s.address+s.bytes,
                    'input outside output extent: '+name)
            require(not occupied.intersection(extent), 'multiply owned executable bytes: '+name)
            occupied.update(extent)
        require(occupied == set(range(s.address, s.address+s.bytes)),
                'unowned executable bytes: '+name)
    inputs = {}
    with tempfile.TemporaryDirectory(prefix='pcrel16-inputs-') as temp:
        for identity in sorted({r['input_path'] for r in rows}):
            archive = re.fullmatch(r'(.+\.a)\(([^()]+)\)', identity)
            if archive:
                path = Path(archive[1]).resolve(); ar = readobj.parent/'llvm-ar'
                members = subprocess.check_output([str(ar), 't', str(path)], text=True).splitlines()
                require(members.count(archive[2]) == 1, 'ambiguous archive member')
                raw = subprocess.check_output([str(ar), 'p', str(path), archive[2]])
                obj = Path(temp)/(str(len(inputs))+'.o'); obj.write_bytes(raw)
                authority = dict(archive=bind(path), member=archive[2], member_sha256=bind(obj)['sha256'])
            else:
                obj = Path(identity).resolve(); authority = dict(object=bind(obj))
            inp = ElfTruth.read(obj, llvm_readobj=readobj, include_section_data=True)
            inputs[identity] = inp
            for r in [r for r in rows if r['input_path'] == identity]:
                s = inp.section(r['input_section'])
                require(s.bytes == r['end']-r['start'] and s.section_type == 'SHT_PROGBITS',
                        'input ELF extent/type mismatch: '+identity+':'+s.name)
                r.update(input_flags=list(s.flags), authority=authority,
                         kind='code' if 'SHF_EXECINSTR' in s.flags else 'data')
    return rows, inputs


def record_subranges(truth, owners, inputs, phase02a, record_oracles):
    """dee26544: start from input symbol; extent and bytes from record population."""
    from runtime_overlay_bank import crc16_ccitt_false
    require(record_oracles is not None and set(record_oracles) == {'shelf', 'c2d'},
            'independent record oracles required')
    result = []
    for role in ('shelf', 'c2d'):
        path = Path(record_oracles[role]); raw = path.read_bytes()
        require(len(raw) >= 32, 'truncated record authority')
        count = raw[7] if role == 'shelf' else struct.unpack_from('<H', raw, 12)[0]
        offset = 32 if role == 'shelf' else struct.unpack_from('<H', raw, 28)[0]
        require(count > 0 and offset+count*32 <= len(raw), 'record population out of bounds')
        expected = b''.join(struct.pack('<H', crc16_ccitt_false(raw[offset+i*32:offset+(i+1)*32]))
                            for i in range(count))
        name = 'c2_phase02a_'+role+'_crc16'
        decl = re.search(re.escape(name)+r':\\n((?:\.short 0x[0-9a-f]+\\n)+)', phase02a.read_text())
        require(decl is not None, 'missing declared table: '+name)
        declared = b''.join(struct.pack('<H', int(x, 16)) for x in re.findall(r'0x([0-9a-f]+)', decl[1]))
        require(declared == expected, 'declared CRC table differs from records: '+name)
        final = truth.symbol(name)
        matches = []
        for owner in owners:
            inp = inputs[owner['input_path']]
            for symbol in inp.symbols:
                if symbol.name == name and symbol.section == owner['input_section']:
                    matches.append((owner, inp, symbol))
        require(len(matches) == 1, 'table input symbol ownership ambiguous: '+name)
        owner, inp, symbol = matches[0]
        require(owner['kind'] == 'code', 'table subrange must refine code owner')
        start = owner['start']+symbol.value; end = start+len(expected)
        require(owner['start'] <= start < end <= owner['end'], 'table outside input owner')
        require(final.section == owner['section'] and final.value == start, 'table input/final location drift')
        if symbol.bytes:
            require(symbol.symbol_type == 'Object' and symbol.bytes == len(expected), 'sized table extent mismatch')
        else:
            require(symbol.symbol_type == 'None', 'unsupported unsized table symbol')
        sec = truth.section(final.section)
        require(inp.section_bytes(symbol.section)[symbol.value:symbol.value+len(expected)] == expected,
                'input table bytes differ from record oracle')
        require(truth.section_bytes(sec.name)[start-sec.address:end-sec.address] == expected,
                'final table bytes differ from record oracle')
        result.append(dict(section=sec.name, start=start, end=end, name=name, owner=owner,
                           input_symbol_type=symbol.symbol_type, input_symbol_size=symbol.bytes,
                           derivation='record_count * CRC16 width', record_count=count,
                           crc_width=struct.calcsize('<H'), expected_bytes=expected.hex(),
                           oracle=bind(path), declaration=bind(phase02a)))
    require(result[0]['record_count'] == result[1]['record_count'], 'record populations disagree')
    return result


def inspect(elf, core, core_sha256, phase02a, readobj, objdump, *, lto=None, link_map=None,
            record_oracles=None, data_subranges=None):
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
    require(lto is not None and link_map is not None, 'consumed inputs and final map required')
    owners, inputs = input_owners(truth, link_map, readobj)
    linked = linked_data_owners(
        truth, ElfTruth.read(lto, llvm_readobj=readobj, include_section_data=True),
        link_map.read_text(), lto)
    proven = record_subranges(truth, owners, inputs, phase02a, record_oracles)
    if data_subranges is not None:
        require(data_subranges == proven, 'data subrange extent/oracle differs from independent derivation')
    data = {name: set() for name in sections}
    for r in owners:
        if r['kind'] == 'data':
            data[r['section']].update(range(r['start'], r['end']))
    for r in proven:
        extent = set(range(r['start'], r['end']))
        require(not extent.intersection(data[r['section']]), 'overlapping data refinements')
        data[r['section']].update(extent)
    covered = {name: set(values) for name, values in data.items()}
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
        if pc in data[section_name]:
            end = pc
            while end < pc+len(raw) and end in data[section_name]:
                end += 1
            data_spans.append({"section": section_name, "address": pc,
                               "bytes": raw[:end-pc].hex(),
                               "discarded_cross_boundary_decode": raw[end-pc:].hex()})
            continue
        selected = [o for o in owners if o['section'] == section_name and o['kind'] == 'code'
                    and o['start'] <= pc and pc+len(raw) <= o['end']]
        require(len(selected) == 1 and not data[section_name].intersection(range(pc, pc+len(raw))),
                'code decode crosses input/data boundary: '+section_name+':'+hex(pc))
        covered[section_name].update(range(pc, pc+len(raw)))
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
    result = {"status": "FAIL" if violations else "PASS", "elf": bind(elf),
            "core": bind(core), "generated_data_owner": bind(phase02a),
            "readobj": bind(readobj), "objdump": bind(objdump),
            "opcodes": sorted(forbidden), "executable_sections": len(sections),
            "instructions": instructions, "data_spans": data_spans,
            "input_owners": owners, "data_subranges": proven,
            "violations": violations,
            "claim": "No PCRel16 in selected ELF code; not a reachability or behavior proof."}
    if lto is not None:
        result['linked_data_ownership'] = {'input_elf': bind(lto), 'link_map': bind(link_map),
                                         'owners': linked}
    return result


def boundary_selftest(elf, core, core_sha256, phase02a, readobj, objdump, *, lto, link_map, record_oracles):
    """Executed copies of the selected ELF; no changes to consumed artifacts."""
    from copy import deepcopy
    kwargs = dict(lto=lto, link_map=link_map, record_oracles=record_oracles)
    def check(path=elf, **extra):
        return inspect(path, core, core_sha256, phase02a, readobj, objdump, **(kwargs|extra))
    frozen = [bind(p) for p in (elf, lto, link_map, phase02a, *record_oracles.values())]
    baseline = check(); require(baseline['status'] == 'PASS', 'selftest baseline fails')
    mutations = []
    def rejected(name, call, address=None):
        try:
            value = call()
        except ValueError as exc:
            require(address is None, 'code mutation rejected before instruction scan: '+str(exc))
            mutations.append(dict(name=name, result='REJECTED', reason=str(exc)))
        else:
            require(value['status'] == 'FAIL' and (address is None or
                    any(v['address'] == address for v in value['violations'])), name+' survived')
            mutations.append(dict(name=name, result='REJECTED', violations=value['violations']))
    for index in range(len(baseline['data_subranges'])):
        for boundary in ('start', 'end'):
            for delta in (-1, 1):
                trial = deepcopy(baseline['data_subranges']); trial[index][boundary] += delta
                rejected(f'table-{index}-{boundary}-{delta:+d}', lambda trial=trial: check(data_subranges=trial))
        trial = deepcopy(baseline['data_subranges']); trial[index].pop('oracle')
        rejected(f'table-{index}-oracle-omitted', lambda trial=trial: check(data_subranges=trial))
    rejected('record-oracle-absent', lambda: check(record_oracles=None))
    truth = ElfTruth.read(elf, llvm_readobj=readobj, include_section_data=True)
    with tempfile.TemporaryDirectory(prefix='pcrel16-boundary-controls-') as temp:
        out = Path(temp)
        def mutate_code(name, section, address):
            raw = bytearray(elf.read_bytes())
            shoff = struct.unpack_from('<I', raw, 32)[0]; entsize = struct.unpack_from('<H', raw, 46)[0]
            offset = struct.unpack_from('<I', raw, shoff+section.index*entsize+16)[0]+address-section.address
            raw[offset:offset+3] = bytes((baseline['opcodes'][0], 0, 0))
            path = out/(name+'.elf'); path.write_bytes(raw)
            rejected(name, lambda: check(path), address)
        entry = truth.symbol('c2_stream_phase_02a')
        mutate_code('real-long-at-function-entry', truth.section(entry.section), entry.value)
        left = truth.symbol('c2_mapped_far_vm_code_load_converged')
        right = truth.symbol('c2_mapped_far_physical_read_converged')
        address = left.value+left.bytes
        require(left.section == right.section and address+3 <= right.value,
                'unnamed helper interval not derivable')
        mutate_code('real-long-in-unnamed-assembler-helper', truth.section(left.section), address)
        owner = next(o for o in baseline['input_owners'] if o['section'] == left.section and
                     o['start'] <= address < o['end'])
        matches = [line for line in link_map.read_text().splitlines() if
                   owner['input_path']+':('+owner['input_section']+')' in line]
        require(len(matches) == 1, 'input placement mutation ambiguous')
        row = matches[0]
        for name, replacement in [('input-section-omitted', ''), ('input-section-duplicated', row+'\n'+row+'\n')]:
            path = out/(name+'.map'); path.write_text(link_map.read_text().replace(row+'\n', replacement))
            rejected(name, lambda path=path: check(link_map=path))
    require(frozen == [bind(p) for p in (elf, lto, link_map, phase02a, *record_oracles.values())],
            'selftest changed selected inputs')
    return mutations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("elf", "core", "phase02a", "readobj", "objdump"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--core-sha256", required=True)
    parser.add_argument("--lto", type=Path)
    parser.add_argument("--link-map", type=Path)
    parser.add_argument("--shelf", type=Path, required=True)
    parser.add_argument("--c2d", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = inspect(args.elf, args.core, args.core_sha256, args.phase02a, args.readobj, args.objdump,
                         lto=args.lto, link_map=args.link_map,
                         record_oracles=dict(shelf=args.shelf, c2d=args.c2d))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
