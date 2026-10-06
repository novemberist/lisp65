#!/usr/bin/env python3
"""Host oracles for the new 2.5.4 emulator rows (no emulator, no device, no product compile/link).

Successor of c253_row_oracles.py (which stays byte-identical).  Two actions:

  oracles --preflight <dir> --table <rows json> --out <new dir under build/>
      Executes the typed forms / key sequences of the 2.5.4 row table on the product worlds that a c254
      preflight emitted and writes one write-once receipt.json:
        lcc       every typed REPL form of the repl-session rows through the packed device compiler exactly as
                  c253_row_oracles.lcc_carrier does (emitted LCC image + projected resident; the product's own
                  %c2-published-direct-call-p decides direct vs compile), one environment per row, every step
                  recorded (a refusal does not end the row)
        ide       the projected product IDE world (c254_e3_product.world; refused unless its compiled blob is the
                  emitted ide image): E3 texts after m keys, pending-C-x row, key extension seam behaviours,
                  ide-bind-key value and registry text, save refusal while a source load is active
        packages  the re-emitted REPL-COMFORT and DEFSTRUCT package worlds (same recipe as
                  c254_product.emit_package; refused unless the compiled blob is the emitted package blob):
                  RP1 bounded result print, HIST1 submitted text after recall, LIB1 macro expansion
  table --draft <rows json> --oracle <receipt.json> --out <rows json>
      The row table with every expected text checked against / replaced by the oracle value and marked:
        HOST-EXECUTED   produced by executing the product world of the named preflight on the host; the screen
                        text is that result under the screen rule (upper-case echo, "*** " + error text, refusal
                        symbol appended to COMPILE FAILED, name appended to UNDEFINED FUNCTION: -- the rule itself
                        is a 2.5.3 emulator observation)
        NOT-DERIVED     could NOT be derived by execution on the product world (device heap/stack limits, native
                        services, emulator transport, timing); the reason is recorded; the text stays an
                        expectation of class OBSERVED until an emulator run

The host VM has no device heap limit, no soft-frame limit and no closure opcode; rows that depend on them say so.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE_DIR))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import c254_config as CFG  # noqa: E402
import c254_e3_product as E3P  # noqa: E402

ROOT = CFG.ROOT
PROFILE = 'dialect-v2'
LEDGER = ROOT / 'config/bytecode-abi-ledger.json'
ERROR_TEXTS = ROOT / 'config/error-texts.json'
# DirMiss (host: 'function not in directory: NAME') is the product's code 28 'undefined function: ' + NAME
# (2.5.x Comfort rows: *** UNDEFINED FUNCTION: CAPZZ).
STATUS_CODE = {'TypeError': 38, 'HeapOOM': 40, 'ArityError': 48, 'BadOpcode': 43, 'DirMiss': 28}
DIR_MISS = 'function not in directory: '
EXECUTED, NOT_DERIVED = 'HOST-EXECUTED', 'NOT-DERIVED'
RP1_LINE = '*** result too deep, too large or circular'
LCC_ROW_GROUPS = ('closure', 'lcc-depth', 'mapcan', 'arity')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def bind(path):
    raw = Path(path).read_bytes()
    return dict(path=str(Path(path).resolve().relative_to(ROOT)), bytes=len(raw), sha256=sha(raw))


def once(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(text)


def load_json(path):
    return json.loads(Path(path).read_text())


def error_texts():
    return {row['code']: row['text'] for row in load_json(ERROR_TEXTS)['entries']}


def screen(error, texts):
    """Screen rule: '*** ' + upper(stable text); COMPILE FAILED carries the refusal symbol on the same line
    (2.5.3 Seed r8 emulator finding); 'undefined function: ' carries the function name."""
    code = error.get('error_code') or STATUS_CODE.get(error['status'])
    text = texts.get(code)
    line = ('*** ' + text.upper()) if text else None
    symbol = error.get('error_symbol')
    if error['status'] == 'DirMiss' and error.get('message', '').startswith(DIR_MISS):
        symbol = error['message'][len(DIR_MISS):].strip()
    if line and text == 'compile failed' and symbol:
        line += symbol.upper()
    if line and text == 'undefined function: ' and symbol:
        line += symbol.upper()
    return dict(code=code, text=text, screen=line)


def vm_error(exc, texts, phase):
    err = dict(status=exc.status, message=str(exc)[:300], error_code=exc.error_code, error_symbol=exc.error_symbol, phase=phase)
    err.update(screen(err, texts))
    return err


# ------------------------------------------------------------------ worlds
def worlds(pre):
    return dict(resident=pre / 'projection/stdlib-p0/suite.json', ide=pre / 'emission/ide/suite.json',
                ide_blob=pre / 'emission/ide/ide.blob.bin', lcc=pre / 'projection/lcc/suite.json',
                lcc_manifest=pre / 'emission/lcc/lcc.manifest.json', lcc_blob=pre / 'emission/lcc/lcc.blob.bin')


class StackTrace:
    """Records the deepest native stack the VM reports (c2_while_gate / probe-integrate pattern)."""
    def __init__(self):
        self.max = 0

    def native_stack(self, _name, used):
        self.max = max(self.max, used)

    def __getattr__(self, _name):
        return lambda *a, **k: None


def lcc_carrier(w, rows, texts):
    """rows: (label, [source, ...], render).  One bound environment per row; every source is one REPL input:
    the product predicate %c2-published-direct-call-p routes it (direct expression, callee = arity authority)
    or the packed LCC compiles it and the code object runs.  render=False: only completion is recorded (cyclic
    results cannot be rendered by the host printer)."""
    import c2_while_gate as G
    suite = STD._read_suite(str(w['lcc']))
    manifest = load_json(w['lcc_manifest'])
    blob = w['lcc_blob'].read_bytes()
    ledger = load_json(LEDGER)
    out = []
    for label, sources, render in rows:
        heap, directory, macros, inliner = G.bound_environment(suite, manifest, blob)
        row = dict(name=label, steps=[])

        def text(obj):
            return heap.obj_to_text(obj) if render else '<completed; not rendered>'
        for index, source in enumerate(sources):
            step = dict(source=source)
            row['steps'].append(step)
            try:
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
                    step.update(route='direct', error=vm_error(exc, texts, 'direct')); continue
                if heap.consp(routed):
                    step.update(route='direct', result=text(heap.cdr(routed)), max_native_stack=pvm.trace.max)
                    continue
                expanded = STD._expand_case_expr(suite, inliner, C.parse_one(f'(%c2-compile-form (quote {source}))'))
                name, caller, helpers = C.compile_top_form_with_helpers(
                    ['defun', f'__row_{index}', [], expanded], heap, strict_arity=True, abi_profile=PROFILE,
                    prebuilt_primitives=True)
                for helper_name, helper in helpers:
                    directory[heap.intern(helper_name)] = helper
                directory[heap.intern(name)] = caller
                vm = B.P0VM(heap=heap, directory=directory, macro_symbols=macros, max_steps=4000000,
                            max_call_args=suite['max_call_args'], abi_profile=PROFILE, abi_ledger=ledger)
                try:
                    generated = vm.run(caller, ())
                except B.VMError as exc:
                    step.update(route='compile', error=vm_error(exc, texts, 'compile')); continue
                codes = []
                for item in G.obj_list(heap, generated):
                    f = G.obj_list(heap, item)
                    codes.append(B.CodeObject(nargs=B.fixval(f[0]), nlocals=B.fixval(f[1]), flags=B.fixval(f[2]),
                                              littab=tuple(G.obj_list(heap, f[3]) if f[3] != B.NIL else ()),
                                              payload=bytes(B.fixval(v) for v in G.obj_list(heap, f[4]))))
                step.update(route='compile', code_objects=len(codes), payload_bytes=len(codes[0].payload))
                parsed = C.parse_one(source)
                if isinstance(parsed, list) and parsed and parsed[0] == 'defun':
                    directory[heap.intern(parsed[1])] = codes[0]   # lcc-install of a defun (host model)
                    step.update(result=parsed[1].upper(), installed=True)
                    continue
                target = B.P0VM(heap=heap, directory=directory, macro_symbols=macros, max_steps=8000000,
                                max_call_args=suite['max_call_args'], abi_profile=PROFILE, abi_ledger=ledger)
                target.trace = StackTrace()
                try:
                    step.update(result=text(target.run(codes[0], ())), max_native_stack=target.trace.max)
                except B.VMError as exc:
                    step.update(error=vm_error(exc, texts, 'run'))
            except Exception as exc:                      # host tool limit, not a product fact
                step.update(host_failure=type(exc).__name__ + ': ' + str(exc)[:200])
        out.append(row)
        print('lcc: ' + label + ': ' + json.dumps([s.get('result', (s.get('error') or {}).get('screen', s.get('host_failure')))
                                                   for s in row['steps']]), flush=True)
    return dict(lcc_image=bind(w['lcc_manifest']), lcc_blob=bind(w['lcc_blob']), suite=bind(w['lcc']), rows=out)


# ------------------------------------------------------------------ ide world
IDE_DRIVERS = E3P.DRIVERS + (
    '(defun seam-bang (buf) (ide-insert-char buf 33))',
    '(defun seam-hash (buf) (ide-insert-char buf 35))',
    '(defun seam-hello (buf) "hello")',
    '(defun seam-nil (buf) nil)',
    '(defun h-registry () (symbol-value (quote ide-bind-key)))',
    '(defun h-save-prepare () (progn (set-symbol-value (quote ide-buffers) nil) '
    '(%ide-store-buffer (ide-make-buffer "selfbuf" (list "one"))) (ide-error)))',
    '(defun h-save (name) (list (save-buffer-to name "selfbuf") (ide-error)))',
)


class IdeVM(E3P._VM):
    """E3 harness VM with the suite's disk model (for the save-refusal row)."""

    def __init__(self, sweep, keys=(), disk=False):
        super().__init__(sweep, keys)
        if disk:
            suite = self.w['suite']
            B.P0VM.__init__(self, heap=self.w['heap'].clone(), directory=self.w['directory'],
                            code_names=self.w['code_names'], macro_symbols=self.w['macro_symbols'],
                            max_steps=10 ** 8, max_call_args=suite.get('max_call_args'),
                            abi_profile=self.w['profile'], abi_ledger=self.w['ledger'],
                            delivered_callprims=suite.get('delivered_callprims'),
                            disk_files=suite.get('disk_files'), d81_bam_model=suite.get('d81_bam_model', False),
                            **STD._disk_world_kwargs(suite, {}))
            self.pending = list(keys)

    def _callprim(self, p, n, stack, **kw):
        if p == 14 and not self.pending:
            return B.NIL
        return super()._callprim(p, n, stack, **kw)


