#!/usr/bin/env python3
"""A7 successor: short-branch crossing ceilings re-based on the 2.4.0 release.

`hot_branch_page_gate.py` keeps its immutable 2.2.0 ceilings and, by default,
evaluates only the 2.2.0 ELF. The released successors were never evaluated:
2.3.0 already had 4 potential crossings in `vm_run_inner` against the 2.2.0
ceiling of 3, and the 2.4.0 release candidate has 7. This successor makes the
exceedance explicit instead of tolerating it silently. The ledger
`config/hot-branch-ceilings-v240.json` records, per owner, the 2.2.0
ceiling, the shipped 2.3.0 count and the 2.4.0 count with its attribution;
the 2.4.0 counts become the ceilings every later world is checked against
(`--elf`). Counts are potential taken-branch page crossings, not cycles; the
cycle effect of each card was measured and accepted in that card's lanes.
"""
import argparse
import hashlib
import json
from pathlib import Path

import hot_branch_page_gate as A7
from stack_layout_assumptions_gate import ROOT, AUTHORITY, require

LEDGER = ROOT/'config/hot-branch-ceilings-v240.json'


def counts(elf):
    return {name: A7.crossings(row) for name, row in A7.population(elf).items()}


def check(successor=None):
    ledger = json.loads(LEDGER.read_text())
    require(ledger['format'] == 'lisp65-a7-hot-branch-ceilings-v240-v1' and ledger['release'] == '2.4.0',
            'ledger format/release drift')
    bound = ledger['ceiling_elf']
    elf = ROOT/bound['path']
    require(hashlib.sha256(elf.read_bytes()).hexdigest() == bound['sha256'], 'v240 ceiling ELF identity drift')
    release = json.loads((ROOT/'config/c2-v240-public-build-authority.json').read_text())['raw_pair']['ELF']
    require(bound['sha256'] == release['sha256'], 'ceiling ELF is not the released 2.4.0 ELF')
    predecessor = json.loads(AUTHORITY.read_text())['raw_pair']['ELF']
    require(ledger['predecessor']['elf_sha256'] == predecessor['sha256'], 'predecessor ELF drift')
    require(counts(ROOT/predecessor['path']) == ledger['predecessor']['ceilings'], 'predecessor ceiling ledger drift')
    ceiling = counts(elf)
    require(ceiling == ledger['ceilings'], 'v240 ceiling ledger differs from the release ELF')
    exceeded = sorted(name for name in A7.OWNERS if ceiling[name] > ledger['predecessor']['ceilings'][name])
    require(exceeded == sorted(ledger['exceedances']), 'exceedance population differs from the ledger')
    for name in exceeded:
        require(ledger['exceedances'][name].get('attribution'), 'unattributed exceedance: '+name)
    actual = counts(successor) if successor else ceiling
    rows = A7.population(successor) if successor else A7.population(elf)
    A7.validate(rows, ceiling)
    rejected = []
    for name, row in A7.population(elf).items():
        shift = next((n for n in range(1, 256) if A7.crossings(row, n) > ceiling[name]), None)
        require(shift is not None, 'no sharp shift control: '+name)
        mutant = dict(A7.population(elf))
        mutant[name] = dict(row, branches=[dict(b, pc=b['pc']+shift, target=b['target']+shift)
                                          for b in row['branches']])
        try:
            A7.validate(mutant, ceiling)
        except RuntimeError:
            rejected.append(dict(owner=name, shift=shift))
        else:
            raise RuntimeError('shift control survived: '+name)
    try:
        A7.validate(A7.population(elf), ledger['predecessor']['ceilings'])
    except RuntimeError:
        rejected.append(dict(owner='release-against-2.2.0-ceiling', result='exceeds as recorded'))
    else:
        raise RuntimeError('recorded 2.2.0 exceedance vanished')
    out = ROOT/'build/hot-branch-pages-v240/receipt.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    result = dict(status='PASS', ceiling_elf=bound, ceilings=ceiling, evaluated=actual,
                  evaluated_elf=str(successor) if successor else bound['path'],
                  exceedances_vs_2_2_0=exceeded, mutations_rejected=rejected)
    out.write_text(json.dumps(result, indent=2)+'\n')
    print('hot-branch-pages-v240: PASS', ceiling, 'exceedances vs 2.2.0:', exceeded)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', type=Path)
    args = parser.parse_args()
    check(args.elf)


if __name__ == '__main__':
    main()
