"""Synthetic native linker controls for cache sizes, floors and CRT extent."""
import argparse,json,subprocess
from pathlib import Path
from code_object_cache_linker import ROW,KEY,transform
from elf_truth import ElfTruth
ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    base=(ROOT/'build/put-kit-product-r4/wplto/full-map-linker/c.ld').read_text();candidate=transform(base)
    assert candidate.replace('\n'+ROW,'',1).replace(KEY+'\n','',1)==base
    (a.out/'candidate-c.ld').write_text(candidate)
    rows=[]
    for name,rowbytes,keybytes,rowstart,keystart,okay in [
        ('good',10,2,0xbc81,0xbff6,True),('row-size',11,2,0xbc81,0xbff6,False),
        ('key-size',10,3,0xbc81,0xbff6,False),('low-floor',10,2,0xbc82,0xbff6,False),
        ('high-floor',10,2,0xbc81,0xbffa,False)]:
        d=a.out/name;d.mkdir();asm=d/'state.s';asm.write_text(f'.section .lisp65_code_cache_row,"aw",@nobits\n.space {rowbytes}\n.section .lisp65_code_cache_key,"aw",@nobits\n.space {keybytes}\n')
        obj=d/'state.o';subprocess.run([str(ROOT/'tools/llvm-mos/bin/mos-mega65-clang'),'-c',str(asm),'-o',str(obj)],check=True)
        ld=d/'state.ld';ld.write_text('MEMORY { c_writeable (rw) : ORIGIN = 0, LENGTH = 65536 }\nSECTIONS {\n'+f'__storage_soft_frames_end = {rowstart};\n__lisp65_c2_symbol_metadata_bss_end = {keystart};\n'+ROW+KEY+'\n.lisp65_c2_input_raw_owner 0xbc90 (NOLOAD) : { . += 112; } >c_writeable\n}\n')
        elf=d/'state.elf';r=subprocess.run([str(ROOT/'tools/llvm-mos/bin/ld.lld'),'-T',str(ld),str(obj),'-o',str(elf)],text=True,capture_output=True);(d/'link.log').write_text(r.stdout+r.stderr)
        assert (r.returncode==0)==okay,(name,r.stderr)
        if okay:
            e=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
            assert e.symbol('__bss_end').value==0xbff8
            assert e.section('.lisp65_code_cache_row').address==0xbc81
            assert e.section('.lisp65_code_cache_key').address==0xbff6
        rows.append(dict(name=name,expected_success=okay,returncode=r.returncode))
    (a.out/'receipt.json').write_text(json.dumps(dict(status='PASS: SYNTHETIC CACHE LINKER CONTROLS; NOT PRODUCT LINK',rows=rows),indent=2)+'\n');print('PASS cache linker: one positive, four negative controls')
if __name__=='__main__':main()