def ide_oracles(w, table):
    world = E3P.world(w['ide'], IDE_DRIVERS)
    blob = w['ide_blob'].read_bytes()
    identity = dict(world_blob_sha256=world['blob_sha256'], emitted=bind(w['ide_blob']),
                    equal=(world['blob_sha256'], world['blob_bytes']) == (sha(blob), len(blob)))
    assert identity['equal'], ('oracle IDE world is not the emitted ide image', identity)
    sweep = E3P.Sweep(world)
    result = dict(world_identity=identity, suite=bind(w['ide']))
    # E3: texts after m accepted keys, through the REAL product loop (ide-run) and through the drain shape.
    e3 = {}
    for row in table['rows']:
        exp = row.get('expected', {})
        if row.get('group') != 'e3' or 'texts_after_m_keys' not in exp:
            continue
        codes = [k for k in exp['keys'] if isinstance(k, int)]
        keys = ''.join(chr(k) for k in codes)
        initial = exp.get('initial_lines', [''])
        texts = {shape: [sweep.session(shape, keys[:m], initial)['text'] for m in range(len(keys) + 1)]
                 for shape in E3P.SHAPES}
        poll = sweep.session('run', keys, initial, stop_at_poll=True)
        e3[row['id']] = dict(keys=codes, initial=initial, texts_after_m_keys=texts['run'],
                             drain_shape_equal=texts['run'] == texts['drain'],
                             table=exp['texts_after_m_keys'], table_equal=texts['run'] == exp['texts_after_m_keys'],
                             idle_text=poll['text'])
        print('ide: e3 texts ' + row['id'] + ': table_equal=' + str(e3[row['id']]['table_equal']), flush=True)
    result['e3_texts'] = e3
    result['pending_cx_reset'] = sweep.d4_row()
    # pending C-x with f BOUND (ide-bind-key 102 seam-bang): after STOP and re-entry f must insert f.
    v = IdeVM(sweep)
    v.heap.set_symbol_value(v.heap.intern('ide-event-command'), B.NIL)
    name, buf = sweep.make_buffer(v, ['ab'])
    state = v.call('h-start', buf)
    bound_value = v.py(v.call('ide-bind-key', B.mkfix(102), v.heap.intern('seam-bang')))
    v.call('ide-step', state, v.key(24))
    v.pending = ['f']
    try:
        v.call('ide', name)
    except E3P.Stop:
        pass
    result['pending_cx_reset_bound'] = dict(first_key_line=v.py(v.call('ide-current-line', v.call('h-resume', name))))
    # Seam behaviours in the order the table's seam group executes them.
    v = IdeVM(sweep)
    v.heap.set_symbol_value(v.heap.intern('ide-event-command'), B.NIL)

    def registry():
        try:
            return v.heap.obj_to_text(v.call('h-registry'))
        except B.VMError as exc:
            return 'ERROR ' + exc.status + ': ' + str(exc)[:120]

    def lm(state):
        return dict(line=v.py(v.call('ide-current-line', v.call('ide-state-buffer', state))),
                    message=v.py(v.call('ide-state-message', state)))

    def cx(state, code):
        return v.call('ide-step', v.call('ide-step', state, v.key(24)), v.key(code))
    seam = dict(registry_initial=registry())
    name = v.text('sm')
    buf = v.call('ide-make-buffer', name, v.lst([v.text('ab')]))
    buf = v.call('h-with-point', buf, v.heap.cons(B.mkfix(0), B.mkfix(2)))
    v.call('%ide-store-buffer', buf)
    s = v.call('ide-make-state', buf)
    seam['unbound_cx_f'] = lm(cx(s, 102))
    seam['bind_102_bang_value'] = v.py(v.call('ide-bind-key', B.mkfix(102), v.heap.intern('seam-bang')))
    s = cx(s, 102); seam['bound_cx_f'] = lm(s)
    s = cx(s, 102); seam['bound_cx_f_twice'] = lm(s)
    seam['bind_102_hash_value'] = v.py(v.call('ide-bind-key', B.mkfix(102), v.heap.intern('seam-hash')))
    s = cx(s, 102); seam['later_binding_shadows'] = lm(s)
    seam['bind_104_hello_value'] = v.py(v.call('ide-bind-key', B.mkfix(104), v.heap.intern('seam-hello')))
    seam['string_result_is_message'] = lm(cx(s, 104))
    seam['bind_110_nil_value'] = v.py(v.call('ide-bind-key', B.mkfix(110), v.heap.intern('seam-nil')))
    seam['nil_result_unchanged'] = lm(cx(s, 110))
    st = cx(s, 8)                                    # C-x then a control key cancels the prefix
    seam['cx_control_key'] = dict(**lm(st), prefix=v.py(v.sym('ide-event-command')))
    seam['f_after_cancel'] = lm(v.call('ide-step', st, v.key(102)))
    seam['bind_113_bang_value'] = v.py(v.call('ide-bind-key', B.mkfix(113), v.heap.intern('seam-bang')))
    seam['builtin_cx_q'] = lm(cx(s, 113))
    seam['registry_final'] = registry()
    result['seam'] = seam
    print('ide: seam ' + json.dumps(seam), flush=True)
    # Save refused while a source load is active (the native query io_disk_source_idle is the VM attribute).
    v = IdeVM(sweep, disk=True)

    def value(o):
        return True if o == v.heap.t_obj else v.py(o)
    save = dict(ide_error_before=value(v.call('h-save-prepare')))
    v.disk_source_active = True
    r = v.call('h-save', v.text('selfout'))
    save['during_load'] = dict(saved=value(v.heap.car(r)), ide_error=value(v.heap.car(v.heap.cdr(r))))
    v.disk_source_active = False
    r = v.call('h-save', v.text('selfok'))
    save['after_load'] = dict(saved=value(v.heap.car(r)), ide_error=value(v.heap.car(v.heap.cdr(r))))
    assert save['during_load'] == dict(saved=None, ide_error='save refused while a file loads'), save
    result['save_refused'] = save
    print('ide: save ' + json.dumps(save), flush=True)
    return result


