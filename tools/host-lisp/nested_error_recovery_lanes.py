"""Natural single-key and batched lanes, repair Final (role "anchor") vs nested-error recovery Seed.

Reuses the qualified r6 cost observer (input-cost-attribution-r6, the observer
the anchor-cache card proved cycle-neutral against the anchor natural lane:
every bracket identical) without any observer or product build.  The observer
address configuration is derived from each ELF exactly as
anchor_cache_projection_measure.py derives it.  The base world's must equal the
qualified configuration; the Seed moves ordinary text, so its configuration
must equal the base configuration mapped by the inventory's address map
(.text symbols +D, all others unchanged).  Both worlds are run fresh in one
invocation; the base rows must reproduce the accepted repair Seed-2/Final rows
of build/input-cost-natural-retained-callable-repair-r2 bracket for bracket.
"""
import json
import sys
from pathlib import Path

import native_cycle_stationary as N
from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT/'build/nested-error-recovery-instrument-r1'
ATTEMPT = 'nested-error-recovery-r1'
WORLDS = [('anchor', 'build/retained-callable-repair-seed-medium-r2'),
          ('candidate', 'build/nested-error-recovery-seed-medium-r1')]


def cost_config(elf, moved=None):
    t = ElfTruth.read(elf, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj', include_section_data=True)
    vm = t.symbol('vm_run_inner')
    sec = t.section(vm.section)
    body = t.section_bytes(vm.section)[vm.value-sec.address:vm.value-sec.address+vm.bytes]
    sig = bytes.fromhex('85040604a6047c')
    assert body.count(sig) == 1
    config = [t.symbol('vm_callprim').value, vm.value+body.index(sig), t.symbol('vm_buf_bank').value,
              t.symbol('vm_buf_off').value, t.symbol('gc_collect').value, t.symbol('c2_product_entry_record').value]
    config += [t.symbol(n).value for n in ('lisp_input_event', 'vm_key_event', 'c2_kernal_event_poll',
                                           'c2_kernal_input_take', 'vm_soft_sp')]
    sections = [t.symbol(n).section for n in ('vm_callprim', 'vm_run_inner', 'vm_buf_bank', 'vm_buf_off',
                                              'gc_collect', 'c2_product_entry_record', 'lisp_input_event',
                                              'vm_key_event', 'c2_kernal_event_poll', 'c2_kernal_input_take',
                                              'vm_soft_sp')]
    if moved is not None:
        moved.extend(s == '.text' for s in sections)
    return ','.join(map(str, config))


def main():
    assert not HERE.exists()
    HERE.mkdir()
    parent = ROOT/'build/anchor-cache-projection-r1/instrument.json'
    qualified = json.loads(parent.read_text())
    anchor = qualified['worlds'][0]
    worlds = []
    inventory = json.loads((ROOT/'build/nested-error-recovery-seed-inventory-r1/inventory.json').read_text())
    delta = inventory['address_map']['delta']
    for role, path in WORLDS:
        packed = json.loads((ROOT/path/'packed-receipt.json').read_text())
        elf = N.checked_binding(packed['elf'])
        moved = []
        config = cost_config(elf, moved)
        if role == 'anchor':
            assert config == anchor['cost_config'], (role, config)
        else:
            base = [int(x) for x in anchor['cost_config'].split(',')]
            assert config == ','.join(str(x+delta if m else x) for x, m in zip(base, moved)), (role, config)
        world = dict(anchor, role=role, ELF=N.bind(elf), medium=packed['medium'], cost_config=config)
        worlds.append(world)
    assert worlds[0]['ELF']['sha256'] == '815b60a5fb4baf405d5b8e14dac5ad9e593c9bf3f73877efc6b6f63499dc26a1'
    assert inventory['status'].startswith('PASS') and inventory['ELFs'][1]['sha256'] == worlds[1]['ELF']['sha256']
    identity = dict(authority='90b5f9f2', binding='44c021ee', worlds=worlds, binary=qualified['binary'],
                    parent=N.bind(parent), cost_header=qualified['cost_header'],
                    resident_identity=dict(inventory=N.bind(ROOT/'build/nested-error-recovery-seed-inventory-r1/inventory.json'),
                                           claim='entry, paused PC, entry code, _start and signature inherited; '
                                                 'the per-world cost configuration follows the proved address map'),
                    driver=N.bind(Path(__file__)), product_builds=0, observer_builds=0, links=0, seeds=0)
    instrument = HERE/'instrument.json'
    instrument.write_text(json.dumps(identity, indent=2)+'\n')
    source = ROOT/'build/anchor-cache-projection-r1/lanes.py'
    raw = source.read_text()
    for old, new in [
        ("instrument=ROOT/'build/anchor-cache-projection-r1/instrument.json'",
         f"instrument=ROOT/'{instrument.relative_to(ROOT)}'"),
        ("for role,path in [('anchor','build/dirty-anchor-seed-medium-r1')]:",
         "for role,path in "+repr(WORLDS)+":"),
        ("    WORLD=next(w for w in identity['worlds'] if w['ELF']['sha256']==packed['elf']['sha256'])",
         "    WORLD=next(w for w in identity['worlds'] if w['role']==role and w['ELF']['sha256']==packed['elf']['sha256'])"),
        ("prior=json.loads((ROOT/'build/dirty-anchor-native-natural-r1/receipt.json').read_text())\n"
         "old=[r for r in prior['rows'] if r['world']=='candidate']\n"
         "assert len(rows)==len(old)==2\n"
         "for row,previous in zip(rows,old):",
         "prior=json.loads((ROOT/'build/input-cost-natural-retained-callable-repair-r2/receipt.json').read_text())\n"
         "old=[r for r in prior['rows'] if r['world']=='candidate']\n"
         "assert len(old)==2 and len(rows)==4\n"
         "for row,previous in zip([r for r in rows if r['world']=='anchor'],old):"),
        ("result=dict(status='PASS: ANCHOR R6 OBSERVER; EVERY BRACKET CYCLE IDENTICAL',rows=rows,",
         "result=dict(status='PASS: FRESH REPAIR-FINAL ROWS REPRODUCE THE ACCEPTED REPAIR ROWS; CANDIDATE MEASURED',rows=rows,"),
        ("    prior=N.bind(ROOT/'build/dirty-anchor-native-natural-r1/receipt.json'),",
         "    prior=N.bind(ROOT/'build/input-cost-natural-retained-callable-repair-r2/receipt.json'),"),
    ]:
        assert raw.count(old) == 1, old
        raw = raw.replace(old, new)
    target = HERE/'lanes.py'
    target.write_text(raw)
    sys.argv = [str(target), '--attempt', ATTEMPT]
    exec(compile(raw, str(target), 'exec'), dict(__name__='__main__', __file__=str(target)))


if __name__ == '__main__':
    main()
