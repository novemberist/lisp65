#!/usr/bin/env python3
"""Backspace card: reviewer emulator rows (behaviour) and a Backspace timing lane.

Rows at both prompts on the Seed medium: end-of-line delete, mid-line delete,
delete across a 40-column wrap, delete in a recalled history line and in a
continuation line; the evaluated result proves the edited text. Backspace is
the single key code 20 (`~typeone`), Return is 13.

Timing: `--time` repeats a 70-character line and N Backspaces at l65>,
reading the DWX CPU cycle counter around each key once the screen settled;
run on --medium seed and --medium base (the IDE-exit Final) for the ratio.

Usage: backspace_rows.py <out-name> [--medium seed|base] [--time]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))
import comfort_default_rows as D  # noqa: E402

R, L = D.R, D.L
WORLD = {
    'lite': (ROOT / 'build/o2-lite-product-r7c/media-r7/o2lite.d81', 'ae4e2931bb79bc6d963a2334d67e0777e924c9b34db42ef16567f472c87a300d'),
    'seed': (ROOT / 'build/backspace-product-r1/media-r1/backspace.d81', 'a2872fbd8aa53690da0f'),
    'base': (ROOT / 'build/ide-exit-final-r1/media/ide-exit.d81', '8901407117b87814009a'),
    'walks': (ROOT / 'build/walks-product-r1/media-r1/walks.d81', '67e37ff37b9294ac8103'),
}
N, C = L.N, L.C
DEL, RET, UP = 20, 13, 145


def main():
    p = argparse.ArgumentParser()
    p.add_argument('out')
    p.add_argument('--medium', choices=sorted(WORLD), default='seed')
    p.add_argument('--time', action='store_true')
    a = p.parse_args()
    out = ROOT / 'build' / a.out
    out.mkdir(exist_ok=False)
    medium, prefix = WORLD[a.medium]
    assert R.bind(medium)['sha256'].startswith(prefix)
    assert R.bind(L.XEMU)['sha256'] == L.EXPECT['xemu']
    args = argparse.Namespace(xemu=L.XEMU, rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
                              sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')), timeout=2400)

    class Monitor(R.ProbeMonitor):
        def wait_screen(self, required, timeout=20):
            return super().wait_screen(['65>'], timeout=180)
    R.ProbeMonitor = Monitor

    rows, timing, error, outputs, run = [], None, None, None, None

    def settle(m, secs=1.5, limit=120):
        last, since, t0 = None, time.monotonic(), time.monotonic()
        while time.monotonic() - t0 < limit:
            s = m.screen()
            if s != last:
                last, since = s, time.monotonic()
            elif time.monotonic() - since > secs:
                return s
            time.sleep(0.05)
        return last

    def keys(m, *codes):
        for c in codes:
            m.queue_one(c)
            time.sleep(0.3)

    def row(m, rid, text, dels, extra, want, prompt):
        before = m.screen()
        m.type_text(text)
        settle(m)
        keys(m, *([DEL] * dels))
        if extra:
            m.type_text(extra)
        settle(m)
        keys(m, RET)
        s = settle(m, 2.0)
        ok = L.fresh(before, s, want) and L.active(s) == prompt
        rows.append(dict(id=rid, typed=text, deletes=dels, then=extra, want=want, result='PASS' if ok else 'FAIL',
                         active=L.active(s), new_lines=L.new_lines(before, s)[-4:]))
        print(rid, rows[-1]['result'], rows[-1]['new_lines'][-2:], flush=True)
        (out / 'rows.json').write_text(json.dumps(rows, indent=1) + '\n')

    try:
        run = R.start_run('rows', medium, out, args)
        m = run['monitor']
        s = settle(m, 3, 240)
        assert L.active(s) == C, L.active(s)
        if a.time:
            line = '(list ' + ' '.join('%d' % (i % 10) for i in range(32)) + ')'   # 71 chars
            m.type_text(line[:70])
            settle(m)
            samples = []
            for i in range(20):
                c0 = m.cycle_count()
                m.queue_one(DEL)
                settle(m, 0.6)
                samples.append(m.cycle_count() - c0)
            timing = dict(line_length=70, deletes=20, cycles_incl_settle=samples,
                          median=statistics.median(samples))
            print('timing median cycles (incl. settle window)', timing['median'], flush=True)
            keys(m, *([DEL] * 60))
            settle(m)
        else:
            row(m, 'eol-delete', '(+ 1 22', 1, ')', '3', C)
            row(m, 'multi-delete', '(list 1 2 345', 3, '3)', '(1 2 3)', C)
            long = '(string-length "' + 'a' * 40 + 'bb")'
            row(m, 'wrap-delete', long[:-4], 2, '")', '38', C)   # 40 a typed, 2 deleted across the wrap
            row(m, 'continuation-delete', '(list 1\r(+ 2 33', 1, '))', '(1 5)', C)
            keys(m, UP)
            settle(m)
            before = m.screen()
            keys(m, DEL, DEL)
            m.type_text('))')
            settle(m)
            keys(m, RET)
            s = settle(m, 2.0)
            ok = L.active(s) == C and any(x.strip() for x in L.new_lines(before, s))
            rows.append(dict(id='history-recall-delete', result='PASS' if ok else 'FAIL',
                             new_lines=L.new_lines(before, s)[-4:]))
            print('history-recall-delete', rows[-1]['result'], rows[-1]['new_lines'][-2:], flush=True)
            keys(m, RET)   # empty line: leave Comfort
            settle(m, 2.0)
            row(m, 'native-eol-delete', '(+ 4 55', 1, ')', '9', N)
            row(m, 'native-multi-delete', '(capitalize "abcxyz', 3, '")', '"ABC"', N)
    except BaseException as exc:
        error = repr(exc)
        raise
    finally:
        if run:
            outputs = R.finish_run(run)
        (out / 'receipt.json').write_text(json.dumps(dict(
            status='HALT' if error else 'DONE', error=error, card='backspace', medium_role=a.medium,
            world=dict(medium=R.bind(medium), xemu=R.bind(L.XEMU)), rows=rows, timing=timing, outputs=outputs,
            driver=R.bind(Path(__file__)), passed=sum(r['result'] == 'PASS' for r in rows),
            failed=[r['id'] for r in rows if r['result'] == 'FAIL'],
            claim='Emulator observation; timing samples include a settle window (relative comparison only)'),
            indent=1) + '\n')


if __name__ == '__main__':
    main()