# ------------------------------------------------------------------ package worlds
def package_suite(pre, name):
    """The suite c254_product.emit_package emitted the package from (same recipe, read-only)."""
    suite_path = str(ROOT / CFG.PACKAGE_SUITE[name])
    suite = STD._read_suite(suite_path)
    suite['sources'] = [str(ROOT / s) for s in CFG.PACKAGE_SOURCES[name]]
    resident = CFG.PACKAGE_RESIDENT[name]
    suite.pop('resident_suites', None)
    suite['resident_suite'] = str(pre / 'projection/stdlib-p0/suite.json' if resident == CFG.PRODUCT_RESIDENT
                                  else ROOT / resident)
    return suite


def compile_package(name, suite, cases, base_addr=None, include_cases=True):
    suite = dict(suite, cases=cases)
    kw = dict(include_cases=include_cases) if base_addr is None else dict(base_addr=base_addr, include_cases=include_cases)
    if name in CFG.PACKAGE_LIST_DOMAIN_WAIVER:
        import editor_product_list_domain as DOMAIN
        with patch.object(DOMAIN, 'check_suite', lambda suite: None):
            return STD._compile_suite(suite, **kw)
    return STD._compile_suite(suite, **kw)


def package_world(pre, name, cases):
    """Compile the package suite and prove it IS the emitted package: same objects in the same order, every
    object header and payload byte-identical to the emitted blob (literal-table words are host placeholders
    that the loader rewrites, so they are not compared -- the same rule as c254_product.entry_code)."""
    suite = package_suite(pre, name)
    base = pre / 'packages/emission' / name
    manifest, blob = load_json(base / (name + '.manifest.json')), (base / (name + '.blob.bin')).read_bytes()
    compiled = compile_package(name, suite, [dict(name='emission-only', expr='nil', expect='nil')], base_addr=0, include_cases=False)
    names, code_by_name = compiled[1], compiled[2]
    entries = manifest['entries']
    assert [e['name'] for e in entries] == list(names), ('package object population', name)
    for e in entries:
        raw = blob[e['blob_offset']:e['blob_offset'] + e['length']]
        code = code_by_name[e['name']]
        enc = code.encode()
        cut = 7 + 2 * len(code.littab)
        assert len(raw) == len(enc) and raw[:7] == enc[:7] and raw[cut:] == enc[cut:], \
            ('oracle package world is not the emitted package', name, e['name'])
    identity = dict(emitted=bind(base / (name + '.blob.bin')), manifest=bind(base / (name + '.manifest.json')),
                    objects=len(entries), code_bytes=len(blob), equal='every object header and payload byte-identical',
                    pinned_code=list(CFG.PACKAGE_BLOBS[name]))
    assert len(blob) == CFG.PACKAGE_BLOBS[name][1]
    return suite, compile_package(name, suite, cases), identity


