"""Nested-error recovery: offline evaluation of gates 1-5 from the executed emulator dumps.

Reads only the gate receipts and their raw Bank-0 / Bank-2 / C2D dumps; every
dump is verified against its bound SHA first.  No emulator, compiler or link.
Gate rows (reviewer decision eaf59c62: the post-halt diagnostic rows do not
count; these are the g1 gate receipts):

  1  nested-g1       nested eval error at 9 images
  2  overcap-g1      one 60-iteration loop past the cap, then one more refused group
     cumulative-g1   1, 2, 16 (called), 54 past the cap, all callable, one more refused
  3  depth2-g1       depth-2 error, inner-transient error, error-free eval control
     normalpath-g1   PC breakpoint on the PREPARE result: depth-1 error NONE (0),
                     error-free form never, nested error PREPARED (2)
  4  reg-*           the repair card's gate rows (sweep 1/2/16, sweep54, lambda, wipe)
                     and both 23-row usage lanes
  5  RUN/STOP        not injectable on the host (recorded; batched device row)
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/host-lisp'))
import retained_callable_writer_analysis as A  # noqa: E402

OUT = ROOT/'build/nested-error-recovery-r1/gate-analysis.json'
CODE7 = 'b5000002030000010705'
ERROR = '*** UNDEFINED FUNCTION: CAPZZ'
OOM = '*** VM: OUT OF MEMORY'


def bind(path):
    raw = Path(path).read_bytes()
    return dict(path=str(Path(path).resolve().relative_to(ROOT)), bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())


def run(directory, inputs):
    d = ROOT/directory
    r = json.loads((d/'receipt.json').read_text())
    inputs.append(bind(d/'receipt.json'))
    assert r['status'].startswith('CAPTURED'), directory
    assert r['world']['ELF']['sha256'] == '66165507a8e5ad1d857afdd967f9056be2ce7bbccc332d5328e981398078b47b'
    for row in r['captures']:
        for b in list(row['regions'].values()) + [row['screen']]:
            assert bind(ROOT/b['path'])['sha256'] == b['sha256'], b['path']
    assert all(s['passed'] for s in r['steps']), directory
    return d, r


def region(d, label, name):
    return (d/f'{label}-{name}.bin').read_bytes()


def directory(bc, ac):
    n = A.u(bc, 16, 2)
    return {name: bc[off:off+cnt] == ac[off:off+cnt] for name, off, cnt in [
        ('header', 0, 48), ('images', 48, A.u(bc, 12, 2)*32), ('entries', A.u(bc, 30, 2), n*10),
        ('resolutions', A.u(bc, 32, 2), A.u(bc, 20, 2)*2), ('roots', A.u(bc, 34, 2), A.u(bc, 24, 2)*2)]}


def identical(d, a, b):
    p = directory(region(d, a, 'c2d'), region(d, b, 'c2d'))
    same2 = region(d, a, 'bank2') == region(d, b, 'bank2')
    return dict(before=a, after=b, counts=A.counts(region(d, b, 'c2d')), planes=p, bank2_identical=same2,
                ok=all(p.values()) and same2)


def population(bc, bb, ac, ab):
    """Every pre-existing entry (row + code) and the pre-existing planes byte-identical."""
    n = A.u(bc, 16, 2)
    changed = [i for i in range(n) if A.entry(bc, bb, i) != A.entry(ac, ab, i)]
    planes = {name: bc[off:off+cnt] == ac[off:off+cnt] for name, off, cnt in [
        ('header-prefix', 0, 12), ('images', 48, A.u(bc, 12, 2)*32), ('entries', A.u(bc, 30, 2), n*10),
        ('resolutions', A.u(bc, 32, 2), A.u(bc, 20, 2)*2), ('roots', A.u(bc, 34, 2), A.u(bc, 24, 2)*2)]}
    return dict(entries_before=n, entries_after=A.u(ac, 16, 2), changed=changed, planes=planes,
                ok=not changed and all(planes.values()))


def published(d, before, after, count):
    bc, bb = region(d, before, 'c2d'), region(d, before, 'bank2')
    ac, ab = region(d, after, 'c2d'), region(d, after, 'bank2')
    base, total = A.u(bc, 16, 2), A.u(ac, 16, 2)
    new = [A.entry(ac, ab, i) for i in range(base, total)]
    assert len(new) == count and all(e['code'] == CODE7 for e in new), (after, len(new))
    comp = population(bc, bb, ac, ab)
    assert comp['ok'], (after, comp)
    return dict(new_entries=len(new), counts=A.counts(ac),
                last_entry=dict(ordinal=total-1, row=new[-1]['raw'], bank2=hex(new[-1]['bank2_offset']),
                                bytes=new[-1]['code']), comparator=comp)


def ready(r):
    values = {c['label']: c['c2_ready'] for c in r['captures']}
    assert set(values.values()) == {1}, values
    return values


def main():
    assert not OUT.exists()
    inputs, gates = [], {}
    # Gate 1.
    d, r = run('build/nested-error-recovery-gates-nested-g1', inputs)
    steps = {s['label']: s for s in r['steps']}
    assert steps['nested']['expected'] == ERROR and steps['arith']['expected'] == '9'
    rows = [identical(d, 'package', 'after-nested'), identical(d, 'after-nested', 'end')]
    assert all(x['ok'] for x in rows) and A.counts(region(d, 'package', 'c2d'))['images'] == 9
    gates['1'] = dict(status='PASS', form=steps['nested']['form'], result=ERROR, prompt_live=True,
                      c2_ready=ready(r), after='9', comparisons=rows)
    # Gate 2 minimal.
    d, r = run('build/nested-error-recovery-gates-overcap-g1', inputs)
    minimal = published(d, 'package', 'after-min', 54)
    assert minimal['counts']['images'] == 63
    rows = [identical(d, 'after-min', 'after-min-calls'), identical(d, 'after-min-calls', 'after-refused'),
            identical(d, 'after-refused', 'end')]
    assert all(x['ok'] for x in rows)
    gates['2-minimal'] = dict(status='PASS', form="(dotimes (n 60) (eval '(defun capm () 7)))", result=OOM,
                              published_before_refusal=minimal, calls='7', refused_group=OOM,
                              refused_group_directory_and_bank2_unchanged=rows[1]['ok'],
                              comparisons=rows, c2_ready=ready(r))
    # Gate 2 cumulative.
    d, r = run('build/nested-error-recovery-gates-cumulative-g1', inputs)
    previous, loops = 'package', []
    for n in (1, 2, 16):
        row = published(d, previous, f'loop-{n}', n)
        assert population(region(d, f'loop-{n}', 'c2d'), region(d, f'loop-{n}', 'bank2'),
                          region(d, f'call-{n}', 'c2d'), region(d, f'call-{n}', 'bank2'))['ok']
        loops.append(dict(N=n, **row))
        previous = f'call-{n}'
    over = published(d, previous, 'after-54', 35)
    assert over['counts']['images'] == 63
    rows = [identical(d, 'after-54', 'after-54-calls'), identical(d, 'after-54-calls', 'after-refused'),
            identical(d, 'after-refused', 'end')]
    assert all(x['ok'] for x in rows)
    gates['2-cumulative'] = dict(status='PASS', loops=[{k: v for k, v in x.items() if k != 'comparator'} for x in loops],
                                 loop_54=dict(result=OOM, published_before_refusal=35, counts=over['counts'],
                                              last_entry=over['last_entry']),
                                 recalls={'capn1': '7', 'capn2': '7', 'capn16': '7', 'capn54': '7'},
                                 refused_group=OOM, comparisons=rows, c2_ready=ready(r))
    # Gate 3.
    d, r = run('build/nested-error-recovery-gates-depth2-g1', inputs)
    seq = ['package', 'after-depth2', 'after-inner', 'after-normal', 'end']
    rows = [identical(d, a, b) for a, b in zip(seq, seq[1:])]
    assert all(x['ok'] for x in rows)
    d2, r2 = run('build/nested-error-recovery-gates-normalpath-g1', inputs)
    seq2 = ['package', 'after-depth1', 'after-plain', 'after-nested', 'end']
    rows2 = [identical(d2, a, b) for a, b in zip(seq2, seq2[1:])]
    assert all(x['ok'] for x in rows2)
    breaks = {b['label']: b for b in r2['breakpoints']}
    assert breaks['depth1']['hit'] and breaks['depth1']['hit']['result'] == 0
    assert breaks['plain']['hit'] is None
    assert breaks['nested']['hit'] and breaks['nested']['hit']['result'] == 2
    gates['3'] = dict(status='PASS', depth2=dict(result=ERROR, comparisons=rows, c2_ready=ready(r)),
                      normal_path=dict(breakpoint=r2['breakpoint'],
                                       rows={k: dict(form=v['form'], hit=bool(v['hit']),
                                                     result=v['hit'] and v['hit']['result']) for k, v in breaks.items()},
                                       meaning='depth-1 VM-status error: fast path with NONE (old path, no retirement); '
                                               'error-free transient form: no abort; nested error: PREPARED, retired',
                                       comparisons=rows2, c2_ready=ready(r2)))
    # Gate 4: repair-card rows.
    reg = {}
    d, r = run('build/nested-error-recovery-reg-sweep-r1', inputs)
    previous, sweep = 'package', []
    for n in (1, 2, 16):
        row = published(d, previous, f'loop-{n}', n)
        sweep.append(dict(N=n, counts=row['counts'], last_entry=row['last_entry']))
        previous = f'call-{n}'
    d, r = run('build/nested-error-recovery-reg-sweep54-r1', inputs)
    row = published(d, 'package', 'loop-54', 54)
    sweep.append(dict(N=54, counts=row['counts'], last_entry=row['last_entry']))
    reg['sweep'] = sweep
    d, r = run('build/nested-error-recovery-reg-lambda-r1', inputs)
    comp = population(region(d, 'boot', 'c2d'), region(d, 'boot', 'bank2'),
                      region(d, 'after-lambda', 'c2d'), region(d, 'after-lambda', 'bank2'))
    assert comp['ok'] and comp['entries_before'] == 804
    reg['lambda'] = dict(result='*** VM: BAD BYTECODE', symbol_value='NIL', recovery='42', objects=804,
                         bank2_identical=region(d, 'boot', 'bank2') == region(d, 'after-lambda', 'bank2'))
    d, r = run('build/nested-error-recovery-reg-wipe-r1', inputs)
    scratch = r['symbols']['lisp65_c2_phase_scratch']
    assert [(t['before'], t['after']) for t in r['transitions']] == [(0, 0xB5), (0xB5, 0)]
    s = A.append_state(region(d, 'watch-1', 'bank0'), scratch)
    assert (s['code_len'], s['chip_code_base']) == (49, 0xED25) and s['rollback_rebuild_header'] & 0x80
    ac, ab = region(d, 'after-loop', 'c2d'), region(d, 'after-loop', 'bank2')
    assert ab[0xED25:0xED56] == bytes(49)
    assert population(region(d, 'package', 'c2d'), region(d, 'package', 'bank2'), ac, ab)['ok']
    spans = [(A.entry(ac, ab, i)['bank2_offset'], A.entry(ac, ab, i)['length']) for i in range(A.u(ac, 16, 2))]
    assert [o for o, l in spans if ab[o:o+l] == bytes(l)] == []
    reg['wipe'] = dict(code_len=49, chip_code_base='0xed25', transient_span_zero=True, persistent_spans_zero=0,
                       call='7')
    usage = {}
    for role in ('baseline', 'candidate'):
        p = ROOT/f'build/nested-error-recovery-usage-{role}-r1/receipt.json'
        inputs.append(bind(p))
        u = json.loads(p.read_text())
        assert u['status'] == 'PASS' and len(u['rows']) == 23
        assert u['rows'][18]['expected'] == '*** VM: BAD BYTECODE'
        usage[role] = dict(status=u['status'], rows=23, row_18=u['rows'][18]['expected'])
    reg['usage'] = usage
    gates['4'] = dict(status='PASS', **reg)
    gates['5'] = dict(status='NOT INJECTABLE ON THE HOST; BATCHED DEVICE ROW',
                      reason='The observer queues HWA keyboard events (~keyevent/~typeone); the product reads '
                             'RUN/STOP from the $D613 keyboard-matrix row 7 bit 7 in its IRQ '
                             '(c2_kernal_irq_base.s), which the Xemu monitor cannot drive. Reviewer decision eaf59c62.')
    value = dict(status='PASS: GATES 1-4; GATE 5 BATCHED DEVICE ROW', binding='44c021ee', decision='eaf59c62',
                 authority='90b5f9f2', gates=gates,
                 superseded=['build/nested-error-recovery-gates-nested-r1 and -depth2-r1: post-halt diagnostics '
                             '(kept; not gate receipts)'],
                 inputs=inputs+[bind(Path(__file__))])
    OUT.write_text(json.dumps(value, indent=2)+'\n')
    print(value['status'], [(x['N'], x['last_entry']['bank2']) for x in sweep],
          gates['2-cumulative']['loop_54']['last_entry'], gates['2-minimal']['published_before_refusal']['last_entry'])


if __name__ == '__main__':
    main()
