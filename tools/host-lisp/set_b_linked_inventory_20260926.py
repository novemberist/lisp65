"""Close allocated Set B owners against the instruction proof, without linking."""
import argparse
import collections
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True
import set_b_producer as P
from elf_truth import ElfTruth
from set_b_instruction_inventory_20260926 import AUTHORED, PATHS, WIDTH

ROOT = P.ROOT


def main(out, proof):
    out.mkdir(parents=True, exist_ok=False)
    write = lambda n, v: P.write(out/n, v)
    census = P.load(proof/'census.json')
    assert census['status'] == 'PASS INSTRUCTION PASS ONLY'
    assert census['widenings'] == dict(eval_init=2, vm_buf_ensure_mine=4, vm_buffer_call=2, vm_run_inner=2)
    assert census['driver'] == P.bind(ROOT/census['driver']['path'])
    ts = [ElfTruth.read(p, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj', include_section_data=True) for p in PATHS]
    assert census['elfs'] == [P.bind(p) for p in PATHS]
    # Source census follows the producer's complete copied tree, exact-context
    # projection, materialized include closure and linker authority.
    P.require_auth()
    roots = [p.parent for p in PATHS]
    materialized = {r['materialized_path']: ROOT/r['source']['path'] for r in P.load(P.CLOSURE)['materialized']}
    source_rows = []; source_fail = []
    allowed_ext = {'.c', '.h', '.s', '.S', '.ld'}
    names = sorted({str(p.relative_to(root)) for root in roots for p in root.rglob('*') if p.is_file() and p.suffix in allowed_ext})
    for name in names:
        a, b = [root/name for root in roots]
        family = None
        if not b.exists(): source_fail.append(['removed source', name]); continue
        if a.exists() and a.read_bytes() == b.read_bytes(): family = 'unchanged copied compiler/linker input'
        elif name.startswith('generated-product-sources/') and Path(name).name in P.UNITS:
            assert b.read_text() == P.project_unit(Path(name).name)
            family = 'authorized exact-context native source projection'
        elif name in materialized and b.read_bytes() == materialized[name].read_bytes():
            family = 'authorized materialized header/source'
        elif (ROOT/'config/set-b-native/linker'/name).is_file() and b.read_bytes() == (ROOT/'config/set-b-native/linker'/name).read_bytes():
            family = 'authorized linker placement'
        else: source_fail.append(['unclassified source', name])
        source_rows.append(dict(name=name, before=P.bind(a) if a.exists() else None, after=P.bind(b), family=family))
    write('source-census.json', dict(rows=source_rows, failures=source_fail, authority=P.require_auth()))

    functions = P.load(proof/'function-instructions.json')
    covers = [collections.defaultdict(dict), collections.defaultdict(dict)]
    mapping = {}; owners = {}; allrels = []; issues = []
    relmaps = [{(r.source_section, r.offset): r for r in t.relocations} for t in ts]
    encoded = P.load(proof/'all-relocation-encodings.json')
    assert not encoded['failures']
    expressions = [{(v['relocation']['source_section'], v['relocation']['offset']): v['expression'] for v in encoded['rows'] if v['world'] == k} for k in (0, 1)]

    def cover(k, sec, start, size, family):
        for pos in range(start, start+size):
            previous = covers[k][sec].get(pos)
            if previous is not None and previous != family:
                issues.append(['overlapping classification', k, sec, pos, previous, family])
            covers[k][sec][pos] = family

    for row in functions:
        a, b = row['before'], row['after']; name = a['name']
        family = 'authorized native body: '+name if name in AUTHORED else 'proved instruction/relocation equivalence'
        for k, f in enumerate((a, b)): cover(k, f['section'], f['value'], f['bytes'], family)
        if name in AUTHORED: continue
        assert row['status'] == 'PASS'
        for w in row['witnesses']:
            x, y = w['before'], w['after']
            for i in range(min(len(bytes.fromhex(x['bytes'])), len(bytes.fromhex(y['bytes'])))):
                mapping[(b['section'], y['address']+i)] = (a['section'], x['address']+i)
    new_sections = {r['section'] for r in P.load(P.INPUTS)['tenants']}
    new_functions = census['new']
    for f in new_functions:
        if f['section'] not in new_sections and f['name'] != 'c2_retire_run':
            issues.append(['new function outside authorized owners', f]); continue
        cover(1, f['section'], f['value'], f['bytes'], 'authorized retirement body')

    # Named non-function data is compared in owner coordinates, retaining exact
    # field offsets. BSS is accounted separately as allocation, never file bytes.
    data_rows = []
    old_data = {(s.name, s.symbol_type): s for s in ts[0].symbols if s.bytes and s.symbol_type != 'Function'}
    new_data = {(s.name, s.symbol_type): s for s in ts[1].symbols if s.bytes and s.symbol_type != 'Function'}
    for key in sorted(old_data.keys() | new_data.keys()):
        a, b = old_data.get(key), new_data.get(key)
        if a and b:
            if a.bytes != b.bytes: issues.append(['data size drift', asdict(a), asdict(b)]); continue
            if ts[1].section(b.section).section_type == 'SHT_NOBITS':
                data_rows.append(dict(before=asdict(a), after=asdict(b), family='same uninitialized owner, relocated'))
                continue
            for i in range(b.bytes):
                pos = (b.section, b.value+i); target = (a.section, a.value+i)
                if pos in mapping and mapping[pos] != target: issues.append(['data mapping overlap', key, pos])
                mapping[pos] = target; owners[pos] = b.name
        elif b and b.name in ('c2r_gc_failed', 'c2r_boot_count') and b.bytes == 1 and ts[1].section(b.section).section_type == 'SHT_NOBITS':
            data_rows.append(dict(before=None, after=asdict(b), family='authorized Set B state latch'))
        else: issues.append(['unclassified data owner addition/removal', asdict(a) if a else None, asdict(b) if b else None])
    write('data-owners.json', data_rows)

    # Map remaining non-function spans in section order. An unchanged length is
    # necessary, not sufficient: every byte and relocation target is checked.
    for sec in ts[1].sections:
        if 'SHF_ALLOC' not in sec.flags or sec.section_type == 'SHT_NOBITS': continue
        if sec.name in new_sections:
            cover(1, sec.name, sec.address, sec.bytes, 'authorized retirement body')
            continue
        if sec.name not in ts[0].sections_by_name:
            issues.append(['unclassified new allocated section', sec.name]); continue
        oldsec = ts[0].section(sec.name)
        left = [v for v in range(oldsec.address, oldsec.address+oldsec.bytes) if v not in covers[0][sec.name]]
        right = [v for v in range(sec.address, sec.address+sec.bytes) if v not in covers[1][sec.name]]
        used_old = {v[1] for k, v in mapping.items() if k[0] == sec.name and v[0] == sec.name}
        left = [v for v in left if v not in used_old]
        right = [v for v in right if (sec.name, v) not in mapping]
        if len(left) != len(right): issues.append(['unowned span length', sec.name, len(left), len(right)]); continue
        for a, b in zip(left, right): mapping[(sec.name, b)] = (sec.name, a)

    # Pair every relocation in the remaining (non-authored, non-function) data.
    admitted = set(); consumed = set(); relissues = []
    for r in ts[1].relocations:
        pos = (r.source_section, r.offset); category = covers[1][r.source_section].get(r.offset)
        if category:
            allrels.append(dict(after=asdict(r), family=category)); continue
        if r.relocation_type == 'R_MOS_ADDR_ASCIZ': continue
        oldpos = mapping.get(pos); old = relmaps[0].get(oldpos)
        if old is None:
            relissues.append(['unpaired relocation', asdict(r), oldpos]); continue
        same = old.relocation_type == r.relocation_type and expressions[0][oldpos] == expressions[1][pos]
        allrels.append(dict(before=asdict(old), after=asdict(r), before_expression=expressions[0][oldpos], after_expression=expressions[1][pos], equivalent=same))
        if not same: relissues.append(['data relocation target', allrels[-1]]); continue
        consumed.add(oldpos)
        admitted.update((r.source_section, r.offset+i) for i in range(WIDTH[r.relocation_type]))
    byte_rows = []; counts = collections.Counter()
    for sec in ts[1].sections:
        if 'SHF_ALLOC' not in sec.flags or sec.section_type == 'SHT_NOBITS': continue
        for i, value in enumerate(ts[1].section_bytes(sec.name)):
            pos = (sec.name, sec.address+i); category = covers[1][sec.name].get(pos[1])
            if category: counts[category] += 1; continue
            oldpos = mapping.get(pos); oldvalue = None
            if oldpos:
                oldsec = ts[0].section(oldpos[0]); off = oldpos[1]-oldsec.address
                oldvalue = ts[0].section_bytes(oldpos[0])[off]
            if pos in admitted: category = 'proved data relocation operand'
            elif oldvalue == value: category = 'owner-coordinate data/assembly identity'
            else: category = 'UNCLASSIFIED'
            counts[category] += 1
            if oldvalue != value:
                byte_rows.append(dict(section=sec.name, after_address=pos[1], before=oldpos, before_byte=oldvalue, after_byte=value, owner=owners.get(pos), family=category))
    write('remaining-relocations.json', dict(rows=allrels, failures=relissues))
    write('allocated-byte-differences.json', byte_rows)
    write('allocated-census.json', dict(status='REVIEW REQUIRED' if source_fail or issues or relissues or counts['UNCLASSIFIED'] else 'PASS ALLOCATED CONTENT',
        driver=P.bind(Path(__file__)), instruction_proof=P.bind(proof/'census.json'),
        elfs=[P.bind(p) for p in PATHS], counts=dict(counts), issues=issues,
        source_failures=source_fail, relocation_failures=relissues, complete_inventory=False))
    print(json.dumps(dict(counts=dict(counts), issues=issues[:12], source_failures=source_fail,
        relocation_failures=relissues[:8], total_issues=len(issues)+len(relissues)), indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True); ap.add_argument('--proof', type=Path, required=True)
    args = ap.parse_args(); main(args.out.resolve(), args.proof.resolve())