def comfort_vm_class():
    from c2_v160_input_service_time_pricing import TimingVM

    class ComfortVM(TimingVM):
        """TimingVM with the product arena/screen model of build/multiline-lite-r2/oracle.py (VM._callprim)."""
        def _callprim(self, prim_id, argc, stack, **kw):
            if prim_id == 1 and argc == 1:
                codes = super()._callprim(prim_id, argc, stack, **kw)
                return self._list_from_objs(self._list_to_objs(codes, 'arena copy'))
            if prim_id in (2, 29) and argc == 1:
                stack[-1] = self._list_from_objs(self._list_to_objs(stack[-1], 'arena snapshot'))
            if prim_id == 9:
                return self._list_from_objs([B.mkfix(self.screen_columns), B.mkfix(self.screen_rows)])
            return super()._callprim(prim_id, argc, stack, **kw)
    return ComfortVM


def run_package_cases(name, compiled, suite, cases, vm_class=B.P0VM, extra=None):
    heap, _names, _code, flags, rflags, _bundle, directory, compiled_cases, entries, _inl = compiled
    profile, ledger = STD._suite_abi(suite)
    rows = []
    for case, entry in zip(compiled_cases, entries):
        kw = dict(heap=heap.clone(), directory=directory, macro_symbols=STD._macro_symbol_objs(heap, flags, rflags),
                  max_steps=case.get('max_steps', 10000000), abi_profile=profile, abi_ledger=ledger)
        kw.update(extra(case) if extra else {})
        vm = vm_class(**kw)
        if vm_class is not B.P0VM:
            vm.screen_columns = 80; vm.screen_cells = [32] * (80 * 25)
        row = dict(name=case['name'], expr=case['expr'])
        try:
            answer = vm.run(directory[heap.intern(entry)], [])
            row['answer'] = vm.heap.obj_to_text(answer) if case.get('render', True) else '<not rendered>'
        except B.VMError as exc:
            row['error'] = dict(status=exc.status, message=str(exc)[:200], error_code=exc.error_code,
                                error_symbol=exc.error_symbol)
        except AssertionError as exc:
            row['error'] = dict(status='HostAssertion', message=str(exc)[:200])
        row['output'] = ''.join(map(chr, getattr(vm, 'output_chars', [])))
        row['steps'] = vm.steps
        row['keys_left'] = len(getattr(vm, 'key_events', None) or [])
        rows.append(row)
        print(f"{name}: {case['name']}: answer={row.get('answer')!r} output={row['output']!r} error={row.get('error')}", flush=True)
    return rows


