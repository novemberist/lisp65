#!/usr/bin/env python3
"""Write-once r4 successor including editor-slots.

Derived commands and complete media reconstruction follow the r3 successor.
Only Lisp changes and derived native constants are authorized.
No Git, emulator, network or device operations. All output is write-once.
"""
import copy
import json
import os
import re
import struct
from pathlib import Path
import strings_seed_producer as S
import o2_lite_r3_price as PRICE
import o2_lite_r3_host as HOST
import o2_lite_r4_host as HOST4
import bytecode_p0_stdlib as P

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT/'build/o2-lite-r4-slots-preflight/native'
BUILD = ROOT/'build/o2-lite-product-r4'
FINAL = ROOT/'build/strings-final-r1'
PLANE = ROOT/'build/strings-r7/seed/plane/candidate'
PREFLIGHT = ROOT/'build/o2-lite-r4-slots-preflight'
BASE_MEDIA_SHA = '9978daa146b89cf71ad1d3f290d80cf74b197911e7854859f9e4aa9bb2fce441'
LIBRARY_BOUND = 3000
TOOLING = HERE/'postlink-tooling.json'

def reviewed(): return load(PREFLIGHT/'planes/price.json')
def library_bytes(): return reviewed()['library']['bytes']
def resident_delta(): return reviewed()['resident_delta']
def code_bytes(): return 50007 + resident_delta()
def static_deltas(): return reviewed()['static_plane_deltas']
sha, bind, checked, load, run = S.sha, S.bind, S.checked, S.load, S.run
native_stdlib_header = S.native_stdlib_header


def once(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw.encode() if isinstance(raw,str) else raw)


def save(path, value):
    once(path,json.dumps(value,indent=2,sort_keys=True)+'\n')


def budget(price):
    assert price['bytes']<=3000 and max(e['bytes'] for e in price['entries'])<=255


def cost_gate(cost):
    assert len(cost['rows'])==3
    rows=cost['rows']+[next(r for r in cost['boundaries'] if r['name']=='single-line-250')]
    for row in rows:
        for phase in ('reader_handoff','result_line','new_empty_prompt'):
            old,new=row['v251'][phase],row['r4'][phase]
            assert new['buffer_overlays']==0
            for key in ('library_calls','all_code_reloads','instructions'):
                assert new[key]<=old[key]*1.15,(row.get('name',row['form']),phase,key)
    # Reviewer explicitly accepts the bounded slow path above 259 source bytes.
    for size in (260,400,640):
        row=next(r for r in cost['boundaries'] if r['name']=='large-form-'+str(size))
        assert len(row['form'])==size
        assert row['r4']['new_empty_prompt']['buffer_overlays']>0


def gates():
    host=load(PREFLIGHT/'host/receipt.json')
    assert host['status']=='PASS' and host['sources']==HOST4.bindings()
    heap=load(PREFLIGHT/'host/heap/heap.json')
    assert heap['status']=='PASS' and heap['cells']+520<=1072 and heap['arena']+2048<=9344 and heap['root_peak']<=128
    assert len(heap['rows'])==16
    batch=load(PREFLIGHT/'batch-heap/receipt.json')
    assert batch['status']=='PASS' and batch['sources']==HOST4.bindings() and len(batch['rows'])==6
    assert load(PREFLIGHT/'host/calls/resident-calls.json')['library_calls_per_key']==0
    cost=load(PREFLIGHT/'cost-final/cost.json');cost_gate(cost)
    assert cost['sources']==HOST4.bindings()
    price=load((PREFLIGHT/'planes')/'price.json');assert price['status']=='PASS';budget(price['library'])
    suite=P._read_suite(str(ROOT/'config/comfort-default-plane/libraries/repl-comfort-suite.json'))
    suite['resident_suite']=str((PREFLIGHT/'planes')/'resident.json')
    assert PRICE.measure(suite)==price['library']
    assert HOST.project_editor()==((PREFLIGHT/'planes')/'product-editor.lisp').read_text()
    for name in ('copy-heap','typeahead-queued'):
        proof=load(PREFLIGHT/name/'receipt.json')
        assert proof['status']=='PASS' and proof['sources']==HOST4.bindings()
    assert load(PREFLIGHT/'slots/receipt.json')['sources']==HOST4.bindings()
    assert load(PREFLIGHT/'slots/receipt.json')['status']=='PASS'
    return [bind(PREFLIGHT/p) for p in ('host/receipt.json','host/heap/heap.json','cost-final/cost.json','planes/price.json','batch-heap/receipt.json','slots/receipt.json','copy-heap/receipt.json','typeahead-queued/receipt.json')]


