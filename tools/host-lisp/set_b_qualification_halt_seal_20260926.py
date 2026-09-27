"""Preserve the Set B inventory/media closure and activation halt, without reruns."""
import argparse
import gzip
import hashlib
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True
import set_b_producer as P

ROOT = P.ROOT
ARCH = ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks'
STEM = 'set-b-seed-qualification-halt-20260926'
SEAL = ARCH/(STEM+'.json')
STEP = ROOT/'build/set-b-r1/step4-r4'
REPORT = ROOT/'docs/planning/set-b-seed-qualification-halt-report.md'


def create():
    assert not SEAL.exists() and not (ARCH/STEM).exists()
    assert P.load(STEP/'inventory-closure-r1/receipt.json')['status'] == 'PASS: COMPLETE LINKED INVENTORY'
    assert P.load(ROOT/'build/set-b-seed-medium-r4/readback.json')['status'] == 'PASS: INDEPENDENT MEDIA READBACK'
    boot = P.load(ROOT/'build/set-b-boot-candidate-r2/receipt.json')
    assert boot['status'] == 'HALT' and boot['result']['ready'] == 1 and boot['result']['retirement_latch'] == 0
    attr = P.load(ROOT/'build/set-b-boot-halt-attribution-r4/receipt.json')
    assert attr['observed']['tenant_bytes_equal'] and attr['observed']['journal_zero']
    roots = [STEP/p for p in ('instruction-inventory-r1','instruction-inventory-r2','linked-inventory-r1',
             'structure-inventory-r1','structure-inventory-r2','structure-inventory-r3','structure-inventory-r4','inventory-closure-r1')]
    roots += [ROOT/f'build/set-b-seed-medium-r{i}' for i in range(1,5)]
    roots += [ROOT/f'build/set-b-boot-candidate-r{i}' for i in range(1,3)]
    roots += [ROOT/f'build/set-b-boot-halt-attribution-r{i}' for i in range(1,5)]
    selected = set(); excluded = []
    for root in roots:
        assert root.is_dir()
        for path in root.rglob('*'):
            if not path.is_file(): continue
            if path.name == 'system-sd.img':
                excluded.append(dict(path=str(path.relative_to(ROOT)),reason='disposable 4 GiB SD copy; original not written; runtime memory and exact D81 are retained'))
            else: selected.add(path)
    tools = ['set_b_instruction_inventory_20260926.py','set_b_linked_inventory_20260926.py',
             'set_b_inventory_structure_20260926.py','set_b_inventory_closure_20260926.py',
             'set_b_seed_delivery_20260926.py','set_b_seed_readback_20260926.py','set_b_seed_boot_20260926.py',
             'set_b_boot_halt_attribution_20260926.py',Path(__file__).name,
             'elf_truth.py','native_cycle_stationary.py','dwx_retroactive_red_replay.py','dwx_comfort_resume.py',
             'nested_error_recovery_gates.py','nested_error_recovery_lanes.py','card_l_seed_media.py',
             'c2_product_substitution_link.py','c2_v160_refill_boundary_witness_media_repair.py',
             'boot_only_carrier_prg.py','c2_lite_canonical_product.py','d81_persistence_fault.py',
             'c2_lite_media_product.py','c2_require_resolver_gate.py']
    selected.update(ROOT/'tools/host-lisp'/p for p in tools)
    selected.update(ROOT/p for p in P.authority_files())
    selected.update([REPORT,ROOT/'scripts/xmega65-safe-run.sh',ROOT/'scripts/kill-xmega65-by-token.py',
        ROOT/'src/optional/c2_map_cpu_read.s',ROOT/'src/c2_kernal_facade_reopen.s',
        ROOT/'build/set-b-product-r3/commands.json',ROOT/'build/set-b-product-r3/wplto/resident-island-seed.prg.elf',
        ROOT/'build/set-b-product-r3/set-b-tenants.bin',ROOT/'build/card-l-r1/instrument-comfort.json',
        ROOT/'build/input-cost-attribution-r6/xemu/build/bin/xmega65.native',
        ARCH/'set-b-third-seed-inventory-halt-20260926.json'])
    for row in P.load(ROOT/'build/set-b-boot-halt-attribution-r4/compiler-roots.json')['roots']:
        selected.add(ROOT/row['source']['path'])
    # Snapshot the owner scope commit, rather than sealing the rolling journal.
    authority = ARCH/STEM/'owner-scope.md'; authority.parent.mkdir(parents=True)
    authority.write_bytes(subprocess.check_output(['git','show','8a3eac10:docs/planning/post-2.4.0-plan.md'],cwd=ROOT))
    copies = []; inputs = []
    for path in sorted(selected):
        bound = P.bind(path); inputs.append(bound)
        if not path.is_relative_to(ROOT/'build'): continue
        data = path.read_bytes(); compressed = len(data) > 131072
        destination = ARCH/STEM/path.relative_to(ROOT)
        if compressed: destination = destination.with_name(destination.name+'.gz')
        assert not destination.exists(); destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(gzip.compress(data,compresslevel=9,mtime=0) if compressed else data)
        assert (gzip.decompress(destination.read_bytes()) if compressed else destination.read_bytes()) == data
        copies.append(dict(source=bound,copy=P.bind(destination),encoding='gzip' if compressed else 'identity'))
    P.write(SEAL,dict(status='HALT: COMPLETE INVENTORY, POSITIVE MEDIUM RETIREMENT DISARMED',
        source_authority=P.require_auth(),scope_authority='8a3eac10',accepted_world='Card L Final',public_release='2.4.0',
        seed=boot['world']['ELF'],medium=boot['world']['medium'],observer=boot['world']['binary'],report=str(REPORT.relative_to(ROOT)),
        complete_linked_inventory=True,unclassified_bytes=0,unclassified_relocations=0,
        seed_attempts=3,finals=0,product_link_attempts=3,successful_product_links=1,
        this_continuation=dict(product_compiles=0,product_links=0,cold_stager_compiles=4,cold_stager_links=4,observer_builds=0,guest_launches=1,device_contacts=0),
        no_final_or_sealed_full_source_run=True,further_product_link_authorized=False,
        owner_scope=P.bind(authority),inputs=inputs,receipt_copies=copies,excluded=excluded,
        evidence_limit=attr['evidence_limit']))
    print('SEALED',len(inputs),'inputs;',len(copies),'lossless evidence copies')


def check():
    seal = P.load(SEAL)
    for row in seal['inputs']+[seal['owner_scope']]: assert P.bind(ROOT/row['path']) == row,row['path']
    for row in seal['receipt_copies']:
        source,copy = row['source'],row['copy']; assert P.bind(ROOT/copy['path']) == copy
        data = (ROOT/copy['path']).read_bytes()
        if row['encoding'] == 'gzip': data = gzip.decompress(data)
        assert len(data) == source['bytes'] and hashlib.sha256(data).hexdigest() == source['sha256']
    print('PASS seal and every decompressed receipt copy')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('mode',choices=['create','check'])
    args = ap.parse_args(); create() if args.mode == 'create' else check()