def lisp_string(text):
    """A Lisp expression building `text` (which may contain double quotes and line feeds)."""
    parts = text.split('"')
    expr = '"%s"' % parts[0]
    for q in parts[1:]:
        expr = '(string-append (string-append %s (char->string 34)) "%s")' % (expr, q)
    return expr


def package_oracles(pre, table):
    result = {}
    rows = {r['id']: r for r in table['rows']}
    # RP1: the Comfort result print of the value of every typed form (the emitted %lt-write).
    cases = []
    for rid in ('rp1-bounded-result', 'rp1-accepted-large', 'rp1-depth8-reentry', 'rp1-flat-1101-heap'):
        for i, e in enumerate(rows[rid]['expected'].get('screen', [])):
            form = e['input']
            if form.startswith('(') and form not in ('(repl)',):
                cases.append(dict(name=f'{rid}#{i}', expr=f'(%lt-write {form})', expect='?', form=form, render=False,
                                  max_steps=20000000))
    suite, compiled, identity = package_world(pre, 'repl-comfort', cases)
    Comfort = comfort_vm_class()
    extra = lambda case: dict(key_events=list(case.get('key_events', [])), private_key_event_modes=True, batch_cap=1)
    out = run_package_cases('rp1', compiled, suite, cases, Comfort, extra)
    for case, row in zip(cases, out):
        row['form'] = case['form']
        row['refused'] = row['output'] == RP1_LINE + '\n'
    result['comfort'] = dict(world_identity=identity, rp1=out)
    # HIST1: the text Comfort submits (a) when the row's key sequence is typed, (b) after UP + Return on that
    # history.  %repl-step returns the submitted text; an 'unexpected empty input poll' means it asked for
    # another line (the 2.5.3 defect).
    hist_cases = []
    for rid in ('hist1-recall-comment', 'hist1-recall-two-comments'):
        typed, segment = [], ''
        for k in rows[rid]['expected']['keys']:
            send = k['send']
            if isinstance(send, str):
                segment += send
                if k.get('want_prompt') == 'C':
                    typed.append(segment); segment = ''
        for i, text in enumerate(typed):
            keys = [13 if ch == '\n' else ord(ch) for ch in text]
            hist_cases.append(dict(name=f'{rid}#typed{i}', keys_text=text, key_events=keys, expect='?', max_steps=6000000,
                                   expr='(progn (set-symbol-value (quote %comfort-history) nil) '
                                        '(%repl-step (symbol-value (quote %comfort-history)) "" 0))'))
    _suite, compiled, _ = package_world(pre, 'repl-comfort', hist_cases)
    typed_rows = run_package_cases('hist1-typed', compiled, suite, hist_cases, Comfort, extra)
    recall_cases = []
    for case, row in zip(hist_cases, typed_rows):
        row['keys_text'] = case['keys_text']
        if 'answer' not in row:
            continue
        submitted = row['answer'][1:-1] if row['answer'].startswith('"') else row['answer']
        row['submitted'] = submitted
        recall_cases.append(dict(name=case['name'].replace('typed', 'recall'), key_events=[145, 13], expect='?',
                                 max_steps=6000000, recalled=submitted,
                                 expr='(progn (set-symbol-value (quote %%comfort-history) (list %s)) '
                                      '(%%repl-step (symbol-value (quote %%comfort-history)) "" 0))' % lisp_string(submitted)))
    recall_rows = []
    if recall_cases:
        _suite, compiled, _ = package_world(pre, 'repl-comfort', recall_cases)
        recall_rows = run_package_cases('hist1-recall', compiled, suite, recall_cases, Comfort, extra)
        for case, row in zip(recall_cases, recall_rows):
            row['recalled'] = case['recalled']
            row['submitted_at_once'] = ('answer' in row and row['keys_left'] == 0
                                        and row['answer'].strip('"') == case['recalled'])
    result['comfort']['hist1'] = dict(typed=typed_rows, recall=recall_rows)
    # LIB1: the emitted DEFSTRUCT macro on the row's forms (expansion only; the REPL then runs the expansion).
    lib_cases = []
    for i, e in enumerate(rows['lib1-defstruct-collision']['expected']['screen']):
        form = C.parse_one(e['input'])
        if isinstance(form, list) and form and form[0] == 'defstruct':
            args = ' '.join('(quote %s)' % a for a in form[1:])
            lib_cases.append(dict(name=f'lib1#{i}', form=e['input'], expect='?', expr=f'(funcall (quote defstruct) {args})'))
    dsuite, dcompiled, didentity = package_world(pre, 'defstruct', lib_cases)
    lib_rows = run_package_cases('lib1', dcompiled, dsuite, lib_cases)
    for case, row in zip(lib_cases, lib_rows):
        row['form'] = case['form']
    result['defstruct'] = dict(world_identity=didentity, expansions=lib_rows)
    return result


