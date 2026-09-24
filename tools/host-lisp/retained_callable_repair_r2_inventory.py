"""Retained-callable repair Seed 2 (member 2 alone): complete linked-byte inventory, anchor Final -> Seed 2.

Derived from the Seed-1 inventory; member 1 is withdrawn, so any difference in
.lisp65_rt_c2d_12 or its relocations is UNCLASSIFIED here.

Every differing byte of the two ELF files is inventoried, by section content
and by physical file offset, and the Seed is reconstructed from the anchor ELF
and the physical ledger alone.  Differences are admitted only as:

  member 1   the function c2_stream_phase_12 (the whole .lisp65_rt_c2d_12
             section) and its relocations;
  member 2   the function c2_append_rollback_prepare_phase (the tail of
             .lisp65_rt_c2append_journal_prepare) and its relocations; the two
             preceding functions of that section must be byte-identical;
  derived    runtime profile Build-ID immediates (same offsets as the
             dirty-anchor inventory) and the error table's Build-ID and CRC16,
             validated with the new Build-ID;
  metadata   the four symbol records of the two member functions and their
             section end markers.

Anything else is UNCLASSIFIED and fails the gate (binding d3d5044b: halt).
Inside the member functions the compiler reallocated registers; this is part
of the member, recorded as an instruction-level summary with exact witnesses
for the removed clause and the inserted field copies.  No build, no link.
"""
import hashlib
import json
import re
import struct
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/host-lisp'))
from elf_truth import ElfTruth  # noqa: E402
import error_text_table as E  # noqa: E402

OUT = ROOT/'build/retained-callable-repair-r2-seed-inventory-r2'
# r1 of this inventory carried the Seed-1 status wording ("two members"); kept.
READOBJ = ROOT/'tools/llvm-mos/bin/llvm-readobj'
OBJDUMP = ROOT/'tools/llvm-mos/bin/llvm-objdump'
WORLDS = [ROOT/'build/dirty-anchor-final-r3/wplto', ROOT/'build/retained-callable-repair-product-r2/wplto']
ELFS = [WORLDS[0]/'lisp65-c2-substitution-linked.prg.elf', WORLDS[1]/'resident-island-seed.prg.elf']
CONSUMED = [WORLDS[0].parent.parent/'dirty-anchor-product-r1/wplto/resident-island-seed.prg.authority-input-consumption.json',
            WORLDS[1]/'resident-island-seed.prg.authority-input-consumption.json']
ANCHOR_SHA = '6aa3040c3f6533a94c053b7b64b932be15514d856dd05f675da771a1f1ea1811'
PHASE12 = '.lisp65_rt_c2d_12'
JOURNAL = '.lisp65_rt_c2append_journal_prepare'
PREPARE = 'c2_append_rollback_prepare_phase'
BUILD_ID_SITES = [('.lisp65_boot_bank3_stage', [1272, 1282, 1292, 1302]),
                  ('.lisp65_rt_rtov_catalog', [5, 13, 21, 29]),
                  ('.lisp65_rt_rtov_record', [5, 13, 21, 29]),
                  ('.lisp65_rt_island_00', [5, 13, 21, 29]),
                  ('.lisp65_boot_carrier', [182, 192, 202, 212])]
# Exact witnesses read from the two linked ELFs (llvm-objdump, raw bytes).
# Anchor $C9AD..$C9C3: lsr $d; lda $c; ror; clc; adc #0; tay; lda $d; adc #$a0;
# cmp $7; bne; ldx #1; cpy $6; bne  -- BCODE_IDX(word) against directory_base+local.
REMOVED_CLAUSE = bytes.fromhex('460da50c6a186900a8a50d69a0c507d009a201c406d003')
INSERTED_COPIES = bytes.fromhex('a012b104a0d29116a013b104a0d39116a015b104a0369116a016b104a0379116')


def bind(path):
    raw = Path(path).read_bytes()
    return dict(path=str(Path(path).resolve().relative_to(ROOT)), bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())


def instructions(elf, section, start=None):
    text = subprocess.check_output([str(OBJDUMP), '-d', '--no-show-raw-insn',
                                    '--section='+section, str(elf)], text=True)
    if start:
        text = text[text.index('<'+start+'>:'):]
    rows = []
    for line in text.splitlines():
        m = re.match(r'^\s+([0-9a-f]+):\s+(.*)$', line)
        if m:
            rows.append(re.sub(r'\s+', ' ', re.sub(r';.*$|<[^>]*>', '', m[2])).strip())
    return rows


