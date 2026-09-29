"""Card-1 sealed prefilter replay plus IDE-exit host transport successor."""
import block_26_sidx_dwx_prefilter as H
import dwx_prefilter_blind_spot_contract_ide_exit_20260928 as D
import evidence_era as E
import ide_exit_successor_20260928 as S


def derive():
    with E.host_source_world(S.KEYMAP_ERA, (S.KEYMAP,)) as reads:
        H.check()
    return dict(sealed_prefilter=S.bind(H.PREFILTER_RECEIPT),
                historical_reads=reads, live_source_contract=D.derive())

RECEIPT = 'config/block-26-sidx-dwx-prefilter-receipt-ide-exit-20260928.json'
HISTORY = {'tools/host-lisp/block_26_sidx_dwx_prefilter.py': '3b460f7101b4aea8dbf44c073dc99470261fae522a58df22ad8accc7c11ed12e', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/block-2.6-card1-sidx-dwx-prefilter-r2.json': '514eba374347e8faaefc7245df4cf48c1da61f10c15eb6824fc19b16b35f0c17'}


if __name__ == '__main__':
    S.finish('block-26-sidx-dwx-prefilter', derive, RECEIPT, HISTORY,
             (S.KEYMAP, __file__, D.__file__, S.__file__))
