"""Explicit successor of the accepted carrier command constructor.

No historical inputs are edited. The inherited constructor is captured
before execution, then rebased with exact, checked seams. Seed remains
blocked until its complete SHA-bound preflight admission exists.
"""
import ast
import builtins
import hashlib
import inspect
import json
from pathlib import Path
import re
import shutil
import sys
import types

import boot_only_carrier_producer as CARRIER
import put_kit_objects as OBJECTS

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'build/put-kit-r4'
BASE = ROOT / 'build/boot-only-carrier-product-r1'
OUT = ROOT / 'build/put-kit-product-r4-preflight'
BUILD = ROOT / 'build/put-kit-product-r4'
AUTH = '3bd13625'
DIFF_BASE = 'e497ad71'
CLOSURE = ROOT / 'config/put-kit-native/include-closure.json'


def bind(path):
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                sha256=OBJECTS.sha(path))


def once(text, before, after):
    return OBJECTS.once(text, before, after)


def write_once(path, text):
    if path.exists():
        if path.read_text() != text:
            raise ValueError('immutable producer input changed: ' + str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def capture():
    """The old constructor's existing receipts must verify, never change."""
    class Captured(Exception):
        pass
    result = {}
    original = CARRIER.inner
    argv = sys.argv[:]
    def intercept(raw):
        result['source'] = original(raw)
        # Caller is compile_successor; its caller is the inherited main.
        result['globals'] = inspect.currentframe().f_back.f_back.f_globals
        raise Captured()
    try:
        CARRIER.inner = intercept
        sys.argv = [str(CARRIER.TEMPLATE), 'command-probe']
        try:
            CARRIER.main()
        except Captured:
            pass
    finally:
        CARRIER.inner = original
        sys.argv = argv
    assert set(result) == {'source', 'globals'}
    return result


def successor(raw):
    changes = {'build/boot-only-carrier-r1': 'build/put-kit-r4',
               'build/boot-only-carrier-product-r1': 'build/put-kit-product-r4',
               'build/ov-crc16-product-r1': 'build/boot-only-carrier-product-r1',
               '4cd7eac3': AUTH, '523c31e0': DIFF_BASE}
    raw = re.sub('|'.join(re.escape(k) for k in sorted(changes, key=len, reverse=True)),
                 lambda m: changes[m[0]], raw)
    raw = once(raw, "INC.CLOSURE=ROOT/'config/boot-name-index-native/include-closure.json';"
               "INC.CLOSURE_SHA='2681fb3e89deb5c70138e1cae6a7e5c00b575a211cf5b3e07d7bf5072debc572'",
               f"INC.CLOSURE=ROOT/'config/put-kit-native/include-closure.json';INC.CLOSURE_SHA='{OBJECTS.sha(CLOSURE)}'")
    raw = once(raw, "CHANGED=('src/vm_boot_overlay.c', 'src/vm_runtime_overlay.c')",
               "CHANGED=('src/c2_product_runtime.c',)")
    matches = re.findall(r'^    expected=(\{[^\n]+\})$', raw, re.M)
    assert len(matches) == 1
    assert ast.literal_eval(matches[0]) == {'src/vm_boot_overlay.c', 'src/vm_runtime_overlay.c'}
    raw = once(raw, 'expected=' + matches[0], "expected={'src/c2_product_runtime.c'}")
    raw = once(raw, "for name,source in (('vm_boot_overlay.c','src/vm_boot_overlay.c'),\n"
               "                        ('vm_runtime_overlay.c','src/vm_runtime_overlay.c')):",
               "for name,source in (('c2_product_runtime.c','src/c2_product_runtime.c'),):")
    raw = once(raw, "allowed=set(proof['changed_members'])|{'vm_boot_overlay.c','vm_runtime_overlay.c'}",
               "allowed=set(proof['changed_members'])|{'c2_product_runtime.c'}")
    raw = once(raw, '    INC.materialize(generated)',
               "    decoder=generated/'c2-stream-v2-decoder.c'\n"
               "    before=BASE/'wplto/generated-product-sources/c2-stream-v2-decoder.c'\n"
               "    if decoder.read_bytes()!=before.read_bytes():\n"
               "        raise ValueError('decoder predecessor projection drift')\n"
               "    successor=ROOT/'config/put-kit-native/includes/c2-stream-v2-decoder.c'\n"
               "    decoder.write_bytes(successor.read_bytes())\n"
               "    (out/'decoder-successor.json').write_bytes(R.C.canonical(dict(\n"
               "        authority=AUTH, predecessor=R.bind(before), source=R.bind(successor),\n"
               "        consumed=R.bind(decoder))))\n"
               '    INC.materialize(generated)')
    # Feature and carrier were already introduced by the accepted world.
    raw = once(raw, "text=CARRIER.add_feature((BASE/'wplto/resolved-profile.txt').read_text())",
               "text=(BASE/'wplto/resolved-profile.txt').read_text()")
    raw = once(raw, "R.C.BOUND_PROFILE.write_text(CARRIER.add_feature('\\n'.join(lines)+'\\n'))",
               "R.C.BOUND_PROFILE.write_text('\\n'.join(lines)+'\\n')")
    carrier_line = "    injected['c2-substitution.ld']=CARRIER.LINKER.transform(injected['c2-substitution.ld'])\n"
    raw = once(raw, carrier_line, '')
    raw = once(raw, '    predecessor={name:', carrier_line + '    predecessor={name:')
    raw = once(raw, 'PASS: PREDECESSOR DERIVATION IDENTICAL BEFORE THE EXPLICIT CARRIER ADDITION',
               'PASS: COMPLETE FOUR-SCRIPT DERIVATION IDENTICAL TO THE CARRIER PREDECESSOR')
    raw = raw.replace('boot-only-carrier-placement', 'put-kit-shared-boot-index')
    return raw


def main():
    if sys.argv[1:] not in (['command-probe'], ['seed']):
        raise SystemExit('command-probe | seed')
    if sys.argv[1:] == ['seed']:
        admission = HERE / 'preflight-admission-r2.json'
        if not admission.is_file():
            raise SystemExit('Seed blocked: full Put-Kit admission absent')
        evidence = json.loads(admission.read_text())
        assert evidence['status'] == 'PASS' and evidence['authority'] == AUTH
        assert evidence['evidence']
        for row in evidence['evidence']:
            assert bind(ROOT / row['path']) == row, 'changed preflight evidence'
        if BUILD.exists():
            raise SystemExit('Seed budget entered; no implicit retry')
    result = capture()
    raw = successor(result['source'])
    HERE.mkdir(parents=True, exist_ok=True)
    write_once(HERE / 'expanded-constructor.py', raw)
    composition = dict(authority=AUTH, diff_base=DIFF_BASE,
                       status='SOURCE AUTHORITY AND HOST PRICE; NOT NATIVE ACCEPTANCE',
                       members=['src/c2_product_runtime.c',
                                'config/put-kit-native/includes/c2-stream-v2-decoder.c'],
                       evidence=[bind(ROOT / p) for p in (
                           'build/put-kit-objects-r1/receipt.json',
                           'build/put-kit-host-r1/receipt.json',
                           'config/put-kit-native/include-closure.json')])
    write_once(HERE / 'composition.json', json.dumps(composition, indent=2) + '\n')
    plane = ROOT / 'build/boot-only-carrier-product-r1-preflight/setup-owned/static-plane/narrow-static/set-a-plane-receipt.json'
    write_once(HERE / 'plane.json', plane.read_text())
    if not (OUT / 'setup-owned').exists():
        shutil.copytree(plane.parents[2], OUT / 'setup-owned')
    inherited = result['globals']
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
    builtins.exec(builtins.compile(raw, str(HERE / 'expanded-constructor.py'), 'exec'), namespace)


if __name__ == '__main__':
    main()
