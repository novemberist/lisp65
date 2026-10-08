#!/usr/bin/env python3
"""2.5.5 product-world E3 check: accepted-edit persistence under RUN/STOP, with INDEPENDENT reference texts.

Successor of c254_e3_product.py (committed, imported, never edited: worlds, VM, cases, point sets, shapes, the
j-1 / j rule and the strict rule are its own).  What changes, and why:

The 2.5.4 sweep took its reference texts exp[k] (buffer text after k keys) from the swept world itself: a
session of the same shape with keys[:k] and no abort, then re-entry.  In the `run` shape that session ends at
the blocking read-key, and what re-entry finds there was the copy the loop stored before every key.  2.5.5
(lever L2) removes that store.  A world without the E3 publication then stores nothing during a run, its `run`
references all become the initial text, and every abort point "matches": on the 2.5.5 candidate the control
without the publication showed 0 violations in the `run` shape although it loses every finished step, even at
the idle prompt (build/card-255-typing-r1/control-analysis.json).  A sweep must not be able to do that.

  1. Reference texts are independent of every store of the swept world: the keys are stepped through ide-step on
     a state, and the text is read from that STATE, never from the stored buffers.  (Multi-buffer cases compare
     all stored buffers; there the stepped state is stored once, explicitly, after the last key.)
  2. Product world: for every case the texts that a no-abort session of each shape leaves for re-entry must
     EQUAL the independent references (`drain` session = `run` session = stepped state).
  3. The control without the publication must fail in BOTH shapes, each with at least CONTROL_MIN_SHARE of that
     shape's abort points violated.  A control whose violations vanish in a shape is a failure of this tool.
  4. Named regression point `abc-after-last-poll`: "abc" typed into an empty buffer through the real loop, abort
     20 instructions after the last (empty) poll.  Product world: re-entry shows "abc".  Control without the
     publication: it does not.
The no-copy control keeps its 2.5.4 rule (violations > 0, only in cases with a Return).

Usage as a library: run(suite_path, out, mode=..., emitted_blob=..., seams=...) -> receipt dict.
        c255_e3_product.py            selftest of the verdict (synthetic; no world is compiled)
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import c254_e3_product as E3     # noqa: E402

B = E3.B
CONTROL_MIN_SHARE = 0.5
REGRESSION = dict(name='abc-after-last-poll', keys='abc', initial=[''], after_last_poll=20, text='abc')
SHAPES = E3.SHAPES


class Sweep(E3.Sweep):
    def reference(self, keys, initial, k):
        """Text after k keys, read from the stepped state (no drain, no loop, no stored buffer)."""
        v = self.vm([])
        v.heap.set_symbol_value(v.heap.intern('ide-event-command'), B.NIL)
        _name, buf = self.make_buffer(v, initial)
        state = v.call('ide-make-state', buf)
        for ch in keys[:k]:
            state = v.call('ide-step', state, v.key(ord(ch)))
        if self.allbuf:
            v.call('h-persist', state)
            return self.all_text(v)
        return self.text_of(v, v.call('ide-state-buffer', state))

    def case(self, shape, label, keys, initial, points_mode, equivalence=False):
        exp = [self.reference(keys, initial, k) for k in range(len(keys) + 1)]
        own = [self.session(shape, keys[:k], initial)['text'] for k in range(len(keys) + 1)]
        full = self.session(shape, keys, initial)
        poll = self.session(shape, keys, initial, stop_at_poll=True)
        total, polls = full['steps'], full['polls']
        points = set(range(1, total + 1, max(1, total // E3.GRID)))
        for i, ch in enumerate(keys):
            if ch == '\r' and i + 1 < len(polls):
                points.update(range(max(1, polls[i] - 2), min(total, polls[i + 1] + 3) + 1))
            if i < len(polls):
                points.update(range(max(1, polls[i] - 3), min(total, polls[i] + 4)))
        if shape == 'run':
            last = full['all_polls'][-1] if full['all_polls'] else polls[-1]
            points.update(range(max(1, last - 3), min(total, last + 40)))
            points.update(range(max(1, total - 60), total))
        lib_points = set(p for p in points if p <= total - (0 if shape == 'drain' else 1))
        points = set(range(1, total + (1 if shape == 'drain' else 0))) if points_mode == 'all' else lib_points
        results = self.sweep_once(shape, keys, initial, True if points_mode == 'all' else points)
        assert set(results) == points, (len(results), len(points), sorted(points - set(results))[:5])
        equiv = None
        if equivalence:
            probe = sorted(points)[::max(1, len(points) // 40)]
            diff = [n for n in probe if (lambda r: (r['accepted'], r['floor'], r['text']))(
                self.session(shape, keys, initial, stop_at_step=n)) != results[n]]
            assert not diff, ('snapshot sweep differs from the re-run method', shape, label, diff[:5])
            equiv = dict(points=len(probe), differences=0)
        bad, bad_strict, kept, lib_bad = [], [], {}, 0
        for n in sorted(points):
            j, f, text = results[n]
            k = exp.index(text) if text in exp else None
            if text in (exp[max(j - 1, 0)], exp[j]):
                kept[exp.index(text)] = kept.get(exp.index(text), 0) + 1
            else:
                bad.append(dict(step=n, accepted=j, floor=f, matched_k=k, text=text))
                lib_bad += n in lib_points
            if not any(text == exp[i] for i in range(f, j + 1)):
                bad_strict.append(dict(step=n, accepted=j, floor=f, matched_k=k, text=text))
        return dict(shape=shape, keys=len(keys), has_return='\r' in keys, steps=total, expected_final=exp[-1],
                    own_references_equal_independent=own == exp,
                    first_own_difference=next((dict(k=i, independent=a, own=b) for i, (a, b) in enumerate(zip(exp, own)) if a != b), None),
                    no_abort_ok=full['text'] == exp[-1], poll_abort_ok=poll['text'] == exp[-1],
                    sweep_points=len(points), lib_point_set=len(lib_points), lib_point_set_violations=lib_bad,
                    sweep_violations=len(bad), strict_violations=len(bad_strict),
                    resumed_k_histogram={str(k): kept[k] for k in sorted(kept)},
                    first_violations=bad[:3], last_violation=bad[-1] if bad else None, snapshot_equivalence=equiv)

    def regression_point(self):
        """The named point: abort a fixed distance after the last poll of the real loop."""
        keys, initial = REGRESSION['keys'], REGRESSION['initial']
        full = self.session('run', keys, initial)
        n = full['all_polls'][-1] + REGRESSION['after_last_poll']
        r = self.session('run', keys, initial, stop_at_step=n)
        return dict(name=REGRESSION['name'], abort_at_instruction=n, keys_accepted=r['accepted'], text=r['text'],
                    expected=REGRESSION['text'], kept=r['accepted'] == len(keys) and r['text'] == REGRESSION['text'],
                    text_at_idle=full['text'], kept_at_idle=full['text'] == REGRESSION['text'])

    def run(self, cases, points_mode, log, equivalence=False):
        result = super().run(cases, points_mode, log, equivalence)
        rows = result['summary']
        result['by_shape'] = {shape: dict(points=sum(r['sweep_points'] for r in rows.values() if r['shape'] == shape),
                                          violations=sum(r['sweep_violations'] for r in rows.values() if r['shape'] == shape),
                                          strict_violations=sum(r['strict_violations'] for r in rows.values() if r['shape'] == shape))
                              for shape in SHAPES}
        result['references_independent_equal'] = all(r['own_references_equal_independent'] for r in rows.values())
        result['regression_point'] = None if self.allbuf else self.regression_point()
        return result


def verdict(runs, deltas):
    """The 2.5.4 rule plus the three rules of this successor.  Returns the list of problems (empty = PASS)."""
    problems = E3.verdict(runs, deltas)
    for name, r in runs.items():
        key = name.split(':')[0]
        if key == 'A':
            if not r['references_independent_equal']:
                problems.append(name + ': a no-abort session of the product world does not leave the independent reference text')
            if r['regression_point'] is not None and not (r['regression_point']['kept'] and r['regression_point']['kept_at_idle']):
                problems.append(name + ': regression point ' + REGRESSION['name'] + ' lost in the product world')
        elif key == 'noA':
            for shape, t in r['by_shape'].items():
                if t['points'] <= 0 or t['violations'] < CONTROL_MIN_SHARE * t['points']:
                    problems.append('%s: the control without the publication fails at only %d of %d points in the %s shape '
                                    '(minimum %d %%): the sweep does not see the loss there'
                                    % (name, t['violations'], t['points'], shape, round(100 * CONTROL_MIN_SHARE)))
            if r['regression_point'] is not None and r['regression_point']['kept']:
                problems.append(name + ': regression point ' + REGRESSION['name'] + ' is kept without the publication')
    return problems


def run(suite_path, out, *, mode, emitted_blob, seams, log=lambda line: print(line, flush=True)):
    """As c254_e3_product.run (same worlds, plan and identity check), swept and judged by this successor."""
    assert mode in ('reduced', 'exhaustive')
    t0 = time.monotonic()
    out = Path(out)
    replace = [(s['product_new'], s['product_old']) for s in seams if s['action'] == 'replace']
    assert len(replace) == 2, 'the E3 publication has two replace seams'
    a_file = [p for p in json.loads(Path(suite_path).read_text())['sources'] if Path(p).name.startswith('source-')]
    assert len(a_file) == 1, ('product ide-ui source', a_file)
    noa_path, noa_row = E3.make_variant(suite_path, out / 'worlds', 'noA', Path(a_file[0]).name, replace)
    nocopy_path, nocopy_row = E3.make_variant(suite_path, out / 'worlds', 'nocopy', E3.NOCOPY_FILE, [E3.NOCOPY_EDIT])
    worlds = {'A': E3.world(suite_path), 'noA': E3.world(noa_path), 'nocopy': E3.world(nocopy_path)}
    emitted = E3.bind(emitted_blob)
    identity = dict(emitted=emitted, world_blob_sha256=worlds['A']['blob_sha256'], world_blob_bytes=worlds['A']['blob_bytes'],
                    objects=worlds['A']['objects'],
                    equal=(worlds['A']['blob_sha256'], worlds['A']['blob_bytes']) == (emitted['sha256'], emitted['bytes']))
    assert identity['equal'], ('E3 harness world is not the emitted ide image', identity)

    def delta(x, y):
        return {k: [x.get(k), y.get(k)] for k in sorted(set(x) | set(y)) if x.get(k) != y.get(k)}
    deltas = {'noA->A': delta(worlds['noA']['sizes'], worlds['A']['sizes']),
              'nocopy->A': delta(worlds['nocopy']['sizes'], worlds['A']['sizes'])}
    lib = list(E3.CASES)
    if mode == 'reduced':
        plan = [('A', 'A', lib, 'lib', False, True), ('nocopy', 'nocopy', lib, 'lib', False, False),
                ('noA', 'noA', lib, 'lib', False, False)]
    else:
        control = lib + [c for c in E3.EXTRA if c[0] != 'x-fill-wrap']
        plan = [('A', 'A', lib + list(E3.EXTRA), 'all', False, True), ('A:allbuf', 'A', list(E3.ALLBUF), 'all', True, False),
                ('nocopy', 'nocopy', control, 'all', False, False), ('noA', 'noA', control, 'all', False, False),
                ('noA:allbuf', 'noA', list(E3.ALLBUF), 'all', True, False)]
    runs = {}
    for name, key, cases, points, allbuf, equivalence in plan:
        log('e3 sweep %s (%s, points %s)' % (name, mode, points))
        runs[name] = Sweep(worlds[key], allbuf).run(cases, points, log, equivalence)
        log('e3 sweep %s: %s references-independent %s seconds %s' % (
            name, json.dumps(runs[name]['by_shape']), runs[name]['references_independent_equal'], runs[name]['seconds']))
    problems = verdict(runs, deltas)
    return dict(status='PASS' if not problems else 'FAIL', mode=mode, problems=problems,
                rules=dict(references='stepped state, independent of the stored buffers', control_min_share=CONTROL_MIN_SHARE,
                           regression_point=REGRESSION),
                suite=E3.bind(suite_path), world_identity=identity, object_deltas=deltas,
                worlds={k: dict(suite=w['path'], blob_sha256=w['blob_sha256'], blob_bytes=w['blob_bytes'],
                                sources=w['sources']) for k, w in worlds.items()},
                controls=[noa_row, nocopy_row],
                totals={n: dict(by_shape=r['by_shape'], total_points=r['total_points'], total_violations=r['total_violations'],
                                total_strict_violations=r['total_strict_violations'],
                                references_independent_equal=r['references_independent_equal'],
                                regression_point=r['regression_point']) for n, r in runs.items()},
                runs=runs, tool=E3.bind(__file__), base_tool=E3.bind(E3.__file__), seconds=round(time.monotonic() - t0, 1))


def selftest():
    """Synthetic: the verdict must refuse what the 2.5.4 verdict could not see, and still refuse what it could."""
    shape_ok = {'drain': dict(points=100, violations=0, strict_violations=0), 'run': dict(points=100, violations=0, strict_violations=0)}
    shape_bad = {'drain': dict(points=100, violations=90, strict_violations=90), 'run': dict(points=100, violations=95, strict_violations=95)}
    kept = dict(kept=True, kept_at_idle=True)
    ok = dict(total_points=200, total_violations=0, total_strict_violations=0, all_poll_aborts_ok=True, all_no_abort_ok=True,
              d4_prefix_reset=dict(ok=True), allbuf=False, violations_outside_return_cases=0, by_shape=shape_ok,
              references_independent_equal=True, regression_point=kept)
    noa = dict(ok, total_violations=185, d4_prefix_reset=dict(ok=False), by_shape=shape_bad, references_independent_equal=False,
               regression_point=dict(kept=False, kept_at_idle=False))
    good = {'A': ok, 'nocopy': dict(ok, total_violations=3), 'noA': noa}
    deltas = {'noA->A': {'%ide-drain-pending': 0, 'ide': 0}, 'nocopy->A': {'ide-split-line': 0}}
    assert verdict(good, deltas) == [], verdict(good, deltas)
    blind = dict(noa, total_violations=90, by_shape=dict(shape_bad, run=dict(points=100, violations=0, strict_violations=0)))
    assert E3.verdict(dict(good, noA=blind), deltas) == [], 'the 2.5.4 verdict was expected to accept the blind control'
    rejected = []
    for name, runs in (
            ('control blind in the run shape (the 2.5.5 candidate under the 2.5.4 tool)', dict(good, noA=blind)),
            ('control below the minimum in the drain shape', dict(good, noA=dict(noa, by_shape=dict(shape_bad, drain=dict(points=100, violations=49, strict_violations=49))))),
            ('control with no points in a shape', dict(good, noA=dict(noa, by_shape=dict(shape_bad, run=dict(points=0, violations=0, strict_violations=0))))),
            ('product world leaves another text than the independent reference', dict(good, A=dict(ok, references_independent_equal=False))),
            ('regression point lost in the product world', dict(good, A=dict(ok, regression_point=dict(kept=False, kept_at_idle=True)))),
            ('regression point lost at idle in the product world', dict(good, A=dict(ok, regression_point=dict(kept=True, kept_at_idle=False)))),
            ('regression point kept without the publication', dict(good, noA=dict(noa, regression_point=kept))),
            ('violation in the product world', dict(good, A=dict(ok, total_violations=1))),
            ('no-copy control passes', dict(good, nocopy=ok)),
            ('control without the publication passes the 2.5.4 rule', dict(good, noA=dict(noa, total_violations=0, by_shape=shape_ok)))):
        assert verdict(runs, deltas), 'negative survived: ' + name
        rejected.append('e3 verdict: ' + name)
    return rejected + E3.selftest()


if __name__ == '__main__':
    print(json.dumps(dict(status='PASS', rejected=selftest()), indent=2))
