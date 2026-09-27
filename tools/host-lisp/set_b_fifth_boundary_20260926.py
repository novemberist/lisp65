"""Positive reset and first retirement boundaries on the immutable fifth Seed."""
import argparse
import inspect
from pathlib import Path
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_read_path_trace_20260926 as T
from set_b_third_seed_inventory_halt_20260926 import instructions
ROOT=P.ROOT


def trace(m,world,out,steps,result):
    assert world['ELF']['sha256']=='139e7775802f0caa1052dfb46d4144582e92c534891706607d948ae7fa24b4ae'
    code,cmd,raw=instructions(ROOT/world['ELF']['path']);(out/'disassembly.txt').write_text(raw)
    def stop(pc,label,section='.text'):
        row=code[section][pc];v=T.boundary(m,pc,label,steps,row['bytes'])
        v.update(busy=m.memory16(0x78)[0],phase_owner=m.memory16(0x89)[0],gc_roots=m.memory16(0x5c)[0])
        return v
    # Main's coordinates come from the closed paired-instruction proof.
    main=next(r for r in P.load(S.OUT/'inventory-r1/instructions/function-instructions.json') if r['before']['name']=='main')
    mapped={w['before']['address']:w['after']['address'] for w in main['witnesses']}
    stop(mapped[0xa85d],'stage succeeded; reset called')
    r=stop(0xc3f4,'reset read called','.lisp65_rt_c2append_retire_reset')
    dest=int.from_bytes(bytes.fromhex(r['zp'])[6:8],'little');assert m.memory16(dest)[0]==255
    r=stop(0xc3f7,'physical reader returned','.lisp65_rt_c2append_retire_reset');assert r['a']==1 and m.memory16(dest)[0]==0
    r=stop(0xc416,'reset OK and armed','.lisp65_rt_c2append_retire_reset');assert r['a']==0 and r['arm']&128
    stop(mapped[0xa862],'READY published')
    r=stop(0x4c64,'resident transaction begin call');assert r['busy']==0
    r=stop(0x4c67,'resident begin returned');assert r['a']==0 and r['busy']==0
    r=stop(0xc368,'control tenant entered','.lisp65_rt_c2append_retire_control');assert r['busy']==1
    r=stop(0x4c31,'control returned to resident');assert r['a']==1 and r['busy']==0
    r=stop(0x4c10,'resident transaction end call');assert r['busy']==0 and r['phase_owner']==2
    r=stop(0x4c13,'resident end returned');assert r['a']==0 and r['busy']==0
    r=stop(0x2afe,'first retirement returned');assert r['a']==1 and r['busy']==0 and r['phase_owner']==0 and r['arm']&128
    assert m.memory_range(0x5de20,72)==bytes(72)
    m.end_breakpoint_connection();m.command('t0');screen=m.wait_screen(['LISP65>'],timeout=180)
    (out/'boot-screen.txt').write_text(screen);m.command('t1')
    result.update(ready=m.memory16(0x8c)[0],arm=m.memory16(0x31)[0],tenant_intact=m.memory_range(0x5de80,8192)==(S.PRODUCT/'set-b-tenants.bin').read_bytes(),journal_zero=m.memory_range(0x5de20,72)==bytes(72))
    assert result['ready']==1 and result['arm']&128 and result['tenant_intact'] and result['journal_zero']
    print('PASS reset and first retirement: resident begin/end, tenant busy, balanced cleanup',flush=True)


def main(out):
    S.require_auth();src=inspect.getsource(T.main).replace('build/set-b-product-r3/','build/set-b-product-r5/')
    start=src.index('            # All PCs bound');end=src.index('        except BaseException:',start)
    src=src[:start]+'            trace(monitor,world,out,steps,result)\n'+src[end:]
    src=src.replace('PASS: EXECUTED RESET REFUSAL ATTRIBUTION','PASS: FIFTH SEED RESET AND FIRST RETIREMENT')
    folder=S.OUT/'boundary-driver-r1';folder.mkdir(exist_ok=False);(folder/'executed.py').write_text(src)
    P.write(folder/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(T.__file__)),executed=P.bind(folder/'executed.py'),product_links=0))
    ns=dict(vars(T));ns.update(trace=trace,MEDIAROOT=ROOT/'build/set-b-seed-medium-r6',__file__=__file__)
    exec(compile(src,str(folder/'executed.py'),'exec'),ns);ns['main'](out,'candidate')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);main(ap.parse_args().out.resolve())
