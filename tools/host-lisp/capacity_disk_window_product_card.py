#!/usr/bin/env python3
"""Card 2b: one Renderer-derived seed, no implicit final product build.

The seed is the price authority under e0957b82. Final C/LTO and product link
are deliberately not exposed by this adapter before a qualified seed exists.
"""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import struct
from copy import deepcopy

import capacity_window_loader_product_card as A
import capacity_disk_window_projection as D
from evidence_era import stable_recorded_on

ROOT, C, F = A.ROOT, A.C, A.F
BUILD = ROOT/'build/capacity/card2b-product-r1'
PREFLIGHT = ROOT/'build/capacity/card2b-product-r1-preflight'
ORIGINAL_CONFIGURE = A.configure
PRODUCT = C.PRODUCT
ORIGINAL_LINKER = PRODUCT.linker_script
ORIGINAL_INVENTORY = PRODUCT.final_section_inventory_expectation
ORIGINAL_APPEND = PRODUCT.configure_append_slices
LEAF = C.B.PREV.CARD.CARD2.R2.CARD.BASE.CHAIN.LINK
ORIGINAL_MATERIALIZE = LEAF.materialize_candidate_sources


def authority():
    raw = subprocess.check_output(['git', 'show', D.AUTHORIZATION+
        ':docs/planning/capacity-block-work-plan.md'], cwd=ROOT)
    assert b'400' in raw and b'retention' in raw.lower()
    return dict(commit=D.AUTHORIZATION, plan_sha256=hashlib.sha256(raw).hexdigest(),
        predecessor={n:C.bind(A.PREDECESSOR[n]) for n in ('ELF','PRG','PROFILE')},
        retention='mandatory', seed_net_text_minimum=400,
        below_floor='HALT for Owner; not a failed repair attempt',
        budget=dict(seed_WPLTO=1,final_C_LTO=1,product_links=1,host_images=2,device_contacts=0))


