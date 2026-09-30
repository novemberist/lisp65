"""Keep 2.1 replay and mixed-keymap control; use the post-publication live docs."""
import c2_v251_r2_20260929_v210_bundle_docs as H
import c2_v252_doc_status_r1_20260929_bundle_docs_gate as LIVE
import c2_v252_doc_status_r1_20260929_common as S
HISTORY={'tools/host-lisp/c2_v251_r2_20260929_v210_bundle_docs.py': '191543f7087df2a5136d4153eb8f741f024b06b5869aeafd5ecbdede588b47b9', 'config/c2-v251-r2-20260929-v210-bundle-docs-receipt.json': 'cb694f88fa2c9c84a427807c2279fd173f02c3e81f23c4cd9b1d114e3680d0f0'}
def derive():
    S.history(H.HISTORY)
    H.LIVE=LIVE
    return H.derive()
if __name__=='__main__':
    S.finish('v210-bundle-docs',derive,HISTORY,(__file__,S.__file__,LIVE.__file__,H.S.__file__,H.S.KEYMAP,
        'docs/user-guide.md','docs/generated/ide-keymap.md','config/c2-v252-doc-status-r1-20260929-bundle-docs.json'))
