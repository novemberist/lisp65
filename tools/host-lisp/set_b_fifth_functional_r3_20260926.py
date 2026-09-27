"""Prompt-by-prompt reuse with a fresh input-echo/result oracle after scrolling.

Each definition has a unique body value. The exact unique echo must be
absent before input and must precede the exact result at the final prompt.
No stale result-count assumption. Explicit expected errors replay/disarm
per step 3b. Historical r1/r2 tools and receipts remain unchanged.
"""
import inspect
import time
from pathlib import Path
import set_b_fifth_functional_20260926 as F
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import dwx_retroactive_red_replay as R
import dwx_comfort_resume as C
ROOT=P.ROOT


def lines(screen):return [s.rstrip() for s in R.ROWS.decoded_framebuffer(screen).splitlines() if s.strip()]


def valid(before,after,form,expected):
    echo='LISP65> '+form.upper();ls=lines(after)
    return echo not in lines(before) and len(ls)>=3 and ls[-3:-1]==[echo,expected.upper()] and C.active(after)=='LISP65>'


def submit(m,out,label,form,expected,steps,timeout=900):
    before=m.screen();echo='LISP65> '+form.upper();assert echo not in lines(before),'unique echo required'
    (out/f'step-{label}-before-screen.txt').write_text(before)
    m.type_text(form+'\n');start=time.monotonic();after=''
    while time.monotonic()-start<timeout:
        after=m.screen()
        if valid(before,after,form,expected):break
        time.sleep(.1)
    p=out/f'step-{label}-screen.txt';p.write_text(after)
    row=dict(label=label,form=form,expected=expected,passed=valid(before,after,form,expected),tail=lines(after)[-6:],screen=P.bind(p),wall_seconds=round(time.monotonic()-start,1))
    steps.append(row);P.write(out/'steps.json',steps)
    print('form',label,'PASS' if row['passed'] else 'FAIL',row['tail'][-3:],flush=True)
    assert row['passed'],row


def main():
    # Falling stale/incorrect-result controls of the output oracle.
    b='LISP65> ';a='LISP65> (DEFUN CAPFILL () 17)\nCAPFILL\nLISP65> '
    assert valid(b,a,'(defun capfill () 17)','CAPFILL')
    assert not valid(a,a,'(defun capfill () 17)','CAPFILL')
    assert not valid(b,a.replace('CAPFILL\n','WRONG\n'),'(defun capfill () 17)','CAPFILL')
    body=inspect.getsource(F.workload).replace("captures=[];result['captures']=captures", "captures=[];result['captures']=captures;want_arm=134")
    body=body.replace("row['arm']&128", "row['arm']==want_arm")
    body=body.replace("        G.submit(m,out,label,form,expected,steps,timeout=900)","        nonlocal want_arm\n        submit_exact(m,out,label,form,expected,steps,timeout=900)\n        if expected.startswith('***'):want_arm=0")
    body=body.replace('{7+i%2}', '{7+i}').replace("submit('call-50','(capfill)','7')", "submit('call-50','(capfill)','57')")
    driver=inspect.getsource(F.main).replace("'-driver-r1'", "'-driver-r3'")
    folder=S.OUT/'functional-reuse-oracle-r3';folder.mkdir(exist_ok=False)
    (folder/'workload.py').write_text(body);(folder/'driver.py').write_text(driver)
    P.write(folder/'binding.json',dict(parent=P.bind(Path(F.__file__)),driver=P.bind(Path(__file__)),stale_and_wrong_result_controls_rejected=2,
        changes='unique definition body 7+i, exact fresh echo/result; expected abort disarms per step 3b',product_changes=0))
    ns=dict(vars(F));ns.update(__file__=__file__,submit_exact=submit)
    exec(compile(body,str(folder/'workload.py'),'exec'),ns);exec(compile(driver,str(folder/'driver.py'),'exec'),ns)
    ns['main'](ROOT/'build/set-b-fifth-functional-reuse-r3','reuse')

if __name__=='__main__':main()
