"""Successor: initialize each Lisp argument with a separate setq form.

The r1 harness assumed multi-pair setq; delivered %lcc-setq compiles
only its first pair. Preserve r1 as an invalid fixture, not row evidence.
"""
import inspect
from pathlib import Path
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_seed_boot_20260926 as B
import set_b_fifth_oracle_r4_20260926 as O
import nested_error_recovery_gates as G
ROOT=P.ROOT
OUT=ROOT/'build/set-b-load-predicates-r2'
ROWS=[
 ('define0','(defun capfill () 7)','CAPFILL'),
 ('define1','(defun capfill () 8)','CAPFILL'),
 ('index','(if (%l65i-parse) 101 102)','101'),
 ('state','(if (%require-c2d-state) 111 112)','111'),
 ('world','(if (%require-world nil) 121 122)','122'),
 ('arg-base','(progn (setq rb (cons 48 1)) 131)','131'),
 ('arg-gen','(progn (setq rg (cons 1 0)) 132)','132'),
 ('arg-low','(progn (setq rl (cons 3 198)) 133)','133'),
 ('row','(if (%require-persistent-row-size rb 8 rg rl) 201 202)','202'),
 ('kind','(+ 300 (%require-row-byte rb 0))','301'),
 ('source','(+ 310 (%require-row-byte rb 2))','312'),
 ('reserved',"(if (%require-row-zeroes-p rb '(1 3 20 23 24 25 26 27)) 321 322)",'321'),
 ('generation','(if (%require-u16= (%require-row-u16 rb 4) rg) 331 332)','331'),
 ('contiguity','(if (%require-u16= (%require-row-u16 rb 18) rl) 341 342)','342'),
 ('actual-low','(+ 350 (%require-row-byte rb 18))','363'),
 ('actual-high','(+ 600 (%require-row-byte rb 19))','798'),
 ('actual-size','(+ 400 (%require-row-byte rb 21))','410'),
 ('actual-arg','(progn (setq rl (cons 13 198)) 411)','411'),
 ('only-low-arg-changed','(if (%require-persistent-row-size rb 8 rg rl) 421 422)','421'),
]

def workload(m,out,truth,steps,result):
    captures=[];result['captures']=captures
    for label,form,expected in ROWS:
        assert len(form)+8<80,(label,len(form))
        O.submit(m,out,label,form,expected,steps,timeout=240)
        if label in ('define1','world','contiguity','only-low-arg-changed'):
            m.command('t1');G.dump(m,out,label,captures,{'c2_ready':0x8c});m.command('t0')
    m.command('t1');result.update(ready=m.memory16(0x8c)[0],arm=m.memory16(0x31)[0],tenant_intact=m.memory_range(0x5de80,8192)==(S.PRODUCT/'set-b-tenants.bin').read_bytes())
    assert result['ready']==1 and result['arm']==134 and result['tenant_intact']
    print('PASS attribution: resolver rejects old contiguous code-low; actual low argument alone passes row predicate',flush=True)


def main():
    S.require_auth();src=inspect.getsource(B.main).replace('build/set-b-product-r3/','build/set-b-product-r5/')
    src=src.replace("str(memory), '600'","str(memory), '1800'")
    a=src.index("            G.submit(monitor,out,'arithmetic'");b=src.index('        except BaseException:',a)
    src=src[:a]+'            workload(monitor,out,truth,steps,result)\n'+src[b:]
    src=src.replace('PASS: MEDIUM BOOT AND LIVE PROMPT','PASS: EXECUTED RESOLVER PREDICATE ATTRIBUTION')
    folder=ROOT/'build/set-b-load-predicates-driver-r2';folder.mkdir(exist_ok=False);(folder/'executed.py').write_text(src)
    P.write(folder/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(B.__file__)),executed=P.bind(folder/'executed.py'),rows=ROWS,guest_memory_edits=0,product_changes=0))
    ns=dict(vars(B));ns.update(workload=workload,MEDIAROOT=ROOT/'build/set-b-seed-medium-r6',__file__=__file__)
    exec(compile(src,str(folder/'executed.py'),'exec'),ns);ns['main'](OUT,'candidate')
if __name__=='__main__':main()
