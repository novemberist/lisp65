"""Seal a pre-Seed checkpoint; no acceptance or compilation is performed."""
from pathlib import Path
import argparse
import hashlib
import json
import shlex

ROOT=Path(__file__).resolve().parents[2]


def bind(path):
    path=path.resolve();raw=path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    target=ap.parse_args().out.resolve()
    if target.exists():raise ValueError('sealed checkpoint already exists')
    directories=[ROOT/p for p in ('build/definition-group-composition-r6',
        'build/definition-set-a-projection-r2','build/definition-group-capacity-r2')]
    composition,objects,capacity=[json.loads((p/'receipt.json').read_text()) for p in directories]
    assert composition['total_bank2_delta']==160
    assert composition['user_code_projection']['candidate']==8365
    assert composition['user_code_projection']['below_floor']==67
    assert all(r['exit']!=0 for r in capacity['rows'] if r['name']!='positive')
    assert capacity['source_sha256']==bind(ROOT/'src/c2_product_runtime.c')['sha256']
    paths=set()
    def consume(value):
        if isinstance(value,dict):
            if 'path' in value and 'sha256' in value:
                actual=bind(ROOT/value['path'])
                assert actual['sha256']==value['sha256'],value['path']
                if 'bytes' in value:assert actual['bytes']==value['bytes']
                paths.add(actual['path'])
            for v in value.values():consume(v)
        elif isinstance(value,list):
            for v in value:consume(v)
    for value in (composition,objects,capacity):consume(value)
    for directory in directories:
        for path in directory.rglob('*'):
            if path.is_file() and path.suffix in ('.json','.c','.h','.lisp','.bin','.o','.d','.log','.patch','.txt'):
                paths.add(str(path.relative_to(ROOT)))
                if path.suffix=='.d':
                    for name in shlex.split(path.read_text().replace('\\\n',' ').split(':',1)[1]):
                        paths.add(bind(ROOT/name)['path'])
    for name in ('lib/defstruct.lisp','lib/dialect-v2/eval-runtime.lisp',
        'src/c2_product_runtime.c','src/c2_product_runtime.h','src/c2_session_emitter.c',
        'tools/host-lisp/v2_workbench_codemod.py','tools/host-lisp/bytecode_p0_stdlib.py',
        'tools/host-lisp/bytecode_p0_compiler.py','tools/host-lisp/c2_full_emission.py',
        'tools/host-lisp/definition_set_a_projection.py',
        'tools/host-lisp/definition_group_capacity_probe.py',
        'tools/host-lisp/definition_group_composition.py',
        'tools/host-lisp/definition_set_a_seal.py',
        'docs/planning/definition-set-a-currency-preflight.md',
        'docs/planning/transient-retirement-final-report.md'):
        paths.add(name)
    result=dict(status='OWNER HOLD: USER-CODE FLOOR; NO SEED',
        authorities=['da42d6f5','91cbb479'],composition=composition,
        isolated_objects=objects,extracted_c_model=capacity,
        budget=dict(seed=0,final=0,product_link=0,device_contact=0),
        bindings=[bind(ROOT/p) for p in sorted(paths)])
    target.write_text(json.dumps(result,indent=2)+'\n')
    print('SEALED',len(paths),'inputs/artifacts; user-code projection 8365, manifest 8432; no Seed')


if __name__=='__main__':main()
