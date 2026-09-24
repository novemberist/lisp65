"""Retained-callable repair: command admission, then one Seed. Never implicit Final.

Binding d3d5044b (top entry of docs/planning/post-2.3.0-plan.md), budget
1 Seed / 1 Final / 1 product link on the accepted dirty-anchor Final.

Nearest template: the Put-Kit constructor, the last card that changed both
native members of this card (src/c2_product_runtime.c through a commissioned
hunk projected onto the inherited generated copy, and the v2 decoder through
a successor include authority).  The inherited Put-Kit constructor is captured
exactly as the dirty-anchor producer captures it (and asserted byte-identical
to build/put-kit-r4/expanded-constructor.py), then rebased with exact, checked
seams onto the dirty-anchor world:

  BASE            build/dirty-anchor-product-r1  (the generated sources, the
                  resolved profile and the four linker scripts the anchor
                  Final consumed; the Final re-used the Seed's sources)
  predecessor ELF build/dirty-anchor-final-r3/wplto  (6aa3040c...)
  plane           the anchor plane, byte-identical (no Lisp change)
  include closure config/retained-callable-repair-native/include-closure.json
  AUTH/DIFF_BASE  e0be22c1 / d3d5044b

The cache transform and its linker allocation are not part of the anchor world
and are not part of this constructor.  Merely running command-probe never
consumes the Seed budget.
"""
import builtins
import hashlib
import json
from pathlib import Path
import shutil
import sys
import types

import code_object_cache_producer as CACHE

ROOT = CACHE.ROOT
PARENT = CACHE.PARENT
HERE = ROOT/'build/retained-callable-repair-r1'
BASE = ROOT/'build/dirty-anchor-product-r1'
BASE_PREFLIGHT = ROOT/'build/dirty-anchor-product-r1-preflight'
ANCHOR_FINAL = ROOT/'build/dirty-anchor-final-r3/wplto'
ANCHOR_ELF_SHA = '6aa3040c3f6533a94c053b7b64b932be15514d856dd05f675da771a1f1ea1811'
OUT = ROOT/'build/retained-callable-repair-product-r1-preflight'
BUILD = ROOT/'build/retained-callable-repair-product-r1'
AUTH = 'e0be22c1'
DIFF_BASE = 'd3d5044b'
CLOSURE = 'config/retained-callable-repair-native/include-closure.json'
DECODER = 'config/retained-callable-repair-native/includes/c2-stream-v2-decoder.c'
PREDECESSOR_DECODER = 'config/put-kit-native/includes/c2-stream-v2-decoder.c'
MEMBERS = ('src/c2_product_runtime.c', DECODER, CLOSURE)
PROBES = ('build/retained-callable-repair-object-probe-r2/receipt.json',)
bind = CACHE.bind
write_once = PARENT.write_once


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('constructor template population drift: '+old)
    return text.replace(old, new, 1)


def successor_decoder_ok():
    """The successor decoder is the consumed Put-Kit decoder minus one clause."""
    old = (ROOT/PREDECESSOR_DECODER).read_text()
    clause = ("                if (word != expected || !IS_BCODE((obj)word)\n"
              "                    || BCODE_IDX((obj)word) != (uint16_t)(directory_base + local))\n")
    repaired = "                if (word != expected || !IS_BCODE((obj)word))\n"
    if old.count(clause) != 1 or (ROOT/DECODER).read_text() != old.replace(clause, repaired):
        raise ValueError('successor decoder is not the commissioned phase-12 projection')
    closure = json.loads((ROOT/CLOSURE).read_text())
    rows = [r for r in closure['materialized'] if r['source']['path'] == DECODER]
    if len(rows) != 1 or rows[0]['source'] != bind(ROOT/DECODER):
        raise ValueError('successor closure does not bind the successor decoder')
    if closure['predecessor'] != bind(ROOT/'config/put-kit-native/include-closure.json'):
        raise ValueError('successor closure predecessor drift')


