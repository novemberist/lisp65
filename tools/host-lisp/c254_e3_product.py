#!/usr/bin/env python3
"""2.5.4 product-world E3 check (reviewer decision D-E3): accepted-edit persistence under RUN/STOP on the
PROJECTED PRODUCT IDE world, with two controls that must fail.

Library used by c254_product.py (preflight: reduced sweep; `c254_seed_producer.py e3`: exhaustive sweep).
Installed copy of the harness of build/card-254-e3-product-r1 (pw.py, e3_product.py, make_worlds.py,
probe_world.py), turned into functions; rule, cases and point sets are unchanged.  Nothing is imported from
build/; nothing from lib/ is read: a world is ONE disk-lib suite JSON (the projected product IDE suite of a
preflight with its resident suites) compiled by the product emission route
(bytecode_p0_stdlib._compile_suite: suite function list, private inlining, residents, strict arity,
dialect-v2 ABI, prebuilt primitives).  The harness world is the product image, not a model of it: run()
refuses unless the compiled blob of world A is byte-identical to the image the preflight emitted.

Worlds
  A       the projected product IDE suite as the preflight wrote it (PRODUCT_SEAMS = proposal A)
  noA     A with every 'replace' product seam reverted (control: the loss E3 fixes must be present)
  nocopy  A with the Return copy in ide-split-line replaced by the consuming nreverse (control: must fail)
The control sources are written below <out>/worlds/ (the caller's write-once directory); they are outputs of
this tool, never inputs of a receipt.

Rule (unchanged from the library harness build/card-254-ide-r1/harness/e3_harness.py): with j keys taken from
the queue when the abort hits, the re-entered buffer text must equal the text after j-1 or j keys.  The
stricter rule (text after k keys, floor <= k <= j, floor = keys accepted when the last poll-key was entered)
is evaluated as well and must also hold in world A.
Abort points: `lib` = the library point set (uniform grid 400 + dense windows around every key poll and over
every Return step, plus the render tail in the `run` shape); `all` = EVERY VM instruction boundary.
Shapes: `drain` (all keys through %ide-drain-pending, then persist) and `run` (the real product loop
ide-run: first key through read-key, the rest through poll-key, batch render, next iteration's persist).

Modes
  reduced     5 library cases x 2 shapes, point set `lib`, worlds A / nocopy / noA, plus the pending-C-x row
              through the real (ide "audit") entry.  About 16,000 abort points per world.
  exhaustive  A: 5 library + 5 extra cases x 2 shapes, EVERY instruction boundary, plus the multi-buffer
              sweep; nocopy / noA: the same without the 86-key fill-wrap case; multi-buffer control on noA.
PASS = world A: 0 violations (both rules), every no-abort and poll-boundary text correct, pending-C-x row ok;
       nocopy: violations > 0, all in cases containing a Return;  noA: violations > 0 and the pending-C-x
       row fails;  object deltas noA -> A exactly {%ide-drain-pending, ide}, nocopy -> A exactly {ide-split-line}.
"""
from __future__ import annotations
import hashlib
import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
import bytecode_p0 as B
import bytecode_p0_compiler as C
import bytecode_p0_stdlib as S

NOCOPY_FILE = 'ide-buffer.lisp'
NOCOPY_EDIT = ('(%string-from-codes (%ide-rev-onto (car (cdr cache)) nil))',
               '(%string-from-codes (nreverse (car (cdr cache))))')
DRIVERS = ('(defun h-persist (state) (%ide-persist-state state))',
           '(defun h-with-point (buf point) (%ide-buffer-with-point buf point))',
           '(defun h-resume (name) (%ide-resume-buffer name))',
           '(defun h-start (buf) (ide-render (ide-make-state buf)))')
