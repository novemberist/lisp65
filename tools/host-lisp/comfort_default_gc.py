#!/usr/bin/env python3
"""Comfort-default matched GC, checked derivation of comfort_library_gc.py.

Roles: baseline = 2.4.0 native; candidate = product after empty-line exit;
comfort = shipped Comfort library on 2.4.0 after require/repl;
product = product at boot Comfort. The inherited workload/forcing/snapshots
are unchanged. --boot OUT records the named six-package startup cost for
base, no-comfort and product (read-only stopped memory).
"""
import argparse
import json
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/host-lisp'))
import comfort_default_rows as D
from comfort_default_lanes import derive, replace
from elf_truth import ElfTruth


def boot(out):
    out=ROOT/'build'/out;out.mkdir(exist_ok=False)
    R=D.R
    original=R.ProbeMonitor
    class Monitor(original):
        def wait_screen(self,required,timeout=20):
            return super().wait_screen(['65>'],timeout=180)
    R.ProbeMonitor=Monitor
    args=argparse.Namespace(xemu=D.L.XEMU,rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')),timeout=600)
    assert R.bind(args.xemu)['sha256']==D.L.EXPECT['xemu']
    worlds={}
    for role in ('base','no-comfort','product'):
        medium,sha,elf=D.WORLD[role]
        assert R.bind(medium)['sha256']==sha and R.bind(elf)['sha256']==D.ELF_SHA[elf]
        t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
        run=R.start_run(role,medium,out,args);m=run['monitor']
        try:
            time.sleep(3);m.command('t1')
            v={}
            for name in ('gc_runs','freelist','nsym','npool','gc_rootsp'):
                s=t.symbol(name);v[name]=int.from_bytes(m.memory_range(s.value,s.bytes),'little')
            header=m.memory_range(0x50000,48)
            assert header[:3]==b'C2D'
            (out/f'{role}-c2d-header.bin').write_bytes(header)
            v.update({name:int.from_bytes(header[at:at+2],'little') for name,at in [('images',12),('entries',16),('roots',24)]})
            v['active']=D.L.active(m.screen())
            assert v['active']==D.BOOT_PROMPT[role]
            v.update(medium=R.bind(medium),ELF=R.bind(elf),outputs=R.finish_run(run,m.screen()))
            worlds[role]=v
            (out/'receipt.json').write_text(json.dumps(dict(worlds=worlds,driver=R.bind(Path(__file__)),xemu=R.bind(args.xemu)),indent=2)+'\n')
            print(role,{k:v[k] for k in ('nsym','npool','images','entries','roots','freelist','gc_rootsp','gc_runs')},flush=True)
        except BaseException:
            R.abort_run(run);raise


def main():
    if len(sys.argv)>1 and sys.argv[1]=='--boot':
        assert len(sys.argv)==3;boot(sys.argv[2]);return
    # Resolve both existing text-derivation layers before rebinding the worlds.
    raw=derive(ROOT/'tools/host-lisp/comfort_library_gc.py')
    scope=dict(__file__=__file__)
    exec(raw.split('exec(compile(raw,')[0],scope)
    raw=scope['raw']
    raw=replace(raw,{
      "choices=['baseline','candidate','comfort']":"choices=['baseline','candidate','comfort','product']",
      "f'build/comfort-library-gc-equal-{a.role}-{a.trial}'":"f'build/comfort-default-gc-equal-{a.role}-{a.trial}'",
      # The accepted cycle-probe adapter binary stays the instrument (reproduction).
      "binary=json.loads((ROOT/'build/dwx/xemu-buffered-repair-three-patch-r2/dwx-xemu-cycle-probe-adapter.json').read_text())['binary']":"import comfort_default_rows as D\nbinary=json.loads((ROOT/'build/dwx/xemu-buffered-repair-three-patch-r2/dwx-xemu-cycle-probe-adapter.json').read_text())['binary']",
      "def wait_screen(self,required,timeout=20):return super().wait_screen(required,timeout=max(timeout,120))":"def wait_screen(self,required,timeout=20):return super().wait_screen(['65>' if x=='LISP65>' else x for x in required],timeout=max(timeout,180))",
      "pack=json.loads((ROOT/'build'/parent/'packed-receipt.json').read_text());elf=checked(pack['elf']);medium=checked(pack['medium'])":"pack=json.loads((ROOT/'build'/parent/'packed-receipt.json').read_text()) if a.role in ('baseline','comfort') else dict(elf=D.R.bind(D.ELF),medium=D.R.bind(D.WORLD['product'][0]))\nelf=checked(pack['elf']);medium=checked(pack['medium'])",
      "    import time as _t":"    import time as _t\n    if a.role=='product':\n        assert D.L.active(m.screen())=='L65>';return",
      "card='comfort-library',binding='180cb993',":"card='comfort-default',",
    })
    raw=raw.replace("if a.role=='comfort':", "if a.role in ('comfort','product'):")
    # Product-native needs the deliberate exit before the inherited read-line
    # controller; no key from this prelude belongs to the measured population.
    at="source=inspect.getsource(G.measure_gc_population)"
    # (repl) clears the input counters on entry: settle before the exit key.
    # A lone pasted newline is lost by the emulator's HWA paste (probe
    # build/comfort-default-r2/gates/exit-probe3-*); a real Return key is used.
    exit_controller = '__import__("time").sleep(3);monitor.command("~typeone 0d");monitor.wait_screen(["LISP65>"]);monitor.type_text(CONTROLLER)'
    raw=raw.replace(at, at + "\nif a.role=='candidate':\n    source=source.replace('monitor.type_text(CONTROLLER)', " + repr(exit_controller) + ")")

    exec(compile(raw,__file__,'exec'),dict(__name__='__main__',__file__=__file__))

if __name__=='__main__':main()
