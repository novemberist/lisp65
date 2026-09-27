"""Read-only writer/lifetime audit for a proposed charged-front certificate."""
from pathlib import Path
import re
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
from elf_truth import ElfTruth
from set_b_third_seed_inventory_halt_20260926 import instructions, price

ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-certificate-audit-r1'

# Classify every actual direct call/jump to the four native transport sinks.
# This census is deliberately not described as proof of all possible raw I/O.
CLASSES={
 'main':'boot-header-reset',
 'c2_stream_phase_07':'resolutions', 'c2_stream_phase_08':'resolutions',
 'c2_stream_phase_09':'roots', 'c2_stream_phase_10':'resolutions',
 'c2_stream_phase_11b':'roots', 'c2_stream_phase_10b':'resolutions',
 'c2_session_emit_literal_prep_phase':'emitter-root-scratch',
 'c2_append_journal_write_phase':'append-journal',
 'c2_append_stage_plane_phase':'unpublished-image-entry-resolution-root-spans',
 'c2_append_image_phase':'image-row',
 'c2_append_entries_phase':'persistent-or-high-transient-entry-rows',
 'c2tr_publish_plan_scan_body':'export-journal',
 'c2tr_publish_plan_resolve_body':'export-journal',
 'c2tr_header_body':'publication-header-and-context',
 'c2_append_publish_exports_phase':'export-journal',
 'c2_append_journal_clear_phase':'append-and-export-journal-clear',
 'c2_append_rollback_unpublish_phase':'rollback-header-and-context',
 'c2_append_rollback_zero_plane':'rollback-directory-spans',
 'c2_append_rollback_finalize_phase':'rollback-header',
 'vm_boot_overlay_chain_commit':'boot-bank0-copy',
 'sym_create':'symbol-owners-outside-directory',
 'symval_set':'symbol-values-after-C2D', 'symfn_ext_set':'symbol-functions-after-C2D',
 'v2_bnx_put':'boot-index-owner-outside-directory',
 'v2_bnx_post':'boot-index-owner-outside-directory',
 'vm_code_load':'physical-read-to-bank0',
 'vm_boot_overlay_chain_prepare':'boot-bank2-stage-before-READY',
 'rc_write':'retirement-journal', 'rm_write':'retirement-image-owner-and-journal',
 'rf_write':'retirement-image-count-and-journal', 'c2_retire_reset':'retirement-journal-reset',
 'c2_append_stage_copy_phase':'session-source-and-bank2-code',
 'c2_append_rollback_zero_chip_code':'bank2-code-wipe',
 'c2_boot_name_index_head_put':'boot-index-owner-outside-directory',
 'c2_stream_c2d_write':'bounded-C2D-write-facade',
 'c2_lite_stage_boot_family_impl':'boot-overlay-storage',
 'c2_phase02a_record_read':'physical-record-read-to-bank0',
 'c2_stream_phase_03b':'boot-bank2-code',
 'card_l_stage':'Bank5-tenants-outside-directory',
 'c2_lite_stage_session_family_impl':'session-overlay-storage',
 'c2_lite_stage_session_overflow':'session-overlay-storage',
 'c2_append_rollback_zero_attic':'session-source-wipe',
 'c2_facade_c2_dma':'DMA-facade-tail',
}

SOURCE_RULES={
 'src/c2_product_runtime.c':r'c2_stream_c2d_write\(|c2_runtime\s*=|entry_cursor|c2_ready\s*=|c2_product_physical_copy\(',
 'src/optional/set_b_retire_commit_a.c':r'rc_write\(|c2_facade_c2_dma|RMAGIC',
 'src/optional/set_b_retire_commit_b.c':r'rm_write\(|rm_own\(|c2_facade_c2_dma',
 'src/optional/set_b_retire_commit_c.c':r'rf_write\(|image_count|c2_facade_c2_dma',
 'src/optional/set_b_retire_reset.c':r'c2r_boot_count|c2_facade_c2_dma',
 'src/optional/set_b_retire_control.c':r'recovery|quiescent|gc_collect|C2D_UNWIND_BASE',
 'src/vm.c':r'case 62:|volatile unsigned char.*address|case 67:',
 'src/c2_platform_dma.c':r'void vm_ext_write|c2_facade_c2_dma|SYMVAL_EXT_OFF|SYMFN_EXT_OFF',
 'src/c2_session_emitter.c':r'C2E_ROOT_STATE|c2_stream_c2d_write',
 'src/c2_product_decoder.c':r'entry_cursor',
 'src/mem.h':r'EXT_BANK|EXT_OFF',
 'config/set-b-native/includes/c2-stream-decoder.c':r'entry_cursor|c2_stream_phase_05b|r16\(de|c2_stream_c2d_write',
 'config/set-b-native/includes/c2-stream-v2-decoder.c':r'c2_stream_c2d_write|c->finished|c2_facade_c2_dma',
 'config/set-b-native/includes/c2-stream-init.c':r'.',
 'config/set-b-native/includes/c2-stream-decoder.h':r'entry_cursor|entry_first|reserved|phase|uint16_t',
 'lib/stdlib-require.lisp':r'defun %require-fast|defun %require-world|synchronous|native write-population|state-advance',
 'lib/stdlib-read-line.lisp':r'\(poke ',
}


