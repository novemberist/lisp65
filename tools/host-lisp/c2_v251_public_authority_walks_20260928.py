"""Keep the released Backspace Final authority in its era; bind live walks."""
from unittest.mock import patch
import c2_v251_public_product as H
import evidence_era as E
import walks_successor_20260928 as W
RECEIPT='config/c2-v251-public-authority-receipt-walks-20260928.json'
HISTORY={'tools/host-lisp/c2_v251_public_product.py': 'd04505c8c04898ad948450c882eea7f27c2ad4653948e83edb3b6eb8b8a3153f', 'tools/host-lisp/c2_v251_public_native.py': '3907e3b34bd6cd48375fe42b7335b6485f9755c1ac4abe9d4df0a3c41e093ec4', 'config/c2-v251-public-build-authority.json': '66b9f27e8dc0f85a19578b4232768df2d62a614dbcbda33976ae42c4886241d4'}
def derive():
    with E.host_source_world('c8c20a64^') as reads:
        historical=H.preflight()
    original=E.era_blob
    def corrupt(commit,path):
        return original(commit,path)+(b'changed' if path==W.SOURCE else b'')
    with patch.object(E,'era_blob',corrupt),E.host_source_world('c8c20a64^'):
        try:H.preflight()
        except ValueError:pass
        else:raise ValueError('historical editor corruption survived')
    return dict(historical_backspace_final=historical,era_reads=reads,historical_editor_mutation_rejected=True,
                claim_limit='Released Backspace Final only; walks product remains unbuilt')
if __name__=='__main__':
    W.finish('c2-v251-public-authority',derive,RECEIPT,HISTORY,(__file__,H.__file__,H.N.__file__))
