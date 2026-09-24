"""One profile-bound Final after exact-HEAD green source qualification."""
from pathlib import Path
import sys
import dirty_anchor_producer as P
ROOT=P.ROOT
H=ROOT/'build/dirty-anchor-final-r3'
write_once=P.CACHE.PARENT.write_once

def generate():
    H.mkdir(exist_ok=True)
    product='''from pathlib import Path
import builtins, types, sys
import dirty_anchor_producer as DRIVER
captured=[]
def capture(code, scope):
    assert scope['__name__']=='__main__'
    scope['__name__']='dirty_anchor_final_constructor'
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
    includes=(ROOT/'build/put-kit-r4/storage_final_includes.py').read_text().replace('put-kit','dirty-anchor')
    raw=(ROOT/'build/put-kit-r4/final-expanded-driver.py').read_text()
    changes={
        '519adbda67da5559d696cd7ea0d373ee73e2405c558cafe255384fc0f43607d5':'6aa3040c3f6533a94c053b7b64b932be15514d856dd05f675da771a1f1ea1811',
        'PASS: EXECUTED PUT-KIT SEED':'PASS: EXECUTED DIRTY-ANCHOR SEED',
        'config/put-kit-seed.json':'config/dirty-anchor-seed.json',
        'build/put-kit-source-qualification-r1/full-source-run.json':'build/dirty-anchor-source-qualification-r1/full-source-run.json',
        "authority='3bd13625'":"authority='e9ef6d57'",
        "out=F.WPLTO;seed=out/'resident-island-seed.prg'":"seed_out=F.WPLTO;out=H/'wplto';out.mkdir(exist_ok=True);seed=seed_out/'resident-island-seed.prg'",
        "dest.write_bytes((out/name).read_bytes())":"dest.write_bytes((seed_out/name).read_bytes())",
        "dest.read_bytes()==(out/name).read_bytes()":"dest.read_bytes()==(seed_out/name).read_bytes()",
        "old=out/'generated-product-sources'":"old=seed_out/'generated-product-sources'",
        "P.BOUND_SCRIPT_INCLUDE_DIRECTORY=out/'generated-product-sources'":"P.BOUND_SCRIPT_INCLUDE_DIRECTORY=seed_out/'generated-product-sources'",
    }
    for old,new in changes.items():
        assert old in raw,old;raw=raw.replace(old,new)
    raw=raw.replace("frozen=[bind", """# Artifact copies only: satisfy the inherited admission's local Seed paths.
for member in ('resident-island-seed.compiler-input-assert.h',
               'resident-island-seed.stdlib-input-assert.h', 'resident-island-seed.prg.elf'):
    source=seed_out/member; destination=out/member
    destination.parent.mkdir(parents=True,exist_ok=True)
    if not destination.exists(): destination.write_bytes(source.read_bytes())
    assert destination.read_bytes()==source.read_bytes()
frozen=[bind""")
    raw=raw.replace("    include_proof=FI.admit", """    # Rebind byte-identical derived headers to this isolated Final directory.
    seed_include=load(seed_out/'active-include-check/receipt.json')
    authority=list(seed_include['authority']); rebased=[]
    for row in seed_include['authority']:
        original=ROOT/row['path']
        if original.is_relative_to(seed_out):
            target=out/original.relative_to(seed_out)
            if target.is_file():
                assert target.read_bytes()==original.read_bytes(),str(target)
                rebased.append(dict(seed=bind(original),final=bind(target)))
                authority.append(bind(target))
    derived=dict(seed_include,authority=authority)
    include_path=out/'active-include-check/receipt.json'
    include_path.parent.mkdir(exist_ok=True)
    encoded=json.dumps(derived,indent=2)+'\\n'
    if include_path.exists(): assert include_path.read_text()==encoded
    else: include_path.write_text(encoded)
    projection=dict(seed=bind(seed_out/'active-include-check/receipt.json'),
        derived=bind(include_path),byteidentical_rebindings=rebased)
    if execute: assert load(H/'final-isolated-include-projection.json')==projection
    else: save('final-isolated-include-projection.json',projection)
    include_proof=FI.admit""")
    raw=raw.replace("save('final-attempt.json',", "save('final-attempt.json' if execute else 'preflight-attempt.json',")
    marker="qualification=load(ROOT/'config/dirty-anchor-seed.json')"
    raw=raw.replace(marker,"""plane_path=P.PRODUCT_ARTIFACTS_MANIFEST.parent.parent/'v6-semantics/bank2-static-code.bin'
plane_seed=load(ROOT/'build/dirty-anchor-card-r1/plane.json')['bank2']
assert sha(plane_path.read_bytes())==plane_seed['sha256']
"""+marker)
    raw=raw.replace("save('final-identity.json',dict(status=", "assert sha(plane_path.read_bytes())==plane_seed['sha256']\n    save('final-identity.json',dict(Bank2_seed=plane_seed,Bank2_final=bind(plane_path),status=")
    for name,text in (('product-card.py',product),('storage_final_includes.py',includes),('final-expanded-driver.py',raw)):
        write_once(H/name,text)

if __name__=='__main__':
    assert sys.argv[1:] in (['preflight'],['final'])
    generate();target=H/'final-expanded-driver.py'
    exec(compile(target.read_text(),str(target),'exec'),dict(__name__='__main__',__file__=str(target)))
