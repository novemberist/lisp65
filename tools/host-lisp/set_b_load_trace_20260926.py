"""Read-only first failing append phase after one retirement on fifth Seed."""
import inspect
import time
from pathlib import Path
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_seed_boot_20260926 as B
import set_b_fifth_oracle_r4_20260926 as O
import nested_error_recovery_gates as G
import set_b_read_path_trace_20260926 as T
from set_b_third_seed_inventory_halt_20260926 import instructions
ROOT=P.ROOT
OUT=ROOT/'build/set-b-load-trace-r1'


def workload(m,out,truth,steps,result):
    code,cmd,raw=instructions(S.PRODUCT/'wplto/resident-island-seed.prg.elf');(out/'disassembly.txt').write_text(raw)
    flat={pc:r for sec,rows in code.items() if sec=='.text' or sec.startswith('.lisp65_c2_kernal_window') for pc,r in rows.items()}
    captures=[];result['captures']=captures;boundaries=[];result['boundaries']=boundaries
    def snap(label):
        G.dump(m,out,label,captures,{'c2_ready':0x8c})
    def stop(pc,label):
        r=T.boundary(m,pc,label,boundaries,flat[pc]['bytes']);r['scratch']=m.memory_range(0xc0c6,0x130).hex();r['runtime']=m.memory_range(0xc084,46).hex();r['phase_owner']=m.memory16(0x89)[0];return r
    O.submit(m,out,'define0','(defun capfill () 7)','CAPFILL',steps,timeout=180)
    O.submit(m,out,'define1','(defun capfill () 8)','CAPFILL',steps,timeout=180)
    m.command('t1');snap('before-load');before=m.screen();(out/'load-before-screen.txt').write_text(before)
    m.begin_breakpoint_connection();m.command('b 2773');m.command('t0');m.type_text('(require "defstruct")\n')
    r=stop(0x2773,'staged library enters append');result['staged_length']=r['a']+256*r['x'];assert result['staged_length']>0
    r=stop(0x279c,'transaction begin returned');assert r['a']==0
    r=stop(0xf109,'append entered');assert r['ready']==1
    phases=[];result['phases']=phases
    for i in range(32):
        r=stop(0xfee1,'overlay call');slot=r['a'];assert slot<56,('unexpected retirement in active append',slot)
        ret=int.from_bytes(m.memory_range(r['sp']+1,2),'little')+1
        assert ret in flat and flat[ret]['bytes'] in ('aa','8518'),(ret,flat.get(ret))
        q=stop(ret,'overlay return slot '+str(slot))
        phases.append(dict(slot=slot,call_pc=r['pc'],return_pc=ret,result=q['a'],call=r,returned=q))
        P.write(out/'phases.json',phases)
        if q['a']==0:break
    else:raise AssertionError('no failing append phase in 32 calls')
    result['first_failed_slot']=slot;snap('first-refusal')
    r=stop(0x27c0,'append result returned');assert r['a']==0
    r=stop(0x27c5,'transaction end returned');assert r['a']==0
    m.end_breakpoint_connection();m.command('~pcclearbreak');m.command('t0')
    until=time.monotonic()+180
    while time.monotonic()<until:
        after=m.screen()
        if O.valid(before,after,'(require "defstruct")','NIL'):break
        time.sleep(.1)
    else:raise AssertionError(O.lines(after))
    (out/'load-screen.txt').write_text(after);m.command('t1');snap('after-load')
    result.update(ready=m.memory16(0x8c)[0],arm=m.memory16(0x31)[0],tenant_intact=m.memory_range(0x5de80,8192)==(S.PRODUCT/'set-b-tenants.bin').read_bytes())
    assert result['ready']==1 and result['arm']==134 and result['tenant_intact']
    for region in ('bank2','c2d'):assert (out/f'before-load-{region}.bin').read_bytes()==(out/f'after-load-{region}.bin').read_bytes()
    print('ATTRIBUTED first failed overlay',slot,'with staged length',result['staged_length'],flush=True)


def main():
    S.require_auth();src=inspect.getsource(B.main).replace('build/set-b-product-r3/','build/set-b-product-r5/')
    a=src.index("            G.submit(monitor,out,'arithmetic'");b=src.index('        except BaseException:',a)
    src=src[:a]+'            workload(monitor,out,truth,steps,result)\n'+src[b:]
    src=src.replace('PASS: MEDIUM BOOT AND LIVE PROMPT','CAPTURED: APPEND REFUSAL TRACE')
    # Preserve the established explicit breakpoint shutdown on errors too.
    src=src.replace("                    (out/'last-screen.txt').write_text(monitor.screen())", "                    if getattr(monitor,'_breakpoint_socket',None) is not None:monitor.end_breakpoint_connection()\n                    (out/'last-screen.txt').write_text(monitor.screen())")
    folder=ROOT/'build/set-b-load-trace-driver-r1';folder.mkdir(exist_ok=False);(folder/'executed.py').write_text(src)
    P.write(folder/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(B.__file__)),executed=P.bind(folder/'executed.py'),product_changes=0))
    ns=dict(vars(B));ns.update(workload=workload,MEDIAROOT=ROOT/'build/set-b-seed-medium-r6',__file__=__file__)
    exec(compile(src,str(folder/'executed.py'),'exec'),ns);ns['main'](OUT,'candidate')
if __name__=='__main__':main()
