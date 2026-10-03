#!/usr/bin/env python3
"""Host proof of the REPL out-of-memory landing fix (2.5.3): endless loop before, recovery after.

Device finding (build/card-253-oom-hang-r1/notes.md): after `*** VM: OUT OF MEMORY` the prompt never
returns on 2.5.2 and 2.5.3 r7.  `mem_oom` (src/mem.c) is set by the failing allocation and cleared
only on the normal-completion path of the repl() line loop; an abort raised inside vm_run longjmps
past that clear, and the first allocating VM op of the next read-line entry then reports OOM again,
forever.  Fix: `mem_oom = 0;` in the setjmp landing of src/repl.c (every landing, not one-shot).

This driver builds scripts/repl-oom-recovery-main.c twice with the host compiler:
  before  with the published 2.5.2 src/repl.c (commit 49d12859, read through the evidence era)
  after   with the working-tree src/repl.c
and runs both.  The harness runs the real repl() loop in the product's read-line shape (bytecode
read-line entry on vm_run) and raises the OOM inside vm_run; see the harness header.

Pinned (receipt): before = HANG (the landing repeats, no input consumed, mem_oom stays 1 although
the collector has free cells again); after = the script completes: one OOM from a local list, three
genuine OOMs while a global list fills the heap (each reported, prompt returns each time, plain
forms still evaluate), then full recovery once the list is dropped.

Usage: repl_oom_recovery_v253_20261002.py generate | check     (receipt is write-once)
Scratch: build/repl-oom-recovery-v253-20261002-live/ (never bound by the receipt).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import evidence_era as E  # noqa: E402

FORMAT = 'lisp65-repl-oom-recovery-v253-20261002'
RECEIPT = ROOT / 'tests/bytecode/dialect-v2/evidence/capability-carrier/repl-oom-recovery-v253-20261002.json'
LIVE = ROOT / 'build/repl-oom-recovery-v253-20261002-live'
BASE_COMMIT = '49d128599c73a5b6eb6b8595431923cd30b84491'      # 2.5.2 published source
HARNESS = 'scripts/repl-oom-recovery-main.c'
SOURCES = ['src/eval.c', 'src/compile.c', 'src/compile_repl.c', 'src/vm.c', 'src/mem.c', 'src/symbol.c',
           'src/reader.c', 'src/printer.c', 'src/io.c', 'src/interrupt.c', 'src/screen.c']
# The product read-line shape (bytecode entry, string arena, numeric errors) on the product's
# 128-slot root stack; a small heap so a list fills it quickly.  Directory index 0 is the entry.
FLAGS = ['-std=c99', '-Wall', '-Wno-unused-function', '-DLISP65_VM', '-DLISP65_VM_GLOBAL_PRIMS',
         '-DLISP65_EVAL_PRIMS', '-DLISP65_EVAL_CONTROL_SF', '-DLISP65_STRING_ARENA', '-DLISP65_NUMERIC_ERRORS',
         '-DLISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY=0', '-DHEAP_CELLS=512', '-DGC_ROOTS=128',
         '-DMAX_SYM=256', '-DNAMEPOOL=4096', '-DVM_DIR_MAX=16', '-DIO_BUF_MAX=16', '-Isrc']
LANDING = re.compile(r'lisp65_error_clear\(\);\n(?:[^\n]*\n){0,4}?\s*mem_oom = 0;\n\s*gc_rootsp = 0;')
EXPECT_AFTER = ['lisp65', '3', 'OOM mem_oom=1', '7', 'OOM mem_oom=1', '11', 'OOM mem_oom=1', '15', 'OOM mem_oom=1',
                'nil', '40', '19', 'DONE landings=5']


class OomError(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise OomError(message)


def build(name, repl_source):
    out = LIVE / name
    cc = os.environ.get('HOSTCC', 'cc').split()
    cmd = cc + FLAGS + [str(repl_source), HARNESS] + SOURCES + ['-Wl,--wrap=emit_str', '-o', str(out)]
    done = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    require(done.returncode == 0, 'host build failed (%s):\n%s' % (name, done.stdout))
    return out


def run(binary):
    done = subprocess.run([str(binary)], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, timeout=60)
    return done.returncode, done.stdout


def normalise(text):
    """Transcript without host-dependent counters: one token per line the REPL printed."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('repl-oom-recovery:'):
            continue
        m = re.fullmatch(r'\[landing \d+ mem_oom=(\d) free=(\d+)\]\*\*\* VM: OUT OF MEMORY', line)
        if m:
            out.append('OOM mem_oom=' + m.group(1))
            continue
        m = re.fullmatch(r'\[landing \d+ mem_oom=(\d) free=(\d+)\]', line)
        if m:
            continue                      # the landing that ends the run (HANG / DONE follows)
        out.append(line)
    return out


