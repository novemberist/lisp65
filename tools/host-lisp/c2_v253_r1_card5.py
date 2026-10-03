"""2.5.3 Card-5 successor: route retargets to the 2.5.3 dated successors.

Successor of c2_v252_r1_card5 (immutable, receipt r4). The inherited chain is
re-derived unchanged. Additionally the expected routes are retargeted to the
2.5.3 candidate's dated successors: the editor-allocation and private-inline
probe successors committed with the source candidate, and the era-scoped or
remeasured successors created for the 2.5.3 gate closure (function metadata,
prelude evidence, Comfort track/C2-Q/resolver, IDE exit key path, chain walker,
stdlib artifacts, Comfort phase 1b, Card 4 compiler prelude). Every retarget
names the exact predecessor command; all other routes keep their v252 meaning.
"""
import copy
import c2_v252_r1_card5 as H
import disk_r7_consumers_20260930 as S
import era_replay_v253_20260930 as R
# r6: the 2.5.3 document layer, the v253 doc-gate/keymap/naming/census successors and the v252 release-era
# route (r5 predates them; write-once, r5 is superseded).
# r7: the check-host r1 closure (number->string verdict, Werkbank suite and private-inline probe successors,
# 2026-10-02) and the Makefile routes for them; r6 is committed and superseded.
# r8: the 2.5.3 r8 source cycle (2026-10-02): LCC nesting-depth fix + REPL OOM landing fix, their two host
# gates (ladder, OOM recovery) with receipts and mk routes, and the v11 function-metadata r6 successor;
# r7 is committed and superseded.
# r9: the 2.5.3 Final r8 release chain (2026-10-03): the r2 successors of the public-source authority, reproduction
# gate, media census and the bundle-docs/naming/v210 doc gates (the r1 family belongs to the unshipped Final r7 and
# is retired from the routes; keymap, toolchain, document index and the v252 era reader are release-neutral and stay
# r1); r8 is committed and superseded.
# r10: the ship-time documentation gates (2026-10-03, device session passed): the r3 successors of the bundle-docs,
# naming and v210 gates and their receipts replace the r2 candidate-time ones in the routes; r9 is committed and superseded.
RECEIPT = 'config/c2-v253-r1-card5-receipt-r10.json'
HISTORY = {'tools/host-lisp/c2_v251_card5_disk_r7_20260930.py': 'f98f775fd7071749bd0306e9298a1bf5fa577a2a86cec880cdc8b6f6cd7a7cc9',
           'config/c2-v251-card5-disk-r7-receipt-r2-20260930.json': '324327edaaec6a712f55d60abae98d55d2add4a351c4737d38ff24ff923839c1'}
REPLACEMENTS = {
    'c2_v252_r1_card5.py': 'c2_v253_r1_card5.py',
    'c2_v126_editor_allocation_o2_lite_20260929.py': 'c2_v126_editor_allocation_o2_lite_r4_20261001.py',
    'workbench-private-inline-composition-probe-v252-20260930.json': 'workbench-private-inline-composition-probe-v253-20260930.json',
    'v11_function_metadata_disk_r7_20260930.py': 'v11_function_metadata_disk_r7_v253_r6_20261002.py',
    'dialect_v2_prelude_evidence.py': 'dialect_v2_prelude_evidence_v253_20260930.py',
    'comfort_track_o2_lite_20260929.py': 'comfort_track_o2_lite_v253_20260930.py',
    'c2_q_o2_lite_20260929.py': 'c2_q_o2_lite_v253_r3_20261001.py',
    'comfort_default_option_a_o2_lite_20260929.py': 'comfort_default_option_a_o2_lite_v253_r3_20261001.py',
    'c2_ide_exit_key_path_20260928.py': 'c2_ide_exit_key_path_v253_20260930.py',
    'chain_walker_inventory_disk_r7_20260930.py': 'chain_walker_inventory_disk_r7_v253_20260930.py',
    'stdlib_artifacts_disk_r7_20260930.py': 'stdlib_artifacts_disk_r7_v253_20260930.py',
    'c2_v17_comfort_phase1b_disk_r7_20260930.py': 'c2_v17_comfort_phase1b_disk_r7_v253_20260930.py',
    'disk_r7_consumers_20260930.py': 'disk_r7_consumers_v253_20260930.py',
    'disk_r7_consumer_mutations_20260930.py': 'disk_r7_consumer_mutations_v253_20260930.py',
    'c2_v160_hybrid_disk_r7_20260930.py': 'c2_v160_hybrid_disk_r7_v253_20260930.py',
    'c2_v160_hybrid_capacity_disk_r7_20260930.py': 'c2_v160_hybrid_capacity_disk_r7_v253_20260930.py',
    'c2_v17_repl_idle_blink_disk_r7_20260930.py': 'c2_v17_repl_idle_blink_disk_r7_v253_20260930.py',
    'dialect_v2_system_runtime_disk_r7_20260930.py': 'dialect_v2_system_runtime_disk_r7_v253_20260930.py',
    'dialect_v2_prelude_evidence_disk_r7_20260930.py': 'dialect_v2_prelude_evidence_disk_r7_v253_20260930.py',
    'c2_v160_comfort_repl_o2_lite_20260929.py': 'c2_v160_comfort_repl_o2_lite_v253_r2_20261001.py',
    'block_26_compiler_prelude_card.py': 'block_26_compiler_prelude_card_v253_r2_20261001.py',
    'v2_string_codec_workloads_disk_r7_20260930.py': 'v2_string_codec_workloads_v253_r2_20261001.py',
    'v2_workbench_codemod_disk_r7_20260930.py': 'v2_workbench_codemod_disk_r8_20261001.py',
    # r4: reviewer LCC arity fix (lib/dialect-v2/lcc-profile.lisp) successors
    'code_object_arity_contract.py': 'code_object_arity_contract_v253_20261001.py',
    'c2_top_level_macro_redispatch.py': 'c2_top_level_macro_redispatch_v253_20261001.py',
    # r6: 2.5.3 documentation/gate successors (the v252 names are the live routes' previous targets)
    'c2_v252_r1_bundle_docs_gate.py': 'c2_v253_r3_bundle_docs_gate.py',
    'c2_v252_r1_v210_bundle_docs.py': 'c2_v253_r3_v210_bundle_docs.py',
    'c2_v252_r1_public_naming.py': 'c2_v253_r3_public_naming.py',
    'c2_v252_r1_keymap.py': 'c2_v253_r1_keymap.py',
    'c2_v252_r1_keymap_receipt.py': 'c2_v253_r1_keymap_receipt.py',
    'c2_v252_r1_media_census.py': 'c2_v253_r2_media_census.py',
}
TOOLS = ['c2_v253_r1_card5_product.py', 'era_replay_v253_20260930.py', 'disk_r7_product_receipts_v253_20260930.py', *(v for v in REPLACEMENTS.values() if v.endswith('.py')),
         'comfort_default_resolver_o2_lite_v253_r3_20261001.py', 'm65d_disk_integrity_v253_20261001.py',
         'c2_v253_r1_common.py', 'c2_v253_r2_common.py', 'c2_v253_r2_reproduction_gate.py', 'c2_v253_r1_toolchain.py',
         'c2_v253_r1_document_index.py', 'c2_v253_r1_v252_release_era.py',
         'dialect_v2_number_to_string_v253_20261002.py', 'workbench_private_inline_probe_v253_20261002.py',
         'lcc_nesting_ladder_v253_20261002.py', 'repl_oom_recovery_v253_20261002.py']
