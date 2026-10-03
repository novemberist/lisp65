"""2.5.3 measurement of the public function-metadata authority population.

The 2.5.3 candidate added %nth-after-domain-check to lib/domain-tier1.lisp,
which shifts the host object words (literal pointers) of every code object
compiled after it, and changed IDE save/eval-buffer code. The 2.5.2 successor
pins five changed authorities; the 2.5.3 world changes twelve. The seven
additions (dir, ide, ide-buffers, m65d-remount, m65d-save, m65d-save-new,
m65d-status) keep arity, length, flags and library and differ only in their raw SHA
(literal pointer words; dir also moves one ordinal); the tool requires exactly that. Predecessor receipt
and tools stay immutable.
"""
import copy
import v11_function_metadata_ide_exit_20260928 as H
import v11_function_metadata_disk_r7_20260930 as D
import disk_r7_consumers_20260930 as S

RECEIPT = 'config/v11-function-metadata-v253-20260930-receipt.json'
PRIOR = ['compile-buffer-to-lib', 'compile-file-to-lib', 'eval-buffer',
         'load-file-to-buffer', 'save-buffer-to']
POINTER_ONLY = ['dir', 'ide', 'ide-buffers', 'm65d-remount', 'm65d-save',
                'm65d-save-new', 'm65d-status']
CHANGED = sorted(PRIOR + POINTER_ONLY)


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
        if row['name'] in POINTER_ONLY:
            now, then = row['authority']['code_object'], before['authority']['code_object']
            V.require(row['arity'] == before['arity'] and now['bytes'] == then['bytes']
                      and now['flags'] == then['flags']
                      and row['authority']['library'] == before['authority']['library']
                      and now['sha256'] != then['sha256'],
                      'pointer-only authority change is not pointer-only: ' + row['name'])
    return dict(index=index, receipt=receipt, changed_authorities=changed)


def derive():
    S.S.history(D.HISTORY)
    current = derive_metadata()
    return dict(metadata=current, disk_r7=S.measure())


if __name__ == '__main__':
    S.finish('v11_function_metadata', derive, RECEIPT, D, (__file__, D.__file__, H.__file__))
