#!/usr/bin/env python3
"""2.5.5 editor key cost gate: what one editing key costs on the host VM, with ceilings.

2.5.5 made typing in the IDE editor cheaper (build/scope-editor-typing-r1,
build/card-255-typing-r1): a printable key no longer searches the keymap
tables, the accessors of the key path are written out, and the loop no longer
stores a flushed copy of the buffer before every key.  This gate keeps that
gain: for insert, Backspace and Return at fixed points it counts, in the
generated IDE core suite, for ide-step and for ide-render separately

  VM instructions
  calls + tail calls
  code-object reads   model of the VM's single execution buffer (src/vm.c,
                      VM_CODEBUF = 56 in the product recipe): entry 1 read,
                      resume after a foreign callee 2 header reads and the
                      window, pc outside the window 1 read.  On the delivered
                      2.5.4 product world this model equals the emulator's
                      vm_object_load counts exactly at six measured points.
  cells               heap cells allocated

and refuses any count above its ceiling (the values measured on the 2.5.5
candidate).  A count BELOW a ceiling passes and is reported, so an
improvement needs no new gate, only (optionally) tighter ceilings.
It also refuses a loop that stores the buffer per key again: ide-run must not
name %ide-persist-state and `ide` must name it exactly once.

Scope: this gate measures the LIBRARY world -- ide-step and ide-render of the
generated IDE core suite, tracked inputs only -- not the delivered product
loop, whose projected world lives under build/ and is counted by the Seed
tooling (build/card-255-typing-r1/host-counts.json for the candidate).  The
two worlds share ide-step and ide-render source; the loop differs.

Inputs: lib/ through the generated suite
build/bytecode/dialect-v2/suites/p0-ide-core-lib.json (prerequisite
v2-workbench-artifacts) and lib/ide-ui.lisp.  Writes nothing.

Usage: c2_v255_editor_key_cost_20261006.py selftest | check | measure
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))

SUITE = 'build/bytecode/dialect-v2/suites/p0-ide-core-lib.json'
UI = 'lib/ide-ui.lisp'
CODEBUF = 56
MAX_STEPS = 2000000
INSERT, BACKSPACE, RETURN = 97, 20, 13
# (label, lines of the buffer, cursor line, cursor column, key)
POINTS = tuple(
    (f'{name}@{column} line 1', ['b' * column], 0, column, key)
    for column in (1, 20, 39) for name, key in (('insert', INSERT), ('backspace', BACKSPACE), ('return', RETURN))
) + tuple(
    (f'{name}@10 line 20', ['b' * 10] * 20, 19, 10, key)
    for name, key in (('insert', INSERT), ('backspace', BACKSPACE), ('return', RETURN)))
KINDS = ('instructions', 'calls', 'reads', 'cells')
# Measured on the 2.5.5 candidate (2026-10-06), after one insert + Backspace warm-up at the point (line cache built,
# screen painted): {point: {phase: [instructions, calls, reads, cells]}}.
CEILINGS = {
    'insert@1 line 1': {'step': [327, 17, 54, 24], 'render': [472, 16, 51, 10]},
    'backspace@1 line 1': {'step': [363, 20, 66, 23], 'render': [461, 16, 51, 10]},
    'return@1 line 1': {'step': [568, 40, 114, 46], 'render': [7094, 395, 681, 48]},
    'insert@20 line 1': {'step': [327, 17, 54, 24], 'render': [472, 16, 51, 10]},
    'backspace@20 line 1': {'step': [363, 20, 66, 23], 'render': [465, 16, 51, 10]},
    'return@20 line 1': {'step': [1537, 78, 190, 103], 'render': [7151, 395, 681, 48]},
    'insert@39 line 1': {'step': [327, 17, 54, 24], 'render': [472, 16, 51, 10]},
    'backspace@39 line 1': {'step': [363, 20, 66, 23], 'render': [465, 16, 51, 10]},
    'return@39 line 1': {'step': [2506, 116, 266, 160], 'render': [7208, 395, 681, 48]},
    'insert@10 line 20': {'step': [327, 17, 54, 24], 'render': [472, 16, 51, 10]},
    'backspace@10 line 20': {'step': [363, 20, 66, 23], 'render': [465, 16, 51, 10]},
    'return@10 line 20': {'step': [10508, 362, 910, 339], 'render': [7864, 452, 795, 50]},
}


class GateError(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise GateError(message)


class Trace:
    """Counts for one run_named call; the read model follows the buffer owner across nested calls."""

    def __init__(self):
        self.instructions = self.calls = self.reads = 0
        self.entered, self.resident, self.win, self.winlen = False, None, 0, 0

    def enter(self, name, code, args):
        self.entered = True

    def exit(self, name, code):
        pass

    def call(self, caller, kind, target, argc, pc=None, resolved=False):
        if kind in ('CALL', 'TAILCALL'):
            self.calls += 1

    def instruction(self, name, code, pc, spec, operand):
        self.instructions += 1
        self.reads += self.reads_for(id(code), 7 + 2 * len(code.littab), len(code.payload), pc)

    def reads_for(self, ident, header, payload, pc):
        window, count = CODEBUF - header, 0
        if self.entered:
            self.entered = False
            self.resident, self.win, self.winlen = ident, 0, min(payload, window)
            count += 1
        elif self.resident != ident:
            self.resident, self.win, self.winlen = ident, pc, 0
            count += 2
        need = payload if payload - pc < 3 else pc + 3
        if pc < self.win or self.win + self.winlen < need:
            self.win, self.winlen = pc, min(payload - pc, window)
            count += 1
        return count


def measure():
    from ide_bytecode_dynamic_report import Runtime
    require((ROOT / SUITE).is_file(), 'generated IDE suite missing (run v2-workbench-artifacts): ' + SUITE)
    runtime = Runtime(ROOT / SUITE, max_steps=MAX_STEPS)
    result = {}
    for label, lines, line, column, key in POINTS:
        state = runtime.make_state(list(lines), line=line, column=column, rendered=True)
        for warm in (INSERT, BACKSPACE):          # steady state: the line cache exists, the screen is painted
            state = runtime.run_named('ide-render', [runtime.run_named('ide-step', [state, runtime.key_event(warm)])])
        event = runtime.key_event(key)
        row = {}
        for phase, name, args in (('step', 'ide-step', lambda: [state, event]), ('render', 'ide-render', lambda: [state])):
            trace, before = Trace(), len(runtime.heap.cells)
            state = runtime.run_named(name, args(), trace=trace)
            row[phase] = [trace.instructions, trace.calls, trace.reads, len(runtime.heap.cells) - before]
        result[label] = row
    return result


def defun_text(source, name):
    match = re.search(r'^\(defun %s[ \n]' % re.escape(name), source, re.M)
    require(match is not None, 'defun missing: ' + name)
    depth, i = 0, match.start()
    while True:
        c = source[i]
        if c == '"':
            i += 1
            while source[i] != '"':
                i += 2 if source[i] == '\\' else 1
        elif c == ';':
            while source[i] != '\n':
                i += 1
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return source[match.start():i + 1]
        i += 1


def loop_problems(source):
    """The loop stores the buffer once at entry, never per key."""
    found = []
    code = lambda text: '\n'.join(line.split(';')[0] for line in text.splitlines())   # noqa: E731
    if '%ide-persist-state' in code(defun_text(source, 'ide-run')):
        found.append('ide-run stores the buffer on every pass (%ide-persist-state)')
    matches = [m.start() for m in re.finditer(r'^\(defun ide \(', source, re.M)]
    require(matches, 'defun missing: ide')
    last = defun_text(source[matches[-1]:], 'ide')
    if code(last).count('%ide-persist-state') != 1:
        found.append('ide does not store the buffer exactly once at entry')
    return found


def problems(measured, ceilings):
    found = []
    if set(measured) != set(ceilings):
        return ['point population differs from the ceilings']
    for label in sorted(measured):
        for phase in ('step', 'render'):
            for kind, got, limit in zip(KINDS, measured[label][phase], ceilings[label][phase]):
                if got > limit:
                    found.append(f'{label} {phase}: {kind} {got} > {limit}')
    return found


def check():
    measured = measure()
    found = problems(measured, CEILINGS) + loop_problems((ROOT / UI).read_text())
    below = {label: {phase: [c - m for m, c in zip(measured[label][phase], CEILINGS[label][phase])] for phase in ('step', 'render')}
             for label in measured if measured[label] != CEILINGS.get(label)}
    return dict(status='PASS' if not found else 'FAIL', problems=found, points=len(measured), kinds=list(KINDS),
                measured=measured, below_ceiling=below)


def selftest():
    rejected = []
    base = {'p': {'step': [10, 2, 5, 3], 'render': [20, 4, 9, 1]}}
    require(problems(base, base) == [], 'equal counts refused')
    require(problems({'p': {'step': [9, 2, 5, 3], 'render': [20, 4, 9, 0]}}, base) == [], 'lower counts refused')
    for index, kind in enumerate(KINDS):
        for phase in ('step', 'render'):
            worse = json.loads(json.dumps(base))
            worse['p'][phase][index] += 1
            require(problems(worse, base) == [f'p {phase}: {kind} {worse["p"][phase][index]} > {base["p"][phase][index]}'],
                    'one more ' + kind + ' accepted')
            rejected.append(f'{phase}: one more {kind[:-1] if kind != "calls" else "call"}')
    require(problems({'q': base['p']}, base), 'another point population accepted')
    rejected.append('another point population')
    # read model: entry, window refill, resume after a foreign callee, self-recursion without a reload
    t = Trace()
    t.enter('f', None, ())
    require(t.reads_for(1, 17, 100, 0) == 1 and t.reads_for(1, 17, 100, 30) == 0 and t.reads_for(1, 17, 100, 40) == 1,
            'entry / window model')
    t.enter('g', None, ())
    require(t.reads_for(2, 7, 10, 0) == 1 and t.reads_for(1, 17, 100, 43) == 3, 'foreign callee / resume model')
    require(t.reads_for(1, 17, 100, 44) == 0 and t.reads_for(1, 17, 100, 10) == 1, 'window move model')
    rejected.append('read model: entry 1, refill 1, resume 3')
    good = ('(defun ide-run (state)\n  (progn\n    (%ide-input-open)\n    (%ide-poll state)))\n'
            '(defun ide (&rest name)\n  (ide-run (%ide-persist-state (%ide-init name))))\n')
    require(loop_problems(good) == [], 'good loop refused')
    require(loop_problems(good.replace('(%ide-poll state)', '(%ide-poll (%ide-persist-state state))')), 'persist per key accepted')
    require(loop_problems(good.replace('(%ide-persist-state (%ide-init name))', '(%ide-init name)')), 'no persist at entry accepted')
    require(loop_problems(good.replace('    (%ide-input-open)\n', '    ;; no %ide-persist-state here\n    (%ide-input-open)\n')) == [],
            'comment counted as code')
    rejected += ['persist on every pass', 'no persist at entry']
    require(loop_problems((ROOT / UI).read_text()) == [], 'the tree loop stores per key')
    require(len(CEILINGS) == len(POINTS) == 12 and all(len(v[p]) == 4 for v in CEILINGS.values() for p in ('step', 'render')),
            'ceiling table incomplete')
    return dict(status='PASS', negative_controls=rejected, points=len(POINTS), emulator_runs=0)


def main(argv):
    require(argv in (['selftest'], ['check'], ['measure']), 'usage: selftest | check | measure')
    if argv == ['measure']:
        result = measure()
        print('CEILINGS = {')
        for label, row in result.items():
            print(f'    {label!r}: {row!r},')
        print('}')
        return 0
    result = selftest() if argv == ['selftest'] else check()
    print(json.dumps(result if argv == ['selftest'] else {k: v for k, v in result.items() if k != 'measured'}, indent=1))
    print('c2-v255-editor-key-cost: ' + result['status'])
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main(sys.argv[1:]))
    except GateError as error:
        raise SystemExit('c2-v255-editor-key-cost: FAIL: ' + str(error))
