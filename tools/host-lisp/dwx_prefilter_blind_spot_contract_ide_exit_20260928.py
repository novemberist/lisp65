"""Keep the DWX qualification in its era and bind the live host tuple proof."""
import dwx_prefilter_blind_spot_contract as H
import dwx_keymap_transport_ide_exit_20260928 as K
import evidence_era as E
import ide_exit_successor_20260928 as S


def derive():
    with E.host_source_world(S.KEYMAP_ERA, (S.KEYMAP,)) as reads:
        H.selftest()
        H.check()
    return dict(historical_contract=S.bind(H.CONTRACT_PATH),
                historical_reads=reads, transport=K.derive())

RECEIPT = 'config/dwx-prefilter-blind-spot-contract-receipt-ide-exit-20260928.json'
HISTORY = {'tools/host-lisp/dwx_prefilter_blind_spot_contract.py': '6ed8c2457a6c91df8f2b11933247dcfc899bb23b8e7e182beacfabc6361e8516', 'config/dwx-prefilter-blind-spot-contract.json': '355e87ce51666db1a14dcbf3dcabdb1448329a7fd1d2429dffa194e118f94917'}


if __name__ == '__main__':
    S.finish('dwx-prefilter-blind-spot-contract', derive, RECEIPT, HISTORY,
             (S.KEYMAP, __file__, K.__file__, S.__file__))
