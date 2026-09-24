"""Retained-callable repair, Seed 2: member 2 alone. Command admission, then one Seed.

Reviewer rebinding 2026-09-23 (top of docs/planning/post-2.3.0-plan.md):
member 1 withdrawn, budget 2 Seeds / 1 Final / 1 link.  This module reuses
the Seed-1 constructor rebase (retained_callable_repair_producer.successor)
unchanged and only rebinds its constants:

  AUTH/DIFF_BASE  dafc1f47 / d3d5044b  (git diff d3d5044b -- src lib shows
                  member 2 alone)
  include closure config/retained-callable-repair-r2-native/ (decoder
                  byte-identical to the anchor's consumed Put-Kit decoder)
  output          build/retained-callable-repair-r2, -product-r2(-preflight)

Seed 1 (build/retained-callable-repair-product-r1) stays as the halted Seed.
"""
import builtins
import json
import shutil
import sys
import types
from pathlib import Path

import retained_callable_repair_producer as S1

ROOT = S1.ROOT
PARENT = S1.PARENT
HERE = ROOT/'build/retained-callable-repair-r2'
OUT = ROOT/'build/retained-callable-repair-product-r2-preflight'
BUILD = ROOT/'build/retained-callable-repair-product-r2'
AUTH = 'dafc1f47'
DIFF_BASE = 'd3d5044b'
CLOSURE = 'config/retained-callable-repair-r2-native/include-closure.json'
DECODER = 'config/retained-callable-repair-r2-native/includes/c2-stream-v2-decoder.c'
MEMBERS = ('src/c2_product_runtime.c', DECODER, CLOSURE)
PROBES = ('build/retained-callable-repair-object-probe-r3/receipt.json',)
BASE = S1.BASE
bind = S1.bind
write_once = S1.write_once
sha = S1.sha


def successor_decoder_ok():
    """Member 1 withdrawn: the successor decoder is the consumed decoder, byte for byte."""
    if (ROOT/DECODER).read_bytes() != (ROOT/S1.PREDECESSOR_DECODER).read_bytes():
        raise ValueError('r2 decoder is not the consumed Put-Kit decoder')
    if (ROOT/DECODER).read_bytes() != (BASE/'wplto/generated-product-sources/c2-stream-v2-decoder.c').read_bytes():
        raise ValueError('r2 decoder is not the anchor-consumed decoder')
    closure = json.loads((ROOT/CLOSURE).read_text())
    rows = [r for r in closure['materialized'] if r['source']['path'] == DECODER]
    if len(rows) != 1 or rows[0]['source'] != bind(ROOT/DECODER):
        raise ValueError('r2 closure does not bind the r2 decoder')
    if closure['predecessor'] != bind(ROOT/'config/retained-callable-repair-native/include-closure.json'):
        raise ValueError('r2 closure predecessor drift')


def rebind():
    for name in ('HERE', 'OUT', 'BUILD', 'AUTH', 'DIFF_BASE', 'CLOSURE', 'DECODER', 'MEMBERS', 'PROBES'):
        setattr(S1, name, globals()[name])


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
        assert not BUILD.exists(), 'Seed 2 output already exists; no third Seed'
    assert sha(S1.ANCHOR_FINAL/'lisp65-c2-substitution-linked.prg.elf') == S1.ANCHOR_ELF_SHA
    successor_decoder_ok()
    captured = PARENT.capture()
    parent = PARENT.successor(captured['source'])
    assert parent == (ROOT/'build/put-kit-r4/expanded-constructor.py').read_text()
    raw = S1.successor(parent)
    HERE.mkdir(parents=True, exist_ok=True)
    write_once(HERE/'expanded-constructor.py', raw)
    composition = dict(authority=AUTH, diff_base=DIFF_BASE, binding='d3d5044b',
                       rebinding='reviewer decision 2026-09-23: member 1 withdrawn, replacement Seed bound',
                       status='SOURCE AUTHORITY AND OBJECT PROJECTION; NOT NATIVE ACCEPTANCE',
                       members=list(MEMBERS),
                       evidence=[bind(ROOT/p) for p in PROBES + (CLOSURE,)])
    write_once(HERE/'composition.json', json.dumps(composition, indent=2)+'\n')
    write_once(HERE/'plane.json', (ROOT/'build/dirty-anchor-card-r1/plane.json').read_text())
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