def main():
    auth=S.require_auth();OUT.mkdir(exist_ok=False)
    authority=ROOT/'build/set-b-r1/step4-r6/closure-r1/compiler-inputs.json'
    inputs=P.load(authority);assert inputs['status']=='PASS' and inputs['root_count']==74
    roots=[row['after'] for row in inputs['roots']]
    for row in roots+inputs['sources']:
        assert P.bind(ROOT/row['path'])==row,row['path']
    elf=S.PRODUCT/'wplto/resident-island-seed.prg.elf'
    t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    decoded,command,raw=instructions(elf)
    endpoints={name:t.symbol(name).value for name in (
        'c2_stream_c2d_write','c2_facade_c2_dma','c2_product_physical_copy','c2_facade_target_c2_dma')}
    calls=[];used=set()
    for section,by in decoded.items():
        for pc,row in by.items():
            bs=bytes.fromhex(row['bytes'])
            if row['mnemonic'] not in ('jsr','jmp') or len(bs)!=3:
                continue
            target=next((n for n,v in endpoints.items() if int.from_bytes(bs[1:],'little')==v),None)
            if target is None:
                continue
            owners=[s.name for s in t.symbols if s.symbol_type=='Function' and s.section==section and s.value<=pc<s.value+s.bytes]
            if target=='c2_facade_target_c2_dma':
                assert pc==t.symbol('c2_facade_c2_dma').value
                owners=['c2_facade_c2_dma']
            assert len(owners)==1,(section,pc,owners)
            owner=owners[0];assert owner in CLASSES,owner;used.add(owner)
            calls.append(dict(section=section,pc=pc,instruction=row,target=target,
                              owner=owner,classification=CLASSES[owner]))
    assert used==set(CLASSES),set(CLASSES)-used
    P.write(OUT/'linked-sink-calls.json',calls)
    snippets=[]
    for name,pattern in SOURCE_RULES.items():
        path=ROOT/name;lines=path.read_text().splitlines()
        hits=[]
        for i,line in enumerate(lines):
            if re.search(pattern,line):
                hits.append(dict(line=i+1,text=line,context=lines[max(0,i-2):i+3]))
        assert hits,name
        snippets.append(dict(source=P.bind(path),hits=hits))
    P.write(OUT/'source-witnesses.json',snippets)
    runtime=(ROOT/'src/c2_product_runtime.c').read_text()
    assert 'w->append.entry_cursor = c2_runtime.entry_cursor;' in runtime
    assert 'c2_runtime = *w->before;' in runtime
    assert 'c2_runtime = w->append;' in runtime
    assert 'while(n--){if(!rm_write(c2_runtime.entries_offset+e*10u,&owner,1u))return 0;++e;}' in (ROOT/'src/optional/set_b_retire_commit_b.c').read_text()
    commands=P.load(S.PRODUCT/'commands.json')
    vm=next(c for c in commands if '-c' in c and c[c.index('-c')+1].endswith('/vm.c'))
    assert '-DLISP_REAL_MEM' in vm
    g=price(t);assert (g['high_bss_free'],g['text_free'])==(10,816)
    P.write(OUT/'receipt.json',dict(status='PASS: DIRECT WRITER CENSUS AND CERTIFICATE DESIGN CONSTRAINTS; RAW-WRITE CLOSURE OPEN',
        driver=P.bind(Path(__file__)),source_authority=auth,execution_head='5f9309fb',elf=P.bind(elf),
        compiler_authority=P.bind(authority),root_count=len(roots),roots=roots,authority_sources=inputs['sources'],
        linked_calls=P.bind(OUT/'linked-sink-calls.json'),linked_call_count=len(calls),
        classified_owners=len(used),unclassified_direct_sink_calls=0,
        witnesses=P.bind(OUT/'source-witnesses.json'),source_bindings=[r['source'] for r in snippets],
        raw_store=dict(primitive=62,real_memory_enabled=True,scope='Arbitrary 16-bit volatile CPU store; no directory/certificate invalidation hook. CPU/I/O behavior must be accounted for, not assumed away.'),
        recovery_hazard='Journal reconstruction copies current entry_cursor into the reconstructed predecessor. Reusing it as front requires invalidation and refill; it is not an old-front undo record.',
        geometry=dict(high_bss_free=10,high_bss_floor=5,new_BSS_available=5,text_free=816,text_floor=32,new_text_available=784),
        no_product_change=True,product_builds=0,product_links=0,seeds=0,device_contacts=0,
        scope='All decoded direct JSR/JMP to the four named linked sinks classified, 74 root hashes verified. This is not an exhaustive indirect/raw-I/O or arbitrary-memory-corruption proof. No compiler/preprocessor/guest executed.'))
    print('PASS',len(calls),'direct sink calls;',len(used),'owners; 74 roots; raw-store and recovery obligations explicit')


if __name__=='__main__':main()
