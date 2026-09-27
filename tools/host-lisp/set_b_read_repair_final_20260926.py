"""Set B read-repair Final, bound before qualification to sealed source r1.

No Final can start until the qualification closure, consumer successors,
clean tree and exact-HEAD green sealed source run all exist and verify.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
sys.dont_write_bytecode=True
import set_b_producer as P
import set_b_fourth_seed_20260926 as S
ROOT=P.ROOT
SOURCE=ROOT/'build/set-b-read-repair-check-source-r1/receipt.json'
QUALIFIED=ROOT/'build/set-b-r1/step4-r5/qualification-closure.json'
SEED=S.PRODUCT
OUT=ROOT/'build/set-b-read-repair-final-r1'
MEMBERS=('resident-island-seed.prg','resident-island-seed.prg.elf','resident-island-seed.prg.lto.o')


def head():return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()

def verify(row):
    assert P.bind(ROOT/row['path'])==row,row['path']
    return ROOT/row['path']


def preflight(pending=False):
    S.require_auth();missing=[]
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT):missing.append('clean tree')
    if not QUALIFIED.exists():missing.append(str(QUALIFIED.relative_to(ROOT)))
    else:
        q=P.load(QUALIFIED);assert q['status']=='PASS: ALL SET B EXECUTED AND CONSUMER GATES'
        assert q['seed']==P.bind(SEED/'wplto'/MEMBERS[1])
        assert q['bank2_plane_byteidentical_to_card_l'] is True
        assert q['failed']==q['tolerated']==0
        for row in q['inputs']+q['consumer_receipts']:verify(row)
        verify(q['medium']);verify(q['bank2_plane'])
    if not SOURCE.exists():missing.append(str(SOURCE.relative_to(ROOT)))
    else:
        s=P.load(SOURCE)
        assert s['exit_code']==0 and s['head_before']==s['head_after']==head()
        assert s['target']=='make -k check-source'
        assert s['changed_protected_files']==0 and not s['changed_files'] and not s['changed_sealed_artifacts']
        verify(s['log'])
    assert pending or not missing,missing
    return dict(status='PENDING' if missing else 'PASS',missing=missing,source=str(SOURCE.relative_to(ROOT)))


def final():
    preflight();assert not OUT.exists(),'No implicit Final retry'
    h=head();q=P.load(QUALIFIED);old,new=str(SEED.relative_to(ROOT)),str(OUT.relative_to(ROOT))
    original=P.load(SEED/'commands.json')
    assert len(original)==76 and sum('-c' not in c for c in original)==2
    commands=[[a.replace(old,new) for a in c] for c in original]
    assert all((ROOT/c[c.index('-o')+1]).resolve().is_relative_to(OUT) for c in commands)
    OUT.mkdir()
    P.write(OUT/'final-invocation.json',dict(head=h,source=P.bind(SOURCE),qualification=P.bind(QUALIFIED),
        seed_commands=P.bind(SEED/'commands.json'),commands=commands,finals=1,retry=False))
    shutil.copytree(SEED/'wplto',OUT/'wplto',ignore=shutil.ignore_patterns('*.o','*.elf','*.prg','*.map','*.json','*.txt'))
    for i,c in enumerate(commands):
        (ROOT/c[c.index('-o')+1]).parent.mkdir(parents=True,exist_ok=True)
        done=subprocess.run(c,cwd=ROOT,capture_output=True,env={**os.environ,'TMPDIR':str(P.HERE/'tmp'),'PYTHONDONTWRITEBYTECODE':'1'})
        (OUT/f'command-{i:03d}.log').write_bytes(done.stdout+done.stderr)
        assert done.returncode==0,('Final stopped; no retry',i)
    identities=[]
    for n in MEMBERS:
        a,b=SEED/'wplto'/n,OUT/'wplto'/n
        assert a.read_bytes()==b.read_bytes(),('Final identity drift',n)
        identities.append(dict(seed=P.bind(a),final=P.bind(b)))
    preflight();assert head()==h
    P.write(OUT/'final-identity.json',dict(status='PASS',head=h,source=P.bind(SOURCE),qualification=P.bind(QUALIFIED),
        identities=identities,ELF_byteidentical=True,medium=q['medium'],medium_adoption='identity; no repack',
        bank2_plane=q['bank2_plane'],Bank2_byteidentical=True,commands_consumed=len(commands),finals=1))
    print('PASS: Final identical to Seed; medium and Bank-2 plane adopted by identity')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['preflight','final']);ap.add_argument('--allow-pending',action='store_true');a=ap.parse_args()
    if a.mode=='preflight':print(preflight(a.allow_pending))
    else:
        assert not a.allow_pending
        final()
