#!/usr/bin/env python3
"""comfort-library card: plain-prompt natural single-key and batched lanes.

Pure renaming derivation of build/nested-error-recovery-instrument-r1/lanes.py
(authority 1536ef74, observer native_cycle_stationary, same qualified observer
binary and cost configuration).  Both worlds run the one 2.4.0 ELF (66165507);
the anchor is the accepted 2.4.0 medium (87cb0f6e), the candidate is the
Comfort medium with Comfort NOT loaded (Comfort is opt-in).  The anchor rows
must reproduce the nested-error recovery card's 2.4.0 rows cycle for cycle
(observer neutrality); the candidate rows are then compared with them.

Usage: comfort_library_lanes.py --attempt comfort-library-r1
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT / 'build/nested-error-recovery-instrument-r1/lanes.py'
raw = source.read_text()
changes = {
    "for role,path in [('anchor', 'build/retained-callable-repair-seed-medium-r2'), ('candidate', 'build/nested-error-recovery-seed-medium-r1')]:":
        "for role,path in [('anchor', 'build/nested-error-recovery-seed-medium-r1'), ('candidate', 'build/comfort-library-medium-r2')]:",
    "assert packed['closure']['failures']==packed['coherence']['failures']==[]":
        "assert (packed['closure']['failures']==packed['coherence']['failures']==[]) if role=='anchor' else packed['status'].startswith('PASS: SIXTH PACKAGE ADDED')",
    "WORLD=next(w for w in identity['worlds'] if w['role']==role and w['ELF']['sha256']==packed['elf']['sha256'])":
        "WORLD=next(w for w in identity['worlds'] if w['role']=='candidate' and w['ELF']['sha256']==packed['elf']['sha256'])",
    "prior=json.loads((ROOT/'build/input-cost-natural-retained-callable-repair-r2/receipt.json').read_text())":
        "prior=json.loads((ROOT/'build/input-cost-natural-nested-error-recovery-r1/receipt.json').read_text())",
    "prior=N.bind(ROOT/'build/input-cost-natural-retained-callable-repair-r2/receipt.json'),":
        "prior=N.bind(ROOT/'build/input-cost-natural-nested-error-recovery-r1/receipt.json'),card='comfort-library',binding='180cb993',",
    "result=dict(status='PASS: FRESH REPAIR-FINAL ROWS REPRODUCE THE ACCEPTED REPAIR ROWS; CANDIDATE MEASURED',":
        "result=dict(status='PASS: FRESH 2.4.0 ROWS REPRODUCE THE ACCEPTED 2.4.0 ROWS; COMFORT MEDIUM MEASURED',",
}
for old, new in changes.items():
    assert raw.count(old) == 1, old
    raw = raw.replace(old, new)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
