"""Two reduced parser fixtures; no product link, source mutation or retry."""
import difflib
from pathlib import Path
import subprocess
import set_b_producer as P
OUT=P.ROOT/'build/set-b-r1/step4-r2/link-syntax-attribution'

def main():
    OUT.mkdir(exist_ok=False)
    obj=P.ROOT/'build/set-b-product-r1/wplto/.canonical-objects-resident-island-seed/048-mega65_math.s.o'
    linker=P.ROOT/'tools/llvm-mos/bin/ld.lld'
    rows=[]
    for label,ending in [('with-semicolon',';'),('without-semicolon','')]:
        script=OUT/(label+'.ld');script.write_text('SECTIONS {\n ASSERT(1, "same predicate")'+ending+'\n}\n')
        cmd=[str(linker),'-r','-T',str(script),str(obj),'-o',str(OUT/(label+'.o'))]
        result=subprocess.run(cmd,capture_output=True,text=True,cwd=P.ROOT)
        log=OUT/(label+'.log');log.write_text(result.stdout+result.stderr)
        rows.append(dict(label=label,command=cmd,exit_code=result.returncode,script=P.bind(script),log=P.bind(log)))
    assert rows[0]['exit_code']!=0 and rows[1]['exit_code']==0
    assert 'malformed number: }' in (OUT/'with-semicolon.log').read_text()
    path=P.ROOT/'config/set-b-native/linker/full-map-linker/c.ld'
    old=path.read_text();line='ASSERT(__set_b_journal_start == 0x5de20 && __set_b_journal_end == 0x5de68, "Set B 72-byte journal owner");'
    assert old.count(line)==1
    new=old.replace(line,line[:-1],1)
    patch=OUT/'proposed-correction.patch';rel=str(path.relative_to(P.ROOT))
    patch.write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+rel,tofile='b/'+rel)))
    P.write(OUT/'receipt.json',dict(status='PASS: LINK-SCRIPT SYNTAX CAUSE REPRODUCED IN ISOLATION',
        driver=P.bind(Path(__file__)),linker=P.bind(linker),input_object=P.bind(obj),rows=rows,
        bound_script=P.bind(path),proposal=P.bind(patch),proposal_applied=False,
        product_link_invocations=0,seed_invocations=0,synthetic_relocatable_linker_invocations=2,
        result='Trailing semicolon on ASSERT inside SECTIONS produces malformed number at closing brace. Removing only that semicolon admits the identical predicate.'))
    print('PASS: reduced failing/control parser fixtures; correction staged as patch only')
if __name__=='__main__':main()
