"""Current command/include-closure replay for the complete cache runtime object."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

from boot_name_index_link_preprobe import compile_command_of
from code_object_cache_transform import transform
from elf_truth import ElfTruth

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'build/put-kit-product-r4/wplto'


def bind(p):
    d=p.read_bytes();return dict(path=str(p.relative_to(ROOT)),bytes=len(d),sha256=hashlib.sha256(d).hexdigest())


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    proof=json.loads((BASE/'command-proof.json').read_text())
    cmd=next(c for c in proof['commands'] if '-c' in c and c[c.index('-c')+1].endswith('c2_product_runtime.c'))
    flags,consumed,_=compile_command_of(cmd);original=(ROOT/consumed).resolve()
    closure=json.loads((BASE/'active-include-check/receipt.json').read_text())
    allowed={(ROOT/d['path']).resolve():d['sha256'] for row in closure['rows'] for d in row['dependencies']}
    candidate,inventory=transform(original.read_text());new=out/'c2_product_runtime.c';new.write_text(candidate)
    rows=[]
    for label,source in [('baseline',original),('candidate',new)]:
        quote=['-iquote',str(original.parent)]
        dep=subprocess.check_output([cmd[0],*flags,*quote,'-M','-MT','probe',str(source)],text=True)
        inputs=[]
        for name in shlex.split(dep.replace('\\\n',' ').split(':',1)[1]):
            path=(ROOT/name).resolve();row=bind(path)
            if path!=new: assert allowed.get(path)==row['sha256'],'unbound Include '+str(path)
            inputs.append(row)
        obj=out/(label+'.o');cc=[cmd[0],*flags,*quote,'-fno-lto','-c',str(source),'-o',str(obj)]
        r=subprocess.run(cc,text=True,capture_output=True);(out/(label+'.log')).write_text(r.stdout+r.stderr);r.check_returncode()
        e=ElfTruth.read(obj,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
        sections={s.name:s.bytes for s in e.sections if 'SHF_ALLOC' in s.flags}
        funcs={s.name:dict(bytes=s.bytes,section=s.section) for s in e.symbols if s.symbol_type=='Function' and s.bytes}
        rows.append(dict(variant=label,command=cc,inputs=inputs,object=bind(obj),sections=sections,functions=funcs))
    # Apart from the explicit TU replacement both compilations consume the same closure.
    assert {r['path']:r['sha256'] for r in rows[0]['inputs'] if r['path']!=str(original.relative_to(ROOT))}=={r['path']:r['sha256'] for r in rows[1]['inputs'] if r['path']!=str(new.relative_to(ROOT))}
    delta={s:rows[1]['sections'].get(s,0)-rows[0]['sections'].get(s,0) for s in set(rows[0]['sections'])|set(rows[1]['sections'])};delta={s:v for s,v in sorted(delta.items()) if v}
    result=dict(status='PASS: CURRENT INCLUDE-CLOSURE OBJECT PRICE; NOT LINKED PRICE',rows=rows,delta=delta,inventory=inventory,tool=bind(Path(__file__)),transform=bind(Path(__file__).with_name('code_object_cache_transform.py')))
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(delta,indent=2))

if __name__=='__main__':main()
