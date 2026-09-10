#!/usr/bin/env python3
"""Commissioned £ successor of A; a seed is never an implicit final build."""
from pathlib import Path
import hashlib
import subprocess
import sys
import shutil
import tempfile
import re

import capacity_lever_a_zp_product_card as R
from evidence_era import stable_recorded_on

ROOT, P, B, A, C, F = R.ROOT, R.P, R.B, R.A, R.C, R.F
BASE = ROOT / 'build/capacity/lever-a-product-r2'
BASE_PREFLIGHT = ROOT / 'build/capacity/lever-a-product-r2-preflight'
BUILD = ROOT / 'build/pound-quasiquote-product-r1'
PREFLIGHT = ROOT / 'build/pound-quasiquote-product-r1-preflight'
EVIDENCE = ROOT / 'build/pound-quasiquote-r1'
AUTHORIZATION = '468808aa'
REF = '9c944a5aa4a155dd397ab3ede9815578cdb3a39f'
REPORT = ROOT / 'docs/planning/pound-quasiquote-product-report.md'
CHANGED = ('src/reader.c', 'src/screen.c', 'src/repl.c',
           'src/optional/c2_kernal_input_consumer.s')
HEADER = 'src/petscii_normalization.h'


def authority():
    raw = subprocess.check_output(['git', 'show', AUTHORIZATION +
        ':docs/planning/v2.0.0-pre-plan.md'], cwd=ROOT)
    assert b'9c944a5a' in raw and b'520352a6' in raw and b'budget 1/1/1' in raw
    expected = {'ELF': '7c1410f44559c30248192672002e47c291e9dc65ca84a4b9e488d6eb10eb74ad',
                'PRG': '7f02e62057f2a59e2d4b5bacb6681e9cd1cc69b2de0db8ee8a74e377f96d4509',
                'PROFILE': '89f7dc0feb4d9080e06f99f01876b17785f28d35c56691d01785074dd32ae762'}
    for name, sha in expected.items():
        assert C.bind(A.PREDECESSOR[name])['sha256'] == sha
    return dict(commit=AUTHORIZATION, patch_commit=REF, landed_base='520352a6',
        plan_sha256=hashlib.sha256(raw).hexdigest(),
        predecessor={n: C.bind(A.PREDECESSOR[n]) for n in ('ELF', 'PRG', 'PROFILE')},
        budget=dict(seed_WPLTO=1, final_C_LTO=1, product_links=1,
                    host_images=2, device_contacts=0),
        device='One combined A/£ session; separate Owner contact word required',
        acceptance='Both stimulus/cycle lanes, per-owner floors, packed quasiquote and glyph oracles')


def unchanged_vm():
    source = (ROOT / 'src/vm.c').read_bytes()
    assert source == subprocess.check_output(['git', 'show', '520352a6:src/vm.c'], cwd=ROOT)
    path = BASE / 'wplto/generated-product-sources/vm.c'
    raw = path.read_bytes()
    binding = 'input_sha256=' + path.relative_to(ROOT).as_posix() + ':' + hashlib.sha256(raw).hexdigest()
    assert A.PREDECESSOR['PROFILE'].read_text().splitlines().count(binding) == 1
    # Authored VM and materialized PID-22 carrier are distinct A authorities.
    # Neither changes here; do not reapply the historical 2b projection.
    return raw


def source_gate():
    for name in CHANGED:
        assert (ROOT / name).read_bytes() == subprocess.check_output(
            ['git', 'show', REF + ':' + name], cwd=ROOT), name
    unchanged_vm()
    for name in R.ASM:
        assert (ROOT / name).read_bytes() == subprocess.check_output(
            ['git', 'show', '520352a6:' + name], cwd=ROOT), name
    # The prepared typedef did not read the rows. Its zero-emission conversion
    # is explicit; the reader/echo implementation remains precisely the branch.
    header = (ROOT / HEADER).read_text()
    assert '1 LISP65_PETSCII_NORMALIZATION_ROWS(LISP65_QUASIQUOTE_OUTSIDE_ROW)' in header
    from native_reader_conformance import check_quasiquote_transport
    check_quasiquote_transport()
    changes = subprocess.check_output(['git', 'diff', '520352a6', '--name-only', '--', 'src'],
                                     cwd=ROOT, text=True).splitlines()
    assert set(changes) == set(CHANGED) | {HEADER}, changes
    return dict(status='PASS', adapter=C.bind(Path(__file__)),
        authored=[C.bind(ROOT / p) for p in (*CHANGED, HEADER)],
        native_changed_compiler_roots=list(CHANGED), extra_header=HEADER,
        normalization_counterexample=C.bind(EVIDENCE / 'normalization-prepared-counterexample.json'),
        normalization_claim='row-derived compile assertion plus executed actual normalizer; no input mapping',
        A_VM_and_assembly_unchanged=True)


