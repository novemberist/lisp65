#!/usr/bin/env python3
"""comfort-default card: reviewer emulator rows on the replacement Seed media.

One headless Xemu session per medium (keyboard queue, framebuffer and memory
reads only; no product build, no device).  Derived from comfort_library_rows.py:
the product now boots into Comfort (`L65>`), errors, the lambda refusal and the
depth refusal land back at `L65>` with definitions and history intact, and the
empty line leaves to `LISP65>` and stays there.

Usage: comfort_default_rows.py <out-name> --medium product|no-comfort|v240-init|base
  Boot cycles (DWX CPU cycle counter at the first stable prompt) are recorded
  for every medium; `base` is the unchanged 2.4.0 D81 (boot comparison only).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))
import comfort_library_rows as L  # noqa: E402
import dwx_retroactive_red_replay as R  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402

MEDIA = ROOT / 'build/comfort-default-r2/seed/media-r2'
ELF = ROOT / 'build/comfort-default-product-r2/wplto/resident-island-seed.prg.elf'
WORLD = {
    'lite': (ROOT / 'build/o2-lite-product-r7c/media-r7/o2lite.d81',
             'ae4e2931bb79bc6d963a2334d67e0777e924c9b34db42ef16567f472c87a300d',
             ROOT / 'build/o2-lite-product-r7c/wplto/resident-island-seed.prg.elf'),
    'product': (MEDIA / 'comfort-default/comfort-default.d81',
                '137bfa51589f096eb715bc1e71c66196b79a365db65c1373696ea82f04dc34e5', ELF),
    'no-comfort': (MEDIA / 'control-no-comfort/control-no-comfort.d81',
                   'b855206f51f483023a227b31ceebaa045f8a6f8588e3e8c18fa3bc0500b59e4d', ELF),
    'v240-init': (MEDIA / 'control-v240-init/control-v240-init.d81',
                  '70fd05aa501bd11c2eeec5424ebaedf456eb889c66d50986f85cdc0a34cacbbc', ELF),
    'base': (L.BASE, L.EXPECT['base'], L.ELF),
    'walks': (ROOT / 'build/walks-product-r1/media-r1/walks.d81',
              '67e37ff37b9294ac81031159174320bf08abd4dc8ae4a7d302fdd66ac5707401',
              ROOT / 'build/walks-product-r1/wplto/resident-island-seed.prg.elf'),
    'strings': (ROOT / 'build/strings-product-r3/media-r1/strings.d81',
                '9978daa146b89cf71ad1d3f290d80cf74b197911e7854859f9e4aa9bb2fce441',
                ROOT / 'build/strings-product-r3/wplto/resident-island-seed.prg.elf'),
}
ELF_SHA = {ROOT / 'build/strings-final-r1/wplto/resident-island-seed.prg.elf': 'd514e4980c636cab0c6ae1ee9bea77afdd3a4fdf58f01995aba5ff822e89ed05', ELF: 'd555f01fbac51bb5fbc035b2b595e95e3c8e3bedc584c87112bca8b073e31444', L.ELF: L.EXPECT['elf'],
           ROOT / 'build/o2-lite-product-r7c/wplto/resident-island-seed.prg.elf': '4edcc037a3fd729cc124ae40d8c85349889ba17941e3468f1ffe8c2de2aa4abd',
           ROOT / 'build/walks-product-r1/wplto/resident-island-seed.prg.elf': '7b8dbf3dd53f08872322035ac260bb36d5fcd941fdeb4ff148e386d09d794449',
           ROOT / 'build/strings-product-r3/wplto/resident-island-seed.prg.elf': 'd514e4980c636cab0c6ae1ee9bea77afdd3a4fdf58f01995aba5ff822e89ed05'}
N, C, K, OVER, UP, DOWN = L.N, L.C, L.K, L.OVER, L.UP, L.DOWN
CAPZZ = "(let ((q 1)) (eval '(capzz)))\n"

# (id, member, keys, active prompt(s) or None, fresh lines required, lines that must not be fresh, read values)
PRODUCT = [
    ('d-eval', 'default', ['(+ 1 2)\n'], C, ['3'], [], False),
    ('d-string', 'default', ['(capitalize "abc")\n'], C, ['"ABC"'], [], False),
    ('d-require-buffer', 'C2', ['(require "buffer")\n'], C, ['T'], [], False),
    ('d-require-inspect', 'C2', ['(require "inspect")\n'], C, ['T'], [], False),
    ('d-require-defstruct', 'C2', ['(require "defstruct")\n'], C, ['T'], [], False),
    ('d-require-comfort-again', 'C1', ['(require "repl-comfort")\n'], C, ['T'], [], True),
    ('d-defun-open', 'C2', ['(defun sq (x)\n'], K, [], [], False),
    ('d-defun-close', 'C2', ['(* x x))\n'], C, ['SQ'], [], False),
    ('d-defun-call', 'C2', ['(sq 7)\n'], C, ['49'], [], False),
    ('d-multiform', 'C2', ['(defun zy () 8) (zy)\n'], C, ['8'], [], False),
    ('d-indent-2', 'C3', ['(list (list 1\n'], K, [], [], False),
    ('d-indent-close', 'C3', ['2))\n'], C, ['((1 2))'], [], False),
    ('d-string-paren', 'C4', ['(string-length "(")\n'], C, ['1'], [], False),
    ('d-comment-paren', 'C4', ['(+ 1 2) ; )\n'], C, ['3'], [], False),
    ('d-string-close-open', 'C4', ['(list "a)"\n'], K, [], [], False),
    ('d-string-close-done', 'C4', ['2)\n'], C, ['("A)" 2)'], [], False),
    ('d-overclose-tail', 'C5', ['(+ 1 2))\n'], C, [OVER], ['3'], False),
    ('d-overclose-alone', 'C5', [')\n'], C, [OVER], [], False),
    ('d-after-overclose', 'C5', ['(+ 2 2)\n'], C, ['4'], [], False),
] + [('d-hist-seed-%02d' % i, 'C6', ['(list %d)\n' % i], C, ['(%d)' % i], [], False) for i in range(1, 12)] + [
    ('d-hist-up-01', 'C6', [UP], 'L65> (LIST 11)', [], [], False),
    ('d-hist-up-02', 'C6', [UP], 'L65> (LIST 10)', [], [], False),
    ('d-hist-down', 'C6', [DOWN], 'L65> (LIST 11)', [], [], False),
    ('d-hist-recall', 'C6', [13], C, ['(11)'], [], False),
    ('d-burst-32', 'C9', ['(string-length "abcdefghijklmn")\n'], C, ['14'], [], False),
    ('reg-retained-define', 'regression', ["(dotimes (n 1) (eval '(defun f () 7)))\n"], C, ['NIL'], [], False),
    ('reg-retained-call', 'regression', ['(f)\n'], C, ['7'], [], False),
    # Sticky re-entry: errors land at l65> again, definitions and history intact.
    ('d-hist-mark', 'sticky', ['(list 77)\n'], C, ['(77)'], [], False),
    ('d-nested-error', 'sticky', [CAPZZ], C, ['*** UNDEFINED FUNCTION: CAPZZ'], [], True),
    ('d-after-error', 'sticky', ['(sq 6)\n'], C, ['36'], [], False),
    ('d-history-after-error', 'sticky', [UP, UP], ('L65> (LIST 77)', 'L65> ' + CAPZZ.strip().upper()), [], [], False),
    ('d-history-recall-eval', 'sticky', [13], C, [], [], False),
    ('d-type-error', 'sticky', ['(+ nil 32)\n'], C, ['*** VM: TYPE ERROR'], [], False),
    ('d-after-type-error', 'sticky', ['(zy)\n'], C, ['8'], [], False),
    ('reg-lambda', 'regression', ['(progn (setq savedlambda (lambda () 27)) 19)\n'], C, ['*** VM: BAD BYTECODE'], [], False),
    ('reg-lambda-after', 'regression', ['(+ 4 5)\n'], C, ['9'], [], False),
    ('d-depth-define', 'depth', ['(defun sp-depth (k) (if (< k 1) 0 (+ 1 (sp-depth (- k 1)))))\n'], C, ['SP-DEPTH'], [], False),
    ('d-depth-14', 'depth', ['(sp-depth 14)\n'], C, ['14'], [], False),
    ('d-depth-15', 'depth', ['(sp-depth 15)\n'], C, [], [], True),
    ('d-depth-16', 'depth', ['(sp-depth 16)\n'], C, [], [], True),
    ('d-depth-refusal', 'depth', ['(sp-depth 40)\n'], C, ['*** VM: STACK OVERFLOW'], [], True),
    ('d-after-depth', 'depth', ['(sq 5)\n'], C, ['25'], [], False),
    # Deliberate exit: native prompt, and it stays native after an error.
    ('d-exit', 'exit', ['\n'], N, ['NIL'], [], False),
    ('d-native-eval', 'exit', ['(+ 4 5)\n'], N, ['9'], [], False),
    ('d-native-error', 'exit', [CAPZZ], N, ['*** UNDEFINED FUNCTION: CAPZZ'], [], False),
    ('d-native-stays', 'exit', ['(sq 3)\n'], N, ['9'], [], False),
    ('d-native-type-error', 'exit', ['(+ nil 32)\n'], N, ['*** VM: TYPE ERROR'], [], False),
    ('d-native-lambda', 'exit', ['(progn (setq savedlambda (lambda () 27)) 19)\n'], N, ['*** VM: BAD BYTECODE'], [], False),
    ('d-native-depth', 'exit', ['(sp-depth 40)\n'], N, ['*** VM: STACK OVERFLOW'], [], False),
    ('d-native-ide', 'C10', ['(load-lib "ide")\n'], N, ['T'], [], True),
    ('d-reentry', 'reentry', ['(repl)\n'], C, [], [], False),
    ('d-reentry-error', 'reentry', [CAPZZ], C, ['*** UNDEFINED FUNCTION: CAPZZ'], [], False),
    ('d-reentry-alive', 'reentry', ['(sq 8)\n'], C, ['64'], [], False),
    ('d-exit-again', 'reentry', ['\n'], N, ['NIL'], [], False),
    ('d-plain-after', 'plain', ['(capitalize "xyz")\n'], N, ['"XYZ"'], [], True),
]
NATIVE_CONTROL = [
    ('ctl-eval', 'control', ['(+ 4 5)\n'], N, ['9'], [], False),
    ('ctl-error', 'control', [CAPZZ], N, ['*** UNDEFINED FUNCTION: CAPZZ'], [], False),
    ('ctl-stays', 'control', ['(+ 2 3)\n'], N, ['5'], [], True),
]
V240_EXTRA = [
    ('ctl-require', 'control', ['(require "repl-comfort")\n'], N, ['T'], [], False),
    ('ctl-entry', 'control', ['(repl)\n'], C, [], [], False),
    ('ctl-sticky', 'control', [CAPZZ], C, ['*** UNDEFINED FUNCTION: CAPZZ'], [], False),
    ('ctl-exit', 'control', ['\n'], N, ['NIL'], [], False),
    ('ctl-native-after', 'control', ['(+ 4 5)\n'], N, ['9'], [], True),
]
# Multi-line strings (owner device finding 2026-09-28): the scanner must carry
# the in-string state across continuation lines; indentation must not enter it.
STRINGS = [
    ('str-owner-example', 'strings', ['(print "hello\n', '     world")\n'], C, ['     WORLD"'], [], False),
    ('str-three-lines', 'strings', ['(string-length "a\n', 'b\n', 'c")\n'], C, ['5'], [], False),
    ('str-escaped-quote', 'strings', ['(string-length "x\\"\n', 'y")\n'], C, ['4'], [], False),
    ('str-parens-inside', 'strings', ['(string-length "((\n', '))")\n'], C, ['5'], [], False),
    ('str-then-eval', 'strings', ['(+ 1 2)\n'], C, ['3'], [], False),
    ('str-overclose-still', 'strings', ['(+ 1 2))\n'], C, [OVER], ['3'], False),
]
# Return with no printable text must use queue_one(13): a lone pasted LF
# is lost by the emulator. The three deletes remove two indent bytes then pop.
LITE = [
    ('lite-owner-five-spaces', 'lite', ['(print "hello\n', '     world")\n'], C, ['     WORLD"'], [], False),
    ('lite-three-lines', 'lite', ['(string-length "a\n', 'b\n', 'c")\n'], C, ['5'], [], False),
    ('lite-escaped-quote', 'lite', ['(string-length "x\\"\n', 'y")\n'], C, ['4'], [], False),
    ('lite-indent-reopen', 'lite', ['(+ 1\n', 20, 20, 20, ' 2)\n'], C,
     ['[EDIT PREVIOUS LINE]', '(+ 1 2)', '3'], [], False),
    ('lite-reopen-twice', 'lite', ['(+ 1\n', '2\n', 20, 20, 20, 20, 20, 20, 20, ' 3)\n'], C,
     ['[EDIT PREVIOUS LINE]', '(+ 1 3)', '4'], [], False),
    ('lite-reopen-return', 'lite', ['(+ 1\n', 20, 20, 20, 13, '2)\n'], C,
     ['[EDIT PREVIOUS LINE]', '3'], [], False),
    ('lite-overclose', 'lite', ['(+ 1 2))\n'], C, [OVER], ['3'], False),
    ('lite-after', 'lite', ['(+ 1 2)\n'], C, ['3'], [], False),
    # 641 source bytes, including three intervening LFs; each active line
    # stays within its weighted allowance so this isolates the form-byte cap.
    ('lite-input-641', 'lite', ['"' + 'a'*199 + '\n', 'b'*200 + '\n',
     'c'*200 + '\n', 'd'*37 + '"\n'], C, ['*** INPUT LIMIT'], [], False),
    ('lite-history-omission', 'lite', ['(string-length "' + 'a'*120 + '\n',
     'b'*120 + '")\n'], C, ['*** HISTORY LIMIT', '241'], [], False),
    ('lite-history-seed', 'lite', ['(+ 7 8)\n'], C, ['15'], [], False),
    ('lite-history-up', 'lite', [UP, 13], C, ['15'], [], False),
    ('lite-history-down', 'lite', [UP, DOWN, '(+ 9 8)\n'], C, ['17'], [], False),
]
PLAN = {'lite': LITE + PRODUCT, 'strings': STRINGS + PRODUCT, 'product': PRODUCT, 'no-comfort': NATIVE_CONTROL, 'v240-init': NATIVE_CONTROL + V240_EXTRA, 'base': [], 'walks': PRODUCT}
BOOT_PROMPT = {'lite': C, 'strings': C, 'product': C, 'no-comfort': N, 'v240-init': N, 'base': N, 'walks': C}


def matches(got, prompt):
    return got in prompt if isinstance(prompt, tuple) else got == prompt


def send_counted(m, keys, taken_address, *, timeout=240, now=time.monotonic, sleep=time.sleep):
    """Singleton HWA events, acknowledged by the product consumer counter.

    typebusy=0 also means Xemu abandoned a stalled paste. In particular, a
    large continuation Return can outlast the injector's 60-frame timeout.
    Only queue the next byte after the product took this one; no paste buffer
    or timeout-discard path is involved. This is a boundary oracle, not timing.
    """
    sent = 0
    for key in keys:
        codes = [key] if isinstance(key, int) else [13 if c == '\n' else ord(c) for c in key]
        for code in codes:
            before = m.memory_range(taken_address, 1)[0]
            m.queue_one(code)
            deadline = now()+timeout
            while True:
                after = m.memory_range(taken_address, 1)[0]
                delta = (after-before) & 255
                if delta:
                    R.require(delta == 1, 'unexpected extra input consumption')
                    break
                R.require(now() < deadline, 'product did not consume singleton input')
                sleep(0.02)
            sent += 1
    return dict(transport='singleton-HWA/product-events-taken', sent=sent, consumed=sent)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('out')
    p.add_argument('--medium', choices=sorted(WORLD), required=True)
    a = p.parse_args()
    out = ROOT / 'build' / a.out
    out.mkdir(exist_ok=False)
    medium, medium_sha, elf = WORLD[a.medium]
    assert R.bind(medium)['sha256'] == medium_sha, 'medium'
    assert R.bind(elf)['sha256'] == ELF_SHA[elf], 'elf'
    assert R.bind(L.XEMU)['sha256'] == L.EXPECT['xemu'], 'xemu'
    truth = ElfTruth.read(elf, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
    args = argparse.Namespace(xemu=L.XEMU, rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
                              sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')), timeout=3600)

    class Monitor(R.ProbeMonitor):
        def wait_screen(self, required, timeout=20):
            # Both prompts end in "65>"; the product's first prompt is l65>.
            return super().wait_screen(['65>' if r == N else r for r in required], timeout=180)
    R.ProbeMonitor = Monitor

    def values(m):
        v = {}
        for name in ('nsym', 'npool'):
            s = truth.symbol(name)
            v[name] = dict(address=s.value, used=int.from_bytes(m.memory_range(s.value, s.bytes), 'little'))
        s = truth.symbol('lisp65_comfort_state') if a.medium != 'base' else None
        if s:
            v['comfort_state'] = m.memory_range(s.value, 1)[0]
        return v

    run, rows, error, outputs = None, [], None, None
    try:
        run = R.start_run('rows', medium, out, args)
        m = run['monitor']
        # First stable prompt: the product reaches l65> only after INIT returned
        # and the deferred request was honoured at the first prompt boundary.
        # The cycle counter is read when the prompt row first appears (the
        # emulator runs sleepless, so wall-clock settling would inflate it).
        last, since, cycles, deadline = None, time.monotonic(), None, time.monotonic() + 240
        while time.monotonic() < deadline:
            s = m.screen()
            if s != last:
                last, since = s, time.monotonic()
                cycles = m.cycle_count() if L.active(s) in (N, C) else None
            if cycles is not None and time.monotonic() - since > 3:
                break
            time.sleep(0.05)
        m.command('t1')
        boot = m.screen()
        (out / 'boot.txt').write_text(boot)
        rows.append(dict(id='boot', member='boot', active=L.active(boot), tail=L.lines(boot)[-8:],
                         boot_cycles_upper=cycles, values=values(m),
                         result='PASS' if L.active(boot) == BOOT_PROMPT[a.medium] else 'FAIL'))
        print('boot', rows[-1]['result'], repr(L.active(boot)), cycles, flush=True)
        m.command('t0')
        for rid, member, keys, prompt, want, forbid, read in PLAN[a.medium]:
            before = m.screen()
            t0 = time.monotonic()
            delivery = None
            if member == 'lite':
                delivery = send_counted(m, keys, truth.symbol('C2K_INPUT_EVENTS_TAKEN').value)
            else:
                for k in keys:
                    if isinstance(k, int):
                        m.queue_one(k)
                        time.sleep(0.5)
                    else:
                        m.type_text(k)
            last, since, deadline = None, time.monotonic(), time.monotonic() + 240
            while time.monotonic() < deadline:
                s = m.screen()
                if s != last:
                    last, since = s, time.monotonic()
                done = all(L.fresh(before, s, w) for w in want)
                done = done and (L.active(s) in (N, C) if prompt is None else matches(L.active(s), prompt))
                if done and time.monotonic() - since > 1.5:
                    break
                time.sleep(0.1)
            m.command('t1')
            s = m.screen()
            path = out / f'{len(rows):02d}-{rid}.txt'
            path.write_text(s)
            got = L.active(s)
            ok = (prompt is None or matches(got, prompt)) and all(L.fresh(before, s, w) for w in want) \
                and not any(L.fresh(before, s, f) for f in forbid)
            rows.append(dict(id=rid, member=member, keys=keys, want_prompt=prompt, want_fresh=want,
                             forbid_fresh=forbid, active=got, new_lines=L.new_lines(before, s),
                             tail=L.lines(s)[-8:], seconds=round(time.monotonic() - t0, 2),
                             screen=R.bind(path), values=values(m) if read else None, delivery=delivery,
                             result=('PASS' if ok else 'FAIL') if prompt is not None or want else 'OBSERVED'))
            print(rid, rows[-1]['result'], repr(got), rows[-1]['tail'][-3:], flush=True)
            (out / 'rows.json').write_text(json.dumps(rows, indent=1) + '\n')
            m.command('t0')
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
            status='HALT' if error else 'DONE', error=error, card='comfort-default', medium_role=a.medium,
            world=dict(elf=R.bind(elf), medium=R.bind(medium), xemu=R.bind(L.XEMU)),
            rows=rows, outputs=outputs, driver=R.bind(Path(__file__)),
            passed=sum(r.get('result') == 'PASS' for r in rows),
            failed=[r['id'] for r in rows if r.get('result') == 'FAIL'],
            claim='Emulator observation (keyboard queue, framebuffer and memory reads); '
                  'boot cycles are an upper bound (stable-screen detection), no device timing claim'),
            indent=1) + '\n')


if __name__ == '__main__':
    main()
