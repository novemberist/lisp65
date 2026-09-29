#!/usr/bin/env python3
"""IDE key exit card: reviewer emulator rows on the Seed medium.

One headless Xemu session (keyboard queue, framebuffer reads only). Keys that
matter for the exit are sent as real single key codes (`~typeone`): a lone
pasted newline is lost by the HWA paste (comfort-default report §9).

Usage: ide_exit_rows.py <out-name> [--medium seed|base]
  base = the 2.5.0 product D81 (control: C-x q does not exit there).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))
import comfort_default_rows as D  # noqa: E402

R, L = D.R, D.L
WORLD = {
    'seed': (ROOT / 'build/ide-exit-product-r2/media-r2/ide-exit.d81',
             '8901407117b87814009a77751a78c0a70096813574300300ef4f8f5c5ad9f8f5'),
    'base': D.WORLD['product'][:2],
}
N, C = L.N, L.C
CTRL_X, RET, DOWN = 24, 13, 17


def text(screen):
    return R.ROWS.decoded_framebuffer(screen)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('out')
    p.add_argument('--medium', choices=sorted(WORLD), default='seed')
    a = p.parse_args()
    out = ROOT / 'build' / a.out
    out.mkdir(exist_ok=False)
    medium, sha = WORLD[a.medium]
    assert R.bind(medium)['sha256'] == sha
    assert R.bind(L.XEMU)['sha256'] == L.EXPECT['xemu']
    args = argparse.Namespace(xemu=L.XEMU, rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
                              sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')), timeout=1800)

    class Monitor(R.ProbeMonitor):
        def wait_screen(self, required, timeout=20):
            return super().wait_screen(['65>'], timeout=180)
    R.ProbeMonitor = Monitor

    rows, error, outputs, run = [], None, None, None

    def settle(m, secs=2.5, limit=120):
        last, since, t0 = None, time.monotonic(), time.monotonic()
        while time.monotonic() - t0 < limit:
            s = m.screen()
            if s != last:
                last, since = s, time.monotonic()
            elif time.monotonic() - since > secs:
                return s
            time.sleep(0.1)
        return last

    def row(m, rid, act, check):
        before = m.screen()
        act(m)
        s = settle(m)
        path = out / f'{len(rows):02d}-{rid}.txt'
        path.write_text(s)
        ok, note = check(before, s)
        rows.append(dict(id=rid, result='PASS' if ok else 'FAIL', note=note, active=L.active(s),
                         tail=[x for x in L.lines(s) if x.strip()][-6:], screen=R.bind(path)))
        print(rid, rows[-1]['result'], note, repr(L.active(s)), flush=True)
        (out / 'rows.json').write_text(json.dumps(rows, indent=1) + '\n')

    def keys(*codes):
        def f(m):
            for c in codes:
                m.queue_one(c)
                time.sleep(0.6)
        return f

    def typed(s):
        return lambda m: m.type_text(s)

    at_prompt = lambda want: (lambda b, s: (L.active(s) == want, 'prompt ' + L.active(s)))
    in_ide = lambda b, s: (L.active(s) not in (N, C), 'editor active')
    try:
        run = R.start_run('rows', medium, out, args)
        m = run['monitor']
        s = settle(m, 3, 240)
        rows.append(dict(id='boot', result='PASS' if L.active(s) == C else 'FAIL', active=L.active(s)))
        print('boot', rows[-1]['result'], repr(L.active(s)), flush=True)
        row(m, 'load-ide', typed('(load-lib "ide")\n'), lambda b, s: (L.active(s) == C and L.fresh(b, s, 'T'), 'T at l65>'))
        row(m, 'edit-enter', typed('(edit)\n'), in_ide)
        row(m, 'type-text', typed('hello'), lambda b, s: ('HELLO' in text(s), 'HELLO in buffer'))
        row(m, 'plain-q-inserts', keys(ord('q')), lambda b, s: (L.active(s) not in (N, C) and 'HELLOQ' in text(s), 'q inserted, still in editor'))
        row(m, 'cx-down-no-exit', keys(CTRL_X, DOWN), lambda b, s: (L.active(s) not in (N, C), 'still in editor'))
        if a.medium == 'seed':
            row(m, 'cx-q-exits', keys(CTRL_X, ord('q')), lambda b, s: (L.active(s) in (N, C), 'back at a prompt'))
            row(m, 'after-exit-eval', typed('(+ 4 5)\n'), lambda b, s: (L.fresh(b, s, '9') and L.active(s) in (N, C), '9'))
            row(m, 'edit-reenter', typed('(edit)\n'), lambda b, s: (L.active(s) not in (N, C) and 'HELLOQ' in text(s), 'buffer kept'))
            row(m, 'cx-q-exits-again', keys(CTRL_X, ord('q')), lambda b, s: (L.active(s) in (N, C), 'back at a prompt'))
        else:
            row(m, 'cx-q-no-exit-base', keys(CTRL_X, ord('q')), lambda b, s: (L.active(s) not in (N, C), 'control: no exit on 2.5.0'))
    except BaseException as exc:
        error = repr(exc)
        raise
    finally:
        if run:
            outputs = R.finish_run(run)
        (out / 'receipt.json').write_text(json.dumps(dict(
            status='HALT' if error else 'DONE', error=error, card='ide-key-exit', medium_role=a.medium,
            world=dict(medium=R.bind(medium), xemu=R.bind(L.XEMU)), rows=rows, outputs=outputs,
            driver=R.bind(Path(__file__)), passed=sum(r['result'] == 'PASS' for r in rows),
            failed=[r['id'] for r in rows if r['result'] == 'FAIL'],
            claim='Emulator observation; RUN/STOP exactly-once and physical keys are device rows'), indent=1) + '\n')


if __name__ == '__main__':
    main()
