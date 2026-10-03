#!/usr/bin/env python3
"""LCC compile-time nesting ladder: 2.5.2 vs 2.5.3 r7 vs the working-tree candidate.

The device compiler (lib/lcc.lisp + lib/dialect-v2/lcc-profile.lisp) runs as bytecode on the VM, so
every non-tail Lisp call it makes while compiling a nested form costs one VM soft frame and some
root slots.  2.5.3 Final r7 lost one nesting level for every form containing `setq` (F2,
build/card-253-f1f2-compare-r1/notes.txt).  This gate measures, for a fixed set of form shapes, the
deepest nesting the PRODUCT LCC bytecode still compiles under the product's real limits and
requires the candidate to be at least as deep as 2.5.2 for every shape, with no higher frame or
root high-water at the 2.5.2 depth.

Worlds (all driven through `%c2-compile-form`, the entry `lcc-run` uses on the device):
  2.5.2      delivered stdlib-p0 + LCC images (tracked: config/c2-v252-r1-public-plane)
  2.5.3-r7   delivered stdlib-p0 + LCC images (tracked: config/c2-v253-r1-public-plane); the
             negative control: this gate must see the regression there
  candidate  the product PROJECTION of the working-tree lib sources onto the frozen v1.5.0 v112
             compiler tier (tracked copy), emitted here against the 2.5.3 product resident suite
             and run on the delivered 2.5.3 stdlib-p0 image.  Same rule as
             c253_product.project_text (whole file, else diff hunks whose old text occurs once).
  control    the 2.5.2 -> r7 projection re-emitted from the r7 source commit must reproduce the
             delivered r7 LCC blob byte for byte (proves the emission route used for `candidate`).

Limits (the host VM is otherwise unbounded; a tracer enforces them):
  soft frames  VM_SOFT_FRAME_MAX is read from src/vm.c (16).  OP_CALL of a bytecode callee pushes
               one frame, OP_TAILCALL reuses it, CALLPRIM funcall/apply re-enter natively (no soft
               frame).  `%c2-compile-form` is entered at soft depth ENTRY_SOFT_FRAMES = 2; that
               value is CALIBRATED against the nine emulator ladder points of the F2 card (2.5.2
               Final r7c and 2.5.3 Final r7 media) and the calibration is re-asserted on every run.
  root slots   the product root stack has 128 slots (src/mem.c static assert; -DGC_ROOTS=128).  The
               host VM reports args + locals + operands per frame (P0VM native_stack); the entry
               reserve ENTRY_ROOT_SLOTS = 16 for the frames above `%c2-compile-form` is an
               UNCALIBRATED allowance (no emulator point trips on roots).  Shapes that end on the
               root limit therefore carry an absolute depth that is a host-model figure; the
               2.5.2-vs-candidate comparison does not depend on the allowance.

Semantics that must survive the fix are asserted in the candidate world as well (multi-pair setq
with DROP between pairs, odd setq and fixed-arity refusals, the F2 form).

Usage: lcc_nesting_ladder_v253_20261002.py generate | check   (receipt is write-once)
Scratch output: build/lcc-nesting-ladder-v253-20261002-live/ (never bound by the receipt).
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.setrecursionlimit(20000)

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import evidence_era as E  # noqa: E402
from v2_workbench_codemod import rewrite_tokens  # noqa: E402

FORMAT = 'lisp65-lcc-nesting-ladder-v253-20261002'
RECEIPT = ROOT / 'tests/bytecode/dialect-v2/evidence/capability-carrier/lcc-nesting-ladder-v253-20261002.json'
LIVE = ROOT / 'build/lcc-nesting-ladder-v253-20261002-live'
LEDGER = ROOT / 'config/bytecode-abi-ledger.json'
PROFILE = 'dialect-v2'
BASE_COMMIT = '49d128599c73a5b6eb6b8595431923cd30b84491'      # 2.5.2 published source
R7_COMMIT = 'fe248d46d66ec06646c6f4721fe7f6c26f378ea0'        # 2.5.3 r7 source authority

P252 = 'config/c2-v252-r1-public-plane/build/'
P253 = 'config/c2-v253-r1-public-plane/build/card-253-preflight-r7/emission/'
IMAGES = {
    '2.5.2': dict(
        stdlib=(P252 + 'o2-lite-r4-slots-preflight/planes/candidate/stdlib-p0.manifest.json',
                P252 + 'o2-lite-r4-slots-preflight/planes/candidate/stdlib-p0.blob.bin'),
        lcc=(P252 + 'walks-product-r1/plane/candidate/lcc.manifest.json',
             P252 + 'walks-r3/seed/inputs/build/backspace-r3/seed/inputs/build/ide-exit-r5/seed/inputs/'
                    'build/release-v1.5.0/public-product-build/build/post-promotion/v112/compiler/lcc.blob.bin')),
    '2.5.3-r7': dict(
        stdlib=(P253 + 'stdlib-p0/stdlib-p0.manifest.json', P253 + 'stdlib-p0/stdlib-p0.blob.bin'),
        lcc=(P253 + 'lcc/lcc.manifest.json', P253 + 'lcc/lcc.blob.bin')),
}
# Frozen v1.5.0 v112 compiler tier (tracked copy) and the 2.5.3 product resident suite.
FROZEN = 'config/c2-v251-r2-20260929-public-plane/build/'
FROZEN_SUITE = FROZEN + 'release-v1.5.0/public-product-build/build/post-promotion/v112/compiler-tier/suite.json'
RESIDENT_SUITE = 'build/card-253-preflight-r7/projection/stdlib-p0/suite.json'
PROJECTION = {'lcc.lisp': 'lib/lcc.lisp', 'lcc-profile.lisp': 'lib/dialect-v2/lcc-profile.lisp'}
# Suite function-list edits of the 2.5.3 projection (c253_config.SUITE_EDITS, key 'lcc'); the
# candidate keeps the r7 function population, so the same edits apply.
FUNCTION_EDITS = (
    (['%lcc-setq'], ['%lcc-setq-one', '%lcc-setq-pairs', '%lcc-setq']),
    (['%lcc-2args-p'], ['%lcc-2args-p', '%lcc-1args-p']),
    (['%lcc-expr-ops2'], ['%lcc-unary-checked', '%lcc-binary-checked', '%lcc-v2-unary', '%lcc-v2-binary',
                          '%lcc-expr-ops2']),
)

GC_ROOTS_PRODUCT = 128
ENTRY_SOFT_FRAMES = 2
ENTRY_ROOT_SLOTS = 16
DEPTH_CAP = 16          # ladder probe cap; a shape that still compiles there is reported as the cap

# Emulator ladder points (build/card-253-f1f2-compare-r1/notes.txt, receipt.json f2_max_nest and the
# "Max nesting k" table): shape -> max depth on the 2.5.2 Final r7c / 2.5.3 Final r7 media.
EMULATOR = {
    '2.5.2': {'let-setq': 8, 'let-dotimes-setq': 6, 'let-arith': 10},
    '2.5.3-r7': {'let-setq': 7, 'let-dotimes-setq': 5, 'let-arith': 10, 'let-dotimes': 7,
                 'let-while-setq': 5, 'defun-let-setq': 7},
}


class LadderError(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise LadderError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def bind(rel):
    raw = (ROOT / rel).read_bytes()
    return dict(path=str(rel), bytes=len(raw), sha256=sha(raw))


# ------------------------------------------------------------------ shapes
def rep(depth, wrap, leaf):
    text = leaf
    for _ in range(depth):
        text = wrap(text)
    return text


def arith(depth, leaf='i'):
    return rep(depth, lambda s: '(+ 1 %s)' % s, leaf)


SHAPES = (
    # (name, class, generator)
    ('nested-let', 'let', lambda k: rep(k, lambda s: '(let ((i 1)) %s)' % s, 'i')),
    ('nested-let*', 'let', lambda k: rep(k, lambda s: '(let* ((a 1) (b a)) %s)' % s, '1')),
    ('let-arith', 'arithmetic', lambda k: '(let ((i 1)) %s)' % arith(k)),
    ('arith', 'arithmetic', lambda k: arith(k, '1')),
    ('arith-binary', 'arithmetic', lambda k: rep(k, lambda s: '(- %s 1)' % s, '1')),
    ('let-setq', 'setq', lambda k: '(let ((i 1)(s 0)) (setq s %s) s)' % arith(k)),
    ('let-dotimes-setq', 'setq', lambda k: '(let ((s 0)) (dotimes (i 1) (setq s %s)) s)' % arith(k)),
    ('let-dotimes', 'loop', lambda k: '(let ((s 0)) (dotimes (i 1) %s) s)' % arith(k)),
    ('let-while-setq', 'setq', lambda k: '(let ((s 0)(i 1)) (while (< s 1) (setq s %s)) s)' % arith(k)),
    ('let-dolist-setq', 'setq', lambda k: "(let ((s 0)) (dolist (i '(1)) (setq s %s)) s)" % arith(k)),
    ('defun-let-setq', 'setq', lambda k: '(defun dz (i) (let ((s 0)) (setq s %s) s))' % arith(k)),
    ('global-setq', 'setq', lambda k: '(let ((i 1)) (setq g253 %s))' % arith(k)),
    ('upvalue-setq', 'setq', lambda k: '(let ((i 1)(s 0)) (funcall (lambda () (setq s %s))) s)' % arith(k)),
    ('nested-setq', 'setq', lambda k: '(let ((i 1)(s 0)) %s)' % rep(k, lambda s: '(setq s %s)' % s, 'i')),
    ('car', 'car/cdr', lambda k: rep(k, lambda s: '(car %s)' % s, "'(1)")),
    ('cdr', 'car/cdr', lambda k: rep(k, lambda s: '(cdr %s)' % s, "'(1)")),
    ('car-cdr', 'car/cdr', lambda k: rep(k, lambda s: '(car (cdr %s))' % s, "'(1)")),
    ('consp', 'car/cdr', lambda k: rep(k, lambda s: '(consp %s)' % s, "'(1)")),
    ('not', 'car/cdr', lambda k: rep(k, lambda s: '(not %s)' % s, 't')),
    ('null', 'car/cdr', lambda k: rep(k, lambda s: '(null %s)' % s, 't')),
    ('mod', 'arithmetic', lambda k: rep(k, lambda s: '(mod %s 7)' % s, '100')),
    ('cons', 'car/cdr', lambda k: rep(k, lambda s: '(cons 1 %s)' % s, 'nil')),
    ('if', 'if/cond/progn', lambda k: rep(k, lambda s: '(if t %s 0)' % s, '1')),
    ('if-test', 'if/cond/progn', lambda k: rep(k, lambda s: '(if %s 1 0)' % s, 't')),
    ('cond', 'if/cond/progn', lambda k: rep(k, lambda s: '(cond (nil 0) (t %s))' % s, '1')),
    ('progn', 'if/cond/progn', lambda k: rep(k, lambda s: '(progn 0 %s)' % s, '1')),
    ('call-prim', 'function calls', lambda k: rep(k, lambda s: '(list %s)' % s, '1')),
    ('call-user', 'function calls', lambda k: rep(k, lambda s: '(f253 %s 2)' % s, '1')),
    ('lambda-funcall-arg', 'lambda/funcall', lambda k: rep(k, lambda s: '(funcall (lambda (x) x) %s)' % s, '1')),
    ('lambda-funcall-body', 'lambda/funcall', lambda k: rep(k, lambda s: '(funcall (lambda () %s))' % s, '1')),
    ('lambda-immediate', 'lambda/funcall', lambda k: rep(k, lambda s: '((lambda (x) %s) 1)' % s, '1')),
    ('when', 'when/unless', lambda k: rep(k, lambda s: '(when t %s)' % s, '1')),
    ('unless', 'when/unless', lambda k: rep(k, lambda s: '(unless nil %s)' % s, '1')),
    ('and', 'and/or', lambda k: rep(k, lambda s: '(and t %s)' % s, '1')),
    ('or', 'and/or', lambda k: rep(k, lambda s: '(or nil %s)' % s, '1')),
)

# Multi-pair setq has no 2.5.2 baseline (2.5.2 silently dropped every pair after the first, so its
# "depth" there is not a compile of the value).  Reported for the candidate and r7 only; the last
# pair costs what a single-pair setq costs, a leading pair one frame more (the DROP between pairs).
INFORMATIONAL = (
    ('two-pair-setq-deep-last', lambda k: '(let ((i 1)(s 0)(u 0)) (setq u 1 s %s) s)' % arith(k)),
    ('two-pair-setq-deep-first', lambda k: '(let ((i 1)(s 0)(u 0)) (setq s %s u 1) s)' % arith(k)),
)

F2_FORM = '(let ((s 0)) (dotimes (i 1) (setq s (+ s (peek 23 (+ 160 i))))) s)'
F2_FORM_96 = '(let ((s 0)) (dotimes (i 96) (setq s (logior s (peek 23 (+ 160 i))))) s)'
REFUSAL = '%lcc-error-invalid-parameter-list'
# (name, form, expectation): value text, or ('refused',) for the compile-time refusal.
SEMANTICS = (
    ('setq-two-pairs', '(let ((a 0) (b 0)) (setq a 100 b (+ a 2)) b)', '102'),
    ('setq-three-pairs', '(let ((a 0) (b 0) (c 0)) (setq a 100 b 2 c 7) (list a b c))', '(100 2 7)'),
    ('setq-single', '(let ((a 0)) (setq a 5))', '5'),
    ('setq-empty', '(setq)', 'nil'),
    ('setq-pairs-loop-stack', '(let ((i 0) (a 0) (b 0)) (while (< i 200) (setq a i b a i (+ i 1))) b)', '199'),
    ('f2-shape-runs', '(let ((s 0)) (dotimes (i 96) (setq s (logior s (+ 160 i)))) s)', '255'),
    ('setq-odd', '(let ((a 1)) (setq a))', ('refused',)),
    ('setq-odd-three', '(let ((a 1) (b 2)) (setq a 1 b))', ('refused',)),
    ('car-two-args', "(car '(1) 2)", ('refused',)),
    ('cdr-no-args', '(cdr)', ('refused',)),
    ('consp-two-args', '(consp 1 2)', ('refused',)),
    ('not-no-args', '(not)', ('refused',)),
    ('null-two-args', '(null 1 2)', ('refused',)),
    ('mod-one-arg', '(mod 1)', ('refused',)),
    ('cons-one-arg', '(cons 1)', ('refused',)),
    ('cons-three-args', '(cons 1 2 3)', ('refused',)),
)
LOOP_STACK_BOUND = 24   # root slots of the compiled multi-pair loop at run time (200 rounds)


# ------------------------------------------------------------------ limits
def soft_frame_max():
    text = (ROOT / 'src/vm.c').read_text()
    found = re.findall(r'^#define VM_SOFT_FRAME_MAX (\d+)\s*$', text, re.M)
    require(len(found) == 1, 'VM_SOFT_FRAME_MAX not found exactly once in src/vm.c')
    require('if (vm_soft_sp >= (uint16_t)VM_SOFT_FRAME_MAX) {' in text, 'soft-frame overflow check moved in src/vm.c')
    require(re.search(r'workbench_rootstack_must_have_128_slots\[\(GC_ROOTS == 128\)', (ROOT / 'src/mem.c').read_text()),
            'product root-stack size assertion moved in src/mem.c')
    return int(found[0])


class Overflow(Exception):
    pass


class Limits:
    """P0VM trace sink enforcing the product limits; also records the high-water marks."""

    def __init__(self, frames, roots):
        self.frames, self.roots = frames, roots
        self.stack, self.soft, self.native = [], 0, 0
        self.kinds = (None, None)
        self.max_frames = self.max_roots = self.max_native = 0
        self.tripped = None

    def call(self, _caller, kind, _target, _argc, pc=None, resolved=False):
        self.kinds = (self.kinds[1], kind)

    def native_frame(self, name, _code, _args, native_base, frame_slots, reserve_slots, tail):
        if tail:
            kind = 'tail'                      # OP_TAILCALL: frame reused
        elif self.kinds == ('CALLPRIM', 'INVOKE'):
            kind = 'native'                    # funcall/apply: native re-entry, no soft frame
            self.native += 1
            self.max_native = max(self.max_native, self.native)
        else:
            kind = 'soft'                      # OP_CALL (the first activation is the entry itself)
            self.soft += 1
        self.stack.append(kind)
        self.kinds = (None, None)
        depth = self.soft - 1
        self.max_frames = max(self.max_frames, depth)
        if self.frames is not None and depth > self.frames:
            self.tripped = 'frames'
            raise Overflow(name)

    def exit(self, _name, _code):
        kind = self.stack.pop()
        if kind == 'soft':
            self.soft -= 1
        elif kind == 'native':
            self.native -= 1

    def native_stack(self, name, used):
        if used > self.max_roots:
            self.max_roots = used
            if self.roots is not None and used > self.roots:
                self.tripped = 'roots'
                raise Overflow(name)

    def __getattr__(self, _name):
        return lambda *a, **k: None


# ------------------------------------------------------------------ worlds
def load_image(heap, directory, names, manifest_rel, blob_rel):
    manifest = json.loads((ROOT / manifest_rel).read_text())
    blob = (ROOT / blob_rel).read_bytes()
    require(len(blob) == int(manifest['code_bytes']) and sha(blob) == manifest['blob_sha256'],
            'manifest/blob drift: ' + str(manifest_rel))
    patch = {int(row['blob_offset']): int(row['node']) for row in manifest['literal_patches']}
    for entry in manifest['entries']:
        symbol = heap.intern(entry['name'])
        require(symbol not in directory, 'duplicate packed callee: ' + entry['name'])
        code = STD._patched_code_from_manifest_entry(heap, manifest, blob, entry, patch)
        directory[symbol] = code
        names[id(code)] = entry['name']
    return manifest


def world(stdlib, lcc):
    heap = C.prepare_heap([])
    directory, names = {}, {}
    load_image(heap, directory, names, *stdlib)
    load_image(heap, directory, names, *lcc)
    return heap, directory, names


def era_text(commit, rel):
    return E.era_blob(commit, rel).decode()


def project_text(frozen, old, new, label):
    """c253_product.project_text rule: whole file when the frozen copy is T(old); else grouped diff
    hunks (3 lines of context) whose old text occurs exactly once.  T in (identity, rewrite_tokens)."""
    transforms = (lambda x: x, lambda x: rewrite_tokens(x)[0])
    for transform in transforms:
        if frozen == transform(old):
            return transform(new), 'whole-file'
    for transform in transforms:
        before, after = transform(old).splitlines(True), transform(new).splitlines(True)
        text, good, count = frozen, True, 0
        for group in difflib.SequenceMatcher(None, before, after, autojunk=False).get_grouped_opcodes(3):
            seg_old = ''.join(before[group[0][1]:group[-1][2]])
            seg_new = ''.join(after[group[0][3]:group[-1][4]])
            if text.count(seg_old) != 1:
                good = False
                break
            text = text.replace(seg_old, seg_new)
            count += 1
        if good and count:
            return text, 'hunks:%d' % count
    raise LadderError('projection seam (old text not unique in the frozen copy): ' + label)


def edit_list(values, old, new):
    hits = [i for i in range(len(values) - len(old) + 1) if values[i:i + len(old)] == old]
    require(len(hits) == 1, 'suite function-list seam: %r' % (old,))
    return values[:hits[0]] + list(new) + values[hits[0] + len(old):]


def emit_projection(out, new_text):
    """Project `new_text` (lib path -> text) onto the frozen tier and emit the LCC image into `out`."""
    require((ROOT / RESIDENT_SUITE).is_file(),
            'missing 2.5.3 product resident suite (local build tree): ' + RESIDENT_SUITE)
    shutil.rmtree(out, ignore_errors=True)
    (out / 'sources').mkdir(parents=True)
    suite = json.loads((ROOT / FROZEN_SUITE).read_text())
    moved, modes = {}, {}
    for source in suite['sources']:
        lib = PROJECTION.get(Path(source).name)
        if lib is None:
            continue
        text, mode = project_text((ROOT / source).read_text(), era_text(BASE_COMMIT, lib), new_text[lib], lib)
        target = out / 'sources' / Path(source).name
        target.write_text(text)
        moved[source] = str(target)
        modes[lib] = mode
    require(len(moved) == len(PROJECTION), 'frozen compiler tier lost a projected source')
    suite['sources'] = [moved.get(s, str(ROOT / s)) for s in suite['sources']]
    suite['definition_source_overrides'] = {k: moved.get(v, str(ROOT / v))
                                            for k, v in suite['definition_source_overrides'].items()}
    for old, new in FUNCTION_EDITS:
        suite['functions'] = edit_list(suite['functions'], old, new)
    suite['resident_suite'] = str(ROOT / RESIDENT_SUITE)
    path = out / 'suite.json'
    path.write_text(json.dumps(suite, indent=2) + '\n')
    STD.emit_artifacts(str(path), STD._read_suite(str(path)), str(out / 'lcc'), base_addr=0, artifact_role='disk-lib')
    manifest = out / 'lcc.manifest.json'
    blob = out / 'lcc.blob.bin'
    data = json.loads(manifest.read_text())
    sizes = [int(e['length']) for e in data['entries']] if data['entries'] and 'length' in data['entries'][0] else []
    return manifest, blob, modes, dict(objects=int(data['objects']), code_bytes=int(data['code_bytes']),
                                       largest_entry=max(sizes) if sizes else None)


# ------------------------------------------------------------------ measurement
def vm_for(w, heap):
    return B.P0VM(heap=heap, directory=w[1], code_names=w[2], max_steps=3000000, max_call_args=12,
                  abi_profile=PROFILE, abi_ledger=LEDGER_VALUE)


def compile_form(w, source, limits):
    heap = w[0].clone()
    vm = vm_for(w, heap)
    vm.trace = limits
    form = vm._compiler_form_obj(C.parse_one(source))
    try:
        return 'ok', vm.run(w[1][heap.intern('%c2-compile-form')], [form]), heap
    except Overflow:
        return 'overflow:' + limits.tripped, None, heap
    except B.VMError as exc:
        text = (exc.error_symbol or '') + ' ' + str(exc)
        return ('refused' if REFUSAL in text.lower() else 'error:' + exc.status), None, heap


def obj_list(heap, value):
    out = []
    while heap.consp(value):
        out.append(heap.car(value))
        value = heap.cdr(value)
    require(value == B.NIL, 'improper list from the compiler carrier')
    return out


def run_compiled(w, heap, generated):
    codes = []
    for item in obj_list(heap, generated):
        f = obj_list(heap, item)
        codes.append(B.CodeObject(nargs=B.fixval(f[0]), nlocals=B.fixval(f[1]), flags=B.fixval(f[2]),
                                  littab=tuple(obj_list(heap, f[3]) if f[3] != B.NIL else ()),
                                  payload=bytes(B.fixval(v) for v in obj_list(heap, f[4]))))
    require(len(codes) == 1, 'semantic probe produced helper code objects')
    vm = vm_for(w, heap)
    sink = Limits(None, None)
    vm.trace = sink
    return heap.obj_to_text(vm.run(codes[0], ())), sink.max_roots


def ladder(w, frames, roots, shapes=SHAPES):
    rows = {}
    for name, cls, make in shapes:
        best, stop, marks = 0, None, {}
        for depth in range(1, DEPTH_CAP + 1):
            limits = Limits(frames, roots)
            status, _value, _heap = compile_form(w, make(depth), limits)
            if status != 'ok':
                stop = status
                break
            best = depth
            marks[depth] = [limits.max_frames, limits.max_roots]
        rows[name] = dict(shape_class=cls, max_depth=best, stop=stop or 'cap', high_water=marks)
    return rows


def semantics(w, frames, roots):
    rows = []
    for name, form, expect in SEMANTICS:
        status, value, heap = compile_form(w, form, Limits(frames, roots))
        row = dict(name=name, form=form, compile=status)
        if status == 'ok':
            row['value'], row['run_root_slots'] = run_compiled(w, heap, value)
        rows.append(row)
        if expect == ('refused',):
            require(status == 'refused', 'candidate must refuse %s (got %s)' % (name, status))
        else:
            require(status == 'ok' and row['value'].lower() == expect, 'candidate semantics drift: %s -> %r' % (name, row))
    by = {r['name']: r for r in rows}
    require(by['setq-pairs-loop-stack']['run_root_slots'] <= LOOP_STACK_BOUND,
            'multi-pair setq loop is not stack-bounded: %d' % by['setq-pairs-loop-stack']['run_root_slots'])
    for name, form in (('f2-minimal-form', F2_FORM), ('f2-reported-form', F2_FORM_96)):
        status, _value, _heap = compile_form(w, form, Limits(frames, roots))
        rows.append(dict(name=name, form=form, compile=status))
    return rows


def render():
    global LEDGER_VALUE
    LEDGER_VALUE = json.loads(LEDGER.read_text())
    soft_max = soft_frame_max()
    frames = soft_max - ENTRY_SOFT_FRAMES
    roots = GC_ROOTS_PRODUCT - ENTRY_ROOT_SLOTS
    LIVE.mkdir(parents=True, exist_ok=True)

    # Emission control: the r7 projection must reproduce the delivered r7 LCC blob.
    r7_text = {lib: era_text(R7_COMMIT, lib) for lib in PROJECTION.values()}
    _m, control_blob, control_modes, _s = emit_projection(LIVE / 'control-r7', r7_text)
    delivered_r7 = (ROOT / IMAGES['2.5.3-r7']['lcc'][1]).read_bytes()
    require(control_blob.read_bytes() == delivered_r7,
            'emission control: the r7 projection does not reproduce the delivered r7 LCC blob')

    new_text = {lib: (ROOT / lib).read_text() for lib in PROJECTION.values()}
    manifest, blob, modes, shape = emit_projection(LIVE / 'candidate', new_text)
    worlds = {name: world(spec['stdlib'], spec['lcc']) for name, spec in IMAGES.items()}
    worlds['candidate'] = world(IMAGES['2.5.3-r7']['stdlib'],
                                (manifest.relative_to(ROOT), blob.relative_to(ROOT)))
    ladders = {name: ladder(w, frames, roots) for name, w in worlds.items()}

    # Calibration: the host model under these limits reproduces every emulator point.
    calibration = []
    for name, points in EMULATOR.items():
        for shape_name, depth in points.items():
            got = ladders[name][shape_name]['max_depth']
            calibration.append(dict(world=name, shape=shape_name, emulator=depth, host=got))
            require(got == depth, 'calibration: %s %s emulator %d host %d' % (name, shape_name, depth, got))

    # Acceptance: candidate >= 2.5.2 for every shape, no higher high-water at any 2.5.2 depth.
    table, regressions_r7 = [], []
    for name, cls, _make in SHAPES:
        base, r7, cand = (ladders[k][name] for k in ('2.5.2', '2.5.3-r7', 'candidate'))
        require(cand['max_depth'] >= base['max_depth'],
                'REGRESSION %s: candidate %d < 2.5.2 %d' % (name, cand['max_depth'], base['max_depth']))
        for depth, (f, r) in base['high_water'].items():
            cf, cr = cand['high_water'][depth]
            require(cf <= f and cr <= r, 'high-water above 2.5.2: %s depth %s frames %d/%d roots %d/%d'
                    % (name, depth, cf, f, cr, r))
        if r7['max_depth'] < base['max_depth']:
            regressions_r7.append(name)
        table.append({'shape': name, 'class': cls, '2.5.2': base['max_depth'], '2.5.3-r7': r7['max_depth'],
                      'candidate': cand['max_depth'], 'limit': base['stop']})
    require(regressions_r7, 'negative control: the r7 image shows no regression (the gate would be blind)')
    require(all(ladders['2.5.3-r7'][n]['shape_class'] == 'setq' for n in regressions_r7),
            'negative control: r7 regresses outside the setq class')

    info_shapes = tuple((name, 'setq-multi', make) for name, make in INFORMATIONAL)
    info = {name: ladder(worlds[name], frames, roots, info_shapes) for name in ('2.5.3-r7', 'candidate')}
    multi = [{'shape': name, '2.5.3-r7': info['2.5.3-r7'][name]['max_depth'],
              'candidate': info['candidate'][name]['max_depth']} for name, _make in INFORMATIONAL]
    single = ladders['candidate']['let-setq']['max_depth']
    require(info['candidate']['two-pair-setq-deep-last']['max_depth'] == single
            and info['candidate']['two-pair-setq-deep-first']['max_depth'] == single - 1
            and all(row['candidate'] >= row['2.5.3-r7'] for row in multi),
            'multi-pair setq depth drift: %r' % (multi,))

    sem = semantics(worlds['candidate'], frames, roots)
    by = {r['name']: r for r in sem}
    require(by['f2-minimal-form']['compile'] == 'ok' and by['f2-reported-form']['compile'] == 'ok',
            'the F2 form does not compile in the candidate under the product limits')
    f2 = {name: [compile_form(worlds[name], form, Limits(frames, roots))[0] for form in (F2_FORM, F2_FORM_96)]
          for name in ('2.5.2', '2.5.3-r7')}
    require(f2['2.5.2'] == ['ok', 'ok'] and f2['2.5.3-r7'] == ['overflow:frames', 'overflow:frames'],
            'F2 reproduction drift: %r' % (f2,))

    return {
        'format': FORMAT,
        'verdict': 'PASS',
        'claim': 'candidate product LCC compiles every shape at least as deep as 2.5.2 under the product '
                 'limits, with no higher frame/root high-water at any 2.5.2 depth; 2.5.3 semantics retained',
        'limits': {
            'vm_soft_frame_max': soft_max, 'entry_soft_frames': ENTRY_SOFT_FRAMES,
            'frames_available_to_compiler': frames,
            'gc_roots_product': GC_ROOTS_PRODUCT, 'entry_root_slots_uncalibrated': ENTRY_ROOT_SLOTS,
            'root_slots_available_to_compiler': roots, 'depth_cap': DEPTH_CAP,
        },
        'inputs': {
            'sources': [bind(lib) for lib in PROJECTION.values()],
            'frozen_tier': [bind(FROZEN_SUITE)] + [bind(s) for s in json.loads((ROOT / FROZEN_SUITE).read_text())['sources']],
            'resident_suite': bind(RESIDENT_SUITE),
            'images': {name: {k: [bind(p) for p in pair] for k, pair in spec.items()} for name, spec in IMAGES.items()},
            'base_commit': BASE_COMMIT, 'r7_commit': R7_COMMIT,
        },
        'emission_control': {'r7_projection_reproduces_delivered_blob': True, 'modes': control_modes,
                             'blob_sha256': sha(delivered_r7)},
        'candidate_image': {'projection_modes': modes, 'blob_sha256': sha(blob.read_bytes()),
                            'blob_bytes': len(blob.read_bytes()), **shape},
        'calibration': calibration,
        'ladder': table,
        'r7_regressed_shapes': regressions_r7,
        'multi_pair_setq_no_252_baseline': multi,
        'high_water': {name: {shape: rows[shape]['high_water'] for shape in rows} for name, rows in ladders.items()},
        'f2_form': {'minimal': F2_FORM, 'reported': F2_FORM_96, '2.5.2': f2['2.5.2'], '2.5.3-r7': f2['2.5.3-r7'],
                    'candidate': [by['f2-minimal-form']['compile'], by['f2-reported-form']['compile']]},
        'candidate_semantics': sem,
    }


def canonical(value):
    return (json.dumps(value, indent=1, sort_keys=True) + '\n').encode()


def main(argv):
    if argv not in (['generate'], ['check']):
        raise SystemExit('usage: lcc_nesting_ladder_v253_20261002.py generate | check')
    os.chdir(ROOT)
    try:
        data = canonical(render())
        if argv == ['generate']:
            with RECEIPT.open('xb') as stream:
                stream.write(data)
        else:
            require(RECEIPT.read_bytes() == data, 'receipt drift: ' + str(RECEIPT.relative_to(ROOT)))
    except LadderError as exc:
        print('lcc-nesting-ladder: FAIL: %s' % exc, file=sys.stderr)
        return 1
    table = json.loads(data)['ladder']
    print('lcc-nesting-ladder: PASS shapes=%d candidate>=2.5.2 everywhere; r7 regressed: %s'
          % (len(table), ','.join(json.loads(data)['r7_regressed_shapes'])))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
