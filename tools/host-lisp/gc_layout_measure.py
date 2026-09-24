"""Same-world matched GC; relocate only the forced collection in emulator RAM."""
import inspect
import json
import os
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

import block_26_vm_hardening_dwx_prefilter as G
from gc_layout_control import ROOT, OUT, bind, write_once

mode = sys.argv[1]
assert mode in ('baseline', 'relocated') and len(sys.argv) == 2
target = ROOT / f'build/gc-layout-measure-{mode}-r1'
assert not target.exists(), 'measurement output already exists'
admission = json.loads((OUT/'preflight.json').read_text())
linked = json.loads((OUT/'linked.json').read_text())
assert linked['status'] == 'PASS: EXACT RELOCATED BODY'
for row in admission['inputs'] + [linked['ELF'], linked['body']]:
    assert bind(row['path'])['sha256'] == row['sha256']
payload = (OUT/'expected.bin').read_bytes()
binary = next(w['binary'] for w in json.loads(
    (ROOT/'build/boot-only-carrier-r1/ready-instrument.json').read_text())['worlds']
    if w['role'] == 'candidate')
assert bind(binary['path'])['sha256'] == binary['sha256']
pc = OUT / f'pc-{mode}.txt'
assert not pc.exists()
os.environ['LISP65_DWX_PC_OUTPUT'] = str(pc)
state = {}


def enter(m, phase, bounds):
    if phase != 'forced':
        return
    assert not state
    original = G.gc_registers(G.register_line(m))
    count = m.cycle_count()
    base = admission['relocated']
    # Both runs install the same bytes in the same unused interval, so the
    # only difference during collection is the selected instruction address.
    before = m.memory_range(base, len(payload))
    for off in range(0, len(payload), 16):
        m.command(f's {base+off:08x} ' + ' '.join(f'{b:02x}' for b in payload[off:off+16]))
    assert m.memory_range(base, len(payload)) == payload
    assert m.cycle_count() == count
    assert G.gc_registers(G.register_line(m)) == original
    state.update(original_bounds=dict(bounds), original_registers=original,
                 prior_bytes=before.hex(), address=base, bytes=len(payload), cycles=count)
    if mode == 'relocated':
        delta = base - admission['original']
        # CLC has already executed at the inherited measurement entry. Set-PC
        # does not execute a guest instruction; assert every other register.
        m.command(f'g {base+1:04x}')
        after = G.gc_registers(G.register_line(m))
        assert after == dict(original, pc=base+1)
        assert m.cycle_count() == count
        bounds['exit_rts'] += delta
    write_once(target/'relocation-entry.json', state)


def capture(m, index, phase):
    count = m.cycle_count()
    assert 'DWX PC save: 0' in m.command('~pcsave')
    assert m.cycle_count() == count
    write_once(target/f'pc-{index}-{phase}.txt', pc.read_bytes())


def restore(bounds, phase):
    if phase == 'forced':
        bounds.update(state['original_bounds'])


G.layout_enter = enter
G.layout_capture = capture
G.layout_restore = restore
original_source = inspect.getsource


def getsource(fn):
    raw = original_source(fn)
    if fn is G.measure_gc_population:
        G.XEMU = ROOT / binary['path']
        replacements = {
            'before=monitor.cycle_count();gen_before=generation()':
                "before=monitor.cycle_count();gen_before=generation();layout_enter(monitor,phase,bounds);layout_capture(monitor,len(rows),'before')",
            'after=monitor.cycle_count();gen_after=generation()':
                "after=monitor.cycle_count();gen_after=generation();layout_capture(monitor,len(rows),'after');layout_restore(bounds,phase)",
        }
        for old, new in replacements.items():
            assert raw.count(old) == 1
            raw = raw.replace(old, new)
    return raw


# Reuse the complete current matched-state/name-domain derivation. Only the
# output directory changes; both roles select the same carrier candidate.
original_read = Path.read_text


def read_text(self, *args, **kwargs):
    raw = original_read(self, *args, **kwargs)
    if self == ROOT/'build/index-crc-r1/gc-equal.py':
        old = "f'build/index-crc-gc-equal-{a.role}-{a.trial}'"
        assert raw.count(old) == 1
        raw = raw.replace(old, repr(str(target.relative_to(ROOT))))
    return raw


sys.argv = [__file__, 'gc', 'candidate', '--trial', '1']
with patch.object(inspect, 'getsource', getsource), patch.object(Path, 'read_text', read_text):
    runpy.run_path(str(ROOT/'tools/host-lisp/boot_only_carrier_qualification.py'), run_name='__main__')
write_once(target/'diagnostic.json', dict(mode=mode, product_medium_changed=False,
           diagnostic_link=bind(OUT/'linked.json'), observer=binary,
           wrapper=bind(Path(__file__)), phase='forced collection only'))
