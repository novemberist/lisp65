"""Native retention through values, conses, function cells, closures and trace."""
import inspect
from pathlib import Path
import set_b_fifth_functional_20260926 as F
import set_b_fifth_functional_r3_20260926 as O
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
ROOT=P.ROOT
ROWS=[
 ('inspect','(require "inspect")','T'),
 ('define7','(defun hold () 7)','HOLD'),
 ('save-value',"(progn (setq kept (%function-cell 'hold)) 101)",'101'),
 ('define8','(defun hold () 8)','HOLD'),
 ('value-old','(funcall kept)','7'),
 ('save-cons',"(progn (setq keptlist (list (%function-cell 'hold))) 102)",'102'),
 ('define9','(defun hold () 9)','HOLD'),
 ('cons-old','(funcall (car keptlist))','8'),
 ('save-function',"(progn (%function-cell 'alias (%function-cell 'hold)) 103)",'103'),
 ('define10','(defun hold () 10)','HOLD'),
 ('function-old','(alias)','9'),
 ('box','(defun box (v) (lambda () (funcall v)))','BOX'),
 ('save-closure',"(progn (setq keptclosure (box (%function-cell 'hold))) 104)",'104'),
 ('define11','(defun hold () 11)','HOLD'),
 ('closure-old','(funcall keptclosure)','10'),
 ('trace','(trace hold)','HOLD'),
 ('trace-original',"(funcall (%inspect-trace-original 'hold))",'11'),
 ('untrace','(untrace hold)','HOLD'),
 ('hold','(hold)','11'),
 ('final-value','(+ 1000 (funcall kept))','1007'),
 ('final-cons','(+ 1000 (funcall (car keptlist)))','1008'),
 ('final-function','(+ 1000 (alias))','1009'),
 ('final-closure','(+ 1000 (funcall keptclosure))','1010'),
]

def main():
    body=inspect.getsource(F.workload)
    a=body.index("    if mode=='reuse':");b=body.index("    result['functional_mode']",a)
    body=body[:a]+"    for label,form,expected in ROWS:submit(label,form,expected)\n"+body[b:]
    body=body.replace('G.submit(m,out,label,form,expected,steps,timeout=900)','submit_exact(m,out,label,form,expected,steps,timeout=900)')
    driver=inspect.getsource(F.main).replace("'-driver-r1'","'-driver-r1'")
    folder=S.OUT/'functional-carriers-source-r1';folder.mkdir(exist_ok=False)
    (folder/'workload.py').write_text(body);(folder/'driver.py').write_text(driver)
    P.write(folder/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(F.__file__)),oracle=P.bind(Path(O.__file__)),rows=ROWS,product_changes=0))
    ns=dict(vars(F));ns.update(__file__=__file__,ROWS=ROWS,submit_exact=O.submit)
    exec(compile(body,str(folder/'workload.py'),'exec'),ns);exec(compile(driver,str(folder/'driver.py'),'exec'),ns)
    ns['main'](ROOT/'build/set-b-fifth-functional-carriers-r1','carriers')
if __name__=='__main__':main()
