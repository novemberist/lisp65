"""Dated ELF-scanner successor: classify one byte-bound, log-only TU producer.

The Step-1 producer saves size/symbol/disassembly text as diagnostics; no
acceptance predicate consumes those columns. The exact source is pinned,
so adding a parser (even in this file) requires a new reviewed successor.
All ten inherited migration mutations remain active. Historical tools and
contracts are unchanged. This does not authorize human-column ELF oracles.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import c2_elf_truth_migration_gate as P
ROOT=P.ROOT
HISTORY = {'tools/host-lisp/c2_elf_truth_migration_gate.py': '45377cbb105547753320a4865af073ff0d11d11678272ec52ac5e3a83ece0921', 'config/c2-elf-truth-contract.json': '3c51ea5b3b898f267138aec8b93f46be36bc14226eec962a5e14e0d0dc1f2624', 'tools/host-lisp/comfort_default_producer.py': '1e513724fa6e44b2c0e5edf3557bcf6f8ad97f178904633a5b716382531de261'}
RECEIPT=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/comfort-default-elf-truth-receipt-20260927.json'
base_scan=P.ungoverned_column_parsers

def history(rows):
    P.require(rows==HISTORY,'ELF diagnostic classification input drift')

def scan(contract):
    history({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in HISTORY})
    value=copy.deepcopy(contract)
    pin=value['ungoverned_column_parsers_2026_07_30']
    pin['files'].append('comfort_default_producer.py');pin['count']+=1
    result=base_scan(value)
    result['pinned']-=1;result['hand_parsers']-=1
    result['hash_bound_log_only_producers']=['comfort_default_producer.py']
    return result
P.ungoverned_column_parsers=scan

def derive():
    rows={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in HISTORY};history(rows)
    for p in rows:
        bad=dict(rows);bad[p]='0'*64
        try:history(bad)
        except P.MigrationError:pass
        else:raise AssertionError('historical/input mutation survived')
    P.selftest()
    return dict(date='2026-09-27',status='PASS',predecessors=rows,
        facts=P.collect(),history_mutations=len(rows),inherited_mutations=10,
        driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        claim='One immutable TU diagnostic writer classified; no acceptance column parser admitted')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','check','selftest']);a=parser.parse_args()
    value=derive()
    if a.action=='prepare':
        assert not RECEIPT.exists();RECEIPT.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    elif a.action=='check':assert json.loads(RECEIPT.read_text())==value,'ELF successor drift'
    print('Comfort default ELF migration: PASS inherited-mutations=10 history-mutations=3')
if __name__=='__main__':main()
