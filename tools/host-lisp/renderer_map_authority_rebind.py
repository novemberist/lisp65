#!/usr/bin/env python3
"""Keep sealed MAP evidence immutable; derive successor prices from its ELF.

No producer entry point.  The two historical checks retain their own eras;
each additionally verifies a separately sealed renderer-world receipt.
"""
import argparse
from copy import deepcopy
import json

import c2_v21_map_mask_fix as FIX
from evidence_era import era_bind, stable_recorded_on
from elf_truth import ElfTruth

ROOT = FIX.ROOT
ARCH = FIX.ARCH
QUALIFICATION = ARCH / 'v2.1-renderer-branch-product-r1-receipt.json'


def receipt(kind):
    if kind not in ('screen', 'bank4'):
        raise ValueError('unknown MAP evidence world')
    return ARCH / f'v2.1-renderer-{kind}-map-successor-receipt.json'


def derive(kind):
    if kind == 'screen':
        import c2_v21_terminal_screen_map_authority_rebind as historical
        old = historical.load(historical.RECEIPT)
        expected = historical.derive()
        expected['mutations_rejected'] = historical.mutations(expected)
    elif kind == 'bank4':
        import c2_v21_bank4_map_attribution as historical
        old = historical.load(historical.RECEIPT)
        expected = historical.derive()
    else:
        raise ValueError('unknown MAP evidence world')
    FIX.require(old == expected, 'sealed historical MAP evidence drift')
    q = FIX.load(QUALIFICATION)
    FIX.require(q['status'].startswith('PASS:'), 'renderer qualification absent')
    for binding in q['pair']:
        FIX.require(FIX.bind(ROOT / binding['path']) == binding,
                    'renderer product identity drift')
    # This receipt prices the sealed renderer pair, not each later live
    # placement. A successor's unexecuted alignment prefix does not rewrite
    # the source authority of the renderer ELF being checked here.
    source = era_bind(q['source_commit'], FIX.SOURCE)
    elf = ROOT / q['pair'][0]['path']
    linked = FIX.linked_gate(elf)
    predecessor = q['authority']['predecessor']['ELF']
    FIX.require(FIX.bind(ROOT / predecessor['path']) == predecessor,
                'renderer predecessor identity drift')
    before = FIX.linked_gate(ROOT / predecessor['path'])
    # Derive both prices from linked symbols, not the old 189-byte micro-price.
    truth = ElfTruth.read(elf, llvm_readobj=FIX.READOBJ)
    section = truth.section(truth.symbol('c2_map_cpu_read').section)
    FIX.require(section.address <= int(linked['reader']['address'], 16)
                and int(linked['reader']['end_exclusive'], 16)
                <= section.address + section.bytes, 'reader outside its owner')
    return {
        'status': 'PASS: SEALED MAP ERA AND LINKED RENDERER SUCCESSOR',
        'recorded_on': stable_recorded_on(receipt(kind)),
        'historical_receipt': FIX.bind(historical.RECEIPT),
        'historical_era': 'screen seal' if kind == 'screen' else 'pre-renderer seal',
        'qualification': FIX.bind(QUALIFICATION),
        'source_commit': q['source_commit'], 'reader_source': source,
        'driver': FIX.bind(ROOT / 'tools/host-lisp/renderer_map_authority_rebind.py'),
        'pair': q['pair'], 'predecessor': predecessor,
        'linked_reader': linked, 'predecessor_reader': before,
        'reader_delta_bytes': linked['reader']['bytes'] - before['reader']['bytes'],
        'owner': {'section': section.name, 'address': section.address,
                  'bytes': section.bytes},
        'boundary': 'Historical price and contact stay historical; current identity and price come from final ELF. No build, medium or contact.',
    }


def validate(value, expected):
    FIX.require(value == expected, 'renderer MAP successor authority/price drift')


def mutations(value):
    cases = {
        'stale-linked-reader-price': lambda x: x['linked_reader']['reader'].update(
            bytes=x['predecessor_reader']['reader']['bytes']),
        'stale-product-identity': lambda x: x['pair'].__setitem__(0, x['predecessor']),
        'omit-current-source': lambda x: x.pop('reader_source'),
        'historical-price-as-current': lambda x: x.update(linked_reader=x['predecessor_reader']),
        'hide-reader-growth': lambda x: x.update(reader_delta_bytes=0),
        'restore-self-covering-map': lambda x: x['linked_reader']['positive'].update(MAPL='0xffc0'),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial, value)
        except FIX.MaskFixError:
            rejected.append(name)
    FIX.require(rejected == list(cases), 'renderer MAP successor mutation survived')
    return rejected


def check(kind):
    expected = derive(kind)
    expected['mutations_rejected'] = mutations(expected)
    validate(FIX.load(receipt(kind)), expected)
    print(f'renderer {kind} MAP successor: PASS linked price derived; mutations=6')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('record', 'check'))
    args = parser.parse_args()
    for kind in ('screen', 'bank4'):
        if args.action == 'record':
            value = derive(kind)
            value['mutations_rejected'] = mutations(value)
            receipt(kind).write_bytes(FIX.canonical(value))
        check(kind)


if __name__ == '__main__':
    main()
