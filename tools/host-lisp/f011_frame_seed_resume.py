#!/usr/bin/env python3
"""Authorized seed relink only; never execute another WPLTO implicitly."""
import argparse
import hashlib
import json
import shutil
import tempfile
import subprocess
from pathlib import Path

import f011_frame_diagnostic_card as D

P = D.C.PRODUCT
ROOT = D.ROOT
OUT = D.WPLTO
SEED = OUT / 'resident-island-seed.prg'
LTO = Path(str(SEED) + '.lto.o')
FROZEN = '2d9090b882b73b3e54284bf030f0b7fc301324b5f78f1f9257e26e751f03af36'
ARCHIVE = D.BUILD / 'failed-seed-frozen'
RECEIPT = D.BUILD / 'seed-only-resume.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gate():
    source = Path(P.__file__).read_text()
    start = source.index('ASSERT(ADDR(.lisp65_c2_convergence_state)')
    body = source[start:source.index('simultaneous-live relation drift', start)]
    assert 'SIZEOF(.lisp65_c2_static_stack) == 6' not in body
    assert 'SIZEOF(.lisp65_c2_static_stack) > 0' in body
    assert '<= ADDR(.lisp65_c2_fixed_bank0)' in body
    def valid(start, size, next_owner):
        return start == 0xc074 and size > 0 and size <= 12 and start + size <= next_owner
    assert all(valid(0xc074, n, 0xc080) for n in (3, 6, 12))
    cases = {'missing': (0xc074, 0, 0xc080),
             'overflow': (0xc074, 13, 0xc080),
             'moved': (0xc075, 3, 0xc080),
             'overlap': (0xc074, 3, 0xc076)}
    assert not any(valid(*row) for row in cases.values())
    assert digest(LTO) == FROZEN
    return {'status': 'PASS', 'source': digest(Path(P.__file__)),
            'negative_controls': list(cases), 'frozen_lto': FROZEN,
            'claim': 'source-bound envelope model; final ELF check remains due'}


def resume():
    proof = gate()
    assert not SEED.exists() and not Path(str(SEED)+'.elf').exists()
    assert not RECEIPT.exists() and not ARCHIVE.exists()
    ARCHIVE.mkdir()
    for path in OUT.glob('resident-island-seed.prg.*'):
        if path.is_file():
            shutil.copy2(path, ARCHIVE / path.name)
    shutil.copy2(OUT/'c2-substitution.ld', ARCHIVE/'c2-substitution.ld')
    D.configure()
    D.C.configure = D.configure
    original_compile = P.compile_link
    original_run = P.run
    original_link = P.run_link_with_exact_orphan_wrapper
    link_module = D.C.B.PREV.CARD.CARD2.R2.CARD.BASE.CHAIN.LINK
    original_materialize = link_module.materialize_candidate_sources
    existing = OUT/'generated-product-sources'
    snapshot = {p.name: digest(p) for p in existing.iterdir() if p.is_file()}
    calls = []

    def reuse_sources(out):
        test = D.BUILD/'seed-resume-source-proof'
        assert not test.exists()
        mapping = original_materialize(test)
        regenerated = {p.name: digest(p) for p in (test/'generated-product-sources').iterdir() if p.is_file()}
        assert regenerated == snapshot, 'generated source world changed'
        return {s: existing/p.name for s, p in mapping.items()}

    def no_compile(command, *args, **kwargs):
        # compile_link always re-merges bitcode even with a complete prefix.
        # The frozen native object is the only input allowed to replace it.
        assert Path(str(command[0])).name == 'llvm-link', 'compiler execution forbidden'
        assert command[-2] == '-o' and command[-1].endswith('/combined-c.bc')

    def native_link(out, target, command):
        assert target == SEED and digest(LTO) == FROZEN
        combined = [x for x in command if x.endswith('/combined-c.bc')]
        assert len(combined) == 1
        command = [str(LTO.relative_to(ROOT)) if x == combined[0] else x
                   for x in command if not x.startswith('-Wl,--lto-obj-path=')]
        assert not any(x.endswith(('.bc', '.c')) for x in command)
        calls.append(command)
        original_link(out, target, command)
        assert digest(LTO) == FROZEN

    def seed_only(out, name, headers, artifacts, **kwargs):
        if name != SEED.name:
            raise RuntimeError('seed-only resume reached final link: explicit boundary')
        objects = OUT/'.canonical-objects-resident-island-seed'
        copied = OUT/'.frozen-native-resume-objects'
        assert not copied.exists()
        copied.mkdir()
        prefix = []
        for path in sorted(objects.glob('*.o')):
            shutil.copy2(path, copied/path.name)
            prefix.append({'name':path.name, 'bytes':path.stat().st_size, 'sha256':digest(path)})
        P.run = no_compile
        P.run_link_with_exact_orphan_wrapper = native_link
        try:
            target = original_compile(out, name, headers, artifacts,
                deterministic_object_prefix=prefix,
                deterministic_object_directory=copied, **kwargs)
        finally:
            P.run = original_run
            P.run_link_with_exact_orphan_wrapper = original_link
        RECEIPT.write_text(json.dumps({'role':'DIAGNOSTIC-EVIDENCE-ONLY',
            'gate':proof, 'new_WPLTO':0, 'seed_links':1, 'product_links':0,
            'command':calls, 'seed_elf_sha256':digest(Path(str(target)+'.elf')),
            'lto_after':digest(LTO)}, indent=2)+'\n')
        raise SystemExit(0)

    link_module.materialize_candidate_sources = reuse_sources
    P.compile_link = seed_only
    try:
        D.C.B.child('_produce')
    finally:
        P.compile_link = original_compile
        link_module.materialize_candidate_sources = original_materialize


