"""Strings library price and unchanged resident/IDE loader content; host only."""
import json,copy
from pathlib import Path
import strings_successor_20260928 as S
import bytecode_p0_stdlib as P
import v2_workbench_codemod as C
from v11_function_metadata_ide_exit_20260928 import idex_projection,projection_selftest
RECEIPT='config/strings-stdlib-artifacts-receipt-20260928.json'
HISTORY={'tools/host-lisp/stdlib_artifacts_walks_20260928.py': 'a7be13d3926b7ecc7caac1e3ef37b6c38592dfc23d5450ea52f895555aeb083f', 'config/walks-stdlib-artifacts-receipt-20260928.json': '589d33ec2a526ca1fc0b18d3e49e01c99db60668a08f47639f38bbf7226c047d'}
SUITE='config/comfort-default-plane/libraries/repl-comfort-suite.json'

def emit(path,prefix,role='stdlib'):
    suite=P._read_suite(str(path))
    P.emit_artifacts(str(path),suite,str(prefix),base_addr=0,artifact_role=role)
    manifest=json.loads(prefix.with_suffix('.manifest.json').read_bytes())
    blob=prefix.with_suffix('.blob.bin').read_bytes()
    projection_selftest(manifest,blob)
    return dict(code_bytes=manifest['code_bytes'],objects=manifest['objects'],
                functions=[e['name'] for e in manifest['entries']],
                loader_content=idex_projection(manifest,blob)),manifest

def derive():
    values={};emissions={}
    from contextlib import nullcontext
    for side in ('baseline','candidate'):
        dest=S.OUT/'artifacts'/side;dest.mkdir(parents=True,exist_ok=True)
        with S.predecessor_world() if side=='baseline' else nullcontext():
            library,manifest=emit(S.ROOT/SUITE,dest/'repl-comfort','disk-lib')
            C.generate(C.DEFAULT_CLOSURE,dest/'generated')
        invariant={}
        for name in ('p0-stdlib-einsuite-core-workbench-subset','p0-ide-core-lib','p0-ide-extra-lib'):
            row,_=emit(dest/'generated/suites'/(name+'.json'),dest/name)
            S.require('%sexp-line-state' not in row['functions'],'Comfort helper leaked to '+name)
            invariant[name]=row
        values[side]=dict(library=library,invariant=invariant)
        emissions[side]=manifest
    a,b=values['baseline'],values['candidate']
    S.require(a['invariant']==b['invariant'],'resident/IDE loader content changed')
    S.require(a['library']['code_bytes']==960 and b['library']['code_bytes']==1060,'library price drift')
    S.require(b['library']['code_bytes']<=1100,'library bound exceeded')
    S.require(b['library']['code_bytes']-a['library']['code_bytes']<=150,'aggregate growth exceeded')
    frozen=S.ROOT/'build/walks-product-r1/plane/candidate'
    plane={n:S.bind(frozen/n) for n in ('CODE.BIN','SHELF.BIN','C2D.BIN')}
    return dict(status='PASS',baseline=a,candidate=b,live=S.live(),library_bound=1100,
      plane=dict(delta={n:0 for n in plane},library_growth=100,total_growth=100,bound=150,price_status='PASS',
                 base=plane,comparison='same frozen six-image plane; separate disk library changes'),
      native_growth=0,loader_projection_mutations='pointer neutral; code/literals/patch corruption rejected')
if __name__=='__main__':
    S.finish('stdlib-artifacts',derive,RECEIPT,HISTORY,(__file__,SUITE,'tests/bytecode/libs/p0-repl-comfort-v250.json'))
