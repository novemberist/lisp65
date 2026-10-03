#!/usr/bin/env python3
"""2.5.3 successor route of code_object_arity_contract.py (unchanged, historical).

The reviewer LCC arity fix adds two profile helpers to lib/dialect-v2/lcc-profile.lisp:
%lcc-v2-unary / %lcc-v2-binary, which guard the fixed-arity opcodes (car cdr consp
not null mod cons) in %lcc-expr-ops2 with %lcc-1args-p / %lcc-2args-p and refuse
other counts with %lcc-error-invalid-parameter-list (as src/compile.c does).  The
historical contract pins the exact profile definition inventory; this successor
admits exactly those two names (one seam, count 1) and additionally requires their
guard shape.  Every other assertion of the original runs unchanged.
"""
import sys
import types
from pathlib import Path

BASE = Path(__file__).resolve().with_name('code_object_arity_contract.py')
OLD = '        "%lcc-v2-imm-binds",\n    }\n    expected_definitions = '
NEW = ('        "%lcc-v2-imm-binds",\n'
       '        # 2.5.3 reviewer arity fix (successor route, code_object_arity_contract_v253_20261001.py)\n'
       '        "%lcc-v2-unary", "%lcc-v2-binary",\n'
       '    }\n    expected_definitions = ')
GUARDS = {'%lcc-v2-unary': ('%lcc-1args-p', '%lcc-unary'), '%lcc-v2-binary': ('%lcc-2args-p', '%lcc-binary')}
GUARDED_OPS = {'car': '%lcc-v2-unary', 'cdr': '%lcc-v2-unary', 'consp': '%lcc-v2-unary', 'not': '%lcc-v2-unary',
               'null': '%lcc-v2-unary', 'mod': '%lcc-v2-binary', 'cons': '%lcc-v2-binary'}


def _load():
    text = BASE.read_text(encoding='utf-8')
    if text.count(OLD) != 1:
        raise SystemExit('code-object-arity-contract-v253: FAIL: historical inventory seam not found exactly once')
    module = types.ModuleType('code_object_arity_contract_v253_base')
    module.__file__ = str(BASE)
    sys.modules[module.__name__] = module
    exec(compile(text.replace(OLD, NEW), str(BASE), 'exec'), module.__dict__)
    return module


A = _load()


def guard_shape():
    forms = A.P0C.parse_all((A.ROOT / 'lib/dialect-v2/lcc-profile.lisp').read_text(encoding='utf-8'))
    by_name = {f[1]: f for f in forms if isinstance(f, list) and len(f) >= 4 and f[0] == 'defun'}
    for name, (predicate, emitter) in GUARDS.items():
        body = by_name[name][3]
        if not (isinstance(body, list) and body[0] == 'if' and body[1][0] == predicate
                and body[2][0] == emitter and body[3] == ['%lcc-error-invalid-parameter-list']):
            raise A.ContractError(f'{name} guard shape drift')
    clauses = {c[0][2][1]: c[1] for c in by_name['%lcc-expr-ops2'][3][1:]
               if isinstance(c[0], list) and c[0][:2] == ['eq', 'op'] and isinstance(c[0][2], list)}
    for op, helper in GUARDED_OPS.items():
        if clauses.get(op, [None])[0] != helper:
            raise A.ContractError(f'%lcc-expr-ops2 {op} is not routed through {helper}')


def main():
    if '--selftest' not in sys.argv[1:]:
        try:
            guard_shape()
        except (A.ContractError, KeyError, IndexError, TypeError) as exc:
            print(f'code-object-arity-contract: FAIL: {exc!r}', file=sys.stderr)
            return 1
    return A.main()


if __name__ == '__main__':
    raise SystemExit(main())
