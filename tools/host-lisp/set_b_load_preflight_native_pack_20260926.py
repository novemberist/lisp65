"""Canonical host packing of the parked native-query Lisp form."""
import inspect
from pathlib import Path
import set_b_load_preflight_pack_20260926 as O
import set_b_producer as P
ROOT=P.ROOT
OUT=ROOT/'build/set-b-load-preflight-native-pack-r1'
def main():
    source=inspect.getsource(O.main)
    for line in ["            suite['functions']+=['%require-charged-row-end','%require-charged-front']\n","            suite.setdefault('tailcall_self',[]).append('%require-charged-front')\n"]:
        assert source.count(line)==1;source=source.replace(line,'')
    folder=ROOT/'build/set-b-load-preflight-native-pack-driver-r1';folder.mkdir(exist_ok=False)
    (folder/'executed.py').write_text(source)
    ns=dict(vars(O));ns.update(OUT=OUT,CAND=ROOT/'build/set-b-load-preflight-native-r2/candidate/lib/stdlib-require.lisp',__file__=__file__)
    P.write(folder/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(O.__file__)),executed=P.bind(folder/'executed.py'),changes='Native-query Lisp file, no added helper objects; same canonical packing/identity checks'))
    exec(compile(source,str(folder/'executed.py'),'exec'),ns);ns['main']()
if __name__=='__main__':main()
