"""Matched five-unit object inventory for the isolated checked-end reuse form."""
from pathlib import Path
import inspect
import traceback
import set_b_producer as P
import set_b_front_integration_native_20260926 as OLD
import set_b_front_end_20260926 as F
ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-end-native-r1'
UNITS=('c2_product_runtime.c','vm.c','c2-stream-phase-04.c','c2-stream-phase-05a.c','c2-stream-phase-05b.c')

def main():
    d=ROOT/'build/set-b-front-end-native-driver-r1';d.mkdir(exist_ok=False)
    source=inspect.getsource(OLD.main).replace('native_object_compiles=6,dependency_calls=6',
        'native_object_compiles=2*len(UNITS),dependency_calls=2*len(UNITS)')
    p=d/'executed.py';p.write_text(source)
    P.write(d/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(OLD.__file__)),executed=P.bind(p),
        transformation=P.bind(Path(F.__file__)),units=list(UNITS),
        scope='Rebind OUT and transformation I; ten matched objects and dependencies, no product link.'))
    ns=dict(vars(OLD),OUT=OUT,I=F,UNITS=UNITS,__file__=__file__)
    exec(compile(source,str(p),'exec'),ns);ns['main']()

if __name__=='__main__':
    try:main()
    except BaseException:
        if OUT.exists():(OUT/'failure.txt').write_text(traceback.format_exc())
        raise
