"""Resume only the two unexecuted post-link gates on the immutable cache ELF.

The r3 link succeeded; exact-section registration rejected the two new cache
NOLOAD owners before the LTO-partition gate. No compiler or linker is called.
The failed invocation stays unchanged and is cited by a successor receipt.
"""
import json
import hashlib
import error_text_table as ERROR
from pathlib import Path
import runpy
import code_object_cache_producer as P
import code_object_cache_sections as S


def main():
    out=P.BUILD/'wplto';target=out/'resident-island-seed.prg'
    proof_path=out/'command-proof.json'
    assert not proof_path.exists(),'post-link continuation already recorded'
    invocation=json.loads((P.BUILD/'seed-invocation.json').read_text())
    assert invocation['status']=='HALT' and "additional=['.lisp65_code_cache_row', '.lisp65_code_cache_key']" in invocation['error']
    ready=json.loads((P.OUT/'command-ready.json').read_text());expected=json.loads((P.ROOT/ready['proof']['path']).read_text())
    assert invocation['commands_started']==len(expected['commands'])==75
    original={s:P.bind(Path(str(target)+s)) for s in ('','.elf','.lto.o','.map')}
    adapter=runpy.run_path(str(P.HERE/'seed-media.py'),run_name='cache_postlink_adapter')
    scope=adapter['configure']();scope['setup']();product=scope['g']['P']
    S.configure(product)
    product.final_section_inventory_gate(out,target)
    product.lto_partition_metadata_gate(out,target)
    assert original=={s:P.bind(Path(str(target)+s)) for s in original},'post-link gates changed native artifacts'
    old=expected['output'];new=str(out)
    def relocate(s):return s.replace(old,new).replace(str(Path(old).relative_to(P.ROOT)),str(out.relative_to(P.ROOT)))
    old_profile=(P.ROOT/expected['source_profile']['path']).read_bytes()
    new_profile=(out/'resolved-profile.txt').read_bytes()
    assert relocate(old_profile.decode()).encode()==new_profile
    old_id=hashlib.sha256(old_profile).hexdigest()[:8]
    new_id=hashlib.sha256(new_profile).hexdigest()[:8]
    proof=dict(expected)
    proof['output']=new;proof['commands']=[[relocate(a) for a in cmd] for cmd in expected['commands']]
    for field in ('source_files','headers'):
        rows=[]
        for r in expected[field]:
            p=P.ROOT/relocate(r['path']);b=P.bind(p)
            if field=='source_files':
                assert b['sha256']==r['sha256'],(field,r['path'])
            elif p.name=='error-text-table.h':
                table=ERROR.prepare_table(P.ROOT/'config/error-texts.json','workbench',int(new_id,16))
                assert p.read_bytes()==ERROR.render_header(table)
            else:
                before=(P.ROOT/r['path']).read_text()
                assert p.read_text()==before.replace('0x'+old_id+'UL','0x'+new_id+'UL')
            rows.append(b)
        proof[field]=rows
    for field in ('admission','source_profile'):
        proof[field]=P.bind(P.ROOT/relocate(expected[field]['path']))
    proof.update(status='SEED EMITTED; POST-LINK GATES RESUMED WITHOUT REBUILD; NATIVE QUALIFICATION PENDING',
                 compiler_invocations=73,link_invocations=1,postlink_successor=True)
    receipt=dict(status='PASS: EXISTING LINK POST-QUALIFIED; NO NATIVE REBUILD',
                 halted_invocation=P.bind(P.BUILD/'seed-invocation.json'),admitted_commands=ready['proof'],
                 original_artifacts=original,cache_ownership=S.check(Path(str(target)+'.elf')),
                 header_build_id_derivation=dict(before=old_id,after=new_id,rule='SHA256 of path-rebound profile; error header regenerated from unchanged workbench spec'),
                 gate_inputs=[P.bind(Path(ERROR.__file__)),P.bind(P.ROOT/'config/error-texts.json'),P.bind(Path(S.__file__)),P.bind(Path(__file__)),P.bind(P.HERE/'seed-media.py')],
                 remaining='artifact materialization, native behavior, latency and physical acceptance',
                 cumulative_native_attempts=dict(failed_link=1,successful_link=1,postlink_only_continuation=1))
    proof_path.write_text(json.dumps(proof,indent=2)+'\n')
    (P.HERE/'post-link-qualification.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'])
if __name__=='__main__':main()
