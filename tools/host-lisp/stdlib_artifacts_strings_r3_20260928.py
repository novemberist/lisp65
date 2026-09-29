"""Reproduce strings artifacts in unbound scratch with content-only receipts."""
import stdlib_artifacts_strings_r2_20260928 as H
import strings_successor_r2_20260928 as S
from strings_scratch_20260928 import scratch, normalized
RECEIPT='config/strings-stdlib-artifacts-receipt-r3-20260928.json'
HISTORY = {'tools/host-lisp/stdlib_artifacts_strings_r2_20260928.py': 'ad42490d2adc094e828ce2b1a304c8bdb48eaed055c4cd9539234affe19e51d0', 'config/strings-stdlib-artifacts-receipt-r2-20260928.json': '5a967f01e2266bb9b499a463f79f55bf0dca6d9fded86e762f93c38fbcad9719'}
def derive():
    from unittest.mock import patch
    import c2_lite_v6_product_probe as V6
    with scratch() as root, patch.object(V6,'OUT',root/'entry-emitter'):
        return normalized(H.derive(),root)
if __name__=='__main__':S.finish('stdlib-artifacts-r3',derive,RECEIPT,HISTORY,(__file__,'tools/host-lisp/strings_scratch_20260928.py'))
