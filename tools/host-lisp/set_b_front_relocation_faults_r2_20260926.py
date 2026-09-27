"""Correct the fixture-only unsigned address comparison; retain strict warnings."""
from pathlib import Path
import inspect
import set_b_producer as P
import set_b_front_relocation_faults_20260926 as OLD
ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-relocation-faults-r2'

def main():
    d=ROOT/'build/set-b-front-relocation-fault-driver-r2';d.mkdir(exist_ok=False)
    source=inspect.getsource(OLD.main);p=d/'executed.py';p.write_text(source)
    pre=OLD.PRE.replace('at==meta+24?','at==(uint32_t)meta+24u?');assert pre!=OLD.PRE
    scaffold=d/'corrected-scaffold.c';scaffold.write_text(pre)
    P.write(d/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(OLD.__file__)),
        executed=P.bind(p),scaffold=P.bind(scaffold),correction='r1 host compile failed -Werror=sign-compare in fixture read-class address arithmetic. Cast fixture meta to uint32_t; extracted product functions unchanged, warnings remain errors.'))
    ns=dict(vars(OLD),OUT=OUT,PRE=pre,__file__=__file__)
    exec(compile(source,str(p),'exec'),ns);ns['main']()

if __name__=='__main__':main()
