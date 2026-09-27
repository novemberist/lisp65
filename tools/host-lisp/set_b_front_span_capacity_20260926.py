"""Account every object delta and aligned record; halt before C if a gate fails."""
from pathlib import Path
from collections import defaultdict
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
from elf_truth import ElfTruth
from set_b_third_seed_inventory_halt_20260926 import price

ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-span-capacity-r1'
NATIVE=ROOT/'build/set-b-front-span-native-r1'

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
    checks=[]
    def gate(name,passed,actual,limit):
        checks.append(dict(name=name,pass_gate=bool(passed),actual=actual,limit=limit))
    for unit,section in (('c2_product_runtime.c','.lisp65_rt_c2append_entries'),
                         ('c2-stream-phase-05a.c','.lisp65_rt_c2d_05a')):
        gate('unchanged '+section,[unit,section] in r['unchanged_allocated_sections'],
            delta[section],0)
    gate('phase04 retained seed',delta['.lisp65_rt_c2d_04']==15,delta['.lisp65_rt_c2d_04'],15)
    gate('phase05b delta',delta['.lisp65_rt_c2d_05b']<=137,delta['.lisp65_rt_c2d_05b'],137)
    gate('ordinary helper plus drift',r['ordinary_text_delta']-726<=58,r['ordinary_text_delta']-726,58)
    previous=P.load(ROOT/'build/set-b-front-relocation-native-r1/receipt.json')
    old={(x['unit'],x['section']):x for x in previous['changes']
        if x['section']!='.lisp65_rt_c2d_05a'}
    allowed_new={('c2_product_runtime.c','.text.c2_front_pending_max'),
                 ('c2-stream-phase-05b.c','.lisp65_rt_c2d_05b')}
    unexpected=[]
    for x in r['changes']:
        key=x['unit'],x['section']
        if key in old:
            if x!=old[key]:unexpected.append(dict(before=old[key],after=x))
            del old[key]
        elif key not in allowed_new:unexpected.append(dict(after=x))
    unexpected.extend(dict(before=x) for x in old.values())
    gate('no unexplained owner drift',not unexpected,unexpected,[])
    elf=S.PRODUCT/'wplto/resident-island-seed.prg.elf'
    t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj');g=price(t)
    owners=[]
    for n,d in list(delta.items()):
        if n.startswith('.lisp65_rt_'):
            before=t.section(n).bytes;after=before+d
            owners.append(dict(section=n,before=before,delta=d,projected=after,air=1792-after))
            gate('overlay '+n,0<after<=1792,after,1792)
    mp=ROOT/'build/set-b-seed-medium-r6/media-seed/session-manifest.json';m=P.load(mp)
    align=lambda n:(n+31)//32*32
    packed=[];regions=[]
    for region,limit in ((0,65536),(1,2032),(2,1622),(3,8192)):
        records=sorted([x for x in m['slices'] if x['region_id']==region],key=lambda x:x['file_offset'])
        offset=records[0]['file_offset'];old_end=offset
        for x in records:
            assert x['file_offset']==align(old_end)
            size=(max(x['file_size'],align(t.section(x['section']).bytes+delta[x['section']]))
                  if region==3 else x['file_size']+delta[x['section']])
            gate('record '+str(x['id']),0<size<=1792,size,1792)
            packed.append(dict(region=region,slot=x['id'],section=x['section'],old_offset=x['file_offset'],
                new_offset=offset,old_size=x['file_size'],projected_size=size))
            old_end=x['file_offset']+x['file_size'];end=offset+size;offset=align(end)
        used=offset if region==3 else end
        regions.append(dict(region=region,before=align(old_end) if region==3 else old_end,
            projected_used=used,limit=limit,air=limit-used))
        gate('region '+str(region),used<=limit,used,limit)
    gate('region0 contract ceiling',regions[0]['projected_used']<=65205,regions[0]['projected_used'],65205)
    ledgers={}
    for name,amount,free,floor in (
        ('text',r['ordinary_text_delta'],g['text_free'],32),
        ('high_BSS',r['high_bss_delta'],g['high_bss_free'],5),
        ('E000',delta['.lisp65_c2_kernal_window.c2_resident'],g['e000_free'],54),
        ('capture',0,g['capture_free'],57)):
        ledgers[name]=dict(new=amount,air=free-amount,floor=floor,margin=free-amount-floor)
        gate(name+' floor',free-amount>=floor,free-amount,floor)
    P.write(OUT/'packing.json',dict(records=packed,regions=regions,catalog_count=len(m['slices']),new_slots=0,
        limits='Same-order all-record projection, correct retained late padding; no executable payload or CRC emitted.'))
    failures=[x for x in checks if not x['pass_gate']]
    status=('HALT AT CAPACITY GATE; NO C EXECUTION' if failures else
            'PASS MATCHED OBJECT AND ALIGNED PACKING PROJECTION; C QUALIFICATION MAY START')
    P.write(OUT/'receipt.json',dict(status=status,driver=P.bind(Path(__file__)),source_authority=authority,
        execution_head='09c7c983',native=P.bind(NATIVE/'receipt.json'),commands=P.bind(NATIVE/'commands.json'),
        manifest=P.bind(mp),elf=P.bind(elf),owners=owners,packing=P.bind(OUT/'packing.json'),regions=regions,
        checks=checks,failures=failures,unchanged_allocated_sections=len(r['unchanged_allocated_sections']),
        changed_allocated_sections=len(r['changes']),**ledgers,
        limits='Non-LTO matched deltas applied to fifth ELF; no linked layout, timing, stack or semantic acceptance.'))
    print(status)
    print('text',r['ordinary_text_delta'],'05b delta',delta['.lisp65_rt_c2d_05b'],'regions',regions)
    for failure in failures:print('FAILED',failure)

if __name__=='__main__':main()
