#!/usr/bin/env python3
"""IDE exit Card-5 successor: inherited integrity and explicit source routes.

The public-era tool and receipt are immutable predecessors. Only source
authority is checked here; no product is built, linked or contacted.
"""
import argparse
import copy

import c2_v250_card5_20260928 as H

G = H.G
RECEIPT = G.ROOT / 'config/c2-ide-exit-card5-receipt-20260928.json'
HISTORY = {
    'tools/host-lisp/c2_v250_card5_20260928.py':
        '3bcef1e0c01527a3571c45dee50bc675dd0a6f80ecea822f66181ca39665f7ff',
    'config/c2-v250-card5-receipt-public-era-20260928.json':
        '8e9d834dcb253f28c0b15ff402892a231c4b2c719fb7ab918250d7a871b5b1ef',
}

# Retain all inherited route checks, replacing the two superseded commands
# and adding both source entry points and the successor's own selftest route.
H.H.K.ROUTES = dict(H.H.K.ROUTES, **{
    'block-26-build-integrity-check': 'c2_ide_exit_card5_20260928.py',
})
H.CHECK_HOST_ROUTES = copy.deepcopy(H.CHECK_HOST_ROUTES)
H.CHECK_HOST_ROUTES['mk/workbench.mk']['v11-l-lite-keymap-check'] = [
    'c2_ide_exit_keymap_20260928.py selftest',
    'c2_ide_exit_keymap_20260928.py check',
]
H.CHECK_HOST_ROUTES['mk/gates.mk'].update({
    'c2-l-full-keymap-end-to-end-check': [
        'c2_ide_exit_keymap_20260928.py selftest',
        'c2_ide_exit_keymap_20260928.py check',
        'c2_ide_exit_key_path_20260928.py',
    ],
    'block-26-build-integrity-selftest': [
        'c2_ide_exit_card5_20260928.py selftest',
    ],
})


def history_check(rows):
    G.require(rows == HISTORY, 'IDE exit Card-5 predecessor drift')


def derive():
    rows = {path: G.sha(G.ROOT / path) for path in HISTORY}
    history_check(rows)
    for path in rows:
        trial = dict(rows)
        trial[path] = '0' * 64
        try:
            history_check(trial)
        except G.CardError:
            pass
        else:
            raise G.CardError('IDE exit predecessor mutation survived: ' + path)
    inherited = H.derive()
    paths = set(HISTORY) | {
        'tools/host-lisp/c2_ide_exit_card5_20260928.py',
        'tools/host-lisp/c2_ide_exit_keymap_20260928.py',
        'tools/host-lisp/c2_ide_exit_key_path_20260928.py',
        'config/v11-l-lite-keymap.json',
        'config/c2-ide-exit-keymap-probe-20260928.json',
        'tests/bytecode/dialect-v2/fixtures/c2-ide-exit-core-source-snapshot-20260928.json',
    }
    return dict(
        format='lisp65-ide-exit-card5-successor-v1', date='2026-09-28',
        status='passed', predecessor=rows, history_mutations=len(rows),
        inherited_v250=inherited,
        inputs=[dict(path=p, sha256=G.sha(G.ROOT / p)) for p in sorted(paths)],
        claim_limit='Source authority only; product and physical acceptance pending',
        product_builds=0, product_links=0, device_contacts=0,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('selftest', 'build', 'check'))
    action = parser.parse_args().action
    value = G.canonical(derive())
    if action == 'build':
        # Exclusive creation also prevents an existing receipt being replaced.
        with RECEIPT.open('xb') as stream:
            stream.write(value)
    elif action == 'check':
        G.require(RECEIPT.read_bytes() == value, 'IDE exit Card-5 receipt drift')
    print('IDE exit Card-5: ' + action.upper() +
          ' PASS inherited-integrity=13 routes=9 source-routes=9 history=2')


if __name__ == '__main__':
    main()
