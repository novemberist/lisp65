"""Reviewer regression suite, retained-callable and nested-error rows plus both 23-row usage lanes."""
import argparse
import ast
import json
import os
import traceback
from card_l_r1_common import ROOT, worlds, preview, arguments, marker, N, R, ElfTruth
import nested_error_recovery_gates as G
import nested_error_recovery_gate_analysis as A

USAGE_SOURCE=ROOT/'tools/host-lisp/retained_callable_repair_r2_usage.py'
USAGE=ast.literal_eval(next(n.value for n in ast.parse(USAGE_SOURCE.read_text()).body
    if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ROWS' for t in n.targets)))
assert len(USAGE)==23
MODES=['retained-1','retained-2','retained-16','retained-54','lambda','nested','overcap','cumulative','usage']

def one(w,mode,out):
    out.mkdir(exist_ok=False,parents=True)
    truth=ElfTruth.read(N.checked_binding(w['ELF']),llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    symbols={'c2_ready':truth.symbol('c2_ready').value}
    os.environ['LISP65_COST_CONFIG']=w['cost_config']
    os.environ['LISP65_DWX_PC_OUTPUT']=str(out/'pc-current.txt')
    captures=[];steps=[];markers=[];checks=[];run=None;error=None
    try:
        run=R.start_run(mode,N.checked_binding(w['medium']),out,arguments(w));m=run['monitor']
        def mark(label):
            if w['role']=='candidate':markers.append(dict(label=label,**marker(m,out,label)))
        def snap(label):
            m.command('t1')
            try:G.dump(m,out,label,captures,symbols)
            finally:m.command('t0')
            assert captures[-1]['c2_ready']==1
            mark(label)
        def submit(label,form,expected):
            G.submit(m,out,label,form,expected,steps,timeout=900)
            mark('row-'+label)
        def identical(before,after):
            row=A.identical(out,before,after);assert row['ok'],row;checks.append(row)
        mark('boot')
        if mode=='usage':
            for i,(form,expected) in enumerate(USAGE):submit(f'usage-{i:02d}',form,expected)
            assert len(steps)==23
        elif mode=='lambda':
            snap('before')
            submit('lambda','(progn (setq savedlambda (lambda () 27)) 19)','*** VM: BAD BYTECODE')
            snap('after-lambda')
            comp=A.population(A.region(out,'before','c2d'),A.region(out,'before','bank2'),A.region(out,'after-lambda','c2d'),A.region(out,'after-lambda','bank2'))
            assert comp['ok'];checks.append(comp)
            submit('symbol','savedlambda','NIL')
            submit('recovery','(+ 40 2)','42')
            snap('after')
            # The refused lambda must publish no image or code; symbol interning is allowed.
            before=A.region(out,'before','c2d');after=A.region(out,'after','c2d')
            assert A.A.counts(before)['images']==A.A.counts(after)['images']
            checks.append(dict(bank2_identical=A.region(out,'before','bank2')==A.region(out,'after-lambda','bank2')))
        else:
            submit('require','(require "defstruct")','T');snap('package')
            assert A.A.counts(A.region(out,'package','c2d'))['images']==9
            if mode.startswith('retained-'):
                count=int(mode.split('-')[1])
                submit('loop',f"(dotimes (n {count}) (eval '(defun capn () 7)))",'NIL');snap('loop')
                checks.append(A.published(out,'package','loop',count))
                submit('call','(capn)','7');snap('call');identical('loop','call')
            elif mode=='nested':
                submit('nested',G.NESTED,G.ERROR);snap('after-nested');identical('package','after-nested')
                submit('recovery','(+ 4 5)','9');snap('end');identical('after-nested','end')
            else:
                previous='package'
                if mode=='cumulative':
                    for count in (1,2,16):
                        submit(f'loop-{count}',f"(dotimes (n {count}) (eval '(defun capn{count} () 7)))",'NIL')
                        snap(f'loop-{count}');checks.append(A.published(out,previous,f'loop-{count}',count))
                        submit(f'call-{count}',f'(capn{count})','7');snap(f'call-{count}')
                        identical(f'loop-{count}',f'call-{count}');previous=f'call-{count}'
                count=54 if mode=='cumulative' else 60
                submit('overcap',f"(dotimes (n {count}) (eval '(defun capend () 7)))",G.OOM);snap('overcap')
                checks.append(A.published(out,previous,'overcap',35 if mode=='cumulative' else 54))
                assert A.A.counts(A.region(out,'overcap','c2d'))['images']==63
                submit('refuse64',"(dotimes (n 1) (eval '(defun caprefused () 7)))",G.OOM);snap('refuse64')
                identical('overcap','refuse64')
                for name in (['capn1','capn2','capn16'] if mode=='cumulative' else [])+['capend']:
                    submit('recall-'+name,f'({name})','7')
                submit('recovery','(+ 4 5)','9');snap('end');identical('refuse64','end')
        mark('end-marker')
    except BaseException:
        error=traceback.format_exc();raise
    finally:
        output=R.finish_run(run) if run else None
        (out/'receipt.json').write_text(json.dumps(dict(status='HALT' if error else 'PASS',mode=mode,world=w,
            steps=steps,captures=captures,markers=markers,checks=checks,error=error,output=output,
            driver=N.bind(ROOT/'tools/host-lisp/card_l_r1_gates.py'),product_builds=0,device_contacts=0),indent=2)+'\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--dry-run',action='store_true');p.add_argument('--attempt',default='r1')
    p.add_argument('--mode',choices=['all']+MODES,default='all');a=p.parse_args()
    ws=worlds();modes=MODES if a.mode=='all' else [a.mode]
    base=ROOT/f'build/card-l-regression-{a.attempt}'
    prior=R.ProbeMonitor
    class Monitor(prior):
        def wait_screen(self,required,timeout=20):return super().wait_screen(required,timeout=180)
    R.ProbeMonitor=Monitor
    for mode in modes:
        for w in ws if mode=='usage' else [ws[1]]:
            out=base/(mode+'-'+w['role'])
            if a.dry_run:preview(w,out,mode)
            else:one(w,mode,out)
    if a.dry_run:print('DRY RUN PASS: N=1/2/16/54, lambda refusal, nested error, cap 63/64, cumulative, 23+23 usage rows; Bank-2 bytes and candidate markers checked; no emulator launched')
if __name__=='__main__':main()
