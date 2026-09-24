"""One authorized media-only replacement; retain all other paid chains."""
from pathlib import Path
import argparse,hashlib,json,math
import d81_package_locators as LOC
import legacy_ide_delivery as D
import stager_crc32_card as C

ROOT=Path(__file__).resolve().parents[2]
PRIOR=ROOT/'build/stager-crc32-r2'
SEAL=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/stager-crc32-halt.json'

def inputs():
    seal=json.loads(SEAL.read_text())
    selected={r['path']:r for r in seal['bindings']}
    stager=PRIOR/'autoboot.c65';old=ROOT/seal['record_medium']['path'];bad=ROOT/seal['candidate']['path']
    for p in (stager,old,bad):assert C.bind(p)==selected[str(p.relative_to(ROOT))]
    return old.read_bytes(),stager.read_bytes(),bad.read_bytes(),[C.bind(p) for p in (old,stager,bad)]

def project(raw,stager):
    LOC.qualify(raw);files=D.inventory(raw);row=files['AUTOBOOT.C65']
    need=math.ceil(len(stager)/254)-len(row['sectors']);assert need==4
    # Only BAM-free data sectors may extend the existing stager chain.
    owned={v for f in files.values() for v in f['sectors']}
    spare=[]
    for t in range(1,81):
        if t==40:continue
        _,bitmap=D.BAM.bam_entry(raw,t)
        for s in range(40):
            if bitmap[s//8]&(1<<(s%8)):
                assert (t,s) not in owned
                spare.append((t,s))
    assert len(spare)>=need
    extra=spare[:need];chain=row['sectors']+extra;out=bytearray(raw)
    for t,s in extra:
        b=D.off(40,1 if t<=40 else 2)+16+6*((t-1)%40)
        assert out[b]>0 and out[b+1+s//8]&(1<<(s%8))
        out[b]-=1;out[b+1+s//8]&=~(1<<(s%8))
    out[row['entry']+30:row['entry']+32]=len(chain).to_bytes(2,'little')
    for i,(t,s) in enumerate(chain):
        chunk=stager[i*254:(i+1)*254];p=D.off(t,s)
        out[p:p+2]=bytes(chain[i+1]) if i+1<len(chain) else bytes((0,len(chunk)+1))
        out[p+2:p+256]=chunk+bytes(254-len(chunk))
    result=bytes(out);actual=D.inventory(result)
    assert set(files)==set(actual)
    for n,r in files.items():
        if n!='AUTOBOOT.C65':assert r==actual[n],('retained chain or bytes changed',n)
    assert actual['AUTOBOOT.C65']['data']==stager
    qualification=LOC.qualify(result)
    return result,dict(extra_sectors=extra,old_chain=row['sectors'],new_chain=chain,
                      retained_files=18,locators=qualification)

def preflight(out):
    out.mkdir(parents=True,exist_ok=False)
    raw,stager,bad,bindings=inputs();result,proof=project(raw,stager)
    try:LOC.qualify(bad)
    except ValueError as e:control=str(e)
    else:raise AssertionError('failed pack admitted')
    receipt=dict(status='PASS: IN-MEMORY OWNERSHIP PROJECTION; LINK UNCONSUMED',authority='ba6ffdf2',
                 inputs=bindings,projected_sha256=D.sha(result),proof=proof,negative_control=control,
                 tool=C.bind(Path(__file__)),locator_tool=C.bind(Path(LOC.__file__)))
    (out/'preflight.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'])

def link(out):
    pre=json.loads((out/'preflight.json').read_text())
    assert pre['tool']==C.bind(Path(__file__)) and pre['locator_tool']==C.bind(Path(LOC.__file__))
    raw,stager,bad,bindings=inputs();assert bindings==pre['inputs']
    result,proof=project(raw,stager);assert D.sha(result)==pre['projected_sha256']
    marker=out/'media-link-started.json';assert not marker.exists(),'replacement link consumed'
    marker.write_text('{"authority":"ba6ffdf2","stager_builds":0,"media_links":1}\n')
    p=out/'product.d81';LOC.publish(p,result)
    assert p.read_bytes()==result;LOC.qualify(p.read_bytes())
    # Repeat descriptor validation over bytes read back from the linked medium.
    files=D.inventory(p.read_bytes());desc=files['BOOT.ID']['data'];rows=[]
    import zlib
    for i in range(desc[6]):
        r=desc[16+32*i:48+32*i];name=r[16:].split(b'\0')[0].decode().upper()
        payload=files[name]['data']
        assert len(payload)==int.from_bytes(r[8:12],'little')
        assert zlib.crc32(payload)==int.from_bytes(r[12:16],'little')
        rows.append(dict(name=name,bytes=len(payload),crc32='%08x'%zlib.crc32(payload)))
    old=json.loads((PRIOR/'packed-receipt.json').read_text())
    receipt=dict(status='LINKED; NATIVE QUALIFICATION PENDING',authority='ba6ffdf2',medium=C.bind(p),
        elf=old['elf'],stager_elf=old['stager_elf'],reused_stager=C.bind(PRIOR/'autoboot.c65'),
        proof=proof,descriptor=rows,preflight=C.bind(out/'preflight.json'),
        budget=dict(stager_builds=1,media_links=2,runtime_seeds=0,runtime_finales=0,runtime_links=0),device_contacts=0)
    (out/'packed-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['status'],receipt['medium']['sha256'])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['preflight','link']);p.add_argument('out',type=Path)
    a=p.parse_args();globals()[a.action](a.out.resolve())