def free_at_landings(text):
    return [int(n) for n in re.findall(r'\[landing \d+ mem_oom=\d free=(\d+)\]', text)]


def render():
    LIVE.mkdir(parents=True, exist_ok=True)
    before_text = E.era_blob(BASE_COMMIT, 'src/repl.c').decode()
    after_text = (ROOT / 'src/repl.c').read_text()
    require(not LANDING.search(before_text), 'the 2.5.2 landing already clears mem_oom')
    require(len(LANDING.findall(after_text)) == 1, 'src/repl.c: mem_oom is not cleared in the setjmp landing')
    require(after_text.count('setjmp(lisp_toplevel)') == 1, 'src/repl.c: more than one top-level landing')
    era = LIVE / 'repl-252.c'
    era.write_text(before_text)

    rc_before, out_before = run(build('before', era))
    rc_after, out_after = run(build('after', ROOT / 'src/repl.c'))
    (LIVE / 'before.txt').write_text(out_before)
    (LIVE / 'after.txt').write_text(out_after)

    nb, na = normalise(out_before), normalise(out_after)
    require(rc_before == 3 and nb[-1].startswith('HANG: 9 landings, input not consumed, mem_oom=1'),
            'before: the 2.5.2 landing no longer reproduces the endless loop (rc %d)\n%s' % (rc_before, out_before))
    require(nb[:2] == ['lisp65', '3'] and nb[2:-1] == ['OOM mem_oom=1'] * 8, 'before: transcript drift: %r' % (nb,))
    free_before = free_at_landings(out_before)
    require(free_before[0] == 0 and all(n > 100 for n in free_before[1:]),
            'before: the repeated OOM is not a stuck flag (free cells %r)' % (free_before,))
    require(rc_after == 0 and na == EXPECT_AFTER, 'after: no recovery (rc %d): %r\n%s' % (rc_after, na, out_after))
    free_after = free_at_landings(out_after)
    require(free_after[:4] == [0, 0, 0, 0] and free_after[4] > 100, 'after: free cells at landings %r' % (free_after,))

    return {
        'format': FORMAT,
        'verdict': 'PASS',
        'claim': 'mem_oom is cleared at every repl() landing: after *** VM: OUT OF MEMORY the read-line '
                 'entry runs again; a genuinely full heap still reports each time and the prompt returns; '
                 'the published 2.5.2 landing loops forever on a stuck flag',
        'inputs': {
            'before_repl': E.era_bind(BASE_COMMIT, 'src/repl.c'),
            'after_repl': 'src/repl.c',          # living source: checked structurally, not hash-pinned
            'harness': HARNESS,
            'flags': FLAGS,
            'sources': SOURCES,
        },
        'before': {'exit': rc_before, 'verdict': 'HANG', 'transcript': nb,
                   'free_cells_at_first_landing': free_before[0],
                   'later_landings_have_free_cells': True},
        'after': {'exit': rc_after, 'verdict': 'RECOVERED', 'transcript': na,
                  'genuine_ooms_reported': 4, 'landings': 5},
    }


def canonical(value):
    return (json.dumps(value, indent=1, sort_keys=True) + '\n').encode()


def main(argv):
    if argv not in (['generate'], ['check']):
        raise SystemExit('usage: repl_oom_recovery_v253_20261002.py generate | check')
    os.chdir(ROOT)
    try:
        data = canonical(render())
        if argv == ['generate']:
            with RECEIPT.open('xb') as stream:
                stream.write(data)
        else:
            require(RECEIPT.read_bytes() == data, 'receipt drift: ' + str(RECEIPT.relative_to(ROOT)))
    except OomError as exc:
        print('repl-oom-recovery: FAIL: %s' % exc, file=sys.stderr)
        return 1
    print('repl-oom-recovery: PASS before=HANG after=RECOVERED (4 OOM reports, prompt returns each time)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
