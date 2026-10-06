"""2.5.4 Card-5 successor: route retargets to the 2.5.4 dated successors.

Successor of c2_v253_r1_card5 (immutable, receipt r10).  The inherited chain
is re-derived unchanged; the expected routes are retargeted to the 2.5.4
candidate's dated successors (IDE card: keymap entry point and key-path check;
integration: keymap receipt, editor allocation E3 re-baseline, Comfort-REPL,
C-2Q, resolver/Option-A, function metadata, string codec, and the 2.5.3-era
replays of the immutable disk/Comfort consumers; the 2.5.3 public authority
runs in its release era, c2_v253_release_era_v254_20261004).  Every retarget names the
exact predecessor command; all other routes keep their v253 meaning.  The
r7 disk / O2-lite source pins are checked in the sealed 2.5.2 world
(era_replay_v254_20261003.pin_disk_r7_source_controls).
"""
import copy
import hashlib

import c2_v253_r1_card5 as H
import disk_r7_consumers_20260930 as S
import era_replay_v254_20261003 as R

# r3: the 2.5.4 candidate-time documentation gates (2026-10-04, Final sealed, device session pending): the r1
# successors of the bundle-docs, naming and v210 gates with their receipts replace the 2.5.3 r3 ones in the routes,
# and the 2.5.4 document-index successor is bound; the 2.5.4 public-source authority (reproduction gate and policy,
# media census successor in the census route, route v254-public-authority-check, toolchain record successor with
# the Fedora 45 host pins; historical host pin rule for the 2.5.3 / 2.5.2 era readers and the r7 product receipts);
# r2 is committed and superseded.
# r4 (2026-10-05, post-commit round after sealed check-host r2): host successor of the number->string four-engine pin
# (the live equivalence binary was rebuilt on Fedora 45; Makefile route, tool and v254 receipt); r3 is committed and superseded.
# r5 (2026-10-05, ship time, device session passed): the r2 successors of the bundle-docs, naming and v210 gates and their
# receipts replace the r1 candidate-time ones in the routes; r4 is committed and superseded.
RECEIPT = 'config/c2-v254-r1-card5-receipt-r5.json'
HISTORY = {p: hashlib.sha256((S.ROOT / p).read_bytes()).hexdigest() for p in (
    'tools/host-lisp/c2_v253_r1_card5.py', H.RECEIPT)}
REPLACEMENTS = {
    'c2_v253_r1_card5.py': 'c2_v254_r1_card5.py',
    'c2_v253_r1_keymap.py': 'c2_v254_r1_keymap.py',
    'c2_v253_r1_keymap_receipt.py': 'c2_v254_r1_keymap_receipt.py',
    'c2_ide_exit_key_path_v253_20260930.py': 'c2_ide_exit_key_path_v254_r1.py',
    'c2_v126_editor_allocation_o2_lite_r4_20261001.py': 'c2_v126_editor_allocation_o2_lite_r5_20261003.py',
    'c2_v160_comfort_repl_o2_lite_v253_r2_20261001.py': 'c2_v160_comfort_repl_o2_lite_v254_r3_20261003.py',
    'comfort_default_option_a_o2_lite_v253_r3_20261001.py': 'comfort_default_option_a_o2_lite_v254_r4_20261003.py',
    'v11_function_metadata_disk_r7_v253_r6_20261002.py': 'v11_function_metadata_disk_r7_v254_r7_20261003.py',
    'v2_string_codec_workloads_v253_r2_20261001.py': 'v2_string_codec_workloads_v254_r3_20261003.py',
    'c2_v160_hybrid_capacity_disk_r7_v253_20260930.py': 'c2_v160_hybrid_capacity_disk_r7_v254_20261003.py',
    'c2_v160_hybrid_disk_r7_v253_20260930.py': 'c2_v160_hybrid_disk_r7_v254_20261003.py',
    'c2_v17_comfort_phase1b_disk_r7_v253_20260930.py': 'c2_v17_comfort_phase1b_disk_r7_v254_20261003.py',
    'c2_v17_repl_idle_blink_disk_r7_v253_20260930.py': 'c2_v17_repl_idle_blink_disk_r7_v254_20261003.py',
    'stdlib_artifacts_disk_r7_v253_20260930.py': 'stdlib_artifacts_disk_r7_v254_20261003.py',
    # r3: 2.5.4 documentation gate successors (the v253 r3 names are the live routes' previous targets)
    'c2_v253_r3_bundle_docs_gate.py': 'c2_v254_r2_bundle_docs_gate.py',
    'c2_v253_r3_v210_bundle_docs.py': 'c2_v254_r2_v210_bundle_docs.py',
    'c2_v253_r3_public_naming.py': 'c2_v254_r2_public_naming.py',
    'c2_v253_r2_media_census.py': 'c2_v254_r1_media_census.py',
    # r4: host successor (Fedora 45)
    'dialect_v2_number_to_string_v253_20261002.py': 'dialect_v2_number_to_string_v254_20261005.py',
}
TOOLS = ['c2_v254_r1_card5_product.py', 'c2_v254_r1_common.py', 'era_replay_v254_20261003.py',
         'o2_lite_consumers_v254_20261003.py', *REPLACEMENTS.values(),
         'c2_bound_artifact_source_parity_v254_20261003.py', 'comfort_track_o2_lite_v254_20261003.py',
         'c2_q_o2_lite_v254_r4_20261003.py', 'comfort_default_resolver_o2_lite_v254_r4_20261003.py',
         'c2_m65_hw_o2_lite_v254_20261003.py', 'dialect_v2_system_runtime_disk_r7_v254_20261003.py',
         'dialect_v2_prelude_evidence_disk_r7_v254_20261003.py', 'bytecode_p0_omissions_v254_20261003.py',
         'c2_top_level_macro_redispatch_v254_20261003.py', 'chain_walker_inventory_disk_r7_v254_20261003.py',
         'disk_r7_consumers_v254_20261003.py', 'disk_r7_consumer_mutations_v254_20261003.py',
         'disk_r7_product_receipts_v254_20261003.py', 'lcc_nesting_ladder_v254_r2_20261004.py',
         'c2_v253_release_era_v254_20261004.py', 'v254_package_suites_20261004.py',
         'dialect_v2_lcc_surface_v254_20261004.py', 'c2_v254_r1_document_index.py',
         'c2_v254_r1_reproduction_gate.py', 'c2_v254_r1_toolchain.py', 'historical_host_pin_20261004.py',
         'c2_release_era_host_pin_v254_20261004.py', 'disk_r7_product_receipts_v254_r2_20261004.py']
