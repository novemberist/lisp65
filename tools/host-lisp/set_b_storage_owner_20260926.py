"""Set B fifth-Seed storage_owner successor; historical derivation and mutations retained.
Prepared before the attempt; execution and receipt closure remain gates.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import storage_owner_preflight as P
from elf_truth import ElfTruth

ROOT=P.ROOT
RECEIPT=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/set-b-storage-owner-receipt-20260926.json'
PREDECESSOR=ROOT/'build/storage-owner-preflight-check/owners.json'
ELF=ROOT/'build/set-b-product-r5/wplto/resident-island-seed.prg.elf'
OBJECT=ELF.with_suffix('.lto.o')
CONFIG=ROOT/'config/set-b-native/set-b-inputs.json'

def validate(owners):
    assert owners==[
        dict(name='storage_symbol_tables',address=0x5c680,bytes=6048),
        dict(name='card_l_gap',address=0x5de20,bytes=96),
        dict(name='card_l_late',address=0x5de80,bytes=8192)], 'Bank-5 owner population/geometry drift'
    for a,b in zip(owners,owners[1:]):assert a['address']+a['bytes']==b['address']
    assert owners[-1]['address']+owners[-1]['bytes']==0x5fe80
    assert 0x60000-(0x5fe80+10)==374

def owners():
    t=ElfTruth.read(ELF,llvm_readobj=P.READOBJ)
    rows=[dict(name=s.name.removeprefix('.noinit.'),address=s.address,bytes=s.bytes)
          for s in t.sections if s.bytes and s.address>>16==5]
    rows.sort(key=lambda r:r['address']);validate(rows)
    c=json.loads(CONFIG.read_text())
    assert [{k:r[k] for k in ('name','address','bytes')} for r in c['owners']]==rows[1:]
    assert c['header']==dict(address=0x5fe80,bytes=10) and c['bank5_tail_floor']==374
    assert c['owners'][0]['tenant']==dict(name='retirement-journal',bytes=72,unassigned=24)
    assert c['aligned_extent']==6752
    assert [r['offset'] for r in c['tenants']]==[0,448,2016,3424,4448,5856,6496]
    return rows

def selftest():
    clean=owners(); rejected=[]
    trials=[]
    for name in ('card_l_gap','card_l_late'):
        trials.append((name+'-omitted',[r for r in clean if r['name']!=name]))
    for field in ('address','bytes'):
        v=deepcopy(clean);v[-1][field]+=1;trials.append(('late-'+field+'-drift',v))
    trials.append(('duplicate-owner',clean+[clean[-1]]))
    for name,value in trials:
        try:validate(value)
        except AssertionError:rejected.append(name)
        else:raise AssertionError('surviving mutation '+name)
    print('Card L storage: SELFTEST PASS mutations=5')
    return rejected

def derive():
    inherited=P.run(ELF,OBJECT)
    return dict(status='PASS: CARD L STORAGE OWNER SUCCESSOR',date='2026-09-25',
        predecessor=P.bind(PREDECESSOR),inherited=inherited,bank5_owners=owners(),
        header=dict(address=0x5fe80,bytes=10),tail_floor=374,mutations=selftest(),
        inputs=[P.bind(CONFIG),P.bind(Path(__file__))],product_builds=0)

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['selftest','check','prepare']);a=p.parse_args()
    if a.action=='selftest':selftest();return
    value=derive()
    if a.action=='prepare':
        assert not RECEIPT.exists();RECEIPT.write_text(json.dumps(value,indent=2)+'\n')
    else:assert json.loads(RECEIPT.read_text())==value,'dated receipt differs'
    print('Card L storage: CHECK PASS owners=3 inherited-mutations=17 new-mutations=5 builds=0')
if __name__=='__main__':main()
