"""2.5.5 Card-5 successor: route retargets to the 2.5.5 dated successors (receipt r3, see RECEIPT).

Successor of c2_v254_r1_card5 (immutable, receipt r5).  The inherited chain is
re-derived unchanged; the expected routes are retargeted to the successors of
the 2.5.5 typing card (IDE editor key cost): keymap entry point and keymap
receipt, IDE exit key-path check, editor allocation r6, function metadata r8,
string codec workloads r4.  Every retarget names the exact predecessor
command; all other routes keep their 2.5.4 meaning.  One route is new and is
bound here: c2-v255-editor-key-cost-check (mk/gates.mk), the per-key cost gate
of this card.  The bound-artifact source-parity successor (which runs the
2.5.5 key-path check) is bound as a tool, as its predecessor was.  The r7
disk / O2-lite source pins are checked in the sealed 2.5.2 world
(era_replay_v254_20261003.pin_disk_r7_source_controls), as in 2.5.4.
"""
import copy
import hashlib

import c2_v254_r1_card5 as H
import disk_r7_consumers_20260930 as S
import era_replay_v254_20261003 as R

# r2 (2026-10-07, candidate time: Final sealed, device session pending): the 2.5.5 r1 successors of the
# bundle-docs, naming and v210 gates with their receipts replace the 2.5.4 r2 ones in the routes, the media census
# successor replaces the 2.5.4 one in the census route, and the 2.5.5 document-index successor, the 2.5.5
# public-source authority (reproduction gate and policy, toolchain record with the one Fedora 45 pin set), the
# historical host pin successor (2.5.4 is now a past release) with its era wrapper and the Card-5 product
# successor are bound; r1 is committed and superseded.
# r3 (2026-10-07, ship time, device session passed): the r2 successors of the bundle-docs, naming and v210 gates
# and their receipts replace the r1 candidate-time ones in the routes; r2 is committed and superseded.
RECEIPT = 'config/c2-v255-r1-card5-receipt-r3.json'
HISTORY = {p: hashlib.sha256((S.ROOT / p).read_bytes()).hexdigest() for p in (
    'tools/host-lisp/c2_v254_r1_card5.py', H.RECEIPT)}
REPLACEMENTS = {
    'c2_v254_r1_card5.py': 'c2_v255_r1_card5.py',
    'c2_v254_r1_keymap.py': 'c2_v255_r1_keymap.py',
    'c2_v254_r1_keymap_receipt.py': 'c2_v255_r1_keymap_receipt.py',
    'c2_ide_exit_key_path_v254_r1.py': 'c2_ide_exit_key_path_v255_r1.py',
    'c2_v126_editor_allocation_o2_lite_r5_20261003.py': 'c2_v126_editor_allocation_o2_lite_r6_20261006.py',
    'v11_function_metadata_disk_r7_v254_r7_20261003.py': 'v11_function_metadata_disk_r7_v255_r8_20261006.py',
    'v2_string_codec_workloads_v254_r3_20261003.py': 'v2_string_codec_workloads_v255_r4_20261006.py',
    # r2 / r3: 2.5.5 documentation gate successors (r3: the ship-time r2 gates) and the media census successor
    'c2_v254_r2_bundle_docs_gate.py': 'c2_v255_r2_bundle_docs_gate.py',
    'c2_v254_r2_v210_bundle_docs.py': 'c2_v255_r2_v210_bundle_docs.py',
    'c2_v254_r2_public_naming.py': 'c2_v255_r2_public_naming.py',
    'c2_v254_r1_media_census.py': 'c2_v255_r1_media_census.py',
}
TOOL_REPLACEMENTS = {**REPLACEMENTS,
                     'c2_bound_artifact_source_parity_v254_20261003.py': 'c2_bound_artifact_source_parity_v255_20261006.py'}
NEW_TOOLS = ['c2_v255_r1_common.py', 'c2_v255_editor_key_cost_20261006.py',
             # r2
             'c2_v255_r1_card5_product.py', 'c2_v255_r1_document_index.py', 'c2_v255_r1_reproduction_gate.py',
             'c2_v255_r1_toolchain.py', 'historical_host_pin_v255_20261007.py',
             'c2_release_era_host_pin_v255_20261007.py']
RECEIPT_REPLACEMENTS = {
    'config/c2-v254-r1-keymap-receipt.json': 'config/c2-v255-r1-keymap-receipt.json',
    'config/c2-v126-editor-allocation-o2-lite-receipt-r5-20261003.json':
        'config/c2-v126-editor-allocation-o2-lite-receipt-r6-20261006.json',
    'config/v11-function-metadata-v254-r7-20261003-receipt.json': 'config/v11-function-metadata-v255-r8-20261006-receipt.json',
    'config/v2-string-codec-workloads-v254-r3-20261003-receipt.json':
        'config/v2-string-codec-workloads-v255-r4-20261006-receipt.json',
    # r2
    'config/c2-v254-r2-bundle-docs.json': 'config/c2-v255-r2-bundle-docs.json',
    'config/c2-v254-r2-public-naming-receipt.json': 'config/c2-v255-r2-public-naming-receipt.json',
    'config/c2-v254-r2-v210-bundle-docs-receipt.json': 'config/c2-v255-r2-v210-bundle-docs-receipt.json',
}
NEW_RECEIPTS = ['config/c2-v255-r1-reproduction-policy.json']
NEW_ROUTE = ('mk/gates.mk', 'c2-v255-editor-key-cost-check',
             ['c2_v255_editor_key_cost_20261006.py selftest', 'c2_v255_editor_key_cost_20261006.py check'])
assert set(TOOL_REPLACEMENTS) <= set(H.TOOLS) and set(RECEIPT_REPLACEMENTS) <= set(H.RECEIPTS), 'predecessor lists moved'
TOOLS = [TOOL_REPLACEMENTS.get(p, p) for p in H.TOOLS] + NEW_TOOLS
RECEIPTS = [RECEIPT_REPLACEMENTS.get(p, p) for p in H.RECEIPTS] + NEW_RECEIPTS
K, V = H.K, H.V
K.ROUTES = {target: REPLACEMENTS.get(tool, tool) for target, tool in K.ROUTES.items()}
V.CHECK_HOST_ROUTES = copy.deepcopy(V.CHECK_HOST_ROUTES)
for targets in V.CHECK_HOST_ROUTES.values():
    for target, commands in targets.items():
        for old, new in REPLACEMENTS.items():
            commands = [c.replace(old, new) if c.split()[0] == old else c for c in commands]
        targets[target] = commands
assert NEW_ROUTE[1] not in V.CHECK_HOST_ROUTES[NEW_ROUTE[0]], 'the new route already exists in the predecessor'
V.CHECK_HOST_ROUTES[NEW_ROUTE[0]][NEW_ROUTE[1]] = list(NEW_ROUTE[2])


def derive():
    S.S.history(HISTORY)
    return dict(inherited=H.derive(), receipts=[S.S.bind(p) for p in RECEIPTS],
                tools=[S.S.bind('tools/host-lisp/' + p) for p in TOOLS],
                retargets=REPLACEMENTS, new_route=dict(file=NEW_ROUTE[0], target=NEW_ROUTE[1], commands=NEW_ROUTE[2]))


if __name__ == '__main__':
    R.V.route_children()
    R.pin_disk_r7_source_controls()
    S.finish('card5-v255', derive, RECEIPT, H,
             (__file__, 'Makefile', 'mk/gates.mk', 'mk/workbench.mk', 'README.md', 'docs/development.md', *RECEIPTS,
              *('tools/host-lisp/' + p for p in TOOLS)))
