"""Nested-error recovery Seed: complete linked-byte inventory, repair Final -> Seed.

The card changes one function in ordinary text,
c2_abort_empty_journal_derived (.text.c2_abort_empty_journal, the first
function after the CRT helpers).  It grows by D bytes, so every later .text
function moves by +D and every absolute reference to them changes.  The
identity gate (2026-09-23: input closure + complete linked-byte inventory +
per-family proof, never program-byte identity) is discharged here by a
relocation-resolved address-drift proof:

  address map   f(x) = x + D for .text targets at M_end_base <= x <= text_end_base,
                x elsewhere (x inside the member other than its entry is never
                admitted); targets in other sections never move, including the
                mapped far/cold sections whose VMAs overlap .text;
  symbols       paired by (name, section, type, binding); every B value equals
                f(A value) with equal size, except the member's own size;
  relocations   every base relocation outside the member has a Seed relocation
                at f(offset) with the same type, the same target identity
                (symbol name and section) and resolved value f(resolved);
                the only unmatched Seed relocations lie inside the member;
  bytes         every relocated field is re-encoded from its resolved value on
                both sides (ADDR8/IMM8/ADDR16/ADDR16_LO/ADDR16_HI/ADDR_ASCIZ)
                and must equal the linked bytes; every other byte of every
                allocated section equals its mapped counterpart, except the
                member and the derived Build-ID/error-table sites;
  metadata      .symtab/.strtab (address drift, member size, one local
                symbol-order change), .rela.* (proved semantically above),
                .llvm_sympart (one 16-bit address, drifted by f).

Anything else is UNCLASSIFIED and fails the gate (binding 44c021ee: halt).
Finally the Seed ELF is reconstructed from the base ELF and the exhaustive
physical file-offset ledger.  No build, no link.
"""
import hashlib
import json
import re
import struct
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/host-lisp'))
from elf_truth import ElfTruth  # noqa: E402
import error_text_table as E  # noqa: E402

OUT = ROOT/'build/nested-error-recovery-seed-inventory-r1'
READOBJ = ROOT/'tools/llvm-mos/bin/llvm-readobj'
OBJDUMP = ROOT/'tools/llvm-mos/bin/llvm-objdump'
WORLDS = [ROOT/'build/retained-callable-repair-final-r1/wplto', ROOT/'build/nested-error-recovery-product-r1/wplto']
ELFS = [WORLDS[0]/'lisp65-c2-substitution-linked.prg.elf', WORLDS[1]/'resident-island-seed.prg.elf']
CONSUMED = [ROOT/'build/retained-callable-repair-product-r2/wplto/resident-island-seed.prg.authority-input-consumption.json',
            WORLDS[1]/'resident-island-seed.prg.authority-input-consumption.json']
BASE_SHA = '815b60a5fb4baf405d5b8e14dac5ad9e593c9bf3f73877efc6b6f63499dc26a1'
MEMBER = 'c2_abort_empty_journal_derived'
BUILD_ID_SITES = [('.lisp65_boot_bank3_stage', [1272, 1282, 1292, 1302]),
                  ('.lisp65_rt_rtov_catalog', [5, 13, 21, 29]),
                  ('.lisp65_rt_rtov_record', [5, 13, 21, 29]),
                  ('.lisp65_rt_island_00', [5, 13, 21, 29]),
                  ('.lisp65_boot_carrier', [182, 192, 202, 212])]
WIDTH = {'R_MOS_ADDR8': 1, 'R_MOS_IMM8': 1, 'R_MOS_ADDR16': 2, 'R_MOS_ADDR16_LO': 1,
         'R_MOS_ADDR16_HI': 1}


def bind(path):
    raw = Path(path).read_bytes()
    return dict(path=str(Path(path).resolve().relative_to(ROOT)), bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())


def encode(kind, value, data, at):
    """Bytes the linker must have written for this relocation; width."""
    if kind in ('R_MOS_ADDR8', 'R_MOS_IMM8', 'R_MOS_ADDR16_LO'):
        return bytes([value & 255]), 1
    if kind == 'R_MOS_ADDR16_HI':
        return bytes([(value >> 8) & 255]), 1
    if kind == 'R_MOS_ADDR16':
        return struct.pack('<H', value & 0xffff), 2
    if kind == 'R_MOS_ADDR_ASCIZ':
        text = str(value).encode()+b'\0'
        return text, len(text)
    raise AssertionError('unsupported relocation type: '+kind)


