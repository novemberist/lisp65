"""Read-only scanner sharing audit. No compiler, new C, emulator or device."""
from dataclasses import asdict
from pathlib import Path
import re
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
from elf_truth import ElfTruth
from set_b_third_seed_inventory_halt_20260926 import instructions, price

ROOT=P.ROOT
OUT=ROOT/'build/set-b-scanner-reuse-audit-r1'
RULES={
 'src/c2_product_runtime.c':r'C2AW_FRONT_ENTRIES|C2AW_RESERVE_MARK|C2_RESERVE_SCAN_|c2_lite_bank2_scan|c2_append_reserve_persistent_code_phase|c2_overlay_call\(|c2_phase_scratch_(acquire|release)|C2_INSTALL_TRACE|record \+ (12|16)|vm_run_dir|vm_runtime_overlay_transaction_end|c2_runtime.entry_count|c2_runtime.entries_offset',
 'src/c2_phase_scratch.c':r'.',
 'src/c2_phase_scratch.h':r'304u|302|INSTALL_TRACE|PHASE_OWNER|non-reentrant|phase_scratch_(acquire|release)',
 'src/c2_product_runtime.h':r'RESERVE_PERSISTENT_CODE_SLOT|LITE_V6',
 'src/c2_bank2_code_domain.h':r'.',
 'src/vm_runtime_overlay.c':r'rtov_fail\(|rtov_fault =|rtov_busy|RTOV_CALL\(|entry_result|rtov_wipe\(|rtov_family_generation|RTOV_SOFT_SP\(|RTOV_TRANSACTION_ACTIVE',
 'src/c2_kernal_facade.s':r'overlay_call|vm_code_load',
 'config/set-b-native/includes/c2-stream-decoder.c':r'entries_offset|entry_count|generation|2096',
 'config/set-b-native/linker/c2-substitution.ld':r'reserve_persistent_code|runtime_overlay_limit',
}

