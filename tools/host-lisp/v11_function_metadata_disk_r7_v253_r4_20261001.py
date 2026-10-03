"""2.5.3 r4 measurement of the public function-metadata authority population.

Successor of v11_function_metadata_disk_r7_v253_r3_20261001 (immutable, receipt
r3) after the reviewer's LCC arity fix in lib/dialect-v2/lcc-profile.lisp
(%lcc-v2-unary / %lcc-v2-binary guard car/cdr/consp/not/null/mod/cons in
%lcc-expr-ops2).  The r3 assertions run unchanged (same twelve authorities,
m65d-remount 148 -> 125, all others pointer-only); the r3 receipt drifts only
through the bound compiler source, so r4 re-measures under its own receipt.
"""
import v11_function_metadata_disk_r7_v253_r3_20261001 as R3

P, H, D, S = R3.P, R3.H, R3.D, R3.S
RECEIPT = 'config/v11-function-metadata-v253-r4-20261001-receipt.json'


LCC_GROWTH = dict(entries=2, blob_bytes=58)   # %lcc-v2-unary, %lcc-v2-binary


def derive():
    import json
    # r3 writes its own receipt path into the index pointer; point it at r4.
    saved, R3.RECEIPT = R3.RECEIPT, RECEIPT
    try:
        value = R3.derive()
    finally:
        R3.RECEIPT = saved
    # The only admitted drift against r3: the compiler-tier authority grows by the two guards.
    old = json.loads((S.ROOT / R3.RECEIPT).read_text())['current']['metadata']['receipt']['bindings']['bytecode_authorities']
    new = value['metadata']['receipt']['bindings']['bytecode_authorities']
    moved = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
    S.require(len(old) == len(new) and len(moved) == 1, 'v11 r4: authority drift beyond the LCC tier')
    a, b = old[moved[0]], new[moved[0]]
    S.require(b['entries'] - a['entries'] == LCC_GROWTH['entries'] and
              b['blob']['bytes'] - a['blob']['bytes'] == LCC_GROWTH['blob_bytes'],
              'v11 r4: LCC tier growth is not exactly +2 entries / +58 B')
    return value


if __name__ == '__main__':
    S.source_controls = P.era_source_controls(S.source_controls)
    S.finish('v11_function_metadata', derive, RECEIPT, R3,
             (__file__, R3.__file__, P.__file__, P.P.__file__, H.__file__, D.__file__))
