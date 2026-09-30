"""Dated O2-lite successor; inherited assertions and controls remain intact."""
import comfort_default_resolver_strings_r2_20260928 as H
import o2_lite_consumers_20260929 as S
RECEIPT='config/comfort-default-resolver-o2-lite-receipt-20260929.json'
HISTORY={'tools/host-lisp/comfort_default_resolver_strings_r2_20260928.py': '3ed1f18768d2e05e3513edb886131217ab80ef47ef492d620843f9fe10d145cf', 'config/c2-require-resolver-receipt-strings-r2-20260928.json': '0eda200554ad434068979aa163be59f2deab99c0826d1cacf95889f25f751da6'}
# Retain every predecessor binding and its mutation controls.
HISTORY = {**H.HISTORY, **HISTORY}
INPUTS = [row['path'] for row in S.json.loads((S.ROOT / H.RECEIPT).read_bytes())['inputs']]
def derive():
    with S.suites():current=H.derive()
    return S.continuity(current, 'config/c2-require-resolver-receipt-strings-r2-20260928.json')
if __name__=='__main__':
    import sys
    if len(sys.argv)==1:sys.argv.append('check')
    S.finish('comfort_default_resolver',derive,RECEIPT,HISTORY,(__file__,*INPUTS,H.__file__))
