#!/usr/bin/env python3
"""GC-stress session on the SEALED 2.5.5 Final, with the breakpoint waits of the driver timed.

Dated successor of c255_gc_session.py (imported, not edited; it wraps c254_gc_session_20261006.py and the
committed driver c254_gc_stress.py).  Added in memory only:
  * the Final role: FINAL of the committed file is None (set-after-seal); the sealed 2.5.5 Final is supplied
    here, so role `final255` performs its seal / sealed-run / identity check;
  * every breakpoint wait of the driver (block_26_vm_hardening_dwx_prefilter.wait_register: input boundary,
    forced GC entry, forced GC return) is timed in wall seconds; <out>/wait-stats.json holds the count, the
    maximum and the largest values per label, i.e. the margin to the driver's timeout (90 s for the two GC
    waits, 240 s for the input boundary).  The waits themselves are the committed ones;
  * when a wait times out, BEFORE the driver aborts its emulator: registers and cycle counter twice two
    seconds apart (does the CPU run at all?), the screen, gc_runs / allocs / input counter, and ONE extension of
    the same wait by its own timeout (does the awaited stop arrive late?).  Written to <out>/timeout-capture.json.
    The timeout is then raised as the driver raised it; nothing is retried or worked around.
Reason: build/card-255-gc-r1/pending32 (first attempt) ended in 'forced GC entry breakpoint timeout' at $E075.

Usage
  c255_gc_session_final_20261007.py selftest
  c255_gc_session_final_20261007.py run --role final255|lite --scenario S --out build/DIR/S [--limit s] [--stall s]
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))
import c255_gc_session as W5  # noqa: E402

GS, W4 = W5.GS, W5.W4
WRAPPED_SHA = 'f2fc0769b67a7cd4bc7395aa8cbcf27fe5ef9442de7faa4035249f066557abb1'      # c255_gc_session.py
FINAL = dict(name='build/card-255-final-r1', seal_sha='2776060ce564c6a16254a2736fb0cac8dec27f35e0d87b6188e3b622034abcb4',
             source_run='build/card-255-check-source-final-r1')
FORMAT = 'card255-gc-session-final-v1'
STATS = dict(waits={}, out=None, capture=None)
KEEP = 8


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def note(label, seconds, ok):
    row = STATS['waits'].setdefault(label, dict(count=0, timeouts=0, total_s=0.0, max_s=0.0, largest_s=[]))
    row['count'] += 1
    row['timeouts'] += 0 if ok else 1
    row['total_s'] = round(row['total_s'] + seconds, 3)
    row['max_s'] = max(row['max_s'], round(seconds, 3))
    row['largest_s'] = sorted(row['largest_s'] + [round(seconds, 3)], reverse=True)[:KEEP]


def flush_stats():
    if STATS['out'] is not None and Path(STATS['out']).is_dir():
        doc = dict(format=FORMAT, unit='wall seconds per driver breakpoint wait', waits=STATS['waits'])
        (Path(STATS['out']) / 'wait-stats.json').write_text(json.dumps(doc, indent=1) + '\n')


def capture(G, monitor, predicate, label, timeout, error):
    """A wait timed out.  Observe; change nothing but one more `wait` of the same kind."""
    rec = dict(label=label, error=str(error), timeout_s=timeout, at=time.strftime('%Y-%m-%d %H:%M:%S'))
    try:
        r1, c1 = G.register_line(monitor), monitor.cycle_count()
        time.sleep(2.0)
        r2, c2 = G.register_line(monitor), monitor.cycle_count()
        rec.update(registers=[r1, r2], cycle_count=[c1, c2], cpu_advanced_in_2_s=c2 != c1, predicate_now=bool(predicate(r2)),
                   full_register_reply=monitor.command('r'), screen=monitor.screen())
        t0 = time.monotonic()
        late = None
        while time.monotonic() - t0 < timeout:
            line = G.register_line(monitor)
            if predicate(line):
                late = dict(arrived_after_s=round(time.monotonic() - t0, 1), registers=line)
                break
            time.sleep(0.5)
        r3, c3 = G.register_line(monitor), monitor.cycle_count()
        rec['extended_wait'] = dict(seconds=timeout, arrived=late, registers_after=r3, cycle_count_after=c3, cpu_advanced=c3 != c2)
    except BaseException as exc:
        rec['capture_error'] = repr(exc)
    STATS['capture'] = rec
    if STATS['out'] is not None and Path(STATS['out']).is_dir():
        (Path(STATS['out']) / 'timeout-capture.json').write_text(json.dumps(rec, indent=1) + '\n')
    print('TIMEOUT CAPTURE', json.dumps({k: rec.get(k) for k in ('label', 'registers', 'cycle_count', 'cpu_advanced_in_2_s', 'extended_wait')}), flush=True)


def install():
    assert sha(W5.__file__) == WRAPPED_SHA, 'c255_gc_session.py is not the wrapped wrapper'
    W5.FINAL = FINAL
    W5.install()
    import block_26_vm_hardening_dwx_prefilter as G
    if getattr(G.wait_register, 'timed', False):
        return
    stock = G.wait_register

    def wait_register(monitor, predicate, label, timeout=90.0):
        t0 = time.monotonic()
        try:
            line = stock(monitor, predicate, label, timeout)
        except G.PrefilterError as exc:
            note(label, time.monotonic() - t0, False)
            capture(G, monitor, predicate, label, timeout, exc)
            flush_stats()
            raise
        note(label, time.monotonic() - t0, True)
        if STATS['waits'][label]['count'] % 200 == 0:
            flush_stats()
        return line
    wait_register.timed = True
    G.wait_register = wait_register


def run(role, scenario, out, limit, stall):
    install()
    STATS['out'] = (ROOT / out).resolve()
    try:
        code = W5.run(role, scenario, out, limit, stall)
    finally:
        flush_stats()
    path = STATS['out'] / 'session.json'
    if path.is_file():
        session = json.loads(path.read_text())
        session.update(wrapper_final=dict(path='tools/host-lisp/' + Path(__file__).name, sha256=sha(__file__)),
                       final=dict(FINAL) if role == 'final255' else session.get('final'),
                       waits={k: dict(count=v['count'], timeouts=v['timeouts'], max_s=v['max_s']) for k, v in STATS['waits'].items()},
                       timeout_capture='timeout-capture.json' if STATS['capture'] else None)
        path.write_text(json.dumps(session, indent=1) + '\n')
    return code


def selftest():
    log = []
    base = W5.selftest()
    assert base['status'] == 'PASS'
    log.append('c255_gc_session.py selftest PASS (%d checks; there FINAL is None and role final255 is refused)' % len(base['checks']))
    install()
    medium, elf = GS.world('final255')
    assert sha(medium) == W5.SEED['medium_sha'] and sha(elf) == W5.SEED['elf_sha'] and medium.is_relative_to(ROOT / FINAL['name'])
    log.append('role final255 resolves through seal, sealed run and final-identity.json; medium and ELF byte-identical to the Seed: '
               + str(medium.relative_to(ROOT)))
    for key, bad in (('seal_sha', '0' * 64), ('source_run', 'build/another-run')):
        saved = FINAL[key]
        try:
            FINAL[key] = bad
            try:
                GS.world('final255')
                raise AssertionError('wrong %s admitted' % key)
            except ValueError:
                pass
        finally:
            FINAL[key] = saved
    log.append('a wrong seal sha and a wrong source run are refused')
    lite, _ = GS.world('lite')
    assert sha(lite) == GS.D81_SHA
    log.append('role lite (sealed 2.5.4 Final) still resolves through the committed checks')
    # the timed wait: a passing wait is counted, a timeout is counted, captured and raised unchanged
    import block_26_vm_hardening_dwx_prefilter as G

    class Fake:
        def __init__(self, lines):
            self.lines, self.n, self.cycles = lines, 0, 0

        def command(self, _c):
            self.n += 1
            return self.lines[min(self.n - 1, len(self.lines) - 1)] + '\r\n.\r\n'

        def cycle_count(self):
            return self.cycles

        def screen(self):
            return 'SCREEN'
    STATS['waits'].clear()
    hit = 'AAAA 00 00 00 00 00 0195 8000 0000 20       27 00 --E-----'
    miss = 'E075 00 00 00 00 00 0195 8000 0000 20       27 00 --E--IZC'
    assert G.wait_register(Fake([hit]), lambda r: r.startswith('AAAA'), 'unit', 1.0) == hit
    try:
        G.wait_register(Fake([miss]), lambda r: r.startswith('AAAA'), 'unit', 1.0)
        raise AssertionError('a timeout was swallowed')
    except G.PrefilterError as exc:
        assert 'unit breakpoint timeout: E075' in str(exc)
    row, cap = STATS['waits']['unit'], STATS['capture']
    assert row['count'] == 2 and row['timeouts'] == 1 and cap['cpu_advanced_in_2_s'] is False and cap['extended_wait']['arrived'] is None
    STATS['waits'].clear()
    STATS['capture'] = None
    log.append('timed wait: a hit is counted, a timeout is counted, captured (halted CPU seen as not advancing, extension recorded) and raised unchanged')
    return dict(status='PASS', checks=log, emulator='NOT RUN')


if __name__ == '__main__':
    assert __debug__, 'assertions required'
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='mode', required=True)
    sub.add_parser('selftest')
    r = sub.add_parser('run')
    r.add_argument('--role', choices=['final255', 'lite'], required=True)
    r.add_argument('--scenario', choices=list(GS.scenarios()), required=True)
    r.add_argument('--out', required=True)
    r.add_argument('--limit', type=int)
    r.add_argument('--stall', type=int, default=W4.DEFAULT_STALL)
    a = p.parse_args()
    if a.mode == 'selftest':
        print(json.dumps(selftest(), indent=1))
    else:
        sys.exit(run(a.role, a.scenario, a.out, a.limit or W4.LIMITS.get(a.scenario, W4.DEFAULT_LIMIT), a.stall))