def classify(counts_a, counts_b):
    """Summarise an instruction-level member diff without admitting it."""
    import difflib
    ops = Counter()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=counts_a, b=counts_b, autojunk=False).get_opcodes():
        if tag == 'equal':
            ops['equal'] += i2 - i1
            continue
        left, right = counts_a[i1:i2], counts_b[j1:j2]
        if tag == 'replace' and len(left) == len(right):
            for x, y in zip(left, right):
                if x.split(' ')[0] == y.split(' ')[0] and x.split(' ')[0][0] in 'bj':
                    ops['branch/jump target displacement'] += 1
                elif x.split(' ')[0] == y.split(' ')[0]:
                    ops['same opcode, different operand (register allocation)'] += 1
                else:
                    ops['different opcode (scheduling/allocation)'] += 1
        else:
            ops['removed'] += len(left)
            ops['inserted'] += len(right)
    return dict(ops)


def main():
    if OUT.exists():
        raise SystemExit('fresh output required: '+str(OUT))
    OUT.mkdir(parents=True)
    raws = [p.read_bytes() for p in ELFS]
    assert hashlib.sha256(raws[0]).hexdigest() == ANCHOR_SHA
    ts = [ElfTruth.read(p, llvm_readobj=READOBJ, include_section_data=True) for p in ELFS]
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
    assert constants[0]['profile_build_id'] == 0xe93dd935
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
    s = ts[0].symbol('l65e_table')
    off = s.value - ts[0].section(s.section).address
    add(s.section, off, tables, 'derived error-table Build-ID and validated CRC16')
    # Member extents.
    prepare = [t.symbol(PREPARE) for t in ts]
    assert prepare[0].value == prepare[1].value and prepare[0].section == prepare[1].section == JOURNAL
    member2_start = prepare[0].value - ts[0].section(JOURNAL).address
    phase12 = [t.symbol('c2_stream_phase_12') for t in ts]
    assert all(p.value == t.section(PHASE12).address and p.bytes == t.section(PHASE12).bytes
               for p, t in zip(phase12, ts)), 'phase 12 function is not its whole section'
    assert all(p.value + p.bytes == t.section(JOURNAL).address + t.section(JOURNAL).bytes
               for p, t in zip(prepare, ts)), 'prepare phase is not the tail of its section'
    assert ts[0].section_bytes(JOURNAL)[:member2_start] == ts[1].section_bytes(JOURNAL)[:member2_start]
    sections, unclassified, counts = [], [], Counter()
    assert [x.name for x in ts[0].sections] == [x.name for x in ts[1].sections]
    for a, b in zip(ts[0].sections, ts[1].sections):
        assert (a.name, a.address, a.flags, a.section_type) == (b.name, b.address, b.flags, b.section_type)
        if a.name not in (JOURNAL, '.rela'+JOURNAL, '.symtab'):
            assert a.bytes == b.bytes, a.name
        if a.section_type == 'SHT_NOBITS':
            continue
        left, right = ts[0].section_bytes(a.name), ts[1].section_bytes(a.name)
        rows = []
        for i in range(max(len(left), len(right))):
            x = left[i] if i < len(left) else None
            y = right[i] if i < len(right) else None
            if x == y:
                continue
            k = (a.name, i)
            if k in known:
                assert (x, y) == known[k][:2]
                family = known[k][2]
            elif a.name == JOURNAL and i >= member2_start:
                family = 'member 2: c2_append_rollback_prepare_phase recompiled (span copies)'
            elif a.name == '.rela'+JOURNAL:
                family = 'member relocation records'
            elif a.name == '.symtab':
                family = 'member symbol metadata'
            else:
                family = 'UNCLASSIFIED'
                unclassified.append(k)
            rows.append(dict(offset=i, before=x, after=y, family=family))
            counts[family] += 1
        sections.append(dict(section=a.name, address=a.address, before_bytes=a.bytes, after_bytes=b.bytes,
                             differences=rows))
    # Semantic symbol and relocation deltas.
    symrows = []
    assert len(ts[0].symbols) == len(ts[1].symbols)
    for a, b in zip(ts[0].symbols, ts[1].symbols):
        assert (a.name, a.section, a.binding, a.symbol_type) == (b.name, b.section, b.binding, b.symbol_type)
        if a != b:
            symrows.append(dict(name=a.name, before_value=a.value, after_value=b.value,
                                before_bytes=a.bytes, after_bytes=b.bytes))
    assert {r['name'] for r in symrows} == {PREPARE, '__lisp65_rt_c2append_journal_prepare_end'}, symrows
    rel = [[r for r in t.relocations] for t in ts]
    outside = [[r for r in rs if not (r.source_section == JOURNAL and r.offset >= prepare[0].value)] for rs in rel]
    assert outside[0] == outside[1], 'relocation outside the member functions changed'
    member_rel = [[dict(section=r.source_section, offset=r.offset, type=r.relocation_type, target=r.target,
                        addend=r.addend) for r in rs if r not in outside[k]] for k, rs in enumerate(rel)]
    # Instruction-level member summary and exact witnesses.
    p12 = [instructions(p, PHASE12) for p in ELFS]
    jp = [instructions(p, JOURNAL, PREPARE) for p in ELFS]
    s12 = [t.section_bytes(PHASE12) for t in ts]
    sjp = [t.section_bytes(JOURNAL)[member2_start:] for t in ts]
    witnesses = dict(
        removed_clause_in_anchor=s12[0].count(REMOVED_CLAUSE), removed_clause_in_seed=s12[1].count(REMOVED_CLAUSE),
        inserted_copies_in_anchor=sjp[0].count(INSERTED_COPIES), inserted_copies_in_seed=sjp[1].count(INSERTED_COPIES))
    assert s12[0] == s12[1], 'phase 12 changed although member 1 is withdrawn'
    assert witnesses == dict(removed_clause_in_anchor=1, removed_clause_in_seed=1,
                             inserted_copies_in_anchor=0, inserted_copies_in_seed=1), witnesses
    members = dict(
        member1=dict(status='WITHDRAWN: c2_stream_phase_12 byte-identical', bytes=[p.bytes for p in phase12],
                     witness='clause present in both ELFs: '+REMOVED_CLAUSE.hex()),
        member2=dict(function=PREPARE, bytes=[p.bytes for p in prepare],
                     instructions=[len(x) for x in jp], diff=classify(*jp),
                     witness='seed-only copies row[18],row[19]->w+$D2,$D3 and row[21],row[22]->w+$36,$37: '
                             + INSERTED_COPIES.hex()),
        relocations=dict(anchor=len(member_rel[0]), seed=len(member_rel[1])))
    (OUT/'member-instructions.json').write_text(json.dumps(dict(phase12=p12, prepare=jp), indent=1)+'\n')
    # Physical file ledger.
    def layout(raw, t):
        shoff = struct.unpack_from('<I', raw, 32)[0]
        phoff = struct.unpack_from('<I', raw, 28)[0]
        ehsize, phsize, phnum, shsize, shnum, _ = struct.unpack_from('<6H', raw, 40)
        assert shnum == len(t.sections)
        intervals = [(0, ehsize, 'ELF header'), (phoff, phoff+phsize*phnum, 'program headers'),
                     (shoff, shoff+shsize*shnum, 'section headers')]
        for s in t.sections:
            vals = struct.unpack_from('<10I', raw, shoff+s.index*shsize)
            offset, size = vals[4:6]
            assert size == s.bytes
            if s.section_type != 'SHT_NOBITS' and size:
                intervals.append((offset, offset+size, 'section '+s.name))
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
    # Negative controls on the classifier itself.
    controls = []
    for label, key in [('underived-immediate', ('.text', 100)), ('foreign-section', ('.rodata', 0)),
                       ('phase-12-byte', (PHASE12, 0)),
                       ('journal-write-phase-byte', (JOURNAL, member2_start-1))]:
        fam = known.get(key)
        member = key[0] == JOURNAL and key[1] >= member2_start
        if fam is None and not member:
            controls.append(label)
        else:
            raise AssertionError('negative control would be admitted: '+label)
    status = 'PASS: ALL DIFFERENCES INSIDE MEMBER 2 OR DERIVED' if not unclassified else \
        'HALT: UNCLASSIFIED LINKED BYTES'
    result = dict(status=status, binding='d3d5044b', authority='e0be22c1', ELFs=[bind(p) for p in ELFS],
                  constants=constants, sections=[s for s in sections if s['differences']],
                  changed_section_byte_counts=dict(counts), unclassified_section_bytes=unclassified,
                  semantic_symbol_deltas=symrows, member_relocations=member_rel, members=members,
                  witnesses=witnesses, physical_different_bytes=total, physical_owners=dict(owners),
                  physical_inventory=bind(OUT/'physical-byte-delta.json'),
                  reconstructed_seed_sha256=hashlib.sha256(rebuilt).hexdigest(),
                  classifier_controls_rejected=controls, driver=bind(Path(__file__)),
                  budget_consumed=dict(seed=2, final=0, product_link=0))
    (OUT/'inventory.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(status=status, counts=dict(counts), symbols=len(symrows),
                          member_relocations=members['relocations'], physical=total,
                          members={k: v.get('diff', v.get('status')) for k, v in members.items() if k.startswith('member')}), indent=1))
    if unclassified:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
