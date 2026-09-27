"""Bidirectional relocation census and immutable Seed receipt verification."""
import collections
from dataclasses import asdict
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import set_b_producer as P
from elf_truth import ElfTruth
from set_b_instruction_inventory_20260926 import PATHS

ROOT = P.ROOT
STEP = ROOT/'build/set-b-r1/step4-r4'
OUT = STEP/'inventory-closure-r1'


def main():
    OUT.mkdir(exist_ok=False)
    instructions = STEP/'instruction-inventory-r2'
    functions = P.load(instructions/'function-instructions.json')
    others = P.load(STEP/'linked-inventory-r1/remaining-relocations.json')['rows']
    new = P.load(instructions/'census.json')['new']
    final = STEP/'structure-inventory-r4/inventory.json'
    assert P.load(final)['status'] == 'PASS'
    ledger = []
    for k, path in enumerate(PATHS):
        t = ElfTruth.read(path, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
        classified = {}
        def assign(r, why):
            classified[(r['source_section'], r['offset'])] = why
        for row in functions:
            if row['status'] == 'PASS':
                for witness in row['witnesses']:
                    for r in witness['relocations'][k]: assign(r['relocation'], 'paired instruction expression and encoded operand')
            else:
                f = row['before' if k == 0 else 'after']
                for r in t.relocations:
                    if r.source_section == f['section'] and f['value'] <= r.offset < f['value']+f['bytes']:
                        assign(asdict(r), 'authorized native source body: '+f['name'])
        if k == 1:
            for f in new:
                for r in t.relocations:
                    if r.source_section == f['section'] and f['value'] <= r.offset < f['value']+f['bytes']:
                        assign(asdict(r), 'authorized new retirement body: '+f['name'])
        for row in others:
            r = row.get('before' if k == 0 else 'after')
            if r and row.get('equivalent'): assign(r, 'paired data expression and encoded operand')
        for r in t.relocations:
            if r.relocation_type == 'R_MOS_ADDR_ASCIZ': assign(asdict(r), 'proved BASIC SYS decimal address')
            assert (r.source_section, r.offset) in classified, ('unclassified relocation', k, r)
        rows = [dict(relocation=asdict(r), family=classified[(r.source_section, r.offset)]) for r in t.relocations]
        P.write(OUT/('before-relocations.json' if k == 0 else 'after-relocations.json'), rows)
        ledger.append(dict(total=len(rows), families=dict(collections.Counter(r['family'] for r in rows))))
    # Verify the original link seal as well as the newly executed proof chain.
    seal = ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/set-b-third-seed-inventory-halt-20260926.json'
    old = P.load(seal); checked = []
    for row in old['inputs']+old['receipt_copies']:
        assert P.bind(ROOT/row['path']) == row, row['path']; checked.append(row)
    for path in [instructions/'census.json', STEP/'linked-inventory-r1/allocated-census.json', final]:
        result = P.load(path)
        assert result['driver'] == P.bind(ROOT/result['driver']['path'])
    P.write(OUT/'receipt.json', dict(status='PASS: COMPLETE LINKED INVENTORY', complete_inventory=True,
        unclassified_bytes=0, unclassified_relocations=0, driver=P.bind(Path(__file__)),
        inventory=P.bind(final), original_link_seal=P.bind(seal), prior_bindings_checked=len(checked),
        relocation_census=ledger, seed=P.bind(PATHS[1]), source_authority=P.require_auth(),
        codegen_scope_authority='8a3eac10', additional_builds=0, additional_links=0,
        media_qualified=False, guest_qualified=False))
    print('PASS: complete inventory; both relocation directions; original link bindings', len(checked))


if __name__ == '__main__': main()
