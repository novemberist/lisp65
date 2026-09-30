"""O2-lite successor for the blink consumer unmasked by phase-1b repair."""
import c2_v17_repl_idle_blink_strings_r2_20260928 as H
import o2_lite_consumers_20260929 as S
RECEIPT='config/c2-v17-repl-idle-blink-o2-lite-receipt-20260929.json'
HISTORY={'tools/host-lisp/c2_v17_repl_idle_blink_strings_r2_20260928.py': '85b1e5f9dcd0227d034b8e41da4389142b88a1e7f376ec959990531fe8b65cfb', 'config/c2-v17-repl-idle-blink-receipt-strings-r2-20260928.json': 'c8f84be28dd44fbc7a342415d67171894d10ffe0648c7e053840b994e88c4cdc'}
# Retain every predecessor binding and its mutation controls.
HISTORY = {**H.HISTORY, **HISTORY}
INPUTS = [row['path'] for row in S.json.loads((S.ROOT / H.RECEIPT).read_bytes())['inputs']]
def derive():
    with S.E.host_source_world(S.ERA,extra_paths=('config/comfort-default-plane/libraries/repl-comfort-suite.json',)), S.scratch():
        inherited=H.derive()
    S.continuity(inherited,'config/c2-v17-repl-idle-blink-receipt-strings-r2-20260928.json')
    return dict(historical_strings=inherited,live_o2_lite=S.live())
if __name__=='__main__':
    S.finish('c2-v17-repl-idle-blink',derive,RECEIPT,HISTORY,(__file__,*INPUTS,H.__file__))
