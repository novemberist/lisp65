"""Aggregate the configured Put-Kit preflight, fail closed before Seed."""
import json
from pathlib import Path
import subprocess

import put_kit_producer as P
import put_kit_host as H
import put_kit_objects as O
import slice_capacity_preflight as C


def publication_body(runtime):
    signature = 'static uint8_t c2_publish_exports_from(uint16_t first) {'
    assert runtime.count(signature) == 2  # unsliced historical branch, then product branch
    return H.function(runtime[runtime.rindex(signature):], signature)


def lifetime(runtime):
    publication = publication_body(runtime)
    abort = H.function(runtime, 'uint8_t c2_product_abort_recover(')
    assert publication.count('c2_boot_name_index_invalidate();') == 2
    assert publication.index('c2_boot_name_index_invalidate();') < publication.index('return 0;')
    assert publication.rindex('c2_boot_name_index_invalidate();') < publication.index(
        'if (!c2_phase_scratch_release(LISP65_C2_PHASE_OWNER_APPEND))')
    assert abort.index('c2_boot_name_index_invalidate();') < abort.index('if (!c2_ready)')


def main():
    evidence = []
    def read(path):
        full = O.ROOT / path
        evidence.append(P.bind(full))
        return json.loads(full.read_text())
    price = read('build/put-kit-objects-r1/receipt.json')
    assert price['tool_sha256'] == O.sha(Path(O.__file__))
    for row in price['rows']:
        for dep in row['inputs']:
            assert O.sha(O.ROOT / dep['path']) == dep['sha256']
    delta = {k: v for k, v in price['section_deltas'].items() if v}
    assert set(delta) == {'.text.v2_bnx_hash', '.text.v2_bnx_put', '.text.v2_bnx_find',
                          '.text.v2_bnx_catch_up', '.lisp65_rt_c2d_10b',
                          '.lisp65_rt_c2append_publish_plan_resolve'}
    text = sum(v for k, v in delta.items() if k.startswith('.text'))
    assert text == 516 and 1847 - text >= 32
    # Exact object proof of unchanged non-code owners; not just equal sizes.
    for unit in {r['unit'] for r in price['rows']}:
        old, new = [r['sections'] for r in price['rows'] if r['unit'] == unit]
        for key in set(old) | set(new):
            if key not in delta:
                assert old.get(key) == new.get(key), (unit, key)
    read('build/put-kit-host-r1/receipt.json')
    replay = read('build/put-kit-replay-r1/receipt.json')
    for row in replay['inputs']:
        assert O.sha(O.ROOT / row['path']) == row['sha256']
    assert replay['results'][0]['returncode'] == 0 and replay['results'][1]['returncode'] != 0
    link = read('build/put-kit-link-preprobe-r1/receipt.json')
    assert link['status'] == 'PASS' and link['new_findings_count'] == 0
    e000 = read('build/put-kit-e000-preprobe-r1/e000-low-edges-receipt.json')
    assert e000['status'] == 'PASS'
    ready = read('build/put-kit-product-r4-preflight/command-ready.json')
    assert ready['driver'] == P.bind(Path(P.__file__))
    for key in ('proof', 'active_includes', 'include_controls'):
        row = ready[key]
        assert P.bind(O.ROOT / row['path']) == row
        evidence.append(row)
    read('build/put-kit-r4/linker-scripts-carrier-successor.json')
    runtime = (O.ROOT / 'src/c2_product_runtime.c').read_text()
    predecessor = subprocess.check_output(['git', 'show', 'e497ad71:src/c2_product_runtime.c'],
                                          cwd=O.ROOT, text=True)
    assert publication_body(runtime) == publication_body(predecessor)
    for signature in ('uint8_t c2_product_abort_recover(',
                      'void c2_boot_name_index_invalidate(',
                      'void c2_boot_name_index_head_get('):
        assert H.function(runtime, signature) == H.function(predecessor, signature)
    lifetime(runtime)
    controls = []
    for occurrence in (0, 1, 2):
        pub = runtime.rindex('static uint8_t c2_publish_exports_from(uint16_t first) {')
        start = runtime.index('c2_boot_name_index_invalidate();', pub)
        if occurrence == 1:
            start = runtime.index('c2_boot_name_index_invalidate();', start + 1)
        if occurrence == 2:
            start = runtime.index('c2_boot_name_index_invalidate();', runtime.index(
                'uint8_t c2_product_abort_recover('))
        mutation = runtime[:start] + runtime[start:].replace('c2_boot_name_index_invalidate();', '', 1)
        try:
            lifetime(mutation)
        except (AssertionError, ValueError):
            controls.append(occurrence)
        else:
            raise AssertionError('invalidation mutation accepted')
    medium = O.ROOT / 'build/boot-only-carrier-seed-medium-r1/materialized'
    world = C.load_world(medium)
    session = world['manifests']['session']
    position = 0
    original_end = 0
    for row in session['slices']:
        if row['region_id'] != 0:
            continue
        original_start = row['source_address'] % 65536
        assert original_start >= original_end
        # Preserve catalog/header prefixes and all paid holes. Repacking from
        # zero would falsely claim the existing leading gap as recovered air.
        position = C.align_up(position + original_start - original_end,
                              session['policy']['payload_alignment'])
        # Conservative per-member projection: never credit shrinking slices;
        # retain their linked size, debit growth at its full object delta.
        size = row['file_size'] + max(0, delta.get(row['section'], 0))
        assert size <= session['policy']['max_slice_bytes']
        position += size
        original_end = original_start + row['file_size']
    projected_free = 65536 - position
    assert projected_free > 0 and world['slice_count_unique'] == 63
    for path in ('src/c2_product_runtime.c', 'src/symbol.c', 'src/c2_platform_dma.c',
                 'config/put-kit-native/includes/c2-stream-v2-decoder.c',
                 'config/put-kit-native/include-closure.json'):
        evidence.append(P.bind(O.ROOT / path))
    for path in sorted((O.ROOT / 'tools/host-lisp').glob('put_kit_*.py')):
        evidence.append(P.bind(path))
    for family in ('session', 'boot'):
        evidence.append(P.bind(medium / f'runtime-overlays-{family}-final.json'))
    value = dict(status='PASS', authority=P.AUTH, budget=dict(seed=0, finale=0, link=0),
                 ordinary_text_object_delta=text, projected_text_reserve=1847-text,
                 invalidation_controls=controls, existing_lifetime_functions_source_identical=True,
                 session_region0_conservative_free=projected_free,
                 session_region1_free=world['families']['session']['region1']['free'],
                 session_region2_free=world['families']['session']['region2']['free'],
                 unique_slots_free=1, evidence=evidence,
                 limits=['Object/link-map projection, not final LTO placement',
                         'Abort controls are compositional/source and host replay, not native fault injection',
                         'Current native name parity, boot timing and all final gates still required'])
    value['supersedes'] = 'build/put-kit-r3/preflight-admission.json: omitted existing paid gaps; r3 command admission predates its final driver; no compiler ran'
    P.write_once(P.HERE / 'preflight-admission-r2.json', json.dumps(value, indent=2) + '\n')
    print(f'put-kit-preflight: PASS text +{text}, conservative region0 free {projected_free}; 0/0/0')


if __name__ == '__main__':
    main()