def profile(mapping=None):
    assert mapping
    by_name = {p.name: p for p in mapping.values()}
    lines = A.PREDECESSOR['PROFILE'].read_text().splitlines()
    changes, population = [], []
    for i, line in enumerate(lines):
        if not line.startswith('input_sha256='): continue
        name, previous = line.split('=', 1)[1].rsplit(':', 1)
        before = (ROOT / name).resolve()
        if '/generated-product-sources/' in name:
            assert C.bind(before)['sha256'] == previous
            target = by_name.get(before.name, before)
        else:
            assert hashlib.sha256(subprocess.check_output(
                ['git', 'show', '520352a6:' + name], cwd=ROOT)).hexdigest() == previous
            target = mapping.get(before, before)
        digest = C.bind(target)['sha256']
        successor = ((F.WPLTO / 'generated-product-sources' / target.name).relative_to(ROOT).as_posix()
                     if target in mapping.values() else name)
        lines[i] = f'input_sha256={successor}:{digest}'
        population.append(dict(before=name, after=successor, sha256=digest))
        if digest != previous:
            changes.append(dict(predecessor=name, successor=successor, before=previous, after=digest))
    assert {row['predecessor'] for row in changes} == set(CHANGED), changes
    C.BOUND_PROFILE.write_text('\n'.join(lines) + '\n')
    assert A.features(C.BOUND_PROFILE) == A.features(A.PREDECESSOR['PROFILE'])
    return dict(predecessor=C.bind(A.PREDECESSOR['PROFILE']), successor=C.bind(C.BOUND_PROFILE),
        changes=changes, population=population, extra_header=C.bind(ROOT / HEADER),
        feature_authority=B.feature_authority())


def materialize(out):
    """Consume A's qualified generated TUs, not a retired 2b projection."""
    # Let the established producer derive its split-source keys first. Some
    # keys (e.g. the phase-03 continuation) differ from the generated basename.
    result = B.ORIGINAL_MATERIALIZE(out)
    selected = A.features(A.PREDECESSOR['PROFILE'])
    originals = [Path(p).resolve() for p in B.PRODUCT.source_list(selected)]
    assert len(originals) == len(set(originals))
    generated = out / 'generated-product-sources'
    generated.mkdir(parents=True, exist_ok=True)
    consumed = set()
    for line in A.PREDECESSOR['PROFILE'].read_text().splitlines():
        if not line.startswith('input_sha256='): continue
        name, digest = line.split('=', 1)[1].rsplit(':', 1)
        if '/generated-product-sources/' not in name: continue
        prior = ROOT / name
        raw = prior.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest, name
        matches = [p for p, target in result.items() if target.name == prior.name]
        if not matches:
            matches = [p for p in originals if p.name == prior.name]
        assert len(matches) == 1, name
        target = generated / prior.name
        target.write_bytes(raw)
        result[matches[0]] = target
        consumed.add(prior.name)
    expected = {p.name for p in (BASE / 'wplto/generated-product-sources').iterdir() if p.is_file()}
    # Included decoder bodies are not independent compiler roots. Close the
    # local include graph, and require the freshly generated body to equal A.
    pending = list(consumed)
    while pending:
        parent = pending.pop()
        for name in re.findall(r'^\s*#include\s+"([^"/]+)"',
                               (generated / parent).read_text(), re.MULTILINE):
            prior = BASE / 'wplto/generated-product-sources' / name
            if not prior.is_file() or name in consumed:
                continue
            assert (generated / name).read_bytes() == prior.read_bytes(), name
            consumed.add(name)
            pending.append(name)
    assert consumed == expected, (consumed ^ expected)
    assert {p.name for p in generated.iterdir() if p.is_file()} == expected
    assert set(result) <= set(originals)
    assert result[ROOT / 'src/vm.c'].read_bytes() == unchanged_vm()
    return result


