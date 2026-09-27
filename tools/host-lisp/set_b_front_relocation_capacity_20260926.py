"""Gate every matched object owner and aligned Session region before C rows."""
from pathlib import Path
from collections import defaultdict
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
from elf_truth import ElfTruth
from set_b_third_seed_inventory_halt_20260926 import price
ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-relocation-capacity-r1'
NATIVE=ROOT/'build/set-b-front-relocation-native-r1'

def main():
    authority=S.require_auth();OUT.mkdir(exist_ok=False)
    r=P.load(NATIVE/'receipt.json');commands=P.load(NATIVE/'commands.json')
    assert len(commands)==10 and r['native_object_compiles']==r['dependency_calls']==10
    for c in commands:
        assert c['exit']==c['dependencies']['exit']==0
        for d in c['dependencies']['inputs']:
            b=d['binding'];assert P.bind(ROOT/b['path'])==b
    delta=defaultdict(int)
    for x in r['changes']:delta[x['section']]+=x['delta']
    assert (delta['.lisp65_rt_c2d_04'],delta['.lisp65_rt_c2d_05a'])==(15,328)
    assert 0<=delta['.lisp65_rt_c2d_04']<=96 and 0<=delta['.lisp65_rt_c2d_05a']<=352
    assert ['c2_product_runtime.c','.lisp65_rt_c2append_entries'] in r['unchanged_allocated_sections']
    assert ['c2-stream-phase-05b.c','.lisp65_rt_c2d_05b'] in r['unchanged_allocated_sections']
    assert (r['ordinary_text_delta'],r['high_bss_delta'])==(726,4)
    assert delta['.lisp65_c2_kernal_window.c2_resident']==36
    allowed={'.lisp65_rt_c2d_04','.lisp65_rt_c2d_05a','.lisp65_rt_c2append_journal_reconstruct',
        '.lisp65_rt_c2append_retire_control','.lisp65_rt_c2append_retire_reset',
        '.lisp65_c2_kernal_window.c2_resident','.rodata.vm_callprim'}
    assert all(n in allowed or n.startswith(('.text.','.bss.c2_front_certificate.')) for n in delta)
    elf=S.PRODUCT/'wplto/resident-island-seed.prg.elf'
    t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj');g=price(t)
    owners=[]
    for n,d in delta.items():
        if n.startswith('.lisp65_rt_'):
            before=t.section(n).bytes;after=before+d
            assert 0<after<=1792
            owners.append(dict(section=n,before=before,delta=d,projected=after,air=1792-after))
    mp=ROOT/'build/set-b-seed-medium-r6/media-seed/session-manifest.json';m=P.load(mp)
    align=lambda n:(n+31)//32*32
    packed=[];regions=[]
    for region,limit in ((0,65536),(1,2032),(2,1622),(3,8192)):
        records=sorted([x for x in m['slices'] if x['region_id']==region],key=lambda x:x['file_offset'])
        offset=records[0]['file_offset'];old_end=offset
        for x in records:
            assert x['file_offset']==align(old_end)
            size=x['file_size']+delta[x['section']]
            assert 0<size<=1792
            packed.append(dict(region=region,slot=x['id'],section=x['section'],old_offset=x['file_offset'],
                new_offset=offset,old_size=x['file_size'],projected_size=size))
            old_end=x['file_offset']+x['file_size'];end=offset+size;offset=align(end)
        used=offset if region==3 else end
        assert used<=limit
        regions.append(dict(region=region,before=align(old_end) if region==3 else old_end,
            projected_used=used,limit=limit,air=limit-used))
    assert regions[0]['projected_used']==65397 and regions[0]['air']==139
    assert regions[3]['projected_used']==6784
    P.write(OUT/'packing.json',dict(records=packed,regions=regions,catalog_count=len(m['slices']),new_slots=0,
        limits='All-record same-order geometry only; original padding and region ownership retained. No executable payload, linked entry offsets or CRCs emitted.'))
    P.write(OUT/'receipt.json',dict(status='PASS MATCHED OBJECT AND ALIGNED PACKING PROJECTION; C QUALIFICATION MAY START',
        driver=P.bind(Path(__file__)),source_authority=authority,execution_head='775c4083',
        native=P.bind(NATIVE/'receipt.json'),commands=P.bind(NATIVE/'commands.json'),manifest=P.bind(mp),elf=P.bind(elf),
        owners=owners,packing=P.bind(OUT/'packing.json'),regions=regions,
        unchanged_allocated_sections=len(r['unchanged_allocated_sections']),changed_allocated_sections=len(r['changes']),
        text=dict(new=726,air=g['text_free']-726,floor=32,margin=g['text_free']-726-32),
        high_BSS=dict(new=4,air=g['high_bss_free']-4,floor=5,margin=g['high_bss_free']-4-5),
        E000=dict(new=36,air=g['e000_free']-36,floor=54,margin=g['e000_free']-36-54),
        capture=dict(new=0,air=g['capture_free'],floor=57),
        limits='Non-LTO deltas applied to fifth ELF; no whole-product linked-size, entry-offset, timing, stack or semantic acceptance.'))
    print('PASS 04+15/96,05a+328/352; Entries/05b unchanged; region0 65397/65536,139free; region3 6784/8192')

if __name__=='__main__':main()
