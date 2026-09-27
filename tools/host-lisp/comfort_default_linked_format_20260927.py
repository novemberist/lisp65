"""Dated Link-88 closure successor: exact historical IDE bytes in an immutable path.

The Link-88 manifest points library-ide into today's generated dialect tree.
Only that path is relocated, retaining its byte count and SHA. Every other
artifact and decoder check is inherited. The historical receipt is immutable.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import c2_linked_format_decoder_closure as P
ROOT=P.ROOT
HISTORY = {'tools/host-lisp/c2_linked_format_decoder_closure.py': '7f0d90091afede8106e86a844898e280a4c528edbf4a5bbd528d719e511745ff', 'config/c2-linked-format-decoder-closure.json': '6aa61f9e6d26d75d6e86f5ed244d9ce47d7cfae2ce51ab95eb8dc3c3f691d25e', 'build/c2.3/v1.3.0-candidate-product-link88-r1/canonical-product-manifest.json': 'cec772177e00d1a413313c53407d66d06b3dbf740d556a0c4e4f92fbad1c5a73', 'build/c2.3/v1.3.0-candidate-product-link88-r1/receipts/linked-format-decoder-closure.json': 'd60c947184ef1590d935330d55a6312111e2b1318c839b5420d0ad4fde3a0936', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/comfort-default-consumers-20260927/ide.ext.bin': '6320b070885e2de285b30eda350e95a7beefc0819fdec5ff2fbc0034d32cacd2'}
ARTIFACT=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/comfort-default-consumers-20260927/ide.ext.bin'
RECEIPT=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/comfort-default-linked-format-receipt-20260927.json'
base_roles=P.artifact_roles

def history(rows):
    P.require(rows==HISTORY,'Link-88 historical input drift')

def relocate(manifest):
    value=copy.deepcopy(manifest)
    rows=[r for r in value['artifacts'] if r['role']=='library-ide']
    P.require(len(rows)==1,'IDE historical role population drift')
    r=rows[0]
    P.require(r==dict(role='library-ide',path='build/bytecode/dialect-v2/libs/ide.ext.bin',bytes=31886,
        sha256='6320b070885e2de285b30eda350e95a7beefc0819fdec5ff2fbc0034d32cacd2'),'IDE historical binding drift')
    r['path']=ARTIFACT.relative_to(ROOT).as_posix()
    return base_roles(value)
P.artifact_roles=relocate

def derive():
    rows={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in HISTORY};history(rows)
    for p in rows:
        bad=dict(rows);bad[p]='0'*64
        try:history(bad)
        except P.ClosureError:pass
        else:raise AssertionError('history mutation survived')
    contract=P.load(P.CONTRACT,'contract');P.validate_contract(contract);P.selftest(contract)
    manifest=P.load(ROOT/contract['candidate_manifest'],'manifest')
    for field,bad in [('path','foreign'),('sha256','0'*64),('bytes',31885)]:
        trial=copy.deepcopy(manifest)
        next(r for r in trial['artifacts'] if r['role']=='library-ide')[field]=bad
        try:relocate(trial)
        except P.ClosureError:pass
        else:raise AssertionError('relocation mutation survived')
    with tempfile.TemporaryDirectory(prefix='comfort-link88-') as tmp:
        value=P.check(contract,Path(tmp)/'receipt.json')
    previous=P.load(P.DEFAULT_RECEIPT,'predecessor')
    # Live strict-source markers are still checked by P.collect; only the
    # runtime source byte binding advances, not linked facts or other evidence.
    left=copy.deepcopy(previous);right=copy.deepcopy(value)
    for projection in (left,right):
        binding=projection['evidence']['decoder_sources']['runtime_overlay']
        binding.pop('bytes');binding.pop('sha256')
    P.require(left==right,'Link-88 semantic/evidence continuity drift')
    return dict(date='2026-09-27',status='PASS',predecessors=rows,closure=value,
        relocation=dict(original='build/bytecode/dialect-v2/libs/ide.ext.bin',archive=P.binding(ARTIFACT),bytes_identical=True),
        history_mutations=len(rows),relocation_mutations=3,driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','check','selftest']);a=parser.parse_args();value=derive()
    if a.action=='prepare':
        assert not RECEIPT.exists();RECEIPT.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    elif a.action=='check':assert json.loads(RECEIPT.read_text())==value,'Link-88 successor drift'
    print('Comfort default Link-88 closure: PASS exact historical IDE, inherited decoder checks')
if __name__=='__main__':main()
