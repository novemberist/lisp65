#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Materialize and pack the reproduced final renderer pair, never re-finalize it."""
import json
from pathlib import Path
import shutil


def pack(P):
    import c2_v160_refill_boundary_witness_media_repair as FACADE
    import c2_lite_canonical_product as CAN
    import c2_lite_media_product as MEDIA
    import c2_v200_block3_return_device_media as COMPOSE
    import c2_v200_tier2_delivery_device_media as DELIVERY
    import d81_persistence_fault as D81
    from elf_truth import ElfTruth
    import c2_v160_nested_map_swap_media as NESTED
    root, final, plane = P.ROOT, P.BUILD/'wplto', P.PLANE_ROOT
    out = P.PUBLIC/'renderer-media'
    P.require(not out.exists(), 'public media completion is one-shot')
    out.mkdir()
    completion = out/'completion'
    shutil.copytree(final, completion)
    target = completion/P.PRG.name
    elf = completion/P.ELF.name
    before = P.PRG.read_bytes()
    predecessors = NESTED.materialize_candidate_publish_predecessors(completion, target, elf)
    address, expected = FACADE.facade_truth(elf)
    _raw, offset = FACADE.prg_span(target, address, len(expected))
    after = target.read_bytes()
    P.require(len(before) == len(after) and before[:offset] == after[:offset]
        and before[offset+len(expected):] == after[offset+len(expected):]
        and after[offset:offset+len(expected)] == expected, 'facade materialization changed another byte')
    facade = FACADE.packed_facade_gate(target, elf)
    for name in ('c2-product-kernal-window.bin', 'runtime-overlays-boot-final.bin',
                 'runtime-overlays-session-final.bin', 'runtime-overlays-session-final-region1.bin', P.ELF.name):
        P.require((completion/name).read_bytes() == (final/name).read_bytes(), 'completion drift: '+name)
    CAN.ARTIFACTS = out/'artifacts'; CAN.ARTIFACTS.mkdir()
    bootstage, geometry = CAN.build_boot_stage(elf, P.PROFILE)
    truth = ElfTruth.read(elf, llvm_readobj=root/'tools/llvm-mos/bin/llvm-readobj', include_section_data=True)
    names = [s.name for s in truth.sections if s.name.startswith('.lisp65_c2_mapped_')
        and truth.symbols_by_name.get('__'+s.name.removeprefix('.')+'_load_start')
        and truth.symbol('__'+s.name.removeprefix('.')+'_load_start').value < 0x30000]
    mapped = COMPOSE.mapped_section_rows(truth, names)
    prefix = P.CODE.read_bytes()
    P.require(len(prefix) == 47795, 'renderer plane extent drift')
    base = 0x20000
    image = bytearray(max(start+len(raw) for start,raw,_ in mapped)-base)
    image[:len(prefix)] = prefix
    cursor = base+len(prefix)
    for start, raw, name in mapped:
        P.require(start >= cursor, 'mapped owner overlap: '+name)
        image[start-base:start-base+len(raw)] = raw; cursor = start+len(raw)
    code = CAN.ARTIFACTS/'bank2-static-code.bin'; code.write_bytes(image)
    roles = {'linked-product-elf': elf, 'c2-resident-prg': target,
        'c2-bank2-static-code-plane': code, 'c2d-v6-code-plane': P.C2D,
        'c2-two-record-boot-stage': bootstage, 'resolved-profile': P.PROFILE,
        'c2-session-family-region-0': completion/'runtime-overlays-session-final.bin',
        'c2-session-family-region-1': completion/'runtime-overlays-session-final-region1.bin',
        'c2-product-shelf': plane/'product/product-shelf-v4-direct.bin',
        'c2-boot-family': completion/'runtime-overlays-boot-final.bin',
        'c2-kernal-window': completion/'c2-product-kernal-window.bin'}
    roles.update({'library-'+n: P.EXTERNAL_IMAGES/(n+'.ext.bin') for n in ('ide','idex','m65d')})
    MEDIA.BUILD = out
    contract = MEDIA.load(MEDIA.CONTRACT)
    staged, reset = MEDIA.stage_artifact_map(contract, roles, write=True)
    media_rows = MEDIA.media_rows(contract, staged)
    descriptor, build_id = MEDIA.make_descriptor(media_rows, int(MEDIA.sha(P.PROFILE)[:8],16))
    desc = out/'boot.id'; desc.write_bytes(descriptor)
    parsed = MEDIA.parse_descriptor(descriptor, build_id, media_rows)
    mutations = MEDIA.mutation_gate(descriptor, build_id, media_rows)
    domains = MEDIA.stage_domain_gate(media_rows)
    stager = out/'autoboot.c65'
    opt = COMPOSE.BASE.MEDIA.PREP.LIVENESS.OPT_IN
    stager_gate = MEDIA.compile_stager(build_id, media_rows, build_dir=out,
        stager=stager, stager_map=Path(str(stager)+'.map'), compile_defines=(opt,))
    medium = out/'lisp65-product.d81'
    entries = [(stager,'autoboot.c65'), (desc,'boot.id'),
               *[(r['path'],r['name']) for r in media_rows]]
    MEDIA.build_d81(medium, 'L65SYS,65', entries); MEDIA.D81.stamp_product_boot_marker(medium)
    actual = D81.visible_files(medium.read_bytes())
    P.require(actual == {name.upper().encode():path.read_bytes() for path,name in entries},
              'packed role readback differs')
    P.require(actual[b'CODE.BIN'] == bytes(image), 'packed code projection differs')
    projection = out/'readback-product'; shutil.copytree(plane/'product', projection)
    offset = 0
    for key in P.CARD.STRIP.PRODUCT_KEYS:
        source = projection/(key+'.code.bin'); n = source.stat().st_size
        source.write_bytes(actual[b'CODE.BIN'][offset:offset+n]); offset += n
    P.require(offset == len(prefix), 'packed static population extent mismatch')
    closure = DELIVERY.CLOSURE.derive(projection/'substitution-artifacts.json')
    DELIVERY.CLOSURE.require_closed(closure)
    coherence = DELIVERY.COHERENCE.derive(plane/'stdlib-p0.manifest.json',
        plane/'product/stdlib-p0.code.bin', P.PUBLIC_GENERATION_SUITE,
        (projection/'stdlib-p0.code.bin').read_bytes())
    DELIVERY.COHERENCE.require_coherent(coherence)
    work = out/'lisp65-work.d81'; MEDIA.build_d81(work, 'L65WORK,65', [])
    mount = out/'lisp65-product.mount.json'
    mount.write_bytes(P.canonical({'disk_id':'65','disk_name':'L65SYS','drive':8,
        'format':'lisp65-product-mount-descriptor-v3','media':medium.name,
        'media_sha256':P.sha(medium),'mutable_entries':False,
        'paired_work_media':{'disk_id':'65','disk_name':'L65WORK','drive':9,
            'media':work.name,'media_sha256':P.sha(work),'mutable_entries':True},
        'write_protect':{'physical_floppy':'required-if-used',
            'stock_core_SD_D81':'unavailable-no-virtual-read-only-attach-control'}}))
    selected = dict(staged)
    selected.update({'boot-descriptor':desc,'cold-stager':stager,
        'product-d81':medium,'product-mount-descriptor':mount,'work-d81':work})
    P.require(set(selected) == set(P.authority()['sealed_roles']), 'public media role population differs')
    rows=[]
    for role,path in sorted(selected.items()):
        row=P.bind(path); expected=P.authority()['sealed_roles'][role]
        P.require({k:row[k] for k in ('bytes','sha256')} == expected,
                  'HALT: media role differs from device-qualified world: '+role)
        name = {'c2d-v6-code-plane':'c2d-v6-reset-domain.bin'}.get(role, path.name)
        rows.append(dict(row, role=role, name=name))
    value={'format':P.FORMAT,'status':P.STATUS,'selector':'v2.1-renderer-f011-native',
        'private_evidence_inputs':0,'artifact_count':len(rows),'artifacts':rows,
        'artifact_set_sha256':P.artifact_set(rows),'product_build_id':build_id,
        'profile_build_id':int(MEDIA.sha(P.PROFILE)[:8],16),
        'completion':{'predecessors':predecessors,'facade':facade},
        'boot_geometry':geometry,'descriptor':parsed,'descriptor_mutations':mutations,
        'domains':domains,'reset':reset,'stager':stager_gate,
        'closure':closure,'coherence':coherence,'product_rebuilds':0,'product_links':0}
    P.require(value['artifact_set_sha256'] == P.authority()['sealed_product_artifact_set_sha256'],
              'public media aggregate differs from sealed target')
    P.MANIFEST_OUT.write_bytes(P.canonical(value))
    return value
