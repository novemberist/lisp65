"""Nested-error recovery (Set B member c, form c-alpha): command admission, then one Seed.

Binding 44c021ee (top entry of docs/planning/post-2.3.0-plan.md), budget
1 Seed / 1 Final / 1 product link (+ at most one replacement Seed) on the
accepted retained-callable repair Final (ELF 815b60a5..., D81 fdb95e71...).

Template: the retained-callable repair Seed-2 producer, unchanged in method.
The Seed-1 constructor rebase (retained_callable_repair_producer.successor)
projects `git diff DIFF_BASE -- src/c2_product_runtime.c` onto the dirty-anchor
generated runtime copy.  With DIFF_BASE d3d5044b that diff is exactly the
repair Final's member 2 plus this card's hunk, so the generated population is
the repair Final's consumed population plus this card's hunk alone (asserted
by the preflight admission against build/retained-callable-repair-product-r2).

  AUTH/DIFF_BASE  90b5f9f2 / d3d5044b  (git diff d3d5044b -- src lib: the
                  runtime alone)
  include closure config/retained-callable-repair-r2-native/ (decoder
                  byte-identical to the accepted world's; no include change)
  predecessor     the repair Final (build/retained-callable-repair-final-r1)
  output          build/nested-error-recovery-r1, -product-r1(-preflight)

Merely running command-probe never consumes the Seed budget.
"""
import builtins
import json
import shutil
import sys
import types

import retained_callable_repair_producer as S1
import retained_callable_repair_r2_producer as S2

ROOT = S1.ROOT
PARENT = S1.PARENT
HERE = ROOT/'build/nested-error-recovery-r1'
OUT = ROOT/'build/nested-error-recovery-product-r1-preflight'
BUILD = ROOT/'build/nested-error-recovery-product-r1'
AUTH = '90b5f9f2'
DIFF_BASE = 'd3d5044b'
BINDING = '44c021ee'
CLOSURE = S2.CLOSURE
DECODER = S2.DECODER
MEMBERS = ('src/c2_product_runtime.c', DECODER, CLOSURE)
PROBES = ('build/nested-error-recovery-r1/projection/projection.json',)
REPAIR_FINAL = ROOT/'build/retained-callable-repair-final-r1/wplto'
REPAIR_FINAL_ELF_SHA = '815b60a5fb4baf405d5b8e14dac5ad9e593c9bf3f73877efc6b6f63499dc26a1'
REPAIR_SEED = ROOT/'build/retained-callable-repair-product-r2/wplto'
BASE = S1.BASE
bind = S1.bind
write_once = S1.write_once
sha = S1.sha
once = S1.once


def rebind():
    for name in ('HERE', 'OUT', 'BUILD', 'AUTH', 'DIFF_BASE', 'CLOSURE', 'DECODER', 'MEMBERS', 'PROBES'):
        setattr(S1, name, globals()[name])


def successor(parent):
    """The repair constructor rebase, then this card's labels and predecessor."""
    raw = S1.successor(parent)
    for old, new in [
        ("    return dict(status='PASS: RETAINED-CALLABLE REPAIR SOURCE COMPOSITION, NOT NATIVE ACCEPTANCE',",
         "    return dict(status='PASS: NESTED-ERROR RECOVERY SOURCE COMPOSITION, NOT NATIVE ACCEPTANCE',"),
        ("        name='retained-callable-repair',world=value['selected_plane_world'],",
         "        name='nested-error-recovery',world=value['selected_plane_world'],"),
        ("        (out/(name+'.retained-callable-repair.patch')).write_text(diff)",
         "        (out/(name+'.nested-error-recovery.patch')).write_text(diff)"),
        # The accepted predecessor is the repair Final, not the dirty anchor
        # whose generated sources the rebase still starts from.
        ("predecessor={n:R.bind(ROOT/'build/dirty-anchor-final-r3/wplto'/p) for n,p in",
         f"predecessor={{n:R.bind(ROOT/'{REPAIR_FINAL.relative_to(ROOT)}'/p) for n,p in"),
    ]:
        raw = once(raw, old, new)
    return raw


def main():
    if sys.argv[1:] not in (['command-probe'], ['seed']):
        raise SystemExit('command-probe | seed')
    rebind()
    if sys.argv[1:] == ['seed']:
        admission = json.loads((HERE/'preflight-admission.json').read_text())
        assert admission['status'] == 'PASS' and admission['authority'] == AUTH
        assert admission['evidence']
        for row in admission['evidence']:
            assert bind(ROOT/row['path']) == row, row['path']
        assert not BUILD.exists(), 'Seed output already exists; no implicit retry'
    assert sha(S1.ANCHOR_FINAL/'lisp65-c2-substitution-linked.prg.elf') == S1.ANCHOR_ELF_SHA
    assert sha(REPAIR_FINAL/'lisp65-c2-substitution-linked.prg.elf') == REPAIR_FINAL_ELF_SHA
    assert (REPAIR_SEED/'resident-island-seed.prg.elf').read_bytes() == \
        (REPAIR_FINAL/'lisp65-c2-substitution-linked.prg.elf').read_bytes()
    S2.successor_decoder_ok()
    captured = PARENT.capture()
    parent = PARENT.successor(captured['source'])
    assert parent == (ROOT/'build/put-kit-r4/expanded-constructor.py').read_text()
    raw = successor(parent)
    HERE.mkdir(parents=True, exist_ok=True)
    write_once(HERE/'expanded-constructor.py', raw)
    composition = dict(authority=AUTH, diff_base=DIFF_BASE, binding=BINDING,
                       base_world='retained-callable repair Final (ELF 815b60a5, D81 fdb95e71)',
                       status='SOURCE AUTHORITY AND OBJECT PROJECTION; NOT NATIVE ACCEPTANCE',
                       members=list(MEMBERS),
                       evidence=[bind(ROOT/p) for p in PROBES + (CLOSURE,)])
    write_once(HERE/'composition.json', json.dumps(composition, indent=2)+'\n')
    # The Lisp plane is the anchor plane (and the repair Final's), byte for byte.
    write_once(HERE/'plane.json', (ROOT/'build/dirty-anchor-card-r1/plane.json').read_text())
    assert (HERE/'plane.json').read_bytes() == (ROOT/'build/retained-callable-repair-r2/plane.json').read_bytes()
    if not (OUT/'setup-owned').exists():
        shutil.copytree(S1.BASE_PREFLIGHT/'setup-owned', OUT/'setup-owned')
    inherited = captured['globals']
    registration = inherited['slice_registration_receipt']
    registration = types.FunctionType(registration.__code__,
                                      {**registration.__globals__, 'HERE': HERE},
                                      registration.__name__)
    index = inherited['INDEX_PRODUCER']
    namespace = dict(__name__='__main__', __file__=__file__,
                     INJECT_SLICES=index.inject_slice_sections,
                     INJECT_SLICES_WIRING=index.WIRING,
                     REGISTER_AND_ADMIT=inherited['register_and_admit'],
                     SLICE_RECEIPT=registration)
    builtins.exec(builtins.compile(raw, str(HERE/'expanded-constructor.py'), 'exec'), namespace)


if __name__ == '__main__':
    main()
