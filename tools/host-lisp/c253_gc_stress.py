#!/usr/bin/env python3
"""Reviewer-only 2.5.3 target GC stress; selftest is strictly offline.

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
sys.path.append(str(ROOT / 'tools/host-lisp'))
import c253_config as CFG
import c253_final_pins as PINS
# Dated successor of o2_lite_gc_stress_r7c_20260930.py bound to the 2.5.3 Final.
# Identity pins come from c253_final_pins (c253_config.py is frozen by the Seed tool identity).
FINAL = CFG.FINAL
D81_SHA = PINS.ARTIFACT_SHA['D81']
ELF_SHA = PINS.ARTIFACT_SHA['ELF']
# [SET-AFTER-SEAL] both, in THIS file, after `c253_seal.py check` passed (editing any file under
# tools/host-lisp changes a replay input, so the seal check cannot be repeated afterwards; the
# committed seal is re-bound here by hash, as in 2.5.2).  None = fail closed.
# [SET-AFTER-SEAL] r8: None until the r8 seal check passed (fail closed).  r7 values (retained Final r7, not
# shipped): seal.json c1f5d8cf816485ab51635449d41c6448ffd0ff1a6756e20299516fd43f25d679, run
# build/card-253-check-source-final-r7c.
SEAL_SHA = 'bb4a509f99fb539f2e1055bf4d6c7b5ac0b40205d6e96be837fe2f1dcf37d469'  # sha256 of FINAL/seal.json
SOURCE_RUN = 'build/card-253-check-source-final-r8'  # the --source-run actually used for Final and seal
# The 2.5.2 Final (role 'v252') is the regression baseline for peak comparison.
V252_FINAL = CFG.BASE_FINAL
V252_D81_SHA = CFG.BASE_MEDIUM_SHA
V252_ELF_SHA = CFG.BASE_ELF_SHA
V252_SEAL_SHA = '8f3b379421f1a7ffaa6fae9b9155377145418a1cf094be4c4c2ece71514f09e5'


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
    # 2.5.3 F2: %set-macro root (native service 35) with a collection at EVERY
    # allocation, including alloc(T_MACRO).  NEW scenario: its oracle strings
    # (echo 'MY-ID', expansion result '7') must be confirmed against one
    # unforced run on the Final before the forced sweep is trusted.
    cases['defmacro-gc']=dict(setup=[],active='(defmacro my-id (x) x)',steps=[('defmacro-return',13,'=MY-ID')])
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
        # The seal check itself requires the sealed HEAD and passed there; its
        # committed seal is re-bound here by hash, and the Final identity below
        # binds the exact D81/ELF bytes.  C253-CHECK: SOURCE_RUN, SEAL_SHA.
        require(SEAL_SHA and SOURCE_RUN,'SEAL_SHA/SOURCE_RUN not set after the seal check')
        invocation=json.loads((ROOT/FINAL/'final-invocation.json').read_text())
        require(invocation['sealed_run']==SOURCE_RUN,'wrong sealed run')
        require(bind(ROOT/FINAL/'seal.json')['sha256']==SEAL_SHA,'seal drift')
        identity=json.loads((ROOT/FINAL/'final-identity.json').read_text())
        rows={r['role']:r['final'] for r in identity['artifacts']}
        require(rows['D81']['sha256']==D81_SHA and rows['ELF']['sha256']==ELF_SHA,'wrong Final')
        return checked(rows['D81']),checked(rows['ELF'])
    if role=='v252':
        identity=json.loads((ROOT/V252_FINAL/'final-identity.json').read_text())
        require(bind(ROOT/V252_FINAL/'seal.json')['sha256']==V252_SEAL_SHA,'2.5.2 seal drift')
        rows={r['role']:r['final'] for r in identity['artifacts']}
        require(rows['D81']['sha256']==V252_D81_SHA and rows['ELF']['sha256']==V252_ELF_SHA,'wrong 2.5.2 Final')
        return checked(rows['D81']),checked(rows['ELF'])
    raise ValueError('unknown world role: '+str(role))


def screen_matches(screen,want):
    import comfort_default_rows as D
    decoded=D.L.lines(screen)
    lines=[x.replace('{$A0}',' ').rstrip() for x in decoded]
    active=lines[-1].strip()
    if want=='@empty':return active==''
    nonblank=[x.strip() for x in lines if x.strip()]
    if want.isdigit():return len(nonblank)>=2 and nonblank[-2:]==[want,'L65>']
    # '=TEXT': a non-numeric result line followed by a fresh prompt (2.5.3 defmacro echo).
    if want.startswith('='):return len(nonblank)>=2 and nonblank[-2:]==[want[1:].upper(),'L65>']
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


PEAK_PHASE={'return250':'return-echo-scan-reader','defmacro-gc':'defmacro-return'}


def compare(a,b):
    # b is the 2.5.2 Final (role v252); any scenario with both receipts may be compared.
    require(a['status']==b['status']=='PASS' and a['role']=='lite' and b['role']=='v252' and
            a['scenario']==b['scenario'],'comparison populations differ')
    require(a['medium']['sha256']==D81_SHA and a['ELF']['sha256']==ELF_SHA, 'comparison is not the 2.5.3 Final')
    require(b['medium']['sha256']==V252_D81_SHA and b['ELF']['sha256']==V252_ELF_SHA, 'comparison is not the 2.5.2 Final')
    require(a['scenario_contract']==b['scenario_contract']==scenarios()[a['scenario']], 'comparison stimuli differ')
    require(a['no_heap_exhaustion'] is True and b['no_heap_exhaustion'] is True,'comparison lacks progress proof')
    def peak(row):
        values=[r['after'] for r in row['collections'] if r['phase']==PEAK_PHASE[row['scenario']]]
        require(values,'measured phase absent')
        return {k:max(v[k] for v in values) for k in ('live_cells','arena_bytes')}
    x,y=peak(a),peak(b)
    require(all(x[k]<=y[k] for k in x),'250-character Return peak regression')
    return dict(status='PASS',v253=x,v252=y,delta={k:x[k]-y[k] for k in x})


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
        assert screen_matches('MY-ID\nL65> {$A0}', '=MY-ID') and not screen_matches('L65> (DEFMACRO MY-ID', '=MY-ID')
        try: world('lite')
        except (ValueError, OSError): pass
        else: require(SEAL_SHA and SOURCE_RUN, 'unsealed Final admitted')
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
        def receipt(role,n,scenario='return250'):
            return dict(status='PASS',role=role,scenario=scenario,scenario_contract=scenarios()[scenario],no_heap_exhaustion=True,
                medium=dict(sha256=D81_SHA if role=='lite' else V252_D81_SHA),
                ELF=dict(sha256=ELF_SHA if role=='lite' else V252_ELF_SHA),
                collections=[dict(phase=PEAK_PHASE[scenario],after=dict(live_cells=n,arena_bytes=100))])
        compare(receipt('lite',99),receipt('v252',100))
        compare(receipt('lite',99,'defmacro-gc'),receipt('v252',100,'defmacro-gc'))
        try:compare(receipt('lite',101),receipt('v252',100))
        except ValueError:rejected.append('Return regression')
        else:raise AssertionError('peak regression accepted')
        return dict(status='PASS',scenarios=list(s),protocol_tests=['GC return PC and SP', 'GC generation population', 'counted singleton wraparound', 'fresh result/prompt and wrapped active-line oracles'],negative_controls=rejected,emulator_runs=0,product_builds=0)


if __name__=='__main__':
    require(__debug__,'assertions required')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--selftest',action='store_true');p.add_argument('--role',choices=['lite','v252'])
    p.add_argument('--out');p.add_argument('--scenario',choices=list(scenarios()))
    p.add_argument('--compare',nargs=2,metavar=('V253_RECEIPT','V252_RECEIPT'))
    a=p.parse_args()
    if a.selftest: result=selftest()
    elif a.compare: result=compare(*(json.loads((ROOT/f).read_text()) for f in a.compare))
    else:
        require(a.role and a.out and a.scenario,'role, out and scenario required')
        require(a.role!='v252' or a.scenario in PEAK_PHASE,'v252 baseline only for scenarios with a comparison phase')
        target=(ROOT/a.out).resolve();require(target.is_relative_to(ROOT/'build'),'output must be under build')
        result=run_case(a.role,a.scenario,target)
    print(json.dumps(result,indent=2))