def instructions(elf, start, length):
    text = subprocess.check_output([str(OBJDUMP), '-d', '--no-show-raw-insn', '--section=.text',
                                    f'--start-address={start}', f'--stop-address={start+length}', str(elf)],
                                   text=True)
    rows = []
    for line in text.splitlines():
        m = re.match(r'^\s+([0-9a-f]+):\s+(.*)$', line)
        if m:
            rows.append(re.sub(r'\s+', ' ', re.sub(r';.*$', '', m[2])).strip())
    return rows


def main():
    if OUT.exists():
        raise SystemExit('fresh output required: '+str(OUT))
    OUT.mkdir(parents=True)
    raws = [p.read_bytes() for p in ELFS]
    assert hashlib.sha256(raws[0]).hexdigest() == BASE_SHA
    ts = [ElfTruth.read(p, llvm_readobj=READOBJ, include_section_data=True) for p in ELFS]
    A, B = ts
    # Member extent and the address map.
    ma, mb = A.symbol(MEMBER), B.symbol(MEMBER)
    assert ma.section == mb.section == '.text' and ma.value == mb.value
    D = mb.bytes - ma.bytes
    text = [t.section('.text') for t in ts]
    assert text[0].address == text[1].address and text[1].bytes - text[0].bytes == D
    m_start, m_end_a, m_end_b = ma.value, ma.value+ma.bytes, mb.value+mb.bytes
    t_end_a = text[0].address+text[0].bytes

    def f(x):
        if m_end_a <= x <= t_end_a:
            return x+D
        assert not (m_start < x < m_end_a), ('reference into the member interior', hex(x))
        return x
    # Consumed identities: plane-derived constants must be unchanged.
    constants = []
    for w, c in zip(WORLDS, CONSUMED):
        value = json.loads(c.read_text())
        vals = {x['compiler_definition']: x['consumed_value'] for x in value['manifest']['derived_constants']}
        et = (w/'error-text-table.bin').read_bytes()
        bid = int.from_bytes(et[8:12], 'little')
        E.parse_table(et, expected_build_id=bid)
        constants.append(dict(manifest_constants=vals, profile_build_id=bid, error_table=bind(w/'error-text-table.bin'),
                              consumption=bind(c)))
    assert constants[0]['manifest_constants'] == constants[1]['manifest_constants']
    ids = [c['profile_build_id'] for c in constants]
    known = {}

    def add(section, offset, pair, family):
        for t, b in zip(ts, pair):
            assert t.section_bytes(section)[offset:offset+len(b)] == b, (section, offset)
        for i, (x, y) in enumerate(zip(*pair)):
            if x != y:
                known[(section, offset+i)] = (x, y, family)
    for section, offsets in BUILD_ID_SITES:
        for offset, shift in zip(offsets, (0, 8, 16, 24)):
            add(section, offset, [bytes([(v >> shift) & 255]) for v in ids], 'derived runtime Build-ID immediate')
    tables = [(w/'error-text-table.bin').read_bytes() for w in WORLDS]
    assert tables[0][:8] == tables[1][:8] and tables[0][12:14] == tables[1][12:14] and tables[0][16:] == tables[1][16:]
    s = A.symbol('l65e_table')
    assert B.symbol('l65e_table').value == s.value
    add(s.section, s.value - A.section(s.section).address, tables, 'derived error-table Build-ID and validated CRC16')
    # Sections: same population and geometry, .text / .rela.text sizes aside.
    assert [x.name for x in A.sections] == [x.name for x in B.sections]
    for a, b in zip(A.sections, B.sections):
        assert (a.name, a.address, a.flags, a.section_type) == (b.name, b.address, b.flags, b.section_type), a.name
        if a.name not in ('.text', '.rela.text'):
            assert a.bytes == b.bytes, a.name
    # Symbols, paired by identity.
    def keyed(t):
        groups = defaultdict(list)
        for y in t.symbols:
            groups[(y.name, y.section, y.symbol_type, y.binding)].append(y)
        return groups
    ga, gb = keyed(A), keyed(B)
    assert {k: len(v) for k, v in ga.items()} == {k: len(v) for k, v in gb.items()}
    moved, symrows, symbad = 0, [], []
    for k in ga:
        xs = sorted(ga[k], key=lambda y: y.value)
        ys = sorted(gb[k], key=lambda y: y.value)
        for x, y in zip(xs, ys):
            want = f(x.value) if x.section == '.text' else x.value
            size_ok = x.bytes == y.bytes or (x.name == MEMBER and y.bytes == x.bytes+D) or \
                (x.symbol_type == 'Section' and x.name == '.text' and y.bytes == x.bytes+D)
            if y.value != want or not size_ok:
                symbad.append(dict(name=x.name, section=x.section, before=x.value, after=y.value,
                                   expected=want, before_bytes=x.bytes, after_bytes=y.bytes))
            elif y.value != x.value or y.bytes != x.bytes:
                moved += y.value != x.value
                symrows.append(dict(name=x.name, section=x.section, before=x.value, after=y.value,
                                    before_bytes=x.bytes, after_bytes=y.bytes))
    order_changed = [(x.index, x.name, y.name) for x, y in zip(A.symbols, B.symbols) if x.name != y.name]
    # Relocations, semantically.
    def rel_index(t):
        out = {}
        for r in t.relocations:
            key = (r.source_section, r.offset)
            assert key not in out, key
            out[key] = r
        return out
    ra, rb = rel_index(A), rel_index(B)
    matched, relbad, drifted = set(), [], Counter()
    member_rel_a, member_rel_b = [], []
    for (sec, off), r in ra.items():
        if sec == '.text' and m_start <= off < m_end_a:
            member_rel_a.append(r)
            continue
        key = (sec, f(off) if sec == '.text' else off)
        q = rb.get(key)
        ia, ib = A.relocation_target_identity(r), (B.relocation_target_identity(q) if q else None)
        # Only targets in .text move; mapped far/cold sections share VMAs
        # with .text and do not move.
        want = f(ia['resolved_value']) if ia['section'] == '.text' else ia['resolved_value']
        ok = q is not None and q.relocation_type == r.relocation_type and ia['symbol'] == ib['symbol'] \
            and ia['section'] == ib['section'] and ib['resolved_value'] == want
        if not ok:
            relbad.append(dict(section=sec, offset=off, type=r.relocation_type, target=r.target,
                               resolved=ia['resolved_value'],
                               seed=None if q is None else dict(offset=q.offset, type=q.relocation_type,
                                                                target=q.target, resolved=ib['resolved_value'])))
            continue
        matched.add(key)
        if ib['resolved_value'] != ia['resolved_value']:
            drifted[sec] += 1
    for key, q in rb.items():
        if key in matched:
            continue
        if key[0] == '.text' and m_start <= key[1] < m_end_b:
            member_rel_b.append(q)
        else:
            relbad.append(dict(section=key[0], offset=key[1], type=q.relocation_type, target=q.target,
                               base=None, reason='seed relocation without base counterpart'))
    # Bytes of every allocated section.
    fields = [defaultdict(dict), defaultdict(dict)]
    encbad = []
    for side, t in enumerate(ts):
        for (sec, off), r in (ra, rb)[side].items():
            s = t.section(sec)
            data = t.section_bytes(sec)
            o = off - s.address
            value = t.relocation_target_identity(r)['resolved_value']
            want, width = encode(r.relocation_type, value, data, o)
            if data[o:o+width] != want:
                encbad.append(dict(side=side, section=sec, offset=off, type=r.relocation_type,
                                   linked=data[o:o+width].hex(), encoded=want.hex()))
            for i in range(width):
                fields[side][sec][o+i] = (r.relocation_type, value)
    sections, unclassified, counts = [], [], Counter()
    for a, b in zip(A.sections, B.sections):
        if a.section_type == 'SHT_NOBITS':
            continue
        left, right = A.section_bytes(a.name), B.section_bytes(b.name)
        alloc = 'SHF_ALLOC' in a.flags
        rows = []

        def note(off_a, off_b, x, y, family):
            rows.append(dict(offset_base=off_a, offset_seed=off_b, before=x, after=y, family=family))
            counts[family] += 1
            if family == 'UNCLASSIFIED':
                unclassified.append((a.name, off_a, off_b))
        if alloc:
            base_addr = a.address
            if a.name == '.text':
                pairs = [(i, i) for i in range(m_start-base_addr)] + \
                        [(i, i+D) for i in range(m_end_a-base_addr, len(left))]
                for j in range(m_start-base_addr, m_end_b-base_addr):
                    x = left[j] if j < m_end_a-base_addr else None
                    note(j if x is not None else None, j, x, right[j],
                         'member: c2_abort_empty_journal_derived recompiled (c-alpha loop)')
            else:
                pairs = [(i, i) for i in range(len(left))]
            fa, fb = fields[0].get(a.name, {}), fields[1].get(a.name, {})
            for i, j in pairs:
                x, y = left[i], right[j]
                if i in fa or j in fb:
                    if (i in fa) != (j in fb):
                        note(i, j, x, y, 'UNCLASSIFIED')
                    elif x != y:
                        note(i, j, x, y, 'relocated address field: target drifted by f (re-encoded both sides)')
                    continue
                if x == y:
                    continue
                k = (a.name, i)
                if k in known and i == j:
                    assert (x, y) == known[k][:2]
                    note(i, j, x, y, known[k][2])
                else:
                    note(i, j, x, y, 'UNCLASSIFIED')
        else:
            if left == right:
                continue
            if a.name == '.symtab' or a.name == '.strtab':
                family = 'symbol metadata: address drift, member size, local symbol order'
            elif a.name.startswith('.rela'):
                family = 'relocation metadata (proved semantically)'
            elif a.name == '.llvm_sympart':
                assert left[:11] == right[:11] == b'contingent\0' and left[13:] == right[13:]
                va, vb = struct.unpack_from('<H', left, 11)[0], struct.unpack_from('<H', right, 11)[0]
                assert vb == f(va) and va != vb, (hex(va), hex(vb))
                family = 'symbol-partition address drifted by f'
            else:
                family = 'UNCLASSIFIED'
            for i in range(max(len(left), len(right))):
                x = left[i] if i < len(left) else None
                y = right[i] if i < len(right) else None
                if x != y:
                    note(i, i, x, y, family)
        if rows:
            sections.append(dict(section=a.name, address=a.address, before_bytes=a.bytes, after_bytes=b.bytes,
                                 differing=len(rows),
                                 families=dict(Counter(r['family'] for r in rows)),
                                 first=rows[:8]))
    # Member witnesses and instruction summary.
    ia = instructions(ELFS[0], m_start, ma.bytes)
    ib = instructions(ELFS[1], m_start, mb.bytes)

    def calls(rows, target):
        return sum(1 for r in rows if r.startswith('jsr') and '<'+target+'>' in r)
    witness = {}
    for side, rows in (('base', ia), ('seed', ib)):
        witness[side] = dict(instructions=len(rows),
                             overlay_calls=calls(rows, 'c2_overlay_call'),
                             rollback_plan_calls=calls(rows, 'c2_append_run_rollback_plan'),
                             c2d_reads=calls(rows, 'c2_stream_c2d_read'),
                             ready_clears=sum(1 for r in rows if re.match(r'stz \$8c\b', r)))
    jc = B.symbol('c2_journal_count').value
    witness['seed']['journal_count_stores'] = sum(1 for r in ib if r.startswith('stz') and f'${jc:x}' in r)
    witness['base']['journal_count_stores'] = sum(1 for r in ia if r.startswith('stz') and f'${jc:x}' in r)
    assert witness['base']['overlay_calls'] == 2 and witness['seed']['overlay_calls'] == 4, witness
    assert witness['base']['rollback_plan_calls'] == witness['seed']['rollback_plan_calls'] == 1, witness
    assert witness['base']['c2d_reads'] == witness['seed']['c2d_reads'] == 1, witness
    (OUT/'member-instructions.json').write_text(json.dumps(dict(base=ia, seed=ib), indent=1)+'\n')
    # Physical file ledger.
    def layout(raw, t):
        shoff = struct.unpack_from('<I', raw, 32)[0]
        phoff = struct.unpack_from('<I', raw, 28)[0]
        ehsize, phsize, phnum, shsize, shnum, _ = struct.unpack_from('<6H', raw, 40)
        assert shnum == len(t.sections)
        intervals = [(0, ehsize, 'ELF header'), (phoff, phoff+phsize*phnum, 'program headers'),
                     (shoff, shoff+shsize*shnum, 'section headers')]
        for sec in t.sections:
            vals = struct.unpack_from('<10I', raw, shoff+sec.index*shsize)
            offset, size = vals[4:6]
            assert size == sec.bytes
            if sec.section_type != 'SHT_NOBITS' and size:
                intervals.append((offset, offset+size, 'section '+sec.name))
        labels = [None]*len(raw)
        for start, end, label in sorted(intervals):
            for i in range(start, end):
                assert labels[i] is None, (label, i)
                labels[i] = (label, i-start)
        for i, x in enumerate(labels):
            if x is None:
                assert raw[i] == 0
                labels[i] = ('zero alignment padding', 0)
        return labels
    layouts = [layout(r, t) for r, t in zip(raws, ts)]
    physical, total, run = [], 0, None
    for i in range(max(map(len, raws))):
        a = raws[0][i] if i < len(raws[0]) else None
        b = raws[1][i] if i < len(raws[1]) else None
        if a == b:
            run = None
            continue
        total += 1
        owners = [layouts[k][i][0] if i < len(raws[k]) else 'EOF' for k in (0, 1)]
        if run and run['offset']+run['length'] == i and run['owners'] == owners:
            run['length'] += 1
            run['before'] += f'{a:02x}' if a is not None else ''
            run['after'] += f'{b:02x}' if b is not None else ''
        else:
            run = dict(offset=i, length=1, owners=owners, before=f'{a:02x}' if a is not None else '',
                       after=f'{b:02x}' if b is not None else '')
            physical.append(run)
    owners = Counter(o for r in physical for o in set(r['owners']))
    rebuilt = bytearray(raws[0])
    if len(rebuilt) < len(raws[1]):
        rebuilt.extend(bytes(len(raws[1])-len(rebuilt)))
    for r in physical:
        after = bytes.fromhex(r['after'])
        rebuilt[r['offset']:r['offset']+len(after)] = after
    rebuilt = bytes(rebuilt[:len(raws[1])])
    assert rebuilt == raws[1], 'physical ledger does not reconstruct the Seed'
    (OUT/'physical-byte-delta.json').write_text(json.dumps(dict(
        status='EXHAUSTIVE FILE-OFFSET INVENTORY', different_bytes=total, rows=physical),
        separators=(',', ':'))+'\n')
    # Negative controls on the classifier itself: a byte flip outside a
    # relocated field or a derived site must be unclassified; a relocation
    # whose resolved target does not follow f must be rejected.
    controls = []
    text_a = A.section_bytes('.text')
    probe = next(i for i in range(m_end_a-text[0].address, len(text_a))
                 if i not in fields[0]['.text'])
    ro = next(i for i in range(A.section('.rodata').bytes) if i not in fields[0].get('.rodata', {}))
    for label, key in [('unrelocated-moved-text-byte', ('.text', probe)), ('foreign-rodata-byte', ('.rodata', ro))]:
        if key[1] in fields[0].get(key[0], {}) or key in known:
            raise AssertionError('negative control would be admitted: '+label)
        controls.append(label)
    try:
        f(m_start+1)
    except AssertionError:
        controls.append('reference-into-member-interior')
    else:
        raise AssertionError('negative control would be admitted: member interior')
    some = next(r for (sec, off), r in ra.items() if sec == '.text' and off >= m_end_a
                and A.relocation_target_identity(r)['resolved_value'] >= m_end_a
                and A.relocation_target_identity(r)['resolved_value'] < t_end_a)
    if A.relocation_target_identity(some)['resolved_value'] == f(A.relocation_target_identity(some)['resolved_value']):
        raise AssertionError('negative control would be admitted: undrifted moved target')
    controls.append('moved-target-without-drift')
    status = 'PASS: ALL DIFFERENCES INSIDE THE MEMBER, ADDRESS DRIFT BY f, OR DERIVED' \
        if not (unclassified or symbad or relbad or encbad) else 'HALT: UNCLASSIFIED LINKED BYTES'
    result = dict(status=status, binding='44c021ee', authority='90b5f9f2', ELFs=[bind(p) for p in ELFS],
                  constants=constants,
                  address_map=dict(member=MEMBER, member_start=m_start, member_end_base=m_end_a,
                                   member_end_seed=m_end_b, delta=D, text_end_base=t_end_a),
                  sections=sections, changed_section_byte_counts=dict(counts),
                  unclassified_section_bytes=unclassified[:200], unclassified_count=len(unclassified),
                  symbols=dict(changed=len(symrows), moved=moved, bad=symbad, local_order_changes=order_changed),
                  relocations=dict(base=len(ra), seed=len(rb), matched=len(matched),
                                   drifted_by_section=dict(drifted), bad=relbad[:200], bad_count=len(relbad),
                                   member_base=len(member_rel_a), member_seed=len(member_rel_b),
                                   encoding_failures=encbad[:50], encoding_failure_count=len(encbad)),
                  member=dict(function=MEMBER, bytes=[ma.bytes, mb.bytes], witness=witness),
                  physical_different_bytes=total, physical_owners=dict(owners),
                  physical_inventory=bind(OUT/'physical-byte-delta.json'),
                  reconstructed_seed_sha256=hashlib.sha256(rebuilt).hexdigest(),
                  classifier_controls_rejected=controls, driver=bind(Path(__file__)),
                  budget_consumed=dict(seed=1, final=0, product_link=0))
    (OUT/'inventory.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(status=status, delta=D, counts=dict(counts), unclassified=len(unclassified),
                          symbols_bad=len(symbad), symbols_changed=len(symrows), relocations_bad=len(relbad),
                          encoding_failures=len(encbad), drifted=dict(drifted),
                          member=witness, physical=total), indent=1))
    if status.startswith('HALT'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
