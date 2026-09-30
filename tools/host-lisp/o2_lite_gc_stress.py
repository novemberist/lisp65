#!/usr/bin/env python3
"""Reviewer-only O2-lite target GC stress; selftest is strictly offline.

Use the accepted cycle-probe adapter, never rebuild the product. Force via the
existing alloc empty-freelist path after its checked LDX instruction. Collect
at EVERY allocation in each measured transition (slow by design). Peak means
maximum post-collection live population across this forced allocation sweep,
not a natural-GC timing claim. Preparation typing uses counted singleton HWA.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
ROOT = Path(__file__).resolve().parents[2]
ADAPTER = 'build/dwx/xemu-buffered-repair-three-patch-r2/dwx-xemu-cycle-probe-adapter.json'
ADAPTER_SHA = '7476df252c59c0012772694dcb32259beaee4125452b971ab92176c9f68f06c0'
FINAL = 'build/o2-lite-final-r1'
D81_SHA = 'b1921228ba1166f283793ae21f51891e6cb48729a8f5d1b5c0d09cdc6e902aef'
ELF_SHA = 'a82d603a03f52a14e6b55bd4d8e35ad5b848b2a540f99f4a529ccddb15c70084'


def require(ok, why):
    if not ok: raise ValueError(why)


def bind(path):
    path=Path(path);raw=path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def checked(row):
    p=ROOT/row['path'];actual=bind(p)
    require(actual['sha256']==row['sha256'] and actual['bytes']==row.get('bytes',actual['bytes']), 'binding drift: '+row['path'])
    return p


def line250(n=0):
    prefix='(string-length "';suffix='")'
    return prefix+chr(97+n)* (250-len(prefix)-len(suffix))+suffix


def scenarios():
    history=[line250(i) for i in range(10)]
    pending=['"'+'a'*18]+['a'*19]*31
    # A 640-byte form exercises scan, >259-byte buffer join and reader wrapper.
    joined=['(string-length "'+'a'*184,'b'*200,'c'*236+'")']
    assert len('\n'.join(joined))==640
    cases = {
        'return250':dict(setup=[],active=line250()[:-1],steps=[('active250',ord(')'),line250().upper()),
            ('return-echo-scan-reader',13,str(250-len('(string-length "")')))]),
        'pending32':dict(setup=pending,active='z'*249,steps=[('pending640-active250',ord('z'),'Z'*70),
            ('input-limit',13,'*** INPUT LIMIT')]),
        'history10':dict(setup=history,active='',steps=[('history-up',145,line250(9).upper()),
            ('history-down',17,'L65>'),('history-up-again',145,line250(9).upper()),
            ('history-return',13,str(250-len('(string-length "")')))]),
        'join640':dict(setup=joined[:-1],active=joined[-1],steps=[('return-echo-scan-source-join-reader',13,'622')]),
        'reopen':dict(setup=['(string-length "abc','def'],active='',steps=[('reopen',20,'DEF'),
            ('reopen-retype-return',13,'@empty'),('close-quote',34,'"'),('close-form',41,'")'),
            ('reader-wrapper',13,'8')]),
    }
    # Retain ten full entries while removing the entire original prefix chain.
    # Every Delete/refill key is forced, including the final Return echo.
    for name,setup,opening in (
        ('reopen-home-delete-refill250', ['"'+'a'*249], [('reopen250',20,'"'+'A'*249)]),
        ('history-home-delete-refill250', [], [('recall250',145,line250(9).upper())]),
    ):
        prefix='"'+'A'*249 if setup else line250(9).upper()
        steps=opening+[('home',1,prefix)]
        steps += [('delete-'+str(i),4,prefix[i:] or ('@empty' if setup else 'L65>')) for i in range(1,251)]
        replacement=line250()
        steps += [('refill-'+str(i),ord(c),replacement[:i].upper()) for i,c in enumerate(replacement,1)]
        steps += [('return-refilled250',13,'232')]
        cases[name]=dict(setup=setup,active='',steps=steps)
    for name,case in cases.items():
        case['history'] = history if name != 'history10' else []
    return cases


def live_snapshot(m,t, *, after_gc=True):
    def raw(name):
        s=t.symbol(name);return m.memory_range(s.value,s.bytes)
    def number(name):return int.from_bytes(raw(name),'little')
    marks=raw('marks'); require(len(marks)==134,'heap bitmap geometry drift')
    frozen=number('gc_frozen')
    # Frozen EXT cells are permanent and deliberately skipped by marking.
    # Count their union with marks, never double count marked hot cells.
    live={i for i in range(1,1072) if marks[i//8] & (1<<(i%8))}
    live.update(range(48,frozen+1))
    row=dict(live_cells=len(live),arena_bytes=number('str_top'),arena_base=number('str_cur_off'),
             frozen_cells=frozen,root_slots=number('gc_rootsp'),gc_runs=number('gc_runs'),
             freelist=number('freelist'),mem_oom=number('mem_oom'),marks=marks.hex())
    if after_gc: validate_snapshot(row)
    return row


def validate_snapshot(row):
    require(0<=row['live_cells']<1071 and 0<=row['arena_bytes']<=9344 and
            0<=row['root_slots']<=128 and row['freelist']!=0 and row['mem_oom']==0,
            'heap/arena/root exhaustion or invalid measurement')


def world(role):
    if role=='lite':
        from o2_lite_final import Driver
        from o2_lite_seal import Seal
        # Consume the same source selection recorded by Final, then verify seal.
        invocation=json.loads((ROOT/FINAL/'final-invocation.json').read_text())
        d=Driver('build/o2-lite-product-r6',invocation['sealed_run'],invocation['replay']['path'],
                 invocation['replay']['sha256'],FINAL)
        Seal(d).check()
        identity=json.loads((ROOT/FINAL/'final-identity.json').read_text())
        rows={r['role']:r['final'] for r in identity['artifacts']}
        require(rows['D81']['sha256']==D81_SHA and rows['ELF']['sha256']==ELF_SHA,'wrong Final')
        return checked(rows['D81']),checked(rows['ELF'])
    import comfort_default_rows as D
    medium,sha,elf=D.WORLD['strings']
    require(bind(medium)['sha256']==sha and bind(elf)['sha256']==D.ELF_SHA[elf],'STRINGS world drift')
    return medium,elf


def screen_matches(screen,want):
    import comfort_default_rows as D
    decoded=D.L.lines(screen)
    lines=[x.replace('{$A0}',' ').rstrip() for x in decoded]
    active=lines[-1].strip()
    if want=='@empty':return active==''
    nonblank=[x.strip() for x in lines if x.strip()]
    if want.isdigit():return len(nonblank)>=2 and nonblank[-2:]==[want,'L65>']
    if want=='L65>':return active=='L65>'
    flat=''.join(lines).upper()
    if want.startswith('*** '):return want in flat and active=='L65>'
    return flat.endswith(want.upper())


def run_case(role,name,out):
    import comfort_default_rows as D
    import block_26_vm_hardening_dwx_prefilter as G
    from elf_truth import ElfTruth
    from types import SimpleNamespace
    medium,elf=world(role)
    require(bind(ROOT/ADAPTER)['sha256']==ADAPTER_SHA,'accepted adapter receipt drift')
    adapter=json.loads((ROOT/ADAPTER).read_text());binary=checked(adapter['binary'])
    t=ElfTruth.read(elf,llvm_readobj=G.CARD.READOBJ,include_section_data=True)
    alloc=t.symbol('alloc');take=t.symbol('c2_kernal_input_take');free=t.symbol('freelist')
    def opcode(s):return t.section_bytes(s.section)[s.value-t.section(s.section).address]
    require(opcode(alloc)==0xa6 and opcode(take)==0xaa and free.bytes==2,'forcing seam changed')
    bounds=G.gc_bounds(elf)
    class Startup(G.CYCLES.ProbeMonitor):
        def wait_screen(self,required,timeout=20):return super().wait_screen(['65>'],timeout=180)
    G.CYCLES.ProbeMonitor=Startup
    args=SimpleNamespace(xemu=binary,rom=G.ROM,sd_image=G.SD_IMAGE,timeout=86400)
    out.mkdir(exist_ok=False)
    run=G.CYCLES.start_run(name,medium,out,args)
    m=G.PersistentProbeMonitor(run['monitor_path']);run['monitor']=m
    rows=[];events=[];case=scenarios()[name]
    result=dict(status='HALT',role=role,scenario=name,medium=bind(medium),ELF=bind(elf),
                adapter=bind(ROOT/ADAPTER),binary=bind(binary),driver=bind(Path(__file__)),
                scenario_contract=case,collections=rows,events=events)
    taken=t.symbol('C2K_INPUT_EVENTS_TAKEN').value
    def counter():return m.memory_range(taken,1)[0]
    def ready():
        m.command('t1');m.command(f'b {take.value:04x}');m.command('t0')
        G.wait_register(m,lambda r:G.gc_registers(r)['pc']==take.value+1,'input boundary',timeout=240)
    def frame_has(want):return screen_matches(m.screen(),want)
    try:
        require(D.L.active(m.screen())=='L65>','Comfort boot required')
        # Counted delivery plus a witnessed next-input call proves completed
        # handling of setup Return; no HWA timeout/paste completion inference.
        for line in case['history']+case['setup']:
            D.send_counted(m,[line,13],taken,timeout=600);ready()
            if line in case['history'] or name=='history10':
                require(frame_has('232'),'250-byte history setup did not evaluate')
            else:
                require(D.L.active(m.screen())=='','pending setup did not reach continuation')
            m.command('b ffff');m.command('t0')
        if case['active']:
            D.send_counted(m,[case['active']],taken,timeout=600)
        ready()
        for label,key,want in case['steps']:
            before_count=counter();start_gen=int.from_bytes(m.memory16(bounds['gc_runs'])[:2],'little')
            first=len(rows);allocations=0
            m.command(f'b {alloc.value:04x}');m.queue_one(key);m.command('t0')
            deadline=time.monotonic()+7200
            quiet=None
            while time.monotonic()<deadline:
                reg=G.register_line(m);pc=G.gc_registers(reg)['pc']
                if pc==alloc.value+2:
                    quiet=None;allocations+=1
                    before=live_snapshot(m,t,after_gc=False)
                    cycles=m.cycle_count()
                    m.command(f's {free.value:08x} 00 00')
                    require(m.memory16(free.value)[:2]==bytes(2) and m.cycle_count()==cycles,'forcing not stopped')
                    m.command(f"b {bounds['entry']:04x}");m.command('t0')
                    entry=G.wait_register(m,lambda r:G.gc_registers(r)['pc']==bounds['entry_after_first_opcode'],'forced GC entry')
                    witness=G.read_gc_return_witness(m,entry);c0=m.cycle_count()
                    m.command(f"b {bounds['exit_rts']:04x}");m.command('t0')
                    exitreg=G.wait_register(m,lambda r:G.gc_return_reached(r,witness),'forced GC return')
                    after=live_snapshot(m,t)
                    require(after['gc_runs']==(before['gc_runs']+1)&65535,'GC generation gap')
                    require(m.cycle_count()>c0,'GC made no cycle progress')
                    rows.append(dict(phase=label,allocation=allocations,before=before,after=after,
                                     entry=entry,exit=exitreg,return_witness=witness,cycles=m.cycle_count()-c0))
                    (out/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
                    m.command(f'b {alloc.value:04x}');m.command('t0');continue
                require((counter()-before_count)&255 in (0,1),'extra consumed key')
                if counter()==(before_count+1)&255 and frame_has(want):
                    quiet=quiet or time.monotonic()
                    if time.monotonic()-quiet>3:break
                else:quiet=None
                time.sleep(.02)
            else:raise ValueError('transition timed out: '+label)
            ready()
            require(frame_has(want),'transition screen lost: '+label)
            end_gen=int.from_bytes(m.memory16(bounds['gc_runs'])[:2],'little')
            require((end_gen-start_gen)&65535==len(rows)-first,'unobserved collection')
            require(allocations>0 or label in ('history-down','home') or label.startswith('delete-'),
                    'transition did not allocate: '+label)
            events.append(dict(phase=label,key=key,consumed=1,allocations=allocations,collections=len(rows)-first,
                               screen=m.screen(),ready=G.register_line(m)))
        require(rows,'no collections')
        # Complete each scenario with a new evaluated expression after the
        # measured transition; a merely drained input counter is insufficient.
        m.command('b ffff');m.command('t0')
        D.send_counted(m,['(+ 20 22)',13],taken,timeout=600);ready()
        require(frame_has('42'), 'post-stress allocation/evaluation did not recover')
        result['recovery_screen'] = m.screen()
        result.update(status='PASS',peak_live_cells=max(r['after']['live_cells'] for r in rows),
            peak_arena_bytes=max(r['after']['arena_bytes'] for r in rows),
            peak_root_slots=max(r['before']['root_slots'] for r in rows),
            allocation_progress=sum(e['allocations'] for e in events),no_heap_exhaustion=True,
            claim='Forced allocation sweep; emulator only, no natural-pause/device claim')
        m.command('b ffff');m.command('t0')
        result['outputs']=G.CYCLES.finish_run(run,m.screen());m.close()
    except BaseException as e:
        result['error']=repr(e);m.close();G.CYCLES.abort_run(run);raise
    finally:
        (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def compare(a,b):
    require(a['status']==b['status']=='PASS' and a['role']=='lite' and b['role']=='strings' and
            a['scenario']==b['scenario']=='return250','comparison populations differ')
    require(a['medium']['sha256']==D81_SHA and a['ELF']['sha256']==ELF_SHA, 'comparison is not r6-identical Final')
    require(b['medium']['sha256']=='9978daa146b89cf71ad1d3f290d80cf74b197911e7854859f9e4aa9bb2fce441' and
            b['ELF']['sha256']=='d514e4980c636cab0c6ae1ee9bea77afdd3a4fdf58f01995aba5ff822e89ed05', 'comparison is not STRINGS Final')
    require(a['scenario_contract']==b['scenario_contract']==scenarios()['return250'], 'comparison stimuli differ')
    require(a['no_heap_exhaustion'] is True and b['no_heap_exhaustion'] is True,'comparison lacks progress proof')
    def peak(row):
        values=[r['after'] for r in row['collections'] if r['phase']=='return-echo-scan-reader']
        require(values,'Return sweep absent')
        return {k:max(v[k] for v in values) for k in ('live_cells','arena_bytes')}
    x,y=peak(a),peak(b)
    require(all(x[k]<=y[k] for k in x),'250-character Return peak regression')
    return dict(status='PASS',lite=x,v251_STRINGS=y,delta={k:x[k]-y[k] for k in x})


def selftest():
    import subprocess
    from unittest.mock import patch
    with patch.object(subprocess,'run',side_effect=AssertionError('offline')),patch.object(subprocess,'check_output',side_effect=AssertionError('offline')):
        import block_26_vm_hardening_dwx_prefilter as G
        import comfort_default_rows as D
        G.gc_exit_selftest();G.gc_population_selftest()
        require(bind(ROOT/ADAPTER)['sha256']==ADAPTER_SHA,'adapter receipt changed')
        checked(json.loads((ROOT/ADAPTER).read_text())['binary'])
        class Counted:
            value=255
            keys=[]
            def memory_range(self,at,n):return bytes([self.value])
            def queue_one(self,key):self.keys.append(key);self.value=(self.value+1)&255
        transport=Counted()
        assert D.send_counted(transport,['a',13],0)['consumed']==2
        assert transport.keys==[97,13]
        assert screen_matches('232\nL65> {$A0}', '232')
        assert not screen_matches('232\nL65> STILL TYPING', '232')
        assert not screen_matches('L65> OLD\nNEW', 'L65>')
        assert not screen_matches('DEF\nL65>', 'DEF')
        text=line250().upper()
        assert screen_matches('\n'.join(text[i:i+80] for i in range(0,len(text),80)),text)
        s=scenarios();require(len(line250())==250,'250 fixture')
        for name in ('reopen-home-delete-refill250','history-home-delete-refill250'):
            require(len(s[name]['history'])==10 and
                    sum(label.startswith('delete-') for label,_,_ in s[name]['steps'])==250 and
                    sum(label.startswith('refill-') for label,_,_ in s[name]['steps'])==250,
                    'prefix deletion/refill population')
        require(len(s['history10']['setup'])==10 and len(set(s['history10']['setup']))==10,'history fixture')
        require(len(s['pending32']['setup'])==32 and sum(len(x)+1 for x in s['pending32']['setup'])==640,'pending fixture')
        good=dict(live_cells=1000,arena_bytes=9000,root_slots=128,freelist=2,mem_oom=0)
        validate_snapshot(good)
        rejected=[]
        for key,value in [('live_cells',1071),('arena_bytes',9345),('root_slots',129),('freelist',0),('mem_oom',1)]:
            try:validate_snapshot({**good,key:value})
            except ValueError:rejected.append(key)
            else:raise AssertionError(key)
        def receipt(role,n):
            return dict(status='PASS',role=role,scenario='return250',scenario_contract=scenarios()['return250'],no_heap_exhaustion=True,
                medium=dict(sha256=D81_SHA if role=='lite' else '9978daa146b89cf71ad1d3f290d80cf74b197911e7854859f9e4aa9bb2fce441'),
                ELF=dict(sha256=ELF_SHA if role=='lite' else 'd514e4980c636cab0c6ae1ee9bea77afdd3a4fdf58f01995aba5ff822e89ed05'),
                collections=[dict(phase='return-echo-scan-reader',after=dict(live_cells=n,arena_bytes=100))])
        compare(receipt('lite',99),receipt('strings',100))
        try:compare(receipt('lite',101),receipt('strings',100))
        except ValueError:rejected.append('Return regression')
        else:raise AssertionError('peak regression accepted')
        return dict(status='PASS',scenarios=list(s),protocol_tests=['GC return PC and SP', 'GC generation population', 'counted singleton wraparound', 'fresh result/prompt and wrapped active-line oracles'],negative_controls=rejected,emulator_runs=0,product_builds=0)


if __name__=='__main__':
    require(__debug__,'assertions required')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--selftest',action='store_true');p.add_argument('--role',choices=['lite','strings'])
    p.add_argument('--out');p.add_argument('--scenario',choices=list(scenarios()))
    p.add_argument('--compare',nargs=2,metavar=('LITE_RECEIPT','STRINGS_RECEIPT'))
    a=p.parse_args()
    if a.selftest: result=selftest()
    elif a.compare: result=compare(*(json.loads((ROOT/f).read_text()) for f in a.compare))
    else:
        require(a.role and a.out and a.scenario,'role, out and scenario required')
        require(a.role!='strings' or a.scenario=='return250','STRINGS only supports inherited Return comparison')
        target=(ROOT/a.out).resolve();require(target.is_relative_to(ROOT/'build'),'output must be under build')
        result=run_case(a.role,a.scenario,target)
    print(json.dumps(result,indent=2))