def seed_data_gate(stem='resident-island-seed.prg'):
    """Read-only qualification plus adversarial copies; never compile/link."""
    from c2_no_pcrel16_gate import inspect, bind
    from elf_truth import ElfTruth
    base = BUILD/'wplto'
    assert stem in ('resident-island-seed.prg','lisp65-c2-substitution-linked.prg')
    elf = base/(stem+'.elf')
    lto = base/(stem+'.lto.o')
    link_map = base/(stem+'.map')
    core = ROOT/'build/v2.1/comfort-buffered-repair-device-r1/stack-repair-pricing-r1/gs4510-03b24c6b.vhdl'
    core_sha = 'd44ae3906e1b0a826ca8e511c73ef1f50223b7de507a3ed349082fdefe58034e'
    frozen = [bind(p) for p in (elf, lto, link_map, base/stem)]
    ro, od = ROOT/'tools/llvm-mos/bin/llvm-readobj', ROOT/'tools/llvm-mos/bin/llvm-objdump'
    phase = base/'generated-product-sources/c2-stream-phase-02a.c'
    def check(e=elf, i=lto, m=link_map):
        return inspect(e, core, core_sha, phase, ro, od, lto=i, link_map=m,
                       record_oracles=dict(shelf=C.PLANE/'product/product-shelf-v4-direct.bin',
                                           c2d=C.PLANE/'v6-semantics/initial.c2d-v6.bin'))
    baseline = check()
    assert baseline['status'] == 'PASS'
    truth = ElfTruth.read(elf, llvm_readobj=ro, include_section_data=True)
    inp = ElfTruth.read(lto, llvm_readobj=ro, include_section_data=True)
    anonymous = [r for r in baseline['linked_data_ownership']['owners']
        if r['relocations'] and not any(s.symbol_type == 'Object' and s.section == r['section'] and
                   s.value <= r['start'] and s.value + s.bytes >= r['end']
                   for s in truth.symbols)]
    assert len(anonymous) == 1, 'anonymous-owner population changed'
    owner = anonymous[0]
    mutations = []
    def rejected(name, operation):
        try:
            value = operation()
        except ValueError as e:
            mutations.append(dict(name=name, result='REJECTED', reason=str(e)))
        else:
            assert value['status'] == 'FAIL', name + ' survived'
            mutations.append(dict(name=name, result='REJECTED', violations=value['violations']))
    # ELF32 header fields locate bytes in fixture copies, never by a VMA-only search.
    def header(raw, index):
        assert raw[:6] == b'\x7fELF\x01\x01'
        shoff = struct.unpack_from('<I', raw, 32)[0]
        entsize = struct.unpack_from('<H', raw, 46)[0]
        assert entsize == 40
        return shoff + index * entsize
    def data_offset(raw, section):
        return struct.unpack_from('<I', raw, header(raw, section.index) + 16)[0]
    with tempfile.TemporaryDirectory(prefix='data-owner-mutations-', dir=PREFLIGHT) as temporary:
        out = Path(temporary)
        row = next(line for line in link_map.read_text().splitlines()
                   if str(lto.relative_to(ROOT))+':('+owner['input_section']+')' in line)
        missing = out/'missing.map'
        missing.write_text(link_map.read_text().replace(row+'\n', ''))
        rejected('input-owner-omitted', lambda: check(m=missing))
        extent = out/'extent.map'
        values = row.split(maxsplit=4)
        values[2] = f'{int(values[2],16)+1:x}'
        extent.write_text(link_map.read_text().replace(row, ' '.join(values)))
        rejected('input-owner-extended-into-code', lambda: check(m=extent))
        shifted = out/'shifted.map'
        values = row.split(maxsplit=4)
        values[0] = f'{int(values[0],16)-1:x}'
        shifted.write_text(link_map.read_text().replace(row, ' '.join(values)))
        rejected('input-owner-shifted-into-code', lambda: check(m=shifted))
        rel_section = inp.section('.rela'+owner['input_section'])
        raw_input = bytearray(lto.read_bytes())
        rel_pos = data_offset(raw_input, rel_section) + 8
        addend = struct.unpack_from('<i', raw_input, rel_pos)[0]
        struct.pack_into('<i', raw_input, rel_pos, addend+1)
        wrong_input = out/'wrong-relocation.o';wrong_input.write_bytes(raw_input)
        wrong_map = out/'wrong-relocation.map'
        wrong_map.write_text(link_map.read_text().replace(str(lto.relative_to(ROOT)),str(wrong_input)))
        rejected('input-relocation-target-changed', lambda: check(i=wrong_input,m=wrong_map))
        for offset in range(owner['end'] - owner['start']):
            raw = bytearray(elf.read_bytes())
            section = truth.section(owner['section'])
            pos = data_offset(raw, section) + owner['start'] - section.address + offset
            raw[pos] ^= 1
            p = out/f'byte-{offset}.elf'; p.write_bytes(raw)
            rejected(f'relocated-byte-{offset}-changed', lambda p=p: check(e=p))
        raw = bytearray(elf.read_bytes())
        section = truth.section(owner['section'])
        pos = data_offset(raw, section) + owner['start'] - section.address
        raw[pos:pos+owner['end']-owner['start']] = bytes([baseline['opcodes'][0], 0, 0]) + b'\xea'*(owner['end']-owner['start']-3)
        long_elf = out/'real-long-branch.elf'; long_elf.write_bytes(raw)
        rejected('long-branch-hidden-under-old-data-proof', lambda: check(e=long_elf))
        raw_input = bytearray(lto.read_bytes())
        source_section = inp.section(owner['input_section'])
        sh = header(raw_input, source_section.index)
        flags = struct.unpack_from('<I', raw_input, sh+8)[0]
        struct.pack_into('<I', raw_input, sh+8, flags | 4)  # SHF_EXECINSTR
        code_input = out/'code-input.o'; code_input.write_bytes(raw_input)
        code_map = out/'code.map'
        code_map.write_text(link_map.read_text().replace(str(lto.relative_to(ROOT)), str(code_input)))
        value = check(e=long_elf, i=code_input, m=code_map)
        assert value['status'] == 'FAIL' and any(v['section'] == owner['section'] and
            v['address'] == owner['start'] for v in value['violations'])
        mutations.append(dict(name='actual-code-owner-long-branch-at-same-address',
                              result='REJECTED', violations=value['violations']))
    from c2_no_pcrel16_gate import boundary_selftest
    mutations.extend(boundary_selftest(elf, core, core_sha, phase, ro, od, lto=lto, link_map=link_map,
        record_oracles=dict(shelf=C.PLANE/'product/product-shelf-v4-direct.bin',
                            c2d=C.PLANE/'v6-semantics/initial.c2d-v6.bin')))
    assert frozen == [bind(p) for p in (elf, lto, link_map, base/stem)]
    value = dict(status='PASS', authorization='23bd3aeb', baseline=baseline,
                 anonymous_owner=owner, mutations=mutations, frozen=frozen,
                 tools=[bind(Path(__file__)),bind(ROOT/'tools/host-lisp/c2_no_pcrel16_gate.py')],
                 budget=dict(additional_product_builds=0, host_images=0, contacts=0))
    role = 'seed' if stem.startswith('resident-island') else 'final'
    (PREFLIGHT/(role+'-data-owner-gate.json')).write_bytes(C.canonical(value))
    print(role+' data-owner gate PASS; every byte checked, real long-branch mutation rejected')
    return value


