#!/usr/bin/env python3
"""comfort-library card: functional gates as executed emulator rows.

One headless Xemu session on the Comfort medium (the 2.4.0 product plus the
sixth package).  Keyboard queue and memory reads only; no product build, no
device.  Every row stores its framebuffer and a decoded tail; rows marked with
`values` also read nsym/npool (ELF symbols) and the C2D counters.

Usage: comfort_library_rows.py <out-name> [--medium base]
  --medium base runs the same boot/plain rows on the unchanged 2.4.0 D81
  (control for the cold-boot identity row).
"""
from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))
import dwx_retroactive_red_replay as R  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402

ELF = ROOT / 'build/nested-error-recovery-final-r1/wplto/lisp65-c2-substitution-linked.prg.elf'
BASE = ROOT / 'build/nested-error-recovery-seed-medium-r1/packed/hardware-sp-seed.d81'
MEDIUM = ROOT / 'build/comfort-library-medium-r2/packed/cmf240.d81'
XEMU = ROOT / 'build/nested-error-recovery-ready-instrument-r1/xemu/build/bin/xmega65.native'
EXPECT = dict(elf='66165507a8e5ad1d857afdd967f9056be2ce7bbccc332d5328e981398078b47b',
              base='87cb0f6ea9b2dc690f66ee11d9c76d5138e11f28452254a9b5730c78cabc5f5d',
              medium='bb9b8d56330c425f43792b4a8e6929db05fc8f6bbca52180d04176619f5ff43f',
              xemu='b5b3821783171954d4a732399f3570533f7ebcf96ac166e6b6bee9fda7494333')
C2D = 327680
MAX_SYM, NAME_CAP = 1008, 16351
UP, DOWN = 145, 17
N, C, K = 'LISP65>', 'L65>', ''   # native prompt, Comfort prompt, continuation row
OVER = '*** READER: UNMATCHED CLOSE PARENTHESIS'

