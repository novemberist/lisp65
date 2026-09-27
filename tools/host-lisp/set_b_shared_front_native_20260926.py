"""Price shared-scanner wrapper with matched non-LTO full-unit objects."""
from pathlib import Path
import inspect
import set_b_producer as P
import set_b_shared_front_20260926 as K
import set_b_load_preflight_native_r2_20260926 as N
ROOT=P.ROOT
OUT=ROOT/'build/set-b-shared-front-native-r1'

def main():
    driver=ROOT/'build/set-b-shared-front-native-driver-r1';driver.mkdir(exist_ok=False)
    source=inspect.getsource(N.main);p=driver/'executed-main.py';p.write_text(source)
    assert (K.OUT/'certificate.inc').read_text()==K.HELPER
    P.write(driver/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(N.__file__)),
        executed=P.bind(p),kernel=P.bind(K.OUT/'certificate.inc'),
        scope='Shared scanner request, resident wrapper and VM selector; no actual hooks or decoder accumulator.'))
    ns=dict(vars(N),OUT=OUT,HELPER=K.HELPER,__file__=__file__)
    exec(compile(source,str(p),'exec'),ns);ns['main']()

if __name__=='__main__':main()
