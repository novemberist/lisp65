#!/usr/bin/env python3
"""Aggregate the 2.5.3 Seed r7 emulator evidence into receipt.json (read-only on the evidence dirs).

Usage: c253_rows_report.py <out-dir-under-build>   (the directory must exist; receipt.json is written once)
The row table (ROWMAP) lists, for every row id of c253_rows_20261001.json, the executed row ids, the evidence
directories they come from, and the reviewer diagnosis of any deviation.  Statuses are copied from the raw
row files; nothing is re-judged here except the explicit DIAGNOSIS table.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
MEDIUM_SHA = 'abc9bb49db28a855f4f5d157eb8c03f58db2bb7a6789eab5025365efcc040b57'
ELF_SHA = '47519653518fcffdb98eec5c069f23ed1db544221b4ed95eea33b27fea5ab57b'


def load(path):
    p = ROOT / path
    return json.loads(p.read_text()) if p.exists() else None


def rows_of(path):
    r = load(path)
    return {x['id']: x for x in (r or [])}


def main():
    out = ROOT / 'build' / sys.argv[1]
    spec = {r['id']: r for r in json.loads((ROOT / 'tools/host-lisp/c253_rows_20261001.json').read_text())['rows']}
    sources, superseded = {}, []
    # later files win; superseded rows are listed (harness failures retained as evidence)
    for path in ('build/card-253-rows-r7/new/repl/repl-rows.json',
                 'build/card-253-rows-r7-c/new/disk/disk-rows.json',
                 'build/card-253-rows-r7-d/new/disk/disk-rows.json',
                 'build/card-253-rows-r7-e/new/ide/ide-rows.json',
                 'build/card-253-rows-r7-f/new/ide/ide-rows.json'):
        for rid, row in rows_of(path).items():
            if rid in sources and sources[rid].get('status') != row.get('status'):
                superseded.append(dict(row=rid, status=sources[rid].get('status'), source=sources[rid]['_src'], superseded_by=path))
            sources[rid] = dict(row, _src=path)
    diag = json.loads((out / 'diagnosis.json').read_text()) if (out / 'diagnosis.json').exists() else {}
    rowmap = diag.get('rowmap', {})
    table = []
    for rid in spec:
        execs = rowmap.get(rid, [rid])
        entries = []
        for eid in execs:
            s = sources.get(eid)
            entries.append(dict(executed_row=eid, status=(s or {}).get('status', 'NOT RUN'),
                                source=(s or {}).get('_src'), group=(s or {}).get('group'),
                                screens=(s or {}).get('screens', [])))
        table.append(dict(row=rid, executed=entries, status=diag.get('status', {}).get(rid, 'UNSET'),
                          diagnosis=diag.get('diagnosis', {}).get(rid)))
    extra = {eid: dict(status=s.get('status'), source=s['_src'], group=s.get('group'), screens=s.get('screens', []))
             for eid, s in sources.items() if not any(eid in v for v in rowmap.values()) and eid not in spec}
    receipt = dict(
        status='see rows', card='2.5.3 Seed r7 emulator rows',
        medium=dict(path='build/card-253-product-r7/media-253/c253.d81', sha256=MEDIUM_SHA),
        ELF=dict(path='build/card-253-product-r7/wplto/resident-island-seed.prg.elf', sha256=ELF_SHA),
        rows=table, auxiliary_rows=extra, superseded_runs=superseded,
        host_checks=diag.get('host_checks'),
        regression=diag.get('regression'), typing_cost=diag.get('typing_cost'), gc_stress=diag.get('gc_stress'),
        boot=diag.get('boot'), tool_changes=diag.get('tool_changes'),
        claim='Emulator observation (Xemu, keyboard queue / framebuffer / memory reads, host readback of D81); no device, no Final')
    target = out / 'receipt.json'
    assert not target.exists(), 'receipt.json is write-once'
    target.write_text(json.dumps(receipt, indent=1) + '\n')
    print(json.dumps({r['row']: r['status'] for r in table}, indent=1))


if __name__ == '__main__':
    main()
