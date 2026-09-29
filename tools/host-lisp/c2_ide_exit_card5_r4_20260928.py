"""Card-5 r4: r3 routes, with the loader-independent v11 function-metadata receipt (r2)."""
import copy
import c2_ide_exit_card5_r2_20260928 as H
import ide_exit_successor_20260928 as S

H.H.H.K.ROUTES = dict(H.H.H.K.ROUTES, **{
    'block-26-build-integrity-check': 'c2_ide_exit_card5_r4_20260928.py'})
H.H.CHECK_HOST_ROUTES = copy.deepcopy(H.H.CHECK_HOST_ROUTES)
H.H.CHECK_HOST_ROUTES['mk/gates.mk']['block-26-build-integrity-selftest'] = [
    'c2_ide_exit_card5_r4_20260928.py selftest']
ROUTES = {
    'mk/gates.mk': {
        'block-26-small-hardening-selftest': ['block_26_small_hardening_card_ide_exit_20260928.py selftest'],
        'block-26-small-hardening-check': ['block_26_small_hardening_card_ide_exit_20260928.py check'],
        'c2-v126-editor-allocation-selftest': ['c2_v126_editor_allocation_ide_exit_20260928.py selftest'],
        'c2-v126-editor-allocation-check': ['c2_v126_editor_allocation_ide_exit_20260928.py check'],
        'block-26-card1-sidx-check': ['block_26_sidx_dwx_prefilter_ide_exit_20260928.py check'],
        'v210-bundle-docs-check': ['c2_v210_bundle_docs_ide_exit_20260928.py check'],
    },
    'mk/workbench.mk': {
        'v11-function-metadata-selftest': ['v11_function_metadata_ide_exit_20260928.py selftest'],
        'v11-function-metadata-check': ['v11_function_metadata_ide_exit_20260928.py check'],
    },
    'Makefile': {
        'v2-string-codec-workload-selftest': ['v2_string_codec_workloads_ide_exit_20260928.py selftest'],
        'v2-string-codec-workload-check': ['v2_string_codec_workloads_ide_exit_20260928.py check'],
        'dwx-freezer-free-boot-variants-check': ['dwx_freezer_free_boot_variants_ide_exit_20260928.py selftest', 'dwx_freezer_free_boot_variants_ide_exit_20260928.py check'],
        'dwx-media-admission-gate-check': ['dwx_media_admission_gate_ide_exit_20260928.py selftest', 'dwx_media_admission_gate_ide_exit_20260928.py check'],

        'dwx-prefilter-blind-spot-contract-check': [
            'dwx_keymap_transport_ide_exit_20260928.py check',
            'dwx_prefilter_blind_spot_contract_ide_exit_20260928.py selftest',
            'dwx_prefilter_blind_spot_contract_ide_exit_20260928.py check'],
    },
}
for path, targets in ROUTES.items():
    H.H.CHECK_HOST_ROUTES.setdefault(path, {}).update(targets)


def derive():
    return H.derive()

RECEIPT = 'config/c2-ide-exit-card5-receipt-r4-20260928.json'
HISTORY = {'tools/host-lisp/c2_ide_exit_card5_r2_20260928.py': '0d322bb30c405c9f98da5d947b7f2f9e84cdcacd6481cfc2b4a9a9b94b0a69bc', 'config/c2-ide-exit-card5-receipt-r2-20260928.json': '9e8ee2b61c96d2ab96081aebf7a4b9610de8ecaff017f2b1866c5a4f1632f15f'}
RECEIPTS = ['config/block-26-sidx-dwx-prefilter-receipt-ide-exit-20260928.json', 'config/block-26-small-hardening-card-receipt-ide-exit-20260928.json', 'config/c2-v126-editor-allocation-receipt-ide-exit-20260928.json', 'config/c2-v210-bundle-docs-receipt-ide-exit-20260928.json', 'config/dwx-keymap-transport-receipt-ide-exit-20260928.json', 'config/dwx-prefilter-blind-spot-contract-receipt-ide-exit-20260928.json', 'config/v11-function-metadata-receipt-ide-exit-r2-20260928.json']

if __name__ == '__main__':
    paths = [__file__, S.__file__]
    for targets in ROUTES.values():
        for commands in targets.values():
            paths.extend('tools/host-lisp/' + command.split()[0] for command in commands)
    # Exact population is pinned below; no glob selects future receipts.
    paths.extend(RECEIPTS)
    paths.append('config/v2-string-codec-workloads-receipt-ide-exit-20260928.json')
    paths.extend(['config/dwx-freezer-free-boot-variants-receipt-ide-exit-20260928.json', 'config/dwx-media-admission-gate-receipt-ide-exit-20260928.json'])
    S.finish('c2-ide-exit-card5-r4', derive, RECEIPT, HISTORY, paths)
