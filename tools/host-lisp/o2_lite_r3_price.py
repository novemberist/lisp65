#!/usr/bin/env python3
"""Measure r3 before Seed; never relax the 255-byte object gate or link."""
import argparse
import json
import os
from pathlib import Path
import bytecode_p0_stdlib as P
from o2_lite_r3_host import ROOT, project_editor, save


def measure(suite):
    h,n,c,*rest=P._compile_suite(suite,include_cases=False)
    return dict(bytes=sum(len(c[x].encode()) for x in n),objects=len(n),
                entries=[dict(name=x,bytes=len(c[x].encode()),payload=c[x].payload.hex(),
                              literals=[h.obj_to_text(v) for v in c[x].littab]) for x in n])


def planes(out, baseline_suite, candidate_suite):
    import c2_full_emission as F
    import c2_substitution_artifacts as SUB
    import c2_lite_v6_product_probe as V6
    base=ROOT/'build/strings-r7/seed/plane/candidate'
    frozen=json.loads((base/'product/substitution-artifacts.json').read_text())
    products={}
    for side,suite in [('baseline',baseline_suite),('candidate',candidate_suite)]:
        dest=out/side;dest.mkdir()
        sp=dest/'resident.json';save(sp,suite)
        P.emit_artifacts(str(sp),suite,str(dest/'stdlib-p0'),base_addr=0,artifact_role='stdlib')
        specs=tuple((key,'stdlib' if key=='stdlib-p0' else key,path) for key,path in zip(
            ('stdlib-p0','ide','idex','m65d','buffer','lcc'),
            [dest/'stdlib-p0.manifest.json']+[ROOT/r['path'] for r in frozen['manifests'][1:]],strict=True))
        SUB.BUILD,SUB.SPECS=dest/'product',specs
        products[side]=SUB.build();V6.PRODUCT_IDENTITY=SUB.BUILD/'substitution-artifacts.json'
        images=[F.emit_image(*spec) for spec in specs]
        V6.STATIC_CODE_BYTES=sum(len(i.code) for i in images)
        plane,geometry=V6.static_plane(images)
        data={'CODE.BIN':bytes(plane.code[:plane.code_low]),'C2D.BIN':bytes(plane.c2d),
              'SHELF.BIN':(SUB.BUILD/'product-shelf-v4-direct.bin').read_bytes()}
        for name,raw in data.items():
            (dest/name).write_bytes(raw)
            if side=='baseline':assert raw==(base/name).read_bytes(),name
    return dict(deltas={name:(out/'candidate'/name).stat().st_size-(out/'baseline'/name).stat().st_size for name in data},
                products=products,baseline_exact=True)


def main():
    assert os.environ.get('PYTHONDONTWRITEBYTECODE')=='1'
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--planes',action='store_true')
    args=parser.parse_args();args.out=args.out.resolve();args.out.mkdir(parents=True)
    baseline=ROOT/'build/strings-r7/seed/plane/candidate'
    manifest=json.loads((baseline/'stdlib-p0.manifest.json').read_text())
    suite=P._read_suite(manifest['suite'])
    editors=[x for x in suite['sources'] if '(defun %rl-dispatch ' in (ROOT/x).read_text()]
    assert len(editors)==1
    editor=args.out/'product-editor.lisp';editor.write_text(project_editor())
    candidate=dict(suite,sources=[str(editor) if x==editors[0] else x for x in suite['sources']],
                   functions=suite['functions']+['%rl-empty-backspace'])
    values={side:measure(s) for side,s in [('baseline',suite),('candidate',candidate)]}
    assert values['baseline']['bytes']==manifest['code_bytes']
    old={e['name']:e for e in values['baseline']['entries']}
    new={e['name']:e for e in values['candidate']['entries']}
    assert set(new)-set(old)=={'%rl-empty-backspace'} and not set(old)-set(new)
    changed=[name for name in old if old[name]!=new[name]]
    assert set(changed)=={'%rl-dispatch','%rl-end','%read-line-loop'},changed
    save(args.out/'resident.json',candidate)
    lib=P._read_suite(str(ROOT/'config/comfort-default-plane/libraries/repl-comfort-suite.json'))
    lib['resident_suite']=str(args.out/'resident.json')
    library=measure(lib)
    oversized=[dict(plane=plane,name=e['name'],bytes=e['bytes']) for plane,v in [('resident',values['candidate']),('library',library)] for e in v['entries'] if e['bytes']>255]
    # Validate with the real artifact gate. No size override or invalid package.
    rejected=[]
    if library['bytes'] > 3000:
        rejected.append(dict(plane='library',error='library exceeds 3000 bytes'))
    for name,s in [('resident',candidate),('library',lib)]:
        try:
            h,n,c,*_=P._compile_suite(s,include_cases=False)
            P._validate_code_object_size_expectations(s,c)
        except P.StdlibCheckError as error:
            rejected.append(dict(plane=name,error=str(error)))
    plane=planes(args.out,suite,candidate) if args.planes and not rejected else None
    if not rejected:
        save(args.out/'library.json',lib)
        P.emit_artifacts(str(args.out/'library.json'),lib,str(args.out/'repl-comfort'),
                         base_addr=0,artifact_role='disk-lib')
    result=dict(status='HALT' if rejected else 'PASS',resident=values,
                resident_delta=values['candidate']['bytes']-values['baseline']['bytes'],
                changed_resident_objects=changed,library=library,library_baseline=1060,
                library_delta=library['bytes']-1060,oversized=oversized,rejected=rejected,
                static_plane_deltas=plane['deltas'] if plane else None,plane=plane,native_links=0,
                note='Preflight only. Native identity and Seed remain gated by the independent heap proof.')
    save(args.out/'price.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('resident','library')},indent=2))
    if rejected:raise SystemExit(2)


if __name__=='__main__':main()
