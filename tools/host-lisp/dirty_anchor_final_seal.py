"""Close the one Final against its Seed, exact-HEAD source run and existing medium."""
import json
from pathlib import Path
import subprocess
import sys
import legacy_ide_delivery as MEDIA
from dirty_anchor_producer import ROOT
from dirty_anchor_receipt_seal import binding

H = ROOT/'build/dirty-anchor-final-r3'

def main():
    inputs = []
    def verify(row):
        actual = binding((ROOT/row['path']).resolve())
        assert actual['sha256'] == row['sha256'], row['path']
        if 'bytes' in row: assert actual['bytes'] == row['bytes'], row['path']
        return actual
    def load(path):
        p = ROOT/path
        inputs.append(binding(p))
        return json.loads(p.read_text())
    pre = load('tests/bytecode/dialect-v2/evidence/architecture-blocks/dirty-anchor-pre-final-20260923.json')
    for row in pre['evidence'] + pre['receipt_copies']: verify(row)
    seed = load('config/dirty-anchor-seed.json')
    assert seed['status'] == 'PASS: EXECUTED DIRTY-ANCHOR SEED'
    for row in seed['inputs']: verify(row)
    final = load('build/dirty-anchor-final-r3/final-identity.json')
    assert final['status'] == 'PASS' and final['ELF_byteidentical']
    for row in final['seed'] + final['final']: verify(row)
    for old,new in zip(final['seed'][:3],final['final'][:3]):
        assert old['sha256'] == new['sha256']
    assert verify(final['Bank2_seed'])['sha256'] == verify(final['Bank2_final'])['sha256']
    assert final['budget'] == dict(seed=1, final=1, link=1)
    attempt = load('build/dirty-anchor-final-r3/final-attempt.json')
    assert attempt == dict(calls=['reused-seed','final'],seed_rebuilds=0,final=1)
    invocation = load('build/dirty-anchor-final-r3/final-invocation.json')
    assert invocation['budget'] == dict(seed=0,final=1,link=1)
    consumed = load('build/dirty-anchor-final-r3/final-command-consumption.json')
    assert consumed['status'] == 'PASS' and consumed['commands_consumed'] == 75
    verify(consumed['admission'])
    source = load('build/dirty-anchor-check-source-r1/receipt.json')
    assert source['target'] == 'make -k check-source'
    assert source['exit_code'] == source['changed_protected_files'] == 0
    assert not source['changed_files'] and not source['changed_sealed_artifacts']
    assert source['head_before'] == source['head_after'] == '17a12ed36091036f51c1134222e8cd8e46a4a0bb'
    verify(source['log'])
    assert load('build/dirty-anchor-source-qualification-r1/full-source-run.json') == source
    inputs.append(binding(ROOT/'build/dirty-anchor-source-final-r1.log'))
    medium = load('build/dirty-anchor-seed-medium-r1/packed-receipt.json')
    extended = load('build/dirty-anchor-seed-medium-r1/extended-resident.json')
    assert extended['status'] == 'PASS'
    for row in [medium['medium'],medium['elf'],*medium['artifacts'].values(),
                extended['elf'],extended['prefix'],extended['extended']]: verify(row)
    assert medium['elf']['sha256'] == extended['elf']['sha256'] == final['final'][1]['sha256']
    packed_plane = (ROOT/medium['artifacts']['c2-bank2-static-code-plane']['path']).read_bytes()
    raw_plane = (ROOT/final['Bank2_final']['path']).read_bytes()
    assert packed_plane[:len(raw_plane)] == raw_plane
    assert medium['artifacts']['c2-resident-prg']['sha256'] == extended['prefix']['sha256']
    files = MEDIA.inventory((ROOT/medium['medium']['path']).read_bytes())
    payload = (ROOT/extended['extended']['path']).read_bytes()
    carriers = [name for name,row in files.items() if row['data'] == payload]
    assert len(carriers) == 1
    code_files = [name for name,row in files.items() if row['data'] == packed_plane]
    assert len(code_files) == 1
    gc = load('build/dirty-anchor-card-r1/gc-accepted.json')
    assert gc['authority'] == 'e9ef6d57' and gc['deltas']['forced']['delta'] == 318
    assert gc['deltas']['warmup']['delta'] == 325 and gc['comparator_unchanged'] and gc['root_population_unchanged']
    inputs.append(binding(Path(__file__)))
    closure = dict(status='PASS: DIRTY-ANCHOR FINAL', authority='e9ef6d57',
        source_head=source['head_after'], source_exit=0, protected_changes=0,
        final=final, compiler_commands_consumed=75, existing_medium=medium['medium'],
        medium_reuse='Final PRG, ELF, LTO object and Bank-2 plane equal Seed; existing qualified carrier payload read back byte-exactly; no new pack or native build.',
        carrier=carriers[0], packed_code=code_files[0], raw_plane_prefix_bytes=len(raw_plane),
        packed_code_bytes=len(packed_plane), gc_named_live_cost=gc,
        prior_pre_final_seal_unchanged=True, prior_evidence_verified=len(pre['evidence']),
        codegen='Final ELF byte-identical to admitted Seed: no additional family; complete Seed inventory and 73-root closure remain applicable.',
        device_contacts=0, physical_rows_pending=['17-key batch','cold boot'], inputs=inputs)
    p=H/'closure.json'; assert not p.exists()
    p.write_text(json.dumps(closure,indent=2)+'\n')
    subprocess.run([sys.executable,'-B','tools/host-lisp/dirty_anchor_receipt_seal.py','final'],cwd=ROOT,check=True)
    print(closure['status'])

if __name__ == '__main__': main()