# ------------------------------------------------------------------ oracles
def lcc_rows(table, expansions):
    rows = []
    for row in table['rows']:
        exp = row.get('expected', {})
        inputs = [e['input'] for e in exp.get('screen', [])] + [k for k in exp.get('any_of', {})]
        if row.get('group') in LCC_ROW_GROUPS and inputs:
            rows.append((row['id'], inputs, True))
        elif row.get('group') == 'rp1' and inputs:
            rows.append((row['id'], [i for i in inputs if i != '(repl)' and i.startswith('(')], False))
    # LIB1 second stage: what the REPL does with the macro expansion of a refused defstruct, and the
    # constructor of a struct that was never defined.
    refused = sorted({r['answer'] for r in expansions if 'answer' in r and r['answer'].startswith('(%defstruct-error')})
    rows.append(('lib1-expansion', refused + ['(make-r 1)'], True))
    return rows


def oracles(out, pre, table_path):
    w = worlds(pre)
    for key, path in w.items():
        assert path.is_file(), ('preflight world missing', key, path)
    receipt = load_json(pre / 'receipt.json')
    assert receipt['status'] == 'PASS'
    assert {k: tuple(v) for k, v in receipt['candidate_blobs'].items()} == {k: tuple(v) for k, v in CFG.CANDIDATE_BLOBS.items()}, \
        'preflight images are not the pinned images'
    table = load_json(table_path)
    texts = error_texts()
    out.mkdir(parents=True)
    result = dict(status='PASS', preflight=bind(pre / 'receipt.json'), table=bind(table_path),
                  error_texts=bind(ERROR_TEXTS), authority=receipt['source_revision']['authority'],
                  candidate_blobs=receipt['candidate_blobs'], package_blobs=receipt['package_blobs'],
                  tools=[bind(__file__), bind(E3P.__file__), bind(CFG.__file__)], product_links=0, emulator_runs=0)
    result['packages'] = package_oracles(pre, table)
    result['ide'] = ide_oracles(w, table)
    result['lcc'] = lcc_carrier(w, lcc_rows(table, result['packages']['defstruct']['expansions']), texts)
    # Accepted (not refused, acyclic) RP1 values: a second carrier pass renders them (the first pass never
    # renders rp1 rows: a cyclic value cannot be printed by the host printer either).
    accepted = {}
    for r in result['packages']['comfort']['rp1']:
        if not r['refused'] and 'error' not in r and not r['name'].startswith('rp1-flat'):
            accepted.setdefault(r['name'].split('#')[0], []).append(r['form'])
    result['lcc_rp1_rendered'] = lcc_carrier(w, [(rid + '#rendered', forms, True) for rid, forms in sorted(accepted.items())], texts)
    once(out / 'receipt.json', json.dumps(result, indent=2) + '\n')
    return result


# ------------------------------------------------------------------ table
def upper_screen(text):
    return text.upper()


