#!/usr/bin/env python3
"""2.5.5: export a reviewable working-tree public projection without touching Git.

Successor of c2_v254_r1_public_source.py (immutable, 2.5.4 Final r1): 2.5.5 r1 export policy and the
2.5.5 (Final r1) stdlib-p0.h normalization, retaining every inherited normalization (the 2.5.4 r1 and the 2.5.3 r2
and r1 copies stay exported with the accumulated policy and so keep their normalization).

Uses the public export policy; includes untracked release successors because
this release is prepared with a read-only Git index. No build files or private
evidence are copied. Toolchain installation is a separate external input.
"""
import argparse
import ast
import re
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import public_export as E
import c2_v255_r1_public_normalization as Z
import c2_v254_r1_public_normalization as Z254
import c2_v253_r2_public_normalization as Z253R2
import c2_v253_r1_public_normalization as Z253R1
import c2_v252_r1_public_normalization as Z252
import c2_v251_r2_20260929_public_normalization as Z251

ROOT = Path(__file__).resolve().parents[2]

def materialize(destination):
    policy = E.load_policy(ROOT/'config/c2-v255-r1-public-export-policy.json')
    paths = subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT).decode().split('\0')
    selected = sorted({p for p in paths if p and E.matches(p,policy['include']) and not E.matches(p,policy['exclude'])})
    missing = set(policy['required'])-set(selected)
    if missing: raise ValueError('required source absent: '+repr(sorted(missing)))
    if destination.exists(): raise ValueError('projection must be fresh')
    rows=[]; conversions=[]
    for name in selected:
        raw=(ROOT/name).read_bytes()
        original=raw
        if name in Z.policy()["paths"]:
            raw=Z.normalize(raw)
            conversions.append(dict(path=name, before=Z.identity(original), after=Z.identity(raw), substitution=Z.policy()))
        if name in Z254.policy()["paths"]:
            raw=Z254.normalize(raw)
            conversions.append(dict(path=name, before=Z.identity(original), after=Z.identity(raw), substitution=Z254.policy()))
        if name in Z253R2.policy()["paths"]:
            raw=Z253R2.normalize(raw)
            conversions.append(dict(path=name, before=Z.identity(original), after=Z.identity(raw), substitution=Z253R2.policy()))
        if name in Z253R1.policy()["paths"]:
            raw=Z253R1.normalize(raw)
            conversions.append(dict(path=name, before=Z.identity(original), after=Z.identity(raw), substitution=Z253R1.policy()))
        if name in Z252.policy()["paths"]:
            raw=Z252.normalize(raw)
            conversions.append(dict(path=name, before=Z.identity(original), after=Z.identity(raw), substitution=Z252.policy()))
        if name in Z251.policy()["paths"]:
            raw=Z251.normalize(raw)
            conversions.append(dict(path=name, before=Z.identity(original), after=Z.identity(raw), substitution=Z251.policy()))
        import c2_v251_public_normalization as predecessor
        if name in predecessor.policy()['paths']:
            raw=predecessor.normalize(raw)
            conversions.append(dict(path=name,before=Z.identity(original),after=Z.identity(raw),substitution=predecessor.policy()))
        if name=="config/comfort-default-native/includes/stdlib-p0.h":
            import c2_v250_public_normalization as historical
            raw=historical.normalize(raw)
            conversions.append(dict(path=name, before=Z.identity(original), after=Z.identity(raw), substitution=historical.policy()))
        if E.PRIVATE_PATH_RE.search(raw):
            text=raw.decode()
            if name.endswith('.json'):
                def relative(v):
                    if isinstance(v,str): return v.replace(str(ROOT)+'/', '')
                    if isinstance(v,list): return [relative(x) for x in v]
                    if isinstance(v,dict): return {k:relative(x) for k,x in v.items()}
                    return v
                raw=(json.dumps(relative(json.loads(text)),indent=2,sort_keys=True)+'\n').encode()
            elif name.endswith('.py'):
                # Same diagnostic-home conversions as the 2.4.0 projection.
                text=re.sub(r"([\"'])"+re.escape(str(Path.home())+'/')+r"(\.local/share/xemu-lgb/mega65/(?:MEGA65\.ROM|mega65\.img))\1",
                            lambda m:'str(Path.home() / '+repr(m[2])+')',text)
                text=text.replace("Path("+repr(str(ROOT.parent/'lisp65-comfort-stack-seed-r1'))+")",
                                  "(ROOT.parent / 'lisp65-comfort-stack-seed-r1')")
                text=text.replace('Path('+repr(str(ROOT))+')', 'Path(__file__).resolve().parents[2]')
                ast.parse(text); raw=text.encode()
            conversions.append(dict(path=name,before=hashlib.sha256(original).hexdigest(),
                                    after=hashlib.sha256(raw).hexdigest()))
        errors=E.scan_data(name,raw,policy)
        if errors: raise ValueError(repr(errors))
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(raw);shutil.copymode(ROOT/name,target)
        rows.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    manifest=dict(format='lisp65-v255-working-tree-public-projection-v1',files=rows,
                  git_index_modified=False,private_build_inputs=False,path_conversions=conversions)
    (destination/'PUBLIC-SOURCE-MANIFEST.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print('PASS: public projection',len(rows),'files',destination)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('destination',type=Path)
    materialize(p.parse_args().destination.resolve())
