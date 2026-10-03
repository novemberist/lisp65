"""2.5.3 r2 measurement of the public function-metadata authority population.

Successor of v11_function_metadata_disk_r7_v253_20260930 (immutable, receipt
r1) after the D3 lossless-load and D5 full-directory-remount disk candidate.
The changed population is still the same twelve authorities; the one new fact
is that m65d-remount is no longer pointer-only: D5 makes %m65d-remount-finish
accept a valid directory without a free entry, which grows the remount object
by exactly ten bytes (148 -> 158, arity, flags and library equal). The other
pointer-only authorities must stay pointer-only. The historical r7 disk price
measurement (D1) is replayed in the sealed 2.5.2 source world, because
lib/m65-disk.lisp moved on purpose.
"""
import copy

import evidence_era as E
import v11_function_metadata_disk_r7_v253_20260930 as P

H, D, S = P.H, P.D, P.S
RECEIPT = 'config/v11-function-metadata-v253-r2-20260930-receipt.json'
ERA = '49d128599c73a5b6eb6b8595431923cd30b84491'
POINTER_ONLY = ['dir', 'ide', 'ide-buffers', 'm65d-save', 'm65d-save-new', 'm65d-status']
GROWN = {'m65d-remount': (148, 158)}
CHANGED = P.CHANGED
assert sorted(POINTER_ONLY + list(GROWN) + P.PRIOR) == CHANGED


def derive_metadata():
    V = H.H
    V.selftest()
    index, receipt = V.collect()
    V.require(not any(row['authority'].get('library') == 'idex'
                      for row in index['records']), 'new public idex authority needs review')
    authority = next(row for row in receipt['bindings']['bytecode_authorities']
                     if row['library'] == 'idex')
    manifest = V.load(V.ROOT / authority['manifest']['path'])
    blob = (V.ROOT / manifest['blob']).read_bytes()
    projection = H.idex_projection(manifest, blob)
    H.projection_selftest(manifest, blob)
    del authority['blob']['sha256']
    del authority['manifest']['blob_sha256']
    authority['loader_projection'] = projection
    old = V.load(V.INDEX)
    def public(value):
        value = copy.deepcopy(value)
        for row in value['records']:
            row.pop('authority')
        return value
    V.require(public(old) == public(index), 'public metadata semantics regressed')
    receipt['index']['path'] = RECEIPT + '#current/index'
    changed = [row['name'] for row, before in zip(index['records'], old['records'])
               if row != before]
    V.require(changed == CHANGED, 'unexpected metadata authority population drift')
    for row, before in zip(index['records'], old['records']):
        if row['name'] not in POINTER_ONLY and row['name'] not in GROWN:
            continue
        now, then = row['authority']['code_object'], before['authority']['code_object']
        if row['name'] in POINTER_ONLY:
            V.require(row['arity'] == before['arity'] and now['bytes'] == then['bytes']
                      and now['flags'] == then['flags']
                      and row['authority']['library'] == before['authority']['library']
                      and now['sha256'] != then['sha256'],
                      'pointer-only authority change is not pointer-only: ' + row['name'])
        if row['name'] in GROWN:
            V.require(row['arity'] == before['arity'] and now['flags'] == then['flags']
                      and row['authority']['library'] == before['authority']['library']
                      and (then['bytes'], now['bytes']) == GROWN[row['name']],
                      'D5 remount growth is not the exact ten bytes: ' + row['name'])
    return dict(index=index, receipt=receipt, changed_authorities=changed)


def era_source_controls(original):
    def controls():
        with E.host_source_world(ERA):
            original()
    return controls


def derive():
    S.S.history(D.HISTORY)
    current = derive_metadata()
    with E.host_source_world(ERA):
        disk_r7 = S.measure()
    return dict(metadata=current, disk_r7=disk_r7)


if __name__ == '__main__':
    S.source_controls = era_source_controls(S.source_controls)
    S.finish('v11_function_metadata', derive, RECEIPT, P, (__file__, P.__file__, H.__file__, D.__file__))