def apply_table(draft_path, oracle_path, out_path):
    doc = load_json(draft_path)
    orc = load_json(oracle_path)
    lcc = {r['name']: {s['source']: s for s in r['steps']} for r in orc['lcc']['rows']}
    rp1 = {r['form']: r for r in orc['packages']['comfort']['rp1']}
    hist = orc['packages']['comfort']['hist1']
    ide = orc['ide']
    seam = ide['seam']
    counts = {EXECUTED: 0, NOT_DERIVED: 0}
    changes = []

    def mark(entry, kind, **kw):
        entry['derivation'] = dict(mark=kind, **kw)
        counts[kind] += 1

    def set_screen(rid, entry, value, **kw):
        if entry.get('screen') != value:
            changes.append(dict(row=rid, input=entry.get('input'), draft=entry.get('screen'), host=value))
            entry['draft_screen'] = entry.get('screen')
            entry['screen'] = value
        mark(entry, EXECUTED, **kw)

    def lcc_value(rid, source):
        step = lcc.get(rid, {}).get(source)
        if step is None or 'host_failure' in step:
            return None, step
        if 'error' in step:
            return step['error']['screen'], step
        return upper_screen(step['result']), step

    for row in doc['rows']:
        rid, exp, group = row['id'], row.get('expected', {}), row.get('group')
        for entry in exp.get('screen', []):
            source = entry.get('input')
            if group in LCC_ROW_GROUPS:
                value, step = lcc_value(rid, source)
                if rid == 'closure-still-refused' and entry.get('screen') == '*** VM: BAD BYTECODE':
                    mark(entry, NOT_DERIVED, why='the host target VM has no closure opcode; its refusal is a host-model limit, '
                         'not the product path (2.5.3 emulator class evidence)', host=(step or {}).get('error', {}).get('message'),
                         host_route=(step or {}).get('route'))
                elif rid == 'lcc-ladder-closure' and (value is None or value != entry.get('screen')):
                    mark(entry, NOT_DERIVED, why='device soft-frame/native-stack limit; the host VM has none (ladder gate model)',
                         host_value=value)
                elif value is None:
                    mark(entry, NOT_DERIVED, why='host carrier could not run the form', host=step)
                elif entry.get('screen') is None:
                    mark(entry, EXECUTED, host_value=value, route=step.get('route'), note='row checks "no *** line"')
                else:
                    set_screen(rid, entry, value, route=step.get('route'), world='lcc image + projected resident')
            elif group == 'rp1':
                r = rp1.get(source)
                step = lcc.get(rid, {}).get(source, {})
                if source == '(repl)' or r is None:
                    mark(entry, NOT_DERIVED, why='native prompt / re-entry is not modelled on the host')
                elif rid == 'rp1-flat-1101-heap':
                    mark(entry, NOT_DERIVED, why='device heap limit (1,071 cells); on the host the form completes and '
                         'the print is ' + ('REFUSED' if r['refused'] else 'accepted'), host_refused=r['refused'])
                elif r.get('error') or 'error' in step or 'host_failure' in step:
                    mark(entry, NOT_DERIVED, why='host run failed', host=r.get('error') or step)
                elif r['refused']:
                    set_screen(rid, entry, upper_screen(RP1_LINE), world='re-emitted REPL-COMFORT %lt-write', route=step.get('route'))
                elif entry.get('screen') is None:
                    mark(entry, EXECUTED, host_refused=False, route=step.get('route'), note='row checks "no refusal line"')
                else:
                    # accepted: the value is printed by the product printer; the host renders the same value
                    from_lcc = lcc_rendered.get((rid, source))
                    if from_lcc is None:
                        mark(entry, NOT_DERIVED, why='accepted by %lt-write on the host; printed text not rendered', host_refused=False)
                    else:
                        set_screen(rid, entry, from_lcc, world='re-emitted REPL-COMFORT %lt-write (accepted) + lcc value', route=step.get('route'))
            elif group == 'lib1':
                exps = {r['form']: r for r in orc['packages']['defstruct']['expansions']}
                if source in exps and exps[source].get('answer', '').startswith('(%defstruct-error'):
                    value, step = lcc_value('lib1-expansion', exps[source]['answer'])
                    if value is None:
                        mark(entry, NOT_DERIVED, why='expansion executed, REPL stage failed on the host', host=step)
                    else:
                        set_screen(rid, entry, value, world='re-emitted DEFSTRUCT macro expansion ' + exps[source]['answer']
                                   + ', then the packed LCC / REPL route', route=step.get('route'))
                elif source == '(make-r 1)':
                    value, step = lcc_value('lib1-expansion', source)
                    if value is None:
                        mark(entry, NOT_DERIVED, why='host carrier could not run the form', host=step)
                    else:
                        set_screen(rid, entry, value, world='lcc image + projected resident (nothing defined)', route=step.get('route'))
                elif source in exps and 'answer' in exps[source]:
                    mark(entry, NOT_DERIVED, why='accepted: the macro expands (head ' + exps[source]['answer'][:24]
                         + '...); the printed line of the defstruct form is device output', host_expansion_head=exps[source]['answer'][:60])
                else:
                    mark(entry, NOT_DERIVED, why='needs the loaded DEFSTRUCT package inside the REPL (require / installed accessors)')
            elif rid == 'seam-prepare':
                if 'symbol-value' in source:
                    set_screen(rid, entry, upper_screen(seam['registry_initial']), world='projected product IDE image')
                else:
                    mark(entry, NOT_DERIVED, why='REPL defun print line; the functions run on the host as harness drivers')
            elif group == 'seam' and source.startswith('(ide-bind-key '):
                key, name = source.split()[1], source.split()[3].rstrip(')').replace('seam-', '')
                set_screen(rid, entry, str(seam['bind_%s_%s_value' % (key, name)]), world='projected product IDE image')
            elif rid == 'seam-registry-value':
                set_screen(rid, entry, upper_screen(seam['registry_final']), world='projected product IDE image',
                           note='binding order 102 bang, 102 hash, 104 hello, 110 nil, 113 bang in ONE boot (seam group)')
            elif rid == 'save-refused-during-load':
                s = ide['save_refused']
                host = {1: s['ide_error_before'], 3: s['during_load']['ide_error'], 4: s['after_load']['saved'],
                        5: s['after_load']['ide_error']}
                index = exp['screen'].index(entry)
                if index in host:
                    v = host[index]
                    value = 'NIL' if v is None else ('T' if v is True or v == 't' else '"%s"' % str(v).upper() if index in (1, 3, 5) else str(v).upper())
                    set_screen(rid, entry, value, world='projected product IDE image, loader flag set by the host (disk_source_active)',
                               host_value=v, nested_save_result=s['during_load']['saved'])
                else:
                    mark(entry, NOT_DERIVED, why='native loader / fixture step (device return value)')
            else:
                mark(entry, NOT_DERIVED, why='no host execution for this step (emulator transport or native service)')
        if 'any_of' in exp:
            fixed = {}
            for source, options in exp['any_of'].items():
                value, step = lcc_value(rid, source)
                if (rid == 'mapcan-heap-edge' and len(options) > 1) or value is None:
                    fixed[source] = dict(any_of=options, derivation=dict(mark=NOT_DERIVED, host_value=value,
                                         why='device heap fit decides between the value and the OOM line'))
                    counts[NOT_DERIVED] += 1
                else:
                    assert value in options, ('host text outside the draft choice', rid, source, value)
                    fixed[source] = dict(any_of=[value], draft_any_of=options,
                                         derivation=dict(mark=EXECUTED, route=step.get('route'), world='lcc image + projected resident',
                                                         caution='the route predicate ran on the host; 2.5.3 r8 saw one host/device '
                                                                 'route divergence (progn-wrapped car)'))
                    counts[EXECUTED] += 1
            exp['any_of'] = fixed
        if group == 'e3' and 'texts_after_m_keys' in exp:
            t = ide['e3_texts'][rid]
            if not t['table_equal']:
                changes.append(dict(row=rid, draft=exp['texts_after_m_keys'], host=t['texts_after_m_keys']))
                exp['draft_texts_after_m_keys'] = exp['texts_after_m_keys']
                exp['texts_after_m_keys'] = t['texts_after_m_keys']
            exp['derivation'] = dict(mark=EXECUTED, world='projected product IDE image (real loop ide-run; drain shape equal: %s)'
                                     % t['drain_shape_equal'], what='texts_after_m_keys and the j-1/j rule (c254_e3_product sweeps)',
                                     not_derived='where the device aborts, the counter j, the screen after re-entry')
            counts[EXECUTED] += 1
        if rid == 'e3-pending-cx-reset':
            ok = ide['pending_cx_reset']
            assert ok['ok'] and ok['first_key_line'] == 'abf'
            exp['derivation'] = dict(mark=EXECUTED, world='projected product IDE image, real (ide "audit") entry', host=ok)
            counts[EXECUTED] += 1
        if rid == 'e3-pending-cx-reset-bound':
            exp['derivation'] = dict(mark=EXECUTED, world='projected product IDE image', host=ide['pending_cx_reset_bound'])
            assert ide['pending_cx_reset_bound']['first_key_line'] == 'abf'
            counts[EXECUTED] += 1
        if group == 'seam' and 'keys' in exp:
            want = {'seam-unbound-unknown': seam['unbound_cx_f'], 'seam-bind-buffer': seam['bound_cx_f_twice'],
                    'seam-message-result': seam['string_result_is_message'], 'seam-nil-result': seam['nil_result_unchanged'],
                    'seam-control-cancels': seam['f_after_cancel'], 'seam-builtin-not-overridable': seam['builtin_cx_q']}.get(rid)
            exp['derivation'] = dict(mark=EXECUTED, world='projected product IDE image (ide-step path)', host=want,
                                     host_all={k: seam[k] for k in seam if isinstance(seam[k], dict)},
                                     not_derived='status-line placement on the screen, HWA key codes')
            counts[EXECUTED] += 1
        if group == 'hist1':
            typed = [r for r in hist['typed'] if r['name'].startswith(rid + '#')]
            recall = [r for r in hist['recall'] if r['name'].startswith(rid + '#')]
            ok = bool(recall) and all(r.get('submitted_at_once') for r in recall)
            exp['derivation'] = dict(mark=EXECUTED if ok else NOT_DERIVED,
                                     world='re-emitted REPL-COMFORT (%repl-step with scripted keys)',
                                     typed=[dict(keys=r.get('keys_text'), submitted=r.get('submitted'), error=r.get('error')) for r in typed],
                                     recall=[dict(recalled=r.get('recalled'), submitted_at_once=r.get('submitted_at_once'), error=r.get('error')) for r in recall],
                                     not_derived='the evaluated values on the device screen and the prompt glyphs (the host proves the '
                                                 'submitted text; the value of that text is ordinary evaluation)')
            counts[EXECUTED if ok else NOT_DERIVED] += 1
        if rid == 'stop-probe':
            exp['derivation'] = dict(mark=NOT_DERIVED, why='RUN/STOP transport of the emulator driver; text from src/interrupt.c / error-texts code 1')
            counts[NOT_DERIVED] += 1
    doc['status'] = ('2.5.4 Seed row table.  Every expected text carries derivation.mark: HOST-EXECUTED = executed on the '
                     'product world of the named preflight (screen rule applied); NOT-DERIVED = could not be derived by '
                     'execution on the product world (reason recorded).  Emulator not run.')
    doc['authority'] = orc['authority']
    doc['oracle'] = dict(receipt=bind(oracle_path), preflight=orc['preflight'], candidate_blobs=orc['candidate_blobs'],
                         package_blobs=orc['package_blobs'], marks=counts, changes_against_draft=changes,
                         draft=dict(path=str(Path(draft_path).resolve().relative_to(ROOT)), sha256=sha(Path(draft_path).read_bytes())))
    once(Path(out_path), json.dumps(doc, indent=1) + '\n')
    return dict(status='PASS', marks=counts, changes=changes)


