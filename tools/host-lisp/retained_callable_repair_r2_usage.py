"""Native five-package usage, anchor Final (baseline) vs repair Seed (candidate); no timing claims.

The 23 rows of the dirty-anchor usage lane.  Row 18 stays the exact
registered error in both worlds (member 1 withdrawn, gate 3 rebound 2026-09-23).
"""
import argparse
import json
from pathlib import Path
import time

import dwx_retroactive_red_replay as R
import dwx_comfort_resume as C
import native_cycle_stationary as N

ROOT = Path(__file__).resolve().parents[2]
import sys
ROLE=sys.argv[1]
assert ROLE in ('baseline','candidate')
OUT = ROOT / ('build/retained-callable-repair-r2-usage-'+ROLE+'-r1')
ROWS = [
    ('(defun cacheprobe () 7)', 'cacheprobe'),
    ('(cacheprobe)', '7'),
    ('(progn (setq savedprobe (function cacheprobe)) 17)', '17'),
    ('(defun cacheprobe () 8)', 'cacheprobe'),
    ('(cacheprobe)', '8'),
    ('(funcall savedprobe)', '8'),
    ('(setf (car (list 1 2)) 9)', '9'),
    ('(capitalize "abc")', '"Abc"'),
    ('(require "place")', 't'),
    ('(require "string-extra")', 't'),
    ('(require "buffer")', 't'),
    ('(buffer-length (make-buffer 3))', '3'),
    ('(require "defstruct")', 't'),
    ('(defstruct point x)', 't'),
    ('(point-x (make-point 42))', '42'),
    ('(require "inspect")', 't'),
    ("(who-calls 'car)", 'nil'),
    ('(+ 40 2)', '42'),
    ('(progn (setq savedlambda (lambda () 27)) 19)', '*** VM: BAD BYTECODE'),
    ('(cacheprobe)', '8'),
    ('(funcall savedprobe)', '8'),
    ("(eval '(+ 10 2))", '12'),
    ('(cacheprobe)', '8'),
]


def main():
    OUT.mkdir(exist_ok=False)
    identity = json.loads((ROOT / 'build/retained-callable-repair-r2/ready-instrument.json').read_text())
    world = next(w for w in identity['worlds'] if w['role'] == ROLE)
    args = argparse.Namespace(xemu=N.checked_binding(world['binary']),
                              rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
                              sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')),
                              timeout=600)
    parent = R.ProbeMonitor
    class Monitor(parent):
        def wait_screen(self, required, timeout=20):
            return super().wait_screen(required, timeout=120)
    R.ProbeMonitor = Monitor
    run = None
    rows = []
    error = None
    try:
        run = R.start_run('usage', N.checked_binding(world['medium']), OUT, args)
        m = run['monitor']
        for index, (form, expected) in enumerate(ROWS):
            before = m.screen()
            m.type_text(form + '\n')
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                after = m.screen()
                visible = R.ROWS.decoded_framebuffer(after)
                assert '***' not in visible or expected.startswith('***') or '***' in R.ROWS.decoded_framebuffer(before), visible
                if C.active(after) == 'LISP65>' and C.fresh_result(before, after, expected):
                    break
                time.sleep(.05)
            else:
                (OUT / f'{index:02d}-failed.txt').write_text(after)
                raise AssertionError('fresh result/prompt absent: ' + form)
            (OUT / f'{index:02d}-screen.txt').write_text(after)
            rows.append(dict(form=form, expected=expected, screen=N.bind(OUT / f'{index:02d}-screen.txt')))
            print(index, form, '=>', expected, flush=True)
    except BaseException as exc:
        error = repr(exc)
        raise
    finally:
        output = R.finish_run(run) if run else None
        (OUT / 'receipt.json').write_text(json.dumps(dict(status='HALT' if error else 'PASS',
            error=error, world=world, rows=rows, output=output,
            driver=N.bind(Path(__file__)),
            claim='Native usage, not a new user-capacity or fresh-load timing claim; no device'), indent=2) + '\n')


if __name__ == '__main__':
    main()
