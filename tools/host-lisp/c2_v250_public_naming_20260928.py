#!/usr/bin/env python3
"""Dated naming successor: retain classifications, bind the 2.5.0 guide.

Only guide provenance changes; no rename or new product claim is authorized.
The historical tool and receipt remain immutable.
"""
import argparse
import copy
import json

import public_naming_audit as H

RECEIPT = H.ROOT / 'config/c2-v250-public-naming-receipt-20260928.json'
HISTORY = {
    'tools/host-lisp/public_naming_audit.py':
        'e21e8c939dca8a84dd03e8b733a5f4745c5bc47932a6224694a2eeb17b00978a',
    'config/public-naming-audit.json':
        '396470556694290c2a1609bd90319d2380f6f04e817ed2c9ec00fa52f9bd6a56',
}


def history(rows):
    H.require(rows == HISTORY, 'naming predecessor drift')


def validate(observed):
    expected = copy.deepcopy(H.load(H.CONTRACT))
    expected['authority']['user_guide']['sha256'] = H.sha(H.USER_GUIDE)
    H.verify(expected, observed)


def derive():
    predecessors = {p: H.sha(H.ROOT / p) for p in HISTORY}
    history(predecessors)
    inherited = H.selftest()
    observed = inherited['observed']
    validate(observed)
    for path in predecessors:
        trial = dict(predecessors)
        trial[path] = '0' * 64
        try:
            history(trial)
        except H.NamingError:
            pass
        else:
            raise H.NamingError('predecessor mutation survived')
    trials = []
    trial = copy.deepcopy(observed)
    trial['authority']['user_guide'] = H.load(H.CONTRACT)['authority']['user_guide']
    trials.append(trial)
    trial = copy.deepcopy(observed)
    trial['public_functions'].pop()
    trials.append(trial)
    for trial in trials:
        try:
            validate(trial)
        except H.NamingError:
            pass
        else:
            raise H.NamingError('successor mutation survived')
    return dict(format='lisp65-public-naming-v250-successor-20260928',
                status='passed', predecessors=predecessors, observed=observed,
                mutations=dict(inherited=inherited['mutations_rejected'],
                               history=len(predecessors), successor=len(trials)),
                media_claim_controls=inherited['media_claim_controls'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('record', 'selftest', 'check'))
    action = parser.parse_args().action
    value = (json.dumps(derive(), indent=2, sort_keys=True) + '\n').encode()
    if action == 'record':
        H.require(not RECEIPT.exists(), 'successor receipt already exists')
        RECEIPT.write_bytes(value)
    elif action == 'check':
        H.require(RECEIPT.read_bytes() == value, 'naming successor drift')
    print('v250 public naming: PASS inherited-mutations=7 history=2 successor=2')


if __name__ == '__main__':
    main()