lcc_rendered = {}


def main():
    assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='action', required=True)
    a = sub.add_parser('oracles')
    a.add_argument('--preflight', type=Path, default=ROOT / CFG.PREFLIGHT)
    a.add_argument('--table', type=Path, required=True)
    a.add_argument('--out', type=Path, required=True)
    b = sub.add_parser('table')
    b.add_argument('--draft', type=Path, required=True)
    b.add_argument('--oracle', type=Path, required=True)
    b.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'oracles':
        out = args.out.resolve()
        assert out.is_relative_to(ROOT / 'build') and not out.exists(), 'write-once output under build/'
        sys.setrecursionlimit(100000)
        result = oracles(out, args.preflight.resolve(), args.table.resolve())
        print(json.dumps(dict(status=result['status'], out=str(out.relative_to(ROOT))), indent=2))
    else:
        assert not args.out.exists(), 'table output is write-once'
        orc = load_json(args.oracle)
        # value text of accepted RP1 forms: the lcc carrier does not render rp1 rows (cycles); accepted,
        # acyclic values are rendered by a second carrier pass recorded in the receipt as lcc_rp1_rendered.
        for r in orc.get('lcc_rp1_rendered', {}).get('rows', []):
            for s in r['steps']:
                if 'result' in s:
                    lcc_rendered[(r['name'].replace('#rendered', ''), s['source'])] = upper_screen(s['result'])
        print(json.dumps(apply_table(args.draft.resolve(), args.oracle.resolve(), args.out.resolve()), indent=2))


if __name__ == '__main__':
    main()
