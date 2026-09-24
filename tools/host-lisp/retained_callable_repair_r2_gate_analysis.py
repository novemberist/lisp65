"""Seed 2: offline evaluation of binding gates 1-4 from the executed emulator dumps.

Reads only the gate receipts and their raw Bank-0 / Bank-2 / C2D dumps; every
dump is verified against its bound SHA first.  No emulator, compiler or link.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/host-lisp'))
import retained_callable_writer_analysis as A  # noqa: E402

OUT = ROOT/'build/retained-callable-repair-r2/gate-analysis.json'
CODE7 = 'b5000002030000010705'           # (defun f () 7), as published on the anchor


def bind(path):
    raw = Path(path).read_bytes()
    return dict(path=str(Path(path).resolve().relative_to(ROOT)), bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())


def run(name, inputs):
    d = ROOT/f'build/retained-callable-repair-r2-gates-{name}'
    r = json.loads((d/'receipt.json').read_text())
    inputs.append(bind(d/'receipt.json'))
    for row in r['captures']:
        for b in list(row['regions'].values()) + [row['screen']]:
            assert bind(ROOT/b['path'])['sha256'] == b['sha256'], b['path']
    return d, r


def region(d, label, name):
    return (d/f'{label}-{name}.bin').read_bytes()


def population(bc, bb, ac, ab):
    """Comparator: every pre-existing entry (row + code) and the five planes of the
    pre-existing population byte-identical from capture b to capture a."""
    n = A.u(bc, 16, 2)
    changed = [i for i in range(n) if A.entry(bc, bb, i) != A.entry(ac, ab, i)]
    planes = {name: bc[off:off+cnt] == ac[off:off+cnt] for name, off, cnt in [
        ('header-prefix', 0, 12), ('images', 48, A.u(bc, 12, 2)*32), ('entries', A.u(bc, 30, 2), n*10),
        ('resolutions', A.u(bc, 32, 2), A.u(bc, 20, 2)*2), ('roots', A.u(bc, 34, 2), A.u(bc, 24, 2)*2)]}
    return dict(entries_before=n, entries_after=A.u(ac, 16, 2), changed=changed, planes=planes,
                ok=not changed and all(planes.values()))


def main():
    inputs = []
    gates = {}
    # Gate 1 + 2: N = 1, 2, 16 cumulative (sweep-r1), N = 54 fresh boot (sweep54-r1).
    rows = []
    for name, counts, first in [('sweep-r1', (1, 2, 16), 'package'), ('sweep54-r1', (54,), 'package')]:
        d, r = run(name, inputs)
        steps = {s['label']: s for s in r['steps']}
        previous = first
        for n in counts:
            assert steps[f'loop-{n}']['passed'] and steps[f'call-{n}']['passed']
            c, b = region(d, f'loop-{n}', 'c2d'), region(d, f'loop-{n}', 'bank2')
            pc, pb = region(d, previous, 'c2d'), region(d, previous, 'bank2')
            base, total = A.u(pc, 16, 2), A.u(c, 16, 2)
            new = [A.entry(c, b, i) for i in range(base, total)]
            assert len(new) == n and all(e['code'] == CODE7 and e['generation'] == 1 for e in new), n
            comp = population(pc, pb, c, b)
            assert comp['ok'], (n, comp)
            after_call = population(c, b, region(d, f'call-{n}', 'c2d'), region(d, f'call-{n}', 'bank2'))
            assert after_call['ok'], n
            rows.append(dict(N=n, run=name, loop_result='NIL', call_result='7', counts=A.counts(c),
                             last_entry=dict(ordinal=total-1, row=new[-1]['raw'],
                                             bank2=hex(new[-1]['bank2_offset']), bytes=new[-1]['code']),
                             new_entries_valid=len(new), comparator=comp,
                             comparator_across_call=after_call['ok']))
            previous = f'call-{n}'
    gates['1'] = dict(status='PASS', rows=[{k: v for k, v in r.items() if k != 'comparator'} for r in rows])
    gates['2'] = dict(status='PASS', rows=[dict(N=r['N'], **r['comparator']) for r in rows])
    # Gate 3 (rebound): exact refusal, symbol value NIL, prior objects and planes identical.
    d, r = run('lambda-r1', inputs)
    steps = {s['label']: s for s in r['steps']}
    assert steps['lambda']['passed'] and steps['lambda']['expected'] == '*** VM: BAD BYTECODE'
    assert steps['symbol-value']['passed'] and steps['recovery']['passed']
    comp = population(region(d, 'boot', 'c2d'), region(d, 'boot', 'bank2'),
                      region(d, 'after-lambda', 'c2d'), region(d, 'after-lambda', 'bank2'))
    assert comp['ok']
    bank2_same = region(d, 'boot', 'bank2') == region(d, 'after-lambda', 'bank2')
    gates['3'] = dict(status='PASS', result='*** VM: BAD BYTECODE', symbol_value='NIL', recovery='42',
                      comparator=comp, bank2_identical=bank2_same)
    # Gate 4: the retiring transient image's own span is zeroed; no persistent span.
    d, r = run('wipe-r1', inputs)
    scratch = r['symbols']['lisp65_c2_phase_scratch']
    assert [(t['before'], t['after']) for t in r['transitions']] == [(0, 0xB5), (0xB5, 0)]
    states = {}
    for label in ('watch-0', 'watch-1'):
        s = A.append_state(region(d, label, 'bank0'), scratch)
        states[label] = dict(code_len=s['code_len'], chip_code_base=hex(s['chip_code_base']),
                             transient=bool(s['rollback_rebuild_header'] & 0x80),
                             staged=s['staged'], committed=s['committed'])
    wipe = states['watch-1']
    assert wipe['transient'] and wipe['staged'] == wipe['committed'] == 1
    assert (wipe['code_len'], wipe['chip_code_base']) == (49, '0xed25')
    pc, pb = region(d, 'package', 'c2d'), region(d, 'package', 'bank2')
    ac, ab = region(d, 'after-loop', 'c2d'), region(d, 'after-loop', 'bank2')
    assert ab[0xED25:0xED56] == bytes(49)
    comp = population(pc, pb, ac, ab)
    assert comp['ok']
    new = A.entry(ac, ab, A.u(ac, 16, 2)-1)
    assert A.u(ac, 16, 2) == A.u(pc, 16, 2)+1 and new['code'] == CODE7
    spans = [(A.entry(ac, ab, i)['bank2_offset'], A.entry(ac, ab, i)['length']) for i in range(A.u(ac, 16, 2))]
    zero_persistent = [o for o, l in spans if ab[o:o+l] == bytes(l)]
    assert zero_persistent == []
    steps = {s['label']: s for s in r['steps']}
    assert steps['loop']['passed'] and steps['call']['passed']
    gates['4'] = dict(status='PASS', transitions=r['transitions'], append_states=states,
                      transient_span='$ED25-$ED55 zero after the form', persistent_spans_zero=0,
                      new_entry=dict(ordinal=A.u(ac, 16, 2)-1, row=new['raw'], bytes=new['code']),
                      comparator=comp, call_result='7',
                      anchor_contrast='anchor r2 loop-1: $ED25-$ED55 left unwiped, persistent $CA2F zeroed')
    # Pre-existing capacity-overflow behaviour, both worlds (not a gate; recorded).
    over = {}
    for name in ('overflow-baseline-r2', 'overflow-r1'):
        d, r = run(name, inputs)
        over[name] = dict(before=A.counts(region(d, 'before-overflow', 'c2d')),
                          after_240s=A.counts(region(d, 'overflow-240s', 'c2d')))
    assert over['overflow-baseline-r2'] == over['overflow-r1']
    value = dict(status='PASS: GATES 1-4 (SEED 2)', binding='d3d5044b', authority='dafc1f47', gates=gates,
                 overflow_observation=dict(
                     worlds=over,
                     note='Cumulative 1/2/16 then 54 evals exceeds the 64-image cap (28 + 54). Anchor and '
                          'Seed 2 behave identically: images stop at 63 and the screen fills with repeated '
                          '*** VM: UNDEFINED FUNCTION without a prompt (900 s in sweep-r1). Pre-existing, '
                          'not introduced by member 2; the interrupted N = 54 rows of the attribution card '
                          'ran the same over-cap sequence.'),
                 superseded=['build/retained-callable-repair-r2-gates-sweep-r1 loop-54 (over cap, kept)',
                             'build/retained-callable-repair-r2-gates-overflow-baseline-r1 (asserted anchor '
                             'call results the anchor cannot give; kept)'],
                 inputs=inputs+[bind(Path(__file__))])
    assert not OUT.exists()
    OUT.write_text(json.dumps(value, indent=2)+'\n')
    print(value['status'], [(r['N'], r['last_entry']['bank2'], r['last_entry']['bytes']) for r in rows])


if __name__ == '__main__':
    main()
