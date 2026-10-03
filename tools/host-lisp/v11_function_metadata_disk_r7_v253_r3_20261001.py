"""2.5.3 r3 measurement of the public function-metadata authority population.

Successor of v11_function_metadata_disk_r7_v253_r2_20260930 (immutable,
receipt r2) after the D2/D4 disk card (ownership check before write enable).
The changed population is still the same twelve authorities. The one moved
fact is the size of m65d-remount: D2/D4 replaces the D5 status test that was
inlined into m65d-remount by a call of the separate %m65d-remount-finish
(directory owner walk, BAM comparison, mount identity), so the public remount
object shrinks from 148 bytes (2.5.2) to exactly 125 (arity, flags and
library equal; r2 measured 158 for the D5-only candidate). The other
authorities stay pointer-only. The historical r7 disk price measurement (D1)
is replayed in the sealed 2.5.2 source world, as in r2.
"""
import copy

import evidence_era as E
import v11_function_metadata_disk_r7_v253_r2_20260930 as P

H, D, S = P.H, P.D, P.S
RECEIPT = 'config/v11-function-metadata-v253-r3-20261001-receipt.json'
ERA = P.ERA
POINTER_ONLY = P.POINTER_ONLY
RESIZED = {'m65d-remount': (148, 125)}
CHANGED = P.CHANGED
assert sorted(POINTER_ONLY + list(RESIZED) + P.P.PRIOR) == CHANGED


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
        if row['name'] not in POINTER_ONLY and row['name'] not in RESIZED:
            continue
        now, then = row['authority']['code_object'], before['authority']['code_object']
        same_shape = (row['arity'] == before['arity'] and now['flags'] == then['flags']
                      and row['authority']['library'] == before['authority']['library'])
        if row['name'] in POINTER_ONLY:
            V.require(same_shape and now['bytes'] == then['bytes'] and now['sha256'] != then['sha256'],
                      'pointer-only authority change is not pointer-only: ' + row['name'])
        else:
            V.require(same_shape and (then['bytes'], now['bytes']) == RESIZED[row['name']],
                      'D2/D4 remount size is not exactly 148 -> 125: ' + row['name'])
    return dict(index=index, receipt=receipt, changed_authorities=changed,
                resized={k: list(v) for k, v in RESIZED.items()})


def derive():
    S.S.history(D.HISTORY)
    current = derive_metadata()
    with E.host_source_world(ERA):
        disk_r7 = S.measure()
    return dict(metadata=current, disk_r7=disk_r7)


if __name__ == '__main__':
    S.source_controls = P.era_source_controls(S.source_controls)
    S.finish('v11_function_metadata', derive, RECEIPT, P, (__file__, P.__file__, P.P.__file__, H.__file__, D.__file__))
