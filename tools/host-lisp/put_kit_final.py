"""One profile-bound Final/link over the qualified Put-Kit Seed."""
from pathlib import Path
import sys
import put_kit_producer as P

ROOT=P.ROOT
H=P.HERE

def generate():
    product='''from pathlib import Path
import builtins, types, sys
import put_kit_producer as DRIVER
captured=[]
def capture(code, scope):
    assert scope['__name__']=='__main__'
    scope['__name__']='put_kit_final_constructor'
    builtins.exec(code,scope)
    captured.append(scope)
old,argv=DRIVER.builtins,sys.argv[:]
try:
    DRIVER.builtins=types.SimpleNamespace(exec=capture,compile=builtins.compile)
    sys.argv=[str(Path(DRIVER.__file__)),'command-probe']
    DRIVER.main()
finally:
    DRIVER.builtins=old
    sys.argv=argv
assert len(captured)==1
namespace=captured[0]
'''
    includes=(ROOT/'build/boot-only-carrier-r1/storage_final_includes.py').read_text().replace('boot-only-carrier','put-kit')
    raw=(ROOT/'build/transient-retirement-r2/final-expanded-driver.py').read_text()
    replacements={
        '7a8d8804c86d67cca6e08ee82070acb3b6ecd618946edaf5f0176aaa0ad4eeb8':'519adbda67da5559d696cd7ea0d373ee73e2405c558cafe255384fc0f43607d5',
        'PASS: ACCEPTED TRANSIENT FALLBACK SEED':'PASS: EXECUTED PUT-KIT SEED',
        "H/'qualification.json'":"ROOT/'config/put-kit-seed.json'",
        'build/transient-retirement-final-qualification-r2/full-source-run.json':'build/put-kit-source-qualification-r1/full-source-run.json',
        'final-preflight-r4.json':'final-preflight.json',
        "authority='4baffa77'":"authority='3bd13625'",
    }
    for old,new in replacements.items():
        assert old in raw,old
        raw=raw.replace(old,new)
    for name,text in (('product-card.py',product),('storage_final_includes.py',includes),('final-expanded-driver.py',raw)):
        P.write_once(H/name,text)

if __name__=='__main__':
    assert sys.argv[1:] in (['preflight'],['final'])
    generate()
    target=H/'final-expanded-driver.py'
    exec(compile(target.read_text(),str(target),'exec'),dict(__name__='__main__',__file__=str(target)))
