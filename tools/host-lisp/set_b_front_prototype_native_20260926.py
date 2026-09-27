"""Matched non-LTO object price of the isolated certificate kernel, no hooks."""
from pathlib import Path
import inspect
import set_b_producer as P
import set_b_front_prototype_20260926 as K
import set_b_load_preflight_native_r2_20260926 as N

ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-prototype-native-r1'

def main():
    driver=ROOT/'build/set-b-front-prototype-native-driver-r1'
    driver.mkdir(exist_ok=False)
    source=inspect.getsource(N.main)
    executed=driver/'executed-main.py';executed.write_text(source)
    assert (K.OUT/'certificate.inc').read_text()==K.HELPER
    P.write(driver/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(N.__file__)),
        executed=P.bind(executed),kernel=P.bind(K.OUT/'certificate.inc'),
        scope='Kernel and VM selector only. No lifecycle/raw-write hooks, decoder accumulator or actual cold trace.'))
    ns=dict(vars(N),OUT=OUT,HELPER=K.HELPER,__file__=__file__)
    exec(compile(source,str(executed),'exec'),ns)
    ns['main']()

if __name__=='__main__':main()
