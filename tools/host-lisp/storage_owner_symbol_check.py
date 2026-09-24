"""Execute the product allocator at the manifest's new storage boundaries."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import symbol_layout_manifest as L

ROOT=Path(__file__).resolve().parents[2]
def bind(p):
    raw=p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def run(out):
    out.mkdir(parents=True,exist_ok=True)
    binary=out/'symbol-host'
    command=['cc','-std=c11','-O1','-Wall','-Wextra','-Werror','-ffunction-sections','-fdata-sections',
        '-fsanitize=address,undefined','-fno-omit-frame-pointer','-DLISP65_NUMERIC_ERRORS',
        '-DLISP65_NAMEOFF_EXT','-DLISP65_SYMVAL_EXT','-DLISP65_SYMFN_EXT','-DLISP65_SYMPOOL_EXT',
        '-Isrc',*['-D'+d for d in L.definitions()],
        'scripts/storage-owner-symbol-main.c','src/symbol.c','-Wl,--gc-sections','-o',str(binary)]
    built=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
    (out/'compile.log').write_text(built.stdout+built.stderr);built.check_returncode()
    rows=[]
    for case in ('slots','pool'):
        result=subprocess.run([str(binary),case],cwd=ROOT,text=True,capture_output=True,
            env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1'))
        (out/(case+'.log')).write_text(result.stdout+result.stderr)
        result.check_returncode();rows.append(dict(case=case,output=result.stdout,log=bind(out/(case+'.log'))))
    report=dict(status='PASS: product allocator at new symbol and name boundaries',
        inputs=[bind(ROOT/p) for p in ('src/symbol.c','src/symbol.h','src/obj.h','scripts/storage-owner-symbol-main.c')],
        manifest=bind(L.MANIFEST),compiler_command=command,binary=bind(binary),rows=rows,
        claim='Host allocator and physical-layout seam model, not native MAP/DMA or candidate headroom/timing evidence.',
        product_builds=0)
    from check_result_receipt import report as report_result
    report_result(out/'receipt.json', report)
    print(report['status'])
    for r in rows: print(r['output'],end='')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.output.resolve())
