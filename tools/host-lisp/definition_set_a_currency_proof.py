"""Derive Seed currencies, images and gaps from the stopped native workload."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT/'build/definition-set-a-r2'
helper = ROOT/'build/storage-owner-preflight-r1/currency.py'
scope = dict(__file__=str(helper), __name__='currency_helpers')
exec(compile(helper.read_text().split('\ncurrent, elf = scan(')[0], str(helper), 'exec'), scope)
measured, elf = scope['scan']('build/definition-set-a-five-ide-r1')
manifest_path = ROOT/'config/storage-owner-manifest.json'
manifest = json.loads(manifest_path.read_text())
free = dict(symbols=manifest['symbol_slots']-measured['symbols_used'],
    names=manifest['name_owner']['bytes']-manifest['name_owner']['tail_guard']-measured['names_used'],
    code=measured['free'])
assert free['symbols'] >= 32 and free['names'] >= 384
predecessor_path = ROOT/'build/transient-retirement-r2/currency-proof.json'
predecessor = json.loads(predecessor_path.read_text())
assert predecessor['free']['code']-free['code'] == 160
cursor = 0
gaps = []
for row in sorted(measured['records'], key=lambda r: r['start']):
    assert row['start'] >= cursor, 'overlapping code objects'
    if row['start'] > cursor:
        gaps.append(dict(start=cursor, end=row['start'], bytes=row['start']-cursor))
    cursor = row['end']
assert cursor == measured['persistent_front']
receipt = json.loads((ROOT/'build/definition-set-a-five-ide-r1/receipt.json').read_text())
images = receipt['rows'][-1]['values']['images']
result = dict(status='PASS: EXECUTED SEED CURRENCY; FINAL TARGET NOT REBOUND',
    authority='c97a8e60', free=free, measured=measured, images=images,
    code_gaps=gaps, gap_bytes=sum(g['bytes'] for g in gaps),
    user_code_price=160, predecessor=scope['bind'](predecessor_path),
    inputs=[scope['bind'](helper), scope['bind'](manifest_path), scope['bind'](Path(__file__))],
    limits=['Identical established currency workload, not complete package-use qualification',
            'Manifest target is rebound only from the executed Final'])
(HERE/'currency-proof.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps({k: result[k] for k in ('status', 'free', 'images', 'gap_bytes', 'user_code_price')}, indent=2))
