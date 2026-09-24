"""Current Put-Kit successor constructor; preserves historical artifacts.

User instruction 2026-09-23 authorizes autonomous cache implementation and
qualification. command-probe creates reviewable commands only; seed requires
all locally SHA-bound preflight evidence and a previously unused output.
"""
import builtins
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import types

import put_kit_producer as PARENT
import code_object_cache_transform as CACHE
import code_object_cache_linker as LINKER

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'build/code-object-cache-card-r3'
BASE=ROOT/'build/put-kit-product-r4'
OUT=ROOT/'build/code-object-cache-product-r3-preflight'
BUILD=ROOT/'build/code-object-cache-product-r3'
AUTH='e2b7189b'


def bind(p):
    d=p.read_bytes();return dict(path=str(p.relative_to(ROOT)),bytes=len(d),sha256=hashlib.sha256(d).hexdigest())


def replace_function(raw,name,next_name,replacement):
    start=raw.index('def '+name+'(');end=raw.index('def '+next_name+'(',start)
    return raw[:start]+replacement+'\n\n'+raw[end:]


def successor(raw):
    changes={'build/put-kit-r4':'build/code-object-cache-card-r3',
             'build/put-kit-product-r4':'build/code-object-cache-product-r3',
             'build/boot-only-carrier-product-r1':'build/put-kit-product-r4',
             '3bd13625':AUTH,'e497ad71':AUTH,'put-kit-shared-boot-index':'code-object-cache'}
    raw=re.sub('|'.join(re.escape(k) for k in sorted(changes,key=len,reverse=True)),lambda m:changes[m[0]],raw)
    raw='import code_object_cache_transform as CACHE\nimport code_object_cache_linker as CACHE_LINKER\n'+raw
    raw=replace_function(raw,'source_gate','prepare_inputs', '''def source_gate():
    changed=set(subprocess.check_output(['git','diff','e2b7189b','--name-only',
        '--','src','lib'],cwd=ROOT,text=True).splitlines())
    if changed: raise ValueError('uncommissioned source population: '+repr(changed))
    comp=R.C.load(HERE/'composition.json')
    if comp['authority']!=AUTH: raise ValueError('cache authority drift')
    for row in comp['evidence']:
        if R.bind(ROOT/row['path'])!=row: raise ValueError('cache input drift: '+row['path'])
    return dict(status='PASS: CACHE GENERATED-RUNTIME SUCCESSOR, NOT NATIVE ACCEPTANCE',
        sources=[R.bind(ROOT/p) for p in comp['members']],
        composition=R.bind(HERE/'composition.json'),plane=R.bind(PLANE/'set-a-plane-receipt.json'))''')
    begin=raw.index('    # Preserve every consumed producer adaptation')
    end=raw.index('    derived,proof=identical_plane',begin)
    raw=raw[:begin]+'''    target=generated/'c2_product_runtime.c'
    text,inventory=CACHE.transform(target.read_text())
    target.write_text(text)
    (out/'cache-invalidation-inventory.json').write_bytes(R.C.canonical(inventory))
'''+raw[end:]
    # Establish complete predecessor identity before the only new linker fragment.
    needle='    for name in files:\n        target=out/name;'
    assert raw.count(needle)==1
    raw=raw.replace(needle,"    injected['full-map-linker/c.ld']=CACHE_LINKER.transform(injected['full-map-linker/c.ld'])\n"+needle,1)
    raw=raw.replace("        gate.expected['c2-substitution.ld']=injected['c2-substitution.ld']","        gate.expected.update(injected)")
    raw=raw.replace('PASS: COMPLETE FOUR-SCRIPT DERIVATION IDENTICAL TO THE CARRIER PREDECESSOR','PASS: COMPLETE PREDECESSOR IDENTITY BEFORE EXPLICIT SPLIT CACHE ALLOCATION')
    # This successor is a local, reviewable candidate, not a release. Keep
    # clean-tree admission and require each native-transform input to be
    # committed. Historical cards additionally required a remote push; that
    # publication prerequisite is not inherited by this local build lane.
    marker="if __name__=='__main__':"
    local_admission = r'''# Explicit local-candidate provenance successor.
probe_source=inspect.getsource(g['command_probe'])
remote_guard="""        if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT)!=subprocess.check_output(['git','rev-parse','@{upstream}'],cwd=ROOT):
            raise ValueError('Seed source commit must be remote-visible')"""
local_guard="""        for member in R.C.load(HERE/'composition.json')['members']:
            committed=subprocess.check_output(['git','show','HEAD:'+member],cwd=ROOT)
            if committed!=(ROOT/member).read_bytes():
                raise ValueError('local candidate input is not committed: '+member)
        (HERE/'local-source-admission.json').write_bytes(R.C.canonical(dict(
            status='PASS: CLEAN COMMITTED LOCAL CANDIDATE; NOT REMOTE PUBLICATION',
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            inputs=[R.bind(ROOT/member) for member in R.C.load(HERE/'composition.json')['members']])))"""
if probe_source.count(remote_guard)!=1: raise ValueError('remote provenance predecessor drift')
probe_source=probe_source.replace(remote_guard,local_guard,1)
exec(compile(probe_source,__file__,'exec'),g)

'''
    if raw.count(marker)!=1: raise ValueError('constructor entry point drift')
    raw=raw.replace(marker,local_admission+marker,1)
    return raw


