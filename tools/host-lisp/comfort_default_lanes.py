#!/usr/bin/env python3
"""Comfort-default lanes: checked text derivation of comfort_library_lanes.

The measurement loop is native_cycle_stationary unchanged. Readiness permits
cumulative prelude poll counts; all raw snapshots remain unmodified. Input
counters must still be zero, and the selected prompt must be at its first poll.
No guest writes, builds or links. --prompt native|comfort --attempt NAME.
"""
import argparse
import inspect
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/host-lisp'))
import native_cycle_stationary as N
import comfort_default_rows as D
import nested_error_recovery_lanes as CONFIG
from elf_truth import ElfTruth


def derive(path):
    scope = dict(__file__=str(path))
    exec(path.read_text().split("exec(compile(raw,")[0], scope)
    return scope['raw']


def replace(raw, changes):
    for old, new in changes.items():
        assert raw.count(old) == 1, old
        raw = raw.replace(old, new)
    return raw


def main():
    p=argparse.ArgumentParser();p.add_argument('--prompt',choices=['native','comfort'],required=True);p.add_argument('--attempt',required=True);p.add_argument('--native-candidate',choices=['v240-init','product'],default='v240-init');a=p.parse_args()
    original_mutations=N.selftest()+N.completion_selftest()+N.readiness_selftest()
    # Generalize only historical readiness counts after a typed prelude. The
    # algorithm, costs, samples, counters and all completion predicates stay.
    patches={
      'validate_ready_state': {"assert state['entry_calls']==1 and state['key_event_calls']==1":"assert state['entry_calls']>=1 and state['key_event_calls']>=1"},
      'verify_ready_trace': {
        "[1,0xaa,0]":"[ready['entry_calls'],0xaa,0]",
        "assert entry==ready['entry_calls']==1 and key==ready['key_event_calls']==1":"assert entry==ready['entry_calls'] and key==ready['key_event_calls']"},
      'completed_cycle_trace': {"assert entry_calls==1":"assert entry_calls==ready['entry_calls']"},
    }
    for name,changes in patches.items():
        raw=inspect.getsource(getattr(N,name))
        for old,new in changes.items():
            assert old in raw;raw=raw.replace(old,new)
        exec(compile(raw,str(Path(N.__file__)), 'exec'),N.__dict__)
    import dwx_retroactive_red_replay as R
    native_find=R.find_input_start
    def find(m,base):
        if a.prompt=='native': return native_find(m,base)
        screen=m.memory_range(base,80*25)
        pos=screen.rfind(bytes((12,54,53,62)))
        assert pos>=0
        target=base+pos+5
        assert m.memory16(target)[0] in (0,32,160)
        return target
    R.find_input_start=find
    out=ROOT/f'build/input-cost-natural-{a.attempt}'
    assert not out.exists()
    identity=json.loads((ROOT/'build/nested-error-recovery-instrument-r1/instrument.json').read_text())
    worlds=[]
    for role in ('anchor','candidate'):
        # Native prompt: the Seed ELF on the 2.4.0-INIT control (same loaded
        # packages as 2.4.0) isolates the resident change; the observer binary's
        # HWA input does not reach the Comfort reader, so no l65> prelude.
        if role=='candidate': medium,sha,elf=D.WORLD[a.native_candidate if a.prompt=='native' else 'product']
        elif a.prompt=='native': medium,sha,elf=D.WORLD['base']
        else: medium,sha,elf=D.L.MEDIUM,D.L.EXPECT['medium'],D.L.ELF
        assert N.bind(medium)['sha256']==sha
        assert N.bind(elf)['sha256']==D.ELF_SHA[elf]
        t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
        s=t.symbol('c2_kernal_input_take');sec=t.section(s.section)
        code=t.section_bytes(s.section)[s.value-sec.address:s.value-sec.address+s.bytes]
        w=dict(identity['worlds'][1],role=role,ELF=N.bind(elf),medium=N.bind(medium),entry=s.value,paused_pc=s.value+1,entry_code=code.hex(),cost_config=CONFIG.cost_config(elf))
        if role=='anchor':assert w['cost_config']==identity['worlds'][1]['cost_config']
        worlds.append(w)
    identity['worlds']=worlds
    inst=ROOT/'build/comfort-default-r2/gates'/f'{a.attempt}-instrument.json'
    assert not inst.exists();inst.write_text(json.dumps(identity,indent=2)+'\n')
    raw=derive(ROOT/'tools/host-lisp/comfort_library_lanes.py')
    # Preludes are typed before the entry breakpoint is armed: the Comfort
    # reader does not pass c2_kernal_input_take, so a breakpoint-driven
    # prelude would never fire at l65>. Each step waits for its prompt.
    readiness='''
        steps = ([('LISP65>','(require "repl-comfort")\\n','LISP65>'),('LISP65>','(repl)\\n','L65>')] if role=='anchor' and PROMPT=='comfort' else
                 [('L65>',None,'LISP65>')] if role=='candidate' and PROMPT=='native' and NATIVE_CANDIDATE=='product' else [])
        for wanted,text,after in steps:
            limit=time.monotonic()+240
            while D.L.active(self.screen())!=wanted:
                assert time.monotonic()<limit,'prelude prompt '+wanted;time.sleep(.2)
            time.sleep(3.0);before=self.screen()
            if text is None: self.command('~typeone 0d')  # real Return: a lone pasted newline is lost
            else: self.type_text(text)
            while not (self.screen()!=before and D.L.active(self.screen())==after):
                assert time.monotonic()<limit,'prelude result '+after;time.sleep(.2)
            time.sleep(1.0)
        expected='L65>' if PROMPT=='comfort' else 'LISP65>'
'''
    hook='''                active=D.L.active(screen)
                counters=list(self.memory16(COUNTER_ADDRESS)[:4])
                if active!=expected or counters!=[0]*4:
                    self.command('t0');continue
'''
    raw=replace(raw,{
      "mutations_rejected=N.selftest()+N.completion_selftest()+N.readiness_selftest(),":"mutations_rejected=ORIGINAL_MUTATIONS,",
      "instrument=ROOT/'build/nested-error-recovery-instrument-r1/instrument.json'":f"instrument=ROOT/{str(inst.relative_to(ROOT))!r}",
      "        self.command(f'b {WORLD[\"entry\"]:04x}')":readiness+"        self.command(f'b {WORLD[\"entry\"]:04x}')",
      "screen=self.screen();assert 'LISP65>' in R.ROWS.decoded_framebuffer(screen)":"screen=self.screen()\n"+hook,
      "assert entry_calls==key_calls==1":"assert entry_calls>=1 and key_calls>=1",
      "for role,path in [('anchor', 'build/nested-error-recovery-seed-medium-r1'), ('candidate', 'build/comfort-library-medium-r2')]:":"for WORLD in identity['worlds']:\n    role=WORLD['role']",
      "packed=json.loads((ROOT/path/'packed-receipt.json').read_text());medium=N.checked_binding(packed['medium']);elf=N.checked_binding(packed['elf'])":"packed=dict(medium=WORLD['medium'],elf=WORLD['ELF']);medium=N.checked_binding(packed['medium']);elf=N.checked_binding(packed['elf'])",
      "assert (packed['closure']['failures']==packed['coherence']['failures']==[]) if role=='anchor' else packed['status'].startswith('PASS: SIXTH PACKAGE ADDED')":"assert N.bind(medium)==WORLD['medium']",
      "WORLD=next(w for w in identity['worlds'] if w['role']=='candidate' and w['ELF']['sha256']==packed['elf']['sha256'])":"assert WORLD['ELF']==packed['elf']",
      "assert row['cycle_deltas']==previous['cycle_deltas'], 'observer cycle neutrality'":"if PROMPT=='native': assert row['cycle_deltas']==previous['cycle_deltas'], 'observer cycle neutrality'",
      "card='comfort-library',binding='180cb993',":"card='comfort-default',prompt=PROMPT,anchor_neutrality=('cycle-identical' if PROMPT=='native' else 'no prior accepted Comfort natural lane'),",
      "PASS: FRESH 2.4.0 ROWS REPRODUCE THE ACCEPTED 2.4.0 ROWS; COMFORT MEDIUM MEASURED":"MEASURED: COMFORT DEFAULT; ALL SAMPLES RETAINED",
    })
    sys.argv=[__file__,'--attempt',a.attempt]
    exec(compile(raw,__file__,'exec'),dict(__name__='__main__',__file__=__file__,PROMPT=a.prompt,NATIVE_CANDIDATE=a.native_candidate,D=D,ORIGINAL_MUTATIONS=original_mutations))

if __name__=='__main__':main()
