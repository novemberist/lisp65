#!/usr/bin/env python3
"""Write-once multiline strings producer, derived from walks_seed_producer.

The reviewer sets AUTH to the committed strings source/consumer authority.
The baseline is the closed walks Final, never its Seed in place of Final.
Probe is budget-free; seed claims one replay/link; acceptance is artifact-only.
Selftest performs no product commands, Git operations, or emulator work.
"""
import argparse,copy,hashlib,json,os,re,shlex,struct,subprocess,sys
from pathlib import Path
import strings_successor_r2_20260928 as STRINGS
ROOT=Path(__file__).resolve().parents[2]
AUTH='f31f79da'
HERE=ROOT/'build/strings-r7/seed'
BUILD=ROOT/'build/strings-product-r3'
FINAL=ROOT/'build/walks-final-r1'
RECIPE=FINAL/'final-invocation.json'
PLANE=ROOT/'build/walks-product-r1/plane/candidate'
BASE_MEDIA_SHA='67e37ff37b9294ac81031159174320bf08abd4dc8ae4a7d302fdd66ac5707401'
BASE_ELF_SHA='7b8dbf3dd53f08872322035ac260bb36d5fcd941fdeb4ff148e386d09d794449'
# Reviewer decision 2026-09-29: f31f79da is retained; aggregate cap is +250
# versus walks Final (measured +204; native resident growth remains zero).
PLANE_BOUND=250
LIBRARY_BOUND=1100
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0')
PRIORITY=['nice','-n','18','ionice','-c3']


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def bind(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                bytes=len(raw), sha256=sha(raw))


def checked(row):
    path = ROOT / row['path']
    actual = bind(path)
    assert all(actual[k] == row[k] for k in ('bytes', 'sha256') if k in row), row
    return path.read_bytes()


def load(path):
    return json.loads(Path(path).read_text())


