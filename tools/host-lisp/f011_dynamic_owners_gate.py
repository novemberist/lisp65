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
    # Synthetic CPU-space partitions, not a physical-load capacity claim.
    # The extent consumer now requires the initialized prefix as an owner too.
    for data_size in (12,15):
        data={'name':'.zp.data','vma':34,'bytes':data_size}
        bss={'name':'.zp.bss','vma':data['vma']+data['bytes'],
             'bytes':120-data['vma']-data['bytes']}
        zp={'allocatable_sections':[data,bss,
                {'name':'.zp','vma':120,'bytes':15},
                {'name':'.lisp65_c2_convergence_zp','vma':135,'bytes':2}],
            'boundary_symbols':{'__zp_data_start':data['vma'],
                '__zp_data_size':data['bytes'],
                '__zp_bss_start':bss['vma'],'__zp_bss_size':bss['bytes']}}
        assert V.candidate_zp_bss_successor(zp)['reserve_bytes']==0
        rejected.extend(str(data_size)+'-'+name for name in V.candidate_zp_bss_mutations(zp))
        missing={**zp,'allocatable_sections':zp['allocatable_sections'][1:]}
        try:V.candidate_zp_bss_successor(missing)
        except (KeyError,V.ConversionError):rejected.append(str(data_size)+'-missing-ZP-data-owner')
        else:raise AssertionError('incomplete ZP population accepted')
    print(json.dumps({'status':'PASS','rejected':rejected,'record_relation_mutations':3},indent=2))

if __name__=='__main__':main()
