"""Read-only closure of the fifth Seed's executed prefix and workload halt."""
from collections import Counter
from pathlib import Path
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import retained_callable_writer_analysis as A
import set_b_fifth_oracle_r4_20260926 as O
ROOT=P.ROOT
OUT=S.OUT/'workload-halt-analysis-r1'

def main():
    OUT.mkdir(exist_ok=False)
    d=ROOT/'build/set-b-fifth-functional-reuse-r3'
    r=P.load(d/'receipt.json');h=P.load(d/'qualification-halt.json')
    assert r['status']=='HALT' and h['actual']=='NIL' and h['ready']==1 and h['arm']==134 and h['tenant_intact']
    steps=P.load(d/'steps.json');assert len(steps)==53 and all(x['passed'] for x in steps)
    inputs=[P.bind(d/x) for x in ['receipt.json','qualification-halt.json','steps.json','captures.json']]
    def raw(label,region):
        p=d/f'{label}-{region}.bin';inputs.append(P.bind(p));return p.read_bytes()
    initial,ib=raw('initial','c2d'),raw('initial','bank2')
    prior,pb=raw('call-50','c2d'),raw('call-50','bank2')
    halt,hb=raw('halt','c2d'),raw('halt','bank2')
    before=(d/'step-require-before-screen.txt').read_text();after=(d/'halt-screen.txt').read_text()
    assert O.valid(before,after,'(require "defstruct")','NIL') and not O.valid(before,after,'(require "defstruct")','T')
    assert prior==halt and pb==hb,'unexpected state change on refused require'
    foreign=[i for i in range(A.counts(initial)['entries']) if A.entry(initial,ib,i)!=A.entry(prior,pb,i)]
    assert not foreign
    rows=[]
    for n in range(51):
        c=raw(f'define-{n}','c2d');b=raw(f'define-{n}','bank2');counts=A.counts(c)
        assert counts==dict(images=9,entries=805+n,resolutions=3142,roots=376)
        assert c[0xde80:0xfe80]==(S.PRODUCT/'set-b-tenants.bin').read_bytes()
        entries=[A.entry(c,b,i) for i in range(804,805+n)]
        assert len(entries)==n+1 and all(e['image']&128 for e in entries[:-1]) and entries[-1]['image']==8
        assert c[0xde20]==0
        rows.append(dict(iteration=n,counts=counts,retired_entries=n,latest_entry=entries[-1],journal_magic=0))
    lambda_dir=ROOT/'build/set-b-fifth-functional-lambda-r2';lam=P.load(lambda_dir/'receipt.json')
    assert lam['status'].startswith('PASS') and [x['expected'] for x in lam['steps']]==['*** VM: BAD BYTECODE','NIL','42']
    assert all(x['passed'] for x in lam['steps'])
    # Abort may intern SAVEDLAMBDA but must not publish directory/code objects.
    lc=(lambda_dir/'initial-c2d.bin').read_bytes();la=(lambda_dir/'lambda-c2d.bin').read_bytes()
    offs=[('header',0,48),('images',48,A.counts(lc)['images']*32),('entries',A.u(lc,30,2),A.counts(lc)['entries']*10),('resolutions',A.u(lc,32,2),A.counts(lc)['resolutions']*2),('roots',A.u(lc,34,2),A.counts(lc)['roots']*2)]
    lp={name:lc[at:at+n]==la[at:at+n] for name,at,n in offs};assert all(lp.values())
    captures=P.load(d/'captures.json');assert len(captures)==54 and all(x['arm']==134 and x['tenant_intact'] for x in captures)
    P.write(OUT/'receipt.json',dict(status='QUALIFICATION HALT; successful prefix closed without another guest',
        source_authority=S.require_auth(),execution_head='1f9fda66',seed=P.bind(S.PRODUCT/'wplto/resident-island-seed.prg.elf'),
        completed_prefix=dict(forms=53,redefinitions=50,first_value=7,last_value=57,images='8 -> 9; all 50 replacements remain 9',entries='804 -> 855',retired_entries=50,unchanged_preexisting_entries=804,foreign_differences=foreign,rows=rows),
        halt=dict(expected='T',actual='NIL',form='(require "defstruct")',c2d_64k_unchanged=True,bank2_64k_unchanged=True,ready=1,arm=134,tenant_intact=True,journal_magic=0,internal_stage='UNATTRIBUTED',capacity_cause='UNATTRIBUTED',subsequent_forms=0),
        lambda_gate=dict(receipt=P.bind(lambda_dir/'receipt.json'),status='PASS',exact_error='*** VM: BAD BYTECODE',symbol='NIL',arithmetic='42',arm_after_abort=0,planes_identical=lp),
        limits='Boundary snapshots do not prove absence of transient/same-value writes. Ordinary unchanged 64KiB C2D and Bank2 refusal is observed; not a diagnosis of cause, no complete carrier/fault/performance closure.',
        driver=P.bind(Path(__file__)),inputs=inputs,product_links=0,guest_launches=0,device_contacts=0))
    print('PASS offline prefix/unchanged refusal; HALT remains, cause unassigned')
if __name__=='__main__':main()
