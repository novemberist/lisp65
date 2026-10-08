#!/usr/bin/env python3
"""Host oracles and the timing verdict for the NEW 2.5.5 emulator rows (no emulator, no device, no product link).

Successor in role of c254_row_oracles.py (which stays byte-identical; the 2.5.4 rows are run unchanged as
regression and keep their own oracle receipt).  2.5.5 adds two row groups (c255_rows_20261006.json):

  l2       behaviour rows that lever L2 could break (the editor no longer stores the buffer before every key; it
           stores once at entry, and RUN/STOP safety rests on the E3 publication alone): edit several buffers,
           switch, exit, re-enter, save / eval a buffer that was left by a switch or by an abort.
  typing   the MEASURED per-key cost row (method of build/card-254-ide-typing-r1/keycost.py) with a pass rule.

Actions
  oracles  --preflight <c255 preflight dir> --table <rows json> --out <new dir under build/>
           Runs every `expected.script` of the l2 rows through the REAL entry (ide NAME) of the product IDE world
           the preflight emitted (refused unless the compiled blob is the emitted ide image and the pinned one),
           and through the same entry of the 2.5.4 product IDE world (the baseline preflight).  Records what the
           readers of the stored buffers see after every session -- (ide-buffers), ide-buffer-lines after
           %ide-resume-buffer (re-entry), %ide-buffer-source (what save / eval-buffer / compile read), the point --
           and, for rows with `prefix_rule`, the same after every prefix of the last session's keys (the j-1 / j
           rule of the E3 rows).  Writes one write-once receipt.json.
           Preparation only: --world-suite / --world-blob instead of --preflight (a stand-in world; the receipt
           says so and `table` refuses it unless --allow-stand-in is given).
  table    --draft <rows json> --oracle <receipt.json> --out <rows json>
           The row table with every l2 expectation replaced by / checked against the oracle and marked
           HOST-EXECUTED; what the host cannot give stays NOT-DERIVED with its reason.
  timing   --seed <keycost results.json> --control <keycost results.json> --table <rows json> [--out <json>]
           The verdict of the typing row: PASS / REVIEW / FAIL with every rule evaluated.  Pure arithmetic.
  selftest synthetic negative controls of the timing verdict and of the script runner's bookkeeping.

The host VM has no device heap limit and no native loader; where RUN/STOP really lands on the device, the
screen after re-entry, the return value of a save and the value an eval-buffer prints are NOT derived here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
HERE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE_DIR))

EXECUTED, NOT_DERIVED = 'HOST-EXECUTED', 'NOT-DERIVED'
FORMAT = 'card255-rows-v1'
ORACLE_FORMAT = 'card255-row-oracles-v1'
CX, Q, NEXT, PREV, RET, DEL = 24, 113, 14, 16, 13, 20
READERS = ('(defun h-find (name) (%ide-buffers-find name (%ide-buffers-alist)))',
           '(defun h-source (buf) (%ide-buffer-source buf))',
           '(defun h-lines (buf) (ide-buffer-lines buf))',
           '(defun h-names () (ide-buffers))')
MHZ = 40.5


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def once(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(text)


def load_json(path):
    return json.loads(Path(path).read_text())


# ------------------------------------------------------------------ script runner (host)
def _modules():
    import bytecode_p0 as B
    import c254_e3_product as E3
    return B, E3


def make_vm_class():
    B, E3 = _modules()

    class ScriptVM(E3._VM):
        """One editor VM whose key queue holds key CODES.  Blocking read-key on an empty queue = RUN/STOP at the
        idle editor (the session ends by an abort); poll-key on an empty queue returns NIL."""

        def _callprim(self, p, n, stack, **kw):
            if p == 14:
                return self.key(self.pending.pop(0)) if self.pending else B.NIL
            if p == 13:
                if self.pending:
                    return self.key(self.pending.pop(0))
                raise E3.Stop('queue empty at the blocking read-key')
            return B.P0VM._callprim(self, p, n, stack, **kw)
    return ScriptVM


def strings(v, lst):
    B, _ = _modules()
    out = []
    while lst != B.NIL:
        out.append(v.heap.string_to_text(v.heap.car(lst)))
        lst = v.heap.cdr(lst)
    return out


def snapshot(v):
    """What the readers of the stored buffers see."""
    B, _ = _modules()
    out = dict(names=strings(v, v.call('h-names')), buffers={})
    for name in out['names']:
        buf = v.call('h-find', v.text(name))
        point = v.call('ide-buffer-point', buf)
        out['buffers'][name] = dict(lines=strings(v, v.call('h-lines', buf)),
                                    source=v.py(v.call('h-source', buf)),
                                    point=[B.fixval(v.heap.car(point)), B.fixval(v.heap.cdr(point))])
    return out


def run_script(world, script, upto=None):
    """Run the sessions of one row.  script = [dict(ide=NAME, keys=[codes], end='exit'|'abort-idle'), ...].
    upto = (session index, key count): stop feeding keys there (prefix rule).  Returns ends + snapshots."""
    _, E3 = _modules()
    v = make_vm_class()(SimpleNamespace(w=world), [])
    ends, shots = [], []
    for i, step in enumerate(script):
        keys = list(step['keys'])
        if upto is not None and i == upto[0]:
            keys = keys[:upto[1]]
        v.pending = list(keys)
        try:
            v.call('ide', v.text(step['ide']))
            end = 'exit'
        except E3.Stop:
            end = 'abort-idle'
        assert not v.pending, ('keys left in the queue', step['ide'], len(v.pending))
        ends.append(end)
        shots.append(snapshot(v))
        if upto is not None and i == upto[0]:
            break
    return dict(ends=ends, after=shots)


def check_script(row):
    script = row['expected']['script']
    assert script and all(set(s) == {'ide', 'keys', 'end'} and s['end'] in ('exit', 'abort-idle') and
                          all(isinstance(k, int) and 0 < k < 256 for k in s['keys']) for s in script), ('script shape', row['id'])
    for s in script:
        tail = s['keys'][-2:] == [CX, Q]
        assert tail == (s['end'] == 'exit'), ('a session ends by C-x q exactly when its end is exit', row['id'], s['ide'])
    return script


def row_oracle(row, world, control):
    script = check_script(row)
    got = run_script(world, script)
    assert got['ends'] == [s['end'] for s in script], ('session end', row['id'], got['ends'])
    result = dict(script=script, ends=got['ends'], after=got['after'])
    if control is not None:
        base = run_script(control, script)
        result['equal_to_254'] = base == got
        if not result['equal_to_254']:
            result['in_254'] = base
    if row['expected'].get('prefix_rule'):
        last = len(script) - 1
        result['after_m_keys_of_last_session'] = [run_script(world, script, upto=(last, m))['after'][-1]
                                                  for m in range(len(script[last]['keys']) + 1)]
    return result


def world_of(suite, blob, pin=None):
    _, E3 = _modules()
    w = E3.world(str(suite), E3.DRIVERS + READERS)
    raw = Path(blob).read_bytes()
    identity = dict(suite=dict(path=str(suite), sha256=sha(Path(suite).read_bytes())), world_blob_sha256=w['blob_sha256'],
                    world_blob_bytes=w['blob_bytes'], emitted=dict(path=str(blob), sha256=sha(raw), bytes=len(raw)))
    identity['equal'] = (w['blob_sha256'], w['blob_bytes']) == (identity['emitted']['sha256'], identity['emitted']['bytes'])
    assert identity['equal'], ('oracle IDE world is not the emitted ide image', identity)
    if pin is not None:
        assert (w['blob_sha256'], w['blob_bytes']) == tuple(pin), ('oracle IDE world is not the pinned ide image', identity)
    return w, identity


def oracles(out, table_path, preflight=None, world_suite=None, world_blob=None):
    import c255_config as CFG
    root = CFG.ROOT
    out = out.resolve()
    assert out.is_relative_to(root / 'build') and not out.exists(), 'oracle output is a new directory below build/'
    table = load_json(table_path)
    assert table['format'] == FORMAT
    stand_in = preflight is None
    if stand_in:
        assert world_suite and world_blob, 'give --preflight, or --world-suite and --world-blob (preparation)'
        suite, blob, pre_binding = Path(world_suite), Path(world_blob), None
    else:
        pre = Path(preflight)
        receipt = load_json(pre / 'receipt.json')
        assert receipt['status'] == 'PASS' and tuple(receipt['candidate_blobs']['ide']) == tuple(CFG.CANDIDATE_BLOBS['ide'])
        suite, blob = pre / 'emission/ide/suite.json', pre / 'emission/ide/ide.blob.bin'
        pre_binding = dict(path=str((pre / 'receipt.json').resolve().relative_to(root)), sha256=sha((pre / 'receipt.json').read_bytes()))
    world, identity = world_of(suite, blob, CFG.CANDIDATE_BLOBS['ide'])
    base = root / CFG.BASE_PREFLIGHT
    control, control_identity = world_of(base / 'emission/ide/suite.json', base / 'emission/ide/ide.blob.bin')
    rows = {}
    for row in table['rows']:
        if row['group'] != 'l2':
            continue
        rows[row['id']] = row_oracle(row, world, control)
        print('l2 row %s: ends %s equal_to_254 %s' % (row['id'], rows[row['id']]['ends'], rows[row['id']]['equal_to_254']), flush=True)
    result = dict(format=ORACLE_FORMAT, status='PASS', stand_in_world=stand_in, preflight=pre_binding,
                  world_identity=identity, control_identity=control_identity,
                  table=dict(path=str(Path(table_path)), sha256=sha(Path(table_path).read_bytes())),
                  tool=dict(sha256=sha(Path(__file__).read_bytes())), rows=rows,
                  all_equal_to_254=all(r['equal_to_254'] for r in rows.values()),
                  note='texts are what the readers of the stored buffers return on the host VM; the screen, the '
                       'device abort position and native services are not modelled')
    once(out / 'receipt.json', json.dumps(result, indent=1) + '\n')
    return dict(status='PASS', rows=len(rows), all_equal_to_254=result['all_equal_to_254'], stand_in_world=stand_in)


def apply_table(draft_path, oracle_path, out_path, allow_stand_in=False):
    table, oracle = load_json(draft_path), load_json(oracle_path)
    assert table['format'] == FORMAT and oracle['format'] == ORACLE_FORMAT and oracle['status'] == 'PASS'
    assert allow_stand_in or not oracle['stand_in_world'], 'the oracle ran on a stand-in world (preparation only)'
    marks = {EXECUTED: 0, NOT_DERIVED: 0}
    for row in table['rows']:
        exp = row['expected']
        if row['group'] != 'l2':
            continue
        got = oracle['rows'][row['id']]
        assert got['script'] == exp['script'], ('the oracle ran another script', row['id'])
        final = got['after'][-1]
        exp['stored_after_each_session'] = got['after']
        exp['final'] = final
        if 'after_m_keys_of_last_session' in got:
            exp['after_m_keys_of_last_session'] = got['after_m_keys_of_last_session']
        exp['equal_to_254'] = got['equal_to_254']
        exp['derivation'] = dict(mark=EXECUTED, world='projected product IDE image, real (ide NAME) entry, real loop',
                                 what='(ide-buffers), lines after re-entry, source text, point after every session',
                                 not_derived='screen layout, where the device aborts, native services')
        marks[EXECUTED] += 1
        for check in exp.get('checks', []):
            kind = check['kind']
            if kind in ('reenter-screen', 'saved-file'):
                want = final['buffers'][check['buffer']]['source']
                assert check.get('text') in (None, want), ('draft text differs from the oracle', row['id'], check, want)
                check['text'] = want
                check['derivation'] = dict(mark=EXECUTED, what='source text the reader returns')
                marks[EXECUTED] += 1
            elif kind == 'buffer-names':
                assert check.get('names') in (None, final['names']), ('draft names differ from the oracle', row['id'])
                check['names'] = final['names']
                check['derivation'] = dict(mark=EXECUTED, what='(ide-buffers)')
                marks[EXECUTED] += 1
            else:
                assert kind in ('repl-value', 'save-result', 'stop-text'), ('unknown check', kind)
                check['derivation'] = dict(mark=NOT_DERIVED, why=check.get('why', 'native service / emulator transport / compiler path'))
                marks[NOT_DERIVED] += 1
    table['oracle'] = dict(receipt=dict(path=str(oracle_path), sha256=sha(Path(oracle_path).read_bytes())),
                           world_identity=oracle['world_identity'], preflight=oracle['preflight'],
                           stand_in_world=oracle['stand_in_world'], all_l2_rows_equal_to_254=oracle['all_equal_to_254'], marks=marks)
    once(Path(out_path), json.dumps(table, indent=1) + '\n')
    return dict(status='PASS', marks=marks, all_l2_rows_equal_to_254=oracle['all_equal_to_254'])


# ------------------------------------------------------------------ timing verdict (pure)
def points(samples):
    """keycost samples -> {(label, n): stats}.  Single keys: median over the samples WITHOUT a collection."""
    groups = {}
    for s in samples:
        groups.setdefault((s['label'], s.get('length', s.get('count'))), []).append(s)
    out = {}
    for key, rows in groups.items():
        clean = [r['cycles'] for r in rows if not r['gc']]
        row = dict(samples=len(rows), gc_samples=sum(1 for r in rows if r['gc']), rendered=all(r['rendered'] for r in rows),
                   median=statistics.median(clean) if clean else None, clean=clean)
        if 'burst' in key[0]:
            row.update(median=statistics.median(r['cycles'] for r in rows),
                       step=statistics.median(g for r in rows for g in r['take_gaps']) if any(r['take_gaps'] for r in rows) else None,
                       render_states=sorted({r['render_states_seen'] for r in rows}))
        out[key] = row
    return out


def timing_verdict(seed_samples, control_samples, rule):
    """Every rule of the typing row.  Returns dict(status, rules=[...]).  FAIL beats REVIEW beats PASS."""
    s, c = points(seed_samples), points(control_samples)
    rows = []

    def add(name, ok, detail, kind='rule'):
        rows.append(dict(rule=name, kind=kind, ok=bool(ok), **detail))

    def med(table, label, n):
        row = table.get((label, n))
        return row['median'] if row else None

    for name, label, n, limit in rule['ratio_max']:
        a, b = med(s, label, n), med(c, label, n)
        add(name, a is not None and b and a <= limit * b, dict(seed=a, control=b, ratio=round(a / b, 4) if a and b else None, max=limit))
    for name, hi, lo, limit in rule['growth_max']:
        a, b = med(s, *hi), med(s, *lo)
        add(name, a is not None and b and (a - b) / b <= limit, dict(high=a, low=b, growth=round((a - b) / b, 4) if a and b else None, max=limit))
    for name, label, n, tolerance in rule['unchanged']:
        a, b = med(s, label, n), med(c, label, n)
        add(name, a is not None and b and abs(a / b - 1) <= tolerance, dict(seed=a, control=b, tolerance=tolerance))
    for name, label, n, cycles, tolerance in rule['control_reference']:
        b = med(c, label, n)
        add(name, b is not None and abs(b / cycles - 1) <= tolerance, dict(control=b, reference=cycles, tolerance=tolerance))
    singles = [k for k in s if k[0].startswith('ide-') and 'burst' not in k[0]]
    add('samples', singles and all(s[k]['samples'] >= rule['min_samples'] and s[k]['median'] is not None for k in singles),
        dict(points=len(singles), min_samples=rule['min_samples']))
    add('every key rendered', all(r['rendered'] for r in s.values()), dict(points=len(s)))
    # A single outlier (the first key after entering the editor costs more once) must not decide: the median is
    # trusted when at least `min_stable` samples without a collection lie within `spread_max` of it.
    def stable(row):
        return sum(1 for x in row['clean'] if abs(x / row['median'] - 1) <= rule['spread_max']) if row['median'] else 0
    loose = sorted('%s@%s' % k for t in (s, c) for k in t if k[0].startswith('ide-') and 'burst' not in k[0] and stable(t[k]) < rule['min_stable'])
    add('stable samples without a collection', not loose, dict(unstable=loose, within=rule['spread_max'], min_stable=rule['min_stable']))
    need = {tuple(p) for p in rule['required_points']}
    add('all points measured', need <= set(s) and need <= set(c), dict(missing=sorted('%s@%s' % k for k in need - (set(s) & set(c)))))
    gs, gc = (sum(t[k]['gc_samples'] for k in t if k[0].startswith('ide-') and 'burst' not in k[0]) for t in (s, c))
    add('collections in single editor keys', gs <= gc, dict(seed=gs, control=gc))
    for name, label, n in rule['burst']:
        a, b = s.get((label, n)), c.get((label, n))
        ok = bool(a and b and a['step'] is not None and b['step'] is not None and a['step'] <= b['step'] and a['render_states'] == [1])
        add(name, ok, dict(seed_step=a and a['step'], control_step=b and b['step'], render_states=a and a['render_states']))
    for name, label, n, cycles in rule['prediction']:
        a = med(s, label, n)
        off = None if a is None else a / cycles - 1
        add(name, off is not None and abs(off) <= rule['prediction_tolerance'],
            dict(seed=a, predicted=cycles, deviation=None if off is None else round(off, 4), tolerance=rule['prediction_tolerance'],
                 ms=None if a is None else round(a / (MHZ * 1000), 1)), kind='review')
    failed = [r['rule'] for r in rows if not r['ok'] and r['kind'] == 'rule']
    review = [r['rule'] for r in rows if not r['ok'] and r['kind'] == 'review']
    return dict(status='FAIL' if failed else 'REVIEW' if review else 'PASS', failed=failed, review=review, rules=rows)


def timing(seed_path, control_path, table_path, out_path=None):
    table = load_json(table_path)
    row = next(r for r in table['rows'] if r['id'] == 'typing-key-cost')
    seed, control = load_json(seed_path), load_json(control_path)
    for label, run, want in (('seed', seed, row['expected']['worlds']['seed']), ('control', control, row['expected']['worlds']['control'])):
        world = run['notes']['world']
        assert not run['notes'].get('error'), (label + ' run recorded an error', run['notes']['error'][-300:])
        for key in ('medium_sha', 'elf_sha'):
            assert want[key] is None or world[key] == want[key], (label + ' run measured another world', key, world[key])
    result = timing_verdict(seed['samples'], control['samples'], row['expected']['rule'])
    result.update(seed=dict(path=str(seed_path), sha256=sha(Path(seed_path).read_bytes()), world=seed['notes']['world']),
                  control=dict(path=str(control_path), sha256=sha(Path(control_path).read_bytes()), world=control['notes']['world']),
                  table=dict(path=str(table_path), sha256=sha(Path(table_path).read_bytes())))
    if out_path:
        once(Path(out_path), json.dumps(result, indent=1) + '\n')
    return result


# ------------------------------------------------------------------ selftest (synthetic)
def _samples(values, burst_step=2400000, gc_keys=0, renders=1):
    out = []
    for (label, n), cycles in values.items():
        for rep in range(7):
            out.append(dict(label=label, length=n, cycles=cycles + rep * 40, rendered=True, gc=rep < gc_keys and label == 'ide-insert' and n == 1,
                            gc_runs=0, rep=rep))
    for count in (8, 32):
        for rep in range(5):
            out.append(dict(label='ide-burst%d' % count, count=count, cycles=burst_step * count, per_key=burst_step,
                            take_gaps=[burst_step] * (count - 1), render_states_seen=renders, rendered=True, gc=True, gc_runs=1, rep=rep))
    return out


def _complete(values, required, single):
    """Synthetic value for every required single-key point that the short table does not name."""
    out = dict(values)
    for label, n in required:
        if 'burst' not in label and (label, n) not in out:
            out[(label, n)] = single['backspace' if 'backspace' in label else 'insert']
    return out


def selftest(rule):
    control = {('ide-insert', 1): 5028089, ('ide-insert', 10): 5278359, ('ide-insert', 20): 5552668, ('ide-insert', 39): 6073800,
               ('ide-backspace', 20): 4846841, ('ide-return30', 30): 18745612, ('ide-join30', 30): 18785152,
               ('ide-insert-line20', 10): 6215326, ('repl-insert', 20): 168822, ('repl-backspace', 20): 717818}
    seed = {('ide-insert', 1): 2310180, ('ide-insert', 10): 2313455, ('ide-insert', 20): 2313455, ('ide-insert', 39): 2313455,
            ('ide-backspace', 20): 2466245, ('ide-return30', 30): 16855138, ('ide-join30', 30): 16673064,
            ('ide-insert-line20', 10): 2313455, ('repl-insert', 20): 168822, ('repl-backspace', 20): 717818}
    control = _complete(control, rule['required_points'], dict(insert=5552668, backspace=4846841))
    seed = _complete(seed, rule['required_points'], dict(insert=2313455, backspace=2466245))
    good = timing_verdict(_samples(seed, 1500000, gc_keys=1), _samples(control, gc_keys=2), rule)
    assert good['status'] == 'PASS', good
    rejected = []

    def expect(name, status, seed_values=seed, control_values=control, **kw):
        r = timing_verdict(_samples(seed_values, **{'burst_step': 1500000, **kw}), _samples(control_values, gc_keys=2), rule)
        assert r['status'] == status, (name, r['status'], r['failed'], r['review'])
        rejected.append('timing: ' + name)
    expect('no gain (2.5.4 measured against itself)', 'FAIL', seed_values=control, burst_step=2400000)
    expect('insert only 30 % cheaper', 'FAIL', seed_values={**seed, ('ide-insert', 20): int(5552668 * 0.70)})
    expect('Backspace only 20 % cheaper', 'FAIL', seed_values={**seed, ('ide-backspace', 20): int(4846841 * 0.80)})
    expect('Return slower than 2.5.4', 'FAIL', seed_values={**seed, ('ide-return30', 30): 19000000})
    expect('cost grows with the column', 'FAIL', seed_values={**seed, ('ide-insert', 39): int(2310180 * 1.08)})
    expect('cost grows with the row', 'FAIL', seed_values={**seed, ('ide-insert-line20', 10): int(2313455 * 1.08)})
    expect('REPL key cost moved', 'FAIL', seed_values={**seed, ('repl-insert', 20): 175000})
    expect('control is not the 2.5.4 medium (method drift)', 'FAIL', control_values={**control, ('ide-insert', 20): 5479436})
    expect('a point is missing', 'FAIL', seed_values={k: v for k, v in seed.items() if k != ('ide-join30', 30)})
    expect('burst step slower than 2.5.4', 'FAIL', burst_step=2500000)
    expect('more than one render per burst', 'FAIL', renders=2)
    expect('more collections than 2.5.4', 'FAIL', gc_keys=3)
    expect('gain real but far from the prediction (model wrong)', 'REVIEW', seed_values={**seed, ('ide-insert', 20): 2900000})
    bad = _samples(seed, 1500000)
    bad[0]['rendered'] = False
    assert timing_verdict(bad, _samples(control, gc_keys=2), rule)['status'] == 'FAIL'
    rejected.append('timing: a key that was not rendered')
    wide = _samples(seed, 1500000)
    wide[1]['cycles'] = int(wide[1]['cycles'] * 1.75)                    # ONE outlier: the median stands
    assert timing_verdict(wide, _samples(control, gc_keys=2), rule)['status'] == 'PASS'
    for i in range(7):
        wide[i]['cycles'] = int(wide[0]['cycles'] * (1 + 0.03 * i))      # scattered samples: no median to trust
    assert 'stable samples without a collection' in timing_verdict(wide, _samples(control, gc_keys=2), rule)['failed']
    rejected.append('timing: scattered samples at a point (fewer than three within 2 % of the median)')
    few = [x for x in _samples(seed, 1500000) if x.get('rep', 0) < 5 or 'burst' in x['label']]
    assert 'samples' in timing_verdict(few, _samples(control, gc_keys=2), rule)['failed']
    rejected.append('timing: fewer than seven samples')
    # script bookkeeping
    for name, script in (('exit without C-x q', [dict(ide='a', keys=[97], end='exit')]),
                         ('abort session that ends by C-x q', [dict(ide='a', keys=[97, CX, Q], end='abort-idle')]),
                         ('key code out of range', [dict(ide='a', keys=[300, CX, Q], end='exit')]),
                         ('empty script', [])):
        try:
            check_script(dict(id='x', expected=dict(script=script)))
        except AssertionError:
            rejected.append('script: ' + name)
        else:
            raise AssertionError('negative survived: ' + name)
    return rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('oracles')
    p.add_argument('--preflight', type=Path); p.add_argument('--world-suite', type=Path); p.add_argument('--world-blob', type=Path)
    p.add_argument('--table', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('table')
    p.add_argument('--draft', type=Path, required=True); p.add_argument('--oracle', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True); p.add_argument('--allow-stand-in', action='store_true')
    p = sub.add_parser('timing')
    p.add_argument('--seed', type=Path, required=True); p.add_argument('--control', type=Path, required=True)
    p.add_argument('--table', type=Path, required=True); p.add_argument('--out', type=Path)
    p = sub.add_parser('selftest')
    p.add_argument('--table', type=Path, default=HERE_DIR / 'c255_rows_20261006.json')
    args = parser.parse_args()
    if args.action == 'oracles':
        result = oracles(args.out, args.table, args.preflight, args.world_suite, args.world_blob)
    elif args.action == 'table':
        result = apply_table(args.draft, args.oracle, args.out, args.allow_stand_in)
    elif args.action == 'timing':
        result = timing(args.seed, args.control, args.table, args.out)
        result = dict(status=result['status'], failed=result['failed'], review=result['review'],
                      rules=[dict(rule=r['rule'], ok=r['ok']) for r in result['rules']])
    else:
        rule = next(r for r in load_json(args.table)['rows'] if r['id'] == 'typing-key-cost')['expected']['rule']
        result = dict(status='PASS', negative_controls=selftest(rule))
    print(json.dumps(result, indent=1))
    sys.exit(0 if result['status'] in ('PASS', 'REVIEW') else 2)


if __name__ == '__main__':
    import os
    assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    main()
