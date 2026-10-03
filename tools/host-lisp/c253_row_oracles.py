#!/usr/bin/env python3
"""D-6: host oracles for the new 2.5.3 emulator rows (no emulator, no device, no product link).

Runs the candidate product worlds that the 2.5.3 preflight emitted (c253_config.PREFLIGHT:
projected resident, projected IDE suite, r8 M65D suite, projected LCC image) in the host
bytecode VM and records the observable result of every new row:

* LCC rows go through the packed device compiler carrier exactly as c2_while_gate.py does:
  the emitted LCC image + the projected resident are loaded into a host VM, the REPL form is
  compiled by `%c2-compile-form`, and the produced code object runs in a target VM.
* IDE / disk rows run the projected IDE world (+ r8 M65D, D81 model) through host cases.
* Screen text = "*** " + upper(config/error-texts.json text of the stable error code), the
  rendering seen in the 2.5.2 device/emulator receipts ("*** VM: OUT OF MEMORY").

Output: one write-once directory (default build/card-253-row-oracles-r1) with receipt.json.
The row table successor (tools/host-lisp/c253_rows_20261001.json) is written separately by
`rows` from that receipt.  Expected texts are host-model facts; heap/arena limits, GC timing
and native services absent from the host VM (%cs-read-open, %set-macro, lcc-install) are NOT
modelled -- rows that depend on them say so in their `oracle` field.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE_DIR))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import c253_config as CFG  # noqa: E402

ROOT = CFG.ROOT
PROFILE = 'dialect-v2'
LEDGER = ROOT / 'config/bytecode-abi-ledger.json'
ERROR_TEXTS = ROOT / 'config/error-texts.json'
STATUS_CODE = {'TypeError': 38, 'HeapOOM': 40, 'ArityError': 48, 'BadOpcode': 43}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def bind(path):
    raw = Path(path).read_bytes()
    return dict(path=str(Path(path).resolve().relative_to(ROOT)), bytes=len(raw), sha256=sha(raw))


def once(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(text)


def error_texts():
    return {row['code']: row['text'] for row in json.loads(ERROR_TEXTS.read_text())['entries']}


def screen(error, texts):
    code = error.get('error_code') or STATUS_CODE.get(error['status'])
    text = texts.get(code)
    return dict(code=code, text=text, screen=('*** ' + text.upper()) if text else None)


# ------------------------------------------------------------------ worlds
def worlds(pre):
    return dict(resident=pre / 'projection/stdlib-p0/suite.json', ide=pre / 'projection/ide/suite.json',
                m65d=pre / 'projection/m65d/suite.json', lcc=pre / 'projection/lcc/suite.json',
                lcc_manifest=pre / 'emission/lcc/lcc.manifest.json', lcc_blob=pre / 'emission/lcc/lcc.blob.bin')


def run_cases(out, tag, suite_path, cases, texts):
    """Host VM over `cases` in the world of `suite_path` (its sources/residents/disk model)."""
    suite = {k: v for k, v in STD._read_suite(str(suite_path)).items() if not k.startswith('_')}
    suite['cases'] = [dict(c, expect=c.get('expect', '?')) for c in cases]
    path = out / tag / 'suite.json'
    once(path, json.dumps(suite, indent=2) + '\n')
    suite = STD._read_suite(str(path))
    heap, names, code_by_name, flags, rflags, bundle, directory, compiled, entries, inliner = \
        STD._compile_suite(suite, include_cases=True)
    max_call_args = STD._validate_vm_limit_expectations(suite, heap, code_by_name)
    macros = STD._macro_symbol_objs(heap, flags, rflags)
    abi_profile, abi_ledger = STD._suite_abi(suite)
    rows = []
    for case, entry in zip(compiled, entries):
        case_heap = heap.clone()
        vm = B.P0VM(heap=case_heap, directory=directory, macro_symbols=macros,
                    max_steps=case.get('max_steps', 3000000), max_call_args=max_call_args,
                    disk_files=case.get('disk_files', suite.get('disk_files')),
                    d81_bam_model=suite.get('d81_bam_model', False),
                    **STD._disk_world_kwargs(suite, case),
                    key_events=case.get('key_events'),
                    private_key_event_modes=suite.get('private_key_event_modes', False),
                    abi_profile=abi_profile, abi_ledger=abi_ledger,
                    delivered_callprims=suite.get('delivered_callprims'))
        row = dict(name=case['name'], expr=case['expr'])
        try:
            row['result'] = case_heap.obj_to_text(vm.run(directory[heap.intern(entry)], []))
        except B.VMError as exc:
            row['error'] = dict(status=exc.status, message=str(exc), error_code=exc.error_code,
                                error_symbol=exc.error_symbol)
            row['error'].update(screen(row['error'], texts))
        row['steps'] = vm.steps
        rows.append(row)
        print(f"{tag}: {case['name']}: {row.get('result', row.get('error', {}).get('screen'))}", flush=True)
    return dict(world=bind(suite_path), suite=bind(path), rows=rows)


def lcc_carrier(w, forms, texts):
    """REPL forms through the packed LCC image (c2_while_gate.bound_environment pattern)."""
    import c2_while_gate as G
    suite = STD._read_suite(str(w['lcc']))
    manifest = json.loads(w['lcc_manifest'].read_text())
    blob = w['lcc_blob'].read_bytes()
    ledger = json.loads(LEDGER.read_text())
    rows = []
    for label, form in forms:
        heap, directory, macros, inliner = G.bound_environment(suite, manifest, blob)
        row = dict(name=label, form=form, steps=[])
        sources = form if isinstance(form, list) else [form]
        try:
            for index, source in enumerate(sources):
                # REPL = lcc-run -> %c2-run-expanded: a tree of published BYTECODE calls over direct
                # values runs through %c2-direct-expression (the callee's CodeObject is the arity
                # authority); everything else is compiled by the packed LCC.  Classify with the
                # product's own predicate first.
                probe = STD._expand_case_expr(suite, inliner, C.parse_one(
                    f'(if (%c2-published-direct-call-p (quote {source})) '
                    f'(cons (quote direct) (%c2-direct-expression (quote {source}))) (quote compile))'))
                pname, pcaller, phelpers = C.compile_top_form_with_helpers(
                    ['defun', f'__route_{index}', [], probe], heap, strict_arity=True, abi_profile=PROFILE,
                    prebuilt_primitives=True)
                for helper_name, helper in phelpers:
                    directory[heap.intern(helper_name)] = helper
                directory[heap.intern(pname)] = pcaller
                pvm = B.P0VM(heap=heap, directory=directory, macro_symbols=macros, max_steps=4000000,
                             max_call_args=suite['max_call_args'], abi_profile=PROFILE, abi_ledger=ledger)
                pvm.trace = StackTrace()
                try:
                    routed = pvm.run(pcaller, ())
                except B.VMError as exc:
                    err = dict(status=exc.status, message=str(exc), error_code=exc.error_code,
                               error_symbol=exc.error_symbol, phase='direct')
                    err.update(screen(err, texts))
                    row['steps'].append(dict(source=source, route='direct', error=err)); raise StopIteration
                if heap.consp(routed):
                    row['steps'].append(dict(source=source, route='direct', result=heap.obj_to_text(heap.cdr(routed)),
                                             max_native_stack=pvm.trace.max))
                    continue
                expanded = STD._expand_case_expr(suite, inliner, C.parse_one(f'(%c2-compile-form (quote {source}))'))
                name, caller, helpers = C.compile_top_form_with_helpers(
                    ['defun', f'__row_{index}', [], expanded], heap, strict_arity=True, abi_profile=PROFILE,
                    prebuilt_primitives=True)
                for helper_name, helper in helpers:
                    directory[heap.intern(helper_name)] = helper
                directory[heap.intern(name)] = caller
                vm = B.P0VM(heap=heap, directory=directory, macro_symbols=macros, max_steps=400000,
                            max_call_args=suite['max_call_args'], abi_profile=PROFILE, abi_ledger=ledger)
                try:
                    generated = vm.run(caller, ())
                except B.VMError as exc:
                    err = dict(status=exc.status, message=str(exc), error_code=exc.error_code,
                               error_symbol=exc.error_symbol, phase='compile')
                    err.update(screen(err, texts))
                    row['steps'].append(dict(source=source, error=err)); raise StopIteration
                codes = []
                for item in G.obj_list(heap, generated):
                    f = G.obj_list(heap, item)
                    codes.append(B.CodeObject(nargs=B.fixval(f[0]), nlocals=B.fixval(f[1]), flags=B.fixval(f[2]),
                                              littab=tuple(G.obj_list(heap, f[3]) if f[3] != B.NIL else ()),
                                              payload=bytes(B.fixval(v) for v in G.obj_list(heap, f[4]))))
                row.setdefault('code', []).append(dict(
                    source=source, payload=codes[0].payload.hex(),
                    disassembly=B.disassemble_code_object(codes[0], profile_id=PROFILE, abi_ledger=ledger)))
                parsed = C.parse_one(source)
                if isinstance(parsed, list) and parsed and parsed[0] == 'defun':
                    directory[heap.intern(parsed[1])] = codes[0]   # lcc-install of a defun (host model)
                    row['steps'].append(dict(source=source, route='compile', result=parsed[1].upper(), installed=True))
                    continue
                target = B.P0VM(heap=heap, directory=directory, macro_symbols=macros, max_steps=4000000,
                                max_call_args=suite['max_call_args'], abi_profile=PROFILE, abi_ledger=ledger)
                target.trace = StackTrace()
                try:
                    row['steps'].append(dict(source=source, route='compile', result=heap.obj_to_text(target.run(codes[0], ())),
                                             max_native_stack=target.trace.max))
                except B.VMError as exc:
                    err = dict(status=exc.status, message=str(exc), error_code=exc.error_code,
                               error_symbol=exc.error_symbol, phase='run')
                    err.update(screen(err, texts))
                    row['steps'].append(dict(source=source, error=err)); raise StopIteration
        except StopIteration:
            pass
        rows.append(row)
        print('lcc: ' + label + ': ' + json.dumps([s.get('result', s.get('error', {}).get('screen')) for s in row['steps']]),
              flush=True)
    return dict(lcc_image=bind(w['lcc_manifest']), lcc_blob=bind(w['lcc_blob']), suite=bind(w['lcc']), rows=rows)


class StackTrace:
    """Records the deepest native stack the VM reports (c2_while_gate / probe-integrate pattern)."""
    def __init__(self):
        self.max = 0

    def native_stack(self, _name, used):
        self.max = max(self.max, used)

    def __getattr__(self, _name):
        return lambda *a, **k: None


# ------------------------------------------------------------------ fixtures
def text_lines(count, width):
    """Distinct numbered lines with inner spaces; every 10th line blank."""
    lines = []
    for i in range(count):
        if i % 10 == 9:
            lines.append('')
            continue
        body = (f'{i:03d} ' + 'abcdefghij klmnopqrst uvwxyz0123 456789ABCD' * 3)[:width]
        lines.append(body[:-3] + '   ' if i % 7 == 0 else body)   # some trailing spaces (D3 keeps them)
    return lines


def lisp_list(lines):
    # A quoted literal: a (list ...) call would exceed the VM's 12-argument limit.
    return '(quote (' + ' '.join(json.dumps(x) for x in lines) + '))'


def ide_cases():
    cases = []
    for rows, width in ((20, 40), (50, 40), (100, 20), (100, 40)):
        lines = text_lines(rows, width)
        name = f'out{rows}x{width}'
        cases.append(dict(name=f'ide-save-{rows}x{width}', max_steps=60000000, expr=(
            '(progn (set-symbol-value (quote ide-buffers) nil) '
            f'(%ide-store-buffer (ide-make-buffer "big" {lisp_list(lines)})) '
            f'(list (save-buffer-to "{name}" "big") (ide-error) '
            f'(progn (load-file-to-buffer "{name}" "copy") (ide-buffer-lines (%ide-resume-buffer "copy"))) '
            f'(%ide-disk-read-string "{name}")))'), fixture=dict(lines=lines)))
    d3 = 'a  \n\n  b\r\nc\r\n  \n\n'
    cases.append(dict(name='disk-d3-lossless', max_steps=20000000,
                      disk_files={'IDE': {'content': '', 'capacity': 0}, 'D3SRC': {'content': d3, 'capacity': len(d3)}},
                      expr=('(progn (set-symbol-value (quote ide-buffers) nil) (load-file-to-buffer "d3src" "d3") '
                            '(list (ide-buffer-lines (%ide-resume-buffer "d3")) (save-buffer-to "d3out" "d3") '
                            '(string= (%ide-disk-read-string "d3out") (%ide-disk-read-string "d3src")) '
                            '(string-length (%ide-disk-read-string "d3out"))))'), fixture=dict(content=d3)))
    cases.append(dict(name='ide-buffer-switch', max_steps=5000000, expr=(
        '(progn (set-symbol-value (quote ide-buffers) nil) '
        '(let* ((s0 (ide-make-state (ide-make-buffer "a" (list "one")))) '
        '(s1 (ide-step s0 (list (quote key) 120 nil))) (s2 (ide-step s1 (list (quote key) 24 nil))) '
        '(s3 (ide-step s2 (list (quote key) 14 nil))) (s4 (ide-step s3 (list (quote key) 24 nil))) '
        '(s5 (ide-step s4 (list (quote key) 16 nil)))) '
        '(list (ide-buffer-lines (ide-state-buffer s1)) (ide-buffer-lines (ide-state-buffer s3)) '
        '(ide-buffer-lines (ide-state-buffer s5)) (car (cdr (cdr (cdr (cdr (cdr (ide-state-buffer s5))))))))))')))
    cases.append(dict(name='ide-buffer-switch-two', max_steps=5000000, expr=(
        '(progn (set-symbol-value (quote ide-buffers) nil) '
        '(%ide-store-buffer (ide-make-buffer "b" (list "bee"))) '
        '(let* ((s0 (ide-make-state (ide-make-buffer "a" (list "one")))) '
        '(s1 (ide-step s0 (list (quote key) 120 nil))) (s2 (ide-step s1 (list (quote key) 24 nil))) '
        '(s3 (ide-step s2 (list (quote key) 14 nil))) (s4 (ide-step s3 (list (quote key) 24 nil))) '
        '(s5 (ide-step s4 (list (quote key) 14 nil))) (s6 (ide-step s5 (list (quote key) 24 nil))) '
        '(s7 (ide-step s6 (list (quote key) 16 nil)))) '
        '(list (ide-buffer-name (ide-state-buffer s3)) (ide-buffer-lines (ide-state-buffer s3)) '
        '(ide-buffer-name (ide-state-buffer s5)) (ide-buffer-lines (ide-state-buffer s5)) '
        '(ide-buffer-name (ide-state-buffer s7)) (ide-buffer-lines (ide-state-buffer s7)))))')))
    # Mark = 5th buffer field (ide-buffer-mark lives outside the IDE image).
    cases.append(dict(name='ide-mark-stale', expr=(
        '(let ((b (quote ("m" nil ("abc" "def") (1 . 2) (0 . 1) nil 1105 nil nil)))) '
        '(list (car (cdr (cdr (cdr (cdr b))))) '
        '(car (cdr (cdr (cdr (cdr (%ide-buffer-with-lines-point b (list "x") (cons 0 0)))))))))')))
    cases.append(dict(name='status-13-message', expr='(list (%ide-m65d-message 13) (%ide-m65d-message 9))'))
    cases.append(dict(name='disk-d4-ide-save-on-leaked-disk', max_steps=20000000, expr=(
        '(progn (set-symbol-value (quote ide-buffers) nil) '
        '(%disk-read-sector 40 1) (%disk-poke 130 (- (%disk-byte 130) 1)) '
        '(%disk-poke 131 (- (%disk-byte 131) 128)) (%disk-write-sector 40 1) '
        '(set-symbol-value (quote m65d-remount) t) '
        '(%ide-store-buffer (ide-make-buffer "s" (list "x"))) '
        '(list (save-buffer-to "leak" "s") (ide-error) (m65d-status)))')))
    return cases


def m65d_cases():
    files = {f'F{i:03d}': {'content': f'file {i}', 'capacity': 254} for i in range(144)}
    return [dict(name='disk-d5-remount-144', max_steps=60000000, disk_files=files,
                 expr='(list (m65d-remount) (m65d-status) (m65d-save "f000" "new0") (m65d-remount))')]


LCC_FORMS = [
    ('lcc-car-2args', '(car 1 2)'),
    ('lcc-car-2args-quoted', '(car (quote (1 2)) 2)'),
    ('lcc-car-1arg', '(car (quote (9)))'),
    ('lcc-car-2args-defun', ['(defun k () (car (quote (1)) 2))', '(k)']),
    ('lcc-setq-odd-toplevel', '(setq a 1 b)'),
    ('lcc-setq-odd-defun', ['(defun h () (let ((a 0)) (setq a 1 b)))', '(h)']),
    ('lcc-setq-multi-defun', ['(defun f () (let ((a 0) (b 0) (c 0)) (setq a 1 b 2 c 3) (+ a (+ b c))))', '(f)']),
    ('lcc-setq-multi-global', ['(setq g1 1 g2 2 g3 3)', '(list g1 g2 g3)']),
    # Reviewer LCC arity fix (lcc-profile.lisp %lcc-v2-unary/%lcc-v2-binary): compiled code.
    ('arity-car-2', '(defun ka () (car (quote (1)) 2))'),
    ('arity-cdr-0', '(defun kb () (cdr))'),
    ('arity-consp-2', '(defun kc (x) (consp x x))'),
    ('arity-not-2', '(defun kd (x) (not x x))'),
    ('arity-null-0', '(defun ke () (null))'),
    ('arity-cons-1', '(defun kf (x) (cons x))'),
    ('arity-cons-3', '(defun kg (x) (cons x x x))'),
    ('arity-mod-1', '(defun kh (x) (mod x))'),
    ('arity-valid-control', ['(defun kv (x y) (list (car x) (cdr x) (cons y x) (mod y 3) (consp x) (not y) (null x)))',
                             '(kv (quote (1 2)) 7)']),
    ('arity-toplevel-compiled', '(progn (car (quote (1)) 2))'),
    ('setq-probe-multi-let', ['(defun main () (let ((a 0) (b 0)) (+ 100 (setq a 1 b 2))))', '(main)']),
    ('setq-probe-multi-list', ['(defun main () (let ((a 0) (b 0)) (list 100 (setq a 1 b 2) 7)))', '(main)']),
    ('setq-probe-multi-global', ['(defun main () (+ 100 (setq zz1 1 zz2 2)))', '(main)']),
    ('setq-probe-loop-600', ['(defun main () (let ((a 0) (b 0)) (dotimes (i 600) (setq a i b i)) (+ a b)))', '(main)']),
    ('setq-probe-loop-2000', ['(defun main () (let ((a 0) (b 0)) (dotimes (i 2000) (setq a i b i)) (+ a b)))', '(main)']),
    ('setq-probe-loop-progn-600', ['(defun main () (let ((a 0) (b 0)) (dotimes (i 600) (progn (setq a i) (setq b i))) (+ a b)))', '(main)']),
    ('nth-dotted-0', "(nth 0 (quote (1 2 . 3)))"),
    ('nth-dotted-1', "(nth 1 (quote (1 . 2)))"),
    ('nth-dotted-pair-0', "(nth 0 (quote (1 . 2)))"),
    ('nth-proper-2', "(nth 2 (quote (a b c)))"),
    ('nth-past-end', "(nth 5 (quote (a b)))"),
    ('nth-negative', "(nth -1 (quote (a)))"),
    ('nth-symbol-index', "(nth (quote x) (quote (a)))"),
]


def eval_fixture(count):
    """Stateful eval-buffer fixture: `count` counting forms, the last also sets the sentinel."""
    forms = [f'(if (= c {i}) (setq c (+ c 1)) (setq order-error t))' for i in range(count - 1)]
    forms.append(f'(progn (if (= c {count - 1}) (setq c (+ c 1)) (setq order-error t)) (setq sentinel (quote done)))')
    return forms


EVAL_INIT = ['(setq c 0)', '(setq order-error nil)', '(setq sentinel nil)']
EVAL_CHECK = '(list c sentinel order-error)'
LCC_FORMS += [(f'eval-buffer-{n}-forms-via-lcc', EVAL_INIT + eval_fixture(n) + [EVAL_CHECK]) for n in (5, 50)]


# r8: host VALUES of the nesting-ladder rows at their max depth (the host VM has no soft-frame limit, so the
# overflow one level deeper is the lcc-nesting-ladder-check receipt's fact, not this oracle's).  Generators are
# the ladder gate's own SHAPES (imported, not re-spelled); labels ladder-<shape>-<depth> are read by the r8 row
# table generator.
def _ladder_forms():
    import lcc_nesting_ladder_v253_20261002 as LAD
    gens = {name: make for name, _cls, make in LAD.SHAPES}
    depths = {'let-setq': 8, 'let-dotimes-setq': 6, 'let-arith': 10, 'let-dotimes': 7, 'let-while-setq': 6,
              'let-dolist-setq': 6, 'global-setq': 9, 'upvalue-setq': 5, 'nested-setq': 10}
    forms = [(f'ladder-{shape}-{k}', gens[shape](k)) for shape, k in depths.items()]
    forms.append(('ladder-defun-let-setq-8', [gens['defun-let-setq'](8), '(dz 1)']))
    forms.append(('f2-peek-free-twin', '(let ((s 0)) (dotimes (i 1) (setq s (+ s (+ 1 (+ 160 i))))) s)'))
    return forms


LCC_FORMS += _ladder_forms()


def oracles(out, pre):
    w = worlds(pre)
    for key in ('resident', 'ide', 'm65d', 'lcc', 'lcc_manifest', 'lcc_blob'):
        assert w[key].is_file(), ('preflight world missing', w[key])
    receipt = load_json(pre / 'receipt.json')
    assert receipt['status'] == 'PASS'
    texts = error_texts()
    out.mkdir(parents=True)
    result = dict(status='PASS', preflight=bind(pre / 'receipt.json'), error_texts=bind(ERROR_TEXTS),
                  authority=receipt['source_revision']['authority'], product_links=0, emulator_runs=0)
    result['lcc'] = lcc_carrier(w, LCC_FORMS, texts)
    result['eval_fixtures'] = {n: dict(init=EVAL_INIT, buffer='\n'.join(eval_fixture(n)) + '\n', check=EVAL_CHECK)
                               for n in (5, 50)}
    cases = ide_cases()
    fixtures = {c['name']: c.pop('fixture') for c in cases if 'fixture' in c}
    result['ide'] = run_cases(out, 'ide', w['ide'], cases, texts)
    result['ide']['fixtures'] = fixtures
    result['m65d'] = run_cases(out, 'm65d', w['m65d'], m65d_cases(), texts)
    once(out / 'receipt.json', json.dumps(result, indent=2) + '\n')
    return result


def load_json(path):
    return json.loads(Path(path).read_text())


def main():
    assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--preflight', type=Path, default=ROOT / CFG.PREFLIGHT)
    # r1-r4 retained; r5 = with the lcc-profile arity fix; r6 = r8 world (setq depth fix, ladder forms)
    parser.add_argument('--out', type=Path, default=ROOT / 'build/card-253-row-oracles-r6')
    args = parser.parse_args()
    out = args.out.resolve()
    assert out.is_relative_to(ROOT / 'build') and not out.exists(), 'write-once output under build/'
    result = oracles(out, args.preflight.resolve())
    print(json.dumps(dict(status=result['status'], out=str(out.relative_to(ROOT))), indent=2))


if __name__ == '__main__':
    main()