def expected_features():
    result = A.features(A.PREDECESSOR['PROFILE'])
    assert result and 'LISP65_RTOV_SESSION_RECORD_CACHE' not in result
    return result


def feature_authority():
    result = A.bound_features()
    return dict(predecessor=C.bind(A.PREDECESSOR['PROFILE']),
                successor=C.bind(C.BOUND_PROFILE), added=[],
                predecessor_feature_count=len(result), successor_feature_count=len(result))


def materialize(out):
    return D.materialize(out, ORIGINAL_MATERIALIZE(out))


def projected_sources(mapping, features):
    original = PRODUCT.source_list(features)
    result = [str(mapping.get(Path(p).resolve(), Path(p))) for p in original]
    assert len(original) == len(set(original)) == len(result)
    assert set(mapping) <= {Path(p).resolve() for p in original}, 'unused generated source'
    assert all(Path(p).is_file() for p in result)
    return result


def profile(mapping=None):
    assert mapping
    by_name = {p.name:p for p in mapping.values()}
    old = D.original_inputs()
    lines = A.PREDECESSOR['PROFILE'].read_text().splitlines()
    changes = []
    for i, line in enumerate(lines):
        if not line.startswith('input_sha256='):
            continue
        name, prior = line.split('=',1)[1].rsplit(':',1)
        root = (ROOT/name).resolve()
        if '/generated-product-sources/' in name:
            p = by_name.get(Path(name).name, ROOT/name)
        else:
            p = mapping.get(root, root)
        digest = C.bind(p)['sha256']
        successor = ((F.WPLTO/'generated-product-sources'/p.name).relative_to(ROOT).as_posix()
                     if p in mapping.values() else name)
        lines[i] = f'input_sha256={successor}:{digest}'
        if digest != prior:
            changes.append(dict(predecessor=name, successor=successor,
                                before=prior, after=digest))
    assert len(old) == len([l for l in lines if l.startswith('input_sha256=')])
    allowed = {'io.c','vm.c','f011_guarded_write.s','vm_runtime_overlay.c'}
    assert {Path(r['predecessor']).name for r in changes} == allowed, changes
    C.BOUND_PROFILE.write_text('\n'.join(lines)+'\n')
    assert A.features(C.BOUND_PROFILE) == expected_features()
    return dict(predecessor=C.bind(A.PREDECESSOR['PROFILE']),
                successor=C.bind(C.BOUND_PROFILE), changes=changes,
                feature_authority=feature_authority(), projection=C.bind(Path(D.__file__)))


def source_gate():
    rows = {}
    for name in ('member-entry-check.json','retention/receipt.json',
                 'owner-projection.json','retention-save-intervals.json'):
        value = D.receipt(name)
        assert value['mutations']
        rows[name] = C.bind(D.EVIDENCE/name)
    return dict(evidence=rows, projection=C.bind(Path(D.__file__)),
        adapter=C.bind(Path(__file__)),
        candidate_sources={name:hashlib.sha256(text.encode()).hexdigest()
                           for name,text in D.sources().items()},
        final_native_ownership_and_timing='owed on the seed/candidate; not host claims')


def produce_seed():
    configure()
    assert not C.INVOCATION.exists() and not BUILD.exists(), 'seed budget already entered'
    pre = C.load(F.PREFLIGHT_RECEIPT)
    assert pre['authority'] == authority()
    assert pre['toolchain'] == C.B.toolchain_identity()
    assert pre['semantic'] == source_gate(), 'source proof changed after preflight'
    assert not subprocess.check_output(['git','diff','HEAD','--name-only'], cwd=ROOT)
    untracked = subprocess.check_output(['git','ls-files','--others','--exclude-standard'],
                                        cwd=ROOT).decode().splitlines()
    assert all(p.startswith('.claude/') for p in untracked), 'unbound untracked source'
    consumed = pre['source_population']['compiler_sources']['bindings']
    assert all(not p['path'].startswith('.claude/') for p in consumed)
    head = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT).decode().strip()
    upstream = subprocess.check_output(['git','rev-parse','@{upstream}'], cwd=ROOT).decode().strip()
    assert head == upstream, 'seed source authority must be remote-visible'
    C.INVOCATION.write_bytes(C.canonical(dict(authority=authority(), commit=head,
        preflight=C.bind(F.PREFLIGHT_RECEIPT), status='SEED ATTEMPT ENTERED',
        foreign_untracked_not_consumed=untracked,
        final_C_LTO_invocations=0, product_links=0)))
    original = PRODUCT.compile_link
    entered = []
    class SeedComplete(Exception):
        pass
    def only_seed(out, name, *args, **kwargs):
        assert out == F.WPLTO and name == 'resident-island-seed.prg' and not entered
        assert len(PRODUCT.SESSION_SLICE_SPECS) == 53
        assert PRODUCT.SESSION_SLICE_SPECS[-1].split(':')[2] == D.SECTION
        entered.append(name)
        original(out, name, *args, **kwargs)
        raise SeedComplete()
    PRODUCT.compile_link = only_seed
    completed = False
    try:
        C.B.child('_produce')
        raise AssertionError('producer returned without a seed')
    except SeedComplete:
        completed = True
    finally:
        PRODUCT.compile_link = original
        paths = [F.WPLTO/('resident-island-seed.prg'+suffix)
                 for suffix in ('','.elf','.lto.o','.map')]
        (PREFLIGHT/'seed-attempt.json').write_bytes(C.canonical(dict(
            entered=entered, completed=completed, authority=authority(),
            artifacts=[C.bind(p) for p in paths if p.exists()],
            final_C_LTO_invocations=0, product_links=0)))
    print('Card 2b seed emitted; price/owners pending, final C/LTO and product link unused')