CASES = (
    ('type3', 'abc', ['']),
    ('type-return-type', 'ab\rcd', ['']),
    ('long-line-return', 'x' * 30 + '\r' + 'y', ['(defun f ()']),
    ('backspace-mix', 'abc\x14\x14d\rz', ['seed']),
    ('cx-seam-type', 'a\x18fb\rc', ['']),        # C-x f (unbound seam key) inside the batch
)
# Beyond the library harness (same rule): fill-column wrap, cursor motion inside a typed run, consecutive
# Returns, kill/yank, C-x prefix as the LAST key of the batch.
EXTRA = (
    ('x-fill-wrap', 'w' * 84 + '\rz', ['']),
    ('x-motion-mid-edit', 'abc\x9dX\rq', ['seed']),
    ('x-two-returns', 'a\r\rb\r', ['one', 'two']),
    ('x-kill-yank', 'abc\x01\x0b\x19z', ['']),
    ('x-cx-last', 'ab\x18', ['']),
)
ALLBUF = (('b-cycle-next', 'a\x18\x0eb\rc', ['']),
          ('b-cycle-prev-twice', 'a\x18\x10b\x18\x10c\rd', ['']),
          ('b-plain', 'ab\rc', ['']))
GRID = 400
SHAPES = ('drain', 'run')


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def bind(path):
    raw = Path(path).read_bytes()
    return dict(path=str(path), sha256=sha256(raw), bytes=len(raw))


def world(suite_path, drivers=DRIVERS):
    """Compile one suite by the emission route.  Returns the world dict; `blob` is the base-0 image."""
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 100000))
    suite = S._read_suite(str(suite_path))
    (heap, names, code_by_name, entry_flags, resident_flags, bundle, directory, _cases, _entries,
     inliner) = S._compile_suite(suite, include_cases=False)
    image = S._compile_suite(S._read_suite(str(suite_path)), base_addr=0, include_cases=False)[5]
    directory = dict(directory)
    code_names = {id(code): heap.symbol_name(sym) for sym, code in directory.items()}
    for src in drivers:
        form = C.parse_one(src)
        form = form[:3] + [S._expand_case_expr(suite, inliner, x) for x in form[3:]]
        name, code, helpers = C.compile_top_form_with_helpers(
            form, heap, strict_arity=True, abi_profile=suite.get('abi_profile'), prebuilt_primitives=True)
        for n, c in [(name, code)] + helpers:
            directory[heap.intern(n)] = c
            code_names[id(c)] = n
    profile, ledger = S._suite_abi(suite)
    return dict(path=str(suite_path), suite=suite, heap=heap, names=names, directory=directory,
                code_names=code_names, profile=profile, ledger=ledger,
                macro_symbols=S._macro_symbol_objs(heap, entry_flags, resident_flags),
                sizes={n: len(code_by_name[n].payload) for n in names},
                blob_sha256=sha256(image.blob), blob_bytes=len(image.blob), objects=len(names),
                sources=[bind(p) for p in suite['sources']])


def make_variant(a_suite_path, out, name, file, edits):
    """A control world: the A suite with ONE source replaced by an edited copy below out/."""
    suite = json.loads(Path(a_suite_path).read_text())
    hits = [p for p in suite['sources'] if Path(p).name == file]
    assert len(hits) == 1, ('control source', name, file, len(hits))
    text = Path(hits[0]).read_text()
    for old, new in edits:
        assert text.count(old) == 1, ('control edit: old text count', name, text.count(old))
        text = text.replace(old, new)
    target = Path(out) / name / file
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x') as stream:
        stream.write(text)
    suite['sources'] = [str(target) if p == hits[0] else p for p in suite['sources']]
    path = Path(out) / name / 'suite.json'
    with path.open('x') as stream:
        stream.write(json.dumps(suite, indent=1) + '\n')
    return path, dict(world=name, suite=str(path), file=str(target), sha256=sha256(text.encode()),
                      edits=[dict(old_sha256=sha256(o.encode()), new_sha256=sha256(n.encode())) for o, n in edits])


class Stop(Exception):
    pass


