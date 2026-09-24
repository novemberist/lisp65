"""Account the net Cons allocations without confusing shifted C2D ordinals."""
from collections import Counter
from pathlib import Path
import json, hashlib
import definition_set_a_attribution_seal as S

ROOT=S.ROOT;HERE=ROOT/'build/definition-set-a-r3'
worlds={}
for role in ('before','seed'):
    r=S.receipt(f'build/definition-set-a-auth-alloc-{role}-5-r1')
    raw=S.A.checked(r['outputs']['memory']).read_bytes()
    header=raw[0x50000:0x50030]
    def u16(b,o):return int.from_bytes(b[o:o+2],'little')
    imageoff=u16(header,28);entryoff=u16(header,30);n=u16(header,16)
    images=[raw[0x50000+imageoff+i*32:0x50000+imageoff+(i+1)*32] for i in range(u16(header,12))]
    names=[x['name'] for x in json.loads(S.A.checked(r['manifest']).read_text())['entries']]
    counts=S.A.subtract(S.A.counts(r['whole']['after'],'A'),S.A.counts(r['whole']['before'],'A'))
    byowner=Counter();mapping=[]
    for ordinal,count in counts.items():
        if not count:continue
        assert ordinal<n
        row=raw[0x50000+entryoff+ordinal*10:0x50000+entryoff+(ordinal+1)*10]
        image=row[0];local=ordinal-u16(images[image],6)
        assert 0<=local<u16(images[image],8)
        key=names[ordinal] if image==0 else f'image-{image}/entry-{local}'
        byowner[key]+=count;mapping.append(dict(ordinal=ordinal,image=image,local=local,owner=key,allocations=count))
    worlds[role]=dict(total=sum(counts.values()),owners=dict(byowner),mapping=mapping,
                      receipt=S.bind(ROOT/f'build/definition-set-a-auth-alloc-{role}-5-r1/receipt.json'))
# The shifted anonymous compiler ordinals name identical consumed code/metadata,
# not newly allocated functions. Image 5 is the existing compiler in both C2Ds.
compiler=[]
for world in ('transient-retirement-final-medium-r1','definition-set-a-seed-medium-r2'):
    folder=ROOT/f'build/{world}/materialized/fresh-c2-lite-prelink-gates/product'
    compiler.append([S.bind(folder/f'lcc.{suffix}.bin') for suffix in ('code','c2i')])
assert [x['sha256'] for x in compiler[0]]==[x['sha256'] for x in compiler[1]]
a,b=(Counter(worlds[x]['owners']) for x in ('before','seed'))
delta={k:v for k,v in S.A.subtract(b,a).items() if v}
assert delta=={'%c2-source-form':54,'%reverse-into':-17,'%append2-rev':-15,'list':5,'append':-2},delta
assert sum(delta.values())==25
result=dict(status='PASS: NET 25 CONS ACCOUNTED BY EXECUTED CURRENT-BUFFER OWNER',worlds=worlds,
            deltas=delta,compiler_identity=compiler,
            interpretation='18 three-cell Prim-66 argument tuples add 54; grouped list construction/traversal nets minus 29. Native authentication does not allocate.',
            limits=['Current VM buffer owner is explicitly observed, not an inferred full call tree.',
                    '14 versus 13 collections is observed; no counterfactual claim that subtracting these 25 alone removes exactly one collection.'])
(HERE/'allocation-attribution.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],delta)
