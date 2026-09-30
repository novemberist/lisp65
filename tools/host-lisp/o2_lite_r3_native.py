"""Exact STRINGS-to-O2-lite r3 native constant/codegen projection.

Only two existing overlays shrink. The source and 75 native commands remain
frozen; these rules classify the single link's instructions, relocations,
symbols and physical ELF packing. No compilation or link occurs here.
"""
import struct
import re
from dataclasses import replace
import strings_seed_producer as S
CRC_SECTION = '.lisp65_rt_c2emit_final_crc'
DECODE_SECTION = '.lisp65_rt_c2d_01'
SIZES = {DECODE_SECTION:(1703,1702), CRC_SECTION:(1250,1246)}
BASE_ELF_SHA = 'd514e4980c636cab0c6ae1ee9bea77afdd3a4fdf58f01995aba5ff822e89ed05'
EDITS = {'.lisp65_rt_c2d_01': [[50396, 'a900481a', 'a901'], [50408, '68', 'a900'], [50787, 'c902', 'c93c'], [50814, 'c9b5', 'c973'], [50837, 'c9ba', 'c90a'], [50848, 'c907', 'c9a8']], '.lisp65_rt_c2emit_final_crc': [[50618, '8517', ''], [50650, '861c', '8617'], [50659, 'a61c', 'a617'], [50676, '851c', ''], [50687, '861d', '861c'], [50710, '', '8517'], [50738, '861e', '861d'], [50757, 'a61d', 'a61c'], [50765, 'a51e', 'a51d'], [50793, 'a916a2baa0b548a51c850468', 'a2a8a073a93c8604a617'], [50809, 'a6178607', '8507'], [50815, '', 'a916']]}
NEW_RELOCS = {'.lisp65_rt_c2d_01': [], '.lisp65_rt_c2emit_final_crc': [[50649, 'R_MOS_ADDR8', '__rc21', 0], [50658, 'R_MOS_ADDR8', '__rc21', 0], [50684, 'R_MOS_ADDR8', '__rc26', 0], [50707, 'R_MOS_ADDR8', '__rc21', 0], [50737, 'R_MOS_ADDR8', '__rc27', 0], [50756, 'R_MOS_ADDR8', '__rc26', 0], [50764, 'R_MOS_ADDR8', '__rc27', 0], [50798, 'R_MOS_ADDR8', '__rc2', 0], [50800, 'R_MOS_ADDR8', '__rc21', 0], [50806, 'R_MOS_ADDR8', '__rc5', 0]]}


def address(section,value):
    return value+sum(len(bytes.fromhex(new))-len(bytes.fromhex(old))
        for at,old,new in EDITS.get(section,[]) if value>=at+len(bytes.fromhex(old)))


def prove(a,b):
    payloads={};relocs=[]
    for section,sizes in SIZES.items():
        assert (a.section(section).bytes,b.section(section).bytes)==sizes
        assert a.section(section).address==b.section(section).address==0xc356
        data=bytearray(a.section_bytes(section))
        for at,old,new in reversed(EDITS[section]):
            old,new=bytes.fromhex(old),bytes.fromhex(new)
            assert data[at-0xc356:at-0xc356+len(old)]==old
            data[at-0xc356:at-0xc356+len(old)]=new
        payloads[section]=data
    for r in a.relocations:
        sec=r.source_section
        if sec not in SIZES:
            assert r.target not in SIZES
            relocs.append(r);continue
        if any(at<=r.offset<at+len(bytes.fromhex(old)) for at,old,new in EDITS[sec]):continue
        offset=address(sec,r.offset);changes=dict(offset=offset)
        if r.target==sec:
            target=address(sec,0xc356+r.addend);changes['addend']=target-0xc356
            if r.relocation_type=='R_MOS_ADDR16':struct.pack_into('<H',payloads[sec],offset-0xc356,target)
            else:
                assert r.relocation_type=='R_MOS_PCREL8'
                displacement=target-(offset+1);assert -128<=displacement<=127
                payloads[sec][offset-0xc356]=displacement&255
        relocs.append(replace(r,**changes))
    for sec,rows in NEW_RELOCS.items():
        for at,kind,name,addend in rows:
            template=next(r for r in a.relocations if r.source_section==sec and r.relocation_type==kind)
            sym=a.symbol(name)
            relocs.append(replace(template,offset=at,target=name,target_symbol_index=sym.index,addend=addend))
    relocs=[r for sec in dict.fromkeys(r.relocation_section for r in a.relocations)
              for r in (sorted((r for r in relocs if r.relocation_section==sec),key=lambda r:r.offset)
                        if sec=='.rela'+CRC_SECTION else [r for r in relocs if r.relocation_section==sec])]
    assert relocs==b.relocations, 'unproved relocation change'
    for sec,data in payloads.items():assert bytes(data)==b.section_bytes(sec),('unproved instruction change',sec)
    syms=[]
    for sym in a.symbols:
        changes={}
        if sym.section in SIZES:
            changes['value']=address(sym.section,sym.value)
            if sym.name in ('c2_session_emit_final_crc_phase','c2_stream_phase_01'):
                x,y=SIZES[sym.section];changes['bytes']=sym.bytes+y-x
        syms.append(replace(sym,**changes))
    assert syms==b.symbols,'unproved symbol change'
    for x,y in zip(a.sections,b.sections,strict=True):
        size=SIZES[x.name][1] if x.name in SIZES else x.bytes-24 if x.name=='.rela'+CRC_SECTION else x.bytes
        assert y==replace(x,bytes=size),'unproved section geometry'
    return payloads,relocs


