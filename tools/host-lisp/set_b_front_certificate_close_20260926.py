"""Bound the certificate design's owner envelopes; no code is compiled."""
from pathlib import Path
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
from elf_truth import ElfTruth

ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-certificate-close-r1'

def main():
    S.require_auth();OUT.mkdir(exist_ok=False)
    audit=ROOT/'build/set-b-front-certificate-audit-r2/receipt.json'
    model=ROOT/'build/set-b-front-certificate-model-r1/receipt.json'
    a=P.load(audit);m=P.load(model)
    assert a['linked_call_count']==53 and a['classified_owners']==44
    assert m['row_count']==324 and m['cold']['proposed_extra_full_scan_rows']==0
    elf=S.PRODUCT/'wplto/resident-island-seed.prg.elf'
    t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    owners=[]
    for section in ('.lisp65_rt_c2d_05b','.lisp65_rt_c2append_header',
                    '.lisp65_rt_c2append_journal_validate',
                    '.lisp65_rt_c2append_rollback_unpublish',
                    '.lisp65_rt_c2append_reserve_persistent_code'):
        sec=t.section(section)
        owners.append(dict(section=section,current=sec.bytes,limit=1792,air=1792-sec.bytes))
    assert [r['air'] for r in owners]==[137,258,828,1034,49]
    P.write(OUT/'owner-envelopes.json',owners)
    P.write(OUT/'receipt.json',dict(status='DESIGN COMPLETE; IMPLEMENTATION NOT ADMITTED UNTIL WRITER/REFILL/FAULT GATES ARE BOUND',
        driver=P.bind(Path(__file__)),authority=S.require_auth(),execution_head='5f9309fb',
        audit=P.bind(audit),model=P.bind(model),elf=P.bind(elf),owners=P.bind(OUT/'owner-envelopes.json'),
        linker=P.bind(ROOT/'config/set-b-native/linker/c2-substitution.ld'),
        preferred_storage=dict(new_high_BSS=3,projected_air=7,floor=5,
            pending='existing decoder entry_cursor field under a new phase-lifetime contract; never a recovery undo value'),
        code_envelope=dict(resident_available_above_floor=784,
            old_scalar_query_plus_VM_projection=687,remaining_if_that_fallback_is_kept=97,
            E000_available_above_floor=61,capture_available_above_floor=48,
            exact_new_code_cost=None,reason='Pure design commission: zero object compiles. Envelopes are not estimates of generated code.'),
        proposed_binding=dict(kind='Host-only certificate barrier/refill and object-admission prototype, subject to reviewer binding',
            product_builds=0,product_links=0,seeds=0,device_contacts=0,
            prerequisites=['Explicit raw poke/I/O writer policy and warm fault successor; no silent gate weakening',
                'No stale front after nonlocal recovery or failed publication',
                'Exact malformed input and BAD BYTECODE behavior; no READY clear or boot-abort path',
                'Cold scan elimination from real call trace, not just this model',
                'Native fallback lifetime and all owner prices before requesting a sixth Seed']),
        consumed=dict(seeds=5,finals=0,product_links=5),authorized_ceiling=dict(seeds=5,finals=1,product_links=5),
        new_product_budget_requested=False,this_commission=m['this_commission'],
        preserved_failed_audit='r1 assumed a command-line LISP_REAL_MEM definition; r2 binds the actual target cfg and source conditional. No product failure.',
        limitations='Direct-call census and Python design model only. Complete indirect/raw-writer mediation, actual hooks, target code costs, stack lifetime and warm failure equivalence remain open.'))
    print('CLOSED design: storage3 fits; phase05b137 and refill49 bytes air; no implementation or product attempt')

if __name__=='__main__':main()
