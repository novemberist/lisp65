"""Use per-run receipt captures; the operator dump wrote its own captures.json."""
import inspect
from pathlib import Path
import set_b_fifth_halt_analysis_20260926 as A
import set_b_producer as P
import set_b_fifth_seed_20260926 as S

def main():
    src=inspect.getsource(A.main)
    old="captures=P.load(d/'captures.json')";new="captures=r['result']['captures']"
    assert src.count(old)==1;src=src.replace(old,new)
    folder=S.OUT/'workload-halt-analysis-r2';folder.mkdir(exist_ok=False)
    (folder/'executed.py').write_text(src)
    P.write(S.OUT/'workload-halt-analysis-r1/failure.json',dict(error='expected 54 run captures, standalone captures.json contains the one later operator halt dump',cause='G.dump publishes captures.json; all 54 original rows remain in run receipt.result.captures and all raw files remain',failed_driver=P.bind(Path(A.__file__)),no_product_failure=True))
    P.write(folder/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(A.__file__)),replacement=dict(before=old,after=new)))
    ns=dict(vars(A));ns.update(OUT=folder,__file__=__file__)
    src=src.replace('    OUT.mkdir(exist_ok=False)\n','')
    (folder/'executed.py').write_text(src)
    exec(compile(src,str(folder/'executed.py'),'exec'),ns);ns['main']()
if __name__=='__main__':main()
