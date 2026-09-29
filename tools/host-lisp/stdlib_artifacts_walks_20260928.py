"""Paired host stdlib and six-image plane emission for editor walks; no native build."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import walks_successor_20260928 as B
import ide_exit_successor_20260928 as S
import v11_function_metadata_ide_exit_20260928 as M

ROOT = B.ROOT
OUT = ROOT / 'build/bytecode/dialect-v2/walks-stdlib'
MANIFEST = ROOT / 'build/backspace-product-r1/plane/candidate/stdlib-p0.manifest.json'
RECEIPT = 'config/walks-stdlib-artifacts-receipt-20260928.json'


def plane_projection():
    import c2_full_emission as F
    import c2_substitution_artifacts as SUB
    import c2_lite_v6_product_probe as V6
    frozen=json.loads((ROOT/'build/backspace-product-r1/plane/candidate/product/substitution-artifacts.json').read_bytes())
    rows=[]
    for side in ('baseline','candidate'):
        dest=OUT/side/'plane';dest.mkdir(exist_ok=True)
        paths=[OUT/side/'stdlib-p0.manifest.json']+[ROOT/r['path'] for r in frozen['manifests'][1:]]
        specs=tuple((key,'stdlib' if key=='stdlib-p0' else key,path) for key,path in zip(('stdlib-p0','ide','idex','m65d','buffer','lcc'),paths,strict=True))
        SUB.BUILD,SUB.SPECS=dest/'product',specs
        product=SUB.build();V6.PRODUCT_IDENTITY=SUB.BUILD/'substitution-artifacts.json'
        images=[F.emit_image(*spec) for spec in specs]
        V6.STATIC_CODE_BYTES=sum(len(i.code) for i in images)
        plane,geometry=V6.static_plane(images)
        data={'CODE.BIN':bytes(plane.code[:plane.code_low]),'C2D.BIN':bytes(plane.c2d),'SHELF.BIN':(SUB.BUILD/'product-shelf-v4-direct.bin').read_bytes()}
        for name,raw in data.items():
            (dest/name).write_bytes(raw)
            if side=='baseline':S.require(raw==(ROOT/'build/backspace-product-r1/plane/candidate'/name).read_bytes(),'frozen plane reproduction: '+name)
        rows.append(dict(files={name:dict(bytes=len(raw),sha256=M.H.sha(raw)) for name,raw in data.items()},geometry=geometry))
    delta={name:rows[1]['files'][name]['bytes']-rows[0]['files'][name]['bytes'] for name in rows[0]['files']}
    return dict(before=rows[0],after=rows[1],delta=delta,total_growth=sum(delta.values()),bound=400,price_status='PASS' if sum(delta.values())<=400 else 'HALT: PLANE BOUND EXCEEDED',native_price='not measured; no native commands')


def derive():
    B.source_proof()
    frozen = json.loads(MANIFEST.read_bytes())
    suite_path = Path(frozen['suite'])
    suite = json.loads(suite_path.read_bytes())
    sources = [Path(p) for p in suite['sources']]
    editor, = [p for p in sources if p.name == 'projected-product-editor.lisp']
    old = editor.read_text()
    new = B.transform(old)
    for bad in (old+old,old.replace('(defun %rl-cut ', '(defun foreign-cut ')):
        try:B.transform(bad)
        except ValueError:pass
        else:raise ValueError('product source mutation survived')
    from v2_workbench_codemod import _top_level_forms
    from bytecode_p0_stdlib import C
    def cut(text):
        return next(C.parse_one(text[a:b]) for a,b in _top_level_forms(text)
                    if text[a:b].startswith('(defun %rl-cut '))
    S.require(cut(new) == cut((ROOT / B.SOURCE).read_text()), 'product/authored cut mismatch')
    OUT.mkdir(parents=True, exist_ok=True)
    values=[]
    for side, text in [('baseline',old),('candidate',new)]:
        dest=OUT/side;dest.mkdir(exist_ok=True)
        (dest/'product-editor.lisp').write_text(text)
        value=copy.deepcopy(suite)
        value['sources']=[str(dest/'product-editor.lisp') if Path(p)==editor else p for p in value['sources']]
        (dest/'suite.json').write_text(json.dumps(value,indent=2)+'\n')
        command=['nice','-n','18','ionice','-c3',sys.executable,'-B',str(ROOT/'tools/host-lisp/bytecode_p0_stdlib.py'),'--check','--emit-artifacts',str(dest/'stdlib-p0'),str(dest/'suite.json')]
        with (dest/'emission.log').open('w') as log:
            subprocess.run(command,cwd=ROOT,check=True,stdout=log,stderr=subprocess.STDOUT)
        manifest=json.loads((dest/'stdlib-p0.manifest.json').read_bytes())
        blob=Path(manifest['blob']).read_bytes()
        M.projection_selftest(manifest,blob)
        values.append((manifest,blob))
    (a,ab),(b,bb)=values
    # Reproduction is loader content, never heap words overwritten at load.
    fb=Path(frozen['blob']).read_bytes()
    S.require(M.idex_projection(a,ab)==M.idex_projection(frozen,fb),'Backspace stdlib baseline reproduction failed')
    changed=[]
    for x,y in zip(a['entries'],b['entries'],strict=True):
        S.require(x['name']==y['name'],'stdlib name drift')
        if x['name'] not in (*B.SHARED,'%read-line-loop'):
            S.require(x['literals']==y['literals'],'foreign stdlib literal change')
        def code(m,blob,e):
            raw=bytearray(blob[e['blob_offset']:e['blob_offset']+e['length']])
            for patch in m['literal_patches']:
                at=patch['blob_offset']-e['blob_offset']
                if 0<=at<len(raw):raw[at:at+2]=b'\0\0'
            return bytes(raw)
        if code(a,ab,x)!=code(b,bb,y):changed.append(x['name'])
    S.require(set(changed)==set((*B.SHARED,'%read-line-loop')),'foreign stdlib executable change')
    S.require(0 < len(bb)-len(ab) <= 256,'ordinary bytecode bound exceeded')
    ah=(OUT/'baseline/stdlib-p0.h').read_text();bh=(OUT/'candidate/stdlib-p0.h').read_text()
    header=ah.replace(str(OUT/'baseline/suite.json'),str(OUT/'candidate/suite.json'))
    for macro,old_count,new_count in [('BLOB_BYTES',len(ab),len(bb)),
                          ('LITERAL_INDEX_COUNT',len(a['literal_index']),len(b['literal_index'])),
                          ('LITERAL_NODE_COUNT',len(a['literal_nodes']),len(b['literal_nodes'])),
                          ('LITERAL_PATCH_COUNT',len(a['literal_patches']),len(b['literal_patches']))]:
        header=header.replace(f'STDLIB_{macro} {old_count}u',f'STDLIB_{macro} {new_count}u')
    S.require(header==bh,'unclassified generated header change')
    return dict(changed_objects=changed,bytecode_delta=len(bb)-len(ab),plane=plane_projection(),
                loader_projection_mutations=8,product_projection_mutations=2,
                before=M.idex_projection(a,ab),after=M.idex_projection(b,bb),
                header_before=S.bind(OUT/'baseline/stdlib-p0.h'),header_after=S.bind(OUT/'candidate/stdlib-p0.h'),
                inputs=[S.bind(p) for p in [MANIFEST,suite_path,*sources]],
                projected_editor_sha256=M.H.sha(new.encode()),
                native_price='unmeasured; no native commands',plane_price='paired host six-image measurement; no Seed')


if __name__=='__main__':
    B.finish('stdlib-artifacts',derive,RECEIPT,{'tools/host-lisp/stdlib_artifacts_backspace_20260928.py': 'e2537745fc40df51629e060b7a06fed705c04ab9348eebba3671f9f2cdfe08f6', 'config/backspace-stdlib-artifacts-receipt-20260928.json': '37a5b0814547939a6789c97b14ecb2838064a6dd57469008fa0538e110ad5979'},(__file__, M.__file__))
