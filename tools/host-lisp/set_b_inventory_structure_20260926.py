"""Seal complete Set B ELF serialization after allocated/instruction closure."""
import argparse
import collections
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import struct
import sys
sys.dont_write_bytecode = True
import set_b_producer as P
from elf_truth import ElfTruth
from set_b_instruction_inventory_20260926 import PATHS, AUTHORED

ROOT = P.ROOT


def main(out, allocated, instructions):
    out.mkdir(parents=True, exist_ok=False)
    write = lambda name, value: P.write(out/name, value)
    c = P.load(allocated/'allocated-census.json')
    assert c['status'] == 'PASS ALLOCATED CONTENT' and not c['counts'].get('UNCLASSIFIED', 0)
    assert c['driver'] == P.bind(ROOT/c['driver']['path'])
    raw = [p.read_bytes() for p in PATHS]
    ts = [ElfTruth.read(p, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj', include_section_data=True) for p in PATHS]
    assert c['elfs'] == [P.bind(p) for p in PATHS]
    fs = P.load(instructions/'function-instructions.json')
    old_to_new = {v['before']['name']: v['after']['name'] for v in fs}
    new_to_old = {v:k for k,v in old_to_new.items()}
    by_name = [{s.name:s for s in t.symbols} for t in ts]
    new_sections = {t['section'] for t in P.load(P.INPUTS)['tenants']}
    new_functions = {s['name'] for s in P.load(instructions/'census.json')['new']}
    headers = []; labels = []; serialization = []; failures = []
    for k, (data, t) in enumerate(zip(raw, ts)):
        phoff, shoff = struct.unpack_from('<II', data, 28)
        eh, phsize, phnum, shsize, shnum, shstridx = struct.unpack_from('<6H', data, 40)
        assert (eh, phsize, shsize) == (52, 32, 40) and shnum == len(t.sections)
        sh = [struct.unpack_from('<10I', data, shoff+i*shsize) for i in range(shnum)]
        ph = [struct.unpack_from('<8I', data, phoff+i*phsize) for i in range(phnum)]
        headers.append(dict(elf_header=data[:eh].hex(), program_headers=ph, section_headers=sh))
        spans = [(0, eh, 'ELF header'), (phoff, phoff+phsize*phnum, 'program headers'), (shoff, shoff+shsize*shnum, 'section headers')]
        for sec, h in zip(t.sections, sh):
            assert sec.index == t.sections.index(sec) and (h[3], h[5]) == (sec.address, sec.bytes)
            if sec.section_type != 'SHT_NOBITS' and h[5]:
                assert data[h[4]:h[4]+h[5]] == t.section_bytes(sec.name)
                spans.append((h[4], h[4]+h[5], sec.name))
                if 'SHF_ALLOC' in sec.flags:
                    matches = [p for p in ph if p[0] == 1 and p[1] <= h[4] and h[4]+h[5] <= p[1]+p[4]
                               and p[2]+h[4]-p[1] == sec.address]
                    assert matches, ('allocated section missing from program headers', sec.name)
        lab = [None]*len(data)
        for start, end, name in spans:
            assert 0 <= start <= end <= len(data)
            for i in range(start, end): assert lab[i] is None; lab[i] = name
        for i, v in enumerate(lab):
            if v is None: assert data[i] == 0; lab[i] = 'zero serialization padding'
        labels.append(lab)
        # Decode symtab and compare every record to structured readobj truth.
        symhdr = sh[t.section('.symtab').index]; strings = sh[symhdr[6]]
        names = data[strings[4]:strings[4]+strings[5]]; used = {0}; records = []
        assert symhdr[9] == 16 and symhdr[5]//16 == len(t.symbols)
        for i, sym in enumerate(t.symbols):
            name, value, size, info, other, idx = struct.unpack_from('<IIIBBH', data, symhdr[4]+i*16)
            end = names.index(0, name); used.update(range(name, end+1))
            decoded_name = names[name:end].decode()
            if info & 15 == 3 and not decoded_name:
                decoded_name = t.sections_by_index[idx].name
            assert (decoded_name, value, size) == (sym.name, sym.value, sym.bytes)
            records.append(dict(name=sym.name, info=info, other=other, section_index=idx))
        assert len(used) == len(names)
        nameshdr = sh[shstridx]; names = data[nameshdr[4]:nameshdr[4]+nameshdr[5]]; used = {0}
        for h, sec in zip(sh, t.sections):
            end = names.index(0, h[0]); used.update(range(h[0], end+1)); assert names[h[0]:end].decode() == sec.name
        assert len(used) == len(names)
        serialization.append(records)
    # ELF architecture/ABI, entry and machine flags stay identical; counts and
    # table offsets are derived from the parsed file coverage above.
    assert raw[0][:28] == raw[1][:28] and raw[0][36:40] == raw[1][36:40]
    write('headers.json', headers)
    write('serialization.json', serialization)
    symbol_rows = []
    for s in ts[1].symbols:
        prior = new_to_old.get(s.name, s.name); old = by_name[0].get(prior)
        family = None
        if old:
            oldrec = serialization[0][old.index]; newrec = serialization[1][s.index]
            assert (old.binding, old.symbol_type, oldrec['info'], oldrec['other']) == (s.binding, s.symbol_type, newrec['info'], newrec['other'])
            if s.symbol_type == 'Function' and s.bytes:
                family = 'authorized body' if old.name in AUTHORED else 'instruction-proved function or merged clone alias'
            elif s.bytes:
                assert s.bytes == old.bytes
                family = 'allocated owner census; data or uninitialized storage'
            elif s.symbol_type == 'Section':
                assert s.value == ts[1].section(s.section).address and old.value == ts[0].section(old.section).address
                family = 'section base derived from linked section table'
            elif old.value == s.value and old.section == s.section:
                family = 'unchanged symbol value'
            elif s.name == '__lisp65_workbench_overlay_len':
                assert all(t.symbol(s.name).value == t.section('.lisp65_workbench_overlay').bytes for t in ts)
                family = 'derived workbench section length'
            elif s.name == '__lisp65_resident_island_seed_lma':
                for t, h, v in zip(ts, headers, (old, s)):
                    sec = t.section('.lisp65_rt_intern_service'); hdr = h['section_headers'][sec.index]
                    ph = [p for p in h['program_headers'] if p[0] == 1 and p[1] <= hdr[4] and hdr[4]+sec.bytes <= p[1]+p[4]]
                    assert len(ph) == 1
                    lma = ph[0][3]+hdr[4]-ph[0][1]
                    assert v.value == (lma+sec.bytes+255)//256*256
                family = 'derived aligned island load address'
            elif s.section in ts[1].sections_by_name and old.section == s.section:
                os, ns = [t.section(s.section) for t in ts]
                if old.value == os.address+os.bytes and s.value == ns.address+ns.bytes:
                    family = 'section end'
                elif old.value-os.address == s.value-ns.address:
                    family = 'same section-relative label'
                elif s.symbol_type == 'Function' and not s.bytes:
                    # Exported entry alias of a sized, already inventoried body.
                    pair = [v for v in fs if v['before']['section'] == old.section and v['after']['section'] == s.section and v['before']['value'] == old.value and v['after']['value'] == s.value]
                    if pair: family = 'proved function entry alias'
            if family is None: failures.append(['unclassified symbol drift', asdict(old), asdict(s)])
        else:
            if s.name in new_functions: family = 'authorized retirement function'
            elif s.section in new_sections and s.symbol_type == 'Function' and s.bytes == 0 and any(f.name in new_functions and f.section == s.section and f.value == s.value for f in ts[1].symbols): family = 'new retirement entry alias'
            elif s.name in ('c2r_gc_failed', 'c2r_boot_count') and s.bytes == 1: family = 'authorized state latch'
            elif s.section in new_sections and s.value in (ts[1].section(s.section).address, ts[1].section(s.section).address+ts[1].section(s.section).bytes): family = 'new retirement section boundary'
            elif (s.name, s.value) in (('__set_b_journal_start', 0x5de20), ('__set_b_journal_end', 0x5de68)): family = 'bound journal boundary'
            else: failures.append(['unclassified new symbol', asdict(s)])
        symbol_rows.append(dict(before=asdict(old) if old else None, after=asdict(s), family=family))
    for s in ts[0].symbols:
        assert old_to_new.get(s.name, s.name) in by_name[1], ('removed symbol', s.name)
    write('symbols.json', dict(rows=symbol_rows, failures=failures))
    # Partition metadata holds the memcpy function address. ADDR_ASCIZ is
    # separately the BASIC SYS decimal address; both encodings are checked.
    for k, t in enumerate(ts):
        part = t.section_bytes('.llvm_sympart'); assert part[:-4] == b'contingent\0'
        assert int.from_bytes(part[-4:], 'little') == t.symbol('memcpy').value
        rel = [r for r in t.relocations if r.relocation_type == 'R_MOS_ADDR_ASCIZ']
        assert len(rel) == 1 and rel[0].source_section == '.basic_header' and rel[0].target == '_start' and rel[0].addend == 0
        sec = t.section('.basic_header'); at = rel[0].offset-sec.address
        basic = t.section_bytes(sec.name); end = basic.index(0, at)
        assert basic[at:end] == str(t.symbol('_start').value).encode()
    assert old_to_new['memcpy'] == 'memcpy'
    sections = []
    for name in dict.fromkeys(s.name for t in ts for s in t.sections):
        a, b = [t.section(name) if name in t.sections_by_name else None for t in ts]
        if a and b:
            assert (a.section_type, a.flags) == (b.section_type, b.flags)
        else:
            assert b and (name in new_sections or name.removeprefix('.rela') in new_sections)
        sec = b or a
        if sec.section_type == 'SHT_NOBITS': family = 'uninitialized storage; linked geometry and named owner census'
        elif 'SHF_ALLOC' in sec.flags: family = 'allocated content proof'
        elif sec.section_type == 'SHT_RELA': family = 'fully encoded relocation records from instruction/data owners'
        elif sec.section_type in ('SHT_SYMTAB', 'SHT_STRTAB', 'SHT_NULL'): family = 'parsed symbol/name serialization'
        elif name == '.llvm_sympart': family = 'proved partition function address'
        elif name in ('.comment', '.lisp65_error_callsites') and a and b and ts[0].section_bytes(name) == ts[1].section_bytes(name): family = 'byte-identical compiler provenance or error-callsite metadata'
        else: failures.append(['unclassified section', name]); family = 'UNCLASSIFIED'
        sections.append(dict(before=asdict(a) if a else None, after=asdict(b) if b else None, family=family))
    write('sections.json', sections)
    ledger = []; run = None; different = 0
    for i in range(max(map(len, raw))):
        x = raw[0][i] if i < len(raw[0]) else None; y = raw[1][i] if i < len(raw[1]) else None
        if x == y: run = None; continue
        different += 1; owner = [labels[k][i] if i < len(labels[k]) else 'EOF' for k in (0, 1)]
        if run and run['offset']+run['length'] == i and run['owners'] == owner:
            run['length'] += 1; run['before'] += f'{x:02x}' if x is not None else ''; run['after'] += f'{y:02x}' if y is not None else ''
        else:
            run = dict(offset=i, length=1, owners=owner, before=f'{x:02x}' if x is not None else '', after=f'{y:02x}' if y is not None else ''); ledger.append(run)
    rebuilt = bytearray(raw[0]); rebuilt.extend(bytes(max(0, len(raw[1])-len(rebuilt))))
    for r in ledger:
        data = bytes.fromhex(r['after']); rebuilt[r['offset']:r['offset']+len(data)] = data
    assert bytes(rebuilt[:len(raw[1])]) == raw[1]
    write('physical-byte-delta.json', dict(different_positions=different, rows=ledger))
    # No consumed build command changes are hidden by source normalization.
    commands = P.load(ROOT/'build/set-b-product-r3/commands.json')
    assert commands == P.prepare_seed_commands(ROOT/'build/set-b-product-r3')
    write('inventory.json', dict(status='HALT' if failures else 'PASS', complete_inventory=not failures,
        unclassified_bytes=0 if not failures else 'metadata unresolved', failures=failures,
        elfs=[P.bind(p) for p in PATHS], instruction_proof=P.bind(instructions/'census.json'),
        allocated_proof=P.bind(allocated/'allocated-census.json'), driver=P.bind(Path(__file__)),
        physical_differences=different, reconstructed_seed_sha256=hashlib.sha256(rebuilt[:len(raw[1])]).hexdigest(),
        source_files=len(P.load(allocated/'source-census.json')['rows']), compile_roots=sum('-c' in x for x in commands),
        commands=P.bind(ROOT/'build/set-b-product-r3/commands.json'), instruction_functions=len(fs),
        widening_named_code_cost=10, runtime_timing_cost='pending execution', new_builds=0, new_links=0))
    print(json.dumps(dict(status='HALT' if failures else 'PASS', failures=failures, physical_differences=different), indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    for arg in ('out', 'allocated', 'instructions'): ap.add_argument('--'+arg, type=Path, required=True)
    args = ap.parse_args(); main(args.out.resolve(), args.allocated.resolve(), args.instructions.resolve())