def main():
    authority=S.require_auth();OUT.mkdir(exist_ok=False)
    old=ROOT/'build/set-b-r1/step4-r6/closure-r1/compiler-inputs.json'
    closure=P.load(old);assert closure['root_count']==74
    bindings=[r['after'] for r in closure['roots']]+closure['sources']
    for b in bindings:assert P.bind(ROOT/b['path'])==b,b['path']
    snippets=[]
    for name,pattern in RULES.items():
        p=ROOT/name;lines=p.read_text().splitlines();hits=[]
        for i,line in enumerate(lines):
            if re.search(pattern,line):hits.append(dict(line=i+1,text=line,context=lines[max(0,i-2):i+3]))
        assert hits,name
        snippets.append(dict(source=P.bind(p),hits=hits))
    P.write(OUT/'source-witnesses.json',snippets)
    elf=S.PRODUCT/'wplto/resident-island-seed.prg.elf'
    truth=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
    decoded,command,raw=instructions(elf);(OUT/'disassembly.txt').write_text(raw)
    names=['c2_lite_bank2_scan','c2_append_reserve_persistent_code_phase','c2_overlay_call',
           'c2_facade_target_overlay_call_family','vm_runtime_overlay_exec_family',
           'c2_stream_c2d_read','rtov_fail','lisp65_c2_phase_scratch']
    linked=[]
    for name in names:
        s=truth.symbol(name)
        rows=[r for pc,r in decoded.get(s.section,{}).items() if s.value<=pc<s.value+s.bytes]
        linked.append(dict(symbol=asdict(s),instructions=rows))
    scan=truth.symbol(names[0]);phase=truth.symbol(names[1]);scratch=truth.symbol('lisp65_c2_phase_scratch')
    assert (scan.value,scan.bytes,phase.value,phase.bytes)==(0xc497,1422,0xc356,321)
    assert (scratch.value,scratch.bytes)==(0xc0c6,304)
    section=truth.section(scan.section);assert section.bytes==1743
    def ins(name):return next(r['instructions'] for r in linked if r['symbol']['name']==name)
    calls=[r for r in ins(names[0]) if r['mnemonic']=='jsr']
    read=truth.symbol('c2_stream_c2d_read')
    assert len(calls)==2 and all(int.from_bytes(bytes.fromhex(r['bytes'])[1:],'little')==read.value for r in calls)
    entry=ins(names[1]);assert any(r['bytes']=='2097c4' for r in entry)
    stamp=next(r for r in entry if r['bytes']=='8ef4c1')
    assert next(r for r in entry if r['address']==stamp['address']-2)['bytes']=='a21d'
    # Bind exactly the linked data addresses; annotation labels at overlapping VMA are not authorities.
    assert stamp['address']==0xc368 and scratch.value+302==0xc1f4
    P.write(OUT/'linked-route.json',dict(owners=linked,scan_calls=calls,slot_stamp=stamp,
        session_slot=29,record_base=182,request_byte=202,transient_first_bytes=[184,185],
        output_bytes=list(range(194,202)),trace_byte=302,scanner_record_air=49,
        scratch_acquire_release='No standalone linked symbols after LTO; source ownership contract retained, no invented size.',
        limits='Existing instruction inventory only. No new wrapper or execution of scanner.'))
    obligations=[
      ['entry','Resident private query only; READY, certificate not BUSY; refuse without changing VM status.'],
      ['header','Actual header read; count<=2048; generation/count equal runtime context; runtime entries_offset==2096 before sharing scan.'],
      ['warm','Valid certificate may return after header check; raw-tainted state always refills. No eliminated read claimed executed.'],
      ['ownership','Acquire existing APPEND owner from NONE. Do not steal/release another owner and do not clear the whole scratch.'],
      ['provenance','Save prior LAST_SLOT (byte302) in resident local storage; preserve byte303 and attribution tail. Restore on every normal return.'],
      ['request','Write LE16 2048 to record+2 and 0x62 to record+20 only after acquisition. This skips all high transient rows.'],
      ['dispatch','Call existing c2_overlay_call(Session slot29,&c2aw) from resident code. Never call c2_lite_bank2_scan directly at its overlay VMA.'],
      ['transport','Require authenticated family/generation/record/payload, stack guard and successful post-entry wipe; never ignore transport false because scratch says DONE.'],
      ['result','Require marker0x64; copy validated low from record+12 into resident scalar before clearing marker/releasing scratch.'],
      ['cleanup','Restore provenance, clear request marker and release only owned scratch on success and failure. No publication before all checks/cleanup succeed.'],
      ['allocation','Release scratch before cons/GC; carry only scalar fixnum bytes, no pointer into overlay/scratch after release.'],
      ['abort','Existing nonlocal abort forcibly releases scratch; certificate invalidation and trace policy require their own integrated successor.'],
      ['latch','Transport failure may latch rtov_fault. Do not reset it or change READY to make a retry pass; explicit fault successor remains a gate.'],
      ['auth','Do not begin/end an unrelated transaction. Caller/auth-state proof is required; scratch-free alone does not prove auth quiescence.'],
    ]
    P.write(OUT/'required-protocol.json',obligations)
    old_price=P.load(ROOT/'build/set-b-front-prototype-close-r1/receipt.json')
    assert old_price['ordinary_text']['new_object_bytes']==892
    geometry=price(truth);assert geometry['text_free']==816
    P.write(OUT/'receipt.json',dict(status='READ-ONLY AUDIT COMPLETE: EXISTING SCAN REQUEST REUSABLE CONDITIONALLY; NO SPACE OR INTEGRATION ADMISSION',
        driver=P.bind(Path(__file__)),execution_head='5960ef83',authority=authority,
        compiler_authority=P.bind(old),verified_compiler_roots=74,compiler_inputs=bindings,
        elf=P.bind(elf),medium=P.bind(ROOT/'build/set-b-seed-medium-r6/media-seed/set-b-comfort.d81'),
        witnesses=P.bind(OUT/'source-witnesses.json'),route=P.bind(OUT/'linked-route.json'),protocol=P.bind(OUT/'required-protocol.json'),
        disassembly=dict(command=command,exit=0,output=P.bind(OUT/'disassembly.txt')),
        space=dict(existing_scan=1422,entry=321,record=1743,record_limit=1792,record_air=49,
            prior_query=764,prior_helpers=103,VM=25,ordinary_available=784,
            maximum_query_and_all_other_integration_if_helpers_unchanged=656,
            exact_new_wrapper_cost=None,minimum_net_reduction_before_other_integration=108,
            note='No compiler invoked. Sharing removes duplication in principle, not a measured 1422-byte or 764-byte saving.'),
        consumed=dict(seeds=5,finals=0,product_links=5),authorized_ceiling=dict(seeds=5,finals=1,product_links=5),
        this_commission=dict(compiler_calls=0,object_compiles=0,product_builds=0,product_links=0,seeds=0,guest_runs=0,device_contacts=0),
        next_proposal='Isolated host fixture of existing scan body and resident wrapper, matched object pricing only after explicit trace/latch/abort semantics; no product attempt.',
        limits='Source and exact linked-byte inspection; no new executed behavior, stack-high-water, cold-time or byte-saving claim. No product changes.'))
    print('PASS read-only audit: slot29 scanner1422 + entry321, air49; wrapper+integration envelope656; exact saving unmeasured')

if __name__=='__main__':main()
