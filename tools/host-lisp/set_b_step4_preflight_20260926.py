"""Fresh Set B admission/object probes; no Seed or product linker invocation."""
import inspect
import json
import os
from pathlib import Path
import sys
import traceback
sys.dont_write_bytecode=True
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import set_b_producer as P
import boot_name_index_link_preprobe as L
import slice_capacity_preflight_20260924 as CAP
ROOT=P.ROOT
OUT=ROOT/'build/set-b-r1/step4-r2'

def write(name,data):P.write(OUT/name,data)

def main():
    OUT.mkdir(exist_ok=False)
    write('start.json',dict(authority=P.require_auth(),producer=P.bind(Path(P.__file__)),
        driver=P.bind(Path(__file__)),seed_invocations=0,product_links=0))
    source=inspect.getsource(P.command_probe)
    old="out=HERE/'step3/command-preview'"
    new="out=ROOT/'build/set-b-r1/step4-r2/command-preview'"
    assert source.count(old)==1
    source=source.replace(old,new,1)
    (OUT/'command-probe-function.py').write_text(source)
    ns=dict(vars(P));exec(compile(source,str(OUT/'command-probe-function.py'),'exec'),ns)
    preview=ns['command_probe']()
    write('authority-admission.json',dict(status='PASS',authority=P.require_auth(),
        files=[P.bind(ROOT/f) for f in P.authority_files()],transformation=dict(before=old,after=new)))
    commands=P.load(preview/'commands.json')
    normalized=[]
    for cmd in commands:
        cmd=list(cmd)
        if '-c' in cmd:
            # Era preprobe reads flags only BEFORE -c. Clang's trailing -D
            # is equivalent; retain the original transcript and bind this move.
            assert cmd[-1]=='-DLISP65_SET_B'
            define=cmd.pop();cmd.insert(cmd.index('-c'),define)
        normalized.append(cmd)
    proof=preview/'wplto/command-proof.json';P.write(proof,dict(commands=normalized))
    write('probe-transcript.json',dict(original=P.bind(preview/'commands.json'),normalized=P.bind(proof),
        transformation='move the unchanged trailing -DLISP65_SET_B before -c for era preprobe flag parser; no flag added or removed'))
    print('PASS authority and command admission',flush=True)
    base=OUT/'baseline-proof';base.mkdir()
    P.write(base/'command-proof.json',P.load(P.BASE/'final-command-consumption.json'))
    # Baseline scripts stay with the exact accepted world's generated inputs.
    baseline=base/'command-proof.json'
    import shutil
    shutil.copyfile(P.BASE/'wplto/c2-substitution.ld',base/'c2-substitution.ld')
    shutil.copytree(P.BASE/'wplto/full-map-linker',base/'full-map-linker')
    link=L.run_preprobe(proof,OUT/'link-preprobe',baseline)
    print('Link preprobe',link['status'],link['new_findings'],flush=True)
    assert link['status']=='PASS',link['new_findings']
    objects=[ROOT/p for p in link['objects']]
    baseobjects=sorted((OUT/'link-preprobe/baseline/objects').glob('*.o'))
    edge=L.e000_low_edges_receipt(objects,baseobjects)
    write('e000-preprobe/e000-low-edges-receipt.json',edge)
    print('E000 preprobe',edge['status'],edge['new_findings_keys'],flush=True)
    assert edge['status']=='PASS',edge['new_findings_keys']
    CAP.check_predecessor()
    medium=ROOT/'build/card-l-seed-medium-r2/materialized'
    rc=CAP.main(['--medium',str(medium),'--out',str(OUT/'capacity')])
    assert rc==0
    inputs=P.load(P.INPUTS);projection=P.load(P.PROJECTION_RECEIPT)
    rows=[]
    for i,t in enumerate(inputs['tenants']):
        limit=inputs['tenants'][i+1]['offset'] if i+1<len(inputs['tenants']) else inputs['aligned_extent']
        n=next(r['bytes'] for r in projection['slices'] if r['slot']==t['slot'])
        rows.append(dict(slot=t['slot'],offset=t['offset'],interval=limit-t['offset'],projected_bytes=n,
            projected_fit=t['offset']+n<=limit,linked_gate='P.extract_tenants enforces exact no-overlap after one Seed'))
    assert CAP.directory_step(56,7)==0 and inputs['session_count']==63
    write('late-capacity.json',dict(status='ADMITTED TO LINK; EXACT TENANT PLACEMENT PENDING',
        directory_growth_bytes=0,session_count=63,session_slots_free=1,late_capacity=8192,
        reserved_extent=inputs['aligned_extent'],journal_bytes=72,gap_bytes=96,tenants=rows,
        note='Dated predecessor supports regions 0/1/2 only; region 3 accounted explicitly. Original slot policy is not reinterpreted as a family catalog limit.'))
    write('preflight-result.json',dict(status='PASS',placement_pending=True,seed_invocations=0,product_links=0))
    print('PASS preflight; exact linked tenant interval gate pending',flush=True)

if __name__=='__main__':
    try:main()
    except Exception as e:
        if OUT.exists():write('failure.json',dict(status='HALT',error=str(e),traceback=traceback.format_exc(),seed_invocations=0,product_links=0))
        raise