# (id, member, keys, active prompt, fresh lines required, lines that must not be fresh, read values)
PLAIN = [
    ('plain-arith', 'plain', ['(+ 4 5)\n'], N, ['9'], [], False),
    ('plain-string', 'plain', ['(capitalize "abc")\n'], N, ['"ABC"'], [], False),
]
ROWS = PLAIN + [
    ('c1-require', 'C1', ['(require "repl-comfort")\n'], N, ['T'], [], True),
    ('c1-require-again', 'C1', ['(require "repl-comfort")\n'], N, ['T'], [], True),
    ('c1-entry', 'C1', ['(repl)\n'], C, [], [], False),
    ('c1-eval', 'C1', ['(+ 1 2)\n'], C, ['3'], [], False),
    ('c2-require-buffer', 'C2', ['(require "buffer")\n'], C, ['T'], [], False),
    ('c2-require-inspect', 'C2', ['(require "inspect")\n'], C, ['T'], [], False),
    ('c2-require-defstruct', 'C2', ['(require "defstruct")\n'], C, ['T'], [], False),
    ('c1-exit', 'C1', ['\n'], N, ['NIL'], [], False),
    ('c10-ide', 'C10', ['(load-lib "ide")\n'], N, ['T'], [], True),
    ('c1-reentry', 'C1', ['(repl)\n'], C, [], [], True),
    ('c2-defun-open', 'C2', ['(defun sq (x)\n'], K, [], [], False),
    ('c2-defun-close', 'C2', ['(* x x))\n'], C, ['SQ'], [], False),
    ('c2-defun-call', 'C2', ['(sq 7)\n'], C, ['49'], [], False),
    ('c2-multiform', 'C2', ['(defun zy () 8) (zy)\n'], C, ['8'], [], False),
    ('c3-indent-2', 'C3', ['(list (list 1\n'], K, [], [], False),
    ('c3-indent-close', 'C3', ['2))\n'], C, ['((1 2))'], [], False),
    ('c4-string-paren', 'C4', ['(string-length "(")\n'], C, ['1'], [], False),
    ('c4-comment-paren', 'C4', ['(+ 1 2) ; )\n'], C, ['3'], [], False),
    ('c4-string-close-open', 'C4', ['(list "a)"\n'], K, [], [], False),
    ('c4-string-close-done', 'C4', ['2)\n'], C, ['("A)" 2)'], [], False),
    ('c4-comment-open', 'C4', ['(+ 4 ; (\n'], K, [], [], False),
    ('c4-comment-done', 'C4', ['5)\n'], C, ['9'], [], False),
    ('c5-overclose-tail', 'C5', ['(+ 1 2))\n'], C, [OVER], ['3'], False),
    ('c5-overclose-alone', 'C5', [')\n'], C, [OVER], [], False),
    ('c5-overclose-setq', 'C5', ['(setq ocv 5))\n'], C, [OVER], ['5'], False),
    ('c5-after', 'C5', ['(+ 2 2)\n'], C, ['4'], [], False),
] + [('c6-seed-%02d' % i, 'C6', ['(list %d)\n' % i], C, ['(%d)' % i], [], False) for i in range(1, 12)] + [
    ('c6-up-01', 'C6', [UP], 'L65> (LIST 11)', [], [], False),
] + [('c6-up-%02d' % i, 'C6', [UP], 'L65> (LIST %d)' % (12 - i), [], [], False) for i in range(2, 11)] + [
    ('c6-up-11-cap', 'C6', [UP], 'L65> (LIST 2)', [], [], False),
    ('c6-down-01', 'C6', [DOWN], 'L65> (LIST 3)', [], [], False),
    ('c6-up-back', 'C6', [UP], 'L65> (LIST 2)', [], [], False),
    ('c6-recall-eval', 'C6', [13], C, ['(2)'], [], False),
    ('c9-burst-32', 'C9', ['(string-length "abcdefghijklmn")\n'], C, ['14'], [], False),
    ('reg-retained-define', 'regression', ["(dotimes (n 1) (eval '(defun f () 7)))\n"], C, ['NIL'], [], False),
    ('reg-retained-call', 'regression', ['(f)\n'], C, ['7'], [], False),
    ('c7-nested-error', 'C7', ["(let ((q 1)) (eval '(capzz)))\n"], N, ['*** UNDEFINED FUNCTION: CAPZZ'], [], True),
    ('c7-after-native', 'C7', ['(+ 4 5)\n'], N, ['9'], [], False),
    ('c7-reentry', 'C7', ['(repl)\n'], C, [], [], False),
    ('c7-session-alive', 'C7', ['(sq 6)\n'], C, ['36'], [], False),
    ('c7-type-error', 'C7', ['(+ nil 32)\n'], N, ['*** VM: TYPE ERROR'], [], False),
    ('c7-reentry-2', 'C7', ['(repl)\n'], C, [], [], False),
    ('reg-lambda-comfort', 'regression', ['(progn (setq savedlambda (lambda () 27)) 19)\n'], N, ['*** VM: BAD BYTECODE'], [], False),
    ('reg-lambda-after', 'regression', ['(+ 4 5)\n'], N, ['9'], [], False),
    ('reg-lambda-native', 'regression', ['(progn (setq savedlambda (lambda () 27)) 19)\n'], N, ['*** VM: BAD BYTECODE'], [], False),
    ('reg-lambda-native-after', 'regression', ['(+ 4 5)\n'], N, ['9'], [], False),
    ('c11-reentry', 'C11', ['(repl)\n'], C, [], [], False),
    ('c11-define', 'C11', ['(defun sp-depth (k) (if (< k 1) 0 (+ 1 (sp-depth (- k 1)))))\n'], C, ['SP-DEPTH'], [], False),
    ('c11-comfort-14', 'C11', ['(sp-depth 14)\n'], C, ['14'], [], False),
    ('c11-comfort-15', 'C11', ['(sp-depth 15)\n'], None, [], [], True),
]
COMFORT16 = [('c11-comfort-16', 'C11', ['(sp-depth 16)\n'], None, [], [], True)]
EXIT = [('c11-exit', 'C11', ['\n'], N, ['NIL'], [], False)]
NATIVE = [
    ('c11-native-16', 'C11', ['(sp-depth 16)\n'], None, [], [], True),
    ('c11-native-17', 'C11', ['(sp-depth 17)\n'], None, [], [], True),
    ('plain-after', 'plain', ['(+ 4 5)\n'], N, ['9'], [], False),
    ('plain-string-after', 'plain', ['(capitalize "xyz")\n'], N, ['"XYZ"'], [], True),
]


def lines(screen):
    return R.ROWS.decoded_framebuffer(screen).splitlines()


def active(screen):
    return lines(screen)[-1].replace('{$A0}', ' ').strip()


def new_lines(before, after):
    """Lines written since `before`: inserted or replaced rows of the framebuffer
    above the active row (covers both scrolling and mid-screen output)."""
    b, a = lines(before)[:-1], lines(after)[:-1]
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, b, a, autojunk=False).get_opcodes():
        if tag in ('insert', 'replace'):
            out.extend(a[j1:j2])
    return out