def source_population():
    bind_member()
    assert len(PRODUCT.SESSION_SLICE_SPECS) == 53
    assert PRODUCT.SESSION_SLICE_SPECS[-1].split(':')[2] == D.SECTION
    directory = Path(tempfile.mkdtemp(prefix='source-population-', dir=PREFLIGHT))
    mapping = materialize(directory)
    selected = A.bound_features()
    sources = projected_sources(mapping, selected)
    value = dict(status='PASS: PRODUCER-DERIVED SOURCE POPULATION',
        recorded_on=stable_recorded_on(F.SOURCE_PREFLIGHT),
        compiler_sources=dict(total=len(sources),generated=len(mapping),
                              bindings=[C.bind(Path(p)) for p in sources]),
        feature_authority=feature_authority(), feature_count=len(selected),
        source_projection=source_gate())
    F.SOURCE_PREFLIGHT.write_bytes(C.canonical(value))
    return value


def preflight():
    # Reuse the established checks, not their historical card labels.
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        A.preflight()
    (PREFLIGHT/'inherited-preflight.stdout').write_text(output.getvalue())
    for path, suffix in ((F.PLANE_RECEIPT,'plane'), (F.PREFLIGHT_RECEIPT,'preflight')):
        value = C.load(path)
        assert value['authority'] == authority()
        value['format'] = 'capacity-disk-window-r1-'+suffix
        path.write_bytes(C.canonical(value))
    print('Card 2b preflight PASS; budget 0/0/0, no medium or device contact')


def linker_script(**kwargs):
    base = ORIGINAL_LINKER(**kwargs)
    # The cold entry's switch table leaves the E000 profile aggregate. Keep
    # that existing owner extent/address, charging any padding to this card;
    # the CALLPRIM ID table itself is neither extended nor renumbered.
    anchor = '        __lisp65_c2_profile_rodata_callprim_end = .;'
    size = PRODUCT.PROFILE_RODATA_INPUT_SECTIONS['.rodata.vm_callprim']
    base = D.checked_replace(base, anchor,
        f'        . = MAX(., __lisp65_c2_profile_rodata_callprim_start + {size});\n'+anchor)
    sections = [s.split(':')[2] for s in PRODUCT.BOOT_SLICE_SPECS+PRODUCT.SESSION_SLICE_SPECS
                if s.split(':')[2] != D.SECTION]
    # Pairwise NOCROSSREFS also catches accidental calls into another live
    # overlay even though the new payload has a separate physical LMA.
    exclusion = ''.join(f'NOCROSSREFS({D.SECTION} {s})\n' for s in sorted(set(sections)))
    return base + D.linker_fragment() + exclusion


def inventory():
    value = ORIGINAL_INVENTORY()
    additions = [D.SECTION, '.rela'+D.SECTION,
                 '.noinit.card2b_carrier_prefix', '.noinit.card2b_carrier_tail']
    assert not set(additions) & set(value['names'])
    value['names'] += additions
    value['expected_names'] = len(value['names'])
    value['added_by_configured_profile'] += additions
    value['card2b'] = dict(authority=authority(), section=D.SECTION,
                          carrier=D.receipt('owner-projection.json')['owner'])
    return value


