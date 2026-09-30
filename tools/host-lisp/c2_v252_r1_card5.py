"""2.5.2 Card-5 successor of the r7 Card-5: reconciled docs and v252 route retargets.

Successor of c2_v251_card5_disk_r7_20260930 (immutable). The inherited chain
pins README.md and docs/development.md through its nested 2.5.0-era layers,
and the 2.5.2 documentation reconciliation changed both, so the r7 receipt can
no longer be re-derived. This successor re-derives the complete inherited
chain and additionally requires the Makefile routes retargeted to the v252
successors (docs, naming, keymap, v210 replay, media census, Card-5).
"""
import copy
import c2_v251_card5_disk_r7_20260930 as H
import disk_r7_consumers_20260930 as S
# r2: the r1 receipt predates the v251 release-era route (write-once; r1 is superseded).
RECEIPT = 'config/c2-v252-r1-card5-receipt-r4.json'
REPLACEMENTS = {
    'c2_v251_card5_disk_r7_20260930.py': 'c2_v252_r1_card5.py',
    'c2_v251_r2_20260929_bundle_docs_gate.py': 'c2_v252_r1_bundle_docs_gate.py',
    'c2_v251_r2_20260929_v210_bundle_docs.py': 'c2_v252_r1_v210_bundle_docs.py',
    'c2_v251_r2_20260929_public_naming.py': 'c2_v252_r1_public_naming.py',
    'c2_v251_r2_20260929_keymap.py': 'c2_v252_r1_keymap.py',
    'c2_v251_keymap_receipt_o2_lite_20260929.py': 'c2_v252_r1_keymap_receipt.py',
    'c2_v251_r2_20260929_media_census.py': 'c2_v252_r1_media_census.py',
    'c2_v251_r2_20260929_public_product.py preflight': 'c2_v252_r1_v251_release_era.py check',
}
TOOLS = ['c2_v252_r1_common.py', 'c2_v252_r1_bundle_docs_gate.py', 'c2_v252_r1_v210_bundle_docs.py',
         'c2_v252_r1_public_naming.py', 'c2_v252_r1_keymap.py', 'c2_v252_r1_keymap_receipt.py',
         'c2_v252_r1_media_census.py', 'c2_v252_r1_reproduction_gate.py', 'c2_v252_r1_toolchain.py',
         'c2_v252_r1_document_index.py', 'c2_v252_r1_v251_release_era.py']
RECEIPTS = ['config/c2-v252-r1-bundle-docs.json', 'config/c2-v252-r1-public-naming-receipt.json',
            'config/c2-v252-r1-keymap-receipt.json', 'config/c2-v252-r1-v210-bundle-docs-receipt.json',
            'config/c2-v252-r1-v251-release-era.json', 'config/c2-v252-r1-reproduction-policy.json']
K, V = H.K, H.V
K.ROUTES = {target: REPLACEMENTS.get(tool, tool) for target, tool in K.ROUTES.items()}
V.CHECK_HOST_ROUTES = copy.deepcopy(V.CHECK_HOST_ROUTES)
for targets in V.CHECK_HOST_ROUTES.values():
    for target, commands in targets.items():
        for old, new in REPLACEMENTS.items():
            commands = [c.replace(old, new) for c in commands]
        targets[target] = commands


def derive():
    return dict(inherited=H.derive(), receipts=[S.S.bind(p) for p in RECEIPTS],
                tools=[S.S.bind('tools/host-lisp/' + p) for p in TOOLS])


if __name__ == '__main__':
    S.finish('card5-v252', derive, RECEIPT, H,
             (__file__, 'Makefile', 'mk/gates.mk', 'mk/workbench.mk', 'README.md', 'docs/development.md', *RECEIPTS,
              *('tools/host-lisp/' + p for p in TOOLS)))
