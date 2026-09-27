"""Readback and post-link gates for the Card L r2 media; never relinks."""
import copy
import hashlib
import inspect
import json
import os
import shutil
from pathlib import Path
import struct
import sys
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True
import card_l_producer as P
import c2_product_substitution_link as L
import runtime_overlay_bank as B
import c2_lite_media_product as M
import d81_persistence_fault as D
import c2_require_resolver_gate as I
from elf_truth import ElfTruth
ROOT=P.ROOT
OUT=ROOT/'build/card-l-seed-medium-r2'
WORLD=OUT/'materialized'
GATES=OUT/'gates'

def sha(b): return hashlib.sha256(b).hexdigest()

def family(raw, overflow, manifest, boot=False):
    rows=manifest['slices']
    if not boot:
        assert [(rows[i]['id'],rows[i]['section']) for i in (52,53,54,55)] == [
            (52,'.lisp65_rt_card2b_disk'),(53,'.lisp65_rt_c2d_10a'),
            (54,'.lisp65_rt_c2d_10b'),(55,'.lisp65_rt_card_l_stage')]
        # Same region-2 projection as ov_crc16_seed_media.validate, with
        # the appended Card L record retained and a 56-record source catalog.
        raw=bytearray(raw)
        for i in range(53,56):
            rec=bytearray(raw[B.HEADER_SIZE+i*B.ENTRY_SIZE:B.HEADER_SIZE+(i+1)*B.ENTRY_SIZE])
            struct.pack_into('<H',rec,0,i-1);struct.pack_into('<H',rec,22,0)
            struct.pack_into('<H',rec,22,B.crc16_ccitt_false(rec))
            raw[B.HEADER_SIZE+(i-1)*B.ENTRY_SIZE:B.HEADER_SIZE+i*B.ENTRY_SIZE]=rec
        raw[B.HEADER_SIZE+55*B.ENTRY_SIZE:B.HEADER_SIZE+56*B.ENTRY_SIZE]=bytes(B.ENTRY_SIZE)
        # Removing slot 52 also crosses the 56-to-55 directory boundary.
        # Normalize the projected main offsets, leaving real media untouched.
        raw[7]=55
        old=struct.unpack_from('<H',raw,18)[0]
        new=B._align(B.HEADER_SIZE+55*B.ENTRY_SIZE,B.CATALOG_ALIGNMENT)
        growth=old-new
        del raw[new:old]
        struct.pack_into('<H',raw,18,new)
        struct.pack_into('<I',raw,20,len(raw))
        for i in range(55):
            at=B.HEADER_SIZE+i*B.ENTRY_SIZE
            if raw[at+24]==0:
                struct.pack_into('<H',raw,at+4,struct.unpack_from('<H',raw,at+4)[0]-growth)
                struct.pack_into('<H',raw,at+22,0)
                struct.pack_into('<H',raw,at+22,B.crc16_ccitt_false(raw[at:at+B.ENTRY_SIZE]))
        B._refresh_catalog_crcs(raw)
    return B.validate_region_images(raw,overflow,
        expected_build_id=manifest['profile_build_id'],expected_vma=manifest['policy']['common_vma'],
        max_slice_bytes=manifest['policy']['max_slice_bytes'],format_version=4,
        main_source_base=next(r['source_address']-r['file_offset'] for r in rows if r['region_id']==0),
        payload_alignment=256 if boot else 32)

