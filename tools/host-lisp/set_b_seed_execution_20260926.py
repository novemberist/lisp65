"""Invoke admitted Set B Seed exactly once; fresh previews, commissioned output."""
import inspect
import json
from pathlib import Path
import sys
import traceback
import set_b_producer as P
OUT=P.ROOT/'build/set-b-r1/step4-r2'

def main():
    assert not (OUT/'seed-invocation.json').exists(),'No implicit Seed retry'
    assert not (P.ROOT/'build/set-b-product-r1').exists(),'Seed output already exists'
    for rel in ['authority-admission.json','link-preprobe/receipt.json',
                'e000-preprobe/e000-low-edges-receipt.json','capacity-delivered/receipt.json']:
        assert P.load(OUT/rel)['status']=='PASS',rel
    ns=dict(vars(P));transforms=[]
    for name,old,new in [('command_probe',"out=HERE/'step3/command-preview'","out=ROOT/'build/set-b-r1/step4-r2/seed-command-preview'"),
                         ('seed',"out=HERE/'seed'","out=ROOT/'build/set-b-product-r1'")]:
        source=inspect.getsource(getattr(P,name));assert source.count(old)==1
        source=source.replace(old,new,1);path=OUT/(name+'-executed.py');path.write_text(source)
        exec(compile(source,str(path),'exec'),ns)
        transforms.append(dict(function=name,before=old,after=new,executed=P.bind(path)))
    P.write(OUT/'seed-invocation.json',dict(authority=P.require_auth(),
        driver=P.bind(Path(__file__)),producer=P.bind(Path(P.__file__)),transformations=transforms,
        output='build/set-b-product-r1',seed_invocations=1,retry=False,
        preflight=[P.bind(OUT/p) for p in ['preflight-result.json','capacity-delivered/receipt.json','late-capacity.json']]))
    try:ns['seed']()
    except Exception as e:
        P.write(OUT/'seed-result.json',dict(status='HALT',error=str(e),traceback=traceback.format_exc(),retry=False))
        raise
    P.write(OUT/'seed-result.json',dict(status='PASS: LINKED AND EXTRACTED; INVENTORY/MEDIA/GUEST GATES PENDING',retry=False))
if __name__=='__main__':main()
