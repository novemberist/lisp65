#!/usr/bin/env python3
"""Read-only closure of the renderer product card; no producer entry point."""
import json
from pathlib import Path
import renderer_branch_product_card as CARD
from elf_truth import ElfTruth
from evidence_era import stable_recorded_on


def run():
    CARD.configure()
    R = CARD.F
    bind, load = R.C.bind, R.C.load
    pair = [bind(R.ELF), bind(R.PRG)]
    failure = load(R.BUILD/'failure-checks.json')
    assert failure['status'] == 'PASS' and failure['elf'] == pair[0]
    proofs = {}
    for name in ('classifier', 'execution'):
        p = R.ROOT/failure[name]['path']
        assert bind(p) == failure[name]
        proofs[name] = load(p)
        assert proofs[name]['status'] == 'PASS'
    assert not proofs['classifier']['violations']
    assert proofs['execution']['identities']['elf'] == pair[0]
    rows = proofs['execution']['rows']
    assert len(rows) == 6 and sum(row['mutant'] for row in rows) == 2
    assert all(row['passed_contract'] != row['mutant'] for row in rows)
    expected_roots = {p.name for p in
        (R.WPLTO/'.canonical-objects-lisp65-c2-substitution-linked').glob('[0-9][0-9][0-9]-*.o')}
    assert expected_roots
    for name in ('seed-to-final-attribution.json', 'predecessor-attribution.json'):
        value = load(R.BUILD/name)
        assert value['pair'][2:] == pair and value['unexplained_members'] == 0
        assert not value['unexplained_compiler_inputs']
        assert {row['name'] for row in value['compiler_roots']} == expected_roots
        assert len(value['compiler_roots']) == len(expected_roots)
    native = load(R.BUILD/'final-native-proof.json')
    assert native['status'] == 'PASS' and native['pair'] == pair
    owners = native['bounded_owners']
    assert owners['all_floors_green']
    assert min(owners['ordinary_BSS']['low_reserve_bytes'], owners['ordinary_BSS']['high_reserve_bytes']) >= 5
    assert native['E000']['free_bytes'] >= native['E000']['floor_bytes']
    assert native['E000']['capture_watch_bytes'] >= native['E000']['capture_watch_floor_bytes']
    t = ElfTruth.read(R.ELF, llvm_readobj=R.C.B.READOBJ)
    old = ElfTruth.read(CARD.PREDECESSOR['ELF'], llvm_readobj=R.C.B.READOBJ)
    renderer = t.section('.lisp65_rt_l65e')
    cap = t.symbol('__lisp65_error_overlay_max_bytes').value
    assert cap == old.symbol('__lisp65_error_overlay_max_bytes').value == 1320
    assert renderer.bytes <= cap
    owners['renderer'] = {'vma': renderer.address, 'bytes': renderer.bytes,
                          'limit': cap, 'remaining': cap-renderer.bytes}
    assert load(R.WPLTO/'owner-scope-result.json')['status'] == 'PASS'
    assert load(R.BUILD/'artifact-acceptance.json')['status'] == 'PASS'
    lto = sorted(R.WPLTO.glob('*.prg.lto.o'))
    assert {p.name for p in lto} == {'resident-island-seed.prg.lto.o', 'lisp65-c2-substitution-linked.prg.lto.o'}
    invocation = load(R.INVOCATION)
    assert invocation['authority'] == CARD.authority()
    # Bind immutable execution runs, not the mutable latest-run pointer.
    paths = [R.ROOT/failure[n]['path'] for n in ('classifier', 'execution')]
    paths += [R.BUILD/n for n in ('final-native-proof.json',
             'seed-to-final-attribution.json', 'predecessor-attribution.json', 'artifact-acceptance.json')]
    paths += [R.WPLTO/'owner-scope-result.json', R.PREFLIGHT_RECEIPT, R.INVOCATION]
    out = R.BUILD/'qualification.json'
    result = {'status': 'PASS: RENDERER PRODUCT QUALIFIED; REVIEW PENDING',
        'recorded_on': stable_recorded_on(out), 'authority': CARD.authority(),
        'source_commit': invocation['commit'], 'pair': pair,
        'owners': owners, 'E000': native['E000'], 'evidence': [bind(p) for p in paths],
        'lto_artifacts': [bind(p) for p in lto],
        'accounting': {'seed_WPLTO': 1, 'final_C_LTO': 1, 'product_links': 1,
                       'new_medium_builds': 0, 'device_contacts': 0},
        'check_source': 'candidate failure target passed and wired; complete check-source not claimed',
        'boundary': 'No packed-medium or hardware acceptance; existing medium only bootstraps disposable leaf-ABI harness.'}
    assert pair == [bind(R.ELF), bind(R.PRG)]
    out.write_text(json.dumps(result, indent=2)+'\n')
    print(result['status'])


if __name__ == '__main__':
    run()
