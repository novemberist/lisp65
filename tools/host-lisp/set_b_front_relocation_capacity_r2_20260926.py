"""Respect existing authenticated padding of the seven late records."""
from pathlib import Path
import inspect
import set_b_producer as P
import set_b_front_relocation_capacity_20260926 as OLD
ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-relocation-capacity-r2'

def main():
    d=ROOT/'build/set-b-front-relocation-capacity-driver-r2';d.mkdir(exist_ok=False)
    source=inspect.getsource(OLD.main)
    old="            size=x['file_size']+delta[x['section']]"
    new="""            size=(max(x['file_size'],align(t.section(x['section']).bytes+delta[x['section']]))
                  if region==3 else x['file_size']+delta[x['section']])"""
    assert source.count(old)==1;source=source.replace(old,new)
    p=d/'executed.py';p.write_text(source)
    P.write(d/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(OLD.__file__)),executed=P.bind(p),
        correction='r1 applied payload delta to already padded late record, double-counting slack. Region3 retains old record extent unless aligned actual payload projection grows beyond it. Other regions remain unchanged. r1 traceback retained.'))
    ns=dict(vars(OLD),OUT=OUT,__file__=__file__)
    exec(compile(source,str(p),'exec'),ns);ns['main']()

if __name__=='__main__':main()
