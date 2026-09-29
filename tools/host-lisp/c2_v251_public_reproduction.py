#!/usr/bin/env python3
"""Public Comfort command replay successor; no private build/evidence inputs."""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import c2_v251_public_native as N
import c2_v251_public_normalization as Z
ROOT=N.ROOT
OUT=ROOT/'build/public-v2.5.1'
RECIPE=ROOT/'config/c2-v251-public-replay.json'
def save(p,v):p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def run(cmd):
    r=subprocess.run(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    N.require(r.returncode==0,'command failed: '+shlex.join(cmd)+'\n'+r.stdout.decode(errors='replace'))
    return r.stdout
def materialize(recipe):
    for row in recipe['inputs']:
        raw=N.bound(row['source'])
        if row['materialized_path'].startswith('tools/llvm-mos/'):continue
        if row['source']['path'] in Z.policy()['paths']:raw=Z.normalize(raw)
        target=N.local(row['materialized_path']);target.parent.mkdir(parents=True,exist_ok=True)
        N.require(not target.exists(),'replay destination exists: '+str(target))
        target.write_bytes(raw)
def include_check(recipe):
    allowed={str(N.local(r['materialized_path']).resolve()):Z.identity(N.local(r['materialized_path']).read_bytes()) for r in recipe['inputs']}
    for r in recipe['inputs']:
        if r['source']['path'].startswith('tools/llvm-mos/'):
            p=N.local(r['source']['path']);allowed[str(p.resolve())]=Z.identity(N.bound(r['source']))
    rows=[]
    for i,c in enumerate(recipe['commands'][:73]):
        src=c[c.index('-c')+1]
        if src.endswith('.s'):
            dirs=[ROOT]+[N.local(c[j+1]) for j,x in enumerate(c) if x=='-I'];pending=[N.local(src)];deps=set()
            while pending:
                p=pending.pop().resolve()
                if str(p) in deps:continue
                deps.add(str(p))
                for name in re.findall(r'^\s*\.include\s+"([^"]+)"',p.read_text(),re.M):
                    found=next((d/name for d in dirs if (d/name).is_file()),None)
                    N.require(found is not None,'assembler include absent: '+name);pending.append(found)
        else:
            cmd=list(c);at=cmd.index('-o');del cmd[at:at+2];cmd.remove('-c')
            output=run(cmd+['-E','-M','-MT','public-input'])
            deps={str((ROOT/p).resolve()) for p in shlex.split(output.decode().replace('\\\n',' ').split(':',1)[1])}
        for p in deps:
            N.require(p in allowed,'unbound compiler dependency: '+p)
            N.require(Z.identity(Path(p).read_bytes())==allowed[p],'compiler input drift: '+p)
        rows.append(dict(source=src,dependencies=sorted(deps)))
    save(OUT/'include-closure.json',dict(status='PASS',translation_units=len(rows),rows=rows))
def normalization_proof(recipe):
    # Preprocess the real repl TU twice at the SAME path, with the only
    # difference being the exact suite comment. Restore normalized bytes.
    p=Z.policy();targets=[N.local(r['materialized_path']) for r in recipe['inputs'] if r['source']['path'] in p['paths']]
    N.require(targets,'normalized compiler input absent')
    command=list(recipe['commands'][18]);at=command.index('-o');del command[at:at+2];command.remove('-c');command+=['-E','-P']
    normalized=run(command)
    saved={t:t.read_bytes() for t in targets}
    try:
        for t,raw in saved.items():
            original=raw.replace(p['new_line'].encode(),'/'.join(p['old_line_parts']).encode())
            N.require(Z.identity(original)==p['before'],'inverse substitution drift');t.write_bytes(original)
        original=run(command)
    finally:
        for t,raw in saved.items():t.write_bytes(raw)
    N.require(original==normalized,'normalization changes preprocessor tokens')
    result=dict(status='PASS',substitution=p,command=command,preprocessed=Z.identity(normalized),byteidentical=True,targets=[str(t.relative_to(ROOT)) for t in targets])
    save(OUT/'normalization-proof.json',result);return result

def build():
    N.require(not (ROOT/'build').exists(),'public reproduction requires no build directory')
    N.require((ROOT/'PUBLIC-SOURCE-MANIFEST.json').is_file(),'exported public source required')
    OUT.mkdir(parents=True)
    # Audit every child command, including commands in inherited media tools.
    def audit(event,args):
        if event=='subprocess.Popen':
            with (OUT/'commands.jsonl').open('a') as f:f.write(json.dumps(dict(executable=str(args[0]),argv=[str(x) for x in args[1]],cwd=str(args[2] or Path.cwd())))+'\n')
    sys.addaudithook(audit)
    state=dict(status='STARTED',source_manifest=Z.identity((ROOT/'PUBLIC-SOURCE-MANIFEST.json').read_bytes()),environment={k:os.environ.get(k) for k in ('PYTHONHASHSEED','LC_ALL','TZ')})
    try:
        N.check()
        import c2_v251_public_plane as plane
        state['plane']=plane.check()
        recipe=json.loads(RECIPE.read_text());materialize(recipe)
        state['normalization']=normalization_proof(recipe);include_check(recipe)
        for i,cmd in enumerate(recipe['commands']):
            N.local(cmd[cmd.index('-o')+1]).parent.mkdir(parents=True,exist_ok=True)
            (OUT/f'command-{i:03d}.log').write_bytes(run(cmd));state['commands_consumed']=i+1
        paths={role:ROOT/'build/backspace-final-r1/wplto'/Path(row['path']).name for role,row in recipe['raw_pair'].items()}
        state['native']={}
        for role,p in paths.items():
            got=Z.identity(p.read_bytes());N.require(got=={k:recipe['raw_pair'][role][k] for k in got},'HALT native mismatch: '+role)
            state['native'][role]=dict(path=str(p.relative_to(ROOT)),**got)
        save(OUT/'reproduction.json',state)
        import c2_v251_public_media as M
        state['media']=M.pack_public(paths)
        state['status']='PASS: PUBLIC SOURCE NATIVE AND MEDIA BYTEIDENTICAL'
    except BaseException as error:
        state.update(status='HALT',error=str(error));raise
    finally:save(OUT/'reproduction.json',state)
    return state

def check():
    state=json.loads((OUT/'reproduction.json').read_text());N.require(state['status'].startswith('PASS:'),'reproduction not passed')
    for r in [*state['native'].values(),state['media']]:N.bound(r)
    return state
if __name__=='__main__':print(json.dumps(build() if sys.argv[1]=='build' else check(),indent=2))
