"""Compose the admitted Set-A resident plane; never invoke a native compiler.

The separately delivered defstruct package is bound in this receipt, not
silently inserted into one of the six resident roles.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil

import c2_substitution_artifacts as SUB
import c2_lite_v6_product_probe as V6
import c2_v17_ide_idle_blink_product_card as PT
from evidence_era import stable_recorded_on

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'build/transient-retirement-product-r1-preflight/setup-owned/static-plane/narrow-static'
COMPOSITION = ROOT/'build/definition-group-composition-r6/receipt.json'


def load(p):
    return json.loads(p.read_text())


def write(p, value):
    p.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def bind(p):
    p = p.resolve()
    raw = p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)), bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True, type=Path)
    out = ap.parse_args().out.resolve()
    composition = load(COMPOSITION)
    assert composition['baseline_relocation_equivalent']
    assert composition['package']['baseline_c2i_byteidentical']
    assert composition['total_bank2_delta'] == 160
    for row in (composition['manifest'], composition['authored'],
                composition['consumed'], composition['projection'],
                composition['package']['candidate']):
        assert bind(ROOT/row['path']) == row, row['path']
    assert not out.exists(), 'preserve composed worlds'
    shutil.copytree(BASE, out, ignore=shutil.ignore_patterns(
        'product', 'v6-semantics', 'stdlib-p0.*'))
    candidate = (ROOT/composition['manifest']['path']).parent
    for p in candidate.glob('stdlib-p0.*'):
        shutil.copyfile(p, out/p.name)
    predecessor = load(BASE/'product/substitution-artifacts.json')
    roles = ('stdlib-p0', 'ide', 'idex', 'm65d', 'buffer', 'lcc')
    assert len(predecessor['manifests']) == len(roles)
    specs = []
    for role, row in zip(roles, predecessor['manifests']):
        prior = ROOT/row['path']
        assert bind(prior) == row
        target = out/'stdlib-p0.manifest.json' if role == 'stdlib-p0' else prior
        specs.append((role, 'stdlib' if role == 'stdlib-p0' else role, target))
    SUB.BUILD = out/'product'
    SUB.SPECS = tuple(specs)
    emitted = SUB.build()
    total = sum(load(p)['code_bytes'] for _, _, p in specs)
    before = load(BASE/'candidate-profile.json')['bank2_static_code']['bytes']
    assert total-before == composition['delta']['code_bytes'] == 153
    V6.OUT = out/'v6-semantics'
    V6.OUT.mkdir()
    V6.PRODUCT_IDENTITY = out/'product/substitution-artifacts.json'
    V6.STATIC_CODE_BYTES = total
    V6.A.SPECS = tuple(specs)
    static = V6.host_semantics()['static_bank2']
    assert static['code_bytes'] == total
    header, count = re.subn(
        r'(#define LISP65_C2_LITE_STATIC_CODE_BYTES )\d+(UL)',
        lambda m: m[1]+str(total)+m[2],
        (BASE/'c2_lite_static_plane.h').read_text())
    assert count == 1
    (out/'c2_lite_static_plane.h').write_text(header)
    contract = load(BASE/'c2-lite-execution-contract.json')
    contract['physical_planes']['code'].update(
        static_use_bytes=total, gross_headroom_bytes=65536-total)
    write(out/'c2-lite-execution-contract.json', contract)
    profile = load(BASE/'candidate-profile.json')
    profile.update(recorded_on=stable_recorded_on(out/'candidate-profile.json'),
        product_build_id=emitted['product_build_id_hex'],
        **{k: emitted[k] for k in ('images', 'entries', 'resolutions', 'roots')})
    profile['bank2_static_code'] = dict(bytes=total,
        sha256=static['code_sha256'], headroom_bytes=65536-total)
    profile['direct_entry_refs'] = PT.L94.direct_entry_census(out/'product')
    profile['authority'].update(
        product_manifest=str((out/'product/substitution-artifacts.json').relative_to(ROOT)),
        compiled_stdlib_manifest=str((out/'stdlib-p0.manifest.json').relative_to(ROOT)),
        bank2_static_plane=str((out/'v6-semantics/bank2-static-code.bin').relative_to(ROOT)),
        successor=dict(kind='definitions-set-a', authority='c97a8e60',
                       source=bind(COMPOSITION), rule='producer-declared definition groups only'))
    write(out/'candidate-profile.json', profile)
    shutil.copyfile(out/'stdlib-p0.h', out/'workbench/stdlib-p0.h')
    write(out/'set-a-plane-receipt.json', dict(
        status='PASS: HOST PLANE COMPOSITION; NOT SEED ADMISSION',
        authority='c97a8e60', composition=bind(COMPOSITION),
        producer=bind(Path(__file__)), product_build_id=emitted['product_build_id_hex'],
        plane_bytes=total, plane_delta=total-before,
        product=bind(out/'product/substitution-artifacts.json'),
        baseline_product=bind(BASE/'product/substitution-artifacts.json'),
        bank2=bind(out/'v6-semantics/bank2-static-code.bin'),
        resident_delta=153, delivered_package_delta=7, total_bank2_delta=160,
        required_defstruct_package=composition['package']['candidate'],
        budget=dict(seed=0, final=0, product_link=0)))
    print('PASS: Set-A six-role plane; resident +153, delivered defstruct +7; no native build')


if __name__ == '__main__':
    main()
