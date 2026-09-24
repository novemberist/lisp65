"""Execute Set-A routing bytecode with explicitly instrumented publication seams.

This proves route selection and reset/add/publish ordering, not native
publication, capacity, recovery, or the ordinary progn 5/6 execution contract.
Those are separate Seed witnesses. Prim 66 is not extended in the host VM.
"""
from pathlib import Path
import argparse
import hashlib
import json

import host_d81_worlds as D

ROOT = Path(__file__).resolve().parents[2]
SUITE = 'build/definition-group-composition-r6/stdlib-candidate-suite.json'


def bind(p):
    p = p.resolve()
    raw = p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)), bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())


def replace_functions(suite, text, heap, directory):
    for form in suite.P.C.parse_all(text):
        name, code, helpers = suite.P.C.compile_top_form_with_helpers(
            form, heap, strict_arity=True, abi_profile=suite.abi)
        directory[heap.intern(name)] = code
        for helper, body in helpers:
            directory[heap.intern(helper)] = body


class Seams(D.B.P0VM):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.operations = []

    def _callprim(self, pid, argc, stack, pc=None, native_base=0, frame_slots=0):
        if pid == 66:
            assert argc == 2
            operation, payload = self._pop_args(argc, stack)
            assert D.B.is_fix(operation) and payload == D.B.NIL
            operation = D.B.fixval(operation)
            assert operation in (0, 3)
            self.operations.append(operation)
            return self.heap.t_obj
        return super()._callprim(pid, argc, stack, pc, native_base, frame_slots)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True, type=Path)
    out = ap.parse_args().out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    cases = [
        ('proper-definitions', "(%c2-definition-group-p '((defun a () 5) (defun b () 6)))", 't', []),
        ('call-rejected', "(%c2-definition-group-p '((defun a () 5) (a)))", 'nil', []),
        ('dotted-spine-rejected', "(%c2-definition-group-p '((defun a () 5) . t))", 'nil', []),
        ('atom-rejected', "(%c2-definition-group-p '(42))", 'nil', []),
        ('marked-group', "(progn (set 'probe-count 0) (%c2-run-expanded '(progn (quote %c2-definition-group) (defun a () 5) (defun b () 6))) (symbol-value 'probe-count))", '2', [0, 3]),
        ('unmarked-progn-sequential', "(%c2-run-expanded '(progn (defun a () 5) (defun b () 6)))", '222', []),
        ('mixed-marker-sequential', "(%c2-run-expanded '(progn (quote %c2-definition-group) (defun a () 5) (a)))", '222', []),
        ('nested-progn-sequential', "(%c2-run-expanded '(progn (quote %c2-definition-group) (progn (defun a () 5))))", '222', []),
    ]
    suite = D.LispSuite(SUITE, [c[1] for c in cases])
    heap, directory = suite.heap.clone(), dict(suite.directory)
    replace_functions(suite, '''
      (defun %c2-source-form (form) (set 'probe-count (+ (symbol-value 'probe-count) 1)) t)
      (defun %c2-top-level-run-forms (forms) 222)
    ''', heap, directory)
    rows = []
    world = D.PRESETS['w4-index-2-t18s34']
    for name, expr, expected, operations in cases:
        value, vm = suite.run(expr, world, heap=heap, directory=directory, vm_class=Seams)
        assert (value, vm.operations) == (expected, operations), (name, value, vm.operations)
        rows.append(dict(name=name, value=value, boundary_operations=vm.operations))
    # If the membership predicate is removed, a call in a marked group is
    # incorrectly admitted to the compiler/publication boundary.
    mh, md = heap.clone(), dict(directory)
    replace_functions(suite, '(defun %c2-definition-group-p (forms) t)', mh, md)
    name, expr, expected, operations = cases[6]
    # Initialize the observation cell without changing the tested form. A
    # mutation must complete the wrong route, not fail in the test fixture.
    replace_functions(suite, '(defun %c2-source-form (form) t)', mh, md)
    value, vm = suite.run(expr, world, heap=mh, directory=md, vm_class=Seams)
    assert (value, vm.operations) != (expected, operations)
    assert value == 't' and vm.operations == [0, 3]
    result = dict(status='PASS: ROUTING ONLY; PUBLICATION SEAMS INSTRUMENTED',
        rows=rows, controls=[dict(name='mixed-group-admission', rejected=True,
                                 observed=value, boundary_operations=vm.operations)],
        inputs=[bind(ROOT/SUITE), bind(ROOT/'lib/dialect-v2/eval-runtime.lisp'),
                bind(Path(__file__))],
        budget=dict(seed=0, final=0, product_link=0),
        remaining=['native integrated publication and capacity',
                   'ordinary progn 5/6 semantics on native Seed',
                   'foreign-code identity on successful and rejected groups'])
    (out/'receipt.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: eight product-bytecode route cases; mixed-group mutation rejected; no native publication claim')


if __name__ == '__main__':
    main()
