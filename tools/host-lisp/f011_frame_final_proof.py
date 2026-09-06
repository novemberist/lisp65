#!/usr/bin/env python3
"""Read-only owner, boot reset, abort survival and mapped-closure proof."""
import json
import f011_frame_diagnostic_card as D
import f011_status_final_proof as F
import c2_bank2_composed_ownership as BANK
from elf_truth import ElfTruth
from evidence_era import stable_recorded_on


def run():
    D.configure();D.C.configure=D.configure
    before=[D.C.bind(D.ELF),D.C.bind(D.PRG)]
    t=ElfTruth.read(D.ELF,llvm_readobj=D.C.B.READOBJ,include_section_data=True)
    old=ElfTruth.read(D.OLD['ELF'],llvm_readobj=D.C.B.READOBJ)
    state=t.symbol('lisp65_f011_status_state');owner=t.section(state.section)
    bss=t.section('.bss'); raw=t.section('.lisp65_c2_input_raw_owner')
    assert state.bytes==owner.bytes==7 and owner.section_type=='SHT_NOBITS'
    assert state.value==owner.address==bss.address+bss.bytes
    gap=raw.address-owner.address-owner.bytes
    text=t.section('.text');facade=t.section('.lisp65_c2_mapped_far_facade')
    text_gap=facade.address-text.address-text.bytes
    assert gap>=5 and text_gap>=32
    cold=t.section('.lisp65_c2_mapped_f011_cold');far=t.section('.lisp65_c2_mapped_far_service')
    assert cold.address>=0x6000 and cold.address+cold.bytes==far.address
    for s in old.sections:
        if s.name.startswith('.lisp65_c2_kernal_window.') or s.name in (
            '.lisp65_c2_fixed_zp','.lisp65_c2_fixed_bank0_hot_bss',
            '.lisp65_c2_terminal_return_raw_owner','.lisp65_c2_input_raw_owner',
            '.lisp65_c2_symbol_metadata_bss'):
            n=t.section(s.name); assert (s.address,s.bytes)==(n.address,n.bytes),s.name
    D.C.PREVIOUS.R2.ELF=D.ELF
    e000=D.C.PREVIOUS.R2.e000_capture_gate()
    graph=F.F011.R2.NESTING.linked_graph(D.ELF)
    assert 'f011_frame_publish' in graph['tenants']
    paths=F.F011.R2.NESTING.paths_to_map(graph,graph['tenants']);assert not paths
    mutant=F.F011.R2.NESTING.paths_to_map(graph,['f011_frame_publish'],
             injected_edges={'f011_frame_publish':{'lisp_abort_code'}})
    assert mutant
    mapped=tuple((n,'__lisp65_c2_'+n.removeprefix('.lisp65_c2_')) for n in (
        '.lisp65_c2_mapped_f011_cold','.lisp65_c2_mapped_far_service','.lisp65_c2_mapped_product_cold'))
    bank=BANK.derive(elf=D.ELF,plane=D.PLANE/'v6-semantics/bank2-static-code.bin',
        readobj=D.C.B.READOBJ,mapped_owners=mapped,placement_policy='map-page-top-derived',
        expected_vmas={n:t.section(n).address for n,_ in mapped})
    assert not bank['overlaps']
    out=D.BUILD/'final-proof.json'
    value={'role':'DIAGNOSTIC-EVIDENCE-ONLY','recorded_on':stable_recorded_on(out),
       'pair':before,'text_reserve':text_gap,'record_reserve':gap,
       'record_owner':{'address':state.value,'bytes':7},'cold_bytes':cold.bytes,
       'E000':e000,'bank2':bank,'boot_tag_reset':F.boot_reset(t),
       'abort_survival':F.survival(t,7,'f011_frame_publish'),
       'ordinary_error_edges':F.error_edges(t),'nesting_paths':paths,
       'in_body_abort_mutation':mutant,'status':'PASS',
       'device_and_DWX_claim':False}
    assert before==[D.C.bind(D.ELF),D.C.bind(D.PRG)]
    out.write_text(json.dumps(value,indent=2)+'\n')
    print('FINAL OWNER/RESET/SURVIVAL/NESTING PASS',text_gap,gap,state.value)

if __name__=='__main__':run()
