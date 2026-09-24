"""Close the executed nested-error recovery Seed: every pre-Final gate from its receipt.

Writes config/nested-error-recovery-seed.json, the qualification the Final
driver verifies input by input (write-once).  No emulator, compiler or link.
The GC placement delta is carried as the named cost the reviewer accepted
(eaf59c62): fully attributed, natural +2,905 / forced +2,641 measured,
+2,751 forced placement expected; any other value fails closed.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'config/nested-error-recovery-seed.json'
SEED_SHA = '66165507a8e5ad1d857afdd967f9056be2ce7bbccc332d5328e981398078b47b'


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
    seed = ROOT/'build/nested-error-recovery-product-r1/wplto/resident-island-seed.prg.elf'
    assert bind(seed)['sha256'] == SEED_SHA
    inputs.append(bind(seed))
    admission = load('build/nested-error-recovery-r1/preflight-admission.json')
    assert admission['status'] == 'PASS' and admission['authority'] == '90b5f9f2'
    inv = load('build/nested-error-recovery-seed-inventory-r1/inventory.json')
    assert inv['status'] == 'PASS: ALL DIFFERENCES INSIDE THE MEMBER, ADDRESS DRIFT BY f, OR DERIVED'
    assert inv['unclassified_count'] == 0 and inv['ELFs'][1]['sha256'] == SEED_SHA
    assert inv['relocations']['bad_count'] == inv['relocations']['encoding_failure_count'] == 0
    gates['6 inventory'] = inv['status']
    price = load('build/nested-error-recovery-product-r1/wplto/nested-error-recovery-seed-price.json')
    assert price['owner_floors_unchanged'] and price['candidate']['ordinary_text_free'] == 1209
    gates['6 price'] = dict(status=price['status'], ordinary_text=[1354, 1209])
    capacity = load('build/nested-error-recovery-capacity-seed-r1/slice-capacity-preflight.json')
    session = capacity['families']['session']
    assert session['region0']['free'] == 1351 and capacity['unique_catalog_slots_free'] == 1
    packed = load('build/nested-error-recovery-seed-medium-r1/packed-receipt.json')
    assert packed['closure']['failures'] == packed['coherence']['failures'] == []
    assert packed['elf']['sha256'] == SEED_SHA
    boot = load('build/nested-error-recovery-native-boot-r1/qualification.json')
    assert boot['status'].startswith('PASS') and boot['carrier_writes'] == 0 and boot['prompt_identical']
    gates['6 boot'] = boot['status']
    latency = load('build/nested-error-recovery-r1/latency-qualification.json')
    assert latency['status'].startswith('PASS')
    gates['6 lanes'] = {k: v['ratio'] for k, v in latency['lanes'].items()}
    gc = load('build/nested-error-recovery-r1/gc-qualification.json')
    c = gc['collections']
    assert all(x['fully_attributed'] for x in c.values())
    assert (c['warmup']['measured_delta'], c['warmup']['expected_placement_delta'], c['warmup']['interrupt_delta']['cycles']) == (2905, 2905, 0)
    assert (c['forced']['measured_delta'], c['forced']['expected_placement_delta'], c['forced']['interrupt_delta']['cycles']) == (2641, 2751, -110)
    plan = (ROOT/'docs/planning/post-2.3.0-plan.md').read_text()
    inputs.append(bind(ROOT/'docs/planning/post-2.3.0-plan.md'))
    assert 'Nested-error recovery: placement GC cost accepted as named cost, Seed continues (reviewer decision)' in plan
    gates['6 GC'] = dict(status='ACCEPTED NAMED PLACEMENT COST (reviewer decision eaf59c62)',
                         natural=dict(measured=2905, placement=2905), forced=dict(measured=2641, placement=2751, irq=-110),
                         placement_fraction={k: v['placement_fraction'] for k, v in c.items()})
    analysis = load('build/nested-error-recovery-r1/gate-analysis.json')
    assert analysis['status'] == 'PASS: GATES 1-4; GATE 5 BATCHED DEVICE ROW'
    for k in ('1', '2-minimal', '2-cumulative', '3', '4'):
        assert analysis['gates'][k]['status'] == 'PASS'
        gates[k] = 'PASS'
    gates['5'] = analysis['gates']['5']['status']
    for role in ('baseline', 'candidate'):
        u = load(f'build/nested-error-recovery-usage-{role}-r1/receipt.json')
        assert u['status'] == 'PASS' and u['error'] is None and len(u['rows']) == 23
        for r in u['rows']:
            assert bind(ROOT/r['screen']['path'])['sha256'] == r['screen']['sha256']
    inputs.append(bind(Path(__file__)))
    value = dict(status='PASS: EXECUTED NESTED-ERROR RECOVERY SEED', authority='90b5f9f2',
                 binding='44c021ee', decision='eaf59c62 (GC placement accepted as named cost; Seed continues)',
                 seed=dict(ELF=bind(seed), medium=packed['medium']), gates=gates,
                 budget=dict(seed=1, final=0, product_link=0, replacement_seed=0), device_contacts=0,
                 halt=dict(commit='62acee68', report='docs/planning/nested-error-recovery-halt-report.md'),
                 inputs=inputs)
    assert not OUT.exists()
    OUT.write_text(json.dumps(value, indent=2)+'\n')
    print(value['status'], gates)


if __name__ == '__main__':
    main()
