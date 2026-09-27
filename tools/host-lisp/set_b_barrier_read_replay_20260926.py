"""Replay the unchanged C library after correcting a cancelling-XOR test oracle."""
import ctypes as C
from pathlib import Path

import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_barrier_read_20260926 as Q

ROOT=P.ROOT
OUT=Q.OUT/'host-replay-r2'


def main():
    S.require_auth()
    prior=Q.OUT/'host-r1'
    halt=P.load(prior/'halt.json')
    assert halt['kind']=='DMA-content' and halt['args']==[161,1,3,0,0,64,0,0,0]
    assert halt['actual']['accept']==1
    lib=P.load(prior/'receipt.json')['library']
    assert P.bind(ROOT/lib['path'])==lib
    OUT.mkdir(exist_ok=False)
    P.write(OUT/'oracle-correction.json',dict(prior_halt=P.bind(prior/'halt.json'),
        prior_driver=P.bind(Path(Q.__file__)),library=lib,
        cause='mutation1 XORs target byte0 with1; read style3 XORs destination byte0 with1 again. The delivered byte is original; accepting correct content is expected.',
        proof=[dict(byte=b,target=b^1,delivered=(b^1)^1) for b in range(256)],
        changed='Expected outcome only for this cancelling pair, all admitted modes; fixture, compiled library and product form unchanged.',
        limits='No comparator relaxation. This is harness attribution, not a product-gate waiver; all later rows stop at first genuine semantic/lifetime failure.',
        compile_calls=0,dependency_calls=0,links=0))
    library=C.CDLL(str(ROOT/lib['path']))
    library.fence_test.argtypes=[C.c_uint8]*4
    library.barrier_test.argtypes=[C.c_uint8]*3+[C.c_uint16]*3+[C.c_uint8]*3
    keys=['producer_status','accept','dma_reads','map_reads','ticks','pending_write_bytes','pending_read_bytes',
          'source_lifetime_errors','order_errors','escaped_destination','data_complete','committed','bounds_errors','has_target_address']
    rows=[]
    def record(row):
        rows.append(row);P.write(OUT/'rows.json',rows)
        if not row['pass_gate']:
            P.write(OUT/'halt.json',row);return False
        return True
    def run(kind,args,expected,check):
        library.barrier_test(*args)
        got=dict(zip(keys,list((C.c_uint16*14).in_dll(library,'barrier_result'))))
        count=C.c_uint16.in_dll(library,'event_count').value
        trace=[list(x) for x in ((C.c_uint16*4)*256).in_dll(library,'events')][:count]
        return record(dict(kind=kind,args=args,actual=got,expected=expected,trace=trace,
            pass_gate=check(got) and got['producer_status']==0 and got['bounds_errors']==0))
    stopped=False
    for mode in (0xa1,0xa2,0xa3,0xa4,0,0xa5):
        for mutation in (0,1,2):
            for fail in (0,1):
                for part in ((0,) if not fail else (0,1,2)):
                    library.fence_test(mode,mutation,fail,part)
                    got=list((C.c_uint16*9).in_dll(library,'fence_result'))
                    valid=0xa1<=mode<=0xa4
                    expected=int(valid and not fail and mutation!=1 and (mutation!=2 or mode in (0xa2,0xa4)))
                    if not record(dict(kind='original-MAP-content',mode=mode,mutation=mutation,read_failure=fail,partial=part,
                        actual=got,expected_accept=expected,pass_gate=got[0]==0 and got[1]==expected and got[2]==int(valid) and got[3:5]==[0,0])):
                        stopped=True;break
                if stopped:break
            if stopped:break
        if stopped:break
    if not stopped:
        for mode in (0xa1,0xa2,0xa3,0xa4,0,0xa5):
            for mutation in (0,1,2):
                for style in (0,1,2,3):
                    valid=0xa1<=mode<=0xa4
                    delivered_original=(style==0 and mutation!=1) or (style==3 and mutation==1)
                    expected=int(valid and delivered_original and (mutation!=2 or mode in (0xa2,0xa4)))
                    ok=run('DMA-content',[mode,mutation,style,0,0,64,0,0,0],dict(accept=expected,dma_reads=int(valid)),
                        lambda x:x['accept']==expected and x['dma_reads']==int(valid) and x['map_reads']==0
                        and x['escaped_destination']==0 and x['committed']==0)
                    if not ok:stopped=True;break
                if stopped:break
            if stopped:break
    if not stopped:
        for mode in (0xa1,0xa2,0xa3,0xa4):
            for delay,part in ((0,64),(3,8),(32,4)):
                if not run('ordered-data-and-read',[mode,0,0,delay,0,part,0,0,1],
                    'Accept only after both data jobs and complete read; live source and local destination.',
                    lambda x:x['accept']==1 and x['data_complete']==1 and x['dma_reads']==1 and x['map_reads']==0
                    and all(x[k]==0 for k in ('pending_write_bytes','pending_read_bytes','source_lifetime_errors','order_errors','escaped_destination','committed'))):
                    stopped=True;break
            if stopped:break
    if not stopped:
        stopped=not run('queued-real-journal-producer',[0xa1,0,0,3,0,8,0,0,2],
            'Actual producer source stays valid until ACTIVE delivery.',lambda x:x['accept']==1 and x['source_lifetime_errors']==0 and x['escaped_destination']==0 and x['pending_write_bytes']==0)
    if not stopped:
        stopped=not run('falling-MAP-control',[0xa3,0,0,0,0,8,1,0,1],
            'Old CPU reader accepts while32 data bytes stay pending; expected falling control.',
            lambda x:x['accept']==1 and x['pending_write_bytes']==32 and x['data_complete']==0 and x['dma_reads']==0 and x['map_reads']==1)
    if not stopped:
        stopped=not run('permanent-drop-known-limit',[0xa3,0,0,0,0,64,0,1,1],
            'Accepted matching journal cannot detect dropped unrelated data; demonstrated limit, NOT robustness qualification.',
            lambda x:x['accept']==1 and x['data_complete']==0 and x['pending_write_bytes']==0 and x['escaped_destination']==0)
    if not stopped:
        stopped=not run('last-attempt-delivery',[0xa3,0,0,0,64,64,0,0,1],
            'Complete read on attempt64 succeeds with no remaining destination obligation.',
            lambda x:x['accept']==1 and x['ticks']==64 and x['data_complete']==1 and x['escaped_destination']==0)
    if not stopped:
        stopped=not run('late-read-destination-lifetime',[0xa3,0,0,0,65,64,0,0,1],
            'Timeout must refuse without leaving any future DMA write into the expired local buffer.',
            lambda x:x['accept']==0 and x['committed']==0 and x['escaped_destination']==0 and x['pending_read_bytes']==0)
    P.write(OUT/'receipt.json',dict(status='HALT AT FIRST C OR LIFETIME GATE' if stopped else 'PASS BOUNDED HOST GATES; NATIVE PRICING NEXT',
        driver=P.bind(Path(__file__)),execution_head=Q.HEAD,prior=P.bind(prior/'receipt.json'),library=lib,
        correction=P.bind(OUT/'oracle-correction.json'),rows=P.bind(OUT/'rows.json'),
        halt=P.bind(OUT/'halt.json') if stopped else None,row_count=len(rows),passing_rows=sum(r['pass_gate'] for r in rows),
        extra_compile_calls=0,extra_dependency_calls=0,extra_links=0,native_objects=0,
        limits='Unchanged C library and contract model, corrected cancelling-XOR oracle. No hardware timing, after-return write, full publication or rollback execution.'))
    print('HALT' if stopped else 'PASS',len(rows),'rows;',sum(r['pass_gate'] for r in rows),'expected outcomes; zero extra compile/dependency/link')


if __name__=='__main__':main()
