"""Close the admitted existing Seed, preserving the exact GC comparator halt."""
import json
from pathlib import Path
from dirty_anchor_producer import ROOT, HERE, bind


def main():
    inputs = []
    def load(name):
        p = ROOT / name
        inputs.append(bind(p))
        return json.loads(p.read_text())
    gates = {}
    for key, name in {
        'identity': 'build/dirty-anchor-card-r1/identity-qualification.json',
        'boot': 'build/dirty-anchor-native-boot-r2/qualification.json',
        'events': 'build/dirty-anchor-events-r3/receipt.json',
        'natural': 'build/dirty-anchor-card-r1/latency-qualification.json',
        'IDE': 'build/dirty-anchor-card-r1/mini-qualification.json',
        'VM': 'build/dirty-anchor-vm-lanes-r1/receipt.json',
    }.items():
        d = load(name)
        assert d['status'].startswith('PASS'), name
        gates[key] = d['status']
    for role in ('baseline', 'candidate'):
        d = load(f'build/dirty-anchor-usage-{role}-r1/receipt.json')
        assert d['status'] == 'PASS' and d['error'] is None and len(d['rows']) == 23
        assert d['rows'][18]['form'] == '(progn (setq savedlambda (lambda () 27)) 19)'
        assert d['rows'][18]['expected'] == '*** VM: BAD BYTECODE'
        assert [r['expected'] for r in d['rows'][19:]] == ['8', '8', '12', '8']
        for r in d['rows']:
            actual = bind(ROOT / r['screen']['path'])
            assert all(actual[k] == r['screen'][k] for k in ('bytes', 'sha256'))
        gates['usage_' + role] = 'PASS: 23 rows, exact registered error and four recovery rows'
    old = load('build/dirty-anchor-card-r1/gc-halt.json')
    assert old['status'] == 'HALT: MATCHED-GC ROOT POPULATION DIFFERS'
    assert old['delta_cycles'] == 318 and old['marked_cells'] == 501
    pairs = {}
    for role in ('baseline', 'candidate'):
        d = load(f'build/dirty-anchor-gc-equal-{role}-3/receipt.json')
        assert d['natural_count'] == d['forced_count'] == 1 and not d['excluded_collections']
        pairs[role] = {r['phase']: r for r in d['collections']}
    deltas = {}
    for phase, expected, marks in [('forced', 318, 501), ('warmup', 325, 532)]:
        a,b = [pairs[r][phase] for r in ('baseline', 'candidate')]
        assert a['marked']['count'] == b['marked']['count'] == marks
        assert b['cycles'] - a['cycles'] == expected
        deltas[phase] = dict(baseline=a['cycles'], candidate=b['cycles'], delta=expected, marked_cells=marks)
    authority = HERE / 'final-release-authority.md'
    assert 'matched-GC cost accepted as named cost' in authority.read_text()
    inputs.append(bind(authority))
    gc = dict(status='ACCEPTED NAMED LIVE COST', authority='e9ef6d57',
        comparator_unchanged=True, root_population_unchanged=True, deltas=deltas,
        attribution=bind(HERE / 'gc-halt.json'),
        interpretation='Duplicate anchor argument root; exact comparator remains HALT. Named live cost, no placement tolerance, no root removed.')
    p = HERE / 'gc-accepted.json'
    assert not p.exists()
    p.write_text(json.dumps(gc, indent=2) + '\n')
    inputs.append(bind(p))
    inputs += [bind(ROOT/'build/dirty-anchor-seed-medium-r1/packed-receipt.json'),
        bind(ROOT/'build/dirty-anchor-card-r1/plane.json'), bind(Path(__file__))]
    result = dict(status='PASS: EXECUTED DIRTY-ANCHOR SEED', authority='e9ef6d57',
        inputs=inputs, gates=gates, matched_gc=gc,
        budget=dict(seed=1, final=0, product_link=0), device_contacts=0,
        known_defect='savedlambda BAD BYTECODE remains registered, exact-error successor only; no tolerance')
    out = ROOT / 'config/dirty-anchor-seed.json'
    assert not out.exists()
    out.write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'])

if __name__ == '__main__':
    main()
