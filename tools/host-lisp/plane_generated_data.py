"""Derive changed generated data by paired emission, never by a filename list."""
import re
import struct
from pathlib import Path
import c2_lite_v6_product_probe as V6
from runtime_overlay_bank import crc16_ccitt_false


def crc_tables(owner, plane):
    text=owner.read_text()
    values={}
    for name in ('shelf','c2d'):
        match=re.search(r'c2_phase02a_'+name+r'_crc16:\\n((?:\.short 0x[0-9a-f]{4}\\n)+)',text)
        assert match, 'delivery CRC table missing: '+name
        values[name]=[int(x,16) for x in re.findall(r'0x([0-9a-f]{4})',match[1])]
    shelf=(plane/'product/product-shelf-v4-direct.bin').read_bytes()
    c2d=(plane/'v6-semantics/initial.c2d-v6.bin').read_bytes()
    count=shelf[7]
    assert count==struct.unpack_from('<H',c2d,12)[0]
    for name,raw,offset in (('shelf',shelf,32),('c2d',c2d,struct.unpack_from('<H',c2d,28)[0])):
        expected=[crc16_ccitt_false(raw[offset+i*32:offset+(i+1)*32]) for i in range(count)]
        assert values[name]==expected, 'delivery CRC mismatch: '+name
    return values


def derive(baseline, successor, qualified, output, bind):
    """Enumerate all outputs of the live generator on both selected worlds.

    The current supported changing data form is assembler .short words.
    Any changing executable text, new output, or old qualified projection
    not matching the generator's baseline data fails closed.
    """
    original=(V6.OUT,V6.PRODUCT_IDENTITY)
    generated=[]
    try:
        for role,plane in (('baseline',baseline),('successor',successor)):
            V6.OUT=plane/'v6-semantics'
            V6.PRODUCT_IDENTITY=plane/'product/substitution-artifacts.json'
            V6.generated_product_sources(output/role)
            generated.append(output/role/'generated-product-sources')
    finally:V6.OUT,V6.PRODUCT_IDENTITY=original
    a,b=generated
    names=lambda root:{p.name for p in root.iterdir() if p.is_file()}
    assert names(a)==names(b), 'generated output population changed'
    rows=[];selected={}
    pattern=r'(?<=\.short )0x[0-9a-f]{4}'
    for name in sorted(names(a)):
        left,right=(p/name for p in (a,b))
        old,new=left.read_bytes(),right.read_bytes()
        row=dict(name=name,baseline=bind(left),successor=bind(right),changed=old!=new)
        if old!=new:
            assert re.sub(pattern,'WORD',old.decode())==re.sub(pattern,'WORD',new.decode()), \
                'unclassified generated code/data change: '+name
            target=qualified/name
            assert target.is_file() and target.read_bytes()==old, \
                'qualified projection differs from baseline generator: '+name
            selected[name]=right
            row['class']='regenerated data words; executable source unchanged'
        rows.append(row)
    # This mandatory consumer contract is independent of the derived exception set.
    owner=b/'c2-stream-phase-02a.c'
    tables=crc_tables(owner,successor)
    try:crc_tables(qualified/owner.name,successor)
    except AssertionError:mutation='old-pounds-tables-rejected-before-WPLTO'
    else:raise AssertionError('stale-table regression survived')
    mutations=[mutation]
    words=list(re.finditer(pattern,owner.read_text()))
    assert len(words)==sum(map(len,tables.values()))
    mutant=output/'mutant-owner.c'
    for index,word in enumerate(words):
        text=owner.read_text()
        mutant.write_text(text[:word.start()]+f'0x{int(word[0],16)^1:04x}'+text[word.end():])
        try:crc_tables(mutant,successor)
        except AssertionError:mutations.append(f'wrong-delivery-word-{index}')
        else:raise AssertionError('wrong CRC word survived')
    return selected,dict(status='PASS',population=rows,changed_members=sorted(selected),
        tables=tables,mutations_rejected=mutations,
        generator=bind(Path(V6.__file__)),
        inputs=[bind(plane/p) for plane in (baseline,successor) for p in
                ('product/substitution-artifacts.json','product/product-shelf-v4-direct.bin',
                 'v6-semantics/initial.c2d-v6.bin')])