RECEIPTS = ['config/c2-v254-r1-keymap-receipt.json',
            'config/c2-v126-editor-allocation-o2-lite-receipt-r5-20261003.json',
            'config/c2-v160-comfort-repl-o2-lite-v254-receipt-r3-20261003.json',
            'config/c2-q-v254-r4-20261003-receipt.json',
            'config/comfort-default-resolver-v254-r4-20261003-receipt.json',
            'config/v11-function-metadata-v254-r7-20261003-receipt.json',
            'config/v2-string-codec-workloads-v254-r3-20261003-receipt.json',
            'tests/bytecode/dialect-v2/evidence/architecture-blocks/comfort-track-live-domain-receipt-v254-20261003.json',
            'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-link95-top-level-macro-publication-receipt-v254-20261003.json',
            'tests/bytecode/dialect-v2/evidence/capability-carrier/lcc-nesting-ladder-v254-r2-20261004.json',
            'tests/bytecode/stdlib/p0-stdlib-werkbank-subset-v254-20261003.json',
            'tests/bytecode/libs/p0-repl-comfort-r254.json',
            'tests/bytecode/libs/p0-defstruct-names-r254.json',
            'config/c2-v253-release-era-v254-20261004.json',
            'tests/bytecode/libs/p0-stdlib-mapcan-r254.json',
            'tests/bytecode/dialect-v2/lcc-surface/cases-v254-20261004.json',
            'config/c2-v254-r2-bundle-docs.json', 'config/c2-v254-r2-public-naming-receipt.json',
            'config/c2-v254-r2-v210-bundle-docs-receipt.json', 'config/c2-v254-r1-reproduction-policy.json',
            'tests/bytecode/dialect-v2/evidence/capability-carrier/number-to-string-prototype/four-engine-v254-20261005-verdict.json']
K, V = H.K, H.V
K.ROUTES = {target: REPLACEMENTS.get(tool, tool) for target, tool in K.ROUTES.items()}
V.CHECK_HOST_ROUTES = copy.deepcopy(V.CHECK_HOST_ROUTES)
for targets in V.CHECK_HOST_ROUTES.values():
    for target, commands in targets.items():
        for old, new in REPLACEMENTS.items():
            commands = [c.replace(old, new) if c.split()[0] == old else c for c in commands]
        targets[target] = commands


def derive():
    S.S.history(HISTORY)
    return dict(inherited=H.derive(), receipts=[S.S.bind(p) for p in RECEIPTS],
                tools=[S.S.bind('tools/host-lisp/' + p) for p in TOOLS])


if __name__ == '__main__':
    R.V.route_children()
    R.pin_disk_r7_source_controls()
    S.finish('card5-v254', derive, RECEIPT, H,
             (__file__, 'Makefile', 'mk/gates.mk', 'mk/workbench.mk', 'README.md', 'docs/development.md', *RECEIPTS,
              *('tools/host-lisp/' + p for p in TOOLS)))