class Sweep:
    """One compiled world plus the sweep machinery (the module-level state of e3_product.py)."""

    def __init__(self, w, allbuf=False):
        self.w, self.allbuf = w, allbuf
        self.EVAL = self.vm([])

    def vm(self, keys, stop_at_poll=False):
        return _VM(self, keys, stop_at_poll)

    def all_text(self, v):
        alist, rows = v.sym('ide-buffers'), []
        while alist != B.NIL:
            pair = v.heap.car(alist)
            rows.append(v.heap.string_to_text(v.heap.car(pair)) + ':' + self.text_of(v, v.heap.cdr(pair)))
            alist = v.heap.cdr(alist)
        return '\n--\n'.join(sorted(rows))

    @staticmethod
    def text_of(v, buf):
        lines, out = v.call('ide-buffer-lines', buf), []
        while lines != B.NIL:
            out.append(v.heap.string_to_text(v.heap.car(lines)))
            lines = v.heap.cdr(lines)
        return '\n'.join(out)

    def make_buffer(self, v, initial):
        if self.allbuf:
            v.call('%ide-store-buffer', v.call('ide-make-buffer', v.text('other'), v.lst([v.text('zz')])))
        name = v.text('audit')
        buf = v.call('ide-make-buffer', name, v.lst([v.text(t) for t in initial]))
        buf = v.call('h-with-point', buf, v.heap.cons(B.mkfix(len(initial) - 1), B.mkfix(len(initial[-1]))))
        v.call('%ide-store-buffer', buf)
        return name, buf

    def sweep_once(self, shape, keys, initial, sample):
        """One session; {n: (accepted, floor, text)} for the sampled abort points (heap cloned before
        instruction n+1 executes = the state a max_steps = n abort leaves, resumed on the clone)."""
        v = self.vm(keys)
        v.heap.set_symbol_value(v.heap.intern('ide-event-command'), B.NIL)
        _name, buf = self.make_buffer(v, initial)
        if shape == 'drain':
            state = v.call('ide-make-state', buf)
            v.sample = sample
            v.call('%ide-drain-pending', state)
            v.sample = None
            if sample is True or v.steps in sample:
                v.take(v.steps)                    # after the last instruction, before the batch-end persist
        else:
            state = v.call('h-start', buf)
            v.sample = sample
            try:
                v.call('ide-run', state)
                raise AssertionError('ide-run returned without C-x C-c')
            except Stop:
                pass
        return {n: (a, f, text) for n, a, f, text in v.samples}

    def session(self, shape, keys, initial, stop_at_poll=False, stop_at_step=None):
        v = self.vm(keys, stop_at_poll)
        v.heap.set_symbol_value(v.heap.intern('ide-event-command'), B.NIL)
        name, buf = self.make_buffer(v, initial)
        aborted, steps = None, None
        try:
            if shape == 'drain':
                state = v.call('ide-make-state', buf)
                if stop_at_step is not None:
                    v.max_steps = stop_at_step
                state = v.call('%ide-drain-pending', state)
                steps = v.steps
                v.max_steps = 10 ** 8
                v.call('h-persist', state)
            else:
                state = v.call('h-start', buf)
                if stop_at_step is not None:
                    v.max_steps = stop_at_step
                v.call('ide-run', state)
                raise AssertionError('ide-run returned without C-x C-c')
        except Stop as e:
            aborted = 'poll' if 'poll-key' in str(e) else 'end'
            steps = v.steps
        except B.VMError as e:
            if 'max_steps' not in str(e):
                raise
            aborted = 'step'
        v.max_steps = 10 ** 8
        accepted, floor = v.accepted, v.floor
        polls, all_polls = list(v.poll_steps), list(v.all_polls)
        v.pending = []
        v.stop_at_poll = False
        resumed = v.call('h-resume', name)
        return dict(aborted=aborted, accepted=accepted, floor=floor, steps=steps, polls=polls, all_polls=all_polls,
                    text=self.all_text(v) if self.allbuf else self.text_of(v, resumed))

    def case(self, shape, label, keys, initial, points_mode, equivalence=False):
        exp = [self.session(shape, keys[:k], initial)['text'] for k in range(len(keys) + 1)]
        full = self.session(shape, keys, initial)
        poll = self.session(shape, keys, initial, stop_at_poll=True)
        total, polls = full['steps'], full['polls']
        points = set(range(1, total + 1, max(1, total // GRID)))
        for i, ch in enumerate(keys):
            if ch == '\r' and i + 1 < len(polls):
                points.update(range(max(1, polls[i] - 2), min(total, polls[i + 1] + 3) + 1))
            if i < len(polls):
                points.update(range(max(1, polls[i] - 3), min(total, polls[i] + 4)))
        if shape == 'run':                     # dense over the tail: last poll .. end (render + next persist)
            last = full['all_polls'][-1] if full['all_polls'] else polls[-1]
            points.update(range(max(1, last - 3), min(total, last + 40)))
            points.update(range(max(1, total - 60), total))
        lib_points = set(p for p in points if p <= total - (0 if shape == 'drain' else 1))
        points = set(range(1, total + (1 if shape == 'drain' else 0))) if points_mode == 'all' else lib_points
        results = self.sweep_once(shape, keys, initial, True if points_mode == 'all' else points)
        assert set(results) == points, (len(results), len(points), sorted(points - set(results))[:5])
        equiv = None
        if equivalence:                        # snapshot method against the library method (one re-run per point)
            probe = sorted(points)[::max(1, len(points) // 40)]
            diff = []
            for n in probe:
                r = self.session(shape, keys, initial, stop_at_step=n)
                if (r['accepted'], r['floor'], r['text']) != results[n]:
                    diff.append(n)
            assert not diff, ('snapshot sweep differs from the re-run method', shape, label, diff[:5])
            equiv = dict(points=len(probe), differences=0)
        bad, bad_strict, kept, lib_bad = [], [], {}, 0
        for n in sorted(points):
            j, f, text = results[n]
            k = exp.index(text) if text in exp else None
            if text in (exp[max(j - 1, 0)], exp[j]):
                kk = exp.index(text)
                kept[kk] = kept.get(kk, 0) + 1
            else:
                bad.append(dict(step=n, accepted=j, floor=f, matched_k=k, text=text))
                lib_bad += n in lib_points
            if not any(text == exp[i] for i in range(f, j + 1)):
                bad_strict.append(dict(step=n, accepted=j, floor=f, matched_k=k, text=text))
        return dict(keys=len(keys), has_return='\r' in keys, steps=total, expected_final=exp[-1],
                    no_abort_ok=full['text'] == exp[-1], poll_abort_ok=poll['text'] == exp[-1],
                    sweep_points=len(points), lib_point_set=len(lib_points), lib_point_set_violations=lib_bad,
                    sweep_violations=len(bad), strict_violations=len(bad_strict),
                    resumed_k_histogram={str(k): kept[k] for k in sorted(kept)},
                    first_violations=bad[:3], last_violation=bad[-1] if bad else None,
                    snapshot_equivalence=equiv)

    def d4_row(self):
        """C-x pending when RUN/STOP hits, then the REAL (ide "audit") re-entry with 'f' as its first key."""
        v = self.vm([])
        v.heap.set_symbol_value(v.heap.intern('ide-event-command'), B.NIL)
        name, buf = self.make_buffer(v, ['ab'])
        state = v.call('h-start', buf)
        v.call('ide-step', state, v.key(24))
        pending = v.sym('ide-event-command')
        v.pending = ['f']                      # RUN/STOP here; re-entry (ide "audit"), key 'f', then queue empty
        try:
            v.call('ide', name)
        except Stop:
            pass
        after = v.sym('ide-event-command')
        line = v.py(v.call('ide-current-line', v.call('h-resume', name)))
        return dict(pending_before_stop=v.py(pending), prefix_after_first_key=v.py(after), first_key_line=line,
                    ok=(v.py(pending) == 24 and line == 'abf'))

    def run(self, cases, points_mode, log, equivalence=False):
        t0 = time.monotonic()
        summary = {}
        for shape in SHAPES:
            for label, keys, initial in cases:
                row = self.case(shape, label, keys, initial, points_mode, equivalence)
                summary[shape + ':' + label] = row
                log('  %s %s steps %d points %d violations %d strict %d' % (
                    shape, label, row['steps'], row['sweep_points'], row['sweep_violations'], row['strict_violations']))
        return dict(points=points_mode, allbuf=self.allbuf, cases=[c[0] for c in cases],
                    total_points=sum(s['sweep_points'] for s in summary.values()),
                    total_violations=sum(s['sweep_violations'] for s in summary.values()),
                    total_strict_violations=sum(s['strict_violations'] for s in summary.values()),
                    lib_point_set_total=sum(s['lib_point_set'] for s in summary.values()),
                    lib_point_set_violations=sum(s['lib_point_set_violations'] for s in summary.values()),
                    violations_outside_return_cases=sum(s['sweep_violations'] for s in summary.values() if not s['has_return']),
                    all_poll_aborts_ok=all(s['poll_abort_ok'] for s in summary.values()),
                    all_no_abort_ok=all(s['no_abort_ok'] for s in summary.values()),
                    d4_prefix_reset=self.d4_row(), summary=summary, seconds=round(time.monotonic() - t0, 1))


class _VM(B.P0VM):
    def __init__(self, sweep, keys, stop_at_poll=False):
        w = sweep.w
        super().__init__(heap=w['heap'].clone(), directory=w['directory'], code_names=w['code_names'],
                         macro_symbols=w['macro_symbols'], max_steps=10 ** 8,
                         max_call_args=w['suite'].get('max_call_args'),
                         abi_profile=w['profile'], abi_ledger=w['ledger'],
                         delivered_callprims=w['suite'].get('delivered_callprims'))
        self.sweep, self.w = sweep, w
        self.pending = list(keys)
        self.stop_at_poll = stop_at_poll
        self.accepted = 0
        self.floor = 0
        self.poll_steps = []       # step index at which key i was handed out
        self.all_polls = []
        self.sample = None         # None | True (every boundary) | set of n
        self.samples = []

    def call(self, n, *a):
        return self.run(self.w['directory'][self.heap.intern(n)], list(a))

    def lst(self, items):
        out = B.NIL
        for x in reversed(items):
            out = self.heap.cons(x, out)
        return out

    def key(self, code):
        return self.lst([self.heap.intern('key'), B.mkfix(code), B.NIL])

    def text(self, s):
        return self.heap.string_from_text(s)

    def sym(self, name):
        return self.heap.symbol_value(self.heap.intern(name))

    def py(self, o):
        if o == B.NIL:
            return None
        if B.is_fix(o):
            return B.fixval(o)
        try:
            return self.heap.string_to_text(o)
        except Exception:
            return repr(o)

    def _trace_instruction_state(self, name, code, pc, operand_depth, frame_slots):
        if self.sample is not None:
            n = self.steps - 1     # n instructions have completed
            if n >= 1 and (self.sample is True or n in self.sample):
                self.take(n)

    def take(self, n):
        ev = self.sweep.EVAL
        ev.heap = self.heap.clone()
        ev.max_steps = 10 ** 8
        if self.sweep.allbuf:
            self.samples.append((n, self.accepted, self.floor, self.sweep.all_text(ev)))
            return
        resumed = ev.call('h-resume', ev.text('audit'))
        self.samples.append((n, self.accepted, self.floor, self.sweep.text_of(ev, resumed)))

    def _callprim(self, p, n, stack, **kw):
        if p == 14:                                  # poll-key
            self.floor = self.accepted
            self.all_polls.append(self.steps)
            if self.pending:
                self.poll_steps.append(self.steps)
                self.accepted += 1
                return self.key(ord(self.pending.pop(0)))
            if self.stop_at_poll:
                raise Stop('RUN/STOP at the next poll-key boundary')
            return B.NIL
        if p == 13:                                  # read-key (blocking)
            if self.pending:
                self.poll_steps.append(self.steps)
                self.accepted += 1
                return self.key(ord(self.pending.pop(0)))
            raise Stop('queue empty at the blocking read-key: end of session')
        return super()._callprim(p, n, stack, **kw)


def verdict(runs, deltas):
    """The discriminating rule.  Returns the list of problems (empty = PASS)."""
    problems = []
    for name, r in runs.items():
        world_key = name.split(':')[0]
        if world_key == 'A':
            if r['total_points'] <= 0 or r['total_violations'] or r['total_strict_violations']:
                problems.append(name + ': violations in the product world (or no points)')
            if not (r['all_poll_aborts_ok'] and r['all_no_abort_ok'] and r['d4_prefix_reset']['ok']):
                problems.append(name + ': no-abort / poll-boundary text or pending-C-x row wrong')
        elif world_key == 'nocopy':
            if r['total_violations'] <= 0:
                problems.append(name + ': the no-copy control does not fail (sweep does not discriminate)')
            if r['violations_outside_return_cases']:
                problems.append(name + ': no-copy violations outside the Return cases')
            if not (r['all_poll_aborts_ok'] and r['all_no_abort_ok']):
                problems.append(name + ': no-copy control broken beyond the abort window')
        elif world_key == 'noA':
            if r['total_violations'] <= 0:
                problems.append(name + ': the control without proposal A does not fail')
            if not r['allbuf'] and r['d4_prefix_reset']['ok']:
                problems.append(name + ': pending-C-x row passes without the seam')
        else:
            problems.append('unknown world ' + name)
    if sorted(deltas['noA->A']) != ['%ide-drain-pending', 'ide']:
        problems.append('proposal A changes other objects than %ide-drain-pending / ide: ' + repr(sorted(deltas['noA->A'])))
    if sorted(deltas['nocopy->A']) != ['ide-split-line']:
        problems.append('the no-copy control changes other objects than ide-split-line: ' + repr(sorted(deltas['nocopy->A'])))
    wanted = {'A', 'nocopy', 'noA'}
    if {n.split(':')[0] for n in runs} != wanted:
        problems.append('a world was not swept')
    return problems


def run(suite_path, out, *, mode, emitted_blob, seams, log=lambda line: print(line, flush=True)):
    """Sweep the projected product IDE suite `suite_path` (world A) and its two controls.

    emitted_blob: path of the ide image the preflight emitted (emission/ide/ide.blob.bin).
    seams: the reviewed product seams of ('ide', 'lib/ide-ui.lisp') (c254_config.PRODUCT_SEAMS).
    Returns the receipt dict (status PASS/FAIL); the caller saves it and refuses on FAIL."""
    assert mode in ('reduced', 'exhaustive')
    t0 = time.monotonic()
    out = Path(out)
    replace = [(s['product_new'], s['product_old']) for s in seams if s['action'] == 'replace']
    assert len(replace) == 2, 'D-E3 proposal A has two replace seams'
    a_file = [p for p in json.loads(Path(suite_path).read_text())['sources'] if Path(p).name.startswith('source-')]
    assert len(a_file) == 1, ('product ide-ui source', a_file)
    noa_path, noa_row = make_variant(suite_path, out / 'worlds', 'noA', Path(a_file[0]).name, replace)
    nocopy_path, nocopy_row = make_variant(suite_path, out / 'worlds', 'nocopy', NOCOPY_FILE, [NOCOPY_EDIT])
    worlds = {'A': world(suite_path), 'noA': world(noa_path), 'nocopy': world(nocopy_path)}
    emitted = bind(emitted_blob)
    identity = dict(emitted=emitted, world_blob_sha256=worlds['A']['blob_sha256'], world_blob_bytes=worlds['A']['blob_bytes'],
                    objects=worlds['A']['objects'],
                    equal=(worlds['A']['blob_sha256'], worlds['A']['blob_bytes']) == (emitted['sha256'], emitted['bytes']))
    assert identity['equal'], ('E3 harness world is not the emitted ide image', identity)

    def delta(x, y):
        return {k: [x.get(k), y.get(k)] for k in sorted(set(x) | set(y)) if x.get(k) != y.get(k)}
    deltas = {'noA->A': delta(worlds['noA']['sizes'], worlds['A']['sizes']),
              'nocopy->A': delta(worlds['nocopy']['sizes'], worlds['A']['sizes'])}
    lib = list(CASES)
    if mode == 'reduced':
        plan = [('A', 'A', lib, 'lib', False, True), ('nocopy', 'nocopy', lib, 'lib', False, False),
                ('noA', 'noA', lib, 'lib', False, False)]
    else:
        control = lib + [c for c in EXTRA if c[0] != 'x-fill-wrap']
        plan = [('A', 'A', lib + list(EXTRA), 'all', False, True), ('A:allbuf', 'A', list(ALLBUF), 'all', True, False),
                ('nocopy', 'nocopy', control, 'all', False, False), ('noA', 'noA', control, 'all', False, False),
                ('noA:allbuf', 'noA', list(ALLBUF), 'all', True, False)]
    runs = {}
    for name, key, cases, points, allbuf, equivalence in plan:
        log('e3 sweep %s (%s, points %s)' % (name, mode, points))
        runs[name] = Sweep(worlds[key], allbuf).run(cases, points, log, equivalence)
        log('e3 sweep %s: points %d violations %d strict %d d4 %s seconds %s' % (
            name, runs[name]['total_points'], runs[name]['total_violations'], runs[name]['total_strict_violations'],
            runs[name]['d4_prefix_reset']['ok'], runs[name]['seconds']))
    problems = verdict(runs, deltas)
    return dict(status='PASS' if not problems else 'FAIL', mode=mode, problems=problems,
                suite=bind(suite_path), world_identity=identity, object_deltas=deltas,
                worlds={k: dict(suite=w['path'], blob_sha256=w['blob_sha256'], blob_bytes=w['blob_bytes'],
                                sources=w['sources']) for k, w in worlds.items()},
                controls=[noa_row, nocopy_row],
                totals={n: {k: r[k] for k in ('total_points', 'total_violations', 'total_strict_violations',
                                              'lib_point_set_total', 'lib_point_set_violations')} for n, r in runs.items()},
                runs=runs, tool=bind(__file__), seconds=round(time.monotonic() - t0, 1))


def selftest():
    """Synthetic: the verdict must refuse a non-discriminating or violated result."""
    ok = dict(total_points=10, total_violations=0, total_strict_violations=0, all_poll_aborts_ok=True,
              all_no_abort_ok=True, d4_prefix_reset=dict(ok=True), allbuf=False, violations_outside_return_cases=0)
    good = {'A': ok, 'nocopy': dict(ok, total_violations=3), 'noA': dict(ok, total_violations=9, d4_prefix_reset=dict(ok=False))}
    deltas = {'noA->A': {'%ide-drain-pending': 0, 'ide': 0}, 'nocopy->A': {'ide-split-line': 0}}
    assert verdict(good, deltas) == []
    rejected = []
    for name, runs, d in (
            ('violation in the product world', dict(good, A=dict(ok, total_violations=1)), deltas),
            ('strict violation in the product world', dict(good, A=dict(ok, total_strict_violations=1)), deltas),
            ('no points', dict(good, A=dict(ok, total_points=0)), deltas),
            ('pending C-x row fails in the product world', dict(good, A=dict(ok, d4_prefix_reset=dict(ok=False))), deltas),
            ('no-copy control passes', dict(good, nocopy=ok), deltas),
            ('no-copy fails outside Return cases', dict(good, nocopy=dict(ok, total_violations=3, violations_outside_return_cases=1)), deltas),
            ('control without proposal A passes', dict(good, noA=dict(ok, d4_prefix_reset=dict(ok=False))), deltas),
            ('pending C-x row passes without the seam', dict(good, noA=dict(ok, total_violations=9)), deltas),
            ('control world missing', {k: v for k, v in good.items() if k != 'noA'}, deltas),
            ('proposal A touches a third object', good, dict(deltas, **{'noA->A': {'%ide-drain-pending': 0, 'ide': 0, 'x': 0}})),
            ('no-copy control is not the Return copy', good, dict(deltas, **{'nocopy->A': {}}))):
        assert verdict(runs, d), 'negative survived: ' + name
        rejected.append('e3 verdict: ' + name)
    return rejected


if __name__ == '__main__':
    print(json.dumps(dict(status='PASS', rejected=selftest()), indent=2))
