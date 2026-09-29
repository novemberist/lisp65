"""Historical DWX receipt verification plus live IDE-exit host successor."""
import dwx_freezer_free_boot_variants as H
import dwx_prefilter_blind_spot_contract_ide_exit_20260928 as D
import evidence_era as E
import ide_exit_successor_20260928 as S

RECEIPT = 'config/dwx-freezer-free-boot-variants-receipt-ide-exit-20260928.json'
HISTORY = {'tools/host-lisp/dwx_freezer_free_boot_variants.py': '358871d6f355bdd21cd12752492fc8ac9e5396795462a7c688b86f795f6c0aa7', 'tests/bytecode/dialect-v2/evidence/post-release/dwx-freezer-free-boot-variants-receipt-20260902.json': 'f303b11ba59bd9542814817bd7dbabe75559eb30a7244e1b28a8fc47e85b8ad9'}


def derive():
    with E.host_source_world(S.KEYMAP_ERA, (S.KEYMAP,)) as reads:
        H.selftest()
        H.check()
    return dict(historical_receipt=S.bind(H.RECEIPT_PATH),
                historical_reads=reads, live_source_contract=D.derive())


if __name__ == '__main__':
    S.finish('dwx_freezer_free_boot_variants', derive, RECEIPT, HISTORY,
             (S.KEYMAP, __file__, S.__file__, D.__file__))
