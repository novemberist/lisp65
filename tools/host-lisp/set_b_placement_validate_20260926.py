"""Host source/geometry/catalog checks for the placement revision; no guest run."""
import copy
import inspect
from pathlib import Path
import re
import struct
import subprocess
from elf_truth import ElfTruth
import runtime_overlay_bank as B
import set_b_producer as P
import set_b_seed_media as M

ROOT=P.ROOT
BASE=ROOT/'build/set-b-placement-r1'
OUT=BASE/'validation-r1'

def main():
    OUT.mkdir(exist_ok=False);checks=[]
    def checked(name):checks.append(dict(name=name,status='PASS'))
    try:P.require_auth()
    except ValueError as e:assert 'reviewer authority commit required' in str(e)
    else:raise AssertionError('Unadmitted Seed allowed')
    checked('Seed admission remains closed')
    source=inspect.getsource(P.command_probe)
    old="out=HERE/'step3/command-preview'";new="out=ROOT/'build/set-b-placement-r1/validation-r1/command-preview'"
    assert source.count(old)==1;source=source.replace(old,new,1)
    executed=OUT/'command-probe-executed.py';executed.write_text(source)
    ns=dict(vars(P));exec(compile(source,str(executed),'exec'),ns)
    preview=ns['command_probe']()
    checked('fresh source command preview matches measured projection; no commands executed')
    extent,tenants=P.late_partition();assert extent==6720
    header=(ROOT/'config/set-b-native/set-b-placement.h').read_text()
    for t in tenants:
        m=re.search(r'#define SET_B_'+str(t['slot'])+r'_OFFSET 0x([0-9A-F]+)u',header)
        assert m and int(m[1],16)==t['offset']
    checked('header, source addresses, manifest geometry and producer agree')
    # Compare the moved function's relocation operands, not merely zero-filled
    # placeholder instruction bytes in the non-LTO objects.
    reader=ROOT/'tools/llvm-mos/bin/llvm-readobj'
    truths=[ElfTruth.read(BASE/label/'runtime.o',llvm_readobj=reader,include_section_data=True) for label in ['before','after']]
    def relocations(t):
        f=t.symbol('c2_overlay_call')
        return [(r.offset-f.value,r.relocation_type,r.target,r.addend) for r in t.relocations
                if r.source_section==f.section and f.value<=r.offset<f.value+f.bytes]
    assert relocations(truths[0])==relocations(truths[1])
    checked('moved function relocation targets/types/addends match')
    original=P.load(P.INPUTS);old_inputs=P.INPUTS
    rejected=[]
    for name,mutate in [
        ('overlap',lambda d:d['tenants'][3].update(offset=d['tenants'][2]['offset']+32)),
        ('misaligned',lambda d:d['tenants'][2].update(offset=d['tenants'][2]['offset']+16)),
        ('wrong-bank-address',lambda d:d['tenants'][2].update(source_address=d['tenants'][2]['source_address']+65536)),
        ('oversize-interval',lambda d:d['tenants'][1].update(offset=1824)),
        ('wrong-tail',lambda d:d.update(aligned_extent=8200))]:
        data=copy.deepcopy(original);mutate(data)
        fixture=OUT/'negative-inputs'/(name+'.json');P.write(fixture,data);P.INPUTS=fixture
        try:
            try:P.late_partition()
            except ValueError:rejected.append(name)
            else:raise AssertionError('accepted geometry '+name)
        finally:P.INPUTS=old_inputs
    assert len(rejected)==5
    checked('five malformed geometry controls rejected')
    image,rows=M.dry_tenants()
    assert len(image)==8192 and image[extent:]==bytes([0xa5])*(8192-extent)
    for i,t in enumerate(rows):
        end=rows[i+1]['offset'] if i+1<len(rows) else extent
        assert len(t['payload'])==end-t['offset']
        assert t['payload'][t['projected_bytes']:]==bytes(len(t['payload'])-t['projected_bytes'])
    items=[]
    for i,t in enumerate(rows):
        spec=B.SliceSpec(i,t['name'],t['section'],t['start_symbol'],t['end_symbol'],t['entry_symbol'],6,1,0,region_id=3)
        items.append(B.ExtractedSlice(spec,0xc356,0xc356+len(t['payload']),0xc356,t['payload']))
    raw,overflow,parsed=B.build_region_images(items,profile_build_id=0x94ad170b,expected_vma=0xc356,
        max_slice_bytes=1792,format_version=4,payload_alignment=32)
    assert parsed.late_image==image and not overflow
    assert [r.file_offset for r in parsed.slices]==[r['offset'] for r in rows]
    (OUT/'fixture-catalog.bin').write_bytes(raw);(OUT/'fixture-late.bin').write_bytes(image)
    checked('unchanged canonical builder reproduces complete padded image and all offsets')
    world=M.dry_world(OUT/'pack-fixture')
    manifest=P.load(world/'runtime-overlays-session-final.json')
    truth=ElfTruth.read(world/manifest['elf']['file'],llvm_readobj=reader,include_section_data=True)
    section=truth.section('.lisp65_rt_card_l_stage');binding=truth.symbol('rtov_late_stage_binding');entry=truth.symbol('card_l_stage_entry')
    session,sm=P.bind_session_payload(world,OUT/'pack-fixture/positive',image,rows,
        truth.section_bytes(section.name),binding.value-section.address,entry.value,dry_run=True)
    boot,bm=M.boot_pack(world,OUT/'pack-fixture/positive',image)
    ov=(world/sm['overflow_storage']['file']).read_bytes()
    assert len(M.validate_session(session,ov,sm,image).slices)==62
    assert struct.unpack_from('<HH',session,28)==(len(ov),B.crc16_ccitt_false(ov))
    for data,m in [(session,sm),(boot,bm)]:
        for r in m['slices']:
            rec=bytearray(data[32+r['id']*32:64+r['id']*32]);crc=struct.unpack_from('<H',rec,22)[0]
            rec[22:24]=bytes(2);assert B.crc16_ccitt_false(rec)==crc
            if r['region_id']==3:
                payload=image[r['file_offset']:r['file_offset']+r['file_size']]
                assert len(payload)==r['memory_size'] and B.crc16_ccitt_false(payload)==r['crc16']
    for before,after in zip(manifest['slices'][:55],sm['slices'][:55]):assert before==after
    checked('63-record Session fixture validates, payload/record/overflow CRCs hold, prior slots 0..54 unchanged')
    for name,mutate in [
        ('displaced-tenant',lambda b:struct.pack_into('<H',b,32+58*32+4,tenants[2]['source_address']%65536+16)),
        ('stale-overflow-crc',lambda b:struct.pack_into('<H',b,30,struct.unpack_from('<H',b,30)[0]^1))]:
        data=bytearray(session);mutate(data)
        if name=='displaced-tenant':
            at=32+58*32;struct.pack_into('<H',data,at+22,0)
            struct.pack_into('<H',data,at+22,B.crc16_ccitt_false(data[at:at+32]))
        B._refresh_catalog_crcs(data)
        try:M.validate_session(data,ov,sm,image)
        except B.OverlayBankError as e:rejected.append(dict(name=name,code=e.code))
        else:raise AssertionError('accepted catalog '+name)
    checked('CRC-consistent displaced source and stale overflow binding rejected')
    # Read total occupied E000 directly from failed-link LTO + unchanged asm
    # inputs through the map, rather than treating an object as a linked ELF.
    mapfile=ROOT/'build/set-b-product-r2/wplto/resident-island-seed.prg.map'
    sections={}
    for line in mapfile.read_text().splitlines():
        m=re.fullmatch(r'\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+ (\.\S+)',line)
        if m and (m[4].startswith('.lisp65_c2_kernal_window.') or m[4]=='.lisp65_c2_vectors'):
            sections[m[4]]=int(m[3],16)
    free=8192-sum(sections.values());assert free==115
    checked('map-based projected E000 air 115 >= 54; move adds zero occupied bytes')
    P.write(OUT/'receipt.json',dict(status='PASS: HOST PLACEMENT AND PACK FIXTURES; NO EXECUTABLE SET B',
        driver=P.bind(Path(__file__)),checks=checks,negative_controls=rejected,
        authority=P.AUTH,command_preview=P.bind(preview/'receipt.json'),executed_preview=P.bind(executed),
        geometry=P.bind(BASE/'geometry-r3/receipt.json'),object_proposal=P.bind(BASE/'review-r2/proposal.json'),
        sources=[P.bind(ROOT/p) for p in P.authority_files()],map=P.bind(mapfile),
        projected_e000_air=free,e000_floor=54,
        seed_invocations=0,product_links=0,finals=0,emulator_runs=0,device_contacts=0,
        fixture_only=True,executable_set_b=False))
    print('PASS:',len(checks),'host checks;',len(rejected),'negative controls; no product link or guest execution')

if __name__=='__main__':main()