def main():
    GATES.mkdir(exist_ok=True)
    results={}
    def gate(name,fn):
        try:
            value=fn();results[name]={'status':'PASS','result':value}
            print(name+': PASS',flush=True)
            return value
        except Exception as e:
            results[name]={'status':'FAIL','error':str(e)}
            print(name+': FAIL '+str(e),flush=True)
    P.configure(L)
    # Reproduce the nested module setup in c2_v240_public_product.configure.
    if L.LINK60_FINAL_GEOMETRY:L.FIXED_BLOCK_LEAF.configure_link60_geometry()
    if L.DERIVED_FIXED_BANK0_CODE_LAYOUT:L.FIXED_BLOCK_LEAF.configure_candidate_derived_code_layout()
    shutil.copyfile(WORLD/'c2-product-kernal-window.bin',GATES/'c2-product-kernal-window.bin')
    def forbidden(*a,**k): raise RuntimeError('runtime compile/link forbidden')
    L.compile_link=forbidden
    target=WORLD/'lisp65-c2-substitution-linked.prg';elf=Path(str(target)+'.elf')
    assert sha(elf.read_bytes())=='7e57bc17f318dd22a6dbc0212fd5fde5b9598eaf645f4f98d6387e0c3f53f3b5'
    for name,mod in [('crc-codegen',L.CRC_CODEGEN),('crc-asm-leaf',L.CRC_ASM_LEAF),('asm-leaf-abi',L.ASM_LEAF_ABI)]:
        kw={'require_bank3_chain':L.FAMILY_STAGE_BINDINGS} if name=='asm-leaf-abi' else {}
        gate(name,lambda mod=mod,kw=kw,name=name:mod.audit_elf(elf,out=GATES/(name+'.json'),**kw))
    gate('f011-window',lambda:L.F011_WINDOW.audit(L.F011_WINDOW.disassemble(L.TOOLCHAIN/'llvm-objdump',elf)))
    gate('handoff-z-abi',lambda:L.handoff_z_abi_gate(GATES,target,'final'))
    pre=gate('pre-ownership',lambda:L.pre_ownership_gate(GATES,target,'final'))
    if pre:gate('profile-data-reference',lambda:L.profile_data_reference_gate(GATES,target,'final',pre))
    gate('fixed-facade',lambda:L.fixed_facade_gate(GATES,target,'final'))
    kernal=gate('kernal-freedom',lambda:L.kernal_freedom_gate(GATES,target))
    import boot_only_carrier_elf_gate as CARRIER
    gate('carrier-elf',lambda:CARRIER.check(elf))
    positive=D.visible_files((OUT/'media-seed/card-l.d81').read_bytes())
    bm=json.loads((OUT/'media-seed/boot-manifest.json').read_text())
    sm=json.loads((OUT/'media-seed/session-manifest.json').read_text())
    for filename,data in [('runtime-overlays-final.bin',positive[b'SESSION.BIN']),
            ('runtime-overlays-session-final.bin',positive[b'SESSION.BIN']),
            ('runtime-overlays-boot-final.bin',positive[b'BOOT.BIN']),
            ('runtime-overlays-session-final-region1.bin',positive[b'REGION1.BIN'])]:
        (GATES/filename).write_bytes(data)
    for family_name,manifest in [('boot',bm),('session',sm)]:
        (GATES/f'runtime-overlays-{family_name}-final.json').write_text(json.dumps(manifest)+'\n')
    gate('one-truth-closure',lambda:L.closure_gate(GATES,target))
    if kernal:gate('substitution-balance',lambda:L.substitution_balance(GATES,target,kernal))
    gate('boot-catalog',lambda:len(family(positive[b'BOOT.BIN'],b'',bm,True).slices))
    gate('session-catalog',lambda:len(family(positive[b'SESSION.BIN'],positive[b'REGION1.BIN'],sm).slices))
    def regressions():
        old=D.visible_files((ROOT/'build/card-l-seed-medium-r1/media-seed/card-l.d81').read_bytes())
        try:family(old[b'SESSION.BIN'],old[b'REGION1.BIN'],sm)
        except B.OverlayBankError as error:assert error.code=='overflow-binding',error.code
        else:raise AssertionError('r1 stale overflow binding accepted')
        for a,b in [(53,54),(52,54)]:
            bad=copy.deepcopy(sm);bad['slices'][a],bad['slices'][b]=bad['slices'][b],bad['slices'][a]
            try:family(positive[b'SESSION.BIN'],positive[b'REGION1.BIN'],bad)
            except AssertionError:pass
            else:raise AssertionError('pin mutation accepted')
        return 'r1 overflow binding and both pin mutations rejected'
    gate('regression-and-pins',regressions)
    def packed_plane():
        import c2_packed_medium_transitive_closure as C
        import c2_packed_object_generation_coherence as O
        import c2_v200_interactive_delivery_chain_pricing as PRICE
        plane=L.PRODUCT_ARTIFACTS_MANIFEST.parent.parent
        projection=GATES/'readback-product'
        shutil.copytree(plane/'product',projection,dirs_exist_ok=True)
        offset=0
        for key in C.PRODUCT_KEYS:
            p=projection/(key+'.code.bin');size=p.stat().st_size
            readback=positive[b'CODE.BIN'][offset:offset+size]
            assert readback==p.read_bytes(),key
            p.write_bytes(readback);offset+=size
        closure=C.derive(projection/'substitution-artifacts.json');C.require_closed(closure)
        coherence=O.derive(plane/'stdlib-p0.manifest.json',plane/'product/stdlib-p0.code.bin',
            PRICE.STDLIB_SUITE,(projection/'stdlib-p0.code.bin').read_bytes())
        O.require_coherent(coherence)
        return dict(closure=closure,coherence=coherence,readback_bytes=offset)
    gate('packed-closure-and-generation',packed_plane)
    def crc32_source():
        import legacy_ide_delivery as D
        source=(OUT/'population/delivery-stager-main.c').read_text()
        accepted=(ROOT/'build/stager-crc32-r2/stager-main.c').read_text()
        assert D.c_function(source,'crc32_step')==D.c_function(accepted,'crc32_step')
        for name in ('delivery-stager-main.c','delivery-roles.h','autoboot-chain.o','autoboot-rom-write-enable.o'):
            assert (OUT/'population'/name).read_bytes()==(ROOT/'build/nested-error-recovery-seed-medium-r1/packed'/name).read_bytes()
        return 'accepted CRC32 implementation and delivery population byte-identical'
    gate('stager-crc32-derivation',crc32_source)
    gate('reset-domain-mutations',lambda:M.reset_domain_mutation_gate(M.load(M.CONTRACT)))
    truth=ElfTruth.read(elf,llvm_readobj=L.TOOLCHAIN/'llvm-readobj',include_section_data=True)
    # Reuse the established compile_stager post-build gate body verbatim;
    # all four stagers have already been built by the media adapter.
    body=inspect.getsource(M.compile_stager)
    body=body[body.index('    stager_elf ='):]
    include=M.ASM_CONTRACT.compile_output(M.ASM_CONTRACT.load_contract(),'cc',('-DLISP65_C2_LITE_MEDIA_STAGER',))
    contract=GATES/'stager-contract.inc';contract.write_bytes(include)
    scope={**vars(M),'STAGER_C':OUT/'population/delivery-stager-main.c','ASM_CONTRACT_INCLUDE':contract}
    exec('def audit_stager(stager, rows, symbols):\n'+body,scope)
    symbols=M.ASM_CONTRACT.parse_equ(include)
    def medium(folder,filename):
        disk=(folder/filename).read_bytes();files=D.visible_files(disk)
        from d81_package_locators import qualify
        qualify(disk)
        prefix=(L.PRODUCT_ARTIFACTS_MANIFEST.parent.parent/'v6-semantics/initial.c2d-v6.bin').read_bytes()
        assert M.reset_domain_valid(files[b'C2D.BIN'],prefix,M.load(M.CONTRACT))
        receipt=json.loads(((OUT/'media-seed' if filename=='card-l-comfort.d81' else folder)/'receipt.json').read_text())
        rows=[dict(r,path=folder/r['name']) for r in receipt['rows']]
        M.RECORDS=len(rows);M.DESCRIPTOR_BYTES=M.HEADER_BYTES+len(rows)*M.RECORD_BYTES
        M.parse_descriptor(files[b'BOOT.ID'],receipt['descriptor_build_id'],rows)
        for r in rows:assert (len(files[r['name'].upper().encode()]),M.crc32(files[r['name'].upper().encode()]))==(r['bytes'],r['crc32'])
        mutations=M.mutation_gate(files[b'BOOT.ID'],receipt['descriptor_build_id'],rows)
        domains=M.stage_domain_gate(rows)
        if filename!='card-l-comfort.d81':
            stager_result=scope['audit_stager'](folder/'autoboot.c65',rows,symbols)
            (GATES/(folder.name+'-stager.json')).write_text(json.dumps(stager_result,indent=2)+'\n')
        slots={D.entry_name(s.record):s.record for s in D.directory_slots(disk) if s.record[2]}
        for row in I.decode_index(files[b'L65INDEX']):assert (row['track'],row['sector'])==D.file_chain(disk,slots[row['name'].upper().encode()])[0]
        prg=files[b'LISP65.PRG'];base=struct.unpack_from('<H',prg)[0]
        carrier=truth.section('.lisp65_boot_carrier');offset=carrier.address-base+2
        assert prg[offset:]==truth.section_bytes(carrier.name)
        assert prg[0xb4f4-base+2]==0xc0 and prg[0xb4fa-base+2]==6
        binding=truth.section('.lisp65_runtime_overlay_verifier_bindings')
        table=struct.unpack_from('<20H',prg,binding.address-base+2)
        for n,key in enumerate((b'BOOT.BIN',b'SESSION.BIN')):
            assert table[16+n*2:18+n*2]==(len(files[key]),B.crc16_ccitt_false(files[key]))
        assert struct.unpack_from('<HH',files[b'SESSION.BIN'],28)==(len(files[b'REGION1.BIN']),B.crc16_ccitt_false(files[b'REGION1.BIN']))
        return dict(sha256=sha(disk),mutations=mutations,domains=domains,carrier_end=base+len(prg)-2)
    for folder,filename in [(OUT/'media-seed','card-l.d81'),*[(OUT/'media-controls'/n,'card-l.d81') for n in ('missing_record','corrupted_byte','displaced_256')],(OUT/'comfort','card-l-comfort.d81')]:
        gate(str(folder.relative_to(OUT)),lambda folder=folder,filename=filename:medium(folder,filename))
    (GATES/'results.json').write_text(json.dumps(results,indent=2,default=str)+'\n')
    assert all(v['status']=='PASS' for v in results.values()),'host gate failures: see gates/results.json'
if __name__=='__main__':main()