def project(raw,a,b):
    assert S.sha(raw)==BASE_ELF_SHA
    payloads,relocs=prove(a,b)
    shoff=struct.unpack_from('<I',raw,32)[0]
    assert shoff==653988 and len(raw)==662868
    assert struct.unpack_from('<H',raw,48)[0]==222
    assert struct.unpack_from('<H',raw,44)[0]==109
    headers=[list(struct.unpack_from('<10I',raw,shoff+i*40)) for i in range(222)]
    def shift(i):
        if 54<=i<=81:return -1
        if 82<=i<=109:return -5
        if 110<=i<=199 or 1<=i<=6:return -4
        if i>=200:return -28
        return 0
    expected=bytearray(len(raw)-28);expected[:3734]=raw[:3734]
    struct.pack_into('<I',expected,32,shoff-28)
    for sec,h in zip(a.sections,headers,strict=True):
        oldoff=h[4];h[4]+=shift(sec.index)
        data=raw[oldoff:oldoff+sec.bytes]
        if sec.name in payloads:data=bytes(payloads[sec.name])
        if sec.section_type=='SHT_RELA':
            rows=[r for r in relocs if r.relocation_section==sec.name]
            oldrows=[r for r in a.relocations if r.relocation_section==sec.name]
            types={r.relocation_type:struct.unpack_from('<I',raw,oldoff+j*12+4)[0]&255 for j,r in enumerate(oldrows)}
            data=b''.join(struct.pack('<III',r.offset,r.target_symbol_index*256+types[r.relocation_type],r.addend&0xffffffff) for r in rows)
        if sec.name=='.symtab':
            data=bytearray(data)
            for sym in b.symbols:struct.pack_into('<II',data,sym.index*16+4,sym.value,sym.bytes)
        if sec.section_type not in ('SHT_NOBITS','SHT_NULL'):
            expected[h[4]:h[4]+len(data)]=data;h[5]=len(data)
        struct.pack_into('<10I',expected,shoff-28+sec.index*40,*h)
    for i in range(109):
        at=52+i*32;ph=list(struct.unpack_from('<8I',raw,at))
        ph[1]+= -1 if 33<=i<=60 else -5 if 61<=i<=88 else -4 if 89<=i<=107 else 0
        if i==32:ph[4]-=1;ph[5]-=1
        if i==60:ph[4]-=4;ph[5]-=4
        if 33<=i<=60:ph[3]-=1
        elif 61<=i<=86 or 104<=i<=107:ph[3]-=5
        struct.pack_into('<8I',expected,at,*ph)
    return expected,dict(status='PASS',bounds={k:y-x for k,(x,y) in SIZES.items()},
        proof='exact instruction, symbol, relocation and physical ELF projection')


def inventory(paths, raws, truths, here, listing_reader=None):
    HERE=here
    ROOT=S.ROOT
    """Read-only classification core; acceptance receipt is written by inventory."""
    a, b = truths
    drift = a.sections != b.sections
    if drift:
        assert len(a.sections) == len(b.sections), 'unproved owner capacity'
        expected, proof = project(raws[0], a, b)
    else:
        assert a.symbols == b.symbols and a.relocations == b.relocations, 'ELF identity drift'
        expected, proof = bytearray(raws[0]), None
    plane = S.load(HERE / 'plane-price.json')
    for row in plane['artifacts']:
        S.checked(row)
    derived = S.load(HERE / 'derived-inputs.json')
    labels = ['proven overlay codegen / ELF packing metadata' if drift else 'unchanged']*max(len(expected),len(raws[0]))
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
                   S.run(command, HERE / 'inventory-logs' / (name + '.log')).decode())
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
    result = S.classify_bytes(*raws, domains)
    result.update(status='PASS' if result['unclassified_bytes'] == 0 else 'HALT: UNCLASSIFIED',
                  geometry_proof=proof, expected_elf_sha256=S.sha(expected))
    return result



def selftest(paths,truths,here):
    import copy
    rejected=[]
    a,b=truths
    damaged=copy.deepcopy(b)
    section=b.section(DECODE_SECTION)
    payload=bytearray(damaged._section_data[section.index]);payload[0]^=1
    damaged._section_data[section.index]=bytes(payload)
    try:prove(a,damaged)
    except AssertionError:rejected.append('foreign overlay instruction')
    else:raise AssertionError('foreign overlay instruction accepted')
    damaged=copy.deepcopy(b)
    damaged.sections[7]=replace(damaged.sections[7],bytes=damaged.sections[7].bytes+1)
    try:prove(a,damaged)
    except AssertionError:rejected.append('foreign section geometry')
    else:raise AssertionError('foreign section geometry accepted')
    raws=[p.read_bytes() for p in paths]
    shoff=struct.unpack_from('<I',raws[1],32)[0]
    offset=struct.unpack_from('<I',raws[1],shoff+b.section('.text').index*40+16)[0]
    raw=bytearray(raws[1]);raw[offset]^=1
    result=inventory(paths,[raws[0],bytes(raw)],truths,here,
        listing_reader=lambda command,name:(here/'inventory-logs'/(name+'.log')).read_text())
    assert result['unclassified_bytes']==1 and result['status']=='HALT: UNCLASSIFIED'
    rejected.append('foreign resident instruction')
    return dict(status='PASS',rejected=rejected)
