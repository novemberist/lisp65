"""Paired host stdlib emission for the Backspace source seam; no native build."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import backspace_successor_20260928 as B
import ide_exit_successor_20260928 as S
import v11_function_metadata_ide_exit_20260928 as M

ROOT = B.ROOT
OUT = ROOT / 'build/bytecode/dialect-v2/backspace-stdlib'
MANIFEST = ROOT / 'build/ide-exit-product-r2/plane/candidate/stdlib-p0.manifest.json'
RECEIPT = 'config/backspace-stdlib-artifacts-receipt-20260928.json'


def derive():
    B.source_proof()
    frozen = json.loads(MANIFEST.read_bytes())
    suite_path = Path(frozen['suite'])
    suite = json.loads(suite_path.read_bytes())
    sources = [Path(p) for p in suite['sources']]
    editor, = [p for p in sources if p.name == 'product-editor.lisp']
    old = editor.read_text()
    new = B.transform(old)
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
    S.require(M.idex_projection(a,ab)==M.idex_projection(frozen,fb),'IDE-exit stdlib baseline reproduction failed')
    changed=[]
    for x,y in zip(a['entries'],b['entries'],strict=True):
        S.require(x['name']==y['name'] and x['literals']==y['literals'],'stdlib literal/name drift')
        def code(m,blob,e):
            raw=bytearray(blob[e['blob_offset']:e['blob_offset']+e['length']])
            for patch in m['literal_patches']:
                at=patch['blob_offset']-e['blob_offset']
                if 0<=at<len(raw):raw[at:at+2]=b'\0\0'
            return bytes(raw)
        if code(a,ab,x)!=code(b,bb,y):changed.append(x['name'])
    S.require(changed==['%rl-cut'],'foreign stdlib executable change')
    S.require(len(bb)-len(ab)==-6,'expected ordinary bytecode delta -6')
    ah=(OUT/'baseline/stdlib-p0.h').read_text();bh=(OUT/'candidate/stdlib-p0.h').read_text()
    S.require(ah.replace(f'STDLIB_BLOB_BYTES {len(ab)}u',f'STDLIB_BLOB_BYTES {len(bb)}u').replace(str(OUT/'baseline/suite.json'),str(OUT/'candidate/suite.json'))==bh,'unclassified generated header change')
    return dict(changed_objects=changed,bytecode_delta=-6,
                loader_projection_mutations=8,
                before=M.idex_projection(a,ab),after=M.idex_projection(b,bb),
                header_before=S.bind(OUT/'baseline/stdlib-p0.h'),header_after=S.bind(OUT/'candidate/stdlib-p0.h'),
                inputs=[S.bind(p) for p in [MANIFEST,suite_path,*sources]],
                projected_editor_sha256=M.H.sha(new.encode()),
                native_price='unmeasured; no native commands',plane_price='unmeasured; no Seed')


if __name__=='__main__':
    B.finish('stdlib-artifacts',derive,RECEIPT,{'tools/host-lisp/bytecode_p0_stdlib.py': '39d91ab5d63232bfae13e19bffa45a280245239930e61c65f2073b36e3201528', 'tools/host-lisp/v11_function_metadata_ide_exit_20260928.py': '08507ee8618d1dbee687da370a8a2cd8b94f7226b87574b63258a3f2d717e5b0'},(__file__, M.__file__))
