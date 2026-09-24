"""Read-only Definitions split admission; never invokes a compiler or linker.

This prices the existing sketch, not a lower bound on every possible design.
JSON is written only to stdout so checking cannot overwrite a sealed receipt.
"""
from pathlib import Path
import hashlib
import json
import subprocess

from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def bind(path):
    raw = (ROOT / path).read_bytes()
    return dict(path=path, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def bind_git(commit, path):
    """Bind a file the way `bind` does, but from a sealed commit, not the
    live working tree (see sealed_manifest above for why)."""
    raw = subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)
    return dict(path=path, commit=commit, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def admissible(free, floor, carrier, journal, control):
    return (min(carrier, journal, control) >= 0
            and free - carrier - journal >= floor and control <= 200)


def sealed_manifest(commit, path):
    """Read the manifest as it stood at this card's own sealed authority.

    This is an era card (Definitions-Placement round, 2026-09-17): its prices
    and controls are receipts about a *specific past* accepted world, not a
    live gate that should track the working-tree manifest. The Bank-5 floor
    it bounds (8,576) was rebound to 374 on 2026-09-20 once the boot-time
    name index formalized a transient owner in the same free tail (see
    config/storage-owner-manifest.json and tools/host-lisp/
    storage_owner_preflight.py); reading the manifest live would make this
    card fail on that later, unrelated re-binding instead of reproducing the
    world it was actually written against. `commit` is this module's own
    `authority` value, so the binding is self-consistent rather than assumed.
    """
    raw = subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)
    return json.loads(raw)


def main():
    manifest_authority = 'da42d6f5'
    manifest_path = 'config/storage-owner-manifest.json'
    elf_path = ('build/transient-retirement-final-medium-r1/materialized/'
                'lisp65-c2-substitution-linked.prg.elf')
    price_path = 'build/definition-retirement-owner-reuse-r1/receipt.json'
    closure_path = 'build/definition-retirement-owner-reuse-r1/closure.json'
    group_path = 'build/definition-pricing-r2/group-probe.json'
    batch_path = 'build/definition-pricing-r1/batch-price.json'
    m = sealed_manifest(manifest_authority, manifest_path)
    price = json.loads((ROOT / price_path).read_text())
    closure = json.loads((ROOT / closure_path).read_text())
    group = json.loads((ROOT / group_path).read_text())
    batch = json.loads((ROOT / batch_path).read_text())
    elf = ElfTruth.read(ROOT / elf_path,
                        llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
    owner = m['table_owner']
    derived_end = (owner['bank'] * 65536 + owner['offset']
                   + len(owner['tables']) * m['symbol_slots'] * owner['bytes_per_slot'])
    linked_end = elf.symbol('__storage_symbol_tables_end').value
    require(derived_end == linked_end, 'manifest versus consumed table owner drift')
    require(owner['bank'] == 5, 'wrong bank')
    free = 6 * 65536 - linked_end
    floor = m['floors']['bank5_free']
    require(floor == 8576, 'bound Bank-5 floor changed')
    require(free == 8672, 'accepted-world free-tail drift')
    require(price['text'] == 4113, 'priced sketch drift')
    require(closure['recover']['bytes'] == 2723
            and closure['max_slice_bytes'] == 1792, 'closure price drift')
    require(group['net_code_bytes'] == 133 and batch['text'] == 137,
            'Set-A partial price drift')
    checks = {
        'last_above_floor_byte_accepted': admissible(free, floor, 96, 0, 200),
        'first_floor_byte_rejected': not admissible(free, floor, 97, 0, 200),
        'journal_charged': not admissible(free, floor, 96, 1, 200),
        'controller_201_rejected': not admissible(free, floor, 0, 0, 201),
        'free_tail_not_spendable_floor': not admissible(free, floor, floor, 0, 0),
        'priced_core_alone_rejected': not admissible(free, floor, price['text'], 0, 0),
        'priced_core_and_journal_rejected': not admissible(free, floor, price['text'], 38, 0),
    }
    require(all(checks.values()), 'placement boundary control failed')
    result = dict(
        authority='da42d6f5', status='SPLIT SELECTED; NOT SEED ADMISSION',
        bank5=dict(table_end=linked_end, free=free, floor=floor,
                   above_floor=free-floor, priced_core=price['text'], journal=38,
                   free_after_core_and_journal=free-price['text']-38,
                   floor_shortfall=price['text']+38-(free-floor)),
        combined=dict(fits=False, controller_cap=200,
                      controller_price=None, gc_price=None, closure_adapter_price=None,
                      phase_cut_proven=False, carrier_replay_proven=False,
                      reason='Existing core alone fails retained Bank-5 floor'),
        set_a=dict(group_lisp_partial_bytes=group['net_code_bytes'],
                   publication_skeleton_text_bytes=batch['text'],
                   seed_admitted=False,
                   remaining=['prompt dispatch', 'typed clean capacity failure',
                              'whole-group capacity/rollback native rows',
                              'composed price including prerequisites',
                              'producer consumption and final preflight']),
        set_b=dict(next_card=True, image_slot_reuse_deferred=True,
                   moving_code=False, code_gaps_are_free_bytes=False),
        controls=checks, budget=dict(seed=0, final=0, product_link=0),
        bindings=[bind_git(manifest_authority, manifest_path)]
                  +[bind(p) for p in (elf_path, price_path,
                    closure_path, group_path, batch_path,
                    'tools/host-lisp/definition_retirement_placement.py',
                    'tools/host-lisp/elf_truth.py',
                    'tools/llvm-mos/bin/llvm-readobj')])
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
