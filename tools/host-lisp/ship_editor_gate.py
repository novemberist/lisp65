"""Permanent host gate for Ship source selection, lowering and closure."""
import copy
import json
from pathlib import Path
import tempfile
import sys

import ship_builder as S
import ship_editor_lowering as L
from c2_v160_input_service_time_pricing import TimingVM


def prompt_check(suite, source):
    """Executed cell oracle; never infer display correctness from return values."""
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 30000))
    class AtReturn(Exception):
        pass
    class VM(TimingVM):
        def _callprim(self, pid, argc, stack, **kwargs):
            if pid == 60 and self.key_events and self.key_events[0][0] == 13:
                raise AtReturn()
            return super()._callprim(pid, argc, stack, **kwargs)
    value = copy.deepcopy(suite)
    value['functions'] = list(dict.fromkeys(value['functions'] + [
        f[1] for f in L.Reader.parse_all(source.read_text())
        if isinstance(f, list) and f and f[0] == 'defun']))
    value['cases'] = [dict(name='prompt', expr='(%native-read-line)', expect='""')]
    h, names, code, flags, resident, bundle, directory, cases, entries, inline = S.Stdlib._compile_suite(value)
    abi, ledger = S.Stdlib._suite_abi(value)
    results = []
    for typed, erased in ((1, 0), (73, 0), (145, 0), (73, 2), (145, 74)):
        vm = VM(heap=h.clone(), directory=directory,
                macro_symbols=S.Stdlib._macro_symbol_objs(h, flags, resident),
                max_steps=2000000, max_call_args=12, abi_profile=abi, abi_ledger=ledger,
                key_events=[97]*typed+[20]*erased+[13], private_key_event_modes=False)
        try:
            vm.run(directory[h.intern(entries[0])], [])
        except AtReturn:
            pass
        else:
            raise AssertionError('missing Return boundary')
        length = typed-erased
        top = length//72
        for row in range(21, 25):
            expected = [32]*80
            offset = row-(24-top)
            if 0 <= offset <= top:
                if offset == 0:
                    expected[:8] = list(b'lisp65> ')
                count = max(0, min(72, length-offset*72))
                expected[8:8+count] = [97]*count
                if offset == top:
                    expected[8+length%72] = 160
            assert vm.screen_cells[row*80:(row+1)*80] == expected, ('prompt cells', typed, erased, row)
        results.append(dict(typed=typed, erased=erased, steps=vm.steps))
    return results


def check():
    controls = []
    with tempfile.TemporaryDirectory(prefix='ship-editor-') as raw:
        root = Path(raw)
        for name in ('first', 'second'):
            S.prepare('(ship "interactive" :entry (quote main))',
                      S.ROOT / 'examples/ship/interactive/project.l65p', root / name)
        assert (root/'first/ship.lock').read_bytes() == (root/'second/ship.lock').read_bytes(), \
            'output directory changed catalogue identity'
        proof = S.load_json(root/'first/editor-lowering.json', 'lowering')['bindings']
        assert len(proof) == 1
        proof = proof[0]
        product = S.ROOT / proof['selected_product']['path']
        lowered = S.ROOT / proof['output']['path']
        L.verify(product.read_text(), lowered.read_text(), proof['lowering'])
        controls += L.selftest(product.read_text())['mutations_rejected']
        source = S.ROOT / proof['authored']['path']
        template = S.ROOT / proof['product']['path']
        derived, binding = L.product_source(source.read_text(), template.read_text())
        assert derived == product.read_text() and binding == proof['product_projection']
        suite = S.load_json(root/'first/suite.json', 'suite')
        domain = S.load_json(root/'first/list-domain-projection.json', 'domain')['bindings']
        assert len(domain) == 1
        domain = domain[0]
        projected = S.ROOT / domain['output']['path']
        base, strict = [S.ROOT / item['path'] for item in domain['inputs']]
        text, receipt = L.compose_list_domain(base.read_text(), strict.read_text())
        assert text == projected.read_text() and receipt == domain['projection']
        domain_suite = copy.deepcopy(suite)
        domain_suite['functions'] = list(dict.fromkeys(domain_suite['functions'] +
            ['append', '%append2', '%append2-rev', '%append-lists', 'length', '%length-from',
             'nthcdr', 'reverse', '%reverse-into']))
        domain_suite['cases'] = [
            dict(name='proper-nthcdr', expr="(nthcdr 1 '(a b))", expect='(b)'),
            dict(name='improper-nthcdr', expr="(nthcdr 0 '(a . b))", expect_vm_error='TypeError'),
            dict(name='improper-append', expr="(append '(a b) 'c)", expect_vm_error='TypeError')]
        S.Stdlib.check_suite('composed Ship list domain', domain_suite)
        for label, replacement in (('permissive-list-domain', str(base)),
                                   ('missing-list-domain', None)):
            mutant = copy.deepcopy(suite)
            mutant['sources'] = [replacement if Path(p).resolve() == projected.resolve() else p
                                 for p in suite['sources']]
            mutant['sources'] = [p for p in mutant['sources'] if p is not None]
            try:
                S.validate_emitted_closure(mutant)
            except (ValueError, S.ShipError, S.Stdlib.StdlibCheckError):
                controls.append(label)
            else:
                raise AssertionError('domain mutation escaped: ' + label)
        original_projection = projected.read_bytes()
        try:
            projected.write_text(text + '\n; forbidden hand edit\n')
            try:
                S.prepare('(ship "interactive" :entry (quote main))',
                          S.ROOT / 'examples/ship/interactive/project.l65p', root/'edited')
            except S.ShipError as exc:
                assert 'edited domain projection' in str(exc), exc
                controls.append('hand-edited-domain-projection')
            else:
                raise AssertionError('edited domain projection accepted')
        finally:
            projected.write_bytes(original_projection)
        prompt_rows = prompt_check(suite, lowered)
        for label, slot in (('prompt-does-not-move', 2), ('old-prompt-not-cleared', 1)):
            forms = L.Reader.parse_all(lowered.read_text())
            lift = next(f for f in forms if isinstance(f, list) and len(f)>1 and f[:2] == ['defun', '%rl-lift'])
            assert lift[3][0] == 'progn' and lift[3][slot][0] == '%rl-label'
            lift[3][slot] = 'nil'
            mutant = root/(label+'.lisp')
            mutant.write_text('\n'.join(L.render(f) for f in forms)+'\n')
            mutated_suite = copy.deepcopy(suite)
            mutated_suite['sources'] = [str(mutant) if Path(p).resolve() == lowered.resolve() else p
                                        for p in suite['sources']]
            try:
                prompt_check(mutated_suite, mutant)
            except AssertionError as exc:
                assert exc.args and isinstance(exc.args[0], tuple) and exc.args[0][0] == 'prompt cells', exc
                controls.append(label)
            else:
                raise AssertionError('display regression escaped: '+label)
        for label in ('missing-source', 'missing-function', 'external-exemption'):
            changed = copy.deepcopy(suite)
            if label == 'missing-source':
                changed['sources'].remove(str(lowered.resolve()))
            elif label == 'missing-function':
                changed['functions'].remove('read-line')
            else:
                changed['allowed_external_calls'] = ['read-line']
            try:
                S.validate_emitted_closure(changed)
            except (S.ShipError, S.Stdlib.StdlibCheckError):
                controls.append(label)
            else:
                raise AssertionError('closure mutation escaped: ' + label)
        return dict(status='PASS', controls=controls, prompt_rows=prompt_rows, product_projection=binding,
                    lowering=proof['lowering'], list_domain=domain,
                    product_builds=0, device_commands=0)


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
