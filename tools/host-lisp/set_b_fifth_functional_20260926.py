"""Fifth Seed prompt maintenance: exact results, directory and tenant snapshots.

Read-only guest inspection and keyboard input on a private SD/medium. No
product compile/link. Stop at the first failed result, disarm or corruption.
Snapshots assert equality at boundaries, not absence of intervening writes.
"""
import argparse
import inspect
from pathlib import Path
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_seed_boot_20260926 as B
import nested_error_recovery_gates as G
import retained_callable_writer_analysis as A
ROOT=P.ROOT


def workload(m,out,truth,steps,result,mode):
    captures=[];result['captures']=captures
    def snap(label):
        m.command('t1')
        try:
            row=G.dump(m,out,label,captures,{'c2_ready':truth.symbol('c2_ready').value})
            c2d=(out/f'{label}-c2d.bin').read_bytes()
            row.update(counts=A.counts(c2d),arm=m.memory16(truth.symbol('c2r_boot_count').value)[0],
                       tenant_intact=c2d[0xde80:0xfe80]==(S.PRODUCT/'set-b-tenants.bin').read_bytes())
            P.write(out/'captures.json',captures)
            assert row['c2_ready']==1 and row['arm']&128 and row['tenant_intact'],row
            return row
        finally:m.command('t0')
    def submit(label,form,expected):
        G.submit(m,out,label,form,expected,steps,timeout=900)
        return snap(label)
    initial=snap('initial')
    if mode=='reuse':
        first=submit('define-0','(defun capfill () 7)','CAPFILL')
        submit('call-0','(capfill)','7')
        for i in range(1,51):
            row=submit(f'define-{i}',f'(defun capfill () {7+i%2})','CAPFILL')
            assert row['counts']['images']==first['counts']['images'],('unreferenced image did not retire',first['counts'],row['counts'])
        submit('call-50','(capfill)','7')
        submit('require','(require "defstruct")','T')
        submit('intern','(intern "set-b-probe")','SET-B-PROBE')
        submit('nested',G.NESTED,G.ERROR)
        submit('recovery','(+ 4 5)','9')
    elif mode=='lambda':
        row=submit('lambda','(progn (setq savedlambda (lambda () 27)) 19)','*** VM: BAD BYTECODE')
        assert row['counts']['images']==initial['counts']['images']
        assert (out/'initial-bank2.bin').read_bytes()==(out/'lambda-bank2.bin').read_bytes()
        submit('symbol','savedlambda','NIL');submit('recovery','(+ 40 2)','42')
    else:raise AssertionError(mode)
    result['functional_mode']=mode
    print('PASS functional',mode,flush=True)


def main(out,mode):
    S.require_auth();src=inspect.getsource(B.main).replace('build/set-b-product-r3/','build/set-b-product-r5/')
    src=src.replace("str(memory), '600'","str(memory), '7200'")
    a=src.index("            G.submit(monitor,out,'arithmetic'")
    b=src.index('        except BaseException:',a)
    src=src[:a]+'            workload(monitor,out,truth,steps,result,MODE)\n'+src[b:]
    src=src.replace('PASS: MEDIUM BOOT AND LIVE PROMPT','PASS: FIFTH SEED FUNCTIONAL '+mode)
    folder=S.OUT/('functional-'+mode+'-driver-r1');folder.mkdir(exist_ok=False)
    (folder/'executed.py').write_text(src)
    P.write(folder/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(B.__file__)),executed=P.bind(folder/'executed.py'),product_links=0))
    ns=dict(vars(B));ns.update(workload=workload,MODE=mode,MEDIAROOT=ROOT/'build/set-b-seed-medium-r6',__file__=__file__)
    exec(compile(src,str(folder/'executed.py'),'exec'),ns);ns['main'](out,'candidate')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['reuse','lambda']);a=ap.parse_args()
    main(ROOT/f'build/set-b-fifth-functional-{a.mode}-r1',a.mode)