def prepare():
    proofs=gates()
    assert not BUILD.exists(), 'Seed already claimed'
    HERE.mkdir()
    old=ROOT/'build/strings-r7/seed'
    frozen=load(old/'derived-inputs.json')
    original=load(old/'command-ready.json')
    toolchain={r['restored']['path'].replace('/native-inputs/','/candidate-inputs/',1):r['source']
               for r in original['native'] if r['source']['path'].startswith('tools/llvm-mos/')}
    native=[]
    prefix=old/'candidate-inputs'
    for row in frozen['all_generated']:
        source=ROOT/row['path'];raw=checked(row)
        target=HERE/'native-inputs'/source.relative_to(prefix)
        once(target,raw);native.append(dict(source=toolchain.get(row['path'],row),restored=bind(target)))
    source=ROOT/frozen['generated']['path']
    target=HERE/'native-inputs/derived-current'/source.relative_to(old/'derived')
    once(target,checked(frozen['generated']))
    native.append(dict(source=frozen['generated'],restored=bind(target)))
    replacements={str(prefix.relative_to(ROOT)):str((HERE/'native-inputs').relative_to(ROOT)),
                  str(source.relative_to(ROOT)):str(target.relative_to(ROOT)),
                  'build/strings-product-r3':str(BUILD.relative_to(ROOT))}
    commands=load(old/'command-proof.json')['commands']
    vm=[c for c in commands if '-c' in c and c[c.index('-c')+1].endswith('/vm.c')]
    assert len(vm)==1 and '-DLISP65_FIRST_CLASS_BUFFER' in vm[0]
    assert not any('LISP65_BUFFER_NO_PRIMS' in arg for arg in vm[0])
    for a,b in replacements.items(): commands=[[x.replace(a,b) for x in c] for c in commands]
    save(HERE/'baseline-command-proof.json',dict(commands=commands,frozen=bind(old/'command-proof.json')))
    # Paired emission was already gated; preserve every artifact in this input world.
    for path in sorted((PREFLIGHT/'planes').rglob('*')):
        if path.is_file(): once(HERE/'plane'/path.relative_to(PREFLIGHT/'planes'),path.read_bytes())
    price=load(PREFLIGHT/'planes/price.json')
    plane=dict(before_product=price['plane']['products']['baseline'],after_product=price['plane']['products']['candidate'],
        before_geometry=dict(code_bytes=50007),after_geometry=dict(code_bytes=code_bytes()),
        libraries=dict(baseline=dict(code_bytes=1060),candidate=dict(code_bytes=library_bytes(),
            blob=bind(PREFLIGHT/'planes/repl-comfort.blob.bin'),manifest=bind(PREFLIGHT/'planes/repl-comfort.manifest.json'))),
        artifacts=[bind(p) for p in sorted((HERE/'plane').rglob('*')) if p.is_file()])
    save(HERE/'plane-price.json',plane)
    ident=load(FINAL/'final-identity.json')
    base_native={Path(x['final']['path']).suffix: x['final'] for x in ident['artifacts']}
    for row in base_native.values():checked(row)
    raw=checked(ident['media'][0]['final']);assert sha(raw)==BASE_MEDIA_SHA
    import d81_persistence_fault as D
    files=D.visible_files(raw)
    packages=load(FINAL/'media/runtime-receipt.json')['packages']
    closure=[dict(source=bind(PLANE/n),restored=bind(HERE/'plane/baseline'/n)) for n in ('CODE.BIN','C2D.BIN','SHELF.BIN')]
    ready=dict(authority='reviewer-authorized O2-lite r4 plus editor-slots working tree',native=native,closure=closure,
        commands=bind(HERE/'baseline-command-proof.json'),base_native=base_native,
        gates=proofs,media_authority=dict(medium=ident['media'][0]['final'],packages=packages,
        files={n.decode():dict(bytes=len(v),sha256=sha(v)) for n,v in files.items()}))
    commands=derived_commands(ready,plane)
    # Reuse strict include closure with every generated file explicitly bound.
    S.HERE=HERE
    S.include_closure(commands,ready)
    ready['prepared']=[bind(p) for p in sorted(HERE.rglob('*')) if p.is_file()]
    ready['sources']=[bind(ROOT/p) for p in ('lib/stdlib-read-line.lisp','lib/repl-comfort-v250.lisp',
        'lib/lite.lisp','lib/lite-hot.lisp','lib/sexp-depth.lisp','config/comfort-default-plane/libraries/repl-comfort-suite.json',
        'tools/host-lisp/o2_lite_r3_host.py','tools/host-lisp/o2_lite_r3_price.py',
        'tools/host-lisp/o2_lite_r4_product.py',
        'tools/host-lisp/o2_lite_r4_cost.py','tools/host-lisp/o2_lite_r4_host.py',
        'tools/host-lisp/o2_lite_r4_slots.py','tools/host-lisp/o2_lite_r4_typeahead.py',
        'tools/host-lisp/o2_lite_seed_producer_20260929.py',
        'build/editor-slots-r1/measure.py','build/code-object-cache-r1/window_replay.py')]
    ready['source_snapshots']=[]
    for row in ready['sources']:
        path=HERE/'authored'/row['path'];once(path,checked(row))
        ready['source_snapshots'].append(dict(source=row,snapshot=bind(path)))
    save(HERE/'command-ready.json',ready)
    return dict(status='PASS',commands=len(commands),ready=bind(HERE/'command-ready.json'))


def verify_ready(*,acceptance=False):
    ready=load(HERE/'command-ready.json')
    for key in ('gates','prepared'):
        for row in ready[key]:checked(row)
    amendments=load(TOOLING) if TOOLING.exists() else None
    for pair in ready['source_snapshots']:
        assert sha(checked(pair['snapshot']))==pair['source']['sha256']
    for row in ready['sources']:
        if amendments and row['path']==amendments['original']['path']:
            assert row==amendments['original']
            saved=checked(amendments['snapshot'])
            assert sha(saved)==row['sha256'] and len(saved)==row['bytes']
            assert amendments['replacement']['path']==row['path']
            checked(amendments['replacement']);checked(amendments['native_projection'])
        else:checked(row)
    for row in ready['native']:checked(row['source']);checked(row['restored'])
    for row in ready['base_native'].values():checked(row)
    checked(ready['media_authority']['medium'])
    return ready


