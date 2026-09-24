"""Close the executed Seed 2 (member 2 alone): every pre-Final gate from its receipt.

Writes config/retained-callable-repair-seed.json, the qualification the Final
driver verifies input by input (write-once).  No emulator, compiler or link.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'config/retained-callable-repair-seed.json'
SEED_SHA = '815b60a5fb4baf405d5b8e14dac5ad9e593c9bf3f73877efc6b6f63499dc26a1'


def bind(path):
    raw = Path(path).read_bytes()
    return dict(path=str(Path(path).resolve().relative_to(ROOT)), bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())


def main():
    inputs = []

    def load(name):
        p = ROOT/name
        inputs.append(bind(p))
        return json.loads(p.read_text())
    gates = {}
    seed = ROOT/'build/retained-callable-repair-product-r2/wplto/resident-island-seed.prg.elf'
    assert bind(seed)['sha256'] == SEED_SHA
    inputs.append(bind(seed))
    admission = load('build/retained-callable-repair-r2/preflight-admission.json')
    assert admission['status'] == 'PASS' and admission['authority'] == 'dafc1f47'
    inv = load('build/retained-callable-repair-r2-seed-inventory-r2/inventory.json')
    assert inv['status'] == 'PASS: ALL DIFFERENCES INSIDE MEMBER 2 OR DERIVED'
    assert not inv['unclassified_section_bytes'] and inv['ELFs'][1]['sha256'] == SEED_SHA
    gates['6 inventory'] = inv['status']
    price = load('build/retained-callable-repair-product-r2/wplto/retained-callable-repair-r2-seed-price.json')
    assert price['owner_floors_unchanged'] and set(price['members']) == {'.lisp65_rt_c2append_journal_prepare'}
    gates['6 price'] = price['status']
    capacity = load('build/retained-callable-repair-r2-capacity-seed-r1/slice-capacity-preflight.json')
    session = capacity['families']['session']
    assert session['region0']['free'] == 1351 and capacity['unique_catalog_slots_free'] == 1
    packed = load('build/retained-callable-repair-seed-medium-r2/packed-receipt.json')
    assert packed['closure']['failures'] == packed['coherence']['failures'] == []
    assert packed['elf']['sha256'] == SEED_SHA
    boot = load('build/retained-callable-repair-r2-native-boot-r1/qualification.json')
    assert boot['status'].startswith('PASS') and boot['carrier_writes'] == 0 and boot['prompt_identical']
    gates['7 boot'] = boot['status']
    latency = load('build/retained-callable-repair-r2/latency-qualification.json')
    assert latency['status'].startswith('PASS')
    gates['7 lanes'] = {k: v['ratio'] for k, v in latency['lanes'].items()}
    gc = load('build/retained-callable-repair-r2/gc-qualification.json')
    assert gc['status'].startswith('PASS') and gc['forced_delta'] == 0 and gc['warmup']['delta'] == 0
    gates['7 GC'] = dict(forced=gc['cycles'], warmup=gc['warmup'])
    for role in ('baseline', 'candidate'):
        u = load(f'build/retained-callable-repair-r2-usage-{role}-r1/receipt.json')
        assert u['status'] == 'PASS' and u['error'] is None and len(u['rows']) == 23
        assert u['rows'][18]['expected'] == '*** VM: BAD BYTECODE'
        for r in u['rows']:
            assert bind(ROOT/r['screen']['path'])['sha256'] == r['screen']['sha256']
        gates['5 usage '+role] = 'PASS: 23 rows, row 18 exact BAD BYTECODE'
    analysis = load('build/retained-callable-repair-r2/gate-analysis.json')
    assert analysis['status'] == 'PASS: GATES 1-4 (SEED 2)'
    for k in ('1', '2', '3', '4'):
        assert analysis['gates'][k]['status'] == 'PASS'
        gates[k] = 'PASS'
    inputs.append(bind(Path(__file__)))
    value = dict(status='PASS: EXECUTED RETAINED-CALLABLE REPAIR SEED', authority='dafc1f47',
                 binding='d3d5044b', rebinding='reviewer decision 2026-09-23 (member 1 withdrawn, 2/1/1)',
                 seed=dict(ELF=bind(seed), medium=packed['medium']), gates=gates,
                 budget=dict(seed=2, final=0, product_link=0), device_contacts=0,
                 halted_seed=dict(ELF='41861dd7f4b28342e3751241fbc99ed6ea526ad0149d147eef58079349f651da',
                                  report='docs/planning/retained-callable-repair-halt-report.md'),
                 inputs=inputs)
    assert not OUT.exists()
    OUT.write_text(json.dumps(value, indent=2)+'\n')
    print(value['status'], gates)


if __name__ == '__main__':
    main()
