"""Temporal reset control: change journal after zero write, before readback."""
import argparse
import inspect
from pathlib import Path
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_read_path_trace_20260926 as T
import nested_error_recovery_gates as G
ROOT=P.ROOT


def trace(m,world,out,steps,result):
    assert world['ELF']['sha256']=='139e7775802f0caa1052dfb46d4144582e92c534891706607d948ae7fa24b4ae'
    main=next(r for r in P.load(S.OUT/'inventory-r1/instructions/function-instructions.json') if r['before']['name']=='main')
    points={w['before']['address']:w['after'] for w in main['witnesses']}
    p=points[0xa85d];T.boundary(m,p['address'],'stage succeeded; reset called',steps,p['bytes'])
    # The call opcode has executed; reader entry has not. Reset's preceding
    # DMA write is complete. Change only the journal byte in this disposable
    # guest, never source or medium bytes and never after READY.
    r=T.boundary(m,0xc3f4,'before reset read executes',steps,'209522')
    assert r['pc']==0x2295 and r['ready']==0 and r['arm']==0
    before=m.memory_range(0x5de20,72);assert before==bytes(72)
    m.command('s 0005de20 a6');after=m.memory_range(0x5de20,72);assert after==b'\xa6'+bytes(71)
    result['injection']=dict(address=0x5de20,before=before.hex(),after=after.hex(),when='after zero DMA, before readback; READY0',guest_only=True)
    r=T.boundary(m,0xc416,'reset refusal selected',steps,'98');assert r['a']==3 and r['arm']==0
    p=points[0xa862];T.boundary(m,p['address'],'READY preserved',steps,p['bytes'])
    m.end_breakpoint_connection();m.command('t0');screen=m.wait_screen(['LISP65>'],timeout=180);(out/'boot-screen.txt').write_text(screen)
    G.submit(m,out,'arithmetic','(+ 4 5)','9',steps,timeout=180)
    m.command('t1');result.update(ready=m.memory16(0x8c)[0],arm=m.memory16(0x31)[0],tenant_intact=m.memory_range(0x5de80,8192)==(S.PRODUCT/'set-b-tenants.bin').read_bytes())
    assert result['ready']==1 and result['arm']==0 and result['tenant_intact']
    print('PASS temporal journal control: reset refused, READY/live arithmetic prompt preserved',flush=True)


def main(out):
    S.require_auth();src=inspect.getsource(T.main).replace('build/set-b-product-r3/','build/set-b-product-r5/')
    a=src.index('            # All PCs bound');b=src.index('        except BaseException:',a)
    src=src[:a]+'            trace(monitor,world,out,steps,result)\n'+src[b:]
    src=src.replace('PASS: EXECUTED RESET REFUSAL ATTRIBUTION','PASS: TEMPORAL JOURNAL REFUSAL WITH LIVE PROMPT')
    folder=S.OUT/'temporal-driver-r1';folder.mkdir(exist_ok=False);(folder/'executed.py').write_text(src)
    P.write(folder/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(T.__file__)),executed=P.bind(folder/'executed.py'),product_links=0))
    ns=dict(vars(T));ns.update(trace=trace,MEDIAROOT=ROOT/'build/set-b-seed-medium-r6',__file__=__file__)
    exec(compile(src,str(folder/'executed.py'),'exec'),ns);ns['main'](out,'candidate')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);main(ap.parse_args().out.resolve())