def fresh(before, after, needle):
    return needle in new_lines(before, after)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('out')
    p.add_argument('--medium', choices=['comfort', 'base'], default='comfort')
    a = p.parse_args()
    out = ROOT / 'build' / a.out
    out.mkdir(exist_ok=False)
    medium = MEDIUM if a.medium == 'comfort' else BASE
    for key, path in (('elf', ELF), ('xemu', XEMU), (a.medium if a.medium == 'base' else 'medium', medium)):
        assert R.bind(path)['sha256'] == EXPECT[key], key
    truth = ElfTruth.read(ELF, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
    args = argparse.Namespace(xemu=XEMU, rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
                              sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')), timeout=3600)

    class Monitor(R.ProbeMonitor):
        def wait_screen(self, required, timeout=20):
            return super().wait_screen(required, timeout=120)
    R.ProbeMonitor = Monitor

    def values(m):
        v = {}
        for name in ('nsym', 'npool'):
            s = truth.symbol(name)
            v[name] = dict(address=s.value, used=int.from_bytes(m.memory_range(s.value, s.bytes), 'little'))
        c2d = m.memory_range(C2D, 64)
        assert c2d[:5] == b'C2D\0\6', c2d[:8]
        for name, off in [('images', 12), ('entries', 16), ('resolutions', 20), ('roots', 24)]:
            v[name] = dict(used=int.from_bytes(c2d[off:off + 2], 'little'),
                           capacity=int.from_bytes(c2d[off + 2:off + 4], 'little'))
        v['free_symbols'] = MAX_SYM - v['nsym']['used']
        v['free_name_bytes'] = NAME_CAP - v['npool']['used']
        v['c2d_header'] = c2d.hex()
        return v

    plan = ROWS if a.medium == 'comfort' else PLAIN
    run = None
    rows = []
    error = None
    outputs = None
    try:
        run = R.start_run('rows', medium, out, args)
        m = run['monitor']
        time.sleep(3)
        boot = m.screen()
        (out / 'boot.txt').write_text(boot)
        m.command('t1')
        rows.append(dict(id='boot', member='boot', active=active(boot), tail=lines(boot)[-8:],
                         values=values(m), result='PASS' if active(boot) == N else 'FAIL'))
        m.command('t0')
        todo = list(plan)
        while todo:
            rid, member, keys, prompt, want, forbid, read = todo.pop(0)
            before = m.screen()
            t0 = time.monotonic()
            for k in keys:
                if isinstance(k, int):
                    m.queue_one(k)
                else:
                    m.type_text(k)
            last, since = None, time.monotonic()
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                s = m.screen()
                if s != last:
                    last, since = s, time.monotonic()
                done = all(fresh(before, s, w) for w in want)
                if prompt is None:
                    done = done and active(s) in (N, C) and s != before
                else:
                    done = done and active(s) == prompt
                if done and time.monotonic() - since > 1.5:
                    break
                time.sleep(0.1)
            m.command('t1')
            s = m.screen()
            path = out / f'{len(rows):02d}-{rid}.txt'
            path.write_text(s)
            got = active(s)
            ok = (prompt is None or got == prompt) and all(fresh(before, s, w) for w in want) \
                and not any(fresh(before, s, f) for f in forbid)
            row = dict(id=rid, member=member, keys=keys, want_prompt=prompt, want_fresh=want, forbid_fresh=forbid,
                       active=got, new_lines=new_lines(before, s), tail=lines(s)[-8:], raw_last_line=lines(s)[-1],
                       seconds=round(time.monotonic() - t0, 2), screen=R.bind(path),
                       values=values(m) if read else None,
                       result=('PASS' if ok else 'FAIL') if prompt is not None or want else 'OBSERVED')
            rows.append(row)
            print(rid, row['result'], repr(got), row['tail'][-3:], flush=True)
            (out / 'rows.json').write_text(json.dumps(rows, indent=1) + '\n')
            m.command('t0')
            if rid == 'c11-comfort-15':
                # 15 returned inside Comfort -> probe 16 there; otherwise Comfort was left.
                todo = (COMFORT16 if got == C else NATIVE) + todo
            if rid == 'c11-comfort-16':
                todo = ((EXIT + NATIVE) if got == C else NATIVE) + todo
    except BaseException as exc:
        error = repr(exc)
        raise
    finally:
        if run:
            try:
                run['monitor'].command('t1')
            except Exception:
                pass
            outputs = R.finish_run(run)
        (out / 'receipt.json').write_text(json.dumps(dict(
            status='HALT' if error else 'DONE', error=error, card='comfort-library', binding='180cb993',
            world=dict(elf=R.bind(ELF), medium=R.bind(medium), xemu=R.bind(XEMU)),
            rows=rows, outputs=outputs, driver=R.bind(Path(__file__)),
            passed=sum(r.get('result') == 'PASS' for r in rows),
            failed=[r['id'] for r in rows if r.get('result') == 'FAIL'],
            claim='Emulator observation (keyboard queue, framebuffer and memory reads); no device, no timing claim'),
            indent=1) + '\n')


if __name__ == '__main__':
    main()
