"""Dated O2-lite successor; inherited assertions and controls remain intact."""
import c2_q_strings_r2_20260928 as H
import o2_lite_consumers_20260929 as S
RECEIPT='config/c2-q-o2-lite-receipt-20260929.json'
HISTORY={'tools/host-lisp/c2_q_strings_r2_20260928.py': 'a46ef6044b29bb267e160b58c95b193e0aea9429626c89feab42e9641ea0f2ab', 'config/c2-q-receipt-strings-r2-20260928.json': '3c164559de6af3f2c5eb8acea86bdfd2e1e34f26200cd972b0d5bec47a7c9780'}
# Retain every predecessor binding and its mutation controls.
HISTORY = {**H.HISTORY, **HISTORY}
INPUTS = [row['path'] for row in S.json.loads((S.ROOT / H.RECEIPT).read_bytes())['inputs']]
def derive():
    with S.suites():current=H.derive()
    return S.continuity(current, 'config/c2-q-receipt-strings-r2-20260928.json')
if __name__=='__main__':
    S.finish('c2_q',derive,RECEIPT,HISTORY,(__file__,*INPUTS,H.__file__))
