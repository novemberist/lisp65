"""Dated post-v1.2 housekeeping successor: route only the ELF scanner successor.
The sealed housekeeping witness and all living checks remain unchanged.
Living counts are derived, never persisted as a frozen repository population.
"""
import argparse
import hashlib
import json
from pathlib import Path
import post_12_housekeeping as P
ROOT=P.ROOT
HISTORY={'tools/host-lisp/post_12_housekeeping.py': '049aac562efa3a8aff4852a97fa88e41eb051d359a4dd1284ad71eb5f36b20ca', 'tests/bytecode/dialect-v2/evidence/post-release/post-v1.2-housekeeping-receipt.json': 'e3cf12bb46a3b47fbfaad8836cc54df87612b92b226e4f2d77954e67dc899247', 'tools/host-lisp/comfort_default_elf_truth_20260927.py': 'aec7f3ecd1d5892c5a9c28e00c9a4db5d48937e5cd22fad7c19560a000fb4c4c'}
RECEIPT=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/comfort-default-housekeeping-receipt-20260927.json'
OLD=['python3','tools/host-lisp/c2_elf_truth_migration_gate.py']
NEW=['python3','-B','tools/host-lisp/comfort_default_elf_truth_20260927.py','check']
base_run=P.run_gate

def route(command):return NEW if command==OLD else command

def run_gate(command,label):return base_run(route(command),label)
P.run_gate=run_gate

def history(rows):P.require(rows==HISTORY,'housekeeping predecessor drift')

def derive():
    rows={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in HISTORY};history(rows)
    for path in rows:
        bad=dict(rows);bad[path]='0'*64
        try:history(bad)
        except P.HousekeepingError:pass
        else:raise AssertionError('history mutation survived')
    assert route(OLD)==NEW
    assert route(OLD+['--selftest'])==OLD+['--selftest']
    P.selftest();P.check()
    return dict(date='2026-09-27',status='PASS',predecessors=rows,
        redirected_subcheck=dict(old=OLD,new=NEW),history_mutations=len(rows),
        inherited_witness_mutations=3,living_counts='derived, not persisted',
        driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','check','selftest']);a=p.parse_args();value=derive()
    if a.action=='prepare':
        assert not RECEIPT.exists();RECEIPT.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    elif a.action=='check':assert json.loads(RECEIPT.read_text())==value,'housekeeping successor drift'
    print('Comfort default housekeeping: PASS inherited witness and living checks, routed ELF successor')
if __name__=='__main__':main()