def additive_owner_closure(layout, golden, registered, proof_rows):
    """Prove the complete physical carrier before projecting additive freight.

    The prefix and tail are reserved owners, never holes.  Only this exact
    derived population is projected; the inherited closure still rejects
    every unrelated, missing, or doubly registered section.
    """
    from elf_truth import ElfTruth
    S = F.STORED
    contract = D.receipt('owner-projection.json')['owner']
    truth = ElfTruth.read(F.ELF, llvm_readobj=C.B.READOBJ)
    names = {D.SECTION, '.noinit.card2b_carrier_prefix', '.noinit.card2b_carrier_tail'}
    start = truth.symbol('__card2b_carrier_start').value
    end = truth.symbol('__card2b_carrier_end').value
    payload_start = truth.symbol('__card2b_payload_load_start').value
    payload_end = truth.symbol('__card2b_payload_load_end').value
    S.require((start, end, payload_start) ==
              (contract['start'], contract['end'], contract['payload']['start'])
              and payload_start % 256 == 0
              and start <= payload_start < payload_end <= end,
              'card2b carrier symbols differ from composed owner')

    def relation(candidate):
        rows = candidate['allocatable_sections']
        own = {r['name']: r for r in rows if r['name'] in names}
        S.require(len([r for r in rows if r['name'] in names]) == len(names)
                  and set(own) == names, 'card2b additive owner missing/duplicated')
        payload = own[D.SECTION]
        prefix = own['.noinit.card2b_carrier_prefix']
        tail = own['.noinit.card2b_carrier_tail']
        S.require(payload['vma'] == contract['window_vma']
                  and payload['lma'] == payload_start
                  and payload['bytes'] == payload_end - payload_start
                  and payload['section_type'] == 'SHT_PROGBITS'
                  and set(payload['flags']) == {'SHF_ALLOC', 'SHF_EXECINSTR'},
                  'card2b executable payload placement/type differs')
        for row, lo, hi in ((prefix, start, payload_start), (tail, payload_end, end)):
            S.require(row['vma'] == row['lma'] == lo and row['bytes'] == hi-lo
                      and row['section_type'] == 'SHT_NOBITS'
                      and set(row['flags']) == {'SHF_ALLOC'},
                      'card2b NOLOAD carrier reservation differs')
        for row in rows:
            if row['name'] not in names and row['bytes']:
                physical = row['lma']
                if physical is None:
                    S.require(row['section_type'] == 'SHT_NOBITS',
                              'file-backed foreign owner has no physical address')
                    physical = row['vma']
                S.require(physical + row['bytes'] <= start or physical >= end,
                          'foreign physical owner overlaps card2b carrier')

    relation(layout)
    rejected = []
    for name in sorted(names):
        for field in ('vma', 'lma', 'bytes', 'section_type'):
            bad = deepcopy(layout)
            row = next(r for r in bad['allocatable_sections'] if r['name'] == name)
            row[field] = 'SHT_NULL' if field == 'section_type' else row[field] + 1
            label = name + ':' + field
            try: relation(bad)
            except S.ConversionError: rejected.append(label)
            else: raise S.ConversionError('carrier mutation survived: ' + label)
        bad = deepcopy(layout)
        bad['allocatable_sections'] = [r for r in bad['allocatable_sections'] if r['name'] != name]
        try: relation(bad)
        except S.ConversionError: rejected.append(name + ':omitted')
        else: raise S.ConversionError('carrier omission survived')
    bad = deepcopy(layout)
    foreign = deepcopy(next(r for r in bad['allocatable_sections'] if r['name'] == D.SECTION))
    foreign['name'] = '.mutation.foreign-carrier-owner'
    bad['allocatable_sections'].append(foreign)
    try: relation(bad)
    except S.ConversionError: rejected.append('foreign-physical-overlap')
    else: raise S.ConversionError('carrier overlap survived')
    S.require(not names & (registered | S.V4_GOLDEN.all_names(golden)),
              'card2b carrier has double authority')
    base = deepcopy(layout)
    base['allocatable_sections'] = [r for r in base['allocatable_sections'] if r['name'] not in names]
    value = F.successor_additive_closure(base, golden, registered, proof_rows)
    value['card2b_carrier'] = dict(status='passed', registered_sections=sorted(names),
        authority=C.bind(D.EVIDENCE/'owner-projection.json'), elf=C.bind(F.ELF),
        relation='NOLOAD-prefix / ELF-LOADADDR-payload / NOLOAD-tail exactly partition carrier',
        mutations_rejected=rejected)
    (PREFLIGHT/'final-additive-carrier-proof.json').write_bytes(C.canonical(value['card2b_carrier']))
    return value


