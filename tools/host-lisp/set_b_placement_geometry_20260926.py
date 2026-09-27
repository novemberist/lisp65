"""Derive canonical 32-byte tenant extents; update reviewed source descriptors."""
from pathlib import Path
import re
import set_b_producer as P
ROOT=P.ROOT
OUT=ROOT/'build/set-b-placement-r1/geometry-r3'

def main():
    OUT.mkdir(exist_ok=False)
    proposal=P.load(ROOT/'build/set-b-placement-r1/review-r2/proposal.json')
    rows=[];offset=0
    for previous in proposal['tenants']:
        row=dict(previous);n=row['budget_bytes'];extent=(n+16+31)&~31
        row.update(offset=offset,interval=extent,air=extent-n,source_address=0x5de80+offset)
        rows.append(row);offset+=extent
    assert offset==6720 and all(r['air']>=16 for r in rows)
    data=P.load(P.INPUTS)
    for t,r in zip(data['tenants'],rows):
        assert t['slot']==r['slot']
        t.update(offset=r['offset'],source_address=r['source_address'],projected_bytes=r['budget_bytes'])
    data['aligned_extent']=offset
    data['image']['status']='ELF-derived after AUTH; tenant payloads zero-padded to bound intervals, 0xA5 tail after aligned_extent'
    P.write(P.INPUTS,data)
    header=ROOT/'config/set-b-native/set-b-placement.h';text=header.read_text()
    for r in rows:
        text,n=re.subn(r'(#define SET_B_'+str(r['slot'])+r'_OFFSET )0x[0-9A-F]+u',
                      lambda m:m[1]+f"0x{r['offset']:04X}u",text)
        assert n==1
    header.write_text(text)
    closure=P.load(P.CLOSURE)
    def update(v):
        if isinstance(v,dict):
            if v.get('path','').endswith('config/set-b-native/set-b-placement.h') and 'sha256' in v:
                v.update(P.bind(ROOT/v['path']))
            for x in v.values():update(x)
        elif isinstance(v,list):
            for x in v:update(x)
    update(closure);P.write(P.CLOSURE,closure)
    receipt=dict(status='CANONICAL PADDED GEOMETRY; HOST VALIDATION PENDING',
        driver=P.bind(Path(__file__)),prior_proposal=P.bind(ROOT/'build/set-b-placement-r1/review-r2/proposal.json'),
        policy_source=P.bind(ROOT/'tools/host-lisp/runtime_overlay_bank.py'),
        tenants=rows,reserved_extent=offset,tail_bytes=8192-offset,
        payload_alignment=32,minimum_code_headroom=16,delivery_padding='authenticated zero bytes through each interval end',
        prior_16_byte_proposal='superseded: strict canonical catalog requires 32-byte alignment and no unrecorded reserve gaps',
        product_links=0,seeds=0,finals=0,device_contacts=0)
    P.write(OUT/'receipt.json',receipt)
    revision=P.load(ROOT/'config/set-b-native/placement-revision.json')
    revision.update(backing_alignment=32,reserved_extent=offset,geometry=P.bind(OUT/'receipt.json'),
                    delivery_padding='Each record covers its full zero-padded interval; all CRCs include padding')
    P.write(ROOT/'config/set-b-native/placement-revision.json',revision)
    print('Prepared canonical geometry:',[r['offset'] for r in rows],'; extent',offset,'tail',8192-offset)

if __name__=='__main__':main()