def configure():
    R.BUILD, R.PREFLIGHT = BUILD, PREFLIGHT
    P.BASE, P.BASE_PREFLIGHT = BASE, BASE_PREFLIGHT
    P.corrected_vm = unchanged_vm
    R.authority, R.profile, R.source_gate, R.materialize = authority, profile, source_gate, materialize
    R.configure()
    for module in (F, C, C.B):
        module.DRIVER = Path(__file__).resolve()
        module.AUTHORIZATION = AUTHORIZATION
        module.FORMAT = 'pound-quasiquote-r1'
        module.STATUS = 'PENDING: POUND QUALIFICATION'
        module.REPORT = REPORT
    C.B.HEADER_ROOTS = (HEADER,)


def preflight():
    """Bind the plane before asking its split-source generator to consume it."""
    configure()
    assert not C.INVOCATION.exists() and not BUILD.exists(), 'product budget already entered'
    toolchain = C.B.toolchain_identity()
    # Configuration consumes features before the successor source projection
    # exists. Bootstrap only from the accepted profile, then replace it below
    # with the fully derived successor input bindings (features stay equal).
    if not C.BOUND_PROFILE.exists():
        shutil.copyfile(A.PREDECESSOR['PROFILE'], C.BOUND_PROFILE)
    if not C.PLANE.exists(): shutil.copytree(A.PREDECESSOR['PLANE'], C.PLANE)
    for name in ('projected-ownership-contract.json', 'projected-full-map-authority.json'):
        source, target = BASE_PREFLIGHT / name, PREFLIGHT / name
        if not target.exists(): shutil.copyfile(source, target)
        assert source.read_bytes() == target.read_bytes()
    leaf = C.B.PREV.CARD.CARD2.R2.CARD
    world = leaf.product_world_identity()
    assert world['selected_plane_world']['product_build_id'] == '0x4a1713ab'
    assert world['selected_plane_world']['banner'] == 'WORKBENCH 2.0.0'
    plane = C.load(A.PREDECESSOR['PLANE_RECEIPT'])
    plane.update(format='pound-quasiquote-r1-plane', recorded_on=stable_recorded_on(F.PLANE_RECEIPT),
        status='PASS: ACCEPTED A PLANE BOUND UNCHANGED', authority=authority(),
        product=C.bind(C.PLANE / 'product/substitution-artifacts.json'),
        profile=C.bind(C.PLANE / 'candidate-profile.json'),
        contract=C.bind(C.PLANE / 'c2-lite-execution-contract.json'),
        header=C.bind(C.PLANE / 'c2_lite_static_plane.h'),
        bank2=C.bind(C.PLANE / 'v6-semantics/bank2-static-code.bin'),
        product_world_identity=world, accounting=dict(seed_WPLTO=0, final_C_LTO=0, product_links=0))
    F.PLANE_RECEIPT.write_bytes(C.canonical(plane))
    configuration = leaf.configuration_gate()
    directory = Path(tempfile.mkdtemp(prefix='bound-source-population-', dir=PREFLIGHT))
    mapping = materialize(directory)
    profile_value = profile(mapping)
    value = dict(format='pound-quasiquote-r1-preflight',
        recorded_on=stable_recorded_on(F.PREFLIGHT_RECEIPT), authority=authority(),
        world=world, toolchain=toolchain, profile=profile_value,
        configuration=configuration, source_population=B.source_population(),
        semantic=source_gate(), instrument_registry=C.PRODUCT.f011_status_inventory_registration(),
        accounting=dict(seed_WPLTO=0, final_C_LTO=0, product_links=0, host_images=0, device_contacts=0))
    F.PREFLIGHT_RECEIPT.write_bytes(C.canonical(value))
    print('£ preflight PASS; A plane bound before materialization, no compiler or device invocation')


def main():
    B.configure = A.configure = configure
    if sys.argv[1:] == ['preflight']:
        preflight()
    elif sys.argv[1:] == ['seed']:
        B.produce_seed()
    else:
        raise SystemExit('Choose preflight or seed; no implicit final product build')


if __name__ == '__main__': main()
