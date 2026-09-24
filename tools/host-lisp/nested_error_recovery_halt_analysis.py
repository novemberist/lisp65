"""Nested-error recovery: halt analysis from the executed receipts (no emulator, compiler or link).

Aggregates the Seed's identity, price, linked-byte inventory, medium, cold
boot, natural lanes, the matched GC with its complete attribution (the halt:
a fully attributed placement delta above 0.05 % of a collection, outside the
named-cost rule of the binding), the alignment-lever projection, and the two
post-halt diagnostic emulator rows (recorded as diagnostics, not as gate
verdicts).  Every bound file is verified before use.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/host-lisp'))
import retained_callable_writer_analysis as A  # noqa: E402

OUT = ROOT/'build/nested-error-recovery-r1/halt-analysis.json'


def bind(path):
    raw = Path(path).read_bytes()
    return dict(path=str(Path(path).resolve().relative_to(ROOT)), bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())


def load(path, inputs):
    inputs.append(bind(ROOT/path))
    return json.loads((ROOT/path).read_text())


def planes(bc, ac):
    n = A.u(bc, 16, 2)
    return {name: bc[off:off+cnt] == ac[off:off+cnt] for name, off, cnt in [
        ('header', 0, 48), ('images', 48, A.u(bc, 12, 2)*32), ('entries', A.u(bc, 30, 2), n*10),
        ('resolutions', A.u(bc, 32, 2), A.u(bc, 20, 2)*2), ('roots', A.u(bc, 34, 2), A.u(bc, 24, 2)*2)]}


def diagnostic(name, sequence, inputs):
    d = ROOT/f'build/nested-error-recovery-gates-{name}-r1'
    r = load(str((d/'receipt.json').relative_to(ROOT)), inputs)
    assert r['status'].startswith('CAPTURED')
    for row in r['captures']:
        for b in list(row['regions'].values()) + [row['screen']]:
            assert bind(ROOT/b['path'])['sha256'] == b['sha256'], b['path']
    caps = {c['label']: c for c in r['captures']}
    comparisons = []
    for a, b in zip(sequence, sequence[1:]):
        bc, bb = (d/f'{a}-c2d.bin').read_bytes(), (d/f'{a}-bank2.bin').read_bytes()
        ac, ab = (d/f'{b}-c2d.bin').read_bytes(), (d/f'{b}-bank2.bin').read_bytes()
        p = planes(bc, ac)
        comparisons.append(dict(before=a, after=b, counts=A.counts(ac), planes=p, bank2_identical=bb == ab,
                                c2_ready_after=caps[b]['c2_ready'], ok=all(p.values()) and bb == ab))
    return dict(status='DIAGNOSTIC ONLY (after the halt was recognised); not a gate verdict',
                steps=[dict(label=s['label'], form=s['form'], expected=s['expected'], passed=s['passed'],
                            tail=s['tail'][-2:]) for s in r['steps']],
                comparisons=comparisons, receipt=bind(d/'receipt.json'))


def main():
    assert not OUT.exists()
    inputs = []
    price = load('build/nested-error-recovery-product-r1/wplto/nested-error-recovery-seed-price.json', inputs)
    inventory = load('build/nested-error-recovery-seed-inventory-r1/inventory.json', inputs)
    packed = load('build/nested-error-recovery-seed-medium-r1/packed-receipt.json', inputs)
    boot = load('build/nested-error-recovery-native-boot-r1/qualification.json', inputs)
    lanes = load('build/nested-error-recovery-r1/latency-qualification.json', inputs)
    gc = load('build/nested-error-recovery-r1/gc-qualification.json', inputs)
    hot = load('build/nested-error-recovery-r1/hot-branch-pages.json', inputs)
    admission = load('build/nested-error-recovery-r1/preflight-admission.json', inputs)
    assert price['status'].startswith('PASS') and inventory['status'].startswith('PASS')
    assert boot['status'].startswith('PASS') and lanes['status'].startswith('PASS')
    assert gc['status'].startswith('HALT: PLACEMENT DELTA FULLY ATTRIBUTED')

    def boot_cycles(path):
        rows = [l.split() for l in (ROOT/path).read_text().splitlines() if l.startswith('E ')]
        inputs.append(bind(ROOT/path))
        return int(rows[-1][2]) - int(rows[0][2])
    base_boot = boot_cycles('build/retained-callable-repair-r2-native-boot-r1/capture-r1/boot.txt')
    seed_boot = boot_cycles('build/nested-error-recovery-native-boot-r1/capture-r1/boot.txt')
    collections = {k: dict(measured=v['measured_delta'], placement=v['expected_placement_delta'],
                           interrupt=v['interrupt_delta']['cycles'], fraction=v['fraction'],
                           placement_fraction=v['placement_fraction'], cycles=v['cycles'],
                           changed_branch_sites=v['changed_branch_sites'],
                           fully_attributed=v['fully_attributed'], within_named_cost=v['within_named_cost'])
                   for k, v in gc['collections'].items()}
    lever = {phase: [r for r in rows if r['pad'] in (-14, -10, 0, 2, 5, 13, 15)]
             for phase, rows in gc['alignment_lever']['rows'].items()}
    value = dict(
        status='HALT: GC PLACEMENT DELTA ABOVE 0.05 % OF A COLLECTION (NAMED-COST RULE); DEFER RULE OF 44c021ee',
        binding='44c021ee', source_authority='90b5f9f2', producer_commit='2fb8df5c', form='c-alpha',
        seed=dict(elf=inventory['ELFs'][1], medium=packed['medium']),
        base=dict(elf=inventory['ELFs'][0]),
        budget_consumed=dict(seed=1, final=0, product_link=0, device=0, replacement_seed=0),
        price=dict(ordinary_text=[price['predecessor']['ordinary_text_free'], price['candidate']['ordinary_text_free']],
                   changed_function=price['changed_function'],
                   other_owners_unchanged=price['owner_floors_unchanged'],
                   projection_non_lto=admission['object_projection']),
        inventory=dict(status=inventory['status'], counts=inventory['changed_section_byte_counts'],
                       relocations=dict((k, inventory['relocations'][k]) for k in
                                        ('base', 'seed', 'matched', 'bad_count', 'member_base', 'member_seed',
                                         'encoding_failure_count')),
                       unclassified=inventory['unclassified_count'], member=inventory['member']),
        medium=dict(sha256=packed['medium']['sha256'], closure_failures=packed['closure']['failures'],
                    coherence_failures=packed['coherence']['failures']),
        boot=dict(status=boot['status'], stack_low=boot['stack_low'], carrier_writes=boot['carrier_writes'],
                  cycles=dict(base=base_boot, seed=seed_boot, delta=seed_boot-base_boot)),
        lanes={k: dict(ratio=v['ratio'], collections=v['collections']) for k, v in lanes['lanes'].items()},
        gc=dict(status=gc['status'], collections=collections, lever=lever,
                rule='placement-only delta at most 0.05 % of a collection, fully attributed; lever taken when a few bytes'),
        hot_branch_pages={k: dict(status=v['status'], owners=v['owners']) for k, v in hot['rows'].items()},
        diagnostics=dict(
            nested=diagnostic('nested', ['package', 'after-nested', 'end'], inputs),
            depth2=diagnostic('depth2', ['package', 'after-depth2', 'after-inner', 'after-normal', 'end'], inputs)),
        not_executed=['gate 2 over-cap rows', 'gate 3 normal-path breakpoint row', 'gate 4 repair regression rows',
                      'gate 5 RUN/STOP attempt', 'usage lanes', 'dated check-source successors',
                      'sealed full check-source', 'Final'],
        inputs=inputs, driver=bind(Path(__file__)))
    OUT.write_text(json.dumps(value, indent=2)+'\n')
    print(value['status'])
    print(json.dumps(dict(gc=collections, boot=value['boot']['cycles'], lanes=value['lanes']), indent=1))


if __name__ == '__main__':
    main()
