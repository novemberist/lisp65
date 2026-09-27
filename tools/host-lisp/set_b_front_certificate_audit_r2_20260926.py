"""Correct audit r1's macro-provenance assumption; no compiler invocation."""
import inspect
from pathlib import Path
import set_b_front_certificate_audit_20260926 as O
import set_b_producer as P
ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-certificate-audit-r2'

def main():
    source=inspect.getsource(O.main)
    old="    assert '-DLISP_REAL_MEM' in vm\n"
    new="""    assert Path(vm[0]).name == 'mos-mega65-clang'
    assert '-D__MEGA65__' in (ROOT/'tools/llvm-mos/bin/mos-mega65.cfg').read_text().splitlines()
    assert '#if defined(__MEGA65__) || defined(__C64__) || defined(__CBM__)\\n#define LISP_REAL_MEM 1' in (ROOT/'src/vm.c').read_text()
"""
    assert source.count(old)==1;source=source.replace(old,new)
    folder=ROOT/'build/set-b-front-certificate-audit-driver-r2';folder.mkdir(exist_ok=False)
    (folder/'executed.py').write_text(source)
    P.write(folder/'binding.json',dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(O.__file__)),
        executed=P.bind(folder/'executed.py'),correction='LISP_REAL_MEM is defined in vm.c from the compiler target config; it is not a direct product -D flag.',
        target_config=P.bind(ROOT/'tools/llvm-mos/bin/mos-mega65.cfg')))
    rules=dict(O.SOURCE_RULES);rules['tools/llvm-mos/bin/mos-mega65.cfg']=r'__MEGA65__'
    ns=dict(vars(O));ns.update(OUT=OUT,SOURCE_RULES=rules,__file__=__file__)
    exec(compile(source,str(folder/'executed.py'),'exec'),ns);ns['main']()

if __name__=='__main__':main()
