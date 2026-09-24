"""Put-Kit-only dirty-anchor constructor; derived data only, one Seed."""
from pathlib import Path
import builtins,json,shutil,subprocess,sys,types
import code_object_cache_producer as CACHE
import dirty_anchor_transform as ANCHOR
import bytecode_p0_stdlib as S
ROOT=CACHE.ROOT;HERE=ROOT/'build/dirty-anchor-card-r1';BASE=CACHE.BASE
OUT=ROOT/'build/dirty-anchor-product-r1-preflight';BUILD=ROOT/'build/dirty-anchor-product-r1';AUTH=CACHE.AUTH
bind=CACHE.bind

def successor(parent):
    # Reuse local-candidate provenance only. Undo all cache code/link changes.
    raw=CACHE.successor(parent)
    raw=raw.replace('import code_object_cache_transform as CACHE\nimport code_object_cache_linker as CACHE_LINKER\n','import dirty_anchor_transform as ANCHOR\n')
    raw=raw.replace("build/code-object-cache-card-r3", "build/dirty-anchor-card-r1").replace("build/code-object-cache-product-r3", "build/dirty-anchor-product-r1")
    start=raw.index("    target=generated/'c2_product_runtime.c'")
    end=raw.index('    derived,proof=identical_plane',start)
    raw=raw[:start]+raw[end:]
    raw=raw.replace("    injected['full-map-linker/c.ld']=CACHE_LINKER.transform(injected['full-map-linker/c.ld'])\n",'')
    raw=raw.replace('PASS: COMPLETE PREDECESSOR IDENTITY BEFORE EXPLICIT SPLIT CACHE ALLOCATION','PASS: FOUR LINKER SCRIPTS BYTE-IDENTICAL TO ACCEPTED PUT-KIT')
    raw=raw.replace("if changed: raise ValueError('uncommissioned source population: '+repr(changed))", "if changed!={'lib/stdlib-read-line.lisp'}: raise ValueError('uncommissioned source population: '+repr(changed))\n    ANCHOR.check_authored(ROOT, AUTH)")
    raw=raw.replace("plane=R.bind(PLANE/'set-a-plane-receipt.json')", "plane=R.bind(HERE/'plane.json')")
    raw=CACHE.replace_function(raw,'identical_plane','materialize', '''def identical_plane(generated,work):
    return R.W.DATA.derive(BASE_PREFLIGHT/'setup-owned/static-plane/narrow-static',
                          PLANE,generated,work,R.bind)''')
    raw=raw.replace("allowed=set(proof['changed_members'])|{'c2_product_runtime.c'}", "allowed=set(proof['changed_members'])")
    raw=raw.replace("CHANGED=('src/c2_product_runtime.c',)", "CHANGED=('lib/stdlib-read-line.lisp',)")
    raw=raw.replace("name='code-object-cache'", "name='input-dirty-anchor'")
    raw=raw.replace('PASS: CACHE GENERATED-RUNTIME SUCCESSOR, NOT NATIVE ACCEPTANCE','PASS: LISP-ONLY PUT-KIT ANCHOR, DERIVED DELIVERY DATA ONLY')
    return raw

def main():
    if sys.argv[1:] not in (['command-probe'],['seed']):raise SystemExit('command-probe | seed')
    if sys.argv[1:]==['seed']:
        admission=json.loads((HERE/'preflight-admission.json').read_text());assert admission['status']=='PASS'
        for row in admission['evidence']:assert bind(ROOT/row['path'])==row,row['path']
        assert not BUILD.exists(),'fresh Seed output required'
    ANCHOR.check_authored(ROOT,AUTH)
    original=ROOT/'build/ship-sample-card-r1/product-editor.lisp'
    projected=ROOT/'build/input-anchor-r2/product-editor.lisp'
    assert S.C.parse_all(ANCHOR.transform(original.read_text()))==S.C.parse_all(projected.read_text())
    captured=CACHE.PARENT.capture();parent=CACHE.PARENT.successor(captured['source'])
    assert parent==(ROOT/'build/put-kit-r4/expanded-constructor.py').read_text()
    raw=successor(parent);HERE.mkdir(parents=True,exist_ok=True)
    CACHE.PARENT.write_once(HERE/'expanded-constructor.py',raw)
    members=['lib/stdlib-read-line.lisp']+['tools/host-lisp/'+n+'.py' for n in ['dirty_anchor_transform','dirty_anchor_producer','code_object_cache_producer','put_kit_producer','plane_generated_data']]
    paths=members+['build/input-anchor-r2/'+n for n in ['receipt.json','matrix-r4.json','controls.json','timing.json','plane.json','data-derivation/receipt.json']]
    CACHE.PARENT.write_once(HERE/'composition.json',json.dumps(dict(authority=AUTH,status='HOST QUALIFIED REPL ANCHOR CANDIDATE',members=members,evidence=[bind(ROOT/p) for p in paths]),indent=2)+'\n')
    plane=ROOT/'build/input-anchor-r2/plane'
    CACHE.PARENT.write_once(HERE/'plane.json',(plane.parent/'plane.json').read_text())
    if not (OUT/'setup-owned').exists():
        shutil.copytree(ROOT/'build/put-kit-product-r4-preflight/setup-owned',OUT/'setup-owned')
        target=OUT/'setup-owned/static-plane/narrow-static';shutil.rmtree(target);shutil.copytree(plane,target)
    inherited=captured['globals'];registration=inherited['slice_registration_receipt']
    registration=types.FunctionType(registration.__code__,{**registration.__globals__,'HERE':HERE},registration.__name__)
    index=inherited['INDEX_PRODUCER']
    ns=dict(__name__='__main__',__file__=__file__,INJECT_SLICES=index.inject_slice_sections,INJECT_SLICES_WIRING=index.WIRING,REGISTER_AND_ADMIT=inherited['register_and_admit'],SLICE_RECEIPT=registration)
    builtins.exec(builtins.compile(raw,str(HERE/'expanded-constructor.py'),'exec'),ns)
if __name__=='__main__':main()