def descriptor_successor():
    """Retention changes the containing loader, not the EDMA byte contract."""
    import capacity_disk_window_descriptor_gate as gate
    proof = gate.run()
    from elf_truth import ElfTruth
    old, new = [ElfTruth.read(p, llvm_readobj=C.B.READOBJ, include_section_data=True)
                for p in (A.PREDECESSOR['ELF'], F.ELF)]
    def identity(row):
        return (row['section'], row['code_owner'], row['trigger_register'],
                tuple(row['descriptor_owners']))
    before, after = [{identity(r):r for r in C.B.descriptor_trigger_inventory(t)}
                     for t in (old, new)]
    assert before.keys() == after.keys() and len(after) == 9
    rows = []
    for key in sorted(after):
        a,b = before[key],after[key]
        assert a['trigger_normalized_hex'] == b['trigger_normalized_hex']
        if key[1] == 'vm_runtime_overlay_exec_family':
            family = 'executed-emitted-descriptor-and-trigger-contract'
        else:
            assert (a['code_region_bytes'],a['code_region_normalized_sha256'],a['code_region_relocations']) == \
                   (b['code_region_bytes'],b['code_region_normalized_sha256'],b['code_region_relocations']), key
            family = 'relocation-normalized-producer-identity'
        rows.append(dict(identity=key, family=family, before=a, after=b))
    for truth in (old,new):
        job=truth.symbol('rtov_edma_job');bss=truth.section('.bss')
        assert job.section=='.bss' and job.bytes==20
        assert bss.address<=job.value and job.value+job.bytes==bss.address+bss.bytes
    sealed=C.ARCH/'block-2.6-card6-small-hardening-dma-tuple-repair-r3-receipt.json'
    value=deepcopy(C.load(sealed)['final_product']['small_hardening']['descriptor_emission'])
    value['successor_neutrality']=dict(predecessor=C.bind(A.PREDECESSOR['ELF']),
        candidate=C.bind(F.ELF), final_trigger_sites=rows,
        emitted_descriptor_proof=proof, BSS_tail_owner_bytes=20,
        claim='Loader retention is intentional; only descriptor/trigger semantics are unchanged.')
    return value


def attribution():
    import f011_frame_attribution as engine
    from elf_truth import ElfTruth
    configure()
    engine.D = F
    sources = D.sources()
    generated = F.WPLTO/'generated-product-sources'
    for name, text in sources.items():
        assert (generated/Path(name).name).read_text() == text
    changed = {'013-io.c.o':'src/io.c', '022-vm.c.o':'src/vm.c',
               '024-vm_runtime_overlay.c.o':'src/vm_runtime_overlay.c'}
    def c_proof(name, before, after, left, right):
        if name not in changed: return None
        source=changed[name]
        return dict(status='PASS',family='bound Card-2b source projection: '+source,
            projected_source=C.bind(generated/Path(source).name),
            projection=C.bind(Path(D.__file__)), source_contract=source_gate(),
            scope='member placement / unchanged PID22 bridge / validated retention; no parked 2a')
    def asm_proof(name,before,after):
        assert name=='047-f011_guarded_write.s.o', 'uncommissioned assembler delta: '+name
        a,b=[ElfTruth.read(p,llvm_readobj=C.B.READOBJ,include_section_data=True) for p in (before,after)]
        sections=['.text.lisp65_f011_mount_token_op','.text.lisp65_f011_scratch_buffer']
        raw=b''.join(a.section_bytes(n) for n in sections)
        assert raw==b.section_bytes(D.SECTION)
        offsets={sections[0]:0,sections[1]:a.section(sections[0]).bytes}
        old=sorted((r.offset+offsets[r.source_section],r.relocation_type,r.target,r.addend) for r in a.relocations)
        new=sorted((r.offset,r.relocation_type,r.target,r.addend) for r in b.relocations)
        assert old==new
        assert a.section('.bss.f011_guard').bytes==b.section('.bss.f011_guard').bytes
        return dict(status='PASS',family='two unchanged assembly bodies concatenated in cold member',
                    bytes=len(raw),relocations_equal=True,source=C.bind(generated/'f011_guarded_write.s'))
    for seed in (True,False):
        value=engine.derive(seed,asm_attributor=asm_proof,c_attributor=c_proof)
        value['role']='CARD2B-RENDERER-SUCCESSOR'
        value['source_projection']=source_gate()
        value['claim']='Closed compiler-root attribution plus complete linked delta enumeration; not byte-local causal uniqueness.'
        path=BUILD/('seed-to-final-attribution.json' if seed else 'predecessor-attribution.json')
        path.write_bytes(C.canonical(value))
        print('ATTRIBUTION PASS',path.name,len(value['compiler_roots']),'roots')