def once(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(raw, str):
        raw = raw.encode()
    if path.exists():
        assert path.read_bytes() == raw, f'write-once mismatch: {path}'
    else:
        path.write_bytes(raw)


def save(path, value):
    once(path, json.dumps(value, indent=2, sort_keys=True) + '\n')


def save_suite(path, value):
    # disk_files order is the virtual D81 directory order, including the
    # historical reserved first slot. Sorting it changes behavioral fixtures.
    once(path, json.dumps(value, indent=2) + '\n')


def git(*args):
    return subprocess.check_output(PRIORITY + ['git', *args], cwd=ROOT, env=ENV).decode().strip()


def run(command, log):
    command = PRIORITY + list(map(str, command))
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('xb') as stream:
        result = subprocess.run(command, cwd=ROOT, env=ENV, stdout=stream,
                                stderr=subprocess.STDOUT)
    assert result.returncode == 0, f'command exit {result.returncode}: {log}'
    return log.read_bytes()


def snapshot(path, rows):
    path = Path(path).resolve()
    row = bind(path)
    target = HERE / 'inputs' / path.relative_to(ROOT)
    once(target, checked(row))
    rows[str(path)] = dict(source=row, restored=bind(target))
    return target


def include_closure(commands, ready):
    allowed = {str((ROOT / r['restored']['path']).resolve()): r['restored'] for r in ready['native']}
    generated = load(HERE / 'derived-inputs.json')['generated']
    allowed[str((ROOT / generated['path']).resolve())] = generated
    for row in load(HERE / 'derived-inputs.json')['all_generated']:
        allowed[str((ROOT / row['path']).resolve())] = row
    # Toolchain includes are explicit public replay bindings, consumed in place.
    for r in ready['native']:
        if r['source']['path'].startswith('tools/llvm-mos/'):
            allowed[str((ROOT / r['source']['path']).resolve())] = r['source']
    rows = []
    for i, command in enumerate(commands[:73]):
        source = command[command.index('-c')+1]
        if source.endswith('.s'):
            dirs = [ROOT] + [ROOT / command[j+1] for j, a in enumerate(command) if a == '-I']
            pending, deps = [ROOT / source], set()
            while pending:
                path = pending.pop().resolve()
                if str(path) in deps:
                    continue
                deps.add(str(path))
                for name in re.findall(r'^\s*\.include\s+"([^"]+)"', path.read_text(), re.M):
                    found = next((d / name for d in dirs if (d / name).is_file()), None)
                    assert found is not None, name
                    pending.append(found)
        else:
            c = list(command)
            at = c.index('-o')
            del c[at:at+2]
            c.remove('-c')
            raw = run(c + ['-E', '-M', '-MT', 'input'], HERE / 'include-logs' / f'{i:03d}.log')
            deps = {str((ROOT / p).resolve()) for p in shlex.split(raw.decode().replace('\\\n', ' ').split(':', 1)[1])}
        for path in deps:
            assert path in allowed, ('unbound dependency', path)
            checked(allowed[path])
        rows.append(dict(source=source, dependencies=[allowed[p] for p in sorted(deps)]))
    save(HERE / 'include-closure.json', dict(status='PASS', translation_units=73, rows=rows))


def seed():
    ready = verify_ready()
    preflight=json.loads(checked(ready['preflight_plane']))
    plane_budget(preflight['current']['plane'])
    commands = load(HERE / 'command-proof.json')['commands']
    assert len(commands) == 75
    assert not BUILD.exists(), 'Seed already claimed; no implicit retry'
    BUILD.mkdir()
    save(BUILD / 'attempt.json', dict(authority=AUTH, seed=1, final=0, product_link_attempts=0,
                                     command_probe=bind(HERE / 'command-ready.json')))
    state = dict(status='STARTED', authority=AUTH, seed=1, final=0, product_link_attempts=0)
    try:
        for i, command in enumerate(commands):
            if i == 74:
                state['product_link_attempts'] = 1
                save(BUILD / 'product-link-claim.json', state)
            output = ROOT / command[command.index('-o')+1]
            output.parent.mkdir(parents=True, exist_ok=True)
            run(command, BUILD / f'command-{i:03d}.log')
            state['commands_consumed'] = i+1
            print(f'completed frozen command {i+1}/75', flush=True)
        state['native'] = {role: bind(BUILD / 'wplto' / Path(row['path']).name) for role, row in ready['base_native'].items()}
        state['status'] = 'LINKED: run price, inventory, media in order'
    except BaseException as error:
        state.update(status='HALT', error=str(error))
        raise
    finally:
        save(BUILD / 'seed.json', state)
    return state


def classify_bytes(before, after, domains):
    """Exact expected byte pairs, never blanket changed-section exemptions."""
    rows, unknown = [], []
    for i in range(max(len(before), len(after))):
        a = before[i] if i < len(before) else None
        b = after[i] if i < len(after) else None
        if a == b:
            continue
        expected = domains.get(i)
        owner = expected[2] if expected and expected[:2] == (a, b) else 'UNCLASSIFIED'
        rows.append(dict(offset=i, before=a, after=b, owner=owner))
        if owner == 'UNCLASSIFIED':
            unknown.append(i)
    return dict(rows=rows, changed_bytes=len(rows), unclassified_bytes=len(unknown))


def inventory():
    from elf_truth import ElfTruth
    verify_ready(acceptance=True)
    priced = load(accepted_price_path())
    assert priced['status'] == 'PASS'
    checked(priced['plane_receipt'])
    assert not (HERE / 'inventory.json').exists(), 'inventory already exists'
    paths = [ROOT / r['path'] for r in priced['ELF']]
    raws = [checked(r) for r in priced['ELF']]
    truths = [ElfTruth.read(p, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj',
                           include_section_data=True) for p in paths]
    result = inventory_analysis(paths, raws, truths)
    result.update(ELFs=priced['ELF'], plane=bind(HERE / 'plane-price.json'),
                  derived=bind(HERE / 'derived-inputs.json'))
    save(HERE / 'inventory.json', result)
    assert result['unclassified_bytes'] == 0, 'unclassified ELF bytes'
    return result


def inventory_analysis(paths, raws, truths, listing_reader=None):
    """Read-only classification core; acceptance receipt is written by inventory."""
    a, b = truths
    drift = a.sections != b.sections
    if drift:
        assert len(a.sections) == len(b.sections), 'unproved owner capacity'
        expected, proof = project_main_drift(raws[0], a, b)
    else:
        assert a.symbols == b.symbols and a.relocations == b.relocations, 'ELF identity drift'
        expected, proof = bytearray(raws[0]), None
    plane = load(HERE / 'plane-price.json')
    for row in plane['artifacts']:
        checked(row)
    derived = load(HERE / 'derived-inputs.json')
    labels = ['proven overlay codegen / ELF packing metadata' if drift else 'unchanged']*len(expected)
    def add(section, offset, old, new, owner):
        assert len(old) == len(new)
        for truth, payload in zip(truths, (old, new)):
            assert truth.section_bytes(section)[offset:offset+len(payload)] == payload
        shoff = struct.unpack_from('<I', expected, 32)[0]
        shsize = struct.unpack_from('<H', raws[0], 46)[0]
        fileoff = struct.unpack_from('<I', expected, shoff+a.section(section).index*shsize+16)[0]
        assert expected[fileoff+offset:fileoff+offset+len(old)] == old
        expected[fileoff+offset:fileoff+offset+len(new)] = new
        labels[fileoff+offset:fileoff+offset+len(new)] = [owner]*len(new)
    for row in derived['crc_tables']:
        symbol = a.symbol('c2_phase02a_' + row['table'] + '_crc16')
        add(symbol.section, symbol.value-a.section(symbol.section).address,
            struct.pack('<6H', *row['before']), struct.pack('<6H', *row['after']),
            'derived ' + row['table'] + ' directory CRC16 array')
    pairs = []
    for key in ('before_product', 'after_product'):
        product = plane[key]
        pairs.append((int(product['product_build_id_hex'], 16), product['artifacts']['shelf']['bytes'],
                      derived['code_bytes_before' if key=='before_product' else 'code_bytes_after']))
    # Decode immediate instruction boundaries in the known constant consumers.
    # The two overlays and their relocation/packing consequences are proved separately;
    # other constant consumers retain their instruction boundaries.
    consumers = {
        'c2_stream_phase_00': 0, 'c2_stream_phase_00b': 0,
        'c2_stream_phase_01': 0, 'c2_append_envelope_phase': 0,
        'c2_session_emit_final_crc_phase': 0, 'c2_stream_shelf_read': 1, 'c2_product_boot': 1,
        'main': 1,  # c2_product_boot is inlined by the frozen Final LTO
        'c2_stream_phase_02b': 2, 'c2_stream_phase_03b': 2,

    }
    for name, kind in consumers.items():
        if name not in a.symbols_by_name or (drift and name in ('c2_session_emit_final_crc_phase', 'c2_stream_phase_01')):
            continue
        symbol = a.symbol(name)
        command = [str(ROOT / 'tools/llvm-mos/bin/llvm-objdump'), '-d',
                   '--section=' + symbol.section, '--start-address=' + str(symbol.value),
                   '--stop-address=' + str(symbol.value+symbol.bytes), str(paths[0])]
        listing = (listing_reader(command, name) if listing_reader else
                   run(command, HERE / 'inventory-logs' / (name + '.log')).decode())
        # Unsigned offset > limit can be lowered as offset >= limit+1.
        adjustments = (0, 1) if name == 'c2_stream_shelf_read' else (0,)
        allowed = {(x, y) for adjustment in adjustments
                   for x, y in zip(struct.pack('<I', pairs[0][kind]+adjustment),
                                   struct.pack('<I', pairs[1][kind]+adjustment)) if x != y}
        for line in listing.splitlines():
            match = re.match(r'\s*([0-9a-f]+):\s+([0-9a-f]{2})\s+([0-9a-f]{2})\s+(?:lda|ldx|ldy|cmp|cpx|cpy|eor|ora|and|adc|sbc)\s+#', line)
            if not match:
                continue
            offset = int(match[1], 16)-a.section(symbol.section).address
            old = a.section_bytes(symbol.section)[offset:offset+2]
            new = b.section_bytes(symbol.section)[offset:offset+2]
            assert old == bytes.fromhex(match[2]+match[3])
            if old[0] == new[0] and (old[1], new[1]) in allowed:
                add(symbol.section, offset+1, old[1:], new[1:], 'derived immediate: '+name)
    from itertools import zip_longest
    domains = {i: (old, new, labels[i]) for i, (old, new) in enumerate(zip_longest(raws[0], expected))
               if old != new}
    result = classify_bytes(*raws, domains)
    result.update(status='PASS' if result['unclassified_bytes'] == 0 else 'HALT: UNCLASSIFIED',
                  geometry_proof=proof, expected_elf_sha256=sha(expected))
    return result


def prepare_overlay_capacity(fam,value,regions,a,b):
    """Only record 22 may expand its slot; decoder 01 consumes Boot padding."""
    assert fam in ('boot','session')
    prove_overlay_drift(a,b)
    rows=value['slices']
    name=CRC_SECTION if fam=='session' else DECODE_SECTION
    row=next(r for r in rows if r['section']==name)
    expected=(22,29664,1244,32,64185) if fam=='session' else (4,6912,1702,256,19676)
    ident,off,size,alignment,extent=expected
    assert (row['id'],row['region_id'],row['file_offset'],row['file_size'],row['memory_size'],row['vma'])==(ident,0,off,size,size,0xc356)
    assert row['source_address']==(0x373e0 if fam=='session' else 0x08201b00)
    assert value['policy']['payload_alignment']==alignment
    assert value['policy']['max_slice_bytes']==1792
    assert len(regions[0])==value['storage']['size']==extent
    for r in rows:
        payload=a.section_bytes(r['section'])
        assert len(payload)==r['file_size']==r['memory_size']
        assert regions[r['region_id']][r['file_offset']:r['file_offset']+len(payload)]==payload
    following=30912 if fam=='session' else 8704
    assert min(r['file_offset'] for r in rows if r['region_id']==0 and r['file_offset']>off)==following
    assert regions[0][off+size:following]==bytes(following-off-size)
    newsize=DRIFT_SIZES[name][1]
    assert newsize<=1792
    if fam=='session':
        # The 1250-byte payload needs 1280 aligned bytes, replacing 1248.
        assert ((newsize+31)&~31)- (following-off)==32
        regions[0][following:following]=bytes(32)
        assert len(regions[0])==64217<=65536
        for r in rows:
            if r['region_id']==0 and r['file_offset']>=following:
                r['file_offset']+=32;r['source_address']+=32
                at=32+32*r['id'];source=r['source_address']
                struct.pack_into('<H',regions[0],at+4,source&65535)
                regions[0][at+25]=(source>>16)&15
                regions[0][at+26]=(source>>20)&255
        value['storage']['size']=len(regions[0])
        struct.pack_into('<I',regions[0],20,len(regions[0]))
    else:
        assert off+newsize<=following
    row.update(file_size=newsize,memory_size=newsize,end=row['vma']+newsize)
    at=32+32*ident
    struct.pack_into('<H',regions[0],at+6,newsize)
    struct.pack_into('<H',regions[0],at+10,newsize)


def rebind_family(C, fam, value, regions, a, b, elf):
    """Comfort lineage: rebind every payload, record, directory and header CRC."""
    BANK = C.BANK
    prepare_overlay_capacity(fam,value,regions,a,b)
    for row in value['slices']:
        old, new = a.section_bytes(row['section']), b.section_bytes(row['section'])
        off, rid = row['file_offset'], row['region_id']
        assert len(new) == row['file_size'] == row['memory_size']
        assert len(old)==len(new) or row['section'] in DRIFT_SIZES
        assert regions[rid][off:off+len(old)] == old
        regions[rid][off:off+len(new)] = new
        row.update(sha256=sha(new), crc16=BANK.crc16_ccitt_false(new))
        at = 32+32*row['id']
        struct.pack_into('<H', regions[0], at+20, row['crc16'])
        regions[0][at+22:at+24] = bytes(2)
        row['record_crc16'] = BANK.crc16_ccitt_false(regions[0][at:at+32])
        struct.pack_into('<H', regions[0], at+22, row['record_crc16'])
    over = regions[1]
    crc = BANK.crc16_ccitt_false(over)
    struct.pack_into('<I', regions[0], 28, len(over) | ((crc if over else 0) << 16))
    BANK._refresh_catalog_crcs(regions[0])
    value['overflow_storage'].update(crc16=crc, sha256=sha(over))
    value['storage'].update(crc16=BANK.crc16_ccitt_false(regions[0]), sha256=sha(regions[0]))
    value['catalog'].update(directory_crc16=int.from_bytes(regions[0][24:26], 'little'),
                            header_crc16=int.from_bytes(regions[0][26:28], 'little'))
    if fam == 'session':
        value['external_storage'].update(crc16=BANK.crc16_ccitt_false(regions[2]), sha256=sha(regions[2]))
    value['elf'] = dict(bind(elf), file=str(elf))
    return C.validate_family(fam, value, regions, a, b)


def replace_file(image, name, payload, domains):
    """Classify exact D81 transaction bytes, including allocation and directory."""
    import d81_persistence_fault as D
    slot, = [s for s in D.directory_slots(image) if s.record[2] and D.entry_name(s.record) == name.upper().encode()]
    # Construction can temporarily pair a new package with the old index.
    # Read this chain directly; pack_media admits only the completed transaction.
    if D.read_record_payload(image, slot.record) == payload:
        return image
    chain = list(D.file_chain(image, slot.record))
    original_chain = set(chain)
    count = (len(payload)+253)//254
    assert count and count <= 0xffff
    state = bytearray(image)
    freed = chain[count:]
    chain = chain[:count]
    for track in list(range(1, 40))+list(range(41, 81)):
        for sector in range(40):
            if len(chain) < count and D.sector_is_free(state, track, sector):
                chain.append((track, sector))
                D.set_sector_free(state, track, sector, False)
    assert len(chain) == count, 'D81 full'
    for track, sector in freed:
        D.set_sector_free(state, track, sector, True)
    for index, (track, sector) in enumerate(chain):
        at = D.sector_offset(track, sector)
        encoded = D.chain_sector(payload, tuple(chain), index)
        # Preserve existing slack: rewriting index padding is not an index
        # field/CRC change and must not inflate the classified diff.
        used = 2 + len(payload[index*254:(index+1)*254])
        state[at:at+256] = (encoded[:used] + image[at+used:at+256]
            if (track, sector) in original_chain else encoded)
    at = D.sector_offset(slot.track, slot.sector)+slot.index*32
    state[at+3:at+5] = bytes(chain[0])
    struct.pack_into('<H', state, at+30, count)
    # Compute expected edits from this deterministic allocation plan. The
    # ledger is later compared to the actual persisted image, byte for byte.
    data_offsets = {D.sector_offset(t, sec)+i for t, sec in chain for i in range(256)}
    for i, (old, new) in enumerate(zip(image, state)):
        if old != new:
            kind = 'file-chain' if i in data_offsets else 'directory' if at <= i < at+32 else 'BAM'
            original = domains[i][0] if i in domains else old
            domains[i] = (original, new, name + ': ' + kind)
    state = bytes(state)
    D.validate_bam(state)
    updated, = [s for s in D.directory_slots(state) if s.record[2] and D.entry_name(s.record) == name.upper().encode()]
    assert D.read_record_payload(state, updated.record) == payload
    return state


def media_like_for_like(before,expected,static=None,derived=None):
    assert set(expected)==set(before), 'media file population drift'
    allowed={b'REPL-COMFORT',b'L65INDEX'}
    if static is not None:
        assert set(static)=={b'CODE.BIN',b'C2D.BIN',b'SHELF.BIN'}
        assert all(expected[n]==payload for n,payload in static.items()), 'foreign static media bytes'
        allowed.update(static)
    if derived is not None:
        permitted={b'AUTOBOOT.C65',b'BOOT.BIN',b'BOOT.ID',b'BOOTSTAGE.BIN',b'LISP65.PRG',b'PROFILE',b'REGION1.BIN',b'SESSION.BIN',b'WINDOW.BIN',b'BUFFER',b'DEFSTRUCT',b'INSPECT',b'PLACE',b'STRING-EXTRA'}
        assert set(derived)<=permitted, 'foreign derived media owner'
        assert all(expected[n]==payload for n,payload in derived.items()), 'derived media payload drift'
        allowed.update(derived)
    assert all(expected[n]==before[n] for n in before if n not in allowed), 'foreign media file change'


def library_budget(before,after):
    assert before==960 and after==1060, 'reviewed library geometry drift'
    assert after<=LIBRARY_BOUND, 'library exceeds 1100'
    assert after-before<=PLANE_BOUND, 'library growth exceeds aggregate bound'


def media_index_control(L, before, rows):
    old = L.decode_index(before)
    assert len(old) == len(rows), 'index population drift'
    for a, b in zip(old, rows):
        allowed = {'artifact_bytes', 'bank2', 'combined_crc32', 'entries',
                   'resolutions', 'scratch'} if a['name'] == 'repl-comfort' else set()
        assert a.keys() == b.keys()
        assert all(a[k] == b[k] for k in a if k not in allowed), 'foreign index field change'
    return L.encode_index(rows)


def emit_media_library(C, med, libraries, build_id):
    package = med / 'repl-comfort'
    import bytecode_p0_stdlib as P
    suite=ROOT/'config/comfort-default-plane/libraries/repl-comfort-suite.json'
    with STRINGS.live_world():
        P.emit_artifacts(str(suite),P._read_suite(str(suite)),str(package),
                         base_addr=0,artifact_role='disk-lib')
    manifest = package.with_suffix('.manifest.json')
    value = load(manifest)
    blob = package.with_suffix('.blob.bin').read_bytes()
    library_budget(libraries['baseline']['code_bytes'], len(blob))
    assert value['code_bytes'] == len(blob) == libraries['candidate']['code_bytes']
    assert blob == checked(libraries['candidate']['blob']), 'priced library blob drift'
    assert value['private_inline_functions'] == ['%comfort-state-hi', '%comfort-state-lo']
    checked(libraries['candidate']['manifest'])
    args = ('repl-comfort', 'repl-comfort', 'repl')
    entry, payload = C.L.F.measured_row(*args, manifest, (), 1, 1, product_build_id=build_id)
    priced_entry, priced_payload = C.L.F.measured_row(*args,
        ROOT / libraries['candidate']['manifest']['path'], (), 1, 1, product_build_id=build_id)
    assert (entry, payload) == (priced_entry, priced_payload), 'priced library package drift'
    assert entry['bank2'] == len(blob) <= LIBRARY_BOUND
    return manifest, dict(status='PASS', bank2_bytes=entry['bank2'], bound=LIBRARY_BOUND,
        headroom=LIBRARY_BOUND-entry['bank2'], artifact_bytes=len(payload),
        manifest=bind(manifest), blob=bind(package.with_suffix('.blob.bin')),
        matches_accepted_price=True)


def pack_media(C, med, artifacts, before_raw, packages, build_id, derived):
    D, L = C.L.D81, C.L
    before = D.visible_files(before_raw)
    expected = {name: (artifacts / name.decode().lower()).read_bytes() for name in before}
    static={n.encode():(HERE/'plane/candidate'/n).read_bytes() for n in ('CODE.BIN','C2D.BIN','SHELF.BIN')}
    static[b'CODE.BIN']=project_delivery_code((med/'code-native-rebound.bin').read_bytes(),(HERE/'plane/baseline/CODE.BIN').read_bytes(),static[b'CODE.BIN'])
    static[b'C2D.BIN']+=bytes(C.M.C2D_RESET_DOMAIN_BYTES-len(static[b'C2D.BIN']))
    media_like_for_like(before,expected,static,derived)
    raw, domains = before_raw, {}
    for name, payload in expected.items():
        if name != b'L65INDEX':
            raw = replace_file(raw, name.decode(), payload, domains)
    # Package locators are final before the index is encoded.
    locators = {D.entry_name(s.record).decode().lower(): D.file_chain(raw, s.record)[0]
                for s in D.directory_slots(raw) if s.record[2]}
    rows, payloads = [], {}
    for row in packages:
        name = row['name']
        entry, payload = L.F.measured_row(name, name, row['shelf'], ROOT / row['manifest']['path'],
            tuple(row['dependencies']), *locators[name], product_build_id=build_id)
        assert payload == expected[name.upper().encode()]
        rows.append(entry); payloads[name] = payload
    index = media_index_control(L.L65I, before[b'L65INDEX'], rows)
    expected[b'L65INDEX'] = index
    raw = replace_file(raw, 'l65index', index, domains)
    media_like_for_like(before, expected, static, derived)
    D.validate_bam(raw)
    assert D.visible_files(raw) == expected
    assert L.L65I.decode_index(index, payloads, artifact_build_id=build_id) == rows
    (artifacts / 'l65index').write_bytes(index)
    final = med / 'strings.d81'
    once(final, raw)
    D.validate_bam(raw)
    raw = final.read_bytes()
    actual = D.visible_files(raw)
    assert actual == expected, 'every file must read back exactly'
    assert L.L65I.decode_index(actual[b'L65INDEX'], payloads, artifact_build_id=build_id) == rows
    mutations = L.L65I.mutation_gate(index, payloads, artifact_build_id=build_id)
    diff = classify_bytes(before_raw, raw, domains)
    assert diff['unclassified_bytes'] == 0
    owners={n.decode() for n in before if n!=b'L65INDEX'}|{'l65index'}
    assert {r['owner'] for r in diff['rows']} <= {
        name+': '+kind for name in owners for kind in ('file-chain','directory','BAM')}, 'foreign D81 transaction change'
    save(med / 'd81-byte-diff.json', diff)
    return dict(status='PASS', medium=bind(final), base_sha256=sha(before_raw),
        every_file_read_back=True, files={n.decode(): dict(bytes=len(v), sha256=sha(v)) for n, v in actual.items()},
        unclassified_bytes=0, diff=bind(med / 'd81-byte-diff.json'), mutations=mutations,
        index_rows=rows,
        product_links=0, emulator_runs=0, device_contacts=0)


def media_plane_control(ready, before):
    """Compare emission with frozen emission, and delivery with delivery."""
    import c2_lite_media_product as M
    sources = {name: PLANE/name for name in ('CODE.BIN','C2D.BIN','SHELF.BIN')}
    closure = {str((ROOT / r['source']['path']).resolve()): r for r in ready['closure']}
    proof = {}
    for name, source in sources.items():
        row = closure[str(source.resolve())]
        baseline = (HERE / 'plane/baseline' / name).read_bytes()
        assert baseline == checked(row['source']) == checked(row['restored']), ('pre-media baseline', name)
        delivered = before[name.encode()]
        if name == 'C2D.BIN':
            assert len(baseline) == M.C2D_PREFIX_BYTES
            expected = baseline + bytes(M.C2D_RESET_DOMAIN_BYTES - len(baseline))
            assert delivered == expected, 'complete C2D reset-domain control'
        elif name == 'SHELF.BIN':
            assert delivered == baseline, 'complete shelf control'
        else:
            assert len(delivered) >= len(baseline) and delivered[:len(baseline)] == baseline, 'static code control'
        proof[name] = dict(emitted_bytes=len(baseline), emitted_sha256=sha(baseline),
                           delivered_bytes=len(delivered), delivered_sha256=sha(delivered),
                           suffix_bytes=len(delivered)-len(baseline), frozen=row['restored'])
    return dict(status='PASS', comparison='frozen pre-media emission; exact delivery projection', files=proof)


def project_delivery_code(delivered, baseline, candidate):
    assert delivered[:len(baseline)]==baseline, 'baseline code mismatch'
    assert 0 <= len(candidate)-len(baseline) <= 48, 'unreviewed static growth'
    assert len(candidate)<=60758, 'static code exceeds frozen Bank-2 owner capacity'
    extent=max(len(baseline),len(candidate))
    assert len(delivered)>=extent and not any(delivered[len(baseline):extent]), 'static growth overlaps native owner'
    result=bytearray(delivered)
    result[:extent]=candidate+bytes(extent-len(candidate))
    assert result[extent:]==delivered[extent:]
    return result


def media(output=None):
    import comfort_default_media as C
    ready = verify_ready(acceptance=True)
    inv = load(HERE / 'inventory.json')
    assert inv['status'] == 'PASS' and inv['unclassified_bytes'] == 0
    assert load(accepted_price_path())['status'] == 'PASS'
    for row in load(BUILD / 'seed.json')['native'].values():
        checked(row)
    for row in inv['ELFs']:
        checked(row)
    checked(inv['plane']); checked(inv['derived'])
    for row in load(HERE / 'plane-price.json')['artifacts']:
        checked(row)
    authority_media = ready['media_authority']
    verify_seed_driver(authority_media['builder'], acceptance=True)
    before_raw = checked(authority_media['medium'])
    assert sha(before_raw) == BASE_MEDIA_SHA
    before = C.L.D81.visible_files(before_raw)
    assert {n.decode(): dict(bytes=len(v), sha256=sha(v)) for n, v in before.items()} == authority_media['files']
    control = media_plane_control(ready, before)
    med = output if output is not None else BUILD / 'media'
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


def price():
    verify_ready(acceptance=True)
    seeded = load(BUILD / 'seed.json')
    assert seeded['commands_consumed'] == 75 and seeded['product_link_attempts'] == 1
    for row in seeded['native'].values():
        checked(row)
    price_path = accepted_price_path()
    assert not price_path.exists(), 'price receipt already exists'
    from elf_truth import ElfTruth
    paths = [FINAL / 'wplto/resident-island-seed.prg.elf', BUILD / 'wplto/resident-island-seed.prg.elf']
    truths = [ElfTruth.read(p, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj', include_section_data=True) for p in paths]
    a, b = truths
    def sizes(t):
        return {'.text': t.section('.text').bytes, '.rodata': t.section('.rodata').bytes,
                'BSS': sum(s.bytes for s in t.sections if s.section_type == 'SHT_NOBITS' and 'SHF_ALLOC' in s.flags),
                'CRT_zero_bytes': t.symbol('__bss_end').value - t.symbol('__bss_start').value}
    old, new = map(sizes, truths)
    delta = {k: new[k] - v for k, v in old.items()}
    sites = []
    for x in a.symbols:
        if not x.bytes or x.symbol_type not in ('Function', 'Object'):
            continue
        ys = [y for y in b.symbols_by_name.get(x.name, []) if y.section == x.section and y.symbol_type == x.symbol_type]
        if len(ys) != 1:
            continue
        y = ys[0]
        if x.bytes != y.bytes:
            sites.append(dict(name=x.name, section=x.section, before=x.bytes, after=y.bytes, delta=y.bytes-x.bytes))
    sections = [dict(name=s.name, before=a.section(s.name).bytes, after=s.bytes, delta=s.bytes-a.section(s.name).bytes)
                for s in b.sections if 'SHF_ALLOC' in s.flags and s.name in a.sections_by_name and s.bytes != a.section(s.name).bytes]
    plane = load(HERE / 'plane-price.json')
    for row in plane['artifacts']:
        checked(row)
    assert plane['status'] == 'PASS'
    plane_budget(dict(bound=plane['bound'],delta=plane['plane_deltas'],library_growth=plane['library_growth'],total_growth=plane['total_growth']))
    library_budget(plane['libraries']['baseline']['code_bytes'],plane['libraries']['candidate']['code_bytes'])
    proof = native_price_proof(paths, truths, delta, sites, sections)
    result = dict(status='PASS',
        ELF=[bind(p) for p in paths], before=old, after=new, delta=delta, bound=0,
        plane_receipt=bind(HERE/'plane-price.json'),
        proven_drift=proof, 
        plane=plane['plane_deltas'], plane_total=plane['total_growth'], plane_bound=PLANE_BOUND,
        section_deltas=sections, per_site_bytes=sites,
        free_after=dict(text=0xb3b0-b.section('.text').address-b.section('.text').bytes,
                        rodata=0xb98c-b.section('.rodata').address-b.section('.rodata').bytes,
                        high_bss=0xc000-b.symbol('__bss_end').value))
    save(price_path, result)
    return result


def main():
    global HERE
    assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', nargs='?', choices=['command-probe', 'seed', 'price', 'inventory', 'media'])
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--probe-output', type=Path, help='fresh budget-free probe receipt root; Seed always uses strings-r7/seed')
    parser.add_argument('--media-output', type=Path, help='fresh media directory under build; preserves failed attempts')
    args = parser.parse_args()
    if args.media_output is not None:
        assert args.mode == 'media' and not args.selftest
        args.media_output = args.media_output.resolve()
        assert args.media_output.is_relative_to(ROOT / 'build') and not args.media_output.exists()
    if args.selftest:
        assert args.mode is None and args.probe_output is None
        result = selftest()
    else:
        assert args.mode is not None
        if args.probe_output is not None:
            assert args.mode == 'command-probe', 'custom root is probe-only'
            HERE = args.probe_output.resolve()
            assert HERE.is_relative_to(ROOT / 'build') and not HERE.exists()
        result = {'command-probe': command_probe, 'seed': seed, 'price': price,
                  'inventory': inventory, 'media': lambda: media(args.media_output)}[args.mode]()
    print(json.dumps(result, indent=2))
    if result['status'].startswith('HALT'):
        raise SystemExit(1)


def authority():
    assert AUTH != 'PENDING', 'reviewer must set the future authority commit'
    subprocess.run(PRIORITY+['git','merge-base','--is-ancestor',AUTH,'HEAD'],cwd=ROOT,env=ENV,check=True)
    assert not git('status','--porcelain','--untracked-files=normal'), 'commit preparation first'
    assert git('ls-files','--error-unmatch','tools/host-lisp/strings_seed_producer.py')
    changed=set(git('diff','--name-only',AUTH,'HEAD').splitlines())
    allowed={
        'build/strings-r6/prep-report.md',
        'build/strings-r7/prep-report.md',
        'config/c2-v16-defstruct-phase-a-receipt-strings-r2-20260928.json',
        'config/c2-v160-comfort-repl-receipt-strings-r2-20260928.json',
        'config/c2-v160-hybrid-capacity-receipt-strings-r2-20260928.json',
        'config/c2-v160-hybrid-receipt-strings-r2-20260928.json',
        'config/c2-v17-comfort-phase1b-receipt-strings-r2-20260928.json',
        'config/c2-v17-repl-idle-blink-receipt-strings-r2-20260928.json',
        'config/c2-v251-card5-receipt-strings-r2-20260928.json',
        'config/c2-v251-keymap-receipt-strings-r2-20260928.json',
        'config/c2-v251-public-authority-receipt-strings-r2-20260928.json',
        'config/document-index.json',
        'config/strings-source-baseline-r2-20260928.json',
        'config/strings-stdlib-artifacts-receipt-r2-20260928.json',
        'docs/planning/post-2.4.0-plan.md',
        'mk/gates.mk',
        'mk/workbench.mk',
        'tools/host-lisp/c2_v160_comfort_repl_strings_r2_20260928.py',
        'tools/host-lisp/c2_v160_hybrid_capacity_strings_r2_20260928.py',
        'tools/host-lisp/c2_v160_hybrid_strings_r2_20260928.py',
        'tools/host-lisp/c2_v16_defstruct_phase_a_strings_r2_20260928.py',
        'tools/host-lisp/c2_v17_comfort_phase1b_strings_r2_20260928.py',
        'tools/host-lisp/c2_v17_repl_idle_blink_strings_r2_20260928.py',
        'tools/host-lisp/c2_v251_card5_strings_r2_20260928.py',
        'tools/host-lisp/c2_v251_keymap_receipt_strings_r2_20260928.py',
        'tools/host-lisp/c2_v251_public_authority_strings_r2_20260928.py',
        'tools/host-lisp/stdlib_artifacts_strings_r2_20260928.py',
        'tools/host-lisp/strings_seed_producer.py',
        'tools/host-lisp/strings_successor_r2_20260928.py',
    }
    assert changed <= allowed, ('unreviewed post-authority drift',sorted(changed-allowed))
    for name in (*STRINGS.baseline(),'tests/bytecode/libs/p0-repl-comfort-v250.json'):
        expected=subprocess.check_output(PRIORITY+['git','show',AUTH+':'+name],cwd=ROOT,env=ENV)
        assert (ROOT/name).read_bytes()==expected, ('source authority drift',name)


def command_probe():
    authority()
    assert FINAL.is_dir() and RECIPE.is_file(), 'walks Final not closed; Seed is not a fallback'
    assert not BUILD.exists() and not HERE.exists(), 'write-once roots already exist'
    plane_budget(load(ROOT/'config/strings-stdlib-artifacts-receipt-r2-20260928.json')['current']['plane'])
    import walks_final as CLOSED
    for name,digest in CLOSED.RECEIPTS.items():assert sha((ROOT/name).read_bytes())==digest, name
    final=load(RECIPE);identities=load(FINAL/'final-identity.json')
    base_native={role:row['final'] for role,row in zip(('ELF','LTO','PRG'),identities['artifacts'],strict=True)}
    for row in base_native.values():checked(row)
    assert base_native['ELF']['sha256']==BASE_ELF_SHA
    base_media=identities['media'][0]['final'];checked(base_media)
    assert base_media['sha256']==BASE_MEDIA_SHA
    old_commands=load(ROOT/final['seed_commands']['path'])['commands']
    commands=final['commands']
    expected=[[a.replace('build/walks-product-r1/wplto/','build/walks-final-r1/wplto/') for a in c] for c in old_commands]
    assert commands==expected and len(commands)==75, 'Final command lineage drift'
    assert any('-DLISP65_C2_BANK2_CODE_LIMIT=60758' in c for c in commands)
    HERE.mkdir(parents=True)
    old=load(ROOT/'build/walks-r3/seed/derived-inputs.json')
    input_map={r['path']:r for r in final['input_bindings']}
    selected=old['all_generated']+[old['generated']]+[r for r in final['input_bindings'] if r['path'].startswith('tools/llvm-mos/')]
    native=[];mapping={}
    for row in {r['path']:r for r in selected}.values():
        assert input_map[row['path']]==row, ('Final input binding drift',row['path'])
        target=HERE/'native-inputs'/row['path'];once(target,checked(row))
        native.append(dict(source=row,original=row['path'],restored=bind(target)))
    prefix=str((HERE/'native-inputs').relative_to(ROOT))+'/'
    def rebase(arg):
        arg=arg.replace('build/walks-final-r1/wplto/',str(BUILD.relative_to(ROOT))+'/wplto/')
        for old in ('build/walks-r3/seed/candidate-inputs/','build/walks-r3/seed/derived/'):
            arg=arg.replace(old,prefix+old)
        return arg
    commands=[[rebase(a) for a in c] for c in commands]
    save(HERE/'baseline-command-proof.json',dict(status='COMMAND PROBE ONLY',commands=commands))
    rows={};product=load(PLANE/'product/substitution-artifacts.json')
    assert product==load(ROOT/'build/walks-r3/seed/plane-price.json')['after_product']
    for row in product['manifests']:
        path=ROOT/row['path'];checked(row);snapshot(path,rows);snapshot(ROOT/load(path)['blob'],rows)
    for p in (RECIPE,FINAL/'final-identity.json',PLANE/'product/substitution-artifacts.json'):
        snapshot(p,rows)
    for n in ('CODE.BIN','C2D.BIN','SHELF.BIN'):snapshot(PLANE/n,rows)
    import bytecode_p0_stdlib as P
    pending=[ROOT/load(ROOT/r['path'])['suite'] for r in product['manifests']]
    seen=set()
    while pending:
        path=pending.pop().resolve()
        if path in seen:continue
        seen.add(path);snapshot(path,rows)
        value=load(path)
        resolved=P._read_suite(str(path))
        for source in resolved['sources']:snapshot(ROOT/source,rows)
        for key in ('resident_suite','resident_suites','extends','cases_from_suites'):
            refs=value.get(key,[])
            if isinstance(refs,str):refs=[refs]
            pending.extend(Path(P._suite_path(ref,str(path.parent))) for ref in refs)
    for name in ('lib/stdlib-read-line.lisp','lib/sexp-depth.lisp','lib/repl-comfort-v250.lisp'):
        snapshot(ROOT/name,rows)
    for p in sorted((FINAL/'media').rglob('*')):
        if p.is_file():snapshot(p,rows)
    packages=load(FINAL/'media/runtime-receipt.json')['packages']
    for row in packages:
        path=ROOT/row['manifest']['path'];checked(row['manifest']);snapshot(path,rows);snapshot(ROOT/load(path)['blob'],rows)
    # Bind the complete authored suite/source population, including inherited
    # resident metadata. Probe preprocessing checks every native include.
    # No native compilation or product link is run during a command probe.
    for directory,pattern in [('lib','*.lisp'),('tests/bytecode/libs','*.json'),('tests/bytecode/stdlib','*.json'),('config/comfort-default-plane/libraries','*.json')]:
        for p in sorted((ROOT/directory).glob(pattern)):snapshot(p,rows)
    for p in (ROOT/STRINGS.BASELINE,ROOT/'tools/host-lisp/strings_successor_r2_20260928.py'):snapshot(p,rows)
    media=load(ROOT/'build/walks-r3/seed/media.json')
    import d81_persistence_fault as D
    files=D.visible_files(checked(base_media))
    assert {n.decode():dict(bytes=len(v),sha256=sha(v)) for n,v in files.items()}==media['files']
    preflight_path=ROOT/'config/strings-stdlib-artifacts-receipt-r2-20260928.json'
    preflight=load(preflight_path);plane_budget(preflight['current']['plane'])
    for row in preflight['inputs']:checked(row)
    ready=dict(status='PASS: COMMAND PROBE ONLY',authority=AUTH,execution_head=git('rev-parse','HEAD'),
        driver=bind(Path(__file__)),base_native=base_native,base_media=base_media,native=native,closure=list(rows.values()),
        preflight_plane=bind(preflight_path),commands=bind(HERE/'baseline-command-proof.json'),
        media_authority=dict(medium=base_media,files=media['files'],packages=packages,builder=bind(Path(__file__))),
        tools=[bind(p) for p in sorted((ROOT/'tools/host-lisp').glob('*.py')) if p!=Path(__file__).resolve()],
        budget=dict(seed=0,final=0,product_link=0))
    prepare_commands(ready)
    save(HERE/'command-ready.json',ready)
    return dict(status=ready['status'],frozen_commands=len(commands),native_inputs=len(native),budget=ready['budget'])


def verify_seed_driver(row,*,acceptance):
    # A producer repair needs a new explicitly reviewed acceptance successor.
    if not acceptance:
        checked(row); return
    # Acceptance stages (price/inventory/media) may run a committed, reviewed
    # repair of the producer: the seed-time driver bytes must be a committed
    # version of this file on the current history (reviewer rule 2026-09-28).
    rel=row['path']
    for rev in git('log','--format=%H','--',rel).split():
        blob=subprocess.check_output(PRIORITY+['git','show',rev+':'+rel],cwd=ROOT,env=ENV)
        if len(blob)==row['bytes'] and hashlib.sha256(blob).hexdigest()==row['sha256']:
            return
    raise AssertionError(('seed-time driver not found in committed history',row))


def verify_ready(*,acceptance=False):
    authority();ready=load(HERE/'command-ready.json')
    assert ready['authority']==AUTH
    verify_seed_driver(ready['driver'],acceptance=acceptance)
    for row in ready['native']:checked(row['source']);checked(row['restored'])
    for row in ready['closure']:checked(row['source']);checked(row['restored'])
    for row in ready['tools']:checked(row)
    for row in ready['base_native'].values():checked(row)
    for key in ('base_media','commands','preflight_plane'):checked(ready[key])
    for row in ready['prepared']:checked(row)
    return ready


def prepare_commands(ready):
    # Finish every pre-link derivation before publishing readiness or claiming
    # the Seed. Seed consumes these exact bytes, without another emission.
    plane = emit_planes(ready)
    commands = derived_commands(ready, plane)
    include_closure(commands, ready)
    paths = [p for directory in ('plane', 'derived', 'candidate-inputs')
             for p in sorted((HERE / directory).rglob('*')) if p.is_file()]
    paths += [HERE / name for name in ('plane-price.json', 'derived-inputs.json',
                                      'command-proof.json', 'include-closure.json')]
    ready['prepared'] = [bind(p) for p in paths]


def accepted_price_path():return HERE/'price.json'


def plane_budget(plane):
    assert plane['bound']==PLANE_BOUND
    assert plane['total_growth']==sum(plane['delta'].values())+plane['library_growth']
    assert plane['total_growth']<=PLANE_BOUND, 'library/plane aggregate exceeds +250'


def emit_planes(ready):
    # Re-emit the six static images and the separate repl-comfort package.
    # Every frozen input and all three authored substitutions are probe-bound.
    from stdlib_artifacts_strings_r2_20260928 import emit_planes as emit
    for row in ready['closure']:
        checked(row['source']);checked(row['restored'])
    result=emit(HERE/'plane')
    plane_budget(dict(bound=result['bound'],delta=result['plane_deltas'],
        library_growth=result['library_growth'],total_growth=result['total_growth']))
    save(HERE/'plane-price.json',result)
    return result


def native_stdlib_header(header):
    # Static images are emitted at offset zero. The frozen native ABI header
    # describes the same bundle at Bank 5. Project only this explicit seam;
    # the complete projected header must still reproduce the frozen input.
    old = '#define LISP65_BYTECODE_STDLIB_BASE_ADDR 0x000000u'
    assert header.count(old) == 1, 'unexpected static stdlib address origin'
    return header.replace(old, '#define LISP65_BYTECODE_STDLIB_BASE_ADDR 0x050000u')


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
                counts=[('BLOB_BYTES',old_size,new_size)]
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


# Exact transformations reviewed in build/strings-r8/drift-report.md.
CRC_SECTION = '.lisp65_rt_c2emit_final_crc'
DECODE_SECTION = '.lisp65_rt_c2d_01'
DRIFT_SIZES = {CRC_SECTION: (1244, 1250), DECODE_SECTION: (1702, 1703)}
DRIFT_EDITS = {
    CRC_SECTION: [
        (0xc5ba, '', '8517'), (0xc5d8, '8617', '861c'),
        (0xc5e1, 'a617', 'a61c'), (0xc5f2, '', '851c'),
        (0xc5fb, '8617', '861d'), (0xc62e, '861c', '861e'),
        (0xc641, 'a617', 'a61d'), (0xc649, 'a51c', 'a51e'),
        (0xc665, 'a05da931a2dc84048505a02c84068607a200a916',
         'a916a2baa0b548a51c85046886058406a6178607a200')],
    DECODE_SECTION: [
        (0xc4dc, 'a901', 'a900481a'), (0xc4e6, 'a900', '68'),
        (0xc662, 'c9dc', 'c902'), (0xc67d, 'c92c', 'c9b5'),
        (0xc694, 'c931', 'c9ba'), (0xc69f, 'c95d', 'c907')],
}


def drift_address(section, address):
    return address + sum(len(bytes.fromhex(new))-len(bytes.fromhex(old))
                         for at, old, new in DRIFT_EDITS.get(section, [])
                         if address >= at+len(bytes.fromhex(old)))


def prove_overlay_drift(a, b):
    """Reconstruct both complete sections and every relocation from baseline."""
    from dataclasses import replace
    plane = load(HERE/'plane-price.json')
    assert [int(plane[k]['product_build_id_hex'],16) for k in
            ('before_product','after_product')] == [0xdc2c315d,0x02b5ba07]
    payloads = {}
    relocs = []
    for section, sizes in DRIFT_SIZES.items():
        assert (a.section(section).bytes,b.section(section).bytes)==sizes
        assert a.section(section).address==b.section(section).address==0xc356
        data=bytearray(a.section_bytes(section))
        for at, old, new in reversed(DRIFT_EDITS[section]):
            old,new=bytes.fromhex(old),bytes.fromhex(new)
            assert data[at-0xc356:at-0xc356+len(old)]==old
            data[at-0xc356:at-0xc356+len(old)]=new
        payloads[section]=data
    for r in a.relocations:
        sec=r.source_section
        if sec not in DRIFT_SIZES:
            assert r.target not in DRIFT_SIZES, 'unexpected external overlay reference'
            relocs.append(r); continue
        if sec==CRC_SECTION and 0xc665<=r.offset<0xc679:
            continue  # Explicit replacement block's ZP operands below.
        offset=drift_address(sec,r.offset)
        changes=dict(offset=offset)
        if r.target==sec:
            target=drift_address(sec,0xc356+r.addend)
            changes['addend']=target-0xc356
            if r.relocation_type=='R_MOS_ADDR16':
                struct.pack_into('<H',payloads[sec],offset-0xc356,target)
            else:
                assert r.relocation_type=='R_MOS_PCREL8'
                displacement=target-(offset+1)
                assert -128<=displacement<=127
                payloads[sec][offset-0xc356]=displacement&255
        elif r.relocation_type=='R_MOS_ADDR8':
            operand=payloads[sec][offset-0xc356]
            if operand != a.symbols[r.target_symbol_index].value+r.addend:
                assert sec==CRC_SECTION and r.offset in (0xc5d9,0xc5e2,0xc5fc,0xc62f,0xc642,0xc64a)
                symbol=a.symbol('__rc'+str(operand-2))
                changes.update(target=symbol.name,target_symbol_index=symbol.index)
        relocs.append(replace(r,**changes))
    template=next(r for r in a.relocations if r.source_section==CRC_SECTION and r.relocation_type=='R_MOS_ADDR8')
    for address, operand in [(0xc5bb,0x17),(0xc5f5,0x1c),(0xc671,0x1c),
                             (0xc673,4),(0xc676,5),(0xc678,6),(0xc67a,0x17),(0xc67c,7)]:
        symbol=a.symbol('__rc'+str(operand-2))
        relocs.append(replace(template,offset=address,target=symbol.name,target_symbol_index=symbol.index,addend=0))
    crc_rows=sorted((r for r in relocs if r.source_section==CRC_SECTION), key=lambda r:r.offset)
    ordered=[]
    for section in dict.fromkeys(r.relocation_section for r in a.relocations):
        ordered.extend(crc_rows if section=='.rela'+CRC_SECTION else [r for r in relocs if r.relocation_section==section])
    relocs=ordered
    assert relocs==b.relocations, 'unproved relocation change'
    for sec,data in payloads.items():
        assert bytes(data)==b.section_bytes(sec), ('unproved instruction change',sec)
    syms=[]
    for s in a.symbols:
        changes={}
        if s.section in DRIFT_SIZES:
            changes['value']=drift_address(s.section,s.value)
            if s.name in ('c2_session_emit_final_crc_phase','c2_stream_phase_01'):
                changes['bytes']=s.bytes+(6 if s.section==CRC_SECTION else 1)
        syms.append(replace(s,**changes))
    assert syms==b.symbols, 'unproved symbol change'
    for x,y in zip(a.sections,b.sections,strict=True):
        size=DRIFT_SIZES[x.name][1] if x.name in DRIFT_SIZES else x.bytes+48 if x.name=='.rela'+CRC_SECTION else x.bytes
        assert y==replace(x,bytes=size), 'unproved section geometry'
    return payloads,relocs


def project_main_drift(raw,a,b):
    """Whole ELF projection; only the two named overlays may change geometry."""
    assert sha(raw)==BASE_ELF_SHA, 'drift baseline binding'
    payloads,relocs=prove_overlay_drift(a,b)
    shoff=struct.unpack_from('<I',raw,32)[0]
    assert shoff==653936 and len(raw)==662816
    headers=[list(struct.unpack_from('<10I',raw,shoff+i*40)) for i in range(222)]
    # Seven code bytes consume one NOBITS alignment byte and two symtab pads.
    # Four added ADDR8 relocations add 48 bytes after section 199.
    def shift(i):
        if i==0:return 0
        if 54<=i<=81:return 1
        if 82<=i<=109:return 7
        if 110<=i<=130 or i==1:return 6
        if i in (2,3,4,5,6) or 131<=i<=199:return 4
        if i>=200:return 52
        return 0
    expected=bytearray(len(raw)+52)
    expected[:3734]=raw[:3734]
    struct.pack_into('<I',expected,32,shoff+52)
    for s,h in zip(a.sections,headers,strict=True):
        oldoff=h[4];h[4]+=shift(s.index)
        data=raw[oldoff:oldoff+s.bytes]
        if s.name in payloads:data=bytes(payloads[s.name])
        if s.section_type=='SHT_RELA':
            rows=[r for r in relocs if r.relocation_section==s.name]
            oldrows=[r for r in a.relocations if r.relocation_section==s.name]
            types={r.relocation_type:struct.unpack_from('<I',raw,oldoff+j*12+4)[0]&255 for j,r in enumerate(oldrows)}
            data=b''.join(struct.pack('<III',r.offset,r.target_symbol_index*256+types[r.relocation_type],r.addend&0xffffffff) for r in rows)
        if s.name=='.symtab':
            data=bytearray(data)
            for sym in b.symbols:struct.pack_into('<II',data,sym.index*16+4,sym.value,sym.bytes)
        if s.section_type not in ('SHT_NOBITS','SHT_NULL'):
            expected[h[4]:h[4]+len(data)]=data
            h[5]=len(data)
        struct.pack_into('<10I',expected,shoff+52+s.index*40,*h)
    for i in range(109):
        at=52+i*32
        ph=list(struct.unpack_from('<8I',raw,at))
        # PT_LOAD ownership includes NOBITS sections sharing physical offsets.
        delta=1 if 33<=i<=60 else 7 if 61<=i<=88 else 6 if 89<=i<=107 else 0
        ph[1]+=delta
        if i==32:ph[4]+=1;ph[5]+=1
        if i==60:ph[4]+=6;ph[5]+=6
        if 33<=i<=60:ph[3]+=1
        elif 61<=i<=86 or 104<=i<=107:ph[3]+=7
        struct.pack_into('<8I',expected,at,*ph)
    return expected,dict(status='PASS',bounds={k:y-x for k,(x,y) in DRIFT_SIZES.items()},
                         proof='exact instruction, symbol, relocation and physical ELF projection')


def native_price_proof(paths,truths,delta,sites,sections):
    assert delta=={'.text':0,'.rodata':0,'BSS':0,'CRT_zero_bytes':0}, 'unproved native growth'
    expected_sections=[dict(name=k,before=x,after=y,delta=y-x) for k,(x,y) in DRIFT_SIZES.items()]
    expected_sites=[dict(name=n,section=s,before=x,after=y,delta=y-x) for n,s,x,y in
                    [('c2_session_emit_final_crc_phase',CRC_SECTION,894,900),('c2_stream_phase_01',DECODE_SECTION,1305,1306)]]
    assert sorted(sections,key=lambda r:r['name'])==sorted(expected_sections,key=lambda r:r['name'])
    assert sorted(sites,key=lambda r:r['name'])==sorted(expected_sites,key=lambda r:r['name'])
    _,proof=project_main_drift(Path(paths[0]).read_bytes(),*truths)
    b=truths[1]
    for name,limit in (('.text',0xb3b0),('.rodata',0xb98c)):
        s=b.section(name);assert s.address+s.bytes<=limit
    assert b.symbol('__bss_end').value<=0xc000
    assert b.section(CRC_SECTION).bytes<=1792 and b.section(DECODE_SECTION).bytes<=1792
    owners={}
    for fam in ('boot','session'):
        value=load(FINAL/'media'/('runtime-overlays-'+fam+'-final.json'))
        regions={0:bytearray((FINAL/'media/artifacts'/(fam+'.bin')).read_bytes()),
                 1:bytearray((FINAL/'media'/value['overflow_storage']['file']).read_bytes())}
        if fam=='session':regions[2]=bytearray(truths[0].section_bytes('.lisp65_rt_card2b_disk'))
        prepare_overlay_capacity(fam,value,regions,*truths)
        owners[fam]=dict(bytes=len(regions[0]),carrier_free=65536-len(regions[0]))
    proof['owners']=owners
    return proof


def replacement_projection_selftest():
    import tempfile
    from unittest.mock import patch
    import runtime_overlay_bank as BANK
    with tempfile.TemporaryDirectory(prefix='walks-producer-selftest-') as tmp:
        root=Path(tmp);here=root/'receipts';build=root/'product'
        with patch.dict(globals(),ROOT=root,HERE=here,BUILD=build), patch.object(subprocess,'run',side_effect=AssertionError('native command forbidden')), patch.object(subprocess,'check_output',side_effect=AssertionError('native command forbidden')):
            native=here/'native-inputs';native.mkdir(parents=True)
            old_code,new_code=49959,50007
            old_size,new_size=19706,19754
            header='#define LISP65_BYTECODE_STDLIB_BASE_ADDR 0x050000u\n#define LISP65_BYTECODE_STDLIB_BLOB_BYTES 19706u\n'+''.join(f'#define LISP65_BYTECODE_STDLIB_{k} 0u\n' for k in ('LITERAL_INDEX_COUNT','LITERAL_NODE_COUNT','LITERAL_PATCH_COUNT'))
            once(native/'stdlib-p0.h',header)
            once(native/'c2_lite_static_plane.h','#define LISP65_C2_LITE_STATIC_CODE_BYTES 49959UL\n')
            once(native/'owner.compiler-input-assert.h','#if LISP65_C2_LITE_STATIC_CODE_BYTES != 49959UL\n#error wrong header\n#endif\n')
            data={}
            for side,size in [('baseline',old_size),('candidate',new_size)]:
                out=here/'plane'/side
                save(out/'stdlib-p0.manifest.json',dict(code_bytes=size,literal_index=[],literal_nodes=[],literal_patches=[]))
                once(out/'stdlib-p0.h',header.replace('19706',str(size)).replace('0x050000', '0x000000'))
                for name in ('SHELF.BIN','C2D.BIN'):
                    raw=bytearray(224)
                    if name=='C2D.BIN':struct.pack_into('<H',raw,28,32)
                    if side=='candidate':raw[40]=1
                    data[side,name]=bytes(raw);once(out/name,raw)
            source=''
            for name,file in [('shelf','SHELF.BIN'),('c2d','C2D.BIN')]:
                raw=data['baseline',file]
                crcs=[BANK.crc16_ccitt_false(raw[32+i*32:32+(i+1)*32]) for i in range(6)]
                source+='c2_phase02a_'+name+'_crc16:\\n'+'\\n'.join(f'.short 0x{x:04x}' for x in crcs)+'\\n'
            once(native/'crc.c',source)
            flags=['cc','-c',str((native/'crc.c').relative_to(root)),'-DLISP65_C2_PRODUCT_BUILD_ID=0x11111111UL','-DLISP65_C2_PRODUCT_SHELF_BYTES=224UL','-include',str((native/'stdlib-p0.h').relative_to(root))]
            commands=[list(flags) for _ in range(75)]
            save(here/'baseline-command-proof.json',dict(commands=commands))
            ready=dict(authority=AUTH,commands=bind(here/'baseline-command-proof.json'),native=[dict(source=bind(p),restored=bind(p)) for p in sorted(native.iterdir())])
            plane=dict(before_product=dict(product_build_id_hex='0x11111111',artifacts=dict(shelf=dict(bytes=224))),after_product=dict(product_build_id_hex='0x22222222',artifacts=dict(shelf=dict(bytes=224))),before_geometry=dict(code_bytes=old_code),after_geometry=dict(code_bytes=new_code))
            projected=derived_commands(ready,plane)
            proof=load(here/'derived-inputs.json')
            assert len(projected)==75 and proof['stdlib_header_changed']
            assert len(proof['header_changes'])==3
            assert all('receipts/native-inputs/' not in a for c in projected for a in c)
            assert (here/'candidate-inputs/stdlib-p0.h').read_text()==header.replace('19706','19754')
            assert (native/'stdlib-p0.h').read_text()==header
            assert '50007UL' in (here/'candidate-inputs/owner.compiler-input-assert.h').read_text()
            assert load(here/'command-proof.json')['commands']==projected
            for side, old, new, message in (
                ('baseline', '19706u', '19705u', 'frozen stdlib header not reproduced'),
                ('baseline', '0x000000u', '0x010000u', 'unexpected static stdlib address origin'),
                ('candidate', '0x000000u', '0x010000u', 'unexpected static stdlib address origin'),
                ('candidate', '19754u', '19755u', 'unclassified stdlib header change')):
                path=here/'plane'/side/'stdlib-p0.h';original=path.read_text()
                path.write_text(original.replace(old,new))
                try:
                    derived_commands(ready,plane)
                except AssertionError as error:
                    assert str(error)==message, str(error)
                else:
                    raise AssertionError('header mutation survived')
                finally:
                    path.write_text(original)
    return ['75-command exact substitution', 'CRC tables', 'stdlib header', 'static extent', 'compiler assertions', 'immutable baseline']


def preparation_selftest():
    import tempfile
    from unittest.mock import patch
    # Exercise the probe's actual preparation boundary, without product work.
    with tempfile.TemporaryDirectory(prefix='strings-probe-selftest-') as tmp:
        here=Path(tmp)/'seed';build=Path(tmp)/'product';events=[]
        def emit(ready):
            events.append('plane');once(here/'plane/baseline/header',b'plane')
            save(here/'plane-price.json',{});return 'plane'
        def derive(ready,plane):
            assert plane=='plane';events.append('derive')
            once(here/'derived/input',b'derived');once(here/'candidate-inputs/header',b'header')
            save(here/'derived-inputs.json',{});save(here/'command-proof.json',{})
            return ['complete commands']
        def includes(commands,ready):
            assert commands==['complete commands'];events.append('includes')
            save(here/'include-closure.json',{})
        with patch.dict(globals(),HERE=here,BUILD=build), \
             patch(__name__+'.emit_planes',side_effect=emit), \
             patch(__name__+'.derived_commands',side_effect=derive), \
             patch(__name__+'.include_closure',side_effect=includes):
            ready={};prepare_commands(ready)
            assert events==['plane','derive','includes'] and len(ready['prepared'])==7
            for row in ready['prepared']:checked(row)
            assert not build.exists() and not (here/'command-ready.json').exists()
            for failing in ('emit_planes','derived_commands','include_closure'):
                with patch(__name__+'.'+failing,side_effect=AssertionError('probe defect')):
                    failed={}
                    try:prepare_commands(failed)
                    except AssertionError as error:assert str(error)=='probe defect'
                    else:raise AssertionError('preparation defect survived')
                    assert 'prepared' not in failed and not build.exists()
            (here/'candidate-inputs/header').write_bytes(b'drift')
            try:
                for row in ready['prepared']:checked(row)
            except AssertionError:pass
            else:raise AssertionError('prepared input drift survived')
    return ['complete derivation before readiness', 'preparation failures budget-free',
            'prepared byte bindings reject drift']


def selftest():
    from unittest.mock import patch
    from types import SimpleNamespace as NS
    import tempfile
    import walks_seed_producer as W
    # Retain predecessor synthetic media/byte classification controls, without
    # inheriting the old walks-specific main shrink as a strings permission.
    inherited=W.selftest()
    replacement=replacement_projection_selftest()
    preparation=preparation_selftest()
    with patch.object(subprocess,'run',side_effect=AssertionError('command forbidden')),patch.object(subprocess,'check_output',side_effect=AssertionError('command forbidden')):
        plane_budget(dict(bound=250,delta={'CODE.BIN':48,'C2D.BIN':0,'SHELF.BIN':56},library_growth=100,total_growth=204))
        for plane in [dict(bound=150,delta={'CODE.BIN':48,'SHELF.BIN':56,'C2D.BIN':0},library_growth=100,total_growth=204),dict(bound=250,delta={'CODE.BIN':151},library_growth=100,total_growth=251),dict(bound=250,delta={'CODE.BIN':1},library_growth=100,total_growth=100),dict(bound=400,delta={},library_growth=100,total_growth=100)]:
            try:plane_budget(plane)
            except AssertionError:pass
            else:raise AssertionError('budget mutation survived')
        try:project_main_drift(b'',NS(),NS())
        except AssertionError:pass
        else:raise AssertionError('unknown geometry admitted')
        library_budget(960,1060)
        for counts in ((960,1101),(960,1111),(959,1060)):
            try:library_budget(*counts)
            except AssertionError:pass
            else:raise AssertionError('library price mutation survived')
        files={b'REPL-COMFORT':b'old',b'L65INDEX':b'index',b'CODE.BIN':b'code',b'C2D.BIN':b'prefix'+bytes(32)}
        changed=dict(files,**{})
        changed[b'REPL-COMFORT']=b'new';changed[b'L65INDEX']=b'updated'
        media_like_for_like(files,changed)
        for mutant in (dict(changed,FOREIGN=b'bad'),{**changed,b'CODE.BIN':b'wrong'},{**changed,b'C2D.BIN':b'prefix'}):
            try:media_like_for_like(files,mutant)
            except AssertionError:pass
            else:raise AssertionError('foreign media mutation survived')
        static={b'CODE.BIN':b'new-code',b'C2D.BIN':b'new-c2d',b'SHELF.BIN':b'new-shelf'}
        prior={**files,b'SHELF.BIN':b'old-shelf',b'LISP65.PRG':b'old-prg'}
        projected={**prior,**static,b'LISP65.PRG':b'new-prg'}
        media_like_for_like(prior,projected,static,{b'LISP65.PRG':b'new-prg'})
        for mutated,derived in [({**projected,b'CODE.BIN':b'foreign'},{b'LISP65.PRG':b'new-prg'}),
                                (projected,{b'LISP65.PRG':b'foreign'}),
                                (projected,{b'FOREIGN':b'bad'})]:
            try:media_like_for_like(prior,mutated,static,derived)
            except AssertionError:pass
            else:raise AssertionError('static/derived media mutation survived')
        # Real D81 chains and index CRCs, with synthetic package bytes. Growth
        # crosses a sector boundary and must remain provisional until reindexed.
        import d81_persistence_fault as D
        import c2_require_resolver_gate as L
        old_payload, new_payload = bytes(250), bytes([42])*350
        original = D.seed_file(bytes(D.blank_image()), 'repl-comfort', old_payload)
        slot, = [s for s in D.directory_slots(original) if s.record[2]]
        track, sector = D.file_chain(original, slot.record)[0]
        row = dict(name='repl-comfort', track=track, sector=sector,
            combined_crc32=1, dependencies=[], execution_source=L.SOURCE_BANK2,
            artifact_bytes=250, bank2=960, images=1, entries=1,
            resolutions=1, roots=1, scratch=8)
        old_index = L.encode_index([row])
        original = D.seed_file(original, 'l65index', old_index)
        index_slot, = [s for s in D.directory_slots(original)
                       if s.record[2] and D.entry_name(s.record) == b'L65INDEX']
        slack = D.sector_offset(*D.file_chain(original, index_slot.record)[-1])+255
        original = bytearray(original);original[slack] = 0x5a;original = bytes(original)
        assert D.visible_files(original)[b'REPL-COMFORT'] == old_payload
        ledger = {}
        provisional = replace_file(original, 'repl-comfort', new_payload, ledger)
        try:D.visible_files(provisional)
        except ValueError as error:assert 'indexed file length' in str(error)
        else:raise AssertionError('stale index admitted')
        updated = dict(row, artifact_bytes=350, bank2=1060, combined_crc32=2)
        index = media_index_control(L, old_index, [updated])
        complete = replace_file(provisional, 'l65index', index, ledger)
        assert complete[slack] == 0x5a and slack not in ledger
        assert D.visible_files(complete) == {b'REPL-COMFORT':new_payload,b'L65INDEX':index}
        assert L.decode_index(index) == [updated]
        diff = classify_bytes(original, complete, ledger)
        assert diff['changed_bytes'] and diff['unclassified_bytes'] == 0
        foreign_offset = next(i for i in range(len(complete)) if i not in ledger)
        corrupted = bytearray(complete);corrupted[foreign_offset] ^= 1
        assert classify_bytes(original, corrupted, ledger)['unclassified_bytes'] == 1
        for field, value in (('track', track+1), ('roots', 2), ('name', 'foreign')):
            try:media_index_control(L, old_index, [dict(updated, **{field:value})])
            except AssertionError:pass
            else:raise AssertionError('foreign index field admitted: '+field)
        corrupt_index = bytearray(index);corrupt_index[11] ^= 1
        try:L.decode_index(bytes(corrupt_index))
        except L.GateError:pass
        else:raise AssertionError('stale index CRC admitted')
        assert classify_bytes(b'ab',b'ac',{})['unclassified_bytes']==1
        grown=project_delivery_code(b'code'+bytes(46)+b'NATIVE',b'code',b'code'+b'x'*46)
        assert grown==b'code'+b'x'*46+b'NATIVE'
        delivered=b'code'+b'NATIVE';assert project_delivery_code(delivered,b'code',b'code')==delivered
        try:project_delivery_code(delivered,b'code',b'codeX')
        except AssertionError:pass
        else:raise AssertionError('foreign static growth admitted')
        with tempfile.TemporaryDirectory(prefix='strings-write-once-') as d:
            p=Path(d)/'receipt';once(p,b'a');once(p,b'a')
            try:once(p,b'b')
            except AssertionError:pass
            else:raise AssertionError('receipt rewrite admitted')
    return dict(status='PASS',synthetic_only=True,product_commands=0,inherited=inherited,replacement=replacement,preparation=preparation,
        controls=['aggregate +250','library 1100 and geometry mutation controls','media population/code/C2D drift rejected','package growth transaction and stale index rejection','index field and CRC mutation controls','D81 allocation diff and foreign byte rejection','wrong bound/sum rejected','write-once','unproved native geometry rejected','unclassified byte rejected','native media suffix preserved'],
        bounds=dict(library=LIBRARY_BOUND,library_plane_growth=PLANE_BOUND,native=0,inventory_unclassified=0))


if __name__=='__main__':
    main()
