"""Correct the arm oracle for explicit abort; preserve exact error and byte checks.

Step 3b explicitly routes c2_product_abort_recover through c2_retire_run(1),
which replays then disarms even for a designed Lisp error. The r1 assertion
that every form stays armed was too strong. No product bytes change. r1
receipt remains an invalid-oracle result, never relabelled PASS.
"""
import argparse
import inspect
from pathlib import Path
import set_b_fifth_functional_20260926 as F
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
ROOT=P.ROOT


def main(mode):
    body=inspect.getsource(F.workload)
    body=body.replace("captures=[];result['captures']=captures", "captures=[];result['captures']=captures;want_arm=134")
    body=body.replace("row['arm']&128", "row['arm']==want_arm")
    body=body.replace("        G.submit(m,out,label,form,expected,steps,timeout=900)","        nonlocal want_arm\n        G.submit(m,out,label,form,expected,steps,timeout=900)\n        if expected.startswith('***'):want_arm=0")
    driver=inspect.getsource(F.main).replace("'-driver-r1'", "'-driver-r2'")
    folder=S.OUT/('functional-'+mode+'-oracle-r2');folder.mkdir(exist_ok=False)
    (folder/'workload.py').write_text(body);(folder/'driver.py').write_text(driver)
    P.write(folder/'binding.json',dict(parent=P.bind(Path(F.__file__)),driver=P.bind(Path(__file__)),
        transformations='Require 0x86 before any expected abort, zero after it; exact result/READY/tenant/Bank2 assertions unchanged',
        authority=[dict(path='src/c2_product_runtime.c',lines='4208-4225; 4397-4418'),dict(path='docs/planning/post-2.4.0-plan.md',entry='Set B step 3/3b')],product_changes=0))
    ns=dict(vars(F));ns['__file__']=__file__
    exec(compile(body,str(folder/'workload.py'),'exec'),ns)
    exec(compile(driver,str(folder/'driver.py'),'exec'),ns)
    ns['main'](ROOT/f'build/set-b-fifth-functional-{mode}-r2',mode)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['lambda']);a=ap.parse_args();main(a.mode)
