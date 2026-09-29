"""Paired walks Final/static and revised strings package emission; no link."""
import copy,json
from pathlib import Path
import strings_successor_r2_20260928 as S
import bytecode_p0_stdlib as P
from v11_function_metadata_ide_exit_20260928 import idex_projection,projection_selftest
RECEIPT='config/strings-stdlib-artifacts-receipt-r2-20260928.json'
FROZEN=S.ROOT/'build/walks-product-r1/plane/candidate'
HISTORY={'tools/host-lisp/stdlib_artifacts_strings_20260928.py': 'b2b2fe2383ed64133db2ece06ee899a5577f327286917f3f7f784e55fad4f50a', 'config/strings-stdlib-artifacts-receipt-20260928.json': 'b3eb80187aa70aad0b4a714abfda3e697c51fa34e1277ce224fad26deb3f3ddb'}

def emit_planes(out):
    import c2_full_emission as F
    import c2_substitution_artifacts as SUB
    import c2_lite_v6_product_probe as V6
    from contextlib import nullcontext
    frozen=json.loads((FROZEN/'product/substitution-artifacts.json').read_bytes())
    fm=json.loads((S.ROOT/frozen['manifests'][0]['path']).read_bytes())
    values={};artifacts=[]
    for side in ('baseline','candidate'):
        dest=out/side;dest.mkdir(parents=True,exist_ok=True)
        suite=P._read_suite(fm['suite'])
        editors=[p for p in suite['sources'] if '(defun %rl-end ' in (S.ROOT/p).read_text()]
        S.require(len(editors)==1,'resident editor population drift')
        editor=editors[0];old=(S.ROOT/editor).read_text()
        ep=dest/'product-editor.lisp';ep.write_text(S.project_editor(old) if side=='candidate' else old)
        suite['sources']=[str(ep) if p==editor else p for p in suite['sources']]
        sp=dest/'resident.json';sp.write_text(json.dumps(suite,indent=2)+'\n')
        P.emit_artifacts(str(sp),suite,str(dest/'stdlib-p0'),base_addr=0,artifact_role='stdlib')
        manifest=json.loads((dest/'stdlib-p0.manifest.json').read_bytes());blob=(dest/'stdlib-p0.blob.bin').read_bytes()
        projection_selftest(manifest,blob)
        paths=[dest/'stdlib-p0.manifest.json']+[S.ROOT/r['path'] for r in frozen['manifests'][1:]]
        specs=tuple((key,'stdlib' if key=='stdlib-p0' else key,path) for key,path in zip(('stdlib-p0','ide','idex','m65d','buffer','lcc'),paths,strict=True))
        SUB.BUILD,SUB.SPECS=dest/'product',specs
        product=SUB.build();V6.PRODUCT_IDENTITY=SUB.BUILD/'substitution-artifacts.json'
        images=[F.emit_image(*spec) for spec in specs];V6.STATIC_CODE_BYTES=sum(len(i.code) for i in images)
        plane,geometry=V6.static_plane(images)
        data={'CODE.BIN':bytes(plane.code[:plane.code_low]),'C2D.BIN':bytes(plane.c2d),'SHELF.BIN':(SUB.BUILD/'product-shelf-v4-direct.bin').read_bytes()}
        for n,raw in data.items():
            (dest/n).write_bytes(raw);artifacts.append(S.bind(dest/n))
            if side=='baseline':S.require(raw==(FROZEN/n).read_bytes(),'walks Final plane reproduction: '+n)
        libsuite=S.ROOT/'config/comfort-default-plane/libraries/repl-comfort-suite.json'
        with S.predecessor_world() if side=='baseline' else S.live_world():
            P.emit_artifacts(str(libsuite),P._read_suite(str(libsuite)),str(dest/'repl-comfort'),base_addr=0,artifact_role='disk-lib')
        lm=json.loads((dest/'repl-comfort.manifest.json').read_bytes());lb=(dest/'repl-comfort.blob.bin').read_bytes()
        library=dict(manifest=S.bind(dest/'repl-comfort.manifest.json'),blob=S.bind(dest/'repl-comfort.blob.bin'),code_bytes=len(lb),content=idex_projection(lm,lb))
        values[side]=dict(product=product,geometry=geometry,manifest=manifest,blob=blob,library=library)
        artifacts.extend(S.bind(dest/n) for n in ('stdlib-p0.manifest.json','stdlib-p0.blob.bin','repl-comfort.manifest.json','repl-comfort.blob.bin'))
    a,b=[values[x] for x in ('baseline','candidate')]
    S.require(idex_projection(a['manifest'],a['blob'])==idex_projection(fm,(S.ROOT/fm['blob']).read_bytes()),'resident baseline loader content')
    def code(m,blob,e):
        raw=bytearray(blob[e['blob_offset']:e['blob_offset']+e['length']])
        for patch in m['literal_patches']:
            at=patch['blob_offset']-e['blob_offset']
            if 0<=at<len(raw):raw[at:at+2]=bytes(2)
        return bytes(raw)
    changed=[]
    for x,y in zip(a['manifest']['entries'],b['manifest']['entries'],strict=True):
        S.require(x['name']==y['name'],'resident name drift')
        expected=([{'symbol':'nthcdr'}]+x['literals']) if x['name']=='%rl-end' else x['literals']
        S.require(y['literals']==expected,'foreign resident literals')
        if code(a['manifest'],a['blob'],x)!=code(b['manifest'],b['blob'],y):changed.append(x['name'])
    S.require(changed==['%rl-end'],'foreign resident code')
    S.require(len(b['blob'])-len(a['blob'])==48,'resident price drift')
    S.require([v['library']['code_bytes'] for v in (a,b)]==[960,1060],'library price drift')
    delta={n:(out/'candidate'/n).stat().st_size-(out/'baseline'/n).stat().st_size for n in data}
    S.require(delta=={'CODE.BIN':48,'C2D.BIN':0,'SHELF.BIN':56},'static plane price drift')
    result=dict(status='PASS',baseline_exact=True,changed_objects=changed,plane_deltas=delta,library_growth=100,total_growth=sum(delta.values())+100,bound=250,
        before_geometry=a['geometry'],after_geometry=b['geometry'],before_product=a['product'],after_product=b['product'],
        libraries={k:v['library'] for k,v in values.items()},artifacts=artifacts,bank2_static_capacity=60758,bank2_static_free_after=60758-b['geometry']['code_bytes'])
    S.require(result['bank2_static_free_after']>=0,'static owner capacity')
    result['price_status']='PASS' if result['total_growth']<=250 else 'HALT: aggregate exceeds +250'
    result['reviewer_decision']='2026-09-29: retain f31f79da; raise aggregate cap to +250 versus walks Final; measured +204; native growth bound remains zero.'
    result['expected_total_growth']=146
    result['expected_measurement_note']='The earlier +46 was resident bytecode in the v240 projection, not aggregate static plane growth against walks Final.'
    return result

def derive():
    result=emit_planes(S.OUT/'artifacts')
    return dict(status='PASS',emission=result,live=S.live(),plane=dict(delta=result['plane_deltas'],library_growth=result['library_growth'],total_growth=result['total_growth'],bound=250,price_status=result['price_status']))
if __name__=='__main__':
    S.finish('stdlib-artifacts-r2',derive,RECEIPT,HISTORY,(__file__,'config/comfort-default-plane/libraries/repl-comfort-suite.json'))