def configure():
    A.BUILD, A.PREFLIGHT, A.AUTHORIZATION = BUILD, PREFLIGHT, D.AUTHORIZATION
    A.AUTHORED = ('src/io.c','src/vm.c','src/f011_guarded_write.s',
                  'src/vm_runtime_overlay.c','src/rtov_crc_mem.s')
    A.authority, A.expected_features, A.feature_authority = authority, expected_features, feature_authority
    A.profile, A.source_gate, A.source_population = profile, source_gate, source_population
    ORIGINAL_CONFIGURE()
    PRODUCT.SESSION_RECORD_CACHE_ENABLED = False
    F.DRIVER = Path(__file__).resolve()
    C.DRIVER = F.DRIVER
    C.B.DRIVER = F.DRIVER
    for module in (F, C, C.B):
        module.FORMAT = 'capacity-disk-window-r1'
        module.STATUS = 'PENDING: CARD 2b SEED PRICE AND QUALIFICATION'
        module.PLAN_HEADER = '### Card 2b — retention stays in the form; the seed measures the net (2026-09-07)'
        module.REPORT = ROOT/'docs/planning/capacity-disk-window-product-report.md'
    LEAF.materialize_candidate_sources = materialize
    LEAF.projected_source_list = projected_sources
    C.B.PREV.CARD.CARD2.R2.CARD.projected_source_list = projected_sources
    PRODUCT.linker_script = linker_script
    PRODUCT.final_section_inventory_expectation = inventory
    PRODUCT.configure_append_slices = configure_append
    F.STORED._additive_section_closure = additive_owner_closure
    C.PREVIOUS.R2.descriptor_emission_gate = descriptor_successor
    bind_member()


def configure_append(slices):
    ORIGINAL_APPEND(slices)
    bind_member()


def final_product():
    """Reuse the frozen seed; exactly one final C/LTO and product link."""
    import capacity_disk_window_media as media
    configure()
    qualification = D.EVIDENCE/'seed-native-qualification.json'
    q = C.load(qualification)
    assert q['status'] == 'PASS: BOUNDED SEED NATIVE PREREQUISITES'
    assert q['authorization'] == 'df7cd1fe'
    for name in ('costs', 'member_error_recovery', 'closure', 'data_gate',
                 'observed', 'control', 'observer_identity', 'control_identity',
                 'disk_observed', 'disk_control'):
        item = q[name]
        assert C.bind(ROOT/item['path'])['sha256'] == item['sha256'], name
    stamp = BUILD/'final-product-invocation.json'
    attempt_path = BUILD/'final-product-attempt.json'
    if stamp.exists():
        # Resume only the proved pre-compiler configuration stop. Preserve
        # both original records; this cannot authorize a replacement build.
        previous = C.load(attempt_path)
        assert previous['calls'] == [] and previous['final_C_LTO_invocations'] == 0
        assert not previous['ELF_present'] and not previous['PRG_present']
        assert previous['seed_before'] == previous['seed_after']
        stamp = BUILD/'final-product-invocation-r2.json'
        attempt_path = BUILD/'final-product-attempt-r2.json'
    assert not stamp.exists() and not attempt_path.exists() and not F.ELF.exists() and not F.PRG.exists()
    assert not (F.WPLTO/'.canonical-objects-lisp65-c2-substitution-linked').exists()
    status = subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).decode().splitlines()
    # The parallel agent's worktrees are outside the product input population.
    # No tracked modification or other untracked path is accepted.
    assert all(row == '?? .claude/' for row in status), status
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    upstream = subprocess.check_output(['git','rev-parse','@{upstream}'],cwd=ROOT).decode().strip()
    assert head == upstream, 'final producer must be remote-visible'
    seed = F.WPLTO/'resident-island-seed.prg'
    paths = [Path(str(seed)+s) for s in ('','.elf','.lto.o','.map')]
    frozen = [C.bind(p) for p in paths]
    assert frozen == C.load(PREFLIGHT/'seed-attempt.json')['artifacts']
    assert frozen[1]['sha256'] == q['elf']['sha256']
    original = PRODUCT.compile_link
    # The producer child configures its world once. Calling media.setup()
    # here would install the same historical root hooks a second time.
    # Only artifact pack/validation hooks belong at this boundary.
    PRODUCT.overlay_pack_family = media.pack_family
    PRODUCT._validate_family_artifact = media.validate
    PRODUCT._family_identity_negative_selftest = media.negative
    media.FINAL = F.WPLTO
    link = LEAF
    materializer = link.materialize_candidate_sources
    existing = F.WPLTO/'generated-product-sources'
    calls = []
    def reuse(out):
        with tempfile.TemporaryDirectory(dir=BUILD,prefix='final-source-check-') as tmp:
            mapping = materializer(Path(tmp))
            before = {p.name:C.bind(p)['sha256'] for p in existing.iterdir() if p.is_file()}
            after = {p.name:C.bind(p)['sha256'] for p in (Path(tmp)/'generated-product-sources').iterdir() if p.is_file()}
            assert before == after, 'final sources differ from frozen seed'
            assert all('.claude' not in p.parts for p in mapping), 'foreign worktree became an input'
            return {s:existing/p.name for s,p in mapping.items()}
    def finish(out,name,headers,artifacts,**kwargs):
        assert out == F.WPLTO and frozen == [C.bind(p) for p in paths]
        calls.append(name)
        if name == seed.name:
            assert calls == [seed.name]
            PRODUCT.final_section_inventory_gate(out,seed)
            PRODUCT.lto_partition_metadata_gate(out,seed)
            return seed
        assert calls == [seed.name,F.PRG.name], 'extra compiler/link invocation forbidden'
        return original(out,name,headers,artifacts,**kwargs)
    stamp.write_bytes(C.canonical(dict(authority=authority(),cost_disposition='df7cd1fe',
        native_qualification=C.bind(qualification),commit=head,seed=frozen,
        excluded_workspace_noise=status,seed_rebuilds=0,
        budget=dict(seed_WPLTO=1,final_C_LTO=1,product_links=1))))
    link.materialize_candidate_sources = reuse
    PRODUCT.compile_link = finish
    try:
        try: C.B.child('_produce')
        except SystemExit as stop: assert stop.code == 0
    finally:
        PRODUCT.compile_link = original
        link.materialize_candidate_sources = materializer
        after = [C.bind(p) for p in paths]
        attempt_path.write_bytes(C.canonical(dict(
            calls=calls,seed_before=frozen,seed_after=after,
            ELF_present=F.ELF.exists(),PRG_present=F.PRG.exists(),
            seed_rebuilds=0,final_C_LTO_invocations=int(F.PRG.name in calls))))
        assert frozen == after