def main():
    if sys.argv[1:] not in (['command-probe'],['seed']):raise SystemExit('command-probe | seed')
    if sys.argv[1:]==['seed']:
        admission=json.loads((HERE/'preflight-admission.json').read_text())
        assert admission['status']=='PASS' and admission['evidence']
        for row in admission['evidence']:assert bind(ROOT/row['path'])==row,row['path']
        assert not BUILD.exists(),'Seed output already exists; no implicit overwrite'
    captured=PARENT.capture();parent=PARENT.successor(captured['source'])
    assert parent==(ROOT/'build/put-kit-r4/expanded-constructor.py').read_text()
    raw=successor(parent);HERE.mkdir(parents=True,exist_ok=True)
    PARENT.write_once(HERE/'expanded-constructor.py',raw)
    members=['tools/host-lisp/code_object_cache_transform.py','tools/host-lisp/code_object_cache_linker.py','tools/host-lisp/code_object_cache_producer.py']
    paths=members+['build/code-object-cache-host-r4/receipt.json','build/code-object-cache-price-r5/receipt.json','build/code-object-cache-locality-lane-r4/locality.json']
    PARENT.write_once(HERE/'composition.json',json.dumps(dict(authority=AUTH,status='HOST QUALIFIED CACHE CANDIDATE',members=members,evidence=[bind(ROOT/p) for p in paths]),indent=2)+'\n')
    plane=ROOT/'build/put-kit-product-r4-preflight/setup-owned/static-plane/narrow-static/set-a-plane-receipt.json'
    PARENT.write_once(HERE/'plane.json',plane.read_text())
    if not (OUT/'setup-owned').exists():shutil.copytree(plane.parents[2],OUT/'setup-owned')
    inherited=captured['globals'];registration=inherited['slice_registration_receipt']
    registration=types.FunctionType(registration.__code__,{**registration.__globals__,'HERE':HERE},registration.__name__)
    index=inherited['INDEX_PRODUCER']
    ns=dict(__name__='__main__',__file__=__file__,INJECT_SLICES=index.inject_slice_sections,
            INJECT_SLICES_WIRING=index.WIRING,REGISTER_AND_ADMIT=inherited['register_and_admit'],SLICE_RECEIPT=registration)
    builtins.exec(builtins.compile(raw,str(HERE/'expanded-constructor.py'),'exec'),ns)

if __name__=='__main__':main()
