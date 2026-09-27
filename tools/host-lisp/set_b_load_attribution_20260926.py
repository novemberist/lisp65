"""Owner-approved attribution on the immutable fifth Seed, no product builds.

Fresh boots with zero/one/two definitions delimit the refused library load.
T and NIL are observations, not interchangeable gate successes. Exact new
echo/result/prompt and complete stopped state are recorded before shutdown.
"""
import argparse
import inspect
import time
from pathlib import Path
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_seed_boot_20260926 as B
import set_b_fifth_oracle_r4_20260926 as O
import nested_error_recovery_gates as G
import retained_callable_writer_analysis as A
ROOT=P.ROOT
OUT=ROOT/'build/set-b-load-attribution-r1'


def workload(m,out,truth,steps,result,n):
    captures=[];result['captures']=captures
    def snap(label):
        m.command('t1')
        try:
            r=G.dump(m,out,label,captures,{'c2_ready':truth.symbol('c2_ready').value})
            c=(out/f'{label}-c2d.bin').read_bytes()
            r.update(counts=A.counts(c),arm=m.memory16(truth.symbol('c2r_boot_count').value)[0],tenant_intact=c[0xde80:0xfe80]==(S.PRODUCT/'set-b-tenants.bin').read_bytes())
            P.write(out/'captures.json',captures)
            assert r['c2_ready']==1 and r['arm']==134 and r['tenant_intact'],r
            return r
        finally:m.command('t0')
    snap('boot')
    for i in range(n):
        O.submit(m,out,f'define-{i}',f'(defun capfill () {7+i})','CAPFILL',steps,timeout=180)
        snap(f'define-{i}')
    snap('before-load')
    form='(require "defstruct")';before=m.screen();(out/'load-before-screen.txt').write_text(before)
    m.type_text(form+'\n');deadline=time.monotonic()+180;actual=None
    while time.monotonic()<deadline:
        after=m.screen()
        actual=next((v for v in ('T','NIL') if O.valid(before,after,form,v)),None)
        if actual:break
        if any('***' in s for s in O.lines(after)[-3:]):raise AssertionError(('new error class',O.lines(after)))
        time.sleep(.1)
    (out/'load-screen.txt').write_text(after);assert actual,('load result absent',O.lines(after))
    result['load_result']=actual;result['definitions']=n
    snap('after-load')
    if actual=='NIL':
        for region in ('c2d','bank2'):
            assert (out/f'before-load-{region}.bin').read_bytes()==(out/f'after-load-{region}.bin').read_bytes(),('refused load changed plane',region)
    print('OBSERVED',n,'definitions; require defstruct ->',actual,flush=True)


def main(n):
    S.require_auth();out=OUT/f'definitions-{n}';folder=OUT/f'driver-{n}';folder.mkdir(exist_ok=False,parents=True)
    source=inspect.getsource(B.main).replace('build/set-b-product-r3/','build/set-b-product-r5/')
    a=source.index("            G.submit(monitor,out,'arithmetic'");b=source.index('        except BaseException:',a)
    source=source[:a]+'            workload(monitor,out,truth,steps,result,NDEFS)\n'+source[b:]
    source=source.replace('PASS: MEDIUM BOOT AND LIVE PROMPT','CAPTURED: LIBRARY LOAD ATTRIBUTION')
    (folder/'executed.py').write_text(source)
    P.write(folder/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(B.__file__)),executed=P.bind(folder/'executed.py'),owner_scope='Freigabe erteilt after halt19738af1; host-only attribution; zero product builds/links/Seeds/device',definitions=n))
    ns=dict(vars(B));ns.update(workload=workload,NDEFS=n,MEDIAROOT=ROOT/'build/set-b-seed-medium-r6',__file__=__file__)
    exec(compile(source,str(folder/'executed.py'),'exec'),ns);ns['main'](out,'candidate')
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('definitions',type=int,choices=range(0,51));a=ap.parse_args();main(a.definitions)