RECEIPTS = ['config/v11-function-metadata-v253-r6-20261002-receipt.json',
            'tests/bytecode/dialect-v2/evidence/capability-carrier/lcc-nesting-ladder-v253-20261002.json',
            'tests/bytecode/dialect-v2/evidence/capability-carrier/repl-oom-recovery-v253-20261002.json',
            'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-link95-top-level-macro-publication-receipt-v253-20261001.json',
            'config/c2-v126-editor-allocation-o2-lite-receipt-r4-20261001.json',
            'config/v2-string-codec-workloads-v253-r2-20261001-receipt.json',
            'config/v2-workbench-artifact-closure-disk-r8-20261001.json',
            'tests/bytecode/libs/p0-m65d-lib-disk-r8-20261001.json',
            'config/c2-v160-comfort-repl-o2-lite-v253-receipt-r2-20261001.json',
            'config/c2-q-v253-r3-20261001-receipt.json',
            'config/comfort-default-resolver-v253-r3-20261001-receipt.json',
            'tests/bytecode/dialect-v2/evidence/architecture-blocks/comfort-track-live-domain-receipt-v253-20260930.json',
            'tests/bytecode/dialect-v2/evidence/capability-carrier/workbench-private-inline-composition-probe-v253-20260930.json',
            'tests/bytecode/dialect-v2/evidence/capability-carrier/workbench-private-inline-composition-probe-v253-20261002.json',
            'tests/bytecode/dialect-v2/evidence/capability-carrier/number-to-string-prototype/four-engine-v253-20261002-verdict.json',
            'tests/bytecode/stdlib/p0-stdlib-werkbank-subset-v253-20261002.json',
            'config/c2-v253-r3-bundle-docs.json', 'config/c2-v253-r3-public-naming-receipt.json',
            'config/c2-v253-r1-keymap-receipt.json', 'config/c2-v253-r3-v210-bundle-docs-receipt.json',
            'config/c2-v253-r1-v252-release-era.json', 'config/c2-v253-r2-reproduction-policy.json']
K, V = H.K, H.V
K.ROUTES = {target: REPLACEMENTS.get(tool, tool) for target, tool in K.ROUTES.items()}
V.CHECK_HOST_ROUTES = copy.deepcopy(V.CHECK_HOST_ROUTES)
for targets in V.CHECK_HOST_ROUTES.values():
    for target, commands in targets.items():
        for old, new in REPLACEMENTS.items():
            commands = [c.replace(old, new) for c in commands]
        targets[target] = commands


def derive():
    S.S.history(HISTORY)
    return dict(inherited=H.derive(), receipts=[S.S.bind(p) for p in RECEIPTS],
                tools=[S.S.bind('tools/host-lisp/' + p) for p in TOOLS])


if __name__ == '__main__':
    R.pin_disk_r7_source_controls()
    S.finish('card5-v253', derive, RECEIPT, H,
             (__file__, 'Makefile', 'mk/gates.mk', 'mk/workbench.mk', 'README.md', 'docs/development.md', *RECEIPTS,
              *('tools/host-lisp/' + p for p in TOOLS)))
