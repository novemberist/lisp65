#!/usr/bin/env python3
"""Record/check two independent public Comfort reproductions and exact Final bytes."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import c2_v251_r2_20260929_public_native as N
import c2_v251_r2_20260929_public_normalization as Z
ROOT=N.ROOT
RECEIPT=ROOT/'config/c2-v251-r2-20260929-reproductions.json'
PRODUCERS=['tools/host-lisp/c2_v251_r2_20260929_public_'+n+'.py' for n in
           ('product','native','source','normalization','reproduction','media','media_reproduction','libraries','plane')]
PRODUCERS += ['tools/host-lisp/strings_seed_producer.py']
CONFIGS=['config/c2-v251-r2-20260929-public-'+n+'.json' for n in
         ('replay','normalization','json-normalization','media-reproduction','export-policy','build-authority','media')]+['config/c2-v251-r2-20260929-public-plane/inputs.json']
CONFIGS += ['config/c2-v250-public-media.json']
def bind(p):return dict(path=str(p.relative_to(ROOT)),**Z.identity(p.read_bytes()))
def expected():
    rows=json.loads(N.AUTHORITY.read_text())['raw_pair']
    rows['D81']=json.loads((ROOT/'config/c2-v251-r2-20260929-public-media.json').read_text())['medium']
    return {k:{field:v[field] for field in ('bytes','sha256')} for k,v in rows.items()}
def validate(v):
    N.require(v['status']=='PASS' and len(v['reproductions'])==2,'two successful reproductions required')
    reps=v['reproductions'];N.require(reps[0]['root']!=reps[1]['root'],'independent absolute roots required')
    N.require(reps[0]['source_manifest']['sha256']==reps[1]['source_manifest']['sha256'],'source exports differ')
    N.require({r['path'] for r in v['producer_bindings']}==set(PRODUCERS+CONFIGS),'producer binding population drift')
    for row in v['producer_bindings']:N.bound(row)
    N.bound(v['toolchain_manifest'])
    final_rows=json.loads(N.AUTHORITY.read_text())['raw_pair']
    final_rows['D81']=json.loads((ROOT/'config/c2-v251-r2-20260929-public-media.json').read_text())['medium']
    for r in reps:
        N.bound(r['source_manifest']);N.bound(r['commands']);N.bound(r['normalization']);N.bound(r['include_closure'])
        N.require(r['commands_consumed']==75,'incomplete public replay')
        proof=json.loads(N.bound(r['normalization']));N.require(proof['byteidentical'] and proof['status']=='PASS' and proof['substitution']==Z.policy(),'normalization not proven')
        closure=json.loads(N.bound(r['include_closure']));N.require(closure['status']=='PASS' and closure['translation_units']==73,'include closure incomplete')
        N.require(set(r['artifacts'])==set(expected()),'artifact population drift')
        for role,row in r['artifacts'].items():
            raw=N.bound(row);N.require(Z.identity(raw)==expected()[role] and raw==N.bound(final_rows[role]),'Final mismatch: '+role)
    for role in expected():N.require(N.bound(reps[0]['artifacts'][role])==N.bound(reps[1]['artifacts'][role]),'reproductions differ: '+role)
    return dict(status='PASS',reproductions=2,artifacts=expected(),normalization='identical full repl preprocessor output',translation_units=73)
def record(roots):
    N.require(not RECEIPT.exists(),'receipt exists; explicit successor required')
    reps=[]
    for i,root in enumerate(roots,1):
        root=root.resolve();N.require(root!=ROOT and not root.is_relative_to(ROOT),'scratch root must be outside repository')
        out=root/'build/public-v2.5.1';state=json.loads((out/'reproduction.json').read_text())
        N.require(state['status']=='PASS: PUBLIC SOURCE NATIVE AND MEDIA BYTEIDENTICAL','nonqualifying build')
        dest=ROOT/f'build/release-v2.5.1/repro-r2-{i}';N.require(not dest.exists(),'retained run exists')
        shutil.copytree(out,dest/'public-result')
        shutil.copyfile(root/'PUBLIC-SOURCE-MANIFEST.json',dest/'PUBLIC-SOURCE-MANIFEST.json')
        artifacts={}
        for role,row in {**state['native'],'D81':state['media']}.items():
            source=root/row['path'];N.require(Z.identity(source.read_bytes())==expected()[role],'reproduced artifact differs')
            target=dest/(role+source.suffix);shutil.copyfile(source,target);artifacts[role]=bind(target)
        manifest=json.loads((root/'PUBLIC-SOURCE-MANIFEST.json').read_text());files={r['path']:r for r in manifest['files']}
        for name in PRODUCERS+CONFIGS:
            N.require(Z.identity((ROOT/name).read_bytes())=={k:files[name][k] for k in ('bytes','sha256')},'producer changed since export: '+name)
        reps.append(dict(root=str(root),environment=state['environment'],commands_consumed=state['commands_consumed'],
            artifacts=artifacts,source_manifest=bind(dest/'PUBLIC-SOURCE-MANIFEST.json'),
            commands=bind(dest/'public-result/commands.jsonl'),normalization=bind(dest/'public-result/normalization-proof.json'),
            include_closure=bind(dest/'public-result/include-closure.json')))
    result=dict(status='PASS',format='lisp65-v251-two-public-reproductions-v1',reproductions=reps,
        producer_bindings=[bind(ROOT/p) for p in PRODUCERS+CONFIGS],
        toolchain_manifest=bind(ROOT/'build/release-v2.5.1/reproduction-qualification-r2/toolchain.json'))
    N.require(Z.identity((ROOT/Z.policy()['path']).read_bytes())==Z.policy()['before'],'frozen source changed')
    validate(result);RECEIPT.write_bytes(N.canonical(result));return validate(result)
def selftest(v):
    validate(v);mutants=[]
    a=copy.deepcopy(v);a['reproductions'].pop();mutants.append(a)
    a=copy.deepcopy(v);a['reproductions'][1]['root']=a['reproductions'][0]['root'];mutants.append(a)
    a=copy.deepcopy(v);a['reproductions'][0]['artifacts']['ELF']['sha256']='0'*64;mutants.append(a)
    a=copy.deepcopy(v);a['reproductions'][0]['commands_consumed']=74;mutants.append(a)
    for a in mutants:
        try:validate(a)
        except ValueError:pass
        else:raise ValueError('reproduction mutation survived')
    return dict(status='PASS',mutations_rejected=len(mutants))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['record','check','selftest']);p.add_argument('--roots',nargs=2,type=Path);a=p.parse_args()
    if a.mode=='record':N.require(a.roots is not None,'two roots required');result=record(a.roots)
    else:
        v=json.loads(RECEIPT.read_text());result=selftest(v) if a.mode=='selftest' else validate(v)
    print(json.dumps(result,indent=2))
