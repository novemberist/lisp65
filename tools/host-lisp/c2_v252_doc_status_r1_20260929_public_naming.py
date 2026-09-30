"""Retain naming classifications and mutations; bind reconciled User Guide."""
import c2_v251_r2_20260929_public_naming as H
import c2_v252_doc_status_r1_20260929_common as S
HISTORY={'tools/host-lisp/c2_v251_r2_20260929_public_naming.py': '6fc900f693c6429d0852c1fb635aaefe037e9e8dfd0439a2dcddd85440e581d9', 'config/c2-v251-r2-20260929-public-naming-receipt.json': '4dfefc11dffe2da9b6964c7e59c92d784cc74d74321b03a48338fb580d50b4ee'}
def derive():
    H.history_check()
    H.H.HISTORY=dict(H.H.HISTORY,**H.HISTORY)
    return H.H.derive()
if __name__=='__main__':
    S.finish('public-naming',derive,HISTORY,(__file__,S.__file__,'docs/user-guide.md'))
