#!/usr/bin/env python3
"""GC-stress session of 2.5.5: the 2.5.4 session wrapper on the 2.5.5 medium, compared with the 2.5.4 Final.

Successor of c254_gc_session_20261006.py, which is imported with the committed driver c254_gc_stress.py it wraps
(neither is edited).  Added in memory only:
  * role `seed255`: the 2.5.5 Seed build/card-255-product-r1b (medium and ELF bound by sha256 and by the Seed's
    complete.json).  This is the role that can run before the Final exists.
  * role `final255`: the sealed 2.5.5 Final.  FINAL below is None until the Final and its seal exist (fail closed);
    after the seal, set FINAL in a dated successor of this file and rerun -- or accept the Seed session when
    final-identity.json shows medium and ELF byte-identical to the Seed (the 2.5.4 precedent ran on the Final).
  * summary: every scenario against the 2.5.4 Final session build/card-254-gc-r2 (role lite, sealed Final, the
    same wrapper and driver bytes, the same stimuli): status, collections, allocations per transition, peaks,
    headroom to the ceiling.  Rule, as the committed compare(): no peak above the baseline.

Usage
  c255_gc_session.py selftest
  c255_gc_session.py run --role seed255 --scenario S --out build/DIR/S [--limit s] [--stall s]
  c255_gc_session.py summary build/DIR
After a STALL the driver's Xemu can linger for more than 300 s: run every scenario in its own unit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))
import c254_gc_session_20261006 as W4  # noqa: E402

GS = W4.GS
WRAPPED_SHA = '5144b8ff05a12e2b19d259f552c44b56f569856dc6b5f17ec212b0f86b64575b'      # c254_gc_session_20261006.py
FORMAT = 'card255-gc-session-v1'
SEED = dict(name='build/card-255-product-r1b', medium='build/card-255-product-r1b/media-255/c255.d81',
            medium_sha='4f0b76ad395ed861da104960859b8d9416750a00684dd4826a1193b14245523b',
            elf='build/card-255-product-r1b/wplto/resident-island-seed.prg.elf',
            elf_sha='592b2c71c30901d2bb9599d2324678be5cd910865fbbfaf888c5d28ecb2e701f')
FINAL = None            # [SET-AFTER-SEAL] dict(name=, seal_sha=, source_run=) of the sealed 2.5.5 Final
ROLES = ('seed255', 'final255')
BASELINE = 'build/card-254-gc-r2'                     # 2.5.4 session on the sealed 2.5.4 Final (role lite)
KNOWN_STALLS = ('history10', 'history-home-delete-refill250')   # pre-existing overdrawn-recall screen (2.5.3, 2.5.4)
CEILING = W4.CEILING
_STOCK_WORLD = GS.world


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def world(role):
    if role == 'seed255':
        complete = json.loads((ROOT / SEED['name'] / 'complete.json').read_text())
        GS.require(complete['medium']['sha256'] == SEED['medium_sha'] and complete['ELF']['sha256'] == SEED['elf_sha'],
                   'complete.json does not bind the pinned 2.5.5 Seed')
        medium, elf = ROOT / SEED['medium'], ROOT / SEED['elf']
        GS.require(sha(medium) == SEED['medium_sha'] and sha(elf) == SEED['elf_sha'], '2.5.5 Seed drift')
        return medium, elf
    if role == 'final255':
        GS.require(FINAL is not None, 'the 2.5.5 Final is not sealed yet (FINAL is None, set after the seal)')
        base = ROOT / FINAL['name']
        GS.require(sha(base / 'seal.json') == FINAL['seal_sha'], '2.5.5 seal drift')
        GS.require(json.loads((base / 'final-invocation.json').read_text())['sealed_run'] == FINAL['source_run'], 'wrong sealed run')
        rows = {r['role']: r['final'] for r in json.loads((base / 'final-identity.json').read_text())['artifacts']}
        return GS.checked(rows['D81']), GS.checked(rows['ELF'])
    return _STOCK_WORLD(role)


def install():
    assert sha(W4.__file__) == WRAPPED_SHA, 'c254_gc_session_20261006.py is not the wrapped wrapper'
    W4.install()
    GS.world = world


def run(role, scenario, out, limit, stall):
    install()
    import c255_emulator as E5
    E5.idle()               # also knows the 2.5.5 tool names; W4.run repeats the 2.5.4 check and waits for a lingering Xemu
    code = W4.run(role, scenario, out, limit, stall)
    path = (ROOT / out).resolve() / 'session.json'
    if path.is_file():
        session = json.loads(path.read_text())
        session.update(format=FORMAT, wrapper_255=dict(path='tools/host-lisp/' + Path(__file__).name, sha256=sha(__file__)),
                       world=dict(role=role, **(SEED if role == 'seed255' else FINAL or {})))
        path.write_text(json.dumps(session, indent=1) + '\n')
    return code


# ------------------------------------------------------------------ comparison (pure)
def latest(base, name):
    """The latest attempt counts: <dir>/<scenario>, then <dir>/rerun-N/<scenario>."""
    attempts = [q for q in [base / name] + sorted(base.glob(f'rerun-*/{name}')) if (q / 'session.json').is_file()]
    return attempts[-1] if attempts else None, attempts[:-1]


def shape(receipt):
    """Figures of one receipt of c254_gc_stress.run_case."""
    rows, events = receipt.get('collections', []), receipt.get('events', [])
    after = [c['after'] for c in rows]
    phases = {}
    for c in rows:
        p = phases.setdefault(c['phase'], dict(collections=0, peak_live_cells=0, peak_arena_bytes=0))
        p['collections'] += 1
        p['peak_live_cells'] = max(p['peak_live_cells'], c['after']['live_cells'])
        p['peak_arena_bytes'] = max(p['peak_arena_bytes'], c['after']['arena_bytes'])
    return dict(status=receipt.get('status'), collections=len(rows), transitions_done=len(events),
                transitions_total=len(receipt['scenario_contract']['steps']) if 'scenario_contract' in receipt else None,
                allocations=sum(e['allocations'] for e in events), allocations_per_transition=[e['allocations'] for e in events],
                peak_live_cells=max((a['live_cells'] for a in after), default=None),
                peak_arena_bytes=max((a['arena_bytes'] for a in after), default=None),
                mem_oom_ever_set=any(c[k]['mem_oom'] for c in rows for k in ('before', 'after')), phases=phases)


def compare_shapes(name, new, old, new_status, old_status):
    """One scenario of 2.5.5 against the 2.5.4 Final.  Returns dict(verdict, ...).
    PASS: both PASS, no out-of-memory, no peak (whole scenario and every common phase) above the baseline.
    KNOWN-STALL: one of the two history scenarios, STALL in both worlds.  Everything else is a finding."""
    out = dict(status_255=new_status, status_254=old_status)
    if new is None or old is None:
        return dict(out, verdict='NO-DATA')
    for k in ('collections', 'allocations', 'peak_live_cells', 'peak_arena_bytes', 'transitions_done'):
        out[k] = dict(v255=new[k], v254=old[k], delta=None if new[k] is None or old[k] is None else new[k] - old[k])
    if new['allocations_per_transition'] and len(new['allocations_per_transition']) == len(old['allocations_per_transition']):
        d = [a - b for a, b in zip(new['allocations_per_transition'], old['allocations_per_transition'])]
        out['allocations_per_transition_delta'] = dict(min=min(d), max=max(d), sum=sum(d), transitions=len(d), changed=sum(1 for x in d if x))
    common = sorted(set(new['phases']) & set(old['phases']))
    worse = [p for p in common if any(new['phases'][p][k] > old['phases'][p][k] for k in ('peak_live_cells', 'peak_arena_bytes'))]
    out['phases_with_higher_peak'] = worse
    if new['peak_live_cells'] is not None:
        out['headroom_255'] = dict(live_cells=CEILING['live_cells'] - new['peak_live_cells'], arena_bytes=CEILING['arena_bytes'] - new['peak_arena_bytes'])
    if old['peak_live_cells'] is not None:
        out['headroom_254'] = dict(live_cells=CEILING['live_cells'] - old['peak_live_cells'], arena_bytes=CEILING['arena_bytes'] - old['peak_arena_bytes'])
    if new_status == old_status == 'PASS':
        higher = new['peak_live_cells'] > old['peak_live_cells'] or new['peak_arena_bytes'] > old['peak_arena_bytes'] or bool(worse)
        verdict = 'FAIL: out of memory' if new['mem_oom_ever_set'] else ('FAIL: peak above the 2.5.4 Final' if higher else 'PASS')
    elif name in KNOWN_STALLS and new_status == old_status == 'STALL':
        verdict = 'KNOWN-STALL (as on the 2.5.4 Final; pre-existing recall screen)'
    else:
        verdict = 'FINDING: status %s, 2.5.4 Final %s' % (new_status, old_status)
    return dict(out, verdict=verdict)


def summary(directory):
    install()
    base, ref = (ROOT / directory).resolve(), ROOT / BASELINE
    assert base.is_relative_to(ROOT / 'build')
    rows = []
    for name in GS.scenarios():
        here, earlier = latest(base, name)
        there, _ = latest(ref, name)
        entry = dict(scenario=name)
        new = old = None
        new_status, old_status = 'NOT RUN', 'NOT RUN'
        if here is not None:
            s = json.loads((here / 'session.json').read_text())
            new_status = s['status']
            entry.update(role=s['role'], error=s['error'], elapsed_s=s['elapsed_s'], stopped_in=s['stopped_in'],
                         medium_sha256=(s['medium'] or {}).get('sha256'), matches_by_second_reading=s['screen_reading']['matches_by_second_reading'])
            if (here / 'receipt.json').is_file():
                new = shape(json.loads((here / 'receipt.json').read_text()))
                entry['receipt'] = dict(name=str((here / 'receipt.json').relative_to(base)), sha256=sha(here / 'receipt.json'))
        if there is not None:
            s = json.loads((there / 'session.json').read_text())
            old_status = s['status']
            entry['baseline'] = dict(dir=str(there.relative_to(ROOT)), stopped_in=s['stopped_in'], medium_sha256=(s['medium'] or {}).get('sha256'),
                                     session_sha256=sha(there / 'session.json'))
            if (there / 'receipt.json').is_file():
                old = shape(json.loads((there / 'receipt.json').read_text()))
                entry['baseline']['receipt_sha256'] = sha(there / 'receipt.json')
        entry.update(compare_shapes(name, new, old, new_status, old_status))
        if earlier:
            entry['earlier_attempts'] = [str(q.relative_to(base)) for q in earlier]
        rows.append(entry)
    verdicts = [r['verdict'] for r in rows]
    committed = all(r['status_255'] == 'PASS' and r['verdict'] == 'PASS' for r in rows)
    no_regression = all(v == 'PASS' or v.startswith('KNOWN-STALL') for v in verdicts)
    peaks = [r['peak_live_cells']['v255'] for r in rows if r.get('peak_live_cells') and r['peak_live_cells']['v255'] is not None]
    result = dict(format=FORMAT, gate='gc-session', status='PASS' if committed else 'FAIL',
                  status_note='PASS needs all eight scenarios PASS and no peak above the 2.5.4 Final (the rule of the 2.5.4 session); '
                              'no_regression_vs_254 also admits the two known history stalls when they repeat exactly',
                  no_regression_vs_254=no_regression, world=dict(SEED, role='seed255') if all(r.get('role') in (None, 'seed255') for r in rows) else 'mixed roles',
                  baseline=dict(dir=BASELINE, role='lite (sealed 2.5.4 Final)',
                                summary_sha256=sha(ref / 'summary.json') if (ref / 'summary.json').is_file() else None),
                  wrapper=dict(path='tools/host-lisp/' + Path(__file__).name, sha256=sha(__file__)),
                  wrapped=dict(path='tools/host-lisp/c254_gc_session_20261006.py', sha256=WRAPPED_SHA),
                  driver=dict(path='tools/host-lisp/c254_gc_stress.py', sha256=W4.DRIVER_SHA), ceiling=CEILING,
                  highest_peak_live_cells=max(peaks, default=None),
                  headroom_at_highest_peak=CEILING['live_cells'] - max(peaks) if peaks else None,
                  scenarios=rows, not_pass=[r['scenario'] + ': ' + r['verdict'] for r in rows if r['verdict'] != 'PASS'],
                  rerun_on_final='this session ran on the Seed medium; the sealed 2.5.5 Final needs role final255 unless its '
                                 'final-identity.json shows medium and ELF byte-identical to the Seed and the reviewer accepts that',
                  claim='Forced collection at every allocation of each measured transition; emulator only, no natural-pause or device claim')
    (base / 'summary.json').write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps(dict(status=result['status'], no_regression_vs_254=no_regression, highest_peak_live_cells=result['highest_peak_live_cells'],
                          headroom=result['headroom_at_highest_peak'], scenarios={r['scenario']: r['verdict'] for r in rows}), indent=1))
    return 0 if committed else 2


# ------------------------------------------------------------------ selftest (offline)
def selftest():
    log = []
    base = W4.selftest()
    assert base['status'] == 'PASS'
    log.append('c254_gc_session_20261006.py selftest PASS (%d checks)' % len(base['checks']))
    install()
    medium, elf = GS.world('seed255')
    assert sha(medium) == SEED['medium_sha'] and sha(elf) == SEED['elf_sha'] and medium.is_relative_to(ROOT / SEED['name'])
    import c255_rows as X
    assert X.SEED == SEED, 'the row driver pins another Seed'
    log.append('role seed255 resolves to the Seed the row driver pins: ' + str(medium.relative_to(ROOT)))
    saved = SEED['medium_sha']
    try:
        SEED['medium_sha'] = '0' * 64
        try:
            GS.world('seed255')
            raise AssertionError('a wrong Seed hash was admitted')
        except ValueError:
            pass
    finally:
        SEED['medium_sha'] = saved
    try:
        GS.world('final255')
        raise AssertionError('the unsealed Final was admitted')
    except ValueError as exc:
        assert 'not sealed yet' in str(exc)
    log.append('a wrong Seed hash is refused; role final255 is refused until FINAL is set after the seal')
    lite_medium, _lite_elf = GS.world('lite')
    assert sha(lite_medium) == GS.D81_SHA
    log.append('the 2.5.4 roles still resolve through the committed checks')

    def receipt(peak, allocs=(5, 7), status='PASS', oom=False):
        cell = lambda v: dict(live_cells=v, arena_bytes=v * 4, mem_oom=oom)       # noqa: E731
        return dict(status=status, scenario_contract=dict(steps=[['a', 1, 'x'], ['b', 2, 'y']]),
                    collections=[dict(phase='a', before=cell(peak - 9), after=cell(peak - 5)), dict(phase='b', before=cell(peak - 3), after=cell(peak))],
                    events=[dict(allocations=n) for n in allocs])
    a, b = shape(receipt(1000)), shape(receipt(1003))
    assert a['peak_live_cells'] == 1000 and a['allocations'] == 12 and a['phases']['b']['peak_live_cells'] == 1000
    c = compare_shapes('return250', a, b, 'PASS', 'PASS')
    assert c['verdict'] == 'PASS' and c['peak_live_cells']['delta'] == -3 and c['headroom_255']['live_cells'] == 70
    assert compare_shapes('return250', b, a, 'PASS', 'PASS')['verdict'].startswith('FAIL: peak above')
    assert compare_shapes('return250', shape(receipt(1000, oom=True)), b, 'PASS', 'PASS')['verdict'] == 'FAIL: out of memory'
    assert compare_shapes('history10', a, b, 'STALL', 'STALL')['verdict'].startswith('KNOWN-STALL')
    assert compare_shapes('return250', a, b, 'STALL', 'STALL')['verdict'].startswith('FINDING')
    assert compare_shapes('history10', a, b, 'STALL', 'PASS')['verdict'].startswith('FINDING')
    assert compare_shapes('reopen', None, b, 'NOT RUN', 'PASS')['verdict'] == 'NO-DATA'
    d = compare_shapes('reopen', shape(receipt(1000, allocs=(4, 7))), b, 'PASS', 'PASS')['allocations_per_transition_delta']
    assert d == dict(min=-1, max=0, sum=-1, transitions=2, changed=1)
    log.append('comparison: lower or equal peaks PASS, a higher peak or out-of-memory FAIL, the two history stalls KNOWN-STALL only when both stall, anything else a finding')
    ref = ROOT / BASELINE
    have = {n: latest(ref, n)[0] is not None for n in GS.scenarios()}
    log.append('baseline %s holds %d of %d scenarios' % (BASELINE, sum(have.values()), len(have)))
    assert all(have.values()), have
    return dict(status='PASS', checks=log, emulator='NOT RUN')


if __name__ == '__main__':
    assert __debug__, 'assertions required'
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='mode', required=True)
    sub.add_parser('selftest')
    r = sub.add_parser('run')
    r.add_argument('--role', choices=list(ROLES), required=True)
    r.add_argument('--scenario', choices=list(GS.scenarios()), required=True)
    r.add_argument('--out', required=True)
    r.add_argument('--limit', type=int)
    r.add_argument('--stall', type=int, default=W4.DEFAULT_STALL)
    s = sub.add_parser('summary')
    s.add_argument('directory')
    a = p.parse_args()
    if a.mode == 'selftest':
        print(json.dumps(selftest(), indent=1))
    elif a.mode == 'run':
        sys.exit(run(a.role, a.scenario, a.out, a.limit or W4.LIMITS.get(a.scenario, W4.DEFAULT_LIMIT), a.stall))
    else:
        sys.exit(summary(a.directory))
