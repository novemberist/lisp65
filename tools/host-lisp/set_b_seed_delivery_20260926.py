"""Deliver the inventoried third Set B Seed; never compile/link the runtime.

Re-extract all inherited records, refresh fixed Bank-2 native owners, retain
the Lisp code plane, and publish derived CRC domains in a PRG copy. Only
the inherited cold delivery stager is compiled/linked by pack_disk.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import traceback
sys.dont_write_bytecode = True
import set_b_producer as P
import set_b_seed_media as M
import card_l_seed_media as C
import runtime_overlay_bank as B
import d81_persistence_fault as D
from elf_truth import ElfTruth

ROOT = P.ROOT
BASE = ROOT/'build/card-l-seed-medium-r2'
SEED = ROOT/'build/set-b-product-r3/wplto'


def sha(raw): return hashlib.sha256(raw).hexdigest()


def lma(path, truth, section):
    raw = path.read_bytes(); phoff, shoff = struct.unpack_from('<II', raw, 28)
    phsize, phnum, shsize = struct.unpack_from('<HHH', raw, 42)
    hdr = struct.unpack_from('<10I', raw, shoff+section.index*shsize)
    rows = [struct.unpack_from('<8I', raw, phoff+i*phsize) for i in range(phnum)]
    rows = [p for p in rows if p[0] == 1 and p[1] <= hdr[4] and hdr[4]+section.bytes <= p[1]+p[4]]
    assert len(rows) == 1
    return rows[0][3]+hdr[4]-rows[0][1]


def refresh_family(family, world, before, after):
    m = P.load(world/f'runtime-overlays-{family}-final.json')
    paths = {0:m['storage']['file'], 1:m['overflow_storage']['file']}
    if 'external_storage' in m: paths[2] = m['external_storage']['file']
    if not (world/paths[1]).exists():
        assert m['overflow_storage']['used'] == 0 and m['overflow_storage']['sha256'] == sha(b'')
        (world/paths[1]).write_bytes(b'')
    regions = {k:bytearray((world/v).read_bytes()) for k,v in paths.items()}
    for key,k in [('storage',0),('overflow_storage',1)]+([('external_storage',2)] if 2 in regions else []):
        assert sha(regions[k]) == m[key]['sha256']
    proofs = []
    for row in m['slices']:
        if family == 'boot' and row['id'] >= 12: continue
        old = before.section_bytes(row['section']); new = after.section_bytes(row['section'])
        at = row['file_offset']; region = row['region_id']; size = row['file_size']
        payload = bytes(regions[region][at:at+size])
        if family == 'session' and row['id'] == 55:
            # The delivered predecessor carries its tuple, unlike its raw ELF.
            binding = before.symbol('rtov_late_stage_binding').value-before.section(row['section']).address
            masked = bytearray(payload); masked[binding:binding+4] = bytes(4)
            assert bytes(masked) == old
            assert len(new) <= size
            new = new.ljust(size, b'\0')
        else: assert payload == old and len(old) == size
        if len(new) != size:
            assert family == 'boot' and row['id'] == 11 and len(new) == size+2
            next_at = m['slices'][12]['file_offset']; assert at+len(new) <= next_at
            assert not any(regions[region][at+size:at+len(new)])
        assert len(new) <= 1792 and after.section(row['section']).address == row['vma']
        regions[region][at:at+len(new)] = new
        entry = after.symbol(row['entry_symbol']).value if row['entry_symbol'] else row['entry']
        entry_offset = entry-row['vma'] if row['entry_symbol'] else row['entry_offset']
        row.update(file_size=len(new), memory_size=len(new), end=row['vma']+len(new), entry=entry,
                   entry_offset=entry_offset, crc16=B.crc16_ccitt_false(new), sha256=sha(new))
        record_at = B.HEADER_SIZE+row['id']*B.ENTRY_SIZE
        struct.pack_into('<H', regions[0], record_at+6, len(new))
        struct.pack_into('<H', regions[0], record_at+10, len(new))
        struct.pack_into('<H', regions[0], record_at+12, entry_offset)
        struct.pack_into('<H', regions[0], record_at+20, row['crc16'])
        proofs.append(dict(slot=row['id'], section=row['section'], before_sha256=sha(payload), after_sha256=sha(new),
                           old_bytes=size, new_bytes=len(new), region=region, offset=at, padding=len(new)-after.section(row['section']).bytes))
    regions[0] = bytearray(P.rebind_family(regions[0], m['slices'], regions[1]))
    h = B.HEADER.unpack_from(regions[0]); m['catalog'].update(directory_crc16=h[12], header_crc16=h[13])
    for k,p in paths.items(): (world/p).write_bytes(regions[k])
    for key,k in [('storage',0),('overflow_storage',1)]+([('external_storage',2)] if 2 in regions else []):
        m[key].update(sha256=sha(regions[k]), crc16=B.crc16_ccitt_false(regions[k]))
    m['elf'].update(file='lisp65-c2-substitution-linked.prg.elf', sha256=sha((world/'lisp65-c2-substitution-linked.prg.elf').read_bytes()))
    P.write(world/f'runtime-overlays-{family}-final.json', m)
    return m, proofs


def main(out):
    assert not out.exists(); out.mkdir(parents=True); (out/'tmp').mkdir()
    closure = ROOT/'build/set-b-r1/step4-r4/inventory-closure-r1/receipt.json'
    assert P.load(closure)['complete_inventory'] and P.load(closure)['unclassified_bytes'] == 0
    P.require_auth()
    frozen = [P.bind(SEED/('resident-island-seed.prg'+s)) for s in ('','.elf','.lto.o','.map')]
    assert frozen[1]['sha256'] == '1eb22d5282acae5e39c1a1ea37bd749d6e524c9fb45005791b298a26bb5b71cf'
    P.write(out/'frozen.json', frozen)
    # This supplies delivered 56/17 catalogs, not the earlier 55/12 inputs.
    world = out/'world'; world.mkdir()
    delivered = D.visible_files((BASE/'comfort/card-l-comfort.d81').read_bytes())
    for family in ('boot','session'):
        manifest = P.load(BASE/'media-seed'/f'{family}-manifest.json')
        manifest.pop('card_l_tuple',None)
        (world/manifest['storage']['file']).write_bytes(delivered[(family+'.bin').upper().encode()])
        for key in ('overflow_storage','external_storage'):
            if key not in manifest: continue
            row = manifest[key]; source = BASE/'materialized'/row['file']
            data = source.read_bytes() if source.exists() else b''
            assert sha(data) == row['sha256']
            (world/row['file']).write_bytes(data)
        P.write(world/f'runtime-overlays-{family}-final.json',manifest)
    for name in ('resolved-profile.txt','c2-kernal-window.generated.h'):
        source = SEED/name if (SEED/name).exists() else BASE/'materialized'/name
        shutil.copyfile(source,world/name)
    assert not (world/'lisp65-c2-substitution-unbound.prg').exists()
    target = world/'lisp65-c2-substitution-linked.prg'
    for suffix in ('','.elf','.lto.o','.map'): shutil.copyfile(SEED/('resident-island-seed.prg'+suffix), Path(str(target)+suffix))
    elf = Path(str(target)+'.elf')
    ts = [ElfTruth.read(p, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj', include_section_data=True) for p in (P.FINAL, elf)]
    before, after = ts
    boot,bp = refresh_family('boot', world, before, after)
    session,sp = refresh_family('session', world, before, after)
    P.write(out/'family-extraction.json', dict(boot=bp, session=sp))
    # Bank-2 contains unchanged Lisp bytecode and four fixed native tenants.
    files = D.visible_files((BASE/'comfort/card-l-comfort.d81').read_bytes())
    code = bytearray(files[b'CODE.BIN']); code_before = bytes(code); native = []
    for sec in after.sections:
        if not (sec.name.startswith('.lisp65_c2_mapped_') or sec.name == '.lisp65_rt_card2b_disk') or sec.section_type == 'SHT_NOBITS': continue
        oldsec = before.section(sec.name); old = before.section_bytes(sec.name); new = after.section_bytes(sec.name)
        if old == new: continue
        address = lma(elf, after, sec)
        assert address == lma(P.FINAL, before, oldsec) and sec.bytes == oldsec.bytes
        assert 0x20000 <= address and address+sec.bytes <= 0x20000+len(code)
        at = address-0x20000; assert code[at:at+sec.bytes] == old
        code[at:at+sec.bytes] = new
        native.append(dict(section=sec.name, physical_address=address, bytes=sec.bytes, before_sha256=sha(old), after_sha256=sha(new)))
    native_positions = {r['physical_address']-0x20000+i for r in native for i in range(r['bytes'])}
    assert all(x == y or i in native_positions for i,(x,y) in enumerate(zip(code_before,code)))
    files[b'CODE.BIN'] = bytes(code)
    (out/'code.bin').write_bytes(code)
    P.write(out/'bank2-native-delivery.json', dict(owners=native, lisp_bytes_unchanged=True, before_sha256=sha(code_before), after_sha256=sha(code)))
    import c2_product_substitution_link as LINK
    P.configure(LINK)
    def forbidden(*a, **kw): raise RuntimeError('Runtime compile/link forbidden: reuse existing Seed')
    LINK.compile_link = forbidden
    import c2_v160_refill_boundary_witness_media_repair as FACADE
    facade = FACADE.materialize_facade(target, elf, world/'facade-materialization.json')
    window = LINK.publish_kernal_window_binding(world, target)
    addr = after.section('.lisp65_runtime_overlay_verifier_bindings').address
    table = LINK.patch_verifier_binding_table(world, target, world/'runtime-overlays-boot-final.json', world/'runtime-overlays-session-final.json', expected_base=addr)
    publication = LINK.total_publish_last_gate(world, target, window, table, expected_verifier_base=addr)
    import boot_only_carrier_prg as CARRIER
    files[b'LISP65.PRG'] = CARRIER.from_elf(elf, target.read_bytes(), publication_dir=world)
    import c2_lite_canonical_product as CAN
    CAN.ARTIFACTS = out/'bootstage'; CAN.ARTIFACTS.mkdir()
    stage, geometry = CAN.build_boot_stage(elf, world/'resolved-profile.txt')
    files.update({b'BOOTSTAGE.BIN':stage.read_bytes(), b'WINDOW.BIN':(world/'c2-product-kernal-window.bin').read_bytes(),
                  b'BOOT.BIN':(world/boot['storage']['file']).read_bytes(), b'SESSION.BIN':(world/session['storage']['file']).read_bytes(),
                  b'REGION1.BIN':(world/session['overflow_storage']['file']).read_bytes()})
    covered = {r['section'] for r in bp+sp+native}|{'.text','.rodata','.lisp65_c2_host_facade','.lisp65_boot_bank3_stage','.lisp65_workbench_overlay','.lisp65_boot_carrier','.lisp65_c2_kernal_handoff','.lisp65_c2_fixed_bank0_code'}|{r['section'] for r in P.load(P.INPUTS)['tenants']}
    unbound = (world/'lisp65-c2-substitution-unbound.prg').read_bytes()
    load = struct.unpack_from('<H',unbound)[0]
    for name in ('.lisp65_c2_kernal_handoff','.lisp65_c2_fixed_bank0_code'):
        sec = after.section(name); at = sec.address-load+2
        assert unbound[at:at+sec.bytes] == after.section_bytes(name)
    changed = []
    for sec in after.sections:
        if 'SHF_ALLOC' not in sec.flags or sec.section_type == 'SHT_NOBITS': continue
        if sec.name in before.sections_by_name and before.section_bytes(sec.name) == after.section_bytes(sec.name): continue
        assert sec.name in covered or sec.name.startswith('.lisp65_c2_kernal_window.'), ('undelivered changed section',sec.name)
        changed.append(sec.name)
    import c2_lite_media_product as DISK
    base = out/'base'; base.mkdir(); entries = []
    for name, data in files.items():
        path = base/name.decode().lower(); path.write_bytes(data); entries.append((path,name.decode().lower()))
    disk = base/'base.d81'; DISK.build_d81(disk,'L65SYS,65',entries); DISK.D81.stamp_product_boot_marker(disk)
    assert D.visible_files(disk.read_bytes()) == files
    population = out/'population'; shutil.copytree(BASE/'population',population)
    positive = out/'media-seed'
    sr,sm = P.bind_session(world, positive); image = (positive/'set-b-tenants.bin').read_bytes()
    br,bm = M.boot_pack(world,positive,image)
    overflow = (world/sm['overflow_storage']['file']).read_bytes()
    assert len(M.validate_session(sr,overflow,sm,image).slices) == 62
    M.OUT = C.OUT = out
    def pack(folder, bootraw, bootmanifest):
        medium = C.pack_disk(disk,population/'delivery-population.json',bootraw,folder,world,bootmanifest,sr,sm)
        newpath = medium.with_name('set-b-comfort.d81'); medium.rename(newpath)
        return newpath
    medium = pack(positive,br,bm)
    controls = []
    for name,(raw,manifest) in M.controls(br,bm).items():
        folder = out/'controls'/name; control = pack(folder,raw,manifest)
        P.write(folder/'boot-manifest.json',manifest)
        controls.append(dict(name=name,medium=P.bind(control),expected='READY=1; identical prompt; retirement disarmed',executed=False))
    # A disk cannot preserve a journal corruption across the reset zero write.
    # Bind the actual temporal fault instead of repeating the old READY=0 rule.
    matrix = P.load(ROOT/'build/set-b-r1/step3/step3b-gate-matrix.json')
    P.write(out/'controls/journal-and-recovery-successor.json',dict(status='PREPARED; NOT EXECUTED',
        authority='step 3b, 4f843a79; current source 7a4e43fa',
        boot_journal=matrix['rows'][3],recovery=matrix['rows'][4:],
        requires_emulator_injection=True,control_medium=P.bind(medium),
        no_claim_of_standalone_corrupted_journal_disk=True))
    assert frozen == [P.bind(SEED/('resident-island-seed.prg'+s)) for s in ('','.elf','.lto.o','.map')]
    P.write(out/'completion.json',dict(status='PASS: MEDIA CONSTRUCTED; INDEPENDENT READBACK AND GUEST GATES PENDING',
        driver=P.bind(Path(__file__)),inventory=P.bind(closure),seed_unchanged=True,frozen=frozen,
        medium=P.bind(medium),comfort_inherited=True,controls=controls,
        native_bank2_owners=native,changed_sections_delivered=changed,facade=facade,window=window,publication=publication,
        bootstage=geometry,product_compiles=0,product_links=0,cold_stager_links=4,device_contact=0))
    print('PASS: existing Seed delivered with refreshed native owners; positive and three control media')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--out',type=Path,required=True)
    args = ap.parse_args(); out = args.out.resolve()
    try: main(out)
    except Exception as e:
        if out.exists(): P.write(out/'failure.json',dict(status='DELIVERY HALT',error=str(e),traceback=traceback.format_exc(),driver=P.bind(Path(__file__))))
        raise