def check_linked(complete=False):
    """Run converted seed gates under the actual producer configuration."""
    assert digest(LTO) == FROZEN
    assert SEED.exists() and Path(str(SEED)+'.elf').exists()
    before = {p.name:digest(p) for p in (SEED, Path(str(SEED)+'.elf'), LTO)}
    D.configure()
    D.C.configure = D.configure
    original = P.single_link
    link_module = D.C.B.PREV.CARD.CARD2.R2.CARD.BASE.CHAIN.LINK
    materializer = link_module.materialize_candidate_sources
    def reuse(out):
        existing = OUT/'generated-product-sources'
        with tempfile.TemporaryDirectory(prefix='seed-source-check-', dir=D.BUILD) as temporary:
            proof_root = Path(temporary)
            mapping = materializer(proof_root)
            assert {p.name:digest(p) for p in existing.iterdir() if p.is_file()} == {
                p.name:digest(p) for p in (proof_root/'generated-product-sources').iterdir() if p.is_file()}
        return {s:existing/p.name for s,p in mapping.items()}
    link_module.materialize_candidate_sources = reuse
    invoked = []
    def inspect(out, *args, **kwargs):
        assert out == OUT
        invoked.append(True)
        if complete:
            from dataclasses import replace
            from elf_truth import ElfTruth
            truth = ElfTruth.read(D.ELF, llvm_readobj=P.TOOLCHAIN/'llvm-readobj')
            leaf = P.FIXED_BLOCK_LEAF
            # final facade setup supplies the real successor leaf addresses.
            P.fixed_facade_gate(out, D.PRG, 'final')
            stack = truth.section(leaf.OWNED_STACK_SECTION)
            rejected = []
            for label, changes in [('missing-extent', {'bytes':0}),
                                   ('overflow', {'bytes':13}),
                                   ('moved', {'address':stack.address+1})]:
                mutant = ElfTruth(sections=[replace(s, **changes) if s.name==stack.name else s
                                           for s in truth.sections],
                                  symbols=truth.symbols, relocations=truth.relocations)
                try:
                    leaf.audit_truth(mutant, require_hot_bss=True, full_map_ownership=True)
                except (leaf.GateError, leaf.ElfTruthError):
                    rejected.append(label)
                else:
                    raise RuntimeError('static-stack mutation survived: '+label)
            # No compile_link call: standard artifact/CRC publication only.
            P.finish_single_link(out, D.PRG, D.PROFILE)
            (D.BUILD/'artifact-completion.json').write_text(json.dumps({
                'role':'DIAGNOSTIC-EVIDENCE-ONLY','new_compiler_calls':0,'new_links':0,
                'static_stack_mutations':rejected,
                'ELF':digest(D.ELF),'PRG':digest(D.PRG),
                'seed_after':{p.name:digest(p) for p in (SEED,Path(str(SEED)+'.elf'),LTO)}},indent=2)+'\n')
            assert before == {p.name:digest(p) for p in (SEED,Path(str(SEED)+'.elf'),LTO)}
            print('DIAGNOSTIC ARTIFACT COMPLETION PASS; no compiler/link; qualification pending')
            raise SystemExit(0)
        inventory = P.final_section_inventory_gate(out, SEED)
        partition = P.lto_partition_metadata_gate(out, SEED)
        negative = P._final_section_inventory_model_selftest()
        after = {p.name:digest(p) for p in (SEED, Path(str(SEED)+'.elf'), LTO)}
        assert before == after
        RECEIPT.write_text(json.dumps({'role':'DIAGNOSTIC-EVIDENCE-ONLY',
            'gate':gate(), 'new_WPLTO':0, 'seed_links':1, 'product_links':0,
            'inventory':inventory, 'partition':partition, 'negative':negative,
            'pair_before':before, 'pair_after':after}, indent=2)+'\n')
        print('SEED GATES PASS; frozen LTO and seed pair unchanged; final link not run')
        raise SystemExit(0)
    P.single_link = inspect
    try:
        try:
            D.C.B.child('_produce')
        except SystemExit as stop:
            assert stop.code == 0 and invoked == [True]
    finally:
        P.single_link = original
        link_module.materialize_candidate_sources = materializer
    assert invoked == [True]