def successor(raw):
    """Rebase the captured Put-Kit constructor onto the dirty-anchor world."""
    comment_start = raw.index('    # Preserve every consumed producer adaptation of the accepted\n')
    comment_end = raw.index('    import re\n', comment_start)
    raw = raw[:comment_start] + '''    # Preserve every consumed producer adaptation of the accepted
    # dirty-anchor world (its Seed's generated sources, which its Final
    # consumed); apply only this card's own commissioned hunk to
    # src/c2_product_runtime.c, with exact context, since the diff base.
    # The runtime already has a generated copy in that population (copied
    # above); the hunk projects onto THAT copy.
''' + raw[comment_end:]
    for old, new in [
        ("HERE=ROOT/'build/put-kit-r4'", f"HERE=ROOT/'{HERE.relative_to(ROOT)}'"),
        ("INC.CLOSURE=ROOT/'config/put-kit-native/include-closure.json';"
         "INC.CLOSURE_SHA='598fd8c50d63792a4b9117a1e7baadbc8b04c4edc6003022cb085954603c99c9'",
         f"INC.CLOSURE=ROOT/'{CLOSURE}';INC.CLOSURE_SHA='{sha(ROOT/CLOSURE)}'"),
        ("BASE=ROOT/'build/boot-only-carrier-product-r1'\n", f"BASE=ROOT/'{BASE.relative_to(ROOT)}'\n"),
        ("BASE_PREFLIGHT=ROOT/'build/boot-only-carrier-product-r1-preflight'",
         f"BASE_PREFLIGHT=ROOT/'{BASE_PREFLIGHT.relative_to(ROOT)}'"),
        ("OUT=ROOT/'build/put-kit-product-r4-preflight'", f"OUT=ROOT/'{OUT.relative_to(ROOT)}'"),
        ("BUILD=ROOT/'build/put-kit-product-r4'", f"BUILD=ROOT/'{BUILD.relative_to(ROOT)}'"),
        ("AUTH='3bd13625'", f"AUTH='{AUTH}'"),
        # The anchor Final was linked into its own isolated directory; its
        # Seed directory (BASE) carries the byte-identical ELF under the Seed
        # name.  Bind the accepted Final by path.
        ("predecessor={n:R.bind(BASE/'wplto'/p) for n,p in",
         f"predecessor={{n:R.bind(ROOT/'{ANCHOR_FINAL.relative_to(ROOT)}'/p) for n,p in"),
        ("    return dict(status='PASS: OV_CRC16 SOURCE COMPOSITION, NOT NATIVE ACCEPTANCE',",
         "    return dict(status='PASS: RETAINED-CALLABLE REPAIR SOURCE COMPOSITION, NOT NATIVE ACCEPTANCE',"),
        ("        name='put-kit-shared-boot-index',world=value['selected_plane_world'],",
         "        name='retained-callable-repair',world=value['selected_plane_world'],"),
        ("        (out/(name+'.ov-crc16.patch')).write_text(diff)",
         "        (out/(name+'.retained-callable-repair.patch')).write_text(diff)"),
        ("    successor=ROOT/'config/put-kit-native/includes/c2-stream-v2-decoder.c'",
         f"    successor=ROOT/'{DECODER}'"),
        ("        status='PASS: COMPLETE FOUR-SCRIPT DERIVATION IDENTICAL TO THE CARRIER PREDECESSOR',",
         "        status='PASS: FOUR LINKER SCRIPTS BYTE-IDENTICAL TO THE ACCEPTED DIRTY-ANCHOR WORLD',"),
    ]:
        raw = once(raw, old, new)
    if raw.count("'e497ad71'") != 3:
        raise ValueError('Put-Kit diff base population drift')
    raw = raw.replace("'e497ad71'", repr(DIFF_BASE))
    # Explicit local-candidate provenance successor, as the cache and
    # dirty-anchor constructors: clean committed local inputs, no push.
    marker = "if __name__=='__main__':"
    local_admission = r'''# Explicit local-candidate provenance successor.
probe_source=inspect.getsource(g['command_probe'])
remote_guard="""        if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT)!=subprocess.check_output(['git','rev-parse','@{upstream}'],cwd=ROOT):
            raise ValueError('Seed source commit must be remote-visible')"""
local_guard="""        for member in R.C.load(HERE/'composition.json')['members']:
            committed=subprocess.check_output(['git','show','HEAD:'+member],cwd=ROOT)
            if committed!=(ROOT/member).read_bytes():
                raise ValueError('local candidate input is not committed: '+member)
        (HERE/'local-source-admission.json').write_bytes(R.C.canonical(dict(
            status='PASS: CLEAN COMMITTED LOCAL CANDIDATE; NOT REMOTE PUBLICATION',
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            inputs=[R.bind(ROOT/member) for member in R.C.load(HERE/'composition.json')['members']])))"""
if probe_source.count(remote_guard)!=1: raise ValueError('remote provenance predecessor drift')
probe_source=probe_source.replace(remote_guard,local_guard,1)
exec(compile(probe_source,__file__,'exec'),g)

'''
    raw = once(raw, marker, local_admission+marker)
    for stale in ('put-kit-native', 'boot-only-carrier-product-r1', 'put-kit-product-r4',
                  'build/put-kit-r4', '3bd13625', 'e497ad71'):
        if stale in raw:
            raise ValueError('stale predecessor reference after rebase: '+stale)
    return raw


def main():
    if sys.argv[1:] not in (['command-probe'], ['seed']):
        raise SystemExit('command-probe | seed')
    if sys.argv[1:] == ['seed']:
        admission = json.loads((HERE/'preflight-admission.json').read_text())
        assert admission['status'] == 'PASS' and admission['authority'] == AUTH
        assert admission['evidence']
        for row in admission['evidence']:
            assert bind(ROOT/row['path']) == row, row['path']
        assert not BUILD.exists(), 'Seed output already exists; no implicit retry'
    assert sha(ANCHOR_FINAL/'lisp65-c2-substitution-linked.prg.elf') == ANCHOR_ELF_SHA
    assert (BASE/'wplto/resident-island-seed.prg.elf').read_bytes() == \
        (ANCHOR_FINAL/'lisp65-c2-substitution-linked.prg.elf').read_bytes()
    successor_decoder_ok()
    captured = PARENT.capture()
    parent = PARENT.successor(captured['source'])
    assert parent == (ROOT/'build/put-kit-r4/expanded-constructor.py').read_text()
    raw = successor(parent)
    HERE.mkdir(parents=True, exist_ok=True)
    write_once(HERE/'expanded-constructor.py', raw)
    composition = dict(authority=AUTH, diff_base=DIFF_BASE, binding='d3d5044b',
                       status='SOURCE AUTHORITY AND OBJECT PROJECTION; NOT NATIVE ACCEPTANCE',
                       members=list(MEMBERS),
                       evidence=[bind(ROOT/p) for p in PROBES + (CLOSURE,)])
    write_once(HERE/'composition.json', json.dumps(composition, indent=2)+'\n')
    # The Lisp plane is the anchor plane, byte for byte.
    write_once(HERE/'plane.json', (ROOT/'build/dirty-anchor-card-r1/plane.json').read_text())
    if not (OUT/'setup-owned').exists():
        shutil.copytree(BASE_PREFLIGHT/'setup-owned', OUT/'setup-owned')
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
