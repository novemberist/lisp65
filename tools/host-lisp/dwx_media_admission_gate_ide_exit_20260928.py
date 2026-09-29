"""Historical DWX receipt verification plus live IDE-exit host successor."""
import dwx_media_admission_gate as H
import dwx_prefilter_blind_spot_contract_ide_exit_20260928 as D
import evidence_era as E
import ide_exit_successor_20260928 as S

RECEIPT = 'config/dwx-media-admission-gate-receipt-ide-exit-20260928.json'
HISTORY = {'tools/host-lisp/dwx_media_admission_gate.py': '9056268a40fd469d4320f1f5bef50d50e480b0caa38e0c7b55fa18667a5ba611', 'tests/bytecode/dialect-v2/evidence/post-release/dwx-media-admission-gate-receipt-20260902.json': 'fde47b9458a3a5b821b153ac4ec8df0708bc6a9c0741a0dec1b3a84494bd7b6f'}


def derive():
    with E.host_source_world(S.KEYMAP_ERA, (S.KEYMAP,)) as reads:
        H.selftest()
        H.check()
    return dict(historical_receipt=S.bind(H.RECEIPT_PATH),
                historical_reads=reads, live_source_contract=D.derive())


if __name__ == '__main__':
    S.finish('dwx_media_admission_gate', derive, RECEIPT, HISTORY,
             (S.KEYMAP, __file__, S.__file__, D.__file__))
