"""2.5.5 r8 measurement of the public function-metadata authority population.

Successor of v11_function_metadata_disk_r7_v254_r7_20261003 (immutable,
receipt r7).  The 2.5.5 typing card changes the IDE library world, and against
r7 the admitted drift is exactly:

  ide authority   +0 entries, -146 blob bytes (printable code before the
                  keymap tables, accessors of the key path written out, the
                  loop stores the buffer once at entry)
  public record   `ide` 94 -> 111 bytes: the entry function now stores the
                  buffer once (%ide-persist-state at entry instead of before
                  every key in ide-run).  Arity, flags, library and the public
                  semantics are unchanged; the record population (139) does not
                  change; no other public record moves.

In the inherited r3 assertions `ide` therefore leaves the pointer-only set and
joins the resized set with exactly (94, 111) against the frozen index; every
other r3 assertion runs unchanged (same twelve changed authorities,
m65d-remount 148 -> 125, the remaining pointer-only rows pointer-only).

The O2-lite / r7 disk source pins are checked in the sealed 2.5.2 world
(era_replay_v254_20261003.pin_disk_r7_source_controls), as in r7.

Note for whoever reruns this by hand: the measurement reads the generated IDE
artifacts (route prerequisite v2-workbench-artifacts).  With stale artifacts it
reports no drift at all; the first r8 draft made exactly that mistake and went
red in its sealed single-target run.
"""
import copy
import json

import era_replay_v254_20261003 as E254
import v11_function_metadata_disk_r7_v254_r7_20261003 as R7

R6, R3 = R7.R6, R7.R3
P, H, D, S = R7.P, R7.H, R7.D, R7.S
RECEIPT = 'config/v11-function-metadata-v255-r8-20261006-receipt.json'
POINTER = '#current/index'
AUTHORITIES = {'ide': dict(entries=0, blob_bytes=-146)}
RECORDS = {'ide': (94, 111)}
INDEX_BYTES = 1          # "94" -> "111" in the index text


def r3_sets():
    """`ide` moves from pointer-only to resized in the inherited r3 assertions (in memory)."""
    assert 'ide' in R3.POINTER_ONLY and 'ide' not in R3.RESIZED, 'r3 sets moved'
    pointer_only = [name for name in R3.POINTER_ONLY if name != 'ide']
    resized = {**R3.RESIZED, 'ide': RECORDS['ide']}
    assert sorted(pointer_only + list(resized) + R3.P.P.PRIOR) == R3.CHANGED, 'r3 changed population moved'
    return pointer_only, resized


def derive():
    saved = R3.RECEIPT, R3.POINTER_ONLY, R3.RESIZED
    R3.RECEIPT = RECEIPT
    R3.POINTER_ONLY, R3.RESIZED = r3_sets()
    try:
        value = R3.derive()
    finally:
        R3.RECEIPT, R3.POINTER_ONLY, R3.RESIZED = saved
    old = json.loads((S.ROOT / R7.RECEIPT).read_text())['current']
    expected = copy.deepcopy(old)
    meta, now = expected['metadata'], value['metadata']
    rows, new_rows = meta['receipt']['bindings']['bytecode_authorities'], now['receipt']['bindings']['bytecode_authorities']
    S.require(len(rows) == len(new_rows), 'v11 r8: authority population drift')
    moved = [a['library'] for a, b in zip(rows, new_rows) if a != b]
    S.require(sorted(moved) == sorted(AUTHORITIES), 'v11 r8: authority drift beyond ide: ' + repr(moved))
    for i, (a, b) in enumerate(zip(rows, new_rows)):
        if a['library'] in AUTHORITIES:
            delta = AUTHORITIES[a['library']]
            S.require(b['entries'] - a['entries'] == delta['entries'] and
                      b['blob']['bytes'] - a['blob']['bytes'] == delta['blob_bytes'],
                      'v11 r8: %s change is not exactly %r' % (a['library'], delta))
            rows[i] = b
    records, new_records = meta['index']['records'], now['index']['records']
    S.require([r['name'] for r in records] == [r['name'] for r in new_records], 'v11 r8: record population drift')
    changed = [b['name'] for a, b in zip(records, new_records) if a != b]
    S.require(sorted(changed) == sorted(RECORDS), 'v11 r8: public record drift: ' + repr(changed))
    for i, (a, b) in enumerate(zip(records, new_records)):
        if b['name'] not in RECORDS:
            continue
        x, y = a['authority']['code_object'], b['authority']['code_object']
        S.require(a['arity'] == b['arity'] and x['flags'] == y['flags'] and
                  a['authority']['library'] == b['authority']['library'] == 'ide' and
                  (x['bytes'], y['bytes']) == RECORDS[b['name']] and
                  {k: v for k, v in a.items() if k != 'authority'} == {k: v for k, v in b.items() if k != 'authority'},
                  'v11 r8: record change is not the 2.5.5 IDE delta: ' + b['name'])
        records[i] = b
    index, new_index = meta['receipt']['index'], now['receipt']['index']
    S.require({k: v for k, v in index.items() if k not in ('path', 'sha256', 'bytes')} ==
              {k: v for k, v in new_index.items() if k not in ('path', 'sha256', 'bytes')}, 'v11 r8: index shape drift')
    S.require(index['path'] == R7.RECEIPT + POINTER and new_index['path'] == RECEIPT + POINTER, 'v11 r8: index pointer drift')
    S.require(new_index['bytes'] - index['bytes'] == INDEX_BYTES, 'v11 r8: index size is not exactly +%d' % INDEX_BYTES)
    index.update(path=new_index['path'], sha256=new_index['sha256'], bytes=new_index['bytes'])
    S.require('ide' not in meta['resized'], 'v11 r8: predecessor already resized ide')
    meta['resized'] = {**meta['resized'], 'ide': list(RECORDS['ide'])}
    S.require(value == expected, 'v11 r8: metadata drift beyond the 2.5.5 IDE delta')
    for mutate in (lambda v: v['metadata']['index']['records'][0].update(name='x'),
                   lambda v: v['metadata']['receipt']['bindings']['bytecode_authorities'][0]['blob'].update(bytes=0),
                   lambda v: v['metadata']['resized'].pop('ide'),
                   lambda v: v['metadata']['receipt']['index'].update(path=R7.RECEIPT + POINTER)):
        trial = copy.deepcopy(value)
        mutate(trial)
        S.require(trial != expected, 'v11 r8: mutation survived')
    return value


if __name__ == '__main__':
    E254.V.route_children()
    E254.pin_disk_r7_source_controls()
    S.source_controls = P.era_source_controls(S.source_controls)
    S.finish('v11_function_metadata', derive, RECEIPT, R7,
             (__file__, E254.__file__, R7.__file__, R6.__file__, R7.R5.__file__, R7.R4.__file__, R3.__file__, P.__file__,
              P.P.__file__, H.__file__, D.__file__))
