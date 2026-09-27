"""Read-only Set B instruction/relocation census on the existing third Seed.

No compiler, linker, media writer or emulator is invoked. Each run needs a
new output directory. Instruction pairing preserves opcodes except for the
ten owner-admitted vm_buf_off accesses; branch targets use instruction IDs.
"""
import argparse
import collections
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
from elf_truth import ElfTruth
from set_b_third_seed_inventory_halt_20260926 import instructions, PATHS, WIDTH, WITNESSES
import set_b_producer as P

ROOT = P.ROOT
AUTHORED = {'c2_overlay_call', 'c2_product_abort_recover',
            'c2_product_gc_mark_roots', 'card_l_stage', 'main', 'repl'}
BRANCHES = {0x10, 0x30, 0x50, 0x70, 0x80, 0x90, 0xb0, 0xd0, 0xf0}
WIDEN = {(0x86, 0x8e), (0x84, 0x8c), (0xa6, 0xae)}


def basename(s):
    return re.sub(r'\.\d+$', '', s.name) if s.symbol_type == 'Function' else s.name


def main(out):
    out.mkdir(exist_ok=False, parents=True)
    def write(name, v):
        (out/name).write_text(json.dumps(v, indent=2)+'\n')
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in PATHS] == [
        '7e57bc17f318dd22a6dbc0212fd5fde5b9598eaf645f4f98d6387e0c3f53f3b5',
        '1eb22d5282acae5e39c1a1ea37bd749d6e524c9fb45005791b298a26bb5b71cf']
    ts = [ElfTruth.read(p, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',
                        include_section_data=True) for p in PATHS]
    decoded = []
    for label, p in zip(('before', 'after'), PATHS):
        ins, cmd, raw = instructions(p)
        decoded.append(ins)
        (out/(label+'-disassembly.txt')).write_text(raw)
        write(label+'-disassembly-command.json', dict(command=cmd, exit=0))
    fs = [[s for s in t.symbols if s.bytes and s.symbol_type == 'Function'] for t in ts]
    # Clone names are paired by section and stem, only if the pair is unique.
    pairs = []; used = set(); removed = []; ambiguous = []
    for a in fs[0]:
        candidates = [b for b in fs[1] if b.name == a.name]
        if not candidates:
            candidates = [b for b in fs[1] if b.section == a.section and basename(b) == basename(a)]
        if len(candidates) > 1:
            left = sorted([f for f in fs[0] if f.section == a.section and basename(f) == basename(a) and f.name not in {g.name for g in fs[1]}], key=lambda f: int(f.name.rsplit('.', 1)[1]))
            right = sorted([f for f in candidates if f.name not in {g.name for g in fs[0]}], key=lambda f: int(f.name.rsplit('.', 1)[1]))
            if len(left) == len(right) and a in left:
                candidates = [right[left.index(a)]]
        if len(candidates) != 1:
            (removed if not candidates else ambiguous).append(asdict(a)); continue
        b = candidates[0]
        assert b.index not in used
        used.add(b.index); pairs.append((a, b))
    aliases = [{s.index: a.name for a, b in pairs for s in ([a] if k == 0 else [b])} for k in (0, 1)]
    index = []; instindex = []; relmaps = []
    for k, t in enumerate(ts):
        idx = collections.defaultdict(dict)
        for s in sorted((s for s in t.symbols if s.bytes), key=lambda s: (s.bytes, s.name), reverse=True):
            for addr in range(s.value, s.value+s.bytes): idx[s.section][addr] = s
        index.append(idx)
        ids = {}
        for f in fs[k]:
            seq = sorted(addr for addr in decoded[k][f.section] if f.value <= addr < f.value+f.bytes)
            for n, addr in enumerate(seq): ids[(f.section, addr)] = (aliases[k].get(f.index, f.name), n)
        instindex.append(ids)
        relmaps.append({(r.source_section, r.offset): r for r in t.relocations})

    def expression(k, r):
        t = ts[k]; s = t.symbols[r.target_symbol_index]; addr = s.value+r.addend
        owner = index[k][s.section].get(addr) if s.symbol_type == 'Section' else s
        if owner is not None:
            off = addr-owner.value
            if owner.symbol_type == 'Function' and off:
                point = instindex[k].get((owner.section, addr))
                if point: return ['instruction', *point]
            return ['owner', aliases[k].get(owner.index, owner.name), off]
        return ['symbol', s.name, r.addend]

    # Verify every supported retained relocation against the encoded ELF bytes.
    encodings = []; bad_encoding = []
    for k, t in enumerate(ts):
        for r in t.relocations:
            width = WIDTH.get(r.relocation_type)
            if width is None:
                if r.relocation_type == 'R_MOS_ADDR_ASCIZ': continue
                bad_encoding.append(dict(world=k, relocation=asdict(r), reason='unsupported')); continue
            value = t.symbols[r.target_symbol_index].value+r.addend
            sec = t.section(r.source_section); at = r.offset-sec.address
            actual = t.section_bytes(sec.name)[at:at+width]
            expected = ((value >> 8) & 255).to_bytes(1, 'little') if r.relocation_type == 'R_MOS_ADDR16_HI' else (value & ((1 << (8*width))-1)).to_bytes(width, 'little')
            row = dict(world=k, relocation=asdict(r), expression=expression(k, r), encoded=actual.hex())
            encodings.append(row)
            if actual != expected: bad_encoding.append(dict(**row, expected=expected.hex()))
    write('all-relocation-encodings.json', dict(rows=encodings, failures=bad_encoding))
    rows = []; failures = []; widened = collections.Counter()
    for a, b in pairs:
        seqs = [[decoded[k][f.section][addr] for addr in sorted(decoded[k][f.section]) if f.value <= addr < f.value+f.bytes] for k, f in enumerate((a, b))]
        row = dict(before=asdict(a), after=asdict(b), instructions=[len(v) for v in seqs], witnesses=[])
        if a.name in AUTHORED:
            row['status'] = 'AUTHORED: separate source attribution required'; rows.append(row); continue
        local = []
        for k, (f, seq) in enumerate(zip((a, b), seqs)):
            cursor = f.value
            for ins in seq:
                raw = bytes.fromhex(ins['bytes'])
                if ins['address'] != cursor: local.append(['decode gap', k, cursor, ins['address']])
                cursor = ins['address']+len(raw)
            if cursor != f.value+f.bytes: local.append(['decode extent', k, cursor, f.value+f.bytes])
        if len(seqs[0]) != len(seqs[1]): local.append(['instruction count', len(seqs[0]), len(seqs[1])])
        else:
            for n, (x, y) in enumerate(zip(*seqs)):
                raw = [bytes.fromhex(z['bytes']) for z in (x, y)]
                rels = [[(i, relmaps[k][(f.section, z['address']+i)]) for i in range(len(raw[k])) if (f.section, z['address']+i) in relmaps[k]] for k, (f, z) in enumerate(zip((a, b), (x, y)))]
                reason = None; family = 'identical instruction with proved relocation operands'
                wide = (raw[0][0], raw[1][0]) in WIDEN and a.name in WITNESSES
                masked = [bytearray(v) for v in raw]
                if len(rels[0]) != len(rels[1]): reason = 'relocation cardinality'
                else:
                    for (i, r), (j, s) in zip(*rels):
                        if i != j or expression(0, r) != expression(1, s): reason = 'relocation target'
                        if r.relocation_type != s.relocation_type and not (wide and (r.relocation_type, s.relocation_type) == ('R_MOS_ADDR8', 'R_MOS_ADDR16') and expression(0, r) in (['owner', 'vm_buf_off', 0], ['owner', 'vm_buf_off', 1])): reason = 'relocation type'
                        for k, off, rel in ((0, i, r), (1, j, s)):
                            w = WIDTH[rel.relocation_type]; masked[k][off:off+w] = bytes(w)
                if wide:
                    if len(rels[0]) != 1 or expression(0, rels[0][0][1]) not in (['owner', 'vm_buf_off', 0], ['owner', 'vm_buf_off', 1]): reason = 'unproved widening'
                    masked[1][0] = masked[0][0]; del masked[1][-1]
                    widened[a.name] += 1; family = 'admitted vm_buf_off widening; same register, field and flags'
                if raw[0][0] in BRANCHES and raw[1][0] == raw[0][0] and len(raw[0]) == len(raw[1]) == 2 and not rels[0] and not rels[1]:
                    targets = [z['address']+2+int.from_bytes(v[1:], 'little', signed=True) for z, v in zip((x, y), raw)]
                    points = [instindex[k].get((f.section, target)) for k, (f, target) in enumerate(zip((a, b), targets))]
                    if points[0] is None or points[0] != points[1]: reason = 'branch instruction target'
                    masked[0][1] = masked[1][1] = 0
                    family = 'same conditional opcode and paired instruction target'
                if masked[0] != masked[1]: reason = reason or 'unclassified opcode or literal bytes'
                witness = dict(index=n, before=x, after=y, family=family,
                    relocations=[[dict(offset=i, relocation=asdict(r), expression=expression(k, r)) for i, r in rs] for k, rs in enumerate(rels)])
                if reason: witness['failure'] = reason; local.append(witness)
                row['witnesses'].append(witness)
        row['status'] = 'FAIL' if local else 'PASS'; row['failures'] = local
        if local: failures.append(dict(function=a.name, failures=local))
        rows.append(row)
    write('function-instructions.json', rows)
    write('census.json', dict(status='REVIEW REQUIRED' if failures or removed or ambiguous or bad_encoding else 'PASS INSTRUCTION PASS ONLY',
        driver=P.bind(Path(__file__)), elfs=[P.bind(p) for p in PATHS], pairs=len(pairs),
        passed=sum(r['status']=='PASS' for r in rows), authored=sorted(AUTHORED),
        removed=removed, ambiguous=ambiguous, new=[asdict(f) for f in fs[1] if f.index not in used],
        widenings=dict(widened), failures=failures, bad_encodings=bad_encoding,
        complete_inventory=False, builds=0, links=0))
    print(json.dumps(dict(pairs=len(pairs), passed=sum(r['status']=='PASS' for r in rows),
        failed_functions=[(r['function'], len(r['failures'])) for r in failures],
        removed=len(removed), ambiguous=len(ambiguous), bad_encodings=len(bad_encoding), widenings=dict(widened)), indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args(); main(args.out.resolve())
