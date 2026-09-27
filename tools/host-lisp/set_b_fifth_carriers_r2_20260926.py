"""Carrier suite successor: admit normal loader progress, preserve all gates."""
import inspect
from pathlib import Path
import set_b_fifth_carriers_20260926 as C
import set_b_fifth_oracle_r4_20260926 as O
import set_b_producer as P
import set_b_fifth_seed_20260926 as S

def main():
    assert O.selftest()==3
    src=inspect.getsource(C.main).replace("'-driver-r1'","'-driver-r2'").replace('functional-carriers-source-r1','functional-carriers-source-r2').replace('functional-carriers-r1','functional-carriers-r2')
    folder=S.OUT/'carriers-r2-driver';folder.mkdir(exist_ok=False);(folder/'executed.py').write_text(src)
    P.write(folder/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(C.__file__)),oracle=P.bind(Path(O.__file__))))
    ns=dict(vars(C));ns.update(O=O,__file__=__file__);exec(compile(src,str(folder/'executed.py'),'exec'),ns);ns['main']()
if __name__=='__main__':main()
