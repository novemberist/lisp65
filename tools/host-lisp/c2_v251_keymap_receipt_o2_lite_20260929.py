"""Dated O2-lite successor; inherited assertions and controls remain intact."""
import c2_v251_r2_20260929_keymap_receipt as H
import o2_lite_consumers_20260929 as S
RECEIPT='config/c2-v251-keymap-receipt-o2-lite-receipt-20260929.json'
HISTORY={'tools/host-lisp/c2_v251_r2_20260929_keymap_receipt.py': '3aa6d5f20a5360b4d7a3ece602a15653a47f39017783c9c2f16e122068783bc1', 'config/c2-v251-r2-20260929-keymap-receipt.json': 'aa0c0e5fbeeb81044cdea703a2bbe18d45900baf3b4865d0245e64b25a141c13'}
def derive():
    current=H.derive()
    old=S.json.loads(H.RECEIPT.read_bytes())
    expected=S.copy.deepcopy(old)
    changed=[a['path'] for a,b in zip(old['files'],current['files'],strict=True) if a!=b]
    S.S.require(changed==['lib/stdlib-read-line.lisp'],'keymap input population drift')
    for row in expected['files']:
        if row['path']=='lib/stdlib-read-line.lisp':row.update(S.S.bind(row['path']))
    S.S.require(current==expected,'keymap exact binding drift')
    return current
if __name__=='__main__':
    S.finish('c2_v251_keymap_receipt',derive,RECEIPT,HISTORY,(__file__,H.__file__))
