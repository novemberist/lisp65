#!/usr/bin/env python3
"""Card L source preparation. No implicit Seed, Final, or product link.

Follows retained_callable_repair_producer's consumed-source projection and
local committed-authority admission. REGISTER_SLICES runs after configure,
like export_publication_producer, because catalog state is process-local.
The sealed marker is bound after link, inside the slot-55 payload.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import struct
import shutil

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'build/card-l-r1'
AUTH = "fee85e6f"
DIFF_BASE = "d7d43762"
BASE = ROOT / 'build/nested-error-recovery-product-r1'
FINAL = ROOT / 'build/nested-error-recovery-final-r1/wplto/lisp65-c2-substitution-linked.prg.elf'
FINAL_SHA = '66165507a8e5ad1d857afdd967f9056be2ce7bbccc332d5328e981398078b47b'
CLOSURE = ROOT / 'config/card-l-native/include-closure.json'
INPUTS = ROOT / 'config/card-l-native/card-l-inputs.json'
RECIPE = ROOT / 'config/card-l-plane/native-recipe.json'
SOURCES = ('src/c2_product_runtime.c', 'src/optional/card_l_stage.c')
TEMPLATE = ROOT / 'tools/host-lisp/retained_callable_repair_producer.py'


def bind(path):
    data = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def load(path):
    return json.loads(path.read_text())


def write_once(path, value):
    """Preserve failed receipts; a differing replay gets a fresh run directory."""
    text = json.dumps(value, indent=2, sort_keys=True) + '\n'
    if path.exists() and path.read_text() != text:
        raise ValueError('refusing to overwrite receipt: ' + str(path))
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def register_and_admit(P):
    """Append exactly slot 55 after inherited 10a/10b configuration."""
    manifest = load(INPUTS)
    spec = manifest['spec']
    predecessor = load(ROOT / 'config/c2-v240-public-plane/native-recipe.json')['values']
    before = list(P.SESSION_SLICE_SPECS)
    if before == predecessor['SESSION_SLICE_SPECS'] + [spec]:
        if len(P.BOOT_SLICE_SPECS) != 12 or P.UNIQUE_SLICE_COUNT != 64:
            raise ValueError('idempotent Card L registration drift')
        return
    if before != predecessor['SESSION_SLICE_SPECS']:
        raise ValueError('configure must select the exact 2.4.0 Session population first')
    if len(before) != 55 or [int(x.split(':')[0]) for x in before] != list(range(55)):
        raise ValueError('slot 55 is not the catalog tail')
    if list(P.BOOT_SLICE_SPECS) != predecessor['BOOT_SLICE_SPECS']:
        raise ValueError('Boot catalog drift')
    if P.UNIQUE_SLICE_COUNT != 63 or manifest['slot'] != 55:
        raise ValueError('catalog or source pin drift')
    P.SESSION_SLICE_SPECS = before + [spec]
    P.UNIQUE_SLICE_COUNT = 64
    P.assert_unique_public_specs()
    if P.SESSION_SLICE_SPECS != load(RECIPE)['values']['SESSION_SLICE_SPECS']:
        raise ValueError('recipe/registration disagreement')


REGISTER_SLICES = register_and_admit


def decode(value):
    if isinstance(value, dict):
        if set(value) == {'path'}:
            return ROOT / value['path']
        return {key: decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [decode(item) for item in value]
    return value


def configure(P):
    """Restore the recorded world, then register the new slice in this process.

    No public predecessor's manifest, include authority, or tool is modified.
    This is source/command preparation, not admission to the product linker.
    """
    predecessor = load(ROOT / 'config/c2-v240-public-plane/native-recipe.json')
    for name, value in predecessor['values'].items():
        value = decode(value)
        kind = predecessor['value_types'][name]
        if kind == 'tuple':
            value = tuple(value)
        elif kind == 'set':
            value = set(value)
        setattr(P, name, value)
    REGISTER_SLICES(P)
    original_sources = P.source_list
    def source_list(features=()):
        sources = list(original_sources(features))
        stage = str(ROOT / SOURCES[1])
        if stage not in sources:
            sources.append(stage)
        return sources
    P.source_list = source_list
    P.linker_script = lambda **_kwargs: (ROOT / 'config/card-l-native/linker/c2-substitution.ld').read_text()


def project_runtime():
    """Same exact-context hunk projection as the retained-callable repair."""
    source = SOURCES[0]
    diff = subprocess.check_output(['git', 'diff', DIFF_BASE, '--', source],
                                   cwd=ROOT, text=True)
    text = (BASE / 'wplto/generated-product-sources/c2_product_runtime.c').read_text()
    parts = re.split(r'(^@@[^\n]*\n)', diff, flags=re.M)
    if len(parts) < 3:
        raise ValueError('commissioned runtime hunk absent')
    for index in range(2, len(parts), 2):
        lines = parts[index].splitlines(keepends=True)
        before = ''.join(line[1:] for line in lines if line[:1] in (' ', '-'))
        after = ''.join(line[1:] for line in lines if line[:1] in (' ', '+'))
        if text.count(before) != 1:
            raise ValueError('consumed-source projection context drift')
        text = text.replace(before, after, 1)
    return text


def command_probe():
    import c2_product_substitution_link as P
    import slice_capacity_preflight_20260924 as capacity
    if bind(FINAL)['sha256'] != FINAL_SHA:
        raise ValueError('2.4.0 Final identity drift')
    manifest = load(INPUTS)
    if manifest['source'] != bind(ROOT / SOURCES[1]):
        raise ValueError('stage source binding drift')
    closure = load(CLOSURE)
    if closure['predecessor'] != bind(ROOT / 'config/retained-callable-repair-r2-native/include-closure.json'):
        raise ValueError('include predecessor drift')
    for row in closure['materialized']:
        if row['source']['path'].startswith('config/card-l-native/'):
            if row['source'] != bind(ROOT / row['source']['path']):
                raise ValueError('include source drift')
    if project_runtime() != (HERE / 'consumed-sources/c2_product_runtime.c').read_text():
        raise ValueError('measured runtime differs from source projection')
    import card_l_seed_media as media
    _, boot = media.boot_pack(media.BASE/'materialized', HERE/'producer-boot-probe')
    attic = manifest['attic']
    if boot['slices'][12]['source_address'] != attic['address']:
        raise ValueError('sealed Boot placement drift')
    header = (ROOT/attic['placement_header']).read_text()
    if f"#define CARD_L_MARKER_BOOT_OFFSET 0x{attic['boot_offset']:04X}u" not in header:
        raise ValueError('placement header drift')
    if bind(HERE/'card-l-marker.bin')['sha256'] != manifest['image']['sha256']:
        raise ValueError('marker identity drift')
    configure(P)
    # The measured object includes the four-byte tuple in the Session record.
    price = load(HERE / 'object-price.json')
    rows = {row['name']: row for row in price['translation_units']}
    for row in rows.values():
        if row.get('exit_code', 0) or bind(ROOT / row['object'])['sha256'] != row['sha256']:
            raise ValueError('object evidence missing or stale')
    stage = sum(rows['card-l-stage']['sections'].values())
    delta = sum(rows['runtime-after']['sections'].values()) - sum(rows['runtime-before']['sections'].values())
    if stage > 640 or delta != 13:
        raise ValueError('Card L object budget exceeded')
    capacity.check_predecessor()
    world = capacity.PRE.load_world(ROOT / 'build/nested-error-recovery-seed-medium-r1/materialized')
    projection = capacity.project(world, 'session', 0, [('card-l-stage', stage)])
    if not projection['all_fit']:
        raise ValueError('Session capacity preflight refused the stage')
    run = 1
    while (HERE / f'producer-probe-r{run}').exists():
        run += 1
    out = HERE / f'producer-probe-r{run}'
    out.mkdir()
    write_once(out / 'capacity.json', projection)
    write_once(out / 'command-probe.json', dict(
        status='PASS: SOURCE/CATALOG/OBJECT PROBE; SEED REQUIRES AUTH',
        authority=AUTH, diff_base=DIFF_BASE, template=bind(TEMPLATE),
        predecessor=bind(FINAL), include_closure=bind(CLOSURE),
        recipe=bind(RECIPE), sources=[bind(ROOT / source) for source in SOURCES],
        session_specs=P.SESSION_SLICE_SPECS, boot_count=len(P.BOOT_SLICE_SPECS),
        unique_slices=P.UNIQUE_SLICE_COUNT, stage_bytes=stage, resident_delta=delta,
        feature='-DLISP65_CARD_L_STAGE',
        unresolved=['Seed after AUTH', 'linked inventory and guest gates'],
        product_link=False, seed=False))
    prepare_seed_commands(out / 'seed-command-preview')
    print(out.relative_to(ROOT))


def require_auth():
    if AUTH == 'AUTH_PENDING':
        raise ValueError('Seed refused: reviewer must commit source authority and fill AUTH')
    commit = subprocess.check_output(['git', 'rev-parse', AUTH+'^{commit}'], cwd=ROOT, text=True).strip()
    for member in authority_files():
        committed = subprocess.check_output(['git', 'show', commit+':'+member], cwd=ROOT)
        current = (ROOT/member).read_bytes()
        if member == 'tools/host-lisp/card_l_producer.py':
            # AUTH is the reviewer's post-commit pointer, not a self-referential hash.
            normalize = lambda b: re.sub(rb'^AUTH = [^\n]+', b'AUTH = AUTH_POINTER', b, flags=re.M)
            committed, current = normalize(committed), normalize(current)
        if committed != current:
            raise ValueError('uncommitted Card L authority: '+member)
    return commit


def authority_files():
    return sorted([str(p.relative_to(ROOT)) for folder in ('config/card-l-native', 'config/card-l-plane')
        for p in (ROOT/folder).rglob('*') if p.is_file()] + list(SOURCES) +
        ['tools/host-lisp/card_l_producer.py', 'tools/host-lisp/card_l_seed_media.py'])


def patch_tuple(payload, offset):
    """Only the four authenticated placeholder bytes may change."""
    import runtime_overlay_bank as B
    m = load(INPUTS)
    sealed = m['binding']
    marker = (HERE/'card-l-marker.bin').read_bytes()
    if (len(marker), B.crc16_ccitt_false(marker), hashlib.sha256(marker).hexdigest()) != (
            sealed['image_size'], sealed['crc16'], m['image']['sha256']):
        raise ValueError('sealed marker tuple mismatch')
    if offset < 0 or offset+4 > len(payload) or payload[offset:offset+4] != bytes(4):
        raise ValueError('binding is not a four-byte placeholder inside slot 55')
    data = bytearray(payload)
    struct.pack_into('<HH', data, offset, sealed['image_size'], sealed['crc16'])
    return bytes(data)


def bind_session(world, out):
    """Consume linked symbols, append slot 55 if needed, authenticate its tuple.

    The private disk record at 52 remains in region 2. Growing the main
    directory moves every region-0 payload by 256; region 1/2 stay fixed.
    The original linked ELF stays immutable: form (a) patches extracted bytes.
    """
    from elf_truth import ElfTruth
    import runtime_overlay_bank as B
    m = load(world/'runtime-overlays-session-final.json')
    elf = world/m['elf']['file']
    if hashlib.sha256(elf.read_bytes()).hexdigest() != m['elf']['sha256']:
        raise ValueError('Session ELF identity drift')
    t = ElfTruth.read(elf, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj', include_section_data=True)
    section = t.section('.lisp65_rt_card_l_stage')
    binding = t.symbol('rtov_late_stage_binding')
    entry = t.symbol('card_l_stage_entry')
    if binding.section != section.name or binding.bytes != 4 or entry.section != section.name:
        raise ValueError('slot-55 symbol ownership drift')
    payload = t.section_bytes(section.name)
    return bind_session_payload(world, out, m, payload, section.address, entry.value,
                                binding.value-section.address)


def bind_session_payload(world, out, m, payload, vma, entry, tuple_offset):
    """Pure bank transformation, independently exercised without a Seed."""
    import runtime_overlay_bank as B
    import copy
    m = copy.deepcopy(m)
    image = (world/m['storage']['file']).read_bytes()
    if hashlib.sha256(image).hexdigest() != m['storage']['sha256']:
        raise ValueError('Session storage identity drift')
    count = m['catalog']['slice_count']
    if count not in (55, 56) or [r['id'] for r in m['slices']] != list(range(count)):
        raise ValueError('Session population drift')
    patched = patch_tuple(payload, tuple_offset)
    if len(patched) > 640:
        raise ValueError('linked stage budget exceeded')
    raw = bytearray(image)
    if count == 55:
        old = m['catalog']['payload_offset']
        new = B._align(B.HEADER_SIZE + 56*B.ENTRY_SIZE, B.CATALOG_ALIGNMENT)
        growth = new-old
        if growth != 256:
            raise ValueError('56th-entry directory boundary drift')
        raw = raw[:old] + bytes(growth) + raw[old:]
        for row in m['slices']:
            if row['region_id'] == 0:
                row['file_offset'] += growth
                row['source_address'] += growth
                pos = B.HEADER_SIZE + row['id']*B.ENTRY_SIZE
                struct.pack_into('<H', raw, pos+4, row['source_address'] & 0xffff)
                struct.pack_into('<H', raw, pos+22, 0)
                crc = B.crc16_ccitt_false(raw[pos:pos+B.ENTRY_SIZE])
                if not crc: raise ValueError('forbidden zero record CRC')
                struct.pack_into('<H', raw, pos+22, crc)
                row['record_crc16'] = crc
        offset = B._align(len(raw), 32)
        base = {r['source_address']-r['file_offset'] for r in m['slices'] if r['region_id']==0}
        if len(base) != 1 or offset+len(payload)>65536:
            raise ValueError('Session capacity/source-base drift')
        source = base.pop()+offset
        row = dict(id=55, name='card-l-stage', section='.lisp65_rt_card_l_stage',
            start_symbol='__lisp65_rt_card_l_stage_start', end_symbol='__lisp65_rt_card_l_stage_end',
            entry_symbol='__lisp65_rt_card_l_stage_entry', flags=B.FLAG_RUNTIME|B.FLAG_REUSABLE,
            roles=B._roles(B.FLAG_RUNTIME|B.FLAG_REUSABLE), file_offset=offset,
            file_size=len(payload), memory_size=len(payload), vma=vma, end=vma+len(payload),
            entry=entry, entry_offset=entry-vma, abi_version=B.ENTRY_ABI,
            slice_build_id=m['profile_build_id'], capability_mask=0, region_id=0, source_address=source)
        m['slices'].append(row)
        raw.extend(bytes(offset+len(payload)-len(raw)))
        h = list(B.HEADER.unpack_from(raw)); h[4]=56; h[10]=new
        raw[:B.HEADER_SIZE]=B.HEADER.pack(*h)
        m['catalog'].update(slice_count=56, payload_offset=new)
    row=m['slices'][55]
    if row['section'] != '.lisp65_rt_card_l_stage' or row['vma'] != vma or row['file_size'] != len(payload):
        raise ValueError('slot-55 section identity drift')
    offset=row['file_offset']; source=row['source_address']
    if count == 56 and raw[offset:offset+len(payload)] != payload:
        raise ValueError('slot-55 packed payload differs from linked ELF')
    raw[offset:offset+len(payload)]=patched
    crc=B.crc16_ccitt_false(patched)
    rec=bytearray(B.ENTRY.pack(55,row['flags'],source&0xffff,len(patched),vma,len(patched),
        entry-vma,B.ENTRY_ABI,m['profile_build_id'],crc,0,
        ((source>>16)&15)<<8 | ((source>>20)&255)<<16,0))
    record_crc=B.crc16_ccitt_false(rec)
    if not record_crc: raise ValueError('forbidden zero record CRC')
    struct.pack_into('<H',rec,22,record_crc)
    raw[B.HEADER_SIZE+55*B.ENTRY_SIZE:B.HEADER_SIZE+56*B.ENTRY_SIZE]=rec
    h = list(B.HEADER.unpack_from(raw)); h[11] = len(raw)
    raw[:B.HEADER_SIZE] = B.HEADER.pack(*h)
    B._refresh_catalog_crcs(raw)
    row.update(crc16=crc,record_crc16=record_crc,sha256=hashlib.sha256(patched).hexdigest())
    h=B.HEADER.unpack_from(raw)
    m['catalog'].update(directory_crc16=h[12],header_crc16=h[13])
    m['storage'].update(file='session.bin',size=len(raw),crc16=B.crc16_ccitt_false(raw),
                        sha256=hashlib.sha256(raw).hexdigest())
    m['card_l_tuple']=dict(offset=tuple_offset, size=8192, crc16=0x7B72,
                          mechanism='post-link extracted payload; immutable ELF')
    out.mkdir(parents=True,exist_ok=True)
    (out/'session.bin').write_bytes(raw)
    (out/'session-manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    return bytes(raw)


def prepare_seed_commands(out):
    """Derive the recorded 2.4.0 one-link Seed recipe; never execute here."""
    proof=load(BASE/'wplto/command-proof.json')
    old=str(BASE.relative_to(ROOT))+'/wplto'
    new=str(out.relative_to(ROOT))+'/wplto'
    commands=[[x.replace(old,new) for x in cmd] for cmd in proof['commands']]
    if len([c for c in commands if '-c' not in c]) != 2 or Path(commands[-2][0]).name != 'llvm-link' or '-c' in commands[-1]:
        raise ValueError('predecessor single-link command shape drift')
    runtime=next(c for c in commands if '-c' in c and Path(c[c.index('-c')+1]).name=='c2_product_runtime.c')
    runtime.append('-DLISP65_CARD_L_STAGE')
    stage=list(runtime)
    stage[stage.index('-c')+1]=str(ROOT/SOURCES[1])
    obj=new+'/card-l-stage.o'
    stage[stage.index('-o')+1]=obj
    commands.insert(-2,stage)
    commands[-2].insert(commands[-2].index('-o'),obj)
    out.mkdir(parents=True,exist_ok=True)
    (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    return commands


def seed():
    require_auth()
    command_probe()
    out=HERE/'seed'
    if out.exists(): raise ValueError('Seed output exists; no implicit retry')
    commands=prepare_seed_commands(out)
    # Copy only the consumed source/header/linker population, never prior outputs.
    work=out/'wplto'
    shutil.copytree(BASE/'wplto',work,ignore=shutil.ignore_patterns('*.o','*.elf','*.prg','*.map','*.json','*.txt'))
    (work/'generated-product-sources/c2_product_runtime.c').write_text(project_runtime())
    for name in ('c2-substitution.ld','full-map-linker/c.ld','full-map-linker/commodore.ld','full-map-linker/zp-data.ld'):
        shutil.copyfile(ROOT/'config/card-l-native/linker'/name,work/name)
    # Output directories are explicit and lie entirely under this card.
    for cmd in commands:
        Path(cmd[cmd.index('-o')+1]).parent.mkdir(parents=True,exist_ok=True)
    (out/'invocation.json').write_text(json.dumps(dict(authority=AUTH, commands_started=True))+'\n')
    for i,cmd in enumerate(commands):
        result=subprocess.run(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
            env={**os.environ,'TMPDIR':str(HERE/'tmp')})
        (out/f'command-{i:03d}.log').write_text(result.stdout)
        if result.returncode: raise ValueError(f'Seed stopped at command {i}; no implicit retry')
    from elf_truth import ElfTruth
    elf=work/'resident-island-seed.prg.elf'
    truth=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
    section=truth.section('.lisp65_rt_card_l_stage')
    symbol=truth.symbol('rtov_late_stage_binding')
    if symbol.section != section.name or symbol.bytes != 4:
        raise ValueError('linked tuple ownership drift')
    sealed=patch_tuple(truth.section_bytes(section.name),symbol.value-section.address)
    (out/'slot55-bound-payload.bin').write_bytes(sealed)
    write_once(out/'tuple-write.json',dict(payload=bind(out/'slot55-bound-payload.bin'),
        offset=symbol.value-section.address,size=8192,crc16=0x7B72,
        record_crc='recomputed by bind_session during media packing'))
    # Slot-55 authentication happens during artifact-only media materialization,
    # after linked symbol ownership and the final extracted record are known.
    write_once(out/'linked.json',dict(authority=AUTH, elf=bind(work/'resident-island-seed.prg.elf'),
        status='LINKED SEED; MATERIALIZATION/PRICING/INVENTORY PENDING'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('command-probe', 'dry-run', 'seed'))
    args = parser.parse_args()
    if args.mode == 'seed':
        seed()
    else:
        command_probe()


if __name__ == '__main__':
    main()