def seed():
    ready=verify_ready()
    assert not BUILD.exists(), 'Seed already claimed; no retry'
    BUILD.mkdir()
    save(BUILD/'attempt.json',dict(status='STARTED',producer=bind(Path(__file__)),ready=bind(HERE/'command-ready.json')))
    try:
        for i,command in enumerate(load(HERE/'command-proof.json')['commands']):
            if i==74:save(BUILD/'product-link-claim.json',dict(product_links=1))
            (ROOT/command[command.index('-o')+1]).parent.mkdir(parents=True,exist_ok=True)
            run(command,BUILD/f'command-{i:03d}.log')
            print(f'completed frozen command {i+1}/75',flush=True)
        native={role:bind(BUILD/'wplto'/Path(row['path']).name) for role,row in ready['base_native'].items()}
        save(BUILD/'linked.json',dict(status='LINKED',seed=1,final=0,product_links=1,native=native))
        return dict(status='LINKED',native=native)
    except BaseException as error:
        save(BUILD/'halt.json',dict(status='HALT',error=repr(error)))
        raise


def accepted_price_path():return HERE/'price.json'


def project_delivery_code(delivered,baseline,candidate):
    assert delivered[:len(baseline)]==baseline
    assert len(candidate)-len(baseline)==resident_delta() and len(candidate)<=60758
    assert not any(delivered[len(baseline):len(candidate)]), 'native owner overlap'
    result=bytearray(delivered);result[:len(candidate)]=candidate
    assert result[len(candidate):]==delivered[len(candidate):]
    return result