def qualify_read_only(action):
    import capacity_disk_window_media as media
    assert action in ('_scope', '_accept')
    configure()
    paths = [Path(str(F.PRG)+suffix) for suffix in ('','.elf','.lto.o','.map')]
    before = [C.bind(p) for p in paths]
    def forbidden(*args, **kwargs):
        raise RuntimeError('qualification cannot invoke a product compiler/link')
    PRODUCT.compile_link = forbidden
    PRODUCT.overlay_pack_family = media.pack_family
    PRODUCT._validate_family_artifact = media.validate
    PRODUCT._family_identity_negative_selftest = media.negative
    try:
        C.B.child(action)
    finally:
        assert before == [C.bind(p) for p in paths], 'qualification changed product artifacts'


def bind_member():
    # Initial module setup still has the historical pre-service catalog.
    # Admission happens only when the inherited world builder has selected
    # the complete Renderer population, never by adding to that old catalog.
    predecessor = json.loads((D.BASE/'runtime-overlays-session-final.json').read_text())
    expected = [(r['id'], r['name']) for r in predecessor['slices']]
    actual = [(int(s.split(':')[0]), s.split(':')[1]) for s in PRODUCT.SESSION_SLICE_SPECS]
    if actual != expected:
        return
    if not any(spec.split(':')[2] == D.SECTION for spec in PRODUCT.SESSION_SLICE_SPECS):
        slot = len(PRODUCT.SESSION_SLICE_SPECS)
        assert slot == 52, 'private member slot no longer matches derived catalog'
        PRODUCT.SESSION_SLICE_SPECS.append(
            f'{slot}:f011-write-member:{D.SECTION}:__lisp65_rt_card2b_disk_start:'
            '__lisp65_rt_card2b_disk_end:__lisp65_rt_card2b_disk_entry:'
            'runtime+reusable:1:0:card2b_disk_entry:2')
        PRODUCT.UNIQUE_SLICE_COUNT += 1


if __name__ == '__main__':
    A.configure = configure
    if sys.argv[1:] == ['preflight']:
        preflight()
    elif sys.argv[1:] == ['seed']:
        produce_seed()
    elif sys.argv[1:] == ['seed-data-gate']:
        seed_data_gate()
    elif sys.argv[1:] == ['final-data-gate']:
        seed_data_gate('lisp65-c2-substitution-linked.prg')
    elif sys.argv[1:] == ['final-product']:
        final_product()
    elif sys.argv[1:] in (['_scope'], ['_accept']):
        qualify_read_only(sys.argv[1])
    elif sys.argv[1:] == ['attribution']:
        attribution()
    else:
        raise SystemExit('Choose preflight, seed, seed-data-gate or qualified final-product')
