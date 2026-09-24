"""Exact cache state registration and independent linked ownership checks."""
from pathlib import Path
from elf_truth import ElfTruth

ROOT=Path(__file__).resolve().parents[2]
NAMES=('.lisp65_code_cache_row','.lisp65_code_cache_key')


def check(elf):
    t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    row,key=[t.section(n) for n in NAMES]
    frames=t.section('.lisp65_vm_soft_frames_bss');metadata=t.section('.lisp65_c2_symbol_metadata_bss')
    input_owner=t.section('.lisp65_c2_input_raw_owner')
    assert row.address==frames.address+frames.bytes and row.bytes==10
    assert key.address==metadata.address+metadata.bytes and key.bytes==2
    assert input_owner.address-(row.address+row.bytes)>=5
    assert 0xc000-(key.address+key.bytes)>=5
    assert t.symbol('__bss_end').value==key.address+key.bytes
    assert t.symbol('__bss_start').value<=row.address
    for s in (row,key):
        assert s.section_type=='SHT_NOBITS' and set(s.flags)=={'SHF_ALLOC','SHF_WRITE'}
    length=t.symbol('c2_product_entry_length');assert length.section=='.text'
    caller_rows=[r for r in t.relocations if r.target=='c2_product_entry_length']
    assert all('c2_kernal_window' not in r.source_section for r in caller_rows)
    return dict(status='PASS: EXACT CACHE OWNERS AND ORDINARY LENGTH WRAPPER',
                row_address=row.address,row_bytes=row.bytes,key_address=key.address,key_bytes=key.bytes,
                low_floor_remaining=input_owner.address-row.address-row.bytes,
                high_floor_remaining=0xc000-key.address-key.bytes,
                CRT_end=t.symbol('__bss_end').value,length_wrapper_bytes=length.bytes,
                length_callers=sorted({r.source_section for r in caller_rows}))


def configure(P):
    old=P.final_section_inventory_expectation
    if getattr(old,'_code_cache',False):return
    def inventory():
        result=old();names=list(result['names'])
        for name in NAMES:
            if name in names:raise ValueError('cache section already registered')
            names.insert(names.index('.llvm_sympart'),name)
        return {**result,'names':names,'code_cache_registration':list(NAMES)}
    inventory._code_cache=True
    P.final_section_inventory_expectation=inventory
    previous=P.final_section_inventory_check
    def gate(target):
        cache=check(Path(str(target)+'.elf'))
        result=previous(target);result['code_cache_ownership']=cache;return result
    P.final_section_inventory_check=gate
