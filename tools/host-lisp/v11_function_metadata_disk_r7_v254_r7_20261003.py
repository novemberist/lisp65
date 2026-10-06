"""2.5.4 r7 measurement of the public function-metadata authority population.

Successor of v11_function_metadata_disk_r7_v253_r6_20261002 (immutable,
receipt r6).  The r3 assertions run unchanged (same twelve changed
authorities against the frozen index, m65d-remount 148 -> 125, pointer-only
rows pointer-only).  Against r6 the admitted drift is exactly the 2.5.4
static-plane change of two bytecode authorities and the public IDE objects
inside the IDE image:

  ide  +0 entries, +160 blob bytes (E3 publish written in place in
       %ide-drain-pending, key seam in route 14 of %ide-dispatch-route-high:
       +ide-bind-key, -%ide-source-size; save fix A)
  lcc  +0 entries, +52 blob bytes (funcall-of-literal-lambda, eq/eql and bit-op
       arity guards)
  public IDE records: compile-buffer-to-lib 185 -> 181, compile-file-to-lib
       174 -> 170, eval-buffer 88 -> 84 (inlined stage join), save-buffer-to
       156 -> 169 (D8 load guard); ide, ide-buffers, load-file-to-buffer
       move by ordinal/pointer only.  Arity, flags, library and the public
       semantics of every record are unchanged; the record population (139)
       does not change.

The O2-lite / r7 disk source pins are checked in the sealed 2.5.2 world
(era_replay_v254_20261003.pin_disk_r7_source_controls); the historical r7
disk price measurement is replayed there as before.
"""
import copy
import json

import era_replay_v254_20261003 as E254
import v11_function_metadata_disk_r7_v253_r6_20261002 as R6

R5, R4, R3 = R6.R5, R6.R4, R6.R3
P, H, D, S = R6.P, R6.H, R6.D, R6.S
RECEIPT = 'config/v11-function-metadata-v254-r7-20261003-receipt.json'
AUTHORITIES = {'ide': dict(entries=0, blob_bytes=160), 'lcc': dict(entries=0, blob_bytes=52)}
RECORDS = {'compile-buffer-to-lib': (185, 181), 'compile-file-to-lib': (174, 170), 'eval-buffer': (88, 84),
           'save-buffer-to': (156, 169), 'ide': (94, 94), 'ide-buffers': (24, 24),
           'load-file-to-buffer': (91, 91)}


def derive():
    # r3 writes its own receipt path into the index pointer; point it at r7.
    saved, R3.RECEIPT = R3.RECEIPT, RECEIPT
    try:
        value = R3.derive()
    finally:
        R3.RECEIPT = saved
    old = json.loads((S.ROOT / R6.RECEIPT).read_text())['current']
    expected = copy.deepcopy(old)
    meta, now = expected['metadata'], value['metadata']
    # bytecode authorities: only ide and lcc, by exactly the 2.5.4 deltas
    rows, new_rows = meta['receipt']['bindings']['bytecode_authorities'], now['receipt']['bindings']['bytecode_authorities']
    S.require(len(rows) == len(new_rows), 'v11 r7: authority population drift')
    moved = [a['library'] for a, b in zip(rows, new_rows) if a != b]
    S.require(sorted(moved) == sorted(AUTHORITIES), 'v11 r7: authority drift beyond ide/lcc: ' + repr(moved))
    for i, (a, b) in enumerate(zip(rows, new_rows)):
        if a['library'] in AUTHORITIES:
            delta = AUTHORITIES[a['library']]
            S.require(b['entries'] - a['entries'] == delta['entries'] and
                      b['blob']['bytes'] - a['blob']['bytes'] == delta['blob_bytes'],
                      'v11 r7: %s growth is not exactly %r' % (a['library'], delta))
            rows[i] = b
    # public records: exactly the listed IDE objects, same arity/flags/library
    records, new_records = meta['index']['records'], now['index']['records']
    S.require([r['name'] for r in records] == [r['name'] for r in new_records], 'v11 r7: record population drift')
    changed = [b['name'] for a, b in zip(records, new_records) if a != b]
    S.require(sorted(changed) == sorted(RECORDS), 'v11 r7: public record drift: ' + repr(changed))
    for i, (a, b) in enumerate(zip(records, new_records)):
        if b['name'] not in RECORDS:
            continue
        x, y = a['authority']['code_object'], b['authority']['code_object']
        S.require(a['arity'] == b['arity'] and x['flags'] == y['flags'] and
                  a['authority']['library'] == b['authority']['library'] == 'ide' and
                  (x['bytes'], y['bytes']) == RECORDS[b['name']] and
                  {k: v for k, v in a.items() if k != 'authority'} == {k: v for k, v in b.items() if k != 'authority'},
                  'v11 r7: record change is not the 2.5.4 IDE delta: ' + b['name'])
        records[i] = b
    index, new_index = meta['receipt']['index'], now['receipt']['index']
    S.require({k: v for k, v in index.items() if k not in ('path', 'sha256')} ==
              {k: v for k, v in new_index.items() if k not in ('path', 'sha256')}, 'v11 r7: index shape drift')
    S.require(new_index['path'] == RECEIPT + '#current/index', 'v11 r7: index pointer drift')
    index.update(path=new_index['path'], sha256=new_index['sha256'])
    S.require(value == expected, 'v11 r7: metadata drift beyond the 2.5.4 IDE/LCC deltas')
    return value


if __name__ == '__main__':
    E254.V.route_children()
    E254.pin_disk_r7_source_controls()
    S.source_controls = P.era_source_controls(S.source_controls)
    S.finish('v11_function_metadata', derive, RECEIPT, R6,
             (__file__, E254.__file__, R6.__file__, R5.__file__, R4.__file__, R3.__file__, P.__file__, P.P.__file__,
              H.__file__, D.__file__))
