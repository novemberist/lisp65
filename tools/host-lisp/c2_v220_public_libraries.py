#!/usr/bin/env python3
"""Pack the five declared 2.2.0 libraries through the existing L65I codec."""
import json
from pathlib import Path

import c2_v220_public_native as N
import c2_defstruct_foundations_gate as F
import c2_require_resolver_gate as L65I
import c2_lite_media_product as MEDIA

AUTHORITY=N.ROOT/'config/c2-v220-public-plane/libraries/libraries.json'


def emit(row,locator,build_id):
    for item in [row['manifest'],row['blob'],row['suite'],*row['sources']]:N.bound(item)
    entry,data=F.measured_row(row['name'],row['name'],row['shelf'],
        N.local(row['manifest']['path']),tuple(row['dependencies']),*locator,
        product_build_id=build_id)
    import hashlib
    N.require(row['artifact']==dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest()),
              'library artifact differs from accepted world: '+row['name'])
    return entry,data


def build(medium,label,entries,build_id):
    """Two-pass locator construction; only the final D81 is a product medium."""
    authority=json.loads(AUTHORITY.read_bytes())
    N.require(authority['product_build_id']==build_id,'library generation mismatch')
    rows=authority['libraries']
    N.require(len(rows)==5 and len({r['name'] for r in rows})==5,'library population drift')
    N.require(not any(name.lower()=='init.l65' for _,name in entries),'INIT unsupported in 2.2.0')
    out=medium.parent/'five-libraries'
    N.require(not out.exists(),'library pack requires fresh output')
    out.mkdir()
    files=[];placeholder=[];artifacts={}
    for row in rows:
        entry,data=emit(row,(1,1),build_id)
        path=out/(row['name']+'.l65s');path.write_bytes(data)
        files.append((path,row['name']));placeholder.append(entry);artifacts[row['name']]=data
    N.require(len({name.lower() for _,name in entries+files})==len(entries)+len(files),
              'duplicate disk filename')
    index=out/'l65index';index.write_bytes(L65I.encode_index(placeholder))
    entries=[*entries,*files,(index,'l65index')]
    provisional=out/'locator-construction.d81'
    MEDIA.build_d81(provisional,label,entries)
    locators=L65I.d81_locators(provisional)
    indexed=[]
    for row in rows:
        entry,data=emit(row,locators[row['name']],build_id)
        N.require(data==artifacts[row['name']],'locator changed library payload')
        indexed.append(entry)
    index.write_bytes(L65I.encode_index(indexed))
    decoded=L65I.decode_index(index.read_bytes(),artifacts,artifact_build_id=build_id)
    MEDIA.build_d81(medium,label,entries)
    N.require(L65I.d81_locators(medium)==locators,'final locator divergence')
    mutations=L65I.mutation_gate(index.read_bytes(),artifacts,artifact_build_id=build_id)
    visible=L65I.D81.visible_files(medium.read_bytes())
    N.require(visible=={name.upper().encode():path.read_bytes() for path,name in entries},
              'disk readback differs from input files')
    result=dict(status='PASS: FIVE LIBRARIES AND INDEX READ BACK',rows=decoded,
                mutations=mutations,construction_passes=2,qualifying_media=1,
                init_present=False)
    (out/'receipt.json').write_bytes(N.canonical(result))
    return result,entries
