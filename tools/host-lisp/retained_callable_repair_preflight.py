"""Retained-callable repair: aggregate the budget-free preflight, fail closed before Seed.

Reads only receipts produced without a product link: the non-LTO object probe,
the command-probe world (command proof, active include admission and
controls), the link and E000 pre-probes against the anchor Seed transcript,
and the slice capacity statement of the anchor medium.  Writes the write-once
admission build/retained-callable-repair-r1/preflight-admission.json that the
producer's `seed` action verifies by SHA.
"""
import json
from pathlib import Path

import retained_callable_repair_producer as P

ROOT = P.ROOT
MEDIUM = ROOT/'build/dirty-anchor-seed-medium-r1/materialized'
JOURNAL = '.lisp65_rt_c2append_journal_prepare'
PHASE12 = '.lisp65_rt_c2d_12'


def load(path, evidence):
    full = ROOT/path
    evidence.append(P.bind(full))
    return json.loads(full.read_text())


def align_up(value, alignment):
    return (value + alignment - 1) // alignment * alignment


def main():
    evidence = []
    probe = load('build/retained-callable-repair-object-probe-r2/receipt.json', evidence)
    assert probe['driver']['sha256'] == P.sha(ROOT/probe['driver']['path'])
    assert probe['decoder']['successor'] == P.bind(ROOT/P.DECODER)
    deltas = {row['unit']: row['delta'] for row in probe['rows']}
    assert deltas == {
        'c2-stream-v2-phase-12.c': {PHASE12: -21, '.rela'+PHASE12: -48},
        'c2_product_runtime.c': {JOURNAL: 28, '.rela'+JOURNAL: 72}}, deltas
    ready = load('build/retained-callable-repair-product-r1-preflight/command-ready.json', evidence)
    assert ready['driver'] == P.bind(ROOT/'tools/host-lisp/retained_callable_repair_producer.py')
    for key in ('proof', 'active_includes', 'include_controls'):
        row = ready[key]
        assert P.bind(ROOT/row['path']) == row, key
        assert key == 'proof' or json.loads((ROOT/row['path']).read_text())['status'].startswith('PASS')
        evidence.append(row)
    proof = json.loads((ROOT/ready['proof']['path']).read_text())
    world = Path(proof['output'])
    generated = world/'generated-product-sources'
    anchor = P.BASE/'wplto/generated-product-sources'
    differing = sorted(p.name for p in generated.iterdir()
                       if p.is_file() and p.read_bytes() != (anchor/p.name).read_bytes())
    assert differing == ['c2-stream-v2-decoder.c', 'c2_product_runtime.c'], differing
    assert (generated/'c2-stream-v2-decoder.c').read_bytes() == (ROOT/P.DECODER).read_bytes()
    assert len(proof['commands']) == 75
    link = load('build/retained-callable-repair-link-preprobe-r1/receipt.json', evidence)
    assert link['status'] == 'PASS' and link['new_findings_count'] == 0
    assert link['bindings']['command_proof']['sha256'] == ready['proof']['sha256']
    assert link['baseline']['command_proof']['path'] == 'build/dirty-anchor-product-r1/wplto/command-proof.json'
    e000 = load('build/retained-callable-repair-e000-preprobe-r1/e000-low-edges-receipt.json', evidence)
    assert e000['status'] == 'PASS' and e000['new_findings_count'] == 0
    capacity = load('build/retained-callable-repair-capacity-r1/slice-capacity-preflight.json', evidence)
    session = json.loads((MEDIUM/'runtime-overlays-session-final.json').read_text())
    evidence.append(P.bind(MEDIUM/'runtime-overlays-session-final.json'))
    policy = session['policy']
    rows = {r['section']: r for r in session['slices']}
    grown = rows[JOURNAL]['file_size'] + 28
    # The object delta is non-LTO; the linked LTO growth is priced at Seed.
    # Headroom against the per-slice hard maximum is stated, not assumed.
    assert rows[JOURNAL]['region_id'] == 0 and grown <= policy['max_slice_bytes']
    # Conservative region-0 projection: debit growth, never credit shrink,
    # keep every paid gap (the Put-Kit preflight rule).
    position, original_end = 0, 0
    for row in session['slices']:
        if row['region_id'] != 0:
            continue
        start = row['source_address'] % 65536
        assert start >= original_end
        position = align_up(position + start - original_end, policy['payload_alignment'])
        size = row['file_size'] + (28 if row['section'] == JOURNAL else 0)
        assert size <= policy['max_slice_bytes']
        position += size
        original_end = start + row['file_size']
    projected_free = 65536 - position
    fam = capacity['families']['session']
    assert projected_free > 0 and capacity['unique_catalog_slots_free'] == 1
    for path in P.MEMBERS + (
            'tools/host-lisp/retained_callable_repair_producer.py',
            'tools/host-lisp/retained_callable_repair_object_probe.py',
            'tools/host-lisp/retained_callable_repair_preflight.py',
            'build/retained-callable-repair-r1/expanded-constructor.py',
            'build/retained-callable-repair-r1/composition.json',
            'build/retained-callable-repair-r1/plane.json',
            'build/retained-callable-repair-r1/linker-scripts-carrier-successor.json',
            'build/retained-callable-repair-r1/slice-registration.json',
            'build/retained-callable-repair-r1/preflight-notes.md',
            'docs/planning/post-2.3.0-plan.md'):
        evidence.append(P.bind(ROOT/path))
    value = dict(status='PASS', authority=P.AUTH, diff_base=P.DIFF_BASE, binding='d3d5044b',
                 scope='Two native members on the accepted dirty-anchor Final; plane, Lisp and public surface unchanged',
                 budget_consumed=dict(seed=0, final=0, product_link=0),
                 object_projection=deltas,
                 journal_prepare_slice=dict(anchor=rows[JOURNAL]['file_size'], projected=grown,
                                            max_slice_bytes=policy['max_slice_bytes']),
                 phase12_slice=dict(anchor=rows[PHASE12]['file_size'], projected=rows[PHASE12]['file_size'] - 21),
                 session_anchor=dict(region0_free=fam['region0']['free'], region1_free=fam['region1']['free'],
                                     region2_free=fam['region2']['free'], catalog_slots_free=fam['catalog_slots_free'],
                                     unique_catalog_slots_free=capacity['unique_catalog_slots_free']),
                 session_region0_conservative_free=projected_free,
                 generated_sources_changed=differing, compiler_commands=75,
                 evidence=evidence,
                 limits=['Object sizes are non-LTO projections; the Seed link prices the product',
                         'No native execution before the Seed; emulator gates follow the Seed'])
    P.write_once(P.HERE/'preflight-admission.json', json.dumps(value, indent=2)+'\n')
    print('retained-callable-repair preflight: PASS; journal slice', rows[JOURNAL]['file_size'], '->', grown,
          '/', policy['max_slice_bytes'], '; conservative region0 free', projected_free, '; 0/0/0')


if __name__ == '__main__':
    main()
