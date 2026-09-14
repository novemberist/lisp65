#!/usr/bin/env python3
"""Execute the loader-owner echo contract; native pixels remain a product lane."""
from pathlib import Path
import re
import subprocess
import tempfile
import inspect

import init_require_scratch_gate as H

ROOT = Path(__file__).resolve().parents[2]


def main():
    body = re.search(r'unsigned char io_disk_source_idle\(void\) \{[^}]+\}',
                     (ROOT / 'src/io.c').read_text()).group()
    unit = ('static unsigned char disk_source_active;\n' + body +
            '\nint main(void){for(unsigned int i=0;i<256;i++){'
            'disk_source_active=i;if(io_disk_source_idle()!=(i==0))return 1;}'
            'return 0;}\n')
    with tempfile.TemporaryDirectory(prefix='lisp65-echo-') as tmp:
        path = Path(tmp)
        for label, text, expected in (
                ('live', unit, 0),
                ('always-idle', unit.replace('return !disk_source_active;', 'return 1;'), 1),
                ('always-active', unit.replace('return !disk_source_active;', 'return 0;'), 1)):
            source = path / (label + '.c')
            source.write_text(text)
            binary = path / label
            subprocess.run(['cc', '-Wall', '-Werror', str(source), '-o', str(binary)], check=True)
            assert subprocess.run([str(binary)]).returncode == expected
    world = H.World()
    vm = world.vm(H.build_disk(H.FIXTURE_TEXT), 'owner-token')
    assert vm.evaluate('(load "init.l65")') == 't'
    assert vm.loaded == ['place', 'string-extra'] and not vm.output_chars
    assert vm.evaluate('(capitalize "abc")') == '"Abc"'
    assert vm.heap.intern('setf') in vm.directory
    for name, answer in (('place', 't'), ('no-such', 'nil')):
        vm.output_chars.clear()
        assert vm.evaluate(f'(require "{name}")') == answer
        assert bytes(vm.output_chars) == f'loading {name}...\n'.encode()
    original = H.DiskVM._callprim
    def unconditional(self, prim, argc, stack, pc=None, native_base=0, frame_slots=0):
        if prim == 18 and argc == 0:
            return self.heap.t_obj
        return original(self, prim, argc, stack, pc, native_base, frame_slots)
    try:
        H.DiskVM._callprim = unconditional
        mutant = world.vm(H.build_disk(H.FIXTURE_TEXT), 'owner-token')
        assert mutant.evaluate('(load "init.l65")') == 't'
        assert bytes(mutant.output_chars) == b'loading place...\nloading string-extra...\n'
        assert mutant.output_chars, 'unconditional echo must fail the silent-INIT oracle'
    finally:
        H.DiskVM._callprim = original
    import c2_link75_real_require_resolver_host as R
    def probe(cls):
        value = cls.__new__(cls)
        H.B.P0VM.__init__(value, heap=world.heap.clone(), directory=world.directory,
                         abi_profile=world.abi, abi_ledger=world.ledger)
        return value
    focused = probe(R.ResolverVM)
    for active in (False, True):
        focused.disk_source_active = active
        assert focused._callprim(18, 0, []) == (H.B.NIL if active else focused.heap.t_obj)
    body = inspect.getsource(R.ResolverVM._callprim)
    old = 'if prim_id not in (18, 67) or (prim_id == 18 and argc == 0):'
    assert body.count(old) == 1
    namespace = dict(R.__dict__)
    exec('class OldArity(ResolverVM):\n' + body.replace(old, 'if prim_id not in (18, 67):'), namespace)
    try:
        probe(namespace['OldArity'])._callprim(18, 0, [])
    except H.B.VMError as exc:
        assert 'expects name or track and sector' in str(exc)
    else:
        raise AssertionError('old specialized arity model survived')
    print('PASS: INIT silent, interactive echo retained, recovery to interactivity; '
          '256 owner states and four falling controls. Native boot/error pixels are separate witnesses.')


if __name__ == '__main__':
    main()