def final_product():
    """One explicitly authorized final C/LTO invocation; reuse seed only."""
    stamp = D.BUILD/'final-product-invocation.json'
    assert not stamp.exists() and not D.ELF.exists() and not D.PRG.exists()
    assert not (OUT/'.canonical-objects-lisp65-c2-substitution-linked').exists()
    assert not subprocess.check_output(['git','status','--porcelain'], cwd=ROOT).strip()
    head = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT).decode().strip()
    upstream = subprocess.check_output(['git','rev-parse','@{upstream}'], cwd=ROOT).decode().strip()
    assert head == upstream, 'producer commit must be remote-visible'
    seed_files = (SEED, Path(str(SEED)+'.elf'), LTO, Path(str(SEED)+'.map'))
    frozen = {p.name:digest(p) for p in seed_files}
    assert digest(LTO) == FROZEN
    assert frozen[SEED.name+'.elf'] == 'd9016f62f3d9a68404859d15908543bbdf257ec3fdd8a58cef9b473a849d248a'
    stamp.write_text(json.dumps({'authorization':'Alex: one final C/LTO and product link; reuse seed',
        'commit':head, 'upstream':upstream, 'seed':frozen,
        'role':'DIAGNOSTIC-EVIDENCE-ONLY', 'seed_builds':0,
        'final_C_LTO_invocations_authorized':1, 'product_links_authorized':1},indent=2)+'\n')
    D.configure()
    D.C.configure = D.configure
    link_module = D.C.B.PREV.CARD.CARD2.R2.CARD.BASE.CHAIN.LINK
    materializer = link_module.materialize_candidate_sources
    original_compile = P.compile_link
    calls = []
    def reuse(out):
        existing = OUT/'generated-product-sources'
        with tempfile.TemporaryDirectory(prefix='final-source-check-', dir=D.BUILD) as temporary:
            root = Path(temporary)
            mapping = materializer(root)
            assert {p.name:digest(p) for p in existing.iterdir() if p.is_file()} == {
                p.name:digest(p) for p in (root/'generated-product-sources').iterdir() if p.is_file()}
        return {s:existing/p.name for s,p in mapping.items()}
    def compile_final(out, name, headers, artifacts, **kwargs):
        assert out == OUT and {p.name:digest(p) for p in seed_files} == frozen
        calls.append(name)
        if name == SEED.name:
            assert calls == [SEED.name]
            P.final_section_inventory_gate(out, SEED)
            P.lto_partition_metadata_gate(out, SEED)
            return SEED
        assert calls == [SEED.name, D.PRG.name], 'extra compile/link forbidden'
        return original_compile(out, name, headers, artifacts, **kwargs)
    link_module.materialize_candidate_sources = reuse
    P.compile_link = compile_final
    try:
        try:
            D.C.B.child('_produce')
        except SystemExit as stop:
            assert stop.code == 0
    finally:
        P.compile_link = original_compile
        link_module.materialize_candidate_sources = materializer
        after = {p.name:digest(p) for p in seed_files}
        (D.BUILD/'final-product-attempt.json').write_text(json.dumps({
            'calls':calls,'seed_before':frozen,'seed_after':after,
            'ELF_present':D.ELF.exists(),'PRG_present':D.PRG.exists(),
            'role':'DIAGNOSTIC-EVIDENCE-ONLY'},indent=2)+'\n')
        assert after == frozen


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['check', 'resume', 'check-linked', 'final-product', 'complete-artifacts'])
    action = parser.parse_args().action
    if action == 'check':
        print(json.dumps(gate(), indent=2))
    elif action == 'check-linked':
        check_linked()
    elif action == 'final-product':
        final_product()
    elif action == 'complete-artifacts':
        check_linked(complete=True)
    else:
        resume()
