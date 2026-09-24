"""Nested-error recovery: aggregate the budget-free preflight, fail closed before Seed.

Reads only receipts produced without a product link: the non-LTO projection of
the exact committed hunk, the command-probe world (command proof, active
include admission and controls), the link and E000 pre-probes against the
repair Seed-2 transcript (= the Final's consumed commands), and the slice
capacity statement of the repair medium.  Writes the write-once admission
build/nested-error-recovery-r1/preflight-admission.json that the producer's
`seed` action verifies by SHA.
"""
import json
import subprocess
from pathlib import Path

import nested_error_recovery_producer as P

ROOT = P.ROOT
REPAIR_SOURCES = P.REPAIR_SEED/'generated-product-sources'
SECTION = '.text.c2_abort_empty_journal'
PRICE = ROOT/'build/retained-callable-repair-product-r2/wplto/retained-callable-repair-r2-seed-price.json'


def load(path, evidence):
    full = ROOT/path
    evidence.append(P.bind(full))
    return json.loads(full.read_text())


def main():
    evidence = []
    projection = load('build/nested-error-recovery-r1/projection/projection.json', evidence)
    assert projection['driver'] == P.bind(ROOT/projection['driver']['path'])
    assert projection['generated'] == P.bind(REPAIR_SOURCES/'c2_product_runtime.c')
    assert projection['delta'] == {'c-alpha': {'.rela'+SECTION: 576, SECTION: 137}}, projection['delta']
    # The projected hunk is the committed authority's hunk.
    committed = subprocess.check_output(['git', 'diff', P.AUTH+'~1', P.AUTH, '--', 'src/c2_product_runtime.c'],
                                        cwd=ROOT, text=True)
    hunk = (ROOT/projection['hunk']['path']).read_text()
    assert hunk.split('@@', 1)[1] == committed.split('@@', 1)[1], 'projected hunk is not the authority hunk'
    ready = load('build/nested-error-recovery-product-r1-preflight/command-ready.json', evidence)
    assert ready['driver'] == P.bind(ROOT/'tools/host-lisp/nested_error_recovery_producer.py')
    for key in ('proof', 'active_includes', 'include_controls'):
        row = ready[key]
        assert P.bind(ROOT/row['path']) == row, key
        assert key == 'proof' or json.loads((ROOT/row['path']).read_text())['status'].startswith('PASS')
        evidence.append(row)
    proof = json.loads((ROOT/ready['proof']['path']).read_text())
    world = Path(proof['output'])
    generated = world/'generated-product-sources'
    differing = sorted(p.name for p in generated.iterdir()
                       if p.is_file() and p.read_bytes() != (REPAIR_SOURCES/p.name).read_bytes())
    assert differing == ['c2_product_runtime.c'], differing
    assert sorted(p.name for p in generated.iterdir() if p.is_file()) == \
        sorted(p.name for p in REPAIR_SOURCES.iterdir() if p.is_file())
    projected = ROOT/projection['arms']['c-alpha']['source']['path']
    assert (generated/'c2_product_runtime.c').read_bytes() == projected.read_bytes(), \
        'generated runtime differs from the projected source'
    assert (generated/'c2-stream-v2-decoder.c').read_bytes() == (ROOT/P.DECODER).read_bytes() \
        == (REPAIR_SOURCES/'c2-stream-v2-decoder.c').read_bytes()
    assert len(proof['commands']) == 75
    link = load('build/nested-error-recovery-link-preprobe-r1/receipt.json', evidence)
    assert link['status'] == 'PASS' and link['new_findings_count'] == 0
    assert link['bindings']['command_proof']['sha256'] == ready['proof']['sha256']
    assert link['baseline']['command_proof']['path'] == \
        'build/retained-callable-repair-product-r2/wplto/command-proof.json'
    e000 = load('build/nested-error-recovery-e000-preprobe-r1/e000-low-edges-receipt.json', evidence)
    assert e000['status'] == 'PASS' and e000['new_findings_count'] == 0
    capacity = load('build/nested-error-recovery-capacity-r1/slice-capacity-preflight.json', evidence)
    price = load(str(PRICE.relative_to(ROOT)), evidence)
    base = price['candidate']
    assert base['ELF']['sha256'] == P.REPAIR_FINAL_ELF_SHA
    # Conservative: charge the whole non-LTO growth to ordinary text; the Seed
    # link prices the product.  No Session slice, E000, capture or high-BSS
    # owner is touched by the hunk (one .text input section).
    projected_free = base['ordinary_text_free'] - 137
    assert projected_free >= base['text_floor'], projected_free
    fam = capacity['families']['session']
    assert capacity['unique_catalog_slots_free'] == 1
    for path in P.MEMBERS + (
            'tools/host-lisp/nested_error_recovery_producer.py',
            'tools/host-lisp/nested_error_recovery_preflight.py',
            'build/nested-error-recovery-r1/driver/projection.py',
            'build/nested-error-recovery-r1/preflight-notes.md',
            'build/nested-error-recovery-r1/expanded-constructor.py',
            'build/nested-error-recovery-r1/composition.json',
            'build/nested-error-recovery-r1/plane.json',
            'build/nested-error-recovery-r1/linker-scripts-carrier-successor.json',
            'build/nested-error-recovery-r1/slice-registration.json',
            'docs/planning/post-2.3.0-plan.md',
            'docs/planning/definitions-set-b-preflight.md'):
        evidence.append(P.bind(ROOT/path))
    value = dict(status='PASS', authority=P.AUTH, diff_base=P.DIFF_BASE, binding=P.BINDING, form='c-alpha',
                 scope='Nested-error recovery (Set B member c) on the accepted retained-callable repair Final; '
                       'one function in ordinary text; plane, Lisp, decoder and public surface unchanged',
                 budget_consumed=dict(seed=0, final=0, product_link=0),
                 object_projection=projection['delta'],
                 ordinary_text=dict(repair_final_free=base['ordinary_text_free'], floor=base['text_floor'],
                                    projected_free_conservative=projected_free),
                 session_base=dict(region0_free=fam['region0']['free'], region1_free=fam['region1']['free'],
                                   region2_free=fam['region2']['free'], catalog_slots_free=fam['catalog_slots_free'],
                                   unique_catalog_slots_free=capacity['unique_catalog_slots_free']),
                 generated_sources_changed_vs_repair_final=differing, compiler_commands=75,
                 evidence=evidence,
                 limits=['Object sizes are non-LTO projections; the Seed link prices the product',
                         'Every .text function after the changed one moves; the inventory must prove address drift',
                         'No native execution before the Seed; emulator gates follow the Seed'])
    P.write_once(P.HERE/'preflight-admission.json', json.dumps(value, indent=2)+'\n')
    print('nested-error-recovery preflight: PASS; ordinary text free', base['ordinary_text_free'], '->',
          projected_free, '(conservative, floor', str(base['text_floor'])+'); session region0 free',
          fam['region0']['free'], '; 0/0/0')


if __name__ == '__main__':
    main()
