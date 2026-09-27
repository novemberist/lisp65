"""Close minimal-load attribution, raw operands, capacity and repair prices."""
from pathlib import Path
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import retained_callable_writer_analysis as A
ROOT=P.ROOT
OUT=ROOT/'build/set-b-load-analysis-r1'

def main():
    S.require_auth();OUT.mkdir(exist_ok=False);root=ROOT/'build/set-b-load-attribution-r1';rows=[];states={}
    def state(p):
        c=p.read_bytes();counts=A.counts(c);ends=[]
        for i in range(counts['entries']):
            at=A.u(c,30,2)+i*10
            assert A.u(c,at+4,2)>0 and A.u(c,at+8,2)==1
            ends.append(A.u(c,at+2,2)+A.u(c,at+4,2))
        return dict(**counts,code_end=max(ends))
    for n,expect in [(0,'T'),(1,'T'),(2,'NIL')]:
        out=root/f'definitions-{n}';r=P.load(out/'receipt.json');assert r['result']['load_result']==expect
        before=state(out/'before-load-c2d.bin');after=state(out/'after-load-c2d.bin');states[n]=before
        same={region:(out/f'before-load-{region}.bin').read_bytes()==(out/f'after-load-{region}.bin').read_bytes() for region in ['c2d','bank2']}
        if n==2:assert all(same.values())
        c=(out/'before-load-c2d.bin').read_bytes()
        image_rows=[dict(slot=i,raw=c[48+32*i:80+32*i].hex(),base=A.u(c,48+32*i+18,2),size=A.u(c,48+32*i+21,2)) for i in range(6,before['images'])]
        rows.append(dict(definitions=n,result=expect,receipt=P.bind(out/'receipt.json'),before=before,after=after,identical_64k_planes=same,images=image_rows))
    delta={k:rows[0]['after'][k]-rows[0]['before'][k] for k in states[0]}
    assert delta=={'images':1,'entries':21,'resolutions':87,'roots':18,'code_end':1038}
    limits=dict(images=64,entries=2048,resolutions=4096,roots=1536,code_end=60758)
    projected={k:states[2][k]+delta[k] for k in states[2]}
    headroom={k:limits[k]-projected[k] for k in projected};assert min(headroom.values())>0
    pred=ROOT/'build/set-b-load-predicates-r2/receipt.json';r=P.load(pred)
    assert r['status']=='PASS: EXECUTED RESOLVER PREDICATE ATTRIBUTION' and all(x['passed'] for x in r['steps'])
    assert r['result']['ready']==1 and r['result']['arm']==134 and r['result']['tenant_intact']
    c=(root/'definitions-2/before-load-c2d.bin').read_bytes();b=(root/'definitions-2/before-load-bank2.bin').read_bytes()
    entries=[A.entry(c,b,i) for i in [804,805]]
    assert entries[0]['image']==255 and entries[1]['image']==8 and entries[0]['bank2_offset']==50691 and entries[1]['bank2_offset']==50701
    price=ROOT/'build/set-b-load-repair-proposal-r5';lp=P.load(price/'lisp-price.json');np=P.load(price/'native-price.json')
    assert lp['code_delta']==214 and {x['section']:x['delta'] for x in np['changes']}=={'.lisp65_rt_c2append_retire_control':83,'.lisp65_rt_c2append_retire_reset':-3}
    P.write(OUT/'receipt.json',dict(status='PASS: MINIMAL REPRO AND FIRST REFUSING PREDICATE ATTRIBUTED',
        driver=P.bind(Path(__file__)),authority=S.require_auth(),seed=P.bind(S.PRODUCT/'wplto/resident-island-seed.prg.elf'),rows=rows,
        first_refusal=dict(owner='%require-persistent-row-size',condition='row code-base equals accumulated live image sizes',base_c2d_offset=304,physical_row=0x50130,field_offset=18,actual_hex='0dc6',expected_hex='03c6',actual_code_base=50701,expected_code_base=50691,gap=10,status='Lisp NIL',native_append_status='not reached by this resolver branch; no append status fabricated'),
        offending_entries=entries,executed_predicates=P.bind(pred),successful_library_delta=delta,
        hypothetical_same_library_after_minimal_reuse=dict(counters=projected,limits=limits,remaining=headroom,qualification='capacity arithmetic from actual fresh-load cost; repaired product load not executed'),
        prefix=dict(design='first native prompt after INIT',observed_latch=134,observed_protected=6,observed_images=8,repair='reset records trusted/pending 128; first normal quiescent control captures actual post-INIT count; recovery never captures'),
        proposal=P.bind(price/'receipt.json'),host_world=P.bind(ROOT/'build/set-b-load-world-checks-r2/receipt.json'),host_latch=P.bind(ROOT/'build/set-b-load-latch-checks-r1/receipt.json'),
        price=dict(lisp_code_delta=214,code_objects_added=2,native_resident_delta=0,native_bss_delta=0,linked_control_before=378,linked_control_projection=461,control_record_before=448,control_record_projection=480,reset_record_unchanged=352,tenant_extent_before=6752,tenant_extent_projection=6784,tenant_tail_before=1440,tenant_tail_projection=1408,text_air=816,text_floor=32,E000_air=115,E000_floor=54,capture_air=105,capture_floor=57,
                   limits='Matched objects only. No whole-product packing/LTO link; literal/root/resolution and delivery-price closure pending. Cold margin only 6.857 ms; full entry scan is not native-timed.'),
        product_builds=0,product_links=0,seeds=0,device_contacts=0))
    print('PASS minimal prefix, raw rejection, capacity projection and parked repair closure')

if __name__=='__main__':main()
