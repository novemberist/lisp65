"""Read-only PC snapshots around the unchanged matched-GC measurement."""
import inspect
import json
import os
from pathlib import Path
import runpy
import sys
from unittest.mock import patch
import block_26_vm_hardening_dwx_prefilter as G

ROOT=Path(__file__).resolve().parents[2]
role=sys.argv[1]
assert role in ('baseline','candidate')
pc=ROOT/f'build/retained-callable-repair-gc-pc-{role}-r1.txt'
assert not pc.exists()
os.environ['LISP65_DWX_PC_OUTPUT']=str(pc)


def capture(monitor,index,phase):
    cycles=monitor.cycle_count()
    assert 'DWX PC save: 0' in monitor.command('~pcsave')
    assert monitor.cycle_count()==cycles
    target=G.BUILD/f'pc-{index}-{phase}.txt'
    assert not target.exists()
    target.write_bytes(pc.read_bytes())


original=inspect.getsource


def source(fn):
    raw=original(fn)
    if fn is G.measure_gc_population:
        instrument=json.loads((ROOT/'build/retained-callable-repair-r1/ready-instrument.json').read_text())
        world=next(w for w in instrument['worlds'] if w['role']==role)
        binary=ROOT/world['binary']['path']
        assert G.sha256(binary)==world['binary']['sha256']
        G.XEMU=binary
        for old,new in [
            ('before=monitor.cycle_count();gen_before=generation()',
             "before=monitor.cycle_count();gen_before=generation();carrier_pc_capture(monitor,len(rows),'before')"),
            ('after=monitor.cycle_count();gen_after=generation()',
             "after=monitor.cycle_count();gen_after=generation();carrier_pc_capture(monitor,len(rows),'after')"),
        ]:
            assert raw.count(old)==1
            raw=raw.replace(old,new)
    return raw


G.carrier_pc_capture=capture
sys.argv=[__file__,'gc',role,'--trial','1']
with patch.object(inspect,'getsource',side_effect=source):
    runpy.run_path(str(ROOT/'tools/host-lisp/retained_callable_repair_qualification.py'),run_name='__main__')
