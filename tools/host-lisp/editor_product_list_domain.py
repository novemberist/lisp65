"""Require the live V2 editor's resolved list functions to match the product."""
from pathlib import Path
import copy

ROOT = Path(__file__).resolve().parents[2]

def product_forms():
    import bytecode_p0_stdlib as S
    from v2_workbench_codemod import rewrite_tokens
    return {f[1]: f for f in S.C.parse_all(rewrite_tokens(
        (ROOT / 'lib/domain-tier1.lisp').read_text())[0])
        if isinstance(f, list) and f and f[0] == 'defun'}

def compare(resolved, required):
    drift = sorted(n for n, f in required.items()
                   if n in resolved and resolved[n] != f)
    missing = sorted(n for n in ('length', '%length-from', 'nthcdr')
                     if n not in resolved)
    if drift or missing:
        raise ValueError('editor product list domain drift: '
                         + ', '.join(drift + missing))

def check_suite(suite):
    from evidence_era import host_source_commit
    # The explicitly scoped replay reads its own sealed runtime and sources.
    # Applying today's domain there changes the historical executable world.
    # No suite flag or filename can opt a live measurement out of this gate.
    if host_source_commit() is not None:
        return
    import bytecode_p0_stdlib as S
    if suite.get('abi_profile') != 'dialect-v2':
        return
    population = S._resident_suites(suite) + [suite]
    names = {n for s in population for n in s.get('functions', [])}
    # The functional owners, not a list of fixture filenames, select readers.
    if not (names & {'ide-step', 'read-line', '%rl-wait'}):
        return
    resolved = {}
    for member in population:
        forms, _ = S._collect_top_defs(member.get('sources', []))
        resolved.update({n: forms[n] for n in member.get('functions', [])
                         if n in forms})
    compare(resolved, product_forms())

def load_eval_domain():
    import mvp_prelude_m1_eval_oracle as E
    def malformed(args):
        if args:
            raise E.EvalError('list error arity')
        raise E.EvalError('vm: type error')
    E.FUNCTIONS['%LIST-MALFORMED-ERROR'] = E.Primitive('%LIST-MALFORMED-ERROR', malformed)
    E.load_prelude(ROOT / 'lib/domain-tier1.lisp', reset=False)

def selftest():
    import bytecode_p0_stdlib as S
    from v2_workbench_codemod import rewrite_tokens
    required = product_forms()
    compare(required, required)
    old = {f[1]: f for f in S.C.parse_all(rewrite_tokens(
        (ROOT / 'lib/prelude-m1.lisp').read_text())[0])
        if isinstance(f, list) and f and f[0] == 'defun'}
    for name in ('nthcdr', 'length', '%length-from'):
        mutant = copy.deepcopy(required)
        if old.get(name) == required[name]:
            mutant.pop(name)
        else:
            mutant[name] = old[name]
        try:
            compare(mutant, required)
        except ValueError:
            pass
        else:
            raise AssertionError('permissive/missing domain survived: '+name)
    suite = dict(abi_profile='dialect-v2', functions=list(required)+['ide-step'],
                 sources=[str(ROOT/'lib/domain-tier1.lisp'), str(ROOT/'lib/ide-ui.lisp')])
    check_suite(suite)
    suite['sources'].append(str(ROOT/'lib/prelude-m1.lisp'))
    try:
        check_suite(suite)
    except ValueError:
        pass
    else:
        raise AssertionError('resolved permissive source survived suite gate')
    from evidence_era import host_source_world
    with host_source_world('520352a6'):
        check_suite(suite)
    try:
        check_suite(suite)
    except ValueError:
        pass
    else:
        raise AssertionError('historical exemption leaked into live suite')
    print('PASS: editor product list domain; five rejected controls; explicit historical scope restored')

if __name__ == '__main__':
    selftest()
