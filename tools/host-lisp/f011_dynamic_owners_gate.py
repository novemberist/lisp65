#!/usr/bin/env python3
"""Permanent non-product regressions for emitted stack/record extents."""
from dataclasses import replace
import json
import c2_fixed_block_leaf_gate as F
import c2_v160_r1_stored_world_conversions as V


def main():
    fixture=F._full_map_fixture()
    for size in (3,6,12):
        sections=[replace(s,bytes=size) if s.name==F.OWNED_STACK_SECTION else s for s in fixture.sections]
        F.audit_truth(F.ElfTruth(sections=sections,symbols=fixture.symbols,relocations=fixture.relocations),
                      require_hot_bss=True,full_map_ownership=True)
    rejected=[]
    for size in (0,13):
        sections=[replace(s,bytes=size) if s.name==F.OWNED_STACK_SECTION else s for s in fixture.sections]
        try:
            F.audit_truth(F.ElfTruth(sections=sections,symbols=fixture.symbols,relocations=fixture.relocations),
                          require_hot_bss=True,full_map_ownership=True)
        except F.GateError:rejected.append('stack-size-'+str(size))
        else:raise AssertionError('out-of-envelope stack accepted')
    layout={'allocatable_sections':[{'name':'.bss','vma':0xB9CA,'bytes':531},
            {'name':'.lisp65_c2_input_raw_owner','vma':0xBC90,'bytes':112}]}
    for size in (3,7):
        row={'vma':0xBBDD,'bytes':size}
        result=V._after_ordinary_bss_proof('.noinit.lisp65_f011_status',row,layout,
                                          {'registration':{'record_bytes':size}})
        assert len(result['mutations_rejected'])==3
    for value in (None,False,0,-1,'7'):
        try:
            V._after_ordinary_bss_proof('.noinit.lisp65_f011_status',{'vma':0xBBDD,'bytes':7},layout,
                {'registration':{} if value is None else {'record_bytes':value}})
        except V.ConversionError:rejected.append('record-authority-'+repr(value))
        else:raise AssertionError('invalid record authority accepted')
    zp={'allocatable_sections':[
            {'name':'.zp.bss','vma':46,'bytes':74},
            {'name':'.zp','vma':120,'bytes':15},
            {'name':'.lisp65_c2_convergence_zp','vma':135,'bytes':2}],
        'boundary_symbols':{'__zp_bss_start':46,'__zp_bss_size':74}}
    assert V.candidate_zp_bss_successor(zp)['reserve_bytes']==0
    rejected.extend(V.candidate_zp_bss_mutations(zp))
    print(json.dumps({'status':'PASS','rejected':rejected,'record_relation_mutations':3},indent=2))

if __name__=='__main__':main()