def rebind_family(C,fam,value,regions,a,b,elf):
    import o2_lite_r4_native as N
    N.prove(a,b)
    for row in value['slices']:
        old,new=a.section_bytes(row['section']),b.section_bytes(row['section'])
        assert len(old)==row['file_size']==row['memory_size']
        assert len(new)<=len(old) and (len(new)==len(old) or row['section'] in N.SIZES)
        at,rid=row['file_offset'],row['region_id']
        assert regions[rid][at:at+len(old)]==old
        regions[rid][at:at+len(old)]=new+bytes(len(old)-len(new))
        row.update(file_size=len(new),memory_size=len(new),end=row['vma']+len(new),
                   sha256=sha(new),crc16=C.BANK.crc16_ccitt_false(new))
        at=32+32*row['id']
        struct.pack_into('<H',regions[0],at+6,len(new))
        struct.pack_into('<H',regions[0],at+10,len(new))
        struct.pack_into('<H',regions[0],at+20,row['crc16'])
        regions[0][at+22:at+24]=bytes(2)
        row['record_crc16']=C.BANK.crc16_ccitt_false(regions[0][at:at+32])
        struct.pack_into('<H',regions[0],at+22,row['record_crc16'])
    if fam=='session':
        row=next(r for r in value['slices'] if r['section']==N.CRC_SECTION)
        alignment=value['policy']['payload_alignment'];assert alignment==32
        following=min(r['file_offset'] for r in value['slices'] if r['region_id']==0 and r['file_offset']>row['file_offset'])
        next_offset=row['file_offset']+((row['file_size']+alignment-1)//alignment)*alignment
        released=following-next_offset
        assert released in (0,32), 'unproved catalog alignment change'
        assert not any(regions[0][next_offset:following])
        del regions[0][next_offset:following]
        for moved in value['slices']:
            if moved['region_id']==0 and moved['file_offset']>=following:
                moved['file_offset']-=released;moved['source_address']-=released
                at=32+32*moved['id'];source=moved['source_address']
                struct.pack_into('<H',regions[0],at+4,source&65535)
                regions[0][at+25]=(source>>16)&15;regions[0][at+26]=(source>>20)&255
                regions[0][at+22:at+24]=bytes(2)
                moved['record_crc16']=C.BANK.crc16_ccitt_false(regions[0][at:at+32])
                struct.pack_into('<H',regions[0],at+22,moved['record_crc16'])
        value['storage']['size']=len(regions[0])
        struct.pack_into('<I',regions[0],20,len(regions[0]))
    crc=C.BANK.crc16_ccitt_false(regions[1])
    struct.pack_into('<I',regions[0],28,len(regions[1])|((crc if regions[1] else 0)<<16))
    C.BANK._refresh_catalog_crcs(regions[0])
    value['overflow_storage'].update(crc16=crc,sha256=sha(regions[1]))
    value['storage'].update(crc16=C.BANK.crc16_ccitt_false(regions[0]),sha256=sha(regions[0]))
    value['catalog'].update(directory_crc16=int.from_bytes(regions[0][24:26],'little'),header_crc16=int.from_bytes(regions[0][26:28],'little'))
    if fam=='session':value['external_storage'].update(crc16=C.BANK.crc16_ccitt_false(regions[2]),sha256=sha(regions[2]))
    value['elf']=dict(bind(elf),file=str(elf))
    return C.validate_family(fam,value,regions,a,b)


def emit_media_library(C,med,libraries,build_id):
    suite=P._read_suite(str(ROOT/'config/comfort-default-plane/libraries/repl-comfort-suite.json'))
    suite['resident_suite']=str(PREFLIGHT/'planes/resident.json')
    path=med/'repl-comfort'
    P.emit_artifacts(str(ROOT/'config/comfort-default-plane/libraries/repl-comfort-suite.json'),suite,str(path),base_addr=0,artifact_role='disk-lib')
    manifest=path.with_suffix('.manifest.json');blob=path.with_suffix('.blob.bin')
    assert blob.read_bytes()==checked(libraries['candidate']['blob'])
    assert load(manifest)['code_bytes']==library_bytes()<=3000
    args=('repl-comfort','repl-comfort','repl')
    row,payload=C.L.F.measured_row(*args,manifest,(),1,1,product_build_id=build_id)
    assert (row,payload)==C.L.F.measured_row(*args,ROOT/libraries['candidate']['manifest']['path'],(),1,1,product_build_id=build_id)
    return manifest,dict(status='PASS',bank2_bytes=library_bytes(),bound=3000,artifact_bytes=len(payload),manifest=bind(manifest),blob=bind(blob))


def media_plane_control(ready,before):
    S.HERE,S.PLANE=HERE,PLANE
    return S.media_plane_control(ready,before)


def pack_media(C,med,artifacts,before_raw,packages,build_id,derived):
    S.HERE=HERE
    # The r3 package adds roots; all other package metadata remains constrained.
    S.project_delivery_code=project_delivery_code
    S.media_index_control=media_index_control
    result=S.pack_media(C,med,artifacts,before_raw,packages,build_id,derived)
    once(med/'o2lite.d81',checked(result['medium']))
    result['medium']=bind(med/'o2lite.d81')
    return result


def media_index_control(L,before,rows):
    old=L.decode_index(before)
    assert len(old)==len(rows)==6
    for a,b in zip(old,rows,strict=True):
        allowed={'artifact_bytes','bank2','combined_crc32','entries','resolutions','roots','scratch'} if a['name']=='repl-comfort' else set()
        assert a.keys()==b.keys() and all(a[k]==b[k] for k in a if k not in allowed), 'foreign index mutation'
    return L.encode_index(rows)


def inventory():
    from elf_truth import ElfTruth
    import o2_lite_r4_native as N
    ready=verify_ready(acceptance=True)
    paths=[FINAL/'wplto/resident-island-seed.prg.elf',BUILD/'wplto/resident-island-seed.prg.elf']
    truths=[ElfTruth.read(p,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True) for p in paths]
    a,b=truths
    N.prove(a,b)
    assert b.symbol('lisp65_comfort_state').value==0xbff6
    S.HERE=HERE
    result=N.inventory(paths,[p.read_bytes() for p in paths],truths,HERE)
    result['negative_controls']=N.selftest(paths,truths,HERE)
    result.update(ELFs=[bind(p) for p in paths],plane=bind(HERE/'plane-price.json'),derived=bind(HERE/'derived-inputs.json'),
        classification_tool=bind(Path(N.__file__)))
    save(HERE/'inventory.json',result)
    assert result['status']=='PASS' and result['unclassified_bytes']==0
    save(HERE/'price.json',dict(status='PASS',resident_native_growth=0,native_symbol_growth=0,
        overlay_deltas={k:y-x for k,(x,y) in N.SIZES.items()},
        library=library_bytes(),resident_delta=resident_delta(),static_deltas=static_deltas()))
    return result


def derived_commands(ready, plane):
    import runtime_overlay_bank as BANK
    commands = load(HERE / 'baseline-command-proof.json')['commands']
    source = ROOT / commands[29][commands[29].index('-c') + 1]
    original = source.read_text()
    projected = original
    changes = []
    for name, file, offset in [('shelf', 'SHELF.BIN', 32), ('c2d', 'C2D.BIN', None)]:
        raw = [(HERE / 'plane' / side / file).read_bytes() for side in ('baseline', 'candidate')]
        if offset is None:
            offset = struct.unpack_from('<H', raw[0], 28)[0]
            assert offset == struct.unpack_from('<H', raw[1], 28)[0]
        values = [[BANK.crc16_ccitt_false(data[offset+i*32:offset+(i+1)*32]) for i in range(6)] for data in raw]
        def emitted(crcs):
            return 'c2_phase02a_' + name + '_crc16:\\n' + '\\n'.join(f'.short 0x{x:04x}' for x in crcs) + '\\n'
        old, new = map(emitted, values)
        assert projected.count(old) == 1, name
        projected = projected.replace(old, new)
        changes.append(dict(table=name, before=values[0], after=values[1]))
    target = HERE / 'derived' / source.relative_to(HERE / 'native-inputs')
    # Keep quoted decoder includes at their frozen locations through -I.
    once(target, projected)
    before, after = plane['before_product'], plane['after_product']
    replacements = {str(source.relative_to(ROOT)): str(target.relative_to(ROOT)),
        '-DLISP65_C2_PRODUCT_BUILD_ID=' + before['product_build_id_hex'] + 'UL':
        '-DLISP65_C2_PRODUCT_BUILD_ID=' + after['product_build_id_hex'] + 'UL',
        '-DLISP65_C2_PRODUCT_SHELF_BYTES=' + str(before['artifacts']['shelf']['bytes']) + 'UL':
        '-DLISP65_C2_PRODUCT_SHELF_BYTES=' + str(after['artifacts']['shelf']['bytes']) + 'UL'}
    assert len(commands) == 75
    assert all(any(key in command for command in commands) for key in replacements), 'derived input not consumed'
    updated = [[replacements.get(a, a) for a in c] for c in commands]
    # Materialize a candidate include world, retaining the frozen baseline.
    # All copies are enumerated; quoted includes and forced includes therefore
    # resolve to the same explicitly derived header values.
    candidate_prefix=HERE/'candidate-inputs'
    generated=[];header_changes=[]
    old_size=load(HERE/'plane/baseline/stdlib-p0.manifest.json')['code_bytes']
    new_size=load(HERE/'plane/candidate/stdlib-p0.manifest.json')['code_bytes']
    old_code=plane['before_geometry']['code_bytes'];new_code=plane['after_geometry']['code_bytes']
    assert 0 < new_size-old_size <= 256 and new_code-old_code==new_size-old_size
    for row in ready['native']:
        path=ROOT/row['restored']['path']
        raw=checked(row['restored']);newraw=raw
        if path.name=='stdlib-p0.h' or (path.name=='c2_lite_static_plane.h' and f'STATIC_CODE_BYTES {old_code}UL'.encode() in raw):
            if path.name=='stdlib-p0.h':
                def tokens(text):return re.sub(r'/\* suite: .*? \*/','',text)
                before_header=native_stdlib_header((HERE/'plane/baseline/stdlib-p0.h').read_text())
                after_header=native_stdlib_header((HERE/'plane/candidate/stdlib-p0.h').read_text())
                assert tokens(raw.decode())==tokens(before_header), 'frozen stdlib header not reproduced'
                ma,mb=[load(HERE/'plane'/s/'stdlib-p0.manifest.json') for s in ('baseline','candidate')]
                projection=before_header
                counts=[('BLOB_BYTES',old_size,new_size),
                        ('OBJECT_COUNT',len(ma['entries']),len(mb['entries'])),
                        ('EMBED_COUNT',len(ma['entries']),len(mb['entries'])),
                        ('DIRECTORY_BYTES',7*len(ma['entries']),7*len(mb['entries']))]
                counts += [(macro,len(ma[key]),len(mb[key])) for macro,key in
                           [('LITERAL_INDEX_COUNT','literal_index'),('LITERAL_NODE_COUNT','literal_nodes'),('LITERAL_PATCH_COUNT','literal_patches')]]
                for macro,x,y in counts:
                    old=f'#define LISP65_BYTECODE_STDLIB_{macro} {x}u'
                    new=f'#define LISP65_BYTECODE_STDLIB_{macro} {y}u'
                    assert projection.count(old)==1
                    projection=projection.replace(old,new)
                    newraw=newraw.replace(old.encode(),new.encode())
                assert tokens(projection)==tokens(after_header), 'unclassified stdlib header change'
                header_changes.append(dict(source=row['restored'],counts=counts,
                    address_projection=dict(emitted='0x000000',native='0x050000')))
                dest=candidate_prefix/path.relative_to(HERE/'native-inputs')
                once(dest,newraw);generated.append(bind(dest));continue
            else:
                old=f'#define LISP65_C2_LITE_STATIC_CODE_BYTES {old_code}UL'
                new=f'#define LISP65_C2_LITE_STATIC_CODE_BYTES {new_code}UL'
            assert raw.count(old.encode())==1, ('derived header seam',path)
            newraw=raw.replace(old.encode(),new.encode())
            header_changes.append(dict(source=row['restored'],before=old,after=new))
        if path.name.endswith('.compiler-input-assert.h'):
            old=f'LISP65_C2_LITE_STATIC_CODE_BYTES != {old_code}UL'
            new=f'LISP65_C2_LITE_STATIC_CODE_BYTES != {new_code}UL'
            assert raw.count(old.encode())==1, 'compiler input assertion drift'
            newraw=raw.replace(old.encode(),new.encode())
            header_changes.append(dict(source=row['restored'],before=old,after=new))
        dest=candidate_prefix/path.relative_to(HERE/'native-inputs')
        once(dest,newraw);generated.append(bind(dest))
    assert {'stdlib-p0.h','c2_lite_static_plane.h'} <= {Path(r['source']['path']).name for r in header_changes}
    oldprefix=str((HERE/'native-inputs').relative_to(ROOT))+'/'
    newprefix=str(candidate_prefix.relative_to(ROOT))+'/'
    updated=[[a.replace(oldprefix,newprefix) for a in c] for c in updated]
    save(HERE/'derived-inputs.json',dict(replacements=replacements,crc_tables=changes,
        generated=bind(target),all_generated=generated,before=bind(source),stdlib_header_changed=True,
        header_changes=header_changes,code_bytes_before=old_code,code_bytes_after=new_code,
        stdlib_bytes_before=old_size,stdlib_bytes_after=new_size))
    save(HERE/'command-proof.json',dict(commands=updated,authority=ready['authority'],
        allowed_substitutions=replacements,header_changes=header_changes,
        include_root_rebase=dict(before=oldprefix,after=newprefix),frozen=ready['commands']))
    return updated


def media(output=None):
    import comfort_default_media as C
    ready = verify_ready(acceptance=True)
    inv = load(HERE / 'inventory.json')
    assert inv['status'] == 'PASS' and inv['unclassified_bytes'] == 0
    assert load(accepted_price_path())['status'] == 'PASS'
    for row in load(BUILD / 'linked.json')['native'].values():
        checked(row)
    for row in inv['ELFs']:
        checked(row)
    checked(inv['plane']); checked(inv['derived'])
    for row in load(HERE / 'plane-price.json')['artifacts']:
        checked(row)
    authority_media = ready['media_authority']
    before_raw = checked(authority_media['medium'])
    assert sha(before_raw) == BASE_MEDIA_SHA
    before = C.L.D81.visible_files(before_raw)
    assert {n.decode(): dict(bytes=len(v), sha256=sha(v)) for n, v in before.items()} == authority_media['files']
    control = media_plane_control(ready, before)
    med = output if output is not None else BUILD / 'media-r4'
    med.mkdir(exist_ok=False)
    artifacts = med / 'artifacts'
    artifacts.mkdir()
    save(med / 'plane-control.json', control)
    for name, data in before.items():
        once(artifacts / name.decode().lower(), data)
    elf = ROOT / inv['ELFs'][1]['path']
    a, b = [C.ElfTruth.read(ROOT / r['path'], llvm_readobj=C.READOBJ, include_section_data=True) for r in inv['ELFs']]
    families, manifests = {}, []
    for fam in ('boot', 'session'):
        value = load(FINAL / 'media' / ('runtime-overlays-'+fam+'-final.json'))
        regions = {0: bytearray(before[(fam+'.bin').upper().encode()]),
                   1: bytearray((FINAL / 'media' / value['overflow_storage']['file']).read_bytes())}
        if fam == 'session':
            regions[2] = bytearray(a.section_bytes('.lisp65_rt_card2b_disk'))
        families[fam] = rebind_family(C, fam, value, regions, a, b, elf)
        (artifacts / (fam+'.bin')).write_bytes(regions[0])
        once(med / value['overflow_storage']['file'], regions[1])
        if fam == 'session':
            (artifacts / 'region1.bin').write_bytes(regions[1])
            code = bytearray(before[b'CODE.BIN'])
            assert code[0xee00:0xee00+len(regions[2])] == a.section_bytes('.lisp65_rt_card2b_disk')
            code[0xee00:0xee00+len(regions[2])] = regions[2]
            (artifacts / 'code.bin').write_bytes(code)
        path = med / ('runtime-overlays-'+fam+'-final.json')
        save(path, value); manifests.append(path)
    window = bytearray(before[b'WINDOW.BIN'])
    for section in a.sections:
        if section.name.startswith('.lisp65_c2_kernal_window.') and section.section_type != 'SHT_NOBITS':
            old, new = a.section_bytes(section.name), b.section_bytes(section.name)
            at = section.address-0xe000
            assert 0 <= at and at+len(old) <= len(window) and len(old) == len(new)
            assert window[at:at+len(old)] == old
            window[at:at+len(new)] = new
        elif section.name.startswith('.lisp65_c2_mapped_') and section.section_type != 'SHT_NOBITS':
            assert a.section_bytes(section.name) == b.section_bytes(section.name), section.name
    (artifacts / 'window.bin').write_bytes(window)
    assert a.section_bytes('.lisp65_c2_vectors') == b.section_bytes('.lisp65_c2_vectors')
    code = bytearray((artifacts / 'code.bin').read_bytes())
    baseline_code = (HERE / 'plane/baseline/CODE.BIN').read_bytes()
    candidate_code = (HERE / 'plane/candidate/CODE.BIN').read_bytes()
    once(med/'code-native-rebound.bin',code)
    code = project_delivery_code(code,baseline_code,candidate_code)
    (artifacts / 'code.bin').write_bytes(code)
    for name in ('SHELF.BIN', 'C2D.BIN'):
        candidate = (HERE / 'plane/candidate' / name).read_bytes()
        if name == 'C2D.BIN':
            assert len(candidate) == C.M.C2D_PREFIX_BYTES
            candidate += bytes(C.M.C2D_RESET_DOMAIN_BYTES - len(candidate))
        (artifacts / name.lower()).write_bytes(candidate)
    table = C.P.verifier_binding_bytes(*manifests)+C.P.family_stage_binding_bytes(*manifests)
    assert len(table) == 40
    once(med / 'runtime-overlay-verifier-bindings.bin', table)
    prg = med / 'lisp65-c2-substitution-linked.prg'
    once(prg, elf.with_suffix('').read_bytes())
    C.FACADE.materialize_facade(prg, elf, med / 'facade-materialization.json')
    unbound = prg.read_bytes()
    once(med / 'lisp65-c2-substitution-unbound.prg', unbound)
    C.PRG.from_elf(elf, unbound)
    raw = bytearray(unbound)
    at = b.section('.lisp65_runtime_overlay_verifier_bindings').address-int.from_bytes(raw[:2], 'little')+2
    raw[at:at+40] = table
    binding = load(FINAL / 'media/kernal-window-publish-last.json')
    crc = C.BANK.crc16_ccitt_false(window)
    binding['single_product_link_window'] = dict(bind(artifacts / 'window.bin'), crc16=f'0x{crc:04x}')
    for row in binding['binding_operands']:
        assert raw[row['file_offset']] == row['compiled_value']
        row['published_value'] = (crc >> 8) & 255 if row['name'].endswith('high') else crc & 255
        raw[row['file_offset']] = row['published_value']
    save(med / 'kernal-window-publish-last.json', binding)
    domain = set(range(at, at+40)) | {r['file_offset'] for r in binding['binding_operands']}
    assert len(raw) == len(unbound) and all(x == y or i in domain for i, (x, y) in enumerate(zip(unbound, raw)))
    save(med / 'total-publish-last-domain.json', dict(status='passed', changes_outside_declared_domains=0,
        declared_domain_bytes=len(domain), bound_product_sha256=sha(raw), unbound_product_sha256=sha(unbound)))
    prg.write_bytes(raw)
    (artifacts / 'lisp65.prg').write_bytes(C.PRG.from_elf(elf, bytes(raw), publication_dir=med))
    C.CAN.ARTIFACTS = artifacts
    _, geometry = C.CAN.build_boot_stage(elf, artifacts / 'profile')
    product = load(HERE / 'plane-price.json')['after_product']
    build_id = int(product['product_build_id_hex'], 16)
    packages = load(FINAL / 'media/runtime-receipt.json')['packages']
    assert len(packages) == 6 and {r['name'] for r in packages} == {r['name'] for r in authority_media['packages']}
    packages=copy.deepcopy(packages)
    comfort,=[r for r in packages if r['name']=='repl-comfort']
    manifest, library_proof = emit_media_library(C, med,
        load(HERE / 'plane-price.json')['libraries'], build_id)
    comfort['manifest'] = bind(manifest)
    for row in packages:
        checked(row['manifest'])
        entry, payload = C.L.F.measured_row(row['name'], row['name'], row['shelf'], ROOT / row['manifest']['path'],
            tuple(row['dependencies']), 1, 1, product_build_id=build_id)
        (artifacts / row['name']).write_bytes(payload)
        row['artifact']=bind(artifacts/row['name']);row['row']=entry
    save(med / 'runtime-receipt.json', dict(status='PASS', ELF=bind(elf), families=families,
        boot_geometry=geometry, product_build_id=build_id, packages=packages,
        comfort_bank2_bytes=library_proof['bank2_bytes'], library=library_proof))
    # The inherited cold delivery stager is not another product link.
    C.MED, C.ART, C.OUT, C.ELF = med, artifacts, HERE, elf
    C.run = lambda cmd: run(cmd, med / ('host-'+sha(str(cmd).encode())[:16]+'.log')).decode('latin1')
    C.M.ASM_CONTRACT_INCLUDE = med / 'stager-contract.inc'
    assembly = C.M.STAGER_S.read_text().replace(C.M.ASM_CONTRACT_INCLUDE_TOKEN,
        '.include "' + str(C.M.ASM_CONTRACT_INCLUDE.relative_to(ROOT)) + '"')
    C.M.ASM_CONTRACT_INCLUDE_TOKEN = '.include "' + str(C.M.ASM_CONTRACT_INCLUDE.relative_to(ROOT)) + '"'
    C.M.STAGER_S = med / 'cold-stager-chain.s'
    once(C.M.STAGER_S, assembly)
    C.M.run = lambda cmd, label: run(cmd, med / ('stager-'+sha(label.encode())[:16]+'.log')).decode('latin1')
    C.stager()
    # These payloads were reconstructed above from the classified ELF, its
    # publish-last bindings, frozen package manifests and cold stager. Bind
    # their exact bytes before entering the disk transaction. INIT stays fixed.
    names=('autoboot.c65','boot.bin','boot.id','bootstage.bin','lisp65.prg','profile',
           'region1.bin','session.bin','window.bin','buffer','defstruct','inspect','place','string-extra')
    derived={n.upper().encode():(artifacts/n).read_bytes() for n in names}
    save(med/'derived-file-bindings.json',[bind(artifacts/n) for n in names])
    result = pack_media(C, med, artifacts, before_raw, packages, build_id, derived)
    result['plane_control'] = bind(med / 'plane-control.json')
    save(HERE / 'media.json', result)
    return result


def selftest():
    import tempfile
    import d81_persistence_fault as D
    import c2_require_resolver_gate as L
    rejected=[]
    def reject(name,fn):
        try:fn()
        except (AssertionError,ValueError,FileExistsError,L.GateError):rejected.append(name)
        else:raise AssertionError('negative survived: '+name)
    baseline=(PREFLIGHT/'planes/baseline/CODE.BIN').read_bytes()
    candidate=(PREFLIGHT/'planes/candidate/CODE.BIN').read_bytes()
    delivered=baseline+bytes(100)+b'native suffix'
    assert project_delivery_code(delivered,baseline,candidate)[len(candidate):]==delivered[len(candidate):]
    reject('wrong static baseline',lambda:project_delivery_code(b'X'+delivered[1:],baseline,candidate))
    reject('growth beyond reviewed resident delta',lambda:project_delivery_code(delivered,baseline,candidate+b'X'))
    overlap=baseline+b'X'+bytes(99)+b'native suffix'
    reject('native suffix overlap',lambda:project_delivery_code(overlap,baseline,candidate))
    before=D.visible_files((FINAL/'media/strings.d81').read_bytes())
    rows=L.decode_index(before[b'L65INDEX'])
    bad=copy.deepcopy(rows);bad[0]['roots']+=1
    reject('foreign index mutation',lambda:media_index_control(L,before[b'L65INDEX'],bad))
    reject('foreign file mutation',lambda:S.media_like_for_like(before,{**before,b'BOOT.ID':b'bad'}))
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'receipt';once(path,b'one')
        reject('write-once retry',lambda:once(path,b'two'))
    assert S.classify_bytes(b'a',b'b',{})['unclassified_bytes']==1
    price=load(PREFLIGHT/'planes/price.json')
    def budget(value):
        assert value['bytes']<=3000 and all(e['bytes']<=255 for e in value['entries'])
    budget(price['library'])
    bad=copy.deepcopy(price['library']);bad['bytes']=3001
    reject('3001 library bytes',lambda:budget(bad))
    bad=copy.deepcopy(price['library']);bad['entries'][0]['bytes']=256
    reject('256-byte object',lambda:budget(bad))
    return dict(status='PASS',negative_controls=rejected)


def finish():
    import mvp_vm_stdlib_boot_budget as B
    import c2_defstruct_foundations_gate as PK
    import c2_full_emission as F
    ready=verify_ready(acceptance=True)
    media=load(HERE/'media.json');assert media['status']=='PASS' and media['unclassified_bytes']==0
    checked(media['medium'])
    product=load(HERE/'plane-price.json')['after_product']
    rows=media['index_rows']
    used={k:base+sum(r[field] for r in rows) for k,field,base in
          [('code','bank2',code_bytes()),('entries','entries',product['entries']),
           ('resolutions','resolutions',product['resolutions']),('roots','roots',product['roots']),('images','images',6)]}
    limits=dict(code=60758,entries=2048,resolutions=4096,roots=1536,images=64)
    assert all(used[k]<=limits[k] for k in used)
    scratch=sum(r['scratch'] for r in rows);assert scratch<=50752-33840
    names=set();inputs=[]
    commands=load(HERE/'command-proof.json')['commands']
    for command in commands:
        if '-c' in command and command[command.index('-c')+1].endswith('.c'):
            path=ROOT/command[command.index('-c')+1]
            native,_,_=B.native_symbols_from_sources([path],set(B.d_flags(' '.join(command)))|{'__MEGA65__'})
            names.update(native);inputs.append(bind(path))
    manifests=[ROOT/r['path'] for r in product['manifests']]
    manifests += [ROOT/r['manifest']['path'] for r in load(BUILD/'media-r4/runtime-receipt.json')['packages']]
    for path in manifests:
        entries,literals=B.manifest_symbols(load(path));names.update(entries|literals);inputs.append(bind(path))
    symbols=dict(symbols=len(names),namepool=B.namepool_bytes(names))
    assert 1008-symbols['symbols']>=32 and 16351-symbols['namepool']>=384
    save(BUILD/'capacity.json',dict(status='PASS',used=used,limits=limits,entry_scratch_sum=scratch,
        entry_scratch_limit=50752-33840,symbols=dict(used=symbols,limits=dict(symbols=1008,namepool=16351),inputs=inputs)))
    manifest=BUILD/'media-r4/repl-comfort.manifest.json'
    blob=manifest.with_name('repl-comfort.blob.bin')
    m=load(manifest)
    known={e['name'] for p in manifests for e in load(p)['entries']}
    disasm=manifest.with_name('repl-comfort.disasm.txt').read_text();refs=set()
    for entry,section in zip(m['entries'],re.split(r'^\[\d+\] .*$',disasm,flags=re.M)[1:],strict=True):
        refs.update(entry['literals'][int(i)]['symbol'] for i in re.findall(r'\b(?:CALL|TAILCALL) lit=(\d+)',section))
    assert not refs-known,refs-known
    assert len(blob.read_bytes())==library_bytes() and len(m['entries'])==reviewed()['library']['objects'] and max(e['length'] for e in m['entries'])<=255
    image=F.emit_image('repl-comfort','repl',manifest)
    once(BUILD/'media-r4/repl-comfort.c2i',image.metadata)
    payload=(BUILD/'media-r4/artifacts/repl-comfort').read_bytes()
    once(BUILD/'media-r4/repl-comfort.l65s',payload)
    save(BUILD/'price.json',dict(status='PASS',library=library_bytes(),objects=len(m['entries']),max_object=max(e['length'] for e in m['entries']),
        metadata_bytes=len(image.metadata),package_bytes=len(payload),call_targets=sorted(refs),resident_delta=resident_delta(),
        resident_native_growth=0,overlay_deltas=load(HERE/'price.json')['overlay_deltas'],
        static_deltas=static_deltas()))
    save(BUILD/'source.json',dict(status='PASS',sources=ready['sources']+[load(HERE/'inventory.json')['classification_tool']],
        committed_source_admission='OPEN; working tree bound, no Git writes'))
    save(BUILD/'negative-controls.json',selftest())
    for name in ('inventory.json','media.json'):
        save(BUILD/name,load(HERE/name))
    for name in ('host','cost-final','batch-heap','slots','copy-heap','typeahead-queued'):
        for path in sorted((PREFLIGHT/name).rglob('*')):
            if path.is_file(): once(BUILD/'proofs'/name/path.relative_to(PREFLIGHT/name),path.read_bytes())
    save(BUILD/'host/receipt.json',dict(status='PASS',behavior=31,baseline=7,admission=16,
        return_parity=3,ordinary_keys=10,publication=2,batch_runs=141,proofs=ready['gates']))
    complete=dict(status='PASS',seed=1,final=0,product_links=1,
        medium=media['medium'],ELF=bind(BUILD/'wplto/resident-island-seed.prg.elf'),
        receipts=[bind(BUILD/n) for n in ('source.json','price.json','capacity.json','negative-controls.json','inventory.json','media.json','host/receipt.json')])
    save(BUILD/'seed.json',complete)
    save(BUILD/'complete.json',complete)
    return load(BUILD/'complete.json')


if __name__=='__main__':
    import argparse
    assert os.environ.get('PYTHONDONTWRITEBYTECODE')=='1'
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['prepare','selftest','seed','inventory','media','finish'])
    args=ap.parse_args();print(json.dumps(globals()[args.action](),indent=2))
