"""2.5.3 r6 measurement of the public function-metadata authority population.

Successor of v11_function_metadata_disk_r7_v253_r5_20261001 (immutable, receipt
r5) after the lib/lcc.lisp nesting-depth fix (F2): %lcc-setq-one is the 2.5.2
single-pair body again and %lcc-setq-pairs calls it in tail position for the
last pair.  The r3 assertions run unchanged (same twelve authorities,
m65d-remount 148 -> 125, all others pointer-only); against r5 the only
admitted drift is the compiler-tier authority: same entries, blob +1 B.
"""
import json

import v11_function_metadata_disk_r7_v253_r5_20261001 as R5

R4 = R5.R4
R3, P, H, D, S = R5.R3, R5.P, R5.H, R5.D, R5.S
RECEIPT = 'config/v11-function-metadata-v253-r6-20261002-receipt.json'
LCC_GROWTH = dict(entries=0, blob_bytes=1)   # setq tail-call reshaping only


def derive():
    # r3 writes its own receipt path into the index pointer; point it at r6.
    saved, R3.RECEIPT = R3.RECEIPT, RECEIPT
    try:
        value = R3.derive()
    finally:
        R3.RECEIPT = saved
    old = json.loads((S.ROOT / R5.RECEIPT).read_text())['current']['metadata']['receipt']['bindings']['bytecode_authorities']
    new = value['metadata']['receipt']['bindings']['bytecode_authorities']
    moved = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
    S.require(len(old) == len(new) and len(moved) == 1, 'v11 r6: authority drift beyond the LCC tier')
    a, b = old[moved[0]], new[moved[0]]
    S.require(b['entries'] - a['entries'] == LCC_GROWTH['entries'] and
              b['blob']['bytes'] - a['blob']['bytes'] == LCC_GROWTH['blob_bytes'],
              'v11 r6: LCC tier growth is not exactly +0 entries / +%d B: %d / %d'
              % (LCC_GROWTH['blob_bytes'], b['entries'] - a['entries'], b['blob']['bytes'] - a['blob']['bytes']))
    return value


if __name__ == '__main__':
    S.source_controls = P.era_source_controls(S.source_controls)
    S.finish('v11_function_metadata', derive, RECEIPT, R5,
             (__file__, R5.__file__, R4.__file__, R3.__file__, P.__file__, P.P.__file__, H.__file__, D.__file__))
