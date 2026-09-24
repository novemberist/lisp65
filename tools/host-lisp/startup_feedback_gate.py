#!/usr/bin/env python3
"""Pre-seed startup pixels: live Lisp and the compiled native screen driver.

Disk transport is the existing Host fixture, not a native/device load witness.
The product Seed still owes its consumed-source, boot, error and cost lanes.
"""
import ctypes
from pathlib import Path
import subprocess
import tempfile

import init_require_scratch_gate as H
import v11_repl_banner_visual as V

ROOT = Path(__file__).resolve().parents[2]
B, C = H.B, H.C


def main():
    repl = (ROOT / 'src/repl.c').read_text()
    start = repl.index('#ifdef LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY\n    if (!aborted)')
    end = repl.index('        (void)vm_run_dir(', start)
    indicator = repl[start:end] + '\n    }\n#endif\n'
    assert indicator.count('emit_str(') == 1
    assert indicator.count('"Initializing...\\n"') == 1
    old_language = indicator.replace('"Initializing...\\n"', '"Initialisiere...\\n"')
    banner = (ROOT / 'lib/repl-banner.lisp').read_text()
    assert banner.count('(screen-clear)') == 1
    with tempfile.TemporaryDirectory(prefix='lisp65-startup-') as tmp:
        tmp = Path(tmp)
        harness = tmp / 'screen.c'
        harness.write_text('#include "screen.h"\n'
                           'static void emit_str(const char *p){while(*p)scr_putc(*p++);}\n'
                           'void indicator(int aborted){\n' + indicator + '}\n'
                           'void old_language_indicator(int aborted){\n' + old_language + '}\n')
        so = tmp / 'screen.so'
        subprocess.run(['cc', '-Wall', '-Werror', '-shared', '-fPIC',
                        '-DLISP65_C2_PRODUCT_CUT', '-DLISP65_SCREEN_DRIVER',
                        '-DLISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY=1',
                        '-I' + str(ROOT / 'src'), str(harness),
                        str(ROOT / 'src/screen.c'), '-o', str(so)], check=True)
        screen = ctypes.CDLL(str(so))
        screen.scr_host_buf.restype = ctypes.POINTER(ctypes.c_uint8)
        screen.scr_put_at.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_char, ctypes.c_int16]
        def pixels():
            return bytes(screen.scr_host_buf()[:2000])
        def code(c):
            return c - 96 if 97 <= c <= 122 else c
        message = bytes(map(code, b'Initializing...'))
        pending = message + b' ' * (2000 - len(message))
        screen.scr_init()
        screen.old_language_indicator(0)
        assert pixels() != pending, 'old German wording must fail the exact English screen oracle'
        screen.scr_init()
        screen.indicator(0)
        assert pixels() == pending and screen.scr_row() == 1
        screen.scr_clear()
        screen.indicator(1)
        assert pixels() == b' ' * 2000, 'recovery must not restart feedback'

        world = H.World()
        def compiled(text):
            heap, directory = world.heap.clone(), dict(world.directory)
            for form in C.parse_all(text):
                fn, bc, helpers = C.compile_top_form_with_helpers(
                    form, heap, strict_arity=True, abi_profile=world.abi,
                    abi_ledger=world.ledger)
                assert not helpers
                directory[heap.intern(fn)] = bc
            return heap, directory

        class VM(H.DiskVM):
            fail_source = False

            def load_source_stream(self, fetch):
                if self.fail_source:
                    raise B.VMError('OutOfMemory', 'startup error fixture')
                return super().load_source_stream(fetch)

            def _callprim(self, prim_id, argc, stack, pc=None, native_base=0, frame_slots=0):
                args = list(stack[-argc:]) if argc else []
                if prim_id == 10:
                    screen.scr_clear()
                elif prim_id == 11:
                    x, y, ch, attr = map(B.fixval, args)
                    screen.scr_put_at(x, y, bytes([ch]), attr)
                elif prim_id == 45:
                    screen.scr_putc(B.fixval(args[0]))
                elif prim_id == 62:
                    hi, lo, value = map(B.fixval, args)
                    address = (hi << 8) | lo
                    if 2048 <= address < 4048:
                        screen.scr_host_buf()[address - 2048] = value
                return super()._callprim(prim_id, argc, stack, pc, native_base, frame_slots)

        expected = bytearray(b' ' * 2000)
        for x, y, ch, attr in V.expected_screen_writes():
            expected[y * 80 + x] = code(ch) | (128 if attr & 128 else 0)
        for address, value in V.expected_pokes():
            expected[address - 2048] = value

        def boot(text, init, show=True, fail_source=False):
            heap, directory = compiled(text)
            vm = VM(heap=heap, directory=directory, abi_profile=world.abi,
                    abi_ledger=world.ledger, max_steps=50_000_000)
            vm.setup(H.build_disk(H.FIXTURE_TEXT), 'owner-token', world.abi, world.ledger)
            vm.fail_source = fail_source
            for name in ('*require-fast*', '*require-index-lock*'):
                heap.set_symbol_value(heap.intern(name), B.NIL)
            if not init:
                # Exercise the real host directory lookup with a missing name.
                fn, bc, helpers = C.compile_top_form_with_helpers(
                    C.parse_one(text[text.index('(defun %repl-banner'):].replace('init.l65', 'none.l65')),
                    heap, strict_arity=True, abi_profile=world.abi, abi_ledger=world.ledger)
                assert not helpers
                directory[heap.intern(fn)] = bc
            screen.scr_init()
            if show:
                screen.indicator(0)
            assert pixels() == pending, 'missing startup feedback'
            if fail_source:
                try:
                    vm.evaluate('(%repl-banner)')
                except B.VMError:
                    # Lisp must not reach the clear/banner after an abort.
                    # Native error formatting/recovery is a separate Seed row.
                    assert pixels() == pending
                    screen.indicator(1)
                    assert pixels() == pending
                    return pixels()
                raise AssertionError('source-error fixture did not abort')
            vm.evaluate('(%repl-banner)')
            assert pixels() == expected, 'banner retains startup or INIT cells'
            assert screen.scr_row() == 9
            assert not vm.output_chars or set(vm.output_chars) == {10}
            return pixels()

        assert boot(banner, True) == boot(banner, False)
        boot(banner, True, fail_source=True)
        for label, text, show in (
                ('missing feedback', banner, False),
                ('missing clear', banner.replace('(screen-clear)', 'nil'), True),
                ('late clear', banner.replace('(screen-clear)', 'nil').replace('(%banner-subtitle)\n', '(%banner-subtitle)\n  (screen-clear)\n'), True)):
            try:
                boot(text, True, show)
            except AssertionError:
                pass
            else:
                raise AssertionError('surviving mutation: ' + label)
    print('PASS: startup exact pixels; INIT/missing INIT identical banner; cursor row 9; '
          'no restart on recovery; old German wording, missing feedback, missing clear and late clear rejected. '
          'Host disk fixture, compiled native screen; native boot/error lanes still required.')


if __name__ == '__main__':
    main()
