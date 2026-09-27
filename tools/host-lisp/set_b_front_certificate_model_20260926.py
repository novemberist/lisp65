"""Executable design model, not candidate runtime code or a product test."""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import random
import set_b_producer as P
import set_b_fifth_seed_20260926 as S

ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-certificate-model-r1'
LIMIT=60758

def oracle(entries,generation):
    ends=[]
    for owner,start,length,gen in entries:
        if not length or start+length>LIMIT or gen!=generation:
            return None
        ends.append(start+length)
    return max(ends,default=0)

@dataclass
class Certificate:
    # Spec storage: front16 + state8. Generation/count are the live native
    # context, checked against an actual query header, not copied cache keys.
    front:int=0
    valid:bool=False
    busy:bool=False
    generation:int=1
    count:int=0
    refills:int=0

    def invalidate(self):
        self.valid=False

    def query(self,entries,generation,header_count=None,read_failure=False):
        count=len(entries) if header_count is None else header_count
        if self.busy or generation!=self.generation or count!=self.count:
            return None
        if self.valid:
            return self.front
        self.refills+=1
        if read_failure:
            return None
        value=oracle(entries,generation)
        if value is None:
            return None
        self.front=value;self.valid=True
        return value

def main():
    S.require_auth();OUT.mkdir(exist_ok=False)
    source=ROOT/'build/set-b-load-attribution-r1/definitions-0/before-load-c2d.bin'
    raw=source.read_bytes();u=lambda at:int.from_bytes(raw[at:at+2],'little')
    generation=u(10);assert u(16)==804
    entries=[(raw[p],u(p+2),u(p+4),u(p+8)) for p in range(2096,2096+804*10,10)]
    rows=[]
    def row(case,**fields):rows.append(dict(case=case,**fields))
    def warm(es):
        cert=Certificate(generation=generation,count=len(es))
        assert cert.query(es,generation)==oracle(es,generation)
        return cert
    basefront=oracle(entries,generation);assert basefront==50691
    # Same generation/count can denote a different successfully published suffix.
    first=entries+[(8,basefront,10,generation)]
    second=entries+[(8,basefront,20,generation)]
    assert (generation,len(first))==(generation,len(second))
    assert oracle(first,generation)!=oracle(second,generation)
    row('generation-count-ABA-falling-control',key=[generation,len(first)],
        first_front=oracle(first,generation),second_front=oracle(second,generation),
        rejects_key_only_design=True,scope='Synthetic two append/rollback histories on captured prefix; not executed product forms')
    # Source audit binds the actual recovery assignment. Current entry_cursor
    # has no front meaning; this is a counterexample to the proposed alias only.
    current_cursor=oracle(first,generation)
    reconstructed_count=len(entries)
    assert current_cursor!=basefront
    row('nonlocal-recovery-cursor-alias-falling-control',restored_count=reconstructed_count,
        copied_current_cursor=current_cursor,true_predecessor_front=basefront,
        rejects_implicit_old_front_restore=True,product_defect_claim=False)

    malformed=[]
    for label,slot,value in [('generation',0,(entries[0][0],entries[0][1],entries[0][2],2)),
            ('zero-length',400,(entries[400][0],entries[400][1],0,generation)),
            ('range',803,(entries[803][0],60758,1,generation))]:
        bad=entries.copy();bad[slot]=value;assert oracle(bad,generation) is None
        malformed.append((label,bad))
        cert=warm(entries);stale=cert.query(bad,generation)
        assert stale==basefront
        row(label+'-missing-writer-hook-falling-control',cached=stale,full_scan=None,
            raw_write_closure_required=True)
        cert.invalidate();assert cert.query(bad,generation) is None and not cert.valid
        row(label+'-covered-write-refusal',result=None,valid_after=False)
    cert=warm(entries);cert.invalidate()
    assert cert.query(entries,generation,read_failure=True) is None and not cert.valid
    row('refill-read-failure',result=None,valid_after=False)
    assert cert.query(entries,generation)==basefront
    row('refill-after-recovery',result=cert.front,valid_after=True)
    cert=warm(entries)
    assert cert.query(entries,generation+1) is None
    assert cert.query(entries,generation,header_count=805) is None
    row('header-context-mismatch',generation_refused=True,count_refused=True)
    # Warm cache has no row read. An injected fault at an eliminated read
    # cannot be represented as the old all-row reader's failure cutpoint.
    assert cert.query(entries,generation,read_failure=True)==basefront
    row('warm-eliminated-read-fault-non-equivalence',cached=basefront,
        cold_refill_would_refuse=True,old_read_cutpoint_cannot_be_claimed=True)

    # All intermediate failure stations leave INVALID. A restored stable
    # prefix requires an actual refill; no stale pending front is published.
    stages=['begin','stage','decode','header','exports','journal-clear','transaction-end','scratch-release']
    for phase in stages:
        cert=warm(entries);cert.invalidate();cert.busy=True
        assert cert.query(entries,generation) is None
        pending=oracle(first,generation)
        cert.busy=False;cert.count=len(entries)
        assert not cert.valid and pending!=basefront
        assert cert.query(entries,generation)==basefront
        row('failure-'+phase,intermediate_query=None,refill=cert.front,refills=cert.refills)
    cert=warm(entries)
    retired=[(255,start,length,gen) for _,start,length,gen in entries]
    assert oracle(retired,generation)==cert.front
    row('retirement-owner-only-invariant',old_front=cert.front,new_front=oracle(retired,generation))
    cert.invalidate();assert cert.query(retired,generation)==basefront
    row('retirement-conservative-refill',result=cert.front)
    # Transient upper rows are outside the charged persistent prefix.
    cert=warm(entries)
    high=[(63,LIMIT-20,20,generation)]
    assert oracle(entries+high,generation)!=cert.front
    assert cert.query(entries,generation)==basefront
    row('transient-high-rows-excluded',persistent_front=basefront,high_transient_front=LIMIT)
    cert.invalidate();cert.generation=2;cert.count=0
    assert cert.query([],2)==0
    row('reset-no-generation-reuse',result=0,generation=2)

    rng=random.Random(59309)
    for test in range(300):
        n=rng.randrange(0,65)
        es=[(255,rng.randrange(0,60000),rng.randrange(1,64),generation) for _ in range(n)]
        cert=warm(es);old=es.copy();front=cert.front
        suffix=[(8,rng.randrange(0,60000),rng.randrange(1,64),generation) for _ in range(rng.randrange(1,8))]
        cert.invalidate();cert.busy=True
        # Derive from certified unchanged prefix + independently validated new
        # suffix, not by querying the full oracle. Compare full oracle after.
        pending=max(front,oracle(suffix,generation))
        new=old+suffix
        assert pending==oracle(new,generation)
        cert.count=len(new);cert.front=pending;cert.busy=False;cert.valid=True
        assert cert.query(new,generation)==oracle(new,generation)
        row('incremental-suffix-'+str(test),prefix=n,suffix=len(suffix),front=pending)

    # Exact cold population trace. Boot/decode row validations already exist;
    # only an accumulator would be added to those visits. This is not a cycle proof.
    cert=Certificate(generation=generation,count=785)
    cert.front=oracle(entries[:785],generation);cert.valid=True
    queries=[];visits=785
    for before,after in [(785,801),(801,804)]:
        assert cert.count==before
        queries.append(dict(entries=before,front=cert.query(entries[:before],generation),entry_scan_rows=0,header_bytes=8))
        cert.invalidate();cert.busy=True
        suffix=entries[before:after];pending=max(cert.front,oracle(suffix,generation));visits+=len(suffix)
        assert pending==oracle(entries[:after],generation)
        cert.count=after;cert.front=pending;cert.busy=False;cert.valid=True
        queries.append(dict(entries=after,front=cert.query(entries[:after],generation),entry_scan_rows=0,header_bytes=8))
    assert [r['entries'] for r in queries]==[785,801,801,804]
    assert visits==804 and cert.refills==0
    P.write(OUT/'rows.json',rows);P.write(OUT/'cold-model.json',queries)
    budget=277701;copy_floor=4*(11*8-3)
    P.write(OUT/'receipt.json',dict(status='DESIGN MODEL CLOSED; WRITER/COLD/FAULT CONTRACT NOT ADMITTED',
        driver=P.bind(Path(__file__)),source=P.bind(source),audit=P.bind(ROOT/'build/set-b-front-certificate-audit-r2/receipt.json'),
        rows=P.bind(OUT/'rows.json'),row_count=len(rows),cold_model=P.bind(OUT/'cold-model.json'),
        storage_options=[dict(form='generation16/count16/front16/valid8',new_bytes=7,high_BSS_air=3,floor=5,fits=False),
            dict(form='front16/valid8 plus context entry_cursor pending alias',new_bytes=3,high_BSS_air=7,floor=5,fits=True,
                 condition='Pending alias not an undo record. Recovery invalidates; refill must establish a new proof.'),
            dict(form='front16/pending16/valid8',new_bytes=5,high_BSS_air=5,floor=5,fits=True,condition='No spare BSS margin; nested pending ownership still required')],
        cold=dict(old_extra_full_scan_rows=3191,proposed_extra_full_scan_rows=0,existing_decoder_visits=visits,
            proposed_header_reads=4,proposed_header_bytes=32,header_copy_floor=copy_floor,
            margin_cycles=budget,remaining_after_copy_floor=budget-copy_floor,
            ceiling_average_cycles_per_existing_row_if_all_other_costs_zero=(budget-copy_floor)/visits,
            warning='Zero extra rows is a conditional model trace. All accumulator, query, invalidation, VM, GC and native owner costs remain unpriced; this is not a cold pass.'),
        completion='Deliver conditional certificate design and exact counterexamples. No implementation or additional product budget request.',
        obligations=['Classify and mediate raw poke/I/O or explicitly bind a narrower supported writer domain; never silently exempt it.',
            'Bind warm fault behavior: old cutpoints at eliminated row reads cannot be asserted to execute.',
            'Recovery invalidates; fallback full scan must be callable without unsafe scratch/overlay lifetime and must fit owner air.',
            'Price accumulator/fast leaf/write barriers against784 resident bytes, E000115/54, capture105/57 and each changed decoder slice.',
            'Keep READY, exact BAD BYTECODE successor, all CRC identities, prefix correction and native reservation validation unchanged.'],
        this_commission=dict(product_builds=0,product_links=0,seeds=0,finals=0,device_contacts=0,guest_launches=0,
            native_object_compiles=0,dependency_calls=0,host_c_compiles=0,host_c_links=0,model_executions=1),
        limitations='Python specification model using captured directory values. No candidate C, no device/emulator, no writer interception executed. Falling controls reject naive designs; they do not register new product defects.'))
    print('CLOSED',len(rows),'model rows; conditional cold trace 3191 -> 0 added scan rows; writer/fault contract remains open')


if __name__=='__main__':main()
